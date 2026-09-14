"""Where Alembic gets its two facts: which database, and what it should hold.

Both come from the application rather than from ``alembic.ini``, and that is
the whole point of this file.

**The URL is read from ``app.core.config.settings``.** It is deliberately *not*
in ``alembic.ini``: the app already reads ``MB_DATABASE_URL`` from the
environment and a second copy of that decision in a checked-in ini file is a
second answer to "which database am I about to migrate". The one that gets
committed by accident is always the developer's own. So

    MB_DATABASE_URL="sqlite:///./scratch.db" .venv/bin/alembic upgrade head

migrates the scratch database, and a bare ``alembic upgrade head`` migrates
whatever the app itself would open. There is nowhere for the two to disagree.

**The metadata is ``SQLModel.metadata``**, with ``app.models`` imported for the
side effect of registering all 53 tables on it. Importing the module is what
fills the registry — a metadata object with nothing imported into it is empty,
and ``--autogenerate`` against an empty registry cheerfully writes a migration
that drops the entire schema.

``render_as_batch`` is on **for SQLite only**. SQLite cannot ``ALTER`` a
column, so batch mode turns "alter this column" into "make a new table, copy
the rows, swap it in" — the only way a type or a nullability changes there.

Postgres can alter a column in place, and on Postgres batch mode is not
harmless: a batch block rebuilds the table and the rebuild is reflected from
the *database*, so anything SQLAlchemy does not reflect faithfully is silently
dropped on the floor. It also turns a one-line ``ALTER TABLE`` into a full
table copy, which on a large table is the difference between a migration that
takes a moment and one that holds a lock for an hour. So it follows the
dialect rather than being set unconditionally.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# ``models`` is imported for the side effect of registering all 53 tables on
# ``SQLModel.metadata`` and for nothing else, so the name is unused on
# purpose. Without it ``--autogenerate`` compares the database against an
# empty registry and writes a migration that drops the whole schema.
from app import models  # noqa: F401
from app.core.config import settings
from app.db import IS_SQLITE

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The application's own answer, overriding whatever placeholder the ini holds.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it — ``alembic upgrade head --sql``.

    For a deployment where the person who reviews the change is not the person
    who runs it.
    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=IS_SQLITE,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER a column, and on Postgres batch mode would
            # rebuild the table for no reason. See the module docstring.
            render_as_batch=IS_SQLITE,
            # Without these two, autogenerate notices a column appearing and
            # disappearing and nothing in between — a column whose type or
            # default changed would produce an empty migration, which is worse
            # than no migration because it looks like agreement.
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
