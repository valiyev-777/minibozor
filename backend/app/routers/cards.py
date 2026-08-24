from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import CardStatus, PaymentCard

router = APIRouter(prefix="/payment-cards", tags=["payment"])


@router.get("", response_model=list[s.CardOut], summary="Screen 32 — saved cards")
def list_cards(user: CurrentUser, session: SessionDep) -> list[s.CardOut]:
    rows = session.exec(
        select(PaymentCard)
        .where(PaymentCard.user_id == user.id)
        .order_by(col(PaymentCard.is_default).desc(), col(PaymentCard.created_at))
    ).all()
    return [sv.card_out(c) for c in rows]


@router.post("", response_model=s.CardOut, status_code=status.HTTP_201_CREATED)
def add_card(payload: s.CardIn, user: CurrentUser, session: SessionDep) -> s.CardOut:
    card = PaymentCard(user_id=user.id, **payload.model_dump())
    if not session.exec(select(PaymentCard).where(PaymentCard.user_id == user.id)).all():
        card.is_default = True
    if card.is_default:
        _clear_default(session, user.id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return sv.card_out(card)


@router.post("/{card_id}/default", response_model=s.CardOut)
def make_default(card_id: int, user: CurrentUser, session: SessionDep) -> s.CardOut:
    card = _owned(session, user.id, card_id)
    if card.status == CardStatus.EXPIRED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Kartaning muddati o'tgan")
    _clear_default(session, user.id)
    card.is_default = True
    session.add(card)
    session.commit()
    session.refresh(card)
    return sv.card_out(card)


@router.delete("/{card_id}", response_model=s.Message)
def delete_card(card_id: int, user: CurrentUser, session: SessionDep) -> s.Message:
    card = _owned(session, user.id, card_id)
    session.delete(card)
    session.commit()
    return s.Message(message="Karta o'chirildi")


def _owned(session: SessionDep, user_id: int, card_id: int) -> PaymentCard:
    card = session.get(PaymentCard, card_id)
    if card is None or card.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Karta topilmadi")
    return card


def _clear_default(session: SessionDep, user_id: int) -> None:
    for row in session.exec(
        select(PaymentCard).where(PaymentCard.user_id == user_id, PaymentCard.is_default.is_(True))
    ).all():
        row.is_default = False
        session.add(row)
