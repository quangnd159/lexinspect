"""Schema version + envelope helpers.

The JSON shape every command emits is the contract downstream agents and
Skills depend on. Bump SCHEMA_VERSION on any change that isn't purely additive.

v2 (lexinspect 0.2): every module counts from one shared tokenisation, so word,
sentence and token counts changed meaning (contractions and hyphenated
compounds are one word; clitics and possessives are not tokens); readability is
computed by lexinspect rather than textstat and `text_standard` is now the
median grade; BNC/COCA uses Nation's full word families (25 bands);
metadiscourse assigns each hit to one category after a context check;
`input.word_count` added to envelopes.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "2"


def envelope(
    module: str,
    source: str,
    char_count: int,
    result: dict[str, Any],
    *,
    words: int | None = None,
) -> dict[str, Any]:
    inp: dict[str, Any] = {"source": source, "char_count": char_count}
    if words is not None:
        inp["word_count"] = words
    return {"schema_version": SCHEMA_VERSION, "module": module, "input": inp, "result": result}
