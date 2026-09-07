"""Paying sellers.

The one thing the marketplace could not do. Everything else worked — a seller
was taken on, priced an offer, the warehouse booked goods in, a customer
bought them and the commission rate was captured onto the order line — and
then no money moved and nobody could say what was owed.

The doors here are deliberately few and each one is a decision:

* **Open a period.** The dates of a payout run, chosen rather than derived.
* **Generate.** Gather each seller's account for it, as many times as anybody
  likes, while it is open.
* **Close.** Freeze it, because the seller is about to be shown the figure.
* **Pay.** Say when, how, and against which transfer.

Only ``generate`` is repeatable. The other three change something a seller has
seen or been paid, so each writes an audit row before it commits — the same
rule the rest of the backoffice follows for money and stock.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import schemas as s
from app import settlement as st
from app.deps import AdminUser, SellerUser, SessionDep, StockViewer
from app.models import (
    FulfilmentTariff,
    Seller,
    SellerStatement,
    SettlementPeriod,
    SettlementStatus,
    StatementLine,
    StatementLineKind,
    User,
    UserRole,
    utcnow,
)

router = APIRouter(prefix="/staff/payouts", tags=["staff"])


# --------------------------------------------------------------------------- periods


@router.get("/periods", response_model=list[s.SettlementPeriodOut])
def list_periods(user: AdminUser, session: SessionDep) -> list[s.SettlementPeriodOut]:
    rows = session.exec(
        select(SettlementPeriod).order_by(col(SettlementPeriod.starts_on).desc())
    ).all()
    return [_period_out(session, row) for row in rows]


@router.post(
    "/periods",
    response_model=s.SettlementPeriodOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a payout run over a range of days",
)
def create_period(
    payload: s.PeriodCreateIn, user: AdminUser, session: SessionDep
) -> s.SettlementPeriodOut:
    """Refused if it overlaps one that already exists.

    Two periods covering the same day would either pay a sale twice or leave
    it ambiguous which run it belonged to. The spent-source rule below would
    stop the double payment, but only after the fact and only if somebody
    closed them in the right order — so the overlap is refused instead.
    """
    if payload.ends_on < payload.starts_on:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("period_backwards")
        )
    clash = session.exec(
        select(SettlementPeriod).where(
            SettlementPeriod.starts_on <= payload.ends_on,
            SettlementPeriod.ends_on >= payload.starts_on,
        )
    ).first()
    if clash is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("period_overlaps"))

    row = SettlementPeriod(
        label=payload.label.strip() or f"{payload.starts_on} — {payload.ends_on}",
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    audit.record(
        session,
        actor=user,
        action="settlement.period.open",
        entity="settlement_period",
        entity_id=row.id,
        field="status",
        old=None,
        new=SettlementStatus.OPEN,
        note=row.label,
    )
    session.commit()
    session.refresh(row)
    return _period_out(session, row)


@router.post(
    "/periods/{period_id}/generate",
    response_model=list[s.SellerStatementOut],
    summary="Work out every seller's account for this period",
)
def generate(
    period_id: int, user: AdminUser, session: SessionDep
) -> list[s.SellerStatementOut]:
    """Repeatable while the period is open, and only then.

    An open period is a running answer: run it on Tuesday and again on Friday
    and Friday's is the one that counts. Once a statement is closed it is not
    rebuilt and its sources are spent, so a later run over a later period
    picks up what arrived in between rather than restating what was settled.
    """
    period = _period(session, period_id)
    if period.status is not SettlementStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("period_closed"))

    sellers = session.exec(select(Seller).order_by(col(Seller.name))).all()
    out = []
    for seller in sellers:
        out.append(st.build(session, period, seller.id))
    session.commit()
    return [_statement_out(session, row) for row in out]


@router.post(
    "/periods/{period_id}/close",
    response_model=s.SettlementPeriodOut,
    summary="Freeze the run — the sellers are about to see it",
)
def close_period(
    period_id: int, user: AdminUser, session: SessionDep
) -> s.SettlementPeriodOut:
    """Closing is what makes the figures mean something.

    A seller who reads what they are owed and is shown a different number next
    week has been told the first number was provisional, which makes every
    number provisional. So this is the point of no return: the lines stop being
    recomputed and the events behind them stop being available to any other
    period.

    It is not the same as paying. The money leaves per seller, against a
    transfer, on its own door.
    """
    period = _period(session, period_id)
    if period.status is not SettlementStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("period_closed"))

    statements = session.exec(
        select(SellerStatement).where(SellerStatement.period_id == period.id)
    ).all()
    if not statements:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("period_empty"))

    for statement in statements:
        if statement.status is SettlementStatus.OPEN:
            st.close(session, statement)
            audit.record(
                session,
                actor=user,
                action="settlement.statement.close",
                entity="seller_statement",
                entity_id=statement.id,
                field="payable",
                old=None,
                new=statement.payable,
                note=_seller_name(session, statement.seller_id),
            )

    period.status = SettlementStatus.CLOSED
    period.closed_at = utcnow()
    period.closed_by_id = user.id
    session.add(period)
    audit.record(
        session,
        actor=user,
        action="settlement.period.close",
        entity="settlement_period",
        entity_id=period.id,
        field="status",
        old=SettlementStatus.OPEN,
        new=SettlementStatus.CLOSED,
        note=period.label,
    )
    session.commit()
    session.refresh(period)
    return _period_out(session, period)


# --------------------------------------------------------------------------- statements


@router.get(
    "/statements",
    response_model=list[s.SellerStatementOut],
    summary="Accounts, filtered by period, seller or state",
)
def list_statements(
    user: StockViewer,
    session: SessionDep,
    period_id: int | None = Query(None),
    seller_id: int | None = Query(None),
    status_filter: SettlementStatus | None = Query(None, alias="status"),
) -> list[s.SellerStatementOut]:
    """A seller reads their own and nobody else's.

    The scoping is not a filter they choose: for a seller these are the only
    rows that exist. Admins see everything, which is what makes a dispute
    answerable from one screen.
    """
    stmt = select(SellerStatement)
    mine = _own_seller(session, user)
    if mine is not None:
        stmt = stmt.where(SellerStatement.seller_id == mine.id)
    elif seller_id is not None:
        stmt = stmt.where(SellerStatement.seller_id == seller_id)
    if period_id is not None:
        stmt = stmt.where(SellerStatement.period_id == period_id)
    if status_filter is not None:
        stmt = stmt.where(SellerStatement.status == status_filter)
    rows = session.exec(stmt.order_by(col(SellerStatement.id).desc())).all()
    return [_statement_out(session, row) for row in rows]


@router.get(
    "/statements/{statement_id}",
    response_model=s.SellerStatementDetailOut,
    summary="One account with every line that adds up to it",
)
def get_statement(
    statement_id: int, user: StockViewer, session: SessionDep
) -> s.SellerStatementDetailOut:
    """The composition, which is the whole reason this model exists.

    ``9 100 000`` is a number to argue with. The order lines, the returns and
    the days of storage behind it are an account to read — and the seller can
    read their own without asking anybody.
    """
    statement = _statement(session, statement_id)
    mine = _own_seller(session, user)
    if mine is not None and statement.seller_id != mine.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("forbidden"))

    lines = st.lines_of(session, statement.id)
    return s.SellerStatementDetailOut(
        **_statement_out(session, statement).model_dump(),
        lines=[
            s.StatementLineOut(
                id=line.id,
                kind=line.kind,
                amount=line.amount,
                quantity=line.quantity,
                title=line.title,
                note=line.note,
                occurred_at=line.occurred_at,
                order_item_id=line.order_item_id,
                return_request_id=line.return_request_id,
                offer_id=line.offer_id,
            )
            for line in lines
        ],
    )


@router.post(
    "/statements/{statement_id}/adjust",
    response_model=s.SellerStatementDetailOut,
    summary="Add a correction, with the reason",
)
def adjust(
    statement_id: int,
    payload: s.AdjustmentIn,
    user: AdminUser,
    session: SessionDep,
) -> s.SellerStatementDetailOut:
    """The one line a person writes by hand, so it is the one that must explain
    itself. Only while the statement is open — a closed one is finished, and a
    correction to it belongs in the next period where it can be seen."""
    statement = _statement(session, statement_id)
    if statement.status is not SettlementStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("statement_closed"))

    session.add(
        StatementLine(
            statement_id=statement.id,
            kind=StatementLineKind.ADJUSTMENT,
            amount=payload.amount,
            quantity=0,
            title=f"{user.full_name or user.phone} tuzatishi",
            note=payload.note.strip(),
        )
    )
    session.commit()

    st.retotal(session, statement)
    audit.record(
        session,
        actor=user,
        action="settlement.adjust",
        entity="seller_statement",
        entity_id=statement.id,
        field="adjustments",
        old=None,
        new=payload.amount,
        note=payload.note.strip(),
    )
    session.add(statement)
    session.commit()
    session.refresh(statement)
    return get_statement(statement_id, user, session)


@router.post(
    "/statements/{statement_id}/pay",
    response_model=s.SellerStatementOut,
    summary="The money has left — say when, how, and against what",
)
def pay(
    statement_id: int,
    payload: s.StatementPayIn,
    user: AdminUser,
    session: SessionDep,
) -> s.SellerStatementOut:
    """Only a closed statement can be paid, and only once.

    Paying an open one would be paying a figure still being recomputed. Paying
    a paid one is the mistake this refusal exists for: two transfers against
    one account is money gone that nobody notices until the seller says
    nothing arrived and the log shows two payments to the one who did not
    call.
    """
    statement = _statement(session, statement_id)
    if statement.status is SettlementStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("statement_open"))
    if statement.status is SettlementStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("statement_paid"))

    audit.record(
        session,
        actor=user,
        action="settlement.pay",
        entity="seller_statement",
        entity_id=statement.id,
        field="payable",
        old=SettlementStatus.CLOSED,
        new=statement.payable,
        note=(
            f"{_seller_name(session, statement.seller_id)} · {payload.method}"
            + (f" · {payload.reference}" if payload.reference else "")
            + (f" · {payload.note}" if payload.note else "")
        ),
    )
    statement.status = SettlementStatus.PAID
    statement.paid_at = utcnow()
    statement.payment_method = payload.method.strip()
    statement.payment_reference = payload.reference.strip()
    if payload.note:
        statement.note = payload.note.strip()
    session.add(statement)
    session.commit()
    session.refresh(statement)
    return _statement_out(session, statement)


# --------------------------------------------------------------------------- tariffs


@router.get(
    "/tariffs",
    response_model=list[s.FulfilmentTariffOut],
    summary="What handling costs, by weight band",
)
def list_tariffs(
    user: SellerUser, session: SessionDep
) -> list[s.FulfilmentTariffOut]:
    """Readable by sellers as well as admins. A fee somebody is charged and
    cannot look up is a fee they can only dispute."""
    rows = session.exec(
        select(FulfilmentTariff).order_by(col(FulfilmentTariff.max_grams))
    ).all()
    return [
        s.FulfilmentTariffOut(
            id=row.id,
            max_grams=row.max_grams,
            fee=row.fee,
            storage_per_day=row.storage_per_day,
            label=row.label,
        )
        for row in rows
    ]


# --------------------------------------------------------------------------- helpers


def _period(session: SessionDep, period_id: int) -> SettlementPeriod:
    row = session.get(SettlementPeriod, period_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("period_not_found"))
    return row


def _statement(session: SessionDep, statement_id: int) -> SellerStatement:
    row = session.get(SellerStatement, statement_id)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("statement_not_found")
        )
    return row


def _own_seller(session: SessionDep, user: User) -> Seller | None:
    """The seller this account belongs to, or None for staff.

    A seller with no ``sellers`` row is not scoped to nothing — that would
    show them everybody's accounts. It is refused.
    """
    if user.role is not UserRole.SELLER:
        return None
    row = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
    if row is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
        )
    return row


def _seller_name(session: SessionDep, seller_id: int) -> str:
    row = session.get(Seller, seller_id)
    return row.name if row else f"#{seller_id}"


def _period_out(session: SessionDep, row: SettlementPeriod) -> s.SettlementPeriodOut:
    count, total = session.exec(
        select(func.count(), func.coalesce(func.sum(SellerStatement.payable), 0))
        .select_from(SellerStatement)
        .where(SellerStatement.period_id == row.id)
    ).one()
    return s.SettlementPeriodOut(
        id=row.id,
        label=row.label,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        status=row.status,
        closed_at=row.closed_at,
        statement_count=int(count),
        total_payable=int(total),
    )


def _statement_out(
    session: SessionDep, row: SellerStatement
) -> s.SellerStatementOut:
    period = session.get(SettlementPeriod, row.period_id)
    count = session.exec(
        select(func.count())
        .select_from(StatementLine)
        .where(StatementLine.statement_id == row.id)
    ).one()
    return s.SellerStatementOut(
        id=row.id,
        period_id=row.period_id,
        period_label=period.label if period else "",
        starts_on=period.starts_on if period else row.created_at.date(),
        ends_on=period.ends_on if period else row.created_at.date(),
        seller_id=row.seller_id,
        seller_name=_seller_name(session, row.seller_id),
        status=row.status,
        gross_sales=row.gross_sales,
        commission=row.commission,
        fulfilment=row.fulfilment,
        refunds=row.refunds,
        storage=row.storage,
        adjustments=row.adjustments,
        payable=row.payable,
        line_count=int(count),
        closed_at=row.closed_at,
        paid_at=row.paid_at,
        payment_method=row.payment_method,
        payment_reference=row.payment_reference,
        note=row.note,
    )
