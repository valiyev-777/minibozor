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

**The shape of the room** is data and has three doors, on purpose. Building a
rack refuses a letter that is taken, because "A, 6 columns" against an
existing A of four cannot be told from a typo; bolting cells onto a rack that
is standing is the second door, takes the shape the rack should have, and
never removes anything. Removing is the third, and it is one cell at a time,
by somebody who has looked in it: a rack grown to 6×4 by a typo carried two
dead columns for ever, because nothing anywhere wrote ``is_active`` and the
two doors above both said "retiring one is ``is_active``" as though a door
existed. A retired cell keeps its code and its history and leaves the room —
it cannot be put into, and the map fetches it back from ``GET
/warehouse/cells/retired`` in order to offer the way back.

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
from app.deps import AdminUser, SessionDep, StockViewer, WarehouseUser
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

    **Live places only, and ``cells`` keeps meaning what it has always meant.**
    Everything that reads this list counts it — how many cells are full, how
    many are empty, which ones a pile may be sent to, how many labels to
    print — so a retired cell arriving in it would make every one of those
    quietly wrong in arithmetic. The cells somebody took out of the room come
    back from ``GET /warehouse/cells/retired``, which is one more request on
    the one screen that wants to draw the hole.
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


@router.get(
    "/suggest-cell",
    response_model=s.SuggestedCellOut,
    summary="Where this model already lives, if anywhere",
)
def suggest_cell(
    product_id: int, user: StockViewer, session: SessionDep
) -> s.SuggestedCellOut:
    """The default the receiving form should offer.

    One model per cell is the discipline, so the useful cell is the one the
    rest of the model is already in: every colour and size of it together,
    which is what leaves a picker choosing between sizes rather than hunting
    the room. Empty when the model is new or has nothing on a shelf.

    A suggestion and not a rule — the cell may be full, and the person can see
    that on the same screen.

    **For a whole pile, ask ``GET /warehouse/putaway-plan`` instead.** This
    answers "where does this model live", which is one cell and one cheap
    query, and it is the right question for a form filling in a default field
    while somebody types. It says nothing about whether eighty pairs fit in
    that cell; the plan is the question with the quantity in it.
    """
    return s.SuggestedCellOut(code=_suggest_cell(session, 0, product_id))


@router.get(
    "/putaway-plan",
    response_model=s.PutawayPlanOut,
    summary="Where these N pieces would go if nobody thought about it",
)
def putaway_plan(
    user: StockViewer,
    session: SessionDep,
    product_id: int,
    quantity: int = Query(gt=0, le=100_000, description="How many pieces are arriving"),
) -> s.PutawayPlanOut:
    """The whole answer the receiving screen needs, in one request.

    ``suggest-cell`` offers one code and says nothing about room, so a person
    holding eighty pairs got a cell with space for four and worked the other
    seventy-six out by eye — against a shelf map on a different screen. This
    is the same judgement, made once, with the quantity in the question.

    The rule, in this order:

    * the cells that already hold this model, in walk order, each filled to
      its free room — one model per cell is the discipline and the goods want
      to be together;
    * then the emptiest cells, nearest those in walk order, until the
      quantity is placed. Emptiest means holding least, which is how a cell
      with nothing in it always comes before one with somebody else's shirts
      in it; nearest keeps the pile in one aisle instead of at both ends of
      the room.

    A cell with no stated capacity takes whatever is left rather than being
    treated as holding nothing: nobody has measured it, and refusing to use
    it would leave the plan short of a cell that is plainly there.

    **If the building has no room the plan says so and over-fills the last
    cell anyway.** The goods are standing on the floor. A plan that stops at
    seventy of eighty does not say where the other ten went, and somebody
    puts them somewhere without telling anyone; an honest 130% is a cell
    people walk past and tidy.

    A suggestion throughout. Nothing here writes anything, and the receiving
    screen is free to type over every line of it.
    """
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    cells = loc.cells(session)
    if not cells:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("putaway_plan_needs_cells")
        )

    units = st.units_by_place(session)
    holders = _cells_holding(session, product_id)
    where = {cell.id: position for position, cell in enumerate(cells)}

    own = [cell for cell in cells if cell.id in holders]
    rest = [cell for cell in cells if cell.id not in holders]
    # The model's own cells anchor the rest: a pile that outgrows A-02-01
    # should carry on into A-02-02 rather than start again in C.
    anchor = where[own[0].id] if own else 0
    rest.sort(key=lambda cell: (units.get(cell.id, 0), abs(where[cell.id] - anchor)))

    left = quantity
    lines: list[s.PutawayPlanLineOut] = []
    for cell in own + rest:
        if left <= 0:
            break
        held = units.get(cell.id, 0)
        free = st.free_room(cell, held)
        take = left if free is None else min(left, free)
        if take <= 0:
            continue
        lines.append(
            s.PutawayPlanLineOut(
                code=cell.code,
                quantity=take,
                free=free,
                units=held,
                holds_this_model=cell.id in holders,
            )
        )
        left -= take

    over = ""
    if left > 0:
        # Every cell in the building is full and the van is still outside.
        last = (own + rest)[-1]
        if lines and lines[-1].code == last.code:
            lines[-1].quantity += left
        else:
            lines.append(
                s.PutawayPlanLineOut(
                    code=last.code,
                    quantity=left,
                    free=st.free_room(last, units.get(last.id, 0)),
                    units=units.get(last.id, 0),
                    holds_this_model=last.id in holders,
                )
            )
        over = i18n.label("putaway_plan_over_capacity", code=last.code, over=left)

    return s.PutawayPlanOut(
        quantity=quantity,
        lines=lines,
        over_capacity=bool(over),
        message=over,
    )


# ------------------------------------------------------------------ the room's shape


@router.post(
    "/racks",
    response_model=s.RackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Build a shelf unit — a letter, and a grid of cells",
)
def add_rack(
    payload: s.RackWriteIn,
    # The office's. A rack is the shape of the building: everybody else in here
    # moves goods between places that exist, and inventing a place is a decision
    # about the room rather than about a sack.
    user: AdminUser,
    session: SessionDep,
) -> s.RackOut:
    """A new unit of shelving, as cells with codes on them.

    The racks were always data — ``locations.RACKS`` is a list the seed reads,
    and nothing anywhere writes 3, 4 or 48 as a number — but the only way to
    add a fourth was to edit that list and run the seed, which is a deployment
    for a job that is really a Saturday afternoon with a screwdriver. This is
    the same write, through a door.

    Columns times rows cells, coded ``B-03-02`` by `locations.cell_code`, row 1
    at the floor. The capacity is per cell and is shown rather than enforced,
    exactly as the seeded ones are.

    **Refused where the letter is taken**, rather than quietly filling in the
    cells a smaller rack is missing: "A, 6 columns" against an existing A of 4
    reads as a correction, and this cannot tell that from a typo. Retiring a
    cell is `is_active`, and growing a rack is a job for the day somebody asks
    for it.
    """
    rack = payload.rack.strip().upper()
    taken = session.exec(
        select(Location).where(Location.rack == rack).limit(1)
    ).first()
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("rack_exists"))

    made = 0
    for column_no in range(1, payload.columns + 1):
        for row_no in range(1, payload.rows + 1):
            code = loc.cell_code(rack, column_no, row_no)
            # A code is unique across the building, and a staging area or an
            # old retired cell could already hold this one.
            if loc.by_code(session, code) is not None:
                continue
            session.add(
                Location(
                    code=code,
                    kind=LocationKind.BIN,
                    rack=rack,
                    column_no=column_no,
                    row_no=row_no,
                    capacity=payload.capacity,
                )
            )
            made += 1
    session.commit()

    audit.record(
        session,
        actor=user,
        action="location.rack_added",
        entity="location",
        entity_id=0,
        field="rack",
        old=None,
        new=rack,
        note=f"{made} ta yacheyka",
    )
    session.commit()
    return s.RackOut(
        rack=rack,
        cells=made,
        message=i18n.label("rack_added", rack=rack, cells=made),
    )


@router.post(
    "/racks/{rack}/cells",
    response_model=s.RackOut,
    summary="Bolt cells onto a rack that is already standing",
)
def extend_rack(
    rack: str,
    payload: s.RackExtendIn,
    # The office's, like building one. A column added to A is the shape of
    # the building changing, and everybody else in here moves goods between
    # places that already exist.
    user: AdminUser,
    session: SessionDep,
) -> s.RackOut:
    """A fifth column on A, without the rack having to be built again.

    ``POST /warehouse/racks`` refuses a letter that is taken, and it is right
    to: "A, 6 columns" against an existing A of 4 reads as a correction and
    that door cannot tell a correction from a typo. But a shelf unit does
    grow — somebody bolts a column on, or a fifth row where the ceiling
    allows — and the only way to record it was to edit ``locations.RACKS``
    and run the seed, which is a deployment for a Saturday with a
    screwdriver.

    So: two doors, not one door with a mode. This one is about a rack that is
    there, and **404 when it is not** — a letter that does not exist is
    somebody meaning to build one, and they should be told so rather than
    quietly given a rack they did not ask to create.

    The body is the shape the rack should **have**, not the difference. The
    person is standing in front of it counting columns, and "add one" asks
    them to know what the system thinks is there. Every missing code inside
    that rectangle is written and **nothing is ever removed**: a smaller
    shape than the rack already has adds nothing and says so, because
    demolishing a cell that is holding forty pairs is not something a typo in
    a number box should be able to do. Retiring one is ``POST
    /warehouse/cells/{code}/active``, one cell at a time, by somebody who has
    looked in it.

    **A retired cell is not brought back by this.** Its code still exists, so
    the skip above steps over it and the count says nothing was written — the
    rack looks as though it is already that big. That is deliberate: a cell
    was taken out of the room by a decision somebody made and recorded, and
    re-typing the rack's shape is not that decision being reversed. Restoring
    it is the same door that retired it.

    **Ragged is fine.** A five-row column beside four four-row ones is a real
    shelf and the map draws a blank where a code is missing, so nothing here
    insists on a rectangle.
    """
    wanted = rack.strip().upper()
    standing = session.exec(
        select(Location).where(Location.rack == wanted, Location.kind == LocationKind.BIN)
    ).all()
    if not standing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("rack_not_found", rack=wanted)
        )

    capacity = (
        payload.capacity if payload.capacity is not None else _house_capacity(standing)
    )
    have = {place.code for place in standing}

    made = 0
    for column_no in range(1, payload.columns + 1):
        for row_no in range(1, payload.rows + 1):
            code = loc.cell_code(wanted, column_no, row_no)
            # Against the whole building and not only against this rack: a
            # code is unique everywhere, and a retired cell still owns its.
            if code in have or loc.by_code(session, code) is not None:
                continue
            session.add(
                Location(
                    code=code,
                    kind=LocationKind.BIN,
                    rack=wanted,
                    column_no=column_no,
                    row_no=row_no,
                    capacity=capacity,
                )
            )
            made += 1
    session.commit()

    if made:
        audit.record(
            session,
            actor=user,
            action="location.rack_extended",
            entity="location",
            # As with building a rack: the thing that changed is a rack, and
            # a rack is not a row. Naming one of its cells here would read as
            # a change to that cell, which is the one thing this did not do.
            entity_id=0,
            field="rack",
            old=len(standing),
            new=len(standing) + made,
            note=f"{wanted} · {made} ta yacheyka qo'shildi",
        )
        session.commit()

    return s.RackOut(
        rack=wanted,
        cells=made,
        message=(
            i18n.label("rack_extended", rack=wanted, cells=made)
            if made
            else i18n.label("rack_already_that_big", rack=wanted)
        ),
    )


def _house_capacity(cells: list[Location]) -> int:
    """What this rack's cells hold, as the commonest figure among them.

    A shelf unit is one piece of furniture: a column bolted onto it holds
    what the other columns hold, so the default for a new cell is the rack's
    own answer rather than the schema's 60 — which is A's number being
    applied to a rack of shoeboxes half the size. Commonest rather than the
    largest or the mean, because one cell someone corrected by hand should
    not drag every new cell with it.
    """
    counts: dict[int, int] = {}
    for cell in cells:
        counts[cell.capacity] = counts.get(cell.capacity, 0) + 1
    # Ties go to the bigger figure, which is the one already written on more
    # of the building than any accident would be.
    return max(counts, key=lambda capacity: (counts[capacity], capacity))


@router.get(
    "/cells/retired",
    response_model=list[s.LocationOut],
    summary="The cells that were taken out of the room, and can be put back",
)
def retired_cells(user: StockViewer, session: SessionDep) -> list[s.LocationOut]:
    """The short list the map needs to draw the holes in itself.

    Its own door rather than a flag on ``GET /warehouse/locations``, and this
    is the whole design decision about retiring a cell.

    ``cells`` in the shelf map means *the cells of this room*, and half a
    dozen things read it that way: the screen counts how many are full and how
    many are empty, the receiving screen builds its destination grid out of
    it, the label sheet prints one label per entry. Slipping dead cells into
    that list would leave every one of those quietly wrong — a full/empty
    figure counting shelves that are not there, a grid offering a cell that
    refuses the goods — and wrong in arithmetic, which is the kind of wrong
    nobody notices for a month. The fix would have to be remembered in every
    reader, including the ones in the web app, on the same day.

    So the main answer keeps its meaning exactly and the dead cells come back
    on a door of their own. The map can still draw the hole, and still offer
    the way back on the tile where somebody is looking for it: it is one more
    request, on the one screen that wants it, instead of a condition in
    everything that has ever read a cell.

    In walk order and carrying ``is_active: false``, so the screen can draw
    them struck through in the grid position they used to occupy — which is
    what tells a gap that was retired apart from a gap that was never built.
    """
    summary = _fill(session)
    rows = session.exec(
        select(Location).where(
            Location.kind == LocationKind.BIN, col(Location.is_active).is_(False)
        )
    ).all()
    return [_location_out(place, summary) for place in sorted(rows, key=loc.walk_order)]


@router.post(
    "/cells/{code}/active",
    response_model=s.LocationOut,
    summary="Take a cell out of the room, or bolt it back in",
)
def set_cell_active(
    code: str,
    payload: s.CellActiveIn,
    # The office's, like building a rack and like growing one. Retiring a cell
    # is the shape of the building changing, and not a wider guard: everybody
    # else in here moves goods between places that exist, and the warehouse
    # hand who finds a cell inconvenient at nine in the evening is exactly the
    # person this should not be a way out for.
    user: AdminUser,
    session: SessionDep,
) -> s.LocationOut:
    """A rack extended to 6×4 by mistake carries two dead columns for ever.

    That was the hole. ``is_active`` has been on ``locations`` since the first
    migration, three readers filter on it, two docstrings promise it is "the
    honest way to retire a cell" — and nothing anywhere ever wrote it. Cells
    were built and never removed.

    One door with a boolean, like ``POST /admin/users/{id}/active``: retiring
    and restoring are the same decision read from opposite sides, and two
    endpoints would be two places for the rule and the audit row to drift.

    **Not a delete, and never a delete.** The row keeps its code, its capacity
    and every movement that ever named it; a stocktake from March still points
    at a cell that still exists. What changes is that the room stops offering
    it — off the shelf map, off the label sheet, off the putaway plan — and
    that nothing may be put into it.

    **Refused while it is holding anything.** A retired cell disappears from
    the map, and goods in a place nobody can see are goods nobody can find:
    the shop's count would still include them and no picker could be sent.
    The sentence says what to do instead — carry them somewhere with ``POST
    /warehouse/move`` or ``POST /warehouse/move-cell``, or write them off with
    ``POST /warehouse/stock/empty`` — because a refusal a warehouse cannot act
    on is a refusal somebody works around.

    **Cells only.** ``QABUL``, ``YIGIM``, ``BRAK`` and ``QAYTGAN`` are not
    shelves, they are places with a job: being in ``QABUL`` *is* the unplaced
    state, ``locations.staging`` raises rather than conjuring one up, and the
    seed writes them by name — so a retired ``QABUL`` is a receiving desk the
    next seed run silently puts back while every count written into it was
    invisible to the map in between. A courier's bag is the same story from
    the other end: it is made on demand and the map draws it only while it
    holds something, so there is nothing to retire. Neither is refused for
    safety's sake; there is simply no such decision to take.

    Restoring is unconditional. A cell that is standing there again is a cell
    the room can use, and nothing about it can have gone wrong while it was
    empty and closed.
    """
    cell = _place(session, code)
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("cell_retire_needs_a_cell", code=cell.code),
        )

    if cell.is_active and not payload.active:
        held = st.units_in(session, cell.id)
        if held:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                i18n.label("cell_retire_not_empty", code=cell.code, units=held),
            )

    if cell.is_active is not payload.active:
        audit.record(
            session,
            actor=user,
            action="location.active",
            entity="location",
            entity_id=cell.id,
            field="is_active",
            old=cell.is_active,
            new=payload.active,
            note=payload.note or cell.code,
        )
        cell.is_active = payload.active
        session.add(cell)
        session.commit()
        session.refresh(cell)

    return _location_out(cell, _fill(session))


# --------------------------------------------------------------------------- moving


@router.post(
    "/move",
    response_model=s.LocationDetailOut,
    summary="Carry a quantity from where it is to a cell",
)
def move_goods(
    payload: s.MoveIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.LocationDetailOut:
    """The only way a mis-shelved pile gets found again.

    Goods land on a shelf in one action at the receiving desk, which is right —
    whoever opened the sack is standing at the shelf with it. The cost of that
    is that the cell is typed once, and if it was typed wrong then the ledger
    and the room disagree with nobody to notice. There used to be a putaway
    queue that could have caught it; there is this instead, and it does more:
    a model that ended up split across two cells can be brought together, and
    a shelf can be tidied without a stocktake pretending the count was wrong.

    Both legs are named. ``QABUL`` to a cell is still a putaway — the kind says
    what sort of journey it was — and cell to cell is a move.

    Answers with the destination, not with a message: the person who just put
    four pairs in A-02-03 is about to want to know what is in A-02-03, and
    being shown it is how a mistyped code is caught in the second it was made.
    """
    done = idem.replay(session, user, idempotency_key, "move", payload)
    if done is not None:
        return s.LocationDetailOut(**done)

    variant = _variant(session, payload.variant_id)
    frm = _place(session, payload.from_code)
    cell = _place(session, payload.to_code)
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("putaway_needs_a_cell"))
    if frm.id == cell.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("move_nowhere"))

    kind = (
        StockMovementKind.PUTAWAY
        if frm.kind is LocationKind.RECEIVING
        else StockMovementKind.MOVE
    )
    try:
        st.move(
            session,
            variant=variant,
            qty=payload.qty,
            kind=kind,
            frm=frm,
            to=cell,
            actor=user,
            reason=f"{frm.code} → {cell.code}",
        )
    except st.StockError as error:
        raise st.refusal(error) from None

    out = s.LocationDetailOut(
        **_location_out(cell, _fill(session)).model_dump(),
        contents=_contents(session, cell),
    )
    idem.keep(session, user, idempotency_key, "move", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "move")
    return s.LocationDetailOut(**replayed) if replayed else out


@router.post(
    "/move-cell",
    response_model=s.LocationDetailOut,
    summary="Carry everything in one cell over to another, in one action",
)
def move_cell(
    payload: s.MoveCellIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.LocationDetailOut:
    """Tidying a shelf, as one request rather than one per size.

    A cell holds one model in four sizes, and moving it with ``/move`` was
    four requests: four keys, four chances to be interrupted, and a model
    left in two cells if anything went wrong in the middle — which is the
    exact mess the move existed to clear up. One transaction, so a
    half-moved cell is not a state this door can produce.

    ``/move`` stays as it is and is not deprecated. A partial move of one
    size — three of the eight 42s to the front of the shop — is a real thing
    somebody does, and it needs a quantity in the request.

    **This one takes no quantities.** What moves is what is standing there,
    read inside the transaction doing the moving. A list of lines with counts
    on them is a snapshot the screen took some seconds ago, and a picker who
    took two out of the cell in between turns the whole batch into a refusal
    over goods nobody is arguing about. ``variant_ids`` narrows it to some of
    what is there; empty means all of it.

    Answers with the destination, like ``/move``, because the person who just
    carried a shelf across the room is about to want to see it.
    """
    done = idem.replay(session, user, idempotency_key, "move.cell", payload)
    if done is not None:
        return s.LocationDetailOut(**done)

    frm = _place(session, payload.from_code)
    cell = _place(session, payload.to_code)
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("putaway_needs_a_cell"))
    if frm.id == cell.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("move_nowhere"))

    standing = session.exec(
        select(StockPlacement).where(
            StockPlacement.location_id == frm.id, StockPlacement.qty > 0
        )
    ).all()
    if payload.variant_ids:
        wanted = set(payload.variant_ids)
        standing = [row for row in standing if row.variant_id in wanted]
    if not standing:
        # A cell with nothing in it is almost always a mistyped code, and
        # answering "done" would leave somebody looking at the wrong shelf
        # wondering why it is empty.
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("cell_is_empty", code=frm.code)
        )

    kind = (
        StockMovementKind.PUTAWAY
        if frm.kind is LocationKind.RECEIVING
        else StockMovementKind.MOVE
    )
    touched: set[int] = set()
    for row in standing:
        variant = _variant(session, row.variant_id)
        try:
            st.move(
                session,
                variant=variant,
                qty=row.qty,
                kind=kind,
                frm=frm,
                to=cell,
                actor=user,
                reason=f"{frm.code} → {cell.code}",
            )
        except st.StockError as error:
            raise st.refusal(error) from None
        touched.add(variant.product_id)

    # What a card advertises can change when goods move: the damaged corner
    # and the uninspected returns are in the building but not for sale, so a
    # shelf-ward move out of either puts a card back in the shop. ``/move``
    # does not do this and should; it is left alone here because its shape
    # was not mine to change.
    for product_id in sorted(touched):
        pr.refresh(session, product_id)

    out = s.LocationDetailOut(
        **_location_out(cell, _fill(session)).model_dump(),
        contents=_contents(session, cell),
    )
    idem.keep(session, user, idempotency_key, "move.cell", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "move.cell")
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

    **Not a retired cell.** It holds nothing — it could not have been retired
    otherwise — so there is nothing to count, and the one thing a count can do
    that nothing else can is book in a surplus: a line for something that
    turned up. That would put goods into a place that is off the map, which is
    the one outcome retiring a cell is not allowed to produce. Refused here
    rather than at the submit, because the person has walked to the shelf by
    then.
    """
    cell = _place(session, payload.code)
    if not cell.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("cell_retired_count", code=cell.code),
        )
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

    # Silence is not agreement. The rule was written down and not enforced: a
    # variant the system believes is in this cell and that nobody answered for
    # is a line nobody counted, and skipping it quietly leaves the old figure
    # standing with a stocktake's signature on it. The whole point of counting
    # is to find the cell that disagrees, so an unanswered line is refused
    # rather than assumed right.
    answered = {line.variant_id for line in payload.lines}
    missing = [row for variant_id, row in lines.items() if variant_id not in answered]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            i18n.label(
                "count_needs_every_line",
                labels=", ".join(
                    sorted(pr.label(session.get(ProductVariant, row.variant_id)) or "—"
                           for row in missing)
                ),
            ),
        )

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
        free=st.free_room(place, units),
        # Uncapped. Capped at a hundred, a cell holding sixty-five of a
        # stated sixty read exactly like one holding sixty, and an over-full
        # cell — the one thing this figure is on the screen to show — was
        # invisible. The bar on the map clamps its own width, so 130 draws
        # full and red where it already drew full and red at 100.
        fill_percent=round(units / place.capacity * 100) if place.capacity else 0,
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

    Live cells only, like ``_cells_holding`` beside it. A retired cell cannot
    be holding anything today, so the filter changes no answer this year; it
    is here because this is a *suggestion typed into a form*, and the one way
    it could ever be wrong is by offering a cell that the door it feeds would
    then refuse.
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
            col(Location.is_active).is_(True),
        )
    ).all()
    if not rows:
        return ""
    best = sorted(rows, key=lambda pair: loc.walk_order(pair[1]))[0]
    return best[1].code


def _cells_holding(session: SessionDep, product_id: int) -> set[int]:
    """The ids of every cell holding any variant of one card.

    Ids and not codes, and a set and not a list: the plan asks this of every
    cell in the room while it sorts them, and it asks by id because that is
    what the units are keyed by. One query for the whole card — a model in
    four colours and five sizes is twenty variants, and twenty queries to
    answer "which cells is this in" is the shape that made the map slow.
    """
    siblings = session.exec(
        select(ProductVariant.id).where(ProductVariant.product_id == product_id)
    ).all()
    rows = session.exec(
        select(StockPlacement.location_id)
        .join(Location, col(Location.id) == col(StockPlacement.location_id))
        .where(
            col(StockPlacement.variant_id).in_(list(siblings) or [-1]),
            StockPlacement.qty > 0,
            Location.kind == LocationKind.BIN,
            col(Location.is_active).is_(True),
        )
    ).all()
    return {int(location_id) for location_id in rows}


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
