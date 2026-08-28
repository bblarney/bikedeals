"""Build the Instagram caption for a deal.

Deterministic templates, no model in the loop. A caption that fires unattended
every night has to be boring and correct rather than surprising: every number in
it comes straight off the listing, so there is nothing here that can invent a
price.
"""
from datetime import date

from social.model import display_model_name

# `#ad` leads the caption rather than trailing in the hashtag block. Instagram
# truncates the caption in-feed after roughly two lines, and both the ACCC's
# influencer guidance and Instagram's own branded-content rules treat a
# disclosure buried among twenty other tags as not prominent enough. Putting it
# first is the only placement that survives the "... more" fold.
AD_DISCLOSURE = "#ad"

# Rotated by day of year so consecutive posts never open identically. Kept
# plain: this is a deals feed, not a personality account.
OPENERS = (
    "Today's pick:",
    "Spotted today:",
    "Deal of the day:",
    "Worth a look:",
    "On sale now:",
    "Price drop:",
    "Today's best discount:",
)

BASE_HASHTAGS = ("#bikegrid", "#bikedeals", "#cyclingaustralia", "#bikesale")

CATEGORY_HASHTAGS = {
    "Road": ("#roadbike", "#roadcycling"),
    "Mountain": ("#mtb", "#mountainbiking"),
    "Gravel": ("#gravelbike", "#gravelcycling"),
    "E-Bike": ("#ebike", "#electricbike"),
    "Commuter": ("#commuterbike", "#bikecommuting"),
}

# Rotated alongside the openers so the tag block is not identical every night.
ROTATING_HASHTAGS = (
    ("#cyclinglife", "#bikeshop"),
    ("#ridemore", "#lbs"),
    ("#newbike", "#cyclingdeals"),
    ("#bikelife", "#australiancycling"),
)


def format_price(value: float) -> str:
    """`$2,499` for whole dollars, `$2,499.50` when the shop lists cents."""
    if float(value).is_integer():
        return f"${int(value):,}"
    return f"${value:,.2f}"


def _rotation_index(on: date, length: int) -> int:
    return on.timetuple().tm_yday % length


def build_caption(bike: dict, deal_count: int, on: date | None = None) -> str:
    """Compose the caption for one bike.

    ``deal_count`` is how many deals the feed turned up today, used only for the
    call to action. ``on`` exists so tests can pin the rotation.
    """
    on = on or date.today()
    opener = OPENERS[_rotation_index(on, len(OPENERS))]
    model = display_model_name(bike["brand"], bike["model_name"])

    where = bike["vendor_name"]
    if bike.get("city"):
        where = f"{where}, {bike['city']}"

    hashtags = list(BASE_HASHTAGS)
    hashtags.extend(CATEGORY_HASHTAGS.get(bike.get("category"), ()))
    hashtags.extend(ROTATING_HASHTAGS[_rotation_index(on, len(ROTATING_HASHTAGS))])

    lines = [
        AD_DISCLOSURE,
        f"{opener} {bike['brand']} {model} at {where}",
        "",
        f"Was {format_price(bike['price_original'])}   "
        f"Now {format_price(bike['price_sale'])}   "
        f"({bike['discount_percentage']}% off)",
    ]
    if bike.get("frame_size_canonical") or bike.get("frame_size"):
        lines.append(f"Size {bike.get('frame_size_canonical') or bike['frame_size']}")
    # Instagram allows no clickable link in a caption, so the bio is the only
    # route off the platform. Guard the count: on a thin day the feed can turn
    # up exactly one qualifying deal, and "and 0 other deals" reads as a bug.
    others = max(deal_count - 1, 0)
    call_to_action = (
        f"This and {others} other deals today at bikegrid.com.au (link in bio)"
        if others
        else "More deals every day at bikegrid.com.au (link in bio)"
    )
    lines += [
        "",
        call_to_action,
        "Price correct at time of posting.",
        "",
        " ".join(hashtags),
    ]
    return "\n".join(lines)
