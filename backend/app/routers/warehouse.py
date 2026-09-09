"""The warehouse: how goods arrive, get counted, and leave.

Nobody delivers to us. The owner goes to the wholesale market, buys what looks
worth buying and comes back with sacks — mixed, unlabelled, unphotographed —
so there is no declaration to check a receipt against and no supplier to
check it with. What there is instead is **two moments**, and this file is
shaped by the gap between them:

* **The sacks arrive.** Thirty seconds at the door: how many, where from, what
  the van cost. That is a ``draft`` supply, and nothing in it is stock — it is
  a sack standing in the receiving area that nobody has opened. It cannot be
  sold because nobody knows what it is.
* **Somebody sorts it.** Open the sack, separate by colour and size, count
  each pile, price it. Closing the run is what brings the goods into
  existence: the lines become movements and the cards go on sale.

The two are apart because the van arrives at nine in the evening and sorting
five sacks that night is not going to happen. The alternative is goods in the
building that the system has never heard of.

Nothing sets a count. Every endpoint writes a *difference*, which is what
makes two people working the same shelf at once safe: the second save adds to
the first rather than erasing it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import locations as loc
from app import products as pr
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import SessionDep, StockViewer, WarehouseUser
from app.models import (
    Location,
    Product,
    ProductVariant,
    StockMovement,
    StockMovementKind,
    Supply,
    SupplyLine,
    SupplyStatus,
    User,
    utcnow,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


def _next_code(session: SessionDep, model, prefix: str) -> str:
    """The next code in a series, ours rather than anybody else's."""
    used = session.exec(select(func.count()).select_from(model)).one()
    return f"{prefix}-{int(used) + 1:06d}"


# --------------------------------------------------------------------------- market runs


@router.post(
    "/supplies",
    response_model=list[s.SupplyOut],
    status_code=status.HTTP_201_CREATED,
    summary="Sacks are in the building — thirty seconds at the door",
)
def start_run(
    payload: s.SupplyCreateIn, user: WarehouseUser, session: SessionDep
) -> list[s.SupplyOut]:
    """One draft per sack, so each is sorted and closed on its own.

    Five sacks is five rows and not one row with a count on it: they will be
    opened on different evenings by different people, and a run that can only
    be closed all at once is a run that stays open until the last sack is
    dealt with.
    """
    runs = []
    for _ in range(payload.sacks):
        run = Supply(
            code=_next_code(session, Supply, "SUP"),
            place=payload.place.strip(),
            # The whole fare against the first sack rather than divided by
            # five: apportioning a taxi across sacks is arithmetic nobody
            # asked for, and the total run cost is the same either way.
            transport_cost=payload.transport_cost if not runs else 0,
            note=payload.note,
            buyer_id=user.id,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        runs.append(run)

    audit.record(
        session,
        actor=user,
        action="supply.start",
        entity="supply",
        entity_id=runs[0].id,
        field="sacks",
        old=None,
        new=payload.sacks,
        note=payload.place,
    )
    session.commit()
    return [_supply_out(session, run) for run in runs]


@router.get(
    "/supplies",
    response_model=list[s.SupplyOut],
    summary="Market runs, unsorted ones first",
)
def list_supplies(
    user: StockViewer,
    session: SessionDep,
    status_filter: SupplyStatus | None = Query(None, alias="status"),
) -> list[s.SupplyOut]:
    stmt = select(Supply)
    if status_filter is not None:
        stmt = stmt.where(Supply.status == status_filter)
    # The same rule as the order queue: a queue is worked from the front, a
    # history is read from the top. `draft` is sacks standing on the floor,
    # and serving the newest first is how the one that came on Monday is still
    # there on Friday.
    waiting = status_filter is SupplyStatus.DRAFT
    rows = session.exec(
        stmt.order_by(
            col(Supply.declared_at) if waiting else col(Supply.declared_at).desc(),
            col(Supply.id) if waiting else col(Supply.id).desc(),
        )
    ).all()
    return [_supply_out(session, row) for row in rows]


@router.get("/supplies/{supply_id}", response_model=s.SupplyOut)
def get_supply(supply_id: int, user: StockViewer, session: SessionDep) -> s.SupplyOut:
    return _supply_out(session, _supply(session, supply_id))


@router.put(
    "/supplies/{supply_id}/lines",
    response_model=s.SupplyOut,
    summary="What was in the sack — written while sorting",
)
def sort_run(
    supply_id: int,
    payload: s.SupplySortIn,
    user: WarehouseUser,
    session: SessionDep,
) -> s.SupplyOut:
    """The sorting itself: pile by pile, what it is and how many.

    Replaces the lines rather than adding to them, because sorting is a table
    somebody is filling in and leaving it half-saved between two shapes is how
    a pile gets counted twice. Nothing moves yet — the run is still a draft,
    and the goods are still a sack.
    """
    run = _draft(session, supply_id)

    for line in payload.lines:
        _variant(session, line.variant_id)

    for old in session.exec(
        select(SupplyLine).where(SupplyLine.supply_id == run.id)
    ).all():
        session.delete(old)
    for line in payload.lines:
        session.add(
            SupplyLine(
                supply_id=run.id,
                variant_id=line.variant_id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
            )
        )
    if payload.place is not None:
        run.place = payload.place.strip()
    if payload.transport_cost is not None:
        run.transport_cost = payload.transport_cost
    if payload.note is not None:
        run.note = payload.note
    session.add(run)
    session.commit()
    session.refresh(run)
    return _supply_out(session, run)


@router.post(
    "/supplies/{supply_id}/receive",
    response_model=s.SupplyOut,
    summary="Close a run — this is where goods reach the shelf",
)
def receive_supply(
    supply_id: int, user: WarehouseUser, session: SessionDep
) -> s.SupplyOut:
    """Closing the draft is what brings the goods into existence.

    Every line has to name a real variant, and a run with no lines cannot be
    closed: an empty receipt is a sack somebody ticked off without opening.

    A closed run is not reopened. Correct it with an adjustment, so the ledger
    keeps the truth about what was believed at the time rather than being
    edited into agreement with what was found later.
    """
    run = _draft(session, supply_id)
    lines = session.exec(
        select(SupplyLine).where(SupplyLine.supply_id == run.id)
    ).all()
    if not lines:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("supply_nothing_sorted")
        )

    receiving = loc.staging(session, loc.QABUL)
    touched: set[int] = set()
    for line in lines:
        variant = _variant(session, line.variant_id)
        # Into the receiving area and not onto a shelf. Somebody carries it
        # to a cell afterwards and records which — until they do, the goods
        # are in QABUL, which is a place and not a state of not being
        # anywhere. They are sellable from there: the pick list simply sends
        # the picker to the desk instead of to a rack.
        st.move(
            session,
            variant=variant,
            qty=line.quantity,
            kind=StockMovementKind.RECEIPT,
            frm=None,
            to=receiving,
            actor=user,
            reason=run.note or f"{run.code} qabul qilindi",
            supply_id=run.id,
        )
        touched.add(variant.product_id)

    run.status = SupplyStatus.RECEIVED
    run.received_at = utcnow()
    run.received_by_id = user.id
    session.add(run)

    audit.record(
        session,
        actor=user,
        action="supply.receive",
        entity="supply",
        entity_id=run.id,
        field="status",
        old=SupplyStatus.DRAFT,
        new=SupplyStatus.RECEIVED,
        note=run.place,
    )
    session.commit()
    for product_id in sorted(touched):
        pr.refresh(session, product_id)
    session.commit()

    session.refresh(run)
    return _supply_out(session, run)


@router.post(
    "/supplies/{supply_id}/cancel",
    response_model=s.SupplyOut,
    summary="A sack that is not going to be booked in",
)
def cancel_supply(
    supply_id: int,
    payload: s.SupplyCancelIn,
    user: WarehouseUser,
    session: SessionDep,
) -> s.SupplyOut:
    """Only a draft. A closed run is corrected, never called off."""
    run = _draft(session, supply_id)
    run.status = SupplyStatus.CANCELLED
    run.note = payload.reason.strip()
    session.add(run)
    audit.record(
        session,
        actor=user,
        action="supply.cancel",
        entity="supply",
        entity_id=run.id,
        field="status",
        old=SupplyStatus.DRAFT,
        new=SupplyStatus.CANCELLED,
        note=run.note,
    )
    session.commit()
    session.refresh(run)
    return _supply_out(session, run)


# --------------------------------------------------------------------------- the shelf


@router.post(
    "/stock/damage",
    response_model=s.ShelfOut,
    summary="Goods that are broken — into the damaged corner",
)
def damage(
    payload: s.WriteOffIn, user: WarehouseUser, session: SessionDep
) -> s.ShelfOut:
    """Not off the books: into ``BRAK``, which is a place in the building.

    A broken shirt has not evaporated. It is in the corner by the door, it is
    countable, and somebody will eventually decide whether it goes back to the
    market or into a bin — none of which is sayable if the ledger's answer to
    "damaged" is that the goods stopped existing.
    """
    variant = _variant(session, payload.variant_id)
    corner = loc.staging(session, loc.BRAK)

    try:
        st.take_from_shelf(
            session,
            variant,
            payload.quantity,
            kind=StockMovementKind.DAMAGE,
            to=corner,
            actor=user,
            reason=payload.reason,
        )
    except st.StockError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None

    audit.record(
        session,
        actor=user,
        action="stock.damage",
        entity="product_variant",
        entity_id=variant.id,
        field="location",
        old=None,
        new=corner.code,
        note=payload.reason,
    )
    pr.refresh(session, variant.product_id)
    session.commit()
    session.refresh(variant)
    return _shelf_out(session, variant)


@router.get(
    "/stock/movements",
    response_model=s.Page[s.MovementOut],
    summary="The ledger — every reason a count changed",
)
def list_movements(
    user: StockViewer,
    session: SessionDep,
    variant_id: int | None = Query(None),
    kind: StockMovementKind | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> s.Page[s.MovementOut]:
    """A count that looks wrong is not an argument, it is this list."""
    stmt = select(StockMovement)
    if variant_id is not None:
        stmt = stmt.where(StockMovement.variant_id == variant_id)
    if kind is not None:
        stmt = stmt.where(StockMovement.kind == kind)

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(StockMovement.created_at).desc(), col(StockMovement.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.MovementOut](
        items=[_movement_out(session, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


# --------------------------------------------------------------------------- helpers


def _supply(session: SessionDep, supply_id: int) -> Supply:
    run = session.get(Supply, supply_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("supply_not_found"))
    return run


def _draft(session: SessionDep, supply_id: int) -> Supply:
    run = _supply(session, supply_id)
    if run.status is not SupplyStatus.DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=run.status.value, to="received"),
        )
    return run


def _variant(session: SessionDep, variant_id: int) -> ProductVariant:
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("variant_invalid"))
    return variant


def _names(session: SessionDep, variant_id: int) -> tuple[str, str, str]:
    """The label, the title and the code — what a person and a scanner read.

    **The label names the whole cell of the grid**, "Oq · S" and not "S". A
    receipt of a two-colour shirt used to produce six lines reading "S", "M",
    "L", "S", "M", "L", with somebody typing a count against each: two rows
    that read identically on the screen where the counting happens is the
    shape of a miscount.
    """
    variant = session.get(ProductVariant, variant_id)
    product = session.get(Product, variant.product_id) if variant else None
    label = sv.variant_label(variant) if variant else "—"
    return (
        label or "—",
        (product.title if product else ""),
        (variant.sku if variant and variant.sku else (product.sku if product else "")),
    )


def _supply_out(session: SessionDep, supply: Supply) -> s.SupplyOut:
    lines = session.exec(
        select(SupplyLine).where(SupplyLine.supply_id == supply.id).order_by(col(SupplyLine.id))
    ).all()
    out = []
    for line in lines:
        label, title, sku = _names(session, line.variant_id)
        out.append(
            s.SupplyLineOut(
                id=line.id,
                variant_id=line.variant_id,
                sku=sku,
                variant_label=label,
                product_title=title,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                line_cost=line.line_cost,
            )
        )
    buyer = session.get(User, supply.buyer_id) if supply.buyer_id else None
    # Standing time is what turns an unsorted run from a row in a list into
    # something somebody acts on, so it is computed here rather than left to
    # each client to work out from a timestamp.
    since = supply.received_at or utcnow()
    return s.SupplyOut(
        id=supply.id,
        code=supply.code,
        status=supply.status,
        place=supply.place,
        transport_cost=supply.transport_cost,
        buyer=(buyer.full_name or buyer.phone) if buyer else "",
        note=supply.note,
        lines=out,
        total_cost=sum(line.line_cost for line in lines) + supply.transport_cost,
        declared_at=supply.declared_at,
        received_at=supply.received_at,
        age_minutes=max(0, int((since - supply.declared_at).total_seconds() // 60)),
    )


def _shelf_out(session: SessionDep, variant: ProductVariant) -> s.ShelfOut:
    label, _, _ = _names(session, variant.id)
    return s.ShelfOut(
        variant_id=variant.id,
        variant_label=label,
        on_hand=st.on_hand(session, variant.id),
        reserved=st.reserved(session, variant.id),
        sellable=st.sellable(session, variant),
        places=[
            s.PlacementOut(location_id=place.id, code=place.code, qty=qty)
            for place, qty in st.placements(session, variant.id)
        ],
    )


def _code(session: SessionDep, location_id: int | None) -> str:
    """A place's code, or the outside world.

    The em dash is the point: "from —" is a market run arriving and "to —" is
    a parcel out of the door, and both are moves the room made rather than
    holes in the record.
    """
    if location_id is None:
        return "—"
    place = session.get(Location, location_id)
    return place.code if place else "—"


def _movement_out(session: SessionDep, movement: StockMovement) -> s.MovementOut:
    label, title, sku = _names(session, movement.variant_id)
    actor = session.get(User, movement.actor_id) if movement.actor_id else None
    return s.MovementOut(
        id=movement.id,
        variant_id=movement.variant_id,
        sku=sku,
        variant_label=label,
        product_title=title,
        kind=movement.kind,
        quantity=movement.qty,
        from_code=_code(session, movement.from_location_id),
        to_code=_code(session, movement.to_location_id),
        reason=movement.reason,
        actor=(actor.full_name or actor.phone) if actor else "tizim",
        supply_id=movement.supply_id,
        order_id=movement.order_id,
        return_request_id=movement.return_request_id,
        created_at=movement.created_at,
    )
