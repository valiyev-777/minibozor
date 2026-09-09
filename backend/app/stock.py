"""The shelf, as a ledger of moves.

A stock figure used to be a number somebody wrote. Then it was a signed row
with a reason on it. It is now a **move**: this many of this variant, from
here to there, where either end may be the outside world.

That third step is what makes the room answerable. A signed ledger can say how
many black 42s the shop has; only a ledger of moves can say that four of them
are in A-02-03, two are in a courier's bag and one is in the damaged corner —
and those are the questions the warehouse actually asks all day.

Three rules hold everything here together.

* **Never assign a figure.** ``move`` writes a difference and carries the
  running totals with it. Two people working the same cell at once therefore
  add to each other rather than overwriting each other.
* **Every count is in exactly one place.** There is no "unplaced" flag: being
  in ``QABUL`` is the unplaced state. So a move always names both ends, and
  ``StockPlacement`` is the derived answer to "what is in this place", held to
  equalling the ledger by a test.
* **Money does not move goods.** There is no ``sale`` movement. Goods leave
  the building when a courier hands them over at a door, and until then they
  are somewhere in it.

The last thing here is **holding**. Stock in somebody's basket, or promised to
an order that has not been delivered, is not anybody else's to buy — but
neither has it moved. That is not a move, so it is not in the ledger: it is a
question asked of the things that are holding it, which means a hold cannot be
leaked, double-released, or left behind by a crash.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, col, func, select

from app import locations as loc
from app.models import (
    SELLABLE_KINDS,
    CartItem,
    Location,
    Order,
    OrderItem,
    OrderStatus,
    ProductVariant,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    User,
    utcnow,
)

# How long a basket holds the last one of something.
#
# Long enough to finish choosing an address and a card; short enough that a
# tab left open over lunch is not a shop with nothing to sell. Touching the
# line pushes it out again.
CART_HOLD = timedelta(minutes=30)

# The orders whose goods are promised and still in the building. A delivered
# order's goods have physically left — the ledger says so — and a cancelled
# one's were given back; everything in between is holding what it was sold.
LIVE_ORDERS = (OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED)


class StockError(RuntimeError):
    """A move the room cannot make — usually taking more than is there."""


# --------------------------------------------------------------------------- moving


def move(
    session: Session,
    *,
    variant: ProductVariant,
    qty: int,
    kind: StockMovementKind,
    frm: Location | None = None,
    to: Location | None = None,
    actor: User | None = None,
    reason: str = "",
    supply_id: int | None = None,
    order_id: int | None = None,
    return_request_id: int | None = None,
    allow_negative: bool = False,
) -> StockMovement:
    """Move ``qty`` of ``variant`` from one place to another.

    ``frm=None`` is the outside world arriving — a market run, a parcel coming
    back. ``to=None`` is leaving the building — delivered, written off. Both
    None is not a move and is refused, as is a quantity of nothing: a row
    saying nothing happened makes the ledger longer without making it truer.

    **Refuses to take what is not there.** A cell that would go negative is a
    miscount somebody needs to look at, not an arithmetic result — the one
    exception is a stocktake correction, which is allowed to say the shelf was
    already wrong.

    Does not commit. The caller commits along with whatever made the move
    necessary, so the ledger cannot end up describing something that rolled
    back.
    """
    if qty <= 0:
        raise StockError("a move of nothing is not a move")
    if frm is None and to is None:
        raise StockError("a move needs somewhere to come from or go to")

    if frm is not None:
        held = at(session, frm.id, variant.id)
        if held < qty and not allow_negative:
            raise StockError(
                f"{frm.code} holds {held} of {variant.sku or variant.id}, not {qty}"
            )
        _shift(session, frm, variant, -qty)
    if to is not None:
        _shift(session, to, variant, qty)

    movement = StockMovement(
        variant_id=variant.id,
        from_location_id=frm.id if frm else None,
        to_location_id=to.id if to else None,
        kind=kind,
        qty=qty,
        reason=reason,
        actor_id=actor.id if actor else None,
        supply_id=supply_id,
        order_id=order_id,
        return_request_id=return_request_id,
    )
    session.add(movement)

    # In the building, over every place holding any. Arriving adds, leaving
    # takes away, and a move from one place to another leaves it alone.
    change = (qty if to is not None else 0) - (qty if frm is not None else 0)
    if change:
        variant.stock_left = max(0, variant.stock_left + change)
    variant.in_stock = variant.stock_left > 0
    session.add(variant)

    return movement


def _shift(session: Session, location: Location, variant: ProductVariant, by: int) -> None:
    """Carry one placement by a difference, making the row if it is the first."""
    row = session.exec(
        select(StockPlacement).where(
            StockPlacement.location_id == location.id,
            StockPlacement.variant_id == variant.id,
        )
    ).first()
    if row is None:
        row = StockPlacement(location_id=location.id, variant_id=variant.id, qty=0)
    row.qty = row.qty + by
    session.add(row)


def at(session: Session, location_id: int, variant_id: int) -> int:
    """How many of one variant one place holds, off the placement."""
    row = session.exec(
        select(StockPlacement).where(
            StockPlacement.location_id == location_id,
            StockPlacement.variant_id == variant_id,
        )
    ).first()
    return row.qty if row else 0


def ledger_at(session: Session, location_id: int, variant_id: int) -> int:
    """The same, computed from the movements — what the placement must equal."""
    into = session.exec(
        select(func.coalesce(func.sum(StockMovement.qty), 0)).where(
            StockMovement.to_location_id == location_id,
            StockMovement.variant_id == variant_id,
        )
    ).one()
    out = session.exec(
        select(func.coalesce(func.sum(StockMovement.qty), 0)).where(
            StockMovement.from_location_id == location_id,
            StockMovement.variant_id == variant_id,
        )
    ).one()
    return int(into) - int(out)


def on_hand(session: Session, variant_id: int) -> int:
    """Everything of this variant in the building, from the ledger."""
    into = session.exec(
        select(func.coalesce(func.sum(StockMovement.qty), 0)).where(
            StockMovement.variant_id == variant_id,
            col(StockMovement.to_location_id).is_not(None),
        )
    ).one()
    out = session.exec(
        select(func.coalesce(func.sum(StockMovement.qty), 0)).where(
            StockMovement.variant_id == variant_id,
            col(StockMovement.from_location_id).is_not(None),
        )
    ).one()
    return int(into) - int(out)


def placements(session: Session, variant_id: int) -> list[tuple[Location, int]]:
    """Every place holding any of this variant, in walk order.

    What the "where is it?" box on the shelf map answers with, and what the
    pick list is built from: a model that outgrew its cell is in two of them
    and the picker has to be sent to both.
    """
    rows = session.exec(
        select(StockPlacement, Location)
        .join(Location, col(Location.id) == col(StockPlacement.location_id))
        .where(StockPlacement.variant_id == variant_id, StockPlacement.qty > 0)
    ).all()
    return sorted(
        ((location, placement.qty) for placement, location in rows),
        key=lambda pair: loc.walk_order(pair[0]),
    )


def sellable_places(session: Session, variant_id: int) -> list[tuple[Location, int]]:
    """The same, less the places goods cannot be sold from."""
    return [
        (location, qty)
        for location, qty in placements(session, variant_id)
        if location.kind in SELLABLE_KINDS
    ]


def take_from_shelf(
    session: Session,
    variant: ProductVariant,
    qty: int,
    *,
    kind: StockMovementKind,
    to: Location | None,
    actor: User | None = None,
    reason: str = "",
    order_id: int | None = None,
    return_request_id: int | None = None,
) -> list[StockMovement]:
    """Take ``qty`` off the shelves, drawing from the nearest places first.

    Nearest in walk order, which for a picker is the receiving desk on the way
    in and then the racks. Split across places when one does not hold enough,
    because a model that outgrew its cell is in two of them and the goods are
    no less real for it.
    """
    left = qty
    made: list[StockMovement] = []
    for location, held in sellable_places(session, variant.id):
        if left <= 0:
            break
        step = min(left, held)
        made.append(
            move(
                session,
                variant=variant,
                qty=step,
                kind=kind,
                frm=location,
                to=to,
                actor=actor,
                reason=reason,
                order_id=order_id,
                return_request_id=return_request_id,
            )
        )
        left -= step
    if left > 0:
        raise StockError(
            f"only {qty - left} of {variant.sku or variant.id} on the shelves, not {qty}"
        )
    return made


# --------------------------------------------------------------------------- holding


def reserved(
    session: Session,
    variant_id: int,
    *,
    ignoring_user_id: int | None = None,
) -> int:
    """How much of this variant is promised to somebody already.

    Asked of the baskets and orders holding it rather than read from a table
    of holds — a hold is not a fact of its own, it is a consequence of
    something else existing, and deriving it means it cannot be leaked or
    released twice.

    **Every live order counts, paid or not.** Money stopped moving goods when
    the ledger became a ledger of places: an order that has been paid for and
    not yet delivered is still standing in the building, so what holds it off
    the shelf is this rather than a sale that already happened.

    ``ignoring_user_id`` leaves out one shopper's own basket, because a
    stepper that stopped at what they are already holding would refuse to let
    them buy the thing they picked.
    """
    now = utcnow()

    baskets = select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
        CartItem.variant_id == variant_id,
        # A line with no deadline predates holding and is treated as expired:
        # it would otherwise hold goods for ever with no way to say why.
        col(CartItem.reserved_until).is_not(None),
        CartItem.reserved_until > now,
    )
    if ignoring_user_id is not None:
        baskets = baskets.where(CartItem.user_id != ignoring_user_id)

    promised = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .where(
            OrderItem.variant_id == variant_id,
            col(Order.status).in_(LIVE_ORDERS),
        )
    )

    # Less what has already been fetched for those orders. A picked parcel has
    # physically left the shelf and is standing in YIGIM, which is not a place
    # anything is sold from — counting it as promised *as well* would hold the
    # same two shirts off the shop twice, and the shelf would appear to shrink
    # every time somebody did their job.
    fetched = (
        select(func.coalesce(func.sum(StockMovement.qty), 0))
        .join(Order, col(Order.id) == col(StockMovement.order_id))
        .where(
            StockMovement.variant_id == variant_id,
            StockMovement.kind == StockMovementKind.PICK,
            col(Order.status).in_(LIVE_ORDERS),
        )
    )

    held = int(session.exec(baskets).one()) + int(session.exec(promised).one())
    return max(0, held - int(session.exec(fetched).one()))


def sellable(
    session: Session,
    variant: ProductVariant,
    *,
    for_user_id: int | None = None,
) -> int:
    """What can still be sold: what is on a sellable shelf, less what is promised.

    Not ``stock_left``, which counts the whole building. Goods in the damaged
    corner and goods that came back and nobody has looked at are in the
    building too, and neither is for sale.
    """
    shelf = sum(qty for _, qty in sellable_places(session, variant.id))
    held = reserved(session, variant.id, ignoring_user_id=for_user_id)
    return max(0, shelf - held)


def hold_until() -> object:
    """The deadline to stamp on a basket line that has just been touched."""
    return utcnow() + CART_HOLD
