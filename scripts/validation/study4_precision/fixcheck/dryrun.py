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
from fixcheck.ledger import COMPLETE, FAMILIES, FAMILY_MODULE, MODULES

DEFAULT_OUT_ROOT = REPO / ".cache" / "validation" / "study4_fix040" / "harness_dryrun" / "real_r5"
PINNED_SRC = REPO / ".cache" / "validation" / "study4_fix040" / "equivalence" / "baseline_033_src"
LABEL_SEED = 20261117  # synthetic labels only; the round seed is round_dev's collection seed
DEMO_COLLECT_SEED = 20261118
SCENARIOS = ("random", "favourable")  # session roots: fresh random temp dirs (audit r2 B3)


def dev_round_dir(out: Path, candidate: dict[str, Any], spec: Path | None = None) -> Path:
    """The development texts as a dry-run round: texts, freeze record (binding the delivery
    spec, audit r2 B3), collection, execution and the collect manifest."""
    from fixcheck import freeze as FZ
    from fixcheck.common import source_hashes

    d = out / "round_dev"
    if (d / "execution.json").exists():
        return d
    (d / "texts").mkdir(parents=True, exist_ok=True)
    rows = []
    for t in read_jsonl(build.DEV_TEXTS):
        text = (build.DEV_OUT / "texts" / f"{t['text_id']}.txt").read_text(encoding="utf-8")
        (d / "texts" / f"{t['text_id']}.txt").write_text(text, encoding="utf-8")
        rows.append(t | {"text_sha256": sha256_text(text)})
    (d / "texts.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), "utf-8"
    )
    from fixcheck.ledger import DRAFT_LEDGER_MD as LEDGER_MD

    fr = {
        "kind": FZ.FREEZE_KIND,
        "version": FZ.FREEZE_VERSION,
        "dry_run": True,
        "round": 1,
        "seed": build.DEV_SEED,
        "note": "development texts as a check round: DRY RUN ONLY, never a fix-check round",
        "candidate": candidate,
        "ledger": FZ.ledger_identity(LEDGER_MD, out / "ledger" / "ledger_components.json"),
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
    args = ap.parse_args(argv)
    if "lexinspect" in sys.modules:
        raise SystemExit("lexinspect was imported before the candidate snapshot was put first")
    settings = {
        "plan_reps": args.plan_reps,
        "power_reps": args.power_reps,
        "pinned_src": str(args.pinned_src.resolve()),
        "label_seed": LABEL_SEED,
        "demo_collect_seed": DEMO_COLLECT_SEED,
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
    from fixcheck.ledger import DRAFT_LEDGER_MD

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
                str(DRAFT_LEDGER_MD),
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
    rd = dev_round_dir(out, candidate, spec)
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
                str(DRAFT_LEDGER_MD),
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
        str(DRAFT_LEDGER_MD),
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
        "blinding_ok": ver["blinding"]["ok"],
        "blinding_problems": ver["blinding"]["problems"][:20],
        "pair_only_counterfactual": ver["pair_only_counterfactual"],
        "harness_dir": str(HERE),
    }
    write_json(out / "dryrun_summary.json", rec)
    set_command("dryrun", argv)  # the sub-steps above recorded their own commands
    write_step_manifest(
        out,
        "dryrun",
        [out / "dryrun_summary.json", out / "DRYRUN_KEY.json"]
        + [p for s in SCENARIOS for p in (out / s / "labels").glob("*.jsonl")],
    )
    print(
        json.dumps(
            {k: rec[k] for k in ("key", "verify_baseline", "scenarios", "determinism")}, indent=1
        )
    )
    ok = verify_rc == 0 and all(worker_det.values()) and vb["identical"]
    return 0 if ok else 1
