"""POS tagging via spaCy. Emits Penn Treebank tags + universal POS counts.

The `summary` block surfaces aggregate views Text Inspector shows on its
Tagger Summary tab — content tokens (excluding punctuation, numerals, and
symbols), unique types, type/token ratio, plus per-sentence rates of verbal
elements (PTB ``VB*``) and nominal elements (PTB ``NN*``). Useful for spotting
verb-light or noun-heavy prose at a glance.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from lexinspect._nlp import get_nlp

# Universal POS tags that are not "content" for the type/token rollup.
_NON_CONTENT_UPOS = frozenset({"PUNCT", "NUM", "SYM", "X"})


def analyze(text: str, *, include_tokens: bool = False) -> dict[str, Any]:
    nlp = get_nlp()
    doc = nlp(text)

    ptb_counts: Counter[str] = Counter()
    upos_counts: Counter[str] = Counter()
    types: set[str] = set()
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
            if tok.pos_ not in _NON_CONTENT_UPOS:
                types.add(tok.text.lower())
        if include_tokens:
            tokens.append(
                {
                    "text": tok.text,
                    "lemma": tok.lemma_,
                    "pos": tok.pos_,
                    "tag": tok.tag_,
                }
            )

    sentence_count = sum(1 for _ in doc.sents)
    content_tokens = total - sum(upos_counts.get(p, 0) for p in _NON_CONTENT_UPOS)
    verbal = sum(c for tag, c in ptb_counts.items() if tag.startswith("VB"))
    nominal = sum(c for tag, c in ptb_counts.items() if tag.startswith("NN"))

    out: dict[str, Any] = {
        "counts": {"total_tokens": total, "sentences": sentence_count},
        "summary": {
            "content_tokens": content_tokens,
            "types": len(types),
            "type_token_ratio": _ratio(len(types), content_tokens),
            "tokens_per_type": _ratio(content_tokens, len(types)),
            "total_verbal_elements": verbal,
            "verbal_elements_per_sentence": _ratio(verbal, sentence_count),
            "total_noun_elements": nominal,
            "noun_elements_per_sentence": _ratio(nominal, sentence_count),
        },
        "ptb_distribution": dict(ptb_counts.most_common()),
        "upos_distribution": dict(upos_counts.most_common()),
    }
    if include_tokens:
        out["tokens"] = tokens
    return out


def _ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 3)
