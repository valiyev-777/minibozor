"""Answering in the language the app asked for.

Two different kinds of text need translating and they are handled separately:

* **Labels written in code** — order statuses, delivery wording, sort options,
  error details. These live in [LABELS] below, next to the code that uses them.
* **Content in the database** — category names, banner copy, product
  descriptions, the FAQ. These live in the ``translation`` table, keyed by the
  row they belong to, so new content can be translated without a deploy.

The active language is a context variable set once per request by the
middleware in ``app.main``. That keeps it out of twenty function signatures in
``services.py``, which otherwise thread only a session around.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, timedelta

from sqlmodel import Session, select

DEFAULT = "uz"
SUPPORTED = (DEFAULT, "ru", "en")

_lang: ContextVar[str] = ContextVar("lang", default=DEFAULT)
_cache: ContextVar[dict | None] = ContextVar("translation_cache", default=None)


def parse_accept_language(header: str | None) -> str:
    """First supported language in an Accept-Language header, else Uzbek.

    Quality values are honoured so a browser sending ``ru;q=0.9, en;q=0.8``
    gets Russian, but the app sends a bare tag like ``ru``.
    """
    if not header:
        return DEFAULT
    entries: list[tuple[float, str]] = []
    for part in header.split(","):
        piece, _, params = part.strip().partition(";")
        tag = piece.strip().lower().split("-")[0]
        quality = 1.0
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        if tag in SUPPORTED:
            entries.append((quality, tag))
    if not entries:
        return DEFAULT
    return max(entries, key=lambda e: e[0])[1]


def set_language(lang: str) -> None:
    _lang.set(lang if lang in SUPPORTED else DEFAULT)
    _cache.set(None)


def current() -> str:
    return _lang.get()


# ─────────────────────────────── labels in code ────────────────────────────

LABELS: dict[str, dict[str, str]] = {
    # order status and delivery
    "delivered": {"uz": "Yetkazildi", "ru": "Доставлен", "en": "Delivered"},
    "cancelled": {"uz": "Bekor qilindi", "ru": "Отменён", "en": "Cancelled"},
    "pickup": {"uz": "Punktdan olish", "ru": "Самовывоз", "en": "Pick-up point"},
    "eta_pending": {
        "uz": "Yetkazish sanasi aniqlanmoqda",
        "ru": "Дата доставки уточняется",
        "en": "Delivery date being confirmed",
    },
    "between": {"uz": "{label} {window} orasida", "ru": "{label} с {window}",
                "en": "{label} between {window}"},
    "delivered_on": {"uz": "{date} yetkaziladi", "ru": "Доставим {date}",
                     "en": "Arrives {date}"},
    "today": {"uz": "Bugun", "ru": "Сегодня", "en": "Today"},
    "tomorrow": {"uz": "Ertaga", "ru": "Завтра", "en": "Tomorrow"},
    "eta_next_day": {"uz": "Ertaga yetkaziladi", "ru": "Доставим завтра",
                     "en": "Arrives tomorrow"},
    "eta_few_days": {"uz": "2–3 kunda yetkaziladi", "ru": "Доставим за 2–3 дня",
                     "en": "Arrives in 2–3 days"},
    "eta_free_suffix": {"uz": " · bepul", "ru": " · бесплатно", "en": " · free"},
    "doc_not_found": {"uz": "Hujjat topilmadi", "ru": "Документ не найден",
                      "en": "Document not found"},
    "support_hours": {"uz": "Har kuni 08:00–22:00", "ru": "Ежедневно 08:00–22:00",
                      "en": "Every day 08:00–22:00"},
    # messages returned by the routers
    "otp_expired": {
        "uz": "Kod eskirgan — qaytadan so'rang",
        "ru": "Код устарел — запросите новый",
        "en": "That code has expired — request a new one",
    },
    "otp_too_many": {
        "uz": "Juda ko'p urinish — qaytadan so'rang",
        "ru": "Слишком много попыток — запросите новый код",
        "en": "Too many attempts — request a new code",
    },
    "otp_wrong": {"uz": "Kod noto'g'ri", "ru": "Неверный код", "en": "That code isn't right"},
    "user_not_found": {
        "uz": "Foydalanuvchi topilmadi",
        "ru": "Пользователь не найден",
        "en": "User not found",
    },
    "signed_out": {
        "uz": "Hisobdan chiqdingiz",
        "ru": "Вы вышли из аккаунта",
        "en": "You've been signed out",
    },
    "pin_current_wrong": {
        "uz": "Joriy kod noto'g'ri",
        "ru": "Неверный текущий код",
        "en": "That current code isn't right",
    },
    "pin_changed": {"uz": "PIN o'zgartirildi", "ru": "PIN изменён", "en": "PIN changed"},
    "pin_wrong": {"uz": "PIN noto'g'ri", "ru": "Неверный PIN", "en": "That PIN isn't right"},
    "pin_removed": {"uz": "PIN o'chirildi", "ru": "PIN удалён", "en": "PIN removed"},
    "card_expired": {
        "uz": "Kartaning muddati o'tgan",
        "ru": "Срок действия карты истёк",
        "en": "That card has expired",
    },
    "card_removed": {"uz": "Karta o'chirildi", "ru": "Карта удалена", "en": "Card removed"},
    "card_not_found": {"uz": "Karta topilmadi", "ru": "Карта не найдена", "en": "Card not found"},
    "product_not_found": {
        "uz": "Mahsulot topilmadi",
        "ru": "Товар не найден",
        "en": "Product not found",
    },
    "product_out_of_stock": {
        "uz": "Mahsulot mavjud emas",
        "ru": "Товара нет в наличии",
        "en": "That product is out of stock",
    },
    "variant_invalid": {
        "uz": "Variant noto'g'ri",
        "ru": "Неверный вариант",
        "en": "That option isn't valid",
    },
    "cart_item_not_found": {
        "uz": "Savatda topilmadi",
        "ru": "Не найдено в корзине",
        "en": "Not found in your cart",
    },
    "category_not_found": {
        "uz": "Turkum topilmadi",
        "ru": "Категория не найдена",
        "en": "Category not found",
    },
    "address_removed": {"uz": "Manzil o'chirildi", "ru": "Адрес удалён", "en": "Address removed"},
    "address_not_found": {
        "uz": "Manzil topilmadi",
        "ru": "Адрес не найден",
        "en": "Address not found",
    },
    "fav_added": {
        "uz": "Sevimlilarga qo'shildi",
        "ru": "Добавлено в избранное",
        "en": "Added to favourites",
    },
    "fav_removed": {
        "uz": "Sevimlilardan olib tashlandi",
        "ru": "Убрано из избранного",
        "en": "Removed from favourites",
    },
    "marked_read": {
        "uz": "O'qilgan deb belgilandi",
        "ru": "Отмечено как прочитанное",
        "en": "Marked as read",
    },
    "deleted": {"uz": "O'chirildi", "ru": "Удалено", "en": "Deleted"},
    "cart_empty": {"uz": "Savat bo'sh", "ru": "Корзина пуста", "en": "Your cart is empty"},
    "order_placed": {"uz": "Buyurtma qabul qilindi", "ru": "Заказ принят", "en": "Order placed"},
    "order_not_cancellable": {
        "uz": "Bu buyurtmani bekor qilib bo'lmaydi",
        "ru": "Этот заказ отменить нельзя",
        "en": "This order can't be cancelled",
    },
    "order_cancelled": {
        "uz": "Buyurtma bekor qilindi",
        "ru": "Заказ отменён",
        "en": "Order cancelled",
    },
    "return_delivered_only": {
        "uz": "Faqat yetkazilgan buyurtmani qaytarish mumkin",
        "ru": "Вернуть можно только доставленный заказ",
        "en": "Only a delivered order can be returned",
    },
    "order_not_found": {
        "uz": "Buyurtma topilmadi",
        "ru": "Заказ не найден",
        "en": "Order not found",
    },
    "account_deleted": {"uz": "Hisob o'chirildi", "ru": "Аккаунт удалён", "en": "Account deleted"},
    "review_not_found": {
        "uz": "Sharh topilmadi",
        "ru": "Отзыв не найден",
        "en": "Review not found",
    },
    "review_removed": {"uz": "Sharh o'chirildi", "ru": "Отзыв удалён", "en": "Review removed"},
    "order_placed_note": {
        "uz": "{code} qabul qilindi — tez orada yig'amiz",
        "ru": "{code} принят — скоро начнём сборку",
        "en": "{code} placed — we'll start picking shortly",
    },
    "order_cancelled_note": {
        "uz": "{code} bekor qilindi. To'lov 1–3 kunda qaytariladi.",
        "ru": "{code} отменён. Оплата вернётся за 1–3 дня.",
        "en": "{code} cancelled. The payment returns within 1–3 days.",
    },
    # order status pills and timeline
    "status_placed": {"uz": "QABUL QILINDI", "ru": "ПРИНЯТ", "en": "PLACED"},
    "status_packing": {"uz": "YIG'ILMOQDA", "ru": "СОБИРАЕТСЯ", "en": "PACKING"},
    "status_shipped": {"uz": "YO'LDA", "ru": "В ПУТИ", "en": "ON THE WAY"},
    "status_delivered": {"uz": "YETKAZILDI", "ru": "ДОСТАВЛЕН", "en": "DELIVERED"},
    "status_cancelled": {"uz": "BEKOR QILINDI", "ru": "ОТМЕНЁН", "en": "CANCELLED"},
    "status_returned": {"uz": "QAYTARILDI", "ru": "ВОЗВРАЩЁН", "en": "RETURNED"},
    "event_placed": {"uz": "Buyurtma qabul qilindi", "ru": "Заказ принят",
                     "en": "Order placed"},
    "event_packing": {"uz": "Omborda yig'ildi", "ru": "Собран на складе",
                      "en": "Picked at the warehouse"},
    "event_shipped": {"uz": "Kuryerga topshirildi", "ru": "Передан курьеру",
                      "en": "Handed to the courier"},
    "event_delivered": {"uz": "Yetkazildi", "ru": "Доставлен", "en": "Delivered"},
    # payment
    "cash_courier": {"uz": "Naqd pul · kuryerga", "ru": "Наличные · курьеру",
                     "en": "Cash · to the courier"},
    "card": {"uz": "Karta", "ru": "Карта", "en": "Card"},
    "paid": {"uz": "to'landi", "ru": "оплачено", "en": "paid"},
    "unpaid": {"uz": "to'lanmagan", "ru": "не оплачено", "en": "unpaid"},
    "card_masked": {"uz": "Karta ···· {last4} · {state}",
                    "ru": "Карта ···· {last4} · {state}",
                    "en": "Card ···· {last4} · {state}"},
    # filter flags and rating buckets
    "flag_next_day_delivery": {"uz": "Ertaga yetkaziladi", "ru": "Доставка завтра",
                               "en": "Arrives tomorrow"},
    "flag_next_day_delivery_sub": {"uz": "Toshkent bo'ylab", "ru": "По Ташкенту",
                                   "en": "Across Tashkent"},
    "flag_free_delivery": {"uz": "Bepul yetkazish", "ru": "Бесплатная доставка",
                           "en": "Free delivery"},
    "flag_free_delivery_sub": {"uz": "250 000 so'mdan yuqori", "ru": "от 250 000 сум",
                               "en": "Over 250,000 UZS"},
    "flag_discounted": {"uz": "Chegirmada", "ru": "Со скидкой", "en": "On sale"},
    "flag_discounted_sub": {"uz": "Faqat arzonlashgan tovarlar",
                            "ru": "Только уценённые товары",
                            "en": "Discounted items only"},
    "flag_is_original": {"uz": "Original kafolati", "ru": "Гарантия оригинала",
                         "en": "Authenticity guaranteed"},
    "flag_is_original_sub": {"uz": "Tekshirilgan sotuvchilar",
                             "ru": "Проверенные продавцы",
                             "en": "Vetted sellers"},
    "rating_45": {"uz": "4.5 ★ dan yuqori", "ru": "Выше 4.5 ★", "en": "Above 4.5 ★"},
    "rating_40": {"uz": "4.0 ★ dan yuqori", "ru": "Выше 4.0 ★", "en": "Above 4.0 ★"},
    "rating_many": {"uz": "Sharhi ko'p", "ru": "Много отзывов", "en": "Many reviews"},
    # sort options
    "sort_popular": {"uz": "Ommabop", "ru": "Популярные", "en": "Popular"},
    "sort_price_asc": {"uz": "Avval arzoni", "ru": "Сначала дешёвые",
                       "en": "Cheapest first"},
    "sort_price_desc": {"uz": "Avval qimmati", "ru": "Сначала дорогие",
                        "en": "Most expensive first"},
    "sort_rating": {"uz": "Reyting bo'yicha", "ru": "По рейтингу", "en": "By rating"},
    "sort_new": {"uz": "Yangilari", "ru": "Новинки", "en": "New arrivals"},
    "sort_discount": {"uz": "Chegirma bo'yicha", "ru": "По скидке", "en": "By discount"},
}

MONTHS: dict[str, list[str]] = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}

WEEKDAYS: dict[str, list[str]] = {
    "uz": ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"],
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}

# Uzbek writes 22-avgust, Russian 22 августа, English 22 August.
DATE_FORMAT = {"uz": "{day}-{month}", "ru": "{day} {month}", "en": "{day} {month}"}


def label(key: str, **fmt: object) -> str:
    """A code-level label in the active language, falling back to Uzbek."""
    entry = LABELS.get(key)
    if entry is None:
        return key
    text = entry.get(current()) or entry[DEFAULT]
    return text.format(**fmt) if fmt else text


def month_name(month: int) -> str:
    return MONTHS.get(current(), MONTHS[DEFAULT])[month - 1]


def weekday_name(weekday: int) -> str:
    return WEEKDAYS.get(current(), WEEKDAYS[DEFAULT])[weekday]


def format_date(d: date) -> str:
    return DATE_FORMAT.get(current(), DATE_FORMAT[DEFAULT]).format(
        day=d.day, month=month_name(d.month)
    )


def day_label(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        return label("today")
    if d == today + timedelta(days=1):
        return label("tomorrow")
    return weekday_name(d.weekday())


# ─────────────────────────────── content in the DB ─────────────────────────

def _load(session: Session) -> dict[tuple[str, int, str], str]:
    """Every translation for the active language, read once per request.

    One query for the whole table rather than a join per row: the catalogue is
    a few hundred rows per language, and the alternative is an extra lookup for
    every card in a listing.
    """
    from app.models import Translation

    cached = _cache.get()
    if cached is not None:
        return cached
    lang = current()
    if lang == DEFAULT:
        table: dict[tuple[str, int, str], str] = {}
    else:
        rows = session.exec(select(Translation).where(Translation.lang == lang)).all()
        table = {(r.entity, r.entity_id, r.field): r.value for r in rows}
    _cache.set(table)
    return table


def t(session: Session, entity: str, entity_id: int | None, field: str, default: str) -> str:
    """A translated field, falling back to the Uzbek text already on the row."""
    if entity_id is None or current() == DEFAULT:
        return default
    return _load(session).get((entity, entity_id, field)) or default
