"""BNC/COCA frequency-band profiling.

Bundled headword list is the lpmi-13 CC0 mirror of Paul Nation's BNC/COCA bands
1k–10k (9,998 head words across 10 bands of 1,000). Headwords only — derivational
family members are not in the data. Lookup tries surface form first, falls back
to spaCy lemma. Tokens that match no band are reported under `off_list`.

Output mirrors Text Inspector's "K-band coverage" view: per-band token counts
plus the cumulative coverage curve (% of running tokens covered at and below
each band), which is the standard ELT/IELTS readout.
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
    raw = resources.files("lexinspect.data").joinpath("bnc_coca.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _word_to_band() -> dict[str, int]:
    data = _load()
    out: dict[str, int] = {}
    for band_str, words in data["bands"].items():
        band = int(band_str)
        for w in words:
            out.setdefault(w, band)
    return out


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)
    word_to_band = _word_to_band()
    max_band = max(int(k) for k in _load()["bands"])

    tokens_per_band: dict[int, int] = defaultdict(int)
    families_per_band: dict[int, set[str]] = defaultdict(set)
    off_list: list[str] = []
    content_tokens = 0

    for tok in doc:
        if tok.is_space or tok.is_punct or tok.like_num:
            continue
        content_tokens += 1
        surface = tok.text.lower()
        lemma = tok.lemma_.lower()
        band = word_to_band.get(surface) or word_to_band.get(lemma)
        head = surface if surface in word_to_band else (lemma if lemma in word_to_band else None)
        if band is None:
            off_list.append(surface)
            continue
        tokens_per_band[band] += 1
        families_per_band[band].add(head or surface)

    on_list_tokens = sum(tokens_per_band.values())

    per_band = {}
    cumulative = 0
    for b in range(1, max_band + 1):
        n = tokens_per_band.get(b, 0)
        cumulative += n
        per_band[str(b)] = {
            "tokens": n,
            "headwords": len(families_per_band.get(b, set())),
            "coverage_pct": _pct(n, content_tokens),
            "cumulative_coverage_pct": _pct(cumulative, content_tokens),
        }

    return {
        "counts": {
            "content_tokens": content_tokens,
            "on_list_tokens": on_list_tokens,
            "off_list_tokens": len(off_list),
        },
        "coverage_pct": _pct(on_list_tokens, content_tokens),
        "per_band": per_band,
        "off_list_sample": sorted(set(off_list))[:50],
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
