"""Running the shop: the endpoints that move a status along.

Four flows had a status column the data model was happy to move and no way to
move it. A return request was submitted and never answered; a review sat in
moderation for ever; an order was placed and stayed placed however long ago
that was; a delivery window's capacity only ever went down. Each of those is
one operator decision away from working, and this is where the decisions live.

Two rules hold throughout:

* **The rules are in one place.** What may follow what is in
  ``app.transitions``, and an illegal move is a 409 — the request was fine, the
  state of the thing is not. The reply also carries ``next_statuses``, so the
  backoffice's buttons come from the same table rather than from a second copy
  of it.
* **The customer is told.** Every one of these flows exists because somebody
  is waiting for an answer, so each decision writes a notification. The
  customer's own response shapes are untouched — the apps are shipped.

Anything that touches money or a count writes to ``audit_log`` in the same
transaction as the change, so a disputed figure names a person and a moment.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n, inventory
from app import schemas as s
from app import services as sv
from app import transitions as tr
from app.deps import (
    OperatorUser,
    PickupHandler,
    SessionDep,
    WarehouseUser,
)
from app.models import (
    CourierShift,
    DeliverySlot,
    Notification,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    PickupLine,
    PickupRun,
    PickupRunStatus,
    Product,
    ReturnRequest,
    ReturnStatus,
    Review,
    ReviewStatus,
    ShiftStatus,
    User,
    UserRole,
)

# The courier's own shapes are rendered by the courier router. Imported rather
# than duplicated: two renderings of one shift would be two things to keep in
# step, and the operator is looking at exactly what the courier reported.
from app.routers import courier as courier_router

router = APIRouter(prefix="/staff", tags=["staff"])


# --------------------------------------------------------------------------- returns


@router.get(
    "/returns",
    response_model=list[s.StaffReturnOut],
    summary="Return requests waiting for a decision",
)
def list_returns(
    user: OperatorUser,
    session: SessionDep,
    status_filter: ReturnStatus | None = Query(
        None, alias="status", description="default: everything, oldest first"
    ),
) -> list[s.StaffReturnOut]:
    stmt = select(ReturnRequest)
    if status_filter is not None:
        stmt = stmt.where(ReturnRequest.status == status_filter)
    rows = session.exec(stmt.order_by(col(ReturnRequest.created_at))).all()
    return [_return_out(session, r) for r in rows]


@router.get("/returns/{return_id}", response_model=s.StaffReturnOut)
def get_return(return_id: int, user: OperatorUser, session: SessionDep) -> s.StaffReturnOut:
    return _return_out(session, _return(session, return_id))


@router.post(
    "/returns/{return_id}/approve",
    response_model=s.StaffReturnOut,
    summary="Accept a return — the money still has to follow",
)
def approve_return(
    return_id: int, payload: s.DecisionIn, user: OperatorUser, session: SessionDep
) -> s.StaffReturnOut:
    return _decide_return(session, user, return_id, ReturnStatus.APPROVED, payload)


@router.post(
    "/returns/{return_id}/reject",
    response_model=s.StaffReturnOut,
    summary="Refuse a return, with a reason the customer is given",
)
def reject_return(
    return_id: int, payload: s.DecisionIn, user: OperatorUser, session: SessionDep
) -> s.StaffReturnOut:
    if not payload.reason.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("reason_required"))
    return _decide_return(session, user, return_id, ReturnStatus.REJECTED, payload)


@router.post(
    "/returns/{return_id}/refund",
    response_model=s.StaffReturnOut,
    summary="Mark an approved return as paid back, and say where the goods went",
)
def refund_return(
    return_id: int, payload: s.RefundIn, user: OperatorUser, session: SessionDep
) -> s.StaffReturnOut:
    """``restock`` has no default on purpose.

    Returned goods are looked over before they go anywhere: what came back
    whole belongs on the shelf, and what came back damaged belongs in neither
    the shelf count nor a quiet gap in it. Whichever it is, somebody has to
    say so — a default here would be a count moving, or failing to move, by
    omission, which is the class of bug this whole area had.
    """
    return _decide_return(
        session, user, return_id, ReturnStatus.REFUNDED, payload, restock=payload.restock
    )


def _decide_return(
    session: SessionDep,
    actor: User,
    return_id: int,
    target: ReturnStatus,
    payload: s.DecisionIn,
    restock: bool = False,
) -> s.StaffReturnOut:
    request = _return(session, return_id)
    tr.ensure(tr.RETURN_TRANSITIONS, request.status, target)
    order = session.get(Order, request.order_id)
    was = request.status

    audit.record(
        session,
        actor=actor,
        action="return.status",
        entity="return_request",
        entity_id=request.id,
        field="status",
        old=was,
        new=target,
        note=payload.note or payload.reason,
    )

    amount = 0
    if target is ReturnStatus.REFUNDED:
        # What is actually being paid back: one line of the order when the
        # request named an item, the whole order when it did not. Recorded as
        # its own row — the status change says a refund happened, and this says
        # how much, which is the number anyone would later dispute — and kept
        # on the request too, where the customer can be shown it.
        lines = _returned_lines(session, request, order)
        amount = _refund_amount(request, order, lines)
        request.refund_amount = amount
        # When, not just how much. A settlement buckets a refund by the day it
        # was paid; with only ``created_at`` a refund granted in February
        # would land in January's account, and January may be closed.
        request.refunded_at = sv.utcnow()
        audit.record(
            session,
            actor=actor,
            action="return.refund",
            entity="order",
            entity_id=request.order_id,
            field="refund",
            old=None,
            new=amount,
            note=payload.note,
        )

        # Both answers are logged. "We put it back" and "we wrote it off" are
        # each a decision about stock, and an unrecorded write-off is
        # indistinguishable from stock going missing.
        audit.record(
            session,
            actor=actor,
            action="return.restock",
            entity="return_request",
            entity_id=request.id,
            field="restock",
            old=None,
            new=restock,
            note=payload.note or payload.reason,
        )
        if restock:
            inventory.restock_returned(
                session,
                lines,
                actor=actor,
                action="return.restock",
                note=payload.note,
            )

    request.status = target
    if target is ReturnStatus.REJECTED:
        request.resolution = payload.reason.strip()
    elif payload.note:
        request.resolution = payload.note.strip()
    session.add(request)

    code = order.code if order else ""
    if target is ReturnStatus.APPROVED:
        title, text = "return_approved", i18n.label("return_approved_note", code=code)
    elif target is ReturnStatus.REJECTED:
        title = "return_rejected"
        text = i18n.label("return_rejected_note", code=code, reason=request.resolution)
    else:
        title = "return_refunded"
        text = i18n.label("return_refunded_note", code=code, amount=sv.money(amount))
    session.add(
        Notification(
            user_id=request.user_id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=i18n.label(title),
            text=text,
            deep_link=f"minibozor://orders/{request.order_id}",
        )
    )

    session.commit()
    session.refresh(request)
    return _return_out(session, request)


def _returned_lines(
    session: SessionDep, request: ReturnRequest, order: Order | None
) -> list[OrderItem]:
    """What is coming back: the line the request named, or the whole order.

    The lines rather than a figure, because the same answer settles both
    questions a refund asks — how much money goes back, and which counts do.
    """
    if request.order_item_id:
        item = session.get(OrderItem, request.order_item_id)
        return [item] if item is not None else []
    return inventory.order_items(session, order) if order else []


def _refund_amount(
    request: ReturnRequest, order: Order | None, lines: list[OrderItem]
) -> int:
    """What goes back to the card, which is not the sum of what goes back on
    the shelf.

    A whole order coming back takes the delivery fee with it — the delivery is
    undone along with the sale. One line of an order coming back does not: the
    van still came, and the rest of the order is still in the customer's
    hands. So the figure is the order's total in the first case and the line's
    own total in the second, and neither is the subtotal of the goods.
    """
    if request.order_item_id:
        return sum(line.line_total for line in lines)
    return order.total if order else 0


# --------------------------------------------------------------------------- reviews


@router.get(
    "/reviews",
    response_model=list[s.StaffReviewOut],
    summary="The moderation queue",
)
def list_reviews_for_moderation(
    user: OperatorUser,
    session: SessionDep,
    status_filter: ReviewStatus | None = Query(
        ReviewStatus.MODERATING, alias="status", description="default: awaiting moderation"
    ),
) -> list[s.StaffReviewOut]:
    stmt = select(Review)
    if status_filter is not None:
        stmt = stmt.where(Review.status == status_filter)
    rows = session.exec(stmt.order_by(col(Review.created_at))).all()
    return [_review_out(session, r) for r in rows]


@router.post("/reviews/{review_id}/publish", response_model=s.StaffReviewOut)
def publish_review(
    review_id: int, payload: s.DecisionIn, user: OperatorUser, session: SessionDep
) -> s.StaffReviewOut:
    return _moderate(session, user, review_id, ReviewStatus.PUBLISHED, payload)


@router.post(
    "/reviews/{review_id}/reject",
    response_model=s.StaffReviewOut,
    summary="Keep a review off the product page, with a reason",
)
def reject_review(
    review_id: int, payload: s.DecisionIn, user: OperatorUser, session: SessionDep
) -> s.StaffReviewOut:
    if not payload.reason.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("reason_required"))
    return _moderate(session, user, review_id, ReviewStatus.REJECTED, payload)


def _moderate(
    session: SessionDep,
    actor: User,
    review_id: int,
    target: ReviewStatus,
    payload: s.DecisionIn,
) -> s.StaffReviewOut:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("review_not_found"))
    tr.ensure(tr.REVIEW_TRANSITIONS, review.status, target)

    audit.record(
        session,
        actor=actor,
        action="review.status",
        entity="review",
        entity_id=review.id,
        field="status",
        old=review.status,
        new=target,
        note=payload.note or payload.reason,
    )
    review.status = target
    session.add(review)
    session.commit()

    # The product's rating counts published reviews only, so moderating one is
    # what makes it count — or stop counting.
    sv.recalc_product_rating(session, review.product_id)

    product = session.get(Product, review.product_id)
    title = "review_published" if target is ReviewStatus.PUBLISHED else "review_rejected"
    text = (
        i18n.label("review_published_note", product=product.title if product else "")
        if target is ReviewStatus.PUBLISHED
        else i18n.label(
            "review_rejected_note",
            product=product.title if product else "",
            reason=payload.reason.strip(),
        )
    )
    session.add(
        Notification(
            user_id=review.user_id,
            kind=NotificationKind.REVIEW,
            icon="star",
            title=i18n.label(title),
            text=text,
            deep_link=f"minibozor://products/{review.product_id}",
        )
    )
    session.commit()
    session.refresh(review)
    return _review_out(session, review)


# --------------------------------------------------------------------------- orders


@router.get(
    "/orders",
    response_model=s.Page[s.StaffOrderOut],
    summary="The order queue",
)
def order_queue(
    user: OperatorUser,
    session: SessionDep,
    status_filter: OrderStatus | None = Query(
        None, alias="status", description="default: everything, oldest first"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> s.Page[s.StaffOrderOut]:
    stmt = select(Order)
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    # Oldest first: a queue is worked from the front, which is the opposite of
    # how the customer's own list is sorted.
    rows = session.exec(
        stmt.order_by(col(Order.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.StaffOrderOut](
        items=[_order_row(session, o) for o in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get(
    "/orders/{order_id}",
    response_model=s.OrderOut,
    summary="One order in full — the customer's own view of it",
)
def get_order(order_id: int, user: OperatorUser, session: SessionDep) -> s.OrderOut:
    # Deliberately the customer's shape: an operator on the phone is being
    # asked about what the customer is looking at, and a second rendering of
    # the same order is a second thing to keep in step.
    return sv.order_out(session, _order(session, order_id))


@router.post(
    "/orders/{order_id}/status",
    response_model=s.OrderOut,
    summary="Move an order along",
)
def set_order_status(
    order_id: int, payload: s.OrderStatusIn, user: OperatorUser, session: SessionDep
) -> s.OrderOut:
    order = _order(session, order_id)
    tr.ensure(tr.ORDER_TRANSITIONS, order.status, payload.status)
    was = order.status

    audit.record(
        session,
        actor=user,
        action="order.status",
        entity="order",
        entity_id=order.id,
        field="status",
        old=was,
        new=payload.status,
        note=payload.note,
    )

    if payload.status is OrderStatus.CANCELLED:
        order.cancel_reason = payload.note or order.cancel_reason
        # The same four counts the customer's own cancel button puts back, by
        # the same function. Two cancel paths with one restore between them is
        # the whole point — the operator's used to put nothing back at all.
        inventory.restore_order(
            session,
            order,
            actor=user,
            action="order.cancel",
            note=payload.note,
            shelf=order.paid,
        )
    if payload.status is OrderStatus.DELIVERED and not order.paid:
        # Cash at the door. The goods were held for this order from the moment
        # it was placed; this is the moment they actually leave, because this
        # is the moment it becomes a sale.
        order.paid = True
        for line in inventory.order_items(session, order):
            inventory.sell(session, line)

    # Returning an order does not restock it here: whether the goods go back on
    # the shelf is decided when the refund is made, and doing it in both places
    # would put them back twice.

    order.status = payload.status
    order.updated_at = sv.utcnow()
    session.add(order)

    # The app draws its timeline from these rows, so the move is only really
    # made once the timeline says so.
    sv.stamp_order_event(session, order, note=payload.note)

    session.add(
        Notification(
            user_id=order.user_id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=i18n.label(f"event_{payload.status.value}"),
            text=i18n.label(f"order_{payload.status.value}_note", code=order.code),
            deep_link=f"minibozor://orders/{order.id}",
        )
    )
    session.commit()
    session.refresh(order)
    return sv.order_out(session, order)


# --------------------------------------------------------------------- the last mile

# The operator's half of the courier module. Three things belong here rather
# than in ``courier.py`` because they are decisions a courier must not make
# about their own work: who carries what, which returns get a van, and what
# the office counted when the cash came back.


@router.get(
    "/couriers",
    response_model=list[s.StaffUserOut],
    summary="Who is available to carry things",
)
def list_couriers(user: OperatorUser, session: SessionDep) -> list[s.StaffUserOut]:
    rows = session.exec(
        select(User)
        .where(User.role == UserRole.COURIER, col(User.is_active).is_(True))
        .order_by(col(User.full_name), col(User.phone))
    ).all()
    return [
        s.StaffUserOut(
            id=row.id,
            phone=row.phone,
            full_name=row.full_name,
            role=row.role,
            is_active=row.is_active,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post(
    "/orders/{order_id}/courier",
    response_model=s.OrderOut,
    summary="Put an order on somebody's round",
)
def assign_courier(
    order_id: int,
    payload: s.CourierAssignIn,
    user: OperatorUser,
    session: SessionDep,
) -> s.OrderOut:
    """The operator plans the round; the courier drives it.

    Allowed while the order has not finished — a round is usually planned
    before anything is packed, and reassigning a stop mid-afternoon is
    ordinary work rather than an exception. Refused once the order is
    delivered, cancelled or returned: there is nothing left to carry, and
    changing the name on a finished delivery would rewrite who did it.

    Logged, because "who was carrying it" is the first question asked about a
    delivery that went wrong.
    """
    order = _order(session, order_id)
    if order.status in (
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.RETURNED,
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_finished"))

    courier = session.get(User, payload.courier_id)
    if courier is None or courier.role is not UserRole.COURIER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("courier_not_found"))
    if not courier.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("courier_inactive"))

    audit.record(
        session,
        actor=user,
        action="order.courier",
        entity="order",
        entity_id=order.id,
        field="courier_id",
        old=order.courier_id,
        new=courier.id,
        note=payload.note or (courier.full_name or courier.phone),
    )
    order.courier_id = courier.id
    order.courier_sequence = payload.sequence
    order.updated_at = sv.utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    return sv.order_out(session, order)


@router.get(
    "/shifts",
    response_model=list[s.ShiftOut],
    summary="Rounds, and whether the cash added up",
)
def list_shifts(
    user: OperatorUser,
    session: SessionDep,
    courier_id: int | None = Query(None),
    status_filter: ShiftStatus | None = Query(None, alias="status"),
) -> list[s.ShiftOut]:
    stmt = select(CourierShift)
    if courier_id is not None:
        stmt = stmt.where(CourierShift.courier_id == courier_id)
    if status_filter is not None:
        stmt = stmt.where(CourierShift.status == status_filter)
    rows = session.exec(stmt.order_by(col(CourierShift.id).desc())).all()
    return [courier_router._shift_out(session, row) for row in rows]


@router.get(
    "/shifts/{shift_id}",
    response_model=s.ShiftDetailOut,
    summary="One round, door by door",
)
def get_shift(
    shift_id: int, user: OperatorUser, session: SessionDep
) -> s.ShiftDetailOut:
    """Every attempt on the shift, so the cash total is followable.

    The same reason a statement carries its lines: a courier told they are
    30 000 short has a number to argue with, and a list of doors with a figure
    against each one is something to check.
    """
    shift = session.get(CourierShift, shift_id)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("shift_not_found"))
    return courier_router._shift_detail(session, shift)


@router.post(
    "/shifts/{shift_id}/count",
    response_model=s.ShiftDetailOut,
    summary="What the office counted",
)
def count_shift(
    shift_id: int,
    payload: s.ShiftCountIn,
    user: OperatorUser,
    session: SessionDep,
) -> s.ShiftDetailOut:
    """The third figure, and the only one that settles anything.

    Counted against ``cash_expected`` rather than against what the courier
    declared: the declaration is one of the claims being checked, so checking
    it against itself would always agree. A difference is recorded as it is
    and never reconciled away — an unexplained shortfall is a fact about a
    day, and the audit row is what makes it findable a month later.
    """
    shift = session.get(CourierShift, shift_id)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("shift_not_found"))
    if shift.status is not ShiftStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("shift_open"))
    if shift.cash_counted is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("shift_counted"))

    gap = payload.cash_counted - shift.cash_expected
    audit.record(
        session,
        actor=user,
        action="shift.count",
        entity="courier_shift",
        entity_id=shift.id,
        field="cash_counted",
        old=shift.cash_expected,
        new=payload.cash_counted,
        note=payload.note or (f"farq {gap}" if gap else "farq yo'q"),
    )
    shift.cash_counted = payload.cash_counted
    shift.counted_by_id = user.id
    shift.counted_at = sv.utcnow()
    if payload.note:
        shift.note = payload.note.strip()
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return courier_router._shift_detail(session, shift)


# --------------------------------------------------------------------- collection runs


@router.post(
    "/pickups",
    response_model=s.PickupRunOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send a van for approved returns",
)
def create_pickup(
    payload: s.PickupCreateIn, user: OperatorUser, session: SessionDep
) -> s.PickupRunOut:
    """Only approved requests go on a run.

    A request still being decided is not something to send a van for, and a
    refused one has nothing to collect. A request already on an open run is
    refused too — two vans for one parcel is one wasted trip and a courier
    told the goods are gone.
    """
    courier = session.get(User, payload.courier_id)
    if courier is None or courier.role is not UserRole.COURIER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("courier_not_found"))

    requests: list[ReturnRequest] = []
    for request_id in dict.fromkeys(payload.return_request_ids):
        request = session.get(ReturnRequest, request_id)
        if request is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, i18n.label("return_not_found")
            )
        if request.status is not ReturnStatus.APPROVED:
            raise HTTPException(
                status.HTTP_409_CONFLICT, i18n.label("return_not_approved")
            )
        already = session.exec(
            select(PickupLine)
            .join(PickupRun, col(PickupLine.run_id) == col(PickupRun.id))
            .where(
                PickupLine.return_request_id == request.id,
                col(PickupRun.status).in_(
                    [PickupRunStatus.OPEN, PickupRunStatus.COLLECTED]
                ),
            )
        ).first()
        if already is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, i18n.label("return_already_on_a_run")
            )
        requests.append(request)

    run = PickupRun(
        code=_next_pickup_code(session),
        courier_id=courier.id,
        note=payload.note.strip(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    for request in requests:
        session.add(PickupLine(run_id=run.id, return_request_id=request.id))

    audit.record(
        session,
        actor=user,
        action="pickup.create",
        entity="pickup_run",
        entity_id=run.id,
        field="courier_id",
        old=None,
        new=courier.id,
        note=f"{run.code} · {len(requests)} ariza",
    )
    session.commit()
    session.refresh(run)
    return courier_router._run_out(session, run)


@router.get(
    "/pickups",
    response_model=list[s.PickupRunOut],
    summary="Collection runs, out and back",
)
def list_pickups(
    user: PickupHandler,
    session: SessionDep,
    status_filter: PickupRunStatus | None = Query(None, alias="status"),
) -> list[s.PickupRunOut]:
    """Read by the warehouse as well as the operator: the goods arrive at a
    desk, and the person at that desk needs to know what is coming."""
    stmt = select(PickupRun)
    if user.role is UserRole.COURIER:
        stmt = stmt.where(PickupRun.courier_id == user.id)
    if status_filter is not None:
        stmt = stmt.where(PickupRun.status == status_filter)
    rows = session.exec(stmt.order_by(col(PickupRun.id).desc())).all()
    return [courier_router._run_out(session, row) for row in rows]


@router.post(
    "/pickups/{run_id}/receive",
    response_model=s.PickupRunOut,
    summary="The warehouse has the goods",
)
def receive_pickup(
    run_id: int, user: WarehouseUser, session: SessionDep
) -> s.PickupRunOut:
    """Booked in, and deliberately not put on a shelf.

    Whether returned goods are sellable is the refund's decision — an operator
    inspects and says restock or write off, and ``inventory.restock_returned``
    is called from there. Doing it here as well would put the same shirt back
    twice, which is the mistake the existing comment in ``operations`` about
    returns already warns about.

    So this records arrival and nothing else. The run answers where the goods
    are; the refund answers whether they count.
    """
    run = session.get(PickupRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("pickup_not_found"))
    tr.ensure(tr.PICKUP_TRANSITIONS, run.status, PickupRunStatus.RECEIVED)

    got = session.exec(
        select(func.count())
        .select_from(PickupLine)
        .where(PickupLine.run_id == run.id, col(PickupLine.collected).is_(True))
    ).one()
    audit.record(
        session,
        actor=user,
        action="pickup.receive",
        entity="pickup_run",
        entity_id=run.id,
        field="status",
        old=PickupRunStatus.COLLECTED,
        new=PickupRunStatus.RECEIVED,
        note=f"{run.code} · {int(got)} dona qabul qilindi",
    )
    run.status = PickupRunStatus.RECEIVED
    run.received_at = sv.utcnow()
    run.received_by_id = user.id
    session.add(run)
    session.commit()
    session.refresh(run)
    return courier_router._run_out(session, run)


def _next_pickup_code(session: SessionDep) -> str:
    last = session.exec(select(func.count()).select_from(PickupRun)).one()
    return f"PCK-{int(last) + 1:06d}"


# --------------------------------------------------------------------- delivery windows


@router.get(
    "/delivery/slots",
    response_model=list[s.StaffSlotOut],
    summary="Every window in a date range, full ones included",
)
def list_slots(
    user: OperatorUser,
    session: SessionDep,
    from_day: date | None = Query(None, description="default: today"),
    to_day: date | None = Query(None, description="default: a fortnight out"),
) -> list[s.StaffSlotOut]:
    start = from_day or date.today()
    end = to_day or start + timedelta(days=14)
    rows = session.exec(
        select(DeliverySlot)
        .where(DeliverySlot.day >= start, DeliverySlot.day <= end)
        .order_by(col(DeliverySlot.day), col(DeliverySlot.start_time))
    ).all()
    # Unlike the customer's list this keeps the windows that have sold out and
    # the ones whose hour has passed: a window nobody can choose is exactly
    # what an operator is looking for.
    return [_slot_out(sl) for sl in rows]


@router.post(
    "/delivery/slots",
    response_model=list[s.StaffSlotOut],
    status_code=status.HTTP_201_CREATED,
    summary="Open windows across a range of days",
)
def create_slots(
    payload: s.SlotCreateIn, user: OperatorUser, session: SessionDep
) -> list[s.StaffSlotOut]:
    created: list[DeliverySlot] = []
    for day in sorted(set(payload.days)):
        existing = {
            (row.start_time, row.end_time)
            for row in session.exec(
                select(DeliverySlot).where(DeliverySlot.day == day)
            ).all()
        }
        for window in payload.windows:
            if (window.start_time, window.end_time) in existing:
                continue
            slot = DeliverySlot(
                day=day,
                start_time=window.start_time,
                end_time=window.end_time,
                note=window.note,
                price=window.price,
                express=window.express,
                capacity_left=window.capacity,
            )
            session.add(slot)
            created.append(slot)
            existing.add((window.start_time, window.end_time))

    session.commit()
    for slot in created:
        session.refresh(slot)
        audit.record(
            session,
            actor=user,
            action="slot.create",
            entity="delivery_slot",
            entity_id=slot.id,
            field="capacity_left",
            old=None,
            new=slot.capacity_left,
            note=f"{slot.day} {slot.start_time}–{slot.end_time}",
        )
    session.commit()
    return [_slot_out(sl) for sl in created]


@router.patch(
    "/delivery/slots/{slot_id}",
    response_model=s.StaffSlotOut,
    summary="Change a window's capacity or its surcharge",
)
def update_slot(
    slot_id: int, payload: s.SlotUpdateIn, user: OperatorUser, session: SessionDep
) -> s.StaffSlotOut:
    slot = session.get(DeliverySlot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("slot_not_found"))

    # Capacity is how many orders may still be promised this window, and the
    # surcharge is money on every one of them. Both are logged; the note and
    # the express flag are wording and are not.
    for field, new in (("capacity_left", payload.capacity_left), ("price", payload.price)):
        if new is None or new == getattr(slot, field):
            continue
        audit.record(
            session,
            actor=user,
            action=f"slot.{field}",
            entity="delivery_slot",
            entity_id=slot.id,
            field=field,
            old=getattr(slot, field),
            new=new,
        )
        setattr(slot, field, new)

    if payload.note is not None:
        slot.note = payload.note
    if payload.express is not None:
        slot.express = payload.express

    session.add(slot)
    session.commit()
    session.refresh(slot)
    return _slot_out(slot)


# --------------------------------------------------------------------------- helpers


def _return(session: SessionDep, return_id: int) -> ReturnRequest:
    request = session.get(ReturnRequest, return_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("return_not_found"))
    return request


def _order(session: SessionDep, order_id: int) -> Order:
    """Any order, not only one's own — there is no owner check on this side."""
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("order_not_found"))
    return order


def _return_out(session: SessionDep, r: ReturnRequest) -> s.StaffReturnOut:
    order = session.get(Order, r.order_id)
    customer = session.get(User, r.user_id)
    return s.StaffReturnOut(
        id=r.id,
        order_id=r.order_id,
        order_code=order.code if order else "",
        order_item_id=r.order_item_id,
        customer_name=customer.full_name if customer else "",
        customer_phone=customer.phone if customer else "",
        reason=r.reason,
        comment=r.comment,
        photos=[u for u in (sv.media_url(p) for p in (r.photos or [])) if u],
        status=r.status,
        resolution=r.resolution,
        refund_amount=r.refund_amount,
        next_statuses=tr.next_states(tr.RETURN_TRANSITIONS, r.status),
        created_at=r.created_at,
    )


def _review_out(session: SessionDep, r: Review) -> s.StaffReviewOut:
    product = session.get(Product, r.product_id)
    author = session.get(User, r.user_id)
    return s.StaffReviewOut(
        id=r.id,
        product_id=r.product_id,
        product_title=product.title if product else "",
        # The full name, not the initial the product page shows: moderation is
        # about the person as much as the words.
        author_name=author.full_name if author else "",
        author_phone=author.phone if author else "",
        rating=r.rating,
        text=r.text,
        photos=[u for u in (sv.media_url(p) for p in (r.photos or [])) if u],
        status=r.status,
        next_statuses=tr.next_states(tr.REVIEW_TRANSITIONS, r.status),
        created_at=r.created_at,
    )


def _order_row(session: SessionDep, o: Order) -> s.StaffOrderOut:
    customer = session.get(User, o.user_id)
    items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    window = (
        f"{o.delivery_start}–{o.delivery_end}" if o.delivery_start and o.delivery_end else ""
    )
    return s.StaffOrderOut(
        id=o.id,
        code=o.code,
        status=o.status,
        status_label=sv.order_status_label(o.status),
        customer_name=o.recipient_name or (customer.full_name if customer else ""),
        customer_phone=o.recipient_phone or (customer.phone if customer else ""),
        delivery_kind=o.delivery_kind,
        address_line=o.address_line,
        delivery_day=o.delivery_day,
        delivery_window=window,
        items_count=sum(i.quantity for i in items),
        total=o.total,
        paid=o.paid,
        next_statuses=tr.next_states(tr.ORDER_TRANSITIONS, o.status),
        created_at=o.created_at,
    )


def _slot_out(sl: DeliverySlot) -> s.StaffSlotOut:
    return s.StaffSlotOut(
        id=sl.id,
        day=sl.day,
        start_time=sl.start_time,
        end_time=sl.end_time,
        note=sl.note,
        price=sl.price,
        express=sl.express,
        capacity_left=sl.capacity_left,
    )
