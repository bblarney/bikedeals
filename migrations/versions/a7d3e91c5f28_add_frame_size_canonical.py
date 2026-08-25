"""add bikes.frame_size_canonical

Revision ID: a7d3e91c5f28
Revises: f6a3c81b4d92
Create Date: 2026-08-25 00:00:00.000000

The size facet listed 536 distinct values for what is really about fifty sizes:
thirty spellings of Large ("L", "Lg", "LGE", "LRG", "LARGE - 56",
"Large 29\" Wheels", "L (Large 170cm - 185cm)"), colours that leaked through
extract_frame_size's fallback ("Chrome Blue", "Light Blue"), tyre widths
("28mm"), top-tube lengths ("20.50 TT RSD") and "Frameset only". Picking "M"
from the dropdown could not return every medium.

``frame_size`` is left exactly as it is, because ``make_bike_id`` hashes it:
rewriting it would change every bike's id, breaking every detail URL, every
shared link and the bike_id join that price_events depends on. The canonical
value goes in a new nullable column instead, and NULL means "names no usable
size" rather than "medium".

The normalisation below is a frozen COPY of scrapers.utils.canonical_frame_size,
following the precedent set by f6a3c81b4d92 for product_key: a migration must
keep producing the same result years from now, even after that function moves
on, and a backfill that silently disagrees with the scraper would file half the
catalogue under the wrong size.

Only ~536 distinct raw sizes exist, so this issues one UPDATE per distinct value
rather than touching 38k rows individually.
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7d3e91c5f28'
down_revision: Union[str, Sequence[str], None] = 'f6a3c81b4d92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- frozen copy of scrapers.utils.canonical_frame_size -----------------------
_ALPHA_PATTERNS = (
    (r"(?:3x|xxx)[\s-]*small|3xs|4xs", "XXXS"),
    (r"(?:2x|xx)[\s-]*small|xxs|2xs", "XXS"),
    (r"x[\s-]*small|extra[\s-]*small|\bxs\b", "XS"),
    (r"(?:3x|xxx)[\s-]*large|3xl|xxxl|4xl", "XXXL"),
    (r"(?:2x|xx)[\s-]*large|xxl|2xl", "XXL"),
    (r"x[\s-]*large|extra[\s-]*large|\bxl\b|\bxlg\b", "XL"),
    (r"\bs[\s/\\-]m\b|\bsmall[\s/\\-]medium\b", "S/M"),
    (r"\bm[\s/\\-]?l\b|\bmedium[\s/\\-]large\b", "M/L"),
    (r"\bsmall\b|\bsml\b|\bsm\b|\bs\b", "S"),
    (r"\bmedium\b|\bmed\b|\bmd\b|\bm\b", "M"),
    (r"\blarge\b|\blge\b|\blrg\b|\blg\b|\bl\b", "L"),
)
_ALPHA_RE = tuple((re.compile(p, re.IGNORECASE), c) for p, c in _ALPHA_PATTERNS)
_S_SIZING = {"s1": "XS", "s2": "S", "s3": "M", "s4": "L", "s5": "XL", "s6": "XXL"}
_S_SIZING_RE = re.compile(r"^\s*(s[1-6])\s*$", re.IGNORECASE)
_ALPHA_CM_RE = re.compile(r"^\s*(xxs|xs|s|m|l|xl|xxl)\s*[-]?\s*\d{2}(?:\.\d)?\s*$", re.IGNORECASE)
_CM_MIN, _CM_MAX = 38.0, 68.0
_CM_MARKED_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s*cm\b", re.IGNORECASE)
_CM_BARE_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\b")
_MM_RE = re.compile(r"\b([3-6]\d{2})\b")
_INCH_SIZES = frozenset({12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24})
_INCH_MARKED_RE = re.compile(r"\b(\d{2})\s*(?:\"|''|in\b|inch\b|inches\b)", re.IGNORECASE)
_INCH_BARE_RE = re.compile(r"^\s*(\d{2})\s*$")
_UNKNOWN_SIZES = frozenset({"n/a", "na", "one size", "onesize", "", "-"})
_TOP_TUBE_RE = re.compile(r"\bTT\b")


def _format_cm(value: str) -> str:
    return f"{float(value):g}cm"


def canonical_frame_size(raw):
    if not raw:
        return None
    text = " ".join(str(raw).split())
    if text.lower() in _UNKNOWN_SIZES or _TOP_TUBE_RE.search(text):
        return None
    s_sized = _S_SIZING_RE.match(text)
    if s_sized:
        return _S_SIZING[s_sized.group(1).lower()]
    welded = _ALPHA_CM_RE.match(text)
    if welded:
        return welded.group(1).upper()
    for pattern, canon in _ALPHA_RE:
        if pattern.search(text):
            return canon
    marked_cm = _CM_MARKED_RE.search(text)
    if marked_cm and _CM_MIN <= float(marked_cm.group(1)) <= _CM_MAX:
        return _format_cm(marked_cm.group(1))
    marked_inch = _INCH_MARKED_RE.search(text)
    if marked_inch and int(marked_inch.group(1)) in _INCH_SIZES:
        return f'{int(marked_inch.group(1))}"'
    bare_inch = _INCH_BARE_RE.match(text)
    if bare_inch and int(bare_inch.group(1)) in _INCH_SIZES:
        return f'{int(bare_inch.group(1))}"'
    for candidate in _CM_BARE_RE.findall(text):
        if _CM_MIN <= float(candidate) <= _CM_MAX:
            return _format_cm(candidate)
    millimetres = _MM_RE.search(text)
    if millimetres and _CM_MIN <= int(millimetres.group(1)) / 10 <= _CM_MAX:
        return _format_cm(f"{int(millimetres.group(1)) / 10:g}")
    return None
# -----------------------------------------------------------------------------


def upgrade() -> None:
    op.add_column('bikes', sa.Column('frame_size_canonical', sa.Text(), nullable=True))

    # Backfill now rather than waiting for the nightly run to rewrite every row:
    # between deploy and that run the size filter reads this column, and an
    # unpopulated one means the filter silently matches nothing.
    conn = op.get_bind()
    raw_sizes = [
        row[0]
        for row in conn.execute(
            sa.text("SELECT DISTINCT frame_size FROM bikes WHERE frame_size IS NOT NULL")
        )
    ]
    for raw in raw_sizes:
        canonical = canonical_frame_size(raw)
        if canonical is None:
            continue
        conn.execute(
            sa.text(
                "UPDATE bikes SET frame_size_canonical = :canonical WHERE frame_size = :raw"
            ),
            {"canonical": canonical, "raw": raw},
        )

    op.create_index('idx_bikes_frame_size_canonical', 'bikes', ['frame_size_canonical'])
    # The feed's composite index covered the raw column, which the filter no
    # longer reads. Repoint it or every filtered size query loses its index.
    op.drop_index('idx_bikes_cat_size_vendor', table_name='bikes')
    op.create_index(
        'idx_bikes_cat_size_vendor',
        'bikes',
        ['category', 'frame_size_canonical', 'vendor_name'],
    )


def downgrade() -> None:
    op.drop_index('idx_bikes_cat_size_vendor', table_name='bikes')
    op.create_index(
        'idx_bikes_cat_size_vendor', 'bikes', ['category', 'frame_size', 'vendor_name']
    )
    op.drop_index('idx_bikes_frame_size_canonical', table_name='bikes')
    op.drop_column('bikes', 'frame_size_canonical')
