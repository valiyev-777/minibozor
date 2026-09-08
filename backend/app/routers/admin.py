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
from app.deps import AdminUser, CatalogReader, SellerUser, SessionDep
from app.models import (
    Brand,
    Category,
    Offer,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    Seller,
    User,
    UserRole,
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


@router.get(
    "/catalog/proposals",
    response_model=s.Page[s.AdminProductOut],
    summary="What I proposed and what became of it (seller)",
)
def list_proposals(
    user: SellerUser,
    session: SessionDep,
    status_filter: ProductStatus | None = Query(
        None, alias="status", description="`rejected` is the one that needs reading"
    ),
    q: str | None = Query(None, description="Part of a title or a SKU"),
    seller_id: int | None = Query(
        None, description="Admins only: whose proposals to read"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.AdminProductOut]:
    """The other half of proposing a card, which did not exist.

    A seller could post a proposal and then never see it again. Approved, it
    turns up in the catalogue by itself and they can find it there. **Refused,
    it went nowhere they could look** — and the refusal carries the one thing
    they need, which is the reason it was refused. So a seller was being asked
    to fix something without being told what was wrong with it, and the only
    way to find out was to ask an admin directly.

    Every state, not just the refused ones: a proposal in moderation is the
    answer to "has anybody looked at it yet", and one that was published is
    how they confirm the card in the shop is theirs. ``moderation_note`` is on
    every row and is filled in on exactly the refusals.

    Scoped to the caller's own shop, and that is not a filter they choose: for
    a seller these are the only proposals that exist. An admin has no shop, so
    they read every seller's proposals — the whole queue with its provenance —
    and may narrow it to one with ``seller_id``.
    """
    stmt = select(Product)
    mine = _own_seller_or_none(session, user)
    if mine is not None:
        stmt = stmt.where(Product.proposed_by_id == mine.id)
    elif seller_id is not None:
        stmt = stmt.where(Product.proposed_by_id == _seller(session, seller_id).id)
    else:
        # Everything anybody proposed, and nothing the platform wrote itself:
        # a draft an admin started is not a proposal and has no reason to be
        # in a list about somebody else's suggestions.
        stmt = stmt.where(col(Product.proposed_by_id).is_not(None))
    if status_filter is not None:
        stmt = stmt.where(Product.status == status_filter)
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Product.title).like(needle) | func.lower(Product.sku).like(needle)
        )

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(Product.created_at).desc(), col(Product.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.AdminProductOut](
        items=[_product_out(session, row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


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
    seller = _own_seller_or_none(session, user)
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


@router.get(
    "/catalog/categories",
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
def list_brands(user: CatalogReader, session: SessionDep) -> list[s.AdminBrandOut]:
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


def _own_seller_or_none(session: SessionDep, user: User) -> Seller | None:
    """The shop this account belongs to, or None when it has no shop of its own.

    None means an admin, and an admin reads across every seller. A *seller*
    with no ``sellers`` row is not scoped to nothing — that would hand them
    everybody's proposals — so it is refused.
    """
    if user.role is not UserRole.SELLER:
        return None
    row = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
    if row is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
        )
    return row


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


def _image_rows(session: SessionDep, product_id: int) -> list[ProductImage]:
    return list(
        session.exec(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(col(ProductImage.sort), col(ProductImage.id))
        ).all()
    )


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
