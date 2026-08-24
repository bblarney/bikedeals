"""add bikes.product_key for cross-shop matching

Revision ID: f6a3c81b4d92
Revises: e4b1a72c9d35
Create Date: 2026-08-24 00:00:00.000000

Matching on ``sku`` alone merged unrelated products. Shops running the same
Lightspeed/Retail POS emit colliding auto-increment SKUs, so ``210000015200``
was simultaneously a $1,299 Jamis Renegade and a $9,999 AMFLOW PX Carbon — and
the detail page quoted the cheaper one as the other's lowest price.

``product_key`` is ``<canonical brand>:<sku>``. Requiring brand agreement drops
the collisions (263 of 2,185 multi-vendor SKU groups in the live feed) while
keeping every genuine match.

The normalisation below is a deliberate frozen COPY of
``scrapers.models.make_product_key`` rather than an import: a migration must
keep producing the same result years from now, even after that function moves
on. It is also not expressed as SQL, because the "don't strip a brand down to a
stub" guard does not survive translation into a regexp cleanly, and a backfill
that silently disagrees with the scraper splits every product in half.

Only ~200 distinct brands exist, so this issues one UPDATE per brand rather than
touching 38k rows individually.
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6a3c81b4d92'
down_revision: Union[str, Sequence[str], None] = 'e4b1a72c9d35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- frozen copy of scrapers.models._canonical_brand -------------------------
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_BRAND_SUFFIXES = (
    "bicycles", "bikeco", "bicycle", "cycling", "cycles", "bikes", "cycle", "bike", "bmx",
)
_MIN_BRAND_STEM = 3


def _canonical_brand(brand: str) -> str:
    stem = _NON_ALNUM.sub("", brand.lower())
    for suffix in _BRAND_SUFFIXES:
        if stem.endswith(suffix) and len(stem) - len(suffix) >= _MIN_BRAND_STEM:
            return stem[: -len(suffix)]
    return stem
# -----------------------------------------------------------------------------


def upgrade() -> None:
    op.add_column('bikes', sa.Column('product_key', sa.Text(), nullable=True))

    # Backfill so cross-shop offers keep working before the next nightly run
    # rewrites every row. btrim + the empty-string guard match the Python: a
    # whitespace-only SKU is "no SKU", not a key of "brand:".
    conn = op.get_bind()
    brands = conn.execute(
        sa.text("SELECT DISTINCT brand FROM bikes WHERE sku IS NOT NULL AND btrim(sku) <> ''")
    ).scalars().all()
    for brand in brands:
        conn.execute(
            sa.text(
                "UPDATE bikes SET product_key = :canon || ':' || btrim(sku) "
                " WHERE brand = :brand AND sku IS NOT NULL AND btrim(sku) <> ''"
            ),
            {"canon": _canonical_brand(brand), "brand": brand},
        )

    op.create_index('idx_bikes_product_key', 'bikes', ['product_key'])


def downgrade() -> None:
    op.drop_index('idx_bikes_product_key', table_name='bikes')
    op.drop_column('bikes', 'product_key')
