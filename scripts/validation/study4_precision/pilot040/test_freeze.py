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
    "late access-review ruling": lambda: (
        freeze.FIX040 / "round2" / "transcripts" / "ACCESS_REVIEW_RULINGS.md"
    ),
    "resumed-session transcript": lambda: first(
        freeze.FIX040 / "post_decision_events", "resumed_*.jsonl"
    ),
    "post-decision checksum target": lambda: first(
        freeze.FIX040 / "post_decision_events", "*_live_labels_rewritten_*.jsonl"
    ),
    "post-decision README": lambda: freeze.FIX040 / "post_decision_events" / "README.md",
    "access-review script": lambda: freeze.FIX040 / "tools" / "review_strict.py",
    "pinned baseline file": lambda: freeze.PINNED / "pyproject.toml",
    "cited final review": lambda: freeze.FIXCACHE / "final_audit" / "sol_final_audit_r2.md",
    "cited harness audit": lambda: freeze.CACHE / "sol_round2_harness_audit_r1.md",
    "access-log Stage-1 snapshot": lambda: freeze.ACCESS_LOG_STAGE1,
}


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_changed_dependency_is_detected(monkeypatch, baseline, name):
    changed = rebuild_with(monkeypatch, TARGETS[name](), "0" * 64)
    assert freeze.differences(baseline, changed) or freeze.PROBLEMS, name


@pytest.mark.parametrize(
    "name",
    [
        "final pilot labels",
        "simulation summary",
        "historical simulation key",
        "rate check",
        "late access-review ruling",
        "post-decision README",
        "cited final review",
        "access-log Stage-1 snapshot",
    ],
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


def test_checksum_target_change_is_a_problem(monkeypatch):
    rebuild_with(monkeypatch, TARGETS["post-decision checksum target"](), "0" * 64)
    assert any("checksum mismatch" in p for p in freeze.PROBLEMS)


def test_appending_to_the_live_access_log_leaves_the_manifest_unchanged(monkeypatch, baseline):
    changed = rebuild_with(monkeypatch, freeze.ACCESS_LOG, "0" * 64)
    assert freeze.PROBLEMS == []
    assert freeze.differences(baseline, changed) == []
    assert changed["administrative_records"]["access_log"] == "docs/validation/study4-access-log.md"


def test_scientific_input_still_fails_after_an_access_log_change(monkeypatch, baseline):
    real = freeze.sha
    targets = {freeze.ACCESS_LOG.resolve(), TARGETS["late access-review ruling"]().resolve()}
    monkeypatch.setattr(
        freeze, "sha", lambda p: "0" * 64 if Path(p).resolve() in targets else real(p)
    )
    assert freeze.differences(baseline, freeze.build_manifest(verify_tars=False))
