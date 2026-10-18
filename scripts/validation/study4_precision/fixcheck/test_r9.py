"""Round-2 harness gaps (ROUND2_PLAN.md section 4; docs/validation/study4-fix040/round2/
HARNESS_ROUND2_RULINGS.md): G1, G2, G3, G4, G5, G7, G10 and G12 are regressions here.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck

No test touches the network: collections read synthetic mock caches (test_fixcheck's
_mock_cache), the git repositories are local temporary ones, and the dry-run checks run on
synthetic frames. No production command is run against the canonical registry or the
freeze directory; the real round-1 files are only read. No real label exists anywhere.
"""

from __future__ import annotations

import functools
import inspect
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fixcheck import collect, dryrun, freeze, ledger, registry  # noqa: E402
from fixcheck.common import read_json, sha256_file, source_hashes, write_json  # noqa: E402
from fixcheck.ledger import FAMILIES  # noqa: E402
from fixcheck.test_fixcheck import _collect_r1, _mock_cache  # noqa: E402
from fixcheck.test_r4 import _dec, _git, _res  # noqa: E402
from fixcheck.test_r6 import _public_documents  # noqa: E402

REPO = freeze.REPO
ROUND1 = freeze.FREEZE_DIR / "round1" / "collect"
RULINGS = freeze.FREEZE_DIR / "round2" / "HARNESS_ROUND2_RULINGS.md"
RUNBOOK = freeze.FREEZE_DIR / "RUNBOOK.md"
KEPT = ["MD-D", "MD-H", "MD-I", "PH-A", "PH-B", "PH-C"]


# --- fixtures: a temporary source repository and a registered round 1 --------------------


def _src_repo(tmp_path) -> tuple[Path, dict[str, str]]:
    """A local repository with three commits: A, then B (a.py changed, b.py removed, c.py
    added under src/lexinspect), then C (src/lexinspect back to A's tree; only a README
    differs). `.cache/` is git-ignored, as in this repository."""
    repo = tmp_path / "srcrepo"
    src = repo / "src" / "lexinspect"
    src.mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    (repo / ".gitignore").write_text(".cache/\n")
    (repo / "docs").mkdir()
    (src / "a.py").write_text("a = 1\n")
    (src / "b.py").write_text("b = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "A")
    commits = {"A": _git(repo, "rev-parse", "HEAD").stdout.strip()}
    (src / "a.py").write_text("a = 2\n")
    (src / "b.py").unlink()
    (src / "c.py").write_text("c = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "B")
    commits["B"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (src / "a.py").write_text("a = 1\n")
    (src / "b.py").write_text("b = 1\n")
    (src / "c.py").unlink()
    (repo / "README").write_text("C\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "C")
    commits["C"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return repo, commits


def _use_src_repo(monkeypatch, repo: Path) -> None:
    """Commit digests and the round-2 tracking checks read the temporary repository."""
    monkeypatch.setattr(
        freeze, "commit_src_digest", functools.partial(freeze.commit_src_digest, repo=repo)
    )
    monkeypatch.setattr(freeze, "REPO", repo)


def _r1_registry(path: Path, r1: Path, cand=None, tree=None, status="fail") -> Path:
    """A scratch registry holding round 1's reservation and its non-pass decision."""
    col = read_json(r1 / "collection.json")
    res = {
        "type": "reservation",
        "round": 1,
        "candidate_commit": cand,
        "candidate_tree_sha256": tree,
        "seed": col["seed"],
        "collect_dir": str(r1),
        "registered_at": "2026-10-17T00:00:00+00:00",
    }
    dec = {
        "type": "decision",
        "round": 1,
        "candidate_commit": cand or "c1",
        "candidate_tree_sha256": tree,
        "seed": col["seed"],
        "reservation_sha256": registry.entry_sha256(res),
        "freeze_record_sha256": sha256_file(r1 / "freeze_record.json"),
        "collection_texts_sha256": sha256_file(r1 / "texts.jsonl"),
        "source_refs": [],
        "inputs_sha256": "i1",
        "status": status,
        "families": list(FAMILIES),
    }
    path.write_text("")
    registry.append_unchecked(path, res)
    registry.append_unchecked(path, dec)
    return path


def _round1(tmp_path, extra=()) -> tuple[Path, Path, Path]:
    """A dry-run round 1 at tmp/r1 whose raw cache is tmp/p1/raw (its private directory is
    tmp/p1, so a round-2 cache elsewhere under tmp is disjoint from it, as G5 requires)."""
    dev_raw, raw = _mock_cache(tmp_path / "p1")
    assert _collect_r1(tmp_path, raw, dev_raw, extra=("--offline", *extra)) == 0
    return dev_raw, raw, tmp_path / "r1"


def _r2(tmp_path, raw, dev_raw, r1, reg, *extra, out="r2", dry=True) -> list[str]:
    argv = [
        "--round",
        "2",
        "--seed",
        "778",
        "--out",
        str(tmp_path / out),
        "--raw-cache",
        str(raw),
        "--dev-raw",
        str(dev_raw),
        "--offline",
        "--plan-only",
        "--earlier",
        str(r1),
        "--registry",
        str(reg),
        *extra,
    ]
    return [*argv, "--dry-run"] if dry else argv


def _ledger_copy(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ledger.LEDGER_MD, dest)
    return dest


# --- G1: round 1's bound files stay byte-equal; round 2 has its own ledger ---------------


def _bound_files(tmp_path) -> dict:
    files = {}
    for name in ("md", "comp", "protocol", "clar", "prereg", "spec", "reg", "d1", "d2"):
        p = tmp_path / "bound" / f"{name}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{name}\n")
        files[name] = p

    def ident(n):
        return {"path": str(files[n]), "sha256": sha256_file(files[n])}

    fr1 = {
        "ledger": {"markdown": ident("md"), "components": ident("comp")},
        "protocol": ident("protocol"),
        "clarifications": ident("clar"),
        "bound": {
            "preregistration": ident("prereg"),
            "delivery_spec": ident("spec"),
            "registry": ident("reg"),
            "dispositions": [ident("d1"), ident("d2")],
        },
    }
    return files, fr1


def test_g1_round1_bound_problems_covers_every_bound_file_but_the_registry(tmp_path):
    files, fr1 = _bound_files(tmp_path)
    assert collect.round1_bound_problems(fr1) == []
    files["reg"].write_text("appended\n")  # the append-only registry is not compared
    assert collect.round1_bound_problems(fr1) == []
    names = {
        "md": "ledger Markdown",
        "comp": "ledger components",
        "protocol": "protocol",
        "clar": "clarifications",
        "prereg": "preregistration",
        "spec": "delivery spec",
        "d2": "dispositions",
    }
    for key, name in names.items():
        before = files[key].read_bytes()
        files[key].write_text("changed\n")
        probs = collect.round1_bound_problems(fr1)
        assert len(probs) == 1 and f"round 1's {name} " in probs[0], probs
        assert "has changed" in probs[0]
        files[key].write_bytes(before)
    files["protocol"].unlink()
    assert ["is missing" in p for p in collect.round1_bound_problems(fr1)] == [True]
    # a name round 1 never bound (no path or no hash) is not compared
    fr1["protocol"] = {"path": None, "sha256": None}
    fr1["bound"]["delivery_spec"] = {"path": str(files["spec"]), "sha256": None}
    assert collect.round1_bound_problems(fr1) == []


def test_g1_changed_round1_ledger_refuses_round2_planning_before_any_reservation(tmp_path):
    l1 = _ledger_copy(tmp_path / "led" / "round1.md")
    dev_raw, raw, r1 = _round1(tmp_path, extra=("--ledger-md", str(l1)))
    assert read_json(r1 / "freeze_record.json")["ledger"]["markdown"]["path"] == str(l1)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    l2 = _ledger_copy(tmp_path / "led" / "round2.md")
    before = reg.read_bytes()
    l1.write_text(l1.read_text() + "\nedited after the round-1 freeze\n")
    with pytest.raises(SystemExit, match="round 1's ledger Markdown .* has changed"):
        collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, "--ledger-md", str(l2)))
    assert reg.read_bytes() == before  # refused before the reservation
    assert not (tmp_path / "r2" / "freeze_record.json").exists()
    shutil.copyfile(ledger.LEDGER_MD, l1)  # restored byte for byte: planning proceeds
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, "--ledger-md", str(l2))) == 0


def test_g1_round2_ledger_must_not_be_round1s(tmp_path):
    dev_raw, raw, r1 = _round1(tmp_path)  # binds the default ledger path
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    before = reg.read_bytes()
    raw2 = tmp_path / "raw2"
    # a production plan naming round 1's ledger file (the default) is refused
    with pytest.raises(SystemExit, match="is round 1's ledger"):
        collect.main(_r2(tmp_path, raw2, dev_raw, r1, reg, dry=False))
    assert reg.read_bytes() == before
    # a dry run of a dry-run round 1 keeps the earlier behaviour (demonstrations, tests)
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, out="r2dry")) == 0


def test_g1_same_ledger_rule_unit(tmp_path):
    led = tmp_path / "l.md"
    fr1 = {"ledger": {"markdown": {"path": str(led)}}, "production_eligible": False}
    assert collect.same_ledger_as_round1(led, fr1, dry_run=False)
    assert not collect.same_ledger_as_round1(led, fr1, dry_run=True)
    assert collect.same_ledger_as_round1(led, fr1 | {"production_eligible": True}, dry_run=True)
    other = tmp_path / "round2" / "l.md"
    assert not collect.same_ledger_as_round1(other, fr1, dry_run=False)
    # the same file under another spelling is the same file
    assert collect.same_ledger_as_round1(tmp_path / "x" / ".." / "l.md", fr1, dry_run=False)


@pytest.mark.skipif(not (ROUND1 / "freeze_record.json").exists(), reason="no round-1 record")
def test_g1_g4_real_round1_still_authenticates_against_this_tree():
    # the registered round 1's bound files (ledger, components, protocol, clarifications,
    # preregistration, delivery spec, dispositions) are byte-equal now; the frozen inputs
    # too; only harness files differ (disclosed)
    fr1 = read_json(ROUND1 / "freeze_record.json")
    assert fr1["production_eligible"] is True
    assert collect.round1_bound_problems(fr1) == []
    changed = collect.harness_vs_round1(fr1)
    assert changed and all(k.startswith("fixcheck/") for k in changed)
    assert "fixcheck/test_r9.py" in changed  # added after round 1
    # round 2's ledger is its own file
    r2_ledger = freeze.FREEZE_DIR / "round2" / "CANDIDATE_LEDGER.md"
    assert collect.same_ledger_as_round1(ledger.LEDGER_MD, fr1, dry_run=True)
    assert not collect.same_ledger_as_round1(r2_ledger, fr1, dry_run=False)


# --- G2: the narrowing disposition, the ledger's tracking, the candidate's changes -------


def _disposition_cases(repo: Path, commit: str) -> dict[str, Path]:
    docs, cache = repo / "docs", repo / ".cache"
    cache.mkdir(exist_ok=True)
    ok = f"# Narrowing\n\n**Status:** FINAL\n\nCandidate {commit}.\n"
    cases = {
        "ok": (docs / "ok.md", ok),
        "draft": (docs / "draft.md", ok.replace("FINAL", "DRAFT")),
        "reviewed": (docs / "reviewed.md", ok.replace("FINAL", "REVIEWED")),
        "no_status": (docs / "nostatus.md", ok.replace("**Status:** FINAL\n\n", "")),
        "no_commit": (docs / "nocommit.md", ok.replace(commit, commit[:11])),
        "ignored": (cache / "ignored.md", ok),
        "outside": (repo.parent / "outside.md", ok),
    }
    for p, text in cases.values():
        p.write_text(text)
    return {k: p for k, (p, _) in cases.items()}


def _g2_only(why: list[str]) -> list[str]:
    """The G2 reasons; the narrowing-check reasons (G10) are tested in test_r10.py."""
    return [w for w in why if "narrowing check" not in w]


G2_MESSAGES = {
    "draft": "has status DRAFT, not FINAL",
    "reviewed": "has status REVIEWED, not FINAL",
    "no_status": "has no **Status:** line",
    "no_commit": "does not name the round-2 candidate commit",
    "ignored": "narrowing disposition is git-ignored",
    "outside": "narrowing disposition is outside the repository",
}


def test_g2_disposition_identity_and_round2_problems(tmp_path):
    repo, commits = _src_repo(tmp_path)
    cand = commits["B"]
    paths = _disposition_cases(repo, cand)
    good_changes = {"round1_tree_matches_registry": True}
    for case, path in paths.items():
        ident = freeze.disposition_identity(path, cand, repo)
        assert ident["sha256"] == sha256_file(path) and ident["candidate_prefix"] == cand[:12]
        why = _g2_only(
            freeze.round2_problems(
                {"narrowing_disposition": ident, "candidate_changes_vs_round1": good_changes}
            )
        )
        if case == "ok":
            assert ident["status"] == "FINAL" and ident["names_candidate"]
            assert ident["in_repository"] and ident["git_ignored"] is False
            assert why == []
        else:
            assert len(why) == 1 and G2_MESSAGES[case] in why[0], (case, why)
    # a force-added file under an ignored directory still counts as ignored
    _git(repo, "add", "-f", ".cache/ignored.md")
    assert freeze.git_ignored(paths["ignored"], repo) is True
    assert freeze.git_ignored(paths["outside"], repo) is None
    # no commit to name (a dry run without --candidate-commit): never names it
    assert freeze.disposition_identity(paths["ok"], None, repo)["names_candidate"] is False


def test_g2_ledger_tracking_and_candidate_changes_problems(tmp_path):
    repo, _ = _src_repo(tmp_path)
    (repo / ".cache").mkdir()
    for p in (repo / "docs" / "l.md", repo / ".cache" / "l.md", tmp_path / "out.json"):
        p.write_text("x\n")
    good = {"round1_tree_matches_registry": True}

    def why(tracking, changes=good):
        return _g2_only(
            freeze.round2_problems({"tracking": tracking, "candidate_changes_vs_round1": changes})
        )

    t = functools.partial(freeze.tracking_identity, repo=repo)
    assert why({"ledger_markdown": t(repo / "docs" / "l.md")}) == []
    [w] = why({"ledger_markdown": t(repo / ".cache" / "l.md")})
    assert "ledger markdown is git-ignored (git check-ignore --no-index" in w
    [w] = why({"ledger_components": t(tmp_path / "out.json")})
    assert "ledger components is outside the repository (the archive receipt" in w
    assert why({"ledger_components": t(None)}) == []  # nothing given: other checks apply
    [w] = why({}, changes=None)
    assert "could not record its candidate's changes" in w
    [w] = why({}, changes={"round1_tree_matches_registry": False})
    assert "no longer has its registered tree digest" in w


@pytest.mark.parametrize("case", ["ok", "draft", "no_status", "no_commit", "ignored", "outside"])
def test_g2_round2_record_discloses_changes_and_disposition_state(tmp_path, monkeypatch, case):
    repo, commits = _src_repo(tmp_path)
    dev_raw, raw, r1 = _round1(tmp_path)
    tree_a = freeze.commit_src_digest(commits["A"], repo)["tree_sha256"]
    reg = _r1_registry(tmp_path / "reg.jsonl", r1, cand=commits["A"], tree=tree_a)
    _use_src_repo(monkeypatch, repo)
    disp = _disposition_cases(repo, commits["B"])[case]
    l2 = _ledger_copy(repo / "docs" / "round2" / "CANDIDATE_LEDGER.md")
    comps = repo / "docs" / "ledger_components.json"
    shutil.copyfile(ledger.LEDGER_COMPONENTS, comps)
    argv = _r2(
        tmp_path,
        raw,
        dev_raw,
        r1,
        reg,
        "--candidate-commit",
        commits["B"],
        "--narrowing-disposition",
        str(disp),
        "--ledger-md",
        str(l2),
        "--ledger-components",
        str(comps),
    )
    assert collect.main(argv) == 0
    r2 = read_json(tmp_path / "r2" / "freeze_record.json")["round2"]
    ch = r2["candidate_changes_vs_round1"]
    assert ch["round1_commit"] == commits["A"] and ch["candidate_commit"] == commits["B"]
    assert ch["round1_tree_sha256"] == tree_a and ch["round1_tree_matches_registry"]
    assert ch["candidate_tree_sha256"] != tree_a
    assert (ch["changed"], ch["added"], ch["removed"]) == (["a.py"], ["c.py"], ["b.py"])
    assert r2["tracking"]["ledger_markdown"]["git_ignored"] is False
    assert r2["tracking"]["ledger_components"]["git_ignored"] is False
    assert r2["harness_changed_vs_round1"] == []  # same harness as this test's round 1
    reasons = read_json(tmp_path / "r2" / "freeze_record.json")["ineligible_reasons"]
    g2 = [r for r in reasons if "narrowing disposition" in r]
    if case == "ok":
        assert g2 == []
    else:
        assert len(g2) == 1 and G2_MESSAGES[case] in g2[0], reasons
    assert not [r for r in reasons if "ledger" in r and "git-ignored" in r]


def test_g2_production_plan_refuses_a_draft_disposition_before_the_reservation(
    tmp_path, monkeypatch
):
    repo, commits = _src_repo(tmp_path)
    dev_raw, raw, r1 = _round1(tmp_path)
    tree_a = freeze.commit_src_digest(commits["A"], repo)["tree_sha256"]
    reg = _r1_registry(tmp_path / "reg.jsonl", r1, cand=commits["A"], tree=tree_a)
    _use_src_repo(monkeypatch, repo)
    paths = _disposition_cases(repo, commits["B"])
    l2 = _ledger_copy(repo / ".cache" / "CANDIDATE_LEDGER.md")  # a git-ignored ledger
    before = reg.read_bytes()
    argv = _r2(
        tmp_path,
        tmp_path / "raw2",
        dev_raw,
        r1,
        reg,
        "--candidate-commit",
        commits["B"],
        "--narrowing-disposition",
        str(paths["draft"]),
        "--ledger-md",
        str(l2),
        dry=False,
    )
    with pytest.raises(SystemExit) as e:
        collect.main(argv)
    msg = str(e.value)
    assert msg.startswith("not a production freeze")
    assert "has status DRAFT, not FINAL" in msg
    assert "ledger markdown is git-ignored" in msg
    assert reg.read_bytes() == before and not (tmp_path / "r2" / "freeze_record.json").exists()


def test_g2_candidate_changes_unavailable_without_both_commits(tmp_path, monkeypatch):
    repo, commits = _src_repo(tmp_path)
    _use_src_repo(monkeypatch, repo)
    assert collect.candidate_changes({"candidate_commit": None}, {"commit": commits["B"]}) is None
    assert collect.candidate_changes({"candidate_commit": "c1"}, {"commit": commits["B"]}) is None
    assert collect.candidate_changes({"candidate_commit": commits["A"]}, {}) is None
    same = collect.candidate_changes(
        {"candidate_commit": commits["A"], "candidate_tree_sha256": "other"},
        {"commit": commits["C"]},
    )
    assert same["changed"] == same["added"] == same["removed"] == []
    assert same["round1_tree_matches_registry"] is False


# --- G3: a revised candidate needs a revised src/lexinspect tree -------------------------


def _with_tree(entry: dict, tree: str | None) -> dict:
    return entry | {"candidate_tree_sha256": tree}


def test_g3_reservation_and_decision_refuse_round1s_tree():
    r1res = _with_tree(_res(), "T1")
    r1dec = _with_tree(_dec(res=r1res), "T1")
    e = [r1res, r1dec]
    same = _with_tree(_res(rnd=2, cand="c2", seed=2, cdir="r2"), "T1")
    verdict, probs = registry.check_reservation(e, same)
    assert verdict == "refuse"
    assert probs == [
        "round 2 needs a revised candidate: its src/lexinspect tree digest equals round 1's"
    ]
    revised = _with_tree(_res(rnd=2, cand="c2", seed=2, cdir="r2"), "T2")
    assert registry.check_reservation(e, revised) == ("append", [])
    # entries without a recorded tree (older fixtures) are not compared
    assert registry.check_reservation([_res(), _dec()], _res(rnd=2, cand="c2", seed=2))[0] == (
        "append"
    )
    for res2, tree in ((same, "T1"), (revised, "T2")):
        d2 = _with_tree(
            _dec(rnd=2, cand="c2", seed=2, texts="t2", refs=("s2",), res=res2, r1=r1dec), tree
        )
        verdict, probs = registry.check_decision([*e, res2], d2)
        if tree == "T1":
            assert verdict == "refuse" and any("tree digest equals round 1's" in p for p in probs)
        else:
            assert (verdict, probs) == ("append", [])


def test_g3_round2_plan_of_a_new_commit_with_round1s_tree_is_refused(tmp_path, monkeypatch):
    repo, commits = _src_repo(tmp_path)
    dev_raw, raw, r1 = _round1(tmp_path)
    tree_a = freeze.commit_src_digest(commits["A"], repo)["tree_sha256"]
    reg = _r1_registry(tmp_path / "reg.jsonl", r1, cand=commits["A"], tree=tree_a)
    _use_src_repo(monkeypatch, repo)
    before = reg.read_bytes()
    argv = _r2(tmp_path, raw, dev_raw, r1, reg, "--candidate-commit", commits["C"])
    with pytest.raises(SystemExit, match="tree digest equals round 1's"):
        collect.main(argv)
    assert reg.read_bytes() == before


# --- G4: the frozen Study 4 inputs equal round 1's; harness changes are disclosed --------


def test_g4_harness_vs_round1_unit():
    now = source_hashes()
    assert collect.harness_vs_round1({"sources_sha256": now}) == []
    fr1 = {"sources_sha256": now | {"fixcheck/collect.py": "0" * 64, "fixcheck/old.py": "1"}}
    assert collect.harness_vs_round1(fr1) == ["fixcheck/collect.py", "fixcheck/old.py"]
    for name in ("build.py", "analyse.py", "estimators.py", "frame.py", "batches.py"):
        with pytest.raises(SystemExit, match=f"frozen Study 4 inputs \\['{name}'\\]"):
            collect.harness_vs_round1({"sources_sha256": now | {name: "0" * 64}})
    missing = {k: v for k, v in now.items() if k != "frame.py"}
    with pytest.raises(SystemExit, match="frame.py"):
        collect.harness_vs_round1({"sources_sha256": missing})
    with pytest.raises(SystemExit, match="frozen Study 4 inputs"):
        collect.harness_vs_round1({})


def test_g4_round2_plan_refuses_changed_frozen_inputs_and_discloses_harness(tmp_path, monkeypatch):
    dev_raw, raw, r1 = _round1(tmp_path)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    real = collect.source_hashes
    monkeypatch.setattr(collect, "source_hashes", lambda: real() | {"estimators.py": "0" * 64})
    with pytest.raises(SystemExit, match=r"frozen Study 4 inputs \['estimators.py'\]"):
        collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, out="r2x"))
    monkeypatch.setattr(collect, "source_hashes", lambda: real() | {"fixcheck/new.py": "0"})
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg)) == 0
    r2 = read_json(tmp_path / "r2" / "freeze_record.json")["round2"]
    assert r2["harness_changed_vs_round1"] == ["fixcheck/new.py"]


# --- G5: a production round's raw cache is private and its own ---------------------------


def test_g5_raw_cache_inside_the_repository_is_refused_before_any_write(tmp_path, monkeypatch):
    dev_raw, _ = _mock_cache(tmp_path)
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    monkeypatch.setattr(collect, "REPO", fake_repo)
    base = ["--round", "1", "--seed", "777", "--dev-raw", str(dev_raw), "--plan-only"]
    argvs = [
        [*base, "--out", str(tmp_path / "o1"), "--raw-cache", str(fake_repo / "raw")],
        [*base, "--out", str(fake_repo / "round1" / "collect")],  # the default <out>/raw
    ]
    for argv in argvs:
        with pytest.raises(SystemExit, match="is inside the repository"):
            collect.main([*argv, "--registry", str(tmp_path / "reg.jsonl")])
    assert sorted(p.name for p in fake_repo.iterdir()) == []
    assert not (tmp_path / "o1").exists() and not (tmp_path / "reg.jsonl").exists()


def test_g5_round2_raw_cache_must_not_be_round1s(tmp_path):
    dev_raw, raw, r1 = _round1(tmp_path)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    before = reg.read_bytes()
    for spelling in (raw, raw.parent / "x" / ".." / raw.name):
        with pytest.raises(SystemExit, match="is the raw cache of the earlier round"):
            collect.main(_r2(tmp_path, spelling, dev_raw, r1, reg, dry=False))
    assert reg.read_bytes() == before and not (tmp_path / "r2").exists()
    # dry runs keep sharing a mock cache (demonstrations, tests)
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg)) == 0


# --- G7: the dry run takes the ledger to bind and check ----------------------------------


class _Stop(Exception):
    pass


def _no_lexinspect(monkeypatch):
    monkeypatch.delitem(sys.modules, "lexinspect", raising=False)


def test_g7_g10_dryrun_arguments_reach_the_resume_identity(tmp_path, monkeypatch):
    _no_lexinspect(monkeypatch)
    seen = {}

    def snapshot(out_root, out, commit, overwrite, settings=None, require_fresh=False):
        seen.update(settings)
        raise _Stop

    monkeypatch.setattr(dryrun, "snapshot_and_key", snapshot)
    l2 = _ledger_copy(tmp_path / "round2" / "CANDIDATE_LEDGER.md")
    argv = ["--out-root", str(tmp_path / "dr"), "--ledger-md", str(l2)]
    compare = ["--compare-candidate", "3d4df70", "--kept", "PH-A, MD-D"]
    with pytest.raises(SystemExit, match="--compare-candidate needs --commit"):
        dryrun.main([*argv, *compare])  # never a working-tree snapshot
    with pytest.raises(_Stop):
        dryrun.main([*argv, "--commit", "HEAD", *compare])
    assert seen["ledger_md"] == str(l2.resolve())
    assert seen["ledger_md_sha256"] == sha256_file(l2)
    # the comparison commit is resolved to its full id before the resume key
    assert seen["compare_candidate"] == freeze.full_commit("3d4df70")
    assert len(seen["compare_candidate"]) == 40 and seen["kept"] == ["MD-D", "PH-A"]
    if ledger.DRAFT_LEDGER_MD.exists():
        seen.clear()
        with pytest.raises(_Stop):
            dryrun.main(["--out-root", str(tmp_path / "dr")])
        assert seen["ledger_md"] == str(ledger.DRAFT_LEDGER_MD.resolve())
        assert seen["kept"] is None and seen["compare_candidate"] is None
    with pytest.raises(SystemExit, match="not found"):
        dryrun.main(["--out-root", str(tmp_path / "dr"), "--ledger-md", str(tmp_path / "no")])


def test_g7_demonstration_plan_binds_the_given_ledger(tmp_path, monkeypatch):
    _no_lexinspect(monkeypatch)
    out = tmp_path / "dr"
    (out / "candidate_src").mkdir(parents=True)
    write_json(out / "candidate_src" / "CANDIDATE_SNAPSHOT.json", {"tree_sha256": "t"})
    write_json(out / "ledger" / "ledger_components.json", {})
    write_json(out / "collect_replay" / "replay.json", {})
    write_json(out / "delivery_spec.json", {})
    monkeypatch.setattr(
        dryrun, "snapshot_and_key", lambda *a, **k: (out, {"candidate_tree_sha256": "t"})
    )
    calls = []

    def cli(args):
        calls.append(args)
        raise _Stop

    monkeypatch.setattr(dryrun, "_cli", cli)
    monkeypatch.setattr(sys, "path", list(sys.path))
    l2 = _ledger_copy(tmp_path / "round2" / "CANDIDATE_LEDGER.md")
    with pytest.raises(_Stop):
        dryrun.main(["--out-root", str(tmp_path), "--ledger-md", str(l2)])
    [plan] = calls
    assert plan[:2] == ["collect", "--round"] and "--plan-only" in plan and "--dry-run" in plan
    assert plan[plan.index("--ledger-md") + 1] == str(l2.resolve())


def test_g7_both_verify_calls_and_the_round_dir_use_the_given_ledger():
    src = inspect.getsource(dryrun.main)
    assert "str(DRAFT_LEDGER_MD)" not in src
    # the demonstration plan and the two verify calls
    assert re.findall(r'"--ledger-md",\s*str\((\w+)\)', src) == ["ledger_md"] * 3
    assert "dev_round_dir(out, candidate, spec, ledger_md)" in src


@pytest.mark.skipif(not collect.build.DEV_TEXTS.exists(), reason="development texts absent")
def test_g7_development_round_record_binds_the_given_ledger(tmp_path):
    l2 = _ledger_copy(tmp_path / "round2" / "CANDIDATE_LEDGER.md")
    cand = {"commit": None, "tree_sha256": "t", "n_files": 1}
    d = dryrun.dev_round_dir(tmp_path / "a", cand, None, l2)
    md = read_json(d / "freeze_record.json")["ledger"]["markdown"]
    assert md["path"] == str(l2) and md["sha256"] == sha256_file(l2)
    if ledger.DRAFT_LEDGER_MD.exists():
        d = dryrun.dev_round_dir(tmp_path / "b", cand, None)
        md = read_json(d / "freeze_record.json")["ledger"]["markdown"]
        assert md["path"] == str(ledger.DRAFT_LEDGER_MD)


# --- G10: kept-family identity, from the harness's own frames ----------------------------


def test_g10_parse_kept():
    assert dryrun.parse_kept(None, None) is None
    assert dryrun.parse_kept("c", "PH-C,MD-D, MD-H") == ["MD-D", "MD-H", "PH-C"]
    assert dryrun.parse_kept("c", ",".join(KEPT)) == KEPT
    for commit, kept in (
        ("c", None),
        (None, "MD-D"),
        ("", "MD-D"),
        ("c", ""),
        ("c", "MD-D,MD-D"),
        ("c", "MD-D,MD-Z"),
        ("c", "COMPLETE"),
    ):
        with pytest.raises(SystemExit):
            dryrun.parse_kept(commit, kept)


# The kept-family identity itself, with its input authentication and every kept
# combination, is tested in test_r10.py (round-2 harness audit r1, findings 1 and 3).


def test_g10_frames_carry_modules_used_by_the_check():
    # the frames.json keys the check reads are the ones frame_summary reports
    src = inspect.getsource(dryrun.frame_summary)
    for k in ("N_baseline", "N_candidate", "N_affected"):
        assert f'"{k}"' in src


# --- G12: the public-document content check reads regular, tracked files only ------------


def test_g12_public_documents_are_regular_tracked_files():
    docs = _public_documents()
    assert docs and all(p.is_file() for p in docs)
    rels = [p.relative_to(REPO).as_posix() for p in docs]
    tracked = set(
        subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z", "--", *rels],
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    in_rounds = [r for r in rels if "/round1/" in r or "/round2/" in r]
    assert set(in_rounds) <= tracked  # never an untracked private body
    for private in ("collection.json", "texts.jsonl", "fetch_journal.jsonl", "execution.lock"):
        assert f"docs/validation/study4-fix040/round1/collect/{private}" not in rels
    if "docs/validation/study4-fix040/round1/collect/freeze_record.json" in tracked:
        assert "docs/validation/study4-fix040/round1/collect/freeze_record.json" in rels


# --- documentation: the round-2 rulings and the runbook ----------------------------------


def test_round2_rulings_and_runbook_state_the_round2_rules():
    rulings = RULINGS.read_text(encoding="utf-8")
    for gap in ("G1", "G2", "G3", "G4", "G5", "G7", "G10", "G12"):
        assert f"**{gap}" in rulings, gap
    text = RUNBOOK.read_text(encoding="utf-8")
    s9 = text[text.index("## 9. Round 2") :]
    for needle in (
        "--ledger-md <REPO>/docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md",
        "ledger_components.json",
        "docs/validation/study4-fix040/round2/NARROWING_DISPOSITION.md",
        "**Status:** FINAL",
        "--raw-cache <R2>/raw",
        "--compare-candidate 3d4df7012656defd5a44571410af00896f634a2d",
        "--kept MD-D,MD-H,MD-I,PH-A,PH-B,PH-C",
        "kept_family_identity.ok",
        "--narrowing-check <REPO>/docs/validation/study4-fix040/round2/NARROWING_CHECK.json",
        "Never overwrite round 1's files",
        "HARNESS_ROUND2_RULINGS.md",
    ):
        assert needle in s9, needle
