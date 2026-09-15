"""The receiving flow in its two moments — §2 of docs/RECEIVING_REBUILD.md.

The walk this file makes is the owner's own sentence: *bring the goods, type
how many, get that many stickers, stick them on, carry them to the shelf,
scan the cell*. Enter → paper → stick → carry → put away. The cell is the
**last** thing said, at the shelf, because it is the one thing nobody could
know before they walked — and between the two moments the goods stand in
QABUL, which is a real, sellable place and not a limbo.

Everything here goes through the same two doors the screen uses: ``POST
/warehouse/receipts`` at the bench and ``POST /warehouse/receipts/{id}/shelve``
at the shelf. The invariants are the suite's usual ones, borrowed from
``test_api``: a placement equals its own movements, and a variant's shelf
figure equals the sum of its placements.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import locations as loc
from app.db import engine
from app.models import StockMovement, Supply, SupplyStatus
from tests.test_api import (
    API,
    _assert_the_room_adds_up,
    _in,
    _sellable,
    _shelf,
)


def _receive(
    client: TestClient,
    warehouse: dict[str, str],
    *,
    kind: str = "Oyoq kiyim",
    brand: str = "",
    colour: str = "Oq",
    sizes: tuple[tuple[str, int], ...] = (("43", 10), ("42", 10)),
    unit_cost: int = 120_000,
    product_id: int | None = None,
    place: str = "Chorsu",
    transport_cost: int = 0,
    key: str | None = None,
):
    """Moment one, exactly as the bench sends it: no cell anywhere on it."""
    body: dict = {
        "kind": kind,
        "brand": brand,
        "colour": colour,
        "sizes": [{"size": size, "quantity": qty} for size, qty in sizes],
        "unit_cost": unit_cost,
        "place": place,
        "transport_cost": transport_cost,
    }
    if product_id is not None:
        body["product_id"] = product_id
    return client.post(
        f"{API}/warehouse/receipts",
        json=body,
        headers={**warehouse, "Idempotency-Key": key or f"receipt-{uuid4()}"},
    )


def _shelve(
    client: TestClient,
    warehouse: dict[str, str],
    receipt_id: int,
    code: str,
    *,
    key: str | None = None,
):
    """Moment two: the cell, said at the shelf."""
    return client.post(
        f"{API}/warehouse/receipts/{receipt_id}/shelve",
        json={"location_code": code},
        headers={**warehouse, "Idempotency-Key": key or f"shelve-{uuid4()}"},
    )


# --------------------------------------------------------------------- the walk


def test_twenty_white_shoes_from_the_bench_to_the_shelf(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """§7 steps 1–4, the backend half: one call, twenty stickers, one scan.

    No cell is asked for at the bench. The receipt answers with everything
    the sticker sheet needs — one line per size, in the typed order, each
    with its count — and the goods stand in QABUL, sellable, until the cell's
    own label is scanned at the shelf.
    """
    made = _receive(
        client,
        warehouse,
        kind="Oyoq kiyim",
        brand="Nike",
        colour="Oq",
        sizes=(("43", 10), ("42", 10)),
        unit_cost=120_000,
        transport_cost=40_000,
    )
    assert made.status_code == 201, made.text
    receipt = made.json()

    # Twenty stickers: ten saying 43, then ten saying 42 — the typed order,
    # matching the piles on the table.
    assert receipt["quantity"] == 20
    assert [row["size"] for row in receipt["labels"]] == ["43", "42"]
    assert [row["copies"] for row in receipt["labels"]] == [10, 10]
    assert all(row["colour"] == "Oq" for row in receipt["labels"])
    assert all(row["barcode"] and row["sku"] for row in receipt["labels"])
    assert receipt["total_cost"] == 20 * 120_000 + 40_000

    # The goods exist, in the receiving area, and can already be sold from it.
    ids = {row["size"]: row["variant_id"] for row in receipt["labels"]}
    assert _in(loc.QABUL, ids["43"]) == 10
    assert _in(loc.QABUL, ids["42"]) == 10
    assert _sellable(ids["43"]) == 10
    _assert_the_room_adds_up()

    # The supply row was written by the receipt, already received, with the
    # cost on it — the market run, never edited by hand.
    with Session(engine) as session:
        run = session.get(Supply, receipt["run_id"])
        assert run.status is SupplyStatus.RECEIVED
        assert run.transport_cost == 40_000

    # One scan at the shelf and the goods move — all of them, both sizes.
    shelved = _shelve(client, warehouse, receipt["run_id"], "B-01-02")
    assert shelved.status_code == 200, shelved.text
    assert shelved.json()["quantity"] == 20
    assert shelved.json()["location_code"] == "B-01-02"
    assert shelved.json()["total_cost"] == 20 * 120_000 + 40_000

    assert _in(loc.QABUL, ids["43"]) == 0
    assert _in("B-01-02", ids["43"]) == 10
    assert _in("B-01-02", ids["42"]) == 10
    assert _shelf(ids["43"]) == 10
    _assert_the_room_adds_up()

    # The shelf map shows them in that cell — the link the screen follows.
    cell = client.get(f"{API}/warehouse/locations/B-01-02", headers=warehouse)
    assert cell.status_code == 200, cell.text
    held = {row["variant_id"]: row["qty"] for row in cell.json()["contents"]}
    assert held[ids["43"]] == 10 and held[ids["42"]] == 10


def test_the_black_ones_are_a_second_receipt_on_the_same_card(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """§7 step 7a: only the colour and the sizes are retyped.

    One receipt is one colour, so white and black arrive as two receipts —
    and the second names the card the first wrote, keeping the kind, the
    brand and the identity. The white variants' barcodes do not move: a
    barcode is permanent, and a second code for one thing is a shelf holding
    it twice.
    """
    white = _receive(
        client, warehouse, kind="Oyoq kiyim", brand="Adidas", colour="Oq",
        sizes=(("41", 5),),
    )
    assert white.status_code == 201, white.text
    card = white.json()["product"]
    white_barcode = white.json()["labels"][0]["barcode"]

    black = _receive(
        client,
        warehouse,
        product_id=card["id"],
        colour="Qora",
        sizes=(("41", 3), ("42", 3)),
    )
    assert black.status_code == 201, black.text
    assert black.json()["product"]["id"] == card["id"]
    assert all(row["colour"] == "Qora" for row in black.json()["labels"])

    # New cells for the new colour, and the old colour's codes untouched.
    barcodes = {row["barcode"] for row in black.json()["labels"]}
    assert white_barcode not in barcodes
    again = _receive(
        client, warehouse, product_id=card["id"], colour="Oq", sizes=(("41", 2),)
    )
    assert again.json()["labels"][0]["barcode"] == white_barcode
    _assert_the_room_adds_up()


def test_a_second_receipt_of_the_same_variant_adds_up(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Four booked in, then two more — six, on one variant, in one cell."""
    first = _receive(
        client, warehouse, kind="Kepka", colour="Sariq", sizes=(("", 4),)
    )
    assert first.status_code == 201, first.text
    card = first.json()["product"]
    leaf = first.json()["labels"][0]["variant_id"]
    assert _shelve(client, warehouse, first.json()["run_id"], "C-02-01").status_code == 200
    _assert_the_room_adds_up()

    second = _receive(
        client, warehouse, product_id=card["id"], colour="Sariq", sizes=(("", 2),)
    )
    assert second.status_code == 201, second.text
    assert second.json()["labels"][0]["variant_id"] == leaf
    assert _in(loc.QABUL, leaf) == 2
    assert _in("C-02-01", leaf) == 4

    done = _shelve(client, warehouse, second.json()["run_id"], "C-02-01")
    assert done.status_code == 200, done.text
    assert done.json()["quantity"] == 2
    assert _in("C-02-01", leaf) == 6
    assert _shelf(leaf) == 6
    _assert_the_room_adds_up()


# ------------------------------------------------------------------ both doors


def test_the_receipt_is_idempotent(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A second tap on a slow connection is not a second van."""
    key = f"receipt-{uuid4()}"
    first = _receive(
        client, warehouse, kind="Sharf", colour="Qizil", sizes=(("", 7),), key=key
    )
    assert first.status_code == 201, first.text
    again = _receive(
        client, warehouse, kind="Sharf", colour="Qizil", sizes=(("", 7),), key=key
    )
    assert again.status_code in (200, 201), again.text
    assert again.json()["run_id"] == first.json()["run_id"]

    leaf = first.json()["labels"][0]["variant_id"]
    assert _in(loc.QABUL, leaf) == 7      # once, not twice
    _assert_the_room_adds_up()


def test_the_shelve_is_idempotent_and_a_second_asks_nothing_more(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The retry replays; a receipt already shelved is answered politely."""
    made = _receive(
        client, warehouse, kind="Qalpoq", colour="Yashil", sizes=(("", 5),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    key = f"shelve-{uuid4()}"
    first = _shelve(client, warehouse, receipt_id, "C-02-02", key=key)
    assert first.status_code == 200, first.text
    assert first.json()["quantity"] == 5

    replayed = _shelve(client, warehouse, receipt_id, "C-02-02", key=key)
    assert replayed.json() == first.json()
    assert _in("C-02-02", leaf) == 5      # carried once

    fresh = _shelve(client, warehouse, receipt_id, "C-02-03")
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["quantity"] == 0
    assert fresh.json()["message"]
    assert _in("C-02-03", leaf) == 0
    _assert_the_room_adds_up()


def test_a_mistyped_cell_is_refused_at_the_shelf_not_invented(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """``B-99-99`` is a typo, not a place — and the goods stay where they are."""
    made = _receive(
        client, warehouse, kind="Kamar", colour="Jigarrang", sizes=(("", 3),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    typo = _shelve(client, warehouse, receipt_id, "B-99-99")
    assert typo.status_code == 404, typo.text
    assert "B-99-99" in typo.json()["detail"]

    desk = _shelve(client, warehouse, receipt_id, loc.QABUL)
    assert desk.status_code == 409, desk.text     # a staging area is not a shelf

    assert _in(loc.QABUL, leaf) == 3
    _assert_the_room_adds_up()


# ------------------------------------------------------- the queue and the tile


def test_the_unanswered_question_waits_on_the_queue_and_the_dashboard(
    client: TestClient, warehouse: dict[str, str], admin: dict[str, str]
) -> None:
    """§7 step 5: close the screen, reload, and the question is still there.

    A receipt whose cell was never scanned is not lost — its goods stand in
    QABUL — but somebody has to be reminded to walk. The queue on ``/qabul``
    restores the second moment after a reload, and the dashboard counts the
    same receipts under "Yorliqlangan, javonga qo'yilmagan" with the oldest
    age on it.
    """
    made = _receive(
        client, warehouse, kind="Sumka", colour="Binafsha", sizes=(("", 4),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]

    queue = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    assert queue.status_code == 200, queue.text
    mine = next(row for row in queue.json() if row["id"] == receipt_id)
    assert mine["quantity"] == 4
    assert mine["age_minutes"] >= 0
    assert mine["product_id"] == made.json()["product"]["id"]
    assert mine["product_title"]

    board = client.get(f"{API}/admin/dashboard", headers=admin)
    assert board.status_code == 200, board.text
    tiles = {tile["key"]: tile for tile in board.json()["tiles"]}
    tile = tiles["labelled_unshelved"]
    assert tile["value"] >= 1
    assert tile["href"] == "/qabul"
    assert tile["label"] == "Yorliqlangan, javonga qo'yilmagan"

    # Shelve it and the queue lets it go.
    assert _shelve(client, warehouse, receipt_id, "C-02-04").status_code == 200
    left = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    assert receipt_id not in [row["id"] for row in left.json()]
    _assert_the_room_adds_up()


def test_goods_sold_straight_from_the_receiving_area_are_not_shelved_twice(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """QABUL is sellable, so a receipt can shrink before it is shelved.

    Two of the five leave through a pick or a damage before anybody walks to
    the shelf. The shelve door carries what is actually standing, not what
    the receipt once said — carrying the receipt's number would move goods
    that are no longer there.
    """
    made = _receive(
        client, warehouse, kind="Ro'mol", colour="Pushti", sizes=(("", 5),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    # Two are damaged at the bench — they leave QABUL for the corner.
    broken = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": leaf, "quantity": 2, "reason": "yirtilgan chiqdi"},
        headers=warehouse,
    )
    assert broken.status_code == 200, broken.text
    assert _in(loc.QABUL, leaf) == 3

    shelved = _shelve(client, warehouse, receipt_id, "C-03-01")
    assert shelved.status_code == 200, shelved.text
    assert shelved.json()["quantity"] == 3
    assert _in("C-03-01", leaf) == 3
    assert _in(loc.QABUL, leaf) == 0
    _assert_the_room_adds_up()

    # And the queue does not keep a ghost of the two that left another way.
    queue = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    assert receipt_id not in [row["id"] for row in queue.json()]


def test_the_ledger_reads_the_two_moments_back(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Receipt into QABUL, putaway into the cell — the journey, per leg."""
    made = _receive(
        client, warehouse, kind="Futbolka", colour="Kulrang", sizes=(("M", 6),)
    )
    assert made.status_code == 201, made.text
    leaf = made.json()["labels"][0]["variant_id"]
    assert _shelve(client, warehouse, made.json()["run_id"], "C-03-02").status_code == 200

    with Session(engine) as session:
        legs = session.exec(
            select(StockMovement)
            .where(StockMovement.variant_id == leaf)
            .order_by(StockMovement.id)
        ).all()
    assert [leg.kind.value for leg in legs] == ["receipt", "putaway"]
    # Both legs name the run, which is what ties the queue, the reprint and
    # the cost to one receipt.
    assert {leg.supply_id for leg in legs} == {made.json()["run_id"]}
    _assert_the_room_adds_up()


def test_a_deleted_card_does_not_poison_the_next_sku(
    client: TestClient, warehouse: dict[str, str], admin: dict[str, str]
) -> None:
    """Create, delete, create again — the third card gets a fresh code.

    `next_sku` used to be count+1, which collides the moment anything has ever
    been deleted: the count shrinks, the deleted card's code stays used for
    ever, and the bench — which never types a SKU — gets "Bu SKU allaqachon
    ishlatilgan" on every new card until somebody works out why. Found live,
    on a database where cleanup had deleted two walked-through cards.
    """
    def open_card(title: str) -> dict:
        made = client.post(
            f"{API}/admin/products",
            json={"sku": "", "title": title, "kind": "Shapka", "price": 0},
            headers=warehouse,
        )
        assert made.status_code == 201, made.text
        return made.json()

    first = open_card("Shapka birinchi")
    second = open_card("Shapka ikkinchi")
    assert first["sku"] != second["sku"]

    # Take the FIRST one out, so the count drops below the highest number —
    # deleting the newest would hide the defect.
    gone = client.delete(f"{API}/admin/products/{first['id']}", headers=admin)
    assert gone.status_code == 200, gone.text

    third = open_card("Shapka uchinchi")
    assert third["sku"] not in (first["sku"], second["sku"])

    # And the receiving door mints its stubs through the same generator.
    receipt = _receive(
        client, warehouse, kind="Shapka to'rtinchi", colour="Qora",
        sizes=(("58", 3),), key="sku-after-delete",
    )
    assert receipt.status_code == 201, receipt.text
