"""Serialisation and the small amount of business logic the screens imply."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Integer
from sqlmodel import Session, col, func, select

from app import i18n
from app import products as pr
from app import schemas as s
from app import stock as st
from app import transitions as tr
from app.models import (
    Address,
    Brand,
    CartItem,
    Category,
    DeliveryAttempt,
    DeliverySlot,
    Favorite,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PickupPoint,
    Product,
    ProductImage,
    ProductSpec,
    ProductStatus,
    ProductVariant,
    User,
)

# Above the median basket, so delivery is a real line on a typical order and
# free on a large one. At 250 000 it was under a quarter of the median price in
# the catalogue, so all but the cheapest orders shipped free and the fee never
# appeared at all.
FREE_DELIVERY_THRESHOLD = 3_000_000
STANDARD_DELIVERY_FEE = 19_000

UZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]
UZ_WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

ORDER_FLOW = [OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]


def order_status_label(status: OrderStatus) -> str:
    return i18n.label(f"status_{status.value}")


def order_event_title(status: OrderStatus) -> str:
    """Derived from the status rather than read from the stored row.

    The timeline is written once when the order is placed, so a stored title
    would be stuck in whatever language the customer used that day.
    """
    return i18n.label(f"event_{status.value}")


# --------------------------------------------------------------------------- formatting


def media_url(path: str | None) -> str | None:
    """Media paths stay relative — e.g. ``products/gazelle.png``.

    The server has no idea how a client reaches it: an emulator uses 10.0.2.2, a
    USB-attached phone uses its own localhost through `adb reverse`, a simulator
    uses localhost, production uses a CDN. Each app prefixes its own base URL, so
    the same response works everywhere.
    """
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return path.lstrip("/")


def money(amount: int) -> str:
    """``1090000`` as ``1 090 000``.

    The apps format their own figures — every price they are sent is an
    integer. This is for the few strings the server writes as prose, where the
    number has to arrive already readable.
    """
    return f"{amount:,}".replace(",", "\u00a0")


def uz_date(d: date) -> str:
    """Kept under the old name; the wording follows the request's language."""
    return i18n.format_date(d)


def uz_weekday_label(d: date, today: date | None = None) -> str:
    return i18n.day_label(d, today)


def initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    if not parts:
        return "MB"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def short_name(name: str) -> str:
    """"Madina Karimova" -> "Madina K." — how the design shows review authors."""
    parts = [p for p in name.split() if p]
    if len(parts) < 2:
        return name or "Mijoz"
    return f"{parts[0]} {parts[1][0]}."


# --------------------------------------------------------------------------- catalog


def in_the_shop(stmt):
    """Narrow a product query to the cards that are actually in the shop.

    Every customer-facing path goes through this. A card that is a draft, in
    moderation, refused or withdrawn is not for sale, and a shopper who can
    find one has been shown something that does not exist yet — or does not
    exist any more, which is worse, because they may already own one.

    One function rather than a repeated ``where`` so that a new listing cannot
    be written that forgets: there is a test that walks every product-returning
    endpoint and holds them all to it.
    """
    return stmt.where(Product.status == ProductStatus.ACTIVE)


def is_in_the_shop(product: Product | None) -> bool:
    """The same question about one row we already have in hand."""
    return product is not None and product.status is ProductStatus.ACTIVE


def colour_image(session: Session, product_id: int, colour: str) -> str | None:
    """The first photograph of one colour of a card.

    A colour is chosen by looking at the thing, so a basket line for a black
    shirt showing the white cover photograph is a line the shopper does not
    recognise as theirs — and the first place they notice is the order, which
    is the worst place to be surprised. A card cannot leave ``draft`` while a
    colour of it is without a picture, but a draft's may be, so this answers
    ``None`` and the caller falls back to the product's cover.
    """
    if not colour:
        return None
    row = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product_id, ProductImage.colour == colour)
        .order_by(col(ProductImage.sort), col(ProductImage.id))
    ).first()
    return media_url(row.url) if row else None


def primary_image(session: Session, product_id: int) -> str | None:
    img = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(col(ProductImage.sort))
    ).first()
    return media_url(img.url) if img else None


def card_images(session: Session, product_id: int, limit: int = 4) -> list[str]:
    """Every photograph a card may swipe through, in the order they are stored.

    The first is the product's own; the rest are the ones the seed hung on it
    from the same shelf — the other three dials of the same watch, the other two
    Air Force 1s. A shopper deciding between four colours of one thing should
    not have to open four pages to see them.

    Capped, because a card is a card: four is what the eye counts as dots
    without reading them.
    """
    rows = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(col(ProductImage.sort))
    ).all()
    return [u for u in (media_url(r.url) for r in rows[:limit]) if u]


def favorite_ids(session: Session, user: User | None) -> set[int]:
    if user is None:
        return set()
    rows = session.exec(select(Favorite.product_id).where(Favorite.user_id == user.id)).all()
    return set(rows)


def product_card(
    session: Session,
    p: Product,
    favs: set[int],
    shelf: dict[int, int] | None = None,
) -> s.ProductCardOut:
    """One card. ``shelf`` is the page's stock figures, read once for all of
    them — a card holds no stock of its own, and asking per card is a query per
    row of every listing."""
    left = shelf[p.id] if shelf is not None and p.id in shelf else pr.on_shelf(session, p.id)
    return s.ProductCardOut(
        id=p.id,
        title=i18n.t(session, "product", p.id, "title", p.title),
        price=p.price,
        old_price=p.old_price,
        discount_percent=p.discount_percent,
        image_url=primary_image(session, p.id),
        images=card_images(session, p.id),
        rating=round(p.rating, 1),
        reviews_count=p.reviews_count,
        badge=i18n.t(session, "product", p.id, "badge", p.badge) if p.badge else None,
        in_stock=p.in_stock,
        is_favorite=p.id in favs,
        stock_left=left,
        has_variants=has_variants(session, p.id),
    )


def has_variants(session: Session, product_id: int) -> bool:
    return session.exec(
        select(func.count())
        .select_from(ProductVariant)
        .where(ProductVariant.product_id == product_id)
    ).one() > 0


def product_cards(
    session: Session, products: list[Product], favs: set[int]
) -> list[s.ProductCardOut]:
    shelf = pr.shelf_map(session, [p.id for p in products])
    return [product_card(session, p, favs, shelf) for p in products]


def category_out(session: Session, c: Category) -> s.CategoryOut:
    has_children = session.exec(
        select(func.count()).select_from(Category).where(Category.parent_id == c.id)
    ).one() > 0
    return s.CategoryOut(
        id=c.id,
        slug=c.slug,
        name=i18n.t(session, "category", c.id, "name", c.name),
        subtitle=i18n.t(session, "category", c.id, "subtitle", c.subtitle),
        icon=c.icon,
        image_url=media_url(c.image_url),
        # Left at zero, and the apps no longer print it.
        #
        # It used to be counted per category, and counting one meant walking
        # its whole subtree first: the catalogue root is 26 categories, so one
        # screen cost 26 tree walks and 26 COUNTs. Nobody picks a category by
        # how many things are in it, and a shopper who reads "3 tovar" as
        # "almost sold out" has been told something untrue. The field stays in
        # the response so an older build still decodes it.
        product_count=0,
        has_children=has_children,
    )


def brand_out(session: Session, b: Brand, product_count: int = 0) -> s.BrandOut:
    """A brand in the language asked for.

    Most brand names are the same in all three — a Latin-alphabet marque is
    read as itself — which is why the row's own name is the fallback and why
    nothing seeded carries a translation. The ones that are not are the local
    names, written in Uzbek on the row and spelt in Cyrillic by a Russian
    speaker; those are the rows an admin fills in.
    """
    return s.BrandOut(
        id=b.id,
        slug=b.slug,
        name=i18n.t(session, "brand", b.id, "name", b.name),
        product_count=product_count,
    )


def admin_product_out(session: Session, product: Product) -> s.AdminProductOut:
    """A card as the people who own the catalogue see it.

    Here rather than in the admin router because the receiving desk answers
    with one too: booking a pile in returns the card it went on, and that is
    the same card in the same shape.
    """
    # Both absent on a card the receiving desk wrote and nobody has filed yet.
    category = (
        session.get(Category, product.category_id) if product.category_id else None
    )
    brand = session.get(Brand, product.brand_id) if product.brand_id else None
    images = session.exec(
        select(func.count())
        .select_from(ProductImage)
        .where(ProductImage.product_id == product.id)
    ).one()
    variants = session.exec(
        select(func.count())
        .select_from(ProductVariant)
        .where(ProductVariant.product_id == product.id)
    ).one()
    return s.AdminProductOut(
        id=product.id,
        sku=product.sku,
        title=product.title,
        subtitle=product.subtitle,
        kind=product.kind,
        status=product.status,
        next_statuses=tr.next_states(tr.PRODUCT_TRANSITIONS, product.status),
        category_slug=category.slug if category else None,
        brand_slug=brand.slug if brand else None,
        snapshot_url=product.snapshot_url,
        unready=[
            s.GapOut(key=gap, label=i18n.label(gap))
            for gap in pr.unready(session, product.id)
        ],
        price=product.price,
        old_price=product.old_price,
        stock_left=pr.on_shelf(session, product.id),
        image_count=int(images),
        variant_count=int(variants),
        created_at=product.created_at,
    )


def product_out(session: Session, p: Product, favs: set[int]) -> s.ProductOut:
    card = product_card(session, p, favs)
    images = session.exec(
        select(ProductImage).where(ProductImage.product_id == p.id).order_by(col(ProductImage.sort))
    ).all()
    variants = session.exec(
        select(ProductVariant)
        .where(ProductVariant.product_id == p.id)
        .order_by(col(ProductVariant.sort))
    ).all()
    specs = session.exec(
        select(ProductSpec).where(ProductSpec.product_id == p.id).order_by(col(ProductSpec.sort))
    ).all()
    category = session.get(Category, p.category_id)
    brand = session.get(Brand, p.brand_id) if p.brand_id else None

    note = i18n.label("eta_next_day" if p.next_day_delivery else "eta_few_days")
    if p.free_delivery:
        note += i18n.label("eta_free_suffix")

    return s.ProductOut(
        # Without the card's own photographs: the product page carries the whole
        # gallery, uncapped, on the line below, and passing both hands the same
        # keyword twice.
        **card.model_dump(exclude={"images"}),
        sku=p.sku,
        subtitle=i18n.t(session, "product", p.id, "subtitle", p.subtitle),
        description=i18n.t(session, "product", p.id, "description", p.description),
        images=[media_url(i.url) for i in images],
        category=category_out(session, category),
        brand=brand_out(session, brand) if brand else None,
        colours=[
            s.ColourOut(
                colour=colour,
                hex=next(
                    (v.colour_hex for v in variants if v.colour == colour), ""
                ),
                image_url=colour_image(session, p.id, colour),
                in_stock=any(
                    v.in_stock for v in variants if v.colour == colour
                ),
            )
            for colour in pr.colours(session, p.id)
        ],
        variants=[
            s.VariantOut(
                id=v.id,
                colour=v.colour,
                size=v.size,
                label=variant_label(v),
                sku=v.sku,
                barcode=v.barcode,
                price=v.price or p.price,
                in_stock=v.in_stock,
                stock_left=st.sellable(session, v),
            )
            for v in variants
        ],
        specs=[
            s.SpecOut(
                key=i18n.t(session, "spec", sp.id, "key", sp.key),
                value=i18n.t(session, "spec", sp.id, "value", sp.value),
            )
            for sp in specs
        ],
        warranty=i18n.t(session, "product", p.id, "warranty", p.warranty) if p.warranty else None,
        is_original=p.is_original,
        free_delivery=p.free_delivery,
        next_day_delivery=p.next_day_delivery,
        delivery_note=note,
        sold_count=p.sold_count,
    )


# --------------------------------------------------------------------------- cart


def cart_items(session: Session, user: User) -> list[CartItem]:
    return session.exec(
        select(CartItem).where(CartItem.user_id == user.id).order_by(col(CartItem.created_at))
    ).all()


def variant_label(variant: ProductVariant) -> str:
    """"Qora · 42", or whichever half of it exists.

    One string, built in one place: a label assembled in the basket, in the
    order and again on a printed label is three chances for the same shoe to
    read three ways.
    """
    return " · ".join(part for part in (variant.colour, variant.size) if part)


def unit_price(product: Product, variant: ProductVariant | None):
    """What one of the thing actually chosen costs.

    The money is on the variant — a 43 can cost more than a 41 — and the
    card's own price is the cheapest of them, which is what a shopper who has
    chosen nothing yet is shown.
    """
    if variant is not None and variant.price > 0:
        return variant.price, product.old_price
    return product.price, product.old_price


def cart_item_out(session: Session, item: CartItem) -> s.CartItemOut | None:
    product = session.get(Product, item.product_id)
    if product is None:
        return None
    variant = session.get(ProductVariant, item.variant_id) if item.variant_id else None

    price, old_unit_price = unit_price(product, variant)
    # This shopper's own hold does not count against them: the line they are
    # looking at is the reason the goods are held.
    left = pr.shelf_left(
        session,
        product,
        item.variant_id,
        for_user_id=item.user_id,
    )
    available = left > 0

    # A card withdrawn from the shop cannot be bought, whatever the shelf says.
    # The line stays in the basket and reads as unavailable rather than
    # disappearing: the shopper put it there, and a basket that quietly loses
    # a row is a basket nobody trusts.
    if not is_in_the_shop(product):
        available = False

    label = variant_label(variant) if variant else ""
    return s.CartItemOut(
        id=item.id,
        product_id=product.id,
        title=i18n.t(session, "product", product.id, "title", product.title),
        # The colour's own photograph when the line has a colour, because that
        # is the thing in the basket. The product's cover is the fallback.
        image_url=(
            colour_image(session, product.id, variant.colour) if variant else None
        )
        or primary_image(session, product.id),
        variant_label=label
        or i18n.t(session, "product", product.id, "subtitle", product.subtitle),
        variant_id=item.variant_id,
        unit_price=price,
        old_unit_price=old_unit_price,
        quantity=item.quantity,
        selected=item.selected,
        in_stock=available,
        stock_left=left,
        line_total=price * item.quantity,
    )


def promo_discount(session: Session, code: str | None, subtotal: int) -> tuple[int, str | None]:
    """No code is valid, because there are no codes.

    ``PromoCode`` went with the panels rebuild — there was no screen that
    wrote one and none is planned in this pass — but the *shape* stays: the
    cart still accepts a ``promo_code`` and still answers with a discount and
    a code, because the shipped apps send and read both. So every code is
    simply unrecognised, which is a thing the cart screen already knew how to
    say, and nothing above this function had to change.

    Bringing discounts back means giving this function a table to look in
    again, and nothing else.
    """
    return 0, None


def cart_totals(
    items: list[s.CartItemOut],
    *,
    discount: int = 0,
    promo_code: str | None = None,
    delivery_fee: int | None = None,
) -> s.CartTotalsOut:
    selected = [i for i in items if i.selected and i.in_stock]
    subtotal = sum(i.line_total for i in selected)
    if delivery_fee is None:
        free = subtotal >= FREE_DELIVERY_THRESHOLD or subtotal == 0
        delivery_fee = 0 if free else STANDARD_DELIVERY_FEE
    total = max(subtotal - discount, 0) + delivery_fee
    return s.CartTotalsOut(
        items_count=sum(i.quantity for i in selected),
        subtotal=subtotal,
        discount=discount,
        delivery_fee=delivery_fee,
        total=total,
        free_delivery_threshold=FREE_DELIVERY_THRESHOLD,
        promo_code=promo_code,
    )


def build_cart(session: Session, user: User, promo_code: str | None = None) -> s.CartOut:
    raw = [cart_item_out(session, i) for i in cart_items(session, user)]
    items = [i for i in raw if i is not None]
    subtotal = sum(i.line_total for i in items if i.selected and i.in_stock)
    discount, code = promo_discount(session, promo_code, subtotal)
    return s.CartOut(items=items, totals=cart_totals(items, discount=discount, promo_code=code))


# --------------------------------------------------------------------------- delivery


def address_out(a: Address) -> s.AddressOut:
    return s.AddressOut(
        id=a.id,
        title=a.title,
        icon=a.icon,
        badge=a.badge,
        line=a.line,
        city=a.city,
        meta=a.meta,
        floor=a.floor,
        apartment=a.apartment,
        entrance_code=a.entrance_code,
        comment=a.comment,
        latitude=a.latitude,
        longitude=a.longitude,
        is_default=a.is_default,
    )


def pickup_out(p: PickupPoint) -> s.PickupPointOut:
    return s.PickupPointOut(
        id=p.id, name=p.name, address=p.address, hours=p.hours, distance_km=p.distance_km
    )


def slot_out(sl: DeliverySlot) -> s.SlotOut:
    label = (
        i18n.label("slot_express") if sl.express
        else f"{sl.start_time} – {sl.end_time}"
    )
    return s.SlotOut(
        id=sl.id,
        day=sl.day,
        start_time=sl.start_time,
        end_time=sl.end_time,
        label=label,
        note=i18n.slot_note(sl.note),
        price=sl.price,
        express=sl.express,
        available=sl.capacity_left > 0,
    )


# --------------------------------------------------------------------------- orders


def order_eta_label(o: Order) -> str:
    if o.status == OrderStatus.DELIVERED:
        return i18n.label("delivered")
    if o.status == OrderStatus.CANCELLED:
        return i18n.label("cancelled")
    if o.delivery_kind.value == "pickup":
        return i18n.label("pickup")
    if o.delivery_day is None:
        return i18n.label("eta_pending")
    day = uz_weekday_label(o.delivery_day)
    window = f"{o.delivery_start} – {o.delivery_end}" if o.delivery_start else ""
    if day in (i18n.label("today"), i18n.label("tomorrow")):
        return i18n.label("between", label=day, window=window).strip()
    return i18n.label("delivered_on", date=uz_date(o.delivery_day))


def payment_label(session: Session, o: Order) -> str:
    if o.payment_method == PaymentMethod.CASH:
        return i18n.label("cash_courier")
    return i18n.label("card")


def order_summary(session: Session, o: Order) -> s.OrderSummaryOut:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    return s.OrderSummaryOut(
        id=o.id,
        code=o.code,
        status=o.status,
        status_label=order_status_label(o.status),
        total=o.total,
        items_count=sum(i.quantity for i in items),
        preview_images=[media_url(i.image_url) for i in items[:3] if i.image_url],
        eta_label=order_eta_label(o),
        created_at=o.created_at,
        can_cancel=o.status in (OrderStatus.PLACED, OrderStatus.PACKING),
        can_track=o.status in (OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED),
    )


def order_out(session: Session, o: Order, *, with_attempts: bool = False) -> s.OrderOut:
    """One order, in the shape both the customer and staff read.

    ``with_attempts`` is off by default: the doors a courier knocked on are
    staff's business, and a customer's own timeline already says the order is
    on its way. An operator asks it on, because deciding whether to give up on
    a delivery is exactly the decision the list of knocks exists for.
    """
    summary = order_summary(session, o)
    items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    events = session.exec(
        select(OrderEvent).where(OrderEvent.order_id == o.id).order_by(col(OrderEvent.sort))
    ).all()
    return s.OrderOut(
        **summary.model_dump(),
        delivery_kind=o.delivery_kind,
        address_line=o.address_line,
        address_meta=o.address_meta,
        delivery_day=o.delivery_day,
        delivery_start=o.delivery_start,
        delivery_end=o.delivery_end,
        payment_method=o.payment_method,
        payment_label=payment_label(session, o),
        paid=o.paid,
        recipient_name=o.recipient_name,
        recipient_phone=o.recipient_phone,
        subtotal=o.subtotal,
        delivery_fee=o.delivery_fee,
        discount=o.discount,
        items=[
            s.OrderItemOut(
                id=i.id,
                product_id=i.product_id,
                title=i.title,
                image_url=media_url(i.image_url) or "",
                variant_label=i.variant_label,
                unit_price=i.unit_price,
                quantity=i.quantity,
                line_total=i.line_total,
                reviewed=i.reviewed,
            )
            for i in items
        ],
        events=[
            s.OrderEventOut(
                status=e.status,
                title=order_event_title(e.status),
                happened_at=e.happened_at,
                note=e.note,
                done=e.happened_at is not None,
            )
            for e in events
        ],
        attempts=_attempts_out(session, o) if with_attempts else [],
    )


# Where the order numbers start. Chosen so the first order of a fresh
# deployment does not look like the first order ever placed.
ORDER_CODE_BASE = 104_688


def _attempts_out(session: Session, o: Order) -> list[s.DeliveryAttemptOut]:
    """Every knock at this order's door, oldest first, with the courier named.

    Named rather than numbered: an operator ringing a customer to ask what
    happened wants to know which of their couriers to ask next, and a
    ``courier_id`` is not something anybody says out loud.
    """
    rows = session.exec(
        select(DeliveryAttempt)
        .where(DeliveryAttempt.order_id == o.id)
        .order_by(col(DeliveryAttempt.happened_at))
    ).all()
    if not rows:
        return []
    names = {
        user.id: user.full_name
        for user in session.exec(
            select(User).where(col(User.id).in_({row.courier_id for row in rows}))
        ).all()
    }
    return [
        s.DeliveryAttemptOut(
            id=row.id,
            order_id=row.order_id,
            order_code=o.code,
            courier_name=names.get(row.courier_id, ""),
            result=row.result,
            reason=row.reason,
            recipient_name=row.recipient_name,
            photo_url=media_url(row.photo_url) or "",
            cash_collected=row.cash_collected,
            happened_at=row.happened_at,
        )
        for row in rows
    ]


def next_order_code(session: Session) -> str:
    """One past the highest code issued, not one past the number of orders.

    It used to be ``base + count + 1``, which is right only while every code
    ever issued is contiguous — and the seeded catalogue's are not: it writes
    ``#A-104512``, ``#A-104688``, ``#A-104692``, ``#A-104693`` and
    ``#A-104729``. So on the fortieth order the count reached 104729, a code
    already taken, and the insert failed on the unique index. That is the
    164th order this system would ever have accepted, and it would have
    failed in a customer's checkout.

    Read off the maximum instead, so a gap in the sequence costs a number
    rather than a collision. Done in SQL because it runs in every checkout;
    a non-numeric tail casts to nought in SQLite, which is harmless.
    """
    highest = session.exec(
        select(func.max(func.cast(func.substr(Order.code, 4), Integer)))
    ).one()
    return f"#A-{max(int(highest or 0), ORDER_CODE_BASE) + 1}"


def seed_order_events(session: Session, order: Order) -> None:
    """Create the full timeline up front; ``done`` is derived from the status."""
    for idx, status in enumerate(ORDER_FLOW):
        session.add(
            OrderEvent(
                order_id=order.id,
                status=status,
                title="",   # rendered from the status at read time
                happened_at=order.created_at if status == OrderStatus.PLACED else None,
                sort=idx,
            )
        )


def stamp_order_event(session: Session, order: Order, note: str = "") -> OrderEvent:
    """Mark the order's current status as having happened, now.

    The four steps of the flow are written as blank rows when the order is
    placed, so reaching one is a matter of filling in its time. Cancelled and
    returned have no row waiting — they are not steps on the way to anywhere —
    so they are appended when they occur, and the timeline ends where the
    order actually ended.
    """
    row = session.exec(
        select(OrderEvent).where(
            OrderEvent.order_id == order.id, OrderEvent.status == order.status
        )
    ).first()
    if row is None:
        last = session.exec(
            select(func.max(OrderEvent.sort)).where(OrderEvent.order_id == order.id)
        ).one()
        row = OrderEvent(
            order_id=order.id,
            status=order.status,
            title="",   # rendered from the status at read time
            sort=(last if last is not None else -1) + 1,
        )
    row.happened_at = utcnow()
    if note:
        row.note = note
    session.add(row)
    return row


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
