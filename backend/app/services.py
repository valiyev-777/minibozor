"""Serialisation and the small amount of business logic the screens imply."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, col, func, select

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

FREE_DELIVERY_THRESHOLD = 250_000
STANDARD_DELIVERY_FEE = 19_000

UZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]
UZ_WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

ORDER_STATUS_LABELS = {
    OrderStatus.PLACED: "QABUL QILINDI",
    OrderStatus.PACKING: "YIG'ILMOQDA",
    OrderStatus.SHIPPED: "YO'LDA",
    OrderStatus.DELIVERED: "YETKAZILDI",
    OrderStatus.CANCELLED: "BEKOR QILINDI",
    OrderStatus.RETURNED: "QAYTARILDI",
}

ORDER_FLOW = [OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]

ORDER_EVENT_TITLES = {
    OrderStatus.PLACED: "Buyurtma qabul qilindi",
    OrderStatus.PACKING: "Omborda yig'ildi",
    OrderStatus.SHIPPED: "Kuryerga topshirildi",
    OrderStatus.DELIVERED: "Yetkazildi",
}


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
    return f"{d.day}-{UZ_MONTHS[d.month - 1]}"


def uz_weekday_label(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        return "Bugun"
    if d == today + timedelta(days=1):
        return "Ertaga"
    return UZ_WEEKDAYS[d.weekday()]


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
        title=p.title,
        price=p.price,
        old_price=p.old_price,
        discount_percent=p.discount_percent,
        image_url=primary_image(session, p.id),
        rating=round(p.rating, 1),
        reviews_count=p.reviews_count,
        badge=p.badge,
        in_stock=p.in_stock,
        is_favorite=p.id in favs,
    )


def product_cards(
    session: Session, products: list[Product], favs: set[int]
) -> list[s.ProductCardOut]:
    return [product_card(session, p, favs) for p in products]


def category_tree_ids(session: Session, root_id: int) -> list[int]:
    """A category and every descendant, so counts and listings agree."""
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        children = session.exec(
            select(Category.id).where(col(Category.parent_id).in_(frontier))
        ).all()
        if not children:
            break
        ids.extend(children)
        frontier = list(children)
    return ids


def category_product_count(session: Session, category_id: int) -> int:
    """Counted, never stored.

    A hand-maintained number drifts the moment stock changes, and showing
    "12 400 tovar" over an empty category is worse than showing nothing.
    """
    return session.exec(
        select(func.count())
        .select_from(Product)
        .where(col(Product.category_id).in_(category_tree_ids(session, category_id)))
    ).one()


def category_out(session: Session, c: Category) -> s.CategoryOut:
    has_children = session.exec(
        select(func.count()).select_from(Category).where(Category.parent_id == c.id)
    ).one() > 0
    return s.CategoryOut(
        id=c.id,
        slug=c.slug,
        name=c.name,
        subtitle=c.subtitle,
        icon=c.icon,
        image_url=media_url(c.image_url),
        product_count=category_product_count(session, c.id),
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

    note = "Ertaga yetkaziladi" if p.next_day_delivery else "2–3 kunda yetkaziladi"
    if p.free_delivery:
        note += " · bepul"

    return s.ProductOut(
        **card.model_dump(),
        sku=p.sku,
        subtitle=p.subtitle,
        description=p.description,
        images=[media_url(i.url) for i in images],
        category=category_out(session, category),
        brand=s.BrandOut(id=brand.id, slug=brand.slug, name=brand.name) if brand else None,
        variants=[
            s.VariantOut(id=v.id, kind=v.kind, label=v.label, value=v.value, in_stock=v.in_stock)
            for v in variants
        ],
        specs=[s.SpecOut(key=sp.key, value=sp.value) for sp in specs],
        seller=p.seller,
        warranty=p.warranty,
        stock_left=p.stock_left,
        is_original=p.is_original,
        free_delivery=p.free_delivery,
        next_day_delivery=p.next_day_delivery,
        delivery_note=note,
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
    return s.ReviewSummaryOut(rating=round(avg, 1), total=total, distribution=distribution)


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


def cart_item_out(session: Session, item: CartItem) -> s.CartItemOut | None:
    product = session.get(Product, item.product_id)
    if product is None:
        return None
    variant = session.get(ProductVariant, item.variant_id) if item.variant_id else None
    return s.CartItemOut(
        id=item.id,
        product_id=product.id,
        title=product.title,
        image_url=primary_image(session, product.id),
        variant_label=variant.label if variant else product.subtitle,
        unit_price=product.price,
        old_unit_price=product.old_price,
        quantity=item.quantity,
        selected=item.selected,
        in_stock=product.in_stock,
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
    label = "2 soat ichida" if sl.express else f"{sl.start_time} – {sl.end_time}"
    return s.SlotOut(
        id=sl.id,
        day=sl.day,
        start_time=sl.start_time,
        end_time=sl.end_time,
        label=label,
        note=sl.note,
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
        return "Yetkazildi"
    if o.status == OrderStatus.CANCELLED:
        return "Bekor qilindi"
    if o.delivery_kind.value == "pickup":
        return "Punktdan olish"
    if o.delivery_day is None:
        return "Yetkazish sanasi aniqlanmoqda"
    label = uz_weekday_label(o.delivery_day)
    window = f"{o.delivery_start} – {o.delivery_end}" if o.delivery_start else ""
    if label in ("Bugun", "Ertaga"):
        return f"{label} {window} orasida".strip()
    return f"{uz_date(o.delivery_day)} yetkaziladi"


def payment_label(session: Session, o: Order) -> str:
    if o.payment_method == PaymentMethod.CASH:
        return "Naqd pul · kuryerga"
    if o.payment_card_id:
        card = session.get(PaymentCard, o.payment_card_id)
        if card:
            return f"Karta ···· {card.last4} · {'to`landi' if o.paid else 'to`lanmagan'}"
    return "Karta"


def order_summary(session: Session, o: Order) -> s.OrderSummaryOut:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    return s.OrderSummaryOut(
        id=o.id,
        code=o.code,
        status=o.status,
        status_label=ORDER_STATUS_LABELS[o.status],
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
                title=e.title,
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
                title=ORDER_EVENT_TITLES[status],
                happened_at=order.created_at if status == OrderStatus.PLACED else None,
                sort=idx,
            )
        )


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
