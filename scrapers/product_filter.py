"""Keep things that are not bikes out of the bike database.

Shops sell bikes *and* everything else, and a vendor's "bikes" collection or
product_type is not a reliable boundary: the live feed carried inner tubes
(Arisun 26x1.50, $9, category Mountain), Oakley sunglasses ($89, Road), CADEX
tyres listed at frame_size 28mm, kids' spoke beads ($6), e-cargo baskets and
seat pads. `resolve_category` cheerfully assigned each of them a bike category,
because a gravel *tyre* does contain the word "gravel".

The cost is not cosmetic. Every one of these lands in the facet lists, in the
"N bikes" the header advertises, in sitemap.xml as its own indexable page, and
inside the Product/AggregateOffer JSON-LD the detail page emits.

Three rules, deliberately in this order, each independently defensible:

1. An accessory noun in the product name. This does the real work. Patterns are
   word-bounded so "Ultralite" is not a light, "tubeless" is not a tube,
   "Mountain" is not a mount and "entire" is not a tyre.
2. A frame size that is a tyre width. A bike frame is never "28mm".
3. A price floor. Measured against the live catalogue, the cheapest genuine
   complete bike is a $89 Holstar Blaster 12" kids' bike; everything below that
   was an accessory. The floor sits under it, not over it — the $150-700 band is
   almost entirely real kids' and balance bikes, so a higher floor would delete
   good inventory to catch junk the keyword rules already have.

Rejections are counted and reported per vendor in the daily email, and are
deliberately NOT routed through `invalid_count`: that feeds the 5% quarantine
ratio in scrapers/run.py, and a shop that genuinely lists 30% accessories would
quarantine itself every night.
"""
import re

# Nouns that name a thing which is not a bicycle. Kept to unambiguous cases —
# the failure mode that matters is deleting a real bike, not missing one.
#
# Notably absent, and on purpose:
#   "brake"/"disc" — real model names say "Disc Brake" constantly.
#   "hub"          — hub-geared bikes exist, and a vendor is called Bike Hub.
#   "frame"        — a discounted frameset is a legitimate deal for this
#                    audience, so framesets stay in. Different question.
_ACCESSORY_TERMS = (
    # wheels, tyres and what goes in them
    r"tyres?", r"tires?", r"tubes?", r"valves?", r"spokes?",
    r"sealant", r"tubeless\s+kit",
    # contact points and cockpit
    r"saddles?", r"seatposts?", r"seat\s+posts?", r"handlebars?", r"stems?",
    r"grips?", r"bar\s+tape", r"pedals?", r"cleats?",
    # drivetrain and braking parts
    r"cassettes?", r"chainrings?", r"derailleurs?", r"chains?",
    r"brake\s+pads?", r"brake\s+levers?", r"brake\s+rotors?", r"rotors?",
    r"bottom\s+brackets?", r"cranksets?",
    # rider kit
    r"helmets?", r"sunglasses", r"goggles", r"lens", r"lenses",
    r"gloves?", r"jerseys?", r"bib\s+shorts?", r"socks?", r"shoes?", r"jackets?",
    # luggage and carrying
    r"racks?", r"panniers?", r"baskets?", r"bags?", r"trailers?", r"tow\s+bars?",
    # fittings and add-ons
    r"mudguards?", r"fenders?", r"kickstands?", r"bells?", r"horns?",
    r"mirrors?", r"bottles?", r"bidons?", r"cages?", r"mounts?", r"brackets?",
    r"adapters?", r"spacers?", r"footboards?", r"footrests?",
    r"child\s+seats?", r"seat\s+pads?", r"streamers?", r"spokey\s+dokes?",
    r"spoke\s+beads?",
    # lighting and electronics. Compounds only: a bare "light" would take
    # Lightspeed, and "battery"/"charger" are catastrophic — 84 real e-bikes in
    # a 5,478-row sample advertise their capacity ("630Wh Battery") in the name,
    # and Norco ships a mountain bike called the Charger.
    r"head\s?lights?", r"tail\s?lights?", r"rear\s+lights?", r"light\s+sets?",
    r"sensors?", r"computers?",
    # Not bicycles, and shops shelve them with the bikes. Inherited from the
    # Shopify pipeline's title matching, which this replaces: a frameset is a
    # frame and fork rather than a rideable bike but is filed under the
    # discipline collection of the bike it builds into, and scooters sit in the
    # kids-bike aisle.
    r"framesets?", r"scooters?", r"throttles?",
    # workshop, care and services
    r"pumps?", r"locks?", r"tools?", r"multi-?tools?", r"lube", r"degreasers?",
    r"cleaners?", r"stands?", r"trainers?", r"gift\s+cards?", r"vouchers?",
    r"services?", r"tune[\s-]?ups?", r"fittings?", r"assembly", r"warranty",
    # Brands that make no bicycles, matched in the name because shops sell them
    # under their own label: "OAKLEY Radar EV Path Prizm Road" is listed by The
    # Bike Shop QLD with brand="THE BIKE SHOP QLD", so the brand check below
    # cannot see it. Restricted to eyewear/luggage/lock/care brands, which never
    # appear as a *spec* on a real bike — unlike SRAM or Shimano, which do.
    r"oakley", r"prizm", r"yakima", r"thule", r"kryptonite", r"abus",
    r"camelbak", r"knog", r"muc-?off", r"park\s+tool", r"lezyne",
    r"topeak", r"garmin", r"wahoo",
)

_ACCESSORY_RE = re.compile(r"\b(?:" + "|".join(_ACCESSORY_TERMS) + r")\b", re.IGNORECASE)

# A frame size quoted as a millimetre width is a tyre, full stop. Live examples:
# "CADEX RACE GC" at frame_size 28mm and 30mm, priced $119.95.
_TYRE_WIDTH_SIZE_RE = re.compile(r"^\s*\d{2,3}(?:\.\d+)?\s*mm\s*$", re.IGNORECASE)

# Tyre and tube sizing in the product name, for the ones that never say "tyre":
# "Vittoria Terreno Dry 700x38 TNT Gravel G2" and "Arisun 26x1.50/2.2 Presta".
#
# The leading number is pinned to the real wheel diameters. A loose \d{2,3}x\d
# also matched ByK's kids bikes, whose model names *are* "E-450x8", "E-620x7"
# and "E-450x1" — four real bikes deleted by a pattern meant for tyres.
_TYRE_DIMENSION_RE = re.compile(
    r"\b(?:16|20|24|26|27\.5|28|29|650|700)\s?[xX]\s?\d{1,2}(?:\.\d+)?\b"
)

# Brands that build components, tyres or apparel and no complete bikes. Matched
# against the brand field only: several of these (SRAM, Shimano) legitimately
# appear inside a real bike's name as the groupset it ships with.
#
# Distributors that front for real brands — Advance Traders, Monza Imports,
# Bikecorp, Sheppard Cycles, Pon Performance — are deliberately absent. Their
# listings are real bikes wearing the wrong brand name, which is a brand
# normalisation problem, not a "this is not a bike" one.
#
# ENVE is absent for a different reason: it started as a component brand but
# sells complete builds, and the live feed has a $13,500 "ENVE Melee -
# Wheelhaus Demo Build" that is unambiguously a bike. Same trap as Hornit,
# which is a bell brand that also makes the AIRO balance bike.
_NON_BIKE_BRANDS = frozenset(
    {
        "sram", "shimano", "campagnolo", "zipp", "dtswiss", "bontrager",
        "raceface", "praxis", "hope", "chrisking",
        "vittoria", "maxxis", "schwalbe", "continental", "kenda", "arisun",
        "pirelli", "michelin", "hutchinson",
        "oakley", "giro", "bell", "kask", "lazer", "poc", "rudyproject",
        "yakima", "thule", "kryptonite", "abus", "camelbak", "knog", "lezyne",
        "topeak", "blackburn", "mucoff", "finishline", "parktool",
        "garmin", "wahoo",
    }
)

_BRAND_NORMALISE_RE = re.compile(r"[^a-z0-9]+")

# Below this, nothing in the live catalogue was a complete bike. See module
# docstring — the cheapest real one found was $89.
MIN_BIKE_PRICE = 80.0


def non_bike_reason(
    model_name: str, frame_size: str, price_sale: float, brand: str = ""
) -> str | None:
    """Why this listing is not a bike, or None if it looks like one.

    Returns a short stable reason string so the daily email can group rejects by
    cause and a bad rule shows up as a spike rather than as silent shrinkage.
    """
    match = _ACCESSORY_RE.search(model_name or "")
    if match:
        return f"accessory:{match.group(0).lower()}"
    if _TYRE_DIMENSION_RE.search(model_name or ""):
        return "tyre-dimensions"
    if _BRAND_NORMALISE_RE.sub("", (brand or "").lower()) in _NON_BIKE_BRANDS:
        return "component-brand"
    if _TYRE_WIDTH_SIZE_RE.match(frame_size or ""):
        return "tyre-width-size"
    if price_sale < MIN_BIKE_PRICE:
        return "below-price-floor"
    return None


def drop_non_bikes(bikes: list) -> tuple[list, dict[str, int]]:
    """Split scraped records into bikes and a count of rejects by reason."""
    kept = []
    rejected: dict[str, int] = {}
    for bike in bikes:
        reason = non_bike_reason(
            bike.model_name, bike.frame_size, bike.price_sale, bike.brand
        )
        if reason is None:
            kept.append(bike)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1
    return kept, rejected
