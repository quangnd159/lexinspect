"""Lexical diversity metrics. Wraps lexicalrichness.

MTLD and HD-D are the most reliable cross-text-length measures (Koizumi 2012,
McCarthy & Jarvis 2010). vocd-D is included for parity with Text Inspector
output but is sample-size dependent.
"""

from __future__ import annotations

from typing import Any

from lexicalrichness import LexicalRichness


def analyze(text: str) -> dict[str, Any]:
    lex = LexicalRichness(text)
    if lex.words == 0:
        return {
            "counts": {"tokens": 0, "types": 0},
            "scores": {},
            "note": "Empty or untokenizable text.",
        }

    out = {
        "counts": {"tokens": lex.words, "types": lex.terms},
        "scores": {
            "ttr": _round(lex.ttr),
            "rttr": _round(lex.rttr),
            "cttr": _round(lex.cttr),
            "msttr": _round(_safe(lex.msttr, segment_window=50)),
            "mattr": _round(_safe(lex.mattr, window_size=50)),
            "mtld": _round(_safe(lex.mtld, threshold=0.72)),
            "hdd": _round(_safe(lex.hdd, draws=42)),
            "herdan": _round(lex.Herdan),
            "summer": _round(lex.Summer),
            "maas": _round(lex.Maas),
        },
    }
    return out


def _safe(fn, **kw):
    try:
        return fn(**kw)
    except (ValueError, ZeroDivisionError):
        return None


def _round(x):
    if x is None:
        return None
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return None
