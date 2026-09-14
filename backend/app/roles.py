"""Changing what somebody is allowed to do, and who works here at all.

The admin panel has a role picker, and it has to honour one rule, which lives
here rather than in whichever endpoint happened to need it first.

**The last admin cannot be stood down.** A role is granted by an admin, so an
admin is the only person who can put one back; demote the last one and the
grant is unreachable from inside the running system. It is the one privilege
change that cannot be undone through the door it was made in, which is why it
is refused rather than warned about. Any other demotion is somebody else's to
reverse. Switching the last admin's account off is the same loss by another
route, so both go through ``is_the_last_admin``.

**Appointing somebody is one function with two callers.** The admin panel and
``tools.make_staff`` both hire people, and for a while only one of them wrote
an audit row — so whether the shop could say who appointed a courier depended
on which of the two the owner happened to use. ``appoint`` is what both call.
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


def is_the_last_admin(session: Session, user: User) -> bool:
    """Whether this account is the only remaining way into the admin panel.

    The one rule, in one place, because there are two ways to lose an
    account: take the role off it, and switch the account off. They were one
    rule written once and then only enforced on the first of the two, which
    left a door — deactivate the last admin and the role is still on a row
    nobody can sign in to, which is no better than not having it.

    A deactivated admin is not the last admin: they are already not a way in,
    and ``admin_count`` does not count them, so demoting one while a live
    admin exists elsewhere is somebody tidying up rather than locking the door.
    """
    return (
        user.role is UserRole.ADMIN and user.is_active and admin_count(session) <= 1
    )


def ensure_not_the_last_admin(session: Session, user: User, new_role: UserRole) -> None:
    """Refuse a role change that would leave the system with no admin."""
    if new_role is UserRole.ADMIN:
        return
    if is_the_last_admin(session, user):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("last_admin"))


def ensure_the_last_admin_stays(session: Session, user: User) -> None:
    """Refuse deactivating the only admin left.

    Same rule as the demotion, different sentence: the admin reading it is
    about to switch an account off, not to change its role, and being told
    about demotion would not tell them what to do.
    """
    if is_the_last_admin(session, user):
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("last_admin_active"))


def assign(
    session: Session,
    *,
    actor: User | None,
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


def appoint(
    session: Session,
    *,
    actor: User | None,
    phone: str,
    role: UserRole,
    full_name: str = "",
    note: str = "",
) -> tuple[User, bool]:
    """Put the person on this number to work, creating the account if need be.

    Returns the account and whether it had to be made. Shared between the
    admin panel's appointment endpoint and ``tools.make_staff``, because for a
    while the two did different things: the endpoint did not exist and the
    script wrote a ``users`` row with no audit line at all. Half the staff in
    the building therefore had no record of who appointed them, which is the
    one fact the audit table exists to keep.

    A brand-new account writes ``user.create`` as well as nothing else — there
    is no old role to record a change from, and a row saying "role: none →
    courier" would be a change that never happened. An account that already
    existed goes through ``assign``, which records the change and enforces the
    last-admin rule.

    ``full_name`` only fills a blank. The name on an account that has been
    used is the name its owner typed into the app, and an admin appointing
    them from a list of phone numbers is the worse source of the two.

    ``actor`` is ``None`` when the script is the caller: nobody is signed in
    at a shell, and the log says "the system" rather than naming whoever's
    token happened to be lying about.
    """
    user = session.exec(select(User).where(User.phone == phone)).first()
    if user is None:
        user = User(phone=phone, full_name=full_name, role=role)
        session.add(user)
        # Flushed rather than committed: the id is needed for the audit row,
        # and the two must still land or roll back together.
        session.flush()
        audit.record(
            session,
            actor=actor,
            action="user.create",
            entity="user",
            entity_id=user.id,
            field="role",
            new=role,
            note=note or phone,
        )
        return user, True

    if full_name and not user.full_name:
        user.full_name = full_name
        session.add(user)
    assign(session, actor=actor, user=user, role=role, note=note)
    return user, False
