from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Which database this process is talking to, asked once and answered by name
# rather than by re-testing the URL prefix at each use. Everything below that
# differs between the two is gathered here; the rest of the application never
# asks.
IS_SQLITE = settings.database_url.startswith("sqlite")
IS_POSTGRES = settings.database_url.startswith(("postgresql", "postgres://"))


def _engine_options() -> tuple[dict, dict]:
    """The two dialects' connection settings, and why each one is needed.

    SQLite and Postgres want opposite things from a pool, because a SQLite
    "connection" is a file handle in this process and a Postgres one is a
    socket to a server that limits how many it will accept.
    """
    if IS_SQLITE:
        # SQLite's driver refuses, by default, to let a connection be used
        # from a thread other than the one that opened it. FastAPI runs sync
        # endpoints in a worker thread pool, so a session opened per request
        # is routinely used from a different thread than the engine's — which
        # is safe here because a session is not shared *concurrently*, only
        # handed across.
        connect_args = {"check_same_thread": False}
        kwargs: dict = {}
        if ":memory:" in settings.database_url:
            # An in-memory database lives inside its connection: pool a
            # second one and it is a second, empty database. StaticPool keeps
            # exactly one, so every session sees the same tables.
            kwargs["poolclass"] = StaticPool
        return connect_args, kwargs

    if IS_POSTGRES:
        return (
            {
                # A query that hangs for ever holds a worker thread for ever.
                # Ten seconds is far longer than a healthy connect and far
                # shorter than a user's patience.
                "connect_timeout": 10,
                # Names the process in `pg_stat_activity`, so "what is that
                # connection" has an answer during an incident.
                "application_name": "minibozor-api",
            },
            {
                # Postgres' own default is 100 connections *for the whole
                # server*. pool_size + max_overflow is the ceiling this
                # process can reach, so it has to be a number several
                # replicas can hold at once without exhausting the server.
                "pool_size": 5,
                "max_overflow": 10,
                # Wait rather than fail when the pool is full, but not for
                # ever: a request queueing 30s behind a connection has
                # already lost.
                "pool_timeout": 30,
                # Recycle before anything upstream decides an idle connection
                # is dead. A pooler or a firewall dropping one silently is the
                # classic cause of "the first request after lunch fails".
                "pool_recycle": 1800,
                # And check the connection is alive before handing it out,
                # which turns a stale-socket error into a transparent
                # reconnect.
                "pool_pre_ping": True,
            },
        )

    return {}, {}


_connect_args, _kwargs = _engine_options()

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
    **_kwargs,
)


# --------------------------------------------------------------------------- lower() is not lower()

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _teach_sqlite_to_lowercase_unicode(dbapi_connection, _record) -> None:
        """Replace SQLite's ``lower()`` with Python's, which knows about Cyrillic.

        Every search in this codebase is written the portable way already —
        ``func.lower(column).like(needle)``, with the needle lowered in Python
        — precisely so that ``LIKE``'s own case rules never come into it.
        SQLite's ``LIKE`` ignores ASCII case and Postgres' does not, and
        neither matters when both sides are already lowercase.

        Except that ``lower()`` is not the same function on the two databases.
        **SQLite's is ASCII-only**: ``lower('Чайники')`` is ``'Чайники'``,
        unchanged. Postgres' is Unicode-aware and returns ``'чайники'``. The
        needle, meanwhile, is lowered by Python — which is Unicode-aware on
        both. So on SQLite a Russian search compared a mixed-case column
        against a lowercase needle and matched nothing:

            lower('Чайники')  ->  'Чайники'     (SQLite leaves it alone)
            'ЧАЙНИКИ'.lower() ->  'чайники'     (Python does not)
            'Чайники' LIKE '%чайники%'  ->  no match

        This is the failure mode that does not announce itself. Nothing
        raises, no test that searches in Uzbek or English notices, and the
        symptom is a customer typing a Russian product name into a trilingual
        shop and being told there is nothing there. It was live on SQLite —
        which is to say on every developer's machine — and would have been
        *fixed* by moving to Postgres, so it would have gone on being invisible
        until somebody ran the two side by side.

        Overriding the builtin rather than rewriting nine call sites: the SQL
        those sites emit is correct and portable, and the thing that was wrong
        was one dialect's implementation of a standard function. Registered per
        connection because that is the only scope SQLite offers, and
        ``deterministic=True`` so the optimiser may still use it in an index or
        a WHERE clause.

        Postgres needs none of this and gets none: the listener is not even
        attached.
        """
        dbapi_connection.create_function(
            "lower", 1, _python_lower, deterministic=True
        )
        # `upper` has the identical defect. Nothing searches with it today, so
        # this is not a fix for a live bug — it is refusing to leave one half
        # of the pair behind for the next person who reaches for it.
        dbapi_connection.create_function(
            "upper", 1, _python_upper, deterministic=True
        )


def _python_lower(value):
    """``str.lower`` for text, and a pass-through for everything else.

    SQLite will hand this a NULL, an integer or a blob if a query asks it to;
    the builtin returns those unchanged rather than raising, and a replacement
    that raised would turn a harmless query into a 500.
    """
    return value.lower() if isinstance(value, str) else value


def _python_upper(value):
    return value.upper() if isinstance(value, str) else value

# Where the migrations live. Resolved from this file rather than from the
# working directory, so the check below answers the same way whether the app
# was started from `backend/` or by an init system from `/`.
BACKEND = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND / "alembic.ini"


def init_db() -> None:
    """Create every table that does not exist yet, and alter nothing.

    **Not the way the schema is maintained any more.** ``create_all`` creates a
    missing table and never touches one that is already there, which is why
    every column change before Alembic was a hand-written ALTER and why seven
    declared indexes had never existed on any database that was upgraded
    rather than rebuilt. See ``tools/adopt_alembic``.

    It survives for the two jobs it is actually good at, both of which start
    from nothing:

    * the test suite, which builds a fresh database per run and wants the
      fastest path to one — with ``stamp_head`` immediately after, so the
      database says what it is;
    * seeding a scratch database.

    Anything with data in it goes through ``alembic upgrade head``.
    """
    from app import models  # noqa: F401  — registers the tables

    SQLModel.metadata.create_all(engine)


# --------------------------------------------------------------------------- what the schema is


def head_revision() -> str | None:
    """The newest revision in ``alembic/versions``, or None if unreadable."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def known_revisions() -> set[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    directory = ScriptDirectory.from_config(config)
    return {script.revision for script in directory.walk_revisions()}


def stamped_revision() -> str | None:
    """What the database says it is, or None if it has never been stamped."""
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        row = connection.execute(
            text("select version_num from alembic_version")
        ).fetchone()
    return row[0] if row else None


def stamp_head(revision: str | None = None) -> str:
    """Write the head revision onto this database without running anything.

    For a database that was just built by ``create_all`` — the test suite's —
    which genuinely holds what the baseline builds and would otherwise be
    refused by ``require_current_schema`` for having no version row. There is
    a test that holds the two builders to being identical, and it is the
    reason this is honest rather than a way of silencing the check.
    """
    target = revision or head_revision()
    with engine.begin() as connection:
        connection.execute(
            text(
                "create table if not exists alembic_version "
                "(version_num varchar(32) not null "
                "constraint alembic_version_pkc primary key)"
            )
        )
        connection.execute(text("delete from alembic_version"))
        connection.execute(
            text("insert into alembic_version (version_num) values (:v)"),
            {"v": target},
        )
    return target


def require_current_schema() -> str:
    """Refuse to carry on unless the database is at the newest revision.

    The application checks and does not migrate, and that is a deliberate
    split. Running ``upgrade head`` here would be one line and it is the wrong
    line:

    * **Several processes start at once.** Two workers, or a rolling deploy
      with the old and new replica overlapping, both run the same DDL. Alembic
      takes no cross-process lock, so on SQLite the loser gets "table already
      exists" or a locked database and on Postgres two DDL transactions can
      deadlock. The failure is intermittent and load-dependent, which is the
      hardest kind to be handed.
    * **Booting is not when anybody decided to change the schema.** A
      migration is a change to durable state that somebody should make in a
      window they chose, with a backup taken. A container that an orchestrator
      restarts at three in the morning is not that moment, and on SQLite a
      batch migration is several statements — one that dies halfway leaves the
      schema half-changed and the process dead, unable to say so.
    * **The runtime credential should not need DDL rights.** If startup
      migrates, it must have them for ever.

    So the failure mode is a process that will not start, naming the two
    revisions and the command that fixes it. The alternative — starting
    anyway — is a service that answers most requests and returns 500 from the
    one endpoint that touches the missing column, which is a worse outcome
    discovered later and by a customer.
    """
    head = head_revision()
    if head is None:                                     # pragma: no cover
        raise RuntimeError(
            "No migrations found. Expected revision scripts in "
            f"{BACKEND / 'alembic' / 'versions'}."
        )

    here = stamped_revision()
    if here is None:
        empty = not inspect(engine).get_table_names()
        raise RuntimeError(
            "This database has no Alembic version.\n"
            + (
                "  It looks empty. Build it with:\n"
                "      .venv/bin/alembic upgrade head\n"
                if empty
                else "  It predates Alembic. Check it against the models and\n"
                "  adopt it — this alters no data:\n"
                "      .venv/bin/python -m tools.adopt_alembic --apply\n"
                "      .venv/bin/alembic stamp head\n"
            )
            + f"  (expected revision {head})"
        )

    if here != head:
        if here not in known_revisions():
            raise RuntimeError(
                f"This database is at revision {here}, which this checkout does "
                "not have.\n"
                "  The code is older than the database — a deploy was rolled "
                "back and the\n"
                "  schema was not. Check out the matching revision rather than "
                "migrating.\n"
                f"  (this checkout's newest is {head})"
            )
        raise RuntimeError(
            f"This database is at revision {here}; the models expect {head}.\n"
            "  Bring it up to date with:\n"
            "      .venv/bin/alembic upgrade head"
        )
    return head


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
