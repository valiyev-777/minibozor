"""Wire format.

Response models are deliberately shaped for the screens that consume them, so a
screen is usually one request. Money is always an integer number of so'm; the
apps do the formatting ("1 090 000").
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator

from app.models import (
    CardStatus,
    DeliveryKind,
    Language,
    NotificationKind,
    OrderStatus,
    PaymentMethod,
    ReturnStatus,
    ReviewStatus,
    VariantKind,
)

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_more: bool


class Message(BaseModel):
    ok: bool = True
    message: str = ""


# --------------------------------------------------------------------------- auth

UZ_PHONE = r"^\+998\d{9}$"


class PhoneIn(BaseModel):
    phone: str = Field(pattern=UZ_PHONE, examples=["+998901234567"])

    @field_validator("phone", mode="before")
    @classmethod
    def normalise(cls, v: str) -> str:
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        if digits.startswith("998"):
            return "+" + digits
        if len(digits) == 9:
            return "+998" + digits
        return str(v).strip()


class OtpRequested(BaseModel):
    phone: str
    expires_in: int
    resend_after: int
    # Only populated in dev, so the apps can run without an SMS gateway.
    dev_code: str | None = None


class OtpVerifyIn(PhoneIn):
    code: str = Field(min_length=4, max_length=6)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    is_new_user: bool = False


class RefreshIn(BaseModel):
    refresh_token: str


class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


class PinChangeIn(BaseModel):
    current_pin: str | None = None
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


# --------------------------------------------------------------------------- user


class UserOut(BaseModel):
    id: int
    phone: str
    full_name: str
    email: str | None
    birth_date: date | None
    gender: str | None
    avatar_url: str | None
    language: Language
    has_pin: bool
    biometrics_enabled: bool


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    email: str | None = None
    birth_date: date | None = None
    gender: str | None = None


class SettingsOut(BaseModel):
    language: Language
    location_enabled: bool
    night_mode: bool


class SettingsIn(BaseModel):
    language: Language | None = None
    location_enabled: bool | None = None
    night_mode: bool | None = None


class NotificationPrefsOut(BaseModel):
    order_status: bool
    promotions: bool
    price_drop: bool
    push: bool
    sms: bool


class NotificationPrefsIn(BaseModel):
    order_status: bool | None = None
    promotions: bool | None = None
    price_drop: bool | None = None
    push: bool | None = None
    sms: bool | None = None


# --------------------------------------------------------------------------- catalog


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    subtitle: str
    icon: str
    image_url: str | None
    product_count: int
    has_children: bool = False


class BrandOut(BaseModel):
    id: int
    slug: str
    name: str
    product_count: int = 0


class VariantOut(BaseModel):
    id: int
    kind: VariantKind
    label: str
    value: str
    # The product in this colour, so the picker can show photographs instead of
    # hex swatches. None for sizes, and for a colour nobody photographed.
    image_url: str | None = None
    in_stock: bool
    # How many of this colour are left, when they are counted apart. None means
    # the shelf is only counted as a whole, and the product's own stock_left is
    # the answer.
    stock_left: int | None = None


class SpecOut(BaseModel):
    key: str
    value: str


class ProductCardOut(BaseModel):
    """The tile used by the home grid, rails, search results and favourites."""

    id: int
    title: str
    price: int
    old_price: int | None
    discount_percent: int | None
    image_url: str | None
    rating: float
    reviews_count: int
    badge: str | None
    in_stock: bool
    is_favorite: bool = False
    # How many are left, so a tile can say when there are few. On the card as
    # well as the product page: the grid is where the choosing happens, and
    # "there are two of these" belongs there rather than one tap further in.
    stock_left: int = 0
    # Lets a tile decide between adding straight to the cart and opening the
    # picker sheet, without fetching the whole product first.
    has_variants: bool = False


class ProductOut(ProductCardOut):
    sku: str
    subtitle: str
    description: str
    images: list[str]
    category: CategoryOut
    brand: BrandOut | None
    variants: list[VariantOut]
    specs: list[SpecOut]
    seller: str
    warranty: str | None
    is_original: bool
    free_delivery: bool
    next_day_delivery: bool
    delivery_note: str = ""
    # How many have been sold — the product page prints it beside the rating,
    # where "2 010 ta buyurtma" is the strongest thing on the panel.
    sold_count: int = 0


class RatingBucket(BaseModel):
    stars: int
    count: int
    percent: int


class ReviewSummaryOut(BaseModel):
    rating: float
    total: int
    distribution: list[RatingBucket]
    # A handful of customer photographs for the strip beside the rating, and the
    # full count so the last tile can say how many more there are.
    photos: list[str] = []
    photos_total: int = 0


class ReviewOut(BaseModel):
    id: int
    author_name: str
    author_initials: str
    rating: int
    text: str
    variant_label: str
    tags: list[str]
    photos: list[str]
    likes: int
    liked_by_me: bool = False
    status: ReviewStatus
    created_at: datetime
    product: ProductCardOut | None = None


class ReviewCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = ""
    tags: list[str] = []
    photos: list[str] = []
    variant_label: str = ""
    order_item_id: int | None = None


class BannerOut(BaseModel):
    id: int
    kicker: str
    title: str
    subtitle: str
    cta: str
    image_url: str
    gradient_from: str
    gradient_to: str
    target_type: str
    target_value: str


class SectionOut(BaseModel):
    key: str
    title: str
    subtitle: str
    layout: str
    category_slug: str | None
    products: list[ProductCardOut]


class HomeOut(BaseModel):
    city: str
    banners: list[BannerOut]
    categories: list[CategoryOut]
    sections: list[SectionOut]


class FilterFlagOut(BaseModel):
    key: str
    label: str
    subtitle: str
    count: int


class FiltersOut(BaseModel):
    price_min: int
    price_max: int
    brands: list[BrandOut]
    sizes: list[str]
    ratings: list[str]
    flags: list[FilterFlagOut]
    sorts: list[dict[str, str]]


class SuggestionOut(BaseModel):
    product_id: int
    title: str
    price: int
    image_url: str | None


class SearchLandingOut(BaseModel):
    recent: list[str]
    popular: list[str]


# --------------------------------------------------------------------------- cart


class CartItemOut(BaseModel):
    id: int
    product_id: int
    title: str
    image_url: str | None
    variant_label: str
    unit_price: int
    old_unit_price: int | None
    quantity: int
    selected: bool
    in_stock: bool
    # What the stepper is allowed to reach, so its plus button can stop where
    # the shelf does rather than at an arbitrary ninety-nine.
    stock_left: int = 0
    line_total: int


class CartTotalsOut(BaseModel):
    items_count: int
    subtotal: int
    discount: int
    delivery_fee: int
    total: int
    free_delivery_threshold: int
    promo_code: str | None = None


class CartOut(BaseModel):
    items: list[CartItemOut]
    totals: CartTotalsOut


class CartAddIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    color_variant_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class CartUpdateIn(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=99)
    selected: bool | None = None


class PromoIn(BaseModel):
    code: str


# --------------------------------------------------------------------------- delivery


class AddressOut(BaseModel):
    id: int
    title: str
    icon: str
    badge: str | None
    line: str
    city: str
    meta: str
    floor: str | None
    apartment: str | None
    entrance_code: str | None
    comment: str | None
    latitude: float | None
    longitude: float | None
    is_default: bool


class AddressIn(BaseModel):
    title: str = "Uy"
    icon: str = "pin"
    badge: str | None = None
    line: str
    city: str = "Toshkent"
    floor: str | None = None
    apartment: str | None = None
    entrance_code: str | None = None
    comment: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False


class PickupPointOut(BaseModel):
    id: int
    name: str
    address: str
    hours: str
    distance_km: float | None


class SlotOut(BaseModel):
    id: int
    day: date
    start_time: str
    end_time: str
    label: str
    note: str
    price: int
    express: bool
    available: bool


class SlotDayOut(BaseModel):
    day: date
    weekday_label: str
    day_label: str
    month_label: str
    slots: list[SlotOut]


# --------------------------------------------------------------------------- payment


class CardOut(BaseModel):
    id: int
    brand: str
    last4: str
    holder: str
    expiry: str
    status: CardStatus
    is_default: bool


class CardIn(BaseModel):
    """The app never sends a PAN here.

    A real integration collects the card in the processor's own SDK/webview and
    posts back only the resulting token plus the display fields below.
    """

    brand: str = "Humo"
    last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    holder: str = ""
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2024, le=2099)
    processor_token: str
    is_default: bool = False


# --------------------------------------------------------------------------- orders


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    title: str
    image_url: str
    variant_label: str
    unit_price: int
    quantity: int
    line_total: int
    reviewed: bool


class OrderEventOut(BaseModel):
    status: OrderStatus
    title: str
    happened_at: datetime | None
    note: str
    done: bool


class OrderSummaryOut(BaseModel):
    id: int
    code: str
    status: OrderStatus
    status_label: str
    total: int
    items_count: int
    preview_images: list[str]
    eta_label: str
    created_at: datetime
    can_cancel: bool
    can_track: bool


class OrderOut(OrderSummaryOut):
    delivery_kind: DeliveryKind
    address_line: str
    address_meta: str
    delivery_day: date | None
    delivery_start: str | None
    delivery_end: str | None
    payment_method: PaymentMethod
    payment_label: str
    paid: bool
    recipient_name: str
    recipient_phone: str
    subtotal: int
    delivery_fee: int
    discount: int
    items: list[OrderItemOut]
    events: list[OrderEventOut]


class CheckoutIn(BaseModel):
    address_id: int | None = None
    pickup_point_id: int | None = None
    slot_id: int | None = None
    payment_method: PaymentMethod = PaymentMethod.CARD
    payment_card_id: int | None = None
    recipient_name: str = ""
    recipient_phone: str = ""
    promo_code: str | None = None
    comment: str = ""


class CheckoutPreviewOut(BaseModel):
    items: list[CartItemOut]
    address: AddressOut | None
    pickup_point: PickupPointOut | None
    slot: SlotOut | None
    card: CardOut | None
    totals: CartTotalsOut


class ReasonOut(BaseModel):
    id: int
    label: str
    requires_comment: bool


class CancelIn(BaseModel):
    reason_id: int | None = None
    reason: str = ""
    comment: str = ""


class ReturnIn(BaseModel):
    order_item_id: int | None = None
    reason_id: int | None = None
    reason: str = ""
    comment: str = ""
    photos: list[str] = []


class ReturnOut(BaseModel):
    id: int
    order_code: str
    reason: str
    comment: str
    status: ReturnStatus
    created_at: datetime


# --------------------------------------------------------------------------- misc


class NotificationOut(BaseModel):
    id: int
    kind: NotificationKind
    icon: str
    title: str
    text: str
    deep_link: str | None
    read: bool
    created_at: datetime


class NotificationGroupOut(BaseModel):
    label: str            # "Bugun", "Shu hafta", "Avvalroq"
    items: list[NotificationOut]


class FaqOut(BaseModel):
    id: int
    question: str
    answer: str


class LegalDocOut(BaseModel):
    slug: str
    icon: str
    title: str
    meta: str


class LegalDocFullOut(LegalDocOut):
    body: str


class ProfileOverviewOut(BaseModel):
    user: UserOut
    orders_count: int
    favorites_count: int
    reviews_count: int
    addresses_count: int
    cards_count: int
    unread_notifications: int
