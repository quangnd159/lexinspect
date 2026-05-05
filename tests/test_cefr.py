"""Smoke tests for CEFR vocabulary profiling."""

from pathlib import Path

import pytest

from lexinspect import cefr

FIXTURES = Path(__file__).parent / "fixtures"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


def test_data_loads():
    data = cefr._load()
    assert data["lemma_count"] >= 8000
    assert set(data["per_level_count"]) == set(LEVELS)
    assert all(data["per_level_count"][lvl] > 0 for lvl in LEVELS)


def test_returns_expected_keys(simple):
    out = cefr.analyze(simple)
    assert {
        "counts",
        "coverage_pct",
        "per_level",
        "dominant_level",
        "estimated_level_95th",
        "caveat",
    } <= set(out)
    assert set(out["per_level"]) == set(LEVELS)


def test_simple_text_dominant_is_low_level(simple):
    out = cefr.analyze(simple)
    assert out["dominant_level"] in {"A1", "A2"}


def test_academic_text_reaches_higher_levels(academic):
    out = cefr.analyze(academic)
    high = out["per_level"]["B2"]["tokens"] + out["per_level"]["C1"]["tokens"] + out["per_level"]["C2"]["tokens"]
    assert high >= 2


def test_cumulative_coverage_monotonic(academic):
    out = cefr.analyze(academic)
    cum = [out["per_level"][lvl]["cumulative_coverage_pct"] for lvl in LEVELS]
    assert cum == sorted(cum)


def test_known_words_at_expected_levels():
    out = cefr.analyze("the cat exterior")
    # 'the', 'cat' should hit A1; 'exterior' is a C1 Octanove entry
    assert out["per_level"]["A1"]["tokens"] >= 1
    assert out["per_level"]["C1"]["tokens"] >= 1
