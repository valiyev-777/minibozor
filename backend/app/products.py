"""The figures on a card, which follow from its variants.

The price used to belong to an offer and the shelf to a seller. There is one
shelf now and one company standing behind it, so both come off the variants —
but the listings still filter and sort on price and availability in SQL, over a
paged query whose total is counted from the same statement. Answering that from
the variants row by row means a correlated subquery per card and paging
computed on top of it.

So two figures stay on ``Product`` as columns: ``price``, the cheapest of its
variants, and ``in_stock``, whether any of them can be sold. They are derived,
and there is exactly one function that writes them — ``refresh`` — which
everything that can move a price or a count calls. Nothing else may assign to
``Product.price``, ``Product.old_price`` or ``Product.in_stock``.

How many there are is *not* one of them. That is a real stock figure and a
product holds none: it is read from the variants, in one grouped query for a
whole page of cards.
"""

from __future__ import annotations

from sqlmodel import Session, col, func, select

from app import stock as st
from app.models import Product, ProductImage, ProductVariant

# --------------------------------------------------------------------------- variants


def variants(session: Session, product_id: int) -> list[ProductVariant]:
    """Every cell of the colour × size grid, in the order the form made them."""
    return list(
        session.exec(
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .order_by(col(ProductVariant.sort), col(ProductVariant.id))
        ).all()
    )


def colours(session: Session, product_id: int) -> list[str]:
    """The distinct colours this card comes in, in variant order.

    Derived rather than stored: a colour is not a row of its own any more — it
    is what a group of variants have in common — and a second table saying
    which colours exist would be a second thing to keep in step with them.
    """
    seen: list[str] = []
    for variant in variants(session, product_id):
        if variant.colour and variant.colour not in seen:
            seen.append(variant.colour)
    return seen


def colours_without_a_photograph(session: Session, product_id: int) -> list[str]:
    """Which colours have no picture — the reason a card is held back.

    Named rather than counted: a form that says "one colour is missing a
    photograph" leaves somebody opening all six to find out which. A card with
    no colours at all still needs one picture of the thing itself, and the
    empty string is what that picture is filed under.
    """
    photographed = {
        row.colour
        for row in session.exec(
            select(ProductImage).where(ProductImage.product_id == product_id)
        ).all()
    }
    wanted = colours(session, product_id) or [""]
    return [colour for colour in wanted if colour not in photographed]


# --------------------------------------------------------------------------- the shelf


def on_shelf(session: Session, product_id: int) -> int:
    """How many of this thing there are, over every variant of it."""
    return shelf_map(session, [product_id]).get(product_id, 0)


def shelf_map(session: Session, product_ids: list[int]) -> dict[int, int]:
    """The same for a page of cards, in one query rather than twenty."""
    if not product_ids:
        return {}
    rows = session.exec(
        select(
            ProductVariant.product_id,
            func.coalesce(func.sum(ProductVariant.stock_left), 0),
        )
        .where(col(ProductVariant.product_id).in_(product_ids))
        .group_by(col(ProductVariant.product_id))
    ).all()
    found = {int(product_id): int(total) for product_id, total in rows}
    return {product_id: found.get(product_id, 0) for product_id in product_ids}


def shelf_left(
    session: Session,
    product: Product,
    variant_id: int | None = None,
    *,
    for_user_id: int | None = None,
) -> int:
    """How many of the thing actually chosen can still be sold.

    A variant is one cell of the grid and answers on its own; without one the
    answer is the card as a whole, which is what a shopper who has chosen
    nothing yet is shown. Less whatever is already promised — except this
    shopper's own basket, because a stepper that stopped at what they are
    already holding would refuse to let them buy the thing they just picked up.
    """
    if variant_id is not None:
        variant = session.get(ProductVariant, variant_id)
        if variant is not None and variant.product_id == product.id:
            return st.sellable(session, variant, for_user_id=for_user_id)

    return sum(
        st.sellable(session, v, for_user_id=for_user_id)
        for v in variants(session, product.id)
    )


# --------------------------------------------------------------------------- the cache


def refresh(session: Session, product_id: int) -> Product | None:
    """Recompute a card's advertised price and availability from its variants.

    Called by everything that can change the answer: a variant priced, a
    receipt, a delivery, a stocktake, and the same in reverse. Does not commit
    — the caller does, in the same transaction as the change that made it
    necessary, so the cache cannot be left describing something that rolled
    back.
    """
    product = session.get(Product, product_id)
    if product is None:
        return None

    rows = variants(session, product_id)
    priced = [v.price for v in rows if v.price > 0]
    if priced:
        product.price = min(priced)
    # With nothing priced the last known price stays put. A card whose
    # variants have not been priced yet is not a card that costs nothing.

    product.in_stock = any(st.sellable(session, v) > 0 for v in rows)
    session.add(product)
    return product
