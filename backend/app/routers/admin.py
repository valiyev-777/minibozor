"""The catalogue — the admin's side.

Until now nothing could write to the catalogue at all: a product, a category,
a brand arrived through ``seed.py`` and nowhere else, which meant adding one
took a developer.

Two decisions run through this file.

**The catalogue is the company's, and there is only one company.** A card is
written here or at the receiving desk while a sack is being sorted; there is
nobody outside to propose one and nothing to moderate.

**Three things about a card are not the edit form's to set.** Its price
belongs to its variants, its stock to the movement ledger, and its status to
whether every colour it has carries a photograph. So none of them is in the
edit shape, and each has its own door.

**A card is written in three languages or it is written badly.** The apps ask
for Uzbek, Russian or English; a row carries its Uzbek and the ``translation``
table carries the other two. Every write here takes them together, because a
translation asked for as a second step is a translation nobody does — and
every delete takes them with it, because SQLite hands a deleted row's id back
out again. See ``app.i18n`` for both halves.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, brands, colours, i18n
from app import products as pr
from app import schemas as s
from app import services as sv
from app import sizes
from app import stock as st
from app import transitions as tr
from app.deps import AdminUser, CatalogReader, CatalogWriter, SessionDep
from app.models import (
    Brand,
    BrandAlias,
    Category,
    Colour,
    OrderItem,
    Product,
    ProductImage,
    ProductSpec,
    ProductStatus,
    ProductVariant,
    SizeSystem,
    SizeValue,
    StockMovement,
    User,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- the catalogue


@router.get(
    "/products",
    response_model=s.Page[s.AdminProductOut],
    summary="Every card, whatever its state",
)
def list_products(
    # The receiving desk reads this all evening: the product field on the
    # sorting screen searches the existing cards first, and a bench that
    # cannot search them writes a third new card for goods that already have
    # one — which is how a catalogue rots.
    user: CatalogReader,
    session: SessionDep,
    status_filter: ProductStatus | None = Query(
        None, alias="status", description="`draft` is what is held back from sale"
    ),
    q: str | None = Query(None),
    stock: Literal["out", "low"] | None = Query(
        None,
        description="`out`: a live card with an empty cell. `low`: one nearly empty",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.AdminProductOut]:
    stmt = select(Product)
    if status_filter is not None:
        stmt = stmt.where(Product.status == status_filter)
    if stock is not None:
        # A card, not a cell: the office works through cards, and a card with
        # one empty colour is one thing to go and deal with rather than four
        # rows of the same name. The dashboard tile lands here — it used to
        # link to `?low=1`, which nothing read, so the count was right and the
        # list you were sent to was the whole catalogue.
        empty = select(ProductVariant.product_id).where(
            ProductVariant.stock_left <= 0
            if stock == "out"
            else col(ProductVariant.stock_left).between(1, pr.LOW_STOCK)
        )
        stmt = stmt.where(col(Product.id).in_(empty))
        if stock == "out":
            # Only what the shop is offering. A draft with empty cells is a
            # card somebody has not finished, which is a different queue.
            stmt = stmt.where(Product.status == ProductStatus.ACTIVE)
    if q:
        # Every word, in any order, in the title or the code. A single LIKE on
        # the whole phrase missed "krossovka nike" against
        # "Krossovka · Nike · Qora" — the separators sit between the words —
        # which is exactly the search somebody types when they are checking
        # whether a card already exists before writing a second one.
        for word in q.lower().split():
            needle = f"%{word}%"
            stmt = stmt.where(
                func.lower(Product.title).like(needle)
                | func.lower(Product.sku).like(needle)
            )
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    # Oldest first when it is a queue of cards waiting on a photograph, newest
    # first when it is a catalogue.
    order = (
        col(Product.created_at)
        if status_filter is ProductStatus.DRAFT
        else col(Product.created_at).desc()
    )
    rows = session.exec(
        stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return s.Page[s.AdminProductOut](
        items=[sv.admin_product_out(session, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get(
    "/products/summary",
    response_model=s.CatalogSummaryOut,
    summary="How many cards are in each state",
)
def catalog_summary(user: AdminUser, session: SessionDep) -> s.CatalogSummaryOut:
    """For the badge that counts what is held back from sale.

    A sidebar that wants to say "3 waiting" should not have to fetch the queue
    to find out — that is a page of cards downloaded to render an integer, on
    every screen, because the sidebar is on every screen.
    """
    rows = session.exec(
        select(Product.status, func.count()).group_by(col(Product.status))
    ).all()
    counts = {status_: 0 for status_ in ProductStatus}
    for status_, count in rows:
        counts[status_] = int(count)
    return s.CatalogSummaryOut(counts=counts)


@router.get("/products/{product_id}", response_model=s.AdminProductDetailOut)
def get_product(
    product_id: int, user: CatalogReader, session: SessionDep
) -> s.AdminProductDetailOut:
    """One card, with the fields only the edit form needs.

    The list shape stays as it was — a description per row is prose fetched to
    draw a table — so this is the richer of the two, on the endpoint an editor
    calls one card at a time.
    """
    product = _product(session, product_id)
    return s.AdminProductDetailOut(
        **sv.admin_product_out(session, product).model_dump(),
        description=product.description,
        badge=product.badge,
        warranty=product.warranty,
        is_original=product.is_original,
        free_delivery=product.free_delivery,
        next_day_delivery=product.next_day_delivery,
        translations=i18n.stored(session, "product", product.id),
    )


@router.post(
    "/products",
    response_model=s.AdminProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Write a card",
)
def create_product(
    # Written at the desk as often as at the office: a pile out of a sack that
    # matches no existing card is a card somebody writes with the goods in
    # front of them, which is the only moment anybody knows what they are.
    payload: s.ProductCreateIn, user: CatalogReader, session: SessionDep
) -> s.AdminProductOut:
    """A new card, held back from sale until it has a photograph.

    Always a draft, whoever writes it: the rule is that a card with no picture
    does not reach the apps, and a door that let one straight into the shop
    would be a way round the rule rather than an exception to it.
    """
    return _create_card(session, user, payload, ProductStatus.DRAFT)


def _create_card(
    session: SessionDep,
    actor: User,
    payload: s.ProductCreateIn,
    state: ProductStatus,
) -> s.AdminProductOut:
    sku = payload.sku.strip().upper() or pr.next_sku(session)
    if session.exec(select(Product).where(Product.sku == sku)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("sku_exists"))
    category = _category(session, payload.category_slug) if payload.category_slug else None
    brand = _brand(session, payload.brand_slug) if payload.brand_slug else None

    product = Product(
        sku=sku,
        title=payload.title,
        subtitle=payload.subtitle,
        description=payload.description,
        kind=payload.kind.strip(),
        snapshot_url=payload.snapshot_url,
        category_id=category.id if category else None,
        brand_id=brand.id if brand else None,
        # What the card is advertised at until it has priced variants, which
        # `products.refresh` takes over from. The money a shopper pays is on
        # the variant.
        price=payload.price,
        old_price=payload.old_price,
        badge=payload.badge,
        warranty=payload.warranty,
        is_original=payload.is_original,
        free_delivery=payload.free_delivery,
        next_day_delivery=payload.next_day_delivery,
        # Nothing on the shelf until the warehouse books something in.
        in_stock=False,
        status=state,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    i18n.write(session, "product", product.id, _texts(payload.translations))

    audit.record(
        session,
        actor=actor,
        action="product.create",
        entity="product",
        entity_id=product.id,
        field="status",
        old=None,
        new=state,
        note=f"{product.sku} · {product.title}",
    )
    session.commit()
    session.refresh(product)
    return sv.admin_product_out(session, product)


@router.delete("/products/{product_id}", response_model=s.Message)
def delete_product(
    product_id: int, user: AdminUser, session: SessionDep
) -> s.Message:
    """A card with no history, gone. A card with history, archived.

    Nothing here could remove a card at all, so a mistake written at the
    receiving desk — a duplicate, a typo, goods that turned out to be something
    else — stayed in the catalogue for ever with `draft` as the only way to
    hide it.

    **The line is history, not status.** A card that has never been booked in
    and never been ordered is a piece of writing somebody got wrong, and it
    goes. A card with a stock movement or an order line against it is part of
    what happened here: deleting it would leave an order naming a product that
    does not exist, and a ledger with a hole in it. That one is archived — out
    of the shop, still answerable — and the caller is told which of the two it
    got.
    """
    product = _product(session, product_id)
    variants = pr.variants(session, product.id)
    ids = [v.id for v in variants]

    moved = ids and session.exec(
        select(StockMovement).where(col(StockMovement.variant_id).in_(ids))
    ).first()
    ordered = session.exec(
        select(OrderItem).where(OrderItem.product_id == product.id)
    ).first()

    if moved or ordered:
        tr.ensure(tr.PRODUCT_TRANSITIONS, product.status, ProductStatus.ARCHIVED)
        product.status = ProductStatus.ARCHIVED
        session.add(product)
        audit.record(
            session,
            actor=user,
            action="product.archive",
            entity="product",
            entity_id=product.id,
            field="status",
            old=product.status,
            new=ProductStatus.ARCHIVED,
            note=i18n.label("card_has_history"),
        )
        session.commit()
        return s.Message(message=i18n.label("card_archived_not_deleted"))

    for row in session.exec(
        select(ProductSpec).where(ProductSpec.product_id == product.id)
    ).all():
        session.delete(row)
    for row in session.exec(
        select(ProductImage).where(ProductImage.product_id == product.id)
    ).all():
        session.delete(row)
    for row in variants:
        session.delete(row)

    audit.record(
        session,
        actor=user,
        action="product.delete",
        entity="product",
        entity_id=product.id,
        field="sku",
        old=product.sku,
        new=None,
        note=product.title,
    )
    session.delete(product)
    session.commit()
    return s.Message(message=i18n.label("card_deleted"))


@router.patch(
    "/products/{product_id}",
    response_model=s.AdminProductDetailOut,
    summary="Edit a card",
)
def update_product(
    product_id: int,
    payload: s.ProductUpdateIn,
    # The admin's: the words on a card are the shop window, and the person
    # who photographs the goods is the person who writes them.
    user: CatalogWriter,
    session: SessionDep,
) -> s.AdminProductDetailOut:
    """Everything about a card except its price, its stock and its status.

    Those three have their own doors, because each is a different kind of
    decision with a different consequence: a price is money, a count is the
    ledger's, and a status decides whether the apps can see the thing at all.
    """
    product = _product(session, product_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"translations"})

    if "category_slug" in fields:
        product.category_id = _category(session, fields.pop("category_slug")).id
    if "brand_slug" in fields:
        slug = fields.pop("brand_slug")
        product.brand_id = _brand(session, slug).id if slug else None
    for field, value in fields.items():
        if value is not None:
            setattr(product, field, value)
    session.add(product)

    i18n.write(session, "product", product.id, _texts(payload.translations))
    session.commit()
    session.refresh(product)
    return get_product(product_id, user, session)


@router.post(
    "/products/{product_id}/status",
    response_model=s.AdminProductOut,
    summary="Put a card in the shop, or take it out",
)
def set_product_status(
    product_id: int,
    payload: s.ProductStatusIn,
    # The admin's, and only theirs. Goods reaching a shelf and goods reaching
    # the shop are two decisions, and the second one is somebody's job rather
    # than a side effect of the first.
    user: CatalogWriter,
    session: SessionDep,
) -> s.AdminProductOut:
    """The only door the shop's front window opens through.

    **A colour with no photograph does not go on sale.** Market goods arrive
    with no pictures, so the only ones that will ever exist are the ones taken
    at the receiving desk — and a catalogue of grey squares sells nothing and
    makes the whole shop look broken. So this is refused rather than warned
    about, and the card stays in ``draft``: it is in stock, it sits in a cell,
    it counts towards the figures, and the apps cannot see it.

    The refusal **names the colours**, because "one colour is missing a
    photograph" leaves somebody opening all six to find out which.
    """
    product = _product(session, product_id)
    tr.ensure(tr.PRODUCT_TRANSITIONS, product.status, payload.status)

    if payload.status is ProductStatus.ACTIVE:
        # The photograph was the first gate and turned out to be the easy one.
        # A card written at the desk with the sack open has no category and no
        # selling price either, and either of those reaching a customer is
        # worse than the card being invisible for another hour: without a
        # category nobody browsing finds it, and without a price there is
        # nothing to charge.
        gaps = pr.unready(session, product.id)
        if gaps:
            # Each gap says what to go and do, and the photograph one still
            # names the colours: "a photograph is missing" leaves somebody
            # opening all six to find out which.
            parts = []
            for gap in gaps:
                if gap != "needs_photo":
                    parts.append(i18n.label(gap))
                    continue
                missing = pr.colours_without_a_photograph(session, product.id)
                named = ", ".join(colour or product.title for colour in missing)
                parts.append(f"{i18n.label(gap)} ({named})")
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                i18n.label("card_not_ready", gaps=", ".join(parts)),
            )

    audit.record(
        session,
        actor=user,
        action="product.status",
        entity="product",
        entity_id=product.id,
        field="status",
        old=product.status,
        new=payload.status,
        note=payload.note,
    )
    product.status = payload.status
    session.add(product)
    session.commit()
    # A card that has just become visible advertises whatever its variants
    # say, so the figures are recomputed rather than left as they were while
    # nobody could see them.
    pr.refresh(session, product.id)
    session.commit()
    session.refresh(product)
    return sv.admin_product_out(session, product)


# ------------------------------------------------------------------ the grid


@router.get(
    "/products/{product_id}/variants",
    response_model=list[s.AdminVariantOut],
    summary="Every cell of the colour × size grid",
)
def list_variants(
    product_id: int, user: CatalogReader, session: SessionDep
) -> list[s.AdminVariantOut]:
    product = _product(session, product_id)
    return [_variant_out(session, row) for row in pr.variants(session, product.id)]


@router.put(
    "/products/{product_id}/variants",
    response_model=list[s.AdminVariantOut],
    summary="Generate the colour × size matrix in one step",
)
def set_grid(
    product_id: int,
    payload: s.VariantGridIn,
    user: CatalogReader,
    session: SessionDep,
) -> list[s.AdminVariantOut]:
    """Pick the colours, pick the sizes, get the variants.

    Typing twelve rows by hand for every shoe model is how a warehouse stops
    being used, so the grid is what the form sends and the cells are what
    comes back.

    **Adds; never renumbers.** Sending the grid again with a colour added
    writes the new cells and leaves the existing ones exactly as they are —
    their prices, their counts, and above all their barcodes. A variant's
    barcode is permanent: when the same goods arrive again the label is
    reprinted, and a regenerated code would leave the shelf holding one thing
    under two of them.

    Nothing is deleted here either. A cell with history is deleted through its
    own door, which can refuse.
    """
    product = _product(session, product_id)
    existing = {(row.colour, row.size): row for row in pr.variants(session, product.id)}

    colours = payload.colours or [s.ColourIn(colour="", hex="")]
    sizes = [pr.tidy_size(one) for one in payload.sizes] or [""]
    price = payload.price or product.price
    sort = max((row.sort for row in existing.values()), default=-1) + 1

    for colour in colours:
        for size in sizes:
            key = (colour.colour, size)
            row = existing.get(key)
            if row is not None:
                # The hex may be corrected — it is a display detail — but the
                # code and the count are the row's own.
                if colour.hex:
                    row.colour_hex = colour.hex
                session.add(row)
                continue
            session.add(
                ProductVariant(
                    product_id=product.id,
                    colour=colour.colour,
                    colour_hex=colour.hex,
                    size=size,
                    price=price,
                    sort=sort,
                )
            )
            sort += 1
    session.commit()

    # The codes are ours, and they are only knowable once the row has an id.
    for row in pr.variants(session, product.id):
        if not row.sku:
            row.sku = pr.variant_sku(product, row)
        if not row.barcode:
            row.barcode = pr.barcode(row.id)
        session.add(row)
    pr.refresh(session, product.id)
    session.commit()
    return [_variant_out(session, row) for row in pr.variants(session, product.id)]


@router.patch(
    "/products/{product_id}/variants/{variant_id}",
    response_model=s.AdminVariantOut,
    summary="Reprice or relabel one cell",
)
def update_variant(
    product_id: int,
    variant_id: int,
    payload: s.VariantWriteIn,
    user: CatalogReader,
    session: SessionDep,
) -> s.AdminVariantOut:
    """The money is here and not on the card: a 43 can cost more than a 41.

    The barcode is not in the shape and cannot be changed. It is on labels
    that are already on shelves.
    """
    product = _product(session, product_id)
    variant = _variant(session, product, variant_id)
    fields = payload.model_dump(exclude_unset=True)

    if "price" in fields and fields["price"] != variant.price:
        audit.record(
            session,
            actor=user,
            action="variant.price",
            entity="product_variant",
            entity_id=variant.id,
            field="price",
            old=variant.price,
            new=fields["price"],
            note=sv.variant_label(variant),
        )
    for field, value in fields.items():
        setattr(variant, field, value)
    session.add(variant)
    pr.refresh(session, product.id)
    session.commit()
    session.refresh(variant)
    return _variant_out(session, variant)


@router.delete(
    "/products/{product_id}/variants/{variant_id}",
    response_model=s.Message,
    summary="Remove a cell that never held anything",
)
def delete_variant(
    product_id: int, variant_id: int, user: AdminUser, session: SessionDep
) -> s.Message:
    """Refused once it has a history, and that is not a technicality.

    A variant is what every movement, every placement and every order line
    points at. Deleting one with a ledger behind it would leave the room
    holding goods nothing can name.
    """
    product = _product(session, product_id)
    variant = _variant(session, product, variant_id)
    blocked = _why_not_deletable(session, variant)
    if blocked:
        raise HTTPException(status.HTTP_409_CONFLICT, blocked)
    session.delete(variant)
    pr.refresh(session, product.id)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


@router.post(
    "/products/{product_id}/variants/{variant_id}/retired",
    response_model=s.AdminVariantOut,
    summary="Take a cell out of the shop window, or put it back",
)
def retire_variant(
    product_id: int,
    variant_id: int,
    payload: s.RetireIn,
    user: CatalogWriter,
    session: SessionDep,
) -> s.AdminVariantOut:
    """The way out for a cell that cannot be deleted.

    A cell is deletable only while nothing has ever moved through it, which is
    right: every movement, placement and order line points at it. But that
    left a typo received once — a cap booked in as `M`, a size called `KS` —
    as a size struck through on the product page for the life of the card,
    with no way at all to remove it. Retiring keeps the ledger and stops the
    offer.

    **Only while it holds nothing.** Retiring a cell with goods on a shelf
    would hide stock the shop has paid for, which is worse than an untidy
    size row: the goods would be in the room, findable by a picker, and
    invisible to the office asking why the money is missing.
    """
    product = _product(session, product_id)
    variant = _variant(session, product, variant_id)
    if payload.retired and variant.stock_left > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("variant_still_holds", count=variant.stock_left),
        )
    was = variant.retired
    variant.retired = payload.retired
    audit.record(
        session,
        actor=user,
        action="variant.retired",
        entity="variant",
        entity_id=variant.id,
        field="retired",
        old=str(was),
        new=str(payload.retired),
        note=pr.label(variant),
    )
    session.add(variant)
    pr.refresh(session, product.id)
    session.commit()
    session.refresh(variant)
    return _variant_out(session, variant)


@router.post(
    "/products/{product_id}/price",
    response_model=list[s.AdminVariantOut],
    summary="Price the whole card at once",
)
def price_card(
    product_id: int,
    payload: s.CardPriceIn,
    # The admin's. The cost is captured at the bench, where it is known; what
    # to charge for it is a decision about the shop window, made by whoever
    # is looking at the window.
    user: CatalogWriter,
    session: SessionDep,
) -> list[s.AdminVariantOut]:
    """Every cell, or every cell of one colour.

    A pile off the van is one price. Publishing a card meant pricing twelve
    cells through twelve requests, which is how a card stays in the queue for a
    week — so this is the door the publishing screen uses, and the per-cell
    door stays for the 43 that really does cost more.
    """
    product = _product(session, product_id)
    rows = pr.variants(session, product.id)
    if payload.colour is not None:
        rows = [row for row in rows if row.colour == payload.colour]

    for row in rows:
        row.price = payload.price
        session.add(row)

    # The struck-through "was" belongs to the card: it is a display figure and
    # a variant has none. ``products.refresh`` takes the price itself from the
    # cheapest cell a moment later and leaves this alone.
    if payload.old_price is not None:
        product.old_price = payload.old_price
        session.add(product)

    audit.record(
        session,
        actor=user,
        action="product.price",
        entity="product",
        entity_id=product.id,
        field="price",
        old=product.price,
        new=payload.price,
        note=payload.colour or "",
    )
    session.commit()
    pr.refresh(session, product.id)
    session.commit()
    return [_variant_out(session, row) for row in pr.variants(session, product.id)]


@router.get(
    "/products/{product_id}/specs",
    response_model=list[s.SpecOut],
    summary="The specification table as it stands",
)
def list_specs(
    product_id: int, user: CatalogReader, session: SessionDep
) -> list[s.SpecOut]:
    product = _product(session, product_id)
    return [
        s.SpecOut(key=row.key, value=row.value)
        for row in session.exec(
            select(ProductSpec)
            .where(ProductSpec.product_id == product.id)
            .order_by(col(ProductSpec.sort), col(ProductSpec.id))
        ).all()
    ]


@router.put(
    "/products/{product_id}/specs",
    response_model=list[s.SpecOut],
    summary="The specification table, replaced whole",
)
def replace_specs(
    product_id: int,
    payload: s.SpecsReplaceIn,
    user: CatalogWriter,
    session: SessionDep,
) -> list[s.SpecOut]:
    """Replaced rather than edited row by row.

    The apps read this as a table and a person writes it as one: the order
    matters, rows get reordered as often as they get changed, and a per-row
    door would mean three requests to swap two lines. There was a schema for
    this and no endpoint — the merchant cabinet that used to call it went with
    the marketplace, and the phone has been rendering an empty block ever since.
    """
    product = _product(session, product_id)

    for old in session.exec(
        select(ProductSpec).where(ProductSpec.product_id == product.id)
    ).all():
        session.delete(old)

    for sort, row in enumerate(payload.specs):
        spec = ProductSpec(
            product_id=product.id,
            key=row.key.strip(),
            value=row.value.strip(),
            sort=sort,
        )
        session.add(spec)
        session.commit()
        session.refresh(spec)
        i18n.write(session, "spec", spec.id, _texts(row.translations))

    audit.record(
        session,
        actor=user,
        action="product.specs",
        entity="product",
        entity_id=product.id,
        field="specs",
        old=None,
        new=len(payload.specs),
        note=product.title,
    )
    session.commit()
    return [
        s.SpecOut(key=row.key, value=row.value)
        for row in session.exec(
            select(ProductSpec)
            .where(ProductSpec.product_id == product.id)
            .order_by(col(ProductSpec.sort), col(ProductSpec.id))
        ).all()
    ]


# ------------------------------------------------------------------ photographs


@router.get(
    "/products/{product_id}/images",
    response_model=list[s.AdminImageOut],
    summary="Every photograph, and which colour it is of",
)
def list_images(
    product_id: int, user: CatalogReader, session: SessionDep
) -> list[s.AdminImageOut]:
    product = _product(session, product_id)
    return [
        s.AdminImageOut(id=row.id, url=sv.media_url(row.url), sort=row.sort, colour=row.colour)
        for row in _image_rows(session, product.id)
    ]


@router.post(
    "/products/{product_id}/images",
    response_model=list[s.AdminImageOut],
    status_code=status.HTTP_201_CREATED,
    summary="Hang a photograph on a colour",
)
def add_image(
    product_id: int,
    payload: s.ImageWriteIn,
    # Both: the receiving desk hangs the identification snapshot on a card it
    # has just written, and the admin hangs the catalogue photographs.
    user: CatalogReader,
    session: SessionDep,
) -> list[s.AdminImageOut]:
    """A picture belongs to a colour, not to a variant.

    Two colours in six sizes is two photographs, not twelve, and nobody is
    ever asked to photograph a size. A colour with no picture is what keeps
    the whole card out of the shop.
    """
    product = _product(session, product_id)
    known = pr.colours(session, product.id)
    if payload.colour and payload.colour not in known:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("variant_invalid"))

    session.add(
        ProductImage(
            product_id=product.id,
            colour=payload.colour,
            url=payload.url,
            sort=payload.sort,
        )
    )
    session.commit()
    return list_images(product_id, user, session)


@router.delete(
    "/products/{product_id}/images/{image_id}",
    response_model=s.Message,
    summary="Take a photograph down",
)
def delete_image(
    product_id: int, image_id: int, user: CatalogReader, session: SessionDep
) -> s.Message:
    """Which may put the card back into ``draft``.

    Deliberately: the rule is that a colour without a picture does not reach
    the apps, and a card that stayed on sale because the last photograph was
    deleted rather than never taken is the same grey square.
    """
    product = _product(session, product_id)
    row = session.get(ProductImage, image_id)
    if row is None or row.product_id != product.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("image_not_found"))
    session.delete(row)
    session.commit()

    if product.status is ProductStatus.ACTIVE and pr.colours_without_a_photograph(
        session, product.id
    ):
        audit.record(
            session,
            actor=user,
            action="product.status",
            entity="product",
            entity_id=product.id,
            field="status",
            old=ProductStatus.ACTIVE,
            new=ProductStatus.DRAFT,
            note=i18n.label("colour_needs_photo", colours=""),
        )
        product.status = ProductStatus.DRAFT
        session.add(product)
        session.commit()
    return s.Message(message=i18n.label("deleted"))


@router.put(
    "/products/{product_id}/images/{image_id}/cover",
    response_model=list[s.AdminImageOut],
    summary="Make a photograph the cover of its colour",
)
def set_image_cover(
    product_id: int,
    image_id: int,
    # The admin's alone. Which photograph a customer sees first is the shop
    # window, not the shelf, and the bench's business with a card ends when
    # the goods are on it.
    user: CatalogWriter,
    session: SessionDep,
) -> list[s.AdminImageOut]:
    """Promote one photograph to the front of its own colour.

    Before this door the only way to change a cover was to delete every
    photograph in front of it — four shots of a jacket and the good one third
    meant throwing two away. A cover-setter rather than a general reorder
    because "make this one the cover" is the whole of what anybody asks for:
    the rest of a colour's pictures are a strip nobody arranges.

    **The whole card is renumbered, not just the promoted colour.** ``sort``
    is written as ``0`` by everything that has ever hung a picture, so in real
    data every row ties and the order is whatever ``id`` falls out as. Some
    read paths break that tie by ``id`` and some order by ``sort`` alone — see
    ``services.card_images`` — so numbering one colour ``0,1,2`` and leaving
    the other at ``0,0`` would interleave the two colours on the customer's
    swipe strip. Renumbering the card densely, colour-block by colour-block in
    the order the blocks already stood, makes every one of those reads agree.
    The other colours keep their order and their place; only their integers
    move, and nothing else reads those integers.
    """
    product = _product(session, product_id)
    chosen = session.get(ProductImage, image_id)
    if chosen is None or chosen.product_id != product.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("image_not_found"))

    # Grouped in the order the colours already stood, which is why this is read
    # before the promotion: a card's first colour stays its first colour even
    # when the photograph promoted is the one that used to be behind.
    groups: dict[str, list[ProductImage]] = {}
    for row in _image_rows(session, product.id):
        groups.setdefault(row.colour, []).append(row)
    # Stable, so the rest of the colour keeps the order it was in.
    groups[chosen.colour].sort(key=lambda row: row.id != chosen.id)

    place = 0
    moved = False
    for group in groups.values():
        for row in group:
            if row.sort != place:
                row.sort = place
                session.add(row)
                moved = True
            place += 1
    # A photograph already at the front of a tidy card is not a write.
    if moved:
        session.commit()
    return list_images(product_id, user, session)


@router.get(
    "/categories",
    response_model=list[s.AdminCategoryOut],
    summary="Every category, flat, in the words the rows hold",
)
def list_categories(user: CatalogReader, session: SessionDep) -> list[s.AdminCategoryOut]:
    """The whole tree at once, and the Uzbek that is on the row.

    Flat rather than nested: an editor picking a parent wants one list to
    search, and the tree is recoverable from ``parent_slug``. The customer
    endpoint answers a level at a time and translates as it goes, which is
    right for the app and wrong for the field that writes the source text.
    """
    rows = session.exec(
        select(Category).order_by(col(Category.sort), col(Category.name))
    ).all()
    parents = {row.id: row.slug for row in rows}
    products = dict(
        session.exec(
            select(Product.category_id, func.count())
            .group_by(col(Product.category_id))
        ).all()
    )
    children: dict[int, int] = {}
    for row in rows:
        if row.parent_id is not None:
            children[row.parent_id] = children.get(row.parent_id, 0) + 1
    return [
        s.AdminCategoryOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            subtitle=row.subtitle,
            icon=row.icon,
            image_url=sv.media_url(row.image_url),
            parent_slug=parents.get(row.parent_id) if row.parent_id else None,
            sort=row.sort,
            is_quick_link=row.is_quick_link,
            product_count=int(products.get(row.id, 0)),
            child_count=children.get(row.id, 0),
        )
        for row in rows
    ]


@router.post(
    "/categories",
    response_model=s.CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: s.CategoryWriteIn,
    # The admin's, because filing a card needs somewhere to file it and the
    # first card ever written has nowhere. Renaming and deleting stay the
    # office's: those move goods that customers are already browsing.
    user: CatalogWriter,
    session: SessionDep,
) -> s.CategoryOut:
    if session.exec(select(Category).where(Category.slug == payload.slug)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
    parent = _category(session, payload.parent_slug) if payload.parent_slug else None
    row = Category(
        slug=payload.slug,
        name=payload.name,
        subtitle=payload.subtitle,
        icon=payload.icon,
        image_url=payload.image_url,
        parent_id=parent.id if parent else None,
        sort=payload.sort,
        is_quick_link=payload.is_quick_link,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    i18n.write(session, "category", row.id, _texts(payload.translations))
    session.commit()
    session.refresh(row)
    return sv.category_out(session, row)


@router.patch("/categories/{slug}", response_model=s.CategoryOut)
def update_category(
    slug: str, payload: s.CategoryUpdateIn, user: AdminUser, session: SessionDep
) -> s.CategoryOut:
    row = _category(session, slug)
    if payload.parent_slug is not None:
        parent = _category(session, payload.parent_slug)
        if parent.id == row.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("category_own_parent")
            )
        row.parent_id = parent.id
    for field in ("name", "subtitle", "icon", "image_url", "sort", "is_quick_link"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    i18n.write(session, "category", row.id, _texts(payload.translations))
    session.add(row)
    session.commit()
    session.refresh(row)
    return sv.category_out(session, row)


@router.delete("/categories/{slug}", response_model=s.Message)
def delete_category(slug: str, user: AdminUser, session: SessionDep) -> s.Message:
    """Refused while anything still points at it.

    A category with cards in it, or with children, is load-bearing: deleting
    it would leave products pointing at a row that is not there and a listing
    that answers with nothing.
    """
    row = _category(session, slug)
    if session.exec(select(Product).where(Product.category_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("category_in_use"))
    if session.exec(select(Category).where(Category.parent_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("category_in_use"))
    i18n.forget(session, "category", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- brands


@router.get(
    "/brands",
    response_model=list[s.AdminBrandOut],
    summary="Every brand, with how many cards carry it",
)
def list_brands(user: CatalogReader, session: SessionDep) -> list[s.AdminBrandOut]:
    """Every brand, with what it holds and what it answers to.

    Both figures are here for the merge screen. ``product_count`` says whether
    a row can simply be deleted; ``aliases`` says which rows look like each
    other, in the words people typed at the desk rather than in a similarity
    score nobody can check.
    """
    counts = dict(
        session.exec(
            select(Product.brand_id, func.count()).group_by(col(Product.brand_id))
        ).all()
    )
    # One query for the whole alias table rather than one per brand: the
    # brand list is drawn in full on one screen, and a lookup per row is the
    # shape that turns forty makes into forty-one queries.
    words: dict[int, list[str]] = {}
    for alias in session.exec(
        select(BrandAlias).order_by(col(BrandAlias.id))
    ).all():
        words.setdefault(alias.brand_id, []).append(alias.name)

    rows = session.exec(select(Brand).order_by(col(Brand.name))).all()
    return [
        s.AdminBrandOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            product_count=int(counts.get(row.id, 0)),
            aliases=words.get(row.id, []),
        )
        for row in rows
    ]


@router.post(
    "/brands", response_model=s.BrandOut, status_code=status.HTTP_201_CREATED
)
def create_brand(
    payload: s.BrandWriteIn, user: AdminUser, session: SessionDep
) -> s.BrandOut:
    """A make written in the panel rather than typed at the desk.

    Refused when some other row already answers to the name, because the row
    written here would be the duplicate the receiving desk can no longer make
    — the desk matches on the spelling and would keep landing on the first
    one, leaving this one with a name, no cards and no way to get any.
    """
    if session.exec(select(Brand).where(Brand.slug == payload.slug)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
    _ensure_name_is_free(session, payload.name, mine=None)

    row = Brand(slug=payload.slug, name=payload.name)
    session.add(row)
    session.commit()
    session.refresh(row)
    brands.remember(session, row, payload.name)
    i18n.write(session, "brand", row.id, _texts(payload.translations))
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.patch("/brands/{slug}", response_model=s.BrandOut)
def update_brand(
    slug: str, payload: s.BrandWriteIn, user: AdminUser, session: SessionDep
) -> s.BrandOut:
    """Correct a brand's name, its slug, or its translations.

    **The slug is applied.** It used to be read off the payload and then
    ignored, so a slug generated from a misspelling — ``on-clod`` — was
    permanent: it is in the catalogue's filter URLs and on every brand link,
    and the only way to change it was to make a second brand and move the
    cards by hand, which is the very thing the merge door exists for.

    **The old name goes on working.** A rename adds the new spelling to the
    ones this row answers to rather than replacing them, because the receiving
    desk matches on the spelling somebody types. Renaming ``On Cloud`` to
    ``On Running`` used to mean the next sack typed as "On Cloud" wrote a
    second row — the correction lasted until the next van.
    """
    row = _brand(session, slug)

    if payload.slug != row.slug:
        if session.exec(select(Brand).where(Brand.slug == payload.slug)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
        row.slug = payload.slug

    _ensure_name_is_free(session, payload.name, mine=row)
    row.name = payload.name
    brands.remember(session, row, payload.name)

    i18n.write(session, "brand", row.id, _texts(payload.translations))
    session.add(row)
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.post(
    "/brands/{slug}/merge",
    response_model=s.BrandMergeOut,
    summary="Two rows were one make — fold this one into another",
)
def merge_brand(
    slug: str, payload: s.BrandMergeIn, user: AdminUser, session: SessionDep
) -> s.BrandMergeOut:
    """Move every card off ``slug`` onto ``into``, then delete ``slug``.

    **It could not be composed from the doors that already existed.**
    ``DELETE /admin/brands/{slug}`` refuses while any card names the brand,
    and nothing repoints a card's brand in bulk — so joining ``on-cloud`` and
    ``on-clod`` meant opening every card, changing its brand, and only then
    deleting. Forty cards is forty chances to stop halfway, and half a merge
    is the duplicate it was supposed to remove plus a brand nobody trusts.

    **One transaction, and nothing downstream to repair.** ``Product`` carries
    the foreign key and no denormalised brand name; ``OrderItem`` snapshots
    the product title rather than the brand. So no order, receipt or report is
    rewritten here, and none of them is wrong afterwards. ``GET
    /warehouse/vocab``, the catalogue's brand filters and the brand index all
    read the ``brands`` table live, so they answer correctly on the next
    request with nothing to clear.

    **The loser's spellings move to the winner**, which is the half that makes
    the merge hold: they are the words that made the duplicate, and the
    receiving desk matches on them. Without that, the next sack typed the old
    way writes the row back.

    **Admin only.** Merging deletes a row and moves other people's cards onto
    another one; the receiving desk creates brands because it must in order to
    book goods in at all, and this is not that.
    """
    loser = _brand(session, slug)
    winner = _brand(session, payload.into)
    if loser.id == winner.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("brand_merge_itself")
        )

    moved = brands.merge(session, actor=user, loser=loser, winner=winner)
    session.commit()
    session.refresh(winner)
    return s.BrandMergeOut(
        brand=s.BrandOut(id=winner.id, slug=winner.slug, name=winner.name),
        products_moved=moved,
        aliases=brands.spellings(session, winner.id),
    )


@router.delete("/brands/{slug}", response_model=s.Message)
def delete_brand(slug: str, user: AdminUser, session: SessionDep) -> s.Message:
    """Only a brand nothing carries. A brand with cards is merged, not deleted."""
    row = _brand(session, slug)
    if session.exec(select(Product).where(Product.brand_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("brand_in_use"))
    for alias in session.exec(
        select(BrandAlias).where(BrandAlias.brand_id == row.id)
    ).all():
        session.delete(alias)
    i18n.forget(session, "brand", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


def _ensure_name_is_free(
    session: SessionDep, name: str, *, mine: Brand | None
) -> None:
    """Refuse a name some other row already answers to.

    Two brands called "Nike" is the state this whole file is trying to get out
    of: the desk can only land on one of them, so the other collects no cards
    and the catalogue offers the customer two filters for one make. The
    refusal names the row that holds the spelling and says to merge, because
    that is the thing the admin was about to do by hand.
    """
    held = brands.by_spelling(session, name)
    if held is not None and (mine is None or held.id != mine.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("brand_name_taken", name=name, slug=held.slug),
        )


# --------------------------------------------------------------------------- the colour palette
#
# **Who may do what, and why the two doors differ.** Reading is
# ``CatalogReader`` — the warehouse as well as the admin — because the palette
# is what the receiving bench picks a colour from, and a bench that cannot
# read it is a bench back at a text box. *Writing a new colour is the bench's
# too*, deliberately: §5.2's form offers "+ yangi rang" and that form opens at
# `/qabul`, so a guard of ``CatalogWriter`` there would mean somebody holding
# a sack of a colour nobody has sold before must go and find the owner before
# the goods can be booked in. They will not; they will type the colour into
# the nearest box that accepts it, which is how this table came to be needed.
# The same argument is already settled for makes: ``brands.named`` writes a
# row from the desk for exactly this reason.
#
# **Changing or removing a colour is the admin's alone.** Those act on rows
# other people's cards are wearing — a rename moves a swatch under forty
# cards, a merge rewrites their colour strings — and that is a decision about
# the shop's vocabulary rather than about the sack on the table.


@router.get(
    "/colours",
    response_model=list[s.ColourSwatchOut],
    summary="The palette, with what each colour is worn by",
)
def list_colours(user: CatalogReader, session: SessionDep) -> list[s.ColourSwatchOut]:
    """Every colour the shop sells, in the order the picker draws them.

    ``variant_count`` and ``spellings`` are both here for the merge screen, in
    one pass: the count says whether a row can simply be deleted, and the
    spellings say which rows look like each other in the words people actually
    typed. One query for the whole variant table rather than one per colour —
    the palette is drawn in full on one screen, and a lookup per row is how
    thirty swatches become thirty-one queries.
    """
    used = colours.spellings_in_use(session)
    rows = session.exec(
        select(Colour).order_by(col(Colour.sort), col(Colour.name))
    ).all()
    return [
        s.ColourSwatchOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            hex=row.hex,
            sort=row.sort,
            variant_count=sum(count for _, count in used.get(row.key, [])),
            spellings=[name for name, _ in used.get(row.key, [])],
        )
        for row in rows
    ]


@router.post(
    "/colours",
    response_model=s.ColourSwatchOut,
    status_code=status.HTTP_201_CREATED,
    summary="+ yangi rang — a colour the shop had not sold before",
)
def create_colour(
    payload: s.ColourWriteIn,
    # The bench's as well as the admin's — see the note at the head of this
    # section. Adding to a palette is additive and reversible; being unable to
    # add to it mid-receipt is neither.
    user: CatalogReader,
    session: SessionDep,
) -> s.ColourSwatchOut:
    """Refused when the palette already answers to the name.

    Not a courtesy. The point of the table is that one spelling means one
    colour, so a second row keyed the same way would give the picker two right
    answers and put the shop back where it started — with the extra insult
    that the new row would collect nothing, because everything already lands
    on the first.
    """
    held = colours.by_spelling(session, payload.name)
    if held is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("colour_name_taken", name=payload.name, slug=held.slug),
        )
    if payload.slug and session.exec(
        select(Colour).where(Colour.slug == payload.slug)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))

    name = pr.tidy_label(payload.name)
    row = Colour(
        slug=payload.slug or colours.free_slug(session, name),
        name=name,
        key=colours.key(name),
        hex=payload.hex,
        sort=payload.sort if payload.sort is not None else colours.next_sort(session),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _colour_out(session, row)


@router.patch("/colours/{slug}", response_model=s.ColourSwatchOut)
def update_colour(
    slug: str,
    payload: s.ColourPatchIn,
    # The admin's: a rename moves the swatch under every card wearing the
    # colour, and the shop's vocabulary is the owner's.
    user: CatalogWriter,
    session: SessionDep,
) -> s.ColourSwatchOut:
    """Correct a colour's name, its swatch, its slug or where it sits.

    **The variants are not renamed.** A card whose colour reads ``Ko'k`` goes
    on reading ``Ko'k`` after the palette row is renamed to ``Moviy`` — the
    string on the variant is what the ledger's neighbours, the photographs and
    every past order agree on, and a rename here is a change to what the
    *picker offers next*. Renaming what is already out there is
    ``POST /colours/{slug}/merge``, which is a different sentence and says so.
    """
    row = _colour(session, slug)
    fields = payload.model_dump(exclude_unset=True)

    if fields.get("slug") and fields["slug"] != row.slug:
        if session.exec(
            select(Colour).where(Colour.slug == fields["slug"])
        ).first():
            raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
        row.slug = fields["slug"]

    if "name" in fields and fields["name"]:
        name = pr.tidy_label(fields["name"])
        held = colours.by_spelling(session, name)
        if held is not None and held.id != row.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                i18n.label("colour_name_taken", name=name, slug=held.slug),
            )
        row.name = name
        row.key = colours.key(name)

    if "hex" in fields and fields["hex"] is not None:
        row.hex = fields["hex"]
    if "sort" in fields and fields["sort"] is not None:
        row.sort = fields["sort"]

    session.add(row)
    session.commit()
    session.refresh(row)
    return _colour_out(session, row)


@router.post(
    "/colours/{slug}/merge",
    response_model=s.ColourMergeOut,
    summary="Two swatches were one colour — fold this one into another",
)
def merge_colour(
    slug: str,
    payload: s.ColourMergeIn,
    user: CatalogWriter,
    session: SessionDep,
) -> s.ColourMergeOut:
    """Rename every variant and photograph off ``slug`` onto ``into``.

    **This is the repair, and the palette alone is not one.** Offering a list
    stops the *next* duplicate; it does nothing about the ``Siniy`` sitting
    beside ``Ko'k`` in this shop's data right now, and there is no composition
    of the other doors that fixes it — ``DELETE`` refuses while anything wears
    the colour, and nothing rewrites a variant's colour in bulk. The only
    other route was opening every card by hand.

    **No stock moves.** A movement names a ``variant_id`` and a placement
    names ``(location, variant)``; neither holds a colour. So the ledger is
    untouched, every placement still equals it, and the figures on the shelf
    map are the same before and after.

    **The photographs come with it**, because the publishing gate wants a
    picture per colour and renaming the variants alone would take that picture
    away from every card in the merge.

    **Order lines are left alone.** They are snapshots of what somebody bought
    in the words the shop used that day, and tidying a vocabulary is not a
    reason to edit a sale after the fact.
    """
    loser = _colour(session, slug)
    winner = _colour(session, payload.into)
    if loser.id == winner.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("colour_merge_itself")
        )

    # Refused rather than guessed: a card holding both colours at one size is
    # two ledger rows trying to become one, which is a stock decision somebody
    # makes with the shelf in front of them.
    clashing = colours.collisions(session, loser=loser, winner=winner)
    if clashing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("colour_merge_clash", cards=", ".join(clashing)),
        )

    variants, images = colours.merge(
        session, actor=user, loser=loser, winner=winner
    )
    session.commit()
    session.refresh(winner)
    return s.ColourMergeOut(
        colour=_colour_out(session, winner),
        variants_moved=variants,
        images_moved=images,
    )


@router.delete("/colours/{slug}", response_model=s.Message)
def delete_colour(
    slug: str, user: CatalogWriter, session: SessionDep
) -> s.Message:
    """Only a colour nothing is wearing. One with variants is merged, not deleted.

    Counted on the key and not the exact spelling, or a swatch that thirty
    ``qora`` variants are wearing would delete cleanly because the palette
    happens to spell it ``Qora`` — and the picker would then stop offering a
    colour the shop demonstrably sells.
    """
    row = _colour(session, slug)
    worn = colours.variant_count(session, row)
    if worn:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("colour_in_use", count=worn)
        )
    i18n.forget(session, "colour", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


def _colour(session: SessionDep, slug: str) -> Colour:
    row = session.exec(select(Colour).where(Colour.slug == slug)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("colour_not_found"))
    return row


def _colour_out(session: SessionDep, row: Colour) -> s.ColourSwatchOut:
    used = colours.spellings_in_use(session).get(row.key, [])
    return s.ColourSwatchOut(
        id=row.id,
        slug=row.slug,
        name=row.name,
        hex=row.hex,
        sort=row.sort,
        variant_count=sum(count for _, count in used),
        spellings=[name for name, _ in used],
    )


# --------------------------------------------------------------------------- the size systems
#
# Read by the bench, written by the admin — and here the split is the plain
# one. A size system is a decision about how a whole category of goods is
# numbered, made once; nothing about a sack on the table requires inventing
# one, and a bench that could would be a bench that invents "Erkaklar
# poyabzali EUR" a second time under a different name.


@router.get(
    "/size-systems",
    response_model=list[s.SizeSystemOut],
    summary="Every run of sizes a card can be numbered in",
)
def list_size_systems(
    user: CatalogReader, session: SessionDep
) -> list[s.SizeSystemOut]:
    """The systems with their values, in the order the picker draws them.

    Values and card counts in two queries for the whole list rather than two
    per row: §5.2's attribute picker draws every system at once, grouped by
    ``family``, and it needs the values in hand to turn the size boxes into
    that system's own.
    """
    counts = dict(
        session.exec(
            select(Product.size_system_id, func.count())
            .where(col(Product.size_system_id).is_not(None))
            .group_by(col(Product.size_system_id))
        ).all()
    )
    values: dict[int, list[str]] = {}
    for row in session.exec(
        select(SizeValue).order_by(col(SizeValue.sort), col(SizeValue.id))
    ).all():
        values.setdefault(row.system_id, []).append(row.value)

    systems = session.exec(
        select(SizeSystem).order_by(col(SizeSystem.sort), col(SizeSystem.name))
    ).all()
    return [
        s.SizeSystemOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            family=row.family,
            scale=row.scale,
            sort=row.sort,
            values=values.get(row.id, []),
            card_count=int(counts.get(row.id, 0)),
        )
        for row in systems
    ]


@router.post(
    "/size-systems",
    response_model=s.SizeSystemOut,
    status_code=status.HTTP_201_CREATED,
    summary="A new run of sizes — the shop started selling belts",
)
def create_size_system(
    payload: s.SizeSystemWriteIn, user: CatalogWriter, session: SessionDep
) -> s.SizeSystemOut:
    """Refused when a system of that name already exists.

    Two systems called "Kiyim" is two answers to "what sizes does a shirt come
    in", and the card that picks the wrong one is indistinguishable afterwards
    from the card that picked the right one.
    """
    _ensure_system_name_is_free(session, payload.name, mine=None)
    if payload.slug and session.exec(
        select(SizeSystem).where(SizeSystem.slug == payload.slug)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))

    row = SizeSystem(
        slug=payload.slug or sizes.free_slug(session, payload.name),
        name=payload.name.strip(),
        family=payload.family.strip(),
        scale=payload.scale.strip(),
        sort=payload.sort if payload.sort is not None else sizes.next_sort(session),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    sizes.replace_values(session, row.id, payload.values)
    session.commit()
    return _size_system_out(session, row)


@router.patch("/size-systems/{slug}", response_model=s.SizeSystemOut)
def update_size_system(
    slug: str, payload: s.SizeSystemPatchIn, user: CatalogWriter, session: SessionDep
) -> s.SizeSystemOut:
    """Correct a system, and optionally replace the sizes it offers.

    **Changing the values changes nothing already on a card.** A variant's
    size is a string on the variant with a barcode printed against it (§6.5),
    and dropping ``47`` from the list stops it being *offered* — it does not
    reach into the shelf and remove the 47s that are on it. That asymmetry is
    deliberate: the list is what the form suggests, never a validator run
    against stock.

    ``values`` absent leaves the list alone; ``[]`` empties it.
    """
    row = _size_system(session, slug)
    fields = payload.model_dump(exclude_unset=True)

    if fields.get("slug") and fields["slug"] != row.slug:
        if session.exec(
            select(SizeSystem).where(SizeSystem.slug == fields["slug"])
        ).first():
            raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
        row.slug = fields["slug"]

    if fields.get("name"):
        _ensure_system_name_is_free(session, fields["name"], mine=row)
        row.name = fields["name"].strip()
    if fields.get("family") is not None:
        row.family = fields["family"].strip()
    if fields.get("scale") is not None:
        row.scale = fields["scale"].strip()
    if fields.get("sort") is not None:
        row.sort = fields["sort"]

    session.add(row)
    if fields.get("values") is not None:
        sizes.replace_values(session, row.id, fields["values"])
    session.commit()
    session.refresh(row)
    return _size_system_out(session, row)


@router.delete("/size-systems/{slug}", response_model=s.Message)
def delete_size_system(
    slug: str, user: CatalogWriter, session: SessionDep
) -> s.Message:
    """Only a system no card names.

    A card whose system vanished would be sized in nothing — the form would
    offer no values and could not tell whether that means "sizeless" or "the
    list is gone", which is precisely the ambiguity §6.3 exists to forbid. So
    the cards come off it first, one decision at a time, by somebody who knows
    what they should be numbered in instead.
    """
    row = _size_system(session, slug)
    cards = sizes.card_count(session, row.id)
    if cards:
        raise HTTPException(
            status.HTTP_409_CONFLICT, i18n.label("size_system_in_use", count=cards)
        )
    for value in session.exec(
        select(SizeValue).where(SizeValue.system_id == row.id)
    ).all():
        session.delete(value)
    i18n.forget(session, "size_system", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


@router.get(
    "/products/{product_id}/size-system",
    response_model=s.ProductSizeSystemOut,
    summary="What this card is sized in, and therefore what its form offers",
)
def get_product_size_system(
    product_id: int, user: CatalogReader, session: SessionDep
) -> s.ProductSizeSystemOut:
    """``null`` means sizeless, not unknown — see ``PUT``."""
    product = _product(session, product_id)
    row = (
        session.get(SizeSystem, product.size_system_id)
        if product.size_system_id
        else None
    )
    return s.ProductSizeSystemOut(
        product_id=product.id,
        size_system=_size_system_out(session, row) if row else None,
    )


@router.put(
    "/products/{product_id}/size-system",
    response_model=s.ProductSizeSystemOut,
    summary="Name the run of sizes this card is numbered in",
)
def set_product_size_system(
    product_id: int,
    payload: s.ProductSizeSystemIn,
    # The bench's as well, because §5.4 opens this same form at `/qabul` for a
    # card that does not exist yet, and the sizes are the half of that form
    # the person with the goods in their hands is filling in.
    user: CatalogReader,
    session: SessionDep,
) -> s.ProductSizeSystemOut:
    """Its own door, and not a field on the edit form, for the ordinary reason
    the price and the status have their own: this is the answer to §6.3's
    either/or. ``slug: null`` says **sizeless** — a cap, a bag — which is a
    statement about the goods and not an empty box somebody has not got to.

    It changes no variant. A card already carrying 41, 42 and 43 goes on
    carrying them; what moves is what the form offers next.
    """
    product = _product(session, product_id)
    row = _size_system(session, payload.slug) if payload.slug else None
    product.size_system_id = row.id if row else None
    session.add(product)
    session.commit()
    session.refresh(product)
    return s.ProductSizeSystemOut(
        product_id=product.id,
        size_system=_size_system_out(session, row) if row else None,
    )


def _size_system(session: SessionDep, slug: str) -> SizeSystem:
    row = session.exec(select(SizeSystem).where(SizeSystem.slug == slug)).first()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, i18n.label("size_system_not_found")
        )
    return row


def _size_system_out(session: SessionDep, row: SizeSystem) -> s.SizeSystemOut:
    return s.SizeSystemOut(
        id=row.id,
        slug=row.slug,
        name=row.name,
        family=row.family,
        scale=row.scale,
        sort=row.sort,
        values=sizes.values(session, row.id),
        card_count=sizes.card_count(session, row.id),
    )


def _ensure_system_name_is_free(
    session: SessionDep, name: str, *, mine: SizeSystem | None
) -> None:
    """Refuse a name another system already holds, case and spacing aside."""
    wanted = colours.key(name)
    for row in session.exec(select(SizeSystem)).all():
        if colours.key(row.name) == wanted and (mine is None or row.id != mine.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                i18n.label("size_system_name_taken", name=name, slug=row.slug),
            )


# --------------------------------------------------------------------------- what a card is made of


def _texts(translations: dict) -> dict[str, dict[str, str | None]]:
    """A ``{lang: TextIn}`` payload as ``i18n.write`` wants it.

    ``exclude_unset`` is what makes the two meanings distinct: a field the
    caller did not mention is left alone, and a field they sent as ``null`` or
    blank has its translation removed. A model dumped whole would turn the
    first into the second and quietly wipe the half of the form that was not
    on screen.
    """
    return {
        lang: text.model_dump(exclude_unset=True)
        for lang, text in translations.items()
    }


# --------------------------------------------------------------------------- helpers


def _product(session: SessionDep, product_id: int) -> Product:
    row = session.get(Product, product_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))
    return row


def _category(session: SessionDep, slug: str) -> Category:
    row = session.exec(select(Category).where(Category.slug == slug)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("category_not_found"))
    return row


def _brand(session: SessionDep, slug: str) -> Brand:
    row = session.exec(select(Brand).where(Brand.slug == slug)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("brand_not_found"))
    return row


def _has_any_stock(session: SessionDep, product_id: int) -> bool:
    return pr.on_shelf(session, product_id) > 0


def _variant(
    session: SessionDep, product: Product, variant_id: int
) -> ProductVariant:
    row = session.get(ProductVariant, variant_id)
    if row is None or row.product_id != product.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("variant_invalid"))
    return row


def _why_not_deletable(session: SessionDep, variant: ProductVariant) -> str:
    from app.models import OrderItem, StockMovement

    if session.exec(
        select(StockMovement).where(StockMovement.variant_id == variant.id)
    ).first():
        return i18n.label("variant_has_history")
    if session.exec(
        select(OrderItem).where(OrderItem.variant_id == variant.id)
    ).first():
        return i18n.label("variant_has_history")
    return ""


def _variant_out(session: SessionDep, variant: ProductVariant) -> s.AdminVariantOut:
    blocked = _why_not_deletable(session, variant)
    return s.AdminVariantOut(
        id=variant.id,
        colour=variant.colour,
        colour_hex=variant.colour_hex,
        size=variant.size,
        label=sv.variant_label(variant) or "—",
        sku=variant.sku,
        barcode=variant.barcode,
        price=variant.price,
        sort=variant.sort,
        stock_left=variant.stock_left,
        in_stock=st.sellable(session, variant) > 0,
        retired=variant.retired,
        can_delete=not blocked,
        blocked_reason=blocked,
    )


def _image_rows(session: SessionDep, product_id: int) -> list[ProductImage]:
    return list(
        session.exec(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(col(ProductImage.sort), col(ProductImage.id))
        ).all()
    )

