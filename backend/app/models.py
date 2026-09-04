"""Database tables.

The shape of this schema is driven directly by the 47 screens of the
"Shunaqa Tez" design: every list, badge, chip and timeline row in the design has
a home here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC — see ``app.core.security.now``."""
    return datetime.now(UTC).replace(tzinfo=None)


# --------------------------------------------------------------------------- enums


class Language(StrEnum):
    UZ = "uz"
    RU = "ru"
    EN = "en"


class UserRole(StrEnum):
    """What a person is allowed to do, and which backoffice they see.

    One account, one role. Staff sign in through the same OTP flow customers
    use — the role is the only difference, so there is no second password
    store, no second login screen, and no way for the two to drift apart.
    """

    CUSTOMER = "customer"      # the app
    ADMIN = "admin"            # everything
    OPERATOR = "operator"      # orders, calls, cancellations
    WAREHOUSE = "warehouse"    # picking, stock counts
    COURIER = "courier"        # a delivery round
    SELLER = "seller"          # one seller's own products and payouts


# Everyone who works here. Handy as the default guard on a backoffice
# endpoint, where "not a customer" is the real question.
STAFF_ROLES: frozenset[UserRole] = frozenset(
    r for r in UserRole if r is not UserRole.CUSTOMER
)


class OrderStatus(StrEnum):
    PLACED = "placed"          # Buyurtma qabul qilindi
    PACKING = "packing"        # Yig'ilmoqda
    SHIPPED = "shipped"        # Kuryerga topshirildi / Yo'lda
    DELIVERED = "delivered"    # Yetkazildi
    CANCELLED = "cancelled"    # Bekor qilindi
    RETURNED = "returned"      # Qaytarilgan


class PaymentMethod(StrEnum):
    CARD = "card"
    CASH = "cash"


class DeliveryKind(StrEnum):
    COURIER = "courier"
    PICKUP = "pickup"


class ReviewStatus(StrEnum):
    MODERATING = "moderating"  # Tekshirilmoqda
    PUBLISHED = "published"    # E'lon qilindi
    REJECTED = "rejected"


class CardStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class NotificationKind(StrEnum):
    ORDER = "order"
    PROMO = "promo"
    PRICE_DROP = "price_drop"
    REVIEW = "review"
    PAYMENT = "payment"
    SYSTEM = "system"


class ReturnStatus(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"


class VariantKind(StrEnum):
    SIZE = "size"
    COLOR = "color"


# --------------------------------------------------------------------------- identity


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    phone: str = Field(index=True, unique=True, max_length=20)
    full_name: str = ""
    email: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    avatar_url: str | None = None

    role: UserRole = Field(default=UserRole.CUSTOMER, index=True)

    pin_hash: str | None = None
    biometrics_enabled: bool = False

    language: Language = Field(default=Language.UZ)
    location_enabled: bool = True
    night_mode: bool = False

    notify_order_status: bool = True
    notify_promotions: bool = True
    notify_price_drop: bool = True
    notify_push: bool = True
    notify_sms: bool = True

    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class OtpCode(SQLModel, table=True):
    __tablename__ = "otp_codes"

    id: int | None = Field(default=None, primary_key=True)
    phone: str = Field(index=True, max_length=20)
    code_hash: str
    expires_at: datetime
    attempts: int = 0
    consumed: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token_hash: str
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- catalog


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    subtitle: str = ""
    icon: str = "box"          # glyph name from design/icons.json
    image_url: str | None = None
    parent_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    sort: int = 0
    is_quick_link: bool = False   # shown in the 10-tile grid on the home screen
    product_count: int = 0


class Brand(SQLModel, table=True):
    __tablename__ = "brands"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str


class Seller(SQLModel, table=True):
    """Somebody who sells here.

    The goods sit in our warehouse and we deliver them, so a seller is a
    price, a stock figure and a bank account rather than a shop with its own
    logistics. What they are not is a column on ``Product``: that field held
    the string "Mini Bozor" on every row, which is a shop, not a marketplace.
    """

    __tablename__ = "sellers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: str = Field(default="", max_length=20)
    # The account that signs in as this seller. Staff come through the same OTP
    # flow as everybody else and the role is the only difference, so a seller
    # holding UserRole.SELLER still needs this to answer "which of these offers
    # are mine". The house seller has nobody: it is us.
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    # What we keep of each item sold. Per seller, because the rate is what a
    # contract says and contracts differ; five per cent is the standard one.
    commission_percent: int = 5
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True)
    title: str
    subtitle: str = ""
    description: str = ""
    category_id: int = Field(foreign_key="categories.id", index=True)
    brand_id: int | None = Field(default=None, foreign_key="brands.id", index=True)

    # Price and stock are a CACHE of the winning offer — the cheapest active
    # offer with something left. They are not the source of truth any more;
    # ``offers`` is. They stay columns because every listing filters and sorts
    # on them in SQL (``catalog.py``), and the alternative is a correlated
    # subquery per row with paging computed over it. ``app.offers.refresh``
    # recomputes them, and everything that changes an offer calls it.
    price: int                       # so'm, integer
    old_price: int | None = None
    rating: float = 0.0
    reviews_count: int = 0
    # Across every seller: how many of this thing have gone, whoever sold it.
    sold_count: int = 0

    badge: str | None = None         # "Bestseller", "Yangi", "Original", "Kafolat 1 yil"
    # The winning seller's name, cached alongside the price it won with.
    seller: str = "Mini Bozor"
    warranty: str | None = None

    in_stock: bool = True
    stock_left: int = 25             # cache: what the winning offer has left
    is_original: bool = True
    free_delivery: bool = True
    next_day_delivery: bool = True

    created_at: datetime = Field(default_factory=utcnow)

    @property
    def discount_percent(self) -> int | None:
        if not self.old_price or self.old_price <= self.price:
            return None
        return round((self.old_price - self.price) / self.old_price * 100)


class ProductImage(SQLModel, table=True):
    __tablename__ = "product_images"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    url: str
    sort: int = 0


class ProductVariant(SQLModel, table=True):
    __tablename__ = "product_variants"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    kind: VariantKind = Field(default=VariantKind.SIZE)
    label: str                      # "42", "Qora"
    value: str                      # "42", "#0E0F12"
    # A colour is chosen by looking at the thing, not at a hex circle: the
    # photograph of the product in that colour, when there is one. Sizes leave
    # it empty, and a colour without a photo falls back to its hex.
    image_url: str | None = None
    in_stock: bool = True
    # How many of *this* colour are on the shelf, when the colours are counted
    # apart. The product's own stock_left is the whole shelf; this is the share
    # of it wearing one colour, so picking a colour on the page answers "how
    # many" about the thing actually being looked at rather than about the
    # sum of every colour. None on a size, and on a colour nobody counted.
    #
    # A cache too, of the winning offer's ``offer_variants`` row: the variant
    # describes the thing, and how many of it there are is a fact about whose
    # shelf it is standing on.
    stock_left: int | None = None
    # Which colour this size belongs to.
    #
    # The shelf used to be counted twice over: the colours split the product's
    # total between them, the sizes split the same total again, and the answer
    # for a pair of them was whichever of the two was scarcer. It kept the
    # arithmetic tidy and it was not true — a shop that has sold its last black
    # 41 has sold it in black, and the page went on offering it because there
    # were still three 41s somewhere in blue.
    #
    # So a size is a cell of the grid: one row per colour per size, pointing at
    # the colour it is a size of, holding its own count. Null on a product
    # with no colours, where the sizes are the product's own.
    parent_id: int | None = Field(
        default=None, foreign_key="product_variants.id", index=True
    )
    sort: int = 0


class Offer(SQLModel, table=True):
    """One seller's price for one product — where the money now lives.

    Several sellers may offer the same thing. The cheapest active offer with
    something left on the shelf wins, and the winner's figures are copied onto
    the ``Product`` row so the listings can still sort and filter in SQL. An
    offer with nothing left does not compete: it is not a price anyone can pay.
    """

    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("seller_id", "product_id", name="uq_offer"),)

    id: int | None = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="sellers.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)

    price: int
    old_price: int | None = None
    stock_left: int = 0
    # A seller withdrawing an offer without deleting it — the price and the
    # history stay, the offer stops competing.
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class OfferVariant(SQLModel, table=True):
    """How many of one colour, or one size of one colour, this seller has.

    The same shape as the stock figure on ``ProductVariant``, one level down:
    the variant says what the thing is and this says whose shelf it is on and
    how much of it is there. Absent for a variant nobody counts apart, which
    is what ``None`` means on the variant itself.
    """

    __tablename__ = "offer_variants"
    __table_args__ = (
        UniqueConstraint("offer_id", "variant_id", name="uq_offer_variant"),
    )

    id: int | None = Field(default=None, primary_key=True)
    offer_id: int = Field(foreign_key="offers.id", index=True)
    variant_id: int = Field(foreign_key="product_variants.id", index=True)
    stock_left: int = 0


class ProductSpec(SQLModel, table=True):
    __tablename__ = "product_specs"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    key: str
    value: str
    sort: int = 0


class Banner(SQLModel, table=True):
    __tablename__ = "banners"

    id: int | None = Field(default=None, primary_key=True)
    kicker: str = ""                # "MINI BOZOR / UY VA YORUG'LIK"
    title: str
    subtitle: str = ""
    cta: str = "Ko'rish"
    image_url: str
    gradient_from: str = "#14162A"
    gradient_to: str = "#0E7BF5"
    target_type: str = "category"   # category | product | url
    target_value: str = ""
    sort: int = 0
    active: bool = True


class HomeSection(SQLModel, table=True):
    """A titled horizontal rail on the home screen ("Poyabzal", "Elektronika")."""

    __tablename__ = "home_sections"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    title: str
    subtitle: str = ""
    category_slug: str | None = None
    layout: str = "rail"            # rail | grid | deals
    sort: int = 0


# --------------------------------------------------------------------------- shopping


class Favorite(SQLModel, table=True):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_favorite"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    price_when_added: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_items"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    # Two variants, not one: a shirt is a size *and* a colour, and the
    # picker sheet lets the customer choose both before adding.
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")
    color_variant_id: int | None = Field(default=None, foreign_key="product_variants.id")
    # Whose offer is in the basket. Chosen when the line is added — the
    # cheapest one with stock at that moment — and held, so a shopper is
    # charged the price they were shown rather than whatever is winning by the
    # time they reach the till. Null on a line added before offers existed.
    offer_id: int | None = Field(default=None, foreign_key="offers.id", index=True)
    quantity: int = 1
    selected: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class PromoCode(SQLModel, table=True):
    __tablename__ = "promo_codes"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    percent_off: int = 0
    amount_off: int = 0
    min_total: int = 0
    active: bool = True


# --------------------------------------------------------------------------- delivery


class Address(SQLModel, table=True):
    __tablename__ = "addresses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str                      # "Uy", "Ish"
    icon: str = "pin"
    badge: str | None = None        # "ASOSIY", "OFIS"
    line: str                       # "Toshkent, Amir Temur shoh ko'chasi 108"
    city: str = "Toshkent"
    floor: str | None = None
    apartment: str | None = None
    entrance_code: str | None = None
    comment: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def meta(self) -> str:
        bits = []
        if self.floor:
            bits.append(f"{self.floor}-qavat")
        if self.apartment:
            bits.append(f"{self.apartment}-xona")
        if self.entrance_code:
            bits.append(f"kirish kodi {self.entrance_code}")
        return " · ".join(bits)


class PickupPoint(SQLModel, table=True):
    __tablename__ = "pickup_points"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    address: str = ""
    hours: str = "Har kuni 09:00–21:00"
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None
    active: bool = True


class DeliverySlot(SQLModel, table=True):
    __tablename__ = "delivery_slots"

    id: int | None = Field(default=None, primary_key=True)
    day: date = Field(index=True)
    start_time: str                 # "09:00"
    end_time: str                   # "13:00"
    note: str = ""                  # "Ertalabki yetkazish"
    price: int = 0                  # 0 == "Bepul"
    express: bool = False
    capacity_left: int = 20


# --------------------------------------------------------------------------- payment


class PaymentCard(SQLModel, table=True):
    __tablename__ = "payment_cards"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    brand: str = "Humo"             # Humo | UzCard | Visa | Mastercard
    last4: str = Field(max_length=4)
    holder: str = ""
    expiry_month: int = 12
    expiry_year: int = 2030
    status: CardStatus = Field(default=CardStatus.ACTIVE)
    is_default: bool = False
    # Never store a PAN. A real integration keeps only the processor's token.
    processor_token: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- orders


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)        # "#A-104729"
    user_id: int = Field(foreign_key="users.id", index=True)
    status: OrderStatus = Field(default=OrderStatus.PLACED, index=True)

    delivery_kind: DeliveryKind = Field(default=DeliveryKind.COURIER)
    address_line: str = ""
    address_meta: str = ""
    pickup_point_id: int | None = Field(default=None, foreign_key="pickup_points.id")

    # Which window was booked, as well as its hours. The hours are a snapshot
    # and stay readable after the window is gone; the id is what makes the
    # seat returnable, and without it a cancelled order held its slot for ever.
    slot_id: int | None = Field(default=None, foreign_key="delivery_slots.id")
    delivery_day: date | None = None
    delivery_start: str | None = None
    delivery_end: str | None = None

    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD)
    payment_card_id: int | None = Field(default=None, foreign_key="payment_cards.id")
    paid: bool = False

    recipient_name: str = ""
    recipient_phone: str = ""

    subtotal: int = 0
    delivery_fee: int = 0
    discount: int = 0
    total: int = 0

    cancel_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrderItem(SQLModel, table=True):
    """A snapshot: an order must not change when the catalogue does."""

    __tablename__ = "order_items"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: int | None = Field(default=None, foreign_key="products.id")
    title: str
    image_url: str = ""
    # Which colour and which size, beside the words for them. The label is for
    # reading ("Ko'k · 42"); the ids are what a count can be put back onto.
    # They used to live only on the cart line, which is deleted the moment the
    # order is placed — so a cancelled order knew it had taken two of
    # something blue and could not say two of what.
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")
    color_variant_id: int | None = Field(
        default=None, foreign_key="product_variants.id"
    )
    # Who sold it and on which offer. Without the seller there is no answering
    # "who is owed this money", which is the whole point of a marketplace; the
    # offer is what the counts come off and go back onto.
    seller_id: int | None = Field(default=None, foreign_key="sellers.id", index=True)
    offer_id: int | None = Field(default=None, foreign_key="offers.id", index=True)
    # What we keep of this line, as the rate stood the day it was sold.
    #
    # Read off ``Seller.commission_percent`` at the time and then left alone.
    # A rate is a term of a contract and contracts get renegotiated; a payout
    # computed later against today's rate would quietly restate what a seller
    # was owed for something they sold last year. There is no payout module
    # yet, which is exactly why the figure has to be captured now — afterwards
    # it is not a column to add but a number nobody can recover.
    commission_percent: int = 0
    variant_label: str = ""
    unit_price: int = 0
    quantity: int = 1
    reviewed: bool = False

    @property
    def line_total(self) -> int:
        return self.unit_price * self.quantity


class OrderEvent(SQLModel, table=True):
    """One row of the delivery timeline on screen 25."""

    __tablename__ = "order_events"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    status: OrderStatus
    title: str
    happened_at: datetime | None = None
    note: str = ""
    sort: int = 0


class CancelReason(SQLModel, table=True):
    __tablename__ = "cancel_reasons"

    id: int | None = Field(default=None, primary_key=True)
    label: str
    sort: int = 0
    requires_comment: bool = False


class ReturnReason(SQLModel, table=True):
    __tablename__ = "return_reasons"

    id: int | None = Field(default=None, primary_key=True)
    label: str
    sort: int = 0
    requires_comment: bool = False


class ReturnRequest(SQLModel, table=True):
    __tablename__ = "return_requests"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    order_item_id: int | None = Field(default=None, foreign_key="order_items.id")
    reason: str = ""
    comment: str = ""
    photos: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: ReturnStatus = Field(default=ReturnStatus.SUBMITTED)
    # What the operator decided and why — the sentence the customer is owed
    # when a request is refused. Who decided it and when are in ``audit_log``;
    # this is the part the customer eventually gets to read, so it lives on
    # the request itself rather than in a log nobody outside can query.
    resolution: str = ""
    # How much was actually paid back. The figure was only ever in the audit
    # log, which the customer cannot read — so the request itself could not
    # answer the one question the customer has about it.
    refund_amount: int = 0
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- reviews


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    order_item_id: int | None = Field(default=None, foreign_key="order_items.id")

    rating: int = 5
    text: str = ""
    variant_label: str = ""
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    photos: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    likes: int = 0
    status: ReviewStatus = Field(default=ReviewStatus.MODERATING)
    created_at: datetime = Field(default_factory=utcnow)


class ReviewLike(SQLModel, table=True):
    __tablename__ = "review_likes"
    __table_args__ = (UniqueConstraint("user_id", "review_id", name="uq_review_like"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    review_id: int = Field(foreign_key="reviews.id", index=True)


class ReviewTag(SQLModel, table=True):
    """The suggested chips on the "write a review" screen."""

    __tablename__ = "review_tags"

    id: int | None = Field(default=None, primary_key=True)
    label: str
    sort: int = 0


# --------------------------------------------------------------------------- misc


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    kind: NotificationKind = Field(default=NotificationKind.SYSTEM)
    icon: str = "bell"
    title: str
    text: str = ""
    deep_link: str | None = None
    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class SearchHistory(SQLModel, table=True):
    __tablename__ = "search_history"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    query: str
    created_at: datetime = Field(default_factory=utcnow)


class PopularQuery(SQLModel, table=True):
    __tablename__ = "popular_queries"

    id: int | None = Field(default=None, primary_key=True)
    query: str
    hits: int = 0
    sort: int = 0


class FaqItem(SQLModel, table=True):
    __tablename__ = "faq_items"

    id: int | None = Field(default=None, primary_key=True)
    question: str
    answer: str = ""
    sort: int = 0


class LegalDoc(SQLModel, table=True):
    __tablename__ = "legal_docs"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    icon: str = "globe"
    title: str
    meta: str = ""
    body: str = ""
    sort: int = 0


class Translation(SQLModel, table=True):
    """Russian and English text for a row that is written in Uzbek.

    Keyed by (entity, entity_id, field) rather than held in extra columns on
    every table: adding a language then costs rows, not a migration on a dozen
    tables. A missing row falls back to the Uzbek already on the record, so a
    partly translated catalogue degrades to Uzbek rather than to blanks.
    """

    __table_args__ = (
        UniqueConstraint("entity", "entity_id", "field", "lang", name="uq_translation"),
    )

    id: int | None = Field(default=None, primary_key=True)
    entity: str = Field(index=True)          # "category", "banner", "product", …
    entity_id: int = Field(index=True)
    field: str                               # "name", "subtitle", "description", …
    lang: str = Field(index=True)            # "ru" | "en"
    value: str


# --------------------------------------------------------------------------- audit


class AuditLog(SQLModel, table=True):
    """Who changed what, when, and from which value to which.

    Money and stock are the two things nobody may quietly alter: a price, a
    refund, a shelf count, an order total. Every staff action that touches
    either writes a row here before it commits, so a disputed number can be
    traced back to a person and a moment rather than argued about.

    Values are kept as text, not typed columns. One table has to hold a price
    in so'm, an order status, a boolean and a null side by side, and the point
    of the row is to be read by a human later — not summed.
    """

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)

    # Null when the actor is the system itself — a scheduled job, a payment
    # webhook — rather than a signed-in person.
    actor_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    # The role as it was at the time. Roles get reassigned; the log must still
    # say what authority the change was made under.
    actor_role: UserRole | None = None

    action: str = Field(index=True)        # "order.cancel", "product.price"
    entity: str = Field(index=True)        # "order", "product", "product_variant"
    entity_id: int | None = Field(default=None, index=True)
    field: str = ""                        # "total", "stock_left", "status"

    old_value: str | None = None
    new_value: str | None = None
    note: str = ""                         # a reason, a ticket number, a phone call

    created_at: datetime = Field(default_factory=utcnow, index=True)
