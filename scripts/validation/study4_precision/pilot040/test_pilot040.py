"""Tests for the 0.4.0 pilot launcher, session screen and collector.

    uv run --offline --no-sync python -I -m pytest scripts/validation/study4_precision/pilot040/test_pilot040.py

Fixtures are synthetic records under /tmp. No labelling CLI is ever run: the
launcher tests replace subprocess.run with a fake that refuses anything but
`git` and the role's CLI name and executes neither. The real-archive tests
read the private archive (read-only) and skip when it is absent.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_sessions as CS  # noqa: E402
import collect_role as CR  # noqa: E402
import launch as L  # noqa: E402

PRIVATE = Path.home() / "lexinspect-private" / "study4-pilot040"
REAL_ROOTS = [PRIVATE / "sessions", PRIVATE / "dryrun" / "archive"]
PROMPT = "Label every item.\nFiles: guidelines.md, items.jsonl, labels.jsonl\n"
SID = {"A": "aaaa-1111", "B": "bbbb-2222", "C": "ses_cccc3333"}
TOOL = {"A": "Read", "B": "exec", "C": "read"}
# sha256 of the argv, env and prompt that launch.py builds for a fixed directory,
# environment and item count, taken before the R1-4 changes (see snapshot()).
ARGV_ENV_PROMPT_SHA256 = "2214863e5da56579c8ca47e1b0292a378c819a2f6fc2ca58e164cd989f6ef41b"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def root():
    d = Path(tempfile.mkdtemp(prefix="p040_", dir="/tmp"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def jsonl(path: Path, rows: list) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def tool_args(role: str, workdir: str, call: str | None) -> str:
    if role == "B":
        return call or 'text(await tools.exec_command({cmd:"cat guidelines.md"}))\n'
    key = "file_path" if role == "A" else "path"
    return call or json.dumps({key: f"{workdir}/guidelines.md"})


def write_context(d: Path, role: str, workdir: str, call: str | None = None) -> None:
    sid, args = SID[role], tool_args(role, workdir, call)
    if role == "A":
        jsonl(
            d / "transcript.jsonl",
            [
                {"type": "user", "sessionId": sid, "message": {"content": PROMPT}},
                {
                    "type": "attachment",
                    "sessionId": sid,
                    "attachment": {
                        "type": "prompt_snapshot",
                        "systemPrompt": ["You are an agent."],
                    },
                },
                {
                    "type": "assistant",
                    "sessionId": sid,
                    "message": {
                        "content": [{"type": "tool_use", "name": "Read", "input": json.loads(args)}]
                    },
                },
            ],
        )
    elif role == "B":
        jsonl(
            d / "rollout.jsonl",
            [
                {
                    "type": "session_meta",
                    "payload": {"id": sid, "base_instructions": {"text": "You are Codex."}},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": PROMPT}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {"type": "custom_tool_call", "name": "exec", "input": args},
                },
            ],
        )
    else:
        rec = {
            "session_id": sid,
            "instruction_state": {"initial": {"core/env": "h1"}, "current": {"core/env": "h1"}},
            "instruction_blobs": {"h1": "Is directory a git repo: no"},
            "messages": [
                {"seq": 1, "type": "user", "data": {"text": f'"{PROMPT}"'}},
                {
                    "seq": 2,
                    "type": "assistant",
                    "data": {
                        "content": [
                            {"type": "tool", "tool": "read", "state": {"input": json.loads(args)}}
                        ]
                    },
                },
            ],
        }
        (d / "opencode_session.json").write_text(json.dumps(rec))


def stream_rows(role: str) -> list[dict]:
    sid = SID[role]
    return {
        "A": [{"type": "system", "session_id": sid}],
        "B": [{"type": "thread.started", "thread_id": sid}],
        "C": [{"type": "step_start", "sessionID": sid}],
    }[role]


def seal(d: Path, **over) -> dict:
    """(Re)write session.json with hashes of what is in d now."""
    p = d / "session.json"
    rec = json.loads(p.read_text()) if p.exists() else {}
    rec |= over
    lab = d / "labels.jsonl"
    rec["labels_sha256"] = sha(lab) if lab.exists() else None
    rec["archive_sha256"] = {
        f.name: sha(f) for f in sorted(d.iterdir()) if f.name != "session.json"
    }
    p.write_text(json.dumps(rec))
    return rec


def make_session(
    root: Path, role: str, token: str, *, items_sha: str = "i" * 64, call: str | None = None
) -> Path:
    d = root / role / token
    d.mkdir(parents=True)
    workdir = f"/tmp/p040wd/{token}"
    jsonl(d / "stream.jsonl", stream_rows(role))
    (d / "stderr.log").write_text("")
    jsonl(
        d / "labels.jsonl", [{"id": "x1", "label": "CORRECT", "alt_category": None, "note": None}]
    )
    write_context(d, role, workdir, call)
    rec = seal(
        d,
        role=role,
        label=f"test-{role}",
        token=token,
        workdir=workdir,
        prompt=PROMPT,
        inputs={"items_sha256": items_sha, "n_items": 1},
        exit_code=0,
        session_id=SID[role],
        labels_delivered=True,
        status="delivered",
    )
    log = {k: rec[k] for k in ("role", "label", "token", "exit_code", "session_id", "status")}
    with (root / "launch_log.jsonl").open("a") as f:
        f.write(json.dumps(log | {"items_sha256": items_sha}) + "\n")
    return d


def fix_log(root: Path, d: Path, **over) -> None:
    rows = [json.loads(x) for x in (root / "launch_log.jsonl").read_text().splitlines()]
    for r in rows:
        if r["token"] == d.name:
            r |= over
    jsonl(root / "launch_log.jsonl", rows)


# ---------------------------------------------------------------- the screen


@pytest.mark.parametrize("role", CS.ROLES)
def test_valid_record_is_clean(root, role):
    make_session(root, role, f"tok{role}")
    out = CS.screen_archive(root)
    (s,) = out["sessions"]
    assert s["status"] == "clean", s
    assert s["n_tool_calls"] == 1 and s["tools"] == [TOOL[role]]
    assert out["ok"] and CS.main([str(root)]) == 0


def test_all_three_roles_clean_together(root):
    for r in CS.ROLES:
        make_session(root, r, f"tok{r}")
    assert CS.main([str(root)]) == 0


@pytest.mark.parametrize("role", CS.ROLES)
def test_missing_record_is_technical_failure(root, role):
    """The review's case: delivered, exit 0, labels present, no provider record."""
    d = make_session(root, role, f"tok{role}")
    (d / CS.CONTEXT_FILE[role]).unlink()
    seal(d)  # hashes now honestly describe an archive without the record
    s = CS.screen(d)
    assert s["status"] == "technical_failure"
    assert f"{CS.CONTEXT_FILE[role]} missing" in s["technical_failures"]
    assert s["n_tool_calls"] == 0 and s["flag"] is True
    assert CS.main([str(root)]) == 1


@pytest.mark.parametrize("role", CS.ROLES)
def test_empty_record_is_technical_failure(root, role):
    d = make_session(root, role, f"tok{role}")
    (d / CS.CONTEXT_FILE[role]).write_text("")
    seal(d)
    s = CS.screen(d)
    assert s["status"] == "technical_failure", s
    assert CS.main([str(root)]) == 1


def test_context_without_expected_fields_is_technical_failure(root):
    a = make_session(root, "A", "tokA")
    jsonl(a / "transcript.jsonl", [{"type": "assistant", "sessionId": SID["A"], "message": {}}])
    seal(a)
    b = make_session(root, "B", "tokB")
    jsonl(b / "rollout.jsonl", [{"type": "session_meta", "payload": {"id": SID["B"]}}])
    seal(b)
    c = make_session(root, "C", "tokC")
    rec = json.loads((c / "opencode_session.json").read_text())
    rec["instruction_state"] = {"initial": None, "current": None}
    rec["instruction_blobs"] = {}
    (c / "opencode_session.json").write_text(json.dumps(rec))
    seal(c)
    fails = {s["role"]: s["technical_failures"] for s in CS.screen_archive(root)["sessions"]}
    assert "transcript has no non-empty prompt snapshot" in fails["A"]
    assert "transcript does not contain the archived prompt" in fails["A"]
    assert "rollout session_meta has no base instructions" in fails["B"]
    assert any("prompt" in f for f in fails["B"])
    assert "OpenCode instruction_state.initial missing or empty" in fails["C"]


def test_null_instruction_blob_is_technical_failure(root):
    c = make_session(root, "C", "tokC")
    rec = json.loads((c / "opencode_session.json").read_text())
    rec["instruction_blobs"] = {"h1": None}
    (c / "opencode_session.json").write_text(json.dumps(rec))
    seal(c)
    assert CS.screen(c)["technical_failures"] == ["OpenCode instruction blobs missing or empty: 1"]


@pytest.mark.parametrize("role", CS.ROLES)
def test_session_id_absent_is_technical_failure(root, role):
    d = make_session(root, role, f"tok{role}")
    seal(d, session_id=None)
    assert "provider session id absent" in CS.screen(d)["technical_failures"]


def test_record_for_another_session_is_technical_failure(root):
    d = make_session(root, "B", "tokB")
    seal(d, session_id="someone-else")
    fails = CS.screen(d)["technical_failures"]
    assert any(f.startswith("rollout session_meta id") for f in fails)
    assert any(f.startswith("event stream session id") for f in fails)


@pytest.mark.parametrize("name", ["rollout.jsonl", "labels.jsonl", "stream.jsonl"])
def test_hash_mismatch_is_technical_failure(root, name):
    d = make_session(root, "B", "tokB")
    with (d / name).open("a") as f:
        f.write("\n")
    s = CS.screen(d)
    assert s["status"] == "technical_failure"
    assert f"{name} does not match its archived SHA-256" in s["technical_failures"]


def test_unlisted_file_and_missing_session_json(root):
    d = make_session(root, "A", "tokA")
    (d / "extra.txt").write_text("x")
    assert "extra.txt present but not in archive_sha256" in CS.screen(d)["technical_failures"]
    e = make_session(root, "C", "tokC")
    (e / "session.json").unlink()
    assert CS.screen(e)["technical_failures"] == ["session.json missing"]


@pytest.mark.parametrize("status", ["failed", "technical_failure"])
def test_undelivered_session_is_technical_failure(root, status):
    d = make_session(root, "A", "tokA")
    seal(d, status=status)
    fix_log(root, d, status=status)
    s = CS.screen(d)
    assert s["status"] == "technical_failure"
    assert f"session status is {status!r}, not 'delivered'" in s["technical_failures"]


def test_empty_archive_root_fails(root):
    assert CS.main([str(root)]) == 1
    assert (
        "no archived session under the archive root"
        in CS.screen_archive(root)["inventory_problems"]
    )
    (root / "launch_log.jsonl").write_text("")
    (root / "A").mkdir()
    assert CS.main([str(root)]) == 1
    assert CS.main([str(root / "does-not-exist")]) == 1


def test_logged_session_without_archive_fails(root):
    d = make_session(root, "B", "tokB")
    shutil.rmtree(d)
    make_session(root, "A", "tokA")
    probs = CS.screen_archive(root)["inventory_problems"]
    assert any(p.startswith("logged session B/tokB has no archive") for p in probs)
    assert CS.main([str(root)]) == 1


def test_unlogged_archive_and_log_mismatch_fail(root):
    d = make_session(root, "A", "tokA")
    fix_log(root, d, session_id="other")
    log = (root / "launch_log.jsonl").read_text()
    make_session(root, "C", "tokC")
    (root / "launch_log.jsonl").write_text(log)  # tokC archived but not logged
    probs = CS.screen_archive(root)["inventory_problems"]
    assert "A/tokA: launch log session_id differs from session.json" in probs
    assert "archived session C/tokC is not in the launch log" in probs
    (root / "launch_log.jsonl").unlink()
    assert CS.screen_archive(root)["inventory_problems"] == ["launch log: launch_log.jsonl missing"]


def test_coverage_against_assignments(root):
    make_session(root, "B", "tokB1", items_sha="1" * 64)
    man = root / "manifest.json"
    man.write_text(json.dumps({"batches": [{"batch": 1, "sha256": "1" * 64}]}))
    assert CS.main([str(root), "--expect", f"B={man}"]) == 0
    man.write_text(
        json.dumps(
            {"batches": [{"batch": 1, "sha256": "1" * 64}, {"batch": 2, "sha256": "2" * 64}]}
        )
    )
    (cov,) = CS.screen_archive(root, [f"B={man}"])["coverage"]
    assert cov["problems"][0].startswith("batch 2: no delivered session archived")
    assert CS.main([str(root), "--expect", f"B={man}"]) == 1
    man.write_text(json.dumps({"batches": []}))
    assert CS.screen_archive(root, [f"B={man}"])["coverage"][0]["problems"] == [
        "assignment manifest lists no batch"
    ]
    assert CS.main([str(root), "--expect", f"adjudicator={root / 'nope.json'}"]) == 1


# ------------------------------------------------------ paths and review items


@pytest.mark.parametrize(
    ("role", "call", "needle"),
    [
        ("B", 'text(await tools.exec_command({cmd:"cat ../other/notes.md"}))', "../other/notes.md"),
        ("B", 'text(await tools.exec_command({cmd:"cat ./sub/x.md"}))', "./sub/x.md"),
        ("B", 'text(await tools.exec_command({cmd:"sed -n 1,5p notes.txt"}))', "notes.txt"),
        ("B", 'text(await tools.exec_command({cmd:"cat ~/.zshrc"}))', "~/.zshrc"),
        ("B", 'text(await tools.exec_command({cmd:"ls"}))', "command: ls"),
        ("B", 'text(await tools.exec_command({cmd:"cat *.md"}))', "(glob)"),
        ("B", 'text(await tools.list_dir({path:"."}))', "tools.list_dir"),
        (
            "B",
            'tools.apply_patch("*** Begin Patch\\n*** Add File: ../out.jsonl\\n+x\\n")',
            "../out.jsonl",
        ),
        ("A", json.dumps({"file_path": "../../secret.md"}), "../../secret.md"),
        ("A", json.dumps({"file_path": "file:///etc/hosts"}), "file:///etc/hosts"),
        ("C", json.dumps({"path": "~/notes.md"}), "~/notes.md"),
        ("C", json.dumps({"path": "drafts/a.md"}), "drafts/a.md"),
    ],
)
def test_relative_and_other_paths_are_review_items(root, role, call, needle):
    d = make_session(root, role, f"tok{role}", call=call)
    s = CS.screen(d)
    assert s["status"] == "flagged", s
    assert any(needle in r for r in s["review"]), s["review"]
    assert CS.main([str(root)]) == 1


@pytest.mark.parametrize(
    "cmd",
    [
        "cat guidelines.md phrase_sense_inventory.md",
        "sed -n '180,410p' guidelines.md",
        "cat ./items.jsonl",
        'cat > labels.jsonl <<\'EOF\'\\n{\\"id\\":\\"x\\",\\"note\\":\\"see ../x\\"}\\nEOF',
        "wc -l labels.jsonl",
    ],
)
def test_own_files_by_relative_path_pass(root, cmd):
    d = make_session(root, "B", "tokB", call=f'text(await tools.exec_command({{cmd:"{cmd}"}}))')
    s = CS.screen(d)
    assert s["review"] == [] and s["status"] == "clean", s


def test_absolute_forms_outside_session(root):
    for i, p in enumerate(["/Users/x/notes.md", "~/notes.md", "file:///tmp/x", "$HOME/x"]):
        d = make_session(root, "A", f"tok{i}", call=json.dumps({"file_path": p}))
        s = CS.screen(d)
        assert s["status"] == "flagged" and s["other_paths"], (p, s)


def test_marker_logic_unchanged(root):
    d = make_session(root, "A", "tokA")
    rows = [json.loads(x) for x in (d / "transcript.jsonl").read_text().splitlines()]
    rows[1]["attachment"]["systemPrompt"] = ["gitStatus: Current branch: main"]
    jsonl(d / "transcript.jsonl", rows)
    seal(d)
    s = CS.screen(d)
    assert s["context_forbidden_hits"] == {"gitStatus": 1, "Current branch:": 1}
    assert s["status"] == "flagged"


# ------------------------------------------------------------ the launcher


def snapshot() -> str:
    env = {"HOME": "/h", "PATH": "/p", "USER": "u", "TMPDIR": "/t/", "EXTRA": "x"}
    old = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        wd = Path("/t/aaaaaaaaaaaa/bbbbbbbbbbbbbbbb")
        prompt = L.prompt_template().replace("⟨dir⟩", str(wd)).replace("⟨n⟩", "7")
        out = {r: L.argv_for(r, wd, prompt) for r in "ABC"}
    finally:
        os.environ.clear()
        os.environ.update(old)
    blob = json.dumps({"prompt": prompt, "argv_env": out}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def test_argv_env_prompt_byte_identical_to_pre_change_snapshot(monkeypatch):
    # CLAUDE_CONFIG is fixed at import from the real home; the snapshot used HOME=/h.
    monkeypatch.setattr(L, "CLAUDE_CONFIG", Path("/h") / ".claude_extra")
    assert snapshot() == ARGV_ENV_PROMPT_SHA256


def real_records() -> list[Path]:
    return sorted(p for r in REAL_ROOTS for p in r.glob("*/*/session.json"))


@pytest.mark.skipif(not real_records(), reason="private archive absent")
def test_argv_env_prompt_match_archived_sessions(monkeypatch):
    seen = set()
    template = L.prompt_template()
    for p in real_records():
        rec = json.loads(p.read_text())
        wd = Path(rec["workdir"])
        prompt = template.replace("⟨dir⟩", str(wd)).replace("⟨n⟩", str(rec["inputs"]["n_items"]))
        assert prompt == rec["prompt"]
        for k in ("HOME", "PATH", "USER", "TMPDIR"):
            monkeypatch.setenv(k, rec["env"][k])
        monkeypatch.setenv("UNRELATED", "dropped")
        argv, env = L.argv_for(rec["role"], wd, prompt)
        assert argv == rec["argv"] and env == rec["env"], p
        seen.add(rec["role"])
    assert seen == {"A", "B", "C"}


class FakeRun:
    """Stands in for subprocess.run: never executes anything."""

    def __init__(self, sessions: Path, *, rc=0, labels=True, sid=True, rollout=True):
        self.sessions, self.rc, self.labels, self.sid, self.rollout = (
            sessions,
            rc,
            labels,
            sid,
            rollout,
        )
        self.calls: list[list[str]] = []

    def __call__(self, cmd, cwd=None, env=None, stdout=None, **kw):
        self.calls.append(cmd)
        if cmd[0] == "git":
            return subprocess.CompletedProcess(cmd, 128)
        assert cmd[0] == "codex", cmd  # no other program may be "run"
        wd = Path(cwd)
        if self.sid:
            stdout.write(json.dumps({"type": "thread.started", "thread_id": SID["B"]}) + "\n")
        if self.labels:
            (wd / "labels.jsonl").write_text('{"id": "x1"}\n')
        if self.rollout:
            day = self.sessions / "2026" / "10" / "21"
            day.mkdir(parents=True, exist_ok=True)
            prompt = cmd[-1]
            jsonl(
                day / f"rollout-x-{SID['B']}.jsonl",
                [
                    {
                        "type": "session_meta",
                        "payload": {"id": SID["B"], "base_instructions": {"text": "Codex"}},
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": prompt}],
                        },
                    },
                ],
            )
        return subprocess.CompletedProcess(cmd, self.rc)


@pytest.fixture
def launch_env(root, monkeypatch):
    g, inv = root / "g.md", root / "inv.md"
    g.write_text("guidelines")
    inv.write_text("inventory")
    items = root / "items.jsonl"
    items.write_text('{"id": "x1"}\n')
    monkeypatch.setattr(L, "GUIDELINES", g)
    monkeypatch.setattr(L, "INVENTORY", inv)
    monkeypatch.setattr(L, "GUIDELINES_SHA256", sha(g))
    monkeypatch.setattr(L, "INVENTORY_SHA256", sha(inv))
    monkeypatch.setattr(L, "CODEX_SESSIONS", root / "codex_sessions")
    (root / "tmp").mkdir()
    monkeypatch.setenv("TMPDIR", str(root / "tmp"))
    return items, root / "archive"


def run_launch(monkeypatch, launch_env, root, **kw) -> tuple[int, dict, FakeRun]:
    items, archive = launch_env
    fake = FakeRun(root / "codex_sessions", **kw)
    monkeypatch.setattr(L.subprocess, "run", fake)
    rc = L.main(["B", str(items), str(archive), "--label", "t"])
    (rec_path,) = archive.glob("B/*/session.json")
    return rc, json.loads(rec_path.read_text()), fake


def test_launch_delivered_only_with_id_and_context(root, monkeypatch, launch_env):
    rc, rec, fake = run_launch(monkeypatch, launch_env, root)
    assert rc == 0 and rec["status"] == "delivered" and rec["failure_reasons"] == []
    wd = Path(rec["workdir"])
    assert fake.calls[1] == L.argv_for("B", wd, rec["prompt"])[0] == rec["argv"]
    assert sorted(p.name for p in wd.iterdir()) == [
        "guidelines.md",
        "items.jsonl",
        "labels.jsonl",
        "phrase_sense_inventory.md",
    ]
    out = CS.screen_archive(launch_env[1])
    assert out["ok"], out


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({"sid": False}, "provider session id absent"),
        ({"rollout": False}, "0 provider session records found (need 1)"),
        ({"labels": False}, "no labels file"),
        ({"rc": 1}, "exit code 1"),
    ],
)
def test_launch_technical_failure(root, monkeypatch, launch_env, kw, reason):
    rc, rec, _ = run_launch(monkeypatch, launch_env, root, **kw)
    assert rc == 1 and rec["status"] == "technical_failure"
    assert reason in rec["failure_reasons"]
    log = json.loads((launch_env[1] / "launch_log.jsonl").read_text())
    assert log["status"] == "technical_failure"
    assert CS.main([str(launch_env[1])]) == 1


def test_launch_archives_even_when_context_export_crashes(root, monkeypatch, launch_env):
    def boom(*a):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(L, "archive_context", boom)
    rc, rec, _ = run_launch(monkeypatch, launch_env, root)
    assert rc == 1 and rec["status"] == "technical_failure"
    assert rec["failure_reasons"][0].startswith("context archiving failed")
    assert {"labels.jsonl", "stream.jsonl", "stderr.log"} <= set(rec["archive_sha256"])


# ------------------------------------------------------------ the collector


def collect_fixture(root: Path, role_dir: str = "B") -> tuple[Path, Path, Path]:
    build = root / "build"
    bdir = build / "batches" / "B" / "batch"
    bdir.mkdir(parents=True)
    jsonl(build / "items.jsonl", [{"id": "x1", "module": "metadiscourse", "claimed": {}}])
    jsonl(bdir / "batch_01.jsonl", [{"id": "x1"}])
    bsha = sha(bdir / "batch_01.jsonl")
    (bdir / "batch_manifest.json").write_text(
        json.dumps(
            {"batches": [{"batch": 1, "file": "batch_01.jsonl", "sha256": bsha, "ids": ["x1"]}]}
        )
    )
    sessions = root / "sessions"
    sessions.mkdir()
    make_session(sessions, role_dir, "tokB", items_sha=bsha)
    return sessions, build, root / "out"


def write_screen(sessions: Path, path: Path) -> Path:
    path.write_text(json.dumps(CS.screen_archive(sessions)))
    return path


def test_collect_accepts_clean_screened_session(root):
    sessions, build, out = collect_fixture(root)
    scr = write_screen(sessions, root / "screen.json")
    assert CR.main(["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)]) == 0
    assert (out / "B_batch.jsonl").read_text().strip().startswith('{"id": "x1"')


def test_collect_refuses_missing_screen(root):
    sessions, build, out = collect_fixture(root)
    with pytest.raises(SystemExit, match="screen result missing"):
        CR.main(["B", "batch", str(sessions), str(build), str(out)])
    assert not out.exists()


def test_collect_refuses_flagged_or_stale_screen(root):
    sessions, build, out = collect_fixture(root)
    d = sessions / "B" / "tokB"
    scr = write_screen(sessions, root / "screen.json")
    write_context(d, "B", "/tmp/p040wd/tokB", 'text(await tools.exec_command({cmd:"cat ../x.md"}))')
    seal(d)
    args = ["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)]
    with pytest.raises(SystemExit, match="different session.json"):
        CR.main(args)
    write_screen(sessions, scr)
    with pytest.raises(SystemExit, match="status 'flagged'.*No label is generated or chosen"):
        CR.main(args)
    assert not out.exists()


def test_collect_refuses_technical_failure(root):
    sessions, build, out = collect_fixture(root)
    d = sessions / "B" / "tokB"
    (d / "rollout.jsonl").unlink()
    seal(d)
    scr = write_screen(sessions, root / "screen.json")
    args = ["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)]
    with pytest.raises(SystemExit, match="status 'technical_failure'.*rollout.jsonl missing"):
        CR.main(args)
    seal(d, status="technical_failure")
    fix_log(sessions, d, status="technical_failure")
    write_screen(sessions, scr)
    with pytest.raises(SystemExit, match="0 delivered sessions.*tokB:technical_failure"):
        CR.main(args)
    assert not out.exists()


def test_collect_refuses_archive_with_missing_session(root):
    sessions, build, out = collect_fixture(root)
    with (sessions / "launch_log.jsonl").open("a") as f:
        f.write(json.dumps({"role": "A", "token": "gone", "status": "delivered"}) + "\n")
    scr = write_screen(sessions, root / "screen.json")
    with pytest.raises(SystemExit, match="has no archive.*no label is generated or chosen"):
        CR.main(["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)])


def test_collect_rechecks_the_archive_after_screening(root):
    """Negative controls: the archive changes between the screen and the collection."""
    sessions, build, out = collect_fixture(root)
    make_session(sessions, "A", "tokA")
    scr = write_screen(sessions, root / "screen.json")
    args = ["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)]
    log = sessions / "launch_log.jsonl"
    before = log.read_text()
    # a logged delivered session with no archive, appended after the screen
    log.write_text(
        before + json.dumps({"role": "A", "token": "gone", "status": "delivered"}) + "\n"
    )
    with pytest.raises(SystemExit, match="current archive problems.*A/gone has no archive"):
        CR.main(args)
    log.write_text(before)
    # an archive removed after the screen
    moved = root / "tokA.moved"
    (sessions / "A" / "tokA").rename(moved)
    with pytest.raises(SystemExit, match="current archive problems.*A/tokA has no archive"):
        CR.main(args)
    # an unlogged archive added after the screen
    moved.rename(sessions / "A" / "tokA")
    make_session(sessions, "A", "tokA2")
    log.write_text(before)
    with pytest.raises(SystemExit, match="A/tokA2 is not in the launch log"):
        CR.main(args)
    # logged too, but never screened
    make_session(sessions, "A", "tokA3")
    shutil.rmtree(sessions / "A" / "tokA2")
    lines = [r for r in log.read_text().splitlines() if '"tokA2"' not in r]
    log.write_text("\n".join(lines) + "\n")
    with pytest.raises(SystemExit, match="different launch log"):
        CR.main(args)
    assert not out.exists()


def test_collect_refuses_screen_from_another_inventory(root):
    sessions, build, out = collect_fixture(root)
    scr = root / "screen.json"
    screen = CS.screen_archive(sessions)
    screen["sessions"] = []
    scr.write_text(json.dumps(screen))
    with pytest.raises(SystemExit, match="does not list exactly the sessions now archived"):
        CR.main(["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)])
    assert not out.exists()


def test_empty_assignment_is_not_applicable(root, capsys):
    sessions, build, out = collect_fixture(root)
    (build / "batches" / "B" / "batch" / "batch_manifest.json").write_text('{"batches": []}')
    scr = write_screen(sessions, root / "screen.json")
    rc = CR.main(["B", "batch", str(sessions), str(build), str(out), "--screen", str(scr)])
    assert rc == 3 and "not applicable" in capsys.readouterr().out
    assert not out.exists()


# ------------------------------------------------------ the real pilot archive


@pytest.mark.skipif(not real_records(), reason="private archive absent")
def test_real_pilot_archive_screen():
    """10 + 3 sessions: all clean bar the known code-like Edit in primary-A-02."""
    res = {}
    for r in REAL_ROOTS:
        out = CS.screen_archive(r)
        assert out["inventory_problems"] == []
        res |= {s["label"]: s for s in out["sessions"]}
    assert len(res) == 13
    for label, s in res.items():
        assert s["technical_failures"] == [], (label, s["technical_failures"])
        assert s["review"] == [] and s["other_paths"] == [] and not s["context_forbidden_hits"]
        if label == "primary-A-02":
            assert s["status"] == "flagged" and len(s["code_like_calls"]) == 1
            assert s["code_like_calls"][0].startswith('Edit: {"replace_all": false, "file_path"')
            assert "/labels.jsonl" in s["code_like_calls"][0]
        else:
            assert s["status"] == "clean", label


# --- recorded rulings on flagged sessions ------------------------------


def _flagged(**over):
    r = {
        "status": "flagged",
        "context_forbidden_hits": [],
        "technical_failures": [],
        "other_paths": [],
        "code_like_calls": [{"tool": "Edit", "match": "x"}],
        "review": [],
    }
    r.update(over)
    return r


def _ruling(r, session_sha="s" * 64):
    return {"session_json_sha256": session_sha, "flags_sha256": CR.flags_sha256(r)}


def test_ruling_accepts_exactly_the_examined_flags():
    r = _flagged()
    assert CR.ruled(r, _ruling(r), "s" * 64)


def test_ruling_no_longer_matches_when_flags_change():
    r = _flagged()
    ruling = _ruling(r)
    changed = _flagged(review=[{"path": "../x"}])
    assert not CR.ruled(changed, ruling, "s" * 64)


def test_ruling_is_bound_to_the_session_record():
    r = _flagged()
    assert not CR.ruled(r, _ruling(r), "t" * 64)


def test_ruling_never_accepts_context_markers_or_technical_failures():
    marker = _flagged(context_forbidden_hits=["lexinspect"])
    assert not CR.ruled(marker, _ruling(marker), "s" * 64)
    broken = _flagged(status="technical_failure", technical_failures=["missing rollout"])
    assert not CR.ruled(broken, _ruling(broken), "s" * 64)


def test_rulings_file_requires_every_field(tmp_path):
    p = tmp_path / "rulings.jsonl"
    p.write_text(json.dumps({"role": "A", "token": "t", "ruling": "accept"}) + "\n")
    with pytest.raises(SystemExit):
        CR.load_rulings(p)
