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
    alternatives,
    awl,
    bnc_coca,
    cefr,
    diversity,
    errors,
    level,
    metadiscourse,
    ngsl,
    phrase,
    profile,
    readability,
    statistics,
    syntax,
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
    "syntax": syntax.analyze,
    "awl": awl.analyze,
    "bnc_coca": bnc_coca.analyze,
    "ngsl": ngsl.analyze,
    "phrase": phrase.analyze,
    "cefr": cefr.analyze,
    "metadiscourse": metadiscourse.analyze,
    "errors": errors.analyze,
    "alternatives": alternatives.analyze,
    "profile": profile.analyze,
}

# Derived from other modules' results rather than from the text; each runs
# after everything it reads, whenever all of it was computed.
DERIVED: dict[str, tuple[Callable[[dict[str, Any]], dict[str, Any]], tuple[str, ...]]] = {
    "level": (level.estimate, level.REQUIRED_MODULES),
}

ALL_MODULES: list[str] = [*MODULES, *DERIVED]


def run_all(
    text: str,
    *,
    modules: Iterable[str] | None = None,
    variant: str = "gb",
    analysis: Analysis | None = None,
) -> tuple[Analysis, dict[str, Any]]:
    a = analysis or analyse(text)
    asked = None if modules is None else set(modules)
    wanted = list(MODULES) if asked is None else [m for m in MODULES if m in asked]
    # A derived module brings in the modules it reads.
    for name, (_fn, needs) in DERIVED.items():
        if asked is not None and name in asked:
            wanted = [m for m in MODULES if m in set(wanted) | set(needs)]
    results: dict[str, Any] = {}
    for name in wanted:
        if name == "errors":
            results[name] = errors.analyze(a.text, variant=variant, analysis=a)
        elif name == "alternatives":
            # Words the spell checker rejects get no suggestions.
            results[name] = alternatives.analyze(
                a.text, analysis=a, variant=variant, errors_result=results.get("errors")
            )
        else:
            results[name] = MODULES[name](a.text, analysis=a)
    for name, (fn, needs) in DERIVED.items():
        if (asked is None or name in asked) and all(n in results for n in needs):
            results[name] = fn(results)
    if asked is not None:
        results = {k: v for k, v in results.items() if k in asked}
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
