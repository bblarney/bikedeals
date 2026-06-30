"""create price_events table

Revision ID: c1e5f3a8d2b6
Revises: b7d4e2f9a1c0
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1e5f3a8d2b6'
down_revision: Union[str, Sequence[str], None] = 'b7d4e2f9a1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change-events table: one row per first-seen / price change, not a
    daily snapshot — keeps storage bounded under the free-tier cap."""
    op.create_table(
        'price_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bike_id', sa.Text(), nullable=False),
        sa.Column('price_sale', sa.Float(), nullable=False),
        sa.Column('price_original', sa.Float(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_price_events_bike_observed', 'price_events', ['bike_id', 'observed_at']
    )


def downgrade() -> None:
    op.drop_index('idx_price_events_bike_observed', table_name='price_events')
    op.drop_table('price_events')
