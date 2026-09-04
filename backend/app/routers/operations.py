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
from app.deps import OperatorUser, SessionDep
from app.models import (
    DeliverySlot,
    Notification,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ReturnRequest,
    ReturnStatus,
    Review,
    ReviewStatus,
    User,
)

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
        )
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
