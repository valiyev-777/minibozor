"""One-off: check an existing database against the models, then adopt it.

    .venv/bin/python -m tools.adopt_alembic          # dry run
    .venv/bin/python -m tools.adopt_alembic --apply
    .venv/bin/alembic stamp head                     # afterwards

For a database that predates Alembic — one built by ``create_all`` and edited
since by the hand-written ALTERs in ``tools/publish_catalogue.py``,
``tools/open_stock_ledger.py`` and ``tools/adopt_offers.py``. Before such a
database can be stamped at the baseline, the claim that stamping makes has to
be true: that it holds what the baseline builds.

On this project's own development database it was **not** true, and the reason
is worth writing down because it is the exact failure the migration system is
being installed to prevent.

``ALTER TABLE ... ADD COLUMN`` adds a column. It does not add the index that
``Field(index=True)`` implies, and none of the three scripts above created one.
So seven indexes the models declare had never existed on any database that was
upgraded rather than rebuilt — including ``ix_products_status``, on the column
that gates every customer-facing read, and ``ix_sellers_user_id``, which is
consulted on every seller-scoped request. A fresh install had them. Nothing
compared the two, so nothing said so.

What this fixes and what it deliberately leaves:

* **Missing indexes: created.** ``CREATE INDEX`` reads the table and writes a
  new b-tree; it moves no rows and rewrites no table, so it is safe on a
  database with real data in it.

* **Legacy server defaults: left alone, on purpose.** The same ALTERs wrote
  ``NOT NULL DEFAULT 0`` and ``NOT NULL DEFAULT ''`` because that is the *only*
  form SQLite accepts when adding a NOT NULL column to a table that already
  has rows — the default is an artefact of how the column arrived, not a
  decision anybody made. Nothing reads it: every model field carries a
  Python-side default and SQLModel supplies a value for every column on every
  insert, so the server default is never consulted. Removing one on SQLite
  means rebuilding the whole table — create, copy every row, drop, rename —
  and there are seven such tables here holding live orders and products. That
  is real risk in exchange for a DDL string nobody reads.

  The cost of leaving them is that ``alembic check`` reports them, on this one
  database, until somebody rebuilds those tables. See ``backend/README.md``.

Idempotent: run it as often as you like.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect
from sqlmodel import SQLModel

from app import models  # noqa: F401  — registers the tables on the metadata
from app.core.config import settings
from app.db import engine


def missing_tables(bind) -> list[str]:
    """Tables the models declare and the database has not got.

    A database missing a whole table is not a drifted one — it is one that was
    never built, or was built from a much older model. Repairing indexes on it
    would be beside the point, so it is reported and nothing is touched.
    """
    present = set(inspect(bind).get_table_names())
    return sorted(set(SQLModel.metadata.tables) - present)


def missing_indexes(bind) -> list[tuple[str, str]]:
    """``(table, index)`` for every index the models declare and the database
    has not got."""
    inspector = inspect(bind)
    present_tables = set(inspector.get_table_names())
    out: list[tuple[str, str]] = []
    for name, table in sorted(SQLModel.metadata.tables.items()):
        if name not in present_tables:
            continue
        have = {index["name"] for index in inspector.get_indexes(name)}
        # A unique column becomes a unique index under SQLModel, so this covers
        # both `index=True` and `unique=True`.
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            if index.name not in have:
                out.append((name, index.name))
    return out


def legacy_server_defaults(bind) -> list[tuple[str, str, str]]:
    """``(table, column, default)`` where the database carries a server default
    the models never asked for. Reported, never changed — see the docstring."""
    inspector = inspect(bind)
    present_tables = set(inspector.get_table_names())
    out: list[tuple[str, str, str]] = []
    for name, table in sorted(SQLModel.metadata.tables.items()):
        if name not in present_tables:
            continue
        for column in inspector.get_columns(name):
            if column.get("default") is None:
                continue
            declared = table.columns.get(column["name"])
            if declared is not None and declared.server_default is None:
                out.append((name, column["name"], str(column["default"])))
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    print(f"database: {settings.database_url}")
    print(f"mode:     {'APPLY' if apply else 'dry run (pass --apply to write)'}\n")

    absent = missing_tables(engine)
    if absent:
        print(f"{len(absent)} table(s) missing entirely: {', '.join(absent)}")
        print("\nThis database was not built from these models. Nothing changed.")
        print("Build it with `alembic upgrade head` instead of repairing it.")
        return 1

    gaps = missing_indexes(engine)
    print(f"indexes the models declare and this database lacks: {len(gaps)}")
    for table, index in gaps:
        print(f"  - {table}.{index}")

    if gaps and apply:
        wanted = {(t, i) for t, i in gaps}
        for name, table in SQLModel.metadata.tables.items():
            for index in table.indexes:
                if (name, index.name) in wanted:
                    # checkfirst so a concurrent run, or a second run of this
                    # script, is not an error.
                    index.create(bind=engine, checkfirst=True)
        print(f"\ncreated {len(gaps)} index(es).")
        left = missing_indexes(engine)
        print(f"still missing: {len(left)}" + (f" — {left}" if left else ""))
    elif gaps:
        print("\nnot created (dry run).")
    else:
        print("  (none)")

    defaults = legacy_server_defaults(engine)
    print(
        f"\nlegacy server defaults, left in place on purpose: {len(defaults)}"
    )
    for table, column, value in defaults:
        print(f"  - {table}.{column} = {value}")
    if defaults:
        print(
            "\n  These came from `ALTER TABLE ... ADD COLUMN x NOT NULL DEFAULT y`,\n"
            "  which is the only form SQLite accepts on a populated table. Nothing\n"
            "  reads them — every default is Python-side — and removing one means\n"
            "  rebuilding the table. `alembic check` will list them; anything it\n"
            "  reports beyond this set is new drift and wants a migration."
        )

    print("\nNext: .venv/bin/alembic stamp head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
