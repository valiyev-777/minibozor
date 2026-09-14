"""The one test that makes the migration history worth having.

Everything else in this suite runs against a database built by
``SQLModel.metadata.create_all``, because that is by far the fastest way to
get one. Which means the suite has nothing at all to say about whether
``alembic upgrade head`` builds the same thing — and if it does not, every
test passes and the schema in ``alembic/versions`` is fiction.

The failure this catches is the ordinary one, not an exotic one. Somebody adds
a field to ``models.py``, runs the tests, sees green, and ships. ``create_all``
puts the column on every fresh database, so their machine and CI are both
fine. The column never appears on any database that already existed, because
``create_all`` does not alter a table it can already see. The error arrives on
the one database nobody rebuilt.

So: build both, from nothing, and compare them at the level a database
actually has — tables, columns, types, nullability, indexes, unique
constraints, foreign keys. The comparison is in ``tools.schema_diff``, which
explains what it does and does not look at, and which has its own
demonstration that it can tell two schemas apart.

If this test fails after you changed ``models.py``, the fix is not here:

    .venv/bin/alembic revision --autogenerate -m "what you changed"
"""

from __future__ import annotations

from tools import schema_diff


def test_alembic_builds_the_same_schema_as_create_all() -> None:
    """``alembic upgrade head`` and ``create_all`` agree, or say where they do not.

    Both databases are built in a temporary directory by subprocesses handed an
    explicit ``MB_DATABASE_URL``; see ``tools.schema_diff.build_with_create_all``
    for why a subprocess and not this one. Nothing here can reach the developer's
    database or the suite's own.
    """
    found = schema_diff.compare_builders()
    assert not found, (
        "`alembic upgrade head` and `SQLModel.metadata.create_all` no longer "
        "build the same schema.\n\n"
        + "\n".join(f"  - {line}" for line in found)
        + "\n\nIf you changed models.py, write the migration:\n"
        "    .venv/bin/alembic revision --autogenerate -m \"what you changed\"\n"
    )


def test_the_comparison_can_actually_tell_two_schemas_apart() -> None:
    """A guard that always passes guards nothing.

    The test above is a single assertion on a function that returns a list, so
    the way it rots is quietly: a refactor that made ``describe`` return ``{}``,
    or ``differences`` return ``[]``, would leave it green for ever while
    checking nothing. This holds the comparison to noticing each kind of drift
    it claims to notice, on hand-written schemas that need no database of ours.
    """
    base = {
        "orders": {
            "columns": {
                "id": {"type": "INTEGER", "nullable": False, "default": None},
                "code": {"type": "VARCHAR", "nullable": False, "default": None},
            },
            "primary_key": ["id"],
            "indexes": [("ix_orders_code", ("code",), True)],
            "unique_constraints": [],
            "foreign_keys": [],
        }
    }

    assert schema_diff.differences(base, base) == []

    def changed(**edit):
        import copy

        out = copy.deepcopy(base)
        out["orders"].update(edit)
        return out

    # A column that only one side has — the missing-migration case.
    added = changed()
    added["orders"]["columns"]["ghost"] = {
        "type": "INTEGER", "nullable": True, "default": None
    }
    assert any("ghost" in line for line in schema_diff.differences(base, added))

    # A type change, which SQLite cannot ALTER and batch mode exists for.
    retyped = changed()
    retyped["orders"]["columns"]["code"]["type"] = "INTEGER"
    assert any("type" in line for line in schema_diff.differences(base, retyped))

    # A nullability change.
    loosened = changed()
    loosened["orders"]["columns"]["code"]["nullable"] = True
    assert any("nullable" in line for line in schema_diff.differences(base, loosened))

    # An index that was never created — what had actually gone wrong on this
    # project's own database before Alembic arrived.
    unindexed = changed(indexes=[])
    assert any("indexes" in line for line in schema_diff.differences(base, unindexed))

    # A unique constraint, a foreign key, a primary key, a whole table.
    assert schema_diff.differences(base, changed(primary_key=[]))
    assert schema_diff.differences(
        base, changed(foreign_keys=[(("id",), "users", ("id",))])
    )
    assert schema_diff.differences(
        base, changed(unique_constraints=[("uq_orders_code", ("code",))])
    )
    assert schema_diff.differences(base, {})
    assert schema_diff.differences({}, base)
