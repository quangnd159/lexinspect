"""Study 4: development and fix-check effects of the 0.3.2 -> 0.3.3 -> 0.4.0 changes.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/effects.py [--check]

Writes docs/validation/study4-development-effects.json and
docs/validation/study4-development-effects.md. Nothing is rerun: every count
comes from archived detector output.

- Development texts (120, 40 per register, byte-identical across builds):
  0.3.2 from .cache/validation/study4/hits.jsonl (the original build);
  0.3.3 from the fix-check harness dry run's BASELINE frame, which ran the
  pinned dec79bc checkout (.cache/validation/study4_fix040/harness_dryrun/),
  cross-checked against the separate 0.3.3 rebuild hits_033.jsonl and the
  BASELINE_PINNED frame; 0.4.0 from .cache/validation/study4_v040/hits.jsonl.
- Fix-check rounds (60 new texts each): BASELINE (0.3.3), COMPLETE and every
  single-family frame from the private run/frames/*.hits.jsonl. The density
  tables are recomputed here and must equal the ones archived in the private
  diff/frames.json; those files' SHA-256s must appear in the public receipts.
- Gate results, losses, unresolved references and the added/changed
  diagnostics are copied from the public acceptance.json files, not recomputed.

Words are whitespace-separated tokens of the archived text (len(text.split())),
the rule build.py uses for eligibility and fixcheck/crosswalk.py uses for
density. Hit densities are hits per 1,000 such words. The output holds counts,
category names, K-bands and identifiers only: no text, gloss or guideline.
--check rebuilds both files in memory and exits 1 if either differs on disk.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = Path("/Users/quangnguyendang/lexinspect-private/study4-fix040")
CACHE = ROOT / ".cache" / "validation"
DEV = CACHE / "study4"
DEV040 = CACHE / "study4_v040"
DRY = CACHE / "study4_fix040" / "harness_dryrun"
FIX = ROOT / "docs" / "validation" / "study4-fix040"
OUT_JSON = ROOT / "docs" / "validation" / "study4-development-effects.json"
OUT_MD = ROOT / "docs" / "validation" / "study4-development-effects.md"

MODULES = ("metadiscourse", "phrase")
REGISTERS = ("academic", "argumentative", "general", "all")
MD_CATS = (
    "transitions",
    "frame_markers",
    "endophoric_markers",
    "evidentials",
    "code_glosses",
    "hedges",
    "boosters",
    "attitude_markers",
    "self_mentions",
    "engagement_markers",
)
BANDS = ("K1", "K2", "K3", "K4", "K5")
GROUPS = {"metadiscourse": (*MD_CATS, "all"), "phrase": (*BANDS, "all")}
FAMILIES = (
    "MD-A",
    "MD-B",
    "MD-C",
    "MD-D",
    "MD-E",
    "MD-F",
    "MD-G",
    "MD-H",
    "MD-I",
    "PH-A",
    "PH-B",
    "PH-C",
)
KEPT = ("MD-D", "MD-H", "MD-I", "PH-A", "PH-B", "PH-C")

RELEASES = {
    "0.3.2": {"tag": "v0.3.2", "commit": "4ef08025b959efd6972bb39694621b0d9da14366"},
    "0.3.3": {"tag": "v0.3.3", "commit": "dec79bc0e642035d2ec686997b284da2ceadd11c"},
    "0.4.0": {"tag": "v0.4.0", "commit": "0556d0826001112eb6a82d08883e3592d05010ea"},
}
CANDIDATES = {
    "round1": {
        "commit": "3d4df7012656defd5a44571410af00896f634a2d",
        "src_tree_sha256": "51ed081b43a8895a6bcaef0e19998beb632e0cbc0acfc0bed2f50e68ecb7d58b",
    },
    "round2": {
        "commit": "16aa95ef10e0ec5fc8df9113e794c85d13c8aafc",
        "src_tree_sha256": "eb233ecaea8f2699123466f6f47e90694bfbc073f4b8209ef78bae12f200de31",
    },
}
DEV040_BUILD_COMMIT = "1c7dd36b4fd80be4713cb5b49238c636acccfec0"


# --- helpers --------------------------------------------------------------------


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    with p.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return "lexinspect-private/" + str(p.relative_to(PRIVATE.parent))


INPUTS: dict[str, str] = {}


def track(p: Path) -> Path:
    INPUTS[rel(p)] = sha256_file(p)
    return p


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def group_of(module: str, row: dict[str, Any]) -> str:
    """Category (metadiscourse) or K-band (phrase), for build rows or harness frame rows."""
    if module == "metadiscourse":
        return row["claim"]["category"] if "claim" in row else row["category"]
    band = row["raw"]["k_band"] if "raw" in row else row["k_band"]
    return f"K{band}"


def claim_of(module: str, row: dict[str, Any]) -> tuple:
    if module == "metadiscourse":
        return (group_of(module, row),)
    if "claim" in row:
        c = row["claim"]
        return (c["expression"], c["rank"], c["sense"])
    return (row["phrase"], row["rank"], row["sense"])


def table(rows: list[dict[str, Any]], register_of: dict[str, str], words: dict[str, int]) -> dict:
    """{module: {register: {group: {hits, per_1000_words}}}}, every cell present (zeros kept)."""
    cnt: dict[str, dict[str, Counter]] = {m: defaultdict(Counter) for m in MODULES}
    for r in rows:
        m = r["module"]
        g = group_of(m, r)
        if g not in GROUPS[m]:
            raise SystemExit(f"unexpected group {g!r} in {m}")
        for reg in (register_of[r["text_id"]], "all"):
            cnt[m][reg][g] += 1
            cnt[m][reg]["all"] += 1
    return {
        m: {
            reg: {
                g: {
                    "hits": cnt[m][reg][g],
                    "per_1000_words": round(1000 * cnt[m][reg][g] / words[reg], 3),
                }
                for g in GROUPS[m]
            }
            for reg in REGISTERS
        }
        for m in MODULES
    }


def effect(before: dict, after: dict, words: dict[str, int]) -> dict:
    out: dict[str, Any] = {}
    for m in MODULES:
        out[m] = {}
        for reg in REGISTERS:
            out[m][reg] = {}
            for g in GROUPS[m]:
                b, a = before[m][reg][g]["hits"], after[m][reg][g]["hits"]
                out[m][reg][g] = {
                    "hits_before": b,
                    "hits_after": a,
                    "delta_hits": a - b,
                    "delta_per_1000_words": round(1000 * (a - b) / words[reg], 3),
                    "pct_change": None if b == 0 else round(100 * (a - b) / b, 1),
                }
    return out


def key_comparison(before: list[dict], after: list[dict]) -> dict:
    """Simple span-keyed comparison (not the fix-check crosswalk).

    Per (module, text, character span): claims present in both are unchanged;
    the rest at a span present in both releases are claim changes; spans present
    in only one release are removed or added. A shifted span counts as one
    removal plus one addition.
    """
    out = {}
    for m in MODULES:
        b: dict[tuple, Counter] = defaultdict(Counter)
        a: dict[tuple, Counter] = defaultdict(Counter)
        for r in before:
            if r["module"] == m:
                b[(r["text_id"], tuple(r["span"]))][claim_of(m, r)] += 1
        for r in after:
            if r["module"] == m:
                a[(r["text_id"], tuple(r["span"]))][claim_of(m, r)] += 1
        res = Counter(
            dict.fromkeys(
                (
                    "unchanged",
                    "claim_changed_before",
                    "claim_changed_after",
                    "span_removed",
                    "span_added",
                ),
                0,
            )
        )
        for k in b.keys() | a.keys():
            cb, ca = b.get(k, Counter()), a.get(k, Counter())
            same = sum((cb & ca).values())
            res["unchanged"] += same
            if k in b and k in a:
                res["claim_changed_before"] += sum(cb.values()) - same
                res["claim_changed_after"] += sum(ca.values()) - same
            elif k in b:
                res["span_removed"] += sum(cb.values())
            else:
                res["span_added"] += sum(ca.values())
        res["n_before"] = sum(sum(c.values()) for c in b.values())
        res["n_after"] = sum(sum(c.values()) for c in a.values())
        assert (
            res["n_before"] == res["unchanged"] + res["claim_changed_before"] + res["span_removed"]
        )
        assert res["n_after"] == res["unchanged"] + res["claim_changed_after"] + res["span_added"]
        out[m] = dict(sorted(res.items()))
    return out


def multiset(rows: list[dict]) -> Counter:
    return Counter(
        (r["module"], r["text_id"], tuple(r["span"]), claim_of(r["module"], r)) for r in rows
    )


# --- development texts ----------------------------------------------------------


def development() -> dict:
    texts = read_jsonl(track(DEV / "texts.jsonl"))
    register_of = {t["text_id"]: t["register"] for t in texts}
    words_by_text, same_bytes_040, same_bytes_dry = {}, 0, 0
    dry_texts = {t["text_id"]: t for t in read_jsonl(track(DRY / "round_dev" / "texts.jsonl"))}
    for t in texts:
        raw = (DEV / "texts" / f"{t['text_id']}.txt").read_bytes()
        words_by_text[t["text_id"]] = len(raw.decode("utf-8").split())
        same_bytes_040 += raw == (DEV040 / "texts" / f"{t['text_id']}.txt").read_bytes()
        same_bytes_dry += (
            raw == (DRY / "round_dev" / "texts" / f"{t['text_id']}.txt").read_bytes()
            and hashlib.sha256(raw).hexdigest() == dry_texts[t["text_id"]]["text_sha256"]
        )
    if same_bytes_040 != len(texts) or same_bytes_dry != len(texts):
        raise SystemExit("development text bytes differ between builds")
    words = defaultdict(int)
    for tid, n in words_by_text.items():
        words[register_of[tid]] += n
    words["all"] = sum(words_by_text.values())
    words = {r: words[r] for r in REGISTERS}

    h032 = read_jsonl(track(DEV / "hits.jsonl"))
    h033 = read_jsonl(track(DRY / "run" / "frames" / "BASELINE.hits.jsonl"))
    h033_pinned = read_jsonl(track(DRY / "run" / "frames" / "BASELINE_PINNED.hits.jsonl"))
    h033_rebuild = read_jsonl(track(CACHE / "study4_fix040" / "hits_033.jsonl"))
    h040 = read_jsonl(track(DEV040 / "hits.jsonl"))
    meta033 = json.loads(track(DRY / "run" / "frames" / "BASELINE.meta.json").read_text())
    pinned = json.loads(track(DRY / "run" / "pinned.json").read_text())
    man032 = json.loads(track(DEV / "manifest.json").read_text())
    man040 = json.loads(track(DEV040 / "manifest.json").read_text())
    narrowing = json.loads(track(FIX / "round2" / "NARROWING_CHECK.json").read_text())

    checks = {
        "text_bytes_identical_0.3.2_0.4.0_builds_and_dry_run": True,
        "0.3.3_frame_equals_pinned_frame": multiset(h033) == multiset(h033_pinned),
        "0.3.3_frame_equals_separate_0.3.3_rebuild": multiset(h033) == multiset(h033_rebuild),
        "0.3.3_frame_ran_pinned_checkout": {
            "pinned_commit": pinned["commit"],
            "lexinspect_version": meta033["lexinspect_version"],
            "families_enabled": meta033["enabled"],
            "lexinspect_file_in_pinned_checkout": "pinned_dec79bc" in meta033["lexinspect_file"],
        },
        "0.3.2_build_commit": man032["lexinspect_commit"],
        "0.4.0_build_commit": man040["lexinspect_commit"],
        "0.4.0_build_src_equals_v0.4.0_src": git(
            "diff", "--name-only", RELEASES["0.4.0"]["commit"], DEV040_BUILD_COMMIT, "--", "src"
        )
        == "",
        "0.4.0_build_dirty": man040["git"]["dirty"],
        "population_counts_match_manifests": {
            "0.3.2": [
                man032["population"]["metadiscourse_hits"],
                man032["population"]["phrase_hits"],
            ],
            "0.4.0": [
                man040["population"]["metadiscourse_hits"],
                man040["population"]["phrase_hits"],
            ],
        },
        "0.4.0_equals_narrowing_check_all_kept_families": None,
    }
    for rel_, rows, man in (("0.3.2", h032, man032), ("0.4.0", h040, man040)):
        c = Counter(r["module"] for r in rows)
        if [c["metadiscourse"], c["phrase"]] != [
            man["population"]["metadiscourse_hits"],
            man["population"]["phrase_hits"],
        ]:
            raise SystemExit(f"{rel_} hit counts differ from its manifest")
    if not (
        checks["0.3.3_frame_equals_pinned_frame"]
        and checks["0.3.3_frame_equals_separate_0.3.3_rebuild"]
        and checks["0.4.0_build_src_equals_v0.4.0_src"]
    ):
        raise SystemExit(f"development provenance check failed: {checks}")

    kfi = narrowing["kept_family_identity"]
    all_kept = kfi["kept_subsets"]["KEPT+" + "+".join(KEPT)]["n_hits"]
    c040 = Counter(r["module"] for r in h040)
    checks["0.4.0_equals_narrowing_check_all_kept_families"] = all_kept == {
        "metadiscourse": c040["metadiscourse"],
        "phrase": c040["phrase"],
    }
    c033 = Counter(r["module"] for r in h033)
    if kfi["baseline"]["n_hits"] != {
        "metadiscourse": c033["metadiscourse"],
        "phrase": c033["phrase"],
    }:
        raise SystemExit("0.3.3 development counts differ from the narrowing check")

    tables = {
        v: table(rows, register_of, words)
        for v, rows in (("0.3.2", h032), ("0.3.3", h033), ("0.4.0", h040))
    }
    return {
        "texts": {r: sum(1 for t in texts if t["register"] == r) for r in REGISTERS[:3]}
        | {"all": len(texts)},
        "words": words,
        "sources": {
            "0.3.2": rel(DEV / "hits.jsonl"),
            "0.3.3": rel(DRY / "run" / "frames" / "BASELINE.hits.jsonl"),
            "0.4.0": rel(DEV040 / "hits.jsonl"),
        },
        "checks": checks,
        "tables": tables,
        "effects": {
            "0.3.2->0.3.3": effect(tables["0.3.2"], tables["0.3.3"], words),
            "0.3.3->0.4.0": effect(tables["0.3.3"], tables["0.4.0"], words),
            "0.3.2->0.4.0": effect(tables["0.3.2"], tables["0.4.0"], words),
        },
        "key_comparison": {
            "0.3.2->0.3.3": key_comparison(h032, h033),
            "0.3.3->0.4.0": key_comparison(h033, h040),
        },
        "per_family_totals_from_narrowing_check": {
            "source": rel(FIX / "round2" / "NARROWING_CHECK.json"),
            "note": "each kept family switched on alone over 0.3.3 on the development texts; all registers",
            "BASELINE": kfi["baseline"]["n_hits"],
            **{f: kfi["kept_frames"][f]["n_hits"] for f in KEPT},
            "ALL_KEPT": all_kept,
        },
    }


# --- fix-check rounds -----------------------------------------------------------


def round_effects(rnd: str) -> dict:
    collect = FIX / rnd / "collect"
    texts = read_jsonl(track(collect / "texts.jsonl"))
    register_of = {t["text_id"]: t["register"] for t in texts}
    words_by_text = {}
    for t in texts:
        raw = (collect / "texts" / f"{t['text_id']}.txt").read_bytes()
        if hashlib.sha256(raw).hexdigest() != t["text_sha256"]:
            raise SystemExit(f"{rnd} {t['text_id']}: text hash differs from texts.jsonl")
        words_by_text[t["text_id"]] = len(raw.decode("utf-8").split())
    words = defaultdict(int)
    for tid, n in words_by_text.items():
        words[register_of[tid]] += n
    words["all"] = sum(words_by_text.values())
    words = {r: words[r] for r in REGISTERS}

    receipt_text = track(FIX / rnd / "receipts" / "primary.json").read_text()
    frames_json = PRIVATE / rnd / "diff" / "frames.json"
    archived = json.loads(track(frames_json).read_text())["density"]
    in_receipt = {rel(frames_json): INPUTS[rel(frames_json)] in receipt_text}

    tables = {}
    for cfg in ("BASELINE", "COMPLETE", *FAMILIES):
        p = PRIVATE / rnd / "run" / "frames" / f"{cfg}.hits.jsonl"
        rows = read_jsonl(track(p))
        in_receipt[rel(p)] = INPUTS[rel(p)] in receipt_text
        tables[cfg] = table(rows, register_of, words)
        # the archived table omits empty cells; compare cell by cell, absent = 0 hits
        arch = archived["configs"][cfg]
        for m in MODULES:
            for reg in REGISTERS:
                for g in GROUPS[m]:
                    want = arch.get(m, {}).get(reg, {}).get(g, {"hits": 0, "per_1000_words": 0.0})
                    if want != tables[cfg][m][reg][g]:
                        raise SystemExit(
                            f"{rnd} {cfg} {m} {reg} {g}: {want} != {tables[cfg][m][reg][g]}"
                        )
    if archived["words"] != dict(sorted(words.items())):
        raise SystemExit(f"{rnd}: word counts differ from the archived density table")
    if not all(in_receipt.values()):
        raise SystemExit(f"{rnd}: a private file is not in the public receipt: {in_receipt}")

    acc = json.loads(track(FIX / rnd / "accept" / "acceptance.json").read_text())
    return {
        "texts": {r: sum(1 for t in texts if t["register"] == r) for r in REGISTERS[:3]}
        | {"all": len(texts)},
        "words": words,
        "baseline": {"release": "0.3.3", "commit": RELEASES["0.3.3"]["commit"]},
        "candidate": {**CANDIDATES[rnd], "acceptance_candidate": acc["candidate"]},
        "checks": {
            "density_recomputed_equals_archived_frames_json": True,
            "private_files_listed_in_public_receipt": in_receipt,
            "text_hashes_match_manifest": True,
        },
        "tables": {"BASELINE": tables["BASELINE"], "COMPLETE": tables["COMPLETE"]},
        "effects": {"BASELINE->COMPLETE": effect(tables["BASELINE"], tables["COMPLETE"], words)},
        "per_family_totals": {
            cfg: {m: tables[cfg][m]["all"]["all"]["hits"] for m in MODULES}
            for cfg in ("BASELINE", *FAMILIES, "COMPLETE")
        },
        "per_family_tables": {cfg: tables[cfg] for cfg in FAMILIES},
        "gates": gates(acc, rnd),
    }


def gates(acc: dict, rnd: str) -> dict:
    """Copied from the public acceptance.json (not recomputed)."""
    out: dict[str, Any] = {
        "source": rel(FIX / rnd / "accept" / "acceptance.json"),
        "status": acc["status"],
        "decision_wording": acc["decision_wording"],
        "procedure_problems": acc["procedure_problems"],
        "a_per_bound": acc["a"],
        "unresolved_references_by_reading": {
            k: v.get("unresolved", 0) for k, v in acc["reference_sources"].items()
        },
        "modules": {},
    }
    for m in MODULES:
        mod = acc["modules"][m]
        rem = {
            cfg: {
                k: v[k] for k in ("N", "n", "k_lo", "k_hi", "bound", "passes", "breach_certificate")
            }
            for cfg, v in mod["removal"].items()
            if v["N"] > 0
        }
        cum = {
            rd: {
                k: v[k]
                for k in (
                    "N_baseline",
                    "U_loss",
                    "L_success",
                    "fraction",
                    "passes",
                    "definite_losses_sampled",
                    "breach_certificate",
                )
            }
            for rd, v in mod["cumulative"].items()
        }
        loss_cells = {
            rd: {
                "N_affected": v["N_affected"],
                "cells": {c: x for c, x in v["cells"].items() if x["N_h"] > 0},
            }
            for rd, v in mod["loss"].items()
        }
        fr = mod["frames"]
        removed = fr[f"COMPLETE|{m}|affected|REMOVED"]
        readings = [k for k in removed if k not in ("N", "n")]
        complete_removed = {
            rd: {
                "baseline_labels": removed[rd]["baseline"],
                "sampled_losses": removed[rd].get("sampled_losses"),
            }
            for rd in readings
        }
        final = {}
        for kind in ("ADDED", "CHANGED"):
            for cfg in ("COMPLETE", *FAMILIES):
                v = fr[f"{cfg}|{m}|final|{kind}"]
                cells = {
                    rd: {
                        k: x.get(k)
                        for k in (
                            "N",
                            "n",
                            "method",
                            "definite_correct",
                            "definite_incorrect",
                            "unresolved",
                            "interval95",
                        )
                    }
                    for rd, x in v.items()
                    if isinstance(x, dict) and "N" in x
                }
                if any(c["N"] for c in cells.values()):
                    final.setdefault(kind, {})[cfg] = cells
        out["modules"][m] = {
            "status": mod["status"],
            "breach_certificates": mod["breach_certificates"],
            "removal": rem,
            "cumulative": cum,
            "loss_cells": loss_cells,
            "complete_removed_frame": {
                "N": removed["N"],
                "n": removed.get("n"),
                **complete_removed,
            },
            "baseline_success_labels": fr[f"BASELINE_SUCCESS|{m}"],
            "final_output_diagnostics": final,
        }
    return out


# --- rendering ------------------------------------------------------------------


def n(x: int) -> str:
    return f"{x:,}"


def d(x: float) -> str:
    return f"{x:.2f}"


def sd(x: int) -> str:
    return f"{x:+,}" if x else "0"


def label(g: str) -> str:
    return g.replace("_", " ") if g != "all" else "**all**"


REG_HEAD = "| | Academic | Argumentative | General | All |\n|---|---|---|---|---|"


def dev_tables(dev: dict, m: str) -> str:
    t = dev["tables"]
    vs = ("0.3.2", "0.3.3", "0.4.0")
    hits = [REG_HEAD]
    dens = [REG_HEAD]
    for g in GROUPS[m]:
        hits.append(
            f"| {label(g)} | "
            + " | ".join(" / ".join(n(t[v][m][reg][g]["hits"]) for v in vs) for reg in REGISTERS)
            + " |"
        )
        dens.append(
            f"| {label(g)} | "
            + " | ".join(
                " / ".join(d(t[v][m][reg][g]["per_1000_words"]) for v in vs) for reg in REGISTERS
            )
            + " |"
        )
    return (
        "Hits, 0.3.2 / 0.3.3 / 0.4.0:\n\n"
        + "\n".join(hits)
        + "\n\nHits per 1,000 words, 0.3.2 / 0.3.3 / 0.4.0:\n\n"
        + "\n".join(dens)
    )


def round_tables(rd: dict, m: str) -> str:
    t = rd["tables"]
    hits = [REG_HEAD]
    dens = [REG_HEAD]
    for g in GROUPS[m]:
        hits.append(
            f"| {label(g)} | "
            + " | ".join(
                f"{n(t['BASELINE'][m][reg][g]['hits'])} → {n(t['COMPLETE'][m][reg][g]['hits'])}"
                for reg in REGISTERS
            )
            + " |"
        )
        dens.append(
            f"| {label(g)} | "
            + " | ".join(
                f"{d(t['BASELINE'][m][reg][g]['per_1000_words'])} → {d(t['COMPLETE'][m][reg][g]['per_1000_words'])}"
                for reg in REGISTERS
            )
            + " |"
        )
    return (
        "Hits, 0.3.3 → candidate:\n\n"
        + "\n".join(hits)
        + "\n\nHits per 1,000 words, 0.3.3 → candidate:\n\n"
        + "\n".join(dens)
    )


def summary_table(dev: dict) -> str:
    lines = [
        "| Module | Register | Words | 0.3.2 | 0.3.3 | 0.4.0 | 0.3.2→0.3.3 | 0.3.3→0.4.0 | 0.3.2→0.4.0 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in MODULES:
        for reg in REGISTERS:
            t = [dev["tables"][v][m][reg]["all"] for v in ("0.3.2", "0.3.3", "0.4.0")]
            e = [
                dev["effects"][k][m][reg]["all"]
                for k in ("0.3.2->0.3.3", "0.3.3->0.4.0", "0.3.2->0.4.0")
            ]
            cells = [f"{n(x['hits'])} ({d(x['per_1000_words'])})" for x in t]
            deltas = [
                f"{sd(x['delta_hits'])} ({x['pct_change']:+.1f}%)" if x["delta_hits"] else "0"
                for x in e
            ]
            lines.append(
                f"| {m} | {reg} | {n(dev['words'][reg])} | " + " | ".join(cells + deltas) + " |"
            )
    return "\n".join(lines)


def round_summary(rounds: dict) -> str:
    lines = [
        "| Round | Module | Register | Words | 0.3.3 | Candidate | Change |",
        "|---|---|---|---|---|---|---|",
    ]
    for rnd, rd in rounds.items():
        for m in MODULES:
            for reg in REGISTERS:
                b, a = (
                    rd["tables"]["BASELINE"][m][reg]["all"],
                    rd["tables"]["COMPLETE"][m][reg]["all"],
                )
                e = rd["effects"]["BASELINE->COMPLETE"][m][reg]["all"]
                lines.append(
                    f"| {rnd[-1]} | {m} | {reg} | {n(rd['words'][reg])} | {n(b['hits'])} ({d(b['per_1000_words'])}) "
                    f"| {n(a['hits'])} ({d(a['per_1000_words'])}) | {sd(e['delta_hits'])} ({e['pct_change']:+.1f}%) |"
                )
    return "\n".join(lines)


def family_table(dev: dict, rounds: dict) -> str:
    lines = [
        "| Family | Kept in 0.4.0 | Round 1: metadiscourse | Round 1: PHRASE | Round 2: metadiscourse | Round 2: PHRASE | Development: metadiscourse | Development: PHRASE |",
        "|---|---|---|---|---|---|---|---|",
    ]
    nc = dev["per_family_totals_from_narrowing_check"]
    for cfg in ("BASELINE", *FAMILIES, "COMPLETE"):
        cells = []
        for rnd in ("round1", "round2"):
            base = rounds[rnd]["per_family_totals"]["BASELINE"]
            v = rounds[rnd]["per_family_totals"][cfg]
            cells += [n(v[m]) if cfg == "BASELINE" else sd(v[m] - base[m]) for m in MODULES]
        key = "ALL_KEPT" if cfg == "COMPLETE" else cfg
        if key in nc:
            cells += [
                n(nc[key][m]) if cfg == "BASELINE" else sd(nc[key][m] - nc["BASELINE"][m])
                for m in MODULES
            ]
        else:
            cells += ["reverted", "reverted"]
        name = {"BASELINE": "0.3.3 (total)", "COMPLETE": "all families"}.get(cfg, cfg)
        kept = (
            ""
            if cfg == "BASELINE"
            else ("yes" if cfg in KEPT else ("—" if cfg == "COMPLETE" else "no"))
        )
        lines.append(f"| {name} | {kept} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def gate_table(rounds: dict) -> str:
    lines = [
        "| Round | Module | Frame | Removals (N) | Labelled (n) | Judged correct (k_lo–k_hi) | Upper bound | ≤ .15 | Certificate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rnd, rd in rounds.items():
        for m in MODULES:
            for cfg, v in rd["gates"]["modules"][m]["removal"].items():
                k = f"{v['k_lo']}" if v["k_lo"] == v["k_hi"] else f"{v['k_lo']}–{v['k_hi']}"
                lines.append(
                    f"| {rnd[-1]} | {m} | {cfg} | {n(v['N'])} | {v['n']} | {k} | {v['bound']:.4f} | "
                    f"{'yes' if v['passes'] else 'no'} | {'yes' if v['breach_certificate'] else 'no'} |"
                )
    return "\n".join(lines)


def cum_table(rounds: dict) -> str:
    lines = [
        "| Round | Module | Reading | Baseline hits | Upper bound on loss | Lower bound on correct | Fraction | ≤ .05 | Definite losses (sampled) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rnd, rd in rounds.items():
        for m in MODULES:
            for rdg, v in rd["gates"]["modules"][m]["cumulative"].items():
                lines.append(
                    f"| {rnd[-1]} | {m} | {rdg} | {n(v['N_baseline'])} | {v['U_loss']:.1f} | "
                    f"{v['L_success']:.1f} | {v['fraction']:.4f} | {'yes' if v['passes'] else 'no'} | "
                    f"{v['definite_losses_sampled']} |"
                )
    return "\n".join(lines)


def loss_table(rounds: dict) -> str:
    lines = [
        "| Round | Module | Reading | Affected cell | N | n | Losses: definite (k_lo) – possible (k_hi) |",
        "|---|---|---|---|---|---|---|",
    ]
    for rnd, rd in rounds.items():
        for m in MODULES:
            for rdg, v in rd["gates"]["modules"][m]["loss_cells"].items():
                for c, x in v["cells"].items():
                    lines.append(
                        f"| {rnd[-1]} | {m} | {rdg} | {c} | {n(x['N_h'])} | {x['n_h']} | {x['k_lo']}–{x['k_hi']} |"
                    )
    return "\n".join(lines)


def final_table(rounds: dict) -> str:
    lines = [
        "| Round | Module | Frame | Configuration | Reading | N | n | Judged correct | Judged incorrect | Unresolved |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for rnd, rd in rounds.items():
        for m in MODULES:
            for kind, cfgs in rd["gates"]["modules"][m]["final_output_diagnostics"].items():
                for cfg, cells in cfgs.items():
                    for rdg, x in cells.items():
                        lines.append(
                            f"| {rnd[-1]} | {m} | {kind} | {cfg} | {rdg} | {n(x['N'])} | {x['n']} | "
                            f"{x['definite_correct']} | {x['definite_incorrect']} | {x['unresolved']} |"
                        )
    return "\n".join(lines)


def key_table(dev: dict) -> str:
    lines = [
        "| Step | Module | Before | After | Unchanged | Claim changed at same span (before → after) | Span removed | Span added |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for step, v in dev["key_comparison"].items():
        for m in MODULES:
            x = v[m]
            lines.append(
                f"| {step.replace('->', '→')} | {m} | {n(x['n_before'])} | {n(x['n_after'])} | {n(x['unchanged'])} | "
                f"{n(x['claim_changed_before'])} → {n(x['claim_changed_after'])} | {n(x['span_removed'])} | {n(x['span_added'])} |"
            )
    return "\n".join(lines)


def unresolved_line(rounds: dict) -> str:
    parts = []
    for rnd, rd in rounds.items():
        u = rd["gates"]["unresolved_references_by_reading"]
        parts.append(
            f"round {rnd[-1]}: " + ", ".join(f"{k.replace('|', ' ')} {v}" for k, v in u.items())
        )
    return "; ".join(parts)


def render(rec: dict) -> str:
    dev, rounds = rec["development"], rec["rounds"]
    r1, r2 = rounds["round1"], rounds["round2"]
    md = f"""# Study 4: development and fix-check effects of the 0.3.2 → 0.4.0 matcher changes

**Draft for independent review.** Generated by [`effects.py`](../../scripts/validation/study4_precision/pilot040/effects.py); every number is also in [`study4-development-effects.json`](study4-development-effects.json), with the SHA-256 of each input.

## What this is, and what it is not

This report publishes how the metadiscourse and PHRASE outputs changed between releases: the 0.3.2 → 0.3.3 bridge, the 0.3.3 → 0.4.0 fixes, and the cumulative 0.3.2 → 0.4.0 change. It gives complete hit counts and hits per 1,000 words by category (metadiscourse) or K-band (PHRASE) and register, on the 120 development texts and on the 60 new texts of each fix-check round.

These are **development diagnostics**:

- They count output. They are not precision, which needs labels, and they are not recall, which Study 4 does not estimate. Fewer hits is not, by itself, better or worse.
- The development texts are the texts on which the errors were found and the fixes written. Changes there are not an unbiased before/after estimate of anything.
- The fix-check round texts were new, but the counts below are still only output counts. The labelled results on those texts are the registered gates, which are summarised and linked [below](#fix-check-gates-and-diagnostics), not recomputed.

## Release identities

| Release | Tag | Commit | Role here |
|---|---|---|---|
| 0.3.2 | `v0.3.2` | `{RELEASES["0.3.2"]["commit"]}` | original development build (2026-10-16) |
| 0.3.3 | `v0.3.3` | `{RELEASES["0.3.3"]["commit"]}` | fix-check baseline; tokenisation fixes only over 0.3.2 |
| round-1 candidate | — | `{CANDIDATES["round1"]["commit"]}` | all 12 families; failed, never released |
| round-2 candidate | — | `{CANDIDATES["round2"]["commit"]}` | 6 kept families; passed |
| 0.4.0 | `v0.4.0` | `{RELEASES["0.4.0"]["commit"]}` | release; its `src/` differs from the round-2 candidate only in the version string and one static HTML note |

The 0.4.0 development rebuild ran at commit `{DEV040_BUILD_COMMIT}`, whose `src/` is identical to `v0.4.0`. All runs used spaCy `en_core_web_sm` 3.8.0.

## How the counts were produced

Nothing was rerun for this report. Every count comes from archived detector output:

| Texts | Release | Source |
|---|---|---|
| development | 0.3.2 | `{dev["sources"]["0.3.2"]}` (original build) |
| development | 0.3.3 | `{dev["sources"]["0.3.3"]}`: the fix-check harness's dry run of a checkout pinned at `dec79bc`, no families. It equals the pinned-baseline frame and a separate 0.3.3 rebuild (`hits_033.jsonl`) hit for hit. |
| development | 0.4.0 | `{dev["sources"]["0.4.0"]}` (rebuild of 2026-10-20 on the same text bytes). Its totals equal the [narrowing check](study4-fix040/round2/NARROWING_CHECK.json)'s run with all kept families on. |
| round 1, round 2 | 0.3.3, candidate, each family | the private `run/frames/*.hits.jsonl` of each round. Their SHA-256s, and that of each round's archived density table, are listed in the public receipts ([round 1](study4-fix040/round1/receipts/primary.json), [round 2](study4-fix040/round2/receipts/primary.json)). This report recomputes the density tables from the hit files; they equal the archived tables cell for cell. |

**Words** are whitespace-separated tokens of the archived text, `len(text.split())`. This is the rule `build.py` uses for eligibility, applied to the archived text the detector actually ran on; for the 37 truncated development texts that is the truncated text, not the full source. Fix-check density used the same rule. Densities are shown to 2 decimals here and 3 in the JSON.

The development text bytes are identical across the 0.3.2 build, the dry run and the 0.4.0 rebuild, so all three releases ran on the same input.

## Development texts (120: 40 per register)

### Totals

Hits (hits per 1,000 words); changes in hits (per cent of the earlier count).

{summary_table(dev)}

The 0.3.2 → 0.3.3 bridge adds two metadiscourse hits and two PHRASE hits in two texts (tokenisation fixes), and changes nothing else.

### Metadiscourse by category

{dev_tables(dev, "metadiscourse")}

### PHRASE by K-band

{dev_tables(dev, "phrase")}

### Which hits changed

A simple span-keyed comparison: per text and character span, claims (category, or PHRASE entry and sense) present in both releases are unchanged; other claims at a span found in both are claim changes; spans found in only one release are removed or added. A moved span counts as one removal and one addition. This is not the fix-check crosswalk, which links hits more carefully and is what the gates use.

{key_table(dev)}

From 0.3.3 to 0.4.0, the metadiscourse claim changes are reassignments: MD-I moves past-tense exclusive *we* and *us* from engagement markers to self mentions, and MD-D moves some *indeed* from boosters to code glosses. The metadiscourse span removals are deletions by MD-D and MD-H; MD-H removes quoted material of any category. The PHRASE removals and additions come from PH-A to PH-C.

### Each kept family alone, on the development texts

From the public [narrowing check](study4-fix040/round2/NARROWING_CHECK.json): total hits with one family switched on over 0.3.3, all registers. They appear in the [family table](#each-family-alone-on-the-round-texts) below as the last two columns.

## Fix-check round texts (60 per round: 20 per register)

Each round compares 0.3.3 with that round's candidate (all families on) on 60 texts not used in development. Round 1's candidate failed and was not released. Round 2's candidate is 0.4.0. 0.3.2 was not run on these texts; its only difference from 0.3.3 on the development texts is the four hits above.

### Totals

Hits (hits per 1,000 words); change in hits (per cent).

{round_summary(rounds)}

The round-2 totals reproduce the published figures: metadiscourse {n(r2["tables"]["BASELINE"]["metadiscourse"]["all"]["all"]["hits"])} → {n(r2["tables"]["COMPLETE"]["metadiscourse"]["all"]["all"]["hits"])}, PHRASE {n(r2["tables"]["BASELINE"]["phrase"]["all"]["all"]["hits"])} → {n(r2["tables"]["COMPLETE"]["phrase"]["all"]["all"]["hits"])} ([fix-check report](study4-fix-check.md#round-2-pass)).

### Round 1: metadiscourse by category ({n(r1["words"]["all"])} words)

{round_tables(r1, "metadiscourse")}

### Round 1: PHRASE by K-band

{round_tables(r1, "phrase")}

### Round 2: metadiscourse by category ({n(r2["words"]["all"])} words)

{round_tables(r2, "metadiscourse")}

### Round 2: PHRASE by K-band

{round_tables(r2, "phrase")}

### Each family alone, on the round texts

Change in total hits (all registers) with one family switched on over 0.3.3. "Kept" means kept in round 2 and 0.4.0; the other six were reverted to 0.3.3 after round 1 ([narrowing disposition](study4-fix040/round2/NARROWING_DISPOSITION.md)). These are net changes: they differ from the removal counts in the gate table below by any additions. Family effects overlap, so they need not add up to the all-families row. Per-family tables by category, K-band and register are in the JSON.

The round-1 decisions, from the [fix-check report](study4-fix-check.md#narrowing): MD-B, MD-C, MD-E and MD-F carried breach certificates; MD-A's removal bound was over .15; MD-G met its gate (.148) but was reverted as a precaution, decided after seeing the result. No kept family's rules changed between rounds.

{family_table(dev, rounds)}

MD-I only reassigns categories, so its total is unchanged; its effect shows in the category tables (engagement markers down, self mentions up).

## Fix-check gates and diagnostics

These are the registered, labelled results. They are copied from the public acceptance files, not recomputed: [round 1](study4-fix040/round1/accept/acceptance.md) ([JSON](study4-fix040/round1/accept/acceptance.json)), [round 2](study4-fix040/round2/accept/acceptance.md) ([JSON](study4-fix040/round2/accept/acceptance.json)). The reference is model labels, not a trained human reference; see the [fix-check report](study4-fix-check.md), including its disclosed blinding deviation and sensitivity analysis.

**Outcomes.** Round 1: **{r1["gates"]["status"]}** (metadiscourse {r1["gates"]["modules"]["metadiscourse"]["status"]}, PHRASE {r1["gates"]["modules"]["phrase"]["status"]}). Round 2: **{r2["gates"]["status"]}** (metadiscourse {r2["gates"]["modules"]["metadiscourse"]["status"]}, PHRASE {r2["gates"]["modules"]["phrase"]["status"]}). Neither round recorded a procedure problem. The terminal outcome, `ship`, is in [`round_registry.jsonl`](study4-fix040/round_registry.jsonl).

### Removal gate (per family and all families)

Removals that the reference judges correct; one-sided upper bound at a = .05/68.

{gate_table(rounds)}

### Cumulative-loss gate

{cum_table(rounds)}

### Losses by affected cell (all families)

Sampled affected baseline hits judged lost. k_lo counts definite losses; k_hi adds possible losses, where an unresolved label or an unresolved correspondence is counted against the candidate.

{loss_table(rounds)}

### Unresolved references

Labelled items with no resolved reference label after adjudication, by module and reading: {unresolved_line(rounds)}. Within a gate frame they count against the candidate. The CONNECTIVE and PHRASAL readings do not enter the gates.

### Added and changed output

Descriptive only, outside the acceptance family: new hits with no 0.3.3 counterpart (ADDED), and every candidate hit linked to a changed 0.3.3 hit (CHANGED), with the reference's judgements. Configurations with no such hits are omitted.

{final_table(rounds)}

## What cannot be concluded

- **Not precision or recall.** Hit counts and densities say how much each release outputs, not how much of it is right or how much it misses. A fall in hits can remove errors, correct detections, or both. The gates bound the loss of correct detections; they do not show a net gain.
- **Not an unbiased before/after estimate.** The development changes were made on the development texts. The round texts were new, but their labelled results are loss bounds against a model reference, not estimates of precision before and after.
- **Not a sample of a defined population.** The texts come from the study's sources (open-access research articles, Wikipedia essays and general articles); density depends on that mix and on truncation at 50,000 bytes.
- **No per-rule validation.** The gates measure aggregate loss per family and in total. Known rule gaps are in [CAVEATS.md](../../CAVEATS.md).
- **Precision is still to be measured.** The precision study is described in the [draft protocol](study4-preregistration.md). The [0.4.0 labelling pilot](study4-pilot040/RESULTS.md) is a separate development exercise on the development texts.
"""
    return md


# --- main -----------------------------------------------------------------------


def build() -> tuple[str, str]:
    INPUTS.clear()
    dev = development()
    rounds = {r: round_effects(r) for r in ("round1", "round2")}
    tags = {v: git("rev-list", "-n", "1", r["tag"]) for v, r in RELEASES.items()}
    for v, c in tags.items():
        if c != RELEASES[v]["commit"]:
            raise SystemExit(f"tag {RELEASES[v]['tag']} points at {c}, not {RELEASES[v]['commit']}")
    cand_vs_release = git(
        "diff",
        "--name-only",
        CANDIDATES["round2"]["commit"],
        RELEASES["0.4.0"]["commit"],
        "--",
        "src",
    ).splitlines()
    rec = {
        "what": "Study 4 development and fix-check effects: hit counts and hits per 1,000 words by module, "
        "category or K-band, and register, for 0.3.2, 0.3.3 and 0.4.0 on the development texts and "
        "for 0.3.3 and each round's candidate on the fix-check texts; plus the registered gate "
        "results copied from the public acceptance files.",
        "status": "draft for independent review",
        "caveat": "Development diagnostics: output counts, not precision and not recall; development-text "
        "changes are not an unbiased before/after estimate. Gate results are copied, not recomputed.",
        "releases": RELEASES,
        "fixcheck_candidates": CANDIDATES,
        "release_checks": {
            "tags_resolve_to_commits": True,
            "round2_candidate_vs_0.4.0_src_files_differing": cand_vs_release,
            "dev_0.4.0_build_commit": DEV040_BUILD_COMMIT,
        },
        "method": {
            "word_count": "len(text.split()) on the archived (normalised, possibly truncated) text: the "
            "whitespace rule build.py uses for eligibility and fixcheck/crosswalk.py uses for density",
            "per_1000_words": "round(1000 * hits / words, 3)",
            "groups": "metadiscourse: hit category; phrase: K-band of the matched PHRASE List entry",
            "pct_change": "round(100 * (after - before) / before, 1); null when before is 0",
            "development_0.3.3": "fix-check harness dry run (.cache/validation/study4_fix040/harness_dryrun), "
            "BASELINE frame, pinned dec79bc checkout run in its own uv environment, no "
            "families; equal hit for hit to BASELINE_PINNED and to hits_033.jsonl",
            "rounds": "density recomputed from private run/frames/<config>.hits.jsonl and the round's "
            "collect/texts; equal cell for cell to the archived private diff/frames.json density",
            "key_comparison": "multiset per (module, text_id, span) of claims (category; or PHRASE expression, "
            "rank, sense); not the fix-check crosswalk",
            "gates": "copied from docs/validation/study4-fix040/round*/accept/acceptance.json",
            "command": "uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/effects.py",
        },
        "inputs_sha256": dict(sorted(INPUTS.items())),
        "development": dev,
        "rounds": rounds,
    }
    return json.dumps(rec, indent=1, ensure_ascii=False) + "\n", render(rec)


def main(argv: list[str]) -> int:
    js, md = build()
    if "--check" in argv:
        ok = OUT_JSON.read_text() == js and OUT_MD.read_text() == md
        print("ok" if ok else "differs")
        return 0 if ok else 1
    OUT_JSON.write_text(js)
    OUT_MD.write_text(md)
    print(f"wrote {rel(OUT_JSON)} and {rel(OUT_MD)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
