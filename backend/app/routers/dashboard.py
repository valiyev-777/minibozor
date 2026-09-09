"""The first screen, and the only one that is allowed to be a list of numbers.

**Every figure links.** A dashboard number that is not a link is a dead end:
somebody reads "4 cards held back for want of a photograph" and then has to go
and find them. So each tile carries the path of the screen it is answered on,
and the client's job is to make it clickable rather than to work out where it
goes.

**One tile is allowed to shout.** Sacks that have been standing unopened for
longer than an evening are the thing this shop actually loses money on — goods
in the building that the system has never heard of — so that tile is marked
urgent and the rest are not. If everything is urgent, nothing is.

Read-only, and deliberately cheap: this is the screen that is open all day.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter
from sqlmodel import col, func, select

from app import i18n
from app import locations as loc
from app import products as pr
from app import schemas as s
from app import services as sv
from app.deps import OrderViewer, SessionDep
from app.models import (
    Location,
    LocationKind,
    Order,
    OrderStatus,
    Product,
    ProductStatus,
    ProductVariant,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    Supply,
    SupplyStatus,
    utcnow,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# When a sack standing in the receiving area stops being normal.
#
# An hour, because the brief is plain that a QABUL tile with anything older
# than an hour in it should be impossible to ignore. Sacks are given the
# evening they were always going to need — an unsorted run is judged against
# a night rather than an hour, because that is the actual working pattern.
QABUL_ALERT_MINUTES = 60

# Three days. A card held back for an afternoon is somebody waiting for
# daylight to photograph it; one held back for three days is goods nobody is
# going to get round to, sitting on a shelf costing rent and earning nothing.
HELD_BACK_ALERT_MINUTES = 3 * 24 * 60
SACK_ALERT_HOURS = 14

# What counts as nearly full, and as nearly out.
FULL_AT_PERCENT = 80
LOW_STOCK = 3

SALES_DAYS = 14
MOVERS = 8


@router.get(
    "/dashboard",
    response_model=s.DashboardOut,
    summary="The figures, and where to act on each one",
)
def dashboard(user: OrderViewer, session: SessionDep) -> s.DashboardOut:
    now = utcnow()
    today = now.date()

    tiles: list[s.DashboardTileOut] = []

    # ---------------------------------------------------------- unsorted sacks
    drafts = session.exec(
        select(Supply).where(Supply.status == SupplyStatus.DRAFT)
    ).all()
    oldest_sack = min((run.declared_at for run in drafts), default=None)
    standing = _hours(oldest_sack, now)
    tiles.append(
        s.DashboardTileOut(
            key="unsorted_sacks",
            label=i18n.label("tile_unsorted_sacks"),
            value=len(drafts),
            hint=_age_words(oldest_sack, now),
            href="/qabul",
            urgent=bool(drafts) and standing >= SACK_ALERT_HOURS,
        )
    )

    # ---------------------------------------------------------- today's orders
    todays = session.exec(
        select(Order).where(col(Order.created_at) >= _midnight(today))
    ).all()
    tiles.append(
        s.DashboardTileOut(
            key="orders_today",
            label=i18n.label("tile_orders_today"),
            value=len(todays),
            hint=f"{sv.money(sum(order.total for order in todays))} so'm",
            href="/buyurtmalar",
        )
    )

    # ---------------------------------------------------------- waiting in QABUL
    receiving = loc.staging(session, loc.QABUL)
    waiting = int(
        session.exec(
            select(func.coalesce(func.sum(StockPlacement.qty), 0)).where(
                StockPlacement.location_id == receiving.id
            )
        ).one()
    )
    since = session.exec(
        select(func.min(StockMovement.created_at)).where(
            StockMovement.to_location_id == receiving.id
        )
    ).one()
    tiles.append(
        s.DashboardTileOut(
            key="awaiting_putaway",
            label=i18n.label("tile_awaiting_putaway"),
            value=waiting,
            hint=_age_words(since, now) if waiting else "",
            href="/joylashtirish",
            urgent=bool(waiting) and _minutes(since, now) >= QABUL_ALERT_MINUTES,
        )
    )

    # ------------------------------------------------- on the shelf, not in the shop
    # The thing this shop loses money on quietly. Goods are shelved, counted
    # and findable, and a customer cannot buy them because the card still has
    # no category, no price or no photograph. Nobody notices, because nothing
    # is broken — which is exactly why it is on the dashboard and not in a
    # menu somewhere.
    held_back = [
        row
        for row in session.exec(
            select(Product).where(Product.status == ProductStatus.DRAFT)
        ).all()
        if pr.on_shelf(session, row.id) > 0
    ]
    oldest = min((row.created_at for row in held_back), default=None)
    tiles.append(
        s.DashboardTileOut(
            key="held_back",
            label=i18n.label("tile_held_back"),
            value=len(held_back),
            hint=_age_words(oldest, now) if held_back else "",
            href="/sotuvga-chiqarish",
            urgent=bool(held_back) and _minutes(oldest, now) >= HELD_BACK_ALERT_MINUTES,
        )
    )

    # ---------------------------------------------------------- the shelves
    cells = session.exec(
        select(Location).where(
            Location.kind == LocationKind.BIN, col(Location.is_active).is_(True)
        )
    ).all()
    held = {
        int(location_id): int(units)
        for location_id, units in session.exec(
            select(
                StockPlacement.location_id,
                func.coalesce(func.sum(StockPlacement.qty), 0),
            ).group_by(col(StockPlacement.location_id))
        ).all()
    }
    full = sum(
        1
        for cell in cells
        if cell.capacity and held.get(cell.id, 0) / cell.capacity * 100 >= FULL_AT_PERCENT
    )
    empty = sum(1 for cell in cells if not held.get(cell.id, 0))
    tiles.append(
        s.DashboardTileOut(
            key="cells_full",
            label=i18n.label("tile_cells_full"),
            value=full,
            hint=i18n.label("tile_cells_empty", count=empty),
            href="/ombor",
        )
    )

    # ---------------------------------------------------------- running out
    low = session.exec(
        select(func.count())
        .select_from(ProductVariant)
        .where(
            ProductVariant.stock_left > 0, ProductVariant.stock_left <= LOW_STOCK
        )
    ).one()
    tiles.append(
        s.DashboardTileOut(
            key="low_stock",
            label=i18n.label("tile_low_stock"),
            value=int(low),
            hint=i18n.label("tile_low_stock_hint", count=LOW_STOCK),
            href="/mahsulotlar?low=1",
        )
    )

    # A tile counting cards without a photograph used to sit here. It said
    # almost what "on the shelf, not in the shop" says above and sent people to
    # a filtered product list rather than to the queue that fixes it — and it
    # counted cards with nothing on a shelf, which are somebody's abandoned
    # draft rather than money standing still. Two tiles for one problem meant
    # neither was the one you acted on.

    # ---------------------------------------------------------- couriers out
    carrying = session.exec(
        select(func.count(func.distinct(StockPlacement.location_id)))
        .select_from(StockPlacement)
        .join(Location, col(Location.id) == col(StockPlacement.location_id))
        .where(Location.kind == LocationKind.COURIER, StockPlacement.qty > 0)
    ).one()
    tiles.append(
        s.DashboardTileOut(
            key="couriers_out",
            label=i18n.label("tile_couriers_out"),
            value=int(carrying),
            href="/kuryerlar",
        )
    )

    return s.DashboardOut(
        tiles=tiles,
        sales=_sales(session, today),
        movers=_movers(session, now),
    )


# --------------------------------------------------------------------------- pieces


def _sales(session: SessionDep, today: date) -> list[s.SalesPointOut]:
    """Fourteen days, including the quiet ones.

    Every day is present whether or not anything was sold: a chart that skips
    empty days draws a shop that was busy on the days it was open, which is
    the opposite of what somebody is looking for.
    """
    start = today - timedelta(days=SALES_DAYS - 1)
    rows = session.exec(
        select(Order).where(
            col(Order.created_at) >= _midnight(start),
            col(Order.status).not_in([OrderStatus.CANCELLED]),
        )
    ).all()

    by_day: dict[date, tuple[int, int]] = {}
    for order in rows:
        day = order.created_at.date()
        orders, total = by_day.get(day, (0, 0))
        by_day[day] = (orders + 1, total + order.total)

    out = []
    for offset in range(SALES_DAYS):
        day = start + timedelta(days=offset)
        orders, total = by_day.get(day, (0, 0))
        out.append(s.SalesPointOut(day=day, orders=orders, total=total))
    return out


def _movers(session: SessionDep, now) -> list[s.MoverOut]:
    """What actually leaves the building, which is not the same as what sells.

    Counted off the ledger's deliveries rather than off order lines: an order
    placed and never delivered moved nothing, and a list of "top sellers" that
    includes it sends somebody to the market to buy more of a thing nobody
    took.
    """
    since = now - timedelta(days=30)
    rows = session.exec(
        select(
            StockMovement.variant_id,
            func.coalesce(func.sum(StockMovement.qty), 0),
        )
        .where(
            StockMovement.kind == StockMovementKind.DELIVERED,
            col(StockMovement.created_at) >= since,
        )
        .group_by(col(StockMovement.variant_id))
    ).all()

    out = []
    for variant_id, qty in sorted(rows, key=lambda row: -int(row[1]))[:MOVERS]:
        variant = session.get(ProductVariant, variant_id)
        product = session.get(Product, variant.product_id) if variant else None
        out.append(
            s.MoverOut(
                variant_id=int(variant_id),
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant) if variant else "",
                qty=int(qty),
            )
        )
    return out


def _midnight(day: date):
    from datetime import datetime

    return datetime(day.year, day.month, day.day)


def _minutes(since, now) -> int:
    return 0 if since is None else max(0, int((now - since).total_seconds() // 60))


def _hours(since, now) -> int:
    return _minutes(since, now) // 60


def _age_words(since, now) -> str:
    """"2 soat 10 daqiqa" — the age a person reads rather than a timestamp.

    Written here rather than in the client because three clients would write
    it three ways, and this is the figure the whole tile exists for.
    """
    if since is None:
        return ""
    minutes = _minutes(since, now)
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return i18n.label("age_hours_minutes", hours=hours, minutes=rest)
    if hours:
        return i18n.label("age_hours", hours=hours)
    return i18n.label("age_minutes", minutes=rest)
