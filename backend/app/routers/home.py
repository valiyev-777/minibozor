from __future__ import annotations

from fastapi import APIRouter, Query
from sqlmodel import col, select

from app import schemas as s
from app import services as sv
from app.deps import OptionalUser, SessionDep
from app.models import Banner, Category, HomeSection, Product

router = APIRouter(tags=["home"])


@router.get("/home", response_model=s.HomeOut, summary="Screen 07 — everything above the fold")
def home(
    session: SessionDep,
    user: OptionalUser,
    city: str = Query("Toshkent"),
) -> s.HomeOut:
    favs = sv.favorite_ids(session, user)

    banners = session.exec(
        select(Banner).where(Banner.active.is_(True)).order_by(col(Banner.sort))
    ).all()

    categories = session.exec(
        select(Category).where(Category.is_quick_link.is_(True)).order_by(col(Category.sort))
    ).all()

    sections: list[s.SectionOut] = []
    for section in session.exec(select(HomeSection).order_by(col(HomeSection.sort))).all():
        products = _section_products(session, section)
        sections.append(
            s.SectionOut(
                key=section.key,
                title=section.title,
                subtitle=section.subtitle,
                layout=section.layout,
                category_slug=section.category_slug,
                products=sv.product_cards(session, products, favs),
            )
        )

    return s.HomeOut(
        city=city,
        banners=[
            s.BannerOut(
                id=b.id,
                kicker=b.kicker,
                title=b.title,
                subtitle=b.subtitle,
                cta=b.cta,
                image_url=sv.media_url(b.image_url) or "",
                gradient_from=b.gradient_from,
                gradient_to=b.gradient_to,
                target_type=b.target_type,
                target_value=b.target_value,
            )
            for b in banners
        ],
        categories=[sv.category_out(session, c) for c in categories],
        sections=sections,
    )


def _section_products(session: SessionDep, section: HomeSection) -> list[Product]:
    limit = {"deals": 2, "grid": 4, "rail": 8}.get(section.layout, 8)
    stmt = select(Product)

    if section.category_slug:
        category = session.exec(
            select(Category).where(Category.slug == section.category_slug)
        ).first()
        if category:
            child_ids = session.exec(
                select(Category.id).where(Category.parent_id == category.id)
            ).all()
            stmt = stmt.where(col(Product.category_id).in_([category.id, *child_ids]))

    if section.layout == "deals":
        stmt = stmt.where(col(Product.old_price).is_not(None)).order_by(
            (col(Product.old_price) - col(Product.price)).desc()
        )
    else:
        stmt = stmt.order_by(col(Product.sold_count).desc(), col(Product.rating).desc())

    return session.exec(stmt.limit(limit)).all()
