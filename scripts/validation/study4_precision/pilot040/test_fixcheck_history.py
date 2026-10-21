"""What two fix-check tests protected, checked against history instead of the live tree.

    uv run --offline --no-sync python -I -m pytest -q scripts/validation/study4_precision/pilot040/test_fixcheck_history.py

Two tests in fixcheck/ assert facts about the working tree that held while the
fix check ran and stopped holding afterwards, by design:

- test_r9.py::test_g1_g4_real_round1_still_authenticates_against_this_tree
  requires round 1's bound files to equal round 1's freeze record now. That was
  the G1 gate for collecting round 2. The fix check ended when round 2 was
  registered (2026-10-19T03:48:54Z), and Stage 1 has edited the preregistration
  since (first in 5edbf61, 2026-10-20).
- test_fixcheck.py::test_pinned_src_record_checks_tree_and_lock passes the live
  repository as the candidate checkout of `run --pinned-src` and expects its
  uv.lock to be dec79bc's. The repository now holds the v0.4.0 release lock.

The fixcheck/ files are not edited: today's fixcheck/ is byte-identical to the
harness bound in round 2's freeze record, and that should stay checkable.
../conftest.py marks the two tests as strict expected failures. The tests here
check what the gates were for.

Two harness details are recorded here rather than corrected in the frozen files:

- run.py's docstring says `run --pinned-src` was "used for the real
  candidate". Both registered rounds used `run --pinned-checkout` (a full
  checkout of dec79bc in its own environment), as their run/pinned.json records
  show.
- In those records, `uv_lock_sha256_commit` holds the git blob id (SHA-1) of
  dec79bc's uv.lock, not a SHA-256. `uv_lock_sha256_checkout` is the SHA-256.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from fixcheck import collect, run  # noqa: E402

FIX = REPO / "docs" / "validation" / "study4-fix040"
ROUND1_FREEZE = FIX / "round1" / "collect" / "freeze_record.json"
ROUND2_FREEZE = FIX / "round2" / "collect" / "freeze_record.json"
ROUND2_REGISTRATION = FIX / "round2" / "accept" / "registration.json"
PRIVATE = Path.home() / "lexinspect-private" / "study4-fix040"
PINNED_SRC = REPO / ".cache/validation/study4_fix040/equivalence/baseline_033_src"
PREREG = "docs/validation/study4-preregistration.md"


def git(*a: str, text: bool = True):
    return subprocess.run(
        ["git", "-C", str(REPO), *a], capture_output=True, text=text, check=True
    ).stdout


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def round1_bound(fr1: dict) -> list[tuple[str, str, str]]:
    """(name, repo-relative path, sha256) of every file collect.round1_bound_problems checks."""
    led = fr1.get("ledger") or {}
    files = [
        ("ledger Markdown", led.get("markdown")),
        ("ledger components", led.get("components")),
        ("protocol", fr1.get("protocol")),
        ("clarifications", fr1.get("clarifications")),
    ]
    for name, b in sorted((fr1.get("bound") or {}).items()):
        if name != "registry":
            files += [(name.replace("_", " "), f) for f in (b if isinstance(b, list) else [b])]
    out = []
    for name, f in files:
        if isinstance(f, dict) and f.get("path") and f.get("sha256"):
            out.append((name, str(Path(f["path"]).relative_to(REPO)), f["sha256"]))
    return out


def registered_at() -> dt.datetime:
    entry = json.loads(ROUND2_REGISTRATION.read_text())["entry"]
    return dt.datetime.fromisoformat(entry["registered_at"])


def decision_commit() -> str:
    """The commit that added round 2's registration record."""
    return git(
        "log", "--diff-filter=A", "--format=%H", "--", str(ROUND2_REGISTRATION.relative_to(REPO))
    ).split()[-1]


def test_round1_bound_files_held_through_the_round2_decision():
    fr1 = json.loads(ROUND1_FREEZE.read_text())
    bound = round1_bound(fr1)
    assert len(bound) > 5
    at = decision_commit()
    for name, path, want in bound:
        assert sha(git("show", f"{at}:{path}", text=False)) == want, (name, path)
    # round 2's own freeze record bound the same preregistration as round 1's
    fr2 = json.loads(ROUND2_FREEZE.read_text())
    assert fr2["bound"]["preregistration"]["sha256"] == fr1["bound"]["preregistration"]["sha256"]


def test_only_the_preregistration_changed_since_and_only_after_round2():
    fr1 = json.loads(ROUND1_FREEZE.read_text())
    problems = collect.round1_bound_problems(fr1)
    assert len(problems) == 1 and "round 1's preregistration" in problems[0], problems
    want = fr1["bound"]["preregistration"]["sha256"]
    commits = git("rev-list", "--reverse", "HEAD", "--", PREREG).split()
    held = [c for c in commits if sha(git("show", f"{c}:{PREREG}", text=False)) == want]
    first_change = commits[commits.index(held[-1]) + 1]
    when = dt.datetime.fromisoformat(git("log", "-1", "--format=%cI", first_change).strip())
    assert when > registered_at(), (first_change, when)
    # and no version after the first change returns to round 1's text
    later = commits[commits.index(first_change) :]
    assert all(sha(git("show", f"{c}:{PREREG}", text=False)) != want for c in later)


@pytest.mark.skipif(not PINNED_SRC.exists(), reason="pinned source archive not present")
def test_pinned_src_record_answers_both_ways(tmp_path):
    co = tmp_path / "candidate"
    co.mkdir()
    (co / "uv.lock").write_bytes(git("show", "dec79bc:uv.lock", text=False))
    rec = run.pinned_src_record(PINNED_SRC, "dec79bc", co)
    assert rec["tree_identical"] and rec["n_files"] > 50
    assert rec["environment_identical"]
    # the repository holds the v0.4.0 release lock (equal to the tag, checked by
    # pilot040/freeze.py), which is not dec79bc's
    assert git("show", "v0.4.0:uv.lock", text=False) == (REPO / "uv.lock").read_bytes()
    assert not run.pinned_src_record(PINNED_SRC, "dec79bc", REPO)["environment_identical"]


@pytest.mark.skipif(not PRIVATE.is_dir(), reason="private archive absent")
@pytest.mark.parametrize("r", [1, 2])
def test_registered_rounds_ran_the_full_pinned_checkout(r):
    rec = json.loads((PRIVATE / f"round{r}" / "run" / "pinned.json").read_text())
    lock = git("show", "dec79bc:uv.lock", text=False)
    assert rec["method"] == "full checkout of the pinned commit run in its own uv environment"
    assert rec["commit"] == git("rev-parse", "dec79bc^{commit}").strip()
    assert rec["tree_identical"] and rec["environment_identical"]
    assert rec["uv_lock_sha256_checkout"] == sha(lock)
    assert rec["uv_lock_sha256_commit"] == git("rev-parse", "dec79bc:uv.lock").strip()
