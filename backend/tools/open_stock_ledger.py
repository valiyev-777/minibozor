"""One-off: turn the shelf into a ledger.

    .venv/bin/python -m tools.open_stock_ledger            # dry run
    .venv/bin/python -m tools.open_stock_ledger --apply

Creates the seven warehouse tables, adds ``cart_items.reserved_until``, and
writes one opening movement per counted leaf so that the running total on every
offer agrees with the sum of its movements from the first row. That agreement is
the invariant the whole ledger rests on, and a database migrated without these
rows would violate it before anybody had done anything.

Safe to run twice: an offer that already has movements is left alone.

Superseded by the migration history, for the schema half of what it does.
Every column and table below is in ``alembic/versions/0001_baseline.py``, so a
database at ``head`` already has them and the ALTER step here finds nothing to
do. It is kept because the *data* half is not in any migration and could not
be: the opening balances are read off whatever the counts happened
to be when the ledger was opened, and that moment has passed.

Creating tables is no longer its job — it used to call
``SQLModel.metadata.create_all`` first — so on a database older than the
baseline, run the migration before this:

    .venv/bin/alembic upgrade head
"""

from __future__ import annotations

import sys

from sqlmodel import Session, col, select

from app import offers as of
from app import stock as st
from app.db import engine
from app.models import CartItem, Offer, StockMovement

NEW_COLUMNS = [
    # Null default, so SQLite takes it without rebuilding the table. A line
    # with no deadline is treated as expired, which is right: it predates
    # holding and there is no way to say when its hold should end.
    ("cart_items", "reserved_until", "DATETIME"),
]

NEW_TABLES = (
    "stock_movements",
    "supplies",
    "supply_lines",
    "stock_counts",
    "stock_count_lines",
    "removal_orders",
    "removal_lines",
)


def add_columns(session: Session, *, apply: bool) -> list[str]:
    done = []
    for table, column, spec in NEW_COLUMNS:
        present = {
            row[1]
            for row in session.connection().exec_driver_sql(f"pragma table_info({table})")
        }
        if column in present:
            continue
        done.append(f"{table}.{column}")
        if apply:
            session.connection().exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {spec}"
            )
    return done


def main() -> None:
    apply = "--apply" in sys.argv

    with Session(engine) as session:
        columns = add_columns(session, apply=apply)
        print(f"columns: {', '.join(columns) if columns else 'already there'}")

        if not apply:
            tables = {
                row[0]
                for row in session.connection().exec_driver_sql(
                    "select name from sqlite_master where type='table'"
                )
            }
            missing = [t for t in NEW_TABLES if t not in tables]
            print(f"tables to create: {', '.join(missing) or 'already there'}")
            offers = session.connection().exec_driver_sql(
                "select count(*) from offers"
            ).scalar()
            print(f"offers needing an opening balance: {offers}")
            print("\nnothing written — pass --apply")
            return

        opened = 0
        for offer in session.exec(select(Offer).order_by(col(Offer.id))).all():
            already = session.exec(
                select(StockMovement).where(StockMovement.offer_id == offer.id)
            ).first()
            if already is not None:
                continue
            of.opening_balance(session, offer)
            opened += 1
        session.commit()
        print(f"offers given an opening balance: {opened}")

        # Every basket line that predates holding gets a deadline, so it holds
        # what it is holding for a stated length of time rather than for ever.
        stale = session.exec(
            select(CartItem).where(col(CartItem.reserved_until).is_(None))
        ).all()
        for line in stale:
            line.reserved_until = st.hold_until()
            session.add(line)
        session.commit()
        print(f"basket lines given a deadline: {len(stale)}")

        # And the cached figures, which are now the shelf less what is held.
        for product_id in {o.product_id for o in session.exec(select(Offer)).all()}:
            of.refresh(session, product_id)
        session.commit()

        wrong = [
            (o.id, o.stock_left, st.on_hand(session, o.id))
            for o in session.exec(select(Offer)).all()
            if o.stock_left != st.on_hand(session, o.id)
        ]
        print(f"movements: {len(session.exec(select(StockMovement)).all())}")
        print(f"offers disagreeing with their ledger: {wrong or 'none'}")


if __name__ == "__main__":
    main()
