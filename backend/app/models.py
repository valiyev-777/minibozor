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
    """What a person is allowed to do, and which part of the app they see.

    One account, one role. Staff sign in through the same OTP flow customers
    use — the role is the only difference, so there is no second password
    store, no second login screen, and no way for the two to drift apart.

    Four, since the shop became one company with one warehouse. ``seller``
    went with the sellers. ``operator`` went because there is nobody to be an
    operator: the owner takes the calls and cancels the orders, and a role
    that only ever names one person who is already an admin is a second name
    for admin.
    """

    CUSTOMER = "customer"      # the app
    ADMIN = "admin"            # everything
    WAREHOUSE = "warehouse"    # receiving, putaway, picking, counts
    COURIER = "courier"        # a delivery round


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


class ReturnInspection(StrEnum):
    """What the warehouse found when it opened the parcel.

    A returned shirt is not one thing: it is either a shirt that can be sold
    again or a shirt that cannot, and until somebody has looked at it the
    shelf cannot be told which. That is why this is nullable on the request —
    ``None`` is not a third outcome, it is "nobody has looked yet".
    """

    OK = "ok"              # whole, sellable again
    DAMAGED = "damaged"    # came back unsellable


class VariantKind(StrEnum):
    SIZE = "size"
    COLOR = "color"


class ProductStatus(StrEnum):
    """Whether a card is in the shop.

    Three states, not five: with nobody outside the company writing cards
    there is nothing to moderate and nobody to refuse. What is left is the one
    question a customer endpoint asks — is this thing for sale — and the
    archive that keeps old orders readable.

    A card stays in ``draft`` while any colour it has is without a
    photograph. Goods sorted at the receiving desk are on a shelf and counted
    from the moment they are booked in; being in ``draft`` says only that the
    shop cannot show them yet.
    """

    DRAFT = "draft"            # being written, or waiting on a photograph
    ACTIVE = "active"          # in the shop
    ARCHIVED = "archived"      # withdrawn; the orders that named it survive


class StockMovementKind(StrEnum):
    """Why a count moved. Every movement has one; there is no other kind.

    A shelf figure used to be a number somebody wrote. Now it is the sum of
    these, which means a disputed count is not an opinion — it is a list.
    """

    OPENING = "opening"                    # what was there when the ledger began
    INTAKE = "intake"                      # booked in off a market run
    SALE = "sale"                          # bought and paid for
    CANCEL_RETURN = "cancel_return"        # an order called off, never left
    CUSTOMER_RETURN = "customer_return"    # came back and passed inspection
    WRITE_OFF = "write_off"                # damaged, lost, unsellable
    COUNT_ADJUSTMENT = "count_adjustment"  # a stocktake found something else


class SupplyStatus(StrEnum):
    """A sack standing unopened, or goods that are now on the books.

    ``draft`` is a real sack in the receiving area that nobody has opened
    yet: nothing in it is in the catalogue and nothing in it can be sold,
    because nobody knows what it is. Sorting it *is* filling in its lines,
    and closing it is what brings the goods into existence.
    """

    DRAFT = "draft"          # a sack in QABUL, unopened
    RECEIVED = "received"    # sorted, counted, and on the books
    CANCELLED = "cancelled"  # the sack was not what it looked like


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


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True)
    title: str
    subtitle: str = ""
    description: str = ""
    category_id: int = Field(foreign_key="categories.id", index=True)
    brand_id: int | None = Field(default=None, foreign_key="brands.id", index=True)

    # The price the card is advertised at, and the one the listings sort and
    # filter on in SQL. The money itself is on the variant — a 43 may cost
    # more than a 41 — and this is the cheapest of them, recomputed by
    # ``app.products.refresh`` whenever a variant's price moves. It is a
    # display figure and nothing is ever charged from it.
    price: int                       # so'm, integer
    old_price: int | None = None
    rating: float = 0.0
    reviews_count: int = 0
    sold_count: int = 0

    # Whether this card is in the shop at all. Customer endpoints filter on it
    # and nothing else is visible to them, whatever is on the shelf.
    status: ProductStatus = Field(default=ProductStatus.DRAFT, index=True)

    badge: str | None = None         # "Bestseller", "Yangi", "Original", "Kafolat 1 yil"
    warranty: str | None = None

    # A product holds no stock of its own — every count is on a variant, which
    # is the unit of stock. This is the one derived flag the listings need,
    # because "has this anything at all" is a filter on every catalogue query
    # and the alternative is a correlated subquery per row.
    # ``app.products.refresh`` recomputes it from the variants.
    in_stock: bool = True
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

    # What one of *these* costs. The money is here and not on the card: a 43
    # can cost more than a 41 and two colours of the same shoe can be priced
    # apart, and a single figure on the product would have to lie about one of
    # them. ``Product.price`` is the cheapest of these, for the listings.
    price: int = 0

    # How many of *this* are on the shelf. Not a cache of anybody else's
    # figure any more — the variant is the unit of stock, and this is the
    # running total of its rows in ``stock_movements``. Never assigned:
    # ``app.stock.move`` carries it.
    stock_left: int = 0
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
    paid: bool = False

    recipient_name: str = ""
    recipient_phone: str = ""

    # Who is carrying it, and where it sits in their round.
    #
    # An order used to say which window it was booked into and nothing about
    # who would turn up. So "where is my order" had no answer past the status,
    # and a courier had no list of their own — the two gaps were the same gap.
    #
    # Assigned by an operator, who plans the round; the sequence is the stop
    # number, so the courier's list comes back in the order somebody meant
    # rather than in the order the ids happen to fall.
    courier_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    courier_sequence: int = 0

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

    # ------------------------------------------------- the goods, after the money
    #
    # A refund answers the customer. It says nothing about the shirt, which is
    # in a box at the warehouse and is either sellable again or is not. That
    # used to be two answers from two parties — the warehouse inspected and
    # the seller decided what to do about it. The goods are ours now, so the
    # inspection is the whole of it: whoever opened the parcel says what they
    # found, and the shelf follows from that.
    inspection: ReturnInspection | None = Field(default=None, index=True)
    inspection_note: str = ""
    inspected_at: datetime | None = None
    inspected_by_id: int | None = Field(default=None, foreign_key="users.id")

    # And whether the shelf has already been moved for this request. A refund
    # that restocked and an inspection that passed can both reach for it; one
    # shirt back is one shirt back, and this is what stops it being two.
    relisted_at: datetime | None = None

    created_at: datetime = Field(default_factory=utcnow)


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
# ``ProductVariant.stock_left`` is a running total of the rows below, kept as a
# column because every listing filters and sorts on it in SQL. The invariant
# the tests hold us to is that the column equals the sum of the ledger — so a
# count that looks wrong is not an argument, it is a list of movements with a
# name and a reason against each one.


class StockMovement(SQLModel, table=True):
    """One reason a count changed.

    Signed: what came in is positive and what went out is negative, so the
    shelf is the sum and nothing has to be read twice. Which *kind* it was is
    separate from the sign — a stocktake correction can go either way and is
    still a stocktake correction.
    """

    __tablename__ = "stock_movements"

    id: int | None = Field(default=None, primary_key=True)
    # The thing that moved. A variant and never a product: "krossovka — 50
    # dona" is a sentence this system cannot express, and every count in it
    # hangs off one of these.
    variant_id: int = Field(foreign_key="product_variants.id", index=True)

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

    created_at: datetime = Field(default_factory=utcnow, index=True)


class Supply(SQLModel, table=True):
    """A market run: sacks brought back from the wholesale market.

    Nobody delivers to us. The owner goes to Chorsu, buys what looks worth
    buying and brings it back in a van, so there is nothing to declare in
    advance and nobody to declare it — the buyer is whoever is signed in.

    A run in ``draft`` is sacks standing unopened in the receiving area. It
    becomes goods only when somebody sorts it, and closing it is what writes
    the receipt into the ledger.
    """

    __tablename__ = "supplies"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)       # "SUP-000123"
    status: SupplyStatus = Field(default=SupplyStatus.DRAFT, index=True)
    note: str = ""

    # Where it was bought — "Chorsu", "Ippodrom". Free text, because a market
    # is not an entity anybody maintains; the form autocompletes it from
    # previous runs so it stays spelt the same way.
    place: str = ""
    # What the van cost, when there was one. Optional, and per run rather than
    # per line: nobody apportions a taxi fare across six sacks of socks.
    transport_cost: int = 0

    # Who went to the market. There is no supplier to name, so this is the
    # only party to the purchase there is.
    buyer_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    declared_at: datetime = Field(default_factory=utcnow)
    received_at: datetime | None = None
    received_by_id: int | None = Field(default=None, foreign_key="users.id")


class SupplyLine(SQLModel, table=True):
    """One pile out of a sack: what it is, how many, and what it cost.

    Written while sorting, not before. There is no declaration to compare a
    receipt against — nobody said in advance what was in the sack — so a line
    is a fact from the moment it exists.
    """

    __tablename__ = "supply_lines"

    id: int | None = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="supplies.id", index=True)
    variant_id: int = Field(foreign_key="product_variants.id", index=True)

    quantity: int = 0
    # What one of them cost at the market, in so'm. Per line because a sack
    # holds several things bought at several prices, and the margin on each is
    # the only reason to record any of it.
    unit_cost: int = 0

    @property
    def line_cost(self) -> int:
        return self.unit_cost * self.quantity


# --------------------------------------------------------------------------- the courier

# The courier was a role and nothing else.
#
# ``UserRole.COURIER`` was added in the first stage and no router ever asked
# about it. An order did not record who was carrying it, and a delivery left
# no evidence beyond a status. So the last mile was the one part of the
# business the system could not describe.
#
# There was a ``CourierShift`` here too, with a cash total to open and close
# and count against. It went with the panels rebuild: a shift is a
# reconciliation container, reconciliation is not in this shop's flow, and
# what a courier took at a door is on the attempt where it happened. Bringing
# it back wants a screen before it wants a table.
#
# Two facts about the work decide the shape of everything below.
#
# **The phone has no signal.** A courier works in lifts, basements and
# stairwells. The app queues what it cannot send and sends it later, possibly
# twice, possibly much later. So every write here is keyed: a repeat of a
# request replays the first answer instead of doing the thing again. Selling
# the same shirt twice is the most expensive mistake available in this module,
# and it is the one the design is built to make impossible.
#
# **A knock at a door is an event, not a state.** An order being refused at
# the door does not put the order into a new status — it is still on its way.
# What matters is how many times somebody tried and why it failed, and that is
# a list. So attempts accumulate as rows and the order stays ``shipped``; the
# decision to give up belongs to an operator, not to the courier at the door.


class AttemptResult(StrEnum):
    """How one knock at one door went."""

    DELIVERED = "delivered"
    FAILED = "failed"


class PickupRunStatus(StrEnum):
    """Where a round of collections from customers has got to."""

    OPEN = "open"              # assigned, not yet driven
    COLLECTED = "collected"    # the courier has the goods
    RECEIVED = "received"      # the warehouse has booked them in
    CANCELLED = "cancelled"


class IdempotencyRecord(SQLModel, table=True):
    """One completed request, kept so that a repeat replays it.

    The courier's app queues writes it cannot send and retries them, so the
    same request arrives more than once as a matter of course rather than as a
    fault. Without this, a retried "delivered, 240 000 so'm in cash" is a
    second sale off the shelf and a second 240 000 on the shift.

    Keyed per user: two couriers generating the same uuid would otherwise
    collide, and one of them would be handed the other's answer.

    The request is hashed as well as keyed. The same key with a different body
    is not a retry — it is a bug in the client, and replaying the first answer
    would hide it while the second request silently never happened.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    key: str = Field(index=True, max_length=80)
    # Which door it was, so a key reused on a different endpoint is caught
    # rather than replaying an answer of the wrong shape.
    endpoint: str = Field(max_length=60)
    request_hash: str = Field(max_length=64)
    # What we answered, verbatim, as JSON. Replayed rather than recomputed:
    # recomputing could give a different answer once the world has moved on,
    # and the client is entitled to the answer it missed.
    response: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)


class DeliveryAttempt(SQLModel, table=True):
    """One knock at one door.

    The evidence, and the reason there is no ``failed`` order status: an order
    refused at the door is still on its way, and what a dispute needs is not a
    state but a list — who was tried, when, by whom, and what happened.

    ``recipient_name`` is required on a delivery and a photograph is not, and
    that is a decision about the work rather than about the data. The name is
    one field the courier can always fill in, standing in front of the person
    who took the goods, and it is the answer to "I never received it". A photo
    needs an upload, an upload needs signal, and requiring one would mean a
    courier in a basement cannot finish a delivery they have already made —
    which is the exact situation the offline design exists for.
    """

    __tablename__ = "delivery_attempts"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    courier_id: int = Field(foreign_key="users.id", index=True)
    result: AttemptResult = Field(index=True)
    # Why it failed. Required on a failure: "not delivered" with no reason is
    # the row nobody can act on, and an operator deciding what to do next has
    # only this to go on.
    reason: str = ""

    recipient_name: str = ""
    photo_url: str = ""
    # Cash taken at the door, in so'm. Only ever positive and only on a
    # delivery; a failed attempt collects nothing.
    cash_collected: int = 0

    happened_at: datetime = Field(default_factory=utcnow, index=True)


class PickupRun(SQLModel, table=True):
    """Approved returns to collect from customers and bring to the warehouse.

    Brings goods *in* from customers whose returns the office has approved.

    **Receiving a run does not put anything on a shelf.** Whether returned
    goods are sellable is decided when the refund is made — the operator
    inspects and says restock or write off — and doing it here as well would
    put the same shirt back twice. This answers where the goods are; the
    refund answers whether they count.
    """

    __tablename__ = "pickup_runs"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)       # "PCK-000004"
    courier_id: int = Field(foreign_key="users.id", index=True)
    status: PickupRunStatus = Field(default=PickupRunStatus.OPEN, index=True)

    created_at: datetime = Field(default_factory=utcnow)
    collected_at: datetime | None = None
    received_at: datetime | None = None
    received_by_id: int | None = Field(default=None, foreign_key="users.id")
    note: str = ""


class PickupLine(SQLModel, table=True):
    """One return request on a collection run."""

    __tablename__ = "pickup_lines"
    __table_args__ = (
        UniqueConstraint("run_id", "return_request_id", name="uq_pickup_line"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="pickup_runs.id", index=True)
    return_request_id: int = Field(
        foreign_key="return_requests.id", index=True
    )

    # Null until the courier has been. True and False are both answers; null
    # is "nobody has tried yet", which is a third thing.
    collected: bool | None = None
    reason: str = ""              # why not, when not
    photo_url: str = ""
    attempted_at: datetime | None = None
