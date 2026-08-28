"""Minimal client for Instagram's Content Publishing API.

Only the four calls the daily post needs, against the documented endpoints on
graph.instagram.com. Nothing here touches Instagram's private mobile API: that
route (instagrapi and similar) is what gets accounts banned, and no convenience
is worth the account.

Publishing is deliberately a three-step dance rather than one upload. Instagram
does not accept image bytes: you hand it a public URL, it queues a container and
fetches the image itself, and only once the container reports FINISHED can the
container be published.
"""
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

GRAPH_HOST = "https://graph.instagram.com"

# Meta expires a Graph API version roughly two years after release, and calling
# an expired one fails outright. v25.0 (February 2026) is the current stable
# release; v23.0 already expired in June 2026. Overridable so a sunset can be
# answered with an environment variable rather than a deploy.
API_VERSION = os.getenv("IG_API_VERSION", "v25.0")

# Meta fetches the image during container creation, so a large photo or a slow
# origin shows up here as a container that stays IN_PROGRESS.
CONTAINER_POLL_SECONDS = 5
CONTAINER_POLL_ATTEMPTS = 24  # two minutes

# A long-lived token lasts 60 days and can be refreshed once it is 24 hours old.
# Refreshing at 50 leaves ten days of slack: the job can fail every night for a
# week and still recover on its own without a manual re-auth.
TOKEN_REFRESH_AFTER_DAYS = 50


class InstagramError(RuntimeError):
    """A call to Instagram failed. Carries Meta's message, never the token."""


def _endpoint(path: str) -> str:
    return f"{GRAPH_HOST}/{API_VERSION}/{path.lstrip('/')}"


def _raise_for_error(response: httpx.Response, what: str) -> dict:
    """Turn Meta's error envelope into something readable in a workflow log."""
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400 or "error" in payload:
        error = payload.get("error", {})
        message = error.get("message") or response.text[:300]
        code = error.get("code")
        raise InstagramError(f"{what} failed (HTTP {response.status_code}, code {code}): {message}")
    return payload


async def me(client: httpx.AsyncClient, token: str) -> dict:
    """Whose account this token actually belongs to.

    Used by bootstrap_token to prove a pasted token works, and to show which
    account it authorises before anything gets published to it.
    """
    response = await client.get(
        _endpoint("me"), params={"fields": "user_id,username", "access_token": token}
    )
    return _raise_for_error(response, "Fetching the account")


async def create_container(
    client: httpx.AsyncClient, user_id: str, token: str, image_url: str, caption: str
) -> str:
    response = await client.post(
        _endpoint(f"{user_id}/media"),
        data={"image_url": image_url, "caption": caption, "access_token": token},
    )
    payload = _raise_for_error(response, "Creating the media container")
    container_id = payload.get("id")
    if not container_id:
        raise InstagramError(f"Container creation returned no id: {payload}")
    return container_id


async def wait_for_container(client: httpx.AsyncClient, container_id: str, token: str) -> None:
    """Block until Instagram has fetched the image, or explain why it never did."""
    for attempt in range(CONTAINER_POLL_ATTEMPTS):
        response = await client.get(
            _endpoint(container_id),
            params={"fields": "status_code,status", "access_token": token},
        )
        payload = _raise_for_error(response, "Checking the container status")
        status = payload.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(
                f"Container {status}: {payload.get('status', 'no detail given')}. "
                "This is almost always the image URL: check it returns 200 with "
                "Content-Type image/jpeg from the public internet."
            )
        logger.info("container %s is %s (attempt %d)", container_id, status, attempt + 1)
        await asyncio.sleep(CONTAINER_POLL_SECONDS)
    raise InstagramError(
        f"Container {container_id} never reached FINISHED. Instagram could not "
        "fetch the image URL in time."
    )


async def publish_container(
    client: httpx.AsyncClient, user_id: str, token: str, container_id: str
) -> str:
    response = await client.post(
        _endpoint(f"{user_id}/media_publish"),
        data={"creation_id": container_id, "access_token": token},
    )
    payload = _raise_for_error(response, "Publishing the container")
    media_id = payload.get("id")
    if not media_id:
        raise InstagramError(f"Publish returned no media id: {payload}")
    return media_id


async def refresh_token(client: httpx.AsyncClient, token: str) -> dict:
    """Extend a long-lived token by another 60 days.

    Unversioned by design: this is the one endpoint Meta documents without a
    version prefix. Takes only the token, so there is no app secret anywhere in
    the automation.
    """
    response = await client.get(
        f"{GRAPH_HOST}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    return _raise_for_error(response, "Refreshing the access token")


async def publish_image(
    client: httpx.AsyncClient, user_id: str, token: str, image_url: str, caption: str
) -> str:
    """Create, wait, publish. Returns the published media id."""
    container_id = await create_container(client, user_id, token, image_url, caption)
    logger.info("created container %s", container_id)
    await wait_for_container(client, container_id, token)
    media_id = await publish_container(client, user_id, token, container_id)
    logger.info("published media %s", media_id)
    return media_id
