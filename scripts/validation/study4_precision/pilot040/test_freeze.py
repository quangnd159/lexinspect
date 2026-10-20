"""Negative controls for the Stage-1 freeze builder.

    uv run --offline --no-sync python -I -m pytest -q scripts/validation/study4_precision/pilot040/test_freeze.py

Each test changes what the builder reads for one dependency, in memory only (no
file is modified), and checks that the rebuilt manifest differs or that the
build fails. The archive tars are not rehashed here, to keep the tests fast;
their check is the same `sha` call as every other receipt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze  # noqa: E402


def first(root: Path, pattern: str) -> Path:
    found = sorted(p for p in root.glob(pattern) if p.is_file())
    assert found, f"no file matches {root}/{pattern}"
    return found[0]


@pytest.fixture(scope="module")
def baseline():
    m = freeze.build_manifest(verify_tars=False)
    assert freeze.PROBLEMS == [], freeze.PROBLEMS
    return m


def rebuild_with(monkeypatch, target: Path, value: str | None):
    real = freeze.sha
    target = target.resolve()

    def fake(p: Path):
        return value if Path(p).resolve() == target else real(p)

    monkeypatch.setattr(freeze, "sha", fake)
    return freeze.build_manifest(verify_tars=False)


TARGETS = {
    "pool file": lambda: first(freeze.DEV / "raw" / "pools", "*"),
    "pilot provider record": lambda: first(freeze.PILOT040 / "sessions" / "B", "*/rollout.jsonl"),
    "pilot session receipt": lambda: first(freeze.PILOT040 / "sessions" / "A", "*/session.json"),
    "validation log": lambda: freeze.PILOT040 / "labels" / "A_batch_validation.json",
    "selection checksum list": lambda: freeze.PILOT040 / "selection" / "build" / "SHA256SUMS",
    "historical pilot label": lambda: first(freeze.PILOT032, "labels_A.jsonl"),
    "historical key": lambda: freeze.DEV / "key.jsonl",
    "historical simulation key": lambda: freeze.DEV032 / "key.jsonl",
    "rate check": lambda: freeze.SIM040 / "ratecheck" / "output.txt",
    "simulation summary": lambda: freeze.SIM040 / "SUMMARY.md",
    "fix-check harness source": lambda: first(freeze.S4 / "fixcheck", "*.py"),
    "fix-check receipt target": lambda: first(
        freeze.FIX040 / "round2" / "run" / "frames", "*.json*"
    ),
    "detector source": lambda: first(freeze.REPO / "src" / "lexinspect", "*.py"),
    "final pilot labels": lambda: freeze.PILOT040 / "labels" / "A_merged.jsonl",
}


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_changed_dependency_is_detected(monkeypatch, baseline, name):
    changed = rebuild_with(monkeypatch, TARGETS[name](), "0" * 64)
    assert freeze.differences(baseline, changed) or freeze.PROBLEMS, name


@pytest.mark.parametrize(
    "name", ["final pilot labels", "simulation summary", "historical simulation key", "rate check"]
)
def test_missing_required_file_fails_the_build(monkeypatch, name):
    rebuild_with(monkeypatch, TARGETS[name](), None)
    assert freeze.PROBLEMS, name


def test_observed_section_is_ignored(baseline):
    other = dict(baseline)
    other["observed"] = {"built": "later", "built_from_commit": "another commit"}
    assert freeze.differences(baseline, other) == []


def test_deposit_receipt_lives_outside_the_manifest(baseline):
    assert "receipt" not in baseline["deposit"]
    assert baseline["deposit"]["record"] == "docs/validation/study4-freeze-deposit.json"
