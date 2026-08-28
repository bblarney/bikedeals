"""Brand de-duplication in the model name.

Mirrors frontend/test/model-name.test.js case for case: the card and the site
show brand and model as separate fields, so the port has to strip the stutter
the same way or the post and the listing disagree about the same bike.
"""
import pytest

from social.model import display_model_name


@pytest.mark.parametrize(
    "brand,model,expected",
    [
        ("Trek", "Trek Rail 9.9", "Rail 9.9"),
        ("Scott", "SCOTT ADDICT 20 Blue", "ADDICT 20 Blue"),
        # The year is signal a buyer uses, so it survives; the brand does not.
        ("Scott", "2023 Scott Contessa", "2023 Contessa"),
        ("Scott", "Scott 2023 Scott Contessa", "2023 Contessa"),
        ("Santa Cruz", "Santa Cruz Hightower", "Hightower"),
        ("Merida", "24 MERIDA SCULTURA 9000", "24 SCULTURA 9000"),
        ("Trek", "Trek - Marlin 5", "Marlin 5"),
        ("Trek", "Domane SL 5", "Domane SL 5"),
        # Whole-word only: "Liv" must not be found inside "Livewire".
        ("Liv", "Livewire Special", "Livewire Special"),
        # A model that was only the brand still needs a label.
        ("Trek", "Trek", "Trek"),
    ],
)
def test_matches_the_frontend(brand, model, expected):
    assert display_model_name(brand, model) == expected


def test_missing_values_do_not_throw():
    assert display_model_name("Trek", "") == ""
    assert display_model_name("Trek", None) == ""
    assert display_model_name("", "Rail 9.9") == "Rail 9.9"
    assert display_model_name(None, "Rail 9.9") == "Rail 9.9"


def test_a_brand_with_regex_metacharacters_neither_throws_nor_corrupts():
    """Brands are proper nouns, but "E+" would compile as a quantifier if it
    reached the pattern unescaped.

    The brand survives here rather than being stripped, because \b after "+"
    needs a word character next and the model has a space. That is the same
    result the frontend gives, and its own test asserts no more than this: the
    contract is "does not throw, does not mangle the name", not "always strips".
    """
    assert display_model_name("E+", "E+ Explore Pro") == "E+ Explore Pro"
