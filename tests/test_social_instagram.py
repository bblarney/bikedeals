"""The Instagram publishing client and the token-freshness policy.

These paths only run unattended at night, so the thing being pinned is that
they fail loudly and legibly rather than quietly: a readable error in a workflow
log is the whole diagnostic surface.
"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from social import instagram, post_daily


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_publish_image_creates_waits_then_publishes():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "container-1"})
        if request.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "media-1"})
        return httpx.Response(200, json={"status_code": "FINISHED"})

    async with client_for(handler) as client:
        media_id = await instagram.publish_image(
            client, "user-1", "tok", "https://example.com/a.jpg", "caption"
        )

    assert media_id == "media-1"
    assert calls[0].endswith("/media")
    assert calls[-1].endswith("/media_publish")


async def test_a_failed_container_explains_the_likely_cause(monkeypatch):
    """A container that errors is nearly always the image URL, and the raw Meta
    message does not say so."""
    monkeypatch.setattr(instagram, "CONTAINER_POLL_SECONDS", 0)

    def handler(request):
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "container-1"})
        return httpx.Response(200, json={"status_code": "ERROR", "status": "media fetch failed"})

    async with client_for(handler) as client:
        with pytest.raises(instagram.InstagramError, match="image URL"):
            await instagram.publish_image(
                client, "user-1", "tok", "https://example.com/a.jpg", "caption"
            )


async def test_a_container_that_never_finishes_gives_up(monkeypatch):
    monkeypatch.setattr(instagram, "CONTAINER_POLL_SECONDS", 0)
    monkeypatch.setattr(instagram, "CONTAINER_POLL_ATTEMPTS", 2)

    def handler(request):
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "container-1"})
        return httpx.Response(200, json={"status_code": "IN_PROGRESS"})

    async with client_for(handler) as client:
        with pytest.raises(instagram.InstagramError, match="never reached FINISHED"):
            await instagram.publish_image(
                client, "user-1", "tok", "https://example.com/a.jpg", "caption"
            )


async def test_metas_error_message_reaches_the_log():
    def handler(request):
        return httpx.Response(
            400, json={"error": {"message": "Invalid OAuth access token", "code": 190}}
        )

    async with client_for(handler) as client:
        with pytest.raises(instagram.InstagramError, match="Invalid OAuth access token"):
            await instagram.create_container(
                client, "user-1", "tok", "https://example.com/a.jpg", "caption"
            )


async def test_errors_never_quote_the_access_token():
    """Workflow logs are readable by anyone who can see the repo's Actions."""
    secret = "IGAA-super-secret-token"

    def handler(request):
        return httpx.Response(400, json={"error": {"message": "nope", "code": 1}})

    async with client_for(handler) as client:
        with pytest.raises(instagram.InstagramError) as caught:
            await instagram.create_container(
                client, "user-1", secret, "https://example.com/a.jpg", "caption"
            )

    assert secret not in str(caught.value)


class FakeStore:
    def __init__(self, values):
        self.values = dict(values)

    async def get(self, key):
        return self.values.get(key)

    async def set_value(self, key, value):
        self.values[key] = value

    async def set_many(self, values):
        self.values.update(values)


def _aged(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


async def test_a_young_token_is_left_alone():
    store = FakeStore({post_daily.KEY_TOKEN_REFRESHED_AT: _aged(3)})

    def handler(request):  # pragma: no cover - must never be called
        raise AssertionError("should not have called Instagram")

    async with client_for(handler) as client:
        assert await post_daily.ensure_fresh_token(client, store, "tok") == "tok"


async def test_an_old_token_is_refreshed_and_stored_with_its_timestamp():
    store = FakeStore({post_daily.KEY_TOKEN_REFRESHED_AT: _aged(55)})

    def handler(request):
        return httpx.Response(200, json={"access_token": "new-tok", "expires_in": 5183944})

    async with client_for(handler) as client:
        assert await post_daily.ensure_fresh_token(client, store, "tok") == "new-tok"

    assert store.values[post_daily.KEY_ACCESS_TOKEN] == "new-tok"
    # Without the timestamp the next run would read the token as 60 days old.
    assert store.values[post_daily.KEY_TOKEN_REFRESHED_AT] != _aged(55)


async def test_a_failed_refresh_with_time_left_only_warns():
    """There are ten days of slack by design: one bad night should not stop the
    post going out."""
    store = FakeStore({post_daily.KEY_TOKEN_REFRESHED_AT: _aged(51)})

    def handler(request):
        return httpx.Response(500, json={"error": {"message": "upstream", "code": 2}})

    async with client_for(handler) as client:
        assert await post_daily.ensure_fresh_token(client, store, "tok") == "tok"


async def test_a_failed_refresh_near_expiry_fails_the_run():
    """Past this point the token is days from being unrecoverable, so the
    operator needs the failure email while manual re-auth is still possible."""
    store = FakeStore({post_daily.KEY_TOKEN_REFRESHED_AT: _aged(57)})

    def handler(request):
        return httpx.Response(500, json={"error": {"message": "upstream", "code": 2}})

    async with client_for(handler) as client:
        with pytest.raises(RuntimeError, match="Re-authorise"):
            await post_daily.ensure_fresh_token(client, store, "tok")
