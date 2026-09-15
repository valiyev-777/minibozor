"""The courier's phone: a map with stops on it, and the cash going back.

Two gaps the map-first app opened, held here because neither of them is
visible from the screens that already existed.

**A stop needs a point.** ``Order`` snapshotted the words for an address and
not the pin, so a round could be listed and could not be drawn. The
coordinates are now copied onto the order at checkout exactly as the text is,
and for the same reason: the address row can be edited or deleted the day
after, and the order must still say where it went. An address saved without a
pin has none — that is an ordinary answer and the stop survives it.

**Cash on hand has to be able to go down.** It was the sum of everything a
courier had ever collected, with nothing anywhere to subtract, so it was only
true on their first day. ``POST /courier/cash/handovers`` is the door, and
what it writes is a receipt with a time on it naming both hands rather than a
counter somebody resets.

Every test here hires **its own courier**. The suite's shared one carries
whatever the tests before it left in their pockets, and an arithmetic assertion
against a figure other tests are adding to is an assertion that fails on the
day somebody writes another delivery test.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.models import User, UserRole
from tests.test_api import API, _on_sale

# --------------------------------------------------------------------------- helpers


def _user_id(phone: str) -> int:
    """The id behind a phone number, which no endpoint hands to its owner."""
    with Session(engine) as session:
        return session.exec(select(User).where(User.phone == phone)).one().id


def _address(
    client: TestClient,
    auth: dict[str, str],
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int:
    """An address with a pin, or deliberately without one."""
    made = client.post(
        f"{API}/addresses",
        json={
            "line": "Toshkent, Amir Temur 108",
            "title": "Uy",
            "latitude": latitude,
            "longitude": longitude,
        },
        headers=auth,
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _cash_order(
    client: TestClient,
    auth: dict[str, str],
    product_id: int,
    variant_id: int,
    address_id: int,
) -> dict:
    """One line, one cash order, from a basket emptied first.

    Emptied because the customer fixture is shared: a line another test left
    selected would be checked out by this one and the totals would stop being
    the arithmetic these tests are about.
    """
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": product_id, "variant_id": variant_id, "quantity": 1},
        headers=auth,
    )
    assert added.status_code == 201, added.text
    placed = client.post(
        f"{API}/orders",
        json={"address_id": address_id, "payment_method": "cash"},
        headers=auth,
    )
    assert placed.status_code == 201, placed.text
    return placed.json()


def _packed(client: TestClient, admin: dict[str, str], order_id: int) -> None:
    done = client.post(
        f"{API}/admin/orders/{order_id}/status",
        json={"status": "packing"},
        headers=admin,
    )
    assert done.status_code == 200, done.text


def _delivered(
    client: TestClient,
    admin: dict[str, str],
    courier: dict[str, str],
    order: dict,
) -> None:
    """Off the board, out of the bag, cash in the pocket."""
    _packed(client, admin, order["id"])
    took = client.post(
        f"{API}/courier/orders/{order['id']}/take",
        headers={**courier, "Idempotency-Key": f"take-{uuid4().hex}"},
    )
    assert took.status_code == 200, took.text
    gave = client.post(
        f"{API}/courier/orders/{order['id']}/deliver",
        json={"recipient_name": "Aziz", "cash_collected": order["total"]},
        headers={**courier, "Idempotency-Key": f"give-{uuid4().hex}"},
    )
    assert gave.status_code == 200, gave.text


def _earnings(client: TestClient, courier: dict[str, str]) -> dict:
    got = client.get(f"{API}/courier/earnings", headers=courier)
    assert got.status_code == 200, got.text
    return got.json()


def _a_receiver(client: TestClient, courier: dict[str, str], phone: str) -> dict:
    """The warehouse hand the courier is about to give the envelope to."""
    got = client.get(f"{API}/courier/cash/receivers", headers=courier)
    assert got.status_code == 200, got.text
    found = [row for row in got.json() if row["phone"] == phone]
    assert found, f"{phone} is not offered as somebody who may take cash"
    return found[0]


def _reads_as(receiver: dict) -> str:
    """How a receipt spells that person: their name, or their number.

    The fallback is not decoration. Staff are made by setting a role on a
    number that signed in, so a warehouse hand who has never filled in their
    name has none — and a receipt that named nobody would be the one row in
    this table that settles no argument.
    """
    return receiver["full_name"] or receiver["phone"]


# --------------------------------------------------------------------------- the map


def test_a_stop_carries_the_pin_it_was_ordered_from(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """The courier's round reports the coordinates the customer ordered to.

    Snapshotted at checkout, so this is asserted through the courier's own
    shape rather than off the address row — the address is what the customer
    can edit, and the round is what has to survive them editing it.
    """
    courier = staff(UserRole.COURIER, "+998900007701")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-PIN", stock=5)
    pinned = _address(client, auth, latitude=41.311081, longitude=69.240562)
    order = _cash_order(client, auth, card["id"], ids["Qora / 42"], pinned)

    _packed(client, admin, order["id"])
    board = client.get(f"{API}/courier/orders/available", headers=courier)
    assert board.status_code == 200, board.text
    stop = next(row for row in board.json() if row["id"] == order["id"])

    assert stop["latitude"] == 41.311081
    assert stop["longitude"] == 69.240562
    # And the words are still there. The pin is an addition to the address, not
    # a replacement for it: a courier at the kerb reads the line to find the
    # entrance.
    assert stop["address_line"] == "Toshkent, Amir Temur 108"


def test_a_stop_without_a_pin_says_so_rather_than_disappearing(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """An address saved without a pin is an ordinary address.

    Null on both, and the stop is still on the round — the screen draws it in
    the list and says it cannot be mapped. Dropping it would hide a real
    delivery from the person who has to make it, which is a far worse failure
    than a missing marker.
    """
    courier = staff(UserRole.COURIER, "+998900007702")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-NOPIN", stock=5)
    bare = _address(client, auth)
    order = _cash_order(client, auth, card["id"], ids["Qora / 42"], bare)

    _packed(client, admin, order["id"])
    board = client.get(f"{API}/courier/orders/available", headers=courier).json()
    stop = next(row for row in board if row["id"] == order["id"])

    assert stop["latitude"] is None
    assert stop["longitude"] is None
    assert stop["address_line"]


# --------------------------------------------------------------------------- the cash


def test_handing_the_cash_in_reduces_what_is_on_hand_and_leaves_a_receipt(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """The figure comes down, and a row says where the money went.

    A counter being reset would satisfy the first half of that sentence and
    nothing at all of the second, which is why this is a table: the office is
    asked "who had Tuesday's takings" and the answer has to name a person and
    a moment.
    """
    courier = staff(UserRole.COURIER, "+998900007703")
    courier_id = _user_id("+998900007703")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-HAND", stock=5)
    order = _cash_order(
        client, auth, card["id"], ids["Qora / 42"], _address(client, auth)
    )
    _delivered(client, admin, courier, order)

    took = order["total"]
    assert _earnings(client, courier)["cash_on_hand"] == took

    desk = _a_receiver(client, courier, "+998900009002")
    handed = client.post(
        f"{API}/courier/cash/handovers",
        json={
            "amount": took,
            "received_by_id": desk["id"],
            "note": "kechki inkassatsiya",
        },
        headers={**courier, "Idempotency-Key": f"cash-{uuid4().hex}"},
    )
    assert handed.status_code == 201, handed.text
    receipt = handed.json()
    assert receipt["amount"] == took
    assert receipt["courier_id"] == courier_id
    assert receipt["received_by_id"] == desk["id"]
    assert receipt["received_by_name"] == _reads_as(desk)
    assert receipt["happened_at"]
    # The reply already carries the new figure, so the phone redraws without a
    # second request over the connection this app is built for.
    assert receipt["cash_on_hand"] == 0

    after = _earnings(client, courier)
    assert after["cash_on_hand"] == 0
    assert after["cash_collected"] == took
    assert after["cash_handed_in"] == took

    # And the office can see it, by courier, naming the hand it went into.
    office = client.get(
        f"{API}/admin/cash/handovers", params={"courier_id": courier_id}, headers=admin
    )
    assert office.status_code == 200, office.text
    rows = office.json()
    assert len(rows) == 1
    assert rows[0]["id"] == receipt["id"]
    assert rows[0]["amount"] == took
    assert rows[0]["received_by_name"] == _reads_as(desk)
    assert rows[0]["note"] == "kechki inkassatsiya"


def test_more_cash_than_is_held_is_refused(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """Refused rather than clamped, and nothing is written.

    A courier handing over more than their doors add up to has either
    mistyped a figure or is carrying money this system does not know about.
    Both want a person to look, and a receipt quietly recording the smaller
    number is how neither of them is ever noticed.
    """
    courier = staff(UserRole.COURIER, "+998900007704")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-OVER", stock=5)
    order = _cash_order(
        client, auth, card["id"], ids["Qora / 42"], _address(client, auth)
    )
    _delivered(client, admin, courier, order)
    desk = _a_receiver(client, courier, "+998900009002")

    too_much = client.post(
        f"{API}/courier/cash/handovers",
        json={"amount": order["total"] + 1, "received_by_id": desk["id"]},
        headers={**courier, "Idempotency-Key": f"cash-{uuid4().hex}"},
    )
    assert too_much.status_code == 400, too_much.text

    # Nothing happened: the figure is where it was and there is no receipt.
    assert _earnings(client, courier)["cash_on_hand"] == order["total"]
    mine = client.get(f"{API}/courier/cash/handovers", headers=courier)
    assert mine.status_code == 200, mine.text
    assert mine.json() == []


def test_nothing_is_not_a_hand_over(
    client: TestClient,
    staff,
) -> None:
    """Nought is a tap on a button, not an envelope.

    Refused by the shape rather than by the endpoint, so it never reaches the
    arithmetic — a receipt for nothing is a row somebody has to explain.
    """
    courier = staff(UserRole.COURIER, "+998900007705")
    desk = _a_receiver(client, courier, "+998900009002")
    nothing = client.post(
        f"{API}/courier/cash/handovers",
        json={"amount": 0, "received_by_id": desk["id"]},
        headers={**courier, "Idempotency-Key": f"cash-{uuid4().hex}"},
    )
    assert nothing.status_code == 422, nothing.text


def test_a_retried_hand_over_happens_once(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """The phone queued it in a warehouse basement and sent it twice.

    The second arrival replays the first answer — the stored bytes, not a
    fresh computation — and the money moves once. Without this, one envelope
    becomes two receipts and a courier reads as owing nothing while still
    holding a day's takings.
    """
    courier = staff(UserRole.COURIER, "+998900007706")
    courier_id = _user_id("+998900007706")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-RETRY", stock=5)
    order = _cash_order(
        client, auth, card["id"], ids["Qora / 42"], _address(client, auth)
    )
    _delivered(client, admin, courier, order)

    desk = _a_receiver(client, courier, "+998900009002")
    body = {"amount": order["total"], "received_by_id": desk["id"]}
    key = f"cash-{uuid4().hex}"

    first = client.post(
        f"{API}/courier/cash/handovers",
        json=body,
        headers={**courier, "Idempotency-Key": key},
    )
    second = client.post(
        f"{API}/courier/cash/handovers",
        json=body,
        headers={**courier, "Idempotency-Key": key},
    )
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()

    assert _earnings(client, courier)["cash_on_hand"] == 0
    office = client.get(
        f"{API}/admin/cash/handovers", params={"courier_id": courier_id}, headers=admin
    )
    assert len(office.json()) == 1


def test_a_courier_cannot_hand_in_somebody_elses_cash(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """Whose money it is comes from the token and from nowhere else.

    The second courier has knocked on no doors, so there is nothing for them
    to hand in however much the first one is carrying — and naming the first
    one in the body changes nothing, because the shape has no field for it and
    an extra one is not read. The refusal is the arithmetic's rather than a
    permission check's, which is the same answer arrived at more honestly.
    """
    earner = staff(UserRole.COURIER, "+998900007707")
    earner_id = _user_id("+998900007707")
    other = staff(UserRole.COURIER, "+998900007708")
    other_id = _user_id("+998900007708")

    card, ids = _on_sale(client, admin, warehouse, sku="KUR-MINE", stock=5)
    order = _cash_order(
        client, auth, card["id"], ids["Qora / 42"], _address(client, auth)
    )
    _delivered(client, admin, earner, order)

    desk = _a_receiver(client, other, "+998900009002")
    tried = client.post(
        f"{API}/courier/cash/handovers",
        json={
            "amount": order["total"],
            "received_by_id": desk["id"],
            # Ignored: the request cannot say whose cash this is.
            "courier_id": earner_id,
        },
        headers={**other, "Idempotency-Key": f"cash-{uuid4().hex}"},
    )
    assert tried.status_code == 400, tried.text

    # The first courier still has every som of it, and neither of them has a
    # receipt.
    assert _earnings(client, earner)["cash_on_hand"] == order["total"]
    assert _earnings(client, other)["cash_on_hand"] == 0
    for who in (earner_id, other_id):
        office = client.get(
            f"{API}/admin/cash/handovers", params={"courier_id": who}, headers=admin
        )
        assert office.json() == []


def test_cash_on_hand_is_taken_at_doors_less_handed_in(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
    staff,
) -> None:
    """Deliver, hand some in, deliver again — and the figure is the subtraction.

    The whole point of the change: the figure moves in both directions, so a
    courier who settles up at lunchtime and works the afternoon reads as
    carrying the afternoon rather than the week.
    """
    courier = staff(UserRole.COURIER, "+998900007709")
    card, ids = _on_sale(client, admin, warehouse, sku="KUR-SUM", stock=5)
    address = _address(client, auth)

    first = _cash_order(client, auth, card["id"], ids["Qora / 42"], address)
    _delivered(client, admin, courier, first)

    desk = _a_receiver(client, courier, "+998900009002")
    part = first["total"] // 2
    handed = client.post(
        f"{API}/courier/cash/handovers",
        json={"amount": part, "received_by_id": desk["id"]},
        headers={**courier, "Idempotency-Key": f"cash-{uuid4().hex}"},
    )
    assert handed.status_code == 201, handed.text
    assert handed.json()["cash_on_hand"] == first["total"] - part

    second = _cash_order(client, auth, card["id"], ids["Oq / 42"], address)
    _delivered(client, admin, courier, second)

    after = _earnings(client, courier)
    assert after["cash_collected"] == first["total"] + second["total"]
    assert after["cash_handed_in"] == part
    assert after["cash_on_hand"] == first["total"] + second["total"] - part
    # Never negative, whatever the order of events.
    assert after["cash_on_hand"] >= 0
