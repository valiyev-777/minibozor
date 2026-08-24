from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import Favorite, Product

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=s.Page[s.ProductCardOut], summary="Screen 35 — favourites")
def list_favorites(
    user: CurrentUser,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=60),
) -> s.Page[s.ProductCardOut]:
    stmt = (
        select(Product)
        .join(Favorite, col(Favorite.product_id) == col(Product.id))
        .where(Favorite.user_id == user.id)
        .order_by(col(Favorite.created_at).desc())
    )
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    favs = sv.favorite_ids(session, user)
    return s.Page[s.ProductCardOut](
        items=sv.product_cards(session, rows, favs),
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.put("/{product_id}", response_model=s.Message, status_code=status.HTTP_200_OK)
def add_favorite(product_id: int, user: CurrentUser, session: SessionDep) -> s.Message:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    existing = session.exec(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.product_id == product_id)
    ).first()
    if existing is None:
        session.add(
            Favorite(user_id=user.id, product_id=product_id, price_when_added=product.price)
        )
        session.commit()
    return s.Message(message="Sevimlilarga qo'shildi")


@router.delete("/{product_id}", response_model=s.Message)
def remove_favorite(product_id: int, user: CurrentUser, session: SessionDep) -> s.Message:
    existing = session.exec(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.product_id == product_id)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
    return s.Message(message="Sevimlilardan olib tashlandi")
