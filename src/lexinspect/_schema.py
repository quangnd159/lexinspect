"""Schema version + envelope helpers.

The JSON shape every CLI command emits is the public contract that downstream
agents and Skills depend on. Bump SCHEMA_VERSION when changing it in a way
that's not additive.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1"


def envelope(
    module: str,
    source: str,
    char_count: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "module": module,
        "input": {"source": source, "char_count": char_count},
        "result": result,
    }
