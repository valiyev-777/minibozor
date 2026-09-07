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


class ProductStatus(StrEnum):
    """Whether a card is in the shop.

    The catalogue belongs to the platform: a seller attaches an offer to a card
    that already exists rather than opening their own copy of it. That is the
    whole point of one card with several offers — a copy per seller would
    duplicate the catalogue and leave the warehouse holding the same goods in
    two places under two names.

    So a seller may *propose* a card and an admin decides. Until somebody
    decides, it is not in the shop, and the customer endpoints show nothing but
    ``published``.
    """

    DRAFT = "draft"            # being written, ours
    MODERATING = "moderating"  # proposed by a seller, waiting on us
    PUBLISHED = "published"    # in the shop
    REJECTED = "rejected"      # refused, with a reason the seller reads
    ARCHIVED = "archived"      # withdrawn; the orders that named it survive


class StockMovementKind(StrEnum):
    """Why a count moved. Every movement has one; there is no other kind.

    A shelf figure used to be a number somebody wrote. Now it is the sum of
    these, which means a disputed count is not an opinion — it is a list.
    """

    OPENING = "opening"                    # what was there when the ledger began
    INTAKE = "intake"                      # received from a seller
    SALE = "sale"                          # bought and paid for
    CANCEL_RETURN = "cancel_return"        # an order called off, never left
    CUSTOMER_RETURN = "customer_return"    # came back and passed inspection
    WRITE_OFF = "write_off"                # damaged, lost, unsellable
    COUNT_ADJUSTMENT = "count_adjustment"  # a stocktake found something else
    SELLER_RETURN = "seller_return"        # handed back to the seller


class SupplyStatus(StrEnum):
    DECLARED = "declared"    # the seller says it is coming
    RECEIVED = "received"    # the warehouse counted it in
    CANCELLED = "cancelled"


class StockCountStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RemovalReason(StrEnum):
    UNSELLABLE = "unsellable"   # damaged, expired
    UNSOLD = "unsold"           # fine, just not selling


class RemovalStatus(StrEnum):
    REQUESTED = "requested"
    READY = "ready"             # picked and set aside — and held off the shelf
    COLLECTED = "collected"
    CANCELLED = "cancelled"


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
    # When that account was pointed at this seller.
    #
    # Not the same as ``created_at``: a seller is taken on first and an account
    # is attached afterwards, sometimes weeks later. The seller's own cabinet
    # answers "since when am I selling here" from this, and it is the date
    # their first statement can be read against. Null on a seller nobody signs
    # in as — the house seller is us.
    linked_at: datetime | None = None
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

    # How heavy one of these is, which decides what handling it costs — see
    # ``FulfilmentTariff``. Zero means nobody has said; ``app.settlement``
    # charges an undeclared weight at a stated default band rather than at
    # nothing, because free is the wrong answer and would make declaring it
    # a thing sellers avoid.
    weight_grams: int = 0

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

    # Whether this card is in the shop at all. Customer endpoints filter on it
    # and nothing else is visible to them, whatever offers it may carry.
    status: ProductStatus = Field(default=ProductStatus.DRAFT, index=True)
    # The seller who suggested it, where one did. Null for a card we wrote.
    proposed_by_id: int | None = Field(default=None, foreign_key="sellers.id", index=True)
    # Why it was refused — the sentence the seller is owed. Who refused it and
    # when are in ``audit_log``.
    moderation_note: str = ""

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
    # A rail taken off the home screen without being deleted. The design's
    # sections are the shop's window and a seasonal one comes back next year;
    # deleting it would mean writing it again from memory.
    active: bool = True


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
    # How long this line holds the goods off other people's shelves.
    #
    # Without it an abandoned basket keeps the last one of something for ever:
    # nobody can buy it and nobody is going to. Touching the line — adding
    # another, changing the quantity — pushes the deadline out again, because
    # somebody still shopping has not abandoned anything.
    reserved_until: datetime | None = Field(default=None, index=True)
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
    # What handling one of these cost, as the tariff stood the day it sold.
    #
    # Snapshotted for exactly the reason above it is: a tariff is a term of a
    # contract and gets renegotiated, and a payout computed later against
    # today's bands would restate what a seller was owed for last year.
    #
    # Kept as so'm per unit rather than as a band id, so the line stays
    # readable after the band it came from is edited or deleted. Zero on
    # everything sold before there was a fee to charge, which is correct: we
    # did not charge one.
    fulfilment_fee: int = 0
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
    # When the money actually went back, which is not when it was asked for.
    #
    # ``created_at`` is the customer opening a request; the refund happens
    # after somebody decides. A settlement buckets a refund by the day it was
    # paid, so with only ``created_at`` a refund granted in February would
    # land in January's account — and January may already be closed.
    refunded_at: datetime | None = None
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


# --------------------------------------------------------------------------- warehouse

# The shelf figure stops being a number anybody writes.
#
# ``Offer.stock_left`` and ``OfferVariant.stock_left`` are now a running total
# of the rows below, kept as columns for the same reason the price is (the
# listings filter and sort on them in SQL). The invariant the tests hold us to
# is that the column equals the sum of the ledger — so a count that looks
# wrong is not an argument, it is a list of movements with a name and a reason
# against each one.


class StockMovement(SQLModel, table=True):
    """One reason a count changed.

    Signed: what came in is positive and what went out is negative, so the
    shelf is the sum and nothing has to be read twice. Which *kind* it was is
    separate from the sign — a stocktake correction can go either way and is
    still a stocktake correction.
    """

    __tablename__ = "stock_movements"

    id: int | None = Field(default=None, primary_key=True)
    offer_id: int = Field(foreign_key="offers.id", index=True)
    # The leaf the count sits on — a size, or a colour where there are no
    # sizes. Null for an offer nobody counts by variant, and for the odd sale
    # of "one of the product" where the customer named no colour.
    variant_id: int | None = Field(
        default=None, foreign_key="product_variants.id", index=True
    )

    kind: StockMovementKind = Field(index=True)
    quantity: int                     # signed
    reason: str = ""

    # Who moved it. Null for the opening balance, which nobody decided.
    actor_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    # What caused it. Exactly one of these is set on anything but an opening
    # balance or a bare write-off, and they are what turns the ledger from a
    # list of numbers into a story that can be followed both ways.
    supply_id: int | None = Field(default=None, foreign_key="supplies.id", index=True)
    order_id: int | None = Field(default=None, foreign_key="orders.id", index=True)
    return_request_id: int | None = Field(
        default=None, foreign_key="return_requests.id", index=True
    )
    count_id: int | None = Field(default=None, foreign_key="stock_counts.id", index=True)
    removal_id: int | None = Field(
        default=None, foreign_key="removal_orders.id", index=True
    )

    created_at: datetime = Field(default_factory=utcnow, index=True)


class Supply(SQLModel, table=True):
    """A batch a seller brings in, declared before it arrives.

    The code is ours. A seller's own label is a label on somebody else's
    system: it may repeat, it may be missing, and two sellers may use the same
    one on the same day. The pallet gets a code from here and the warehouse
    looks for that.
    """

    __tablename__ = "supplies"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)       # "SUP-000123"
    seller_id: int = Field(foreign_key="sellers.id", index=True)
    status: SupplyStatus = Field(default=SupplyStatus.DECLARED, index=True)
    note: str = ""

    declared_at: datetime = Field(default_factory=utcnow)
    received_at: datetime | None = None
    received_by_id: int | None = Field(default=None, foreign_key="users.id")


class SupplyLine(SQLModel, table=True):
    """What the seller says is in the batch, and what the warehouse found.

    Both, kept side by side. A declaration is a promise and a receipt is a
    fact, and the gap between them is the only thing either party will want to
    talk about afterwards.
    """

    __tablename__ = "supply_lines"

    id: int | None = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="supplies.id", index=True)
    offer_id: int = Field(foreign_key="offers.id", index=True)
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")

    declared_quantity: int = 0
    received_quantity: int | None = None    # None until somebody counts it

    @property
    def difference(self) -> int | None:
        if self.received_quantity is None:
            return None
        return self.received_quantity - self.declared_quantity


class StockCount(SQLModel, table=True):
    """A stocktake of one offer: what we think is there, then what is.

    Opened against an offer rather than a place, because a place is not
    modelled yet and the offer is what a figure belongs to. The expected
    numbers are snapshotted when it opens, so a sale during the count does not
    silently become a discrepancy.
    """

    __tablename__ = "stock_counts"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)       # "CNT-000042"
    offer_id: int = Field(foreign_key="offers.id", index=True)
    status: StockCountStatus = Field(default=StockCountStatus.OPEN, index=True)
    note: str = ""

    opened_by_id: int | None = Field(default=None, foreign_key="users.id")
    opened_at: datetime = Field(default_factory=utcnow)
    closed_by_id: int | None = Field(default=None, foreign_key="users.id")
    closed_at: datetime | None = None


class StockCountLine(SQLModel, table=True):
    __tablename__ = "stock_count_lines"

    id: int | None = Field(default=None, primary_key=True)
    count_id: int = Field(foreign_key="stock_counts.id", index=True)
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")

    expected: int = 0                  # as at the moment the count opened
    counted: int | None = None         # what was on the shelf

    @property
    def difference(self) -> int | None:
        if self.counted is None:
            return None
        return self.counted - self.expected


class RemovalOrder(SQLModel, table=True):
    """A seller asking for their goods back — damaged or simply unsold.

    Between ``ready`` and ``collected`` the goods are held: picked, set aside,
    and not on anybody's shelf. Selling something that is already on a pallet
    by the door is the failure this state exists to prevent.
    """

    __tablename__ = "removal_orders"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)       # "RMV-000007"
    seller_id: int = Field(foreign_key="sellers.id", index=True)
    status: RemovalStatus = Field(default=RemovalStatus.REQUESTED, index=True)
    reason: RemovalReason = Field(default=RemovalReason.UNSOLD)
    note: str = ""

    requested_at: datetime = Field(default_factory=utcnow)
    ready_at: datetime | None = None
    collected_at: datetime | None = None
    prepared_by_id: int | None = Field(default=None, foreign_key="users.id")


class RemovalLine(SQLModel, table=True):
    __tablename__ = "removal_lines"

    id: int | None = Field(default=None, primary_key=True)
    removal_id: int = Field(foreign_key="removal_orders.id", index=True)
    offer_id: int = Field(foreign_key="offers.id", index=True)
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")

    quantity: int = 0                       # what the seller asked for
    prepared_quantity: int | None = None    # what the warehouse actually found


# --------------------------------------------------------------------------- paying sellers

# Nobody was being paid.
#
# The marketplace worked end to end — a seller was taken on, priced an offer,
# the warehouse booked goods in, a customer bought them, and the commission
# rate was snapshotted onto the order line. And then nothing. There was no
# period, no statement, no payout, and no way to answer "what am I owed".
#
# Two decisions run through everything below.
#
# **A statement is a ledger, not a figure.** Its payable is the sum of its
# lines and every line names what it came from — an order line, a return, an
# offer sitting in the warehouse. A seller told "9 100 000" and nothing else
# has been given a number to argue with rather than an account to read. This
# is the same reason the shelf stopped being a number somebody wrote.
#
# **A closed statement never changes.** A seller who reads a figure and is
# shown a different one next week has been told that the first figure meant
# nothing. So closing freezes the lines, and anything that arrives afterwards
# — a refund on a months-old order especially — lands in the next period
# instead of rewriting the one already seen.


class SettlementStatus(StrEnum):
    """Where a period, or one seller's account within it, has got to."""

    OPEN = "open"        # still gathering; may be rebuilt from the sources
    CLOSED = "closed"    # frozen, and the seller may be shown it
    PAID = "paid"        # the money has left, with a date and a method


class StatementLineKind(StrEnum):
    """What one row of a statement is.

    Signed amounts, so the statement is the sum of its lines the way the shelf
    is the sum of its movements: what is owed to the seller is positive and
    what we keep or claw back is negative. Which *kind* it is stays separate
    from the sign, because a refund's commission comes back and is still part
    of the refund.
    """

    SALE = "sale"                            # goods delivered — owed
    COMMISSION = "commission"                # our cut of that sale
    FULFILMENT = "fulfilment"                # picking, packing, the van
    REFUND = "refund"                        # a sale undone
    REFUND_COMMISSION = "refund_commission"  # our cut of it, given back
    STORAGE = "storage"                      # warehouse space, per unit-day
    ADJUSTMENT = "adjustment"                # a correction somebody explained


class FulfilmentTariff(SQLModel, table=True):
    """What one unit costs us physically, by how heavy it is.

    Two rates, because a weight band decides two different things: what it
    costs to pick and carry one of these once, and what it costs to keep one
    on a shelf for a day. Both follow the same physical fact — how big the
    thing is — so they live on the same band rather than in two tables that
    would have to be kept in step.

    **This is the whole reason a second fee exists.** Commission is a
    percentage, and a percentage of a cheap thing does not pay for a van. The
    catalogue's cheapest card is 39 000 so'm: five per cent of it is 1 950,
    against a Tashkent delivery that costs multiples of that. Thirty per cent
    of the published catalogue loses money on every order under a flat
    commission — and the more of it sells, the more is lost. Meanwhile five
    per cent of a 182 000 000 so'm watch is 9 100 000 for carrying one small
    box the same distance.

    So the two are separated: commission scales with what the goods are worth,
    and this scales with what they cost us to move. Weight bands rather than
    measured volume because weight is one column and a seller can state it;
    dimensions and volumetric weight are a bigger question and are deferred
    deliberately rather than half-built.
    """

    __tablename__ = "fulfilment_tariffs"

    id: int | None = Field(default=None, primary_key=True)
    # The top of the band, inclusive. The heaviest band is given a very large
    # number rather than a null, so "which band is this" is one comparison
    # with no special case.
    max_grams: int = Field(index=True)
    # Per shipment: picking, packing and the van.
    fee: int = 0
    # Per unit per day on a shelf. Flat storage would charge a washing machine
    # and a pair of earphones the same rent, which is the same mistake a flat
    # commission makes about price — see the note above.
    storage_per_day: int = 0
    label: str = ""


class SettlementPeriod(SQLModel, table=True):
    """The calendar decision: which days one payout run covers.

    Global rather than per seller. "Close January" has to mean the same dates
    for everybody, or two sellers' accounts cannot be compared and a gap
    between one seller's periods becomes days nobody is paid for.
    """

    __tablename__ = "settlement_periods"
    __table_args__ = (
        UniqueConstraint("starts_on", "ends_on", name="uq_settlement_period"),
    )

    id: int | None = Field(default=None, primary_key=True)
    label: str = ""                      # "2026-yil yanvar", "9-hafta"
    starts_on: date = Field(index=True)
    ends_on: date = Field(index=True)
    status: SettlementStatus = Field(default=SettlementStatus.OPEN, index=True)
    closed_at: datetime | None = None
    closed_by_id: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utcnow)


class SellerStatement(SQLModel, table=True):
    """One seller's account for one period.

    The totals are columns as well as the sum of the lines, for the same
    reason ``Offer.stock_left`` is a column: a list of statements is sorted
    and filtered on them in SQL, and the alternative is summing every line of
    every statement to draw one table. The invariant the tests hold us to is
    that ``payable`` equals the sum of the lines — a figure that disagrees
    with its own composition is the thing this whole model exists to prevent.
    """

    __tablename__ = "seller_statements"
    __table_args__ = (
        UniqueConstraint("period_id", "seller_id", name="uq_seller_statement"),
    )

    id: int | None = Field(default=None, primary_key=True)
    period_id: int = Field(foreign_key="settlement_periods.id", index=True)
    seller_id: int = Field(foreign_key="sellers.id", index=True)
    status: SettlementStatus = Field(default=SettlementStatus.OPEN, index=True)

    # Each of these is a positive figure read as a heading, not a signed
    # amount: "commission 420 000" is a deduction and reads as one. The signs
    # live on the lines, where the arithmetic is.
    gross_sales: int = 0
    commission: int = 0
    fulfilment: int = 0
    refunds: int = 0
    storage: int = 0
    adjustments: int = 0     # signed: a correction can go either way
    payable: int = 0

    closed_at: datetime | None = None
    paid_at: datetime | None = None
    payment_method: str = ""       # "bank o'tkazmasi", "naqd"
    payment_reference: str = ""    # a transfer number somebody can look up
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class StatementLine(SQLModel, table=True):
    """One row of a seller's account, and where it came from.

    ``9 100 000`` is not an answer to a seller who disputes it; this is. Every
    line carries the thing it was computed from — the order line that sold,
    the return that came back, the offer that sat in the warehouse — so the
    figure can be walked back to the event that caused it.
    """

    __tablename__ = "statement_lines"

    id: int | None = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="seller_statements.id", index=True)
    kind: StatementLineKind = Field(index=True)

    # Signed: positive is owed to the seller, negative is kept or clawed back.
    amount: int = 0
    quantity: int = 0

    # What caused it. Exactly one is set on everything but an adjustment, and
    # they are what makes the total followable in both directions.
    order_item_id: int | None = Field(
        default=None, foreign_key="order_items.id", index=True
    )
    return_request_id: int | None = Field(
        default=None, foreign_key="return_requests.id", index=True
    )
    offer_id: int | None = Field(default=None, foreign_key="offers.id", index=True)

    # Readable without joining: what sold, and the sum in words where the sum
    # is a calculation ("4 dona × 31 kun × 60 so'm").
    title: str = ""
    note: str = ""

    # When the thing happened, not when the line was written. This is what
    # buckets an event into a period, and what lets a refund that arrives
    # after its own period was closed fall into the next one instead.
    occurred_at: datetime = Field(default_factory=utcnow, index=True)
