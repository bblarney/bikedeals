"""Rasterise the BikeGrid mark into the favicon set (one-off; run by hand).

    python frontend/scripts/generate-favicons.py     # needs Pillow

Geometry is transcribed from public/favicon.svg (48x48 viewBox) and drawn onto a
dark rounded tile, supersampled 8x then downscaled for antialiasing. Edit the SVG
and this file together: browsers take the SVG, Googlebot-Image takes the .ico,
and the two looking different is the thing this set exists to prevent.
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "public"

BG = (15, 23, 42, 255)      # slate-900, matches the site's ink colour
FG = (255, 255, 255, 255)

# --- source geometry, in the 48x48 viewBox ---------------------------------
CIRCLES = [((11, 32), 9), ((37, 32), 9)]          # wheels, stroke 2.5
LINES = [                                          # frame, stroke 2.5
    ((24, 27), (11, 32)),   # chainstay
    ((18, 12), (11, 32)),   # seat stays
    ((31, 12), (37, 32)),   # fork
    ((18, 12), (31, 12)),   # top tube
    ((18, 12), (24, 27)),   # seat tube
    ((31, 12), (24, 27)),   # down tube
    ((14, 11), (21, 11)),   # saddle
]
BARS = [((31, 12), (35, 9)), ((35, 9), (37, 13))]  # drop bars, stroke 2
TRIANGLE = [(18, 21), (24, 27), (27, 19)]          # the grid mark

STROKE = 2.5
BAR_STROKE = 2.0

# The mark's ink spans x 2..46, y 8..41 once strokes are included; centre on
# that box, not on the viewBox, or the tile looks bottom-heavy.
MARK_CENTER = (24.0, 24.6)
INSET = 0.80          # how much of the tile the mark occupies
SS = 8                # supersample factor
MASTER = 512


def build(size, radius_ratio=0.20, transparent=False):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if not transparent:
        r = n * radius_ratio
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=r, fill=BG)

    ink = BG if transparent else FG
    k = (n / 48.0) * INSET

    def T(p):
        return (n / 2 + (p[0] - MARK_CENTER[0]) * k,
                n / 2 + (p[1] - MARK_CENTER[1]) * k)

    def w(stroke):
        return max(1, round(stroke * k))

    def dot(p, stroke):
        """Round line cap — Pillow's line() caps are square."""
        x, y = T(p)
        r = w(stroke) / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=ink)

    for (c, rad) in CIRCLES:
        cx, cy = T(c)
        rr = rad * k
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=ink, width=w(STROKE))

    d.polygon([T(p) for p in TRIANGLE], fill=ink)

    for a, b in LINES:
        d.line([T(a), T(b)], fill=ink, width=w(STROKE))
        dot(a, STROKE)
        dot(b, STROKE)

    for a, b in BARS:
        d.line([T(a), T(b)], fill=ink, width=w(BAR_STROKE))
        dot(a, BAR_STROKE)
        dot(b, BAR_STROKE)

    return img.resize((size, size), Image.LANCZOS)


master = build(MASTER)
for size in (96, 192, 512):
    build(size).save(OUT / f"favicon-{size}.png")
    print("wrote", f"favicon-{size}.png")

# Apple wants no transparency and a smaller corner radius (iOS masks it itself).
build(180, radius_ratio=0.0).save(OUT / "apple-touch-icon.png")
print("wrote apple-touch-icon.png")

# Multi-resolution .ico: what Googlebot-Image fetches from /favicon.ico.
build(256).save(OUT / "favicon.ico", format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote favicon.ico")
