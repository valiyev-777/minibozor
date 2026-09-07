from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from app import i18n
from app import offers as of
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import CurrentUser, SessionDep
from app.models import CartItem, Offer, Product, ProductVariant, VariantKind

router = APIRouter(prefix="/cart", tags=["cart"])


def _cap(
    session: Session,
    offer: Offer | None,
    product: Product,
    quantity: int,
    color: ProductVariant | None = None,
    size: ProductVariant | None = None,
    *,
    user_id: int | None = None,
) -> int:
    """How many of this the basket is allowed to hold.

    A backstop rather than the way the customer finds out: the stepper is given
    the same figure and stops its own plus button there. Ninety-nine was the
    only ceiling before, which is not a ceiling — it let the basket hold thirty
    of something there were three of, and the shortfall surfaced at checkout or
    not at all.

    The variants chosen are the shelf that counts: a basket holding six of a
    colour there are two of is the same shortfall one level down, and the same
    goes for a size. And the shelf is the seller's, not the catalogue's —
    holding three of something the chosen seller has one of is the same
    shortfall again, a level sideways. And less whatever somebody else is
    already holding — in their own basket, on an unpaid order, or picked for a
    seller to collect — because those goods are promised, not available.
    """
    if offer is not None:
        left = of.shelf_left(
            session,
            offer,
            color.id if color else None,
            size.id if size else None,
            for_user_id=user_id,
        )
    else:
        left = sv.shelf_left(product, color, size)
    return max(1, min(quantity, left)) if left else 1


def _chosen(
    session: Session, item: CartItem
) -> tuple[ProductVariant | None, ProductVariant | None]:
    """The colour and the size a cart line was added for."""
    return (
        session.get(ProductVariant, item.color_variant_id) if item.color_variant_id else None,
        session.get(ProductVariant, item.variant_id) if item.variant_id else None,
    )


def _require_a_leaf(
    session: SessionDep,
    product: Product,
    offer: Offer,
    color: ProductVariant | None,
    size: ProductVariant | None,
    color_id: int | None,
) -> None:
    """A basket line for a counted product has to say which one.

    The shelf of a product with variants is counted on its leaves — the sizes
    where there are sizes, the colours otherwise — and a sale that names none
    of them takes the count off the offer's total and off no leaf at all. The
    ledger still adds up, but the colour figures drift away from it by exactly
    that much, permanently: there is no working out afterwards which colour
    the shirt was. So the choice is required rather than defaulted, because
    guessing a colour on the customer's behalf is the same lie told earlier.

    Except when there is nothing to choose. Both apps send a leaf in the
    ordinary flow, and the one case they do not is a colour whose every size
    has gone — there the honest answer is that it is out of stock, which is
    also the answer they are written to expect.
    """
    leaves = of.leaf_variants(session, product.id)
    if not leaves:
        return

    by_colour = leaves[0].kind is VariantKind.COLOR
    named = color_id if by_colour else (size.id if size is not None else None)
    if named is not None:
        return

    candidates = [
        leaf
        for leaf in leaves
        if color is None or by_colour or leaf.parent_id == color.id
    ] or leaves
    if not any(st.sellable(session, offer, leaf.id) > 0 for leaf in candidates):
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock")
        )
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        i18n.label("choose_a_colour" if by_colour else "choose_a_size"),
    )


def _release(session: SessionDep, product_id: int | None) -> None:
    """Let go of a hold, by telling the card the shelf grew back.

    Nothing is deleted anywhere: a hold is derived from the basket line, so
    removing the line *is* the release. This only refreshes the cached figure
    that had been reduced by it.
    """
    if product_id is not None:
        of.refresh(session, product_id)
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
    color: ProductVariant | None = None
    size: ProductVariant | None = None
    for variant_id in (payload.variant_id, payload.color_variant_id):
        if variant_id is None:
            continue
        variant = session.get(ProductVariant, variant_id)
        if variant is None or variant.product_id != product.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("variant_invalid"))
        if not variant.in_stock:
            raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock"))
        if variant_id == payload.color_variant_id:
            color = variant
        else:
            size = variant

    # A size belongs to a colour, so the line is the pair of them.
    #
    # Sent on its own, the size says which colour it is a size of — a client
    # that only tracks the size still lands in the right line. Sent with a
    # colour that is not the one it belongs to, it is a pair this shop does not
    # stock, and quietly filing it under one of the two would sell something
    # nobody has.
    color_id = payload.color_variant_id
    if size is not None and size.parent_id is not None:
        if color is None:
            color = session.get(ProductVariant, size.parent_id)
            color_id = size.parent_id
        elif size.parent_id != color.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("variant_invalid"))

    # Whose offer this is. The cheapest with something left, which is the one
    # the card was showing — the product's own price is a copy of it.
    offer = of.winning_offer(session, product.id)
    if offer is None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("product_out_of_stock"))

    _require_a_leaf(session, product, offer, color, size, color_id)

    existing = session.exec(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.product_id == payload.product_id,
            CartItem.variant_id == payload.variant_id,
            CartItem.color_variant_id == color_id,
        )
    ).first()

    if existing:
        # The line keeps the offer it was opened with. Adding another of
        # something already in the basket is not a fresh decision about who to
        # buy it from, and re-pricing the line under the shopper would be.
        held = session.get(Offer, existing.offer_id) if existing.offer_id else offer
        existing.offer_id = existing.offer_id or offer.id
        existing.quantity = _cap(
            session,
            held,
            product,
            existing.quantity + payload.quantity,
            color,
            size,
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
                variant_id=payload.variant_id,
                color_variant_id=color_id,
                offer_id=offer.id,
                quantity=_cap(
                    session, offer, product, payload.quantity, color, size,
                    user_id=user.id,
                ),
                reserved_until=st.hold_until(),
            )
        )
    session.commit()
    # What the card says is the shelf less what is held, and this just held
    # some, so the card has to be told.
    of.refresh(session, product.id)
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
            offer = session.get(Offer, item.offer_id) if item.offer_id else None
            item.quantity = (
                _cap(
                    session,
                    offer,
                    product,
                    payload.quantity,
                    *_chosen(session, item),
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


@router.post("/promo", response_model=s.CartOut, summary="Apply a promo code")
def apply_promo(payload: s.PromoIn, user: CurrentUser, session: SessionDep) -> s.CartOut:
    cart = sv.build_cart(session, user, payload.code)
    if cart.totals.promo_code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("promo_invalid"))
    return cart
