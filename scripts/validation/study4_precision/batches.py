"""Study 4: per-labeller item order and batches.

Every labeller role gets its own seeded, independently shuffled order of the
items it labels, cut into batches, so that position and batch effects are not
shared between labellers and can be checked (analyse.py reports agreement and
STRICT precision by batch for each primary).

    # orders for a built set, written to OUT/orders.json, plus batch files
    uv run python scripts/validation/study4_precision/batches.py \\
        --dir .cache/validation/study4 --out .cache/validation/study4_scratch

    # adjudicator batches for the items analyse.py --disagreements listed
    uv run python scripts/validation/study4_precision/batches.py \\
        --dir BUILD --orders BUILD/orders.json --role adjudicator --ids disagreements.txt \\
        --out BUILD --prefix adjudication

    # a retry batch (ids from a retry manifest) for one role
    ... --role A --ids retry/retry_A.jsonl --out BUILD --prefix retry

Roles: A and B (primaries; all items), adjudicator (an order over all items,
filtered at labelling time to the items needing adjudication) and maintainer
(the maintainer sample). The seed for role R is the string "{seed}-order-{R}".
Batch files hold the items.jsonl records unchanged, in order:
`<out>/batches/<role>/<prefix>/<prefix>_01.jsonl`, ... with an authoritative assignment
manifest `<prefix>_manifest.json` (ids per batch, positions, file SHA-256).
The batch of an item is position // batch_size + 1 in the role's (filtered)
order. A role/prefix set is written only into a fresh location. `--replace`
builds the complete new set in a temporary directory, then moves the old set
aside and renames the new one into place: after a successful run no stale
batch file can survive. The two renames are not an atomic exchange; a crash
between them leaves no set at that path (never a mixed one), and the run
should be repeated. Before anything is written the CLI rejects duplicate ids
in items.jsonl, key.jsonl, orders.json and the requested id list (checked on
the raw lists, before any conversion to a dict or set), runs analyse.py's
design validation, and rejects unknown ids and non-positive batch sizes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROLES = ("A", "B", "adjudicator", "maintainer")
MODEL_BATCH_SIZE = 325


def role_order(ids: list[str], seed: int, role: str) -> list[str]:
    out = sorted(ids)
    random.Random(f"{seed}-order-{role}").shuffle(out)
    return out


def make_orders(
    item_ids: list[str],
    maintainer_ids: list[str],
    seed: int,
    batch_size: int = MODEL_BATCH_SIZE,
    maintainer_batch_size: int | None = None,
) -> dict[str, Any]:
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if maintainer_batch_size is not None and maintainer_batch_size <= 0:
        raise ValueError("maintainer_batch_size must be a positive integer")
    for name, ids in (("items", item_ids), ("maintainer", maintainer_ids)):
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate {name} ids")
    if not set(maintainer_ids) <= set(item_ids):
        raise ValueError("maintainer ids not among the items")
    roles = {}
    for role in ROLES:
        ids = maintainer_ids if role == "maintainer" else item_ids
        bs = (maintainer_batch_size or max(1, len(ids))) if role == "maintainer" else batch_size
        roles[role] = {
            "seed": f"{seed}-order-{role}",
            "batch_size": bs,
            "n": len(ids),
            "order": role_order(ids, seed, role),
        }
    return {
        "seed": seed,
        "note": (
            "Independent order per role; batch = position // batch_size + 1. The "
            "adjudicator's order covers all items and is filtered to the items needing "
            "adjudication before batching."
        ),
        "roles": roles,
    }


def batches_for(orders: dict[str, Any], role: str, ids: set[str] | None = None) -> list[list[str]]:
    r = orders["roles"][role]
    if ids is not None:
        unknown = sorted(set(ids) - set(r["order"]))
        if unknown:
            raise ValueError(f"{len(unknown)} ids not in role {role}'s order, e.g. {unknown[:3]}")
    order = [i for i in r["order"] if ids is None or i in ids]
    bs = r["batch_size"]
    if not isinstance(bs, int) or bs <= 0:
        raise ValueError("batch_size must be a positive integer")
    return [order[i : i + bs] for i in range(0, len(order), bs)]


def write_batches(
    items: dict[str, dict[str, Any]],
    orders: dict[str, Any],
    role: str,
    out: Path,
    ids: set[str] | None = None,
    prefix: str = "batch",
    replace: bool = False,
) -> list[Path]:
    """Write the role's batch files and manifest under out/batches/<role>/<prefix>/."""
    batches = batches_for(orders, role, ids)
    missing = [i for b in batches for i in b if i not in items]
    if missing:
        raise ValueError(f"{len(missing)} ordered ids have no item record")
    final = out / "batches" / role / prefix
    if final.exists() and not replace:
        raise FileExistsError(f"{final} exists; use replace=True (--replace) to swap in a new set")
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{prefix}-", dir=final.parent))
    manifest: dict[str, Any] = {
        "role": role,
        "prefix": prefix,
        "seed": orders["roles"][role]["seed"],
        "batch_size": orders["roles"][role]["batch_size"],
        "n": sum(len(b) for b in batches),
        "restricted_to_ids": ids is not None,
        "batches": [],
    }
    for k, batch in enumerate(batches, 1):
        name = f"{prefix}_{k:02d}.jsonl"
        data = "".join(json.dumps(items[i], ensure_ascii=False) + "\n" for i in batch)
        (tmp / name).write_text(data, encoding="utf-8")
        manifest["batches"].append(
            {
                "batch": k,
                "file": name,
                "sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
                "ids": batch,
            }
        )
    (tmp / f"{prefix}_manifest.json").write_text(json.dumps(manifest, indent=1))
    if final.exists():
        old = final.with_name(f".{prefix}-old-{os.getpid()}")
        final.rename(old)
        tmp.rename(final)
        shutil.rmtree(old)
    else:
        tmp.rename(final)
    return [final / b["file"] for b in manifest["batches"]]


def _read_ids(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(json.loads(s)["id"] if s.startswith("{") else s)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, required=True, help="build directory (items.jsonl)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--orders", type=Path, help="existing orders.json (else made from --seed)")
    ap.add_argument("--seed", type=int, default=20261016)
    ap.add_argument("--batch-size", type=int, default=MODEL_BATCH_SIZE)
    ap.add_argument("--role", choices=ROLES, help="only this role")
    ap.add_argument("--ids", type=Path, help="restrict the role's batches to these ids")
    ap.add_argument("--prefix", default="batch")
    ap.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing set (new set built first, then two renames)",
    )
    args = ap.parse_args(argv)
    if args.batch_size <= 0:
        ap.error("--batch-size must be positive")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import analyse

    item_list = [
        json.loads(x)
        for x in (args.dir / "items.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    key = [json.loads(x) for x in (args.dir / "key.jsonl").read_text().splitlines() if x.strip()]
    if any("in_maintainer_sample" in r for r in key):
        mids = [r["id"] for r in key if r.get("in_maintainer_sample")]
    else:
        mids = _read_ids(args.dir / "human_sample_ids.txt")
    orders = json.loads(args.orders.read_text()) if args.orders else None
    problems = analyse.validate_design(key, item_list, mids, orders)
    req = _read_ids(args.ids) if args.ids else None
    if req is not None:
        dup = sorted({i for i in req if req.count(i) > 1})
        if dup:
            problems.append(f"requested ids: duplicate {', '.join(dup[:5])}")
    if problems:
        raise SystemExit("design problems, nothing written:\n- " + "\n- ".join(problems))
    items = {it["id"]: it for it in item_list}
    if orders is None:
        orders = make_orders(sorted(items), mids, args.seed, args.batch_size)
        args.out.mkdir(parents=True, exist_ok=True)
        op = args.out / "orders.json"
        if op.exists() and not args.replace:
            raise SystemExit(f"{op} exists (use --orders to reuse it, or --replace)")
        op.write_text(json.dumps(orders, indent=1))
    ids = set(req) if req is not None else None
    for role in [args.role] if args.role else [r for r in ROLES if r != "adjudicator"]:
        paths = write_batches(items, orders, role, args.out, ids, args.prefix, args.replace)
        print(
            f"{role}: {len(paths)} batch files in {paths[0].parent if paths else '-'}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
