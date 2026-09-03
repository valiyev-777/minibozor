from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import i18n
from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import (
    Address,
    CancelReason,
    DeliverySlot,
    Notification,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    PaymentCard,
    PaymentMethod,
    PickupPoint,
    Product,
    ReturnReason,
    ReturnRequest,
)

router = APIRouter(tags=["orders"])


# --------------------------------------------------------------------------- checkout


@router.post(
    "/checkout/preview",
    response_model=s.CheckoutPreviewOut,
    summary="Screens 19, 23 — review before paying",
)
def checkout_preview(
    payload: s.CheckoutIn, user: CurrentUser, session: SessionDep
) -> s.CheckoutPreviewOut:
    cart = sv.build_cart(session, user, payload.promo_code)
    selected = [i for i in cart.items if i.selected and i.in_stock]
    if not selected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("cart_empty"))

    address = _resolve_address(session, user.id, payload.address_id)
    pickup = session.get(PickupPoint, payload.pickup_point_id) if payload.pickup_point_id else None
    slot = session.get(DeliverySlot, payload.slot_id) if payload.slot_id else None
    card = _resolve_card(session, user.id, payload.payment_card_id, payload.payment_method)

    # A slot's price is a surcharge — the picker shows it as "+9 000" — so it
    # adds to the standard fee rather than replacing it. Replacing it made every
    # daytime slot, priced at nothing, deliver the whole order free.
    delivery_fee = 0 if pickup else cart.totals.delivery_fee + (slot.price if slot else 0)
    totals = sv.cart_totals(
        selected,
        discount=cart.totals.discount,
        promo_code=cart.totals.promo_code,
        delivery_fee=delivery_fee,
    )

    return s.CheckoutPreviewOut(
        items=selected,
        address=sv.address_out(address) if address else None,
        pickup_point=sv.pickup_out(pickup) if pickup else None,
        slot=sv.slot_out(slot) if slot else None,
        card=sv.card_out(card) if card else None,
        totals=totals,
    )


@router.post(
    "/orders",
    response_model=s.OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Screen 24 — place the order",
)
def create_order(payload: s.CheckoutIn, user: CurrentUser, session: SessionDep) -> s.OrderOut:
    preview = checkout_preview(payload, user, session)

    if payload.pickup_point_id is None and preview.address is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Yetkazish manzilini tanlang")

    slot = session.get(DeliverySlot, payload.slot_id) if payload.slot_id else None
    card = _resolve_card(session, user.id, payload.payment_card_id, payload.payment_method)

    if preview.address:
        address_line, address_meta = preview.address.line, preview.address.meta
    elif preview.pickup_point:
        address_line, address_meta = preview.pickup_point.name, preview.pickup_point.address
    else:
        address_line = address_meta = ""

    order = Order(
        code=sv.next_order_code(session),
        user_id=user.id,
        status=OrderStatus.PLACED,
        delivery_kind="pickup" if payload.pickup_point_id else "courier",
        address_line=address_line,
        address_meta=address_meta,
        pickup_point_id=payload.pickup_point_id,
        delivery_day=slot.day if slot else None,
        delivery_start=slot.start_time if slot else None,
        delivery_end=slot.end_time if slot else None,
        payment_method=payload.payment_method,
        payment_card_id=card.id if card else None,
        paid=payload.payment_method == PaymentMethod.CARD,
        recipient_name=payload.recipient_name or user.full_name,
        recipient_phone=payload.recipient_phone or user.phone,
        subtotal=preview.totals.subtotal,
        delivery_fee=preview.totals.delivery_fee,
        discount=preview.totals.discount,
        total=preview.totals.total,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for item in preview.items:
        product = session.get(Product, item.product_id)
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                title=item.title,
                image_url=_raw_image(session, item.product_id),
                variant_label=item.variant_label,
                unit_price=item.unit_price,
                quantity=item.quantity,
            )
        )
        if product:
            product.sold_count += item.quantity
            # What is left, kept in step with what has gone. The sold count was
            # being raised here already and the stock beside it was not, so a
            # product could be bought any number of times and still claim the
            # same 25 remaining — and never fall out of stock on its own.
            product.stock_left = max(0, product.stock_left - item.quantity)
            if product.stock_left == 0:
                product.in_stock = False
            session.add(product)

    sv.seed_order_events(session, order)

    # Clear only what was actually bought.
    for cart_item in sv.cart_items(session, user):
        if cart_item.selected:
            session.delete(cart_item)

    if slot and slot.capacity_left > 0:
        slot.capacity_left -= 1
        session.add(slot)

    session.add(
        Notification(
            user_id=user.id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=i18n.label("order_placed"),
            text=i18n.label("order_placed_note", code=order.code),
            deep_link=f"minibozor://orders/{order.id}",
        )
    )
    session.commit()
    session.refresh(order)
    return sv.order_out(session, order)


# --------------------------------------------------------------------------- orders


@router.get("/orders", response_model=s.Page[s.OrderSummaryOut], summary="Screen 26 — my orders")
def list_orders(
    user: CurrentUser,
    session: SessionDep,
    active: bool | None = Query(None, description="true = in progress, false = finished"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=60),
) -> s.Page[s.OrderSummaryOut]:
    stmt = select(Order).where(Order.user_id == user.id)
    if active is True:
        stmt = stmt.where(
            col(Order.status).in_([OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED])
        )
    elif active is False:
        stmt = stmt.where(
            col(Order.status).in_(
                [OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.RETURNED]
            )
        )
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(Order.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.OrderSummaryOut](
        items=[sv.order_summary(session, o) for o in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get("/orders/reasons/cancel", response_model=list[s.ReasonOut])
def cancel_reasons(session: SessionDep) -> list[s.ReasonOut]:
    rows = session.exec(select(CancelReason).order_by(col(CancelReason.sort))).all()
    return [
        s.ReasonOut(
            id=r.id,
            label=i18n.t(session, "cancel_reason", r.id, "label", r.label),
            requires_comment=r.requires_comment,
        )
        for r in rows
    ]


@router.get("/orders/reasons/return", response_model=list[s.ReasonOut])
def return_reasons(session: SessionDep) -> list[s.ReasonOut]:
    rows = session.exec(select(ReturnReason).order_by(col(ReturnReason.sort))).all()
    return [
        s.ReasonOut(
            id=r.id,
            label=i18n.t(session, "return_reason", r.id, "label", r.label),
            requires_comment=r.requires_comment,
        )
        for r in rows
    ]


@router.get("/orders/{order_id}", response_model=s.OrderOut, summary="Screens 25, 27 — one order")
def get_order(order_id: int, user: CurrentUser, session: SessionDep) -> s.OrderOut:
    return sv.order_out(session, _owned_order(session, user.id, order_id))


@router.post(
    "/orders/{order_id}/cancel",
    response_model=s.OrderOut,
    summary="Screen 28 — cancel an order",
)
def cancel_order(
    order_id: int, payload: s.CancelIn, user: CurrentUser, session: SessionDep
) -> s.OrderOut:
    order = _owned_order(session, user.id, order_id)
    if order.status not in (OrderStatus.PLACED, OrderStatus.PACKING):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_not_cancellable"))

    reason = payload.reason
    if payload.reason_id:
        row = session.get(CancelReason, payload.reason_id)
        reason = row.label if row else reason

    order.status = OrderStatus.CANCELLED
    order.cancel_reason = " · ".join(x for x in (reason, payload.comment) if x)
    order.updated_at = sv.utcnow()
    session.add(order)
    session.add(
        Notification(
            user_id=user.id,
            kind=NotificationKind.ORDER,
            icon="box",
            title=i18n.label("order_cancelled"),
            text=i18n.label("order_cancelled_note", code=order.code),
            deep_link=f"minibozor://orders/{order.id}",
        )
    )
    session.commit()
    session.refresh(order)
    return sv.order_out(session, order)


@router.post(
    "/orders/{order_id}/return",
    response_model=s.ReturnOut,
    status_code=status.HTTP_201_CREATED,
    summary="Screen 29 — return request",
)
def request_return(
    order_id: int, payload: s.ReturnIn, user: CurrentUser, session: SessionDep
) -> s.ReturnOut:
    order = _owned_order(session, user.id, order_id)
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("return_delivered_only")
        )

    reason = payload.reason
    if payload.reason_id:
        row = session.get(ReturnReason, payload.reason_id)
        reason = row.label if row else reason

    request = ReturnRequest(
        user_id=user.id,
        order_id=order.id,
        order_item_id=payload.order_item_id,
        reason=reason,
        comment=payload.comment,
        photos=payload.photos,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return s.ReturnOut(
        id=request.id,
        order_code=order.code,
        reason=request.reason,
        comment=request.comment,
        status=request.status,
        created_at=request.created_at,
    )


@router.get("/returns", response_model=list[s.ReturnOut])
def list_returns(user: CurrentUser, session: SessionDep) -> list[s.ReturnOut]:
    rows = session.exec(
        select(ReturnRequest)
        .where(ReturnRequest.user_id == user.id)
        .order_by(col(ReturnRequest.created_at).desc())
    ).all()
    out = []
    for r in rows:
        order = session.get(Order, r.order_id)
        out.append(
            s.ReturnOut(
                id=r.id,
                order_code=order.code if order else "",
                reason=r.reason,
                comment=r.comment,
                status=r.status,
                created_at=r.created_at,
            )
        )
    return out


# --------------------------------------------------------------------------- helpers


def _owned_order(session: SessionDep, user_id: int, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("order_not_found"))
    return order


def _resolve_address(session: SessionDep, user_id: int, address_id: int | None) -> Address | None:
    if address_id is not None:
        address = session.get(Address, address_id)
        if address is None or address.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("address_not_found"))
        return address
    return session.exec(
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(col(Address.is_default).desc(), col(Address.created_at))
    ).first()


def _resolve_card(
    session: SessionDep, user_id: int, card_id: int | None, method: PaymentMethod
) -> PaymentCard | None:
    if method == PaymentMethod.CASH:
        return None
    if card_id is not None:
        card = session.get(PaymentCard, card_id)
        if card is None or card.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("card_not_found"))
        return card
    return session.exec(
        select(PaymentCard)
        .where(PaymentCard.user_id == user_id)
        .order_by(col(PaymentCard.is_default).desc())
    ).first()


def _raw_image(session: SessionDep, product_id: int | None) -> str:
    """Store the relative path in the snapshot so the media host can change."""
    if product_id is None:
        return ""
    from app.models import ProductImage

    img = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(col(ProductImage.sort))
    ).first()
    return img.url if img else ""
