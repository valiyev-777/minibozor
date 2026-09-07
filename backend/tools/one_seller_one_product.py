"""Narrow the shop to one seller and one product, without losing anything.

    .venv/bin/python -m tools.one_seller_one_product            # dry run
    .venv/bin/python -m tools.one_seller_one_product --apply

The seeded shop is 35 products across two "sellers" named after markets —
"Mini Bozor", which is the platform, and "Chorsu Bozori". Neither is a shop.
For testing the whole line end to end what is wanted is one real seller with
one real product, so every screen shows the thing under test and nothing else.

**Archived, never deleted.** Seven of those products have orders against them
and the ledger has a hundred and fourteen movements. Deleting them would take
the order history with it, and with the history goes the ability to test the
courier's round, a return, or a payout — the flows that need an order that
already happened. ``archived`` is the state that means "withdrawn from the
shop, and the orders that named it survive": every customer path is narrowed
to ``published``, so an archived product is invisible to a shopper and intact
to a statement.

What it does, in order:

1. renames the seller that has an account to a shop name, and stands the
   platform's own "Mini Bozor" seller down — its offers go with it, which is
   what standing a seller down means;
2. archives every published product except the one t-shirt;
3. makes sure that t-shirt is what it should be: two colours, five sizes each,
   with stock on every cell.

Step 3 goes through the same doors everything else does — ``app.stock.move``
for a count, ``offers.refresh`` for the cached figures. Nothing here assigns
to ``stock_left``.

Idempotent: run it twice and the second run reports that there is nothing to
do.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, col, func, select

from app import offers as of
from app import stock as st
from app.core.config import settings
from app.db import engine, require_current_schema
from app.models import (
    Offer,
    OfferVariant,
    Product,
    ProductStatus,
    ProductVariant,
    Seller,
    StockMovementKind,
    User,
    UserRole,
    VariantKind,
)

# The shop's name. Not a market: a seller is a shop, and naming one after the
# bazaar it stands in is what made "Chorsu Bozori" read as a place rather than
# as somebody who sells.
SHOP = "Anvar Tekstil"

# The product everything is tested on, and the grid it has.
KEEP_SKU_HINT = "futbolka"
COLOURS: tuple[tuple[str, str], ...] = (("Oq", "#FFFFFF"), ("Qora", "#111113"))
SIZES: tuple[tuple[str, int, int], ...] = (
    # size, white stock, black stock — different on purpose, so a test that
    # reads the wrong cell reads an obviously wrong number.
    ("S", 12, 9),
    ("M", 18, 14),
    ("L", 15, 11),
    ("XL", 8, 6),
    ("XXL", 4, 3),
)


def _house(session: Session) -> Seller | None:
    return session.exec(select(Seller).where(Seller.name == "Mini Bozor")).first()


def _shop(session: Session) -> Seller | None:
    """The seller with a real account behind it — the one a person signs in as."""
    return session.exec(
        select(Seller).where(col(Seller.user_id).is_not(None))
    ).first()


def _keeper(session: Session) -> Product | None:
    """The t-shirt to keep: the one with the most sizes already on it.

    Chosen by shape rather than by id, so this does not depend on the seed
    happening to put it at a particular row.
    """
    best: tuple[int, Product] | None = None
    for product in session.exec(
        select(Product).where(Product.status == ProductStatus.PUBLISHED)
    ).all():
        if KEEP_SKU_HINT not in product.title.lower():
            continue
        sizes = session.exec(
            select(func.count())
            .select_from(ProductVariant)
            .where(
                ProductVariant.product_id == product.id,
                ProductVariant.kind == VariantKind.SIZE,
            )
        ).one()
        if best is None or int(sizes) > best[0]:
            best = (int(sizes), product)
    return best[1] if best else None


def plan(session: Session) -> list[str]:
    out: list[str] = []
    shop, house, keep = _shop(session), _house(session), _keeper(session)

    if shop is None:
        out.append("! no seller has an account behind it — run tools.dev_accounts first")
        return out
    if keep is None:
        out.append("! no published t-shirt found to keep")
        return out

    out.append(
        f"seller {shop.id}: {shop.name!r} → {SHOP!r}"
        if shop.name != SHOP
        else f"seller {shop.id}: already {SHOP!r}"
    )
    if house is not None and house.active:
        offers = session.exec(
            select(func.count()).select_from(Offer).where(Offer.seller_id == house.id)
        ).one()
        out.append(f"stand down {house.name!r} and withdraw its {int(offers)} offer(s)")

    doomed = [
        p
        for p in session.exec(
            select(Product).where(Product.status == ProductStatus.PUBLISHED)
        ).all()
        if p.id != keep.id
    ]
    out.append(f"archive {len(doomed)} published product(s), keep {keep.title!r}")

    # Offers the archiving above will leave pointing at nothing a shopper can
    # reach. Counted here from what archiving is about to do rather than from
    # the current state, so the plan matches what apply will actually change.
    doomed_ids = {p.id for p in doomed}
    orphans = [
        offer
        for offer in session.exec(select(Offer).where(Offer.active)).all()
        if offer.product_id in doomed_ids
        or (
            (product := session.get(Product, offer.product_id)) is None
            or product.status is not ProductStatus.PUBLISHED
        )
    ]
    if orphans:
        out.append(
            f"withdraw {len(orphans)} offer(s) left on products out of the shop — "
            "otherwise the cabinet lists prices for goods nobody can buy"
        )

    out.append(f"give {keep.title!r} 2 colours × 5 sizes with stock on every cell")
    return out


def apply(session: Session, actor: User) -> None:
    shop, house, keep = _shop(session), _house(session), _keeper(session)
    if shop is None or keep is None:
        raise SystemExit("nothing to do — see the dry run")

    # 1. A shop with a name.
    if shop.name != SHOP:
        shop.name = SHOP
        session.add(shop)

    # 2. The platform's own seller stands down. Its offers go with it, which is
    #    what standing a seller down means — otherwise the cheapest card in the
    #    shop could belong to somebody who no longer sells.
    if house is not None and house.active:
        house.active = False
        session.add(house)
        touched: set[int] = set()
        for offer in session.exec(
            select(Offer).where(Offer.seller_id == house.id)
        ).all():
            if offer.active:
                offer.active = False
                session.add(offer)
                touched.add(offer.product_id)
        session.commit()
        for product_id in touched:
            of.refresh(session, product_id)
        session.commit()

    # 3. Everything else out of the shop. Archived, so the orders that named it
    #    still resolve and the ledger still explains its own totals.
    for product in session.exec(
        select(Product).where(Product.status == ProductStatus.PUBLISHED)
    ).all():
        if product.id == keep.id:
            continue
        product.status = ProductStatus.ARCHIVED
        product.in_stock = False
        session.add(product)
    session.commit()

    # 3b. And every offer left pointing at something no longer in the shop.
    #
    #     Step 2 stood down the house seller's offers because standing down a
    #     seller means standing down what they sell. It did not touch the
    #     kept seller's, and after step 3 seven of those named products that
    #     had just been archived. The shop was clean and the cabinet was not:
    #     "Narxlarim" and "Qoldiq" each listed eight rows, seven of them
    #     figures for goods a shopper cannot reach. That is the same confusion
    #     this script exists to remove, moved one screen along.
    #
    #     Deactivated rather than deleted, like everything else here: the
    #     ledger explains its own totals through these rows, and an offer with
    #     `active = False` is out of the shop and still legible in the history.
    stale: set[int] = set()
    for offer in session.exec(select(Offer).where(Offer.active)).all():
        product = session.get(Product, offer.product_id)
        if product is None or product.status is not ProductStatus.PUBLISHED:
            offer.active = False
            session.add(offer)
            stale.add(offer.product_id)
    session.commit()
    for product_id in stale:
        of.refresh(session, product_id)
    session.commit()

    # 4. The keeper, and its grid.
    keep.status = ProductStatus.PUBLISHED
    keep.proposed_by_id = shop.id
    keep.seller = shop.name
    keep.weight_grams = keep.weight_grams or 300
    session.add(keep)
    session.commit()

    offer = session.exec(
        select(Offer).where(Offer.product_id == keep.id, Offer.seller_id == shop.id)
    ).first()
    if offer is None:
        offer = Offer(
            seller_id=shop.id,
            product_id=keep.id,
            price=keep.price or 149_000,
            stock_left=0,
            active=True,
        )
        session.add(offer)
        session.commit()
        session.refresh(offer)
    else:
        offer.active = True
        session.add(offer)
        session.commit()

    _rebuild_grid(session, keep, offer, actor)

    of.refresh(session, keep.id)
    session.commit()


def _rebuild_grid(
    session: Session, product: Product, offer: Offer, actor: User
) -> None:
    """Two colours, five sizes each, and a count on every cell.

    Existing variants are reused by label rather than replaced: a variant named
    by an order line or a movement is part of a record, and deleting it would
    leave the ledger unable to explain its own totals.

    The counts go through ``stock.move`` as a stocktake correction, which
    records the *difference* — so running this twice moves nothing the second
    time, and the ledger still adds up to the column.
    """
    existing = session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all()
    colours: dict[str, ProductVariant] = {}
    for row in existing:
        if row.kind is VariantKind.COLOR:
            colours.setdefault(row.label, row)

    wanted: list[tuple[ProductVariant, int]] = []
    for c_index, (label, value) in enumerate(COLOURS):
        swatch = colours.get(label)
        if swatch is None:
            swatch = ProductVariant(
                product_id=product.id,
                kind=VariantKind.COLOR,
                label=label,
                value=value,
                sort=c_index,
                stock_left=None,
                in_stock=True,
            )
            session.add(swatch)
            session.commit()
            session.refresh(swatch)
        else:
            swatch.value = value
            swatch.sort = c_index
            swatch.in_stock = True
            session.add(swatch)

        sizes = {
            row.label: row
            for row in existing
            if row.kind is VariantKind.SIZE and row.parent_id == swatch.id
        }
        for s_index, (size, white, black) in enumerate(SIZES):
            cell = sizes.get(size)
            if cell is None:
                cell = ProductVariant(
                    product_id=product.id,
                    kind=VariantKind.SIZE,
                    label=size,
                    value=size,
                    parent_id=swatch.id,
                    sort=s_index,
                    stock_left=None,
                    in_stock=True,
                )
                session.add(cell)
                session.commit()
                session.refresh(cell)
            else:
                cell.sort = s_index
                cell.in_stock = True
                session.add(cell)
            wanted.append((cell, white if c_index == 0 else black))
    session.commit()

    # Any size that is not in the grid — a leftover from the seed — is taken
    # out of stock rather than deleted, for the same reason as above.
    keep_ids = {cell.id for cell, _ in wanted} | {
        row.id for row in existing if row.kind is VariantKind.COLOR
    }
    for row in session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all():
        if row.id not in keep_ids and row.kind is VariantKind.SIZE:
            row.in_stock = False
            session.add(row)
    session.commit()

    # A row on the offer for every variant, so the per-colour figures survive.
    have = {
        row.variant_id
        for row in session.exec(
            select(OfferVariant).where(OfferVariant.offer_id == offer.id)
        ).all()
    }
    for row in session.exec(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all():
        if row.id not in have:
            session.add(
                OfferVariant(offer_id=offer.id, variant_id=row.id, stock_left=0)
            )
    session.commit()

    # And the counts, as differences. `move` is the only thing in this codebase
    # that writes a stock figure.
    for cell, target in wanted:
        current = session.exec(
            select(OfferVariant).where(
                OfferVariant.offer_id == offer.id, OfferVariant.variant_id == cell.id
            )
        ).first()
        now = current.stock_left if current else 0
        gap = target - now
        if gap == 0:
            continue
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=gap,
            variant_id=cell.id,
            actor=actor,
            reason="Sinov uchun bitta mahsulot qoldirildi",
        )
    session.commit()


def main() -> int:
    if not settings.is_dev:
        print(f"MB_ENV is {settings.env!r}, not 'dev'.", file=sys.stderr)
        return 2
    require_current_schema()
    doing = "--apply" in sys.argv

    with Session(engine) as session:
        print(f"database: {settings.database_url}")
        print(f"mode:     {'APPLY' if doing else 'dry run (pass --apply)'}\n")
        for line in plan(session):
            print(f"  {line}")
        if not doing:
            print("\n  nothing written.")
            return 0

        actor = session.exec(
            select(User).where(User.role == UserRole.ADMIN).order_by(col(User.id))
        ).first()
        if actor is None:
            print("no admin to attribute the stocktake to", file=sys.stderr)
            return 1
        apply(session, actor)

        print("\napplied. The shop now holds:")
        rows = session.exec(
            select(Product).where(Product.status == ProductStatus.PUBLISHED)
        ).all()
        for product in rows:
            print(f"  {product.id}  {product.title}  {product.price} so'm")
        print(f"  ({len(rows)} product in the shop)")
        archived = session.exec(
            select(func.count())
            .select_from(Product)
            .where(Product.status == ProductStatus.ARCHIVED)
        ).one()
        print(f"  {int(archived)} archived — their orders and movements are intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
