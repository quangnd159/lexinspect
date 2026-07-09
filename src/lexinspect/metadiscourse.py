"""Metadiscourse marker detection (Hyland 2005, 10-category framework).

Two dimensions, five categories each:
- Interactive (organize the text): transitions, frame markers, endophoric
  markers, evidentials, code glosses.
- Interactional (engage the reader): hedges, boosters, attitude markers,
  engagement markers, self-mentions.

Detection scans token spans of length 1–6 against the lemmatized marker
index. When a span matches multiple categories (e.g. 'in fact' is both a
booster and a code gloss), all matching categories are recorded. Density
is reported per 1,000 content tokens — the standard comparability metric
in the L2 academic writing literature.

Marker lists are curated from canonical Hyland 2005 reproductions; the
hedges category is a verbatim Appendix A mirror. See data/SOURCES.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._nlp import get_doc


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("metadiscourse.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> tuple[dict[tuple[str, ...], list[tuple[str, str]]], int]:
    """Map token-tuple -> [(dimension, category), ...]; also return max span length."""
    data = _load()
    out: dict[tuple[str, ...], list[tuple[str, str]]] = defaultdict(list)
    max_len = 0
    for dimension, cats in data["categories"].items():
        for category, items in cats.items():
            for item in items:
                key = tuple(item.split())
                if not key:
                    continue
                out[key].append((dimension, category))
                max_len = max(max_len, len(key))
    return dict(out), max_len


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)
    index, max_len = _index()

    content = [t for t in doc if not (t.is_space or t.is_punct)]
    surfaces = [t.text.lower() for t in content]

    hits: list[dict[str, Any]] = []
    cat_counts: dict[str, int] = defaultdict(int)
    cat_unique: dict[str, set[str]] = defaultdict(set)
    dim_counts: dict[str, int] = defaultdict(int)

    n = len(content)
    i = 0
    while i < n:
        matched_len = 0
        for span_len in range(min(max_len, n - i), 0, -1):
            window = tuple(surfaces[i : i + span_len])
            entries = index.get(window)
            if entries:
                surface = " ".join(window)
                for dim, cat in entries:
                    hits.append(
                        {
                            "dimension": dim,
                            "category": cat,
                            "marker": surface,
                            "surface": surface,
                            "token_index": content[i].i,
                        }
                    )
                    cat_counts[cat] += 1
                    cat_unique[cat].add(surface)
                    dim_counts[dim] += 1
                matched_len = span_len
                break
        i += matched_len if matched_len else 1

    cats_meta = _load()["categories"]
    per_category: dict[str, dict[str, Any]] = {}
    for dim, cats in cats_meta.items():
        for cat in cats:
            per_category[cat] = {
                "dimension": dim,
                "hits": cat_counts.get(cat, 0),
                "unique_markers": len(cat_unique.get(cat, set())),
                "density_per_1000": _density(cat_counts.get(cat, 0), n),
            }

    per_dimension = {
        dim: {
            "hits": dim_counts.get(dim, 0),
            "density_per_1000": _density(dim_counts.get(dim, 0), n),
        }
        for dim in cats_meta
    }

    return {
        "counts": {
            "content_tokens": n,
            "total_hits": len(hits),
            "interactive_hits": dim_counts.get("interactive", 0),
            "interactional_hits": dim_counts.get("interactional", 0),
        },
        "density_per_1000": _density(len(hits), n),
        "per_dimension": per_dimension,
        "per_category": per_category,
        "hits": hits,
    }


def _density(n: int, total: int) -> float:
    return round(n / total * 1000, 3) if total else 0.0
