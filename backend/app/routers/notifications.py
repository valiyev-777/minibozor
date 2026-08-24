from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import schemas as s
from app import services as sv
from app.deps import CurrentUser, SessionDep
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=list[s.NotificationGroupOut],
    summary="Screen 36 — grouped by Bugun / Shu hafta / Avvalroq",
)
def list_notifications(
    user: CurrentUser, session: SessionDep, limit: int = Query(100, le=300)
) -> list[s.NotificationGroupOut]:
    rows = session.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(col(Notification.created_at).desc())
        .limit(limit)
    ).all()

    now = sv.utcnow()
    today = now.date()
    week_start = today - timedelta(days=7)

    buckets: dict[str, list[s.NotificationOut]] = {"Bugun": [], "Shu hafta": [], "Avvalroq": []}
    for row in rows:
        created = row.created_at.date()
        if created == today:
            key = "Bugun"
        elif created >= week_start:
            key = "Shu hafta"
        else:
            key = "Avvalroq"
        buckets[key].append(
            s.NotificationOut(
                id=row.id,
                kind=row.kind,
                icon=row.icon,
                title=row.title,
                text=row.text,
                deep_link=row.deep_link,
                read=row.read_at is not None,
                created_at=row.created_at,
            )
        )

    return [
        s.NotificationGroupOut(label=label, items=items)
        for label, items in buckets.items()
        if items
    ]


@router.get("/unread-count", response_model=dict[str, int])
def unread_count(user: CurrentUser, session: SessionDep) -> dict[str, int]:
    count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, col(Notification.read_at).is_(None))
    ).one()
    return {"count": count}


@router.post("/read", response_model=s.Message, summary="Mark all (or some) as read")
def mark_read(
    user: CurrentUser, session: SessionDep, ids: list[int] | None = None
) -> s.Message:
    stmt = select(Notification).where(
        Notification.user_id == user.id, col(Notification.read_at).is_(None)
    )
    if ids:
        stmt = stmt.where(col(Notification.id).in_(ids))
    now = sv.utcnow()
    for row in session.exec(stmt).all():
        row.read_at = now
        session.add(row)
    session.commit()
    return s.Message(message="O'qilgan deb belgilandi")


@router.delete("/{notification_id}", response_model=s.Message)
def delete_notification(
    notification_id: int, user: CurrentUser, session: SessionDep
) -> s.Message:
    row = session.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bildirishnoma topilmadi")
    session.delete(row)
    session.commit()
    return s.Message(message="O'chirildi")
