"""How the business is doing — the screen `/hisobotlar` should always have been.

What was there was one paged table of raw ``stock_movements``: no dates, no
totals, and not a single so'm on it. A good forensic tool, filed under the menu
item an owner opens to ask whether the shop is making money. The owner's own
words were "junlar va chalkashlik" — fluff and confusion — and the request was
for money in, customers, and whether each is going up or down.

**Every headline carries the period before it.** "Oshishi pasayishi" is the
whole question, so a figure never arrives alone: this period, the one before of
exactly the same length, the difference, and the percentage where one exists.
The screen draws the arrow and does no arithmetic of its own. A figure the past
genuinely cannot answer — what is standing in the room today — says so with a
null rather than being compared against a nought.

**Nothing here is invented.** Conversion, traffic, sessions, cart abandonment
and route efficiency are all absent because nothing records them; a number with
no measurement behind it is worse than an empty panel, because somebody will
act on it. Three traps in this schema are worth naming, because each one is a
plausible report that would have been wrong:

* ``orders.updated_at`` is the last status change of **any** kind. It is not a
  delivered-at and is used nowhere below. The real one is the ``delivered``
  row of ``order_events``, which is why revenue joins it.
* ``products.last_cost`` is a *function* answering the newest supply line for
  a whole card, and ``sort_run`` deletes and re-inserts lines so the ids lie
  about which is newest. Margin is built on ``order_items.unit_cost``, frozen
  at checkout, and on nothing else.
* An order moved to ``returned`` has already left revenue, because revenue is
  delivered orders only. Subtracting its refund as well would count the
  reversal twice, so ``net`` subtracts only refunds whose order still counts.

**Two axes, deliberately.** Revenue is bucketed by the day the goods were
*delivered* — that is when the shop earned it — and order counts by the day the
order was *placed*, because a cancellation happened on the day somebody called
off a sale. Mixing them onto one axis would make the last day of any period
look like a collapse, since orders placed yesterday have not been delivered
yet.

**Grouped in SQL.** These are aggregates over every order the shop has ever
taken, and the neighbouring ``dashboard._sales`` loads fourteen days of orders
and buckets them in Python — fine for fourteen days and ruinous for a year. One
query per panel, and the days a query returns are rolled up into weeks and
months here, where there are at most a few hundred rows to roll.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, literal_column
from sqlalchemy.orm import aliased
from sqlmodel import col, func, select

from app import i18n
from app import schemas as s
from app.deps import AdminUser, SessionDep
from app.models import (
    SELLABLE_KINDS,
    AttemptResult,
    CountStatus,
    DeliveryAttempt,
    DeliveryKind,
    Location,
    LocationKind,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PickTask,
    Product,
    ProductVariant,
    ReturnInspection,
    ReturnRequest,
    ReturnStatus,
    StockCount,
    StockCountLine,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    Supply,
    SupplyLine,
    SupplyStatus,
    User,
    UserRole,
    utcnow,
)

router = APIRouter(prefix="/admin/reports", tags=["reports"])

# A month, because that is the window somebody means when they open the screen
# without choosing anything. Short enough to be about now and long enough that
# a quiet Tuesday does not look like a catastrophe.
DEFAULT_DAYS = 30

# Two years and a day. Not a performance limit — the queries group in SQL and
# would survive more — but a limit on the comparison: asking for five years
# compares them against the five before, which for a shop this age is a period
# that does not exist, and the arrow would point at nothing.
MAX_DAYS = 731

# How many rows a ranked list comes back with. Long enough to find the thing
# you are looking for, short enough that the screen is still a list of things
# to do rather than a second table to page through.
TOP = 20

# Bought before, nothing since. Two months, because this shop sells clothes and
# shoes: a customer who has not been back in two months has probably gone
# somewhere else, and one who has not been back in three weeks is simply
# somebody who does not need trainers this week.
LAPSED_AFTER_DAYS = 60

# On a shelf, nothing delivered since. Six weeks — long enough to survive a
# slow season, short enough that the goods have not yet been standing there
# long enough to be worth less than the rent.
DEAD_AFTER_DAYS = 45

# What counts as a full cell. The same figure the dashboard uses, and named
# here rather than imported so the two screens do not quietly diverge — the
# dashboard's is about a tile and this one is about a report.
FULL_AT_PERCENT = 80

# Hundredths of a per cent. Percentages are integers on the wire for the same
# reason money is: the apps format, and a float that renders as 12.340000001 in
# one client and 12.34 in another is a bug report nobody can reproduce.
PERCENT = 10_000

# What to put in a GROUP BY when a query is split by period rather than by day.
# Names the output column of ``Period.side`` — see the note there for why the
# expression itself cannot be repeated.
SIDE = literal_column("side")


# --------------------------------------------------------------------------- the period


@dataclass(frozen=True)
class Period:
    """What was asked for, and the stretch of days it is measured against.

    The previous period is **the same number of days, ending the day before
    this one begins**. Not "last month" and not "this month last year": those
    are different lengths and different numbers of weekends, and a shop that
    takes most of its money on a Saturday would see an arrow that was really
    about the calendar. Same length, immediately before, every time.
    """

    start: date
    end: date
    bucket: Literal["day", "week", "month"]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def previous_start(self) -> date:
        return self.start - timedelta(days=self.days)

    @property
    def previous_end(self) -> date:
        return self.start - timedelta(days=1)

    @property
    def floor(self) -> datetime:
        """Midnight at the start of the previous period.

        Both periods are read in one query wherever it is possible, so this is
        the bottom of the range and ``ceiling`` is the top. Two queries with
        two ranges would be two table scans for one screen.
        """
        return _midnight(self.previous_start)

    @property
    def ceiling(self) -> datetime:
        """Midnight at the *end* of the last day, exclusive.

        Exclusive rather than 23:59:59, which drops anything that happened in
        the last second of a day — rare, and the kind of missing order nobody
        ever finds.
        """
        return _midnight(self.end + timedelta(days=1))

    def side(self, column) -> object:
        """0 for the previous period, 1 for this one, as a SQL expression.

        Lets one grouped query answer both periods. Used where a query is not
        already grouped by day; where it is, the side is read off the day here
        and the database is not asked twice.

        **Group by ``SIDE``, never by this.** The expression carries a bound
        parameter, and Postgres compares a GROUP BY expression against the
        selected one *textually*: the same CASE rendered twice becomes
        ``$1`` and ``$4``, which do not match, and the query is refused with
        "column supplies.received_at must appear in the GROUP BY clause".
        SQLite accepts it, so the tests pass and production does not — which is
        the worst shape a bug can have. Both dialects accept a GROUP BY that
        names an output column instead, which is what ``SIDE`` is.
        """
        return case((col(column) < _midnight(self.start), 0), else_=1).label("side")

    def side_of(self, day: date) -> int:
        """The same answer for a day already in hand, without asking again.

        Where a query is grouped by day the side is a comparison and not a
        second column, and a query that asked for both would be grouping by a
        thing it can already derive.
        """
        return 0 if day < self.start else 1

    def out(self) -> s.ReportPeriodOut:
        return s.ReportPeriodOut(
            from_day=self.start,
            to_day=self.end,
            previous_from_day=self.previous_start,
            previous_to_day=self.previous_end,
            days=self.days,
            bucket=self.bucket,
        )


def period(
    from_day: date | None = Query(
        None, description="First day, inclusive. Default: 29 days before to_day"
    ),
    to_day: date | None = Query(None, description="Last day, inclusive. Default: today"),
    bucket: Literal["day", "week", "month"] = Query(
        "day", description="How the series is grouped. The headlines never change"
    ),
) -> Period:
    """The period, guarded in the signature, shared by every report.

    A dependency rather than three parameters repeated six times: the two
    refusals below would otherwise be written six times and would disagree
    with each other by the third.
    """
    end = to_day or utcnow().date()
    start = from_day or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("report_period_backwards")
        )
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            i18n.label("report_period_too_long", days=MAX_DAYS),
        )
    return Period(start=start, end=end, bucket=bucket)


PeriodDep = Annotated[Period, Depends(period)]


# --------------------------------------------------------------------------- sales


@router.get(
    "/sales",
    response_model=s.SalesReportOut,
    summary="Trade over a period, against the period before it",
)
def sales(user: AdminUser, session: SessionDep, span: PeriodDep) -> s.SalesReportOut:
    """Revenue, orders, and what happened to the ones that did not arrive.

    Four queries. Revenue and its two splits come off one grouped join, the
    order counts off another, refunds off a third, and the fourth is the
    honesty check — delivered orders with no ``delivered`` event to bucket by,
    which is the one way this report can silently understate itself.

    Revenue is **delivered orders only**, which is what ``staff.list_customers``
    already does and the only definition in the codebase that was right. A
    placed order is a promise and a cancelled one is nothing.
    """
    revenue_rows = session.exec(
        select(
            func.date(OrderEvent.happened_at),
            col(Order.payment_method),
            col(Order.delivery_kind),
            func.count(),
            func.coalesce(func.sum(Order.total), 0),
            func.coalesce(func.sum(Order.delivery_fee), 0),
            func.coalesce(func.sum(Order.discount), 0),
        )
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= span.floor,
            col(OrderEvent.happened_at) < span.ceiling,
        )
        .group_by(
            func.date(OrderEvent.happened_at),
            col(Order.payment_method),
            col(Order.delivery_kind),
        )
    ).all()

    status_rows = session.exec(
        select(
            func.date(Order.created_at),
            col(Order.status),
            func.count(),
        )
        .where(
            col(Order.created_at) >= span.floor,
            col(Order.created_at) < span.ceiling,
        )
        .group_by(func.date(Order.created_at), col(Order.status))
    ).all()

    refund_rows = session.exec(
        select(
            func.date(ReturnRequest.refunded_at),
            col(Order.status),
            func.coalesce(func.sum(ReturnRequest.refund_amount), 0),
        )
        .join(Order, col(Order.id) == col(ReturnRequest.order_id))
        .where(
            col(ReturnRequest.refunded_at) >= span.floor,
            col(ReturnRequest.refunded_at) < span.ceiling,
        )
        .group_by(func.date(ReturnRequest.refunded_at), col(Order.status))
    ).all()

    # Delivered, and no time to say when. Nought is the expected answer; every
    # road to a delivered order stamps the event. Anything else means the
    # revenue series above is missing that many orders, and the screen is told
    # rather than a log nobody reads.
    stamped = select(col(OrderEvent.order_id)).where(
        OrderEvent.status == OrderStatus.DELIVERED,
        col(OrderEvent.happened_at).is_not(None),
    )
    untimed = session.exec(
        select(func.count())
        .select_from(Order)
        .where(
            Order.status == OrderStatus.DELIVERED,
            col(Order.created_at) >= span.floor,
            col(Order.created_at) < span.ceiling,
            col(Order.id).not_in(stamped),
        )
    ).one()

    # ------------------------------------------------------------- fold it up
    # Every accumulator below is ``[previous, current]``, in that order, all
    # the way through this module — see ``figure``.
    revenue = [0, 0]
    delivered = [0, 0]
    fees = [0, 0]
    discounts = [0, 0]
    by_day_revenue: dict[date, int] = {}
    payments: dict[str, list[int]] = {}
    deliveries: dict[str, list[int]] = {}

    for day_value, method, kind, count, total, fee, discount in revenue_rows:
        day = day_of(day_value)
        side = span.side_of(day)
        revenue[side] += int(total)
        delivered[side] += int(count)
        fees[side] += int(fee)
        discounts[side] += int(discount)
        if side:
            by_day_revenue[day] = by_day_revenue.get(day, 0) + int(total)
        row = payments.setdefault(_enum(method), [0, 0, 0, 0])
        row[side * 2] += int(count)
        row[side * 2 + 1] += int(total)
        row = deliveries.setdefault(_enum(kind), [0, 0, 0, 0])
        row[side * 2] += int(count)
        row[side * 2 + 1] += int(total)

    placed = [0, 0]
    cancelled = [0, 0]
    returned = [0, 0]
    by_day_orders: dict[date, list[int]] = {}
    for day_value, order_status, count in status_rows:
        day = day_of(day_value)
        side = span.side_of(day)
        placed[side] += int(count)
        name = _enum(order_status)
        if name == OrderStatus.CANCELLED.value:
            cancelled[side] += int(count)
        if name == OrderStatus.RETURNED.value:
            returned[side] += int(count)
        if side:
            counts = by_day_orders.setdefault(day, [0, 0, 0])
            counts[0] += int(count)
            counts[1] += int(count) if name == OrderStatus.CANCELLED.value else 0
            counts[2] += int(count) if name == OrderStatus.RETURNED.value else 0

    refunds = [0, 0]
    refunds_against_revenue = [0, 0]
    by_day_refunds: dict[date, int] = {}
    for day_value, order_status, amount in refund_rows:
        day = day_of(day_value)
        side = span.side_of(day)
        refunds[side] += int(amount)
        # Only refunds on an order that is still counted as revenue. One whose
        # status was moved to `returned` has already dropped out of the
        # revenue figure above, so subtracting its refund as well would charge
        # the shop for the same reversal twice.
        if _enum(order_status) == OrderStatus.DELIVERED.value:
            refunds_against_revenue[side] += int(amount)
        if side:
            by_day_refunds[day] = by_day_refunds.get(day, 0) + int(amount)

    # Delivered orders per bucket, for the series only.
    delivered_by_day: dict[date, int] = {}
    for day_value, _method, _kind, count, *_ in revenue_rows:
        day = day_of(day_value)
        if span.side_of(day):
            delivered_by_day[day] = delivered_by_day.get(day, 0) + int(count)

    buckets = []
    for bucket_day, label, days in _bucket_days(span):
        buckets.append(
            s.SalesBucketOut(
                day=bucket_day,
                label=label,
                orders=sum(by_day_orders.get(d, [0, 0, 0])[0] for d in days),
                delivered=sum(delivered_by_day.get(d, 0) for d in days),
                cancelled=sum(by_day_orders.get(d, [0, 0, 0])[1] for d in days),
                returned=sum(by_day_orders.get(d, [0, 0, 0])[2] for d in days),
                revenue=sum(by_day_revenue.get(d, 0) for d in days),
                refunds=sum(by_day_refunds.get(d, 0) for d in days),
            )
        )

    net = [
        revenue[0] - refunds_against_revenue[0],
        revenue[1] - refunds_against_revenue[1],
    ]

    headlines = [
        figure("revenue", "fig_revenue", revenue, money=True),
        figure("orders", "fig_orders", placed),
        figure(
            "average_order",
            "fig_average_order",
            [_over(revenue[0], delivered[0]), _over(revenue[1], delivered[1])],
            money=True,
        ),
        figure("delivered", "fig_delivered", delivered),
        figure("cancelled", "fig_cancelled", cancelled),
        figure("returned", "fig_returned", returned),
        figure(
            "cancel_rate",
            "fig_cancel_rate",
            [_rate(cancelled[0], placed[0]), _rate(cancelled[1], placed[1])],
            percent_value=True,
        ),
        figure("delivery_fee", "fig_delivery_fee", fees, money=True),
        figure("discount", "fig_discount", discounts, money=True),
        figure("refunds", "fig_refunds", refunds, money=True),
        figure("net", "fig_net", net, money=True),
    ]

    return s.SalesReportOut(
        period=span.out(),
        headlines=headlines,
        buckets=buckets,
        by_payment=_split(payments, PaymentMethod, "split_"),
        by_delivery=_split(deliveries, DeliveryKind, "split_"),
        delivered_without_a_time=int(untimed),
    )


# --------------------------------------------------------------------------- money


@router.get(
    "/money",
    response_model=s.MoneyReportOut,
    summary="Cash in, cash out to the market, and the margin we can see",
)
def money(user: AdminUser, session: SessionDep, span: PeriodDep) -> s.MoneyReportOut:
    """What came in, what went out, and — honestly — what was left.

    ``difference`` is **cash in less cash out**, and the label says so in every
    language. It is not profit and it is not COGS-based anything: a market run
    that lands on the 3rd puts a month of buying into one day, and a month with
    two big runs in it can look like a disaster while the shop is doing well.
    Calling it "foyda" would be the single most misleading word available on
    this screen.

    Purchase cost is bucketed by ``supplies.received_at`` and is exact: the
    pile path makes ``unit_cost`` mandatory and greater than nought, so every
    line that exists has a real price on it.

    ``transport_cost`` is summed and reported on its own. It is nought
    everywhere today because no form sends one, and it is shown rather than
    hidden so that it stops being nought the moment somebody adds the field.
    """
    revenue_rows = session.exec(
        select(
            func.date(OrderEvent.happened_at),
            func.coalesce(func.sum(Order.total), 0),
        )
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= span.floor,
            col(OrderEvent.happened_at) < span.ceiling,
        )
        .group_by(func.date(OrderEvent.happened_at))
    ).all()

    cost_rows = session.exec(
        select(
            func.date(Supply.received_at),
            func.coalesce(func.sum(SupplyLine.unit_cost * SupplyLine.quantity), 0),
            func.coalesce(func.sum(SupplyLine.quantity), 0),
        )
        .join(Supply, col(Supply.id) == col(SupplyLine.supply_id))
        .where(
            Supply.status == SupplyStatus.RECEIVED,
            col(Supply.received_at) >= span.floor,
            col(Supply.received_at) < span.ceiling,
        )
        .group_by(func.date(Supply.received_at))
    ).all()

    # Runs and transport off the runs themselves. Not off the line join above:
    # a run with four lines would have its taxi fare counted four times, which
    # is the classic way a join quietly multiplies money.
    run_rows = session.exec(
        select(
            func.date(Supply.received_at),
            func.count(),
            func.coalesce(func.sum(Supply.transport_cost), 0),
        )
        .where(
            Supply.status == SupplyStatus.RECEIVED,
            col(Supply.received_at) >= span.floor,
            col(Supply.received_at) < span.ceiling,
        )
        .group_by(func.date(Supply.received_at))
    ).all()

    refund_rows = session.exec(
        select(
            func.date(ReturnRequest.refunded_at),
            func.coalesce(func.sum(ReturnRequest.refund_amount), 0),
        )
        .where(
            col(ReturnRequest.refunded_at) >= span.floor,
            col(ReturnRequest.refunded_at) < span.ceiling,
        )
        .group_by(func.date(ReturnRequest.refunded_at))
    ).all()

    market_rows = session.exec(
        select(
            col(Supply.place),
            span.side(Supply.received_at),
            func.count(func.distinct(Supply.id)),
            func.coalesce(func.sum(SupplyLine.unit_cost * SupplyLine.quantity), 0),
            func.coalesce(func.sum(SupplyLine.quantity), 0),
        )
        .join(Supply, col(Supply.id) == col(SupplyLine.supply_id))
        .where(
            Supply.status == SupplyStatus.RECEIVED,
            col(Supply.received_at) >= span.floor,
            col(Supply.received_at) < span.ceiling,
        )
        .group_by(col(Supply.place), SIDE)
    ).all()

    buyer_rows = session.exec(
        select(
            col(Supply.buyer_id),
            span.side(Supply.received_at),
            func.count(func.distinct(Supply.id)),
            func.coalesce(func.sum(SupplyLine.unit_cost * SupplyLine.quantity), 0),
        )
        .join(Supply, col(Supply.id) == col(SupplyLine.supply_id))
        .where(
            Supply.status == SupplyStatus.RECEIVED,
            col(Supply.received_at) >= span.floor,
            col(Supply.received_at) < span.ceiling,
        )
        .group_by(col(Supply.buyer_id), SIDE)
    ).all()

    margin = _margin(session, span)

    # ------------------------------------------------------------- fold it up
    money_in = [0, 0]
    money_out = [0, 0]
    refunds = [0, 0]
    units = [0, 0]
    runs = [0, 0]
    transport = [0, 0]
    in_by_day: dict[date, int] = {}
    out_by_day: dict[date, int] = {}
    refunds_by_day: dict[date, int] = {}

    for day_value, total in revenue_rows:
        day = day_of(day_value)
        money_in[span.side_of(day)] += int(total)
        if span.side_of(day):
            in_by_day[day] = in_by_day.get(day, 0) + int(total)
    for day_value, cost, quantity in cost_rows:
        day = day_of(day_value)
        money_out[span.side_of(day)] += int(cost)
        units[span.side_of(day)] += int(quantity)
        if span.side_of(day):
            out_by_day[day] = out_by_day.get(day, 0) + int(cost)
    for day_value, count, fare in run_rows:
        day = day_of(day_value)
        runs[span.side_of(day)] += int(count)
        transport[span.side_of(day)] += int(fare)
        money_out[span.side_of(day)] += int(fare)
        if span.side_of(day):
            out_by_day[day] = out_by_day.get(day, 0) + int(fare)
    for day_value, amount in refund_rows:
        day = day_of(day_value)
        refunds[span.side_of(day)] += int(amount)
        if span.side_of(day):
            refunds_by_day[day] = refunds_by_day.get(day, 0) + int(amount)

    buckets = []
    for bucket_day, label, days in _bucket_days(span):
        came_in = sum(in_by_day.get(d, 0) for d in days)
        went_out = sum(out_by_day.get(d, 0) for d in days)
        paid_back = sum(refunds_by_day.get(d, 0) for d in days)
        buckets.append(
            s.MoneyBucketOut(
                day=bucket_day,
                label=label,
                money_in=came_in,
                money_out=went_out,
                refunds=paid_back,
                difference=came_in - went_out - paid_back,
            )
        )

    markets: dict[str, list[int]] = {}
    for place, side, run_count, cost, quantity in market_rows:
        row = markets.setdefault(place or "", [0, 0, 0, 0])
        if int(side):
            row[0] += int(run_count)
            row[1] += int(quantity)
            row[2] += int(cost)
        else:
            row[3] += int(cost)

    buyers: dict[int | None, list[int]] = {}
    for buyer_id, side, run_count, cost in buyer_rows:
        row = buyers.setdefault(buyer_id, [0, 0, 0])
        if int(side):
            row[0] += int(run_count)
            row[1] += int(cost)
        else:
            row[2] += int(cost)
    names = _people(session, [b for b in buyers if b is not None])

    difference = [
        money_in[0] - money_out[0] - refunds[0],
        money_in[1] - money_out[1] - refunds[1],
    ]
    headlines = [
        figure("money_in", "fig_money_in", money_in, money=True),
        figure("money_out", "fig_money_out", money_out, money=True),
        figure("refunds", "fig_refunds", refunds, money=True),
        figure("difference", "fig_difference", difference, money=True),
        figure("runs", "fig_runs", runs),
        figure("units_bought", "fig_units_bought", units),
        figure(
            "average_run",
            "fig_average_run",
            [_over(money_out[0], runs[0]), _over(money_out[1], runs[1])],
            money=True,
        ),
        figure("transport", "fig_transport", transport, money=True),
        figure(
            "gross_margin",
            "fig_gross_margin",
            [margin.previous_margin, margin.value.margin],
            money=True,
        ),
    ]

    return s.MoneyReportOut(
        period=span.out(),
        headlines=headlines,
        buckets=buckets,
        by_market=sorted(
            (
                s.MarketSpendOut(
                    place=place or i18n.label("market_not_said"),
                    runs=row[0],
                    units=row[1],
                    cost=row[2],
                    previous_cost=row[3],
                )
                for place, row in markets.items()
            ),
            key=lambda row: -row.cost,
        ),
        by_buyer=sorted(
            (
                s.BuyerSpendOut(
                    buyer_id=buyer_id,
                    name=names.get(buyer_id, i18n.label("unknown_person")),
                    runs=row[0],
                    cost=row[1],
                    previous_cost=row[2],
                )
                for buyer_id, row in buyers.items()
            ),
            key=lambda row: -row.cost,
        ),
        margin=margin.value,
    )


@dataclass(frozen=True)
class _Margin:
    value: s.MarginOut
    previous_margin: int


def _margin(session: SessionDep, span: Period) -> _Margin:
    """Gross margin over the lines that carry a cost, and how many that was.

    **Only lines with a cost.** An order placed before ``order_items.unit_cost``
    existed has nought on every line, and nought is unknown rather than free —
    counting it would print a hundred per cent margin over the shop's whole
    history and somebody would price against it. So the sums below are over
    ``unit_cost > 0`` alone, and the coverage travels back with them so the
    screen can say "on 4 of 900 units" instead of "38%".

    ``known_from`` is the day the earliest order carrying any cost was placed.
    That is the honest floor for this whole panel: before it, margin is not
    nought, it is unknowable.
    """
    costed = col(OrderItem.unit_cost) > 0
    rows = session.exec(
        select(
            span.side(OrderEvent.happened_at),
            func.coalesce(
                func.sum(
                    case(
                        (costed, OrderItem.unit_price * OrderItem.quantity),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((costed, OrderItem.unit_cost * OrderItem.quantity), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(case((costed, OrderItem.quantity), else_=0)), 0
            ),
            func.coalesce(func.sum(OrderItem.quantity), 0),
        )
        .select_from(OrderItem)
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= span.floor,
            col(OrderEvent.happened_at) < span.ceiling,
        )
        .group_by(SIDE)
    ).all()

    revenue = [0, 0]
    cost = [0, 0]
    units_costed = [0, 0]
    units = [0, 0]
    for side, sold, paid, costed_units, all_units in rows:
        side = int(side)
        revenue[side] = int(sold)
        cost[side] = int(paid)
        units_costed[side] = int(costed_units)
        units[side] = int(all_units)

    # The first order that carries any cost at all. One query over the whole
    # history, and the only honest answer to "from when is this real".
    known_from = session.exec(
        select(func.min(Order.created_at))
        .select_from(OrderItem)
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .where(col(OrderItem.unit_cost) > 0)
    ).one()

    gross = revenue[1] - cost[1]
    return _Margin(
        value=s.MarginOut(
            revenue=revenue[1],
            cost=cost[1],
            margin=gross,
            margin_percent=_rate(gross, revenue[1]) if revenue[1] else None,
            units=units[1],
            units_costed=units_costed[1],
            coverage_percent=_rate(units_costed[1], units[1]),
            known_from=known_from.date() if known_from else None,
        ),
        previous_margin=revenue[0] - cost[0],
    )


# --------------------------------------------------------------------------- customers


@router.get(
    "/customers",
    response_model=s.CustomersReportOut,
    summary="Who is buying, who came back, and who has stopped",
)
def customers(
    user: AdminUser,
    session: SessionDep,
    span: PeriodDep,
    lapsed_after: int = Query(
        LAPSED_AFTER_DAYS, ge=7, le=730, description="Days of silence before lapsed"
    ),
) -> s.CustomersReportOut:
    """Signups, first-time against returning, and the call list.

    **An order is "first" if it is that user's earliest**, and earliest is
    ``min(id)`` rather than ``min(created_at)``: two orders placed in the same
    second would both match a timestamp comparison and the same customer would
    be counted as new twice. Ids are issued in order and exactly one row can
    hold the minimum.

    The lapsed list is the point of this screen. Somebody bought here, spent
    real money, and has not been back — that is a telephone call, and it is the
    only list in these reports that is a list of things to do. It cannot
    include somebody who never bought, because it is built from an inner join
    to their order history.

    Cohort retention by signup month was asked for and is **not** here — see
    the module note at the foot of this file.
    """
    signup_rows = session.exec(
        select(func.date(User.created_at), func.count())
        .where(
            User.role == UserRole.CUSTOMER,
            col(User.created_at) >= span.floor,
            col(User.created_at) < span.ceiling,
        )
        .group_by(func.date(User.created_at))
    ).all()

    firsts = (
        select(
            col(Order.user_id).label("user_id"),
            func.min(Order.id).label("first_id"),
        )
        .group_by(col(Order.user_id))
        .subquery()
    )
    order_rows = session.exec(
        select(
            func.date(Order.created_at),
            # Labelled and grouped by the label, for the reason written out on
            # ``Period.side``: Postgres matches a GROUP BY against the selected
            # expression textually, and the same CASE rendered twice carries
            # two different bound parameters.
            case((col(Order.id) == firsts.c.first_id, 1), else_=0).label("first"),
            func.count(),
        )
        .join(firsts, firsts.c.user_id == col(Order.user_id))
        .where(
            col(Order.created_at) >= span.floor,
            col(Order.created_at) < span.ceiling,
        )
        .group_by(func.date(Order.created_at), literal_column("first"))
    ).all()

    # How many people bought, and how many of them bought more than once —
    # counted in SQL off a grouped subquery rather than by loading every buyer
    # and counting in Python, which is the same shape the shelf map avoids.
    per_buyer = (
        select(
            col(Order.user_id).label("user_id"),
            span.side(Order.created_at),
            func.count().label("orders"),
        )
        .where(
            col(Order.created_at) >= span.floor,
            col(Order.created_at) < span.ceiling,
        )
        .group_by(col(Order.user_id), SIDE)
        .subquery()
    )
    buyer_rows = session.exec(
        select(
            per_buyer.c.side,
            func.count(),
            func.coalesce(func.sum(case((per_buyer.c.orders >= 2, 1), else_=0)), 0),
        ).group_by(per_buyer.c.side)
    ).all()

    history = (
        select(
            col(Order.user_id).label("user_id"),
            func.count().label("orders"),
            func.coalesce(
                func.sum(
                    case((Order.status == OrderStatus.DELIVERED, Order.total), else_=0)
                ),
                0,
            ).label("spent"),
            func.max(Order.created_at).label("last_order"),
        )
        .group_by(col(Order.user_id))
        .subquery()
    )
    top_rows = session.exec(
        select(User, history.c.orders, history.c.spent, history.c.last_order)
        .join(history, history.c.user_id == col(User.id))
        .order_by(func.coalesce(history.c.spent, 0).desc(), col(User.id))
        .limit(TOP)
    ).all()

    now = utcnow()
    cutoff = now - timedelta(days=lapsed_after)
    lapsed_rows = session.exec(
        select(User, history.c.orders, history.c.spent, history.c.last_order)
        .join(history, history.c.user_id == col(User.id))
        .where(history.c.last_order < cutoff)
        .order_by(func.coalesce(history.c.spent, 0).desc(), col(User.id))
        .limit(TOP)
    ).all()

    # ------------------------------------------------------------- fold it up
    signups = [0, 0]
    signups_by_day: dict[date, int] = {}
    for day_value, count in signup_rows:
        day = day_of(day_value)
        signups[span.side_of(day)] += int(count)
        if span.side_of(day):
            signups_by_day[day] = signups_by_day.get(day, 0) + int(count)

    orders = [0, 0]
    first_orders = [0, 0]
    orders_by_day: dict[date, list[int]] = {}
    for day_value, is_first, count in order_rows:
        day = day_of(day_value)
        side = span.side_of(day)
        orders[side] += int(count)
        if int(is_first):
            first_orders[side] += int(count)
        if side:
            row = orders_by_day.setdefault(day, [0, 0])
            row[0] += int(count)
            row[1] += int(count) if int(is_first) else 0

    buyers = [0, 0]
    repeat_buyers = [0, 0]
    for side, count, repeats in buyer_rows:
        buyers[int(side)] = int(count)
        repeat_buyers[int(side)] = int(repeats)

    buckets = []
    for bucket_day, label, days in _bucket_days(span):
        placed = sum(orders_by_day.get(d, [0, 0])[0] for d in days)
        first = sum(orders_by_day.get(d, [0, 0])[1] for d in days)
        buckets.append(
            s.CustomerBucketOut(
                day=bucket_day,
                label=label,
                signups=sum(signups_by_day.get(d, 0) for d in days),
                orders=placed,
                first_orders=first,
                repeat_orders=placed - first,
            )
        )

    headlines = [
        figure("signups", "fig_signups", signups),
        figure("buyers", "fig_buyers", buyers),
        figure("new_buyers", "fig_new_buyers", first_orders),
        figure(
            "returning_buyers",
            "fig_returning_buyers",
            [buyers[0] - first_orders[0], buyers[1] - first_orders[1]],
        ),
        figure(
            "repeat_rate",
            "fig_repeat_rate",
            [
                _rate(repeat_buyers[0], buyers[0]),
                _rate(repeat_buyers[1], buyers[1]),
            ],
            percent_value=True,
        ),
        # Hundredths of an order, for the same reason percentages are
        # hundredths of a per cent: 1.7 orders per customer is a real answer
        # and 1 is not, and the wire stays integers.
        figure(
            "orders_per_customer",
            "fig_orders_per_customer",
            [
                _over(orders[0] * 100, buyers[0]),
                _over(orders[1] * 100, buyers[1]),
            ],
        ),
    ]

    return s.CustomersReportOut(
        period=span.out(),
        headlines=headlines,
        buckets=buckets,
        top_customers=[_customer(row, now, lapsed=False) for row in top_rows],
        lapsed=[_customer(row, now, lapsed=True) for row in lapsed_rows],
        lapsed_after_days=lapsed_after,
    )


def _customer(row, now: datetime, *, lapsed: bool) -> s.CustomerRankOut:
    account, orders, spent, last_order = row
    return s.CustomerRankOut(
        user_id=account.id,
        name=account.full_name or "",
        phone=account.phone,
        orders=int(orders or 0),
        spent=int(spent or 0),
        last_order_at=last_order,
        days_since=(
            max(0, (now - last_order).days) if lapsed and last_order else 0
        ),
    )


# --------------------------------------------------------------------------- products


@router.get(
    "/products",
    response_model=s.ProductsReportOut,
    summary="What sold, what is rising, and what is standing still",
)
def products(
    user: AdminUser,
    session: SessionDep,
    span: PeriodDep,
    dead_after: int = Query(
        DEAD_AFTER_DAYS, ge=7, le=365, description="Days unsold before dead stock"
    ),
) -> s.ProductsReportOut:
    """Units **and so'm** per card and per cell, over two adjacent windows.

    Revenue per product is computable off ``order_items`` today and nothing in
    the back office shows it, so the shop could see what moved and not what it
    was worth. Those are different lists: a pile of socks tops one and a single
    coat tops the other, and only one of them is a reason to go back to the
    market.

    Rising and falling are the same figure over this period and the one before,
    differenced — which is why the aggregate is grouped by side rather than
    being run twice.

    Dead stock is valued at the **selling** price. What the shop paid is sunk;
    what it is still asking is what is standing still on a shelf.
    """
    sale_rows = session.exec(
        select(
            col(OrderItem.product_id),
            col(OrderItem.variant_id),
            span.side(OrderEvent.happened_at),
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), 0
            ),
        )
        .select_from(OrderItem)
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= span.floor,
            col(OrderEvent.happened_at) < span.ceiling,
        )
        .group_by(
            col(OrderItem.product_id),
            col(OrderItem.variant_id),
            SIDE,
        )
    ).all()

    by_product: dict[int | None, list[int]] = {}
    by_variant: dict[int, list[int]] = {}
    for product_id, variant_id, side, quantity, revenue in sale_rows:
        side = int(side)
        row = by_product.setdefault(product_id, [0, 0, 0, 0])
        row[side * 2] += int(quantity)
        row[side * 2 + 1] += int(revenue)
        if variant_id is not None:
            cell = by_variant.setdefault(int(variant_id), [0, 0, 0, 0])
            cell[side * 2] += int(quantity)
            cell[side * 2 + 1] += int(revenue)

    titles = _titles(session, [p for p in by_product if p is not None])
    cells = _cells(session, list(by_variant))

    product_rows = sorted(
        (
            s.ProductSaleOut(
                product_id=product_id,
                title=titles.get(product_id, ""),
                units=row[2],
                revenue=row[3],
                previous_units=row[0],
                previous_revenue=row[1],
                delta_units=row[2] - row[0],
                delta_revenue=row[3] - row[1],
            )
            for product_id, row in by_product.items()
        ),
        key=lambda row: -row.revenue,
    )

    variant_rows = sorted(
        (
            s.VariantSaleOut(
                variant_id=variant_id,
                product_id=cells.get(variant_id, _Cell()).product_id,
                product_title=cells.get(variant_id, _Cell()).title,
                variant_label=cells.get(variant_id, _Cell()).label,
                units=row[2],
                revenue=row[3],
                previous_units=row[0],
                stock_left=cells.get(variant_id, _Cell()).stock_left,
                sell_through_percent=_rate_or_none(
                    row[2], row[2] + cells.get(variant_id, _Cell()).stock_left
                ),
            )
            for variant_id, row in by_variant.items()
        ),
        key=lambda row: -row.revenue,
    )

    # Standing on a shelf, and nobody has taken one out of the building since
    # the cutoff. Off the ledger's deliveries rather than off order lines: an
    # order placed and never delivered moved nothing, and counting it would
    # make goods that have never left look alive.
    cutoff = utcnow() - timedelta(days=dead_after)
    moved = select(col(StockMovement.variant_id)).where(
        StockMovement.kind == StockMovementKind.DELIVERED,
        col(StockMovement.created_at) >= cutoff,
    )
    dead_where = (
        ProductVariant.stock_left > 0,
        col(ProductVariant.retired).is_(False),
        col(ProductVariant.id).not_in(moved),
    )
    dead_total = session.exec(
        select(
            func.count(),
            func.coalesce(
                func.sum(ProductVariant.stock_left * ProductVariant.price), 0
            ),
        )
        .select_from(ProductVariant)
        .where(*dead_where)
    ).one()
    dead_rows = session.exec(
        select(ProductVariant, Product.title)
        .join(Product, col(Product.id) == col(ProductVariant.product_id))
        .where(*dead_where)
        .order_by(
            (col(ProductVariant.stock_left) * col(ProductVariant.price)).desc(),
            col(ProductVariant.id),
        )
        .limit(TOP)
    ).all()
    last_seen = _last_delivered(session, [v.id for v, _ in dead_rows])

    units = [
        sum(row[0] for row in by_product.values()),
        sum(row[2] for row in by_product.values()),
    ]
    revenue = [
        sum(row[1] for row in by_product.values()),
        sum(row[3] for row in by_product.values()),
    ]
    sold_cards = [
        sum(1 for row in by_product.values() if row[0]),
        sum(1 for row in by_product.values() if row[2]),
    ]

    headlines = [
        figure("units_sold", "fig_units_sold", units),
        figure("revenue", "fig_revenue", revenue, money=True),
        figure("products_sold", "fig_products_sold", sold_cards),
        # No previous. The shop knows what is standing still today and keeps no
        # record of what was standing still a month ago, so there is nothing
        # honest to compare it against.
        _point("dead_stock", "fig_dead_stock", int(dead_total[0])),
        _point(
            "dead_stock_value",
            "fig_dead_stock_value",
            int(dead_total[1]),
            money=True,
        ),
    ]

    return s.ProductsReportOut(
        period=span.out(),
        headlines=headlines,
        products=product_rows[:TOP],
        variants=variant_rows[:TOP],
        # Only what actually moved. Sorting the whole list both ways and
        # taking the ends would fill "falling" with the cards that rose least
        # on a week when nothing fell at all — a panel headed "going down"
        # listing four products that are going up.
        rising=sorted(
            (row for row in product_rows if row.delta_revenue > 0),
            key=lambda row: -row.delta_revenue,
        )[:TOP],
        falling=sorted(
            (row for row in product_rows if row.delta_revenue < 0),
            key=lambda row: row.delta_revenue,
        )[:TOP],
        dead_stock=[
            s.DeadStockOut(
                variant_id=variant.id,
                product_id=variant.product_id,
                product_title=title,
                variant_label=_label(variant),
                stock_left=variant.stock_left,
                unit_price=variant.price,
                shelf_value=variant.stock_left * variant.price,
                last_delivered_at=last_seen.get(variant.id),
            )
            for variant, title in dead_rows
        ],
        dead_after_days=dead_after,
    )


# --------------------------------------------------------------------------- stock


@router.get(
    "/stock",
    response_model=s.StockReportOut,
    summary="What is in the building, split by the kind of place it stands in",
)
def stock(user: AdminUser, session: SessionDep, span: PeriodDep) -> s.StockReportOut:
    """Stock value at selling price, **split by what the place is for**.

    That split is the valuable one. "The shop holds 94 million so'm of stock"
    is a figure nobody can do anything with; "eleven million of it is in the
    damaged corner and four million is returns nobody has opened" is a
    morning's work with a clear outcome. Sellable bins, the receiving desk, the
    packing bench, courier bags, damage and uninspected returns are six
    different answers to "why is the money not moving".

    Valued at the **selling** price throughout, which is the number that makes
    somebody act. Costed stock value would want a lot-level cost and this
    system has one only from the day ``product_variants.last_cost`` started
    being kept — so it is not claimed here at all.

    Stocktake accuracy comes off ``stock_count_lines``, which keeps both what
    the system expected and what the person found. Nothing surfaces it today,
    and it is the only measure there is of whether the ledger and the room
    agree.
    """
    kind_rows = session.exec(
        select(
            col(Location.kind),
            func.coalesce(func.sum(StockPlacement.qty), 0),
            func.coalesce(func.sum(StockPlacement.qty * ProductVariant.price), 0),
            func.count(func.distinct(StockPlacement.variant_id)),
        )
        .join(Location, col(Location.id) == col(StockPlacement.location_id))
        .join(
            ProductVariant, col(ProductVariant.id) == col(StockPlacement.variant_id)
        )
        .where(StockPlacement.qty > 0)
        .group_by(col(Location.kind))
    ).all()

    cells = session.exec(
        select(col(Location.id), col(Location.capacity)).where(
            Location.kind == LocationKind.BIN, col(Location.is_active).is_(True)
        )
    ).all()
    held = {
        int(location_id): int(units)
        for location_id, units in session.exec(
            select(
                col(StockPlacement.location_id),
                func.coalesce(func.sum(StockPlacement.qty), 0),
            ).group_by(col(StockPlacement.location_id))
        ).all()
    }

    movement_rows = session.exec(
        select(
            col(StockMovement.kind),
            span.side(StockMovement.created_at),
            func.coalesce(func.sum(StockMovement.qty), 0),
        )
        .where(
            col(StockMovement.kind).in_(
                [StockMovementKind.WRITE_OFF, StockMovementKind.DAMAGE]
            ),
            col(StockMovement.created_at) >= span.floor,
            col(StockMovement.created_at) < span.ceiling,
        )
        .group_by(col(StockMovement.kind), SIDE)
    ).all()

    # Closed counts only. An open one is somebody still walking the cell, and
    # its lines are half-written — reading them would say the shelf is wildly
    # wrong when in fact nobody has finished looking.
    count_rows = session.exec(
        select(
            span.side(StockCount.closed_at),
            func.count(func.distinct(StockCount.id)),
            func.count(),
            func.coalesce(
                func.sum(
                    case(
                        (
                            col(StockCountLine.counted_qty)
                            != col(StockCountLine.expected_qty),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(StockCountLine.expected_qty), 0),
            func.coalesce(func.sum(StockCountLine.counted_qty), 0),
            func.coalesce(
                func.sum(
                    func.abs(
                        col(StockCountLine.counted_qty)
                        - col(StockCountLine.expected_qty)
                    )
                ),
                0,
            ),
        )
        .select_from(StockCountLine)
        .join(StockCount, col(StockCount.id) == col(StockCountLine.count_id))
        .where(
            StockCount.status == CountStatus.CLOSED,
            col(StockCount.closed_at) >= span.floor,
            col(StockCount.closed_at) < span.ceiling,
        )
        .group_by(SIDE)
    ).all()

    # ------------------------------------------------------------- fold it up
    by_kind = []
    total_units = total_value = 0
    sellable_value = damaged_value = 0
    for kind, units, value, variants in kind_rows:
        name = LocationKind(_enum(kind))
        total_units += int(units)
        total_value += int(value)
        if name in SELLABLE_KINDS:
            sellable_value += int(value)
        if name is LocationKind.DAMAGED:
            damaged_value += int(value)
        by_kind.append(
            s.StockKindOut(
                kind=name,
                label=i18n.label(f"kind_{name.value}"),
                units=int(units),
                value=int(value),
                variants=int(variants),
            )
        )
    by_kind.sort(key=lambda row: -row.value)

    full = sum(
        1
        for location_id, capacity in cells
        if capacity and held.get(int(location_id), 0) / capacity * 100 >= FULL_AT_PERCENT
    )
    empty = sum(1 for location_id, _ in cells if not held.get(int(location_id), 0))

    written_off = [0, 0]
    damaged_units = [0, 0]
    for kind, side, quantity in movement_rows:
        bucket = (
            written_off
            if _enum(kind) == StockMovementKind.WRITE_OFF.value
            else damaged_units
        )
        bucket[int(side)] += int(quantity)

    takes = [_stocktake(None), _stocktake(None)]
    for row in count_rows:
        takes[int(row[0])] = _stocktake(row)

    headlines = [
        _point("stock_value", "fig_stock_value", total_value, money=True),
        _point("stock_units", "fig_stock_units", total_units),
        _point("sellable_value", "fig_sellable_value", sellable_value, money=True),
        _point("damaged_value", "fig_damaged_value", damaged_value, money=True),
        _point("cells_full", "fig_cells_full", full),
        _point("cells_empty", "fig_cells_empty", empty),
        figure("written_off", "fig_written_off", written_off),
        figure("damaged_units", "fig_damaged_units", damaged_units),
    ]
    # Only when somebody counted something.
    #
    # A nought here would say the shelf was nought per cent right, on a week
    # when nobody opened a count — and a nought in the *previous* slot would
    # then draw an arrow shooting upwards on the first week anybody did. So a
    # week with no stocktake has no accuracy headline, and the panel below says
    # the same thing with a null.
    if takes[1].accuracy_percent is not None:
        headlines.append(
            s.FigureOut(
                key="stocktake_accuracy",
                label=i18n.label("fig_stocktake_accuracy"),
                value=takes[1].accuracy_percent,
                previous=takes[0].accuracy_percent,
                delta=(
                    takes[1].accuracy_percent - takes[0].accuracy_percent
                    if takes[0].accuracy_percent is not None
                    else None
                ),
                percent_value=True,
            )
        )

    return s.StockReportOut(
        period=span.out(),
        headlines=headlines,
        by_kind=by_kind,
        cells=len(cells),
        cells_full=full,
        cells_empty=empty,
        stocktake=takes[1],
        previous_stocktake=takes[0],
    )


def _stocktake(row) -> s.StocktakeOut:
    if row is None:
        return s.StocktakeOut(
            counts=0,
            lines=0,
            lines_wrong=0,
            expected_units=0,
            counted_units=0,
            miscounted_units=0,
            accuracy_percent=None,
        )
    _side, counts, lines, wrong, expected, counted, missed = row
    return s.StocktakeOut(
        counts=int(counts),
        lines=int(lines),
        lines_wrong=int(wrong),
        expected_units=int(expected),
        counted_units=int(counted),
        miscounted_units=int(missed),
        # Expected less the total miscount, over expected. Null when nothing
        # was counted: a hundred per cent accuracy over nought lines is the
        # most misleading figure this whole report could produce.
        accuracy_percent=(
            _rate(max(0, int(expected) - int(missed)), int(expected))
            if int(expected)
            else None
        ),
    )


# --------------------------------------------------------------------------- operations


@router.get(
    "/operations",
    response_model=s.OperationsReportOut,
    summary="The door, the bench, and what came back",
)
def operations(
    user: AdminUser, session: SessionDep, span: PeriodDep
) -> s.OperationsReportOut:
    """Deliveries, first-attempt success, how long the work takes, and returns.

    **First-attempt success is measured on the order, not the knock.** The
    naive figure — deliveries over attempts — improves when a courier gives up
    quickly and gets worse when they try again, which is backwards. So the
    first attempt on each order is found by ``min(id)`` over every attempt that
    order ever had, and the question asked of it is whether that one succeeded.

    Durations are averaged **and** given a median, because one parcel that sat
    over a weekend moves an average and does not move a middle one. They are
    the only figures here computed outside SQL: subtracting two timestamps is
    dialect-specific (``julianday`` against ``extract(epoch …)``) and a median
    wants the rows anyway, so the two columns are pulled and the arithmetic is
    done here. See the note at the foot of the file about what that costs.

    The approve/reject ratio is over requests **opened** in the period, showing
    where each of them ended up. One opened yesterday and not yet decided
    counts as submitted, which is the truth about it.
    """
    attempt_rows = session.exec(
        select(
            col(DeliveryAttempt.courier_id),
            col(DeliveryAttempt.result),
            span.side(DeliveryAttempt.happened_at),
            func.count(),
            func.coalesce(func.sum(DeliveryAttempt.cash_collected), 0),
        )
        .where(
            col(DeliveryAttempt.happened_at) >= span.floor,
            col(DeliveryAttempt.happened_at) < span.ceiling,
        )
        .group_by(
            col(DeliveryAttempt.courier_id),
            col(DeliveryAttempt.result),
            SIDE,
        )
    ).all()

    firsts = (
        select(
            col(DeliveryAttempt.order_id).label("order_id"),
            func.min(DeliveryAttempt.id).label("first_id"),
        )
        .group_by(col(DeliveryAttempt.order_id))
        .subquery()
    )
    first_rows = session.exec(
        select(
            span.side(DeliveryAttempt.happened_at),
            col(DeliveryAttempt.result),
            func.count(),
        )
        .join(firsts, firsts.c.first_id == col(DeliveryAttempt.id))
        .where(
            col(DeliveryAttempt.happened_at) >= span.floor,
            col(DeliveryAttempt.happened_at) < span.ceiling,
        )
        .group_by(SIDE, col(DeliveryAttempt.result))
    ).all()

    failure_rows = session.exec(
        select(
            col(DeliveryAttempt.reason),
            span.side(DeliveryAttempt.happened_at),
            func.count(),
        )
        .where(
            DeliveryAttempt.result == AttemptResult.FAILED,
            col(DeliveryAttempt.happened_at) >= span.floor,
            col(DeliveryAttempt.happened_at) < span.ceiling,
        )
        .group_by(col(DeliveryAttempt.reason), SIDE)
    ).all()

    placed_event = aliased(OrderEvent)
    done_event = aliased(OrderEvent)
    fulfilment_rows = session.exec(
        select(done_event.happened_at, placed_event.happened_at)
        .select_from(done_event)
        .join(
            placed_event,
            and_(
                placed_event.order_id == done_event.order_id,
                placed_event.status == OrderStatus.PLACED,
                col(placed_event.happened_at).is_not(None),
            ),
        )
        .where(
            done_event.status == OrderStatus.DELIVERED,
            col(done_event.happened_at) >= span.floor,
            col(done_event.happened_at) < span.ceiling,
        )
    ).all()

    pick_rows = session.exec(
        select(
            col(PickTask.finished_at),
            col(PickTask.created_at),
            col(PickTask.taken_at),
        ).where(
            col(PickTask.finished_at) >= span.floor,
            col(PickTask.finished_at) < span.ceiling,
        )
    ).all()

    return_rows = session.exec(
        select(
            col(ReturnRequest.status),
            span.side(ReturnRequest.created_at),
            func.count(),
        )
        .where(
            col(ReturnRequest.created_at) >= span.floor,
            col(ReturnRequest.created_at) < span.ceiling,
        )
        .group_by(col(ReturnRequest.status), SIDE)
    ).all()

    reason_rows = session.exec(
        select(
            col(ReturnRequest.reason),
            span.side(ReturnRequest.created_at),
            func.count(),
        )
        .where(
            col(ReturnRequest.created_at) >= span.floor,
            col(ReturnRequest.created_at) < span.ceiling,
        )
        .group_by(col(ReturnRequest.reason), SIDE)
    ).all()

    inspection_rows = session.exec(
        select(
            col(ReturnRequest.inspection),
            span.side(ReturnRequest.inspected_at),
            func.count(),
        )
        .where(
            col(ReturnRequest.inspected_at) >= span.floor,
            col(ReturnRequest.inspected_at) < span.ceiling,
        )
        .group_by(
            col(ReturnRequest.inspection), SIDE
        )
    ).all()

    delivered_rows = session.exec(
        select(span.side(OrderEvent.happened_at), func.count())
        .select_from(Order)
        .join(OrderEvent, col(OrderEvent.order_id) == col(Order.id))
        .where(
            Order.status == OrderStatus.DELIVERED,
            OrderEvent.status == OrderStatus.DELIVERED,
            col(OrderEvent.happened_at) >= span.floor,
            col(OrderEvent.happened_at) < span.ceiling,
        )
        .group_by(SIDE)
    ).all()

    # ------------------------------------------------------------- fold it up
    couriers: dict[int, list[int]] = {}
    delivered = [0, 0]
    failed = [0, 0]
    cash = [0, 0]
    for courier_id, result, side, count, collected in attempt_rows:
        side = int(side)
        row = couriers.setdefault(int(courier_id), [0, 0, 0, 0, 0])
        won = _enum(result) == AttemptResult.DELIVERED.value
        if side:
            row[0] += int(count) if won else 0
            row[1] += int(count) if not won else 0
            row[2] += int(collected)
        else:
            row[3] += int(count) if won else 0
        if won:
            delivered[side] += int(count)
        else:
            failed[side] += int(count)
        cash[side] += int(collected)

    first_won = [0, 0]
    first_all = [0, 0]
    for side, result, count in first_rows:
        side = int(side)
        first_all[side] += int(count)
        if _enum(result) == AttemptResult.DELIVERED.value:
            first_won[side] += int(count)

    names = _people(session, list(couriers))
    courier_rows = sorted(
        (
            s.CourierRowOut(
                courier_id=courier_id,
                name=names.get(courier_id, i18n.label("unknown_person")),
                phone=_phones(session).get(courier_id, ""),
                attempts=row[0] + row[1],
                delivered=row[0],
                failed=row[1],
                success_percent=_rate_or_none(row[0], row[0] + row[1]),
                cash_collected=row[2],
                previous_delivered=row[3],
            )
            for courier_id, row in couriers.items()
        ),
        key=lambda row: -row.delivered,
    )

    opened = [0, 0]
    approved = [0, 0]
    rejected = [0, 0]
    for return_status, side, count in return_rows:
        side = int(side)
        opened[side] += int(count)
        name = _enum(return_status)
        if name in (ReturnStatus.APPROVED.value, ReturnStatus.REFUNDED.value):
            approved[side] += int(count)
        if name == ReturnStatus.REJECTED.value:
            rejected[side] += int(count)

    inspected_ok = [0, 0]
    inspected_damaged = [0, 0]
    for inspection, side, count in inspection_rows:
        side = int(side)
        if inspection is None:
            continue
        if _enum(inspection) == ReturnInspection.OK.value:
            inspected_ok[side] += int(count)
        else:
            inspected_damaged[side] += int(count)

    delivered_orders = [0, 0]
    for side, count in delivered_rows:
        delivered_orders[int(side)] = int(count)

    fulfilment = ([], [])
    for finished, started in fulfilment_rows:
        if finished is None or started is None:
            continue
        fulfilment[span.side_of(finished.date())].append(
            (finished - started).total_seconds() / 60
        )
    waiting = ([], [])
    picking = ([], [])
    for finished, created, taken in pick_rows:
        if finished is None:
            continue
        side = span.side_of(finished.date())
        if taken is not None:
            waiting[side].append((taken - created).total_seconds() / 60)
            picking[side].append((finished - taken).total_seconds() / 60)

    headlines = [
        figure("deliveries", "fig_deliveries", delivered),
        figure("attempts", "fig_attempts", [delivered[0] + failed[0], delivered[1] + failed[1]]),
        figure(
            "first_attempt",
            "fig_first_attempt",
            [_rate(first_won[0], first_all[0]), _rate(first_won[1], first_all[1])],
            percent_value=True,
        ),
        figure("cash_collected", "fig_cash_collected", cash, money=True),
        figure("returns_opened", "fig_returns_opened", opened),
        figure(
            "returns_rate",
            "fig_returns_rate",
            [
                _rate(opened[0], delivered_orders[0]),
                _rate(opened[1], delivered_orders[1]),
            ],
            percent_value=True,
        ),
        figure("returns_approved", "fig_returns_approved", approved),
        figure("returns_rejected", "fig_returns_rejected", rejected),
        figure("inspected_ok", "fig_inspected_ok", inspected_ok),
        figure("inspected_damaged", "fig_inspected_damaged", inspected_damaged),
    ]

    return s.OperationsReportOut(
        period=span.out(),
        headlines=headlines,
        couriers=courier_rows,
        failure_reasons=_reasons(failure_rows),
        return_reasons=_reasons(reason_rows),
        durations=[
            _duration("fulfilment", "dur_fulfilment", fulfilment),
            _duration("pick_wait", "dur_pick_wait", waiting),
            _duration("pick_work", "dur_pick_work", picking),
        ],
    )


# --------------------------------------------------------------------------- pieces


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day)


def day_of(value) -> date:
    """``func.date`` answers a string on SQLite and a date on Postgres.

    Public, and imported by ``routers.dashboard``: one dialect answer, not two.

    One line here rather than a dialect branch in six places. The application
    never asks which database it is on — ``app.db`` is where that lives — and a
    report that worked in the tests and not in production because of this would
    be found by the owner rather than by the suite.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _enum(value) -> str:
    """The stored string, whichever of the two the driver handed back."""
    return value.value if hasattr(value, "value") else str(value)


def _over(total: int, count: int) -> int:
    """An average that is nought when there is nothing to average.

    Not a division by nought and not a null: every caller here is a headline
    that must render, and "no orders, so no average order" is nought on the
    screen with the count beside it saying why.
    """
    return int(total // count) if count else 0


def _rate(part: int, whole: int) -> int:
    """A share, in hundredths of a per cent. Nought when there is no whole."""
    return int(round(part * PERCENT / whole)) if whole else 0


def _rate_or_none(part: int, whole: int) -> int | None:
    """The same, but null rather than nought when there is nothing to divide.

    Used where nought would be a claim — a courier who knocked on no doors has
    no success rate, and drawing them at 0% would put them at the bottom of a
    league table they never entered.
    """
    return _rate(part, whole) if whole else None


def figure(
    key: str,
    label_key: str,
    pair: list[int],
    *,
    money: bool = False,
    percent_value: bool = False,
) -> s.FigureOut:
    """``pair`` is ``[previous, current]`` throughout, and never the other way.

    Public, because the dashboard's headlines are made with it too. One place
    decides what a comparison is and how a percentage against nought is
    reported, so the two screens cannot answer the same question differently.

    One order, everywhere, because the two are the same type and a swapped
    pair produces a report that is wrong in a way no test catches unless it
    looks at the sign.
    """
    previous, value = pair[0], pair[1]
    return s.FigureOut(
        key=key,
        label=i18n.label(label_key),
        value=value,
        previous=previous,
        delta=value - previous,
        percent=(
            round((value - previous) / previous * 100, 1) if previous else None
        ),
        money=money,
        percent_value=percent_value,
    )


def _point(
    key: str, label_key: str, value: int, *, money: bool = False
) -> s.FigureOut:
    """A figure about now, with nothing honest to compare it against.

    What is on the shelves today is a fact; what was on them a month ago is
    not recorded anywhere, and there is no ledger of placements over time to
    reconstruct it from. So these arrive with a null previous and the screen
    draws no arrow, rather than an arrow computed against a nought.
    """
    return s.FigureOut(
        key=key,
        label=i18n.label(label_key),
        value=value,
        previous=None,
        delta=None,
        money=money,
    )


def _split(rows: dict[str, list[int]], enum, prefix: str) -> list[s.SplitRowOut]:
    """A revenue split, with every member of the enum present.

    Every one, including the ones with nothing in them: a split that omits
    "cash" on a week when nobody paid cash reads as a shop that does not take
    cash, and the reader cannot tell the difference between nought and absent.
    """
    out = []
    for member in enum:
        row = rows.get(member.value, [0, 0, 0, 0])
        out.append(
            s.SplitRowOut(
                key=member.value,
                label=i18n.label(f"{prefix}{member.value}"),
                previous_orders=row[0],
                previous_revenue=row[1],
                orders=row[2],
                revenue=row[3],
            )
        )
    return sorted(out, key=lambda row: -row.revenue)


def _reasons(rows) -> list[s.ReasonRowOut]:
    """Free-text reasons, commonest first, with the blank one kept visible."""
    tally: dict[str, list[int]] = {}
    for reason, side, count in rows:
        row = tally.setdefault((reason or "").strip(), [0, 0])
        row[int(side)] += int(count)
    total = sum(row[1] for row in tally.values())
    return sorted(
        (
            s.ReasonRowOut(
                reason=reason or i18n.label("reason_not_given"),
                count=row[1],
                previous=row[0],
                share_percent=_rate(row[1], total),
            )
            for reason, row in tally.items()
        ),
        key=lambda row: -row.count,
    )


def _duration(key: str, label_key: str, pair: tuple[list, list]) -> s.DurationOut:
    """Minutes, with the middle one as well as the mean.

    Null rather than nought when nothing was measured. Nought minutes is a
    claim that the work is instant, and on a quiet week that is exactly what a
    screen would print.
    """
    previous, current = pair
    return s.DurationOut(
        key=key,
        label=i18n.label(label_key),
        samples=len(current),
        average_minutes=int(statistics.fmean(current)) if current else None,
        median_minutes=int(statistics.median(current)) if current else None,
        previous_average_minutes=(
            int(statistics.fmean(previous)) if previous else None
        ),
    )


@dataclass(frozen=True)
class _Cell:
    """What a variant is called and what is left of it, for the sales lists."""

    product_id: int | None = None
    title: str = ""
    label: str = ""
    stock_left: int = 0


def _titles(session: SessionDep, product_ids: list[int]) -> dict[int, str]:
    """One lookup for every card on the page, not one per row."""
    if not product_ids:
        return {}
    rows = session.exec(
        select(col(Product.id), col(Product.title)).where(
            col(Product.id).in_(product_ids)
        )
    ).all()
    return {int(product_id): title for product_id, title in rows}


def _cells(session: SessionDep, variant_ids: list[int]) -> dict[int, _Cell]:
    """The same for the grid cells, with the card's title joined on."""
    if not variant_ids:
        return {}
    rows = session.exec(
        select(ProductVariant, Product.title)
        .join(Product, col(Product.id) == col(ProductVariant.product_id))
        .where(col(ProductVariant.id).in_(variant_ids))
    ).all()
    return {
        variant.id: _Cell(
            product_id=variant.product_id,
            title=title,
            label=_label(variant),
            stock_left=variant.stock_left,
        )
        for variant, title in rows
    }


def _label(variant: ProductVariant) -> str:
    """"Qora · 42". Written here rather than imported from ``services``: that
    one is the customer's label and is allowed to change with the app."""
    return " · ".join(part for part in (variant.colour, variant.size) if part)


def _last_delivered(
    session: SessionDep, variant_ids: list[int]
) -> dict[int, datetime]:
    """When one of each of these last left the building. One grouped query."""
    if not variant_ids:
        return {}
    rows = session.exec(
        select(col(StockMovement.variant_id), func.max(StockMovement.created_at))
        .where(
            StockMovement.kind == StockMovementKind.DELIVERED,
            col(StockMovement.variant_id).in_(variant_ids),
        )
        .group_by(col(StockMovement.variant_id))
    ).all()
    return {int(variant_id): when for variant_id, when in rows if when}


def _people(session: SessionDep, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = session.exec(
        select(col(User.id), col(User.full_name), col(User.phone)).where(
            col(User.id).in_(user_ids)
        )
    ).all()
    return {
        int(user_id): (full_name or phone) for user_id, full_name, phone in rows
    }


def _phones(session: SessionDep) -> dict[int, str]:
    """Staff numbers, for the courier table. Couriers are a handful of rows."""
    rows = session.exec(
        select(col(User.id), col(User.phone)).where(User.role == UserRole.COURIER)
    ).all()
    return {int(user_id): phone for user_id, phone in rows}


def _bucket_start(day: date, bucket: str) -> date:
    if bucket == "week":
        return day - timedelta(days=day.weekday())
    if bucket == "month":
        return day.replace(day=1)
    return day


def _bucket_days(span: Period) -> list[tuple[date, str, list[date]]]:
    """Every bucket in the period, in order, each with the days it covers.

    Built from the calendar rather than from the rows, so a week nothing was
    sold in is present and empty. A chart that drops quiet days draws a shop
    that was busy every day it was open, which is the opposite of what somebody
    opening this screen wants to know.

    A week or month bucket is clipped to the period at both ends: asking for
    the 10th to the 20th and being shown a bar covering the whole month would
    make the figure look bigger than what was asked for.
    """
    order: list[date] = []
    days: dict[date, list[date]] = {}
    for offset in range(span.days):
        day = span.start + timedelta(days=offset)
        start = _bucket_start(day, span.bucket)
        if start not in days:
            days[start] = []
            order.append(start)
        days[start].append(day)
    return [(start, _bucket_label(start, days[start], span.bucket), days[start]) for start in order]


def _bucket_label(start: date, days: list[date], bucket: str) -> str:
    """What goes on the axis, written here because three clients would write it
    three ways and one of them would get the Uzbek month names wrong."""
    if bucket == "month":
        return f"{i18n.month_name(start.month)} {start.year}"
    if bucket == "week":
        return f"{i18n.format_date(days[0])} – {i18n.format_date(days[-1])}"
    return i18n.format_date(start)


# What is deliberately absent, so the next person does not go looking.
#
# **Conversion, traffic, sessions, visits, funnels, cart abandonment, route
# efficiency, supplier performance.** Nothing records any of them. A conversion
# rate needs visits and this system has never seen one; a cart abandonment rate
# would be computed off basket rows that are deleted at checkout, so it would
# measure deletion; route efficiency needs a route and a courier's round is an
# ordered list with no distances on it; supplier performance needs a supplier
# and nobody delivers to this shop — the owner goes to the market himself, which
# is what ``supplies.buyer_id`` is for and why "spend by buyer" is here instead.
#
# **Cohort retention by signup month.** Computable — signup month against first
# order month is one grouped query — and cut anyway. A cohort matrix is a
# screen of its own, every cell of it is a number that needs a paragraph, and
# the owner's complaint about the reports that were here was precisely that
# they were fluff. It can come back when somebody asks a question it answers.
#
# **Costed stock value.** Stock value is at the selling price only. Valuing
# what is on the shelf at cost wants a cost per lot, and ``last_cost`` is the
# newest lot's — so a cell holding goods from three runs would be valued at
# whichever price the last one happened to be. That is a plausible-looking
# number with nothing behind it.
#
# **The worst query in this file** is the fulfilment duration in `operations`:
# a self-join of `order_events` returning one row per delivered order in the
# period, subtracted here rather than in SQL. Every other figure comes back
# already grouped. It is bounded by `MAX_DAYS` and by the shop's order rate,
# and if it ever hurts the fix is a `delivered_at` column on the order — which
# is the thing this schema should have had all along.
