"""One-off: turn the single-seller catalogue into offers.

    backend/.venv/bin/python -m tools.adopt_offers          # dry run
    backend/.venv/bin/python -m tools.adopt_offers --apply

There is no migration tool in this project, so schema changes are applied by
hand. This script is that hand for the offers change: it adds the three tables
and the four columns, creates the shop itself as the first seller, reads every
product's price and stock back out into an offer, and fills in the seller on
order lines that were written before any of it existed.

Safe to run twice: every step checks first, and ``app.offers.mirror_catalogue``
leaves a product that already has an offer alone.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, col, select

from app import offers as of
from app.db import engine, init_db
from app.models import CartItem, Offer, OfferVariant, Order, OrderItem, Seller

NEW_COLUMNS = [
    # SQLite takes a REFERENCES clause on ADD COLUMN as long as the default is
    # NULL, which all four of these are, so no table has to be rebuilt.
    ("cart_items", "offer_id", "INTEGER REFERENCES offers(id)"),
    ("order_items", "seller_id", "INTEGER REFERENCES sellers(id)"),
    ("order_items", "offer_id", "INTEGER REFERENCES offers(id)"),
]


def add_columns(session: Session, *, apply: bool) -> list[str]:
    done = []
    for table, column, spec in NEW_COLUMNS:
        existing = {
            row[1]
            for row in session.connection().exec_driver_sql(
                f"pragma table_info({table})"
            )
        }
        if column in existing:
            continue
        done.append(f"{table}.{column}")
        if apply:
            session.connection().exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {spec}"
            )
    return done


def backfill_order_lines(session: Session, *, apply: bool) -> int:
    """Give every existing order line the seller it must have had.

    Before offers there was one seller and one price, so the answer is not a
    guess: whichever offer the product now has is the one the line was bought
    on. A line whose product has since been deleted keeps its nulls, and
    ``inventory`` declines to move a shelf it cannot name.
    """
    lines = session.exec(
        select(OrderItem).where(col(OrderItem.offer_id).is_(None))
    ).all()
    touched = 0
    for line in lines:
        if line.product_id is None:
            continue
        offers = of.offers_for(session, line.product_id, active_only=False)
        if not offers:
            continue
        touched += 1
        if apply:
            line.seller_id = offers[0].seller_id
            line.offer_id = offers[0].id
            session.add(line)
    return touched


def backfill_cart_lines(session: Session, *, apply: bool) -> int:
    lines = session.exec(select(CartItem).where(col(CartItem.offer_id).is_(None))).all()
    touched = 0
    for line in lines:
        offer = of.winning_offer(session, line.product_id)
        if offer is None:
            continue
        touched += 1
        if apply:
            line.offer_id = offer.id
            session.add(line)
    return touched


def main() -> None:
    apply = "--apply" in sys.argv
    if apply:
        # Creates the three new tables; leaves every existing one alone.
        init_db()

    with Session(engine) as session:
        columns = add_columns(session, apply=apply)
        print(f"columns: {', '.join(columns) if columns else 'already there'}")

        if not apply:
            # Deliberately reads only what is certainly there: on a database
            # that has not been migrated yet the new tables do not exist, and
            # a dry run that crashes looking for them is no use.
            tables = {
                row[0]
                for row in session.connection().exec_driver_sql(
                    "select name from sqlite_master where type='table'"
                )
            }
            missing = {"sellers", "offers", "offer_variants"} - tables
            print(f"tables to create: {', '.join(sorted(missing)) or 'already there'}")
            for table, label in (("products", "offers to create, one each"),
                                 ("order_items", "order lines to backfill"),
                                 ("cart_items", "cart lines to backfill")):
                count = session.connection().exec_driver_sql(
                    f"select count(*) from {table}"
                ).scalar()
                print(f"{label}: {count}")
            print("\nnothing written — pass --apply")
            return

        house = of.house_seller(session)
        made = of.mirror_catalogue(session, house)
        print(f"seller: {house.name} (id {house.id}, {house.commission_percent}%)")
        print(f"offers created: {made}")

        print(f"order lines backfilled: {backfill_order_lines(session, apply=True)}")
        print(f"cart lines backfilled:  {backfill_cart_lines(session, apply=True)}")
        session.commit()

        # And a pass of the cache, so every product row is what its offer says.
        for product_id in session.exec(select(Offer.product_id)).all():
            of.refresh(session, product_id)
        session.commit()

        print(
            f"\nsellers {len(session.exec(select(Seller)).all())}, "
            f"offers {len(session.exec(select(Offer)).all())}, "
            f"offer variants {len(session.exec(select(OfferVariant)).all())}, "
            f"orders {len(session.exec(select(Order)).all())}"
        )


if __name__ == "__main__":
    main()
