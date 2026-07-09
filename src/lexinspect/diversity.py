"""Lexical diversity metrics. Wraps lexicalrichness.

MTLD and HD-D are the most reliable cross-text-length measures (Koizumi 2012,
McCarthy & Jarvis 2010). lexicalrichness exposes HD-D (a hypergeometric
probability bounded 0–1, McCarthy & Jarvis 2007) but **not** Durán's vocd-D
(scale ~30–150, McKee, Malvern & Richards 2000). The two are highly
rank-correlated but live on different numeric scales — they should never be
compared against each other's reference ranges.

The `references` block surfaces the two published vocd-D ranges from Durán,
Malvern, Richards & Chipere (2004) **for awareness only** — the user can
read what an Adult L2 learner or an Adult native academic writer typically
scores, but lexinspect does not compute vocd-D itself, so no auto-comparison
against the user's text is performed. Implementing vocd-D properly requires
the McKee/Malvern/Richards 2000 sub-sample TTR curve-fitting procedure;
adding it is a fair Phase-7 follow-up.
"""

from __future__ import annotations

from typing import Any

from lexicalrichness import LexicalRichness

# Published reference ranges for D (vocd-D) from Durán, Malvern, Richards &
# Chipere (2004), Applied Linguistics 25/2: 220–242. Only the two ranges
# explicitly stated in the paper's abstract are bundled. lexinspect doesn't
# compute vocd-D itself, so these are for reading reference, not auto-compare.
VOCD_D_REFERENCE_RANGES: list[dict[str, Any]] = [
    {
        "name": "Adult L2 / ESL learner",
        "min": 40.0,
        "max": 70.0,
        "source": "Durán, Malvern, Richards & Chipere 2004 (Applied Linguistics 25/2)",
    },
    {
        "name": "Adult native speaker, academic writing",
        "min": 80.0,
        "max": 105.0,
        "source": "Durán, Malvern, Richards & Chipere 2004 (Applied Linguistics 25/2)",
    },
]

_REFERENCES_NOTE = (
    "Reference ranges are for vocd-D (Durán et al. 2004). lexinspect does not "
    "compute vocd-D — the closest measure exposed is HD-D, which is "
    "rank-correlated but on a different numeric scale (0–1 vs ~30–150). Read "
    "the bands for context; do not compare them directly against the HD-D or "
    "MTLD scores above."
)


# MTLD's published procedure needs enough tokens for at least one complete
# factor; below the same ~50-token floor the other windowed measures use, its
# fallback is not a measurement.
MIN_TOKENS_MTLD = 50
MIN_TOKENS_RELIABLE = 50


def analyze(text: str) -> dict[str, Any]:
    lex = LexicalRichness(text)
    if lex.words == 0:
        return {
            "counts": {"tokens": 0, "types": 0},
            "scores": {},
            "references": _references_block(),
            "note": "Empty or untokenizable text.",
        }

    out = {
        "counts": {"tokens": lex.words, "types": lex.terms},
        "scores": {
            "ttr": _round(_safe_prop(lambda: lex.ttr)),
            "rttr": _round(_safe_prop(lambda: lex.rttr)),
            "cttr": _round(_safe_prop(lambda: lex.cttr)),
            "msttr": _round(_safe(lex.msttr, segment_window=50)),
            "mattr": _round(_safe(lex.mattr, window_size=50)),
            # msttr/mattr/hdd raise below their window or draw size, so `_safe`
            # already suppresses them. MTLD never raises: its factor-count
            # fallback always yields a number, and on short text that number is
            # nonsense — twelve all-unique words score 12.0, which reads as
            # maximally repetitive when it is maximally diverse. Suppress it
            # explicitly so the module keeps the promise the other metrics keep.
            "mtld": (
                _round(_safe(lex.mtld, threshold=0.72))
                if lex.words >= MIN_TOKENS_MTLD
                else None
            ),
            "hdd": _round(_safe(lex.hdd, draws=42)),
            "herdan": _round(_safe_prop(lambda: lex.Herdan)),
            "summer": _round(_safe_prop(lambda: lex.Summer)),
            "maas": _round(_safe_prop(lambda: lex.Maas)),
        },
        "references": _references_block(),
    }
    if lex.words < MIN_TOKENS_RELIABLE:
        out["note"] = (
            f"Only {lex.words} tokens. Lexical-diversity measures are sample-size "
            f"dependent; scores below ~{MIN_TOKENS_RELIABLE} tokens are unstable and "
            f"the ones that cannot be computed at all are reported as null."
        )
    return out


def _references_block() -> dict[str, Any]:
    return {
        "vocd_d_bands": [dict(b) for b in VOCD_D_REFERENCE_RANGES],
        "note": _REFERENCES_NOTE,
    }


def _safe_prop(get):
    """Guard the property-style metrics the same way `_safe` guards the callables.

    Herdan/Summer/Maas are ratios of logs of the type and token counts. A text
    with exactly one distinct type ("the the the") makes log(types) zero, so
    Summer takes log(0) and Herdan/Maas divide by zero. Ungarded, that was a
    500 on `/v1/diversity` and `/v1/analyze` for trivially reachable input.
    """
    try:
        return get()
    except (ValueError, ZeroDivisionError):
        return None


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
