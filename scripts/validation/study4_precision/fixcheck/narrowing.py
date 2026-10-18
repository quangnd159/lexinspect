"""The round-2 narrowing check (gap G10; round-2 harness audit r1, findings 1 and 3).

G10 is a development-text conformance check, not held-out validation or proof of
equivalence on all possible texts. Production planning requires its authenticated result
for the exact frozen candidate, round-1 comparison candidate, final ledger, harness and
reviewed kept/reverted lists. The separate source audit establishes that no new rule or
condition was introduced, including under an existing family identity. The six kept
families are unchanged; the six specified reverted families are inactive. COMPLETE and
interactions are evaluated afresh in round 2.

The evidence. `dryrun --commit <CAND2> --compare-candidate <round-1 commit> --kept <the
kept families>` runs, on the 120 development texts, both candidates' BASELINE, each kept
family alone and every combination of two or more kept families (all 2^6 = 64 subsets of
the six kept switches, the empty one being BASELINE), and the new candidate's every family
alone and COMPLETE. After authenticating every input (dryrun.kept_family_identity: both
run manifests, the snapshots against their commits, worker metadata against the actual
rows, one development text manifest) it writes <dry-run dir>/NARROWING_CHECK.json: counts
and hashes only, never a hit, a context or a PHRASE list entry. That file, copied byte for
byte to docs/validation/study4-fix040/round2/NARROWING_CHECK.json and named by its SHA-256
in the narrowing disposition, is the round-2 plan's `--narrowing-check`.

`problems` validates it against the round being planned: the exact kept and reverted lists
of the authorized disposition (KEPT, REVERTED), the candidate commit and tree, round 1's
registered candidate commit and tree as the comparison, the ledger Markdown's SHA-256, the
harness source hashes, the canonical development manifest, every per-family and per-subset
result and boolean, and `ok`. A bare `ok` is never enough. The nested result
(kept_family_identity) must name the same candidate and comparison commits and trees as the
document and as the round being planned, and the development round's texts.jsonl SHA-256
that dev_round_texts_sha256 recomputes from the development manifest used (audit r2 N1).
Every boolean of the result must also agree with the counts recorded beside it. collect calls
it before the reservation (freeze.production_prerequisites refuses on any problem) and again
when the execution rebuilds the record; package.check_collect calls it at acceptance, where a
problem is a chain problem: accept.compute then makes the status inconclusive, never pass
or fail, whatever the labels give (audit r2 N2; harness ruling A1; RUNBOOK section 8).

What it does not establish. Every result is observed on these 120 development texts only:
byte-equal frames of BASELINE, of each kept family and of each of the 57 combinations of two
or more kept families; each reverted family alone identical to BASELINE; and COMPLETE (all
twelve switches) identical to the six kept families together. Other combinations that
include a reverted family (with fewer than all six kept families, or with reverted families
only) are not run.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

from fixcheck.common import canonical_json, read_json, read_jsonl, sha256_text
from fixcheck.ledger import FAMILIES, MODULES

KIND = "fixcheck-narrowing-check"
VERSION = 1
FILENAME = "NARROWING_CHECK.json"
# The authorized round-2 narrowing disposition (the maintainer's, after the round-1 non-pass;
# .cache/validation/study4_fix040/round2/ROUND2_PLAN.md): kept and reverted families.
KEPT = ("MD-D", "MD-H", "MD-I", "PH-A", "PH-B", "PH-C")
REVERTED = ("MD-A", "MD-B", "MD-C", "MD-E", "MD-F", "MD-G")
SUBSET_PREFIX = "KEPT+"
DRYRUN_CHECKS = (
    "verify_ok",
    "ledger_ok",
    "blinding_ok",
    "verify_baseline_identical",
    "determinism_identical",
    "ledger_md_is_keyed",
)


def subset_config(families: list[str] | tuple[str, ...]) -> str:
    """The configuration name of a combination of kept families (worker --config)."""
    return SUBSET_PREFIX + "+".join(families)


def kept_subsets(kept: list[str] | tuple[str, ...]) -> dict[str, list[str]]:
    """Every combination of two or more kept families (the empty one is BASELINE and the
    singletons are the families alone), in family order: name -> families."""
    order = [f for f in FAMILIES if f in kept]
    return {
        subset_config(c): list(c) for r in range(2, len(order) + 1) for c in combinations(order, r)
    }


def dev_round_texts(dev_texts: Path) -> tuple[str, dict[str, str]]:
    """The development round's texts.jsonl (dryrun.dev_round_dir) and its texts, from the
    development manifest `dev_texts` and the text files beside it (<dir>/texts/<id>.txt):
    each manifest row with its text's SHA-256, one sorted-key JSON line per row."""
    rows, texts = [], {}
    for t in read_jsonl(Path(dev_texts)):
        text = (Path(dev_texts).parent / "texts" / f"{t['text_id']}.txt").read_text(
            encoding="utf-8"
        )
        texts[t["text_id"]] = text
        rows.append(t | {"text_sha256": sha256_text(text)})
    jsonl = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    return jsonl, texts


def dev_round_texts_sha256(dev_texts: Path | None) -> str | None:
    """The SHA-256 of the development round's texts.jsonl that `dev_texts` gives (None if the
    manifest or a text is missing or unreadable): the nested texts_jsonl_sha256 of a narrowing
    check run on that manifest."""
    if dev_texts is None or not Path(dev_texts).is_file():
        return None
    try:
        return sha256_text(dev_round_texts(Path(dev_texts))[0])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def harness_sha256(sources_sha256: dict[str, str]) -> str:
    """The harness identity of a dry run's key (dryrun.snapshot_and_key)."""
    return sha256_text(canonical_json(sources_sha256))


def _same_frame(name: str, v: Any) -> list[str]:
    if not isinstance(v, dict):
        return [f"{name}: no result"]
    a, b = v.get("candidate_sha256"), v.get("compare_sha256")
    if not a or a != b or v.get("byte_equal") is not True:
        return [f"{name}: the two candidates' development-text frames are not byte-equal"]
    return []


def problems(
    ev: Any,
    *,
    candidate: dict[str, Any],
    round1_candidate: dict[str, Any],
    ledger_md_sha256: str | None,
    sources_sha256: dict[str, str] | None,
    dev_texts_sha256: str | None,
    dev_round_texts_sha256: str | None,
) -> list[str]:
    """Why `ev` is not the narrowing check of this round 2 (empty: it is). Explicit
    refusal reasons, never assertions; every identity (outer and nested), list, per-family
    and per-subset result and boolean is checked, not only `ok`, and no boolean may contradict
    the counts recorded beside it. `dev_round_texts_sha256` is dev_round_texts_sha256 of the
    development manifest whose SHA-256 is `dev_texts_sha256`."""
    if not isinstance(ev, dict):
        return ["the narrowing check is not a JSON object"]
    p: list[str] = []
    if ev.get("kind") != KIND or ev.get("version") != VERSION:
        p.append(f"the narrowing check is not a {KIND} version {VERSION} document")
    pairs = (
        ("candidate_commit", candidate.get("commit"), "the round-2 candidate commit"),
        ("candidate_tree_sha256", candidate.get("tree_sha256"), "the round-2 candidate tree"),
        ("compare_commit", round1_candidate.get("commit"), "round 1's candidate commit"),
        ("compare_tree_sha256", round1_candidate.get("tree_sha256"), "round 1's candidate tree"),
        ("ledger_md_sha256", ledger_md_sha256, "the bound ledger Markdown's SHA-256"),
        ("dev_texts_jsonl_sha256", dev_texts_sha256, "the canonical development manifest"),
    )
    for key, want, what in pairs:
        if not want or ev.get(key) != want:
            p.append(f"the narrowing check's {key} {ev.get(key)!r} is not {what} ({want!r})")
    want_h = harness_sha256(sources_sha256) if sources_sha256 else None
    if not want_h or ev.get("harness_sha256") != want_h:
        p.append("the narrowing check was not produced by this harness (harness_sha256 differs)")
    if ev.get("kept") != list(KEPT):
        p.append(f"the narrowing check's kept families {ev.get('kept')} are not {list(KEPT)}")
    if ev.get("not_kept") != list(REVERTED):
        p.append(
            f"the narrowing check's reverted families {ev.get('not_kept')} are not {list(REVERTED)}"
        )
    checks = (ev.get("dryrun") or {}).get("checks") or {}
    bad = [k for k in DRYRUN_CHECKS if checks.get(k) is not True]
    if bad:
        p.append(f"the narrowing check's dry run did not pass {bad}")
    k = ev.get("kept_family_identity")
    if not isinstance(k, dict):
        return [*p, "the narrowing check has no kept_family_identity"]
    if k.get("kept") != list(KEPT) or k.get("not_kept") != list(REVERTED):
        p.append("kept_family_identity names other kept or reverted families")
    # audit r2 N1: the nested result is of the same comparison as the document and the round
    nested = (
        ("candidate_commit", candidate.get("commit")),
        ("candidate_tree_sha256", candidate.get("tree_sha256")),
        ("compare_commit", round1_candidate.get("commit")),
        ("compare_tree_sha256", round1_candidate.get("tree_sha256")),
    )
    for key, want in nested:
        if not k.get(key) or k.get(key) != ev.get(key) or k.get(key) != want:
            p.append(
                f"kept_family_identity's {key} {k.get(key)!r} is not the narrowing check's "
                f"({ev.get(key)!r}) and the expected one ({want!r})"
            )
    if not dev_round_texts_sha256 or k.get("texts_jsonl_sha256") != dev_round_texts_sha256:
        p.append(
            f"kept_family_identity's texts_jsonl_sha256 {k.get('texts_jsonl_sha256')!r} is not "
            f"the development round of the development manifest ({dev_round_texts_sha256!r})"
        )
    p += _same_frame("BASELINE", k.get("baseline"))
    kf = k.get("kept_frames") or {}
    if sorted(kf) != sorted(KEPT):
        p.append(f"kept_family_identity covers the kept families {sorted(kf)}, not {list(KEPT)}")
    for f in KEPT:
        p += _same_frame(f, kf.get(f))
    ks = k.get("kept_subsets") or {}
    want_s = kept_subsets(KEPT)
    if sorted(ks) != sorted(want_s):
        p.append(
            f"kept_family_identity covers {len(ks)} kept-family combinations, not the "
            f"{len(want_s)} of two or more"
        )
    for name, fams in want_s.items():
        v = ks.get(name)
        if isinstance(v, dict) and v.get("families") != fams:
            p.append(f"{name}: names the families {v.get('families')}, not {fams}")
        p += _same_frame(name, v)
    base_hits = (k.get("baseline") or {}).get("n_hits") or {}
    nk = k.get("not_kept_frames") or {}
    if sorted(nk) != sorted(REVERTED):
        p.append(f"kept_family_identity covers the reverted families {sorted(nk)}")
    for f in REVERTED:
        v = nk.get(f) or {}
        mods = v.get("modules") or {}
        rows = v.get("rows") or {}
        for m in MODULES:
            c = mods.get(m) or {}
            r = rows.get(m) or {}
            counts = (c.get("N_affected"), c.get("N_candidate"), c.get("N_baseline"))
            if c.get("N_affected") != 0 or c.get("N_candidate") != c.get("N_baseline"):
                p.append(f"{f} {m}: not inactive (N_affected, N_candidate, N_baseline {counts})")
            elif (r.get("candidate"), r.get("baseline")) != (c["N_candidate"], c["N_baseline"]):
                p.append(f"{f} {m}: the frame counts are not the rows' counts")
            if r.get("baseline") != base_hits.get(m):
                p.append(f"{f} {m}: the baseline row count is not BASELINE's ({base_hits.get(m)})")
        if v.get("zero_affected") is not True or v.get("identical_to_baseline") is not True:
            p.append(f"{f}: not identical to BASELINE alone")
        if v.get("counts_match_rows") is not True:
            p.append(f"{f}: counts_match_rows is not true (contradicts the counts recorded)")
    ce = k.get("complete_equals_kept_union") or {}
    if ce.get("identical") is not True:
        p.append("COMPLETE is not the six kept families together (a reverted family is active)")
    union = (ks.get(subset_config(KEPT)) or {}).get("n_hits") or {}
    n_union = sum(union.values()) if all(isinstance(x, int) for x in union.values()) else None
    if not isinstance(ce.get("n_complete"), int) or not (
        ce.get("n_complete") == ce.get("n_kept_union") == n_union
    ):
        p.append(
            "complete_equals_kept_union: the COMPLETE and kept-union hit counts "
            f"({ce.get('n_complete')}, {ce.get('n_kept_union')}) are not equal to each other and "
            f"to the six-kept combination's ({n_union})"
        )
    if k.get("ok") is not True:
        p.append("kept_family_identity.ok is not true")
    if ev.get("ok") is not True:
        p.append("the narrowing check's ok is not true")
    return p


def file_problems(path: Path | None, **want: Any) -> list[str]:
    """`problems` of the file at `path` (missing or unreadable: a problem)."""
    if path is None:
        return ["no narrowing check (--narrowing-check)"]
    path = Path(path)
    if not path.is_file():
        return [f"the narrowing check {path} is missing"]
    try:
        ev = read_json(path)
    except (OSError, ValueError) as e:
        return [f"the narrowing check {path} is not readable JSON ({type(e).__name__})"]
    return problems(ev, **want)
