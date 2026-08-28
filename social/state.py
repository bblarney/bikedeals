"""Durable state for the poster: the token, the ledger, and the image staging.

Everything here talks to the same Postgres the scraper writes to, reached over
the tailnet. Deliberately does NOT call ``create_all``: per CLAUDE.md, Alembic
owns the Postgres schema, and creating these tables outside its tracking would
break the next migration.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.models import SocialImage, SocialPost, SocialState

# How long a rendered card is kept after publishing. Instagram takes its own
# copy at publish time, so this only has to outlive the fetch; 30 days is slack
# for debugging a bad-looking post, not a retention requirement.
IMAGE_RETENTION_DAYS = 30

KEY_ACCESS_TOKEN = "ig_access_token"
KEY_TOKEN_REFRESHED_AT = "ig_token_refreshed_at"
KEY_USER_ID = "ig_user_id"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    """Thin async wrapper over the three social tables."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._session = async_sessionmaker(self._engine, expire_on_commit=False)

    @classmethod
    def from_env(cls) -> "Store":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required to publish (set it in the workflow).")
        return cls(url)

    async def close(self) -> None:
        await self._engine.dispose()

    # --- key/value ---------------------------------------------------------

    async def get(self, key: str) -> str | None:
        async with self._session() as session:
            row = await session.get(SocialState, key)
            return row.value if row else None

    async def set_value(self, key: str, value: str) -> None:
        async with self._session() as session:
            row = await session.get(SocialState, key)
            if row is None:
                session.add(SocialState(key=key, value=value, updated_at=_now()))
            else:
                row.value = value
                row.updated_at = _now()
            await session.commit()

    async def set_many(self, values: dict[str, str]) -> None:
        """Write several keys in one transaction.

        Used for the token refresh, where the new token and its timestamp must
        land together: a token written without its timestamp would look 60 days
        old on the next run and be refreshed again immediately.
        """
        async with self._session() as session:
            for key, value in values.items():
                row = await session.get(SocialState, key)
                if row is None:
                    session.add(SocialState(key=key, value=value, updated_at=_now()))
                else:
                    row.value = value
                    row.updated_at = _now()
            await session.commit()

    # --- the ledger --------------------------------------------------------

    async def recent_keys(self, days: int) -> set[str]:
        """Ledger keys posted within the window, in the form select.ledger_key builds."""
        cutoff = _now() - timedelta(days=days)
        async with self._session() as session:
            rows = await session.execute(
                select(SocialPost.product_key, SocialPost.bike_id).where(
                    SocialPost.posted_at >= cutoff
                )
            )
            keys = set()
            for product_key, bike_id in rows.all():
                keys.add(product_key or f"bike:{bike_id}")
            return keys

    async def record_post(self, bike: dict, ig_media_id: str | None) -> None:
        async with self._session() as session:
            session.add(
                SocialPost(
                    product_key=bike.get("product_key"),
                    bike_id=bike["id"],
                    ig_media_id=ig_media_id,
                    posted_at=_now(),
                )
            )
            await session.commit()

    # --- image staging -----------------------------------------------------

    async def store_image(self, jpeg: bytes) -> str:
        """Stage a rendered card and return the id its public URL is built from.

        The id is random rather than sequential. These images are public by
        design (Instagram has to fetch one without credentials), so this is not
        a security control; it just stops the endpoint being an enumerable
        archive of every card ever rendered.
        """
        image_id = secrets.token_urlsafe(16)
        async with self._session() as session:
            session.add(SocialImage(id=image_id, jpeg=jpeg, created_at=_now()))
            await session.commit()
        return image_id

    async def prune_images(self, days: int = IMAGE_RETENTION_DAYS) -> int:
        """Drop staged cards past the retention window.

        Safe to run at any time: Instagram serves its own copy of a published
        image, so deleting the row cannot affect a live post.
        """
        cutoff = _now() - timedelta(days=days)
        async with self._session() as session:
            result = await session.execute(
                delete(SocialImage).where(SocialImage.created_at < cutoff)
            )
            await session.commit()
            return result.rowcount or 0
