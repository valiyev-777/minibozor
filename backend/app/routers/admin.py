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

**A card is written in three languages or it is written badly.** The apps ask
for Uzbek, Russian or English; a row carries its Uzbek and the ``translation``
table carries the other two. Every write here takes them together, because a
translation asked for as a second step is a translation nobody does — and
every delete takes them with it, because SQLite hands a deleted row's id back
out again. See ``app.i18n`` for both halves.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n, roles
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

    # Through ``app.roles`` rather than straight onto the row: this is the
    # second door a role goes through, and the rule that the last admin cannot
    # be stood down has to hold at both. An admin who linked their own account
    # to a seller would otherwise demote themselves out of the panel by
    # filling in a form about somebody else's shop.
    roles.assign(
        session,
        actor=actor,
        user=account,
        role=UserRole.SELLER,
        note=f"{seller.name} bilan bog'landi",
    )

    if seller.user_id != account.id:
        # Stamped with the link, not with the seller row: the cabinet answers
        # "since when am I selling here" from this, and re-pointing a shop at
        # a different account starts that again.
        seller.linked_at = sv.utcnow()
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


@router.get(
    "/catalog/summary",
    response_model=s.CatalogSummaryOut,
    summary="How many cards are in each state",
)
def catalog_summary(user: AdminUser, session: SessionDep) -> s.CatalogSummaryOut:
    """For the badge on the moderation row.

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


@router.get("/catalog/products/{product_id}", response_model=s.AdminProductDetailOut)
def get_product(
    product_id: int, user: AdminUser, session: SessionDep
) -> s.AdminProductDetailOut:
    """One card, with the fields only the edit form needs.

    The list shape stays as it was — a description per row is prose fetched to
    draw a table — so this is the richer of the two, on the endpoint an editor
    calls one card at a time.
    """
    product = _product(session, product_id)
    return s.AdminProductDetailOut(
        **_product_out(session, product).model_dump(),
        description=product.description,
        badge=product.badge,
        warranty=product.warranty,
        is_original=product.is_original,
        free_delivery=product.free_delivery,
        next_day_delivery=product.next_day_delivery,
        translations=i18n.stored(session, "product", product.id),
    )


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

    i18n.write(session, "product", product.id, _texts(payload.translations))
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


@router.get(
    "/catalog/categories",
    response_model=list[s.AdminCategoryOut],
    summary="Every category, flat, in the words the rows hold",
)
def list_categories(user: AdminUser, session: SessionDep) -> list[s.AdminCategoryOut]:
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
    i18n.write(session, "category", row.id, _texts(payload.translations))
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
    i18n.write(session, "category", row.id, _texts(payload.translations))
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
    i18n.forget(session, "category", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- brands


@router.get(
    "/catalog/brands",
    response_model=list[s.AdminBrandOut],
    summary="Every brand, with how many cards carry it",
)
def list_brands(user: AdminUser, session: SessionDep) -> list[s.AdminBrandOut]:
    counts = dict(
        session.exec(
            select(Product.brand_id, func.count()).group_by(col(Product.brand_id))
        ).all()
    )
    rows = session.exec(select(Brand).order_by(col(Brand.name))).all()
    return [
        s.AdminBrandOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            product_count=int(counts.get(row.id, 0)),
        )
        for row in rows
    ]


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
    i18n.write(session, "brand", row.id, _texts(payload.translations))
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.patch("/catalog/brands/{slug}", response_model=s.BrandOut)
def update_brand(
    slug: str, payload: s.BrandWriteIn, user: AdminUser, session: SessionDep
) -> s.BrandOut:
    row = _brand(session, slug)
    row.name = payload.name
    i18n.write(session, "brand", row.id, _texts(payload.translations))
    session.add(row)
    session.commit()
    session.refresh(row)
    return s.BrandOut(id=row.id, slug=row.slug, name=row.name)


@router.delete("/catalog/brands/{slug}", response_model=s.Message)
def delete_brand(slug: str, user: AdminUser, session: SessionDep) -> s.Message:
    row = _brand(session, slug)
    if session.exec(select(Product).where(Product.brand_id == row.id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("brand_in_use"))
    i18n.forget(session, "brand", row.id)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- what a card is made of


@router.get(
    "/catalog/products/{product_id}/images",
    response_model=list[s.AdminImageOut],
    summary="The gallery, with the ids to edit it by",
)
def list_images(
    product_id: int, user: AdminUser, session: SessionDep
) -> list[s.AdminImageOut]:
    """The write endpoints answer with bare URLs, which redraws a gallery and
    does not edit one: ``DELETE .../images/{image_id}`` has always been here
    and nothing ever told the panel what ``image_id`` was."""
    product = _product(session, product_id)
    return [
        s.AdminImageOut(id=row.id, url=sv.media_url(row.url) or row.url, sort=row.sort)
        for row in _image_rows(session, product.id)
    ]


@router.put(
    "/catalog/products/{product_id}/images/order",
    response_model=list[s.AdminImageOut],
    summary="Set the order of the photographs, first one being the cover",
)
def reorder_images(
    product_id: int, payload: s.ReorderIn, user: AdminUser, session: SessionDep
) -> list[s.AdminImageOut]:
    """The whole list, the way the showcase takes its orders.

    Every row named once and none left out: a partial list would leave the
    rest holding numbers that mean something else. The first photograph is the
    one every tile in the shop shows, so this is not only arrangement.
    """
    product = _product(session, product_id)
    rows = {row.id: row for row in _image_rows(session, product.id)}
    if len(set(payload.ids)) != len(payload.ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("order_repeats"))
    if set(payload.ids) != set(rows):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("order_incomplete"))
    for position, image_id in enumerate(payload.ids):
        rows[image_id].sort = position
        session.add(rows[image_id])
    session.commit()
    return list_images(product_id, user, session)


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


@router.get(
    "/catalog/products/{product_id}/variants",
    response_model=s.AdminVariantsOut,
    summary="The colour and size tree, and what may be done to it",
)
def list_variants(
    product_id: int, user: AdminUser, session: SessionDep
) -> s.AdminVariantsOut:
    """Every variant with its own delete guard, and the tree's size guard.

    Both answers come from the functions the write endpoints refuse with, so
    a button greyed out here and a 409 from there are the same rule rather
    than two copies of it. The editor can then say why in advance, which is
    the whole difference between a form that explains itself and one that
    waits to be wrong at.
    """
    product = _product(session, product_id)
    rows = session.exec(
        select(ProductVariant)
        .where(ProductVariant.product_id == product.id)
        .order_by(col(ProductVariant.sort), col(ProductVariant.id))
    ).all()
    blocked = _size_block(session, product.id)
    return s.AdminVariantsOut(
        variants=[
            s.AdminVariantOut(
                id=row.id,
                kind=row.kind,
                label=row.label,
                value=row.value,
                image_url=sv.media_url(row.image_url),
                parent_id=row.parent_id,
                sort=row.sort,
                stock_left=row.stock_left,
                in_stock=row.in_stock,
                can_delete=not _variant_block(session, row),
                blocked_reason=_variant_block(session, row),
            )
            for row in rows
        ],
        can_add_size=not blocked,
        size_blocked_reason=blocked,
    )


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
            blocked = _size_block(session, product.id)
            if blocked:
                raise HTTPException(status.HTTP_409_CONFLICT, blocked)

    row = ProductVariant(
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
    session.add(row)
    session.commit()
    session.refresh(row)
    i18n.write(session, "variant", row.id, _texts(payload.translations))
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
    # The same function the editor greys the button out with, so what it says
    # and what this refuses cannot drift apart.
    blocked = _variant_block(session, row)
    if blocked:
        raise HTTPException(status.HTTP_409_CONFLICT, blocked)

    for offer_row in session.exec(
        select(OfferVariant).where(OfferVariant.variant_id == row.id)
    ).all():
        session.delete(offer_row)
    i18n.forget(session, "variant", row.id)
    session.delete(row)
    session.commit()
    of.refresh(session, product.id)
    session.commit()
    return _variants_out(session, product.id)


@router.get(
    "/catalog/products/{product_id}/specs",
    response_model=list[s.AdminSpecOut],
    summary="The spec table as it stands, translations included",
)
def list_specs(
    product_id: int, user: AdminUser, session: SessionDep
) -> list[s.AdminSpecOut]:
    """A draft card cannot be read through ``/products/{id}``: that path is
    narrowed to what is in the shop, which is the point of it. So the editor
    needs its own way to see the rows it is about to replace.

    With the translations, because replacing is all this table supports. The
    editor has to send back every row it means to keep and every word in every
    language on it; anything it could not read is a thing it would delete by
    saving something else.
    """
    product = _product(session, product_id)
    rows = session.exec(
        select(ProductSpec)
        .where(ProductSpec.product_id == product.id)
        .order_by(col(ProductSpec.sort))
    ).all()
    return [
        s.AdminSpecOut(
            id=row.id,
            key=row.key,
            value=row.value,
            translations=i18n.stored(session, "spec", row.id),
        )
        for row in rows
    ]


@router.put(
    "/catalog/products/{product_id}/specs",
    response_model=list[s.SpecOut],
    summary="Replace the spec table, in order",
)
def replace_specs(
    product_id: int, payload: s.SpecsReplaceIn, user: AdminUser, session: SessionDep
) -> list[s.SpecOut]:
    product = _product(session, product_id)
    # The old rows' translations go with them. Their ids come back around —
    # SQLite reuses them — and a spec table replaced in place would otherwise
    # inherit the Russian of whatever used to sit in that slot.
    for row in session.exec(
        select(ProductSpec).where(ProductSpec.product_id == product.id)
    ).all():
        i18n.forget(session, "spec", row.id)
        session.delete(row)
    session.commit()

    written: list[tuple[ProductSpec, dict]] = []
    for index, spec in enumerate(payload.specs):
        row = ProductSpec(
            product_id=product.id, key=spec.key, value=spec.value, sort=index
        )
        session.add(row)
        written.append((row, _texts(spec.translations)))
    session.commit()
    for row, texts in written:
        session.refresh(row)
        i18n.write(session, "spec", row.id, texts)
    session.commit()
    return _specs_out(session, product.id)


# --------------------------------------------------------------------------- translations


@router.get(
    "/catalog/translations/{entity}/{entity_id}",
    response_model=s.TranslationsOut,
    summary="What Russian and English a row already has",
)
def get_translations(
    entity: str, entity_id: int, user: AdminUser, session: SessionDep
) -> s.TranslationsOut:
    """The one read the panel cannot get from the catalogue endpoints.

    Those answer in a single language and fall back to Uzbek without saying
    so, which is exactly right for a shopper and no use to somebody trying to
    see what is still missing. This returns the Uzbek on the row beside every
    translation held for it, so an editor can show three columns and mark the
    empty cells.
    """
    if entity not in i18n.WRITABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("doc_not_found"))
    source = _source_text(session, entity, entity_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("doc_not_found"))
    return s.TranslationsOut(
        entity=entity,
        entity_id=entity_id,
        uz=source,
        translations=i18n.stored(session, entity, entity_id),
    )


# What the Uzbek side of each translatable row is called on the row itself.
# The keys are the fields ``i18n.WRITABLE`` allows, which are in turn the
# fields the read path passes through ``i18n.t`` — one list, stated three
# times only because each layer needs it in a different shape.
_SOURCES: dict[str, type] = {
    "product": Product,
    "category": Category,
    "brand": Brand,
    "variant": ProductVariant,
    "spec": ProductSpec,
}


def _source_text(session: SessionDep, entity: str, entity_id: int) -> dict[str, str] | None:
    row = session.get(_SOURCES[entity], entity_id)
    if row is None:
        return None
    return {
        field: getattr(row, field) or ""
        for field in sorted(i18n.WRITABLE[entity])
    }


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


def _variant_block(session: SessionDep, variant: ProductVariant) -> str:
    """Why this variant cannot be deleted, as a sentence — or "" if it can.

    One function, two callers: the delete endpoint refuses with it, and the
    editor greys its button out with it. Written that way round on purpose —
    a rule the browser re-derives is a second copy of the rule, and it is the
    copy that goes stale.

    A variant named by a movement or an order line is part of a record. The
    ledger would stop explaining its own totals and an old order would point
    at a row that is not there, so what "we do not sell this any more" means
    here is taking it out of stock, not deleting it.
    """
    if session.exec(
        select(StockMovement).where(StockMovement.variant_id == variant.id)
    ).first():
        return i18n.label("variant_has_history")
    if session.exec(
        select(OrderItem).where(
            (OrderItem.variant_id == variant.id)
            | (OrderItem.color_variant_id == variant.id)
        )
    ).first():
        return i18n.label("variant_has_history")
    if session.exec(
        select(ProductVariant).where(ProductVariant.parent_id == variant.id)
    ).first():
        return i18n.label("variant_has_children")
    return ""


def _size_block(session: SessionDep, product_id: int) -> str:
    """Why a first size cannot be added under a colour — or "" if it can.

    The shelf is counted on the leaves. While the leaves are colours, the
    counts sit on the colours; adding the first size makes the sizes the
    leaves and every existing count is suddenly a level above where the ledger
    looks for it, with nothing to say how a colour's twelve should divide
    between the sizes being added.

    Empty once the product already has sizes: the leaves have moved, and a
    second size changes nothing about where counting happens.
    """
    leaves = of.leaf_variants(session, product_id)
    if not any(v.kind is VariantKind.COLOR for v in leaves):
        return ""
    if _has_any_stock(session, product_id):
        return i18n.label("variant_would_move_the_count")
    return ""


def _has_any_stock(session: SessionDep, product_id: int) -> bool:
    return any(
        offer.stock_left
        for offer in of.offers_for(session, product_id, active_only=False)
    )


def _image_rows(session: SessionDep, product_id: int) -> list[ProductImage]:
    return list(
        session.exec(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(col(ProductImage.sort), col(ProductImage.id))
        ).all()
    )


def _image_urls(session: SessionDep, product_id: int) -> list[str]:
    return [
        url
        for url in (sv.media_url(row.url) for row in _image_rows(session, product_id))
        if url
    ]


def _specs_out(session: SessionDep, product_id: int) -> list[s.SpecOut]:
    return [
        s.SpecOut(key=row.key, value=row.value)
        for row in session.exec(
            select(ProductSpec)
            .where(ProductSpec.product_id == product_id)
            .order_by(col(ProductSpec.sort))
        ).all()
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
