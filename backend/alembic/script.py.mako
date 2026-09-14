"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Autogenerate writes `sqlmodel.sql.sqltypes.AutoString()` for every `str`
# field, because that is the type SQLModel put on the column. Without this
# import the generated file is a NameError waiting for whoever runs it — and
# it fails at `upgrade`, on their database, not at review time. Imported
# unconditionally rather than left to `${"${imports}"}`: a migration that
# happens to touch no string column does not need it, and an unused import is
# a much smaller problem than a broken one.
import sqlmodel
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
