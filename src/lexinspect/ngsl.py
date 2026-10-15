"""NGSL + NAWL coverage profiling (Browne, Culligan & Phillips).

- New General Service List 1.2 — 2,809 lemmas, ~92% of general English.
- New Academic Word List 1.2 — 959 academic lemmas, for use after NGSL.

CC BY-SA 4.0. A token is NGSL if any of its forms is an NGSL form (every
inflection and UK/US spelling the official teaching list gives), else NAWL,
else a proper noun (tagged NNP/NNPS and on neither list), else off-list. The
two lists are reported separately as well as combined — they answer different
questions (general vs academic vocabulary).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from lexinspect import _lists
from lexinspect._text import Analysis, ensure, lookup

OFF_LIST_LIMIT = 200


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    ngsl, nawl = _lists.ngsl_forms(), _lists.nawl_forms()

    ngsl_tokens = nawl_tokens = 0
    ngsl_lemmas: set[str] = set()
    nawl_lemmas: set[str] = set()
    proper: Counter[str] = Counter()
    off: Counter[str] = Counter()
    nawl_words: Counter[str] = Counter()

    for lex in a.lexical:
        _k, item = lookup(ngsl, lex.keys)
        if item is not None:
            ngsl_tokens += 1
            ngsl_lemmas.add(item["lemma"])
            continue
        _k, item = lookup(nawl, lex.keys)
        if item is not None:
            nawl_tokens += 1
            nawl_lemmas.add(item["lemma"])
            nawl_words[lex.surface] += 1
            continue
        if lex.is_proper:
            proper[lex.surface] += 1
        else:
            off[lex.surface] += 1

    n = len(a.lexical)
    off_tokens = sum(off.values())
    return {
        "counts": {
            "content_tokens": n,
            "ngsl_tokens": ngsl_tokens,
            "nawl_tokens": nawl_tokens,
            "proper_noun_tokens": sum(proper.values()),
            "off_list_tokens": off_tokens,
            "ngsl_lemmas": len(ngsl_lemmas),
            "nawl_lemmas": len(nawl_lemmas),
        },
        "coverage_pct": {
            "ngsl": _pct(ngsl_tokens, n),
            "nawl": _pct(nawl_tokens, n),
            "ngsl_plus_nawl": _pct(ngsl_tokens + nawl_tokens, n),
            "proper_nouns": _pct(sum(proper.values()), n),
            "off_list": _pct(off_tokens, n),
        },
        "ngsl_lemmas_found": sorted(ngsl_lemmas),
        "nawl_lemmas_found": sorted(nawl_lemmas),
        "nawl_words": [{"word": w, "count": c} for w, c in nawl_words.most_common()],
        "proper_nouns": [{"word": w, "count": c} for w, c in proper.most_common(OFF_LIST_LIMIT)],
        "off_list": [{"word": w, "count": c} for w, c in off.most_common(OFF_LIST_LIMIT)],
        "off_list_sample": sorted(off)[:50],
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
