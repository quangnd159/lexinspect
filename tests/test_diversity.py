"""Lexical diversity: formulas, edge cases, and agreement with lexicalrichness.

lexicalrichness is no longer a dependency. Its formulas are re-implemented here,
independently and as plainly as possible (`_ref_*`), and the module's pure
functions are checked against them and against literal reference values
computed from the formulas, so a regression in either shows up.
"""

from __future__ import annotations

import math
from collections import Counter

import pytest
from conftest import NARRATIVE, analysed

from lexinspect import diversity

PASSAGE = (
    "the old man walked to the river every morning and the river was always cold "
    "he sat on a stone and watched the water run past the stone and the trees "
    "some days a bird came to the stone and sat with him and some days nobody came "
    "the man did not mind because the river was enough company for a man of his age "
    "in winter the water froze at the edges and the bird stopped coming but the man "
    "still walked to the river every morning and sat on the cold stone until noon"
)
TOKS = PASSAGE.split()  # 96 tokens, 50 types


# --- independent reference implementations (lexicalrichness semantics) --------


def _ref_mtld_pass(toks, threshold=0.72):
    terms, count, factors, ttr = set(), 0, 0.0, 1.0
    for tok in toks:
        count += 1
        terms.add(tok)
        ttr = len(terms) / count
        if ttr <= threshold:
            factors += 1
            terms, count = set(), 0
    if count:
        factors += (1 - ttr) / (1 - threshold)
    return len(toks) / factors


def _ref_mtld(toks):
    return (_ref_mtld_pass(toks) + _ref_mtld_pass(list(reversed(toks)))) / 2


def _ref_hdd(toks, draws=42):
    # 1 - P(type absent from a draw), hypergeometric via exact binomials.
    n = len(toks)
    return sum(
        (1 - math.comb(n - f, draws) / math.comb(n, draws)) / draws for f in Counter(toks).values()
    )


def _ref_mattr(toks, window=50):
    spans = [toks[i : i + window] for i in range(len(toks) - window + 1)]
    return sum(len(set(s)) / window for s in spans) / len(spans)


def _ref_msttr(toks, segment=50):
    segs = [toks[i : i + segment] for i in range(0, len(toks), segment)]
    segs = [s for s in segs if len(s) == segment]
    return sum(len(set(s)) / segment for s in segs) / len(segs)


# --- literal reference values on PASSAGE -------------------------------------
# N = 96, V = 50
#   TTR    50/96                          = 0.520833
#   RTTR   50/sqrt(96)                    = 5.103104
#   CTTR   50/sqrt(192)                   = 3.608439
#   Herdan ln 50 / ln 96                  = 0.857083
#   Summer ln ln 50 / ln ln 96            = 0.898424
#   Maas   (ln 96 - ln 50) / (ln 96)^2    = 0.031312
#   MSTTR  one complete 50-token segment (29 types) = 0.58
REFERENCE = {
    "ttr": 0.520833,
    "rttr": 5.103104,
    "cttr": 3.608439,
    "herdan": 0.857083,
    "summer": 0.898424,
    "maas": 0.031312,
    "msttr": 0.58,
    "mattr": 0.688936,
    "hdd": 0.673552,
    "mtld": 44.363636,
}


@pytest.mark.parametrize("name,expected", sorted(REFERENCE.items()))
def test_measures_match_reference_values(name, expected):
    assert getattr(diversity, name)(TOKS) == pytest.approx(expected, abs=1e-6)


def test_counts_of_reference_passage():
    assert (len(TOKS), len(set(TOKS))) == (96, 50)


@pytest.mark.parametrize(
    "name,ref",
    [("mtld", _ref_mtld), ("hdd", _ref_hdd), ("mattr", _ref_mattr), ("msttr", _ref_msttr)],
)
@pytest.mark.parametrize("mult", [1, 2, 3])
def test_measures_match_independent_implementation(name, ref, mult):
    toks = diversity.tokens(analysed(NARRATIVE * mult))
    assert getattr(diversity, name)(toks) == pytest.approx(ref(toks), rel=1e-9)


# --- MSTTR segment handling ----------------------------------------------------


def test_msttr_keeps_a_complete_final_segment():
    # 100 tokens = two complete segments: all-unique then all-same.
    toks = [f"u{i}" for i in range(50)] + ["same"] * 50
    # lexicalrichness discarded the second (complete) segment and reported 1.0.
    assert diversity.msttr(toks) == pytest.approx((1.0 + 1 / 50) / 2)


def test_msttr_discards_only_an_incomplete_final_segment():
    toks = [f"u{i}" for i in range(50)] + ["same"] * 30
    assert diversity.msttr(toks) == 1.0


def test_msttr_raises_below_one_segment():
    with pytest.raises(ValueError):
        diversity.msttr(["a"] * 49)


def test_mattr_single_window_equals_ttr():
    toks = TOKS[:50]
    assert diversity.mattr(toks) == pytest.approx(len(set(toks)) / 50)


def test_hdd_bounds():
    assert diversity.hdd([f"u{i}" for i in range(60)]) == pytest.approx(1.0)
    assert diversity.hdd(["x"] * 60) == pytest.approx(1 / 42)


# --- vocd-D --------------------------------------------------------------------


def test_vocd_model_fit_recovers_known_d():
    for d in (20.0, 70.0, 120.0):
        points = [(n, diversity._ttr_model(n, d)) for n in range(35, 51)]
        assert diversity._fit_d(points) == pytest.approx(d, rel=1e-3)


def test_vocd_d_is_deterministic():
    toks = diversity.tokens(analysed(NARRATIVE * 2))
    assert diversity.vocd_d(toks) == diversity.vocd_d(toks)
    out1 = diversity.analyze(NARRATIVE * 2, analysis=analysed(NARRATIVE * 2))
    out2 = diversity.analyze(NARRATIVE * 2)
    assert out1["scores"]["vocd_d"] == out2["scores"]["vocd_d"]


@pytest.mark.parametrize("mult", [2, 3])
def test_vocd_d_plausible_on_narrative(mult):
    d = diversity.analyze(NARRATIVE * mult, analysis=analysed(NARRATIVE * mult))["scores"]["vocd_d"]
    assert 30 <= d <= 150


def test_vocd_d_orders_diverse_above_repetitive():
    rep = (["the", "cat", "sat", "on", "mat"] * 30)[:150]
    div = [f"w{i % 120}" for i in range(150)]
    assert diversity.vocd_d(div) > diversity.vocd_d(rep)


def test_vocd_d_band_positions():
    out = diversity.analyze(NARRATIVE * 2, analysis=analysed(NARRATIVE * 2))
    d = out["scores"]["vocd_d"]
    for band in out["references"]["vocd_d_bands"]:
        expected = "below" if d < band["min"] else "above" if d > band["max"] else "within"
        assert band["position"] == expected


def test_vocd_d_needs_more_than_50_tokens():
    with pytest.raises(ValueError):
        diversity.vocd_d(["a", "b"] * 25)


# --- module output -------------------------------------------------------------


def test_returns_expected_keys(narrative):
    out = diversity.analyze(narrative, analysis=analysed(narrative))
    assert set(out) >= {"counts", "scores", "references"}
    assert set(out["scores"]) == {
        "ttr", "rttr", "cttr", "msttr", "mattr", "mtld", "hdd", "vocd_d", "herdan", "summer", "maas",
    }  # fmt: skip


def test_tokens_are_lowercased_words_without_numerals():
    a = analysed("Don't stop. In 2019 the well-known Band didn't STOP.")
    assert diversity.tokens(a) == [
        "don't", "stop", "in", "the", "well-known", "band", "didn't", "stop",
    ]  # fmt: skip


def test_repetitive_text_has_lower_ttr_than_diverse():
    rep = diversity.analyze("the cat the cat the cat the cat the cat " * 5)
    div = diversity.analyze(
        "Maria walked through twilight gardens beneath unfamiliar constellations."
    )
    assert rep["scores"]["ttr"] < div["scores"]["ttr"]


def test_short_text_nulls_and_note():
    out = diversity.analyze("Alpha beta gamma delta epsilon zeta eta theta iota kappa")
    s = out["scores"]
    assert s["ttr"] == 1.0
    for name in ("msttr", "mattr", "mtld", "hdd", "vocd_d"):
        assert s[name] is None, name
    assert "note" in out
    assert all("position" not in b for b in out["references"]["vocd_d_bands"])


def test_long_text_has_no_nulls():
    out = diversity.analyze(NARRATIVE * 2, analysis=analysed(NARRATIVE * 2))
    assert all(v is not None for v in out["scores"].values())
    assert "note" not in out


def test_mtld_floor():
    assert diversity.analyze(" ".join(f"word{i}" for i in range(49)))["scores"]["mtld"] is None
    assert diversity.analyze(" ".join(f"word{i}" for i in range(50)))["scores"]["mtld"] is not None


def test_single_type_text_does_not_crash():
    # log(V) == 0 for one type: Herdan/Summer/Maas must come back null or finite, not raise.
    for text in ("the the the the the", "hello hello", "aaa"):
        scores = diversity.analyze(text)["scores"]
        assert scores["summer"] is None
        assert scores["herdan"] is None or isinstance(scores["herdan"], float)


def test_empty_text():
    out = diversity.analyze("")
    assert out["counts"]["tokens"] == 0
    assert out["scores"] == {}
    assert len(out["references"]["vocd_d_bands"]) == 2


def test_references_block(narrative):
    refs = diversity.analyze(narrative, analysis=analysed(narrative))["references"]
    assert "vocd-D" in refs["note"]
    assert {b["name"] for b in refs["vocd_d_bands"]} == {
        "Adult L2 / ESL learner",
        "Adult native speaker, academic writing",
    }


def test_tiers_cover_every_score_once():
    out = diversity.analyze("The quick brown fox jumps over the lazy dog again and again. " * 10)
    tiers = out["tiers"]
    tiered = tiers["recommended"] + tiers["caution"] + tiers["legacy"]
    assert len(tiered) == len(set(tiered))
    assert set(tiered) == set(out["scores"])
