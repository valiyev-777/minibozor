from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app import i18n
from app.core.security import decode_token
from app.db import get_session
from app.models import STAFF_ROLES, User, UserRole

SessionDep = Annotated[Session, Depends(get_session)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = _bearer(authorization)
    payload = decode_token(token, "access") if token else None
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=i18n.label("auth_required"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=i18n.label("user_not_found"),
        )
    return user


def get_optional_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """For catalogue endpoints: anonymous browsing works, but a signed-in user
    additionally gets ``is_favorite`` populated."""
    token = _bearer(authorization)
    payload = decode_token(token, "access") if token else None
    if not payload:
        return None
    return session.get(User, int(payload["sub"]))


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_role(*roles: UserRole | Iterable[UserRole]) -> Callable[[User], User]:
    """A dependency that only lets the listed roles through.

    For backoffice endpoints. Customer endpoints keep ``CurrentUser``: every
    signed-in person owns their own cart and orders, so there is nothing there
    for a role to decide.

    Signing in is unchanged — the same OTP, the same token. This only reads the
    role off the user the token already identified, which is why a 401 and a
    403 stay distinct: "we don't know who you are" against "we know, and this
    isn't yours".

        AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]

        @router.post("/products/{product_id}/price")
        def set_price(product_id: int, user: AdminUser, ...): ...
    """
    allowed: set[UserRole] = set()
    for role in roles:
        if isinstance(role, UserRole):
            allowed.add(role)
        else:
            allowed.update(role)

    def guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=i18n.label("forbidden"),
            )
        return user

    return guard


# The two guards a backoffice needs before it has any screens of its own:
# anyone who works here, and the person who may change anything.
StaffUser = Annotated[User, Depends(require_role(STAFF_ROLES))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]

# Running the shop day to day: return decisions, moving an order along,
# opening delivery windows. There is no separate operator any more — the owner
# takes the calls — so this is the admin, named for the job rather than for
# the role, because the endpoints that use it are about the work and not about
# who happens to do it this year.
OperatorUser = AdminUser

# Who may put a picture on the server. Everyone whose work produces one: an
# admin writing a card, the receiving desk photographing a pile it has just
# sorted, a courier standing on a doorstep. Not a customer — their review
# photos come in through the review endpoint, which knows what they are for.
MediaUploader = Annotated[
    User,
    Depends(
        require_role(
            UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.SELLER, UserRole.COURIER
        )
    ),
]

# Counting the shelf. A stock figure changes when something is booked in or
# out of the warehouse, so it is the warehouse's to move.
WarehouseUser = Annotated[
    User, Depends(require_role(UserRole.WAREHOUSE, UserRole.ADMIN))
]

# Reading the goods: the market runs, the ledger, what is on which shelf.
StockViewer = WarehouseUser

# The last mile. Couriers only, and deliberately not admins: every door in
# ``app.routers.courier`` is scoped to the caller's own round, and an admin
# has none — they would be handed empty lists. An admin watches the rounds
# through the office screens, where the audit trail records that they looked.
CourierUser = Annotated[User, Depends(require_role(UserRole.COURIER))]

# Reading a return request. A returned shirt passes through two hands and both
# have a question only this row answers: the office decides the money and the
# warehouse says what arrived. Not a customer — their own request is on their
# own orders screen, in the shape the shipped apps already read.
ReturnViewer = Annotated[
    User, Depends(require_role(UserRole.WAREHOUSE, UserRole.ADMIN))
]

# Reading the order queue. Three jobs on one list, which is why it is one
# endpoint with a status filter rather than three renderings of `orders`: the
# office runs it, the warehouse picks from it, and the shop assistant is the
# one who picks up the telephone. A customer ringing to ask where their order
# is used to be a question only the owner could answer, which meant the owner
# answered the telephone all day.
OrderViewer = Annotated[
    User,
    Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.SELLER)),
]

# Reading the catalogue's own vocabulary — the categories and brands a card
# can be filed under. The receiving desk picks from both while sorting a
# sack, so reading is theirs; *writing* one is not, and stays `AdminUser` on
# the same paths.
CatalogReader = Annotated[
    User, Depends(require_role(UserRole.WAREHOUSE, UserRole.SELLER, UserRole.ADMIN))
]

# Writing the shop window: the photographs, the words, the price, and the
# switch that puts a card on sale. The seller's whole job, and the admin
# because they own the place — but not the warehouse, whose business with a
# card ends when the goods are on a shelf.
CatalogWriter = Annotated[
    User, Depends(require_role(UserRole.SELLER, UserRole.ADMIN))
]

# The shop's own figures. Everybody who works here except the courier, whose
# screens are their own round and nothing else: the seller's menu carries the
# publishing queue's count, and that count comes from here — a badge that
# 403s is a badge that never appears, on the one queue nothing else reminds
# anybody about.
DashboardViewer = Annotated[
    User,
    Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.SELLER)),
]

# Moving an order along. The warehouse and the shop assistant join the office
# here because most of the moves are theirs: a picker marks an order picked,
# and the assistant on the telephone is the one who hears that it arrived.
# Which moves each of them may make is decided inside the endpoint, because it
# is a rule per transition and not per door — **cancelling is the owner's**,
# and neither a picker at the bench nor an assistant on the telephone should
# be able to call off a sale. Somebody has to answer for a cancelled order,
# and that is the person whose shop it is.
OrderMover = OrderViewer

# Handling the goods once they are back: a courier brings a collection in and
# the warehouse books it, so both need to read a run.
PickupHandler = Annotated[
    User,
    Depends(require_role(UserRole.COURIER, UserRole.WAREHOUSE, UserRole.ADMIN)),
]


def get_user_by_phone(session: Session, phone: str) -> User | None:
    return session.exec(select(User).where(User.phone == phone)).first()
