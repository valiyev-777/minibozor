"""The last mile, from the phone in the courier's hand.

``UserRole.COURIER`` existed from the first stage and no router ever asked
about it: an order did not record who was carrying it, and a delivery left no
evidence beyond a status. This file is the whole of the courier's side, and
every door in it is scoped to the caller — a courier reads their own round,
their own collections and nobody else's.

**There is no shift.** There was one, with a cash total to open and close and
count against; it went with the panels rebuild because it is not in this
shop's flow — a courier's day is a list of doors, and what they took at each
one is on the attempt. Cash reconciliation is a separate job for whoever
wants it back, and it wants a screen before it wants a table.

**Every write is keyed.** The app queues what it cannot send and retries, so
the same request arrives twice as a matter of course. The header
``Idempotency-Key`` is required on all of them and the repeat replays the
first answer rather than doing the thing again — see ``app.idempotency``. The
sentence that design exists for is "delivered, 240 000 so'm at the door":
without a key, a retry is a second sale off the shelf, and nobody notices
until the shelf is short.

**A courier never decides to give up.** They record what happened at one door;
an operator who can see three failures and phone the customer decides what
follows. So there is no cancel here, and no ``failed`` status — an attempt is
a row, not a state.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlalchemy import update
from sqlmodel import col, func, select

from app import audit, i18n, inventory
from app import idempotency as idem
from app import schemas as s
from app import services as sv
from app import transitions as tr
from app.core.config import settings
from app.deps import CourierUser, SessionDep
from app.models import (
    AttemptResult,
    CashHandover,
    DeliveryAttempt,
    Notification,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PickupLine,
    PickupRun,
    PickupRunStatus,
    ReturnRequest,
    User,
    UserRole,
    utcnow,
)

router = APIRouter(prefix="/courier", tags=["courier"])

# The header the app sends on every write. Required rather than optional: an
# optional key is a key some client forgets, and the failure is silent and
# financial.
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", description="A uuid per queued action")
]


# --------------------------------------------------------------------------- my round


@router.get(
    "/orders",
    response_model=list[s.CourierOrderOut],
    summary="The ones I took, oldest promise first",
)
def my_orders(
    user: CourierUser,
    session: SessionDep,
    day: date | None = Query(None, description="default: everything still open"),
    done: bool = Query(False, description="Include finished stops"),
) -> list[s.CourierOrderOut]:
    """Mine and nobody else's — not a filter the caller chose but the only
    rows that exist for them.

    Ordered by when the customer was promised it, then by code. Nobody plans
    this round: a courier builds it themselves off the board, so the only
    honest order is the one the promises are in. ``courier_sequence`` is still
    read first and is nought on everything now that no operator sets it — the
    column stays because dropping it is a migration for nothing, and a stop
    somebody does want moved has a place to say so.
    """
    stmt = select(Order).where(Order.courier_id == user.id)
    if day is not None:
        stmt = stmt.where(Order.delivery_day == day)
    if not done:
        stmt = stmt.where(
            col(Order.status).in_([OrderStatus.PACKING, OrderStatus.SHIPPED])
        )
    rows = session.exec(
        stmt.order_by(
            col(Order.courier_sequence),
            col(Order.delivery_day),
            col(Order.delivery_start),
            col(Order.code),
        )
    ).all()
    return [_order_out(session, order) for order in rows]


# ------------------------------------------------------------------ the free board


@router.get(
    "/orders/available",
    response_model=list[s.CourierOrderOut],
    summary="Packed and waiting — anybody's to take",
)
def available_orders(user: CourierUser, session: SessionDep) -> list[s.CourierOrderOut]:
    """Every order the warehouse has packed and nobody has taken.

    Nobody hands these out. An operator choosing who carries what meant a
    packed order sat until somebody remembered to assign it, and a courier
    standing in the warehouse could not pick up the parcel in front of them.
    So the board is open: the warehouse says a parcel is ready, every courier
    sees it, and the one who wants it takes it.

    Oldest first, and that is the only order there is. A board sorted by value
    would have couriers skimming the expensive stops and leaving the rest,
    which is the incentive a flat delivery fee exists to avoid.
    """
    rows = session.exec(
        select(Order)
        .where(Order.status == OrderStatus.PACKING)
        .where(col(Order.courier_id).is_(None))
        .order_by(col(Order.delivery_day), col(Order.delivery_start), col(Order.created_at))
    ).all()
    return [_order_out(session, order) for order in rows]


@router.post(
    "/orders/{order_id}/take",
    response_model=s.CourierOrderOut,
    summary="I am carrying this one",
)
def take_order(
    order_id: int,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.CourierOrderOut:
    """Claim a packed order and walk out with it.

    This is the handover, and it is one act rather than two: the courier
    picking the parcel up off the warehouse shelf is what puts the order on
    the road, so taking it moves ``packing → shipped``. There is no separate
    "handed over" for somebody else to remember to press.

    **Two couriers reaching for the same parcel is the case this has to get
    right.** The claim writes ``courier_id`` only while it is still null and
    checks that the write took, so the second one is told the parcel is gone
    rather than quietly overwriting the first. That is also why the same
    courier repeating the call is not an error — a queued retry from a phone
    in a lift is the ordinary case, and it replays through the key.
    """
    done = idem.replay(session, user, idempotency_key, "order.take", None)
    if done is not None:
        return s.CourierOrderOut(**done)

    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("order_not_found"))
    if order.courier_id == user.id:
        # Already mine. Not an error and not a second claim: the app queues
        # and retries, and "I have it" is still true.
        return _order_out(session, order)
    if order.courier_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_taken"))
    if order.status is not OrderStatus.PACKING:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_not_ready"))

    # Claim it where it is still unclaimed, and read back how many rows that
    # touched. Nought means somebody else got there between the check above
    # and this line, which is a race a check alone cannot close.
    taken = session.exec(
        update(Order)
        .where(col(Order.id) == order.id)
        .where(col(Order.courier_id).is_(None))
        .values(courier_id=user.id, status=OrderStatus.SHIPPED, updated_at=sv.utcnow())
    )
    if taken.rowcount == 0:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_taken"))

    session.refresh(order)
    audit.record(
        session,
        actor=user,
        action="order.taken",
        entity="order",
        entity_id=order.id,
        field="courier_id",
        old=None,
        new=user.id,
    )
    sv.stamp_order_event(session, order)
    session.add(
        Notification(
            user_id=order.user_id,
            kind=NotificationKind.ORDER,
            icon="truck",
            title=i18n.label("event_shipped"),
            text=i18n.label("order_shipped_note", code=order.code),
            deep_link=f"minibozor://orders/{order.id}",
        )
    )
    out = _order_out(session, order)
    idem.keep(session, user, idempotency_key, "order.take", None, out)
    replayed = idem.commit(session, user, idempotency_key, "order.take")
    if replayed:
        return s.CourierOrderOut(**replayed)
    session.refresh(order)
    return _order_out(session, order)


# --------------------------------------------------------------------------- my worth


@router.get(
    "/earnings",
    response_model=s.CourierEarningsOut,
    summary="What I have delivered and what it came to",
)
def earnings(user: CourierUser, session: SessionDep) -> s.CourierEarningsOut:
    """Counted off the attempts, not off the orders.

    A delivery is an event with a time on it, and pay is a question about a
    period — "what did I earn today" cannot be answered by an order's status,
    which only says where the order ended up. The attempt rows are the day's
    work, in order, with the cash on them.
    """
    fee = settings.courier_fee_per_delivery
    mine = select(DeliveryAttempt).where(DeliveryAttempt.courier_id == user.id)

    done = session.exec(mine.where(DeliveryAttempt.result == AttemptResult.DELIVERED)).all()
    failed = session.exec(mine.where(DeliveryAttempt.result == AttemptResult.FAILED)).all()

    today = utcnow().date()
    day = [row for row in done if row.happened_at.date() == today]
    month = [
        row
        for row in done
        if (row.happened_at.year, row.happened_at.month) == (today.year, today.month)
    ]

    collected = sum(row.cash_collected for row in done)
    handed = _handed_in(session, user.id)

    return s.CourierEarningsOut(
        delivered_today=len(day),
        delivered_month=len(month),
        delivered_total=len(done),
        fee_per_delivery=fee,
        earned_today=len(day) * fee,
        earned_month=len(month) * fee,
        earned_total=len(done) * fee,
        # Taken at doors less handed back at the warehouse. This used to be the
        # first half alone, which meant a courier who gave every som to the
        # office still read as carrying a week's takings — a figure that was
        # only ever true on their first day.
        cash_on_hand=max(collected - handed, 0),
        cash_collected=collected,
        cash_handed_in=handed,
        failed_attempts=len(failed),
    )


# --------------------------------------------------------------------- cash back in


@router.get(
    "/cash/receivers",
    response_model=list[s.CashReceiverOut],
    summary="Who at the warehouse may take the cash",
)
def cash_receivers(user: CourierUser, session: SessionDep) -> list[s.CashReceiverOut]:
    """The short list the hand-in screen picks from.

    A courier must name the person who took the money, and naming somebody
    means choosing them from somewhere. Warehouse and admin, which is exactly
    the set ``hand_in_cash`` accepts — a picker offering a name the write
    refuses is a picker that lies.
    """
    rows = session.exec(
        select(User)
        .where(col(User.role).in_([UserRole.WAREHOUSE, UserRole.ADMIN]))
        .where(col(User.is_active).is_(True))
        .order_by(col(User.full_name), col(User.phone))
    ).all()
    return [
        s.CashReceiverOut(
            id=row.id, full_name=row.full_name, phone=row.phone, role=row.role
        )
        for row in rows
    ]


@router.get(
    "/cash/handovers",
    response_model=list[s.CashHandoverOut],
    summary="What I have handed in, newest first",
)
def my_handovers(user: CourierUser, session: SessionDep) -> list[s.CashHandoverOut]:
    """Mine and nobody else's, like the round.

    The receipts the courier can point at when the office's figure and theirs
    disagree — which is the whole reason these are rows and not a counter.
    """
    rows = session.exec(
        select(CashHandover)
        .where(CashHandover.courier_id == user.id)
        .order_by(col(CashHandover.happened_at).desc(), col(CashHandover.id).desc())
    ).all()
    on_hand = _cash_on_hand(session, user.id)
    return [_handover_out(session, row, on_hand) for row in rows]


@router.post(
    "/cash/handovers",
    response_model=s.CashHandoverOut,
    status_code=status.HTTP_201_CREATED,
    summary="Naqdni omborga topshirish — the cash goes back",
)
def hand_in_cash(
    payload: s.CashHandoverIn,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.CashHandoverOut:
    """Money out of a pocket and into the office, with a time on it.

    **Whose money is not a question the request gets to answer.** The courier
    is the caller, always, so there is no way to spell "hand in somebody
    else's cash" — and a courier holding nothing is refused by the arithmetic
    below rather than by a permission check, which is the same answer arrived
    at more honestly.

    Refused rather than clamped when it is more than is held. A courier
    handing over 500 000 while their attempts add up to 300 000 has either
    mistyped a figure or is carrying money this system does not know about,
    and both of those want a person to look rather than a receipt that
    silently records the smaller number.

    Keyed like every other write here: a phone in a warehouse basement queues
    this and retries, and a second receipt for one envelope is exactly the
    kind of quiet financial error the keys exist for.
    """
    done = idem.replay(session, user, idempotency_key, "cash.handover", payload)
    if done is not None:
        return s.CashHandoverOut(**done)

    receiver = session.get(User, payload.received_by_id)
    if (
        receiver is None
        or not receiver.is_active
        or receiver.role not in (UserRole.WAREHOUSE, UserRole.ADMIN)
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("cash_receiver_not_found")
        )

    held = _cash_on_hand(session, user.id)
    if payload.amount > held:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            i18n.label("cash_more_than_held", held=held, given=payload.amount),
        )

    row = CashHandover(
        courier_id=user.id,
        received_by_id=receiver.id,
        amount=payload.amount,
        note=payload.note.strip(),
    )
    session.add(row)
    # Flushed rather than committed: the receipt needs its id to be rendered
    # into the reply that the idempotency record stores, and the record and the
    # money have to land in one transaction or a retry hands the cash in twice.
    session.flush()

    audit.record(
        session,
        actor=user,
        action="cash.handover",
        entity="cash_handover",
        entity_id=row.id,
        field="amount",
        old=held,
        new=held - payload.amount,
        note=f"{payload.amount} so'm · {receiver.full_name or receiver.phone}",
    )

    out = _handover_out(session, row, held - payload.amount)
    idem.keep(session, user, idempotency_key, "cash.handover", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "cash.handover")
    return s.CashHandoverOut(**replayed) if replayed else out


# --------------------------------------------------------------------------- the door


@router.post(
    "/orders/{order_id}/deliver",
    response_model=s.CourierOrderOut,
    summary="Handed over — with who took it, and the cash",
)
def deliver(
    order_id: int,
    payload: s.DeliverIn,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.CourierOrderOut:
    """The one write where a repeat would cost real money.

    A cash order becomes a sale here and not before: the goods were held for
    it from the moment it was placed and this is the moment they leave, which
    is the rule the rest of the system already keeps. Doing that twice would
    take the same shirt off the shelf twice — so this is keyed like everything
    else, and the key is the reason the second arrival is free.

    The cash figure has to match what is owed. A courier who mistypes it has
    nothing to point at afterwards, and a mismatch is far more likely to be a
    typo than a part payment we want to record. The figure is kept on the
    attempt: there is no shift to add it up on any more, so what a courier
    took at the door is answered by their attempts rather than by a running
    total somebody has to close.
    """
    done = idem.replay(session, user, idempotency_key, "order.deliver", payload)
    if done is not None:
        return s.CourierOrderOut(**done)

    order = _own_order(session, user, order_id)
    tr.ensure(tr.ORDER_TRANSITIONS, order.status, OrderStatus.DELIVERED)

    owed = _cash_due(order)
    if payload.cash_collected != owed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            i18n.label("cash_mismatch", owed=owed, given=payload.cash_collected),
        )

    session.add(
        DeliveryAttempt(
            order_id=order.id,
            courier_id=user.id,
            result=AttemptResult.DELIVERED,
            recipient_name=payload.recipient_name.strip(),
            photo_url=payload.photo_url.strip(),
            cash_collected=owed,
        )
    )

    audit.record(
        session,
        actor=user,
        action="order.deliver",
        entity="order",
        entity_id=order.id,
        field="status",
        old=order.status,
        new=OrderStatus.DELIVERED,
        note=(
            f"{payload.recipient_name.strip()}"
            + (f" · naqd {owed}" if owed else "")
            + (" · suratsiz" if not payload.photo_url.strip() else "")
        ),
    )

    # The goods leave the building here, out of this courier's own bag: this
    # is the door, and handing them over is the only thing that empties the
    # room. Cash settles the money at the same moment and is a separate fact.
    order.paid = True
    inventory.hand_over(
        session, order, actor=user, note=payload.recipient_name.strip()
    )

    order.status = OrderStatus.DELIVERED
    order.updated_at = utcnow()
    session.add(order)
    sv.stamp_order_event(session, order, note=payload.note)

    session.add(
        Notification(
            user_id=order.user_id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=i18n.label("event_delivered"),
            text=i18n.label("order_delivered_note", code=order.code),
            deep_link=f"minibozor://orders/{order.id}",
        )
    )

    out = _order_out(session, order)
    idem.keep(session, user, idempotency_key, "order.deliver", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "order.deliver")
    if replayed:
        return s.CourierOrderOut(**replayed)
    session.refresh(order)
    return _order_out(session, order)


@router.post(
    "/orders/{order_id}/failed",
    response_model=s.CourierOrderOut,
    summary="Nobody answered — record the attempt, keep the order",
)
def failed(
    order_id: int,
    payload: s.FailedIn,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.CourierOrderOut:
    """The order stays where it is, and stays with this courier.

    No status change, because nothing about the order changed: it is still
    shipped and still on its way. What changed is that there is now a row
    saying somebody tried and what they found, which is what an operator needs
    to decide whether to phone the customer, send the van again, or give up
    and cancel — and giving up is theirs, not the courier's.
    """
    done = idem.replay(session, user, idempotency_key, "order.failed", payload)
    if done is not None:
        return s.CourierOrderOut(**done)

    order = _own_order(session, user, order_id)
    if order.status is not OrderStatus.SHIPPED:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("not_out_for_delivery"))

    session.add(
        DeliveryAttempt(
            order_id=order.id,
            courier_id=user.id,
            result=AttemptResult.FAILED,
            reason=payload.reason.strip(),
            photo_url=payload.photo_url.strip(),
        )
    )
    audit.record(
        session,
        actor=user,
        action="order.attempt_failed",
        entity="order",
        entity_id=order.id,
        field="attempts",
        old=_attempts(session, order.id) - 1,
        new=_attempts(session, order.id),
        note=payload.reason.strip(),
    )
    # The timeline is not touched: an attempt is not a step the customer's
    # order took, and writing one would put "delivered" in their history
    # before it was true.

    out = _order_out(session, order)
    idem.keep(session, user, idempotency_key, "order.failed", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "order.failed")
    return s.CourierOrderOut(**replayed) if replayed else _order_out(session, order)


# --------------------------------------------------------------------------- collections


@router.get(
    "/pickups",
    response_model=list[s.PickupRunOut],
    summary="Returns to collect from customers",
)
def my_pickups(
    user: CourierUser,
    session: SessionDep,
    done: bool = Query(False, description="Include runs already handed in"),
) -> list[s.PickupRunOut]:
    stmt = select(PickupRun).where(PickupRun.courier_id == user.id)
    if not done:
        stmt = stmt.where(PickupRun.status == PickupRunStatus.OPEN)
    rows = session.exec(stmt.order_by(col(PickupRun.id).desc())).all()
    return [_run_out(session, run) for run in rows]


@router.post(
    "/pickups/{run_id}/collect",
    response_model=s.PickupRunOut,
    summary="What I came back with, door by door",
)
def collect(
    run_id: int,
    payload: s.PickupCollectIn,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.PickupRunOut:
    """Line by line, because a round is rarely all or nothing.

    A door that did not open needs a reason for the same purpose a failed
    delivery does: somebody has to decide what happens to that return, and
    they decide from this sentence.

    Nothing here touches stock. Whether returned goods go back on a shelf is
    the refund's decision — the operator inspects and says restock or write
    off — and putting them back here as well would put the same shirt back
    twice.
    """
    done = idem.replay(session, user, idempotency_key, "pickup.collect", payload)
    if done is not None:
        return s.PickupRunOut(**done)

    run = _own_run(session, user, run_id)
    tr.ensure(tr.PICKUP_TRANSITIONS, run.status, PickupRunStatus.COLLECTED)

    lines = {
        line.return_request_id: line
        for line in session.exec(
            select(PickupLine).where(PickupLine.run_id == run.id)
        ).all()
    }
    for given in payload.lines:
        line = lines.get(given.return_request_id)
        if line is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("pickup_line_not_of_run")
            )
        if not given.collected and not given.reason.strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("pickup_reason_required")
            )
        line.collected = given.collected
        line.reason = given.reason.strip()
        line.photo_url = given.photo_url.strip()
        line.attempted_at = utcnow()
        session.add(line)

    run.status = PickupRunStatus.COLLECTED
    run.collected_at = utcnow()
    if payload.note:
        run.note = payload.note.strip()
    session.add(run)

    audit.record(
        session,
        actor=user,
        action="pickup.collect",
        entity="pickup_run",
        entity_id=run.id,
        field="status",
        old=PickupRunStatus.OPEN,
        new=PickupRunStatus.COLLECTED,
        note=f"{sum(1 for x in payload.lines if x.collected)}/{len(lines)} olindi",
    )

    out = _run_out(session, run)
    idem.keep(session, user, idempotency_key, "pickup.collect", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "pickup.collect")
    if replayed:
        return s.PickupRunOut(**replayed)
    session.refresh(run)
    return _run_out(session, run)


# --------------------------------------------------------------------------- helpers


def _own_order(session: SessionDep, user: User, order_id: int) -> Order:
    """An order on this courier's round. Somebody else's is a 403, not a 404.

    A courier asking about an order they are not carrying has found a real one
    and is being refused, which is what 403 says. Calling it missing would be
    a different claim, and a false one.
    """
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("order_not_found"))
    if order.courier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_delivery"))
    return order

def _own_run(session: SessionDep, user: User, run_id: int) -> PickupRun:
    run = session.get(PickupRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("pickup_not_found"))
    if run.courier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_pickup"))
    return run

def _cash_due(order: Order) -> int:
    """What to ask for at the door.

    Nothing on a card order — it is already paid, and asking again is the
    mistake this exists to prevent. The order's own total otherwise, which is
    the figure the customer agreed to including delivery.
    """
    if order.paid or order.payment_method is not PaymentMethod.CASH:
        return 0
    return order.total


def _collected(session: SessionDep, courier_id: int) -> int:
    """Everything this courier has ever taken at a door."""
    return int(
        session.exec(
            select(func.coalesce(func.sum(DeliveryAttempt.cash_collected), 0))
            .where(DeliveryAttempt.courier_id == courier_id)
            .where(DeliveryAttempt.result == AttemptResult.DELIVERED)
        ).one()
    )


def _handed_in(session: SessionDep, courier_id: int) -> int:
    """And everything they have handed back."""
    return int(
        session.exec(
            select(func.coalesce(func.sum(CashHandover.amount), 0)).where(
                CashHandover.courier_id == courier_id
            )
        ).one()
    )


def _cash_on_hand(session: SessionDep, courier_id: int) -> int:
    """What is in the pocket: taken at doors, less handed in.

    Floored at nought rather than allowed to go negative. Negative cash on
    hand is not a state a person can be in, and an endpoint that reported one
    would be inviting the phone to draw it — the hand-over door refuses to
    take more than is held, so the floor is a second lock on a door already
    bolted rather than a way of hiding a bad figure.
    """
    return max(_collected(session, courier_id) - _handed_in(session, courier_id), 0)


def _handover_out(
    session: SessionDep, row: CashHandover, on_hand: int
) -> s.CashHandoverOut:
    courier = session.get(User, row.courier_id)
    receiver = session.get(User, row.received_by_id)
    return s.CashHandoverOut(
        id=row.id,
        amount=row.amount,
        courier_id=row.courier_id,
        courier_name=(courier.full_name or courier.phone)
        if courier
        else f"#{row.courier_id}",
        received_by_id=row.received_by_id,
        received_by_name=(receiver.full_name or receiver.phone)
        if receiver
        else f"#{row.received_by_id}",
        note=row.note,
        happened_at=row.happened_at,
        cash_on_hand=on_hand,
    )


def _attempts(session: SessionDep, order_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(DeliveryAttempt)
            .where(DeliveryAttempt.order_id == order_id)
        ).one()
    )


def _order_out(session: SessionDep, order: Order) -> s.CourierOrderOut:
    items = session.exec(
        select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(
            OrderItem.order_id == order.id
        )
    ).one()
    tried = session.exec(
        select(DeliveryAttempt)
        .where(DeliveryAttempt.order_id == order.id)
        .order_by(col(DeliveryAttempt.happened_at).desc())
    ).all()
    last = next((a for a in tried if a.result is AttemptResult.FAILED), None)
    window = (
        f"{order.delivery_start}–{order.delivery_end}"
        if order.delivery_start and order.delivery_end
        else ""
    )
    return s.CourierOrderOut(
        id=order.id,
        code=order.code,
        sequence=order.courier_sequence,
        status=order.status,
        recipient_name=order.recipient_name,
        recipient_phone=order.recipient_phone,
        address_line=order.address_line,
        address_meta=order.address_meta,
        # Both null together on a stop whose address was saved without a pin,
        # and on every order placed before the column existed. The screen says
        # "no pin" and keeps the stop; it does not guess one.
        latitude=order.latitude,
        longitude=order.longitude,
        delivery_kind=order.delivery_kind,
        delivery_day=order.delivery_day,
        delivery_window=window,
        items_count=int(items),
        total=order.total,
        payment_method=order.payment_method,
        cash_due=_cash_due(order),
        attempts=len(tried),
        last_failure=last.reason if last else "",
    )

def _run_out(session: SessionDep, run: PickupRun) -> s.PickupRunOut:
    courier = session.get(User, run.courier_id)
    lines = session.exec(
        select(PickupLine).where(PickupLine.run_id == run.id).order_by(col(PickupLine.id))
    ).all()
    out: list[s.PickupLineOut] = []
    for line in lines:
        request = session.get(ReturnRequest, line.return_request_id)
        order = session.get(Order, request.order_id) if request else None
        customer = session.get(User, request.user_id) if request else None
        item = (
            session.get(OrderItem, request.order_item_id)
            if request and request.order_item_id
            else None
        )
        title = item.title if item else ""
        if not title and order is not None:
            first = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).first()
            title = first.title if first else ""
        out.append(
            s.PickupLineOut(
                id=line.id,
                return_request_id=line.return_request_id,
                order_code=order.code if order else "",
                customer_name=(customer.full_name or customer.phone) if customer else "",
                customer_phone=customer.phone if customer else "",
                address_line=order.address_line if order else "",
                reason=request.reason if request else "",
                product_title=title,
                collected=line.collected,
                note=line.reason,
                photo_url=sv.media_url(line.photo_url),
                attempted_at=line.attempted_at,
            )
        )
    return s.PickupRunOut(
        id=run.id,
        code=run.code,
        courier_id=run.courier_id,
        courier_name=(courier.full_name or courier.phone)
        if courier
        else f"#{run.courier_id}",
        status=run.status,
        next_statuses=tr.next_states(tr.PICKUP_TRANSITIONS, run.status),
        created_at=run.created_at,
        collected_at=run.collected_at,
        received_at=run.received_at,
        note=run.note,
        lines=out,
    )
