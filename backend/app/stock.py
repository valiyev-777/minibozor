"""The shelf, as a ledger.

A stock figure used to be a number somebody wrote. ``PUT .../stock`` set it,
and that was the whole of it: nothing recorded where the goods came from, who
counted them, or why the number changed — and two people saving at once meant
the second one won and the first one's count vanished without trace.

So the figure is now the sum of ``stock_movements``. Every change is a row with
a kind, a reason, a person and a cause, and ``ProductVariant.stock_left`` is a
running total of it, kept as a column because every listing filters and sorts
on it in SQL. The invariant the tests hold us to is that the column equals the
sum of the ledger.

**The count hangs off a variant.** It used to hang off an offer — whose shelf
this was — and there is only one shelf now. "Krossovka — 50 dona" is a
sentence this system cannot express; "qora / 42 — 3 dona" is what it stores.

The second thing here is **holding**. Stock in somebody's basket, or on an
unpaid order, is not on the shelf and not anybody else's to buy — but neither
has it left. That is not a movement, so it is not in the ledger: it is a
question asked of the things that are holding it, which means a hold cannot be
leaked, double-released, or left behind by a crash. An abandoned basket stops
holding anything the moment its deadline passes, without a sweeper having to
notice.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, col, func, or_, select

from app.models import (
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    ProductVariant,
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
}

# The orders whose goods are promised but not yet paid for. A paid order has
# already taken its stock off the shelf as a sale; an unpaid one has not, so
# what it is owed has to be held for it.
LIVE_UNPAID = (OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED)


# --------------------------------------------------------------------------- moving


def move(
    session: Session,
    *,
    variant: ProductVariant,
    kind: StockMovementKind,
    quantity: int,
    actor: User | None = None,
    reason: str = "",
    supply_id: int | None = None,
    order_id: int | None = None,
    return_request_id: int | None = None,
) -> StockMovement | None:
    """Write one movement and carry the running total with it.

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
        variant_id=variant.id,
        kind=kind,
        quantity=amount,
        reason=reason,
        actor_id=actor.id if actor else None,
        supply_id=supply_id,
        order_id=order_id,
        return_request_id=return_request_id,
    )
    session.add(movement)

    variant.stock_left = max(0, variant.stock_left + amount)
    variant.in_stock = variant.stock_left > 0
    session.add(variant)
    _recount_colour(session, variant)

    return movement


def _recount_colour(session: Session, variant: ProductVariant) -> None:
    """A colour is the sum of its sizes, so a size moving moves it.

    Recomputed rather than moved: a colour holding four when its sizes hold
    one, one and one is a shelf that lies about itself, and the sizes are
    where the counting happens. Nothing is written to the ledger for the
    colour — it is an aggregate, and a movement recorded twice would be a
    shelf counted twice. That is also why the ledger invariant is checked
    against the leaves: a colour row has no movements of its own.
    """
    if variant.kind is not VariantKind.SIZE or variant.parent_id is None:
        return

    colour = session.get(ProductVariant, variant.parent_id)
    if colour is None:
        return

    total = int(
        session.exec(
            select(func.coalesce(func.sum(ProductVariant.stock_left), 0)).where(
                ProductVariant.parent_id == colour.id
            )
        ).one()
    )
    colour.stock_left = total
    colour.in_stock = total > 0
    session.add(colour)


def on_hand(session: Session, variant_id: int) -> int:
    """The shelf according to the ledger, which is the only authority on it."""
    return int(
        session.exec(
            select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
                StockMovement.variant_id == variant_id
            )
        ).one()
    )


# --------------------------------------------------------------------------- holding


def reserved(
    session: Session,
    variant_id: int,
    *,
    ignoring_user_id: int | None = None,
) -> int:
    """How much of this variant is promised to somebody already.

    Asked of the baskets and orders that are holding it rather than read from
    a table of holds — a hold is not a fact of its own, it is a consequence of
    something else existing, and deriving it means it cannot be leaked or
    released twice.

    ``ignoring_user_id`` leaves out one shopper's own basket, because a
    stepper that stopped at what the shopper is already holding would refuse
    to let them buy the thing they picked.
    """
    now = utcnow()

    def matches(model) -> object:
        return or_(model.variant_id == variant_id, model.color_variant_id == variant_id)

    baskets = select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
        matches(CartItem),
        # A line with no deadline predates holding and is treated as expired:
        # it would otherwise hold goods for ever with no way to say why.
        col(CartItem.reserved_until).is_not(None),
        CartItem.reserved_until > now,
    )
    if ignoring_user_id is not None:
        baskets = baskets.where(CartItem.user_id != ignoring_user_id)

    unpaid = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .where(
            matches(OrderItem),
            Order.paid.is_(False),
            col(Order.status).in_(LIVE_UNPAID),
        )
    )

    return sum(int(session.exec(stmt).one()) for stmt in (baskets, unpaid))


def sellable(
    session: Session,
    variant: ProductVariant,
    *,
    for_user_id: int | None = None,
) -> int:
    """What can still be sold: the shelf less what is already promised."""
    held = reserved(session, variant.id, ignoring_user_id=for_user_id)
    return max(0, variant.stock_left - held)


def hold_until() -> object:
    """The deadline to stamp on a basket line that has just been touched."""
    return utcnow() + CART_HOLD
