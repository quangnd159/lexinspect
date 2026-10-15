"""CEFR vocabulary profiling (A1–C2).

Combines CEFR-J Vocabulary Profile 1.5 (A1–B2; Tono, TUFS) with the Octanove
Vocabulary Profile C1/C2 1.0 (Octanove Labs, CC BY-SA 4.0).

Levels are per part of speech, as the sources list them: *present* is A1 as a
noun and B2 as a verb, and the token's spaCy POS picks which applies. When the
source lists no level for the token's POS, the word's lowest level is used and
the token is counted in `pos_fallback_tokens`. (The previous build kept only
the lowest level, so every "to present findings" scored A1.)

Proper nouns — tagged NNP/NNPS and not on the list — are counted separately
rather than as off-list. They aren't vocabulary a learner is expected to know
at a level, and lumping them in with genuinely rare words made the 95th
percentile estimate refuse to answer on most academic texts.

`estimated_level_95th` is the lowest level at which cumulative coverage,
counting proper nouns as known, reaches 95% — a heuristic, not a verdict.
`dominant_level` (argmax of token counts) is almost always A1 because of
function words; read it alongside the distribution, never alone.

This is *not* the Cambridge English Vocabulary Profile; cite CEFR-J and
Octanove in any output that uses these results.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from lexinspect import _lists
from lexinspect._text import Analysis, ensure, lookup

WORDS_PER_LEVEL_LIMIT = 100
OFF_LIST_LIMIT = 200


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    entries = _lists.cefr_entries()
    levels: list[str] = _lists.cefr_raw()["level_order"]

    tokens: Counter[str] = Counter()
    lemmas: dict[str, set[str]] = defaultdict(set)
    words: dict[str, Counter[str]] = defaultdict(Counter)
    proper: Counter[str] = Counter()
    off: Counter[str] = Counter()
    pos_fallback = 0

    for lex in a.lexical:
        key, entry = lookup(entries, lex.keys)
        if entry is None:
            (proper if lex.is_proper else off)[lex.surface] += 1
            continue
        level, matched = _lists.cefr_level(entry, lex.pos)
        if not matched:
            pos_fallback += 1
        tokens[level] += 1
        lemmas[level].add(key)
        words[level][lex.surface] += 1

    n = len(a.lexical)
    n_proper = sum(proper.values())
    on_list = sum(tokens.values())
    per_level: dict[str, Any] = {}
    cumulative = 0
    estimated = None
    for lvl in levels:
        cumulative += tokens[lvl]
        per_level[lvl] = {
            "tokens": tokens[lvl],
            "lemmas": len(lemmas[lvl]),
            "coverage_pct": _pct(tokens[lvl], n),
            "cumulative_coverage_pct": _pct(cumulative, n),
        }
        if estimated is None and n and (cumulative + n_proper) / n >= 0.95:
            estimated = lvl

    return {
        "counts": {
            "content_tokens": n,
            "on_list_tokens": on_list,
            "proper_noun_tokens": n_proper,
            "off_list_tokens": sum(off.values()),
            "pos_fallback_tokens": pos_fallback,
        },
        "coverage_pct": _pct(on_list, n),
        "per_level": per_level,
        "dominant_level": max(levels, key=lambda lv: tokens[lv]) if on_list else None,
        "estimated_level_95th": estimated,
        "highest_level_present": next((lv for lv in reversed(levels) if tokens[lv]), None),
        "words_by_level": {
            lvl: [{"word": w, "count": c} for w, c in words[lvl].most_common(WORDS_PER_LEVEL_LIMIT)]
            for lvl in levels
        },
        "proper_nouns": [{"word": w, "count": c} for w, c in proper.most_common(OFF_LIST_LIMIT)],
        "off_list": [{"word": w, "count": c} for w, c in off.most_common(OFF_LIST_LIMIT)],
        "off_list_sample": sorted(off)[:50],
        "caveat": (
            "Heuristic only. Based on CEFR-J 1.5 + Octanove C1/C2 1.0; not Cambridge EVP. "
            "Cite both sources. Combine this with readability, BNC/COCA and diversity "
            "signals before reporting a level."
        ),
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
