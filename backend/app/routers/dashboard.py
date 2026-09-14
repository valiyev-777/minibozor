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
from app import products as pr
from app import schemas as s
from app import services as sv
from app.deps import DashboardViewer, SessionDep
from app.models import (
    Location,
    LocationKind,
    Order,
    OrderEvent,
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

# The comparison arithmetic, borrowed rather than written again. `figure`
# decides what "the period before" means and what a percentage against nought
# reports; `day_of` is the one answer to `func.date` returning a string on
# SQLite and a date on Postgres. Two copies of either is two screens quietly
# disagreeing about the shop's own revenue.
from app.routers.reports import day_of, figure

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

# What counts as nearly full. Nearly out is `products.LOW_STOCK`, because the
# catalogue list asks the same question and two answers would disagree.
FULL_AT_PERCENT = 80
LOW_STOCK = pr.LOW_STOCK

SALES_DAYS = 14
MOVERS = 8

# How far back the headline windows reach: a month, and the month before it to
# compare against. One query covers all three windows and their twins.
HEADLINE_DAYS = 60


@router.get(
    "/dashboard",
    response_model=s.DashboardOut,
    summary="The figures, and where to act on each one",
)
def dashboard(user: DashboardViewer, session: SessionDep) -> s.DashboardOut:
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
    # Cancelled orders are not today's takings.
    #
    # This tile counted every row created today, with no status filter, while
    # the fourteen-day chart two panels down excludes cancellations. So the
    # tile and the last point of the chart disagreed by exactly the number of
    # orders somebody had called off — two figures for the same question, on
    # the same screen, one of which counted money the shop was never going to
    # see. The chart was the right one, so the tile now asks what the chart
    # asks.
    trade = _trade(session, today, HEADLINE_DAYS)
    orders_today, takings_today = trade.get(today, (0, 0))
    yesterday = today - timedelta(days=1)
    tiles.append(
        s.DashboardTileOut(
            key="orders_today",
            label=i18n.label("tile_orders_today"),
            value=orders_today,
            hint=f"{sv.money(takings_today)} so'm",
            href="/buyurtmalar",
            previous=trade.get(yesterday, (0, 0))[0],
        )
    )

    # A tile counting what stood in QABUL used to be here, beside a putaway
    # queue that fed it. Goods land on a shelf in one action now, so nothing
    # reaches the receiving area and the figure was always nought — a dashboard
    # row that is always zero teaches people to stop reading the dashboard.

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

    # ------------------------------------------------------------ run out
    # Counted in cards, because a card is what somebody goes and deals with —
    # and counted only among what the shop is offering, because a draft with
    # empty cells is an unfinished card and a different queue. Nothing counted
    # this at all: the tile below starts at one left, so a colour that had
    # actually finished fell out of the bottom of the dashboard and the first
    # anybody heard of it was a customer ordering it.
    gone = session.exec(
        select(func.count(func.distinct(ProductVariant.product_id)))
        .select_from(ProductVariant)
        .join(Product, col(Product.id) == col(ProductVariant.product_id))
        .where(
            ProductVariant.stock_left <= 0,
            Product.status == ProductStatus.ACTIVE,
        )
    ).one()
    tiles.append(
        s.DashboardTileOut(
            key="sold_out",
            label=i18n.label("tile_sold_out"),
            value=int(gone),
            hint=i18n.label("tile_sold_out_hint"),
            href="/mahsulotlar?stock=out",
            urgent=bool(gone),
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
            href="/mahsulotlar?stock=low",
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
        sales=_sales(trade, today),
        movers=_movers(session, now),
        headlines=_headlines(session, trade, today),
    )


# --------------------------------------------------------------------------- pieces


def _trade(session: SessionDep, today: date, days: int) -> dict[date, tuple[int, int]]:
    """Orders placed per day and what they came to, grouped in the database.

    This used to load every order of the window as a row object and bucket
    them in Python. Fourteen days of a small shop is nothing, which is why it
    survived — but the same shape at report scale is every order the shop has
    ever taken passing through a loop to produce thirty numbers. Grouped here
    so nothing copies it.

    Cancelled orders are left out. Nothing was sold, nothing was taken, and
    the goods went back on the shelf.
    """
    start = today - timedelta(days=days - 1)
    rows = session.exec(
        select(
            func.date(Order.created_at),
            func.count(),
            func.coalesce(func.sum(Order.total), 0),
        )
        .where(
            col(Order.created_at) >= _midnight(start),
            col(Order.status).not_in([OrderStatus.CANCELLED]),
        )
        .group_by(func.date(Order.created_at))
    ).all()
    return {
        day_of(day): (int(orders), int(total)) for day, orders, total in rows
    }


def _sales(trade: dict[date, tuple[int, int]], today: date) -> list[s.SalesPointOut]:
    """Fourteen days, including the quiet ones.

    Every day is present whether or not anything was sold: a chart that skips
    empty days draws a shop that was busy on the days it was open, which is
    the opposite of what somebody is looking for.
    """
    start = today - timedelta(days=SALES_DAYS - 1)
    out = []
    for offset in range(SALES_DAYS):
        day = start + timedelta(days=offset)
        orders, total = trade.get(day, (0, 0))
        out.append(s.SalesPointOut(day=day, orders=orders, total=total))
    return out


def _headlines(
    session: SessionDep, trade: dict[date, tuple[int, int]], today: date
) -> list[s.FigureOut]:
    """Orders and revenue over three windows, each against the one before it.

    Every trend on this screen was being differenced in the browser off the
    last two points of the chart — which can only ever answer "today against
    yesterday", answers it wrong at eleven in the morning when today is a third
    over, and leaves the definition of the shop's revenue in a React component
    where nobody can test it. The windows are here instead, and the same
    ``_figure`` the reports use makes them, so the two screens cannot drift
    into two answers.

    Revenue is **delivered orders, bucketed by the day they were delivered** —
    the reports' definition, and the only honest one. The tile above counts
    orders *placed* today, which is a different question and keeps its own
    figure; a tile and a headline saying different things is fine as long as
    each says which it is.
    """
    revenue = _delivered(session, today, HEADLINE_DAYS)

    def window(end: date, length: int) -> tuple[int, int]:
        days = [end - timedelta(days=n) for n in range(length)]
        return (
            sum(trade.get(day, (0, 0))[0] for day in days),
            sum(revenue.get(day, 0) for day in days),
        )

    out: list[s.FigureOut] = []
    for key, length in (("today", 1), ("week", 7), ("month", 30)):
        orders, taken = window(today, length)
        was_orders, was_taken = window(today - timedelta(days=length), length)
        out.append(
            figure(f"orders_{key}", "fig_orders", [was_orders, orders])
        )
        out.append(
            figure(f"revenue_{key}", "fig_revenue", [was_taken, taken], money=True)
        )
    return out


def _delivered(session: SessionDep, today: date, days: int) -> dict[date, int]:
    """Delivered revenue per day, by the day it was delivered.

    Off ``order_events`` and not off ``orders.updated_at``, which is the last
    status change of any kind and moves again every time anything touches the
    row — using it as a delivered-at is the mistake this whole schema makes
    easy to make.
    """
    start = today - timedelta(days=days - 1)
    rows = session.exec(
        select(
            func.date(OrderEvent.happened_at),
            func.coalesce(func.sum(Order.total), 0),
        )
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= _midnight(start),
        )
        .group_by(func.date(OrderEvent.happened_at))
    ).all()
    return {day_of(day): int(total) for day, total in rows}


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
