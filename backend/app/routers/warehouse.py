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

import re
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
from app.deps import (
    AdminUser,
    CatalogReader,
    SessionDep,
    StockViewer,
    WarehouseUser,
)
from app.models import (
    Brand,
    Location,
    LocationKind,
    Product,
    ProductSpec,
    ProductStatus,
    ProductVariant,
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

# What a card of a kind nobody has described yet gets offered. Four rows that
# fit almost anything off a market stall, and the seller deletes what does not
# apply — which is a faster thing to do than thinking of the words.
STARTER_SPECS: tuple[str, ...] = (
    "Mato",
    "Ishlab chiqarilgan",
    "O'lcham jadvali",
    "Parvarish",
)


def _next_code(session: SessionDep, model, prefix: str) -> str:
    """The next code in a series, ours rather than anybody else's."""
    used = session.exec(select(func.count()).select_from(model)).one()
    return f"{prefix}-{int(used) + 1:06d}"


# --------------------------------------------------------------------------- a pile


@router.get(
    "/vocab",
    response_model=s.VocabOut,
    summary="The receiving desk's chips — learned, not configured",
)
def vocab(user: CatalogReader, session: SessionDep) -> s.VocabOut:
    """What has come through the door before, most-used first.

    Nobody sets up a list of goods before they have received any, and a market
    brings whatever it brings — so there is no vocabulary screen and nothing to
    maintain. The chips are the answer to "what have we called things", which
    means the list is short and right on day thirty and empty on day one, when
    typing is the only thing that could have worked anyway.
    """
    kinds = _one_spelling(
        session.exec(
            select(Product.kind, func.count())
            .where(col(Product.kind) != "")
            .group_by(col(Product.kind))
        ).all()
    )
    brands = _one_spelling(
        session.exec(
            select(Brand.name, func.count())
            .join(Product, col(Product.brand_id) == col(Brand.id))
            .group_by(col(Brand.name))
        ).all()
    )
    colours = _one_spelling(
        session.exec(
            select(ProductVariant.colour, func.count())
            .where(col(ProductVariant.colour) != "")
            .group_by(col(ProductVariant.colour))
        ).all()
    )

    # Sizes by kind: trainers were last received in 40-45 and shirts in S-XXL,
    # and offering the right row is the difference between three taps and
    # twelve.
    sizes: dict[str, list[str]] = {}
    for kind, size in session.exec(
        select(Product.kind, ProductVariant.size)
        .join(ProductVariant, col(ProductVariant.product_id) == col(Product.id))
        .where(col(Product.kind) != "", col(ProductVariant.size) != "")
        .distinct()
    ).all():
        # Keyed by the tidied kind, because that is the spelling the chips
        # carry and the form looks the sizes up by whatever it was given.
        row = sizes.setdefault(pr.tidy_label(kind), [])
        if size not in row:
            row.append(size)
    for row in sizes.values():
        row.sort(key=pr.size_order)

    # The specification rows, by kind. A starter set until a kind has been
    # written once, because the first card of anything would otherwise face an
    # empty table and nobody types one of those.
    spec_keys: dict[str, list[str]] = {}
    for kind, key in session.exec(
        select(Product.kind, ProductSpec.key)
        .join(ProductSpec, col(ProductSpec.product_id) == col(Product.id))
        .where(col(Product.kind) != "", col(ProductSpec.key) != "")
        .order_by(col(ProductSpec.sort))
    ).all():
        row = spec_keys.setdefault(pr.tidy_label(kind), [])
        if key not in row:
            row.append(key)
    for kind in kinds:
        spec_keys.setdefault(kind, list(STARTER_SPECS))

    return s.VocabOut(
        kinds=kinds,
        brands=brands,
        colours=colours,
        sizes=sizes,
        spec_keys=spec_keys,
    )


@router.post(
    "/piles",
    response_model=s.PileOut,
    status_code=status.HTTP_201_CREATED,
    summary="A pile off the van — booked in and shelved in one action",
)
def book_in_pile(
    payload: s.PileIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.PileOut:
    """Receipt and putaway together, because the person is holding the goods.

    A sack from the market is usually one thing — only black trainers, only
    white shirts — and whoever opened it is standing at the shelf with it. The
    two-stage flow below made them walk the room twice: once to tip the sack
    out and once to carry what they had already counted. So this books the
    goods in *and* shelves them, in one submit, with the cell typed on the same
    form.

    ``location_code`` empty is not an error. It means the goods are going no
    further than the receiving area for now, and the putaway queue will offer
    them to whoever has time — the physical work never waits for the
    paperwork, and QABUL is a place rather than a state of not being anywhere.

    The card this writes is a **stub**: a name, a colour, sizes and counts. It
    has no category, no selling price and no catalogue photograph, so it stays
    in ``draft`` and the apps cannot see it. Somebody fills those in at a desk
    afterwards, in the light, which is the only place that work was ever going
    to get done properly.
    """
    done = idem.replay(session, user, idempotency_key, "pile", payload)
    if done is not None:
        return s.PileOut(**done)

    product = _pile_card(session, user, payload)
    colour = pr.tidy_label(payload.colour)

    # A card that already has colours cannot take a colourless pile. Without
    # this, an empty colour writes a cell beside the ones that exist and puts
    # the count on a variant no picker will ever be sent to — the goods would
    # be on the shelf under a name nobody looks for. Guarded here and not only
    # on the form, because the form is not the only caller there will be.
    if payload.product_id is not None and not colour:
        known = [one for one in pr.colours(session, product.id) if one]
        if known:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                i18n.label("pile_needs_a_colour", colours=", ".join(known)),
            )

    cells = pr.ensure_cells(
        session,
        product,
        colour=colour,
        colour_hex=payload.colour_hex,
        sizes=[line.size.strip() for line in payload.sizes],
        price=product.price,
    )
    where = _pile_cell(session, payload.location_code)

    run = Supply(
        code=_next_code(session, Supply, "SUP"),
        place=payload.place.strip(),
        transport_cost=payload.transport_cost,
        buyer_id=user.id,
        status=SupplyStatus.RECEIVED,
        received_at=utcnow(),
        received_by_id=user.id,
        note=product.title,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    quantity = 0
    for line, variant in zip(payload.sizes, cells, strict=True):
        session.add(
            SupplyLine(
                supply_id=run.id,
                variant_id=variant.id,
                quantity=line.quantity,
                unit_cost=payload.unit_cost,
            )
        )
        # One movement, from the outside world straight to where the goods
        # actually are. Not two — a receipt into QABUL followed by a putaway
        # out of it would put a leg in the ledger for a journey nobody made.
        st.move(
            session,
            variant=variant,
            qty=line.quantity,
            kind=StockMovementKind.RECEIPT,
            frm=None,
            to=where,
            actor=user,
            reason=f"{run.code} · {where.code}",
            supply_id=run.id,
        )
        quantity += line.quantity

    # The identification photograph belongs to the card, and the first one
    # wins: a second pile of the same goods should not quietly replace the
    # picture somebody is recognising them by.
    if payload.snapshot_url and not product.snapshot_url:
        product.snapshot_url = payload.snapshot_url
        session.add(product)

    audit.record(
        session,
        actor=user,
        action="pile.receive",
        entity="product",
        entity_id=product.id,
        field="location",
        old=None,
        new=where.code,
        note=f"{run.code} · {quantity} dona · {product.title}",
    )
    session.commit()
    pr.refresh(session, product.id)
    session.commit()
    session.refresh(product)

    out = s.PileOut(
        product=sv.admin_product_out(session, product),
        run_id=run.id,
        run_code=run.code,
        location_code=where.code,
        quantity=quantity,
        total_cost=quantity * payload.unit_cost + run.transport_cost,
        labels=[
            s.ProductLabelOut(
                variant_id=variant.id,
                product_title=product.title,
                variant_label=_label(variant),
                sku=variant.sku,
                barcode=variant.barcode,
                price=variant.price,
            )
            for variant in cells
        ],
    )
    idem.keep(session, user, idempotency_key, "pile", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "pile")
    return s.PileOut(**replayed) if replayed else out


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
    "/supplies/{supply_id}/sorted",
    response_model=s.SupplyOut,
    summary="This sack has been dealt with — its goods went in as piles",
)
def sack_sorted(
    supply_id: int, user: WarehouseUser, session: SessionDep
) -> s.SupplyOut:
    """Closes the reminder, not a receipt.

    A ``draft`` supply is two words for one thing: goods are standing in the
    building and nobody knows what they are. Its value is entirely the age on
    the dashboard. When somebody finally tips it out, what comes out is piles —
    one card each, one receipt each, booked through ``POST /piles`` — and there
    is no arrangement of lines on *this* row that would describe that, because
    a sack is not one pile.

    So this row is dismissed rather than filled in. Not ``cancel``: cancelling
    says the goods were never booked, and these were.
    """
    run = _draft(session, supply_id)
    run.status = SupplyStatus.RECEIVED
    run.received_at = utcnow()
    run.received_by_id = user.id
    run.note = i18n.label("sack_sorted_note")
    session.add(run)
    audit.record(
        session,
        actor=user,
        action="supply.sorted",
        entity="supply",
        entity_id=run.id,
        field="status",
        old=SupplyStatus.DRAFT,
        new=SupplyStatus.RECEIVED,
        note=run.note,
    )
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
    "/stock/empty",
    response_model=s.EmptiedOut,
    summary="Take everything off a cell, or out of the whole room",
)
def empty_room(
    payload: s.EmptyRoomIn, user: AdminUser, session: SessionDep
) -> s.EmptiedOut:
    """The one operation here that makes stock disappear rather than move.

    Everything else in this file is a journey: goods arrive, cross the room,
    go out in a courier's bag. This writes off what the shop still believes it
    has — for a room being cleared to start again, or a cell whose contents
    turned out not to exist.

    **Still a movement per line.** It would be quicker to delete the
    placements, and the ledger would then disagree with the shelf for ever
    with nothing to explain it. So every line leaves the building the way any
    other line does — ``kind=write_off``, from where it was, to nowhere — the
    invariant that a placement equals the sum of its movements survives, and
    the reason is on every row.
    """
    if payload.code.strip():
        cells = [_pile_cell(session, payload.code)]
    else:
        cells = [
            row
            for row in session.exec(select(Location)).all()
            if row.kind is not LocationKind.COURIER
        ]

    reason = payload.reason.strip()
    moved = units = touched = 0
    products: set[int] = set()
    for cell in cells:
        placements = session.exec(
            select(StockPlacement).where(StockPlacement.location_id == cell.id)
        ).all()
        if not placements:
            continue
        touched += 1
        for row in placements:
            # Read before the move. ``st.move`` decrements this very row, so
            # counting after it counted nought every time — the answer said
            # "one line moved, no units" and the caller had no way to tell that
            # from a cell that was already empty.
            qty = row.qty
            variant = _variant(session, row.variant_id)
            st.move(
                session,
                variant=variant,
                qty=qty,
                kind=StockMovementKind.WRITE_OFF,
                frm=cell,
                to=None,
                actor=user,
                reason=reason,
            )
            moved += 1
            units += qty
            products.add(variant.product_id)

    audit.record(
        session,
        actor=user,
        action="stock.empty",
        entity="location",
        entity_id=cells[0].id if len(cells) == 1 else None,
        field="qty",
        old=units,
        new=0,
        note=f"{payload.code.strip() or 'hamma joy'} · {reason}",
    )
    session.commit()
    for product_id in sorted(products):
        pr.refresh(session, product_id)
    session.commit()
    return s.EmptiedOut(moved=moved, units=units, cells=touched)


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


def _one_spelling(rows: list) -> list[str]:
    """Most-used first, and one chip per thing however it was typed.

    Writes are tidied now, but the rows written before that are still there —
    and a `nike` chip beside a `Nike` chip makes somebody choose between two
    right answers. Grouped by spelling, and the spelling most people used wins.
    """
    tally: dict[str, int] = {}
    for value, count in rows:
        # Tidied on the way out as well as on the way in. Writes are tidy now,
        # but the rows written before that are still there, and a `nike` chip
        # is a chip somebody taps — which would write `nike` again. Tapping the
        # tidy one sends `Nike`, and the brand lookup is case-insensitive, so
        # it lands on the row that already exists.
        label = pr.tidy_label(value)
        if label:
            tally[label] = tally.get(label, 0) + int(count)
    return sorted(tally, key=lambda label: -tally[label])[:40]


def _label(variant: ProductVariant) -> str:
    return " / ".join(part for part in (variant.colour, variant.size) if part)


def _brand_named(session: SessionDep, name: str) -> Brand:
    """The brand by the name somebody typed, made if it is new.

    Two black trainers of different makes are two cards, so the make is part of
    the goods' identity and not a detail — which means the receiving desk has
    to be able to name one that has never been seen before, without leaving the
    form. "On Cloud" is typed once and is a chip from then on.
    """
    wanted = pr.tidy_label(name)
    found = session.exec(
        select(Brand).where(func.lower(col(Brand.name)) == wanted.lower())
    ).first()
    if found is not None:
        # And tidied in place. A row written as `nike` before the tidying
        # existed goes on lending its spelling to every card titled from it,
        # so the chip reads `Nike` and the card reads `nike`. One row, one
        # write, and the catalogue agrees with itself from here on.
        if found.name != wanted:
            found.name = wanted
            session.add(found)
            session.commit()
            session.refresh(found)
        return found

    stem = re.sub(r"[^a-z0-9]+", "-", wanted.lower()).strip("-") or "brend"
    slug = stem
    n = 2
    while session.exec(select(Brand).where(Brand.slug == slug)).first() is not None:
        slug = f"{stem}-{n}"
        n += 1
    row = Brand(slug=slug, name=wanted)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _pile_cell(session: SessionDep, code: str) -> Location:
    """Where the pile is going, which is always a cell.

    A typed cell code is checked against the cells that exist rather than
    trusted, because there is no scanner yet and ``A-03-11`` is one keystroke
    away from ``A-03-01``. A code for a cell that is not there is refused; a
    code for the wrong *cell* is caught by the form showing what is in it.
    """
    wanted = code.strip().upper()
    cell = loc.by_code(session, wanted)
    if cell is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("no_such_cell", code=wanted)
        )
    if cell.kind is not LocationKind.BIN:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("putaway_needs_a_cell")
        )
    return cell


def _pile_card(session: SessionDep, user: User, payload: s.PileIn) -> Product:
    """The card this pile goes on: one that exists, or a stub written now.

    Written here rather than through the catalogue's own door because what the
    desk knows is not what that door asks for. It has a name, a colour and
    sizes; it has no category, no price and no catalogue picture, and requiring
    any of them is what stopped the goods reaching the shelf.
    """
    if payload.product_id is not None:
        product = session.get(Product, payload.product_id)
        if product is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, i18n.label("product_not_found")
            )
        return product

    kind = pr.tidy_label(payload.kind)
    brand = _brand_named(session, payload.brand) if payload.brand.strip() else None
    title = payload.title.strip() or " · ".join(
        part
        for part in (kind, brand.name if brand else "", pr.tidy_label(payload.colour))
        if part
    )
    if not title:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("pile_needs_a_name")
        )

    product = Product(
        sku=pr.next_sku(session),
        title=title,
        kind=kind,
        brand_id=brand.id if brand else None,
        snapshot_url=payload.snapshot_url,
        # Nothing yet: the shop cannot show this and is not meant to.
        category_id=None,
        price=0,
        in_stock=False,
        status=ProductStatus.DRAFT,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    audit.record(
        session,
        actor=user,
        action="product.create",
        entity="product",
        entity_id=product.id,
        field="status",
        old=None,
        new=ProductStatus.DRAFT,
        note=f"{product.sku} · {product.title}",
    )
    session.commit()
    session.refresh(product)
    return product


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
