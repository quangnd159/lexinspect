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

from lexinspect._nlp import get_doc


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


@lru_cache(maxsize=1)
def _buckets() -> dict[tuple[int, str], list[tuple[int, tuple[str, ...], dict[str, Any]]]]:
    """Group the phrase index by (span length, first target token).

    Matching used to rescan all ~500 phrases for every token/span-length pair,
    which is linear in the text but with a ~3000x constant — enough to turn a
    large request into minutes of CPU. A window can only match a phrase whose
    first target the window's first token satisfies, so bucketing on that pair
    cuts the candidate set to a handful. The stored position preserves the old
    insertion-order tie-break between equal-length phrases.
    """
    out: dict[tuple[int, str], list[tuple[int, tuple[str, ...], dict[str, Any]]]] = {}
    for pos, (key, item) in enumerate(_index().items()):
        out.setdefault((len(key), key[0]), []).append((pos, key, item))
    return out


def _candidate_targets(token_text: str, token_lemma: str) -> set[str]:
    """Every phrase-initial target this token could satisfy under `_token_matches`."""
    targets = {token_text, token_lemma}
    if token_text in _BE_FORMS or token_lemma == "be":
        targets.add("be")
    if token_text in _HAVE_FORMS or token_lemma == "have":
        targets.add("have")
    if token_text in _DO_FORMS or token_lemma == "do":
        targets.add("do")
    return targets


def _token_matches(token_lemma: str, token_text: str, target: str) -> bool:
    target = target.lower()
    if target == "be":
        return token_text in _BE_FORMS or token_lemma == "be"
    if target == "have":
        return token_text in _HAVE_FORMS or token_lemma == "have"
    if target == "do":
        return token_text in _DO_FORMS or token_lemma == "do"
    return token_text == target or token_lemma == target


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)
    index = _index()

    content_tokens = [
        (t.text.lower(), t.lemma_.lower(), t.i)
        for t in doc
        if not (t.is_space or t.is_punct)
    ]

    max_len = max((len(k) for k in index), default=0)
    hits: list[dict[str, Any]] = []
    matched_ranks: dict[int, int] = {}

    buckets = _buckets()
    n = len(content_tokens)
    for i in range(n):
        targets = _candidate_targets(content_tokens[i][0], content_tokens[i][1])
        for span_len in range(1, min(max_len, n - i) + 1):
            candidates = [c for t in targets for c in buckets.get((span_len, t), ())]
            if not candidates:
                continue
            candidates.sort(key=lambda c: c[0])
            window = content_tokens[i : i + span_len]
            for _pos, key, item in candidates:
                if all(_token_matches(w[1], w[0], k) for w, k in zip(window, key, strict=True)):
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
