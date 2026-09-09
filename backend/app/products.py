"""The figures on a card, which follow from its variants.

The price used to belong to an offer and the shelf to a seller. There is one
shelf now and one company standing behind it, so both come off the variants —
but the listings still filter and sort on price and availability in SQL, over a
paged query whose total is counted from the same statement. Answering that from
the variants row by row means a correlated subquery per card and paging
computed on top of it.

So two figures stay on ``Product`` as columns: ``price``, the cheapest of its
variants, and ``in_stock``, whether any of them has anything. They are derived,
and there is exactly one function that writes them — ``refresh`` — which
everything that can move a price or a count calls. Nothing else may assign to
``Product.price``, ``Product.old_price`` or ``Product.in_stock``.

How many there are is *not* one of them. That is a real stock figure and the
brief is plain that a product holds none: it is read from the variants, in one
grouped query for a whole page of cards.
"""

from __future__ import annotations

from sqlmodel import Session, col, func, select

from app import stock as st
from app.models import Product, ProductVariant, VariantKind

# --------------------------------------------------------------------------- leaves


def leaves(session: Session, product_id: int) -> list[ProductVariant]:
    """The variants a count actually sits on.

    A size where there are sizes, a colour where there are only colours. The
    two are the same goods counted at two depths — a colour row is the sum of
    its sizes — so anything that adds up stock has to pick one depth and stay
    on it.
    """
    rows = list(
        session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        ).all()
    )
    sizes = [v for v in rows if v.kind is VariantKind.SIZE]
    return sizes or rows


# --------------------------------------------------------------------------- the shelf


def on_shelf(session: Session, product_id: int) -> int:
    """How many of this thing there are, over every variant of it."""
    return shelf_map(session, [product_id]).get(product_id, 0)


def shelf_map(session: Session, product_ids: list[int]) -> dict[int, int]:
    """The same for a page of cards, in one query rather than twenty.

    Sizes only where a product has them: adding a colour to its own sizes
    would count the same shoes twice.
    """
    if not product_ids:
        return {}
    rows = session.exec(
        select(
            ProductVariant.product_id,
            ProductVariant.kind,
            func.coalesce(func.sum(ProductVariant.stock_left), 0),
        )
        .where(col(ProductVariant.product_id).in_(product_ids))
        .group_by(col(ProductVariant.product_id), col(ProductVariant.kind))
    ).all()

    by_kind: dict[int, dict[VariantKind, int]] = {}
    for product_id, kind, total in rows:
        by_kind.setdefault(product_id, {})[VariantKind(kind)] = int(total)

    shelf: dict[int, int] = {}
    for product_id in product_ids:
        kinds = by_kind.get(product_id, {})
        shelf[product_id] = kinds.get(
            VariantKind.SIZE, kinds.get(VariantKind.COLOR, 0)
        )
    return shelf


def shelf_left(
    session: Session,
    product: Product,
    color_variant_id: int | None = None,
    variant_id: int | None = None,
    *,
    for_user_id: int | None = None,
) -> int:
    """How many of the thing actually chosen can still be sold.

    A size is a cell of the colour × size grid and answers on its own; failing
    that the colour; failing that the product as a whole. Less whatever is
    already promised — except this shopper's own basket, because a stepper
    that stopped at what they are already holding would refuse to let them buy
    the thing they just picked up.
    """
    for candidate in (variant_id, color_variant_id):
        if candidate is None:
            continue
        variant = session.get(ProductVariant, candidate)
        if variant is not None and variant.product_id == product.id:
            return st.sellable(session, variant, for_user_id=for_user_id)

    return sum(
        st.sellable(session, v, for_user_id=for_user_id)
        for v in leaves(session, product.id)
    )


# --------------------------------------------------------------------------- the cache


def refresh(session: Session, product_id: int) -> Product | None:
    """Recompute a card's advertised price and availability from its variants.

    Called by everything that can change the answer: a variant priced, a sale,
    a receipt, a stocktake, and the same in reverse. Does not commit — the
    caller does, in the same transaction as the change that made it necessary,
    so the cache cannot be left describing something that rolled back.
    """
    product = session.get(Product, product_id)
    if product is None:
        return None

    rows = leaves(session, product_id)
    priced = [v.price for v in rows if v.price > 0]
    if priced:
        product.price = min(priced)
    # With nothing priced the last known price stays put. A card whose
    # variants have not been priced yet is not a card that costs nothing.

    ready = sum(st.sellable(session, v) for v in rows)
    product.in_stock = ready > 0
    session.add(product)
    return product
