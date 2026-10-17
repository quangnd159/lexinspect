"""`assign` and `flash`: blinded labelling assignments (protocol "Blind labelling").

`assign` turns the label units (distinct payloads) into ordinary Study 4
items, in build.py's labeller format exactly: {"id", "module", "context",
"marker", "claimed"} and nothing else, so nothing reveals the version, the diff
direction, the family, the configuration, the frame or any pairing. Ids are
fresh random 40-bit hex strings (random.Random(derive_seed(round seed,
"item-ids"))), distinct from every development item id; items.jsonl is in a
shuffled order (derive_seed(round seed, "item-order")). The unblinded
key.jsonl (id -> payload hash, memberships) is for the analysis only.

Separate assignments for paired claims. Each batch is labelled in its own
fresh session (prereg "Batches and returned labels"), so a batch is an
assignment. Two items conflict, and must not share a batch, when either
holds:
- they form a pair: a sampled affected baseline payload and one of its
  counterpart payloads (identical payloads are one item);
- they make different claims about one occurrence: their recorded
  occurrences share source, text hash and module, and their spans overlap.
This covers every crosswalk link, since counterparts always overlap their
baseline hit. It also covers a sampled final output that meets a
baseline-success item for the same occurrence, and two candidate versions of
one occurrence. In a shared batch, any of these would show a labeller an old
and a new output side by side.
For each role (A, B) the items are put in that role's own seeded order
(batches.role_order with the round seed), cut into batches of equal size
(number of batches = max(ceil(n / batch size), 1 + the largest number of
items one item conflicts with), so that a separation exists), and every
conflicting pair falling in one batch is separated by a deterministic swap: the
later member of the pair, scanning batches and positions in order, is swapped
with the first item of another batch (scanning later batches first, then
earlier ones) such that neither batch then holds a pair. Batch sizes are
unchanged, so batch = position // batch size + 1 holds and batches.py's
write_batches writes the files and manifests (batches/<role>/batch/...).
The swap leaves the separated items at the start of a batch, so position in
a batch would track being a changed occurrence. Each batch is therefore
shuffled in place afterwards with random.Random(derive_seed(round seed,
"within-batch|<role>")), which leaves batch membership as it was. A final
check asserts that no batch holds a conflicting pair.

`retry` carries out the single registered retry with the same separation. It
validates a primary's first-pass labels (analyse.load_labels) and writes the
retry manifest exactly as analyse.py --retry-manifest does
(analyse.write_retry_manifest). The manifest's items then go into retry
batches cut from the role's own seeded order, restricted to those items.
Conflicting items still never share a batch. batches.py alone would put
every retry item into one batch. The retry labels are merged with
analyse.py --merge-retry, as registered.

`flash` validates the A and B label files with analyse.validate_lines
(registered rules; after the single registered retry has been merged with
analyse.py --merge-retry), computes analyse.needs_adjudication over all items
(every non-vote and every disagreement on any applicable outcome), and writes
the adjudicator's blinded assignment (same item format, same pair separation)
plus the validation logs.
"""

from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import analyse
import batches

from fixcheck.common import (
    derive_seed,
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    write_json,
    write_jsonl,
    write_step_manifest,
)

ITEM_FIELDS = ("id", "module", "context", "marker", "claimed")
# What a labeller session receives besides its batch file (prereg "Batches and returned labels").
LABELLER_MATERIALS = {
    "guidelines": analyse.REPO / "docs" / "validation" / "study4-guidelines.md",
    "sense_inventory": analyse.REPO
    / ".cache"
    / "validation"
    / "study4"
    / "phrase_sense_inventory.md",
}
DEV_ITEMS = analyse.REPO / ".cache" / "validation" / "study4" / "items.jsonl"


def item_of(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != set(ITEM_FIELDS) - {"id"}:
        raise ValueError(f"payload fields {sorted(payload)} are not the labeller fields")
    return {
        "id": item_id,
        "module": payload["module"],
        "context": payload["context"],
        "marker": payload["marker"],
        "claimed": payload["claimed"],
    }


def new_ids(n: int, round_seed: int, avoid: set[str]) -> list[str]:
    r = random.Random(derive_seed(round_seed, "item-ids"))
    ids: list[str] = []
    seen = set(avoid)
    while len(ids) < n:
        x = f"{r.getrandbits(40):010x}"
        if x not in seen:
            seen.add(x)
            ids.append(x)
    return ids


def pair_edges(units: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Pairs of payload hashes (baseline payload, counterpart or sibling payload), excluding
    identical ones."""
    row_payload: dict[tuple[str, str], str] = {}
    for u in units:
        for mb in u["memberships"]:
            if mb["role"] == "sampled" and "|affected|" in mb["frame"]:
                row_payload[(mb["frame"], mb["row"])] = u["payload_sha256"]
    edges = set()
    for u in units:
        for mb in u["memberships"]:
            if mb["role"] in ("counterpart", "sibling"):
                b = row_payload[(mb["frame"], mb["of"])]
                c = u["payload_sha256"]
                if b != c:
                    edges.add(tuple(sorted((b, c))))
    return edges


def occurrence_edges(units: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Pairs of distinct payloads with overlapping occurrences in one text and module."""
    by_group: dict[tuple, list[tuple[int, int, str]]] = defaultdict(list)
    for u in units:
        for src, text_sha, module, start, end in u.get("occurrences", []):
            by_group[(src, text_sha, module)].append((start, end, u["payload_sha256"]))
    edges = set()
    for occs in by_group.values():
        occs.sort()
        for i, (s1, e1, p1) in enumerate(occs):
            for s2, e2, p2 in occs[i + 1 :]:
                if s2 >= e1:
                    break
                if p1 != p2 and s1 < e2:
                    edges.add(tuple(sorted((p1, p2))))
    return edges


def conflict_edges(units: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return pair_edges(units) | occurrence_edges(units)


def separated_order(
    order: list[str],
    conflicts: dict[str, set[str]],
    batch_size: int,
    shuffle_seed: int | None = None,
) -> tuple[list[str], int]:
    """Cut `order` into equal batches and swap items until no batch holds a conflicting pair.

    Returns (new order, batch size). Deterministic; raises if no valid swap exists."""
    n = len(order)
    if n == 0:
        return [], batch_size
    max_degree = max((len(conflicts.get(i, ())) for i in order), default=0)
    nb = min(n, max(math.ceil(n / batch_size), 1 + max_degree))
    bs = math.ceil(n / nb)
    while math.ceil(n / bs) < nb:  # equal batches (batches.py) must still give nb of them
        bs -= 1
    bl = [order[i : i + bs] for i in range(0, n, bs)]
    sets = [set(b) for b in bl]

    def clash(x: str, k: int, without: str | None = None) -> bool:
        return any(y in sets[k] and y != without for y in conflicts.get(x, ()))

    for bi in range(len(bl)):
        for pos in range(len(bl[bi])):
            x = bl[bi][pos]
            if not clash(x, bi, x):
                continue
            done = False
            others = list(range(bi + 1, len(bl))) + list(range(bi))
            for bj in others:
                for qpos, y in enumerate(bl[bj]):
                    if clash(y, bi, x) or y in conflicts.get(x, ()) or clash(x, bj, y):
                        continue
                    bl[bi][pos], bl[bj][qpos] = y, x
                    sets[bi].discard(x)
                    sets[bi].add(y)
                    sets[bj].discard(y)
                    sets[bj].add(x)
                    done = True
                    break
                if done:
                    break
            if not done:
                raise RuntimeError(f"cannot separate item {x} from its paired items")
    if shuffle_seed is not None:
        r = random.Random(shuffle_seed)
        for b in bl:
            r.shuffle(b)
    for k, b in enumerate(bl):
        for x in b:
            if clash(x, k, x):
                raise AssertionError("a batch still holds a paired claim")
    return [x for b in bl for x in b], bs


def check_batch_size(batch_size: int) -> int:
    """Prereg: at most MODEL_BATCH_SIZE (325) items per fresh session (audit r1 S2)."""
    if not 1 <= batch_size <= batches.MODEL_BATCH_SIZE:
        raise SystemExit(f"--batch-size {batch_size}: must be 1..{batches.MODEL_BATCH_SIZE}")
    return batch_size


def conflicts_by_id(edges: set[tuple[str, str]], id_of: dict[str, str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        out[id_of[a]].add(id_of[b])
        out[id_of[b]].add(id_of[a])
    return out


def role_orders(
    ids: list[str],
    conflicts: dict[str, set[str]],
    round_seed: int,
    roles: tuple[str, ...],
    batch_size: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {"seed": round_seed, "roles": {}}
    for role in roles:
        base = batches.role_order(ids, round_seed, role)
        order, bs = separated_order(
            base, conflicts, batch_size, derive_seed(round_seed, f"within-batch|{role}")
        )
        out["roles"][role] = {
            "seed": f"{round_seed}-order-{role}",
            "batch_size": bs,
            "requested_batch_size": batch_size,
            "n": len(order),
            "order": order,
            "pair_separation": "deterministic swap repair, then seeded within-batch shuffle "
            "(fixcheck.assign.separated_order)",
            "within_batch_seed_label": f"fixcheck-v1|{round_seed}|within-batch|{role}",
        }
    return out


def main(argv: list[str]) -> int:
    set_command("assign", argv)
    ap = argparse.ArgumentParser(prog="fixcheck assign", description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample-dir", type=Path, required=True)
    ap.add_argument("--round-seed", type=int, help="default: selection.json's round seed")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=batches.MODEL_BATCH_SIZE)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    check_batch_size(args.batch_size)
    out = args.out.resolve()
    refuse_existing(out / "items.jsonl", args.overwrite)
    archived = read_json(args.sample_dir / "selection.json")["round_seed"]
    if args.round_seed is not None and args.round_seed != archived:
        raise SystemExit(f"--round-seed {args.round_seed} is not the sample's seed {archived}")
    args.round_seed = archived
    units = read_jsonl(args.sample_dir / "units.jsonl")
    avoid = {r["id"] for r in read_jsonl(DEV_ITEMS)} if DEV_ITEMS.exists() else set()
    ids = new_ids(len(units), args.round_seed, avoid)
    id_of = {u["payload_sha256"]: i for u, i in zip(units, ids, strict=True)}
    items = [item_of(id_of[u["payload_sha256"]], u["payload"]) for u in units]
    order = list(range(len(items)))
    random.Random(derive_seed(args.round_seed, "item-order")).shuffle(order)
    items_shuffled = [items[i] for i in order]
    key = []
    for u in units:
        cat = u["payload"]["claimed"].get("category") if u["module"] == "metadiscourse" else None
        key.append(
            {
                "id": id_of[u["payload_sha256"]],
                "module": u["module"],
                "category": cat,
                "payload_sha256": u["payload_sha256"],
                "memberships": u["memberships"],
                "occurrences": u.get("occurrences", []),
            }
        )
    key.sort(key=lambda k: k["id"])
    out.mkdir(parents=True, exist_ok=True)
    # items.jsonl exactly as build.py writes it (json.dumps, ensure_ascii=False, field order kept).
    import json

    (out / "items.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items_shuffled), encoding="utf-8"
    )
    write_jsonl(out / "key.jsonl", key)
    edges = conflict_edges(units)
    conflicts = conflicts_by_id(edges, id_of)
    orders = role_orders(sorted(ids), conflicts, args.round_seed, ("A", "B"), args.batch_size)
    write_json(out / "orders.json", orders)
    items_by_id = {i["id"]: i for i in items}
    files = [out / "items.jsonl", out / "key.jsonl", out / "orders.json"]
    for role in ("A", "B"):
        paths = batches.write_batches(items_by_id, orders, role, out, replace=args.overwrite)
        files += paths + [out / "batches" / role / "batch" / "batch_manifest.json"]
    summary = {
        "n_items": len(items),
        "n_conflicts": len(edges),
        "n_pairs": len(pair_edges(units)),
        "n_occurrence_conflicts": len(occurrence_edges(units)),
        "batches": {r: math.ceil(o["n"] / o["batch_size"]) for r, o in orders["roles"].items()},
        "batch_size": {r: o["batch_size"] for r, o in orders["roles"].items()},
        "item_fields": list(ITEM_FIELDS),
        "units_sha256": sha256_file(args.sample_dir / "units.jsonl"),
        "selection_sha256": sha256_file(args.sample_dir / "selection.json"),
        "decision_plan_sha256": sha256_file(args.sample_dir / "decision_plan.json")
        if (args.sample_dir / "decision_plan.json").exists()
        else None,
        "production_eligible": bool(
            read_json(args.sample_dir / "selection.json").get("production_eligible", False)
        ),
        "dev_item_ids_avoided": len(avoid),
        "labeller_materials_sha256": {
            k: sha256_file(p) if p.exists() else None for k, p in LABELLER_MATERIALS.items()
        },
        "labeller_materials_note": "label reuse needs identical guideline, inventory and "
        "prompt versions; these are the files the sessions are given",
    }
    write_json(out / "assignments.json", summary)
    files.append(out / "assignments.json")
    write_step_manifest(out, "assign", files)
    print(f"items {len(items)}, pairs {len(edges)}, batches {summary['batches']}")
    return 0


def load_round_labels(
    assign_dir: Path, specs: dict[str, Path], flash: Path | None, flash_dir: Path | None = None
):
    """Items, key, validated primaries (all items expected) and adjudicator (its assignment)."""
    items = {r["id"]: r for r in read_jsonl(assign_dir / "items.jsonl")}
    key = read_jsonl(assign_dir / "key.jsonl")
    prim = [analyse.load_labels(specs[r], items, None, r) for r in ("A", "B")]
    adj = None
    if flash is not None:
        fids = ((flash_dir or assign_dir / "flash") / "flash_ids.txt").read_text().split()
        adj = analyse.load_labels(flash, items, fids, analyse.ADJUDICATOR)
    return items, key, prim, adj


def main_flash(argv: list[str]) -> int:
    set_command("flash", argv)
    ap = argparse.ArgumentParser(prog="fixcheck flash")
    ap.add_argument("--assign-dir", type=Path, required=True)
    ap.add_argument("--labels", nargs=2, required=True, metavar="ROLE=PATH")
    ap.add_argument("--round-seed", type=int, help="default: the assignment's round seed")
    ap.add_argument("--batch-size", type=int, default=batches.MODEL_BATCH_SIZE)
    ap.add_argument("--out", type=Path, help="default <assign-dir>/flash")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    check_batch_size(args.batch_size)
    ad = args.assign_dir.resolve()
    archived = read_json(ad / "orders.json")["seed"]
    if args.round_seed is not None and args.round_seed != archived:
        raise SystemExit(f"--round-seed {args.round_seed} is not the assignment's seed {archived}")
    args.round_seed = archived
    specs = dict(analyse._spec(s) for s in args.labels)
    if set(specs) != {"A", "B"}:
        raise SystemExit("--labels A=PATH B=PATH")
    out = (args.out or ad / "flash").resolve()
    refuse_existing(out / "flash_ids.txt", args.overwrite)
    items, key, prim, _ = load_round_labels(ad, specs, None)
    rows = [{"id": k["id"], "module": k["module"], "category": k["category"]} for k in key]
    ids = analyse.needs_adjudication(rows, prim)
    # Pair conflicts among the adjudicator's items, from the key's memberships.
    id_of_payload = {k["payload_sha256"]: k["id"] for k in key}
    pseudo_units = [
        {
            "payload_sha256": k["payload_sha256"],
            "memberships": k["memberships"],
            "occurrences": k.get("occurrences", []),
        }
        for k in key
    ]
    conflicts = conflicts_by_id(conflict_edges(pseudo_units), id_of_payload)
    idset = set(ids)
    sub = {i: v & idset for i, v in conflicts.items() if i in idset}
    orders = role_orders(sorted(ids), sub, args.round_seed, ("adjudicator",), args.batch_size)
    out.mkdir(parents=True, exist_ok=True)
    (out / "flash_ids.txt").write_text("".join(i + "\n" for i in ids), encoding="utf-8")
    write_json(out / "orders.json", orders)
    files = [out / "flash_ids.txt", out / "orders.json"]
    if ids:
        files += batches.write_batches(items, orders, "adjudicator", out, replace=args.overwrite)
        files.append(out / "batches" / "adjudicator" / "batch" / "batch_manifest.json")
    log = {
        "rule": "analyse.needs_adjudication: any primary UNSURE/missing/invalid, or the primaries "
        "split on any applicable outcome",
        "n_items": len(items),
        "n_flash": len(ids),
        "validation": {p.name: p.summary() for p in prim},
        "problems": {p.name: p.problems for p in prim},
        "non_votes": {p.name: p.retry for p in prim},
        "label_files_sha256": {r: sha256_file(p) for r, p in specs.items()},
    }
    write_json(out / "flash_assignment.json", log)
    files.append(out / "flash_assignment.json")
    write_step_manifest(out, "flash", files)
    print(f"flash items: {len(ids)} of {len(items)}")
    return 0


def main_retry(argv: list[str]) -> int:
    set_command("retry", argv)
    ap = argparse.ArgumentParser(prog="fixcheck retry")
    ap.add_argument("--assign-dir", type=Path, required=True)
    ap.add_argument("--labels", nargs="+", required=True, metavar="ROLE=PATH")
    ap.add_argument("--batch-size", type=int, default=batches.MODEL_BATCH_SIZE)
    ap.add_argument("--out", type=Path, help="default <assign-dir>/retry")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    check_batch_size(args.batch_size)
    ad = args.assign_dir.resolve()
    out = (args.out or ad / "retry").resolve()
    refuse_existing(out / "retry.json", args.overwrite)
    specs = dict(analyse._spec(s) for s in args.labels)
    if not set(specs) <= {"A", "B"}:
        raise SystemExit("--labels A=PATH [B=PATH]")
    items = {r["id"]: r for r in read_jsonl(ad / "items.jsonl")}
    key = read_jsonl(ad / "key.jsonl")
    round_seed = read_json(ad / "orders.json")["seed"]
    id_of_payload = {k["payload_sha256"]: k["id"] for k in key}
    pseudo_units = [
        {
            "payload_sha256": k["payload_sha256"],
            "memberships": k["memberships"],
            "occurrences": k.get("occurrences", []),
        }
        for k in key
    ]
    conflicts = conflicts_by_id(conflict_edges(pseudo_units), id_of_payload)
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    rec: dict[str, Any] = {"round_seed": round_seed, "roles": {}}
    for role, path in sorted(specs.items()):
        ls = analyse.load_labels(path, items, None, role)
        man = out / f"retry_{role}.jsonl"
        analyse.write_retry_manifest(ls, man)
        files.append(man)
        ids = sorted(r["id"] for r in ls.retry)
        idset = set(ids)
        sub = {i: v & idset for i, v in conflicts.items() if i in idset}
        orders = role_orders(ids, sub, round_seed, (role,), args.batch_size)
        write_json(out / f"orders_{role}.json", orders)
        files.append(out / f"orders_{role}.json")
        if ids:
            files += batches.write_batches(
                items, orders, role, out, prefix="retry", replace=args.overwrite
            )
            files.append(out / "batches" / role / "retry" / "retry_manifest.json")
        rec["roles"][role] = {
            "labels_sha256": sha256_file(path),
            "n_retry": len(ids),
            "by_reason": ls.summary()["retry_by_reason"],
            "n_batches": math.ceil(len(ids) / orders["roles"][role]["batch_size"]) if ids else 0,
        }
    write_json(out / "retry.json", rec)
    files.append(out / "retry.json")
    write_step_manifest(out, "retry", files)
    print(f"retry: { {r: v['n_retry'] for r, v in rec['roles'].items()} }")
    return 0
