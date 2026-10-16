"""Golden outputs: the full `analyze` result for each fixture, frozen.

Any change to a number, label or note fails here, so output changes only
when someone regenerates the files on purpose and the changelog says why.
That is what lets a methods section cite "lexinspect 0.3.0" and get the same
numbers back.

Regenerate after an intended change:
    UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest
from conftest import FIXTURES

from lexinspect import pipeline

GOLDEN = Path(__file__).parent / "golden"
CASES = [
    ("simple", "sample_simple.txt", "gb"),
    ("academic", "sample_academic.txt", "gb"),
    ("narrative", "sample_narrative.txt", "gb"),
    ("learner", "sample_learner.txt", "gb"),
    ("learner-us", "sample_learner.txt", "us"),
]


def _diff(got, want, path="$"):
    """First difference between two JSON values, or None. Floats get 1e-9
    relative tolerance so libm differences between platforms don't count."""
    if isinstance(want, float) and isinstance(got, (int, float)):
        return (
            None
            if math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-12)
            else f"{path}: {got!r} != {want!r}"
        )
    if type(got) is not type(want):
        return f"{path}: type {type(got).__name__} != {type(want).__name__}"
    if isinstance(want, dict):
        if set(got) != set(want):
            return f"{path}: keys added {sorted(set(got) - set(want))}, removed {sorted(set(want) - set(got))}"
        return next((d for k in want if (d := _diff(got[k], want[k], f"{path}.{k}"))), None)
    if isinstance(want, list):
        if len(got) != len(want):
            return f"{path}: length {len(got)} != {len(want)}"
        return next(
            (
                d
                for i, (g, w) in enumerate(zip(got, want, strict=True))
                if (d := _diff(g, w, f"{path}[{i}]"))
            ),
            None,
        )
    return None if got == want else f"{path}: {got!r} != {want!r}"


@pytest.mark.parametrize(("name", "fixture", "variant"), CASES, ids=[c[0] for c in CASES])
def test_output_matches_golden(name, fixture, variant):
    text = (FIXTURES / fixture).read_text()
    _, results = pipeline.run_all(text, variant=variant)
    got = json.loads(json.dumps(results))  # tuples to lists, as clients see it
    path = GOLDEN / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(json.dumps(got, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    want = json.loads(path.read_text())
    assert (d := _diff(got, want)) is None, (
        f"{name}: {d}. If intended, regenerate (see module docstring)."
    )
