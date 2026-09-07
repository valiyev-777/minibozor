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

Two more doors, and both are about the same thing — a figure a seller reads
before it is final.

* **The running total.** ``GET /current`` runs the arithmetic over the window
  covering today and stores none of it. Marked provisional in the shape
  itself, because the alternative was answering "how is this month going" with
  silence until an admin happened to generate a run.
* **The weight bands.** ``POST``/``PATCH``/``DELETE /tariffs``. A band is a
  term of a contract, so every change is logged per field, with a name and a
  time against it.

**The bands are global, not per seller, and that is a decision rather than an
omission.** The negotiated lever already exists and is per seller:
``Seller.commission_percent``, a percentage of what the goods are worth. A
band says what a two-kilogram parcel costs *us* to pick, carry and shelve, and
that does not become cheaper because of whose parcel it is. Two further
reasons it should not be copied per seller yet:

* A handling fee is snapshotted onto the order line the day it sells, so a
  per-seller band would need its own snapshot before it could be trusted —
  whereas the storage rate is read live and would need one at close time,
  which does not exist. Two rates with two different freezing rules on one
  table is how a settlement model starts disagreeing with itself.
* A per-seller override is only meaningful once somebody has negotiated one.
  Building the column first means every band lookup grows a fallback chain
  that nothing exercises, and the day a real override arrives it will want a
  start date as well — which is a contract, not a column.

When a seller does negotiate handling separately, it belongs on a contract row
with dates, read through ``settlement.fulfilment_fee`` and
``settlement.storage_rate`` — the two functions that already exist so nothing
else has to know where a rate comes from.
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


# --------------------------------------------------------------------------- so far


@router.get(
    "/current",
    response_model=s.RunningTotalOut,
    summary="How the period is going so far — not the figure that will be paid",
)
def current(
    user: SellerUser,
    session: SessionDep,
    seller_id: int | None = Query(
        None, description="Admins only: whose running total to read"
    ),
) -> s.RunningTotalOut:
    """The question a seller asks between payouts, and could not ask here.

    ``/statements`` answers with the runs an admin has generated. Until one is
    generated there is nothing to read, and a seller mid-month was told
    nothing at all — while the sales, the returns and the days of storage were
    all sitting in the database being counted for them.

    So this runs the same arithmetic ``generate`` runs, over the window that
    covers today, and stores none of it. Two things make that safe to show:

    **It is marked provisional in the shape itself.** ``is_final`` is the
    constant ``false``. A seller who reads a figure and is paid a different
    one has been told the first number was a guess, which makes every number a
    guess — so this one says it is a guess before they ask.

    **It cannot be mistaken for a statement.** No id, no lines with ids, no
    status that could become ``paid``. The only door that produces a figure
    somebody is paid is ``close``, and it is an admin's.

    Why it will differ: goods delivered after the request, a return that
    arrives next week, another day of storage on every unit — and an
    adjustment, which is not derived from anything and so is not here at all.
    """
    mine = _own_seller(session, user)
    if mine is not None:
        seller = mine
    else:
        if seller_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("seller_required")
            )
        seller = session.get(Seller, seller_id)
        if seller is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, i18n.label("seller_not_found")
            )

    period = st.current_window(session)
    tally, lines = st.running(session, period, seller.id)
    return s.RunningTotalOut(
        period_id=period.id,
        # A window nobody opened has no name of its own, so it is given the
        # one thing that is true about it: it is not a run yet.
        period_label=period.label or i18n.label("period_not_opened"),
        period_status=period.status if period.id else None,
        starts_on=period.starts_on,
        ends_on=period.ends_on,
        as_of=utcnow(),
        seller_id=seller.id,
        seller_name=seller.name,
        gross_sales=tally.gross_sales,
        commission=tally.commission,
        fulfilment=tally.fulfilment,
        refunds=tally.refunds,
        storage=tally.storage,
        payable=tally.payable,
        line_count=len(lines),
        lines=[
            s.RunningLineOut(
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


# --------------------------------------------------------------------------- tariffs

# Global bands, read by everybody who is charged them and written by admins
# only. Why they are not per seller is in the module docstring.


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
    return [_tariff_out(row) for row in rows]


@router.post(
    "/tariffs",
    response_model=s.FulfilmentTariffOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a weight band",
)
def create_tariff(
    payload: s.FulfilmentTariffWriteIn, user: AdminUser, session: SessionDep
) -> s.FulfilmentTariffOut:
    """A band is a term of a contract, so writing one is logged with a name
    against it.

    Refused if a band already tops out at the same weight. ``band_for`` takes
    the lightest band that still covers a parcel, so two bands sharing a
    ceiling make "what does this cost to handle" a question with two answers
    and the one that wins depends on row order — which is not a rule anybody
    could quote back to a seller.
    """
    _band_ceiling_is_free(session, payload.max_grams, None)
    row = FulfilmentTariff(
        max_grams=payload.max_grams,
        fee=payload.fee,
        storage_per_day=payload.storage_per_day,
        label=payload.label.strip(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    audit.record(
        session,
        actor=user,
        action="tariff.create",
        entity="fulfilment_tariff",
        entity_id=row.id,
        field="max_grams",
        old=None,
        new=row.max_grams,
        note=_band_note(row),
    )
    session.commit()
    session.refresh(row)
    return _tariff_out(row)


@router.patch(
    "/tariffs/{tariff_id}",
    response_model=s.FulfilmentTariffOut,
    summary="Change what a weight band charges",
)
def update_tariff(
    tariff_id: int,
    payload: s.FulfilmentTariffUpdateIn,
    user: AdminUser,
    session: SessionDep,
) -> s.FulfilmentTariffOut:
    """One audit row per field that actually moved.

    Per field because "the 2 kg band was edited" is not a fact anybody can
    act on: a seller disputing a handling charge wants to know that the fee
    went from 14 000 to 19 000 on a particular day, by a particular person.
    And only when it moved — a panel that saves a form it did not change
    should not fill the log with a change nobody made.

    **What this does not do is rewrite history.** A closed statement's lines
    are frozen rows and a sold order line carries the fee it was sold at, so
    a band edited today changes what the *next* parcel is charged and nothing
    that has already been settled. There is a test that says so, because it is
    the property a seller has to be able to rely on and the one that would
    break silently.
    """
    row = _tariff(session, tariff_id)
    if payload.max_grams is not None:
        _band_ceiling_is_free(session, payload.max_grams, row.id)

    for field in ("max_grams", "fee", "storage_per_day", "label"):
        value = getattr(payload, field)
        if value is None:
            continue
        if field == "label":
            value = value.strip()
        if value == getattr(row, field):
            continue
        audit.record(
            session,
            actor=user,
            action=f"tariff.{field}",
            entity="fulfilment_tariff",
            entity_id=row.id,
            field=field,
            old=getattr(row, field),
            new=value,
            note=_band_note(row),
        )
        setattr(row, field, value)

    session.add(row)
    session.commit()
    session.refresh(row)
    return _tariff_out(row)


@router.delete(
    "/tariffs/{tariff_id}",
    response_model=s.Message,
    summary="Withdraw a weight band",
)
def delete_tariff(
    tariff_id: int, user: AdminUser, session: SessionDep
) -> s.Message:
    """Refused for the heaviest band while any lighter one remains.

    The heaviest band is the roof: it is what covers everything above the band
    below it, which is why the seed gives it an absurdly large ceiling rather
    than a null. Delete it and every parcel heavier than the next band down
    falls through to no band at all — handled free, and stored at the flat
    fallback rate — which is a free ride nobody decided to give and nothing
    would report. Raise the ceiling of the band below it instead, or add the
    replacement first.

    The last band standing can go: an installation with no tariffs at all
    charges no handling, which is honest about not having decided yet.
    """
    row = _tariff(session, tariff_id)
    lighter = session.exec(
        select(FulfilmentTariff).where(FulfilmentTariff.max_grams < row.max_grams)
    ).first()
    heavier = session.exec(
        select(FulfilmentTariff).where(FulfilmentTariff.max_grams > row.max_grams)
    ).first()
    if heavier is None and lighter is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("tariff_top_band"))

    audit.record(
        session,
        actor=user,
        action="tariff.delete",
        entity="fulfilment_tariff",
        entity_id=row.id,
        field="max_grams",
        old=row.max_grams,
        new=None,
        note=_band_note(row),
    )
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- helpers


def _tariff(session: SessionDep, tariff_id: int) -> FulfilmentTariff:
    row = session.get(FulfilmentTariff, tariff_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("tariff_not_found"))
    return row


def _band_ceiling_is_free(
    session: SessionDep, max_grams: int, except_id: int | None
) -> None:
    """Two bands may not share a ceiling. See ``create_tariff``."""
    clash = session.exec(
        select(FulfilmentTariff).where(FulfilmentTariff.max_grams == max_grams)
    ).first()
    if clash is not None and clash.id != except_id:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("tariff_band_exists"))


def _band_note(row: FulfilmentTariff) -> str:
    """The band in words, for the log — a row id is not a band anybody
    recognises a year later."""
    return f"{row.label or row.max_grams} · {row.fee} so'm · {row.storage_per_day}/kun"


def _tariff_out(row: FulfilmentTariff) -> s.FulfilmentTariffOut:
    return s.FulfilmentTariffOut(
        id=row.id,
        max_grams=row.max_grams,
        fee=row.fee,
        storage_per_day=row.storage_per_day,
        label=row.label,
    )


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
