"""add current tax regime

Existing rows are backfilled to "new" rather than left null, because that is
what is true of them: the new regime has been the statutory default since
FY2023-24, so a user who never told us anything is in it.

Revision ID: 7c4a1e920b3d
Revises: 388acb48fac4
Create Date: 2026-07-27 22:10:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4a1e920b3d'
down_revision: Union[str, None] = '388acb48fac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'current_tax_regime',
            sa.String(),
            nullable=False,
            server_default='new',
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'current_tax_regime')
