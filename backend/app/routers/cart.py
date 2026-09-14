"""The basket.

One line is one variant — one cell of the colour × size grid — and that is the
whole of the change here. A line used to carry a colour id and a size id, and
the two could disagree: a pair the shop does not stock, filed under whichever
of the two was counted. There is one id now, and it points at the thing on the
shelf.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from app import i18n
from app import products as pr
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import CurrentUser, SessionDep
from app.models import CartItem, Product, ProductVariant

router = APIRouter(prefix="/cart", tags=["cart"])


def _cap(
    session: Session,
    product: Product,
    variant: ProductVariant | None,
    quantity: int,
    *,
    user_id: int | None = None,
) -> int:
    """How many of this the basket is allowed to hold.

    A backstop rather than the way the customer finds out: the stepper is given
    the same figure and stops its own plus button there. Ninety-nine was the
    only ceiling before, which is not a ceiling — it let the basket hold thirty
    of something there were three of, and the shortfall surfaced at checkout or
    not at all.

    Less whatever somebody else is already holding — in their own basket or
    promised to an order — because those goods are spoken for, not available.
    """
    left = pr.shelf_left(
        session,
        product,
        variant.id if variant else None,
        for_user_id=user_id,
    )
    return max(1, min(quantity, left)) if left else 1


def _chosen(session: Session, item: CartItem) -> ProductVariant | None:
    return (
        session.get(ProductVariant, item.variant_id) if item.variant_id else None
    )


def _require_a_variant(
    session: SessionDep, product: Product, variant: ProductVariant | None
) -> None:
    """A basket line for a card with variants has to name one.

    A sale that names none takes the count off nothing at all: the ledger
    still adds up, but the shelf never moves for it and there is no working
    out afterwards which colour the shirt was. So the choice is required
    rather than defaulted, because guessing on the customer's behalf is the
    same lie told earlier.

    Except when there is nothing to choose. Every card gets at least one
    variant, and one with a single unnamed cell is a product with no
    variation — there the id is filled in rather than demanded.
    """
    if variant is not None:
        return

    rows = pr.variants(session, product.id)
    if not rows:
        return
    if not any(st.sellable(session, row) > 0 for row in rows):
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock")
        )
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        i18n.label("choose_a_colour" if rows[0].colour else "choose_a_size"),
    )


def _only_variant(session: SessionDep, product: Product) -> ProductVariant | None:
    """The one cell of a card that has no real variation, if that is what it is."""
    rows = pr.variants(session, product.id)
    if len(rows) == 1 and not rows[0].colour and not rows[0].size:
        return rows[0]
    return None


def _release(session: SessionDep, product_id: int | None) -> None:
    """Let go of a hold, by telling the card the shelf grew back.

    Nothing is deleted anywhere: a hold is derived from the basket line, so
    removing the line *is* the release. This only refreshes the cached figure
    that had been reduced by it.
    """
    if product_id is not None:
        pr.refresh(session, product_id)
        session.commit()


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

    variant: ProductVariant | None = None
    if payload.variant_id is not None:
        variant = session.get(ProductVariant, payload.variant_id)
        if variant is None or variant.product_id != product.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("variant_invalid"))
        if st.sellable(session, variant, for_user_id=user.id) <= 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock")
            )
    else:
        variant = _only_variant(session, product)
    _require_a_variant(session, product, variant)

    existing = session.exec(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == (variant.id if variant else None),
        )
    ).first()

    if existing:
        existing.quantity = _cap(
            session,
            product,
            variant,
            existing.quantity + payload.quantity,
            user_id=user.id,
        )
        # Touched, so the hold starts again: somebody still shopping has not
        # abandoned anything.
        existing.reserved_until = st.hold_until()
        session.add(existing)
    else:
        session.add(
            CartItem(
                user_id=user.id,
                product_id=payload.product_id,
                variant_id=variant.id if variant else None,
                quantity=_cap(
                    session, product, variant, payload.quantity, user_id=user.id
                ),
                reserved_until=st.hold_until(),
            )
        )
    session.commit()
    # What the card says is the shelf less what is held, and this just held
    # some, so the card has to be told.
    pr.refresh(session, product.id)
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
            item.quantity = (
                _cap(
                    session,
                    product,
                    _chosen(session, item),
                    payload.quantity,
                    user_id=user.id,
                )
                if product
                else payload.quantity
            )
            item.reserved_until = st.hold_until()
            session.add(item)
    if payload.selected is not None:
        item.selected = payload.selected
        session.add(item)

    session.commit()
    _release(session, item.product_id)
    return sv.build_cart(session, user)


@router.delete("/items/{item_id}", response_model=s.CartOut)
def delete_item(item_id: int, user: CurrentUser, session: SessionDep) -> s.CartOut:
    item = session.get(CartItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("cart_item_not_found"))
    product_id = item.product_id
    session.delete(item)
    session.commit()
    _release(session, product_id)
    return sv.build_cart(session, user)


@router.delete("", response_model=s.CartOut, summary="Empty the cart")
def clear_cart(user: CurrentUser, session: SessionDep) -> s.CartOut:
    touched = {item.product_id for item in sv.cart_items(session, user)}
    for item in sv.cart_items(session, user):
        session.delete(item)
    session.commit()
    for product_id in touched:
        _release(session, product_id)
    return sv.build_cart(session, user)
