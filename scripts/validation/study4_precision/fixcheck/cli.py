"""Study 4 fix-check harness: command line.

    uv run python -I scripts/validation/study4_precision/fixcheck/cli.py <subcommand> ...

Subcommands, in protocol order:
  ledger           write ledger_components.json (J = 68 component identities, a = .05/68)
  collect          --plan-only (freeze_record.json), then --execute --freeze-record; or
                   --dry-run (ineligible one step); --replay-round, --replay-development
  prepare-pinned   extract the pinned baseline commit (dec79bc) into a separate directory
  prepare-candidate  --commit C: snapshot src/lexinspect from git archive (production);
                   --from-working-tree: interim candidate digest (not production-eligible)
  run              full hit frames: BASELINE, COMPLETE, each family alone (+ BASELINE_PINNED
                   with --pinned-src or --pinned-checkout)
  verify-baseline  only([]) vs the pinned 0.3.3 code: identical hit sequences, source, uv.lock
  diff             crosswalk, change-type partition, frames and overlaps (no labels)
  sample           SRS per frame, baseline-success sample, label units, decision plan,
                   operational power and feasible attainable bounds (operational_power.json)
  power            recompute operational_power.json for a sample (B5)
  assign           blinded items, key, A/B batches with paired claims separated
  delivery-spec    freeze the session delivery spec (registered prompt, materials, routes)
  export-sessions  one neutral session directory per batch (primary, retry, flash)
  stage-receipt    the pre-delivery receipt of a stage (hashes only; committed and pushed
                   before export-sessions in production)
  gather-labels    concatenate delivered session labels into a role's label file
  retry            the single registered retry: manifests and separated retry batches
  flash            validate A/B, needs_adjudication, adjudicator assignment
  accept           --package P: hash-chain check, then the frozen acceptance calculation
  register-failure   register a failed, killed or aborted execution as procedure_failure
                   (evidence, failure archive, exposure inventory; no labels)
  register-terminal  append a terminal outcome (ship / revert_0.3.3 / amendment)
  scan-restricted  fragments / staged / whole-set: the restricted-content check before
                   every commit (paths and counts only; nonzero exit stops)
  verify           ledger check, blinding audit, determinism (byte) comparisons
  dryrun           end-to-end dry run on the development build (the real candidate
                   families, the 120 development texts as the check set, synthetic labels)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixcheck.common import set_command, write_json, write_step_manifest  # noqa: E402
from fixcheck.ledger import ledger_document  # noqa: E402


def main_ledger(argv: list[str]) -> int:
    set_command("ledger", argv)
    import argparse

    ap = argparse.ArgumentParser(prog="fixcheck ledger")
    ap.add_argument("--out", type=Path, required=True, help="directory")
    args = ap.parse_args(argv)
    out = args.out.resolve()
    write_json(out / "ledger_components.json", ledger_document())
    write_step_manifest(out, "ledger", [out / "ledger_components.json"])
    print(f"wrote {out / 'ledger_components.json'}")
    return 0


def main_power(argv: list[str]) -> int:
    set_command("power", argv)
    import argparse

    from fixcheck.common import derive_seed, read_json, sha256_file
    from fixcheck.power import operational_power

    ap = argparse.ArgumentParser(prog="fixcheck power")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--diff-dir", type=Path, required=True)
    ap.add_argument("--sample-dir", type=Path, required=True)
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, help="default <sample-dir>/operational_power.json")
    args = ap.parse_args(argv)
    sel = read_json(args.sample_dir / "selection.json")
    pw = operational_power(
        args.run_dir.resolve(),
        args.diff_dir.resolve(),
        sel,
        args.reps,
        derive_seed(sel["round_seed"], "operational_power"),
        jobs=args.jobs,
    )
    pw["production_eligible"] = sel.get("production_eligible", False)
    pw["selection_sha256"] = sha256_file(args.sample_dir / "selection.json")
    out = args.out or args.sample_dir / "operational_power.json"
    write_json(out, pw)
    print(f"wrote {out}")
    return 0


def main_terminal(argv: list[str]) -> int:
    set_command("register-terminal", argv)
    import argparse

    from fixcheck import registry as REG

    ap = argparse.ArgumentParser(prog="fixcheck register-terminal")
    ap.add_argument("--outcome", choices=REG.TERMINAL, required=True)
    ap.add_argument("--basis", required=True, help="acceptance.json path(s) or decision note")
    ap.add_argument("--registry", type=Path, default=REG.REGISTRY)
    args = ap.parse_args(argv)

    # the same integrity checks as a decision (audit r2 B2): canonical, committed,
    # append-only history; checked and appended atomically under the registry lock
    def make(entries):
        entry = {"type": "terminal", "outcome": args.outcome, "basis": args.basis}
        # audit r5 S1: the identical terminal already last in the registry is the rerun of
        # a command whose barrier failed; it is acknowledged ('present') only after the
        # barrier passes. A different terminal is refused ("already registered").
        if REG.same_terminal(entries, args.outcome, args.basis):
            return "present", [], entry
        probs = REG.check_terminal(entries, args.outcome)
        return ("refuse" if probs else "append"), probs, entry

    verdict, probs, _ = REG.atomic_append(args.registry, make, REG.REPO)
    if verdict not in ("append", "present"):
        raise SystemExit("refused:\n" + "\n".join(probs))
    tail = "" if verdict == "append" else " (already registered; durable barrier rechecked)"
    print(f"registered terminal outcome {args.outcome}{tail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    from fixcheck import (
        accept,
        assign,
        collect,
        crosswalk,
        dryrun,
        failure,
        run,
        sampling,
        scan,
        sessions,
        verify,
    )

    table = {
        "ledger": main_ledger,
        "collect": collect.main,
        "prepare-pinned": run.main_prepare_pinned,
        "prepare-candidate": run.main_prepare_candidate,
        "run": run.main,
        "verify-baseline": run.main_verify,
        "diff": crosswalk.main,
        "sample": sampling.main,
        "power": main_power,
        "delivery-spec": sessions.main_spec,
        "export-sessions": sessions.main_export,
        "gather-labels": sessions.main_gather,
        "stage-receipt": sessions.main_stage_receipt,
        "register-failure": failure.main,
        "register-terminal": main_terminal,
        "scan-restricted": scan.main,
        "assign": assign.main,
        "retry": assign.main_retry,
        "flash": assign.main_flash,
        "accept": accept.main,
        "verify": verify.main,
        "dryrun": dryrun.main,
    }
    if cmd not in table:
        print(f"unknown subcommand {cmd!r}\n{__doc__}", file=sys.stderr)
        return 2
    return table[cmd](rest)


if __name__ == "__main__":
    raise SystemExit(main())
