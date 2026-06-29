"""add index on bikes.sku

Revision ID: b7d4e2f9a1c0
Revises: 3f9a1c7b2e84
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d4e2f9a1c0'
down_revision: Union[str, Sequence[str], None] = '3f9a1c7b2e84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Index bikes.sku for cross-shop comparison (grouped/filtered by SKU)."""
    op.create_index('idx_bikes_sku', 'bikes', ['sku'])


def downgrade() -> None:
    op.drop_index('idx_bikes_sku', table_name='bikes')
