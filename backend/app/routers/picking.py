"""Picking: fetching one order off the shelves.

Three decisions shape this file.

**A task is taken, not assigned.** A picker at the bench takes the oldest task
on the board, the same way a courier takes a round. An assigner would be a
person deciding something a queue already decides, and on the evening the
assigner is not in, nothing gets picked.

**The lines come back in walk order.** Serpentine — up one column and down the
next — so the picker walks the room once. A list in id order is a list that
sends somebody back down a rack they have already passed.

**The variant leads, not the cell.** The cell is where you walk to; the
variant is the thing you must not get wrong. So a line is the model, then the
colour and the size, then the code, then the quantity — and a line whose cell
holds more than one thing says so, because a picker reaching into a cell of
black and white shoes has to be told to look.

Picking moves goods: a cell to ``YIGIM``, and the ledger records each one.
Completing the task does not hand anything over — that is the courier taking
the parcel, at their own door.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlmodel import col, func, select

from app import i18n
from app import idempotency as idem
from app import locations as loc
from app import products as pr
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import SessionDep, StockViewer, WarehouseUser
from app.models import (
    Location,
    Order,
    OrderItem,
    OrderStatus,
    PickLine,
    PickStatus,
    PickTask,
    Product,
    ProductVariant,
    StockMovementKind,
    StockPlacement,
    User,
    utcnow,
)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", description="A uuid per queued action")
]


@router.get(
    "/pick",
    response_model=list[s.PickTaskOut],
    summary="The pick queue — oldest first",
)
def pick_queue(
    user: StockViewer,
    session: SessionDep,
    status_filter: PickStatus | None = Query(None, alias="status"),
    mine: bool = Query(False, description="Only what I have taken"),
) -> list[s.PickTaskOut]:
    """A queue is worked from the front, so the oldest task is at the top.

    Serving the newest first is how the order that came in at nine is still
    on the board at six.
    """
    stmt = select(PickTask)
    if status_filter is not None:
        stmt = stmt.where(PickTask.status == status_filter)
    if mine:
        stmt = stmt.where(PickTask.picker_id == user.id)
    rows = session.exec(
        stmt.order_by(col(PickTask.created_at), col(PickTask.id))
    ).all()
    return [_task_out(session, row) for row in rows]


@router.post(
    "/pick/orders/{order_id}",
    response_model=s.PickTaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="Put an order on the board",
)
def build_task(
    order_id: int, user: WarehouseUser, session: SessionDep
) -> s.PickTaskOut:
    """Work out where every line of this order actually is, and list it.

    **A line per place, not per order line.** A model that outgrew its cell is
    in two of them and the picker has to be sent to both; one line saying
    "six" against a cell holding four is a line somebody has to solve standing
    in front of a shelf.

    Built once. Asking again answers with the task that exists rather than
    making a second one, because two boards for one order is two people
    fetching the same parcel.
    """
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("order_not_found"))
    if order.status not in (OrderStatus.PLACED, OrderStatus.PACKING):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("order_not_pickable"))

    existing = session.exec(
        select(PickTask).where(PickTask.order_id == order.id)
    ).first()
    if existing is not None:
        return _task_out(session, existing)

    task = PickTask(order_id=order.id)
    session.add(task)
    session.commit()
    session.refresh(task)

    walk = 0
    for item in session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all():
        if item.variant_id is None:
            continue
        left = item.quantity
        for place, held in st.sellable_places(session, item.variant_id):
            if left <= 0:
                break
            step = min(left, held)
            session.add(
                PickLine(
                    task_id=task.id,
                    order_item_id=item.id,
                    variant_id=item.variant_id,
                    location_id=place.id,
                    qty=step,
                    walk_order=walk,
                )
            )
            walk += 1
            left -= step
        if left > 0:
            # The order promised more than the room holds. The task is still
            # built — a picker fetching what there is beats a screen refusing
            # to open — and the short line is visible as a quantity nobody can
            # complete.
            session.add(
                PickLine(
                    task_id=task.id,
                    order_item_id=item.id,
                    variant_id=item.variant_id,
                    location_id=loc.staging(session, loc.QABUL).id,
                    qty=left,
                    walk_order=walk,
                )
            )
            walk += 1
    session.commit()
    _reorder(session, task)
    return _task_out(session, task)


@router.get(
    "/pick/waiting",
    response_model=list[s.PickWaitingOut],
    summary="Orders nobody has begun — the front of the board",
)
def waiting_orders(user: StockViewer, session: SessionDep) -> list[s.PickWaitingOut]:
    """Every placed order with no task on it, oldest first.

    This is the fix for a queue that only filled when somebody remembered.
    "A task is taken, not assigned" is the first thing this file says, and it
    was only half true: the taking was the bench's, but the *putting on the
    board* was a button on the office's order screen — a screen the warehouse
    role cannot even open. So an order arrived from a telephone, sat in
    ``placed``, and the bench's board stayed empty until the owner opened
    Buyurtmalar and pressed a button for it, one order at a time. On the
    evening the owner was not in, nothing was picked, which is precisely the
    failure the docstring at the top of this file says a queue exists to
    prevent.

    Nothing is created here. A row in this list is an order, not a task; the
    task is built when a picker starts one, which is also the moment the cells
    are worked out, so the walk list is as fresh as the shelf. Building them
    all up front would freeze a room that moves all day.

    ``placed`` only. An order in ``packing`` has been picked — that is what
    completing a task does — and putting it back on this board would send a
    second person after a parcel already on the courier shelf.
    """
    taken = select(PickTask.order_id)
    rows = session.exec(
        select(Order)
        .where(Order.status == OrderStatus.PLACED)
        .where(col(Order.id).not_in(taken))
        .order_by(col(Order.created_at), col(Order.id))
    ).all()
    return [_waiting_out(session, order) for order in rows]


@router.get("/pick/{task_id}", response_model=s.PickTaskOut)
def get_task(task_id: int, user: StockViewer, session: SessionDep) -> s.PickTaskOut:
    return _task_out(session, _task(session, task_id))


@router.post(
    "/pick/{task_id}/take",
    response_model=s.PickTaskOut,
    summary="Take a task off the board",
)
def take_task(
    task_id: int,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.PickTaskOut:
    """Taken, not assigned — and taken once.

    Two pickers tapping the same task is the ordinary race on a shared board,
    so the second one is told it is gone rather than being sent to fetch a
    parcel somebody is already carrying.
    """
    done = idem.replay(session, user, idempotency_key, "pick.take", None)
    if done is not None:
        return s.PickTaskOut(**done)

    task = _task(session, task_id)
    if task.status is not PickStatus.WAITING:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("pick_already_taken"))

    task.status = PickStatus.PICKING
    task.picker_id = user.id
    task.taken_at = utcnow()
    session.add(task)

    out = _task_out(session, task)
    idem.keep(session, user, idempotency_key, "pick.take", None, out)
    replayed = idem.commit(session, user, idempotency_key, "pick.take")
    return s.PickTaskOut(**replayed) if replayed else out


@router.post(
    "/pick/{task_id}/lines/{line_id}",
    response_model=s.PickTaskOut,
    summary="One line fetched — the goods move to YIGIM",
)
def pick_line(
    task_id: int,
    line_id: int,
    payload: s.PickLineIn,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.PickTaskOut:
    """One tap, one move: out of the cell and into the packing area.

    The move is written here rather than at the end, because the goods leave
    the cell when somebody lifts them out of it. A task abandoned half way
    through has still moved what it moved, and the room says so.
    """
    done = idem.replay(session, user, idempotency_key, "pick.line", payload)
    if done is not None:
        return s.PickTaskOut(**done)

    task = _task(session, task_id)
    _must_be_mine(task, user)
    line = session.get(PickLine, line_id)
    if line is None or line.task_id != task.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("pick_line_not_found"))
    if line.picked_qty >= line.qty:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("pick_line_done"))

    wanted = min(payload.qty, line.qty - line.picked_qty)
    variant = session.get(ProductVariant, line.variant_id)
    cell = session.get(Location, line.location_id)
    packing = loc.staging(session, loc.YIGIM)
    try:
        st.move(
            session,
            variant=variant,
            qty=wanted,
            kind=StockMovementKind.PICK,
            frm=cell,
            to=packing,
            actor=user,
            reason=cell.code if cell else "",
            order_id=task.order_id,
        )
    except st.StockError as error:
        raise st.refusal(error) from None

    line.picked_qty += wanted
    if line.picked_qty >= line.qty:
        line.picked_at = utcnow()
    session.add(line)
    pr.refresh(session, variant.product_id)

    out = _task_out(session, task)
    idem.keep(session, user, idempotency_key, "pick.line", payload, out)
    replayed = idem.commit(session, user, idempotency_key, "pick.line")
    return s.PickTaskOut(**replayed) if replayed else out


@router.post(
    "/pick/{task_id}/complete",
    response_model=s.PickTaskOut,
    summary="The parcel is in YIGIM, waiting for a courier",
)
def complete_task(
    task_id: int,
    user: WarehouseUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey,
) -> s.PickTaskOut:
    """Finished means every line fetched, and the order moves to ``packing``.

    It does not hand anything over. The handover is the courier picking the
    parcel up at their own door, which is a different person's decision and a
    different move in the ledger.
    """
    done = idem.replay(session, user, idempotency_key, "pick.complete", None)
    if done is not None:
        return s.PickTaskOut(**done)

    task = _task(session, task_id)
    _must_be_mine(task, user)
    lines = _lines(session, task)
    short = [line for line in lines if line.picked_qty < line.qty]
    if short:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("pick_not_finished"))

    task.status = PickStatus.PICKED
    task.finished_at = utcnow()
    session.add(task)

    order = session.get(Order, task.order_id)
    if order is not None and order.status is OrderStatus.PLACED:
        order.status = OrderStatus.PACKING
        order.updated_at = utcnow()
        session.add(order)
        sv.stamp_order_event(session, order)

    out = _task_out(session, task)
    idem.keep(session, user, idempotency_key, "pick.complete", None, out)
    replayed = idem.commit(session, user, idempotency_key, "pick.complete")
    return s.PickTaskOut(**replayed) if replayed else out


# --------------------------------------------------------------------------- helpers


def _task(session: SessionDep, task_id: int) -> PickTask:
    row = session.get(PickTask, task_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("pick_not_found"))
    return row


def _must_be_mine(task: PickTask, user: User) -> None:
    """Somebody else's trolley.

    Not a permission so much as a fact: the goods are in their hands, and a
    second person marking lines picked is describing a walk they did not take.
    """
    if task.picker_id not in (None, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("pick_not_yours"))
    if task.status is PickStatus.PICKED:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("pick_already_done"))


def _lines(session: SessionDep, task: PickTask) -> list[PickLine]:
    return list(
        session.exec(
            select(PickLine)
            .where(PickLine.task_id == task.id)
            .order_by(col(PickLine.walk_order), col(PickLine.id))
        ).all()
    )


def _reorder(session: SessionDep, task: PickTask) -> None:
    """Number the lines in the order somebody actually walks them."""
    lines = list(
        session.exec(select(PickLine).where(PickLine.task_id == task.id)).all()
    )
    places = {
        line.location_id: session.get(Location, line.location_id) for line in lines
    }
    lines.sort(key=lambda line: loc.walk_order(places[line.location_id]))
    for order, line in enumerate(lines):
        line.walk_order = order
        session.add(line)
    session.commit()


def _waiting_out(session: SessionDep, order: Order) -> s.PickWaitingOut:
    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()
    return s.PickWaitingOut(
        order_id=order.id,
        order_code=order.code,
        items_count=sum(item.quantity for item in items),
        items_summary=sv.items_summary(list(items)),
        delivery_day=order.delivery_day,
        delivery_window=(
            f"{order.delivery_start}–{order.delivery_end}"
            if order.delivery_start and order.delivery_end
            else ""
        ),
        age_minutes=max(0, int((utcnow() - order.created_at).total_seconds() // 60)),
    )


def _task_out(session: SessionDep, task: PickTask) -> s.PickTaskOut:
    order = session.get(Order, task.order_id)
    picker = session.get(User, task.picker_id) if task.picker_id else None
    lines = []
    for line in _lines(session, task):
        variant = session.get(ProductVariant, line.variant_id)
        product = session.get(Product, variant.product_id) if variant else None
        place = session.get(Location, line.location_id)
        distinct = session.exec(
            select(func.count())
            .select_from(StockPlacement)
            .where(
                StockPlacement.location_id == line.location_id,
                StockPlacement.qty > 0,
            )
        ).one()
        lines.append(
            s.PickLineOut(
                id=line.id,
                variant_id=line.variant_id,
                product_title=product.title if product else "",
                colour=variant.colour if variant else "",
                size=variant.size if variant else "",
                variant_label=sv.variant_label(variant) if variant else "",
                sku=variant.sku if variant else "",
                barcode=variant.barcode if variant else "",
                location_id=line.location_id,
                location_code=place.code if place else "",
                qty=line.qty,
                picked_qty=line.picked_qty,
                walk_order=line.walk_order,
                mixed_cell=int(distinct) > 1,
            )
        )
    return s.PickTaskOut(
        id=task.id,
        order_id=task.order_id,
        order_code=order.code if order else "",
        status=task.status,
        picker=(picker.full_name or picker.phone) if picker else "",
        lines=lines,
        created_at=task.created_at,
        taken_at=task.taken_at,
        finished_at=task.finished_at,
        age_minutes=max(
            0, int((utcnow() - task.created_at).total_seconds() // 60)
        ),
    )
