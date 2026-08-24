from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import Address, DeliverySlot, PickupPoint

router = APIRouter(tags=["delivery"])


# --------------------------------------------------------------------------- addresses


@router.get("/addresses", response_model=list[s.AddressOut], summary="Screen 33 — my addresses")
def list_addresses(user: CurrentUser, session: SessionDep) -> list[s.AddressOut]:
    rows = session.exec(
        select(Address)
        .where(Address.user_id == user.id)
        .order_by(col(Address.is_default).desc(), col(Address.created_at))
    ).all()
    return [sv.address_out(a) for a in rows]


@router.post(
    "/addresses",
    response_model=s.AddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Screen 20 — add an address",
)
def create_address(payload: s.AddressIn, user: CurrentUser, session: SessionDep) -> s.AddressOut:
    address = Address(user_id=user.id, **payload.model_dump())
    existing = session.exec(select(Address).where(Address.user_id == user.id)).all()
    if not existing:
        address.is_default = True
        address.badge = address.badge or "ASOSIY"
    if address.is_default:
        _clear_default_addresses(session, user.id)
    session.add(address)
    session.commit()
    session.refresh(address)
    return sv.address_out(address)


@router.put("/addresses/{address_id}", response_model=s.AddressOut)
def update_address(
    address_id: int, payload: s.AddressIn, user: CurrentUser, session: SessionDep
) -> s.AddressOut:
    address = _owned_address(session, user.id, address_id)
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    if address.is_default:
        _clear_default_addresses(session, user.id, keep=address_id)
    session.add(address)
    session.commit()
    session.refresh(address)
    return sv.address_out(address)


@router.delete("/addresses/{address_id}", response_model=s.Message)
def delete_address(address_id: int, user: CurrentUser, session: SessionDep) -> s.Message:
    address = _owned_address(session, user.id, address_id)
    session.delete(address)
    session.commit()
    return s.Message(message="Manzil o'chirildi")


# --------------------------------------------------------------------------- slots


@router.get(
    "/delivery/slots",
    response_model=list[s.SlotDayOut],
    summary="Screen 21 — delivery day and time",
)
def delivery_slots(session: SessionDep, days: int = Query(3, ge=1, le=14)) -> list[s.SlotDayOut]:
    today = date.today()
    window = [today + timedelta(days=n) for n in range(days)]
    rows = session.exec(
        select(DeliverySlot)
        .where(col(DeliverySlot.day).in_(window))
        .order_by(col(DeliverySlot.day), col(DeliverySlot.start_time))
    ).all()

    grouped: dict[date, list[DeliverySlot]] = {d: [] for d in window}
    for row in rows:
        grouped.setdefault(row.day, []).append(row)

    return [
        s.SlotDayOut(
            day=day,
            weekday_label=sv.uz_weekday_label(day, today),
            day_label=str(day.day),
            month_label=sv.UZ_MONTHS[day.month - 1],
            slots=[sv.slot_out(sl) for sl in grouped[day]],
        )
        for day in window
    ]


@router.get(
    "/delivery/pickup-points",
    response_model=list[s.PickupPointOut],
    summary="Screen 19 — pick-up points",
)
def pickup_points(session: SessionDep) -> list[s.PickupPointOut]:
    rows = session.exec(
        select(PickupPoint).where(PickupPoint.active.is_(True)).order_by(col(PickupPoint.distance_km))
    ).all()
    return [sv.pickup_out(p) for p in rows]


# --------------------------------------------------------------------------- helpers


def _owned_address(session: SessionDep, user_id: int, address_id: int) -> Address:
    address = session.get(Address, address_id)
    if address is None or address.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Manzil topilmadi")
    return address


def _clear_default_addresses(session: SessionDep, user_id: int, keep: int | None = None) -> None:
    for row in session.exec(
        select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    ).all():
        if row.id != keep:
            row.is_default = False
            session.add(row)
