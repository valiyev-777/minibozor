"""End-to-end coverage of the shop as one company with one warehouse.

The suite that stood here was written against a marketplace: sellers, offers,
statements, a seeded catalogue of sixty products with ids the tests named. All
three are gone, and so the tests that named them are gone with them — not to
make anything pass, but because they asserted things that are no longer true
of this system.

What replaced them follows the same shape as the code. **The database starts
empty**, so a test that needs goods builds them: a category, a card, its
colour × size grid, and a market run booked in through the same doors the
warehouse uses. Nothing here reaches into the ledger to set a count — the one
exception is ``_variants``, which writes the rows an editor's screen will
write in a later phase and which has no door of its own yet.

**Every count is somewhere.** A quantity in this suite is always a quantity in
a place, and the two invariants at the bottom hold the whole thing together: a
placement equals its own movements, and a variant's shelf figure equals the
sum of its placements.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import locations as loc
from app import stock as st
from app.db import engine
from app.models import (
    AuditLog,
    Location,
    LocationKind,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    ReturnRequest,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    Supply,
    SupplyStatus,
    User,
    UserRole,
)
from app.seed import ADMIN_PHONE
from tests.conftest import COURIER_PHONE

API = "/api/v1"


# --------------------------------------------------------------------------- helpers


def _category(client: TestClient, admin: dict[str, str], slug: str = "krossovkalar") -> str:
    made = client.post(
        f"{API}/admin/categories",
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
        f"{API}/admin/products",
        json={
            # Titled after its own code, because the suite shares one shop and
            # forty cards called "Krossovka Alfa" cannot be told apart in a
            # listing that pages.
            "sku": sku,
            "title": f"Krossovka {sku}",
            "category_slug": category,
            "price": price,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _variants(
    client: TestClient,
    admin: dict[str, str],
    product_id: int,
    colours: list[str],
    sizes: list[str],
    *,
    price: int = 500_000,
) -> dict[str, int]:
    """The colour × size grid, through the door that generates one.

    Pick the colours, pick the sizes, get the variants — because typing twelve
    rows by hand for every shoe model is how a warehouse stops being used.
    **No stock is set here**: every count in this suite arrives through a
    market run.

    Returns the ids by label: ``{"Qora / 42": 5, …}``.
    """
    made = client.put(
        f"{API}/admin/products/{product_id}/variants",
        json={
            "colours": [{"colour": c, "hex": "#0E0F12"} for c in colours],
            "sizes": sizes,
            "price": price,
        },
        headers=admin,
    )
    assert made.status_code == 200, made.text
    return {
        f"{row['colour']} / {row['size']}": row["id"] for row in made.json()
    }


def _photograph(
    client: TestClient, admin: dict[str, str], product_id: int, *colours: str
) -> None:
    """A picture per colour, which is what lets a card leave ``draft``."""
    for colour in colours or ("",):
        hung = client.post(
            f"{API}/admin/products/{product_id}/images",
            json={"url": "products/alfa.jpg", "colour": colour},
            headers=admin,
        )
        assert hung.status_code == 201, hung.text


# The cell this suite's goods land in when a test does not care which one.
#
# `_book_in` used to put everything in QABUL, because a market run was booked
# into the receiving area and carried to a shelf afterwards. Goods land on a
# shelf in one action now, so they have to land *somewhere* nameable, and a
# cell nothing else in the suite asserts on keeps that from being a hidden
# dependency of every other test in the file.
BENCH = "C-03-04"


def _book_in(
    client: TestClient,
    warehouse: dict[str, str],
    lines: list[tuple[int, int]],
    *,
    place: str = "Chorsu",
    unit_cost: int = 200_000,
    code: str = BENCH,
) -> dict:
    """Stock onto a shelf, through the door the receiving desk actually uses.

    ``POST /warehouse/piles`` books a pile in and shelves it in one action,
    which is what the bench does: whoever opened the sack is standing at the
    cell holding the goods. The two-step door this helper used to drive —
    sort the lines, then close the run — booked goods into the receiving area
    for somebody to carry out again, and was removed with nothing calling it
    but this suite.

    The lines are given as ``(variant_id, quantity)`` because that is what
    every caller has to hand. A pile is one card and one colour, so the
    variants are looked up and grouped into one request per colour, and the
    sizes of a colour go in together the way they came out of the sack.

    Returns the receipt the **first** pile wrote — ``GET
    /warehouse/supplies/{id}``, the same shape the old helper returned — so a
    caller can still assert on what a run cost.
    """
    with Session(engine) as session:
        rows = [session.get(ProductVariant, variant_id) for variant_id, _ in lines]
    groups: dict[tuple[int, str], list[tuple[str, int]]] = {}
    for variant, (_, qty) in zip(rows, lines, strict=True):
        groups.setdefault((variant.product_id, variant.colour), []).append(
            (variant.size, qty)
        )

    first: dict | None = None
    for (product_id, colour), sizes in groups.items():
        made = client.post(
            f"{API}/warehouse/piles",
            json={
                "product_id": product_id,
                "colour": colour,
                "sizes": [{"size": size, "quantity": qty} for size, qty in sizes],
                "unit_cost": unit_cost,
                "location_code": code,
                "place": place,
                # The whole fare against the first pile, the way a market run
                # puts a taxi against the first sack.
                "transport_cost": 30_000 if first is None else 0,
            },
            headers={**warehouse, "Idempotency-Key": f"pile-{uuid4()}"},
        )
        assert made.status_code == 201, made.text
        if first is None:
            got = client.get(
                f"{API}/warehouse/supplies/{made.json()['run_id']}", headers=warehouse
            )
            assert got.status_code == 200, got.text
            first = got.json()
    return first


def _publish(
    client: TestClient, admin: dict[str, str], product_id: int, *colours: str
) -> None:
    _photograph(client, admin, product_id, *colours)
    put = client.post(
        f"{API}/admin/products/{product_id}/status",
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
    ids = _variants(client, admin, card["id"], ["Qora", "Oq"], ["42", "43"], price=price)
    _book_in(
        client,
        warehouse,
        [(ids["Qora / 42"], stock), (ids["Oq / 42"], stock)],
    )
    _publish(client, admin, card["id"], "Qora", "Oq")
    return card, ids


def _put_away(
    client: TestClient,
    warehouse: dict[str, str],
    variant_id: int,
    qty: int,
    code: str,
    frm: str = BENCH,
) -> dict:
    """Carry a quantity from the cell `_book_in` used to the one named.

    The default used to be ``QABUL``, because that is where a market run put
    the goods and the second walk was carrying them to a shelf. A pile lands
    on a shelf in one action, so what this now exercises is a mis-shelved
    pile being carried to the right cell.
    """
    done = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": variant_id,
            "qty": qty,
            "from_code": frm,
            "to_code": code,
        },
        headers={
            **warehouse,
            "Idempotency-Key": f"move-{variant_id}-{frm}-{code}-{qty}",
        },
    )
    assert done.status_code == 200, done.text
    return done.json()


def _address(client: TestClient, auth: dict[str, str]) -> int:
    made = client.post(
        f"{API}/addresses",
        json={"line": "Toshkent, Amir Temur 108", "title": "Uy"},
        headers=auth,
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _payment_card(
    client: TestClient,
    auth: dict[str, str],
    *,
    last4: str = "9012",
    default: bool = True,
) -> int:
    """Save a payment card, tokenised the way the app tokenises one.

    ``_payment_card`` and not ``_card``: in this shop a "card" is a product —
    see the helper of that name above, which creates one — and the two words
    collided in the same file with the same signature shape.

    ``last4`` is what the test processor decides on — see ``app.payments`` —
    so a test that wants a refusal asks for `0000`, `0001` or `0002` and gets
    a card that behaves that way every time it is charged.
    """
    made = client.post(
        f"{API}/payment-cards",
        json={
            "brand": "Humo",
            "last4": last4,
            "holder": "AZIZ TOSHMATOV",
            "expiry_month": 12,
            "expiry_year": 2030,
            "processor_token": f"dev_tok_{last4}{uuid4().hex}",
            "is_default": default,
        },
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
    card_id: int | None = None,
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
    # A card order needs a card, because a card order is now charged. Saved
    # here rather than in twenty tests: what those tests are about is the
    # queue, the ledger and the returns, and none of them is about paying.
    if payment == "card" and card_id is None:
        card_id = _payment_card(client, auth)
    placed = client.post(
        f"{API}/orders",
        json={
            "address_id": _address(client, auth),
            "payment_method": payment,
            "payment_card_id": card_id,
        },
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
        f"{API}/admin/orders/{order_id}/status",
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
            f"{API}/admin/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=staff_headers,
        )
        assert done.status_code == 200, done.text
    return courier


def _shelf(variant_id: int) -> int:
    """Everything of this variant in the building, off the variant's column."""
    with Session(engine) as session:
        return session.get(ProductVariant, variant_id).stock_left


def _ledger(variant_id: int) -> int:
    """The same, computed from the movements — what the column must equal."""
    with Session(engine) as session:
        return st.on_hand(session, variant_id)


def _sellable(variant_id: int) -> int:
    """What can still be bought: on a sellable shelf, less what is promised."""
    with Session(engine) as session:
        return st.sellable(session, session.get(ProductVariant, variant_id))


def _in(code: str, variant_id: int) -> int:
    """How many of this variant one place holds."""
    with Session(engine) as session:
        place = loc.by_code(session, code)
        return st.at(session, place.id, variant_id) if place else 0


def _assert_the_room_adds_up() -> None:
    """Both invariants, over every placement and every variant there is.

    Called at the end of anything that moves goods. A placement that has
    drifted from its movements is a bug in ``app.stock``, and the point of
    checking it here rather than in one dedicated test is that it is checked
    after each *kind* of move rather than after one of them.
    """
    with Session(engine) as session:
        for placement in session.exec(select(StockPlacement)).all():
            assert placement.qty == st.ledger_at(
                session, placement.location_id, placement.variant_id
            ), f"placement {placement.location_id}/{placement.variant_id} has drifted"
            assert placement.qty >= 0, "a place cannot hold less than nothing"

        for variant in session.exec(select(ProductVariant)).all():
            spread = sum(
                row.qty
                for row in session.exec(
                    select(StockPlacement).where(
                        StockPlacement.variant_id == variant.id
                    )
                ).all()
            )
            assert variant.stock_left == spread, f"{variant.sku} is not where it says"
            assert variant.stock_left == st.on_hand(session, variant.id)


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
    me = client.get(f"{API}/me/staff", headers=admin)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "admin"


def test_a_customer_cannot_reach_the_backoffice(
    client: TestClient, auth: dict[str, str]
) -> None:
    assert client.get(f"{API}/admin/products", headers=auth).status_code == 403
    assert client.get(f"{API}/admin/products").status_code == 401


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
    assert roles == {
        UserRole.ADMIN,
        UserRole.WAREHOUSE,
        UserRole.SELLER,
        UserRole.COURIER,
    }


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
    _variants(client, admin, card["id"], ["Qora", "Oq"], ["42"])
    refused = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    # Named, because "one colour is missing a photograph" leaves somebody
    # opening all six to find out which.
    assert "Qora" in refused.json()["detail"]
    assert "Oq" in refused.json()["detail"]

    _photograph(client, admin, card["id"], "Qora")
    still = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert still.status_code == 409, still.text
    assert "Oq" in still.json()["detail"]

    _photograph(client, admin, card["id"], "Oq")
    allowed = client.post(
        f"{API}/admin/products/{card['id']}/status",
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
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "archived", "note": "sotilmadi"},
        headers=admin,
    )
    assert archived.status_code == 200, archived.text
    assert client.get(f"{API}/products/{card['id']}").status_code == 404


def test_a_card_cannot_jump_from_archived_to_active(
    client: TestClient, admin: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-JUMP")
    _photograph(client, admin, card["id"])
    client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "archived"},
        headers=admin,
    )
    refused = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text


def test_the_same_sku_twice_is_refused(
    client: TestClient, admin: dict[str, str]
) -> None:
    _card(client, admin, sku="ALFA-DUP")
    again = client.post(
        f"{API}/admin/products",
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
        f"{API}/admin/products/{card['id']}",
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
        f"{API}/admin/products",
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
    counts = client.get(f"{API}/admin/products/summary", headers=admin)
    assert counts.status_code == 200, counts.text
    assert set(counts.json()["counts"]) == {"draft", "active", "archived"}


# --------------------------------------------------------------------------- the room


def test_the_seed_builds_the_room_from_a_list() -> None:
    """Three units of four by four today, and not a 3 or a 48 anywhere.

    The count is asserted against ``locations.RACKS`` rather than against 48,
    because the point of the list is that a fourth unit is a line in it — a
    test that hard-codes the answer is the constant the code refused to have.
    """
    with Session(engine) as session:
        cells = session.exec(
            select(Location).where(Location.kind == LocationKind.BIN)
        ).all()
        staging = session.exec(
            select(Location).where(Location.kind != LocationKind.BIN)
        ).all()

    expected = sum(columns * rows for _, columns, rows, _ in loc.RACKS)
    assert len(cells) == expected
    assert {place.code for place in staging} >= {
        loc.QABUL, loc.YIGIM, loc.BRAK, loc.QAYTGAN
    }


def test_the_office_can_build_a_rack_and_nobody_else_can(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Shelving goes up on a Saturday, not at the next deployment.

    The racks were always data, but the only door to that data was the seed —
    so a fourth unit meant editing a list in the source. This is the same
    write through the API: a letter and a grid, cells coded the way every
    label in the building is, and refused where the letter is taken.

    Cleaned up at the end because the room's own total is asserted elsewhere
    against ``locations.RACKS``, and a test that leaves six cells behind
    breaks that one from a distance.
    """
    refused = client.post(
        f"{API}/warehouse/racks",
        json={"rack": "Z", "columns": 2, "rows": 3},
        headers=warehouse,
    )
    assert refused.status_code == 403

    try:
        made = client.post(
            f"{API}/warehouse/racks",
            json={"rack": "z", "columns": 2, "rows": 3, "capacity": 40},
            headers=admin,
        )
        assert made.status_code == 201, made.text
        # Upper-cased on the way in: the letter is read off a label.
        assert made.json()["rack"] == "Z"
        assert made.json()["cells"] == 6

        with Session(engine) as session:
            corner = loc.by_code(session, "Z-02-03")
            assert corner is not None
            assert (corner.rack, corner.column_no, corner.row_no) == ("Z", 2, 3)
            assert corner.capacity == 40

        # And the map draws it without being told anything new.
        room = client.get(f"{API}/warehouse/locations", headers=admin)
        assert room.status_code == 200
        assert len([c for c in room.json()["cells"] if c["rack"] == "Z"]) == 6

        again = client.post(
            f"{API}/warehouse/racks",
            json={"rack": "Z", "columns": 4, "rows": 4},
            headers=admin,
        )
        assert again.status_code == 409
    finally:
        with Session(engine) as session:
            for cell in session.exec(
                select(Location).where(Location.rack == "Z")
            ).all():
                session.delete(cell)
            session.commit()


def test_a_rack_that_is_standing_can_have_cells_bolted_onto_it(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A fifth column goes up on a Saturday, and A is still A.

    Building a rack refuses a letter that is taken, and it is right to — "A,
    6 columns" against an existing A of four cannot be told from a typo. So
    growing one is its own door, it takes the shape the rack should *have*
    rather than a difference, and it writes only what is missing: the cells
    that are there keep their capacity, their contents and their codes.

    Cleaned up at the end for the same reason the rack test is: the room's
    own total is asserted elsewhere against ``locations.RACKS``.
    """
    # A letter nobody has built is somebody meaning to build one.
    nowhere = client.post(
        f"{API}/warehouse/racks/Q/cells",
        json={"columns": 2, "rows": 2},
        headers=admin,
    )
    assert nowhere.status_code == 404, nowhere.text

    try:
        built = client.post(
            f"{API}/warehouse/racks",
            json={"rack": "Y", "columns": 2, "rows": 2, "capacity": 25},
            headers=admin,
        )
        assert built.status_code == 201, built.text

        refused = client.post(
            f"{API}/warehouse/racks/Y/cells",
            json={"columns": 3, "rows": 2},
            headers=warehouse,
        )
        assert refused.status_code == 403

        grown = client.post(
            f"{API}/warehouse/racks/y/cells",
            json={"columns": 3, "rows": 2},
            headers=admin,
        )
        assert grown.status_code == 200, grown.text
        # Two cells and not six: what was missing, not what was asked for.
        assert grown.json()["cells"] == 2
        # Upper-cased on the way in, like the letter on a label.
        assert grown.json()["rack"] == "Y"

        with Session(engine) as session:
            # The rack's own figure, not the schema's sixty: a column bolted
            # onto a unit holds what the rest of the unit holds.
            assert loc.by_code(session, "Y-03-01").capacity == 25
            assert loc.by_code(session, "Y-01-01").capacity == 25

        # A ragged rack is a real shelf — three rows in the columns that have
        # room for them — and only the new cells take the stated capacity.
        ragged = client.post(
            f"{API}/warehouse/racks/Y/cells",
            json={"columns": 3, "rows": 3, "capacity": 10},
            headers=admin,
        )
        assert ragged.status_code == 200, ragged.text
        assert ragged.json()["cells"] == 3
        with Session(engine) as session:
            assert loc.by_code(session, "Y-01-03").capacity == 10
            assert loc.by_code(session, "Y-01-01").capacity == 25

        # Asking for a smaller shape than is there is not a demolition.
        smaller = client.post(
            f"{API}/warehouse/racks/Y/cells",
            json={"columns": 1, "rows": 1},
            headers=admin,
        )
        assert smaller.status_code == 200, smaller.text
        assert smaller.json()["cells"] == 0
        assert "Y" in smaller.json()["message"]

        with Session(engine) as session:
            assert len(
                session.exec(select(Location).where(Location.rack == "Y")).all()
            ) == 9

        trail = client.get(
            f"{API}/admin/audit",
            params={"action": "location.rack_extended"},
            headers=admin,
        ).json()
        assert trail["total"] == 2      # the two that wrote something
    finally:
        with Session(engine) as session:
            for cell in session.exec(
                select(Location).where(Location.rack == "Y")
            ).all():
                session.delete(cell)
            for row in session.exec(
                select(AuditLog).where(AuditLog.action == "location.rack_extended")
            ).all():
                session.delete(row)
            session.commit()


def _build_a_rack(client: TestClient, admin: dict[str, str], rack: str) -> None:
    """A shelf unit of this test's own, two columns by one.

    Its own letter per test, like the two rack tests above: the room's total
    is asserted elsewhere against ``locations.RACKS``, and a cell left
    standing — or worse, left retired — breaks that from a distance.
    """
    built = client.post(
        f"{API}/warehouse/racks",
        json={"rack": rack, "columns": 2, "rows": 1, "capacity": 20},
        headers=admin,
    )
    assert built.status_code == 201, built.text


def _take_the_rack_down(rack: str) -> None:
    """Remove a rack a test built, and every trace it left in the ledger.

    The movements first, then the placements, then the cells. A test that
    wrote goods into one of these cells has written them off again by the time
    this runs, so the net at each cell is nought and deleting both ends of the
    pair leaves the variant's own figure exactly as it was — which is what
    ``_assert_the_room_adds_up`` is going to check on the next test that moves
    anything.
    """
    with Session(engine) as session:
        cells = session.exec(select(Location).where(Location.rack == rack)).all()
        here = [cell.id for cell in cells]
        if here:
            for row in session.exec(
                select(StockMovement).where(
                    col(StockMovement.from_location_id).in_(here)
                    | col(StockMovement.to_location_id).in_(here)
                )
            ).all():
                session.delete(row)
            for row in session.exec(
                select(StockPlacement).where(col(StockPlacement.location_id).in_(here))
            ).all():
                session.delete(row)
        for cell in cells:
            session.delete(cell)
        for row in session.exec(
            select(AuditLog).where(
                col(AuditLog.action).in_(["location.rack_added", "location.active"])
            )
        ).all():
            session.delete(row)
        session.commit()


def test_a_cell_that_is_holding_goods_will_not_be_taken_out_of_the_room(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """And the refusal says which of the two things to do about it.

    A retired cell leaves the map, so goods in one are goods the shop's count
    still includes and no picker can be sent to — found again only by somebody
    walking the room with a list. So the door refuses while anything is
    standing there, and names the quantity, because "that cell is not empty"
    to a person looking at an empty-looking shelf is an argument rather than
    an instruction.
    """
    _build_a_rack(client, admin, "X")
    try:
        card = _card(client, admin, sku="XRETIRE-1")
        ids = _variants(client, admin, card["id"], ["Qora"], ["42"])
        _book_in(client, warehouse, [(ids["Qora / 42"], 6)], code="X-01-01")

        refused = client.post(
            f"{API}/warehouse/cells/X-01-01/active",
            json={"active": False, "note": "javon sindi"},
            headers=admin,
        )
        assert refused.status_code == 409, refused.text
        detail = refused.json()["detail"]
        assert "X-01-01" in detail and "6" in detail
        assert "ko'chiring" in detail          # move them
        assert "hisobdan chiqaring" in detail  # or write them off

        english = client.post(
            f"{API}/warehouse/cells/X-01-01/active",
            json={"active": False},
            headers={**admin, "Accept-Language": "en"},
        )
        assert english.json()["detail"] == (
            "X-01-01 still holds 6 — move them to another cell or write them "
            "off first"
        )

        # Nothing happened: the cell is where it was, on the map and in use.
        room = client.get(f"{API}/warehouse/locations", headers=admin).json()
        assert "X-01-01" in [cell["code"] for cell in room["cells"]]

        # And doing what the sentence said is enough. Writing them off is the
        # remedy it names, and the cell goes straight after it.
        emptied = client.post(
            f"{API}/warehouse/stock/empty",
            json={"code": "X-01-01", "reason": "javon sindi"},
            headers=admin,
        )
        assert emptied.status_code == 200, emptied.text
        assert emptied.json()["units"] == 6

        gone = client.post(
            f"{API}/warehouse/cells/X-01-01/active",
            json={"active": False, "note": "javon sindi"},
            headers=admin,
        )
        assert gone.status_code == 200, gone.text
        assert gone.json()["is_active"] is False
        _assert_the_room_adds_up()
    finally:
        _take_the_rack_down("X")


def test_an_emptied_cell_leaves_the_map_and_can_be_brought_back(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The hole the owner asked for, and the way out of it again.

    ``is_active`` had been on the row since the first migration with nothing
    anywhere writing it, so a rack extended to 6×4 by a typo carried its dead
    columns for ever. Retiring one takes it off the shelf map, off the label
    sheet and out of the putaway plan; it is **not** a delete, so the code,
    the capacity and every movement that ever named it stay where they are —
    which is what makes bringing it back a single word.

    The retired cell is answered for by its own door rather than left in the
    map's ``cells``: half a dozen things count that list, and a dead cell in
    it is a full/empty figure and a destination grid quietly counting a shelf
    that is not there.
    """
    _build_a_rack(client, admin, "W")
    try:
        out = client.post(
            f"{API}/warehouse/cells/w-01-01/active",
            json={"active": False, "note": "ikkita ustun ortiqcha edi"},
            headers=admin,
        )
        assert out.status_code == 200, out.text
        # Upper-cased on the way in, like the letter on every label.
        assert out.json()["code"] == "W-01-01"
        assert out.json()["is_active"] is False

        room = client.get(f"{API}/warehouse/locations", headers=admin).json()
        drawn = [cell["code"] for cell in room["cells"]]
        assert "W-01-01" not in drawn
        assert "W-02-01" in drawn      # its neighbour is untouched

        # Off the plan and off the label sheet with it.
        sheet = client.get(
            f"{API}/warehouse/labels", params={"cells": True}, headers=warehouse
        ).json()
        assert "W-01-01" not in [cell["code"] for cell in sheet["cells"]]

        # But answered for, so the map can draw the hole where the cell was
        # and offer the way back on the tile somebody is looking at.
        retired = client.get(f"{API}/warehouse/cells/retired", headers=warehouse)
        assert retired.status_code == 200, retired.text
        mine = [cell for cell in retired.json() if cell["code"] == "W-01-01"]
        assert len(mine) == 1
        assert mine[0]["is_active"] is False
        assert (mine[0]["rack"], mine[0]["column_no"], mine[0]["row_no"]) == ("W", 1, 1)

        # Asking twice writes nothing and is not an error: a form somebody
        # double-taps is not a second decision.
        again = client.post(
            f"{API}/warehouse/cells/W-01-01/active",
            json={"active": False},
            headers=admin,
        )
        assert again.status_code == 200, again.text

        back = client.post(
            f"{API}/warehouse/cells/W-01-01/active",
            json={"active": True, "note": "noto'g'ri olib tashlangan"},
            headers=admin,
        )
        assert back.status_code == 200, back.text
        assert back.json()["is_active"] is True
        room = client.get(f"{API}/warehouse/locations", headers=admin).json()
        assert "W-01-01" in [cell["code"] for cell in room["cells"]]
        assert client.get(
            f"{API}/warehouse/cells/retired", headers=warehouse
        ).json() == []

        # Both decisions are in the log, with the reason on them — switching a
        # cell off is audited the way switching an account off is.
        trail = client.get(
            f"{API}/admin/audit", params={"action": "location.active"}, headers=admin
        ).json()
        assert trail["total"] == 2
        assert {row["new_value"] for row in trail["items"]} == {"true", "false"}
        assert "ikkita ustun ortiqcha edi" in [row["note"] for row in trail["items"]]
    finally:
        _take_the_rack_down("W")


def test_goods_cannot_be_put_into_a_cell_that_has_been_retired(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """``loc.by_code`` finds a cell by its name, retired or not.

    Which is right — the movements that named it have to resolve — but it
    meant every door that takes a typed code would happily shelve goods into
    a cell that is off the map. All three are shut: carrying a quantity
    across, tipping a pile in at the receiving desk, and the back way in,
    which is a stocktake booking a surplus into a cell nobody can see.
    """
    _build_a_rack(client, admin, "V")
    try:
        card = _card(client, admin, sku="VRETIRE-1")
        ids = _variants(client, admin, card["id"], ["Qora"], ["42"])
        _book_in(client, warehouse, [(ids["Qora / 42"], 4)])

        out = client.post(
            f"{API}/warehouse/cells/V-01-01/active",
            json={"active": False},
            headers=admin,
        )
        assert out.status_code == 200, out.text

        carried = client.post(
            f"{API}/warehouse/move",
            json={
                "variant_id": ids["Qora / 42"],
                "qty": 2,
                "from_code": BENCH,
                "to_code": "V-01-01",
            },
            headers={**warehouse, "Idempotency-Key": f"move-{uuid4()}"},
        )
        assert carried.status_code == 409, carried.text
        assert "V-01-01" in carried.json()["detail"]
        assert "qaytaring" in carried.json()["detail"]   # bring it back first

        whole = client.post(
            f"{API}/warehouse/move-cell",
            json={"from_code": BENCH, "to_code": "V-01-01"},
            headers={**warehouse, "Idempotency-Key": f"move-cell-{uuid4()}"},
        )
        assert whole.status_code == 409, whole.text

        tipped = client.post(
            f"{API}/warehouse/piles",
            json={
                "kind": "Sviter",
                "colour": "Qora",
                "sizes": [{"size": "L", "quantity": 3}],
                "location_code": "V-01-01",
                "place": "Chorsu",
                "unit_cost": 10_000,
            },
            headers={**warehouse, "Idempotency-Key": f"pile-{uuid4()}"},
        )
        assert tipped.status_code == 409, tipped.text
        assert "V-01-01" in tipped.json()["detail"]

        counting = client.post(
            f"{API}/warehouse/counts",
            json={"code": "V-01-01"},
            headers=warehouse,
        )
        assert counting.status_code == 409, counting.text
        assert "V-01-01" in counting.json()["detail"]

        # Refused before anything was written, which is the point of checking
        # the cells first: no stub card, no run, and nothing moved.
        assert _in("V-01-01", ids["Qora / 42"]) == 0
        assert _in(BENCH, ids["Qora / 42"]) == 4
        _assert_the_room_adds_up()
    finally:
        _take_the_rack_down("V")


def test_an_area_with_a_job_cannot_be_taken_out_of_the_room(
    client: TestClient, admin: dict[str, str]
) -> None:
    """QABUL is not a shelf, it is the unplaced state having an address.

    Being in it *is* what "arrived and not yet put away" means, the seed
    writes it by name, and ``locations.staging`` raises rather than conjuring
    one up — so a retired QABUL is a receiving desk the next deployment
    silently puts back, with everything booked into it invisible to the map in
    between. There is no such decision to take, so the door does not offer it.
    """
    for code in (loc.QABUL, loc.YIGIM, loc.BRAK, loc.QAYTGAN):
        refused = client.post(
            f"{API}/warehouse/cells/{code}/active",
            json={"active": False},
            headers=admin,
        )
        assert refused.status_code == 409, refused.text
        assert code in refused.json()["detail"]

    with Session(engine) as session:
        assert loc.staging(session, loc.QABUL).is_active is True


def test_only_the_office_takes_a_cell_out_of_the_room(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The same guard as building a rack, and not a wider one.

    Retiring a cell is the shape of the building changing. Everybody else in
    the warehouse moves goods between places that exist, and the hand who
    finds a cell inconvenient at nine in the evening is exactly the person
    this must not be a way out for.
    """
    refused = client.post(
        f"{API}/warehouse/cells/A-01-01/active",
        json={"active": False},
        headers=warehouse,
    )
    assert refused.status_code == 403

    with Session(engine) as session:
        assert loc.by_code(session, "A-01-01").is_active is True


def test_a_cell_reads_the_way_a_person_reads_a_shelf() -> None:
    """``A-01-01`` is rack A, leftmost column, bottom row."""
    with Session(engine) as session:
        first = loc.by_code(session, "A-01-01")
        assert first is not None
        assert (first.rack, first.column_no, first.row_no) == ("A", 1, 1)
        assert first.capacity > 0

        last_rack = loc.RACKS[-1][0]
        columns, rows = loc.RACKS[-1][1], loc.RACKS[-1][2]
        assert loc.by_code(session, loc.cell_code(last_rack, columns, rows)) is not None


def test_the_room_is_walked_in_serpentine_order() -> None:
    """Up one column and down the next, so a picker walks the room once."""
    with Session(engine) as session:
        codes = [place.code for place in loc.cells(session)]

    rows = loc.RACKS[0][2]
    first_column = codes[:rows]
    second_column = codes[rows : rows * 2]
    assert first_column == [f"A-01-0{n}" for n in range(1, rows + 1)]
    assert second_column == [f"A-02-0{n}" for n in range(rows, 0, -1)]


def test_seeding_the_room_again_adds_nothing(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Idempotent on the code, so a fourth rack is a seed run and not a reset."""
    with Session(engine) as session:
        before = len(session.exec(select(Location)).all())
        assert loc.seed_locations(session) == 0
        assert len(session.exec(select(Location)).all()) == before


def test_goods_are_carried_from_the_receiving_area_to_a_cell(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Putaway, as a move: out of QABUL and into a cell that is named.

    A sack no longer lands at the receiving desk — a pile goes straight to the
    cell the person is standing at — but a parcel a customer sent back does,
    and somebody still has to carry it to a shelf. So the journey this tests
    is live, and the kind on the movement is what says which journey it was:
    out of the receiving area is a putaway, cell to cell is a move.

    The endpoint that does this from a screen is `POST /warehouse/move`; the
    move itself is the model's, and this is what it has to do.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-PUTAWAY", stock=6)
    leaf = ids["Qora / 42"]

    with Session(engine) as session:
        variant = session.get(ProductVariant, leaf)
        # Two came back from a customer, the way `app.inventory` records it:
        # into the uninspected corner, and out of it once somebody has looked.
        st.move(
            session,
            variant=variant,
            qty=2,
            kind=StockMovementKind.RETURN,
            frm=None,
            to=loc.staging(session, loc.QAYTGAN),
            reason="mijozdan qaytdi",
        )
        st.move(
            session,
            variant=variant,
            qty=2,
            kind=StockMovementKind.RELIST,
            frm=loc.staging(session, loc.QAYTGAN),
            to=loc.staging(session, loc.QABUL),
            reason="butun",
        )
        session.commit()

    assert _in(loc.QABUL, leaf) == 2

    with Session(engine) as session:
        st.move(
            session,
            variant=session.get(ProductVariant, leaf),
            qty=2,
            kind=StockMovementKind.PUTAWAY,
            frm=loc.staging(session, loc.QABUL),
            to=loc.by_code(session, "A-02-03"),
            reason="joylashtirildi",
        )
        session.commit()

    assert _in(loc.QABUL, leaf) == 0
    assert _in("A-02-03", leaf) == 2
    assert _in(BENCH, leaf) == 6
    # Carrying goods across the room changes where they are and not how many
    # there are.
    assert _shelf(leaf) == 8
    assert _sellable(leaf) == 8
    _assert_the_room_adds_up()


def test_a_model_that_outgrew_its_cell_is_picked_from_both(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Split across places, in walk order, because the goods are in two."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-TWOCELLS", stock=6)
    leaf = ids["Qora / 42"]
    with Session(engine) as session:
        variant = session.get(ProductVariant, leaf)
        st.move(
            session,
            variant=variant,
            qty=5,
            kind=StockMovementKind.MOVE,
            frm=loc.by_code(session, BENCH),
            to=loc.by_code(session, "A-01-01"),
        )
        session.commit()

    order = _order(client, auth, card["id"], leaf, quantity=6)
    _to_the_door(client, admin, order["id"])

    assert _shelf(leaf) == 0
    assert _in("A-01-01", leaf) == 0
    assert _in(BENCH, leaf) == 0
    _assert_the_room_adds_up()


def test_a_courier_is_a_place_too(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A parcel in a bag has not left the building's books.

    Made the first time somebody carries something, unlike the four staging
    areas: couriers are hired and leave, and a seed that has to be re-run
    whenever somebody joins is a seed nobody re-runs.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-BAG", stock=3)
    leaf = ids["Qora / 42"]

    with Session(engine) as session:
        courier = session.exec(
            select(User).where(User.phone == COURIER_PHONE)
        ).one()
        bag = loc.for_courier(session, courier.id)
        assert bag.code == f"{loc.COURIER_PREFIX}-{courier.id}"
        assert bag.kind is LocationKind.COURIER
        st.move(
            session,
            variant=session.get(ProductVariant, leaf),
            qty=1,
            kind=StockMovementKind.HANDOVER,
            frm=loc.by_code(session, BENCH),
            to=bag,
        )
        session.commit()

    assert _shelf(leaf) == 3          # still in the building
    assert _sellable(leaf) == 2       # but not on a shelf anybody sells from
    _assert_the_room_adds_up()


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
        f"{API}/warehouse/supplies",
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
    ids = _variants(client, admin, card["id"], ["Qora"], ["42"])
    client.post(f"{API}/warehouse/supplies", json={"sacks": 1}, headers=warehouse)

    assert _shelf(ids["Qora / 42"]) == 0
    assert _ledger(ids["Qora / 42"]) == 0
    with Session(engine) as session:
        assert session.get(Product, card["id"]).in_stock is False


def test_a_receipt_with_nothing_in_it_is_refused(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """An empty receipt is a sack somebody ticked off without opening.

    This used to be `POST /supplies/{id}/receive` refusing a draft with no
    lines on it. That door is gone — no supply this shop creates is ever a
    draft with lines to fill in — and the same statement through the door the
    bench uses is a pile with no sizes against it: nothing was counted, so
    there is nothing to book in.
    """
    nothing = client.post(
        f"{API}/warehouse/piles",
        json={
            "kind": "Ro'mol",
            "colour": "Oq",
            "sizes": [],
            "unit_cost": 100,
            "location_code": "A-01-01",
        },
        headers={**warehouse, "Idempotency-Key": f"pile-{uuid4()}"},
    )
    assert nothing.status_code == 422, nothing.text


def test_booking_a_pile_in_is_what_brings_the_goods_into_existence(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The receipt, the shelf and the ledger, from one action.

    Closing a sorted draft used to be the moment goods started existing, and
    it put them in the receiving area for somebody to carry out again. The
    pile does both halves at once, so what has to still add up afterwards is
    everything that added up before: the column equals the ledger, the goods
    are in a place that can be named, and the run says what it cost.
    """
    card = _card(client, admin, sku="ALFA-CLOSE")
    ids = _variants(client, admin, card["id"], ["Qora"], ["42", "43"])
    closed = _book_in(
        client, warehouse, [(ids["Qora / 42"], 6), (ids["Qora / 43"], 4)]
    )

    assert closed["status"] == "received"
    assert closed["total_cost"] == 10 * 200_000 + 30_000
    assert _shelf(ids["Qora / 42"]) == 6
    assert _ledger(ids["Qora / 42"]) == 6

    # Onto the shelf, in one move, because the person is standing at it. Not
    # into the receiving area and out of it again — that is a leg in the
    # ledger for a journey nobody made.
    assert _in(BENCH, ids["Qora / 42"]) == 6
    assert _in(loc.QABUL, ids["Qora / 42"]) == 0
    assert _sellable(ids["Qora / 42"]) == 6

    with Session(engine) as session:
        kinds = session.exec(
            select(StockMovement.kind).where(
                StockMovement.variant_id == ids["Qora / 42"]
            )
        ).all()
    assert list(kinds) == [StockMovementKind.RECEIPT]
    _assert_the_room_adds_up()


def test_a_receipt_is_not_reopened_dismissed_or_called_off(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Correct it with an adjustment. The ledger keeps what was believed then.

    A pile writes its run already closed, so there is no second receive to
    refuse — the door that would have done it is gone. What is left pointing
    at a closed run are the two live ones, and both have to refuse it: a
    receipt cannot be dismissed as an unopened sack, and it cannot be called
    off as goods that never arrived, because the goods are on a shelf and the
    ledger says who put them there.
    """
    card = _card(client, admin, sku="ALFA-ONCE")
    ids = _variants(client, admin, card["id"], ["Qora"], ["42"])
    closed = _book_in(client, warehouse, [(ids["Qora / 42"], 3)])
    assert closed["status"] == "received"

    dismissed = client.post(
        f"{API}/warehouse/supplies/{closed['id']}/sorted", headers=warehouse
    )
    assert dismissed.status_code == 409, dismissed.text

    off = client.post(
        f"{API}/warehouse/supplies/{closed['id']}/cancel",
        json={"reason": "Aslida kelmagan"},
        headers=warehouse,
    )
    assert off.status_code == 409, off.text

    assert _shelf(ids["Qora / 42"]) == 3
    assert _in(BENCH, ids["Qora / 42"]) == 3


def test_a_sack_can_be_called_off_with_a_reason(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    run = client.post(f"{API}/warehouse/supplies", json={"sacks": 1}, headers=warehouse).json()[0]
    off = client.post(
        f"{API}/warehouse/supplies/{run['id']}/cancel",
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
    client.post(f"{API}/warehouse/supplies", json={"sacks": 2}, headers=warehouse)
    drafts = client.get(
        f"{API}/warehouse/supplies", params={"status": "draft"}, headers=warehouse
    ).json()
    ids = [run["id"] for run in drafts]
    assert ids == sorted(ids)


def test_only_the_warehouse_books_goods_in(
    client: TestClient, auth: dict[str, str]
) -> None:
    refused = client.post(
        f"{API}/warehouse/supplies", json={"sacks": 1}, headers=auth
    )
    assert refused.status_code == 403


# --------------------------------------------------------------------------- the ledger


def test_the_shelf_is_the_sum_of_the_ledger(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The invariant, over a sequence with moves in every direction."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-LEDGER", stock=10)
    leaf = ids["Qora / 42"]

    client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": leaf, "quantity": 2, "reason": "Ombor devoridan tushdi"},
        headers=warehouse,
    )
    _book_in(client, warehouse, [(leaf, 5)])

    # Fifteen in the building — the two broken ones are in the corner by the
    # door, not gone — and thirteen that can be sold.
    assert _shelf(leaf) == 15
    assert _ledger(leaf) == 15
    assert _in(loc.BRAK, leaf) == 2
    assert _sellable(leaf) == 13
    _assert_the_room_adds_up()


def test_a_place_cannot_give_up_what_it_never_held(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A cell that would go negative is a miscount, not an arithmetic result."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SHORT", stock=2)
    refused = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": ids["Qora / 42"], "quantity": 9, "reason": "suvda qoldi"},
        headers=warehouse,
    )
    assert refused.status_code == 409, refused.text
    assert _shelf(ids["Qora / 42"]) == 2
    _assert_the_room_adds_up()


def test_damaged_goods_need_a_reason(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Stock that moved without one is indistinguishable from stock that was stolen."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-WRITEOFF")
    refused = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": ids["Qora / 42"], "quantity": 1, "reason": ""},
        headers=warehouse,
    )
    assert refused.status_code == 422, refused.text


def test_damaged_goods_are_audited_and_read_as_a_move(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-AUDIT")
    leaf = ids["Qora / 42"]
    client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": leaf, "quantity": 1, "reason": "Suvda qoldi"},
        headers=warehouse,
    )

    ledger = client.get(
        f"{API}/warehouse/stock/movements",
        params={"variant_id": leaf, "kind": "damage"},
        headers=warehouse,
    ).json()
    assert ledger["total"] == 1
    row = ledger["items"][0]
    # A move reads as one: this many, out of there, into here.
    assert row["quantity"] == 1
    assert row["from_code"] == BENCH
    assert row["to_code"] == loc.BRAK
    assert row["reason"] == "Suvda qoldi"
    assert row["variant_label"] == "Qora · 42"

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.action == "stock.damage",
                AuditLog.entity_id == leaf,
            )
        ).all()
    assert len(logged) == 1


def test_more_than_the_shelves_hold_says_so_in_the_readers_language(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The shortfall used to reach the damage form as an English f-string.

    "only 4 of MB-000001-QORA-M on the shelves, not 999", with an internal
    code in it, on a screen whose every other refusal is Uzbek. `/warehouse/move`
    had been given a label and this door had not, so the same shortfall came
    back in two languages depending on which button was pressed.

    Its own sentence and not the cell one: "A-02-03 holds 4, not 999" would
    send somebody to one shelf over goods that are spread across several.
    """
    made = _pile(
        client, warehouse, kind="Qo\'lqop", colour="Kulrang", sizes=(("M", 4),),
        code="C-03-01",
    )
    assert made.status_code == 201, made.text
    leaf = made.json()["labels"][0]["variant_id"]

    too_many = {"variant_id": leaf, "quantity": 999, "reason": "suvda qoldi"}
    short = client.post(
        f"{API}/warehouse/stock/damage", json=too_many, headers=warehouse
    )
    assert short.status_code == 409, short.text
    detail = short.json()["detail"]
    assert "Javonlarda" in detail          # Uzbek, like every other refusal
    assert "4" in detail and "999" in detail
    assert "C-03-01" not in detail         # no cell to send anybody to
    assert made.json()["labels"][0]["sku"] not in detail

    english = client.post(
        f"{API}/warehouse/stock/damage",
        json=too_many,
        headers={**warehouse, "Accept-Language": "en"},
    )
    assert english.json()["detail"] == "There are 4 on the shelves altogether, not 999"

    # And nothing moved on the way to being refused.
    assert _in("C-03-01", leaf) == 4


def test_nothing_can_be_damaged_that_is_not_a_variant(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    missing = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": 999_999, "quantity": 1, "reason": "yo'q"},
        headers=warehouse,
    )
    assert missing.status_code == 404


# --------------------------------------------------------------------------- the map


def test_the_map_draws_the_whole_room_in_one_answer(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Three shapes on one screen: the racks, the staging tiles, the bags."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-MAP", stock=5)

    room = client.get(f"{API}/warehouse/locations", headers=warehouse)
    assert room.status_code == 200, room.text
    body = room.json()

    assert len(body["cells"]) == sum(c * r for _, c, r, _ in loc.RACKS)
    assert [cell["code"] for cell in body["cells"]][:2] == ["A-01-01", "A-01-02"]
    staging = {tile["code"]: tile for tile in body["staging"]}
    assert set(staging) == {loc.QABUL, loc.YIGIM, loc.BRAK, loc.QAYTGAN}
    # The four tiles are drawn whether or not anything is standing in them,
    # which is the point of a map: an empty receiving desk is a fact about the
    # room and not a reason to leave a hole in the picture. Nothing reaches
    # QABUL any more — goods land on a shelf in one action — so the card's ten
    # are in a cell, and that is what the map has to show.
    assert staging[loc.QABUL]["oldest_minutes"] >= 0
    assert _in(BENCH, ids["Qora / 42"]) == 5
    bench = next(cell for cell in body["cells"] if cell["code"] == BENCH)
    assert bench["units"] >= 10


def test_a_cell_says_how_full_it_is(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-FILL", stock=30)
    _put_away(client, warehouse, ids["Qora / 42"], 30, "B-01-01")

    cell = client.get(f"{API}/warehouse/locations/B-01-01", headers=warehouse).json()
    assert cell["units"] == 30
    assert cell["capacity"] == 60
    assert cell["fill_percent"] == 50
    # And how many more it is meant to take, which is the figure a putaway
    # screen needs and had to work out for itself.
    assert cell["free"] == 30
    assert cell["contents"][0]["variant_label"] == "Qora · 42"


def test_a_cell_owns_up_to_being_past_full(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Seventy in a cell of sixty reads as seventy, not as full.

    Capped at a hundred, a cell holding sixty-five of a stated sixty looked
    exactly like one holding sixty — and an over-full cell is the one thing
    that figure is on the screen to show. Nothing refuses the goods: the
    model's rule is that a cell which turns the last pair away at nine in the
    evening is a cell somebody works around. It shows.
    """
    _pile(
        client,
        warehouse,
        kind="Krossovka",
        colour="Pushti",
        sizes=(("42", 70),),
        code="A-01-04",
    )

    cell = client.get(f"{API}/warehouse/locations/A-01-04", headers=warehouse).json()
    assert cell["capacity"] == 60
    assert cell["units"] == 70
    assert cell["fill_percent"] == 117
    # Room left is never negative — "minus ten of room" is not a thing
    # anybody says, and how far over is `units` against `capacity`.
    assert cell["free"] == 0

    # A place with no stated capacity answers null rather than a big number:
    # nobody has measured QABUL, which is a different thing from it being
    # roomy, and a screen draws the two differently.
    desk = client.get(
        f"{API}/warehouse/locations/{loc.QABUL}", headers=warehouse
    ).json()
    assert desk["free"] is None
    assert desk["fill_percent"] == 0

    # The map carries the same figures, so the red-at-90 tile keeps working.
    room = client.get(f"{API}/warehouse/locations", headers=warehouse).json()
    drawn = next(tile for tile in room["cells"] if tile["code"] == "A-01-04")
    assert drawn["fill_percent"] >= 90
    assert drawn["free"] == 0


def test_where_is_it_answers_by_barcode_and_by_name(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The find-it-fast box the whole warehouse exists for."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-WHERE", stock=4)
    _put_away(client, warehouse, ids["Qora / 42"], 4, "C-03-02")

    with Session(engine) as session:
        barcode = session.get(ProductVariant, ids["Qora / 42"]).barcode

    by_code = client.get(
        f"{API}/warehouse/where-is", params={"q": barcode}, headers=warehouse
    ).json()
    assert len(by_code) == 1
    assert by_code[0]["places"][0]["code"] == "C-03-02"
    assert by_code[0]["places"][0]["qty"] == 4

    by_name = client.get(
        f"{API}/warehouse/where-is", params={"q": "krossovka"}, headers=warehouse
    ).json()
    codes = {place["code"] for row in by_name for place in row["places"]}
    assert "C-03-02" in codes


# --------------------------------------------------------------------------- moving


def test_a_pile_must_name_the_cell_it_went_into(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """There is nowhere else for goods to go, and there are two ways to say it.

    The cell was optional for a while, and empty meant the receiving area with
    a putaway queue offering the goods to whoever had time. Nobody used it:
    whoever opens a sack is standing at the shelf with it. What catches a
    wrongly-typed cell now is `POST /warehouse/move`, not homeless stock.

    Since a big pile can be split across cells there are two ways to answer —
    one cell, or a list of them — and exactly one of them has to be used. The
    refusal is a sentence in the reader's language rather than a validation
    error naming a field, because both halves of it are decisions about the
    request and not about a value.
    """
    nowhere = _pile(client, warehouse, kind="Ro'mol", colour="Oq", code="")
    assert nowhere.status_code == 400, nowhere.text
    assert "yacheyka" in nowhere.json()["detail"]

    both = _pile(
        client,
        warehouse,
        kind="Ro'mol",
        colour="Oq",
        sizes=(("M", 4),),
        code="A-01-01",
        placements=(("A-01-01", 4),),
    )
    assert both.status_code == 400, both.text


def test_a_mis_shelved_pile_can_be_carried_to_the_right_cell(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Cell to cell, both legs named, and the count untouched.

    A move is a journey and not a correction: an adjustment would say the count
    was wrong, and it was not — the goods were only ever in the wrong place.
    """
    made = _pile(
        client, warehouse, kind="Ko'ylak", colour="Oq", sizes=(("M", 6),), code="A-02-03"
    )
    assert made.status_code == 201, made.text
    leaf = made.json()["labels"][0]["variant_id"]

    cell = _put_away(client, warehouse, leaf, 4, "A-02-04", frm="A-02-03")
    assert cell["code"] == "A-02-04"
    assert _in("A-02-03", leaf) == 2
    assert _in("A-02-04", leaf) == 4
    assert _sellable(leaf) == 6      # carrying it across the room sells nothing
    _assert_the_room_adds_up()

    # And the receiving form is told where the rest of the model lives.
    where = client.get(
        f"{API}/warehouse/suggest-cell",
        params={"product_id": made.json()["product"]["id"]},
        headers=warehouse,
    )
    assert where.status_code == 200, where.text
    assert where.json()["code"] in {"A-02-03", "A-02-04"}


def test_a_whole_cell_is_carried_across_the_room_in_one_request(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """One model in three sizes is one journey, not three.

    Tidying a shelf through `/move` was a request per size: three keys, three
    chances to be interrupted, and a model left in two cells if anything went
    wrong halfway — which is the exact mess moving it was meant to clear up.
    No quantities are sent, because what moves is what is standing there and
    a count the screen read some seconds ago goes stale while a picker works.
    """
    made = _pile(
        client,
        warehouse,
        kind="Krossovka",
        colour="Jigarrang",
        sizes=(("41", 4), ("42", 5), ("43", 6)),
        code="C-01-03",
    )
    assert made.status_code == 201, made.text
    ids = {row["variant_label"]: row["variant_id"] for row in made.json()["labels"]}

    moved = client.post(
        f"{API}/warehouse/move-cell",
        json={"from_code": "C-01-03", "to_code": "C-01-04"},
        headers={**warehouse, "Idempotency-Key": "tidy-c-01-03"},
    )
    assert moved.status_code == 200, moved.text
    # Answered with the destination, like `/move`: the person who just
    # carried a shelf across the room wants to see it.
    assert moved.json()["code"] == "C-01-04"
    assert moved.json()["units"] == 15
    assert len(moved.json()["contents"]) == 3

    for label, quantity in (("41", 4), ("42", 5), ("43", 6)):
        leaf = ids[f"Jigarrang / {label}"]
        assert _in("C-01-03", leaf) == 0
        assert _in("C-01-04", leaf) == quantity
    _assert_the_room_adds_up()

    # A retry is the answer we already gave, not a second journey.
    again = client.post(
        f"{API}/warehouse/move-cell",
        json={"from_code": "C-01-03", "to_code": "C-01-04"},
        headers={**warehouse, "Idempotency-Key": "tidy-c-01-03"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["units"] == 15
    assert _in("C-01-04", ids["Jigarrang / 41"]) == 4

    # One size of a cell holding several, back where it came from.
    some = client.post(
        f"{API}/warehouse/move-cell",
        json={
            "from_code": "C-01-04",
            "to_code": "C-01-03",
            "variant_ids": [ids["Jigarrang / 41"]],
        },
        headers={**warehouse, "Idempotency-Key": "tidy-c-01-04-41"},
    )
    assert some.status_code == 200, some.text
    assert _in("C-01-03", ids["Jigarrang / 41"]) == 4
    assert _in("C-01-04", ids["Jigarrang / 42"]) == 5
    _assert_the_room_adds_up()

    # An empty cell is almost always a mistyped code, and answering "done"
    # would leave somebody staring at the wrong shelf.
    nothing = client.post(
        f"{API}/warehouse/move-cell",
        json={"from_code": "B-04-03", "to_code": "C-01-03"},
        headers={**warehouse, "Idempotency-Key": "tidy-nothing"},
    )
    assert nothing.status_code == 409, nothing.text
    assert "B-04-03" in nothing.json()["detail"]


def test_a_cell_that_holds_less_says_so_in_the_readers_language(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The shortfall used to reach the screen as an English f-string.

    "A-02-03 holds 2 of SHIRT-BLK-M, not 5", in a warehouse that reads Uzbek.
    The exception carries the place and the two counts now, and the door
    says it with a label like every other refusal here.
    """
    made = _pile(
        client, warehouse, kind="Kamar", colour="Sariq", sizes=(("M", 2),),
        code="B-04-04",
    )
    leaf = made.json()["labels"][0]["variant_id"]

    short = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": leaf,
            "qty": 5,
            "from_code": "B-04-04",
            "to_code": "B-04-02",
        },
        headers={**warehouse, "Idempotency-Key": "short-b-04-04"},
    )
    assert short.status_code == 409, short.text
    detail = short.json()["detail"]
    assert "B-04-04" in detail
    assert "yacheykasida" in detail      # Uzbek, like every other refusal
    assert "2" in detail and "5" in detail

    english = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": leaf,
            "qty": 5,
            "from_code": "B-04-04",
            "to_code": "B-04-02",
        },
        headers={
            **warehouse,
            "Idempotency-Key": "short-b-04-04-en",
            "Accept-Language": "en",
        },
    )
    assert english.json()["detail"] == "B-04-04 holds 2, not 5"


def test_goods_cannot_be_moved_into_a_staging_area(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    made = _pile(client, warehouse, kind="Kamar", colour="Qora", code="B-03-01")
    leaf = made.json()["labels"][0]["variant_id"]
    refused = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": leaf,
            "qty": 1,
            "from_code": "B-03-01",
            "to_code": loc.BRAK,
        },
        headers={**warehouse, "Idempotency-Key": "move-brak"},
    )
    assert refused.status_code == 409, refused.text


def test_moving_a_pile_to_the_cell_it_is_in_is_refused(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A journey to where you already are is not a journey."""
    made = _pile(client, warehouse, kind="Sharf", colour="Ko'k", code="B-03-02")
    leaf = made.json()["labels"][0]["variant_id"]
    refused = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": leaf,
            "qty": 1,
            "from_code": "B-03-02",
            "to_code": "B-03-02",
        },
        headers={**warehouse, "Idempotency-Key": "move-nowhere"},
    )
    assert refused.status_code == 400, refused.text


def test_a_mistyped_cell_is_a_404_and_moves_nothing(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    made = _pile(client, warehouse, kind="Qalpoq", colour="Qora", sizes=(("", 2),), code="B-03-03")
    leaf = made.json()["labels"][0]["variant_id"]
    missing = client.post(
        f"{API}/warehouse/move",
        json={
            "variant_id": leaf,
            "qty": 1,
            "from_code": "B-03-03",
            "to_code": "Z-09-09",
        },
        headers={**warehouse, "Idempotency-Key": "move-typo"},
    )
    assert missing.status_code == 404, missing.text
    assert _in("B-03-03", leaf) == 2
    _assert_the_room_adds_up()


def test_a_retried_move_does_not_carry_the_goods_twice(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    made = _pile(
        client, warehouse, kind="Qo'lqop", colour="Qora", sizes=(("L", 5),), code="B-04-01"
    )
    leaf = made.json()["labels"][0]["variant_id"]
    body = {
        "variant_id": leaf,
        "qty": 2,
        "from_code": "B-04-01",
        "to_code": "B-04-02",
    }
    headers = {**warehouse, "Idempotency-Key": "move-once"}

    first = client.post(f"{API}/warehouse/move", json=body, headers=headers)
    second = client.post(f"{API}/warehouse/move", json=body, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert _in("B-04-02", leaf) == 2
    assert _in("B-04-01", leaf) == 3
    _assert_the_room_adds_up()


# --------------------------------------------------------------------------- picking


def test_a_pick_task_lists_the_room_in_walk_order(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Serpentine, so the picker walks the room once.

    The goods are deliberately split across two cells in the wrong order —
    A-01-03 is reached before A-02-02 going up the first column and down the
    second — and the task has to put them back in the order somebody walks.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-WALK", stock=5)
    leaf = ids["Qora / 42"]
    # Every one of them onto a shelf, so the receiving desk — which a picker
    # passes before the racks and which therefore sorts first — is out of the
    # way and the two cells are the whole answer.
    _put_away(client, warehouse, leaf, 2, "A-02-02")
    _put_away(client, warehouse, leaf, 3, "A-01-03")

    order = _order(client, auth, card["id"], leaf, quantity=5)
    task = client.post(
        f"{API}/warehouse/pick/orders/{order['id']}", headers=warehouse
    )
    assert task.status_code == 201, task.text
    lines = task.json()["lines"]
    assert [line["location_code"] for line in lines] == ["A-01-03", "A-02-02"]
    assert [line["qty"] for line in lines] == [3, 2]
    # The variant leads: the thing you must not get wrong comes before the
    # place you walk to.
    assert lines[0]["variant_label"] == "Qora · 42"
    assert lines[0]["product_title"] == "Krossovka ALFA-WALK"


def test_a_line_says_when_its_cell_holds_more_than_one_thing(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A picker reaching into a cell of black and white shoes is told to look."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-MIXED", stock=4)
    _put_away(client, warehouse, ids["Qora / 42"], 4, "B-02-02")
    _put_away(client, warehouse, ids["Oq / 42"], 4, "B-02-02")

    order = _order(client, auth, card["id"], ids["Qora / 42"], quantity=1)
    task = client.post(
        f"{API}/warehouse/pick/orders/{order['id']}", headers=warehouse
    ).json()
    assert task["lines"][0]["mixed_cell"] is True


def test_picking_moves_the_goods_and_completing_packs_the_order(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-PICK", stock=5)
    leaf = ids["Qora / 42"]
    _put_away(client, warehouse, leaf, 5, "A-01-01")
    order = _order(client, auth, card["id"], leaf, quantity=2)

    task = client.post(
        f"{API}/warehouse/pick/orders/{order['id']}", headers=warehouse
    ).json()
    took = client.post(
        f"{API}/warehouse/pick/{task['id']}/take",
        headers={**warehouse, "Idempotency-Key": f"take-{task['id']}"},
    )
    assert took.status_code == 200, took.text
    assert took.json()["status"] == "picking"

    line = took.json()["lines"][0]
    fetched = client.post(
        f"{API}/warehouse/pick/{task['id']}/lines/{line['id']}",
        json={"qty": 2},
        headers={**warehouse, "Idempotency-Key": f"line-{line['id']}"},
    )
    assert fetched.status_code == 200, fetched.text
    assert _in("A-01-01", leaf) == 3
    assert _in(loc.YIGIM, leaf) == 2
    # Picked goods are off the shelf, and the order still holds them — the
    # shop must not offer the same two shirts to anybody else.
    assert _sellable(leaf) == 3
    _assert_the_room_adds_up()

    done = client.post(
        f"{API}/warehouse/pick/{task['id']}/complete",
        headers={**warehouse, "Idempotency-Key": f"done-{task['id']}"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "picked"
    assert client.get(
        f"{API}/orders/{order['id']}", headers=auth
    ).json()["status"] == "packing"


def test_a_task_cannot_be_completed_half_walked(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-HALF", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"], quantity=2)
    task = client.post(
        f"{API}/warehouse/pick/orders/{order['id']}", headers=warehouse
    ).json()
    client.post(
        f"{API}/warehouse/pick/{task['id']}/take",
        headers={**warehouse, "Idempotency-Key": f"take-half-{task['id']}"},
    )
    refused = client.post(
        f"{API}/warehouse/pick/{task['id']}/complete",
        headers={**warehouse, "Idempotency-Key": f"done-half-{task['id']}"},
    )
    assert refused.status_code == 409, refused.text


def test_two_pickers_cannot_take_the_same_trolley(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-RACE", stock=3)
    order = _order(client, auth, card["id"], ids["Qora / 42"])
    task = client.post(
        f"{API}/warehouse/pick/orders/{order['id']}", headers=warehouse
    ).json()

    client.post(
        f"{API}/warehouse/pick/{task['id']}/take",
        headers={**warehouse, "Idempotency-Key": f"race-a-{task['id']}"},
    )
    other = staff(UserRole.WAREHOUSE, "+998900009003")
    second = client.post(
        f"{API}/warehouse/pick/{task['id']}/take",
        headers={**other, "Idempotency-Key": f"race-b-{task['id']}"},
    )
    assert second.status_code == 409, second.text


# --------------------------------------------------------------------------- counting


def test_a_count_records_what_was_found_as_a_difference(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Never an assignment. A cell three short is three that went somewhere."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-COUNT", stock=6)
    leaf = ids["Qora / 42"]
    _put_away(client, warehouse, leaf, 6, "C-01-01")

    started = client.post(
        f"{API}/warehouse/counts", json={"code": "C-01-01"}, headers=warehouse
    )
    assert started.status_code == 201, started.text
    count = started.json()
    assert count["lines"][0]["expected_qty"] == 6

    submitted = client.post(
        f"{API}/warehouse/counts/{count['id']}/submit",
        json={"lines": [{"variant_id": leaf, "counted_qty": 4}], "note": "sanaldi"},
        headers={**warehouse, "Idempotency-Key": f"count-{count['id']}"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "closed"

    assert _in("C-01-01", leaf) == 4
    assert _shelf(leaf) == 4
    _assert_the_room_adds_up()

    ledger = client.get(
        f"{API}/warehouse/stock/movements",
        params={"variant_id": leaf, "kind": "adjust"},
        headers=warehouse,
    ).json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["quantity"] == 2
    assert ledger["items"][0]["from_code"] == "C-01-01"
    assert ledger["items"][0]["to_code"] == "—"

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.action == "stock.count", AuditLog.entity_id == leaf
            )
        ).all()
    assert len(logged) == 1
    assert logged[0].old_value == "6"
    assert logged[0].new_value == "4"


def test_a_count_can_find_something_nobody_expected(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Goods turn up in the wrong cell, which is what a count is for."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SURPRISE", stock=2)
    leaf = ids["Oq / 43"]

    count = client.post(
        f"{API}/warehouse/counts", json={"code": "C-04-04"}, headers=warehouse
    ).json()
    assert count["lines"] == []

    client.post(
        f"{API}/warehouse/counts/{count['id']}/submit",
        json={"lines": [{"variant_id": leaf, "counted_qty": 3}]},
        headers={**warehouse, "Idempotency-Key": f"count-new-{count['id']}"},
    )
    assert _in("C-04-04", leaf) == 3
    assert _shelf(leaf) == 3
    _assert_the_room_adds_up()


def test_a_count_that_skips_a_line_is_refused(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Silence is not agreement.

    The rule was written down and not enforced: a variant the system believes
    is in this cell and that nobody answered for kept its old figure, with a
    stocktake's signature on it. The whole point of counting is to find the
    cell that disagrees.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SKIP", stock=4)
    started = client.post(
        f"{API}/warehouse/counts", json={"code": BENCH}, headers=warehouse
    )
    assert started.status_code == 201, started.text
    count = started.json()
    assert len(count["lines"]) >= 2

    one = count["lines"][0]
    short = client.post(
        f"{API}/warehouse/counts/{count['id']}/submit",
        json={"lines": [{"variant_id": one["variant_id"], "counted_qty": 1}]},
        headers={**warehouse, "Idempotency-Key": f"skip-{count['id']}"},
    )
    assert short.status_code == 400, short.text
    assert "sanash kerak" in short.json()["detail"]

    # Answered in full, and the difference goes in the ledger as always.
    whole = client.post(
        f"{API}/warehouse/counts/{count['id']}/submit",
        json={
            "lines": [
                {"variant_id": line["variant_id"], "counted_qty": line["expected_qty"]}
                for line in count["lines"]
            ]
        },
        headers={**warehouse, "Idempotency-Key": f"whole-{count['id']}"},
    )
    assert whole.status_code == 200, whole.text
    _assert_the_room_adds_up()


def test_one_count_per_cell_at_a_time(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    first = client.post(
        f"{API}/warehouse/counts", json={"code": "B-04-04"}, headers=warehouse
    )
    assert first.status_code == 201
    second = client.post(
        f"{API}/warehouse/counts", json={"code": "B-04-04"}, headers=warehouse
    )
    assert second.status_code == 409, second.text


# --------------------------------------------------------------------------- labels


def test_the_label_sheet_reprints_the_code_that_is_on_the_row(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A variant's barcode is permanent: reprinted, never regenerated."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-LABEL", stock=2)
    leaf = ids["Qora / 42"]
    with Session(engine) as session:
        barcode = session.get(ProductVariant, leaf).barcode

    sheet = client.get(
        f"{API}/warehouse/labels", params={"variant_id": leaf}, headers=warehouse
    ).json()
    assert len(sheet["products"]) == 1
    label = sheet["products"][0]
    assert label["barcode"] == barcode
    assert label["variant_label"] == "Qora · 42"
    assert label["sku"].startswith("ALFA-LABEL")

    again = client.get(
        f"{API}/warehouse/labels", params={"variant_id": leaf}, headers=warehouse
    ).json()
    assert again["products"][0]["barcode"] == barcode


def test_the_cell_labels_are_a_full_set(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    sheet = client.get(
        f"{API}/warehouse/labels", params={"cells": True}, headers=warehouse
    ).json()
    assert len(sheet["cells"]) == sum(c * r for _, c, r, _ in loc.RACKS)
    assert sheet["cells"][0]["code"] == "A-01-01"


# --------------------------------------------------------------------------- the grid


def test_the_grid_is_generated_in_one_step_and_never_renumbered(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Adding a colour in October must not move the barcodes printed in June."""
    card = _card(client, admin, sku="ALFA-GRID")
    first = client.put(
        f"{API}/admin/products/{card['id']}/variants",
        json={
            "colours": [{"colour": "Qora", "hex": "#000"}],
            "sizes": ["41", "42"],
            "price": 300_000,
        },
        headers=admin,
    )
    assert first.status_code == 200, first.text
    made = first.json()
    assert len(made) == 2
    assert {row["label"] for row in made} == {"Qora · 41", "Qora · 42"}
    assert all(row["barcode"] for row in made)
    was = {row["label"]: row["barcode"] for row in made}

    second = client.put(
        f"{API}/admin/products/{card['id']}/variants",
        json={
            "colours": [{"colour": "Qora", "hex": "#000"}, {"colour": "Oq", "hex": "#fff"}],
            "sizes": ["41", "42"],
            "price": 300_000,
        },
        headers=admin,
    ).json()
    assert len(second) == 4
    now = {row["label"]: row["barcode"] for row in second}
    assert {label: now[label] for label in was} == was


def test_a_variant_carrying_history_cannot_be_deleted(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-KEEP", stock=1)
    leaf = ids["Qora / 42"]

    grid = client.get(
        f"{API}/admin/products/{card['id']}/variants", headers=admin
    ).json()
    used = next(row for row in grid if row["id"] == leaf)
    spare = next(row for row in grid if row["id"] == ids["Oq / 43"])
    assert used["can_delete"] is False
    assert used["blocked_reason"]
    assert spare["can_delete"] is True

    refused = client.delete(
        f"{API}/admin/products/{card['id']}/variants/{leaf}", headers=admin
    )
    assert refused.status_code == 409, refused.text
    allowed = client.delete(
        f"{API}/admin/products/{card['id']}/variants/{spare['id']}", headers=admin
    )
    assert allowed.status_code == 200, allowed.text


def test_repricing_one_size_moves_the_card_and_is_audited(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-REPRICE", stock=2)
    repriced = client.patch(
        f"{API}/admin/products/{card['id']}/variants/{ids['Qora / 42']}",
        json={"price": 350_000},
        headers=admin,
    )
    assert repriced.status_code == 200, repriced.text
    assert client.get(f"{API}/products/{card['id']}").json()["price"] == 350_000

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.action == "variant.price",
                AuditLog.entity_id == ids["Qora / 42"],
            )
        ).all()
    assert len(logged) == 1


def test_taking_the_last_photograph_down_pulls_the_card_out_of_the_shop(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The rule holds in both directions, or it is not a rule."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-UNPIC", stock=2)
    images = client.get(
        f"{API}/admin/products/{card['id']}/images", headers=admin
    ).json()
    assert {row["colour"] for row in images} == {"Qora", "Oq"}

    gone = client.delete(
        f"{API}/admin/products/{card['id']}/images/{images[0]['id']}", headers=admin
    )
    assert gone.status_code == 200, gone.text
    assert client.get(f"{API}/products/{card['id']}").status_code == 404


# --------------------------------------------------------------------------- the dashboard


def test_the_dashboard_answers_with_figures_that_link(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A figure that is not a link is a dead end."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-DASH", stock=4)
    _order(client, auth, card["id"], ids["Qora / 42"])
    client.post(f"{API}/warehouse/supplies", json={"sacks": 2}, headers=warehouse)
    _card(client, admin, sku="ALFA-DASH-DRAFT")

    board = client.get(f"{API}/admin/dashboard", headers=admin)
    assert board.status_code == 200, board.text
    body = board.json()
    tiles = {tile["key"]: tile for tile in body["tiles"]}

    assert tiles["unsorted_sacks"]["value"] >= 2
    assert tiles["orders_today"]["value"] >= 1
    # Goods on a shelf that the shop cannot sell: the tile that replaced a
    # narrower "no photograph" one, and the only figure here that counts money
    # standing still rather than work arriving.
    assert tiles["held_back"]["value"] >= 1
    assert tiles["held_back"]["href"] == "/sotuvga-chiqarish"
    assert all(tile["href"] for tile in body["tiles"])

    # Fourteen days, quiet ones included: a chart that skips empty days draws
    # a shop that was busy every day it was open.
    assert len(body["sales"]) == 14
    assert body["sales"][-1]["orders"] >= 1


def test_the_dashboard_counts_what_left_rather_than_what_sold(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """An order placed and never delivered moved nothing."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-MOVER", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"], quantity=3)

    before = client.get(f"{API}/admin/dashboard", headers=admin).json()["movers"]
    assert ids["Qora / 42"] not in [row["variant_id"] for row in before]

    _to_the_door(client, admin, order["id"])
    after = client.get(f"{API}/admin/dashboard", headers=admin).json()["movers"]
    mine = next(row for row in after if row["variant_id"] == ids["Qora / 42"])
    assert mine["qty"] == 3
    assert mine["variant_label"] == "Qora · 42"


def test_the_receiving_desk_can_read_and_write_cards(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The sorting screen searches the existing cards first.

    A bench that cannot search them writes a third new card for goods that
    already have one, which is how a catalogue rots — so the catalogue's
    reading doors, and writing one card with the goods in front of you, are
    the desk's as well as the office's.
    """
    card = _card(client, admin, sku="ALFA-DESK")

    found = client.get(
        f"{API}/admin/products", params={"q": "ALFA-DESK"}, headers=warehouse
    )
    assert found.status_code == 200, found.text
    assert [p["id"] for p in found.json()["items"]] == [card["id"]]

    written = client.post(
        f"{API}/admin/products",
        json={
            "sku": "ALFA-DESK-2",
            "title": "Sochiq",
            "category_slug": "krossovkalar",
            "price": 40_000,
        },
        headers=warehouse,
    )
    assert written.status_code == 201, written.text

    # Categories are read at the desk too — the new-card form picks from them.
    assert client.get(f"{API}/admin/categories", headers=warehouse).status_code == 200
    # But writing one is the office's.
    refused = client.post(
        f"{API}/admin/categories",
        json={"slug": "yangi", "name": "Yangi"},
        headers=warehouse,
    )
    assert refused.status_code == 403, refused.text


def test_a_product_photograph_is_padded_onto_a_white_square(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A grid of cards where every tile crops differently looks broken.

    Padding rather than cropping, because the goods are what was framed and a
    crop cuts the toe off a shoe.
    """
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (800, 400), (12, 34, 56)).save(buffer, "PNG")

    uploaded = client.post(
        f"{API}/media",
        params={"square": True},
        files={"file": ("shoe.png", buffer.getvalue(), "image/png")},
        headers=admin,
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["width"] == body["height"] == 800

    # And off by default, because a doorstep is not a product.
    buffer.seek(0)
    plain = client.post(
        f"{API}/media",
        files={"file": ("door.png", buffer.getvalue(), "image/png")},
        headers=admin,
    )
    assert plain.json()["width"] != plain.json()["height"]


# --------------------------------------------------------------------------- the shop


def test_the_card_advertises_the_cheapest_of_its_variants(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The money is on the variant: a 43 can cost more than a 41."""
    card = _card(client, admin, sku="ALFA-PRICE", price=900_000)
    ids = _variants(client, admin, card["id"], ["Qora"], ["42", "43"], price=900_000)
    with Session(engine) as session:
        cheap = session.get(ProductVariant, ids["Qora / 42"])
        cheap.price = 700_000
        session.add(cheap)
        session.commit()
    _book_in(client, warehouse, [(ids["Qora / 42"], 2), (ids["Qora / 43"], 2)])
    _publish(client, admin, card["id"], "Qora")

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

    # The grid is flat: four cells, each answering for itself.
    cells = {f"{v['colour']} · {v['size']}": v for v in shown["variants"]}
    assert set(cells) == {"Qora · 42", "Qora · 43", "Oq · 42", "Oq · 43"}
    assert cells["Qora · 42"]["stock_left"] == 4
    assert cells["Qora · 43"]["stock_left"] == 0
    assert [c["colour"] for c in shown["colours"]] == ["Qora", "Oq"]


def test_the_listing_hides_what_cannot_be_bought(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SOLDOUT", stock=1)
    for leaf in (ids["Qora / 42"], ids["Oq / 42"]):
        client.post(
            f"{API}/warehouse/stock/damage",
            json={"variant_id": leaf, "quantity": 1, "reason": "brak"},
            headers=warehouse,
        )

    shown = client.get(f"{API}/products", params={"q": "ALFA-SOLDOUT"}).json()
    assert card["id"] not in [p["id"] for p in shown["items"]]
    with_sold_out = client.get(
        f"{API}/products", params={"q": "ALFA-SOLDOUT", "show_sold_out": True}
    ).json()["items"]
    assert card["id"] in [p["id"] for p in with_sold_out]


def test_search_finds_a_card_by_its_title(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, _ = _on_sale(client, admin, warehouse, sku="ALFA-SEARCH")
    found = client.get(f"{API}/products", params={"q": "ALFA-SEARCH"}).json()
    assert [p["id"] for p in found["items"]] == [card["id"]]

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
    # The hold moved nothing: the goods are still standing where they stood,
    # and the ledger has nothing to say about a basket.
    assert theirs.status_code == 409, theirs.text
    assert _shelf(ids["Qora / 42"]) == 1
    assert _in(BENCH, ids["Qora / 42"]) == 1
    _assert_the_room_adds_up()


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
        assert st.reserved(session, ids["Qora / 42"]) == 1
    assert _sellable(ids["Qora / 42"]) == 0

    client.delete(f"{API}/cart", headers=auth)
    with Session(engine) as session:
        assert st.reserved(session, ids["Qora / 42"]) == 0
    assert _sellable(ids["Qora / 42"]) == 1


# --------------------------------------------------------------------------- orders


def test_paying_for_an_order_moves_nothing_in_the_room(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    """Money does not move goods. A courier at a door does.

    Paying used to take the goods off the shelf, which meant the shop could
    not answer "where is it" between the till and the door — and a refusal at
    that door had nothing to put back.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-SALE", stock=5)
    leaf = ids["Qora / 42"]
    _order(client, auth, card["id"], leaf, quantity=2)

    assert _shelf(leaf) == 5
    assert _in(BENCH, leaf) == 5
    # Held rather than gone: nobody else may promise them.
    assert _sellable(leaf) == 3
    with Session(engine) as session:
        assert session.get(Product, card["id"]).sold_count == 2
    _assert_the_room_adds_up()


def test_a_cash_order_holds_the_goods_the_same_way(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CASH", stock=5)
    leaf = ids["Qora / 42"]
    _order(client, auth, card["id"], leaf, quantity=2, payment="cash")

    assert _shelf(leaf) == 5
    with Session(engine) as session:
        assert st.reserved(session, leaf) == 2


def test_a_card_order_is_only_paid_once_the_card_has_been_charged(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """`paid` used to mean "they tapped Karta", which is not the same thing.

    It was `payment_method == CARD`, decided at the moment the order was
    written and never checked against anything — so a shopper could tap Karta,
    take delivery, and the shop would have a row saying it had been paid for
    goods nobody paid for. The courier believed it too: nothing is asked for at
    the door on a card order.
    """
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Order
    from app.payments import DEV_TOKEN_PREFIX

    card, ids = _on_sale(client, admin, warehouse, sku="PAY-CHARGED", stock=3)
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    assert order["paid"] is True
    # And it carries the charge's own name, which is what a refund or a bank
    # statement is reconciled against. Read from the row rather than the
    # response: it is the shop's record, not the customer's business.
    with Session(engine) as session:
        stored = session.exec(select(Order).where(Order.code == order["code"])).one()
    assert stored.payment_reference.startswith(DEV_TOKEN_PREFIX)


def test_a_refused_card_leaves_no_order_behind(
    client: TestClient,
    sign_in: Callable[[str], dict[str, str]],
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """The charge happens before the order, so a refusal costs nothing.

    An order written first and charged second is an order somebody has to go
    back and cancel — and the counts it held have to be put back by hand. So
    nothing is written: the basket is still there, the shelf never moved, and
    the customer gets a sentence they can act on.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="PAY-REFUSED", stock=3)
    shopper = sign_in("+998900007001")
    before = client.get(f"{API}/admin/orders", headers=admin).json()["items"]

    client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"]},
        headers=shopper,
    )
    broke = _payment_card(client, shopper, last4="0001")
    refused = client.post(
        f"{API}/orders",
        json={
            "address_id": _address(client, shopper),
            "payment_method": "card",
            "payment_card_id": broke,
        },
        headers=shopper,
    )

    assert refused.status_code == 402, refused.text
    assert "mablag" in refused.json()["detail"]

    after = client.get(f"{API}/admin/orders", headers=admin).json()["items"]
    assert len(after) == len(before)
    # The basket is untouched, so the customer can try another card rather
    # than build the order again.
    assert client.get(f"{API}/cart", headers=shopper).json()["items"]


def test_the_test_processor_names_the_reason_it_refused(
    client: TestClient,
    sign_in: Callable[[str], dict[str, str]],
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """Three refusals, three sentences — see ``app.payments``.

    One "payment failed" for all of them is one sentence nobody can act on:
    another card, more money on this one and a card that has expired are three
    different things to go and do.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="PAY-REASONS", stock=6)
    shopper = sign_in("+998900007002")
    address = _address(client, shopper)
    for last4, word in (("0000", "rad etdi"), ("0001", "mablag"), ("0002", "muddat")):
        client.post(
            f"{API}/cart/items",
            json={"product_id": card["id"], "variant_id": ids["Qora / 42"]},
            headers=shopper,
        )
        refused = client.post(
            f"{API}/orders",
            json={
                "address_id": address,
                "payment_method": "card",
                "payment_card_id": _payment_card(
                    client, shopper, last4=last4, default=False
                ),
            },
            headers=shopper,
        )
        assert refused.status_code == 402, refused.text
        assert word in refused.json()["detail"], (last4, refused.json())


def test_a_card_order_names_a_card_and_somebody_elses_is_not_found(
    client: TestClient,
    sign_in: Callable[[str], dict[str, str]],
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """Two ways to fail before the processor is asked anything.

    A card order with no card is the client's mistake and says so; a card that
    belongs to another customer is a 404 rather than a 403, because telling a
    caller that a card they cannot touch exists tells them about somebody else.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="PAY-NAMED", stock=3)
    shopper = sign_in("+998900007003")
    stranger = sign_in("+998900007004")
    address = _address(client, shopper)

    client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"]},
        headers=shopper,
    )
    nameless = client.post(
        f"{API}/orders",
        json={"address_id": address, "payment_method": "card"},
        headers=shopper,
    )
    assert nameless.status_code == 400, nameless.text

    borrowed = client.post(
        f"{API}/orders",
        json={
            "address_id": address,
            "payment_method": "card",
            "payment_card_id": _payment_card(client, stranger),
        },
        headers=shopper,
    )
    assert borrowed.status_code == 404, borrowed.text


def test_a_cash_order_is_not_paid_when_it_is_placed(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """Cash is settled at a door, by a courier, and not before."""
    card, ids = _on_sale(client, admin, warehouse, sku="PAY-CASH", stock=3)
    order = _order(client, auth, card["id"], ids["Qora / 42"], payment="cash")
    assert order["paid"] is False


def test_one_saved_card_is_the_default_and_only_one(
    client: TestClient, sign_in: Callable[[str], dict[str, str]]
) -> None:
    """A shopper with one card and no default is a checkout with nothing chosen.

    So the first one saved is the default whether or not it was asked for, and
    marking another one moves it — one default, never two. Its own customer,
    because the card list is per person and the suite shares one database.
    """
    shopper = sign_in("+998900007005")
    first = _payment_card(client, shopper, last4="9012", default=False)
    cards = client.get(f"{API}/payment-cards", headers=shopper).json()
    assert [c["id"] for c in cards] == [first]
    assert cards[0]["is_default"] is True
    # Assembled on the server so three clients cannot spell it three ways.
    assert cards[0]["expiry"] == "12/30"

    second = _payment_card(client, shopper, last4="1111", default=True)
    cards = client.get(f"{API}/payment-cards", headers=shopper).json()
    assert [c["id"] for c in cards if c["is_default"]] == [second]
    # The default comes back first, which is the order the checkout picks from.
    assert cards[0]["id"] == second

    gone = client.delete(f"{API}/payment-cards/{first}", headers=shopper)
    assert gone.status_code == 200, gone.text
    left = client.get(f"{API}/payment-cards", headers=shopper).json()
    assert [c["id"] for c in left] == [second]


def test_a_saved_card_never_holds_a_number(
    client: TestClient, sign_in: Callable[[str], dict[str, str]]
) -> None:
    """The one property of this table worth a test of its own.

    Nothing in the row can be used to reconstruct a card: four digits, a name,
    an expiry and a token. If a column ever appears that could, this fails —
    which is the point of asserting the whole set rather than a few members.
    """
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import PaymentCard, User

    shopper = sign_in("+998900007006")
    _payment_card(client, shopper, last4="9012")
    with Session(engine) as session:
        owner = session.exec(
            select(User).where(User.phone == "+998900007006")
        ).one()
        card = session.exec(
            select(PaymentCard).where(PaymentCard.user_id == owner.id)
        ).one()
    stored = card.model_dump()
    assert set(stored) == {
        "id",
        "user_id",
        "brand",
        "last4",
        "holder",
        "expiry_month",
        "expiry_year",
        "status",
        "is_default",
        "processor_token",
        "created_at",
    }
    assert len(stored["last4"]) == 4


def test_cancelling_an_order_puts_everything_back(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CANCEL", stock=5)
    leaf = ids["Qora / 42"]
    order = _order(client, auth, card["id"], leaf, quantity=2)

    assert _sellable(leaf) == 3

    off = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason": "Fikrimdan qaytdim"},
        headers=auth,
    )
    assert off.status_code == 200, off.text
    assert _shelf(leaf) == 5
    assert _ledger(leaf) == 5
    # The hold ends with the order, so the goods are on offer again.
    assert _sellable(leaf) == 5
    with Session(engine) as session:
        assert session.get(Product, card["id"]).sold_count == 0
    _assert_the_room_adds_up()


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
        f"{API}/admin/orders", params={"status": "placed"}, headers=admin
    ).json()["items"]
    ids_in_order = [o["id"] for o in queue]
    assert ids_in_order == sorted(ids_in_order)

    history = client.get(f"{API}/admin/orders", headers=admin).json()["items"]
    newest = [o["id"] for o in history]
    assert newest == sorted(newest, reverse=True)


def test_a_card_is_sized_or_sizeless_and_not_both(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A cap has no size, and the second sack of caps must not invent one.

    One card held a sizeless grey cap beside a grey cap in `M` — the same cap
    on the same shelf under two names, and the shop drew a blank size chip
    next to a real one. The desk is also told which kinds have never had a
    size, so it asks the right question before anybody types into a box that
    will not go away.
    """
    first = client.post(
        f"{API}/warehouse/piles",
        json={
            "kind": "Kepka",
            "colour": "Kulrang",
            "sizes": [{"size": "", "quantity": 6}],
            "unit_cost": 12_000,
            "location_code": "A-04-04",
        },
        headers={**warehouse, "Idempotency-Key": "cap-one"},
    )
    assert first.status_code == 201, first.text
    card = first.json()["product"]

    vocab = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert "Kepka" in vocab["sizeless"]
    assert vocab["sizes"].get("Kepka") in (None, [])

    sized = client.post(
        f"{API}/warehouse/piles",
        json={
            "product_id": card["id"],
            "colour": "Kulrang",
            "sizes": [{"size": "M", "quantity": 4}],
            "unit_cost": 12_000,
            "location_code": "A-04-04",
        },
        headers={**warehouse, "Idempotency-Key": "cap-two"},
    )
    assert sized.status_code == 409, sized.text
    assert "o'lchamsiz" in sized.json()["detail"]

    # And the other way round, on a card that does have sizes.
    shirt = client.post(
        f"{API}/warehouse/piles",
        json={
            "kind": "Ko'ylak",
            "colour": "Oq",
            "sizes": [{"size": "m", "quantity": 3}],
            "unit_cost": 20_000,
            "location_code": "A-04-03",
        },
        headers={**warehouse, "Idempotency-Key": "shirt-one"},
    )
    assert shirt.status_code == 201, shirt.text
    # One spelling, whatever the hurry: `m` is `M`.
    assert [line["variant_label"] for line in shirt.json()["labels"]] == ["Oq / M"]

    bare = client.post(
        f"{API}/warehouse/piles",
        json={
            "product_id": shirt.json()["product"]["id"],
            "colour": "Oq",
            "sizes": [{"size": "", "quantity": 2}],
            "unit_cost": 20_000,
            "location_code": "A-04-03",
        },
        headers={**warehouse, "Idempotency-Key": "shirt-two"},
    )
    assert bare.status_code == 409, bare.text


def test_a_size_received_by_mistake_can_leave_the_shop_window(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A typo cannot be deleted, so it has to be able to stop being offered.

    Every movement and order line points at a cell, so a cell that has ever
    held anything is not deletable — and that left a cap booked in as `M`
    struck through on the product page for the life of the card. Retiring
    keeps the ledger and stops the offer, and is refused while the cell still
    holds goods: hiding stock the shop paid for is worse than an untidy row.
    """
    booked = client.post(
        f"{API}/warehouse/piles",
        json={
            "kind": "Ko'ylak",
            "colour": "Yashil",
            "sizes": [{"size": "M", "quantity": 4}, {"size": "KS", "quantity": 2}],
            "unit_cost": 30_000,
            "location_code": "C-04-01",
        },
        headers={**warehouse, "Idempotency-Key": "typo-pile"},
    )
    assert booked.status_code == 201, booked.text
    card = booked.json()["product"]
    grid = client.get(
        f"{API}/admin/products/{card['id']}/variants", headers=admin
    ).json()
    wrong = next(row for row in grid if row["size"] == "KS")

    # It has a ledger behind it, so it cannot be deleted — that is the point.
    gone = client.delete(
        f"{API}/admin/products/{card['id']}/variants/{wrong['id']}", headers=admin
    )
    assert gone.status_code == 409, gone.text

    refused = client.post(
        f"{API}/admin/products/{card['id']}/variants/{wrong['id']}/retired",
        json={"retired": True},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    assert "2" in refused.json()["detail"]

    # Written off the shelf — the two were never there — and then it can go.
    emptied = client.post(
        f"{API}/warehouse/stock/empty",
        json={"code": "C-04-01", "reason": "KS degan o'lcham yo'q edi"},
        headers=admin,
    )
    assert emptied.status_code == 200, emptied.text

    retired = client.post(
        f"{API}/admin/products/{card['id']}/variants/{wrong['id']}/retired",
        json={"retired": True},
        headers=admin,
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["retired"] is True

    # The editor still holds it; the shop is not offering it.
    after = client.get(
        f"{API}/admin/products/{card['id']}/variants", headers=admin
    ).json()
    assert wrong["id"] in [row["id"] for row in after]
    assert [row["retired"] for row in after if row["id"] == wrong["id"]] == [True]

    # Filed, priced and photographed — the three gates — so the shop can be
    # asked what it offers.
    _category(client, admin, "koylaklar")
    client.patch(
        f"{API}/admin/products/{card['id']}",
        json={"category_slug": "koylaklar"},
        headers=admin,
    )
    client.post(
        f"{API}/admin/products/{card['id']}/price",
        json={"price": 90_000},
        headers=admin,
    )
    _publish(client, admin, card["id"], "Yashil")

    shown = client.get(f"{API}/products/{card['id']}").json()
    assert [v["size"] for v in shown["variants"]] == ["M"]

    # And back again, for a size this shop starts buying after all.
    back = client.post(
        f"{API}/admin/products/{card['id']}/variants/{wrong['id']}/retired",
        json={"retired": False},
        headers=admin,
    )
    assert back.status_code == 200, back.text
    assert back.json()["retired"] is False


def test_a_colour_that_has_run_out_is_said_out_loud(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """One colour finishing is the thing nobody notices.

    The card still says "sotuvda", the total on it still reads comfortably,
    and the first anybody hears of it is a customer ordering black. The
    dashboard counted from one left upwards, so a cell that had actually
    finished fell out of the bottom of it.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-GONE", stock=1)

    before = client.get(f"{API}/admin/products?stock=out", headers=admin).json()
    mine = next(row for row in before["items"] if row["id"] == card["id"])
    # The 43s of this card were never received, so they are already empty —
    # and the 42s, which were, are not named yet.
    assert "Qora / 42" not in mine["sold_out"]

    # A customer buys the only black 42 there was, and a courier takes it out.
    order = _order(client, auth, card["id"], ids["Qora / 42"], payment="cash")
    _to_the_door(client, admin, order["id"])

    page = client.get(f"{API}/admin/products?stock=out", headers=admin).json()
    mine = next(row for row in page["items"] if row["id"] == card["id"])
    assert "Qora / 42" in mine["sold_out"]

    tiles = client.get(f"{API}/admin/dashboard", headers=admin).json()["tiles"]
    gone = next(tile for tile in tiles if tile["key"] == "sold_out")
    assert gone["value"] >= 1
    # The tile has to land somewhere that reads the filter. It used to link to
    # `?low=1`, which nothing on either side read.
    assert gone["href"] == "/mahsulotlar?stock=out"

    # And the shop says so to the customer, on the colour and not only in a
    # total that is still positive.
    shown = client.get(f"{API}/products/{card['id']}").json()
    black = next(one for one in shown["colours"] if one["colour"] == "Qora")
    assert black["in_stock"] is False


def test_the_warehouse_may_pack_but_not_cancel(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-BENCH", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    packed = client.post(
        f"{API}/admin/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=warehouse,
    )
    assert packed.status_code == 200, packed.text

    called_off = client.post(
        f"{API}/admin/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "bekor"},
        headers=warehouse,
    )
    assert called_off.status_code == 403, called_off.text


def test_the_assistant_answers_the_telephone_but_does_not_call_off_a_sale(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    seller: dict[str, str],
    auth: dict[str, str],
) -> None:
    """The shop assistant reads the queue and moves an order along.

    A customer who rings to ask where their order is asks whoever answers the
    telephone, and that person had no screen with the answer on it — so every
    such call reached the owner. Cancelling stays the owner's: somebody has to
    answer for a sale called off, and it is the person whose shop it is.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-PHONE", stock=5)
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    queue = client.get(f"{API}/admin/orders", headers=seller)
    assert queue.status_code == 200, queue.text
    mine = next(row for row in queue.json()["items"] if row["id"] == order["id"])
    # The buttons come from here, so the move the assistant may not make is
    # not offered rather than refused after the tap.
    assert "cancelled" not in mine["next_statuses"]

    one = client.get(f"{API}/admin/orders/{order['id']}", headers=seller)
    assert one.status_code == 200, one.text

    packed = client.post(
        f"{API}/admin/orders/{order['id']}/status",
        json={"status": "packing"},
        headers=seller,
    )
    assert packed.status_code == 200, packed.text

    called_off = client.post(
        f"{API}/admin/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "bekor"},
        headers=seller,
    )
    assert called_off.status_code == 403, called_off.text

    # The owner's own row still offers it.
    owners = client.get(f"{API}/admin/orders", headers=admin).json()["items"]
    theirs = next(row for row in owners if row["id"] == order["id"])
    assert "cancelled" in theirs["next_statuses"]


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
        f"{API}/admin/orders/{order['id']}/status",
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
    # The door is where the goods actually leave the building.
    assert _shelf(ids["Qora / 42"]) == 4
    assert _in(BENCH, ids["Qora / 42"]) == 4
    _assert_the_room_adds_up()


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
        f"{API}/admin/orders/{order['id']}/status",
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
    _assert_the_room_adds_up()


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
        f"{API}/admin/returns/{request_id}/approve", json={}, headers=admin
    )
    assert approved.status_code == 200, approved.text

    refunded = client.post(
        f"{API}/admin/returns/{request_id}/refund",
        json={"restock": True, "note": "butun"},
        headers=admin,
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["refund_amount"] > 0
    # Back in the building, in the receiving area, and on sale again. The
    # four that never left are on the shelf they were booked onto; the one
    # that came back is at the receiving desk, because a parcel off a
    # courier's round has not been put anywhere yet.
    assert _shelf(leaf) == 5
    assert _in(BENCH, leaf) == 4
    assert _in(loc.QABUL, leaf) == 1
    assert _sellable(leaf) == 5
    _assert_the_room_adds_up()


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
    client.post(f"{API}/admin/returns/{request_id}/approve", json={}, headers=admin)
    client.post(
        f"{API}/admin/returns/{request_id}/refund",
        json={"restock": True},
        headers=admin,
    )
    assert _shelf(leaf) == 5

    inspected = client.post(
        f"{API}/warehouse/returns/{request_id}/inspect",
        json={"result": "ok", "note": "butun"},
        headers=warehouse,
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["relisted"] is True
    assert _shelf(leaf) == 5
    _assert_the_room_adds_up()


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
    client.post(f"{API}/admin/returns/{request_id}/approve", json={}, headers=admin)
    client.post(
        f"{API}/admin/returns/{request_id}/refund",
        json={"restock": False},
        headers=admin,
    )
    inspected = client.post(
        f"{API}/warehouse/returns/{request_id}/inspect",
        json={"result": "damaged", "note": "yirtilgan"},
        headers=warehouse,
    )
    assert inspected.status_code == 200, inspected.text
    # The parcel is recorded as having arrived — a parcel nobody booked in is
    # a parcel the room cannot find — but it lands in the damaged corner and
    # nothing there is for sale.
    assert inspected.json()["relisted"] is True
    assert _shelf(leaf) == 5
    assert _in(loc.BRAK, leaf) == 1
    assert _sellable(leaf) == 4
    _assert_the_room_adds_up()


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
    client.post(f"{API}/admin/returns/{request_id}/approve", json={}, headers=admin)

    first = client.post(
        f"{API}/warehouse/returns/{request_id}/inspect",
        json={"result": "ok"},
        headers=warehouse,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"{API}/warehouse/returns/{request_id}/inspect",
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
    client.post(f"{API}/admin/returns/{request_id}/approve", json={}, headers=admin)

    waiting = client.get(
        f"{API}/admin/returns", params={"awaiting": "inspection"}, headers=warehouse
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
        f"{API}/admin/users/{user_id}/role",
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
        f"{API}/admin/users/{only}/role",
        json={"role": "warehouse"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text


def test_the_last_admin_cannot_be_switched_off_either(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The same loss through the other door.

    Demoting the last admin was already refused. Switching their account off
    leaves the role sitting on a row nobody can sign in to, which is the same
    building with the same nobody in it — and until the rule was shared it was
    enforced on one of the two.
    """
    with Session(engine) as session:
        only = session.exec(
            select(User).where(
                User.role == UserRole.ADMIN, col(User.is_active).is_(True)
            )
        ).one().id

    refused = client.post(
        f"{API}/admin/users/{only}/active",
        json={"active": False, "note": "ta'tilga chiqdi"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    with Session(engine) as session:
        assert session.get(User, only).is_active is True


def test_the_staff_list_is_colleagues_and_not_customers(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """The complaint that started all of this.

    The screen headed "Xodimlar" was reading ``/admin/users``, which answers
    with every account in the shop — so the list of the five people who work
    here grew by one every time somebody bought a pair of shoes. The old door
    still answers that way on purpose, because looking a number up is a real
    job; the staff door does not.
    """
    listing = client.get(
        f"{API}/admin/staff", params={"page_size": 100}, headers=admin
    )
    assert listing.status_code == 200, listing.text
    rows = listing.json()["items"]
    assert "customer" not in {row["role"] for row in rows}
    assert "+998901234567" not in {row["phone"] for row in rows}
    assert ADMIN_PHONE in {row["phone"] for row in rows}

    # The same admin, through the old door, arrives with the shoppers.
    everybody = client.get(
        f"{API}/admin/users", params={"page_size": 100}, headers=admin
    )
    assert "customer" in {row["role"] for row in everybody.json()["items"]}

    # Asking for customers here is asking the wrong screen, and gets nothing
    # rather than the whole shop.
    none = client.get(f"{API}/admin/staff", params={"role": "customer"}, headers=admin)
    assert none.json()["items"] == []

    # One job at a time, and the sign-in the office is really looking for:
    # the admin signed in to make this request, so their row says so.
    benches = client.get(
        f"{API}/admin/staff", params={"role": "warehouse"}, headers=admin
    ).json()["items"]
    assert benches and {row["role"] for row in benches} == {"warehouse"}
    us = [row for row in rows if row["phone"] == ADMIN_PHONE][0]
    assert us["last_seen"] is not None


def test_appointing_a_number_nobody_has_seen_makes_the_account(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Hired on Monday, handed the app on Tuesday.

    Until this endpoint an account came into existence only when somebody
    signed in, so a new courier had to sign in as a customer before anybody
    could make them a courier — and the way round it was a shell script on the
    server, which wrote no audit row at all.

    The number is typed the way it is said out loud and normalised by the same
    validator the OTP screen uses, because two spellings of one number are two
    accounts and the one they sign in to is the empty one.
    """
    made = client.post(
        f"{API}/admin/staff",
        json={
            "phone": "901110061",
            "full_name": "Sanjar Qodirov",
            "role": "courier",
            "note": "dushanbadan boshlaydi",
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["phone"] == "+998901110061"
    assert body["role"] == "courier"
    assert body["full_name"] == "Sanjar Qodirov"
    # Nobody has signed in to it yet, and the field says so rather than
    # guessing at the moment the row was written.
    assert body["last_seen"] is None

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.entity == "user", AuditLog.entity_id == body["id"]
            )
        ).all()
    assert [row.action for row in logged] == ["user.create"]
    assert logged[0].new_value == "courier"
    assert logged[0].note == "dushanbadan boshlaydi"

    # And on Tuesday they sign in like anybody else, into their own panel.
    theirs = sign_in("+998901110061")
    mine = client.get(f"{API}/me/staff", headers=theirs)
    assert mine.status_code == 200, mine.text
    assert mine.json()["role"] == "courier"

    seen = client.get(
        f"{API}/admin/staff", params={"q": "1110061"}, headers=admin
    ).json()["items"]
    assert len(seen) == 1
    assert seen[0]["last_seen"] is not None


def test_appointing_a_customer_promotes_them_and_keeps_their_id(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """A person who works here is allowed to have shopped here.

    Same row, same id: their orders, their addresses and their basket are
    theirs and stay theirs. A second account would split one person in two and
    leave the half with the history on it unreachable from the staff screen.

    The name only fills a blank. What is on a used account is what its owner
    typed into the app, and an admin working from a list of phone numbers is
    the worse of the two sources.
    """
    phone = "+998901110062"
    theirs = sign_in(phone)
    _address(client, theirs)
    with Session(engine) as session:
        before = session.exec(select(User).where(User.phone == phone)).one()
        was, had_a_name = before.id, before.full_name
    assert had_a_name == ""

    made = client.post(
        f"{API}/admin/staff",
        json={"phone": phone, "full_name": "Dilnoza Rasulova", "role": "seller"},
        headers=admin,
    )
    assert made.status_code == 201, made.text
    assert made.json()["id"] == was
    assert made.json()["role"] == "seller"
    assert made.json()["full_name"] == "Dilnoza Rasulova"
    # They have signed in, so the directory knows when.
    assert made.json()["last_seen"] is not None

    # Everything they had is still theirs.
    kept = client.get(f"{API}/addresses", headers=theirs)
    assert len(kept.json()) == 1

    # Recorded as a change of role, because that is what happened — there was
    # no account to create.
    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.entity == "user", AuditLog.entity_id == was
            )
        ).all()
    assert [row.action for row in logged] == ["user.role"]
    assert (logged[0].old_value, logged[0].new_value) == ("customer", "seller")

    # And they have left the customer list, which is the other half of the
    # owner's complaint.
    shoppers = client.get(
        f"{API}/admin/customers", params={"q": "1110062"}, headers=admin
    )
    assert shoppers.json()["items"] == []


def test_appointing_somebody_who_already_works_here_is_refused(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Because the form was filled in by somebody adding a person.

    If that number is already the warehouse manager, the answer they need is
    "that is the warehouse manager" — not a warehouse manager who is now a
    courier, which is what a quiet re-assignment would leave behind.
    """
    refused = client.post(
        f"{API}/admin/staff",
        json={"phone": "+998900009002", "full_name": "Kimdir", "role": "courier"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    assert "warehouse" in refused.json()["detail"]

    # And `customer` is not a job, so it is not an appointment.
    nonsense = client.post(
        f"{API}/admin/staff",
        json={"phone": "+998901110063", "role": "customer"},
        headers=admin,
    )
    assert nonsense.status_code == 400, nonsense.text
    with Session(engine) as session:
        assert (
            session.exec(
                select(User).where(User.phone == "+998901110063")
            ).first()
            is None
        )


def test_switching_an_account_off_shuts_the_door_behind_them(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Somebody left, and the office had no way of saying so.

    ``is_active`` had been on the row since the first migration and exactly
    one thing wrote it — a customer deleting their own account — so a courier
    who stopped turning up kept a working token and an opening panel.

    Not a delete: they stay in the directory, marked inactive, with the last
    day they worked still on the row. That is the question asked of a staff
    list more often than any other.
    """
    phone = "+998901110064"
    theirs = sign_in(phone)
    appointed = client.post(
        f"{API}/admin/staff",
        json={"phone": phone, "full_name": "Bekzod Yo'ldoshev", "role": "courier"},
        headers=admin,
    )
    assert appointed.status_code == 201, appointed.text
    user_id = appointed.json()["id"]
    assert client.get(f"{API}/me/staff", headers=theirs).status_code == 200

    off = client.post(
        f"{API}/admin/users/{user_id}/active",
        json={"active": False, "note": "ishdan bo'shadi"},
        headers=admin,
    )
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False
    # The token they were carrying stops working on the next request.
    assert client.get(f"{API}/me/staff", headers=theirs).status_code == 401

    gone = client.get(
        f"{API}/admin/staff", params={"active": False, "q": "1110064"}, headers=admin
    ).json()["items"]
    assert [row["id"] for row in gone] == [user_id]
    assert gone[0]["last_seen"] is not None
    still_here = client.get(
        f"{API}/admin/staff", params={"active": True, "q": "1110064"}, headers=admin
    ).json()["items"]
    assert still_here == []

    with Session(engine) as session:
        logged = session.exec(
            select(AuditLog).where(
                AuditLog.entity_id == user_id, AuditLog.action == "user.active"
            )
        ).one()
    assert (logged.old_value, logged.new_value) == ("true", "false")
    assert logged.note == "ishdan bo'shadi"

    back = client.post(
        f"{API}/admin/users/{user_id}/active", json={"active": True}, headers=admin
    )
    assert back.status_code == 200, back.text
    assert back.json()["is_active"] is True


def test_an_admin_corrects_a_name_and_the_correction_is_logged(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Two fields, and every other one is somebody else's.

    A name taken down wrong over the telephone is the office's to fix. The
    role is not — it has its own door with the last-admin rule on it — and
    neither are the language, the notification switches or the PIN, which is
    why sending a role here changes nothing.
    """
    phone = "+998901110065"
    sign_in(phone)
    with Session(engine) as session:
        user_id = session.exec(select(User).where(User.phone == phone)).one().id

    fixed = client.patch(
        f"{API}/admin/users/{user_id}",
        json={
            "full_name": "Nodira Yusupova",
            "email": "nodira@minibozor.uz",
            "role": "admin",
        },
        headers=admin,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["full_name"] == "Nodira Yusupova"
    assert fixed.json()["email"] == "nodira@minibozor.uz"
    # The role rode along in the body and was ignored.
    assert fixed.json()["role"] == "customer"

    # Saving the form again, unchanged, writes nothing: the log is a list of
    # changes, not of times somebody had the screen open.
    again = client.patch(
        f"{API}/admin/users/{user_id}",
        json={"full_name": "Nodira Yusupova", "email": "nodira@minibozor.uz"},
        headers=admin,
    )
    assert again.status_code == 200, again.text

    trail = client.get(
        f"{API}/admin/audit",
        params={"entity": "user", "entity_id": user_id, "action": "user.profile"},
        headers=admin,
    ).json()
    assert trail["total"] == 2
    assert {row["field"] for row in trail["items"]} == {"full_name", "email"}


def test_a_customers_page_is_their_own_orders_and_nobody_elses(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The screen somebody opens with a telephone in their hand.

    Six endpoints existed for the customer's own app to answer these questions
    and none of them for the office, so what the shop knew about a caller was
    whatever the owner remembered. One request now, because the alternative is
    six fired off while the caller waits through all of them.

    ``spent`` is delivered orders only: a placed order is a promise and a
    cancelled one is nothing, so counting either would put the keenest
    tyre-kicker at the top of the list.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-CALLER", stock=6)
    mine = sign_in("+998901110066")
    theirs = sign_in("+998901110067")

    my_order = _order(client, mine, card["id"], ids["Qora / 42"])
    their_order = _order(client, theirs, card["id"], ids["Oq / 42"])
    _to_the_door(client, admin, my_order["id"])

    # Left in the basket and never checked out — the commonest telephone call
    # there is.
    left = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Oq / 42"], "quantity": 2},
        headers=mine,
    )
    assert left.status_code == 201, left.text
    assert client.put(f"{API}/favorites/{card['id']}", headers=mine).status_code == 200

    with Session(engine) as session:
        my_id = session.exec(
            select(User).where(User.phone == "+998901110066")
        ).one().id

    page = client.get(f"{API}/admin/customers/{my_id}", headers=admin)
    assert page.status_code == 200, page.text
    body = page.json()
    assert [row["code"] for row in body["orders"]] == [my_order["code"]]
    assert their_order["code"] not in [row["code"] for row in body["orders"]]
    assert body["orders_count"] == 1
    assert body["spent"] == my_order["total"]
    assert body["last_order_at"] is not None
    assert body["last_seen"] is not None
    assert body["favorites_count"] == 1
    assert len(body["addresses"]) == 1
    assert [line["quantity"] for line in body["cart"]] == [2]

    # The card is described the way its owner recognises it and no further:
    # the processor's token is the only part that can be charged.
    assert body["cards"][0]["last4"] == "9012"
    assert "processor_token" not in body["cards"][0]

    # The other customer's money is not on this page.
    assert body["spent"] != my_order["total"] + their_order["total"]

    # The list carries the same figures without a query per row.
    listed = client.get(
        f"{API}/admin/customers",
        params={"q": "1110066", "ordering": "spend"},
        headers=admin,
    ).json()["items"]
    assert len(listed) == 1
    assert (listed[0]["orders_count"], listed[0]["spent"]) == (1, my_order["total"])

    # A colleague is not a customer, and guessing their id does not open
    # their page.
    with Session(engine) as session:
        colleague = session.exec(
            select(User).where(User.role == UserRole.WAREHOUSE)
        ).first().id
    assert client.get(
        f"{API}/admin/customers/{colleague}", headers=admin
    ).status_code == 404


def test_the_audit_endpoint_reads_back_the_change_that_was_just_made(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Thirty-eight places wrote this table and nothing read it.

    So the one question it exists to answer — who changed this, and when —
    could only be answered with a database client on the server, which is the
    same as not being able to answer it.

    The actor arrives as a person rather than an id, joined on here so the
    screen does not have to, and ``action`` matches on a prefix so a family
    can be asked for as one thing.
    """
    phone = "+998901110068"
    sign_in(phone)
    with Session(engine) as session:
        user_id = session.exec(select(User).where(User.phone == phone)).one().id

    changed = client.patch(
        f"{API}/admin/users/{user_id}/role",
        json={"role": "warehouse", "note": "kuzgi mavsumga"},
        headers=admin,
    )
    assert changed.status_code == 200, changed.text

    trail = client.get(
        f"{API}/admin/audit",
        params={"entity": "user", "entity_id": user_id},
        headers=admin,
    )
    assert trail.status_code == 200, trail.text
    rows = trail.json()["items"]
    assert [row["action"] for row in rows] == ["user.role"]
    row = rows[0]
    assert (row["old_value"], row["new_value"]) == ("customer", "warehouse")
    assert row["note"] == "kuzgi mavsumga"
    assert row["actor_phone"] == ADMIN_PHONE
    assert row["actor_name"] == "Mini Bozor administratori"
    assert row["actor_role"] == "admin"

    # The whole family of account actions, asked for as one word.
    family = client.get(
        f"{API}/admin/audit",
        params={"action": "user", "entity_id": user_id},
        headers=admin,
    )
    assert family.json()["total"] == 1

    # A filter that matches nothing answers with nothing, not with everything.
    silent = client.get(
        f"{API}/admin/audit",
        params={"action": "product.price", "entity_id": user_id},
        headers=admin,
    )
    assert silent.json()["items"] == []

    # And the note is findable by the words somebody remembers typing.
    found = client.get(
        f"{API}/admin/audit", params={"q": "kuzgi mavsumga"}, headers=admin
    )
    assert user_id in [item["entity_id"] for item in found.json()["items"]]


def test_the_people_screens_are_the_owners_alone(
    client: TestClient, auth: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A directory of colleagues, a customer's saved cards and a log of every
    change made in the building are not tools for doing the work.

    So the wider backoffice guard is wrong for all of them, including for the
    warehouse — who can already read the order queue, and whose 403 here is
    the point rather than an oversight.
    """
    doors = (
        ("get", "/admin/staff", None),
        ("get", "/admin/customers", None),
        ("get", "/admin/customers/1", None),
        ("get", "/admin/audit", None),
        ("post", "/admin/staff", {"phone": "+998901110069", "role": "courier"}),
        ("patch", "/admin/users/1", {"full_name": "Kimdir"}),
        ("post", "/admin/users/1/active", {"active": False}),
    )
    for headers in (auth, warehouse):
        for method, path, body in doors:
            call = getattr(client, method)
            sent = call(f"{API}{path}", json=body, headers=headers) if body else call(
                f"{API}{path}", headers=headers
            )
            assert sent.status_code == 403, f"{method} {path}: {sent.text}"

    # And signed out entirely it is a 401, which is a different sentence.
    assert client.get(f"{API}/admin/staff").status_code == 401
    with Session(engine) as session:
        assert (
            session.exec(select(User).where(User.phone == "+998901110069")).first()
            is None
        )


def test_the_seller_that_is_left_is_a_shop_assistant(
    client: TestClient, admin: dict[str, str]
) -> None:
    """There is a `seller` role again, and it is not the one that went away.

    The one that went was an outside merchant: their own stock, their own
    prices, their own payout, and a cabinet to run it from. What is here now is
    somebody who works in this shop and whose job is the window — the catalogue
    photographs, the words, the price, the switch that puts a card on sale.

    The test that this file used to hold asserted the *word* was gone, which
    was the wrong thing to hold: what must stay gone is the machinery.
    """
    assert {r.value for r in UserRole} == {
        "customer",
        "admin",
        "warehouse",
        "seller",
        "courier",
    }
    # The role is assignable, unlike the marketplace one.
    given = client.patch(
        f"{API}/admin/users/1/role", json={"role": "seller"}, headers=admin
    )
    assert given.status_code in (200, 404), given.text

    # And none of what the old one needed came back with it.
    paths = client.get("/openapi.json").json()["paths"]
    for gone in ("offer", "payout", "settlement", "statement", "tariff"):
        assert not [path for path in paths if gone in path], gone


# --------------------------------------------------------------------------- the customer


def test_the_profile_overview_counts_what_is_left_of_it(
    client: TestClient, sign_in: Callable[[str], dict[str, str]]
) -> None:
    """The card tile counts cards again.

    It answered a hard nought for a while, because the vault had gone and the
    shipped apps would crash on a missing key — so the profile kept a row that
    said "0" and led nowhere. Now it counts, and the row has somewhere to go.

    Its own customer: the suite shares one database and the demo shopper picks
    up a card from every card order in it.
    """
    shopper = sign_in("+998900007007")
    overview = client.get(f"{API}/me/overview", headers=shopper)
    assert overview.status_code == 200, overview.text
    assert overview.json()["cards_count"] == 0

    _payment_card(client, shopper, last4="9012")
    assert client.get(f"{API}/me/overview", headers=shopper).json()["cards_count"] == 1


def test_an_address_is_written_and_read_back(
    client: TestClient, auth: dict[str, str]
) -> None:
    address_id = _address(client, auth)
    mine = client.get(f"{API}/addresses", headers=auth).json()
    assert address_id in [a["id"] for a in mine]


def test_the_languages_the_apps_may_ask_for(client: TestClient) -> None:
    langs = {row["code"] for row in client.get(f"{API}/languages").json()}
    assert langs == {"uz", "ru", "en"}


# ------------------------------------------------- a pile, booked in and shelved


def _pile(
    client: TestClient,
    warehouse: dict[str, str],
    *,
    kind: str = "Krossovka",
    brand: str = "",
    colour: str = "Qora",
    sizes: tuple[tuple[str, int], ...] = (("42", 4),),
    unit_cost: int = 200_000,
    code: str = "",
    placements: tuple[tuple[str, int], ...] = (),
    product_id: int | None = None,
    snapshot: str = "",
    key: str | None = None,
):
    """One pile off the van, the way the receiving desk books one in."""
    body: dict = {
        "kind": kind,
        "brand": brand,
        "colour": colour,
        "sizes": [{"size": size, "quantity": qty} for size, qty in sizes],
        "unit_cost": unit_cost,
        "location_code": code,
        "place": "Chorsu",
    }
    if placements:
        body["placements"] = [
            {"code": cell, "quantity": qty} for cell, qty in placements
        ]
    if product_id is not None:
        body["product_id"] = product_id
    if snapshot:
        body["snapshot_url"] = snapshot
    return client.post(
        f"{API}/warehouse/piles",
        json=body,
        headers={**warehouse, "Idempotency-Key": key or f"pile-{uuid4()}"},
    )


def test_a_pile_goes_straight_to_the_cell_that_was_typed(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Receipt and putaway in one action, and one leg in the ledger.

    The person who opened the sack is standing at the shelf holding the goods.
    Booking them into the receiving area and then carrying them out of it again
    would put a journey in the ledger that nobody made.
    """
    made = _pile(client, warehouse, colour="Qora", sizes=(("42", 4),), code="A-01-01")
    assert made.status_code == 201, made.text
    pile = made.json()
    assert pile["location_code"] == "A-01-01"
    assert pile["quantity"] == 4

    cell = client.get(f"{API}/warehouse/locations/A-01-01", headers=warehouse)
    assert cell.status_code == 200, cell.text
    assert sum(row["qty"] for row in cell.json()["contents"]) >= 4

    variant_id = pile["labels"][0]["variant_id"]
    moves = client.get(
        f"{API}/warehouse/stock/movements",
        params={"variant_id": variant_id},
        headers=warehouse,
    )
    kinds = [row["kind"] for row in moves.json()["items"]]
    assert kinds == ["receipt"], kinds


def test_a_pile_too_big_for_one_cell_is_split_across_several(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Seventy pairs, three cells, one action — and the sizes straddle them.

    A cell holds sixty and the sack held seventy, so the desk was booking the
    pile in three times: three market runs for one sack, three receipts, and
    a unit cost typed three times. The cells are filled in the order they are
    given, the first to its stated quantity and then the next, and a size
    that runs over the end of one cell carries into the next — which is what
    physically happens, and the movements are per size and cell anyway.
    """
    made = _pile(
        client,
        warehouse,
        kind="Krossovka",
        colour="Ko'k",
        sizes=(("41", 30), ("42", 30), ("43", 10)),
        placements=(("A-03-01", 25), ("A-03-02", 25), ("A-03-03", 20)),
    )
    assert made.status_code == 201, made.text
    pile = made.json()
    assert pile["quantity"] == 70
    # One receipt, one run, one unit cost.
    assert pile["total_cost"] == 70 * 200_000
    # The old field still prints, now as every cell it went into.
    assert pile["location_code"] == "A-03-01, A-03-02, A-03-03"
    assert pile["placements"] == [
        {"code": "A-03-01", "quantity": 25},
        {"code": "A-03-02", "quantity": 25},
        {"code": "A-03-03", "quantity": 20},
    ]

    ids = {row["variant_label"]: row["variant_id"] for row in pile["labels"]}
    assert _in("A-03-01", ids["Ko'k / 41"]) == 25
    assert _in("A-03-02", ids["Ko'k / 41"]) == 5      # the size straddles two
    assert _in("A-03-02", ids["Ko'k / 42"]) == 20
    assert _in("A-03-03", ids["Ko'k / 42"]) == 10
    assert _in("A-03-03", ids["Ko'k / 43"]) == 10

    # Every cell holds exactly what the split said it would.
    for code, units in (("A-03-01", 25), ("A-03-02", 25), ("A-03-03", 20)):
        cell = client.get(f"{API}/warehouse/locations/{code}", headers=warehouse)
        assert cell.json()["units"] == units

    # And the ledger adds up to the pile: two legs for the size that
    # straddled, one for each of the others, and no journey nobody made.
    moves = client.get(
        f"{API}/warehouse/stock/movements",
        params={"variant_id": ids["Ko'k / 41"]},
        headers=warehouse,
    ).json()
    assert [row["kind"] for row in moves["items"]] == ["receipt", "receipt"]
    assert sum(row["quantity"] for row in moves["items"]) == 30
    assert {row["to_code"] for row in moves["items"]} == {"A-03-01", "A-03-02"}
    _assert_the_room_adds_up()


def test_a_split_that_does_not_add_up_to_the_pile_is_refused(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The sizes are what came off the van; the cells are where it went.

    A disagreement between the two is somebody having mistyped one of them,
    and there is no way to tell which — so neither is guessed at, and the
    sentence says both numbers rather than leaving a person to recount a
    sack to find out what the system thinks.
    """
    refused = _pile(
        client,
        warehouse,
        kind="Krossovka",
        colour="Moviy",
        sizes=(("41", 10), ("42", 10)),
        placements=(("A-03-04", 12), ("B-01-03", 4)),
    )
    assert refused.status_code == 400, refused.text
    detail = refused.json()["detail"]
    assert "16" in detail and "20" in detail

    # Nothing was written: not the goods, and not a stub card for a pile that
    # never arrived — the cells are checked before a card is made.
    empty = client.get(f"{API}/warehouse/locations/A-03-04", headers=warehouse)
    assert empty.json()["units"] == 0
    words = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert "Moviy" not in words["colours"]


def test_the_putaway_plan_fills_the_models_own_cell_first_and_then_spills(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Where forty pairs go, answered once instead of worked out by eye.

    `suggest-cell` offers one code and says nothing about room, so somebody
    holding a sack got a cell with space for ten and a shelf map on another
    screen. The plan is the same judgement with the quantity in the question:
    the model's own cell first, filled to what is actually left in it, then
    the emptiest cells nearest it.
    """
    made = _pile(
        client,
        warehouse,
        kind="Ko'ylak",
        colour="Binafsha",
        sizes=(("M", 50),),
        code="B-02-03",
    )
    assert made.status_code == 201, made.text
    card = made.json()["product"]["id"]

    plan = client.get(
        f"{API}/warehouse/putaway-plan",
        params={"product_id": card, "quantity": 25},
        headers=warehouse,
    )
    assert plan.status_code == 200, plan.text
    body = plan.json()

    first = body["lines"][0]
    assert first["code"] == "B-02-03"
    assert first["holds_this_model"] is True
    assert first["units"] == 50
    assert first["free"] == 10
    assert first["quantity"] == 10          # what is left in it, not all 25
    assert len(body["lines"]) > 1           # the rest spills

    # Everything after the model's own cell is somewhere else, and no line is
    # asked to hold more than it has room for.
    assert all(not line["holds_this_model"] for line in body["lines"][1:])
    assert all(line["quantity"] <= line["free"] for line in body["lines"][1:])
    assert sum(line["quantity"] for line in body["lines"]) == 25
    assert body["over_capacity"] is False
    assert body["message"] == ""

    # A van the building cannot hold is still a plan. The goods are standing
    # on the floor, so the last cell takes the remainder and the answer says
    # so — a plan that stopped short would not say where the rest went.
    too_much = client.get(
        f"{API}/warehouse/putaway-plan",
        params={"product_id": card, "quantity": 100_000},
        headers=warehouse,
    ).json()
    assert too_much["over_capacity"] is True
    assert too_much["message"]
    assert sum(line["quantity"] for line in too_much["lines"]) == 100_000

    # Nothing was written by any of it.
    assert _in("B-02-03", made.json()["labels"][0]["variant_id"]) == 50


def test_a_pile_is_a_stub_and_the_shop_cannot_see_it(
    client: TestClient, warehouse: dict[str, str], admin: dict[str, str]
) -> None:
    """Three gaps, all named, and no way past them.

    A card written with the sack open has a name, a colour and a count. It has
    no category, so nobody browsing would find it; no price, so there is
    nothing to charge; and no catalogue photograph, so it would show as a grey
    square. Being invisible for another hour is the better of the two.
    """
    made = _pile(client, warehouse, kind="Futbolka", colour="Oq", code="A-01-02")
    card = made.json()["product"]
    assert card["status"] == "draft"
    assert card["category_slug"] is None
    assert card["price"] == 0
    assert {gap["key"] for gap in card["unready"]} == {
        "needs_category",
        "needs_price",
        "needs_photo",
    }

    refused = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text


def test_the_bench_books_goods_in_and_the_seller_puts_them_on_sale(
    client: TestClient, warehouse: dict[str, str], seller: dict[str, str]
) -> None:
    """Two jobs, two people, and the boundary is where it should be.

    The bench's business with a card ends when the goods are on a shelf: it
    writes the stub, and it may not price the goods or put them in the shop.
    The window is the seller's — the category, the price, the photographs, and
    the switch.
    """
    made = _pile(client, warehouse, kind="Shim", colour="Ko'k", code="A-01-03")
    card = made.json()["product"]

    # Not the bench's to price.
    refused = client.post(
        f"{API}/admin/products/{card['id']}/price",
        json={"price": 149_000},
        headers=warehouse,
    )
    assert refused.status_code == 403, refused.text

    # The seller files it — including writing the category, because the first
    # card ever written has nowhere to go.
    _category(client, seller, "shimlar")
    filed = client.patch(
        f"{API}/admin/products/{card['id']}",
        json={"category_slug": "shimlar"},
        headers=seller,
    )
    assert filed.status_code == 200, filed.text

    priced = client.post(
        f"{API}/admin/products/{card['id']}/price",
        json={"price": 149_000},
        headers=seller,
    )
    assert priced.status_code == 200, priced.text
    assert all(row["price"] == 149_000 for row in priced.json())

    _photograph(client, seller, card["id"], "Ko'k")

    live = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=seller,
    )
    assert live.status_code == 200, live.text
    assert live.json()["unready"] == []
    assert live.json()["price"] == 149_000

    # And a card already on sale does not offer to go on sale again. The
    # publishing screen draws that button from this field rather than from the
    # status, because guessing produced a button that asked the server to move
    # a card from active to active and was refused.
    assert "active" not in live.json()["next_statuses"]
    again = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=seller,
    )
    assert again.status_code == 409, again.text


def test_the_words_and_the_table_the_phone_renders(
    client: TestClient, warehouse: dict[str, str], seller: dict[str, str]
) -> None:
    """A card that reads like a shop rather than like a receipt.

    The apps hide a block whose field is empty, so a thin card looks sparse
    rather than broken — which is exactly why nobody notices it needs
    finishing. `listing_gaps` is the to-do list, and it is not a gate: none of
    this stops the card going on sale.
    """
    made = _pile(client, warehouse, kind="Kostyum", colour="Kulrang", code="A-04-02")
    card = made.json()["product"]
    assert {gap["key"] for gap in card["listing_gaps"]} == {
        "needs_subtitle",
        "needs_description",
        "needs_specs",
        "needs_more_photos",
    }

    written = client.patch(
        f"{API}/admin/products/{card['id']}",
        json={
            "title": "Erkaklar kostyumi Alfa",
            "subtitle": "Kulrang, ikki qismli",
            "description": "Yengil mato, kunlik kiyim uchun.",
        },
        headers=seller,
    )
    assert written.status_code == 200, written.text

    # The specification table had a schema and no door: the cabinet that used
    # to call it went with the sellers, and the phone has been rendering an
    # empty block ever since.
    specs = client.put(
        f"{API}/admin/products/{card['id']}/specs",
        json={"specs": [{"key": "Mato", "value": "Paxta"}, {"key": "Fason", "value": "Klassik"}]},
        headers=seller,
    )
    assert specs.status_code == 200, specs.text
    assert [row["key"] for row in specs.json()] == ["Mato", "Fason"]

    _photograph(client, seller, card["id"], "Kulrang")
    _photograph(client, seller, card["id"], "Kulrang")

    left = client.get(f"{API}/admin/products/{card['id']}", headers=seller)
    assert left.status_code == 200, left.text
    assert left.json()["listing_gaps"] == []


def test_a_second_pile_of_the_same_size_adds_to_the_first(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Four found, then two more found — six, not two.

    The screen this replaced overwrote the earlier line instead of adding to
    it, silently, so a size counted twice ended up holding whatever was
    counted last. Every count here is a difference written to the ledger, which
    is the only shape that cannot lose the first one.
    """
    first = _pile(
        client, warehouse, kind="Kepka", colour="Qora", sizes=(("L", 4),), code="A-02-01"
    )
    assert first.status_code == 201, first.text
    card = first.json()["product"]

    again = _pile(
        client,
        warehouse,
        product_id=card["id"],
        colour="Qora",
        sizes=(("L", 2),),
        code="A-02-01",
    )
    assert again.status_code == 201, again.text

    variant_id = first.json()["labels"][0]["variant_id"]
    assert again.json()["labels"][0]["variant_id"] == variant_id

    cell = client.get(f"{API}/warehouse/locations/A-02-01", headers=warehouse)
    held = {row["variant_id"]: row["qty"] for row in cell.json()["contents"]}
    assert held[variant_id] == 6


def test_a_mistyped_cell_is_refused_rather_than_invented(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """``A-03-11`` is one keystroke from ``A-03-01`` and there is no scanner yet."""
    refused = _pile(client, warehouse, colour="Qora", code="A-03-11")
    assert refused.status_code == 404, refused.text

    not_a_cell = _pile(client, warehouse, colour="Qora", code=loc.QABUL)
    assert not_a_cell.status_code == 409, not_a_cell.text


def test_one_pile_key_books_it_in_once(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A second tap on a slow connection is not a second sack."""
    key = f"pile-{uuid4()}"
    sack = {"kind": "Sumka", "colour": "Qora", "sizes": (("", 7),), "code": "A-02-02"}
    first = _pile(client, warehouse, key=key, **sack)
    assert first.status_code == 201, first.text
    again = _pile(client, warehouse, key=key, **sack)
    assert again.status_code in (200, 201), again.text
    assert again.json()["run_id"] == first.json()["run_id"]

    variant_id = first.json()["labels"][0]["variant_id"]
    cell = client.get(f"{API}/warehouse/locations/A-02-02", headers=warehouse)
    held = {row["variant_id"]: row["qty"] for row in cell.json()["contents"]}
    assert held[variant_id] == 7


def test_the_desk_vocabulary_is_learned_from_what_came_through_the_door(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """No vocabulary screen: a brand typed once is a chip from then on.

    Nobody sets up a list of goods before receiving any, and a market brings
    whatever it brings — so "On Cloud" is written on the form that needed it
    and the chips are the answer to what things have been called.
    """
    made = _pile(
        client,
        warehouse,
        kind="Krossovka",
        brand="On Cloud",
        colour="Oq",
        sizes=(("41", 4), ("42", 6)),
        code="A-04-01",
        snapshot="uploads/oncloud.webp",
    )
    assert made.status_code == 201, made.text
    assert made.json()["product"]["brand_slug"] == "on-cloud"
    assert made.json()["product"]["snapshot_url"] == "uploads/oncloud.webp"

    words = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert "Krossovka" in words["kinds"]
    assert "On Cloud" in words["brands"]
    assert "Oq" in words["colours"]
    # 41 before 42, and offering the right row is three taps instead of twelve.
    assert words["sizes"]["Krossovka"][:2] == ["41", "42"]


def test_two_black_trainers_of_different_makes_are_two_cards(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The make is part of the goods' identity, not a detail.

    A picker sent to a cell of black trainers has to be able to tell which pair
    the order named, and "qora krossovka" twice cannot tell them.
    """
    shoe = {"kind": "Krossovka", "colour": "Qora"}
    nike = _pile(client, warehouse, brand="Nike", code="B-01-01", **shoe)
    adidas = _pile(client, warehouse, brand="Adidas", code="B-01-02", **shoe)
    assert nike.status_code == 201 and adidas.status_code == 201

    assert nike.json()["product"]["id"] != adidas.json()["product"]["id"]
    assert nike.json()["product"]["sku"] != adidas.json()["product"]["sku"]
    assert "Nike" in nike.json()["product"]["title"]
    assert "Adidas" in adidas.json()["product"]["title"]


def test_a_card_with_colours_will_not_take_a_colourless_pile(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Otherwise the count lands on a cell no picker is ever sent to.

    The form picks the colour from the card's own list, and this is the same
    rule underneath it — an empty colour against a card that has some would
    write a colourless variant beside "Oq" and put the goods on the shelf under
    a name nobody looks for.
    """
    first = _pile(client, warehouse, kind="Palto", colour="Oq", code="B-02-01")
    assert first.status_code == 201, first.text
    card = first.json()["product"]

    refused = _pile(client, warehouse, product_id=card["id"], colour="", code="B-02-01")
    assert refused.status_code == 400, refused.text
    assert "Oq" in refused.json()["detail"]


def test_the_desk_keeps_one_spelling_per_thing(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """`nike`, `NIKE` and `Nike` are one chip, not three.

    The vocabulary is learned from what people type, so it also learns their
    typos — and three chips for one brand is worse than no chips, because now
    somebody has to choose between two right answers.
    """
    first = _pile(client, warehouse, kind="sumka", brand="nike", colour="qora", code="C-01-01")
    assert first.status_code == 201, first.text
    assert first.json()["product"]["title"] == "Sumka · Nike · Qora"

    again = _pile(client, warehouse, kind="SUMKA", brand="NIKE", colour="QORA", code="C-01-02")
    assert again.status_code == 201, again.text
    # The same brand row, not a second one spelt louder.
    assert again.json()["product"]["brand_slug"] == first.json()["product"]["brand_slug"]

    words = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert words["brands"].count("Nike") == 1
    assert "NIKE" not in words["brands"] and "nike" not in words["brands"]
    assert "Sumka" in words["kinds"] and "SUMKA" not in words["kinds"]
    assert "Qora" in words["colours"] and "qora" not in words["colours"]


def test_a_brand_written_badly_once_is_tidied_in_place(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Otherwise the chip reads `Nike` and the card it writes reads `nike`.

    The row keeps lending its spelling to every card titled from it, so the
    catalogue disagrees with the form that wrote it. Tidied on the way past.
    """
    sloppy = _pile(client, warehouse, kind="Kurtka", brand="adidas", colour="Qora", code="C-02-01")
    assert sloppy.status_code == 201, sloppy.text
    assert sloppy.json()["product"]["title"] == "Kurtka · Adidas · Qora"

    # The chip now offers `Adidas`; tapping it must land on the same row and
    # title the next card the same way.
    words = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert "Adidas" in words["brands"]

    again = _pile(client, warehouse, kind="Kurtka", brand="Adidas", colour="Oq", code="C-02-02")
    assert again.json()["product"]["title"] == "Kurtka · Adidas · Oq"
    assert again.json()["product"]["brand_slug"] == sloppy.json()["product"]["brand_slug"]


def _brands(client: TestClient, admin: dict[str, str]) -> dict[str, dict]:
    """The brand list, by slug — with its count and the spellings it holds."""
    got = client.get(f"{API}/admin/brands", headers=admin)
    assert got.status_code == 200, got.text
    return {row["slug"]: row for row in got.json()}


def test_two_spellings_of_one_make_are_merged_into_one_row(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The cards move, one row is left, and the merge says how many moved.

    The desk types the make, so a mistyped one is a permanent brand: "On
    Cloud" and "On Clod" are two makes as far as the catalogue's filters and
    the brand index are concerned. Deleting the wrong one was refused while
    any card carried it, and nothing repointed a card's brand in bulk — so
    joining them meant opening every card by hand.
    """
    # The suite books "On Cloud" in elsewhere too, so what is checked is the
    # change rather than the total: one card moved across, none lost.
    before = _brands(client, admin).get("on-cloud", {}).get("product_count", 0)
    right = _pile(
        client, warehouse, kind="Krossovka", brand="On Cloud", colour="Oq",
        code="B-01-04",
    )
    wrong = _pile(
        client, warehouse, kind="Krossovka", brand="On Clod", colour="Qora",
        code="B-01-04",
    )
    assert right.status_code == 201 and wrong.status_code == 201
    assert right.json()["product"]["brand_slug"] == "on-cloud"
    assert wrong.json()["product"]["brand_slug"] == "on-clod"

    merged = client.post(
        f"{API}/admin/brands/on-clod/merge",
        json={"into": "on-cloud"},
        headers=admin,
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()
    assert body["brand"]["slug"] == "on-cloud"
    assert body["products_moved"] == 1
    # The loser's spelling comes with it, which is what stops the duplicate
    # being made again at the desk.
    assert "On Clod" in body["aliases"] and "On Cloud" in body["aliases"]

    rows = _brands(client, admin)
    assert "on-clod" not in rows
    assert rows["on-cloud"]["product_count"] == before + 2

    # The card that was on the loser now reads as the make it always was, and
    # the chip row offers one spelling rather than two.
    card = client.get(
        f"{API}/admin/products/{wrong.json()['product']['id']}", headers=admin
    ).json()
    assert card["brand_slug"] == "on-cloud"
    words = client.get(f"{API}/warehouse/vocab", headers=warehouse).json()
    assert "On Cloud" in words["brands"] and "On Clod" not in words["brands"]


def test_the_spelling_that_made_the_duplicate_stops_making_one(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A merge that did not keep the loser's words would last until the next van.

    The desk matches on what somebody types. Fold "Nayki" into "Nike", leave
    the word behind, and the very next sack typed the old way writes the row
    straight back — the tidying is undone by the receipt it was done for.
    """
    _pile(client, warehouse, kind="Shim", brand="Nayki", colour="Qora", code="B-02-04")
    _pile(client, warehouse, kind="Shim", brand="Nike", colour="Oq", code="B-02-04")
    merged = client.post(
        f"{API}/admin/brands/nayki/merge", json={"into": "nike"}, headers=admin
    )
    assert merged.status_code == 200, merged.text

    again = _pile(
        client, warehouse, kind="Shim", brand="Nayki", colour="Kulrang",
        code="B-02-04",
    )
    assert again.status_code == 201, again.text
    assert again.json()["product"]["brand_slug"] == "nike"
    assert "nayki" not in _brands(client, admin)


def test_a_brands_slug_is_corrected_and_the_old_name_goes_on_working(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The slug used to be read off the payload and then ignored.

    So a slug generated from a misspelling was permanent — it is in the
    catalogue's filter URLs and on every brand link. And because the desk
    matched on the *name*, correcting the name detached the row from every
    sack that would be typed the old way, which wrote the duplicate back.
    Both halves are fixed here: the slug changes, and the old spelling still
    lands on the same row.
    """
    made = _pile(
        client, warehouse, kind="Sviter", brand="Rebok", colour="Qora",
        code="B-01-04",
    )
    assert made.json()["product"]["brand_slug"] == "rebok"

    fixed = client.patch(
        f"{API}/admin/brands/rebok",
        json={"slug": "reebok", "name": "Reebok"},
        headers=admin,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["slug"] == "reebok"
    assert fixed.json()["name"] == "Reebok"

    rows = _brands(client, admin)
    assert "rebok" not in rows
    assert set(rows["reebok"]["aliases"]) >= {"Rebok", "Reebok"}

    typed_the_old_way = _pile(
        client, warehouse, kind="Sviter", brand="Rebok", colour="Oq",
        code="B-01-04",
    )
    assert typed_the_old_way.json()["product"]["brand_slug"] == "reebok"


def test_a_brand_cannot_be_merged_into_itself(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Which of the two would be left? The endpoint deletes one of its arguments."""
    _pile(client, warehouse, kind="Kepka", brand="Puma", colour="Qora", code="B-02-04")
    silly = client.post(
        f"{API}/admin/brands/puma/merge", json={"into": "puma"}, headers=admin
    )
    assert silly.status_code == 409, silly.text
    assert "puma" in _brands(client, admin)


def test_merging_brands_is_the_owners_alone(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The desk writes brands because it has to; joining two is not that.

    A merge deletes a row and moves other people's cards onto another one, on
    a form that is being filled in with a sack open at nine in the evening.
    """
    _pile(client, warehouse, kind="Kurtka", brand="Asiks", colour="Qora", code="B-02-04")
    _pile(client, warehouse, kind="Kurtka", brand="Asics", colour="Oq", code="B-02-04")

    refused = client.post(
        f"{API}/admin/brands/asiks/merge", json={"into": "asics"}, headers=warehouse
    )
    assert refused.status_code == 403, refused.text
    assert "asiks" in _brands(client, admin)


def test_a_brand_name_another_row_already_answers_to_is_refused(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Two rows called the same thing is the state all of this is getting out of.

    The desk can only land on one of them, so the other collects no cards and
    the customer is offered two filters for one make. The refusal names the
    row that holds the spelling, because merging is what the admin was about
    to do by hand.
    """
    _pile(client, warehouse, kind="Palto", brand="Zara", colour="Qora", code="B-01-04")
    _pile(client, warehouse, kind="Palto", brand="Mango", colour="Oq", code="B-01-04")

    clash = client.patch(
        f"{API}/admin/brands/mango",
        json={"slug": "mango", "name": "ZARA"},
        headers=admin,
    )
    assert clash.status_code == 409, clash.text
    assert "zara" in clash.json()["detail"]
    assert _brands(client, admin)["mango"]["name"] == "Mango"


def test_the_card_search_matches_every_word_in_any_order(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """"krossovka nike" has to find "Krossovka · Nike · Qora".

    A single LIKE on the whole phrase does not: the separators sit between the
    words. And this is precisely the search somebody types while checking
    whether a card exists before writing a second one for the same goods.
    """
    made = _pile(client, warehouse, kind="Botinka", brand="Nike", colour="Qora", code="C-03-01")
    assert made.status_code == 201, made.text

    for query in ("botinka nike", "nike botinka", "qora botinka"):
        found = client.get(
            f"{API}/admin/products", params={"q": query}, headers=warehouse
        )
        assert found.status_code == 200, found.text
        titles = [row["title"] for row in found.json()["items"]]
        assert "Botinka · Nike · Qora" in titles, f"{query!r} found {titles}"


def test_a_colour_with_no_photograph_is_not_in_the_shop(
    client: TestClient,
    warehouse: dict[str, str],
    seller: dict[str, str],
    admin: dict[str, str],
) -> None:
    """Goods keep arriving after a card has gone on sale.

    A pile of red shirts booked in against a live card adds a colour nobody has
    photographed. Taking the whole card down for it would hide the black ones,
    which are perfectly sellable; leaving the colour in the shop puts a grey
    square with a hex swatch behind it in front of a customer. So the colour
    waits and the card does not.
    """
    made = _pile(
        client, warehouse, kind="Ko'ylak", colour="Qora",
        sizes=(("M", 4),), code="C-04-01",
    )
    card = made.json()["product"]

    _category(client, seller, "koylaklar")
    client.patch(
        f"{API}/admin/products/{card['id']}",
        json={"category_slug": "koylaklar"},
        headers=seller,
    )
    client.post(
        f"{API}/admin/products/{card['id']}/price", json={"price": 99_000}, headers=seller
    )
    _photograph(client, seller, card["id"], "Qora")
    live = client.post(
        f"{API}/admin/products/{card['id']}/status",
        json={"status": "active"},
        headers=seller,
    )
    assert live.status_code == 200, live.text

    # The red ones turn up a week later.
    again = _pile(
        client,
        warehouse,
        product_id=card["id"],
        colour="Qizil",
        sizes=(("M", 3),),
        code="C-04-02",
    )
    assert again.status_code == 201, again.text

    shown = client.get(f"{API}/products/{card['id']}").json()
    assert [c["colour"] for c in shown["colours"]] == ["Qora"]
    assert {v["colour"] for v in shown["variants"]} == {"Qora"}

    # And the card is still on sale, with the queue asking for the picture.
    held = client.get(f"{API}/admin/products/{card['id']}", headers=seller).json()
    assert held["status"] == "active"
    assert "needs_photo" in {gap["key"] for gap in held["unready"]}

    # Photograph it and the red ones appear.
    _photograph(client, seller, card["id"], "Qizil")
    both = client.get(f"{API}/products/{card['id']}").json()
    assert {c["colour"] for c in both["colours"]} == {"Qora", "Qizil"}


def test_a_basket_line_never_shows_another_colour(
    client: TestClient,
    auth: dict[str, str],
    warehouse: dict[str, str],
    seller: dict[str, str],
) -> None:
    """An empty tile is a shrug; the wrong colour is a dispute.

    The line used to fall back to the card's cover, which is a *different*
    colour's photograph — so a black shirt could sit in the basket showing the
    white one, and the customer notices in the order, which is the worst place
    to be surprised.
    """
    made = _pile(client, warehouse, kind="Sviter", colour="Qora", sizes=(("L", 5),), code="C-04-03")
    card = made.json()["product"]
    _photograph(client, seller, card["id"], "Qora")
    variant = made.json()["labels"][0]["variant_id"]

    added = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": variant, "quantity": 1},
        headers=auth,
    )
    assert added.status_code in (200, 201), added.text
    line = next(row for row in added.json()["items"] if row["variant_id"] == variant)
    assert line["colour"] == "Qora"
    assert line["size"] == "L"
    assert line["image_url"], "the colour was photographed, so the line has its picture"

    # A colour with no photograph of its own shows nothing rather than the
    # cover, which belongs to another colour.
    grey = _pile(
        client,
        warehouse,
        product_id=card["id"],
        colour="Kulrang",
        sizes=(("L", 2),),
        code="C-04-04",
    )
    assert grey.status_code == 201, grey.text
    other = grey.json()["labels"][0]["variant_id"]
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": other, "quantity": 1},
        headers=auth,
    )
    line = next(row for row in added.json()["items"] if row["variant_id"] == other)
    assert line["colour"] == "Kulrang"
    assert not line["image_url"]


def test_sizes_read_in_the_order_they_are_worn(
    client: TestClient, warehouse: dict[str, str], seller: dict[str, str]
) -> None:
    """S M L XL XXL, whatever order the goods turned up in.

    The cells are made as the piles arrive, so a shirt that came in M and L and
    then S, XL and XXL was read off the shelf in exactly that order — and a
    customer looking for their size faced a row with no order at all. Shoes
    have the same problem the other way: 100 sorts before 41 lexically.
    """
    first = _pile(
        client, warehouse, kind="Futbolka", colour="Oq",
        sizes=(("M", 2), ("L", 2)), code="C-02-03",
    )
    card = first.json()["product"]
    again = _pile(
        client, warehouse, product_id=card["id"], colour="Oq",
        sizes=(("XXL", 1), ("S", 3), ("XL", 2)), code="C-02-03",
    )
    assert again.status_code == 201, again.text

    grid = client.get(f"{API}/admin/products/{card['id']}/variants", headers=seller)
    assert [row["size"] for row in grid.json()] == ["S", "M", "L", "XL", "XXL"]

    # And numbers as numbers, not as text.
    shoes = _pile(
        client, warehouse, kind="Botinka", colour="Qora",
        sizes=(("41", 1), ("100", 1), ("39", 1)), code="C-02-04",
    )
    grid = client.get(
        f"{API}/admin/products/{shoes.json()['product']['id']}/variants", headers=seller
    )
    assert [row["size"] for row in grid.json()] == ["39", "41", "100"]


def test_a_card_with_no_history_is_deleted_and_one_with_history_is_archived(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The line is history, not status.

    Nothing could remove a card at all, so a duplicate written at the receiving
    desk stayed in the catalogue for ever with `draft` as the only way to hide
    it. A card nothing has happened to is a piece of writing somebody got
    wrong; a card with a movement against it is part of what happened here, and
    deleting that would leave a ledger with a hole in it.
    """
    _category(client, admin, "sumkalar")
    written = _card(client, admin, sku="ALFA-TYPO-1", category="sumkalar")
    gone = client.delete(f"{API}/admin/products/{written['id']}", headers=admin)
    assert gone.status_code == 200, gone.text
    assert client.get(
        f"{API}/admin/products/{written['id']}", headers=admin
    ).status_code == 404

    booked = _pile(client, warehouse, kind="Sumka", colour="Qora", code="C-03-02")
    card = booked.json()["product"]
    kept = client.delete(f"{API}/admin/products/{card['id']}", headers=admin)
    assert kept.status_code == 200, kept.text
    after = client.get(f"{API}/admin/products/{card['id']}", headers=admin)
    assert after.status_code == 200
    assert after.json()["status"] == "archived"


def test_emptying_a_cell_writes_the_goods_off_rather_than_forgetting_them(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A room being cleared is still a room with a ledger.

    Deleting the placements would be quicker and would leave the ledger
    disagreeing with the shelf for ever with nothing to explain it. So every
    line leaves the building the way any other line does, with the reason on
    it, and the invariant holds afterwards.
    """
    booked = _pile(
        client, warehouse, kind="Ro'mol", colour="Oq", sizes=(("", 7),), code="C-03-03"
    )
    leaf = booked.json()["labels"][0]["variant_id"]
    assert _in("C-03-03", leaf) == 7

    emptied = client.post(
        f"{API}/warehouse/stock/empty",
        json={"code": "C-03-03", "reason": "sanoqda topilmadi"},
        headers=admin,
    )
    assert emptied.status_code == 200, emptied.text
    assert emptied.json() == {"moved": 1, "units": 7, "cells": 1}
    assert _in("C-03-03", leaf) == 0
    _assert_the_room_adds_up()

    moves = client.get(
        f"{API}/warehouse/stock/movements",
        params={"variant_id": leaf, "kind": "write_off"},
        headers=warehouse,
    )
    assert moves.json()["total"] == 1
    assert moves.json()["items"][0]["reason"] == "sanoqda topilmadi"


def test_only_the_office_may_empty_the_room(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The bench moves goods; it does not decide they stopped existing."""
    refused = client.post(
        f"{API}/warehouse/stock/empty",
        json={"reason": "hammasini tozalash"},
        headers=warehouse,
    )
    assert refused.status_code == 403, refused.text


# ------------------------------------------------------- how the business is doing

# `/hisobotlar` used to be one paged table of raw stock movements: no dates, no
# totals, not a single so'm. The tests below are about the three ways the
# replacement could quietly lie — claiming a margin it cannot know, counting a
# cancelled order as takings, and comparing this period against a period of a
# different length.


def _report(client: TestClient, admin: dict[str, str], name: str, **params) -> dict:
    answer = client.get(f"{API}/admin/reports/{name}", params=params, headers=admin)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _headline(report: dict, key: str) -> dict:
    found = [row for row in report["headlines"] if row["key"] == key]
    assert found, f"no headline called {key} in {[r['key'] for r in report['headlines']]}"
    return found[0]


def test_a_cell_remembers_what_its_newest_lot_cost(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The cost lands on the cell, and the newest run wins.

    Per cell and not per card: a 43 is bought at a different price from a 41,
    and `products.last_cost` — which answers the whole card — would have made
    the margin on one of them the margin of the other.
    """
    booked = _pile(
        client,
        warehouse,
        kind="Shippak",
        colour="Sariq",
        sizes=(("40", 3), ("41", 3)),
        unit_cost=120_000,
        code="A-01-02",
    )
    assert booked.status_code == 201, booked.text
    leaf = booked.json()["labels"][0]["variant_id"]
    with Session(engine) as session:
        product_id = session.get(ProductVariant, leaf).product_id
        cells = {
            variant.size: variant.id
            for variant in session.exec(
                select(ProductVariant).where(ProductVariant.product_id == product_id)
            ).all()
        }
        assert session.get(ProductVariant, cells["40"]).last_cost == 120_000
        assert session.get(ProductVariant, cells["41"]).last_cost == 120_000

    # A second run of the same size, dearer. The cell's cost moves; the other
    # size is untouched, which is the whole reason this is on the variant.
    again = _pile(
        client,
        warehouse,
        kind="Shippak",
        colour="Sariq",
        sizes=(("40", 2),),
        unit_cost=155_000,
        code="A-01-02",
        product_id=product_id,
    )
    assert again.status_code == 201, again.text
    with Session(engine) as session:
        assert session.get(ProductVariant, cells["40"]).last_cost == 155_000
        assert session.get(ProductVariant, cells["41"]).last_cost == 120_000


def test_margin_is_claimed_only_for_what_the_shop_knows_it_paid_for(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A line with no cost is uncosted, never free.

    Every order placed before `order_items.unit_cost` existed carries a nought,
    and reading that as a cost of zero would print a hundred per cent margin
    over the shop's whole history. So the sums are over costed lines alone and
    the coverage is reported beside them — here, one of the two units sold is
    stripped of its cost to stand for the past, and the margin must not move
    while the coverage must.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="ALFA-MARGIN", stock=4, price=900_000
    )
    leaf = ids["Qora / 42"]

    before = _report(client, admin, "money")["margin"]

    order = _order(client, auth, card["id"], leaf, quantity=2)
    _to_the_door(client, admin, order["id"])

    after = _report(client, admin, "money")["margin"]
    # Two units at 900 000 sold, bought at 200 000 by `_book_in`.
    assert after["revenue"] - before["revenue"] == 1_800_000
    assert after["cost"] - before["cost"] == 400_000
    assert after["margin"] - before["margin"] == 1_400_000
    assert after["units_costed"] - before["units_costed"] == 2
    assert after["known_from"] is not None

    # Now the past: one order line loses its cost, the way every line written
    # before the column existed has none.
    second = _order(client, auth, card["id"], leaf, quantity=1)
    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == second["id"])
        ).one()
        assert line.unit_cost == 200_000, "checkout froze the cost"
        line.unit_cost = 0
        session.add(line)
        session.commit()
    _to_the_door(client, admin, second["id"])

    blind = _report(client, admin, "money")["margin"]
    # The uncosted unit adds nothing to either side of the margin...
    assert blind["revenue"] == after["revenue"]
    assert blind["cost"] == after["cost"]
    assert blind["margin"] == after["margin"]
    # ...and is counted in the units, so the coverage says what was missed.
    assert blind["units"] - after["units"] == 1
    assert blind["units_costed"] == after["units_costed"]
    assert blind["coverage_percent"] < 10_000


def test_a_cancelled_order_is_not_takings(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Revenue is delivered orders. A cancelled one sold nothing.

    It is also the disagreement the dashboard had with itself: the tile counted
    every row created today and the chart under it excluded cancellations, so
    the two differed by exactly the orders somebody had called off.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="ALFA-VOID", stock=4, price=650_000
    )
    leaf = ids["Qora / 42"]

    before = _report(client, admin, "sales")
    board = client.get(f"{API}/admin/dashboard", headers=admin).json()
    tile = next(t for t in board["tiles"] if t["key"] == "orders_today")
    was_on_the_tile = tile["value"]
    was_on_the_chart = board["sales"][-1]["orders"]
    assert was_on_the_tile == was_on_the_chart, "the tile and the chart disagree"

    order = _order(client, auth, card["id"], leaf)
    off = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason": "Fikrimdan qaytdim"},
        headers=auth,
    )
    assert off.status_code == 200, off.text

    after = _report(client, admin, "sales")
    assert _headline(after, "revenue")["value"] == _headline(before, "revenue")["value"]
    assert _headline(after, "cancelled")["value"] == (
        _headline(before, "cancelled")["value"] + 1
    )

    board = client.get(f"{API}/admin/dashboard", headers=admin).json()
    tile = next(t for t in board["tiles"] if t["key"] == "orders_today")
    assert tile["value"] == was_on_the_tile, "a cancelled order reached the tile"
    assert tile["value"] == board["sales"][-1]["orders"]
    assert tile["previous"] is not None, "the tile arrives with yesterday beside it"


def test_a_customer_calling_off_their_own_order_leaves_a_mark(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Both cancel paths write the same event.

    An operator cancelling stamped a `cancelled` row and a customer pressing
    the button in the app stamped nothing, so the timeline the app draws
    stopped at "placed" for half the cancellations there are — and anything
    counting them off the events saw only the operator's. `orders.updated_at`
    is not the answer: it is the last change of any kind.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="ALFA-MARK", stock=3, price=300_000
    )
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    off = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason": "Boshqa rangini olmoqchiman"},
        headers=auth,
    )
    assert off.status_code == 200, off.text

    timeline = client.get(f"{API}/orders/{order['id']}", headers=auth).json()["events"]
    stamped = [row for row in timeline if row["status"] == "cancelled"]
    assert stamped, "the customer's own cancellation left no event"
    assert stamped[0]["happened_at"] is not None
    assert "Boshqa rangini" in stamped[0]["note"]


def test_the_previous_period_is_the_same_length_and_ends_the_day_before(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Same length, immediately before — not "last month".

    Last month is a different number of days and a different number of
    weekends, and a shop that takes most of its money on a Saturday would be
    shown an arrow that was really about the calendar.
    """
    for name in ("sales", "money", "customers", "products", "stock", "operations"):
        report = _report(
            client, admin, name, from_day="2026-09-08", to_day="2026-09-14"
        )
        span = report["period"]
        assert span["days"] == 7, name
        assert span["previous_to_day"] == "2026-09-07", name
        assert span["previous_from_day"] == "2026-09-01", name
        for row in report["headlines"]:
            # A figure either has its twin or says plainly that it has none.
            assert (row["previous"] is None) == (row["delta"] is None), row


def test_a_report_bucket_is_never_missing_a_quiet_day(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A chart that skips empty days draws a shop that was busy every day."""
    report = _report(
        client, admin, "sales", from_day="2026-08-01", to_day="2026-08-14"
    )
    assert [row["day"] for row in report["buckets"]] == [
        f"2026-08-{day:02d}" for day in range(1, 15)
    ]

    monthly = _report(
        client,
        admin,
        "sales",
        from_day="2026-07-01",
        to_day="2026-09-30",
        bucket="month",
    )
    assert [row["day"] for row in monthly["buckets"]] == [
        "2026-07-01",
        "2026-08-01",
        "2026-09-01",
    ]


def test_the_call_list_leaves_out_somebody_who_never_bought(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Lapsed means bought before and stopped, which a browser has not done.

    The list is a list of telephone calls. Somebody who signed in once and
    never ordered anything is not a lapsed customer, they are a stranger — and
    ringing them off a list headed "we miss you" is how a shop annoys people.
    """
    quiet = sign_in("+998900007701")
    shopper = sign_in("+998900007702")

    card, ids = _on_sale(
        client, admin, warehouse, sku="ALFA-LAPSED", stock=4, price=410_000
    )
    order = _order(client, shopper, card["id"], ids["Qora / 42"])

    with Session(engine) as session:
        row = session.get(Order, order["id"])
        row.created_at = row.created_at - timedelta(days=200)
        session.add(row)
        session.commit()
        never = session.exec(
            select(User).where(User.phone == "+998900007701")
        ).one().id
        bought = session.exec(
            select(User).where(User.phone == "+998900007702")
        ).one().id
    assert quiet["Authorization"], "the quiet one has an account and never used it"

    report = _report(client, admin, "customers", lapsed_after=30)
    called = {row["user_id"] for row in report["lapsed"]}
    assert bought in called, "somebody who bought and stopped is not on the list"
    assert never not in called, "a customer who never bought is on the call list"
    for row in report["lapsed"]:
        assert row["days_since"] > 0


def test_the_stock_value_splits_by_the_kind_of_place_it_stands_in(
    client: TestClient, warehouse: dict[str, str], admin: dict[str, str]
) -> None:
    """"94 million of stock" is a figure nobody can act on.

    "Four million of it is in the damaged corner" is a morning's work. Goods
    that move from one kind of place to another must move between the two rows
    by exactly what they are worth, and nothing may appear or vanish in the
    total.

    The split used to be demonstrated with the receiving desk, because a
    market run booked goods in there and somebody carried them to a cell
    afterwards. A pile goes straight to a shelf, so the pair of rows worth
    watching is the racks and the corner by the door — which is the split that
    pays for the whole panel anyway.
    """
    def value_of(kind: str) -> int:
        report = _report(client, admin, "stock")
        rows = {row["kind"]: row["value"] for row in report["by_kind"]}
        return rows.get(kind, 0)

    card = _card(client, admin, sku="ALFA-SPLIT", price=250_000)
    ids = _variants(client, admin, card["id"], ["Jigarrang"], ["M"], price=250_000)
    leaf = ids["Jigarrang / M"]

    was_bin = value_of("bin")
    _book_in(client, warehouse, [(leaf, 6)])
    assert value_of("bin") == was_bin + 6 * 250_000

    was_bin = value_of("bin")
    was_damaged = value_of("damaged")
    broke = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": leaf, "quantity": 2, "reason": "yomg\'irda qolgan"},
        headers=warehouse,
    )
    assert broke.status_code == 200, broke.text
    assert value_of("damaged") == was_damaged + 2 * 250_000
    assert value_of("bin") == was_bin - 2 * 250_000
    _assert_the_room_adds_up()


def test_the_reports_are_the_owners_alone(
    client: TestClient, warehouse: dict[str, str], seller: dict[str, str]
) -> None:
    """The bench and the shop assistant have their own screens.

    What the shop took, what each customer is worth and what the margin is are
    the owner's business, and there is nobody else here for them to be.
    """
    for headers in (warehouse, seller):
        for name in ("sales", "money", "customers", "products", "stock", "operations"):
            refused = client.get(f"{API}/admin/reports/{name}", headers=headers)
            assert refused.status_code == 403, f"{name}: {refused.text}"


def test_a_period_that_runs_backwards_is_refused(
    client: TestClient, admin: dict[str, str]
) -> None:
    refused = client.get(
        f"{API}/admin/reports/sales",
        params={"from_day": "2026-09-10", "to_day": "2026-09-01"},
        headers=admin,
    )
    assert refused.status_code == 400, refused.text
