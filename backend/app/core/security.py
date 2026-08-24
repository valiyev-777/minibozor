from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_secret(raw: str) -> str:
    """Hash a PIN / OTP / refresh token. Never store any of these in the clear."""
    return _hasher.hash(raw)


def verify_secret(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, Exception):  # noqa: BLE001 - any argon2 error means "no"
        return False


def now() -> datetime:
    """Naive UTC.

    SQLite hands back naive datetimes, so storing aware ones makes every later
    comparison raise. We normalise on the way in instead.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def _create_token(subject: str, token_type: TokenType, expires: timedelta) -> str:
    # Aware UTC here on purpose: `.timestamp()` on a naive datetime is read as
    # local time, which would shift `iat`/`exp` by the machine's UTC offset.
    issued = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(issued.timestamp()),
        "exp": int((issued + expires).timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(str(user_id), "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: int) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != expected_type:
        return None
    return payload


def new_otp_code() -> str:
    if settings.is_dev:
        return settings.otp_dev_code
    return f"{secrets.randbelow(1_000_000):06d}"
