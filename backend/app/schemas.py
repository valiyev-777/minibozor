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
    UserRole,
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
    # How many of this colour, or of this size in this colour, are left. None
    # means the shelf is only counted as a whole, and the product's own
    # stock_left is the answer.
    stock_left: int | None = None
    # The colour a size belongs to: sizes are counted per colour, so a page
    # showing one colour shows that colour's sizes. Null on a colour, and on a
    # size of a product that has no colours.
    parent_id: int | None = None


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
    # Every photograph the card may swipe through, the first of them being
    # `image_url` again. A client that does not know about this field shows the
    # one picture it always did.
    images: list[str] = []
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
    # Which size and which colour this line is, and not only what they are
    # called. The label is one joined string for reading; a client deciding
    # whether *this* line is the one the product page is currently showing
    # needs the ids it was added with, and without them the page could only
    # match on the product — so a shirt in the basket in medium left no way to
    # add a large.
    variant_id: int | None = None
    color_variant_id: int | None = None
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
    # Added rather than changed: the apps read the fields they know and ignore
    # this one until they are taught about it. Nought until a refund is made.
    refund_amount: int = 0
    created_at: datetime


# --------------------------------------------------------------------------- offers


class SellerOut(BaseModel):
    id: int
    name: str


class OfferOut(BaseModel):
    """One seller's price for a product.

    An addition, not a change: every existing response still carries the
    winning offer's figures in the fields it always did. This is the list
    behind that one number.
    """

    id: int
    seller: SellerOut
    price: int
    old_price: int | None
    discount_percent: int | None
    stock_left: int
    in_stock: bool
    # Whose price the product card is showing. Exactly one offer has it, and
    # only while it has something left.
    is_winner: bool


class StaffOfferVariantOut(BaseModel):
    variant_id: int
    kind: VariantKind
    label: str
    parent_id: int | None
    stock_left: int


class StaffOfferOut(BaseModel):
    """An offer as the seller who owns it, or an admin, needs to see it."""

    id: int
    seller: SellerOut
    product_id: int
    product_title: str
    price: int
    old_price: int | None
    stock_left: int
    active: bool
    is_winner: bool
    variants: list[StaffOfferVariantOut]
    created_at: datetime


class OfferCreateIn(BaseModel):
    """Offering a product at a price.

    ``variant_ids`` is what closes a hole rather than ceremony. An offer that
    named no variants used to win the card and leave every colour of the
    product without a count, because a colour with no row on the winning offer
    reads as "nobody counts this apart". Listing them says which colours and
    sizes this offer is for; how many of each is the warehouse's answer, and
    starts at nought.
    """

    product_id: int
    price: int = Field(gt=0)
    old_price: int | None = Field(None, gt=0)
    active: bool = True
    # Admin only. A seller offers as themselves and may not say otherwise.
    seller_id: int | None = None
    variant_ids: list[int] = Field(default_factory=list, max_length=200)


class OfferUpdateIn(BaseModel):
    """What a seller may change: the price, and whether they are still selling.

    ``old_price`` set to 0 removes the struck-through price; omitted leaves it
    as it was. Stock is deliberately absent — see ``PUT .../stock``.
    """

    price: int | None = Field(None, gt=0)
    old_price: int | None = Field(None, ge=0)
    active: bool | None = None


class OfferVariantStockIn(BaseModel):
    variant_id: int
    stock_left: int = Field(ge=0)


class OfferStockIn(BaseModel):
    """Warehouse intake: the counts, and nothing else about the offer.

    Only the leaves are given — the sizes of a product that has sizes, its
    colours otherwise. Colour totals and the offer's own total are computed
    from them, so a shelf cannot be left disagreeing with itself.
    ``stock_left`` is for a product with no variants at all, where the offer
    *is* the leaf.
    """

    stock_left: int | None = Field(None, ge=0)
    variants: list[OfferVariantStockIn] = Field(default_factory=list, max_length=200)


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


# --------------------------------------------------------------------------- staff


class StaffMeOut(BaseModel):
    """Who the backoffice is talking to, and therefore which one to show.

    Separate from ``UserOut`` on purpose: the apps' shape must not change, and
    a backoffice asks a different question — not "what is my profile" but
    "what am I allowed to do here".
    """

    id: int
    phone: str
    full_name: str
    role: UserRole


# ------------------------------------------------------------------ backoffice

# The customer's shapes above are shipped and read by two apps, so none of
# them changes. A backoffice asks different questions of the same rows — whose
# order is this, what may I do to it next — and gets its own shapes for them.


class StaffReturnOut(BaseModel):
    id: int
    order_id: int
    order_code: str
    order_item_id: int | None
    customer_name: str
    customer_phone: str
    reason: str
    comment: str
    photos: list[str]
    status: ReturnStatus
    resolution: str
    refund_amount: int
    next_statuses: list[ReturnStatus]
    created_at: datetime


class StaffReviewOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    author_name: str
    author_phone: str
    rating: int
    text: str
    photos: list[str]
    status: ReviewStatus
    next_statuses: list[ReviewStatus]
    created_at: datetime


class DecisionIn(BaseModel):
    """A refusal, or a note on an approval.

    ``reason`` is what the customer is told and is required to refuse
    something; ``note`` is internal and lands in the audit log — a ticket
    number, who rang, what they said.
    """

    reason: str = ""
    note: str = ""


class RefundIn(DecisionIn):
    """Paying a return back, and saying where the goods went.

    ``restock`` is required. Returned goods are inspected first: what came
    back whole goes on the shelf, what came back damaged goes on nobody's
    count. There is no sensible default for that, and a default would mean a
    count moving by omission.
    """

    restock: bool


class StaffOrderOut(BaseModel):
    """One row of the operator's queue."""

    id: int
    code: str
    status: OrderStatus
    status_label: str
    customer_name: str
    customer_phone: str
    delivery_kind: DeliveryKind
    address_line: str
    delivery_day: date | None
    delivery_window: str
    items_count: int
    total: int
    paid: bool
    # What this order may become next. The backoffice draws its buttons from
    # this rather than from its own copy of the rules, so the two cannot drift.
    next_statuses: list[OrderStatus]
    created_at: datetime


class OrderStatusIn(BaseModel):
    status: OrderStatus
    note: str = ""


class StaffSlotOut(BaseModel):
    id: int
    day: date
    start_time: str
    end_time: str
    note: str
    price: int
    express: bool
    capacity_left: int


class SlotWindowIn(BaseModel):
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["09:00"])
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["13:00"])
    note: str = ""
    price: int = Field(0, ge=0)
    express: bool = False
    capacity: int = Field(20, ge=0)


class SlotCreateIn(BaseModel):
    """Open the same windows across a set of days.

    A day at a time would mean four calls per day and twenty-eight to fill a
    week, which is why the shop ran out of slots in the first place. Days that
    already have a window with the same hours are left alone, so "top up the
    next fortnight" can be run again tomorrow without doubling anything.
    """

    days: list[date] = Field(min_length=1, max_length=60)
    windows: list[SlotWindowIn] = Field(min_length=1, max_length=12)

    @field_validator("windows")
    @classmethod
    def _ends_after_it_starts(cls, windows: list[SlotWindowIn]) -> list[SlotWindowIn]:
        for w in windows:
            if w.end_time <= w.start_time:
                raise ValueError("a window has to end after it starts")
        return windows


class SlotUpdateIn(BaseModel):
    """Only what is given is changed — an absent field is not "set to nothing"."""

    capacity_left: int | None = Field(None, ge=0)
    price: int | None = Field(None, ge=0)
    note: str | None = None
    express: bool | None = None
