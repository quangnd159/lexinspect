"""`verify`: checks of the harness's own outputs (ledger, blinding, determinism). No labels.

ledger_check(ledger_md)
  Checks the 68 component identities (ledger.ledger_components) against the
  protocol's construction:
  - J = 4(F + 5) with F = 12, and a = .05/J for every component;
  - the ids are unique and exactly R{1,2} x {metadiscourse, phrase} x
    (12 family removals + COMPLETE x 5 kinds);
  - success bounds are lower bounds, every other component an upper bound.
  It also parses the family table and the J and a figures of
  CANDIDATE_LEDGER.md and compares them with ledger.py.

blinding_audit(assign_dir, sample_dir, run_dir)
  Checks that nothing but the ordinary judgement payload reaches a
  labeller:
  - every items.jsonl record is exactly {id, module, context, marker,
    claimed}, in that field order;
  - its payload (without the id) hashes to the key's payload hash, and that
    payload is a hit emitted in the run, so the context is build.py's own
    context_for;
  - ids are fresh 10-hex strings: not development item ids, and not the
    10-digit prefix of any hit id's hash;
  - marker and claimed contain no configuration, family, change-type or
    version token;
  - every batch file record is byte-identical to its items.jsonl line;
  - each role's batches cover every assigned item exactly once;
  - each batch directory holds only batch files and the batch manifest;
  - no batch of A, B, a retry or the adjudicator holds two conflicting
    items (assign.conflict_edges), and every retry and adjudicator batch set
    is exactly its manifest's items;
  - the order of items.jsonl and of every role is recomputed from the
    declared seeds and must match exactly.
  It also reports how many same-batch conflicts the pair-only rule would
  have missed.

compare_dirs(a, b)
  Byte comparison of two output trees, ignoring only manifest_*.json (they
  hold write times and command lines): the determinism check.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from fixcheck.assign import (
    DEV_ITEMS,
    ITEM_FIELDS,
    conflict_edges,
    conflicts_by_id,
    occurrence_edges,
    pair_edges,
    role_orders,
)
from fixcheck.common import (
    derive_seed,
    payload_sha256,
    read_json,
    read_jsonl,
    set_command,
    sha256_file,
    write_json,
    write_step_manifest,
)
from fixcheck.ledger import (
    COMPLETE,
    COMPONENT_KINDS,
    FAMILIES,
    FAMILY_MODULE,
    FAMILY_RULES,
    LEDGER_MD,
    MODULES,
    ROUNDS,
    A,
    F,
    J,
    ledger_components,
)

FORBIDDEN = re.compile(
    r"BASELINE|COMPLETE|PINNED|\bMD-[A-I]\b|\bPH-[ABC]\b|\bMD-\d\d\b|\bPH-\d\d\b|\bSX-\d\d\b|"
    r"REMOVED|CLAIM_DROPPED|REASSIGNED|SPAN_CHANGED|MULTIPLICITY|DISPLAY_CONTEXT|COUNTERPART|counterpart|"
    r"0\.3\.3|0\.4\.0|dec79bc|hit_id|payload|fixcheck"
)


def ledger_check(ledger_md: Path = LEDGER_MD) -> dict[str, Any]:
    comps = ledger_components()
    problems: list[str] = []
    ids = [c["id"] for c in comps]
    expected = {
        f"R{r}.{m}.{w}.{k}"
        for r in ROUNDS
        for m in MODULES
        for w, k in [(f, "removal") for f in FAMILIES] + [(COMPLETE, k) for k in COMPONENT_KINDS]
    }
    if J != 4 * (F + 5) or F != 12 or J != 68:
        problems.append(f"J = {J}, F = {F}")
    if len(comps) != J or len(set(ids)) != len(ids) or set(ids) != expected:
        problems.append("component ids are not the 68 declared identities")
    if any(c["alpha"] != 0.05 / 68 for c in comps) or A != 0.05 / 68:
        problems.append("a component's level is not .05/68")
    for c in comps:
        want = "lower" if c["kind"].startswith("success") else "upper"
        if c["bound"] != want:
            problems.append(f"{c['id']}: bound {c['bound']} != {want}")
    md: dict[str, Any] = {"file": str(ledger_md), "found": ledger_md.exists()}
    if ledger_md.exists():
        text = ledger_md.read_text(encoding="utf-8")
        md["sha256"] = sha256_file(ledger_md)
        rows = re.findall(
            r"^\| ((?:MD|PH)-[A-I]) [^|]*\| (\w+) \| ([^|]+) \| ([^|]+) \|$", text, re.M
        )
        table = {
            f: (mod, tuple(r.strip() for r in re.sub(r"\s*\([^)]*\)", "", rules).split(",")))
            for f, mod, rules, _ in rows
        }
        md["families_in_table"] = sorted(table)
        if set(table) != set(FAMILIES):
            problems.append(f"ledger table families {sorted(table)} != {list(FAMILIES)}")
        for f, (mod, rules) in table.items():
            if f in FAMILY_MODULE and (mod != FAMILY_MODULE[f] or rules != FAMILY_RULES[f]):
                problems.append(f"{f}: ledger table {mod} {rules} != ledger.py")
        if "**68**" not in text or "0.000735294" not in text:
            problems.append("CANDIDATE_LEDGER.md does not state J = 68 and a = 0.000735294…")
        prereq = {p.strip() for *_, p in rows}
        md["prerequisites"] = sorted(prereq)
        if prereq != {"none"}:
            problems.append(f"family prerequisites {prereq}: the harness assumes none")
    else:
        problems.append(f"{ledger_md} not found")
    per = {
        f"R{r}.{m}": sum(c["round"] == r and c["module"] == m for c in comps)
        for r in ROUNDS
        for m in MODULES
    }
    return {
        "J": J,
        "F": F,
        "a": A,
        "n_components": len(comps),
        "per_round_module": per,
        "ledger_md": md,
        "problems": problems,
        "ok": not problems,
    }


def _batch_sets(role_dir: Path) -> tuple[list[list[str]], list[str], str]:
    mans = sorted(role_dir.glob("*_manifest.json"))
    if len(mans) != 1:
        raise ValueError(f"{role_dir}: expected one batch manifest, found {len(mans)}")
    man = read_json(mans[0])
    return [b["ids"] for b in man["batches"]], [b["file"] for b in man["batches"]], mans[0].name


def blinding_audit(
    assign_dir: Path,
    sample_dir: Path,
    run_dir: Path,
    flash_dirs: list[Path] | None = None,
    retry_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    raw_lines = (assign_dir / "items.jsonl").read_text(encoding="utf-8").splitlines()
    items = [json.loads(x) for x in raw_lines]
    line_of = {it["id"]: line for it, line in zip(items, raw_lines, strict=True)}
    key = {k["id"]: k for k in read_jsonl(assign_dir / "key.jsonl")}
    units = read_jsonl(sample_dir / "units.jsonl")
    round_seed = read_json(sample_dir / "selection.json")["round_seed"]
    # 1-2. fields and payload identity
    run_payloads: set[str] = set()
    hit_prefixes: set[str] = set()
    for f in sorted((run_dir / "frames").glob("*.hits.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                run_payloads.add(r["payload_sha256"])
                hit_prefixes.add(r["hit_id"].split(":", 1)[1][:10])
    for it in items:
        if list(it) != list(ITEM_FIELDS):
            problems.append(f"{it.get('id')}: fields {list(it)}")
        if not re.fullmatch(r"[0-9a-f]{10}", it["id"]):
            problems.append(f"{it['id']}: id is not 10 hex digits")
        p = payload_sha256({k: v for k, v in it.items() if k != "id"})
        if key[it["id"]]["payload_sha256"] != p:
            problems.append(f"{it['id']}: item payload differs from the key's payload hash")
        if p not in run_payloads:
            problems.append(f"{it['id']}: payload is not a hit emitted in the run")
        visible = json.dumps([it["marker"], it["claimed"]], ensure_ascii=False)
        if FORBIDDEN.search(visible):
            problems.append(f"{it['id']}: marker/claimed holds {FORBIDDEN.search(visible)[0]!r}")
    contexts_with_tokens = sum(bool(FORBIDDEN.search(it["context"])) for it in items)
    ids = {it["id"] for it in items}
    dev_ids = {r["id"] for r in read_jsonl(DEV_ITEMS)} if DEV_ITEMS.exists() else set()
    if ids & dev_ids:
        problems.append(f"{len(ids & dev_ids)} ids are development item ids")
    if ids & hit_prefixes:
        problems.append(f"{len(ids & hit_prefixes)} ids equal a hit-id hash prefix")
    if len(ids) != len(items) or set(key) != ids:
        problems.append("items and key ids differ or repeat")
    # 3. orders recomputed from the declared seeds
    order = list(range(len(units)))
    random.Random(derive_seed(round_seed, "item-order")).shuffle(order)
    id_of = {k["payload_sha256"]: k["id"] for k in key.values()}
    expect_items = [id_of[units[i]["payload_sha256"]] for i in order]
    if [it["id"] for it in items] != expect_items:
        problems.append("items.jsonl order is not the declared seeded shuffle")
    edges = conflict_edges(units)
    conflicts = conflicts_by_id(edges, id_of)
    orders = read_json(assign_dir / "orders.json")
    bs_declared = {r: o["batch_size"] for r, o in orders["roles"].items()}
    for role in ("A", "B"):
        o = orders["roles"][role]
        redo = role_orders(sorted(ids), conflicts, round_seed, (role,), o["requested_batch_size"])
        if redo["roles"][role]["order"] != o["order"] or bs_declared[role] != o["batch_size"]:
            problems.append(f"{role}: order is not reproducible from the declared seeds")
    # 4. batch files, coverage, separation
    pair_only = {tuple(sorted((id_of[a], id_of[b]))) for a, b in pair_edges(units)}
    occ_only = {tuple(sorted((id_of[a], id_of[b]))) for a, b in occurrence_edges(units)}
    roles: dict[str, Any] = {}
    role_dirs = {r: assign_dir / "batches" / r / "batch" for r in ("A", "B")}
    flash_ids: dict[str, set[str]] = {}

    def label(d: Path, dirs: list[Path]) -> str:
        """The dir's name, or parent/name when two given dirs share a name."""
        return d.name if [x.name for x in dirs].count(d.name) == 1 else f"{d.parent.name}/{d.name}"

    for fl in flash_dirs or []:
        name = f"adjudicator ({label(fl, flash_dirs)})"
        flash_ids[name] = set((fl / "flash_ids.txt").read_text().split())
        d = fl / "batches" / "adjudicator" / "batch"
        if d.exists():
            role_dirs[name] = d
        elif flash_ids[name]:
            problems.append(f"{name}: items need adjudication but no batches were written")
    for rt in retry_dirs or []:
        for role in ("A", "B"):
            man = rt / f"retry_{role}.jsonl"
            if not man.exists():
                continue
            name = f"retry {role} ({label(rt, retry_dirs)})"
            flash_ids[name] = {r["id"] for r in read_jsonl(man)}
            d = rt / "batches" / role / "retry"
            if d.exists():
                role_dirs[name] = d
            elif flash_ids[name]:
                problems.append(f"{name}: items need a retry but no batches were written")
    for role, d in role_dirs.items():
        bsets, files, man_name = _batch_sets(d)
        extra = sorted(p.name for p in d.iterdir() if p.name not in {*files, man_name})
        if extra:
            problems.append(f"{role}: unexpected files in the batch directory {extra}")
        flat = [i for b in bsets for i in b]
        if len(flat) != len(set(flat)):
            problems.append(f"{role}: an item is in two batches")
        if role in ("A", "B") and set(flat) != ids:
            problems.append(f"{role}: batches do not cover every item exactly once")
        if role in flash_ids and set(flat) != flash_ids[role]:
            problems.append(f"{role}: batches are not exactly the items it was assigned")
        same_batch_conflicts = same_batch_missed = 0
        for b, fname in zip(bsets, files, strict=True):
            lines = (d / fname).read_text(encoding="utf-8").splitlines()
            if [json.loads(x)["id"] for x in lines] != b:
                problems.append(f"{role} {fname}: file order differs from the manifest")
            if any(line_of.get(json.loads(x)["id"]) != x for x in lines):
                problems.append(f"{role} {fname}: a record differs from items.jsonl")
            bset = set(b)
            for x in b:
                for y in conflicts.get(x, ()):
                    if y in bset and x < y:
                        same_batch_conflicts += 1
            same_batch_missed += sum(1 for x, y in occ_only - pair_only if x in bset and y in bset)
        if same_batch_conflicts:
            problems.append(f"{role}: {same_batch_conflicts} conflicting pairs share a batch")
        roles[role] = {
            "n_items": len(flat),
            "n_batches": len(bsets),
            "batch_sizes": sorted({len(b) for b in bsets}),
            "conflicting_pairs_in_one_batch": same_batch_conflicts,
            "occurrence_conflicts_in_one_batch_missed_by_pair_rule": same_batch_missed,
        }
    return {
        "n_items": len(items),
        "n_conflicts": len(edges),
        "n_pair_edges": len(pair_only),
        "n_occurrence_edges": len(occ_only),
        "n_occurrence_edges_not_pairs": len(occ_only - pair_only),
        "contexts_containing_a_listed_token": contexts_with_tokens,
        "dev_item_ids_checked": len(dev_ids),
        "roles": roles,
        "problems": problems,
        "ok": not problems,
    }


def counterfactual_pair_only(assign_dir: Path, sample_dir: Path) -> dict[str, Any]:
    """Batches built with the pair-only rule (the previous design): how many conflicts share
    a batch. A diagnostic of why occurrence conflicts are needed; nothing is written."""
    units = read_jsonl(sample_dir / "units.jsonl")
    key = read_jsonl(assign_dir / "key.jsonl")
    round_seed = read_json(sample_dir / "selection.json")["round_seed"]
    id_of = {k["payload_sha256"]: k["id"] for k in key}
    orders = read_json(assign_dir / "orders.json")
    bs = orders["roles"]["A"]["requested_batch_size"]
    old = role_orders(
        sorted(id_of.values()), conflicts_by_id(pair_edges(units), id_of), round_seed, ("A",), bs
    )
    o, b = old["roles"]["A"]["order"], old["roles"]["A"]["batch_size"]
    batch = {x: i // b for i, x in enumerate(o)}
    occ = {tuple(sorted((id_of[x], id_of[y]))) for x, y in occurrence_edges(units)}
    return {
        "role": "A",
        "occurrence_conflicts_sharing_a_batch_under_pair_only_rule": sum(
            batch[x] == batch[y] for x, y in occ
        ),
        "n_occurrence_conflicts": len(occ),
    }


def compare_dirs(a: Path, b: Path) -> dict[str, Any]:
    def files(d: Path) -> dict[str, Path]:
        return {
            str(p.relative_to(d)): p
            for p in sorted(d.rglob("*"))
            if p.is_file() and not p.name.startswith("manifest_")
        }

    fa, fb = files(a), files(b)
    differ = sorted(k for k in set(fa) & set(fb) if fa[k].read_bytes() != fb[k].read_bytes())
    return {
        "a": str(a),
        "b": str(b),
        "n_files": len(fa),
        "only_in_a": sorted(set(fa) - set(fb)),
        "only_in_b": sorted(set(fb) - set(fa)),
        "differ": differ,
        "identical": not differ and set(fa) == set(fb),
        "ignored": "manifest_*.json (write time, command line)",
    }


def main(argv: list[str]) -> int:
    set_command("verify", argv)
    ap = argparse.ArgumentParser(prog="fixcheck verify", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ledger-md", type=Path, default=LEDGER_MD)
    ap.add_argument("--assign-dir", type=Path)
    ap.add_argument("--sample-dir", type=Path)
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--flash-dir", type=Path, action="append", default=[])
    ap.add_argument("--retry-dir", type=Path, action="append", default=[])
    ap.add_argument("--compare", nargs=2, type=Path, action="append", default=[], metavar="DIR")
    args = ap.parse_args(argv)
    out = args.out.resolve()
    rec: dict[str, Any] = {"ledger": ledger_check(args.ledger_md)}
    if args.assign_dir and args.sample_dir and args.run_dir:
        rec["blinding"] = blinding_audit(
            args.assign_dir, args.sample_dir, args.run_dir, args.flash_dir, args.retry_dir
        )
        rec["pair_only_counterfactual"] = counterfactual_pair_only(args.assign_dir, args.sample_dir)
        rec["inputs"] = {
            "key_jsonl_sha256": sha256_file(args.assign_dir / "key.jsonl"),
            "items_jsonl_sha256": sha256_file(args.assign_dir / "items.jsonl"),
            "selection_json_sha256": sha256_file(args.sample_dir / "selection.json"),
            "run_json_sha256": sha256_file(args.run_dir / "run.json"),
            "ledger_md_sha256": sha256_file(args.ledger_md) if args.ledger_md.exists() else None,
        }
        # the exact retry and Flash directories audited (package.check_verify, audit r2 B5)
        rec["stage_inputs"] = {
            "retry": [
                sha256_file(d / "retry.json") if (d / "retry.json").exists() else None
                for d in args.retry_dir
            ],
            "flash": [
                sha256_file(d / "flash_ids.txt") if (d / "flash_ids.txt").exists() else None
                for d in args.flash_dir
            ],
        }
    rec["determinism"] = [compare_dirs(a.resolve(), b.resolve()) for a, b in args.compare]
    ok = (
        rec["ledger"]["ok"]
        and rec.get("blinding", {"ok": True})["ok"]
        and all(d["identical"] for d in rec["determinism"])
    )
    rec["ok"] = ok
    write_json(out / "verify.json", rec)
    write_step_manifest(out, "verify", [out / "verify.json"])
    print(f"verify: ok={ok}")
    return 0 if ok else 1
