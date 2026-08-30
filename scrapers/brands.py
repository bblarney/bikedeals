"""One brand, one name.

The live brand facet had 246 entries for about 190 real brands. Every kind of
duplicate was in there at once:

    casing      FELT / Felt          GT / Gt          MONGOOSE / Mongoose
    suffixes    Norco / Norco Bicycles / Norco Bikes  Reid / Reid Cycles
    accents     Cervelo / CERVELO / Cervelo (with the accent)
    punctuation X-LAB / X-Lab / X-lab / XLAB
    wording     AMPD BROS / AMPD BROTHERS     ET Cycle / ET-Cycles / ET.CYCLE

A 246-entry dropdown with Norco in it three times is unusable, and the split
also costs matches: ``product_key`` is ``<canonical brand>:<sku>``, so two shops
selling the same bike under "Cervelo" and "Cervélo" are never compared.

Then there are listings with no brand at all — a shop's own name, a distributor,
or a placeholder:

    "Advance Traders"  ->  "Merida eBIG NINE 600"        (79 listings)
    "Bicycle Workshop" ->  "Giant TCR Advanced Disc 1"   (297 listings)
    "Pon Performance"  ->  "2025 Santa Cruz Nomad"       (67 listings)
    "Not specified"    ->  "JAMIS Durango A2 19"         (18 listings)
    "My Store"         ->  "2018 Canyon Strive CF 9.0"
    "global"           ->  "Icon EB One"

In each of those the real brand is sitting at the front of the model name, so it
can be recovered rather than guessed.

Two mechanisms, in order:

1. **Recovery.** When the brand names the shop rather than the manufacturer,
   read the brand off the model name. Falls back to leaving the brand alone, so
   a shop whose own name really is the brand (Progear Bikes sells Progear) keeps
   it.
2. **Folding.** Strip accents, case, punctuation and corporate suffixes to a
   key, then look up the one spelling to display. An unknown key keeps the
   brand as scraped — normalising is never allowed to invent a brand.

This runs for every pipeline (it is a BikeRecord validator), unlike the
Shopify-only ``_BRAND_ALIASES`` table it supersedes. Per-vendor ``brand_map``
overrides in the YAML still apply first, inside the pipelines.
"""
import re
import unicodedata

# Corporate suffixes shops append to the same manufacturer. Longest first, or
# "bicycles" is matched as "cycles" and leaves "specializedbi" behind.
#
# Mirrors scrapers.models._BRAND_SUFFIXES, which does the same job for
# product_key. Kept as its own copy because this one also has to survive accent
# folding, and because the two answer different questions: that one asks "is
# this the same product", this one asks "what do we call this brand".
_BRAND_SUFFIXES = (
    "bicycles", "bikeco", "bicycle", "cycling", "cycles", "bikes", "cycle", "bike", "bmx",
)
# Never strip a brand down to a stub: "ET Cycle" must not become "et".
_MIN_BRAND_STEM = 3

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold_brand(brand: str) -> str:
    """A brand's identity, ignoring how it happens to be written."""
    ascii_only = unicodedata.normalize("NFKD", brand or "").encode("ascii", "ignore").decode()
    stem = _NON_ALNUM.sub("", ascii_only.lower())
    for suffix in _BRAND_SUFFIXES:
        if stem.endswith(suffix) and len(stem) - len(suffix) >= _MIN_BRAND_STEM:
            return stem[: -len(suffix)]
    return stem


# folded key -> the spelling to show. Derived by clustering the 246 live brand
# names, then correcting the cases where the most common spelling is not the
# right one (GT and XDS are acronyms; Cervélo and Riese & Müller have accents).
_CANONICAL: dict[str, str] = {
    # Brands the live facet listed more than once.
    "amflow": "Amflow",
    "ampdbros": "Ampd Bros",
    "ampdbrothers": "Ampd Bros",
    "avanti": "Avanti",
    "azonic": "Azonic",
    "base": "Base",
    "brompton": "Brompton",
    "byk": "ByK",
    "cervelo": "Cervélo",
    "cruzee": "Cruzee",
    "cruzr": "Cruzr",
    "dirodi": "DiroDi",
    "dyu": "DYU",
    "eastern": "Eastern",
    "etcycle": "ET Cycle",
    "etcycles": "ET Cycle",
    "factor": "Factor",
    "fatboy": "Fatboy",
    "felt": "Felt",
    "forbidden": "Forbidden",
    "fuji": "Fuji",
    "gt": "GT",
    "icon": "Icon",
    "jamis": "Jamis",
    "kona": "Kona",
    "lekker": "Lekker",
    "liv": "Liv",
    "mondraker": "Mondraker",
    "mongoose": "Mongoose",
    "norco": "Norco",
    "progear": "Progear",
    "radio": "Radio",
    "raven": "Raven",
    "reid": "Reid",
    "rfn": "RFN",
    "riesemuller": "Riese & Müller",
    "rieseandmuller": "Riese & Müller",
    "santacruz": "Santa Cruz",
    "silverback": "Silverback",
    "smartmotion": "SmartMotion",
    "specialized": "Specialized",
    "surly": "Surly",
    "tebco": "Tebco",
    "vamos": "Vamos",
    "wilier": "Wilier",
    "xds": "XDS",
    "xlab": "X-Lab",
    # Single-spelling today, listed so a new vendor shouting the name does not
    # reintroduce the duplicate. These are the marques the catalogue is built on.
    "giant": "Giant",
    "trek": "Trek",
    "merida": "Merida",
    "scott": "Scott",
    "cannondale": "Cannondale",
    "cube": "Cube",
    "bmc": "BMC",
    "bianchi": "Bianchi",
    "orbea": "Orbea",
    "pinarello": "Pinarello",
    "polygon": "Polygon",
    "marin": "Marin",
    "yeti": "Yeti",
    "ibis": "Ibis",
    "juliana": "Juliana",
    "salsa": "Salsa",
    "genesis": "Genesis",
    "focus": "Focus",
    "bergamont": "Bergamont",
    "kalkhoff": "Kalkhoff",
    "moustache": "Moustache",
    "tern": "Tern",
    "dahon": "Dahon",
    "benno": "Benno",
    "aventon": "Aventon",
    "apollo": "Apollo",
    "malvernstar": "Malvern Star",
    "raleigh": "Raleigh",
    "schwinn": "Schwinn",
    "haro": "Haro",
    "redline": "Redline",
    "commencal": "Commencal",
    "canyon": "Canyon",
    "rockymountain": "Rocky Mountain",
    "titanracing": "Titan Racing",
    "shogun": "Shogun",
    "earlyrider": "Early Rider",
    "frog": "Frog",
    "cheetah": "Cheetah",
    "radius": "Radius",
    "rascal": "Rascal",
    "holstar": "Holstar",
    "velectrix": "Velectrix",
    "smartmotionebikes": "SmartMotion",
    "stacyc": "STACYC",
    "hornit": "Hornit",
    "firstbike": "FirstBIKE",
}

# The vocabulary a placeholder brand can be recovered *into*. Longest first so
# "Santa Cruz" is matched before "Santa".
_KNOWN_BRAND_KEYS = frozenset(_CANONICAL)

def is_known_brand(brand: str) -> bool:
    """Is this one of the manufacturers we recognise, however it is spelled?

    Reads the same folded vocabulary canonical_brand_name recovers into, so a
    caller cannot drift from the brand list the scrapers already agree on.
    """
    return fold_brand(brand) in _KNOWN_BRAND_KEYS


# Brands that name a distributor or a placeholder rather than a manufacturer.
# A shop's own name is caught generically (see canonical_brand_name), so this
# list only needs the ones whose text matches no vendor.
_PLACEHOLDER_BRANDS = frozenset(
    {
        "notspecified", "unspecified", "none", "na", "mystore", "global",
        "default", "brand", "generic",
        # Australian distributors, which front for real marques.
        "advancetraders", "monzaimports", "sheppard", "ponperformance",
        "bikecorp", "dirtworks", "lusty", "lustyindustries",
        # "PSI Cycling" (folds to "psi" once the "cycling" suffix is stripped)
        # and "Cassons" both arrive as the brand on GT and Haro listings at
        # Freedom Machine. "psi" is short for a key here, but these are exact
        # folded-key matches, not prefixes, and recovery is allowed to fail: a
        # marque genuinely called PSI keeps its name unless its model line
        # happens to open with a different known brand.
        "psi", "cassons",
    }
)

# A model name often opens with the model year: "2025 Santa Cruz Nomad".
_LEADING_YEAR_RE = re.compile(r"^\s*(?:19|20)\d{2}\s+")
_MAX_BRAND_WORDS = 3

# The Giant franchise, 22 storefronts in the registry and growing, each of which
# can put its own shop name in the brand field ("Giant Brisbane", "Giant Lygon
# St"). They all white-label one national catalogue, so the brand is Giant.
#
# A prefix rule rather than 22 table entries, because a table would silently go
# stale the next time a store is added — the same failure mode as the Worker
# allowlist, and it fails the same quiet way: one vendor's bikes filed under a
# brand nobody can pick from the dropdown.
#
# Prefix matching is used *only* here, and only because no other bicycle brand
# begins with these letters. It is not safe in general: scrapers/models.py
# documents why "Liv" must never prefix-match "Live Life Cycling".
_GIANT_STORE_RE = re.compile(r"^giant[a-z]")


def brand_from_model_name(model_name: str) -> str | None:
    """Read the manufacturer off the front of a product title, or None.

    Only ever returns a brand already in the canonical vocabulary, so this
    cannot mint a new one out of a product name.
    """
    text = _LEADING_YEAR_RE.sub("", model_name or "").strip()
    words = text.split()
    # Longest first: "Santa Cruz Nomad" is Santa Cruz, not Santa.
    for length in range(min(_MAX_BRAND_WORDS, len(words)), 0, -1):
        key = fold_brand(" ".join(words[:length]))
        if key in _KNOWN_BRAND_KEYS:
            return _CANONICAL[key]
    return None


def canonical_brand_name(brand: str, model_name: str = "", vendor_name: str = "") -> str:
    """The one name to file this bike's manufacturer under.

    Falls back to the brand exactly as scraped whenever it cannot do better —
    an unrecognised brand is far less damaging than a wrong one.
    """
    original = (brand or "").strip()
    if not original:
        return brand_from_model_name(model_name) or original

    key = fold_brand(original)
    if _GIANT_STORE_RE.match(key):
        return "Giant"

    # A brand that names the shop is not a brand. Comparing against the vendor
    # catches every shop-as-brand case without listing them: "Bicycle Workshop",
    # "Bikeology", "THE BIKE SHOP QLD". Recovery is allowed to fail, which is
    # what keeps Progear Bikes' own-brand bikes labelled Progear.
    if key in _PLACEHOLDER_BRANDS or (vendor_name and key == fold_brand(vendor_name)):
        recovered = brand_from_model_name(model_name)
        if recovered:
            return recovered
        return _CANONICAL.get(key, original)

    return _CANONICAL.get(key, original)
