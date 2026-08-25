"""Reject an RRP that cannot be true, so a typo cannot headline the site.

The default sort is `discount_desc`, so the single largest discount in the
catalogue is the first thing every visitor sees. On 2026-08-25 that was:

    91% off — Giant Propel Advanced Pro 0-Di2 2027, was $84,990, now $7,799

It is not a deal. Saint Cloud's own product feed lists six variants of that
bike, five with `compare_at_price` 8499.00 and the XL with 84990.00 — a stray
zero at the source. We scraped it faithfully and put it at the top of the page.

The guard is a **sibling comparison**, not a discount cap. Every variant of one
product is the same bike in a different size and they carry the same RRP, so a
variant whose RRP is several times its siblings' is a typo — and this catches
one that produces a *plausible-looking* 40% discount just as well as one that
produces 91%. A cap could only ever catch the loud ones.

Measured against the live feed, a cap would also be hard to place honestly:

    >=50%: 77 listings      >=65%:  2
    >=55%: 16               >=70%:  1
    >=60%:  4               >=91%:  1

The 69% Cannondale SuperSix EVO Neo and the 62% Focus VICE are real run-out
clearances. Any cap tight enough to catch 91% without deleting those sits in an
arbitrary band with nothing in it.

A cap survives only as a **backstop for products with no siblings**, where there
is nothing to compare against, and it is set far above any genuine discount ever
observed.

Nothing is invented when a typo is found: the RRP is dropped and the discount
goes to zero. The bike stays in the catalogue at the real price it sells for,
without a fabricated saving next to it.
"""
import logging
from statistics import median

logger = logging.getLogger(__name__)

# How many times its siblings' RRP a variant's RRP may be before it is a typo.
# Variants of one product are the same bike in different sizes and normally
# share an RRP exactly, so this is deliberately loose: the real case was 10x.
MAX_RRP_RATIO_TO_SIBLINGS = 3.0

# Below this many priced siblings there is no majority to be the odd one out.
MIN_SIBLINGS_FOR_MEDIAN = 3

# Backstop for single-variant products. Far above the 69% that is the largest
# genuine discount in the live catalogue, because this rule cannot tell a real
# clearance from a typo — it only knows that nothing sells for 12% of its RRP.
MAX_PLAUSIBLE_DISCOUNT = 85


def _variant_group(bike) -> tuple:
    """The sizes of one bike at one shop.

    Keyed on the name rather than on product_url. The URL looks like the more
    precise choice and is not: it is rewritten downstream for affiliate vendors,
    where every product collapses onto one tracking link
    (`bikesonline-australia.pxf.io/c/…`). Grouping on that put 538 unrelated
    Bikes Online products in a single group, took the median of the whole
    catalogue, and condemned every genuinely expensive bike in it — 106 real
    discounts, all of them correct.

    (brand, model_name) is what "the same bike in a different size" actually
    means, and it does not depend on how the URL is spelled. vendor_name is in
    the key so the function is safe on a mixed list, though a scrape only ever
    passes one vendor's records.
    """
    return (bike.vendor_name, bike.brand, bike.model_name)


def drop_implausible_rrp(bikes: list) -> tuple[list, dict[str, int]]:
    """Clear any price_original that its siblings contradict.

    Returns the same records (mutated in place) and a count by reason, so the
    daily email can show a spike if a shop starts publishing nonsense.
    """
    groups: dict[tuple, list] = {}
    for bike in bikes:
        groups.setdefault(_variant_group(bike), []).append(bike)

    reasons: dict[str, int] = {}

    def reject(bike, reason: str) -> None:
        logger.warning(
            "Implausible RRP on %r (%s): was %s, now %s (%d%% off) — dropping the RRP",
            bike.model_name, reason, bike.price_original, bike.price_sale,
            bike.discount_percentage,
        )
        bike.price_original = None
        bike.discount_percentage = 0
        reasons[reason] = reasons.get(reason, 0) + 1

    for siblings in groups.values():
        priced = [b for b in siblings if b.price_original]
        if len(priced) >= MIN_SIBLINGS_FOR_MEDIAN:
            typical = median(b.price_original for b in priced)
            for bike in priced:
                if typical > 0 and bike.price_original > typical * MAX_RRP_RATIO_TO_SIBLINGS:
                    reject(bike, "rrp-disagrees-with-siblings")
            continue
        # No majority to compare against: fall back to the blunt rule.
        for bike in priced:
            if bike.discount_percentage >= MAX_PLAUSIBLE_DISCOUNT:
                reject(bike, "discount-beyond-plausible")

    return bikes, reasons
