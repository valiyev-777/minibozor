from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import i18n
from app import schemas as s
from app import services as sv
from app.core.config import settings
from app.deps import CurrentUser, SessionDep
from app.models import (
    OrderItem,
    Product,
    Review,
    ReviewLike,
    ReviewStatus,
    ReviewTag,
)

router = APIRouter(tags=["reviews"])


@router.get("/reviews/tags", response_model=list[str], summary="Screen 16 — suggested chips")
def review_tags(session: SessionDep) -> list[str]:
    return [t.label for t in session.exec(select(ReviewTag).order_by(col(ReviewTag.sort))).all()]


@router.post(
    "/products/{product_id}/reviews",
    response_model=s.ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Screen 16 — write a review",
)
def create_review(
    product_id: int, payload: s.ReviewCreateIn, user: CurrentUser, session: SessionDep
) -> s.ReviewOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("product_not_found"))

    existing = session.exec(
        select(Review).where(Review.user_id == user.id, Review.product_id == product_id)
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Siz bu mahsulotga sharh qoldirgansiz")

    order_item = None
    if payload.order_item_id:
        order_item = session.get(OrderItem, payload.order_item_id)

    review = Review(
        user_id=user.id,
        product_id=product_id,
        order_item_id=payload.order_item_id,
        rating=payload.rating,
        text=payload.text.strip(),
        variant_label=payload.variant_label or (order_item.variant_label if order_item else ""),
        tags=payload.tags,
        photos=payload.photos,
        # Dev builds publish immediately so the flow is visible end to end.
        status=ReviewStatus.PUBLISHED if settings.is_dev else ReviewStatus.MODERATING,
    )
    session.add(review)

    if order_item:
        order_item.reviewed = True
        session.add(order_item)

    session.commit()
    session.refresh(review)
    sv.recalc_product_rating(session, product_id)
    session.commit()
    return sv.review_out(session, review, viewer=user)


@router.post("/reviews/{review_id}/like", response_model=s.ReviewOut)
def toggle_like(review_id: int, user: CurrentUser, session: SessionDep) -> s.ReviewOut:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("review_not_found"))

    existing = session.exec(
        select(ReviewLike).where(ReviewLike.review_id == review_id, ReviewLike.user_id == user.id)
    ).first()
    if existing:
        session.delete(existing)
        review.likes = max(review.likes - 1, 0)
    else:
        session.add(ReviewLike(review_id=review_id, user_id=user.id))
        review.likes += 1
    session.add(review)
    session.commit()
    session.refresh(review)
    return sv.review_out(session, review, viewer=user)


@router.get("/me/reviews", response_model=s.Page[s.ReviewOut], summary="Screen 34 — my reviews")
def my_reviews(
    user: CurrentUser,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=60),
) -> s.Page[s.ReviewOut]:
    stmt = select(Review).where(Review.user_id == user.id)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(Review.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.ReviewOut](
        items=[sv.review_out(session, r, viewer=user, with_product=True) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.delete("/me/reviews/{review_id}", response_model=s.Message)
def delete_review(review_id: int, user: CurrentUser, session: SessionDep) -> s.Message:
    review = session.get(Review, review_id)
    if review is None or review.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("review_not_found"))
    product_id = review.product_id
    session.delete(review)
    session.commit()
    sv.recalc_product_rating(session, product_id)
    session.commit()
    return s.Message(message=i18n.label("review_removed"))


@router.get(
    "/me/reviews/pending",
    response_model=list[s.OrderItemOut],
    summary="Delivered items still awaiting a review",
)
def pending_reviews(user: CurrentUser, session: SessionDep) -> list[s.OrderItemOut]:
    from app.models import Order, OrderStatus

    rows = session.exec(
        select(OrderItem)
        .join(Order, col(Order.id) == col(OrderItem.order_id))
        .where(
            Order.user_id == user.id,
            Order.status == OrderStatus.DELIVERED,
            OrderItem.reviewed.is_(False),
        )
        .order_by(col(OrderItem.id).desc())
    ).all()
    return [
        s.OrderItemOut(
            id=i.id,
            product_id=i.product_id,
            title=i.title,
            image_url=sv.media_url(i.image_url) or "",
            variant_label=i.variant_label,
            unit_price=i.unit_price,
            quantity=i.quantity,
            line_total=i.line_total,
            reviewed=i.reviewed,
        )
        for i in rows
    ]
