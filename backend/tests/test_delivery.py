"""Delivery is free and there are no windows to choose from.

Two deletions, held here so neither can drift back in halves.

**The fee is gone.** There was a threshold — spend above it and delivery cost
nothing, below it and it cost 19 000 — and the owner has replaced the whole
rule with one answer: delivery is free. ``Order.delivery_fee`` and
``CartTotalsOut.delivery_fee`` survive as a zero, because a charge is a price a
shop may want back and a kept line means the orders already placed still add
up when it returns. So the tests below are about the *rule*, not the column: no
basket, at any size, is ever charged for delivery.

**The windows are gone.** ``delivery_slots`` was a table, four endpoints and a
seat count that a cancellation had to remember to give back. Nothing chose a
window, nothing was ever shown one, and the office had to open a fortnight of
them before the shop could take its first order. What stays is the snapshot on
the order — ``delivery_day``, ``delivery_start``, ``delivery_end`` — which
nothing writes now, so every order reads back saying its date is being worked
out. That is the wanted answer, and it is asserted here rather than left to be
discovered.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import i18n
from app.db import engine
from app.models import Order, PickupPoint
from tests.test_api import (
    API,
    _address,
    _on_sale,
    _order,
    _payment_card,
    _sellable,
)

# --------------------------------------------------------------------------- helpers


def _basket(
    client: TestClient, auth: dict[str, str], product_id: int, variant_id: int, qty: int
) -> dict:
    """One line in an empty basket, and the totals that come back."""
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": product_id, "variant_id": variant_id, "quantity": qty},
        headers=auth,
    )
    assert added.status_code == 201, added.text
    return client.get(f"{API}/cart", headers=auth).json()["totals"]


def _a_pickup_point() -> int:
    """Nothing seeds one, and the point of this test is the ``pickup`` branch."""
    with Session(engine) as session:
        row = session.exec(
            select(PickupPoint).where(PickupPoint.name == "Chilonzor punkti")
        ).first()
        if row is None:
            row = PickupPoint(
                name="Chilonzor punkti",
                address="Toshkent, Chilonzor 9",
                distance_km=2.4,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return row.id


# --------------------------------------------------------------------------- the fee


def test_delivery_is_free_whatever_the_basket_costs(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """The old rule turned on 500 000. Both sides of it are now nothing.

    One cheap card and one dear one, so a threshold reintroduced by accident —
    in either direction, and in a currency where 19 000 is easy to miss — has
    a basket here that fails.
    """
    cheap, cheap_ids = _on_sale(
        client, admin, warehouse, sku="DLV-CHEAP", stock=6, price=90_000
    )
    dear, dear_ids = _on_sale(
        client, admin, warehouse, sku="DLV-DEAR", stock=6, price=640_000
    )

    small = _basket(client, auth, cheap["id"], cheap_ids["Qora / 42"], 1)
    assert small["subtotal"] == 90_000
    assert small["delivery_fee"] == 0, "a small basket was charged for delivery"
    assert small["total"] == small["subtotal"]

    large = _basket(client, auth, dear["id"], dear_ids["Qora / 42"], 3)
    assert large["subtotal"] == 1_920_000
    assert large["delivery_fee"] == 0
    assert large["total"] == large["subtotal"]

    client.delete(f"{API}/cart", headers=auth)


def test_the_basket_no_longer_names_a_threshold(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """``free_delivery_threshold`` is gone from the shape, not set to zero.

    A zero would have every client drawing "spend 0 so'm more for free
    delivery" until each of them noticed. The field is removed, and the apps
    remove the line that read it.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-NOTHRESH", stock=4, price=120_000
    )
    totals = _basket(client, auth, card["id"], ids["Qora / 42"], 1)
    assert "free_delivery_threshold" not in totals
    client.delete(f"{API}/cart", headers=auth)


def test_a_placed_order_is_written_down_as_free(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Free in the reply and free in the row, which are two different claims.

    The report reads ``orders.delivery_fee`` and the app reads the response;
    a rule removed from only one of them shows up as a headline that
    disagrees with every receipt under it.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-PLACED", stock=4, price=150_000
    )
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    assert order["delivery_fee"] == 0
    assert order["total"] == order["subtotal"] - order["discount"]

    with Session(engine) as session:
        assert session.get(Order, order["id"]).delivery_fee == 0


def test_a_pickup_order_is_free_too(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """Collection was the one delivery that was already free.

    It reached zero by its own branch in the checkout, which has gone with the
    rule around it. So the branch is checked from outside: a collected order
    still costs the goods and nothing else, and it says "Punktdan olish"
    rather than a date being worked out.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-PICKUP", stock=4, price=210_000
    )
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 1},
        headers=auth,
    )
    assert added.status_code == 201, added.text

    placed = client.post(
        f"{API}/orders",
        json={
            "pickup_point_id": _a_pickup_point(),
            "payment_method": "card",
            "payment_card_id": _payment_card(client, auth, last4="7777"),
        },
        headers=auth,
    )
    assert placed.status_code == 201, placed.text
    order = placed.json()

    assert order["delivery_kind"] == "pickup"
    assert order["delivery_fee"] == 0
    assert order["total"] == order["subtotal"]
    assert order["eta_label"] == i18n.label("pickup")


# --------------------------------------------------------------------------- the windows


def test_an_order_is_placed_with_no_window_and_says_so(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """The snapshot columns stay and nothing writes them.

    Which is the accepted cost of the deletion: the three columns are what a
    later version puts a chosen window into, and until then every courier
    order reads back empty and the ETA falls through to "the date is being
    worked out". A regression here would be an order claiming a delivery day
    the shop never promised.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-NOWINDOW", stock=4, price=180_000
    )
    order = _order(client, auth, card["id"], ids["Qora / 42"])

    read = client.get(f"{API}/orders/{order['id']}", headers=auth)
    assert read.status_code == 200, read.text
    body = read.json()

    assert body["delivery_kind"] == "courier"
    assert body["delivery_day"] is None
    assert body["delivery_start"] is None
    assert body["delivery_end"] is None
    assert body["eta_label"] == i18n.label("eta_pending")

    # And the same order in the operator's queue, which prints the window
    # from those columns and must not invent one.
    queue = client.get(f"{API}/admin/orders?status=placed", headers=admin)
    assert queue.status_code == 200, queue.text
    row = next(r for r in queue.json()["items"] if r["id"] == order["id"])
    assert row["delivery_day"] is None
    assert row["delivery_window"] == ""


def test_the_customers_slot_door_is_gone(client: TestClient) -> None:
    got = client.get(f"{API}/delivery/slots")
    assert got.status_code == 404, got.text


def test_the_office_has_no_doors_for_opening_windows(
    client: TestClient, admin: dict[str, str]
) -> None:
    """All three, and as the admin — so a 403 cannot be mistaken for a 404.

    Checked against a reader who is allowed everything else in that router,
    because the failure being guarded against is a route left mounted and
    merely unreachable by the people who used it.
    """
    listed = client.get(f"{API}/admin/delivery/slots", headers=admin)
    assert listed.status_code == 404, listed.text

    opened = client.post(
        f"{API}/admin/delivery/slots",
        json={"days": ["2026-10-01"], "windows": [{"start_time": "09:00", "end_time": "13:00"}]},
        headers=admin,
    )
    assert opened.status_code == 404, opened.text

    changed = client.patch(
        f"{API}/admin/delivery/slots/1", json={"capacity_left": 5}, headers=admin
    )
    assert changed.status_code == 404, changed.text


def test_the_checkout_ignores_a_slot_id_it_is_sent(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """A shipped app still sends one, and it must not be a 422.

    The phones in people's pockets were built against a checkout that took
    ``slot_id``. Pydantic drops a field the model does not declare, so the
    order places — but "it happens to work" is the kind of thing a strict-mode
    change breaks silently, and the customers it breaks for are the ones who
    have not updated.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-OLDAPP", stock=4, price=130_000
    )
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={"product_id": card["id"], "variant_id": ids["Qora / 42"], "quantity": 1},
        headers=auth,
    )
    assert added.status_code == 201, added.text

    placed = client.post(
        f"{API}/orders",
        json={
            "address_id": _address(client, auth),
            "slot_id": 3,
            "payment_method": "card",
            "payment_card_id": _payment_card(client, auth, last4="6543"),
        },
        headers=auth,
    )
    assert placed.status_code == 201, placed.text
    assert placed.json()["delivery_day"] is None


def test_a_cancelled_order_still_gives_back_everything_it_owes(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    auth: dict[str, str],
) -> None:
    """The seat is not one of the three things any more; the other two are.

    ``inventory.restore_order`` gave back the sold count, the picked goods and
    the window's seat. Deleting the third by hand is exactly the edit that
    takes a working ``for`` loop with it, so this holds the two that remain:
    the promised units are released and the order is cancelled with its reason
    on it.
    """
    card, ids = _on_sale(
        client, admin, warehouse, sku="DLV-CANCEL", stock=5, price=240_000
    )
    leaf = ids["Qora / 42"]
    before = _sellable(leaf)

    order = _order(client, auth, card["id"], leaf, quantity=2)
    assert _sellable(leaf) == before - 2, "the order did not hold the goods"

    off = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason": "Fikrimdan qaytdim"},
        headers=auth,
    )
    assert off.status_code == 200, off.text

    assert _sellable(leaf) == before, "a cancelled order kept holding the goods"
    read = client.get(f"{API}/orders/{order['id']}", headers=auth).json()
    assert read["status"] == "cancelled"
    assert read["delivery_fee"] == 0
