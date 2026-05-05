"""Smoke tests for BNC/COCA band profiling."""

from pathlib import Path

import pytest

from lexinspect import bnc_coca

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


def test_data_loads():
    data = bnc_coca._load()
    assert data["band_count"] == 10
    assert data["headword_count"] >= 9000


def test_returns_expected_keys(academic):
    out = bnc_coca.analyze(academic)
    assert {"counts", "coverage_pct", "per_band", "off_list_sample"} <= set(out)
    for b in range(1, 11):
        assert str(b) in out["per_band"]


def test_simple_text_concentrates_in_band_1(simple):
    out = bnc_coca.analyze(simple)
    band1 = out["per_band"]["1"]["tokens"]
    higher = sum(out["per_band"][str(b)]["tokens"] for b in range(2, 11))
    assert band1 > higher


def test_cumulative_coverage_monotonic(academic):
    out = bnc_coca.analyze(academic)
    cum = [out["per_band"][str(b)]["cumulative_coverage_pct"] for b in range(1, 11)]
    assert cum == sorted(cum)
