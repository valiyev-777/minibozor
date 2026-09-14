"""the userrole enum has a seller in it on postgres too

The baseline built `userrole` with four values — CUSTOMER, ADMIN, WAREHOUSE,
COURIER — and `UserRole` has five. `SELLER` is the shop-window job: the
photographs, the words, the price, putting a card on sale. It is in the models,
it is in `STAFF_ROLES`, `deps.CatalogWriter` guards on it, and `tools.make_staff`
appoints one.

On Postgres none of that works. Appointing or seeding a seller fails with

    invalid input value for enum userrole: "SELLER"

and it fails at the *insert*, so the first person to find out is whoever runs
the seed against a real database. Development is on SQLite, where an enum
column is a plain VARCHAR with no server-side value list at all, so the whole
suite passes and has always passed. That is precisely why this went unnoticed
and why it is a production-breaker rather than a nuisance: nothing in the
normal working day can surface it.

**`ALTER TYPE ... ADD VALUE` is not reversible.** Postgres has no
`DROP VALUE`. Removing one means creating a second type, rewriting every
column that uses it, and dropping the first — which on `users.role` and
`audit_logs.actor_role` is a table rewrite to undo something that harms
nothing by being present. So the downgrade is deliberately a no-op, and says
so below. An extra value nobody writes costs nothing; the rollback that
removes it costs a lock on the users table.

**It must also run inside Alembic's transaction.** Before Postgres 12,
`ALTER TYPE ... ADD VALUE` could not run in a transaction block at all, and
Alembic wraps a migration in one. `COMMIT` first — closing Alembic's
transaction — is the ordinary way round it and is what this does, guarded by
`IF NOT EXISTS` so a database that already has the value is untouched and a
re-run is harmless. On 12 and later the commit is unnecessary and still
correct.

**A no-op on SQLite**, which has no enum types: the column is a VARCHAR and
already accepts the value. Nothing to add, and `sa.text` against a dialect
that has never heard of `ALTER TYPE` would simply fail.

Revision ID: 3b4d3d7fc68b
Revises: efe41db38f4a
Create Date: 2026-09-11 16:24:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3b4d3d7fc68b'
down_revision: Union[str, Sequence[str], None] = 'efe41db38f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add SELLER to the `userrole` enum, on Postgres only."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite and anything else store the column as text. There is no
        # server-side list of values, so there is nothing to add to.
        return

    # Alembic opened a transaction; older Postgres refuses ADD VALUE inside
    # one. Committing here ends Alembic's transaction rather than starting a
    # second — which is safe because this migration does exactly one thing and
    # has nothing left to roll back with it.
    op.execute("COMMIT")
    # The name is the *enum member's* name and not its value: SQLAlchemy maps
    # a Python enum by name, so the rows hold 'SELLER' and not 'seller'. The
    # baseline's four are spelt the same way.
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SELLER'")


def downgrade() -> None:
    """Nothing. Postgres cannot remove a value from an enum.

    There is no `ALTER TYPE ... DROP VALUE`. Taking `SELLER` back out means
    building a second type without it, rewriting `users.role` and
    `audit_logs.actor_role` onto it, and dropping the old one — a full rewrite
    of both tables, holding an exclusive lock, to remove a value that breaks
    nothing by existing. A rollback past this revision leaves the enum with
    five values and a schema that is otherwise exactly what the revision below
    built, which is the property a rollback is actually for.

    The one thing that would make this a real loss is a seller account still
    on the database when somebody downgrades *and* then rebuilds the type by
    hand. That is not a path this file can protect, and pretending to would
    mean deleting people's accounts inside a downgrade.
    """
