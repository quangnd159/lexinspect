"""Study 4 0.4.0 pilot: run one labelling session and archive it.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/launch.py \\
        ROLE ITEMS_FILE ARCHIVE_ROOT [--label NAME]

ROLE is A (Claude Sonnet 5.5, effort high), B (GPT-6.1-Sol, reasoning high) or
C (the adjudicator, DeepSeek V4.1 Flash on OpenCode's free route, variant
high). ITEMS_FILE is a batch, retry or adjudication file of blind item records.

One call is one fresh session:

1. A new directory `$TMPDIR/<12 hex>/<16 hex>` (neutral names, outside any git
   repository; the run stops if it is inside one) gets exactly three files:
   guidelines.md and phrase_sense_inventory.md (checked against the frozen
   SHA-256s) and items.jsonl (a byte copy of ITEMS_FILE).
2. The registered prompt (prereg "Prompt given to each model labeller",
   template SHA-256 PROMPT_SHA256) is filled with that directory and the item
   count.
3. The role's CLI runs in that directory with a cleaned environment and the
   settings proved by the context probes (pilot040/probe_*.sh): no git
   context, no user or project instruction files, no memory, no MCP servers;
   role A has only Read, Write and Edit; role B has network access off and
   plugins, apps, hooks, browser and multi-agent features off; role C has web
   fetch, web search and skills denied.
4. Everything is archived under ARCHIVE_ROOT/<role>/<token>/: the CLI's event
   stream, labels.jsonl as delivered, the provider's full session record (the
   effective context: Claude transcript with its prompt snapshots, Codex
   rollout, OpenCode instruction state and messages) and session.json with
   argv, times, exit code and every hash. launch_log.jsonl in ARCHIVE_ROOT
   gets one line per call.

A session is `delivered` only if the CLI exits 0, labels.jsonl exists, the
provider session id is recovered from the event stream and the provider's
session record is archived with its expected context (check_sessions.py,
context_failures). Anything else is recorded as `technical_failure`, with the
reasons, after archiving everything there is. The script never retries; a
relaunch is a new call with its own directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sessions as CS  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
GUIDELINES = REPO / "docs" / "validation" / "study4-guidelines.md"
INVENTORY = REPO / ".cache" / "validation" / "study4" / "phrase_sense_inventory.md"
GUIDELINES_SHA256 = "276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e"
INVENTORY_SHA256 = "a761f159541023fd51f5ca45e1fc44432b572ab22ffcad74f414b1e35a776a5d"
DELIVERY_SPEC = REPO / "docs" / "validation" / "study4-fix040" / "delivery_spec.json"
PROMPT_SHA256 = "86985e10f3abb87b082ad4059dbeff8bfa36a62c23256c784122cffe362b96ee"
HOME = Path.home()
CLAUDE_CONFIG = HOME / ".claude_extra"
CODEX_SESSIONS = HOME / ".codex" / "sessions"
OPENCODE_DB = HOME / ".local" / "share" / "opencode" / "opencode.db"
CODEX_OFF = [
    "apps",
    "plugins",
    "remote_plugin",
    "hooks",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "image_generation",
    "multi_agent",
    "skill_search",
    "skill_mcp_dependency_install",
    "goals",
    "tool_suggest",
    "in_app_browser",
]
OPENCODE_CONFIG = '{"permission": {"webfetch": "deny", "websearch": "deny", "skill": "deny"}}'
MODELS = {
    "A": "claude-sonnet-5-5 (Claude Code, account claude_extra, effort high)",
    "B": "gpt-6.1-sol (codex exec, reasoning high)",
    "C": "opencode/deepseek-v4.1-flash-free (opencode run, variant high)",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def prompt_template() -> str:
    t = json.loads(DELIVERY_SPEC.read_text())["prompt_template"]
    if hashlib.sha256(t.encode()).hexdigest() != PROMPT_SHA256:
        raise SystemExit("prompt template does not match its registered SHA-256")
    return t


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: os.environ[k] for k in ("HOME", "PATH", "USER", "TMPDIR") if k in os.environ}
    return env | {"LANG": "en_US.UTF-8"} | extra


def argv_for(role: str, workdir: Path, prompt: str) -> tuple[list[str], dict[str, str]]:
    if role == "A":
        argv = ["claude", "-p", prompt, "--model", "claude-sonnet-5-5", "--effort", "high"]
        argv += ["--tools", "Read,Write,Edit", "--strict-mcp-config"]
        argv += ["--permission-mode", "acceptEdits", "--settings", '{"autoMemoryEnabled": false}']
        argv += ["--output-format", "stream-json", "--verbose"]
        return argv, clean_env(CLAUDE_CONFIG_DIR=str(CLAUDE_CONFIG))
    if role == "B":
        argv = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"]
        argv += ["-C", str(workdir), "-m", "gpt-6.1-sol", "-c", 'model_reasoning_effort="high"']
        argv += ["-c", 'web_search="disabled"', "-s", "workspace-write"]
        for f in CODEX_OFF:
            argv += ["--disable", f]
        argv += ["--json", prompt]
        return argv, clean_env()
    argv = ["opencode", "run", "--standalone", "--auto"]
    argv += ["--model", "opencode/deepseek-v4.1-flash-free#high", "--format", "json", prompt]
    return argv, clean_env(
        OPENCODE_DISABLE_CLAUDE_CODE="1", OPENCODE_CONFIG_CONTENT=OPENCODE_CONFIG
    )


def session_id(role: str, stream: Path) -> str | None:
    return CS.stream_session_id(role, stream)


def archive_context(role: str, sid: str | None, dest: Path) -> list[str]:
    """Copy the provider's own session record: the effective context."""
    if sid is None:
        return []
    out: list[str] = []
    if role == "A":
        for f in (CLAUDE_CONFIG / "projects").glob(f"*/{sid}.jsonl"):
            shutil.copy2(f, dest / "transcript.jsonl")
            out.append(str(f))
    elif role == "B":
        for f in CODEX_SESSIONS.rglob(f"*{sid}*.jsonl"):
            shutil.copy2(f, dest / "rollout.jsonl")
            out.append(str(f))
    else:
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
        msgs = con.execute(
            "select seq, type, data from session_message where session_id=? order by seq", (sid,)
        ).fetchall()
        state = con.execute(
            "select initial_values, current_values from instruction_state where session_id=?",
            (sid,),
        ).fetchone()
        blobs: dict[str, str | None] = {}
        if state:
            for vals in state:
                for h in json.loads(vals).values():
                    row = con.execute(
                        "select value from instruction_blob where hash=?", (h,)
                    ).fetchone()
                    blobs[h] = row[0] if row else None
        con.close()
        rec = {
            "session_id": sid,
            "instruction_state": {
                "initial": json.loads(state[0]) if state else None,
                "current": json.loads(state[1]) if state else None,
            },
            "instruction_blobs": blobs,
            "messages": [{"seq": s, "type": t, "data": json.loads(d)} for s, t, d in msgs],
        }
        (dest / "opencode_session.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        out.append(f"{OPENCODE_DB}#session={sid}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", choices=("A", "B", "C"))
    ap.add_argument("items", type=Path)
    ap.add_argument("archive", type=Path)
    ap.add_argument("--label", default="", help="free-text name recorded in the log")
    args = ap.parse_args(argv)
    for path, want in ((GUIDELINES, GUIDELINES_SHA256), (INVENTORY, INVENTORY_SHA256)):
        if sha256(path) != want:
            raise SystemExit(f"{path} does not match its frozen SHA-256")
    template = prompt_template()
    lines = args.items.read_text(encoding="utf-8").splitlines()
    n = sum(1 for line in lines if line.strip())
    token = secrets.token_hex(8)
    workdir = Path(os.environ["TMPDIR"]) / secrets.token_hex(6) / token
    workdir.mkdir(parents=True)
    probe = subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "--git-dir"], capture_output=True
    )
    if probe.returncode == 0:
        raise SystemExit(f"{workdir} is inside a git repository")
    shutil.copyfile(GUIDELINES, workdir / "guidelines.md")
    shutil.copyfile(INVENTORY, workdir / "phrase_sense_inventory.md")
    shutil.copyfile(args.items, workdir / "items.jsonl")
    prompt = template.replace("⟨dir⟩", str(workdir)).replace("⟨n⟩", str(n))
    cmd, env = argv_for(args.role, workdir, prompt)
    dest = args.archive.resolve() / args.role / token
    dest.mkdir(parents=True)
    stream = dest / "stream.jsonl"
    started = now()
    with stream.open("w") as so, (dest / "stderr.log").open("w") as se:
        rc = subprocess.run(
            cmd, cwd=workdir, env=env, stdin=subprocess.DEVNULL, stdout=so, stderr=se
        )
    ended = now()
    labels = workdir / "labels.jsonl"
    delivered = labels.exists()
    if delivered:
        shutil.copy2(labels, dest / "labels.jsonl")
    sid = session_id(args.role, stream)
    reasons: list[str] = []
    try:
        ctx = archive_context(args.role, sid, dest)
    except Exception as e:  # archive what there is; the session is not delivered
        ctx = []
        reasons.append(f"context archiving failed: {e!r}")
    if rc.returncode != 0:
        reasons.append(f"exit code {rc.returncode}")
    if not delivered:
        reasons.append("no labels file")
    if sid is not None and len(ctx) != 1:
        reasons.append(f"{len(ctx)} provider session records found (need 1)")
    reasons += CS.context_failures(dest, args.role, sid, prompt)
    rec: dict[str, Any] = {
        "role": args.role,
        "label": args.label,
        "model": MODELS[args.role],
        "token": token,
        "workdir": str(workdir),
        "argv": cmd,
        "env": env,
        "prompt": prompt,
        "prompt_template_sha256": PROMPT_SHA256,
        "inputs": {
            "items_source": str(args.items.resolve()),
            "items_sha256": sha256(workdir / "items.jsonl"),
            "n_items": n,
            "guidelines_sha256": GUIDELINES_SHA256,
            "inventory_sha256": INVENTORY_SHA256,
        },
        "started": started,
        "ended": ended,
        "exit_code": rc.returncode,
        "session_id": sid,
        "context_sources": ctx,
        "labels_delivered": delivered,
        "labels_sha256": sha256(dest / "labels.jsonl") if delivered else None,
        "status": "technical_failure" if reasons else "delivered",
        "failure_reasons": reasons,
    }
    files = sorted(p.name for p in dest.iterdir())
    rec["archive_sha256"] = {f: sha256(dest / f) for f in files}
    (dest / "session.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    with (args.archive / "launch_log.jsonl").open("a") as log:
        keys = ("role", "label", "token", "started", "ended", "exit_code", "session_id", "status")
        log.write(
            json.dumps({k: rec[k] for k in keys} | {"items_sha256": rec["inputs"]["items_sha256"]})
            + "\n"
        )
    print(json.dumps({k: rec[k] for k in ("role", "label", "token", "status", "exit_code")}))
    return 0 if rec["status"] == "delivered" else 1


if __name__ == "__main__":
    sys.exit(main())
