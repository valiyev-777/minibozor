"""Unsaying a receipt while its goods are still on the receiving floor.

*"Typed 20, meant 10"* had no path through this system. The goods were in
``QABUL``, the stickers were printed, and the only correction available was
somebody opening the database — which is the answer that makes a warehouse
stop trusting the screen and start keeping a second count on paper.

``POST /warehouse/receipts/{id}/cancel`` is that path, and it is deliberately
narrow: open only while every line of the receipt is still standing, whole and
untouched, in the receiving area. The moment the goods reach a cell, or leave
``QABUL`` by any other door, the way back is a move or a write-off at the
place they actually are — and the refusal has to say which of those it is,
because they send a person to two different parts of the building.

The reversal is written **into** the ledger and never by deleting anything:
one ``receipt_cancel`` per variant, out of ``QABUL`` and out of the building.
So the invariants this suite checks everywhere still hold — a placement equals
its own movements — and the history still says what happened, which is the
point of having one.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import locations as loc
from app.db import engine
from app.models import (
    Product,
    ProductVariant,
    StockMovement,
    Supply,
    SupplyStatus,
)
from tests.test_api import (
    API,
    _assert_the_room_adds_up,
    _in,
    _shelf,
)
from tests.test_receiving import _receive, _shelve


def _cancel(
    client: TestClient,
    warehouse: dict[str, str],
    receipt_id: int,
    *,
    reason: str = "20 deb yozdim, 10 ta keldi",
    key: str | None = None,
):
    """The door, exactly as the bench would press it."""
    return client.post(
        f"{API}/warehouse/receipts/{receipt_id}/cancel",
        json={"reason": reason},
        headers={**warehouse, "Idempotency-Key": key or f"cancel-{uuid4()}"},
    )


def test_twenty_typed_when_ten_came_is_unsaid_at_the_bench(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The whole point of the door, in the owner's own sentence.

    A receipt booked in a minute ago, nothing shelved, nothing sold: the goods
    go back out of the receiving area, the run is marked cancelled, and the
    room still adds up afterwards.
    """
    made = _receive(
        client,
        warehouse,
        kind="Oyoq kiyim",
        brand="Nike",
        colour="Oq",
        sizes=(("43", 10), ("42", 10)),
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    ids = {row["size"]: row["variant_id"] for row in made.json()["labels"]}
    assert _in(loc.QABUL, ids["43"]) == 10

    undone = _cancel(client, warehouse, receipt_id)
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["receipt_id"] == receipt_id
    assert body["quantity"] == 20
    assert body["run_code"] in body["message"]

    # Nothing of it is anywhere: not in the receiving area, not on a shelf,
    # not in the shop's own figure for the variant.
    assert _in(loc.QABUL, ids["43"]) == 0
    assert _in(loc.QABUL, ids["42"]) == 0
    assert _shelf(ids["43"]) == 0
    assert _shelf(ids["42"]) == 0
    _assert_the_room_adds_up()

    with Session(engine) as session:
        run = session.get(Supply, receipt_id)
        assert run.status is SupplyStatus.CANCELLED


def test_the_reversal_is_a_move_out_and_not_a_deleted_row(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Stock is a ledger (§6.1), and a correction is a move like any other.

    Deleting the receipt's movements would leave a stock figure that is right
    and a history with a hole in it, exactly where somebody later has to look.
    So the ledger reads receipt-then-cancel, both naming the run, and the
    cancel is its own kind rather than a write-off: a receipt nobody should
    have written is not twenty pairs of shoes the shop lost.
    """
    made = _receive(
        client, warehouse, kind="Shim", colour="Ko'k", sizes=(("M", 7),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    assert _cancel(client, warehouse, receipt_id).status_code == 200

    with Session(engine) as session:
        legs = session.exec(
            select(StockMovement)
            .where(StockMovement.variant_id == leaf)
            .order_by(StockMovement.id)
        ).all()
        assert [leg.kind.value for leg in legs] == ["receipt", "receipt_cancel"]
        assert {leg.supply_id for leg in legs} == {receipt_id}

        back = legs[-1]
        assert back.qty == 7
        assert back.from_location_id == loc.staging(session, loc.QABUL).id
        # Out of the building, the way a write-off leaves — but said as its
        # own kind, so the loss reports do not read a typo as twenty pairs
        # of shoes gone.
        assert back.to_location_id is None
        assert "20 deb yozdim" in back.reason or made.json()["run_code"] in back.reason

    _assert_the_room_adds_up()


def test_the_cancelled_receipt_leaves_the_queue_and_the_dashboard(
    client: TestClient, warehouse: dict[str, str], admin: dict[str, str]
) -> None:
    """A receipt nobody has to walk for is not on the list of walks.

    The queue and the tile are one figure read twice — ``receipts_waiting``
    feeds both — so if a cancelled run stayed on either it would stay on both,
    and somebody would carry goods to a shelf that no longer exist.
    """
    made = _receive(
        client, warehouse, kind="Sumka", colour="Yashil", sizes=(("", 6),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]

    queue = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    assert receipt_id in [row["id"] for row in queue.json()]
    board = client.get(f"{API}/admin/dashboard", headers=admin).json()
    before = {tile["key"]: tile for tile in board["tiles"]}["labelled_unshelved"]

    assert _cancel(client, warehouse, receipt_id).status_code == 200

    left = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    assert receipt_id not in [row["id"] for row in left.json()]
    after = {
        tile["key"]: tile
        for tile in client.get(f"{API}/admin/dashboard", headers=admin).json()["tiles"]
    }["labelled_unshelved"]
    assert after["value"] == before["value"] - 1
    _assert_the_room_adds_up()


def test_the_queue_row_says_which_colour_arrived(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """One receipt is one colour, so the queue can say which one.

    Two runs of the same card an hour apart are "Oq" and "Qora"; a queue that
    draws both as the card's name is a queue where the wrong row gets shelved
    into the right cell.
    """
    made = _receive(
        client, warehouse, kind="Ko'ylak", colour="Sariq", sizes=(("L", 3),)
    )
    assert made.status_code == 201, made.text
    queue = client.get(f"{API}/warehouse/receipts/waiting", headers=warehouse)
    mine = next(row for row in queue.json() if row["id"] == made.json()["run_id"])
    assert mine["colour"] == "Sariq"
    assert "colour_hex" in mine


def test_a_shelved_receipt_is_refused_and_the_refusal_says_why(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The door closes when the goods reach a cell.

    Taking them back out is a move or a write-off *at that cell*, which is
    where somebody has to walk anyway — so the sentence says that rather than
    "bekor qilib bo'lmaydi", which is the answer that makes a person ring
    whoever wrote the screen.
    """
    made = _receive(
        client, warehouse, kind="Krossovka", colour="Qizil", sizes=(("41", 5),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]
    assert _shelve(client, warehouse, receipt_id, "C-04-01").status_code == 200

    refused = _cancel(client, warehouse, receipt_id)
    assert refused.status_code == 409, refused.text
    said = refused.json()["detail"]
    assert "javonga qo'yilgan" in said
    assert "yacheykadan" in said

    # And nothing moved because of the asking.
    assert _in("C-04-01", leaf) == 5
    with Session(engine) as session:
        assert session.get(Supply, receipt_id).status is SupplyStatus.RECEIVED
    _assert_the_room_adds_up()


def test_a_receipt_partly_gone_from_the_receiving_floor_is_refused(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """QABUL is sellable, so a receipt can shrink before anybody shelves it.

    Two of the five go to the damaged corner. The receipt can no longer be
    said never to have happened — part of what it booked in has moved on — and
    the refusal counts how many, because "some of it is gone" leaves a person
    hunting for which.
    """
    made = _receive(
        client, warehouse, kind="Ro'mol", colour="Oltin", sizes=(("", 5),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    broken = client.post(
        f"{API}/warehouse/stock/damage",
        json={"variant_id": leaf, "quantity": 2, "reason": "yirtilgan chiqdi"},
        headers=warehouse,
    )
    assert broken.status_code == 200, broken.text

    refused = _cancel(client, warehouse, receipt_id)
    assert refused.status_code == 409, refused.text
    assert "2" in refused.json()["detail"]

    assert _in(loc.QABUL, leaf) == 3
    with Session(engine) as session:
        assert session.get(Supply, receipt_id).status is SupplyStatus.RECEIVED
    _assert_the_room_adds_up()


def test_the_cancel_is_idempotent_and_a_second_one_asks_nothing_more(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Rule §6.7, and the politeness the shelve door already shows.

    The same key twice replays the stored answer rather than taking the goods
    out a second time — which, on a door that moves stock, is the difference
    between a correction and a shop that owes itself ten pairs of shoes. A
    *different* key on an already-cancelled run is answered rather than
    refused: it is not a mistake to want what has already happened.
    """
    made = _receive(
        client, warehouse, kind="Kepka", colour="Kulrang", sizes=(("", 4),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]
    leaf = made.json()["labels"][0]["variant_id"]

    key = f"cancel-{uuid4()}"
    first = _cancel(client, warehouse, receipt_id, key=key)
    assert first.status_code == 200, first.text
    again = _cancel(client, warehouse, receipt_id, key=key)
    assert again.status_code == 200, again.text
    assert again.json() == first.json()

    fresh = _cancel(client, warehouse, receipt_id)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["quantity"] == 0
    assert fresh.json()["message"]

    assert _shelf(leaf) == 0
    with Session(engine) as session:
        backs = session.exec(
            select(StockMovement).where(
                StockMovement.variant_id == leaf,
                StockMovement.kind == "RECEIPT_CANCEL",
            )
        ).all()
        assert len(backs) == 1, "the goods came back out exactly once"
    _assert_the_room_adds_up()


def test_the_key_is_required_like_every_other_warehouse_write(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """An optional key is a key some client forgets, silently and expensively."""
    made = _receive(
        client, warehouse, kind="Sharf", colour="Pushti", sizes=(("", 2),)
    )
    assert made.status_code == 201, made.text
    naked = client.post(
        f"{API}/warehouse/receipts/{made.json()['run_id']}/cancel",
        json={"reason": ""},
        headers=warehouse,
    )
    assert naked.status_code == 422, naked.text


def test_only_the_bench_may_unsay_a_receipt(
    client: TestClient, warehouse: dict[str, str], auth: dict[str, str]
) -> None:
    """The same guard the receive door has: this one takes goods off the books."""
    made = _receive(
        client, warehouse, kind="Jemper", colour="Jigarrang", sizes=(("S", 2),)
    )
    assert made.status_code == 201, made.text
    shut = client.post(
        f"{API}/warehouse/receipts/{made.json()['run_id']}/cancel",
        json={"reason": ""},
        headers={**auth, "Idempotency-Key": f"cancel-{uuid4()}"},
    )
    assert shut.status_code == 403, shut.text


def test_a_cancelled_receipt_prints_no_stickers(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """The reprint bench refuses it by name instead of printing paper.

    `/yorliqlar` is exactly the screen somebody reaches for after a receipt
    went wrong, and a sheet of stickers for goods the ledger says never
    arrived is how one of them ends up on a shoe.
    """
    made = _receive(
        client, warehouse, kind="Kostyum", colour="Qora", sizes=(("48", 3),)
    )
    assert made.status_code == 201, made.text
    receipt_id = made.json()["run_id"]

    sheet = client.get(
        f"{API}/warehouse/labels", params={"supply_id": receipt_id}, headers=warehouse
    )
    assert sheet.status_code == 200, sheet.text
    assert sheet.json()["products"]

    assert _cancel(client, warehouse, receipt_id).status_code == 200

    refused = client.get(
        f"{API}/warehouse/labels", params={"supply_id": receipt_id}, headers=warehouse
    )
    assert refused.status_code == 409, refused.text
    assert "bekor qilingan" in refused.json()["detail"]


def test_the_card_and_its_barcodes_outlive_the_cancellation(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """§6.5: a variant's barcode and SKU are permanent.

    The stickers may already be stuck to goods on the table, and a code that
    stops resolving is worse than a variant holding nought. A card whose only
    receipt was this one is a draft with no stock — which is what it was five
    minutes before somebody mistyped.
    """
    made = _receive(
        client, warehouse, kind="Paypoq", colour="Havorang", sizes=(("", 9),)
    )
    assert made.status_code == 201, made.text
    card_id = made.json()["product"]["id"]
    leaf = made.json()["labels"][0]
    assert _cancel(client, warehouse, made.json()["run_id"]).status_code == 200

    with Session(engine) as session:
        card = session.get(Product, card_id)
        assert card is not None
        variant = session.get(ProductVariant, leaf["variant_id"])
        assert variant is not None
        assert variant.barcode == leaf["barcode"]
        assert variant.sku == leaf["sku"]
        assert variant.stock_left == 0
        assert variant.in_stock is False

    # And the scanner still finds it, which is the whole reason the row stays.
    found = client.get(
        f"{API}/warehouse/scan", params={"code": leaf["barcode"]}, headers=warehouse
    )
    assert found.status_code == 200, found.text


def test_the_reprint_bench_can_read_its_own_list(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """A list of `SUP-000032` is a list nobody can read back to a pile of shoes.

    Each row carries what came and when, so `/yorliqlar` can draw a run a
    person recognises instead of a code they have to open to identify.
    """
    made = _receive(
        client, warehouse, kind="Palto", colour="Bej", sizes=(("L", 2),)
    )
    assert made.status_code == 201, made.text

    runs = client.get(f"{API}/warehouse/supplies", headers=warehouse)
    assert runs.status_code == 200, runs.text
    mine = next(row for row in runs.json() if row["id"] == made.json()["run_id"])
    assert mine["product_title"]
    assert mine["colour"] == "Bej"
    assert mine["created_at"]
    assert mine["age_minutes"] >= 0
