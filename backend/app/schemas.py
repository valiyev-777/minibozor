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
    CountStatus,
    DeliveryKind,
    Language,
    LocationKind,
    NotificationKind,
    OrderStatus,
    PaymentMethod,
    PickStatus,
    PickupRunStatus,
    ProductStatus,
    ReturnInspection,
    ReturnStatus,
    StockMovementKind,
    SupplyStatus,
    UserRole,
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


class ColourOut(BaseModel):
    """One colour a card comes in, with the picture of it.

    A colour is chosen by looking at the thing, so what the picker draws is
    the photograph; the hex is the fallback for a colour that has none, which
    only a draft can have.
    """

    colour: str
    hex: str = ""
    image_url: str | None = None
    in_stock: bool = True


class VariantOut(BaseModel):
    """One cell of the colour × size grid — the thing that is actually bought.

    Flat, where this used to be a tree of colours with sizes hanging off them.
    A basket line names one of these and nothing else: the pair used to be two
    ids that could disagree with each other, and one of the two was an
    aggregate nobody could point at on a shelf.
    """

    id: int
    colour: str
    size: str
    label: str            # "Qora · 42", ready to print
    sku: str = ""
    barcode: str = ""
    price: int
    in_stock: bool
    # What can still be bought: what is on a sellable shelf, less what is
    # already in somebody's basket or promised to an order.
    stock_left: int = 0


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
    # The colours first, because that is the order a person chooses in: which
    # one, looking at the photographs, and then which size of it.
    colours: list[ColourOut]
    variants: list[VariantOut]
    specs: list[SpecOut]
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
    # The colour and the size, apart. `variant_label` joins them with a dot
    # for a place with one line to spare, and a client that prints only that
    # ends up showing "Qora · 41" as though it were the name of one thing —
    # the customer chose a colour *and* a size, and the basket should say so.
    # Kept beside it rather than instead of it: the shipped apps read the label.
    colour: str = ""
    size: str = ""
    variant_label: str
    # Which size and which colour this line is, and not only what they are
    # called. The label is one joined string for reading; a client deciding
    # whether *this* line is the one the product page is currently showing
    # needs the ids it was added with, and without them the page could only
    # match on the product — so a shirt in the basket in medium left no way to
    # add a large.
    variant_id: int | None = None
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
    # One id, not two. It names a cell of the colour × size grid; a card with
    # no variation has exactly one and it may be left out.
    variant_id: int | None = None
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


# --------------------------------------------------------------------------- orders


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    title: str
    image_url: str
    colour: str = ""
    size: str = ""
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

    The number is collected and validated on the handset — Luhn and the BIN,
    see ``core/util/CardBrand.kt`` — and what is posted is the description a
    person recognises their own card by, plus the token that can be charged.
    Until an SDK is wired up the token is ``app.payments.DEV_TOKEN_PREFIX``
    and a uuid, which is the one line that changes when Click or Payme lands.
    """

    brand: str = "Humo"
    last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    holder: str = ""
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2024, le=2099)
    processor_token: str
    is_default: bool = False


class CheckoutIn(BaseModel):
    address_id: int | None = None
    pickup_point_id: int | None = None
    slot_id: int | None = None
    payment_method: PaymentMethod = PaymentMethod.CARD
    # Which card pays for it. Required when the method is ``card`` and refused
    # when it is ``cash``: an order cannot be charged to a card nobody named,
    # and a cash order that names one is a client that has not decided.
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
    totals: CartTotalsOut
    # The card the order would be charged to, so the confirm screen can name it
    # before anybody presses anything.
    card: CardOut | None = None


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


# --------------------------------------------------------------------------- warehouse


class StockLineOut(BaseModel):
    """One count on one variant, named so a person can read it.

    The SKU is here because a warehouse reads a label, not a title: the code
    on the pile has to be able to find the line.
    """

    variant_id: int
    sku: str
    variant_label: str
    product_title: str


class PlacementOut(BaseModel):
    """How many of one variant one place holds."""

    location_id: int
    code: str
    qty: int


class MovementOut(StockLineOut):
    id: int
    kind: StockMovementKind
    quantity: int
    # Where it came from and where it went, by code. "—" at either end is the
    # outside world: a market run arriving, a parcel going out of the door.
    from_code: str
    to_code: str
    reason: str
    actor: str
    supply_id: int | None
    order_id: int | None
    return_request_id: int | None
    created_at: datetime


class ShelfOut(BaseModel):
    """What the ledger says, what is promised, and what is left to sell."""

    variant_id: int
    variant_label: str
    # Everything in the building. Not the same as what can be sold: the
    # damaged corner and the uninspected returns are in the building too.
    on_hand: int
    reserved: int
    sellable: int
    places: list[PlacementOut] = []


class SupplyLineOut(StockLineOut):
    id: int
    quantity: int
    unit_cost: int
    line_cost: int


class SupplyOut(BaseModel):
    id: int
    code: str
    status: SupplyStatus
    place: str
    transport_cost: int
    buyer: str
    note: str
    lines: list[SupplyLineOut]
    total_cost: int
    declared_at: datetime
    received_at: datetime | None
    # How long the sacks have been standing there. The one figure that turns
    # an unsorted run from a row in a list into something anybody acts on.
    age_minutes: int


class LocationOut(BaseModel):
    """One place, as the shelf map draws it.

    ``units`` and ``products`` are what a cell is judged by: how full it is
    and how many different things are mixed into it. A picker reaching into a
    cell of black and white shoes needs to be told to look, and the count is
    what tells them.
    """

    id: int
    code: str
    kind: LocationKind
    rack: str | None = None
    column_no: int | None = None
    row_no: int | None = None
    capacity: int = 0
    is_active: bool = True
    note: str = ""

    products: int = 0
    units: int = 0
    # How many more units this place is meant to take. Null where no capacity
    # was ever stated — every staging area, and a cell built in a hurry — and
    # null is not "plenty": it is nobody having said, which is a different
    # thing for a screen to draw than a number.
    free: int | None = None
    # Against capacity, **uncapped**. It used to be capped at a hundred, which
    # made a cell holding sixty-five of a stated sixty read exactly like one
    # holding sixty — the office could not see the one thing this figure is on
    # the screen to show them. 130 means a third more than it is meant to
    # hold. Zero capacity reads as nought rather than as a division by
    # nothing, and the bar on the map clamps its own width.
    fill_percent: int = 0
    # How long the oldest thing here has been standing, in minutes. The one
    # figure that turns QABUL from a list into something somebody acts on.
    oldest_minutes: int = 0


class CellContentOut(BaseModel):
    """One variant in one place, named the way a person reads a label."""

    variant_id: int
    product_id: int
    product_title: str
    variant_label: str
    sku: str
    barcode: str
    qty: int
    minutes_here: int = 0


class LocationDetailOut(LocationOut):
    contents: list[CellContentOut] = []


class ShelfMapOut(BaseModel):
    """The room in one answer, because the map draws all of it at once.

    Three lists rather than one: the racks are a grid, the staging areas are a
    row of tiles above them, and a courier's bag is a tile that exists only
    while somebody is carrying something.
    """

    cells: list[LocationOut]
    staging: list[LocationOut]
    couriers: list[LocationOut]


class RackWriteIn(BaseModel):
    """A shelf unit to build, described the way somebody stands in front of it.

    Columns and rows rather than a total: a rack is a grid and every code in
    the building reads ``A-03-02`` — third column, second row from the floor.
    A number of cells with no shape to it could not be written down as codes,
    and a picker's route through the room is a walk along columns.
    """

    # Short, because it is the first thing on every label in the building.
    rack: str = Field(min_length=1, max_length=4, pattern=r"^[A-Za-z0-9]+$")
    columns: int = Field(ge=1, le=99)
    rows: int = Field(ge=1, le=99)
    # What one cell holds, in units. Shown rather than enforced — see Location.
    capacity: int = Field(default=60, ge=0, le=9999)


class RackExtendIn(BaseModel):
    """The shape a rack that already exists should **have** — not a delta.

    Somebody bolted a fifth column onto A. They are standing in front of it
    counting columns, so what they can say without arithmetic is "A is five
    by four now"; "add one column" asks them to know what the system thinks A
    was, and they are looking at the shelf rather than at the system.

    It also makes the request repeatable. Sending the same shape twice adds
    nothing the second time, which is what a form somebody double-taps at the
    end of a Saturday needs to do.

    **Nothing is ever removed.** A smaller shape than the rack already has is
    not an error and not a demolition — it adds nothing and says so. Retiring
    a cell is ``is_active`` and is a decision about one cell, taken by
    somebody who has looked at what is in it.

    The rack letter is in the path, because this door is about a rack that is
    already there. Building a new one is ``POST /warehouse/racks``, and the
    two are apart on purpose: "A, 6 columns" against an A that does not exist
    is a typo, and against an A of four columns it is a screwdriver.
    """

    columns: int = Field(ge=1, le=99)
    rows: int = Field(ge=1, le=99)
    # What one *new* cell holds, in units. Absent means what the rack's own
    # cells already hold — a shelf unit is one piece of furniture and a column
    # bolted onto it holds what the others hold, so the schema's own default
    # would be a number from a different rack. Existing cells are never
    # touched, whatever this says.
    capacity: int | None = Field(default=None, ge=0, le=9999)


class RackOut(BaseModel):
    rack: str
    # How many cells were **written**, which for an extension is how many were
    # missing rather than how many were asked for.
    cells: int
    message: str


class CellRemoved(BaseModel):
    """A cell taken out of the room, and whether its row went with it.

    **Removing a cell means removing it.** For a long time it meant
    ``is_active = False``: the row stayed, the code stayed, and the map drew
    the hole struck through with a way back on it. That is a correct thing to
    do with a ledger and the wrong thing to show a shop. A rack unbolted back
    to four columns is four columns; a fifth column of crossed-out tiles is a
    shelf nobody can point at in the room, and it is on the screen for ever.

    So the row goes — *when it can*. A cell that was built by a typo and never
    used is named by nothing, and deleting it leaves the shop exactly as it
    would be had the typo never happened. A cell that has been lived in is a
    different object: a movement from March, a stocktake, a picking line all
    name it, and deleting the row would leave the ledger pointing at a place
    that does not exist — which is not a tidier shop, it is a shop that cannot
    say where its goods came from. That one keeps its row and leaves the room
    the quiet way, invisible to every screen.

    ``erased`` is which of the two happened, and it is reported rather than
    chosen: the caller cannot ask for the ledger to be broken, and does not
    have to know which case it is in. Both are gone from the map.

    Emptiness is the one thing asked of the caller beforehand, and it is
    refused loudly: goods in a place nobody can see are goods nobody can find.
    Carry them somewhere first.
    """

    code: str
    # True when the row itself is gone, false when it was kept for the
    # ledger's sake. Either way the cell is out of the room.
    erased: bool
    message: str


class WhereIsOut(BaseModel):
    """Where one thing is, for the search box on the map.

    Type a name or paste a barcode and the cells holding it light up. The
    answer is per variant and not per card: "krossovka" is in nine cells and
    none of that helps; "qora 42" is in one.
    """

    variant_id: int
    product_id: int
    product_title: str
    variant_label: str
    sku: str
    barcode: str
    places: list[PlacementOut] = []


class PutawayLineOut(CellContentOut):
    """Something standing in the receiving area, waiting to be shelved."""

    suggestion: str = ""       # a cell this model is already in, if there is one


class EmptyRoomIn(BaseModel):
    """Take everything off a cell, or out of the whole room.

    A reason is required and there is no default. This writes off goods that
    the shop still believes it has — the one operation here that makes stock
    disappear rather than move — and "why" is the only thing that tells a
    stocktake three months later from a mistake somebody made in a hurry.
    """

    # Empty when the whole room is meant. A cell code narrows it to one cell.
    code: str = Field(default="", max_length=20)
    reason: str = Field(min_length=3, max_length=200)


class EmptiedOut(BaseModel):
    """What left, so the answer is not a shrug."""

    moved: int = 0
    units: int = 0
    cells: int = 0


class SuggestedCellOut(BaseModel):
    """The cell the receiving form should offer, or an empty code.

    Its own shape rather than a reused `Message`, whose fields are `ok` and
    `message`: a cell code is not a message, and reading one out of the other
    is how a caller ends up asserting on the wrong key.
    """

    code: str = ""


class PutawayPlanLineOut(BaseModel):
    """One cell in the plan, and what the plan would put in it.

    ``free`` and ``units`` are how it was chosen, shown rather than hidden: a
    plan a person cannot argue with is a plan they will ignore, and the whole
    answer is a suggestion. Null ``free`` is a cell with no stated capacity —
    not a roomy one, an unmeasured one.
    """

    code: str
    quantity: int
    free: int | None = None
    units: int = 0
    # Whether this cell already holds this model. One model per cell is the
    # discipline, and these come first — the screen usually ticks them and
    # thinks about the rest.
    holds_this_model: bool = False


class PutawayPlanOut(BaseModel):
    """Where N pieces would go if nobody thought about it.

    The answer the receiving screen needs in one request: it was asking
    ``suggest-cell`` for one code, getting one cell that may hold four more
    pairs, and leaving the person to work out the other forty by eye.

    ``over_capacity`` says the last line is more than the room it is going
    into. That happens because the goods are standing on the floor: a plan
    that stops short of the quantity is a plan that does not say where the
    rest went, and the honest answer is a cell that will be over-full and a
    sentence saying so.
    """

    quantity: int
    lines: list[PutawayPlanLineOut] = []
    over_capacity: bool = False
    # Empty when the plan fits. A sentence in the reader's language when it
    # does not, because "130%" on its own is a screen nobody reads twice.
    message: str = ""


class MoveIn(BaseModel):
    """Carry a quantity from where it is to a cell.

    ``from_code`` because a mistyped cell is the one thing nothing else can
    fix: goods land on a shelf in one action now, and if that action named the
    wrong shelf then the ledger and the room disagree until somebody says so.
    Both legs are named, so the movement is a journey rather than an
    adjustment — an adjustment says the count was wrong, and it was not.
    """

    variant_id: int
    qty: int = Field(gt=0)
    from_code: str = Field(min_length=1, max_length=20)
    to_code: str = Field(min_length=1, max_length=20)


class MoveCellIn(BaseModel):
    """Carry what is standing in one cell over to another, in one action.

    A cell holds one model in four sizes, and tidying it through ``MoveIn``
    was four requests, four idempotency keys and four chances to be
    interrupted halfway — leaving a model in two cells, which is the exact
    mess moving it was meant to clear up. This is the same journey, once.

    **No quantities.** What moves is what is there, read inside the
    transaction that moves it. The alternative — a list of lines with counts
    on them — is a snapshot the screen read some seconds ago, and if a picker
    took two out of the cell in between then the batch is asking for five
    where three stand and the whole move is refused. "Everything in A-02-03"
    does not go stale.

    ``variant_ids`` narrows it: a cell with two models in it, and only one of
    them is moving. Empty means all of it, which is the ordinary case and the
    reason this door exists.
    """

    from_code: str = Field(min_length=1, max_length=20)
    to_code: str = Field(min_length=1, max_length=20)
    variant_ids: list[int] = Field(default=[], max_length=200)


class PutawayIn(BaseModel):
    """Carry a quantity to a cell.

    ``code`` is typed, not scanned — market goods have no usable code of their
    own and the owner's phone cameras read them badly. It must keep working
    unchanged when a scanner gun is plugged in later: the gun types the code
    and presses Enter, which is what a text input already does.
    """

    variant_id: int
    qty: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=30)


class PickLineOut(BaseModel):
    """One place to walk to, and the thing to bring back from it.

    **The variant leads, not the cell.** The cell is where you walk to; the
    variant is the thing you must not get wrong, so the model, the colour and
    the size come first and the code follows them.
    """

    id: int
    variant_id: int
    product_title: str
    colour: str
    size: str
    variant_label: str
    sku: str
    barcode: str
    location_id: int
    location_code: str
    qty: int
    picked_qty: int
    walk_order: int
    # Whether this cell holds anything else. A picker reaching into a cell of
    # black and white shoes has to be told to look.
    mixed_cell: bool = False


class PickTaskOut(BaseModel):
    id: int
    order_id: int
    order_code: str
    status: PickStatus
    picker: str = ""
    lines: list[PickLineOut] = []
    created_at: datetime
    taken_at: datetime | None = None
    finished_at: datetime | None = None
    age_minutes: int = 0


class PickWaitingOut(BaseModel):
    """One order that is waiting for the board, with nothing on it yet.

    Not a task, and that is the point: a task exists once somebody has worked
    out where the goods are, and until then the order is only a promise the
    bench has not begun. The picker's board shows these above the real tasks so
    that starting one is a tap rather than a message to the office.
    """

    order_id: int
    order_code: str
    items_count: int
    # The same one-line summary the office queue carries: a picker recognises
    # an order by the thing in it, not by its code.
    items_summary: str = ""
    delivery_day: date | None = None
    delivery_window: str = ""
    age_minutes: int = 0


class PickLineIn(BaseModel):
    qty: int = Field(gt=0)


class CountLineOut(BaseModel):
    variant_id: int
    product_title: str
    variant_label: str
    sku: str
    barcode: str
    expected_qty: int
    counted_qty: int


class CountOut(BaseModel):
    id: int
    location_id: int
    location_code: str
    status: CountStatus
    counter: str = ""
    note: str = ""
    lines: list[CountLineOut] = []
    started_at: datetime
    closed_at: datetime | None = None


class CountStartIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)


class CountedLineIn(BaseModel):
    variant_id: int
    counted_qty: int = Field(ge=0)


class CountSubmitIn(BaseModel):
    """What is actually in the cell, as counted.

    Every variant the system thinks is there has to be answered for — a line
    left out is a line nobody counted, and treating silence as agreement is
    how a stocktake finds nothing. Variants *not* expected may be added: goods
    turn up in the wrong cell, and that is exactly what a count is for.
    """

    lines: list[CountedLineIn] = Field(min_length=1, max_length=500)
    note: str = ""


class CardPriceIn(BaseModel):
    """One selling price for the whole card.

    The money lives on the variants, because a 43 can cost more than a 41 — but
    nothing off a market run is priced by size, and pricing twelve cells one at
    a time to publish one card is the sort of arithmetic that leaves cards
    unpublished. So this writes them all, and repricing a single cell
    afterwards still goes through its own door.
    """

    price: int = Field(gt=0)
    old_price: int | None = Field(None, gt=0)
    # Only this colour, when a colour costs more than the others.
    colour: str | None = None


class ReceiptSizeIn(BaseModel):
    """One size of one receipt. An empty size is goods that have none."""

    size: str = Field(default="", max_length=40)
    quantity: int = Field(gt=0)


class ReceiptIn(BaseModel):
    """What came through the door, and how many — and nothing about where.

    The first of the receiving flow's two moments. The person is at the bench
    with the goods; the cell is asked at the shelf, one minute and ten metres
    later, by ``POST /warehouse/receipts/{id}/shelve`` — asking for it here
    is asking somebody who has not walked anywhere yet where they will end
    up, and a guess in a cell field is stock in the wrong place. Until the
    second moment the goods stand in ``QABUL``, which is a real, sellable
    place and not a flag.

    Either ``product_id`` names a card that already exists, or ``kind`` /
    ``brand`` / ``colour`` write a new one. Two black trainers of different
    makes are two cards, which is why the brand is part of the identity and
    why the identification photograph matters more than the spelling.

    One receipt is one colour. White shoes and black shoes are two receipts,
    each with its own sheet of labels — the second keeps the card, the kind,
    the brand and the cost, so only the colour and the sizes are retyped.
    """

    product_id: int | None = None

    kind: str = Field(default="", max_length=60)
    brand: str = Field(default="", max_length=80)
    colour: str = Field(default="", max_length=60)
    colour_hex: str = Field(default="", max_length=9)
    # Composed from kind/brand/colour when absent. A card written at the desk
    # is renamed at publishing time by somebody writing for customers.
    title: str = Field(default="", max_length=200)
    snapshot_url: str = Field(default="", max_length=300)

    # In the order they were typed, which is the order the stickers print in
    # and the order the piles sit on the table.
    sizes: list[ReceiptSizeIn] = Field(min_length=1, max_length=60)

    # What one of these cost at the market. Required, and required *here*:
    # this is the only moment anybody knows it. By the evening it is a guess,
    # and a guessed cost is worse than an empty one because it reaches the
    # profit report looking like a fact.
    unit_cost: int = Field(gt=0)

    # This receipt's own supply row. Where it was bought and what the van
    # cost, both optional — written *by* the receipt, never edited by hand.
    place: str = Field(default="", max_length=120)
    transport_cost: int = Field(default=0, ge=0)


class ReceiptLabelOut(BaseModel):
    """One variant's sticker, and how many of it to print.

    ``copies`` is the quantity received: twenty shoes are twenty stickers of
    one barcode, because twenty identical shoes are twenty of one thing. The
    size and the colour ride separately from ``variant_label`` because the
    58 mm sticker draws the size biggest and the colour beside it.
    """

    variant_id: int
    product_title: str
    colour: str
    size: str
    variant_label: str
    sku: str
    barcode: str
    copies: int


class ReceiptOut(BaseModel):
    """What was booked in, and the sheet of stickers to print for it.

    No cell on it: the goods are standing in ``QABUL`` and the screen's next
    question — the only one left — is answered through the shelve door.
    """

    product: AdminProductOut
    run_id: int
    run_code: str
    quantity: int
    total_cost: int
    # One line per size, in the order they were typed, each with its count.
    labels: list[ReceiptLabelOut] = []


class ReceiptShelveIn(BaseModel):
    """The second moment: the one thing nobody could know at the bench."""

    location_code: str = Field(min_length=1, max_length=20)


class ReceiptShelvedOut(BaseModel):
    """The confirmation line: ``20 dona · B-01-02 · 2 400 000 so'm``.

    ``quantity`` is what was carried *now* — nought when the receipt had
    already been shelved, which is answered politely rather than refused: the
    goods are where the person wanted them, and a second tap at the shelf is
    not a mistake to shout about. ``message`` says so in the reader's
    language when there was nothing left to carry.
    """

    receipt_id: int
    run_code: str
    location_code: str
    quantity: int
    total_cost: int
    message: str = ""


class ReceiptWaitingOut(BaseModel):
    """One receipt whose goods are labelled and still standing in QABUL.

    What the ``/qabul`` screen restores its second moment from after a
    reload, and what the dashboard's "Yorliqlangan, javonga qo'yilmagan"
    tile counts. ``product_id`` is there so the screen can ask
    ``suggest-cell`` where the rest of this model already lives.
    """

    id: int
    code: str
    product_id: int | None = None
    product_title: str = ""
    quantity: int
    age_minutes: int


class RetireIn(BaseModel):
    """Whether this cell is offered in the shop. False puts it back."""

    retired: bool


class VocabOut(BaseModel):
    """The receiving desk's chips, learned rather than configured.

    Nobody sets up a list of goods before they have received any, and a market
    brings whatever it brings. So the chips are what has come through the door
    before, most-used first, and "+ yangi" is always there.

    ``sizes`` is keyed by kind: trainers were last received in 40-45 and shirts
    in S-XXL, and offering the right row is the difference between three taps
    and twelve.
    """

    kinds: list[str] = []
    brands: list[str] = []
    colours: list[str] = []
    sizes: dict[str, list[str]] = {}
    # The kinds that have no sizes at all — a cap, a bag, a wristwatch. The
    # desk asked every kind for sizes, and somebody holding a sack of caps
    # types *something* into a box that will not go away, which is how a size
    # called "KS" was born. Learned the same way as the rest: a kind belongs
    # here while every one of its cells is sizeless.
    sizeless: list[str] = []
    # The rows of the specification table, keyed by kind: what was written
    # against a Krossovka last time. Typing "Mato", "Taglik", "Ishlab
    # chiqarilgan" from scratch for every card is how a table stays empty, and
    # an empty table is a block the apps do not draw at all.
    spec_keys: dict[str, list[str]] = {}


class ProductLabelOut(BaseModel):
    """One printable label: what we generate, because nothing else has a code."""

    variant_id: int
    product_title: str
    variant_label: str
    # The two halves of the label's face, separately: at 58 × 40 mm the size
    # is the biggest thing on the sticker and the colour sits beside it, so
    # the printer needs them apart rather than glued into ``variant_label``.
    colour: str = ""
    size: str = ""
    sku: str
    barcode: str
    price: int
    # How many stickers to print of this line — every unit gets one, so a
    # receipt of ten 43s is one label printed ten times. Defaults to one
    # because a reprint from the label screen is usually a printer jam, not a
    # second van.
    copies: int = 1


class CellLabelOut(BaseModel):
    code: str
    rack: str | None = None
    column_no: int | None = None
    row_no: int | None = None


class LabelSheetOut(BaseModel):
    """The data behind the labels the browser prints — one 58 mm page each.

    Rendered client-side: a barcode is a picture of a string and drawing it in
    the browser means no image to store, no font to install on a server, and a
    reprint that cannot drift from the code on the row.
    """

    products: list[ProductLabelOut] = []
    cells: list[CellLabelOut] = []


class ScanVariantOut(WhereIsOut):
    """What a scanned goods label names, whether or not any is on a shelf.

    ``where-is`` hides a variant with no placements because its screen lights
    cells up and there is no cell to light. A scan is a different question —
    "what is this sticker?" — and the receiving desk asks it precisely about
    goods that are not booked in yet, so the places may be an empty list and
    the identity still comes back whole.
    """

    colour: str = ""
    size: str = ""


class ScanOut(BaseModel):
    """One answer for whatever the scanner read, whichever screen read it.

    A gun and a phone camera both end at a string, and the string is one of
    three things: a goods label (barcode or SKU), a cell label, or noise.
    ``kind`` says which, and exactly one of the two payloads is filled. A miss
    is a typed answer rather than a 404 because a mis-scan is a normal minute
    of warehouse work, not an error — the screen shows it loudly and listens
    for the next one.
    """

    kind: Literal["variant", "cell", "none"]
    # What was looked up — normalised to the cell's own spelling on a cell
    # hit, echoed as scanned otherwise, so the screen can name the code it is
    # refusing.
    code: str
    variant: ScanVariantOut | None = None
    cell: LocationDetailOut | None = None


class FigureOut(BaseModel):
    """One headline, and the same headline over the period before it.

    ``percent`` is null when the previous period was nought. "Up from nothing"
    has no percentage, and the alternatives are all worse: infinity does not
    render, a hundred per cent is a lie, and nought reads as "no change" — the
    opposite of what happened. A null tells the screen to draw the arrow and
    leave the number off.

    ``money`` says whether the value is so'm or a count of things, because the
    apps format money themselves and a so'm figure printed as a bare integer is
    the one mistake every client makes once.

    ``percent_value`` is for the figures that are themselves a percentage — a
    cancellation rate, a first-attempt rate. The value is then in hundredths of
    a per cent, so 12.34% is 1234 and the wire stays integers all the way
    through, as money does.
    """

    key: str
    label: str
    value: int
    # Null on a figure the period before cannot answer. Stock value, full
    # cells, dead stock: the shop knows what is standing in the room now and
    # keeps no history of what was standing in it a month ago, so a previous
    # would have to be invented. Null makes the screen draw the figure without
    # an arrow, which is the truth; a nought would draw an arrow pointing up.
    previous: int | None = None
    delta: int | None = None
    percent: float | None = None
    money: bool = False
    percent_value: bool = False


class DashboardTileOut(BaseModel):
    """One figure on the dashboard, and where to go and act on it.

    ``href`` is not decoration. A dashboard figure that is not a link is a
    dead end: somebody reads "4 cards held back for want of a photograph" and
    then has to go and find them.
    """

    key: str
    label: str
    value: int
    hint: str = ""
    href: str = ""
    # For the one tile that must be impossible to ignore — goods that have
    # stood in the receiving area too long.
    urgent: bool = False
    # The same figure a period ago, where a period ago means anything. Most of
    # these tiles are about now — how many cells are full, how many receipts
    # are unshelved — and the shop keeps no history of that, so they carry
    # null and
    # the screen draws no arrow. Orders today has yesterday.
    previous: int | None = None


class SalesPointOut(BaseModel):
    day: date
    orders: int
    total: int


class MoverOut(BaseModel):
    variant_id: int
    product_title: str
    variant_label: str
    qty: int


class DashboardOut(BaseModel):
    """The first screen: the figures, the fortnight, and what is moving.

    ``headlines`` was added because every trend on the dashboard was being
    computed in the browser from the last two points of ``sales`` — which
    answers "today against yesterday" and nothing else, gets the answer wrong
    before midday when today is half over, and puts the definition of the
    shop's own revenue in a React component. The figures now arrive with their
    comparison already made, over three windows, by the same code the reports
    use. ``sales`` and ``tiles`` are unchanged: the nav badges and several
    screens read the tile keys.
    """

    tiles: list[DashboardTileOut]
    sales: list[SalesPointOut]
    movers: list[MoverOut]
    headlines: list[FigureOut] = []


class WriteOffIn(BaseModel):
    """Goods that are gone: damaged, lost, spoiled.

    A reason is required for the same reason it is on a stocktake correction —
    stock that left without one is indistinguishable from stock that was
    stolen.
    """

    variant_id: int
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------- admin


class GapOut(BaseModel):
    """One reason a card is not in the shop: the key and the words.

    Both, because the two readers want different things. The publishing screen
    branches on ``key`` to decide which control to put in front of somebody —
    a category picker, a price field, a camera — and shows ``label``, which is
    the server's wording in the reader's language, so that the browser is not
    keeping its own copy of a rule or a translation.
    """

    key: str
    label: str


class AdminProductOut(BaseModel):
    """A card as the person who owns the catalogue sees it."""

    id: int
    sku: str
    title: str
    subtitle: str
    kind: str
    status: ProductStatus
    next_statuses: list[ProductStatus]
    # Absent on a card still waiting to be filed and priced.
    category_slug: str | None
    brand_slug: str | None
    snapshot_url: str
    # Why this card is not in the shop. Empty means it is ready, whether or
    # not anybody has published it yet.
    unready: list[GapOut] = []
    # What it is missing to read like a shop rather than a stub. Not a gate:
    # a card with one photograph and no prose still sells, and holding it back
    # until the writing is done is how nothing goes on sale.
    listing_gaps: list[GapOut] = []
    price: int
    old_price: int | None
    # What these last cost at the market, from the most recent market run that
    # named any of this card's cells. The publishing screen offers a markup
    # against it, because "+75%" is how the person who bought them thinks — and
    # they wrote the cost at the bench with the sack open, which is the only
    # moment anybody knew it.
    last_cost: int = 0
    stock_left: int
    # The cells of this card that are empty — `Qora`, or `Qora / 42`. A card
    # is rarely out of stock as a whole; one colour of it is, and that is the
    # one nobody notices until a customer orders it.
    sold_out: list[str] = []
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

    ``aliases`` is every spelling this row answers to, which is what a merge
    screen has to show: two rows are the same make when somebody recognises
    the words, and the words people actually typed are the only evidence there
    is. Deliberately not a similarity score — a number saying two brands are
    83% alike is a number nobody can check, and the decision it would be
    steering deletes a row.
    """

    id: int
    slug: str
    name: str
    product_count: int
    aliases: list[str] = []


class CatalogSummaryOut(BaseModel):
    """How many cards sit in each state.

    One query for a number the sidebar wants on every screen. The alternative
    is fetching the drafts themselves to count them, which is a page of cards
    fetched to display an integer.
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
    # Which colour this is a photograph of. Empty on a card with no colours,
    # where the picture is of the thing itself.
    colour: str = ""


class AdminVariantOut(BaseModel):
    """One cell of the grid, as the editor holds it.

    ``can_delete`` is the backend's own answer, from the same function the
    delete endpoint refuses with — not a rule copied into the browser that
    would drift from it. A panel that greys the button out and says why is
    telling the truth; one that lets somebody click and then shows a 409 has
    made them find out the hard way.
    """

    id: int
    colour: str
    colour_hex: str
    size: str
    label: str
    sku: str
    barcode: str
    price: int
    sort: int
    stock_left: int
    in_stock: bool
    # Out of the shop window without being erased: a size received by mistake
    # cannot be deleted — the ledger points at it — and would otherwise be
    # offered, struck through, for the life of the card.
    retired: bool = False
    can_delete: bool
    # An already-translated sentence, empty when it can be deleted.
    blocked_reason: str


class ColourIn(BaseModel):
    colour: str = Field(min_length=1, max_length=60)
    hex: str = Field(default="", max_length=9)


class VariantGridIn(BaseModel):
    """The colour × size matrix, in one step.

    Typing twelve variants by hand for every shoe model is how a warehouse
    stops being used, so the form takes the colours and the sizes and the grid
    is what comes back. Sending it again adds what is new and leaves what
    exists alone — a colour added in October must not renumber the barcodes
    printed in June.
    """

    colours: list[ColourIn] = Field(default_factory=list, max_length=40)
    sizes: list[str] = Field(default_factory=list, max_length=40)
    price: int = Field(default=0, ge=0)


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

    ``price`` is what the card is advertised at until it has priced variants,
    and ``app.products.refresh`` takes it over as soon as it has — the money
    itself is on the variant, because a 43 can cost more than a 41. Stock is
    absent on purpose: it comes from the movement ledger and is the
    warehouse's to move.
    """

    # Generated when absent. Market goods arrive with no usable code and
    # nobody at a receiving desk should be inventing one: a person asked to
    # think of "KRS-01" is a person who stops writing cards.
    sku: str = Field(default="", max_length=40)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = ""
    description: str = ""
    # The receiving desk's word for the goods — "Krossovka". Free text on
    # purpose: the vocabulary is learned from what has been received.
    kind: str = Field(default="", max_length=60)
    # Both optional, because a card written with the sack open has neither yet
    # and the goods still have to reach the shelf. ``app.products.unready``
    # names the gaps and ``status`` keeps the card out of the shop until they
    # are filled.
    category_slug: str | None = None
    brand_slug: str | None = None
    price: int = Field(default=0, ge=0)
    old_price: int | None = Field(None, gt=0)
    # The identification photograph, over the open sack. Not a catalogue
    # picture; see ``Product.snapshot_url``.
    snapshot_url: str = Field(default="", max_length=300)
    badge: str | None = None
    warranty: str | None = None
    is_original: bool = True
    free_delivery: bool = True
    next_day_delivery: bool = True
    # The Russian and English for this card, written with it. See TextIn.
    translations: dict[Lang, ProductTextIn] = Field(default_factory=dict)


class ProductUpdateIn(BaseModel):
    """Everything about a card except its price, its stock and its status.

    Those three have owners: the price belongs to the variants, the stock to
    the ledger, and the status to whether every colour has a photograph.
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


class ProductStatusIn(BaseModel):
    """Into the shop, or out of it.

    ``note`` lands in the audit log beside who moved it: a card taken out of
    the shop is a card that stops selling, and the sentence explaining why is
    what somebody reads in three months when they ask what happened to it.
    """

    status: ProductStatus
    note: str = ""


class CategoryWriteIn(BaseModel):
    slug: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    subtitle: str = ""
    icon: str = "box"
    image_url: str | None = None
    parent_slug: str | None = None
    sort: int = 0
    # True by default, and that is the fix for a hole rather than a preference:
    # the home screen's grid and the catalogue's own filter both read this, so
    # a category written with it false is a category nobody browsing the shop
    # can ever reach. The seller writes one while filing a card, which is the
    # moment they are least equipped to know that.
    is_quick_link: bool = True
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


class BrandMergeIn(BaseModel):
    """Which row survives the merge.

    The brand in the path is the one that disappears and this is the one that
    is left, because the request reads the way the sentence does: merge
    ``on-cloud`` **into** ``on-running``. Naming the survivor by slug and not
    by id so the call can be written from what the brand list already shows.
    """

    into: str = Field(min_length=1, max_length=60)


class BrandMergeOut(BaseModel):
    """What the merge did, in the two numbers somebody will want to check."""

    brand: BrandOut
    # How many cards changed hands. The figure the audit row carries, returned
    # as well because the screen that asked has to say something that is not
    # "done".
    products_moved: int
    # Every spelling the survivor now answers to, the loser's among them — so
    # it is visible that the duplicate cannot come back through the desk.
    aliases: list[str] = []


class ImageWriteIn(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    # Which colour this is a photograph of. A picture belongs to a colour, not
    # to a variant: two colours in six sizes is two pictures, not twelve.
    colour: str = Field(default="", max_length=60)
    sort: int = 0


class VariantWriteIn(BaseModel):
    """One cell of the grid, edited on its own.

    The grid itself is made in one step — see ``VariantGridIn`` — because
    typing twelve variants by hand for every shoe model is how a warehouse
    stops being used. This is for afterwards: repricing a size, correcting a
    colour's spelling, printing a label again.
    """

    colour: str = Field(default="", max_length=60)
    colour_hex: str = Field(default="", max_length=9)
    size: str = Field(default="", max_length=40)
    price: int = Field(default=0, ge=0)
    sort: int = 0


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


class StaffMemberOut(StaffUserOut):
    """A staff row, with the two things a directory is actually read for.

    ``email`` because the office writes to people. ``last_seen`` because the
    question asked of a staff list is nearly always "is this still somebody's
    account?" — a courier who left in March has a row that looks exactly like
    a courier who is out on a round.

    ``last_seen`` is **derived, not stored**: it is the newest refresh token
    the account still holds. One is written when they sign in and another on
    every renewal, so the timestamp tracks use rather than only the first
    login, and no column had to be added to ``users`` to get it. Null means
    nothing is outstanding — they have never signed in, or they signed out.
    """

    email: str | None = None
    last_seen: datetime | None = None


class StaffAppointIn(PhoneIn):
    """Putting somebody on the staff, by the only thing anybody knows: a number.

    The phone normalisation is inherited from ``PhoneIn`` rather than written
    again, so an admin typing ``901234567`` appoints the same person who later
    signs in as ``+998901234567``. Two spellings of one number would be two
    accounts, and the one they signed in to would be the empty one.

    The number need not exist yet. Somebody is hired on Monday and handed the
    app on Tuesday; until now there was no way to make the account before they
    first signed in, which is why staff were made with a shell script.
    """

    full_name: str = Field("", max_length=120)
    role: UserRole
    note: str = Field("", max_length=200)


class AdminUserWriteIn(BaseModel):
    """The two fields on somebody else's account an admin may correct.

    A name taken down wrong at the counter, and an email nobody can spell over
    the telephone. Not the role — that has its own door with the last-admin
    rule on it. Not the language, the notification switches or the PIN: those
    are the person's own settings, and an office that can quietly turn
    somebody's order notifications off is an office that gets blamed for the
    message that never arrived.

    Unset is unchanged, so a form that edits one field sends one field — and
    clearing an email is ``""``, which is a different statement from not
    mentioning it.
    """

    full_name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=120)


class ActiveWriteIn(BaseModel):
    """Somebody left, or somebody came back.

    Not a delete. Their orders, their addresses and every audit row naming
    them stay where they are — an account is the thread all of that hangs off,
    and deleting it would take the history of the shop with it. ``is_active``
    is checked on every request, so switching it off is the door that closes
    behind somebody.
    """

    active: bool
    note: str = Field("", max_length=200)


class CustomerRowOut(BaseModel):
    """A customer as the office sees them in a list.

    The four figures are what somebody reaches for before picking up the
    telephone: how often this person buys, what they have actually paid for,
    when they last did, and whether they are still using the app at all.

    ``spent`` counts delivered orders only. A placed order is a promise and a
    cancelled one is nothing; counting either would make the shop's keenest
    tyre-kicker its best customer.
    """

    id: int
    phone: str
    full_name: str
    email: str | None
    is_active: bool
    created_at: datetime
    orders_count: int
    spent: int
    last_order_at: datetime | None
    last_seen: datetime | None


class CustomerOrderOut(BaseModel):
    """One line of a customer's order history, short enough for a panel.

    Not ``OrderSummaryOut``: that carries the delivery wording, the payment
    label and the item thumbnails, which is a screen's worth of fetching per
    row, and this is ten rows drawn beside everything else about the person.
    """

    id: int
    code: str
    status: OrderStatus
    status_label: str
    total: int
    created_at: datetime


class CustomerDetailOut(CustomerRowOut):
    """Everything about one customer, on the screen somebody opens mid-call.

    Assembled in one response rather than left to the panel, because the
    alternative is six requests fired when a name is clicked while the person
    on the telephone waits through all of them.

    The cards carry the brand, the last four digits and whether they still
    work — never ``processor_token``, which is the only part of that row that
    can actually be charged and has no business leaving the server.

    The basket is here because it answers the commonest call there is: the
    thing they cannot check out is a line the office can now see, with the
    reason it is unavailable already worked out.
    """

    language: Language
    birth_date: date | None
    favorites_count: int
    addresses: list[AddressOut]
    cards: list[CardOut]
    orders: list[CustomerOrderOut]
    cart: list[CartItemOut]


class AuditRowOut(BaseModel):
    """One line of the trail, with the actor already resolved.

    Thirty-eight places in the code write these rows and nothing read them
    back, so the one question the table exists to answer — who changed this,
    and when — could only be answered with a database client on the server.

    The actor's name and number are joined on here rather than looked up per
    row by the panel: a page of fifty rows is two queries instead of
    fifty-one, and a screen that prints ids where people should be is a screen
    nobody reads. ``actor_role`` is off the row itself — the authority the
    change was made under, not whatever the person's role is today.
    """

    id: int
    created_at: datetime
    actor_id: int | None
    actor_name: str
    actor_phone: str
    actor_role: UserRole | None
    action: str
    entity: str
    entity_id: int | None
    field: str
    old_value: str | None
    new_value: str | None
    note: str


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
    """One return request, read by the office or by the warehouse.

    The inspection fields are the reason both read the same shape. A return
    is answered once after the money — whoever opened the parcel says what
    they found — and the shelf follows from that, so every screen involved
    needs to see the verdict to know whether there is anything left to do.
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

    product_title: str = ""

    inspection: ReturnInspection | None = None
    inspection_label: str = ""
    inspection_note: str = ""
    inspected_at: datetime | None = None
    relisted: bool = False


class ReturnInspectIn(BaseModel):
    """The warehouse's verdict on a parcel that came back.

    ``result`` has no default. Somebody has to look at the shirt, and a
    default here would be a verdict arrived at by pressing Save.
    """

    result: ReturnInspection
    note: str = ""


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


# --------------------------------------------------------------------------- reports

# The shapes behind `app.routers.reports`, which replaced a paged table of raw
# stock movements filed under the menu item an owner opens to see how the
# business is doing.
#
# Two decisions run through every model below.
#
# **Every headline carries the period before it.** "Oshishi pasayishi" — is it
# going up or down — is the whole question, and a figure without its twin makes
# the browser difference two numbers and hope it picked the right two. So a
# figure is a `FigureOut`: this period, last period, the difference, and the
# percentage where one exists.
#
# **A figure that lies is worse than a figure we do not show.** Where something
# is only partly knowable — margin on orders placed before the cost column
# existed — the coverage travels with it rather than being rounded away.


class ReportPeriodOut(BaseModel):
    """What was asked for, and what it is being compared against.

    Echoed back rather than assumed, because the previous period is chosen
    here — the same number of days, ending the day before this one starts —
    and a screen that printed "vs last month" without being told would be
    guessing at it.
    """

    from_day: date
    to_day: date
    previous_from_day: date
    previous_to_day: date
    days: int
    bucket: Literal["day", "week", "month"]


class SalesBucketOut(BaseModel):
    """One day, week or month of trade, named by the day it starts.

    ``revenue`` is bucketed by the day the goods were **delivered** and the
    counts by the day the order was **placed**, and the two are deliberately
    not the same axis — see the report's own docstring. A bucket with nothing
    in it is present rather than skipped: a chart that drops empty days draws a
    shop that was busy every day it was open.
    """

    day: date
    label: str
    orders: int = 0
    delivered: int = 0
    cancelled: int = 0
    returned: int = 0
    revenue: int = 0
    refunds: int = 0


class SplitRowOut(BaseModel):
    """Revenue cut one way — by payment method, or by how it was delivered."""

    key: str
    label: str
    orders: int
    revenue: int
    previous_orders: int
    previous_revenue: int


class SalesReportOut(BaseModel):
    """Trade over a period, with the period before it beside every figure."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    buckets: list[SalesBucketOut]
    by_payment: list[SplitRowOut]
    by_delivery: list[SplitRowOut]
    # Delivered orders with no `delivered` event to bucket by. Nought is the
    # expected answer and anything else means the revenue series is
    # understating itself by that many orders — so it is on the wire rather
    # than in a log, where the one person who could act on it would never see
    # it.
    delivered_without_a_time: int = 0


class MoneyBucketOut(BaseModel):
    """Cash in and cash out on one day, week or month.

    ``difference`` is exactly that — what came in less what went out — and is
    **not** profit. A market run that lands on the 3rd puts a month's buying
    into one day, so this swings hard and says nothing about whether the shop
    made money. Profit is the margin block, and only for the days it can see.
    """

    day: date
    label: str
    money_in: int = 0
    money_out: int = 0
    refunds: int = 0
    difference: int = 0


class MarketSpendOut(BaseModel):
    """What was spent at one market, over this period and the one before.

    ``place`` is free text off the run — nobody maintains a list of markets —
    so an empty one is a run somebody did not say where they went, and it is
    shown as itself rather than being folded into the others.
    """

    place: str
    runs: int
    units: int
    cost: int
    previous_cost: int


class BuyerSpendOut(BaseModel):
    """What one person spent at the market. The only party to a purchase there
    is — nobody delivers to this shop, so there is no supplier to rank."""

    buyer_id: int | None
    name: str
    runs: int
    cost: int
    previous_cost: int


class MarginOut(BaseModel):
    """Gross margin, and how much of the period it could actually see.

    The honest part of this whole exercise. ``revenue`` and ``cost`` cover
    **only the lines that carry a cost**, so the percentage between them is
    real; ``units_costed`` against ``units`` is what says how much of the
    period that was. A screen showing the percentage without the coverage
    beside it would read as the shop's margin when it may be the margin on four
    units out of nine hundred.

    ``known_from`` is the day the first order carrying a cost was placed.
    Everything before it is unknowable — not nought — because the column did
    not exist and no backfill can invent what a shirt sold in March cost
    without inventing it. Null means no order anywhere carries a cost yet, and
    the whole block should be drawn as "not yet".
    """

    revenue: int
    cost: int
    margin: int
    # Hundredths of a per cent, as `FigureOut.percent_value` describes. Null
    # when nothing costed was sold, because nought per cent is a claim.
    margin_percent: int | None
    units: int
    units_costed: int
    coverage_percent: int
    known_from: date | None


class MoneyReportOut(BaseModel):
    """The shop's cash shape, and — where it is knowable — its margin."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    buckets: list[MoneyBucketOut]
    by_market: list[MarketSpendOut]
    by_buyer: list[BuyerSpendOut]
    margin: MarginOut


class CustomerBucketOut(BaseModel):
    """Signups and buyers over one bucket, bucketed by when they happened."""

    day: date
    label: str
    signups: int = 0
    orders: int = 0
    first_orders: int = 0
    repeat_orders: int = 0


class CustomerRankOut(BaseModel):
    """One customer on a list somebody is going to act on.

    ``spent`` is delivered so'm over their whole life, not over the period: a
    call list is about who is worth ringing, and somebody who spent nine
    million last year and nothing this month is exactly who it is for.

    ``days_since`` is nought on the top-spender list, where it means nothing,
    and is the point of the lapsed list, where it is what makes the row a
    reason to pick up a telephone.
    """

    user_id: int
    name: str
    phone: str
    orders: int
    spent: int
    last_order_at: datetime | None
    days_since: int = 0


class CustomersReportOut(BaseModel):
    """Who is buying, who is coming back, and who has stopped."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    buckets: list[CustomerBucketOut]
    top_customers: list[CustomerRankOut]
    # Bought before, nothing since. The most useful thing on the screen,
    # because it is the only list here that is a list of things to do.
    lapsed: list[CustomerRankOut]
    lapsed_after_days: int


class ProductSaleOut(BaseModel):
    """Units and so'm for one card over the period, against the one before.

    Revenue per product is computable off `order_items` today and nothing in
    the back office shows it — a shop could see what moved and not what it was
    worth, which are different lists with different things at the top.
    """

    product_id: int | None
    title: str
    units: int
    revenue: int
    previous_units: int
    previous_revenue: int
    delta_units: int
    delta_revenue: int


class VariantSaleOut(BaseModel):
    """The same for one cell of the grid, with what is left of it.

    ``sell_through_percent`` is units sold in the period against those units
    plus what is on the shelf now — hundredths of a per cent. It mixes a flow
    with a snapshot on purpose: the question it answers is "did we buy too many
    of these", and the stock that is left is the half of that question the
    period cannot supply. Null when neither sold nor stocked.
    """

    variant_id: int
    product_id: int | None
    product_title: str
    variant_label: str
    units: int
    revenue: int
    previous_units: int
    stock_left: int
    sell_through_percent: int | None


class DeadStockOut(BaseModel):
    """On a shelf, and nobody has bought one for a long time.

    ``shelf_value`` is at the **selling** price, which is the figure that makes
    somebody act: what the shop paid is sunk, and what it is asking is what is
    standing still. Costed value is in the money report, where it belongs.
    """

    variant_id: int
    product_id: int | None
    product_title: str
    variant_label: str
    stock_left: int
    unit_price: int
    shelf_value: int
    last_delivered_at: datetime | None


class ProductsReportOut(BaseModel):
    """What sold, what is rising, what is falling, and what is not moving."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    products: list[ProductSaleOut]
    variants: list[VariantSaleOut]
    rising: list[ProductSaleOut]
    falling: list[ProductSaleOut]
    dead_stock: list[DeadStockOut]
    dead_after_days: int


class StockKindOut(BaseModel):
    """What is standing in one kind of place, and what it is worth.

    The genuinely valuable split. "The shop holds 94 million so'm of stock" is
    a number nobody can act on; "eleven million of it is in the damaged corner
    and four million is returns nobody has opened" is a morning's work.
    """

    kind: LocationKind
    label: str
    units: int
    value: int
    variants: int


class StocktakeOut(BaseModel):
    """How far the shelf had drifted, off the counts that were closed.

    Nothing surfaces this today, and it is the only measure of whether the
    ledger and the room agree. ``accuracy_percent`` is hundredths of a per
    cent: expected less the total miscount, over expected. Null when nothing
    was counted in the period, because a hundred per cent accuracy on nought
    lines is the most misleading number available here.
    """

    counts: int
    lines: int
    lines_wrong: int
    expected_units: int
    counted_units: int
    miscounted_units: int
    accuracy_percent: int | None


class StockReportOut(BaseModel):
    """What is in the building, where it is standing, and how right that is."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    by_kind: list[StockKindOut]
    cells: int
    cells_full: int
    cells_empty: int
    stocktake: StocktakeOut
    previous_stocktake: StocktakeOut


class CourierRowOut(BaseModel):
    """One courier's period: knocks, doors that opened, and cash in hand."""

    courier_id: int
    name: str
    phone: str
    attempts: int
    delivered: int
    failed: int
    # Hundredths of a per cent. Null when they knocked on no doors.
    success_percent: int | None
    cash_collected: int
    previous_delivered: int


class ReasonRowOut(BaseModel):
    """A free-text reason and how often it was given, commonest first.

    Ranked rather than totalled, because the action is always "deal with the
    top one". An empty reason is its own row: a failure recorded with no reason
    is a gap in the work, and folding it into the others hides it.
    """

    reason: str
    count: int
    previous: int
    # Hundredths of a per cent of this period's total.
    share_percent: int


class DurationOut(BaseModel):
    """How long a step of the work took, in minutes.

    Median as well as average, because one parcel that sat over a weekend
    moves an average and does not move a median — and the question ("how long
    does this normally take") is about the middle one. ``samples`` is how many
    it was measured over; a duration over three of them is not a fact about the
    shop and the screen is told so.
    """

    key: str
    label: str
    samples: int
    average_minutes: int | None
    median_minutes: int | None
    previous_average_minutes: int | None


class OperationsReportOut(BaseModel):
    """The work itself: the door, the bench, and what came back."""

    period: ReportPeriodOut
    headlines: list[FigureOut]
    couriers: list[CourierRowOut]
    failure_reasons: list[ReasonRowOut]
    return_reasons: list[ReasonRowOut]
    durations: list[DurationOut]
