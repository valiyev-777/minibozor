from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, or_, select

from app import i18n
from app import schemas as s
from app import services as sv
from app.deps import OptionalUser, SessionDep
from app.models import Brand, Category, Product, ProductVariant, Review, ReviewStatus, VariantKind

router = APIRouter(tags=["catalog"])

SortKey = Literal["popular", "price_asc", "price_desc", "rating", "new", "discount"]

SORT_KEYS = ["popular", "price_asc", "price_desc", "rating", "new", "discount"]


def sort_options() -> list[dict[str, str]]:
    """Built per request so the labels follow Accept-Language."""
    return [{"key": k, "label": i18n.label(f"sort_{k}")} for k in SORT_KEYS]

FLAG_KEYS = ("next_day_delivery", "free_delivery", "discounted", "is_original")


@router.get("/categories", response_model=list[s.CategoryOut], summary="Screen 10 — catalogue root")
def list_categories(
    session: SessionDep,
    parent: str | None = Query(None, description="Parent category slug; omit for the root"),
    quick_links: bool = Query(False, description="Only the 10 tiles on the home screen"),
) -> list[s.CategoryOut]:
    stmt = select(Category)
    if quick_links:
        stmt = stmt.where(Category.is_quick_link.is_(True))
    elif parent:
        parent_row = session.exec(select(Category).where(Category.slug == parent)).first()
        if parent_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("category_not_found"))
        stmt = stmt.where(Category.parent_id == parent_row.id)
    else:
        stmt = stmt.where(col(Category.parent_id).is_(None))
    rows = session.exec(stmt.order_by(col(Category.sort))).all()
    return [sv.category_out(session, c) for c in rows]


@router.get("/categories/{slug}", response_model=s.CategoryOut, summary="Screen 11 — subcategory")
def get_category(slug: str, session: SessionDep) -> s.CategoryOut:
    row = session.exec(select(Category).where(Category.slug == slug)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("category_not_found"))
    return sv.category_out(session, row)


@router.get(
    "/products",
    response_model=s.Page[s.ProductCardOut],
    summary="Screens 09, 12 — listing",
)
def list_products(
    session: SessionDep,
    user: OptionalUser,
    q: str | None = None,
    category: str | None = Query(None, description="Category slug (includes children)"),
    brand: list[str] = Query(default=[]),
    min_price: int | None = None,
    max_price: int | None = None,
    min_rating: float | None = None,
    size: list[str] = Query(default=[]),
    next_day_delivery: bool | None = None,
    free_delivery: bool | None = None,
    discounted: bool | None = None,
    is_original: bool | None = None,
    show_sold_out: bool = Query(
        False,
        description="Include products with nothing left. Off by default: a shelf "
        "shows what can be bought.",
    ),
    sort: SortKey = "popular",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=60),
) -> s.Page[s.ProductCardOut]:
    stmt = select(Product)

    # What cannot be bought is not on the shelf. A sold-out product used to sit
    # in the grid behind its veil, taking a slot in every listing and every page
    # of results from the products that could actually be sold — and the filter
    # sheet can put them back for anyone who wants to see them.
    if not show_sold_out:
        stmt = stmt.where(Product.in_stock.is_(True))

    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.title).like(needle),
                func.lower(Product.subtitle).like(needle),
                func.lower(Product.description).like(needle),
            )
        )
    if category:
        stmt = stmt.where(col(Product.category_id).in_(_category_tree_ids(session, category)))
    if brand:
        brand_ids = session.exec(select(Brand.id).where(col(Brand.slug).in_(brand))).all()
        stmt = stmt.where(col(Product.brand_id).in_(brand_ids or [-1]))
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if min_rating is not None:
        stmt = stmt.where(Product.rating >= min_rating)
    if next_day_delivery:
        stmt = stmt.where(Product.next_day_delivery.is_(True))
    if free_delivery:
        stmt = stmt.where(Product.free_delivery.is_(True))
    if is_original:
        stmt = stmt.where(Product.is_original.is_(True))
    if discounted:
        stmt = stmt.where(col(Product.old_price).is_not(None), Product.old_price > Product.price)
    if size:
        sized = session.exec(
            select(ProductVariant.product_id).where(
                ProductVariant.kind == VariantKind.SIZE, col(ProductVariant.label).in_(size)
            )
        ).all()
        stmt = stmt.where(col(Product.id).in_(sized or [-1]))

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    stmt = _apply_sort(stmt, sort)
    rows = session.exec(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    favs = sv.favorite_ids(session, user)
    return s.Page[s.ProductCardOut](
        items=sv.product_cards(session, rows, favs),
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get("/products/filters", response_model=s.FiltersOut, summary="Screen 13 — filter sheet")
def product_filters(session: SessionDep, category: str | None = None) -> s.FiltersOut:
    stmt = select(Product)
    if category:
        stmt = stmt.where(col(Product.category_id).in_(_category_tree_ids(session, category)))
    products = session.exec(stmt).all()
    ids = [p.id for p in products] or [-1]

    prices = [p.price for p in products] or [0]
    brand_counts: dict[int, int] = {}
    for p in products:
        if p.brand_id:
            brand_counts[p.brand_id] = brand_counts.get(p.brand_id, 0) + 1
    brands = [
        s.BrandOut(id=b.id, slug=b.slug, name=b.name, product_count=brand_counts[b.id])
        for b in session.exec(select(Brand).where(col(Brand.id).in_(brand_counts or {-1}))).all()
    ]
    brands.sort(key=lambda b: -b.product_count)

    sizes = sorted(
        {
            v.label
            for v in session.exec(
                select(ProductVariant).where(
                    col(ProductVariant.product_id).in_(ids), ProductVariant.kind == VariantKind.SIZE
                )
            ).all()
        },
        key=lambda x: (len(x), x),
    )

    flags = [
        s.FilterFlagOut(
            key=key,
            label=i18n.label(f"flag_{key}"),
            subtitle=i18n.label(f"flag_{key}_sub"),
            count=sum(1 for p in products if _flag_matches(p, key)),
        )
        for key in FLAG_KEYS
    ]

    return s.FiltersOut(
        price_min=min(prices),
        price_max=max(prices),
        brands=brands,
        sizes=sizes,
        ratings=[
            i18n.label("rating_45"),
            i18n.label("rating_40"),
            i18n.label("rating_many"),
        ],
        flags=flags,
        sorts=sort_options(),
    )


@router.get("/products/{product_id}", response_model=s.ProductOut, summary="Screen 14 — product")
def get_product(product_id: int, session: SessionDep, user: OptionalUser) -> s.ProductOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))
    return sv.product_out(session, product, sv.favorite_ids(session, user))


@router.get("/products/{product_id}/similar", response_model=list[s.ProductCardOut])
def similar_products(
    product_id: int, session: SessionDep, user: OptionalUser, limit: int = Query(8, le=20)
) -> list[s.ProductCardOut]:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))
    rows = session.exec(
        select(Product)
        .where(
            Product.category_id == product.category_id,
            Product.id != product_id,
            # A recommendation is a suggestion to buy something. One that cannot
            # be bought is not a recommendation.
            Product.in_stock.is_(True),
        )
        .order_by(col(Product.rating).desc())
        .limit(limit)
    ).all()
    return sv.product_cards(session, rows, sv.favorite_ids(session, user))


@router.get(
    "/products/{product_id}/reviews/summary",
    response_model=s.ReviewSummaryOut,
    summary="Screen 15 — rating breakdown",
)
def product_review_summary(product_id: int, session: SessionDep) -> s.ReviewSummaryOut:
    return sv.review_summary(session, product_id)


@router.get(
    "/products/{product_id}/reviews",
    response_model=s.Page[s.ReviewOut],
    summary="Screen 15 — reviews",
)
def product_reviews(
    product_id: int,
    session: SessionDep,
    user: OptionalUser,
    stars: int | None = Query(None, ge=1, le=5),
    with_photos: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> s.Page[s.ReviewOut]:
    stmt = select(Review).where(
        Review.product_id == product_id, Review.status == ReviewStatus.PUBLISHED
    )
    if stars:
        stmt = stmt.where(Review.rating == stars)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(Review.likes).desc(), col(Review.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    if with_photos:
        rows = [r for r in rows if r.photos]
    return s.Page[s.ReviewOut](
        items=[sv.review_out(session, r, viewer=user) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get("/brands", response_model=list[s.BrandOut])
def list_brands(session: SessionDep) -> list[s.BrandOut]:
    rows = session.exec(select(Brand).order_by(col(Brand.name))).all()
    return [s.BrandOut(id=b.id, slug=b.slug, name=b.name) for b in rows]


# --------------------------------------------------------------------------- helpers


def _category_tree_ids(session: SessionDep, slug: str) -> list[int]:
    root = session.exec(select(Category).where(Category.slug == slug)).first()
    if root is None:
        return [-1]
    ids = [root.id]
    frontier = [root.id]
    while frontier:
        children = session.exec(
            select(Category.id).where(col(Category.parent_id).in_(frontier))
        ).all()
        if not children:
            break
        ids.extend(children)
        frontier = list(children)
    return ids


def _flag_matches(product: Product, key: str) -> bool:
    if key == "discounted":
        return bool(product.old_price and product.old_price > product.price)
    return bool(getattr(product, key, False))


def _apply_sort(stmt, sort: SortKey):
    if sort == "price_asc":
        return stmt.order_by(col(Product.price))
    if sort == "price_desc":
        return stmt.order_by(col(Product.price).desc())
    if sort == "rating":
        return stmt.order_by(col(Product.rating).desc(), col(Product.reviews_count).desc())
    if sort == "new":
        return stmt.order_by(col(Product.created_at).desc())
    if sort == "discount":
        return stmt.order_by((col(Product.old_price) - col(Product.price)).desc())
    return stmt.order_by(col(Product.sold_count).desc(), col(Product.rating).desc())
