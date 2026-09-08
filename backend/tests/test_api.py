"""End-to-end coverage of the flows the 47 screens depend on."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import audit
from app import offers as of
from app import schemas as s
from app import stock as st
from app.core.config import settings
from app.db import engine
from app.deps import AdminUser
from app.models import (
    AuditLog,
    Brand,
    CartItem,
    Category,
    DeliveryAttempt,
    DeliverySlot,
    Notification,
    Offer,
    OfferVariant,
    Order,
    OrderItem,
    Product,
    ProductStatus,
    ProductVariant,
    ReturnRequest,
    Seller,
    SellerStatement,
    StockMovement,
    StockMovementKind,
    User,
    UserRole,
    VariantKind,
    utcnow,
)
from app.seed import ADMIN_PHONE

from tests.conftest import COURIER_PHONE

API = "/api/v1"



def _courier_headers(client: TestClient) -> dict[str, str]:
    """The suite's own courier, signed in the ordinary way.

    Signed in here rather than taken as a fixture so that the eight setup
    paths below did not each have to grow a parameter to reach one.
    """
    asked = client.post(f"{API}/auth/otp/request", json={"phone": COURIER_PHONE}).json()
    tokens = client.post(
        f"{API}/auth/otp/verify", json={"phone": COURIER_PHONE, "code": asked["dev_code"]}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _to_the_door(
    client: TestClient,
    staff_headers: dict[str, str],
    order_id: int,
    *,
    delivered: bool = True,
) -> dict[str, str]:
    """Packed by the bench, taken off the board by a courier, delivered.

    ``shipped`` is not a move staff can make. The handover is the courier
    picking the parcel up — ``POST /courier/orders/{id}/take`` — so every path
    to a delivered order goes through a courier choosing it, which is the
    road a person walks. Returns the courier's headers, for the tests that
    then want to knock at the door as them.
    """
    packed = client.post(
        f"{API}/staff/orders/{order_id}/status",
        json={"status": "packing"},
        headers=staff_headers,
    )
    assert packed.status_code == 200, packed.text

    courier = _courier_headers(client)
    took = client.post(
        f"{API}/courier/orders/{order_id}/take",
        headers={**courier, "Idempotency-Key": f"test-take-{order_id}"},
    )
    assert took.status_code == 200, took.text
    assert took.json()["status"] == "shipped", took.text

    if delivered:
        done = client.post(
            f"{API}/staff/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=staff_headers,
        )
        assert done.status_code == 200, done.text
    return courier



def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


# --------------------------------------------------------------------------- 01-06


def test_phone_login_creates_a_user(client: TestClient) -> None:
    phone = "+998995554433"
    requested = client.post(f"{API}/auth/otp/request", json={"phone": phone})
    assert requested.status_code == 200
    code = requested.json()["dev_code"]

    verified = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})
    assert verified.status_code == 200
    body = verified.json()
    assert body["is_new_user"] is True
    assert body["access_token"] and body["refresh_token"]


def test_wrong_otp_is_rejected(client: TestClient) -> None:
    phone = "+998991112200"
    client.post(f"{API}/auth/otp/request", json={"phone": phone})
    bad = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": "999999"})
    assert bad.status_code == 400


def test_refresh_token_rotates(client: TestClient) -> None:
    phone = "+998997778899"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code}).json()

    refreshed = client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refreshed.status_code == 200

    replayed = client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert replayed.status_code == 401, "a refresh token must be single use"


def test_protected_route_needs_a_token(client: TestClient) -> None:
    assert client.get(f"{API}/cart").status_code == 401


# --------------------------------------------------------------------------- 07-16


def test_home_is_one_request(client: TestClient) -> None:
    body = client.get(f"{API}/home").json()
    assert body["city"] == "Toshkent"
    assert len(body["banners"]) >= 1
    assert len(body["categories"]) == 10, "the home grid is a 5x2 tile grid"
    keys = [s["key"] for s in body["sections"]]
    assert keys == ["deals", "for-you", "shoes", "electronics"]
    assert all(s["products"] for s in body["sections"])


def test_catalog_tree(client: TestClient) -> None:
    roots = client.get(f"{API}/categories").json()
    clothing = next(c for c in roots if c["slug"] == "kiyim-poyabzal")
    assert clothing["has_children"] is True

    children = client.get(f"{API}/categories", params={"parent": "kiyim-poyabzal"}).json()
    assert {c["slug"] for c in children} >= {"krossovkalar", "futbolka-toplar"}


def test_listing_filters_and_sorts(client: TestClient) -> None:
    cheap_first = client.get(
        f"{API}/products", params={"category": "kiyim-poyabzal", "sort": "price_asc"}
    ).json()
    prices = [p["price"] for p in cheap_first["items"]]
    assert prices == sorted(prices)

    nike = client.get(f"{API}/products", params={"brand": "nike"}).json()
    assert nike["total"] >= 3

    discounted = client.get(f"{API}/products", params={"discounted": True}).json()
    assert all(p["discount_percent"] for p in discounted["items"])


def test_filter_sheet(client: TestClient) -> None:
    body = client.get(f"{API}/products/filters", params={"category": "kiyim-poyabzal"}).json()
    assert body["price_min"] <= body["price_max"]
    assert body["brands"][0]["product_count"] >= body["brands"][-1]["product_count"]
    assert "42" in body["sizes"]
    assert {f["key"] for f in body["flags"]} == {
        "next_day_delivery", "free_delivery", "discounted", "is_original"
    }


def test_search(client: TestClient) -> None:
    landing = client.get(f"{API}/search").json()
    assert "iPhone 15" in landing["popular"]

    hits = client.get(f"{API}/search/suggest", params={"q": "gazelle"}).json()
    assert hits and "Gazelle" in hits[0]["title"]


def test_product_detail(client: TestClient) -> None:
    listing = client.get(f"{API}/products", params={"q": "Gazelle"}).json()
    product_id = listing["items"][0]["id"]

    product = client.get(f"{API}/products/{product_id}").json()
    assert product["images"]
    assert {v["label"] for v in product["variants"]} >= {"42", "Ko'k"}
    assert product["specs"][0]["key"] == "Material"
    assert product["delivery_note"]

    # The review endpoints went with the panels rebuild — the whole system did,
    # and it comes back with a screen of its own. The rating is still on the
    # card because the app's page renders it, and it is now a seeded figure
    # rather than a computed one.
    assert product["rating"] >= 0


# --------------------------------------------------------------------------- 17-24


def test_cart_lifecycle(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)

    product = client.get(f"{API}/products", params={"q": "futbolka"}).json()["items"][0]
    added = client.post(
        f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth
    )
    assert added.status_code == 201
    cart = added.json()
    assert cart["totals"]["items_count"] == 2

    item_id = cart["items"][0]["id"]
    bumped = client.patch(
        f"{API}/cart/items/{item_id}", json={"quantity": 3}, headers=auth
    ).json()
    assert bumped["items"][0]["quantity"] == 3
    assert bumped["totals"]["subtotal"] == product["price"] * 3

    emptied = client.patch(
        f"{API}/cart/items/{item_id}", json={"quantity": 0}, headers=auth
    ).json()
    assert emptied["items"] == []


def test_free_delivery_threshold(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    cheap = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]

    cart = client.post(
        f"{API}/cart/items", json=_pick(cheap["id"], 1), headers=auth
    ).json()
    assert cart["totals"]["delivery_fee"] > 0

    expensive = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    cart = client.post(
        f"{API}/cart/items", json=_pick(expensive["id"], 1), headers=auth
    ).json()
    assert cart["totals"]["subtotal"] >= cart["totals"]["free_delivery_threshold"]
    assert cart["totals"]["delivery_fee"] == 0


def test_a_free_slot_does_not_make_delivery_free(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A slot's price is a surcharge, not the whole fee.

    Picking a daytime slot, which costs nothing extra, used to replace the
    standard fee with that nothing — so a small order shipped free and the
    confirm screen showed no delivery line at all.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    cart = client.get(f"{API}/cart", headers=auth).json()
    base = cart["totals"]["delivery_fee"]
    assert base > 0, "a cheap order should not already qualify for free delivery"

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", headers=auth).json()
    free = next(
        s for day in days for s in day["slots"] if s["price"] == 0 and s["available"]
    )

    totals = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": free["id"]},
        headers=auth,
    ).json()["totals"]

    assert totals["delivery_fee"] == base
    assert totals["total"] == totals["subtotal"] - totals["discount"] + base


def test_a_paid_slot_adds_to_the_standard_fee(
    client: TestClient, auth: dict[str, str]
) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    base = client.get(f"{API}/cart", headers=auth).json()["totals"]["delivery_fee"]
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", headers=auth).json()
    paid = next(s for day in days for s in day["slots"] if s["price"] > 0 and s["available"])

    totals = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": paid["id"]},
        headers=auth,
    ).json()["totals"]

    assert totals["delivery_fee"] == base + paid["price"]


def test_checkout_places_an_order(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    slot = client.get(f"{API}/delivery/slots", headers=auth).json()[1]["slots"][0]
    card = client.get(f"{API}/payment-cards", headers=auth).json()[0]

    preview = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": slot["id"], "payment_card_id": card["id"]},
        headers=auth,
    ).json()
    assert preview["address"]["id"] == address["id"]
    assert preview["totals"]["total"] > 0

    created = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"], "payment_card_id": card["id"]},
        headers=auth,
    )
    assert created.status_code == 201
    order = created.json()
    assert order["code"].startswith("#A-")
    assert order["status"] == "placed"
    assert len(order["events"]) == 4
    assert order["events"][0]["done"] is True
    assert order["events"][-1]["done"] is False

    assert client.get(f"{API}/cart", headers=auth).json()["items"] == []


def _pick(product_id: int, quantity: int = 1, *, colour_id: int | None = None) -> dict:
    """The body for POST /cart/items, naming a leaf.

    A product with variants will not go into a basket without one: a sale that
    names no colour takes the count off the offer's total and off no colour at
    all, and there is no working out afterwards which one it was. So the tests
    choose the same way the apps do — the leaf with the most of it left, so
    that "add N" has somewhere to come from.
    """
    body: dict = {"product_id": product_id, "quantity": quantity}
    with Session(engine) as session:
        leaves = of.leaf_variants(session, product_id)
        if not leaves:
            return body
        pool = [
            leaf for leaf in leaves if colour_id is None or leaf.parent_id == colour_id
        ] or leaves
        offer = of.winning_offer(session, product_id)
        chosen = max(
            pool,
            key=lambda leaf: st.sellable(session, offer, leaf.id) if offer else 0,
        )
        if chosen.kind is VariantKind.SIZE:
            body["variant_id"] = chosen.id
            if chosen.parent_id is not None:
                body["color_variant_id"] = chosen.parent_id
        else:
            body["color_variant_id"] = chosen.id
    return body


def _variantless_product(client: TestClient) -> dict:
    """A product counted once, for the tests that talk about a whole shelf.

    A product with colours has its shelf counted per colour, so emptying it
    means buying every cell of the grid. These tests are about the product's
    own figure, so they take one that has no cells.
    """
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
    with Session(engine) as session:
        return next(
            item
            for item in listing
            if item["in_stock"] and not of.leaf_variants(session, item["id"])
        )


def test_the_basket_cannot_hold_more_than_the_shelf(
    client: TestClient, auth: dict[str, str]
) -> None:
    """The only ceiling was ninety-nine, which is not a ceiling: the basket
    would hold thirty of something there were three of, and the shortfall
    surfaced at checkout or not at all."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    added = client.post(
        f"{API}/cart/items",
        json=_pick(product["id"], left + 10),
        headers=auth,
    ).json()
    item = added["items"][0]
    assert item["quantity"] == left
    # And the stepper is handed the same figure to stop its own plus button.
    assert item["stock_left"] == left

    # The stepper itself cannot push past it either.
    patched = client.patch(
        f"{API}/cart/items/{item['id']}",
        json={"quantity": left + 5},
        headers=auth,
    ).json()
    assert patched["items"][0]["quantity"] == left


def test_buying_takes_the_item_off_the_shelf(client: TestClient, auth: dict[str, str]) -> None:
    """The sold count was being raised on every order and the stock beside it
    was not, so a product could be bought any number of times and still claim
    the same 25 remaining."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    before = client.get(f"{API}/products/{product['id']}").json()
    quantity = 3

    client.post(f"{API}/cart/items", json=_pick(product["id"], quantity), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(f"{API}/orders", json={"address_id": address["id"]}, headers=auth)
    assert created.status_code == 201

    after = client.get(f"{API}/products/{product['id']}").json()
    assert after["stock_left"] == before["stock_left"] - quantity
    assert after["sold_count"] == before["sold_count"] + quantity
    # And the card carries it too, so a tile can say when there are few.
    card = next(
        item
        for item in client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
        if item["id"] == product["id"]
    )
    assert card["stock_left"] == after["stock_left"]


def test_the_last_one_sold_goes_out_of_stock(client: TestClient, auth: dict[str, str]) -> None:
    """Nothing was setting in_stock, so a product could sit at zero remaining
    and still offer a basket button on every tile in the catalogue."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    client.post(f"{API}/cart/items", json=_pick(product["id"], left), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    placed = client.post(f"{API}/orders", json={"address_id": address["id"]}, headers=auth)
    assert placed.status_code == 201

    sold_out = client.get(f"{API}/products/{product['id']}").json()
    assert sold_out["stock_left"] == 0
    assert sold_out["in_stock"] is False
    # And it cannot be put back in the basket.
    rejected = client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    assert rejected.status_code == 409


def test_a_variant_is_counted_apart_from_the_shelf(client: TestClient) -> None:
    """The page shows one colour in one size at a time and used to answer "how
    many" with the sum of all of them — so a shirt with two left in black
    claimed twenty-five while the picture on screen was of the black one."""
    product = client.get(f"{API}/products/1").json()
    colors = [v for v in product["variants"] if v["kind"] == "color"]
    sizes = [v for v in product["variants"] if v["kind"] == "size"]
    assert len(colors) > 1 and len(sizes) > 1, "seeded with colours and sizes"

    # Two views of one shelf rather than a grid: each kind carries its own
    # counts, and each kind's counts add back up to the product's total.
    for kind in (colors, sizes):
        assert all(v["stock_left"] is not None for v in kind)
        assert sum(v["stock_left"] for v in kind) == product["stock_left"]

    # A variant counted down to nothing says so, rather than only counting zero.
    assert all(v["in_stock"] == (v["stock_left"] > 0) for v in colors + sizes)


def test_buying_a_colour_takes_it_off_that_colour(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Only the product's own count was coming down, so a colour could be
    bought out and go on offering itself at the top of the page."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/1").json()
    colors = [v for v in product["variants"] if v["kind"] == "color"]
    chosen, other = colors[0], colors[1]
    quantity = 2

    added = client.post(
        f"{API}/cart/items",
        json=_pick(product["id"], quantity, colour_id=chosen["id"]),
        headers=auth,
    ).json()
    # The stepper's ceiling is the chosen cell of the grid, not the product's
    # whole shelf — and that cell belongs to the colour under test.
    assert added["items"][0]["color_variant_id"] == chosen["id"]
    assert 0 < added["items"][0]["stock_left"] <= chosen["stock_left"]

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    assert client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).status_code == 201

    after = client.get(f"{API}/products/{product['id']}").json()
    after_colors = {v["id"]: v for v in after["variants"] if v["kind"] == "color"}
    assert after_colors[chosen["id"]]["stock_left"] == chosen["stock_left"] - quantity
    # The colour nobody bought is untouched.
    assert after_colors[other["id"]]["stock_left"] == other["stock_left"]
    assert after["stock_left"] == product["stock_left"] - quantity


def test_the_listing_leaves_out_what_cannot_be_bought(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A sold-out product sat in the grid behind its veil, taking a slot in
    every listing from the products that could actually be sold."""
    listed = client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
    assert listed, "the shop is not empty"
    assert all(item["in_stock"] for item in listed)

    # The filter sheet can put them back for anyone who wants to see them.
    with_sold_out = client.get(
        f"{API}/products", params={"page_size": 60, "show_sold_out": True}
    ).json()["items"]
    assert len(with_sold_out) > len(listed)
    assert any(not item["in_stock"] for item in with_sold_out)


# --------------------------------------------------------------------------- 25-29


def test_order_list_and_cancel(client: TestClient, auth: dict[str, str]) -> None:
    active = client.get(f"{API}/orders", params={"active": True}, headers=auth).json()
    assert active["total"] >= 2
    assert all(o["can_track"] for o in active["items"])

    reasons = client.get(f"{API}/orders/reasons/cancel").json()
    assert len(reasons) == 5

    cancellable = next(o for o in active["items"] if o["can_cancel"])
    cancelled = client.post(
        f"{API}/orders/{cancellable['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    ).json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["status_label"] == "BEKOR QILINDI"

    again = client.post(
        f"{API}/orders/{cancellable['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    )
    assert again.status_code == 409


def test_return_request(client: TestClient, auth: dict[str, str]) -> None:
    finished = client.get(f"{API}/orders", params={"active": False}, headers=auth).json()
    delivered = next(o for o in finished["items"] if o["status"] == "delivered")
    reasons = client.get(f"{API}/orders/reasons/return").json()

    created = client.post(
        f"{API}/orders/{delivered['id']}/return",
        json={"reason_id": reasons[0]["id"], "comment": "O'lcham kichik keldi"},
        headers=auth,
    )
    assert created.status_code == 201
    assert created.json()["status"] == "submitted"
    assert client.get(f"{API}/returns", headers=auth).json()


# --------------------------------------------------------------------------- 30-40


def test_profile_overview(client: TestClient, auth: dict[str, str]) -> None:
    body = client.get(f"{API}/me/overview", headers=auth).json()
    assert body["user"]["full_name"] == "Aziz Toshmatov"
    assert body["user"]["has_pin"] is True
    assert body["addresses_count"] == 2
    assert body["cards_count"] == 2
    assert body["unread_notifications"] >= 1


def test_favorites(client: TestClient, auth: dict[str, str]) -> None:
    favorites = client.get(f"{API}/favorites", headers=auth).json()
    assert favorites["total"] == 4
    assert all(p["is_favorite"] for p in favorites["items"])

    product_id = favorites["items"][0]["id"]
    client.delete(f"{API}/favorites/{product_id}", headers=auth)
    assert client.get(f"{API}/favorites", headers=auth).json()["total"] == 3

    client.put(f"{API}/favorites/{product_id}", headers=auth)
    assert client.get(f"{API}/favorites", headers=auth).json()["total"] == 4


def test_addresses_keep_a_single_default(client: TestClient, auth: dict[str, str]) -> None:
    created = client.post(
        f"{API}/addresses",
        json={"title": "Dala hovli", "line": "Toshkent viloyati, Zangiota", "is_default": True},
        headers=auth,
    )
    assert created.status_code == 201
    rows = client.get(f"{API}/addresses", headers=auth).json()
    assert sum(1 for a in rows if a["is_default"]) == 1
    client.delete(f"{API}/addresses/{created.json()['id']}", headers=auth)


def test_cards_never_expose_a_pan(client: TestClient, auth: dict[str, str]) -> None:
    cards = client.get(f"{API}/payment-cards", headers=auth).json()
    assert {c["last4"] for c in cards} == {"4417", "3390"}
    assert all("processor_token" not in c for c in cards)

    expired = next(c for c in cards if c["status"] == "expired")
    rejected = client.post(f"{API}/payment-cards/{expired['id']}/default", headers=auth)
    assert rejected.status_code == 409


def test_notifications_are_grouped(client: TestClient, auth: dict[str, str]) -> None:
    groups = client.get(f"{API}/notifications", headers=auth).json()
    assert [g["label"] for g in groups][0] == "Bugun"

    before = client.get(f"{API}/notifications/unread-count", headers=auth).json()["count"]
    assert before > 0
    client.post(f"{API}/notifications/read", headers=auth)
    assert client.get(f"{API}/notifications/unread-count", headers=auth).json()["count"] == 0


def test_settings_and_prefs(client: TestClient, auth: dict[str, str]) -> None:
    updated = client.put(
        f"{API}/me/settings", json={"language": "ru", "night_mode": True}, headers=auth
    ).json()
    assert updated["language"] == "ru" and updated["night_mode"] is True
    client.put(f"{API}/me/settings", json={"language": "uz", "night_mode": False}, headers=auth)

    prefs = client.put(
        f"{API}/me/notification-prefs", json={"promotions": False}, headers=auth
    ).json()
    assert prefs["promotions"] is False and prefs["order_status"] is True


def test_pin_change(client: TestClient, auth: dict[str, str]) -> None:
    wrong = client.post(
        f"{API}/auth/pin", json={"current_pin": "0000", "new_pin": "5678"}, headers=auth
    )
    assert wrong.status_code == 400

    ok = client.post(
        f"{API}/auth/pin", json={"current_pin": "1234", "new_pin": "5678"}, headers=auth
    )
    assert ok.status_code == 200
    verified = client.post(f"{API}/auth/pin/verify", json={"pin": "5678"}, headers=auth)
    assert verified.status_code == 200
    client.post(f"{API}/auth/pin", json={"current_pin": "5678", "new_pin": "1234"}, headers=auth)


# --------------------------------------------------------------------------- 45-47


def test_content_screens(client: TestClient) -> None:
    assert len(client.get(f"{API}/help/faq").json()) == 5
    assert client.get(f"{API}/help/support").json()["phone"] == "1150"
    docs = client.get(f"{API}/legal").json()
    assert len(docs) == 4
    assert client.get(f"{API}/legal/{docs[0]['slug']}").json()["body"]
    assert [x["code"] for x in client.get(f"{API}/languages").json()] == ["uz", "ru", "en"]


def test_logout_revokes_refresh_tokens(client: TestClient) -> None:
    phone = "+998933332211"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code}).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    ).status_code == 401


# --------------------------------------------------------------------------- languages


def test_categories_follow_accept_language(client: TestClient) -> None:
    def first_name(lang: str | None) -> str:
        headers = {"Accept-Language": lang} if lang else {}
        return client.get(f"{API}/categories", headers=headers).json()[0]["name"]

    assert first_name(None) == "Elektronika"          # no header: the default
    assert first_name("uz") == "Elektronika"
    assert first_name("ru") == "Электроника"
    assert first_name("en") == "Electronics"


def test_unknown_language_falls_back_to_uzbek(client: TestClient) -> None:
    body = client.get(f"{API}/categories", headers={"Accept-Language": "de"}).json()
    assert body[0]["name"] == "Elektronika"


def test_quality_values_are_honoured(client: TestClient) -> None:
    headers = {"Accept-Language": "de;q=1.0, ru;q=0.9, en;q=0.8"}
    body = client.get(f"{API}/categories", headers=headers).json()
    assert body[0]["name"] == "Электроника"


def test_untranslated_rows_keep_their_uzbek(client: TestClient) -> None:
    """A missing translation degrades to Uzbek rather than to a blank."""
    uz = client.get(f"{API}/products/1", headers={"Accept-Language": "uz"}).json()
    ru = client.get(f"{API}/products/1", headers={"Accept-Language": "ru"}).json()

    # Brands have no translations and must survive the lookup untouched.
    assert ru["brand"]["name"] == uz["brand"]["name"]
    # Everything that is translated came back filled in, not blank.
    assert ru["subtitle"] and ru["description"] and ru["title"]
    assert ru["subtitle"] != uz["subtitle"]


def test_error_details_are_translated(client: TestClient) -> None:
    missing = f"{API}/products/999999"
    assert client.get(missing, headers={"Accept-Language": "ru"}).json()["detail"] == (
        "Товар не найден"
    )
    assert client.get(missing, headers={"Accept-Language": "en"}).json()["detail"] == (
        "Product not found"
    )


def test_response_advertises_its_language(client: TestClient) -> None:
    response = client.get(f"{API}/categories", headers={"Accept-Language": "ru"})
    assert response.headers["Content-Language"] == "ru"
    # Without this a cache could hand a Russian body to an English client.
    assert response.headers["Vary"] == "Accept-Language"


# --------------------------------------------------------------------------- roles


def test_a_staff_endpoint_refuses_an_anonymous_caller(client: TestClient) -> None:
    assert client.get(f"{API}/staff/me").status_code == 401


def test_a_customer_cannot_reach_a_staff_endpoint(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A signed-in customer is still not staff — 403, not 401.

    The two must stay apart: the app retries a 401 by refreshing its token,
    and a customer refreshing forever would never learn why.
    """
    assert client.get(f"{API}/staff/me", headers=auth).status_code == 403


def test_an_admin_reaches_a_staff_endpoint(
    client: TestClient, admin: dict[str, str]
) -> None:
    response = client.get(f"{API}/staff/me", headers=admin)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_every_staff_role_is_staff(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    roles = (UserRole.OPERATOR, UserRole.WAREHOUSE, UserRole.COURIER, UserRole.SELLER)
    for index, role in enumerate(roles):
        headers = staff(role, f"+99890000201{index}")
        response = client.get(f"{API}/staff/me", headers=headers)
        assert response.status_code == 200, role
        assert response.json()["role"] == role.value


def test_require_role_admits_one_role_and_not_the_others(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """``AdminUser`` is stricter than ``StaffUser``, which is the point of
    naming roles at all: an operator works here, but not on this.

    Mounted on a throwaway app rather than a real endpoint — the backoffice
    has no admin-only route to guard yet, and the guard is what is under test.
    """
    probe = FastAPI()

    @probe.get("/admin-only")
    def admin_only(user: AdminUser) -> dict[str, str]:
        return {"role": user.role.value}

    operator = staff(UserRole.OPERATOR, "+998900002020")
    with TestClient(probe) as c:
        assert c.get("/admin-only", headers=admin).json() == {"role": "admin"}
        assert c.get("/admin-only", headers=operator).status_code == 403
        assert c.get("/admin-only").status_code == 401


def test_a_new_account_is_a_customer(client: TestClient) -> None:
    phone = "+998900003030"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})

    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone == phone)).one()
    assert user.role is UserRole.CUSTOMER


def test_the_role_stays_out_of_the_apps_profile(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The apps are shipped and read this shape — the role must not leak into
    it, however the account is flagged on our side."""
    body = client.get(f"{API}/me", headers=admin).json()
    assert "role" not in body
    assert body["phone"] and "has_pin" in body


# --------------------------------------------------------------------------- audit


def test_the_audit_log_records_both_sides_of_a_change() -> None:
    with Session(engine) as session:
        actor = session.exec(select(User).where(User.role == UserRole.ADMIN)).one()
        row = audit.record(
            session,
            actor=actor,
            action="product.price",
            entity="product",
            entity_id=1,
            field="price",
            old=1_090_000,
            new=990_000,
            note="hafta oxiri chegirmasi",
        )
        session.commit()
        session.refresh(row)

        assert row.actor_id == actor.id
        assert row.actor_role is UserRole.ADMIN
        assert (row.old_value, row.new_value) == ("1090000", "990000")
        assert row.created_at is not None


def test_the_audit_log_keeps_an_absent_value_absent() -> None:
    """"There was no value" and "the value was the word None" are different
    claims about the past, and only one of them is true."""
    with Session(engine) as session:
        row = audit.record(
            session,
            action="order.cancel_reason",
            entity="order",
            entity_id=1,
            field="cancel_reason",
            old=None,
            new="Mijoz bekor qildi",
        )
        session.commit()
        session.refresh(row)

    assert row.old_value is None
    assert row.new_value == "Mijoz bekor qildi"
    # No actor at all: a webhook or a scheduled job, not a person.
    assert row.actor_id is None and row.actor_role is None


# --------------------------------------------------------------------------- 401 / 403


def test_a_401_speaks_the_apps_language(client: TestClient) -> None:
    expected = {
        "uz": "Avtorizatsiya talab qilinadi",
        "ru": "Требуется авторизация",
        "en": "You need to sign in",
    }
    for lang, detail in expected.items():
        response = client.get(f"{API}/cart", headers={"Accept-Language": lang})
        assert response.status_code == 401
        assert response.json()["detail"] == detail, lang


def test_a_403_speaks_the_apps_language(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.get(
        f"{API}/staff/me", headers={**auth, "Accept-Language": "en"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have permission for this"


# --------------------------------------------------------------------------- operator


def _place_an_order(client: TestClient, auth: dict[str, str]) -> dict:
    """An order of this customer's own, in ``placed``, to push around."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert created.status_code == 201, created.text
    return created.json()


def _audit_rows(action: str, entity_id: int) -> list[AuditLog]:
    with Session(engine) as session:
        return session.exec(
            select(AuditLog).where(
                AuditLog.action == action, AuditLog.entity_id == entity_id
            )
        ).all()


# ------------------------------------------------------------------ order status


def test_an_order_walks_its_flow_and_will_not_walk_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"

    # Skipping a step is not a step.
    assert client.post(url, json={"status": "delivered"}, headers=operator).status_code == 409

    # The bench packs it and the bench stops there: shipping is the courier
    # taking the parcel off the shelf, and staff asking for it is refused.
    for target in ("packing",):
        moved = client.post(url, json={"status": target}, headers=operator)
        assert moved.status_code == 200, (target, moved.text)
        assert moved.json()["status"] == target

    refused = client.post(url, json={"status": "shipped"}, headers=operator)
    assert refused.status_code == 409, refused.text
    assert "kuryer" in refused.json()["detail"].lower()

    courier = _courier_headers(client)
    took = client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**courier, "Idempotency-Key": f"queue-take-{order['id']}"},
    )
    assert took.status_code == 200, took.text
    assert took.json()["status"] == "shipped"

    moved = client.post(url, json={"status": "delivered"}, headers=operator)
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "delivered"

    # The one the brief names: a delivered order does not go back to packing.
    back = client.post(url, json={"status": "packing"}, headers=operator)
    assert back.status_code == 409
    assert "delivered" in back.json()["detail"]

    # Delivered has exactly one way on: a return.
    returned = client.post(url, json={"status": "returned"}, headers=operator)
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    # And that really is the end of it.
    assert client.post(url, json={"status": "delivered"}, headers=operator).status_code == 409


def test_the_queue_says_what_an_order_may_become_next(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The backoffice draws its buttons from this rather than keeping its own
    copy of the rules."""
    order = _place_an_order(client, auth)
    queue = client.get(
        f"{API}/staff/orders", params={"status": "placed", "page_size": 100}, headers=operator
    ).json()
    row = next(r for r in queue["items"] if r["id"] == order["id"])
    assert row["next_statuses"] == ["packing", "cancelled"]
    assert row["customer_phone"] and row["code"] == order["code"]


def test_moving_an_order_writes_the_timeline_the_app_draws(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing", "note": "3-qatordan yig'ildi"},
        headers=operator,
    )

    # Read it back the way the customer's app does.
    events = client.get(f"{API}/orders/{order['id']}", headers=auth).json()["events"]
    by_status = {e["status"]: e for e in events}
    assert by_status["placed"]["done"] is True
    assert by_status["packing"]["done"] is True
    assert by_status["packing"]["happened_at"] is not None
    assert by_status["packing"]["note"] == "3-qatordan yig'ildi"
    assert by_status["shipped"]["done"] is False
    assert by_status["delivered"]["done"] is False


def test_a_cancelled_order_is_not_drawn_as_a_delivered_one(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Cancelled is not a step on the way to delivery, and the timeline used
    to say it was: the status fell outside the flow, so every step of it came
    back done and the app drew a cancelled order as arrived."""
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "Mijoz telefonda bekor qildi"},
        headers=operator,
    )

    events = client.get(f"{API}/orders/{order['id']}", headers=auth).json()["events"]
    by_status = {e["status"]: e for e in events}
    assert by_status["placed"]["done"] is True
    assert by_status["delivered"]["done"] is False
    # And the timeline ends where the order actually ended, in words.
    assert by_status["cancelled"]["done"] is True
    assert by_status["cancelled"]["title"] == "Bekor qilindi"


def test_moving_an_order_tells_the_customer_and_the_audit_log(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing", "note": "smena-2"},
        headers=operator,
    )

    groups = client.get(f"{API}/notifications", headers=auth).json()
    titles = [n["title"] for g in groups for n in g["items"]]
    assert "Yig'ildi — kuryer kutilmoqda" in titles

    rows = _audit_rows("order.status", order["id"])
    assert len(rows) == 1
    assert (rows[0].old_value, rows[0].new_value) == ("placed", "packing")
    assert rows[0].actor_role is UserRole.OPERATOR
    assert rows[0].note == "smena-2"


def test_only_staff_may_move_an_order(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"
    body = {"status": "packing"}

    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers=auth).status_code == 403
    assert client.post(url, json=body, headers=operator).status_code == 200


# ------------------------------------------------------------------ returns


def _submit_a_return(client: TestClient, auth: dict[str, str]) -> dict:
    finished = client.get(f"{API}/orders", params={"active": False}, headers=auth).json()
    delivered = next(o for o in finished["items"] if o["status"] == "delivered")
    created = client.post(
        f"{API}/orders/{delivered['id']}/return",
        json={"reason": "O'lcham kichik keldi", "comment": "Qadoq butun"},
        headers=auth,
    )
    assert created.status_code == 201
    return created.json()


def test_a_return_is_approved_and_then_paid_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    # Where the goods went is not a question with a default answer.
    assert client.post(f"{base}/refund", json={}, headers=operator).status_code == 422

    # The money cannot move before the decision does.
    early = client.post(f"{base}/refund", json={"restock": False}, headers=operator)
    assert early.status_code == 409

    approved = client.post(f"{base}/approve", json={"note": "TKT-4417"}, headers=operator)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["next_statuses"] == ["refunded"]

    # Approving twice is not approving harder.
    assert client.post(f"{base}/approve", json={}, headers=operator).status_code == 409
    # Nor is refusing something already accepted.
    assert client.post(
        f"{base}/reject", json={"reason": "Kech"}, headers=operator
    ).status_code == 409

    refunded = client.post(
        f"{base}/refund", json={"note": "Humo", "restock": True}, headers=operator
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"
    assert refunded.json()["next_statuses"] == []

    # Three status moves, all logged against the request.
    moves = _audit_rows("return.status", request["id"])
    assert [(r.old_value, r.new_value) for r in moves] == [
        ("submitted", "approved"),
        ("approved", "refunded"),
    ]

    # How much was paid back is its own row, against the order: it is the
    # figure anyone would later dispute, and a status change does not carry it.
    order_id = approved.json()["order_id"]
    money = _audit_rows("return.refund", order_id)
    assert len(money) == 1
    assert money[0].field == "refund" and int(money[0].new_value) > 0
    assert money[0].actor_role is UserRole.OPERATOR


def test_a_refusal_needs_a_reason_and_the_customer_gets_it(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    assert client.post(f"{base}/reject", json={}, headers=operator).status_code == 400
    blank = client.post(f"{base}/reject", json={"reason": "   "}, headers=operator)
    assert blank.status_code == 400

    rejected = client.post(
        f"{base}/reject",
        json={"reason": "Kiyilgan holda qaytarilgan"},
        headers=operator,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["resolution"] == "Kiyilgan holda qaytarilgan"

    # The answer that never used to come.
    groups = client.get(f"{API}/notifications", headers=auth).json()
    texts = [n["text"] for g in groups for n in g["items"]]
    assert any("Kiyilgan holda qaytarilgan" in t for t in texts)

    rows = _audit_rows("return.status", request["id"])
    assert len(rows) == 1
    assert (rows[0].old_value, rows[0].new_value) == ("submitted", "rejected")


def test_the_customers_own_view_of_a_return_keeps_its_shape(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The apps read this list and are shipped, so a decision may change what
    it says but not which fields it has."""
    request = _submit_a_return(client, auth)
    before = next(
        r for r in client.get(f"{API}/returns", headers=auth).json() if r["id"] == request["id"]
    )
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    after = next(
        r for r in client.get(f"{API}/returns", headers=auth).json() if r["id"] == request["id"]
    )

    assert set(before) == set(after)
    assert before["status"] == "submitted" and after["status"] == "approved"


def test_only_staff_may_decide_a_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    assert client.get(f"{API}/staff/returns").status_code == 401
    assert client.get(f"{API}/staff/returns", headers=auth).status_code == 403
    assert client.post(f"{base}/approve", json={}, headers=auth).status_code == 403
    assert client.get(f"{API}/staff/returns", headers=operator).status_code == 200


# ------------------------------------------------------------------ delivery windows


def test_windows_can_be_opened_a_fortnight_at_a_time(
    client: TestClient, operator: dict[str, str]
) -> None:
    """The seed fills a week and nothing refills it, which is how the shop ran
    out of slots. One call has to be able to open a whole stretch."""
    far = date.today() + timedelta(days=40)
    days = [(far + timedelta(days=n)).isoformat() for n in range(3)]
    body = {
        "days": days,
        "windows": [
            {"start_time": "09:00", "end_time": "13:00", "note": "Ertalabki yetkazish"},
            {"start_time": "14:00", "end_time": "18:00", "price": 9000, "capacity": 5},
        ],
    }

    created = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert created.status_code == 201
    assert len(created.json()) == 6

    # Running it again tops up rather than doubling up.
    again = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert again.status_code == 201
    assert again.json() == []

    listed = client.get(
        f"{API}/staff/delivery/slots",
        params={"from_day": days[0], "to_day": days[-1]},
        headers=operator,
    ).json()
    assert len(listed) == 6
    assert {sl["capacity_left"] for sl in listed} == {20, 5}

    # And the customer's own picker now has them.
    offered = client.get(
        f"{API}/delivery/slots", params={"days": 14}, headers=operator
    ).json()
    assert offered, "the customer endpoint still answers"


def test_a_window_that_ends_before_it_starts_is_refused(
    client: TestClient, operator: dict[str, str]
) -> None:
    body = {
        "days": [date.today().isoformat()],
        "windows": [{"start_time": "18:00", "end_time": "14:00"}],
    }
    refused = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert refused.status_code == 422


def test_capacity_can_be_raised_again_and_the_change_is_logged(
    client: TestClient, operator: dict[str, str]
) -> None:
    """Capacity only ever went down — one seat per order placed, and nothing
    to put a seat back or open more."""
    far = (date.today() + timedelta(days=50)).isoformat()
    slot = client.post(
        f"{API}/staff/delivery/slots",
        json={
            "days": [far],
            "windows": [{"start_time": "10:00", "end_time": "12:00", "capacity": 0}],
        },
        headers=operator,
    ).json()[0]
    assert slot["capacity_left"] == 0

    raised = client.patch(
        f"{API}/staff/delivery/slots/{slot['id']}",
        json={"capacity_left": 12, "price": 15000},
        headers=operator,
    )
    assert raised.status_code == 200
    assert raised.json()["capacity_left"] == 12
    assert raised.json()["price"] == 15000
    # An absent field is not "set to nothing".
    assert raised.json()["note"] == slot["note"]

    capacity = _audit_rows("slot.capacity_left", slot["id"])
    assert (capacity[0].old_value, capacity[0].new_value) == ("0", "12")
    price = _audit_rows("slot.price", slot["id"])
    assert (price[0].old_value, price[0].new_value) == ("0", "15000")


def test_only_staff_may_touch_the_delivery_windows(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    body = {
        "days": [(date.today() + timedelta(days=60)).isoformat()],
        "windows": [{"start_time": "09:00", "end_time": "11:00"}],
    }
    assert client.post(f"{API}/staff/delivery/slots", json=body).status_code == 401
    assert client.post(f"{API}/staff/delivery/slots", json=body, headers=auth).status_code == 403
    assert client.get(f"{API}/staff/delivery/slots", headers=auth).status_code == 403
    allowed = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert allowed.status_code == 201


def test_a_missing_thing_is_a_404_not_a_conflict(
    client: TestClient, operator: dict[str, str]
) -> None:
    assert client.get(f"{API}/staff/returns/999999", headers=operator).status_code == 404
    assert client.get(f"{API}/staff/orders/999999", headers=operator).status_code == 404
    assert client.patch(
        f"{API}/staff/delivery/slots/999999", json={"capacity_left": 1}, headers=operator
    ).status_code == 404
    assert client.post(
        f"{API}/staff/reviews/999999/publish", json={}, headers=operator
    ).status_code == 404


def test_a_refused_move_says_so_in_the_apps_language(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    refused = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "delivered"},
        headers={**operator, "Accept-Language": "en"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "placed cannot become delivered"


# --------------------------------------------------------- what comes back


def _counts(product_id: int, variant_ids: tuple[int, ...] = (), slot_id: int | None = None) -> dict:
    """Every count an order moves, read straight from the tables."""
    with Session(engine) as session:
        product = session.get(Product, product_id)
        slot = session.get(DeliverySlot, slot_id) if slot_id else None
        return {
            "stock_left": product.stock_left,
            "in_stock": product.in_stock,
            "sold_count": product.sold_count,
            "variants": {
                v: session.get(ProductVariant, v).stock_left for v in variant_ids
            },
            "capacity_left": slot.capacity_left if slot else None,
        }


PRODUCT_WITH_VARIANTS = 1
SHELF = 50          # what the helper below stocks the shelf with
VARIANT_SHELF = 20  # and each of the two variants it picks


def _order_with_a_variant_and_a_slot(
    client: TestClient, auth: dict[str, str], quantity: int = 2
) -> tuple[dict, dict, tuple[int, ...], int]:
    """An order that moves all four counts, and what they were beforehand.

    The shelf is set to a known figure first. These tests each spend some of
    it and only some of them put it back, which is the behaviour under test —
    so without a baseline they would run the product out and start failing in
    whatever order they happen to run in.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/{PRODUCT_WITH_VARIANTS}").json()
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    size = next(
        v
        for v in product["variants"]
        if v["kind"] == "size" and v["parent_id"] == colour["id"]
    )
    days = client.get(f"{API}/delivery/slots", params={"days": 5}, headers=auth).json()
    slot = next(sl for day in days for sl in day["slots"] if sl["available"])
    variant_ids = (colour["id"], size["id"])

    # Stocked through the ledger, because that is the only way a count moves
    # now: writing the figure onto the row would leave the running total
    # disagreeing with the sum of its movements, which is the one thing the
    # ledger must never do. Only the leaves are set — a colour is the sum of
    # its sizes and follows on its own.
    with Session(engine) as session:
        offer = of.winning_offer(session, product["id"]) or of.offers_for(
            session, product["id"], active_only=False
        )[0]
        offer.active = True
        session.add(offer)
        for leaf in of.leaf_variants(session, product["id"]):
            current = of.variant_stock(session, offer.id, leaf.id) or 0
            st.move(
                session,
                offer=offer,
                kind=StockMovementKind.COUNT_ADJUSTMENT,
                quantity=VARIANT_SHELF - current,
                variant_id=leaf.id,
                reason="sinov javoni",
            )
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    before = _counts(product["id"], variant_ids, slot["id"])
    client.post(
        f"{API}/cart/items",
        json={
            "product_id": product["id"],
            "color_variant_id": colour["id"],
            "variant_id": size["id"],
            "quantity": quantity,
        },
        headers=auth,
    )
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"]},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    return created.json(), before, variant_ids, slot["id"]


def test_placing_an_order_moves_all_four_counts(
    client: TestClient, auth: dict[str, str]
) -> None:
    """The baseline the restoration is measured against — and proof the order
    line now remembers which variants it took, which is what makes any of it
    possible to undo."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)

    assert after["stock_left"] == before["stock_left"] - 2
    assert after["sold_count"] == before["sold_count"] + 2
    assert after["capacity_left"] == before["capacity_left"] - 1
    for v in variant_ids:
        assert after["variants"][v] == before["variants"][v] - 2

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert (line.color_variant_id, line.variant_id) == variant_ids
        assert session.get(Order, order["id"]).slot_id == slot_id


def test_cancelling_puts_all_four_counts_back(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Nothing about a cancelled order happened, so nothing about it should
    still be counted: the goods never left, they were never sold, and the
    window is free for somebody else."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    reasons = client.get(f"{API}/orders/reasons/cancel").json()

    cancelled = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["sold_count"] == before["sold_count"]
    assert after["capacity_left"] == before["capacity_left"]
    assert after["variants"] == before["variants"]


def test_the_operator_cancels_exactly_as_the_customer_does(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Two cancel paths, one restoration between them. The operator's put
    nothing back at all."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)

    cancelled = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "Mijoz telefonda voz kechdi"},
        headers=operator,
    )
    assert cancelled.status_code == 200

    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["sold_count"] == before["sold_count"]
    assert after["capacity_left"] == before["capacity_left"]
    assert after["variants"] == before["variants"]


def test_a_sold_out_product_is_on_sale_again_once_it_is_cancelled(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A shelf emptied by an order that never happened is not empty."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    client.post(f"{API}/cart/items", json=_pick(product["id"], left), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    emptied = client.get(f"{API}/products/{product['id']}").json()
    assert emptied["stock_left"] == 0
    assert emptied["in_stock"] is False

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)

    back = client.get(f"{API}/products/{product['id']}").json()
    assert back["stock_left"] == left
    assert back["in_stock"] is True


def test_cancelling_says_who_moved_which_count(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    product_id = order["items"][0]["product_id"]
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "TKT-9001"},
        headers=operator,
    )

    with Session(engine) as session:
        rows = session.exec(
            select(AuditLog).where(
                AuditLog.action == "order.cancel", AuditLog.note == "TKT-9001"
            )
        ).all()
    moved = {(r.entity, r.field) for r in rows}
    assert ("product", "stock_left") in moved
    assert ("product", "sold_count") in moved
    assert ("product_variant", "stock_left") in moved
    assert ("delivery_slot", "capacity_left") in moved
    assert all(r.actor_role is UserRole.OPERATOR for r in rows)

    shelf = next(
        r for r in rows if r.entity == "product" and r.field == "stock_left"
    )
    assert shelf.entity_id == product_id
    assert int(shelf.new_value) - int(shelf.old_value) == 2


# --------------------------------------------------------- refund and restock


def _refundable_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> tuple[dict, dict, tuple[int, ...], int]:
    """An approved return on a delivered order, ready to be paid back."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"
    _to_the_door(client, operator, order["id"])

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Rangi rasmdagidek emas"},
        headers=auth,
    ).json()
    approved = client.post(
        f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator
    )
    assert approved.status_code == 200
    return request, before, variant_ids, slot_id


def test_a_refund_that_restocks_puts_the_goods_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request, before, variant_ids, slot_id = _refundable_return(client, auth, operator)
    product_id = client.get(
        f"{API}/staff/returns/{request['id']}", headers=operator
    ).json()["order_id"]

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Ko'zdan kechirildi, butun"},
        headers=operator,
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"

    after = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["variants"] == before["variants"]
    # It was sold, and delivered, and that happened. A refund returns money,
    # not the fact of the sale — and the window was used, not freed.
    assert after["sold_count"] == before["sold_count"] + 2
    assert after["capacity_left"] == before["capacity_left"] - 1
    assert product_id


def test_a_refund_without_restocking_leaves_the_shelf_alone(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Goods that came back damaged belong on nobody's count."""
    request, before, variant_ids, slot_id = _refundable_return(client, auth, operator)
    sold_out = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": False, "reason": "Yaroqsiz holatda qaytdi"},
        headers=operator,
    )
    assert refunded.status_code == 200

    after = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)
    assert after["stock_left"] == sold_out["stock_left"] == before["stock_left"] - 2
    assert after["variants"] == sold_out["variants"]


def test_both_answers_about_the_goods_are_logged(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """A write-off nobody recorded is indistinguishable from stock going
    missing, so "we kept it off the shelf" is a logged decision too."""
    kept, _, _, _ = _refundable_return(client, auth, operator)
    client.post(
        f"{API}/staff/returns/{kept['id']}/refund",
        json={"restock": False, "reason": "Yaroqsiz"},
        headers=operator,
    )
    shelved, _, _, _ = _refundable_return(client, auth, operator)
    client.post(
        f"{API}/staff/returns/{shelved['id']}/refund",
        json={"restock": True},
        headers=operator,
    )

    decisions = {
        r.entity_id: r.new_value
        for r in _audit_rows("return.restock", kept["id"])
        + _audit_rows("return.restock", shelved["id"])
        if r.entity == "return_request"
    }
    assert decisions == {kept["id"]: "false", shelved["id"]: "true"}

    # And the counts that actually moved are logged against the goods.
    assert not [
        r for r in _audit_rows("return.restock", kept["id"]) if r.entity == "product"
    ]
    with Session(engine) as session:
        shelf = session.exec(
            select(AuditLog).where(
                AuditLog.action == "return.restock",
                AuditLog.entity == "product",
                AuditLog.field == "stock_left",
            )
        ).all()
    assert shelf and all(
        int(r.new_value) > int(r.old_value) for r in shelf
    )


def test_the_customer_can_read_how_much_came_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The figure was only ever in the audit log, which the customer cannot
    read — so the request could not answer the one question they have."""
    request, _, _, _ = _refundable_return(client, auth, operator)

    before = next(
        r for r in client.get(f"{API}/returns", headers=auth).json()
        if r["id"] == request["id"]
    )
    assert before["refund_amount"] == 0

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True},
        headers=operator,
    ).json()

    after = next(
        r for r in client.get(f"{API}/returns", headers=auth).json()
        if r["id"] == request["id"]
    )
    assert after["refund_amount"] == refunded["refund_amount"] > 0
    # The whole order, because the request did not name a line of it.
    with Session(engine) as session:
        order = session.get(Order, refunded["order_id"])
    assert after["refund_amount"] == order.total
    # Added, not changed: every field the apps already read is still there.
    assert set(before) == set(after)
    assert {"id", "order_code", "reason", "comment", "status", "created_at"} <= set(after)


def test_only_the_named_line_comes_back_on_a_partial_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """A request that names one item is about that item, and neither the money
    nor the shelf should move for the rest of the order."""
    client.delete(f"{API}/cart", headers=auth)
    cheap, dear = client.get(
        f"{API}/products", params={"sort": "price_asc"}
    ).json()["items"][:2]
    for product in (cheap, dear):
        client.post(
            f"{API}/cart/items", json=_pick(product["id"]), headers=auth
        )
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    assert len(order["items"]) == 2

    url = f"{API}/staff/orders/{order['id']}/status"
    _to_the_door(client, operator, order["id"])

    line = next(i for i in order["items"] if i["product_id"] == cheap["id"])
    other = next(i for i in order["items"] if i["product_id"] == dear["id"])
    before = _counts(other["product_id"])

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"order_item_id": line["id"], "reason": "Kerak emas"},
        headers=auth,
    ).json()
    client.post(
        f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator
    )
    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True},
        headers=operator,
    ).json()

    assert refunded["refund_amount"] == line["line_total"] < order["total"]
    assert _counts(other["product_id"])["stock_left"] == before["stock_left"]


# --------------------------------------------------------- offers and sellers


def _seller(name: str, *, commission: int = 5) -> int:
    with Session(engine) as session:
        row = session.exec(select(Seller).where(Seller.name == name)).first()
        if row is None:
            row = Seller(name=name, phone="+998781234567", commission_percent=commission)
            session.add(row)
            session.commit()
            session.refresh(row)
        return row.id


def _offer(
    product_id: int,
    *,
    seller: str,
    price: int,
    stock: int,
    old_price: int | None = None,
    active: bool = True,
) -> int:
    """Put one seller's offer on a product, and let the cache follow.

    The shelf is moved through the ledger rather than written onto the row: a
    running total that disagrees with the sum of its movements is the one
    thing the warehouse must never contain, and the suite checks that
    globally.
    """
    seller_id = _seller(seller)
    with Session(engine) as session:
        row = session.exec(
            select(Offer).where(
                Offer.product_id == product_id, Offer.seller_id == seller_id
            )
        ).first()
        if row is None:
            row = Offer(seller_id=seller_id, product_id=product_id, price=price)
        row.price, row.old_price, row.active = price, old_price, active
        session.add(row)
        session.commit()
        session.refresh(row)
        _adjust_to(session, row, stock)
        session.commit()
        of.refresh(session, product_id)
        session.commit()
        return row.id


def _adjust_to(session: Session, offer: Offer, target: int) -> None:
    """Bring an offer's whole shelf to `target` by recording the difference.

    All of it on the first leaf and nothing on the rest, so the offer's total
    is the figure asked for rather than the figure times the number of sizes.
    Which size is arbitrary and does not matter to the callers; what matters
    is that the total is right and the ledger explains it.
    """
    leaves = of.leaf_variants(session, offer.product_id)
    if leaves:
        for index, leaf in enumerate(leaves):
            current = of.variant_stock(session, offer.id, leaf.id) or 0
            st.move(
                session,
                offer=offer,
                kind=StockMovementKind.COUNT_ADJUSTMENT,
                quantity=(target if index == 0 else 0) - current,
                variant_id=leaf.id,
                reason="sinov javoni",
            )
    else:
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=target - offer.stock_left,
            reason="sinov javoni",
        )


def _undercuts(house_price: int) -> tuple[int, int]:
    """Two prices below the house's, well apart, and never below a so'm.

    Fixed offsets do not work across this catalogue: it runs from a few
    thousand so'm to a few million, and "the house price less six hundred
    thousand" is a negative number on half of it.
    """
    cheap = max(1_000, house_price // 3)
    mid = max(cheap * 2, house_price // 2)
    return cheap, mid


def _untouched_product(client: TestClient) -> dict:
    """A product no other test has put a second seller on.

    One offer means one price, which is the state the whole catalogue is in
    after the migration — and taking a fresh one per test keeps each of them
    reasoning about a shelf nothing else has been spending.

    The seeded catalogue is thirty-one cards and this suite spends them, so
    when they run out a new one is made through the front door: written,
    published, offered by the house and stocked. That is a slower path than
    picking one, which is why it is the fallback rather than the rule.
    """
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    with Session(engine) as session:
        single = {
            product_id
            for product_id in session.exec(select(Offer.product_id)).all()
            if len(of.offers_for(session, product_id, active_only=False)) == 1
        }
    found = next(
        (p for p in listing["items"] if p["in_stock"] and p["id"] in single), None
    )
    return found if found is not None else _mint_a_product(client)


def _mint_a_product(client: TestClient) -> dict:
    """A fresh card in the shop, offered by the house and stocked.

    Everything through the endpoints this stage added, except the shelf, which
    goes through the ledger because that is the only way a count moves.
    """
    admin = _sign_in_as(client, ADMIN_PHONE)
    with Session(engine) as session:
        minted = len(session.exec(select(Product)).all()) + 1
        house = session.exec(select(Seller).where(Seller.name == "Mini Bozor")).one()
        house_id = house.id

    product_id = _write_a_card(
        sku=f"MB-MINT-{minted}",
        title=f"Sinov tovari {minted}",
        price=400_000,
        status=ProductStatus.PUBLISHED,
    )
    offer = client.post(
        f"{API}/staff/offers",
        json={"product_id": product_id, "price": 400_000, "seller_id": house_id},
        headers=admin,
    )
    assert offer.status_code == 201, offer.text

    with Session(engine) as session:
        _adjust_to(session, session.get(Offer, offer.json()["id"]), 25)
        session.commit()
        of.refresh(session, product_id)
        session.commit()
    return client.get(f"{API}/products/{product_id}").json()


def _sign_in_as(client: TestClient, phone: str) -> dict[str, str]:
    """Auth headers for a phone, for the helpers that cannot take a fixture."""
    requested = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    tokens = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": requested["dev_code"]}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_the_cheapest_offer_wins_the_card(client: TestClient) -> None:
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])

    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=4)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=9)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["price"] == cheap
    assert card["stock_left"] == 4
    assert card["seller"] == "Toshkent Elektronika"
    # Every field the apps read is still the field it was; only the value moved.
    assert set(card) >= {"price", "old_price", "discount_percent", "stock_left", "in_stock"}


def test_an_offer_with_nothing_left_does_not_compete(client: TestClient) -> None:
    """A price nobody can pay is not a price. It used to be the whole shop's
    only price, so the question could not come up."""
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])

    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=0)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=6)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["price"] == mid
    assert card["seller"] == "Chilonzor Savdo"
    assert card["in_stock"] is True

    # And with none of them holding anything, the card keeps a price to print
    # and says plainly that it cannot be bought.
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=0)
    with Session(engine) as session:
        for row in of.offers_for(session, product["id"]):
            _adjust_to(session, row, 0)
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    empty = client.get(f"{API}/products/{product['id']}").json()
    assert empty["in_stock"] is False
    assert empty["stock_left"] == 0
    assert empty["price"] == cheap, "the cheapest offer still names the price"


def test_selling_a_winner_out_hands_the_card_to_the_next_seller(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Bought through the front door, not set in the table: the point is that
    an order draws down the seller's shelf and the card follows."""
    product = _untouched_product(client)
    low, mid = _undercuts(product["price"])
    cheap = _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=2)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=8)

    client.delete(f"{API}/cart", headers=auth)
    response = client.post(f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth)
    assert response.status_code == 201, response.text
    added = response.json()
    # The basket is capped by the chosen seller's shelf, not the catalogue's.
    assert added["items"][0]["unit_price"] == low
    assert added["items"][0]["stock_left"] == 2

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert order.status_code == 201

    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 0

    moved_on = client.get(f"{API}/products/{product['id']}").json()
    assert moved_on["price"] == mid
    assert moved_on["seller"] == "Chilonzor Savdo"
    assert moved_on["stock_left"] == 8


def test_the_order_line_says_who_sold_it(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Without this there is no answering "who is owed this money", which is
    the difference between a shop and a marketplace."""
    product = _untouched_product(client)
    cheap, _ = _undercuts(product["price"])
    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=5)
    seller_id = _seller("Toshkent Elektronika")

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert line.seller_id == seller_id
        assert line.offer_id is not None
        seller = session.get(Seller, line.seller_id)
    assert seller.commission_percent == 5, "five per cent of every item sold"


def test_cancelling_gives_the_stock_back_to_the_seller_it_came_from(
    client: TestClient, auth: dict[str, str]
) -> None:
    product = _untouched_product(client)
    low, _ = _undercuts(product["price"])
    cheap = _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=5)
    dear_id = _offer(product["id"], seller="Chilonzor Savdo", price=product["price"], stock=7)

    client.delete(f"{API}/cart", headers=auth)
    added = client.post(f"{API}/cart/items", json=_pick(product["id"], 3), headers=auth)
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 2
        assert session.get(Offer, dear_id).stock_left == 7

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)

    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 5, "back on the shelf it left"
        assert session.get(Offer, dear_id).stock_left == 7, "and not on anybody else's"
    assert client.get(f"{API}/products/{product['id']}").json()["stock_left"] == 5


def test_the_cache_follows_the_offer_that_changed(client: TestClient) -> None:
    """The product's price is a copy, and a copy is only as good as what keeps
    it in step. One function writes it, and everything that can change the
    answer calls that function."""
    product = _untouched_product(client)
    # Under the house's price, whatever the house's price happens to be: this
    # catalogue runs from a few thousand so'm to a few million.
    was = product["price"]
    low, mid = _undercuts(was)
    _offer(product["id"], seller="Toshkent Elektronika", price=mid, stock=3, old_price=was)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert (card["price"], card["old_price"]) == (mid, was)
    assert card["discount_percent"] == round((was - mid) / was * 100)

    # A seller cutting their price.
    _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=3, old_price=was)
    cut = client.get(f"{API}/products/{product['id']}").json()
    assert cut["price"] == low
    assert cut["discount_percent"] == round((was - low) / was * 100)

    # And withdrawing it altogether, which hands the card back.
    _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=3, active=False)
    withdrawn = client.get(f"{API}/products/{product['id']}").json()
    assert withdrawn["price"] != low
    assert withdrawn["seller"] == "Mini Bozor"


def test_price_sorting_sorts_by_the_winning_price(client: TestClient) -> None:
    """The listing sorts in SQL over a paged query, which is the whole reason
    the winning price is cached on the product at all."""
    product = _untouched_product(client)
    # One so'm: nothing in the catalogue can undercut it, so the assertion
    # does not depend on what the rest of the shop happens to cost.
    _offer(product["id"], seller="Toshkent Elektronika", price=1, stock=3)

    cheapest = client.get(
        f"{API}/products", params={"sort": "price_asc", "page_size": 5}
    ).json()["items"]
    assert cheapest[0]["id"] == product["id"]
    assert cheapest[0]["price"] == 1
    assert [i["price"] for i in cheapest] == sorted(i["price"] for i in cheapest)

    # And the filter reads the same figure.
    under = client.get(f"{API}/products", params={"max_price": 1}).json()
    assert [i["id"] for i in under["items"]] == [product["id"]]
    assert under["total"] == 1

    dearest = client.get(
        f"{API}/products", params={"sort": "price_desc", "page_size": 5}
    ).json()["items"]
    assert product["id"] not in [i["id"] for i in dearest]


def test_the_offers_list_shows_every_seller_cheapest_first(client: TestClient) -> None:
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])
    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=0)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=4)

    listed = client.get(f"{API}/products/{product['id']}/offers").json()
    assert [o["price"] for o in listed] == sorted(o["price"] for o in listed)
    assert [o["seller"]["name"] for o in listed[:2]] == [
        "Toshkent Elektronika",
        "Chilonzor Savdo",
    ]
    # The cheapest is shown, and shown to be sold out — which is why the card
    # is quoting the second one.
    assert listed[0]["in_stock"] is False and listed[0]["is_winner"] is False
    assert listed[1]["is_winner"] is True
    assert sum(1 for o in listed if o["is_winner"]) == 1

    # A withdrawn offer is not on sale, so it is not on the list.
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=4, active=False)
    fewer = client.get(f"{API}/products/{product['id']}/offers").json()
    assert "Chilonzor Savdo" not in [o["seller"]["name"] for o in fewer]

    assert client.get(f"{API}/products/999999/offers").status_code == 404


def test_every_product_still_has_at_least_one_offer(client: TestClient) -> None:
    """The invariant the migration left behind: the catalogue read as a
    single-seller shop all along, so nothing should have been left without a
    price to show."""
    with Session(engine) as session:
        products = session.exec(select(Product.id)).all()
        offered = {o.product_id for o in session.exec(select(Offer)).all()}
    assert set(products) <= offered

    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    assert all(p["price"] > 0 for p in listing["items"])


# --------------------------------------------------------- selling and stocking


def _linked_seller(
    staff: Callable[[UserRole, str], dict[str, str]],
    name: str,
    phone: str,
    *,
    commission: int = 5,
) -> tuple[int, dict[str, str]]:
    """A seller, and the account that signs in as them.

    Two rows, not one: staff come through the same OTP flow as customers and
    the role is the only difference, so a seller is a `sellers` row pointed at
    a `users` row holding UserRole.SELLER.
    """
    headers = staff(UserRole.SELLER, phone)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone == phone)).one()
        row = session.exec(select(Seller).where(Seller.name == name)).first()
        if row is None:
            row = Seller(name=name, phone=phone, commission_percent=commission)
        row.user_id = user.id
        row.commission_percent = commission
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id, headers


def _offer_body(product_id: int, price: int, **extra) -> dict:
    """Post an offer with the product's variants filled in.

    Naming every leaf is required, and most of these tests are about something
    else, so the list is assembled here rather than written out eight times.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    body = {"product_id": product_id, "price": price, "variant_ids": leaves, **extra}
    return body


def _receive_into(
    client: TestClient,
    *,
    seller: dict[str, str],
    warehouse: dict[str, str],
    offer_id: int,
    product_id: int,
    per_leaf: int,
) -> dict:
    """Goods onto the shelf, through the only door there is.

    ``PUT /staff/offers/{id}/stock`` did this in one call and went with the
    panels rebuild, because a count is not a figure anybody types. So the
    seller declares a batch and the warehouse counts it in — two calls rather
    than one because it is two people, which is the whole point.

    Leaves only: a product with colours and sizes is counted cell by cell, and
    one with neither is counted once on the offer itself.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    lines = [
        {"offer_id": offer_id, "variant_id": leaf, "quantity": per_leaf}
        for leaf in leaves
    ] or [{"offer_id": offer_id, "quantity": per_leaf}]

    declared = client.post(
        f"{API}/staff/supplies",
        json={"lines": lines, "note": "sinov uchun partiya"},
        headers=seller,
    )
    assert declared.status_code == 201, declared.text
    batch = declared.json()
    received = client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": per_leaf}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return received.json()


def _untouched_with_variants(client: TestClient) -> dict:
    """A product that has colours and sizes, and only one offer so far."""
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    with Session(engine) as session:
        single = {
            product_id
            for product_id in session.exec(select(Offer.product_id)).all()
            if len(of.offers_for(session, product_id, active_only=False)) == 1
        }
        return next(
            p
            for p in listing["items"]
            if p["in_stock"]
            and p["id"] in single
            and of.leaf_variants(session, p["id"])
        )


def test_a_seller_sets_their_own_price_and_the_card_follows(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    seller_id, mine = _linked_seller(staff, "Yunusobod Savdo", "+998900010001")
    cheap, _ = _undercuts(product["price"])

    created = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap),
        headers=mine,
    )
    assert created.status_code == 201, created.text
    offer = created.json()
    assert offer["seller"]["id"] == seller_id
    # Nothing on the shelf until the warehouse books something in, so the card
    # is not handed over on the strength of a price alone.
    assert offer["stock_left"] == 0
    assert offer["is_winner"] is False
    assert client.get(f"{API}/products/{product['id']}").json()["price"] != cheap

    with Session(engine) as session:
        _adjust_to(session, session.get(Offer, offer["id"]), 5)
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    won = client.get(f"{API}/products/{product['id']}").json()
    assert (won["price"], won["seller"], won["stock_left"]) == (cheap, "Yunusobod Savdo", 5)

    # And cutting it again moves the card again — one cache, one writer.
    dropped = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": cheap - 1}, headers=mine
    )
    assert dropped.status_code == 200
    assert client.get(f"{API}/products/{product['id']}").json()["price"] == cheap - 1


def test_a_seller_cannot_touch_somebody_elses_offer(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Sergeli Savdo", "+998900010002")
    _, theirs = _linked_seller(staff, "Olmazor Savdo", "+998900010003")
    cheap, mid = _undercuts(product["price"])

    ours = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).json()

    # A real offer, and a refusal — not a pretence that it is missing.
    refused = client.patch(
        f"{API}/staff/offers/{ours['id']}", json={"price": cheap}, headers=theirs
    )
    assert refused.status_code == 403
    with Session(engine) as session:
        assert session.get(Offer, ours["id"]).price == mid

    # Nor may a seller open an offer in somebody else's name.
    assert client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, seller_id=1),
        headers=theirs,
    ).status_code == 403

    # Their own is fine, and the two coexist.
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=theirs
    ).status_code == 201


def test_stock_is_the_warehouses_and_not_the_sellers(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """The line that matters under this model: the goods are in our warehouse,
    so a seller who could write a stock figure could promise goods nobody has
    received."""
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Chirchiq Savdo", "+998900010004")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010005")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).json()

    # A seller may say a batch is coming. That is a promise and it moves
    # nothing — the shelf is still empty afterwards.
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    lines = [
        {"offer_id": offer["id"], "variant_id": leaf, "quantity": 9} for leaf in leaves
    ] or [{"offer_id": offer["id"], "quantity": 9}]
    declared = client.post(f"{API}/staff/supplies", json={"lines": lines}, headers=mine)
    assert declared.status_code == 201, declared.text
    batch = declared.json()
    assert all(row["received_quantity"] is None for row in batch["lines"])
    with Session(engine) as session:
        assert st.on_hand(session, offer["id"]) == 0

    # Counting it in is the warehouse's, and only theirs.
    counted = {
        "lines": [
            {"line_id": row["id"], "received_quantity": 9} for row in batch["lines"]
        ]
    }
    door = f"{API}/staff/supplies/{batch['id']}/receive"
    assert client.post(door, json=counted).status_code == 401
    assert client.post(door, json=counted, headers=mine).status_code == 403
    assert client.post(door, json=counted, headers=warehouse).status_code == 200
    with Session(engine) as session:
        assert st.on_hand(session, offer["id"]) > 0

    # The price side is closed to the warehouse in the same way.
    assert client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": 1}, headers=warehouse
    ).status_code == 403
    # And a seller still cannot smuggle stock in through the price endpoint.
    assert "stock_left" not in s.OfferUpdateIn.model_fields


def test_an_offer_on_a_product_with_variants_must_name_them_all(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """An offer naming no variants used to win the card and leave every colour
    of the product without a count — a colour with no row on the winning offer
    reads as "nobody counts this apart"."""
    product = _untouched_with_variants(client)
    _, mine = _linked_seller(staff, "Bektemir Savdo", "+998900010006")
    cheap, _ = _undercuts(product["price"])
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    assert len(leaves) > 1

    bare = client.post(
        f"{API}/staff/offers", json={"product_id": product["id"], "price": cheap}, headers=mine
    )
    assert bare.status_code == 422

    partial = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves[:1]},
        headers=mine,
    )
    assert partial.status_code == 422
    assert "detail" in partial.json()

    stray = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": [*leaves, 999999]},
        headers=mine,
    )
    assert stray.status_code == 400

    full = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves},
        headers=mine,
    )
    assert full.status_code == 201
    offer = full.json()
    # Rows for every variant, parents included: the parents are what a
    # colour's count is rolled up onto.
    with Session(engine) as session:
        every = session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product["id"])
        ).all()
    assert {v["variant_id"] for v in offer["variants"]} == {v.id for v in every}
    assert all(v["stock_left"] == 0 for v in offer["variants"])


def test_the_warehouse_rolls_a_shelf_up_from_its_leaves(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A colour holding four when its sizes hold one, one and one is a shelf
    that lies about itself, so neither total is ever written directly."""
    product = _untouched_with_variants(client)
    _, mine = _linked_seller(staff, "Zangiota Savdo", "+998900010007")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010008")
    cheap, _ = _undercuts(product["price"])

    with Session(engine) as session:
        leaves = of.leaf_variants(session, product["id"])
        leaf_ids = [v.id for v in leaves]
        parents = {v.id: v.parent_id for v in leaves}

    offer = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, variant_ids=leaf_ids),
        headers=mine,
    ).json()

    _receive_into(
        client,
        seller=mine,
        warehouse=warehouse,
        offer_id=offer["id"],
        product_id=product["id"],
        per_leaf=2,
    )
    body = next(
        row
        for row in client.get(f"{API}/staff/offers", headers=warehouse).json()
        if row["id"] == offer["id"]
    )

    counts = {v["variant_id"]: v["stock_left"] for v in body["variants"]}
    assert body["stock_left"] == 2 * len(leaf_ids), "the offer is the sum of its colours"
    for colour_id in {p for p in parents.values() if p is not None}:
        children = [v for v, parent in parents.items() if parent == colour_id]
        assert counts[colour_id] == 2 * len(children), "a colour is the sum of its sizes"

    # The cache follows, one level down as well.
    page = client.get(f"{API}/products/{product['id']}").json()
    assert page["price"] == cheap and page["stock_left"] == body["stock_left"]
    shown = {v["id"]: v["stock_left"] for v in page["variants"]}
    assert all(shown[v] is not None for v in leaf_ids), "no colour left uncounted"
    assert shown[leaf_ids[0]] == 2

    # A later delivery of one variant is not a statement about the others. Four
    # more of the first cell arrive; every other cell keeps the two it had.
    second = client.post(
        f"{API}/staff/supplies",
        json={
            "lines": [
                {"offer_id": offer["id"], "variant_id": leaf_ids[0], "quantity": 4}
            ]
        },
        headers=mine,
    ).json()
    assert client.post(
        f"{API}/staff/supplies/{second['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": 4}
                for row in second["lines"]
            ]
        },
        headers=warehouse,
    ).status_code == 200

    again = next(
        row
        for row in client.get(f"{API}/staff/offers", headers=warehouse).json()
        if row["id"] == offer["id"]
    )
    after = {v["variant_id"]: v["stock_left"] for v in again["variants"]}
    assert after[leaf_ids[0]] == 6
    assert after[leaf_ids[1]] == 2
    assert again["stock_left"] == body["stock_left"] + 4


def test_a_seller_sees_only_their_own_offers(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    admin: dict[str, str],
) -> None:
    product = _untouched_product(client)
    mine_id, mine = _linked_seller(staff, "Qibray Savdo", "+998900010009")
    _, theirs = _linked_seller(staff, "Nurafshon Savdo", "+998900010010")
    cheap, mid = _undercuts(product["price"])

    client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    )
    client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=theirs
    )

    ours = client.get(f"{API}/staff/offers", headers=mine).json()
    assert {o["seller"]["id"] for o in ours} == {mine_id}
    # Not a filter they chose — asking for somebody else's changes nothing.
    asked = client.get(f"{API}/staff/offers", params={"seller_id": 1}, headers=mine).json()
    assert {o["seller"]["id"] for o in asked} == {mine_id}

    everybody = client.get(
        f"{API}/staff/offers", params={"product_id": product["id"]}, headers=admin
    ).json()
    assert len(everybody) >= 3, "the house's offer and both sellers'"

    # An admin has no seller of their own, so they have to say who they mean.
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], 5), headers=admin
    ).status_code == 400
    named = client.post(
        f"{API}/staff/offers",
        json=_offer_body(_untouched_product(client)["id"], 5, seller_id=mine_id),
        headers=admin,
    )
    assert named.status_code == 201
    assert named.json()["seller"]["id"] == mine_id


def test_a_seller_may_offer_a_product_only_once(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Angren Savdo", "+998900010011")
    cheap, mid = _undercuts(product["price"])

    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).status_code == 201
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).status_code == 409

    missing = client.post(
        f"{API}/staff/offers", json=_offer_body(999999, cheap), headers=mine
    )
    assert missing.status_code == 404
    gone = client.patch(f"{API}/staff/offers/999999", json={"price": 1}, headers=mine)
    assert gone.status_code == 404


def test_every_price_and_count_names_who_moved_it(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A price is the number a seller will argue about."""
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Guliston Savdo", "+998900010012")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010013")
    cheap, mid = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).json()
    client.patch(f"{API}/staff/offers/{offer['id']}", json={"price": cheap}, headers=mine)
    client.patch(f"{API}/staff/offers/{offer['id']}", json={"active": False}, headers=mine)
    _receive_into(
        client,
        seller=mine,
        warehouse=warehouse,
        offer_id=offer["id"],
        product_id=product["id"],
        per_leaf=7,
    )

    rows = _audit_rows("offer.price", offer["id"]) + _audit_rows("offer.create", offer["id"])
    priced = [r for r in rows if r.action == "offer.price"]
    assert (priced[0].old_value, priced[0].new_value) == (str(mid), str(cheap))
    assert priced[0].actor_role is UserRole.SELLER

    withdrawn = _audit_rows("offer.active", offer["id"])
    assert (withdrawn[0].old_value, withdrawn[0].new_value) == ("true", "false")

    # The count's name is on the ledger rather than in the audit log now.
    # ``offer.stock_left`` audit rows were written by the count-correction
    # endpoint, which has gone: goods arrive through a supply, and a movement
    # already carries who moved it and why, which is what that audit row was
    # standing in for while a shelf figure was a number somebody assigned.
    with Session(engine) as session:
        moves = session.exec(
            select(StockMovement).where(
                StockMovement.offer_id == offer["id"],
                StockMovement.kind == StockMovementKind.INTAKE,
            )
        ).all()
        who = {session.get(User, row.actor_id).role for row in moves if row.actor_id}
    assert moves and all(row.quantity > 0 for row in moves)
    assert who == {UserRole.WAREHOUSE}
    assert all(row.reason for row in moves), "every movement says why"


def test_the_struck_through_price_can_be_put_up_and_taken_down(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Denov Savdo", "+998900010014")
    cheap, mid = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, old_price=mid),
        headers=mine,
    ).json()
    assert offer["old_price"] == mid

    # Omitted leaves it alone; nought takes it away. Two different statements.
    kept = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": cheap}, headers=mine
    ).json()
    assert kept["old_price"] == mid
    cleared = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"old_price": 0}, headers=mine
    ).json()
    assert cleared["old_price"] is None


# --------------------------------------------------------- the commission


def test_the_commission_is_snapshotted_on_the_order_line(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A rate is a term of a contract and contracts get renegotiated. A payout
    computed later against today's rate would quietly restate what a seller was
    owed for something they sold last year."""
    product = _untouched_product(client)
    seller_id, mine = _linked_seller(staff, "Buxoro Savdo", "+998900010015", commission=12)
    warehouse = staff(UserRole.WAREHOUSE, "+998900010016")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).json()
    _receive_into(
        client,
        seller=mine,
        warehouse=warehouse,
        offer_id=offer["id"],
        product_id=product["id"],
        per_leaf=4,
    )

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert (line.seller_id, line.commission_percent) == (seller_id, 12)

        # The contract is renegotiated.
        seller = session.get(Seller, seller_id)
        seller.commission_percent = 20
        session.add(seller)
        session.commit()

        again = session.get(OrderItem, line.id)
        assert again.commission_percent == 12, "what was sold was sold at twelve"
        assert session.get(Seller, seller_id).commission_percent == 20

    # And the next sale is at the new rate.
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    later = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    with Session(engine) as session:
        fresh = session.exec(
            select(OrderItem).where(OrderItem.order_id == later["id"])
        ).one()
    assert fresh.commission_percent == 20


def test_the_house_orders_carry_the_rate_they_were_sold_at(client: TestClient) -> None:
    """The backfill the migration did: one seller, one rate, never changed
    since — so the figure was recoverable, and only while that stayed true."""
    with Session(engine) as session:
        lines = session.exec(
            select(OrderItem).where(col(OrderItem.seller_id).is_not(None))
        ).all()
    assert lines
    assert all(line.commission_percent > 0 for line in lines)


# --------------------------------------------------------- the browser's session


def test_the_refresh_token_arrives_as_a_cookie_the_page_cannot_read(
    client: TestClient,
) -> None:
    """A refresh token readable from JavaScript is one XSS away from being
    somebody else's session for the next sixty days."""
    phone = "+998900020001"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    verified = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    )
    assert verified.status_code == 200

    jar = verified.headers.get("set-cookie", "")
    assert "mb_refresh=" in jar
    assert "HttpOnly" in jar
    assert "SameSite=lax" in jar
    assert "Path=/api/v1/auth" in jar, "nothing else should carry this credential"

    # The response shape the apps read is untouched.
    body = verified.json()
    assert set(body) == {
        "access_token", "refresh_token", "token_type", "expires_in", "is_new_user"
    }


def test_a_browser_refreshes_with_no_body_at_all(client: TestClient) -> None:
    phone = "+998900020002"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})

    # The cookie is in the client's jar; no body is sent.
    refreshed = client.post(f"{API}/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # And it rotated, so the cookie has to have been replaced along with it.
    again = client.post(f"{API}/auth/refresh")
    assert again.status_code == 200


def test_the_apps_keep_refreshing_through_the_body(client: TestClient) -> None:
    """The shipped builds send the token in the body and must go on working
    exactly as they did."""
    phone = "+998900020003"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    ).json()
    client.cookies.clear()

    refreshed = client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != pair["refresh_token"]

    # Single use, as before.
    replayed = client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert replayed.status_code == 401


def test_refreshing_with_neither_is_a_401(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh").status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": "nonsense"}).status_code == 401


def test_signing_out_takes_the_cookie_with_it(client: TestClient) -> None:
    phone = "+998900020004"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    out = client.post(f"{API}/auth/logout", headers=headers)
    assert out.status_code == 200
    assert 'mb_refresh=""' in out.headers.get("set-cookie", "")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_the_allowed_origins_are_named_and_never_a_wildcard() -> None:
    """A browser refuses a wildcard together with credentials, so a deployment
    that set one would not be permissive — it would be broken."""
    from app.core.config import Settings

    assert "*" not in settings.cors_origin_list

    # All three staff applications, on both hostnames. Listing only the
    # backoffice is what had actually shipped, and the seller's cabinet and the
    # courier PWA could not reach this API at all: the browser refused the
    # request before it was sent, so the server never saw one to complain
    # about. A test that named the single origin which worked is why that
    # survived, so this names every one of them.
    for port in (5173, 5174, 5175):
        for host in ("localhost", "127.0.0.1"):
            assert f"http://{host}:{port}" in settings.cors_origin_list

    # And a wildcard in the environment is dropped rather than passed through.
    assert Settings(cors_origins="*").cors_origin_list == []
    assert Settings(cors_origins="*,https://ofis.minibozor.uz").cors_origin_list == [
        "https://ofis.minibozor.uz"
    ]


def test_a_preflight_answers_each_staff_application_by_name(
    client: TestClient,
) -> None:
    """One request per application, not one for the first of them.

    The three are separate builds on separate ports and in production on
    separate hostnames, and being allowed is a per-origin fact. Asserting it
    for the backoffice alone said nothing about the other two, which were in
    fact blocked.
    """
    for origin in (
        "http://localhost:5173",   # backoffice
        "http://localhost:5174",   # seller's cabinet
        "http://localhost:5175",   # courier PWA
    ):
        preflight = client.options(
            f"{API}/staff/returns",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert preflight.status_code == 200, origin
        assert preflight.headers["access-control-allow-origin"] == origin
        assert preflight.headers["access-control-allow-credentials"] == "true"

    # Somebody else's page gets nothing.
    stranger = client.options(
        f"{API}/staff/returns",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert stranger.headers.get("access-control-allow-origin") != "https://evil.example"


# --------------------------------------------------------- the shelf as a ledger


def _stock_is_consistent() -> list[str]:
    """Everything the warehouse must never contain, as a list of complaints.

    Two invariants, and both of them hold everywhere or the shelf is lying:

    * **The ledger.** An offer's running total is the sum of its movements. A
      figure is no longer a number anybody writes, so a disagreement here
      means something assigned to one instead of recording why it changed.
    * **The roll-up.** An offer's total is the sum of its colours, and a
      colour is the sum of its sizes. This one is not repairable after the
      fact: a sale that named no colour comes off the total and off no colour,
      and afterwards there is no working out which colour the shirt was. So it
      is checked beside the ledger rather than trusted.
    """
    complaints: list[str] = []
    with Session(engine) as session:
        for offer in session.exec(select(Offer)).all():
            ledger = st.on_hand(session, offer.id)
            if offer.stock_left != ledger:
                complaints.append(
                    f"offer {offer.id}: total {offer.stock_left} but ledger {ledger}"
                )

            variants = session.exec(
                select(ProductVariant).where(ProductVariant.product_id == offer.product_id)
            ).all()
            colours = [v for v in variants if v.kind is VariantKind.COLOR]
            sizes = [v for v in variants if v.kind is VariantKind.SIZE]
            counts = {
                row.variant_id: row.stock_left
                for row in session.exec(
                    select(OfferVariant).where(OfferVariant.offer_id == offer.id)
                ).all()
            }
            if not counts:
                continue

            for colour in colours:
                children = [z for z in sizes if z.parent_id == colour.id]
                if not children or colour.id not in counts:
                    continue
                total = sum(counts.get(z.id, 0) for z in children)
                if counts[colour.id] != total:
                    complaints.append(
                        f"offer {offer.id} colour {colour.id}: "
                        f"{counts[colour.id]} but its sizes hold {total}"
                    )

            if colours and all(c.id in counts for c in colours):
                across = sum(counts[c.id] for c in colours)
                if offer.stock_left != across:
                    complaints.append(
                        f"offer {offer.id}: total {offer.stock_left} "
                        f"but its colours hold {across}"
                    )
    return complaints


def _stocked_offer(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    name: str,
    phone: str,
    *,
    units: int = 6,
) -> tuple[dict, dict, dict[str, str], dict[str, str]]:
    """A seller's own offer on a fresh product, stocked through a supply.

    Which is the only way goods reach a shelf now: declared by the seller,
    counted in by the warehouse.
    """
    product = _untouched_product(client)
    _, seller = _linked_seller(staff, name, phone)
    warehouse = staff(UserRole.WAREHOUSE, f"{phone[:-1]}9")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=seller
    ).json()

    # All of it in one size, so the offer's total is the figure asked for
    # rather than the figure times the number of sizes. Which size is
    # arbitrary; that the total is right is not.
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    lines: list[dict] = [{"offer_id": offer["id"], "quantity": units}]
    if leaves:
        lines = [{"offer_id": offer["id"], "variant_id": leaves[0], "quantity": units}]
    declared = client.post(
        f"{API}/staff/supplies", json={"lines": lines, "note": "sinov partiyasi"}, headers=seller
    )
    assert declared.status_code == 201, declared.text
    supply = declared.json()

    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={
            "lines": [
                {"line_id": line["id"], "received_quantity": units}
                for line in supply["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return product, offer, seller, warehouse


def test_goods_reach_the_shelf_only_by_being_counted_in(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A declaration is a promise. The shelf moves when somebody counts."""
    product = _untouched_product(client)
    _, seller = _linked_seller(staff, "Chinoz Savdo", "+998900020101")
    warehouse = staff(UserRole.WAREHOUSE, "+998900020102")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=seller
    ).json()
    assert offer["stock_left"] == 0

    supply = client.post(
        f"{API}/staff/supplies",
        json={"lines": [{"offer_id": offer["id"], "quantity": 10}], "note": "birinchi palet"},
        headers=seller,
    ).json()
    assert supply["code"].startswith("SUP-"), "the code is ours, not the seller's label"
    assert supply["status"] == "declared"
    # Declared is not delivered: nothing on the shelf yet.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 0

    line_id = supply["lines"][0]["id"]
    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={"lines": [{"line_id": line_id, "received_quantity": 8}], "note": "2 tasi kelmadi"},
        headers=warehouse,
    )
    assert received.status_code == 200
    body = received.json()
    assert body["status"] == "received"
    # The promise and the fact are kept side by side, and so is the gap.
    assert body["lines"][0]["declared_quantity"] == 10
    assert body["lines"][0]["received_quantity"] == 8
    assert body["lines"][0]["difference"] == -2

    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 8
        movement = session.exec(
            select(StockMovement).where(StockMovement.supply_id == supply["id"])
        ).one()
    assert movement.kind is StockMovementKind.INTAKE
    assert movement.quantity == 8
    assert movement.reason == "2 tasi kelmadi"
    assert movement.actor_id is not None, "somebody counted it"
    assert not _stock_is_consistent()


def test_the_shelf_is_always_the_sum_of_its_movements(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The invariant, put through the whole cycle: received, sold, cancelled,
    written off, corrected. A count that disagrees with its own ledger is a
    count somebody assigned."""
    product, offer, seller, warehouse = _stocked_offer(
        client, staff, "Zarafshon Savdo", "+998900020111", units=9
    )
    assert not _stock_is_consistent()

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    assert not _stock_is_consistent()

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)
    assert not _stock_is_consistent()

    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    body = {"quantity": 2, "reason": "suv ketgan"}
    if leaves:
        body["variant_id"] = leaves[0]
    written = client.post(
        f"{API}/staff/offers/{offer['id']}/write-off", json=body, headers=warehouse
    )
    assert written.status_code == 200
    assert not _stock_is_consistent()

    # And the whole story is readable, oldest reason first.
    #
    # ``count_adjustment`` is not in the list any more: the door that wrote one
    # — ``PUT /staff/offers/{id}/stock`` — went with the panels rebuild, and no
    # endpoint produces that kind. The kind itself stays on the enum because
    # rows written before it went are still in the ledger and still have to
    # render.
    ledger = client.get(
        f"{API}/staff/stock/movements", params={"offer_id": offer["id"]}, headers=warehouse
    ).json()
    kinds = {row["kind"] for row in ledger["items"]}
    assert {"intake", "sale", "cancel_return", "write_off"} <= kinds
    assert all(row["reason"] for row in ledger["items"]), "every movement says why"


# --------------------------------------------------------- holding


def test_what_is_in_one_basket_is_not_offered_to_the_next_shopper(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The last one of something used to sit in two baskets at once, and one of
    those two shoppers was going to be disappointed at the till."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Nukus Savdo", "+998900020131", units=2
    )
    mine = sign_in("+998900020135")
    theirs = sign_in("+998900020136")

    client.delete(f"{API}/cart", headers=mine)
    client.delete(f"{API}/cart", headers=theirs)

    pick = _pick(product["id"], 2)
    response = client.post(f"{API}/cart/items", json=pick, headers=mine)
    assert response.status_code == 201, response.text
    assert response.json()["items"][0]["quantity"] == 2

    # The card stops offering what is already promised.
    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["stock_left"] == 0
    assert card["in_stock"] is False

    # And the next shopper is refused rather than sold the same two.
    refused = client.post(f"{API}/cart/items", json=pick, headers=theirs)
    assert refused.status_code == 409

    # Nothing left the shelf: it is held, not gone.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 2
        assert st.reserved(session, offer["id"]) == 2
    assert not _stock_is_consistent()


def test_a_hold_that_has_run_out_lets_go(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """An abandoned basket kept the last one of something for ever: nobody
    could buy it and nobody was going to."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Termiz Savdo", "+998900020141", units=1
    )
    mine = sign_in("+998900020145")
    theirs = sign_in("+998900020146")
    client.delete(f"{API}/cart", headers=mine)
    client.delete(f"{API}/cart", headers=theirs)

    pick = _pick(product["id"], 1)
    client.post(f"{API}/cart/items", json=pick, headers=mine)
    assert client.post(f"{API}/cart/items", json=pick, headers=theirs).status_code == 409

    # Walk away. Nothing sweeps up — the deadline is part of the question.
    with Session(engine) as session:
        line = session.exec(
            select(CartItem).where(CartItem.offer_id == offer["id"])
        ).first()
        assert line is not None
        line.reserved_until = utcnow() - timedelta(minutes=1)
        session.add(line)
        session.commit()
        assert st.reserved(session, offer["id"]) == 0
        of.refresh(session, product["id"])
        session.commit()

    assert client.get(f"{API}/products/{product['id']}").json()["in_stock"] is True
    assert client.post(f"{API}/cart/items", json=pick, headers=theirs).status_code == 201


def test_an_unpaid_order_holds_the_goods_until_the_courier_is_paid(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
    operator: dict[str, str],
) -> None:
    """Cash at the door is not a sale yet. Selling on promise-of-cash is how an
    order refused at the doorstep consumed stock nobody ever gave back."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Jizzax Savdo", "+998900020151", units=5
    )
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth)
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "payment_method": "cash"},
        headers=auth,
    )
    assert order.status_code == 201
    assert order.json()["paid"] is False
    order_id = order.json()["id"]

    # Still on the shelf, and held for this order.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 5
        assert st.reserved(session, offer["id"]) == 2
    assert client.get(f"{API}/products/{product['id']}").json()["stock_left"] == 3
    assert not _stock_is_consistent()

    _to_the_door(client, operator, order_id)
    # Paid at the door: now the goods leave, and the ledger says why.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 3
        assert st.reserved(session, offer["id"]) == 0
        sale = session.exec(
            select(StockMovement).where(
                StockMovement.order_id == order_id,
                StockMovement.kind == StockMovementKind.SALE,
            )
        ).one()
    assert sale.quantity == -2
    assert not _stock_is_consistent()


def test_a_removal_holds_the_goods_then_takes_them_away(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """Selling something that is already on a pallet by the door is the
    failure `ready` exists to prevent."""
    product, offer, seller, warehouse = _stocked_offer(
        client, staff, "Andijon Savdo", "+998900020171", units=6
    )
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    line = {"offer_id": offer["id"], "quantity": 4}
    if leaves:
        line["variant_id"] = leaves[0]

    requested = client.post(
        f"{API}/staff/removals",
        json={"reason": "unsold", "lines": [line], "note": "sotilmadi"},
        headers=seller,
    )
    assert requested.status_code == 201
    removal = requested.json()
    assert removal["code"].startswith("RMV-")
    assert removal["status"] == "requested"

    # Requested is not picked: nothing is held yet.
    with Session(engine) as session:
        assert st.reserved(session, offer["id"]) == 0

    # A seller may not walk off with it themselves.
    assert client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=seller
    ).status_code == 403

    ready = client.post(
        f"{API}/staff/removals/{removal['id']}/prepare",
        json={"lines": [{"line_id": removal["lines"][0]["id"], "prepared_quantity": 4}]},
        headers=warehouse,
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    # Picked and standing by the door: still ours to account for, nobody's to buy.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 6
        assert st.reserved(session, offer["id"]) == 4
        assert st.sellable(session, session.get(Offer, offer["id"])) == 2
    assert not _stock_is_consistent()

    collected = client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=warehouse
    )
    assert collected.status_code == 200
    assert collected.json()["status"] == "collected"

    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 2
        assert st.reserved(session, offer["id"]) == 0
        movement = session.exec(
            select(StockMovement).where(StockMovement.removal_id == removal["id"])
        ).one()
    assert movement.kind is StockMovementKind.SELLER_RETURN
    assert movement.quantity == -4
    assert not _stock_is_consistent()

    # And it cannot be collected twice.
    assert client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=warehouse
    ).status_code == 409


def test_a_seller_sees_their_own_batches_and_nobody_elses(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    _, mine_offer, mine, warehouse = _stocked_offer(
        client, staff, "Farg'ona Savdo", "+998900020181", units=3
    )
    _, _, theirs, _ = _stocked_offer(
        client, staff, "Namangan Savdo", "+998900020191", units=3
    )

    ours = client.get(f"{API}/staff/supplies", headers=mine).json()
    assert ours and {row["seller"]["name"] for row in ours} == {"Farg'ona Savdo"}
    others = client.get(f"{API}/staff/supplies", headers=theirs).json()
    assert {row["seller"]["name"] for row in others} == {"Namangan Savdo"}

    # The warehouse sees everybody's, which is the point of a warehouse.
    everything = client.get(f"{API}/staff/supplies", headers=warehouse).json()
    assert {"Farg'ona Savdo", "Namangan Savdo"} <= {r["seller"]["name"] for r in everything}

    # And one seller cannot read the other's by id.
    theirs_id = next(r["id"] for r in others)
    assert client.get(f"{API}/staff/supplies/{theirs_id}", headers=mine).status_code == 403

    # Nor declare a batch against somebody else's offer.
    assert client.post(
        f"{API}/staff/supplies",
        json={"lines": [{"offer_id": mine_offer["id"], "quantity": 1}]},
        headers=theirs,
    ).status_code == 403, "whose offer it is comes before what it names"

    # The ledger is scoped the same way.
    mine_ledger = client.get(f"{API}/staff/stock/movements", headers=mine).json()
    with Session(engine) as session:
        mine_offers = {
            o.id
            for o in session.exec(
                select(Offer).where(Offer.id == mine_offer["id"])
            ).all()
        }
    assert mine_offers <= {row["offer_id"] for row in mine_ledger["items"]}
    assert all(row["offer_id"] != theirs_id for row in mine_ledger["items"])


def test_a_counted_product_will_not_go_into_a_basket_unnamed(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A sale that names no colour comes off the offer's total and off no
    colour at all, and afterwards there is no working out which colour the
    shirt was. The choice is required rather than guessed."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/1").json()
    sizes = [v for v in product["variants"] if v["kind"] == "size"]
    assert sizes, "seeded with a colour × size grid"

    bare = client.post(
        f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth
    )
    assert bare.status_code == 422
    assert bare.json()["detail"] == "O'lchamni tanlang"

    # A colour on its own is not a leaf either, where the colours have sizes.
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    half = client.post(
        f"{API}/cart/items",
        json={"product_id": product["id"], "color_variant_id": colour["id"]},
        headers=auth,
    )
    assert half.status_code == 422

    # And with the size, it goes in.
    named = client.post(
        f"{API}/cart/items", json=_pick(product["id"]), headers=auth
    )
    assert named.status_code == 201, named.text
    line = named.json()["items"][0]
    assert line["variant_id"] is not None
    assert line["color_variant_id"] is not None

    # A product nobody counts by variant still goes in on its own.
    plain = _variantless_product(client)
    assert client.post(
        f"{API}/cart/items", json={"product_id": plain["id"]}, headers=auth
    ).status_code == 201

    assert not _stock_is_consistent()


def test_a_colour_with_nothing_left_is_out_of_stock_not_a_question(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The one case both apps send no size: a colour whose every size has
    gone. Asking them to choose one would be asking for something that is not
    there, so the answer stays the one they are written to expect."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900020211")
    client.delete(f"{API}/cart", headers=auth)

    # The winning offer's own shelf, because that is the one a shopper buys
    # from — emptying somebody else's cell would leave the colour perfectly
    # buyable and the question perfectly sensible.
    product_id = 1
    with Session(engine) as session:
        assert of.winning_offer(session, product_id) is not None
        colour = next(
            leaf.parent_id
            for leaf in of.leaf_variants(session, product_id)
            if leaf.parent_id is not None
        )
        # Every seller's, not only the winner's: emptying one shelf hands the
        # card to the next, and the colour would still be for sale.
        cells = [
            (offer.id, leaf.id, of.variant_stock(session, offer.id, leaf.id) or 0)
            for offer in of.offers_for(session, product_id, active_only=False)
            for leaf in of.leaf_variants(session, product_id)
            if leaf.parent_id == colour
        ]

    for shelf_id, variant_id, held in cells:
        if held:
            written = client.post(
                f"{API}/staff/offers/{shelf_id}/write-off",
                json={"variant_id": variant_id, "quantity": held, "reason": "suv ketgan"},
                headers=warehouse,
            )
            assert written.status_code == 200, written.text

    # Every size of that colour is gone, so there is no size to choose. Both
    # apps ask exactly this, and the answer they expect is the true one.
    refused = client.post(
        f"{API}/cart/items",
        json={"product_id": product_id, "color_variant_id": colour},
        headers=auth,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "Mahsulot mavjud emas"
    # The other half of the pair — a colour that *does* still have sizes gets
    # asked rather than refused — is
    # `test_a_counted_product_will_not_go_into_a_basket_unnamed`.
    assert not _stock_is_consistent()


def test_the_warehouse_can_see_the_shelves_it_counts(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Reading which offers exist is not pricing them — a warehouse that
    cannot list a shelf cannot go and count it."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900020221")

    listed = client.get(f"{API}/staff/offers", headers=warehouse)
    assert listed.status_code == 200
    assert listed.json(), "every shelf, not one seller's"
    assert len({row["seller"]["id"] for row in listed.json()}) >= 1

    # Still nobody else's business.
    assert client.get(f"{API}/staff/offers", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/offers", headers=operator).status_code == 403
    # And reading is not writing.
    offer_id = listed.json()[0]["id"]
    assert client.patch(
        f"{API}/staff/offers/{offer_id}", json={"price": 1}, headers=warehouse
    ).status_code == 403


# --------------------------------------------------------- the catalogue's owner


def _write_a_card(
    *,
    sku: str,
    title: str,
    price: int = 500_000,
    status: ProductStatus = ProductStatus.DRAFT,
    category_slug: str | None = None,
    **fields,
) -> int:
    """A ``products`` row, written straight into the database.

    **There is no endpoint that writes a card any more.** A seller's listing
    creates one and the warehouse's receipt publishes it —
    ``POST /staff/catalog/listings`` then ``POST /staff/supplies/{id}/receive``
    — and that line has its own tests, which walk all of it. Driving thirty
    unrelated tests through the same line to get a row to edit, translate,
    photograph, reorder or search for would be testing the flow again rather
    than the thing under test, and every one of them would break the next time
    the flow moved.

    So the row is written here directly, for the same reason ``_linked_seller``
    writes a ``sellers`` row directly: the subject of these tests is what
    happens *to* a card that already exists. Returns the id; the tests read it
    back through the admin's own door, which is the one still in the API.
    """
    with Session(engine) as session:
        if category_slug:
            category = session.exec(
                select(Category).where(Category.slug == category_slug)
            ).one()
        else:
            category = session.exec(select(Category).order_by(col(Category.id))).first()
        product = Product(
            sku=sku,
            title=title,
            subtitle=fields.pop("subtitle", "sinov"),
            category_id=category.id,
            price=price,
            status=status,
            **fields,
        )
        session.add(product)
        session.commit()
        return product.id


def _set_status(product_id: int, status: ProductStatus) -> None:
    """Move a card's state, directly.

    ``POST /staff/catalog/products/{id}/status`` is gone: an admin no longer
    publishes cards, because publishing is what receiving the goods means —
    ``app.routers.warehouse.receive_supply``. Nothing else moves a status, so
    a test that needs a card in a particular state writes it, and the tests
    that are *about* the move are the supply ones.
    """
    with Session(engine) as session:
        product = session.get(Product, product_id)
        product.status = status
        session.add(product)
        session.commit()
        of.refresh(session, product_id)
        session.commit()


def _refuse(product_id: int, reason: str) -> None:
    """Refuse a card, directly, with the sentence the seller reads.

    The door that did this — the admin's moderation decision — has gone with
    ``POST /staff/catalog/products/{id}/status``; a card is refused now by the
    warehouse refusing the batch behind it, which is
    ``POST /staff/supplies/{id}/cancel`` and has its own test. See
    ``_set_status``.
    """
    with Session(engine) as session:
        product = session.get(Product, product_id)
        product.status = ProductStatus.REJECTED
        product.moderation_note = reason
        session.add(product)
        session.commit()
        of.refresh(session, product_id)
        session.commit()


def _admin_card(
    client: TestClient,
    admin: dict[str, str],
    *,
    sku: str,
    title: str,
    price: int = 100_000,
    status: ProductStatus = ProductStatus.DRAFT,
    category_slug: str | None = None,
    brand_slug: str | None = None,
    translations: dict | None = None,
    **fields,
) -> dict:
    """A card for the admin's own editing endpoints to work on.

    The row is written directly — see ``_write_a_card`` — and everything the
    admin's doors still own is then written through them: the brand and the
    Russian and English go in with a ``PATCH``, which is where they live now
    that no endpoint creates a card. That is the door these tests are about
    anyway; creating the row was only ever how they got something to edit.
    """
    product_id = _write_a_card(
        sku=sku, title=title, price=price, status=status,
        category_slug=category_slug, **fields,
    )
    patch: dict = {}
    if brand_slug is not None:
        patch["brand_slug"] = brand_slug
    if translations is not None:
        patch["translations"] = translations
    if patch:
        done = client.patch(
            f"{API}/staff/catalog/products/{product_id}", json=patch, headers=admin
        )
        assert done.status_code == 200, done.text
        return done.json()
    got = client.get(f"{API}/staff/catalog/products/{product_id}", headers=admin)
    assert got.status_code == 200, got.text
    return got.json()


def _new_card(
    client: TestClient,
    headers: dict[str, str],
    *,
    sku: str,
    title: str,
    price: int = 500_000,
    path: str | None = None,
) -> dict:
    """A card, read back the way an editor is about to read it.

    ``path`` sends it through a seller's proposal instead, which is still a
    door; without one the row is written directly — see ``_write_a_card``.
    """
    if path is not None:
        listing = client.get(f"{API}/categories").json()
        created = client.post(
            f"{API}{path}",
            json={
                "sku": sku,
                "title": title,
                "subtitle": "sinov",
                "category_slug": listing[0]["slug"],
                "price": price,
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        return created.json()

    product_id = _write_a_card(sku=sku, title=title, price=price)
    got = client.get(f"{API}/staff/catalog/products/{product_id}", headers=headers)
    assert got.status_code == 200, got.text
    return got.json()


def test_an_admin_takes_on_a_seller_and_nobody_else_can(
    client: TestClient,
    admin: dict[str, str],
    operator: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Until now the only way to make a second seller was the database, which
    left the multi-seller model exercised by nothing but a fixture."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030001")
    body = {"name": "Chorsu Bozori", "phone": "+998781112233", "commission_percent": 8}

    assert client.post(f"{API}/staff/sellers", json=body).status_code == 401
    assert client.post(f"{API}/staff/sellers", json=body, headers=auth).status_code == 403
    assert client.post(f"{API}/staff/sellers", json=body, headers=operator).status_code == 403
    assert client.post(f"{API}/staff/sellers", json=body, headers=warehouse).status_code == 403

    created = client.post(f"{API}/staff/sellers", json=body, headers=admin)
    assert created.status_code == 201, created.text
    seller = created.json()
    assert (seller["name"], seller["commission_percent"], seller["active"]) == (
        "Chorsu Bozori",
        8,
        True,
    )
    assert seller["user_phone"] is None, "nobody signs in as them yet"

    # And one name, one seller.
    assert client.post(f"{API}/staff/sellers", json=body, headers=admin).status_code == 409


def test_linking_an_account_is_what_makes_somebody_a_seller(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """There is no state where an account is attached to a seller and cannot
    act as one, so the role comes with the link rather than through a second
    door that does not exist."""
    phone = "+998900030011"
    theirs = sign_in(phone)          # an ordinary customer, for now
    assert client.get(f"{API}/staff/offers", headers=theirs).status_code == 403

    seller = client.post(
        f"{API}/staff/sellers",
        json={"name": "Yakkasaroy Savdo", "user_phone": phone},
        headers=admin,
    ).json()
    assert seller["user_phone"] == phone

    with Session(engine) as session:
        account = session.exec(select(User).where(User.phone == phone)).one()
    assert account.role is UserRole.SELLER

    # They can now see their own shelf — and it is theirs, not everybody's.
    theirs = sign_in(phone)
    mine = client.get(f"{API}/staff/offers", headers=theirs)
    assert mine.status_code == 200
    assert mine.json() == [], "a new seller has no offers"

    # A privilege change is logged with a name against it.
    rows = _audit_rows("user.role", account.id)
    assert rows and rows[0].new_value == "seller"

    # And one account cannot be two sellers.
    assert client.post(
        f"{API}/staff/sellers",
        json={"name": "Boshqa Savdo", "user_phone": phone},
        headers=admin,
    ).status_code == 409


def test_a_second_seller_undercuts_the_first_on_the_same_card(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The whole model, end to end and through the front door: the admin takes
    on a seller, the seller offers on a card the platform already owns, the
    warehouse books the goods in, and the cheaper price wins the card."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030021")
    phone = "+998900030022"
    sign_in(phone)
    seller_row = client.post(
        f"{API}/staff/sellers",
        json={"name": "Olmaliq Savdo", "user_phone": phone, "commission_percent": 11},
        headers=admin,
    ).json()
    seller = sign_in(phone)

    product = _untouched_product(client)
    was = client.get(f"{API}/products/{product['id']}").json()
    cheap, _ = _undercuts(was["price"])
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]

    offer = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves},
        headers=seller,
    )
    assert offer.status_code == 201, offer.text
    # Not in the shop until the warehouse has it: a price with nothing behind
    # it does not win a card.
    assert client.get(f"{API}/products/{product['id']}").json()["price"] == was["price"]

    line: dict = {"offer_id": offer.json()["id"], "quantity": 4}
    if leaves:
        line["variant_id"] = leaves[0]
    supply = client.post(
        f"{API}/staff/supplies", json={"lines": [line]}, headers=seller
    ).json()
    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={"lines": [{"line_id": supply["lines"][0]["id"], "received_quantity": 4}]},
        headers=warehouse,
    )
    assert received.status_code == 200, received.text

    won = client.get(f"{API}/products/{product['id']}").json()
    assert (won["price"], won["seller"], won["stock_left"]) == (cheap, "Olmaliq Savdo", 4)

    # And the card lists both sellers, cheapest first.
    quotes = client.get(f"{API}/products/{product['id']}/offers").json()
    assert [q["seller"]["name"] for q in quotes][0] == "Olmaliq Savdo"
    assert len(quotes) >= 2
    assert sum(1 for q in quotes if q["is_winner"]) == 1

    # The admin sees who they took on, and what they carry.
    seen = next(
        row
        for row in client.get(f"{API}/staff/sellers", headers=admin).json()
        if row["id"] == seller_row["id"]
    )
    assert (seen["offer_count"], seen["commission_percent"]) == (1, 11)
    assert not _stock_is_consistent()


def test_a_card_nobody_has_approved_is_not_in_the_shop(
    client: TestClient, admin: dict[str, str], auth: dict[str, str]
) -> None:
    """Every customer-facing path that returns a product, held to the same
    rule. A shopper who can find a draft has been shown something that does
    not exist yet."""
    card = _new_card(client, admin, sku="MB-DRAFT-1", title="Sinov chiroq, qoralama")
    assert card["status"] == "draft"
    product_id = card["id"]

    def visible() -> dict[str, bool]:
        listing = client.get(f"{API}/products", params={"page_size": 60}).json()
        sold_out_too = client.get(
            f"{API}/products", params={"page_size": 60, "show_sold_out": True}
        ).json()
        similar = client.get(f"{API}/products/1/similar").json()
        home = client.get(f"{API}/home").json()
        suggest = client.get(f"{API}/search/suggest", params={"q": "Sinov chiroq"}).json()
        client.put(f"{API}/favorites/{product_id}", headers=auth)
        favourites = client.get(f"{API}/favorites", headers=auth).json()
        return {
            "listing": any(p["id"] == product_id for p in listing["items"]),
            "even_sold_out": any(p["id"] == product_id for p in sold_out_too["items"]),
            "similar": any(p["id"] == product_id for p in similar),
            "home": any(
                p["id"] == product_id
                for section in home["sections"]
                for p in section["products"]
            ),
            "suggest": any(row["product_id"] == product_id for row in suggest),
            "favourites": any(p["id"] == product_id for p in favourites["items"]),
            "page": client.get(f"{API}/products/{product_id}").status_code == 200,
            "offers": client.get(f"{API}/products/{product_id}/offers").status_code == 200,
        }

    assert not any(visible().values()), visible()

    # Published, and the same walk finds it — the page and the offer list at
    # least; the rails and the typeahead want stock, which it has none of.
    _set_status(product_id, ProductStatus.PUBLISHED)
    now = visible()
    assert now["page"] and now["offers"]
    assert now["even_sold_out"], "in the shop, and the filter can show it"
    assert now["favourites"], "a favourite that can be opened again"

    # Withdrawn, and it is gone from all of them again.
    _set_status(product_id, ProductStatus.ARCHIVED)
    assert not any(visible().values())


def test_a_sellers_proposal_never_lands_in_the_shop(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """A suggestion is not a card in the shop, and no seller can make it one.

    ``POST /staff/catalog/proposals`` is the older door — a seller suggesting a
    card for the platform's own catalogue — and it still exists. What has gone
    is the admin's decision beside it: nothing publishes a card by saying so
    any more. A proposal reaches the shop the way everything else does, by
    goods arriving against it, and the seller's own line for that is
    ``POST /staff/catalog/listings`` (see the section at the end of this file).
    """
    phone = "+998900030031"
    sign_in(phone)
    client.post(
        f"{API}/staff/sellers",
        json={"name": "Uchtepa Savdo", "user_phone": phone},
        headers=admin,
    )
    seller = sign_in(phone)

    proposed = _new_card(
        client,
        seller,
        sku="MB-PROP-1",
        title="Sotuvchi taklifi, stol chirog'i",
        path="/staff/catalog/proposals",
    )
    assert proposed["status"] == "moderating", "not in the shop, whoever sent it"
    assert proposed["proposed_by"]["name"] == "Uchtepa Savdo"
    assert client.get(f"{API}/products/{proposed['id']}").status_code == 404

    # A seller cannot write straight into the catalogue — and neither can an
    # admin. That door is gone from the API rather than guarded, which is a
    # 405 on the path the list endpoint still answers on.
    body = {
        "sku": "MB-PROP-2",
        "title": "O'zim yozdim",
        "category_slug": client.get(f"{API}/categories").json()[0]["slug"],
        "price": 100_000,
    }
    for headers in (seller, admin):
        assert client.post(
            f"{API}/staff/catalog/products", json=body, headers=headers
        ).status_code == 405
    # Nor is there a status door to approve one's own proposal with.
    assert client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "published"},
        headers=seller,
    ).status_code == 404

    # It is in the admin's queue, where somebody will see it.
    queue = client.get(
        f"{API}/staff/catalog/products", params={"status": "moderating"}, headers=admin
    ).json()
    assert any(row["id"] == proposed["id"] for row in queue["items"])

    # And an admin may fix what the seller wrote — editing a card is still
    # theirs, which is the half of moderation that survived.
    fixed = client.patch(
        f"{API}/staff/catalog/products/{proposed['id']}",
        json={"subtitle": "Admin tuzatdi"},
        headers=admin,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["subtitle"] == "Admin tuzatdi"
    assert fixed.json()["status"] == "moderating", "editing is not approving"
    assert client.get(f"{API}/products/{proposed['id']}").status_code == 404


def _card_with_a_colour(
    client: TestClient, admin: dict[str, str], sku: str, *, with_a_size: bool
) -> tuple[int, int]:
    """A published card carrying a colour, and optionally a size of it.

    The row is written directly and the variants go through the admin's own
    endpoints, which are the ones under test — see ``_write_a_card`` for why
    the card itself is not built through a door any more.
    """
    product_id = _write_a_card(
        sku=sku,
        title=f"Sinov kiyim {sku}",
        price=300_000,
        status=ProductStatus.PUBLISHED,
    )

    colour = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "color", "label": "Qora", "value": "#0E0F12"},
        headers=admin,
    )
    assert colour.status_code == 201, colour.text
    colour_id = colour.json()[0]["id"]

    leaf_id = colour_id
    if with_a_size:
        sized = client.post(
            f"{API}/staff/catalog/products/{product_id}/variants",
            json={"kind": "size", "label": "L", "value": "L", "parent_id": colour_id},
            headers=admin,
        )
        assert sized.status_code == 201, sized.text
        leaf_id = next(v["id"] for v in sized.json() if v["kind"] == "size")

    return product_id, leaf_id


def _stock_a_leaf(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    product_id: int,
    leaf_id: int,
    units: int,
) -> int:
    """The house takes the card on and the warehouse books goods in."""
    with Session(engine) as session:
        house_id = session.exec(select(Seller).where(Seller.name == "Mini Bozor")).one().id
    offer = client.post(
        f"{API}/staff/offers",
        json={
            "product_id": product_id,
            "price": 300_000,
            "seller_id": house_id,
            "variant_ids": [leaf_id],
        },
        headers=admin,
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    supply = client.post(
        f"{API}/staff/supplies",
        json={
            "lines": [{"offer_id": offer_id, "variant_id": leaf_id, "quantity": units}],
            "seller_id": house_id,
        },
        headers=admin,
    )
    assert supply.status_code == 201, supply.text
    received = client.post(
        f"{API}/staff/supplies/{supply.json()['id']}/receive",
        json={
            "lines": [
                {"line_id": supply.json()["lines"][0]["id"], "received_quantity": units}
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return offer_id


def test_a_variant_with_a_history_cannot_be_deleted(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The ledger would stop explaining its own totals, and an old order would
    point at a row that is not there."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030041")
    product_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-VAR-1", with_a_size=True
    )

    # Before anything has happened to it, a variant is just a row.
    spare = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "color", "label": "Oq", "value": "#FFFFFF"},
        headers=admin,
    ).json()
    spare_id = next(v["id"] for v in spare if v["label"] == "Oq")
    assert client.delete(
        f"{API}/staff/catalog/products/{product_id}/variants/{spare_id}",
        headers=admin,
    ).status_code == 200

    _stock_a_leaf(client, admin, warehouse, product_id, leaf_id, 3)

    refused = client.delete(
        f"{API}/staff/catalog/products/{product_id}/variants/{leaf_id}",
        headers=admin,
    )
    assert refused.status_code == 409
    assert "harakat" in refused.json()["detail"]
    assert not _stock_is_consistent()


def test_a_size_cannot_be_added_under_stock_that_is_already_counted(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A shelf counted on colours would have every figure sitting a level
    above where the ledger looks for it, with no way to say how the colour's
    stock divides between the new sizes."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030042")
    product_id, colour_id = _card_with_a_colour(
        client, admin, "MB-VAR-2", with_a_size=False
    )

    # No stock yet, so the grid may still change shape.
    allowed = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "size", "label": "S", "value": "S", "parent_id": colour_id},
        headers=admin,
    )
    assert allowed.status_code == 201

    other_id, other_colour = _card_with_a_colour(
        client, admin, "MB-VAR-3", with_a_size=False
    )
    _stock_a_leaf(client, admin, warehouse, other_id, other_colour, 4)

    blocked = client.post(
        f"{API}/staff/catalog/products/{other_id}/variants",
        json={"kind": "size", "label": "M", "value": "M", "parent_id": other_colour},
        headers=admin,
    )
    assert blocked.status_code == 409
    assert "sanoq" in blocked.json()["detail"]
    assert not _stock_is_consistent()


def test_standing_a_seller_down_takes_their_offers_with_them(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Left active, the cheapest card in the shop could belong to somebody we
    have stopped dealing with."""
    product, offer, seller_headers, _ = _stocked_offer(
        client, staff, "Sirdaryo Savdo", "+998900030051", units=5
    )
    assert client.get(f"{API}/products/{product['id']}").json()["seller"] == "Sirdaryo Savdo"

    with Session(engine) as session:
        seller_id = session.exec(
            select(Seller).where(Seller.name == "Sirdaryo Savdo")
        ).one().id

    stood_down = client.patch(
        f"{API}/staff/sellers/{seller_id}", json={"active": False}, headers=admin
    )
    assert stood_down.status_code == 200
    assert stood_down.json()["active"] is False

    # The card is back with whoever else sells it.
    assert client.get(f"{API}/products/{product['id']}").json()["seller"] != "Sirdaryo Savdo"
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).active is False
    rows = _audit_rows("seller.active", seller_id)
    assert (rows[0].old_value, rows[0].new_value) == ("true", "false")
    assert seller_headers


# --------------------------------------------------------- who works here


def _find_user(client: TestClient, admin: dict[str, str], phone: str) -> dict:
    """The account behind a phone number, the way a panel finds it."""
    found = client.get(f"{API}/staff/users", params={"q": phone}, headers=admin)
    assert found.status_code == 200, found.text
    rows = [row for row in found.json()["items"] if row["phone"] == phone]
    assert rows, f"{phone} not found by search"
    return rows[0]


def test_an_admin_appoints_an_operator_and_nobody_else_can(
    client: TestClient,
    admin: dict[str, str],
    operator: dict[str, str],
    auth: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Until now a role came from a shell script, so a panel could list the
    operators and had no way to appoint one."""
    phone = "+998900040001"
    theirs = sign_in(phone)                      # an ordinary customer, for now
    account = _find_user(client, admin, phone)
    assert account["role"] == "customer"

    # Searching by the digits alone is enough — an admin has the number in
    # front of them, not a directory.
    assert _find_user(client, admin, phone)["id"] == account["id"]
    by_tail = client.get(f"{API}/staff/users", params={"q": "900040001"}, headers=admin)
    assert account["id"] in [row["id"] for row in by_tail.json()["items"]]

    body = {"role": "operator", "note": "yangi smena"}
    door = f"{API}/staff/users/{account['id']}/role"
    assert client.patch(door, json=body).status_code == 401
    assert client.patch(door, json=body, headers=auth).status_code == 403
    assert client.patch(door, json=body, headers=theirs).status_code == 403
    # Not even the role that runs the shop day to day: this is how somebody
    # would promote themselves.
    assert client.patch(door, json=body, headers=operator).status_code == 403

    done = client.patch(door, json=body, headers=admin)
    assert done.status_code == 200, done.text
    assert done.json()["role"] == "operator"

    # And the role is the whole of the difference — the same token now opens
    # the operator's door.
    assert client.get(f"{API}/staff/returns", headers=theirs).status_code == 200

    # A privilege change is the kind of thing asked about months later.
    rows = _audit_rows("user.role", account["id"])
    assert rows[-1].action == "user.role"
    assert (rows[-1].old_value, rows[-1].new_value) == ("customer", "operator")
    assert rows[-1].actor_role is UserRole.ADMIN
    assert rows[-1].note == "yangi smena"

    # Saving a form that changed nothing is not an error, and does not add a
    # row to a log that is meant to be a list of changes.
    again = client.patch(door, json={"role": "operator"}, headers=admin)
    assert again.status_code == 200
    assert len(_audit_rows("user.role", account["id"])) == len(rows)

    # Standing them down again is the same door.
    back = client.patch(door, json={"role": "customer"}, headers=admin)
    assert back.status_code == 200
    assert back.json()["role"] == "customer"
    assert client.get(f"{API}/staff/returns", headers=theirs).status_code == 403


def test_the_last_admin_cannot_be_stood_down(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The one privilege change that cannot be undone through the door it was
    made in: demote the last admin and there is nobody left who can hand the
    role back."""
    me = client.get(f"{API}/staff/me", headers=admin).json()
    door = f"{API}/staff/users/{me['id']}/role"

    refused = client.patch(door, json={"role": "operator"}, headers=admin)
    assert refused.status_code == 409, refused.text
    assert "admin" in refused.json()["detail"].lower()
    assert client.get(f"{API}/staff/me", headers=admin).json()["role"] == "admin"

    # With a second admin in place the same request is ordinary.
    phone = "+998900040002"
    theirs = sign_in(phone)
    second = _find_user(client, admin, phone)
    assert client.patch(
        f"{API}/staff/users/{second['id']}/role", json={"role": "admin"}, headers=admin
    ).status_code == 200

    stood_down = client.patch(door, json={"role": "operator"}, headers=theirs)
    assert stood_down.status_code == 200, stood_down.text
    assert stood_down.json()["role"] == "operator"

    # Put back by the admin who is left, which is the point of the rule.
    assert client.patch(
        door, json={"role": "admin"}, headers=theirs
    ).status_code == 200

    # And now the second one is the one who cannot go — whichever of them is
    # last is the one the rule protects.
    client.patch(
        f"{API}/staff/users/{second['id']}/role", json={"role": "customer"},
        headers=admin,
    )
    assert client.patch(
        door, json={"role": "operator"}, headers=admin
    ).status_code == 409


def test_a_role_a_seller_link_hands_out_obeys_the_same_rule(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Linking an account to a seller sets its role, so it is a second door on
    to the same rule and has to be guarded at the same place."""
    me = client.get(f"{API}/staff/me", headers=admin).json()
    seller = client.post(
        f"{API}/staff/sellers",
        json={"name": "Yakka Admin Savdo", "phone": "+998781119988"},
        headers=admin,
    ).json()

    # The last admin filling in a form about somebody else's shop would
    # otherwise demote themselves out of the panel.
    refused = client.patch(
        f"{API}/staff/sellers/{seller['id']}",
        json={"user_phone": me["phone"]},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    assert client.get(f"{API}/staff/me", headers=admin).json()["role"] == "admin"


# --------------------------------------------------------- a card in three languages


def _ru(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {**(headers or {}), "Accept-Language": "ru"}


def _en(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {**(headers or {}), "Accept-Language": "en"}


def _trilingual_card(client: TestClient, admin: dict[str, str]) -> dict:
    """A card written the way the panel writes one: all three languages, in the
    same request that creates the row."""
    category = client.post(
        f"{API}/staff/catalog/categories",
        json={
            "slug": "sinov-choynak",
            "name": "Choynaklar",
            "subtitle": "Choy uchun",
            "translations": {
                "ru": {"name": "Чайники", "subtitle": "Для чая"},
                "en": {"name": "Teapots", "subtitle": "For tea"},
            },
        },
        headers=admin,
    )
    assert category.status_code == 201, category.text

    brand = client.post(
        f"{API}/staff/catalog/brands",
        json={
            "slug": "sinov-hunarmand",
            "name": "Hunarmand",
            "translations": {"ru": {"name": "Ремесленник"}, "en": {"name": "Artisan"}},
        },
        headers=admin,
    )
    assert brand.status_code == 201, brand.text

    created = _admin_card(
        client,
        admin,
        sku="SINOV-I18N-1",
        title="Choynak",
        subtitle="Sopol choynak",
        description="Qo'lda yasalgan sopol choynak.",
        badge="Yangi",
        warranty="Kafolat 1 yil",
        category_slug="sinov-choynak",
        brand_slug="sinov-hunarmand",
        price=120_000,
        translations={
                "ru": {
                    "title": "Чайник",
                    "subtitle": "Керамический чайник",
                    "description": "Керамический чайник ручной работы.",
                    "badge": "Новинка",
                    "warranty": "Гарантия 1 год",
                },
                "en": {
                    "title": "Teapot",
                    "subtitle": "Ceramic teapot",
                    "description": "A hand-thrown ceramic teapot.",
                    "badge": "New",
                    "warranty": "1-year warranty",
                },
        },
    )
    product = created

    variant = client.post(
        f"{API}/staff/catalog/products/{product['id']}/variants",
        json={
            "kind": "color",
            "label": "Ko'k",
            "value": "#2E5AAC",
            "translations": {"ru": {"label": "Синий"}, "en": {"label": "Blue"}},
        },
        headers=admin,
    )
    assert variant.status_code == 201, variant.text

    specs = client.put(
        f"{API}/staff/catalog/products/{product['id']}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {
                        "ru": {"key": "Материал", "value": "Керамика"},
                        "en": {"key": "Material", "value": "Ceramic"},
                    },
                }
            ]
        },
        headers=admin,
    )
    assert specs.status_code == 200, specs.text

    _set_status(product["id"], ProductStatus.PUBLISHED)
    return product


def test_a_card_written_in_three_languages_answers_in_all_three(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The table has always been read. Until now nothing could write to it, so
    every card added after the seed made the catalogue a little more Uzbek than
    the app claims it is."""
    product = _trilingual_card(client, admin)
    url = f"{API}/products/{product['id']}"

    uz = client.get(url).json()
    assert (uz["title"], uz["subtitle"]) == ("Choynak", "Sopol choynak")
    assert uz["description"].startswith("Qo'lda")
    assert (uz["badge"], uz["warranty"]) == ("Yangi", "Kafolat 1 yil")
    assert uz["category"]["name"] == "Choynaklar"
    assert uz["brand"]["name"] == "Hunarmand"
    assert uz["variants"][0]["label"] == "Ko'k"
    assert (uz["specs"][0]["key"], uz["specs"][0]["value"]) == ("Material", "Sopol")

    ru = client.get(url, headers=_ru()).json()
    assert (ru["title"], ru["subtitle"]) == ("Чайник", "Керамический чайник")
    assert ru["description"] == "Керамический чайник ручной работы."
    assert (ru["badge"], ru["warranty"]) == ("Новинка", "Гарантия 1 год")
    assert ru["category"]["name"] == "Чайники"
    assert ru["brand"]["name"] == "Ремесленник"
    assert ru["variants"][0]["label"] == "Синий"
    assert (ru["specs"][0]["key"], ru["specs"][0]["value"]) == ("Материал", "Керамика")

    en = client.get(url, headers=_en()).json()
    assert (en["title"], en["brand"]["name"]) == ("Teapot", "Artisan")
    assert en["specs"][0]["value"] == "Ceramic"

    # The value the row itself holds is untouched: the panel edits Uzbek, and
    # sees Uzbek.
    card = client.get(
        f"{API}/staff/catalog/products/{product['id']}", headers=_ru(admin)
    ).json()
    assert card["title"] == "Choynak"

    # A listing carries the translation too, not only the product page.
    # Nothing has been booked in against this card, so the grid is asked for
    # what it normally hides.
    listing = client.get(
        f"{API}/products",
        params={"category": "sinov-choynak", "show_sold_out": True},
        headers=_ru(),
    ).json()
    assert [row["title"] for row in listing["items"]] == ["Чайник"]


def test_a_card_with_no_translation_is_uzbek_in_every_language(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The fallback is what makes a partly translated catalogue usable: a card
    written by somebody in a hurry degrades to Uzbek, not to blanks."""
    product = _admin_card(
        client,
        admin,
        sku="SINOV-I18N-2",
        title="Tarjimasiz kartochka",
        subtitle="Faqat o'zbekcha",
        price=90_000,
        status=ProductStatus.PUBLISHED,
    )

    for headers in ({}, _ru(), _en()):
        body = client.get(f"{API}/products/{product['id']}", headers=headers).json()
        assert body["title"] == "Tarjimasiz kartochka"
        assert body["subtitle"] == "Faqat o'zbekcha"


def test_a_translation_can_be_read_back_and_taken_away(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The catalogue endpoints answer in one language and fall back silently,
    which is right for a shopper and no use to an editor trying to see what is
    still missing."""
    product = _admin_card(
        client,
        admin,
        sku="SINOV-I18N-3",
        title="Piyola",
        price=30_000,
        status=ProductStatus.PUBLISHED,
        translations={"ru": {"title": "Пиала"}},
    )
    door = f"{API}/staff/catalog/translations/product/{product['id']}"

    held = client.get(door, headers=admin)
    assert held.status_code == 200, held.text
    assert held.json()["uz"]["title"] == "Piyola"
    assert held.json()["translations"]["ru"]["title"] == "Пиала"
    assert "en" not in held.json()["translations"]

    # A field left out of the payload is left alone; the English arriving
    # later does not wipe the Russian that was already there.
    client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"en": {"title": "Tea bowl"}}},
        headers=admin,
    )
    assert client.get(door, headers=admin).json()["translations"] == {
        "ru": {"title": "Пиала"},
        "en": {"title": "Tea bowl"},
    }

    # Blank is not the same as absent: it takes the row away, and the card
    # falls back to its Uzbek again.
    client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"ru": {"title": ""}}},
        headers=admin,
    )
    assert "ru" not in client.get(door, headers=admin).json()["translations"]
    assert client.get(
        f"{API}/products/{product['id']}", headers=_ru()
    ).json()["title"] == "Piyola"

    # A field the shape does not have is a bug in the caller, not a silent
    # no-op that shows up months later as a card nobody translated.
    assert client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"ru": {"nomi": "Пиала"}}},
        headers=admin,
    ).status_code == 422
    assert client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"de": {"title": "Teeschale"}}},
        headers=admin,
    ).status_code == 422
    # Uzbek is the row itself, and is not written here.
    assert client.get(door).status_code == 401


def test_a_replaced_spec_table_does_not_inherit_the_old_rows_words(
    client: TestClient, admin: dict[str, str]
) -> None:
    """SQLite hands a deleted row's id straight back out, so a spec table
    replaced in place would arrive in Russian describing something else."""
    product = _admin_card(
        client,
        admin,
        sku="SINOV-I18N-4",
        title="Likobcha",
        price=20_000,
        status=ProductStatus.PUBLISHED,
    )
    specs_url = f"{API}/staff/catalog/products/{product['id']}/specs"

    client.put(
        specs_url,
        json={
            "specs": [
                {
                    "key": "Rang",
                    "value": "Oq",
                    "translations": {"ru": {"key": "Цвет", "value": "Белый"}},
                }
            ]
        },
        headers=admin,
    )
    client.put(
        specs_url,
        json={"specs": [{"key": "Og'irlik", "value": "300 g"}]},
        headers=admin,
    )

    ru = client.get(f"{API}/products/{product['id']}", headers=_ru()).json()
    assert [(s["key"], s["value"]) for s in ru["specs"]] == [("Og'irlik", "300 g")]


# --------------------------------------------------------- photographs


def _photograph(width: int, height: int, fmt: str = "JPEG") -> bytes:
    """A picture of the size a phone actually takes one."""
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (width, height))
    for x in range(0, width, 7):
        for y in range(0, height, 11):
            image.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, (x + y) % 256))
    buffer = BytesIO()
    image.save(buffer, fmt, quality=95)
    return buffer.getvalue()


def test_a_photograph_is_re_encoded_shrunk_and_renamed(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The catalogue's pictures are 169–641 px. What arrives from a phone is
    four megabytes and four thousand pixels across, under a name of its
    own."""
    from io import BytesIO

    from PIL import Image

    from app.images import MEDIA_DIR

    original = _photograph(4000, 3000)
    sent = client.post(
        f"{API}/staff/media",
        files={"file": ("IMG_20260907_113045.jpg", original, "image/jpeg")},
        headers=admin,
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()

    # Shrunk on its long side, and the shape kept.
    assert (body["width"], body["height"]) == (1600, 1200)
    assert body["bytes"] < len(original)

    # Named by us. Nothing of what the uploader called it survives.
    assert body["media_url"].startswith("uploads/")
    assert body["media_url"].endswith(".webp")
    assert "IMG_20260907" not in body["media_url"]

    # Written where the existing StaticFiles mount already serves, and in the
    # format we chose rather than the one that was sent.
    on_disk = MEDIA_DIR / body["media_url"]
    assert on_disk.is_file()
    with Image.open(BytesIO(on_disk.read_bytes())) as written:
        assert written.format == "WEBP"
        assert written.size == (1600, 1200)
    assert client.get(f"/media/{body['media_url']}").status_code == 200

    # And the path is the shape the rest of the catalogue already stores, so
    # it goes straight back as a product image.
    product = _admin_card(
        client, admin, sku="SINOV-MEDIA-1", title="Suratli kartochka", price=55_000
    )
    attached = client.post(
        f"{API}/staff/catalog/products/{product['id']}/images",
        json={"url": body["media_url"]},
        headers=admin,
    )
    assert attached.status_code == 201, attached.text
    assert attached.json() == [body["media_url"]]

    # A picture already inside the box is re-encoded but never enlarged.
    small = client.post(
        f"{API}/staff/media",
        files={"file": ("swatch.png", _photograph(640, 640, "PNG"), "image/png")},
        headers=admin,
    ).json()
    assert (small["width"], small["height"]) == (640, 640)


def test_a_file_that_is_not_an_image_is_refused_however_it_is_named(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The name, the extension and the declared type are all the uploader's to
    write. The bytes are the only honest part of the request."""
    refused = client.post(
        f"{API}/staff/media",
        files={"file": ("photo.jpg", b"#!/bin/sh\necho not a picture\n", "image/jpeg")},
        headers=admin,
    )
    assert refused.status_code == 415, refused.text
    assert refused.json()["detail"]

    # Nor does a real image header make the rest of the file an image.
    truncated = _photograph(320, 240)[:40]
    assert client.post(
        f"{API}/staff/media",
        files={"file": ("half.jpg", truncated, "image/jpeg")},
        headers=admin,
    ).status_code == 415

    assert client.post(
        f"{API}/staff/media",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        headers=admin,
    ).status_code == 400


def test_a_file_over_the_limit_is_refused_before_it_is_read(
    client: TestClient, admin: dict[str, str]
) -> None:
    from app.images import MAX_BYTES

    too_big = b"\xff\xd8\xff\xe0" + b"\x00" * (MAX_BYTES + 1024)
    refused = client.post(
        f"{API}/staff/media",
        files={"file": ("huge.jpg", too_big, "image/jpeg")},
        headers=admin,
    )
    assert refused.status_code == 413, refused.text
    assert "8" in refused.json()["detail"], "the limit is named, not just refused"


def test_only_the_people_who_write_cards_may_upload_a_picture(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A seller photographs the goods they propose, so uploading is theirs as
    well as the admin's — and nobody else's."""
    seller = staff(UserRole.SELLER, "+998900040011")
    picture = _photograph(200, 200)

    def send(headers: dict[str, str] | None) -> int:
        return client.post(
            f"{API}/staff/media",
            files={"file": ("a.jpg", picture, "image/jpeg")},
            headers=headers or {},
        ).status_code

    assert send(None) == 401
    assert send(auth) == 403
    assert send(operator) == 403
    assert send(seller) == 201
    assert send(admin) == 201


# --------------------------------------------------------- what the editor reads


def test_the_admin_lists_answer_in_the_words_the_rows_hold(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The customer endpoints translate as they go, which is right for the app
    and wrong for the field that writes the source: an editor working in
    Russian would be shown the translation and save it back as the Uzbek."""
    client.post(
        f"{API}/staff/catalog/categories",
        json={
            "slug": "sinov-admin-turkum",
            "name": "Sinov turkumi",
            "subtitle": "izohi",
            "translations": {"ru": {"name": "Тестовая категория"}},
        },
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/brands",
        json={
            "slug": "sinov-admin-brend",
            "name": "Sinov Brend",
            "translations": {"ru": {"name": "Тестовый бренд"}},
        },
        headers=admin,
    )

    # The shopper's list, asked for in Russian, answers in Russian.
    shopper = client.get(f"{API}/brands", headers=_ru()).json()
    assert "Тестовый бренд" in [row["name"] for row in shopper]

    # The editor's list, asked for in Russian, answers with the row itself.
    brands = client.get(f"{API}/staff/catalog/brands", headers=_ru(admin))
    assert brands.status_code == 200, brands.text
    mine = next(row for row in brands.json() if row["slug"] == "sinov-admin-brend")
    assert mine["name"] == "Sinov Brend"

    categories = client.get(f"{API}/staff/catalog/categories", headers=_ru(admin))
    assert categories.status_code == 200, categories.text
    row = next(r for r in categories.json() if r["slug"] == "sinov-admin-turkum")
    assert (row["name"], row["subtitle"]) == ("Sinov turkumi", "izohi")

    # Flat, and the tree recoverable from parent_slug — a child of the seeded
    # root reports which root it hangs from.
    slugs = {r["slug"] for r in categories.json()}
    assert len(slugs) > len(client.get(f"{API}/categories").json()), "children too"
    assert any(r["parent_slug"] for r in categories.json())

    # Nobody else's list.
    assert client.get(f"{API}/staff/catalog/brands").status_code == 401


def test_the_admin_lists_carry_the_counts_that_explain_a_refusal(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`GET /brands` sends `product_count: 0` for every row — the figure is
    only computed in `/products/filters`, scoped to one listing. Here it is the
    whole catalogue, and it is the answer to "why can't I delete this"."""
    client.post(
        f"{API}/staff/catalog/categories",
        json={"slug": "sinov-sanoq", "name": "Sanoq turkumi"},
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-brend", "name": "Sanoq Brend"},
        headers=admin,
    )

    def counts() -> tuple[int, int]:
        category = next(
            r
            for r in client.get(f"{API}/staff/catalog/categories", headers=admin).json()
            if r["slug"] == "sinov-sanoq"
        )
        brand = next(
            r
            for r in client.get(f"{API}/staff/catalog/brands", headers=admin).json()
            if r["slug"] == "sinov-sanoq-brend"
        )
        return category["product_count"], brand["product_count"]

    assert counts() == (0, 0)
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-sanoq-brend", headers=admin
    ).status_code == 200

    # Written again, this time with a card against it.
    client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-brend", "name": "Sanoq Brend"},
        headers=admin,
    )
    _admin_card(
        client,
        admin,
        sku="SINOV-SANOQ-1",
        title="Sanoq kartochkasi",
        category_slug="sinov-sanoq",
        brand_slug="sinov-sanoq-brend",
        price=40_000,
    )
    assert counts() == (1, 1)

    # And the count is exactly why the delete is refused.
    assert client.delete(
        f"{API}/staff/catalog/categories/sinov-sanoq", headers=admin
    ).status_code == 409
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-sanoq-brend", headers=admin
    ).status_code == 409


def test_the_queue_can_be_counted_without_fetching_it(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The sidebar says "3 waiting" on every screen. Fetching the queue to
    render an integer would be a page of cards downloaded each time."""
    before = client.get(f"{API}/staff/catalog/summary", headers=admin)
    assert before.status_code == 200, before.text
    waiting = before.json()["counts"]["moderating"]

    listing = client.get(f"{API}/categories").json()
    made = client.post(
        f"{API}/staff/catalog/proposals",
        json={
            "sku": "SINOV-QUEUE-1",
            "title": "Navbat kartochkasi",
            "category_slug": listing[0]["slug"],
            "price": 30_000,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text

    after = client.get(f"{API}/staff/catalog/summary", headers=admin).json()
    assert after["counts"]["moderating"] == waiting + 1
    # Every state is named, so a zero is a zero rather than a missing key.
    assert set(after["counts"]) == {
        "draft", "moderating", "published", "rejected", "archived",
    }

    _set_status(made.json()["id"], ProductStatus.PUBLISHED)
    assert (
        client.get(f"{API}/staff/catalog/summary", headers=admin).json()["counts"][
            "moderating"
        ]
        == waiting
    )
    assert client.get(f"{API}/staff/catalog/summary").status_code == 401


def test_a_draft_card_can_be_read_back_in_full_to_be_edited(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A draft is invisible through `/products/{id}` — that path is narrowed to
    what is in the shop, which is the point of it. So until now nothing could
    read back the description, the photographs, the colours or the specs of a
    card that had not been published, and an edit form had nothing to open."""
    made = _admin_card(
        client,
        admin,
        sku="SINOV-EDIT-1",
        title="Tahrir kartochkasi",
        subtitle="qoralama",
        description="Uzun tavsif matni.",
        badge="Yangi",
        warranty="Kafolat 1 yil",
        price=60_000,
        translations={"ru": {"title": "Карточка", "description": "Описание."}},
    )
    product_id = made["id"]

    # The draft is not in the shop, and reading it there says so.
    assert client.get(f"{API}/products/{product_id}").status_code == 404

    card = client.get(f"{API}/staff/catalog/products/{product_id}", headers=admin)
    assert card.status_code == 200, card.text
    body = card.json()
    assert body["description"] == "Uzun tavsif matni."
    assert (body["badge"], body["warranty"]) == ("Yangi", "Kafolat 1 yil")
    assert body["is_original"] is True
    # Every language at once, so the editor can mark the empty cells.
    assert body["translations"]["ru"]["title"] == "Карточка"
    assert "en" not in body["translations"]

    # The list shape stays lean — a description per row is prose fetched to
    # draw a table.
    page = client.get(
        f"{API}/staff/catalog/products", params={"q": "SINOV-EDIT-1"}, headers=admin
    ).json()
    assert "description" not in page["items"][0]

    specs = client.put(
        f"{API}/staff/catalog/products/{product_id}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {"ru": {"key": "Материал"}},
                }
            ]
        },
        headers=admin,
    )
    assert specs.status_code == 200, specs.text
    read_back = client.get(
        f"{API}/staff/catalog/products/{product_id}/specs", headers=admin
    )
    assert read_back.status_code == 200, read_back.text
    assert [(r["key"], r["value"]) for r in read_back.json()] == [("Material", "Sopol")]

    # With the Russian on the row. The table is only ever replaced whole, so a
    # form that could not read this back would delete it by saving an
    # unrelated row.
    assert read_back.json()[0]["translations"]["ru"]["key"] == "Материал"

    # Saving the table again, carrying the translation with it, keeps it.
    client.put(
        f"{API}/staff/catalog/products/{product_id}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {"ru": {"key": "Материал"}},
                },
                {"key": "Vazn", "value": "300 g"},
            ]
        },
        headers=admin,
    )
    again = client.get(
        f"{API}/staff/catalog/products/{product_id}/specs", headers=admin
    ).json()
    assert [r["key"] for r in again] == ["Material", "Vazn"]
    assert again[0]["translations"]["ru"]["key"] == "Материал"
    # And the new row inherits nothing from whatever held its id before.
    assert again[1]["translations"] == {}


def test_photographs_can_be_reordered_because_the_ids_are_readable(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`DELETE .../images/{image_id}` has always existed and nothing ever told
    the panel what `image_id` was — the write endpoints answer with bare URLs,
    which redraws a gallery and cannot edit one."""
    product_id = _write_a_card(
        sku="SINOV-RASM-1", title="Rasmli kartochka", price=70_000
    )

    for index, name in enumerate(("bir.png", "ikki.png", "uch.png")):
        client.post(
            f"{API}/staff/catalog/products/{product_id}/images",
            json={"url": f"products/{name}", "sort": index},
            headers=admin,
        )

    images = client.get(
        f"{API}/staff/catalog/products/{product_id}/images", headers=admin
    )
    assert images.status_code == 200, images.text
    rows = images.json()
    assert [r["url"] for r in rows] == ["products/bir.png", "products/ikki.png", "products/uch.png"]
    assert all(isinstance(r["id"], int) for r in rows)

    door = f"{API}/staff/catalog/products/{product_id}/images/order"
    flipped = [rows[2]["id"], rows[0]["id"], rows[1]["id"]]
    moved = client.put(door, json={"ids": flipped}, headers=admin)
    assert moved.status_code == 200, moved.text
    assert [r["url"] for r in moved.json()] == [
        "products/uch.png", "products/bir.png", "products/ikki.png"
    ]

    # The whole list or nothing: a partial order would leave the rest holding
    # numbers that mean something else.
    assert client.put(
        door, json={"ids": [rows[0]["id"]]}, headers=admin
    ).status_code == 400
    assert client.put(
        door, json={"ids": [rows[0]["id"], rows[0]["id"], rows[1]["id"]]}, headers=admin
    ).status_code == 400

    # The first photograph is the cover, so the order reaches the shop.
    _set_status(product_id, ProductStatus.PUBLISHED)
    assert client.get(f"{API}/products/{product_id}").json()["images"][0] == "products/uch.png"

    # And an id read here is the id the delete takes.
    gone = client.delete(
        f"{API}/staff/catalog/products/{product_id}/images/{rows[0]['id']}",
        headers=admin,
    )
    assert gone.status_code == 200
    assert len(client.get(
        f"{API}/staff/catalog/products/{product_id}/images", headers=admin
    ).json()) == 2


def test_the_editor_is_told_what_it_may_not_do_before_it_tries(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Both guards come from the functions the write endpoints refuse with, so
    a greyed-out button and a 409 are the same rule rather than two copies of
    it that drift."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030051")
    door = f"{API}/staff/catalog/products"

    # A colour with nothing against it yet: deletable, and the tree can still
    # change shape.
    product_id, colour_id = _card_with_a_colour(
        client, admin, "MB-GUARD-1", with_a_size=False
    )
    open_ = client.get(f"{door}/{product_id}/variants", headers=admin)
    assert open_.status_code == 200, open_.text
    assert open_.json()["can_add_size"] is True
    assert open_.json()["size_blocked_reason"] == ""
    colour = next(v for v in open_.json()["variants"] if v["id"] == colour_id)
    assert colour["can_delete"] is True and colour["blocked_reason"] == ""

    # Stock arrives on the colour. Now a first size would move where the shelf
    # is counted, and the editor is told so rather than finding out.
    _stock_a_leaf(client, admin, warehouse, product_id, colour_id, 4)
    stocked = client.get(f"{door}/{product_id}/variants", headers=admin).json()
    assert stocked["can_add_size"] is False
    assert "sanoq" in stocked["size_blocked_reason"]

    # And it is the same sentence the write endpoint refuses with.
    refused = client.post(
        f"{door}/{product_id}/variants",
        json={"kind": "size", "label": "M", "value": "M", "parent_id": colour_id},
        headers=admin,
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == stocked["size_blocked_reason"]

    # The movement against the colour also makes it undeletable, and says why.
    blocked = next(v for v in stocked["variants"] if v["id"] == colour_id)
    assert blocked["can_delete"] is False
    assert "harakat" in blocked["blocked_reason"]
    gone = client.delete(f"{door}/{product_id}/variants/{colour_id}", headers=admin)
    assert gone.status_code == 409
    assert gone.json()["detail"] == blocked["blocked_reason"]

    # A colour holding sizes is blocked for a different reason, and says that
    # one instead.
    parent_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-GUARD-2", with_a_size=True
    )
    tree = client.get(f"{door}/{parent_id}/variants", headers=admin).json()
    colour_row = next(v for v in tree["variants"] if v["kind"] == "color")
    assert colour_row["can_delete"] is False
    assert "o'lcham" in colour_row["blocked_reason"]
    # Its size is a leaf with nothing against it, so that one may go.
    assert next(v for v in tree["variants"] if v["id"] == leaf_id)["can_delete"] is True
    assert not _stock_is_consistent()


# --------------------------------------------------------- paying the sellers


def _period(
    client: TestClient, admin: dict[str, str], *, starts: str, ends: str, label: str
) -> dict:
    made = client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": starts, "ends_on": ends, "label": label},
        headers=admin,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _statement(
    client: TestClient, admin: dict[str, str], period_id: int, seller_id: int
) -> dict:
    """Generate the run and return this seller's account, with its lines."""
    made = client.post(
        f"{API}/staff/payouts/periods/{period_id}/generate", headers=admin
    )
    assert made.status_code == 200, made.text
    mine = next(row for row in made.json() if row["seller_id"] == seller_id)
    full = client.get(f"{API}/staff/payouts/statements/{mine['id']}", headers=admin)
    assert full.status_code == 200, full.text
    return full.json()


def _sell_and_deliver(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    warehouse: dict[str, str],
    *,
    seller_id: int,
    product_id: int,
    price: int,
    quantity: int = 1,
) -> dict:
    """One order for this seller's goods, carried all the way to the door.

    A sale only counts once it is delivered — a placed order may be called off
    and a cash order is not paid until the doorstep — so every one of these
    walks the whole flow.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    offer = client.post(
        f"{API}/staff/offers",
        json={
            "product_id": product_id,
            "price": price,
            "seller_id": seller_id,
            "variant_ids": leaves,
        },
        headers=admin,
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    supply = client.post(
        f"{API}/staff/supplies",
        json={
            "seller_id": seller_id,
            "lines": [
                {
                    "offer_id": offer_id,
                    **({"variant_id": leaves[0]} if leaves else {}),
                    "quantity": quantity + 2,
                }
            ],
        },
        headers=admin,
    )
    assert supply.status_code == 201, supply.text
    client.post(
        f"{API}/staff/supplies/{supply.json()['id']}/receive",
        json={
            "lines": [
                {
                    "line_id": supply.json()["lines"][0]["id"],
                    "received_quantity": quantity + 2,
                }
            ]
        },
        headers=warehouse,
    )

    client.delete(f"{API}/cart", headers=auth)
    # `_pick` names the leaf the way the apps do, and this card has exactly
    # one offer — the seller's — so that is the one the cart takes.
    added = client.post(
        f"{API}/cart/items", json=_pick(product_id, quantity), headers=auth
    )
    assert added.status_code == 201, added.text

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert order.status_code == 201, order.text
    order = order.json()
    _to_the_door(client, operator, order["id"])
    return order


def _lines(statement: dict, kind: str) -> list[dict]:
    return [line for line in statement["lines"] if line["kind"] == kind]


def test_a_sellers_two_orders_add_up_to_one_account(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Nobody was being paid. Everything the arithmetic needed was captured on
    the order line and nothing added it up."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060001")
    seller_id, theirs = _linked_seller(staff, "Payout Bir", "+998900060002", commission=10)

    first_id, _ = _card_with_a_colour(client, admin, "MB-PAY-1", with_a_size=False)
    second_id, _ = _card_with_a_colour(client, admin, "MB-PAY-2", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=first_id, price=500_000,
    )
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=second_id, price=300_000, quantity=2,
    )

    # Its own window. Periods may not overlap — one sale falling into two
    # runs is the thing that guard exists for — and every test here shares
    # one database. A period's start date does not filter sales (see
    # `_sale_lines`: anything delivered by the closing day and not yet
    # settled belongs to it), so a far window still picks up today's sale.
    period = _period(
        client, admin, starts="2040-01-01", ends="2040-12-31", label="Sinov davri"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    # 500 000 + 2 × 300 000, and the commission is the rate on the line.
    assert statement["gross_sales"] == 1_100_000
    assert statement["commission"] == 110_000
    assert statement["seller_name"] == "Payout Bir"

    # The figure is the sum of its rows, the way the shelf is the sum of its
    # movements. A total that can drift from its own composition is the thing
    # this model exists to prevent.
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert (
        statement["payable"]
        == statement["gross_sales"]
        - statement["commission"]
        - statement["fulfilment"]
        - statement["refunds"]
        - statement["storage"]
        + statement["adjustments"]
    )

    # Every line names what it came from. "9 100 000" is a number to argue
    # with; this is an account to read.
    sales = _lines(statement, "sale")
    assert len(sales) == 2
    assert all(line["order_item_id"] for line in sales)
    assert all(line["title"].startswith("#") for line in sales)
    for line in _lines(statement, "commission"):
        assert "10%" in line["note"]
        assert line["order_item_id"]

    # The seller reads their own account, and only their own.
    theirs_view = client.get(f"{API}/staff/payouts/statements", headers=theirs)
    assert theirs_view.status_code == 200, theirs_view.text
    assert {row["seller_id"] for row in theirs_view.json()} == {seller_id}
    assert client.get(
        f"{API}/staff/payouts/statements/{statement['id']}", headers=theirs
    ).status_code == 200
    assert client.get(f"{API}/staff/payouts/periods", headers=theirs).status_code == 403
    assert not _stock_is_consistent()


def test_the_commission_is_the_rate_it_was_sold_at_not_todays(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A payout computed against today's rate would quietly restate what
    somebody was owed for something they sold last year."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060011")
    seller_id, _ = _linked_seller(staff, "Payout Ikki", "+998900060012", commission=8)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-3", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=1_000_000,
    )

    past = _period(
        client, admin, starts="2019-01-01", ends="2019-12-31", label="Bo'sh"
    )
    # A period that closes before the sale happened sees nothing of it — not
    # the sale, and not a day of storage either.
    empty = _statement(client, admin, past["id"], seller_id)
    assert (empty["gross_sales"], empty["storage"], empty["payable"]) == (0, 0, 0)

    wide = _period(
        client, admin, starts="2041-01-01", ends="2041-12-31", label="Keng"
    )
    before = _statement(client, admin, wide["id"], seller_id)
    assert before["commission"] == 80_000

    # The contract is renegotiated upwards. What was already sold keeps the
    # rate it was sold at.
    changed = client.patch(
        f"{API}/staff/sellers/{seller_id}", json={"commission_percent": 25}, headers=admin
    )
    assert changed.status_code == 200, changed.text
    after = _statement(client, admin, wide["id"], seller_id)
    assert after["commission"] == 80_000, "the snapshot, not the seller row"
    assert "8%" in _lines(after, "commission")[0]["note"]
    assert not _stock_is_consistent()


def test_a_cheap_item_costs_more_to_handle_than_it_earns_in_commission(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The reason there are two fees at all.

    Five per cent of the catalogue's cheapest card is 1 950 so'm against a
    Tashkent delivery that costs many times that; five per cent of its dearest
    is 9 100 000 for carrying one small box the same distance. A single
    percentage is a loss at one end and an embarrassment at the other.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900060021")
    seller_id, _ = _linked_seller(staff, "Payout Uch", "+998900060022", commission=5)

    cheap_id, _ = _card_with_a_colour(client, admin, "MB-PAY-CHEAP", with_a_size=False)
    dear_id, _ = _card_with_a_colour(client, admin, "MB-PAY-DEAR", with_a_size=False)
    # Both light — a phone accessory and a watch weigh about the same, which
    # is exactly why the fee cannot follow the price.
    with Session(engine) as session:
        for product_id in (cheap_id, dear_id):
            row = session.get(Product, product_id)
            row.weight_grams = 300
            session.add(row)
        session.commit()

    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=cheap_id, price=39_000,
    )
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=dear_id, price=182_000_000,
    )

    period = _period(
        client, admin, starts="2042-01-01", ends="2042-12-31", label="Ikki haq"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    handling = {
        line["order_item_id"]: -line["amount"] for line in _lines(statement, "fulfilment")
    }
    commission = {
        line["order_item_id"]: -line["amount"] for line in _lines(statement, "commission")
    }
    sales = {line["order_item_id"]: line["amount"] for line in _lines(statement, "sale")}

    cheap = next(item for item, gross in sales.items() if gross == 39_000)
    dear = next(item for item, gross in sales.items() if gross == 182_000_000)

    # The whole point, in one assertion: on the cheap card the handling fee is
    # the larger of the two, and on the dear one it is a rounding error.
    assert handling[cheap] > commission[cheap], (handling[cheap], commission[cheap])
    assert commission[cheap] == 1_950
    assert handling[dear] < commission[dear] // 1000

    # Same weight, same handling fee — it does not follow the price.
    assert handling[cheap] == handling[dear]

    # And it is visible in the statement rather than buried in a net figure.
    assert statement["fulfilment"] == handling[cheap] + handling[dear]
    assert "yig'ish va yetkazish" in _lines(statement, "fulfilment")[0]["note"]
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert not _stock_is_consistent()


def test_a_refund_comes_off_the_account_and_gives_the_commission_back(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refunded sale was never a sale, so keeping our cut of it would be
    charging for something that did not happen. The van still came, though, so
    the handling fee is not given back."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060031")
    seller_id, _ = _linked_seller(staff, "Payout To'rt", "+998900060032", commission=10)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-4", with_a_size=False)
    order = _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=400_000,
    )

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "O'lchami to'g'ri kelmadi"},
        headers=auth,
    ).json()
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Butun holida qaytdi"},
        headers=operator,
    )
    assert refunded.status_code == 200, refunded.text

    period = _period(
        client, admin, starts="2043-01-01", ends="2043-12-31", label="Qaytarish"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    # Sold, and unsold. The refund deduction is the goods less the commission
    # we handed back — exactly what the seller had received for it.
    assert statement["gross_sales"] == 400_000
    assert statement["commission"] == 40_000
    assert statement["refunds"] == 360_000

    back = _lines(statement, "refund")
    assert back and all(line["return_request_id"] == request["id"] for line in back)
    assert all(line["amount"] == -400_000 for line in back)
    given = _lines(statement, "refund_commission")
    assert [line["amount"] for line in given] == [40_000]
    assert "komissiya olinmaydi" in given[0]["note"]

    # The handling fee stays deducted: it was really spent.
    assert statement["fulfilment"] > 0
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    # Nothing left of the sale but the cost of having shipped it.
    assert statement["payable"] == -statement["fulfilment"] - statement["storage"]
    assert not _stock_is_consistent()


def test_a_refund_after_the_period_closed_lands_in_the_next_one(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A seller who reads what they are owed and is shown a different number
    next week has been told the first number was provisional — which makes
    every number provisional."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060041")
    seller_id, _ = _linked_seller(staff, "Payout Besh", "+998900060042", commission=10)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-5", with_a_size=False)
    order = _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=700_000,
    )

    first = _period(
        client, admin, starts="2044-01-01", ends="2044-12-31", label="Birinchi"
    )
    before = _statement(client, admin, first["id"], seller_id)
    assert before["gross_sales"] == 700_000
    assert before["refunds"] == 0
    settled = before["payable"]

    closed = client.post(
        f"{API}/staff/payouts/periods/{first['id']}/close", headers=admin
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    # The refund arrives afterwards.
    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Kechikkan qaytarish"},
        headers=auth,
    ).json()
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Davr yopilgandan keyin"},
        headers=operator,
    )

    # The closed account is untouched — the same figure the seller read.
    frozen = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    ).json()
    assert frozen["payable"] == settled
    assert frozen["refunds"] == 0
    assert frozen["gross_sales"] == 700_000

    # A closed period will not be regenerated, and refuses to be reclosed.
    assert client.post(
        f"{API}/staff/payouts/periods/{first['id']}/generate", headers=admin
    ).status_code == 409
    assert client.post(
        f"{API}/staff/payouts/periods/{first['id']}/close", headers=admin
    ).status_code == 409

    # It lands in the next one instead, and the sale is not counted twice.
    second = _period(
        client, admin, starts="2045-01-01", ends="2045-12-31", label="Ikkinchi"
    )
    later = _statement(client, admin, second["id"], seller_id)
    assert later["refunds"] == 630_000, later
    assert later["gross_sales"] == 0, "the sale was settled in the closed period"
    assert later["payable"] == sum(line["amount"] for line in later["lines"])
    assert later["payable"] < 0, "a period of refunds alone is a debt, not a zero"
    assert not _stock_is_consistent()


def test_storage_is_charged_per_unit_day_and_surcharged_when_nothing_moves(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The only mechanism here that empties a shelf. Without a standing cost
    the warehouse is a free storage unit, and the way to use one is to send
    everything and let somebody else hold it."""
    from datetime import timedelta

    from app import settlement as settle
    from app.models import StockMovement

    warehouse = staff(UserRole.WAREHOUSE, "+998900060051")
    seller_id, _ = _linked_seller(staff, "Payout Olti", "+998900060052")
    product_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-PAY-6", with_a_size=False
    )
    _stock_a_leaf(client, admin, warehouse, product_id, leaf_id, 4)

    with Session(engine) as session:
        offer = session.exec(
            select(Offer).where(
                Offer.product_id == product_id, Offer.seller_id != seller_id
            )
        ).first()
        # Hand the stocked offer to our seller so the storage lands on them.
        offer.seller_id = seller_id
        session.add(offer)
        # And date the intake far enough back that it counts as stale.
        movements = session.exec(
            select(StockMovement).where(StockMovement.offer_id == offer.id)
        ).all()
        old = utcnow() - timedelta(days=settle.STALE_AFTER_DAYS + 40)
        for movement in movements:
            movement.created_at = old
            session.add(movement)
        session.commit()
        offer_id = offer.id

    starts = (utcnow() - timedelta(days=9)).date()
    ends = (utcnow() - timedelta(days=1)).date()
    period = _period(
        client, admin, starts=str(starts), ends=str(ends), label="Saqlash"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    rows = [line for line in _lines(statement, "storage") if line["offer_id"] == offer_id]
    assert rows, statement["lines"]
    row = rows[0]
    days = (ends - starts).days + 1
    # The rate is the weight band's, not a flat number: a washing machine and
    # a pair of earphones do not occupy the same warehouse.
    with Session(engine) as session:
        rate = settle.storage_rate(session, session.get(Product, product_id))
    expected = 4 * days * rate * settle.STALE_MULTIPLIER
    assert -row["amount"] == expected, (row, expected)

    # The sum in words, so a seller can check it rather than only dispute it.
    assert f"{4 * days} dona-kun" in row["note"]
    assert f"{settle.STALE_MULTIPLIER}×" in row["note"]
    assert "harakatsiz" in row["note"]
    assert statement["storage"] >= expected
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert not _stock_is_consistent()


def test_a_payout_is_marked_paid_once_with_a_date_and_a_reference(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two transfers against one account is money gone that nobody notices
    until the seller who was not paid rings up."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060061")
    seller_id, theirs = _linked_seller(staff, "Payout Yetti", "+998900060062")
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-7", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=900_000,
    )

    period = _period(
        client, admin, starts="2046-01-01", ends="2046-12-31", label="To'lov"
    )
    statement = _statement(client, admin, period["id"], seller_id)
    door = f"{API}/staff/payouts/statements/{statement['id']}"
    body = {"method": "bank o'tkazmasi", "reference": "TR-99001", "note": "Oylik"}

    # An open account cannot be paid: the figure is still being recomputed.
    assert client.post(f"{door}/pay", json=body, headers=admin).status_code == 409

    # A correction is the one line a person writes, so it must explain itself.
    assert client.post(
        f"{door}/adjust", json={"amount": -50_000, "note": ""}, headers=admin
    ).status_code == 422
    fixed = client.post(
        f"{door}/adjust",
        json={"amount": -50_000, "note": "Sinov uchun tuzatish"},
        headers=admin,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["adjustments"] == -50_000
    assert fixed.json()["payable"] == sum(
        line["amount"] for line in fixed.json()["lines"]
    )

    client.post(f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin)
    # Closed: no more corrections here — one goes in the next period, where it
    # can be seen.
    assert client.post(
        f"{door}/adjust", json={"amount": -1, "note": "kech"}, headers=admin
    ).status_code == 409

    paid = client.post(f"{door}/pay", json=body, headers=admin)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["payment_reference"] == "TR-99001"
    assert paid.json()["paid_at"]

    # Once, and only once.
    assert client.post(f"{door}/pay", json=body, headers=admin).status_code == 409
    # And not by the seller being paid.
    assert client.post(f"{door}/pay", json=body, headers=theirs).status_code == 403
    assert client.post(f"{door}/pay", json=body, headers=operator).status_code == 403

    # Money leaving is logged with a name against it.
    rows = _audit_rows("settlement.pay", statement["id"])
    assert rows and rows[-1].actor_role is UserRole.ADMIN
    assert "TR-99001" in rows[-1].note
    assert _audit_rows("settlement.adjust", statement["id"])
    assert not _stock_is_consistent()


def test_two_periods_cannot_cover_the_same_day(
    client: TestClient, admin: dict[str, str]
) -> None:
    """One sale falling into two runs would either be paid twice or leave
    nobody able to say which run it belonged to."""
    _period(client, admin, starts="2031-01-01", ends="2031-01-31", label="Yanvar")
    clash = client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2031-01-15", "ends_on": "2031-02-15"},
        headers=admin,
    )
    assert clash.status_code == 409
    assert "davr" in clash.json()["detail"].lower()

    # Backwards is refused too.
    assert client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2031-03-31", "ends_on": "2031-03-01"},
        headers=admin,
    ).status_code == 400

    # The month after it is fine.
    after = _period(
        client, admin, starts="2031-02-01", ends="2031-02-28", label="Fevral"
    )
    assert after["status"] == "open"
    assert client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2032-01-01", "ends_on": "2032-01-31"},
    ).status_code == 401


def test_the_handling_tariff_is_readable_by_the_people_charged_it(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A fee somebody is charged and cannot look up is a fee they can only
    dispute."""
    _, theirs = _linked_seller(staff, "Payout Sakkiz", "+998900060072")
    bands = client.get(f"{API}/staff/payouts/tariffs", headers=theirs)
    assert bands.status_code == 200, bands.text
    rows = bands.json()
    assert len(rows) >= 2
    # Read top to bottom as "up to 500 g", "up to 2 kg", so the band a parcel
    # falls into is the first that covers it.
    assert rows == sorted(rows, key=lambda r: r["max_grams"])
    assert all(r["fee"] > 0 and r["storage_per_day"] > 0 and r["label"] for r in rows)
    # Both rates climb with the band, because both follow how big the thing is.
    assert [r["fee"] for r in rows] == sorted(r["fee"] for r in rows)
    assert [r["storage_per_day"] for r in rows] == sorted(
        r["storage_per_day"] for r in rows
    )
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).status_code == 200
    assert client.get(f"{API}/staff/payouts/tariffs", headers=auth).status_code == 403


# --------------------------------------------------------- the seller's own way in


def test_a_seller_can_see_which_shop_they_are_and_nobody_elses(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """`/staff/me` answers with the user — a phone number and a role — and says
    nothing about the shop behind it. So the cabinet greeted people by phone
    number, and somebody just taken on could not confirm they were linked to
    the right shop, which is the first thing they would check."""
    mine_id, mine = _linked_seller(staff, "Katalog Bir", "+998900080001", commission=12)
    other_id, other = _linked_seller(staff, "Katalog Ikki", "+998900080002", commission=7)

    shop = client.get(f"{API}/staff/sellers/me", headers=mine)
    assert shop.status_code == 200, shop.text
    body = shop.json()
    assert (body["id"], body["name"]) == (mine_id, "Katalog Bir")
    # A term of their own contract, and the figure every statement is computed
    # from — a seller who cannot read it cannot check a payout.
    assert body["commission_percent"] == 12
    assert body["active"] is True
    assert body["created_at"]

    # The other seller gets their own row, never this one.
    theirs = client.get(f"{API}/staff/sellers/me", headers=other).json()
    assert (theirs["id"], theirs["name"]) == (other_id, "Katalog Ikki")
    assert theirs["commission_percent"] == 7

    # And no door to anybody else's: the admin's list stays the admin's.
    assert client.get(f"{API}/staff/sellers/{other_id}", headers=mine).status_code == 403
    assert client.get(f"{API}/staff/sellers", headers=mine).status_code == 403
    assert client.get(f"{API}/staff/sellers/me", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/sellers/me").status_code == 401

    # An admin has no shop of their own and is told so rather than guessed at.
    refused = client.get(f"{API}/staff/sellers/me", headers=admin)
    assert refused.status_code == 400
    assert "do'kon" in refused.json()["detail"]

    # Linking is what stamps the date, so it is there for anybody linked
    # through the front door.
    phone = "+998900080003"
    sign_in_needed = client.post(
        f"{API}/staff/sellers",
        json={"name": "Katalog Uch", "phone": "+998781119977"},
        headers=admin,
    )
    assert sign_in_needed.status_code == 201, sign_in_needed.text
    third_id = sign_in_needed.json()["id"]
    fresh = staff(UserRole.CUSTOMER, phone)
    linked = client.patch(
        f"{API}/staff/sellers/{third_id}", json={"user_phone": phone}, headers=admin
    )
    assert linked.status_code == 200, linked.text
    third = client.get(f"{API}/staff/sellers/me", headers=fresh).json()
    assert third["name"] == "Katalog Uch"
    assert third["linked_at"], "the moment the account was pointed at the shop"
    assert third["offer_count"] == 0


def test_one_seller_gets_one_offer_per_card(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two offers from one seller on one card is two prices for the same goods
    from the same person — the cheaper would always win and the other would
    sit there confusing the shelf."""
    _, mine = _linked_seller(staff, "Katalog Olti", "+998900080031")
    other_id, other = _linked_seller(staff, "Katalog Yetti", "+998900080032")
    product_id, _ = _card_with_a_colour(client, admin, "MB-BROWSE-2", with_a_size=False)

    def body(price: int, **extra: object) -> dict:
        with Session(engine) as session:
            leaves = [v.id for v in of.leaf_variants(session, product_id)]
        return {"product_id": product_id, "price": price, "variant_ids": leaves, **extra}

    first = client.post(f"{API}/staff/offers", json=body(300_000), headers=mine)
    assert first.status_code == 201, first.text

    second = client.post(f"{API}/staff/offers", json=body(250_000), headers=mine)
    assert second.status_code == 409, second.text
    assert "taklif" in second.json()["detail"]
    # Changing the price is how a seller lowers it, and that door works.
    assert client.patch(
        f"{API}/staff/offers/{first.json()['id']}", json={"price": 250_000}, headers=mine
    ).status_code == 200

    # A different seller on the same card is the whole point of the model.
    theirs = client.post(f"{API}/staff/offers", json=body(240_000), headers=other)
    assert theirs.status_code == 201, theirs.text

    # And offering as somebody else is refused rather than quietly corrected.
    assert client.post(
        f"{API}/staff/offers", json=body(1_000, seller_id=other_id), headers=mine
    ).status_code == 403

    # Each seller reads their own offers and only their own.
    def sellers_on(headers: dict[str, str]) -> set[str]:
        rows = client.get(f"{API}/staff/offers", headers=headers).json()
        return {row["seller"]["name"] for row in rows}

    assert sellers_on(mine) == {"Katalog Olti"}
    assert sellers_on(other) == {"Katalog Yetti"}

    # And the two prices sit on the same card, the cheaper one winning it.
    #
    # Read through the offers list rather than through a seller's catalogue
    # browser: ``GET /staff/catalog/browse`` was how a seller found a card of
    # somebody else's to price, which is the Ozon model this shop is not — a
    # seller opens their own product now, so that door went.
    mine_row = next(
        row
        for row in client.get(f"{API}/staff/offers", headers=mine).json()
        if row["product_id"] == product_id
    )
    assert mine_row["price"] == 250_000
    with Session(engine) as session:
        rows = of.offers_for(session, product_id, active_only=False)
    assert {row.price for row in rows} == {250_000, 240_000}
    # No winner yet, and that is the rule rather than a gap: nothing is on the
    # shelf, so there is nothing to sell at either price.
    with Session(engine) as session:
        assert of.winning_offer(session, product_id) is None


# --------------------------------------------------------- the last mile


def _courier(
    staff: Callable[[UserRole, str], dict[str, str]], phone: str
) -> tuple[int, dict[str, str]]:
    headers = staff(UserRole.COURIER, phone)
    with Session(engine) as session:
        return session.exec(select(User).where(User.phone == phone)).one().id, headers


def _key(name: str) -> dict[str, str]:
    """One idempotency key, the way the app makes one per queued action."""
    return {"Idempotency-Key": f"test-{name}"}


def _on_a_round(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    courier: dict[str, str],
    *,
    cash: bool,
) -> dict:
    """An order packed and taken, ready to be knocked on.

    Taken rather than assigned: nobody hands work out any more, so the way an
    order gets onto a round is the courier choosing it off the board — which
    means ``courier`` here is their headers, not their id.

    The shelf is topped up first. Every round here spends one unit of the
    cheapest card and none of them put it back, so without a baseline the
    tests run it out and then start failing on "the basket is empty" — in
    whatever order they happen to run in, which is the worst way to be told.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(
        f"{API}/products", params={"sort": "price_asc"}
    ).json()["items"][0]
    with Session(engine) as session:
        offer = of.winning_offer(session, product["id"]) or of.offers_for(
            session, product["id"], active_only=False
        )[0]
        _adjust_to(session, offer, 25)
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    added = client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    assert added.status_code in (200, 201), added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders",
        json={
            "address_id": address["id"],
            **({"payment_method": "cash"} if cash else {}),
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    order = created.json()

    packed = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=operator,
    )
    assert packed.status_code == 200, packed.text

    board = client.get(f"{API}/courier/orders/available", headers=courier)
    assert board.status_code == 200, board.text
    assert any(row["id"] == order["id"] for row in board.json()), board.text

    took = client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**courier, "Idempotency-Key": f"round-take-{order['id']}"},
    )
    assert took.status_code == 200, took.text
    assert took.json()["status"] == "shipped", took.text
    return order


def test_a_courier_takes_their_own_work_and_reads_only_their_own(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Nobody hands work out. A packed order goes on a board every courier can
    see, the one who wants it takes it, and from that moment it is on their
    round and on nobody else's.

    Assignment used to be an operator's job and it was the step that made a
    packed parcel wait: a courier standing in the warehouse could see the box
    in front of them and not the order, and nothing moved until somebody in an
    office remembered to name them."""
    mine_id, mine = _courier(staff, "+998900090001")
    other_id, other = _courier(staff, "+998900090002")

    listed = client.get(f"{API}/staff/couriers", headers=operator)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} >= {mine_id, other_id}
    assert all(row["role"] == "courier" for row in listed.json())

    order = _on_a_round(client, auth, operator, mine, cash=False)

    round_ = client.get(f"{API}/courier/orders", headers=mine)
    assert round_.status_code == 200, round_.text
    stop = next(row for row in round_.json() if row["id"] == order["id"])
    # What somebody at a door needs, and not the catalogue detail the
    # customer's own shape carries.
    assert stop["recipient_phone"] and stop["address_line"]
    assert stop["attempts"] == 0 and stop["last_failure"] == ""

    # And the operator's own queue says who took it. They do not choose who
    # carries what any more, but "who has it" is still the first question
    # asked about a delivery that went wrong.
    queue = client.get(f"{API}/staff/orders", headers=operator, params={"page_size": 100})
    assert queue.status_code == 200, queue.text
    rows = {row["id"]: row for row in queue.json()["items"]}
    assert rows[order["id"]]["courier_id"] == mine_id
    # The name, because a row is read by a person and an id is not a person.
    listed_names = {
        row["id"]: row["full_name"]
        for row in client.get(f"{API}/staff/couriers", headers=operator).json()
    }
    assert rows[order["id"]]["courier_name"] == listed_names[mine_id]

    # An order nobody is carrying says so rather than naming somebody.
    unassigned = [row for row in rows.values() if row["courier_id"] is None]
    assert all(row["courier_name"] == "" for row in unassigned)
    # A card order is already paid: asking for money again is the mistake
    # `cash_due` exists to prevent.
    assert stop["cash_due"] == 0

    # The other courier's round does not contain it, and reaching for it is a
    # refusal rather than a pretence that it is missing.
    assert order["id"] not in [row["id"] for row in client.get(
        f"{API}/courier/orders", headers=other
    ).json()]
    poached = client.post(
        f"{API}/courier/orders/{order['id']}/failed",
        json={"reason": "boshqa kuryerning buyurtmasi"},
        headers={**other, **_key("poach")},
    )
    assert poached.status_code == 403, poached.text

    # Nobody else's door either.
    assert client.get(f"{API}/courier/orders", headers=operator).status_code == 403
    assert client.get(f"{API}/courier/orders", headers=admin).status_code == 403
    assert client.get(f"{API}/courier/orders").status_code == 401

    # A courier is not somebody an operator can invent.
    # The door an operator used to hand work out through is gone. Nobody
    # assigns a courier now — not an operator, and not a courier naming
    # themselves — so the path itself answers 404 rather than a role check
    # answering 403.
    assert client.post(
        f"{API}/staff/orders/{order['id']}/courier",
        json={"courier_id": other_id},
        headers=operator,
    ).status_code == 404

    # A parcel already taken is not there to take twice, and the courier who
    # missed it is told so rather than handed a second copy.
    late = client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**other, "Idempotency-Key": f"late-take-{order['id']}"},
    )
    assert late.status_code == 409, late.text

    rows = _audit_rows("order.taken", order["id"])
    assert rows and str(rows[-1].new_value) == str(mine_id)


def test_a_retried_delivery_is_not_a_second_sale(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The sentence the whole idempotency design exists for.

    The app queues writes it cannot send and retries them, so "delivered,
    N so'm at the door" arrives twice as a matter of course. Without a key
    that is a second sale off the shelf, and nobody notices until the shelf is
    short.
    """
    courier_id, courier = _courier(staff, "+998900090011")
    order = _on_a_round(client, auth, operator, courier, cash=True)

    stop = next(
        row
        for row in client.get(f"{API}/courier/orders", headers=courier).json()
        if row["id"] == order["id"]
    )
    owed = stop["cash_due"]
    assert owed == order["total"] > 0, "cash at the door"

    body = {"recipient_name": "Aziz Toshmatov", "cash_collected": owed}
    door = f"{API}/courier/orders/{order['id']}/deliver"

    first = client.post(door, json=body, headers={**courier, **_key("deliver-1")})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "delivered"

    # The same request again, with the same key: the answer, not the act.
    again = client.post(door, json=body, headers={**courier, **_key("deliver-1")})
    assert again.status_code == 200, again.text
    assert again.json() == first.json(), "the stored answer, replayed"

    # Sent a third time for good measure, because the app retries until it
    # gets an answer and does not count how many times it tried.
    assert client.post(
        door, json=body, headers={**courier, **_key("deliver-1")}
    ).json() == first.json()

    # The goods left the shelf once — read off the ledger rather than off the
    # cached figure, which is where the claim actually lives. A cash order's
    # goods were *held* from the moment it was placed, so the cache had
    # already dropped; what delivery does is turn the hold into a sale, and a
    # retry that ran twice would leave two sale movements against one order.
    with Session(engine) as session:
        sold = session.exec(
            select(StockMovement).where(
                StockMovement.order_id == order["id"],
                StockMovement.kind == StockMovementKind.SALE,
            )
        ).all()
    assert len(sold) == 1, [(m.id, m.quantity, m.reason) for m in sold]
    assert sold[0].quantity == -1, "signed: what went out"

    # And the cash landed once. On the attempt, which is where it happened —
    # there is no shift adding it up any more.
    with Session(engine) as session:
        attempts = session.exec(
            select(DeliveryAttempt).where(DeliveryAttempt.order_id == order["id"])
        ).all()
    assert len(attempts) == 1, "one door, one row"
    assert attempts[0].cash_collected == owed

    # A second attempt on a delivered order is refused rather than replayed:
    # a new key means a new request, and the order has moved on.
    assert client.post(
        door, json=body, headers={**courier, **_key("deliver-2")}
    ).status_code == 409
    assert not _stock_is_consistent()


def test_a_key_may_not_be_reused_for_a_different_request(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The same key carrying a different body is a bug in the client, not a
    retry. Replaying the first answer would hide it and lose the second
    request entirely."""
    courier_id, courier = _courier(staff, "+998900090031")
    order = _on_a_round(client, auth, operator, courier, cash=False)
    door = f"{API}/courier/orders/{order['id']}/failed"

    assert client.post(
        door, json={"reason": "eshikni ochmadi"}, headers={**courier, **_key("f1")}
    ).status_code == 200

    clash = client.post(
        door, json={"reason": "telefon o'chirilgan"}, headers={**courier, **_key("f1")}
    )
    assert clash.status_code == 409, clash.text
    assert "kalit" in clash.json()["detail"]

    # A missing key is refused too: an optional key is a key some client
    # forgets, and the failure is silent and financial.
    assert client.post(door, json={"reason": "yana"}, headers=courier).status_code == 422

    # Two couriers may use the same key without colliding.
    other_id, other = _courier(staff, "+998900090032")
    theirs = _on_a_round(client, auth, operator, other, cash=False)
    assert client.post(
        f"{API}/courier/orders/{theirs['id']}/failed",
        json={"reason": "manzil topilmadi"},
        headers={**other, **_key("f1")},
    ).status_code == 200


def test_a_delivery_needs_a_name_and_the_photo_is_optional(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The decision, and its reason.

    The name is required: one field a courier can always fill in while
    standing in front of the person who took the goods, and the answer to "I
    never received it". The photo is not: an upload needs signal, and
    requiring one would stop a courier in a basement finishing a delivery they
    have already made — which is the exact situation the offline design is for.
    """
    courier_id, courier = _courier(staff, "+998900090041")
    order = _on_a_round(client, auth, operator, courier, cash=False)
    door = f"{API}/courier/orders/{order['id']}/deliver"

    nameless = client.post(
        door, json={"recipient_name": ""}, headers={**courier, **_key("n1")}
    )
    assert nameless.status_code == 422, nameless.text

    # A courier may upload the picture through the same pipeline a seller
    # uses — that guard was widened rather than a second one built.
    shot = client.post(
        f"{API}/staff/media",
        files={"file": ("door.jpg", _photograph(900, 700), "image/jpeg")},
        headers=courier,
    )
    assert shot.status_code == 201, shot.text

    with_photo = client.post(
        door,
        json={"recipient_name": "Qo'shni", "photo_url": shot.json()["media_url"]},
        headers={**courier, **_key("n2")},
    )
    assert with_photo.status_code == 200, with_photo.text

    with Session(engine) as session:
        kept = session.exec(
            select(DeliveryAttempt)
            .where(DeliveryAttempt.order_id == order["id"])
            .order_by(col(DeliveryAttempt.id).desc())
        ).first()
    assert kept.recipient_name == "Qo'shni"
    assert kept.photo_url, "the evidence is stored"

    # And without one it still goes through, noted as such in the log.
    second = _on_a_round(client, auth, operator, courier, cash=False)
    plain = client.post(
        f"{API}/courier/orders/{second['id']}/deliver",
        json={"recipient_name": "Mijozning o'zi"},
        headers={**courier, **_key("n3")},
    )
    assert plain.status_code == 200, plain.text
    rows = _audit_rows("order.deliver", second["id"])
    assert rows and "suratsiz" in rows[-1].note


def test_a_cash_figure_that_does_not_match_is_refused(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A courier who mistypes it is short at the end of the day with nothing
    to point at, and a mismatch is far likelier to be a typo than a part
    payment worth recording."""
    courier_id, courier = _courier(staff, "+998900090051")
    order = _on_a_round(client, auth, operator, courier, cash=True)
    door = f"{API}/courier/orders/{order['id']}/deliver"
    owed = order["total"]

    wrong = client.post(
        door,
        json={"recipient_name": "Mijoz", "cash_collected": owed - 1000},
        headers={**courier, **_key("c1")},
    )
    assert wrong.status_code == 400
    assert str(owed) in wrong.json()["detail"]

    # The exact figure goes through, and the shelf follows. There is no shift
    # to open first any more: a courier's day is a list of doors, and the cash
    # is recorded where it was taken.
    lone_id, lone = _courier(staff, "+998900090052")
    theirs = _on_a_round(client, auth, operator, lone, cash=True)
    straight = client.post(
        f"{API}/courier/orders/{theirs['id']}/deliver",
        json={
            "recipient_name": "Mijoz",
            "cash_collected": theirs["total"],
        },
        headers={**lone, **_key("c2")},
    )
    assert straight.status_code == 200, straight.text

    assert client.post(
        door,
        json={"recipient_name": "Mijoz", "cash_collected": owed},
        headers={**courier, **_key("c3")},
    ).status_code == 200
    assert not _stock_is_consistent()


def test_a_failed_attempt_keeps_the_order_and_the_courier(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """There is deliberately no `failed` status: a refusal at a door is an
    event, not a state of the order — it is still on its way. What a dispute
    needs is how many times and why, which is a list.

    And giving up is the operator's: the courier is at one door with one
    refusal, and the person who can see three of them and phone the customer
    is somebody else.
    """
    courier_id, courier = _courier(staff, "+998900090061")
    order = _on_a_round(client, auth, operator, courier, cash=False)
    door = f"{API}/courier/orders/{order['id']}/failed"

    for index, reason in enumerate(
        ("Eshikni ochmadi", "Telefon o'chirilgan", "Manzilda yo'q ekan")
    ):
        attempt = client.post(
            door, json={"reason": reason}, headers={**courier, **_key(f"x{index}")}
        )
        assert attempt.status_code == 200, attempt.text
        # Still shipped, still theirs, and the count is climbing.
        assert attempt.json()["status"] == "shipped"
        assert attempt.json()["attempts"] == index + 1
        assert attempt.json()["last_failure"] == reason

    stop = next(
        row
        for row in client.get(f"{API}/courier/orders", headers=courier).json()
        if row["id"] == order["id"]
    )
    assert stop["attempts"] == 3

    # The customer's timeline is untouched: an attempt is not a step their
    # order took, and writing one would put "delivered" in their history
    # before it was true.
    theirs = client.get(f"{API}/orders/{order['id']}", headers=auth).json()
    assert theirs["status"] == "shipped"
    assert not any(e["done"] and e["status"] == "delivered" for e in theirs["events"])

    # A reason is required — "not delivered" with nothing after it is the row
    # nobody can act on.
    assert client.post(
        door, json={"reason": ""}, headers={**courier, **_key("x9")}
    ).status_code == 422

    # The way out is the operator's, and it now exists: goods that never
    # reached the customer were never sold, so cancelling puts the counts back.
    assert client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "uch urinish — mijoz javob bermadi"},
        headers=operator,
    ).status_code == 200
    assert client.get(f"{API}/orders/{order['id']}", headers=auth).json()["status"] == "cancelled"
    assert not _stock_is_consistent()


def test_a_collection_run_brings_returns_back_to_the_warehouse(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A `RemovalOrder` carries goods out to a seller who wants their stock
    back. This brings goods in from customers whose returns were approved —
    opposite direction, different paperwork, same van.

    Receiving one puts nothing on a shelf: whether returned goods are sellable
    is the refund's decision, and doing it here as well would put the same
    shirt back twice.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900090071")
    courier_id, courier = _courier(staff, "+998900090072")
    request, _, _, _ = _refundable_return(client, auth, operator)

    made = client.post(
        f"{API}/staff/pickups",
        json={
            "courier_id": courier_id,
            "return_request_ids": [request["id"]],
            "note": "ertaga ertalab",
        },
        headers=operator,
    )
    assert made.status_code == 201, made.text
    run = made.json()
    assert run["code"].startswith("PCK-")
    assert run["status"] == "open"
    assert run["next_statuses"] == ["collected", "cancelled"]
    line = run["lines"][0]
    # What a courier needs at the door, without another request.
    assert line["customer_phone"] and line["address_line"]
    assert line["collected"] is None, "nobody has tried yet"

    # One van per parcel.
    assert client.post(
        f"{API}/staff/pickups",
        json={"courier_id": courier_id, "return_request_ids": [request["id"]]},
        headers=operator,
    ).status_code == 409

    # It is on this courier's list and nobody else's.
    assert [r["id"] for r in client.get(f"{API}/courier/pickups", headers=courier).json()] == [
        run["id"]
    ]
    _, other = _courier(staff, "+998900090073")
    assert client.get(f"{API}/courier/pickups", headers=other).json() == []
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={"lines": [{"return_request_id": request["id"], "collected": True}]},
        headers={**other, **_key("p0")},
    ).status_code == 403

    # Not collected needs a reason, for the same purpose a failed delivery does.
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={"lines": [{"return_request_id": request["id"], "collected": False}]},
        headers={**courier, **_key("p1")},
    ).status_code == 400

    got = client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={
            "lines": [{"return_request_id": request["id"], "collected": True}],
            "note": "qadoq butun",
        },
        headers={**courier, **_key("p2")},
    )
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "collected"
    assert got.json()["lines"][0]["collected"] is True
    assert got.json()["lines"][0]["attempted_at"]

    # Sent twice, collected once.
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={
            "lines": [{"return_request_id": request["id"], "collected": True}],
            "note": "qadoq butun",
        },
        headers={**courier, **_key("p2")},
    ).json() == got.json()

    # The warehouse books it in — and the shelf does not move.
    with Session(engine) as session:
        before = _stock_snapshot(session)
    received = client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=warehouse
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"
    assert received.json()["received_at"]
    assert received.json()["next_statuses"] == []
    with Session(engine) as session:
        assert _stock_snapshot(session) == before, "the refund decides the shelf"

    # A courier does not book goods in at the warehouse desk.
    assert client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=courier
    ).status_code == 403
    # And twice is not twice.
    assert client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=warehouse
    ).status_code == 409

    # The warehouse can see what is coming, which is the point of it arriving
    # at their desk.
    seen = client.get(
        f"{API}/staff/pickups", params={"status": "received"}, headers=warehouse
    )
    assert seen.status_code == 200
    assert run["id"] in [r["id"] for r in seen.json()]
    assert not _stock_is_consistent()


def _stock_snapshot(session: Session) -> dict[int, int]:
    return {row.id: row.stock_left for row in session.exec(select(Offer)).all()}


# ================================================================== the gaps closed

# Five things the system could not answer. Each one is somebody looking at a
# screen with a reasonable question and being told nothing.


# ------------------------------------------------ what became of what I proposed


def test_a_seller_reads_what_became_of_the_card_they_proposed(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refusal carries a reason, and the seller could not read it.

    Proposing worked. Approved, the card turns up in the shop and they can
    find it there. Refused, it went nowhere they could look — so a seller was
    being asked to fix something without being told what was wrong with it,
    and the only way to find out was to telephone an admin.
    """
    seller_id, mine = _linked_seller(staff, "Taklif Bir", "+998900100001")
    _, theirs = _linked_seller(staff, "Taklif Ikki", "+998900100002")
    category = client.get(f"{API}/categories").json()[0]["slug"]

    def propose(sku: str, headers: dict[str, str]) -> dict:
        made = client.post(
            f"{API}/staff/catalog/proposals",
            json={
                "sku": sku,
                "title": f"Taklif {sku}",
                "category_slug": category,
                "price": 90_000,
            },
            headers=headers,
        )
        assert made.status_code == 201, made.text
        return made.json()

    refused = propose("MB-GAP-PROP-1", mine)
    accepted = propose("MB-GAP-PROP-2", mine)
    somebody_elses = propose("MB-GAP-PROP-3", theirs)

    # Before anybody has looked: in the queue, and the seller can see that it
    # is — "has anybody read it yet" is the other half of the question.
    waiting = client.get(f"{API}/staff/catalog/proposals", headers=mine)
    assert waiting.status_code == 200, waiting.text
    rows = {row["id"]: row for row in waiting.json()["items"]}
    assert rows[refused["id"]]["status"] == "moderating"
    assert rows[refused["id"]]["moderation_note"] == ""

    # Nobody else's proposals, and that is not a filter they chose: for a
    # seller these are the only rows that exist.
    assert somebody_elses["id"] not in rows
    assert {row["proposed_by"]["id"] for row in waiting.json()["items"]} == {seller_id}

    # Somebody answers. The *answering* is the warehouse's now — receiving a
    # batch publishes a card and refusing one takes it down with its reason,
    # both in ``app.routers.warehouse``, and both have their own tests. This
    # one is about what the seller can read afterwards, so the two outcomes
    # are written rather than driven.
    _refuse(refused["id"], "Surat yo'q — kamida bitta kerak")
    _set_status(accepted["id"], ProductStatus.PUBLISHED)

    # The refusal, and the reason for it, which is the whole point.
    after = client.get(f"{API}/staff/catalog/proposals", headers=mine).json()["items"]
    rows = {row["id"]: row for row in after}
    assert rows[refused["id"]]["status"] == "rejected"
    assert rows[refused["id"]]["moderation_note"] == "Surat yo'q — kamida bitta kerak"
    # And the approved one is here too, so a seller can confirm the card in the
    # shop is theirs rather than hunting the catalogue for it.
    assert rows[accepted["id"]]["status"] == "published"
    assert rows[accepted["id"]]["moderation_note"] == ""

    # The list a seller actually opens after being told "one was refused".
    only_refused = client.get(
        f"{API}/staff/catalog/proposals", params={"status": "rejected"}, headers=mine
    )
    assert only_refused.status_code == 200, only_refused.text
    assert [row["id"] for row in only_refused.json()["items"]] == [refused["id"]]
    assert only_refused.json()["total"] == 1

    # Findable by SKU, which is what a seller's own system calls it.
    found = client.get(
        f"{API}/staff/catalog/proposals",
        params={"q": "MB-GAP-PROP-2"},
        headers=mine,
    ).json()["items"]
    assert [row["id"] for row in found] == [accepted["id"]]

    # An admin has no shop, so they read every seller's proposals — with the
    # provenance on each row — and may narrow it to one.
    everybody = client.get(f"{API}/staff/catalog/proposals", headers=admin)
    assert everybody.status_code == 200, everybody.text
    seen = {row["id"] for row in everybody.json()["items"]}
    assert {refused["id"], accepted["id"], somebody_elses["id"]} <= seen
    # A draft the platform wrote itself is not a proposal and has no business
    # in a list about somebody else's suggestions.
    assert all(row["proposed_by"] for row in everybody.json()["items"])
    narrowed = client.get(
        f"{API}/staff/catalog/proposals",
        params={"seller_id": seller_id},
        headers=admin,
    ).json()["items"]
    assert somebody_elses["id"] not in {row["id"] for row in narrowed}

    # Not a customer's list, and not an anonymous one.
    assert client.get(f"{API}/staff/catalog/proposals", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/catalog/proposals").status_code == 401


# ----------------------------------------------- a weight band is a contract term


def test_a_weight_band_can_be_edited_and_every_change_is_logged(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The bands were readable and unwritable: a rate somebody is charged
    arrived through the seed and could only be changed in the database, which
    is a change with nobody's name on it.

    A band this light covers nothing in the catalogue — the lightest seeded
    band tops out at 500 g — so the suite's other arithmetic is untouched by
    it. That is deliberate: these rates are global, and a test that edited a
    real band would be editing what every other test is charged.
    """
    _, theirs = _linked_seller(staff, "Tarif Bir", "+998900100011")
    seeded = client.get(f"{API}/staff/payouts/tariffs", headers=admin).json()

    made = client.post(
        f"{API}/staff/payouts/tariffs",
        json={
            "max_grams": 12,
            "fee": 1_000,
            "storage_per_day": 5,
            "label": "Sinov guruhi",
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    band = made.json()
    assert (band["max_grams"], band["fee"], band["storage_per_day"]) == (12, 1_000, 5)

    # Writing a band is logged with a name against it, and the log says which
    # band in words — a row id is not a band anybody recognises a year later.
    created = _audit_rows("tariff.create", band["id"])
    assert created and created[-1].actor_role is UserRole.ADMIN
    assert "Sinov guruhi" in created[-1].note

    # One row per field that actually moved. "The band was edited" is not a
    # fact a seller disputing a charge can act on; "the fee went from 1 000 to
    # 4 000 on this day, by this person" is.
    changed = client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}",
        json={"fee": 4_000, "storage_per_day": 5, "label": "Sinov guruhi"},
        headers=admin,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["fee"] == 4_000
    fees = _audit_rows("tariff.fee", band["id"])
    assert [(row.old_value, row.new_value) for row in fees] == [("1000", "4000")]
    # Only when it moved: a panel saving a form it did not change should not
    # fill the log with a change nobody made.
    assert not _audit_rows("tariff.storage_per_day", band["id"])
    assert not _audit_rows("tariff.label", band["id"])

    # Two bands may not share a ceiling. `band_for` takes the lightest band
    # that still covers a parcel, so with two of them the answer to "what does
    # this cost to handle" would depend on row order.
    clash = client.post(
        f"{API}/staff/payouts/tariffs",
        json={"max_grams": 12, "fee": 2_000},
        headers=admin,
    )
    assert clash.status_code == 409
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}",
        json={"max_grams": 500},
        headers=admin,
    ).status_code == 409, "500 g is the seeded lightest band"

    # The heaviest band is the roof. Delete it and every parcel above the band
    # below falls into no band at all and is handled free — a discount nobody
    # decided to give and nothing would report.
    bands = client.get(f"{API}/staff/payouts/tariffs", headers=admin).json()
    roof = max(bands, key=lambda row: row["max_grams"])
    refused = client.delete(f"{API}/staff/payouts/tariffs/{roof['id']}", headers=admin)
    assert refused.status_code == 409
    assert "guruh" in refused.json()["detail"].lower()
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).json() == bands, (
        "a refusal changes nothing"
    )

    # A rate is a term of a contract, so a seller reads it and does not write
    # it — and a customer does neither.
    assert client.post(
        f"{API}/staff/payouts/tariffs",
        json={"max_grams": 14, "fee": 1},
        headers=theirs,
    ).status_code == 403
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}", json={"fee": 1}, headers=theirs
    ).status_code == 403
    assert client.delete(
        f"{API}/staff/payouts/tariffs/{band['id']}", headers=theirs
    ).status_code == 403
    assert client.get(f"{API}/staff/payouts/tariffs", headers=auth).status_code == 403
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}", json={"fee": 1}
    ).status_code == 401

    assert client.patch(
        f"{API}/staff/payouts/tariffs/999999", json={"fee": 1}, headers=admin
    ).status_code == 404

    # Withdrawn, and the withdrawal logged too.
    gone = client.delete(f"{API}/staff/payouts/tariffs/{band['id']}", headers=admin)
    assert gone.status_code == 200, gone.text
    assert _audit_rows("tariff.delete", band["id"])
    # The table as the seed left it: this test edited nothing anybody else is
    # charged, which is what makes it safe to run beside the rest of them.
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).json() == seeded
    assert client.delete(
        f"{API}/staff/payouts/tariffs/{band['id']}", headers=admin
    ).status_code == 404


def test_editing_a_tariff_does_not_rewrite_a_closed_statement(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The property that makes the bands safe to edit at all.

    A closed statement is a figure a seller has read. Recomputing it against
    today's rates would mean that reading it twice gives two answers, which
    makes every answer provisional — the same reason the commission on a line
    is the rate it sold at rather than the rate on the seller row today.

    So this walks both halves: the closed run does not move when the band
    under it is doubled a hundredfold, and the next open run does.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900100021")
    seller_id, _ = _linked_seller(staff, "Tarif Ikki", "+998900100022", commission=10)

    # A band nothing else in the catalogue falls into, so this test is not
    # editing what every other test is charged. Written before the sale,
    # because the fee is captured onto the order line at checkout.
    band = client.post(
        f"{API}/staff/payouts/tariffs",
        json={
            "max_grams": 9,
            "fee": 5_000,
            "storage_per_day": 100,
            "label": "Qulf guruhi",
        },
        headers=admin,
    )
    assert band.status_code == 201, band.text
    band_id = band.json()["id"]

    first_id, _ = _card_with_a_colour(client, admin, "MB-GAP-LOCK-1", with_a_size=False)
    second_id, _ = _card_with_a_colour(client, admin, "MB-GAP-LOCK-2", with_a_size=False)
    with Session(engine) as session:
        for product_id in (first_id, second_id):
            row = session.get(Product, product_id)
            row.weight_grams = 7
            session.add(row)
        session.commit()

    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=first_id, price=200_000,
    )

    period = _period(
        client, admin, starts="2047-01-01", ends="2047-12-31", label="Qulflangan"
    )
    before = _statement(client, admin, period["id"], seller_id)
    assert before["fulfilment"] == 5_000, "one unit, at the band's fee"
    assert before["storage"] > 0
    # Nothing has moved for months by the closing day, so the shelf rate is
    # tripled — and the line says so, which is what makes it checkable.
    assert "× 300 so'm" in _lines(before, "storage")[0]["note"]

    closed = client.post(
        f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin
    )
    assert closed.status_code == 200, closed.text
    frozen = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    ).json()
    assert frozen["status"] == "closed"

    # The contract is renegotiated, steeply.
    bumped = client.patch(
        f"{API}/staff/payouts/tariffs/{band_id}",
        json={"fee": 999_000, "storage_per_day": 9_900},
        headers=admin,
    )
    assert bumped.status_code == 200, bumped.text

    # Every row of the closed account, unchanged — not the totals only, the
    # lines and their workings-out, because the note is what a seller checks
    # the figure against.
    after = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    )
    assert after.status_code == 200, after.text
    assert after.json() == frozen, "a closed statement is finished"
    assert (after.json()["fulfilment"], after.json()["storage"]) == (
        before["fulfilment"],
        before["storage"],
    )

    # And the lock is a lock rather than an accident of nothing being asked:
    # the next run, still open, is worked out at the new rate.
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=second_id, price=200_000,
    )
    later = _period(
        client, admin, starts="2048-01-01", ends="2048-12-31", label="Yangi stavka"
    )
    now = _statement(client, admin, later["id"], seller_id)
    assert now["fulfilment"] == 999_000, "the parcel sold after the change"
    assert "× 29700 so'm" in _lines(now, "storage")[0]["note"]
    # The settled sale is spent and is not restated into the new run.
    assert [line["order_item_id"] for line in _lines(now, "sale")] != [
        line["order_item_id"] for line in _lines(before, "sale")
    ]

    client.delete(f"{API}/staff/payouts/tariffs/{band_id}", headers=admin)
    assert not _stock_is_consistent()


# ------------------------------------------------------- how the month is going


def test_a_seller_reads_the_period_still_running_and_it_says_it_is_not_final(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """"How is this month going" had no answer.

    `/statements` lists the runs an admin has generated, so until somebody
    generated one a seller mid-period was told nothing — while the sales, the
    returns and the days of storage were all in the database being counted
    for them.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900100031")
    seller_id, mine = _linked_seller(staff, "Joriy Bir", "+998900100032", commission=10)
    _, theirs = _linked_seller(staff, "Joriy Ikki", "+998900100033")

    product_id, _ = _card_with_a_colour(client, admin, "MB-GAP-NOW-1", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=700_000, quantity=2,
    )

    running = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert running.status_code == 200, running.text
    body = running.json()

    # The point of the shape: it says it is a guess before anybody asks. A
    # seller shown a figure and paid a different one has been told the first
    # number was provisional, which makes every number provisional.
    assert body["is_final"] is False
    assert body["as_of"]
    assert body["starts_on"] <= body["ends_on"]

    # The arithmetic is the arithmetic — 2 × 700 000 at the rate on the line.
    assert (body["seller_id"], body["seller_name"]) == (seller_id, "Joriy Bir")
    assert body["gross_sales"] == 1_400_000
    assert body["commission"] == 140_000
    assert body["payable"] == sum(line["amount"] for line in body["lines"])
    assert body["line_count"] == len(body["lines"])
    assert body["lines"], "an account to read, not a number to argue with"

    # Not a statement, and nothing about it could be mistaken for one: no id
    # to fetch, no status that could become `paid`.
    assert "id" not in body and "status" not in body
    assert all("id" not in line for line in body["lines"])

    # And it wrote nothing. A read that persisted a statement would let a
    # seller opening their cabinet create the run an admin is supposed to.
    with Session(engine) as session:
        assert not session.exec(
            select(SellerStatement).where(SellerStatement.seller_id == seller_id)
        ).all()

    # Somebody else's sales are not in it.
    others = client.get(f"{API}/staff/payouts/current", headers=theirs)
    assert others.status_code == 200, others.text
    assert others.json()["seller_id"] != seller_id
    assert others.json()["gross_sales"] == 0

    # An admin has no shop of their own, so they say whose.
    assert client.get(f"{API}/staff/payouts/current", headers=admin).status_code == 400
    for_them = client.get(
        f"{API}/staff/payouts/current",
        params={"seller_id": seller_id},
        headers=admin,
    )
    assert for_them.status_code == 200, for_them.text
    assert for_them.json()["gross_sales"] == 1_400_000
    assert client.get(
        f"{API}/staff/payouts/current", params={"seller_id": 999999}, headers=admin
    ).status_code == 404

    assert client.get(f"{API}/staff/payouts/current", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/payouts/current").status_code == 401

    # It is a preview of the run, not a second opinion about it: generating a
    # period over the same days reaches the same figure from the same lines.
    period = _period(
        client, admin, starts="2049-01-01", ends="2049-12-31", label="Joriy sinov"
    )
    statement = _statement(client, admin, period["id"], seller_id)
    assert statement["gross_sales"] == body["gross_sales"]
    assert statement["commission"] == body["commission"]
    assert [
        (line["kind"], line["amount"], line["order_item_id"])
        for line in _lines(statement, "sale")
    ] == [
        (line["kind"], line["amount"], line["order_item_id"])
        for line in body["lines"]
        if line["kind"] == "sale"
    ]

    # Closing it is what turns the number into a promise — and the running
    # total then reads zero for what has been settled, because a closed
    # statement's sources are spent.
    client.post(f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin)
    settled = client.get(f"{API}/staff/payouts/current", headers=mine).json()
    assert settled["is_final"] is False
    assert settled["gross_sales"] == 0, "paid for once"
    assert not _stock_is_consistent()


# ------------------------------------------------------------ the brand index


def test_the_brand_index_says_how_many_cards_carry_each_brand(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`product_count` was in the shape and was always nought.

    The figure was only ever computed in `/products/filters`, where it is
    scoped to one listing so the tick-boxes add up to the grid beside them. An
    A-to-Z of marques with "(0)" against every one of them tells a shopper
    nothing and reads like a bug.
    """
    assert client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-index", "name": "Sanoq Index"},
        headers=admin,
    ).status_code == 201
    category = client.get(f"{API}/categories").json()[0]["slug"]

    def counted() -> int:
        rows = client.get(f"{API}/brands")
        assert rows.status_code == 200, rows.text
        return next(
            row["product_count"]
            for row in rows.json()
            if row["slug"] == "sinov-sanoq-index"
        )

    # A brand with nothing in the shop is still listed — the index is a
    # directory — and counts nought, which is the truth about it.
    assert counted() == 0

    card = _admin_card(
        client,
        admin,
        sku="MB-GAP-BRAND-1",
        title="Sanoq kartochkasi",
        category_slug=category,
        brand_slug="sinov-sanoq-index",
        price=60_000,
    )

    # A draft is not in the shop, and tapping the brand would open an empty
    # listing — the listing is narrowed the same way, so the count is too.
    assert counted() == 0

    _set_status(card["id"], ProductStatus.PUBLISHED)
    assert counted() == 1

    # The same window the filter sheet counts in, so the two screens agree.
    sheet = client.get(f"{API}/products/filters").json()["brands"]
    assert next(
        row["product_count"] for row in sheet if row["slug"] == "sinov-sanoq-index"
    ) == 1

    # Every seeded marque is counted, not just the one this test wrote: the
    # figure was nought for all of them.
    assert sum(row["product_count"] for row in client.get(f"{API}/brands").json()) > 1

    # Withdrawn from the shop, and the count follows it out.
    _set_status(card["id"], ProductStatus.ARCHIVED)
    assert counted() == 0


def test_the_running_total_names_the_run_it_belongs_to_when_there_is_one(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two windows "so far" can mean, and the answer says which it is.

    Between runs there is no period to belong to — the last one is closed and
    the next is not open — and answering with silence would be answering "how
    is this month going" with "an admin has not got round to it". So the days
    since the last period are worked out instead and come back with no id,
    because they are not a period: calling them one would invite somebody to
    close them.

    Once a run does cover today, that is the window, and its dates were
    somebody's decision rather than ours.
    """
    _, mine = _linked_seller(staff, "Oyna Bir", "+998900100041")

    # No run covers today, so the window is the gap and says so.
    gap = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert gap.status_code == 200, gap.text
    assert gap.json()["period_id"] is None
    assert gap.json()["period_status"] is None
    assert gap.json()["period_label"], "a window with no name still says what it is"
    assert gap.json()["ends_on"] == utcnow().date().isoformat(), "through today"

    # Opened. Periods may not overlap and every test here shares one database,
    # so this run starts today: the days behind it are taken by the storage
    # test, which dates its window to yesterday. A test added after this one
    # can no longer open a run covering today — take a window in the future,
    # the way the rest of this section does.
    today = utcnow().date()
    period = _period(
        client,
        admin,
        starts=today.isoformat(),
        ends=(today + timedelta(days=5)).isoformat(),
        label="Joriy oy",
    )

    now = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert now.status_code == 200, now.text
    body = now.json()
    assert body["period_id"] == period["id"]
    assert body["period_status"] == "open"
    assert body["period_label"] == "Joriy oy"
    assert body["starts_on"] == period["starts_on"]
    assert body["ends_on"] == period["ends_on"], "the run's days, not ours"
    # Still not the figure they will be paid: closing is what makes it one.
    assert body["is_final"] is False


# ================================================== the same answer on both databases

# SQLite for development, Postgres for production. Anything that answers
# differently on the two is a bug that reaches the user through whichever one
# the tests are not running on, so these run on both and assert the same thing.


def test_search_ignores_case_in_russian_as_well_as_english(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """`lower()` is not the same function on the two databases.

    Every search here is already written the portable way —
    `func.lower(column).like(needle)` with the needle lowered in Python — so
    that `LIKE`'s own case rules never come into it. SQLite's `LIKE` ignores
    ASCII case and Postgres' does not, and with both sides lowercase that
    difference cannot bite.

    What it misses is that **SQLite's `lower()` is ASCII-only**:

        lower('Чайники')   -> 'Чайники'   unchanged, on SQLite
        'ЧАЙНИКИ'.lower()  -> 'чайники'   Python, which is not ASCII-only
        'Чайники' LIKE '%чайники%'  ->  no match

    Postgres lowercases Cyrillic properly and matches. So this was live on
    SQLite — every developer's machine — and would have been *fixed* by the
    move to Postgres, which is the worst way for a bug to go: nothing raises,
    no test that searches in Latin notices, and the symptom is a customer
    typing a Russian name into a trilingual shop and being told there is
    nothing there.

    `app.db` now replaces SQLite's `lower` with Python's, so this test is the
    same on both. It searches in upper case on purpose: matching only works if
    both sides really were folded.
    """
    product_id = _write_a_card(
        sku="MB-CYR-1",
        title="Чайник электрический",
        subtitle="Стеклянный",
        description="Чайник с подсветкой",
        price=250_000,
    )

    # The editor's search, before it is even published.
    def admin_hits(q: str) -> list[int]:
        got = client.get(
            f"{API}/staff/catalog/products", params={"q": q}, headers=admin
        )
        assert got.status_code == 200, got.text
        return [row["id"] for row in got.json()["items"]]

    assert product_id in admin_hits("Чайник"), "as typed"
    assert product_id in admin_hits("ЧАЙНИК"), "upper case Cyrillic"
    assert product_id in admin_hits("чайник"), "lower case Cyrillic"
    assert product_id in admin_hits("ЭЛЕКТРИЧЕСКИЙ"), "a later word, upper case"
    # And Latin still behaves, which is what would have broken if the fix had
    # been to stop lowering at all.
    assert admin_hits("MB-CYR-1") == admin_hits("mb-cyr-1") == [product_id]

    _set_status(product_id, ProductStatus.PUBLISHED)

    # The shopper's listing, and the typeahead behind the search box.
    def shop_hits(q: str) -> list[int]:
        got = client.get(f"{API}/products", params={"q": q, "show_sold_out": True})
        assert got.status_code == 200, got.text
        return [row["id"] for row in got.json()["items"]]

    assert product_id in shop_hits("ЧАЙНИК")
    assert product_id in shop_hits("чайник")
    # The description is searched too, and it only has the word in one case.
    assert product_id in shop_hits("ПОДСВЕТКОЙ")

    # A staff account found by name — the search an admin uses to appoint
    # somebody, and the one most likely to be given a Cyrillic name.
    theirs = sign_in("+998900110001")
    named = client.patch(
        f"{API}/me", json={"full_name": "Дилноза Расулова"}, headers=theirs
    )
    assert named.status_code == 200, named.text

    def users_found(q: str) -> list[str]:
        got = client.get(f"{API}/staff/users", params={"q": q}, headers=admin)
        assert got.status_code == 200, got.text
        return [row["phone"] for row in got.json()["items"]]

    assert "+998900110001" in users_found("Дилноза")
    assert "+998900110001" in users_found("ДИЛНОЗА"), "upper case Cyrillic"
    assert "+998900110001" in users_found("расулова"), "surname, lower case"
    # The phone half of the same search, which is what it is mostly used for.
    assert "+998900110001" in users_found("900110001")

    # Nothing matches a word that is not there — a search that found
    # everything would satisfy every assertion above.
    assert product_id not in shop_hits("самовар")
    assert "+998900110001" not in users_found("Гулнора")


def test_the_same_row_gets_the_same_id_on_a_freshly_seeded_database() -> None:
    """`reset()` has to put the id counters back, not just empty the tables.

    On SQLite the next rowid is `max(rowid) + 1`, so an empty table starts at 1
    again by itself. On Postgres a sequence is its own object and `DELETE` does
    not touch it — a second seed numbered the same catalogue from 63 instead of
    1, which broke every test that names a row by id and, worse, meant two
    freshly seeded databases could not be compared at all.

    The suite's own database is seeded once per session, so this asserts the
    property that made that safe: the seeded rows occupy the bottom of the
    range, from 1.
    """
    with Session(engine) as session:
        first = session.exec(
            select(Product).order_by(col(Product.id)).limit(1)
        ).one()
        assert first.id == 1, "the seed's first product is id 1, on either database"

        # Every seeded table that the suite names by id starts from 1 too.
        for model in (Category, Brand, User):
            lowest = session.exec(
                select(func.min(model.id)).select_from(model)
            ).one()
            assert lowest == 1, f"{model.__name__} ids start at 1"


def test_every_column_type_survives_the_round_trip_on_this_database() -> None:
    """The types SQLite is relaxed about and Postgres is not.

    SQLite stores what you hand it and barely inspects the declared type;
    Postgres enforces one. So a value that goes in and comes back unchanged on
    a developer's machine is not evidence that it will in production, and the
    classes that differ are well known: a JSON column, a naive datetime, a
    boolean, an enum, a float.

    This writes one of each through the models and reads it back through a
    fresh session — fresh so the answer comes from the database rather than
    from the identity map, which would happily hand back the Python object
    that was just put in and prove nothing.

    ``ReturnRequest`` carries all of it now: two JSON columns, three enums, a
    naive timestamp. It used to be split with ``Review``, which went with the
    panels rebuild — and losing the only row that carried a JSON list of
    non-ASCII strings would have quietly narrowed what this checks.

    Nothing here is a fix; it is the assertion that no fix is needed, made on
    whichever database the suite was pointed at.
    """
    from app.models import ReturnInspection, ReturnStatus, SellerReturnDecision

    with Session(engine) as session:
        # An existing order to hang a return on, so the foreign keys are real.
        item = session.exec(select(OrderItem).order_by(col(OrderItem.id))).first()
        assert item is not None, "the seed writes orders"
        # Plain integers, read out while the session is still open: the ORM
        # object goes stale the moment the block closes.
        product_id, order_id, item_id = item.product_id, item.order_id, item.id
        user_id = session.exec(select(User.id).order_by(col(User.id))).first()

        stamp = utcnow().replace(microsecond=123456)
        request = ReturnRequest(
            user_id=user_id,
            order_id=order_id,
            order_item_id=item_id,
            reason="Turlar tekshiruvi",
            # JSON: a list of strings, non-ASCII among them.
            photos=["возврат/a.png", "returns/b.png", "o'lcham.png"],
            status=ReturnStatus.SUBMITTED,
            # Two more enums, one of which is nullable — and a null enum is a
            # different value from its first member, which a driver that
            # coerced them would be caught doing here.
            inspection=ReturnInspection.OK,
            seller_decision=None,
            created_at=stamp,
        )
        empty = ReturnRequest(
            user_id=user_id,
            order_id=order_id,
            reason="Bo'sh ro'yxat",
            # `[]` and NULL are different values in the column beside it.
            photos=[],
            status=ReturnStatus.SUBMITTED,
            created_at=stamp,
        )
        session.add(request)
        session.add(empty)
        session.commit()
        request_id, empty_id = request.id, empty.id

    with Session(engine) as fresh:
        got = fresh.get(ReturnRequest, request_id)

        # JSON, both directions and both shapes.
        assert got.photos == ["возврат/a.png", "returns/b.png", "o'lcham.png"]
        assert fresh.get(ReturnRequest, empty_id).photos == [], (
            "an empty list is a list, not a null"
        )

        # A naive UTC datetime, to the microsecond. Every timestamp in this
        # codebase comes from `models.utcnow`, which strips the tzinfo, and the
        # columns are `DateTime` with no timezone — so both databases hold
        # `timestamp without time zone` and neither is doing a conversion.
        assert got.created_at.tzinfo is None, "naive on the way out as well as in"
        assert got.created_at == stamp, "microseconds included"

        # An enum, which is a VARCHAR with a check on SQLite and a real type on
        # Postgres. Read back as the Python member, not as its name — and a
        # nullable one that was never set comes back as None.
        assert got.status is ReturnStatus.SUBMITTED
        assert got.inspection is ReturnInspection.OK
        assert got.seller_decision is None
        assert got.refund_amount == 0 and isinstance(got.refund_amount, int)

        # And the enum is usable in a WHERE, which is where a native type
        # would bite if the value were being sent as the wrong thing.
        #
        # Against `stamp` rather than a fresh `utcnow()`. `stamp` is `utcnow()`
        # with its microseconds *replaced* by 123456, so whenever the real
        # clock was below that it sits a fraction of a second in the future —
        # and a comparison made microseconds later in the same second then
        # failed about one run in eight.
        found = fresh.exec(
            select(ReturnRequest).where(
                ReturnRequest.id == request_id,
                col(ReturnRequest.status).in_([ReturnStatus.SUBMITTED]),
                col(ReturnRequest.inspection).in_([ReturnInspection.OK]),
                col(ReturnRequest.seller_decision).is_(None),
                ReturnRequest.created_at <= stamp,
            )
        ).first()
        assert found is not None, "enum in an IN, a null enum, a datetime compared"
        assert SellerReturnDecision.RELIST.value == "relist", "the wire value"

        # A float column, on a row the seed wrote.
        product = fresh.get(Product, product_id)
        assert isinstance(product.rating, float)

        # Boolean, and the `.is_(True)` form every listing uses.
        assert isinstance(product.in_stock, bool)
        assert fresh.exec(
            select(func.count()).select_from(Product).where(Product.in_stock.is_(True))
        ).one() >= 0

    # Tidy up: these rows would otherwise show up in another test's counts.
    with Session(engine) as session:
        session.delete(session.get(ReturnRequest, request_id))
        session.delete(session.get(ReturnRequest, empty_id))
        session.commit()


# ============================================ a seller's own product, end to end

# The catalogue is not the platform's alone. A seller opens their own product,
# photographs it, prices it and says what colours and sizes they have; what the
# warehouse confirms is that the goods turned up, not that the listing was
# permitted. These hold that whole line together, because it is one line and
# breaking it anywhere leaves a seller with a product nobody can buy.


def _listing_body(
    client: TestClient, seller: dict[str, str], title: str, **over
) -> dict:
    """A two-colour, five-size listing with real uploaded photographs."""
    images = []
    for name in ("front.jpg", "back.jpg"):
        got = client.post(
            f"{API}/staff/media",
            files={"file": (name, _photograph(900, 900), "image/jpeg")},
            headers=seller,
        )
        assert got.status_code == 201, got.text
        images.append(got.json()["media_url"])

    sizes = (("S", 6), ("M", 9), ("L", 7), ("XL", 4), ("XXL", 2))
    body = {
        "title": title,
        "subtitle": "Yumshoq trikotaj",
        "description": "Kunlik kiyish uchun.",
        "category_slug": client.get(f"{API}/categories").json()[0]["slug"],
        "price": 149_000,
        "weight_grams": 300,
        "images": images,
        "colors": [
            {
                "label": "Oq",
                "value": "#FFFFFF",
                "image_url": images[0],
                "sizes": [{"label": s, "quantity": q} for s, q in sizes],
            },
            {
                "label": "Qora",
                "value": "#111113",
                "image_url": images[1],
                "sizes": [{"label": s, "quantity": q - 1} for s, q in sizes],
            },
        ],
    }
    body.update(over)
    return body


def test_a_seller_adds_their_own_product_and_the_warehouse_confirms_it_arrived(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The whole line, in the order it happens.

    A seller adds a product with its photographs; it reaches the warehouse as
    *their* goods, declared and not yet counted; the warehouse counts it and
    **that** is what puts it in the shop. Approval here is not the platform
    deciding whether a card may exist — it is somebody confirming the box
    turned up.

    Six calls decomposed into one on purpose: create the card, post each
    image, post each colour, post each size, open the offer, declare the batch.
    Each of those is a chance to be the last one that worked, and the result of
    a half-run is a seller staring at a product nobody can buy with no way to
    tell which half is missing.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900120001")
    seller_id, mine = _linked_seller(staff, "Sotuvchi Do'kon", "+998900120002")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Mening futbolkam"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    listing = made.json()
    product_id = listing["id"]

    # The SKU is ours: a seller does not think in stock codes and should not
    # have to invent a unique one.
    assert listing["sku"].startswith("S"), listing["sku"]
    assert listing["price"] == 149_000

    # Two colours, five sizes each — ten cells that get counted.
    assert len(listing["stock"]) == 10
    assert {cell["color_label"] for cell in listing["stock"]} == {"Oq", "Qora"}
    assert sum(cell["declared"] for cell in listing["stock"]) == 28 + 23

    # Declared is a promise. Nothing is on the shelf, and the quantities in the
    # request went onto supply lines rather than onto a stock figure.
    assert listing["on_hand_total"] == 0
    assert all(cell["on_hand"] == 0 for cell in listing["stock"])
    assert listing["supply_code"] and listing["supply_status"] == "declared"

    # The pictures survived in the order they were given, first one primary.
    assert len(listing["images"]) == 2

    # Waiting on the warehouse, and the seller is told so in their own words.
    assert listing["stage"] == "awaiting_warehouse"
    assert listing["stage_label"]

    # And it is not in the shop. Not the listing, not the product page.
    assert client.get(f"{API}/products/{product_id}").status_code == 404
    shop = client.get(
        f"{API}/products", params={"q": "Mening futbolkam", "show_sold_out": True}
    ).json()
    assert product_id not in [row["id"] for row in shop["items"]]

    # The warehouse sees the batch, and whose goods it is.
    queue = client.get(
        f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
    )
    assert queue.status_code == 200, queue.text
    batch = next(
        row for row in queue.json() if row["code"] == listing["supply_code"]
    )
    assert batch["seller"]["id"] == seller_id
    assert len(batch["lines"]) == 10

    # Counting it in is the confirmation, and the confirmation is what sells it.
    received = client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": row["declared_quantity"]}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text

    assert client.get(f"{API}/products/{product_id}").status_code == 200
    now = client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=mine
    ).json()
    assert now["stage"] == "on_sale"
    assert now["on_hand_total"] == 51
    # The card's own figures are a cache of the offers, and they were
    # recomputed when it became visible rather than left describing a product
    # that was not in the shop.
    page = client.get(f"{API}/products/{product_id}").json()
    assert page["price"] == 149_000
    assert page["in_stock"] is True
    assert len([v for v in page["variants"] if v["kind"] == "color"]) == 2

    # The move is logged as a status change like any other, with the reason.
    rows = _audit_rows("product.status", product_id)
    assert rows and listing["supply_code"] in rows[-1].note
    assert not _stock_is_consistent()


def test_buying_one_size_takes_it_off_that_size_and_no_other(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The invariant the grid exists for.

    A shop that has sold its last white M has sold it in white. If the count
    came off the product's total, or off the colour, the page would go on
    offering that M out of the black ones — and there is no working out
    afterwards which shirt the customer got.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900120011")
    _, mine = _linked_seller(staff, "Razmer Do'kon", "+998900120012")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Razmer futbolkasi"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]
    batch_code = made.json()["supply_code"]

    batch = next(
        row
        for row in client.get(f"{API}/staff/supplies", headers=warehouse).json()
        if row["code"] == batch_code
    )
    client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": row["declared_quantity"]}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )

    variants = client.get(f"{API}/products/{product_id}").json()["variants"]
    white = next(v for v in variants if v["label"] == "Oq")
    black = next(v for v in variants if v["label"] == "Qora")
    white_m = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "M" and v["parent_id"] == white["id"]
    )
    black_m = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "M" and v["parent_id"] == black["id"]
    )
    white_l = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "L" and v["parent_id"] == white["id"]
    )

    def cells() -> dict[int, int]:
        rows = client.get(
            f"{API}/staff/catalog/listings/{product_id}", headers=mine
        ).json()["stock"]
        return {row["variant_id"]: row["on_hand"] for row in rows}

    before = cells()
    assert before[white_m["id"]] == 9
    assert before[black_m["id"]] == 8
    assert before[white_l["id"]] == 7

    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "variant_id": white_m["id"],
            "color_variant_id": white["id"],
            "quantity": 2,
        },
        headers=auth,
    )
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    placed = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert placed.status_code == 201, placed.text

    after = cells()
    assert after[white_m["id"]] == 7, "the white M, and by exactly two"
    assert after[black_m["id"]] == 8, "the black M did not move"
    assert after[white_l["id"]] == 7, "nor did the white L"
    assert sum(after.values()) == sum(before.values()) - 2
    assert not _stock_is_consistent()


def test_a_listing_refuses_what_would_make_the_shelf_uncountable(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The three refusals, each protecting a warehouse invariant.

    Mixing sized and unsized colours puts some counts a level above where the
    ledger looks for them, with no way to say how a colour's stock divides
    between sizes it has not got. A repeated colour or size makes two cells
    that mean the same thing, and the sum of the colours stops equalling the
    offer's total the first time either is counted.
    """
    _, mine = _linked_seller(staff, "Qoida Do'kon", "+998900120022")
    body = _listing_body(client, mine, "Qoida futbolkasi")

    mixed = {**body, "colors": [
        {**body["colors"][0]},
        {**body["colors"][1], "sizes": []},
    ]}
    refused = client.post(f"{API}/staff/catalog/listings", json=mixed, headers=mine)
    assert refused.status_code == 400
    assert "razmer" in refused.json()["detail"].lower()

    twice = {**body, "colors": [body["colors"][0], {**body["colors"][1], "label": "Oq"}]}
    assert client.post(
        f"{API}/staff/catalog/listings", json=twice, headers=mine
    ).status_code == 400

    dup_size = {**body, "colors": [
        {**body["colors"][0],
         "sizes": [{"label": "M", "quantity": 1}, {"label": "m", "quantity": 2}]},
    ]}
    assert client.post(
        f"{API}/staff/catalog/listings", json=dup_size, headers=mine
    ).status_code == 400

    # A picture is not optional: a card with no photograph is a card nobody taps.
    assert client.post(
        f"{API}/staff/catalog/listings", json={**body, "images": []}, headers=mine
    ).status_code == 400

    # And neither is a picture *per colour*. The shopper's page swaps the hero
    # when a swatch is tapped, so a colour with nothing behind it leaves them
    # looking at the previous one — they tap "Qora", see a white shirt, and buy
    # the wrong thing or nothing. The refusal names the colour, because a seller
    # with eight of them should not have to guess which is short.
    naked = {**body, "colors": [
        body["colors"][0],
        {**body["colors"][1], "image_url": None},
    ]}
    refused = client.post(f"{API}/staff/catalog/listings", json=naked, headers=mine)
    assert refused.status_code == 400, refused.text
    said = refused.json()["detail"]
    assert body["colors"][1]["label"] in said, said
    assert body["colors"][0]["label"] not in said, said

    # Somebody else's door.
    assert client.post(
        f"{API}/staff/catalog/listings", json=body, headers=admin
    ).status_code == 400, "an admin has no shop of their own"
    assert client.get(f"{API}/staff/catalog/listings").status_code == 401


def test_a_seller_reads_the_reason_their_product_was_refused(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refusal is a sentence the seller is owed.

    They are being asked to fix something; without the reason they are being
    asked to guess. ``moderation_note`` has always been on the row — what was
    missing was anywhere for a seller to read it. The refusal comes from the
    warehouse turning the batch away, which is the only thing that refuses a
    product now: see ``app.routers.warehouse.cancel_supply``.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900120031")
    _, mine = _linked_seller(staff, "Sabab Do'kon", "+998900120032")
    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Sababli futbolka"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    listing = made.json()
    product_id = listing["id"]

    batch = next(
        row
        for row in client.get(
            f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
        ).json()
        if row["code"] == listing["supply_code"]
    )
    refused = client.post(
        f"{API}/staff/supplies/{batch['id']}/cancel",
        json={"reason": "Rasmda tovar ko'rinmaydi"},
        headers=warehouse,
    )
    assert refused.status_code == 200, refused.text

    mine_rows = client.get(f"{API}/staff/catalog/listings", headers=mine)
    assert mine_rows.status_code == 200, mine_rows.text
    row = next(r for r in mine_rows.json() if r["id"] == product_id)
    assert row["stage"] == "rejected"
    assert row["moderation_note"] == "Rasmda tovar ko'rinmaydi"
    assert row["stage_label"]

    # And a refused product is nobody else's to read.
    _, theirs = _linked_seller(staff, "Boshqa Do'kon", "+998900120042")
    assert product_id not in [
        r["id"] for r in client.get(f"{API}/staff/catalog/listings", headers=theirs).json()
    ]
    assert client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=theirs
    ).status_code == 404


# ================================= the goods after the refund: B2 and B3

# A refund answers the customer. It answers nothing about the shirt, which is
# in a box at the warehouse belonging to a seller nobody has asked anything
# yet. Two people answer for it in turn — the warehouse says what arrived, the
# seller says what to do about it — and these hold that pair together with the
# other half of receiving a batch: refusing one.


def _received_listing(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    *,
    title: str,
    seller_name: str,
    seller_phone: str,
    warehouse_phone: str,
) -> tuple[int, dict[str, str], dict[str, str], dict]:
    """A seller's own product, counted in and on sale.

    Returns the product id, the seller's headers, the warehouse's, and the
    listing as the seller last saw it.
    """
    warehouse = staff(UserRole.WAREHOUSE, warehouse_phone)
    _, mine = _linked_seller(staff, seller_name, seller_phone)

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, title),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    listing = made.json()

    batch = next(
        row
        for row in client.get(
            f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
        ).json()
        if row["code"] == listing["supply_code"]
    )
    received = client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": row["declared_quantity"]}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return listing["id"], mine, warehouse, listing


def _sold_and_returned(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    product_id: int,
) -> dict:
    """One of the seller's shirts bought, delivered, and asked back.

    Left at ``approved``: the money is a separate decision from the goods, and
    every test below is about the goods.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/{product_id}").json()
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    size = next(
        v
        for v in product["variants"]
        if v["kind"] == "size" and v["parent_id"] == colour["id"]
    )
    added = client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "color_variant_id": colour["id"],
            "variant_id": size["id"],
            "quantity": 1,
        },
        headers=auth,
    )
    assert added.status_code in (200, 201), added.text

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", params={"days": 5}, headers=auth).json()
    slot = next(sl for day in days for sl in day["slots"] if sl["available"])
    order = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"]},
        headers=auth,
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    _to_the_door(client, operator, order_id)
    request = client.post(
        f"{API}/orders/{order_id}/return",
        json={"reason": "O'lchami kelmadi"},
        headers=auth,
    )
    assert request.status_code == 201, request.text
    approved = client.post(
        f"{API}/staff/returns/{request.json()['id']}/approve",
        json={},
        headers=operator,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def _shelf(product_id: int, variant_id: int | None = None) -> int:
    """What the winning offer holds, through the ledger's own reader."""
    with Session(engine) as session:
        offer = of.winning_offer(session, product_id) or of.offers_for(
            session, product_id, active_only=False
        )[0]
        return st.on_hand(session, offer.id, variant_id)


# ------------------------------------------------------- B2: refusing a batch


def test_a_refused_batch_takes_the_product_down_with_it(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """Receiving publishes; refusing is the other half of the same decision.

    Nothing was counted in, so nothing would ever publish this card — it would
    sit ``moderating`` for ever with nobody waiting on anything. The refusal
    takes it down and hands the seller the one sentence they need to fix it.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900130001")
    _, mine = _linked_seller(staff, "Rad Do'kon", "+998900130002")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Rad etiladigan futbolka"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    listing = made.json()
    product_id = listing["id"]

    batch = next(
        row
        for row in client.get(
            f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
        ).json()
        if row["code"] == listing["supply_code"]
    )

    # The reason is the whole content of the answer, so there is no refusing
    # without one.
    blank = client.post(
        f"{API}/staff/supplies/{batch['id']}/cancel",
        json={"reason": "   "},
        headers=warehouse,
    )
    assert blank.status_code == 400, blank.text

    refused = client.post(
        f"{API}/staff/supplies/{batch['id']}/cancel",
        json={"reason": "Kelgan tovar kartochkadagi rangda emas"},
        headers=warehouse,
    )
    assert refused.status_code == 200, refused.text
    assert refused.json()["status"] == "cancelled"

    row = client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=mine
    ).json()
    assert row["status"] == "rejected"
    assert row["stage"] == "rejected"
    assert row["moderation_note"] == "Kelgan tovar kartochkadagi rangda emas"

    # Not in the shop, and the seller was told rather than left to notice.
    assert client.get(f"{API}/products/{product_id}").status_code == 404
    with Session(engine) as session:
        seller = session.exec(select(Seller).where(Seller.name == "Rad Do'kon")).one()
        told = session.exec(
            select(Notification).where(Notification.user_id == seller.user_id)
        ).all()
    assert any(listing["supply_code"] in row.text for row in told)

    # Logged as a status change like any other, with the reason on it.
    rows = _audit_rows("product.status", product_id)
    assert rows and rows[-1].new_value == "rejected"
    assert "rangda emas" in rows[-1].note


def test_refusing_a_later_batch_leaves_a_product_that_is_already_selling(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A card in the shop has stock from an earlier batch.

    Refusing a second pallet is not a reason to stop selling what is on the
    shelf, and taking the card down would be exactly that.
    """
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Ikkinchi partiyali futbolka",
        seller_name="Ikki Partiya",
        seller_phone="+998900130012",
        warehouse_phone="+998900130011",
    )
    on_sale = client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=mine
    ).json()
    assert on_sale["stage"] == "on_sale"

    offer_id = on_sale["offer_id"]
    with Session(engine) as session:
        leaf = of.leaf_variants(session, product_id)[0].id
    second = client.post(
        f"{API}/staff/supplies",
        json={
            "note": "qo'shimcha",
            "lines": [
                {"offer_id": offer_id, "variant_id": leaf, "quantity": 5}
            ],
        },
        headers=mine,
    )
    assert second.status_code == 201, second.text

    refused = client.post(
        f"{API}/staff/supplies/{second.json()['id']}/cancel",
        json={"reason": "Yetib kelmadi"},
        headers=warehouse,
    )
    assert refused.status_code == 200, refused.text

    still = client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=mine
    ).json()
    assert still["status"] == "published"
    assert still["stage"] == "on_sale"
    assert client.get(f"{API}/products/{product_id}").status_code == 200


# ------------------------------------- B3: the inspection and the seller's answer


def test_the_warehouse_says_what_came_back_and_the_seller_sells_it_again(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The whole of B3, in the order it happens."""
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Qaytadigan futbolka",
        seller_name="Qaytish Do'kon",
        seller_phone="+998900130022",
        warehouse_phone="+998900130021",
    )
    request = _sold_and_returned(client, auth, operator, product_id)
    sold_shelf = _shelf(product_id)

    # Nobody has looked yet, so the seller has nothing to answer.
    waiting = client.get(f"{API}/staff/returns/{request['id']}", headers=mine).json()
    assert waiting["inspection"] is None
    assert waiting["seller_decisions"] == []
    assert waiting["seller_name"] == "Qaytish Do'kon"
    assert waiting["product_title"] == "Qaytadigan futbolka"
    early = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "relist"},
        headers=mine,
    )
    assert early.status_code == 409, early.text

    # The warehouse opens the parcel.
    looked = client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "ok", "note": "Yorliqlari joyida"},
        headers=warehouse,
    )
    assert looked.status_code == 200, looked.text
    seen = looked.json()
    assert seen["inspection"] == "ok"
    assert seen["inspection_label"]
    assert seen["decision_due_at"]
    assert seen["seller_decisions"] == ["relist", "take_back"]
    # Looking at it did not move the shelf: that is the seller's answer.
    assert _shelf(product_id) == sold_shelf

    # A second verdict is two people disagreeing about a shirt one of them is
    # holding, and the first answer is the one the seller was told.
    again = client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "damaged"},
        headers=warehouse,
    )
    assert again.status_code == 409, again.text

    # The seller was asked, in their own words, with the deadline in it.
    with Session(engine) as session:
        seller = session.exec(
            select(Seller).where(Seller.name == "Qaytish Do'kon")
        ).one()
        told = session.exec(
            select(Notification).where(Notification.user_id == seller.user_id)
        ).all()
    assert any(str(settings.return_decision_days) in row.text for row in told)

    # And the queue answers "what is waiting for me" for both of them.
    assert request["id"] in [
        row["id"]
        for row in client.get(
            f"{API}/staff/returns", params={"awaiting": "decision"}, headers=mine
        ).json()
    ]

    decided = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "relist"},
        headers=mine,
    )
    assert decided.status_code == 200, decided.text
    answer = decided.json()
    assert answer["seller_decision"] == "relist"
    assert answer["seller_decision_label"]
    assert answer["relisted"] is True
    assert answer["seller_decisions"] == []

    assert _shelf(product_id) == sold_shelf + 1
    assert not _stock_is_consistent()

    # Asked and answered — a second answer is not an overwrite.
    twice = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "take_back"},
        headers=mine,
    )
    assert twice.status_code == 409, twice.text

    rows = _audit_rows("return.decide", request["id"])
    assert rows and rows[-1].new_value == "relist"


def test_damaged_goods_do_not_go_back_on_sale(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The one decision the seller may not make, refused by the server and
    left off the buttons it hands the client."""
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Buzilgan futbolka",
        seller_name="Buzilgan Do'kon",
        seller_phone="+998900130032",
        warehouse_phone="+998900130031",
    )
    request = _sold_and_returned(client, auth, operator, product_id)
    sold_shelf = _shelf(product_id)

    seen = client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "damaged", "note": "Yoqasi yirilgan"},
        headers=warehouse,
    ).json()
    assert seen["inspection"] == "damaged"
    # No deadline: nothing relists something damaged, so there is no answer
    # that can expire.
    assert seen["decision_due_at"] is None
    assert seen["seller_decisions"] == ["take_back"]

    refused = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "relist"},
        headers=mine,
    )
    assert refused.status_code == 409, refused.text

    taken = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "take_back"},
        headers=mine,
    )
    assert taken.status_code == 200, taken.text
    assert taken.json()["relisted"] is False
    assert _shelf(product_id) == sold_shelf


def test_an_unanswered_deadline_puts_the_goods_back_on_sale(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Silence expires into the answer that costs the seller least.

    The clock is moved back rather than waited out, and the sweep runs off the
    side of a read because there is no scheduler here — see
    ``app.returns.sweep_overdue``.
    """
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Javobsiz futbolka",
        seller_name="Javobsiz Do'kon",
        seller_phone="+998900130042",
        warehouse_phone="+998900130041",
    )
    request = _sold_and_returned(client, auth, operator, product_id)
    sold_shelf = _shelf(product_id)

    assert client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "ok"},
        headers=warehouse,
    ).status_code == 200

    with Session(engine) as session:
        row = session.get(ReturnRequest, request["id"])
        row.decision_due_at = utcnow() - timedelta(days=1)
        session.add(row)
        session.commit()

    # Any returns screen settles it — this one is the seller's own.
    listed = client.get(f"{API}/staff/returns", headers=mine).json()
    swept = next(row for row in listed if row["id"] == request["id"])
    assert swept["seller_decision"] == "relist"
    assert swept["relisted"] is True
    assert _shelf(product_id) == sold_shelf + 1
    assert not _stock_is_consistent()

    rows = _audit_rows("return.decide", request["id"])
    assert rows and rows[-1].actor_id is None


def test_a_damaged_parcel_is_never_swept_back_onto_the_shelf(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A seller who ignores the question is asked again, not sold something
    broken."""
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Eskirgan futbolka",
        seller_name="Eskirgan Do'kon",
        seller_phone="+998900130052",
        warehouse_phone="+998900130051",
    )
    request = _sold_and_returned(client, auth, operator, product_id)
    sold_shelf = _shelf(product_id)

    client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "damaged"},
        headers=warehouse,
    )
    with Session(engine) as session:
        row = session.get(ReturnRequest, request["id"])
        # Even if a deadline somehow got onto it, the sweep is about whole
        # goods and only whole goods.
        row.decision_due_at = utcnow() - timedelta(days=30)
        session.add(row)
        session.commit()

    still = next(
        row
        for row in client.get(f"{API}/staff/returns", headers=mine).json()
        if row["id"] == request["id"]
    )
    assert still["seller_decision"] is None
    assert still["relisted"] is False
    assert _shelf(product_id) == sold_shelf


def test_one_shirt_back_is_one_shirt_back(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two people can agree about the same parcel minutes apart.

    An operator refunding with ``restock: true`` and a seller choosing
    ``relist`` are two roads to the same shelf, walked by people who do not
    know about each other. The decision is recorded both times; the count
    moves once.
    """
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Ikki marta futbolka",
        seller_name="Ikki Marta",
        seller_phone="+998900130062",
        warehouse_phone="+998900130061",
    )
    request = _sold_and_returned(client, auth, operator, product_id)
    sold_shelf = _shelf(product_id)

    paid = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Butun holida qaytdi"},
        headers=operator,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["relisted"] is True
    assert _shelf(product_id) == sold_shelf + 1

    client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "ok"},
        headers=warehouse,
    )
    decided = client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "relist"},
        headers=mine,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["seller_decision"] == "relist"

    # The seller's answer is on the record and the shelf did not move twice.
    assert _shelf(product_id) == sold_shelf + 1
    assert _audit_rows("return.decide", request["id"])
    assert not _stock_is_consistent()


def test_a_seller_reads_only_returns_on_their_own_goods(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Not a filter they choose — the only rows that exist for them.

    And an id that is not theirs is a 404 rather than a 403: "there is one,
    and it is somebody else's" is a fact about a competitor's returns.
    """
    product_id, mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Mening qaytishim",
        seller_name="Menikidir",
        seller_phone="+998900130072",
        warehouse_phone="+998900130071",
    )
    request = _sold_and_returned(client, auth, operator, product_id)

    _, theirs = _linked_seller(staff, "Boshqa Qaytish", "+998900130073")
    assert request["id"] not in [
        row["id"] for row in client.get(f"{API}/staff/returns", headers=theirs).json()
    ]
    assert client.get(
        f"{API}/staff/returns/{request['id']}", headers=theirs
    ).status_code == 404
    assert client.post(
        f"{API}/staff/returns/{request['id']}/decide",
        json={"decision": "take_back"},
        headers=theirs,
    ).status_code == 404

    # The operator and the warehouse read every parcel, whoever sent it.
    for headers in (operator, warehouse):
        assert request["id"] in [
            row["id"]
            for row in client.get(f"{API}/staff/returns", headers=headers).json()
        ]

    # A customer's own request is on their own orders screen, not this one.
    assert client.get(f"{API}/staff/returns", headers=auth).status_code == 403


def test_nothing_is_inspected_before_it_could_have_arrived(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A request still being decided is not a parcel on a desk."""
    product_id, _mine, warehouse, _ = _received_listing(
        client,
        staff,
        title="Kelmagan futbolka",
        seller_name="Kelmagan Do'kon",
        seller_phone="+998900130082",
        warehouse_phone="+998900130081",
    )
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/{product_id}").json()
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    size = next(
        v
        for v in product["variants"]
        if v["kind"] == "size" and v["parent_id"] == colour["id"]
    )
    client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "color_variant_id": colour["id"],
            "variant_id": size["id"],
            "quantity": 1,
        },
        headers=auth,
    )
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", params={"days": 5}, headers=auth).json()
    slot = next(sl for day in days for sl in day["slots"] if sl["available"])
    order_id = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"]},
        headers=auth,
    ).json()["id"]
    _to_the_door(client, operator, order_id)
    request = client.post(
        f"{API}/orders/{order_id}/return",
        json={"reason": "Kerak emas"},
        headers=auth,
    ).json()

    too_early = client.post(
        f"{API}/staff/returns/{request['id']}/inspect",
        json={"result": "ok"},
        headers=warehouse,
    )
    assert too_early.status_code == 409, too_early.text


def test_the_order_queue_is_read_by_four_roles_and_a_seller_sees_only_their_own(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """One queue, four jobs.

    The operator runs it, the warehouse picks from it, the admin does either,
    and the seller watches their own goods go out. It used to be the
    operator's alone, which left the warehouse with no list to pick from and a
    seller unable to see that anything had sold.

    A seller's narrowing is not a filter they chose — it is the only set of
    orders that exists for them — and an order that is not theirs is a 404
    rather than an empty page, because "there is one, and it is somebody
    else's" is a fact about a competitor's sales.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900140001")
    product_id, mine, _wh, _ = _received_listing(
        client,
        staff,
        title="Navbatdagi futbolka",
        seller_name="Navbat Do'kon",
        seller_phone="+998900140002",
        warehouse_phone="+998900140003",
    )

    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/{product_id}").json()
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    size = next(
        v
        for v in product["variants"]
        if v["kind"] == "size" and v["parent_id"] == colour["id"]
    )
    added = client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "color_variant_id": colour["id"],
            "variant_id": size["id"],
            "quantity": 1,
        },
        headers=auth,
    )
    assert added.status_code in (200, 201), added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order_id = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()["id"]

    # Everyone who works the queue can read it.
    for headers in (operator, warehouse, mine):
        got = client.get(f"{API}/staff/orders", headers=headers)
        assert got.status_code == 200, got.text

    # The seller's own is the only one on their list.
    theirs = client.get(f"{API}/staff/orders", headers=mine).json()
    assert [row["id"] for row in theirs["items"]] == [order_id]
    assert theirs["total"] == 1
    assert client.get(f"{API}/staff/orders/{order_id}", headers=mine).status_code == 200

    # Another seller's list does not have it, and neither does their detail.
    _, theirs_headers = _linked_seller(staff, "Chetdagi Do'kon", "+998900140004")
    other = client.get(f"{API}/staff/orders", headers=theirs_headers).json()
    assert other["items"] == [] and other["total"] == 0
    assert client.get(
        f"{API}/staff/orders/{order_id}", headers=theirs_headers
    ).status_code == 404

    # A seller may not move one along. Reading a queue is not working it.
    assert client.post(
        f"{API}/staff/orders/{order_id}/status",
        json={"status": "packing"},
        headers=mine,
    ).status_code == 403

    # The warehouse picks it and hands it over, because that is what a person
    # at a bench does — once the operator has said who is carrying it.
    _to_the_door(client, operator, order_id, delivered=False)
    # And does not call off a sale from the packing bench. That decision needs
    # somebody who can phone the customer.
    refused = client.post(
        f"{API}/staff/orders/{order_id}/status",
        json={"status": "cancelled", "note": "shunchaki"},
        headers=warehouse,
    )
    assert refused.status_code == 403, refused.text
    assert client.post(
        f"{API}/staff/orders/{order_id}/status",
        json={"status": "cancelled", "note": "mijoz javob bermadi"},
        headers=operator,
    ).status_code == 200

    # A customer is not staff, whatever they can see of their own order.
    assert client.get(f"{API}/staff/orders", headers=auth).status_code == 403


def test_a_batch_line_names_the_cell_and_not_only_the_size(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """Two colours of one shirt must not read the same on the receive screen.

    A size's own label is "S", so a two-colour, three-size batch produced six
    lines reading S, M, L, S, M, L — with somebody at the warehouse typing a
    count against each. Two identical rows on the screen where the counting
    happens is the shape of a miscount.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900150001")
    _, mine = _linked_seller(staff, "Yorliq Do'kon", "+998900150002")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Yorliqli futbolka"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    batch = next(
        row
        for row in client.get(
            f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
        ).json()
        if row["code"] == made.json()["supply_code"]
    )

    labels = [line["variant_label"] for line in batch["lines"]]
    assert len(labels) == len(set(labels)), labels
    assert "Oq · S" in labels and "Qora · S" in labels


def test_a_seller_reads_the_categories_they_have_to_file_a_product_under(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The product form cannot exist without this list.

    A seller opening their own product picks a category and, optionally, a
    brand. Both lists were admin-only, so the field on their form had nothing
    in it — and an empty select that looks filled in is worse than a refusal.

    Reading, not writing. Somebody else's vocabulary is not theirs to edit.
    """
    _, mine = _linked_seller(staff, "Turkum Do'kon", "+998900160001")

    for path in ("/staff/catalog/categories", "/staff/catalog/brands"):
        got = client.get(f"{API}{path}", headers=mine)
        assert got.status_code == 200, got.text
        assert got.json(), path
        assert client.get(f"{API}{path}", headers=admin).status_code == 200
        # Not staff who have no product to file, and not a customer.
        assert client.get(f"{API}{path}", headers=operator).status_code == 403
        assert client.get(f"{API}{path}", headers=auth).status_code == 403
        assert client.get(f"{API}{path}").status_code == 401

    # And writing one stays the admin's.
    body = {"slug": "sotuvchi-yozdi", "name": "Sotuvchi yozdi"}
    assert client.post(
        f"{API}/staff/catalog/categories", json=body, headers=mine
    ).status_code == 403
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-brend", headers=mine
    ).status_code == 403
