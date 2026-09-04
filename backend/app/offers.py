"""Who wins, and what the product row says about it.

The catalogue used to be a shop: one price per product, in a column on the
product. It is a marketplace now, and the price belongs to a seller's offer.
Several sellers may offer the same thing, the cheapest one with stock wins,
and the shopper sees that one.

Which leaves the listings. Every one of them filters and sorts on price and
stock in SQL — ``min_price``, ``max_price``, ``discounted``, ``price_asc``,
``price_desc``, ``discount``, and ``in_stock`` on all of them — over a paged
query whose total is counted from the same statement. Answering those from the
offers table means a correlated subquery per row and paging computed on top of
it, for a figure that changes when a seller edits a price and at no other time.

So the winner's figures are copied onto the ``Product`` row and the listings go
on reading columns. That is a cache, and a cache is only ever as good as the
discipline around it, so there is exactly one function that writes it —
``refresh`` — and every place that can change an offer calls it. Nothing else
may assign to ``Product.price``, ``old_price``, ``stock_left``, ``in_stock``
or ``seller``, nor to ``ProductVariant.stock_left`` or ``in_stock``.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.models import (
    Offer,
    OfferVariant,
    Product,
    ProductVariant,
    Seller,
    VariantKind,
)

# --------------------------------------------------------------------------- winning


def offers_for(session: Session, product_id: int, *, active_only: bool = True) -> list[Offer]:
    """Every offer on a product, cheapest first.

    Ties break on the offer's own id, so "cheapest" is a total order and two
    sellers at the same price do not swap the card between them from one
    request to the next.
    """
    stmt = select(Offer).where(Offer.product_id == product_id)
    if active_only:
        stmt = stmt.where(Offer.active.is_(True))
    return list(session.exec(stmt.order_by(col(Offer.price), col(Offer.id))).all())


def winning_offer(session: Session, product_id: int) -> Offer | None:
    """The cheapest active offer with something left, or nothing.

    An offer with an empty shelf is not in the running — it is not a price
    anybody can pay, and letting it win would put a number on the card that
    cannot be bought at.
    """
    for offer in offers_for(session, product_id):
        if offer.stock_left > 0:
            return offer
    return None


def _price_to_show(session: Session, product_id: int) -> Offer | None:
    """The offer whose price the card shows when nothing is in stock.

    A sold-out card still has to print a figure — ``price`` is not nullable in
    the response, and a shopper looking at last week's listing should see what
    the thing costs, not a zero. So the cheapest active offer stands in, with
    the stock read as the nought it is.
    """
    offers = offers_for(session, product_id)
    return offers[0] if offers else None


# --------------------------------------------------------------------------- the cache


def refresh(session: Session, product_id: int) -> Product | None:
    """Recompute a product's cached price and stock from its offers.

    Called by everything that can change the answer: an offer created, edited,
    withdrawn, or drawn down by an order, and the same in reverse. Does not
    commit — the caller does, in the same transaction as the change that made
    it necessary, so the cache cannot be left describing an offer that was
    rolled back.
    """
    product = session.get(Product, product_id)
    if product is None:
        return None

    winner = winning_offer(session, product_id)
    shown = winner or _price_to_show(session, product_id)

    if shown is not None:
        product.price = shown.price
        product.old_price = shown.old_price
        seller = session.get(Seller, shown.seller_id)
        if seller is not None:
            product.seller = seller.name
    # With no offer at all the last known price stays put. Deleting every offer
    # on a product is not a statement about what it used to cost.

    product.stock_left = winner.stock_left if winner else 0
    product.in_stock = winner is not None
    session.add(product)

    _refresh_variants(session, product, winner)
    return product


def _refresh_variants(session: Session, product: Product, winner: Offer | None) -> None:
    """The same, one level down: each variant's count from the winner's shelf.

    A variant with no ``offer_variants`` row on the winning offer is one
    nobody counts apart, which is what ``None`` has always meant here — the
    product's own figure is the whole answer for it.
    """
    variants = session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all()
    if not variants:
        return

    counted: dict[int, int] = {}
    if winner is not None:
        counted = {
            row.variant_id: row.stock_left
            for row in session.exec(
                select(OfferVariant).where(OfferVariant.offer_id == winner.id)
            ).all()
        }

    for variant in variants:
        if variant.id in counted:
            variant.stock_left = counted[variant.id]
            variant.in_stock = counted[variant.id] > 0
        elif winner is None:
            # Nothing is on sale, so nothing is in stock — but a variant that
            # was never counted apart stays uncounted rather than becoming a
            # zero it never had.
            variant.in_stock = False
            if variant.stock_left is not None:
                variant.stock_left = 0
        else:
            variant.stock_left = None
            variant.in_stock = True
        session.add(variant)


def refresh_offer(session: Session, offer: Offer) -> Product | None:
    """Convenience for the common case: this offer moved, so recompute."""
    return refresh(session, offer.product_id)


# --------------------------------------------------------------------------- one offer's shelf


def variant_stock(session: Session, offer_id: int, variant_id: int | None) -> int | None:
    """How many of one variant this offer has, or ``None`` if uncounted."""
    if variant_id is None:
        return None
    row = session.exec(
        select(OfferVariant).where(
            OfferVariant.offer_id == offer_id, OfferVariant.variant_id == variant_id
        )
    ).first()
    return row.stock_left if row is not None else None


def shelf_left(
    session: Session,
    offer: Offer,
    color_variant_id: int | None = None,
    variant_id: int | None = None,
) -> int:
    """How many of the thing actually chosen this offer has left.

    The same rule as the product-level shelf, read off one seller's stock: a
    size is a cell of the colour × size grid and answers on its own; failing
    that the colour; failing that the offer as a whole.
    """
    size_left = variant_stock(session, offer.id, variant_id)
    if size_left is not None:
        return size_left
    color_left = variant_stock(session, offer.id, color_variant_id)
    if color_left is not None:
        return color_left
    return offer.stock_left


# --------------------------------------------------------------------------- adoption


def house_seller(session: Session, name: str = "Mini Bozor") -> Seller:
    """The shop itself, as a seller among sellers. Created once."""
    seller = session.exec(select(Seller).where(Seller.name == name)).first()
    if seller is None:
        seller = Seller(name=name, phone="+998781000000")
        session.add(seller)
        session.commit()
        session.refresh(seller)
    return seller


def mirror_catalogue(session: Session, seller: Seller) -> int:
    """Give every product an offer from this seller, copied off the product.

    The single-seller catalogue read as one offer all along — the price and the
    stock were on the product because there was only ever one of each. This
    reads them back out into the shape that can hold a second seller, and the
    figures come out the way they went in, so the apps see no change at all.

    Idempotent: a product that already has an offer from this seller is left
    alone, so it can be run again after new products are added.
    """
    made = 0
    products = session.exec(select(Product).order_by(col(Product.id))).all()
    for product in products:
        existing = session.exec(
            select(Offer).where(
                Offer.product_id == product.id, Offer.seller_id == seller.id
            )
        ).first()
        if existing is not None:
            continue

        offer = Offer(
            seller_id=seller.id,
            product_id=product.id,
            price=product.price,
            old_price=product.old_price,
            stock_left=product.stock_left,
            active=True,
        )
        session.add(offer)
        session.commit()
        session.refresh(offer)
        made += 1

        # Only the variants somebody counted apart. A ``None`` there has always
        # meant "the product's own shelf is the answer", and inventing a figure
        # for it would answer a question nobody asked.
        for variant in session.exec(
            select(ProductVariant).where(
                ProductVariant.product_id == product.id,
                col(ProductVariant.stock_left).is_not(None),
            )
        ).all():
            session.add(
                OfferVariant(
                    offer_id=offer.id,
                    variant_id=variant.id,
                    stock_left=variant.stock_left,
                )
            )
        session.commit()
    return made


# --------------------------------------------------------------------------- the shelf's shape


def leaf_variants(session: Session, product_id: int) -> list[ProductVariant]:
    """The rows a shelf is actually counted on.

    Sizes where there are sizes — a size is one cell of the colour × size grid
    and is the smallest thing anybody has one of — and colours where there are
    only colours. A product with neither is counted once, on the offer itself.
    """
    variants = session.exec(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(col(ProductVariant.sort), col(ProductVariant.id))
    ).all()
    sizes = [v for v in variants if v.kind == VariantKind.SIZE]
    return list(sizes) if sizes else [v for v in variants if v.kind == VariantKind.COLOR]


def roll_up(session: Session, offer: Offer) -> None:
    """Recompute an offer's totals from the counts underneath them.

    A colour holding four when its sizes hold one, one and one is a shelf that
    lies about itself, and so is an offer holding twelve when its colours hold
    ten. So neither total is ever set directly: a colour is the sum of its
    sizes and the offer is the sum of its colours, and the only figures anybody
    writes are the leaves.

    Left alone for a product with no variants — there the offer's own count *is*
    the leaf.
    """
    counts = {
        row.variant_id: row
        for row in session.exec(
            select(OfferVariant).where(OfferVariant.offer_id == offer.id)
        ).all()
    }
    if not counts:
        return

    variants = session.exec(
        select(ProductVariant).where(ProductVariant.product_id == offer.product_id)
    ).all()
    colors = [v for v in variants if v.kind == VariantKind.COLOR]
    sizes = [v for v in variants if v.kind == VariantKind.SIZE]

    for color in colors:
        children = [s for s in sizes if s.parent_id == color.id]
        if not children:
            continue
        row = counts.get(color.id)
        if row is not None:
            row.stock_left = sum(
                counts[c.id].stock_left for c in children if c.id in counts
            )
            session.add(row)

    if colors:
        offer.stock_left = sum(
            counts[c.id].stock_left for c in colors if c.id in counts
        )
    elif sizes:
        offer.stock_left = sum(
            counts[s.id].stock_left for s in sizes if s.id in counts
        )
    session.add(offer)
