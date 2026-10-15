"""Academic Word List (Coxhead 2000) coverage profiling.

Each lexical token is matched against Coxhead's 570 word families (3,111 forms,
British and American spellings both listed) by its forms, lemma, or spelling
variant. Reports per-sublist token and family coverage and the families found.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from lexinspect import _lists
from lexinspect._text import Analysis, ensure, lookup


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    forms = _lists.awl_forms()
    n = len(a.lexical)

    awl_tokens = 0
    families: dict[str, dict[str, Any]] = {}
    family_tokens: Counter[str] = Counter()
    sub_tokens: Counter[int] = Counter()
    sub_families: dict[int, set[str]] = defaultdict(set)
    family_spans: dict[str, list[list[int]]] = defaultdict(list)

    for lex in a.lexical:
        _k, fam = lookup(forms, lex.keys)
        if fam is None:
            continue
        awl_tokens += 1
        head, sub = fam["headword"], fam["sublist"]
        families[head] = fam
        family_tokens[head] += 1
        sub_tokens[sub] += 1
        sub_families[sub].add(head)
        tok = a.doc[lex.i]
        family_spans[head].append([tok.idx, tok.idx + len(tok.text)])

    return {
        "counts": {"content_tokens": n, "awl_tokens": awl_tokens, "awl_families": len(families)},
        "coverage_pct": _pct(awl_tokens, n),
        "per_sublist": {
            str(s): {
                "tokens": sub_tokens[s],
                "families": len(sub_families[s]),
                "coverage_pct": _pct(sub_tokens[s], n),
            }
            for s in range(1, 11)
        },
        "families_found": sorted(families),
        "families_detail": [
            {
                "headword": h,
                "sublist": families[h]["sublist"],
                "tokens": c,
                "spans": family_spans[h],
            }
            for h, c in sorted(
                family_tokens.items(), key=lambda kv: (families[kv[0]]["sublist"], -kv[1], kv[0])
            )
        ],
    }


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 3) if total else 0.0
