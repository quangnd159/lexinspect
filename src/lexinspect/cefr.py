"""CEFR vocabulary profiling (A1–C2).

Combines CEFR-J Vocabulary Profile 1.5 (A1–B2; Tono, TUFS) with the Octanove
Vocabulary Profile C1/C2 1.0 (Octanove Labs, CC-BY-SA 4.0). 8,690 lemmas total.

Each token is mapped to the lowest CEFR level at which it's listed (a word that
appears as both an A2 verb and a B1 noun is reported as A2). Lookup tries
surface form first, then spaCy lemma. The off-list residual is named — these
are typically proper nouns, very low-frequency items, or words above C2.

The `dominant_level` field is the level with the most token hits; the
`estimated_level_95th` field is the lowest level at which cumulative coverage
crosses 95% — a heuristic, not a verdict. Text Inspector's proprietary
Scorecard weighting is not reproduced here; agents combine these signals with
readability and band coverage themselves.

This is *not* the Cambridge English Vocabulary Profile. Different corpora,
different methodology — numbers will diverge from EVP-based tools. Cite
CEFR-J + Octanove in any output that uses these results.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._nlp import get_doc


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("cefr.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _lemma_to_level() -> dict[str, str]:
    return {item["lemma"]: item["level"] for item in _load()["lemmas"]}


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)
    lookup = _lemma_to_level()
    levels = _load()["level_order"]

    per_level_tokens: dict[str, int] = {lvl: 0 for lvl in levels}
    per_level_lemmas: dict[str, set[str]] = {lvl: set() for lvl in levels}
    off_list: list[str] = []
    content = 0

    for tok in doc:
        if tok.is_space or tok.is_punct or tok.like_num:
            continue
        content += 1
        surface = tok.text.lower()
        lemma = tok.lemma_.lower()
        level = lookup.get(surface) or lookup.get(lemma)
        if level is None:
            off_list.append(surface)
            continue
        per_level_tokens[level] += 1
        per_level_lemmas[level].add(lemma if lemma in lookup else surface)

    on_list = sum(per_level_tokens.values())
    cumulative = 0
    per_level_out = {}
    estimated = None
    for lvl in levels:
        n = per_level_tokens[lvl]
        cumulative += n
        per_level_out[lvl] = {
            "tokens": n,
            "lemmas": len(per_level_lemmas[lvl]),
            "coverage_pct": _pct(n, content),
            "cumulative_coverage_pct": _pct(cumulative, content),
        }
        if estimated is None and content and (cumulative / content) >= 0.95:
            estimated = lvl

    dominant = max(levels, key=lambda lvl: per_level_tokens[lvl]) if on_list else None

    return {
        "counts": {
            "content_tokens": content,
            "on_list_tokens": on_list,
            "off_list_tokens": len(off_list),
        },
        "coverage_pct": _pct(on_list, content),
        "per_level": per_level_out,
        "dominant_level": dominant,
        "estimated_level_95th": estimated,
        "off_list_sample": sorted(set(off_list))[:50],
        "caveat": (
            "Heuristic only. Based on CEFR-J 1.5 + Octanove C1/C2 1.0; not Cambridge EVP. "
            "Cite both sources. Agents should combine this with readability, BNC/COCA, and "
            "diversity signals before reporting a level."
        ),
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
