"""`sample`: frame samples, shared label units, and the pre-label decision plan.

Protocol "Allocation", "Candidate and frames", "Counterparts".

Frames (one per configuration c in COMPLETE + the 12 families, module m):
  c|m|affected|<cell>  for the six affected-baseline cells (REMOVED,
                       REASSIGNED, SPAN_CHANGED, MULTIPLICITY,
                       DISPLAY_CONTEXT_CHANGED, CLAIM_DROPPED); population =
                       baseline hit ids;
  c|m|final|ADDED      new outputs (candidate hit ids);
  c|m|final|CHANGED    changed-claim counterparts (candidate hit ids).
The genuine-deletion frame of the removal gate IS the REMOVED cell (the same
population: baseline hits with no counterpart at the same occurrence; ruling
A1), so one SRS serves both the removal bound and the REMOVED cell of U_loss.
A claim dropped at a span where the candidate keeps another claim is the
separate CLAIM_DROPPED cell (audit r2 B4): it enters U_loss, never the removal
gate.

Each frame: simple random sample without replacement of n = min(200, N):
the population sorted by hit id, then random.Random(seed).sample(population,
n); N <= 200 is a census; N = 0 is recorded. The round seed is the seed in
the round's collection.json, archived before collection; `sample` refuses
any other value. seed = common.derive_seed(round seed, frame id), i.e. the first 64 bits of sha256("fixcheck-v1|{round
seed}|{frame id}"): independent seeds per frame, all archived with the
inclusion probability n/N.

Baseline-success denominator: a separate stratified sample of BASELINE hits
drawn by build.draw itself (the registered allocation: metadiscourse 100 per
category, PHRASE 300 water-filled over K-band x multi-sense strata, 15% marker
sub-strata), with build.SEED = derive_seed(round seed, "BASELINE_SUCCESS"),
the polysemous-rank set recorded by the BASELINE run, and the hits fed in hit
id order. Its sub-stratum N_h and n_h are archived; inclusion n_h/N_h.

Counterparts: for every sampled affected baseline hit, every linked candidate
counterpart is added to the label set (role "counterpart"; it is not a sample
of final outputs and carries no inclusion probability). Each counterpart
membership carries its own link's resolution (crosswalk links[].resolved, audit
r1 B4). Every same-span candidate hit that is not a counterpart is added with
role "sibling" (resolved True): it can retain the occurrence under the inventory
outcome (LENIENT / LIST_LENIENT) only, never under STRICT. Shared payloads: units
are distinct payload hashes; a payload is labelled once and keeps every
membership (frame, row, role). Each unit also records its occurrences: every
(source id, text hash, module, span) at which one of its rows was emitted.
assign.py uses them to keep different claims about one occurrence out of
the same batch.

Pre-label decision plan (`decision_plan`): for every removal frame, the
attainable upper bound with no sampled success (k_hi = 0), the largest k_hi
that still passes .15, whether a breach certificate is attainable at all, and
the probability of passing at specified true success shares among deletions;
for each module's cumulative gates, U_loss with no sampled loss divided by
L_success with every sampled baseline item successful (best attainable) and
with the assumed share successful (attainable at the planning share), and
simulated pass probabilities at specified true loss fractions, under stated
planning assumptions (all labels resolved; baseline success shares from the
development labels, unweighted). Its simulated pass probabilities are an
OPTIMISTIC MARGINAL BENCHMARK (audit r1 M1), labelled as such, with integer
targets, realised fractions and Wilson intervals. The operational power of the
frozen acceptance path (fixcheck/power.py: crosswalk links, worst-case
completion, all gates jointly) and the feasible attainable bounds are written to
operational_power.json (audit r1 B5). Every output carries production_eligible
from run.json.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import build
import estimators as E

from fixcheck.common import (
    derive_seed,
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    write_json,
    write_jsonl,
    write_step_manifest,
)
from fixcheck.crosswalk import AFFECTED_CELLS, FINAL_FRAMES, REMOVED
from fixcheck.ledger import (
    BASELINE,
    COMPLETE,
    CUMULATIVE_TOLERANCE,
    FAMILIES,
    GATED_OUTCOMES,
    MODULES,
    REMOVAL_TOLERANCE,
    A,
)

SRS_MAX = 200
BASELINE_SUCCESS = "BASELINE_SUCCESS"
# Planning assumptions only (unweighted definite-correct shares of the development
# references, dev_error_table.jsonl): never used in any acceptance calculation.
PLAN_SUCCESS_SHARE = {
    ("metadiscourse", "STRICT"): 621 / 1000,
    ("metadiscourse", "LENIENT"): 690 / 1000,
    ("phrase", "STRICT"): 201 / 300,
    ("phrase", "LIST_LENIENT"): 202 / 300,
}
PLAN_REMOVAL_SHARES = (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30)
PLAN_LOSS_FRACTIONS = (0.0, 0.005, 0.01, 0.02, 0.05)


def round_seed_of(run_dir: Path, given: int | None) -> int:
    """The round's one seed: the collection seed archived before collection (protocol
    "Fixed before collection"). Every frame seed derives from it; no other is accepted."""
    run = read_json(run_dir / "run.json")
    col_path = Path(run["round_dir"]) / "collection.json" if run.get("round_dir") else None
    archived = read_json(col_path)["seed"] if col_path and col_path.exists() else None
    if archived is None:
        if given is None:
            raise SystemExit("no collection.json seed for this run: pass --round-seed")
        return given
    if given is not None and given != archived:
        raise SystemExit(f"--round-seed {given} is not the round's archived seed {archived}")
    return int(archived)


def frame_ids(configs: list[str]) -> list[tuple[str, str, str, str]]:
    """(frame_id, config, module, part) in a fixed order."""
    out = []
    for c in configs:
        for m in MODULES:
            for cell in AFFECTED_CELLS:
                out.append((f"{c}|{m}|affected|{cell}", c, m, f"affected|{cell}"))
            for fr in FINAL_FRAMES:
                out.append((f"{c}|{m}|final|{fr}", c, m, f"final|{fr}"))
    return out


def srs(
    population: list[str], round_seed: int, frame_id: str, n_max: int = SRS_MAX
) -> dict[str, Any]:
    pop = sorted(population)
    if len(set(pop)) != len(pop):
        raise ValueError(f"{frame_id}: duplicate ids in the frame")
    n = min(n_max, len(pop))
    seed = derive_seed(round_seed, frame_id)
    chosen = sorted(random.Random(seed).sample(pop, n))
    return {
        "frame": frame_id,
        "N": len(pop),
        "n": n,
        "census": len(pop) <= n_max,
        "seed_label": f"fixcheck-v1|{round_seed}|{frame_id}",
        "seed": seed,
        "inclusion_probability": (n / len(pop)) if pop else None,
        "selected": chosen,
    }


@contextlib.contextmanager
def _build_seed(seed: int, poly: set[int]):
    old_seed, old_poly = build.SEED, build.polysemous_ranks
    build.SEED = seed
    build.polysemous_ranks = lambda: set(poly)
    try:
        yield
    finally:
        build.SEED, build.polysemous_ranks = old_seed, old_poly


def baseline_success_sample(
    base: list[dict[str, Any]], poly: set[int], round_seed: int
) -> dict[str, Any]:
    """build.draw on the BASELINE frame (copies), seeded for this round."""
    hits = []
    for r in sorted(base, key=lambda r: r["hit_id"]):
        hits.append(
            {
                **r["raw"],
                "module": r["module"],
                "text_id": r["text_id"],
                "span": r["span"],
                "hit_id": r["hit_id"],
            }
        )
    seed = derive_seed(round_seed, BASELINE_SUCCESS)
    with _build_seed(seed, poly):
        sampled, design = build.draw(hits)
    strata: dict[str, Any] = {m: {} for m in MODULES}
    for h in sampled:
        d = strata[h["module"]].setdefault(
            h["substratum"], {"N_h": h["N_sub"], "n_h": h["n_sub"], "selected": []}
        )
        d["selected"].append(h["hit_id"])
    for m, subs in design.items():
        for st, d in subs.items():
            for sub, s in d["substrata"].items():
                key = f"{st}|{sub}"
                strata[m].setdefault(key, {"N_h": s["N"], "n_h": s["n"], "selected": []})
                if strata[m][key]["N_h"] != s["N"] or strata[m][key]["n_h"] != s["n"]:
                    raise AssertionError(f"design mismatch in {m} {key}")
    for m in MODULES:
        for d in strata[m].values():
            d["selected"].sort()
            if len(d["selected"]) != d["n_h"]:
                raise AssertionError("sub-stratum sample size mismatch")
        n_mod = sum(r["module"] == m for r in base)
        covered = sum(d["N_h"] for d in strata[m].values())
        if covered != n_mod:
            raise AssertionError(f"{m}: baseline strata cover {covered} of {n_mod} hits")
    return {
        "frame": BASELINE_SUCCESS,
        "seed_label": f"fixcheck-v1|{round_seed}|{BASELINE_SUCCESS}",
        "seed": seed,
        "allocation": "build.draw: metadiscourse MD_TARGET per category, PHRASE PHRASE_TARGET "
        "water-filled over K-band x multi-sense strata, CAP_FRAC marker sub-strata",
        "targets": {
            "metadiscourse": build.MD_TARGET * len(build.MD_CATEGORIES),
            "phrase": build.PHRASE_TARGET,
        },
        "N": {m: sum(r["module"] == m for r in base) for m in MODULES},
        "n": {m: sum(d["n_h"] for d in strata[m].values()) for m in MODULES},
        "strata": strata,
    }


def removal_plan(N: int, n: int, a: float = A, tol: float = REMOVAL_TOLERANCE) -> dict[str, Any]:
    if N == 0:
        return {"N": 0, "n": 0, "status": "not_applicable (empty deletion frame)"}
    best = E.hyper_ucl(0, n, N, a) / N
    kmax = -1
    for k in range(n + 1):
        if E.hyper_ucl(k, n, N, a) / N <= tol:
            kmax = k
        else:
            break
    power = {}
    for p in PLAN_REMOVAL_SHARES:
        T = math.floor(p * N)
        power[str(p)] = E.hyper_cdf(kmax, N, T, n) if kmax >= 0 else 0.0
    return {
        "N": N,
        "n": n,
        "attainable_upper_bound_if_no_success": best,
        "gate_passable": best <= tol,
        "max_k_hi_passing": kmax,
        "breach_certificate_attainable": n > math.floor(tol * N),
        "min_definite_successes_for_breach_certificate": math.floor(tol * N) + 1,
        "pass_probability_at_true_success_share": power,
        "assumption": "every sampled reference resolved; pass probability = "
        "P(K <= max_k_hi_passing), K ~ Hypergeometric(N, floor(p N), n)",
    }


def _u_loss(cells: list[tuple[int, int, int, int]], a: float) -> float:
    pos = [c for c in cells if c[0] > 0]
    if not pos:
        return 0.0
    return sum(c[0] for c in pos) * E.exact_limits(pos, None, a)["upper"]


def _l_success(cells: list[tuple[int, int, int, int]], a: float) -> float | None:
    pos = [c for c in cells if c[0] > 0]
    if not pos:
        return None
    return sum(c[0] for c in pos) * E.exact_limits(pos, a, None)["lower"]


def cumulative_plan(
    affected: list[tuple[int, int]],
    baseline: list[tuple[int, int]],
    share: float,
    reps: int,
    seed: int,
    a: float = A,
    tol: float = CUMULATIVE_TOLERANCE,
) -> dict[str, Any]:
    """affected/baseline: [(N_h, n_h)]. Best attainable ratio and simulated pass probabilities."""
    n_aff = sum(N for N, _ in affected)
    n_base = sum(N for N, _ in baseline)
    u0 = _u_loss([(N, n, 0, 0) for N, n in affected], a)
    l1 = _l_success([(N, n, n, n) for N, n in baseline], a)
    best = None if not l1 else min(1.0, u0 / l1)
    ks = [min(n, round(share * n)) for _, n in baseline]
    l_share = _l_success([(N, n, k, k) for (N, n), k in zip(baseline, ks, strict=True)], a)
    at_share = None if not l_share else min(1.0, u0 / l_share)
    rng = random.Random(seed)
    sims = {}
    for lam in PLAN_LOSS_FRACTIONS:
        if reps <= 0:
            break
        total_loss = min(n_aff, round(lam * share * n_base))
        # spread the true losses over affected cells proportionally to N_h (largest remainder)
        quota = [total_loss * N / n_aff if n_aff else 0 for N, _ in affected]
        T_aff = [min(N, int(q)) for q, (N, _) in zip(quota, affected, strict=True)]
        left = total_loss - sum(T_aff)
        for i in sorted(range(len(affected)), key=lambda i: -(quota[i] - int(quota[i]))):
            if left <= 0:
                break
            if T_aff[i] < affected[i][0]:
                T_aff[i] += 1
                left -= 1
        T_base = [round(share * N) for N, _ in baseline]
        passes = 0
        for _ in range(reps):
            ca = [
                (N, n, k, k)
                for (N, n), T in zip(affected, T_aff, strict=True)
                for k in [_hyper_draw(rng, N, T, n)]
            ]
            cb = [
                (N, n, k, k)
                for (N, n), T in zip(baseline, T_base, strict=True)
                for k in [_hyper_draw(rng, N, T, n)]
            ]
            u = _u_loss(ca, a)
            lo = _l_success(cb, a)
            if lo and min(1.0, u / lo) <= tol:
                passes += 1
        sims[str(lam)] = {
            "p": passes / reps,
            "realised_loss_fraction": total_loss / max(1, sum(T_base)),
            "wilson95": _wilson(passes, reps),
        }
    return {
        "label": "optimistic marginal benchmark (not operational power; audit r1 M1): one "
        "outcome, all labels resolved, no crosswalk links or unresolved correspondences; the "
        "operational power of the frozen acceptance path is in operational_power.json",
        "integer_targets": {
            str(lam): {
                "true_losses": min(n_aff, round(lam * share * n_base)),
                "baseline_successes": sum(round(share * N) for N, _ in baseline),
            }
            for lam in PLAN_LOSS_FRACTIONS
        },
        "N_affected": n_aff,
        "N_baseline": n_base,
        "best_attainable_U_loss": u0,
        "best_attainable_L_success": l1,
        "best_attainable_fraction": best,
        "L_success_at_assumed_share": l_share,
        "attainable_fraction_at_assumed_share": at_share,
        "gate_passable": best is not None and best <= tol,
        "assumed_baseline_success_share": share,
        "simulated_pass_probability_at_true_loss_fraction": sims,
        "reps": reps,
        "assumption": "all labels resolved; true losses spread over affected cells in proportion "
        "to N_h; baseline successes = round(share x N_h) per stratum; loss fraction = lost "
        "successes / baseline successes",
    }


def _wilson(k: int, n: int) -> list[float] | None:
    from fixcheck.power import wilson

    return wilson(k, n)


def _hyper_draw(rng: random.Random, N: int, T: int, n: int) -> int:
    if n >= N:
        return T
    pop = [1] * T + [0] * (N - T)
    return sum(rng.sample(pop, n))


def decision_plan(selection: dict[str, Any], reps: int, round_seed: int) -> dict[str, Any]:
    frames = selection["frames"]
    out: dict[str, Any] = {"a": A, "reps": reps, "removal": {}, "cumulative": {}}
    for fid, f in frames.items():
        if fid.endswith(f"|affected|{REMOVED}"):
            out["removal"][fid] = removal_plan(f["N"], f["n"])
    bs = selection["baseline_success"]
    for m in MODULES:
        aff = [
            (
                frames[f"{COMPLETE}|{m}|affected|{cell}"]["N"],
                frames[f"{COMPLETE}|{m}|affected|{cell}"]["n"],
            )
            for cell in AFFECTED_CELLS
            if f"{COMPLETE}|{m}|affected|{cell}" in frames
        ]
        base = [(d["N_h"], d["n_h"]) for _, d in sorted(bs["strata"][m].items())]
        for oc in GATED_OUTCOMES[m]:
            out["cumulative"][f"{m}|{oc}"] = cumulative_plan(
                aff,
                base,
                PLAN_SUCCESS_SHARE[(m, oc)],
                reps,
                derive_seed(round_seed, f"plan|{m}|{oc}"),
            )
    return out


def main(argv: list[str]) -> int:
    set_command("sample", argv)
    ap = argparse.ArgumentParser(prog="fixcheck sample", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--diff-dir", type=Path, required=True)
    ap.add_argument(
        "--round-seed",
        type=int,
        help="default and only accepted value: the seed in the round's collection.json",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--plan-reps", type=int, default=200)
    ap.add_argument(
        "--power-reps",
        type=int,
        default=200,
        help="operational-power replicates per scenario (B5); 0 = attainable bounds only, "
        "-1 = skip",
    )
    ap.add_argument("--jobs", type=int, default=1, help="processes for the power simulation")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    run_dir, diff_dir, out = args.run_dir.resolve(), args.diff_dir.resolve(), args.out.resolve()
    refuse_existing(out / "selection.json", args.overwrite)
    fr = read_json(diff_dir / "frames.json")
    args.round_seed = round_seed_of(run_dir, args.round_seed)
    configs = fr["configs"]
    base = read_jsonl(run_dir / "frames" / f"{BASELINE}.hits.jsonl")
    base_by_id = {r["hit_id"]: r for r in base}
    poly = set(read_json(run_dir / "frames" / f"{BASELINE}.meta.json")["polysemous_ranks"])

    run_meta = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    selection: dict[str, Any] = {
        "round_seed": args.round_seed,
        "srs_max": SRS_MAX,
        "production_eligible": bool(run_meta.get("production_eligible", False)),
        "frames": {},
    }
    for fid, c, m, part in frame_ids(configs):
        kind, name = part.split("|")
        f = fr["frames"][c][m]
        pop = f["affected_cells"][name] if kind == "affected" else f["final_frames"][name]
        selection["frames"][fid] = srs(pop, args.round_seed, fid)
    selection["baseline_success"] = baseline_success_sample(base, poly, args.round_seed)

    # Label units: distinct payloads with every membership.
    units: dict[str, dict[str, Any]] = {}

    def add(row: dict[str, Any], membership: dict[str, Any]) -> None:
        u = units.setdefault(
            row["payload_sha256"],
            {
                "payload_sha256": row["payload_sha256"],
                "module": row["module"],
                "payload": row["payload"],
                "memberships": [],
                "occurrences": [],
            },
        )
        if u["payload"] != row["payload"]:
            raise AssertionError("payload hash collision")
        u["memberships"].append(membership)
        occ = [row["source_id"], row["text_sha256"], row["module"], *row["span"]]
        if occ not in u["occurrences"]:
            u["occurrences"].append(occ)

    need_cand: dict[str, set[str]] = defaultdict(set)
    links: dict[str, dict[str, dict[str, Any]]] = {}
    for c in configs:
        links[c] = {r["hit_id"]: r for r in read_jsonl(diff_dir / "links" / f"{c}.baseline.jsonl")}
    for fid, c, _m, part in frame_ids(configs):
        sel = selection["frames"][fid]
        for h in sel["selected"]:
            if part.startswith("affected"):
                need_cand[c].update(links[c][h]["counterparts"])
                need_cand[c].update(links[c][h].get("siblings", []))
            else:
                need_cand[c].add(h)
    cand_rows: dict[str, dict[str, dict[str, Any]]] = {}
    for c in configs:
        want = need_cand[c]
        cand_rows[c] = {}
        with (run_dir / "frames" / f"{c}.hits.jsonl").open(encoding="utf-8") as fh:
            import json

            for line in fh:
                r = json.loads(line)
                if r["hit_id"] in want:
                    cand_rows[c][r["hit_id"]] = r
    for fid, c, _m, part in frame_ids(configs):
        sel = selection["frames"][fid]
        for h in sel["selected"]:
            if part.startswith("affected"):
                b = base_by_id[h]
                add(
                    b,
                    {
                        "frame": fid,
                        "row": h,
                        "role": "sampled",
                        "inclusion": sel["inclusion_probability"],
                    },
                )
                # One membership per crosswalk link, with that link's own resolution
                # (audit r1 B4); same-span siblings retain under the inventory outcome only.
                for lk in links[c][h]["links"]:
                    add(
                        cand_rows[c][lk["hit"]],
                        {
                            "frame": fid,
                            "row": lk["hit"],
                            "role": "counterpart",
                            "of": h,
                            "resolved": bool(lk["resolved"]),
                        },
                    )
                for sid in links[c][h].get("siblings", []):
                    add(
                        cand_rows[c][sid],
                        {"frame": fid, "row": sid, "role": "sibling", "of": h, "resolved": True},
                    )
            else:
                add(
                    cand_rows[c][h],
                    {
                        "frame": fid,
                        "row": h,
                        "role": "sampled",
                        "inclusion": sel["inclusion_probability"],
                    },
                )
    for m in MODULES:
        for sub, d in selection["baseline_success"]["strata"][m].items():
            for h in d["selected"]:
                add(
                    base_by_id[h],
                    {
                        "frame": f"{BASELINE_SUCCESS}|{m}",
                        "row": h,
                        "role": "sampled",
                        "substratum": sub,
                        "inclusion": d["n_h"] / d["N_h"],
                    },
                )
    unit_rows = [units[k] for k in sorted(units)]
    for u in unit_rows:
        u["memberships"].sort(key=lambda x: (x["frame"], x["row"], x["role"], x.get("of", "")))
        u["occurrences"].sort()
    # Overlaps: label units shared between frames.
    frame_units: dict[str, set[str]] = defaultdict(set)
    for u in unit_rows:
        for mb in u["memberships"]:
            frame_units[mb["frame"]].add(u["payload_sha256"])
    shared = {}
    names = sorted(frame_units)
    for i, x in enumerate(names):
        for y in names[i + 1 :]:
            k = len(frame_units[x] & frame_units[y])
            if k:
                shared[f"{x} & {y}"] = k
    selection["label_units"] = {
        "n_units": len(unit_rows),
        "by_module": {m: sum(u["module"] == m for u in unit_rows) for m in MODULES},
        "units_per_frame": {k: len(v) for k, v in sorted(frame_units.items())},
        "shared_units_between_frames": shared,
    }
    selection["inputs"] = {
        "frames_json_sha256": sha256_file(diff_dir / "frames.json"),
        "baseline_hits_sha256": sha256_file(run_dir / "frames" / f"{BASELINE}.hits.jsonl"),
    }
    write_json(out / "selection.json", selection)
    write_jsonl(out / "units.jsonl", unit_rows)
    plan = decision_plan(selection, args.plan_reps, args.round_seed)
    write_json(out / "decision_plan.json", plan)
    outputs = [out / "selection.json", out / "units.jsonl", out / "decision_plan.json"]
    if args.power_reps >= 0:
        from fixcheck.power import operational_power

        pw = operational_power(
            run_dir,
            diff_dir,
            selection,
            args.power_reps,
            derive_seed(args.round_seed, "operational_power"),
            jobs=args.jobs,
        )
        pw["production_eligible"] = selection["production_eligible"]
        pw["selection_sha256"] = sha256_file(out / "selection.json")
        write_json(out / "operational_power.json", pw)
        outputs.append(out / "operational_power.json")
    write_step_manifest(out, "sample", outputs)
    print(
        f"label units: {selection['label_units']['n_units']} {selection['label_units']['by_module']}"
    )
    return 0


__all__ = ["FAMILIES", "main"]
