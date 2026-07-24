"""dedupe giant franchise vendor names

Revision ID: 9aef44225dc3
Revises: c1e5f3a8d2b6
Create Date: 2026-07-23 16:33:15.541679

"""
import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9aef44225dc3'
down_revision: Union[str, Sequence[str], None] = 'c1e5f3a8d2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# scrapers/vendors/giant{brisbane,goldcoast,osbornepark,sunshinecoast,sydney,
# wollongong}.yaml previously all shared vendor_name "Giant" for 6 distinct
# franchise shops, disambiguated only by city. This collided in mark_stale()
# (filters on vendor_name only, no city) and scrape_log (unique on
# vendor_name) — one store's scrape could flip a *different* store's in-stock
# bikes to out-of-stock, and the 6 stores overwrote each other's scrape_log
# row. The yaml configs now each use a unique vendor_name; this backfills
# existing bikes rows to match by city, so they keep getting matched (and
# correctly mark_stale'd) by the next scrape instead of silently orphaning
# under a vendor_name no config produces anymore.
_CITY_TO_VENDOR_NAME = {
    "Brisbane": "Giant Brisbane",
    "Gold Coast": "Giant Gold Coast",
    "Perth": "Giant Osborne Park",
    "Sunshine Coast": "Giant Sunshine Coast",
    "Sydney": "Giant Sydney",
    "Wollongong": "Giant Wollongong",
}


def _make_bike_id(vendor_name: str, product_url: str, frame_size: str, city: str | None) -> str:
    # Mirrors scrapers/models.make_bike_id exactly, as of this migration's
    # authoring. Deliberately NOT imported from there: this is a historical
    # data fix and must keep producing the same ids even if that function's
    # hashing scheme changes later.
    key = f"{vendor_name}::{city or ''}::{product_url}::{frame_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def upgrade() -> None:
    bind = op.get_bind()
    bikes = sa.table(
        "bikes",
        sa.column("id", sa.Text),
        sa.column("vendor_name", sa.Text),
        sa.column("city", sa.Text),
        sa.column("product_url", sa.Text),
        sa.column("frame_size", sa.Text),
    )
    price_events = sa.table(
        "price_events",
        sa.column("bike_id", sa.Text),
    )
    scrape_log = sa.table(
        "scrape_log",
        sa.column("vendor_name", sa.Text),
    )

    bike_updates = []
    price_event_updates = []
    for city, new_vendor_name in _CITY_TO_VENDOR_NAME.items():
        rows = bind.execute(
            sa.select(bikes.c.id, bikes.c.product_url, bikes.c.frame_size)
            .where(bikes.c.vendor_name == "Giant", bikes.c.city == city)
        ).fetchall()
        for old_id, product_url, frame_size in rows:
            # bikes.id is derived from vendor_name (see make_bike_id), so the
            # rename must recompute it too, or tomorrow's scrape — which will
            # compute this same new id — inserts a fresh row instead of
            # updating this one, leaving this row orphaned under the old id.
            new_id = _make_bike_id(new_vendor_name, product_url, frame_size, city)
            bike_updates.append({"old_id": old_id, "new_id": new_id, "new_vendor_name": new_vendor_name})
            price_event_updates.append({"old_id": old_id, "new_id": new_id})

    # Batched as a single executemany call per table instead of one Python
    # round trip per row: an earlier version of this migration looped
    # bind.execute() per row and took over an hour against production for a
    # few thousand rows, almost entirely spent on network round-trip latency.
    if price_event_updates:
        bind.execute(
            price_events.update()
            .where(price_events.c.bike_id == sa.bindparam("old_id"))
            .values(bike_id=sa.bindparam("new_id")),
            price_event_updates,
        )
    if bike_updates:
        bind.execute(
            bikes.update()
            .where(bikes.c.id == sa.bindparam("old_id"))
            .values(id=sa.bindparam("new_id"), vendor_name=sa.bindparam("new_vendor_name")),
            bike_updates,
        )

    # scrape_log is unique on vendor_name and only ever held the *last* of the
    # 6 stores to finish under the shared "Giant" name — there's no per-store
    # history to recover from it. Drop it; each store gets a fresh row under
    # its own name on its next scrape.
    bind.execute(scrape_log.delete().where(scrape_log.c.vendor_name == "Giant"))


def downgrade() -> None:
    raise NotImplementedError(
        "not reversible: the vendor_name collision being fixed here is the "
        "bug, and the shared 'Giant' scrape_log row was discarded in "
        "upgrade() with no per-store history to restore it from"
    )
