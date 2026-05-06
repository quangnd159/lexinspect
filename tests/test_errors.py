"""Tests for the optional spelling-errors module.

The real spell-check tests are gated behind ``LEXINSPECT_TEST_ERRORS=1``
because they require the `errors` extra to be installed *and* will trigger a
~1.5 MB Hunspell-dictionary download into the user cache on first run. The
shape tests below run unconditionally — they exercise the import-level
contract (custom exceptions, validation, lazy import) without touching
spylls or the network.
"""

from __future__ import annotations

import os

import pytest

from lexinspect import errors

REAL = os.getenv("LEXINSPECT_TEST_ERRORS") == "1"


def test_invalid_variant_raises_value_error():
    with pytest.raises(ValueError):
        errors.analyze("hello", variant="fr")


def test_missing_extra_raises_clear_error(monkeypatch):
    """If spylls isn't importable, _dictionary surfaces a custom exception."""
    # Wipe the cached loader so the import attempt happens fresh.
    errors._dictionary.cache_clear()
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name.startswith("spylls"):
            raise ImportError("simulated missing spylls")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(errors.ErrorsExtraNotInstalled):
        errors._dictionary("gb")
    errors._dictionary.cache_clear()


def test_valid_variants_constant():
    assert errors.VALID_VARIANTS == ("gb", "us")


@pytest.mark.skipif(not REAL, reason="LEXINSPECT_TEST_ERRORS=1 not set")
def test_real_check_flags_an_obvious_misspelling():
    out = errors.analyze("Ths is a smple test of speling.", variant="gb")
    surfaces = {e["surface"].lower() for e in out["errors"]}
    # 'Ths', 'smple', 'speling' are all definite misspellings the dict knows.
    assert surfaces & {"ths", "smple", "speling"}
    assert out["counts"]["errors_total"] >= 1
    assert out["counts"]["tokens_checked"] > 0


@pytest.mark.skipif(not REAL, reason="LEXINSPECT_TEST_ERRORS=1 not set")
def test_real_clean_text_has_no_errors():
    out = errors.analyze("The cat sat on the mat.", variant="gb")
    assert out["counts"]["errors_total"] == 0
    assert out["errors"] == []


@pytest.mark.skipif(not REAL, reason="LEXINSPECT_TEST_ERRORS=1 not set")
def test_real_envelope_shape():
    out = errors.analyze("hello world", variant="us")
    assert set(out) == {"variant", "counts", "rates", "errors", "dictionary", "caveat"}
    assert out["variant"] == "us"
    assert {"tokens_checked", "sentences", "errors_total", "unique_errors"} <= set(out["counts"])
    assert {"errors_per_sentence", "errors_per_100_words"} <= set(out["rates"])
