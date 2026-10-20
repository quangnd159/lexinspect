"""Recompute the Study 4 pilot quantities, fix-check gates and sensitivity analysis from the
text-free export alone, with the frozen project code, and compare with the published values.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/recompute.py \\
        [--export docs/validation/study4-textfree] [--json report.json]

Reads only the export folder and the public repository (code, and the published documents
and acceptance files the numbers are compared with). Exit 0 only if every check passes.

How. The export's shapes are materialised as a text-free "shadow package" in a temporary
directory: label lines rebuilt by common.synth_line, items by common.pseudo_item (codes and
placeholder strings only), the key, frame, orders, selection and assignment files as
exported. The frozen entry points then run unchanged on it:
- pilots: analyse.main (design validation, label validation, references, estimates,
  agreement, batches), exactly as the private pilot.json was produced (default options);
- gates and sensitivity: fixcheck.accept.acceptance_of (label loading and validation,
  references, frames_from_key, compute), as in the registered decision and in
  round2/sensitivity/run_sensitivity.py.txt.
Bypassed, because they read text or the full package: fixcheck.package.check_package (hash
chain of every package file), the registry and runtime checks of accept.main. The label
files' SHA-256 in acceptance.json are those of the private files; they are compared with
the SHA-256 the export records for its sources.

What is compared.
1. 0.4.0 pilot: every figure of study4-pilot040/RESULTS.md (each expected phrase is built
   from the recomputed numbers and must occur verbatim in the document); the whole
   recomputed analysis against reference/pilot_textfree.json (pilot.json minus the PHRASE
   alt-category wording); the change-status diagnostics against
   reference/flash_diagnostics.json (byte copy; its SHA-256 is published); A's retry merge.
2. 0.3.2 pilot: the figures in the preregistration and the RESULTS.md history line.
3. Fix-check gates: round{1,2}/accept/acceptance.json, every field computed from labels.
4. Round-2 sensitivity: sensitivity/S-B_acceptance.json and control_acceptance.json, whole.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import analyse
import common as C
from fixcheck import accept

REPO = HERE.parents[3]
EXPORT = REPO / "docs" / "validation" / "study4-textfree"
DOCS = REPO / "docs" / "validation"
RESULTS = DOCS / "study4-pilot040" / "RESULTS.md"
PREREG = DOCS / "study4-preregistration.md"
FIX = DOCS / "study4-fix040"
# acceptance.json fields that describe the package and the production run, not the
# arithmetic: they need the full package and are not recomputed.
PACKAGE_FIELDS = (
    "package_check",
    "acceptance_runtime",
    "candidate",
    "registry_entry",
    "mode",
    "production_eligible",
    "mathematical_status",
)
LABEL_ABBR = {
    "CORRECT": "C",
    "WRONG_CATEGORY": "WC",
    "EXTERNAL_CONNECTIVE": "EC",
    "NOT_METADISCOURSE": "NM",
    "WRONG_SENSE_LISTED": "WL",
    "WRONG_SENSE_UNLISTED": "WU",
    "NOT_THE_EXPRESSION": "NE",
    "UNSURE": "U",
}


# --- formatting as published --------------------------------------------------------------------


def p3(x: float) -> str:
    return f"{x:.3f}".removeprefix("0")


def p5(x: float) -> str:
    return f"{x:.5f}".removeprefix("0")


def k2(x: float) -> str:
    return f"{x:.2f}".removeprefix("0")


def n(x: int) -> str:
    return f"{x:,}"


# --- the export ---------------------------------------------------------------------------------


class Export:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = C.read_json(root / "manifest.json")

    def p(self, rel: str) -> Path:
        return self.root / rel

    def lines(self, rel: str) -> list[str]:
        return C.read_lines(self.p(rel))

    def jsonl(self, rel: str) -> list[dict[str, Any]]:
        return C.read_jsonl(self.p(rel))

    def json(self, rel: str) -> Any:
        return C.read_json(self.p(rel))

    def ids(self, rel: str) -> list[str]:
        return [x.strip() for x in self.lines(rel) if x.strip()]

    def source(self, rel: str) -> dict[str, str]:
        (src,) = self.manifest["files"][rel]["derived_from"]
        return src

    def integrity(self) -> list[str]:
        """SHA256SUMS covers every file and every file matches."""
        sums = {}
        for line in self.lines("SHA256SUMS"):
            h, rel = line.split("  ", 1)
            sums[rel] = h
        present = {
            p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()
        } - {"SHA256SUMS"}
        probs = [f"not in SHA256SUMS: {r}" for r in sorted(present - set(sums))]
        probs += [f"missing: {r}" for r in sorted(set(sums) - present)]
        probs += [
            f"SHA-256 differs: {r}"
            for r in sorted(present & set(sums))
            if C.sha256_file(self.p(r)) != sums[r]
        ]
        return probs


def write_lines(p: Path, lines: list[str]) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(x + "\n" for x in lines), encoding="utf-8")
    return p


def shadow_items(ex: Export, folder: str) -> tuple[list[dict], dict[str, dict], list[dict]]:
    shapes = ex.jsonl(f"{folder}/items.jsonl.gz")
    pseudo = [C.pseudo_item(s) for s in shapes]
    return shapes, {s["id"]: s for s in shapes}, pseudo


def synth(ex: Export, rel: str) -> list[str]:
    return [C.synth_line(x) for x in ex.lines(rel)]


# --- pilots ---------------------------------------------------------------------------------------


def run_pilot(ex: Export, name: str, tmp: Path) -> dict[str, Any]:
    """analyse.main on the shadow package: the frozen registered analysis, default options."""
    d = tmp / name
    _, by_id, pseudo = shadow_items(ex, name)
    key = ex.jsonl(f"{name}/key.jsonl.gz")
    for r in key:
        if r["module"] == "phrase":
            r["expression"] = C.claimed_placeholder(by_id[r["id"]])
    write_lines(d / "key.jsonl", [C.dump_line(r) for r in key])
    write_lines(d / "items.jsonl", [C.dump_line(it) for it in pseudo])
    (d / "frame.json").write_bytes(ex.p(f"{name}/frame.json").read_bytes())
    (d / "orders.json").write_bytes(ex.p(f"{name}/orders.json").read_bytes())
    write_lines(d / "human_sample_ids.txt", ex.ids(f"{name}/maintainer_sample_ids.txt"))
    files = {
        r: write_lines(d / f"{r}.jsonl", synth(ex, f"{name}/labels/{r}.jsonl.gz"))
        for r in ("A", "B", "adjudicator")
    }
    out = d / "pilot.json"
    argv = [
        "--key", str(d / "key.jsonl"),
        "--labels", f"A={files['A']}", f"B={files['B']}",
        "--adjudicator", f"C={files['adjudicator']}",
        "--json", str(out),
    ]  # fmt: skip
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = analyse.main(argv)
    if rc != 0:
        raise RuntimeError(f"{name}: analyse.main exited {rc}")
    rep = json.loads(out.read_text())
    items = {it["id"]: it for it in pseudo}
    sets = {
        r: analyse.validate_lines(synth(ex, f"{name}/labels/{r}.jsonl.gz"), items, None, r)
        for r in ("A_original", "A", "B")
    }
    sets["A_retry"] = analyse.validate_lines(
        synth(ex, f"{name}/labels/A_retry.jsonl.gz"),
        items,
        ex.ids(f"{name}/labels/A_retry_ids.txt"),
        "A_retry",
    )
    need = ex.ids(f"{name}/labels/needs_adjudication.txt")
    sets["adjudicator"] = analyse.validate_lines(
        synth(ex, f"{name}/labels/adjudicator.jsonl.gz"), items, need, "C"
    )
    merged, notes = analyse.merge_retry(
        ex.lines(f"{name}/labels/A_original.jsonl.gz"),
        ex.lines(f"{name}/labels/A_retry.jsonl.gz"),
        ex.ids(f"{name}/labels/A_retry_ids.txt"),
    )
    final = [x for x in ex.lines(f"{name}/labels/A.jsonl.gz") if x.strip()]
    return {
        "report": rep,
        "sets": sets,
        "key": key,
        "need": need,
        "merge_ok": merged == final and not notes,
        "need_ok": analyse.needs_adjudication(key, [sets["A"], sets["B"]]) == need,
    }


def strict_all(rep: dict, m: str) -> dict:
    return rep["model_reference"][m]["STRICT"]["ALL"]


def strict_needed(rep: dict, m: str) -> int:
    src = rep["reference_sources"][m]["STRICT"]
    return src.get("adjudicator", 0) + src.get("unresolved", 0)


def role_row(ls: analyse.LabelSet) -> str:
    c = Counter(r["label"] for r in ls.labels.values())
    return " | ".join(str(c.get(lab, 0)) for lab in LABEL_ABBR)


def flash_diagnostics(ex: Export, run: dict[str, Any]) -> dict[str, Any]:
    """The change-status diagnostics of RESULTS.md (no frozen code exists for these; the rule
    is the one recorded in flash_diagnostics.json)."""
    old = {
        (h["module"], h["text_id"], tuple(h["span"]), h.get("category", h.get("rank")))
        for h in ex.jsonl("pilot040/dev032_hits.jsonl.gz")
    }
    status = {}
    for r in run["key"]:
        claim = r["category"] if r["module"] == "metadiscourse" else r["rank"]
        hit = (r["module"], r["text_id"], tuple(r["span"]), claim) in old
        status[r["id"]] = f"{r['module']}|{'unchanged' if hit else 'new_or_changed'}"
    counts = Counter(status.values())
    a, b, c = run["sets"]["A"], run["sets"]["B"], run["sets"]["adjudicator"]
    module = {r["id"]: r["module"] for r in run["key"]}
    by: dict[str, Counter] = {}
    for i in run["need"]:
        g = by.setdefault(status[i], Counter())
        m = module[i]
        ya, yb, yc = (analyse.outcome_value(m, "STRICT", ls.label(i)) for ls in (a, b, c))
        g["requests"] += 1
        g["valid"] += i in c.labels
        g["unsure"] += c.label(i) == "UNSURE"
        for role, y in (("A", ya), ("B", yb)):
            if y is not None and yc is not None:
                g[f"strict_pairs_{role}"] += 1
                g[f"agree_{role}"] += y == yc
        g["ab_strict_split"] += ya is not None and yb is not None and ya != yb
    keys = (
        "requests",
        "valid",
        "unsure",
        "strict_pairs_A",
        "agree_A",
        "strict_pairs_B",
        "agree_B",
        "ab_strict_split",
    )
    return {
        "change_status_counts": dict(counts),
        "flash_by_module_change": {g: {k: v[k] for k in keys} for g, v in by.items()},
    }


# --- comparison helpers -------------------------------------------------------------------------


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.docs: dict[Path, str] = {}

    def add(self, target: str, what: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"target": target, "check": what, "ok": bool(ok), "detail": detail})

    def quote(self, target: str, what: str, doc: Path, text: str) -> None:
        """The published document contains `text`, built from the recomputed numbers."""
        if doc not in self.docs:
            self.docs[doc] = doc.read_text(encoding="utf-8") if doc.exists() else ""
        rel = doc.relative_to(REPO).as_posix()
        self.add(target, what, text in self.docs[doc], f"{rel}: {text!r}")

    def equal(self, target: str, what: str, got: Any, want: Any) -> None:
        diffs = diff(got, want)
        detail = "identical" if not diffs else f"{len(diffs)} differences: " + "; ".join(diffs[:5])
        self.add(target, what, not diffs, detail)


def norm(x: Any) -> Any:
    return json.loads(json.dumps(x, sort_keys=True, default=str))


def diff(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{path}/{k}: only recomputed" for k in sorted(set(a) - set(b))]
        out += [f"{path}/{k}: only published" for k in sorted(set(b) - set(a))]
        for k in sorted(set(a) & set(b)):
            out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            d for i, (x, y) in enumerate(zip(a, b, strict=True)) for d in diff(x, y, f"{path}[{i}]")
        ]
    if a != b or type(a) is not type(b):
        return [f"{path}: {str(a)[:60]} != {str(b)[:60]}"]
    return []


# --- targets ------------------------------------------------------------------------------------


def target_pilot040(ex: Export, ck: Checks, tmp: Path) -> None:
    T, R = "1 pilot040", RESULTS
    run = run_pilot(ex, "pilot040", tmp)
    rep, sets = run["report"], run["sets"]
    md, ph = strict_all(rep, "metadiscourse"), strict_all(rep, "phrase")
    ck.add(T, "A's merged file = merge_retry(pass 1, retry, manifest ids)", run["merge_ok"])
    ck.add(T, "adjudicator assignment = needs_adjudication(A, B)", run["need_ok"])
    # Whole analysis against pilot.json (text-free projection).
    got = norm(rep)
    for ls in got["alt_categories"].values():
        ls.pop("phrase", None)
    ck.equal(
        T,
        "whole analysis = reference/pilot_textfree.json",
        got,
        ex.json("pilot040/reference/pilot_textfree.json"),
    )
    ck.equal(
        T,
        "change-status diagnostics = reference/flash_diagnostics.json",
        flash_diagnostics(ex, run),
        {
            k: v
            for k, v in ex.json("pilot040/reference/flash_diagnostics.json").items()
            if k != "rule"
        },
    )
    # RESULTS.md, figure by figure.
    a0, rt, c = sets["A_original"], sets["A_retry"], sets["adjudicator"]
    inval = a0.summary()["problems_by_reason"]
    ck.add(
        T,
        "A pass-1 invalid records all alt_category_same_as_claimed",
        set(inval) == {"alt_category_same_as_claimed"},
        str(inval),
    )
    ck.quote(
        T,
        "A pass-1 validation",
        R,
        f"**A:** {n(len(a0.labels))}/{n(len(a0.expected))} valid. The {len(a0.retry)} invalid records gave the claimed category",
    )
    ck.quote(
        T,
        "A retry",
        R,
        f"all {len(rt.labels)} came back valid"
        if len(rt.labels) == len(rt.expected)
        else "<retry incomplete>",
    )
    b = sets["B"]
    ck.quote(
        T,
        "B validation",
        R,
        f"**B:** {n(len(b.labels))}/{n(len(b.expected))} valid, with no retry."
        if not b.retry
        else "<B retried>",
    )
    nu_c = sum(r["label"] == "UNSURE" for r in c.labels.values())
    bad_c = len(c.expected) - len(c.labels)
    ck.quote(
        T,
        "adjudicator validation",
        R,
        f"**Adjudicator:** {len(c.labels)}/{len(c.expected)} valid records"
        + ("; no missing or invalid record and no retry." if not bad_c and not c.retry else ""),
    )
    ck.quote(
        T,
        "adjudicator UNSURE",
        R,
        "One valid record was UNSURE." if nu_c == 1 else f"<{nu_c} UNSURE>",
    )
    a = sets["A"]
    nu = {
        r: sum(x["label"] == "UNSURE" for x in s.labels.values()) for r, s in (("A", a), ("B", b))
    }
    ok_after = len(a.labels) == len(b.labels) == len(a.expected) and nu["A"] == nu["B"]
    ck.quote(
        T,
        "A and B after the retry",
        R,
        f"A and B each had {n(len(a.labels))} valid records and no missing or invalid record, including {nu['A']} UNSURE records each."
        if ok_after
        else "<A and B differ>",
    )
    ck.quote(T, "labels by role: A", R, f"| A (merged) | {role_row(a)} |")
    ck.quote(T, "labels by role: B", R, f"| B | {role_row(b)} |")
    ck.quote(
        T,
        "labels by role: adjudicator",
        R,
        f"| adjudicator ({len(c.expected)} items) | {role_row(c)} |",
    )
    ck.quote(T, "items", R, f"| Items | {n(md['n_items'])} | {n(ph['n_items'])} |")
    ck.quote(T, "design-weighted STRICT precision and exact 95% limits", R,
             f"| STRICT precision, design-weighted (N_h/r_h) | **{p3(md['p'])}** ({p5(md['p'])}); exact 95% [{p3(md['ci95_exact'][0])}, {p3(md['ci95_exact'][1])}] | **{p3(ph['p'])}** ({p5(ph['p'])}); exact 95% [{p3(ph['ci95_exact'][0])}, {p3(ph['ci95_exact'][1])}] |")  # fmt: skip
    uw = md["unweighted"], ph["unweighted"]
    ck.quote(
        T,
        "unweighted STRICT precision",
        R,
        f"| STRICT precision, unweighted | {uw[0]['k']}/{uw[0]['n']} = {p3(uw[0]['p'])} | {uw[1]['k']}/{uw[1]['n']} = {p3(uw[1]['p'])} |",
    )
    src = (
        rep["reference_sources"]["metadiscourse"]["STRICT"],
        rep["reference_sources"]["phrase"]["STRICT"],
    )
    ck.quote(
        T,
        "reference from A-B agreement",
        R,
        f"| STRICT reference from A–B agreement | {src[0].get('primaries', 0)} | {src[1].get('primaries', 0)} |",
    )
    ck.quote(
        T,
        "reference from the adjudicator",
        R,
        f"| STRICT reference from the adjudicator | {src[0].get('adjudicator', 0)} | {src[1].get('adjudicator', 0)} |",
    )
    ck.quote(
        T,
        "unresolved",
        R,
        f"| STRICT unresolved | {src[0].get('unresolved', 0)} | {src[1].get('unresolved', 0)} |",
    )
    ck.quote(
        T,
        "adjudicator needed for STRICT",
        R,
        f"| Adjudicator needed for STRICT (split, or a primary UNSURE) | {strict_needed(rep, 'metadiscourse')} | {strict_needed(rep, 'phrase')} |",
    )
    adj = rep["adjudication"]
    ck.quote(
        T,
        "all-outcome adjudication requests",
        R,
        f"| All-outcome adjudication requests | {adj['metadiscourse']['needed']} | {adj['phrase']['needed']} |",
    )
    ag = (
        rep["agreement_pairs"]["metadiscourse"]["A vs B"],
        rep["agreement_pairs"]["phrase"]["A vs B"],
    )

    def strict_ag(x: dict) -> str:
        s = x["strict"]
        k = round(s["agreement"] * s["n"])
        return f"{k}/{s['n']} = {p3(s['agreement'])}, κ {k2(s['kappa'])}"

    ck.quote(
        T,
        "A-B STRICT agreement",
        R,
        f"| A–B STRICT agreement | {strict_ag(ag[0])} | {strict_ag(ag[1])} |",
    )
    ck.quote(
        T,
        "A-B full-label agreement",
        R,
        f"| A–B full-label agreement | {p3(ag[0]['labels']['agreement'])}, κ {k2(ag[0]['labels']['kappa'])} | {p3(ag[1]['labels']['agreement'])}, κ {k2(ag[1]['labels']['kappa'])} |",
    )
    per = {}
    for m in ("metadiscourse", "phrase"):
        ids = [r["id"] for r in run["key"] if r["module"] == m and r["id"] in set(c.expected)]
        per[m] = (sum(i not in c.labels for i in ids), sum(c.label(i) == "UNSURE" for i in ids))
    ck.quote(
        T,
        "adjudicator missing or invalid / UNSURE",
        R,
        f"| Adjudicator missing or invalid records / valid UNSURE records | {per['metadiscourse'][0]} / {per['metadiscourse'][1]} | {per['phrase'][0]} / {per['phrase'][1]} |",
    )
    ck.quote(
        T,
        "pooled requests",
        R,
        f"Pooled over both modules there were {len(c.expected)} adjudication requests, of which the adjudicator answered {nu_c} UNSURE.",
    )
    lo, hi = md["bounds_unresolved_wrong_right"]
    ck.quote(
        T, "unresolved bounds", R, f"Its bounds on the weighted estimate are [{p5(lo)}, {p5(hi)}]."
    )
    fd = flash_diagnostics(ex, run)
    cs = fd["change_status_counts"]
    newc = cs.get("metadiscourse|new_or_changed", 0) + cs.get("phrase|new_or_changed", 0)
    new_adj = sum(1 for g in fd["flash_by_module_change"] if g.endswith("new_or_changed"))
    ck.quote(
        T,
        "change status",
        R,
        f"{cs['metadiscourse|unchanged']} metadiscourse items and {cs['phrase|unchanged']} PHRASE items are unchanged; {cs.get('metadiscourse|new_or_changed', 0)} and {cs.get('phrase|new_or_changed', 0)} are new or changed."
        + (f" None of the {newc} new or changed items needed adjudication." if not new_adj else ""),
    )
    for g, v in fd["flash_by_module_change"].items():
        mod, st = g.split("|")
        ck.quote(
            T,
            f"adjudicator diagnostics {g}",
            R,
            f"| {mod}, {st.replace('_', ' ')} | {v['requests']} | {v['valid']} | {v['unsure']} | {v['agree_A']}/{v['strict_pairs_A']} | {v['agree_B']}/{v['strict_pairs_B']} |",
        )
    ck.quote(
        T,
        "simulation p_target",
        R,
        f"**`p_target`** is {p3(md['p'])} for metadiscourse and {p3(ph['p'])} for PHRASE",
    )
    ck.quote(
        T,
        "simulation adjudication share",
        R,
        f"**Adjudication share:** {strict_needed(rep, 'metadiscourse')}/{n(md['n_items'])} and {strict_needed(rep, 'phrase')}/{ph['n_items']}.",
    )
    ck.quote(
        T,
        "simulation non-resolution (metadiscourse)",
        R,
        f"for metadiscourse, the observed {src[0].get('unresolved', 0)}/{n(md['n_items'])};",
    )
    ck.quote(
        T,
        "simulation non-resolution (PHRASE)",
        R,
        f"({strict_needed(rep, 'phrase')}/{ph['n_items']}) × ({nu_c}/{len(c.expected)})",
    )
    ck.quote(
        T,
        "A-B STRICT agreement in the prereg",
        PREREG,
        f"({p3(ag[0]['strict']['agreement'])} and {p3(ag[1]['strict']['agreement'])};",
    )


def target_pilot032(ex: Export, ck: Checks, tmp: Path) -> None:
    T = "2 pilot032"
    run = run_pilot(ex, "pilot032", tmp)
    rep, c = run["report"], run["sets"]["adjudicator"]
    md, ph = strict_all(rep, "metadiscourse"), strict_all(rep, "phrase")
    ck.add(T, "A's merged file = merge_retry(original, retry, manifest ids)", run["merge_ok"])
    ck.add(T, "adjudicator assignment = needs_adjudication(A, B)", run["need_ok"])
    un = {
        m: rep["reference_sources"][m]["STRICT"].get("unresolved", 0)
        for m in ("metadiscourse", "phrase")
    }
    need = {m: strict_needed(rep, m) for m in ("metadiscourse", "phrase")}
    nu = sum(c.label(i) == "UNSURE" for i in c.expected)
    req = len(c.expected)
    ck.quote(T, "history line", RESULTS,
             f"It had metadiscourse at {p3(md['p'])} weighted and {p3(md['unweighted']['p'])} unweighted, with {need['metadiscourse']} adjudicated and {un['metadiscourse']} unresolved, and PHRASE at {p3(ph['p'])} weighted and {p3(ph['unweighted']['p'])} unweighted, with {need['phrase']} adjudicated and {un['phrase']} unresolved. It had {req} requests, {nu} of them UNSURE.")  # fmt: skip
    ck.quote(
        T,
        "prereg: history",
        PREREG,
        f"unweighted STRICT precision {p3(md['unweighted']['p'])} metadiscourse and {p3(ph['unweighted']['p'])} PHRASE, and design-weighted estimates {p3(md['p'])} and {p3(ph['p'])}",
    )
    ck.quote(T, "prereg: simulation parameters", PREREG,
             f"The 0.3.2 pilot's parameters were {p3(md['p'])} and {p3(ph['p'])} (precision), {need['metadiscourse']}/{n(md['n_items'])} and {need['phrase']}/{ph['n_items']} (adjudicator needed), and {un['metadiscourse']}/{n(md['n_items'])} and ({need['phrase']}/{ph['n_items']}) × ({nu}/{req}) (unresolved).")  # fmt: skip
    words = {1: "one", 2: "two", 3: "three"}.get(nu, str(nu))
    ck.quote(
        T,
        "prereg: adjudicator UNSURE among requests",
        PREREG,
        f"{words} UNSURE responses among its {req} adjudication requests",
    )
    ag = (
        rep["agreement_pairs"]["metadiscourse"]["A vs B"]["strict"],
        rep["agreement_pairs"]["phrase"]["A vs B"]["strict"],
    )
    ck.quote(
        T,
        "prereg: A-B STRICT agreement",
        PREREG,
        f"it was {p3(ag[0]['agreement'])} and {p3(ag[1]['agreement'])} in the 0.3.2 pilot",
    )
    ck.add(
        T,
        "full-precision weighted estimates (not published to 5 places; informational)",
        True,
        f"metadiscourse {md['p']!r}, PHRASE {ph['p']!r}",
    )


def gate(ex: Export, rnd: int, tmp: Path, roles: dict[str, str]) -> dict[str, Any]:
    """fixcheck.accept.acceptance_of on the round's shadow package."""
    folder = f"fixcheck/round{rnd}"
    d = tmp / f"round{rnd}-{'-'.join(roles.values())}"
    _, _, pseudo = shadow_items(ex, folder)
    assign, sample = d / "assign", d / "sample"
    write_lines(assign / "items.jsonl", [C.dump_line(it) for it in pseudo])
    write_lines(assign / "key.jsonl", ex.lines(f"{folder}/key.jsonl.gz"))
    write_lines(assign / "flash" / "flash_ids.txt", ex.ids(f"{folder}/flash_ids.txt"))
    sample.mkdir(parents=True, exist_ok=True)
    (sample / "selection.json").write_bytes(ex.p(f"{folder}/selection.json").read_bytes())
    lab = {
        r: write_lines(d / "labels" / f"{r}.jsonl", synth(ex, f"{folder}/labels/{r}.jsonl.gz"))
        for r in ("A", "B", "adjudicator")
    }
    files = {slot: lab[src] for slot, src in roles.items()}
    res = accept.acceptance_of(
        assign, sample, files, lab["adjudicator"], rnd, [], flash_dir=assign / "flash"
    )
    res = norm(res)
    for slot, src in [*roles.items(), ("adjudicator", "adjudicator")]:
        s = ex.source(f"{folder}/labels/{src}.jsonl.gz")
        res["labels"][slot]["file"] = s["path"]
        res["labels"][slot]["sha256"] = s["sha256"]
    return res


SUBSTRATUM = re.compile(r"[^|]+\|(rest|marker=.*)")


def _keys(o: Any, out: set[str]) -> set[str]:
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(o, list):
        for v in o:
            _keys(v, out)
    return out


def align_substrata(got: dict, pub: dict) -> tuple[dict[str, str] | None, str]:
    """Published sub-stratum names -> the export's codes, paired in sort order.

    The codes preserve the sort order of the original names, so the k-th published name
    is the k-th code. Each pair must have the same stratum and the same kind (rest or
    marker); everything attached to the names (N_h, n_h, k) is then compared exactly."""
    gk = sorted(k for k in _keys(got, set()) if SUBSTRATUM.fullmatch(k))
    pk = sorted(k for k in _keys(pub, set()) if SUBSTRATUM.fullmatch(k))
    if len(gk) != len(pk):
        return None, f"{len(pk)} published sub-strata, {len(gk)} recomputed"
    for p, g in zip(pk, gk, strict=True):
        if p.split("|")[0] != g.split("|")[0] or p.endswith("|rest") != g.endswith("|rest"):
            return None, "sort-order pairing breaks stratum or kind"
    m = dict(zip(pk, gk, strict=True))
    return m, f"{len(m)} sub-strata paired ({sum(p != g for p, g in m.items())} coded)"


def rename(o: Any, m: dict[str, str]) -> Any:
    if isinstance(o, dict):
        return {m.get(k, k): rename(v, m) for k, v in o.items()}
    if isinstance(o, list):
        return [rename(v, m) for v in o]
    return m.get(o, o) if isinstance(o, str) else o


def compare_acceptance(
    ck: Checks, T: str, what: str, got: dict, pub: dict, fields: list[str] | None = None
) -> None:
    fields = fields or sorted(pub)
    mapping, how = align_substrata({k: got[k] for k in fields}, {k: pub[k] for k in fields})
    ck.add(T, f"{what}: sub-stratum names paired with the export's codes", mapping is not None, how)
    pub = rename(pub, mapping or {})
    for slot in ("A", "B", "adjudicator"):
        g, p = got["labels"][slot], pub["labels"][slot]
        ck.add(
            T,
            f"{what}: labels.{slot} file and SHA-256 = the export's source",
            g["sha256"] == p["sha256"] and p["file"].endswith(g["file"]),
            f"{g['sha256'][:16]}… {g['file']}",
        )
    g = {k: got[k] for k in fields}
    p = {k: pub[k] for k in fields}
    for x in (g, p):
        x["labels"] = {
            s: {k: v for k, v in d.items() if k not in ("file", "sha256")}
            if isinstance(d, dict)
            else d
            for s, d in x["labels"].items()
        }
    ck.equal(T, f"{what}: {', '.join(fields)}", g, p)
    ck.add(
        T,
        f"{what}: status",
        got["status"] == pub["status"],
        f"{got['status']} (published {pub['status']})",
    )


def target_gates(ex: Export, ck: Checks, tmp: Path) -> None:
    T = "3 gates"
    for rnd in (1, 2):
        pub = json.loads((FIX / f"round{rnd}" / "accept" / "acceptance.json").read_text())
        got = gate(ex, rnd, tmp, {"A": "A", "B": "B"})
        fields = sorted(set(pub) - set(PACKAGE_FIELDS))
        compare_acceptance(ck, T, f"round {rnd} acceptance.json", got, pub, fields)
        ck.add(
            T,
            f"round {rnd}: package fields not recomputed (need the full package)",
            True,
            ", ".join(PACKAGE_FIELDS),
        )


def target_sensitivity(ex: Export, ck: Checks, tmp: Path) -> None:
    T = "4 sensitivity"
    sens = FIX / "round2" / "sensitivity"
    sums = dict(
        reversed(line.split("  ", 1))
        for line in (sens / "SHA256SUMS").read_text().splitlines()
        if line.strip()
    )
    for name in ("S-B_acceptance.json", "control_acceptance.json"):
        ck.add(
            T, f"{name} matches the folder's SHA256SUMS", C.sha256_file(sens / name) == sums[name]
        )
    for name, roles in (
        ("control_acceptance.json", {"A": "A", "B": "B"}),
        ("S-B_acceptance.json", {"A": "B", "B": "B"}),
    ):
        pub = json.loads((sens / name).read_text())
        compare_acceptance(ck, T, name, gate(ex, 2, tmp, roles), pub)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--export", type=Path, default=EXPORT)
    ap.add_argument("--json", type=Path, help="write the full comparison here")
    args = ap.parse_args(argv)
    ex = Export(args.export.resolve())
    ck = Checks()
    probs = ex.integrity()
    ck.add("0 export", "SHA256SUMS covers and matches every file", not probs, "; ".join(probs[:5]))
    with tempfile.TemporaryDirectory(prefix="s4textfree-") as t:
        tmp = Path(t)
        target_pilot040(ex, ck, tmp)
        target_pilot032(ex, ck, tmp)
        target_gates(ex, ck, tmp)
        target_sensitivity(ex, ck, tmp)
    bad = [r for r in ck.rows if not r["ok"]]
    for r in ck.rows:
        print(
            f"{'ok  ' if r['ok'] else 'FAIL'} [{r['target']}] {r['check']}"
            + (f" — {r['detail']}" if r["detail"] else "")
        )
    print(f"\n{len(ck.rows)} checks; {len(bad)} failed")
    if args.json:
        args.json.write_text(
            json.dumps({"checks": ck.rows, "failed": len(bad)}, ensure_ascii=False, indent=1)
            + "\n",
            encoding="utf-8",
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
