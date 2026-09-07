"""One-off: give every card a state, and publish the ones already in the shop.

    .venv/bin/python -m tools.publish_catalogue          # dry run
    .venv/bin/python -m tools.publish_catalogue --apply

The customer endpoints now show ``published`` cards and nothing else. Every
card that predates the column *was* in the shop, so it is published — and the
column's own default is ``DRAFT``, matching the model, so nothing written
afterwards is published by accident.

Note the two steps: the ALTER defaults to the model's own value and the
existing rows are then updated. A column left defaulting to ``PUBLISHED``
would be a trap for the next person inserting a row by hand.

Idempotent.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, col, select

from app.db import engine, init_db
from app.models import Product, ProductStatus

NEW_COLUMNS = [
    # SQLAlchemy stores an enum by its *name*, so the default is the name.
    ("products", "status", "VARCHAR(10) NOT NULL DEFAULT 'DRAFT'"),
    ("products", "proposed_by_id", "INTEGER REFERENCES sellers(id)"),
    ("products", "moderation_note", "VARCHAR NOT NULL DEFAULT ''"),
]


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
    if apply:
        init_db()

    with Session(engine) as session:
        columns = add_columns(session, apply=apply)
        print(f"columns: {', '.join(columns) if columns else 'already there'}")

        if not apply:
            total = session.connection().exec_driver_sql(
                "select count(*) from products"
            ).scalar()
            print(f"cards to publish: {total}")
            print("\nnothing written — pass --apply")
            return

        # Everything that predates the column was in the shop.
        drafts = session.exec(
            select(Product).where(Product.status == ProductStatus.DRAFT)
        ).all()
        for card in drafts:
            card.status = ProductStatus.PUBLISHED
            session.add(card)
        session.commit()
        print(f"cards published: {len(drafts)}")

        counts: dict[str, int] = {}
        for card in session.exec(select(Product).order_by(col(Product.id))).all():
            counts[card.status.value] = counts.get(card.status.value, 0) + 1
        print("by state:", counts)


if __name__ == "__main__":
    main()
