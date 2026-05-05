"""Smoke tests for readability module + JSON envelope shape."""

from pathlib import Path

import pytest

from lexinspect import readability
from lexinspect._schema import SCHEMA_VERSION, envelope

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


def test_returns_expected_keys(simple):
    out = readability.analyze(simple)
    assert set(out) == {"counts", "averages", "scores"}
    assert "flesch_reading_ease" in out["scores"]
    assert "flesch_kincaid_grade" in out["scores"]
    assert "gunning_fog" in out["scores"]


def test_simple_text_is_easier_than_academic(simple, academic):
    s = readability.analyze(simple)
    a = readability.analyze(academic)
    # FRE: higher = easier
    assert s["scores"]["flesch_reading_ease"] > a["scores"]["flesch_reading_ease"]
    # FK Grade: higher = harder
    assert s["scores"]["flesch_kincaid_grade"] < a["scores"]["flesch_kincaid_grade"]


def test_counts_are_positive(academic):
    out = readability.analyze(academic)
    assert out["counts"]["words"] > 0
    assert out["counts"]["sentences"] > 0
    assert out["counts"]["syllables"] > 0


def test_envelope_shape(simple):
    payload = envelope("readability", "test.txt", len(simple), readability.analyze(simple))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["module"] == "readability"
    assert payload["input"]["source"] == "test.txt"
    assert payload["input"]["char_count"] == len(simple)
    assert "scores" in payload["result"]


def test_handles_empty_string():
    out = readability.analyze("")
    assert out["counts"]["words"] == 0
