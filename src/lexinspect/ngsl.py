"""NGSL + NAWL coverage profiling.

Browne, Culligan, Phillips:
- New General Service List 1.2 — 2,809 lemmas, ~92% coverage of general English
- New Academic Word List 1.2 — 959 academic lemmas to use after NGSL

CC-BY-SA 4.0. Lookup tries surface form, then spaCy lemma, then NAWL
inflected variants for words like 'analyses' that NGSL doesn't carry but
NAWL does.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._nlp import get_nlp


@lru_cache(maxsize=1)
def _ngsl() -> dict[str, dict]:
    raw = resources.files("lexinspect.data").joinpath("ngsl.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    return {item["lemma"]: item for item in data["lemmas"]}


@lru_cache(maxsize=1)
def _nawl() -> dict[str, dict]:
    raw = resources.files("lexinspect.data").joinpath("nawl.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    out: dict[str, dict] = {}
    for item in data["lemmas"]:
        for form in item["forms"]:
            out[form] = item
    return out


def analyze(text: str) -> dict[str, Any]:
    nlp = get_nlp()
    doc = nlp(text)
    ngsl = _ngsl()
    nawl = _nawl()

    ngsl_tokens = 0
    nawl_tokens = 0
    off_tokens = 0
    ngsl_lemmas: set[str] = set()
    nawl_lemmas: set[str] = set()
    off_sample: list[str] = []
    content = 0

    for tok in doc:
        if tok.is_space or tok.is_punct or tok.like_num:
            continue
        content += 1
        surface = tok.text.lower()
        lemma = tok.lemma_.lower()
        if surface in ngsl or lemma in ngsl:
            ngsl_tokens += 1
            ngsl_lemmas.add(lemma if lemma in ngsl else surface)
            continue
        if surface in nawl or lemma in nawl:
            nawl_tokens += 1
            entry = nawl.get(surface) or nawl.get(lemma)
            nawl_lemmas.add(entry["lemma"] if entry else lemma)
            continue
        off_tokens += 1
        if len(off_sample) < 50:
            off_sample.append(surface)

    return {
        "counts": {
            "content_tokens": content,
            "ngsl_tokens": ngsl_tokens,
            "nawl_tokens": nawl_tokens,
            "off_list_tokens": off_tokens,
            "ngsl_lemmas": len(ngsl_lemmas),
            "nawl_lemmas": len(nawl_lemmas),
        },
        "coverage_pct": {
            "ngsl": _pct(ngsl_tokens, content),
            "nawl": _pct(nawl_tokens, content),
            "ngsl_plus_nawl": _pct(ngsl_tokens + nawl_tokens, content),
            "off_list": _pct(off_tokens, content),
        },
        "ngsl_lemmas_found": sorted(ngsl_lemmas),
        "nawl_lemmas_found": sorted(nawl_lemmas),
        "off_list_sample": sorted(set(off_sample))[:50],
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
