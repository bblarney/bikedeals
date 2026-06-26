"""scrape_log one row per vendor

Revision ID: 3f9a1c7b2e84
Revises: 8c24986e1289
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f9a1c7b2e84'
down_revision: Union[str, Sequence[str], None] = '8c24986e1289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Collapse scrape_log to one row per vendor."""
    op.add_column(
        'scrape_log',
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill last_success_at from full history BEFORE collapsing rows, so a
    # vendor whose latest run failed still retains its last successful run_at.
    op.execute(
        """
        UPDATE scrape_log t
        SET last_success_at = s.max_ok
        FROM (SELECT vendor_name, MAX(run_at) AS max_ok
              FROM scrape_log WHERE status = 'ok' GROUP BY vendor_name) s
        WHERE t.vendor_name = s.vendor_name
        """
    )
    # Keep only the newest row (highest id) per vendor.
    op.execute(
        """
        DELETE FROM scrape_log a USING scrape_log b
        WHERE a.vendor_name = b.vendor_name AND a.id < b.id
        """
    )
    op.create_unique_constraint(
        'uq_scrape_log_vendor', 'scrape_log', ['vendor_name']
    )


def downgrade() -> None:
    """Revert to append-style scrape_log."""
    op.drop_constraint('uq_scrape_log_vendor', 'scrape_log', type_='unique')
    op.drop_column('scrape_log', 'last_success_at')
