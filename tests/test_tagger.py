"""Smoke tests for the spaCy POS tagger wrapper."""

import pytest

from lexinspect import tagger


@pytest.fixture(scope="module")
def out():
    return tagger.analyze("The quick brown fox jumps over the lazy dog.")


def test_returns_expected_keys(out):
    assert set(out) >= {"counts", "ptb_distribution", "upos_distribution"}


def test_token_count_matches_visible_tokens(out):
    assert out["counts"]["total_tokens"] == 10  # 9 words + 1 period


def test_distributions_sum_to_total(out):
    assert sum(out["ptb_distribution"].values()) == out["counts"]["total_tokens"]
    assert sum(out["upos_distribution"].values()) == out["counts"]["total_tokens"]


def test_include_tokens_flag():
    out = tagger.analyze("Cats sleep.", include_tokens=True)
    assert "tokens" in out
    assert len(out["tokens"]) == 3
    assert out["tokens"][0]["text"] == "Cats"
