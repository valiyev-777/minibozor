"""The warehouse: how goods arrive, get counted, and leave.

Nobody delivers to us. The owner goes to the wholesale market, buys what looks
worth buying and comes back with the goods — mixed, unlabelled,
unphotographed — so there is no declaration to check a receipt against and no
supplier to check it with. Receiving is **two moments**, in the order the
body moves — enter, print, stick, carry, put away:

* **At the bench.** What came and how many: one card, one colour, a
  size→quantity list, the cost while somebody still knows it. ``POST
  /receipts`` books the goods in, writes the supply row, and answers with the
  sheet of stickers — one per unit. The goods now exist and stand in
  ``QABUL``, which is a real, *sellable* place and not a flag: nothing is
  lost while the second question is unanswered.
* **At the shelf.** The one thing nobody could know before they walked: which
  cell. ``POST /receipts/{id}/shelve`` carries the receipt's goods out of the
  receiving area into the cell that was scanned or typed.

The cell is asked **last** because asking for it at the bench is asking
somebody who has not walked anywhere yet where they are going to end up —
they guess, and a guess in the cell field is stock in the wrong place.

Nothing sets a count. Every endpoint writes a *difference*, which is what
makes two people working the same shelf at once safe: the second save adds to
the first rather than erasing it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, brands, i18n
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


# --------------------------------------------------------------------------- receiving


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
    # Archived cards are not vocabulary. A card written by mistake is deleted
    # if nothing has moved through it and archived if something has — and its
    # kind then sat in the chip row for good. A word this shop has finished
    # with is a word the desk should stop offering, which also means the row
    # tidies itself: get rid of the card and the chip goes with it.
    alive = col(Product.status) != ProductStatus.ARCHIVED

    kinds = _one_spelling(
        session.exec(
            select(Product.kind, func.count())
            .where(col(Product.kind) != "", alive)
            .group_by(col(Product.kind))
        ).all()
    )
    brands = _one_spelling(
        session.exec(
            select(Brand.name, func.count())
            .join(Product, col(Product.brand_id) == col(Brand.id))
            .where(alive)
            .group_by(col(Brand.name))
        ).all()
    )
    colours = _one_spelling(
        session.exec(
            select(ProductVariant.colour, func.count())
            .join(Product, col(Product.id) == col(ProductVariant.product_id))
            .where(col(ProductVariant.colour) != "", alive)
            .group_by(col(ProductVariant.colour))
        ).all()
    )

    # Sizes by kind: trainers were last received in 40-45 and shirts in S-XXL,
    # and offering the right row is the difference between three taps and
    # twelve.
    # Some things have no size: a cap, a bag, a wristwatch. The form used to
    # ask for sizes whatever had arrived, and a person holding a sack of caps
    # types *something* into a box that will not go away — which is how a size
    # called "KS" was born. So the desk is also told which kinds have never
    # had one, and asks the right question before it is asked anything.
    sizeless: list[str] = []
    for kind, sized in session.exec(
        select(Product.kind, func.max(func.length(ProductVariant.size)))
        .join(ProductVariant, col(ProductVariant.product_id) == col(Product.id))
        .where(col(Product.kind) != "", alive)
        .group_by(col(Product.kind))
    ).all():
        if not sized:
            tidied = pr.tidy_label(kind)
            if tidied not in sizeless:
                sizeless.append(tidied)

    sizes: dict[str, list[str]] = {}
    for kind, size in session.exec(
        select(Product.kind, ProductVariant.size)
        .join(ProductVariant, col(ProductVariant.product_id) == col(Product.id))
        .where(col(Product.kind) != "", col(ProductVariant.size) != "", alive)
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
        .where(col(Product.kind) != "", col(ProductSpec.key) != "", alive)
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
        sizeless=sizeless,
        spec_keys=spec_keys,
    )


@router.post(
    "/receipts",
    response_model=s.ReceiptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Moment one, at the bench — what came, how many, what it cost",
)
def receive(
    payload: s.ReceiptIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.ReceiptOut:
    """Books the goods in and answers with the stickers to print.

    One call is one receipt: one card, one colour, the sizes in the order
    they were typed — which is the order the stickers print in and the order
    the piles sit on the table. It writes three things at once:

    * the card stub and its variants — permanent SKUs and barcodes, minted
      once and never regenerated;
    * one supply row, already ``received``, with its lines: the market run,
      written *by* the receipt and never edited by hand;
    * one ``receipt`` movement per size, into ``QABUL``.

    **No cell is asked for.** The door that stood here took the cell on the
    same form, and that decision is reversed on purpose: the person at the
    bench has not walked anywhere yet, so a cell typed here is a guess, and a
    guess in the cell field is stock in the wrong place. The goods stand in
    the receiving area — a *sellable* place, so nothing is lost while the
    question waits — until ``POST /receipts/{id}/shelve`` answers it at the
    shelf, usually with one scan of the cell's own label.

    The card this writes is a **stub**: a name, a colour, sizes and counts. It
    has no category, no selling price and no catalogue photograph, so it stays
    in ``draft`` and the apps cannot see it. Somebody fills those in at a desk
    afterwards, in the light, which is the only place that work was ever going
    to get done properly.
    """
    done = idem.replay(session, user, idempotency_key, "receipt", payload)
    if done is not None:
        return s.ReceiptOut(**done)

    desk = loc.staging(session, loc.QABUL)
    product = _receipt_card(session, user, payload)
    colour = pr.tidy_label(payload.colour)

    # A card that already has colours cannot take a colourless receipt.
    # Without this, an empty colour writes a cell beside the ones that exist
    # and puts the count on a variant no picker will ever be sent to — the
    # goods would be on the shelf under a name nobody looks for. Guarded here
    # and not only on the form, because the form is not the only caller there
    # will be.
    if payload.product_id is not None and not colour:
        known = [one for one in pr.colours(session, product.id) if one]
        if known:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                i18n.label("receipt_needs_a_colour", colours=", ".join(known)),
            )

    wanted = [pr.tidy_size(line.size) for line in payload.sizes]

    # A card is one shape: either its goods have sizes or they do not. A cap
    # arrived sizeless, then arrived again as `M` and `XL`, and the card ended
    # up holding both — a grey cap with no size beside a grey cap in M, which
    # nobody can tell apart, on a shelf where they are the same cap. The shop
    # then offered a blank size chip next to a real one. Refused here rather
    # than tidied afterwards: by the time it is on the shelf the counts have
    # already been split between two names for one thing.
    if payload.product_id is not None:
        had = pr.variants(session, product.id)
        if had:
            was_sized = any(row.size for row in had)
            now_sized = any(wanted)
            if was_sized != now_sized:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    i18n.label(
                        "receipt_sized_or_not",
                        card=product.title,
                        shape=i18n.label(
                            "shape_sized" if was_sized else "shape_sizeless"
                        ),
                    ),
                )

    cells = pr.ensure_cells(
        session,
        product,
        colour=colour,
        colour_hex=payload.colour_hex,
        sizes=wanted,
        price=product.price,
    )

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
        # One supply line per size. The line is what came off the van and
        # what it cost; where it ends up is the ledger's business.
        session.add(
            SupplyLine(
                supply_id=run.id,
                variant_id=variant.id,
                quantity=line.quantity,
                unit_cost=payload.unit_cost,
            )
        )
        # One movement per size, from the outside world into the receiving
        # area — the first leg of a journey whose second leg is walked a
        # minute later, at the shelf. The unit cost rides on the receipt so
        # the margin somebody reads afterwards is a fact and not a guess.
        st.move(
            session,
            variant=variant,
            qty=line.quantity,
            kind=StockMovementKind.RECEIPT,
            frm=None,
            to=desk,
            actor=user,
            reason=f"{run.code} · {desk.code}",
            supply_id=run.id,
            unit_cost=payload.unit_cost,
        )
        quantity += line.quantity

    # The identification photograph belongs to the card, and the first one
    # wins: a second receipt of the same goods should not quietly replace the
    # picture somebody is recognising them by.
    if payload.snapshot_url and not product.snapshot_url:
        product.snapshot_url = payload.snapshot_url
        session.add(product)

    audit.record(
        session,
        actor=user,
        action="receipt.receive",
        entity="product",
        entity_id=product.id,
        field="location",
        old=None,
        new=desk.code,
        note=f"{run.code} · {quantity} dona · {product.title}",
    )
    session.commit()
    pr.refresh(session, product.id)
    session.commit()
    session.refresh(product)

    out = s.ReceiptOut(
        product=sv.admin_product_out(session, product),
        run_id=run.id,
        run_code=run.code,
        quantity=quantity,
        total_cost=quantity * payload.unit_cost + run.transport_cost,
        labels=[
            # One line per size, in the order typed, each with its count —
            # everything the sticker sheet needs and nothing it must look up.
            s.ReceiptLabelOut(
                variant_id=variant.id,
                product_title=product.title,
                colour=variant.colour,
                size=variant.size,
                variant_label=pr.label(variant),
                sku=variant.sku,
                barcode=variant.barcode,
                copies=line.quantity,
            )
            for line, variant in zip(payload.sizes, cells, strict=True)
        ],
    )
    idem.keep(session, user, idempotency_key, "receipt", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "receipt")
    return s.ReceiptOut(**replayed) if replayed else out


@router.post(
    "/receipts/{receipt_id}/shelve",
    response_model=s.ReceiptShelvedOut,
    summary="Moment two, at the shelf — the cell, scanned or typed",
)
def shelve_receipt(
    receipt_id: int,
    payload: s.ReceiptShelveIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.ReceiptShelvedOut:
    """Carries one receipt's goods out of QABUL into the cell that was named.

    The cell is checked against the cells that exist rather than trusted —
    ``A-03-11`` is one keystroke from ``A-03-01`` — and a mistyped code is
    refused, not invented. What moves is what of this receipt is still
    standing in the receiving area: a receipt already shelved has nothing
    left to carry and is answered politely rather than refused, because the
    goods are exactly where the person wanted them.

    This is not the old two-stage sorting flow coming back. That one asked a
    second person to sort a sack at a later time; this is the same person,
    one minute later, ten metres away, answering the one thing they could
    not know before they walked.
    """
    stamp = {"receipt_id": receipt_id, **payload.model_dump()}
    done = idem.replay(session, user, idempotency_key, "receipt-shelve", stamp)
    if done is not None:
        return s.ReceiptShelvedOut(**done)

    run = _supply(session, receipt_id)
    cell = _open_cell(session, payload.location_code)
    desk = loc.staging(session, loc.QABUL)

    lines = session.exec(
        select(SupplyLine)
        .where(SupplyLine.supply_id == run.id)
        .order_by(col(SupplyLine.id))
    ).all()

    # What of this receipt is still standing at the desk, per variant, off the
    # ledger: receipted into QABUL less already carried out of it. Capped at
    # what actually stands there now — goods sold straight from the receiving
    # area left through a pick, which names an order rather than this run.
    left = _still_at_the_desk(session, desk.id, run.id)

    moved = 0
    products: set[int] = set()
    carried: set[int] = set()
    for line in lines:
        if line.variant_id in carried:
            continue
        carried.add(line.variant_id)
        step = min(
            left.get(line.variant_id, 0),
            st.at(session, desk.id, line.variant_id),
        )
        if step <= 0:
            continue
        variant = _variant(session, line.variant_id)
        st.move(
            session,
            variant=variant,
            qty=step,
            kind=StockMovementKind.PUTAWAY,
            frm=desk,
            to=cell,
            actor=user,
            reason=f"{run.code} · {cell.code}",
            supply_id=run.id,
        )
        moved += step
        products.add(variant.product_id)

    if moved:
        audit.record(
            session,
            actor=user,
            action="receipt.shelve",
            entity="supply",
            entity_id=run.id,
            field="location",
            old=desk.code,
            new=cell.code,
            note=f"{run.code} · {moved} dona · {cell.code}",
        )

    out = s.ReceiptShelvedOut(
        receipt_id=run.id,
        run_code=run.code,
        location_code=cell.code,
        quantity=moved,
        total_cost=sum(line.line_cost for line in lines) + run.transport_cost,
        message="" if moved else i18n.label("receipt_already_shelved"),
    )
    idem.keep(session, user, idempotency_key, "receipt-shelve", stamp, out)
    replayed = idem.commit(session, user, idempotency_key, "receipt-shelve")
    if replayed:
        return s.ReceiptShelvedOut(**replayed)
    for product_id in sorted(products):
        pr.refresh(session, product_id)
    session.commit()
    return out


@router.post(
    "/receipts/{receipt_id}/cancel",
    response_model=s.ReceiptCancelledOut,
    summary="Unsay a receipt while its goods are still on the receiving floor",
)
def cancel_receipt(
    receipt_id: int,
    payload: s.ReceiptCancelIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.ReceiptCancelledOut:
    """"Typed 20, meant 10" — the way back, while the way back is still open.

    Until this door existed a receipt could not be unsaid. A miscounted pile,
    a colour picked from the wrong chip, a sack booked in twice: all of them
    were stock the shop believed in, and the honest answer to the person at
    the bench was to ring whoever wrote the software. So: one door, open for
    exactly as long as the mistake is still recoverable.

    **Only while the receipt is whole and still in QABUL.** Every line's
    quantity must still be standing in the receiving area, untouched. Two
    things close the door, and the refusal says which:

    * the goods went to a cell — the receipt was shelved, and taking them back
      out is a move or a write-off *at that cell*, which is where somebody has
      to walk anyway;
    * part of the receipt left the receiving area by another door. ``QABUL``
      is a sellable place, so a receipt can be picked for an order or carried
      to the damaged corner before anybody shelves it — and once one of those
      has happened the receipt is no longer a thing that can be said never to
      have happened.

    **The reversal is a move, not a deletion.** One ``receipt_cancel`` per
    variant, out of ``QABUL`` and out of the building, so ``StockPlacement``
    still equals the sum of the movements and the ledger still says what
    happened and when. Deleting the receipt's rows would leave a shop whose
    stock figure is right and whose history has a hole in it — and the hole
    would be exactly where somebody later needs to look.

    Its own movement kind rather than a ``write_off``, because a write-off is
    read downstream as goods the shop lost. A receipt nobody should have
    written is not twenty pairs of shoes gone; it is twenty pairs that were
    never there.

    **The card and its variants stay.** A barcode and an SKU are permanent
    (§6.5) — the stickers may already be stuck to goods on the table, and a
    code that stops resolving is worse than a variant holding nought. A card
    whose only receipt was this one is simply a draft with no stock, which is
    what it was five minutes before the mistake.
    """
    stamp = {"receipt_id": receipt_id, **payload.model_dump()}
    done = idem.replay(session, user, idempotency_key, "receipt-cancel", stamp)
    if done is not None:
        return s.ReceiptCancelledOut(**done)

    run = _supply(session, receipt_id)
    desk = loc.staging(session, loc.QABUL)

    if run.status is SupplyStatus.CANCELLED:
        # Answered politely rather than refused, like a second tap at the
        # shelf: the goods are already not on the books, which is what the
        # caller wanted.
        out = s.ReceiptCancelledOut(
            receipt_id=run.id,
            run_code=run.code,
            quantity=0,
            message=i18n.label("receipt_already_cancelled"),
        )
        idem.keep(session, user, idempotency_key, "receipt-cancel", stamp, out)
        replayed = idem.commit(session, user, idempotency_key, "receipt-cancel")
        return s.ReceiptCancelledOut(**replayed) if replayed else out

    lines = session.exec(
        select(SupplyLine)
        .where(SupplyLine.supply_id == run.id)
        .order_by(col(SupplyLine.id))
    ).all()

    # Per variant rather than per line: a receipt may name one size twice —
    # the same variant on two lines — and one move of the total is one true
    # row where two would be two halves of it.
    booked: dict[int, int] = {}
    for line in lines:
        booked[line.variant_id] = booked.get(line.variant_id, 0) + line.quantity

    # What of this receipt the ledger still shows standing at the desk: in
    # less out, counting only movements that name this run. Short of what was
    # booked means a putaway carried it to a cell.
    left = _still_at_the_desk(session, desk.id, run.id)
    if any(left.get(variant_id, 0) < qty for variant_id, qty in booked.items()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("receipt_cancel_already_shelved"),
        )

    # And what is physically there now, which is a different question: a pick
    # or a damage takes goods out of QABUL without naming the run, so the
    # ledger above can still show them standing while the shelf does not.
    short = sum(
        max(0, qty - st.at(session, desk.id, variant_id))
        for variant_id, qty in booked.items()
    )
    if short:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("receipt_cancel_partly_gone", gone=short),
        )

    reason = payload.reason.strip()
    quantity = 0
    products: set[int] = set()
    for variant_id, qty in booked.items():
        variant = _variant(session, variant_id)
        st.move(
            session,
            variant=variant,
            qty=qty,
            kind=StockMovementKind.RECEIPT_CANCEL,
            frm=desk,
            to=None,
            actor=user,
            reason=f"{run.code} · bekor qilindi{f' · {reason}' if reason else ''}",
            supply_id=run.id,
        )
        quantity += qty
        products.add(variant.product_id)

    was = run.status
    run.status = SupplyStatus.CANCELLED
    session.add(run)

    audit.record(
        session,
        actor=user,
        action="receipt.cancel",
        entity="supply",
        entity_id=run.id,
        field="status",
        old=was,
        new=SupplyStatus.CANCELLED,
        note=f"{run.code} · {quantity} dona · {reason or run.note}",
    )

    out = s.ReceiptCancelledOut(
        receipt_id=run.id,
        run_code=run.code,
        quantity=quantity,
        message=i18n.label("receipt_cancelled", code=run.code, quantity=quantity),
    )
    idem.keep(session, user, idempotency_key, "receipt-cancel", stamp, out)
    replayed = idem.commit(session, user, idempotency_key, "receipt-cancel")
    if replayed:
        return s.ReceiptCancelledOut(**replayed)
    for product_id in sorted(products):
        pr.refresh(session, product_id)
    session.commit()
    return out


@router.get(
    "/receipts/waiting",
    response_model=list[s.ReceiptWaitingOut],
    summary="Labelled, not yet shelved — the second moment's queue",
)
def waiting_receipts(
    user: StockViewer, session: SessionDep
) -> list[s.ReceiptWaitingOut]:
    """Receipts whose goods are still standing in the receiving area.

    The screen may be closed between the two moments — nothing is lost, QABUL
    is a sellable place — and this is what brings the question back after a
    reload: on ``/qabul`` as the queue, on the dashboard as a count with the
    oldest age on it. Oldest first, because a queue is worked from the front.
    """
    out = []
    for run, quantity in receipts_waiting(session):
        line = session.exec(
            select(SupplyLine)
            .where(SupplyLine.supply_id == run.id)
            .order_by(col(SupplyLine.id))
        ).first()
        variant = (
            session.get(ProductVariant, line.variant_id) if line else None
        )
        since = run.received_at or run.declared_at
        out.append(
            s.ReceiptWaitingOut(
                id=run.id,
                code=run.code,
                product_id=variant.product_id if variant else None,
                product_title=run.note,
                # Off the first line, which is enough: one receipt is one
                # colour, so every line of it carries the same one.
                colour=variant.colour if variant else "",
                colour_hex=variant.colour_hex if variant else "",
                quantity=quantity,
                age_minutes=max(
                    0, int((utcnow() - since).total_seconds() // 60)
                ),
            )
        )
    out.sort(key=lambda row: -row.age_minutes)
    return out


def receipts_waiting(session) -> list[tuple[Supply, int]]:
    """Every receipt with goods still in QABUL, and how many are standing.

    Off the ledger, per supply: receipted into the receiving area less
    carried out of it. Shared with the dashboard tile so the queue and the
    count on the first screen cannot disagree.

    Capped by what actually stands. QABUL is a sellable place, so a receipt
    can shrink before it is shelved — a pick or a damage takes goods out
    without naming the run — and a receipt whose goods have all left through
    those doors is not waiting for anything. Two unshelved receipts of the
    same variant can each claim the same stragglers under this cap, which is
    accepted: that state lasts minutes, and the alternative is allocating
    anonymous departures between runs by guesswork.
    """
    desk = loc.staging(session, loc.QABUL)
    into = {
        int(supply_id): int(units)
        for supply_id, units in session.exec(
            select(
                StockMovement.supply_id,
                func.coalesce(func.sum(StockMovement.qty), 0),
            )
            .where(
                StockMovement.to_location_id == desk.id,
                col(StockMovement.supply_id).is_not(None),
            )
            .group_by(col(StockMovement.supply_id))
        ).all()
    }
    gone = {
        int(supply_id): int(units)
        for supply_id, units in session.exec(
            select(
                StockMovement.supply_id,
                func.coalesce(func.sum(StockMovement.qty), 0),
            )
            .where(
                StockMovement.from_location_id == desk.id,
                col(StockMovement.supply_id).is_not(None),
            )
            .group_by(col(StockMovement.supply_id))
        ).all()
    }
    waiting = []
    for supply_id, received in into.items():
        if received - gone.get(supply_id, 0) <= 0:
            continue
        # A receipt that was called off is nobody's queue. The arithmetic
        # above already drops it — the reversal is a movement out of the desk
        # — but the cap below lets two unshelved receipts of one variant claim
        # the same stragglers, and a cancelled run must not be one of the two.
        run = session.get(Supply, supply_id)
        if run is None or run.status is SupplyStatus.CANCELLED:
            continue
        standing = sum(
            min(left, st.at(session, desk.id, variant_id))
            for variant_id, left in _still_at_the_desk(
                session, desk.id, supply_id
            ).items()
            if left > 0
        )
        if standing > 0:
            waiting.append((run, standing))
    return waiting


def _still_at_the_desk(
    session: SessionDep, desk_id: int, supply_id: int
) -> dict[int, int]:
    """This receipt's goods still in QABUL, per variant, off the ledger."""
    into = {
        int(variant_id): int(units)
        for variant_id, units in session.exec(
            select(
                StockMovement.variant_id,
                func.coalesce(func.sum(StockMovement.qty), 0),
            )
            .where(
                StockMovement.supply_id == supply_id,
                StockMovement.to_location_id == desk_id,
            )
            .group_by(col(StockMovement.variant_id))
        ).all()
    }
    for variant_id, units in session.exec(
        select(
            StockMovement.variant_id,
            func.coalesce(func.sum(StockMovement.qty), 0),
        )
        .where(
            StockMovement.supply_id == supply_id,
            StockMovement.from_location_id == desk_id,
        )
        .group_by(col(StockMovement.variant_id))
    ).all():
        into[int(variant_id)] = into.get(int(variant_id), 0) - int(units)
    return into


# --------------------------------------------------------------------------- market runs


@router.get(
    "/supplies",
    response_model=list[s.SupplyOut],
    summary="Market runs, newest first",
)
def list_supplies(
    user: StockViewer,
    session: SessionDep,
    status_filter: SupplyStatus | None = Query(None, alias="status"),
) -> list[s.SupplyOut]:
    """The runs, every one of them written by a receipt.

    The hand-driven doors — declaring sacks, dismissing them as sorted,
    calling one off — are gone with the sack flow: a supply row exists
    because ``POST /receipts`` wrote it, already ``received``, and it is
    never edited by hand. This list and the row below it stay because the
    labels screen reprints from a run and the reports read what a run cost.
    """
    stmt = select(Supply)
    if status_filter is not None:
        stmt = stmt.where(Supply.status == status_filter)
    rows = session.exec(
        stmt.order_by(col(Supply.declared_at).desc(), col(Supply.id).desc())
    ).all()
    return [_supply_out(session, row) for row in rows]


@router.get("/supplies/{supply_id}", response_model=s.SupplyOut)
def get_supply(supply_id: int, user: StockViewer, session: SessionDep) -> s.SupplyOut:
    return _supply_out(session, _supply(session, supply_id))


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
        cells = [_cell(session, payload.code)]
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

    Asking for more than the building holds is refused in the reader's
    language. It used to arrive as ``str(error)`` — "only 4 of
    MB-000001-QORA-M on the shelves, not 999", English, with an internal code
    in it — on a form whose every other refusal is Uzbek. See
    ``app.stock.refusal``.
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
        raise st.refusal(error) from None

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


def _cell(session: SessionDep, code: str) -> Location:
    """A typed or scanned cell code, checked rather than trusted.

    ``A-03-11`` is one keystroke away from ``A-03-01``, and a scanner can
    read a label still stuck to a shelf that left the room. A code for a cell
    that is not there is refused; a code for the wrong *cell* is caught by
    the screen showing what is in it.

    Says nothing about whether the cell is retired, because the two callers
    want opposite answers: goods being shelved must not go into a cell that
    is off the map, while emptying one is the way goods get out of exactly
    that mess and must keep working. ``_open_cell`` below is the arriving
    half.
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


def _open_cell(session: SessionDep, code: str) -> Location:
    """The same, and standing in the room: goods may actually go in here.

    ``loc.by_code`` finds a cell by its code and says nothing about whether it
    is still part of the building, so a receipt could be shelved into a cell
    somebody retired last month — where the count would include it and the map
    would not show it, which is the one thing retiring a cell is not allowed
    to produce.

    Refused here rather than left to ``st.move``, which refuses it too: this
    runs before anything is written, and the sentence names the cell and says
    to bring it back or pick another one.
    """
    cell = _cell(session, code)
    if not cell.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("cell_retired_destination", code=cell.code),
        )
    return cell


def _receipt_card(session: SessionDep, user: User, payload: s.ReceiptIn) -> Product:
    """The card this receipt goes on: one that exists, or a stub written now.

    Written here rather than through the catalogue's own door because what the
    bench knows is not what that door asks for. It has a name, a colour and
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
    brand = brands.named(session, payload.brand) if payload.brand.strip() else None
    title = payload.title.strip() or " · ".join(
        part
        for part in (kind, brand.name if brand else "", pr.tidy_label(payload.colour))
        if part
    )
    if not title:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("receipt_needs_a_name")
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
    # What came, in the words that tell one run from another. `/yorliqlar`
    # lists runs to reprint from and had nothing but `SUP-000032` to draw —
    # thirty rows of a code nobody can read back to a pile of shoes. One
    # receipt is one colour, so the first line carries the colour of all of
    # them; the title is on the run itself, written there by the receipt.
    first = session.get(ProductVariant, lines[0].variant_id) if lines else None
    product = (
        session.get(Product, first.product_id) if first is not None else None
    )
    # When the run happened, and how long ago — the figure a person scanning
    # a list of runs reads first. It used to be `received_at - declared_at`,
    # the standing time of a sack in the flow that is gone: a receipt stamps
    # both in the same breath, so it read nought for every run this door has
    # ever written.
    since = supply.received_at or supply.declared_at
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
        created_at=since,
        age_minutes=max(0, int((utcnow() - since).total_seconds() // 60)),
        product_title=supply.note or (product.title if product else ""),
        colour=first.colour if first is not None else "",
        colour_hex=first.colour_hex if first is not None else "",
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
