"""End-to-end coverage of the shop as one company with one warehouse.

The suite that stood here was written against a marketplace: sellers, offers,
statements, a seeded catalogue of sixty products with ids the tests named. All
three are gone, and so the tests that named them are gone with them — not to
make anything pass, but because they asserted things that are no longer true
of this system.

What replaced them follows the same shape as the code. **The database starts
empty**, so a test that needs goods builds them: a category, a card, its
variants, and a market run booked in through the same doors the warehouse
uses. Nothing here reaches into the ledger to set a count — the one exception
is ``_variants``, which writes the rows an editor's screen will write in a
later phase and which has no door of its own yet.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import stock as st
from app.db import engine
from app.models import (
    AuditLog,
    CartItem,
    Product,
    ProductImage,
    ProductVariant,
    ReturnRequest,
    StockMovement,
    StockMovementKind,
    Supply,
    SupplyStatus,
    User,
    UserRole,
    VariantKind,
)
from tests.conftest import COURIER_PHONE

API = "/api/v1"


# --------------------------------------------------------------------------- helpers


def _category(client: TestClient, admin: dict[str, str], slug: str = "krossovkalar") -> str:
    made = client.post(
        f"{API}/staff/catalog/categories",
        json={"slug": slug, "name": "Krossovkalar", "icon": "shoe"},
        headers=admin,
    )
    assert made.status_code in (201, 409), made.text
    return slug


def _card(
    client: TestClient,
    admin: dict[str, str],
    *,
    sku: str,
    price: int = 500_000,
    category: str = "krossovkalar",
) -> dict:
    """A card, written the way the owner writes one: as a draft."""
    _category(client, admin, category)
    made = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": sku,
            "title": "Krossovka Alfa",
            "category_slug": category,
            "price": price,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _variants(
    product_id: int, colours: list[str], sizes: list[str], *, price: int = 500_000
) -> dict[str, int]:
    """The colour × size grid, written straight into the database.

    The product editor grows a door for this in a later phase; until then the
    rows have to come from somewhere, and a fixture that fakes the screen is
    honest in a way that faking the ledger would not be. **No stock is set
    here** — every count in this suite arrives through a market run.

    Returns the ids by label: ``{"Qora": 4, "Qora / 42": 5, …}``.
    """
    ids: dict[str, int] = {}
    with Session(engine) as session:
        for c_sort, colour in enumerate(colours):
            colour_row = ProductVariant(
                product_id=product_id,
                kind=VariantKind.COLOR,
                label=colour,
                value=colour.lower(),
                price=price,
                sort=c_sort,
            )
            session.add(colour_row)
            session.commit()
            session.refresh(colour_row)
            ids[colour] = colour_row.id
            for s_sort, size in enumerate(sizes):
                size_row = ProductVariant(
                    product_id=product_id,
                    kind=VariantKind.SIZE,
                    label=size,
                    value=size,
                    price=price,
                    parent_id=colour_row.id,
                    sort=s_sort,
                )
                session.add(size_row)
                session.commit()
                session.refresh(size_row)
                ids[f"{colour} / {size}"] = size_row.id
    return ids


def _photograph(product_id: int) -> None:
    """One picture on the card, which is what lets it leave ``draft``."""
    with Session(engine) as session:
        session.add(ProductImage(product_id=product_id, url="products/alfa.jpg"))
        session.commit()


def _book_in(
    client: TestClient,
    warehouse: dict[str, str],
    lines: list[tuple[int, int]],
    *,
    place: str = "Chorsu",
    unit_cost: int = 200_000,
) -> dict:
    """A market run: sacks in, sorted, closed. The only way stock exists."""
    started = client.post(
        f"{API}/staff/supplies",
        json={"sacks": 1, "place": place, "transport_cost": 30_000},
        headers=warehouse,
    )
    assert started.status_code == 201, started.text
    run = started.json()[0]

    sorted_ = client.put(
        f"{API}/staff/supplies/{run['id']}/lines",
        json={
            "lines": [
                {"variant_id": variant_id, "quantity": qty, "unit_cost": unit_cost}
                for variant_id, qty in lines
            ]
        },
        headers=warehouse,
    )
    assert sorted_.status_code == 200, sorted_.text

    closed = client.post(f"{API}/staff/supplies/{run['id']}/receive", headers=warehouse)
    assert closed.status_code == 200, closed.text
    return closed.json()


def _publish(client: TestClient, admin: dict[str, str], product_id: int) -> None:
    _photograph(product_id)
    put = client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert put.status_code == 200, put.text


def _on_sale(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    *,
    sku: str,
    stock: int = 5,
    price: int = 500_000,
) -> tuple[dict, dict[str, int]]:
    """The whole road: a card, its grid, a market run, and into the shop."""
    card = _card(client, admin, sku=sku, price=price)
    ids = _variants(card["id"], ["Qora", "Oq"], ["42", "43"], price=price)
    _book_in(
        client,
        warehouse,
        [(ids["Qora / 42"], stock), (ids["Oq / 42"], stock)],
    )
    _publish(client, admin, card["id"])
    return card, ids


def _address(client: TestClient, auth: dict[str, str]) -> int:
    made = client.post(
        f"{API}/addresses",
        json={"line": "Toshkent, Amir Temur 108", "title": "Uy"},
        headers=auth,
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _order(
    client: TestClient,
    auth: dict[str, str],
    product_id: int,
    variant_id: int,
    *,
    quantity: int = 1,
    payment: str = "card",
) -> dict:
    added = client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity": quantity,
        },
        headers=auth,
    )
    assert added.status_code == 201, added.text
    placed = client.post(
        f"{API}/orders",
        json={"address_id": _address(client, auth), "payment_method": payment},
        headers=auth,
    )
    assert placed.status_code == 201, placed.text
    return placed.json()


def _courier_headers(client: TestClient) -> dict[str, str]:
    asked = client.post(f"{API}/auth/otp/request", json={"phone": COURIER_PHONE}).json()
    tokens = client.post(
        f"{API}/auth/otp/verify",
        json={"phone": COURIER_PHONE, "code": asked["dev_code"]},
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

    ``shipped`` is not a move staff can make: the handover *is* the courier
    picking the parcel up, so every road to a delivered order goes through a
    courier choosing it.
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
        headers={**courier, "Idempotency-Key": f"take-{order_id}"},
    )
    assert took.status_code == 200, took.text
    assert took.json()["status"] == "shipped"

    if delivered:
        done = client.post(
            f"{API}/staff/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=staff_headers,
        )
        assert done.status_code == 200, done.text
    return courier


def _shelf(variant_id: int) -> int:
    with Session(engine) as session:
        return session.get(ProductVariant, variant_id).stock_left


def _ledger(variant_id: int) -> int:
    with Session(engine) as session:
        return st.on_hand(session, variant_id)


# --------------------------------------------------------------------------- the door


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_phone_login_creates_a_customer(client: TestClient) -> None:
    phone = "+998901110001"
    asked = client.post(f"{API}/auth/otp/request", json={"phone": phone})
    assert asked.status_code == 200, asked.text
    code = asked.json()["dev_code"]
    assert code == "123456"

    tokens = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    )
    assert tokens.status_code == 200, tokens.text
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}

    me = client.get(f"{API}/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["phone"] == phone


def test_a_wrong_code_is_refused(client: TestClient) -> None:
    phone = "+998901110002"
    client.post(f"{API}/auth/otp/request", json={"phone": phone})
    bad = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": "000000"})
    assert bad.status_code == 400


def test_staff_sign_in_the_same_way_customers_do(
    client: TestClient, admin: dict[str, str]
) -> None:
    me = client.get(f"{API}/staff/me", headers=admin)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "admin"


def test_a_customer_cannot_reach_the_backoffice(
    client: TestClient, auth: dict[str, str]
) -> None:
    assert client.get(f"{API}/staff/catalog/products", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/catalog/products").status_code == 401


# --------------------------------------------------------------------------- empty


def test_the_catalogue_starts_empty(client: TestClient) -> None:
    """No demo shop. The owner types their own products in.

    Asserted before anything else creates one — the seed writes accounts and
    two lists of reasons, and nothing that could be mistaken for a sale.
    """
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Product)).one() == 0

    listing = client.get(f"{API}/products")
    assert listing.status_code == 200
    assert listing.json()["items"] == []


def test_the_seed_writes_one_account_per_role() -> None:
    with Session(engine) as session:
        roles = {
            user.role
            for user in session.exec(select(User)).all()
            if user.phone.startswith("+9989000000")
        }
    assert roles == {UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.COURIER}


def test_the_reason_lists_are_seeded_and_translated(client: TestClient) -> None:
    uz = client.get(f"{API}/orders/reasons/cancel").json()
    assert len(uz) == 5
    ru = client.get(
        f"{API}/orders/reasons/cancel", headers={"Accept-Language": "ru"}
    ).json()
    assert ru[0]["label"] == "Передумал(а)"


# --------------------------------------------------------------------------- cards


def test_a_new_card_is_a_draft_and_the_apps_cannot_see_it(
    client: TestClient, admin: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-DRAFT")
    assert card["status"] == "draft"

    assert client.get(f"{API}/products/{card['id']}").status_code == 404
    ids = [p["id"] for p in client.get(f"{API}/products").json()["items"]]
    assert card["id"] not in ids


def test_a_card_with_no_photograph_stays_in_draft(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The rule, refused at the door rather than warned about.

    A catalogue of grey squares sells nothing, and market goods arrive with no
    pictures at all — so the only ones that will ever exist are the ones taken
    at the receiving desk.
    """
    card = _card(client, admin, sku="ALFA-NOPIC")
    refused = client.post(
        f"{API}/staff/catalog/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text

    _photograph(card["id"])
    allowed = client.post(
        f"{API}/staff/catalog/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "active"


def test_a_card_in_the_shop_is_visible_and_archiving_takes_it_out(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, _ = _on_sale(client, admin, warehouse, sku="ALFA-SHOP")

    shown = client.get(f"{API}/products/{card['id']}")
    assert shown.status_code == 200, shown.text
    assert shown.json()["in_stock"] is True

    archived = client.post(
        f"{API}/staff/catalog/products/{card['id']}/status",
        json={"status": "archived", "note": "sotilmadi"},
        headers=admin,
    )
    assert archived.status_code == 200, archived.text
    assert client.get(f"{API}/products/{card['id']}").status_code == 404


def test_a_card_cannot_jump_from_archived_to_active(
    client: TestClient, admin: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-JUMP")
    _photograph(card["id"])
    client.post(
        f"{API}/staff/catalog/products/{card['id']}/status",
        json={"status": "archived"},
        headers=admin,
    )
    refused = client.post(
        f"{API}/staff/catalog/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text


def test_the_same_sku_twice_is_refused(
    client: TestClient, admin: dict[str, str]
) -> None:
    _card(client, admin, sku="ALFA-DUP")
    again = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "ALFA-DUP",
            "title": "Boshqa nom",
            "category_slug": "krossovkalar",
            "price": 100_000,
        },
        headers=admin,
    )
    assert again.status_code == 409, again.text


def test_a_card_is_edited_without_touching_price_stock_or_status(
    client: TestClient, admin: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-EDIT")
    edited = client.patch(
        f"{API}/staff/catalog/products/{card['id']}",
        json={"title": "Krossovka Beta", "description": "Yozgi model"},
        headers=admin,
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["title"] == "Krossovka Beta"
    assert body["description"] == "Yozgi model"
    assert body["status"] == "draft"
    assert body["price"] == card["price"]


def test_a_card_is_written_in_three_languages(
    client: TestClient, admin: dict[str, str]
) -> None:
    _category(client, admin)
    made = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "ALFA-RU",
            "title": "Krossovka Alfa",
            "category_slug": "krossovkalar",
            "price": 400_000,
            "translations": {
                "ru": {"title": "Кроссовки Альфа"},
                "en": {"title": "Alfa trainers"},
            },
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]
    _publish(client, admin, product_id)

    ru = client.get(f"{API}/products/{product_id}", headers={"Accept-Language": "ru"})
    assert ru.json()["title"] == "Кроссовки Альфа"
    en = client.get(f"{API}/products/{product_id}", headers={"Accept-Language": "en"})
    assert en.json()["title"] == "Alfa trainers"


def test_the_catalogue_summary_counts_every_state(
    client: TestClient, admin: dict[str, str]
) -> None:
    counts = client.get(f"{API}/staff/catalog/summary", headers=admin)
    assert counts.status_code == 200, counts.text
    assert set(counts.json()["counts"]) == {"draft", "active", "archived"}


# --------------------------------------------------------------------------- market runs


def test_sacks_arrive_as_drafts_one_row_each(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Thirty seconds at the door, and five sacks are five rows.

    They will be opened on different evenings by different people; a run that
    can only be closed all at once stays open until the last sack is dealt
    with.
    """
    started = client.post(
        f"{API}/staff/supplies",
        json={"sacks": 3, "place": "Ippodrom", "transport_cost": 50_000},
        headers=warehouse,
    )
    assert started.status_code == 201, started.text
    runs = started.json()
    assert len(runs) == 3
    assert {run["status"] for run in runs} == {"draft"}
    assert {run["place"] for run in runs} == {"Ippodrom"}
    assert [run["age_minutes"] for run in runs] == [0, 0, 0]
    assert sum(run["transport_cost"] for run in runs) == 50_000


def test_an_unsorted_sack_is_not_stock(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-SACK")
    ids = _variants(card["id"], ["Qora"], ["42"])
    client.post(f"{API}/staff/supplies", json={"sacks": 1}, headers=warehouse)

    assert _shelf(ids["Qora / 42"]) == 0
    assert _ledger(ids["Qora / 42"]) == 0
    with Session(engine) as session:
        assert session.get(Product, card["id"]).in_stock is False


def test_sorting_replaces_the_lines_rather_than_adding_to_them(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-SORT")
    ids = _variants(card["id"], ["Qora"], ["42", "43"])
    run = client.post(f"{API}/staff/supplies", json={"sacks": 1}, headers=warehouse).json()[0]

    first = client.put(
        f"{API}/staff/supplies/{run['id']}/lines",
        json={"lines": [{"variant_id": ids["Qora / 42"], "quantity": 4, "unit_cost": 100}]},
        headers=warehouse,
    )
    assert len(first.json()["lines"]) == 1

    second = client.put(
        f"{API}/staff/supplies/{run['id']}/lines",
        json={
            "lines": [
                {"variant_id": ids["Qora / 42"], "quantity": 4, "unit_cost": 100},
                {"variant_id": ids["Qora / 43"], "quantity": 2, "unit_cost": 100},
            ]
        },
        headers=warehouse,
    )
    assert len(second.json()["lines"]) == 2
    assert second.json()["status"] == "draft"


def test_a_run_with_nothing_sorted_cannot_be_closed(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    run = client.post(f"{API}/staff/supplies", json={"sacks": 1}, headers=warehouse).json()[0]
    refused = client.post(f"{API}/staff/supplies/{run['id']}/receive", headers=warehouse)
    assert refused.status_code == 409, refused.text


def test_closing_a_run_is_what_brings_the_goods_into_existence(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-CLOSE")
    ids = _variants(card["id"], ["Qora"], ["42", "43"])
    closed = _book_in(
        client, warehouse, [(ids["Qora / 42"], 6), (ids["Qora / 43"], 4)]
    )

    assert closed["status"] == "received"
    assert closed["total_cost"] == 10 * 200_000 + 30_000
    assert _shelf(ids["Qora / 42"]) == 6
    assert _ledger(ids["Qora / 42"]) == 6
    # A colour is the sum of its sizes, and nothing wrote a movement for it.
    assert _shelf(ids["Qora"]) == 10
    assert _ledger(ids["Qora"]) == 0

    with Session(engine) as session:
        kinds = session.exec(
            select(StockMovement.kind).where(
                StockMovement.variant_id == ids["Qora / 42"]
            )
        ).all()
    assert list(kinds) == [StockMovementKind.INTAKE]


def test_a_closed_run_is_not_reopened(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Correct it with an adjustment. The ledger keeps what was believed then."""
    card = _card(client, admin, sku="ALFA-ONCE")
    ids = _variants(card["id"], ["Qora"], ["42"])
    closed = _book_in(client, warehouse, [(ids["Qora / 42"], 3)])

    again = client.post(f"{API}/staff/supplies/{closed['id']}/receive", headers=warehouse)
    assert again.status_code == 409, again.text
    edited = client.put(
        f"{API}/staff/supplies/{closed['id']}/lines",
        json={"lines": [{"variant_id": ids["Qora / 42"], "quantity": 99}]},
        headers=warehouse,
    )
    assert edited.status_code == 409, edited.text
    assert _shelf(ids["Qora / 42"]) == 3


def test_a_sack_can_be_called_off_with_a_reason(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    run = client.post(f"{API}/staff/supplies", json={"sacks": 1}, headers=warehouse).json()[0]
    off = client.post(
        f"{API}/staff/supplies/{run['id']}/cancel",
        json={"reason": "Qop bo'sh chiqdi"},
        headers=warehouse,
    )
    assert off.status_code == 200, off.text
    assert off.json()["status"] == "cancelled"
    assert off.json()["note"] == "Qop bo'sh chiqdi"

    with Session(engine) as session:
        assert session.get(Supply, run["id"]).status is SupplyStatus.CANCELLED


def test_the_unsorted_queue_is_worked_from_the_front(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    client.post(f"{API}/staff/supplies", json={"sacks": 2}, headers=warehouse)
    drafts = client.get(
        f"{API}/staff/supplies", params={"status": "draft"}, headers=warehouse
    ).json()
    ids = [run["id"] for run in drafts]
    assert ids == sorted(ids)


def test_only_the_warehouse_books_goods_in(
    client: TestClient, auth: dict[str, str]
) -> None:
    assert client.post(f"{API}/staff/supplies", json={"sacks": 1}, headers=auth).status_code == 403


# --------------------------------------------------------------------------- the ledger


def test_the_shelf_is_the_sum_of_the_ledger(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The invariant, over a sequence with movements in both directions."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-LEDGER", stock=10)
    leaf = ids["Qora / 42"]

    client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": leaf, "quantity": 2, "reason": "Ombor devoridan tushdi"},
        headers=warehouse,
    )
    _book_in(client, warehouse, [(leaf, 5)])

    assert _shelf(leaf) == 13
    assert _ledger(leaf) == 13

    with Session(engine) as session:
        for variant in session.exec(
            select(ProductVariant).where(ProductVariant.kind == VariantKind.SIZE)
        ).all():
            assert variant.stock_left == st.on_hand(session, variant.id), variant.label


def test_a_write_off_needs_a_reason(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Stock that left without one is indistinguishable from stock that was stolen."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-WRITEOFF")
    refused = client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": ids["Qora / 42"], "quantity": 1, "reason": ""},
        headers=warehouse,
    )
    assert refused.status_code == 422, refused.text


def test_a_write_off_is_audited_and_shows_in_the_ledger(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-AUDIT")
    leaf = ids["Qora / 42"]
    client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": leaf, "quantity": 1, "reason": "Suvda qoldi"},
        headers=warehouse,
    )

    ledger = client.get(
        f"{API}/staff/stock/movements",
        params={"variant_id": leaf, "kind": "write_off"},
        headers=warehouse,
    ).json()
    assert ledger["total"] == 1
    row = ledger["items"][0]
    assert row["quantity"] == -1
    assert row["reason"] == "Suvda qoldi"
    assert row["variant_label"] == "Qora · 42"

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.action == "stock.write_off",
                AuditLog.entity_id == leaf,
            )
        ).all()
    assert len(logged) == 1


def test_nothing_can_be_written_off_that_is_not_a_variant(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    missing = client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": 999_999, "quantity": 1, "reason": "yo'q"},
        headers=warehouse,
    )
    assert missing.status_code == 404


# --------------------------------------------------------------------------- the shop


def test_the_card_advertises_the_cheapest_of_its_variants(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The money is on the variant: a 43 can cost more than a 41."""
    card = _card(client, admin, sku="ALFA-PRICE", price=900_000)
    ids = _variants(card["id"], ["Qora"], ["42", "43"], price=900_000)
    with Session(engine) as session:
        cheap = session.get(ProductVariant, ids["Qora / 42"])
        cheap.price = 700_000
        session.add(cheap)
        session.commit()
    _book_in(client, warehouse, [(ids["Qora / 42"], 2), (ids["Qora / 43"], 2)])
    _publish(client, admin, card["id"])

    shown = client.get(f"{API}/products/{card['id']}").json()
    assert shown["price"] == 700_000


def test_the_card_carries_no_stock_of_its_own_but_reports_it(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SHELF", stock=4)
    assert not hasattr(Product, "stock_left")

    shown = client.get(f"{API}/products/{card['id']}").json()
    assert shown["stock_left"] == 8          # two colours, four each
    assert shown["in_stock"] is True


def test_the_listing_hides_what_cannot_be_bought(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SOLDOUT", stock=1)
    client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": ids["Qora / 42"], "quantity": 1, "reason": "brak"},
        headers=warehouse,
    )
    client.post(
        f"{API}/staff/stock/write-off",
        json={"variant_id": ids["Oq / 42"], "quantity": 1, "reason": "brak"},
        headers=warehouse,
    )

    ids_shown = [p["id"] for p in client.get(f"{API}/products").json()["items"]]
    assert card["id"] not in ids_shown
    with_sold_out = client.get(
        f"{API}/products", params={"show_sold_out": True}
    ).json()["items"]
    assert card["id"] in [p["id"] for p in with_sold_out]


def test_search_finds_a_card_by_its_title(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, _ = _on_sale(client, admin, warehouse, sku="ALFA-SEARCH")
    found = client.get(f"{API}/products", params={"q": "Krossovka"}).json()
    assert card["id"] in [p["id"] for p in found["items"]]

    typeahead = client.get(f"{API}/search/suggest", params={"q": "Kross"}).json()
    assert any("Krossovka" in row["title"] for row in typeahead)


# --------------------------------------------------------------------------- the basket


def test_a_basket_line_has_to_say_which_size(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    """A sale that names no variant takes the count off nothing at all."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-LEAF")
    vague = client.post(
        f"{API}/cart/items", json={"product_id": card["id"]}, headers=auth
    )
    assert vague.status_code == 422, vague.text


def test_a_basket_cannot_hold_more_than_there_are(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CAP", stock=2)
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 9},
        headers=auth,
    )
    assert added.status_code == 201, added.text
    line = added.json()["items"][0]
    assert line["quantity"] == 2
    assert line["unit_price"] == 500_000


def test_a_basket_holds_the_goods_off_everybody_else(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-HOLD", stock=1)
    client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 1},
        headers=auth,
    )

    other = sign_in("+998901110099")
    theirs = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 1},
        headers=other,
    )
    # The hold is not on the shelf — the goods are still there — but nobody
    # else may promise them.
    assert theirs.json()["items"][0]["stock_left"] == 0
    assert _shelf(ids["Qora / 42"]) == 1


def test_emptying_a_basket_releases_what_it_held(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-RELEASE", stock=1)
    client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 1},
        headers=auth,
    )
    with Session(engine) as session:
        assert (
            st.reserved(session, ids["Qora / 42"]) == 1
        )

    client.delete(f"{API}/cart", headers=auth)
    with Session(engine) as session:
        assert st.reserved(session, ids["Qora / 42"]) == 0
        assert session.exec(select(func.count()).select_from(CartItem)).one() >= 0


# --------------------------------------------------------------------------- orders


def test_a_paid_order_takes_the_goods_off_the_shelf(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SALE", stock=5)
    leaf = ids["Qora / 42"]
    _order(client, auth, card["id"], leaf, quantity=2)

    assert _shelf(leaf) == 3
    assert _ledger(leaf) == 3
    with Session(engine) as session:
        assert session.get(Product, card["id"]).sold_count == 2


def test_a_cash_order_holds_the_goods_rather_than_selling_them(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    """Selling on promise-of-cash is how a refusal at the door lost stock."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CASH", stock=5)
    leaf = ids["Qora / 42"]
    _order(client, auth, card["id"], leaf, quantity=2, payment="cash")

    assert _shelf(leaf) == 5
    with Session(engine) as session:
        assert st.reserved(session, leaf) == 2


def test_cancelling_an_order_puts_everything_back(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CANCEL", stock=5)
    leaf = ids["Qora / 42"]
    order = _order(client, auth, card["id"], leaf, quantity=2)

    off = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason": "Fikrimdan qaytdim"},
        headers=auth,
    )
    assert off.status_code == 200, off.text
    assert _shelf(leaf) == 5
    assert _ledger(leaf) == 5
    with Session(engine) as session:
        assert session.get(Product, card["id"]).sold_count == 0


def test_the_order_queue_is_worked_from_the_front(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-QUEUE", stock=5)
    _order(client, auth, card["id"], ids["Qora / 42"])
    _order(client, auth, card["id"], ids["Oq / 42"])

    queue = client.get(
        f"{API}/staff/orders", params={"status": "placed"}, headers=admin
    ).json()["items"]
    ids_in_order = [o["id"] for o in queue]
    assert ids_in_order == sorted(ids_in_order)

    history = client.get(f"{API}/staff/orders", headers=admin).json()["items"]
    newest = [o["id"] for o in history]
    assert newest == sorted(newest, reverse=True)


def test_the_warehouse_may_pack_but_not_cancel(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-BENCH", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    packed = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=warehouse,
    )
    assert packed.status_code == 200, packed.text

    called_off = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "bekor"},
        headers=warehouse,
    )
    assert called_off.status_code == 403, called_off.text


# --------------------------------------------------------------------------- the door


def test_a_courier_takes_a_parcel_and_delivers_it(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-DOOR", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"], payment="cash")

    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=admin,
    )
    courier = _courier_headers(client)
    board = client.get(f"{API}/courier/orders/available", headers=courier).json()
    assert order["id"] in [o["id"] for o in board]

    took = client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**courier, "Idempotency-Key": f"door-take-{order['id']}"},
    )
    assert took.status_code == 200, took.text

    delivered = client.post(
        f"{API}/courier/orders/{order['id']}/deliver",
        json={"recipient_name": "Aziz", "cash_collected": order["total"]},
        headers={**courier, "Idempotency-Key": f"door-give-{order['id']}"},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"
    # Cash at the door is when the goods actually leave.
    assert _shelf(ids["Qora / 42"]) == 4


def test_a_retried_delivery_replays_rather_than_selling_twice(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """The courier's phone has no signal, so the same request arrives twice."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-RETRY", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"], payment="cash")
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=admin,
    )
    courier = _courier_headers(client)
    key = f"retry-{order['id']}"
    client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**courier, "Idempotency-Key": f"take-{key}"},
    )

    body = {"recipient_name": "Aziz", "cash_collected": order["total"]}
    first = client.post(
        f"{API}/courier/orders/{order['id']}/deliver",
        json=body,
        headers={**courier, "Idempotency-Key": key},
    )
    second = client.post(
        f"{API}/courier/orders/{order['id']}/deliver",
        json=body,
        headers={**courier, "Idempotency-Key": key},
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert _shelf(ids["Qora / 42"]) == 4


def test_a_courier_earns_per_delivery(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-EARN", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])
    courier = _to_the_door(client, admin, order["id"])

    earned = client.get(f"{API}/courier/earnings", headers=courier)
    assert earned.status_code == 200, earned.text
    assert earned.json()["delivered_today"] >= 1


# --------------------------------------------------------------------------- returns


def test_a_return_is_asked_for_approved_and_refunded(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-RETURN", stock=5)
    leaf = ids["Qora / 42"]
    order = _order(client, auth, card["id"], leaf)
    _to_the_door(client, admin, order["id"])

    asked = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "O'lcham to'g'ri kelmadi"},
        headers=auth,
    )
    assert asked.status_code == 201, asked.text
    request_id = asked.json()["id"]

    approved = client.post(
        f"{API}/staff/returns/{request_id}/approve", json={}, headers=admin
    )
    assert approved.status_code == 200, approved.text

    refunded = client.post(
        f"{API}/staff/returns/{request_id}/refund",
        json={"restock": True, "note": "butun"},
        headers=admin,
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["refund_amount"] > 0
    assert _shelf(leaf) == 5


def test_goods_come_back_onto_the_shelf_exactly_once(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A refund that restocked and an inspection that passed are one shirt."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-TWICE", stock=5)
    leaf = ids["Qora / 42"]
    order = _order(client, auth, card["id"], leaf)
    _to_the_door(client, admin, order["id"])

    request_id = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Rasmga mos kelmadi"},
        headers=auth,
    ).json()["id"]
    client.post(f"{API}/staff/returns/{request_id}/approve", json={}, headers=admin)
    client.post(
        f"{API}/staff/returns/{request_id}/refund",
        json={"restock": True},
        headers=admin,
    )
    assert _shelf(leaf) == 5

    inspected = client.post(
        f"{API}/staff/returns/{request_id}/inspect",
        json={"result": "ok", "note": "butun"},
        headers=warehouse,
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["relisted"] is True
    assert _shelf(leaf) == 5


def test_a_damaged_return_does_not_go_back_on_sale(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-DAMAGED", stock=5)
    leaf = ids["Qora / 42"]
    order = _order(client, auth, card["id"], leaf)
    _to_the_door(client, admin, order["id"])

    request_id = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Nuqsonli yoki shikastlangan", "comment": "yirtilgan"},
        headers=auth,
    ).json()["id"]
    client.post(f"{API}/staff/returns/{request_id}/approve", json={}, headers=admin)
    client.post(
        f"{API}/staff/returns/{request_id}/refund",
        json={"restock": False},
        headers=admin,
    )
    inspected = client.post(
        f"{API}/staff/returns/{request_id}/inspect",
        json={"result": "damaged", "note": "yirtilgan"},
        headers=warehouse,
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["relisted"] is False
    assert _shelf(leaf) == 4


def test_a_parcel_is_inspected_once(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-INSPECT", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])
    _to_the_door(client, admin, order["id"])
    request_id = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Boshqa tovar keldi", "comment": "boshqa rang"},
        headers=auth,
    ).json()["id"]
    client.post(f"{API}/staff/returns/{request_id}/approve", json={}, headers=admin)

    first = client.post(
        f"{API}/staff/returns/{request_id}/inspect",
        json={"result": "ok"},
        headers=warehouse,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"{API}/staff/returns/{request_id}/inspect",
        json={"result": "damaged"},
        headers=warehouse,
    )
    assert second.status_code == 409, second.text

    with Session(engine) as session:
        assert session.get(ReturnRequest, request_id).inspection.value == "ok"


def test_the_returns_list_says_what_is_waiting_on_the_warehouse(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-WAITING", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])
    _to_the_door(client, admin, order["id"])
    request_id = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Sifati kutganimdek emas"},
        headers=auth,
    ).json()["id"]
    client.post(f"{API}/staff/returns/{request_id}/approve", json={}, headers=admin)

    waiting = client.get(
        f"{API}/staff/returns", params={"awaiting": "inspection"}, headers=warehouse
    ).json()
    assert request_id in [r["id"] for r in waiting]


# --------------------------------------------------------------------------- who works here


def test_a_role_is_granted_and_audited(
    client: TestClient, admin: dict[str, str], sign_in: Callable[[str], dict[str, str]]
) -> None:
    sign_in("+998901110055")
    with Session(engine) as session:
        user_id = session.exec(
            select(User).where(User.phone == "+998901110055")
        ).one().id

    changed = client.patch(
        f"{API}/staff/users/{user_id}/role",
        json={"role": "warehouse", "note": "yangi xodim"},
        headers=admin,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "warehouse"

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.action == "user.role", AuditLog.entity_id == user_id
            )
        ).all()
    assert len(logged) == 1
    assert logged[0].new_value == "warehouse"


def test_the_last_admin_cannot_be_stood_down(
    client: TestClient, admin: dict[str, str]
) -> None:
    with Session(engine) as session:
        admins = session.exec(
            select(User).where(
                User.role == UserRole.ADMIN, col(User.is_active).is_(True)
            )
        ).all()
        assert len(admins) == 1
        only = admins[0].id

    refused = client.patch(
        f"{API}/staff/users/{only}/role",
        json={"role": "warehouse"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text


def test_there_is_no_seller_role_left(client: TestClient, admin: dict[str, str]) -> None:
    assert {r.value for r in UserRole} == {"customer", "admin", "warehouse", "courier"}
    refused = client.patch(
        f"{API}/staff/users/1/role", json={"role": "seller"}, headers=admin
    )
    assert refused.status_code == 422


# --------------------------------------------------------------------------- the customer


def test_the_profile_overview_counts_what_is_left_of_it(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Saved cards went with the marketplace; the tile stays at nought.

    The apps are shipped and read this shape, so the field is answered rather
    than removed — a missing key is a crash on a phone nobody can rebuild.
    """
    overview = client.get(f"{API}/me/overview", headers=auth)
    assert overview.status_code == 200, overview.text
    assert overview.json()["cards_count"] == 0


def test_an_address_is_written_and_read_back(
    client: TestClient, auth: dict[str, str]
) -> None:
    address_id = _address(client, auth)
    mine = client.get(f"{API}/addresses", headers=auth).json()
    assert address_id in [a["id"] for a in mine]


def test_the_languages_the_apps_may_ask_for(client: TestClient) -> None:
    langs = {row["code"] for row in client.get(f"{API}/languages").json()}
    assert langs == {"uz", "ru", "en"}
