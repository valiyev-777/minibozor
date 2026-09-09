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

from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import locations as loc
from app import stock as st
from app.db import engine
from app.models import (
    AuditLog,
    Location,
    LocationKind,
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
        f"{API}/warehouse/supplies",
        json={"sacks": 1, "place": place, "transport_cost": 30_000},
        headers=warehouse,
    )
    assert started.status_code == 201, started.text
    run = started.json()[0]

    sorted_ = client.put(
        f"{API}/warehouse/supplies/{run['id']}/lines",
        json={
            "lines": [
                {"variant_id": variant_id, "quantity": qty, "unit_cost": unit_cost}
                for variant_id, qty in lines
            ]
        },
        headers=warehouse,
    )
    assert sorted_.status_code == 200, sorted_.text

    closed = client.post(f"{API}/warehouse/supplies/{run['id']}/receive", headers=warehouse)
    assert closed.status_code == 200, closed.text
    return closed.json()


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
) -> dict:
    """Carry a quantity from the receiving area to a cell."""
    done = client.post(
        f"{API}/warehouse/putaway",
        json={"variant_id": variant_id, "qty": qty, "code": code},
        headers={**warehouse, "Idempotency-Key": f"putaway-{variant_id}-{code}-{qty}"},
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

    The endpoint that does this from a screen arrives with the rest of the
    warehouse doors; the move itself is the model's, and this is what it has
    to do.
    """
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-PUTAWAY", stock=6)
    leaf = ids["Qora / 42"]

    with Session(engine) as session:
        variant = session.get(ProductVariant, leaf)
        st.move(
            session,
            variant=variant,
            qty=4,
            kind=StockMovementKind.PUTAWAY,
            frm=loc.staging(session, loc.QABUL),
            to=loc.by_code(session, "A-02-03"),
            reason="joylashtirildi",
        )
        session.commit()

    assert _in(loc.QABUL, leaf) == 2
    assert _in("A-02-03", leaf) == 4
    # Carrying goods across the room changes where they are and not how many
    # there are.
    assert _shelf(leaf) == 6
    assert _sellable(leaf) == 6
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
            kind=StockMovementKind.PUTAWAY,
            frm=loc.staging(session, loc.QABUL),
            to=loc.by_code(session, "A-01-01"),
        )
        session.commit()

    order = _order(client, auth, card["id"], leaf, quantity=6)
    _to_the_door(client, admin, order["id"])

    assert _shelf(leaf) == 0
    assert _in("A-01-01", leaf) == 0
    assert _in(loc.QABUL, leaf) == 0
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
            frm=loc.staging(session, loc.QABUL),
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


def test_sorting_replaces_the_lines_rather_than_adding_to_them(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-SORT")
    ids = _variants(client, admin, card["id"], ["Qora"], ["42", "43"])
    run = client.post(f"{API}/warehouse/supplies", json={"sacks": 1}, headers=warehouse).json()[0]

    first = client.put(
        f"{API}/warehouse/supplies/{run['id']}/lines",
        json={"lines": [{"variant_id": ids["Qora / 42"], "quantity": 4, "unit_cost": 100}]},
        headers=warehouse,
    )
    assert len(first.json()["lines"]) == 1

    second = client.put(
        f"{API}/warehouse/supplies/{run['id']}/lines",
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
    run = client.post(f"{API}/warehouse/supplies", json={"sacks": 1}, headers=warehouse).json()[0]
    refused = client.post(f"{API}/warehouse/supplies/{run['id']}/receive", headers=warehouse)
    assert refused.status_code == 409, refused.text


def test_closing_a_run_is_what_brings_the_goods_into_existence(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card = _card(client, admin, sku="ALFA-CLOSE")
    ids = _variants(client, admin, card["id"], ["Qora"], ["42", "43"])
    closed = _book_in(
        client, warehouse, [(ids["Qora / 42"], 6), (ids["Qora / 43"], 4)]
    )

    assert closed["status"] == "received"
    assert closed["total_cost"] == 10 * 200_000 + 30_000
    assert _shelf(ids["Qora / 42"]) == 6
    assert _ledger(ids["Qora / 42"]) == 6

    # Into the receiving area, not onto a shelf. Somebody carries it to a cell
    # afterwards; until they do, being in QABUL *is* the unplaced state.
    assert _in(loc.QABUL, ids["Qora / 42"]) == 6
    assert _sellable(ids["Qora / 42"]) == 6

    with Session(engine) as session:
        kinds = session.exec(
            select(StockMovement.kind).where(
                StockMovement.variant_id == ids["Qora / 42"]
            )
        ).all()
    assert list(kinds) == [StockMovementKind.RECEIPT]
    _assert_the_room_adds_up()


def test_a_closed_run_is_not_reopened(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Correct it with an adjustment. The ledger keeps what was believed then."""
    card = _card(client, admin, sku="ALFA-ONCE")
    ids = _variants(client, admin, card["id"], ["Qora"], ["42"])
    closed = _book_in(client, warehouse, [(ids["Qora / 42"], 3)])

    again = client.post(f"{API}/warehouse/supplies/{closed['id']}/receive", headers=warehouse)
    assert again.status_code == 409, again.text
    edited = client.put(
        f"{API}/warehouse/supplies/{closed['id']}/lines",
        json={"lines": [{"variant_id": ids["Qora / 42"], "quantity": 99}]},
        headers=warehouse,
    )
    assert edited.status_code == 409, edited.text
    assert _shelf(ids["Qora / 42"]) == 3


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
    assert row["from_code"] == loc.QABUL
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
    # Two colours, five each, all still standing at the receiving desk. The
    # suite shares one room, so this card's ten are a share of the tile rather
    # than the whole of it.
    assert staging[loc.QABUL]["units"] >= 10
    assert staging[loc.QABUL]["oldest_minutes"] >= 0
    assert _in(loc.QABUL, ids["Qora / 42"]) == 5


def test_a_cell_says_how_full_it_is(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-FILL", stock=30)
    _put_away(client, warehouse, ids["Qora / 42"], 30, "B-01-01")

    cell = client.get(f"{API}/warehouse/locations/B-01-01", headers=warehouse).json()
    assert cell["units"] == 30
    assert cell["capacity"] == 60
    assert cell["fill_percent"] == 50
    assert cell["contents"][0]["variant_label"] == "Qora · 42"


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


# --------------------------------------------------------------------------- putaway


def test_the_putaway_queue_is_the_receiving_area_itself(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """No task table: standing in QABUL *is* the state of not being shelved."""
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-QUEUE2", stock=3)

    queue = client.get(f"{API}/warehouse/putaway", headers=warehouse).json()
    lines = {row["variant_id"]: row for row in queue}
    assert lines[ids["Qora / 42"]]["qty"] == 3
    assert lines[ids["Qora / 42"]]["minutes_here"] >= 0
    assert lines[ids["Qora / 42"]]["suggestion"] == ""


def test_putting_goods_away_empties_the_queue_and_fills_a_cell(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-AWAY", stock=6)
    leaf = ids["Qora / 42"]

    cell = _put_away(client, warehouse, leaf, 4, "A-02-03")
    assert cell["code"] == "A-02-03"
    assert cell["units"] >= 4
    assert _in(loc.QABUL, leaf) == 2
    assert _in("A-02-03", leaf) == 4
    assert _sellable(leaf) == 6      # carrying it across the room sells nothing
    _assert_the_room_adds_up()

    # And the next line of the same model is offered the cell it already lives in.
    queue = client.get(f"{API}/warehouse/putaway", headers=warehouse).json()
    mine = next(row for row in queue if row["variant_id"] == leaf)
    assert mine["suggestion"] == "A-02-03"


def test_goods_cannot_be_put_into_a_staging_area(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-BADCELL", stock=2)
    refused = client.post(
        f"{API}/warehouse/putaway",
        json={"variant_id": ids["Qora / 42"], "qty": 1, "code": loc.BRAK},
        headers={**warehouse, "Idempotency-Key": "putaway-brak"},
    )
    assert refused.status_code == 409, refused.text


def test_a_mistyped_cell_is_a_404_and_moves_nothing(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-TYPO", stock=2)
    missing = client.post(
        f"{API}/warehouse/putaway",
        json={"variant_id": ids["Qora / 42"], "qty": 1, "code": "Z-09-09"},
        headers={**warehouse, "Idempotency-Key": "putaway-typo"},
    )
    assert missing.status_code == 404, missing.text
    assert _in(loc.QABUL, ids["Qora / 42"]) == 2
    _assert_the_room_adds_up()


def test_a_retried_putaway_does_not_carry_the_goods_twice(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    card, ids = _on_sale(client, admin, warehouse, sku="ALFA-IDEM", stock=5)
    leaf = ids["Qora / 42"]
    body = {"variant_id": leaf, "qty": 2, "code": "A-01-02"}
    headers = {**warehouse, "Idempotency-Key": "putaway-once"}

    first = client.post(f"{API}/warehouse/putaway", json=body, headers=headers)
    second = client.post(f"{API}/warehouse/putaway", json=body, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert _in("A-01-02", leaf) == 2
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
    assert tiles["awaiting_putaway"]["value"] >= 8
    assert tiles["no_photograph"]["value"] >= 1
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
    assert _in(loc.QABUL, ids["Qora / 42"]) == 1
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
    assert _in(loc.QABUL, leaf) == 5
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
    assert _in(loc.QABUL, ids["Qora / 42"]) == 4
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
    # Back in the building, in the receiving area, and on sale again.
    assert _shelf(leaf) == 5
    assert _in(loc.QABUL, leaf) == 5
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


def test_there_is_no_seller_role_left(client: TestClient, admin: dict[str, str]) -> None:
    assert {r.value for r in UserRole} == {"customer", "admin", "warehouse", "courier"}
    refused = client.patch(
        f"{API}/admin/users/1/role", json={"role": "seller"}, headers=admin
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
