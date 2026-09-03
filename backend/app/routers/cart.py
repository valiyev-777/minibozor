from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app import i18n
from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import CartItem, Product, ProductVariant

router = APIRouter(prefix="/cart", tags=["cart"])


def _cap(product: Product, quantity: int) -> int:
    """How many of this the basket is allowed to hold.

    A backstop rather than the way the customer finds out: the stepper is given
    the same figure and stops its own plus button there. Ninety-nine was the
    only ceiling before, which is not a ceiling — it let the basket hold thirty
    of something there were three of, and the shortfall surfaced at checkout or
    not at all.
    """
    return max(1, min(quantity, product.stock_left)) if product.stock_left else 1


@router.get("", response_model=s.CartOut, summary="Screens 17, 18 — cart")
def get_cart(user: CurrentUser, session: SessionDep, promo_code: str | None = None) -> s.CartOut:
    return sv.build_cart(session, user, promo_code)


@router.post("/items", response_model=s.CartOut, status_code=status.HTTP_201_CREATED)
def add_item(payload: s.CartAddIn, user: CurrentUser, session: SessionDep) -> s.CartOut:
    product = session.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))
    if not product.in_stock:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock"))
    for variant_id in (payload.variant_id, payload.color_variant_id):
        if variant_id is None:
            continue
        variant = session.get(ProductVariant, variant_id)
        if variant is None or variant.product_id != product.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("variant_invalid"))

    existing = session.exec(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == payload.variant_id,
            CartItem.color_variant_id == payload.color_variant_id,
        )
    ).first()

    if existing:
        existing.quantity = _cap(product, existing.quantity + payload.quantity)
        session.add(existing)
    else:
        session.add(
            CartItem(
                user_id=user.id,
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                color_variant_id=payload.color_variant_id,
                quantity=_cap(product, payload.quantity),
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("cart_item_not_found"))

    if payload.quantity is not None:
        if payload.quantity == 0:
            session.delete(item)
        else:
            product = session.get(Product, item.product_id)
            item.quantity = _cap(product, payload.quantity) if product else payload.quantity
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("cart_item_not_found"))
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
