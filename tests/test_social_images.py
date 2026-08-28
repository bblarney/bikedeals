"""The Shopify CDN width rewrite, ported from the frontend.

Mirrors frontend/test/images.test.js: the post card and the site should ask the
CDN for images the same way, so the two suites assert the same contract.
"""
from social.images import shop_image


def test_adds_a_width_to_shopify_urls():
    assert shop_image("https://cdn.shopify.com/s/files/1/a.jpg", 1200) == (
        "https://cdn.shopify.com/s/files/1/a.jpg?width=1200"
    )


def test_preserves_the_shopify_cache_key():
    result = shop_image("https://cdn.shopify.com/s/files/1/a.jpg?v=17", 1200)
    assert "v=17" in result
    assert "width=1200" in result


def test_overwrites_an_existing_width_rather_than_appending():
    result = shop_image("https://cdn.shopify.com/s/files/1/a.jpg?width=100", 1200)
    assert result.count("width=") == 1
    assert "width=1200" in result


def test_other_cdns_pass_through_untouched():
    """The other ~2% of images sit on vendor CDNs with no shared transform
    contract, so guessing a parameter would just break them."""
    url = "https://images.vendor.example/a.jpg"
    assert shop_image(url, 1200) == url


def test_missing_or_malformed_urls_are_returned_unchanged():
    assert shop_image(None, 1200) is None
    assert shop_image("", 1200) == ""
    assert shop_image("not a url", 1200) == "not a url"
