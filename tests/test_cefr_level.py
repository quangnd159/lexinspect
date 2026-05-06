"""Tests for CEFR text-level classification.

The transformer model is heavy (~400MB download, ~2–5s per inference) and is
*not* exercised by default in CI. Tests here split into two groups:

1. Always-on: contract checks that don't require the `cefr-level` extra to be
   installed. Verify that the module imports cleanly, that constants are
   correct, that calling `analyze()` without the extra raises a clear
   typed error, and that the empty-text path returns a well-formed envelope.

2. Opt-in (skipped unless `LEXINSPECT_TEST_CEFR_LEVEL=1` and the extra is
   installed): end-to-end smoke tests that actually run the model on short
   fixtures. Run locally with:

       LEXINSPECT_TEST_CEFR_LEVEL=1 uv run pytest tests/test_cefr_level.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lexinspect import cefr_level

FIXTURES = Path(__file__).parent / "fixtures"
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
RUN_MODEL = os.environ.get("LEXINSPECT_TEST_CEFR_LEVEL") == "1"


def _has_extras() -> bool:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


# --- Always-on: contract checks --------------------------------------------


def test_module_constants():
    assert cefr_level.LEVELS == LEVELS
    assert cefr_level.MODEL_ID.startswith("UniversalCEFR/")
    assert "Estimate only" in cefr_level.CAVEAT


def test_empty_text_returns_well_formed_envelope():
    out = cefr_level.analyze("")
    assert out["level"] is None
    assert out["confidence"] == 0.0
    assert set(out["all_levels"]) == set(LEVELS)
    assert all(v == 0.0 for v in out["all_levels"].values())
    assert out["top_2"] == []
    assert out["model"] == cefr_level.MODEL_ID
    assert out["method"] == "transformer-classifier"
    assert "caveat" in out


def test_whitespace_only_text_returns_empty():
    assert cefr_level.analyze("   \n\t  ").get("level") is None


@pytest.mark.skipif(_has_extras(), reason="cefr-level extra is installed; error path n/a")
def test_clear_error_when_extra_missing():
    with pytest.raises(cefr_level.CEFRLevelExtraNotInstalled) as ei:
        cefr_level.analyze("This is a short test passage.")
    assert "cefr-level" in str(ei.value)


# --- Opt-in: model smoke tests (require the extra + env var) ---------------


@pytest.fixture
def simple() -> str:
    return (FIXTURES / "sample_simple.txt").read_text()


@pytest.fixture
def academic() -> str:
    return (FIXTURES / "sample_academic.txt").read_text()


@pytest.mark.skipif(
    not (RUN_MODEL and _has_extras()),
    reason="Set LEXINSPECT_TEST_CEFR_LEVEL=1 and install the cefr-level extra.",
)
def test_returns_expected_keys(simple):
    out = cefr_level.analyze(simple)
    assert set(out) >= {
        "level",
        "confidence",
        "all_levels",
        "top_2",
        "model",
        "method",
        "caveat",
    }
    assert out["level"] in LEVELS
    assert 0.0 <= out["confidence"] <= 1.0
    assert set(out["all_levels"]) == set(LEVELS)
    assert abs(sum(out["all_levels"].values()) - 1.0) < 0.01
    assert len(out["top_2"]) == 2


@pytest.mark.skipif(
    not (RUN_MODEL and _has_extras()),
    reason="Set LEXINSPECT_TEST_CEFR_LEVEL=1 and install the cefr-level extra.",
)
def test_simple_text_classifies_lower_than_academic(simple, academic):
    s = cefr_level.analyze(simple)
    a = cefr_level.analyze(academic)
    s_idx = LEVELS.index(s["level"])
    a_idx = LEVELS.index(a["level"])
    # Rank correlation, not number-matching: simple text should not be rated
    # *higher* than academic. Allow equal (both can land in B1/B2 on short
    # samples) but never reversed.
    assert a_idx >= s_idx
