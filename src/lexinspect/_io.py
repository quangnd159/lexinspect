"""Shared input handling: read from file path or stdin (-)."""

from __future__ import annotations

import sys
from pathlib import Path


def read_text(source: str) -> tuple[str, str]:
    """Return (text, display_source). source='-' reads stdin."""
    if source == "-":
        return sys.stdin.read(), "<stdin>"
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(f"No such file: {source}")
    return p.read_text(encoding="utf-8"), str(p)
