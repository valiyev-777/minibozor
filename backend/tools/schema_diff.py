"""Comparing two schemas, table by table, column by column.

The reason this file exists rather than a careful read-through: the failure it
guards against is invisible. ``SQLModel.metadata.create_all`` creates a table
that is missing and *never alters one that exists*, so a column added to
``models.py`` without a migration written for it appears on every fresh
database and on nobody's existing one. Nothing raises. The tests pass, because
the tests build their database from ``create_all``. The error surfaces on the
one database that was not rebuilt, which is production.

So the question "does ``alembic upgrade head`` build what ``create_all``
builds" has to be answered by something that cannot get bored.

**Both sides are reflected, never one reflected and one read from metadata.**
That distinction is the whole trick. SQLAlchemy's idea of a column's type and
SQLite's idea of it are not the same object — ``AutoString`` becomes
``VARCHAR``, an enum becomes ``VARCHAR``, a ``date`` becomes ``DATE`` — so
comparing metadata against a real database would report dozens of differences
that are not differences. Building two real databases and reflecting both
compares like with like: whatever the dialect did to one, it did to the other.

Two things are deliberately not compared, and both would be noise:

* **Foreign key names.** ``create_all`` leaves them unnamed on SQLite and
  there is no statement in SQLite that refers to one, so a name is not part of
  the schema in any sense that matters. The columns, the target table and the
  target columns are compared.
* **``autoincrement``.** SQLite reflection infers it from ``INTEGER PRIMARY
  KEY`` rather than reading it back, and reports it inconsistently between an
  inline primary key and a table-level constraint. The primary key columns
  themselves are compared.

Everything else is: tables, and per table the columns with their type,
nullability and server default; the primary key; every index with its name,
columns and uniqueness; and every named unique constraint.

Run it directly to check the two builders against each other::

    .venv/bin/python -m tools.schema_diff

or to compare two databases that already exist — any two URLs SQLAlchemy can
open, including one of each dialect::

    .venv/bin/python -m tools.schema_diff sqlite:///./minibozor.db sqlite:///./test.db
    .venv/bin/python -m tools.schema_diff sqlite:///./test.db "postgresql+psycopg://..."

``compare_builders`` — the no-argument form, and what the test in the suite
calls — builds both sides on **SQLite**, because the property it checks is
whether the migration scripts still describe the models and that is not a
question about a dialect. Checking the same thing on Postgres needs two
databases and the rights to create them, so it is a documented command rather
than part of the suite; see "Postgres" in ``backend/README.md``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect

# Alembic's own bookkeeping table. It exists on a migrated database and cannot
# exist on a `create_all` one, so comparing it would be comparing the two
# builders' signatures rather than their schemas.
BOOKKEEPING = {"alembic_version"}


def describe(url: str) -> dict[str, Any]:
    """One database's schema as plain data, ready to be compared or printed."""
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        out: dict[str, Any] = {}
        for table in sorted(inspector.get_table_names()):
            if table in BOOKKEEPING:
                continue
            out[table] = {
                "columns": {
                    column["name"]: {
                        "type": str(column["type"]),
                        "nullable": bool(column["nullable"]),
                        "default": _text(column.get("default")),
                    }
                    for column in inspector.get_columns(table)
                },
                "primary_key": sorted(
                    inspector.get_pk_constraint(table).get(
                        "constrained_columns"
                    )
                    or []
                ),
                "indexes": sorted(
                    (
                        index["name"] or "",
                        tuple(index["column_names"]),
                        bool(index.get("unique")),
                    )
                    for index in inspector.get_indexes(table)
                ),
                "unique_constraints": sorted(
                    (
                        constraint.get("name") or "",
                        tuple(sorted(constraint["column_names"])),
                    )
                    for constraint in inspector.get_unique_constraints(table)
                ),
                # Unnamed on purpose; see the module docstring.
                "foreign_keys": sorted(
                    (
                        tuple(key["constrained_columns"]),
                        key["referred_table"],
                        tuple(key["referred_columns"]),
                    )
                    for key in inspector.get_foreign_keys(table)
                ),
            }
        return out
    finally:
        engine.dispose()


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def safe_url(url: str) -> str:
    """The URL with any password replaced, for printing.

    A Postgres URL carries its credentials, and this tool's whole output is
    meant to be pasted into an issue or a terminal somebody else is watching.
    """
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return url


def differences(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    """Every way the two schemas disagree, as sentences.

    Sentences rather than a diff of two JSON blobs: the reader of this list is
    somebody who has just been told their migration is wrong and needs to know
    which column, not which line.
    """
    out: list[str] = []

    only_left = sorted(set(left) - set(right))
    only_right = sorted(set(right) - set(left))
    for table in only_left:
        out.append(f"table {table}: on the left only")
    for table in only_right:
        out.append(f"table {table}: on the right only")

    for table in sorted(set(left) & set(right)):
        a, b = left[table], right[table]

        for column in sorted(set(a["columns"]) - set(b["columns"])):
            out.append(f"{table}.{column}: on the left only")
        for column in sorted(set(b["columns"]) - set(a["columns"])):
            out.append(f"{table}.{column}: on the right only")
        for column in sorted(set(a["columns"]) & set(b["columns"])):
            for field in ("type", "nullable", "default"):
                first, second = a["columns"][column][field], b["columns"][column][field]
                if first != second:
                    out.append(
                        f"{table}.{column} {field}: {first!r} on the left, "
                        f"{second!r} on the right"
                    )

        for field in ("primary_key", "indexes", "unique_constraints", "foreign_keys"):
            if a[field] != b[field]:
                missing = [row for row in a[field] if row not in b[field]]
                extra = [row for row in b[field] if row not in a[field]]
                if missing:
                    out.append(f"{table} {field}: left has {missing!r}, right does not")
                if extra:
                    out.append(f"{table} {field}: right has {extra!r}, left does not")

    return out


# ------------------------------------------------------- building the two sides


def build_with_create_all(path: Path) -> str:
    """A database as ``init_db`` would build it, in a subprocess.

    A subprocess because ``app.db`` builds its engine at import time from
    ``settings.database_url``, and ``settings`` is an ``lru_cache``d singleton:
    inside one process the URL is decided once and cannot be pointed somewhere
    else afterwards. Handing the child an explicit ``MB_DATABASE_URL`` is also
    the only way to be sure this cannot touch the developer's own database —
    the one thing in here that would be unrecoverable.
    """
    url = f"sqlite:///{path}"
    subprocess.run(
        [sys.executable, "-c", "from app.db import init_db; init_db()"],
        check=True,
        cwd=_backend(),
        env=_env(url),
        capture_output=True,
    )
    return url


def build_with_alembic(path: Path) -> str:
    """The same database as ``alembic upgrade head`` builds it."""
    url = f"sqlite:///{path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=_backend(),
        env=_env(url),
        capture_output=True,
    )
    return url


def _backend() -> Path:
    """The directory both commands have to run from.

    ``alembic.ini`` names ``%(here)s/alembic`` and ``prepend_sys_path = .``, so
    Alembic and the app both expect to be started from ``backend/``.
    """
    return Path(__file__).resolve().parent.parent


def _env(url: str) -> dict[str, str]:
    import os

    return {**os.environ, "MB_DATABASE_URL": url, "MB_ENV": "dev"}


def compare_builders() -> list[str]:
    """Build both, from nothing, and say how they differ."""
    with tempfile.TemporaryDirectory() as tmp:
        room = Path(tmp)
        created = describe(build_with_create_all(room / "create_all.db"))
        migrated = describe(build_with_alembic(room / "alembic.db"))
    return differences(created, migrated)


def main(argv: list[str]) -> int:
    if len(argv) == 2:
        left, right = describe(argv[0]), describe(argv[1])
        names = (argv[0], argv[1])
        found = differences(left, right)
    elif not argv:
        names = ("create_all", "alembic upgrade head")
        found = compare_builders()
    else:
        print(__doc__)
        return 2

    print(f"left:  {safe_url(names[0])}\nright: {safe_url(names[1])}")
    if not found:
        print("\nidentical: no difference in tables, columns, types, nullability,")
        print("indexes, unique constraints or foreign keys.")
        return 0
    print(f"\n{len(found)} difference(s):")
    for line in found:
        print(f"  - {line}")
    return 1


if __name__ == "__main__":
    if "--json" in sys.argv[1:]:
        rest = [a for a in sys.argv[1:] if a != "--json"]
        print(json.dumps(describe(rest[0]), indent=2, sort_keys=True))
        raise SystemExit(0)
    raise SystemExit(main(sys.argv[1:]))
