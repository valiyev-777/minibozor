from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_secret,
    new_otp_code,
    now,
    verify_secret,
)
from app.deps import CurrentUser, SessionDep, get_user_by_phone
from app.models import OtpCode, RefreshToken, User
from app.schemas import (
    Message,
    OtpRequested,
    OtpVerifyIn,
    PhoneIn,
    PinChangeIn,
    PinIn,
    RefreshIn,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])

RESEND_AFTER_SECONDS = 30


@router.post("/otp/request", response_model=OtpRequested, summary="Screen 05 — send an SMS code")
def request_otp(payload: PhoneIn, session: SessionDep) -> OtpRequested:
    # Invalidate anything still outstanding for this number.
    for old in session.exec(
        select(OtpCode).where(OtpCode.phone == payload.phone, OtpCode.consumed.is_(False))
    ).all():
        old.consumed = True
        session.add(old)

    code = new_otp_code()
    otp = OtpCode(
        phone=payload.phone,
        code_hash=hash_secret(code),
        expires_at=now() + timedelta(seconds=settings.otp_ttl_seconds),
    )
    session.add(otp)
    session.commit()

    # A production build sends `code` over an SMS gateway here.
    return OtpRequested(
        phone=payload.phone,
        expires_in=settings.otp_ttl_seconds,
        resend_after=RESEND_AFTER_SECONDS,
        dev_code=code if settings.is_dev else None,
    )


@router.post("/otp/verify", response_model=TokenPair, summary="Screen 06 — verify the code")
def verify_otp(payload: OtpVerifyIn, session: SessionDep) -> TokenPair:
    otp = session.exec(
        select(OtpCode)
        .where(OtpCode.phone == payload.phone, OtpCode.consumed.is_(False))
        .order_by(col(OtpCode.created_at).desc())
    ).first()

    if otp is None or otp.expires_at < now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kod eskirgan — qaytadan so'rang")
    if otp.attempts >= settings.otp_max_attempts:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Juda ko'p urinish — qaytadan so'rang"
        )

    if not verify_secret(payload.code, otp.code_hash):
        otp.attempts += 1
        session.add(otp)
        session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kod noto'g'ri")

    otp.consumed = True
    session.add(otp)

    user = get_user_by_phone(session, payload.phone)
    is_new = user is None
    if user is None:
        user = User(phone=payload.phone)
        session.add(user)
        session.commit()
        session.refresh(user)

    pair = _issue_tokens(session, user)
    pair.is_new_user = is_new
    return pair


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, session: SessionDep) -> TokenPair:
    claims = decode_token(payload.refresh_token, "refresh")
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token yaroqsiz")

    user = session.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")

    stored = _find_refresh(session, user.id, payload.refresh_token)
    if stored is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token bekor qilingan")

    # Rotate: a refresh token is single use.
    stored.revoked = True
    session.add(stored)
    return _issue_tokens(session, user)


@router.post("/logout", response_model=Message, summary="Screen 47 — sign out")
def logout(user: CurrentUser, session: SessionDep) -> Message:
    for token in session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
    ).all():
        token.revoked = True
        session.add(token)
    session.commit()
    return Message(message="Hisobdan chiqdingiz")


@router.post("/pin", response_model=Message, summary="Screens 41–44 — set or change the PIN")
def set_pin(payload: PinChangeIn, user: CurrentUser, session: SessionDep) -> Message:
    if user.pin_hash and (
        not payload.current_pin or not verify_secret(payload.current_pin, user.pin_hash)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Joriy kod noto'g'ri")
    user.pin_hash = hash_secret(payload.new_pin)
    session.add(user)
    session.commit()
    return Message(message="PIN o'zgartirildi")


@router.post("/pin/verify", response_model=Message)
def verify_pin(payload: PinIn, user: CurrentUser) -> Message:
    if not user.pin_hash or not verify_secret(payload.pin, user.pin_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PIN noto'g'ri")
    return Message(message="Tasdiqlandi")


@router.delete("/pin", response_model=Message)
def remove_pin(payload: PinIn, user: CurrentUser, session: SessionDep) -> Message:
    if not user.pin_hash or not verify_secret(payload.pin, user.pin_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PIN noto'g'ri")
    user.pin_hash = None
    session.add(user)
    session.commit()
    return Message(message="PIN o'chirildi")


# --------------------------------------------------------------------------- helpers


def _issue_tokens(session: SessionDep, user: User) -> TokenPair:
    access = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(refresh_token),
            expires_at=now() + timedelta(days=settings.refresh_token_days),
        )
    )
    session.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh_token,
        expires_in=settings.access_token_minutes * 60,
    )


def _find_refresh(session: SessionDep, user_id: int, raw: str) -> RefreshToken | None:
    candidates = session.exec(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .order_by(col(RefreshToken.created_at).desc())
    ).all()
    for token in candidates:
        if token.expires_at >= now() and verify_secret(raw, token.token_hash):
            return token
    return None
