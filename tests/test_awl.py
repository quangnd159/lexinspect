"""Smoke tests for AWL profiling."""

from pathlib import Path

import pytest

from lexinspect import awl

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


def test_data_loads():
    data = awl._load_data()
    assert data["headword_count"] == 570
    assert sum(data["sublist_counts"].values()) == 570


def test_returns_expected_keys(academic):
    out = awl.analyze(academic)
    assert set(out) >= {"counts", "coverage_pct", "per_sublist", "families_found"}
    assert all(str(i) in out["per_sublist"] for i in range(1, 11))


def test_academic_text_has_higher_awl_coverage_than_simple(simple, academic):
    s = awl.analyze(simple)
    a = awl.analyze(academic)
    assert a["coverage_pct"] > s["coverage_pct"]
    assert a["counts"]["awl_families"] > s["counts"]["awl_families"]


def test_known_awl_words_detected():
    out = awl.analyze("The analysis evaluated significant policy approaches.")
    fams = out["families_found"]
    # analysis -> analyse, evaluated -> evaluate, significant -> significant,
    # policy -> policy, approaches -> approach
    assert any(f in fams for f in ["analyse", "analyze"])
    assert "evaluate" in fams
    assert "significant" in fams
    assert "policy" in fams
    assert "approach" in fams


def test_no_awl_in_pure_function_words():
    out = awl.analyze("The cat is on the mat.")
    assert out["counts"]["awl_tokens"] == 0
