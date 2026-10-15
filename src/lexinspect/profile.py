"""Per-word vocabulary profile with character spans.

The list modules (cefr, bnc_coca, awl, ngsl) report totals; this one reports
where each lexical token sits in the text and what every list says about it, so
a reader can see *which* words make a text hard, not just how many there are.
It is what the web UI's in-text highlighting reads.

Output is a compact column table, because a 50 KB text has ~8,000 tokens and an
array of objects would repeat every key 8,000 times:

    {"columns": ["start", "end", "cefr", "bnc", "awl", "ngsl"],
     "rows": [[0, 3, "A1", 1, null, "ngsl"], ...]}

- `cefr`: "A1".."C2", "proper" or null (not on the list).
- `bnc`: band 1..25, "proper", "supplementary" or null (off-list).
- `awl`: sublist 1..10 or null.
- `ngsl`: "ngsl", "nawl", "proper" or null.

Every lookup is the same one the list modules make, so a word coloured B2 here
is the word counted under B2 on the CEFR tab.
"""

from __future__ import annotations

from typing import Any

from lexinspect import _lists, bnc_coca
from lexinspect._text import Analysis, ensure, lookup

COLUMNS = ["start", "end", "cefr", "bnc", "awl", "ngsl"]


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    cefr_entries = _lists.cefr_entries()
    awl_forms = _lists.awl_forms()
    ngsl_forms, nawl_forms = _lists.ngsl_forms(), _lists.nawl_forms()

    rows: list[list[Any]] = []
    for lex in a.lexical:
        tok = a.doc[lex.i]
        start, end = tok.idx, tok.idx + len(tok.text)

        _k, entry = lookup(cefr_entries, lex.keys)
        if entry is not None:
            cefr: Any = _lists.cefr_level(entry, lex.pos)[0]
        else:
            cefr = "proper" if lex.is_proper else None

        kind, value = bnc_coca.classify(lex)
        bnc: Any = (
            value.band
            if kind == "band"
            else (kind if kind in ("proper", "supplementary") else None)
        )

        _k, fam = lookup(awl_forms, lex.keys)
        awl = fam["sublist"] if fam is not None else None

        if lookup(ngsl_forms, lex.keys)[1] is not None:
            ngsl: Any = "ngsl"
        elif lookup(nawl_forms, lex.keys)[1] is not None:
            ngsl = "nawl"
        else:
            ngsl = "proper" if lex.is_proper else None

        rows.append([start, end, cefr, bnc, awl, ngsl])
    return {"columns": COLUMNS, "rows": rows}
