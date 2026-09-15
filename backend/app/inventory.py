"""What an order does to the room.

Placing an order used to move several counts and cancelling one moved none of
them back: the goods vanished and the order stayed "sold". So both halves live
here, they read the same snapshot, and every count that moves writes an audit
row in the caller's transaction.

**Money does not move goods.** That is the change this file exists to carry.
An order being paid for used to take the goods off the shelf; now it holds
them, and they physically leave when a courier hands them over at a door. The
two are different events with different evidence — a payment is a row on an
order, a delivery is a move in the ledger — and the shop was only ever able to
answer "where is it" for one of them.

Three rules:

* **The order line is the record.** ``take`` and the giving-back pair work
  from ``OrderItem``, which carries the product and the variant. The cart line
  it came from is deleted when the order is placed, so anything not
  snapshotted there cannot be given back.
* **Every move names two places.** Goods leave the shelves through
  ``app.stock.take_from_shelf``, which draws from the nearest place first and
  splits across two cells when one does not hold enough.
* **Nothing is restored twice.** Both entry points are guarded by a status
  that can only be reached once — cancelled from placed or packing, refunded
  from approved — so the counts move exactly as often as the decision is made.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app import audit
from app import locations as loc
from app import products as pr
from app import stock as st
from app.models import (
    Location,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    StockMovementKind,
    User,
)


def order_items(session: Session, order: Order) -> list[OrderItem]:
    return list(
        session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    )


def _variant(session: Session, item: OrderItem) -> ProductVariant | None:
    """The cell of the grid this line was bought from.

    ``None`` on a line written before every card had variants, which is a line
    with no shelf to move: there is no telling which colour or size it was,
    and inventing one would be worse than leaving it.
    """
    if item.variant_id is None:
        return None
    return session.get(ProductVariant, item.variant_id)


# --------------------------------------------------------------------------- taking


def take(session: Session, item: OrderItem) -> None:
    """One line of a new order.

    Nothing moves. The goods are held for the order — which
    ``app.stock.reserved`` reads off the order itself — and they stand where
    they stood until somebody picks them.

    The sold count is a fact about the card's popularity rather than about the
    shelf, so it moves here, where the buying happened.
    """
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return
    product.sold_count += item.quantity
    session.add(product)
    pr.refresh(session, product.id)


def hand_over(
    session: Session,
    order: Order,
    *,
    actor: User | None,
    note: str = "",
) -> None:
    """The goods leave the building, which is what a delivery is.

    Taken from wherever they actually are: the courier's own bag if the parcel
    was handed to them, then the packing area if it was picked but never
    loaded, and the shelves if neither — which is the ordinary case until
    there are pick tasks to walk. Nothing here is a status: the order's own
    status is moved by the caller, and this is only the room emptying.
    """
    bag = (
        loc.for_courier(session, order.courier_id)
        if order.courier_id is not None
        else None
    )
    packing = loc.staging(session, loc.YIGIM)

    touched: set[int] = set()
    for item in order_items(session, order):
        variant = _variant(session, item)
        if variant is None:
            continue
        left = item.quantity
        for place in (bag, packing):
            if left <= 0 or place is None:
                continue
            here = min(left, st.at(session, place.id, variant.id))
            if here <= 0:
                continue
            st.move(
                session,
                variant=variant,
                qty=here,
                kind=StockMovementKind.DELIVERED,
                frm=place,
                to=None,
                actor=actor,
                reason=note or item.title,
                order_id=order.id,
            )
            left -= here
        if left > 0:
            st.take_from_shelf(
                session,
                variant,
                left,
                kind=StockMovementKind.DELIVERED,
                to=None,
                actor=actor,
                reason=note or item.title,
                order_id=order.id,
            )
        if item.product_id is not None:
            touched.add(item.product_id)

    for product_id in sorted(touched):
        pr.refresh(session, product_id)


# --------------------------------------------------------------------------- giving back


def restore_order(
    session: Session,
    order: Order,
    *,
    actor: User | None,
    action: str,
    note: str = "",
) -> None:
    """Everything a cancelled order took, back where it came from.

    Which is less than it used to be. The goods never left — being sold
    stopped moving them — so what is owed is the sold count and putting back
    anything already fetched for this order that is standing in the packing
    area or in a courier's bag.
    """
    for item in order_items(session, order):
        _unpick(session, item, order, actor=actor, note=note)
        _unsell(session, item, actor=actor, action=action, note=note)


def came_back(
    session: Session,
    items: list[OrderItem],
    *,
    actor: User | None,
    note: str = "",
    damaged: bool = False,
) -> None:
    """A customer's parcel, arriving back in the building.

    Two moves and not one, because they are two different facts: the goods
    came back — from outside, into the returns corner — and then somebody
    decided what they were. Whole goods go on to the receiving area and are
    for sale again; damaged ones go to the damaged corner, where they are
    still in the building, still counted, and not for sale.

    Recording only the second would leave the room unable to say a parcel had
    arrived until somebody had judged it.
    """
    returns = loc.staging(session, loc.QAYTGAN)
    onward = loc.staging(session, loc.BRAK if damaged else loc.QABUL)
    kind = StockMovementKind.DAMAGE if damaged else StockMovementKind.RELIST

    touched: set[int] = set()
    for item in items:
        variant = _variant(session, item)
        if variant is None:
            continue
        st.move(
            session,
            variant=variant,
            qty=item.quantity,
            kind=StockMovementKind.RETURN,
            frm=None,
            to=returns,
            actor=actor,
            reason=note or item.title,
            order_id=item.order_id,
        )
        st.move(
            session,
            variant=variant,
            qty=item.quantity,
            kind=kind,
            frm=returns,
            to=onward,
            actor=actor,
            reason=note or item.title,
            order_id=item.order_id,
        )
        if item.product_id is not None:
            touched.add(item.product_id)

    for product_id in sorted(touched):
        pr.refresh(session, product_id)


def _unpick(
    session: Session,
    item: OrderItem,
    order: Order,
    *,
    actor: User | None,
    note: str,
) -> None:
    """Anything already fetched for this order, back into the receiving area.

    Not back into the cell it came from. The cell is known — the ledger says
    so — but the goods are in somebody's hands by the door, and telling them
    to walk it back to A-02-03 is a rule that gets ignored. ``QABUL`` is where
    unplaced goods live, and the putaway queue is what gets them home.
    """
    variant = _variant(session, item)
    if variant is None:
        return
    receiving = loc.staging(session, loc.QABUL)
    places: list[Location] = [loc.staging(session, loc.YIGIM)]
    if order.courier_id is not None:
        places.append(loc.for_courier(session, order.courier_id))

    for place in places:
        here = min(item.quantity, st.at(session, place.id, variant.id))
        if here <= 0:
            continue
        st.move(
            session,
            variant=variant,
            qty=here,
            kind=StockMovementKind.MOVE,
            frm=place,
            to=receiving,
            actor=actor,
            reason=note or item.title,
            order_id=order.id,
        )


def _unsell(
    session: Session,
    item: OrderItem,
    *,
    actor: User | None,
    action: str,
    note: str,
) -> None:
    """The sold count, and what the card is advertising as a result.

    Both logged, and logged as what they are: one is a decision somebody made
    and the other is a consequence of it.
    """
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return
    before = pr.on_shelf(session, product.id)

    audit.record(
        session,
        actor=actor,
        action=action,
        entity="product",
        entity_id=product.id,
        field="sold_count",
        old=product.sold_count,
        new=max(0, product.sold_count - item.quantity),
        note=note,
    )
    product.sold_count = max(0, product.sold_count - item.quantity)
    session.add(product)

    pr.refresh(session, product.id)
    now = pr.on_shelf(session, product.id)
    if now != before:
        audit.record(
            session,
            actor=actor,
            action=action,
            entity="product",
            entity_id=product.id,
            field="stock_left",
            old=before,
            new=now,
            note=note,
        )
