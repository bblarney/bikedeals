"""Shared test fixtures.

The API is exercised against an isolated on-disk SQLite database (created via
the app's own lifespan/`create_all`). Seeding and per-test cleanup use a
*synchronous* SQLAlchemy session against the same file — this reuses the ORM
models (so Python-side column defaults apply) and avoids juggling the async
event loop that `TestClient` runs in.
"""
import os
from datetime import datetime, timezone

# Must be set before api.* is imported, since api.db reads DATABASE_URL lazily.
TEST_DB_FILE = "_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./{TEST_DB_FILE}")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
# /meta/market memoises its whole payload for an hour in production. Each test
# seeds its own catalogue, so the cache has to be off or the second test to hit
# the endpoint asserts against the first one's data.
os.environ.setdefault("MARKET_CACHE_TTL", "0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

import api.main as main_module
from api.models import Bike, PriceEvent, ScrapeLog, SocialImage, SocialPost, SocialState, Subscriber
from scrapers.models import make_product_key
from scrapers.utils import canonical_frame_size

_SYNC_URL = f"sqlite:///./{TEST_DB_FILE}"


def _try_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        # The async engine may still hold the SQLite file open (esp. on
        # Windows). Harmless: the file is gitignored and rebuilt next run.
        pass


@pytest.fixture(scope="session")
def client():
    """A TestClient whose lifespan creates the schema in the test DB."""
    _try_remove(TEST_DB_FILE)
    with TestClient(main_module.app) as c:
        yield c
    _try_remove(TEST_DB_FILE)


@pytest.fixture
def sync_engine(client):
    # Depends on `client` so the schema exists before we connect.
    engine = create_engine(_SYNC_URL, connect_args={"timeout": 10})
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(sync_engine):
    """Empty all tables before each test for isolation."""
    with Session(sync_engine) as s:
        for model in (Bike, Subscriber, ScrapeLog, PriceEvent, SocialImage, SocialPost, SocialState):
            s.execute(delete(model))
        s.commit()
    yield


def make_bike(**overrides):
    """Build a Bike with sensible defaults; override any field per test."""
    now = datetime.now(timezone.utc)
    data = dict(
        id="bike-1",
        vendor_name="Test Cycles",
        city="Sydney",
        brand="Trek",
        model_name="Domane SL5",
        category="Road",
        frame_size="M",
        price_original=2000.0,
        price_sale=1500.0,
        discount_percentage=25,
        in_stock=True,
        product_url="https://shop.example.com/p/1",
        image_url="https://shop.example.com/i/1.jpg",
        scraped_at=now,
        last_seen_at=now,
    )
    data.update(overrides)
    # Derive product_key exactly as the scraper does rather than letting tests
    # hand-set it, so a test can't assert on a pairing production would never
    # produce. An explicit product_key= override still wins.
    data.setdefault("product_key", make_product_key(data["brand"], data.get("sku")))
    # Same reasoning as product_key: derive it the way the scraper does, so a
    # test cannot assert on a size pairing production would never produce.
    data.setdefault("frame_size_canonical", canonical_frame_size(data["frame_size"]))
    return Bike(**data)


@pytest.fixture
def seed(sync_engine):
    """Insert the given Bike objects (or a default one) into the test DB."""
    def _seed(*bikes):
        bikes = bikes or (make_bike(),)
        with Session(sync_engine) as s:
            s.add_all(list(bikes))
            s.commit()
        return bikes
    return _seed
