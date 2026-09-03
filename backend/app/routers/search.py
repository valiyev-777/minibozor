from __future__ import annotations

from fastapi import APIRouter, Query
from sqlmodel import col, func, select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, OptionalUser, SessionDep
from app.models import PopularQuery, Product, SearchHistory

router = APIRouter(prefix="/search", tags=["search"])

RECENT_LIMIT = 8


@router.get("", response_model=s.SearchLandingOut, summary="Screen 08 — search landing")
def search_landing(session: SessionDep, user: OptionalUser) -> s.SearchLandingOut:
    recent: list[str] = []
    if user:
        rows = session.exec(
            select(SearchHistory)
            .where(SearchHistory.user_id == user.id)
            .order_by(col(SearchHistory.created_at).desc())
            .limit(RECENT_LIMIT)
        ).all()
        seen: set[str] = set()
        for row in rows:
            if row.query.lower() not in seen:
                seen.add(row.query.lower())
                recent.append(row.query)

    popular = [
        p.query
        for p in session.exec(
            select(PopularQuery).order_by(col(PopularQuery.sort), col(PopularQuery.hits).desc())
        ).all()
    ]
    return s.SearchLandingOut(recent=recent, popular=popular)


@router.get("/suggest", response_model=list[s.SuggestionOut], summary="Screen 08 — typeahead")
def suggest(
    session: SessionDep,
    q: str = Query(min_length=1),
    limit: int = Query(6, ge=1, le=20),
) -> list[s.SuggestionOut]:
    needle = f"%{q.lower()}%"
    rows = session.exec(
        select(Product)
        # Suggesting something that cannot be bought wastes one of six rows.
        .where(func.lower(Product.title).like(needle), Product.in_stock.is_(True))
        .order_by(col(Product.sold_count).desc())
        .limit(limit)
    ).all()
    return [
        s.SuggestionOut(
            product_id=p.id,
            title=p.title,
            price=p.price,
            image_url=sv.primary_image(session, p.id),
        )
        for p in rows
    ]


@router.post("/recent", response_model=s.Message, summary="Remember a search")
def remember(query: str, user: CurrentUser, session: SessionDep) -> s.Message:
    query = query.strip()
    if query:
        session.add(SearchHistory(user_id=user.id, query=query))
        popular = session.exec(
            select(PopularQuery).where(func.lower(PopularQuery.query) == query.lower())
        ).first()
        if popular:
            popular.hits += 1
            session.add(popular)
        session.commit()
    return s.Message(message="Saqlandi")


@router.delete("/recent", response_model=s.Message, summary="Clear search history")
def clear_recent(user: CurrentUser, session: SessionDep) -> s.Message:
    for row in session.exec(select(SearchHistory).where(SearchHistory.user_id == user.id)).all():
        session.delete(row)
    session.commit()
    return s.Message(message="Tarix tozalandi")
