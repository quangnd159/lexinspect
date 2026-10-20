"""Study 4 0.4.0 pilot: collect one role's delivered labels and validate them.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/collect_role.py \\
        ROLE PREFIX SESSIONS_ROOT BUILD OUT

For ROLE (A, B or adjudicator) and PREFIX (batch, retry or adjudication), the
script reads the role's assignment manifest
(BUILD/batches/<role>/<prefix>/<prefix>_manifest.json) and, for every batch,
the one delivered session in SESSIONS_ROOT whose items SHA-256 equals that
batch file's. It stops if a batch has no delivered session or more than one.
Labels are concatenated in batch order and validated per batch with the
frozen validator (analyse.validate_lines), against the ids assigned to that
batch. It writes:

- OUT/<role>_<prefix>.jsonl: the delivered lines, unchanged, in batch order;
- OUT/<role>_<prefix>_retry.jsonl: the retry manifest (missing or invalid ids);
- OUT/<role>_<prefix>_validation.json: per-batch counts, problems, warnings,
  label counts, the session tokens and every SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyse as A  # noqa: E402

SESSION_ROLE = {"A": "A", "B": "B", "adjudicator": "C"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", choices=tuple(SESSION_ROLE))
    ap.add_argument("prefix")
    ap.add_argument("sessions", type=Path)
    ap.add_argument("build", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)
    bdir = args.build / "batches" / args.role / args.prefix
    manifest = json.loads((bdir / f"{args.prefix}_manifest.json").read_text())
    items = {r["id"]: r for r in A.read_jsonl(args.build / "items.jsonl")}
    sessions = [
        json.loads(p.read_text())
        for p in sorted((args.sessions / SESSION_ROLE[args.role]).glob("*/session.json"))
    ]
    delivered = [s for s in sessions if s["status"] == "delivered"]
    all_lines: list[str] = []
    retry: list[dict] = []
    counts: Counter[str] = Counter()
    report: list[dict] = []
    for b in manifest["batches"]:
        f = bdir / b["file"]
        if sha256(f) != b["sha256"]:
            raise SystemExit(f"{f} does not match its manifest")
        match = [s for s in delivered if s["inputs"]["items_sha256"] == b["sha256"]]
        if len(match) != 1:
            raise SystemExit(
                f"batch {b['batch']}: {len(match)} delivered sessions (need exactly 1)"
            )
        s = match[0]
        lab = args.sessions / SESSION_ROLE[args.role] / s["token"] / "labels.jsonl"
        if sha256(lab) != s["labels_sha256"]:
            raise SystemExit(f"{lab} does not match its session record")
        lines = lab.read_text(encoding="utf-8").splitlines()
        ls = A.validate_lines(lines, items, b["ids"], f"{args.role}_{args.prefix}_{b['batch']:02d}")
        all_lines += lines
        retry += ls.retry
        c = Counter(r["label"] for r in ls.labels.values())
        counts.update(c)
        report.append(
            {
                "batch": b["batch"],
                "token": s["token"],
                "session_id": s["session_id"],
                "labels_sha256": s["labels_sha256"],
                "assigned": len(b["ids"]),
                "lines": ls.n_lines,
                "valid": len(ls.labels),
                "retry": len(ls.retry),
                "problems": ls.problems,
                "warnings": ls.warnings,
                "label_counts": dict(c),
            }
        )
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.role}_{args.prefix}"
    (args.out / f"{stem}.jsonl").write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    retry.sort(key=lambda r: r["id"])
    (args.out / f"{stem}_retry.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in retry),
        encoding="utf-8",
    )
    summary = {
        "role": args.role,
        "prefix": args.prefix,
        "manifest_sha256": sha256(bdir / f"{args.prefix}_manifest.json"),
        "items_sha256": sha256(args.build / "items.jsonl"),
        "batches": report,
        "label_counts": dict(counts),
        "retry_total": len(retry),
        "labels_sha256": sha256(args.out / f"{stem}.jsonl"),
        "retry_sha256": sha256(args.out / f"{stem}_retry.jsonl"),
        "analyse_sha256": sha256(Path(A.__file__)),
    }
    (args.out / f"{stem}_validation.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False)
    )
    for r in report:
        print(f"{stem} batch {r['batch']}: valid {r['valid']}/{r['assigned']}, retry {r['retry']}")
    print("labels:", dict(counts), "retry total:", len(retry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
