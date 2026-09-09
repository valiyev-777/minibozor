"""The room, and the three things people do to it.

**The map** is the screen the shop is judged by. It answers in one request,
because it draws the whole room at once: three units of cells, the staging
areas as their own row, and a tile per courier who is holding something.

**Putaway** is the queue of goods standing in the receiving area with nobody
having said where they went. Oldest first, with the age in plain words, and a
cell code that is *typed*. Market goods arrive with no usable code of their own
and the owner's phone cameras read codes badly, so every field here is a text
input — one that keeps working unchanged when a scanner gun is plugged in
later, because a gun types the code and presses Enter.

**Counting** is a cell at a time. A stocktake of the whole warehouse is a day
nobody has; a cell is what one person can count without stopping the shop, and
what it finds becomes an ``adjust`` movement with the counter's name on it.

And the label sheet, because we generate the barcodes: market goods arrive
unlabelled, so the only code a pile will ever have is the one we print.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import idempotency as idem
from app import locations as loc
from app import products as pr
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import SessionDep, StockViewer, WarehouseUser
from app.models import (
    CountStatus,
    Location,
    LocationKind,
    Product,
    ProductVariant,
    StockCount,
    StockCountLine,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    User,
    utcnow,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", description="A uuid per queued action")
]


# --------------------------------------------------------------------------- the map


@router.get(
    "/locations",
    response_model=s.ShelfMapOut,
    summary="The whole room — the shelf map draws all of it at once",
)
def shelf_map(user: StockViewer, session: SessionDep) -> s.ShelfMapOut:
    """Every place, with what is in it and how full it is.

    One request rather than one per cell: the map is a picture of a room and
    a room is not paged. Three lists because the screen has three shapes — a
    grid of racks, a row of staging tiles above them, and a courier's bag,
    which exists only while somebody is carrying something.
    """
    places = session.exec(select(Location).where(col(Location.is_active).is_(True))).all()
    summary = _fill(session)

    cells = [
        _location_out(place, summary) for place in places if place.kind is LocationKind.BIN
    ]
    cells.sort(key=lambda out: (out.rack or "", out.column_no or 0, out.row_no or 0))
    staging = [
        _location_out(place, summary)
        for place in places
        if place.kind in (
            LocationKind.RECEIVING,
            LocationKind.PACKING,
            LocationKind.DAMAGED,
            LocationKind.RETURNS,
        )
    ]
    couriers = [
        _location_out(place, summary)
        for place in places
        if place.kind is LocationKind.COURIER and summary.get(place.id, (0, 0, None))[1]
    ]
    return s.ShelfMapOut(cells=cells, staging=staging, couriers=couriers)


@router.get(
    "/locations/{code}",
    response_model=s.LocationDetailOut,
    summary="What is in one place",
)
def location_detail(
    code: str, user: StockViewer, session: SessionDep
) -> s.LocationDetailOut:
    place = _place(session, code)
    out = _location_out(place, _fill(session))
    return s.LocationDetailOut(
        **out.model_dump(), contents=_contents(session, place)
    )


@router.get(
    "/where-is",
    response_model=list[s.WhereIsOut],
    summary="Find it fast — by name, SKU or barcode",
)
def where_is(
    user: StockViewer,
    session: SessionDep,
    q: str = Query(min_length=1, description="A product name, a SKU, or a barcode"),
) -> list[s.WhereIsOut]:
    """The one feature the whole warehouse exists for.

    A barcode or a SKU answers exactly, because it names one cell of the grid.
    A name answers with every variant of every card that matches, which is the
    honest answer to "where are the trainers" — they are in nine places, and
    the screen dims everything else so the nine light up.
    """
    needle = q.strip().lower()
    exact = session.exec(
        select(ProductVariant).where(
            (func.lower(ProductVariant.barcode) == needle)
            | (func.lower(ProductVariant.sku) == needle)
        )
    ).all()

    if exact:
        variants = list(exact)
    else:
        products = session.exec(
            select(Product.id).where(func.lower(Product.title).like(f"%{needle}%"))
        ).all()
        variants = list(
            session.exec(
                select(ProductVariant).where(
                    col(ProductVariant.product_id).in_(list(products) or [-1])
                )
            ).all()
        )

    found = []
    for variant in variants:
        places = st.placements(session, variant.id)
        if not places:
            continue
        product = session.get(Product, variant.product_id)
        found.append(
            s.WhereIsOut(
                variant_id=variant.id,
                product_id=variant.product_id,
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant),
                sku=variant.sku,
                barcode=variant.barcode,
                places=[
                    s.PlacementOut(location_id=place.id, code=place.code, qty=qty)
                    for place, qty in places
                ],
            )
        )
    return found


# --------------------------------------------------------------------------- putaway


@router.get(
    "/putaway",
    response_model=list[s.PutawayLineOut],
    summary="What is standing in QABUL, oldest first",
)
def putaway_queue(user: StockViewer, session: SessionDep) -> list[s.PutawayLineOut]:
    """The queue, and how long each line has been standing.

    There is no ``PutawayTask`` table and deliberately so: being in the
    receiving area *is* the state of not having been shelved, and a task row
    beside it would be a second answer to the same question — one that can
    disagree with the shelf.

    The suggestion is a cell this model is already in. One model per cell is
    the working discipline and the software supports it rather than enforcing
    it, so this is a default somebody may overrule and not a rule.
    """
    receiving = loc.staging(session, loc.QABUL)
    lines = _contents(session, receiving)
    out = []
    for line in lines:
        out.append(
            s.PutawayLineOut(
                **line.model_dump(),
                suggestion=_suggest_cell(session, line.variant_id, line.product_id),
            )
        )
    out.sort(key=lambda row: -row.minutes_here)
    return out


@router.post(
    "/putaway",
    response_model=s.LocationDetailOut,
    summary="Carry a quantity to a cell",
)
def put_away(
    payload: s.PutawayIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.LocationDetailOut:
    """Out of the receiving area and into the cell that was typed.

    Answers with the cell, not with a message: the person who just put four
    pairs in A-02-03 is about to want to know what is in A-02-03, and being
    shown it is how a mistyped code is caught in the second it was made.
    """
    done = idem.replay(session, user, idempotency_key, "putaway", payload)
    if done is not None:
        return s.LocationDetailOut(**done)

    variant = _variant(session, payload.variant_id)
    cell = _place(session, payload.code)
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("putaway_needs_a_cell"))

    receiving = loc.staging(session, loc.QABUL)
    try:
        st.move(
            session,
            variant=variant,
            qty=payload.qty,
            kind=StockMovementKind.PUTAWAY,
            frm=receiving,
            to=cell,
            actor=user,
            reason=payload.code.strip().upper(),
        )
    except st.StockError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None

    out = s.LocationDetailOut(
        **_location_out(cell, _fill(session)).model_dump(),
        contents=_contents(session, cell),
    )
    idem.keep(session, user, idempotency_key, "putaway", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "putaway")
    return s.LocationDetailOut(**replayed) if replayed else out


# --------------------------------------------------------------------------- counting


@router.post(
    "/counts",
    response_model=s.CountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start counting one cell",
)
def start_count(
    payload: s.CountStartIn, user: WarehouseUser, session: SessionDep
) -> s.CountOut:
    """What the system thinks is in the cell, ready to be disagreed with.

    One count per cell at a time. Two people counting the same shelf are two
    answers about one moment, and the second to submit would silently win.
    """
    cell = _place(session, payload.code)
    open_already = session.exec(
        select(StockCount).where(
            StockCount.location_id == cell.id, StockCount.status == CountStatus.OPEN
        )
    ).first()
    if open_already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("count_already_open"))

    count = StockCount(location_id=cell.id, counter_id=user.id)
    session.add(count)
    session.commit()
    session.refresh(count)

    for line in _contents(session, cell):
        session.add(
            StockCountLine(
                count_id=count.id,
                variant_id=line.variant_id,
                expected_qty=line.qty,
                counted_qty=line.qty,
            )
        )
    session.commit()
    return _count_out(session, count)


@router.get("/counts/{count_id}", response_model=s.CountOut)
def get_count(count_id: int, user: StockViewer, session: SessionDep) -> s.CountOut:
    return _count_out(session, _count(session, count_id))


@router.post(
    "/counts/{count_id}/submit",
    response_model=s.CountOut,
    summary="What is actually there — the difference goes in the ledger",
)
def submit_count(
    count_id: int,
    payload: s.CountSubmitIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.CountOut:
    """The difference becomes a move, with the counter's name on it.

    Never an assignment. A cell that was three short is three that went
    somewhere, and writing the new figure over the old one loses the only
    thing anybody will want to look at afterwards — that it happened, when,
    and who found it.

    A shortfall moves out of the building and a surplus moves into it, because
    from the room's point of view that is exactly what a miscount is: goods
    that were never here, or goods nobody recorded arriving.
    """
    done = idem.replay(session, user, idempotency_key, "count.submit", payload)
    if done is not None:
        return s.CountOut(**done)

    count = _count(session, count_id)
    if count.status is not CountStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("count_already_closed"))
    cell = session.get(Location, count.location_id)

    lines = {
        row.variant_id: row
        for row in session.exec(
            select(StockCountLine).where(StockCountLine.count_id == count.id)
        ).all()
    }

    touched: set[int] = set()
    for counted in payload.lines:
        variant = _variant(session, counted.variant_id)
        row = lines.get(counted.variant_id)
        if row is None:
            # Something turned up that the system did not know was here, which
            # is the other half of what a count is for.
            row = StockCountLine(
                count_id=count.id, variant_id=variant.id, expected_qty=0
            )
        row.counted_qty = counted.counted_qty
        session.add(row)

        difference = row.counted_qty - row.expected_qty
        if difference:
            st.move(
                session,
                variant=variant,
                qty=abs(difference),
                kind=StockMovementKind.ADJUST,
                frm=None if difference > 0 else cell,
                to=cell if difference > 0 else None,
                actor=user,
                reason=payload.note or i18n.label("count_difference"),
                allow_negative=True,
            )
            audit.record(
                session,
                actor=user,
                action="stock.count",
                entity="product_variant",
                entity_id=variant.id,
                field=cell.code,
                old=row.expected_qty,
                new=row.counted_qty,
                note=payload.note,
            )
            touched.add(variant.product_id)

    count.status = CountStatus.CLOSED
    count.closed_at = utcnow()
    count.note = payload.note
    session.add(count)
    for product_id in sorted(touched):
        pr.refresh(session, product_id)

    out = _count_out(session, count)
    idem.keep(session, user, idempotency_key, "count.submit", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "count.submit")
    return s.CountOut(**replayed) if replayed else out


# --------------------------------------------------------------------------- labels


@router.get(
    "/labels",
    response_model=s.LabelSheetOut,
    summary="The data behind a printable A4 sheet",
)
def labels(
    user: StockViewer,
    session: SessionDep,
    supply_id: int | None = Query(None, description="Everything one market run brought"),
    variant_id: list[int] | None = Query(None),
    cells: bool = Query(False, description="A full set of cell labels instead"),
) -> s.LabelSheetOut:
    """What to print, and nothing about how.

    The barcode is drawn in the browser: a barcode is a picture of a string,
    and rendering it client-side means no image to store, no font to install
    on a server, and a reprint that cannot drift from the code on the row.

    A variant's barcode is permanent. When the same goods arrive again the
    label is **reprinted** — this endpoint answers with the code that is on
    the row, never a new one — because a second code for one thing is a shelf
    holding it twice.
    """
    if cells:
        return s.LabelSheetOut(
            cells=[
                s.CellLabelOut(
                    code=place.code,
                    rack=place.rack,
                    column_no=place.column_no,
                    row_no=place.row_no,
                )
                for place in loc.cells(session)
            ]
        )

    stmt = select(ProductVariant)
    if supply_id is not None:
        from app.models import SupplyLine

        wanted = session.exec(
            select(SupplyLine.variant_id).where(SupplyLine.supply_id == supply_id)
        ).all()
        stmt = stmt.where(col(ProductVariant.id).in_(list(wanted) or [-1]))
    elif variant_id:
        stmt = stmt.where(col(ProductVariant.id).in_(variant_id))
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("labels_need_a_selection")
        )

    out = []
    for variant in session.exec(stmt).all():
        product = session.get(Product, variant.product_id)
        out.append(
            s.ProductLabelOut(
                variant_id=variant.id,
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant),
                sku=variant.sku,
                barcode=variant.barcode,
                price=variant.price or (product.price if product else 0),
            )
        )
    return s.LabelSheetOut(products=out)


# --------------------------------------------------------------------------- helpers


def _place(session: SessionDep, code: str) -> Location:
    place = loc.by_code(session, code)
    if place is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("location_not_found", code=code)
        )
    return place


def _variant(session: SessionDep, variant_id: int) -> ProductVariant:
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("variant_invalid"))
    return variant


def _fill(session: SessionDep) -> dict[int, tuple[int, int, object]]:
    """How many products, how many units, and the oldest arrival, per place.

    One grouped query for the whole room rather than one per cell: the map
    draws fifty-odd places and a query each is what makes a picture of a room
    take a second to load.
    """
    rows = session.exec(
        select(
            StockPlacement.location_id,
            func.count(),
            func.coalesce(func.sum(StockPlacement.qty), 0),
        )
        .where(StockPlacement.qty > 0)
        .group_by(col(StockPlacement.location_id))
    ).all()
    ages = session.exec(
        select(
            StockMovement.to_location_id,
            func.min(StockMovement.created_at),
        )
        .where(col(StockMovement.to_location_id).is_not(None))
        .group_by(col(StockMovement.to_location_id))
    ).all()
    oldest = {location_id: when for location_id, when in ages}
    return {
        int(location_id): (int(products), int(units), oldest.get(location_id))
        for location_id, products, units in rows
    }


def _location_out(place: Location, summary: dict) -> s.LocationOut:
    products, units, oldest = summary.get(place.id, (0, 0, None))
    return s.LocationOut(
        id=place.id,
        code=place.code,
        kind=place.kind,
        rack=place.rack,
        column_no=place.column_no,
        row_no=place.row_no,
        capacity=place.capacity,
        is_active=place.is_active,
        note=place.note,
        products=products,
        units=units,
        fill_percent=(
            min(100, round(units / place.capacity * 100)) if place.capacity else 0
        ),
        oldest_minutes=_minutes(oldest) if units else 0,
    )


def _contents(session: SessionDep, place: Location) -> list[s.CellContentOut]:
    rows = session.exec(
        select(StockPlacement).where(
            StockPlacement.location_id == place.id, StockPlacement.qty > 0
        )
    ).all()
    out = []
    for row in rows:
        variant = session.get(ProductVariant, row.variant_id)
        if variant is None:
            continue
        product = session.get(Product, variant.product_id)
        arrived = session.exec(
            select(func.max(StockMovement.created_at)).where(
                StockMovement.to_location_id == place.id,
                StockMovement.variant_id == variant.id,
            )
        ).one()
        out.append(
            s.CellContentOut(
                variant_id=variant.id,
                product_id=variant.product_id,
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant),
                sku=variant.sku,
                barcode=variant.barcode,
                qty=row.qty,
                minutes_here=_minutes(arrived),
            )
        )
    out.sort(key=lambda line: (line.product_title, line.variant_label))
    return out


def _suggest_cell(session: SessionDep, variant_id: int, product_id: int) -> str:
    """A cell this model is already in, if it is in one.

    One model per cell is the discipline, so the useful default is where the
    rest of the model already lives — every colour and every size of it
    together, which is what leaves a picker choosing between sizes instead of
    hunting the room.
    """
    siblings = session.exec(
        select(ProductVariant.id).where(ProductVariant.product_id == product_id)
    ).all()
    rows = session.exec(
        select(StockPlacement, Location)
        .join(Location, col(Location.id) == col(StockPlacement.location_id))
        .where(
            col(StockPlacement.variant_id).in_(list(siblings) or [-1]),
            StockPlacement.qty > 0,
            Location.kind == LocationKind.BIN,
        )
    ).all()
    if not rows:
        return ""
    best = sorted(rows, key=lambda pair: loc.walk_order(pair[1]))[0]
    return best[1].code


def _count(session: SessionDep, count_id: int) -> StockCount:
    row = session.get(StockCount, count_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("count_not_found"))
    return row


def _count_out(session: SessionDep, count: StockCount) -> s.CountOut:
    place = session.get(Location, count.location_id)
    counter = session.get(User, count.counter_id) if count.counter_id else None
    lines = []
    for row in session.exec(
        select(StockCountLine)
        .where(StockCountLine.count_id == count.id)
        .order_by(col(StockCountLine.id))
    ).all():
        variant = session.get(ProductVariant, row.variant_id)
        product = session.get(Product, variant.product_id) if variant else None
        lines.append(
            s.CountLineOut(
                variant_id=row.variant_id,
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant) if variant else "",
                sku=variant.sku if variant else "",
                barcode=variant.barcode if variant else "",
                expected_qty=row.expected_qty,
                counted_qty=row.counted_qty,
            )
        )
    return s.CountOut(
        id=count.id,
        location_id=count.location_id,
        location_code=place.code if place else "",
        status=count.status,
        counter=(counter.full_name or counter.phone) if counter else "",
        note=count.note,
        lines=lines,
        started_at=count.started_at,
        closed_at=count.closed_at,
    )


def _minutes(since) -> int:
    if since is None:
        return 0
    return max(0, int((utcnow() - since).total_seconds() // 60))
