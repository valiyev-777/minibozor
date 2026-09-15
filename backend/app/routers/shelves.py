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
by somebody who has looked in it. It **removes**: the row is deleted when
nothing in the ledger names the cell, which is every cell built by a typo and
never used, and kept with ``is_active`` off when a movement or a stocktake
does — because a deleted row there would leave the ledger pointing at a place
that does not exist. Both leave the room, and neither is drawn: a rack
carrying a column of crossed-out tiles is a shelf nobody can point at. Asking
the second door for that column again is the way back, for both.

And the labels, because we generate the barcodes: market goods arrive
unlabelled, so the only code they will ever carry is the one we print — one
58 mm sticker per unit. The scanner reads those codes back through one door,
``GET /warehouse/scan``, which every warehouse screen shares.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlmodel import Session, col, func, or_, select

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
    PickLine,
    Product,
    ProductVariant,
    StockCount,
    StockCountLine,
    StockMovement,
    StockMovementKind,
    StockPlacement,
    Supply,
    SupplyLine,
    SupplyStatus,
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
    needle = q.strip()
    exact = _exact_variants(session, needle)

    if exact:
        variants = exact
    else:
        lowered = needle.lower()
        products = session.exec(
            select(Product.id).where(func.lower(Product.title).like(f"%{lowered}%"))
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
        out = _where_is_out(session, variant)
        # A variant with nothing on any shelf would light no cell up, which
        # on this screen reads as a broken search rather than as an answer.
        # ``/warehouse/scan`` is the door that answers for those.
        if not out.places:
            continue
        found.append(out)
    return found


@router.get(
    "/scan",
    response_model=s.ScanOut,
    summary="One answer for whatever was scanned, on every warehouse screen",
)
def scan(
    user: StockViewer,
    session: SessionDep,
    code: str = Query(min_length=1, description="Whatever the gun or the camera read"),
) -> s.ScanOut:
    """A goods label, a cell label, or noise — the screen decides what to do.

    A scanner gun and a phone camera both end at a string, and every warehouse
    screen wants the same classification of it: `/qabul` fills in the card or
    the destination, `/ombor` jumps the map, `/terish` confirms or refuses a
    line, `/sanash` counts one up. So one door answers all of them.

    Exact matches only. A scan is a code, not a search: the LIKE-on-title leg
    of ``where-is`` would turn a mis-read into a confident wrong card.

    Two things ``where-is`` will not do, on purpose, that this must:

    * **answer for a cell code** — the sticker on the shelf edge is scanned as
      often as the one on the shoe, and the answer carries what is standing in
      the cell so the screen has something to show;
    * **answer for a variant with no stock** — the receiving desk scans a label
      already stuck on one of the new shoes precisely *before* they are booked
      in, so an empty ``places`` is an answer and not a miss.

    A string that names nothing comes back as ``kind="none"`` with 200 rather
    than a 404: a mis-scan is a normal minute of warehouse work, and the screen
    shows the refusal loudly and keeps listening.
    """
    needle = code.strip()

    hit = _exact_variants(session, needle)
    if hit:
        # Barcode and SKU are unique per variant, so an exact hit is one row.
        variant = hit[0]
        return s.ScanOut(
            kind="variant",
            code=needle,
            variant=s.ScanVariantOut(
                **_where_is_out(session, variant).model_dump(),
                colour=variant.colour,
                size=variant.size,
            ),
        )

    place = loc.by_code(session, needle)
    if place is not None:
        # Retired cells included: the sticker outlives the row's is_active
        # flag, and "that cell was taken out of the room" is an answer the
        # flag on the payload lets the screen give.
        return s.ScanOut(
            kind="cell",
            code=place.code,
            cell=s.LocationDetailOut(
                **_location_out(place, _fill(session)).model_dump(),
                contents=_contents(session, place),
            ),
        )

    return s.ScanOut(kind="none", code=needle)


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

    * **every cell that already holds this model**, in walk order, each filled
      to its free room — one model per cell is the discipline and the goods
      want to be together;
    * then **one** cell for whatever is left: the emptiest, nearest those in
      walk order. Emptiest means holding least, which is how a cell with
      nothing in it always comes before one with somebody else's shirts in
      it; nearest keeps the pile in one aisle instead of at both ends of the
      room.

    **A cell holding this model is listed even when it is full.** It used to
    be dropped — its free room was nought, so the line the loop would have
    written was a line for nothing — and a person carrying ten more pairs of
    a model that already fills ``B-01-02`` to 307% was sent to ``B-01-01``
    and told it was empty, with nothing anywhere on the screen saying where
    the other thirty pairs were. Where the pile already is is the first thing
    this answer owes them, and a full cell is the case where they most need
    to be told: they are about to split one model across two aisles, and the
    plan should be what says so rather than what hides it. Such a line
    carries ``quantity`` nought and its real fullness.

    **One suggestion for "somewhere else", not a list of them.** The door this
    feeds — ``POST /receipts/{id}/shelve`` — takes exactly one cell code, so a
    plan naming four cells is a plan three quarters of which nobody can act
    on. The spill is one cell and it takes the whole remainder, honestly
    over-full if that is what it comes to.

    A cell with no stated capacity takes whatever is left rather than being
    treated as holding nothing: nobody has measured it, and refusing to use
    it would leave the plan short of a cell that is plainly there.

    **If the room has no space the plan says so and over-fills anyway.** The
    goods are standing on the floor. A plan that stops at seventy of eighty
    does not say where the other ten went, and somebody puts them somewhere
    without telling anyone; an honest 130% is a cell people walk past and
    tidy.

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

    def line(cell: Location, take: int) -> s.PutawayPlanLineOut:
        held = units.get(cell.id, 0)
        return s.PutawayPlanLineOut(
            code=cell.code,
            quantity=take,
            free=st.free_room(cell, held),
            units=held,
            holds_this_model=cell.id in holders,
        )

    left = quantity
    lines: list[s.PutawayPlanLineOut] = []

    # Where the model already is — all of it, room or no room. A cell at 307%
    # takes nought more and is still the most useful line on the screen.
    for cell in own:
        free = st.free_room(cell, units.get(cell.id, 0))
        take = left if free is None else min(left, free)
        take = max(0, take)
        lines.append(line(cell, take))
        left -= take

    # And one place for the rest. The first cell with any room in it, in the
    # order the sort above put them — emptiest, then nearest the model's own
    # cells — or, when every cell in the building is full, the emptiest of
    # them anyway: the goods are standing on the floor and the plan has to
    # name somewhere.
    spill = next(
        (cell for cell in rest if st.free_room(cell, units.get(cell.id, 0)) != 0),
        rest[0] if rest else None,
    )
    if spill is not None and (left > 0 or not lines):
        lines.append(line(spill, max(0, left)))
        left = 0

    # Over-full is a property of the last line rather than of a remainder the
    # loop gave up on: the spill takes everything, so what is left to say is
    # how much more than it holds it was asked to take.
    over = ""
    last = lines[-1] if lines else None
    if last is not None and last.free is not None and last.quantity > last.free:
        over = i18n.label(
            "putaway_plan_over_capacity",
            code=last.code,
            over=last.quantity - last.free,
        )

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
    a number box should be able to do. Taking one out is ``DELETE
    /warehouse/cells/{code}``, one cell at a time, by somebody who has looked
    in it.

    **A cell that was taken out and whose row was kept is woken by this**, and
    this is the only thing that wakes it. Removing a cell deletes its row when
    nothing in the ledger names it, and keeps the row invisibly when something
    does; either way the room stops having a cell there. So asking for the
    column again means the same thing in both cases — *this rack is five
    columns wide* — and it has to do the same thing in both cases, or a rack
    would refuse to grow back into a position the shop cannot see is taken.
    A woken cell counts as written, because from the room's side one appeared.

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

    # The rack as the shop has it, which is not every row carrying its letter:
    # a cell taken out of the room may have kept its row for the ledger's
    # sake, and it is neither shelving the shop has nor a shape to copy a new
    # cell's capacity from.
    live = [place for place in standing if place.is_active]
    capacity = (
        payload.capacity
        if payload.capacity is not None
        else _house_capacity(live or standing)
    )
    here = {place.code: place for place in standing}

    made = 0
    for column_no in range(1, payload.columns + 1):
        for row_no in range(1, payload.rows + 1):
            code = loc.cell_code(wanted, column_no, row_no)
            known = here.get(code)
            if known is not None:
                # The kept row of a cell that was taken out. Asking for this
                # column again is what puts it back, and it comes back as
                # itself — same code, same capacity, same history.
                if not known.is_active:
                    known.is_active = True
                    session.add(known)
                    made += 1
                continue
            # Against the whole building and not only against this rack: a
            # code is unique everywhere.
            if loc.by_code(session, code) is not None:
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
            old=len(live),
            new=len(live) + made,
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


@router.delete(
    "/cells/{code}",
    response_model=s.CellRemoved,
    summary="Take a cell out of the room, for good",
)
def remove_cell(
    code: str,
    # The office's, like building a rack and like growing one. Taking a cell
    # out is the shape of the building changing, and not a wider guard:
    # everybody else in here moves goods between places that exist, and the
    # warehouse hand who finds a cell inconvenient at nine in the evening is
    # exactly the person this should not be a way out for.
    user: AdminUser,
    session: SessionDep,
    reason: str = Query("", max_length=200, description="Why, for the audit trail"),
) -> s.CellRemoved:
    """A rack unbolted back to four columns is four columns.

    This was ``POST /cells/{code}/active`` with a boolean, and the boolean was
    the problem. Retiring flipped a flag: the row stayed, the code stayed, and
    the map drew the dead cell struck through in the grid with a way back on
    it, so a rack built 6×4 by a typo showed two columns of crossed-out tiles
    for ever. Correct about the ledger, and a lie about the room — there is no
    fifth column standing in the shop for anybody to point at.

    **So the row goes, when it can go.** A cell nothing has ever written down
    is deleted outright, and the shop is left exactly as it would be had the
    typo never happened. Its empty placement rows go with it: a placement of
    nought is the absence of stock, which is also what a cell that no longer
    exists holds.

    **And it is kept, invisibly, when it cannot.** A movement from March, a
    stocktake, a picking line — anything that names this cell makes the row
    load-bearing, and deleting it would leave the ledger pointing at a place
    that does not exist. That cell keeps its row with ``is_active`` off: out
    of the map, out of the label sheet, out of the putaway plan, refused as a
    destination, and gone from every screen exactly like the deleted one. The
    answer says which of the two happened; the caller cannot ask for the
    ledger to be broken and does not have to know which case it is in.

    **Refused while it is holding anything, and that is the only thing asked
    of the caller.** Goods in a place nobody can see are goods nobody can
    find. The sentence names the two ways out — carry them somewhere with
    ``POST /warehouse/move`` or ``POST /warehouse/move-cell``, or write them
    off with ``POST /warehouse/stock/empty`` — because a refusal a warehouse
    cannot act on is a refusal somebody works around.

    **Cells only.** ``QABUL``, ``YIGIM``, ``BRAK`` and ``QAYTGAN`` are not
    shelves, they are places with a job: being in ``QABUL`` *is* the unplaced
    state, ``locations.staging`` raises rather than conjuring one up, and the
    seed writes them by name — so a removed ``QABUL`` is a receiving desk the
    next seed run silently puts back while every count written into it was
    invisible to the map in between. A courier's bag is the same story from
    the other end: it is made on demand and the map draws it only while it
    holds something. Neither is refused for safety's sake; there is simply no
    such decision to take.

    **The way back is the rack's shape, not a button on a ghost.** There is no
    ghost any more, so ``POST /warehouse/racks/{rack}/cells`` asking for the
    column again is what brings it back — it builds the code afresh where the
    row was deleted, and wakes the kept one where it was not. One door for
    "this rack is five columns wide", whatever the room did last week.
    """
    cell = _place(session, code)
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("cell_retire_needs_a_cell", code=cell.code),
        )

    held = st.units_in(session, cell.id)
    if held:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("cell_retire_not_empty", code=cell.code, units=held),
        )

    # Read before anything is written: after the delete the object is detached
    # and its id is a number that no longer means anything.
    cell_id = cell.id
    cell_code = cell.code
    kept = _ledger_names(session, cell_id)

    audit.record(
        session,
        actor=user,
        action="location.removed",
        entity="location",
        entity_id=cell_id,
        field="code",
        old=cell_code,
        # The row is going, so there is nothing to point at afterwards. The
        # old value is the whole record, which is why it is the code and not
        # the flag: a year later "A-05-03 was removed" is readable and
        # "is_active: true → false" is not.
        new=None,
        note=reason or cell_code,
    )

    if kept:
        cell.is_active = False
        session.add(cell)
    else:
        for row in session.exec(
            select(StockPlacement).where(StockPlacement.location_id == cell_id)
        ).all():
            session.delete(row)
        session.delete(cell)
    session.commit()

    return s.CellRemoved(
        code=cell_code,
        erased=not kept,
        message=i18n.label(
            "cell_removed_kept" if kept else "cell_removed", code=cell_code
        ),
    )


def _ledger_names(session: Session, cell_id: int) -> bool:
    """Whether anything written down still points at this cell.

    Three tables and not one: a cell can have been counted without ever having
    been moved into, and a picking line names the cell a picker was sent to
    whether or not the goods were still there when they arrived. Any of the
    three makes the row load-bearing.

    Placements are deliberately not among them. A placement is what a cell
    holds *now*, not what it did — the caller has already been refused if that
    is anything at all, so what is left is rows of nought, which say the cell
    holds none of this model. A cell that does not exist holds none of it
    either, so they are deleted with it rather than keeping it alive.
    """
    moves = session.exec(
        select(func.count())
        .select_from(StockMovement)
        .where(
            or_(
                StockMovement.from_location_id == cell_id,
                StockMovement.to_location_id == cell_id,
            )
        )
    ).one()
    if moves:
        return True

    picks = session.exec(
        select(func.count()).select_from(PickLine).where(PickLine.location_id == cell_id)
    ).one()
    if picks:
        return True

    counted = session.exec(
        select(func.count())
        .select_from(StockCount)
        .where(StockCount.location_id == cell_id)
    ).one()
    return bool(counted)


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
    summary="The data behind the labels — one 58 mm page per sticker",
)
def labels(
    user: StockViewer,
    session: SessionDep,
    supply_id: int | None = Query(None, description="Everything one market run brought"),
    variant_id: list[int] | None = Query(None),
    cells: bool = Query(False, description="A full set of cell labels instead"),
) -> s.LabelSheetOut:
    """What to print, how many times, and nothing about how.

    The barcode is drawn in the browser: a barcode is a picture of a string,
    and rendering it client-side means no image to store, no font to install
    on a server, and a reprint that cannot drift from the code on the row.

    A variant's barcode is permanent. When the same goods arrive again the
    label is **reprinted** — this endpoint answers with the code that is on
    the row, never a new one — because a second code for one thing is a shelf
    holding it twice.

    **Every unit gets a sticker**, so a receipt's labels carry ``copies``: the
    line's own quantity, grouped by variant in the order the lines were typed
    — ten 43s then ten 42s, matching the piles on the table. A reprint by
    ``variant_id`` answers one copy each, because its usual reason is a
    printer jam, not a second van.
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

    # Insertion order is the answer's order: a receipt's labels come out
    # grouped by variant exactly as the lines were written down.
    counted: dict[int, int] = {}
    if supply_id is not None:
        # A receipt that was called off has no goods to stick anything to.
        # Printing its sheet anyway is how a sticker ends up on a shoe the
        # ledger says never arrived — and the reprint bench is exactly the
        # screen somebody reaches for after a receipt went wrong, so this is
        # the refusal that has to say which run and why.
        run = session.get(Supply, supply_id)
        if run is not None and run.status is SupplyStatus.CANCELLED:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                i18n.label("receipt_cancelled_no_labels", code=run.code),
            )
        lines = session.exec(
            select(SupplyLine)
            .where(SupplyLine.supply_id == supply_id)
            .order_by(col(SupplyLine.id))
        ).all()
        for line in lines:
            counted[line.variant_id] = counted.get(line.variant_id, 0) + line.quantity
    elif variant_id:
        for wanted in variant_id:
            counted.setdefault(wanted, 1)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("labels_need_a_selection")
        )

    out = []
    for wanted, copies in counted.items():
        # A line of nought would print nothing; sending it would only make
        # the screen divide by it when it numbers stickers n-of-copies.
        if copies <= 0:
            continue
        variant = session.get(ProductVariant, wanted)
        if variant is None:
            continue
        product = session.get(Product, variant.product_id)
        out.append(
            s.ProductLabelOut(
                variant_id=variant.id,
                product_title=product.title if product else "",
                variant_label=sv.variant_label(variant),
                colour=variant.colour,
                size=variant.size,
                sku=variant.sku,
                barcode=variant.barcode,
                price=variant.price or (product.price if product else 0),
                copies=copies,
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


def _exact_variants(session: SessionDep, needle: str) -> list[ProductVariant]:
    """The variants this string is the code of — barcode or SKU, exactly.

    Shared by ``where-is`` and ``scan`` so the two doors can never disagree
    about what a code names. Case-insensitive because a scanner gun is honest
    but a person retyping a smudged label is not.
    """
    lowered = needle.strip().lower()
    return list(
        session.exec(
            select(ProductVariant).where(
                (func.lower(ProductVariant.barcode) == lowered)
                | (func.lower(ProductVariant.sku) == lowered)
            )
        ).all()
    )


def _where_is_out(session: SessionDep, variant: ProductVariant) -> s.WhereIsOut:
    """One variant with its places — possibly none, which the caller judges.

    ``where-is`` drops the placeless ones because its screen lights cells up;
    ``scan`` keeps them because the receiving desk scans goods that are not
    booked in yet. The identity is built once, here, for both.
    """
    product = session.get(Product, variant.product_id)
    return s.WhereIsOut(
        variant_id=variant.id,
        product_id=variant.product_id,
        product_title=product.title if product else "",
        variant_label=sv.variant_label(variant),
        sku=variant.sku,
        barcode=variant.barcode,
        places=[
            s.PlacementOut(location_id=place.id, code=place.code, qty=qty)
            for place, qty in st.placements(session, variant.id)
        ],
    )


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
