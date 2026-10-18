"""Harness audit r4 dispositions (R4-B1, R4-S1, R4-S2, R4-S3, R4-M1): every executed probe
of sol_harness_audit_r4.md is a regression here.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck

No test touches the network: collections read synthetic mock caches (test_fixcheck's
_mock_cache), urllib's urlopen is replaced by a function that raises, and the hard-exit
drivers are real subprocesses in temporary directories (test_r6's DRIVER). No real label
exists anywhere. Restricted inventory fragments are counted, never printed.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402

from fixcheck import accept, cli, collect, freeze, package, registry  # noqa: E402
from fixcheck.common import canonical_json, read_json, read_jsonl, sha256_file  # noqa: E402
from fixcheck.ledger import FAMILIES  # noqa: E402
from fixcheck.test_fixcheck import _mock_cache  # noqa: E402
from fixcheck.test_r4 import (  # noqa: E402, F401  (pkg: a module-scoped fixture)
    _canonical_registry,
    _git,
    _repo,
    _res,
    pkg,
)
from fixcheck.test_r5 import _first_fetched_epmc  # noqa: E402
from fixcheck.test_r6 import _production_package  # noqa: E402

DARWIN = sys.platform == "darwin" and hasattr(fcntl, "F_FULLFSYNC")
REPO = freeze.REPO


def _commits() -> tuple[str, str]:
    """Two real commits of this repository, as distinct dry-run candidates (round 2 needs a
    separately frozen candidate whose src/lexinspect tree differs, gap G3): HEAD, and the
    parent of the latest commit that changed src/lexinspect."""

    def git(*a: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True
        ).stdout.strip()

    head = git("rev-parse", "HEAD")
    last = git("rev-list", "-n", "1", "HEAD", "--", "src/lexinspect")
    other = git("rev-parse", f"{last}~1")
    assert (
        freeze.commit_src_digest(head)["tree_sha256"]
        != freeze.commit_src_digest(other)["tree_sha256"]
    )
    return head, other


def _plan(
    tmp_path, raw, dev_raw, reg, out="r1", rnd=1, seed="777", cand=None, offline=True, earlier=()
):
    argv = [
        "--round",
        str(rnd),
        "--seed",
        seed,
        "--out",
        str(tmp_path / out),
        "--raw-cache",
        str(raw),
        "--dev-raw",
        str(dev_raw),
        *(["--offline"] if offline else []),
        "--dry-run",
        "--registry",
        str(reg),
    ]
    if cand:
        argv += ["--candidate-commit", cand]
    for e in earlier:
        argv += ["--earlier", str(e)]
    assert collect.main([*argv, "--plan-only"]) == 0
    rec = read_json(tmp_path / out / "freeze_record.json")
    return rec, rec["execution_argv"][4:]


def _archive(tmp_path, d: Path, raw: Path, name="failed.tar") -> Path:
    """The runbook's failure archive: collect/ (the round directory) and raw/ (its cache)."""
    a = tmp_path / name
    with tarfile.open(a, "w") as tf:
        for f in sorted(d.iterdir()):
            if f.is_file():
                tf.add(f, arcname=f"collect/{f.name}")
        tf.add(raw, arcname="raw")
    return a


def _register(d, archive, reg, out, *extra) -> int:
    return cli.main(
        [
            "register-failure",
            "--round-dir",
            str(d),
            "--archive",
            str(archive),
            "--registry",
            str(reg),
            "--out",
            str(out),
            *extra,
        ]
    )


def _journal(d: Path) -> list[dict]:
    return [json.loads(x) for x in (d / collect.FETCH_JOURNAL).read_text().splitlines()]


# A synthetic origin stands in for the network: build.py's urlopen is replaced by a function
# that serves the mock bodies from a directory (never a socket). The round's own cache then
# starts with the pool snapshot only, as in production, so "every cached body" is exactly
# what the execution fetched.
ORIGIN = r"""
import io, os, urllib.parse
from pathlib import Path


def origin_urlopen(origin, calls=None):
    import build

    def urlopen(req, timeout=None):
        url = getattr(req, "full_url", req)
        if calls is not None:
            with open(calls, "a") as f:
                f.write(url + "\n")
        if url.endswith("/fullTextXML"):
            f = Path(origin) / "epmc" / (url.split("/")[-2] + ".xml")
        else:
            title = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["titles"][0]
            f = Path(origin) / "wiki" / (build._key(title) + ".json")
        if not f.exists():
            raise OSError("synthetic origin: no such resource (no network in this test)")
        return io.BytesIO(f.read_bytes())

    return urlopen
"""

DRIVER7 = r"""
import json, os, sys
from pathlib import Path

study4, mode, work, argv_json, origin = sys.argv[1:6]
sys.path.insert(0, study4)
import build
from fixcheck import collect

exec(Path(work, "origin.py").read_text())
build.urllib.request.urlopen = origin_urlopen(origin, Path(work) / "origin_calls")
build.time.sleep = lambda s: None  # build.fetch's back-off
real_fetch = build.fetch
state = {"failed": False}


def fetch(url, cache, refresh=False):
    if state["failed"]:
        os._exit(9)  # killed at the next request, after the failure was journalled
    try:
        return real_fetch(url, cache, refresh)
    except BaseException:
        if mode == "kill_in_failed_request":
            os._exit(9)
        state["failed"] = True
        raise


build.fetch = fetch
try:
    rc = collect.main(json.loads(argv_json))
except SystemExit as e:
    print(f"REFUSED: {e}", flush=True)
    sys.exit(3)
sys.exit(rc)
"""


def _origin_driver(tmp_path, mode, argv, origin) -> subprocess.Popen:
    work = tmp_path / "work7"
    work.mkdir(exist_ok=True)
    (work / "origin.py").write_text(ORIGIN)
    (work / "driver.py").write_text(DRIVER7)
    return subprocess.Popen(
        [
            sys.executable,
            "-I",
            str(work / "driver.py"),
            str(HERE.parent),
            mode,
            str(work),
            json.dumps(argv),
            str(origin),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _origin_in_process(monkeypatch, origin):
    ns: dict = {}
    exec(ORIGIN, ns)
    monkeypatch.setattr(build.urllib.request, "urlopen", ns["origin_urlopen"](origin))
    monkeypatch.setattr(build.time, "sleep", lambda s: None)


def _hard_exit_round1(tmp_path):
    """Round 1 planned with a scratch registry, its cache holding the pool snapshot only,
    then killed (os._exit) by a real subprocess at the request after a failed one (the
    victim body is missing at the synthetic origin): start + journal survive, nothing else."""
    rel = _first_fetched_epmc(tmp_path)
    dev_raw, origin = _mock_cache(tmp_path)
    keep = tmp_path / "victim.body"
    shutil.move(origin / rel, keep)
    raw = tmp_path / "cache1"
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    rec, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1, offline=False)
    assert rec["initial_cache_inventory"]["n_files"] == len(list((dev_raw / "pools").iterdir()))
    p = _origin_driver(tmp_path, "kill_after_failure", ex, origin)
    assert p.wait(timeout=120) == 9, p.stdout.read()
    d = tmp_path / "r1"
    assert not (d / collect.EXEC_DONE).exists() and not (d / collect.EXEC_ABORT).exists()
    shutil.move(keep, origin / rel)  # the victim is available again (later rounds)
    return dict(
        dev_raw=dev_raw,
        origin=origin,
        raw=raw,
        reg=reg,
        rec=rec,
        ex=ex,
        d=d,
        rel=rel,
        c1=c1,
        c2=c2,
    )


class _Stop(BaseException):  # noqa: N818 - an in-process interruption (Ctrl-C-like)
    """Raised at the request after a failed one: the collector's BaseException handler
    writes the abort record (the authenticated endpoint; ruling after audit r7 B1)."""


def _stopped_round1(tmp_path, monkeypatch):
    """Round 1 as in _hard_exit_round1, but interrupted in-process (a BaseException at the
    request after the failed one), so its abort record fixes the full request history."""
    rel = _first_fetched_epmc(tmp_path)
    dev_raw, origin = _mock_cache(tmp_path)
    keep = tmp_path / "victim.body"
    shutil.move(origin / rel, keep)
    raw = tmp_path / "cache1"
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    rec, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1, offline=False)
    with monkeypatch.context() as m:
        _origin_in_process(m, origin)
        real_fetch = build.fetch
        state = {"failed": False}

        def fetch(url, cache, refresh=False):
            if state["failed"]:
                raise _Stop("interrupted at the request after a failed one")
            try:
                return real_fetch(url, cache, refresh)
            except BaseException:
                state["failed"] = True
                raise

        m.setattr(build, "fetch", fetch)
        with pytest.raises(_Stop):
            collect.main(ex)
    d = tmp_path / "r1"
    assert (d / collect.EXEC_ABORT).exists() and not (d / collect.EXEC_DONE).exists()
    shutil.move(keep, origin / rel)  # the victim is available again (later rounds)
    return dict(
        dev_raw=dev_raw, origin=origin, raw=raw, reg=reg, rec=rec, ex=ex, d=d, rel=rel, c1=c1,
        c2=c2,
    )  # fmt: skip


# --- R4-B1: the durable barrier before any request ---------------------------------------


class _Spy:
    """Records os.open paths, F_FULLFSYNC and fsync calls (by path) and fetches, in order."""

    def __init__(self, monkeypatch, root: Path, fail_at: int | None = None, fail_on=None):
        self.root = os.path.realpath(str(root))
        self.paths: dict[int, str] = {}
        self.events: list[tuple[str, str]] = []
        self.n_full = 0
        self.fail_at = fail_at
        self.fail_on = fail_on
        real_open, real_fcntl, real_fsync = os.open, fcntl.fcntl, os.fsync

        def spy_open(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            self.paths[fd] = os.path.realpath(str(path))
            return fd

        def path_of(fd):
            # descriptors opened by io.open (the registry's Path.open) bypass os.open
            if fd not in self.paths:
                try:
                    if hasattr(fcntl, "F_GETPATH"):
                        raw = real_fcntl(fd, fcntl.F_GETPATH, bytes(1024))
                        self.paths[fd] = os.path.realpath(raw.split(b"\0", 1)[0].decode())
                    else:
                        self.paths[fd] = os.path.realpath(os.readlink(f"/proc/self/fd/{fd}"))
                except OSError:
                    self.paths[fd] = "?"
            return self.paths[fd]

        self.path_of = path_of

        def name(fd):
            p = path_of(fd)
            return p if not p.startswith(self.root) else Path(p).name or p

        def spy_fcntl(fd, cmd, *a):
            if DARWIN and cmd == fcntl.F_FULLFSYNC and path_of(fd).startswith(self.root):
                self.n_full += 1
                self.events.append(("F_FULLFSYNC", name(fd)))
                if self.n_full == self.fail_at or (self.fail_on and self.fail_on(self, fd)):
                    raise OSError(errno.EIO, "injected F_FULLFSYNC failure")
            return real_fcntl(fd, cmd, *a)

        def spy_fsync(fd):
            if path_of(fd).startswith(self.root):
                self.events.append(("fsync", name(fd)))
                if self.fail_on and self.fail_on(self, fd):
                    raise OSError(errno.EIO, "injected fsync failure")
            return real_fsync(fd)

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(fcntl, "fcntl", spy_fcntl)
        monkeypatch.setattr(os, "fsync", spy_fsync)
        real_fetch = collect._offline_fetch

        def fetch(url, cache, refresh=False):
            self.events.append(("FETCH", Path(cache).name))
            return real_fetch(url, cache, refresh)

        monkeypatch.setattr(collect, "_offline_fetch", fetch)

    def fetches(self) -> int:
        return sum(1 for e in self.events if e[0] == "FETCH")


def _forbid_network(monkeypatch):
    def urlopen(*a, **k):
        raise AssertionError("a request left the process")

    monkeypatch.setattr(build.urllib.request, "urlopen", urlopen)


@pytest.mark.skipif(not DARWIN, reason="the macOS full barrier (F_FULLFSYNC) needs Darwin")
def test_r4_b1_darwin_full_barrier_is_called_in_order_before_every_request(tmp_path, monkeypatch):
    # the audit: CLAIM_SYNC_CALLS [fsync(start), fsync(dir), fsync(journal), fsync(dir)],
    # F_FULLFSYNC_CALLS 0. Now: the real F_FULLFSYNC (called through, not mocked) on the file,
    # then on its directory, for the start record, the journal and every journalled request.
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    rec, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    out = tmp_path / "r1"
    spy = _Spy(monkeypatch, tmp_path)
    assert collect.main(ex) == 0
    ev = spy.events
    assert not [e for e in ev if e[0] == "fsync"]  # no downgraded ordinary fsync
    first = ev.index(next(e for e in ev if e[0] == "FETCH"))
    assert ev[:4] == [
        ("F_FULLFSYNC", collect.EXEC_START),
        ("F_FULLFSYNC", "r1"),
        ("F_FULLFSYNC", collect.FETCH_JOURNAL),
        ("F_FULLFSYNC", "r1"),
    ]
    # the first request is journalled and fully flushed (file, then directory) before it
    assert ev[4:first] == [("F_FULLFSYNC", collect.FETCH_JOURNAL), ("F_FULLFSYNC", "r1")]
    for i, e in enumerate(ev):
        if e[0] == "FETCH":  # every request: its journal line's full barrier just before
            assert ev[i - 2 : i] == [
                ("F_FULLFSYNC", collect.FETCH_JOURNAL),
                ("F_FULLFSYNC", "r1"),
            ], i
    n_req = len(_journal(out)) // 2
    assert spy.fetches() == n_req and n_req > 0
    start = read_json(out / collect.EXEC_START)
    assert start["durability"].startswith("darwin: fcntl F_FULLFSYNC")


@pytest.mark.skipif(not DARWIN, reason="the macOS full barrier (F_FULLFSYNC) needs Darwin")
@pytest.mark.parametrize(
    "where", ["start_file", "start_directory", "journal_file", "first_request"]
)
def test_r4_b1_failed_full_barrier_reaches_no_request(tmp_path, monkeypatch, where):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    rec, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    out = tmp_path / "r1"
    k = {"start_file": 1, "start_directory": 2, "journal_file": 3, "first_request": 5}[where]
    spy = _Spy(monkeypatch, tmp_path, fail_at=k)
    with pytest.raises((SystemExit, collect.JournalBarrierFailure)) as ei:
        collect.main(ex)
    assert "barrier failed" in str(ei.value)
    assert spy.fetches() == 0  # no request was reached
    # the start record exists: the round is consumed (no silent downgrade, no retry)
    assert (out / collect.EXEC_START).exists() and not (out / collect.EXEC_DONE).exists()
    if where == "first_request":  # the request line was written but never authorised
        assert [e["event"] for e in _journal(out)] == ["request"]
        assert read_json(out / collect.EXEC_ABORT)["fetch_log"] == []
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex)
    assert spy.fetches() == 0
    assert freeze.cache_inventory(raw)["sha256"] == rec["initial_cache_inventory"]["sha256"]


def test_r4_b1_linux_sequence_is_fsync_file_then_directory(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    rec, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    spy = _Spy(monkeypatch, tmp_path)
    assert collect.main(ex) == 0
    ev = spy.events
    assert not [e for e in ev if e[0] == "F_FULLFSYNC"]
    assert ev[:6] == [
        ("fsync", collect.EXEC_START),
        ("fsync", "r1"),
        ("fsync", collect.FETCH_JOURNAL),
        ("fsync", "r1"),
        ("fsync", collect.FETCH_JOURNAL),
        ("fsync", "r1"),
    ]
    assert ev[6][0] == "FETCH"
    assert read_json(tmp_path / "r1" / collect.EXEC_START)["durability"].startswith("linux")


def test_r4_b1_linux_failed_fsync_reaches_no_request(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    _, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    spy = _Spy(monkeypatch, tmp_path, fail_on=lambda s, fd: s.path_of(fd).endswith("r1"))
    with pytest.raises(SystemExit, match="barrier failed"):
        collect.main(ex)
    assert spy.fetches() == 0 and (tmp_path / "r1" / collect.EXEC_START).exists()


@pytest.mark.parametrize("plat", ["win32", "sunos5"])
def test_r4_b1_platform_without_a_barrier_refuses_before_the_claim(tmp_path, monkeypatch, plat):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    _, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    monkeypatch.setattr(sys, "platform", plat)
    spy = _Spy(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="no durable-write barrier"):
        collect.main(ex)
    assert spy.fetches() == 0
    assert collect.executed_evidence(tmp_path / "r1") == []  # nothing claimed or consumed
    with pytest.raises(collect.DurabilityError):
        collect.durability_method("win32")


def test_r4_b1_probe_crash_between_lock_and_claim_consumes_nothing(tmp_path):
    out = tmp_path / "r"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; import os;"
        "from fixcheck import collect;"
        "cm = collect.execution_lock(Path(sys.argv[2])); cm.__enter__(); os._exit(9)"
    )
    p = subprocess.run([sys.executable, "-I", "-c", code, str(HERE.parent), str(out)])
    assert p.returncode == 9
    assert collect.executed_evidence(out) == []  # merely locking is not an attempt
    with collect.execution_lock(out):  # the kernel released the dead holder's lock
        pass


def test_r4_b1_probe_failure_between_start_and_journal_is_conservative(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    _, ex = _plan(tmp_path, raw, dev_raw, reg)
    _forbid_network(monkeypatch)
    real = collect.write_exclusive

    def write(path, data, mode=0o444):
        if Path(path).name == collect.FETCH_JOURNAL:
            raise OSError(errno.ENOSPC, "injected: the journal cannot be created")
        return real(path, data, mode)

    monkeypatch.setattr(collect, "write_exclusive", write)
    with pytest.raises(OSError, match="journal cannot be created"):
        collect.main(ex)
    assert collect.executed_evidence(tmp_path / "r1") == [collect.EXEC_START]
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex)


def test_r4_b1_probe_competing_exclusive_start_creation(tmp_path):
    # the audit: eight subprocesses raced the same O_CREAT|O_EXCL start path -> [0,3,...,3]
    target = tmp_path / "start.json"
    go = tmp_path / "go"
    code = (
        "import sys, os, time; sys.path.insert(0, sys.argv[1]); from pathlib import Path;"
        "from fixcheck import collect\n"
        "while not os.path.exists(sys.argv[3]): time.sleep(0.001)\n"
        "try:\n collect.write_exclusive(Path(sys.argv[2]), b'{}')\n"
        "except FileExistsError:\n sys.exit(3)\n"
    )
    procs = [
        subprocess.Popen([sys.executable, "-I", "-c", code, str(HERE.parent), str(target), str(go)])
        for _ in range(8)
    ]
    go.write_text("")
    assert sorted(p.wait(timeout=60) for p in procs) == [0] + [3] * 7
    # a present but empty start file also prevents a second claim
    out = tmp_path / "r"
    out.mkdir()
    (out / collect.EXEC_START).write_text("")
    rec = {"round": 1, "seed": 7, "production_eligible": False}
    fr = tmp_path / "fr.json"
    fr.write_text("{}")
    with pytest.raises(SystemExit, match="already executed"):
        collect.claim_execution(out, rec, fr, {"production": False}, "t")


# --- R4-S2: the journal is a request/outcome state machine --------------------------------


def _entry(seq=0, url="https://x/a", cache="epmc/PMC1.xml", sha="ab"):
    return {
        "seq": seq,
        "url": url,
        "cache": cache,
        "refresh": False,
        "cache_hit": True,
        "sha256": sha,
        "bytes": 2,
    }


def _req(f):
    return {"event": "request", **{k: f[k] for k in collect.REQUEST_FIELDS}}


def _out(f):
    return {"event": "outcome", **f}


def _write_journal(path: Path, events) -> Path:
    path.write_text("".join(canonical_json(e) + "\n" for e in events))
    return path


def test_r4_s2_valid_stream_reconstructs_the_log(tmp_path):
    f0, f1 = _entry(0), _entry(1, url="https://x/b", cache="epmc/PMC2.xml")
    j = _write_journal(tmp_path / "j", [_req(f0), _out(f0), _req(f1), _out(f1)])
    assert collect.journal_problems(j, [f0, f1]) == []
    assert collect.journal_problems(j, [f0]) != []


@pytest.mark.parametrize(
    "case",
    ["identity_differs", "outcome_first", "made_up_event"],
)
def test_r4_s2_audit_counterexamples_are_refused(tmp_path, case):
    # the audit: each of these returned [] with the final log [f]
    f = _entry()
    if case == "identity_differs":
        other = _entry(url="https://x/different", cache="epmc/PMC9.xml")
        events = [_req(other), _out(f)]
    elif case == "outcome_first":
        events = [_out(f), _req(f)]
    else:
        events = [_req(f), {"event": "made_up_event", **f}]
    j = _write_journal(tmp_path / "j", events)
    assert collect.journal_problems(j, [f]) != []
    assert collect.journal_pairs(j, allow_trailing_request=True)[2] != []


@pytest.mark.parametrize(
    "case",
    ["duplicate_request", "duplicate_outcome", "skipped_seq", "trailing_request"],
)
def test_r4_s2_duplicates_gaps_and_trailing_requests(tmp_path, case):
    f0, f1 = _entry(0), _entry(1)
    events = {
        "duplicate_request": [_req(f0), _req(f0), _out(f0)],
        "duplicate_outcome": [_req(f0), _out(f0), _out(f0)],
        "skipped_seq": [_req(f0), _out(f0), _req(_entry(2)), _out(_entry(2))],
        "trailing_request": [_req(f0), _out(f0), _req(f1)],
    }[case]
    j = _write_journal(tmp_path / "j", events)
    assert collect.journal_problems(j, [f0]) != []  # a completed collection: never
    pairs, trailing, p = collect.journal_pairs(j, allow_trailing_request=True)
    if case == "trailing_request":  # the failure validator: one final unmatched request
        assert p == [] and len(pairs) == 1 and trailing["seq"] == 1
        two = _write_journal(tmp_path / "j2", [*events, _req(_entry(2))])
        assert collect.journal_pairs(two, allow_trailing_request=True)[2] != []
    else:
        assert p != []


@pytest.mark.parametrize("damage", ["truncated", "not_json", "missing_field", "two_outcomes"])
def test_r4_s2_malformed_or_truncated_lines_are_integrity_problems(tmp_path, damage):
    f = _entry()
    j = _write_journal(tmp_path / "j", [_req(f), _out(f)])
    if damage == "truncated":
        with j.open("ab") as fh:
            fh.write(b'{"event":"request","seq":1')
    elif damage == "not_json":
        with j.open("a") as fh:
            fh.write("not json\n")
    elif damage == "missing_field":
        _write_journal(j, [{k: v for k, v in _req(f).items() if k != "url"}, _out(f)])
    else:
        bad = dict(_out(f), error="E: x", error_class="E", error_message="x")
        _write_journal(j, [_req(f), bad])
    assert collect.journal_problems(j, [f]) != []
    assert collect.journal_pairs(j, allow_trailing_request=True)[2] != []


def test_r4_s2_short_writes_are_continued_and_a_zero_write_refuses(tmp_path, monkeypatch):
    j = tmp_path / "j"
    j.write_text("")
    real = os.write
    calls = []

    def short(fd, data):
        calls.append(len(data))
        return real(fd, bytes(data[:3]))  # at most three bytes per call

    monkeypatch.setattr(os, "write", short)
    line = canonical_json(_req(_entry())) + "\n"
    collect.append_fsync(j, line)
    assert j.read_text() == line and len(calls) > 10
    monkeypatch.setattr(os, "write", lambda fd, data: 0)
    with pytest.raises(collect.DurabilityError, match="partial write"):
        collect.append_fsync(j, line)
    # a FetchRecorder whose journal append fails never makes the request
    monkeypatch.setattr(os, "write", real)
    j2 = tmp_path / "j2"
    j2.write_text("")
    made = []
    rec = collect.FetchRecorder(tmp_path, journal=j2)
    wrapped = rec.wrap_fetch(lambda url, cache, refresh=False: made.append(url) or b"x")
    monkeypatch.setattr(os, "write", lambda fd, data: 0)
    # a BaseException: build.py's per-article `except Exception` cannot swallow it and go on
    with pytest.raises(collect.JournalBarrierFailure, match="partial write"):
        wrapped("https://x/a", tmp_path / "a", False)
    assert not issubclass(collect.JournalBarrierFailure, Exception)
    assert made == [] and rec.fetches == []


# --- R4-S1: procedure_failure registration and continuation -------------------------------


def test_r4_s1_hard_exit_register_failure_restart_refusal_terminal_only(tmp_path):
    # a hard exit leaves no abort or completion record: no authenticated endpoint, so the
    # exposure is never established (ruling after audit r7 B1) and only terminals remain
    s = _hard_exit_round1(tmp_path)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    journal = _journal(d)
    assert journal[-1]["event"] == "request"  # killed at its next request
    a = _archive(tmp_path, d, raw)
    o = tmp_path / "fail1"
    assert _register(d, a, reg, o, "--dry-run") == 0
    entries = registry.load(reg)
    assert [e["type"] for e in entries] == ["reservation", "decision"]
    f = entries[1]
    assert f["status"] == "procedure_failure" and f["collection_texts_sha256"] is None
    assert f["failure"]["exposure_complete"] is False
    assert f["failure"]["archive_sha256"] == sha256_file(a)
    assert f["failure"]["execution_start_sha256"] == sha256_file(d / collect.EXEC_START)
    ex = read_json(o / "failure.json")["exposure"]
    assert any("no abort record" in p for p in ex["problems"]) and ex["endpoint"] is None
    refs = set(ex["refs"])
    victim = Path(s["rel"]).stem
    assert build._norm_ref(victim) in refs  # diagnostics: the failed request is recorded
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(s["ex"])
    assert registry.check_terminal(entries, "revert_0.3.3") == []
    assert registry.check_terminal(entries, "amendment") == []
    v, probs = registry.check_reservation(entries, _res(rnd=2, cand=s["c2"], seed=778, cdir="r2"))
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    with pytest.raises(SystemExit, match="exposure"):
        _plan(
            tmp_path, tmp_path / "cache2", s["dev_raw"], reg, out="r2", rnd=2, seed="778",
            cand=s["c2"], earlier=[d],
        )  # fmt: skip
    assert len(registry.load(reg)) == 2


def test_r4_s1_stopped_execution_register_failure_restart_refusal_disjoint_round2(
    tmp_path, monkeypatch
):
    s = _stopped_round1(tmp_path, monkeypatch)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    journal = _journal(d)
    assert journal[-1]["event"] == "outcome" and journal[-1].get("error_class") == "_Stop"
    a = _archive(tmp_path, d, raw)
    o = tmp_path / "fail1"
    assert _register(d, a, reg, o, "--dry-run") == 0
    entries = registry.load(reg)
    assert [e["type"] for e in entries] == ["reservation", "decision"]
    f = entries[1]
    assert f["status"] == "procedure_failure" and f["collection_texts_sha256"] is None
    assert f["failure"]["exposure_complete"] is True
    assert f["failure"]["archive_sha256"] == sha256_file(a)
    fj = read_json(o / "failure.json")
    assert f["acceptance_sha256"] == sha256_file(o / "failure.json")
    ex = fj["exposure"]
    refs = set(ex["refs"])
    assert ex["problems"] == [] and ex["endpoint"] == collect.EXEC_ABORT
    victim = Path(s["rel"]).stem
    assert build._norm_ref(victim) in refs  # the failed request is exposed
    for e in journal:  # every journalled request, succeeded or not, is exposed
        if e["cache"].startswith("epmc/"):
            assert build._norm_ref(Path(e["cache"]).stem) in refs
    assert sorted(f["source_refs"]) == ex["refs_sha256"]
    assert ex["n_requested_refs"] >= len({e["cache"] for e in journal})
    assert ex["n_selected_refs"] > 0
    # restart refusal: the execution, and normal acceptance of the consumed round
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(s["ex"])
    normal = {
        **{k: f[k] for k in ("type", "round", "candidate_commit", "candidate_tree_sha256")},
        **{k: f[k] for k in ("seed", "reservation_sha256", "freeze_record_sha256")},
        "collection_texts_sha256": "t",
        "source_refs": ["s"],
        "inputs_sha256": "a normal package",
        "status": "inconclusive",
        "families": list(FAMILIES),
    }
    v, probs = registry.check_decision(entries, normal)
    assert v == "refuse" and any("procedure_failure" in p for p in probs)
    # idempotent re-registration (another output directory); the registry does not grow
    assert _register(d, a, reg, tmp_path / "fail1b", "--dry-run") == 0
    assert read_json(tmp_path / "fail1b" / "registration.json")["verdict"] == "idempotent"
    assert len(registry.load(reg)) == 2
    # a different archive (another complete input identity) is refused, nothing written
    a2 = _archive(tmp_path, d, raw, name="other.tar")
    with tarfile.open(a2, "a") as tf:
        extra = tmp_path / "note.txt"
        extra.write_text("x")
        tf.add(extra, arcname="note.txt")
    with pytest.raises(SystemExit, match="procedure_failure"):
        _register(d, a2, reg, tmp_path / "fail1c", "--dry-run")
    assert not (tmp_path / "fail1c").exists() and len(registry.load(reg)) == 2
    # round 2: a fresh, disjoint collection; the synthetic origin serves every body again
    raw2 = tmp_path / "cache2"
    assert (s["origin"] / s["rel"]).exists()
    rec2, ex2 = _plan(
        tmp_path,
        raw2,
        s["dev_raw"],
        reg,
        out="r2",
        rnd=2,
        seed="778",
        cand=s["c2"],
        earlier=[d],
        offline=False,
    )
    ident = rec2["round2"]["earlier_identity"]
    assert ident["status"] == "procedure_failure"
    assert ident["exposure_sha256"] == f["failure"]["exposure_sha256"]
    assert rec2["earlier_rounds"][0]["exposure_sha256"] == f["failure"]["exposure_sha256"]
    _origin_in_process(monkeypatch, s["origin"])
    assert collect.main(ex2) == 0
    t2 = read_jsonl(tmp_path / "r2" / "texts.jsonl")
    r2refs = set().union(*(build.text_refs(t) for t in t2))
    assert len(t2) == 60 and not (r2refs & refs)
    assert victim not in {t["source_id"] for t in t2}
    col2 = read_json(tmp_path / "r2" / "collection.json")
    assert set(map(build._norm_ref, col2["selection_log"].get("excluded_texts", []))) & refs
    # the round-2 decision line: admitted when disjoint from the exposure, refused otherwise
    entries = registry.load(reg)
    r2res = entries[-1]
    assert r2res["type"] == "reservation" and r2res["round"] == 2
    d2 = {
        "type": "decision",
        "round": 2,
        "candidate_commit": r2res["candidate_commit"],
        "candidate_tree_sha256": r2res["candidate_tree_sha256"],
        "seed": 778,
        "reservation_sha256": registry.entry_sha256(r2res),
        "freeze_record_sha256": sha256_file(tmp_path / "r2" / "freeze_record.json"),
        "collection_texts_sha256": sha256_file(tmp_path / "r2" / "texts.jsonl"),
        "source_refs": package.source_refs_sha256(tmp_path / "r2" / "texts.jsonl"),
        "inputs_sha256": "i2",
        "status": "inconclusive",
        "families": list(FAMILIES),
        "round1_entry_sha256": registry.entry_sha256(f),
    }
    assert registry.check_decision(entries, d2) == ("append", [])
    overlap = dict(d2, source_refs=[*d2["source_refs"], f["source_refs"][0]])
    v, probs = registry.check_decision(entries, overlap)
    assert v == "refuse" and any("disjoint" in p for p in probs)


@pytest.mark.parametrize("damage", ["truncated_journal", "reordered_journal", "unknown_cache_file"])
def test_r4_s1_unestablished_exposure_leaves_only_terminal_outcomes(tmp_path, damage):
    s = _hard_exit_round1(tmp_path)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    j = d / collect.FETCH_JOURNAL
    if damage == "truncated_journal":
        with j.open("ab") as fh:
            fh.write(b'{"event":"outc')
    elif damage == "reordered_journal":
        lines = j.read_text().splitlines(keepends=True)
        j.write_text("".join([lines[1], lines[0], *lines[2:]]))
    else:
        (raw / "stray.bin").write_bytes(b"?")
    a = _archive(tmp_path, d, raw)
    assert _register(d, a, reg, tmp_path / "fail", "--dry-run") == 0  # the round is consumed
    f = registry.load(reg)[-1]
    assert f["status"] == "procedure_failure" and f["failure"]["exposure_complete"] is False
    assert read_json(tmp_path / "fail" / "failure.json")["exposure"]["problems"]
    with pytest.raises(SystemExit, match="exposure"):
        _plan(
            tmp_path,
            tmp_path / "cache2",
            s["dev_raw"],
            reg,
            out="r2",
            rnd=2,
            seed="778",
            cand=s["c2"],
            earlier=[d],
        )
    assert not (tmp_path / "r2" / "freeze_record.json").exists()
    assert len(registry.load(reg)) == 2  # no round-2 reservation
    r2res = _res(rnd=2, cand=s["c2"], seed=778, cdir="r2")
    v, probs = registry.check_reservation(registry.load(reg), r2res)
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    # nor is a round-2 decision admitted, even with a (hand-made) reservation before it
    d2 = {
        "type": "decision",
        "round": 2,
        "candidate_commit": s["c2"],
        "candidate_tree_sha256": None,
        "seed": 778,
        "reservation_sha256": registry.entry_sha256(r2res),
        "freeze_record_sha256": "f2",
        "collection_texts_sha256": "t2",
        "source_refs": ["z"],
        "inputs_sha256": "i2",
        "status": "inconclusive",
        "families": list(FAMILIES),
        "round1_entry_sha256": registry.entry_sha256(f),
    }
    v, probs = registry.check_decision([*registry.load(reg), r2res], d2)
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    # the terminal rules (register-terminal appends them to the canonical registry only)
    assert registry.check_terminal(registry.load(reg), "ship")  # refused
    assert registry.check_terminal(registry.load(reg), "revert_0.3.3") == []
    assert registry.check_terminal(registry.load(reg), "amendment") == []


def test_r4_s1_failed_round2_is_terminal(tmp_path, monkeypatch):
    s = _stopped_round1(tmp_path, monkeypatch)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    assert _register(d, _archive(tmp_path, d, raw), reg, tmp_path / "fail1", "--dry-run") == 0
    raw2 = tmp_path / "cache2"
    for x in (s["origin"] / "epmc").glob("*.xml"):
        x.unlink()  # round 2's first article request fails, and the driver kills it there
    _, ex2 = _plan(
        tmp_path,
        raw2,
        s["dev_raw"],
        reg,
        out="r2",
        rnd=2,
        seed="778",
        cand=s["c2"],
        earlier=[d],
        offline=False,
    )
    p = _origin_driver(tmp_path, "kill_after_failure", ex2, s["origin"])
    assert p.wait(timeout=120) == 9, p.stdout.read()
    d2 = tmp_path / "r2"
    a2 = _archive(tmp_path, d2, raw2, name="failed2.tar")
    assert _register(d2, a2, reg, tmp_path / "fail2", "--dry-run") == 0
    entries = registry.load(reg)
    assert [(e["type"], e.get("round"), e.get("status")) for e in entries] == [
        ("reservation", 1, None),
        ("decision", 1, "procedure_failure"),
        ("reservation", 2, None),
        ("decision", 2, "procedure_failure"),
    ]
    assert entries[-1]["round1_entry_sha256"] == registry.entry_sha256(entries[1])
    assert registry.check_terminal(entries, "ship")  # refused
    assert registry.check_terminal(entries, "revert_0.3.3") == []
    assert registry.check_terminal(entries, "amendment") == []
    other = _res(rnd=2, cand=s["c1"], seed=990, cdir="elsewhere")
    assert registry.check_reservation(entries, other)[0] == "refuse"
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex2)


def test_r4_s1_aborted_execution_after_selection_registers_every_selected_text(
    tmp_path, monkeypatch
):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    _, ex = _plan(tmp_path, raw, dev_raw, reg)

    def boom(*a, **k):
        raise RuntimeError("post-fetch mapping failure")

    monkeypatch.setattr(collect, "raw_files_of", boom)
    with pytest.raises(RuntimeError):
        collect.main(ex)
    d = tmp_path / "r1"
    assert (d / collect.EXEC_ABORT).exists()
    assert _register(d, _archive(tmp_path, d, raw), reg, tmp_path / "fail", "--dry-run") == 0
    ex_ = read_json(tmp_path / "fail" / "failure.json")["exposure"]
    assert ex_["complete"] and ex_["ended"] == "selection completed"
    assert ex_["n_cached_refs"] > 0  # this (pre-populated) cache: every body is exposure
    f = registry.load(reg)[-1]
    assert f["failure"]["execution_abort_sha256"] == sha256_file(d / collect.EXEC_ABORT)
    # every journalled request is exposed (the 60 selected texts are among them)
    for e in _journal(d):
        if e["event"] == "request" and e["cache"].startswith("epmc/"):
            assert build._norm_ref(Path(e["cache"]).stem) in set(ex_["refs"])


def test_r4_s1_register_failure_refusals(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    _, ex = _plan(tmp_path, raw, dev_raw, reg)
    d = tmp_path / "r1"
    a = _archive(tmp_path, d, raw)
    with pytest.raises(SystemExit, match="never claimed"):  # planned, never executed
        _register(d, a, reg, tmp_path / "o", "--dry-run")
    assert collect.main(ex) == 0
    # completed, without --reason: refused (R4 Addendum 2 needs the named pre-label step)
    with pytest.raises(SystemExit, match="only with --reason"):
        _register(d, _archive(tmp_path, d, raw, "c.tar"), reg, tmp_path / "o", "--dry-run")
    assert not (tmp_path / "o").exists() and len(registry.load(reg)) == 1


def test_r4_s1_register_failure_checks_archive_lock_mode_and_registry(tmp_path):
    s = _hard_exit_round1(tmp_path)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    o = tmp_path / "o"
    # an archive without the journal, or with another raw cache, is refused
    bad = tmp_path / "bad.tar"
    with tarfile.open(bad, "w") as tf:
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name != collect.FETCH_JOURNAL:
                tf.add(f, arcname=f"collect/{f.name}")
        tf.add(raw, arcname="raw")
    with pytest.raises(SystemExit, match="lacks collect/fetch_journal.jsonl"):
        _register(d, bad, reg, o, "--dry-run")
    a = _archive(tmp_path, d, raw)
    (raw / "epmc" / "PMC9999999.xml").write_bytes(b"added after archiving")
    with pytest.raises(SystemExit, match="raw/ is not exactly"):
        _register(d, a, reg, o, "--dry-run")
    a = _archive(tmp_path, d, raw, "a2.tar")
    # a production registration of a dry record, and a dry run into the canonical registry
    with pytest.raises(SystemExit, match="not a production freeze record"):
        _register(d, a, reg, o)
    with pytest.raises(SystemExit, match="canonical registry"):
        _register(d, a, registry.canonical_path(), o, "--dry-run")
    # an execution still holding the round's lock
    holder = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import fcntl, os, sys, time; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT); "
            "fcntl.flock(fd, fcntl.LOCK_EX); print('locked', flush=True); time.sleep(30)",
            str(d / collect.EXEC_LOCK),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(SystemExit, match="is held"):
            _register(d, a, reg, o, "--dry-run")
    finally:
        holder.kill()
        holder.wait()
    assert not o.exists() and len(registry.load(reg)) == 1
    assert _register(d, a, reg, o, "--dry-run") == 0


def test_r4_s1_production_registration_revalidates_the_execution_receipt(tmp_path, monkeypatch):
    """A production failure registration in a temporary git repository: the start record's
    gate receipt is re-validated against committed objects; the canonical registry is
    appended atomically; a changed origin URL refuses."""
    from fixcheck.common import set_command

    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    monkeypatch.setattr(freeze, "REPO", repo)
    reg = _canonical_registry(repo)
    dev_raw, raw = _mock_cache(tmp_path)
    scratch = tmp_path / "scratch.jsonl"
    scratch.write_text("")
    out = repo / "round1" / "collect"
    rec, ex = _plan(tmp_path, raw, dev_raw, scratch, out=str(out.relative_to(tmp_path)))
    res = _res(cand=None, seed=777, cdir="round1/collect")
    registry.append_unchecked(reg, res)
    rec.update(
        dry_run=False,
        production_eligible=True,
        ineligible_reasons=[],
        registry={"path": str(reg), "reservation_sha256": registry.entry_sha256(res)},
    )
    rp = out / "freeze_record.json"
    rp.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(freeze, "receipt_paths", lambda record_path, record: [rp, reg])
    rc = freeze.archive_receipt([rp, reg], repo, "refs/remotes/origin/main")
    assert rc["ok"], rc["problems"]
    set_command("collect", ex)  # the recorded execution argv (claim_execution records it)
    collect.claim_execution(out, rec, rp, {"production": True, "ok": True, "receipt": rc}, "t")
    a = _archive(tmp_path, out, raw)
    _git(repo, "remote", "set-url", "origin", "https://example.invalid/another.git")
    with pytest.raises(SystemExit, match="remote URL differs"):
        _register(out, a, reg, tmp_path / "o")
    assert [e["type"] for e in registry.load(reg)] == ["reservation"]
    _git(repo, "remote", "set-url", "origin", "https://example.invalid/never-contacted.git")
    assert _register(out, a, reg, tmp_path / "o") == 0
    entries = registry.load(reg)
    assert [e.get("status") for e in entries] == [None, "procedure_failure"]
    assert read_json(tmp_path / "o" / "failure.json")["receipt"]["problems"] == []
    assert freeze.verify_receipt(rc, repo) == []  # the appended line extends the receipt


def test_r4_s1_production_acceptance_of_a_failed_round_refuses(pkg, tmp_path, monkeypatch):  # noqa: F811
    repo, reg, res, P = _production_package(pkg, tmp_path, monkeypatch)
    fail = {
        "type": "decision",
        "round": 1,
        "candidate_commit": res["candidate_commit"],
        "candidate_tree_sha256": None,
        "seed": res["seed"],
        "reservation_sha256": registry.entry_sha256(res),
        "freeze_record_sha256": "f",
        "collection_texts_sha256": None,
        "source_refs": [],
        "session_ids_sha256": [],
        "transcripts_sha256": [],
        "inputs_sha256": "failure-inputs",
        "status": "procedure_failure",
        "families": list(FAMILIES),
        "failure": dict.fromkeys(registry.FAILURE_KEYS, "x") | {"exposure_complete": True},
    }
    assert registry.check_decision(registry.load(reg), fail) == ("append", [])
    registry.append_unchecked(reg, fail)

    def arithmetic(*a, **k):
        raise AssertionError("the acceptance arithmetic was reached")

    monkeypatch.setattr(accept, "acceptance_of", arithmetic)
    with pytest.raises(SystemExit, match="refused before any decision"):
        accept.main(["--package", str(P), "--registry", str(reg), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()
    assert [e["type"] for e in registry.load(reg)] == ["reservation", "decision"]


def test_r4_s1_audit_probe_manual_failure_decision_and_round2_dead_end(tmp_path):
    # the audit: a manually constructed procedure_failure decision was admitted and round 2
    # was then a dead end in _round2_part. Now: a decision without failure evidence is
    # refused, and an unknown status is refused.
    res = _res(cand="c1", seed=5)
    bare = {
        "type": "decision",
        "round": 1,
        "candidate_commit": "c1",
        "candidate_tree_sha256": None,
        "seed": 5,
        "reservation_sha256": registry.entry_sha256(res),
        "freeze_record_sha256": "f",
        "collection_texts_sha256": None,
        "source_refs": [],
        "inputs_sha256": "i",
        "status": "procedure_failure",
        "families": list(FAMILIES),
    }
    v, probs = registry.check_decision([res], bare)
    assert v == "refuse" and any("failure evidence" in p for p in probs)
    v, probs = registry.check_decision([res], dict(bare, status="made_up"))
    assert v == "refuse" and any("not one of" in p for p in probs)


# --- R4-S3: the whole intended publication set carries no inventory fragment --------------

INVENTORY = REPO / ".cache" / "validation" / "study4" / "phrase_sense_inventory.md"
FIX040 = REPO / ".cache" / "validation" / "study4_fix040"
# the audit's reported match (its text is never reproduced): 21 characters, this SHA-256
AUDIT_FRAGMENT_SHA256 = "7c660af870e36ebc60ff9f2351a26301e4b0bf9790c90aa860b7c282feebfc12"


def _fragments() -> set[str]:
    text = INVENTORY.read_text(encoding="utf-8")
    return {f.strip() for f in re.split(r'[|;"*\n]', text) if len(f.strip()) >= 20}


def publication_set() -> list[Path]:
    """Every file the runbook's public allowlist publishes, as it is now (RUNBOOK section
    0.3, "Whole publication set"): the study scripts and harness with their tests, the
    candidate source and its tests, the protocol, clarifications and preregistration,
    docs/validation/study4-fix040/, and the ledger, dispositions and rulings that step 3
    copies there."""

    def tree(rel):
        root = REPO / rel
        return [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and "__pycache__" not in p.parts
            and ".pytest_cache" not in p.parts
            and p.suffix != ".pyc"
        ]

    files = [
        *tree("scripts/validation/study4_precision"),
        *tree("src/lexinspect"),
        *tree("tests"),
        *tree("docs/validation/study4-fix040"),
        REPO / "docs" / "validation" / "study4-fix-protocol.md",
        REPO / "docs" / "validation" / "study4-fix-protocol-clarifications.md",
        REPO / "docs" / "validation" / "study4-preregistration.md",
    ]
    for name in (
        "CANDIDATE_LEDGER.md",
        "HARNESS_AUDIT_R1_DISPOSITIONS.md",
        "HARNESS_AUDIT_R2_DISPOSITIONS.md",
        "HARNESS_AUDIT_R3_DISPOSITIONS.md",
        "HARNESS_AUDIT_R4_DISPOSITIONS.md",
        "HARNESS_AUDIT_R5_DISPOSITIONS.md",
        "HARNESS_RULINGS.md",
    ):
        if (FIX040 / name).exists():
            files.append(FIX040 / name)
    return files


@pytest.mark.skipif(not INVENTORY.exists(), reason="private inventory not present")
def test_r4_s3_whole_publication_set_has_no_inventory_fragment():
    frags = [f.encode("utf-8") for f in _fragments()]
    assert len(frags) > 100
    files = publication_set()
    rels = {p.relative_to(REPO).as_posix() for p in files}
    for must in (
        "src/lexinspect/_context.py",
        "src/lexinspect/_fix_families.py",
        "src/lexinspect/phrase.py",
        "tests/test_fix_families.py",
        "scripts/validation/study4_precision/fixcheck/failure.py",
        "docs/validation/study4-fix040/RUNBOOK.md",
        "docs/validation/study4-fix-protocol-clarifications.md",
        ".cache/validation/study4_fix040/HARNESS_AUDIT_R4_DISPOSITIONS.md",
    ):
        assert must in rels, must
    assert "docs/validation/study4-guidelines.md" not in rels  # private (Addendum 4)
    assert len(files) >= 90
    # counts per file only; the matched text is never printed (bytes: binaries included)
    hits = {
        p.relative_to(REPO).as_posix(): n
        for p in files
        if (n := sum(f in p.read_bytes() for f in frags))
    }
    assert hits == {}, sorted(hits)
    # the audit's one reported match is gone from the candidate comment (by its hash)
    by_hash = {hashlib.sha256(f).hexdigest(): f for f in frags}
    assert AUDIT_FRAGMENT_SHA256 in by_hash and len(by_hash[AUDIT_FRAGMENT_SHA256]) == 21
    assert by_hash[AUDIT_FRAGMENT_SHA256] not in (REPO / "src/lexinspect/_context.py").read_bytes()


# --- runbook: failure route, whole-set scan, durability, shell function (R4-S1/S3/B1/M1) ---

RUNBOOK = freeze.FREEZE_DIR / "RUNBOOK.md"


def test_r4_runbook_failure_route_scan_durability_and_function():
    text = RUNBOOK.read_text(encoding="utf-8")
    fail = text[text.index("**Failure.**") : text.index("## 6.")]
    for word in (
        "register-failure",
        "procedure_failure",
        "round1-aborted.tar",
        "--round-dir",
        "--archive",
        "exposure",
        "revert_0.3.3",
        "section 9",
    ):
        assert word in fail, word
    assert "The maintainer records the disposition of the consumed round" not in text
    for word in ("shortfall", "--reason", "procedure_failure.json", "pre-label step"):
        assert word in fail, word  # R4 Addendum 2
    assert "**Registry appends**" in text  # R4 Addendum 1
    r2 = text[text.index("## 9.") :]
    assert "procedure_failure" in r2 and "exposure" in r2
    assert "F_FULLFSYNC" in text and "honour" in text  # durability, with its residual
    scan = text[text.index("### 0.3") : text.index("### 0.4")]
    assert "Whole publication set" in scan and "There is no exemption" in scan
    for part in ("src/lexinspect", "tests", "HARNESS_AUDIT_R4_DISPOSITIONS.md"):
        assert part in scan, part
    assert "$FIX" not in text and 'FIX="' not in text


def test_r4_m1_runbook_shell_function_runs_in_zsh_and_sh(tmp_path):
    # the audit: zsh -fc 'FIX="printf ok"; $FIX' -> command not found
    text = RUNBOOK.read_text(encoding="utf-8")
    line = next(x.strip().strip("`") for x in text.splitlines() if "fix() {" in x)
    cmd = "uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py"
    assert cmd in line
    probe = line.replace(cmd, "printf '%s|'")
    for shell in ("zsh", "sh", "bash"):
        exe = shutil.which(shell)
        if exe is None:
            continue
        flags = ["-fc"] if shell == "zsh" else ["-c"]
        r = subprocess.run(
            [exe, *flags, probe + '; fix collect "a b"'], capture_output=True, text=True
        )
        assert r.stdout == "collect|a b|", (shell, r.stdout, r.stderr)


# --- R4 Addendum ruling 1: registry appends use the claim's durable barrier --------------


def _reg_repo(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    monkeypatch.setattr(freeze, "REPO", repo)
    reg = _canonical_registry(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "empty registry")
    return repo, reg


def _make(res):
    return lambda entries: (*registry.check_reservation(entries, res), res)


@pytest.mark.skipif(not DARWIN, reason="the macOS full barrier (F_FULLFSYNC) needs Darwin")
def test_r4_add1_darwin_registry_append_full_barrier_in_order(tmp_path, monkeypatch):
    repo, reg = _reg_repo(tmp_path, monkeypatch)
    spy = _Spy(monkeypatch, tmp_path)
    assert registry.atomic_append(reg, _make(_res()), repo)[0] == "append"
    assert spy.events == [("F_FULLFSYNC", reg.name), ("F_FULLFSYNC", reg.parent.name)]
    assert not [e for e in spy.events if e[0] == "fsync"]
    spy.events.clear()
    registry.append_unchecked(reg, {"type": "terminal", "outcome": "x"})
    assert spy.events == [("F_FULLFSYNC", reg.name), ("F_FULLFSYNC", reg.parent.name)]


def test_r4_add1_linux_registry_append_is_fsync_file_then_directory(tmp_path, monkeypatch):
    repo, reg = _reg_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    spy = _Spy(monkeypatch, tmp_path)
    assert registry.atomic_append(reg, _make(_res()), repo)[0] == "append"
    assert spy.events == [("fsync", reg.name), ("fsync", reg.parent.name)]


@pytest.mark.parametrize("where", ["file", "directory"])
def test_r4_add1_failed_registry_barrier_refuses_and_a_rerun_never_duplicates(
    tmp_path, monkeypatch, where
):
    repo, reg = _reg_repo(tmp_path, monkeypatch)
    want = reg.name if where == "file" else reg.parent.name

    def fail_on(spy, fd):
        return Path(spy.path_of(fd)).name == want

    if DARWIN:
        spy = _Spy(monkeypatch, tmp_path, fail_on=fail_on)
    else:
        monkeypatch.setattr(sys, "platform", "linux")
        spy = _Spy(monkeypatch, tmp_path, fail_on=fail_on)
    with pytest.raises(SystemExit, match="durable-write barrier failed"):
        registry.atomic_append(reg, _make(_res()), repo)
    assert spy.events  # the barrier was attempted and its failure refused the command
    monkeypatch.undo()
    monkeypatch.setattr(registry, "REPO", repo)
    monkeypatch.setattr(freeze, "REPO", repo)
    # the line may be on disk without the guarantee; the rerun finds it, never appends again
    assert registry.atomic_append(reg, _make(_res()), repo)[0] == "present"
    assert len(registry.load(reg)) == 1


@pytest.mark.parametrize("plat", ["win32", "sunos5"])
def test_r4_add1_registry_append_refused_without_a_barrier(tmp_path, monkeypatch, plat):
    repo, reg = _reg_repo(tmp_path, monkeypatch)
    before = reg.read_bytes()
    monkeypatch.setattr(sys, "platform", plat)
    v, probs, _ = registry.atomic_append(reg, _make(_res()), repo)
    assert v == "refuse" and any("no durable-write barrier" in p for p in probs)
    assert reg.read_bytes() == before  # nothing written


# --- R4 Addendum ruling 2: completed but unlabellable collections -------------------------


def _shortfall_round1(tmp_path, monkeypatch):
    """Round 1 from a synthetic origin that answers 20 of the 30 essay titles with a
    missing page: every essay is requested, 10 are collected, status shortfall (exit 2)."""
    dev_raw, origin = _mock_cache(tmp_path)
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    essays = json.loads((dev_raw / "pools" / "wiki_essays.json").read_text())["titles"]
    for t in essays[:20]:
        body = origin / "wiki" / f"{build._key(t)}.json"
        shutil.move(body, hidden / body.name)
        body.write_text(json.dumps({"query": {"pages": [{"title": t, "missing": True}]}}))
    raw = tmp_path / "cache1"
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    rec, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1, offline=False)
    _origin_in_process(monkeypatch, origin)
    assert collect.main(ex) == 2  # SHORTFALL
    d = tmp_path / "r1"
    assert read_json(d / "collection.json")["status"] == "shortfall"
    for f in hidden.iterdir():  # the origin serves every essay again (later rounds)
        shutil.move(f, origin / "wiki" / f.name)
    return dict(
        dev_raw=dev_raw, origin=origin, raw=raw, reg=reg, ex=ex, d=d, c1=c1, c2=c2, essays=essays
    )


def test_r4_add2_shortfall_register_failure_then_disjoint_round2(tmp_path, monkeypatch):
    s = _shortfall_round1(tmp_path, monkeypatch)
    d, raw, reg = s["d"], s["raw"], s["reg"]
    texts1 = read_jsonl(d / "texts.jsonl")
    assert 0 < len(texts1) < 60
    a = _archive(tmp_path, d, raw)
    assert _register(d, a, reg, tmp_path / "fail1", "--dry-run") == 0  # no --reason needed
    f = registry.load(reg)[-1]
    assert f["status"] == "procedure_failure" and f["failure"]["kind"] == "shortfall"
    assert f["failure"]["reason"].startswith("shortfall")
    assert f["collection_texts_sha256"] == sha256_file(d / "texts.jsonl")
    assert f["failure"]["exposure_complete"] is True
    ex = read_json(tmp_path / "fail1" / "failure.json")["exposure"]
    refs = set(ex["refs"])
    assert ex["completed_collection"] and ex["ended"] == "selection completed"
    assert build.read_exclusions(d / "texts.jsonl") <= refs  # the full collected text set
    assert {build._norm_ref(t) for t in s["essays"]} <= refs  # every requested essay
    marker = read_json(d / "procedure_failure.json")
    assert marker["inputs_sha256"] == f["inputs_sha256"] and marker["failure_kind"] == "shortfall"
    # the round is consumed: no execution, no other decision; idempotent re-registration
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(s["ex"])
    assert _register(d, a, reg, tmp_path / "fail1b", "--dry-run") == 0
    assert read_json(tmp_path / "fail1b" / "registration.json")["verdict"] == "idempotent"
    assert len(registry.load(reg)) == 2
    # round 2: fresh and disjoint from the whole exposure (not just round 1's texts)
    rec2, ex2 = _plan(
        tmp_path,
        tmp_path / "cache2",
        s["dev_raw"],
        reg,
        out="r2",
        rnd=2,
        seed="778",
        cand=s["c2"],
        earlier=[d],
        offline=False,
    )
    assert rec2["earlier_rounds"][0]["status"] == "procedure_failure"
    assert rec2["earlier_rounds"][0]["exposure_sha256"] == f["failure"]["exposure_sha256"]
    assert rec2["round2"]["earlier_identity"]["exposure_sha256"] == f["failure"]["exposure_sha256"]
    _origin_in_process(monkeypatch, s["origin"])
    rc = collect.main(ex2)
    assert rc in (0, 2)  # every essay was exposed in round 1, so round 2 has none left
    t2 = read_jsonl(tmp_path / "r2" / "texts.jsonl")
    r2refs = set().union(*(build.text_refs(t) for t in t2))
    assert t2 and not (r2refs & refs)
    assert not [t for t in t2 if t["register"] == "argumentative"]
    entries = registry.load(reg)
    r2res = entries[-1]
    d2 = {
        "type": "decision",
        "round": 2,
        "candidate_commit": r2res["candidate_commit"],
        "candidate_tree_sha256": r2res["candidate_tree_sha256"],
        "seed": 778,
        "reservation_sha256": registry.entry_sha256(r2res),
        "freeze_record_sha256": sha256_file(tmp_path / "r2" / "freeze_record.json"),
        "collection_texts_sha256": sha256_file(tmp_path / "r2" / "texts.jsonl"),
        "source_refs": package.source_refs_sha256(tmp_path / "r2" / "texts.jsonl"),
        "inputs_sha256": "i2",
        "status": "inconclusive",
        "families": list(FAMILIES),
        "round1_entry_sha256": registry.entry_sha256(f),
    }
    assert registry.check_decision(entries, d2) == ("append", [])
    v, probs = registry.check_decision(
        entries, dict(d2, source_refs=[*d2["source_refs"], f["source_refs"][0]])
    )
    assert v == "refuse" and any("disjoint" in p for p in probs)


def test_r4_add2_pre_label_step_needs_a_reason_and_excludes_the_whole_exposure(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    assert collect.main(ex) == 0
    d = tmp_path / "r1"
    a = _archive(tmp_path, d, raw)
    with pytest.raises(SystemExit, match="only with --reason"):
        _register(d, a, reg, tmp_path / "o", "--dry-run")
    reason = "the candidate run stage cannot complete"
    assert _register(d, a, reg, tmp_path / "o", "--dry-run", "--reason", reason) == 0
    f = registry.load(reg)[-1]
    assert f["failure"]["kind"] == "pre_label_step" and f["failure"]["reason"] == reason
    ex_ = read_json(tmp_path / "o" / "failure.json")["exposure"]
    assert ex_["complete"] and ex_["n_collected_refs"] > 0
    assert build.read_exclusions(d / "texts.jsonl") <= set(ex_["refs"])
    # later rounds exclude the whole exposure, not only the 60 texts
    rec2, _ = _plan(
        tmp_path,
        tmp_path / "cache2",
        dev_raw,
        reg,
        out="r2",
        rnd=2,
        seed="778",
        cand=c2,
        earlier=[d],
    )
    e = rec2["earlier_rounds"][0]
    assert e["status"] == "procedure_failure" and e["n_refs"] == len(ex_["refs"])
    assert e["n_refs"] > len(build.read_exclusions(d / "texts.jsonl"))
    # without its round-directory record the failed round is not authenticated
    os.chmod(d / "procedure_failure.json", 0o644)
    (d / "procedure_failure.json").unlink()
    with pytest.raises(SystemExit, match="procedure_failure.json"):
        _plan(
            tmp_path,
            tmp_path / "cache3",
            dev_raw,
            reg,
            out="r2b",
            rnd=2,
            seed="779",
            cand=c2,
            earlier=[d],
        )


def test_r4_add2_damaged_completed_collection_leaves_only_terminal_outcomes(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    assert collect.main(ex) == 0
    d = tmp_path / "r1"
    (d / "texts" / "T001.txt").write_text("edited after collection")
    a = _archive(tmp_path, d, raw)
    assert _register(d, a, reg, tmp_path / "o", "--dry-run", "--reason", "x") == 0
    f = registry.load(reg)[-1]
    assert f["failure"]["exposure_complete"] is False
    with pytest.raises(SystemExit, match="exposure"):
        _plan(
            tmp_path,
            tmp_path / "cache2",
            dev_raw,
            reg,
            out="r2",
            rnd=2,
            seed="778",
            cand=c2,
            earlier=[d],
        )
    assert registry.check_terminal(registry.load(reg), "ship")
    assert registry.check_terminal(registry.load(reg), "revert_0.3.3") == []


def test_r4_add2_registry_kind_rules():
    res = _res(cand="c1", seed=5)
    base = {
        "type": "decision",
        "round": 1,
        "candidate_commit": "c1",
        "candidate_tree_sha256": None,
        "seed": 5,
        "reservation_sha256": registry.entry_sha256(res),
        "freeze_record_sha256": "f",
        "source_refs": [],
        "inputs_sha256": "i",
        "status": "procedure_failure",
        "families": list(FAMILIES),
    }
    fail = dict.fromkeys(registry.FAILURE_KEYS, "x") | {"exposure_complete": True}

    def check(kind, texts):
        e = dict(base, collection_texts_sha256=texts, failure=dict(fail, kind=kind))
        return registry.check_decision([res], e)

    assert check("interrupted", None) == ("append", [])
    assert check("shortfall", "t") == ("append", [])
    assert check("pre_label_step", "t") == ("append", [])
    assert check("interrupted", "t")[0] == "refuse"
    assert check("shortfall", None)[0] == "refuse"
    assert check("made_up", None)[0] == "refuse"


def test_r4_add2_production_acceptance_of_a_shortfall_refuses(pkg, tmp_path, monkeypatch):  # noqa: F811
    repo, reg, res, P = _production_package(pkg, tmp_path, monkeypatch)
    c = P / "collect" / "collection.json"
    col = read_json(c)
    col["status"] = "shortfall"
    c.write_text(json.dumps(col))

    def arithmetic(*a, **k):
        raise AssertionError("the acceptance arithmetic was reached")

    monkeypatch.setattr(accept, "acceptance_of", arithmetic)
    with pytest.raises(SystemExit, match="shortfall"):
        accept.main(["--package", str(P), "--registry", str(reg), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()
    assert [e["type"] for e in registry.load(reg)] == ["reservation"]
