from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import CartItem, Product, ProductVariant

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=s.CartOut, summary="Screens 17, 18 — cart")
def get_cart(user: CurrentUser, session: SessionDep, promo_code: str | None = None) -> s.CartOut:
    return sv.build_cart(session, user, promo_code)


@router.post("/items", response_model=s.CartOut, status_code=status.HTTP_201_CREATED)
def add_item(payload: s.CartAddIn, user: CurrentUser, session: SessionDep) -> s.CartOut:
    product = session.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    if not product.in_stock:
        raise HTTPException(status.HTTP_409_CONFLICT, "Mahsulot mavjud emas")
    if payload.variant_id is not None:
        variant = session.get(ProductVariant, payload.variant_id)
        if variant is None or variant.product_id != product.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Variant noto'g'ri")

    existing = session.exec(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == payload.variant_id,
        )
    ).first()

    if existing:
        existing.quantity = min(existing.quantity + payload.quantity, 99)
        session.add(existing)
    else:
        session.add(
            CartItem(
                user_id=user.id,
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                quantity=payload.quantity,
            )
        )
    session.commit()
    return sv.build_cart(session, user)


@router.patch("/items/{item_id}", response_model=s.CartOut, summary="Quantity stepper / select")
def update_item(
    item_id: int, payload: s.CartUpdateIn, user: CurrentUser, session: SessionDep
) -> s.CartOut:
    item = session.get(CartItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Savatda topilmadi")

    if payload.quantity is not None:
        if payload.quantity == 0:
            session.delete(item)
        else:
            item.quantity = payload.quantity
            session.add(item)
    if payload.selected is not None:
        item.selected = payload.selected
        session.add(item)

    session.commit()
    return sv.build_cart(session, user)


@router.delete("/items/{item_id}", response_model=s.CartOut)
def delete_item(item_id: int, user: CurrentUser, session: SessionDep) -> s.CartOut:
    item = session.get(CartItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Savatda topilmadi")
    session.delete(item)
    session.commit()
    return sv.build_cart(session, user)


@router.delete("", response_model=s.CartOut, summary="Empty the cart")
def clear_cart(user: CurrentUser, session: SessionDep) -> s.CartOut:
    for item in sv.cart_items(session, user):
        session.delete(item)
    session.commit()
    return sv.build_cart(session, user)


@router.post("/promo", response_model=s.CartOut, summary="Apply a promo code")
def apply_promo(payload: s.PromoIn, user: CurrentUser, session: SessionDep) -> s.CartOut:
    cart = sv.build_cart(session, user, payload.code)
    if cart.totals.promo_code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Promokod yaroqsiz")
    return cart
