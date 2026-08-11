"""retire Cranks, Cycle Co-op and NRG Cycles

Revision ID: e4b1a72c9d35
Revises: d2c6f4b9e1a7
Create Date: 2026-08-11 20:14:02.118374

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e4b1a72c9d35'
down_revision: Union[str, Sequence[str], None] = 'd2c6f4b9e1a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# These three shops left the registry (their YAMLs are deleted in the same
# commit), which stops them being *scraped* but does nothing to the rows they
# already have: nothing in the run prunes a vendor that no config produces
# anymore, and mark_stale only ever runs for vendors that are still scraped. So
# without this migration the site would keep serving three dead shops'
# inventory — Cycle Co-op's storefront is closed, NRG's listings would freeze at
# their last successful scrape, and Cranks' rows point at WooCommerce URLs the
# replatformed site no longer serves — with the "last seen" date frozen and no
# way for it ever to change.
_RETIRED_VENDORS = ("Cranks", "Cycle Co-op", "NRG Cycles")


def upgrade() -> None:
    bind = op.get_bind()
    bikes = sa.table(
        "bikes",
        sa.column("id", sa.Text),
        sa.column("vendor_name", sa.Text),
    )
    price_events = sa.table(
        "price_events",
        sa.column("bike_id", sa.Text),
    )
    scrape_log = sa.table(
        "scrape_log",
        sa.column("vendor_name", sa.Text),
    )

    # price_events has no hard FK to bikes (see api/models.py), so deleting the
    # bikes first would orphan its rows rather than cascade to them.
    bind.execute(
        price_events.delete().where(
            price_events.c.bike_id.in_(
                sa.select(bikes.c.id).where(bikes.c.vendor_name.in_(_RETIRED_VENDORS))
            )
        )
    )
    bind.execute(bikes.delete().where(bikes.c.vendor_name.in_(_RETIRED_VENDORS)))
    bind.execute(scrape_log.delete().where(scrape_log.c.vendor_name.in_(_RETIRED_VENDORS)))


def downgrade() -> None:
    raise NotImplementedError(
        "not reversible: these vendors' listings and price history are deleted "
        "outright, and with their configs gone there is no scrape that would "
        "recreate them. Re-adding a shop means re-adding its YAML and letting "
        "the nightly run repopulate it from scratch."
    )
