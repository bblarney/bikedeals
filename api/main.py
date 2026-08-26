import logging
import os
import secrets
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import Text, distinct, false, func, literal, select, text, union_all, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from scrapers.utils import canonical_frame_size

from api.db import get_db, get_engine
from api.models import Base, Bike, PriceEvent, ScrapeLog, Subscriber
from api.schemas import (
    BikeDetailResponse,
    BikeResponse,
    FiltersResponse,
    MessageResponse,
    OfferResponse,
    PaginatedBikes,
    PricePoint,
    StatsResponse,
    SubscribeRequest,
    UnsubscribeRequest,
    VariantResponse,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("bikegrid.api")

_AFFILIATE_URLS: dict[str, str] = {
    k: v
    for k, v in {
        "Bikes Online": os.getenv("IMPACT_BIKESONLINE_URL", ""),
    }.items()
    if v
}


def _apply_affiliate_url(vendor_name: str, product_url: str) -> str:
    base = _AFFILIATE_URLS.get(vendor_name)
    if base:
        return f"{base}?u={quote(product_url, safe='')}"
    return product_url


# A competing offer is a *vendor*, not a storefront.
#
# This used to key on (vendor_name, city), which is the right identity for "where
# can I collect this" but the wrong one for "who else sells it". Chains list one
# national catalogue at one price across every city, so counting storefronts
# inflated the badge badly: SKU MEKI2192036 claimed 21 shops when it is 4
# vendors — 99 Bikes and Bicycle Centre Australia each counted once per city.
# Against the live feed that padding touched 8,097 listings (21% of the feed).
#
# Cities are not lost: an offer carries location_count and the city of its
# cheapest listing, so the UI can still say "also at 7 other 99 Bikes stores".
def _vendor_key():
    return Bike.vendor_name


# A chain's storefronts are one listing, not N.
#
# A vendor with a `cities:` list in its YAML gets one row per city, because
# bikes.id hashes the city in (scrapers.models.make_bike_id). For a chain that
# publishes one national catalogue at one price, those rows are the *same
# listing* seen from N shopfronts, and the feed showed every one of them:
# 99 Bikes was 8,616 of 38,724 in-stock rows (~1,077 products x 8 cities),
# Bicycle Centre 5,643 (~513 x 11), Bikes Online 2,875 (575 x 5). Three chains
# alone were 44% of the catalogue, and the duplicates sat next to each other in
# the grid because they sort identically.
#
# The detail endpoint already resolved the same problem for cross-shop offers
# ("a competing offer is a vendor, not a storefront", see _vendor_key). This is
# that rule applied to the feed itself: collapse to one row and carry a
# location_count so the UI can still say "at 8 stores".
#
# Grouping on product_url rather than sku is deliberate — 13% of listings have
# no SKU, and the URL is what actually distinguishes two products at one vendor.
# frame_size stays in the key so a chain's S/M/L remain separate listings.
_STOREFRONT_GROUP = (Bike.vendor_name, Bike.product_url, Bike.frame_size)

# Which storefront represents the group. Cheapest first (chains price nationally,
# but if one city undercuts, that is the honest row to show), then city, then id
# as a deterministic tiebreak so the choice is stable across requests and
# backends. The sitemap MUST order identically or it advertises a different URL
# than the feed links to.
_STOREFRONT_PICK = (Bike.price_sale.asc(), Bike.city.asc(), Bike.id.asc())


def _storefront_rank():
    return func.row_number().over(
        partition_by=_STOREFRONT_GROUP, order_by=_STOREFRONT_PICK
    ).label("storefront_rank")


def _storefront_count():
    return func.count().over(partition_by=_STOREFRONT_GROUP).label("location_count")


def _collapse_storefronts(query):
    """One row per (vendor, product, size), with a location_count.

    Window functions run after WHERE, so any filter — notably ?city= — narrows
    the rows *before* the collapse. Filtering to one city therefore leaves each
    chain listing with location_count 1, which is correct: in that city it is
    one shop.
    """
    ranked = query.add_columns(_storefront_rank(), _storefront_count()).subquery()
    return aliased(Bike, ranked), ranked


# A product's URL with any ?query stripped.
#
# Shopify puts the variant id in the query string (`/products/foo?variant=123`),
# so the raw product_url is per-*variant*, not per-product. Everything below
# that groups "the same bike in another size" needs the path.
#
# SQLite and Postgres agree on substr() but not on how to find a character:
# SQL-standard POSITION() covers Postgres, SQLite wants instr(). One @compiles
# override is cheaper than either dialect-sniffing at call sites or a stored
# column that a migration and every scraper would have to keep in step.
class _url_path(FunctionElement):
    type = Text()
    name = "url_path"
    inherit_cache = True


@compiles(_url_path)
def _compile_url_path(element, compiler, **kw):
    url = compiler.process(list(element.clauses)[0], **kw)
    return (
        f"CASE WHEN POSITION('?' IN {url}) > 0 "
        f"THEN SUBSTRING({url} FROM 1 FOR POSITION('?' IN {url}) - 1) "
        f"ELSE {url} END"
    )


@compiles(_url_path, "sqlite")
def _compile_url_path_sqlite(element, compiler, **kw):
    url = compiler.process(list(element.clauses)[0], **kw)
    return (
        f"CASE WHEN instr({url}, '?') > 0 "
        f"THEN substr({url}, 1, instr({url}, '?') - 1) "
        f"ELSE {url} END"
    )


def _url_path_py(url: str) -> str:
    """The Python mirror of _url_path, for grouping rows already fetched.

    Must agree with the SQL exactly: the feed's cards are grouped in the
    database and their size lists are grouped here, so a disagreement shows up
    as a card whose size chips are empty.
    """
    return url.split("?", 1)[0]


# One card per product, not one per size.
#
# The storefront collapse above dedupes a chain's cities; this dedupes the sizes
# (and, on Shopify, the colourways) that a shop publishes as separate variants.
# Both are the same listing wearing different hats, and the feed showed every
# one: measured over 2,000 live rows sorted the way the site opens
# (discount_desc), collapsing here removes 49% of them. On page one the "best
# deals" grid was six consecutive cards of one Giant Revolt X Advanced Pro; one
# Bikes Online product alone occupied 13 rows, which are 3 sizes in assorted
# colours at a single price.
#
# The key is the *intersection* of the two identities already in the codebase:
# (brand, model_name), which scrapers.price_sanity._variant_group argues is what
# "the same bike in a different size" means, AND the URL path, which the
# storefront collapse treats as what distinguishes two products at one vendor.
# Either alone collapses ~49.4% / 51.5% of rows and the intersection 49.2%, so
# the conservative choice costs nothing measurable and cannot merge two rows
# that the rest of the API considers different products. The cases it declines
# are shops that list one bike twice under two URLs (3 in 2,000 rows) — a real
# problem, but a different one.
_VARIANT_GROUP = (
    Bike.vendor_name,
    Bike.brand,
    Bike.model_name,
    _url_path(Bike.product_url),
)


def _variant_group_of(sq):
    """_VARIANT_GROUP rebound to a subquery's columns."""
    return (sq.c.vendor_name, sq.c.brand, sq.c.model_name, _url_path(sq.c.product_url))


# Which variant fronts the card. Cheapest first, so the headline price is one a
# buyer can actually pay; then the biggest discount, so a tie does not bury the
# deal; then id, for the same stability _STOREFRONT_PICK needs. Deliberately
# independent of ?sort= — a product that changed price when you re-sorted the
# feed would be worse than a sort that occasionally ranks on a sibling's number.
_VARIANT_PICK = (
    "price_sale",
    "discount_percentage",
    "id",
)


def _collapse_variants(collapsed):
    """One row per product, from the already-storefront-collapsed feed.

    Nested rather than folded into one SELECT because the storefront rank is
    filtered in WHERE, and a window function cannot see another window's result
    in the same query level.
    """
    sq = collapsed.subquery()
    group = _variant_group_of(sq)
    price, discount, ident = (sq.c[c] for c in _VARIANT_PICK)
    ranked = select(
        sq,
        func.row_number()
        .over(partition_by=group, order_by=(price.asc(), discount.desc(), ident.asc()))
        .label("variant_rank"),
    ).subquery()
    return aliased(Bike, ranked), ranked


def _variant_key_of(bike) -> tuple:
    """_VARIANT_GROUP evaluated in Python, for a row already fetched.

    Named to keep its distance from Bike.product_key, which is the unrelated
    cross-*shop* identity (brand:sku). This one never leaves the vendor.
    """
    return (bike.vendor_name, bike.brand, bike.model_name, _url_path_py(bike.product_url))


async def _sizes_for_page(db, bikes, filters, *, in_stock):
    """Every size behind each card on this page, keyed by _variant_key_of.

    A second round trip rather than a window aggregate: string_agg (Postgres)
    and group_concat (SQLite) do not share a name, and this endpoint already
    pays one extra trip for the cross-shop vendor counts.

    The same filters narrow this as narrow the feed, so ?size=L yields cards
    listing only L. That matches location_count, which likewise reports what is
    left after ?city= rather than what exists — a filtered feed answers
    questions about the filtered catalogue.
    """
    if not bikes:
        return {}
    wanted = {_variant_key_of(b) for b in bikes}
    query = _apply_filters(
        select(
            Bike.vendor_name, Bike.brand, Bike.model_name, Bike.product_url,
            Bike.frame_size, Bike.frame_size_canonical,
        ),
        **filters,
    )
    if in_stock:
        query = query.where(Bike.in_stock == True)  # noqa: E712
    # Narrow to the page before the exact key match happens in Python: the
    # four-column key has no index and IN over a row constructor is
    # Postgres-only, while model_name alone cuts the scan to a handful of rows.
    query = query.where(Bike.model_name.in_({b.model_name for b in bikes}))

    sizes: dict[tuple, set] = defaultdict(set)
    for row in await db.execute(query):
        key = (row.vendor_name, row.brand, row.model_name, _url_path_py(row.product_url))
        if key not in wanted:
            continue
        # Canonical where the shop published a usable size, raw as the fallback,
        # and nothing at all for "One Size" / "N/A" — a chip reading N/A is
        # worse than no chip row.
        label = row.frame_size_canonical or canonical_frame_size(row.frame_size)
        if label:
            sizes[key].add(label)
    return {key: sorted(values, key=_size_sort_key) for key, values in sizes.items()}


def _distinct_listing_count(*where_clauses):
    """COUNT of the cards the feed would show, for the trust-facing totals.

    Grouped on exactly what the feed collapses on — chain storefronts *and*
    size/colour variants — because the header's "N bikes" and the feed's own
    total must not disagree.

    GROUP BY rather than COUNT(DISTINCT a, b, c): the multi-column form is
    Postgres-only and the test suite runs on SQLite.
    """
    grouped = (
        select(*_VARIANT_GROUP)
        .where(*where_clauses)
        .group_by(*_VARIANT_GROUP)
        .subquery()
    )
    return select(func.count()).select_from(grouped)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is a zero-setup dev convenience only. On Postgres (prod) Alembic
    # owns the schema (`alembic upgrade head`); calling create_all there silently
    # creates new *tables* outside Alembic's tracking, so the next migration that
    # tries to create the same table fails with DuplicateTableError. Restrict it
    # to SQLite — mirrors scrapers/run.py. See migrations/.
    engine = get_engine()
    if engine.url.get_backend_name() == "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="BikeGrid API", version="1.0", lifespan=lifespan)

_default_origins = "https://bikegrid.com.au,https://www.bikegrid.com.au"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

# Public site origin (the frontend), used to build absolute sitemap URLs.
SITE_URL = os.getenv("SITE_URL", "https://bikegrid.com.au").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "Origin"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Log the full traceback server-side, but never leak it to the client.
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}},
    )

# (attribute, descending?) rather than a bound Bike column, because the feed
# orders the *collapsed* subquery alias, not the base table.
_SORT_COLUMNS = {
    "discount_desc": ("discount_percentage", True),
    "price_asc": ("price_sale", False),
    "price_desc": ("price_sale", True),
    "clicks_desc": ("click_count", True),
}


def _order_by(entity, sort: str):
    """Sort expression plus a deterministic tiebreak.

    Every sort key has enormous ties — half the feed sits at 0% discount — and
    without a unique tiebreak the DB is free to return them in a different order
    per query. That silently drops and repeats rows across LIMIT/OFFSET pages.
    """
    name, descending = _SORT_COLUMNS.get(sort, _SORT_COLUMNS["discount_desc"])
    col = getattr(entity, name)
    return [col.desc() if descending else col.asc(), entity.id.asc()]

CACHE_BIKES = "max-age=300"   # 5 min — bikes update after each scrape run
CACHE_FILTERS = "max-age=60"  # 1 min — filters change when vendors are added
CACHE_STATS = "max-age=300"   # 5 min — stats change only after a scrape run

_ADDED_SINCE_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


# Smallest to largest, so a size list reads the way a size chart does. Alpha
# sizes first, then centimetres, then inches, then anything uncanonicalised.
_ALPHA_ORDER = ("XXXS", "XXS", "XS", "S", "S/M", "M", "M/L", "L", "XL", "XXL", "XXXL")


def _size_sort_key(size: str | None) -> tuple:
    if not size:
        return (4, 0.0, "")
    if size in _ALPHA_ORDER:
        return (0, float(_ALPHA_ORDER.index(size)), "")
    if size.endswith("cm"):
        return (1, float(size[:-2]), "")
    if size.endswith('"'):
        return (2, float(size[:-1]), "")
    return (3, 0.0, size)


def _added_since_cutoff(added_since: str) -> datetime:
    # Quantize "now" to the start of the current hour so identical requests
    # within the hour share a cache key and a DB query plan.
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(days=_ADDED_SINCE_DAYS[added_since])


def _apply_filters(
    query,
    *,
    city: list[str],
    category: list[str],
    size: list[str],
    vendor: list[str],
    brand: list[str],
    frame_material: list[str],
    drivetrain_groupset: list[str],
    min_discount: int,
    q: str | None,
    added_since: str | None,
    min_price: float | None = None,
    max_price: float | None = None,
    sku: str | None = None,
    product_key: str | None = None,
):
    if city:
        query = query.where(func.lower(Bike.city).in_([c.lower() for c in city]))
    if category:
        query = query.where(Bike.category.in_(category))
    if size:
        # Canonicalise the *input* too, so a bookmarked ?size=Large from before
        # sizes were normalised still resolves — to "L", the same value the
        # facet now offers.
        wanted = {canonical_frame_size(s) for s in size}
        wanted.discard(None)
        # Every requested size was uncanonicalisable (e.g. a stale ?size=Chrome
        # Blue): match nothing rather than silently ignoring the filter.
        query = query.where(Bike.frame_size_canonical.in_(wanted)) if wanted else query.where(false())
    if vendor:
        query = query.where(Bike.vendor_name.in_(vendor))
    if brand:
        query = query.where(Bike.brand.in_(brand))
    if frame_material:
        query = query.where(Bike.frame_material.in_(frame_material))
    if drivetrain_groupset:
        query = query.where(Bike.drivetrain_groupset.in_(drivetrain_groupset))
    if min_discount > 0:
        query = query.where(Bike.discount_percentage >= min_discount)
    if min_price is not None:
        query = query.where(Bike.price_sale >= min_price)
    if max_price is not None:
        query = query.where(Bike.price_sale <= max_price)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(Bike.brand).like(pattern)
            | func.lower(Bike.model_name).like(pattern)
        )
    if added_since:
        query = query.where(Bike.scraped_at >= _added_since_cutoff(added_since))
    # Prefer product_key: `sku` alone collides across brands (see
    # scrapers.models.make_product_key), so "show me every shop selling this"
    # returned unrelated bikes. `sku` is kept for back-compat with any saved or
    # shared links.
    if product_key:
        query = query.where(Bike.product_key == product_key)
    elif sku:
        query = query.where(Bike.sku == sku)
    return query


@app.get("/api/v1/health")
async def health(response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Health check failed: database unreachable", exc_info=True)
        response.status_code = 503
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/bikes", response_model=PaginatedBikes)
@limiter.limit("120/minute")
async def get_bikes(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    frame_material: list[str] = Query(default=[]),
    drivetrain_groupset: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    in_stock: bool = True,
    q: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="discount_desc", pattern="^(discount_desc|price_asc|price_desc|clicks_desc)$"),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
    sku: str | None = None,
    product_key: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    # Single GROUP BY: count distinct vendors per product.
    vendor_key = _vendor_key()
    product_counts_q = (
        select(Bike.product_key, func.count(distinct(vendor_key)).label("cnt"))
        .where(Bike.product_key.isnot(None), Bike.in_stock == True)  # noqa: E712
        .group_by(Bike.product_key)
        .having(func.count(distinct(vendor_key)) >= 2)
    )
    product_counts_r = await db.execute(product_counts_q)
    product_vendor_counts: dict[str, int] = {
        row.product_key: row.cnt for row in product_counts_r.all()
    }

    active_filters = dict(
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        frame_material=frame_material, drivetrain_groupset=drivetrain_groupset,
        min_discount=min_discount, min_price=min_price, max_price=max_price,
        q=q, added_since=added_since, sku=sku, product_key=product_key,
    )
    base = _apply_filters(select(Bike), **active_filters)
    if in_stock:
        base = base.where(Bike.in_stock == True)  # noqa: E712

    # One row per chain listing rather than one per storefront...
    listing, ranked = _collapse_storefronts(base)
    collapsed = (
        select(listing, ranked.c.location_count)
        .where(ranked.c.storefront_rank == 1)
    )
    # ...then one row per product rather than one per size.
    product, pranked = _collapse_variants(collapsed)
    feed = (
        select(product, pranked.c.location_count)
        .where(pranked.c.variant_rank == 1)
    )

    count_result = await db.execute(select(func.count()).select_from(feed.subquery()))
    total = count_result.scalar_one()

    rows = (
        await db.execute(
            feed.order_by(*_order_by(product, sort)).limit(limit).offset(offset)
        )
    ).all()

    sizes_by_product = await _sizes_for_page(
        db, [b for b, *_ in rows], active_filters, in_stock=in_stock
    )

    results = []
    for bike_obj, location_count in rows:
        br = BikeResponse.model_validate(bike_obj)
        br.sku = bike_obj.sku
        br.sku_vendor_count = (
            product_vendor_counts.get(bike_obj.product_key, 0) if bike_obj.product_key else 0
        )
        br.location_count = location_count
        br.sizes = sizes_by_product.get(_variant_key_of(bike_obj), [])
        br.product_url = _apply_affiliate_url(bike_obj.vendor_name, br.product_url)
        results.append(br)

    response.headers["Cache-Control"] = CACHE_BIKES
    return PaginatedBikes(total=total, limit=limit, offset=offset, results=results)


@app.get("/api/v1/bikes/{bike_id}", response_model=BikeDetailResponse)
@limiter.limit("120/minute")
async def get_bike(
    request: Request,
    response: Response,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    primary = await db.get(Bike, bike_id)
    if primary is None:
        raise HTTPException(status_code=404, detail="Bike not found")

    # Cross-shop offers: every in-stock listing of the same product, collapsed to
    # the cheapest listing per vendor. Keyed on product_key, not sku — see
    # _vendor_key and scrapers.models.make_product_key for why matching on the
    # raw SKU merged unrelated bikes. No product_key → the bike stands alone.
    if primary.product_key:
        rows = await db.execute(
            select(Bike)
            .where(Bike.product_key == primary.product_key, Bike.in_stock == True)  # noqa: E712
            .order_by(Bike.price_sale.asc())
        )
        candidates = rows.scalars().all()
    else:
        candidates = [primary] if primary.in_stock else []

    # Rows arrive price-ascending, so the first row seen per vendor is its
    # cheapest; the rest of that vendor's storefronts only bump location_count.
    cheapest_per_vendor: dict[str, Bike] = {}
    locations: dict[str, set[str]] = {}
    for b in candidates:
        cheapest_per_vendor.setdefault(b.vendor_name, b)
        if b.city:
            locations.setdefault(b.vendor_name, set()).add(b.city)

    offers = [
        OfferResponse(
            bike_id=b.id,
            vendor_name=b.vendor_name,
            city=b.city,
            frame_size=b.frame_size,
            price_original=b.price_original,
            price_sale=b.price_sale,
            discount_percentage=b.discount_percentage,
            in_stock=b.in_stock,
            product_url=_apply_affiliate_url(b.vendor_name, b.product_url),
            last_seen_at=b.last_seen_at,
            location_count=len(locations.get(b.vendor_name, ())) or 1,
        )
        for b in sorted(cheapest_per_vendor.values(), key=lambda x: x.price_sale)
    ]

    # Other frame sizes of the same model, cheapest listing per size.
    var_rows = await db.execute(
        select(Bike)
        .where(
            Bike.brand == primary.brand,
            Bike.model_name == primary.model_name,
            Bike.in_stock == True,  # noqa: E712
        )
        .order_by(Bike.price_sale.asc())
    )
    # Group on the canonical size, not the raw one: two shops listing the same
    # model as "L" and "LARGE - 56" were offered as two different sizes to pick
    # between. Raw is the fallback so a size we cannot canonicalise still
    # appears once rather than merging into a single null bucket.
    cheapest_per_size: dict[str, Bike] = {}
    for b in var_rows.scalars().all():
        key = b.frame_size_canonical or b.frame_size
        if key not in cheapest_per_size:
            cheapest_per_size[key] = b
    variants = [
        VariantResponse(
            bike_id=b.id,
            frame_size=b.frame_size_canonical or b.frame_size,
            price_sale=b.price_sale,
            in_stock=b.in_stock,
        )
        # Alphabetical ordered sizes as L, M, S, XL. Sort on the scale instead.
        for b in sorted(
            cheapest_per_size.values(),
            key=lambda x: _size_sort_key(x.frame_size_canonical or x.frame_size),
        )
    ]

    detail = BikeDetailResponse.model_validate(primary)
    detail.sku = primary.sku
    detail.product_url = _apply_affiliate_url(primary.vendor_name, primary.product_url)
    detail.offers = offers
    detail.shop_count = len(offers)
    detail.lowest_price = offers[0].price_sale if offers else primary.price_sale
    detail.sku_vendor_count = len(offers) if len(offers) >= 2 else 0
    detail.variants = variants

    response.headers["Cache-Control"] = CACHE_BIKES
    return detail


@app.get("/api/v1/bikes/{bike_id}/price-history", response_model=list[PricePoint])
@limiter.limit("120/minute")
async def get_price_history(
    request: Request,
    response: Response,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # 404 on an unknown bike so the chart can distinguish "no such deal" from
    # "deal with no recorded changes yet" (mirrors get_bike).
    if await db.get(Bike, bike_id) is None:
        raise HTTPException(status_code=404, detail="Bike not found")

    rows = await db.execute(
        select(PriceEvent)
        .where(PriceEvent.bike_id == bike_id)
        .order_by(PriceEvent.observed_at.asc())
    )
    response.headers["Cache-Control"] = CACHE_BIKES
    return list(rows.scalars().all())


@app.post("/api/v1/bikes/{bike_id}/click", status_code=204)
@limiter.limit("30/minute")
async def record_click(
    request: Request,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        update(Bike)
        .where(Bike.id == bike_id)
        .values(click_count=Bike.click_count + 1)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bike not found")
    await db.commit()


@app.get("/api/v1/meta/filters", response_model=FiltersResponse)
@limiter.limit("120/minute")
async def get_filters(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    frame_material: list[str] = Query(default=[]),
    drivetrain_groupset: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=100),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
):
    # Faceted filters: each facet's options are computed with all *other* active
    # filters applied (the facet excludes itself). That keeps each list relevant
    # without trapping the user in a single-option facet.
    f = dict(
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        frame_material=frame_material, drivetrain_groupset=drivetrain_groupset,
        min_discount=min_discount, min_price=min_price, max_price=max_price,
        q=q, added_since=added_since,
    )

    def facet_select(name: str, col, ignored: str, *extra_where):
        """One facet's options, labelled so several can share a round trip."""
        base = (
            select(literal(name).label("facet"), col.label("value"))
            .distinct()
            .where(Bike.in_stock == True, *extra_where)  # noqa: E712
        )
        overrides = f.copy()
        overrides[ignored] = [] if isinstance(f[ignored], list) else (0 if ignored == "min_discount" else None)
        # Range filters don't narrow discrete facet options — an out-of-range
        # price shouldn't wipe out the category/brand/size lists.
        overrides["min_price"] = None
        overrides["max_price"] = None
        overrides["min_discount"] = 0
        return _apply_filters(base, **overrides)

    # The seven facets go to the database as ONE statement.
    #
    # They used to be seven separate awaits, and a note here explained that
    # asyncio.gather could not parallelise them because an async session
    # serializes within its connection. That framing had the wrong target:
    # against a remote Postgres the cost is not scan time, it is eleven
    # sequential round trips. In production this endpoint took ~0.8s while
    # /bikes — which does real work over the same table — took ~0.28s.
    #
    # UNION ALL removes the round trips instead of trying to overlap them, and
    # needs no extra connections from the pool. Each branch still filters
    # independently, so the facet-excludes-itself rule is unchanged; the label
    # column is what lets one result set be split back apart.
    in_stock_clause = Bike.in_stock == True  # noqa: E712
    facets_stmt = union_all(
        facet_select("categories", Bike.category, "category"),
        facet_select("cities", Bike.city, "city", Bike.city.isnot(None)),
        # The canonical column, never the raw one — raw is 536 spellings of
        # about fifty sizes, which is the whole point of frame_size_canonical.
        facet_select("sizes", Bike.frame_size_canonical, "size",
                     Bike.frame_size_canonical.isnot(None)),
        facet_select("vendors", Bike.vendor_name, "vendor"),
        facet_select("brands", Bike.brand, "brand"),
        facet_select("frame_materials", Bike.frame_material, "frame_material",
                     Bike.frame_material.isnot(None)),
        facet_select("drivetrain_groupsets", Bike.drivetrain_groupset, "drivetrain_groupset",
                     Bike.drivetrain_groupset.isnot(None)),
    )
    facet_rows = await db.execute(facets_stmt)
    facets: dict[str, list[str]] = {
        "categories": [], "cities": [], "sizes": [], "vendors": [],
        "brands": [], "frame_materials": [], "drivetrain_groupsets": [],
    }
    for name, value in facet_rows.all():
        facets[name].append(value)
    # Sorted here rather than with a per-branch ORDER BY, which UNION ALL would
    # not preserve anyway. Sizes sort on the size scale — sorting them as
    # strings lists a size chart as 12", 16", L, M, S, XL.
    for name, values in facets.items():
        values.sort(key=_size_sort_key if name == "sizes" else None)

    discount_r = await db.execute(
        select(func.min(Bike.discount_percentage), func.max(Bike.discount_percentage))
        .where(in_stock_clause)
    )
    # Price range is separate because it alone applies the active non-price
    # filters — the number drives the price slider's bounds.
    price_r = await db.execute(
        _apply_filters(
            select(func.min(Bike.price_sale), func.max(Bike.price_sale)).where(in_stock_clause),
            **{**f, "min_price": None, "max_price": None},
        )
    )
    # Chain-collapsed, so the header's "N bikes" matches what the feed returns.
    # A GROUP BY count, so unlike the min/max pair it cannot share a query —
    # which is why the round-trip budget is five here and not four.
    total_r = await db.execute(_distinct_listing_count(in_stock_clause))
    last_scraped_r = await db.execute(
        select(func.max(ScrapeLog.run_at)).where(ScrapeLog.status == "ok")
    )
    discount_row = discount_r.one()
    price_row = price_r.one()

    response.headers["Cache-Control"] = CACHE_FILTERS

    return FiltersResponse(
        categories=facets["categories"],
        cities=facets["cities"],
        sizes=facets["sizes"],
        vendors=facets["vendors"],
        brands=facets["brands"],
        frame_materials=facets["frame_materials"],
        drivetrain_groupsets=facets["drivetrain_groupsets"],
        discount_range={"min": discount_row[0] or 0, "max": discount_row[1] or 0},
        price_range={"min": float(price_row[0] or 0), "max": float(price_row[1] or 0)},
        total_bikes=total_r.scalar_one(),
        last_scraped_at=last_scraped_r.scalar_one(),
    )


@app.post("/api/v1/subscribe", status_code=201, response_model=MessageResponse)
@limiter.limit("5/minute")
async def subscribe(
    request: Request,
    body: SubscribeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    subscriber = Subscriber(
        email=body.email,
        token=secrets.token_urlsafe(32),
        subscribed_at=datetime.now(timezone.utc),
    )
    db.add(subscriber)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already subscribed")
    return MessageResponse(message="Subscribed")


# POST (not GET) so that email-client / CDN link prefetching cannot trigger an
# accidental unsubscribe, and so the token is not captured in proxy access logs.
@app.post("/api/v1/unsubscribe", status_code=200, response_model=MessageResponse)
@limiter.limit("10/minute")
async def unsubscribe(
    request: Request,
    body: UnsubscribeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Subscriber).where(Subscriber.token == body.token))
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(subscriber)
    await db.commit()
    return MessageResponse(message="Unsubscribed")


@app.get("/api/v1/meta/stats", response_model=StatsResponse)
@limiter.limit("120/minute")
async def get_stats(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    in_stock = Bike.in_stock == True  # noqa: E712
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    new_today_r        = await db.execute(_distinct_listing_count(in_stock, Bike.scraped_at >= cutoff))
    shops_r            = await db.execute(select(func.count(Bike.vendor_name.distinct())).where(in_stock))
    biggest_discount_r = await db.execute(select(func.max(Bike.discount_percentage)).where(in_stock))
    avg_discount_r     = await db.execute(
        select(func.round(func.avg(Bike.discount_percentage))).where(in_stock, Bike.discount_percentage > 0)
    )

    response.headers["Cache-Control"] = CACHE_STATS
    return StatsResponse(
        new_today=new_today_r.scalar_one() or 0,
        shops_tracked=shops_r.scalar_one() or 0,
        biggest_discount=biggest_discount_r.scalar_one() or 0,
        avg_discount=int(avg_discount_r.scalar_one() or 0),
    )


@app.get("/sitemap.xml")
@limiter.limit("30/minute")
async def sitemap(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # One <url> per in-stock bike detail page so Google can discover them, plus
    # the core landing pages. Without this the detail pages never get crawled.
    #
    # Chain storefronts are collapsed with the same rule (and the same pick
    # order) the feed uses, so we advertise exactly the URL the feed links to.
    #
    # Size variants are deliberately NOT collapsed here, though the feed does
    # collapse them. The two are answering different questions: the feed is
    # asking what a browsing human should scroll past, and a size is not a
    # reason to show the same bike twice; the sitemap is asking what pages
    # exist, and /bikes/<id> for an L is a distinct, canonical, self-describing
    # page that can rank for "… size L". Collapsing here would drop roughly half
    # the indexable pages on the site — a real SEO decision, not a side effect
    # of a feed change, and not one to make silently.
    # Previously this listed all 38,725 rows — ~44% of them near-identical pages
    # for one chain product in 8-11 cities, which is duplicate content pointed
    # at Google on purpose, on a domain that also has a finite crawl budget.
    ranked = (
        select(Bike.id, Bike.last_seen_at, _storefront_rank())
        .where(Bike.in_stock == True)  # noqa: E712
        .subquery()
    )
    rows = await db.execute(
        select(ranked.c.id, ranked.c.last_seen_at)
        .where(ranked.c.storefront_rank == 1)
        .order_by(ranked.c.last_seen_at.desc())
    )

    def url_entry(loc: str, lastmod: datetime | None = None) -> str:
        parts = [f"<loc>{xml_escape(loc)}</loc>"]
        if lastmod is not None:
            parts.append(f"<lastmod>{lastmod.date().isoformat()}</lastmod>")
        return f"<url>{''.join(parts)}</url>"

    entries = [url_entry(f"{SITE_URL}/")]
    entries.extend(
        url_entry(f"{SITE_URL}/bikes/{bike_id}", last_seen_at)
        for bike_id, last_seen_at in rows.all()
    )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(entries)}"
        "</urlset>"
    )
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": "max-age=3600"},
    )
