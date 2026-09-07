"""Working out what a seller is owed, and freezing it once they have seen it.

The marketplace could sell things and could not pay for them. Everything the
arithmetic needs was already being captured — who sold each line, at what
price, at what commission rate — and nothing added it up.

Five rules hold everywhere in here.

**A statement is the sum of its lines.** Not a figure computed alongside a
list; the figure *is* the list. ``SellerStatement.payable`` equals
``sum(line.amount)`` and there is a test that says so, for the same reason
``Offer.stock_left`` equals the sum of its movements: a total that can drift
from its own composition is a total nobody can defend in an argument.

**Every rate is read from the snapshot, never from the seller.** The
commission on a line and the handling fee on a line were written the day it
sold. Recomputing either from today's ``Seller.commission_percent`` would
quietly restate what somebody was owed for something they sold last year, and
would do it silently.

**Two fees, because one cannot work.** Commission scales with what goods are
worth; handling scales with what they cost to move. The catalogue's cheapest
card earns 1 950 so'm of commission against a delivery that costs many times
that, and its dearest earns 9 100 000 for carrying one small box. A single
percentage is a loss on one end and an embarrassment on the other.

**A sale counts when it is delivered.** Not when it is placed — it may be
called off — and not when it is paid, because cash orders are paid at the
door. The day it was delivered is on the order's own timeline.

**A closed statement is finished.** Its lines are frozen rows and its sources
are spent. Anything arriving afterwards is unspent and lands in the next open
period, so a figure a seller has read never becomes a different figure.

That last rule is also what makes the rates safe to edit. A band's handling
fee is snapshotted onto the order line the day it sells and a closed
statement's lines are rows in a table, so raising a tariff changes what the
next parcel is charged and nothing that has been settled. The storage rate is
the one figure read live — which is correct, because an open period is a
running answer — and closing is what stops it being read again.

``compose`` is the arithmetic; ``build`` persists what it returns and
``running`` throws it away. One function rather than two because a seller
reading "so far" has to be reading a preview of the figure they will be paid
rather than a second opinion about it, and two copies of this would disagree
the first time a line kind was added to one of them.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlmodel import Session, col, func, select

from app.models import (
    FulfilmentTariff,
    Offer,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    Product,
    ReturnRequest,
    ReturnStatus,
    SellerStatement,
    SettlementPeriod,
    SettlementStatus,
    StatementLine,
    StatementLineKind,
    StockMovement,
    utcnow,
)

# --------------------------------------------------------------------------- rates

# What happens to goods that will not sell, and what space costs when nobody
# has said how big the goods are.
#
# The surcharge is the point of charging at all. Space is the one thing a
# seller consumes whether or not they earn anything with it, so without a
# standing cost the warehouse is a free storage unit and the way to use it is
# to send everything and let us hold it. A multiplier on stock that has not
# moved in two months is the only mechanism here that empties a shelf; the
# alternative is somebody having that argument by hand, every month, per
# seller.
#
# The rate itself is not here — it is on the weight band, beside the shipment
# fee, because a washing machine and a pair of earphones do not occupy the
# same warehouse. This is only the fallback for goods no band covers.
#
# Constants rather than a table because they are one number each and are not
# yet negotiated per seller. When they are they become terms on a contract and
# this module reads them from there, which is why nothing outside reads them
# directly.
STORAGE_PER_UNIT_DAY = 60          # so'm, only when no band matches
STALE_AFTER_DAYS = 60
STALE_MULTIPLIER = 3

# What an undeclared weight is charged at.
#
# Not nothing. A seller who leaves the field empty would otherwise be handled
# free, which makes leaving it empty the profitable choice and the column
# useless. One kilogram is a real parcel and declaring a lighter one is
# rewarded.
UNDECLARED_GRAMS = 1000


def band_for(session: Session, product: Product | None) -> FulfilmentTariff | None:
    """The weight band this product falls into.

    The lightest band that still covers it, so the bands read top to bottom as
    "up to 500 g", "up to 2 kg" and the answer is the first that fits.
    """
    grams = (product.weight_grams if product else 0) or UNDECLARED_GRAMS
    return session.exec(
        select(FulfilmentTariff)
        .where(FulfilmentTariff.max_grams >= grams)
        .order_by(col(FulfilmentTariff.max_grams))
    ).first()


def fulfilment_fee(session: Session, product: Product | None) -> int:
    """What handling one unit of this product costs.

    No band at all — nobody has set a tariff — is zero. Charging a fee that
    has not been decided would be worse than charging none.
    """
    band = band_for(session, product)
    return band.fee if band else 0


def storage_rate(session: Session, product: Product | None) -> int:
    """What one of these costs to keep on a shelf for a day.

    From the same band as the shipment fee, for the same reason: both follow
    how big the thing is. Falls back to the flat constant only when no band
    covers it, so an untariffed catalogue still pays rent rather than nothing.
    """
    band = band_for(session, product)
    if band is None or not band.storage_per_day:
        return STORAGE_PER_UNIT_DAY
    return band.storage_per_day


# --------------------------------------------------------------------------- when things happened


def _end_of(day: date) -> datetime:
    """A period runs to the last moment of its closing day, not to midnight
    at the start of it."""
    return datetime.combine(day, time.max)


def delivered_at(session: Session, order_id: int) -> datetime | None:
    """The moment an order reached the door, off its own timeline."""
    row = session.exec(
        select(OrderEvent).where(
            OrderEvent.order_id == order_id,
            OrderEvent.status == OrderStatus.DELIVERED,
        )
    ).first()
    return row.happened_at if row else None


# --------------------------------------------------------------------------- what is already spent


def _settled_sources(session: Session, seller_id: int) -> tuple[set[int], set[int]]:
    """The order lines and returns already accounted for in a frozen statement.

    Frozen meaning closed or paid. An open statement's lines are rebuilt from
    scratch every time it is generated, so they are not a claim on anything —
    which is what makes regenerating an open period safe and closing it final.
    """
    rows = session.exec(
        select(StatementLine.order_item_id, StatementLine.return_request_id)
        .join(SellerStatement, col(StatementLine.statement_id) == col(SellerStatement.id))
        .where(
            SellerStatement.seller_id == seller_id,
            col(SellerStatement.status).in_(
                [SettlementStatus.CLOSED, SettlementStatus.PAID]
            ),
        )
    ).all()
    items = {row[0] for row in rows if row[0] is not None}
    returns = {row[1] for row in rows if row[1] is not None}
    return items, returns


# --------------------------------------------------------------------------- storage


def _unit_days(session: Session, offer_id: int, since: date, until: date) -> int:
    """How many unit-days this offer occupied the warehouse for.

    Walked out of the movement ledger rather than taken from today's count.
    ``stock_left`` is what is on the shelf now; a seller whose goods arrived on
    the 28th would otherwise be charged for the whole month, and one who sold
    out on the 2nd would be charged for none of it having been there — both
    wrong, and wrong in a way that only shows up in a dispute.

    The holding is the running sum of the signed movements, so this is the same
    arithmetic the shelf itself is, integrated over the days of the period.
    """
    movements = session.exec(
        select(StockMovement)
        .where(StockMovement.offer_id == offer_id)
        .order_by(col(StockMovement.created_at), col(StockMovement.id))
    ).all()
    if not movements:
        return 0

    start = datetime.combine(since, time.min)
    # Exclusive: a period running the 1st to the 9th covers nine whole days,
    # which is midnight on the 1st up to midnight on the 10th. Integrating to
    # 23:59:59.999999 instead leaves the total a microsecond short of nine
    # days per unit, and the truncation to whole unit-days then loses one —
    # a rounding error that would only ever be noticed by the seller it
    # under-charged.
    end = datetime.combine(until, time.min) + timedelta(days=1)

    # What was already on the shelf when the period opened.
    holding = sum(m.quantity for m in movements if m.created_at < start)
    total = 0.0
    cursor = start
    for movement in movements:
        if movement.created_at < start:
            continue
        moment = min(movement.created_at, end)
        if moment > cursor:
            total += holding * (moment - cursor).total_seconds()
            cursor = moment
        if movement.created_at > end:
            break
        holding += movement.quantity
    if cursor < end:
        total += holding * (end - cursor).total_seconds()

    return int(total / 86_400)


def _last_intake(session: Session, offer_id: int) -> datetime | None:
    return session.exec(
        select(func.max(StockMovement.created_at)).where(
            StockMovement.offer_id == offer_id, StockMovement.quantity > 0
        )
    ).one()


def _storage_lines(
    session: Session, seller_id: int, period: SettlementPeriod
) -> list[StatementLine]:
    """One line per offer that took up space, with the sum in words.

    Per offer rather than one lump, because "storage: 840 000" is the kind of
    figure a seller writes an email about and "this offer, four units, 31 days,
    60 so'm, tripled because nothing has moved since November" is the kind
    they act on.
    """
    offers = session.exec(select(Offer).where(Offer.seller_id == seller_id)).all()
    lines: list[StatementLine] = []
    stale_before = _end_of(period.ends_on) - timedelta(days=STALE_AFTER_DAYS)

    for offer in offers:
        unit_days = _unit_days(session, offer.id, period.starts_on, period.ends_on)
        if unit_days <= 0:
            continue
        product = session.get(Product, offer.product_id)
        intake = _last_intake(session, offer.id)
        stale = intake is not None and intake < stale_before
        base = storage_rate(session, product)
        rate = base * (STALE_MULTIPLIER if stale else 1)
        amount = unit_days * rate
        days = (period.ends_on - period.starts_on).days + 1
        grams = product.weight_grams if product else 0
        note = f"{unit_days} dona-kun × {rate} so'm"
        if grams:
            note += f" ({grams} g guruhi)"
        if stale:
            note += (
                f" ({STALE_AFTER_DAYS} kundan ortiq harakatsiz — "
                f"{STALE_MULTIPLIER}× stavka)"
            )
        note += f" · davr {days} kun"
        lines.append(
            StatementLine(
                kind=StatementLineKind.STORAGE,
                amount=-amount,
                quantity=unit_days,
                offer_id=offer.id,
                title=product.title if product else f"Taklif #{offer.id}",
                note=note,
                occurred_at=_end_of(period.ends_on),
            )
        )
    return lines


# --------------------------------------------------------------------------- building


def _sale_lines(
    session: Session, seller_id: int, period: SettlementPeriod, spent: set[int]
) -> list[StatementLine]:
    """Three lines per delivered order line: what it earned and what it cost.

    Split rather than netted. A seller looking at one line of one order wants
    to see the price they set, the cut we took and the handling we charged as
    three figures — netting them into "you get 27 050" is the number that
    starts the argument this whole model exists to end.
    """
    items = session.exec(
        select(OrderItem)
        .join(Order, col(OrderItem.order_id) == col(Order.id))
        .where(
            OrderItem.seller_id == seller_id,
            Order.status == OrderStatus.DELIVERED,
        )
        .order_by(col(OrderItem.id))
    ).all()

    lines: list[StatementLine] = []
    for item in items:
        if item.id in spent:
            continue
        when = delivered_at(session, item.order_id)
        if when is None or when > _end_of(period.ends_on):
            continue
        order = session.get(Order, item.order_id)
        code = order.code if order else f"#{item.order_id}"
        where = f"{code} · {item.title}"
        if item.variant_label:
            where += f" · {item.variant_label}"

        gross = item.line_total
        commission = gross * item.commission_percent // 100
        handling = item.fulfilment_fee * item.quantity

        lines.append(
            StatementLine(
                kind=StatementLineKind.SALE,
                amount=gross,
                quantity=item.quantity,
                order_item_id=item.id,
                title=where,
                note=f"{item.quantity} × {item.unit_price} so'm",
                occurred_at=when,
            )
        )
        lines.append(
            StatementLine(
                kind=StatementLineKind.COMMISSION,
                amount=-commission,
                quantity=item.quantity,
                order_item_id=item.id,
                title=where,
                # The rate as it was, said out loud: this is the figure a
                # seller checks against their contract.
                note=f"{item.commission_percent}% · sotilgan kundagi stavka",
                occurred_at=when,
            )
        )
        if handling:
            lines.append(
                StatementLine(
                    kind=StatementLineKind.FULFILMENT,
                    amount=-handling,
                    quantity=item.quantity,
                    order_item_id=item.id,
                    title=where,
                    note=f"{item.quantity} × {item.fulfilment_fee} so'm · yig'ish va yetkazish",
                    occurred_at=when,
                )
            )
    return lines


def _refund_lines(
    session: Session, seller_id: int, period: SettlementPeriod, spent: set[int]
) -> list[StatementLine]:
    """A sale undone, and our cut of it given back.

    The commission comes back; the handling fee does not. A refunded sale was
    never a sale, so keeping five per cent of it would be charging for
    something that did not happen. The van still came, though, and the goods
    were still picked and packed — that cost was incurred and is not recovered
    by the customer changing their mind.
    """
    requests = session.exec(
        select(ReturnRequest)
        .where(ReturnRequest.status == ReturnStatus.REFUNDED)
        .order_by(col(ReturnRequest.id))
    ).all()

    lines: list[StatementLine] = []
    for request in requests:
        if request.id in spent or not request.refund_amount:
            continue
        when = request.refunded_at
        if when is None or when > _end_of(period.ends_on):
            continue

        # Whose sale was undone. A request naming one line is that line's
        # seller; a whole-order refund is split across the lines it covers.
        items = _refunded_items(session, request)
        mine = [item for item in items if item.seller_id == seller_id]
        if not mine:
            continue

        goods = sum(item.line_total for item in items) or 1
        order = session.get(Order, request.order_id)
        code = order.code if order else f"#{request.order_id}"

        for item in mine:
            # The refund may include a delivery fee the seller never received,
            # so a seller is only ever charged back their share of the goods.
            share = item.line_total
            commission = share * item.commission_percent // 100
            where = f"{code} · {item.title}"
            lines.append(
                StatementLine(
                    kind=StatementLineKind.REFUND,
                    amount=-share,
                    quantity=item.quantity,
                    return_request_id=request.id,
                    order_item_id=item.id,
                    title=where,
                    note=(
                        f"Qaytarish #{request.id}"
                        + (f" · {request.reason}" if request.reason else "")
                        + (
                            f" · mijozga {request.refund_amount} so'm qaytdi"
                            if request.refund_amount != goods
                            else ""
                        )
                    ),
                    occurred_at=when,
                )
            )
            lines.append(
                StatementLine(
                    kind=StatementLineKind.REFUND_COMMISSION,
                    amount=commission,
                    quantity=item.quantity,
                    return_request_id=request.id,
                    order_item_id=item.id,
                    title=where,
                    note=(
                        f"{item.commission_percent}% qaytarildi — bo'lmagan "
                        "sotuvdan komissiya olinmaydi"
                    ),
                    occurred_at=when,
                )
            )
    return lines


def _refunded_items(session: Session, request: ReturnRequest) -> list[OrderItem]:
    if request.order_item_id:
        item = session.get(OrderItem, request.order_item_id)
        return [item] if item else []
    return list(
        session.exec(
            select(OrderItem).where(OrderItem.order_id == request.order_id)
        ).all()
    )


def compose(
    session: Session, period: SettlementPeriod, seller_id: int
) -> list[StatementLine]:
    """Every line one seller's account over these days is made of.

    Unattached rows: nothing here is added to the session. ``build`` persists
    what it gets back, ``running`` throws it away, and the arithmetic is the
    same both times — which is the only way a seller reading "so far" is
    reading a preview of the figure rather than a second opinion about it.

    Not adjustments. Those are not derived from anything; see
    ``schemas.RunningTotalOut``.
    """
    spent_items, spent_returns = _settled_sources(session, seller_id)
    return [
        *_sale_lines(session, seller_id, period, spent_items),
        *_refund_lines(session, seller_id, period, spent_returns),
        *_storage_lines(session, seller_id, period),
    ]


def current_window(session: Session) -> SettlementPeriod:
    """Which days "so far" means, and whether anybody has named them.

    The open period covering today, when there is one. That is the run the
    seller's next statement will be cut from, and its dates were somebody's
    decision rather than ours.

    When there is none — the last run has been closed and the next has not
    been opened, while the selling carries on regardless — a window is worked
    out instead: the day after the last day any period already accounts for,
    through today. The row it returns is **not in the database** and its ``id``
    is ``None``, because it is not a period. It is the gap between the last one
    and now, and calling it a period would invite somebody to close it.

    Clamped to today at the near end, so a period closed early — one whose
    days run past today — cannot make the window start in the future.
    """
    today = utcnow().date()
    covering = session.exec(
        select(SettlementPeriod)
        .where(
            SettlementPeriod.status == SettlementStatus.OPEN,
            SettlementPeriod.starts_on <= today,
            SettlementPeriod.ends_on >= today,
        )
        .order_by(col(SettlementPeriod.starts_on).desc())
    ).first()
    if covering is not None:
        return covering

    # The last day already spoken for. Periods that have not started yet are
    # ignored: a run opened for next month says nothing about where this
    # month's accounting begins.
    previous = session.exec(
        select(SettlementPeriod)
        .where(SettlementPeriod.starts_on <= today)
        .order_by(col(SettlementPeriod.ends_on).desc())
    ).first()
    starts = (
        min(previous.ends_on + timedelta(days=1), today)
        if previous is not None
        else today.replace(day=1)
    )
    return SettlementPeriod(label="", starts_on=starts, ends_on=today)


def running(
    session: Session, period: SettlementPeriod, seller_id: int
) -> tuple[SellerStatement, list[StatementLine]]:
    """The same arithmetic over a window nobody has frozen, stored nowhere.

    The totals are hung on an unsaved ``SellerStatement`` so that ``_total``
    is the one place the headings are worked out — a second copy of that
    function is a second answer to "what does commission mean", and the two
    would drift the first time a line kind was added.
    """
    lines = compose(session, period, seller_id)
    tally = SellerStatement(period_id=period.id or 0, seller_id=seller_id)
    _total(tally, lines)
    return tally, lines


def build(
    session: Session, period: SettlementPeriod, seller_id: int
) -> SellerStatement:
    """Gather one seller's account for one period, or rebuild it.

    Rebuilt in place while the period is open: the lines are dropped and
    recomputed, because an open period is a running answer rather than a
    promise. Once closed it is neither rebuilt nor consulted again — see
    ``_settled_sources``.

    The caller commits.
    """
    statement = session.exec(
        select(SellerStatement).where(
            SellerStatement.period_id == period.id,
            SellerStatement.seller_id == seller_id,
        )
    ).first()

    if statement is None:
        statement = SellerStatement(period_id=period.id, seller_id=seller_id)
        session.add(statement)
        session.commit()
        session.refresh(statement)
    elif statement.status is not SettlementStatus.OPEN:
        return statement

    for row in session.exec(
        select(StatementLine).where(StatementLine.statement_id == statement.id)
    ).all():
        session.delete(row)
    session.commit()

    lines = compose(session, period, seller_id)
    for line in lines:
        line.statement_id = statement.id
        session.add(line)

    _total(statement, lines)
    session.add(statement)
    return statement


def _total(statement: SellerStatement, lines: list[StatementLine]) -> None:
    """The headings, and the one figure that has to equal their arithmetic.

    ``payable`` is summed from the lines rather than from the headings, so a
    kind added later and forgotten here shows up as a heading that does not
    add up rather than as money quietly not paid.
    """
    def total(*kinds: StatementLineKind) -> int:
        return sum(line.amount for line in lines if line.kind in kinds)

    statement.gross_sales = total(StatementLineKind.SALE)
    statement.commission = -total(StatementLineKind.COMMISSION)
    statement.fulfilment = -total(StatementLineKind.FULFILMENT)
    statement.refunds = -total(
        StatementLineKind.REFUND, StatementLineKind.REFUND_COMMISSION
    )
    statement.storage = -total(StatementLineKind.STORAGE)
    statement.adjustments = total(StatementLineKind.ADJUSTMENT)
    statement.payable = sum(line.amount for line in lines)


def retotal(session: Session, statement: SellerStatement) -> None:
    """Recompute the headings from the lines currently on the statement.

    For the one line a person writes by hand. Everything else arrives through
    ``build``, which totals as it goes; an adjustment is added to a statement
    that already exists, so the arithmetic has to be redone against what is
    now there. The caller commits.
    """
    _total(statement, lines_of(session, statement.id))
    session.add(statement)


def lines_of(session: Session, statement_id: int) -> list[StatementLine]:
    return list(
        session.exec(
            select(StatementLine)
            .where(StatementLine.statement_id == statement_id)
            .order_by(col(StatementLine.occurred_at), col(StatementLine.id))
        ).all()
    )


def sum_of_lines(session: Session, statement_id: int) -> int:
    """What the statement's own rows add up to, for the invariant test."""
    return sum(line.amount for line in lines_of(session, statement_id))


def close(session: Session, statement: SellerStatement) -> None:
    """Freeze it. The caller commits, and audits."""
    statement.status = SettlementStatus.CLOSED
    statement.closed_at = utcnow()
    session.add(statement)
