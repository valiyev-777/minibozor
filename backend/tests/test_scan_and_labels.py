"""The 58 mm labels and the one scan door every warehouse screen shares.

Two contracts live here. ``GET /warehouse/labels`` says not only what to print
but **how many times** — every unit gets a sticker, so a receipt's labels
carry the line quantities, grouped in the order the lines were typed. And
``GET /warehouse/scan`` classifies whatever a gun or a camera read: a goods
label, a cell label, or noise — including the two answers ``where-is`` refuses
to give (a cell code, and a variant with nothing on any shelf).

The goods are built through the admin doors, but the market run is written
straight onto the ``supplies`` tables and the ledger via ``st.move``: the
receiving endpoint is being rebuilt in the same wave, and these tests are
about the labels and the scanner, not about that door. The rows written here
are the rows it will write.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import stock as st
from app.db import engine
from app.models import (
    Location,
    ProductVariant,
    StockMovementKind,
    Supply,
    SupplyLine,
    SupplyStatus,
)

API = "/api/v1"


# --------------------------------------------------------------------------- helpers


def _card_with_sizes(
    client: TestClient,
    admin: dict[str, str],
    *,
    sku: str,
    colours: list[str],
    sizes: list[str],
) -> tuple[dict, dict[str, int]]:
    """A card and its grid, through the admin doors — no stock anywhere yet."""
    made = client.post(
        f"{API}/admin/categories",
        json={"slug": "krossovkalar", "name": "Krossovkalar", "icon": "shoe"},
        headers=admin,
    )
    assert made.status_code in (201, 409), made.text

    card = client.post(
        f"{API}/admin/products",
        json={
            "sku": sku,
            "title": f"Krossovka {sku}",
            "category_slug": "krossovkalar",
            "price": 400_000,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text

    grid = client.put(
        f"{API}/admin/products/{card.json()['id']}/variants",
        json={
            "colours": [{"colour": c, "hex": "#0E0F12"} for c in colours],
            "sizes": sizes,
            "price": 400_000,
        },
        headers=admin,
    )
    assert grid.status_code == 200, grid.text
    ids = {f"{row['colour']} / {row['size']}": row["id"] for row in grid.json()}
    return card.json(), ids


def _supply(lines: list[tuple[int, int]], *, unit_cost: int = 200_000) -> int:
    """A market run's rows, written in the order the lines were typed."""
    with Session(engine) as session:
        run = Supply(
            code=f"SUP-TEST-{uuid4().hex[:8].upper()}",
            status=SupplyStatus.RECEIVED,
            place="Chorsu",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        for variant_id, quantity in lines:
            session.add(
                SupplyLine(
                    supply_id=run.id,
                    variant_id=variant_id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                )
            )
        session.commit()
        return run.id


def _stock(variant_id: int, qty: int, code: str) -> None:
    """A receipt straight into the named place, ledger and placements agreeing."""
    with Session(engine) as session:
        variant = session.get(ProductVariant, variant_id)
        place = session.exec(select(Location).where(Location.code == code)).one()
        st.move(
            session,
            variant=variant,
            qty=qty,
            kind=StockMovementKind.RECEIPT,
            frm=None,
            to=place,
            reason="test receipt",
            unit_cost=200_000,
        )
        session.commit()


def _barcode(variant_id: int) -> str:
    with Session(engine) as session:
        return session.get(ProductVariant, variant_id).barcode


def _sku(variant_id: int) -> str:
    with Session(engine) as session:
        return session.get(ProductVariant, variant_id).sku


# --------------------------------------------------------------------------- copies


def test_a_receipts_labels_say_how_many_to_print_in_the_typed_order(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """Twenty shoes are twenty stickers: ten saying 43, then ten saying 42."""
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-COPIES", colours=["Oq"], sizes=["43", "42"]
    )
    run_id = _supply([(ids["Oq / 43"], 10), (ids["Oq / 42"], 10)])

    sheet = client.get(
        f"{API}/warehouse/labels", params={"supply_id": run_id}, headers=warehouse
    )
    assert sheet.status_code == 200, sheet.text
    products = sheet.json()["products"]

    assert [row["size"] for row in products] == ["43", "42"]
    assert [row["copies"] for row in products] == [10, 10]
    assert all(row["colour"] == "Oq" for row in products)
    # The code on the sticker is the row's own, printed ten times — one label
    # per unit is a quantity of pages, never a new identity.
    assert products[0]["barcode"] == _barcode(ids["Oq / 43"])
    assert products[1]["barcode"] == _barcode(ids["Oq / 42"])


def test_two_lines_of_one_variant_come_out_as_one_label_with_summed_copies(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-SUMMED", colours=["Oq"], sizes=["41"]
    )
    run_id = _supply([(ids["Oq / 41"], 7), (ids["Oq / 41"], 3)])

    products = client.get(
        f"{API}/warehouse/labels", params={"supply_id": run_id}, headers=warehouse
    ).json()["products"]
    assert len(products) == 1
    assert products[0]["copies"] == 10


def test_a_reprint_by_variant_id_is_one_copy_each_in_the_asked_order(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """A reprint is a jammed printer, not a second van."""
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-REPRINT", colours=["Qora"], sizes=["42", "43"]
    )
    first, second = ids["Qora / 43"], ids["Qora / 42"]

    products = client.get(
        f"{API}/warehouse/labels",
        params={"variant_id": [first, second]},
        headers=warehouse,
    ).json()["products"]
    assert [row["variant_id"] for row in products] == [first, second]
    assert [row["copies"] for row in products] == [1, 1]


# --------------------------------------------------------------------------- scan


def test_scan_answers_a_barcode_with_the_identity_and_its_places(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-SCAN", colours=["Qora"], sizes=["42"]
    )
    leaf = ids["Qora / 42"]
    _stock(leaf, 4, "A-04-01")

    read = client.get(
        f"{API}/warehouse/scan", params={"code": _barcode(leaf)}, headers=warehouse
    )
    assert read.status_code == 200, read.text
    answer = read.json()
    assert answer["kind"] == "variant"
    assert answer["cell"] is None
    variant = answer["variant"]
    assert variant["variant_id"] == leaf
    assert variant["colour"] == "Qora"
    assert variant["size"] == "42"
    assert variant["barcode"] == _barcode(leaf)
    assert {(place["code"], place["qty"]) for place in variant["places"]} >= {
        ("A-04-01", 4)
    }


def test_scan_answers_a_sku_the_same_way(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-SKUSCAN", colours=["Qora"], sizes=["41"]
    )
    leaf = ids["Qora / 41"]

    answer = client.get(
        f"{API}/warehouse/scan", params={"code": _sku(leaf)}, headers=warehouse
    ).json()
    assert answer["kind"] == "variant"
    assert answer["variant"]["variant_id"] == leaf


def test_scan_answers_a_zero_stock_variant_with_an_empty_places_list(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The receiving desk scans a label *before* the goods are booked in.

    ``where-is`` hides a variant with no placements — its screen lights cells
    up. The scan door must not: an empty ``places`` is the answer, and the
    identity still fills in the card on ``/qabul``.
    """
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-EMPTYSCAN", colours=["Oq"], sizes=["40"]
    )
    leaf = ids["Oq / 40"]
    code = _barcode(leaf)

    answer = client.get(
        f"{API}/warehouse/scan", params={"code": code}, headers=warehouse
    ).json()
    assert answer["kind"] == "variant"
    assert answer["variant"]["variant_id"] == leaf
    assert answer["variant"]["places"] == []

    # And where-is still keeps its silence about the same code, on purpose.
    hidden = client.get(
        f"{API}/warehouse/where-is", params={"q": code}, headers=warehouse
    ).json()
    assert hidden == []


def test_scan_answers_a_cell_code_with_what_stands_in_it(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    _, ids = _card_with_sizes(
        client, admin, sku="ALFA-CELLSCAN", colours=["Qora"], sizes=["44"]
    )
    leaf = ids["Qora / 44"]
    _stock(leaf, 3, "A-04-02")

    # Lower case on purpose: a retyped smudged label must land on the cell.
    read = client.get(
        f"{API}/warehouse/scan", params={"code": "a-04-02"}, headers=warehouse
    )
    assert read.status_code == 200, read.text
    answer = read.json()
    assert answer["kind"] == "cell"
    assert answer["variant"] is None
    assert answer["code"] == "A-04-02"
    cell = answer["cell"]
    assert cell["code"] == "A-04-02"
    assert cell["kind"] == "bin"
    assert {(line["variant_id"], line["qty"]) for line in cell["contents"]} >= {
        (leaf, 3)
    }

    # The staging areas carry labels too, and QABUL's answers as a place.
    staging = client.get(
        f"{API}/warehouse/scan", params={"code": "QABUL"}, headers=warehouse
    ).json()
    assert staging["kind"] == "cell"
    assert staging["cell"]["kind"] == "receiving"


def test_scan_refuses_an_unknown_code_with_a_typed_miss(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A mis-scan is a normal minute of work: 200, ``kind="none"``, loudly."""
    read = client.get(
        f"{API}/warehouse/scan", params={"code": "NIMADIR-000"}, headers=warehouse
    )
    assert read.status_code == 200, read.text
    answer = read.json()
    assert answer["kind"] == "none"
    assert answer["variant"] is None
    assert answer["cell"] is None
    # The code comes back so the screen can name what it is refusing.
    assert answer["code"] == "NIMADIR-000"


def test_scan_is_for_warehouse_eyes_only(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A customer's token opens the shop, not the room."""
    read = client.get(
        f"{API}/warehouse/scan", params={"code": "A-01-01"}, headers=auth
    )
    assert read.status_code == 403, read.text
