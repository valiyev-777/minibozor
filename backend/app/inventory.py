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
  pair work from ``OrderItem``, which carries the offer, the product and both
  variant ids. The cart line it came from is deleted when the order is placed,
  so anything not snapshotted there cannot be given back.
* **The shelf belongs to an offer.** The counts that move are the seller's —
  ``Offer.stock_left`` and ``OfferVariant.stock_left`` — because the seller is
  who the goods and the money belong to. The figures on ``Product`` and
  ``ProductVariant`` are a cache of whichever offer is winning, so they are
  never assigned here: ``app.offers.refresh`` recomputes them after every
  movement, and what they did as a result is logged beside what the shelf did.
* **Nothing is restored twice.** Both entry points are guarded by a status
  that can only be reached once — cancelled from placed or packing, refunded
  from approved — so the counts move exactly as often as the decision is made.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, select

from app import audit
from app import offers as of
from app.models import (
    DeliverySlot,
    Offer,
    OfferVariant,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    User,
)


def order_items(session: Session, order: Order) -> list[OrderItem]:
    return list(
        session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    )


def _counted_variants(session: Session, item: OrderItem) -> Iterator[OfferVariant]:
    """The colour and the size of this line, on this seller's shelf.

    A row absent means nobody counts that variant apart — the offer's own
    total is the whole answer for it — and moving a count that does not exist
    would invent one.
    """
    if item.offer_id is None:
        return
    for variant_id in (item.color_variant_id, item.variant_id):
        if variant_id is None:
            continue
        row = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == item.offer_id,
                OfferVariant.variant_id == variant_id,
            )
        ).first()
        if row is not None:
            yield row


# --------------------------------------------------------------------------- taking


def take(session: Session, item: OrderItem) -> None:
    """One line of a new order: off the seller's shelf, onto the sold count.

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

    # Sold is a fact about the thing, whoever sold it, so it stays on the
    # product rather than on one seller's offer.
    product.sold_count += item.quantity
    session.add(product)

    offer = session.get(Offer, item.offer_id) if item.offer_id else None
    if offer is not None:
        offer.stock_left = max(0, offer.stock_left - item.quantity)
        session.add(offer)
        for row in _counted_variants(session, item):
            row.stock_left = max(0, row.stock_left - item.quantity)
            session.add(row)

    # The card's price and stock follow from whose offer is now winning, which
    # this may just have changed — a seller selling out hands the card to the
    # next cheapest.
    of.refresh(session, product.id)


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

    All four counts, because none of it happened: the goods never left, so
    they are on the shelf and were never sold, and the window is free for
    somebody else.
    """
    for item in order_items(session, order):
        _give_back_line(
            session, item, actor=actor, action=action, note=note, unsell=True
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
            session, item, actor=actor, action=action, note=note, unsell=False
        )


def _give_back_line(
    session: Session,
    item: OrderItem,
    *,
    actor: User | None,
    action: str,
    note: str,
    unsell: bool,
) -> None:
    product = session.get(Product, item.product_id) if item.product_id else None
    if product is None:
        return

    offer = session.get(Offer, item.offer_id) if item.offer_id else None
    before = _cache_snapshot(session, product)

    if offer is not None:
        _log(
            session,
            actor=actor,
            action=action,
            entity="offer",
            entity_id=offer.id,
            field="stock_left",
            old=offer.stock_left,
            new=offer.stock_left + item.quantity,
            note=note,
        )
        offer.stock_left += item.quantity
        session.add(offer)

        for row in _counted_variants(session, item):
            variant = session.get(ProductVariant, row.variant_id)
            _log(
                session,
                actor=actor,
                action=action,
                entity="offer_variant",
                entity_id=row.id,
                field="stock_left",
                old=row.stock_left,
                new=row.stock_left + item.quantity,
                note=note or (variant.label if variant else ""),
            )
            row.stock_left += item.quantity
            session.add(row)
    # A line with no offer has no shelf to put anything back onto: the seller
    # it was bought from cannot be named, so inventing a count for one of them
    # would be worse than leaving it. Every line written since offers exist
    # carries one, and the migration filled the older ones in.

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

    # The advertised figures follow the shelf, and are logged as what they are:
    # a consequence. With one seller they move by the same amount; with
    # several, giving stock back to the dearer seller may not move the card at
    # all, and that is worth being able to read afterwards.
    of.refresh(session, product.id)
    _log_cache_moves(
        session, product, before, actor=actor, action=action, note=note
    )


def _cache_snapshot(session: Session, product: Product) -> dict:
    """The figures the shop is advertising, before the shelf moves under them."""
    return {
        "stock_left": product.stock_left,
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
    for field in ("stock_left", "price"):
        now = getattr(product, field)
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
