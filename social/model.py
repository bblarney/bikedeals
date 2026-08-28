"""What the post prints for a bike's model, after the brand shown beside it.

A direct port of ``displayModelName`` in frontend/src/lib/model.js, kept
deliberately identical rather than reimplemented: the card shows brand and model
as two separate lines exactly as the site's cards do, so it inherits the same
stutter the frontend already fixed. About one listing in five repeats the brand
inside the model field, which reads as "SCOTT / SCOTT ADDICT 20" on the card and
"Scott Scott Addict 20" in the caption.

Model years are kept on purpose: a buyer uses them, so they are signal.
"""
import re

# Separator punctuation left dangling once the brand is removed ("- Rail 9.9",
# "Contessa |"). The dashes are written as escapes so no literal em dash appears
# in the source, per the repo's writing rule.
_EDGE_PUNCT = "[-:|/,\u00b7\u2013\u2014]"
_STRIP_EDGE_PUNCT = re.compile(rf"^{_EDGE_PUNCT}+\s*|\s*{_EDGE_PUNCT}+$")


def display_model_name(brand: str, model_name: str) -> str:
    if not model_name:
        return model_name or ""

    out = model_name
    trimmed_brand = (brand or "").strip()
    if trimmed_brand:
        # Whole-word and case-insensitive. A brand can be several words
        # ("Santa Cruz", "Rocky Mountain"), so match the phrase, not each token.
        out = re.sub(rf"\b{re.escape(trimmed_brand)}\b", " ", out, flags=re.IGNORECASE)

    out = _STRIP_EDGE_PUNCT.sub("", " ".join(out.split())).strip()

    # Never return empty: a model that was only the brand ("Trek") still needs a
    # label, so fall back to the raw value rather than printing the brand alone.
    return out or model_name
