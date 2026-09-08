"""Goods that came back, and who answers for them.

A refund settles the money. It settles nothing about the shirt, which is in a
box at the warehouse belonging to a seller who has not been asked anything
yet. Two people answer for it, in this order:

1. **the warehouse** opens the parcel and says what arrived — whole, or
   damaged. Until that happens there is nothing to ask the seller;
2. **the seller** says what to do about it — back on sale, or they collect it.
   Only they can answer: the goods are theirs and the choice costs them money
   either way.

This module holds the two things both of those answers need and neither
endpoint should own: *which lines came back*, and *putting them back on the
shelf exactly once*.

**Why once matters.** There are two roads to the same shirt returning to the
shelf — an operator refunding with ``restock: true``, and a seller choosing
``relist`` — and they can be walked in either order by two different people
minutes apart. Neither knows about the other. So the move is guarded by
``ReturnRequest.relisted_at``: the first road moves the ledger, the second
records its decision and finds the work already done. A shelf count that
gained two shirts because two people agreed about one is the bug this exists
to make unwriteable.

**Why the deadline is swept on read.** There is no scheduler in this system,
and adding one to answer "has a week passed" would be a process to deploy,
supervise and explain. The question is only ever asked when somebody opens a
returns screen, so it is answered there: every list of returns sweeps the
overdue ones first. The cost is a handful of rows on a screen load; the
alternative is a cron job that is down on the one week it mattered.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from app import audit, i18n, inventory
from app.core.config import settings
from app.models import (
    Notification,
    NotificationKind,
    Offer,
    Order,
    OrderItem,
    ReturnInspection,
    ReturnRequest,
    Seller,
    SellerReturnDecision,
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


def seller_of(session: Session, request: ReturnRequest) -> Seller | None:
    """Whose goods came back.

    Read off the offer the order line was bought from rather than the product:
    a card can carry several sellers' offers, and the one that owes an answer
    here is the one that made the sale.
    """
    for line in returned_lines(session, request):
        if line.offer_id is None:
            continue
        offer = session.get(Offer, line.offer_id)
        if offer is None:
            continue
        return session.get(Seller, offer.seller_id)
    return None


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
        # it. *Who decided* is the separate row — ``return.restock`` against
        # the request for an operator's refund, ``return.decide`` for the
        # seller's answer — and that is the row a dispute is about.
        action="return.restock",
        note=note,
    )
    request.relisted_at = utcnow()
    session.add(request)
    return True


def notify_seller(
    session: Session, request: ReturnRequest, *, title: str, text: str
) -> None:
    """Tell the seller something about their returned goods.

    Silently does nothing when there is nobody to tell — an offer whose seller
    row is gone, or a seller with no user account. A notification is not worth
    a 500 on somebody else's decision.
    """
    seller = seller_of(session, request)
    if seller is None or seller.user_id is None:
        return
    session.add(
        Notification(
            user_id=seller.user_id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=title,
            text=text,
            deep_link=f"minibozor://returns/{request.id}",
        )
    )


def deadline() -> datetime:
    """When a seller asked today would run out of time."""
    return utcnow() + timedelta(days=settings.return_decision_days)


def sweep_overdue(session: Session) -> int:
    """Relist everything whose seller never answered, and say how many.

    Only requests that passed inspection: a damaged shirt is not put back on
    sale by a deadline, and a seller who ignores that question is asked again
    rather than sold something broken. Those simply stay undecided — the
    warehouse holds them and the removal flow is how they leave.

    Committed here rather than left to the caller: this runs off the side of a
    read, and a GET that leaves a half-written transaction open for its caller
    to notice is worse than one that finishes its own work.
    """
    now = utcnow()
    overdue = session.exec(
        select(ReturnRequest).where(
            ReturnRequest.inspection == ReturnInspection.OK,
            col(ReturnRequest.seller_decision).is_(None),
            col(ReturnRequest.decision_due_at).is_not(None),
            ReturnRequest.decision_due_at <= now,
        )
    ).all()

    swept = 0
    for request in overdue:
        request.seller_decision = SellerReturnDecision.RELIST
        request.decided_at = now
        audit.record(
            session,
            actor=None,
            action="return.decide",
            entity="return_request",
            entity_id=request.id,
            field="seller_decision",
            old=None,
            new=SellerReturnDecision.RELIST,
            note=i18n.label("return_decision_expired"),
        )
        relist(session, request, actor=None, note=i18n.label("return_decision_expired"))
        notify_seller(
            session,
            request,
            title=i18n.label("return_relisted"),
            text=i18n.label("return_relisted_by_default"),
        )
        swept += 1

    if swept:
        session.commit()
    return swept
