"""Study 4 0.4.0 pilot: collect one role's delivered labels and validate them.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/collect_role.py \\
        ROLE PREFIX SESSIONS_ROOT BUILD OUT --screen SCREEN_JSON [--rulings RULINGS_JSONL]

For ROLE (A, B or adjudicator) and PREFIX (batch, retry or adjudication), the
script reads the role's assignment manifest
(BUILD/batches/<role>/<prefix>/<prefix>_manifest.json) and, for every batch,
the one delivered session in SESSIONS_ROOT whose items SHA-256 equals that
batch file's. SCREEN_JSON is check_sessions.py's --json output for
SESSIONS_ROOT. The script stops, and collects nothing, if a batch has no
delivered session or more than one, if the matched session is a technical
failure, if the screen is missing, is for another root, lists an archive
problem, has no entry for the session or was made from a different
session.json, or if the session's screen status (in the file, and on a fresh
in-process screen) is not `clean`. It never generates or chooses a label: a
stopped batch waits for technical recovery or a relaunch.

A `flagged` session is accepted only with a recorded human ruling
(--rulings, one JSON object per line) that names the role, the session token,
the SHA-256 of its session.json and the SHA-256 of its exact flag set
(`flags_sha256`, below), with `"ruling": "accept"`, the reviewer, the date
and the reason. A ruling can accept only path, code-like and review flags,
after the maintainer has examined them in the transcript. A context-marker hit
(forbidden context injected into the session) and a technical failure can't be
accepted by any ruling. If the flags change, the ruling no longer matches.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sessions as CS  # noqa: E402

SESSION_ROLE = {"A": "A", "B": "B", "adjudicator": "C"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_screen(path: Path | None, sessions: Path) -> dict:
    if path is None or not path.is_file():
        raise SystemExit(f"screen result missing ({path}): run check_sessions.py --json first")
    try:
        screen = json.loads(path.read_text(encoding="utf-8"))
        entries = screen["sessions"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise SystemExit(f"screen result {path} unreadable: {e!r}") from e
    if Path(screen.get("archive", "")).resolve() != sessions.resolve():
        raise SystemExit(f"screen result {path} is for {screen.get('archive')}, not {sessions}")
    if screen.get("inventory_problems"):
        raise SystemExit(
            "archive problems stop acceptance pending technical recovery (no label is "
            "generated or chosen): " + "; ".join(screen["inventory_problems"])
        )
    return {(e.get("role"), e.get("token")): e for e in entries}


FLAG_KEYS = ("other_paths", "code_like_calls", "review")


def flags_sha256(r: dict) -> str:
    """The SHA-256 of a screen entry's acceptable-by-ruling flags, canonically encoded."""
    flags = {k: r.get(k) or [] for k in FLAG_KEYS}
    return hashlib.sha256(
        json.dumps(flags, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_rulings(path: Path | None) -> dict:
    if path is None:
        return {}
    out = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        missing = [
            k
            for k in (
                "role",
                "token",
                "session_json_sha256",
                "flags_sha256",
                "ruling",
                "reviewer",
                "date",
                "reason",
            )
            if not r.get(k)
        ]
        if missing or r["ruling"] != "accept":
            raise SystemExit(
                f"{path}:{n}: not a valid ruling (missing {missing} or ruling != accept)"
            )
        out[(r["role"], r["token"])] = r
    return out


def ruled(r: dict, ruling: dict | None, session_sha: str) -> bool:
    """True if a flagged screen result is covered by a matching human ruling."""
    return (
        ruling is not None
        and r.get("status") == "flagged"
        and not r.get("context_forbidden_hits")
        and not r.get("technical_failures")
        and ruling["session_json_sha256"] == session_sha
        and ruling["flags_sha256"] == flags_sha256(r)
    )


def accept(batch: int, d: Path, entry: dict | None, ruling: dict | None = None) -> None:
    """Stop unless the session is delivered, validated and clean (or flagged and ruled),
    in the file and afresh."""
    stop = f"batch {batch}, session {d.parent.name}/{d.name}"
    if entry is None:
        raise SystemExit(f"{stop}: screen result missing for this session")
    session_sha = sha256(d / "session.json")
    if entry.get("session_json_sha256") != session_sha:
        raise SystemExit(f"{stop}: screen result was made from a different session.json")
    fresh = CS.screen(d)
    for where, r in (("screen file", entry), ("fresh screen", fresh)):
        if r.get("status") != "clean" and not ruled(r, ruling, session_sha):
            why = r.get("technical_failures") or [
                f"{k}: {len(r.get(k) or [])}"
                for k in ("context_forbidden_hits", "other_paths", "code_like_calls", "review")
                if r.get(k)
            ]
            raise SystemExit(
                f"{stop}: {where} status {r.get('status')!r} ({'; '.join(why)}); not collected. "
                "No label is generated or chosen: technical failures wait for recovery or a "
                "relaunch, flagged calls for the maintainer's examination and a recorded ruling "
                f"(flags_sha256 {flags_sha256(r)})."
            )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", choices=tuple(SESSION_ROLE))
    ap.add_argument("prefix")
    ap.add_argument("sessions", type=Path)
    ap.add_argument("build", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--screen", type=Path, help="check_sessions.py --json output")
    ap.add_argument("--rulings", type=Path, help="recorded human rulings on flagged sessions")
    args = ap.parse_args(argv)
    screened = load_screen(args.screen, args.sessions)
    rulings = load_rulings(args.rulings)
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
            other = [
                f"{s['token']}:{s['status']}"
                for s in sessions
                if s["status"] != "delivered" and s["inputs"]["items_sha256"] == b["sha256"]
            ]
            raise SystemExit(
                f"batch {b['batch']}: {len(match)} delivered sessions (need exactly 1)"
                + (f"; not delivered: {', '.join(other)}" if other else "")
                + ". Acceptance stops pending technical recovery or a relaunch; no label is "
                "generated or chosen."
            )
        s = match[0]
        sdir = args.sessions / SESSION_ROLE[args.role] / s["token"]
        key = (SESSION_ROLE[args.role], s["token"])
        accept(b["batch"], sdir, screened.get(key), rulings.get(key))
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
        "screen_sha256": sha256(args.screen),
        "rulings_sha256": sha256(args.rulings) if args.rulings else None,
        "check_sessions_sha256": sha256(Path(CS.__file__)),
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
