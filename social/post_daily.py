"""Publish one deal to Instagram. The entry point the nightly workflow runs.

    python -m social.post_daily --dry-run   # render locally, publish nothing
    python -m social.post_daily             # the real thing

Exits 0 when nothing qualifies. An empty day is a normal outcome, not a
failure: posting a weak deal to keep a streak alive is worse than posting
nothing.
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from social import instagram, select
from social.caption import build_caption
from social.render import render_card
from social.state import (
    KEY_ACCESS_TOKEN,
    KEY_TOKEN_REFRESHED_AT,
    KEY_USER_ID,
    Store,
)

logger = logging.getLogger("social.post_daily")

# Where the staged card is publicly readable, which is what Instagram fetches.
IMAGE_BASE = os.getenv("SOCIAL_IMAGE_BASE", "https://api.bikegrid.com.au").rstrip("/")

TOKEN_LIFETIME_DAYS = 60
# Below this many days of token life left, a failed refresh stops being a
# warning and becomes a failure, so the operator gets an email while there is
# still time to re-authorise by hand. A token that expires unrefreshed cannot
# be recovered without going back to the Meta dashboard.
TOKEN_PANIC_DAYS_LEFT = 5


async def verify_public_image(client: httpx.AsyncClient, url: str) -> None:
    """Fetch the staged card the way Instagram will, before asking it to.

    Worth the extra request: a container that sits in IN_PROGRESS until it
    expires gives no useful diagnostic, and the cause is almost always this URL.
    Checking here turns two minutes of polling and an opaque error into one
    clear line in the log.
    """
    response = await client.get(url, follow_redirects=False, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Staged image {url} returned HTTP {response.status_code}, not 200.")
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if content_type != "image/jpeg":
        raise RuntimeError(f"Staged image {url} served Content-Type {content_type!r}, not image/jpeg.")
    logger.info("staged image verified: %s (%d bytes)", url, len(response.content))


async def ensure_fresh_token(client: httpx.AsyncClient, store: Store, token: str) -> str:
    """Refresh the long-lived token when it is getting old. Returns the token to use."""
    raw_refreshed_at = await store.get(KEY_TOKEN_REFRESHED_AT)
    if not raw_refreshed_at:
        logger.warning("no token refresh timestamp recorded; treating the token as new")
        await store.set_value(KEY_TOKEN_REFRESHED_AT, datetime.now(timezone.utc).isoformat())
        return token

    refreshed_at = datetime.fromisoformat(raw_refreshed_at)
    age_days = (datetime.now(timezone.utc) - refreshed_at).days
    if age_days < instagram.TOKEN_REFRESH_AFTER_DAYS:
        logger.info("access token is %d days old, no refresh needed", age_days)
        return token

    days_left = TOKEN_LIFETIME_DAYS - age_days
    try:
        payload = await instagram.refresh_token(client, token)
    except instagram.InstagramError as exc:
        if days_left <= TOKEN_PANIC_DAYS_LEFT:
            raise RuntimeError(
                f"Token refresh failed with only {days_left} days left before it "
                f"expires for good. Re-authorise from the Meta dashboard "
                f"(Instagram > API setup with Instagram login) and reload it with "
                f"social.bootstrap_token. Cause: {exc}"
            ) from exc
        logger.error("token refresh failed (%d days left, will retry tomorrow): %s", days_left, exc)
        return token

    new_token = payload.get("access_token")
    if not new_token:
        logger.error("refresh returned no token, continuing with the existing one")
        return token
    # Both keys in one transaction: a token written without its timestamp would
    # read as 60 days old tomorrow and be refreshed again immediately.
    await store.set_many(
        {
            KEY_ACCESS_TOKEN: new_token,
            KEY_TOKEN_REFRESHED_AT: datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info("access token refreshed, valid for another %s seconds", payload.get("expires_in"))
    return new_token


async def run(dry_run: bool) -> int:
    async with httpx.AsyncClient(timeout=30) as client:
        deals = await select.fetch_deals(client)
        logger.info("feed returned %d candidate deals", len(deals))

        blocked = select.opted_out_vendors()
        if blocked:
            logger.info("vendors opted out of Instagram: %s", ", ".join(sorted(blocked)))

        store = None if dry_run else Store.from_env()
        try:
            posted = set() if dry_run else await store.recent_keys(select.REPOST_WINDOW_DAYS)
            bike = select.select_deal(deals, posted, blocked)
            if bike is None:
                logger.info("nothing qualified today; posting nothing")
                return 0

            logger.info(
                "selected %s %s at %s (%d%% off)",
                bike["brand"], bike["model_name"], bike["vendor_name"], bike["discount_percentage"],
            )
            caption = build_caption(bike, deal_count=len(deals))
            jpeg = await render_card(bike, client)
            logger.info("rendered card: %d bytes", len(jpeg))

            if dry_run:
                out = Path("card.jpg")
                out.write_bytes(jpeg)
                print(f"\nWrote {out.resolve()} ({len(jpeg):,} bytes)\n")
                print("--- caption ---")
                print(caption)
                print("--- end caption ---")
                return 0

            token = await store.get(KEY_ACCESS_TOKEN)
            user_id = await store.get(KEY_USER_ID)
            if not token or not user_id:
                raise RuntimeError(
                    "No Instagram credentials in social_state. Run "
                    "`python -m social.bootstrap_token` first."
                )
            token = await ensure_fresh_token(client, store, token)

            image_id = await store.store_image(jpeg)
            image_url = f"{IMAGE_BASE}/social/{image_id}.jpg"
            await verify_public_image(client, image_url)

            media_id = await instagram.publish_image(client, user_id, token, image_url, caption)
            await store.record_post(bike, media_id)
            logger.info("published %s as media %s", bike["id"], media_id)

            pruned = await store.prune_images()
            if pruned:
                logger.info("pruned %d staged image(s) past retention", pruned)
            return 0
        finally:
            if store is not None:
                await store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish today's deal to Instagram.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pick and render today's deal to card.jpg, print the caption, publish nothing. "
             "Needs no database and no Instagram credentials.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
