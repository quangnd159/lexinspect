"""`dryrun`: exercise every path end to end on the DEVELOPMENT build (no new texts).

The 120 development texts stand in for a check round. The candidate is the
real one: a frozen snapshot of src/ with the toggle interface
lexinspect._fix_families. BASELINE is only([]); COMPLETE is all twelve
families; each family alone is only([f]). The pinned 0.3.3 source tree
(dec79bc, archived at equivalence/baseline_033_src) runs as BASELINE_PINNED
in the same locked environment, and verify-baseline compares it with only([]).
The labels are synthetic (synthetic.py). Nothing here is evidence about the
candidate: the development texts informed the fixes, and the labels are random
or constructed. Everything is stamped production_eligible false.

Keyed by candidate digest (audit r1 S4). The first step snapshots the
candidate (prepare-candidate --from-working-tree: an INTERIM CANDIDATE DIGEST;
or --commit C) into a scratch directory and takes its digest. The output
directory is <out-root>/<first 16 hex of the digest>/ (or --out), with
DRYRUN_KEY.json naming the digest. Resuming into a directory whose key names
another digest is refused; --overwrite deletes the directory and regenerates
the snapshot and every stage.

Steps (each skipped when its output exists, unless --overwrite):
 ledger, collect --replay-development, collect --plan-only --dry-run (a
 demonstration round-1 freeze record, offline, nothing drawn), the development
 texts as a dry-run round package part (freeze_record.json, collection.json,
 execution.json, all stamped dry run), run (+ BASELINE_PINNED and
 verify-baseline), diff, sample (with operational power, B5), assign,
 delivery-spec; then for each label scenario (random, favourable): primary
 sessions exported to neutral directories, synthetic labels written into them
 with synthetic delivery records and transcripts, gather-labels; retry,
 retry sessions, gather, analyse.merge_retry; flash, adjudicator sessions,
 gather; then verify and `accept --package <scenario>.json --dry-run`.
 Determinism: BASELINE and COMPLETE re-run, and diff, sample and assign re-run
 from the same inputs and seed into determinism/, compared byte for byte.

Round 2 (HARNESS_ROUND2_RULINGS.md). `--ledger-md` (default: the DRAFT working
copy) is the ledger bound by the demonstration plan and the development round's
freeze record and checked by both verify calls, so a round-2 dry run checks the
round-2 ledger (gap G7). `--commit C2 --compare-candidate C --kept F1,F2,...` adds
the narrowing check (gap G10; narrowing.py). C is resolved to its full commit id
before the resume key. Commit C's candidate is snapshotted and run on the same
development texts (BASELINE and each kept family alone, into compare/); both
candidates run every combination of two or more kept families (subsets/,
compare/subsets/). kept_family_identity authenticates every one of these inputs
(a failure is a nonzero exit) and records, with a boolean `ok`: the BASELINE
frame, each kept family's frame and each kept combination byte-equal between the
two candidates; every other family of the new candidate with zero affected rows,
candidate and baseline counts equal (cross-checked against the rows) and a hit
sequence identical to BASELINE's; and the new candidate's COMPLETE equal to all
kept families together. The result and the identities it rests on are written to
NARROWING_CHECK.json (counts and hashes only), the round-2 plan's
`--narrowing-check`; `narrowing-check --dryrun-dir D` re-checks such a file
against D. The families come from the arguments; the round-2 plan checks them
against the authorized disposition's lists (narrowing.KEPT, narrowing.REVERTED).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import analyse
import build

from fixcheck import HERE, REPO
from fixcheck.common import (
    read_json,
    read_jsonl,
    set_command,
    sha256_file,
    sha256_text,
    write_json,
    write_step_manifest,
)
from fixcheck.ledger import COMPLETE, DRAFT_LEDGER_MD, FAMILIES, FAMILY_MODULE, MODULES

DEFAULT_OUT_ROOT = REPO / ".cache" / "validation" / "study4_fix040" / "harness_dryrun" / "real_r5"
PINNED_SRC = REPO / ".cache" / "validation" / "study4_fix040" / "equivalence" / "baseline_033_src"
LABEL_SEED = 20261117  # synthetic labels only; the round seed is round_dev's collection seed
DEMO_COLLECT_SEED = 20261118
SCENARIOS = ("random", "favourable")  # session roots: fresh random temp dirs (audit r2 B3)


def dev_round_dir(
    out: Path, candidate: dict[str, Any], spec: Path | None = None, ledger_md: Path | None = None
) -> Path:
    """The development texts as a dry-run round: texts, freeze record (binding the delivery
    spec, audit r2 B3), collection, execution and the collect manifest."""
    from fixcheck import freeze as FZ
    from fixcheck.common import source_hashes

    d = out / "round_dev"
    if (d / "execution.json").exists():
        return d
    from fixcheck import narrowing as NC

    (d / "texts").mkdir(parents=True, exist_ok=True)
    # the narrowing check's nested texts_jsonl_sha256 is recomputed from the development
    # manifest with this same function (narrowing.dev_round_texts_sha256; audit r2 N1)
    jsonl, texts = NC.dev_round_texts(build.DEV_TEXTS)
    for tid, text in texts.items():
        (d / "texts" / f"{tid}.txt").write_text(text, encoding="utf-8")
    (d / "texts.jsonl").write_text(jsonl, "utf-8")
    rows = read_jsonl(d / "texts.jsonl")
    fr = {
        "kind": FZ.FREEZE_KIND,
        "version": FZ.FREEZE_VERSION,
        "dry_run": True,
        "round": 1,
        "seed": build.DEV_SEED,
        "note": "development texts as a check round: DRY RUN ONLY, never a fix-check round",
        "candidate": candidate,
        "ledger": FZ.ledger_identity(
            ledger_md or DRAFT_LEDGER_MD, out / "ledger" / "ledger_components.json"
        ),
        "protocol": FZ.file_identity(FZ.PROTOCOL),
        "clarifications": FZ.file_identity(FZ.CLARIFICATIONS),
        "environment": FZ.environment_identity(REPO),
        "sources_sha256": source_hashes(),
        "bound": {"delivery_spec": FZ.file_identity(spec)},
        "delivery": {"spec_sha256": read_json(spec)["spec_sha256"] if spec else None},
        "registry": {"path": None, "reservation_sha256": None},
        "production_eligible": False,
        "ineligible_reasons": ["dry run", "development texts"],
    }
    write_json(d / "freeze_record.json", fr)
    col = {
        "round": 1,
        "seed": build.DEV_SEED,
        "status": "complete",
        "n_texts": len(rows),
        "texts_jsonl_sha256": sha256_file(d / "texts.jsonl"),
        "freeze_record_sha256": sha256_file(d / "freeze_record.json"),
        "production_eligible": False,
        "candidate": candidate,
        "note": "the 120 development texts, copied byte for byte; NOT a fix-check round",
    }
    write_json(d / "collection.json", col)
    write_json(
        d / "execution.json",
        {
            "freeze_record_sha256": col["freeze_record_sha256"],
            "collection_json_sha256": sha256_file(d / "collection.json"),
            "production_eligible": False,
            "gate": None,
        },
    )
    write_step_manifest(
        d,
        "collect",
        [d / "freeze_record.json", d / "texts.jsonl", d / "collection.json", d / "execution.json"]
        + sorted((d / "texts").glob("*.txt")),
    )
    return d


def _cli(args: list[str]) -> int:
    from fixcheck import cli

    print("+ fixcheck " + " ".join(args), file=sys.stderr)
    rc = cli.main(args)
    if rc not in (0, None):
        raise SystemExit(f"step failed ({rc}): {' '.join(args)}")
    return rc or 0


def power_headline(pw: dict[str, Any]) -> list[dict[str, Any]]:
    """Per scenario: all-gates, module and certificate frequencies with Wilson intervals,
    the target and the realised loss kept apart (audit r2 S4)."""
    out = []
    for sc in pw["scenarios"]:
        g = sc["gates"]
        out.append(
            {
                "kind": sc.get("kind", "lambda_grid"),
                "target_lambda": sc["lambda"],
                "calibrated_variant": sc.get("calibrated_variant"),
                "unresolved_structure": sc["unresolved_structure"],
                "all_gates_pass": g["ALL_REQUIRED_GATES_PASS"],
                "fail_by_certificate": g["FAIL_BY_CERTIFICATE"],
                "module_pass": {m: g[f"{m}|module_pass"] for m in MODULES},
                "realised_loss_fraction": {m: sc["realised"][m]["loss_fraction"] for m in MODULES},
                "nominal_zero_with_realised_losses": sc.get("nominal_zero_with_realised_losses"),
            }
        )
    return out


def frame_summary(frames: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Per configuration and module: frame sizes, and the removal plan of its deletion frame."""
    out: dict[str, Any] = {}
    for c in (COMPLETE, *FAMILIES):
        out[c] = {}
        for m in MODULES:
            f = frames["frames"][c][m]
            rp = plan["removal"][f"{c}|{m}|affected|REMOVED"]
            out[c][m] = {
                "own_module": c == COMPLETE or FAMILY_MODULE[c] == m,
                "N_baseline": f["N_baseline"],
                "N_candidate": f["N_candidate"],
                "N_unchanged": f["N_unchanged"],
                "N_affected": f["N_affected"],
                "affected": f["affected_sizes"],
                "span_changed_unresolved": f["span_changed_unresolved"],
                "final": f["final_sizes"],
                "removal_plan": {
                    k: rp.get(k)
                    for k in (
                        "N",
                        "n",
                        "status",
                        "attainable_upper_bound_if_no_success",
                        "gate_passable",
                        "max_k_hi_passing",
                        "breach_certificate_attainable",
                        "pass_probability_at_true_success_share",
                    )
                    if k in rp
                },
            }
    return out


RESUME_IDENTITY = (
    "candidate_tree_sha256",
    "source",
    "commit",
    "label",
    "harness_sha256",
    "environment_sha256",
    "settings",
)


def snapshot_and_key(
    out_root: Path,
    out: Path | None,
    commit: str | None,
    overwrite: bool,
    settings: dict[str, Any] | None = None,
    require_fresh: bool = False,
):
    """Snapshot the candidate into scratch, key the output directory by its digest (S4).

    The resume identity (audit r2 S2) is the candidate digest, its source and commit, the
    harness source hashes, the runtime environment identity and the dry-run settings. A
    directory whose key differs in any of them is refused before anything is rewritten;
    --overwrite regenerates everything; require_fresh refuses any existing directory."""
    import os
    import shutil

    from fixcheck.common import canonical_json, environment_sha256, source_hashes

    out_root.mkdir(parents=True, exist_ok=True)
    scratch = out_root / f".snapshot-{os.getpid()}"
    if scratch.exists():
        shutil.rmtree(scratch)
    args = ["prepare-candidate", "--checkout", str(REPO), "--dest", str(scratch)]
    _cli([*args, "--commit", commit] if commit else [*args, "--from-working-tree"])
    snap = read_json(scratch / "CANDIDATE_SNAPSHOT.json")
    digest = snap["tree_sha256"]
    out = (out or out_root / digest[:16]).resolve()
    key = {
        "candidate_tree_sha256": digest,
        "source": snap["source"],
        "commit": snap.get("commit"),
        "label": snap.get("label", "candidate commit snapshot"),
        "harness_sha256": sha256_text(canonical_json(source_hashes())),
        "environment_sha256": environment_sha256(),
        "settings": settings or {},
        "production_eligible": False,
        "note": "dry run: development texts, synthetic labels; never production evidence",
    }
    kp = out / "DRYRUN_KEY.json"
    if out.exists() and require_fresh:
        shutil.rmtree(scratch)
        raise SystemExit(f"{out} exists: this dry run must use a fresh, unique directory")
    if out.exists() and any(out.iterdir()):
        old = read_json(kp) if kp.exists() else {}
        differ = [k for k in RESUME_IDENTITY if old.get(k) != key[k]]
        if overwrite:
            shutil.rmtree(out)
        elif differ:
            shutil.rmtree(scratch)
            raise SystemExit(
                f"{out} holds a dry run of candidate "
                f"{str(old.get('candidate_tree_sha256'))[:16]} whose identity differs in "
                f"{differ}: refusing to resume (pass --overwrite to regenerate everything)"
            )
        else:  # identical identity: resume, keeping the existing snapshot and key
            shutil.rmtree(scratch)
            return out, old
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "candidate_src" / "CANDIDATE_SNAPSHOT.json").exists():
        if (out / "candidate_src").exists():
            shutil.rmtree(out / "candidate_src")
        shutil.move(str(scratch), str(out / "candidate_src"))
    else:
        shutil.rmtree(scratch)
    write_json(kp, key)
    return out, key


def _split_by_session(lines: list[str], index: dict[str, Any], role: str) -> dict[str, str]:
    by_id: dict[str, list[str]] = {}
    for x in lines:
        if x.strip():
            by_id.setdefault(json.loads(x)["id"], []).append(x)
    out = {}
    for s in index["sessions"]:
        if s["role"] == role:
            out[s["token"]] = "".join(y + "\n" for i in s["ids"] for y in by_id.get(i, []))
    return out


def deliver(stage_out: Path, per_role_lines: dict[str, list[str]], transcripts: Path) -> None:
    """Synthetic deliveries: write each session's labels and a delivery record (dry run)."""
    index = read_json(stage_out / "sessions_index.json")
    spec = read_json(Path(index["spec"]))
    transcripts.mkdir(parents=True, exist_ok=True)
    recs = []
    for role, lines in per_role_lines.items():
        for tok, text in _split_by_session(lines, index, role).items():
            s = next(x for x in index["sessions"] if x["token"] == tok)
            lab = Path(s["dir"]) / "labels.jsonl"
            lab.write_text(text, encoding="utf-8")
            tr = transcripts / f"{tok}.txt"
            tr.write_text(f"synthetic dry-run transcript for session {tok}\n", encoding="utf-8")
            recs.append(
                {
                    "token": tok,
                    "delivered": True,
                    **spec["roles"][role],
                    "session_id": f"dryrun-{tok}",
                    "transcript": str(tr),
                    "transcript_sha256": sha256_file(tr),
                    "labels_sha256": sha256_file(lab),
                    "delivered_at": None,
                    "access_review": "DRY RUN: synthetic labels, no model session",
                }
            )
    from fixcheck.common import write_jsonl

    write_jsonl(stage_out / "deliveries.jsonl", recs)


def parse_kept(compare_candidate: str | None, kept: str | None) -> list[str] | None:
    """The kept families of --kept (gap G10): given together with --compare-candidate, each
    one of the twelve, no repeats. None when no comparison is asked for."""
    if compare_candidate is None and kept is None:
        return None
    if not compare_candidate or kept is None:
        raise SystemExit("--compare-candidate and --kept are given together")
    fams = [f.strip() for f in kept.split(",") if f.strip()]
    unknown = [f for f in fams if f not in FAMILIES]
    if not fams or unknown or len(set(fams)) != len(fams):
        raise SystemExit(
            f"--kept {kept!r}: give distinct families from {list(FAMILIES)} (unknown: {unknown})"
        )
    return [f for f in FAMILIES if f in fams]


def _rows_by_module(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {m: sum(r.get("module") == m for r in rows) for m in MODULES}


def _module_counts(path: Path) -> dict[str, int]:
    """_rows_by_module of a hit file, read one row at a time. The narrowing check's four frame
    sets (135 frames, about 7.6 GB of JSONL on the real development texts) never fit in
    memory at once: holding them all made the first full round-2 dry runs be killed (exit
    137, review-1 report r2)."""
    n = dict.fromkeys(MODULES, 0)
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                m = json.loads(line).get("module")
                if m in n:
                    n[m] += 1
    return n


def _snapshot_problems(snap_dir: Path, commit: str, what: str) -> tuple[dict[str, Any], list[str]]:
    """A candidate snapshot is the named commit's src/lexinspect: a nonempty commit and tree
    digest, the commit the one requested, the snapshot's bytes its recorded digest, and that
    digest the commit's git-object digest (freeze.commit_src_digest)."""
    from fixcheck import freeze as FZ
    from fixcheck.run import pkg_digest

    sp = snap_dir / "CANDIDATE_SNAPSHOT.json"
    if not sp.is_file():
        return {}, [f"{what}: {sp} missing"]
    snap = read_json(sp)
    p = []
    if not snap.get("commit") or not snap.get("tree_sha256"):
        return snap, [f"{what}: the snapshot records no commit or no tree digest"]
    if snap["commit"] != commit:
        p.append(f"{what}: the snapshot is of {snap['commit']}, not the requested {commit}")
    if pkg_digest(snap_dir / "lexinspect")["tree_sha256"] != snap["tree_sha256"]:
        p.append(f"{what}: the snapshot's bytes are not its recorded tree digest")
    try:
        if FZ.commit_src_digest(snap["commit"])["tree_sha256"] != snap["tree_sha256"]:
            p.append(f"{what}: the snapshot's tree digest is not the commit's (git objects)")
    except SystemExit as e:
        p.append(f"{what}: the commit is unreadable ({e})")
    return snap, p


def _frames_problems(
    root: Path,
    step: str,
    configs: dict[str, list[str]],
    snap_dir: Path,
    texts_sha: str,
    what: str,
) -> tuple[dict[str, dict[str, int]], list[str]]:
    """One set of worker frames: its step manifest holds every hits and meta file with its
    hash; each meta names its configuration, the families enabled, the snapshot it imported,
    the development text manifest, its hit file's SHA-256 and per-module counts equal to the
    actual rows. Returns each configuration's per-module row counts (counted one row at a
    time, never holding the frames)."""
    from fixcheck.package import check_manifest

    head = "run.json" if step == "run" else "subsets.json"
    req = [head] + [f"frames/{c}.{x}" for c in configs for x in ("hits.jsonl", "meta.json")]
    p = [f"{what}: {x}" for x in check_manifest(root, step, req)]
    if p:
        return {}, p
    counts: dict[str, dict[str, int]] = {}
    imp = str(snap_dir.resolve())
    for c, fams in configs.items():
        hits, meta = (
            root / "frames" / f"{c}.hits.jsonl",
            read_json(root / "frames" / f"{c}.meta.json"),
        )
        counts[c] = _module_counts(hits)
        if meta.get("config") != c or meta.get("enabled") != fams:
            p.append(f"{what}: {c}.meta.json is not configuration {c} with {fams}")
        if meta.get("import_root") != imp:
            p.append(f"{what}: {c} did not import the snapshot {imp}")
        if meta.get("texts_jsonl_sha256") != texts_sha:
            p.append(f"{what}: {c} ran on another text manifest")
        if meta.get("hits_sha256") != sha256_file(hits):
            p.append(f"{what}: {c}.meta.json does not name its hit file")
        if meta.get("n_hits") != counts[c]:
            p.append(f"{what}: {c}.meta.json's counts are not the rows' counts")
    return counts, p


def _dev_round_problems(rd: Path, dev_texts: Path) -> tuple[str | None, list[str]]:
    """The development round directory holds the canonical development texts: its
    texts.jsonl is the manifest's rows with their text hashes, and each text file has its
    hash. Returns (round texts.jsonl SHA-256, problems)."""
    tj = rd / "texts.jsonl"
    if not tj.is_file() or not Path(dev_texts).is_file():
        return None, [f"development texts missing ({tj}, {dev_texts})"]
    rows, dev = read_jsonl(tj), read_jsonl(Path(dev_texts))
    p = []
    if [{k: v for k, v in r.items() if k != "text_sha256"} for r in rows] != dev:
        p.append("the development round's texts.jsonl is not the development manifest")
    for r in rows:
        f = rd / "texts" / f"{r.get('text_id')}.txt"
        if not f.is_file() or sha256_text(f.read_text(encoding="utf-8")) != r.get("text_sha256"):
            p.append(f"{r.get('text_id')}: text bytes differ from the development round")
    return sha256_file(tj), p[:20]


def kept_family_identity(
    out: Path,
    cmp_dir: Path,
    kept: list[str],
    compare_commit: str,
    candidate_commit: str,
    dev_texts: Path | None = None,
) -> dict[str, Any]:
    """Gap G10 (narrowing.py), from the harness's own authenticated outputs.

    Authentication first (any problem raises SystemExit, a nonzero exit): both candidate
    snapshots are the requested commits (nonempty commit and tree, bytes, git objects); the
    new candidate's run (BASELINE, COMPLETE, every family alone), the comparison candidate's
    run (BASELINE, each kept family alone), both candidates' kept-family combinations
    (subsets/) and the new candidate's diff hold every file in their step manifests with its
    hash; every worker imported its snapshot, ran its configuration on the one development
    text manifest, and its meta names its hit file and the rows' per-module counts; the diff
    is of this run. Then, counts and hashes only:
    - the BASELINE frame, each kept family's frame and each combination of two or more kept
      families are byte-equal between the two candidates;
    - every other family of the new candidate has zero affected rows, candidate and
      baseline counts equal (diff/frames.json, cross-checked against the rows) and a hit
      sequence identical to BASELINE's (run.compare_frames);
    - the new candidate's COMPLETE has the hit sequence of all kept families together."""
    from fixcheck import narrowing as NC
    from fixcheck.run import compare_frames

    dev_texts = build.DEV_TEXTS if dev_texts is None else dev_texts
    others = [f for f in FAMILIES if f not in kept]
    subsets = NC.kept_subsets(kept)
    cand_snap, p = _snapshot_problems(out / "candidate_src", candidate_commit, "candidate")
    cmp_snap, q = _snapshot_problems(cmp_dir / "candidate_src", compare_commit, "comparison")
    p += q
    texts_sha, q = _dev_round_problems(out / "round_dev", dev_texts)
    p += q
    if p:
        raise SystemExit(f"kept-family identity inputs do not authenticate: {p}")
    new_cfg = {"BASELINE": [], COMPLETE: list(FAMILIES)} | {f: [f] for f in FAMILIES}
    cmp_cfg = {"BASELINE": []} | {f: [f] for f in kept}
    sets = (
        ("new run", out / "run", "run", new_cfg, out / "candidate_src"),
        ("comparison run", cmp_dir / "run", "run", cmp_cfg, cmp_dir / "candidate_src"),
        ("new subsets", out / "subsets", "subsets", subsets, out / "candidate_src"),
        ("comparison subsets", cmp_dir / "subsets", "subsets", subsets, cmp_dir / "candidate_src"),
    )
    got = {}
    for what, root, step, cfg, snap_dir in sets:
        got[what], q = _frames_problems(root, step, cfg, snap_dir, texts_sha, what)
        p += q
    for what, root, _, _, snap_dir in sets:
        head = root / ("run.json" if what.endswith("run") else "subsets.json")
        if not head.is_file():
            continue
        h = read_json(head)
        tree = (h.get("candidate_snapshot") or h.get("snapshot") or {}).get("tree_sha256")
        snap = cand_snap if snap_dir == out / "candidate_src" else cmp_snap
        if h.get("candidate_src") != str(snap_dir.resolve()) or tree != snap.get("tree_sha256"):
            p.append(f"{what}: not run on its candidate snapshot")
    from fixcheck.package import check_manifest

    p += [f"diff: {x}" for x in check_manifest(out / "diff", "diff", ["frames.json"])]
    frames_path = out / "diff" / "frames.json"
    fj = read_json(frames_path) if frames_path.is_file() else {}
    if fj.get("run_json_sha256") != _maybe_sha(out / "run" / "run.json"):
        p.append("diff: frames.json is not of this run")
    if p:
        raise SystemExit(f"kept-family identity inputs do not authenticate: {p}")
    new_frames, cmp_frames = out / "run" / "frames", cmp_dir / "run" / "frames"
    new_sub, cmp_sub = out / "subsets" / "frames", cmp_dir / "subsets" / "frames"

    def same(name: str, a_dir: Path, b_dir: Path, n_hits: dict[str, int]) -> dict[str, Any]:
        a, b = a_dir / f"{name}.hits.jsonl", b_dir / f"{name}.hits.jsonl"
        return {
            "candidate_sha256": sha256_file(a),
            "compare_sha256": sha256_file(b),
            "byte_equal": a.read_bytes() == b.read_bytes(),
            "n_hits": n_hits,
        }

    # per-module counts from the authentication above; rows are read only for the sequence
    # comparisons, at most two frames at a time (_module_counts: the frames never fit at once)
    new_counts = got["new run"]
    base_counts = new_counts["BASELINE"]
    base = read_jsonl(new_frames / "BASELINE.hits.jsonl")
    frames = fj["frames"]
    not_kept = {}
    for f in others:
        mods = {
            m: {k: frames[f][m][k] for k in ("N_baseline", "N_candidate", "N_affected")}
            for m in MODULES
        }
        counts = {m: {"candidate": new_counts[f][m], "baseline": base_counts[m]} for m in MODULES}
        not_kept[f] = {
            "modules": mods,
            "rows": counts,
            "zero_affected": all(
                v["N_affected"] == 0 and v["N_candidate"] == v["N_baseline"] for v in mods.values()
            ),
            "counts_match_rows": all(
                (mods[m]["N_candidate"], mods[m]["N_baseline"])
                == (counts[m]["candidate"], counts[m]["baseline"])
                for m in MODULES
            ),
            "identical_to_baseline": compare_frames(
                base, read_jsonl(new_frames / f"{f}.hits.jsonl")
            )["identical"],
        }
    del base
    kept_res = {f: same(f, new_frames, cmp_frames, new_counts[f]) for f in kept}
    sub_res = {
        n: {"families": fams, **same(n, new_sub, cmp_sub, got["new subsets"][n])}
        for n, fams in subsets.items()
    }
    union_path = (
        new_sub / f"{NC.subset_config(kept)}.hits.jsonl"
        if len(kept) > 1
        else new_frames / f"{kept[0]}.hits.jsonl"
    )
    ce = compare_frames(read_jsonl(new_frames / f"{COMPLETE}.hits.jsonl"), read_jsonl(union_path))
    baseline = same("BASELINE", new_frames, cmp_frames, base_counts)
    ok = (
        baseline["byte_equal"]
        and all(v["byte_equal"] for v in kept_res.values())
        and all(v["byte_equal"] for v in sub_res.values())
        and all(
            v["zero_affected"] and v["counts_match_rows"] and v["identical_to_baseline"]
            for v in not_kept.values()
        )
        and ce["identical"]
    )
    return {
        "compare_commit": cmp_snap["commit"],
        "compare_tree_sha256": cmp_snap["tree_sha256"],
        "candidate_commit": cand_snap["commit"],
        "candidate_tree_sha256": cand_snap["tree_sha256"],
        "texts_jsonl_sha256": texts_sha,
        "kept": list(kept),
        "not_kept": others,
        "baseline": baseline,
        "kept_frames": kept_res,
        "kept_subsets": sub_res,
        "not_kept_frames": not_kept,
        "complete_equals_kept_union": {
            "identical": ce["identical"],
            "n_complete": ce["n_a"],
            "n_kept_union": ce["n_b"],
        },
        "ok": ok,
    }


def _maybe_sha(p: Path) -> str | None:
    return sha256_file(p) if p.is_file() else None


def run_subsets(dest: Path, snap_dir: Path, rd: Path, kept: list[str], jobs: int) -> None:
    """Every combination of two or more kept families (narrowing.kept_subsets), each in its
    own worker process importing the snapshot `snap_dir`, on the development round `rd`:
    dest/frames/<KEPT+...>.hits.jsonl and .meta.json, dest/subsets.json and
    dest/manifest_subsets.json. Skipped when subsets.json exists (resumed; authenticated by
    kept_family_identity either way)."""
    from concurrent.futures import ThreadPoolExecutor

    from fixcheck import narrowing as NC
    from fixcheck.run import _run, worker_cmd

    if (dest / "subsets.json").exists():
        return
    subsets = NC.kept_subsets(kept)
    (dest / "frames").mkdir(parents=True, exist_ok=True)
    (dest / "logs").mkdir(exist_ok=True)
    snap_dir = snap_dir.resolve()
    fam_mod = "lexinspect._fix_families"
    cmds = {
        n: [
            *worker_cmd(REPO, rd, n, fam_mod, fams, dest / "frames"),
            "--import-root",
            str(snap_dir),
        ]
        for n, fams in subsets.items()
    }
    print(f"+ {len(cmds)} kept-family combinations into {dest}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {n: ex.submit(_run, c, None, dest / "logs" / f"{n}.log") for n, c in cmds.items()}
        failed = {n: f.result() for n, f in futs.items() if f.result() != 0}
    if failed:
        raise SystemExit(f"kept-family combination workers failed {failed}; see {dest / 'logs'}")
    snap = read_json(snap_dir / "CANDIDATE_SNAPSHOT.json")
    write_json(
        dest / "subsets.json",
        {
            "configs": subsets,
            "candidate_src": str(snap_dir),
            "snapshot": {"commit": snap.get("commit"), "tree_sha256": snap.get("tree_sha256")},
            "round_dir": str(rd),
            "families_module": fam_mod,
            "production_eligible": False,
        },
    )
    files = [dest / "subsets.json"] + [
        dest / "frames" / f"{n}.{x}" for n in subsets for x in ("hits.jsonl", "meta.json")
    ]
    write_step_manifest(dest, "subsets", files)


def narrowing_evidence(
    out: Path,
    key: dict[str, Any],
    identity: dict[str, Any],
    summary: dict[str, Any],
    dev_texts: Path | None = None,
) -> dict[str, Any]:
    """NARROWING_CHECK.json (narrowing.py): the kept-family identity of this dry run, with
    the identities the round-2 plan validates it against. Counts and hashes only."""
    from fixcheck import narrowing as NC

    dev_texts = build.DEV_TEXTS if dev_texts is None else dev_texts
    settings = key.get("settings") or {}
    det = summary.get("determinism") or {}
    checks = {
        "verify_ok": summary.get("verify_ok") is True,
        "ledger_ok": summary.get("ledger_ok") is True,
        "blinding_ok": summary.get("blinding_ok") is True,
        "verify_baseline_identical": (summary.get("verify_baseline") or {}).get("identical")
        is True,
        "determinism_identical": bool(det)
        and all(v is True for d in det.values() for v in d.values()),
        "ledger_md_is_keyed": summary.get("ledger_md_sha256") == settings.get("ledger_md_sha256"),
    }
    return {
        "kind": NC.KIND,
        "version": NC.VERSION,
        "what": "G10 development-text conformance check (the 120 development texts): not "
        "held-out validation or proof of equivalence on all possible texts",
        "candidate_commit": identity["candidate_commit"],
        "candidate_tree_sha256": identity["candidate_tree_sha256"],
        "compare_commit": identity["compare_commit"],
        "compare_tree_sha256": identity["compare_tree_sha256"],
        "kept": identity["kept"],
        "not_kept": identity["not_kept"],
        "ledger_md_sha256": settings.get("ledger_md_sha256"),
        "harness_sha256": key.get("harness_sha256"),
        "environment_sha256": key.get("environment_sha256"),
        "dev_texts_jsonl_sha256": sha256_file(dev_texts) if Path(dev_texts).is_file() else None,
        "dryrun": {
            "key_sha256": sha256_file(out / "DRYRUN_KEY.json"),
            "summary_sha256": sha256_file(out / "dryrun_summary.json"),
            "checks": checks,
        },
        "kept_family_identity": identity,
        "ok": identity["ok"] is True and all(checks.values()),
    }


def narrowing_main(argv: list[str]) -> int:
    """`narrowing-check --dryrun-dir D [--evidence F]`: re-check a narrowing check (for
    example round2/NARROWING_CHECK.json) against the dry run that produced it. The kept-family
    identity is recomputed from D's authenticated outputs (a failed authentication refuses:
    nonzero exit) and must equal the evidence's, which must name D's key and summary by
    SHA-256 and be ok. Exit 0 only then. Writes nothing."""
    from fixcheck.common import canonical_json

    set_command("narrowing-check", argv)
    ap = argparse.ArgumentParser(prog="fixcheck narrowing-check")
    ap.add_argument("--dryrun-dir", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, help="default <dryrun-dir>/NARROWING_CHECK.json")
    args = ap.parse_args(argv)
    from fixcheck import narrowing as NC

    d = args.dryrun_dir.resolve()
    ev_path = (args.evidence or d / NC.FILENAME).resolve()
    for f in (d / "DRYRUN_KEY.json", d / "dryrun_summary.json", ev_path):
        if not f.is_file():
            raise SystemExit(f"narrowing check refused: {f} missing")
    key = read_json(d / "DRYRUN_KEY.json")
    st = key.get("settings") or {}
    if not st.get("compare_candidate") or not st.get("kept") or not key.get("commit"):
        raise SystemExit("narrowing check refused: the dry run ran no kept-family comparison")
    identity = kept_family_identity(
        d, d / "compare", st["kept"], st["compare_candidate"], key["commit"]
    )
    ev = read_json(ev_path)
    p = []
    if canonical_json(ev.get("kept_family_identity")) != canonical_json(identity):
        p.append("the evidence's kept_family_identity is not what the dry run's outputs give")
    dr = ev.get("dryrun") or {}
    if dr.get("key_sha256") != sha256_file(d / "DRYRUN_KEY.json"):
        p.append("the evidence does not name this dry run's key")
    if dr.get("summary_sha256") != sha256_file(d / "dryrun_summary.json"):
        p.append("the evidence does not name this dry run's summary")
    for k, want in (
        ("harness_sha256", key.get("harness_sha256")),
        ("ledger_md_sha256", st.get("ledger_md_sha256")),
        ("candidate_commit", key.get("commit")),
        ("compare_commit", st.get("compare_candidate")),
    ):
        if ev.get(k) != want:
            p.append(f"the evidence's {k} is not the dry run's")
    if ev.get("ok") is not True:
        p.append("the evidence's ok is not true")
    print(json.dumps({"evidence": str(ev_path), "ok": not p, "problems": p}, indent=1))
    return 0 if not p else 1


def main(argv: list[str]) -> int:
    set_command("dryrun", argv)
    ap = argparse.ArgumentParser(prog="fixcheck dryrun", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--out", type=Path, help="explicit output dir (still key-checked)")
    ap.add_argument("--commit", help="snapshot this commit instead of the working tree")
    ap.add_argument("--pinned-src", type=Path, default=PINNED_SRC)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--plan-reps", type=int, default=200)
    ap.add_argument("--power-reps", type=int, default=200)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument(
        "--require-fresh",
        action="store_true",
        help="refuse an existing output directory (the final committed-candidate dry run)",
    )
    ap.add_argument(
        "--ledger-md",
        type=Path,
        default=DRAFT_LEDGER_MD,
        help="the ledger the demonstration plan binds and verify checks (round 2: the "
        "round-2 ledger)",
    )
    ap.add_argument(
        "--compare-candidate",
        metavar="COMMIT",
        help="kept-family identity check against this commit's candidate (needs --kept)",
    )
    ap.add_argument("--kept", help="comma-separated kept families (with --compare-candidate)")
    args = ap.parse_args(argv)
    if "lexinspect" in sys.modules:
        raise SystemExit("lexinspect was imported before the candidate snapshot was put first")
    kept = parse_kept(args.compare_candidate, args.kept)
    compare_commit = None
    if kept is not None:
        from fixcheck import freeze as FZ

        if not args.commit:
            raise SystemExit(
                "--compare-candidate needs --commit: the narrowing check is evidence for an "
                "exact committed candidate, never a working-tree snapshot"
            )
        compare_commit = FZ.full_commit(args.compare_candidate)  # immutable, before the resume key
    ledger_md = args.ledger_md.resolve()
    if not ledger_md.is_file():
        raise SystemExit(f"--ledger-md {ledger_md} not found")
    settings = {
        "plan_reps": args.plan_reps,
        "power_reps": args.power_reps,
        "pinned_src": str(args.pinned_src.resolve()),
        "label_seed": LABEL_SEED,
        "demo_collect_seed": DEMO_COLLECT_SEED,
        "ledger_md": str(ledger_md),
        "ledger_md_sha256": sha256_file(ledger_md),
        "compare_candidate": compare_commit,
        "kept": kept,
    }
    out, key = snapshot_and_key(
        args.out_root.resolve(),
        args.out,
        args.commit,
        args.overwrite,
        settings=settings,
        require_fresh=args.require_fresh,
    )
    print(f"dry run of candidate {key['candidate_tree_sha256'][:16]} into {out}", file=sys.stderr)

    def todo(p: Path) -> bool:
        return not p.exists()

    cand = out / "candidate_src"
    snap = read_json(cand / "CANDIDATE_SNAPSHOT.json")
    sys.path.insert(0, str(cand))
    if todo(out / "ledger" / "ledger_components.json"):
        _cli(["ledger", "--out", str(out / "ledger")])
    if todo(out / "collect_replay" / "replay.json"):
        _cli(["collect", "--replay-development", "--out", str(out / "collect_replay")])
    spec = out / "delivery_spec.json"
    if todo(spec):
        _cli(["delivery-spec", "--out", str(spec)])
    if todo(out / "collect_plan_round1" / "freeze_record.json"):
        # a demonstration plan: a scratch (non-canonical) registry receives the reservation
        _cli(
            [
                "collect",
                "--round",
                "1",
                "--seed",
                str(DEMO_COLLECT_SEED),
                "--offline",
                "--plan-only",
                "--dry-run",
                "--ledger-md",
                str(ledger_md),
                "--ledger-components",
                str(out / "ledger" / "ledger_components.json"),
                "--delivery-spec",
                str(spec),
                "--registry",
                str(out / "demo_registry.jsonl"),
                "--out",
                str(out / "collect_plan_round1"),
            ]
        )
    candidate = {
        "commit": snap.get("commit"),
        "tree_sha256": snap["tree_sha256"],
        "n_files": snap["n_files"],
    }
    rd = dev_round_dir(out, candidate, spec, ledger_md)
    run_common = [
        "--round-dir",
        str(rd),
        "--checkout",
        str(REPO),
        "--candidate-src",
        str(cand),
        "--families-module",
        "lexinspect._fix_families",
        "--jobs",
        str(args.jobs),
    ]
    if todo(out / "run" / "run.json"):
        _cli(
            [
                "run",
                "--out",
                str(out / "run"),
                "--pinned-src",
                str(args.pinned_src.resolve()),
                *run_common,
            ]
        )

    def chain(prefix: Path, power_reps: int) -> None:
        """diff -> sample -> assign from out/run into prefix/."""
        if todo(prefix / "diff" / "frames.json"):
            _cli(["diff", "--run-dir", str(out / "run"), "--out", str(prefix / "diff")])
        if todo(prefix / "sample" / "selection.json"):
            _cli(
                [
                    "sample",
                    "--run-dir",
                    str(out / "run"),
                    "--diff-dir",
                    str(prefix / "diff"),
                    "--out",
                    str(prefix / "sample"),
                    "--plan-reps",
                    str(args.plan_reps),
                    "--power-reps",
                    str(power_reps),
                    "--jobs",
                    str(args.jobs),
                ]
            )
        if todo(prefix / "assign" / "items.jsonl"):
            _cli(
                ["assign", "--sample-dir", str(prefix / "sample"), "--out", str(prefix / "assign")]
            )

    chain(out, args.power_reps)
    from fixcheck import synthetic

    ad = out / "assign"
    items = {r["id"]: r for r in read_jsonl(ad / "items.jsonl")}
    key_rows = read_jsonl(ad / "key.jsonl")
    pkg_dir = out / "pkg"
    pkg_dir.mkdir(exist_ok=True)
    summary = {}
    for scen in SCENARIOS:
        sd = out / scen
        L = sd / "labels"
        L.mkdir(parents=True, exist_ok=True)
        trans = out / "transcripts" / scen
        pkg_json = pkg_dir / f"{scen}.json"
        write_json(
            pkg_json,
            {
                "collect": "../round_dev",
                "replay": "../collect_replay",
                "candidate": "../candidate_src",
                "run": "../run",
                "diff": "../diff",
                "sample": "../sample",
                "assign": "../assign",
                "retry": f"../{scen}/retry",
                "flash": f"../{scen}/flash",
                "sessions": f"../{scen}/sessions",
                "labels": f"../{scen}/labels",
                "verify": f"../{scen}/verify",
            },
        )

        def export(stage: str, stage_dir: Path, sd=sd, scen=scen, pkg_json=pkg_json) -> Path:
            so = sd / "sessions" / stage
            if todo(so / "sessions_index.json"):
                # the stage receipt first (in production: committed and pushed before export)
                rc = out / "receipts" / scen / f"{stage}.json"
                if todo(rc):
                    _cli(
                        [
                            "stage-receipt",
                            "--package",
                            str(pkg_json),
                            "--stage",
                            stage,
                            "--out",
                            str(rc),
                        ]
                    )
                _cli(
                    [
                        "export-sessions",
                        "--spec",
                        str(spec),
                        "--stage",
                        stage,
                        "--stage-dir",
                        str(stage_dir),
                        "--fresh-session-root",
                        "--package",
                        str(pkg_json),
                        "--receipt",
                        str(rc),
                        "--out",
                        str(so),
                    ]
                )
            return so

        def gather(so: Path, role: str, dest: Path) -> None:
            if todo(dest):
                from fixcheck import cli

                print(f"+ fixcheck gather-labels {so} {role}", file=sys.stderr)
                rc = cli.main(
                    ["gather-labels", "--stage-out", str(so), "--role", role, "--out", str(dest)]
                )
                if rc:
                    raise SystemExit(f"gather-labels failed for {role} ({so})")

        if scen == "random":
            la, lb = synthetic.random_primaries(key_rows, items, LABEL_SEED)
            truth = None
        else:
            la, lb, truth = synthetic.favourable(key_rows, LABEL_SEED)
        so = export("primary", ad)
        if todo(so / "deliveries.jsonl"):
            deliver(so, {"A": la, "B": lb}, trans / "primary")
        for role in ("A", "B"):
            gather(so, role, L / f"{role}.pass1.jsonl")
        rt = sd / "retry"
        if todo(rt / "retry.json"):
            _cli(
                [
                    "retry",
                    "--assign-dir",
                    str(ad),
                    "--labels",
                    f"A={L / 'A.pass1.jsonl'}",
                    f"B={L / 'B.pass1.jsonl'}",
                    "--out",
                    str(rt),
                ]
            )
        manifest = {r: analyse.read_id_file(rt / f"retry_{r}.jsonl") for r in ("A", "B")}
        if any(manifest.values()):
            so_r = export("retry", rt)
            answers = {
                r: synthetic.retry_answers(ids, items, LABEL_SEED + ord(r))
                for r, ids in manifest.items()
                if ids
            }
            if todo(so_r / "deliveries.jsonl"):
                deliver(so_r, answers, trans / "retry")
            for r in answers:
                gather(so_r, r, L / f"{r}.retry.jsonl")
        for r in ("A", "B"):
            first = (L / f"{r}.pass1.jsonl").read_text(encoding="utf-8").splitlines()
            rf = L / f"{r}.retry.jsonl"
            again = rf.read_text(encoding="utf-8").splitlines() if rf.exists() else []
            merged, _ = analyse.merge_retry(first, again, manifest[r])
            (L / f"{r}.jsonl").write_text("".join(x + "\n" for x in merged), encoding="utf-8")
        fd = sd / "flash"
        if todo(fd / "flash_ids.txt"):
            _cli(
                [
                    "flash",
                    "--assign-dir",
                    str(ad),
                    "--labels",
                    f"A={L / 'A.jsonl'}",
                    f"B={L / 'B.jsonl'}",
                    "--out",
                    str(fd),
                ]
            )
        fids = (fd / "flash_ids.txt").read_text().split()
        if fids:
            adj = (
                synthetic.random_adjudicator(fids, items, LABEL_SEED)
                if truth is None
                else synthetic.favourable_adjudicator(fids, truth)
            )
            so_f = export("flash", fd)
            if todo(so_f / "deliveries.jsonl"):
                deliver(so_f, {"adjudicator": adj}, trans / "flash")
            gather(so_f, "adjudicator", L / "adjudicator.jsonl")
        if todo(sd / "verify" / "verify.json"):
            from fixcheck import cli

            vargs = [
                "verify",
                "--out",
                str(sd / "verify"),
                "--ledger-md",
                str(ledger_md),
                "--assign-dir",
                str(ad),
                "--sample-dir",
                str(out / "sample"),
                "--run-dir",
                str(out / "run"),
                "--flash-dir",
                str(fd),
                "--retry-dir",
                str(rt),
            ]
            print("+ fixcheck " + " ".join(vargs), file=sys.stderr)
            cli.main(vargs)
        acc = out / f"accept_{scen}"
        if todo(acc / "acceptance.json"):
            _cli(
                [
                    "accept",
                    "--package",
                    str(pkg_dir / f"{scen}.json"),
                    "--dry-run",
                    "--out",
                    str(acc),
                ]
            )
        res = read_json(acc / "acceptance.json")
        pc = res["package_check"]
        summary[scen] = {
            "mathematical_status": res["status"],
            "production_eligible": res["production_eligible"],
            "modules": {m: res["modules"][m]["status"] for m in res["modules"]},
            "breach_certificates": {
                m: res["modules"][m]["breach_certificates"] for m in res["modules"]
            },
            "package_links_ok": {k: v["ok"] for k, v in pc["links"].items()},
            "package_problems": pc["problems"],
            "n_retry": {r: len(v) for r, v in manifest.items()},
            "n_flash": len(fids),
        }
    # Determinism: the same inputs and seed give the same bytes.
    det = out / "determinism"
    if todo(det / "run" / "run.json"):
        _cli(["run", "--out", str(det / "run"), "--configs", f"BASELINE,{COMPLETE}", *run_common])
    chain(det, args.power_reps)
    compare = [
        ("diff", out / "diff", det / "diff"),
        ("sample", out / "sample", det / "sample"),
        ("assign", out / "assign", det / "assign"),
    ]
    vargs = [
        "verify",
        "--out",
        str(out / "verify"),
        "--ledger-md",
        str(ledger_md),
        "--assign-dir",
        str(ad),
        "--sample-dir",
        str(out / "sample"),
        "--run-dir",
        str(out / "run"),
    ]
    for scen in SCENARIOS:
        vargs += [
            "--flash-dir",
            str(out / scen / "flash"),
            "--retry-dir",
            str(out / scen / "retry"),
        ]
    for _, a, b in compare:
        vargs += ["--compare", str(a), str(b)]
    from fixcheck import cli

    print("+ fixcheck " + " ".join(vargs), file=sys.stderr)
    verify_rc = cli.main(vargs)
    kept_identity = None
    if kept is not None:
        cmp_dir = out / "compare"
        csrc = cmp_dir / "candidate_src"
        if todo(csrc / "CANDIDATE_SNAPSHOT.json"):
            if csrc.exists():
                import shutil

                shutil.rmtree(csrc)
            _cli(
                [
                    "prepare-candidate",
                    "--checkout",
                    str(REPO),
                    "--dest",
                    str(csrc),
                    "--commit",
                    compare_commit,
                ]
            )
        if todo(cmp_dir / "run" / "run.json"):
            _cli(
                [
                    "run",
                    "--out",
                    str(cmp_dir / "run"),
                    "--configs",
                    ",".join(["BASELINE", *kept]),
                    "--round-dir",
                    str(rd),
                    "--checkout",
                    str(REPO),
                    "--candidate-src",
                    str(csrc),
                    "--families-module",
                    "lexinspect._fix_families",
                    "--jobs",
                    str(args.jobs),
                ]
            )
        # every combination of two or more kept families, for both candidates (G10)
        run_subsets(out / "subsets", cand, rd, kept, args.jobs)
        run_subsets(cmp_dir / "subsets", csrc, rd, kept, args.jobs)
        kept_identity = kept_family_identity(out, cmp_dir, kept, compare_commit, snap.get("commit"))
    worker_det = {
        c: sha256_file(out / "run" / "frames" / f"{c}.hits.jsonl")
        == sha256_file(det / "run" / "frames" / f"{c}.hits.jsonl")
        for c in ("BASELINE", COMPLETE)
    }
    ver = read_json(out / "verify" / "verify.json")
    sel = read_json(out / "sample" / "selection.json")
    run = read_json(out / "run" / "run.json")
    vb = read_json(out / "run" / "verify_baseline.json")
    frames = read_json(out / "diff" / "frames.json")
    plan = read_json(out / "sample" / "decision_plan.json")
    asg = read_json(out / "assign" / "assignments.json")
    pw = read_json(out / "sample" / "operational_power.json")
    rec = {
        "WARNING": "dry run on the 120 development texts with the real candidate families and "
        "synthetic labels: exercises the harness only; the development texts informed the fixes, "
        "so nothing here is held-out evidence about the candidate",
        "key": key,
        "production_eligible": False,
        "candidate": {
            "checkout": run["checkout"],
            "snapshot": run["candidate_src"],
            "label": snap.get("label"),
            "git": run["candidate_snapshot"]["git"],
            "tree_sha256": snap["tree_sha256"],
            "families_module": run["families_module"],
            "families_module_sha256": run["metas"][COMPLETE]["families_module_sha256"],
            "uv_lock_sha256": run["checkout_uv_lock_sha256"],
        },
        "run_production_eligible": run["production_eligible"],
        "run_ineligible_reasons": run["ineligible_reasons"],
        "verify_baseline": {
            "identical": vb["identical"],
            "problems": vb["problems"],
            "n_hits": [vb["n_a"], vb["n_b"]],
            "pinned": vb.get("pinned", {}).get("commit"),
        },
        "hits": {c: m["n_hits"] for c, m in run["metas"].items()},
        "crosswalk_version": frames.get("crosswalk_version"),
        "frames": frame_summary(frames, plan),
        "overlaps": frames["overlaps"],
        "optimistic_marginal_benchmark": plan["cumulative"],
        "operational_power": {
            k: pw[k] for k in ("model", "reps", "seed", "structure", "assumptions")
        },
        "attainable": pw["attainable"],
        "operational_power_headline": power_headline(pw),
        "baseline_success_sample": {
            "N": sel["baseline_success"]["N"],
            "n": sel["baseline_success"]["n"],
            "n_strata": {m: len(sel["baseline_success"]["strata"][m]) for m in MODULES},
        },
        "label_units": sel["label_units"]["n_units"],
        "label_units_by_module": sel["label_units"]["by_module"],
        "assignments": asg,
        "scenarios": summary,
        "determinism": {
            "worker_frames_identical": worker_det,
            "steps_identical": {
                name: d["identical"]
                for (name, *_), d in zip(compare, ver["determinism"], strict=True)
            },
        },
        "verify_ok": ver["ok"],
        "ledger_ok": ver["ledger"]["ok"],
        "ledger_md": ver["ledger"]["ledger_md"].get("file"),
        "ledger_md_sha256": ver["ledger"]["ledger_md"].get("sha256"),
        "kept_family_identity": kept_identity,
        "blinding_ok": ver["blinding"]["ok"],
        "blinding_problems": ver["blinding"]["problems"][:20],
        "pair_only_counterfactual": ver["pair_only_counterfactual"],
        "harness_dir": str(HERE),
    }
    write_json(out / "dryrun_summary.json", rec)
    evidence = None
    if kept_identity is not None:
        from fixcheck import narrowing as NC

        evidence = narrowing_evidence(out, key, kept_identity, rec)
        write_json(out / NC.FILENAME, evidence)
    set_command("dryrun", argv)  # the sub-steps above recorded their own commands
    write_step_manifest(
        out,
        "dryrun",
        [out / "dryrun_summary.json", out / "DRYRUN_KEY.json"]
        + ([out / "NARROWING_CHECK.json"] if evidence is not None else [])
        + [p for s in SCENARIOS for p in (out / s / "labels").glob("*.jsonl")],
    )
    print(
        json.dumps(
            {
                k: rec[k]
                for k in (
                    "key",
                    "verify_baseline",
                    "scenarios",
                    "determinism",
                    "kept_family_identity",
                )
            },
            indent=1,
        )
    )
    ok = verify_rc == 0 and all(worker_det.values()) and vb["identical"]
    ok = ok and (evidence is None or evidence["ok"])
    return 0 if ok else 1
