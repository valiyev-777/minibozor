"""Wire format.

Response models are deliberately shaped for the screens that consume them, so a
screen is usually one request. Money is always an integer number of so'm; the
apps do the formatting ("1 090 000").
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    AttemptResult,
    CardStatus,
    DeliveryKind,
    Language,
    NotificationKind,
    OrderStatus,
    PaymentMethod,
    PickupRunStatus,
    ProductStatus,
    RemovalReason,
    RemovalStatus,
    ReturnInspection,
    ReturnStatus,
    SellerReturnDecision,
    SettlementStatus,
    StatementLineKind,
    StockMovementKind,
    SupplyStatus,
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


# --------------------------------------------------------------------------- translations

# The apps are trilingual and a new card is written in Uzbek, so every card
# added without the other two makes the catalogue a little more Uzbek than it
# says it is. These ride along on the write that creates the row, because a
# translation asked for as a second step is a translation nobody does.
#
# The Uzbek is the row itself — ``Product.title`` — and is not repeated here.
# What goes in the ``translation`` table is only what differs from it.

Lang = Literal["ru", "en"]


class TextIn(BaseModel):
    """One language's version of a row's words.

    Unknown fields are refused rather than dropped: a payload naming
    ``name`` where the shape wants ``title`` has a bug in it, and silently
    saving nothing would hide it until somebody switched the app to Russian.

    A field left out is left alone; a field given as ``null`` or blank has its
    translation removed, so the row falls back to its Uzbek again.
    """

    model_config = ConfigDict(extra="forbid")


class ProductTextIn(TextIn):
    title: str | None = Field(None, max_length=200)
    subtitle: str | None = None
    description: str | None = None
    badge: str | None = None
    warranty: str | None = None


class CategoryTextIn(TextIn):
    name: str | None = Field(None, max_length=120)
    subtitle: str | None = None


class BrandTextIn(TextIn):
    name: str | None = Field(None, max_length=120)


class VariantTextIn(TextIn):
    label: str | None = Field(None, max_length=60)


class SpecTextIn(TextIn):
    key: str | None = Field(None, max_length=80)
    value: str | None = Field(None, max_length=200)


class TranslationsOut(BaseModel):
    """What is held for one row, in every language at once.

    The read path answers in one language and falls back to Uzbek without
    saying so, which is right for a shopper and useless to somebody trying to
    see what is still missing.
    """

    entity: str
    entity_id: int
    uz: dict[str, str]
    translations: dict[str, dict[str, str]]


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


class DeliveryAttemptOut(BaseModel):
    """One knock at one door.

    The courier's own list carries a *count* and the last reason, which is
    what somebody about to knock needs. An operator is answering a different
    question — has this been tried enough to give up on — and a number cannot
    answer it: three attempts at one wrong buzzer and three on three different
    days are the same count and different decisions. So this is the row, with
    who knocked and when.

    ``courier_name`` and not ``courier_id``: an operator ringing the customer
    to ask what happened wants to know which of their couriers to ask next,
    and an id is not something anybody says out loud.
    """

    id: int
    order_id: int
    order_code: str
    courier_name: str
    result: AttemptResult
    reason: str
    recipient_name: str
    photo_url: str | None
    cash_collected: int
    happened_at: datetime


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
    # Every knock, and empty for a customer looking at their own order — the
    # doors that were tried are staff's business and the customer's timeline
    # already says "on its way".
    #
    # It lives on the shared shape rather than a staff-only one because the
    # operator's detail screen *is* the customer's shape (see
    # `operations.get_order`), and the alternative was a second rendering of
    # an order to keep in step with this one.
    attempts: list[DeliveryAttemptOut] = []


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


# --------------------------------------------------------------------------- warehouse


class StockLineOut(BaseModel):
    """One count on one offer, named so a person can read it.

    The SKU is here because a warehouse reads a barcode, not a title: a
    scanner hands the screen a code, and the code has to be able to find the
    line. There is no per-variant barcode in this model, so a scan identifies
    the product and the size is still tapped.
    """

    offer_id: int
    variant_id: int | None
    sku: str
    variant_label: str
    product_title: str


class MovementOut(StockLineOut):
    id: int
    kind: StockMovementKind
    quantity: int
    reason: str
    actor: str
    supply_id: int | None
    order_id: int | None
    return_request_id: int | None
    removal_id: int | None
    created_at: datetime


class ShelfOut(BaseModel):
    """What the ledger says, what is promised, and what is left to sell."""

    offer_id: int
    variant_id: int | None
    variant_label: str
    on_hand: int
    reserved: int
    sellable: int


class SupplyLineIn(BaseModel):
    offer_id: int
    variant_id: int | None = None
    quantity: int = Field(gt=0)


class SupplyCreateIn(BaseModel):
    """A batch a seller says is coming.

    No label from the seller: their own reference belongs to their system, may
    repeat, and two sellers may use the same one on the same day. The code
    comes back from us and goes on the pallet.
    """

    lines: list[SupplyLineIn] = Field(min_length=1, max_length=500)
    note: str = ""
    seller_id: int | None = None    # admin only


class SupplyReceiveLineIn(BaseModel):
    line_id: int
    received_quantity: int = Field(ge=0)


class SupplyReceiveIn(BaseModel):
    lines: list[SupplyReceiveLineIn] = Field(min_length=1, max_length=500)
    note: str = ""


class SupplyCancelIn(BaseModel):
    """Why a batch is not being received.

    Required, and the same shape whoever sends it: a seller calling off a
    pallet writes what changed, the warehouse refusing one writes what was
    wrong with it. When the batch was a product's first, this sentence is the
    entire answer the seller gets about why their product is not in the shop.
    """

    reason: str = Field(min_length=1, max_length=500)


class SupplyLineOut(StockLineOut):
    id: int
    declared_quantity: int
    received_quantity: int | None
    difference: int | None


class SupplyOut(BaseModel):
    id: int
    code: str
    seller: SellerOut
    status: SupplyStatus
    note: str
    lines: list[SupplyLineOut]
    declared_at: datetime
    received_at: datetime | None


class RemovalLineIn(BaseModel):
    offer_id: int
    variant_id: int | None = None
    quantity: int = Field(gt=0)


class RemovalCreateIn(BaseModel):
    reason: RemovalReason
    lines: list[RemovalLineIn] = Field(min_length=1, max_length=500)
    note: str = ""
    seller_id: int | None = None    # admin only


class RemovalPrepareLineIn(BaseModel):
    line_id: int
    prepared_quantity: int = Field(ge=0)


class RemovalPrepareIn(BaseModel):
    lines: list[RemovalPrepareLineIn] = Field(min_length=1, max_length=500)
    note: str = ""


class RemovalLineOut(StockLineOut):
    id: int
    quantity: int
    prepared_quantity: int | None


class RemovalOut(BaseModel):
    id: int
    code: str
    seller: SellerOut
    status: RemovalStatus
    reason: RemovalReason
    note: str
    lines: list[RemovalLineOut]
    requested_at: datetime
    ready_at: datetime | None
    collected_at: datetime | None


class WriteOffIn(BaseModel):
    """Goods that are gone: damaged, lost, spoiled.

    A reason is required for the same reason it is on a stocktake correction —
    stock that left without one is indistinguishable from stock that was
    stolen.
    """

    variant_id: int | None = None
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------- admin


class AdminSellerOut(BaseModel):
    id: int
    name: str
    phone: str
    commission_percent: int
    active: bool
    # The account that signs in as this seller, if one is linked yet.
    user_phone: str | None
    user_name: str | None
    offer_count: int
    created_at: datetime


class SellerCreateIn(BaseModel):
    """A seller, and optionally the account that signs in as them.

    Linking an account is what *makes* somebody a seller — it is not a
    separate administrative step — so giving a phone here grants that user the
    seller role, and the change is written to the audit log.
    """

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field("", max_length=20)
    commission_percent: int = Field(5, ge=0, le=100)
    user_phone: str | None = Field(None, pattern=UZ_PHONE)


class SellerUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)
    commission_percent: int | None = Field(None, ge=0, le=100)
    active: bool | None = None
    user_phone: str | None = Field(None, pattern=UZ_PHONE)


class AdminProductOut(BaseModel):
    """A card as the person who owns the catalogue sees it."""

    id: int
    sku: str
    title: str
    subtitle: str
    status: ProductStatus
    next_statuses: list[ProductStatus]
    category_slug: str
    brand_slug: str | None
    price: int
    old_price: int | None
    stock_left: int
    offer_count: int
    proposed_by: SellerOut | None
    moderation_note: str
    image_count: int
    variant_count: int
    created_at: datetime


# --------------------------------------------------------------------------- the editor

# What a card is made of, as the person who owns the catalogue sees it.
#
# The customer shapes above are no use here twice over. They answer in the
# language that was asked for, and an editor needs the Uzbek that is actually
# on the row — otherwise saving a Russian screen writes the Russian back as
# the Uzbek. And they carry only what a shopper needs; an editor also needs
# the ids it will delete and reorder by, and needs to know which of those it
# is allowed to do before it tries.


class AdminCategoryOut(BaseModel):
    """A category as it is stored, not as it is read.

    ``name`` and ``subtitle`` are the row's own Uzbek. What makes this shape
    necessary rather than convenient: ``/categories`` passes both through
    ``i18n.t``, so an admin working with the panel in Russian would be shown
    the translation in the field that writes the source.
    """

    id: int
    slug: str
    name: str
    subtitle: str
    icon: str
    image_url: str | None
    parent_slug: str | None
    sort: int
    is_quick_link: bool
    # Why a delete would be refused, without having to try it.
    product_count: int
    child_count: int


class AdminBrandOut(BaseModel):
    """A brand as it is stored, with the figure the customer list never fills.

    ``/brands`` sends ``product_count: 0`` for every row — the count is only
    computed in ``/products/filters``, and scoped to one listing. Here it is
    the whole catalogue, and it is the answer to "can this be deleted".
    """

    id: int
    slug: str
    name: str
    product_count: int


class CatalogSummaryOut(BaseModel):
    """How many cards sit in each state.

    One query for a number the sidebar wants on every screen. The alternative
    is fetching the moderation queue itself to count its rows, which is a page
    of cards fetched to display an integer.
    """

    counts: dict[ProductStatus, int]


class AdminImageOut(BaseModel):
    """A photograph with the id needed to remove or reorder it.

    The write endpoints answer with bare URLs, which is enough to redraw a
    gallery and not enough to edit one: ``DELETE .../images/{image_id}`` has
    always existed and nothing told the panel what ``image_id`` was.
    """

    id: int
    url: str
    sort: int


class AdminVariantOut(BaseModel):
    """A colour or a size, and whether it may be deleted.

    ``can_delete`` is the backend's own answer, from the same function the
    delete endpoint refuses with — not a rule copied into the browser that
    would drift from it. A panel that greys the button out and says why is
    telling the truth; one that lets somebody click and then shows a 409 has
    made them find out the hard way.
    """

    id: int
    kind: VariantKind
    label: str
    value: str
    image_url: str | None
    parent_id: int | None
    sort: int
    stock_left: int | None
    in_stock: bool
    can_delete: bool
    # An already-translated sentence, empty when it can be deleted.
    blocked_reason: str


class AdminVariantsOut(BaseModel):
    """The tree, plus whether a size may be added to it at all.

    The second guard the editor has to show in advance: a colour with stock
    against it cannot take its first size, because the shelf is counted on the
    colour and the size would move where the counting happens.
    """

    variants: list[AdminVariantOut]
    can_add_size: bool
    size_blocked_reason: str


class AdminSpecOut(BaseModel):
    """A spec row as the editor has to hold it, translations included.

    ``SpecOut`` is key and value, which is all a product page shows. An editor
    needs more, and not for convenience: ``PUT .../specs`` replaces the whole
    table, so every row it does not send is gone — translations with it. A
    form that could not read the Russian back would quietly delete it on the
    next save of an unrelated row.
    """

    id: int
    key: str
    value: str
    translations: dict[str, dict[str, str]]


class AdminProductDetailOut(AdminProductOut):
    """One card, with everything the edit form binds to.

    The list shape stays lean — a description per row is a page of prose
    fetched to render a table — so the fields only an editor needs are added
    here, on the endpoint only an editor calls.
    """

    description: str
    badge: str | None
    warranty: str | None
    is_original: bool
    free_delivery: bool
    next_day_delivery: bool
    # {"ru": {"title": …}, "en": {…}} — absent languages simply not present.
    translations: dict[str, dict[str, str]]


class ProductCreateIn(BaseModel):
    """A new card.

    ``price`` seeds the cached figure and nothing more. The price a shopper
    pays comes from an offer, and ``app.offers.refresh`` overwrites this the
    moment one exists — it is here so a card with no offers yet has a number
    to show rather than a nought. Stock is absent on purpose: it comes from
    the movement ledger and is the warehouse's to move.
    """

    sku: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = ""
    description: str = ""
    category_slug: str
    brand_slug: str | None = None
    price: int = Field(gt=0)
    old_price: int | None = Field(None, gt=0)
    badge: str | None = None
    warranty: str | None = None
    is_original: bool = True
    free_delivery: bool = True
    next_day_delivery: bool = True
    # The Russian and English for this card, written with it. See TextIn.
    translations: dict[Lang, ProductTextIn] = Field(default_factory=dict)


class ProductUpdateIn(BaseModel):
    """Everything about a card except its price, its stock and its status.

    Those three have owners: the price belongs to an offer, the stock to the
    ledger, and the status to a moderation decision with a reason attached.
    """

    title: str | None = Field(None, min_length=1, max_length=200)
    subtitle: str | None = None
    description: str | None = None
    category_slug: str | None = None
    brand_slug: str | None = None
    badge: str | None = None
    warranty: str | None = None
    is_original: bool | None = None
    free_delivery: bool | None = None
    next_day_delivery: bool | None = None
    translations: dict[Lang, ProductTextIn] = Field(default_factory=dict)


class ProductProposeIn(ProductCreateIn):
    """A seller suggesting a card for the platform's catalogue.

    The catalogue belongs to the platform: a seller attaches an offer to a card
    that already exists rather than opening their own copy, because a copy per
    seller duplicates the catalogue and leaves the warehouse holding the same
    goods in two places. What a seller *can* do is suggest one, and this is
    that — it lands in moderation, never in the shop.
    """


class CategoryWriteIn(BaseModel):
    slug: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    subtitle: str = ""
    icon: str = "box"
    image_url: str | None = None
    parent_slug: str | None = None
    sort: int = 0
    is_quick_link: bool = False
    translations: dict[Lang, CategoryTextIn] = Field(default_factory=dict)


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    subtitle: str | None = None
    icon: str | None = None
    image_url: str | None = None
    parent_slug: str | None = None
    sort: int | None = None
    is_quick_link: bool | None = None
    translations: dict[Lang, CategoryTextIn] = Field(default_factory=dict)


class BrandWriteIn(BaseModel):
    slug: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    translations: dict[Lang, BrandTextIn] = Field(default_factory=dict)


class ImageWriteIn(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    sort: int = 0


class VariantWriteIn(BaseModel):
    kind: VariantKind
    label: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=60)
    image_url: str | None = None
    # Which colour this size belongs to. Required for a size on a product that
    # has colours — a size that belongs to nothing is a cell of no grid.
    parent_id: int | None = None
    sort: int = 0
    translations: dict[Lang, VariantTextIn] = Field(default_factory=dict)


class SpecWriteIn(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)
    translations: dict[Lang, SpecTextIn] = Field(default_factory=dict)


class SpecsReplaceIn(BaseModel):
    """The whole list, in order. Specs are read as a table, not edited row by
    row, and replacing them is how the order gets fixed."""

    specs: list[SpecWriteIn] = Field(default_factory=list, max_length=60)


# --------------------------------------------------------------------------- showcase


class BannerWriteIn(BaseModel):
    kicker: str = ""
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = ""
    cta: str = "Ko'rish"
    image_url: str = Field(min_length=1, max_length=300)
    gradient_from: str = "#14162A"
    gradient_to: str = "#0E7BF5"
    target_type: Literal["category", "product", "url"] = "category"
    target_value: str = ""
    active: bool = True


class BannerUpdateIn(BaseModel):
    kicker: str | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    subtitle: str | None = None
    cta: str | None = None
    image_url: str | None = Field(None, min_length=1, max_length=300)
    gradient_from: str | None = None
    gradient_to: str | None = None
    target_type: Literal["category", "product", "url"] | None = None
    target_value: str | None = None
    active: bool | None = None


class SectionWriteIn(BaseModel):
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = ""
    category_slug: str | None = None
    layout: Literal["rail", "grid", "deals"] = "rail"
    active: bool = True


class SectionUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=120)
    subtitle: str | None = None
    category_slug: str | None = None
    layout: Literal["rail", "grid", "deals"] | None = None
    active: bool | None = None


class ReorderIn(BaseModel):
    """The whole order, in one call.

    A screen where rows are dragged into place knows the final order and
    nothing else. Sending it as one list means the order cannot be left half
    applied, and it costs one request instead of one per row.
    """

    ids: list[int] = Field(min_length=1, max_length=200)


class PromoWriteIn(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    percent_off: int = Field(0, ge=0, le=100)
    amount_off: int = Field(0, ge=0)
    min_total: int = Field(0, ge=0)
    active: bool = True

    @field_validator("code")
    @classmethod
    def _upper(cls, value: str) -> str:
        # The cart looks a code up in upper case, so a lower-case one would be
        # a code nobody could redeem.
        return value.strip().upper()


class PromoUpdateIn(BaseModel):
    percent_off: int | None = Field(None, ge=0, le=100)
    amount_off: int | None = Field(None, ge=0)
    min_total: int | None = Field(None, ge=0)
    active: bool | None = None


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


class StaffUserOut(BaseModel):
    """An account as the person handing out roles sees it.

    Separate from ``UserOut``, which is somebody's own profile and is read by
    two shipped apps. This one answers a different question — who is this, and
    what are they allowed to do — and carries nothing an admin has no business
    reading off a customer's row.
    """

    id: int
    phone: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class RoleWriteIn(BaseModel):
    """Making somebody staff, or standing them down.

    ``note`` is why. It is not required — the audit row records who and when
    regardless — but it is the field that makes the log worth reading a year
    later, so the panel offers it.
    """

    role: UserRole
    note: str = Field("", max_length=200)


class MediaOut(BaseModel):
    """Where an uploaded picture ended up.

    ``media_url`` is the same shape every other image in the API carries — a
    path relative to the media root — so it can be handed straight back as the
    ``url`` of a product image, a category, or a colour swatch, and every app
    resolves it the way it already resolves the seeded ones.

    The size is returned because it is not the size that was sent: the picture
    has been re-encoded and shrunk, and a panel that shows a preview wants to
    know what it is previewing.
    """

    media_url: str
    width: int
    height: int
    bytes: int


# ------------------------------------------------------------------ the seller's own

# The marketplace's founding move — a seller arrives and puts their goods up —
# did not work. Offering a product needs a ``product_id``, and the only
# catalogue listing was the admin's; so a seller could edit the offers
# somebody had opened for them and could not open one.
#
# These three shapes close that. What runs through all of them: a seller is an
# outside party, so each answers exactly what they need and nothing about
# anybody else's arrangement with us.


class SellerMeOut(BaseModel):
    """Which shop am I.

    ``/staff/me`` answers with the *user* — a phone number and a role — and
    says nothing about the ``sellers`` row behind it. So the cabinet greeted
    people by phone number, and a seller who had just been taken on had no way
    to confirm they were linked to the right shop, which is the one thing they
    would want to check first.

    The commission rate is here because it is a term of their own contract and
    they are entitled to read it. It is also the figure every statement is
    computed from, so a seller who cannot see it cannot check a payout.
    """

    id: int
    name: str
    phone: str
    commission_percent: int
    active: bool
    # When this account was pointed at this shop. Null for a shop linked
    # before the column existed and whose link was never recorded.
    linked_at: datetime | None
    # When we took the shop on, which is earlier and is not the same thing.
    created_at: datetime
    offer_count: int


# ------------------------------------------------ a seller's own listing, whole

# The catalogue is not the platform's alone. A seller opens their own product,
# photographs it, prices it, and says what colours and sizes they have — and
# what the warehouse then confirms is that the goods *arrived*, not that the
# listing was allowed.
#
# So these shapes describe one product as one thing. The alternative was the
# five calls it decomposes into — create the card, post each image, post each
# colour, post each size, open the offer, declare the batch — which is five
# chances to end up with half a product and no way to tell which half.


class ListingSizeIn(BaseModel):
    """One size of one colour, and how many of it are coming.

    ``quantity`` is what the seller says is in the box. It is *not* a stock
    figure and is not written to one: it becomes the declared quantity on a
    supply line, and the shelf moves when the warehouse counts it. Nothing in
    this codebase assigns to ``stock_left`` — see ``app.stock``.
    """

    label: str = Field(min_length=1, max_length=20)          # "M", "42"
    value: str = ""                                          # defaults to label
    quantity: int = Field(0, ge=0)


class ListingColorIn(BaseModel):
    """One colour, and the sizes it comes in.

    ``sizes`` may be empty for a product that has colours and nothing below
    them — then the colour is the leaf and the count sits on it. A product with
    sizes under its colours is counted on the sizes, because a shop that has
    sold its last black M has sold it in black and the page must not go on
    offering it out of the blue Ms.
    """

    label: str = Field(min_length=1, max_length=40)          # "Oq"
    value: str = Field("", max_length=40)                    # "#FFFFFF"
    # The photograph of the goods in this colour. A colour is chosen by
    # looking at the thing, not at a hex circle.
    image_url: str | None = None
    sizes: list[ListingSizeIn] = Field(default_factory=list, max_length=40)
    # How many of this colour, when the colour is the leaf.
    #
    # A bag or a watch has colours and no sizes, and the count then sits on
    # the colour — but there was nowhere to put it: every quantity lived on a
    # size, so a sizeless colour was always declared as nought and a seller of
    # bags submitted a card the warehouse was expecting no box for. Ignored
    # when the colour has sizes, because then the sizes are the leaves and
    # counting the colour as well would count the shelf twice.
    quantity: int = Field(0, ge=0, le=100_000)


class ListingVariantsIn(BaseModel):
    """Colours and sizes to add to a card that already exists.

    The same shape as creation's ``colors``, on purpose: the form a seller
    fills in to add a colour is the form they filled in to make the card, and
    a second shape for it would be a second thing to keep in step.

    Sending a colour that is already there is not an error — only the new
    parts are written, and any quantities become a batch. Which means a seller
    can send the whole grid they are looking at and let the server work out
    what is new, rather than the screen having to.
    """

    colors: list[ListingColorIn] = Field(min_length=1, max_length=20)


class ListingEditIn(BaseModel):
    """What a seller may change about their own card after it exists.

    Not ``ProductUpdateIn``. That shape is an admin's, and it carries fields a
    seller has no business setting on their own goods — ``is_original``, a
    badge, a warranty, free delivery. Those are claims the shop makes, and a
    seller who could tick "original" for themselves has made the tick
    worthless.

    What is here is the description of the thing: what it is called, what it
    is, which shelf of the catalogue it belongs on, and its photographs. Every
    field is optional and only what arrives is written, so a screen that edits
    the title alone sends the title alone.

    ``images`` replaces the whole list when given, in order, first one primary.
    Not a patch per picture: reordering, removing and adding are one act to
    the person doing it — they drag the pictures into the order they want and
    save — and three endpoints for it would need the client to work out the
    difference between two lists and then send it as a diff nobody can read in
    a log.

    Price, stock and status are absent and stay absent. The price belongs to
    the offer (``PATCH /staff/offers/{id}``), the stock to the ledger, and the
    status to the warehouse counting the goods in.
    """

    title: str | None = Field(None, min_length=2, max_length=200)
    subtitle: str | None = Field(None, max_length=200)
    description: str | None = None
    category_slug: str | None = None
    weight_grams: int | None = Field(None, ge=0)
    images: list[str] | None = Field(None, max_length=12)


class ListingCreateIn(BaseModel):
    """Everything a seller's new product is, in one request.

    ``images`` are media paths from ``POST /staff/media`` — upload first, send
    the paths here. **The first is the primary one**: it is the picture in
    every listing, every basket line and every order row, so the order of this
    list is a decision and not an accident of which file dialog opened first.
    """

    title: str = Field(min_length=2, max_length=200)
    subtitle: str = ""
    description: str = ""
    category_slug: str
    brand_slug: str | None = None

    # The seller's own price. It reaches the shop through the offer this
    # creates, and `offers.refresh` copies it onto the card — the card's own
    # `price` is a cache and never a source.
    price: int = Field(gt=0)
    old_price: int | None = Field(None, gt=0)
    # What it costs us to handle, which decides the fulfilment band. Zero means
    # undeclared and is charged as one kilogram; see ``app.settlement``.
    weight_grams: int = Field(0, ge=0)

    images: list[str] = Field(default_factory=list, max_length=12)
    colors: list[ListingColorIn] = Field(default_factory=list, max_length=20)

    @field_validator("images")
    @classmethod
    def _no_blanks(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("bir rasm ikki marta berilgan")
        return cleaned


class ListingStockOut(BaseModel):
    """One countable cell of a listing, as the seller reads it."""

    variant_id: int
    color_label: str
    size_label: str | None
    # What the seller declared on the batch that is coming, and what is on the
    # shelf now. Both, because the gap between them is the only thing either
    # party will want to talk about.
    declared: int
    on_hand: int
    sellable: int


class SellerListingOut(BaseModel):
    """A seller's own product, and where it has got to.

    ``stage`` is derived rather than stored, from the card's status and the
    batch behind it, because it is a sentence about two different rows and
    neither of them owns it:

    * ``awaiting_warehouse`` — declared, the goods have not arrived
    * ``in_warehouse`` — counted in, and on the shelf
    * ``on_sale`` — in the shop, with something to sell
    * ``sold_out`` — in the shop, and nothing left
    * ``rejected`` — refused, and ``moderation_note`` says why
    * ``archived`` — withdrawn; the orders that named it survive
    """

    id: int
    sku: str
    title: str
    subtitle: str
    status: ProductStatus
    stage: Literal[
        "awaiting_warehouse", "in_warehouse", "on_sale", "sold_out",
        "rejected", "archived",
    ]
    # The sentence a refusal owes the seller. Empty on everything else.
    moderation_note: str
    stage_label: str

    category_slug: str
    price: int
    old_price: int | None
    images: list[str]
    offer_id: int | None
    # The batch the warehouse is expecting, or counted. Null once there has
    # never been one.
    supply_code: str | None
    supply_status: SupplyStatus | None

    stock: list[ListingStockOut]
    on_hand_total: int
    sellable_total: int
    created_at: datetime


# ------------------------------------------------------------------ payouts

# What a seller is owed, and what it is made of.
#
# Every shape here is read by somebody who may be about to disagree with it,
# which is why none of them is only a total. A statement carries its headings
# and its lines; a line carries what it was computed from.


class StatementLineOut(BaseModel):
    """One row of an account, and its source.

    ``amount`` is signed the way the ledger is: positive is owed to the
    seller, negative is what we keep or claw back. The apps never see this —
    it is a backoffice shape — so the sign convention can be the one the
    arithmetic actually uses rather than one that reads nicely in a column.
    """

    id: int
    kind: StatementLineKind
    amount: int
    quantity: int
    title: str
    note: str
    occurred_at: datetime
    # Which event this came from. Exactly one is set on everything but a
    # manual adjustment.
    order_item_id: int | None
    return_request_id: int | None
    offer_id: int | None


class SellerStatementOut(BaseModel):
    """A seller's account for one period.

    The headings are positive figures read as deductions — "commission
    420 000" — while ``payable`` is the signed arithmetic. It can be negative:
    a period of refunds and storage against no sales means the seller owes us,
    and rounding that up to zero would hide a debt rather than settle it.
    """

    id: int
    period_id: int
    period_label: str
    starts_on: date
    ends_on: date
    seller_id: int
    seller_name: str
    status: SettlementStatus

    gross_sales: int
    commission: int
    fulfilment: int
    refunds: int
    storage: int
    adjustments: int
    payable: int

    line_count: int
    closed_at: datetime | None
    paid_at: datetime | None
    payment_method: str
    payment_reference: str
    note: str


class SellerStatementDetailOut(SellerStatementOut):
    """The same account with its composition, which is the point of it.

    A seller told "9 100 000" has a number to argue with. A seller shown the
    order lines, the returns and the days of storage that add up to it has an
    account to read.
    """

    lines: list[StatementLineOut]


class SettlementPeriodOut(BaseModel):
    id: int
    label: str
    starts_on: date
    ends_on: date
    status: SettlementStatus
    closed_at: datetime | None
    statement_count: int
    # Across every seller in the period, so a run can be looked at whole.
    total_payable: int


class PeriodCreateIn(BaseModel):
    """A payout run's dates.

    Chosen rather than derived: a week and a month are both reasonable and
    which one a marketplace uses is a business decision, not something to
    infer from a calendar.
    """

    starts_on: date
    ends_on: date
    label: str = Field("", max_length=80)


class StatementPayIn(BaseModel):
    """Marking money as gone.

    The reference is what makes this checkable later — a transfer number
    somebody can look up when a seller says it never arrived. Not required,
    because cash exists, but asked for.
    """

    method: str = Field(min_length=1, max_length=60, examples=["bank o'tkazmasi"])
    reference: str = Field("", max_length=80)
    note: str = Field("", max_length=200)


class AdjustmentIn(BaseModel):
    """A correction, with the reason attached.

    Signed, and the note is required. An unexplained adjustment is the one
    line of a statement nobody can defend, so the endpoint refuses a blank
    one rather than accepting a number from nowhere.
    """

    amount: int
    note: str = Field(min_length=1, max_length=200)


class FulfilmentTariffOut(BaseModel):
    """One weight band's two rates: per shipment, and per day on a shelf."""

    id: int
    max_grams: int
    fee: int
    storage_per_day: int
    label: str


class FulfilmentTariffWriteIn(BaseModel):
    """A new weight band.

    ``max_grams`` is the top of the band, and it is what makes a band a band:
    the lightest one that still covers a parcel is the one that applies, so
    two bands sharing a ceiling would make "which band is this" a question
    with two answers. The endpoint refuses the second.

    Both rates default to nothing rather than to a guess. A fee that has not
    been decided is better charged as zero than as a number somebody made up,
    because the seller is going to read it against their contract.
    """

    max_grams: int = Field(gt=0)
    fee: int = Field(0, ge=0)
    storage_per_day: int = Field(0, ge=0)
    label: str = ""


class FulfilmentTariffUpdateIn(BaseModel):
    """A change to a term of a contract; every field left out is left alone.

    Partial rather than whole-row because the audit trail records fields, not
    saves: a panel that PUT the entire band back would log four changes every
    time somebody corrected the label.
    """

    max_grams: int | None = Field(None, gt=0)
    fee: int | None = Field(None, ge=0)
    storage_per_day: int | None = Field(None, ge=0)
    label: str | None = None


# ----------------------------------------------------- the period still running


class RunningLineOut(BaseModel):
    """One row of a running total.

    ``StatementLineOut`` with the ``id`` removed, and the absence is the
    point: these rows are worked out for the request and stored nowhere, so an
    id would be a handle on something that does not exist and a panel would be
    entitled to think it could fetch it again.
    """

    kind: StatementLineKind
    amount: int
    quantity: int
    title: str
    note: str
    occurred_at: datetime
    order_item_id: int | None
    return_request_id: int | None
    offer_id: int | None


class RunningTotalOut(BaseModel):
    """How the period is going so far — deliberately not a statement.

    ``is_final`` is a constant ``false`` rather than a flag that might one day
    be true. That is the whole shape of the thing: a seller reading this is
    reading arithmetic over events that have not stopped arriving, and the
    figure will differ from the one they are paid. Closing the period is what
    turns a number into a promise, and a closed period answers on
    ``/statements`` instead.

    An adjustment is not here. Every other line is derived from something that
    happened — goods delivered, goods returned, days on a shelf — and can be
    recomputed from the events at any moment. An adjustment is a decision
    somebody wrote onto a statement with a reason attached, and until a
    statement exists there is nothing to write it on.
    """

    is_final: Literal[False] = False

    # Null when nobody has opened a run covering today: the window is then the
    # gap between the last period and now, which is a real span of days and
    # not a period. Sales still happen in it.
    period_id: int | None
    period_label: str
    period_status: SettlementStatus | None
    starts_on: date
    ends_on: date
    # When the tally was taken. Two requests a minute apart may disagree, and
    # this is what says which is the later one.
    as_of: datetime

    seller_id: int
    seller_name: str

    gross_sales: int
    commission: int
    fulfilment: int
    refunds: int
    storage: int
    payable: int

    line_count: int
    lines: list[RunningLineOut]


# ------------------------------------------------------------------ the courier

# The last mile, which the system could not describe at all.
#
# Every write shape here is submitted from a phone that may have queued it for
# an hour and may send it twice. The header ``Idempotency-Key`` is required on
# all of them; see ``app.idempotency`` for why it is not optional.


class CourierEarningsOut(BaseModel):
    """What a courier has done and what it came to.

    Theirs alone, and it is the reason a courier opens the app when they are
    not at a door: nobody works a round they cannot count. Three windows
    rather than one running total — today is what they are doing now, the
    month is what their rent is measured against, and the lifetime figure is
    the one that makes a long day feel like it added up to something.

    ``cash_on_hand`` is not earnings and is deliberately next to them: money
    taken at doors belongs to the office and a courier carrying it needs to
    see how much of it they are carrying. Confusing the two is how a courier
    ends up short at the end of a week.
    """

    delivered_today: int
    delivered_month: int
    delivered_total: int

    fee_per_delivery: int
    earned_today: int
    earned_month: int
    earned_total: int

    # Cash collected at doors and not yet handed in. Ours to reconcile, and
    # shown because the person holding it should know the figure.
    cash_on_hand: int

    # How many doors were knocked on for nothing. Not a score — a courier who
    # takes the hard addresses should not read this as a mark against them —
    # but a figure they can point at when an operator asks.
    failed_attempts: int


class CourierOrderOut(BaseModel):
    """One stop on a round.

    Not the customer's ``OrderOut``. A courier at a door needs the address,
    the phone, how much cash to ask for and how many times this door has
    already been tried — and none of the catalogue detail that shape carries.
    """

    id: int
    code: str
    sequence: int
    status: OrderStatus

    recipient_name: str
    recipient_phone: str
    address_line: str
    address_meta: str
    delivery_kind: DeliveryKind
    delivery_day: date | None
    delivery_window: str

    items_count: int
    total: int
    payment_method: PaymentMethod
    # Whether money changes hands at the door, and how much. Zero on a card
    # order, which is already paid — asking for it again is the mistake this
    # field exists to prevent.
    cash_due: int

    # How this door has gone so far, so a courier knows before they knock.
    attempts: int
    last_failure: str


class DeliverIn(BaseModel):
    """Proof that goods changed hands.

    ``recipient_name`` is required and the photograph is not. That is a
    decision about the work: the name is one field a courier can always fill
    in while standing in front of the person who took the goods, and it is
    what answers "I never received it". A photo needs an upload, an upload
    needs signal, and requiring one would stop a courier in a basement
    finishing a delivery they have already made.
    """

    recipient_name: str = Field(min_length=1, max_length=120)
    # A path from ``POST /staff/media``, uploaded when there was signal to.
    photo_url: str = Field("", max_length=300)
    # What was taken at the door. Refused unless it matches what is owed:
    # a courier who mistypes this is short at the end of the day and cannot
    # prove why.
    cash_collected: int = Field(0, ge=0)
    note: str = Field("", max_length=200)


class FailedIn(BaseModel):
    """A door that did not open.

    The reason is required. "Not delivered" with nothing after it is the row
    an operator cannot act on, and deciding what happens next — phone the
    customer, try tomorrow, give up — is a decision made from this sentence.
    """

    reason: str = Field(min_length=1, max_length=200)
    photo_url: str = Field("", max_length=300)


class PickupLineOut(BaseModel):
    id: int
    return_request_id: int
    order_code: str
    customer_name: str
    customer_phone: str
    address_line: str
    reason: str                  # why the customer is returning it
    product_title: str
    # Null until the courier has been: True and False are answers, null is
    # "nobody has tried".
    collected: bool | None
    note: str                    # why it was not collected, when it was not
    photo_url: str | None
    attempted_at: datetime | None


class PickupRunOut(BaseModel):
    id: int
    code: str
    courier_id: int
    courier_name: str
    status: PickupRunStatus
    next_statuses: list[PickupRunStatus]
    created_at: datetime
    collected_at: datetime | None
    received_at: datetime | None
    note: str
    lines: list[PickupLineOut]


class PickupCreateIn(BaseModel):
    """A round of collections, built from approved returns.

    Only approved ones: a request still being decided is not something to
    send a van for, and a refused one has nothing to collect.
    """

    courier_id: int
    return_request_ids: list[int] = Field(min_length=1, max_length=60)
    note: str = Field("", max_length=200)


class PickupLineIn(BaseModel):
    return_request_id: int
    collected: bool
    # Required when nothing was collected, for the same reason a failed
    # delivery needs one.
    reason: str = Field("", max_length=200)
    photo_url: str = Field("", max_length=300)


class PickupCollectIn(BaseModel):
    """What the courier came back with, door by door."""

    lines: list[PickupLineIn] = Field(min_length=1, max_length=60)
    note: str = Field("", max_length=200)


# ------------------------------------------------------------------ backoffice

# The customer's shapes above are shipped and read by two apps, so none of
# them changes. A backoffice asks different questions of the same rows — whose
# order is this, what may I do to it next — and gets its own shapes for them.


class StaffReturnOut(BaseModel):
    """One return request, read by an operator, the warehouse or the seller.

    The last four fields are the reason all three read the same shape. A
    return is answered twice after the money — the warehouse says what
    arrived, the seller says what to do about it — and every screen involved
    needs to see both answers to know whose turn it is. ``seller_decisions``
    carries the moves that are open the way ``next_statuses`` does: a damaged
    shirt cannot be relisted, and that rule belongs here rather than written
    again in three clients.
    """

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

    # Whose goods these are, so a seller's list can say and an operator's can
    # tell two sellers' parcels apart.
    seller_id: int | None = None
    seller_name: str = ""
    product_title: str = ""

    inspection: ReturnInspection | None = None
    inspection_label: str = ""
    inspection_note: str = ""
    inspected_at: datetime | None = None

    seller_decision: SellerReturnDecision | None = None
    seller_decision_label: str = ""
    seller_decisions: list[SellerReturnDecision] = []
    decision_due_at: datetime | None = None
    decided_at: datetime | None = None
    relisted: bool = False


class ReturnInspectIn(BaseModel):
    """The warehouse's verdict on a parcel that came back.

    ``result`` has no default. Somebody has to look at the shirt, and a
    default here would be a verdict arrived at by pressing Save.
    """

    result: ReturnInspection
    note: str = ""


class SellerDecisionIn(BaseModel):
    """The seller's answer: sell it again, or come and get it."""

    decision: SellerReturnDecision


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
    # What is in it, short enough for a row.
    #
    # The queue used to carry a count and nothing else, so a picker reading it
    # knew an order had one thing in it and not what the thing was — which is
    # the whole of their job. They had to open every order to find out what to
    # fetch, and on a bench with twenty of them that is twenty round trips.
    #
    # A sentence rather than the lines themselves: a row has space for one, and
    # the order's own screen has every line with its price.
    items_summary: str
    total: int
    paid: bool
    # What this order may become next. The backoffice draws its buttons from
    # this rather than from its own copy of the rules, so the two cannot drift.
    next_statuses: list[OrderStatus]
    # Who is carrying it, if anybody yet.
    #
    # ``Order.courier_id`` has existed since the courier app was built, and
    # nothing outside the courier's own endpoints could read it — so the
    # operator's queue could not show an unassigned order as unassigned, and
    # the panel that is supposed to plan the round had no way to see the round.
    # The name as well as the id because a row is read by a person and an id
    # is not a person.
    courier_id: int | None = None
    courier_name: str = ""
    courier_sequence: int = 0
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
