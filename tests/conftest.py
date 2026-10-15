"""Shared fixtures.

Parsing is the expensive step, so every test that only needs to *read* an
analysis goes through `analysed()`, which parses each distinct text once per
test session. Modules never mutate an `Analysis`, so sharing is safe.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from lexinspect._text import Analysis, analyse

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE = (FIXTURES / "sample_simple.txt").read_text()
ACADEMIC = (FIXTURES / "sample_academic.txt").read_text()
NARRATIVE = (FIXTURES / "sample_narrative.txt").read_text()


@lru_cache(maxsize=256)
def analysed(text: str) -> Analysis:
    return analyse(text)


@pytest.fixture(scope="session")
def simple() -> str:
    return SIMPLE


@pytest.fixture(scope="session")
def academic() -> str:
    return ACADEMIC


@pytest.fixture(scope="session")
def narrative() -> str:
    return NARRATIVE
