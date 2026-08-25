from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import col, func, select

from app import i18n
from app import schemas as s
from app.deps import CurrentUser, SessionDep
from app.models import (
    Address,
    Favorite,
    Notification,
    Order,
    PaymentCard,
    Review,
    User,
)

router = APIRouter(prefix="/me", tags=["profile"])


def _user_out(user: User) -> s.UserOut:
    return s.UserOut(
        id=user.id,
        phone=user.phone,
        full_name=user.full_name,
        email=user.email,
        birth_date=user.birth_date,
        gender=user.gender,
        avatar_url=user.avatar_url,
        language=user.language,
        has_pin=user.pin_hash is not None,
        biometrics_enabled=user.biometrics_enabled,
    )


@router.get("", response_model=s.UserOut, summary="Screen 31 — personal details")
def me(user: CurrentUser) -> s.UserOut:
    return _user_out(user)


@router.patch("", response_model=s.UserOut)
def update_me(payload: s.UserUpdateIn, user: CurrentUser, session: SessionDep) -> s.UserOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_out(user)


@router.get("/overview", response_model=s.ProfileOverviewOut, summary="Screen 30 — profile")
def overview(user: CurrentUser, session: SessionDep) -> s.ProfileOverviewOut:
    def count(model, *where) -> int:
        return session.exec(select(func.count()).select_from(model).where(*where)).one()

    return s.ProfileOverviewOut(
        user=_user_out(user),
        orders_count=count(Order, Order.user_id == user.id),
        favorites_count=count(Favorite, Favorite.user_id == user.id),
        reviews_count=count(Review, Review.user_id == user.id),
        addresses_count=count(Address, Address.user_id == user.id),
        cards_count=count(PaymentCard, PaymentCard.user_id == user.id),
        unread_notifications=count(
            Notification, Notification.user_id == user.id, col(Notification.read_at).is_(None)
        ),
    )


@router.get("/settings", response_model=s.SettingsOut, summary="Screens 37, 39 — settings")
def get_settings(user: CurrentUser) -> s.SettingsOut:
    return s.SettingsOut(
        language=user.language,
        location_enabled=user.location_enabled,
        night_mode=user.night_mode,
    )


@router.put("/settings", response_model=s.SettingsOut)
def update_settings(payload: s.SettingsIn, user: CurrentUser, session: SessionDep) -> s.SettingsOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return get_settings(user)


@router.get(
    "/notification-prefs",
    response_model=s.NotificationPrefsOut,
    summary="Screen 38 — notification switches",
)
def get_notification_prefs(user: CurrentUser) -> s.NotificationPrefsOut:
    return s.NotificationPrefsOut(
        order_status=user.notify_order_status,
        promotions=user.notify_promotions,
        price_drop=user.notify_price_drop,
        push=user.notify_push,
        sms=user.notify_sms,
    )


@router.put("/notification-prefs", response_model=s.NotificationPrefsOut)
def update_notification_prefs(
    payload: s.NotificationPrefsIn, user: CurrentUser, session: SessionDep
) -> s.NotificationPrefsOut:
    mapping = {
        "order_status": "notify_order_status",
        "promotions": "notify_promotions",
        "price_drop": "notify_price_drop",
        "push": "notify_push",
        "sms": "notify_sms",
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, mapping[key], value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return get_notification_prefs(user)


@router.put("/biometrics", response_model=s.UserOut, summary="Screen 40 — Face ID / fingerprint")
def set_biometrics(enabled: bool, user: CurrentUser, session: SessionDep) -> s.UserOut:
    user.biometrics_enabled = enabled
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_out(user)


@router.delete("", response_model=s.Message, summary="Delete the account")
def delete_account(user: CurrentUser, session: SessionDep) -> s.Message:
    user.is_active = False
    session.add(user)
    session.commit()
    return s.Message(message=i18n.label("account_deleted"))
