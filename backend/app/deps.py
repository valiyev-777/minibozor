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

# Running the shop day to day: return decisions, review moderation, moving an
# order along, opening delivery windows. The admin is included because an admin
# who cannot do the operator's job is an admin who has to hand out a second
# account to get anything done.
#
# Warehouse and courier belong on some of this later — picking is theirs, and
# so is the doorstep — but that is a rule per transition rather than per
# endpoint, and it wants their screens to exist first.
OperatorUser = Annotated[
    User, Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN))
]

# Setting a price. A seller decides what their goods cost and nothing else
# about them — under this model the goods are in our warehouse and we ship
# them, so the shelf is not theirs to count.
SellerUser = Annotated[User, Depends(require_role(UserRole.SELLER, UserRole.ADMIN))]

# Counting the shelf. A stock figure changes when something is booked in or out
# of the warehouse, so it is the warehouse's to move — never the seller's, who
# would otherwise be able to promise goods nobody has received.
#
# The warehouse module does not exist yet. The boundary is drawn now anyway:
# moving it later means finding every caller that grew up on the wrong side
# of it.
WarehouseUser = Annotated[
    User, Depends(require_role(UserRole.WAREHOUSE, UserRole.ADMIN))
]

# Reading the goods: a seller's own supplies and removals, all of them for the
# warehouse. The scoping is done in the endpoint — a seller sees their own
# rows and nobody else's, which is not a filter they choose but the only rows
# that exist for them.
StockViewer = Annotated[
    User,
    Depends(require_role(UserRole.SELLER, UserRole.WAREHOUSE, UserRole.ADMIN)),
]


def get_user_by_phone(session: Session, phone: str) -> User | None:
    return session.exec(select(User).where(User.phone == phone)).first()
