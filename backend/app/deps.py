from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.core.security import decode_token
from app.db import get_session
from app.models import User

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
            detail="Avtorizatsiya talab qilinadi",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi"
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


def get_user_by_phone(session: Session, phone: str) -> User | None:
    return session.exec(select(User).where(User.phone == phone)).first()
