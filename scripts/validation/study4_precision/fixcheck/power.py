"""Operational power and feasible attainable bounds of the frozen acceptance path (audit r1
B5, M1). Pre-label: uses frames, crosswalk links and the registered samples only.

What it computes (frozen before labels; nothing here is chosen from check outcomes):

1. FEASIBLE ATTAINABLE BOUNDS on the archived selection. One coherent set of
   references for every sampled payload (a payload has one reference, shared by
   every frame and role it belongs to) is put through accept.compute:
   - "most favourable feasible": every sampled affected baseline payload (COMPLETE
     cells and every removal frame) is 0; every counterpart and sibling payload 1;
     every other baseline-success payload 1. A payload in both an affected sample
     and the baseline-success sample is 0 (it cannot be both);
   - "maximal denominator": every baseline-success payload is 1, the shared ones
     included (so a shared REMOVED payload becomes a sampled loss, and a shared
     unresolved row a possible loss); other affected payloads 0;
   - "a feasible value found by the declared greedy search": two coordinate passes
     over the shared payloads from the better of the two, keeping a flip only if it
     improves, lexicographically, (candidate status: pass < inconclusive < fail;
     number of gates not passed; largest cumulative fraction). It is not a certified
     optimum and its sampled losses and removal successes need not be zero; their
     exact counts are reported with it (audit r2 S4).
   Every reported configuration is feasible, so its gate values are attainable;
   the best attainable value is at most the value reported. Nothing here licenses an
   inverse inference from an observed status to a true loss level.

2. OPERATIONAL POWER. For each scenario a fixed finite population of references
   is built (below), the registered sampling design is redrawn R times (SRS of
   min(200, N) per frame, the same draw serving the REMOVED cell and the removal
   frame; the baseline-success sub-strata of build.draw with their archived N_h
   and n_h, SRS within each), and each replicate runs accept.compute (gated
   arithmetic only), with the actual crosswalk links, sibling links and
   worst-case completion. Reported: the probability that each gate passes, that
   each module passes, that ALL required gates pass (candidate status "pass") and
   of a breach certificate ("fail"), each with a Wilson 95% Monte Carlo interval.
   Common random numbers: the same R sample draws and the same baseline
   references serve every scenario.

POPULATION MODEL (declared). References have three levels per payload: 2 =
STRICT and inventory success, 1 = inventory success only, 0 = neither.
- Baseline payloads: level 2 with probability s_STRICT, 1 with s_INV - s_STRICT
  (development planning shares, sampling.PLAN_SUCCESS_SHARE).
- COMPLETE affected rows are split into UNRESOLVED rows (SPAN_CHANGED with no
  resolved link) and the rest. Unresolved rows keep their drawn level; whether a
  successful one is truly lost is the scenario's unresolved structure:
  "all_loss" (every one), "none_loss" (none; its counterparts carry its level), or
  "dev_share" (each unresolved row is a loss with probability q_dev, the
  development definite-loss share among determinable labelled affected rows:
  metadiscourse LENIENT 4/142, PHRASE LIST_LENIENT 1/56, from
  dev_collateral_families_r2b.json).
- Other affected rows: REMOVED and CLAIM_DROPPED rows start unsuccessful (a
  successful one would be a loss under STRICT, and under the inventory outcome
  too for REMOVED); the others keep their drawn level and are retained
  (counterparts carry the baseline level).
- Loss target: L = round(lambda x baseline inventory successes), lambda from the
  declared grid; the losses still needed after the unresolved ones are spread over
  the non-unresolved affected cells in proportion to N_h (largest remainder,
  capped by cell size) and drawn at random within a cell. A lost row is made
  successful (level 2 with probability s_STRICT/s_INV, else 1) and its counterparts
  and siblings unsuccessful. A retained row's counterparts carry at least its
  level (a counterpart shared by several retained rows takes the highest; one
  already made unsuccessful by a loss stays so). If the unresolved losses alone
  exceed L, the scenario
  is infeasible at that lambda and is reported with its realised lambda.
- A payload's level, once set, is never changed by a later row (coherence); the
  realised loss fractions (STRICT and inventory), realised removal success shares
  and integer totals are computed from the final references and reported (M1).
- MODULE-CALIBRATED scenarios (informational; audit r2 S4): instead of one lambda,
  per-module and per-outcome loss targets, as fractions of the realised baseline
  successes of that outcome: "S8_definite" uses the development definite-loss rates
  of dev_collateral_families.md S8 (metadiscourse LENIENT 3/690, STRICT 2/621;
  PHRASE LIST_LENIENT 1/202, STRICT 1/201) and "S8_upper" its upper rates
  (metadiscourse LENIENT 31/690, STRICT 6/621; PHRASE as definite, its upper rates
  equal its definite ones). Every unresolved row is retained (its counterparts
  carry its level) unless drawn as a loss; the L_INV losses are allocated over all
  affected cells, unresolved rows included, in proportion to N_h; L_STRICT of the
  lost rows (at most L_INV) are level 2 and the rest level 1. The target and the
  realised loss are reported separately.
- Labels: each sampled payload's reference is its level, except that with the
  pilot unresolved-reference rate (metadiscourse 2/1000, PHRASE (8/300)(2/86);
  preregistration) it is unresolved in a replicate.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import build

from fixcheck.common import derive_seed, read_json, read_jsonl
from fixcheck.crosswalk import AFFECTED_CELLS, CLAIM_DROPPED, REMOVED, SPAN_CHANGED
from fixcheck.ledger import BASELINE, COMPLETE, FAMILIES, INV, MODULES
from fixcheck.sampling import (
    BASELINE_SUCCESS,
    PLAN_LOSS_FRACTIONS,
    PLAN_SUCCESS_SHARE,
    SRS_MAX,
    _build_seed,
)

DEV_SHARE_UNRESOLVED_LOSS = {"metadiscourse": 4 / 142, "phrase": 1 / 56}
REF_UNRESOLVED_RATE = {"metadiscourse": 2 / 1000, "phrase": (8 / 300) * (2 / 86)}
STRUCTURES = ("all_loss", "none_loss", "dev_share")
CALIBRATED = "calibrated"
# S8 development definite-loss and upper rates (dev_collateral_families.md S8, ALL rows),
# as fractions of baseline successes, per module and outcome ("INV" = the inventory
# outcome, LENIENT for metadiscourse and LIST_LENIENT for PHRASE).
CALIBRATED_TARGETS = {
    "S8_definite": {
        "metadiscourse": {"INV": (3, 690), "STRICT": (2, 621)},
        "phrase": {"INV": (1, 202), "STRICT": (1, 201)},
    },
    "S8_upper": {
        "metadiscourse": {"INV": (31, 690), "STRICT": (6, 621)},
        "phrase": {"INV": (1, 202), "STRICT": (1, 201)},
    },
}
MODEL_VERSION = "fixcheck-power/2 (audit r1 B5, r2 S4)"


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo = 0.0 if k == 0 else max(0.0, c - h)
    hi = 1.0 if k == n else min(1.0, c + h)
    return [lo, hi]


# --- the population structure (frames, links, strata) ---------------------------------


def _payloads(path: Path, want: set[str] | None = None) -> dict[str, tuple[str, str]]:
    import json

    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if want is None or r["hit_id"] in want:
                out[r["hit_id"]] = (r["payload_sha256"], r["module"])
    return out


def strata_members(base_rows: list[dict[str, Any]], poly: set[int], round_seed: int) -> dict:
    """{module: {substratum: [hit ids]}}: build.draw's sub-strata, with every member."""
    hits = [
        {
            **r["raw"],
            "module": r["module"],
            "text_id": r["text_id"],
            "span": r["span"],
            "hit_id": r["hit_id"],
        }
        for r in sorted(base_rows, key=lambda r: r["hit_id"])
    ]
    with _build_seed(derive_seed(round_seed, BASELINE_SUCCESS), poly):
        _, design = build.draw(hits)
    out: dict[str, dict[str, list[str]]] = {m: defaultdict(list) for m in MODULES}
    for h in hits:
        if h["module"] == "metadiscourse":
            st, marker = h["category"], h["marker"]
        else:
            st, marker = build._phrase_stratum(h), h["phrase"]
        subs = design[h["module"]][st]["substrata"]
        sub = f"marker={marker}" if f"marker={marker}" in subs else "rest"
        out[h["module"]][f"{st}|{sub}"].append(h["hit_id"])
    return {m: dict(v) for m, v in out.items()}


class Structure:
    """Everything the simulation needs about one round, loaded once."""

    def __init__(self, run_dir: Path, diff_dir: Path, selection: dict[str, Any]):
        fr = read_json(diff_dir / "frames.json")
        self.configs = [c for c in (COMPLETE, *FAMILIES) if c in fr["frames"]]
        base_rows = read_jsonl(run_dir / "frames" / f"{BASELINE}.hits.jsonl")
        self.base = {r["hit_id"]: (r["payload_sha256"], r["module"]) for r in base_rows}
        links = {}
        import json

        with (diff_dir / "links" / f"{COMPLETE}.baseline.jsonl").open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["change_type"] != "UNCHANGED":
                    links[r["hit_id"]] = r
        need = {lk["hit"] for r in links.values() for lk in r.get("links", [])}
        need |= {s for r in links.values() for s in r.get("siblings", [])}
        cand = _payloads(run_dir / "frames" / f"{COMPLETE}.hits.jsonl", need)
        self.frame_pop: dict[str, list[str]] = {}
        for c in self.configs:
            for m in MODULES:
                cells = fr["frames"][c][m]["affected_cells"]
                self.frame_pop[f"{c}|{m}|affected|{REMOVED}"] = sorted(cells[REMOVED])
                if c == COMPLETE:
                    for cell in AFFECTED_CELLS:
                        self.frame_pop[f"{c}|{m}|affected|{cell}"] = sorted(cells[cell])
        self.cell_of: dict[str, str] = {}
        self.links: dict[str, list[tuple[str, bool, str]]] = {}
        self.unresolved: set[str] = set()
        for m in MODULES:
            for cell in AFFECTED_CELLS:
                for h in self.frame_pop[f"{COMPLETE}|{m}|affected|{cell}"]:
                    self.cell_of[h] = cell
                    r = links[h]
                    lk = [
                        (cand[x["hit"]][0], bool(x["resolved"]), "counterpart") for x in r["links"]
                    ]
                    lk += [(cand[s][0], True, "sibling") for s in r.get("siblings", [])]
                    self.links[h] = lk
                    if cell == SPAN_CHANGED and not r["resolved"]:
                        self.unresolved.add(h)
        poly = set(read_json(run_dir / "frames" / f"{BASELINE}.meta.json")["polysemous_ranks"])
        members = strata_members(base_rows, poly, selection["round_seed"])
        self.strata: dict[str, dict[str, tuple[list[str], int]]] = {}
        for m in MODULES:
            self.strata[m] = {}
            for sub, d in selection["baseline_success"]["strata"][m].items():
                pop = sorted(members[m].get(sub, []))
                if len(pop) != d["N_h"]:
                    raise AssertionError(f"{m} {sub}: {len(pop)} members, archived N_h {d['N_h']}")
                self.strata[m][sub] = (pop, d["n_h"])
        self.selection = selection

    # registered selection -> compute inputs
    def frames_for(self, chosen: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        frames = {}
        for fid, pop in self.frame_pop.items():
            rows = chosen[fid]
            frames[fid] = {
                "N": len(pop),
                "n": len(rows),
                "rows": {h: self.base[h][0] for h in rows},
                "counterparts": {h: self.links.get(h, []) for h in rows}
                if fid.startswith(COMPLETE)
                else {},
            }
        return frames

    def bs_for(self, chosen: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, Any]]:
        return {
            m: {
                sub: {
                    "N_h": len(self.strata[m][sub][0]),
                    "n_h": len(rows),
                    "rows": {h: self.base[h][0] for h in rows},
                }
                for sub, rows in chosen[m].items()
            }
            for m in MODULES
        }

    def archived_choice(self):
        fr = {fid: self.selection["frames"][fid]["selected"] for fid in self.frame_pop}
        bs = {
            m: {
                sub: d["selected"]
                for sub, d in self.selection["baseline_success"]["strata"][m].items()
            }
            for m in MODULES
        }
        return fr, bs

    def draw(self, seed: int, rep: int):
        fr = {}
        for fid, pop in self.frame_pop.items():
            r = random.Random(derive_seed(seed, f"rep{rep}|{fid}"))
            fr[fid] = sorted(r.sample(pop, min(SRS_MAX, len(pop))))
        bs = {}
        for m in MODULES:
            bs[m] = {}
            for sub, (pop, n) in self.strata[m].items():
                r = random.Random(derive_seed(seed, f"rep{rep}|{BASELINE_SUCCESS}|{m}|{sub}"))
                bs[m][sub] = sorted(r.sample(pop, n))
        return fr, bs


def _compute(st: Structure, frames, bs, refs):
    from fixcheck.accept import compute

    return compute(frames, bs, refs, st.configs, descriptive=False)


def _gates(res: dict[str, Any]) -> dict[str, bool | None]:
    g: dict[str, bool | None] = {}
    for m, mod in res["modules"].items():
        for c, r in mod["removal"].items():
            if r["status"] == "computed":
                g[f"{m}|removal|{c}"] = bool(r["passes"])
        for oc, cg in mod["cumulative"].items():
            g[f"{m}|cumulative|{oc}"] = bool(cg["status"] == "computed" and cg["passes"])
        g[f"{m}|module_pass"] = mod["status"] == "pass"
    g["ALL_REQUIRED_GATES_PASS"] = res["status"] == "pass"
    g["FAIL_BY_CERTIFICATE"] = res["status"] == "fail"
    return g


def _summary(res: dict[str, Any]) -> dict[str, Any]:
    out = {"status": res["status"]}
    for m, mod in res["modules"].items():
        out[m] = {
            "status": mod["status"],
            "removal_bounds": {
                c: r["bound"] for c, r in mod["removal"].items() if r["status"] == "computed"
            },
            # exact sampled counts behind the values (audit r2 S4)
            "removal_sampled_successes": {
                c: {"k_lo": r["k_lo"], "k_hi": r["k_hi"], "n": r["n"], "N": r["N"]}
                for c, r in mod["removal"].items()
                if r["status"] == "computed"
            },
            "sampled_losses": {
                oc: {
                    "k_lo": sum(c["k_lo"] for c in d["cells"].values()),
                    "k_hi": sum(c["k_hi"] for c in d["cells"].values()),
                    "n": sum(c["n_h"] for c in d["cells"].values()),
                }
                for oc, d in mod["loss"].items()
            },
            "cumulative": {
                oc: {"U_loss": g["U_loss"], "L_success": g["L_success"], "fraction": g["fraction"]}
                for oc, g in mod["cumulative"].items()
            },
        }
    return out


# --- feasible attainable bounds --------------------------------------------------------


def _refs_from_levels(levels: dict[str, int], unresolved: set[str] = frozenset()):
    refs: dict[tuple[str, str], dict[str, int | None]] = {}
    for m in MODULES:
        refs[(m, "STRICT")] = {}
        refs[(m, INV[m])] = {}
    for p, (lev, m) in levels.items():
        u = p in unresolved
        refs[(m, "STRICT")][p] = None if u else int(lev == 2)
        refs[(m, INV[m])][p] = None if u else int(lev >= 1)
    return refs


def attainable(st: Structure) -> dict[str, Any]:
    fr_ch, bs_ch = st.archived_choice()
    frames, bs = st.frames_for(fr_ch), st.bs_for(bs_ch)
    affected = {
        (p, st.base[h][1]) for fid, rows in fr_ch.items() for h in rows for p in [st.base[h][0]]
    }
    linked = {
        (q, st.base[h][1])
        for fid, rows in fr_ch.items()
        if fid.startswith(COMPLETE)
        for h in rows
        for q, _, _ in st.links.get(h, [])
    }
    base_pay = {(st.base[h][0], m) for m in MODULES for rows in bs_ch[m].values() for h in rows}
    aff_p = {p for p, _ in affected}
    shared = sorted(p for p, _ in base_pay if p in aff_p)

    def evaluate(zero: set[str]) -> tuple[dict, dict]:
        lev: dict[str, tuple[int, str]] = {}
        for p, m in linked:
            lev[p] = (2, m)
        for p, m in base_pay:
            lev[p] = (2, m)
        for p, m in affected:
            if p in zero or (p, m) not in base_pay:
                lev[p] = (0, m)
        res = _compute(st, frames, bs, _refs_from_levels(lev))
        return res, _gates(res)

    def worst_fraction(res) -> tuple[int, int, float]:
        """Lexicographic: certificates (fail), then gates not passed, then worst fraction."""
        rank = {"pass": 0, "inconclusive": 1, "fail": 2}
        fs = [
            g["fraction"] if g["fraction"] is not None else math.inf
            for mod in res["modules"].values()
            for g in mod["cumulative"].values()
        ]
        not_passed = sum(not v for k, v in _gates(res).items() if "|" in k and "module" not in k)
        return (rank[res["status"]], not_passed, max(fs))

    fav_res, fav_g = evaluate(set(shared))
    max_res, max_g = evaluate(set())
    best_zero = set(shared) if worst_fraction(fav_res) <= worst_fraction(max_res) else set()
    best_res = fav_res if best_zero else max_res
    for _ in range(2):
        improved = False
        for p in shared:
            trial = best_zero ^ {p}
            r, _ = evaluate(trial)
            if worst_fraction(r) < worst_fraction(best_res):
                best_zero, best_res, improved = trial, r, True
        if not improved:
            break
    return {
        "note": "feasible configurations: every value is attained by one coherent set of "
        "references on the archived samples; the best attainable value is at most it",
        "n_payloads_shared_between_affected_and_baseline_samples": len(shared),
        "most_favourable_feasible": {"result": _summary(fav_res), "gates": fav_g},
        "maximal_denominator": {"result": _summary(max_res), "gates": max_g},
        "greedy_search_feasible": {
            "label": "a feasible value found by the declared greedy search (two coordinate "
            "passes over the shared payloads); not a certified optimum",
            "result": _summary(best_res),
            "gates": _gates(best_res),
            "shared_payloads_set_unsuccessful": len(best_zero),
        },
    }


# --- operational power ---------------------------------------------------------------


def population(
    st: Structure, m: str, lam: float | str, structure: str, seed: int
) -> dict[str, Any]:
    """References (levels) for every payload of module m in one scenario, and its realised
    totals. Baseline levels share one stream across scenarios (common random numbers).
    With structure CALIBRATED, lam names a CALIBRATED_TARGETS variant."""
    s_inv = PLAN_SUCCESS_SHARE[(m, INV[m])]
    s2 = PLAN_SUCCESS_SHARE[(m, "STRICT")]
    base_rng = random.Random(derive_seed(seed, f"truth|{m}"))
    rng = random.Random(derive_seed(seed, f"truth|{m}|{lam}|{structure}"))
    calibrated = structure == CALIBRATED
    targets = CALIBRATED_TARGETS[str(lam)][m] if calibrated else None
    level: dict[str, int] = {}
    fixed: set[str] = set()

    zeroed: set[str] = set()

    def put(p: str, v: int) -> None:
        if p not in fixed:
            level[p] = v
            fixed.add(p)

    def zero(qp: str) -> None:  # a lost row's links are unsuccessful (unless already carried)
        if qp not in fixed:
            level[qp] = 0
            fixed.add(qp)
            zeroed.add(qp)

    def carry(qp: str, v: int) -> None:  # a retained row's counterpart has at least its level
        if qp in zeroed:
            return
        level[qp] = max(level[qp], v) if qp in fixed else v
        fixed.add(qp)

    rows = sorted(h for h, (_, mm) in st.base.items() if mm == m)
    drawn = {}
    for h in rows:
        p = st.base[h][0]
        if p not in drawn:
            u = base_rng.random()
            drawn[p] = 2 if u < s2 else (1 if u < s_inv else 0)
    aff = sorted(h for h in st.cell_of if st.base[h][1] == m)
    lost: set[str] = set()
    retains_unresolved: set[str] = set()
    q = (
        0.0
        if calibrated
        else {"all_loss": 1.0, "none_loss": 0.0, "dev_share": DEV_SHARE_UNRESOLVED_LOSS[m]}[
            structure
        ]
    )
    for h in aff:
        p = st.base[h][0]
        if h in st.unresolved and not calibrated:
            lev = drawn[p]
            if structure == "dev_share":
                if rng.random() < q:
                    lev = lev or (2 if rng.random() < s2 / s_inv else 1)
                    is_lost = True
                else:
                    is_lost = False
            else:
                is_lost = lev >= 1 and q == 1.0
            put(p, lev)
            if is_lost:
                lost.add(h)
                for qp, _, _ in st.links[h]:
                    zero(qp)
            else:
                retains_unresolved.add(h)
                for qp, _, kind in st.links[h]:
                    if kind == "counterpart":
                        carry(qp, level[p])
    # Losses still needed, over the other affected cells.
    for h in rows:  # provisional levels of the rest (REMOVED rows start unsuccessful)
        p = st.base[h][0]
        if p in fixed:
            continue
        level[p] = 0 if st.cell_of.get(h) in (REMOVED, CLAIM_DROPPED) else drawn[p]
    prov = [level.get(st.base[h][0], drawn[st.base[h][0]]) for h in rows]
    S_inv = sum(v >= 1 for v in prov)
    S_strict = sum(v == 2 for v in prov)
    if targets is not None:
        target_frac = {k: a / b for k, (a, b) in targets.items()}
        L_target = round(target_frac["INV"] * S_inv)
        L_target_strict = min(L_target, round(target_frac["STRICT"] * S_strict))
    else:
        target_frac = {"INV": float(lam)}
        L_target = round(float(lam) * S_inv)
        L_target_strict = None
    need = L_target - len(lost)
    cand_rows = {
        c: [h for h in aff if st.cell_of[h] == c and (calibrated or h not in st.unresolved)]
        for c in AFFECTED_CELLS
    }
    sizes = {c: len(v) for c, v in cand_rows.items()}
    tot = sum(sizes.values())
    alloc = dict.fromkeys(AFFECTED_CELLS, 0)
    if need > 0 and tot:
        quota = {c: need * sizes[c] / tot for c in AFFECTED_CELLS}
        alloc = {c: min(sizes[c], int(quota[c])) for c in AFFECTED_CELLS}
        left = need - sum(alloc.values())
        for c in sorted(AFFECTED_CELLS, key=lambda c: -(quota[c] - int(quota[c]))):
            if left <= 0:
                break
            if alloc[c] < sizes[c]:
                alloc[c] += 1
                left -= 1
    chosen = [h for c in AFFECTED_CELLS for h in sorted(rng.sample(cand_rows[c], alloc[c]))]
    strict_lost = set()
    if L_target_strict is not None:  # calibrated: exactly L_STRICT of the lost rows at level 2
        strict_lost = set(rng.sample(sorted(chosen), min(L_target_strict, len(chosen))))
    for h in chosen:
        p = st.base[h][0]
        if L_target_strict is None:
            put(p, 2 if rng.random() < s2 / s_inv else 1)
        else:
            put(p, 2 if h in strict_lost else 1)
        lost.add(h)
        for qp, _, _ in st.links[h]:
            zero(qp)
    for h in aff:  # retained rows: counterparts carry the baseline level
        p = st.base[h][0]
        put(p, level.get(p, drawn[p]))
        if h not in lost and h in st.unresolved:
            retains_unresolved.add(h)
        if h not in lost:
            for qp, _, kind in st.links[h]:
                if kind == "counterpart":
                    carry(qp, level[p])
    for h in rows:
        put(st.base[h][0], level.get(st.base[h][0], drawn[st.base[h][0]]))

    # Realised truth (M1): exact from the final references.
    def lev(p: str) -> int:
        return level.get(p, 0)

    S = {"STRICT": 0, "INV": 0}
    L = {"STRICT": 0, "INV": 0}
    for h in rows:
        lb = lev(st.base[h][0])
        S["STRICT"] += lb == 2
        S["INV"] += lb >= 1
        if h not in st.cell_of:
            continue
        ok_link = [
            (lev(qp), kind)
            for qp, res, kind in st.links[h]
            if kind == "sibling" or res or h in retains_unresolved
        ]
        if lb == 2 and not any(v == 2 and k == "counterpart" for v, k in ok_link):
            L["STRICT"] += 1
        if lb >= 1 and not any(v >= 1 for v, _ in ok_link):
            L["INV"] += 1
    removal = {}
    for c in st.configs:
        pop = st.frame_pop[f"{c}|{m}|affected|{REMOVED}"]
        if pop:
            k = sum(lev(st.base[h][0]) >= 1 for h in pop)
            removal[c] = {"N": len(pop), "T_successes": k, "share": k / len(pop)}
    return {
        "levels": level,
        "realised": {
            "baseline_hits": len(rows),
            "baseline_successes": S,
            "true_losses": L,
            "loss_fraction": {k: (L[k] / S[k] if S[k] else None) for k in S},
            # the target is a design input; the realised loss above is what the
            # population actually contains (audit r2 S4)
            "target_lambda": target_frac,
            "target_losses_INV": L_target,
            "target_losses_STRICT": L_target_strict,
            "nominal_zero_with_realised_losses": (
                not calibrated and float(lam) == 0.0 and (L["INV"] > 0 or L["STRICT"] > 0)
            ),
            "unresolved_rows": sum(1 for h in aff if h in st.unresolved),
            "unresolved_losses": sum(1 for h in lost if h in st.unresolved),
            "feasible": need >= 0,
            "allocation_over_cells": alloc,
            "removal_success_share": removal,
        },
    }


_ST: Structure | None = None


def _run_scenario(args: tuple[float | str, str, int, int]) -> dict[str, Any]:
    lam, structure, reps, seed = args
    st = _ST
    assert st is not None
    pops = {m: population(st, m, lam, structure, seed) for m in MODULES}
    levels = {p: (v, m) for m in MODULES for p, v in pops[m]["levels"].items()}
    counts: dict[str, int] = defaultdict(int)
    n_gates: dict[str, int] = defaultdict(int)
    for rep in range(reps):
        fr_ch, bs_ch = st.draw(seed, rep)
        frames, bs = st.frames_for(fr_ch), st.bs_for(bs_ch)
        r = random.Random(derive_seed(seed, f"refs|{rep}"))
        sampled = {st.base[h][0] for rows in fr_ch.values() for h in rows}
        sampled |= {st.base[h][0] for m in MODULES for rows in bs_ch[m].values() for h in rows}
        sampled |= {
            q
            for fid, rows in fr_ch.items()
            if fid.startswith(COMPLETE)
            for h in rows
            for q, _, _ in st.links.get(h, [])
        }
        lv = {p: levels.get(p, (0, None)) for p in sampled}
        lv = {p: (v, m if m else _module_of(st, p)) for p, (v, m) in lv.items()}
        unres = {p for p in sorted(sampled) if r.random() < REF_UNRESOLVED_RATE[lv[p][1]]}
        res = _compute(st, frames, bs, _refs_from_levels(lv, unres))
        for g, v in _gates(res).items():
            n_gates[g] += 1
            counts[g] += bool(v)
    gates = {
        g: {
            "p": counts[g] / n_gates[g],
            "k": counts[g],
            "reps": n_gates[g],
            "wilson95": wilson(counts[g], n_gates[g]),
        }
        for g in sorted(n_gates)
    }
    calibrated = structure == CALIBRATED
    return {
        "kind": "module_calibrated" if calibrated else "lambda_grid",
        "lambda": None if calibrated else lam,
        "calibrated_variant": lam if calibrated else None,
        "unresolved_structure": structure,
        "realised": {m: pops[m]["realised"] for m in MODULES},
        "nominal_zero_with_realised_losses": any(
            pops[m]["realised"]["nominal_zero_with_realised_losses"] for m in MODULES
        ),
        "gates": gates,
    }


def _module_of(st: Structure, p: str) -> str:
    for pay, m in st.base.values():
        if pay == p:
            return m
    return "metadiscourse"


def operational_power(
    run_dir: Path,
    diff_dir: Path,
    selection: dict[str, Any],
    reps: int,
    seed: int,
    jobs: int = 1,
    lambdas: tuple[float, ...] = PLAN_LOSS_FRACTIONS,
    structures: tuple[str, ...] = STRUCTURES,
    calibrated: tuple[str, ...] = tuple(CALIBRATED_TARGETS),
) -> dict[str, Any]:
    global _ST
    st = Structure(run_dir, diff_dir, selection)
    _ST = st
    att = attainable(st)
    tasks: list[tuple[float | str, str, int, int]] = [
        (lam, s, reps, seed) for lam in lambdas for s in structures
    ]
    tasks += [(v, CALIBRATED, reps, seed) for v in calibrated]
    if jobs > 1 and reps > 0:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("fork")) as ex:
            scen = list(ex.map(_run_scenario, tasks))
    else:
        scen = [_run_scenario(t) for t in tasks] if reps > 0 else []
    return {
        "model": MODEL_VERSION,
        "seed": seed,
        "reps": reps,
        "mc_interval": "Wilson 95% score interval on the replicate pass frequency",
        "all_gates": "ALL_REQUIRED_GATES_PASS: every statistical gate passes (candidate status "
        "pass), conditional on a valid procedure; FAIL_BY_CERTIFICATE: a breach certificate",
        "reading": "informational: the probability of each outcome under declared populations; "
        "an observed status does not license an inverse inference to a true loss level",
        "assumptions": {
            "planning_success_shares": {f"{m}|{o}": v for (m, o), v in PLAN_SUCCESS_SHARE.items()},
            "dev_share_unresolved_loss": DEV_SHARE_UNRESOLVED_LOSS,
            "reference_unresolved_rate": REF_UNRESOLVED_RATE,
            "loss_grid": list(lambdas),
            "unresolved_structures": list(structures),
            "module_calibrated_targets": {
                v: {
                    m: {k: {"num": a, "den": b, "rate": a / b} for k, (a, b) in t.items()}
                    for m, t in CALIBRATED_TARGETS[v].items()
                }
                for v in calibrated
            },
            "population_model": "see fixcheck/power.py docstring",
        },
        "structure": {
            "unresolved_rows": {
                m: sum(1 for h in st.unresolved if st.base[h][1] == m) for m in MODULES
            },
            "affected_rows": {m: sum(1 for h in st.cell_of if st.base[h][1] == m) for m in MODULES},
            "rows_with_sibling_links": {
                m: sum(
                    1
                    for h in st.cell_of
                    if st.base[h][1] == m and any(k == "sibling" for _, _, k in st.links[h])
                )
                for m in MODULES
            },
        },
        "attainable": att,
        "scenarios": scen,
    }
