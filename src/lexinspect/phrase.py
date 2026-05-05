"""PHRASE list detection (Martinez & Schmitt 2012).

506 phrasal expressions across K1–K5 frequency bands. Each item is a base form
(`HAVE TO`, `IN SPITE OF`, `ON THE OTHER HAND`). Detection scans token spans
of length 1–6 against the lemmatized phrase index, allowing common verb
inflections via spaCy lemmas. Slot phrases like `BE EXPECTED TO` accept any
'be' inflection in the matching slot.

Output: ranked hit list with band, frequency, and the surface span found.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._nlp import get_nlp


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("phrase.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, ...], dict[str, Any]]:
    """Map lemmatized phrase tuple -> phrase entry."""
    out: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in _load()["items"]:
        key = _phrase_key(item["phrase"])
        if key:
            out[key] = item
    return out


_NOTE_RE = re.compile(r"\([^)]*\)")
_SPACE_RE = re.compile(r"\s+")


def _phrase_key(phrase: str) -> tuple[str, ...]:
    """Normalize a base phrase into a tuple of lemma-form tokens.
    `HAVE TO` -> ('have', 'to'); `BE EXPECTED TO` -> ('be', 'expected', 'to').
    Drops parenthetical glosses and slash alternants (keeps the first variant)."""
    p = _NOTE_RE.sub(" ", phrase).lower()
    p = p.replace("/", " ")
    p = _SPACE_RE.sub(" ", p).strip()
    return tuple(p.split())


_BE_FORMS = {"be", "is", "am", "are", "was", "were", "been", "being"}
_HAVE_FORMS = {"have", "has", "had", "having"}
_DO_FORMS = {"do", "does", "did", "doing", "done"}


def _token_matches(token_lemma: str, token_text: str, target: str) -> bool:
    target = target.lower()
    if target == "be":
        return token_text in _BE_FORMS or token_lemma == "be"
    if target == "have":
        return token_text in _HAVE_FORMS or token_lemma == "have"
    if target == "do":
        return token_text in _DO_FORMS or token_lemma == "do"
    return token_text == target or token_lemma == target


def analyze(text: str) -> dict[str, Any]:
    nlp = get_nlp()
    doc = nlp(text)
    index = _index()

    content_tokens = [
        (t.text.lower(), t.lemma_.lower(), t.i)
        for t in doc
        if not (t.is_space or t.is_punct)
    ]

    max_len = max((len(k) for k in index), default=0)
    hits: list[dict[str, Any]] = []
    matched_ranks: dict[int, int] = {}

    n = len(content_tokens)
    for i in range(n):
        for span_len in range(1, min(max_len, n - i) + 1):
            window = content_tokens[i : i + span_len]
            for key, item in index.items():
                if len(key) != span_len:
                    continue
                if all(_token_matches(w[1], w[0], k) for w, k in zip(window, key)):
                    surface = " ".join(w[0] for w in window)
                    hits.append(
                        {
                            "rank": item["rank"],
                            "phrase": item["phrase"],
                            "k_band": item["k_band"],
                            "surface": surface,
                        }
                    )
                    matched_ranks[item["rank"]] = matched_ranks.get(item["rank"], 0) + 1
                    break

    per_band: dict[str, int] = {str(k): 0 for k in range(1, 6)}
    for h in hits:
        per_band[str(h["k_band"])] += 1

    return {
        "counts": {
            "total_hits": len(hits),
            "unique_phrases": len(matched_ranks),
            "content_tokens": len(content_tokens),
        },
        "hits_per_k_band": per_band,
        "hits": sorted(hits, key=lambda h: h["rank"]),
    }
