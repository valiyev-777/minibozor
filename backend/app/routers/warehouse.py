"""The warehouse: how goods arrive, get counted, and leave.

Under this model the goods are ours to hold and the seller's to own. So the
two sides of the shelf answer to different people, and these endpoints draw
that line:

* **A seller declares and requests.** A supply is a promise that a pallet is
  coming; a removal is a request to have goods back. Both are the seller's to
  make and neither moves a count.
* **The warehouse counts.** Receiving a supply, closing a stocktake, and
  handing a removal over are the only ways a figure changes here, and each one
  writes to ``stock_movements`` with a kind, a reason and a name against it.

Nothing sets a count. Every endpoint writes a *difference*, which is what
makes two people working the same shelf at once safe: the second save adds to
the first rather than erasing it.

The batch code is ours, not the seller's. A seller's own reference belongs to
their system — it may repeat, it may be missing, and two sellers may use the
same one on the same day — so the pallet gets a code from here and the
warehouse looks for that.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import offers as of
from app import schemas as s
from app import stock as st
from app.deps import SellerUser, SessionDep, StockViewer, WarehouseUser
from app.models import (
    Offer,
    Product,
    ProductVariant,
    RemovalLine,
    RemovalOrder,
    RemovalStatus,
    Seller,
    StockCount,
    StockCountLine,
    StockCountStatus,
    StockMovement,
    StockMovementKind,
    Supply,
    SupplyLine,
    SupplyStatus,
    User,
    UserRole,
    utcnow,
)

router = APIRouter(prefix="/staff", tags=["staff"])


def _next_code(session: SessionDep, model, prefix: str) -> str:
    """The next code in a series, ours rather than anybody else's."""
    used = session.exec(select(func.count()).select_from(model)).one()
    return f"{prefix}-{int(used) + 1:06d}"


# --------------------------------------------------------------------------- supplies


@router.post(
    "/supplies",
    response_model=s.SupplyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Declare a batch that is coming in",
)
def declare_supply(
    payload: s.SupplyCreateIn, user: SellerUser, session: SessionDep
) -> s.SupplyOut:
    """A promise, not a movement. Nothing reaches the shelf until it is counted."""
    seller = _seller_for(session, user, payload.seller_id)
    supply = Supply(
        code=_next_code(session, Supply, "SUP"),
        seller_id=seller.id,
        note=payload.note,
    )
    session.add(supply)
    session.commit()
    session.refresh(supply)

    for line in payload.lines:
        offer = _own_offer(session, seller, line.offer_id)
        _check_variant(session, offer, line.variant_id)
        session.add(
            SupplyLine(
                supply_id=supply.id,
                offer_id=offer.id,
                variant_id=line.variant_id,
                declared_quantity=line.quantity,
            )
        )
    session.commit()
    return _supply_out(session, supply)


@router.get(
    "/supplies",
    response_model=list[s.SupplyOut],
    summary="My batches — or everybody's, for the warehouse",
)
def list_supplies(
    user: StockViewer,
    session: SessionDep,
    status_filter: SupplyStatus | None = Query(None, alias="status"),
) -> list[s.SupplyOut]:
    stmt = select(Supply)
    if user.role is UserRole.SELLER:
        # Not a filter they chose — the only rows that exist for them.
        stmt = stmt.where(Supply.seller_id == _own_seller(session, user).id)
    if status_filter is not None:
        stmt = stmt.where(Supply.status == status_filter)
    rows = session.exec(stmt.order_by(col(Supply.declared_at).desc())).all()
    return [_supply_out(session, row) for row in rows]


@router.get("/supplies/{supply_id}", response_model=s.SupplyOut)
def get_supply(supply_id: int, user: StockViewer, session: SessionDep) -> s.SupplyOut:
    return _supply_out(session, _visible_supply(session, user, supply_id))


@router.post(
    "/supplies/{supply_id}/receive",
    response_model=s.SupplyOut,
    summary="Count a batch in — this is where goods reach the shelf",
)
def receive_supply(
    supply_id: int,
    payload: s.SupplyReceiveIn,
    user: WarehouseUser,
    session: SessionDep,
) -> s.SupplyOut:
    """What was actually found, line by line, and the shelf follows.

    The declared figure is left alone: a declaration is a promise and a
    receipt is a fact, and the gap between them is the only thing either party
    will want to talk about afterwards. A line not mentioned is received as
    nought — it did not turn up.
    """
    supply = session.get(Supply, supply_id)
    if supply is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("supply_not_found"))
    if supply.status is not SupplyStatus.DECLARED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=supply.status.value, to="received"),
        )

    counted = {entry.line_id: entry.received_quantity for entry in payload.lines}
    lines = session.exec(
        select(SupplyLine).where(SupplyLine.supply_id == supply.id)
    ).all()
    unknown = set(counted) - {line.id for line in lines}
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("supply_line_not_found")
        )

    touched: set[int] = set()
    for line in lines:
        received = counted.get(line.id, 0)
        line.received_quantity = received
        session.add(line)
        offer = session.get(Offer, line.offer_id)
        if offer is None or received == 0:
            continue
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.INTAKE,
            quantity=received,
            variant_id=line.variant_id,
            actor=user,
            reason=payload.note or f"{supply.code} qabul qilindi",
            supply_id=supply.id,
        )
        touched.add(offer.product_id)

    supply.status = SupplyStatus.RECEIVED
    supply.received_at = utcnow()
    supply.received_by_id = user.id
    if payload.note:
        supply.note = payload.note
    session.add(supply)

    audit.record(
        session,
        actor=user,
        action="supply.receive",
        entity="supply",
        entity_id=supply.id,
        field="status",
        old=SupplyStatus.DECLARED,
        new=SupplyStatus.RECEIVED,
        note=payload.note,
    )
    session.commit()
    for product_id in touched:
        of.refresh(session, product_id)
    session.commit()
    session.refresh(supply)
    return _supply_out(session, supply)


@router.post(
    "/supplies/{supply_id}/cancel",
    response_model=s.SupplyOut,
    summary="Call off a batch that has not arrived",
)
def cancel_supply(
    supply_id: int, user: StockViewer, session: SessionDep
) -> s.SupplyOut:
    supply = _visible_supply(session, user, supply_id)
    if supply.status is not SupplyStatus.DECLARED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=supply.status.value, to="cancelled"),
        )
    supply.status = SupplyStatus.CANCELLED
    session.add(supply)
    audit.record(
        session,
        actor=user,
        action="supply.cancel",
        entity="supply",
        entity_id=supply.id,
        field="status",
        old=SupplyStatus.DECLARED,
        new=SupplyStatus.CANCELLED,
    )
    session.commit()
    session.refresh(supply)
    return _supply_out(session, supply)


# --------------------------------------------------------------------------- stocktakes


@router.post(
    "/stock-counts",
    response_model=s.StockCountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a stocktake, snapshotting what is expected",
)
def open_count(
    payload: s.StockCountCreateIn, user: WarehouseUser, session: SessionDep
) -> s.StockCountOut:
    """The expected figures are frozen now, not read at the end.

    A sale during the count would otherwise look like a discrepancy, and
    somebody would go looking for goods that were bought while they counted.
    """
    offer = session.get(Offer, payload.offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))

    open_already = session.exec(
        select(StockCount).where(
            StockCount.offer_id == offer.id, StockCount.status == StockCountStatus.OPEN
        )
    ).first()
    if open_already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("count_already_open"))

    count = StockCount(
        code=_next_code(session, StockCount, "CNT"),
        offer_id=offer.id,
        note=payload.note,
        opened_by_id=user.id,
    )
    session.add(count)
    session.commit()
    session.refresh(count)

    leaves = of.leaf_variants(session, offer.product_id)
    if leaves:
        for leaf in leaves:
            session.add(
                StockCountLine(
                    count_id=count.id,
                    variant_id=leaf.id,
                    expected=of.variant_stock(session, offer.id, leaf.id) or 0,
                )
            )
    else:
        session.add(StockCountLine(count_id=count.id, expected=offer.stock_left))
    session.commit()
    return _count_out(session, count)


@router.get("/stock-counts", response_model=list[s.StockCountOut])
def list_counts(
    user: WarehouseUser,
    session: SessionDep,
    status_filter: StockCountStatus | None = Query(None, alias="status"),
) -> list[s.StockCountOut]:
    stmt = select(StockCount)
    if status_filter is not None:
        stmt = stmt.where(StockCount.status == status_filter)
    rows = session.exec(stmt.order_by(col(StockCount.opened_at).desc())).all()
    return [_count_out(session, row) for row in rows]


@router.get("/stock-counts/{count_id}", response_model=s.StockCountOut)
def get_count(count_id: int, user: WarehouseUser, session: SessionDep) -> s.StockCountOut:
    return _count_out(session, _count(session, count_id))


@router.post(
    "/stock-counts/{count_id}/close",
    response_model=s.StockCountOut,
    summary="Record what was found, and correct the difference",
)
def close_count(
    count_id: int,
    payload: s.StockCountCloseIn,
    user: WarehouseUser,
    session: SessionDep,
) -> s.StockCountOut:
    """The difference becomes a movement, so the correction has a reason.

    Against the *expected* figure frozen when the count opened, not against
    the shelf as it stands now — anything sold in between is already in the
    ledger and is not a discrepancy.
    """
    count = _count(session, count_id)
    if count.status is not StockCountStatus.OPEN:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=count.status.value, to="closed"),
        )
    offer = session.get(Offer, count.offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))

    lines = session.exec(
        select(StockCountLine).where(StockCountLine.count_id == count.id)
    ).all()
    by_variant = {line.variant_id: line for line in lines}
    for entry in payload.lines:
        line = by_variant.get(entry.variant_id)
        if line is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
            )
        line.counted = entry.counted
        session.add(line)

    for line in lines:
        if line.counted is None or line.difference == 0:
            continue
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=line.difference,
            variant_id=line.variant_id,
            actor=user,
            reason=payload.note or f"{count.code} sanoq farqi",
            count_id=count.id,
        )

    count.status = StockCountStatus.CLOSED
    count.closed_at = utcnow()
    count.closed_by_id = user.id
    if payload.note:
        count.note = payload.note
    session.add(count)

    audit.record(
        session,
        actor=user,
        action="stock_count.close",
        entity="stock_count",
        entity_id=count.id,
        field="difference",
        old=None,
        new=sum(line.difference or 0 for line in lines),
        note=payload.note or count.code,
    )
    of.refresh(session, offer.product_id)
    session.commit()
    session.refresh(count)
    return _count_out(session, count)


# --------------------------------------------------------------------------- removals


@router.post(
    "/removals",
    response_model=s.RemovalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ask for goods back — damaged or simply unsold",
)
def request_removal(
    payload: s.RemovalCreateIn, user: SellerUser, session: SessionDep
) -> s.RemovalOut:
    seller = _seller_for(session, user, payload.seller_id)
    removal = RemovalOrder(
        code=_next_code(session, RemovalOrder, "RMV"),
        seller_id=seller.id,
        reason=payload.reason,
        note=payload.note,
    )
    session.add(removal)
    session.commit()
    session.refresh(removal)

    for line in payload.lines:
        offer = _own_offer(session, seller, line.offer_id)
        _check_variant(session, offer, line.variant_id)
        session.add(
            RemovalLine(
                removal_id=removal.id,
                offer_id=offer.id,
                variant_id=line.variant_id,
                quantity=line.quantity,
            )
        )
    session.commit()
    return _removal_out(session, removal)


@router.get("/removals", response_model=list[s.RemovalOut])
def list_removals(
    user: StockViewer,
    session: SessionDep,
    status_filter: RemovalStatus | None = Query(None, alias="status"),
) -> list[s.RemovalOut]:
    stmt = select(RemovalOrder)
    if user.role is UserRole.SELLER:
        stmt = stmt.where(RemovalOrder.seller_id == _own_seller(session, user).id)
    if status_filter is not None:
        stmt = stmt.where(RemovalOrder.status == status_filter)
    rows = session.exec(stmt.order_by(col(RemovalOrder.requested_at).desc())).all()
    return [_removal_out(session, row) for row in rows]


@router.get("/removals/{removal_id}", response_model=s.RemovalOut)
def get_removal(removal_id: int, user: StockViewer, session: SessionDep) -> s.RemovalOut:
    return _removal_out(session, _visible_removal(session, user, removal_id))


@router.post(
    "/removals/{removal_id}/prepare",
    response_model=s.RemovalOut,
    summary="Pick it and set it aside — the goods stop being on sale",
)
def prepare_removal(
    removal_id: int,
    payload: s.RemovalPrepareIn,
    user: WarehouseUser,
    session: SessionDep,
) -> s.RemovalOut:
    """Ready means picked and standing by the door.

    No movement yet — the goods are still ours to account for — but they are
    held: selling something that is already on a pallet waiting for its owner
    is the failure this state exists to prevent.
    """
    removal = _removal(session, removal_id)
    if removal.status is not RemovalStatus.REQUESTED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=removal.status.value, to="ready"),
        )

    prepared = {entry.line_id: entry.prepared_quantity for entry in payload.lines}
    lines = session.exec(
        select(RemovalLine).where(RemovalLine.removal_id == removal.id)
    ).all()
    unknown = set(prepared) - {line.id for line in lines}
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("removal_line_not_found")
        )

    touched: set[int] = set()
    for line in lines:
        line.prepared_quantity = prepared.get(line.id, 0)
        session.add(line)
        offer = session.get(Offer, line.offer_id)
        if offer is not None:
            touched.add(offer.product_id)

    removal.status = RemovalStatus.READY
    removal.ready_at = utcnow()
    removal.prepared_by_id = user.id
    session.add(removal)
    session.commit()
    # Held now, so the card must stop offering them.
    for product_id in touched:
        of.refresh(session, product_id)
    session.commit()
    session.refresh(removal)
    return _removal_out(session, removal)


@router.post(
    "/removals/{removal_id}/collect",
    response_model=s.RemovalOut,
    summary="Hand it over — this is where the goods leave us",
)
def collect_removal(
    removal_id: int, user: WarehouseUser, session: SessionDep
) -> s.RemovalOut:
    removal = _removal(session, removal_id)
    if removal.status is not RemovalStatus.READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=removal.status.value, to="collected"),
        )

    touched: set[int] = set()
    for line in session.exec(
        select(RemovalLine).where(RemovalLine.removal_id == removal.id)
    ).all():
        offer = session.get(Offer, line.offer_id)
        if offer is None or not line.prepared_quantity:
            continue
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.SELLER_RETURN,
            quantity=line.prepared_quantity,
            variant_id=line.variant_id,
            actor=user,
            reason=removal.note or f"{removal.code} · {removal.reason.value}",
            removal_id=removal.id,
        )
        touched.add(offer.product_id)

    removal.status = RemovalStatus.COLLECTED
    removal.collected_at = utcnow()
    session.add(removal)
    audit.record(
        session,
        actor=user,
        action="removal.collect",
        entity="removal_order",
        entity_id=removal.id,
        field="status",
        old=RemovalStatus.READY,
        new=RemovalStatus.COLLECTED,
        note=removal.code,
    )
    session.commit()
    for product_id in touched:
        of.refresh(session, product_id)
    session.commit()
    session.refresh(removal)
    return _removal_out(session, removal)


# --------------------------------------------------------------------------- the shelf


@router.post(
    "/offers/{offer_id}/write-off",
    response_model=s.ShelfOut,
    summary="Goods that are gone — damaged, lost, spoiled",
)
def write_off(
    offer_id: int, payload: s.WriteOffIn, user: WarehouseUser, session: SessionDep
) -> s.ShelfOut:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))
    _check_variant(session, offer, payload.variant_id)

    st.move(
        session,
        offer=offer,
        kind=StockMovementKind.WRITE_OFF,
        quantity=payload.quantity,
        variant_id=payload.variant_id,
        actor=user,
        reason=payload.reason,
    )
    audit.record(
        session,
        actor=user,
        action="stock.write_off",
        entity="offer",
        entity_id=offer.id,
        field="stock_left",
        old=None,
        new=-payload.quantity,
        note=payload.reason,
    )
    of.refresh(session, offer.product_id)
    session.commit()
    session.refresh(offer)
    return _shelf_out(session, offer, payload.variant_id)


@router.get(
    "/offers/{offer_id}/shelf",
    response_model=list[s.ShelfOut],
    summary="On hand, promised, and left to sell",
)
def read_shelf(
    offer_id: int, user: StockViewer, session: SessionDep
) -> list[s.ShelfOut]:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))
    if user.role is UserRole.SELLER and offer.seller_id != _own_seller(session, user).id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_offer"))

    rows = [_shelf_out(session, offer, None)]
    rows.extend(
        _shelf_out(session, offer, leaf.id)
        for leaf in of.leaf_variants(session, offer.product_id)
    )
    return rows


@router.get(
    "/stock/movements",
    response_model=s.Page[s.MovementOut],
    summary="The ledger — every reason a count changed",
)
def list_movements(
    user: StockViewer,
    session: SessionDep,
    offer_id: int | None = Query(None),
    kind: StockMovementKind | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> s.Page[s.MovementOut]:
    """A count that looks wrong is not an argument, it is this list."""
    stmt = select(StockMovement)
    if user.role is UserRole.SELLER:
        mine = session.exec(
            select(Offer.id).where(Offer.seller_id == _own_seller(session, user).id)
        ).all()
        stmt = stmt.where(col(StockMovement.offer_id).in_(mine or [-1]))
    if offer_id is not None:
        stmt = stmt.where(StockMovement.offer_id == offer_id)
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


def _own_seller(session: SessionDep, user: User) -> Seller:
    seller = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
    if seller is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
        )
    return seller


def _seller_for(session: SessionDep, user: User, seller_id: int | None) -> Seller:
    """Whose batch this is. A seller acts as themselves; an admin must say."""
    if user.role is not UserRole.ADMIN:
        own = _own_seller(session, user)
        if seller_id is not None and seller_id != own.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_offer"))
        return own
    if seller_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("seller_required"))
    seller = session.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("seller_not_found"))
    return seller


def _own_offer(session: SessionDep, seller: Seller, offer_id: int) -> Offer:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))
    if offer.seller_id != seller.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_offer"))
    return offer


def _check_variant(session: SessionDep, offer: Offer, variant_id: int | None) -> None:
    """A count sits on a leaf of this product, or on the offer itself.

    Which cell is required wherever there are cells. A movement that names no
    leaf comes off the offer's total and off no colour, and afterwards there
    is no working out which colour it was — the shelf and its colours drift
    apart by exactly that much, permanently. The same rule the basket enforces
    on the way out is enforced here on the way in.
    """
    leaves = {leaf.id: leaf for leaf in of.leaf_variants(session, offer.product_id)}
    if variant_id is None:
        if leaves:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                i18n.label("variant_required"),
            )
        return
    variant = session.get(ProductVariant, variant_id)
    if variant is None or variant.product_id != offer.product_id or variant.id not in leaves:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
        )


def _visible_supply(session: SessionDep, user: User, supply_id: int) -> Supply:
    supply = session.get(Supply, supply_id)
    if supply is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("supply_not_found"))
    if user.role is UserRole.SELLER and supply.seller_id != _own_seller(session, user).id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_supply"))
    return supply


def _removal(session: SessionDep, removal_id: int) -> RemovalOrder:
    removal = session.get(RemovalOrder, removal_id)
    if removal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("removal_not_found"))
    return removal


def _visible_removal(session: SessionDep, user: User, removal_id: int) -> RemovalOrder:
    removal = _removal(session, removal_id)
    if user.role is UserRole.SELLER and removal.seller_id != _own_seller(session, user).id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_supply"))
    return removal


def _count(session: SessionDep, count_id: int) -> StockCount:
    count = session.get(StockCount, count_id)
    if count is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("count_not_found"))
    return count


def _seller_out(session: SessionDep, seller_id: int) -> s.SellerOut:
    seller = session.get(Seller, seller_id)
    return (
        s.SellerOut(id=seller.id, name=seller.name)
        if seller
        else s.SellerOut(id=0, name="")
    )


def _names(
    session: SessionDep, offer_id: int, variant_id: int | None
) -> tuple[str, str, str]:
    """The label, the title and the code — what a person and a scanner read."""
    offer = session.get(Offer, offer_id)
    product = session.get(Product, offer.product_id) if offer else None
    variant = session.get(ProductVariant, variant_id) if variant_id else None
    return (
        (variant.label if variant else "—"),
        (product.title if product else ""),
        (product.sku if product else ""),
    )


def _supply_out(session: SessionDep, supply: Supply) -> s.SupplyOut:
    lines = session.exec(
        select(SupplyLine).where(SupplyLine.supply_id == supply.id).order_by(col(SupplyLine.id))
    ).all()
    out = []
    for line in lines:
        label, title, sku = _names(session, line.offer_id, line.variant_id)
        out.append(
            s.SupplyLineOut(
                id=line.id,
                offer_id=line.offer_id,
                variant_id=line.variant_id,
                sku=sku,
                variant_label=label,
                product_title=title,
                declared_quantity=line.declared_quantity,
                received_quantity=line.received_quantity,
                difference=line.difference,
            )
        )
    return s.SupplyOut(
        id=supply.id,
        code=supply.code,
        seller=_seller_out(session, supply.seller_id),
        status=supply.status,
        note=supply.note,
        lines=out,
        declared_at=supply.declared_at,
        received_at=supply.received_at,
    )


def _count_out(session: SessionDep, count: StockCount) -> s.StockCountOut:
    offer = session.get(Offer, count.offer_id)
    product = session.get(Product, offer.product_id) if offer else None
    lines = session.exec(
        select(StockCountLine)
        .where(StockCountLine.count_id == count.id)
        .order_by(col(StockCountLine.id))
    ).all()
    return s.StockCountOut(
        id=count.id,
        code=count.code,
        offer_id=count.offer_id,
        product_title=product.title if product else "",
        seller=_seller_out(session, offer.seller_id) if offer else s.SellerOut(id=0, name=""),
        status=count.status,
        note=count.note,
        lines=[
            s.StockCountLineOut(
                id=line.id,
                variant_id=line.variant_id,
                sku=_names(session, count.offer_id, line.variant_id)[2],
                variant_label=_names(session, count.offer_id, line.variant_id)[0],
                expected=line.expected,
                counted=line.counted,
                difference=line.difference,
            )
            for line in lines
        ],
        opened_at=count.opened_at,
        closed_at=count.closed_at,
    )


def _removal_out(session: SessionDep, removal: RemovalOrder) -> s.RemovalOut:
    lines = session.exec(
        select(RemovalLine)
        .where(RemovalLine.removal_id == removal.id)
        .order_by(col(RemovalLine.id))
    ).all()
    out = []
    for line in lines:
        label, title, sku = _names(session, line.offer_id, line.variant_id)
        out.append(
            s.RemovalLineOut(
                id=line.id,
                offer_id=line.offer_id,
                variant_id=line.variant_id,
                sku=sku,
                variant_label=label,
                product_title=title,
                quantity=line.quantity,
                prepared_quantity=line.prepared_quantity,
            )
        )
    return s.RemovalOut(
        id=removal.id,
        code=removal.code,
        seller=_seller_out(session, removal.seller_id),
        status=removal.status,
        reason=removal.reason,
        note=removal.note,
        lines=out,
        requested_at=removal.requested_at,
        ready_at=removal.ready_at,
        collected_at=removal.collected_at,
    )


def _shelf_out(session: SessionDep, offer: Offer, variant_id: int | None) -> s.ShelfOut:
    label, _, _ = _names(session, offer.id, variant_id)
    return s.ShelfOut(
        offer_id=offer.id,
        variant_id=variant_id,
        variant_label=label if variant_id else "Hammasi",
        on_hand=st.on_hand(session, offer.id, variant_id),
        reserved=st.reserved(session, offer.id, variant_id),
        sellable=st.sellable(session, offer, variant_id),
    )


def _movement_out(session: SessionDep, movement: StockMovement) -> s.MovementOut:
    label, title, sku = _names(session, movement.offer_id, movement.variant_id)
    actor = session.get(User, movement.actor_id) if movement.actor_id else None
    return s.MovementOut(
        id=movement.id,
        offer_id=movement.offer_id,
        variant_id=movement.variant_id,
        sku=sku,
        variant_label=label,
        product_title=title,
        kind=movement.kind,
        quantity=movement.quantity,
        reason=movement.reason,
        actor=(actor.full_name or actor.phone) if actor else "tizim",
        supply_id=movement.supply_id,
        order_id=movement.order_id,
        return_request_id=movement.return_request_id,
        count_id=movement.count_id,
        removal_id=movement.removal_id,
        created_at=movement.created_at,
    )
