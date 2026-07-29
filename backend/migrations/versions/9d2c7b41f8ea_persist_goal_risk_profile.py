"""persist goal risk profile

Existing rows are backfilled to "moderate", which is what every edit was
already silently forcing them to, so nothing changes for them on the next save.

Revision ID: 9d2c7b41f8ea
Revises: 7c4a1e920b3d
Create Date: 2026-07-29 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d2c7b41f8ea'
down_revision: Union[str, None] = '7c4a1e920b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'goals',
        sa.Column('risk_profile', sa.String(), nullable=False, server_default='moderate'),
    )


def downgrade() -> None:
    op.drop_column('goals', 'risk_profile')
