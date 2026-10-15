"""Spelling-error detection: false positives, suggestions, variants and names.

The Hunspell dictionaries are bundled (data/hunspell/), so these run offline.
"""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect import errors


def check(text: str, variant: str = "gb") -> dict:
    return errors.analyze(text, variant=variant, analysis=analysed(text))


def error_surfaces(text: str, variant: str = "gb") -> list[str]:
    return [e["surface"] for e in check(text, variant)["errors"]]


def first_suggestion(text: str, surface: str) -> str:
    (e,) = [e for e in check(text)["errors"] if e["surface"] == surface]
    return e["suggestions"][0]


# --- contract ------------------------------------------------------------------


def test_valid_variants_constant():
    assert errors.VALID_VARIANTS == ("gb", "us")


def test_invalid_variant_raises_value_error():
    with pytest.raises(ValueError):
        errors.analyze("hello", variant="fr")


def test_missing_spylls_raises_clear_error(monkeypatch):
    import builtins

    errors._dictionary.cache_clear()
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name.startswith("spylls"):
            raise ImportError("simulated missing spylls")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        with pytest.raises(errors.ErrorsExtraNotInstalled):
            errors._dictionary("gb")
    finally:
        monkeypatch.undo()
        errors._dictionary.cache_clear()


def test_output_shape():
    out = check("hello world", "us")
    assert set(out) == {
        "variant", "counts", "rates", "errors", "variant_mismatches", "unknown_names",
        "dictionary", "caveat",
    }  # fmt: skip
    assert out["variant"] == "us"
    assert set(out["counts"]) == {
        "tokens_checked", "sentences", "errors_total", "unique_errors", "variant_mismatches",
        "unknown_names",
    }  # fmt: skip
    assert set(out["rates"]) == {"errors_per_sentence", "errors_per_100_words"}


# --- no false positives --------------------------------------------------------


def test_clean_text_has_no_errors():
    out = check("The cat sat on the mat.")
    assert out["counts"]["errors_total"] == 0
    assert out["errors"] == []


@pytest.mark.parametrize(
    "text",
    [
        "I don't like it.",
        "The children's toys are here.",
        "Dr. Brown agreed.",
        "Bring fruit, e.g. apples.",
        "He moved to the U.S. last year.",
        "It is a well-known fact.",
        "James' car is red.",
        "It was popular in the 1990s.",
        "She can’t and won’t, they’d say.",
        "Visit https://example.com or write to me@example.com today.",
        "It rose 3.5% to 1,500 units, the 3rd rise.",
        "A climate-related, evidence-based policy.",
    ],
)
def test_no_false_positives(text):
    out = check(text)
    assert out["errors"] == [], out["errors"]
    assert out["unknown_names"] == [], out["unknown_names"]


def test_numerals_urls_and_abbreviations_are_not_checked():
    out = check("Visit https://example.com in 2019, e.g. today.")
    # visit, in, today
    assert out["counts"]["tokens_checked"] == 3


# --- real errors ---------------------------------------------------------------

MISSPELT = "I recieve it becuase it is definately alot. Teh end."


@pytest.mark.parametrize(
    "surface,expected",
    [
        ("recieve", "receive"),
        ("becuase", "because"),
        ("definately", "definitely"),
        ("alot", "a lot"),
        ("Teh", "The"),
    ],
)
def test_first_suggestion(surface, expected):
    assert first_suggestion(MISSPELT, surface) == expected


def test_error_counts_and_rates():
    out = check(MISSPELT)
    c = out["counts"]
    assert c["errors_total"] == 5
    assert c["unique_errors"] == 5
    assert c["tokens_checked"] == 10
    assert c["sentences"] == 2
    assert out["rates"]["errors_per_sentence"] == 2.5
    assert out["rates"]["errors_per_100_words"] == 50.0


def test_error_spans():
    out = check(MISSPELT)
    for e in out["errors"]:
        for s, t in e["spans"]:
            assert MISSPELT[s:t] == e["surface"]


def test_repeated_error_counted_with_all_spans():
    text = "I recieve mail. You recieve mail."
    (e,) = check(text)["errors"]
    assert e["count"] == 2
    assert e["spans"] == [[2, 9], [20, 27]]


def test_sentence_initial_misspelling_after_us_is_an_error():
    text = "He moved to the U.S. Recieve the parcel."
    out = check(text)
    assert error_surfaces(text) == ["Recieve"]
    assert out["unknown_names"] == []


def test_sentence_initial_misspelling_is_an_error_not_a_name():
    assert error_surfaces("Teh cat sat.") == ["Teh"]


# --- variants ------------------------------------------------------------------


def test_us_spelling_in_gb_mode_is_variant_mismatch():
    out = check("The color is nice.", "gb")
    assert out["errors"] == []
    (m,) = out["variant_mismatches"]
    assert (m["surface"], m["suggestions"][0], m["count"]) == ("color", "colour", 1)
    assert out["counts"]["errors_total"] == 0
    assert out["counts"]["variant_mismatches"] == 1


def test_gb_spelling_in_us_mode_is_variant_mismatch():
    out = check("The colour is nice.", "us")
    assert out["errors"] == []
    (m,) = out["variant_mismatches"]
    assert (m["surface"], m["suggestions"][0]) == ("colour", "color")


def test_variant_mismatch_keeps_case():
    (m,) = check("Color matters.", "gb")["variant_mismatches"]
    assert m["suggestions"][0] == "Colour"


@pytest.mark.parametrize(
    "text,variant",
    [
        ("She organised the programme and analysed the behaviour in the centre.", "gb"),
        ("She organized the program and analyzed the behavior in the center.", "us"),
    ],
)
def test_consistent_variant_is_clean(text, variant):
    out = check(text, variant)
    assert out["errors"] == [] and out["variant_mismatches"] == []


# --- names ---------------------------------------------------------------------


def test_allcaps_acronym_is_unknown_name():
    out = check("The UNESCOX report was late.")
    assert [n["surface"] for n in out["unknown_names"]] == ["UNESCOX"]
    assert out["errors"] == []
    assert out["counts"]["errors_total"] == 0


def test_capitalised_names_are_not_errors():
    text = "Mr Zbigniewski met Ms Okonkwo yesterday. Zbigniewski left."
    out = check(text)
    assert out["errors"] == []
    names = {n["surface"]: n["count"] for n in out["unknown_names"]}
    assert names == {"Zbigniewski": 2, "Okonkwo": 1}


def test_capitalised_typo_of_common_word_is_an_error():
    r = errors.analyze("The Goverment said it would act.")
    assert [e["surface"] for e in r["errors"]] == ["Goverment"]
    assert r["unknown_names"] == []


def test_surname_with_first_name_stays_a_name():
    r = errors.analyze("We met Thomas Browne and Mr Kowalski.")
    assert r["errors"] == []
