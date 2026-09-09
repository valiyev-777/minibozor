"""Goods that came back, and what becomes of them.

A refund settles the money. It settles nothing about the shirt, which is in a
box at the warehouse. Somebody opens the parcel and says what arrived — whole,
or damaged — and the shelf follows from that: whole goods go back on sale,
damaged ones do not.

There used to be a second answer here. The goods belonged to a seller and only
they could say whether to relist them or come and collect them, with a
deadline and a sweep for the ones who never replied. The goods are ours now,
so the inspection is the whole of it.

This module holds the two things that answer needs and no endpoint should own:
*which lines came back*, and *putting them back on the shelf exactly once*.

**Why once matters.** There are two roads to the same shirt returning to the
shelf — a refund with ``restock: true``, and an inspection that passed — and
they can be walked in either order by two different people minutes apart.
Neither knows about the other. So the move is guarded by
``ReturnRequest.relisted_at``: the first road moves the ledger, the second
finds the work already done. A shelf count that gained two shirts because two
people agreed about one is the bug this exists to make unwriteable.
"""

from __future__ import annotations

from sqlmodel import Session

from app import inventory
from app.models import (
    Order,
    OrderItem,
    ReturnRequest,
    User,
)
from app.services import utcnow


def returned_lines(
    session: Session, request: ReturnRequest, order: Order | None = None
) -> list[OrderItem]:
    """What is coming back: the line the request named, or the whole order.

    The lines rather than a figure, because the same answer settles every
    question anybody asks of a return — how much money goes back, which counts
    move, and whose goods these are.
    """
    if request.order_item_id:
        item = session.get(OrderItem, request.order_item_id)
        return [item] if item is not None else []
    if order is None:
        order = session.get(Order, request.order_id)
    return inventory.order_items(session, order) if order else []


def relist(
    session: Session,
    request: ReturnRequest,
    *,
    actor: User | None,
    note: str = "",
) -> bool:
    """Put the returned goods back on the shelf, at most once ever.

    Returns whether this call was the one that moved the ledger. Does not
    commit — the caller commits together with whatever decision made the move
    necessary, so the shelf cannot end up describing a decision that rolled
    back.
    """
    if request.relisted_at is not None:
        return False

    inventory.restock_returned(
        session,
        returned_lines(session, request),
        actor=actor,
        # One action name for the shelf whichever road got here, because the
        # shelf-level fact is the same one: goods that came back are back on
        # it. *Who decided* is the separate row against the request, and that
        # is the row a dispute is about.
        action="return.restock",
        note=note,
    )
    request.relisted_at = utcnow()
    session.add(request)
    return True
