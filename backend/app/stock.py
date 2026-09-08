"""The shelf, as a ledger.

A stock figure used to be a number somebody wrote. ``PUT .../stock`` set it,
and that was the whole of it: nothing recorded where the goods came from, who
counted them, or why the number changed — and two people saving at once meant
the second one won and the first one's count vanished without trace.

So the figure is now the sum of ``stock_movements``. Every change is a row with
a kind, a reason, a person and a cause, and the columns on ``Offer`` and
``OfferVariant`` are a running total kept for the same reason the price is:
the listings filter and sort on them in SQL. The invariant the tests hold us
to is that the column equals the sum of the ledger.

The second thing here is **holding**. Stock in somebody's basket, or on an
unpaid order, or picked for a seller's collection, is not on the shelf and not
anybody else's to buy — but neither has it left. That is not a movement, so it
is not in the ledger: it is a question asked of the things that are holding it,
which means a hold cannot be leaked, double-released, or left behind by a
crash. An abandoned basket stops holding anything the moment its deadline
passes, without a sweeper having to notice.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, col, func, or_, select

from app.models import (
    CartItem,
    Offer,
    OfferVariant,
    Order,
    OrderItem,
    OrderStatus,
    ProductVariant,
    RemovalLine,
    RemovalOrder,
    RemovalStatus,
    StockMovement,
    StockMovementKind,
    User,
    VariantKind,
    utcnow,
)

# How long a basket holds the last one of something.
#
# Long enough to finish choosing an address and a card; short enough that a
# tab left open over lunch is not a shop with nothing to sell. Touching the
# line pushes it out again.
CART_HOLD = timedelta(minutes=30)

# Which way each kind of movement points. ``None`` means either: a stocktake
# correction is a correction whichever direction the shelf turned out to be
# wrong in.
KIND_SIGN: dict[StockMovementKind, int | None] = {
    StockMovementKind.OPENING: 1,
    StockMovementKind.INTAKE: 1,
    StockMovementKind.SALE: -1,
    StockMovementKind.CANCEL_RETURN: 1,
    StockMovementKind.CUSTOMER_RETURN: 1,
    StockMovementKind.WRITE_OFF: -1,
    StockMovementKind.COUNT_ADJUSTMENT: None,
    StockMovementKind.SELLER_RETURN: -1,
}

# The orders whose goods are promised but not yet paid for. A paid order has
# already taken its stock off the shelf as a sale; an unpaid one has not, so
# what it is owed has to be held for it.
LIVE_UNPAID = (OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED)


# --------------------------------------------------------------------------- moving


def move(
    session: Session,
    *,
    offer: Offer,
    kind: StockMovementKind,
    quantity: int,
    variant_id: int | None = None,
    actor: User | None = None,
    reason: str = "",
    supply_id: int | None = None,
    order_id: int | None = None,
    return_request_id: int | None = None,
    removal_id: int | None = None,
) -> StockMovement | None:
    """Write one movement and carry the running totals with it.

    ``quantity`` is given as a plain count and the sign comes from the kind, so
    a caller cannot get the direction wrong by typing a minus. The one kind
    that may go either way — a stocktake correction — takes a signed number,
    because there the direction is the finding.

    Does not commit. The caller commits along with whatever made the movement
    necessary, so the ledger cannot end up describing something that rolled
    back.
    """
    sign = KIND_SIGN[kind]
    amount = quantity if sign is None else abs(quantity) * sign
    if amount == 0:
        # Not a movement. A stocktake that found exactly what it expected has
        # nothing to record, and a row saying "nothing happened" would make
        # the ledger longer without making it truer.
        return None

    movement = StockMovement(
        offer_id=offer.id,
        variant_id=variant_id,
        kind=kind,
        quantity=amount,
        reason=reason,
        actor_id=actor.id if actor else None,
        supply_id=supply_id,
        order_id=order_id,
        return_request_id=return_request_id,
        removal_id=removal_id,
    )
    session.add(movement)

    offer.stock_left = max(0, offer.stock_left + amount)
    session.add(offer)

    if variant_id is not None:
        row = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == offer.id,
                OfferVariant.variant_id == variant_id,
            )
        ).first()
        if row is None:
            row = OfferVariant(offer_id=offer.id, variant_id=variant_id, stock_left=0)
        row.stock_left = max(0, row.stock_left + amount)
        session.add(row)
        _recount_colour(session, offer, variant_id)

    return movement


def _recount_colour(session: Session, offer: Offer, variant_id: int) -> None:
    """A colour is the sum of its sizes, so a size moving moves it.

    Recomputed rather than moved: a colour holding four when its sizes hold
    one, one and one is a shelf that lies about itself, and the sizes are
    where the counting happens. Nothing is written to the ledger for the
    colour — it is an aggregate, and a movement recorded twice would be a
    shelf counted twice.
    """
    variant = session.get(ProductVariant, variant_id)
    if variant is None or variant.kind is not VariantKind.SIZE:
        return
    colour_id = variant.parent_id
    if colour_id is None:
        return

    siblings = session.exec(
        select(ProductVariant.id).where(ProductVariant.parent_id == colour_id)
    ).all()
    total = 0
    for sibling_id in siblings:
        row = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == offer.id,
                OfferVariant.variant_id == sibling_id,
            )
        ).first()
        if row is not None:
            total += row.stock_left

    colour = session.exec(
        select(OfferVariant).where(
            OfferVariant.offer_id == offer.id, OfferVariant.variant_id == colour_id
        )
    ).first()
    if colour is None:
        colour = OfferVariant(offer_id=offer.id, variant_id=colour_id, stock_left=0)
    colour.stock_left = total
    session.add(colour)


def on_hand(session: Session, offer_id: int, variant_id: int | None = None) -> int:
    """The shelf according to the ledger, which is the only authority on it."""
    stmt = select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
        StockMovement.offer_id == offer_id
    )
    if variant_id is not None:
        stmt = stmt.where(StockMovement.variant_id == variant_id)
    return int(session.exec(stmt).one())


# --------------------------------------------------------------------------- holding


def reserved(
    session: Session,
    offer_id: int,
    variant_id: int | None = None,
    *,
    ignoring_user_id: int | None = None,
) -> int:
    """How much of this offer is promised to somebody already.

    Asked of the baskets, orders and removals that are holding it rather than
    read from a table of holds — a hold is not a fact of its own, it is a
    consequence of something else existing, and deriving it means it cannot be
    leaked or released twice.

    ``ignoring_user_id`` leaves out one shopper's own basket, because a
    stepper that stopped at what the shopper is already holding would refuse
    to let them buy the thing they picked.
    """
    now = utcnow()

    def matches_variant(model) -> object:
        if variant_id is None:
            return True
        return or_(model.variant_id == variant_id, model.color_variant_id == variant_id)

    baskets = select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
        CartItem.offer_id == offer_id,
        # A line with no deadline predates holding and is treated as expired:
        # it would otherwise hold goods for ever with no way to say why.
        col(CartItem.reserved_until).is_not(None),
        CartItem.reserved_until > now,
    )
    if variant_id is not None:
        baskets = baskets.where(matches_variant(CartItem))
    if ignoring_user_id is not None:
        baskets = baskets.where(CartItem.user_id != ignoring_user_id)

    unpaid = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .where(
            OrderItem.offer_id == offer_id,
            Order.paid.is_(False),
            col(Order.status).in_(LIVE_UNPAID),
        )
    )
    if variant_id is not None:
        unpaid = unpaid.where(matches_variant(OrderItem))

    # Picked and standing by the door. Requested is not enough — nobody has
    # touched the shelf yet — but ready is.
    picked = (
        select(func.coalesce(func.sum(RemovalLine.prepared_quantity), 0))
        .join(RemovalOrder, col(RemovalOrder.id) == col(RemovalLine.removal_id))
        .where(
            RemovalLine.offer_id == offer_id,
            RemovalOrder.status == RemovalStatus.READY,
        )
    )
    if variant_id is not None:
        picked = picked.where(RemovalLine.variant_id == variant_id)

    return sum(int(session.exec(stmt).one()) for stmt in (baskets, unpaid, picked))


def sellable(
    session: Session,
    offer: Offer,
    variant_id: int | None = None,
    *,
    for_user_id: int | None = None,
) -> int:
    """What can still be sold: the shelf less what is already promised."""
    shelf = offer.stock_left
    if variant_id is not None:
        row = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == offer.id,
                OfferVariant.variant_id == variant_id,
            )
        ).first()
        if row is None:
            return 0
        shelf = row.stock_left
    held = reserved(session, offer.id, variant_id, ignoring_user_id=for_user_id)
    return max(0, shelf - held)


def hold_until() -> object:
    """The deadline to stamp on a basket line that has just been touched."""
    return utcnow() + CART_HOLD
