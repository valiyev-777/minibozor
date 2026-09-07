"""Changing what somebody is allowed to do.

Two doors lead here. The admin panel has a role picker, and linking an account
to a seller makes it a seller — and both have to honour the same rule, so the
rule lives here rather than in whichever endpoint happened to need it first.

**The last admin cannot be stood down.** A role is granted by an admin, so an
admin is the only person who can put one back; demote the last one and the
grant is unreachable from inside the running system. It is the one privilege
change that cannot be undone through the door it was made in, which is why it
is refused rather than warned about. Any other demotion is somebody else's to
reverse.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, col, func, select

from app import audit, i18n
from app.models import User, UserRole


def admin_count(session: Session) -> int:
    """How many active admins there are.

    Deactivated accounts are not counted: a role on an account nobody can sign
    in to is not a way back into the system, and counting it would let the last
    usable admin be demoted.
    """
    return int(
        session.exec(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, col(User.is_active).is_(True))
        ).one()
    )


def ensure_not_the_last_admin(session: Session, user: User, new_role: UserRole) -> None:
    """Refuse a change that would leave the system with no admin."""
    if user.role is not UserRole.ADMIN or new_role is UserRole.ADMIN:
        return
    if admin_count(session) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("last_admin"))


def assign(
    session: Session,
    *,
    actor: User,
    user: User,
    role: UserRole,
    note: str = "",
) -> bool:
    """Give ``user`` a role, writing the audit row that goes with it.

    Returns whether anything changed. A privilege change is the kind of thing
    asked about months later — who made this person an operator, and when — so
    it is logged in the same session as the change and commits with it.
    """
    if user.role is role:
        return False
    ensure_not_the_last_admin(session, user, role)
    audit.record(
        session,
        actor=actor,
        action="user.role",
        entity="user",
        entity_id=user.id,
        field="role",
        old=user.role,
        new=role,
        note=note or user.phone,
    )
    user.role = role
    session.add(user)
    return True
