"""Smoke tests for statistics module."""

from lexinspect import statistics


def test_returns_expected_keys(simple):
    out = statistics.analyze(simple)
    assert set(out) == {"counts", "averages", "excluded_digits"}
    assert {
        "characters_with_spaces",
        "characters_without_spaces",
        "tokens_excluding_numbers",
        "unique_types_excluding_numbers",
        "sentences",
        "syllables",
        "polysyllable_words",
        "excluded_numeric_tokens",
    } <= set(out["counts"])
    assert {
        "tokens_per_sentence",
        "type_token_ratio",
        "syllables_per_word",
        "syllables_per_sentence",
        "syllables_per_100_words",
        "polysyllable_pct",
    } <= set(out["averages"])


def test_counts_are_positive(simple):
    out = statistics.analyze(simple)
    assert out["counts"]["tokens_excluding_numbers"] > 0
    assert out["counts"]["sentences"] > 0
    assert out["counts"]["syllables"] > 0


def test_academic_has_more_polysyllables_than_simple(simple, academic):
    s = statistics.analyze(simple)
    a = statistics.analyze(academic)
    assert a["averages"]["polysyllable_pct"] > s["averages"]["polysyllable_pct"]


def test_type_token_ratio_within_bounds(simple):
    out = statistics.analyze(simple)
    ttr = out["averages"]["type_token_ratio"]
    assert 0.0 < ttr <= 1.0


def test_excludes_numeric_tokens():
    text = "The show debuted in 2015 but was cancelled in 2018."
    out = statistics.analyze(text)
    assert out["excluded_digits"] == ["2015", "2018"]
    assert out["counts"]["excluded_numeric_tokens"] == 2
    # The show debuted in but was cancelled in
    assert out["counts"]["tokens_excluding_numbers"] == 8


def test_numeric_forms_excluded():
    out = statistics.analyze("It rose 3.5% to 1,500 in the 1990s, the 3rd rise.")
    assert out["excluded_digits"] == ["3.5", "1,500", "1990s", "3rd"]
    # It rose to in the the rise
    assert out["counts"]["tokens_excluding_numbers"] == 7


def test_contractions_and_compounds_count_once():
    out = statistics.analyze("I don't think the well-known author's book can't sell.")
    # I don't think the well-known author's book can't sell
    assert out["counts"]["tokens_excluding_numbers"] == 9
    assert out["counts"]["sentences"] == 1


def test_keeps_word_numerals():
    out = statistics.analyze("There were twenty children playing.")
    # 'twenty' is a word numeral — kept in tokens, not in excluded_digits.
    assert out["excluded_digits"] == []
    assert out["counts"]["tokens_excluding_numbers"] == 5  # There were twenty children playing


def test_handles_empty_string():
    out = statistics.analyze("")
    assert out["counts"]["tokens_excluding_numbers"] == 0
    assert out["counts"]["sentences"] == 0
    assert out["averages"]["type_token_ratio"] == 0.0
    assert out["excluded_digits"] == []
