"""Switches for the 0.4.0 matcher-fix families (Study 4 development only).

The 0.4.0 metadiscourse and PHRASE context rules are grouped into twelve fix
families (docs/validation/study4-fix-protocol.md; the family ledger is kept
with the Study 4 fix work). The fix-check measures each family alone against
the 0.3.3 baseline, so every new rule asks `enabled(<its family>)` before it
acts, and with no family enabled the matchers behave exactly as 0.3.3 did.

All twelve are on by default; that is the shipped behaviour. This is not part
of the public API: it exists so the validation harness can run

    with only(["MD-A"]):        # 0.3.3 plus one family
        ...
    with only([]):              # 0.3.3
        ...

The setting lives in a ContextVar. Overrides are local to the current
context, inherited by child contexts according to Python's ContextVar
semantics (an asyncio task created inside `only(...)`, a copied context,
`asyncio.to_thread`), and restored on exit, also when the block raises.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

FAMILIES: tuple[str, ...] = (
    "MD-A",  # clause linking and transitions
    "MD-B",  # word-internal hyphens and brackets
    "MD-C",  # frame and endophoric markers
    "MD-D",  # code glosses
    "MD-E",  # sources and evidentials
    "MD-F",  # stance: hedges, boosters, attitude
    "MD-G",  # reader/writer forms and directives
    "MD-H",  # quotation (the writer's own voice)
    "MD-I",  # exclusive we
    "PH-A",  # USED TO and THAT IS
    "PH-B",  # entry-specific constructions
    "PH-C",  # matching form
)

_ENABLED: ContextVar[frozenset[str]] = ContextVar(
    "lexinspect_fix_families", default=frozenset(FAMILIES)
)


def enabled(family: str) -> bool:
    """Whether the rules of `family` apply in the current context."""
    if family not in FAMILIES:
        raise KeyError(f"unknown fix family {family!r}")
    return family in _ENABLED.get()


@contextmanager
def only(families: Iterable[str]) -> Iterator[None]:
    """Within the block exactly `families` are enabled; `[]` gives 0.3.3 behaviour."""
    chosen = frozenset(families)
    if unknown := chosen - set(FAMILIES):
        raise KeyError(f"unknown fix families {sorted(unknown)}")
    token = _ENABLED.set(chosen)
    try:
        yield
    finally:
        _ENABLED.reset(token)
