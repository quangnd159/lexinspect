"""Smoke tests for NGSL/NAWL coverage."""

from pathlib import Path

import pytest

from lexinspect import ngsl

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


def test_data_loads():
    n = ngsl._ngsl()
    a = ngsl._nawl()
    assert len(n) >= 2500
    assert len(a) >= 900


def test_returns_expected_keys(simple):
    out = ngsl.analyze(simple)
    assert {"counts", "coverage_pct", "ngsl_lemmas_found", "nawl_lemmas_found"} <= set(out)


def test_simple_text_high_ngsl_coverage(simple):
    out = ngsl.analyze(simple)
    assert out["coverage_pct"]["ngsl"] >= 80.0


def test_academic_text_has_nawl_hits(academic):
    out = ngsl.analyze(academic)
    assert out["counts"]["nawl_tokens"] >= 1
