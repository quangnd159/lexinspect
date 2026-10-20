"""Write inventory.json, the final machine inventory of the frozen exclusion file.

Every count is recomputed from the files with build.py's own readers. The v1
inventory (the 909-record file before the page-id aliases) is kept byte for byte
as inventory_v1_historical.json; this script only reads it.

    uv run --offline --no-sync python -I docs/validation/study4-exclusions/tools/final_inventory.py
    uv run --offline --no-sync python -I docs/validation/study4-exclusions/tools/final_inventory.py --check

--check rebuilds the inventory in memory and exits 1 unless inventory.json is
byte-identical to it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

E = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts/validation/study4_precision"))
import build  # noqa: E402

FROZEN = E / "exclusions.jsonl"
V1 = E / "exclusions_v1_before_pageids.jsonl"
V1_INVENTORY = E / "inventory_v1_historical.json"
V1_INVENTORY_SHA256 = "118ff3dc4417eb74b569b0497be1d4a24ed4d218f7b217cf4c6a5c42f356d58a"
LOOKUP = E / "pageid_lookup"
OUT = E / "inventory.json"
ROUNDS = REPO / "docs/validation/study4-fix040"
SEED = 3195330621
COMMAND = (
    "uv run --offline --no-sync python -I scripts/validation/study4_precision/build.py "
    f"--set evaluation --seed {SEED} --out .cache/validation/study4_eval "
    "--raw-cache .cache/validation/study4_eval/raw "
    "--exclude-texts docs/validation/study4-exclusions/exclusions.jsonl"
)
CLASSES = {
    "labelled_texts": (
        "development_selected",
        "fixcheck_round1_selected",
        "fixcheck_round2_selected",
    ),
    "fetched_then_rejected_candidates": (
        "development_fetched_rejected",
        "fixcheck_round1_fetched_rejected",
        "fixcheck_round2_fetched_rejected",
    ),
    "study3_texts": ("study3_equivalence",),
    "study1_clear_excerpts": ("study1_clear_excerpt",),
}
ADDENDUM = "README.md, 'Addendum, 2026-10-21: page ids, and the decisions on the open questions'"
# Each v1 open question (by index in inventory_v1_historical.json) and its dated
# resolution. Quotes are verbatim from the README (bold markers dropped); --check
# fails if one is no longer in the README.
DECISIONS = [
    {
        "v1_open_question": 0,
        "topic": "Study 1 CLEAR excerpts",
        "decision": "kept (excluded)",
        "date": "2026-10-21",
        "source": f"{ADDENDUM}, decision 1",
        "quote": "The Study 1 CLEAR excerpts stay excluded. They were never used in Study 4 development, "
        "but excluding them costs little: about 800 eligible Level-3 Vital titles remain for 40 general texts.",
    },
    {
        "v1_open_question": 1,
        "topic": "317 title-only English Wikipedia records",
        "decision": "resolved: page ids looked up and appended as 331 alias lines",
        "date": "2026-10-21",
        "source": f"{ADDENDUM}, 'Page ids'",
        "quote": "317 English Wikipedia records matched by title only. Their page ids were looked up "
        "through the public Wikipedia API on 2026-10-21.",
    },
    {
        "v1_open_question": 2,
        "topic": "Simple English Wikipedia titles",
        "decision": "kept unchanged (324 records, no revid, simplewiki: source ids); the README makes no "
        "separate dated decision, and the prereg adopts the recommendation",
        "date": None,
        "source": "README.md, 'Simple English Wikipedia'",
        "quote": "I recommend keeping these titles, to be conservative: Study 3 paired each Simple text with "
        "its English counterpart on the same topic, so the same title points at closely related content.",
    },
    {
        "v1_open_question": 3,
        "topic": "Fetched-then-rejected candidates",
        "decision": "kept (excluded)",
        "date": "2026-10-21",
        "source": f"{ADDENDUM}, decision 2",
        "quote": "The fetched-then-rejected candidates stay excluded. The registered exclusion rule covers "
        'every text "collected or inspected", and these were downloaded.',
    },
    {
        "v1_open_question": 4,
        "topic": "PMIDs and PMC version ids",
        "decision": "not matched; none are recorded locally",
        "date": "2026-10-21",
        "source": f"{ADDENDUM}, decision 3",
        "quote": "PMIDs: none are recorded locally, and `build.py` doesn't match on them. Europe PMC texts "
        "are matched on PMCID, both URLs, DOI and title.",
    },
    {
        "v1_open_question": 5,
        "topic": "Pool snapshot",
        "decision": "the 2026-10-16 snapshot, byte-copied into the evaluation cache, no --refresh",
        "date": "2026-10-21",
        "source": f"{ADDENDUM}, decision 4",
        "quote": "The pools: the evaluation build uses the 2026-10-16 pool snapshot. A byte copy of "
        "`.cache/validation/study4/raw` is made into the evaluation build's own cache, with no `--refresh`. "
        "The development cache is never written to. If the pools were ever refreshed, the overlap check "
        "would be rerun on the refreshed pools.",
    },
    {
        "v1_open_question": None,
        "topic": "Freeze (README open question 6; not in the v1 inventory)",
        "decision": "frozen: this file's frozen.sha256 is the hash recorded in the prereg and passed unchanged "
        "through --exclude-texts",
        "date": "2026-10-21",
        "source": "README.md, 'Open questions for the maintainer', 6",
        "quote": "Record this file's SHA-256 in the prereg and freeze file, and pass it unchanged through "
        "`--exclude-texts`. Any edit after a decision above means a new hash.",
    },
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.resolve().relative_to(REPO).as_posix()


def jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def inventory() -> dict:
    lines = FROZEN.read_text(encoding="utf-8").splitlines()
    kinds = Counter(
        "blank"
        if not s
        else "comment"
        if s.startswith("#")
        else "json"
        if s.startswith("{")
        else "alias"
        for s in (x.strip() for x in lines)
    )
    aliases = [x.strip() for x in lines if x.strip() and not x.strip().startswith(("#", "{"))]
    n_pageid = sum(bool(re.fullmatch(r"pageid:\d+", a)) for a in aliases)
    recs = [json.loads(x) for x in lines if x.strip().startswith("{")]
    v1_text = V1.read_text(encoding="utf-8")
    v1_recs = jsonl(V1)
    assert FROZEN.read_text(encoding="utf-8").startswith(v1_text.rstrip("\n") + "\n"), (
        "v1 is not a prefix"
    )
    assert recs == v1_recs, "the JSON records differ from v1"

    # the alias lines are exactly what add_pageids.py derives from v1 + lookup.json
    look = json.loads((LOOKUP / "lookup.json").read_text(encoding="utf-8"))
    have = {r["source_id"] for r in v1_recs if str(r.get("source_id", "")).startswith("pageid:")}
    titles = {t for r in v1_recs for t in r.get("all_titles", []) + [r.get("title") or ""]}
    want = set()
    for v in look["results"].values():
        if f"pageid:{v['pageid']}" not in have:
            want.add(f"pageid:{v['pageid']}")
        if v["resolved_title"] not in titles:
            want.add(v["resolved_title"])
    assert sorted(want) == aliases, "alias lines do not match lookup.json"
    renamed = sum(k != v["resolved_title"] for k, v in look["results"].items())

    extra = build.read_exclusions(FROZEN)
    v1_extra = build.read_exclusions(V1)
    dev, dev_info = build.load_dev_exclusions(build.DEV_TEXTS)
    union = extra | dev
    dev_texts = jsonl(build.DEV_TEXTS)

    # distinct sources: the development texts plus every record, keyed by source_id
    srcs: dict[str, dict] = {}
    for t in dev_texts:
        srcs.setdefault(t["source_id"], {"source": t["source"], "exp": set()})["exp"].add(
            "development_selected"
        )
    for r in recs:
        s = srcs.setdefault(r["source_id"], {"source": r["source"], "exp": set()})
        assert s["source"] == r["source"]
        s["exp"] |= set(r["exposure"])
    by_class = {}
    for k, exps in CLASSES.items():
        hit = [v for v in srcs.values() if v["exp"] & set(exps)]
        by_class[k] = {
            "total": len(hit),
            "by_source": dict(sorted(Counter(v["source"] for v in hit).items())),
        }
    labelled = {i for i, v in srcs.items() if v["exp"] & set(CLASSES["labelled_texts"])}
    rejected = {
        i for i, v in srcs.items() if v["exp"] & set(CLASSES["fetched_then_rejected_candidates"])
    }

    # self-check against the final file
    checked = Counter()
    fails = []
    sets = (
        [("development_manifest", dev_texts)]
        + [
            (f"fixcheck_{r}", jsonl(ROUNDS / r / "collect/texts.jsonl"))
            for r in ("round1", "round2")
        ]
        + [("union_record", recs)]
    )
    for name, texts in sets:
        for t in texts:
            checked[name] += 1
            if not build.exclusion_overlap([t], union) or not build.text_refs(t) <= union:
                fails.append(f"{name}:{t['source_id']}")
    fails += [f"alias:{a}" for a in aliases if build._norm_ref(a) not in union]

    tools = E / "tools"
    return {
        "purpose": "Final machine inventory of the frozen Study 4 evaluation exclusion file. exclusions.jsonl is "
        "the ADDITIONAL file for build.py --exclude-texts; build.py always excludes the canonical development "
        "manifest itself. This inventory supersedes the v1 inventory, which is retained unchanged as "
        "inventory_v1_historical.json.",
        "built": "2026-10-21",
        "built_by": f"{rel(Path(__file__))} (rerun with --check to verify)",
        "frozen": {
            "path": rel(FROZEN),
            "sha256": sha(FROZEN),
            "physical_lines": len(lines),
            "json_source_records": kinds["json"],
            "json_source_records_by_source": dict(
                sorted(Counter(r["source"] for r in recs).items())
            ),
            "plain_alias_lines": kinds["alias"],
            "plain_alias_lines_by_kind": {
                "pageid": n_pageid,
                "current_title_of_renamed_page": kinds["alias"] - n_pageid,
            },
            "comment_lines": kinds["comment"],
            "blank_lines": kinds["blank"],
            "note": "The JSON records are the v1 records byte for byte; the comment and alias lines follow them. "
            "Alias lines are extra identities of sources already in the records, not new sources.",
        },
        "n_normalised_identifiers": {
            "rule": "build.read_exclusions (build.text_refs for JSON lines, build._norm_ref for plain lines; "
            "# lines skipped) and build.load_dev_exclusions(build.DEV_TEXTS)",
            "additional_file": len(extra),
            "development_manifest": len(dev),
            "shared": len(extra & dev),
            "union": len(union),
            "added_by_alias_lines": len(extra - v1_extra),
        },
        "development_manifest": {
            "path": rel(build.DEV_TEXTS),
            "sha256": dev_info["sha256"],
            "n_texts": dev_info["n_texts"],
            "n_refs": dev_info["n_refs"],
        },
        "distinct_sources": {
            "total": len(srcs),
            "by_source": dict(sorted(Counter(v["source"] for v in srcs.values()).items())),
            "development_selected_only (excluded by build.py, not in the file)": sum(
                v["exp"] == {"development_selected"} for v in srcs.values()
            ),
            "in_exclusions_file": len(recs),
            "by_exposure_class": by_class,
            "labelled_and_rejected_overlap": len(labelled & rejected),
            "sources_with_more_than_one_exposure": sum(len(v["exp"]) > 1 for v in srcs.values()),
            "sources_by_exposure": dict(
                sorted(Counter(e for v in srcs.values() for e in v["exp"]).items())
            ),
        },
        "pageid_lookup": {
            "queried": look["queried"],
            "n_titles": look["n_titles"],
            "missing": look["missing"],
            "renamed": renamed,
            "files": {rel(p): sha(p) for p in sorted(LOOKUP.glob("*.json"))},
            "note": "lookup.json is the parsed result; batch_*.json are the raw Wikipedia API responses.",
        },
        "builders": {
            "files": {
                rel(p): sha(p) for p in sorted(tools.glob("*.py")) if p.name != Path(__file__).name
            },
            "order": [
                "tools/clear_wiki.py",
                "tools/build_union.py",
                "tools/inventory.py",
                "tools/add_pageids.py",
            ],
            "note": "clear_wiki.py, build_union.py and inventory.py built the v1 file and the v1 inventory; "
            "add_pageids.py appended the alias lines to make the frozen file. They are kept as run.",
            "lint_config": {
                "path": rel(tools / "ruff.toml"),
                "sha256": sha(tools / "ruff.toml"),
                "note": "Only excludes the *.py files in tools/ from ruff; it builds nothing and changes no output.",
            },
        },
        "self_check": {
            "rule": "for every development, fix-check and union record, build.exclusion_overlap([record], union) "
            "is non-empty and build.text_refs(record) is a subset of union; every alias line is in union",
            "records_checked": dict(checked),
            "aliases_checked": len(aliases),
            "failures": fails,
            "passed": not fails,
        },
        "evaluation_build": {
            "seed": SEED,
            "command": COMMAND,
            "source": "docs/validation/study4-preregistration.md, 'The evaluation build, as frozen at stage 1'",
        },
        "decisions": DECISIONS,
        "historical_v1": {
            "note": "Historical: the 909-record file and its inventory before the 2026-10-21 page-id aliases. "
            "Their counts and open questions are not current; see decisions.",
            "exclusions": {
                "path": rel(V1),
                "sha256": sha(V1),
                "physical_lines": len(v1_text.splitlines()),
                "json_source_records": len(v1_recs),
                "n_normalised_identifiers": len(v1_extra),
                "union_with_development": len(v1_extra | dev),
                "shared_with_development": len(v1_extra & dev),
            },
            "inventory": {
                "path": rel(V1_INVENTORY),
                "sha256": sha(V1_INVENTORY),
                "note": "Byte copy of the former inventory.json. Its output_files entry names the pre-freeze "
                "cache path .cache/validation/study4_eval_exclusions/exclusions.jsonl with the v1 hash; that "
                "file is the v1 file above. Its pool_impact, not_excluded, input_manifests and raw-cache "
                "listings still describe the sources, but pool_impact was computed before the alias lines.",
            },
        },
    }


def render() -> str:
    assert sha(V1_INVENTORY) == V1_INVENTORY_SHA256, "inventory_v1_historical.json has changed"
    readme = (E / "README.md").read_text(encoding="utf-8").replace("**", "")
    readme = re.sub(r"\s+", " ", readme)
    for d in DECISIONS:
        assert d["quote"] in readme, f"decision quote not in README: {d['topic']}"
    prereg = (REPO / "docs/validation/study4-preregistration.md").read_text(encoding="utf-8")
    assert sha(FROZEN) in prereg, "the prereg does not name the frozen file's hash"
    assert COMMAND in re.sub(r"\s*\\\n\s*", " ", prereg), "the prereg's evaluation command differs"
    return json.dumps(inventory(), indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--check", action="store_true", help="compare with inventory.json instead of writing it"
    )
    a = ap.parse_args()
    text = render()
    if a.check:
        if OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"{rel(OUT)} differs from the rebuilt inventory")
        print(f"{rel(OUT)} matches (sha256 {sha(OUT)})")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {rel(OUT)} (sha256 {sha(OUT)})")


if __name__ == "__main__":
    main()
