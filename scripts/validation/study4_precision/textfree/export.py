"""Build the text-free Study 4 export (docs/validation/study4-textfree/) from the private files.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/export.py
    uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/export.py --check

Reads (read-only) ~/lexinspect-private/study4-pilot040/, ~/lexinspect-private/study4-fix040/
round{1,2}/ and .cache/validation/{study4,study4_pilot,study4_scratch/dev032}/. Writes only
the export folder. Deterministic: --check rebuilds every file in memory and compares it byte
for byte with the folder (exit 1 on any difference). Before anything is written, every
label file is proved equivalent under the frozen validator (common.verify_labels) and the
whole export passes guard.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import analyse
import common as C
import guard

REPO = HERE.parents[3]
HOME = Path.home()
PRIVATE = HOME / "lexinspect-private"
P040 = PRIVATE / "study4-pilot040"
FIX = PRIVATE / "study4-fix040"
CACHE = REPO / ".cache" / "validation"
OUT = REPO / "docs" / "validation" / "study4-textfree"

PILOT_KEY_FIELDS = (
    "id",
    "module",
    "text_id",
    "register",
    "discipline",
    "source_id",
    "span",
    "sentence_span",
    "token_index",
    "stratum",
    "substratum",
    "N_sub",
    "n_sub",
    "weight",
    "provenance",
    "category",
    "dimension",
    "also_listed_as",
    "rank",
    "k_band",
    "multi_sense",
    "has_also_possible",
    "in_maintainer_sample",
    "m_sub",
)
ROUND_KEY_FIELDS = ("id", "module", "category", "payload_sha256", "memberships", "occurrences")
MEMBERSHIP_FIELDS = {"frame", "inclusion", "role", "row", "substratum", "of", "resolved"}
TEXT_FIELDS = (
    "text_id",
    "register",
    "discipline",
    "source",
    "source_id",
    "doi",
    "url",
    "fulltext_url",
    "revid",
    "rev_timestamp",
    "licence",
    "retrieved",
    "truncated",
    "n_chars",
    "year",
    "text_sha256",
    "extracted_sha256",
    "fixcheck_round",
)
# Published SHA-256 of private files that the export copies or projects (RESULTS.md).
PUBLISHED = {
    P040
    / "analysis"
    / "pilot.json": "f3aa1dd84cff957a2272fba354e4fa055cc5ff178eb235700ff261d99b8d24b4",
    P040
    / "analysis"
    / "flash_diagnostics.json": "e3d2d90dbb6673fd386b4c36a5b94a5963dbd532972e6b8e139342568a953d38",
}


def disp(p: Path) -> str:
    p = Path(p)
    for root, name in ((REPO, ""), (PRIVATE, "lexinspect-private/")):
        try:
            return name + p.relative_to(root).as_posix()
        except ValueError:
            pass
    return str(p)


def raw_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in raw_lines(p) if x.strip()]


def id_list(p: Path) -> list[str]:
    return analyse.read_id_file(p)


class Export:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.meta: dict[str, dict[str, Any]] = {}

    def add(self, rel: str, data: bytes, sources: list[Path], what: str, **extra: Any) -> None:
        if rel in self.files:
            raise ValueError(f"{rel} written twice")
        self.files[rel] = C.gz(data) if rel.endswith(".gz") else data
        self.meta[rel] = {
            "what": what,
            "derived_from": [{"path": disp(s), "sha256": C.sha256_file(s)} for s in sources],
            **extra,
        }

    def add_jsonl(self, rel: str, lines: list[str], sources: list[Path], what: str, **e) -> None:
        self.add(rel, C.dump_jsonl(lines), sources, what, lines=len(lines), **e)


# --- datasets ---------------------------------------------------------------------------------


def pilot_sources(name: str) -> dict[str, Any]:
    if name == "pilot032":
        d, p = CACHE / "study4", CACHE / "study4_pilot"
        return {
            "key": d / "key.jsonl",
            "items": d / "items.jsonl",
            "frame": CACHE / "study4_scratch" / "dev032" / "frame.json",
            "frame_key": CACHE / "study4_scratch" / "dev032" / "key.jsonl",
            "orders": p / "orders.json",
            "maintainer_ids": d / "human_sample_ids.txt",
            "labels": {
                "A_original": p / "labels_A_original.jsonl",
                "A_retry": p / "raw" / "A_retry.jsonl",
                "A": p / "labels_A.jsonl",
                "B": p / "labels_B.jsonl",
                "adjudicator": p / "raw" / "DSF2_flash.jsonl",
            },
            "retry_manifest": p / "retry_A_manifest.jsonl",
            "needs_adjudication": p / "needs_adjudication.txt",
        }
    b, lab = P040 / "selection" / "build", P040 / "labels"
    return {
        "key": b / "key.jsonl",
        "items": b / "items.jsonl",
        "frame": b / "frame.json",
        "orders": b / "orders.json",
        "maintainer_ids": b / "human_sample_ids.txt",
        "labels": {
            "A_original": lab / "A_batch.jsonl",
            "A_retry": lab / "A_retry.jsonl",
            "A": lab / "A_merged.jsonl",
            "B": lab / "B_batch.jsonl",
            "adjudicator": lab / "adjudicator_adjudication.jsonl",
        },
        "retry_manifest": lab / "A_batch_retry.jsonl",
        "needs_adjudication": lab / "needs_adjudication.txt",
    }


def round_sources(rnd: int) -> dict[str, Any]:
    r = FIX / f"round{rnd}"
    return {
        "key": r / "assign" / "key.jsonl",
        "items": r / "assign" / "items.jsonl",
        "selection": r / "sample" / "selection.json",
        "flash_ids": r / "assign" / "flash" / "flash_ids.txt",
        "labels": {role: r / "labels" / f"{role}.jsonl" for role in ("A", "B", "adjudicator")},
        "texts": REPO
        / "docs"
        / "validation"
        / "study4-fix040"
        / f"round{rnd}"
        / "collect"
        / "texts.jsonl",
        "collect_manifest": REPO
        / "docs"
        / "validation"
        / "study4-fix040"
        / f"round{rnd}"
        / "collect"
        / "manifest_collect.json",
    }


def all_substrata() -> set[str]:
    names: set[str] = set()
    for name in ("pilot032", "pilot040"):
        s = pilot_sources(name)
        names |= {r["substratum"] for r in read_jsonl(s["key"])}
        for fm in json.loads(s["frame"].read_text())["modules"].values():
            names |= set(fm)
    for rnd in (1, 2):
        s = round_sources(rnd)
        for k in read_jsonl(s["key"]):
            names |= {mb["substratum"] for mb in k["memberships"] if "substratum" in mb}
        for st in json.loads(s["selection"].read_text())["baseline_success"]["strata"].values():
            names |= set(st)
    return names


def export_labels(
    ex: Export,
    folder: str,
    files: dict[str, Path],
    items: dict[str, dict[str, Any]],
    expected: dict[str, list[str] | None],
) -> dict[str, list[str]]:
    """Shapes of every label file of one dataset (one registry), each proved equivalent."""
    pseudo = {i: C.pseudo_item(C.item_shape(it)) for i, it in items.items()}
    reg = C.Registry()
    real = {role: raw_lines(p) for role, p in files.items()}
    for lines in real.values():
        C.encode_file(lines, items, reg)
    reg.freeze()
    shapes = {}
    for role, p in files.items():
        shapes[role] = C.encode_file(real[role], items, reg)
        summary = C.verify_labels(real[role], shapes[role], items, pseudo, expected[role], role)
        ex.add_jsonl(
            f"{folder}/labels/{role}.jsonl.gz",
            shapes[role],
            [p],
            f"label shapes of role {role} (one line per line of the source file)",
            validator_summary=summary,
            expected_ids="all items" if expected[role] is None else len(expected[role]),
        )
    return shapes


def export_pilot(ex: Export, name: str, codes: C.SubstratumCodes) -> None:
    s = pilot_sources(name)
    key = read_jsonl(s["key"])
    items_list = read_jsonl(s["items"])
    items = {it["id"]: it for it in items_list}
    frame = json.loads(s["frame"].read_text())
    if "frame_key" in s and C.sha256_file(s["frame_key"]) != C.sha256_file(s["key"]):
        raise ValueError(f"{name}: the frame's key is not the pilot's key")
    orders = json.loads(s["orders"].read_text())
    mids = id_list(s["maintainer_ids"])
    problems = analyse.validate_design(key, items_list, mids, orders, frame)
    if problems:
        raise ValueError(f"{name}: design problems {problems[:3]}")
    dropped = sorted({f for r in key for f in r} - set(PILOT_KEY_FIELDS))
    rows = [
        {f: (codes(r[f]) if f == "substratum" else r[f]) for f in PILOT_KEY_FIELDS if f in r}
        for r in key
    ]
    ex.add_jsonl(
        f"{name}/key.jsonl.gz",
        [C.dump_line(r) for r in rows],
        [s["key"]],
        "sampled items: strata, weights, text identity and offsets (analyse.py key)",
        dropped_fields=dropped,
    )
    ex.add_jsonl(
        f"{name}/items.jsonl.gz",
        [C.dump_line(C.item_shape(it)) for it in items_list],
        [s["items"]],
        "item shapes: module and claimed category, or PHRASE word counts (no text)",
    )
    fr = dict(frame, modules={m: codes.replace_in(fm) for m, fm in frame["modules"].items()})
    ex.add(
        f"{name}/frame.json",
        C.dump_json(fr),
        [s["frame"]],
        "N_h and register counts per sub-stratum",
    )
    ex.add(
        f"{name}/orders.json",
        C.dump_json({k: v for k, v in orders.items() if k != "note"}),
        [s["orders"]],
        "labelling orders and batch sizes per role (the descriptive 'note' string dropped)",
    )
    ex.add(
        f"{name}/maintainer_sample_ids.txt",
        "".join(i + "\n" for i in mids).encode(),
        [s["maintainer_ids"]],
        "maintainer audit-sample ids (no maintainer labels exist)",
    )
    # Labels. Expected ids as analyse.main sets them: all items for A and B; the adjudicator's
    # from needs_adjudication on the final primaries.
    lab = s["labels"]
    prim = [analyse.load_labels(lab[r], items, None, r) for r in ("A", "B")]
    need = analyse.needs_adjudication(key, prim)
    if need != id_list(s["needs_adjudication"]):
        raise ValueError(f"{name}: needs_adjudication differs from the archived list")
    retry_ids = id_list(s["retry_manifest"])
    merged, notes = analyse.merge_retry(
        raw_lines(lab["A_original"]), raw_lines(lab["A_retry"]), retry_ids
    )
    if [x for x in merged if x.strip()] != [x for x in raw_lines(lab["A"]) if x.strip()] or notes:
        raise ValueError(f"{name}: the merged A file is not merge_retry(original, retry)")
    expected = {"A_original": None, "A_retry": retry_ids, "A": None, "B": None, "adjudicator": need}
    export_labels(ex, name, lab, items, expected)
    ex.add(
        f"{name}/labels/A_retry_ids.txt",
        "".join(i + "\n" for i in retry_ids).encode(),
        [s["retry_manifest"]],
        "ids of A's retry manifest (reasons and details dropped)",
    )
    ex.add(
        f"{name}/labels/needs_adjudication.txt",
        s["needs_adjudication"].read_bytes(),
        [s["needs_adjudication"]],
        "the adjudicator's assignment (analyse.needs_adjudication)",
    )


def export_pilot040_extras(ex: Export, codes: C.SubstratumCodes) -> None:
    for p, h in PUBLISHED.items():
        if C.sha256_file(p) != h:
            raise ValueError(f"{disp(p)} does not match its published SHA-256")
    rep = json.loads((P040 / "analysis" / "pilot.json").read_text())
    for ls in rep["alt_categories"].values():
        ls.pop("phrase", None)
    ex.add(
        "pilot040/reference/pilot_textfree.json",
        C.dump_json(codes.replace_in(rep)),
        [P040 / "analysis" / "pilot.json"],
        "analysis/pilot.json with alt_categories.<role>.phrase removed (PHRASE wording) and "
        "sub-stratum names coded; everything else unchanged",
    )
    fd = P040 / "analysis" / "flash_diagnostics.json"
    ex.add(
        "pilot040/reference/flash_diagnostics.json",
        fd.read_bytes(),
        [fd],
        "byte copy (text-free; SHA-256 published in RESULTS.md)",
    )
    hits = CACHE / "study4" / "hits.jsonl"
    out = []
    for h in read_jsonl(hits):
        claim = (
            {"category": h["category"]} if h["module"] == "metadiscourse" else {"rank": h["rank"]}
        )
        out.append(
            C.dump_line(
                {"module": h["module"], "text_id": h["text_id"], "span": h["span"], **claim}
            )
        )
    ex.add_jsonl(
        "pilot040/dev032_hits.jsonl.gz",
        out,
        [hits],
        "identity of every 0.3.2 development hit: module, text, span, claim (category or PHRASE rank)",
    )


def export_round(ex: Export, rnd: int, codes: C.SubstratumCodes) -> None:
    s = round_sources(rnd)
    name = f"fixcheck/round{rnd}"
    key = read_jsonl(s["key"])
    rows = []
    for k in key:
        extra = set(k) - set(ROUND_KEY_FIELDS)
        if extra:
            raise ValueError(f"{name}: unexpected key fields {sorted(extra)}")
        mbs = []
        for mb in k["memberships"]:
            if set(mb) - MEMBERSHIP_FIELDS:
                raise ValueError(
                    f"{name}: unexpected membership fields {sorted(set(mb) - MEMBERSHIP_FIELDS)}"
                )
            mbs.append({f: (codes(v) if f == "substratum" else v) for f, v in mb.items()})
        for o in k["occurrences"]:
            ok = (
                len(o) == 5
                and isinstance(o[0], str)
                and isinstance(o[1], str)
                and len(o[1]) == 64
                and o[2] in analyse.LABELS
                and all(isinstance(x, int) for x in o[3:])
            )
            if not ok:
                raise ValueError(f"{name}: unexpected occurrence form")
        rows.append(dict(k, memberships=mbs))
    ex.add_jsonl(
        f"{name}/key.jsonl.gz",
        [C.dump_line(r) for r in rows],
        [s["key"]],
        "one line per label unit: payload hash, claim code, frame memberships and occurrence locators (source id, text SHA-256, module, offsets)",
    )
    items_list = read_jsonl(s["items"])
    items = {it["id"]: it for it in items_list}
    ex.add_jsonl(
        f"{name}/items.jsonl.gz",
        [C.dump_line(C.item_shape(it)) for it in items_list],
        [s["items"]],
        "item shapes (no text)",
    )
    sel = json.loads(s["selection"].read_text())
    ex.add(
        f"{name}/selection.json",
        C.dump_json(codes.replace_in(sel)),
        [s["selection"]],
        "frame sizes, SRS selections and the baseline-success strata (sub-stratum names coded)",
    )
    fids = id_list(s["flash_ids"])
    ex.add(
        f"{name}/flash_ids.txt",
        s["flash_ids"].read_bytes(),
        [s["flash_ids"]],
        "the adjudicator's assignment",
    )
    export_labels(ex, name, s["labels"], items, {"A": None, "B": None, "adjudicator": fids})


def export_texts(ex: Export) -> None:
    dev = CACHE / "study4" / "texts.jsonl"
    sums = P040 / "selection" / "build" / "SHA256SUMS"
    archived = {
        line.split()[1].removeprefix("./texts/").removesuffix(".txt"): line.split()[0]
        for line in raw_lines(sums)
        if line.split()[1].startswith("./texts/")
    }
    rows, srcs = [], [dev, sums]
    for t in read_jsonl(dev):
        p = CACHE / "study4" / "texts" / f"{t['text_id']}.txt"
        h = C.sha256_file(p)
        if archived.get(t["text_id"]) != h:
            raise ValueError(f"{t['text_id']}: cache copy differs from the archived 0.4.0 copy")
        rows.append(C.dump_line({f: t[f] for f in TEXT_FIELDS if f in t} | {"text_sha256": h}))
    ex.add_jsonl(
        "texts/development.jsonl",
        rows,
        srcs,
        "the 120 development texts: identifiers, licence, length and SHA-256 of the archived text (no title, authors or journal)",
    )
    for rnd in (1, 2):
        src = round_sources(rnd)["texts"]
        man = json.loads(round_sources(rnd)["collect_manifest"].read_text())["outputs"]
        if man["texts.jsonl"]["sha256"] != C.sha256_file(src):
            raise ValueError(f"round {rnd}: texts.jsonl differs from manifest_collect.json")
        rows = [C.dump_line({f: t[f] for f in TEXT_FIELDS if f in t}) for t in read_jsonl(src)]
        srcs = [src, round_sources(rnd)["collect_manifest"]]
        ex.add_jsonl(
            f"texts/round{rnd}.jsonl", rows, srcs, f"the 60 fix-check round-{rnd} texts (as above)"
        )


def build(readme: bytes | None) -> dict[str, bytes]:
    codes = C.SubstratumCodes(all_substrata())
    ex = Export()
    export_texts(ex)
    for name in ("pilot032", "pilot040"):
        export_pilot(ex, name, codes)
    export_pilot040_extras(ex, codes)
    for rnd in (1, 2):
        export_round(ex, rnd, codes)
    manifest = {
        "format": "study4-textfree/1",
        "generator": "scripts/validation/study4_precision/textfree/export.py",
        "substratum_codes": {
            "scheme": "<stratum>|rest kept; <stratum>|marker=<words> -> <stratum>|marker=m<NNN>, "
            "numbered in the sorted order of all original names (one numbering for every "
            "dataset); the mapping is not published",
            "n_names": len(codes.names),
            "n_coded": sum(1 for n in codes.names if codes(n) != n),
        },
        "label_shapes": "see scripts/validation/study4_precision/textfree/common.py",
        "files": {
            rel: dict(m, bytes=len(ex.files[rel]), sha256=C.sha256_bytes(ex.files[rel]))
            for rel, m in sorted(ex.meta.items())
        },
    }
    files = dict(ex.files)
    files["manifest.json"] = C.dump_json(manifest)
    if readme is not None:
        files["README.md"] = readme
    sums = "".join(f"{C.sha256_bytes(files[r])}  {r}\n" for r in sorted(files))
    files["SHA256SUMS"] = sums.encode()
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="rebuild in memory; compare byte for byte")
    ap.add_argument("--no-guard", action="store_true", help="skip guard.py (tests only)")
    args = ap.parse_args(argv)
    readme_p = args.out / "README.md"
    files = build(readme_p.read_bytes() if readme_p.exists() else None)
    if not args.no_guard:
        res = guard.scan_files(files, guard.default_corpora())
        print(guard.report(res))
        if not res["ok"]:
            print("export refused: the guard found text", file=sys.stderr)
            return 1
    if args.check:
        on_disk = {p.relative_to(args.out).as_posix() for p in args.out.rglob("*") if p.is_file()}
        bad = sorted(
            r
            for r in files
            if not (args.out / r).is_file() or (args.out / r).read_bytes() != files[r]
        )
        extra = sorted(on_disk - set(files))
        for r in bad:
            print(f"DIFFERS: {r}")
        for r in extra:
            print(f"EXTRA: {r}")
        print(f"check: {len(files)} files rebuilt; {len(bad)} differ; {len(extra)} extra")
        return 1 if bad or extra else 0
    for r, data in files.items():
        p = args.out / r
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    total = sum(len(d) for d in files.values())
    print(f"wrote {len(files)} files, {total:,} bytes -> {disp(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
