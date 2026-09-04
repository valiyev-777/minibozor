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
from sqlmodel import col, select

from app import audit, i18n
from app import offers as of
from app import schemas as s
from app.deps import SellerUser, SessionDep, WarehouseUser
from app.models import (
    Offer,
    OfferVariant,
    Product,
    ProductVariant,
    Seller,
    User,
    UserRole,
)

router = APIRouter(prefix="/staff", tags=["staff"])


# --------------------------------------------------------------------------- the seller's side


@router.get(
    "/offers",
    response_model=list[s.StaffOfferOut],
    summary="My offers — or everybody's, for an admin",
)
def list_offers(
    user: SellerUser,
    session: SessionDep,
    product_id: int | None = Query(None),
    seller_id: int | None = Query(None, description="Admin only; ignored for a seller"),
) -> list[s.StaffOfferOut]:
    stmt = select(Offer)
    if user.role is UserRole.ADMIN:
        if seller_id is not None:
            stmt = stmt.where(Offer.seller_id == seller_id)
    else:
        # Not a filter the caller chose — the only rows that exist for them.
        stmt = stmt.where(Offer.seller_id == _own_seller(session, user).id)
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
    summary="Warehouse intake — set what is actually on the shelf",
)
def set_offer_stock(
    offer_id: int, payload: s.OfferStockIn, user: WarehouseUser, session: SessionDep
) -> s.StaffOfferOut:
    """The counts, and only the counts.

    Deliberately not the seller's endpoint and deliberately not part of the
    price one: these two figures answer to different people, and an endpoint
    that took both would be an endpoint whose guard had to be the weaker of
    the two.

    Only the leaves are given. A colour's total is the sum of its sizes and the
    offer's total is the sum of its colours, computed here rather than trusted,
    so a shelf cannot be left disagreeing with itself. A variant left out of
    the request keeps the count it had — a delivery of black 42s is not a
    statement about the blue ones.
    """
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("offer_not_found"))

    leaves = {v.id: v for v in of.leaf_variants(session, offer.product_id)}
    for entry in payload.variants:
        variant = leaves.get(entry.variant_id)
        if variant is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, i18n.label("variant_not_of_product")
            )
        row = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == offer.id,
                OfferVariant.variant_id == variant.id,
            )
        ).first()
        if row is None:
            row = OfferVariant(offer_id=offer.id, variant_id=variant.id, stock_left=0)
        if row.stock_left != entry.stock_left:
            _log(
                session,
                user,
                offer,
                "stock_left",
                row.stock_left,
                entry.stock_left,
                entity="offer_variant",
                entity_id=row.id,
                note=variant.label,
            )
        row.stock_left = entry.stock_left
        session.add(row)

    if not leaves and payload.stock_left is not None:
        if payload.stock_left != offer.stock_left:
            _log(session, user, offer, "stock_left", offer.stock_left, payload.stock_left)
        offer.stock_left = payload.stock_left
        session.add(offer)

    session.commit()
    was = offer.stock_left
    of.roll_up(session, offer)
    if leaves and offer.stock_left != was:
        _log(session, user, offer, "stock_left", was, offer.stock_left)
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
