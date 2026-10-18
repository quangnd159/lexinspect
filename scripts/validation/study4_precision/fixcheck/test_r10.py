"""Round-2 harness audit r1 (.cache/validation/sol_round2_harness_audit_r1.md), findings 1 to 5.

- Finding 1: the narrowing check (NARROWING_CHECK.json, narrowing.py) is a production
  prerequisite of the round-2 plan, validated before the reservation, rebuilt at execution,
  bound and receipted in the freeze record and rechecked at acceptance.
- Finding 2: round 1's receipted command.txt and manifest_plan.json and its execution
  receipt (collect.round1_preservation_problems), at planning and at acceptance.
- Finding 3: the kept-family comparison authenticates every saved input (dryrun.
  kept_family_identity) and covers every combination of two or more kept families; the
  `narrowing-check` command's exit status.
- Finding 4: the raw cache is disjoint from round 1's cache and private directory, holds no
  link into them, and is fresh at planning.
- Finding 5: the documentation wording.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck/test_r10.py

No test touches the network. Repositories are temporary local ones; the canonical registry
and the freeze directory are only read. No real label or text exists anywhere here.
"""

from __future__ import annotations

import ast
import inspect
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fixcheck import cli, collect, dryrun, freeze, narrowing, package  # noqa: E402
from fixcheck.common import (  # noqa: E402
    read_json,
    read_jsonl,
    sha256_file,
    sha256_text,
    source_hashes,
    write_json,
    write_step_manifest,
)
from fixcheck.ledger import COMPLETE, FAMILIES, MODULES  # noqa: E402
from fixcheck.test_r4 import _git  # noqa: E402
from fixcheck.test_r9 import (  # noqa: E402
    _ledger_copy,
    _r1_registry,
    _r2,
    _round1,
    _src_repo,
    _use_src_repo,
)

REPO = freeze.REPO
KEPT = list(narrowing.KEPT)
REVERTED = list(narrowing.REVERTED)
RULINGS = freeze.FREEZE_DIR / "round2" / "HARNESS_ROUND2_RULINGS.md"
RUNBOOK = freeze.FREEZE_DIR / "RUNBOOK.md"
LEDGER2 = REPO / ".cache" / "validation" / "study4_fix040" / "round2" / "CANDIDATE_LEDGER.md"


class _Stop(Exception):
    pass


# --- a synthetic, fully manifested dry run (findings 1 and 3) -----------------------------


def _snapshot(repo: Path, commit: str, dest: Path) -> None:
    """candidate_src: `git archive <commit> src/lexinspect` of the temporary repository, with
    the snapshot record prepare-candidate writes (commit, tree digest)."""
    dest.mkdir(parents=True)
    data = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", commit, "src/lexinspect"],
        capture_output=True,
        check=True,
    ).stdout
    tmp = dest / ".x"
    tmp.mkdir()
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=data, check=True)
    shutil.move(str(tmp / "src" / "lexinspect"), str(dest / "lexinspect"))
    shutil.rmtree(tmp)
    d = freeze.commit_src_digest(commit)  # the temporary repository's (_use_src_repo)
    write_json(
        dest / "CANDIDATE_SNAPSHOT.json",
        {"commit": d["commit"], "tree_sha256": d["tree_sha256"], "source": "commit"},
    )


BASE_KEYS = [("k1", MODULES[0]), ("k2", MODULES[0]), ("k3", MODULES[1])]


def _keys(families: list[str]) -> list[tuple[str, str]]:
    """The fake hits of a configuration: BASELINE's, plus one per kept family enabled (both
    candidates alike); a reverted family adds nothing."""
    return BASE_KEYS + [(f"x-{f}", MODULES[0]) for f in families if f in KEPT]


def _rows(config: str, keys: list[tuple[str, str]]) -> list[dict]:
    return [
        {
            "config": config,
            "claim_key": k,
            "module": m,
            "payload_sha256": f"p{k}",
            "raw": {"s": k},
            "hit_id": f"{config}:{k}",
        }
        for k, m in keys
    ]


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _n_hits(rows: list[dict]) -> dict:
    return {m: sum(r["module"] == m for r in rows) for m in MODULES}


def _frames(root: Path, step: str, configs: dict, snap_dir: Path, texts_sha: str) -> None:
    (root / "frames").mkdir(parents=True)
    snap = read_json(snap_dir / "CANDIDATE_SNAPSHOT.json")
    files = []
    for c, fams in configs.items():
        rows = _rows(c, _keys(fams))
        hits = root / "frames" / f"{c}.hits.jsonl"
        _write_rows(hits, rows)
        meta = root / "frames" / f"{c}.meta.json"
        write_json(
            meta,
            {
                "config": c,
                "enabled": fams,
                "import_root": str(snap_dir.resolve()),
                "texts_jsonl_sha256": texts_sha,
                "hits_sha256": sha256_file(hits),
                "n_hits": _n_hits(rows),
            },
        )
        files += [hits, meta]
    head = root / ("run.json" if step == "run" else "subsets.json")
    tree = {"tree_sha256": snap["tree_sha256"], "commit": snap["commit"]}
    key = "candidate_snapshot" if step == "run" else "snapshot"
    write_json(head, {"candidate_src": str(snap_dir.resolve()), key: tree})
    write_step_manifest(root, step, [head, *files])


def _remanifest(root: Path, step: str) -> None:
    """Rewrite a step manifest over its current files (a self-consistent rewrite)."""
    m = read_json(root / f"manifest_{step}.json")
    write_step_manifest(root, step, [root / rel for rel in m["outputs"] if (root / rel).exists()])


def _rewrite(root: Path, step: str, config: str, rows: list[dict]) -> None:
    """Replace a frame consistently: hits, its meta's hash and counts, and the manifest."""
    hits = root / "frames" / f"{config}.hits.jsonl"
    _write_rows(hits, rows)
    meta = read_json(root / "frames" / f"{config}.meta.json")
    meta |= {"hits_sha256": sha256_file(hits), "n_hits": _n_hits(rows)}
    write_json(root / "frames" / f"{config}.meta.json", meta)
    _remanifest(root, step)


def _fake_dryrun(tmp_path, monkeypatch, kept=KEPT):
    """A dry run whose candidate is commit B and whose comparison is commit A of a temporary
    repository: snapshots, both runs, both subset runs, the diff, the development round and
    the development manifest, every step manifested. Kept families change hits (alike for
    both candidates); the others change nothing."""
    repo, commits = _src_repo(tmp_path)
    _use_src_repo(monkeypatch, repo)
    out = tmp_path / "dr"
    cmp_dir = out / "compare"
    dev_texts = tmp_path / "dev_texts.jsonl"
    dev_rows = [{"text_id": "T001", "source_id": "s1"}, {"text_id": "T002", "source_id": "s2"}]
    dev_texts.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in dev_rows))
    (tmp_path / "texts").mkdir()  # the development texts beside their manifest
    for r in dev_rows:
        (tmp_path / "texts" / f"{r['text_id']}.txt").write_text(f"text {r['text_id']}\n")
    rd = out / "round_dev"
    (rd / "texts").mkdir(parents=True)
    rows = []
    for r in dev_rows:
        text = f"text {r['text_id']}\n"
        (rd / "texts" / f"{r['text_id']}.txt").write_text(text)
        rows.append(r | {"text_sha256": sha256_text(text)})
    (rd / "texts.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    texts_sha = sha256_file(rd / "texts.jsonl")
    _snapshot(repo, commits["B"], out / "candidate_src")
    _snapshot(repo, commits["A"], cmp_dir / "candidate_src")
    new_cfg = {"BASELINE": [], COMPLETE: list(FAMILIES)} | {f: [f] for f in FAMILIES}
    _frames(out / "run", "run", new_cfg, out / "candidate_src", texts_sha)
    cmp_cfg = {"BASELINE": []} | {f: [f] for f in kept}
    _frames(cmp_dir / "run", "run", cmp_cfg, cmp_dir / "candidate_src", texts_sha)
    subs = narrowing.kept_subsets(kept)
    _frames(out / "subsets", "subsets", subs, out / "candidate_src", texts_sha)
    _frames(cmp_dir / "subsets", "subsets", subs, cmp_dir / "candidate_src", texts_sha)
    frames = {}
    for f in FAMILIES:
        base, cand = _n_hits(_rows("x", BASE_KEYS)), _n_hits(_rows("x", _keys([f])))
        frames[f] = {
            m: {
                "N_baseline": base[m],
                "N_candidate": cand[m],
                "N_affected": 1 if f in kept and m == MODULES[0] else 0,
            }
            for m in MODULES
        }
    (out / "diff").mkdir()
    write_json(
        out / "diff" / "frames.json",
        {"run_json_sha256": sha256_file(out / "run" / "run.json"), "frames": frames},
    )
    write_step_manifest(out / "diff", "diff", [out / "diff" / "frames.json"])
    return out, cmp_dir, commits, dev_texts


def _identity(out, cmp_dir, commits, dev_texts, kept=KEPT, compare=None):
    return dryrun.kept_family_identity(
        out, cmp_dir, kept, compare or commits["A"], commits["B"], dev_texts
    )


LEDGER_SHA = "l" * 64


def _key_and_summary(out: Path, commits: dict) -> tuple[dict, dict]:
    key = {
        "commit": commits["B"],
        "harness_sha256": narrowing.harness_sha256(source_hashes()),
        "environment_sha256": "e" * 64,
        "settings": {
            "compare_candidate": commits["A"],
            "kept": KEPT,
            "ledger_md_sha256": LEDGER_SHA,
        },
    }
    summary = {
        "verify_ok": True,
        "ledger_ok": True,
        "blinding_ok": True,
        "verify_baseline": {"identical": True},
        "determinism": {
            "worker_frames_identical": {"BASELINE": True, COMPLETE: True},
            "steps_identical": {"diff": True, "sample": True, "assign": True},
        },
        "ledger_md_sha256": LEDGER_SHA,
    }
    write_json(out / "DRYRUN_KEY.json", key)
    write_json(out / "dryrun_summary.json", summary)
    return key, summary


def _want(commits: dict, dev_texts: Path) -> dict:
    """What a round-2 plan of candidate B after round 1's candidate A validates against."""
    a = freeze.commit_src_digest(commits["A"])
    b = freeze.commit_src_digest(commits["B"])
    return {
        "candidate": {"commit": b["commit"], "tree_sha256": b["tree_sha256"]},
        "round1_candidate": {"commit": a["commit"], "tree_sha256": a["tree_sha256"]},
        "ledger_md_sha256": LEDGER_SHA,
        "sources_sha256": source_hashes(),
        "dev_texts_sha256": sha256_file(dev_texts),
        "dev_round_texts_sha256": narrowing.dev_round_texts_sha256(dev_texts),
    }


def _canonical_dev_texts(ev: dict) -> None:
    """Relabel a synthetic dry run's evidence as run on the canonical development manifest
    (a production plan validates against it): the manifest's SHA-256 and, nested, the
    development round's texts.jsonl SHA-256 that manifest gives."""
    ev["dev_texts_jsonl_sha256"] = collect.build.DEV_TEXTS_SHA256
    ev["kept_family_identity"]["texts_jsonl_sha256"] = narrowing.dev_round_texts_sha256(
        collect.build.DEV_TEXTS
    )


def _nested(ev: dict, path: tuple, value) -> dict:
    """A deep copy of `ev` whose kept_family_identity has `value` at `path` (a missing key
    when value is _DROP)."""
    ev = json.loads(json.dumps(ev))
    d = ev["kept_family_identity"]
    for k in path[:-1]:
        d = d[k]
    if value is _DROP:
        d.pop(path[-1])
    else:
        d[path[-1]] = value
    return ev


_DROP = object()


def _nested_mutations(ev: dict, commits: dict) -> dict:
    """Audit r2 N1: the nested identities, missing or changed while the outer ones stay right,
    and booleans that contradict the counts beside them. -> case: (evidence, refusal text)."""
    k = ev["kept_family_identity"]
    nc = k["complete_equals_kept_union"]
    return {
        "nested_candidate_commit_changed": (
            _nested(ev, ("candidate_commit",), commits["C"]),
            "kept_family_identity's candidate_commit",
        ),
        "nested_candidate_commit_missing": (
            _nested(ev, ("candidate_commit",), _DROP),
            "kept_family_identity's candidate_commit None",
        ),
        "nested_candidate_tree_changed": (
            _nested(ev, ("candidate_tree_sha256",), "0" * 64),
            "kept_family_identity's candidate_tree_sha256",
        ),
        "nested_compare_commit_changed": (
            _nested(ev, ("compare_commit",), commits["C"]),
            "kept_family_identity's compare_commit",
        ),
        "nested_compare_commit_missing": (
            _nested(ev, ("compare_commit",), _DROP),
            "kept_family_identity's compare_commit None",
        ),
        "nested_compare_tree_changed": (
            _nested(ev, ("compare_tree_sha256",), "0" * 64),
            "kept_family_identity's compare_tree_sha256",
        ),
        "nested_compare_tree_missing": (
            _nested(ev, ("compare_tree_sha256",), ""),
            "kept_family_identity's compare_tree_sha256 ''",
        ),
        "nested_texts_changed": (
            _nested(ev, ("texts_jsonl_sha256",), "0" * 64),
            "kept_family_identity's texts_jsonl_sha256",
        ),
        "nested_texts_missing": (
            _nested(ev, ("texts_jsonl_sha256",), _DROP),
            "kept_family_identity's texts_jsonl_sha256 None",
        ),
        "contradictory_counts_match_rows": (
            _nested(ev, ("not_kept_frames", "MD-A", "counts_match_rows"), False),
            "MD-A: counts_match_rows is not true",
        ),
        "contradictory_reverted_baseline_rows": (
            _nested(
                ev, ("not_kept_frames", "MD-B", "rows", MODULES[0]), {"candidate": 7, "baseline": 7}
            ),
            "the baseline row count is not BASELINE's",
        ),
        "contradictory_complete_counts": (
            _nested(ev, ("complete_equals_kept_union",), nc | {"n_complete": nc["n_complete"] + 1}),
            "complete_equals_kept_union: the COMPLETE and kept-union hit counts",
        ),
    }


def _evidence(tmp_path, monkeypatch) -> tuple[dict, dict, Path, dict]:
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path, monkeypatch)
    key, summary = _key_and_summary(out, commits)
    ident = _identity(out, cmp_dir, commits, dev_texts)
    ev = dryrun.narrowing_evidence(out, key, ident, summary, dev_texts)
    return ev, _want(commits, dev_texts), out, commits


# --- finding 3: the comparison authenticates its inputs and covers every kept subset ------


def test_f3_kept_family_identity_ok_and_every_kept_combination(tmp_path, monkeypatch):
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path, monkeypatch)
    res = _identity(out, cmp_dir, commits, dev_texts)
    assert res["ok"] is True
    assert res["kept"] == KEPT and res["not_kept"] == REVERTED
    assert res["compare_commit"] == commits["A"] and res["candidate_commit"] == commits["B"]
    # 2^6 = 64 subsets of the kept switches: BASELINE, 6 singletons and these 57
    assert len(res["kept_subsets"]) == 57 == 64 - 1 - 6
    assert all(v["byte_equal"] for v in res["kept_subsets"].values())
    assert res["complete_equals_kept_union"]["identical"] is True
    assert all(
        v["zero_affected"] and v["counts_match_rows"] and v["identical_to_baseline"]
        for v in res["not_kept_frames"].values()
    )
    assert json.dumps(res)


def test_f3_kept_family_identity_parses_only_the_sequence_frames(tmp_path, monkeypatch):
    # the real frame sets (135 frames, about 7.6 GB) never fit in memory at once: the first
    # full round-2 dry runs were killed (exit 137) holding every parsed frame. Counts are
    # streamed; rows are parsed only for the sequence comparisons, BASELINE against each
    # reverted family and COMPLETE against the kept union (1 + 6 + 2 hit files)
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path, monkeypatch)
    real, parsed = dryrun.read_jsonl, []

    def spy(path):
        if str(path).endswith(".hits.jsonl"):
            parsed.append(Path(path).relative_to(out).as_posix())
        return real(path)

    monkeypatch.setattr(dryrun, "read_jsonl", spy)
    assert _identity(out, cmp_dir, commits, dev_texts)["ok"] is True
    union = f"subsets/frames/{narrowing.subset_config(KEPT)}.hits.jsonl"
    want = [f"run/frames/{c}.hits.jsonl" for c in ["BASELINE", *REVERTED, COMPLETE]] + [union]
    assert parsed == want


def _meta_edit(root: Path, step: str, config: str, **change) -> None:
    p = root / "frames" / f"{config}.meta.json"
    write_json(p, read_json(p) | change)
    _remanifest(root, step)


AUTH_FAULTS = {
    "comparison_meta_missing": "comparison run: run/frames/MD-D.meta.json differs from manifest_run",
    "comparison_kept_hits_missing": "comparison run: run/frames/PH-C.hits.jsonl differs from manifest_run",
    "comparison_manifest_missing": "missing",
    "stale_hits_against_manifest": "MD-H.hits.jsonl differs from manifest_run",
    "new_subset_missing": "differs from manifest_subsets",
    "wrong_comparison_commit": "not the requested",
    "missing_comparison_commit": "records no commit or no tree digest",
    "snapshot_bytes_changed": "bytes are not its recorded tree digest",
    "different_text_hashes": "ran on another text manifest",
    "inconsistent_counts": "counts are not the rows' counts",
    "meta_names_another_hit_file": "does not name its hit file",
    "meta_other_import_root": "did not import the snapshot",
    "diff_of_another_run": "frames.json is not of this run",
    "development_text_changed": "text bytes differ",
}


@pytest.mark.parametrize("fault", sorted(AUTH_FAULTS))
def test_f3_unauthenticated_inputs_refuse(tmp_path, monkeypatch, fault):
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path, monkeypatch)
    cr, nr = cmp_dir / "run", out / "run"
    compare = None
    if fault == "comparison_meta_missing":
        (cr / "frames" / "MD-D.meta.json").unlink()
    elif fault == "comparison_kept_hits_missing":  # test_r9's former kept_missing
        (cr / "frames" / "PH-C.hits.jsonl").unlink()
    elif fault == "comparison_manifest_missing":
        (cr / "manifest_run.json").unlink()
    elif fault == "stale_hits_against_manifest":
        _write_rows(cr / "frames" / "MD-H.hits.jsonl", _rows("MD-H", BASE_KEYS))
    elif fault == "new_subset_missing":
        (out / "subsets" / "frames" / f"{narrowing.subset_config(KEPT)}.hits.jsonl").unlink()
    elif fault == "wrong_comparison_commit":
        compare = commits["C"]  # round 1's tree under another commit id
    elif fault == "missing_comparison_commit":
        sp = cmp_dir / "candidate_src" / "CANDIDATE_SNAPSHOT.json"
        write_json(sp, {k: v for k, v in read_json(sp).items() if k != "commit"})
    elif fault == "snapshot_bytes_changed":
        (cmp_dir / "candidate_src" / "lexinspect" / "a.py").write_text("a = 3\n")
    elif fault == "different_text_hashes":
        _meta_edit(cr, "run", "PH-B", texts_jsonl_sha256="0" * 64)
    elif fault == "inconsistent_counts":
        _meta_edit(cr, "run", "BASELINE", n_hits={MODULES[0]: 999, MODULES[1]: 1})
    elif fault == "meta_names_another_hit_file":
        _meta_edit(nr, "run", "MD-A", hits_sha256="0" * 64)
    elif fault == "meta_other_import_root":
        _meta_edit(nr, "run", "PH-A", import_root=str(cmp_dir / "candidate_src"))
    elif fault == "diff_of_another_run":
        fj = read_json(out / "diff" / "frames.json") | {"run_json_sha256": "0" * 64}
        write_json(out / "diff" / "frames.json", fj)
        _remanifest(out / "diff", "diff")
    elif fault == "development_text_changed":
        (out / "round_dev" / "texts" / "T002.txt").write_text("changed\n")
    with pytest.raises(SystemExit) as e:
        _identity(out, cmp_dir, commits, dev_texts, compare=compare)
    msg = str(e.value)
    assert msg.startswith("kept-family identity inputs do not authenticate")
    assert AUTH_FAULTS[fault] in msg, msg


DIFFERENCES = (
    "kept_frame",
    "kept_combination",
    "baseline_frame",
    "reverted_affected",
    "reverted_counts_not_rows",
    "reverted_candidate_count",
    "reverted_sequence",
    "complete_not_kept_union",
)


@pytest.mark.parametrize("fault", DIFFERENCES)
def test_f3_authenticated_differences_make_ok_false(tmp_path, monkeypatch, fault):
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path, monkeypatch)
    cr, nr = cmp_dir / "run", out / "run"
    combo = narrowing.subset_config(["MD-D", "MD-I", "PH-C"])
    if fault == "kept_frame":
        _rewrite(cr, "run", "MD-H", _rows("MD-H", BASE_KEYS))
    elif fault == "kept_combination":  # only a combination differs; every singleton agrees
        _rewrite(cmp_dir / "subsets", "subsets", combo, _rows(combo, BASE_KEYS))
    elif fault == "baseline_frame":
        _rewrite(cr, "run", "BASELINE", _rows("BASELINE", BASE_KEYS[:2]))
    elif fault in ("reverted_affected", "reverted_counts_not_rows", "reverted_candidate_count"):
        fj = read_json(out / "diff" / "frames.json")
        c = fj["frames"]["MD-A"][MODULES[1]]
        if fault == "reverted_affected":
            c["N_affected"] = 1
        elif fault == "reverted_candidate_count":  # test_r9's former not_kept_count
            c["N_candidate"] = c["N_baseline"] + 1
        else:
            c["N_candidate"] = c["N_baseline"] = 7
        write_json(out / "diff" / "frames.json", fj)
        _remanifest(out / "diff", "diff")
    elif fault == "reverted_sequence":
        _rewrite(nr, "run", "MD-B", list(reversed(_rows("MD-B", BASE_KEYS))))
    else:  # a reverted family active only together with the kept families
        _rewrite(nr, "run", COMPLETE, _rows(COMPLETE, _keys(KEPT) + [("x-MD-E", MODULES[0])]))
    res = _identity(out, cmp_dir, commits, dev_texts)
    assert res["ok"] is False
    if fault == "kept_combination":
        assert all(v["byte_equal"] for v in res["kept_frames"].values())
        assert [n for n, v in res["kept_subsets"].items() if not v["byte_equal"]] == [combo]
    if fault == "reverted_sequence":
        assert res["not_kept_frames"]["MD-B"]["zero_affected"] is True
        assert res["not_kept_frames"]["MD-B"]["identical_to_baseline"] is False
    if fault == "reverted_counts_not_rows":
        assert res["not_kept_frames"]["MD-A"]["counts_match_rows"] is False
    if fault == "reverted_candidate_count":
        assert res["not_kept_frames"]["MD-A"]["zero_affected"] is False
    if fault == "complete_not_kept_union":
        assert res["complete_equals_kept_union"]["identical"] is False


def test_f3_narrowing_check_cli_exit_status(tmp_path, monkeypatch):
    ev, _, out, commits = _evidence(tmp_path, monkeypatch)
    write_json(out / narrowing.FILENAME, ev)
    dev_texts = tmp_path / "dev_texts.jsonl"
    monkeypatch.setattr(dryrun.build, "DEV_TEXTS", dev_texts)
    argv = ["narrowing-check", "--dryrun-dir", str(out)]
    assert cli.main(argv) == 0
    # a copy elsewhere (round2/NARROWING_CHECK.json) is checked the same way
    copy = tmp_path / "copy.json"
    shutil.copyfile(out / narrowing.FILENAME, copy)
    assert cli.main([*argv, "--evidence", str(copy)]) == 0
    # the evidence does not reproduce from the dry run's outputs
    write_json(copy, ev | {"kept_family_identity": ev["kept_family_identity"] | {"ok": False}})
    assert cli.main([*argv, "--evidence", str(copy)]) == 1
    write_json(copy, ev | {"harness_sha256": "0" * 64})
    assert cli.main([*argv, "--evidence", str(copy)]) == 1
    write_json(copy, ev | {"ok": False})
    assert cli.main([*argv, "--evidence", str(copy)]) == 1
    # an authenticated difference: the recomputed identity is not ok
    combo = narrowing.subset_config(["MD-H", "PH-A"])
    sub = out / "compare" / "subsets"
    _rewrite(sub, "subsets", combo, _rows(combo, BASE_KEYS))
    assert cli.main(argv) == 1
    # stale data against an existing manifest: refused (SystemExit, a nonzero exit)
    _write_rows(out / "compare" / "run" / "frames" / "MD-D.hits.jsonl", _rows("MD-D", BASE_KEYS))
    with pytest.raises(SystemExit, match="do not authenticate"):
        cli.main(argv)
    # missing comparison metadata
    (out / "compare" / "run" / "frames" / "PH-A.meta.json").unlink()
    with pytest.raises(SystemExit, match="do not authenticate"):
        cli.main(argv)


def test_f3_narrowing_check_process_exit_status(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    r = subprocess.run(
        [sys.executable, "-I", str(HERE / "cli.py"), "narrowing-check", "--dryrun-dir", str(empty)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "narrowing check refused" in r.stderr


def test_f3_dryrun_runs_every_combination_for_both_candidates_and_writes_the_evidence():
    src = inspect.getsource(dryrun.main)
    assert 'run_subsets(out / "subsets", cand, rd, kept, args.jobs)' in src
    assert 'run_subsets(cmp_dir / "subsets", csrc, rd, kept, args.jobs)' in src
    assert "kept_family_identity(out, cmp_dir, kept, compare_commit," in src
    assert "write_json(out / NC.FILENAME, evidence)" in src
    assert 'ok = ok and (evidence is None or evidence["ok"])' in src
    # the comparison commit is resolved before the resume settings
    assert src.index("FZ.full_commit(args.compare_candidate)") < src.index('"compare_candidate"')
    # and never rebound afterwards (the first r2 dry run crashed: main's verify `compare`
    # list shadowed the comparison commit given to prepare-candidate)
    tree = ast.parse(textwrap.dedent(src))
    bound = [
        ast.unparse(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "compare_commit" for t in n.targets)
    ]
    assert bound == ["None", "FZ.full_commit(args.compare_candidate)"]
    stores = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and n.id == "compare_commit" and isinstance(n.ctx, ast.Store)
    ]
    assert len(stores) == 2


# --- finding 1: the narrowing check's validation ----------------------------------------


def test_f1_evidence_is_counts_and_hashes_and_validates(tmp_path, monkeypatch):
    ev, want, _, _ = _evidence(tmp_path, monkeypatch)
    assert narrowing.problems(ev, **want) == []
    assert ev["ok"] is True and ev["kept"] == KEPT and ev["not_kept"] == REVERTED

    def strings(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from strings(v)
        elif isinstance(x, list):
            for v in x:
                yield from strings(v)
        elif isinstance(x, str):
            yield x

    seen = list(strings(ev))
    assert not [s for s in seen if s.startswith("/")]  # no paths
    for k in ("raw", "payload", "context", "claim_key", "marker", "text"):
        assert k not in seen  # never a hit, a context or a PHRASE list entry


def _mutations(ev: dict, commits: dict) -> dict:
    k = ev["kept_family_identity"]
    subs = dict(k["kept_subsets"])
    name = sorted(subs)[0]
    subs[name] = subs[name] | {"byte_equal": False}
    fewer = dict(subs)
    fewer.pop(name)
    nk = json.loads(json.dumps(k["not_kept_frames"]))
    nk["MD-C"]["modules"][MODULES[0]]["N_affected"] = 2
    rows = json.loads(json.dumps(k["not_kept_frames"]))
    rows["MD-E"]["rows"][MODULES[1]]["candidate"] = 99
    return {
        "ok_false": (ev | {"ok": False}, "the narrowing check's ok is not true"),
        "identity_ok_false": (
            ev | {"kept_family_identity": k | {"ok": False}},
            "kept_family_identity.ok is not true",
        ),
        "wrong_compare_commit": (ev | {"compare_commit": commits["C"]}, "compare_commit"),
        "wrong_compare_tree": (ev | {"compare_tree_sha256": "0" * 64}, "compare_tree_sha256"),
        "wrong_candidate_commit": (ev | {"candidate_commit": commits["A"]}, "candidate_commit"),
        "wrong_candidate_tree": (ev | {"candidate_tree_sha256": "0" * 64}, "candidate_tree"),
        "wrong_kept_list": (
            ev | {"kept": ["MD-A", *KEPT[1:]]},
            "the narrowing check's kept families",
        ),
        "wrong_reverted_list": (ev | {"not_kept": REVERTED[:-1]}, "reverted families"),
        "other_ledger": (ev | {"ledger_md_sha256": "0" * 64}, "ledger_md_sha256"),
        "other_harness": (ev | {"harness_sha256": "0" * 64}, "not produced by this harness"),
        "other_dev_texts": (ev | {"dev_texts_jsonl_sha256": "0" * 64}, "development manifest"),
        "dryrun_check_failed": (
            ev | {"dryrun": ev["dryrun"] | {"checks": ev["dryrun"]["checks"] | {"verify_ok": 0}}},
            "did not pass ['verify_ok']",
        ),
        "kind": (ev | {"kind": "x"}, "is not a fixcheck-narrowing-check"),
        "subset_not_equal": (
            ev | {"kept_family_identity": k | {"kept_subsets": subs}},
            f"{name}: the two candidates'",
        ),
        "subset_missing": (
            ev | {"kept_family_identity": k | {"kept_subsets": fewer}},
            "kept-family combinations, not the 57",
        ),
        "reverted_active": (
            ev | {"kept_family_identity": k | {"not_kept_frames": nk}},
            "MD-C metadiscourse: not inactive",
        ),
        "reverted_rows": (
            ev | {"kept_family_identity": k | {"not_kept_frames": rows}},
            "MD-E phrase: the frame counts are not the rows' counts",
        ),
        "complete": (
            ev | {"kept_family_identity": k | {"complete_equals_kept_union": {"identical": False}}},
            "COMPLETE is not the six kept families together",
        ),
        "baseline": (
            ev
            | {"kept_family_identity": k | {"baseline": k["baseline"] | {"compare_sha256": "x"}}},
            "BASELINE: the two candidates'",
        ),
    }


def test_f1_every_field_is_validated_not_only_ok(tmp_path, monkeypatch):
    ev, want, _, commits = _evidence(tmp_path, monkeypatch)
    for case, (bad, needle) in (_mutations(ev, commits) | _nested_mutations(ev, commits)).items():
        probs = narrowing.problems(bad, **want)
        assert probs and any(needle in x for x in probs), (case, probs)
    # the development round must be the one the manifest gives (not merely nonempty)
    probs = narrowing.problems(ev, **(want | {"dev_round_texts_sha256": None}))
    assert any("kept_family_identity's texts_jsonl_sha256" in x for x in probs), probs
    # a bare ok flag is never enough
    assert narrowing.problems({"ok": True}, **want)
    assert narrowing.file_problems(None, **want) == ["no narrowing check (--narrowing-check)"]
    assert "is missing" in narrowing.file_problems(tmp_path / "none.json", **want)[0]
    (tmp_path / "bad.json").write_text("{")
    assert "not readable JSON" in narrowing.file_problems(tmp_path / "bad.json", **want)[0]


# --- finding 1: the production plan refuses before the reservation ----------------------


def _production_round2(tmp_path, monkeypatch, case: str):
    """A production round-2 plan of candidate B (round 1: candidate A, registered) whose
    prerequisites other than the narrowing check are taken as met: freeze.
    production_prerequisites is narrowed to the narrowing-check reasons, so an otherwise
    valid plan reaches the reservation (collect._reserve, stubbed)."""
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path / "d", monkeypatch)
    repo = freeze.REPO
    dev_raw, raw, r1 = _round1(tmp_path)
    tree_a = freeze.commit_src_digest(commits["A"])["tree_sha256"]
    reg = _r1_registry(tmp_path / "reg.jsonl", r1, cand=commits["A"], tree=tree_a)
    l2 = _ledger_copy(repo / "docs" / "round2" / "CANDIDATE_LEDGER.md")
    key, summary = _key_and_summary(out, commits)
    key["settings"]["ledger_md_sha256"] = summary["ledger_md_sha256"] = sha256_file(l2)
    ident = _identity(out, cmp_dir, commits, dev_texts)
    ev = dryrun.narrowing_evidence(out, key, ident, summary, dev_texts)
    _canonical_dev_texts(ev)
    if case in _MUTATE:
        ev = _MUTATE[case](ev, commits)
    if case in NESTED_REFUSALS:
        ev = _nested_mutations(ev, commits)[case][0]
    nc = repo / ("docs" if case != "ignored" else ".cache") / "round2" / "NARROWING_CHECK.json"
    nc.parent.mkdir(parents=True, exist_ok=True)
    write_json(nc, ev)
    disp = repo / "docs" / "round2" / "NARROWING_DISPOSITION.md"
    disp.write_text(
        f"# Narrowing\n\n**Status:** FINAL\n\nCandidate {commits['B']}.\n\n"
        f"Narrowing check SHA-256 {sha256_file(nc)}.\n"
    )
    orig = freeze.production_prerequisites
    monkeypatch.setattr(
        freeze,
        "production_prerequisites",
        lambda rec: [r for r in orig(rec) if "narrowing check" in r],
    )
    reserved: list = []

    def reserve(args):
        reserved.append(args.round)
        raise _Stop

    monkeypatch.setattr(collect, "_reserve", reserve)
    if case == "ledger_changed_after_the_dry_run":
        l2.write_text(l2.read_text() + "\nedited after the dry run\n")
    if case == "harness_changed_after_the_dry_run":
        real = collect.source_hashes
        monkeypatch.setattr(collect, "source_hashes", lambda: real() | {"fixcheck/new.py": "0"})
    if case == "evidence_changed_after_the_disposition":
        write_json(nc, ev | {"note": "edited"})
    extra = ["--candidate-commit", commits["B"], "--narrowing-disposition", str(disp)]
    extra += ["--ledger-md", str(l2)]
    if case != "missing":
        extra += ["--narrowing-check", str(nc)]
    argv = _r2(tmp_path, tmp_path / "p2" / "raw", dev_raw, r1, reg, *extra, dry=False)
    return argv, reg, reserved


_MUTATE = {
    "ok_false": lambda ev, c: ev | {"ok": False},
    "wrong_comparison_commit": lambda ev, c: ev | {"compare_commit": c["C"]},
    "wrong_candidate": lambda ev, c: ev | {"candidate_commit": c["C"]},
    "wrong_tree": lambda ev, c: ev | {"candidate_tree_sha256": "0" * 64},
    "wrong_kept_list": lambda ev, c: ev | {"kept": KEPT[:-1], "not_kept": [*REVERTED, KEPT[-1]]},
}
PLAN_REFUSALS = {
    "missing": "round 2 needs the final dry run's development-text narrowing check",
    "ok_false": "the narrowing check's ok is not true",
    "wrong_comparison_commit": "compare_commit",
    "wrong_candidate": "is not the round-2 candidate commit",
    "wrong_tree": "is not the round-2 candidate tree",
    "wrong_kept_list": "the narrowing check's kept families",
    "ledger_changed_after_the_dry_run": "ledger_md_sha256",
    "harness_changed_after_the_dry_run": "not produced by this harness",
    "evidence_changed_after_the_disposition": "does not name the narrowing check's SHA-256",
    "ignored": "the narrowing check is git-ignored",
}


# audit r2 N1: the nested identities and contradictory booleans (_nested_mutations)
NESTED_REFUSALS = {
    "nested_candidate_commit_changed": "kept_family_identity's candidate_commit",
    "nested_candidate_commit_missing": "kept_family_identity's candidate_commit None",
    "nested_candidate_tree_changed": "kept_family_identity's candidate_tree_sha256",
    "nested_compare_commit_changed": "kept_family_identity's compare_commit",
    "nested_compare_commit_missing": "kept_family_identity's compare_commit None",
    "nested_compare_tree_changed": "kept_family_identity's compare_tree_sha256",
    "nested_compare_tree_missing": "kept_family_identity's compare_tree_sha256 ''",
    "nested_texts_changed": "kept_family_identity's texts_jsonl_sha256",
    "nested_texts_missing": "kept_family_identity's texts_jsonl_sha256 None",
    "contradictory_counts_match_rows": "MD-A: counts_match_rows is not true",
    "contradictory_reverted_baseline_rows": "the baseline row count is not BASELINE's",
    "contradictory_complete_counts": "the COMPLETE and kept-union hit counts",
}


@pytest.mark.parametrize("case", sorted(PLAN_REFUSALS | NESTED_REFUSALS))
def test_f1_production_plan_refuses_before_the_reservation(tmp_path, monkeypatch, case):
    argv, reg, reserved = _production_round2(tmp_path, monkeypatch, case)
    before = reg.read_bytes()
    with pytest.raises(SystemExit) as e:
        collect.main(argv)
    msg = str(e.value)
    needle = (PLAN_REFUSALS | NESTED_REFUSALS)[case]
    assert msg.startswith("not a production freeze") and needle in msg, msg
    assert reserved == [] and reg.read_bytes() == before
    assert not (tmp_path / "r2" / "freeze_record.json").exists()


def test_f1_production_plan_with_valid_evidence_reaches_the_reservation(tmp_path, monkeypatch):
    argv, reg, reserved = _production_round2(tmp_path, monkeypatch, "valid")
    with pytest.raises(_Stop):
        collect.main(argv)
    assert reserved == [2]


def _no_collector(monkeypatch):
    def reached(*a, **k):
        raise AssertionError("the collector was reached")

    monkeypatch.setattr(collect, "_collect_round", reached)


def _dry_plan_with_evidence(tmp_path, monkeypatch, l1=None):
    """A dry-run round-2 plan binding a valid narrowing check (and, with l1, a round 1 whose
    ledger is the copy l1). Returns (record, execution argv, evidence path, round-1 dir)."""
    out, cmp_dir, commits, dev_texts = _fake_dryrun(tmp_path / "d", monkeypatch)
    repo = freeze.REPO
    extra1 = ("--ledger-md", str(l1)) if l1 else ()
    dev_raw, raw, r1 = _round1(tmp_path, extra=extra1)
    tree_a = freeze.commit_src_digest(commits["A"])["tree_sha256"]
    reg = _r1_registry(tmp_path / "reg.jsonl", r1, cand=commits["A"], tree=tree_a)
    l2 = _ledger_copy(repo / "docs" / "round2" / "CANDIDATE_LEDGER.md")
    key, summary = _key_and_summary(out, commits)
    key["settings"]["ledger_md_sha256"] = summary["ledger_md_sha256"] = sha256_file(l2)
    ev = dryrun.narrowing_evidence(
        out, key, _identity(out, cmp_dir, commits, dev_texts), summary, dev_texts
    )
    _canonical_dev_texts(ev)
    nc = repo / "docs" / "round2" / "NARROWING_CHECK.json"
    write_json(nc, ev)
    disp = repo / "docs" / "round2" / "NARROWING_DISPOSITION.md"
    disp.write_text(f"**Status:** FINAL\n\n{commits['B']}\n\n{sha256_file(nc)}\n")
    extra = ["--candidate-commit", commits["B"], "--narrowing-disposition", str(disp)]
    extra += ["--ledger-md", str(l2), "--narrowing-check", str(nc)]
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, *extra)) == 0
    rec = read_json(tmp_path / "r2" / "freeze_record.json")
    return rec, rec["execution_argv"][4:], nc, r1


def test_f1_bound_in_the_freeze_receipted_and_rebuilt_at_execution(tmp_path, monkeypatch):
    rec, ex, nc, _ = _dry_plan_with_evidence(tmp_path, monkeypatch)
    _no_collector(monkeypatch)  # after round 1's own collection
    bound = rec["round2"]["narrowing_check"]
    assert bound["sha256"] == sha256_file(nc) and bound["problems"] == []
    assert rec["round2"]["narrowing_disposition"]["names_narrowing_check"] is True
    assert not [r for r in rec["ineligible_reasons"] if "narrowing" in r]
    paths = freeze.receipt_paths(tmp_path / "r2" / "freeze_record.json", rec)
    assert nc.resolve() in [Path(p).resolve() for p in paths]
    good = nc.read_bytes()
    write_json(nc, read_json(nc) | {"ok": False})  # changed after the plan
    with pytest.raises(SystemExit, match="execution does not match the freeze record.*round2"):
        collect.main(ex)
    nc.write_bytes(good)
    with pytest.raises(AssertionError, match="the collector was reached"):
        collect.main(ex)  # unchanged: the execution proceeds to collection


def test_f1_f2_round2_package_chain_problems(tmp_path, monkeypatch):
    l1 = _ledger_copy(tmp_path / "led" / "round1.md")
    rec, _, nc, r1 = _dry_plan_with_evidence(tmp_path, monkeypatch, l1=l1)
    assert package.round2_chain_problems(rec, rec["paths"]) == []
    good = nc.read_bytes()
    nc.write_text(nc.read_text() + "\n")
    [p] = package.round2_chain_problems(rec, rec["paths"])
    assert "differs from the freeze record's" in p
    nc.write_bytes(good)
    fr = json.loads(json.dumps(rec))
    fr["sources_sha256"]["fixcheck/new.py"] = "0"  # a harness other than the evidence's
    probs = package.round2_chain_problems(fr, fr["paths"])
    assert any("not produced by this harness" in p for p in probs)
    l1.write_text(l1.read_text() + "\nedited after round 2's plan\n")
    probs = package.round2_chain_problems(rec, rec["paths"])
    assert any(p.startswith("round 1 preservation: round 1's ledger Markdown") for p in probs)


def _rebind(rec: dict, nc: Path, ev: dict) -> dict:
    """A freeze record binding `ev` written at `nc` (as if a plan had bound it), so that
    acceptance validates the evidence itself rather than refusing its changed bytes."""
    write_json(nc, ev)
    fr = json.loads(json.dumps(rec))
    fr["round2"]["narrowing_check"]["sha256"] = sha256_file(nc)
    return fr


def test_n1_package_validation_refuses_nested_identities_and_contradictions(tmp_path, monkeypatch):
    # audit r2 N1: at acceptance, the bound evidence's nested result must name the round's
    # candidate and comparison and the development round, and its booleans must agree
    rec, _, nc, _ = _dry_plan_with_evidence(tmp_path, monkeypatch)
    good = read_json(nc)
    assert package.round2_chain_problems(_rebind(rec, nc, good), rec["paths"]) == []
    for case, (bad, needle) in _nested_mutations(good, {"C": "f" * 40}).items():
        probs = package.round2_chain_problems(_rebind(rec, nc, bad), rec["paths"])
        assert any(x.startswith("narrowing check: ") and needle in x for x in probs), (case, probs)
    # the development manifest the freeze record names gives another development round
    fr = _rebind(rec, nc, good)
    other = tmp_path / "otherdev"
    (other / "texts").mkdir(parents=True)
    rows = read_jsonl(Path(rec["paths"]["dev_texts"]))[:1]
    (other / "texts.jsonl").write_text(json.dumps(rows[0], sort_keys=True) + "\n")
    (other / "texts" / f"{rows[0]['text_id']}.txt").write_text("other\n")
    fr["paths"] = fr["paths"] | {"dev_texts": str(other / "texts.jsonl")}
    probs = package.round2_chain_problems(fr, fr["paths"])
    assert any("kept_family_identity's texts_jsonl_sha256" in x for x in probs), probs


# --- finding 2: round 1's receipted files, at planning and after execution ----------------


def test_f2_dry_run_round1_command_and_plan_manifest_refuse_round2_planning(tmp_path):
    dev_raw, raw, r1 = _round1(tmp_path)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    before = reg.read_bytes()
    cmd, man = r1 / "command.txt", r1 / "manifest_plan.json"
    good_cmd, good_man = cmd.read_bytes(), man.read_bytes()
    cases = (
        (lambda: cmd.write_text(cmd.read_text() + " --edited\n"), "command.txt differs"),
        (lambda: cmd.unlink(), "receipted command.txt"),
        (lambda: man.unlink(), "receipted manifest_plan.json"),
    )
    for i, (alter, needle) in enumerate(cases):
        alter()
        with pytest.raises(SystemExit, match="round 1's bound and receipted files") as e:
            collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, out=f"r2_{i}"))
        assert needle in str(e.value), str(e.value)
        assert reg.read_bytes() == before
        cmd.write_bytes(good_cmd)
        man.write_bytes(good_man)
    assert collect.main(_r2(tmp_path, raw, dev_raw, r1, reg, out="r2_ok")) == 0


def _receipted_round1(tmp_path, monkeypatch):
    """A production round 1 in a temporary repository: its plan files, one reviewed harness
    source, one frozen input, committed and on a receipt ref; the start record holds the
    archive receipt its execution gate checked."""
    repo = tmp_path / "rrepo"
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    d = repo / "docs" / "r1" / "collect"
    d.mkdir(parents=True)
    write_json(d / "freeze_record.json", {"production_eligible": True, "round": 1})
    (d / "command.txt").write_text("cd x && fixcheck collect --execute\n")
    write_json(d / "manifest_plan.json", {"outputs": {}})
    harness = repo / collect.HARNESS_RECEIPT_PREFIX / "x.py"
    harness.parent.mkdir(parents=True)
    harness.write_text("x = 1\n")
    frozen = harness.parent.parent / "build.py"
    frozen.write_text("b = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "round 1")
    _git(repo, "remote", "add", "origin", "https://example.org/r.git")
    _git(repo, "update-ref", "refs/remotes/origin/b", "HEAD")
    monkeypatch.setattr(freeze, "REPO", repo)
    files = [d / "freeze_record.json", d / "command.txt", d / "manifest_plan.json"]

    def start(paths=files + [harness, frozen], **change):
        receipt = freeze.archive_receipt(paths, repo, "refs/remotes/origin/b") | change
        p = d / collect.EXEC_START
        if p.exists():
            p.unlink()
        write_json(p, {"kind": collect.START_KIND, "gate": {"ok": True, "receipt": receipt}})
        return receipt

    assert start()["ok"] is True
    return d, harness, frozen, start


def test_f2_production_round1_receipt_is_revalidated(tmp_path, monkeypatch):
    d, harness, frozen, start = _receipted_round1(tmp_path, monkeypatch)
    probs = collect.round1_preservation_problems
    assert probs(d) == []
    harness.write_text("x = 2\n")  # a reviewed round-2 harness change: exempt
    assert probs(d) == []
    harness.write_text("x = 1\n")
    frozen.write_text("b = 2\n")  # a frozen input: compared
    assert any("build.py: changed since the receipt" in p for p in probs(d))
    frozen.write_text("b = 1\n")
    for name in ("command.txt", "manifest_plan.json"):
        f = d / name
        good = f.read_bytes()
        f.write_bytes(good + b" ")
        p = probs(d)
        assert any(f"receipted docs/r1/collect/{name} is missing or changed" in x for x in p), p
        f.unlink()
        assert any(f"receipted {name} {f.resolve()} is missing" in x for x in probs(d))
        f.write_bytes(good)
    assert probs(d) == []
    # the receipt must have held, list the plan files, and name the committed blobs
    start(ok=False)
    assert any("did not hold when it was made" in p for p in probs(d))
    start(paths=[d / "freeze_record.json", d / "command.txt"])
    assert any("manifest_plan.json: not covered by the receipt" in p for p in probs(d))
    r = start()
    rel = "docs/r1/collect/command.txt"
    start(files=r["files"] | {rel: r["files"][rel] | {"sha256": "0" * 64}})
    got = probs(d)
    assert any(f"{rel}: not the committed blob named by the receipt" in p for p in got), got
    (d / collect.EXEC_START).unlink()
    assert any("execution receipt is unavailable" in p for p in probs(d))


def test_f2_round1_ledger_altered_after_round2_execution_is_a_package_problem(tmp_path):
    l1 = _ledger_copy(tmp_path / "led" / "round1.md")
    dev_raw, raw, r1 = _round1(tmp_path, extra=("--ledger-md", str(l1)))
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    l2 = _ledger_copy(tmp_path / "led" / "round2.md")
    argv = [a for a in _r2(tmp_path, raw, dev_raw, r1, reg, "--ledger-md", str(l2)) if a]
    argv.remove("--plan-only")  # one-step dry run: plan and execute
    assert collect.main(argv) == 2  # the small mock pool runs short; the round is collected
    P = {"collect": tmp_path / "r2"}

    def preservation():
        return [p for p in package.check_collect(P)[0] if "round 1 preservation" in p]

    assert preservation() == []
    l1.write_text(l1.read_text() + "\nedited after round 2's execution\n")
    [p] = preservation()
    assert "round 1's ledger Markdown" in p and "has changed" in p
    shutil.copyfile(collect.LEDGER_MD, l1)
    assert preservation() == []
    (r1 / "command.txt").write_text("edited\n")
    assert any("command.txt differs" in p for p in preservation())


def _chain_problems(tmp_path, monkeypatch, kind: str) -> list[str]:
    """Problems that check_package actually reports for a round-2 package with a broken
    chain: the bound narrowing check changed after the plan, or round 1's ledger changed
    after round 2's plan (round 1 preservation). Every other link is taken as clean, so the
    list is exactly what the frozen accept.main passes to the acceptance calculation
    (`problems = list(chk["problems"])`)."""
    from fixcheck import freeze as FZ

    l1 = _ledger_copy(tmp_path / "led" / "round1.md")
    rec, _, nc, _ = _dry_plan_with_evidence(tmp_path, monkeypatch, l1=l1)
    if kind == "narrowing":
        write_json(nc, read_json(nc) | {"ok": False})
    else:
        l1.write_text(l1.read_text() + "\nedited after round 2's plan\n")
    pkg = tmp_path / "pkg"
    pkg.mkdir()

    def collect_link(P):
        return package.round2_chain_problems(rec, rec["paths"]), {"freeze_record": rec}

    monkeypatch.setattr(package, "check_collect", collect_link)
    for name in (
        "check_replay",
        "check_candidate",
        "check_run",
        "check_diff",
        "check_sample",
        "check_assign",
        "check_verify",
        "check_ledger",
    ):
        monkeypatch.setattr(package, name, lambda *a, **k: [])
    monkeypatch.setattr(package, "check_labels", lambda *a, **k: ([], {}))
    monkeypatch.setattr(
        FZ, "acceptance_runtime", lambda: {"environment": {}, "environment_sha256": "e" * 64}
    )
    monkeypatch.setattr(FZ, "runtime_problems", lambda *a: [])
    chk = package.check_package(pkg)
    assert chk["production_eligible"] is False
    assert chk["problems"] and all(x.startswith("[collect] ") for x in chk["problems"])
    want = "narrowing check" if kind == "narrowing" else "round 1 preservation"
    assert any(want in x for x in chk["problems"]), chk["problems"]
    return chk["problems"]


def _labels(breach: bool):
    """Synthetic labels (test_fixcheck._round): otherwise passing, or with a removal breach
    certificate (2 definite successes among 10 deletions, 2/10 > .15)."""
    from fixcheck import crosswalk as X
    from fixcheck.test_fixcheck import _round

    cells = (
        {X.REMOVED: (10, {f"r{i}": (1 if i < 2 else 0, []) for i in range(10)})}
        if breach
        else {
            X.REMOVED: (3, {"a": (0, []), "b": (0, []), "c": (0, [])}),
            X.REASSIGNED: (2, {"d": (1, [(1, True)]), "e": (0, [(1, True)])}),
        }
    )
    return _round(cells, bs_md={"s1": (100, [1] * 100)}, bs_ph={"t1": (50, [1] * 50)})


@pytest.mark.parametrize("kind", ["narrowing", "preservation"])
def test_n2_chain_problem_with_otherwise_passing_labels_is_inconclusive(
    tmp_path, monkeypatch, kind
):
    from fixcheck import accept

    frames, bs, refs, configs = _labels(breach=False)
    assert accept.compute(frames, bs, refs, configs, rnd=2)["status"] == "pass"  # control
    probs = _chain_problems(tmp_path, monkeypatch, kind)
    res = accept.compute(frames, bs, refs, configs, rnd=2, procedure_problems=probs)
    assert res["status"] == "inconclusive" and res["procedure_problems"] == probs
    assert (
        accept.decision_entry(
            {"collection": {"round": 2}, "inputs_sha256": "i" * 64}, res["status"]
        )["status"]
        == "inconclusive"
    )


@pytest.mark.parametrize("kind", ["narrowing", "preservation"])
def test_n2_chain_problem_with_breach_labels_is_inconclusive(tmp_path, monkeypatch, kind):
    """Clarifications 3.4 ("Incomplete procedure"): a detected chain problem makes the
    result inconclusive even when the labels give a breach certificate (accept.py amended
    after audit r2 N2; HARNESS_ROUND2_RULINGS.md)."""
    from fixcheck import accept

    frames, bs, refs, configs = _labels(breach=True)
    assert accept.compute(frames, bs, refs, configs, rnd=2)["status"] == "fail"  # control
    probs = _chain_problems(tmp_path, monkeypatch, kind)
    res = accept.compute(frames, bs, refs, configs, rnd=2, procedure_problems=probs)
    assert res["status"] == "inconclusive", res["status"]
    assert {m: v["status"] for m, v in res["modules"].items()} == {
        "metadiscourse": "inconclusive",
        "phrase": "inconclusive",
    }
    assert res["procedure_problems"] == probs
    entry = accept.decision_entry(
        {"collection": {"round": 2}, "inputs_sha256": "i" * 64}, res["status"]
    )
    assert entry["status"] == "inconclusive"


@pytest.mark.parametrize("kind", ["narrowing", "preservation"])
def test_n2_inconclusive_still_reports_the_breach_certificates(tmp_path, monkeypatch, kind):
    """With procedure problems and breach labels the record still shows what the labels
    said: the certificate detection and every bound are unchanged by the problems."""
    from fixcheck import accept

    frames, bs, refs, configs = _labels(breach=True)
    control = accept.compute(frames, bs, refs, configs, rnd=2)
    probs = _chain_problems(tmp_path, monkeypatch, kind)
    res = accept.compute(frames, bs, refs, configs, rnd=2, procedure_problems=probs)
    md = res["modules"]["metadiscourse"]
    assert md["breach_certificates"] == ["removal COMPLETE"]
    assert md["removal"]["COMPLETE"]["breach_certificate"] is True
    for m in res["modules"]:
        for part in ("removal", "loss", "success", "cumulative"):
            assert res["modules"][m][part] == control["modules"][m][part]
        assert (
            res["modules"][m]["breach_certificates"] == control["modules"][m]["breach_certificates"]
        )
    assert res["components"] == control["components"]
    assert "## Procedure problems" in accept.to_markdown(res)


def test_n2_problem_found_in_a_later_module_makes_every_module_inconclusive():
    """A problem the calculation finds only in the phrase module (checked after
    metadiscourse) still makes metadiscourse, which has a breach certificate, inconclusive."""
    from fixcheck import accept
    from fixcheck import crosswalk as X
    from fixcheck.test_fixcheck import _round

    frames, bs, refs, configs = _round(
        {X.REMOVED: (10, {f"r{i}": (1 if i < 2 else 0, []) for i in range(10)})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
        ph_removed=(300, [0, 0, 0, 0, 0]),  # n 5 != min(200, N 300): a phrase-only problem
    )
    res = accept.compute(frames, bs, refs, configs, rnd=2)
    assert res["procedure_problems"] and all("phrase" in p for p in res["procedure_problems"])
    assert res["modules"]["metadiscourse"]["breach_certificates"] == ["removal COMPLETE"]
    assert res["modules"]["metadiscourse"]["status"] == "inconclusive"
    assert res["modules"]["phrase"]["status"] == "inconclusive"
    assert res["status"] == "inconclusive"


# --- finding 4: the raw cache is disjoint, link-free and fresh -----------------------------


def test_f4_overlapping_or_linked_caches_are_refused(tmp_path):
    dev_raw, raw, r1 = _round1(tmp_path)  # round 1's cache tmp/p1/raw, private dir tmp/p1
    refuse = collect.refuse_unsafe_raw_cache
    link = tmp_path / "link"
    link.symlink_to(raw)
    with pytest.raises(SystemExit, match="is the raw cache of the earlier round"):
        refuse(link, [r1])  # equal via a symbolic link
    for overlap in (raw / "round2", raw.parent, tmp_path):  # descendant, ancestors
        with pytest.raises(SystemExit, match="disjoint from round 1's cache"):
            refuse(overlap, [r1])
    with pytest.raises(SystemExit, match="inside the earlier round's private directory"):
        refuse(raw.parent / "round2raw", [r1])
    linked = tmp_path / "p2" / "raw"
    linked.mkdir(parents=True)
    (linked / "epmc").symlink_to(raw / "epmc")
    with pytest.raises(SystemExit, match="links into the earlier round's preserved material"):
        refuse(linked, [r1])
    (linked / "epmc").unlink()
    (linked / "epmc").symlink_to(raw.parent / "elsewhere")  # into the private directory
    with pytest.raises(SystemExit, match="links into the earlier round's preserved material"):
        refuse(linked, [r1])
    (linked / "epmc").unlink()
    refuse(linked, [r1])  # a fresh sibling cache
    refuse(tmp_path / "p3" / "raw", [r1])  # not yet created


def test_f4_production_plan_needs_a_fresh_cache(tmp_path):
    dev_raw, raw, r1 = _round1(tmp_path)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    before = reg.read_bytes()
    l2 = _ledger_copy(tmp_path / "led" / "round2.md")
    copied = tmp_path / "p2" / "raw"
    shutil.copytree(raw / "epmc", copied / "epmc")  # round 1's bodies at a distinct root
    argv = _r2(tmp_path, copied, dev_raw, r1, reg, "--ledger-md", str(l2), dry=False)
    with pytest.raises(SystemExit, match="is not fresh"):
        collect.main(argv)
    assert not (copied / "pools").exists() and reg.read_bytes() == before
    # only byte-equal frozen pool listings: fresh; a changed listing is not
    shutil.rmtree(copied / "epmc")
    shutil.copytree(dev_raw / "pools", copied / "pools")
    collect.refuse_used_raw_cache(copied, dev_raw)
    listing = next(iter(sorted((copied / "pools").glob("*.json"))))
    listing.write_text(listing.read_text() + " ")
    with pytest.raises(SystemExit, match="is not fresh"):
        collect.refuse_used_raw_cache(copied, dev_raw)
    # a new cache passes every G5 check; the plan then stops on other prerequisites
    fresh = tmp_path / "p3" / "raw"
    argv = _r2(tmp_path, fresh, dev_raw, r1, reg, "--ledger-md", str(l2), out="r2b", dry=False)
    with pytest.raises(SystemExit) as e:
        collect.main(argv)
    assert str(e.value).startswith("not a production freeze")
    assert "download cache" not in str(e.value) and reg.read_bytes() == before


def test_f4_freshness_is_a_plan_check_not_an_execution_check():
    plan = inspect.getsource(collect._plan)
    assert "if not args.dry_run:\n        refuse_used_raw_cache(raw, args.dev_raw)" in plan
    assert plan.index("refuse_used_raw_cache") < plan.index("snapshot_pools")
    main = inspect.getsource(collect.main)
    assert (
        "refuse_used_raw_cache" not in main and "refuse_unsafe_raw_cache(raw, args.earlier)" in main
    )


# --- finding 5: documentation --------------------------------------------------------------

G10_WORDING = (
    "G10 is a development-text conformance check, not held-out validation or proof of "
    "equivalence on all possible texts. Production planning requires its authenticated result "
    "for the exact frozen candidate, round-1 comparison candidate, final ledger, harness and "
    "reviewed kept/reverted lists. The separate source audit establishes that no new rule or "
    "condition was introduced, including under an existing family identity. The six kept "
    "families are unchanged; the six specified reverted families are inactive. COMPLETE and "
    "interactions are evaluated afresh in round 2."
)


def _flat(text: str) -> str:
    return " ".join(text.replace("> ", " ").split())


def test_f5_documentation_wording():
    rulings, runbook = RULINGS.read_text(encoding="utf-8"), RUNBOOK.read_text(encoding="utf-8")
    s9 = runbook[runbook.index("## 9. Round 2") :]
    for doc in (rulings, s9, inspect.getsource(narrowing)):
        assert G10_WORDING in _flat(doc)
    # the documented lifecycle (audit r2 N3): DRAFT for review, then FINAL once the
    # maintainer adopts it before the plan (the adoption instructions are asserted below)
    status = [ln for ln in rulings.splitlines() if ln.startswith("**Status:**")]
    assert len(status) == 1, status
    assert status[0].startswith(("**Status:** DRAFT", "**Status:** FINAL")), status
    for needle in (
        "Finalize the ledger before the final fresh dry run. Any later change to candidate "
        "bytes, ledger bytes, harness bytes or comparison settings requires another fresh dry "
        "run and renewed review of its conformance evidence before planning.",
        "The maintainer reviews and adopts `round2/HARNESS_ROUND2_RULINGS.md`, replacing its "
        "status with `**Status:** FINAL` and recording the adoption date before the plan. Bind "
        "that exact committed file with `--dispositions`. The FINAL check on "
        "`--narrowing-disposition` does not validate the status of this separate rulings file.",
        "Planning authenticates round 1 and freezes its canonical-source exclusion set. "
        "Collection skips excluded sources, and acceptance checks disjointness of the actual "
        "collected source identities.",
    ):
        assert needle in _flat(s9), needle
    assert "the canonical source identities overlap round 1's" not in s9
    for name in ("human_page.py", "simulate_coverage.py", "test_analyse.py"):
        assert name in rulings  # all eight frozen inputs are named
    assert "all eight" in rulings
    if LEDGER2.exists():
        led = LEDGER2.read_text(encoding="utf-8")
        assert "the unchanged fix-check harness and acceptance code" not in led
        assert (
            "the reviewed round-2 harness changes disclosed in "
            "`round2.harness_changed_vs_round1`, the acceptance calculation with its bounds and "
            "gates unchanged apart from the procedure-precedence amendment to "
            "`fixcheck/accept.py` (round-2 rulings, A1), and the reviewed narrowing disposition"
            in _flat(led)
        )
