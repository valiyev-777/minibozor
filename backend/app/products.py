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
from app.models import (
    Product,
    ProductImage,
    ProductSpec,
    ProductVariant,
    SupplyLine,
)

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


def tidy_label(value: str) -> str:
    """One spelling per thing, so the desk's chips do not rot.

    The vocabulary is learned from what people type, which means it also learns
    their typos: a week in, the brand row read `nike`, `Nike` and `NIKE`, and
    the colour row `qora` beside `Oq`. Three chips for one brand is worse than
    no chips, because now somebody has to decide which one is the real one.

    So a value written in one case is capitalised and one written in mixed case
    is left exactly as it is — `nike` and `NIKE` both become `Nike`, and
    `On Cloud` stays `On Cloud` rather than being mangled into `On cloud`.
    """
    tidied = " ".join(value.split())
    if not tidied:
        return ""
    if tidied.islower() or tidied.isupper():
        return " ".join(word[:1].upper() + word[1:].lower() for word in tidied.split())
    return tidied


def ensure_cells(
    session: Session,
    product: Product,
    *,
    colour: str,
    colour_hex: str = "",
    sizes: list[str],
    price: int = 0,
) -> list[ProductVariant]:
    """The cells for one colour in the sizes that arrived, made if absent.

    **Adds; never renumbers and never deletes.** A pile of 44s turning up for
    a card that only had 41-43 writes one new cell and leaves the others
    exactly as they are — their prices, their counts, and above all their
    barcodes. A regenerated code would leave the shelf holding one thing under
    two of them.

    Returns the cells for the sizes asked about, in the order asked, so the
    caller can put a count against each without matching them up again.
    """
    existing = {(row.colour, row.size): row for row in variants(session, product.id)}
    sort = max((row.sort for row in existing.values()), default=-1) + 1

    made = False
    for size in sizes:
        if (colour, size) in existing:
            continue
        row = ProductVariant(
            product_id=product.id,
            colour=colour,
            colour_hex=colour_hex,
            size=size,
            price=price or product.price,
            sort=sort,
        )
        session.add(row)
        existing[(colour, size)] = row
        sort += 1
        made = True

    if made:
        session.commit()
        # The codes are ours and are only knowable once the row has an id.
        for row in variants(session, product.id):
            if not row.sku:
                row.sku = variant_sku(product, row)
            if not row.barcode:
                row.barcode = barcode(row.id)
            session.add(row)
        session.commit()
        existing = {
            (row.colour, row.size): row for row in variants(session, product.id)
        }

    return [existing[(colour, size)] for size in sizes]


def last_cost(session: Session, product_id: int) -> int:
    """What these last cost us, from the newest market run that named a cell.

    Not an average and not the cheapest: the price at the market moves, and
    what somebody pricing goods wants to know is what *this* lot cost. Zero
    when nothing has been booked in yet, which the caller shows as "unknown"
    rather than as free.
    """
    row = session.exec(
        select(SupplyLine.unit_cost)
        .join(ProductVariant, col(ProductVariant.id) == col(SupplyLine.variant_id))
        .where(ProductVariant.product_id == product_id, col(SupplyLine.unit_cost) > 0)
        .order_by(col(SupplyLine.id).desc())
        .limit(1)
    ).first()
    return int(row) if row else 0


def listing_gaps(session: Session, product_id: int) -> list[str]:
    """What a card is missing to look like a shop and not like a stub.

    Separate from ``unready`` on purpose. Those three — a category, a price, a
    photograph per colour — are refused: without them a card either cannot be
    found, cannot be charged for, or shows as a grey square. These are not
    refused, because a card with one photograph and no prose is a card somebody
    can still buy, and holding it back until the writing is done is how nothing
    ever goes on sale.

    So this is a to-do list rather than a gate. The apps hide a block whose
    field is empty — no description means no description panel, not an empty one
    — which is why a thin card looks sparse rather than broken, and why nobody
    would ever notice it needed finishing. Hence the list.
    """
    product = session.get(Product, product_id)
    if product is None:
        return []

    gaps: list[str] = []
    if not product.subtitle.strip():
        gaps.append("needs_subtitle")
    if not product.description.strip():
        gaps.append("needs_description")

    specs = session.exec(
        select(func.count())
        .select_from(ProductSpec)
        .where(ProductSpec.product_id == product_id)
    ).one()
    if not int(specs):
        gaps.append("needs_specs")

    # One photograph per colour publishes a card; a person deciding what to buy
    # swipes. Two per colour is the difference between a listing and a receipt.
    wanted = len(colours(session, product_id) or [""]) * 2
    shots = session.exec(
        select(func.count())
        .select_from(ProductImage)
        .where(ProductImage.product_id == product_id)
    ).one()
    if int(shots) < wanted:
        gaps.append("needs_more_photos")

    return gaps


# --------------------------------------------------------------------------- our codes


def next_sku(session: Session) -> str:
    """The next card code, ours because nothing else has one.

    Market goods arrive with no usable code — no label, no barcode — and two
    sacks of the same shoe from two traders would collide if they did. Nobody
    at a receiving desk should be inventing one either: a person asked to think
    up "KRS-01" with a sack open in front of them is a person who stops writing
    cards, which is how the flow stalled before.
    """
    used = session.exec(select(func.count()).select_from(Product)).one()
    return f"MB-{int(used) + 1:06d}"


def variant_sku(product: Product, variant: ProductVariant) -> str:
    """The card's code with the cell's on the end: ``MB-000124-QORA-42``.

    Readable on purpose. A picker reading a label wants to recognise the thing
    without decoding it, and a random string is a string somebody transcribes
    wrong when the printer is out of toner — or writes on the box with a
    marker, which is what happens here until there is a printer at all.
    """
    parts = [product.sku, variant.colour, variant.size]
    return "-".join(part.upper().replace(" ", "") for part in parts if part)


def barcode(variant_id: int) -> str:
    """Ours, and permanent.

    Generated from the row's own id and never regenerated: when the same goods
    arrive again the label is reprinted, or the shelf ends up holding one thing
    under two codes. ``200`` is the prefix reserved for in-store use, which is
    exactly what this is.
    """
    return f"200{variant_id:09d}"


def unready(session: Session, product_id: int) -> list[str]:
    """Everything that keeps this card out of the shop, named.

    Three gates, not one. A photograph was the first, and it turned out to be
    the easy one: a card written at the receiving desk with the sack open also
    has no category and no selling price, and either of those reaching a
    customer is worse than the card being invisible for another hour. Without
    a category nobody browsing can find it; without a price there is nothing
    to charge.

    Named rather than counted, for the same reason the colours are: a queue
    that says "3 cards are not ready" leaves somebody opening all three to
    find out what for. The strings are i18n labels, resolved by the caller.
    """
    product = session.get(Product, product_id)
    if product is None:
        return []

    gaps: list[str] = []
    if product.category_id is None:
        gaps.append("needs_category")
    if product.price <= 0:
        gaps.append("needs_price")
    missing = colours_without_a_photograph(session, product_id)
    if missing:
        gaps.append("needs_photo")
    return gaps


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
