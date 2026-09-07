"""Pricing and stocking goods — where the seller role gets its first real job.

Offers existed but nothing could make one: the catalogue was split by a
migration script and edited from the database afterwards. These are the
endpoints that change that, and the reason they are their own file is the line
running through the middle of them:

* **A seller sets the price.** Their own offer, nobody else's. Price, the
  struck-through price beside it, and whether they are still selling.
* **The warehouse sets the count.** Under this model the goods sit in our
  warehouse and we deliver them, so a stock figure changes when something is
  booked in or out — never because a seller said so. A seller who could write
  a stock figure could promise goods nobody has received.

That boundary is drawn now, before the warehouse module exists, because a
permission line is easy to place and hard to move: afterwards it means finding
every caller that grew up on the wrong side of it.

Every price and every count is written to ``audit_log``, and every change ends
with ``app.offers.refresh`` — the one function allowed to write the cached
figures on ``Product``. There is no second copy of that logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import audit, i18n
from app import offers as of
from app import schemas as s
from app import services as sv
from app import stock as st
from app.deps import SellerUser, SessionDep, StockViewer, WarehouseUser
from app.models import (
    Brand,
    Category,
    Offer,
    OfferVariant,
    Product,
    ProductVariant,
    Seller,
    StockMovementKind,
    User,
    UserRole,
)

router = APIRouter(prefix="/staff", tags=["staff"])


# --------------------------------------------------------------------------- the seller's side


@router.get(
    "/sellers/me",
    response_model=s.SellerMeOut,
    summary="Which shop am I",
)
def my_seller(user: SellerUser, session: SessionDep) -> s.SellerMeOut:
    """The seller's own row, and the first thing their cabinet asks for.

    ``/staff/me`` answers with the user — a phone number and a role — and
    nothing about the shop behind it, so a seller who had just been taken on
    could not confirm they were linked to the right one.

    Declared here rather than in ``admin.py`` beside ``/sellers/{seller_id}``,
    and this router is registered first, so ``me`` is matched as a literal
    before that path's integer. An admin has no shop of their own; they read
    any seller's row through the admin door.
    """
    if user.role is UserRole.ADMIN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("admin_has_no_seller")
        )
    seller = _own_seller(session, user)
    offers = session.exec(
        select(func.count()).select_from(Offer).where(Offer.seller_id == seller.id)
    ).one()
    return s.SellerMeOut(
        id=seller.id,
        name=seller.name,
        phone=seller.phone,
        commission_percent=seller.commission_percent,
        active=seller.active,
        linked_at=seller.linked_at,
        created_at=seller.created_at,
        offer_count=int(offers),
    )


@router.get(
    "/catalog/browse",
    response_model=s.Page[s.SellerCatalogOut],
    summary="The catalogue as a seller looking for something to stock sees it",
)
def browse_catalogue(
    user: SellerUser,
    session: SessionDep,
    q: str | None = Query(None, description="Part of a title or a SKU"),
    category: str | None = Query(None, description="Category slug"),
    mine: bool | None = Query(
        None, description="true: only cards I already offer; false: only the rest"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=60),
) -> s.Page[s.SellerCatalogOut]:
    """Published cards only.

    A draft, a proposal in moderation, a refused card and a withdrawn one are
    somebody else's unfinished work; a seller attaching an offer to one would
    be pricing something that is not in the shop and may never be. This goes
    through the same ``in_the_shop`` narrowing every customer path uses, which
    is why there is one function for it rather than a ``where`` repeated here.

    Not the admin's listing. That one answers with the Uzbek on the row
    because an editor is about to write it back, and includes every state so
    the moderation queue has somewhere to live. This is read to recognise a
    product, so it is translated and carries the photograph.
    """
    seller = _own_seller_or_none(session, user)

    stmt = sv.in_the_shop(select(Product))
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Product.title).like(needle) | func.lower(Product.sku).like(needle)
        )
    if category:
        row = session.exec(select(Category).where(Category.slug == category)).first()
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, i18n.label("category_not_found")
            )
        stmt = stmt.where(Product.category_id == row.id)

    if mine is not None and seller is not None:
        owned = session.exec(
            select(Offer.product_id).where(Offer.seller_id == seller.id)
        ).all()
        stmt = (
            stmt.where(col(Product.id).in_(owned or [-1]))
            if mine
            else stmt.where(col(Product.id).notin_(owned or [-1]))
        )

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(Product.sold_count).desc(), col(Product.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.SellerCatalogOut](
        items=[_catalogue_out(session, row, seller) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get(
    "/catalog/browse/{product_id}",
    response_model=s.SellerCatalogDetailOut,
    summary="One card, with the leaves an offer has to name",
)
def browse_product(
    product_id: int, user: SellerUser, session: SessionDep
) -> s.SellerCatalogDetailOut:
    """Everything the offer form binds to, in one request.

    ``leaf_ids`` is the field that closes the gap this endpoint exists for:
    an offer must name every leaf and nothing told a seller what the leaves
    were, so the rule could only be discovered by being refused with a 422.

    The offers list is the same one the shop shows to anybody, with the same
    seller names on it — see ``SellerCatalogOut`` for why that is not hidden.
    """
    product = session.get(Product, product_id)
    if not sv.is_in_the_shop(product):
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    seller = _own_seller_or_none(session, user)
    variants = session.exec(
        select(ProductVariant)
        .where(ProductVariant.product_id == product.id)
        .order_by(col(ProductVariant.sort), col(ProductVariant.id))
    ).all()
    leaves = {v.id for v in of.leaf_variants(session, product.id)}
    winner = of.winning_offer(session, product.id)

    return s.SellerCatalogDetailOut(
        **_catalogue_out(session, product, seller).model_dump(),
        description=i18n.t(session, "product", product.id, "description", product.description),
        variants=[
            s.SellerVariantOut(
                id=v.id,
                kind=v.kind,
                label=i18n.t(session, "variant", v.id, "label", v.label),
                value=v.value,
                image_url=sv.media_url(v.image_url),
                parent_id=v.parent_id,
                is_leaf=v.id in leaves,
            )
            for v in variants
        ],
        leaf_ids=[v.id for v in of.leaf_variants(session, product.id)],
        offers=[
            sv.offer_out(session, offer, winner_id=winner.id if winner else None)
            for offer in of.offers_for(session, product.id)
        ],
    )


@router.get(
    "/offers",
    response_model=list[s.StaffOfferOut],
    summary="My offers — or everybody's, for the warehouse and the admin",
)
def list_offers(
    user: StockViewer,
    session: SessionDep,
    product_id: int | None = Query(None),
    seller_id: int | None = Query(None, description="Admin only; ignored for a seller"),
) -> list[s.StaffOfferOut]:
    stmt = select(Offer)
    if user.role is UserRole.SELLER:
        # Not a filter the caller chose — the only rows that exist for them.
        stmt = stmt.where(Offer.seller_id == _own_seller(session, user).id)
    elif seller_id is not None:
        # The warehouse and the admin see every shelf, which is what a
        # warehouse is: reading which offers exist is not pricing them.
        stmt = stmt.where(Offer.seller_id == seller_id)
    if product_id is not None:
        stmt = stmt.where(Offer.product_id == product_id)

    rows = session.exec(
        stmt.order_by(col(Offer.product_id), col(Offer.price), col(Offer.id))
    ).all()
    return [_offer_out(session, offer) for offer in rows]


@router.post(
    "/offers",
    response_model=s.StaffOfferOut,
    status_code=status.HTTP_201_CREATED,
    summary="Offer a product at a price",
)
def create_offer(
    payload: s.OfferCreateIn, user: SellerUser, session: SessionDep
) -> s.StaffOfferOut:
    product = session.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    seller = _seller_for_new_offer(session, user, payload.seller_id)
    if session.exec(
        select(Offer).where(
            Offer.product_id == product.id, Offer.seller_id == seller.id
        )
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("offer_exists"))

    declared = _checked_variants(session, product.id, payload.variant_ids)

    offer = Offer(
        seller_id=seller.id,
        product_id=product.id,
        price=payload.price,
        old_price=payload.old_price,
        # Nothing on the shelf until the warehouse books something in, which is
        # also why a new offer does not win the card the moment it is made.
        stock_left=0,
        active=payload.active,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)

    # A row per variant of the product, not only per leaf: a colour with no row
    # on the winning offer reads as uncounted, and the product page would lose
    # its per-colour figures the moment this offer won.
    for variant in declared:
        session.add(
            OfferVariant(offer_id=offer.id, variant_id=variant.id, stock_left=0)
        )

    audit.record(
        session,
        actor=user,
        action="offer.create",
        entity="offer",
        entity_id=offer.id,
        field="price",
        old=None,
        new=offer.price,
        note=f"{seller.name} · {product.title}",
    )
    of.refresh(session, product.id)
    session.commit()
    session.refresh(offer)
    return _offer_out(session, offer)


@router.patch(
    "/offers/{offer_id}",
    response_model=s.StaffOfferOut,
    summary="Change my price, or stop selling",
)
def update_offer(
    offer_id: int, payload: s.OfferUpdateIn, user: SellerUser, session: SessionDep
) -> s.StaffOfferOut:
    offer = _own_offer(session, user, offer_id)

    # A price is the number a seller will argue about, so every move of it is
    # written down with a name against it.
    if payload.price is not None and payload.price != offer.price:
        _log(session, user, offer, "price", offer.price, payload.price)
        offer.price = payload.price

    if payload.old_price is not None:
        # Nought means "no struck-through price", which is a different
        # statement from leaving the field out.
        wanted = payload.old_price or None
        if wanted != offer.old_price:
            _log(session, user, offer, "old_price", offer.old_price, wanted)
            offer.old_price = wanted

    if payload.active is not None and payload.active != offer.active:
        _log(session, user, offer, "active", offer.active, payload.active)
        offer.active = payload.active

    session.add(offer)
    of.refresh(session, offer.product_id)
    session.commit()
    session.refresh(offer)
    return _offer_out(session, offer)


# --------------------------------------------------------------------------- the warehouse's side


@router.put(
    "/offers/{offer_id}/stock",
    response_model=s.StaffOfferOut,
    summary="Correct a count — a stocktake finding, with a reason",
)
def adjust_offer_stock(
    offer_id: int, payload: s.OfferStockIn, user: WarehouseUser, session: SessionDep
) -> s.StaffOfferOut:
    """Set a count to what was actually found, and say why.

    This used to *be* the way stock arrived, which was the wrong shape for it
    twice over: nothing recorded where the goods came from, and two people
    saving at once meant the second one won silently. Goods now arrive through
    a supply (``POST /staff/supplies/{id}/receive``) and leave through a
    removal, and what is left here is the one thing neither of those covers —
    the shelf disagreeing with the books.

    So it is a stocktake correction. It writes the *difference* to the ledger
    rather than overwriting the figure, which means a concurrent sale is not
    lost, and it requires a reason, because a count that changed for no stated
    reason is the thing this whole ledger exists to make impossible. For a
    full recount of an offer, open a ``stock-count`` instead — it snapshots
    what was expected first, so a sale during the count is not mistaken for a
    discrepancy.

    A variant left out of the request keeps the count it had: finding two more
    black 42s is not a statement about the blue ones.
    """
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))

    was = offer.stock_left
    leaves = {v.id: v for v in of.leaf_variants(session, offer.product_id)}
    for entry in payload.variants:
        variant = leaves.get(entry.variant_id)
        if variant is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
            )
        current = of.variant_stock(session, offer.id, variant.id) or 0
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=entry.stock_left - current,
            variant_id=variant.id,
            actor=user,
            reason=payload.reason,
        )

    if not leaves and payload.stock_left is not None:
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=payload.stock_left - offer.stock_left,
            actor=user,
            reason=payload.reason,
        )

    # The audit row stays beside the ledger row: the ledger says what the
    # shelf did, the audit log says what the shop is advertising as a result.
    if offer.stock_left != was:
        _log(session, user, offer, "stock_left", was, offer.stock_left, note=payload.reason)
    of.refresh(session, offer.product_id)
    session.commit()
    session.refresh(offer)
    return _offer_out(session, offer)


# --------------------------------------------------------------------------- helpers


def _own_seller(session: SessionDep, user: User) -> Seller:
    seller = session.exec(select(Seller).where(Seller.user_id == user.id)).first()
    if seller is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, i18n.label("seller_account_missing")
        )
    return seller


def _own_seller_or_none(session: SessionDep, user: User) -> Seller | None:
    """The caller's own shop, or None when they have no shop of their own.

    An admin reading these lists has none — they are looking at the catalogue,
    not shopping for something to stock — so the "is this mine" columns come
    back empty for them rather than guessing at a seller.
    """
    if user.role is UserRole.ADMIN:
        return None
    return _own_seller(session, user)


def _catalogue_out(
    session: SessionDep, product: Product, seller: Seller | None
) -> s.SellerCatalogOut:
    """A published card as a seller reads it.

    Translated, because this is read to recognise a product rather than to
    edit it. The ``mine`` flag is what lets a list say "you already sell this"
    instead of offering a button whose only answer is a 409.
    """
    category = session.get(Category, product.category_id)
    brand = session.get(Brand, product.brand_id) if product.brand_id else None
    offers = of.offers_for(session, product.id, active_only=False)
    mine = next((o for o in offers if seller and o.seller_id == seller.id), None)
    variants = session.exec(
        select(func.count())
        .select_from(ProductVariant)
        .where(ProductVariant.product_id == product.id)
    ).one()

    return s.SellerCatalogOut(
        id=product.id,
        sku=product.sku,
        title=i18n.t(session, "product", product.id, "title", product.title),
        subtitle=i18n.t(session, "product", product.id, "subtitle", product.subtitle),
        image_url=sv.primary_image(session, product.id),
        category_slug=category.slug if category else "",
        category_name=(
            i18n.t(session, "category", category.id, "name", category.name)
            if category
            else ""
        ),
        brand_name=(
            i18n.t(session, "brand", brand.id, "name", brand.name) if brand else None
        ),
        price=product.price,
        old_price=product.old_price,
        in_stock=product.in_stock,
        # Every seller on the card, withdrawn ones included: "three people
        # already sell this" is the honest figure for somebody deciding
        # whether to be the fourth.
        offer_count=len(offers),
        variant_count=int(variants),
        mine=mine is not None,
        my_offer_id=mine.id if mine else None,
        my_price=mine.price if mine else None,
    )


def _seller_for_new_offer(
    session: SessionDep, user: User, seller_id: int | None
) -> Seller:
    """Whose offer this is going to be.

    A seller offers as themselves; naming somebody else is not a mistake to
    correct silently. An admin has no seller of their own and must say.
    """
    if user.role is not UserRole.ADMIN:
        own = _own_seller(session, user)
        if seller_id is not None and seller_id != own.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_offer"))
        return own

    if seller_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("seller_required")
        )
    seller = session.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("seller_not_found"))
    return seller


def _own_offer(session: SessionDep, user: User, offer_id: int) -> Offer:
    """An offer this caller may change. Somebody else's is a 403, not a 404.

    A seller asking about an offer they do not own has found a real one and is
    being refused, which is what 403 says. Pretending it is missing would be a
    different claim, and a false one.
    """
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))
    if user.role is UserRole.ADMIN:
        return offer
    if offer.seller_id != _own_seller(session, user).id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, i18n.label("not_your_offer"))
    return offer


def _checked_variants(
    session: SessionDep, product_id: int, variant_ids: list[int]
) -> list[ProductVariant]:
    """Every variant of the product, given that the leaves were all named.

    The request lists the leaves — the sizes of a product that has sizes, its
    colours otherwise — and all of them, because an offer for some of the
    colours would leave the rest of the card without figures, which is the
    hole this rule exists to close. The rows returned cover the parents too:
    they are what a colour's count is rolled up onto.
    """
    leaves = of.leaf_variants(session, product_id)
    if not leaves:
        return []

    named = set(variant_ids)
    missing = [v for v in leaves if v.id not in named]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            i18n.label(
                "variants_required",
                missing=", ".join(v.label for v in missing[:8]),
            ),
        )
    stray = named - {v.id for v in leaves}
    if stray:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
        )
    return list(
        session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        ).all()
    )


def _log(
    session: SessionDep,
    actor: User,
    offer: Offer,
    field: str,
    old: object,
    new: object,
    *,
    entity: str = "offer",
    entity_id: int | None = None,
    note: str = "",
) -> None:
    audit.record(
        session,
        actor=actor,
        action=f"offer.{field}",
        entity=entity,
        entity_id=entity_id if entity_id is not None else offer.id,
        field=field,
        old=old,
        new=new,
        note=note,
    )


def _offer_out(session: SessionDep, offer: Offer) -> s.StaffOfferOut:
    seller = session.get(Seller, offer.seller_id)
    product = session.get(Product, offer.product_id)
    winner = of.winning_offer(session, offer.product_id)
    counts = {
        row.variant_id: row.stock_left
        for row in session.exec(
            select(OfferVariant).where(OfferVariant.offer_id == offer.id)
        ).all()
    }
    variants = session.exec(
        select(ProductVariant)
        .where(col(ProductVariant.id).in_(counts or [-1]))
        .order_by(col(ProductVariant.sort), col(ProductVariant.id))
    ).all()
    return s.StaffOfferOut(
        id=offer.id,
        seller=s.SellerOut(id=seller.id, name=seller.name)
        if seller
        else s.SellerOut(id=0, name=""),
        product_id=offer.product_id,
        product_title=product.title if product else "",
        price=offer.price,
        old_price=offer.old_price,
        stock_left=offer.stock_left,
        active=offer.active,
        is_winner=winner is not None and winner.id == offer.id,
        variants=[
            s.StaffOfferVariantOut(
                variant_id=v.id,
                kind=v.kind,
                label=v.label,
                parent_id=v.parent_id,
                stock_left=counts[v.id],
            )
            for v in variants
        ],
        created_at=offer.created_at,
    )
