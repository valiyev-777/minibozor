"""The people: who works here, who buys from here, and who changed what.

``/staff/me`` answers the first question the backoffice asks — the person has
signed in through the ordinary OTP flow and now needs to know which of the
panels they are looking at.

The rest of the file is the office's own directory, and it was wrong in three
ways at once.

**Staff and customers were one list.** There is one ``users`` table and one
``role`` column, which is right — staff sign in the way customers do and
there is no second password store — but the screen called "Xodimlar" was
reading ``/admin/users``, which answers with every account in the shop. So
the list of the five people who work here was a list of every person who has
ever bought a pair of shoes, and it got longer every day. ``/admin/staff`` and
``/admin/customers`` are the two questions, asked separately, because they are
two screens with nothing in common: one is a directory of colleagues, the
other is a ledger of buyers with money next to their names.

**There was no way to hire anybody.** An account came into existence when an
unknown number signed in, or from a shell script on the server. So appointing
a courier meant ssh, and somebody appointed at the counter on Monday could not
be set up until they had first used the app. ``POST /admin/staff`` makes the
row, whether or not the number has ever been seen.

**Nothing ever read the audit table.** Thirty-eight places write to it before
they commit, and the only way to read one back was a database client.
``GET /admin/audit`` is that door, admin-only, because a log of who did what
is a record of everybody and not a tool for doing the work.

Everything the panel wanted and the schema does not store is derived here
rather than added as a column — see ``_last_seen`` for the one that came
closest to being one.

The guards are the file's other half. ``StaffUser`` means "not a customer";
``AdminUser`` means one role only. Both come from ``require_role`` in
``app.deps``, so an endpoint says who may call it in its signature rather than
in a body check that is easy to forget. Everything below ``/admin`` here is an
``AdminUser`` door: a directory of colleagues with their last sign-in on it, a
customer's saved cards and a log of every change made in the building are the
owner's to read, and a picker at the bench has no use for any of them.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case
from sqlmodel import col, func, select

from app import audit, i18n, roles
from app import schemas as s
from app import services as sv
from app.deps import AdminUser, SessionDep, StaffUser, get_user_by_phone
from app.models import (
    STAFF_ROLES,
    Address,
    AuditLog,
    CartItem,
    Favorite,
    Order,
    OrderStatus,
    PaymentCard,
    RefreshToken,
    User,
    UserRole,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# "Who am I, and what am I allowed to do" is a question about the caller
# rather than about the office, so it hangs off ``/me`` where every signed-in
# person can reach it — a warehouse worker has to be able to ask it too.
me = APIRouter(prefix="/me", tags=["profile"])

# How many of a customer's orders the detail screen carries. Enough to see a
# pattern — a run of cancellations, a first order last week — without turning
# the screen somebody opens mid-call into a year of history.
RECENT_ORDERS = 10


@me.get("/staff", response_model=s.StaffMeOut, summary="Who am I, and what may I do?")
def staff_me(user: StaffUser) -> s.StaffMeOut:
    return s.StaffMeOut(
        id=user.id,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
    )


# --------------------------------------------------------------------------- who works here


@router.get(
    "/staff",
    response_model=s.Page[s.StaffMemberOut],
    summary="Everybody who works here, and nobody who doesn't",
)
def list_staff(
    user: AdminUser,
    session: SessionDep,
    q: str | None = Query(None, description="Part of a phone number, or of a name"),
    role: UserRole | None = Query(None, description="Only people doing this job"),
    active: bool | None = Query(None, description="Unset: both, which is the norm"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.StaffMemberOut]:
    """The staff screen, which until now was the whole shop.

    ``customer`` is excluded in the query and not by a filter the panel has to
    remember to send: the filter was what was missing, and a screen titled
    "Xodimlar" that lists four thousand shoppers is not a screen with a bug in
    it — it is the wrong question being asked of the database. Passing
    ``role=customer`` here answers with nothing, for the same reason.

    Ordered by job and then by name rather than newest first. A directory is
    read to find a person or to see who is covering a job, and both want the
    couriers together; "who joined most recently" is a question about hiring,
    which is what the audit trail is for.
    """
    where = [col(User.role).in_(list(STAFF_ROLES))]
    if role is not None:
        where.append(User.role == role)
    if active is not None:
        where.append(col(User.is_active).is_(active))
    if q:
        needle = f"%{q.strip().lower().lstrip('+')}%"
        where.append(
            func.lower(User.phone).like(needle) | func.lower(User.full_name).like(needle)
        )

    total = session.exec(select(func.count()).select_from(User).where(*where)).one()
    rows = session.exec(
        select(User)
        .where(*where)
        .order_by(col(User.role), col(User.full_name), col(User.phone))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    seen = _last_seen(session, [row.id for row in rows])
    return s.Page[s.StaffMemberOut](
        items=[_staff_out(row, seen.get(row.id)) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.post(
    "/staff",
    response_model=s.StaffMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Appoint somebody",
)
def appoint_staff(
    payload: s.StaffAppointIn, user: AdminUser, session: SessionDep
) -> s.StaffMemberOut:
    """Hiring, from inside the running system for the first time.

    Three cases, and the interesting one is the first.

    **Nobody has that number.** The account is made, with the job already on
    it. Somebody taken on at the counter can be set up before they have ever
    opened the app; they then sign in with an OTP like anybody else and find
    the panel already theirs. Without this an admin had to wait for the new
    courier to sign in as a customer before they could be made a courier,
    which is why this was a shell script.

    **They are a customer.** Promoted in place, same row, same id — their
    orders, their addresses and their basket are theirs and stay theirs. A
    person who works here is allowed to have bought something here, and making
    a second account would split them in two.

    **They already work here.** Refused, rather than quietly re-assigned: an
    appointment form is filled in by somebody who thinks they are adding a
    person, and if that number belongs to the warehouse manager the answer
    they need is "that is the warehouse manager", not a warehouse manager who
    is now a courier.

    ``customer`` is not a job and is refused here. Standing somebody down is
    the role door or the active door, both of which say what they are doing.
    """
    if payload.role is UserRole.CUSTOMER:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, i18n.label("not_an_appointment")
        )

    existing = get_user_by_phone(session, payload.phone)
    if existing is not None and existing.role in STAFF_ROLES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            i18n.label("already_staff", role=existing.role.value),
        )

    account, _ = roles.appoint(
        session,
        actor=user,
        phone=payload.phone,
        role=payload.role,
        full_name=payload.full_name.strip(),
        note=payload.note,
    )
    session.commit()
    session.refresh(account)
    return _staff_out(account, _last_seen(session, [account.id]).get(account.id))


# --------------------------------------------------------------------------- the accounts


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
    """Every account there is, customers included — a search, not a screen.

    Kept as it was, and deliberately not narrowed: this is the lookup an admin
    uses when all they have is a phone number somebody read out and they do
    not yet know whether it belongs to a colleague or to a shopper. The two
    screens that used to share it now have their own doors above and below,
    which is what this was being asked to be and could not be.
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
    "/users/{user_id}",
    response_model=s.StaffMemberOut,
    summary="Correct a name or an email",
)
def update_user(
    user_id: int, payload: s.AdminUserWriteIn, user: AdminUser, session: SessionDep
) -> s.StaffMemberOut:
    """The office fixing what the office got wrong.

    A name taken down over the telephone and an email with a letter missing:
    two fields, and nothing else. The role has its own door with the
    last-admin rule on it, and the language, the notification switches, the
    PIN and the biometrics are the account holder's own settings — an office
    that can turn somebody's order notifications off without them knowing is
    an office that gets blamed for the message that never arrived.

    Audited field by field, and only where the value actually moves. Saving a
    form nobody changed writes nothing, so the log stays a list of changes
    rather than a list of times a screen was open.
    """
    account = _account(session, user_id)
    changes = payload.model_dump(exclude_unset=True)
    # ``full_name`` is a string on the row and every reader prints it, so
    # clearing one is the empty string rather than a null that would come back
    # out of the API as ``None`` in the middle of a table.
    if changes.get("full_name") is None and "full_name" in changes:
        changes["full_name"] = ""

    for field, value in changes.items():
        old = getattr(account, field)
        if old == value:
            continue
        audit.record(
            session,
            actor=user,
            action="user.profile",
            entity="user",
            entity_id=account.id,
            field=field,
            old=old,
            new=value,
            note=account.phone,
        )
        setattr(account, field, value)
    session.add(account)
    session.commit()
    session.refresh(account)
    return _staff_out(account, _last_seen(session, [account.id]).get(account.id))


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
    account = _account(session, user_id)

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


@router.post(
    "/users/{user_id}/active",
    response_model=s.StaffMemberOut,
    summary="Somebody left, or somebody came back",
)
def set_active(
    user_id: int, payload: s.ActiveWriteIn, user: AdminUser, session: SessionDep
) -> s.StaffMemberOut:
    """The "somebody left" door, which the office did not have.

    ``is_active`` has been on the row since the first migration and exactly
    one thing wrote it: a customer deleting their own account. So when a
    courier stopped turning up, their token kept working and their panel kept
    opening, and the only remedy was a shell.

    Switching an account off is not deleting it. Their orders, the addresses
    they were delivered to and every audit row naming them stay exactly where
    they are — that history is the shop's, and an account is the thread it
    hangs off. What changes is that ``get_current_user`` stops letting them
    in, which it has always done and nothing could trigger.

    The outstanding refresh tokens are deliberately left alone. They are
    already worthless — both the guard and the refresh endpoint check
    ``is_active`` — and they are the only record of when this person last
    worked, which is the thing the screen above them shows. Revoking them
    would close a door that is already shut and erase the answer to "when did
    we last see them" in the same stroke.

    Refused for the last active admin, by the same rule that refuses demoting
    them: an admin nobody can sign in as is not an admin.
    """
    account = _account(session, user_id)
    if account.is_active and not payload.active:
        roles.ensure_the_last_admin_stays(session, account)

    if account.is_active is not payload.active:
        audit.record(
            session,
            actor=user,
            action="user.active",
            entity="user",
            entity_id=account.id,
            field="is_active",
            old=account.is_active,
            new=payload.active,
            note=payload.note or account.phone,
        )
        account.is_active = payload.active
        session.add(account)
        session.commit()
    session.refresh(account)
    return _staff_out(account, _last_seen(session, [account.id]).get(account.id))


# --------------------------------------------------------------------------- the customers


@router.get(
    "/customers",
    response_model=s.Page[s.CustomerRowOut],
    summary="Everybody who buys here, with what they are worth next to them",
)
def list_customers(
    user: AdminUser,
    session: SessionDep,
    q: str | None = Query(None, description="Part of a phone number, or of a name"),
    ordering: Literal["recent", "spend", "orders"] = Query(
        "recent",
        description="`recent`: newest account. `spend`: delivered so'm. `orders`: count",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> s.Page[s.CustomerRowOut]:
    """One query for the page, not one query per row.

    A customer list is read for the four figures beside the name, and the
    obvious way to get them — fetch thirty customers, then count each one's
    orders — is ninety-one round trips to draw a table. The counts come off a
    grouped subquery joined onto the page, so thirty rows cost the same as
    one; ``app.routers.shelves._fill`` does the same thing for the same
    reason. Sorting by spend needs the figure in the page query anyway, which
    is the other half of why the join is there rather than a second pass.

    The join is an outer one because most customers have never ordered
    anything, and an inner join would have quietly turned this into a list of
    buyers — the missing half being exactly the people somebody might want to
    ring.
    """
    history = (
        select(
            col(Order.user_id).label("user_id"),
            func.count().label("orders"),
            # Delivered only. A placed order is a promise and a cancelled one
            # is nothing, so counting either would put the shop's keenest
            # tyre-kicker at the top of a list headed "biggest spender".
            func.coalesce(
                func.sum(
                    case((Order.status == OrderStatus.DELIVERED, Order.total), else_=0)
                ),
                0,
            ).label("spent"),
            func.max(Order.created_at).label("last_order"),
        )
        .group_by(col(Order.user_id))
        .subquery()
    )

    where = [User.role == UserRole.CUSTOMER]
    if q:
        needle = f"%{q.strip().lower().lstrip('+')}%"
        where.append(
            func.lower(User.phone).like(needle) | func.lower(User.full_name).like(needle)
        )

    total = session.exec(select(func.count()).select_from(User).where(*where)).one()
    # ``coalesce`` in the ordering and not only in the projection: a customer
    # with no orders has a null here, and Postgres sorts nulls first on a
    # descending order while SQLite sorts them last. Zero sorts the same way
    # in both, and "nobody who has never bought anything at the top of the
    # biggest-spender list" is the behaviour either way.
    sort = {
        "recent": col(User.created_at).desc(),
        "spend": func.coalesce(history.c.spent, 0).desc(),
        "orders": func.coalesce(history.c.orders, 0).desc(),
    }[ordering]
    rows = session.exec(
        select(User, history.c.orders, history.c.spent, history.c.last_order)
        .outerjoin(history, history.c.user_id == User.id)
        .where(*where)
        # A second key so paging is stable: without it two customers with the
        # same spend can swap places between page one and page two and one of
        # them is never shown.
        .order_by(sort, col(User.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    seen = _last_seen(session, [row[0].id for row in rows])
    return s.Page[s.CustomerRowOut](
        items=[
            _customer_row(account, orders, spent, last_order, seen.get(account.id))
            for account, orders, spent, last_order in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.get(
    "/customers/{user_id}",
    response_model=s.CustomerDetailOut,
    summary="One customer, in full — the screen you open mid-call",
)
def get_customer(
    user_id: int, user: AdminUser, session: SessionDep
) -> s.CustomerDetailOut:
    """Everything about one person, in one response.

    Somebody rings up. Whoever answers has their number and thirty seconds,
    and the questions are always the same: what have they ordered, where do we
    deliver to them, did their card work, and what is sitting in their basket
    that they cannot check out. Six endpoints existed for the customer's own
    app to answer those and none of them for the office, so the answer was the
    owner's memory.

    The basket comes back through the same ``cart_item_out`` the shopper's own
    screen uses, holds and all — so the office sees the line as unavailable
    for the reason the shopper sees it, rather than a second opinion computed
    a different way that disagrees on the telephone.

    A staff id here is a 404. This is the customer screen; a colleague is on
    the staff screen, and answering with their orders would put their saved
    cards on a page reached by guessing an integer.
    """
    account = session.get(User, user_id)
    if account is None or account.role is not UserRole.CUSTOMER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("user_not_found"))

    orders_count, spent, last_order = session.exec(
        select(
            func.count(),
            func.coalesce(
                func.sum(
                    case((Order.status == OrderStatus.DELIVERED, Order.total), else_=0)
                ),
                0,
            ),
            func.max(Order.created_at),
        ).where(Order.user_id == account.id)
    ).one()

    recent = session.exec(
        select(Order)
        .where(Order.user_id == account.id)
        .order_by(col(Order.created_at).desc())
        .limit(RECENT_ORDERS)
    ).all()
    addresses = session.exec(
        select(Address)
        .where(Address.user_id == account.id)
        .order_by(col(Address.is_default).desc(), col(Address.id))
    ).all()
    cards = session.exec(
        select(PaymentCard)
        .where(PaymentCard.user_id == account.id)
        .order_by(col(PaymentCard.is_default).desc(), col(PaymentCard.id))
    ).all()
    favorites = session.exec(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == account.id)
    ).one()

    basket = [
        line
        for line in (sv.cart_item_out(session, item) for item in _cart(session, account))
        if line is not None
    ]

    row = _customer_row(
        account,
        orders_count,
        spent,
        last_order,
        _last_seen(session, [account.id]).get(account.id),
    )
    return s.CustomerDetailOut(
        **row.model_dump(),
        language=account.language,
        birth_date=account.birth_date,
        favorites_count=int(favorites),
        addresses=[sv.address_out(a) for a in addresses],
        cards=[sv.card_out(c) for c in cards],
        orders=[
            s.CustomerOrderOut(
                id=o.id,
                code=o.code,
                status=o.status,
                status_label=sv.order_status_label(o.status),
                total=o.total,
                created_at=o.created_at,
            )
            for o in recent
        ],
        cart=basket,
    )


# --------------------------------------------------------------------------- the trail


@router.get(
    "/audit",
    response_model=s.Page[s.AuditRowOut],
    summary="Who changed what, and when",
)
def list_audit(
    # Admin only, and not the wider backoffice guard. The trail is every
    # change anybody made — a picker's counts, a courier's failed drops, the
    # owner's refunds — and being able to read it is a different thing from
    # being able to do the work. It is also the record that would be read
    # *about* a member of staff.
    user: AdminUser,
    session: SessionDep,
    actor_id: int | None = Query(None, description="Everything one person did"),
    entity: str | None = Query(None, description="`order`, `product`, `user`, …"),
    entity_id: int | None = Query(None, description="Use with `entity`"),
    action: str | None = Query(
        None, description="`user.role`, or `user` for the whole family"
    ),
    q: str | None = Query(None, description="Part of the note, or of either value"),
    from_day: date | None = Query(None, description="Inclusive, UTC"),
    to_day: date | None = Query(None, description="Inclusive, UTC"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> s.Page[s.AuditRowOut]:
    """The table nothing read, read back at last.

    Every filter here is a question somebody has actually asked out loud:
    what happened to order 412 (``entity``/``entity_id``), what did the new
    warehouse lad do on his first day (``actor_id`` and a date), who has been
    changing prices (``action=product.price``), and where did that note about
    a telephone call go (``q``).

    ``action`` matches on a prefix so a family can be asked for as one thing:
    ``user`` brings back ``user.role``, ``user.create``, ``user.active`` and
    ``user.profile``, which is "everything that has been done to accounts" —
    a question with no other way to ask it, since the actions are named in
    dotted pairs precisely so they group.

    Newest first, tie-broken on the id. Rows written in one transaction share
    a timestamp to the microsecond, so an order by time alone is not a total
    order and the same row can appear on two pages while another appears on
    none.
    """
    where = []
    if actor_id is not None:
        where.append(AuditLog.actor_id == actor_id)
    if entity:
        where.append(AuditLog.entity == entity)
    if entity_id is not None:
        where.append(AuditLog.entity_id == entity_id)
    if action:
        where.append(col(AuditLog.action).like(f"{action.strip().lower()}%"))
    if q:
        needle = f"%{q.strip().lower()}%"
        where.append(
            func.lower(AuditLog.note).like(needle)
            | func.lower(func.coalesce(AuditLog.old_value, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.new_value, "")).like(needle)
        )
    if from_day is not None:
        where.append(AuditLog.created_at >= datetime.combine(from_day, time.min))
    if to_day is not None:
        # Inclusive: somebody asking for "the 9th" means the whole of the 9th,
        # and a range whose last day silently returns midnight's rows only is
        # a range that hides the afternoon the question was about.
        where.append(
            AuditLog.created_at < datetime.combine(to_day + timedelta(days=1), time.min)
        )

    total = session.exec(
        select(func.count()).select_from(AuditLog).where(*where)
    ).one()
    rows = session.exec(
        select(AuditLog, User)
        .outerjoin(User, col(User.id) == AuditLog.actor_id)
        .where(*where)
        .order_by(col(AuditLog.created_at).desc(), col(AuditLog.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return s.Page[s.AuditRowOut](
        items=[_audit_out(row, actor) for row, actor in rows],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


# --------------------------------------------------------------------------- helpers


def _account(session: SessionDep, user_id: int) -> User:
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("user_not_found"))
    return account


def _cart(session: SessionDep, account: User) -> list[CartItem]:
    return session.exec(
        select(CartItem)
        .where(CartItem.user_id == account.id)
        .order_by(col(CartItem.created_at))
    ).all()


def _last_seen(session: SessionDep, user_ids: list[int]) -> dict[int, datetime]:
    """When each of these accounts was last used, without a column for it.

    There is no ``last_login`` on ``users`` and this is why one was not added.
    A refresh token row is written when somebody signs in and again on every
    renewal — the token rotates, the old row is marked revoked and a new one
    takes its place — so the newest live row's ``created_at`` is the last time
    that account's session was alive. A stored column would have to be written
    on the hot path of every request to say the same thing, and would be wrong
    for every account that already exists.

    Two consequences, both honest. Signing out revokes everything, so somebody
    who signed out looks like somebody who never signed in: what the field
    really says is "we have a live session from then", which is the thing an
    office wants to know. And the resolution is a session's length rather than
    a minute, which is the right grain for "is this account still somebody's".

    One grouped query for the whole page, for the reason every other list here
    uses one: a timestamp per row is thirty queries to draw a table.
    """
    if not user_ids:
        return {}
    rows = session.exec(
        select(RefreshToken.user_id, func.max(RefreshToken.created_at))
        .where(
            col(RefreshToken.user_id).in_(user_ids),
            col(RefreshToken.revoked).is_(False),
        )
        .group_by(col(RefreshToken.user_id))
    ).all()
    return {int(user_id): when for user_id, when in rows}


def _user_out(row: User) -> s.StaffUserOut:
    return s.StaffUserOut(
        id=row.id,
        phone=row.phone,
        full_name=row.full_name,
        role=row.role,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _staff_out(row: User, last_seen: datetime | None) -> s.StaffMemberOut:
    return s.StaffMemberOut(
        **_user_out(row).model_dump(),
        email=row.email,
        last_seen=last_seen,
    )


def _customer_row(
    row: User,
    orders_count: int | None,
    spent: int | None,
    last_order_at: datetime | None,
    last_seen: datetime | None,
) -> s.CustomerRowOut:
    return s.CustomerRowOut(
        id=row.id,
        phone=row.phone,
        full_name=row.full_name,
        email=row.email,
        is_active=row.is_active,
        created_at=row.created_at,
        # Null out of an outer join means "no orders", not "unknown".
        orders_count=int(orders_count or 0),
        spent=int(spent or 0),
        last_order_at=last_order_at,
        last_seen=last_seen,
    )


def _audit_out(row: AuditLog, actor: User | None) -> s.AuditRowOut:
    return s.AuditRowOut(
        id=row.id,
        created_at=row.created_at,
        actor_id=row.actor_id,
        # Empty rather than a placeholder when the actor is the system — a
        # webhook or a scheduled job — or when the account has since gone.
        actor_name=actor.full_name if actor else "",
        actor_phone=actor.phone if actor else "",
        actor_role=row.actor_role,
        action=row.action,
        entity=row.entity,
        entity_id=row.entity_id,
        field=row.field,
        old_value=row.old_value,
        new_value=row.new_value,
        note=row.note,
    )
