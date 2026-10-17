"""`diff`: the frozen diff, occurrence crosswalk and change-type partition.

Uses hit frames only (never labels). Protocol: "Diff and label transfer" and
"Exhaustive affected-baseline frame".

Claim key (worker.py): (source identity, normalised-text SHA-256, module,
character span, claim), claim = category (metadiscourse) or PHRASE entry, rank
and sense. Matching is done within one group = (source identity, text hash,
module); hits of different texts or modules never correspond.

CROSSWALK RULE (deterministic; applied per group, in this order)
----------------------------------------------------------------
Step 1, same claim key. For every claim key present in both frames, with
baseline occurrences B_k and candidate occurrences C_k:
  - |B_k| != |C_k|: every b in B_k is MULTIPLICITY; its counterparts are all of
    C_k (correspondence resolved: same span, same claim). All of C_k are
    COUNTERPART_MULTIPLICITY.
  - |B_k| == |C_k|: occurrences are paired one to one, identical payload hashes
    first (both sides sorted by (payload_sha256, hit_id)), then the remaining
    ones in that sorted order. A pair with identical payloads is UNCHANGED;
    otherwise the baseline hit is DISPLAY_CONTEXT_CHANGED (context, marker or
    claimed-object display changed) and the candidate COUNTERPART_DISPLAY.
  Candidate hits used here are consumed.
Step 2, same span, different claim. A baseline hit left after step 1 whose
  exact span is also the span of one or more candidate hits whose claim key has
  no baseline occurrence is REASSIGNED; its counterparts are all those
  candidate hits (correspondence resolved: same occurrence, new claim). Those
  candidate hits are COUNTERPART_REASSIGNED and consumed.
Step 3, overlapping span. A baseline hit left after step 2 whose span overlaps
  (start_c < end_b and start_b < end_c) one or more candidate hits not consumed
  in steps 1-2 is SPAN_CHANGED; its counterparts are all those candidate hits
  (COUNTERPART_SPAN). Each counterpart LINK is resolved or not (audit r1 B4,
  frozen resolution rule): a link is resolved only if
    (a) baseline and counterpart have the same canonical marker or expression:
        metadiscourse, the same normalised marker string (raw "marker",
        casefolded, whitespace collapsed) AND the same category; PHRASE, the
        same rank; and
    (b) the candidate span contains the baseline hit's head token, or the
        baseline span contains the candidate hit's head token (worker
        `head_span`; a row without a head token never meets (b), since
        geometry alone never resolves);
  and, a declared conservative addition, the pairs meeting (a) and (b) are one
  to one (the baseline hit has exactly one such candidate and that candidate
  has exactly one such baseline hit). Geometric nesting alone never resolves.
  A reassignment that also changes the span (another category) is unresolved:
  the harness has no declared map of reassignment targets, so the stricter
  reading of the rule applies. A SPAN_CHANGED row with no resolved link is
  unresolved and takes worst-case loss.
Step 4. A baseline hit left after step 3 at whose exact span the candidate still
  emits another claim (a candidate hit of the same group consumed by its own key
  match in step 1) is CLAIM_DROPPED: the claim is dropped, but the occurrence has
  a same-occurrence counterpart, so it is NOT a genuine deletion (audit r2 B4).
  It has no emitted-claim counterpart; its same-span candidate hits are its
  `siblings` (below). Every other baseline hit left is REMOVED: no counterpart
  at the same occurrence at all (no retained claim at the same span, no
  resolved or unresolved span change, no reassignment). REMOVED is the
  protocol's genuine-deletion subset and the only population of the removal
  gate. Every candidate hit left is ADDED (a new output).

PRECEDENCE (mutually exclusive partition of baseline hits): the first step
that applies decides: key match (MULTIPLICITY, then UNCHANGED vs
DISPLAY_CONTEXT_CHANGED) > REASSIGNED > SPAN_CHANGED > CLAIM_DROPPED > REMOVED.
Each baseline emitted hit is one counting unit with exactly one type;
`check_partition` verifies this, that every UNCHANGED hit has an
identical-payload, same-key, equal-multiplicity counterpart (the zero-loss
match that keeps it outside the frame), that a REMOVED hit has no candidate hit
at its span and a CLAIM_DROPPED hit has one. Everything else is in the
affected-baseline frame, whose cells are REMOVED, REASSIGNED, SPAN_CHANGED,
MULTIPLICITY, DISPLAY_CONTEXT_CHANGED and CLAIM_DROPPED.

Conservative choices: candidate hits consumed by an exact key or same-span
match never serve as emitted-claim counterparts for another baseline hit (a
baseline hit can only become CLAIM_DROPPED or REMOVED, the directions that can
add loss, not hide it); a multiplicity change puts every occurrence of that key
in the frame; uncertain overlaps are unresolved.

TWO LAYERS (audit r1 B4, r2 B4; clarification file, item 1). The change types
above are the EMITTED-CLAIM DISPOSITION: one row per baseline emitted hit. The
removal gate uses the REMOVED cell only (genuine deletions); ruling A2, which
also counted a claim dropped at a retained span as a deletion, is withdrawn
(HARNESS_AUDIT_R2_DISPOSITIONS.md R2-B4): enlarging the deletion denominator
with such claims could dilute the registered success share among deletions.
Separately, OCCURRENCE-RETENTION LINKS serve loss accounting only: every
baseline row also lists `siblings`, the candidate hits with exactly its span in
the same group that are not already its counterparts, including siblings
consumed by another claim's key match in step 1. For LENIENT/LIST_LENIENT a
definitely successful sibling establishes retention of the occurrence (a
supported occurrence in the same target inventory); for STRICT only the row's
own counterparts count, so a correct CLAIM_DROPPED claim is a STRICT loss.
Siblings are same-occurrence links by construction (identical span), hence
resolved.

Output density (protocol "What these figures are called"): for BASELINE and
every configuration, complete hit counts and hits per 1,000 words by module,
category (metadiscourse) or K-band (PHRASE), and register. Words are counted
as build.py counts them for eligibility, i.e. whitespace-separated tokens of
the archived text. These describe output density, not recall.

Final-output frames (for the descriptive precision of new and changed
outputs): ADDED (candidate hits with no baseline link) and CHANGED (every
candidate hit linked as a counterpart: COUNTERPART_DISPLAY / _MULTIPLICITY /
_REASSIGNED / _SPAN).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from fixcheck.common import (
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    write_json,
    write_jsonl,
    write_step_manifest,
)
from fixcheck.ledger import BASELINE, COMPLETE, FAMILIES, MODULES

UNCHANGED = "UNCHANGED"
DISPLAY = "DISPLAY_CONTEXT_CHANGED"
MULTIPLICITY = "MULTIPLICITY"
REASSIGNED = "REASSIGNED"
SPAN_CHANGED = "SPAN_CHANGED"
REMOVED = "REMOVED"
CLAIM_DROPPED = "CLAIM_DROPPED"
CROSSWALK_VERSION = (
    "fixcheck-crosswalk/3 (audit r1 B4: per-link resolution, span rule, siblings; "
    "audit r2 B4: CLAIM_DROPPED is not a genuine deletion)"
)
AFFECTED_CELLS = (REMOVED, REASSIGNED, SPAN_CHANGED, MULTIPLICITY, DISPLAY, CLAIM_DROPPED)
BASE_TYPES = (UNCHANGED, *AFFECTED_CELLS)
C_UNCHANGED = "UNCHANGED"
C_DISPLAY = "COUNTERPART_DISPLAY"
C_MULT = "COUNTERPART_MULTIPLICITY"
C_REASSIGNED = "COUNTERPART_REASSIGNED"
C_SPAN = "COUNTERPART_SPAN"
ADDED = "ADDED"
CAND_TYPES = (C_UNCHANGED, C_DISPLAY, C_MULT, C_REASSIGNED, C_SPAN, ADDED)
FINAL_FRAMES = ("ADDED", "CHANGED")
CHANGED_CAND_TYPES = (C_DISPLAY, C_MULT, C_REASSIGNED, C_SPAN)


def _group(r: dict[str, Any]) -> tuple[str, str, str]:
    return (r["source_id"], r["text_sha256"], r["module"])


def _sort_key(r: dict[str, Any]) -> tuple[str, str]:
    return (r["payload_sha256"], r["hit_id"])


def _overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _nested(a: list[int], b: list[int]) -> bool:
    return (a[0] <= b[0] and b[1] <= a[1]) or (b[0] <= a[0] and a[1] <= b[1])


def _norm_marker(r: dict[str, Any]) -> str:
    m = (r.get("raw") or {}).get("marker") or r.get("surface") or r["payload"]["marker"]
    return " ".join(str(m).casefold().split())


def _contains(span: list[int], point: list[int] | None) -> bool:
    return point is not None and span[0] <= point[0] and point[1] <= span[1]


def span_rule_holds(b: dict[str, Any], c: dict[str, Any]) -> bool:
    """The frozen span-change resolution rule (B4), without the one-to-one condition."""
    if b["module"] == "metadiscourse":
        same = _norm_marker(b) == _norm_marker(c) and b["claim"] == c["claim"]
    else:
        same = b["claim"].get("rank") == c["claim"].get("rank")
    if not same:
        return False
    hb, hc = b.get("head_span"), c.get("head_span")
    if hb is None or hc is None:  # no head token: geometry alone never resolves
        return False
    return _contains(c["span"], hb) or _contains(b["span"], hc)


def crosswalk(
    base: list[dict[str, Any]], cand: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Baseline and candidate hit rows -> (baseline links, candidate links), keyed by hit_id.

    Baseline link: {change_type, counterparts (sorted hit ids), resolved (row: True/False/None),
    links [{hit, resolved}] (per counterpart), siblings (same-span candidate ids, loss layer)}.
    Candidate link: {change_type, linked_baseline (sorted hit ids)}.
    """
    for rows, side in ((base, "baseline"), (cand, "candidate")):
        ids = [r["hit_id"] for r in rows]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate hit ids in the {side} frame")
    groups: dict[tuple, tuple[list, list]] = defaultdict(lambda: ([], []))
    for r in base:
        groups[_group(r)][0].append(r)
    for r in cand:
        groups[_group(r)][1].append(r)
    bl: dict[str, dict[str, Any]] = {}
    cl: dict[str, dict[str, Any]] = {}
    for g in sorted(groups):
        b_rows, c_rows = groups[g]
        _crosswalk_group(b_rows, c_rows, bl, cl)
    return bl, cl


def _crosswalk_group(b_rows, c_rows, bl, cl) -> None:
    b_by_key: dict[str, list] = defaultdict(list)
    c_by_key: dict[str, list] = defaultdict(list)
    for r in b_rows:
        b_by_key[r["claim_key"]].append(r)
    for r in c_rows:
        c_by_key[r["claim_key"]].append(r)
    pending_b: list[dict[str, Any]] = []
    free_c: list[dict[str, Any]] = []  # candidate hits whose key has no baseline occurrence
    # Step 1: same claim key.
    for k in sorted(set(b_by_key) | set(c_by_key)):
        bs = sorted(b_by_key.get(k, []), key=_sort_key)
        cs = sorted(c_by_key.get(k, []), key=_sort_key)
        if bs and cs:
            if len(bs) != len(cs):
                ids = sorted(c["hit_id"] for c in cs)
                for b in bs:
                    bl[b["hit_id"]] = {
                        "change_type": MULTIPLICITY,
                        "counterparts": ids,
                        "resolved": True,
                        "links": [{"hit": i, "resolved": True} for i in ids],
                    }
                for c in cs:
                    cl[c["hit_id"]] = {
                        "change_type": C_MULT,
                        "linked_baseline": sorted(b["hit_id"] for b in bs),
                    }
                continue
            pairs = []
            b_left, c_left = list(bs), list(cs)
            for b in list(b_left):
                same = next((c for c in c_left if c["payload_sha256"] == b["payload_sha256"]), None)
                if same is not None:
                    pairs.append((b, same))
                    b_left.remove(b)
                    c_left.remove(same)
            pairs += list(zip(b_left, c_left, strict=True))
            for b, c in pairs:
                same = b["payload_sha256"] == c["payload_sha256"]
                bl[b["hit_id"]] = {
                    "change_type": UNCHANGED if same else DISPLAY,
                    "counterparts": [c["hit_id"]],
                    "resolved": True,
                    "links": [{"hit": c["hit_id"], "resolved": True}],
                }
                cl[c["hit_id"]] = {
                    "change_type": C_UNCHANGED if same else C_DISPLAY,
                    "linked_baseline": [b["hit_id"]],
                }
        elif bs:
            pending_b += bs
        else:
            free_c += cs
    pending_b.sort(key=lambda r: (r["span"][0], r["span"][1], r["hit_id"]))
    free_c.sort(key=lambda r: (r["span"][0], r["span"][1], r["hit_id"]))
    # Step 2: same span, different claim.
    c_by_span: dict[tuple[int, int], list] = defaultdict(list)
    for c in free_c:
        c_by_span[tuple(c["span"])].append(c)
    step2_links: dict[str, set[str]] = defaultdict(set)
    after2: list[dict[str, Any]] = []
    for b in pending_b:
        same_span = c_by_span.get(tuple(b["span"]), [])
        if same_span:
            ids = sorted(c["hit_id"] for c in same_span)
            bl[b["hit_id"]] = {
                "change_type": REASSIGNED,
                "counterparts": ids,
                "resolved": True,
                "links": [{"hit": i, "resolved": True} for i in ids],
            }
            for c in same_span:
                step2_links[c["hit_id"]].add(b["hit_id"])
        else:
            after2.append(b)
    for cid, bids in step2_links.items():
        cl[cid] = {"change_type": C_REASSIGNED, "linked_baseline": sorted(bids)}
    avail = [c for c in free_c if c["hit_id"] not in step2_links]
    # Step 3: overlapping span.
    ov_b: dict[str, list] = {
        b["hit_id"]: [c for c in avail if _overlap(b["span"], c["span"])] for b in after2
    }
    ov_c: dict[str, list] = defaultdict(list)
    for b in after2:
        for c in ov_b[b["hit_id"]]:
            ov_c[c["hit_id"]].append(b)
    rule_b: dict[str, set[str]] = defaultdict(set)
    rule_c: dict[str, set[str]] = defaultdict(set)
    for b in after2:
        for c in ov_b[b["hit_id"]]:
            if span_rule_holds(b, c):
                rule_b[b["hit_id"]].add(c["hit_id"])
                rule_c[c["hit_id"]].add(b["hit_id"])
    c_spans = {tuple(c["span"]) for c in c_rows}
    for b in after2:
        cs = ov_b[b["hit_id"]]
        if not cs:
            # Step 4: a claim dropped at a retained span, or a genuine deletion.
            bl[b["hit_id"]] = {
                "change_type": CLAIM_DROPPED if tuple(b["span"]) in c_spans else REMOVED,
                "counterparts": [],
                "resolved": None,
                "links": [],
            }
            continue
        links = [
            {
                "hit": c["hit_id"],
                "resolved": c["hit_id"] in rule_b[b["hit_id"]]
                and len(rule_b[b["hit_id"]]) == 1
                and len(rule_c[c["hit_id"]]) == 1,
            }
            for c in sorted(cs, key=lambda r: r["hit_id"])
        ]
        bl[b["hit_id"]] = {
            "change_type": SPAN_CHANGED,
            "counterparts": [lk["hit"] for lk in links],
            "resolved": any(lk["resolved"] for lk in links),
            "links": links,
        }
    for c in avail:
        linked = ov_c.get(c["hit_id"], [])
        cl[c["hit_id"]] = (
            {"change_type": C_SPAN, "linked_baseline": sorted(b["hit_id"] for b in linked)}
            if linked
            else {"change_type": ADDED, "linked_baseline": []}
        )
    # Occurrence-retention siblings (loss layer only): same span, not a counterpart.
    c_at: dict[tuple[int, int], list[str]] = defaultdict(list)
    for c in c_rows:
        c_at[tuple(c["span"])].append(c["hit_id"])
    for b in b_rows:
        link = bl[b["hit_id"]]
        cps = set(link["counterparts"])
        link["siblings"] = sorted(h for h in c_at.get(tuple(b["span"]), []) if h not in cps)


def check_partition(
    base: list[dict[str, Any]],
    cand: list[dict[str, Any]],
    bl: dict[str, dict[str, Any]],
    cl: dict[str, dict[str, Any]],
) -> list[str]:
    """Independent checks of the crosswalk output; returns problems (empty = valid)."""
    problems = []
    bid = {r["hit_id"]: r for r in base}
    cid = {r["hit_id"]: r for r in cand}
    if set(bl) != set(bid):
        problems.append("baseline hits and baseline links differ")
    if set(cl) != set(cid):
        problems.append("candidate hits and candidate links differ")
    from collections import Counter

    bk = Counter(r["claim_key"] for r in base)
    ck = Counter(r["claim_key"] for r in cand)
    for h, link in bl.items():
        t = link["change_type"]
        if t not in BASE_TYPES:
            problems.append(f"{h}: unknown type {t}")
            continue
        cps = link["counterparts"]
        if any(c not in cid for c in cps):
            problems.append(f"{h}: counterpart not in the candidate frame")
        if t == UNCHANGED:
            b = bid[h]
            if len(cps) != 1:
                problems.append(f"{h}: UNCHANGED without exactly one counterpart")
                continue
            c = cid[cps[0]]
            if (
                c["payload_sha256"] != b["payload_sha256"]
                or c["claim_key"] != b["claim_key"]
                or bk[b["claim_key"]] != ck[b["claim_key"]]
            ):
                problems.append(
                    f"{h}: UNCHANGED without an identical-payload equal-multiplicity match"
                )
        if t in (REMOVED, CLAIM_DROPPED) and cps:
            problems.append(f"{h}: {t} with counterparts")
        if t == REMOVED and link.get("siblings"):
            problems.append(f"{h}: REMOVED although the candidate keeps a claim at its span")
        if t == CLAIM_DROPPED and not link.get("siblings"):
            problems.append(f"{h}: CLAIM_DROPPED without a same-span candidate hit")
        if t not in (REMOVED, CLAIM_DROPPED) and not cps:
            problems.append(f"{h}: {t} without counterparts")
        if t not in (SPAN_CHANGED, REMOVED, CLAIM_DROPPED) and link["resolved"] is not True:
            problems.append(f"{h}: {t} must be resolved")
        lks = link.get("links", [])
        if [lk["hit"] for lk in lks] != list(cps):
            problems.append(f"{h}: links differ from counterparts")
        if t != SPAN_CHANGED and any(lk["resolved"] is not True for lk in lks):
            problems.append(f"{h}: {t} has an unresolved link")
        if t == SPAN_CHANGED and link["resolved"] != any(lk["resolved"] for lk in lks):
            problems.append(f"{h}: row resolution is not 'some link resolved'")
        for sib in link.get("siblings", []):
            if sib in cps or sib not in cid or cid[sib]["span"] != bid[h]["span"]:
                problems.append(f"{h}: sibling {sib} is not a same-span non-counterpart")
    unchanged_c = Counter(
        link["counterparts"][0] for link in bl.values() if link["change_type"] == UNCHANGED
    )
    if any(v > 1 for v in unchanged_c.values()):
        problems.append("a candidate hit is the UNCHANGED match of two baseline hits")
    for h, link in cl.items():
        if link["change_type"] not in CAND_TYPES:
            problems.append(f"{h}: unknown candidate type")
        if link["change_type"] == ADDED and link["linked_baseline"]:
            problems.append(f"{h}: ADDED with a baseline link")
        if link["change_type"] != ADDED and not link["linked_baseline"]:
            problems.append(f"{h}: linked type without baseline link")
    return problems


def frames_for(
    base: list[dict[str, Any]],
    cand: list[dict[str, Any]],
    bl: dict[str, dict[str, Any]],
    cl: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Per module: affected cells (baseline hit ids), final frames (candidate hit ids), sizes."""
    out: dict[str, Any] = {}
    for m in MODULES:
        cells = {
            t: sorted(
                r["hit_id"]
                for r in base
                if r["module"] == m and bl[r["hit_id"]]["change_type"] == t
            )
            for t in AFFECTED_CELLS
        }
        final = {
            "ADDED": sorted(
                r["hit_id"]
                for r in cand
                if r["module"] == m and cl[r["hit_id"]]["change_type"] == ADDED
            ),
            "CHANGED": sorted(
                r["hit_id"]
                for r in cand
                if r["module"] == m and cl[r["hit_id"]]["change_type"] in CHANGED_CAND_TYPES
            ),
        }
        unresolved = sum(1 for h in cells[SPAN_CHANGED] if bl[h]["resolved"] is False)
        span_links = [lk for h in cells[SPAN_CHANGED] for lk in bl[h].get("links", [])]
        with_sibling = {t: sum(1 for h in v if bl[h].get("siblings")) for t, v in cells.items()}
        cand_spans = {
            (r["source_id"], r["text_sha256"], tuple(r["span"])) for r in cand if r["module"] == m
        }
        bid = {r["hit_id"]: r for r in base if r["module"] == m}
        removed_same_span = sum(
            (bid[h]["source_id"], bid[h]["text_sha256"], tuple(bid[h]["span"])) in cand_spans
            for h in cells[REMOVED]
        )
        if removed_same_span:
            raise AssertionError("a REMOVED hit has a candidate hit at its span")
        out[m] = {
            "N_baseline": sum(r["module"] == m for r in base),
            "N_candidate": sum(r["module"] == m for r in cand),
            "N_unchanged": sum(
                r["module"] == m and bl[r["hit_id"]]["change_type"] == UNCHANGED for r in base
            ),
            "affected_cells": cells,
            "affected_sizes": {t: len(v) for t, v in cells.items()},
            "N_affected": sum(len(v) for v in cells.values()),
            "N_genuine_deletion": len(cells[REMOVED]),
            "N_claim_dropped_at_retained_span": len(cells[CLAIM_DROPPED]),
            "span_changed_unresolved": unresolved,
            "span_changed_links": len(span_links),
            "span_changed_links_resolved": sum(lk["resolved"] for lk in span_links),
            "rows_with_same_span_sibling": with_sibling,
            "removed_with_same_span_candidate_hit": removed_same_span,
            "final_frames": final,
            "final_sizes": {k: len(v) for k, v in final.items()},
        }
    return out


def overlaps(frames: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Overlap of affected and deletion frames between configurations, per module."""
    out: dict[str, Any] = {}
    for m in MODULES:
        aff = {
            c: {h for v in f[m]["affected_cells"].values() for h in v} for c, f in frames.items()
        }
        dele = {c: set(f[m]["affected_cells"][REMOVED]) for c, f in frames.items()}
        fams = [c for c in frames if c != COMPLETE]
        union_aff = set().union(*(aff[c] for c in fams)) if fams else set()
        out[m] = {
            "family_vs_complete_affected": {
                c: {"family": len(aff[c]), "both": len(aff[c] & aff.get(COMPLETE, set()))}
                for c in fams
            },
            "family_vs_complete_deletion": {
                c: {"family": len(dele[c]), "both": len(dele[c] & dele.get(COMPLETE, set()))}
                for c in fams
            },
            "pairwise_family_affected": {
                f"{a}&{b}": len(aff[a] & aff[b])
                for a, b in combinations(fams, 2)
                if aff[a] & aff[b]
            },
            "union_of_families_affected": len(union_aff),
            "complete_affected": len(aff.get(COMPLETE, set())),
            "complete_minus_union": len(aff.get(COMPLETE, set()) - union_aff),
            "union_minus_complete": len(union_aff - aff.get(COMPLETE, set())),
        }
    return out


def density(
    rows_by_config: dict[str, list[dict[str, Any]]], texts: list[dict[str, Any]], words: dict
) -> dict[str, Any]:
    """Hit counts and hits per 1,000 words by config, module, register and category/band."""
    reg_words: dict[str, int] = defaultdict(int)
    for t in texts:
        reg_words[t["register"]] += words[t["text_id"]]
    reg_words["all"] = sum(words.values())
    out: dict[str, Any] = {"words": dict(sorted(reg_words.items())), "configs": {}}
    for c, rows in rows_by_config.items():
        tab: dict[str, Any] = {}
        for m in MODULES:
            cnt: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for r in rows:
                if r["module"] != m:
                    continue
                g = r["claim"]["category"] if m == "metadiscourse" else f"K{r['raw']['k_band']}"
                for reg in (r["register"], "all"):
                    cnt[reg][g] += 1
                    cnt[reg]["all"] += 1
            tab[m] = {
                reg: {
                    g: {"hits": n, "per_1000_words": round(1000 * n / reg_words[reg], 3)}
                    for g, n in sorted(gs.items())
                }
                for reg, gs in sorted(cnt.items())
            }
        out["configs"][c] = tab
    return out


def main(argv: list[str]) -> int:
    set_command("diff", argv)
    ap = argparse.ArgumentParser(prog="fixcheck diff", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    run_dir, out = args.run_dir.resolve(), args.out.resolve()
    refuse_existing(out / "frames.json", args.overwrite)
    run = read_json(run_dir / "run.json")
    base = read_jsonl(run_dir / "frames" / f"{BASELINE}.hits.jsonl")
    configs = [c for c in (COMPLETE, *FAMILIES) if c in run["configs"]]
    frames: dict[str, Any] = {}
    files = []
    problems_all = {}
    rd = Path(run["round_dir"]) if run.get("round_dir") else None
    texts = read_jsonl(rd / "texts.jsonl") if rd and (rd / "texts.jsonl").exists() else None
    dens_rows: dict[str, list[dict[str, Any]]] = {BASELINE: base}
    for c in configs:
        cand = read_jsonl(run_dir / "frames" / f"{c}.hits.jsonl")
        if texts is not None:
            dens_rows[c] = [{k: r[k] for k in ("module", "register", "claim", "raw")} for r in cand]
        bl, cl = crosswalk(base, cand)
        problems = check_partition(base, cand, bl, cl)
        problems_all[c] = problems
        frames[c] = frames_for(base, cand, bl, cl)
        p1, p2 = out / "links" / f"{c}.baseline.jsonl", out / "links" / f"{c}.candidate.jsonl"
        write_jsonl(p1, [{"hit_id": h, **bl[h]} for h in sorted(bl)])
        write_jsonl(p2, [{"hit_id": h, **cl[h]} for h in sorted(cl)])
        files += [p1, p2]
    if any(problems_all.values()):
        raise SystemExit(
            f"crosswalk check failed: { {c: p[:5] for c, p in problems_all.items() if p} }"
        )
    dens = None
    if texts is not None:
        words = {
            t["text_id"]: len((rd / "texts" / f"{t['text_id']}.txt").read_text("utf-8").split())
            for t in texts
        }
        dens = density(dens_rows, texts, words)
    rec = {
        "crosswalk_version": CROSSWALK_VERSION,
        "baseline": BASELINE,
        "density": dens,
        "run_json_sha256": sha256_file(run_dir / "run.json"),
        "baseline_hits_sha256": sha256_file(run_dir / "frames" / f"{BASELINE}.hits.jsonl"),
        "candidate_hits_sha256": {
            c: sha256_file(run_dir / "frames" / f"{c}.hits.jsonl") for c in configs
        },
        "configs": configs,
        "frames": frames,
        "overlaps": overlaps(frames),
        "partition_checks": {c: "ok" for c in configs},
        "labels_used": False,
        "cross_module_effects": {
            c: [
                m
                for m in MODULES
                if frames[c][m]["N_affected"] or frames[c][m]["final_sizes"]["ADDED"]
            ]
            for c in configs
        },
    }
    write_json(out / "frames.json", rec)
    files.append(out / "frames.json")
    write_step_manifest(out, "diff", files)
    for c in configs:
        print(c, {m: frames[c][m]["affected_sizes"] | frames[c][m]["final_sizes"] for m in MODULES})
    return 0
