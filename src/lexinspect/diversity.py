"""Lexical diversity: TTR family, MSTTR, MATTR, MTLD, HD-D and vocd-D.

Implemented here rather than wrapping `lexicalrichness`, for three reasons:

- **Units.** lexicalrichness tokenised for itself — it replaced apostrophes
  with spaces, so `don't` became two "words", `don` and `t`, and it disagreed
  with every other tab's word count. Here the tokens are lexinspect's words
  (contractions and hyphenated compounds whole), lowercased, numerals excluded.
- **Correctness.** Its MSTTR discarded the final segment unconditionally, so a
  100-word text with 50-word segments threw away a complete segment and
  averaged one. Only a genuinely incomplete trailing segment is dropped here.
- **Weight.** It was the only reason scipy, pandas, matplotlib and textblob
  shipped — ~160 MB of the deployment and most of an 11-second cold start
  (matplotlib rebuilds its font cache on every new instance) — to compute
  formulas that need nothing beyond `math`.

The formulas are checked against lexicalrichness on identical token lists in
`tests/test_diversity.py`, so the numbers carry over wherever the inputs agree.

vocd-D is new. lexinspect used to show Durán et al.'s (2004) vocd-D reference
bands with a note saying it couldn't compute vocd-D; it now does, following
McKee, Malvern & Richards (2000), so the bands can be read against the text.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Any

from lexinspect._text import Analysis, ensure

# Durán, Malvern, Richards & Chipere (2004), Applied Linguistics 25/2: 220–242.
# Only the two ranges stated explicitly in the paper's abstract are bundled.
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
    "Reference ranges are for vocd-D (Durán et al. 2004), which lexinspect computes as "
    "`vocd_d` following McKee, Malvern & Richards (2000). Compare them with vocd-D only — "
    "HD-D (0–1) and MTLD are on different scales."
)

MTLD_THRESHOLD = 0.72  # McCarthy & Jarvis (2010) default
MSTTR_SEGMENT = 50
MATTR_WINDOW = 50
HDD_DRAWS = 42  # McCarthy & Jarvis (2007)
VOCD_MIN_N, VOCD_MAX_N = 35, 50  # McKee, Malvern & Richards (2000)
VOCD_SAMPLES = 100
VOCD_TRIALS = 3
VOCD_SEED = 42

# Below these sizes a measure is not computed. MTLD needs at least one full
# factor to be a measurement rather than its fallback; the windowed measures
# need one full window; vocd-D needs more tokens than its largest sample.
MIN_TOKENS_MTLD = 50
MIN_TOKENS_RELIABLE = 50


def tokens(analysis: Analysis) -> list[str]:
    """The token stream every measure here reads: lowercase word forms, no numerals."""
    return [w.lower for w in analysis.non_numeric_words]


# --- measures (pure functions of a token list) -------------------------------


def ttr(toks: list[str]) -> float:
    """Type–token ratio (Templin 1957)."""
    return len(set(toks)) / len(toks)


def rttr(toks: list[str]) -> float:
    """Root TTR, Guiraud's R (Guiraud 1960)."""
    return len(set(toks)) / math.sqrt(len(toks))


def cttr(toks: list[str]) -> float:
    """Corrected TTR (Carroll 1964)."""
    return len(set(toks)) / math.sqrt(2 * len(toks))


def herdan(toks: list[str]) -> float:
    """Herdan's C = log V / log N (Herdan 1960)."""
    return math.log(len(set(toks))) / math.log(len(toks))


def summer(toks: list[str]) -> float:
    """Somers' S = log log V / log log N (Somers 1966)."""
    return math.log(math.log(len(set(toks)))) / math.log(math.log(len(toks)))


def maas(toks: list[str]) -> float:
    """Maas a² = (log N − log V) / (log N)² (Maas 1972). Lower is more diverse."""
    n = len(toks)
    return (math.log(n) - math.log(len(set(toks)))) / math.log(n) ** 2


def msttr(toks: list[str], segment: int = MSTTR_SEGMENT) -> float:
    """Mean segmental TTR (Johnson 1944): mean TTR of consecutive non-overlapping
    segments; an incomplete final segment is discarded."""
    full = len(toks) // segment
    if full < 1:
        raise ValueError("text shorter than one segment")
    return (
        sum(len(set(toks[i * segment : (i + 1) * segment])) / segment for i in range(full)) / full
    )


def mattr(toks: list[str], window: int = MATTR_WINDOW) -> float:
    """Moving-average TTR (Covington & McFall 2010), computed incrementally."""
    n = len(toks)
    if window > n:
        raise ValueError("text shorter than the window")
    counts = Counter(toks[:window])
    total = len(counts)
    for i in range(window, n):
        out_tok, in_tok = toks[i - window], toks[i]
        counts[out_tok] -= 1
        if counts[out_tok] == 0:
            del counts[out_tok]
        counts[in_tok] += 1
        total += len(counts)
    return total / ((n - window + 1) * window)


def _mtld_pass(toks: list[str], threshold: float) -> float:
    terms: set[str] = set()
    count = 0
    factors = 0.0
    current_ttr = 1.0
    for tok in toks:
        count += 1
        terms.add(tok)
        current_ttr = len(terms) / count
        if current_ttr <= threshold:
            factors += 1
            terms = set()
            count = 0
    if count > 0:
        factors += (1 - current_ttr) / (1 - threshold)
    if factors == 0:
        whole = len(set(toks)) / len(toks)
        factors = 1 if whole == 1 else (1 - whole) / (1 - threshold)
    return len(toks) / factors


def mtld(toks: list[str], threshold: float = MTLD_THRESHOLD) -> float:
    """MTLD (McCarthy & Jarvis 2010): mean of the forward and reverse passes."""
    return (_mtld_pass(toks, threshold) + _mtld_pass(toks[::-1], threshold)) / 2


def hdd(toks: list[str], draws: int = HDD_DRAWS) -> float:
    """HD-D (McCarthy & Jarvis 2007): Σ over types of P(type appears in a random
    draw of `draws` tokens) / draws, with P from the hypergeometric distribution."""
    n = len(toks)
    if n < draws:
        raise ValueError("text shorter than the draw size")
    total = 0.0
    for freq in Counter(toks).values():
        # P(X = 0) = C(n − f, d) / C(n, d) = Π_{i<d} (n − f − i) / (n − i)
        p0 = 1.0
        for i in range(draws):
            num = n - freq - i
            if num <= 0:
                p0 = 0.0
                break
            p0 *= num / (n - i)
        total += (1 - p0) / draws
    return total


def _ttr_model(n: float, d: float) -> float:
    """McKee, Malvern & Richards (2000): expected TTR of an n-token sample."""
    return (d / n) * (math.sqrt(1 + 2 * n / d) - 1)


def _fit_d(points: list[tuple[int, float]]) -> float:
    """Least-squares D for the TTR model, by golden-section search on log D.

    The model is monotone in D and the squared error is unimodal over the
    plausible range, so a bracketed 1-D search is exact enough and needs no
    scipy.
    """

    def sse(log_d: float) -> float:
        d = math.exp(log_d)
        return sum((y - _ttr_model(x, d)) ** 2 for x, y in points)

    lo, hi = math.log(1.0), math.log(10_000.0)
    phi = (math.sqrt(5) - 1) / 2
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = sse(a), sse(b)
    for _ in range(80):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = sse(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = sse(b)
    return math.exp((lo + hi) / 2)


def vocd_d(toks: list[str], seed: int = VOCD_SEED) -> float:
    """vocd-D (McKee, Malvern & Richards 2000).

    For each sample size 35..50, draw 100 random samples without replacement
    and average their TTRs; fit D to that curve; repeat three times and average
    the three Ds. Seeded, so the same text always gets the same D.
    """
    if len(toks) <= VOCD_MAX_N:
        raise ValueError("text not longer than the largest sample")
    rng = random.Random(seed)
    ds: list[float] = []
    for _ in range(VOCD_TRIALS):
        points = []
        for size in range(VOCD_MIN_N, VOCD_MAX_N + 1):
            mean_ttr = sum(len(set(rng.sample(toks, size))) / size for _ in range(VOCD_SAMPLES))
            points.append((size, mean_ttr / VOCD_SAMPLES))
        ds.append(_fit_d(points))
    return sum(ds) / len(ds)


# --- module entry ------------------------------------------------------------


def _safe(fn, toks, *args):
    try:
        return round(float(fn(toks, *args)), 4)
    except (ValueError, ZeroDivisionError):
        return None


def _references_block(vocd: float | None) -> dict[str, Any]:
    bands = []
    for b in VOCD_D_REFERENCE_RANGES:
        band = dict(b)
        if vocd is not None:
            band["position"] = (
                "below" if vocd < b["min"] else "above" if vocd > b["max"] else "within"
            )
        bands.append(band)
    return {"vocd_d_bands": bands, "note": _REFERENCES_NOTE}


# Which indices to trust: TAALED's tiers (github.com/LCR-ADS-Lab/TAALED), whose
# minimum lengths cite Zenker & Kyle (2021, Assessing Writing 47). TAALED doesn't
# rate vocd-D; putting it with HD-D is lexinspect's own call, because TAALED
# describes HD-D (McCarthy & Jarvis 2007, Language Testing 24) as "a more
# reliable calculation of vocd-D".
TIERS: dict[str, Any] = {
    "recommended": ["mtld", "mattr"],
    "caution": ["hdd", "vocd_d", "maas"],
    "legacy": ["ttr", "rttr", "cttr", "msttr", "herdan", "summer"],
    "note": (
        "Tiers follow TAALED's guidance, whose minimum lengths draw on Zenker & Kyle "
        "(2021): MTLD and MATTR with confidence from 50 tokens; HD-D (50 tokens) and "
        "Maas (100) with caution. TTR and its transforms, and MSTTR, change with text "
        "length; compare them only between texts of the same length. TAALED doesn't "
        'rate vocd-D; lexinspect groups it with HD-D, which TAALED calls "a more '
        'reliable calculation of vocd-D" (HD-D: McCarthy & Jarvis 2007).'
    ),
}


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    toks = tokens(ensure(text, analysis))
    n = len(toks)
    if n == 0:
        return {
            "counts": {"tokens": 0, "types": 0},
            "scores": {},
            "references": _references_block(None),
            "tiers": TIERS,
            "note": "Empty or untokenizable text.",
        }

    vocd = _safe(vocd_d, toks) if n > VOCD_MAX_N else None
    out: dict[str, Any] = {
        "counts": {"tokens": n, "types": len(set(toks))},
        "scores": {
            "ttr": _safe(ttr, toks),
            "rttr": _safe(rttr, toks),
            "cttr": _safe(cttr, toks),
            "msttr": _safe(msttr, toks),
            "mattr": _safe(mattr, toks),
            # MTLD never raises — its fallback always yields a number, and on
            # short text that number is nonsense (twelve all-unique words score
            # 12.0, which reads as maximally repetitive). Suppressed explicitly.
            "mtld": _safe(mtld, toks) if n >= MIN_TOKENS_MTLD else None,
            "hdd": _safe(hdd, toks),
            "vocd_d": round(vocd, 2) if vocd is not None else None,
            "herdan": _safe(herdan, toks),
            "summer": _safe(summer, toks),
            "maas": _safe(maas, toks),
        },
        "references": _references_block(vocd),
        "tiers": TIERS,
    }
    if n < MIN_TOKENS_RELIABLE:
        out["note"] = (
            f"Only {n} tokens. Lexical-diversity measures are sample-size dependent; scores "
            f"below ~{MIN_TOKENS_RELIABLE} tokens are unstable and the ones that cannot be "
            "computed at all are reported as null."
        )
    return out
