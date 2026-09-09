"""What comes off the shelf, and what goes back on it.

Placing an order moved four counts — the product's stock, each chosen
variant's stock, the product's sold count, and a seat in the delivery window —
and cancelling one moved none of them back. The goods vanished, the order
stayed "sold", and the freed window was never offered to anybody else. The
cause was not a missing line in the cancel handler so much as the shape of the
code: taking was thirty lines inlined in ``create_order`` and giving back was
nowhere, so there was nothing for the two halves to be checked against.

So both halves live here, they read the same snapshot, and every count that
moves writes an audit row in the caller's transaction. Two rules:

* **The order line is the record.** ``take`` and the ``restore``/``restock``
  pair work from ``OrderItem``, which carries the product and both variant
  ids. The cart line it came from is deleted when the order is placed, so
  anything not snapshotted there cannot be given back.
* **The shelf belongs to a variant, and it is a ledger.** Counts move by
  writing a row in ``stock_movements`` through ``app.stock.move`` — never by
  assignment. ``ProductVariant.stock_left`` is a running total of that ledger,
  and the price and availability on the card follow from it, recomputed by
  ``app.products.refresh`` after every movement. What the advertised figures
  did as a result is logged beside what the shelf did.
* **Nothing is restored twice.** Both entry points are guarded by a status
  that can only be reached once — cancelled from placed or packing, refunded
  from approved — so the counts move exactly as often as the decision is made.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app import audit
from app import products as pr
from app import stock as st
from app.models import (
    DeliverySlot,
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


def _leaf(session: Session, item: OrderItem) -> ProductVariant | None:
    """The one count this line sits on, if it sits on one.

    The size where a size was chosen, the colour otherwise. One leaf, not
    both: a size and its colour are the same goods counted at two depths, and
    moving both would take the same shirt off the shelf twice.

    ``None`` on a line the customer bought without naming a variant, which is
    only possible on a card that has none — and every card gets at least one
    default variant, so it means a line written before that rule existed.
    """
    for variant_id in (item.variant_id, item.color_variant_id):
        if variant_id is None:
            continue
        variant = session.get(ProductVariant, variant_id)
        if variant is not None:
            return variant
    return None


# --------------------------------------------------------------------------- taking


def take(session: Session, item: OrderItem) -> None:
    """One line of a new order: off the shelf, onto the sold count.

    A colour and a size are each counted apart from the shelf they stand on,
    so buying two blue 42s comes off the blue and off the 42 as well as off
    the total — otherwise the page keeps offering a colour or a size that has
    gone while the product itself looks fine.

    No audit row: nothing here is a decision. The order is the record of it,
    and it is one ``select`` away.
    """
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return

    # Sold is a fact about the thing rather than about one size of it, so it
    # is counted on the card.
    product.sold_count += item.quantity
    session.add(product)
    sell(session, item)


def sell(session: Session, item: OrderItem) -> None:
    """The goods leaving the shelf, and nothing else.

    Apart from ``take`` because the two halves happen at different moments for
    a cash order: it is counted as sold when it is placed, and the goods only
    actually leave when the courier is paid at the door. Until then they are
    held for it rather than gone from it.
    """
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return
    variant = _leaf(session, item)
    if variant is not None:
        st.move(
            session,
            variant=variant,
            kind=StockMovementKind.SALE,
            quantity=item.quantity,
            order_id=item.order_id,
            reason=f"{item.title} × {item.quantity}",
        )
    # The card's figures follow the shelf: selling the last of the cheapest
    # size moves the price the listing shows.
    pr.refresh(session, product.id)


# --------------------------------------------------------------------------- giving back


def restore_order(
    session: Session,
    order: Order,
    *,
    actor: User | None,
    action: str,
    note: str = "",
    shelf: bool = True,
) -> None:
    """Everything a cancelled order took, back where it came from.

    All four counts, because none of it happened: the goods never left, so
    they are on the shelf and were never sold, and the window is free for
    somebody else.

    ``shelf=False`` for an order that was never paid: its goods were only ever
    held for it, not taken off the shelf, and the hold ends when the order
    does. Putting them "back" would create stock out of nothing.
    """
    for item in order_items(session, order):
        _give_back_line(
            session,
            item,
            actor=actor,
            action=action,
            note=note,
            unsell=True,
            shelf=shelf,
            # Nothing about a cancelled order happened, so the goods come back
            # as goods that never left.
            kind=StockMovementKind.CANCEL_RETURN,
        )
    _give_back_seat(session, order, actor=actor, action=action, note=note)


def restock_returned(
    session: Session,
    items: list[OrderItem],
    *,
    actor: User | None,
    action: str,
    note: str = "",
) -> None:
    """Goods that came back and passed inspection, back on the shelf.

    The shelf and the variants only. This was a real sale that a real customer
    took delivery of, and the sold count is the record of that having happened
    rather than of the money having stayed — a refund does not un-sell it. The
    delivery window is not given back either: it was used.
    """
    for item in items:
        _give_back_line(
            session,
            item,
            actor=actor,
            action=action,
            note=note,
            unsell=False,
            # This one did happen: it was bought, delivered, and came back.
            kind=StockMovementKind.CUSTOMER_RETURN,
        )


def _give_back_line(
    session: Session,
    item: OrderItem,
    *,
    actor: User | None,
    action: str,
    note: str,
    unsell: bool,
    kind: StockMovementKind,
    shelf: bool = True,
) -> None:
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return

    variant = _leaf(session, item)
    before = _cache_snapshot(session, product)

    if variant is not None and shelf:
        # The ledger, not an audit row: the movement carries who did it and
        # why, which is what an audit row was standing in for while the shelf
        # was a number somebody assigned.
        st.move(
            session,
            variant=variant,
            kind=kind,
            quantity=item.quantity,
            actor=actor,
            reason=note or item.title,
            order_id=item.order_id,
        )
    # A line that named no variant has no shelf to put anything back onto:
    # there is no telling which colour or size came back, and inventing one
    # would be worse than leaving it.

    if unsell:
        _log(
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

    # The advertised figures follow the shelf, and are logged as what they
    # are: a consequence.
    pr.refresh(session, product.id)
    _log_cache_moves(
        session, product, before, actor=actor, action=action, note=note
    )


def _cache_snapshot(session: Session, product: Product) -> dict:
    """The figures the shop is advertising, before the shelf moves under them."""
    return {
        "stock_left": pr.on_shelf(session, product.id),
        "price": product.price,
        "variants": {
            v.id: v.stock_left
            for v in session.exec(
                select(ProductVariant).where(ProductVariant.product_id == product.id)
            ).all()
        },
    }


def _log_cache_moves(
    session: Session,
    product: Product,
    before: dict,
    *,
    actor: User | None,
    action: str,
    note: str,
) -> None:
    now_shelf = pr.on_shelf(session, product.id)
    for field in ("stock_left", "price"):
        now = now_shelf if field == "stock_left" else product.price
        if now != before[field]:
            _log(
                session,
                actor=actor,
                action=action,
                entity="product",
                entity_id=product.id,
                field=field,
                old=before[field],
                new=now,
                note=note,
            )
    for variant in session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all():
        was = before["variants"].get(variant.id)
        if variant.stock_left != was:
            _log(
                session,
                actor=actor,
                action=action,
                entity="product_variant",
                entity_id=variant.id,
                field="stock_left",
                old=was,
                new=variant.stock_left,
                note=note or variant.label,
            )


def _give_back_seat(
    session: Session,
    order: Order,
    *,
    actor: User | None,
    action: str,
    note: str,
) -> None:
    if order.slot_id is None:
        return
    slot = session.get(DeliverySlot, order.slot_id)
    if slot is None:
        return
    _log(
        session,
        actor=actor,
        action=action,
        entity="delivery_slot",
        entity_id=slot.id,
        field="capacity_left",
        old=slot.capacity_left,
        new=slot.capacity_left + 1,
        note=note or f"{slot.day} {slot.start_time}–{slot.end_time}",
    )
    slot.capacity_left += 1
    session.add(slot)


def _log(session: Session, **kwargs) -> None:
    """Every count that moves, in the caller's transaction.

    Written here rather than in the endpoints so that there is no way to put
    stock back without saying who did it and what the figure was before.
    """
    audit.record(session, **kwargs)
