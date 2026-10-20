"""Study 4 0.4.0 pilot: screen archived labelling sessions.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/check_sessions.py \\
        ARCHIVE_ROOT [--expect ROLE=MANIFEST ...] [--json OUT]

Every session directory archived by launch.py (ARCHIVE_ROOT/<role>/<token>/)
gets one status:

- technical_failure: the record can't support acceptance. session.json is
  missing or unreadable; the session is not `delivered`; the provider session
  id is absent, or differs from the one in the event stream; an archived file
  is missing, unlisted or doesn't match its SHA-256 in session.json; or the
  provider's session record (the effective context) is missing, unreadable,
  empty or lacks its expected fields: for A, a transcript with the session id,
  a non-empty prompt snapshot and the archived prompt; for B, a rollout with
  one session_meta (session id, base instructions) and the archived prompt as
  a user message; for C, the OpenCode export with the session id, non-empty
  instruction state whose every blob is present and non-empty, and the
  archived prompt as a user message.
- flagged: the context contains a repository, study or private-path marker,
  a git-status block or the user's own instruction file; a tool call names an
  absolute path that is not one of the session's own files; a call looks like
  code generating labels; or a call has a review item. Review items are
  relative paths (./, ../, bare names given to a command or patch) that
  resolve outside the session's files, ~/, $HOME and file:// paths, globs,
  shell commands other than cat, sed, head, tail, wc and nl, and tools the
  role was not given.
- clean: none of the above.

The archive as a whole fails when it holds no session, when launch_log.jsonl
is missing or empty, when a logged session has no archive (or an archived one
is not logged), or when a log line disagrees with its session.json. Each
`--expect ROLE=MANIFEST` (ROLE A, B, C or adjudicator; MANIFEST an assignment
manifest from batches.py) requires exactly one delivered session per assigned
batch. A missing archive stops acceptance pending technical recovery: the
screen never generates a label or chooses a response.

The exit status is 0 only when every session is clean and the archive has no
problem. This is a screen, not a verdict: the maintainer still reads every
flagged call, every command, relative path and file read, and samples the
rest, before labels are accepted.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shlex
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
_TAIL = r"[^\s\"'\\)\]>,;]"
PATH_RE = re.compile(
    r"(file://" + _TAIL + r"+"
    r"|/(?:private/)?(?:var|tmp|Users|etc|opt|home|root|usr|bin|sbin|dev|Library|System|"
    r"Volumes|Applications)/" + _TAIL + r"+"
    r"|(?<![\w~])~[\w.-]*/" + _TAIL + r"*"
    r"|\$\{?HOME\}?/" + _TAIL + r"*)"
)

ROLES = ("A", "B", "C")
SESSION_ROLE = {"A": "A", "B": "B", "C": "C", "adjudicator": "C"}
CONTEXT_FILE = {"A": "transcript.jsonl", "B": "rollout.jsonl", "C": "opencode_session.json"}
OWN_FILES = ("guidelines.md", "phrase_sense_inventory.md", "items.jsonl", "labels.jsonl")
EXPECTED_TOOLS = {
    "A": {"Read", "Write", "Edit"},
    "B": {"exec", "exec_command", "shell", "apply_patch"},
    "C": {"read", "write", "edit"},
}
CODEX_INNER_TOOLS = {"exec_command", "apply_patch"}
SHELL_FILE_CMDS = {"cat", "sed", "head", "tail", "wc", "nl"}
PATH_KEYS = {"file_path", "filePath", "path", "notebook_path", "dir", "directory", "cwd", "workdir"}
SHELL_KEYS = {"command", "cmd"}
_STR = r"\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'|`([^`]*)`"
JS_CMD = re.compile(r"\bcmd\s*:\s*(?:" + _STR + r")", re.S)
JS_TOOL = re.compile(r"\btools\.(\w+)\s*\(")
PATCH_HEADER = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): *(.+?) *$", re.M)
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n(?:.*?\n)??[ \t]*\2[ \t]*(?:\n|\Z)", re.S)
HEREDOC_OPEN = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n.*\Z", re.S)
SHELL_OPS = set(";&|()")


class TechnicalFailure(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stream_session_id(role: str, stream: Path) -> str | None:
    """The provider session id announced in the CLI's event stream."""
    for line in stream.read_text(errors="replace").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict):
            continue
        if role == "A" and r.get("type") == "system" and r.get("session_id"):
            return r["session_id"]
        if role == "B" and r.get("type") == "thread.started":
            return r.get("thread_id")
        if role == "C" and r.get("sessionID"):
            return r["sessionID"]
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise TechnicalFailure(f"{path.name} missing")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise TechnicalFailure(f"{path.name} unreadable: {e}") from e
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            raise TechnicalFailure(f"{path.name} line {i} is not JSON") from e
        if not isinstance(r, dict):
            raise TechnicalFailure(f"{path.name} line {i} is not an object")
        rows.append(r)
    if not rows:
        raise TechnicalFailure(f"{path.name} empty")
    return rows


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise TechnicalFailure(f"{path.name} missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise TechnicalFailure(f"{path.name} unreadable: {e}") from e


def context_failures(d: Path, role: str, sid: str | None, prompt: str | None) -> list[str]:
    """Why the provider's session record can't stand as the effective context."""
    if not sid:
        return ["provider session id absent"]
    if not prompt:
        return ["archived prompt absent"]
    out: list[str] = []
    try:
        if role == "A":
            rows = _read_jsonl(d / "transcript.jsonl")
            sids = {r.get("sessionId") for r in rows if "sessionId" in r}
            if sids != {sid}:
                out.append(f"transcript session ids {sorted(map(str, sids))} != {sid}")
            snaps = [
                r
                for r in rows
                if r.get("type") == "attachment"
                and isinstance(r.get("attachment"), dict)
                and r["attachment"].get("type") == "prompt_snapshot"
                and r["attachment"].get("systemPrompt")
            ]
            if not snaps:
                out.append("transcript has no non-empty prompt snapshot")
            users = [
                r["message"]["content"]
                for r in rows
                if r.get("type") == "user"
                and isinstance(r.get("message"), dict)
                and isinstance(r["message"].get("content"), str)
            ]
            if not any(prompt in u for u in users):
                out.append("transcript does not contain the archived prompt")
        elif role == "B":
            rows = _read_jsonl(d / "rollout.jsonl")
            metas = [
                r["payload"]
                for r in rows
                if r.get("type") == "session_meta" and isinstance(r.get("payload"), dict)
            ]
            if len(metas) != 1:
                out.append(f"rollout has {len(metas)} session_meta records (need 1)")
            elif sid not in (metas[0].get("id"), metas[0].get("session_id")):
                out.append(f"rollout session_meta id {metas[0].get('id')} != {sid}")
            elif not (metas[0].get("base_instructions") or {}).get("text"):
                out.append("rollout session_meta has no base instructions")
            texts = [
                c.get("text") or ""
                for r in rows
                if isinstance(p := r.get("payload"), dict)
                and p.get("type") == "message"
                and p.get("role") == "user"
                for c in (p.get("content") or [])
                if isinstance(c, dict)
            ]
            if not any(prompt in t for t in texts):
                out.append("rollout does not contain the archived prompt as a user message")
        else:
            s = _read_json(d / "opencode_session.json")
            if not isinstance(s, dict):
                raise TechnicalFailure("opencode_session.json is not an object")
            if s.get("session_id") != sid:
                out.append(f"OpenCode record session id {s.get('session_id')} != {sid}")
            state = s.get("instruction_state") or {}
            blobs = s.get("instruction_blobs") or {}
            refs: set[str] = set()
            for k in ("initial", "current"):
                v = state.get(k) if isinstance(state, dict) else None
                if not isinstance(v, dict) or not v:
                    out.append(f"OpenCode instruction_state.{k} missing or empty")
                else:
                    refs |= {str(h) for h in v.values()}
            empty = sorted(h for h in refs if not (isinstance(blobs, dict) and blobs.get(h)))
            if empty:
                out.append(f"OpenCode instruction blobs missing or empty: {len(empty)}")
            msgs = s.get("messages")
            if not isinstance(msgs, list) or not msgs:
                out.append("OpenCode messages missing or empty")
                msgs = []
            texts = [
                str((m.get("data") or {}).get("text") or "")
                for m in msgs
                if isinstance(m, dict) and m.get("type") == "user"
            ]
            if not any(prompt in t for t in texts):
                out.append("OpenCode messages do not contain the archived prompt")
    except TechnicalFailure as e:
        out.append(str(e))
    return out


def archive_failures(d: Path, rec: dict[str, Any]) -> list[str]:
    """Record-level checks: identity, delivery, session id and every archived hash."""
    out: list[str] = []
    role, token = rec.get("role"), rec.get("token")
    if role not in ROLES or d.parent.name != role:
        out.append(f"role {role!r} does not match directory {d.parent.name}")
    if token != d.name:
        out.append(f"token {token!r} does not match directory {d.name}")
    if not rec.get("workdir"):
        out.append("workdir absent")
    if rec.get("status") != "delivered":
        out.append(f"session status is {rec.get('status')!r}, not 'delivered'")
    sid = rec.get("session_id")
    if not sid:
        out.append("provider session id absent")
    hashes = rec.get("archive_sha256")
    if not isinstance(hashes, dict) or not hashes:
        out.append("archive_sha256 missing or empty")
        hashes = {}
    need = {"stream.jsonl", "labels.jsonl"} | ({CONTEXT_FILE[role]} if role in ROLES else set())
    for f in sorted(need - set(hashes)):
        out.append(f"{f} not in archive_sha256")
    for f, want in sorted(hashes.items()):
        p = d / f
        if not p.is_file():
            out.append(f"{f} listed but missing")
        elif sha256(p) != want:
            out.append(f"{f} does not match its archived SHA-256")
    unlisted = sorted(p.name for p in d.iterdir() if p.name != "session.json") if d.is_dir() else []
    for f in unlisted:
        if f not in hashes:
            out.append(f"{f} present but not in archive_sha256")
    lab = d / "labels.jsonl"
    if not rec.get("labels_delivered") or not lab.is_file():
        out.append("labels not delivered")
    elif sha256(lab) != rec.get("labels_sha256"):
        out.append("labels.jsonl does not match labels_sha256")
    stream = d / "stream.jsonl"
    if sid and role in ROLES and stream.is_file():
        got = stream_session_id(role, stream)
        if got != sid:
            out.append(f"event stream session id {got} != recorded {sid}")
    return out


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


def _own_paths(workdir: str) -> tuple[set[str], set[str]]:
    dirs = {workdir.rstrip("/"), "/private" + workdir.rstrip("/")}
    files = {f"{w}/{n}" for w in dirs for n in OWN_FILES}
    return files, dirs


def _resolve(token: str, workdir: str) -> str | None:
    """None if `token` names one of the session's own files or its directory."""
    raw, t = token, token
    if t.startswith("file://"):
        t = t[len("file://") :]
    if t.startswith("~") or "$" in t:
        return f"{raw} (home or variable path)"
    if any(c in t for c in "*?["):
        return f"{raw} (glob)"
    p = os.path.normpath(t if t.startswith("/") else os.path.join(workdir, t))
    files, dirs = _own_paths(workdir)
    return None if p in files or p in dirs else f"{raw} -> {p}"


def _path_like(t: str) -> bool:
    if re.fullmatch(r"[\d.,:]+", t):
        return False
    return (
        "/" in t
        or t.startswith(("~", ".", "$"))
        or any(c in t for c in "*?[")
        or re.fullmatch(r"[\w.-]*\.\w{1,10}", t) is not None
    )


def _js_string(m: re.Match[str]) -> str:
    dq, sq, bt = m.groups()
    if bt is not None:
        return bt
    s = dq if dq is not None else re.sub(r'(?<!\\)"', '\\"', sq.replace("\\'", "'"))
    try:
        return json.loads('"' + s + '"')
    except json.JSONDecodeError:
        return s.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")


def shell_review(cmd: str, workdir: str) -> list[str]:
    """Commands other than plain file reads/writes, and paths outside the session's files."""
    out: list[str] = []
    text = HEREDOC_OPEN.sub(r"\3\n", HEREDOC.sub(r"\3\n", cmd))
    for line in text.splitlines():
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError:
            toks = line.split()
        segs: list[list[str]] = [[]]
        for t in toks:
            if t and set(t) <= SHELL_OPS:
                segs.append([])
            else:
                segs[-1].append(t)
        for seg in segs:
            while seg and re.match(r"^\w+=", seg[0]):
                out.append(f"variable assignment: {seg[0][:120]}")
                seg = seg[1:]
            if not seg:
                continue
            if os.path.basename(seg[0]) not in SHELL_FILE_CMDS:
                out.append(f"command: {' '.join(seg)[:200]}")
            for i, t in enumerate(seg):
                if (i == 0 and "/" not in t) or t.startswith("-") or set(t) <= set("<>&0123456789"):
                    continue
                if _path_like(t) and (r := _resolve(t, workdir)):
                    out.append(f"path: {r}")
    return out


def _walk_json(v: Any, workdir: str, out: list[str]) -> None:
    if isinstance(v, dict):
        for k, x in v.items():
            if k in PATH_KEYS and isinstance(x, str):
                if r := _resolve(x, workdir):
                    out.append(f"path: {r}")
            elif k in SHELL_KEYS and isinstance(x, str):
                out += shell_review(x, workdir)
            elif k in SHELL_KEYS and isinstance(x, list) and all(isinstance(a, str) for a in x):
                script = x[-1] if len(x) >= 3 and x[-2] in ("-c", "-lc") else shlex.join(x)
                out += shell_review(script, workdir)
            else:
                _walk_json(x, workdir, out)
    elif isinstance(v, list):
        for x in v:
            _walk_json(x, workdir, out)


def call_review(role: str, name: str, arg: str, workdir: str) -> list[str]:
    """Review items for one tool call: never a pass/fail by itself."""
    out: list[str] = []
    if name not in EXPECTED_TOOLS[role]:
        out.append(f"tool not given to role {role}: {name}")
    try:
        parsed = json.loads(arg)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, (dict, list)):
        _walk_json(parsed, workdir, out)
    else:
        for t in JS_TOOL.findall(arg):
            if t not in CODEX_INNER_TOOLS:
                out.append(f"tool not given to role {role}: tools.{t}")
        for m in JS_CMD.finditer(arg):
            out += shell_review(_js_string(m), workdir)
    for p in PATCH_HEADER.findall(arg.replace("\\n", "\n")):
        if r := _resolve(p.strip().strip('"'), workdir):
            out.append(f"path: {r}")
    return [f"{name}: {x}" for x in dict.fromkeys(out)]


def screen(d: Path) -> dict[str, Any]:
    res: dict[str, Any] = {
        "role": d.parent.name,
        "token": d.name,
        "label": "",
        "session_status": None,
        "session_json_sha256": None,
        "technical_failures": [],
        "context_forbidden_hits": {},
        "n_tool_calls": 0,
        "tools": [],
        "other_paths": [],
        "code_like_calls": [],
        "review": [],
    }
    fails: list[str] = res["technical_failures"]
    try:
        rec = _read_json(d / "session.json")
        if not isinstance(rec, dict):
            raise TechnicalFailure("session.json is not an object")
    except TechnicalFailure as e:
        fails.append(str(e))
        return _finish(res)
    res["session_json_sha256"] = sha256(d / "session.json")
    role, workdir = rec.get("role"), str(rec.get("workdir") or "")
    res |= {"label": rec.get("label", ""), "session_status": rec.get("status")}
    fails += archive_failures(d, rec)
    if role not in ROLES:
        return _finish(res)
    ctx_fail = context_failures(d, role, rec.get("session_id"), rec.get("prompt"))
    fails += ctx_fail
    if any(f.startswith(CONTEXT_FILE[role]) for f in ctx_fail):
        return _finish(res)  # missing or unreadable: nothing to screen
    try:
        ctx = context_text(d, role)
        calls = tool_calls(d, role)
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as e:
        fails.append(f"{CONTEXT_FILE[role]} lacks expected fields: {e!r}")
        return _finish(res)
    if not ctx.strip():
        fails.append("injected context is empty")
    allowed, dirs = _own_paths(workdir)
    # The prompt itself names the workdir; the forbidden list never matches it.
    hits = {w: ctx.count(w) for w in FORBIDDEN if w in ctx}
    other_paths: set[str] = set()
    code_like: list[str] = []
    review: list[str] = []
    for name, arg in calls:
        for p in PATH_RE.findall(arg.replace("\\n", " ")):
            p = p.rstrip(".:")
            bare = p[len("file://") :] if p.startswith("file://") else p
            if bare not in allowed and bare.rstrip("/") not in dirs:
                other_paths.add(p)
        if CODE_HINTS.search(arg):
            code_like.append(f"{name}: {arg[:300]}")
        review += call_review(role, name, arg, workdir)
    res |= {
        "context_forbidden_hits": hits,
        "n_tool_calls": len(calls),
        "tools": sorted({n for n, _ in calls}),
        "other_paths": sorted(other_paths),
        "code_like_calls": code_like,
        "review": list(dict.fromkeys(review)),
    }
    return _finish(res)


def _finish(res: dict[str, Any]) -> dict[str, Any]:
    res["technical_failures"] = list(dict.fromkeys(res["technical_failures"]))
    if res["technical_failures"]:
        res["status"] = "technical_failure"
    elif (
        res["context_forbidden_hits"]
        or res["other_paths"]
        or res["code_like_calls"]
        or res["review"]
    ):
        res["status"] = "flagged"
    else:
        res["status"] = "clean"
    res["flag"] = res["status"] != "clean"
    return res


def session_dirs(root: Path) -> list[Path]:
    return sorted(
        p for r in ROLES if (root / r).is_dir() for p in (root / r).iterdir() if p.is_dir()
    )


def inventory_problems(root: Path, dirs: list[Path]) -> list[str]:
    """The archive against its own launch log: nothing missing, nothing extra."""
    if not root.is_dir():
        return [f"archive root {root} does not exist"]
    out: list[str] = []
    if not dirs:
        out.append("no archived session under the archive root")
    try:
        log = _read_jsonl(root / "launch_log.jsonl")
    except TechnicalFailure as e:
        return out + [f"launch log: {e}"]
    logged: dict[tuple[str, str], dict[str, Any]] = {}
    for r in log:
        key = (str(r.get("role")), str(r.get("token")))
        if key in logged:
            out.append(f"launch log lists {key[0]}/{key[1]} twice")
        logged[key] = r
    archived = {(d.parent.name, d.name): d for d in dirs}
    for key in sorted(logged.keys() - archived.keys()):
        out.append(
            f"logged session {key[0]}/{key[1]} has no archive: acceptance stops pending "
            "technical recovery (no label is generated or chosen)"
        )
    for key in sorted(archived.keys() - logged.keys()):
        out.append(f"archived session {key[0]}/{key[1]} is not in the launch log")
    for key in sorted(logged.keys() & archived.keys()):
        try:
            rec = json.loads((archived[key] / "session.json").read_text(encoding="utf-8"))
            got = (rec.get("inputs") or {}).get("items_sha256")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue  # reported as a technical failure of the session
        for k in ("status", "session_id", "exit_code"):
            if logged[key].get(k) != rec.get(k):
                out.append(f"{key[0]}/{key[1]}: launch log {k} differs from session.json")
        if logged[key].get("items_sha256") != got:
            out.append(f"{key[0]}/{key[1]}: launch log items_sha256 differs from session.json")
    return out


def coverage(root: Path, dirs: list[Path], expect: list[str]) -> list[dict[str, Any]]:
    """Each assigned batch against the delivered sessions archived for its role."""
    recs: list[dict[str, Any]] = []
    for d in dirs:
        with contextlib.suppress(OSError, json.JSONDecodeError):
            recs.append(json.loads((d / "session.json").read_text(encoding="utf-8")))
    out: list[dict[str, Any]] = []
    for spec in expect:
        role, _, path = spec.partition("=")
        entry: dict[str, Any] = {"expect": spec, "problems": [], "batches": []}
        out.append(entry)
        if role not in SESSION_ROLE or not path:
            entry["problems"].append("expected ROLE=MANIFEST with ROLE in A, B, C, adjudicator")
            continue
        try:
            batches = _read_json(Path(path)).get("batches") or []
        except (TechnicalFailure, AttributeError) as e:
            entry["problems"].append(f"manifest unreadable: {e}")
            continue
        if not batches:
            entry["problems"].append("assignment manifest lists no batch")
        for b in batches:
            same = [
                r
                for r in recs
                if r.get("role") == SESSION_ROLE[role]
                and (r.get("inputs") or {}).get("items_sha256") == b.get("sha256")
            ]
            done = [r for r in same if r.get("status") == "delivered"]
            entry["batches"].append(
                {
                    "batch": b.get("batch"),
                    "delivered_tokens": [r.get("token") for r in done],
                    "other_tokens": [
                        f"{r.get('token')}:{r.get('status')}" for r in same if r not in done
                    ],
                }
            )
            if not done:
                entry["problems"].append(
                    f"batch {b.get('batch')}: no delivered session archived; acceptance stops "
                    "pending technical recovery (no label is generated or chosen)"
                )
            elif len(done) > 1:
                entry["problems"].append(f"batch {b.get('batch')}: {len(done)} delivered sessions")
    return out


def screen_archive(root: Path, expect: list[str] | None = None) -> dict[str, Any]:
    dirs = session_dirs(root) if root.is_dir() else []
    sessions = [screen(d) for d in dirs]
    inv = inventory_problems(root, dirs)
    cov = coverage(root, dirs, expect or [])
    ok = bool(sessions) and not inv and all(s["status"] == "clean" for s in sessions)
    ok = ok and not any(c["problems"] for c in cov)
    return {
        "archive": str(root),
        "check_sessions_sha256": sha256(Path(__file__)),
        "ok": ok,
        "inventory_problems": inv,
        "coverage": cov,
        "sessions": sessions,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("archive", type=Path)
    ap.add_argument("--expect", action="append", default=[], metavar="ROLE=MANIFEST")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    out = screen_archive(args.archive, args.expect)
    for r in out["sessions"]:
        print(
            f"{r['role']} {r['token']} {r['label']:<14} {r['session_status']!s:<9} "
            f"calls={r['n_tool_calls']:<3} ctx={r['context_forbidden_hits'] or '-'} "
            f"paths={len(r['other_paths'])} code={len(r['code_like_calls'])} "
            f"review={len(r['review'])} {r['status'].upper()}"
        )
        for f in r["technical_failures"]:
            print(f"    technical failure: {f}")
    for p in out["inventory_problems"]:
        print(f"ARCHIVE: {p}")
    for c in out["coverage"]:
        for p in c["problems"]:
            print(f"COVERAGE {c['expect']}: {p}")
    print("ok" if out["ok"] else "NOT ACCEPTABLE AS IS: see above")
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
