from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import i18n, inventory
from app import payments
from app import products as pr
from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import (
    Address,
    CancelReason,
    CardStatus,
    CartItem,
    DeliverySlot,
    Notification,
    NotificationKind,
    Order,
    OrderItem,
    OrderStatus,
    PaymentCard,
    PaymentMethod,
    PickupPoint,
    ProductImage,
    ProductVariant,
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
        totals=totals,
        # Read here so the confirm screen can print "•• 9012" before anybody
        # presses anything. Resolved rather than trusted: a card id from a
        # client is a card id somebody else's client could have sent.
        card=(
            sv.card_out(_card(session, user.id, payload.payment_card_id))
            if payload.payment_method is PaymentMethod.CARD
            and payload.payment_card_id is not None
            else None
        ),
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
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("address_required")
        )

    slot = session.get(DeliverySlot, payload.slot_id) if payload.slot_id else None

    if preview.address:
        address_line, address_meta = preview.address.line, preview.address.meta
    elif preview.pickup_point:
        address_line, address_meta = preview.pickup_point.name, preview.pickup_point.address
    else:
        address_line = address_meta = ""

    # The money, before the order.
    #
    # ``paid`` used to be `payment_method == CARD` — a card order was written
    # down as paid at the moment it was placed and nothing was ever charged.
    # The whole shop believed it: ``courier._cash_due`` asks for nothing at
    # the door on a card order "because it is already paid", so a shopper
    # could tap Karta and take delivery of goods nobody was ever paid for.
    #
    # So the charge happens here and the order is written only if it goes
    # through. That ordering is the customer's too — they are paying for a
    # basket, not settling an invoice for something already promised — and it
    # means a refusal leaves nothing behind: no order to cancel, no counts to
    # put back, no row for the owner to explain.
    #
    # 402 rather than 400: the request is right and the card is real, and what
    # went wrong is the payment. The reason is the processor's, in the
    # customer's language, because "another card", "more money" and "this card
    # has expired" are three different things to go and do.
    charge = payments.Charge(ok=True)
    if payload.payment_method is PaymentMethod.CARD:
        if payload.payment_card_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("card_required")
            )
        card = _card(session, user.id, payload.payment_card_id)
        charge = payments.charge(card, preview.totals.total)
        if not charge.ok:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED, i18n.label(charge.reason)
            )

    order = Order(
        code=sv.next_order_code(session),
        user_id=user.id,
        status=OrderStatus.PLACED,
        delivery_kind="pickup" if payload.pickup_point_id else "courier",
        address_line=address_line,
        address_meta=address_meta,
        pickup_point_id=payload.pickup_point_id,
        slot_id=slot.id if slot else None,
        delivery_day=slot.day if slot else None,
        delivery_start=slot.start_time if slot else None,
        delivery_end=slot.end_time if slot else None,
        payment_method=payload.payment_method,
        # Paid because it was, not because of which button was pressed. Cash
        # is settled at the door by the courier, and stays false until then.
        paid=charge.ok and payload.payment_method is PaymentMethod.CARD,
        payment_reference=charge.reference,
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

    # Every product this order touched. The cached figure is the shelf less
    # what is held, and both sides of that move here — the goods leave the
    # shelf and the basket line that was holding them is deleted — so the
    # figure is recomputed once at the end rather than halfway through, when
    # it would count the same three items as both sold and still held.
    touched: set[int] = set()

    for item in preview.items:
        # The cart line is about to be deleted, so which colour and which size
        # were chosen is copied onto the order line first. Not for display —
        # ``variant_label`` already reads well — but so that a cancellation
        # later knows which counts to put back.
        cart_item = session.get(CartItem, item.id)
        # What the shop paid for this cell's newest lot, frozen beside what it
        # is charging. Snapshotted for the same reason the price is: the next
        # market run moves the cost and this order must not move with it.
        # Nought when nothing was ever booked in with a price — which is every
        # order placed before the column existed — and nought means unknown,
        # so the reports count the line's units as uncosted rather than
        # claiming the whole price as margin.
        bought = (
            session.get(ProductVariant, cart_item.variant_id)
            if cart_item and cart_item.variant_id
            else None
        )
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            title=item.title,
            # The colour's photograph, snapshotted like everything else on the
            # line: a customer opening this order in six months should see the
            # thing they bought, not whatever the card's cover is by then.
            image_url=_colour_or_cover(
                session,
                cart_item.variant_id if cart_item else None,
                item.product_id,
            ),
            variant_id=cart_item.variant_id if cart_item else None,
            colour=item.colour,
            size=item.size,
            variant_label=item.variant_label,
            unit_price=item.unit_price,
            unit_cost=bought.last_cost if bought else 0,
            quantity=item.quantity,
        )
        session.add(order_item)
        # Nothing moves in the room. Paying for something does not fetch it
        # off a shelf — a courier does, at a door — so the goods are held for
        # this order and stand where they stand until somebody picks them.
        # ``app.stock.reserved`` reads the hold off the order itself.
        if order_item.product_id is not None:
            touched.add(order_item.product_id)
        inventory.take(session, order_item)

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
    for product_id in touched:
        pr.refresh(session, product_id)
    if touched:
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

    order.cancel_reason = " · ".join(x for x in (reason, payload.comment) if x)
    # Before the status changes, because that is what makes this reachable
    # once. Nothing of a cancelled order happened: the goods are on the shelf,
    # they were never sold, and the delivery window is free again.
    inventory.restore_order(
        session,
        order,
        actor=user,
        action="order.cancel",
        note=order.cancel_reason,
    )
    order.status = OrderStatus.CANCELLED
    order.updated_at = sv.utcnow()
    session.add(order)
    # The same stamp the operator's cancel writes.
    #
    # It was missing here, and the two cancel paths therefore left different
    # evidence: an operator cancelling wrote a `cancelled` event and a customer
    # pressing the button in the app wrote none at all. So the timeline the app
    # draws stopped at "placed" for the customer's own cancellation, and
    # anything counting cancellations off the events — a report of how many
    # sales were called off and when — quietly saw only half of them.
    # ``orders.updated_at`` is not the answer: it is the last change of any
    # kind, so it moves again the next time anything touches the row.
    sv.stamp_order_event(session, order, note=order.cancel_reason or "")
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
        refund_amount=request.refund_amount,
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
                refund_amount=r.refund_amount,
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


def _card(session: SessionDep, user_id: int, card_id: int | None) -> PaymentCard:
    """This customer's card, or nothing that can be charged.

    404 on somebody else's, as in ``routers.cards``: a caller who cannot use a
    card should not be able to learn that it exists. An expired one is a 409 —
    it is theirs, it is simply not usable, and the app should send them to the
    form rather than telling them to try again.
    """
    card = session.get(PaymentCard, card_id) if card_id is not None else None
    if card is None or card.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("card_not_found"))
    if card.status is not CardStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("card_expired"))
    return card


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


def _colour_or_cover(
    session: SessionDep, variant_id: int | None, product_id: int | None
) -> str:
    """The photograph of the colour bought, and no other.

    Where the line has a colour this answers that colour's picture or nothing.
    It used to fall back to the card's cover, which is a *different* colour's
    photograph — so an order for a black shirt could be remembered, for ever,
    as a picture of the white one. That is the surprise nobody can argue with
    six months later, and an empty tile is the honest version of it.

    Relative paths on both sides, because this is a snapshot and the media
    host is allowed to move.
    """
    variant = session.get(ProductVariant, variant_id) if variant_id else None
    if variant is not None and variant.colour:
        row = session.exec(
            select(ProductImage)
            .where(
                ProductImage.product_id == variant.product_id,
                ProductImage.colour == variant.colour,
            )
            .order_by(col(ProductImage.sort), col(ProductImage.id))
        ).first()
        return row.url if row is not None else ""
    return _raw_image(session, product_id)


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
