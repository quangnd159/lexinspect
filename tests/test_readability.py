"""Smoke tests for readability module + JSON envelope shape."""

from lexinspect import readability
from lexinspect._schema import SCHEMA_VERSION, envelope

SCORES = {
    "flesch_reading_ease",
    "flesch_kincaid_grade",
    "gunning_fog",
    "smog_index",
    "automated_readability_index",
    "coleman_liau_index",
    "dale_chall_readability_score",
    "linsear_write_formula",
    "text_standard",
}


def test_returns_expected_keys(simple):
    out = readability.analyze(simple)
    assert set(out) == {"counts", "averages", "scores", "reliability"}
    assert set(out["scores"]) == SCORES
    assert set(out["reliability"]) == {"reliable", "notes"}
    assert "difficult_words" in out["counts"]
    assert "reading_time_seconds" in out["counts"]


def test_simple_text_is_easier_than_academic(simple, academic):
    s = readability.analyze(simple)
    a = readability.analyze(academic)
    # FRE: higher = easier
    assert s["scores"]["flesch_reading_ease"] > a["scores"]["flesch_reading_ease"]
    # FK Grade: higher = harder
    assert s["scores"]["flesch_kincaid_grade"] < a["scores"]["flesch_kincaid_grade"]


def test_counts_are_positive(academic):
    out = readability.analyze(academic)
    assert out["counts"]["words"] > 0
    assert out["counts"]["sentences"] > 0
    assert out["counts"]["syllables"] > 0


def test_text_standard_is_median_of_grades(academic):
    s = readability.analyze(academic)["scores"]
    grades = sorted(
        [
            s["flesch_kincaid_grade"],
            s["gunning_fog"],
            s["smog_index"],
            s["automated_readability_index"],
            s["coleman_liau_index"],
            s["linsear_write_formula"],
            readability._dale_chall_grade(s["dale_chall_readability_score"]),
            readability._flesch_grade(s["flesch_reading_ease"]),
        ]
    )
    # Inputs are rounded to 2 dp before this recomputation, hence the tolerance.
    assert abs(s["text_standard"] - (grades[3] + grades[4]) / 2) <= 0.02


def test_envelope_shape(simple):
    payload = envelope("readability", "test.txt", len(simple), readability.analyze(simple))
    assert SCHEMA_VERSION == "2"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["module"] == "readability"
    assert payload["input"]["source"] == "test.txt"
    assert payload["input"]["char_count"] == len(simple)
    assert "scores" in payload["result"]


def test_envelope_word_count():
    payload = envelope("readability", "x", 3, {}, words=7)
    assert payload["input"] == {"source": "x", "char_count": 3, "word_count": 7}
    assert "word_count" not in envelope("readability", "x", 3, {})["input"]


def test_handles_empty_string():
    out = readability.analyze("")
    assert out["counts"]["words"] == 0
    assert out["counts"]["sentences"] == 0
    assert set(out["scores"].values()) == {0.0}
    assert out["reliability"]["reliable"] is False


def test_punctuation_only():
    out = readability.analyze("... !!! ---")
    assert out["counts"]["words"] == 0
