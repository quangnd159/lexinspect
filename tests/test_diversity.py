"""Smoke tests for lexical diversity module."""

from pathlib import Path

import pytest

from lexinspect import diversity

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def narrative() -> str:
    return (FIXTURES / "sample_narrative.txt").read_text()


def test_returns_expected_keys(narrative):
    out = diversity.analyze(narrative)
    assert set(out) >= {"counts", "scores"}
    assert "mtld" in out["scores"]
    assert "hdd" in out["scores"]
    assert "ttr" in out["scores"]


def test_ttr_within_range(narrative):
    out = diversity.analyze(narrative)
    ttr = out["scores"]["ttr"]
    assert 0.0 < ttr <= 1.0


def test_repetitive_text_has_lower_ttr_than_diverse():
    rep = "the cat the cat the cat the cat the cat " * 5
    div = "Maria walked through twilight gardens beneath unfamiliar constellations."
    r = diversity.analyze(rep)
    d = diversity.analyze(div)
    assert r["scores"]["ttr"] < d["scores"]["ttr"]


def test_handles_empty_string():
    out = diversity.analyze("")
    assert out["counts"]["tokens"] == 0
