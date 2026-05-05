"""POS tagging via spaCy. Emits Penn Treebank tags + universal POS counts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from lexinspect._nlp import get_nlp


def analyze(text: str, *, include_tokens: bool = False) -> dict[str, Any]:
    nlp = get_nlp()
    doc = nlp(text)

    ptb_counts: Counter[str] = Counter()
    upos_counts: Counter[str] = Counter()
    tokens: list[dict[str, Any]] = []

    total = 0
    for tok in doc:
        if tok.is_space:
            continue
        total += 1
        if tok.is_punct:
            ptb_counts[tok.tag_ or "PUNCT"] += 1
            upos_counts["PUNCT"] += 1
        else:
            ptb_counts[tok.tag_] += 1
            upos_counts[tok.pos_] += 1
        if include_tokens:
            tokens.append(
                {
                    "text": tok.text,
                    "lemma": tok.lemma_,
                    "pos": tok.pos_,
                    "tag": tok.tag_,
                }
            )

    out: dict[str, Any] = {
        "counts": {"total_tokens": total, "sentences": sum(1 for _ in doc.sents)},
        "ptb_distribution": dict(ptb_counts.most_common()),
        "upos_distribution": dict(upos_counts.most_common()),
    }
    if include_tokens:
        out["tokens"] = tokens
    return out
