"""The poster's durable state: the ledger, the token store, and image staging.

Exercised against the same SQLite test database the API tests use, so the
schema comes from the real models rather than a hand-rolled fixture.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from api.models import SocialImage
from social.state import (
    KEY_ACCESS_TOKEN,
    KEY_TOKEN_REFRESHED_AT,
    Store,
)
from tests.conftest import TEST_DB_FILE


@pytest.fixture
async def store(client):
    """A Store on the test database. Depends on `client` so the schema exists."""
    s = Store(f"sqlite+aiosqlite:///./{TEST_DB_FILE}")
    yield s
    await s.close()


async def test_key_values_round_trip_and_overwrite(store):
    await store.set_value("ig_user_id", "123")
    assert await store.get("ig_user_id") == "123"

    await store.set_value("ig_user_id", "456")
    assert await store.get("ig_user_id") == "456"


async def test_missing_key_is_none_not_an_error(store):
    assert await store.get("never-set") is None


async def test_set_many_writes_the_token_and_its_timestamp_together(store):
    """They have to land in one transaction. A token stored without its
    timestamp reads as 60 days old on the next run and is refreshed again
    immediately."""
    stamp = datetime.now(timezone.utc).isoformat()
    await store.set_many({KEY_ACCESS_TOKEN: "tok", KEY_TOKEN_REFRESHED_AT: stamp})

    assert await store.get(KEY_ACCESS_TOKEN) == "tok"
    assert await store.get(KEY_TOKEN_REFRESHED_AT) == stamp


async def test_recent_keys_reports_what_was_posted(store):
    await store.record_post({"id": "bike-1", "product_key": "trek:ABC"}, "media-1")
    assert await store.recent_keys(days=60) == {"trek:ABC"}


async def test_recent_keys_falls_back_to_bike_id_without_a_sku(store):
    """Must produce the same string select.ledger_key builds, or the repost
    window silently stops matching those listings."""
    await store.record_post({"id": "bike-9", "product_key": None}, "media-2")
    assert await store.recent_keys(days=60) == {"bike:bike-9"}


async def test_recent_keys_ignores_posts_outside_the_window(store, sync_engine):
    await store.record_post({"id": "bike-1", "product_key": "trek:OLD"}, "media-1")
    # Age the row past the window rather than waiting 61 days for it.
    from sqlalchemy import update

    from api.models import SocialPost

    with Session(sync_engine) as session:
        session.execute(
            update(SocialPost).values(posted_at=datetime.now(timezone.utc) - timedelta(days=61))
        )
        session.commit()

    assert await store.recent_keys(days=60) == set()


async def test_stored_images_get_distinct_unguessable_ids(store):
    first = await store.store_image(b"\xff\xd8jpeg-one")
    second = await store.store_image(b"\xff\xd8jpeg-two")

    assert first != second
    # Random, not sequential: these are public URLs, and the endpoint should not
    # be an enumerable archive of every card ever rendered.
    assert len(first) > 8


async def test_prune_drops_only_images_past_retention(store, sync_engine):
    keep = await store.store_image(b"recent")
    stale = await store.store_image(b"stale")

    with Session(sync_engine) as session:
        row = session.get(SocialImage, stale)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=31)
        session.commit()

    assert await store.prune_images(days=30) == 1

    with Session(sync_engine) as session:
        assert session.get(SocialImage, keep) is not None
        assert session.get(SocialImage, stale) is None
