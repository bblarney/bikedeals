"""The endpoint Instagram fetches a rendered card from.

This is the only consumer that matters, and it is unforgiving: it wants a plain
200 with an image/jpeg content type. A container stuck in IN_PROGRESS is almost
always this response being wrong, so the contract is worth pinning.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.models import SocialImage

# Smallest thing that is unambiguously a JPEG: SOI + EOI markers.
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


def _stage(sync_engine, image_id="abc123", created_at=None):
    with Session(sync_engine) as session:
        session.add(
            SocialImage(
                id=image_id,
                jpeg=JPEG_BYTES,
                created_at=created_at or datetime.now(timezone.utc),
            )
        )
        session.commit()
    return image_id


def test_serves_the_bytes_as_jpeg(client, sync_engine):
    image_id = _stage(sync_engine)
    response = client.get(f"/social/{image_id}.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == JPEG_BYTES


def test_is_cacheable_and_not_indexed(client, sync_engine):
    image_id = _stage(sync_engine, "cache-me")
    response = client.get(f"/social/{image_id}.jpg")

    assert "immutable" in response.headers["cache-control"]
    # Post artefacts, not site content: they should not turn up in search.
    assert response.headers["x-robots-tag"] == "noindex"


def test_a_pruned_or_unknown_id_is_a_clean_404(client):
    """Expected once an image ages out. The published post is unaffected,
    because Instagram serves its own copy."""
    assert client.get("/social/never-existed.jpg").status_code == 404


def test_no_redirect_before_the_bytes(client, sync_engine):
    """Meta's fetcher is happiest with a direct 200. Hosting these ourselves
    instead of on a git CDN is what buys that, so assert we keep it."""
    image_id = _stage(sync_engine, "direct")
    response = client.get(f"/social/{image_id}.jpg", follow_redirects=False)
    assert response.status_code == 200
    assert not response.history
