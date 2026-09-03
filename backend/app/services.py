"""Serialisation and the small amount of business logic the screens imply."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Session, col, func, select

from app import i18n
from app import schemas as s
from app.models import (
    Address,
    Brand,
    CartItem,
    Category,
    DeliverySlot,
    Favorite,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentCard,
    PaymentMethod,
    PickupPoint,
    Product,
    ProductImage,
    ProductSpec,
    ProductVariant,
    PromoCode,
    Review,
    ReviewLike,
    ReviewStatus,
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


def primary_image(session: Session, product_id: int) -> str | None:
    img = session.exec(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(col(ProductImage.sort))
    ).first()
    return media_url(img.url) if img else None


def favorite_ids(session: Session, user: User | None) -> set[int]:
    if user is None:
        return set()
    rows = session.exec(select(Favorite.product_id).where(Favorite.user_id == user.id)).all()
    return set(rows)


def product_card(session: Session, p: Product, favs: set[int]) -> s.ProductCardOut:
    return s.ProductCardOut(
        id=p.id,
        title=i18n.t(session, "product", p.id, "title", p.title),
        price=p.price,
        old_price=p.old_price,
        discount_percent=p.discount_percent,
        image_url=primary_image(session, p.id),
        rating=round(p.rating, 1),
        reviews_count=p.reviews_count,
        badge=i18n.t(session, "product", p.id, "badge", p.badge) if p.badge else None,
        in_stock=p.in_stock,
        is_favorite=p.id in favs,
        stock_left=p.stock_left,
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
    return [product_card(session, p, favs) for p in products]


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
        **card.model_dump(),
        sku=p.sku,
        subtitle=i18n.t(session, "product", p.id, "subtitle", p.subtitle),
        description=i18n.t(session, "product", p.id, "description", p.description),
        images=[media_url(i.url) for i in images],
        category=category_out(session, category),
        brand=s.BrandOut(id=brand.id, slug=brand.slug, name=brand.name) if brand else None,
        variants=[
            s.VariantOut(
                id=v.id,
                kind=v.kind,
                label=i18n.t(session, "variant", v.id, "label", v.label),
                value=v.value,
                image_url=media_url(v.image_url),
                in_stock=v.in_stock,
                stock_left=v.stock_left,
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
        seller=p.seller,
        warranty=i18n.t(session, "product", p.id, "warranty", p.warranty) if p.warranty else None,
        is_original=p.is_original,
        free_delivery=p.free_delivery,
        next_day_delivery=p.next_day_delivery,
        delivery_note=note,
        sold_count=p.sold_count,
    )


# --------------------------------------------------------------------------- reviews


def review_out(
    session: Session,
    r: Review,
    *,
    viewer: User | None = None,
    with_product: bool = False,
) -> s.ReviewOut:
    author = session.get(User, r.user_id)
    name = short_name(author.full_name) if author and author.full_name else "Mijoz"
    liked = False
    if viewer:
        liked = session.exec(
            select(ReviewLike).where(
                ReviewLike.review_id == r.id, ReviewLike.user_id == viewer.id
            )
        ).first() is not None

    product = None
    if with_product:
        p = session.get(Product, r.product_id)
        if p:
            product = product_card(session, p, favorite_ids(session, viewer))

    return s.ReviewOut(
        id=r.id,
        author_name=name,
        author_initials=initials(author.full_name if author else ""),
        rating=r.rating,
        text=r.text,
        variant_label=r.variant_label,
        tags=list(r.tags or []),
        photos=[media_url(p) for p in (r.photos or [])],
        likes=r.likes,
        liked_by_me=liked,
        status=r.status,
        created_at=r.created_at,
        product=product,
    )


def review_summary(session: Session, product_id: int) -> s.ReviewSummaryOut:
    reviews = session.exec(
        select(Review).where(
            Review.product_id == product_id, Review.status == ReviewStatus.PUBLISHED
        )
    ).all()
    total = len(reviews)
    counts = {n: 0 for n in range(1, 6)}
    for r in reviews:
        counts[r.rating] = counts.get(r.rating, 0) + 1
    avg = sum(r.rating for r in reviews) / total if total else 0.0
    distribution = [
        s.RatingBucket(
            stars=n,
            count=counts[n],
            percent=round(counts[n] / total * 100) if total else 0,
        )
        for n in range(5, 0, -1)
    ]
    # Every published photograph, newest first, capped at what a strip can show.
    # The count is of photographs rather than of reviews carrying them: the tile
    # says "+60", and 60 pictures across 20 reviews is still 60 pictures.
    photos = [
        media_url(url)
        for r in sorted(reviews, key=lambda r: r.created_at, reverse=True)
        for url in r.photos
    ]
    return s.ReviewSummaryOut(
        rating=round(avg, 1),
        total=total,
        distribution=distribution,
        photos=[u for u in photos[:9] if u],
        photos_total=len([u for u in photos if u]),
    )


def recalc_product_rating(session: Session, product_id: int) -> None:
    summary = review_summary(session, product_id)
    product = session.get(Product, product_id)
    if product:
        product.rating = summary.rating
        product.reviews_count = summary.total
        session.add(product)


# --------------------------------------------------------------------------- cart


def cart_items(session: Session, user: User) -> list[CartItem]:
    return session.exec(
        select(CartItem).where(CartItem.user_id == user.id).order_by(col(CartItem.created_at))
    ).all()


def shelf_left(
    product: Product,
    color: ProductVariant | None,
    size: ProductVariant | None = None,
) -> int:
    """
    How many of the thing actually chosen are left.

    A cart line is for one colour in one size, not for the product, so the
    stepper's ceiling and the page's count are the smallest shelf the choice
    stands on. Colours and sizes are counted apart from the same total rather
    than as a grid, so the honest answer for a pair of them is whichever is
    scarcer — never more than either. Falls back to the whole shelf for a
    variant nobody counted.
    """
    counted = [v.stock_left for v in (color, size) if v is not None and v.stock_left is not None]
    return min(counted) if counted else product.stock_left


def cart_item_out(session: Session, item: CartItem) -> s.CartItemOut | None:
    product = session.get(Product, item.product_id)
    if product is None:
        return None
    color = session.get(ProductVariant, item.color_variant_id) if item.color_variant_id else None
    size = session.get(ProductVariant, item.variant_id) if item.variant_id else None
    labels = [
        i18n.t(session, "variant", v.id, "label", v.label)
        for v in (color, size)
        if v is not None
    ]
    return s.CartItemOut(
        id=item.id,
        product_id=product.id,
        title=i18n.t(session, "product", product.id, "title", product.title),
        image_url=primary_image(session, product.id),
        variant_label=" · ".join(labels)
        if labels
        else i18n.t(session, "product", product.id, "subtitle", product.subtitle),
        unit_price=product.price,
        old_unit_price=product.old_price,
        quantity=item.quantity,
        selected=item.selected,
        in_stock=product.in_stock
        and (color is None or color.in_stock)
        and (size is None or size.in_stock),
        stock_left=shelf_left(product, color, size),
        line_total=product.price * item.quantity,
    )


def promo_discount(session: Session, code: str | None, subtotal: int) -> tuple[int, str | None]:
    if not code:
        return 0, None
    promo = session.exec(
        select(PromoCode).where(PromoCode.code == code.upper(), PromoCode.active.is_(True))
    ).first()
    if promo is None or subtotal < promo.min_total:
        return 0, None
    discount = promo.amount_off + round(subtotal * promo.percent_off / 100)
    return min(discount, subtotal), promo.code


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


def card_out(c: PaymentCard) -> s.CardOut:
    return s.CardOut(
        id=c.id,
        brand=c.brand,
        last4=c.last4,
        holder=c.holder,
        expiry=f"{c.expiry_month:02d}/{str(c.expiry_year)[-2:]}",
        status=c.status,
        is_default=c.is_default,
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
    if o.payment_card_id:
        card = session.get(PaymentCard, o.payment_card_id)
        if card:
            state = i18n.label("paid" if o.paid else "unpaid")
            return i18n.label("card_masked", last4=card.last4, state=state)
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


def order_out(session: Session, o: Order) -> s.OrderOut:
    summary = order_summary(session, o)
    items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    events = session.exec(
        select(OrderEvent).where(OrderEvent.order_id == o.id).order_by(col(OrderEvent.sort))
    ).all()
    reached = ORDER_FLOW.index(o.status) if o.status in ORDER_FLOW else len(ORDER_FLOW)
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
                done=(e.status in ORDER_FLOW and ORDER_FLOW.index(e.status) <= reached),
            )
            for e in events
        ],
    )


def next_order_code(session: Session) -> str:
    last = session.exec(select(func.count()).select_from(Order)).one()
    return f"#A-{104_688 + last + 1}"


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


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
