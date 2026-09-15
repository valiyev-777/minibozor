"""delivery windows are gone; delivery is free

Revision ID: a91d2fc3352c
Revises: 8a32e11a5130
Create Date: 2026-09-15 08:36:44.715085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Autogenerate writes `sqlmodel.sql.sqltypes.AutoString()` for every `str`
# field, because that is the type SQLModel put on the column. Without this
# import the generated file is a NameError waiting for whoever runs it — and
# it fails at `upgrade`, on their database, not at review time. Imported
# unconditionally rather than left to `${imports}`: a migration that
# happens to touch no string column does not need it, and an unused import is
# a much smaller problem than a broken one.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a91d2fc3352c'
down_revision: Union[str, Sequence[str], None] = '8a32e11a5130'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The referring column before the table it refers to, which is the reverse
    # of the order autogenerate wrote: dropping `delivery_slots` first leaves
    # `orders.slot_id` pointing at nothing for the length of one migration, and
    # on any database that enforces foreign keys the drop is simply refused.
    #
    # No explicit `drop_constraint` either. The foreign key here was never
    # named — SQLModel declared it inline — so there is nothing for batch mode
    # to drop by name, and it does not need one: batch rebuilds the table from
    # what is left, and a constraint on a column that is gone goes with it.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('slot_id')

    with op.batch_alter_table('delivery_slots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_delivery_slots_day'))

    op.drop_table('delivery_slots')


def downgrade() -> None:
    """Downgrade schema."""
    # Mirrored: the table exists before anything points at it.
    op.create_table('delivery_slots',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('day', sa.DATE(), nullable=False),
    sa.Column('start_time', sa.VARCHAR(), nullable=False),
    sa.Column('end_time', sa.VARCHAR(), nullable=False),
    sa.Column('note', sa.VARCHAR(), nullable=False),
    sa.Column('price', sa.INTEGER(), nullable=False),
    sa.Column('express', sa.BOOLEAN(), nullable=False),
    sa.Column('capacity_left', sa.INTEGER(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('delivery_slots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_delivery_slots_day'), ['day'], unique=False)

    # Named, unlike the original. Autogenerate wrote `None` here to mirror the
    # inline SQLModel declaration, but batch mode rebuilds the table from an
    # explicit constraint list and refuses an anonymous one outright
    # (`ValueError: Constraint must have a name`). The upgrade never had to
    # name it because it drops the column and lets the rebuild take the
    # constraint with it; coming back the other way, it has to be spelled.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slot_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_orders_slot_id', 'delivery_slots', ['slot_id'], ['id']
        )

    # The seat count cannot come back: what each cancelled order gave back was
    # never written down anywhere but the row this dropped. A downgrade gets
    # the shape, not the bookings.
