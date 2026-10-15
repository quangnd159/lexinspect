"""POS tagging via spaCy: Penn Treebank and Universal POS distributions.

Tag distributions are over spaCy tokens (that is what a tagger tags: `don't`
is `do`/VBP + `n't`/RB). The `summary` block — Text Inspector's Tagger Summary
— counts *words* from the shared `Analysis`, so its content-word and sentence
counts agree with every other tab: content words exclude punctuation, numerals
and symbols; verbal elements are PTB `VB*` and `MD` (modals are verbs on
every grammar's account; the old count left `can`/`will`/`must` out), nominal
elements are PTB `NN*`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from lexinspect._text import Analysis, ensure

_NON_CONTENT_UPOS = frozenset({"PUNCT", "NUM", "SYM", "X", "SPACE"})


def analyze(
    text: str, *, include_tokens: bool = False, analysis: Analysis | None = None
) -> dict[str, Any]:
    a = ensure(text, analysis)

    ptb: Counter[str] = Counter()
    upos: Counter[str] = Counter()
    tokens: list[dict[str, Any]] = []
    total = 0
    verbal = nominal = 0
    for tok in a.doc:
        if tok.is_space:
            continue
        total += 1
        tag = tok.tag_ or ("PUNCT" if tok.is_punct else "X")
        pos = "PUNCT" if tok.is_punct else tok.pos_
        ptb[tag] += 1
        upos[pos] += 1
        if tag.startswith("VB") or tag == "MD":
            verbal += 1
        elif tag.startswith("NN"):
            nominal += 1
        if include_tokens:
            tokens.append({"text": tok.text, "lemma": tok.lemma_, "pos": pos, "tag": tag})

    content_words = [
        w for w in a.non_numeric_words if any(t.pos_ not in _NON_CONTENT_UPOS for t in w.tokens)
    ]
    n_content = len(content_words)
    n_types = len({w.lower for w in content_words})
    n_sent = a.sentence_count

    out: dict[str, Any] = {
        "counts": {"total_tokens": total, "sentences": n_sent},
        "summary": {
            "content_tokens": n_content,
            "types": n_types,
            "type_token_ratio": _ratio(n_types, n_content),
            "tokens_per_type": _ratio(n_content, n_types),
            "total_verbal_elements": verbal,
            "verbal_elements_per_sentence": _ratio(verbal, n_sent),
            "total_noun_elements": nominal,
            "noun_elements_per_sentence": _ratio(nominal, n_sent),
        },
        "ptb_distribution": dict(ptb.most_common()),
        "upos_distribution": dict(upos.most_common()),
    }
    if include_tokens:
        out["tokens"] = tokens
    return out


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0
