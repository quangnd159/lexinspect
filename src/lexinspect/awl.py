"""Academic Word List (Coxhead 2000) coverage profiling.

For each token in the text, look up the lowercase surface form against
Coxhead's 570 head-word families (3111 inflected forms). Reports per-sublist
type and token coverage plus the unique families found.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._nlp import get_doc


@lru_cache(maxsize=1)
def _load_data() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("awl.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _form_to_family() -> dict[str, dict[str, Any]]:
    data = _load_data()
    out: dict[str, dict[str, Any]] = {}
    for fam in data["families"]:
        for form in fam["forms"]:
            out[form] = fam
    return out


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)
    forms = _form_to_family()

    content_tokens = 0
    awl_tokens = 0
    families_seen: dict[str, dict[str, Any]] = {}
    sublist_tokens: dict[int, int] = defaultdict(int)
    sublist_families: dict[int, set[str]] = defaultdict(set)

    for tok in doc:
        if tok.is_space or tok.is_punct or tok.like_num:
            continue
        content_tokens += 1
        surface = tok.text.lower()
        fam = forms.get(surface) or forms.get(tok.lemma_.lower())
        if not fam:
            continue
        awl_tokens += 1
        head = fam["headword"]
        sub = fam["sublist"]
        families_seen[head] = fam
        sublist_tokens[sub] += 1
        sublist_families[sub].add(head)

    coverage = (awl_tokens / content_tokens * 100) if content_tokens else 0.0

    per_sublist = {
        str(sub): {
            "tokens": sublist_tokens.get(sub, 0),
            "families": len(sublist_families.get(sub, set())),
            "coverage_pct": round(
                (sublist_tokens.get(sub, 0) / content_tokens * 100) if content_tokens else 0.0,
                3,
            ),
        }
        for sub in range(1, 11)
    }

    return {
        "counts": {
            "content_tokens": content_tokens,
            "awl_tokens": awl_tokens,
            "awl_families": len(families_seen),
        },
        "coverage_pct": round(coverage, 3),
        "per_sublist": per_sublist,
        "families_found": sorted(families_seen.keys()),
    }
