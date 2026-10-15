"""Run several modules over one shared analysis.

The CLI's `analyze` command and the API's `/v1/analyze` both go through
`run_all`, so the two transports can't drift apart: same parse, same modules,
same numbers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from lexinspect import (
    _lists,
    _syllables,
    awl,
    bnc_coca,
    cefr,
    diversity,
    errors,
    metadiscourse,
    ngsl,
    phrase,
    profile,
    readability,
    statistics,
    tagger,
)
from lexinspect._nlp import get_nlp
from lexinspect._text import Analysis, analyse

# Order is the order results appear in.
MODULES: dict[str, Callable[..., dict[str, Any]]] = {
    "readability": readability.analyze,
    "statistics": statistics.analyze,
    "diversity": diversity.analyze,
    "tagger": tagger.analyze,
    "awl": awl.analyze,
    "bnc_coca": bnc_coca.analyze,
    "ngsl": ngsl.analyze,
    "phrase": phrase.analyze,
    "cefr": cefr.analyze,
    "metadiscourse": metadiscourse.analyze,
    "errors": errors.analyze,
    "profile": profile.analyze,
}


def run_all(
    text: str,
    *,
    modules: Iterable[str] | None = None,
    variant: str = "gb",
    analysis: Analysis | None = None,
) -> tuple[Analysis, dict[str, Any]]:
    a = analysis or analyse(text)
    wanted = list(MODULES) if modules is None else [m for m in MODULES if m in set(modules)]
    results: dict[str, Any] = {}
    for name in wanted:
        if name == "errors":
            results[name] = errors.analyze(a.text, variant=variant, analysis=a)
        else:
            results[name] = MODULES[name](a.text, analysis=a)
    return a, results


def warm() -> None:
    """Load every model, list and dictionary once, single-threaded, at startup."""
    get_nlp()
    _syllables.cmudict()
    _lists.warm()
    phrase._index()
    metadiscourse.warm()
    errors.warm()
    run_all("Warm-up: the quick brown fox doesn't jump over the lazy dog.")
