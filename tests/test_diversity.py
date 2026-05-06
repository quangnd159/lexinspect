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


def test_references_block_surfaces_vocd_d_bands(narrative):
    out = diversity.analyze(narrative)
    refs = out["references"]
    assert "note" in refs
    assert "vocd-D" in refs["note"]
    bands = refs["vocd_d_bands"]
    assert len(bands) == 2
    names = {b["name"] for b in bands}
    assert names == {"Adult L2 / ESL learner", "Adult native speaker, academic writing"}
    # No automatic comparison — bands are reference-only.
    assert "score" not in refs
    assert "lands_in" not in refs


def test_references_present_on_empty_text():
    out = diversity.analyze("")
    assert "references" in out
    assert len(out["references"]["vocd_d_bands"]) == 2


def test_handles_empty_string():
    out = diversity.analyze("")
    assert out["counts"]["tokens"] == 0
