"""The last mile, from the phone in the courier's hand.

``UserRole.COURIER`` existed from the first stage and no router ever asked
about it. An order did not record who was carrying it; there was no shift; a
delivery left no evidence beyond a status; and cash — which a courier
physically holds all day — was counted nowhere. This file is the whole of the
courier's side, and every door in it is scoped to the caller: a courier reads
their own round, their own shift, their own collections and nobody else's.

**Every write is keyed.** The app queues what it cannot send and retries, so
the same request arrives twice as a matter of course. The header
``Idempotency-Key`` is required on all of them and the repeat replays the
first answer rather than doing the thing again — see ``app.idempotency``. The
sentence that design exists for is "delivered, 240 000 so'm at the door":
without a key, a retry is a second sale off the shelf and a second 240 000 on
the shift, and nobody notices until the courier is accused of being short.

**A courier never decides to give up.** They record what happened at one door;
an operator who can see three failures and phone the customer decides what
follows. So there is no cancel here, and no ``failed`` status — an attempt is
a row, not a state.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n, inventory
from app import idempotency as idem
from app import schemas as s
from app import services as sv
from app import transitions as tr
from app.deps import CourierUser, SessionDep
from app.models import (
    AttemptResult,
    CourierShift,
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
    ShiftStatus,
    User,
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
    summary="My deliveries, in the order somebody planned",
)
def my_orders(
    user: CourierUser,
    session: SessionDep,
    day: date | None = Query(None, description="default: everything still open"),
    done: bool = Query(False, description="Include finished stops"),
) -> list[s.CourierOrderOut]:
    """Mine and nobody else's — not a filter the caller chose but the only
    rows that exist for them.

    Sorted by the sequence an operator set, then the delivery window, then the
    code. An unsequenced round still comes back in a sensible order rather
    than in whatever order the ids happen to fall.
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


# --------------------------------------------------------------------------- the shift


@router.get(
    "/shifts/current",
    response_model=s.ShiftDetailOut | None,
    summary="My open shift, if I am out",
)
def current_shift(user: CourierUser, session: SessionDep) -> s.ShiftDetailOut | None:
    shift = _open_shift(session, user)
    return _shift_detail(session, shift) if shift else None


@router.post(
    "/shifts",
    response_model=s.ShiftDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a round",
)
def open_shift(
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.ShiftDetailOut:
    """One open shift at a time.

    Two would mean cash landing on whichever one a request happened to find,
    and no way afterwards to say which round a note came from. A courier who
    already has one open gets it back rather than an error: the app is
    probably retrying, and the answer to "start my shift" when it is already
    started is the shift.
    """
    done = idem.replay(session, user, idempotency_key, "shift.open", None)
    if done is not None:
        return s.ShiftDetailOut(**done)

    existing = _open_shift(session, user)
    if existing is not None:
        return _shift_detail(session, existing)

    shift = CourierShift(courier_id=user.id)
    session.add(shift)
    session.commit()
    session.refresh(shift)

    out = _shift_detail(session, shift)
    idem.keep(session, user, idempotency_key, "shift.open", None, out)
    replayed = idem.commit(session, user, idempotency_key, "shift.open")
    return s.ShiftDetailOut(**replayed) if replayed else out


@router.post(
    "/shifts/{shift_id}/close",
    response_model=s.ShiftDetailOut,
    summary="Come back, and hand the cash over",
)
def close_shift(
    shift_id: int,
    payload: s.ShiftCloseIn,
    user: CourierUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.ShiftDetailOut:
    """The courier's claim about the money, recorded against ours.

    ``cash_expected`` is the sum of the doors and is not editable here.
    ``cash_declared`` is what the courier says they are handing over. The
    office counts later, and the three figures are kept apart so a difference
    is a fact rather than an argument. Closing writes an audit row whether
    they agree or not — money moving is the thing that always gets a name
    against it.
    """
    done = idem.replay(session, user, idempotency_key, "shift.close", payload)
    if done is not None:
        return s.ShiftDetailOut(**done)

    shift = _own_shift(session, user, shift_id)
    if shift.status is not ShiftStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("shift_closed"))

    audit.record(
        session,
        actor=user,
        action="shift.close",
        entity="courier_shift",
        entity_id=shift.id,
        field="cash_declared",
        old=shift.cash_expected,
        new=payload.cash_declared,
        note=(
            payload.note
            or (
                ""
                if payload.cash_declared == shift.cash_expected
                else f"farq {payload.cash_declared - shift.cash_expected}"
            )
        ),
    )
    shift.status = ShiftStatus.CLOSED
    shift.cash_declared = payload.cash_declared
    shift.closed_at = utcnow()
    if payload.note:
        shift.note = payload.note.strip()
    session.add(shift)

    out = _shift_detail(session, shift)
    idem.keep(session, user, idempotency_key, "shift.close", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "shift.close")
    if replayed:
        return s.ShiftDetailOut(**replayed)
    session.refresh(shift)
    return _shift_detail(session, shift)


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
    take the same shirt off the shelf twice and put the same cash on the shift
    twice — so this is keyed like everything else, and the key is the reason
    the second arrival is free.

    The cash figure has to match what is owed. A courier who mistypes it is
    short at the end of the day with nothing to point at, and a mismatch is
    far more likely to be a typo than a part payment we want to record.
    """
    done = idem.replay(session, user, idempotency_key, "order.deliver", payload)
    if done is not None:
        return s.CourierOrderOut(**done)

    order = _own_order(session, user, order_id)
    tr.ensure(tr.ORDER_TRANSITIONS, order.status, OrderStatus.DELIVERED)

    shift = _open_shift(session, user)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("shift_required"))

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
            shift_id=shift.id,
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

    if not order.paid:
        # Cash at the door. The goods leave the shelf now, because now is when
        # it becomes a sale — the same two-step the operator's own status door
        # keeps, and the reason ``inventory.sell`` is separate from ``take``.
        order.paid = True
        for line in inventory.order_items(session, order):
            inventory.sell(session, line)

    order.status = OrderStatus.DELIVERED
    order.updated_at = utcnow()
    session.add(order)
    sv.stamp_order_event(session, order, note=payload.note)

    shift.cash_expected += owed
    shift.orders_delivered += 1
    session.add(shift)

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

    shift = _open_shift(session, user)
    session.add(
        DeliveryAttempt(
            order_id=order.id,
            courier_id=user.id,
            shift_id=shift.id if shift else None,
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
    if shift is not None:
        shift.orders_failed += 1
        session.add(shift)

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


def _own_shift(session: SessionDep, user: User, shift_id: int) -> CourierShift:
    shift = session.get(CourierShift, shift_id)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("shift_not_found"))
    if shift.courier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_shift"))
    return shift


def _own_run(session: SessionDep, user: User, run_id: int) -> PickupRun:
    run = session.get(PickupRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("pickup_not_found"))
    if run.courier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_pickup"))
    return run


def _open_shift(session: SessionDep, user: User) -> CourierShift | None:
    return session.exec(
        select(CourierShift).where(
            CourierShift.courier_id == user.id,
            CourierShift.status == ShiftStatus.OPEN,
        )
    ).first()


def _cash_due(order: Order) -> int:
    """What to ask for at the door.

    Nothing on a card order — it is already paid, and asking again is the
    mistake this exists to prevent. The order's own total otherwise, which is
    the figure the customer agreed to including delivery.
    """
    if order.paid or order.payment_method is not PaymentMethod.CASH:
        return 0
    return order.total


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


def _shift_detail(session: SessionDep, shift: CourierShift) -> s.ShiftDetailOut:
    courier = session.get(User, shift.courier_id)
    rows = session.exec(
        select(DeliveryAttempt)
        .where(DeliveryAttempt.shift_id == shift.id)
        .order_by(col(DeliveryAttempt.happened_at))
    ).all()
    codes = {
        order.id: order.code
        for order in session.exec(
            select(Order).where(col(Order.id).in_([a.order_id for a in rows] or [-1]))
        ).all()
    }
    return s.ShiftDetailOut(
        **_shift_out(session, shift, courier).model_dump(),
        attempts=[
            s.DeliveryAttemptOut(
                id=a.id,
                order_id=a.order_id,
                order_code=codes.get(a.order_id, f"#{a.order_id}"),
                result=a.result,
                reason=a.reason,
                recipient_name=a.recipient_name,
                photo_url=sv.media_url(a.photo_url),
                cash_collected=a.cash_collected,
                happened_at=a.happened_at,
            )
            for a in rows
        ],
    )


def _shift_out(
    session: SessionDep, shift: CourierShift, courier: User | None = None
) -> s.ShiftOut:
    who = courier or session.get(User, shift.courier_id)
    return s.ShiftOut(
        id=shift.id,
        courier_id=shift.courier_id,
        courier_name=(who.full_name or who.phone) if who else f"#{shift.courier_id}",
        status=shift.status,
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
        cash_expected=shift.cash_expected,
        cash_declared=shift.cash_declared,
        cash_counted=shift.cash_counted,
        # Against what the doors add up to, not against what the courier
        # said: the courier's word is one of the claims being checked.
        difference=(
            None if shift.cash_counted is None else shift.cash_counted - shift.cash_expected
        ),
        counted_at=shift.counted_at,
        orders_delivered=shift.orders_delivered,
        orders_failed=shift.orders_failed,
        note=shift.note,
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
