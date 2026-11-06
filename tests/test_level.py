"""Tests for the reading-text CEFR level estimate (`lexinspect.level`)."""

from __future__ import annotations

import ast
import math
import sys
from pathlib import Path

import pytest
from conftest import analysed

from lexinspect import level
from lexinspect.pipeline import run_all

# Written for these tests (no third-party text). A2: a simple graded-reader
# style self-description. C1: a dense academic paragraph.
A2_TEXT = (
    "My name is Anna and I live in a small town near the sea. Every morning I get up at "
    "seven o'clock. I have breakfast with my mother and my little brother. We usually eat "
    "bread and eggs, and I drink a cup of tea. Then I walk to school with my best friend, "
    "Maria. Our school is not very big, but it has a nice garden. My favourite subject is "
    "English because the teacher is very kind and the lessons are fun. After school I play "
    "football in the park or I watch TV at home. At the weekend my family often goes to the "
    "beach. We swim, play games and have lunch in a cafe. I love my town because the people "
    "are friendly."
)
C1_TEXT = (
    "Although the notion that economic growth inevitably erodes biodiversity has gained "
    "considerable traction, the empirical evidence underpinning it remains surprisingly "
    "contested. Proponents of the so-called environmental Kuznets curve contend that, beyond "
    "a certain threshold of prosperity, societies acquire both the institutional capacity and "
    "the political will to mitigate ecological degradation. Critics, however, argue that such "
    "apparent improvements frequently reflect the displacement of resource-intensive "
    "production to jurisdictions with less stringent regulation, rather than any genuine "
    "decoupling of consumption from environmental harm. Disentangling these competing "
    "explanations is far from straightforward, not least because conventional indicators "
    "conflate distinct phenomena and are themselves susceptible to methodological bias. "
    "Consequently, policymakers who invoke aggregate statistics to justify complacency may "
    "be drawing unwarranted inferences from fundamentally ambiguous data."
)


def _results(text: str) -> dict:
    _, results = run_all(text, analysis=analysed(text))
    return results


def _expected(est: dict) -> float:
    return sum((i + 1) * est["probabilities"][lv] for i, lv in enumerate(level.LEVELS))


def test_model_file_loads():
    m = level.model()
    assert m["levels"] == level.LEVELS
    assert len(m["thresholds"]) == 5
    assert m["thresholds"] == sorted(m["thresholds"])
    assert m["min_words"] == 100
    assert m["features"]
    for f in m["features"]:
        assert f["name"] in level.FEATURES
        assert f["sd"] > 0
        assert math.isfinite(f["weight"])
        if f["sign_constraint"] == ">= 0":
            assert f["weight"] >= 0
    assert m["licence"].startswith("CC BY-NC-SA 4.0")
    assert set(m["metadata"]["training_data"]) == {"cambridge_exams", "elg_cefr_en"}
    s = m["summary_for_users"]
    assert 0 < s["held_out_within_one"] <= 1
    assert s["text"]


@pytest.mark.parametrize("text", [A2_TEXT, C1_TEXT])
def test_probabilities_sum_to_one(text):
    est = level.estimate(_results(text))
    assert est["applicable"] is True
    assert set(est["probabilities"]) == set(level.LEVELS)
    assert sum(est["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
    assert all(p >= 0 for p in est["probabilities"].values())
    assert est["level"] == max(est["probabilities"], key=est["probabilities"].get)
    rng = est["range"]
    idx = [level.LEVELS.index(lv) for lv in rng]
    assert idx == list(range(idx[0], idx[0] + len(idx)))  # adjacent
    assert sum(est["probabilities"][lv] for lv in rng) >= 0.8 - 1e-3
    assert est["level"] in rng
    assert 1 <= len(est["contributions"]) <= 3
    assert all(c["text"] for c in est["contributions"])
    assert est["confidence"]["label"] in {"high", "moderate", "low"}
    assert est["evaluation"]["held_out_within_one"] > 0


def test_simple_text_scores_lower_than_academic_text():
    easy = level.estimate(_results(A2_TEXT))
    hard = level.estimate(_results(C1_TEXT))
    assert _expected(easy) < _expected(hard)
    assert level.LEVELS.index(easy["level"]) < level.LEVELS.index(hard["level"])
    assert easy["level"] in {"A1", "A2", "B1"}
    assert hard["level"] in {"B2", "C1", "C2"}


def test_not_applicable_below_length_floor():
    short = "The cat sat on the mat. It was warm, and the cat was happy to sleep there."
    est = level.estimate(_results(short))
    assert est["applicable"] is False
    assert est["level"] is None and est["probabilities"] is None and est["range"] is None
    assert "100" in est["reason"]
    assert est["evaluation"]  # the evaluation summary is still shown


def test_missing_modules_not_applicable():
    est = level.estimate({"readability": _results(A2_TEXT)["readability"]})
    assert est["applicable"] is False
    assert "cefr" in est["reason"]


def test_deterministic():
    a = level.estimate(_results(C1_TEXT))
    b = level.estimate(_results(C1_TEXT))
    _, fresh = run_all(C1_TEXT)  # a fresh parse, not the shared one
    assert a == b == level.estimate(fresh)


def test_level_range():
    p = {"A1": 0.05, "A2": 0.5, "B1": 0.35, "B2": 0.07, "C1": 0.02, "C2": 0.01}
    assert level.level_range(p) == ["A2", "B1"]
    p = {"A1": 0.0, "A2": 0.0, "B1": 0.9, "B2": 0.1, "C1": 0.0, "C2": 0.0}
    assert level.level_range(p) == ["B1"]
    p = {lv: 1 / 6 for lv in level.LEVELS}
    assert len(level.level_range(p)) == 5


def test_cvla_matches_published_example():
    # Uchida & Negishi 2018, Table 4: the Simple English Wikipedia "Writing"
    # entry, Reading mode.
    out = level.cvla({"ari": 7.72, "verbs_per_sentence": 2.89, "avr_diff": 1.68, "b_per_a": 0.19})
    assert [out["indices"][k]["level"] for k in level.CVLA_READING] == [
        "A2.2",
        "B2.2",
        "B2.1",
        "B1.1",
    ]
    assert out["cefr_j_level"] == "B1.2"
    assert out["level"] == "B1"
    # Section 3.5: estimates 1.1, 1.5, 2.1 and 2.6 average to 1.825, A2.1.
    assert level.cvla_label(1.825) == ("A2.1", "A2")


def test_cvla_indices_from_analysis():
    a = analysed(A2_TEXT)
    ari = _results(A2_TEXT)["readability"]["scores"]["automated_readability_index"]
    idx = level.cvla_indices(a, ari)
    assert idx["verbs_per_sentence"] > 0
    assert 1.0 <= idx["avr_diff"] <= 2.0  # nearly all content words are A-level
    assert idx["b_per_a"] < 0.2


def test_estimator_is_pure_stdlib():
    src = Path(level.__file__).read_text(encoding="utf-8")
    roots = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    assert roots - {"lexinspect", "__future__"} <= set(sys.stdlib_module_names)


def test_estimate_refuses_texts_without_varied_rated_words():
    """Word count alone would let through number lists and repetition."""
    from lexinspect import pipeline

    for text in ["Ok, " * 110, " ".join(str(i) for i in range(150))]:
        _, r = pipeline.run_all(text, modules=["level"])
        assert r["level"]["applicable"] is False
        assert "too few distinct words" in r["level"]["reason"]
