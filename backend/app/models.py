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

    ``operator`` went because there is nobody to be an operator: the owner
    takes the calls and cancels the orders, and a role that only ever names one
    person who is already an admin is a second name for admin.

    ``seller`` went the same way, twice. The marketplace one was an outside
    merchant with their own stock and payout. The in-house one owned the shop
    window — photographs, words, prices — and named a person this shop does
    not have: there is one shop, and whoever photographs the goods is the
    person who sells them. Publishing is the admin's now.
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


class CardStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


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


class LocationKind(StrEnum):
    """What a place in the building is for.

    The staging areas are places, not statuses. There is no "unplaced" flag on
    anything: being in ``QABUL`` *is* the unplaced state, and a place can be
    counted, listed and alerted on in a way a flag cannot.
    """

    BIN = "bin"              # a real shelf cell, A-01-01
    RECEIVING = "receiving"  # QABUL — off the van, not yet shelved
    PACKING = "packing"      # YIGIM — picked for an order, waiting for a courier
    COURIER = "courier"      # KURYER-7 — in one courier's bag
    DAMAGED = "damaged"      # BRAK — broken, not sellable
    RETURNS = "returns"      # QAYTGAN — came back, not yet inspected


# Where goods may be sold from. A shelf cell, and the receiving area — sorted
# goods standing in QABUL are in the building and the pick list simply sends
# the picker there instead of to a shelf. Not the damaged corner, not the
# uninspected returns, and not a parcel already picked or already in a bag.
SELLABLE_KINDS: frozenset[LocationKind] = frozenset(
    {LocationKind.BIN, LocationKind.RECEIVING}
)


class StockMovementKind(StrEnum):
    """Why goods moved from one place to another.

    A shelf figure used to be a number somebody wrote, then a signed row with
    a reason on it, and now a *move*: from somewhere to somewhere, both of
    which may be the outside world. The kinds below are the moves the
    warehouse actually makes, which is why there is no ``sale`` among them —
    money does not move goods. Goods leave the building when a courier hands
    them over at a door.
    """

    RECEIPT = "receipt"        # van → QABUL, a market run closed
    PUTAWAY = "putaway"        # QABUL → a cell
    MOVE = "move"              # cell → cell, tidying up
    PICK = "pick"              # cell → YIGIM, for an order
    HANDOVER = "handover"      # YIGIM → a courier's bag
    DELIVERED = "delivered"    # a courier's bag → out of the building
    RETURN = "return"          # a customer's hands → QAYTGAN
    RELIST = "relist"          # QAYTGAN → back on sale
    DAMAGE = "damage"          # anywhere → BRAK
    WRITE_OFF = "write_off"    # BRAK → out; gone, and said so
    ADJUST = "adjust"          # a count found something else


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


class BrandAlias(SQLModel, table=True):
    """A spelling of a make, and which row it means.

    The receiving desk types the brand as free text, so the same make arrives
    written five ways. Matching on ``brands.name`` alone made a second row of
    every spelling nobody had used yet — and worse, made the *name* the only
    thing the desk could find a row by, so renaming a brand in the admin panel
    detached it from every sack that would be typed the old way.

    So the name column is what a brand is *called* and this table is what it
    **answers to**: the current name, the names it has been renamed away from,
    and every spelling of every brand folded into it. ``key`` is the name with
    case and punctuation flattened, and is unique across the whole table — one
    spelling means one make, or the desk is back to choosing between two right
    answers. See ``app.brands``.
    """

    __tablename__ = "brand_aliases"

    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brands.id", index=True)
    # As somebody typed it, tidied. Shown on the merge screen, because "which
    # spellings does this row swallow" is the question being asked there.
    name: str = Field(max_length=120)
    key: str = Field(index=True, unique=True, max_length=120)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True)
    title: str
    subtitle: str = ""
    description: str = ""
    # The description with its markup taken off, kept beside it so the
    # shopper's search matches words rather than tags (`app.richtext`). Written
    # by every door that writes `description`; never edited on its own.
    description_text: str = ""

    # The word the receiving desk used — "Krossovka", "Futbolka". Not the
    # category: a category is where the card is filed in the shop, and it is
    # chosen later at a desk by somebody deciding how customers should browse.
    # This is what the goods were called with the sack open, and it is where
    # the receiving form's chips come from: the vocabulary is learned from what
    # has been received rather than configured before anybody has received
    # anything.
    kind: str = Field(default="", index=True, max_length=60)

    # **Both absent while the card is a stub.** A pile off the van has a name,
    # a colour and a count, and nothing else that is true yet: no category, no
    # selling price, no photograph. Making either of these required is what
    # stops the goods reaching the shelf, and the shelf is the urgent half.
    # ``status`` is what keeps such a card out of the shop, and
    # ``app.products.unready`` is what names the gaps.
    category_id: int | None = Field(
        default=None, foreign_key="categories.id", index=True
    )
    brand_id: int | None = Field(default=None, foreign_key="brands.id", index=True)

    # Which run of sizes this card's variants are numbered in — EUR, UK, or
    # the letters. Null is not "unknown", it is **sizeless**: a cap, a bag, a
    # belt buckle. §6.3 says a card is sized or sizeless and never both, and
    # this column is the one place that answers which, so the form offers a
    # size box or does not. It names the system and not the sizes: the sizes
    # a card actually has are its variants, and they are the ledger's.
    size_system_id: int | None = Field(
        default=None, foreign_key="size_systems.id", index=True
    )

    # The identification photograph, taken over the open sack in two seconds.
    # It is not a catalogue picture and is never shown to a customer: its job
    # is to tell two black trainers apart in a search result and in the
    # publishing queue, which no amount of naming discipline does reliably.
    # A good one can be promoted to a catalogue image at publishing time.
    snapshot_url: str = Field(default="", max_length=300)

    # The price the card is advertised at, and the one the listings sort and
    # filter on in SQL. The money itself is on the variant — a 43 may cost
    # more than a 41 — and this is the cheapest of them, recomputed by
    # ``app.products.refresh`` whenever a variant's price moves. It is a
    # display figure and nothing is ever charged from it.
    price: int = 0                   # so'm, integer; 0 until somebody prices it
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
    """A photograph of the goods, belonging to a colour rather than to a card.

    Two colours in six sizes is two pictures, not twelve: nobody photographs a
    size, and asking them to is how a receiving desk stops photographing
    anything. ``colour`` is the colour's own label — the same string the
    variants carry — and an empty one is a picture of the product itself,
    which is what a card with no colours has.

    The first by ``sort`` within a colour is that colour's cover. A card
    cannot leave ``draft`` while any colour it has is without one.
    """

    __tablename__ = "product_images"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    colour: str = Field(default="", index=True, max_length=60)
    url: str
    sort: int = 0


class ProductVariant(SQLModel, table=True):
    """The unit of stock. Everything hangs off this.

    One row per colour per size — "qora / 42" — and not a tree of colours with
    sizes underneath them. The tree counted the same shoes at two depths: a
    colour row held the sum of its sizes, so every count existed twice and one
    of the two had to be an aggregate nobody could move. With a placement
    keyed by (location, variant) that aggregate has nowhere to stand, and
    "which cell is the colour in" has no answer.

    So a variant is one cell of the grid, and it is the only thing the ledger,
    the shelf map and the pick list ever name. "Krossovka — 50 dona" is a
    sentence this system cannot express; "qora / 42 — 3 dona" is what it
    stores.

    A product with no real variation still gets one of these, with both labels
    empty, so stock always has exactly one thing to hang off.
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "colour", "size", name="uq_variant_cell"),
    )

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)

    colour: str = Field(default="", max_length=60)       # "Qora"
    # The hex the picker draws when there is no photograph yet. A colour is
    # chosen by looking at the thing, so this is the fallback and not the
    # point — the pictures are on ``product_images``, keyed by ``colour``.
    colour_hex: str = Field(default="", max_length=9)
    size: str = Field(default="", max_length=40)         # "42"

    # Ours, printed by us. Market goods arrive with no usable code of their
    # own — no label, no barcode, and two sacks of the same shoe from two
    # traders would collide if there were. A variant's barcode is permanent:
    # when the same goods arrive again the label is reprinted, never
    # regenerated, or the shelf ends up holding one thing under two codes.
    sku: str = Field(default="", index=True, max_length=40)
    barcode: str = Field(default="", index=True, max_length=40)

    # What one of *these* costs. The money is here and not on the card: a 43
    # can cost more than a 41 and two colours of the same shoe can be priced
    # apart, and a single figure on the product would have to lie about one of
    # them. ``Product.price`` is the cheapest of these, for the listings.
    price: int = 0

    # What the newest lot of *this cell* cost at the market, in so'm.
    #
    # Kept by ``app.stock.move`` on every ``receipt``, which is the one moment
    # a cost is known: a supply line names a variant and a unit cost together.
    # Per cell and not per card, because a 43 is bought at a different price
    # from a 41 — ``app.products.last_cost`` answers the whole card and is a
    # pricing aid for the card editor, and a margin built on it would be a
    # margin of the wrong shoe.
    #
    # **Nought means unknown, never free.** Every cell received before this
    # column existed has nought here, and a report that treated that as a cost
    # of zero would print a hundred per cent margin on the shop's whole
    # history. Callers render it as unknown and say from when it is real.
    last_cost: int = 0

    # How many of these are in the building, over every location holding any.
    # A running total of ``stock_movements`` and never assigned — see
    # ``app.stock.move``. What can be *sold* is less than this: goods in the
    # damaged corner and goods that came back uninspected are in the building
    # too.
    stock_left: int = 0
    # A cache kept by ``app.stock.move``, and false on a cell that has never
    # held anything. The customer-facing shapes derive availability from the
    # shelf rather than reading this: a cell written into the grid and never
    # received said `true` with nothing behind it, and the shop offered a size
    # it had never owned.
    in_stock: bool = False

    # Taken out of the shop window without being erased.
    #
    # A cell cannot be deleted once anything has moved through it — every
    # movement, placement and order line points at it, and deleting one would
    # leave the room holding goods nothing can name. But a cell written by
    # mistake, or a size this shop has stopped buying, has to be able to stop
    # being offered: a typo received once was otherwise a size struck through
    # on the product page for the life of the card. Retiring is allowed only
    # when it holds nothing, because retiring a cell with goods on a shelf
    # would hide stock the shop has paid for.
    retired: bool = False

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
    layout: str = "rail"            # rail | grid | deals — how it is drawn
    # Which products, which is not the same question as how they are drawn. It
    # was read off ``layout`` for a while and everything that was not ``deals``
    # came back in sold-count order — so "Yangi keldi" and "Ko'p olinadi"
    # answered with the same products in the same order, which reads as a
    # broken screen rather than as two rails.
    pick: str = "popular"           # new | popular | deals
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
    # One variant, not two. A shirt is a size *and* a colour, and it used to
    # take an id for each — which meant a line could name a pair the shop does
    # not stock, and the shelf it drew down was whichever of the two happened
    # to be counted. A variant is now the pair itself.
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")
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


# --------------------------------------------------------------------------- payment


class PaymentCard(SQLModel, table=True):
    """A card a customer may pay with, as the processor describes it.

    **There is no PAN here and there never was.** The app collects the number,
    validates it on the device and sends the four facts a person needs to
    recognise their own card — the scheme, the last four digits, the name and
    the expiry — plus the processor's token, which is the only thing that can
    actually be charged. The number itself never leaves the handset.

    That is also why the row survives a provider swap: Click, Payme and Stripe
    all hand back a token and a masked description, and the column that holds
    it does not care which of them wrote it. What changes is
    ``app.payments``.
    """

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

    # When the order is promised, as a snapshot rather than a booking. Nothing
    # writes these now that the shop has stopped offering windows to choose
    # from — ``services.order_eta_label`` says "being worked out" when the day
    # is null — but the courier list and the operator panel already read them,
    # so a later version that brings windows back has somewhere to put them.
    delivery_day: date | None = None
    delivery_start: str | None = None
    delivery_end: str | None = None

    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD)
    paid: bool = False
    # What the processor called the charge.
    #
    # A payment is a row on an order rather than a table of its own — see the
    # top of ``app.inventory`` — but a row that only says "true" cannot be
    # reconciled against a bank statement or refunded through anybody's API.
    # This is the charge's own name, empty on a cash order because nothing has
    # been charged yet at the point one is placed.
    payment_reference: str = ""

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
    # Always zero: the shop delivers free. The column stays because the charge
    # is a price the owner may want back, and a kept column means the orders
    # already placed still add up when it returns.
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
    # Which cell of the grid was bought. The id is what a count goes back
    # onto; the label beside it is for reading ("Qora · 42") and survives the
    # variant being renamed or deleted.
    variant_id: int | None = Field(default=None, foreign_key="product_variants.id")
    # Apart, as well as joined. The label is one string for a line with one
    # line to spare, and a client with only that prints "Qora · 41" as though
    # it were the name of one thing — the customer chose a colour *and* a size.
    # Snapshotted for the same reason the label is: the variant may be gone by
    # the time somebody opens this order again.
    colour: str = Field(default="", max_length=60)
    size: str = Field(default="", max_length=40)
    variant_label: str = ""
    unit_price: int = 0
    # What the shop paid for one of these, frozen beside what it charged.
    #
    # Snapshotted at checkout from the variant's ``last_cost``, for the same
    # reason ``unit_price`` is snapshotted: the next market run moves the cost
    # and an order must not change when the shelf does. Without it a sold unit
    # cannot be traced to a lot at all — the ``delivered`` movement carries no
    # supply id — so margin was not a figure this system could produce.
    #
    # **Nought means unknown.** Every line written before this column existed
    # has nought, and margin on those orders is unknowable rather than total.
    unit_cost: int = 0
    quantity: int = 1
    reviewed: bool = False

    @property
    def line_total(self) -> int:
        return self.unit_price * self.quantity

    @property
    def line_cost(self) -> int:
        """Nought when the cost is unknown, which is not the same as free."""
        return self.unit_cost * self.quantity


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
    # the merchant decided what to do about it. The goods are ours now, so the
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

# Where everything is.
#
# The old model knew how many of a thing there were and nothing about where
# they stood, so "fetch two black 42s" was answered by a person who already
# knew the room. Below is the part that was missing: a place, what is in it,
# and every move between two places.


class Location(SQLModel, table=True):
    """One place goods can be: a shelf cell, or an area with a job.

    **The racks are data, not constants.** Three units of four columns by four
    rows is where the owner starts, not where they end — a fourth unit or a
    second room is a seed change and not a code change, and nothing anywhere
    may write 3, 4 or 48 as a number.

    Cell codes read the way a person reads a shelf: ``A-01-01`` is rack A,
    leftmost column, **bottom** row. Row 1 at the bottom because that is where
    a person's eye starts and where the heavy things go.
    """

    __tablename__ = "locations"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=30)
    kind: LocationKind = Field(index=True)

    # Null on everything but a cell: QABUL is not in a rack.
    rack: str | None = Field(default=None, max_length=4)
    column_no: int | None = None
    row_no: int | None = None

    # How many units this cell is meant to hold. Not enforced — a cell that
    # refuses the last pair of shoes at nine in the evening is a cell somebody
    # works around — but shown, so the map can say which cells are full and
    # the putaway screen can warn before it is.
    capacity: int = 0
    is_active: bool = True
    note: str = ""


class StockPlacement(SQLModel, table=True):
    """How many of one variant are in one place.

    Derived state: the sum of the movements into this pair less the movements
    out of it. It is a table rather than a query because the shelf map reads
    every cell at once and the pick list asks "where is this" on every line,
    and a test holds it to equalling the ledger — a placement that has drifted
    is a bug in ``app.stock``, not a figure to be corrected by hand.
    """

    __tablename__ = "stock_placements"
    __table_args__ = (
        UniqueConstraint("location_id", "variant_id", name="uq_placement"),
    )

    id: int | None = Field(default=None, primary_key=True)
    location_id: int = Field(foreign_key="locations.id", index=True)
    variant_id: int = Field(foreign_key="product_variants.id", index=True)
    qty: int = 0


class StockMovement(SQLModel, table=True):
    """One move: this many of this variant, from here to there.

    ``from_location_id`` null means the outside world — a market run arriving,
    a customer's parcel coming back. ``to_location_id`` null means it left the
    building: delivered, or written off. Both null is not a movement and is
    refused.

    ``qty`` is always positive. The direction is the pair of places, not a
    sign, which is what makes "what is in cell A-02-03" a question with one
    answer rather than a sum somebody has to interpret.
    """

    __tablename__ = "stock_movements"

    id: int | None = Field(default=None, primary_key=True)
    variant_id: int = Field(foreign_key="product_variants.id", index=True)

    from_location_id: int | None = Field(
        default=None, foreign_key="locations.id", index=True
    )
    to_location_id: int | None = Field(
        default=None, foreign_key="locations.id", index=True
    )

    kind: StockMovementKind = Field(index=True)
    qty: int
    reason: str = ""

    # Who moved it. Null for a move nobody decided.
    actor_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    # What caused it, so the ledger reads as a story in both directions. The
    # return is here as well as the brief's two because a parcel coming back
    # is the one cause that arrives from outside the building and has no
    # supply and no order line to explain it.
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


class PickStatus(StrEnum):
    """Where one order's picking has got to."""

    WAITING = "waiting"      # on the board, nobody has taken it
    PICKING = "picking"      # somebody is walking the room with it
    PICKED = "picked"        # everything is in YIGIM, waiting for a courier


class PickTask(SQLModel, table=True):
    """One order, to be fetched off the shelves.

    Taken rather than assigned: a picker at the bench takes the oldest task on
    the board, the same way a courier takes a round. An assigner would be a
    person deciding something a queue already decides.
    """

    __tablename__ = "pick_tasks"
    __table_args__ = (UniqueConstraint("order_id", name="uq_pick_task_order"),)

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    status: PickStatus = Field(default=PickStatus.WAITING, index=True)
    picker_id: int | None = Field(default=None, foreign_key="users.id", index=True)

    created_at: datetime = Field(default_factory=utcnow, index=True)
    taken_at: datetime | None = None
    finished_at: datetime | None = None


class PickLine(SQLModel, table=True):
    """One variant to fetch from one place.

    A line per *place*, not per order line: a model that outgrew its cell is
    in two of them, and the picker has to be sent to both. ``walk_order`` is
    filled in when the task is built, from the serpentine order of the room,
    so the list comes back in the order somebody walks rather than in the
    order the ids fall.
    """

    __tablename__ = "pick_lines"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="pick_tasks.id", index=True)
    order_item_id: int | None = Field(default=None, foreign_key="order_items.id")
    variant_id: int = Field(foreign_key="product_variants.id", index=True)
    location_id: int = Field(foreign_key="locations.id", index=True)

    qty: int = 0
    picked_qty: int = 0
    walk_order: int = 0
    picked_at: datetime | None = None


class CountStatus(StrEnum):
    OPEN = "open"          # somebody is counting
    CLOSED = "closed"      # the differences are in the ledger


class StockCount(SQLModel, table=True):
    """A recount of one cell.

    Per cell rather than per room: a stocktake of the whole warehouse is a day
    nobody has, and a cell is what one person can count without stopping the
    shop. What it finds becomes an ``adjust`` movement with the counter's name
    on it — never an assignment.
    """

    __tablename__ = "stock_counts"

    id: int | None = Field(default=None, primary_key=True)
    location_id: int = Field(foreign_key="locations.id", index=True)
    status: CountStatus = Field(default=CountStatus.OPEN, index=True)
    counter_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    note: str = ""

    started_at: datetime = Field(default_factory=utcnow, index=True)
    closed_at: datetime | None = None


class StockCountLine(SQLModel, table=True):
    """What the system thought, and what the person found.

    Both are kept. The difference is the whole point of a stocktake, and a
    line that only recorded the new figure would leave nobody able to say how
    far out the shelf had drifted.
    """

    __tablename__ = "stock_count_lines"

    id: int | None = Field(default=None, primary_key=True)
    count_id: int = Field(foreign_key="stock_counts.id", index=True)
    variant_id: int = Field(foreign_key="product_variants.id", index=True)

    expected_qty: int = 0
    counted_qty: int = 0

    @property
    def difference(self) -> int:
        return self.counted_qty - self.expected_qty


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


# --------------------------------------------------------------------------- the palette and the size systems


class Colour(SQLModel, table=True):
    """One named colour, and the swatch a picker draws for it.

    ``product_variants.colour`` goes on holding the **name as a string**, and
    that is deliberate: the ledger, the shelf map, ``product_images.colour``
    and every order line already agree on that string, and turning it into a
    foreign key would rewrite all of them to solve a problem none of them has.
    What this table fixes is upstream of that. The colour was typed at the
    receiving desk, so ``qora``, ``Qora`` and ``QORA`` became three chips, three
    filters and three photograph groups for one black shoe — and this shop's
    live data holds ``Siniy`` beside ``Ko'k``, which is the same failure in two
    languages. Offering a list instead of a box is what stops the next one.

    **It is a palette, not a whitelist.** A colour already on a variant that is
    not in this table is still a perfectly good colour and nothing rejects it;
    the form's "+ yangi rang" writes it in here so the *next* person picks it
    rather than retyping it.

    ``key`` is the name with case and punctuation flattened — the same rule
    ``app.brands`` uses, and unique for the same reason: one spelling must mean
    one row, or the picker is offering two right answers again.
    """

    __tablename__ = "colours"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=60)
    # 60 to match ``ProductVariant.colour``: a palette name that will not fit
    # in the column it is copied into is a name that fails at the receipt.
    name: str = Field(max_length=60)
    key: str = Field(index=True, unique=True, max_length=60)
    # ``#rrggbb``, or empty for a colour no single swatch describes. The
    # picker falls back to the photograph, which is what it prefers anyway.
    hex: str = Field(default="", max_length=9)
    sort: int = 0


class SizeSystem(SQLModel, table=True):
    """A named run of sizes — ``Erkaklar poyabzali EUR`` — that a card can use.

    The desk used to type sizes, so a European 43 and a UK 9 could sit on one
    card and nothing could tell them apart afterwards. A card names a system
    and the form then offers that system's values, so the mixture cannot be
    typed in the first place.

    ``family`` and ``scale`` are split out rather than left for a screen to
    parse back out of ``name``: §5.2 draws *Erkaklar poyabzali* once with
    EUR/UK/US/RUS under it, and splitting a display name on a space to find
    that grouping is the kind of rule that breaks on the first system called
    ``Kamar``. Either may be empty — ``Kiyim`` is a family with one scale and
    no name for it.

    **Nothing here makes a card sized.** A card that names no system is
    sizeless, which is the state ``VocabOut.sizeless`` already reports and
    §6.3 requires to stay a single either/or.
    """

    __tablename__ = "size_systems"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=60)
    name: str = Field(max_length=80)
    family: str = Field(default="", max_length=60)   # "Erkaklar poyabzali"
    scale: str = Field(default="", max_length=20)    # "EUR"
    sort: int = 0


class SizeValue(SQLModel, table=True):
    """One size a system offers, in the order it is worn or numbered.

    Stored already tidied by ``app.products.tidy_size`` — the same function
    every door that writes a variant runs — so the palette cannot be the one
    place in the system where ``xl`` and ``XL`` are two sizes (§6.4). The
    uniqueness is on the tidied value for the same reason.

    ``sort`` is stored rather than derived because a shop reorders its own
    list, and ``app.products.size_order`` only knows the orders it was taught.
    """

    __tablename__ = "size_values"
    __table_args__ = (
        UniqueConstraint("system_id", "value", name="uq_size_value"),
    )

    id: int | None = Field(default=None, primary_key=True)
    system_id: int = Field(foreign_key="size_systems.id", index=True)
    value: str = Field(max_length=40)
    sort: int = 0
