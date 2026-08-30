"""retire George's Bike Shop

Revision ID: 595a0ae4dcf0
Revises: b8e2d5c47f13
Create Date: 2026-08-30 12:23:59.559008

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '595a0ae4dcf0'
down_revision: Union[str, Sequence[str], None] = 'b8e2d5c47f13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The shop left the registry (its YAML is deleted in the same commit), which
# stops it being *scraped* but does nothing to the rows it already has: nothing
# in the run prunes a vendor no config produces anymore, and mark_stale only
# ever runs for vendors that are still scraped. Its last successful scrape was
# from a residential IP in early August, so without this migration the site
# would keep serving a frozen Perth catalogue — still flagged in stock, still
# eligible for the daily Instagram pick — with a "last seen" date that could
# never change again.
_RETIRED_VENDORS = ("George's Bike Shop",)


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

    # social_posts rows are deliberately left alone. That table is a ledger of
    # what was actually published to Instagram, not a view of current inventory:
    # `SocialState.recent_keys` only ever reads product_key/bike_id out of it and
    # never joins bikes, so a row whose bike is gone still reads correctly, and
    # the post it records is still live on the account.


def downgrade() -> None:
    raise NotImplementedError(
        "not reversible: this vendor's listings and price history are deleted "
        "outright, and with its config gone there is no scrape that would "
        "recreate them. Re-adding the shop means re-adding its YAML and letting "
        "the nightly run repopulate it from scratch."
    )
