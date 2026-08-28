"""Render a deal into the 1080x1350 JPEG that gets posted.

HTML and headless Chromium rather than drawing with Pillow: the card has to
match the site's look, and text wrapping, line clamping and baseline alignment
are things a browser already does correctly. The template is the design; this
module only fills it in.
"""
import base64
import logging
from html import escape
from pathlib import Path

import httpx

from social.caption import format_price
from social.images import shop_image
from social.model import display_model_name

logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).parent / "templates" / "card.html"
LOGO = Path(__file__).parent.parent / "frontend" / "public" / "logos" / "bikegrid" / "bikegrid_white.png"

CARD_WIDTH = 1080
CARD_HEIGHT = 1350

# The stage is 620px tall inside a 1080px card, so anything past ~1200px wide is
# detail nobody sees. Asking the CDN for this instead of the original turns a
# 2-3 MB download into roughly 200 KB.
PRODUCT_IMAGE_WIDTH = 1200

JPEG_QUALITY = 88


def _model_font_size(model_name: str) -> int:
    """Shrink the headline for names that would otherwise clamp mid-word.

    Two lines is the hard limit in the template, so the choice is between a
    smaller face and a truncated model name. Shops publish some very long ones
    ("Domane SL 5 Gen 4 Disc Ultegra Di2"), and a size the reader can still
    parse beats an ellipsis.
    """
    length = len(model_name)
    if length <= 22:
        return 78
    if length <= 34:
        return 66
    return 54


async def fetch_data_uri(client: httpx.AsyncClient, url: str) -> str:
    """Inline a remote image so the rendered page needs no network of its own."""
    response = await client.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    media_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    encoded = base64.b64encode(response.content).decode()
    return f"data:{media_type};base64,{encoded}"


def _local_data_uri(path: Path, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode()}"


def build_html(bike: dict, product_data_uri: str) -> str:
    """Fill the template. Every interpolated value is HTML-escaped.

    The values come from shop-published text, so a model name containing an
    ampersand or a stray angle bracket must not be able to break the layout.
    """
    size = bike.get("frame_size_canonical") or bike.get("frame_size")
    chips = []
    if bike.get("category"):
        chips.append(f'<span class="chip">{escape(str(bike["category"]))}</span>')
    if size:
        chips.append(f'<span class="chip">Size {escape(str(size))}</span>')

    city = f", {escape(bike['city'])}" if bike.get("city") else ""
    model = display_model_name(bike["brand"], bike["model_name"])

    replacements = {
        "{{LOGO}}": _local_data_uri(LOGO, "image/png"),
        "{{PRODUCT_IMAGE}}": product_data_uri,
        "{{DISCOUNT}}": str(bike["discount_percentage"]),
        "{{BRAND}}": escape(bike["brand"]),
        "{{MODEL}}": escape(model),
        "{{MODEL_FONT_SIZE}}": str(_model_font_size(model)),
        "{{PRICE_WAS}}": format_price(bike["price_original"]),
        "{{PRICE_NOW}}": format_price(bike["price_sale"]),
        "{{CHIPS}}": "".join(chips),
        "{{VENDOR}}": escape(bike["vendor_name"]),
        "{{CITY}}": city,
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


async def render_card(bike: dict, client: httpx.AsyncClient) -> bytes:
    """Fetch the product photo, lay out the card, and screenshot it as JPEG."""
    # Imported here rather than at module scope so the selection and caption
    # tests can import this package without Playwright installed.
    from playwright.async_api import async_playwright

    source = shop_image(bike["image_url"], PRODUCT_IMAGE_WIDTH)
    product_data_uri = await fetch_data_uri(client, source)
    html = build_html(bike, product_data_uri)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page(
                viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
                device_scale_factor=1,
            )
            # The page has no external references left: the logo and the product
            # photo are both data URIs, so "loaded" needs no network wait.
            await page.set_content(html, wait_until="load")
            return await page.screenshot(type="jpeg", quality=JPEG_QUALITY)
        finally:
            await browser.close()
