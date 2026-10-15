"""Smoke tests for the spaCy POS tagger wrapper."""

import pytest

from lexinspect import tagger


@pytest.fixture(scope="module")
def out():
    return tagger.analyze("The quick brown fox jumps over the lazy dog.")


def test_returns_expected_keys(out):
    assert set(out) >= {"counts", "summary", "ptb_distribution", "upos_distribution"}


def test_token_count_matches_visible_tokens(out):
    assert out["counts"]["total_tokens"] == 10  # 9 words + 1 period


def test_distributions_sum_to_total(out):
    assert sum(out["ptb_distribution"].values()) == out["counts"]["total_tokens"]
    assert sum(out["upos_distribution"].values()) == out["counts"]["total_tokens"]


def test_summary_has_aggregates(out):
    s = out["summary"]
    assert {
        "content_tokens",
        "types",
        "type_token_ratio",
        "tokens_per_type",
        "total_verbal_elements",
        "verbal_elements_per_sentence",
        "total_noun_elements",
        "noun_elements_per_sentence",
    } <= set(s)
    # 'jumps' is the one verb in 'The quick brown fox jumps over the lazy dog.'
    assert s["total_verbal_elements"] >= 1
    # 'fox' and 'dog' are the nouns.
    assert s["total_noun_elements"] >= 2


def test_include_tokens_flag():
    out = tagger.analyze("Cats sleep.", include_tokens=True)
    assert "tokens" in out
    assert len(out["tokens"]) == 3
    assert out["tokens"][0]["text"] == "Cats"


def test_modals_are_verbal_elements():
    out = tagger.analyze("You must go.")
    # must (MD) + go (VB)
    assert out["summary"]["total_verbal_elements"] == 2


def test_summary_counts_words_not_spacy_tokens():
    out = tagger.analyze("I don't own 3 well-known books.")
    s = out["summary"]
    # I, don't, own, well-known, books — the numeral is not a content word
    assert s["content_tokens"] == 5
    assert out["counts"]["sentences"] == 1
    # The distributions are over spaCy tokens: I do n't own 3 well - known books .
    assert out["counts"]["total_tokens"] == 10


def test_accepts_shared_analysis():
    from lexinspect._text import analyse

    text = "The quick brown fox jumps over the lazy dog."
    assert tagger.analyze(text, analysis=analyse(text)) == tagger.analyze(text)
