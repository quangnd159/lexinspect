"""PHRASE list detection (Martinez & Schmitt 2012).

506 phrasal expressions across K1–K5 frequency bands. Each entry's printed base
form is compiled at build time (scripts/build_data/build_phrase_index.py) into
its real variants — `THERE IS/ARE` into `there is` and `there are`,
`A BIT (OF)` into `a bit of` and `a bit` — with sense glosses set aside and
`ONE'S`/`ONESELF` as possessive/reflexive slots.

Matching, per sentence, never across punctuation:

- **Inflection.** A word in the phrase matches its own form or any form with
  the same lemma, so DEAL WITH matches `dealt with` and HAVE TO matches `had to`.
  Contractions read as their full forms (`there's` = `there is`).
- **Senses.** Where an entry's example sentence shows its `to` as infinitival
  (TO) or prepositional (IN), or its `that` as complementiser or determiner,
  the text must agree. That's what keeps "going to the park" from counting as
  GOING TO (FUTURE), and picks USED TO (PAST) for "used to snow" but USED TO
  (ACCUSTOMED) for "used to the noise".
- **Overlap.** Longest match wins and consumes its tokens: `as well as` is one
  hit, not also `as well`. (The old matcher counted both.)

When two senses of one form both fit (`out of`: 'IN/FROM', 'USING', 'DUE TO'),
the hit takes the more frequent sense and lists the others in `also_possible`.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._text import Analysis, ensure

POSS, REFL = "<poss>", "<refl>"
_POSSESSIVES = frozenset({"my", "your", "his", "her", "its", "our", "their", "one's"})
_REFLEXIVES = frozenset(
    {
        "myself",
        "yourself",
        "himself",
        "herself",
        "itself",
        "ourselves",
        "yourselves",
        "themselves",
        "oneself",
    }
)
_CLITIC_FULL = {
    "n't": "not",
    "'re": "are",
    "'m": "am",
    "'ve": "have",
    "'ll": "will",
    "ca": "can",
    "wo": "will",
    "sha": "shall",
}


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("phrase.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> dict[str, list[tuple[tuple[str, ...], dict[str, Any]]]]:
    """First phrase word -> [(variant, item)], longest variants first, then by rank."""
    out: dict[str, list[tuple[tuple[str, ...], dict[str, Any]]]] = {}
    for item in _load()["items"]:
        for var in item["variants"]:
            out.setdefault(var[0], []).append((tuple(var), item))
    for cands in out.values():
        cands.sort(key=lambda c: (-len(c[0]), c[1]["rank"]))
    return out


def _norm(tok) -> str:
    text = tok.lower_.replace("’", "'")
    if text == "'s":
        lemma = tok.lemma_.lower()
        if lemma in ("be", "have"):
            return "is" if lemma == "be" else "has"
        # spaCy lemmatises a curly `’s` to `’`, so fall back on the tag: a verb
        # `'s` before a past participle is `has` (`it's been`), otherwise `is`.
        if tok.tag_ == "VBZ":
            nxt = tok.nbor(1) if tok.i + 1 < len(tok.doc) else None
            return "has" if nxt is not None and nxt.tag_ == "VBN" else "is"
        return "'s"
    if text == "'d":
        return "would" if tok.tag_ == "MD" else "had"
    return _CLITIC_FULL.get(text, text)


def _first_keys(norm: str, lemma: str) -> tuple[str, ...]:
    keys = [norm, lemma]
    if norm in _POSSESSIVES:
        keys.append(POSS)
    if norm in _REFLEXIVES:
        keys.append(REFL)
    return tuple(dict.fromkeys(keys))


def _matches(tok, norm: str, target: str) -> bool:
    if target == POSS:
        return norm in _POSSESSIVES
    if target == REFL:
        return norm in _REFLEXIVES
    return norm == target or tok.lemma_.lower() == target


# Tags that play the same role for sense purposes: an adverbial particle is
# tagged RP or RB depending on the parse, and both mean "not a preposition".
_TAG_CLASS = {"RP": "particle", "RB": "particle", "RBR": "particle", "WDT": "DT"}


def _tag_class(tag: str) -> str:
    return _TAG_CLASS.get(tag, tag)


def _clause_final(tok) -> bool:
    """Nothing but punctuation (or the end of the text) follows `tok`."""
    nxt = tok.nbor(1) if tok.i + 1 < len(tok.doc) else None
    return nxt is None or nxt.is_punct or nxt.is_space


# Senses the tagger can't separate. TO GO ('REMAINING') — "two more to go" —
# is tagged exactly like the infinitive in "trains to go to work"; the
# remaining sense ends its clause.
_CONTEXT = {5463: lambda span: _clause_final(span[-1])}


def _segments(doc):
    """Runs of word tokens within a sentence, broken at punctuation."""
    for sent in doc.sents:
        run = []
        for tok in sent:
            if tok.is_space:
                continue
            if tok.is_punct and tok.text not in ("'", "’"):
                if run:
                    yield run
                run = []
                continue
            run.append(tok)
        if run:
            yield run


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    index = _index()

    hits: list[dict[str, Any]] = []
    for run in _segments(a.doc):
        norms = [_norm(t) for t in run]
        i, n = 0, len(run)
        while i < n:
            found: list[tuple[tuple[str, ...], dict[str, Any]]] = []
            for key in _first_keys(norms[i], run[i].lemma_.lower()):
                for var, item in index.get(key, ()):
                    if i + len(var) > n or (found and len(var) < len(found[0][0])):
                        continue
                    if not all(_matches(run[i + k], norms[i + k], w) for k, w in enumerate(var)):
                        continue
                    tags = item.get("tags") or {}
                    if any(
                        _tag_class(run[i + k].tag_) != _tag_class(tags[w])
                        for k, w in enumerate(var)
                        if w in tags
                    ):
                        continue
                    check = _CONTEXT.get(item["rank"])
                    if check is not None and not check(run[i : i + len(var)]):
                        continue
                    if found and len(var) > len(found[0][0]):
                        found = []
                    found.append((var, item))
            if not found:
                i += 1
                continue
            found.sort(key=lambda f: f[1]["rank"])
            var, item = found[0]
            span = run[i : i + len(var)]
            hit = {
                "rank": item["rank"],
                "phrase": item["phrase"],
                "k_band": item["k_band"],
                "surface": a.text[span[0].idx : span[-1].idx + len(span[-1].text)],
                "sense": item.get("sense"),
                "token_index": span[0].i,
                "span": [span[0].idx, span[-1].idx + len(span[-1].text)],
            }
            others = [f[1]["phrase"] for f in found[1:] if f[1]["rank"] != item["rank"]]
            if others:
                hit["also_possible"] = others
            hits.append(hit)
            i += len(var)

    per_band = {str(k): 0 for k in range(1, 6)}
    for h in hits:
        per_band[str(h["k_band"])] += 1
    return {
        "counts": {
            "total_hits": len(hits),
            "unique_phrases": len({h["rank"] for h in hits}),
            "content_tokens": len(a.lexical),
            "hits_per_1000_words": round(len(hits) / a.word_count * 1000, 2)
            if a.word_count
            else 0.0,
        },
        "hits_per_k_band": per_band,
        "hits": sorted(hits, key=lambda h: (h["rank"], h["token_index"])),
        "phrase_frequency": dict(Counter(h["phrase"] for h in hits).most_common()),
    }
