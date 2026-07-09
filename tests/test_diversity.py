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


def test_single_type_text_does_not_crash():
    """`the the the` makes types == 1, so log(types) == 0.

    Herdan/Summer/Maas divide by or take the log of that. Unguarded this was a
    500 on /v1/diversity and /v1/analyze for input a curious user types in ten
    seconds. The metrics should come back null, not raise.
    """
    for text in ("the the the the the", "hello hello", "aaa"):
        scores = diversity.analyze(text)["scores"]
        assert scores["summer"] is None
        assert scores["herdan"] is None or isinstance(scores["herdan"], float)


def test_mtld_suppressed_below_the_token_floor():
    """MTLD never raises, so it silently returned nonsense on short text.

    Twelve all-unique words scored 12.0, which reads as maximally repetitive
    when it is maximally diverse. The tab promises these come back empty.
    """
    short = diversity.analyze("Alpha beta gamma delta epsilon zeta eta theta iota kappa")
    assert short["scores"]["mtld"] is None
    assert "note" in short

    long_text = " ".join(f"word{i}" for i in range(60))
    assert diversity.analyze(long_text)["scores"]["mtld"] is not None
    assert "note" not in diversity.analyze(long_text)
