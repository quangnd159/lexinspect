"""Study 4: module-level end-to-end analysis simulations (STRICT, module ALL).

    uv run python scripts/validation/study4_precision/simulate_coverage.py \\
        [--key .cache/validation/study4/key.jsonl] [--frame FRAME] \\
        [--main-reps 23410] [--grid-reps 2000] [--scenario all|main|grid|NAME ...] \\
        [--workers 11] [--out results.json] [--md results.md] [--resume]
    uv run python scripts/validation/study4_precision/simulate_coverage.py \\
        [same design options] --write-inventory final_inventory.json
    uv run python scripts/validation/study4_precision/simulate_coverage.py \\
        --merge A.json B.json ... --inventory final_inventory.json --out merged.json \\
        [--md merged.md]

Every replicate goes through the code that produces the reported results:
synthetic label files for A, B, the adjudicator and the maintainer's two passes
are built as `analyse.LabelSet`s and passed to `analyse.analyse(...,
scope="module")`, which assembles the model reference (A, B, adjudicator),
the estimates, the exact limits, the resolution region and the concordance.
Only the module-level ALL domain and the STRICT outcome are evaluated.

Finite populations
------------------
Sub-strata (N_h, n_h) come from the development key (or a synthetic design),
register counts from the frame. Every population unit has a fixed model
value R_u (the label the model reference gives it when it is resolved) and a
fixed maintainer value H_u. The targets are P_R = mean R_u over the module
population and D = P_R - P_H. Per sub-stratum, P(R_u = 1) varies (with a
register effect); H_u flips R_u with per-sub-stratum rates f10 (R=1 -> H=0)
and f01 (R=0 -> H=1). PHRASE wrong labels are drawn among
NOT_THE_EXPRESSION, WRONG_SENSE_LISTED and WRONG_SENSE_UNLISTED, so the
module's outcome parsing is exercised.

Scenarios. The main scenario, `main-pilot`, is calibrated to the development
pilot (PILOT, pilot_resolution): population STRICT precision exactly .491
(metadiscourse) and .836 (PHRASE), the pilot's design-weighted estimates, via
`p_target`, and per-module adjudication
and unresolved rates equal to the pilot's (metadiscourse 63/1,000 adjudicated,
2/1,000 unresolved; PHRASE 8/300 adjudicated and (8/300)(2/86) unresolved).
Sub-stratum heterogeneity, register effects and the maintainer's parameters
are BASE's: the pilot has no maintainer labels. The grid keeps the boundary,
non-resolution, weight, threshold and adverse scenarios; `main-realistic` (the
round-3/round-4 main scenario, precision about .72-.83) and
`low-precision-050` (precision .50, pilot resolution rates) cover high and low
precision. Scenarios without `p_target` draw exactly as before.

Each replicate draws the stratified SRSWOR phase-one sample, then the
maintainer's SRS within each sub-stratum (build.allocate_maintainer, 300 per
module by default; PHRASE is a census of phase one in the development
design). Model status per sampled unit: resolved by A and B, resolved by the
adjudicator after a split, or unresolved (A and B split and the adjudicator
UNSURE, or A and B both UNSURE). Unresolvedness is "random" (per replicate,
independent of R), "outcome" (per replicate, depends on R), "fixed" (a
deterministic flag on the population unit, independent of R) or
"fixed-outcome" (deterministic flag, more often on R = 0). Maintainer UNSURE
in pass 1 can be more likely on discordant units; the second pass resolves a
share of them to H_u.

Recorded per replicate: whether each interval misses its target below or
above, and its width:
- primary: exact pointwise limits for P_R (valid if resolution is exchangeable
  within cells; not under outcome-dependent resolution);
- region: co-primary resolution region (valid whatever the mechanism);
- KG: the secondary approximate interval;
- concordance: the worst-case-completion interval for D, with the second pass
  and (same replicate) without it.
Monte Carlo precision: Clopper-Pearson 95% intervals for each tail-error rate,
with the failure counts. Population seeds are reported.

Reproducibility: every replicate i of a cell has its own stream,
random.Random(f"{base_seed}|{scenario}|{module}|pop={pop_seed}|rep={i}"), so results
do not depend on the worker count, the chunking or which other cells run.
Replicates are computed in fixed logical chunks of CHUNK_SIZE. Each worker
re-hashes the sources and the run stops if any changed.

Inventory, status, resume and merge. The options define an explicit inventory
of required cells (`inventory`): one entry per (scenario, module, pop_seed)
with its replicate range [replicate_start, replicate_stop), cell seed and
effective parameters. The output holds {"manifest", "cells"}; every cell
records its identity and range. The manifest (format FORMAT; every field in
REQUIRED_MANIFEST is required, and a manifest lacking one is rejected) records
`status` ("running" after each checkpoint, "complete" only when every
inventory cell is present with exactly its range and count and the end-of-run
source check passed), `started`, `checkpoint_time` and `completed_time`
(null while running), the inventory and its SHA-256, the SHA-256 of every
imported source (SOURCES), of the key and frame, the effective parameters of
every scenario per module, the pilot figures, the environment, the command and
the parsed arguments as structured data. An existing --out is never
overwritten without --resume. --resume continues the same request only: the
frozen manifest fields and the inventory must equal the saved ones, and every
saved cell must match its entry exactly, so a cell is never skipped because
it exists with a different (e.g. shorter) range, nor extended; a different
request needs a new --out and --merge. A complete file is left byte-identical
when there is nothing to do. --merge needs complete parts with equal frozen
manifests, run by the same sources as the merging code; each part's cells must
equal its own inventory; cells must be unique within a part (identical copies
across parts collapse; differing copies are refused); and their union must
equal the declared final inventory (--inventory, written by
--write-inventory), checked cell by cell for seed, parameters, range and count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse as A  # noqa: E402
import build  # noqa: E402

Unit = dict[str, Any]
REG_EFFECT = {"academic": 0.0, "general": 0.04, "argumentative": -0.10}
WRONG = {
    "metadiscourse": [("NOT_METADISCOURSE", None), ("WRONG_CATEGORY", "boosters")],
    "phrase": [
        ("NOT_THE_EXPRESSION", None),
        ("WRONG_SENSE_LISTED", "OTHER SENSE"),
        ("WRONG_SENSE_UNLISTED", "SOME GLOSS"),
    ],
}

# Scenario parameters (defaults in BASE; each scenario overrides some).
BASE: dict[str, Any] = {
    "design": "dev",  # dev | sparse | threshold | mixed
    "p_range": (0.45, 0.97),  # sub-stratum P(R=1) before the register effect
    "exact_share": 0.0,  # share of sub-strata with P(R=1) exactly `exact_value`
    "exact_value": 1.0,
    "f10": (0.02, 0.02),  # per-sub-stratum range of P(H=0 | R=1)
    "f01": (0.02, 0.02),  # per-sub-stratum range of P(H=1 | R=0)
    "mech": "random",  # random | outcome | fixed | fixed-outcome
    "pu1": 0.03,  # P(model unresolved | R=1)
    "pu0": 0.03,  # P(model unresolved | R=0)
    "p_adj": 0.10,  # P(resolved by the adjudicator | resolved)
    "unobserved_subs": 0,  # sub-strata where nothing resolves (mixed design)
    "q_unsure": 0.05,  # maintainer pass-1 UNSURE, concordant units
    "q_unsure_disc": 0.05,  # ... discordant units
    "q2": 0.7,  # second pass resolves this share of pass-1 UNSURE items
    "maintainer_total": 300,
    # Optional, not in BASE (so the parameters of older scenarios are unchanged):
    # "p_target": population share of R = 1, reached exactly by a shift (see population);
    # "by_module": {module: {parameter: value}}, applied after the scenario's own values.
}


def effective(spec: dict[str, Any], module: str) -> dict[str, Any]:
    """The parameters a cell actually uses: BASE, then the scenario, then its module block."""
    full = BASE | spec
    by_module = full.pop("by_module", None) or {}
    return full | by_module.get(module, {})


# Development pilot (the dev design: 1,000 metadiscourse and 300 PHRASE phase-one items).
# "precision" is the design-weighted pilot estimate (the registered resolution-adjusted
# estimator, weights N_h/r_h from the dev key: MD .49140, PHRASE .83556; N_h/n_h gives
# the same PHRASE value and MD .49131),
# because p_target sets the share of R = 1 in the whole population; the unweighted sample
# shares were .622 and .670 (in metadiscourse the more heavily weighted, less sampled
# sub-strata have lower precision; in PHRASE, higher). The resolution counts below are unweighted,
# because they act per sampled unit. Model reference = the agreed definite A/B STRICT value, else the
# adjudicator's. "adjudicated" = items whose STRICT reference needed the adjudicator
# (A/B split on STRICT, or a primary UNSURE/missing); "unresolved" = the adjudicator was
# UNSURE too. The 86 requests also include 15 items sent only because A and B split on a
# secondary outcome; their STRICT reference is the agreed A/B value, so they do not
# affect STRICT results and are not simulated. A-B STRICT agreement (MD .954, PHRASE
# .973) is recorded for reference only: the simulation does not separate splits from
# primary UNSUREs, which the STRICT reference treats the same way (the adjudicator
# decides). The pilot has no maintainer labels, so the maintainer parameters keep BASE.
PILOT: dict[str, Any] = {
    "metadiscourse": {"items": 1000, "precision": 0.491, "adjudicated": 63, "unresolved": 2},
    "phrase": {"items": 300, "precision": 0.836, "adjudicated": 8, "unresolved": 0},
    "ab_strict_agreement": {"metadiscourse": 0.954, "phrase": 0.973},
    "adjudication_requests": 86,  # of 1,300 items (6.6%)
    "adjudicator_unsure": 2,  # of the 86 requests
}


def pilot_resolution(module: str) -> dict[str, float]:
    """pu and p_adj that reproduce the pilot's per-module STRICT resolution rates.

    In `replicate`, P(adjudicator needed) = pu + (1 - pu) * p_adj and P(unresolved) = pu.
    Metadiscourse: pu = 2/1000. PHRASE had 0 unresolved of 8 adjudicated, too few to
    estimate, so its pu is its adjudication share times the pooled adjudicator UNSURE
    rate: (8/300) * (2/86)."""
    p = PILOT[module]
    adj = p["adjudicated"] / p["items"]
    if p["unresolved"]:
        pu = p["unresolved"] / p["items"]
    else:
        pu = adj * PILOT["adjudicator_unsure"] / PILOT["adjudication_requests"]
    return {"pu1": pu, "pu0": pu, "p_adj": (adj - pu) / (1 - pu)}


def _pilot(p_target: float | None = None) -> dict[str, Any]:
    """Pilot resolution rates per module; population precision = the pilot's (or p_target)."""
    return {
        "by_module": {
            m: pilot_resolution(m)
            | {"p_target": PILOT[m]["precision"] if p_target is None else p_target}
            for m in ("metadiscourse", "phrase")
        }
    }


# Main scenario: the pilot-calibrated one (population STRICT precision .491 / .836, the
# pilot's adjudication and unresolved rates, random non-resolution; sub-stratum
# heterogeneity, register effects and maintainer parameters as in BASE).
MAIN: dict[str, dict[str, Any]] = {"main-pilot": _pilot()}
GRID: dict[str, dict[str, Any]] = {
    # The round-3/round-4 main scenario (population precision about .72-.83), kept under
    # its original name so its streams and results are unchanged: high-precision cells.
    "main-realistic": {},
    # Low precision with the pilot's resolution rates: population precision .50.
    "low-precision-050": _pilot(0.50),
    "boundary-high": {"p_range": (0.97, 1.0), "exact_share": 1 / 3, "exact_value": 1.0},
    "boundary-low": {"p_range": (0.0, 0.05), "exact_share": 1 / 3, "exact_value": 0.0},
    "outcome-unresolved": {"mech": "outcome", "pu1": 0.03, "pu0": 0.25},
    "fixed-unresolved": {"mech": "fixed", "pu1": 0.05, "pu0": 0.05},
    "fixed-outcome-unresolved": {"mech": "fixed-outcome", "pu1": 0.02, "pu0": 0.30},
    "mixed-census-unobserved": {"design": "mixed", "unobserved_subs": 3},
    "extreme-weights": {"design": "sparse", "maintainer_total": 120},
    "thresholds-2500-2501": {"design": "threshold", "maintainer_total": 200},
    "hetero-discordance-plus": {"f10": (0.0, 0.15), "f01": (0.0, 0.03)},
    "hetero-discordance-minus": {"f10": (0.0, 0.03), "f01": (0.0, 0.30)},
    "adverse-concordance": {
        "f10": (0.03, 0.08),
        "f01": (0.03, 0.08),
        "pu1": 0.10,
        "pu0": 0.10,
        "q_unsure": 0.08,
        "q_unsure_disc": 0.40,
        "q2": 0.5,
    },
}


# --- populations ----------------------------------------------------------------


def _design(spec, key_rows, frame, module, rng) -> tuple[dict[str, tuple[int, int]], dict]:
    """{h: (N_h, n_h)} and {h: {register: count}} for the scenario's design."""
    if spec["design"] in ("dev", "mixed"):
        rows = [r for r in key_rows if r["module"] == module]
        n = Counter(r["substratum"] for r in rows)
        big = {r["substratum"]: r["N_sub"] for r in rows}
        subs = {h: (big[h], n[h]) for h in sorted(n)}
        if spec["design"] == "mixed":  # three small sub-strata become censuses
            for h in sorted(subs, key=lambda h: subs[h][0])[:3]:
                subs[h] = (subs[h][1], subs[h][1]) if subs[h][1] >= 2 else (2, 2)
        regs = {}
        for h, (bn, _) in subs.items():
            fr = (frame or {}).get("modules", {}).get(module, {}).get(h, {}).get("by_register")
            if fr and sum(fr.values()) == bn:
                regs[h] = dict(fr)
            else:
                comp = Counter(r["register"] for r in rows if r["substratum"] == h)
                gs = rng.choices(
                    sorted(A.REGISTERS), [comp[g] + 0.5 for g in sorted(A.REGISTERS)], k=bn
                )
                regs[h] = dict(Counter(gs))
        return subs, regs
    if spec["design"] == "sparse":  # extreme weights: N_h 50 .. 50,000, n_h 2 .. 40
        subs = {}
        for k in range(30):
            bn = int(round(10 ** rng.uniform(math.log10(50), math.log10(50_000))))
            subs[f"{module[:2]}|s{k:02d}"] = (bn, min(bn, rng.choice([2, 2, 3, 5, 15, 40])))
    else:  # threshold: cells at M = 2500 (a/M = .05), 2501, and 2000 (a/M = .05)
        subs = {
            f"{module[:2]}|t2500": (2500, 125),
            f"{module[:2]}|t2501": (2501, 125),
            f"{module[:2]}|t2000": (2000, 100),
            f"{module[:2]}|t300": (300, 30),
        }
    regs = {h: {"academic": bn} for h, (bn, _) in subs.items()}
    return subs, regs


def _target_shift(draws: list[tuple[float, float]], target: float) -> float:
    """Shift d such that exactly round(target * N) units have u < clip(p + d, 0, 1).

    For u in [0, 1), u < clip(p + d, 0, 1) iff u - p < d, so the count of R = 1 is the
    number of thresholds u - p below d; d is the midpoint between the k-th and (k+1)-th
    smallest thresholds (deterministic, no search)."""
    t = sorted(u - p for p, u in draws)
    k = round(target * len(t))
    if k <= 0:
        return t[0] - 1.0
    if k >= len(t):
        return t[-1] + 1.0
    return (t[k - 1] + t[k]) / 2


def population(spec, key_rows, frame, module, pop_seed) -> dict[str, Any]:
    """The finite population of a cell.

    With `p_target`, every unit's P(R = 1) is shifted by one common d (clipped to [0, 1])
    so that the population share of R = 1 is round(p_target * N) / N exactly; H and the
    fixed non-resolution flag are then derived from the same uniforms. The random draws
    are identical with and without p_target, so scenarios without it are unchanged."""
    rng = random.Random(pop_seed)
    subs, regs = _design(spec, key_rows, frame, module, rng)
    unobserved = set(sorted(subs, key=lambda h: (-subs[h][0], h))[: spec["unobserved_subs"]])
    target = spec.get("p_target")
    if target is not None and spec["exact_share"] > 0:
        raise ValueError("p_target cannot be combined with exact_share (it would shift them)")
    pop: dict[str, list[Unit]] = {}
    draws: list[tuple[Unit, float, float, float, float | None, float, float]] = []
    for h, (bn, _) in subs.items():
        if rng.random() < spec["exact_share"]:
            base, exact = spec["exact_value"], True
        else:
            base, exact = rng.uniform(*spec["p_range"]), False
        f10, f01 = rng.uniform(*spec["f10"]), rng.uniform(*spec["f01"])
        units = []
        j = 0
        for g, c in sorted(regs[h].items()):
            for _ in range(c):
                p = base if exact else min(1.0, max(0.0, base + REG_EFFECT[g]))
                u_r = rng.random()
                r_u = int(u_r < p)
                u_h = rng.random()
                h_u = 1 - r_u if u_h < (f10 if r_u else f01) else r_u
                pu = spec["pu1"] if r_u else spec["pu0"]
                u_hard = rng.random() if spec["mech"].startswith("fixed") else None
                units.append(
                    {
                        "id": f"{h}#{j}",
                        "module": module,
                        "stratum": h.split("|")[0],
                        "substratum": h,
                        "N_sub": bn,
                        "register": g,
                        "R": r_u,
                        "H": h_u,
                        "hard": u_hard is not None and u_hard < pu,
                        "unobs": h in unobserved,
                    }
                )
                if target is not None:
                    draws.append((units[-1], p, u_r, u_h, u_hard, f10, f01))
                j += 1
        pop[h] = units
    shift = None
    if target is not None:
        shift = _target_shift([(p, u_r) for _, p, u_r, *_ in draws], target)
        for unit, p, u_r, u_h, u_hard, f10, f01 in draws:
            r_u = int(u_r < min(1.0, max(0.0, p + shift)))
            pu = spec["pu1"] if r_u else spec["pu0"]
            unit["R"] = r_u
            unit["H"] = 1 - r_u if u_h < (f10 if r_u else f01) else r_u
            unit["hard"] = u_hard is not None and u_hard < pu
    allu = [u for us in pop.values() for u in us]
    frame_out = {
        "modules": {
            m: (
                {
                    h: {"N": len(us), "by_register": dict(Counter(u["register"] for u in us))}
                    for h, us in pop.items()
                }
                if m == module
                else {}
            )
            for m in A.LABELS
        }
    }
    alloc = build.allocate_maintainer(
        {h: (bn, n) for h, (bn, n) in subs.items()}, spec["maintainer_total"]
    )
    return {
        "pop": pop,
        "n": {h: n for h, (_, n) in subs.items()},
        "m": alloc,
        "frame": frame_out,
        "P": sum(u["R"] for u in allu) / len(allu),
        "D": sum(u["R"] - u["H"] for u in allu) / len(allu),
        "N": len(allu),
        "n_total": sum(n for _, n in subs.values()),
        "m_total": sum(alloc.values()),
        "census_subs": sum(1 for bn, n in subs.values() if n >= bn),
        "unobserved_subs": len(unobserved),
        "p_shift": shift,
    }


# --- one replicate ----------------------------------------------------------------


def _rec(rid, label, alt=None):
    return {"id": rid, "label": label, "alt_category": alt, "note": None}


def _lab(module, value, rng):
    if value == 1:
        return "CORRECT", None
    return rng.choice(WRONG[module])


def replicate(world: dict[str, Any], spec: dict[str, Any], module: str, rng: random.Random):
    rows, a, b, c, h1, h2, mids = [], {}, {}, {}, {}, {}, []
    for h, units in world["pop"].items():
        n_h = world["n"][h]
        smp = rng.sample(units, n_h)
        msmp = set(id(u) for u in rng.sample(smp, world["m"][h]))
        for u in smp:
            rid = u["id"]
            rows.append(
                {
                    "id": rid,
                    "module": module,
                    "stratum": u["stratum"],
                    "substratum": h,
                    "N_sub": u["N_sub"],
                    "n_sub": n_h,
                    "register": u["register"],
                    "category": "hedges",
                    "dimension": "interactional",
                    "k_band": 1,
                    "multi_sense": False,
                }
            )
            r_u = u["R"]
            pu = spec["pu1"] if r_u else spec["pu0"]
            if u["unobs"]:
                unres = True
            elif spec["mech"] in ("random", "outcome"):
                unres = rng.random() < pu
            else:
                unres = u["hard"]
            right, wrong = _lab(module, r_u, rng), _lab(module, 1 - r_u, rng)
            if unres:
                if rng.random() < 0.5:
                    a[rid], b[rid], c[rid] = (
                        _rec(rid, *right),
                        _rec(rid, *wrong),
                        _rec(rid, "UNSURE"),
                    )
                else:
                    a[rid], b[rid] = _rec(rid, "UNSURE"), _rec(rid, "UNSURE")
                    c[rid] = _rec(rid, "UNSURE")
            elif rng.random() < spec["p_adj"]:
                a[rid], b[rid], c[rid] = _rec(rid, *right), _rec(rid, *wrong), _rec(rid, *right)
            else:
                a[rid] = b[rid] = _rec(rid, *right)
            if id(u) in msmp:
                mids.append(rid)
                q = spec["q_unsure_disc"] if u["H"] != r_u else spec["q_unsure"]
                if rng.random() < q:
                    h1[rid] = _rec(rid, "UNSURE")
                    h2[rid] = (
                        _rec(rid, *_lab(module, u["H"], rng))
                        if rng.random() < spec["q2"]
                        else _rec(rid, "UNSURE")
                    )
                else:
                    h1[rid] = _rec(rid, *_lab(module, u["H"], rng))
    ids = sorted(a)
    need = A.needs_adjudication(rows, [A.LabelSet("A", a, ids), A.LabelSet("B", b, ids)])
    c = {i: v for i, v in c.items() if i in set(need)}
    la, lb = A.LabelSet("A", a, ids), A.LabelSet("B", b, ids)
    lc = A.LabelSet(A.ADJUDICATOR, c, need)
    p1 = A.LabelSet(A.MAINTAINER, h1, sorted(mids))
    p2 = A.LabelSet("maintainer_pass2", h2, sorted(h2))
    rep = A.analyse(rows, [la, lb], lc, p1, mids, None, world["frame"], False, p2, scope="module")
    est = rep["model_reference"][module]["STRICT"]["ALL"]
    conc = rep["maintainer_concordance"][module]
    ref = A.reference(rows, "STRICT", [la, lb], lc)
    final1, _ = A.combine_maintainer_passes(p1, None)
    conc1 = A.concordance(rows, ref, final1, set(mids), world["frame"])
    return (
        est["p"],
        est["p_represented"],
        tuple(est["ci95_exact"]),
        tuple(est["region95_exact"]),
        tuple(est["ci95_approx"]) if est["ci95_approx"] else None,
        tuple(conc["difference"]["interval95_worst_case_completion"]),
        tuple(conc1["difference"]["interval95_worst_case_completion"]),
        est["ci95_exact_method"],
        conc["comparable_share"],
        conc1["comparable_share"],
    )


def replicate_rng(cell_seed: str, index: int) -> random.Random:
    """One deterministic stream per replicate: independent of workers and chunking."""
    return random.Random(f"{cell_seed}|rep={index}")


def _chunk(task: dict[str, Any]) -> tuple[list[tuple], dict[str, str]]:
    spec = effective(task["spec"], task["module"])
    world = population(spec, task["key_rows"], task["frame"], task["module"], task["pop_seed"])
    recs = [
        replicate(world, spec, task["module"], replicate_rng(task["cell_seed"], j))
        for j in range(task["start"], task["start"] + task["reps"])
    ]
    return recs, source_hashes()  # the sources as seen by this worker


# --- Monte Carlo summaries ------------------------------------------------------------


def _binom_cdf(x: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if x >= n else 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * lp + (n - k) * lq
        for k in range(x + 1)
    ]
    mx = max(terms)
    return min(1.0, math.exp(mx) * sum(math.exp(t - mx) for t in terms))


def clopper_pearson(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial 95% interval for x failures in n replicates."""
    if n == 0:
        return (0.0, 1.0)

    def solve(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    upper = 1.0 if x == n else solve(lambda p: _binom_cdf(x, n, p), alpha / 2)
    # P(X >= x; p) increases in p: the lower limit solves P(X >= x; p) = alpha / 2.
    lower = 0.0 if x == 0 else 1.0 - solve(lambda q: _binom_cdf(n - x, n, q), alpha / 2)
    return (lower, upper)


def _tails(intervals: list[tuple | None], target: float) -> dict[str, Any]:
    got = [iv for iv in intervals if iv is not None and iv[0] is not None]
    n = len(got)
    lo = sum(1 for iv in got if iv[0] > target + 1e-12)
    hi = sum(1 for iv in got if iv[1] < target - 1e-12)
    return {
        "reported": n,
        "miss_low": lo,
        "miss_high": hi,
        "miss_low_rate": lo / n if n else None,
        "miss_high_rate": hi / n if n else None,
        "miss_low_cp95": clopper_pearson(lo, n),
        "miss_high_cp95": clopper_pearson(hi, n),
        "coverage": 1 - (lo + hi) / n if n else None,
        "coverage_cp95": tuple(1 - x for x in reversed(clopper_pearson(lo + hi, n))),
        "mean_width": sum(iv[1] - iv[0] for iv in got) / n if n else None,
    }


def summarise(world_info: dict[str, Any], recs: list[tuple]) -> dict[str, Any]:
    P, D = world_info["P"], world_info["D"]
    pts = [r[0] for r in recs if r[0] is not None]
    return {
        **world_info,
        "reps": len(recs),
        "point_reported": len(pts),
        "mean_point": sum(pts) / len(pts) if pts else None,
        "primary": _tails([r[2] for r in recs], P),
        "region": _tails([r[3] for r in recs], P),
        "kg": _tails([r[4] for r in recs], P),
        "concordance_pass2": _tails([r[5] for r in recs], D),
        "concordance_pass1_only": _tails([r[6] for r in recs], D),
        "primary_methods": dict(Counter(r[7] for r in recs)),
        "mean_comparable_share_pass2": sum(r[8] for r in recs) / len(recs),
        "mean_comparable_share_pass1_only": sum(r[9] for r in recs) / len(recs),
    }


# --- provenance -------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
SOURCES = ("simulate_coverage", "analyse", "estimators", "build", "frame", "batches")
CHUNK_SIZE = 50  # fixed logical chunk: replicates [k*50, (k+1)*50) of a cell
FORMAT = "study4-simulation-results/2"
INVENTORY_FORMAT = "study4-simulation-inventory/1"
STATUSES = ("running", "complete")
REQUIRED_MANIFEST = (
    "format",
    "status",
    "sources_sha256",
    "key",
    "key_sha256",
    "frame",
    "frame_sha256",
    "environment",
    "base_seed",
    "rng_scheme",
    "chunk_scheme",
    "base_parameters",
    "scenario_parameters",
    "inventory",
    "inventory_sha256",
    "command",
    "arguments",
    "workers",
    "started",
    "checkpoint_time",
    "completed_time",
    "merge_provenance",
)
CELL_IDENTITY = ("scenario", "module", "pop_seed", "replicate_start", "replicate_stop", "cell_seed")
REQUIRED_CELL = (*CELL_IDENTITY, "parameters", "reps", "P", "D", "N")
INTERVALS = ("primary", "region", "kg", "concordance_pass2", "concordance_pass1_only")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_json(x: Any) -> str:
    """Canonical JSON hash (sorted keys, no whitespace)."""
    s = json.dumps(A.clean_json(x), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def source_hashes() -> dict[str, str]:
    return {m: sha256_file(HERE / f"{m}.py") for m in SOURCES}


def environment() -> dict[str, Any]:
    import numpy

    try:
        import scipy  # type: ignore[import-not-found]

        sv = scipy.__version__
    except ImportError:
        sv = "not installed (not used)"
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "numpy": numpy.__version__,
        "scipy": sv,
        "platform": platform.platform(),
    }


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def cell_seed(base_seed: int, scenario: str, module: str, pop_seed: int) -> str:
    """Named per cell, so a cell's stream does not depend on which other cells run."""
    return f"{base_seed}|{scenario}|{module}|pop={pop_seed}"


def scenario_parameters() -> dict[str, dict[str, Any]]:
    """Effective parameters of every scenario, per module."""
    return A.clean_json(
        {k: {m: effective(v, m) for m in A.LABELS} for k, v in (MAIN | GRID).items()}
    )


def frozen_part(manifest: dict[str, Any]) -> dict[str, Any]:
    """The fields that must match for resume and merge."""
    keys = (
        "format",
        "sources_sha256",
        "key_sha256",
        "frame_sha256",
        "environment",
        "base_seed",
        "chunk_scheme",
        "rng_scheme",
        "base_parameters",
        "scenario_parameters",
    )
    return {k: manifest.get(k) for k in keys}


# --- inventory: the cells a run must produce ---------------------------------------------


def inventory(args: argparse.Namespace) -> list[dict[str, Any]]:
    """The required cells for the effective options, in run order.

    One entry per (scenario, module, pop_seed): the replicate range [start, stop), the cell
    seed and the effective parameters. A cell is complete only with exactly that range."""
    sc = set(args.scenario)
    names = {"all", "main", "grid", *MAIN, *GRID}
    if sc - names:
        raise SystemExit(f"unknown --scenario {sorted(sc - names)}; choose from {sorted(names)}")
    for opt in ("pop_seeds", "grid_pop_seeds", "modules"):
        vals = getattr(args, opt)
        if len(set(vals)) != len(vals):
            raise SystemExit(f"--{opt.replace('_', '-')} has repeated values: {vals}")
    unknown = sorted(set(args.modules) - set(A.LABELS))
    if unknown:
        raise SystemExit(f"unknown --modules {unknown}")
    plan: list[tuple[str, dict[str, Any], int, int]] = []
    for name, spec in MAIN.items():
        if sc & {"all", "main", name}:
            plan += [(name, spec, args.main_reps, ps) for ps in args.pop_seeds]
    for name, spec in GRID.items():
        if sc & {"all", "grid", name}:
            plan += [(name, spec, args.grid_reps, ps) for ps in args.grid_pop_seeds]
    out = []
    for name, spec, reps, ps in plan:
        if reps < 1:
            raise SystemExit(f"{name}: the replicate count must be at least 1 (got {reps})")
        for module in args.modules:
            out.append(
                {
                    "scenario": name,
                    "module": module,
                    "pop_seed": ps,
                    "replicate_start": 0,
                    "replicate_stop": reps,
                    "cell_seed": cell_seed(args.seed, name, module, ps),
                    "parameters": A.clean_json(effective(spec, module)),
                }
            )
    return out


def inventory_document(args: argparse.Namespace) -> dict[str, Any]:
    cells = inventory(args)
    return {
        "format": INVENTORY_FORMAT,
        "base_seed": args.seed,
        "scenario_parameters": scenario_parameters(),
        "arguments": arguments(args),
        "cells": cells,
        "cells_sha256": sha256_json(cells),
    }


def _index(entries: list[dict[str, Any]], what: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        cid = e.get("cell_seed")
        if not isinstance(cid, str):
            raise SystemExit(f"{what}: an entry has no cell_seed: {sorted(e)}")
        if cid in out:
            raise SystemExit(f"{what}: cell {cid} appears more than once")
        out[cid] = e
    return out


def check_inventory(
    entries: list[dict[str, Any]], base_seed: int, params: dict[str, Any], what: str
) -> dict[str, dict[str, Any]]:
    """Inventory entries are unique and agree with the base seed and scenario parameters."""
    idx = _index(entries, what)
    for cid, e in idx.items():
        missing = [k for k in (*CELL_IDENTITY, "parameters") if k not in e]
        if missing:
            raise SystemExit(f"{what}: cell {cid} lacks {missing}")
        if cid != cell_seed(base_seed, e["scenario"], e["module"], e["pop_seed"]):
            raise SystemExit(f"{what}: cell {cid} does not match its seed fields")
        if not (0 <= e["replicate_start"] < e["replicate_stop"]):
            raise SystemExit(f"{what}: cell {cid} has an empty or negative replicate range")
        want = (params.get(e["scenario"]) or {}).get(e["module"])
        if want is None or A.clean_json(e["parameters"]) != want:
            raise SystemExit(f"{what}: cell {cid} parameters differ from the scenario's")
    return idx


def cell_problems(c: dict[str, Any], entry: dict[str, Any] | None) -> list[str]:
    """Why a saved cell does not satisfy its inventory entry (empty if it does)."""
    missing = [k for k in REQUIRED_CELL if k not in c]
    if missing:
        return [f"missing fields {missing}"]
    if entry is None:
        return ["not in the inventory"]
    out = []
    for k in CELL_IDENTITY:
        if c[k] != entry[k]:
            out.append(f"{k} {c[k]!r} != required {entry[k]!r}")
    if A.clean_json(c["parameters"]) != A.clean_json(entry["parameters"]):
        out.append("parameters differ")
    want = entry["replicate_stop"] - entry["replicate_start"]
    if c["reps"] != want:
        out.append(
            f"holds {c['reps']} replicates [{c['replicate_start']}, {c['replicate_stop']}) "
            f"but {want} are required [{entry['replicate_start']}, {entry['replicate_stop']})"
        )
    for k in INTERVALS:
        if k not in c or not 0 <= c[k].get("reported", -1) <= c["reps"]:
            out.append(f"{k}: reported count missing or above the replicate count")
    if not 0 <= c.get("point_reported", -1) <= c["reps"]:
        out.append("point_reported missing or above the replicate count")
    return out


def verify_cells(
    cells: list[dict[str, Any]], inv: dict[str, dict[str, Any]], what: str
) -> dict[str, dict[str, Any]]:
    """Every cell unique and exactly as its inventory entry requires; returns them by id."""
    by_id: dict[str, dict[str, Any]] = {}
    for c in cells:
        cid = c.get("cell_seed")
        if cid in by_id:
            raise SystemExit(f"{what}: cell {cid} appears more than once")
        probs = cell_problems(c, inv.get(cid))
        if probs:
            raise SystemExit(f"{what}: cell {cid}: " + "; ".join(probs))
        by_id[cid] = c
    return by_id


def arguments(args: argparse.Namespace) -> dict[str, Any]:
    """The effective parsed options, as structured data."""
    return A.clean_json({k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()})


def make_manifest(
    args, key_path: Path, frame_path: Path | None, inv: list[dict[str, Any]]
) -> dict[str, Any]:
    t = now()
    return {
        "format": FORMAT,
        "status": "running",
        "sources_sha256": source_hashes(),
        "key": str(key_path),
        "key_sha256": sha256_file(key_path),
        "frame": str(frame_path) if frame_path else None,
        "frame_sha256": sha256_file(frame_path) if frame_path else None,
        "environment": environment(),
        "base_seed": args.seed,
        "rng_scheme": "random.Random(f'{base_seed}|{scenario}|{module}|pop={pop_seed}|rep={i}') "
        "per replicate i; population: random.Random(pop_seed)",
        "chunk_scheme": f"fixed logical chunks of {CHUNK_SIZE} replicates; workers only "
        "parallelise and do not affect results",
        "base_parameters": A.clean_json(BASE),
        "scenario_parameters": scenario_parameters(),
        "pilot": A.clean_json(PILOT),
        "inventory": inv,
        "inventory_sha256": sha256_json(inv),
        "command": [sys.executable, *sys.argv],
        "arguments": arguments(args),
        "workers": args.workers,
        "started": t,
        "checkpoint_time": t,
        "completed_time": None,
        "merge_provenance": [],
    }


def check_manifest(m: Any, what: str) -> None:
    """Reject manifests that lack a required field or have an inconsistent status."""
    if not isinstance(m, dict):
        raise SystemExit(f"{what}: manifest is not an object")
    missing = [k for k in REQUIRED_MANIFEST if k not in m]
    if missing:
        raise SystemExit(f"{what}: manifest lacks required fields {missing}")
    if m["format"] != FORMAT:
        raise SystemExit(f"{what}: format {m['format']!r} is not {FORMAT!r}")
    if m["status"] not in STATUSES:
        raise SystemExit(f"{what}: status {m['status']!r} is not one of {STATUSES}")
    if (m["status"] == "complete") != (m["completed_time"] is not None):
        raise SystemExit(
            f"{what}: status {m['status']!r} with completed_time {m['completed_time']!r}"
        )
    if not isinstance(m["inventory"], list) or sha256_json(m["inventory"]) != m["inventory_sha256"]:
        raise SystemExit(f"{what}: inventory does not match inventory_sha256")
    if not isinstance(m["arguments"], dict):
        raise SystemExit(f"{what}: arguments must be structured (an object)")


def run(
    name,
    spec,
    module,
    key_rows,
    frame,
    reps,
    pop_seed,
    base_seed,
    workers,
    expect_sources=None,
    start: int = 0,
) -> dict[str, Any]:
    """Replicates [start, start + reps) of one cell."""
    full = effective(spec, module)
    world = population(full, key_rows, frame, module, pop_seed)
    info = {
        k: world[k]
        for k in ("P", "D", "N", "n_total", "m_total", "census_subs", "unobserved_subs", "p_shift")
    }
    cs = cell_seed(base_seed, name, module, pop_seed)
    info |= {
        "scenario": name,
        "module": module,
        "pop_seed": pop_seed,
        "cell_seed": cs,
        "replicate_start": start,
        "replicate_stop": start + reps,
        "parameters": A.clean_json(full),
    }
    tasks = [
        {
            "spec": spec,
            "key_rows": key_rows,
            "frame": frame,
            "module": module,
            "pop_seed": pop_seed,
            "cell_seed": cs,
            "start": s,
            "reps": min(CHUNK_SIZE, start + reps - s),
        }
        for s in range(start, start + reps, CHUNK_SIZE)
    ]
    expect = expect_sources or source_hashes()
    recs: list[tuple] = []
    if workers <= 1:
        parts = map(_chunk, tasks)
        for part, seen in parts:
            _check_sources(seen, expect)
            recs += part
    else:
        with ProcessPoolExecutor(workers) as ex:
            for part, seen in ex.map(_chunk, tasks):
                _check_sources(seen, expect)
                recs += part
    return summarise(info, recs)


def _check_sources(seen: dict[str, str], expect: dict[str, str]) -> None:
    if seen != expect:
        changed = sorted(k for k in expect if seen.get(k) != expect[k])
        raise SystemExit(f"source files changed during the run: {changed}; restart from scratch")


def load_results(path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text())
    if not isinstance(d, dict) or "manifest" not in d or "cells" not in d:
        raise SystemExit(f"{path}: not a manifest-bearing result file")
    check_manifest(d["manifest"], str(path))
    if not isinstance(d["cells"], list):
        raise SystemExit(f"{path}: cells is not a list")
    return d


def load_inventory(path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text())
    if not isinstance(d, dict) or d.get("format") != INVENTORY_FORMAT:
        raise SystemExit(f"{path}: not an inventory file ({INVENTORY_FORMAT})")
    for k in ("base_seed", "scenario_parameters", "cells", "cells_sha256"):
        if k not in d:
            raise SystemExit(f"{path}: inventory lacks {k}")
    if sha256_json(d["cells"]) != d["cells_sha256"]:
        raise SystemExit(f"{path}: cells do not match cells_sha256")
    return d


def _inventory_diff(saved: list[dict[str, Any]], want: list[dict[str, Any]]) -> list[str]:
    s, w = _index(saved, "saved inventory"), _index(want, "requested inventory")
    out = [f"cell {c} is requested but not in the saved run" for c in w if c not in s]
    out += [f"cell {c} is in the saved run but not requested" for c in s if c not in w]
    for c in s.keys() & w.keys():
        a, b = s[c], w[c]
        if (a["replicate_start"], a["replicate_stop"]) != (
            b["replicate_start"],
            b["replicate_stop"],
        ):
            out.append(
                f"cell {c}: saved replicates [{a['replicate_start']}, {a['replicate_stop']}) "
                f"but requested [{b['replicate_start']}, {b['replicate_stop']})"
            )
        elif A.clean_json(a) != A.clean_json(b):
            out.append(f"cell {c}: saved and requested entries differ")
    return sorted(out)


def merge(paths: list[Path], out: Path, inventory_path: Path) -> dict[str, Any]:
    """Merge complete result files into the declared final inventory.

    Each part must be complete and its cells exactly its own inventory; frozen manifests
    must match each other and the merging code's sources; cells must be unique (identical
    copies in different parts collapse) and their union must equal the declared
    inventory, cell by cell (seed, parameters, replicate range and count)."""
    docs = [load_results(p) for p in paths]
    ref = frozen_part(docs[0]["manifest"])
    for p, d in zip(paths, docs, strict=True):
        if frozen_part(d["manifest"]) != ref:
            diff = sorted(k for k, v in frozen_part(d["manifest"]).items() if v != ref[k])
            raise SystemExit(f"{p}: manifest differs from {paths[0]} in {diff}")
        if d["manifest"]["status"] != "complete":
            raise SystemExit(f"{p}: status is {d['manifest']['status']!r}, not 'complete'")
    if source_hashes() != ref["sources_sha256"]:
        changed = sorted(k for k, v in source_hashes().items() if ref["sources_sha256"].get(k) != v)
        raise SystemExit(f"the merging code's sources differ from the parts' sources: {changed}")
    decl = load_inventory(inventory_path)
    if decl["base_seed"] != ref["base_seed"]:
        raise SystemExit(f"{inventory_path}: base seed {decl['base_seed']} != {ref['base_seed']}")
    if A.clean_json(decl["scenario_parameters"]) != ref["scenario_parameters"]:
        raise SystemExit(f"{inventory_path}: scenario parameters differ from the parts'")
    final = check_inventory(
        decl["cells"], ref["base_seed"], ref["scenario_parameters"], str(inventory_path)
    )
    cells: dict[str, dict[str, Any]] = {}
    for p, d in zip(paths, docs, strict=True):
        own = check_inventory(
            d["manifest"]["inventory"], ref["base_seed"], ref["scenario_parameters"], str(p)
        )
        got = verify_cells(d["cells"], own, str(p))
        if set(got) != set(own):
            raise SystemExit(f"{p}: complete but missing cells {sorted(set(own) - set(got))}")
        for cid, c in got.items():
            if cid in cells and A.clean_json(cells[cid]) != A.clean_json(c):
                raise SystemExit(f"{p}: cell {cid} differs from an earlier file")
            cells.setdefault(cid, c)
    extra, absent = sorted(set(cells) - set(final)), sorted(set(final) - set(cells))
    if extra or absent:
        raise SystemExit(
            f"merged cells differ from the declared inventory {inventory_path}: "
            f"missing {absent}, not declared {extra}"
        )
    verify_cells(list(cells.values()), final, "merged")
    t = now()
    manifest = {k: docs[0]["manifest"][k] for k in REQUIRED_MANIFEST} | {
        "pilot": docs[0]["manifest"].get("pilot"),
        "status": "complete",
        "inventory": decl["cells"],
        "inventory_sha256": sha256_json(decl["cells"]),
        "inventory_file": {"path": str(inventory_path), "sha256": sha256_file(inventory_path)},
        "command": [sys.executable, *sys.argv],
        "arguments": {"merge": [str(p) for p in paths], "inventory": str(inventory_path)},
        "workers": None,
        "started": t,
        "checkpoint_time": t,
        "completed_time": t,
        "merge_provenance": [
            {
                "file": str(p),
                "sha256": sha256_file(p),
                "command": d["manifest"]["command"],
                "arguments": d["manifest"]["arguments"],
                "started": d["manifest"]["started"],
                "completed_time": d["manifest"]["completed_time"],
                "workers": d["manifest"]["workers"],
                "inventory_sha256": d["manifest"]["inventory_sha256"],
                "cells": [c["cell_seed"] for c in d["cells"]],
            }
            for p, d in zip(paths, docs, strict=True)
        ],
    }
    order = [e["cell_seed"] for e in decl["cells"]]
    merged = {"manifest": manifest, "cells": [cells[c] for c in order]}
    out.write_text(json.dumps(A.clean_json(merged), indent=1))
    return merged


# --- output ---------------------------------------------------------------------------


def _f(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def _ci(t):
    return f"[{t[0]:.4f}, {t[1]:.4f}]"


def table(results: list[dict[str, Any]]) -> str:
    out = [
        "| Scenario | Module | Pop seed | Reps | True P | True D | Interval | Lower-tail "
        "failures (rate, CP95) | Upper-tail failures (rate, CP95) | Mean width |",
        "|---|---|---:|---:|---:|---:|---|---|---|---:|",
    ]
    for r in results:
        for key, lab in (
            ("primary", "primary exact"),
            ("region", "co-primary region"),
            ("kg", "KG (secondary)"),
            ("concordance_pass2", "concordance, 2 passes"),
            ("concordance_pass1_only", "concordance, pass 1 only"),
        ):
            t = r[key]
            out.append(
                f"| {r['scenario']} | {r['module']} | {r['pop_seed']} | {t['reported']} | "
                f"{r['P']:.4f} | {r['D']:+.4f} | {lab} | {t['miss_low']} "
                f"({_f(t['miss_low_rate'], 4)}, {_ci(t['miss_low_cp95'])}) | {t['miss_high']} "
                f"({_f(t['miss_high_rate'], 4)}, {_ci(t['miss_high_cp95'])}) | "
                f"{_f(t['mean_width'])} |"
            )
    return "\n".join(out)


def _write(path: Path, manifest: dict[str, Any], cells: list[dict[str, Any]]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(A.clean_json({"manifest": manifest, "cells": cells}), indent=1))
    tmp.replace(path)  # a checkpoint is never left half-written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--key", type=Path, default=A.DEFAULT_KEY)
    ap.add_argument("--frame", type=Path)
    ap.add_argument("--main-reps", type=int, default=23_410)
    ap.add_argument("--grid-reps", type=int, default=2_000)
    ap.add_argument("--pop-seeds", type=int, nargs="+", default=[101, 202, 303])
    ap.add_argument("--grid-pop-seeds", type=int, nargs="+", default=[101, 202])
    ap.add_argument("--seed", type=int, default=20261016)
    ap.add_argument(
        "--scenario",
        nargs="+",
        default=["all"],
        help="one or more of: all, main, grid, scenario names",
    )
    ap.add_argument("--modules", nargs="+", default=["metadiscourse", "phrase"])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument(
        "--resume",
        action="store_true",
        help="continue the same request in --out: its inventory must equal this one",
    )
    ap.add_argument(
        "--write-inventory",
        type=Path,
        metavar="PATH",
        help="write the required-cell inventory for these options, then stop",
    )
    ap.add_argument("--merge", nargs="+", type=Path, metavar="RESULTS", help="merge, then stop")
    ap.add_argument(
        "--inventory", type=Path, help="declared final inventory that --merge must equal"
    )
    args = ap.parse_args(argv)
    if args.merge:
        if not (args.out and args.inventory):
            ap.error("--merge needs --out and --inventory")
        merged = merge(args.merge, args.out, args.inventory)
        if args.md:
            args.md.write_text(table(merged["cells"]) + "\n")
        print(f"merged {len(merged['cells'])} cells from {len(args.merge)} files -> {args.out}")
        return 0
    if args.write_inventory:
        doc = inventory_document(args)
        args.write_inventory.write_text(json.dumps(doc, indent=1) + "\n")
        print(f"{len(doc['cells'])} cells -> {args.write_inventory}")
        return 0
    inv = inventory(args)
    key_rows = A.read_jsonl(args.key)
    frame_path = args.frame or args.key.parent / "frame.json"
    if not frame_path.exists():
        frame_path = None
    frame = json.loads(frame_path.read_text()) if frame_path else None
    manifest = make_manifest(args, args.key, frame_path, inv)
    required = check_inventory(
        inv, args.seed, manifest["scenario_parameters"], "requested inventory"
    )
    cells: list[dict[str, Any]] = []
    old_status = None
    if args.out and args.out.exists():
        if not args.resume:
            raise SystemExit(f"{args.out} exists: use --resume to continue it, or a new --out")
        old = load_results(args.out)
        if frozen_part(old["manifest"]) != frozen_part(manifest):
            diff = sorted(
                k for k, v in frozen_part(old["manifest"]).items() if v != frozen_part(manifest)[k]
            )
            raise SystemExit(f"--resume: {args.out} has a different manifest ({diff})")
        diff = _inventory_diff(old["manifest"]["inventory"], inv)
        if diff:
            raise SystemExit(
                f"--resume: {args.out} was run for a different request; resume continues the "
                "same request only and never extends or shortens a cell. Use a new --out "
                "(and --merge) instead:\n  " + "\n  ".join(diff)
            )
        cells = list(verify_cells(old["cells"], required, f"--resume {args.out}").values())
        manifest["started"] = old["manifest"]["started"]
        manifest["checkpoint_time"] = old["manifest"]["checkpoint_time"]
        manifest["resumed_from"] = old["manifest"]
        old_status = old["manifest"]["status"]
    done = {c["cell_seed"] for c in cells}
    specs = MAIN | GRID
    for e in inv:
        if e["cell_seed"] in done:
            continue
        t0 = time.time()
        r = run(
            e["scenario"],
            specs[e["scenario"]],
            e["module"],
            key_rows,
            frame,
            e["replicate_stop"] - e["replicate_start"],
            e["pop_seed"],
            args.seed,
            args.workers,
            manifest["sources_sha256"],
            start=e["replicate_start"],
        )
        r["seconds"] = round(time.time() - t0, 1)
        cells.append(r)
        print(table([r]).split("\n", 2)[2], flush=True)
        if args.out:
            manifest["checkpoint_time"] = now()
            _write(args.out, manifest, cells)
    if source_hashes() != manifest["sources_sha256"]:
        raise SystemExit("source files changed during the run; restart from scratch")
    got = verify_cells(cells, required, "run")
    if set(got) != set(required):
        raise SystemExit(f"run incomplete: missing {sorted(set(required) - set(got))}")
    cells = [got[e["cell_seed"]] for e in inv]  # inventory order
    if args.out and len(done) == len(inv) and old_status == "complete":
        print(f"{args.out} is already complete; left unchanged")
    else:
        t = now()
        manifest |= {"status": "complete", "completed_time": t}  # checkpoint: last cell
        if args.out:
            _write(args.out, manifest, cells)
    if args.md:
        args.md.write_text(table(cells) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
