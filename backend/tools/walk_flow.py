"""Walk the one flow this marketplace has, over HTTP, and say where it breaks.

    .venv/bin/python -m tools.walk_flow                    # against :8000
    .venv/bin/python -m tools.walk_flow --api http://localhost:8010/api/v1

Twelve steps, each one somebody's turn:

    1  seller    creates a product with sizes and quantities, and submits it
    2  seller    sees it waiting, with no stock figure yet
    3  customer  cannot find it — it is not in the shop
    4  warehouse sees the batch and counts it in (one size one short)
    5  seller    sees it on sale, at the counted quantity
    6  customer  finds it, opens it, sees the sizes
    7  customer  buys one
    8  seller    sees the order, and the stock is one lower
    9  warehouse packs it, operator hands it to a courier
   10  courier   delivers it
   11  customer  asks to send it back; it reaches the warehouse; warehouse
                 says it is undamaged
   12  seller    puts it back on sale, and the stock is whole again

Every assertion is a sentence about the flow rather than about a field, and a
failure prints the request that produced it. Nothing is mocked and nothing is
written straight to the database: every step goes through the door the panel
would use, as the role that panel signs in as, so a step that passes here is a
step a person can do.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

ADMIN = "+998900000001"
OPERATOR = "+998900000002"
WAREHOUSE = "+998900000003"
COURIER = "+998900000004"
SELLER = "+998900000005"
CUSTOMER = "+998901234567"
CODE = "123456"

GREEN, RED, DIM, BOLD, OFF = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


class Fail(Exception):
    pass


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.tokens: dict[str, str] = {}
        self.last = ""

    def call(self, method, path, *, who=None, json_body=None, query=None, key=None):
        url = f"{self.base}{path}"
        if query:
            parts = [f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items() if v is not None]
            url += "?" + "&".join(parts)
        data = json.dumps(json_body).encode() if json_body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data:
            request.add_header("Content-Type", "application/json")
        if who:
            request.add_header("Authorization", f"Bearer {self.tokens[who]}")
        # Writes a courier makes twice by accident must land once. The header
        # is required rather than optional, which is the right way round: a
        # client that forgets it is told, not silently allowed to double-post.
        if key:
            request.add_header("Idempotency-Key", key)
        self.last = f"{method} {url}" + (f"\n     body {json.dumps(json_body)}" if data else "")
        try:
            with urllib.request.urlopen(request, timeout=20) as answer:
                body = answer.read().decode()
                return answer.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as error:
            body = error.read().decode()
            try:
                return error.code, json.loads(body)
            except json.JSONDecodeError:
                return error.code, body

    def ok(self, method, path, *, who=None, json_body=None, query=None, key=None,
           expect=(200, 201)):
        status, body = self.call(method, path, who=who, json_body=json_body, query=query, key=key)
        if status not in expect:
            raise Fail(f"{self.last}\n     → HTTP {status} {json.dumps(body)[:400]}")
        return body

    def upload_png(self, who: str) -> str:
        """A real picture through the real door — a card with none is refused."""
        import io
        import uuid

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (600, 600), (245, 245, 245)).save(buffer, format="PNG")
        boundary = uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="tovar.png"\r\n',
            b"Content-Type: image/png\r\n\r\n",
            buffer.getvalue(),
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        request = urllib.request.Request(
            f"{self.base}/staff/media", data=body, method="POST"
        )
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        request.add_header("Authorization", f"Bearer {self.tokens[who]}")
        self.last = f"POST {self.base}/staff/media (png)"
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                out = json.loads(answer.read().decode())
        except urllib.error.HTTPError as error:
            raise Fail(f"{self.last}\n     → HTTP {error.code} {error.read().decode()[:300]}")
        return out["media_url"]

    def sign_in(self, phone: str, label: str) -> None:
        self.ok("POST", "/auth/otp/request", json_body={"phone": phone})
        out = self.ok("POST", "/auth/otp/verify", json_body={"phone": phone, "code": CODE})
        self.tokens[label] = out["access_token"]


class Walk:
    def __init__(self, api: Api) -> None:
        self.api = api
        self.step = 0
        self.failures: list[tuple[str, str]] = []
        self.notes: list[str] = []

    def __call__(self, title):
        def run(fn):
            self.step += 1
            head = f"{self.step:>2}. {title}"
            try:
                detail = fn()
                print(f"  {GREEN}✓{OFF} {head}" + (f"  {DIM}{detail}{OFF}" if detail else ""))
            except Fail as error:
                print(f"  {RED}✗{OFF} {head}")
                print(f"     {RED}{error}{OFF}")
                self.failures.append((head, str(error)))
            except Exception as error:  # noqa: BLE001 — the report is the point
                print(f"  {RED}✗{OFF} {head}")
                print(f"     {RED}{type(error).__name__}: {error}{OFF}")
                self.failures.append((head, f"{type(error).__name__}: {error}"))
            return fn
        return run

    def expect(self, claim: str, condition: bool, saw=None) -> None:
        if not condition:
            raise Fail(f"{claim}\n     saw: {json.dumps(saw, ensure_ascii=False)[:400]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    args = parser.parse_args()

    api = Api(args.api)
    walk = Walk(api)
    state: dict = {}

    print(f"\n{BOLD}Mini Bozor — the whole flow, over {api.base}{OFF}\n")

    print(f"{DIM}  signing in{OFF}")
    for phone, label in [
        (SELLER, "seller"), (WAREHOUSE, "warehouse"), (OPERATOR, "operator"),
        (COURIER, "courier"), (ADMIN, "admin"), (CUSTOMER, "customer"),
    ]:
        try:
            api.sign_in(phone, label)
        except Fail as error:
            print(f"  {RED}✗ cannot sign in as {label} ({phone}){OFF}\n     {error}")
            return 1
    print(f"{DIM}  six accounts in{OFF}\n")

    # ---------------------------------------------------------------- 1
    @walk("Sotuvchi tovar yaratadi va omborga topshiradi")
    def _():
        # The staff list is flat and names each parent, so a leaf is a row
        # with no children — which is what a product must be filed under.
        cats = api.ok("GET", "/staff/catalog/categories", who="seller")
        leaf = next((c["slug"] for c in cats
                     if not c.get("child_count") and c.get("parent_slug")), None)
        walk.expect("there is a leaf category to file a product under",
                    leaf is not None, cats[:2])
        state["category"] = leaf
        picture = api.upload_png("seller")
        walk.expect("the picture uploaded", bool(picture), picture)
        made = api.ok(
            "POST", "/staff/catalog/listings", who="seller",
            json_body={
                "title": "Oq futbolka",
                "subtitle": "Paxta, yengil",
                "description": "Sof paxta futbolka.",
                "category_slug": leaf,
                "price": 89000,
                "images": [picture],
                "colors": [{
                    "label": "Oq",
                    "value": "#FFFFFF",
                    "sizes": [
                        {"label": "S", "quantity": 10},
                        {"label": "M", "quantity": 15},
                        {"label": "L", "quantity": 5},
                    ],
                }],
            },
        )
        state["product"] = made["id"]
        state["supply_code"] = made.get("supply_code")
        walk.expect("submitting made one batch for the warehouse", bool(made.get("supply_code")), made)
        walk.expect("it is waiting for the warehouse, not for an admin",
                    made["stage"] == "awaiting_warehouse", made["stage"])
        return f"#{made['id']} · {made['supply_code']} · 30 dona"

    # ---------------------------------------------------------------- 2
    @walk("Sotuvchi ro'yxatda 'Kutilmoqda' holatida ko'radi, qoldiq yo'q")
    def _():
        rows = api.ok("GET", "/staff/catalog/listings", who="seller")
        mine = next((r for r in rows if r["id"] == state["product"]), None)
        walk.expect("the product is in the seller's own list", mine is not None, rows[:1])
        walk.expect("nothing is on a shelf yet", mine["on_hand_total"] == 0, mine["on_hand_total"])
        declared = sum(cell["declared"] for cell in mine["stock"])
        walk.expect("all thirty are recorded as handed in", declared == 30, declared)
        return f"topshirildi 30 · omborda 0"

    # ---------------------------------------------------------------- 3
    @walk("Xaridor hali topa olmaydi — tovar do'konda yo'q")
    def _():
        status, _ = api.call("GET", f"/products/{state['product']}")
        walk.expect("an uncounted product is a 404 for a shopper", status == 404, status)
        found = api.ok("GET", "/search", query={"q": "Oq futbolka"})
        hits = found.get("products") or found.get("items") or []
        walk.expect("and it is not in search either",
                    all(h.get("id") != state["product"] for h in hits), hits[:2])
        return "404, va qidiruvda yo'q"

    # ---------------------------------------------------------------- 4
    @walk("Ombor partiyani ko'radi va sanab qabul qiladi (L bittasi kam)")
    def _():
        batches = api.ok("GET", "/staff/supplies", who="warehouse", query={"status": "declared"})
        batch = next((b for b in batches if b["code"] == state["supply_code"]), None)
        walk.expect("the batch is in the warehouse's queue", batch is not None, batches[:1])
        state["supply"] = batch["id"]
        counted = []
        for line in batch["lines"]:
            short = line["variant_label"] and line["variant_label"].endswith("L")
            counted.append({
                "line_id": line["id"],
                "received_quantity": line["declared_quantity"] - (1 if short else 0),
            })
        got = api.ok(
            "POST", f"/staff/supplies/{batch['id']}/receive", who="warehouse",
            json_body={"lines": counted, "note": "Qadoq butun, L bittasi kam"},
        )
        walk.expect("the batch is received", got["status"] == "received", got["status"])
        return "qabul qilindi: 29 dona"

    # ---------------------------------------------------------------- 5
    @walk("Tovar sotuvga chiqdi — hech kim boshqa tasdiqlamadi")
    def _():
        row = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        walk.expect("receiving the goods is what put it on sale",
                    row["stage"] == "on_sale", row["stage"])
        walk.expect("the shelf holds what was counted, not what was promised",
                    row["on_hand_total"] == 29, row["on_hand_total"])
        return "on_sale · omborda 29"

    # ---------------------------------------------------------------- 6
    @walk("Xaridor ilovada topadi, ochadi, o'lchamlarni ko'radi")
    def _():
        page = api.ok("GET", f"/products/{state['product']}")
        walk.expect("the shopper can open it now", page["id"] == state["product"], page.get("id"))
        sizes = [v for v in (page.get("variants") or []) if v.get("kind") == "size"]
        walk.expect("all three sizes are on the page", len(sizes) == 3,
                    [v.get("label") for v in (page.get("variants") or [])])
        medium = next((v for v in sizes if v["label"] == "M"), sizes[0])
        state["variant"] = medium["id"]
        walk.expect("the size the customer wants is in stock", medium["in_stock"], medium)
        return f"3 o'lcham · narx {page.get('price')}"

    # ---------------------------------------------------------------- 7
    @walk("Xaridor bittasini sotib oladi")
    def _():
        api.ok("DELETE", "/cart", who="customer", expect=(200, 204))
        api.ok("POST", "/cart/items", who="customer",
               json_body={"product_id": state["product"], "variant_id": state["variant"],
                          "quantity": 1})
        points = api.ok("GET", "/delivery/pickup-points", who="customer")
        pts = points if isinstance(points, list) else points.get("items", [])
        walk.expect("there is somewhere to collect from", bool(pts), points)
        order = api.ok(
            "POST", "/orders", who="customer",
            # No delivery_method field: naming a pickup point *is* choosing
            # collection, and naming an address is choosing a courier.
            json_body={
                "pickup_point_id": pts[0]["id"],
                "payment_method": "cash",
                "recipient_name": "Muhammadsodiq",
                "recipient_phone": "+998901234567",
            },
        )
        state["order"] = order["id"]
        walk.expect("the order is placed", order["status"] == "placed", order["status"])
        return f"#{order.get('code') or order['id']}"

    # ---------------------------------------------------------------- 8
    @walk("Sotuvchi buyurtmani ko'radi, qoldiq bittaga kamaydi")
    def _():
        row = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        walk.expect("the sold one is no longer sellable",
                    row["sellable_total"] == 28, row["sellable_total"])
        orders = api.ok("GET", "/staff/orders", who="seller")
        rows = orders if isinstance(orders, list) else orders.get("items", [])
        walk.expect("the seller can see the order against their goods",
                    any(o["id"] == state["order"] for o in rows), rows[:1])
        return "sotuvga tayyor 28"

    # ---------------------------------------------------------------- 9
    @walk("Ombor yig'adi, operator kuryerga biriktiradi")
    def _():
        api.ok("POST", f"/staff/orders/{state['order']}/status", who="warehouse",
               json_body={"status": "packing"})
        couriers = api.ok("GET", "/staff/couriers", who="operator")
        rows = couriers if isinstance(couriers, list) else couriers.get("items", [])
        walk.expect("there is a courier to give it to", bool(rows), couriers)
        api.ok("POST", f"/staff/orders/{state['order']}/courier", who="operator",
               json_body={"courier_id": rows[0]["id"]})
        api.ok("POST", f"/staff/orders/{state['order']}/status", who="operator",
               json_body={"status": "shipped"})
        mine = api.ok("GET", "/courier/orders", who="courier")
        rows = mine if isinstance(mine, list) else mine.get("items", [])
        walk.expect("it is on the courier's round now",
                    any(o["id"] == state["order"] for o in rows), rows[:1])
        return "kuryerda"

    # ---------------------------------------------------------------- 10
    @walk("Kuryer yetkazadi")
    def _():
        body = {"recipient_name": "Muhammadsodiq", "cash_collected": 89000}
        out = api.ok("POST", f"/courier/orders/{state['order']}/deliver", who="courier",
                     json_body=body, key=f"walk-deliver-{state['order']}")
        walk.expect("the order is delivered", out["status"] == "delivered", out["status"])
        # The same key again is the thumb that pressed twice on a bad
        # connection. It must be the same answer, not a second delivery.
        again = api.ok("POST", f"/courier/orders/{state['order']}/deliver", who="courier",
                       json_body=body, key=f"walk-deliver-{state['order']}")
        walk.expect("pressing it twice delivers once",
                    again["status"] == "delivered", again["status"])
        return "yetkazildi · ikki marta bosilsa bir marta"

    # ---------------------------------------------------------------- 11
    @walk("Xaridor qaytaradi; ombor tekshiradi — buzilmagan")
    def _():
        reasons = api.ok("GET", "/orders/reasons/return", who="customer")
        rows = reasons if isinstance(reasons, list) else reasons.get("items", [])
        walk.expect("there are return reasons to pick from", bool(rows), reasons)
        order = api.ok("GET", f"/orders/{state['order']}", who="customer")
        items = order.get("items") or []
        walk.expect("the order has the line to send back", bool(items), order)
        made = api.ok(
            "POST", f"/orders/{state['order']}/return", who="customer",
            json_body={
                "order_item_id": items[0]["id"],
                "reason_id": rows[0]["id"],
                "comment": "O'lcham kichik keldi",
            },
        )
        state["return"] = made["id"]
        api.ok("POST", f"/staff/returns/{made['id']}/approve", who="operator", json_body={})

        # The goods come home. A run needs a courier named up front — the
        # collection is somebody's errand, not an open request.
        couriers = api.ok("GET", "/staff/couriers", who="operator")
        crows = couriers if isinstance(couriers, list) else couriers.get("items", [])
        run = api.ok("POST", "/staff/pickups", who="operator",
                     json_body={"courier_id": crows[0]["id"],
                                "return_request_ids": [made["id"]]})
        state["run"] = run["id"]
        api.ok("POST", f"/courier/pickups/{run['id']}/collect", who="courier",
               json_body={"lines": [{"return_request_id": made["id"], "collected": True}]},
               key=f"walk-collect-{run['id']}")
        api.ok("POST", f"/staff/pickups/{run['id']}/receive", who="warehouse", json_body={})
        got = api.ok("POST", f"/staff/returns/{made['id']}/inspect", who="warehouse",
                     json_body={"result": "ok", "note": "Yorliqlar joyida"})
        walk.expect("the warehouse's verdict is recorded",
                    got.get("inspection") == "ok", got.get("inspection"))
        return "omborda · buzilmagan"

    # ---------------------------------------------------------------- 12
    @walk("Sotuvchi qayta sotuvga chiqaradi, qoldiq tiklanadi")
    def _():
        pending = api.ok("GET", "/staff/returns", who="seller")
        rows = pending if isinstance(pending, list) else pending.get("items", [])
        mine = next((r for r in rows if r["id"] == state["return"]), None)
        walk.expect("the decision is waiting for the seller", mine is not None, rows[:1])
        out = api.ok("POST", f"/staff/returns/{state['return']}/decide", who="seller",
                     json_body={"decision": "relist"})
        walk.expect("the decision is recorded",
                    out.get("seller_decision") == "relist", out.get("seller_decision"))
        row = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        walk.expect("the returned one is back on the shelf",
                    row["on_hand_total"] == 29, row["on_hand_total"])
        walk.expect("and it can be sold again",
                    row["sellable_total"] == 29, row["sellable_total"])
        return "omborda 29 · sotuvga tayyor 29"

    # ------------------------------------------------------------ 13
    @walk("Ombor rad etadi — sotuvchi sababni ko'radi, do'konda paydo bo'lmaydi")
    def _():
        picture = api.upload_png("seller")
        made = api.ok(
            "POST", "/staff/catalog/listings", who="seller",
            json_body={
                "title": "Qora shim",
                "category_slug": state["category"],
                "price": 150000,
                "images": [picture],
                "colors": [{"label": "Qora", "value": "#000000",
                            "sizes": [{"label": "48", "quantity": 4}]}],
            },
        )
        batches = api.ok("GET", "/staff/supplies", who="warehouse", query={"status": "declared"})
        batch = next(b for b in batches if b["code"] == made["supply_code"])
        api.ok("POST", f"/staff/supplies/{batch['id']}/cancel", who="warehouse",
               json_body={"reason": "Rasm tovarga mos emas"})
        row = api.ok("GET", f"/staff/catalog/listings/{made['id']}", who="seller")
        walk.expect("a refused product is refused, not quietly waiting",
                    row["stage"] == "rejected", row["stage"])
        walk.expect("and the seller can read why",
                    bool(row["moderation_note"]), row["moderation_note"])
        status, _ = api.call("GET", f"/products/{made['id']}")
        walk.expect("a refused product never reaches the shop", status == 404, status)
        return f"rejected · \"{row['moderation_note'][:28]}…\""

    # ------------------------------------------------------------ 14
    @walk("Buzilgan qaytarish — sotuvchi qayta sotuvga chiqara olmaydi")
    def _():
        page = api.ok("GET", f"/products/{state['product']}")
        size = next(v for v in page["variants"] if v["kind"] == "size" and v["in_stock"])
        api.ok("DELETE", "/cart", who="customer", expect=(200, 204))
        api.ok("POST", "/cart/items", who="customer",
               json_body={"product_id": state["product"], "variant_id": size["id"],
                          "quantity": 1})
        points = api.ok("GET", "/delivery/pickup-points", who="customer")
        pts = points if isinstance(points, list) else points.get("items", [])
        order = api.ok("POST", "/orders", who="customer",
                       json_body={"pickup_point_id": pts[0]["id"], "payment_method": "cash",
                                  "recipient_name": "Muhammadsodiq",
                                  "recipient_phone": "+998901234567"})
        oid = order["id"]
        api.ok("POST", f"/staff/orders/{oid}/status", who="warehouse",
               json_body={"status": "packing"})
        couriers = api.ok("GET", "/staff/couriers", who="operator")
        crows = couriers if isinstance(couriers, list) else couriers.get("items", [])
        api.ok("POST", f"/staff/orders/{oid}/courier", who="operator",
               json_body={"courier_id": crows[0]["id"]})
        api.ok("POST", f"/staff/orders/{oid}/status", who="operator",
               json_body={"status": "shipped"})
        api.ok("POST", f"/courier/orders/{oid}/deliver", who="courier",
               json_body={"recipient_name": "Muhammadsodiq", "cash_collected": 89000},
               key=f"walk-deliver-damaged-{oid}")

        reasons = api.ok("GET", "/orders/reasons/return", who="customer")
        rrows = reasons if isinstance(reasons, list) else reasons.get("items", [])
        full = api.ok("GET", f"/orders/{oid}", who="customer")
        back = api.ok("POST", f"/orders/{oid}/return", who="customer",
                      json_body={"order_item_id": full["items"][0]["id"],
                                 "reason_id": rrows[0]["id"], "comment": "Yirilgan"})
        api.ok("POST", f"/staff/returns/{back['id']}/approve", who="operator", json_body={})
        run = api.ok("POST", "/staff/pickups", who="operator",
                     json_body={"courier_id": crows[0]["id"],
                                "return_request_ids": [back["id"]]})
        api.ok("POST", f"/courier/pickups/{run['id']}/collect", who="courier",
               json_body={"lines": [{"return_request_id": back["id"], "collected": True}]},
               key=f"walk-collect-damaged-{run['id']}")
        api.ok("POST", f"/staff/pickups/{run['id']}/receive", who="warehouse", json_body={})
        api.ok("POST", f"/staff/returns/{back['id']}/inspect", who="warehouse",
               json_body={"result": "damaged", "note": "Yon chok yirilgan"})

        before = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        status, body = api.call("POST", f"/staff/returns/{back['id']}/decide", who="seller",
                                json_body={"decision": "relist"})
        walk.expect("damaged goods cannot be put back on sale", status == 409, (status, body))
        after = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        walk.expect("and the refusal did not move the shelf",
                    after["on_hand_total"] == before["on_hand_total"],
                    (before["on_hand_total"], after["on_hand_total"]))
        return "409 · qoldiq o'zgarmadi"

    # ------------------------------------------------------------ 15
    @walk("Kuryer yetkaza olmadi — urinish yoziladi, buyurtma yo'lda qoladi")
    def _():
        page = api.ok("GET", f"/products/{state['product']}")
        size = next(v for v in page["variants"] if v["kind"] == "size" and v["in_stock"])
        api.ok("DELETE", "/cart", who="customer", expect=(200, 204))
        api.ok("POST", "/cart/items", who="customer",
               json_body={"product_id": state["product"], "variant_id": size["id"],
                          "quantity": 1})
        points = api.ok("GET", "/delivery/pickup-points", who="customer")
        pts = points if isinstance(points, list) else points.get("items", [])
        order = api.ok("POST", "/orders", who="customer",
                       json_body={"pickup_point_id": pts[0]["id"], "payment_method": "cash",
                                  "recipient_name": "Muhammadsodiq",
                                  "recipient_phone": "+998901234567"})
        oid = order["id"]
        api.ok("POST", f"/staff/orders/{oid}/status", who="warehouse",
               json_body={"status": "packing"})
        couriers = api.ok("GET", "/staff/couriers", who="operator")
        crows = couriers if isinstance(couriers, list) else couriers.get("items", [])
        api.ok("POST", f"/staff/orders/{oid}/courier", who="operator",
               json_body={"courier_id": crows[0]["id"]})
        api.ok("POST", f"/staff/orders/{oid}/status", who="operator",
               json_body={"status": "shipped"})
        out = api.ok("POST", f"/courier/orders/{oid}/failed", who="courier",
                     json_body={"reason": "Xaridor javob bermadi"},
                     key=f"walk-failed-{oid}")
        walk.expect("a knock at an empty door does not cancel the order",
                    out["status"] == "shipped", out["status"])
        seen = api.ok("GET", f"/staff/orders/{oid}", who="operator")
        walk.expect("the operator can see the attempt", seen.get("attempts"), seen.get("attempts"))
        # Only an operator gives up, and the counts come back when they do.
        api.ok("POST", f"/staff/orders/{oid}/status", who="operator",
               json_body={"status": "cancelled", "note": "Uch marta urinildi"})
        row = api.ok("GET", f"/staff/catalog/listings/{state['product']}", who="seller")
        walk.expect("cancelling put the goods back on the shelf",
                    row["sellable_total"] == row["on_hand_total"],
                    (row["sellable_total"], row["on_hand_total"]))
        return "urinish yozildi · bekor qilinganda qoldiq qaytdi"

    print()
    if walk.failures:
        print(f"{RED}{BOLD}{len(walk.failures)} of {walk.step} steps failed{OFF}\n")
        for head, why in walk.failures:
            print(f"{RED}  {head}{OFF}\n     {why}\n")
        return 1
    print(f"{GREEN}{BOLD}All {walk.step} steps passed — the flow works end to end.{OFF}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
