"""Study 4 0.4.0 pilot: screen archived labelling sessions.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/check_sessions.py \\
        ARCHIVE_ROOT [--json OUT]

For every session archived by launch.py it reports:

- context: whether the provider's session record (the effective context)
  contains any repository, study or private-path marker, a git-status block, or
  the user's own instruction file;
- files: every absolute path the session's tool calls mention that is not one of
  its three input files or its output file;
- tools: the tool calls by name, and any call that looks like code generating
  labels (python, node, jq, awk, a loop or a regular expression over items).

This is a screen, not a verdict. The maintainer still reads every flagged
call, and samples the rest, before labels are accepted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FORBIDDEN = [
    "lexinspect",
    "study4",
    "Study 4",
    "webapps",
    "lexinspect-private",
    "gitStatus",
    "Current branch:",
    "Recent commits:",
    "Is directory a git repo: yes",
    "When a step doesn't need my input",  # the user's ~/.claude/CLAUDE.md
    "preregistration",
    "fix-check",
    "fixcheck",
]
CODE_HINTS = re.compile(
    r"\b(python3?|node|jq|awk|perl|ruby)\b|for\s+\w+\s+in\b|\bwhile\b|re\.(sub|match|search)|"
    r"\.map\(|JSON\.parse|json\.loads|readFileSync|split\(['\"]\\n",
)
PATH_RE = re.compile(r"(/(?:private/)?(?:var|tmp|Users|etc|opt)/[^\s\"'\\)\]>,;]+)")


def context_text(d: Path, role: str) -> str:
    """The injected context only: never tool outputs, which quote the guidelines."""
    parts: list[str] = []
    if role == "A" and (d / "transcript.jsonl").exists():
        for line in (d / "transcript.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("type") == "attachment":
                parts.append(json.dumps(r, ensure_ascii=False))
            elif r.get("type") == "user" and isinstance(r["message"].get("content"), str):
                parts.append(r["message"]["content"])
    elif role == "B" and (d / "rollout.jsonl").exists():
        for line in (d / "rollout.jsonl").read_text().splitlines():
            r = json.loads(line)
            p = r.get("payload", {})
            if (
                r.get("type") == "session_meta"
                or isinstance(p, dict)
                and p.get("type") == "message"
                and p.get("role") != "assistant"
            ):
                parts.append(json.dumps(p, ensure_ascii=False))
    elif role == "C" and (d / "opencode_session.json").exists():
        s = json.loads((d / "opencode_session.json").read_text())
        parts += [v or "" for v in s["instruction_blobs"].values()]
        parts += [json.dumps(m, ensure_ascii=False) for m in s["messages"] if m["type"] == "user"]
    return "\n".join(parts)


def tool_calls(d: Path, role: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    if role == "A" and (d / "transcript.jsonl").exists():
        for line in (d / "transcript.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("type") != "assistant":
                continue
            for c in r["message"].get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    calls.append((c["name"], json.dumps(c["input"], ensure_ascii=False)))
    elif role == "B" and (d / "rollout.jsonl").exists():
        for line in (d / "rollout.jsonl").read_text().splitlines():
            p = json.loads(line).get("payload", {})
            if isinstance(p, dict) and p.get("type", "").endswith("call"):
                arg = p.get("arguments") or p.get("input") or p.get("action") or ""
                calls.append(
                    (p.get("name") or p["type"], arg if isinstance(arg, str) else json.dumps(arg))
                )
    elif role == "C" and (d / "opencode_session.json").exists():
        s = json.loads((d / "opencode_session.json").read_text())
        for m in s["messages"]:
            for c in m["data"].get("content", []) or []:
                if isinstance(c, dict) and c.get("type") in ("tool", "tool-call", "tool_call"):
                    calls.append(
                        (
                            c.get("name") or c.get("tool") or "tool",
                            json.dumps((c.get("state") or {}).get("input"), ensure_ascii=False),
                        )
                    )
    return calls


def screen(d: Path) -> dict[str, Any]:
    rec = json.loads((d / "session.json").read_text())
    role, workdir = rec["role"], rec["workdir"]
    allowed = {
        f"{workdir}/{n}"
        for n in ("guidelines.md", "phrase_sense_inventory.md", "items.jsonl", "labels.jsonl")
    }
    allowed |= {a.replace("/var/", "/private/var/", 1) for a in allowed}
    ctx = context_text(d, role)
    # The prompt itself names the workdir; the forbidden list never matches it.
    hits = {w: ctx.count(w) for w in FORBIDDEN if w in ctx}
    calls = tool_calls(d, role)
    other_paths: set[str] = set()
    code_like: list[str] = []
    for name, arg in calls:
        for p in PATH_RE.findall(arg.replace("\\n", " ")):
            p = p.rstrip(".:")
            if p not in allowed and p.rstrip("/") not in (workdir, "/private" + workdir):
                other_paths.add(p)
        if CODE_HINTS.search(arg):
            code_like.append(f"{name}: {arg[:300]}")
    return {
        "role": role,
        "token": rec["token"],
        "label": rec["label"],
        "status": rec["status"],
        "context_forbidden_hits": hits,
        "n_tool_calls": len(calls),
        "tools": sorted({n for n, _ in calls}),
        "other_paths": sorted(other_paths),
        "code_like_calls": code_like,
        "flag": bool(hits or other_paths or code_like or rec["status"] != "delivered"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("archive", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    out = [screen(p.parent) for p in sorted(args.archive.glob("*/*/session.json"))]
    for r in out:
        print(
            f"{r['role']} {r['token']} {r['label']:<14} {r['status']:<9} calls={r['n_tool_calls']:<3} "
            f"ctx={r['context_forbidden_hits'] or '-'} paths={len(r['other_paths'])} "
            f"code={len(r['code_like_calls'])} {'FLAG' if r['flag'] else 'ok'}"
        )
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return 1 if any(r["flag"] for r in out) else 0


if __name__ == "__main__":
    sys.exit(main())
