"""`accept`: the frozen acceptance calculation (protocol "Estimation, uncertainty and
unresolved labels", "Acceptance gates", "Definite and possible losses").

References. For every module and outcome, analyse.reference(rows, outcome,
[A, B], adjudicator): primaries definite and equal, else the adjudicator's
definite value, else unresolved (None). Maintainer labels never enter. Each
payload has one reference per outcome; every frame row with that payload uses
it.

Per gated outcome o (STRICT; LENIENT or LIST_LENIENT = INV), a sampled affected
baseline row b with counterparts c_1..c_j (each with the crosswalk's resolved
flag) has loss bounds
    definite retention = some counterpart has y_o = 1 and a resolved correspondence
    possible retention = some counterpart has y_o in {1, unresolved}
    loss_hi = 1 if y_o(b) in {1, unresolved} and not definite retention, else 0
    loss_lo = 1 if y_o(b) = 1 and not possible retention, else 0
(a definitely incorrect baseline hit contributes 0; a REMOVED row has no
counterpart; an unresolved correspondence never proves retention). For STRICT,
y = 1 means a supported, correct emitted claim; for INV, a supported occurrence
in the same inventory (CORRECT or WRONG_CATEGORY; CORRECT or
WRONG_SENSE_LISTED). Additions never offset losses.

Bounds, a = .05 / J (ledger.A):
1. Removal (each family and COMPLETE, per module; genuine-deletion frame =
   REMOVED cell, baseline hits with no counterpart at the same occurrence; a
   claim dropped at a retained span is CLAIM_DROPPED, never in this frame, audit
   r2 B4): N = frame size, n = assigned SRS size, k_hi = sampled rows with y_INV
   in {1, unresolved}; bound = estimators.hyper_ucl(k_hi, n, N, a) / N.
   N = 0: not applicable.
2. U_loss (COMPLETE, per module and gated outcome): cells (N_h, n_h, k_lo_h,
   k_hi_h) over the six affected cells with N_h > 0, full assigned n_h;
   per-cell k_lo_h / k_hi_h are sums of the rows' exact bounds (loss_bounds).
   Rows sharing an unresolved payload are completed separately, so a cell total
   can exceed the highest total consistent with the shared variables: a declared
   conservative relaxation (it can only raise U_loss; clarifications 1.2);
   U_loss = sum N_h x estimators.exact_limits(cells, alpha_lo=None,
   alpha_hi=a)["upper"]; no positive-size cell: U_loss = 0.
3. L_success (per module and gated outcome): the stratified baseline sample,
   cells (N_h, n_h, definite successes, definite + unresolved);
   L_success = sum N_h x exact_limits(cells, alpha_lo=a, alpha_hi=None)["lower"].
   Empty baseline population: not assessable.
Cumulative loss fraction = min(1, U_loss / L_success) when L_success > 0;
otherwise the cumulative gate is not assessable.

Gates per module: every applicable removal bound <= .15 and both cumulative
fractions <= .05. Breach certificates (fail; no confidence spent): distinct
sampled definitely successful deletions / all deletions > .15, or distinct
sampled definite baseline losses / the full baseline hit count > .05.
Status: fail if any certificate holds; pass if every applicable removal gate
and every required cumulative gate passes and the procedure is complete;
otherwise inconclusive. The candidate passes only if both modules pass; fails
if either module fails.

Descriptive (outside the simultaneous family, never gated): pointwise 95%
worst-case intervals for the precision of ADDED and CHANGED final-output frames
(exact_limits on (N, n, definite correct, definite correct + unresolved) at
.025 per side), paired old/new outcomes of changed claims, and definite-correct /
definite-incorrect / unresolved counts for every frame and outcome. PHRASAL and
CONNECTIVE are diagnostics (counts only).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import analyse
import estimators as E

from fixcheck.common import (
    read_json,
    refuse_existing,
    set_command,
    sha256_file,
    write_json,
    write_step_manifest,
)
from fixcheck.crosswalk import AFFECTED_CELLS, CLAIM_DROPPED, FINAL_FRAMES, REMOVED
from fixcheck.ledger import (
    COMPLETE,
    CUMULATIVE_TOLERANCE,
    DIAGNOSTIC_OUTCOMES,
    FAMILIES,
    FAMILY_MODULE,
    GATED_OUTCOMES,
    INV,
    MODULES,
    REMOVAL_TOLERANCE,
    A,
    component_id,
    ledger_components,
)
from fixcheck.registry import REGISTRY as REG_DEFAULT
from fixcheck.sampling import BASELINE_SUCCESS, SRS_MAX

Y = int | None  # 1, 0 or None (unresolved)


# --- pure arithmetic ----------------------------------------------------------------


def loss_bounds(
    y_b: Y, counterparts: list[tuple[Any, ...]], b_payload: str | None = None
) -> tuple[int, int]:
    """(loss_lo, loss_hi) for one sampled baseline row under one outcome: exact.

    counterparts: (y, resolved) or (y, resolved, payload). Every distinct payload is
    one reference variable (audit r1 S1): a counterpart sharing the baseline's
    payload shares its reference. The bounds are the lowest and highest loss over
    every completion of the unresolved variables, solved analytically (audit r2
    S1; no enumeration, so exact for any number of variables):
    - a loss needs a successful baseline, so a definitely unsuccessful baseline
      gives (0, 0);
    - highest: set the baseline to 1 if it is unresolved, every other unresolved
      variable to 0. Only a resolved correspondence retains. The loss is then 1
      unless a resolved counterpart is known to be 1 or shares the baseline's
      variable (then it equals the baseline's value, so the loss is identically 0);
    - lowest: set the baseline to 0 if it is unresolved (no loss); a known
      successful baseline is lost only if no counterpart, resolved or not, can be 1.
    A payload that carries two different known references is an error."""
    bvar = b_payload if b_payload is not None else "\0b"
    cps = [
        (c[0], c[1], c[2] if len(c) > 2 and c[2] is not None else f"\0c{i}")
        for i, c in enumerate(counterparts)
    ]
    known: dict[str, Y] = {bvar: y_b}
    for y, _, p in cps:
        if p in known and known[p] is not None and y is not None and known[p] != y:
            raise ValueError(f"payload {p} carries two different references")
        if known.get(p) is None:
            known[p] = y
    yb = known[bvar]
    if yb == 0:
        return 0, 0
    retained_hi = any(res is True and (p == bvar or known[p] == 1) for _, res, p in cps)
    hi = int(not retained_hi)
    lo = int(yb == 1 and not any(p == bvar or known[p] in (1, None) for _, _, p in cps))
    return lo, hi


@functools.lru_cache(maxsize=200_000)
def _limits(cells: tuple[tuple[int, int, int, int], ...], alo: float | None, ahi: float | None):
    """estimators.exact_limits, memoised (a pure function of its arguments)."""
    return E.exact_limits(list(cells), alpha_lo=alo, alpha_hi=ahi)


def removal_component(
    N: int, ys: list[Y], a: float = A, tol: float = REMOVAL_TOLERANCE
) -> dict[str, Any]:
    n = len(ys)
    k_lo = sum(y == 1 for y in ys)
    k_hi = sum(y in (1, None) for y in ys)
    rec: dict[str, Any] = {
        "N": N,
        "n": n,
        "k_lo": k_lo,
        "k_hi": k_hi,
        "counts": _counts(ys),
    }
    if N == 0:
        return rec | {
            "status": "not_applicable",
            "bound": None,
            "passes": None,
            "breach_certificate": False,
        }
    if not 0 < n <= N:
        raise ValueError(f"removal frame: need 0 < n <= N (n={n}, N={N})")
    bound = E.hyper_ucl(k_hi, n, N, a) / N
    return rec | {
        "status": "computed",
        "bound": bound,
        "passes": bound <= tol,
        "breach_lower": k_lo / N,
        "breach_certificate": k_lo / N > tol,
    }


def u_loss(cells: list[tuple[int, int, int, int]], a: float = A) -> dict[str, Any]:
    pos = [c for c in cells if c[0] > 0]
    if not pos:
        return {"U_loss": 0.0, "upper_proportion": None, "method": "no positive-size affected cell"}
    lim = _limits(tuple(pos), None, a)
    total = sum(c[0] for c in pos)
    return {
        "U_loss": total * lim["upper"],
        "upper_proportion": lim["upper"],
        "method": lim["method"],
        "N_affected": total,
    }


def l_success(cells: list[tuple[int, int, int, int]], a: float = A) -> dict[str, Any]:
    pos = [c for c in cells if c[0] > 0]
    if not pos:
        return {"L_success": None, "lower_proportion": None, "method": "empty baseline population"}
    lim = _limits(tuple(pos), a, None)
    total = sum(c[0] for c in pos)
    return {
        "L_success": total * lim["lower"],
        "lower_proportion": lim["lower"],
        "method": lim["method"],
        "N_baseline": total,
    }


def cumulative_gate(U: float, L: float | None, tol: float = CUMULATIVE_TOLERANCE) -> dict[str, Any]:
    if L is None:
        return {
            "fraction": None,
            "status": "not_assessable",
            "reason": "empty baseline population",
            "passes": None,
        }
    if L <= 0:
        return {
            "fraction": None,
            "status": "not_assessable",
            "reason": "zero baseline-success lower bound",
            "passes": None,
        }
    frac = min(1.0, U / L)
    return {"fraction": frac, "status": "computed", "passes": frac <= tol}


def descriptive_interval(N: int, ys: list[Y], alpha_side: float = 0.025) -> dict[str, Any]:
    c = _counts(ys)
    if N == 0:
        return {"N": 0, "n": 0, **c, "interval95": None}
    k_lo, k_hi = c["definite_correct"], c["definite_correct"] + c["unresolved"]
    lim = E.exact_limits([(N, len(ys), k_lo, k_hi)], alpha_lo=alpha_side, alpha_hi=alpha_side)
    return {
        "N": N,
        "n": len(ys),
        **c,
        "interval95": [lim["lower"], lim["upper"]],
        "assigned_sample_worst_case_range": [k_lo / len(ys), k_hi / len(ys)] if ys else None,
        "method": lim["method"],
        "note": "pointwise, worst-case completion; descriptive, outside the acceptance family",
    }


def _counts(ys: list[Y]) -> dict[str, int]:
    return {
        "definite_correct": sum(y == 1 for y in ys),
        "definite_incorrect": sum(y == 0 for y in ys),
        "unresolved": sum(y is None for y in ys),
    }


# --- round data ----------------------------------------------------------------------


def frames_from_key(key: list[dict[str, Any]], selection: dict[str, Any]) -> tuple[dict, dict]:
    """Frame rows and baseline-success strata, as payload hashes, from the key's memberships."""
    frames: dict[str, dict[str, Any]] = {
        fid: {"N": f["N"], "n": f["n"], "rows": {}, "counterparts": defaultdict(list)}
        for fid, f in selection["frames"].items()
    }
    bsel = selection["baseline_success"]["strata"]
    bs: dict[str, dict[str, Any]] = {
        m: {sub: {"N_h": d["N_h"], "n_h": d["n_h"], "rows": {}} for sub, d in bsel[m].items()}
        for m in MODULES
    }
    for k in key:
        p = k["payload_sha256"]
        for mb in k["memberships"]:
            fr = mb["frame"]
            if fr.startswith(BASELINE_SUCCESS):
                bs[fr.split("|")[1]][mb["substratum"]]["rows"][mb["row"]] = p
            elif mb["role"] == "sampled":
                frames[fr]["rows"][mb["row"]] = p
            else:
                kind = "sibling" if mb["role"] == "sibling" else "counterpart"
                frames[fr]["counterparts"][mb["of"]].append((p, mb["resolved"], kind))
    for fid, f in frames.items():
        if set(f["rows"]) != set(selection["frames"][fid]["selected"]):
            raise ValueError(f"{fid}: key rows differ from the archived selection")
        f["counterparts"] = {h: sorted(v) for h, v in f["counterparts"].items()}
    for m in MODULES:
        for sub, d in bs[m].items():
            if set(d["rows"]) != set(bsel[m][sub]["selected"]):
                raise ValueError(f"baseline success {m} {sub}: key rows differ from the selection")
    return frames, bs


def compute(
    frames: dict[str, dict[str, Any]],
    bs: dict[str, dict[str, Any]],
    refs: dict[tuple[str, str], dict[str, Y]],
    configs: list[str],
    rnd: int = 1,
    a: float = A,
    procedure_problems: list[str] | None = None,
    descriptive: bool = True,
) -> dict[str, Any]:
    """The frozen acceptance calculation on frames (payload hashes) and references.

    frames[fid] = {"N", "n", "rows": {row: payload},
                   "counterparts": {row: [(payload, resolved, "counterpart" | "sibling")]}}
    Sibling links (same-span candidate hits, crosswalk loss layer) count for the
    inventory outcome only; STRICT uses the row's own counterparts (audit r1 B4).
    With descriptive=False only the gated arithmetic runs (used by power.py).
    Status: any procedure problem (given or found here) makes every module and the
    round inconclusive, before fail or pass (clarifications 3.4, "Incomplete
    procedure"; amended after audit r2 N2); breach_certificates are still reported.
    bs[module][sub] = {"N_h", "n_h", "rows": {row: payload}}
    refs[(module, outcome)][payload] = 1 | 0 | None
    """
    problems = list(procedure_problems or [])

    def y(m: str, oc: str, p: str) -> Y:
        return refs.get((m, oc), {}).get(p)

    def links(m: str, oc: str, f: dict[str, Any], row: str) -> list[tuple[Y, Any, str]]:
        """(reference, resolved, payload) of the links that can retain under outcome oc."""
        return [
            (y(m, oc, q), res, q)
            for q, res, *kind in f["counterparts"].get(row, [])
            if not kind or kind[0] == "counterpart" or oc == INV[m]
        ]

    def emitted(f: dict[str, Any], row: str) -> list:
        return [c for c in f["counterparts"].get(row, []) if len(c) < 3 or c[2] == "counterpart"]

    def ys_for(m: str, oc: str, payloads: list[str]) -> list[Y]:
        """References of the payloads to which the outcome applies (CONNECTIVE: transitions)."""
        if oc == "CONNECTIVE":
            return [refs[(m, oc)][p] for p in payloads if p in refs.get((m, oc), {})]
        return [y(m, oc, p) for p in payloads]

    out: dict[str, Any] = {"a": a, "round": rnd, "modules": {}, "components": {}}
    for m in MODULES:
        inv = INV[m]
        mod: dict[str, Any] = {
            "removal": {},
            "loss": {},
            "success": {},
            "cumulative": {},
            "frames": {},
        }
        n_base = sum(d["N_h"] for d in bs[m].values())
        for c in configs:
            fid = f"{c}|{m}|affected|{REMOVED}"
            f = frames[fid]
            if f["N"] and f["n"] != min(SRS_MAX, f["N"]):
                problems.append(f"{fid}: n {f['n']} != min(200, N)")
            ys = [y(m, inv, p) for _, p in sorted(f["rows"].items())]
            rc = removal_component(f["N"], ys, a)
            cid = component_id(rnd, m, c, "removal")
            rc["component"] = cid
            if c != COMPLETE and FAMILY_MODULE[c] != m and f["N"]:
                rc["note"] = (
                    "family not assigned to this module but its deletion frame is non-empty"
                )
            mod["removal"][c] = rc
            out["components"][cid] = {"status": rc["status"], "value": rc.get("bound")}
        # Loss totals over the COMPLETE affected cells.
        definite_losses: dict[str, set[str]] = {}
        for oc in GATED_OUTCOMES[m]:
            cells, detail = [], {}
            dl: set[str] = set()
            for cell in AFFECTED_CELLS:
                f = frames[f"{COMPLETE}|{m}|affected|{cell}"]
                if f["N"] and f["n"] != min(SRS_MAX, f["N"]):
                    problems.append(f"{COMPLETE}|{m}|{cell}: n {f['n']} != min(200, N)")
                k_lo = k_hi = 0
                for row, p in sorted(f["rows"].items()):
                    if cell == CLAIM_DROPPED:
                        if not f["counterparts"].get(row):
                            problems.append(f"{cell} row {row} has no labelled same-span sibling")
                    elif cell != REMOVED and not emitted(f, row):
                        problems.append(f"{cell} row {row} has no labelled counterpart")
                    lo, hi = loss_bounds(y(m, oc, p), links(m, oc, f, row), p)
                    k_lo += lo
                    k_hi += hi
                    if lo:
                        dl.add(row)
                cells.append((f["N"], f["n"], k_lo, k_hi))
                detail[cell] = {"N_h": f["N"], "n_h": f["n"], "k_lo": k_lo, "k_hi": k_hi}
            res = u_loss(cells, a)
            kind = "loss_STRICT" if oc == "STRICT" else "loss_INV"
            cid = component_id(rnd, m, COMPLETE, kind)
            mod["loss"][oc] = {"component": cid, "cells": detail, **res}
            out["components"][cid] = {"status": "computed", "value": res["U_loss"]}
            definite_losses[oc] = dl
            scells, sdetail = [], {}
            for sub, d in sorted(bs[m].items()):
                ys = [y(m, oc, p) for _, p in sorted(d["rows"].items())]
                if len(ys) != d["n_h"]:
                    problems.append(f"baseline success {m} {sub}: {len(ys)} rows != n_h {d['n_h']}")
                k_lo = sum(v == 1 for v in ys)
                k_hi = sum(v in (1, None) for v in ys)
                scells.append((d["N_h"], d["n_h"], k_lo, k_hi))
                sdetail[sub] = {"N_h": d["N_h"], "n_h": d["n_h"], "k_lo": k_lo, "k_hi": k_hi}
            sres = l_success(scells, a)
            kind = "success_STRICT" if oc == "STRICT" else "success_INV"
            scid = component_id(rnd, m, COMPLETE, kind)
            mod["success"][oc] = {"component": scid, "strata": sdetail, **sres}
            out["components"][scid] = {
                "status": "computed" if sres["L_success"] is not None else "not_assessable",
                "value": sres["L_success"],
            }
            gate = cumulative_gate(res["U_loss"], sres["L_success"])
            cert_lower = (len(dl) / n_base) if n_base else None
            gate |= {
                "U_loss": res["U_loss"],
                "L_success": sres["L_success"],
                "definite_losses_sampled": len(dl),
                "N_baseline": n_base,
                "breach_lower": cert_lower,
                "breach_certificate": bool(n_base) and len(dl) / n_base > CUMULATIVE_TOLERANCE,
            }
            mod["cumulative"][oc] = gate
        # Status.
        rem = [r for r in mod["removal"].values() if r["status"] == "computed"]
        breach = any(r["breach_certificate"] for r in rem) or any(
            g["breach_certificate"] for g in mod["cumulative"].values()
        )
        all_pass = all(r["passes"] for r in rem) and all(
            g["status"] == "computed" and g["passes"] for g in mod["cumulative"].values()
        )
        mod["status"] = (
            "inconclusive"
            if problems
            else ("fail" if breach else ("pass" if all_pass else "inconclusive"))
        )
        mod["breach_certificates"] = [
            f"removal {c}" for c, r in mod["removal"].items() if r.get("breach_certificate")
        ] + [f"cumulative {oc}" for oc, g in mod["cumulative"].items() if g["breach_certificate"]]
        out["modules"][m] = mod
        if not descriptive:
            continue
        # Descriptive.
        for c in configs:
            for fr in FINAL_FRAMES:
                fid = f"{c}|{m}|final|{fr}"
                f = frames[fid]
                payloads = [p for _, p in sorted(f["rows"].items())]
                mod["frames"][fid] = {
                    oc: descriptive_interval(f["N"], ys_for(m, oc, payloads))
                    if oc != "CONNECTIVE"
                    else {"counts_claimed_transitions": _counts(ys_for(m, oc, payloads))}
                    for oc in (*GATED_OUTCOMES[m], *DIAGNOSTIC_OUTCOMES[m])
                }
            for cell in AFFECTED_CELLS:
                fid = f"{c}|{m}|affected|{cell}"
                f = frames[fid]
                entry: dict[str, Any] = {"N": f["N"], "n": f["n"]}
                rows = sorted(f["rows"].items())
                for oc in (*GATED_OUTCOMES[m], *DIAGNOSTIC_OUTCOMES[m]):
                    entry[oc] = {"baseline": _counts(ys_for(m, oc, [p for _, p in rows]))}
                    if oc == "CONNECTIVE":
                        continue  # claimed transitions only: counts, no loss accounting
                    if cell != REMOVED:
                        pairs: Counter = Counter()
                        for row, p in rows:
                            for q, res, *_ in emitted(f, row):
                                tag = "" if res else " (unresolved correspondence)"
                                pairs[f"{_s(y(m, oc, p))}->{_s(y(m, oc, q))}{tag}"] += 1
                        entry[oc]["paired_old_new_link_counts"] = dict(sorted(pairs.items()))
                        entry[oc]["paired_old_new_note"] = (
                            "unweighted sampled LINK counts: a baseline row with several "
                            "counterparts contributes several entries; not population estimates"
                        )
                        entry[oc]["distinct_baseline_rows"] = len(rows)
                        entry[oc]["inclusion_probability"] = (f["n"] / f["N"]) if f["N"] else None
                    lo = hi = 0
                    for row, p in rows:
                        d_lo, d_hi = loss_bounds(y(m, oc, p), links(m, oc, f, row), p)
                        lo += d_lo
                        hi += d_hi
                    entry[oc]["sampled_losses"] = {"definite": lo, "possible_max": hi}
                mod["frames"][fid] = entry
        bcounts = {
            oc: _counts(ys_for(m, oc, [p for d in bs[m].values() for p in d["rows"].values()]))
            for oc in (*GATED_OUTCOMES[m], *DIAGNOSTIC_OUTCOMES[m])
        }
        mod["frames"][f"{BASELINE_SUCCESS}|{m}"] = bcounts
    if problems:  # also a problem found only in a later module
        for m in MODULES:
            out["modules"][m]["status"] = "inconclusive"
    statuses = [out["modules"][m]["status"] for m in MODULES]
    out["procedure_problems"] = problems
    out["status"] = (
        "inconclusive"
        if problems
        else (
            "fail"
            if "fail" in statuses
            else ("pass" if all(s == "pass" for s in statuses) else "inconclusive")
        )
    )
    out["decision_wording"] = {
        "pass": "passed the loss safeguards (not 'all fixes validated')",
        "fail": "failed: a deterministic breach certificate holds; the checked candidate cannot be kept",
        "inconclusive": "inconclusive: not passed and no breach established; the checked candidate cannot be kept",
    }[out["status"]]
    # Ledger components of this round not computed above.
    for comp in ledger_components():
        if comp["round"] != rnd or comp["id"] in out["components"]:
            continue
        out["components"][comp["id"]] = {"status": "reserved", "value": None}
    return out


def _s(v: Y) -> str:
    return "U" if v is None else str(v)


def refs_from_labels(key: list[dict[str, Any]], prim, adj) -> dict[tuple[str, str], dict[str, Y]]:
    refs: dict[tuple[str, str], dict[str, Y]] = {}
    for m in MODULES:
        rows = [
            {"id": k["id"], "module": m, "category": k["category"]} for k in key if k["module"] == m
        ]
        pay = {k["id"]: k["payload_sha256"] for k in key}
        for oc in analyse.OUTCOMES[m]:
            ref = analyse.reference(rows, oc, prim, adj)
            refs[(m, oc)] = {pay[i]: r["y"] for i, r in ref.items()}
    return refs


def to_markdown(res: dict[str, Any]) -> str:
    L = [
        f"# Fix-check round {res['round']}: acceptance",
        "",
        f"**Status: {res['status']}** — {res['decision_wording']}",
        "",
        f"a = .05/68 = {res['a']:.9f}",
        "",
    ]
    if "mode" in res:
        L += [f"Mode: {res['mode']}; production_eligible: {res['production_eligible']}", ""]
    for m, mod in res["modules"].items():
        L += [
            f"## {m}: {mod['status']}",
            "",
            "| removal frame | N | n | k_lo | k_hi | bound | ≤ .15 | certificate |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for c, r in mod["removal"].items():
            b = "n/a" if r["bound"] is None else f"{r['bound']:.4f}"
            L.append(
                f"| {c} | {r['N']} | {r['n']} | {r['k_lo']} | {r['k_hi']} | {b} | {r['passes']} | {r['breach_certificate']} |"
            )
        L += [
            "",
            "| outcome | U_loss | L_success | fraction | ≤ .05 | definite losses / N_base | certificate |",
            "|---|---|---|---|---|---|---|",
        ]
        for oc, g in mod["cumulative"].items():
            f = "n/a" if g["fraction"] is None else f"{g['fraction']:.4f}"
            ls = "n/a" if g["L_success"] is None else f"{g['L_success']:.1f}"
            L.append(
                f"| {oc} | {g['U_loss']:.1f} | {ls} | {f} | {g['passes']} | {g['definite_losses_sampled']}/{g['N_baseline']} | {g['breach_certificate']} |"
            )
        L.append("")
    if res["procedure_problems"]:
        L += ["## Procedure problems", ""] + [f"- {p}" for p in res["procedure_problems"]] + [""]
    return "\n".join(L)


def acceptance_of(
    assign_dir: Path,
    sample_dir: Path,
    label_files: dict[str, Path],
    adjudicator: Path | None,
    rnd: int,
    problems: list[str],
    flash_dir: Path | None = None,
) -> dict[str, Any]:
    """The acceptance calculation on one assignment's final label files."""
    from fixcheck.assign import load_round_labels

    selection = read_json(sample_dir / "selection.json")
    flash_dir = flash_dir or assign_dir / "flash"
    flash_ids = (flash_dir / "flash_ids.txt").read_text().split()
    if flash_ids and (adjudicator is None or not adjudicator.exists()):
        problems.append(
            f"{len(flash_ids)} items need adjudication but no adjudicator labels were given"
        )
        adjudicator = None
    items, key, prim, adj = load_round_labels(
        assign_dir, label_files, adjudicator if flash_ids else None, flash_dir
    )
    refs = refs_from_labels(key, prim, adj)
    frames, bs = frames_from_key(key, selection)
    configs = [
        c for c in (COMPLETE, *FAMILIES) if f"{c}|metadiscourse|affected|{REMOVED}" in frames
    ]
    if len(configs) != 1 + len(FAMILIES):
        problems.append(f"only configurations {configs} were sampled")
    res = compute(frames, bs, refs, configs, rnd=rnd, procedure_problems=problems)
    res["labels"] = {
        r: {"file": str(label_files[r]), "sha256": sha256_file(label_files[r]), **ls.summary()}
        for r, ls in zip(("A", "B"), prim, strict=True)
    }
    res["labels"]["adjudicator"] = (
        None
        if adj is None
        else {"file": str(adjudicator), "sha256": sha256_file(adjudicator), **adj.summary()}
    )
    res["labels"]["n_items"] = len(items)
    res["labels"]["n_flash"] = len(flash_ids)
    res["reference_sources"] = {
        f"{m}|{oc}": dict(
            Counter(
                r["source"]
                for r in analyse.reference(
                    [
                        {"id": k["id"], "module": m, "category": k["category"]}
                        for k in key
                        if k["module"] == m
                    ],
                    oc,
                    prim,
                    adj,
                ).values()
            )
        )
        for m in MODULES
        for oc in analyse.OUTCOMES[m]
    }
    return res


def decision_entry(chk: dict[str, Any], status: str) -> dict[str, Any]:
    """The registry decision line of a checked package (audit r2 B2, B5)."""
    cinfo = chk["collection"]
    cand = cinfo.get("candidate") or {}
    entry = {
        "type": "decision",
        "round": cinfo.get("round"),
        "candidate_commit": cand.get("commit"),
        "candidate_tree_sha256": cand.get("tree_sha256"),
        "seed": cinfo.get("seed"),
        "reservation_sha256": cinfo.get("reservation_sha256"),
        "freeze_record_sha256": cinfo.get("freeze_record_sha256"),
        "collection_texts_sha256": cinfo.get("texts_jsonl_sha256"),
        "source_refs": cinfo.get("source_refs_sha256") or [],
        "session_ids_sha256": (chk.get("sessions") or {}).get("session_ids_sha256", []),
        "transcripts_sha256": (chk.get("sessions") or {}).get("transcripts_sha256", []),
        "inputs_sha256": chk["inputs_sha256"],
        "status": status,
        "families": list(FAMILIES),
    }
    if cinfo.get("round") == 2:
        entry["round1_entry_sha256"] = (cinfo.get("round2") or {}).get("round1_entry_sha256")
    return entry


def _serialised(obj: Any) -> bytes:
    import json

    return (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()


def main(argv: list[str]) -> int:
    """Production acceptance consumes one round package (audit r1 B2, B3; audit r2 B2).

    Round number, candidate and component identities come from the package's
    freeze record. Every link of the hash chain is checked (fixcheck.package);
    in production any problem makes the result inconclusive (never pass).

    Modes:
    - production (default): the package's freeze record must be a production
      record and the registry the canonical, committed, append-only one; the
      decision is computed and then ATOMICALLY checked against and appended to
      the registry (registry.atomic_append). A refused registration writes no
      acceptance output. There is no unregistered production decision.
    - production refuses before computing anything if the round is registered as a
      procedure_failure (register-failure; audit r4 S1): that round is consumed; or if its
      collection is a shortfall (R4 Addendum 2: closed by register-failure instead).
    - production refuses before computing anything if the runtime doing acceptance,
      observed afresh, is not the frozen runtime (package link "runtime", audit r3 S3).
    - --check-only: the package chain check alone (the preview). It never
      computes or reports the acceptance arithmetic and never registers, so no
      label-derived status exists outside the registry.
    - --dry-run: only for a dry-run package (its freeze record says so): the
      mathematical status is reported, stamped production_eligible false, and
      nothing is registered."""
    set_command("accept", argv)
    ap = argparse.ArgumentParser(prog="fixcheck accept", description=__doc__.split("\n\n")[0])
    ap.add_argument("--package", type=Path, required=True, help="round package dir or package.json")
    ap.add_argument(
        "--dry-run", action="store_true", help="dry-run packages only: math, ineligible"
    )
    ap.add_argument("--check-only", action="store_true", help="package chain check only")
    ap.add_argument("--registry", type=Path, default=REG_DEFAULT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    from fixcheck import package as PK
    from fixcheck import registry as REG

    out = args.out.resolve()
    if args.dry_run and args.check_only:
        raise SystemExit("--dry-run and --check-only are separate modes")
    refuse_existing(
        out / ("package_check.json" if args.check_only else "acceptance.json"), args.overwrite
    )
    production = not (args.dry_run or args.check_only)
    if production:
        # the registry is checked before any production step (audit r2 B2)
        integ = REG.integrity(args.registry, REG.REPO)
        if not integ["ok"]:
            raise SystemExit("round registry refused:\n" + "\n".join(integ["problems"]))
    chk = PK.check_package(args.package)
    P = PK.resolve(args.package)
    cinfo = chk["collection"]
    rnd = cinfo.get("round")
    if rnd not in (1, 2):
        raise SystemExit(f"the package's freeze record has no valid round ({rnd})")
    if args.check_only:
        write_json(out / "package_check.json", chk)
        write_step_manifest(out, "accept_check_only", [out / "package_check.json"])
        print(f"package problems: {len(chk['problems'])} (check only; no decision)")
        return 0
    if args.dry_run and cinfo.get("dry_run") is not True:
        raise SystemExit(
            "--dry-run computes dry-run packages only; a production package is decided once, "
            "with registration (or use --check-only)"
        )
    if production and cinfo.get("dry_run") is not False:
        raise SystemExit("the package's freeze record is a dry run: use --dry-run")
    if production:
        # audit r4 S1: a round registered as procedure_failure is consumed; its normal
        # acceptance refuses permanently, before any arithmetic
        consumed = [
            e
            for e in REG.decisions(REG.load(args.registry))
            if e.get("status") == REG.FAILURE_STATUS
            and (
                e.get("reservation_sha256") == cinfo.get("reservation_sha256")
                or e.get("round") == rnd
            )
        ]
        if consumed:
            raise SystemExit(
                f"round {rnd} is registered as a procedure_failure: the round is consumed and "
                "is never accepted (refused before any decision)"
            )
        # R4 Addendum 2: accepting a shortfall stays forbidden; it is closed by register-failure
        cj = P["collect"] / "collection.json"
        col_status = read_json(cj).get("status") if cj.exists() else None
        if col_status == "shortfall":
            raise SystemExit(
                "the round's collection is a shortfall: acceptance is refused before any "
                "decision; close the round with register-failure (procedure_failure)"
            )
    if production and not chk["links"]["runtime"]["ok"]:
        # audit r3 S3: no decision is computed or registered under another runtime
        raise SystemExit(
            "production acceptance refused before any decision: "
            + "; ".join(chk["links"]["runtime"]["problems"])
        )
    problems = list(chk["problems"])
    L = P["labels"]
    files = {r: L / f"{r}.jsonl" for r in ("A", "B")}
    missing = [str(f) for f in files.values() if not f.exists()]
    if missing:
        raise SystemExit(f"final label files missing: {missing}")
    res = acceptance_of(
        P["assign"],
        P["sample"],
        files,
        L / "adjudicator.jsonl",
        rnd,
        problems if production else [],
        flash_dir=P["flash"],
    )
    res["mathematical_status"] = res["status"] if args.dry_run else None
    res["package_check"] = chk
    res["production_eligible"] = production and chk["production_eligible"]
    res["mode"] = "dry-run (not production-eligible)" if args.dry_run else "production"
    if args.dry_run:
        res["procedure_problems_not_applied"] = chk["problems"]
    res["candidate"] = cinfo.get("candidate")
    res["acceptance_runtime"] = chk.get("acceptance_runtime")
    entry = decision_entry(chk, res["status"])
    res["registry_entry"] = entry if production else None
    acc_bytes = _serialised(res)
    if production:
        reg_entry = dict(entry, acceptance_sha256=hashlib.sha256(acc_bytes).hexdigest())

        def make(entries):
            verdict, probs = REG.check_decision(entries, reg_entry)
            return verdict, probs, reg_entry

        verdict, rprobs, written = REG.atomic_append(args.registry, make, REG.REPO)
        if verdict not in ("append", "idempotent"):
            raise SystemExit("round registry refuses this decision:\n" + "\n".join(rprobs))
    out.mkdir(parents=True, exist_ok=True)
    (out / "acceptance.json").write_bytes(acc_bytes)
    (out / "acceptance.md").write_text(to_markdown(res), encoding="utf-8")
    comps = [
        dict(c, **res["components"].get(c["id"], {})) if c["round"] == rnd else c
        for c in ledger_components()
    ]
    write_json(out / "ledger_components_result.json", comps)
    outputs = [
        out / "acceptance.json",
        out / "acceptance.md",
        out / "ledger_components_result.json",
    ]
    if production:
        write_json(
            out / "registration.json",
            {"registry": str(Path(args.registry).resolve()), "verdict": verdict, "entry": written},
        )
        outputs.append(out / "registration.json")
    write_step_manifest(out, "accept", outputs)
    tag = " (dry run: mathematical status; not production-eligible)" if args.dry_run else ""
    print(f"status: {res['status']}{tag}")
    return 0
