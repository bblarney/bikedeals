import logging
import os
import re
import time
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
from sqlalchemy import (
    Float, Text, case, cast, distinct, false, func, literal, null, select, text,
    union_all, update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from scrapers.registry import load_registry
from scrapers.utils import canonical_frame_size, vendor_slug

from api.db import get_db, get_engine
from api.models import Base, Bike, PriceEvent, ScrapeLog, SocialImage, Subscriber
from api.schemas import (
    BikeDetailResponse,
    BikeResponse,
    FiltersResponse,
    MarketPoint,
    MarketResponse,
    MessageResponse,
    OfferResponse,
    PaginatedBikes,
    PricePoint,
    StatsResponse,
    SubscribeRequest,
    UnsubscribeRequest,
    VariantResponse,
    VendorSummary,
    VendorsResponse,
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


async def _cross_shop_for_page(db, product_keys: set[str]) -> dict[str, tuple[int, float]]:
    """Cross-shop vendor count and floor price, keyed by product_key.

    Single GROUP BY: count distinct vendors per product, and take the cheapest
    price anyone is asking for it. The floor price is what makes the card's
    cross-shop line worth reading ("3 shops, from $1,649"); a bare count says
    only that the product exists elsewhere, not that it is worth the click.
    It rides on the aggregate the count already needs, so it costs no query.

    Scoped to the page's own product keys, not the whole catalogue: this used
    to aggregate every product_key in the table on every request and ship
    thousands of rows to pick out the fifty on the page. The numbers still
    deliberately ignore the request's filters (they answer "what does this
    cost elsewhere", not "within my current view"), and the IN list turns the
    full-table scan into a few probes of idx_bikes_product_key.
    """
    if not product_keys:
        return {}
    vendor_key = _vendor_key()
    rows = await db.execute(
        select(
            Bike.product_key,
            func.count(distinct(vendor_key)).label("cnt"),
            func.min(Bike.price_sale).label("min_price"),
        )
        .where(Bike.product_key.in_(product_keys), Bike.in_stock == True)  # noqa: E712
        .group_by(Bike.product_key)
        .having(func.count(distinct(vendor_key)) >= 2)
    )
    return {row.product_key: (row.cnt, row.min_price) for row in rows.all()}


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

def _saving(entity):
    """Dollars off, as an expression rather than a stored column.

    Not the same question as discount_percentage: 20% off a $13,000 bike is
    $2,600 and 60% off a $600 one is $360, so the two sorts rank the feed
    completely differently. price_original is null on anything that was never
    discounted, which coalesces to a saving of zero rather than to null.
    """
    return func.coalesce(entity.price_original, entity.price_sale) - entity.price_sale


# (attribute name or expression builder, descending?) rather than a bound Bike
# column, because the feed orders the *collapsed* subquery alias, not the base
# table.
_SORT_COLUMNS = {
    "discount_desc": ("discount_percentage", True),
    "price_asc": ("price_sale", False),
    "price_desc": ("price_sale", True),
    "saving_desc": (_saving, True),
    "clicks_desc": ("click_count", True),
}

SORT_PATTERN = "^(discount_desc|price_asc|price_desc|saving_desc|clicks_desc)$"


def _order_by(entity, sort: str):
    """Sort expression plus a deterministic tiebreak.

    Every sort key has enormous ties — half the feed sits at 0% discount — and
    without a unique tiebreak the DB is free to return them in a different order
    per query. That silently drops and repeats rows across LIMIT/OFFSET pages.
    """
    name, descending = _SORT_COLUMNS.get(sort, _SORT_COLUMNS["discount_desc"])
    col = name(entity) if callable(name) else getattr(entity, name)
    return [col.desc() if descending else col.asc(), entity.id.asc()]

CACHE_BIKES = "max-age=300"   # 5 min — bikes update after each scrape run
CACHE_FILTERS = "max-age=60"  # 1 min — filters change when vendors are added
CACHE_STATS = "max-age=300"   # 5 min — stats change only after a scrape run
CACHE_MARKET = "max-age=3600" # 1 hr: the market page only moves once a night

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
    sort: str = Query(default="discount_desc", pattern=SORT_PATTERN),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
    sku: str | None = None,
    product_key: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
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

    page_bikes = [b for b, *_ in rows]
    sizes_by_product = await _sizes_for_page(db, page_bikes, active_filters, in_stock=in_stock)
    product_cross_shop = await _cross_shop_for_page(
        db, {b.product_key for b in page_bikes if b.product_key}
    )

    results = []
    for bike_obj, location_count in rows:
        br = BikeResponse.model_validate(bike_obj)
        br.sku = bike_obj.sku
        count, min_price = (
            product_cross_shop.get(bike_obj.product_key, (0, None))
            if bike_obj.product_key
            else (0, None)
        )
        br.sku_vendor_count = count
        br.sku_min_price = min_price if count else None
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

    new_today_r = await db.execute(_distinct_listing_count(in_stock, Bike.scraped_at >= cutoff))
    # The three whole-table numbers share one SELECT, for the reason
    # /meta/filters documents: against a remote Postgres the cost is the round
    # trips, not the scans. Averaging only the discounted listings needs no
    # WHERE of its own; the CASE leaves everything else null, and AVG ignores
    # nulls.
    summary_r = await db.execute(
        select(
            func.count(Bike.vendor_name.distinct()),
            func.max(Bike.discount_percentage),
            func.round(func.avg(case((Bike.discount_percentage > 0, Bike.discount_percentage)))),
        ).where(in_stock)
    )
    shops_tracked, biggest_discount, avg_discount = summary_r.one()

    response.headers["Cache-Control"] = CACHE_STATS
    return StatsResponse(
        new_today=new_today_r.scalar_one() or 0,
        shops_tracked=shops_tracked or 0,
        biggest_discount=biggest_discount or 0,
        avg_discount=int(avg_discount or 0),
    )


@app.get("/api/v1/vendors", response_model=VendorsResponse)
@limiter.limit("120/minute")
async def get_vendors(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Every shop with stock, and how much of its range is currently cut.

    Backs both /shops and /shops/<slug>: the list is ~100 rows, so the shop page
    reads the same cached response rather than paying for an endpoint of its
    own, which is also what lets it show its own rank without recomputing one.

    Counted on _VARIANT_GROUP, the same collapse /meta/filters uses for its
    total, so a shop's "listings" here matches what /bikes?vendor= returns.
    Counting raw rows instead would report a chain's catalogue once per city:
    99 Bikes would claim ~8x its real range.

    Deliberately returns no city: a chain stores one catalogue per city, so
    filtering these counts by city would not narrow them, and a per-city count
    would read as local stock when it is nothing of the kind. Which cities a
    shop trades in comes from the YAML registry via
    frontend/src/content/shops.js, and the UI ranks local shops separately.
    """
    # One row per collapsed listing. max() over the group because a listing's
    # storefront and size rows carry the same discount; max is the aggregate
    # that says so without assuming a row order.
    listings = (
        select(
            Bike.vendor_name.label("vendor_name"),
            func.max(Bike.discount_percentage).label("discount"),
        )
        .where(Bike.in_stock == True)  # noqa: E712
        .group_by(*_VARIANT_GROUP)
        .subquery()
    )
    per_vendor = (
        select(
            listings.c.vendor_name.label("vendor_name"),
            func.count().label("listings"),
            func.sum(case((listings.c.discount > 0, 1), else_=0)).label("on_sale"),
            func.max(listings.c.discount).label("deepest_cut"),
        )
        .group_by(listings.c.vendor_name)
        .subquery()
    )
    # LEFT join: a vendor that has stock but no scrape_log row (seeded fixtures,
    # or a log trimmed by hand) still appears, just without a checked-at time.
    rows = await db.execute(
        select(
            per_vendor.c.vendor_name,
            per_vendor.c.listings,
            per_vendor.c.on_sale,
            per_vendor.c.deepest_cut,
            ScrapeLog.last_success_at,
        )
        .select_from(
            per_vendor.outerjoin(
                ScrapeLog, ScrapeLog.vendor_name == per_vendor.c.vendor_name
            )
        )
        .order_by(per_vendor.c.vendor_name)
    )

    response.headers["Cache-Control"] = CACHE_STATS
    return VendorsResponse(
        vendors=[
            VendorSummary(
                vendor_name=name,
                listings=listings_n or 0,
                on_sale=on_sale or 0,
                deepest_cut=deepest or 0,
                last_success_at=last_success_at,
            )
            for name, listings_n, on_sale, deepest, last_success_at in rows.all()
        ]
    )


# --- /meta/market -------------------------------------------------------------
#
# The site knows what is on Australian shop floors today, and nothing about what
# was on them last month: bikes is UPSERT-in-place, so yesterday's attributes are
# overwritten. These aggregations are therefore all cross-sectional: the shape
# of the current catalogue, re-derived nightly.

# Every chart below shares one row shape so the eight aggregations can be one
# UNION ALL rather than eight round trips, for the reason /meta/filters
# documents at length: against a remote Postgres the cost is the round trips,
# not the scans, and an async session cannot overlap them.
_MARKET_SQL_CHARTS = (
    "price_hist",            # price distribution, series = category
    "brands",                # listings per brand, value = avg discount
    "material_by_band",      # frame material share, series = material
    "groupset_by_category",  # groupset mix, bucket = category
    "groupset_by_band",      # groupset mix, bucket = price band
    "discount_depth",        # discounted listings per cell, value = avg depth
    "cell_totals",           # all listings per cell, the heatmap's denominator
    "discount_hist",         # how deep the discounts run
)

# What the response actually carries. The two groupset branches above are the
# raw material for three charts and are rolled up before they are emitted, so
# they do not appear here.
_MARKET_CHARTS = (
    "price_hist",
    "brands",
    "material_by_band",
    "groupset_brand_by_category",
    "groupset_ladder",
    "shifting_by_band",
    "discount_depth",
    "cell_totals",
    "discount_hist",
    "median_price",
)

# A groupset string is normalised by the scraper to '<Brand> <Tier> [<Suffix>]',
# so the brand is the first word and electronic shifting is one of three
# suffixes. Both splits happen here rather than in SQL because the substring
# functions differ between SQLite and Postgres, and here rather than in the
# browser because rolling up first drops ~350 rows the charts never plot.
_ELECTRONIC_RE = re.compile(r"(Di2|AXS|eTap)")


def _groupset_brand(point):
    return point.series.split(" ", 1)[0]


def _shifting_kind(point):
    return "Electronic" if _ELECTRONIC_RE.search(point.series) else "Mechanical"


def _rollup(points, chart, series_of, keep_bucket=True):
    """Merge points onto a coarser series, summing their counts."""
    totals = {}
    for p in points:
        key = ((p.bucket, p.bucket_rank) if keep_bucket else ("all", 0)) + (series_of(p),)
        totals[key] = totals.get(key, 0) + p.n
    return [
        MarketPoint(chart=chart, bucket=bucket, bucket_rank=rank, series=series, n=n)
        for (bucket, rank, series), n in totals.items()
    ]


# Recomputing this costs a full scan plus eight aggregations, and the answer
# only changes once a night, so one request an hour pays for it
# and the rest are served from memory. Per process, which is fine: it is a cache,
# not a source of truth. Tests set the TTL to 0 so each one sees its own seed.
_MARKET_CACHE_TTL = int(os.getenv("MARKET_CACHE_TTL", "3600"))
_market_cache = {"at": 0.0, "payload": None}

# Upper bound (exclusive) and label. The last entry is the open-ended top band.
_PRICE_BANDS = (
    (1000, "Under $1k"),
    (2000, "$1–2k"),
    (3000, "$2–3k"),
    (5000, "$3–5k"),
    (8000, "$5–8k"),
    (12000, "$8–12k"),
    (None, "$12k+"),
)

# Finer than the bands above, and log-ish rather than linear, because bike
# prices are: half the catalogue sits under $2k and the tail runs to $168k.
# Hardcoded rather than computed with log(), because SQLite's math functions are a
# compile-time option and the test suite runs on SQLite.
_PRICE_BINS = (
    (250, "<$250"), (500, "$250–500"), (750, "$500–750"), (1000, "$750–1k"),
    (1250, "$1–1.25k"), (1500, "$1.25–1.5k"), (2000, "$1.5–2k"),
    (2500, "$2–2.5k"), (3000, "$2.5–3k"), (4000, "$3–4k"), (5000, "$4–5k"),
    (6000, "$5–6k"), (7000, "$6–7k"), (8000, "$7–8k"), (10000, "$8–10k"),
    (12000, "$10–12k"), (15000, "$12–15k"), (20000, "$15–20k"),
    (None, "$20k+"),
)

_DISCOUNT_BINS = (
    (10, "1–9%"), (20, "10–19%"), (30, "20–29%"), (40, "30–39%"),
    (50, "40–49%"), (60, "50–59%"), (None, "60%+"),
)

# Cheapest-first reads as a spectrum rather than an alphabet, and puts the two
# categories people compare most (Road, Gravel) side by side.
_CATEGORY_ORDER = ("Commuter", "E-Bike", "Mountain", "Gravel", "Road")

_MARKET_BRAND_LIMIT = 25


def _bucketed(col, bins):
    """(label, rank) expressions placing `col` into `bins`.

    A CASE ladder rather than arithmetic so the bins can be unevenly spaced,
    and so one definition produces both the label and its sort order. A chart
    whose x-axis ordering disagrees with its own labels is worse than no chart.
    """
    label_whens = [(col < hi, lab) for hi, lab in bins if hi is not None]
    rank_whens = [(col < hi, i) for i, (hi, _) in enumerate(bins) if hi is not None]
    return (
        case(*label_whens, else_=bins[-1][1]),
        case(*rank_whens, else_=len(bins) - 1),
    )


def _category_rank(col):
    """_CATEGORY_ORDER as a sort rank, for charts whose x-axis is the category."""
    return case(
        *[(col == name, i) for i, name in enumerate(_CATEGORY_ORDER)],
        else_=len(_CATEGORY_ORDER),
    )


def _listing_cte():
    """One row per card the feed shows, as a CTE the aggregations share.

    Ranked and filtered to rank 1 rather than GROUP BY'd with MIN()s, so every
    attribute on the row belongs to the same variant (the one the card
    actually displays) instead of being assembled from siblings.

    Partitioned on _VARIANT_GROUP, which is exactly what _distinct_listing_count
    counts, so these charts and the header's "N bikes" cannot disagree. Note
    _VARIANT_GROUP is strictly coarser than _STOREFRONT_GROUP (same vendor, same
    URL path), so this single pass collapses a chain's cities and a product's
    sizes together; the feed needs two stages only because it carries a
    location_count through, and nothing here does.
    """
    ranked = (
        select(
            Bike.category,
            Bike.brand,
            Bike.price_sale,
            Bike.discount_percentage,
            Bike.frame_material,
            Bike.drivetrain_groupset,
            func.row_number()
            .over(
                partition_by=_VARIANT_GROUP,
                # Matches _VARIANT_PICK: cheapest fronts the card, biggest
                # discount breaks the tie, id makes it deterministic.
                order_by=(
                    Bike.price_sale.asc(),
                    Bike.discount_percentage.desc(),
                    Bike.id.asc(),
                ),
            )
            .label("variant_rank"),
        )
        .where(Bike.in_stock == True)  # noqa: E712
        .subquery()
    )
    return (
        select(
            ranked.c.category,
            ranked.c.brand,
            ranked.c.price_sale,
            ranked.c.discount_percentage,
            ranked.c.frame_material,
            ranked.c.drivetrain_groupset,
        )
        .where(ranked.c.variant_rank == 1)
        .cte("listings")
    )


def _market_branch(chart, bucket, bucket_rank, series, *where, value=None):
    """One aggregation, labelled so all eight can share a result set."""
    return (
        select(
            literal(chart).label("chart"),
            bucket.label("bucket"),
            bucket_rank.label("bucket_rank"),
            series.label("series"),
            func.count().label("n"),
            (value if value is not None else cast(null(), Float)).label("value"),
        )
        .where(*where)
        .group_by(bucket, bucket_rank, series)
    )


def _interpolated_median(bins, counts):
    """Median from a histogram, linearly interpolated inside the crossing bin.

    Exact percentiles would mean percentile_cont, which is Postgres-only while
    the test suite runs on SQLite. The bins are narrow where the catalogue is
    dense, so the error is small, but it is an approximation and the page
    labels it as one.
    """
    total = sum(counts)
    if not total:
        return None
    target = total / 2
    cumulative = 0
    for i, count in enumerate(counts):
        if not count:
            continue
        if cumulative + count >= target:
            low = bins[i - 1][0] if i else 0
            high = bins[i][0]
            if high is None:  # open-ended top bin: no upper edge to interpolate to
                return float(low)
            return float(low + (high - low) * (target - cumulative) / count)
        cumulative += count
    return None


def _market_sort_key(point):
    """Bucket order first, then series, with categories on their own scale."""
    series = point.series
    rank = _CATEGORY_ORDER.index(series) if series in _CATEGORY_ORDER else len(_CATEGORY_ORDER)
    return (point.bucket_rank, rank, -point.n, series)


@app.get("/api/v1/meta/market", response_model=MarketResponse)
@limiter.limit("120/minute")
async def get_market(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    now = time.monotonic()
    cached = _market_cache["payload"]
    if cached is None or now - _market_cache["at"] >= _MARKET_CACHE_TTL:
        cached = await _build_market(db)
        if _MARKET_CACHE_TTL > 0:
            _market_cache.update(at=now, payload=cached)

    response.headers["Cache-Control"] = CACHE_MARKET
    return cached


async def _build_market(db):
    """The eight aggregations and everything derived from them."""
    listings = _listing_cte()
    band, band_rank = _bucketed(listings.c.price_sale, _PRICE_BANDS)
    price_bin, bin_rank = _bucketed(listings.c.price_sale, _PRICE_BINS)
    discount_bin, discount_rank = _bucketed(listings.c.discount_percentage, _DISCOUNT_BINS)
    all_bucket, all_rank = literal("all"), literal(0)
    avg_discount = func.avg(listings.c.discount_percentage)
    on_sale = listings.c.discount_percentage > 0
    has_material = listings.c.frame_material.isnot(None)
    has_groupset = listings.c.drivetrain_groupset.isnot(None)

    # Brand and electronic-shifting splits are derived in Python rather than in
    # SQL: both mean picking apart the groupset string, and the substring
    # functions for that differ between SQLite and Postgres.
    stmt = union_all(
        _market_branch("price_hist", price_bin, bin_rank, listings.c.category),
        _market_branch("brands", all_bucket, all_rank, listings.c.brand,
                       value=avg_discount),
        _market_branch("material_by_band", band, band_rank,
                       listings.c.frame_material, has_material),
        _market_branch("groupset_by_category", listings.c.category,
                       _category_rank(listings.c.category),
                       listings.c.drivetrain_groupset, has_groupset),
        _market_branch("groupset_by_band", band, band_rank,
                       listings.c.drivetrain_groupset, has_groupset),
        _market_branch("discount_depth", band, band_rank, listings.c.category,
                       on_sale, value=avg_discount),
        _market_branch("cell_totals", band, band_rank, listings.c.category),
        _market_branch("discount_hist", discount_bin, discount_rank,
                       literal("all"), on_sale),
    )
    rows = (await db.execute(stmt)).all()

    grouped: dict[str, list] = {name: [] for name in _MARKET_SQL_CHARTS}
    for chart, bucket, bucket_rank, series, n, value in rows:
        grouped[chart].append(
            MarketPoint(
                chart=chart, bucket=bucket, bucket_rank=int(bucket_rank),
                series=series, n=int(n),
                value=None if value is None else round(float(value), 1),
            )
        )

    # The brand chart is a top-N bar chart and the tail is ~165 brands with a
    # handful of listings each. Truncated here rather than shipped for the
    # client to throw away.
    grouped["brands"].sort(key=lambda p: (-p.n, p.series))
    grouped["brands"] = grouped["brands"][:_MARKET_BRAND_LIMIT]

    grouped["groupset_ladder"] = _rollup(
        grouped["groupset_by_category"], "groupset_ladder",
        lambda p: p.series, keep_bucket=False,
    )
    grouped["groupset_brand_by_category"] = _rollup(
        grouped["groupset_by_category"], "groupset_brand_by_category", _groupset_brand,
    )
    grouped["shifting_by_band"] = _rollup(
        grouped["groupset_by_band"], "shifting_by_band", _shifting_kind,
    )

    total_listings = sum(p.n for p in grouped["cell_totals"])
    coverage = {
        "frame_material": sum(p.n for p in grouped["material_by_band"]),
        "drivetrain_groupset": sum(p.n for p in grouped["groupset_by_category"]),
    }

    # Median price per category, from the histogram the same query already
    # returned: no extra round trip and no percentile_cont.
    by_category: dict[str, list[int]] = {}
    for point in grouped["price_hist"]:
        counts = by_category.setdefault(point.series, [0] * len(_PRICE_BINS))
        counts[point.bucket_rank] += point.n
    grouped["median_price"] = [
        MarketPoint(chart="median_price", bucket="all", bucket_rank=0,
                    series=category, n=sum(counts), value=median)
        for category, counts in by_category.items()
        if (median := _interpolated_median(_PRICE_BINS, counts)) is not None
    ]

    # Sorted here rather than with a per-branch ORDER BY, which UNION ALL would
    # not preserve anyway. Emitting in final order means the client renders in
    # encounter order and keeps no ordering constants of its own.
    points = []
    for name in _MARKET_CHARTS:
        points.extend(sorted(grouped[name], key=_market_sort_key))

    return MarketResponse(
        total_listings=total_listings, coverage=coverage, points=points
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

    # The static pages, in the order a reader would meet them. Kept in step with
    # frontend/src/content/categories.js and content/guides.js by hand: they are
    # a different deployable, so there is nothing to import, and a stale entry
    # here costs one 404 in Search Console rather than a broken page.
    static_paths = (
        "/",
        "/deals",
        "/road-bikes",
        "/gravel-bikes",
        "/mountain-bikes",
        "/commuter-bikes",
        "/electric-bikes",
        "/guides",
        "/guides/road-bikes",
        "/guides/gravel-bikes",
        "/guides/mountain-bikes",
        "/guides/commuter-bikes",
        "/guides/electric-bikes",
        "/trends",
        "/shops",
        "/data",
        "/about",
        "/contact",
    )
    entries = [url_entry(f"{SITE_URL}{path}") for path in static_paths]
    # One <url> per shop page. Derived from the registry rather than hand-listed
    # because there are ~108 of them and the list turns over; the frontend's
    # own copy (src/content/shops.js) is generated from the same registry with
    # the same vendor_slug, so the two cannot drift.
    entries.extend(
        url_entry(f"{SITE_URL}/shops/{vendor_slug(cfg.vendor_name)}")
        for cfg in load_registry()
    )
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



@app.get("/social/{image_id}.jpg")
@limiter.limit("60/minute")
async def social_image(
    request: Request,
    image_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Serve a rendered Instagram card so Meta's fetcher can collect it.

    Instagram's publishing API takes a public URL rather than image bytes: it
    cURLs this endpoint once when a post is created, then serves its own copy.
    So this exists to be read a handful of times by one client, and the rows
    behind it are pruned after 30 days (see social/state.py). A 404 here for an
    old id is expected and harmless — the live post is unaffected.

    Serving it from our own domain rather than a git-hosted URL keeps the fetch
    a plain 200 with no cross-host redirect, which is the shape Meta's fetcher
    is happiest with, and it keeps image hosting independent of the frontend's
    build configuration.
    """
    row = await db.get(SocialImage, image_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=row.jpeg,
        media_type="image/jpeg",
        headers={
            # The id is a random token and the bytes behind it never change,
            # so this is safe to cache for as long as anything will keep it.
            "Cache-Control": "public, max-age=31536000, immutable",
            # These are post artefacts, not site content. Keep them out of
            # search results and out of the sitemap's company.
            "X-Robots-Tag": "noindex",
        },
    )
