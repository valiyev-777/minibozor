"""drop what the panels rebuild removed

Seven tables and two columns, and every one of them is something the API no
longer has a door for. The reasoning is in ``docs/rebuild-plan.md`` §3; the
short version per table:

* ``reviews``, ``review_likes``, ``review_tags`` — the review system is out
  whole and comes back with a screen of its own. The apps' review screen 404s
  in the meantime, which is accepted.
* ``promo_codes`` — nothing wrote one and no panel is planned that would. The
  cart still *accepts* a code and still answers with a discount field, because
  the shipped apps send and read both; see ``app.services.promo_discount``.
* ``stock_counts``, ``stock_count_lines`` — a stocktake is not in this shop's
  flow. Goods arrive through a supply and leave through a removal.
* ``courier_shifts`` — a shift is a cash-reconciliation container and
  reconciliation is not in the flow either. What a courier took at a door is
  on ``delivery_attempts.cash_collected``, where it happened.

And the two columns that pointed at the last two of those:
``delivery_attempts.shift_id`` and ``stock_movements.count_id``. Dropping them
is what makes the tables droppable.

**What autogenerate wrote and this file does not.** The generated revision
also carried a dozen ``alter_column(..., server_default=None)`` lines against
``products``, ``users``, ``orders`` and three other tables. Those are not this
change: they are the difference between the developer's own ``minibozor.db``,
built by hand before Alembic existed, and the schema ``models.py`` describes.
They were deleted — the same edit as in ``7fa2e16dad22``.

Reversible, and the downgrade is worth reading: it rebuilds all seven tables
empty. The rows are gone for good, which is the honest thing for a drop to
mean — a downgrade restores the *schema*, so an older build starts, and
nothing pretends the reviews came back.

Revision ID: aa9347d1726d
Revises: 7fa2e16dad22
Create Date: 2026-09-08 09:43:43.222076

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
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'aa9347d1726d'
down_revision: Union[str, Sequence[str], None] = '7fa2e16dad22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The two pointing columns first, then the tables they pointed at.
    #
    # Autogenerate wrote it the other way round and it does not run: SQLite's
    # batch mode rebuilds a table by *reflecting* it, and reflecting
    # `delivery_attempts` while its foreign key still names a `courier_shifts`
    # that has already been dropped raises `NoSuchTableError`. Cutting the
    # references before the referents is the order that works on both
    # dialects.
    with op.batch_alter_table('delivery_attempts', schema=None) as batch_op:
        # No `drop_constraint` beside these: the foreign key hangs off the
        # column and goes with it, and SQLite's batch mode refuses to drop a
        # constraint it cannot name.
        batch_op.drop_index(batch_op.f('ix_delivery_attempts_shift_id'))
        batch_op.drop_column('shift_id')

    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stock_movements_count_id'))
        batch_op.drop_column('count_id')

    # Then the tables, children before parents: `review_likes` names
    # `reviews`, and `stock_count_lines` names `stock_counts`.
    with op.batch_alter_table('review_likes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_review_likes_review_id'))
        batch_op.drop_index(batch_op.f('ix_review_likes_user_id'))

    op.drop_table('review_likes')
    op.drop_table('review_tags')
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reviews_product_id'))
        batch_op.drop_index(batch_op.f('ix_reviews_user_id'))

    op.drop_table('reviews')

    with op.batch_alter_table('stock_count_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stock_count_lines_count_id'))

    op.drop_table('stock_count_lines')
    with op.batch_alter_table('stock_counts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stock_counts_code'))
        batch_op.drop_index(batch_op.f('ix_stock_counts_offer_id'))
        batch_op.drop_index(batch_op.f('ix_stock_counts_status'))

    op.drop_table('stock_counts')

    with op.batch_alter_table('courier_shifts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_courier_shifts_courier_id'))
        batch_op.drop_index(batch_op.f('ix_courier_shifts_status'))

    op.drop_table('courier_shifts')

    with op.batch_alter_table('promo_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_promo_codes_code'))

    op.drop_table('promo_codes')


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('count_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_stock_movements_count_id_stock_counts',
            'stock_counts', ['count_id'], ['id'],
        )
        batch_op.create_index(batch_op.f('ix_stock_movements_count_id'), ['count_id'], unique=False)

    with op.batch_alter_table('delivery_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shift_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_delivery_attempts_shift_id_courier_shifts',
            'courier_shifts', ['shift_id'], ['id'],
        )
        batch_op.create_index(batch_op.f('ix_delivery_attempts_shift_id'), ['shift_id'], unique=False)

    op.create_table('review_likes',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('review_id', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'review_id', name=op.f('uq_review_like'))
    )
    with op.batch_alter_table('review_likes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_likes_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_review_likes_review_id'), ['review_id'], unique=False)

    op.create_table('review_tags',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('label', sa.VARCHAR(), nullable=False),
    sa.Column('sort', sa.INTEGER(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('promo_codes',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('code', sa.VARCHAR(), nullable=False),
    sa.Column('percent_off', sa.INTEGER(), nullable=False),
    sa.Column('amount_off', sa.INTEGER(), nullable=False),
    sa.Column('min_total', sa.INTEGER(), nullable=False),
    sa.Column('active', sa.BOOLEAN(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('promo_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_promo_codes_code'), ['code'], unique=1)

    op.create_table('reviews',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('product_id', sa.INTEGER(), nullable=False),
    sa.Column('order_item_id', sa.INTEGER(), nullable=True),
    sa.Column('rating', sa.INTEGER(), nullable=False),
    sa.Column('text', sa.VARCHAR(), nullable=False),
    sa.Column('variant_label', sa.VARCHAR(), nullable=False),
    sa.Column('tags', sqlite.JSON(), nullable=True),
    sa.Column('photos', sqlite.JSON(), nullable=True),
    sa.Column('likes', sa.INTEGER(), nullable=False),
    sa.Column('status', sa.VARCHAR(length=10), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reviews_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reviews_product_id'), ['product_id'], unique=False)

    op.create_table('stock_counts',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('code', sa.VARCHAR(), nullable=False),
    sa.Column('offer_id', sa.INTEGER(), nullable=False),
    sa.Column('status', sa.VARCHAR(length=9), nullable=False),
    sa.Column('note', sa.VARCHAR(), nullable=False),
    sa.Column('opened_by_id', sa.INTEGER(), nullable=True),
    sa.Column('opened_at', sa.DATETIME(), nullable=False),
    sa.Column('closed_by_id', sa.INTEGER(), nullable=True),
    sa.Column('closed_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['closed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ),
    sa.ForeignKeyConstraint(['opened_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('stock_counts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_counts_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_stock_counts_offer_id'), ['offer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_stock_counts_code'), ['code'], unique=1)

    op.create_table('stock_count_lines',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('count_id', sa.INTEGER(), nullable=False),
    sa.Column('variant_id', sa.INTEGER(), nullable=True),
    sa.Column('expected', sa.INTEGER(), nullable=False),
    sa.Column('counted', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['count_id'], ['stock_counts.id'], ),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('stock_count_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_count_lines_count_id'), ['count_id'], unique=False)

    op.create_table('courier_shifts',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('courier_id', sa.INTEGER(), nullable=False),
    sa.Column('status', sa.VARCHAR(length=6), nullable=False),
    sa.Column('opened_at', sa.DATETIME(), nullable=False),
    sa.Column('closed_at', sa.DATETIME(), nullable=True),
    sa.Column('cash_expected', sa.INTEGER(), nullable=False),
    sa.Column('cash_declared', sa.INTEGER(), nullable=True),
    sa.Column('cash_counted', sa.INTEGER(), nullable=True),
    sa.Column('counted_by_id', sa.INTEGER(), nullable=True),
    sa.Column('counted_at', sa.DATETIME(), nullable=True),
    sa.Column('orders_delivered', sa.INTEGER(), nullable=False),
    sa.Column('orders_failed', sa.INTEGER(), nullable=False),
    sa.Column('note', sa.VARCHAR(), nullable=False),
    sa.ForeignKeyConstraint(['counted_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['courier_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('courier_shifts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_courier_shifts_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_courier_shifts_courier_id'), ['courier_id'], unique=False)

    # ### end Alembic commands ###
