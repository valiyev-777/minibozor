"""The backoffice: who is looking at it, and who may work here at all.

``/staff/me`` answers the first question — the person has signed in through
the ordinary OTP flow and now needs to know which of the five panels they are
looking at.

The rest of the file answers the second. Until now the only ways to make
somebody staff were a shell script
account, which meant an admin panel could show a list of operators and had no
way to appoint one. Two endpoints close that: find the account by the only
thing anyone knows about it — the phone number they sign in with — and set its
role.

The guards are the point of the file's first half. ``StaffUser`` on an
endpoint means "not a customer"; ``AdminUser`` means one role only. Both come
from ``require_role`` in ``app.deps``, so a new backoffice endpoint declares
who may call it in its signature rather than in a body check that is easy to
forget. Handing out roles is an ``AdminUser`` door for the obvious reason:
anything else is a way to promote yourself.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app import i18n, roles
from app import schemas as s
from app.deps import AdminUser, SessionDep, StaffUser
from app.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])

# "Who am I, and what am I allowed to do" is a question about the caller
# rather than about the office, so it hangs off ``/me`` where every signed-in
# person can reach it — a warehouse worker has to be able to ask it too.
me = APIRouter(prefix="/me", tags=["profile"])


@me.get("/staff", response_model=s.StaffMeOut, summary="Who am I, and what may I do?")
def staff_me(user: StaffUser) -> s.StaffMeOut:
    return s.StaffMeOut(
        id=user.id,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
    )


# --------------------------------------------------------------------------- the people


@router.get(
    "/users",
    response_model=s.Page[s.StaffUserOut],
    summary="Find an account by phone, or list who holds a role",
)
def list_users(
    user: AdminUser,
    session: SessionDep,
    q: str | None = Query(None, description="Part of a phone number, or of a name"),
    role: UserRole | None = Query(None, description="Only accounts holding this role"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.StaffUserOut]:
    """Two screens, one query.

    Appointing somebody starts from their phone number, because that is the
    only thing the admin knows about them — it is what they sign in with and
    what they were given over the phone. Reviewing who works here starts from
    the role instead. Searching by digits alone is enough for the first: an
    admin typing ``9001`` has the number in front of them and wants the row,
    not a directory.
    """
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if q:
        needle = f"%{q.strip().lower().lstrip('+')}%"
        stmt = stmt.where(
            func.lower(User.phone).like(needle) | func.lower(User.full_name).like(needle)
        )
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(
        stmt.order_by(col(User.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.StaffUserOut](
        items=[_user_out(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=s.StaffUserOut,
    summary="Appoint somebody, or stand them down",
)
def set_role(
    user_id: int, payload: s.RoleWriteIn, user: AdminUser, session: SessionDep
) -> s.StaffUserOut:
    """The only door a role goes through from inside the running system.

    Refused when it would demote the last admin — including the admin making
    the request, who is the likeliest person to try it. A role is granted by
    an admin, so an admin is the only one who can put it back; take the last
    one away and there is nobody left who can, and the way in is a shell on
    the server. See ``app.roles`` for the rule itself.
    """
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("user_not_found"))

    # Setting the role somebody already holds is a no-op rather than an
    # error: a panel that saves a form it did not change should not be told
    # off for it, and the audit log stays a list of changes rather than of
    # saves.
    if roles.assign(
        session, actor=user, user=account, role=payload.role, note=payload.note
    ):
        session.commit()
    session.refresh(account)
    return _user_out(account)


def _user_out(row: User) -> s.StaffUserOut:
    return s.StaffUserOut(
        id=row.id,
        phone=row.phone,
        full_name=row.full_name,
        role=row.role,
        is_active=row.is_active,
        created_at=row.created_at,
    )
