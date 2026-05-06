"""CEFR text-level classification (A1–C2) via UniversalCEFR ModernBERT.

This module is the *judgement* counterpart to the existing `cefr` module.
Where `cefr` reports a vocabulary-profile coverage curve plus a 95th-percentile
heuristic, `cefr_level` returns a single CEFR band with a confidence
distribution from a transformer fine-tuned on the UniversalCEFR corpus
(Imperial et al., EMNLP 2025; 505k texts across 13 languages, English the
largest slice).

Model: `UniversalCEFR/ModernBERT-base-cefr-all-classifier` (Apache 2.0,
~100M parameters, max 8192 tokens). Six output classes A1–C2.

Heavy ML dependency. Install via:
    uv sync --extra cefr-level

Lazy-loaded — importing this module without the extras installed is fine,
but calling `analyze()` will raise a clear error.

Caveats: every published CEFR text classifier is an estimate. Vocabulary
features dominate the prediction signal; syntactic complexity and discourse
organisation are under-weighted. Calibrated on writing/reading/listening,
not speech. See CAVEATS.md and the Atlas note `CEFR Text-Level Classification`
for the universal limits.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

MODEL_ID = "UniversalCEFR/ModernBERT-base-cefr-all-classifier"
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

CAVEAT = (
    "Estimate only; not for high-stakes decisions. Trained on the UniversalCEFR "
    "corpus (Imperial et al., EMNLP 2025; Apache 2.0). Vocabulary features dominate "
    "the prediction; syntactic complexity, discourse organisation, and topic "
    "familiarity are under-weighted. Calibrated on writing/reading/listening, not "
    "speech. Adjacent-band confusion is irreducible — within-one-level reliability "
    "is the realistic target. Combine with readability, BNC/COCA, diversity, and "
    "metadiscourse signals before reporting a level."
)


class CEFRLevelExtraNotInstalled(RuntimeError):
    """Raised when the `cefr-level` extra is not installed."""


@lru_cache(maxsize=1)
def _pipeline():
    try:
        from transformers import logging as hf_logging  # type: ignore
        from transformers import pipeline  # type: ignore
    except ImportError as e:
        raise CEFRLevelExtraNotInstalled(
            "The `cefr-level` extra is not installed. Run:\n"
            "    uv sync --extra cefr-level\n"
            "or:\n"
            "    pip install 'lexinspect[cefr-level]'"
        ) from e

    # Suppress info-level chatter (HF Hub anonymous-request warning,
    # weight-loading progress) so the CLI's stderr stays clean. Errors
    # still surface.
    hf_logging.set_verbosity_error()

    # `top_k=None` returns scores for every class.
    return pipeline(
        "text-classification",
        model=MODEL_ID,
        tokenizer=MODEL_ID,
        top_k=None,
    )


def analyze(text: str) -> dict[str, Any]:
    """Classify `text` into a CEFR level (A1–C2) with a confidence distribution.

    First call downloads the model (~400MB) into the HuggingFace cache.
    Subsequent calls reuse the in-memory pipeline. CPU inference takes ~2–5s
    per text on a typical laptop.
    """
    if not text or not text.strip():
        return _empty_result()

    pipe = _pipeline()
    raw = pipe(text, truncation=True)

    # `pipeline` with `top_k=None` returns either:
    #   [[{"label": "A1", "score": ...}, ...]]  (newer transformers)
    # or:
    #   [{"label": "A1", "score": ...}, ...]    (older transformers)
    # Normalise.
    scores = raw[0] if raw and isinstance(raw[0], list) else raw

    by_level = {item["label"]: round(float(item["score"]), 4) for item in scores}
    # Force canonical ordering even if model returns labels out-of-order.
    all_levels = {lvl: by_level.get(lvl, 0.0) for lvl in LEVELS}

    ranked = sorted(all_levels.items(), key=lambda kv: kv[1], reverse=True)
    top_level, top_conf = ranked[0]
    top_2 = [lvl for lvl, _ in ranked[:2]]

    return {
        "level": top_level,
        "confidence": top_conf,
        "all_levels": all_levels,
        "top_2": top_2,
        "model": MODEL_ID,
        "method": "transformer-classifier",
        "caveat": CAVEAT,
    }


def _empty_result() -> dict[str, Any]:
    return {
        "level": None,
        "confidence": 0.0,
        "all_levels": {lvl: 0.0 for lvl in LEVELS},
        "top_2": [],
        "model": MODEL_ID,
        "method": "transformer-classifier",
        "caveat": CAVEAT,
    }
