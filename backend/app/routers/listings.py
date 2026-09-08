"""A seller's own product, opened and run by the seller.

This file exists because of a correction. The catalogue was built on the rule
that a card belongs to the platform: a seller could *propose* one, an admin
decided whether it existed, and the price was the only thing the seller
touched. That was a misreading, and it is the wrong shape for this shop.

**A seller owns their own product.** They open it, photograph it, price it,
and say what colours and sizes they have. What the warehouse confirms is not
that the listing is permitted — it is that **the goods turned up**. So the
sequence is one line, end to end:

    the seller adds a product, with its photographs
      → it arrives at the warehouse as a batch, marked as this seller's goods
      → the warehouse counts it in
      → it appears in the app
      → a customer buys one, and that size's stock goes down

Nothing underneath changes. A seller's product is still one ``Product`` with
one ``Offer`` — theirs — because that is what makes the price theirs to set
and the money theirs to be paid. The price still reaches the shop through
``offers.refresh``, and the stock still moves only through ``app.stock.move``:
the quantities in a request here become *declared* quantities on a supply
line, and the shelf does not move until somebody counts the box.

**Why one endpoint and not six.** Decomposed, this is: create the card, post
each image, post each colour, post each size, open the offer, declare the
batch. Six calls, each of which can be the last one that worked — leaving a
card with no pictures, or colours with no offer, or an offer with no batch,
and a seller looking at a half-made product with no way to tell which half.
Composed, it either happens or it does not.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, col, func, select

from app import audit, i18n
from app import offers as of
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import SellerUser, SessionDep
from app.models import (
    Brand,
    Category,
    Offer,
    OfferVariant,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    Seller,
    Supply,
    SupplyLine,
    SupplyStatus,
    User,
    UserRole,
    VariantKind,
)

router = APIRouter(prefix="/staff/catalog", tags=["staff"])


# --------------------------------------------------------------------------- create


@router.post(
    "/listings",
    response_model=s.SellerListingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add my product — pictures, price, colours, sizes and the batch",
)
def create_listing(
    payload: s.ListingCreateIn, user: SellerUser, session: SessionDep
) -> s.SellerListingOut:
    """One request, and at the end of it the warehouse is expecting a box.

    What it writes, in order, and why each piece belongs to somebody:

    1. the ``Product`` — the seller's, recorded in ``proposed_by_id``, so
       every screen that asks "whose is this" has an answer;
    2. its ``ProductImage`` rows in the order given, first one primary;
    3. a ``ProductVariant`` per colour, and one per size *under* each colour —
       a size is a cell of the grid, not a row beside it;
    4. one ``Offer``, this seller's, at their price, with an ``OfferVariant``
       per variant so the per-colour figures survive when this offer wins;
    5. one ``Supply``, declared, with a line per countable cell.

    The card is left ``moderating`` and that word now means one thing: the
    goods have not been counted in yet. Receiving the batch publishes it —
    see ``app.routers.warehouse.receive_supply``.

    Nothing here touches a stock figure. Every quantity becomes
    ``SupplyLine.declared_quantity``; the shelf follows the ledger.
    """
    seller = _own_seller(session, user)
    category = _category(session, payload.category_slug)
    brand = _brand(session, payload.brand_slug) if payload.brand_slug else None

    if not payload.images:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("images_required"))
    _sizes_are_consistent(payload)
    _colours_have_photographs(payload.colors)

    product = Product(
        # The seller does not think in SKUs and should not have to invent a
        # unique one. Ours, from the id, once there is an id.
        sku="",
        title=payload.title.strip(),
        subtitle=payload.subtitle.strip(),
        description=payload.description.strip(),
        category_id=category.id,
        brand_id=brand.id if brand else None,
        # A cache, seeded so a card with no offer yet has a number rather than
        # a nought; `offers.refresh` overwrites it the moment the offer exists.
        price=payload.price,
        old_price=payload.old_price,
        weight_grams=payload.weight_grams,
        stock_left=0,
        in_stock=False,
        status=ProductStatus.MODERATING,
        proposed_by_id=seller.id,
        seller=seller.name,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    product.sku = f"S{seller.id:03d}-{product.id:05d}"
    session.add(product)

    for order, path in enumerate(payload.images):
        session.add(ProductImage(product_id=product.id, url=path, sort=order))

    # The variants. Colours first so a size has a parent to point at.
    leaves: list[tuple[ProductVariant, str, str | None, int]] = []
    for c_order, colour in enumerate(payload.colors):
        swatch = ProductVariant(
            product_id=product.id,
            kind=VariantKind.COLOR,
            label=colour.label.strip(),
            value=(colour.value or colour.label).strip(),
            image_url=colour.image_url,
            sort=c_order,
            # Counted by the offers that carry it, never here.
            stock_left=None,
            in_stock=True,
        )
        session.add(swatch)
        session.commit()
        session.refresh(swatch)

        if not colour.sizes:
            # No sizes: the colour is the cell that gets counted, and its own
            # `quantity` is what is coming. This used to be a hard nought,
            # which meant a seller of bags submitted a card and the warehouse
            # was expecting no box.
            leaves.append((swatch, swatch.label, None, colour.quantity))
            continue

        for s_order, size in enumerate(colour.sizes):
            cell = ProductVariant(
                product_id=product.id,
                kind=VariantKind.SIZE,
                label=size.label.strip(),
                value=(size.value or size.label).strip(),
                parent_id=swatch.id,
                sort=s_order,
                stock_left=None,
                in_stock=True,
            )
            session.add(cell)
            session.commit()
            session.refresh(cell)
            leaves.append((cell, swatch.label, cell.label, size.quantity))
    session.commit()

    offer = Offer(
        seller_id=seller.id,
        product_id=product.id,
        price=payload.price,
        old_price=payload.old_price,
        # Nothing on the shelf until the warehouse books something in.
        stock_left=0,
        active=True,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)

    # A row per variant, not only per leaf: a colour with no row on the winning
    # offer reads as uncounted, and the product page would lose its per-colour
    # figures the moment this offer won.
    for variant in session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all():
        session.add(
            OfferVariant(offer_id=offer.id, variant_id=variant.id, stock_left=0)
        )
    session.commit()

    supply = _declare(session, seller, offer, leaves)

    audit.record(
        session,
        actor=user,
        action="listing.create",
        entity="product",
        entity_id=product.id,
        field="status",
        old=None,
        new=ProductStatus.MODERATING,
        note=f"{seller.name} · {product.title} · {supply.code if supply else 'partiyasiz'}",
    )
    session.commit()

    of.refresh(session, product.id)
    session.commit()
    session.refresh(product)
    return _listing_out(session, product, seller)


def _declare(
    session: Session,
    seller: Seller,
    offer: Offer,
    leaves: list[tuple[ProductVariant, str, str | None, int]],
) -> Supply | None:
    """The batch the warehouse will be looking for.

    Only the cells the seller says they are sending: a line declaring nought
    is not a promise, and the warehouse counting a box that was never coming
    is how a declaration stops meaning anything.
    """
    coming = [(variant, qty) for variant, _c, _s, qty in leaves if qty > 0]
    if not coming:
        return None

    used = session.exec(select(func.count()).select_from(Supply)).one()
    supply = Supply(
        code=f"SUP-{int(used) + 1:06d}",
        seller_id=seller.id,
        note="",
    )
    session.add(supply)
    session.commit()
    session.refresh(supply)

    for variant, quantity in coming:
        session.add(
            SupplyLine(
                supply_id=supply.id,
                offer_id=offer.id,
                variant_id=variant.id,
                declared_quantity=quantity,
            )
        )
    session.commit()
    return supply


# ----------------------------------------------------------------------- read


@router.get(
    "/listings",
    response_model=list[s.SellerListingOut],
    summary="My products, and where each of them has got to",
)
def list_listings(
    user: SellerUser, session: SessionDep
) -> list[s.SellerListingOut]:
    """Every product this seller opened, whatever became of it.

    Including the refusals, with the reason. A seller whose product was
    refused and cannot read why is being asked to fix something without being
    told what is wrong with it — which was the state of things before this
    screen existed.
    """
    seller = _own_seller(session, user)
    rows = session.exec(
        select(Product)
        .where(Product.proposed_by_id == seller.id)
        .order_by(col(Product.created_at).desc(), col(Product.id).desc())
    ).all()
    return [_listing_out(session, row, seller) for row in rows]


@router.get(
    "/listings/{product_id}",
    response_model=s.SellerListingOut,
    summary="One of my products",
)
def get_listing(
    product_id: int, user: SellerUser, session: SessionDep
) -> s.SellerListingOut:
    seller = _own_seller(session, user)
    product = session.get(Product, product_id)
    if product is None or product.proposed_by_id != seller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))
    return _listing_out(session, product, seller)


@router.patch(
    "/listings/{product_id}",
    response_model=s.SellerListingOut,
    summary="Fix my own card — its words, its shelf, its photographs",
)
def edit_listing(
    product_id: int,
    payload: s.ListingEditIn,
    user: SellerUser,
    session: SessionDep,
) -> s.SellerListingOut:
    """A seller's own card, corrected by the seller.

    This did not exist, and its absence was the reason a seller who mistyped a
    name had nothing to do about it: the only editable thing on their product
    was the price, and every other field belonged to an admin's screen. A shop
    where fixing a typo means asking somebody at head office is a shop whose
    cards stay wrong.

    **Theirs and only theirs**, matched on ``proposed_by_id``, and a 404 rather
    than a 403 for somebody else's product: which cards exist in another
    seller's shop is not a fact we owe them.

    Allowed in every stage, including ``on_sale``. A card in the shop with the
    wrong description is worse than one being edited, and the alternative —
    withdraw, fix, resubmit, wait for a recount — would mean nobody ever fixes
    anything. A refused card is the case this matters most for: the refusal
    reason says what to fix and this is the door to fix it through.

    What it does not touch: the price, the stock, the status, and the colours.
    The first three have owners of their own. The colours are the goods
    themselves — a colour is a row on a shelf with a count against it, so
    adding or removing one is a supply or a removal, not an edit.
    """
    seller = _own_seller(session, user)
    product = session.get(Product, product_id)
    if product is None or product.proposed_by_id != seller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    if payload.category_slug is not None:
        product.category_id = _category(session, payload.category_slug).id

    for field in ("title", "subtitle", "description"):
        value = getattr(payload, field)
        if value is not None:
            setattr(product, field, value.strip())
    if payload.weight_grams is not None:
        product.weight_grams = payload.weight_grams

    if payload.images is not None:
        # A card with no picture is a card nobody taps, which is the same rule
        # creation has — so an edit may reorder and replace the list but not
        # empty it.
        if not payload.images:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("images_required")
            )
        for row in session.exec(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).all():
            session.delete(row)
        for order, path in enumerate(payload.images):
            session.add(ProductImage(product_id=product.id, url=path, sort=order))

    audit.record(
        session,
        actor=user,
        action="listing.edit",
        entity="product",
        entity_id=product.id,
        field="listing",
        old=None,
        new=", ".join(
            name
            for name in ("title", "subtitle", "description", "category_slug",
                         "weight_grams", "images")
            if getattr(payload, name) is not None
        ),
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return _listing_out(session, product, seller)


@router.post(
    "/listings/{product_id}/variants",
    response_model=s.SellerListingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a colour or a size to my own card, and the goods with it",
)
def add_variants(
    product_id: int,
    payload: s.ListingVariantsIn,
    user: SellerUser,
    session: SessionDep,
) -> s.SellerListingOut:
    """A colour or a size the card did not have, and a batch on its way.

    This did not exist, and its absence was the sharpest edge on the seller's
    side: a shop that started selling a shirt in black and later got it in blue
    had to open a **second card** for the blue one — a second set of
    photographs, a second price to keep in step, and two rows in the shop for
    one thing. The only thing "add more" could do was send another box of a
    colour that already existed.

    **Creating the variant and declaring the goods is one act.** A colour with
    no supply is a swatch a customer can tap and never buy; a supply for a
    variant that does not exist is not expressible. Two endpoints would leave
    both halves reachable on their own, and one of the two would be somebody's
    afternoon.

    Existing labels are reused rather than refused. A seller adding `XL` to
    black and blue sends both colours with all their sizes — that is what the
    form in front of them looks like — and only the parts that are new get
    written. So this is safe to send twice, which matters because the seller's
    screen is the same one they add a plain restock from.

    A new colour needs its own photograph, for the same reason creation does:
    the shopper's page swaps the hero when a swatch is tapped.
    """
    seller = _own_seller(session, user)
    product = session.get(Product, product_id)
    if product is None or product.proposed_by_id != seller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    offer = session.exec(
        select(Offer)
        .where(Offer.product_id == product.id)
        .where(Offer.seller_id == seller.id)
    ).first()
    if offer is None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("offer_missing"))

    existing = session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all()
    colours = {v.label.strip().casefold(): v for v in existing if v.kind is VariantKind.COLOR}

    # Only the colours that are actually new need a photograph. Demanding one
    # for a colour already on the card would mean re-uploading its picture to
    # add a size to it.
    _colours_have_photographs(
        [c for c in payload.colors if c.label.strip().casefold() not in colours]
    )

    leaves: list[tuple[ProductVariant, str, str | None, int]] = []
    made = 0
    for colour in payload.colors:
        key = colour.label.strip().casefold()
        swatch = colours.get(key)
        if swatch is None:
            swatch = ProductVariant(
                product_id=product.id,
                kind=VariantKind.COLOR,
                label=colour.label.strip(),
                value=(colour.value or colour.label).strip(),
                image_url=colour.image_url,
                sort=max((v.sort for v in existing if v.kind is VariantKind.COLOR), default=-1) + 1,
                stock_left=None,
                in_stock=True,
            )
            session.add(swatch)
            session.commit()
            session.refresh(swatch)
            colours[key] = swatch
            made += 1
            session.add(OfferVariant(offer_id=offer.id, variant_id=swatch.id, stock_left=0))
            session.commit()

        if not colour.sizes:
            leaves.append((swatch, swatch.label, None, colour.quantity))
            continue

        # A colour with nothing under it is counted on itself, so putting
        # sizes under it moves the count a level down from where the ledger
        # already put it — and there is no honest way to say how eight black
        # shirts divide between an S and an M nobody has counted. This rule
        # came off the admin's variant door when that door was removed; it is
        # the seller's door now, and the rule belongs with it.
        counted = session.exec(
            select(OfferVariant)
            .where(OfferVariant.offer_id == offer.id)
            .where(OfferVariant.variant_id == swatch.id)
        ).first()
        has_sizes = session.exec(
            select(ProductVariant).where(ProductVariant.parent_id == swatch.id)
        ).first()
        if has_sizes is None and counted is not None and counted.stock_left > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT, i18n.label("variant_would_move_the_count")
            )

        under = {
            v.label.strip().casefold(): v
            for v in session.exec(
                select(ProductVariant).where(ProductVariant.parent_id == swatch.id)
            ).all()
        }
        for size in colour.sizes:
            cell = under.get(size.label.strip().casefold())
            if cell is None:
                cell = ProductVariant(
                    product_id=product.id,
                    kind=VariantKind.SIZE,
                    label=size.label.strip(),
                    value=(size.value or size.label).strip(),
                    parent_id=swatch.id,
                    sort=len(under),
                    stock_left=None,
                    in_stock=True,
                )
                session.add(cell)
                session.commit()
                session.refresh(cell)
                under[size.label.strip().casefold()] = cell
                made += 1
                session.add(
                    OfferVariant(offer_id=offer.id, variant_id=cell.id, stock_left=0)
                )
                session.commit()
            leaves.append((cell, swatch.label, cell.label, size.quantity))

    if made == 0 and not any(qty > 0 for _v, _c, _s, qty in leaves):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("nothing_new"))

    supply = _declare(session, seller, offer, leaves)

    audit.record(
        session,
        actor=user,
        action="listing.variants",
        entity="product",
        entity_id=product.id,
        field="variants",
        old=len(existing),
        new=len(existing) + made,
        note=supply.code if supply else "",
    )
    session.commit()
    of.refresh(session, product.id)
    session.commit()
    session.refresh(product)
    return _listing_out(session, product, seller)


# -------------------------------------------------------------------- helpers


def _colours_have_photographs(colours: list[s.ListingColorIn]) -> None:
    """A colour without a photograph is not a colour anybody can choose.

    The shopper's page swaps the picture when a colour is tapped — that is the
    whole point of having colours on a card. A swatch with no picture behind it
    leaves the hero showing the previous colour, so the customer taps "black",
    sees a white shirt, and either buys the wrong thing or does not buy. The
    hex circle is a label for the picture, not a substitute for it.

    So the rule is the same one the card itself has for images: it is refused
    at the door rather than accepted and worked around downstream. Which
    colour is named, because a seller with eight of them should not have to
    guess which one the message is about.
    """
    missing = [c.label.strip() for c in colours if not (c.image_url or "").strip()]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            i18n.label("colour_needs_photo", colours=", ".join(missing)),
        )


def _sizes_are_consistent(payload: s.ListingCreateIn) -> None:
    """Either every colour has sizes or none does.

    A product is counted on its leaves, and mixing the two levels puts some of
    the counts a level above where the ledger looks for them — with no way to
    say how a colour's stock divides between sizes it does not have. The
    warehouse invariant that an offer's total equals the sum of its colours,
    and a colour the sum of its sizes, is the thing that would quietly stop
    holding.
    """
    if not payload.colors:
        return
    sized = [bool(c.sizes) for c in payload.colors]
    if any(sized) and not all(sized):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("sizes_all_or_none")
        )
    for colour in payload.colors:
        labels = [size.label.strip().lower() for size in colour.sizes]
        if len(labels) != len(set(labels)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("sizes_repeat")
            )
    names = [c.label.strip().lower() for c in payload.colors]
    if len(names) != len(set(names)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("colors_repeat"))


def _own_seller(session: Session, user: User) -> Seller:
    """The shop this account acts for.

    An admin has none, and this is a seller's door: everything behind it is
    scoped to one shop, and an admin arriving here would be scoped to nothing
    — which means every shop's products, on a screen written for one.
    """
    if user.role is UserRole.ADMIN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("admin_has_no_seller")
        )
    row = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
    if row is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
        )
    return row


def _category(session: Session, slug: str) -> Category:
    row = session.exec(select(Category).where(Category.slug == slug)).first()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("category_not_found")
        )
    return row


def _brand(session: Session, slug: str) -> Brand:
    row = session.exec(select(Brand).where(Brand.slug == slug)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("brand_not_found"))
    return row


def _stage(
    session: Session, product: Product, offer: Offer | None, supply: Supply | None
) -> str:
    """Where this product has got to, as one word.

    Derived, not stored, because it is a statement about two rows — the card's
    status and the batch behind it — and neither of them owns it. Storing it
    would mean a third place that can disagree with the other two.
    """
    if product.status is ProductStatus.REJECTED:
        return "rejected"
    if product.status is ProductStatus.ARCHIVED:
        return "archived"
    if product.status is ProductStatus.PUBLISHED:
        sellable = st.sellable(session, offer) if offer else 0
        return "on_sale" if sellable > 0 else "sold_out"
    # Still not in the shop: the question is whether the goods have arrived.
    if supply is not None and supply.status is SupplyStatus.RECEIVED:
        return "in_warehouse"
    return "awaiting_warehouse"


def _listing_out(
    session: Session, product: Product, seller: Seller
) -> s.SellerListingOut:
    offer = session.exec(
        select(Offer).where(
            Offer.product_id == product.id, Offer.seller_id == seller.id
        )
    ).first()

    supply = None
    if offer is not None:
        supply = session.exec(
            select(Supply)
            .join(SupplyLine, col(SupplyLine.supply_id) == col(Supply.id))
            .where(SupplyLine.offer_id == offer.id)
            .order_by(col(Supply.declared_at).desc())
        ).first()

    declared: dict[int, int] = {}
    if supply is not None:
        for line in session.exec(
            select(SupplyLine).where(SupplyLine.supply_id == supply.id)
        ).all():
            if line.variant_id is not None:
                declared[line.variant_id] = line.declared_quantity

    # One row per countable cell, named the way the seller entered it.
    colours = {
        row.id: row
        for row in session.exec(
            select(ProductVariant).where(
                ProductVariant.product_id == product.id,
                ProductVariant.kind == VariantKind.COLOR,
            )
        ).all()
    }
    cells: list[s.ListingStockOut] = []
    on_hand_total = 0
    sellable_total = 0
    for variant in of.leaf_variants(session, product.id):
        parent = colours.get(variant.parent_id) if variant.parent_id else None
        on_hand = 0
        sellable = 0
        if offer is not None:
            row = session.exec(
                select(OfferVariant).where(
                    OfferVariant.offer_id == offer.id,
                    OfferVariant.variant_id == variant.id,
                )
            ).first()
            on_hand = row.stock_left if row else 0
            sellable = st.sellable(session, offer, variant.id)
        on_hand_total += on_hand
        sellable_total += sellable
        cells.append(
            s.ListingStockOut(
                variant_id=variant.id,
                color_label=(parent.label if parent else variant.label),
                size_label=variant.label if parent else None,
                declared=declared.get(variant.id, 0),
                on_hand=on_hand,
                sellable=sellable,
            )
        )

    if not cells and offer is not None:
        # A product with no variants at all is counted on the offer itself.
        on_hand_total = offer.stock_left
        sellable_total = st.sellable(session, offer)

    stage = _stage(session, product, offer, supply)
    category = session.get(Category, product.category_id)
    images = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product.id)
        .order_by(col(ProductImage.sort), col(ProductImage.id))
    ).all()

    return s.SellerListingOut(
        id=product.id,
        sku=product.sku,
        title=product.title,
        subtitle=product.subtitle,
        status=product.status,
        stage=stage,
        stage_label=i18n.label(f"stage_{stage}"),
        moderation_note=product.moderation_note,
        category_slug=category.slug if category else "",
        price=offer.price if offer else product.price,
        old_price=offer.old_price if offer else product.old_price,
        images=[sv.media_url(row.url) for row in images],
        offer_id=offer.id if offer else None,
        supply_code=supply.code if supply else None,
        supply_status=supply.status if supply else None,
        stock=cells,
        on_hand_total=on_hand_total,
        sellable_total=sellable_total,
        created_at=product.created_at,
    )
