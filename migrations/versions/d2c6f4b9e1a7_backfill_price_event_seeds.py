"""backfill price_event seed anchors for pre-existing bikes

Revision ID: d2c6f4b9e1a7
Revises: 9aef44225dc3
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd2c6f4b9e1a7'
down_revision: Union[str, Sequence[str], None] = '9aef44225dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The price_events table was created 2026-06-30, but bikes had been scraped
# into the bikes table since 2026-05-26. A seed/anchor event is only written on
# a *new* listing (a `prior` miss in scrapers.db.price_event_rows); every bike
# that already existed on 2026-06-30 was a `prior` hit on the first scrape
# after, so it never got an anchor. Those bikes therefore need TWO real price
# changes to reach the >=2 events the chart requires
# (frontend PriceHistoryChart) instead of one, so almost none render a graph.
#
# This backfills one anchor event per bike, priced at the bike's current
# price and dated at its first-seen timestamp (bikes.scraped_at), so any
# single price change — already recorded or future — yields a 2-point graph.
def upgrade() -> None:
    bikes = sa.table(
        "bikes",
        sa.column("id", sa.Text),
        sa.column("price_sale", sa.Float),
        sa.column("price_original", sa.Float),
        sa.column("scraped_at", sa.DateTime(timezone=True)),
    )
    price_events = sa.table(
        "price_events",
        sa.column("bike_id", sa.Text),
        sa.column("price_sale", sa.Float),
        sa.column("price_original", sa.Float),
        sa.column("observed_at", sa.DateTime(timezone=True)),
    )

    # Only seed bikes that lack an anchor at/before their first-seen time.
    # Bikes added *after* 2026-06-30 already got a real seed at scraped_at via
    # the scraper, so an event with observed_at <= scraped_at already exists for
    # them and this excludes them — leaving only the pre-existing catalog that
    # the rollout missed. Guards against double-seeding if replayed, too.
    already_anchored = (
        sa.select(sa.literal(1))
        .select_from(price_events)
        .where(
            price_events.c.bike_id == bikes.c.id,
            price_events.c.observed_at <= bikes.c.scraped_at,
        )
        .exists()
    )

    seed_select = sa.select(
        bikes.c.id,
        bikes.c.price_sale,
        bikes.c.price_original,
        bikes.c.scraped_at,
    ).where(~already_anchored)

    # Single server-side INSERT ... SELECT: no per-row Python round trips, so
    # it stays fast against production even for the full catalog.
    op.get_bind().execute(
        price_events.insert().from_select(
            ["bike_id", "price_sale", "price_original", "observed_at"],
            seed_select,
        )
    )


def downgrade() -> None:
    raise NotImplementedError(
        "not reversible: backfilled seeds are anchored at bikes.scraped_at, "
        "the same timestamp organically-created seeds use, so there's no marker "
        "to tell them apart and delete only the ones this migration inserted"
    )
