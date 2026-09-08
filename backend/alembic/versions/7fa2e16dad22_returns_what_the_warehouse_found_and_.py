"""returns: what the warehouse found and what the seller decided

Eight columns on ``return_requests``, all of them about the goods rather than
the money. A refund closes the customer's side of a return; the shirt is still
in a box at the warehouse and two people have yet to answer for it — the
warehouse says what arrived, the seller says what to do about it. See
``app.returns`` for why those two answers live here and not in an audit log.

**What autogenerate wrote and this file does not.** The generated revision also
carried a dozen ``alter_column(..., server_default=None)`` lines against
``products``, ``users``, ``orders`` and three other tables. Those are not this
change: they are the difference between the developer's own
``minibozor.db`` — built by hand before Alembic existed, with SQLite defaults
this project never asked for — and the schema ``models.py`` describes. Applying
them would rewrite six unrelated tables to fix a drift that exists on exactly
one machine. They were deleted.

``inspection_note`` is the one column that needs care: it is ``NOT NULL`` and a
table with rows in it cannot take a new ``NOT NULL`` column with nothing to put
there. So it arrives with an empty-string default, which fills the existing
rows, and the default is then dropped — because ``create_all`` puts no default
on that column and ``tests/test_schema.py`` compares the two builders down to
the defaults.

Revision ID: 7fa2e16dad22
Revises: 0001_baseline
Create Date: 2026-09-08 08:37:23.986508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Autogenerate writes `sqlmodel.sql.sqltypes.AutoString()` for every `str`
# field, because that is the type SQLModel put on the column.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7fa2e16dad22'
down_revision: Union[str, Sequence[str], None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('return_requests', schema=None) as batch_op:
        # The warehouse's verdict. Nullable, and nullable is not a third
        # outcome — it is "nobody has looked yet", which is what the seller's
        # screen is empty for.
        batch_op.add_column(
            sa.Column(
                'inspection',
                sa.Enum('OK', 'DAMAGED', name='returninspection'),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                'inspection_note',
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default='',
            )
        )
        batch_op.add_column(sa.Column('inspected_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('inspected_by_id', sa.Integer(), nullable=True))

        # The seller's answer, and the clock it runs against. The clock is
        # started by the inspection rather than by the request: a seller
        # cannot be late answering a question nobody has asked them.
        batch_op.add_column(
            sa.Column(
                'seller_decision',
                sa.Enum('RELIST', 'TAKE_BACK', name='sellerreturndecision'),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column('decided_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('decision_due_at', sa.DateTime(), nullable=True))

        # Whether the shelf has already been moved for this request, by
        # whichever of the two roads got there first.
        batch_op.add_column(sa.Column('relisted_at', sa.DateTime(), nullable=True))

        batch_op.create_index(
            batch_op.f('ix_return_requests_inspection'), ['inspection'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_return_requests_seller_decision'),
            ['seller_decision'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_return_requests_decision_due_at'),
            ['decision_due_at'],
            unique=False,
        )
        # Named, unlike the ones the baseline created inside `create_table`:
        # SQLite's batch mode rebuilds the table and refuses to add a
        # constraint it cannot name. The name is not compared by
        # `tools.schema_diff` — foreign keys are compared on their columns —
        # so naming it here does not put it out of step with `create_all`.
        batch_op.create_foreign_key(
            'fk_return_requests_inspected_by_id_users',
            'users',
            ['inspected_by_id'],
            ['id'],
        )

    # The default did its job — the existing rows have an empty note — and now
    # it would be drift against `create_all`, which puts none there.
    with op.batch_alter_table('return_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'inspection_note',
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('return_requests', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_return_requests_inspected_by_id_users', type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_return_requests_decision_due_at'))
        batch_op.drop_index(batch_op.f('ix_return_requests_seller_decision'))
        batch_op.drop_index(batch_op.f('ix_return_requests_inspection'))
        batch_op.drop_column('relisted_at')
        batch_op.drop_column('decision_due_at')
        batch_op.drop_column('decided_at')
        batch_op.drop_column('seller_decision')
        batch_op.drop_column('inspected_by_id')
        batch_op.drop_column('inspected_at')
        batch_op.drop_column('inspection_note')
        batch_op.drop_column('inspection')
