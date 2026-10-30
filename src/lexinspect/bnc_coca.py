"""BNC/COCA frequency-band profiling (Nation's 25,000 word families).

Each lexical token is matched to its Bauer–Nation Level 6 word family, and the
family's band (1k … 25k) is the token's band — so `clearly`, `unclear` and
`clearance` all count toward `clear` in the 1k band, as in Range and
AntWordProfiler. Lookup tries the token's own forms, then its lemma, then its
British/American respelling.

Tokens no family claims fall into Nation's supplementary lists — proper names,
marginal words (`oh`, `hmm`), transparent compounds, acronyms — or, failing
those, are proper nouns by tag, or off-list. Nation's convention, followed by
the cumulative curve's `..._with_supplementary` field, is that supplementary
and proper-noun tokens are assumed known: a reader doesn't need to have learnt
`London` to follow a text about it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from lexinspect import _lists
from lexinspect._text import Analysis, ensure, lookup

BANDS = 25
OFF_LIST_LIMIT = 200


def classify(lex) -> tuple[str, Any]:
    """('band', Family) | ('supplementary', list_name) | ('proper', None) | ('off', None)."""
    _key, fam = lookup(_lists.bnc_forms(), lex.keys)
    if fam is not None:
        return "band", fam
    _key, sup = lookup(_lists.bnc_supplementary(), lex.keys)
    if sup == "proper_names" or (sup is None and lex.is_proper):
        return "proper", None
    if sup is not None:
        return "supplementary", sup
    return "off", None


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    lexical = a.lexical
    n = len(lexical)

    band_tokens: Counter[int] = Counter()
    band_families: dict[int, set[str]] = defaultdict(set)
    supplementary: Counter[str] = Counter()
    proper: Counter[str] = Counter()
    off: Counter[str] = Counter()

    for lex in lexical:
        kind, value = classify(lex)
        if kind == "band":
            band_tokens[value.band] += 1
            band_families[value.band].add(value.headword)
        elif kind == "supplementary":
            supplementary[value] += 1
        elif kind == "proper":
            proper[lex.surface] += 1
        else:
            off[lex.surface] += 1

    on_list = sum(band_tokens.values())
    assumed_known = sum(supplementary.values()) + sum(proper.values())
    per_band = {
        b: {"tokens": row.pop("tokens"), "headwords": len(band_families[int(b)]), **row}
        for b, row in coverage_by_band(band_tokens, n, assumed_known).items()
    }

    return {
        "counts": {
            "content_tokens": n,
            "on_list_tokens": on_list,
            "proper_noun_tokens": sum(proper.values()),
            "supplementary_tokens": sum(supplementary.values()),
            "off_list_tokens": sum(off.values()),
        },
        "coverage_pct": pct(on_list, n),
        "coverage_with_supplementary_pct": pct(on_list + assumed_known, n),
        "per_band": per_band,
        "supplementary": dict(supplementary),
        "proper_nouns": [{"word": w, "count": c} for w, c in proper.most_common(OFF_LIST_LIMIT)],
        "off_list": [{"word": w, "count": c} for w, c in off.most_common(OFF_LIST_LIMIT)],
        "off_list_sample": sorted(off)[:50],
    }


def coverage_by_band(band_tokens: Counter[int], n: int, assumed_known: int) -> dict[str, dict]:
    """Per band 1-25: its tokens, its coverage of `n` tokens, and the
    cumulative coverage up to it, with and without the `assumed_known` tokens
    (supplementary lists and proper nouns). `phrase` builds its integrated
    profile with this too, so the two profiles can't be computed differently."""
    per_band = {}
    cumulative = 0
    for b in range(1, BANDS + 1):
        cumulative += band_tokens[b]
        per_band[str(b)] = {
            "tokens": band_tokens[b],
            "coverage_pct": pct(band_tokens[b], n),
            "cumulative_coverage_pct": pct(cumulative, n),
            "cumulative_coverage_with_supplementary_pct": pct(cumulative + assumed_known, n),
        }
    return per_band


def pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
