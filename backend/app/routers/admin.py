"""The catalogue and who sells in it — the admin's side.

Until now nothing could write to the catalogue at all: a product, a category,
a brand arrived through ``seed.py`` and nowhere else, which meant adding one
took a developer. And there was no way to make a second seller, so the
multi-seller model the last three stages built was never exercised by anything
but a test fixture.

Two decisions run through this file.

**The catalogue belongs to the platform.** A seller attaches an offer to a card
that already exists; they do not open their own copy of it. That is the whole
point of one card carrying several offers — a copy per seller duplicates the
catalogue and leaves the warehouse holding the same goods in two places under
two names. What a seller can do is *propose* a card, which lands in moderation.

**Three things about a card are not the catalogue's to set.** Its price belongs
to an offer, its stock to the movement ledger, and its status to a decision
somebody made with a reason attached. So none of them is in the edit shape,
and each has its own door.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import offers as of
from app import schemas as s
from app import services as sv
from app import transitions as tr
from app.deps import AdminUser, SellerUser, SessionDep
from app.models import (
    Brand,
    Category,
    Offer,
    OfferVariant,
    OrderItem,
    Product,
    ProductImage,
    ProductSpec,
    ProductStatus,
    ProductVariant,
    Seller,
    StockMovement,
    User,
    UserRole,
    VariantKind,
)

router = APIRouter(prefix="/staff", tags=["staff"])


# --------------------------------------------------------------------------- sellers


@router.get("/sellers", response_model=list[s.AdminSellerOut], summary="Every seller")
def list_sellers(user: AdminUser, session: SessionDep) -> list[s.AdminSellerOut]:
    rows = session.exec(select(Seller).order_by(col(Seller.name))).all()
    return [_seller_out(session, row) for row in rows]


@router.post(
    "/sellers",
    response_model=s.AdminSellerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Take on a seller",
)
def create_seller(
    payload: s.SellerCreateIn, user: AdminUser, session: SessionDep
) -> s.AdminSellerOut:
    if session.exec(select(Seller).where(Seller.name == payload.name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("seller_exists"))

    seller = Seller(
        name=payload.name,
        phone=payload.phone,
        commission_percent=payload.commission_percent,
    )
    session.add(seller)
    session.commit()
    session.refresh(seller)

    audit.record(
        session,
        actor=user,
        action="seller.create",
        entity="seller",
        entity_id=seller.id,
        field="commission_percent",
        old=None,
        new=seller.commission_percent,
        note=seller.name,
    )
    if payload.user_phone:
        _link_account(session, user, seller, payload.user_phone)
    session.commit()
    session.refresh(seller)
    return _seller_out(session, seller)


@router.get("/sellers/{seller_id}", response_model=s.AdminSellerOut)
def get_seller(seller_id: int, user: AdminUser, session: SessionDep) -> s.AdminSellerOut:
    return _seller_out(session, _seller(session, seller_id))


@router.patch(
    "/sellers/{seller_id}",
    response_model=s.AdminSellerOut,
    summary="Edit a seller, or stop them selling",
)
def update_seller(
    seller_id: int, payload: s.SellerUpdateIn, user: AdminUser, session: SessionDep
) -> s.AdminSellerOut:
    seller = _seller(session, seller_id)

    if payload.name is not None and payload.name != seller.name:
        clash = session.exec(select(Seller).where(Seller.name == payload.name)).first()
        if clash is not None and clash.id != seller.id:
            raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("seller_exists"))
        seller.name = payload.name
    if payload.phone is not None:
        seller.phone = payload.phone

    # The rate a seller is paid at is a term of a contract, so a change to it
    # is logged with a name against it. What was already sold keeps the rate it
    # was sold at — that figure lives on the order line.
    if (
        payload.commission_percent is not None
        and payload.commission_percent != seller.commission_percent
    ):
        audit.record(
            session,
            actor=user,
            action="seller.commission_percent",
            entity="seller",
            entity_id=seller.id,
            field="commission_percent",
            old=seller.commission_percent,
            new=payload.commission_percent,
            note=seller.name,
        )
        seller.commission_percent = payload.commission_percent

    if payload.active is not None and payload.active != seller.active:
        audit.record(
            session,
            actor=user,
            action="seller.active",
            entity="seller",
            entity_id=seller.id,
            field="active",
            old=seller.active,
            new=payload.active,
            note=seller.name,
        )
        seller.active = payload.active
        # Standing a seller down takes their offers out of the running with
        # them. Left active, the cheapest card in the shop could belong to
        # somebody we have stopped dealing with.
        if not payload.active:
            _withdraw_offers(session, seller)

    session.add(seller)
    if payload.user_phone:
        _link_account(session, user, seller, payload.user_phone)
    session.commit()
    session.refresh(seller)
    return _seller_out(session, seller)


def _link_account(
    session: SessionDep, actor: User, seller: Seller, phone: str
) -> None:
    """Point an account at this seller, and give it the role.

    Linking *is* what makes somebody a seller — there is no meaningful state
    where an account is attached to a seller and cannot act as one — so the
    role comes with the link rather than needing a second step through a
    door that does not exist. It is a privilege change, so it is logged.
    """
    account = session.exec(select(User).where(User.phone == phone)).first()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("user_not_found"))

    taken = session.exec(
        select(Seller).where(Seller.user_id == account.id, Seller.id != seller.id)
    ).first()
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("account_taken"))

    if account.role is not UserRole.SELLER:
        audit.record(
            session,
            actor=actor,
            action="user.role",
            entity="user",
            entity_id=account.id,
            field="role",
            old=account.role,
            new=UserRole.SELLER,
            note=f"{seller.name} bilan bog'landi",
        )
        account.role = UserRole.SELLER
        session.add(account)

    seller.user_id = account.id
    session.add(seller)


def _withdraw_offers(session: SessionDep, seller: Seller) -> None:
    touched: set[int] = set()
    for offer in session.exec(select(Offer).where(Offer.seller_id == seller.id)).all():
        if offer.active:
            offer.active = False
            session.add(offer)
            touched.add(offer.product_id)
    session.commit()
    for product_id in touched:
        of.refresh(session, product_id)


# --------------------------------------------------------------------------- the catalogue


@router.get(
    "/catalog/products",
    response_model=s.Page[s.AdminProductOut],
    summary="Every card, whatever its state — and the moderation queue",
)
def list_products(
    user: AdminUser,
    session: SessionDep,
    status_filter: ProductStatus | None = Query(
        None, alias="status", description="`moderating` is the queue"
    ),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.AdminProductOut]:
    stmt = select(Product)
    if status_filter is not None:
        stmt = stmt.where(Product.status == status_filter)
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Product.title).like(needle) | func.lower(Product.sku).like(needle)
        )
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    # Oldest first when it is a queue, newest first when it is a catalogue.
    order = (
        col(Product.created_at)
        if status_filter is ProductStatus.MODERATING
        else col(Product.created_at).desc()
    )
    rows = session.exec(
        stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return s.Page[s.AdminProductOut](
        items=[_product_out(session, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get("/catalog/products/{product_id}", response_model=s.AdminProductOut)
def get_product(product_id: int, user: AdminUser, session: SessionDep) -> s.AdminProductOut:
    return _product_out(session, _product(session, product_id))


@router.post(
    "/catalog/products",
    response_model=s.AdminProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Write a new card",
)
def create_product(
    payload: s.ProductCreateIn, user: AdminUser, session: SessionDep
) -> s.AdminProductOut:
    """Created as a draft. Publishing it is a separate act with its own door."""
    return _create_card(session, user, payload, ProductStatus.DRAFT, proposed_by=None)


@router.post(
    "/catalog/proposals",
    response_model=s.AdminProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Suggest a card for the catalogue (seller)",
)
def propose_product(
    payload: s.ProductProposeIn, user: SellerUser, session: SessionDep
) -> s.AdminProductOut:
    """A suggestion, not a card in the shop.

    It lands in moderation whoever sends it — an admin included, because an
    admin who wanted it published outright would use the door marked that way.
    """
    seller = None
    if user.role is UserRole.SELLER:
        seller = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
        if seller is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
            )
    return _create_card(
        session, user, payload, ProductStatus.MODERATING, proposed_by=seller
    )


def _create_card(
    session: SessionDep,
    actor: User,
    payload: s.ProductCreateIn,
    state: ProductStatus,
    *,
    proposed_by: Seller | None,
) -> s.AdminProductOut:
    if session.exec(select(Product).where(Product.sku == payload.sku)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("sku_exists"))
    category = _category(session, payload.category_slug)
    brand = _brand(session, payload.brand_slug) if payload.brand_slug else None

    product = Product(
        sku=payload.sku,
        title=payload.title,
        subtitle=payload.subtitle,
        description=payload.description,
        category_id=category.id,
        brand_id=brand.id if brand else None,
        # Seeding the cache, not setting a price: the figure a shopper pays
        # comes from an offer, and `offers.refresh` overwrites this the moment
        # one exists. It is here so a card with no offers has a number rather
        # than a nought.
        price=payload.price,
        old_price=payload.old_price,
        badge=payload.badge,
        warranty=payload.warranty,
        is_original=payload.is_original,
        free_delivery=payload.free_delivery,
        next_day_delivery=payload.next_day_delivery,
        # Nothing on the shelf until the warehouse books something in.
        stock_left=0,
        in_stock=False,
        status=state,
        proposed_by_id=proposed_by.id if proposed_by else None,
        seller=proposed_by.name if proposed_by else "Mini Bozor",
    )
    session.add(product)
    session.commit()
    session.refresh(product)

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
    return _product_out(session, product)


@router.patch("/catalog/products/{product_id}", response_model=s.AdminProductOut)
def update_product(
    product_id: int, payload: s.ProductUpdateIn, user: AdminUser, session: SessionDep
) -> s.AdminProductOut:
    product = _product(session, product_id)

    if payload.category_slug is not None:
        product.category_id = _category(session, payload.category_slug).id
    if payload.brand_slug is not None:
        product.brand_id = _brand(session, payload.brand_slug).id
    for field in (
        "title",
        "subtitle",
        "description",
        "badge",
        "warranty",
        "is_original",
        "free_delivery",
        "next_day_delivery",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(product, field, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    return _product_out(session, product)


@router.post(
    "/catalog/products/{product_id}/status",
    response_model=s.AdminProductOut,
    summary="Publish, refuse, or withdraw a card",
)
def set_product_status(
    product_id: int, payload: s.ProductStatusIn, user: AdminUser, session: SessionDep
) -> s.AdminProductOut:
    """The moderation decision, and the only way a card's state moves.

    A refusal needs a reason because the seller who proposed it reads it and
    has to know what to fix. Which moves are legal is in
    ``app.transitions.PRODUCT_TRANSITIONS`` and nowhere else.
    """
    product = _product(session, product_id)
    tr.ensure(tr.PRODUCT_TRANSITIONS, product.status, payload.status)

    if payload.status is ProductStatus.REJECTED and not payload.reason.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("reason_required"))

    audit.record(
        session,
        actor=user,
        action="product.status",
        entity="product",
        entity_id=product.id,
        field="status",
        old=product.status,
        new=payload.status,
        note=payload.reason or product.sku,
    )
    product.status = payload.status
    if payload.status is ProductStatus.REJECTED:
        product.moderation_note = payload.reason.strip()
    elif payload.status is ProductStatus.PUBLISHED:
        product.moderation_note = ""
    session.add(product)
    session.commit()

    # A card leaving or entering the shop changes what its offers can do, so
    # the cached figures are recomputed rather than left describing the old
    # answer.
    of.refresh(session, product.id)
    session.commit()
    session.refresh(product)
    return _product_out(session, product)


# --------------------------------------------------------------------------- categories


@router.post(
    "/catalog/categories",
    response_model=s.CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: s.CategoryWriteIn, user: AdminUser, session: SessionDep
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
    return sv.category_out(session, row)


@router.patch("/catalog/categories/{slug}", response_model=s.CategoryOut)
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
    session.add(row)
    session.commit()
    session.refresh(row)
    return sv.category_out(session, row)


@router.delete("/catalog/categories/{slug}", response_model=s.Message)
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
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- brands


@router.post(
    "/catalog/brands", response_model=s.BrandOut, status_code=status.HTTP_201_CREATED
)
def create_brand(
    payload: s.BrandWriteIn, user: AdminUser, session: SessionDep
) -> s.BrandOut:
    if session.exec(select(Brand).where(Brand.slug == payload.slug)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
    row = Brand(slug=payload.slug, name=payload.name)
    session.add(row)
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.patch("/catalog/brands/{slug}", response_model=s.BrandOut)
def update_brand(
    slug: str, payload: s.BrandWriteIn, user: AdminUser, session: SessionDep
) -> s.BrandOut:
    row = _brand(session, slug)
    row.name = payload.name
    session.add(row)
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.delete("/catalog/brands/{slug}", response_model=s.Message)
def delete_brand(slug: str, user: AdminUser, session: SessionDep) -> s.Message:
    row = _brand(session, slug)
    if session.exec(select(Product).where(Product.brand_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("brand_in_use"))
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- what a card is made of


@router.post(
    "/catalog/products/{product_id}/images",
    response_model=list[str],
    status_code=status.HTTP_201_CREATED,
)
def add_image(
    product_id: int, payload: s.ImageWriteIn, user: AdminUser, session: SessionDep
) -> list[str]:
    product = _product(session, product_id)
    session.add(
        ProductImage(product_id=product.id, url=payload.url, sort=payload.sort)
    )
    session.commit()
    return _image_urls(session, product.id)


@router.delete("/catalog/products/{product_id}/images/{image_id}", response_model=list[str])
def remove_image(
    product_id: int, image_id: int, user: AdminUser, session: SessionDep
) -> list[str]:
    product = _product(session, product_id)
    row = session.get(ProductImage, image_id)
    if row is None or row.product_id != product.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("image_not_found"))
    session.delete(row)
    session.commit()
    return _image_urls(session, product.id)


@router.post(
    "/catalog/products/{product_id}/variants",
    response_model=list[s.VariantOut],
    status_code=status.HTTP_201_CREATED,
)
def add_variant(
    product_id: int, payload: s.VariantWriteIn, user: AdminUser, session: SessionDep
) -> list[s.VariantOut]:
    """Add a colour, or a size of a colour.

    Refused if it would move where the shelf is counted. A product whose
    leaves are colours has its stock recorded on those colours; adding the
    first size makes the sizes the leaves, and every existing count would then
    be sitting a level above where the ledger expects to find it — with no way
    to say how the colour's stock should divide between the new sizes. Add the
    sizes before the stock, or count the shelf out and back in.
    """
    product = _product(session, product_id)
    leaves = of.leaf_variants(session, product.id)

    parent = None
    if payload.parent_id is not None:
        parent = session.get(ProductVariant, payload.parent_id)
        if parent is None or parent.product_id != product.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
            )

    if payload.kind is VariantKind.SIZE:
        colours = [v for v in leaves if v.kind is VariantKind.COLOR]
        if colours:
            if parent is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, i18n.label("size_needs_a_colour")
                )
            if _has_any_stock(session, product.id):
                raise HTTPException(
                    status.HTTP_409_CONFLICT, i18n.label("variant_would_move_the_count")
                )

    session.add(
        ProductVariant(
            product_id=product.id,
            kind=payload.kind,
            label=payload.label,
            value=payload.value,
            image_url=payload.image_url,
            parent_id=payload.parent_id,
            sort=payload.sort,
            # Counted by the offers that carry it, not here.
            stock_left=None,
            in_stock=True,
        )
    )
    session.commit()
    of.refresh(session, product.id)
    session.commit()
    return _variants_out(session, product.id)


@router.delete(
    "/catalog/products/{product_id}/variants/{variant_id}",
    response_model=list[s.VariantOut],
)
def remove_variant(
    product_id: int, variant_id: int, user: AdminUser, session: SessionDep
) -> list[s.VariantOut]:
    """Refused once anything has happened to it.

    A variant named by a movement or by an order line is part of a record: the
    ledger would stop explaining its own totals and an old order would point
    at a row that is not there. Take it out of stock instead — that is what
    "we do not sell this any more" means when it has been sold before.
    """
    product = _product(session, product_id)
    row = session.get(ProductVariant, variant_id)
    if row is None or row.product_id != product.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
        )
    if session.exec(
        select(StockMovement).where(StockMovement.variant_id == row.id)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("variant_has_history"))
    if session.exec(
        select(OrderItem).where(
            (OrderItem.variant_id == row.id) | (OrderItem.color_variant_id == row.id)
        )
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("variant_has_history"))
    if session.exec(select(ProductVariant).where(ProductVariant.parent_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("variant_has_children"))

    for offer_row in session.exec(
        select(OfferVariant).where(OfferVariant.variant_id == row.id)
    ).all():
        session.delete(offer_row)
    session.delete(row)
    session.commit()
    of.refresh(session, product.id)
    session.commit()
    return _variants_out(session, product.id)


@router.put(
    "/catalog/products/{product_id}/specs",
    response_model=list[s.SpecOut],
    summary="Replace the spec table, in order",
)
def replace_specs(
    product_id: int, payload: s.SpecsReplaceIn, user: AdminUser, session: SessionDep
) -> list[s.SpecOut]:
    product = _product(session, product_id)
    for row in session.exec(
        select(ProductSpec).where(ProductSpec.product_id == product.id)
    ).all():
        session.delete(row)
    for index, spec in enumerate(payload.specs):
        session.add(
            ProductSpec(
                product_id=product.id, key=spec.key, value=spec.value, sort=index
            )
        )
    session.commit()
    return [
        s.SpecOut(key=row.key, value=row.value)
        for row in session.exec(
            select(ProductSpec)
            .where(ProductSpec.product_id == product.id)
            .order_by(col(ProductSpec.sort))
        ).all()
    ]


# --------------------------------------------------------------------------- helpers


def _seller(session: SessionDep, seller_id: int) -> Seller:
    row = session.get(Seller, seller_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("seller_not_found"))
    return row


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
    return any(
        offer.stock_left
        for offer in of.offers_for(session, product_id, active_only=False)
    )


def _image_urls(session: SessionDep, product_id: int) -> list[str]:
    return [
        url
        for url in (
            sv.media_url(row.url)
            for row in session.exec(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(col(ProductImage.sort), col(ProductImage.id))
            ).all()
        )
        if url
    ]


def _variants_out(session: SessionDep, product_id: int) -> list[s.VariantOut]:
    rows = session.exec(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(col(ProductVariant.sort), col(ProductVariant.id))
    ).all()
    return [
        s.VariantOut(
            id=row.id,
            kind=row.kind,
            label=row.label,
            value=row.value,
            image_url=sv.media_url(row.image_url),
            in_stock=row.in_stock,
            stock_left=row.stock_left,
            parent_id=row.parent_id,
        )
        for row in rows
    ]


def _seller_out(session: SessionDep, seller: Seller) -> s.AdminSellerOut:
    account = session.get(User, seller.user_id) if seller.user_id else None
    offers = session.exec(
        select(func.count()).select_from(Offer).where(Offer.seller_id == seller.id)
    ).one()
    return s.AdminSellerOut(
        id=seller.id,
        name=seller.name,
        phone=seller.phone,
        commission_percent=seller.commission_percent,
        active=seller.active,
        user_phone=account.phone if account else None,
        user_name=(account.full_name or account.phone) if account else None,
        offer_count=int(offers),
        created_at=seller.created_at,
    )


def _product_out(session: SessionDep, product: Product) -> s.AdminProductOut:
    category = session.get(Category, product.category_id)
    brand = session.get(Brand, product.brand_id) if product.brand_id else None
    proposer = (
        session.get(Seller, product.proposed_by_id) if product.proposed_by_id else None
    )
    offers = session.exec(
        select(func.count()).select_from(Offer).where(Offer.product_id == product.id)
    ).one()
    images = session.exec(
        select(func.count())
        .select_from(ProductImage)
        .where(ProductImage.product_id == product.id)
    ).one()
    variants = session.exec(
        select(func.count())
        .select_from(ProductVariant)
        .where(ProductVariant.product_id == product.id)
    ).one()
    return s.AdminProductOut(
        id=product.id,
        sku=product.sku,
        title=product.title,
        subtitle=product.subtitle,
        status=product.status,
        next_statuses=tr.next_states(tr.PRODUCT_TRANSITIONS, product.status),
        category_slug=category.slug if category else "",
        brand_slug=brand.slug if brand else None,
        price=product.price,
        old_price=product.old_price,
        stock_left=product.stock_left,
        offer_count=int(offers),
        proposed_by=(
            s.SellerOut(id=proposer.id, name=proposer.name) if proposer else None
        ),
        moderation_note=product.moderation_note,
        image_count=int(images),
        variant_count=int(variants),
        created_at=product.created_at,
    )
