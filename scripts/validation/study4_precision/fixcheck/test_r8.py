"""Harness audit r5 dispositions (R5-S1, R5-S2, R5-S3, R5-M1, R5-M2, R5-M3): every executed
probe of sol_harness_audit_r5.md (sections 3, 5 and 7) is a regression here.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck

No test touches the network: collections read synthetic mock caches (test_fixcheck's
_mock_cache), the git repositories are local temporary ones, and the restricted-content
scanner is exercised on synthetic fragments (the real inventory only for the whole-set
count, which prints paths and counts, never a fragment). No real label exists anywhere.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402

from fixcheck import cli, collect, durable, failure, freeze, registry, scan  # noqa: E402
from fixcheck.common import canonical_json, read_json, sha256_file  # noqa: E402
from fixcheck.ledger import FAMILIES  # noqa: E402
from fixcheck.test_fixcheck import _mock_cache  # noqa: E402
from fixcheck.test_r4 import _dec, _git, _res  # noqa: E402
from fixcheck.test_r7 import (  # noqa: E402
    DARWIN,
    INVENTORY,
    REPO,
    _archive,
    _commits,
    _entry,
    _make,
    _out,
    _plan,
    _reg_repo,
    _register,
    _req,
    _Spy,
    _write_journal,
    publication_set,
)

RUNBOOK = freeze.FREEZE_DIR / "RUNBOOK.md"
CLARIFICATIONS = REPO / "docs" / "validation" / "study4-fix-protocol-clarifications.md"


def _platform_spy(monkeypatch, root, **kw) -> _Spy:
    if not DARWIN:
        monkeypatch.setattr(sys, "platform", "linux")
    return _Spy(monkeypatch, root, **kw)


def _barrier_events(reg: Path) -> list[tuple[str, str]]:
    kind = "F_FULLFSYNC" if DARWIN else "fsync"
    return [(kind, reg.name), (kind, reg.parent.name)]


class _Broken:
    """registry.durable_sync replaced by a recorder that always fails (the audit's probe)."""

    def __init__(self, monkeypatch):
        self.calls: list[str] = []

        def broken(fd, path):
            self.calls.append(str(path))
            raise durable.DurabilityError(errno.EIO, "injected barrier failure")

        monkeypatch.setattr(registry, "durable_sync", broken)


# --- R5-S1: a registry rerun acknowledges an existing line only after the barrier --------


def test_r5_s1_audit_probe_persistent_barrier_failure_refuses_every_retry(tmp_path, monkeypatch):
    # the audit: first call SystemExit, second returned 'present' with one barrier call total
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    broken = _Broken(monkeypatch)
    res = _res()
    with pytest.raises(SystemExit, match="durable-write barrier failed"):
        registry.atomic_append(reg, _make(res), require_integrity=False)
    with pytest.raises(SystemExit, match="already present but the durable-write barrier failed"):
        registry.atomic_append(reg, _make(res), require_integrity=False)
    assert len(registry.load(reg)) == 1 and len(broken.calls) == 2


def _decision_registry(tmp_path, monkeypatch):
    repo, reg = _reg_repo(tmp_path, monkeypatch)
    assert registry.atomic_append(reg, _make(_res()), repo)[0] == "append"
    return repo, reg


@pytest.mark.parametrize("kind", ["reservation", "decision"])
def test_r5_s1_broken_then_repaired_retry_rechecks_the_barrier(tmp_path, monkeypatch, kind):
    if kind == "reservation":
        repo, reg = _reg_repo(tmp_path, monkeypatch)
        make, ack = _make(_res()), "present"
    else:
        repo, reg = _decision_registry(tmp_path, monkeypatch)
        dec = _dec(res=registry.load(reg)[0])  # the reservation as registered

        def make(entries):
            return (*registry.check_decision(entries, dec), dec)

        ack = "idempotent"
    n0 = len(registry.load(reg))
    with monkeypatch.context() as m:
        broken = _Broken(m)
        with pytest.raises(SystemExit, match="line was written but its durable-write barrier"):
            registry.atomic_append(reg, make, repo)
        written = reg.read_bytes()
        assert len(registry.load(reg)) == n0 + 1
        # the barrier stays broken: the retry refuses, writes nothing, and did try the barrier
        with pytest.raises(SystemExit, match="already present but the durable-write barrier"):
            registry.atomic_append(reg, make, repo)
        assert broken.calls == [str(reg), str(reg)] and reg.read_bytes() == written
    # repaired: the retry passes the file-then-directory barrier and only then acknowledges
    with monkeypatch.context() as m:
        spy = _platform_spy(m, tmp_path)
        assert registry.atomic_append(reg, make, repo)[0] == ack
        assert spy.events == _barrier_events(reg)
    assert reg.read_bytes() == written and len(registry.load(reg)) == n0 + 1


def test_r5_s1_terminal_rerun_is_acknowledged_only_after_the_barrier(tmp_path, monkeypatch, capsys):
    repo, reg = _decision_registry(tmp_path, monkeypatch)
    dec = _dec(res=registry.load(reg)[0])
    assert registry.atomic_append(reg, lambda e: (*registry.check_decision(e, dec), dec), repo)[
        0
    ] == ("append")
    argv = [
        "register-terminal",
        "--outcome",
        "revert_0.3.3",
        "--basis",
        "b",
        "--registry",
        str(reg),
    ]
    with monkeypatch.context() as m:
        broken = _Broken(m)
        with pytest.raises(SystemExit, match="line was written"):
            cli.main(argv)
        written = reg.read_bytes()
        with pytest.raises(SystemExit, match="already present but the durable-write barrier"):
            cli.main(argv)
        assert len(broken.calls) == 2 and reg.read_bytes() == written
    with monkeypatch.context() as m:
        spy = _platform_spy(m, tmp_path)
        assert cli.main(argv) == 0
        assert spy.events == _barrier_events(reg)
    assert "durable barrier rechecked" in capsys.readouterr().out
    assert reg.read_bytes() == written and registry.load(reg)[-1]["outcome"] == "revert_0.3.3"
    # anything but the identical terminal is still refused: no acknowledgement, no line
    for other in (
        ["--outcome", "amendment", "--basis", "b"],
        ["--outcome", "revert_0.3.3", "--basis", "c"],
    ):
        with pytest.raises(SystemExit, match="already registered"):
            cli.main(["register-terminal", *other, "--registry", str(reg)])
    assert reg.read_bytes() == written


def test_r5_s1_same_terminal_needs_it_to_be_the_last_line():
    res, dec = _res(), _dec()
    term = {"type": "terminal", "outcome": "amendment", "basis": "b"}
    assert registry.same_terminal([res, dec, term], "amendment", "b")
    assert not registry.same_terminal([res, dec, term], "amendment", "x")
    assert not registry.same_terminal([res, dec, term], "ship", "b")
    assert not registry.same_terminal([res, dec], "amendment", "b")
    assert not registry.same_terminal([res, term, dec], "amendment", "b")


def test_r5_s1_dry_run_acknowledgements_pass_the_barrier(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    a = _archive(tmp_path, s["d"], s["raw"])
    assert _register(s["d"], a, s["reg"], tmp_path / "o1", "--dry-run") == 0
    with monkeypatch.context() as m:
        broken = _Broken(m)
        with pytest.raises(SystemExit, match="already present but the durable-write barrier"):
            _register(s["d"], a, s["reg"], tmp_path / "o2", "--dry-run")
        assert broken.calls == [str(s["reg"])]
    with monkeypatch.context() as m:
        broken = _Broken(m)
        with pytest.raises(SystemExit, match="already present but the durable-write barrier"):
            collect.main([*s["plan_argv"], "--plan-only", "--overwrite"])
        assert broken.calls == [str(s["reg"])]
    assert len(registry.load(s["reg"])) == 2


# --- the audit's independent durability and journal probes (section 3) -------------------


def test_r5_probe_durable_sync_file_then_directory_with_the_file_open(tmp_path, monkeypatch):
    f = tmp_path / "x"
    seen: list[tuple[str, bool]] = []
    fd = os.open(f, os.O_WRONLY | os.O_CREAT, 0o644)

    def barrier(bfd, what):
        try:
            os.fstat(fd)
            still_open = True
        except OSError:
            still_open = False
        seen.append(("dir" if what.startswith("the directory") else "file", still_open))
        if what.startswith("the directory") and fail["dir"]:
            raise durable.DurabilityError(errno.EIO, "injected directory failure")

    fail = {"dir": False}
    monkeypatch.setattr(durable, "_barrier", barrier)
    try:
        durable.durable_sync(fd, f)
        assert seen == [("file", True), ("dir", True)]
        fail["dir"] = True
        with pytest.raises(durable.DurabilityError):
            durable.durable_sync(fd, f)
    finally:
        os.close(fd)


def test_r5_probe_outcome_barrier_failure_escapes_after_one_fetch(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    (raw / "epmc").mkdir(parents=True)
    journal = tmp_path / "j.jsonl"
    journal.write_text("")
    real = collect.append_fsync
    n = {"appends": 0, "fetches": 0}

    def append(path, text):
        n["appends"] += 1
        if n["appends"] == 2:  # the outcome's barrier
            raise OSError(errno.EIO, "injected outcome barrier failure")
        real(path, text)

    monkeypatch.setattr(collect, "append_fsync", append)

    def fetch(url, cache, refresh=False):
        n["fetches"] += 1
        return b"<xml/>"

    rec = collect.FetchRecorder(raw, journal)
    wrapped = rec.wrap_fetch(fetch)
    with pytest.raises(collect.JournalBarrierFailure):
        try:
            wrapped("https://x/PMC1/fullTextXML", raw / "epmc" / "PMC1.xml")
        except Exception:  # build.py's per-article handler: it must not catch the failure
            pytest.fail("JournalBarrierFailure was caught as an Exception")
    assert n["fetches"] == 1
    lines = [json.loads(x) for x in journal.read_text().splitlines()]
    assert [x["event"] for x in lines] == ["request"]


@pytest.mark.parametrize(
    "mutation",
    [
        ("req", "seq", True),
        ("req", "seq", -1),
        ("req", "url", None),
        ("req", "cache", ["epmc/PMC1.xml"]),
        ("req", "refresh", 0),
        ("req", "cache_hit", 1),
        ("out", "url", "https://x/other"),
        ("out", "cache", "epmc/PMC2.xml"),
        ("out", "refresh", True),
        ("out", "cache_hit", False),
    ],
)
def test_r5_probe_request_identity_and_type_mutations_refuse(tmp_path, mutation):
    which, key, value = mutation
    f = _entry()
    req, out = _req(f), _out(f)
    (req if which == "req" else out)[key] = value
    j = _write_journal(tmp_path / "j", [req, out])
    assert collect.journal_problems(j, [f]) != []
    assert collect.journal_pairs(j, allow_trailing_request=True)[2] != []


@pytest.mark.parametrize("shape", ["array", "null", "invalid_utf8", "blank_line", "incomplete"])
def test_r5_probe_journal_shapes_are_integrity_problems(tmp_path, shape):
    f = _entry()
    j = _write_journal(tmp_path / "j", [_req(f), _out(f)])
    body = {
        "array": b"[1, 2]\n",
        "null": b"null\n",
        "invalid_utf8": b'{"event": "request", "url": "\xff"}\n',
        "blank_line": b"\n",
        "incomplete": canonical_json({"event": "request", "seq": 1}).encode() + b"\n",
    }[shape]
    with j.open("ab") as fh:
        fh.write(body)
    assert collect.journal_problems(j, [f]) != []
    assert collect.journal_pairs(j, allow_trailing_request=True)[2] != []


# --- R5-S2: damaged cached responses never block the terminal failure registration -------


def _wiki_bodies(raw: Path) -> list[Path]:
    return sorted((raw / "wiki").glob("*.json"))


def _damage(raw: Path, damage: str) -> None:
    for f in _wiki_bodies(raw):
        if damage == "null_page":
            f.write_text('{"query":{"pages":[null]}}')  # the audit's exact body
        elif damage == "scalar_page":
            f.write_text('{"query":{"pages":[7]}}')
        elif damage in ("null_revision", "scalar_revision"):
            d = json.loads(f.read_text())
            d["query"]["pages"][0]["revisions"] = [None if damage == "null_revision" else 5]
            f.write_text(json.dumps(d))
        elif damage == "truncated":
            data = f.read_bytes()
            f.write_bytes(data[: len(data) // 2])
        else:  # undecodable bytes
            f.write_bytes(b"\xff\xfe\x00\x00 not a response")


@pytest.mark.parametrize(
    "damage",
    ["null_page", "scalar_page", "null_revision", "scalar_revision", "truncated", "undecodable"],
)
def test_r5_s2_damaged_wikipedia_body_aborts_then_registers_with_exposure_incomplete(
    tmp_path, damage
):
    # the audit: _mock_cache bodies damaged before planning, real offline collection aborts,
    # register-failure raised AttributeError and the registry held only the reservation
    dev_raw, raw = _mock_cache(tmp_path)
    _damage(raw, damage)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    with pytest.raises(Exception):  # noqa: B017 - whatever build.py raises on the body
        collect.main(ex)
    d = tmp_path / "r1"
    assert (d / collect.EXEC_ABORT).exists() and not (d / collect.EXEC_DONE).exists()
    damaged = {f.name: f.read_bytes() for f in _wiki_bodies(raw)}
    assert _register(d, _archive(tmp_path, d, raw), reg, tmp_path / "fail", "--dry-run") == 0
    assert {f.name: f.read_bytes() for f in _wiki_bodies(raw)} == damaged  # never repaired
    entries = registry.load(reg)
    assert [(e["type"], e.get("status")) for e in entries] == [
        ("reservation", None),
        ("decision", "procedure_failure"),
    ]
    f = entries[-1]
    assert f["failure"]["exposure_complete"] is False and f["failure"]["kind"] == "interrupted"
    exp = read_json(tmp_path / "fail" / "failure.json")["exposure"]
    assert exp["complete"] is False
    assert any("Wikipedia body" in p for p in exp["problems"])
    # the requested title of every journalled Wikipedia request is still counted
    for e in collect.read_journal(d / collect.FETCH_JOURNAL)[0]:
        if e["event"] == "request" and e["cache"].startswith("wiki/"):
            q = e["url"].split("titles=")[1].split("&")[0]
            title = build.urllib.parse.unquote_plus(q)
            assert build._norm_ref(title) in set(exp["refs"])
    # both non-pass terminals are admitted; ship is not; no round 2
    assert registry.check_terminal(entries, "revert_0.3.3") == []
    assert registry.check_terminal(entries, "amendment") == []
    assert registry.check_terminal(entries, "ship")
    v, probs = registry.check_reservation(entries, _res(rnd=2, cand=c2, seed=778, cdir="r2"))
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    with pytest.raises(SystemExit, match="exposure"):
        _plan(
            tmp_path,
            tmp_path / "c2",
            dev_raw,
            reg,
            out="r2",
            rnd=2,
            seed="778",
            cand=c2,
            earlier=[d],
        )
    assert len(registry.load(reg)) == 2


@pytest.mark.parametrize(
    "body",
    [
        b"[]",
        b"null",
        b'{"query": null}',
        b'{"query": {"pages": {}}}',
        b'{"query": {"pages": [null]}}',
        b'{"query": {"pages": [7]}}',
        b'{"query": {"pages": [{"title": "T"}]}}',
        b'{"query": {"pages": [{"pageid": true, "title": "T"}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": 5}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": ""}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": "T", "revisions": {}}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": "T", "revisions": [null]}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": "T", "revisions": [5]}]}}',
        b'{"query": {"pages": [{"pageid": 1, "title": "T", "revisions": [{"revid": "9"}]}]}}',
        b'{"query": {"pa',
        b"\xff\xfe\x00",
    ],
)
def test_r5_s2_wiki_body_schema_violations_are_problems_never_exceptions(tmp_path, body):
    f = tmp_path / "b.json"
    f.write_bytes(body)
    refs, probs = failure._wiki_body_refs(f)
    assert refs == set() and len(probs) == 1


def test_r5_s2_wiki_body_valid_and_unreadable(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text(
        json.dumps(
            {
                "query": {
                    "pages": [
                        {"title": "Gone", "missing": True},
                        {"pageid": 3, "title": "Page", "revisions": [{"revid": 11}]},
                    ]
                }
            }
        )
    )
    refs, probs = failure._wiki_body_refs(ok)
    assert probs == [] and refs == {
        build._norm_ref(x)
        for x in ("pageid:3", "Page", "https://en.wikipedia.org/w/index.php?oldid=11")
    }
    d = tmp_path / "dir.json"
    d.mkdir()  # reading it raises an OSError
    refs, probs = failure._wiki_body_refs(d)
    assert refs == set() and "cannot be read" in probs[0]


def test_r5_s2_damaged_pool_listing_is_a_problem(tmp_path):
    raw = tmp_path / "raw"
    (raw / "pools").mkdir(parents=True)
    (raw / "pools" / "a.json").write_text('{"rows": [null, {"pmcid": 5}], "titles": [3]}')
    (raw / "pools" / "b.json").write_bytes(b"{trunc")
    (raw / "pools" / "c.json").write_text("[]")
    rows, titles, probs = failure._pool_maps(raw)
    assert rows == {} and titles == {} and len(probs) == 5


def _aborted_round1(tmp_path, monkeypatch):
    """Round 1 aborted after its selection (a post-fetch mapping failure): fast, with an
    abort record, a complete journal and a pre-populated cache."""
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    rec, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    plan_argv = [
        "--round", "1", "--seed", "777", "--out", str(tmp_path / "r1"), "--raw-cache", str(raw),
        "--dev-raw", str(dev_raw), "--offline", "--dry-run", "--registry", str(reg),
        "--candidate-commit", c1,
    ]  # fmt: skip

    def boom(*a, **k):
        raise RuntimeError("post-fetch mapping failure")

    with monkeypatch.context() as m:
        m.setattr(collect, "raw_files_of", boom)
        with pytest.raises(RuntimeError):
            collect.main(ex)
    d = tmp_path / "r1"
    assert (d / collect.EXEC_ABORT).exists()
    return dict(dev_raw=dev_raw, raw=raw, reg=reg, d=d, c1=c1, c2=c2, ex=ex, plan_argv=plan_argv)


def test_r5_s2_truncated_abort_record_registers_with_exposure_incomplete(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    ab = s["d"] / collect.EXEC_ABORT
    data = ab.read_bytes()
    ab.write_bytes(data[: len(data) // 3])  # as if the crash it records cut it short
    a = _archive(tmp_path, s["d"], s["raw"])
    assert _register(s["d"], a, s["reg"], tmp_path / "fail", "--dry-run") == 0
    f = registry.load(s["reg"])[-1]
    assert f["status"] == "procedure_failure" and f["failure"]["exposure_complete"] is False
    exp = read_json(tmp_path / "fail" / "failure.json")["exposure"]
    assert any("abort record cannot be read" in p for p in exp["problems"])


def test_r5_s2_authentication_failures_still_refuse(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    d = s["d"]
    ab = d / collect.EXEC_ABORT
    good = ab.read_bytes()
    ab.write_text(json.dumps(dict(json.loads(good), freeze_record_sha256="0" * 64)))
    with pytest.raises(SystemExit, match="not this round's abort record"):
        _register(
            d, _archive(tmp_path, d, s["raw"], "a.tar"), s["reg"], tmp_path / "o", "--dry-run"
        )
    ab.write_bytes(good)
    # a readable start record that names another freeze record is refused (only an
    # unreadable one is registrable: R5 Addendum ruling 2)
    st = d / collect.EXEC_START
    os.chmod(st, 0o644)
    st.write_text(json.dumps(dict(json.loads(st.read_bytes()), freeze_record_sha256="0" * 64)))
    with pytest.raises(SystemExit, match="does not name this freeze record"):
        _register(
            d, _archive(tmp_path, d, s["raw"], "b.tar"), s["reg"], tmp_path / "o", "--dry-run"
        )
    assert len(registry.load(s["reg"])) == 1 and not (tmp_path / "o").exists()


# --- audit section 3: crash after the registry append, extra cached source ---------------


def test_r5_probe_crash_after_registry_append_recovers_and_authenticates(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg = s["d"], s["reg"]
    a = _archive(tmp_path, d, s["raw"])

    def stop(*a, **k):
        raise RuntimeError("injected stop before the round marker")

    with monkeypatch.context() as m:
        m.setattr(failure, "_write_failure_record", stop)
        with pytest.raises(RuntimeError):
            _register(d, a, reg, tmp_path / "o", "--dry-run")
    assert len(registry.load(reg)) == 2 and not (d / failure.FAILURE_RECORD).exists()
    assert _register(d, a, reg, tmp_path / "o", "--dry-run") == 0
    assert len(registry.load(reg)) == 2 and (d / failure.FAILURE_RECORD).exists()
    ident, probs = failure.authenticate_failed_round(d, registry.load(reg)[-1])
    assert probs == [] and ident["status"] == "procedure_failure"


def test_r5_probe_extra_cached_source_after_registration_refuses_round2(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg, raw = s["d"], s["reg"], s["raw"]
    assert _register(d, _archive(tmp_path, d, raw), reg, tmp_path / "o", "--dry-run") == 0
    r1 = registry.load(reg)[-1]
    assert failure.authenticate_failed_round(d, r1)[1] == []
    # an identifiable body the execution never cached (the audit's extra cached source)
    t = "Synthetic extra page"
    assert not (raw / "wiki" / f"{build._key(t)}.json").exists()
    (raw / "wiki" / f"{build._key(t)}.json").write_text(
        json.dumps(
            {"query": {"pages": [{"pageid": 424242, "title": t, "revisions": [{"revid": 1}]}]}}
        )
    )
    _, probs = failure.authenticate_failed_round(d, r1)
    assert any("differs from the registered one" in p for p in probs)


# --- R5-M1: same-output recovery without --overwrite -------------------------------------


@pytest.mark.parametrize(
    "where", ["before_marker", "after_marker", "after_failure_json", "after_registration_json"]
)
def test_r5_m1_interrupted_registration_recovers_with_the_same_command(
    tmp_path, monkeypatch, where
):
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg = s["d"], s["reg"]
    a = _archive(tmp_path, d, s["raw"])
    o = tmp_path / "fail"

    def stop(*a, **k):
        raise RuntimeError(f"injected stop {where}")

    real_marker, real_json = failure._write_failure_record, failure.write_json
    with monkeypatch.context() as m:
        if where == "before_marker":
            m.setattr(failure, "_write_failure_record", stop)
        elif where == "after_marker":

            def marker_then_stop(*a, **k):
                real_marker(*a, **k)
                stop()

            m.setattr(failure, "_write_failure_record", marker_then_stop)
        elif where == "after_failure_json":  # the audit's probe: stop at registration.json

            def json_stop(path, obj):
                if Path(path).name == "registration.json":
                    stop()
                real_json(path, obj)

            m.setattr(failure, "write_json", json_stop)
        else:
            m.setattr(failure, "write_step_manifest", stop)
        with pytest.raises(RuntimeError, match="injected stop"):
            _register(d, a, reg, o, "--dry-run")
    assert len(registry.load(reg)) == 2
    # the same command, the same --out, no --overwrite
    assert _register(d, a, reg, o, "--dry-run") == 0
    entries = registry.load(reg)
    assert len(entries) == 2
    assert read_json(o / "registration.json")["entry"] == entries[-1]
    assert entries[-1]["acceptance_sha256"] == sha256_file(o / "failure.json")
    man = read_json(o / "manifest_register_failure.json")["outputs"]
    assert man["failure.json"]["sha256"] == sha256_file(o / "failure.json")
    assert man["registration.json"]["sha256"] == sha256_file(o / "registration.json")
    assert (d / failure.FAILURE_RECORD).exists()
    # a fresh output directory reproduces failure.json byte for byte
    assert _register(d, a, reg, tmp_path / "fresh", "--dry-run") == 0
    assert (tmp_path / "fresh" / "failure.json").read_bytes() == (o / "failure.json").read_bytes()
    # a completed registration rerun into the same --out keeps registration.json as it was
    before = (o / "registration.json").read_bytes()
    assert _register(d, a, reg, o, "--dry-run") == 0
    assert (o / "registration.json").read_bytes() == before


def test_r5_m1_foreign_outputs_are_refused_without_touching_the_registry(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg = s["d"], s["reg"]
    a = _archive(tmp_path, d, s["raw"])
    o = tmp_path / "fail"
    o.mkdir()
    (o / "failure.json").write_text('{"another": "registration"}\n')
    with pytest.raises(SystemExit, match="exists for another registration input"):
        _register(d, a, reg, o, "--dry-run")
    assert len(registry.load(reg)) == 1 and not (d / failure.FAILURE_RECORD).exists()
    assert _register(d, a, reg, o, "--dry-run", "--overwrite") == 0  # explicit replacement
    assert len(registry.load(reg)) == 2
    reg_json = o / "registration.json"
    reg_json.write_text(json.dumps({"registry": str(reg), "verdict": "append", "entry": {}}))
    with pytest.raises(SystemExit, match="does not record this registration"):
        _register(d, a, reg, o, "--dry-run")
    assert len(registry.load(reg)) == 2


def test_r5_m1_failure_docstring_states_the_write_order():
    doc = failure.__doc__
    i_reg = doc.index("appends one decision line")
    i_marker = doc.index("D/procedure_failure.json")
    i_private = doc.index("then writes O/failure.json")
    assert i_reg < i_marker < i_private


# --- R5-M3: the Python byte scanner -------------------------------------------------------

SYNTH_FRAGMENTS = ["alpha bravo charlie delta echo", "foxtrot golf hotel india juliet"]


def _scan(argv, capsys) -> tuple[int, str, str]:
    rc = scan.main(argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def _frag_file(tmp_path) -> Path:
    inv = tmp_path / "inv.md"
    inv.write_text("| " + " | ".join(SYNTH_FRAGMENTS) + " | short |\n")
    f = tmp_path / "private" / "frags.txt"
    assert scan.main(["fragments", "--inventory", str(inv), "--out", str(f)]) == 0
    return f


def _scan_repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    for rel in scan.TREES:
        (repo / rel).mkdir(parents=True)
        (repo / rel / "a.txt").write_text("clean\n")
    for rel in scan.FILES:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("clean\n")
    (repo / scan.FIX040).mkdir(parents=True)
    for n in scan.COPIED:
        (repo / scan.FIX040 / n).write_text("clean\n")
    return repo


def test_r5_m3_fragments_match_the_runbook_rule(tmp_path):
    f = _frag_file(tmp_path)
    assert sorted(f.read_text().splitlines()) == sorted(SYNTH_FRAGMENTS)


def test_r5_m3_staged_blob_with_a_clean_worktree_is_reported_without_the_fragment(tmp_path, capsys):
    # the audit: staged sensitive bytes, clean working tree, in a temporary git repository
    frags = _frag_file(tmp_path)
    repo = _scan_repo(tmp_path)
    (repo / "c.py").write_text(f"x = '{SYNTH_FRAGMENTS[0]}'\n")
    _git(repo, "add", "c.py")
    (repo / "c.py").write_text("x = 'clean'\n")
    rc, out, err = _scan(["staged", "--fragments", str(frags), "--repo", str(repo)], capsys)
    assert rc == 1 and "RESTRICTED (staged blob): c.py (1 fragments)" in out
    assert scan.DONE not in out
    # working tree only
    _git(repo, "add", "c.py")
    (repo / "c.py").write_text(f"x = '{SYNTH_FRAGMENTS[1]}'\n")
    rc, out, err = _scan(["staged", "--fragments", str(frags), "--repo", str(repo)], capsys)
    assert rc == 1 and "RESTRICTED (working tree): c.py" in out
    # binary bytes are matched too
    (repo / "c.py").write_text("x = 'clean'\n")
    (repo / "b.bin").write_bytes(b"\x00\xff" + SYNTH_FRAGMENTS[1].encode() + b"\x00")
    _git(repo, "add", "c.py", "b.bin")
    rc, out, err = _scan(["staged", "--fragments", str(frags), "--repo", str(repo)], capsys)
    assert rc == 1 and "RESTRICTED (staged blob): b.bin" in out and "ok: c.py" in out
    for text in (out, err):
        assert not any(fr in text for fr in SYNTH_FRAGMENTS)  # paths and counts only
    _git(repo, "rm", "-q", "--cached", "b.bin")
    rc, out, _ = _scan(["staged", "--fragments", str(frags), "--repo", str(repo)], capsys)
    assert rc == 0 and out.rstrip().endswith(scan.DONE) and "ok: c.py" in out


@pytest.mark.parametrize("fault", ["missing", "empty", "short_line", "unreadable"])
def test_r5_m3_fragment_file_faults_fail_without_ok_lines(tmp_path, capsys, fault):
    # the audit: grep's error went to stderr and the loop still printed ok, status 0
    frags = _frag_file(tmp_path)
    repo = _scan_repo(tmp_path)
    (repo / "c.py").write_text("x = 1\n")
    _git(repo, "add", "c.py")
    if fault == "missing":
        frags.unlink()
    elif fault == "empty":
        frags.write_text("\n\n")
    elif fault == "short_line":
        frags.write_text(SYNTH_FRAGMENTS[0] + "\nshort\n")
    else:
        frags.unlink()
        frags.mkdir()
    for mode in ("staged", "whole-set"):
        rc, out, err = _scan([mode, "--fragments", str(frags), "--repo", str(repo)], capsys)
        assert rc == 2 and "NOT COMPLETED" in err
        assert "ok:" not in out and scan.DONE not in out


def test_r5_m3_whole_set_read_and_listing_failures(tmp_path, capsys):
    frags = _frag_file(tmp_path)
    repo = _scan_repo(tmp_path)
    argv = ["whole-set", "--fragments", str(frags), "--repo", str(repo)]
    rc, out, _ = _scan(argv, capsys)
    n = len(scan.publication_set(repo))
    assert rc == 0 and f"publication-set files read: {n}; restricted: 0" in out
    assert out.rstrip().endswith(scan.DONE)
    # a fragment anywhere in the set (binary included)
    hit = repo / scan.TREES[1] / "x.bin"
    hit.write_bytes(b"\x00" + SYNTH_FRAGMENTS[0].encode())
    rc, out, err = _scan(argv, capsys)
    assert rc == 1 and f"RESTRICTED: {scan.TREES[1]}/x.bin (1 fragments)" in out
    assert scan.DONE not in out and SYNTH_FRAGMENTS[0] not in out + err
    hit.unlink()
    # a missing copied file, an unreadable file, an unreadable directory: not completed
    gone = repo / scan.FIX040 / scan.COPIED[-1]
    gone.unlink()
    rc, out, err = _scan(argv, capsys)
    assert rc == 2 and "missing" in err and scan.DONE not in out
    gone.write_text("clean\n")
    if os.geteuid() != 0:
        locked = repo / scan.TREES[0] / "a.txt"
        locked.chmod(0)
        try:
            rc, out, err = _scan(argv, capsys)
            assert rc == 2 and "cannot be read" in err and scan.DONE not in out
        finally:
            locked.chmod(0o644)
        sub = repo / scan.TREES[2] / "sub"
        sub.mkdir()
        sub.chmod(0)
        try:
            rc, out, err = _scan(argv, capsys)
            assert rc == 2 and "listing failed" in err and scan.DONE not in out
        finally:
            sub.chmod(0o755)
    shutil.rmtree(repo / scan.TREES[3])
    rc, out, err = _scan(argv, capsys)
    assert rc == 2 and "not a directory" in err


def test_r5_m3_staged_outside_a_repository_and_inventory_faults(tmp_path, capsys):
    frags = _frag_file(tmp_path)
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    rc, out, err = _scan(["staged", "--fragments", str(frags), "--repo", str(nogit)], capsys)
    assert rc == 2 and "git diff failed" in err and scan.DONE not in out
    out_f = tmp_path / "f2.txt"
    rc, _, err = _scan(
        ["fragments", "--inventory", str(tmp_path / "none.md"), "--out", str(out_f)], capsys
    )
    assert rc == 2 and "inventory cannot be read" in err and not out_f.exists()
    (tmp_path / "tiny.md").write_text("| a | b |\n")
    rc, _, err = _scan(
        ["fragments", "--inventory", str(tmp_path / "tiny.md"), "--out", str(out_f)], capsys
    )
    assert rc == 2 and "no fragment" in err


@pytest.mark.skipif(not INVENTORY.exists(), reason="private inventory not present")
def test_r5_m3_actual_tree_whole_set_is_clean_and_matches_the_test_set(tmp_path, capsys):
    frags = tmp_path / "frags.txt"
    rc, _, _ = _scan(["fragments", "--inventory", str(INVENTORY), "--out", str(frags)], capsys)
    assert rc == 0
    from fixcheck.test_r7 import _fragments

    assert set(frags.read_text(encoding="utf-8").splitlines()) == _fragments()
    rc, out, err = _scan(["whole-set", "--fragments", str(frags)], capsys)
    files = scan.publication_set()
    assert {p.resolve() for p in files} == {p.resolve() for p in publication_set()}
    assert rc == 0, out + err
    assert f"publication-set files read: {len(files)}; restricted: 0" in out
    assert out.rstrip().endswith(scan.DONE)
    lines = frags.read_bytes().split(b"\n")
    assert not any(x and x in (out + err).encode() for x in lines)  # nothing restricted printed


def test_r5_m3_scanner_through_the_cli_subprocess(tmp_path):
    frags = _frag_file(tmp_path)
    repo = _scan_repo(tmp_path)
    r = subprocess.run(
        [sys.executable, "-I", str(HERE / "cli.py"), "scan-restricted", "whole-set",
         "--fragments", str(frags), "--repo", str(repo)],
        capture_output=True, text=True,
    )  # fmt: skip
    assert r.returncode == 0 and r.stdout.rstrip().endswith(scan.DONE), r.stderr
    frags.unlink()
    r = subprocess.run(
        [sys.executable, "-I", str(HERE / "cli.py"), "scan-restricted", "whole-set",
         "--fragments", str(frags), "--repo", str(repo)],
        capture_output=True, text=True,
    )  # fmt: skip
    assert r.returncode == 2 and scan.DONE not in r.stdout


# --- registry route matrix (audit section 3) ----------------------------------------------


def _failure_entry(res, complete=True, refs=("e1", "e2")):
    return {
        "type": "decision",
        "round": 1,
        "candidate_commit": res["candidate_commit"],
        "candidate_tree_sha256": None,
        "seed": res["seed"],
        "reservation_sha256": registry.entry_sha256(res),
        "freeze_record_sha256": "f",
        "collection_texts_sha256": None,
        "source_refs": list(refs),
        "session_ids_sha256": [],
        "transcripts_sha256": [],
        "inputs_sha256": "fail-inputs",
        "status": "procedure_failure",
        "acceptance_sha256": "a",
        "families": list(FAMILIES),
        "failure": dict.fromkeys(registry.FAILURE_KEYS, "x")
        | {"exposure_complete": complete, "kind": "interrupted"},
    }


def test_r5_probe_registry_route_matrix_after_a_round1_failure():
    res1 = _res(cand="c1", seed=1)
    f1 = _failure_entry(res1)
    base = [res1, f1]
    for status in ("pass", "inconclusive", "fail"):  # nothing else decides a consumed round
        v, _ = registry.check_decision(base, _dec(status=status, inputs="new", res=res1))
        assert v == "refuse", status
    res2 = _res(rnd=2, cand="c2", seed=2, cdir="r2")
    assert registry.check_reservation(base, res2) == ("append", [])
    with_r2 = [*base, res2]
    d2 = _dec(rnd=2, cand="c2", seed=2, refs=("z1",), res=res2, r1=f1, texts="t2", inputs="i2")
    assert registry.check_decision(with_r2, d2) == ("append", [])
    overlap = dict(d2, source_refs=["z1", "e2"])
    v, probs = registry.check_decision(with_r2, overlap)
    assert v == "refuse" and any("disjoint" in p for p in probs)
    # incomplete exposure: neither a round-2 reservation nor a round-2 decision
    inc = [res1, _failure_entry(res1, complete=False)]
    assert registry.check_reservation(inc, res2)[0] == "refuse"
    d2_inc = dict(d2, round1_entry_sha256=registry.entry_sha256(inc[1]))
    assert registry.check_decision([*inc, res2], d2_inc)[0] == "refuse"
    # round 3, a second round-2 decision, ship after failure, unknown terminal
    assert registry.check_reservation(with_r2, _res(rnd=3, cand="c3", seed=3, cdir="r3"))[0] == (
        "refuse"
    )
    done = [*with_r2, d2]
    assert registry.check_decision(done, dict(d2, inputs_sha256="other"))[0] == "refuse"
    assert registry.check_terminal(base, "ship") != []
    assert registry.check_terminal(base, "made_up") != []
    assert registry.check_terminal(base, "revert_0.3.3") == []
    assert registry.check_terminal(base, "amendment") == []
    # after a terminal: no reservation, no decision
    term = [*base, {"type": "terminal", "outcome": "amendment", "basis": "b"}]
    assert registry.check_reservation(term, res2)[0] == "refuse"
    assert registry.check_decision([*term, res2], d2)[0] == "refuse"


# --- R5-S3 / R5-M2 / R5-M1 / R5-M3: the operator documents ------------------------------


def test_r5_runbook_and_clarifications_state_the_r5_rules():
    rb = RUNBOOK.read_text(encoding="utf-8")
    cl = CLARIFICATIONS.read_text(encoding="utf-8")
    fail = rb[rb.index("**Failure.**") : rb.index("## 6.")]
    # S3: the exhausted-stratum warning beside shortfall registration and continuation
    assert "A shortfall exhausts its stratum" in fail
    for word in ("no** eligible unexposed source", "new seed", "revert_0.3.3", "listing counts"):
        assert word in fail, word
    for n in ("3,502", "7,686", "597", "961", "2,040"):
        assert n in fail and n in cl, n
    assert "interrupted execution" in fail.split("A shortfall exhausts its stratum")[1]
    r2 = rb[rb.index("## 9.") :]
    assert "After a round-1 shortfall" in r2
    assert "A shortfall exhausts its stratum (R5-S3)" in cl
    # M2: the registry is kept in round 2
    assert "the registry is kept (R5-M2)" in r2 and "never reset" in r2
    assert "Skip the empty-registry requirement of step 3.4" in r2
    # S1: registry rerun acknowledgement after the barrier; terminal handling
    assert "acknowledged only after the same file-plus-directory barrier" in rb
    assert "R5-S1" in cl
    # M1: write order and same-output recovery
    reg_para = fail[fail.index("**Registration.**") :]
    assert reg_para.index("round_registry.jsonl") < reg_para.index("procedure_failure.json")
    assert reg_para.index("procedure_failure.json") < reg_para.index("`failure.json`")
    assert "without `--overwrite`" in reg_para
    # S2: damaged evidence registers, authentication refuses
    assert "Never repair, replace or delete a damaged cached response" in fail
    assert "Damaged evidence never blocks the closure (R5-S2)" in cl
    # M3: the Python scanner replaced the shell loops; no grep loop remains
    s03 = rb[rb.index("### 0.3") : rb.index("### 0.4")]
    assert "scan-restricted fragments" in s03 and "scan-restricted staged" in s03
    assert "scan-restricted whole-set" in s03 and "status 2" in s03
    assert "grep -q" not in rb and "for f in $(" not in rb
    assert "HARNESS_AUDIT_R5_DISPOSITIONS.md" in rb.split("## 4.")[0]
    plan = next(x for x in rb.splitlines() if "--plan-only" in x and "collect --round 1" in x)
    assert "HARNESS_AUDIT_R5_DISPOSITIONS.md" in plan


# --- R5 Addendum ruling 2: an unreadable (truncated) start record is registrable ----------

TRUNCATING_DRIVER = r"""
import json, os, sys
from pathlib import Path

study4, argv_json = sys.argv[1:3]
sys.path.insert(0, study4)
from fixcheck import collect

real = collect.write_exclusive


def write_exclusive(path, data, mode=0o444):
    if Path(path).name == collect.EXEC_START:
        # the claim's write is cut short: half the bytes reach the file, then the process
        # dies before the barrier returns (as on power loss or a crash mid-write)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        os.write(fd, data[: len(data) // 2])
        os._exit(9)
    return real(path, data, mode)


collect.write_exclusive = write_exclusive
sys.exit(collect.main(json.loads(argv_json)))
"""


def _truncated_claim(tmp_path, extra_cache=False):
    """Round 1 planned, then its claim killed in the middle of writing the start record (a
    real subprocess): a truncated start record and no journal file."""
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    drv = tmp_path / "trunc_driver.py"
    drv.write_text(TRUNCATING_DRIVER)
    r = subprocess.run(
        [sys.executable, "-I", str(drv), str(HERE.parent), json.dumps(ex)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 9, r.stdout + r.stderr
    d = tmp_path / "r1"
    st = d / collect.EXEC_START
    assert st.exists() and st.stat().st_size > 0 and failure.start_unreadable(d)
    assert not (d / collect.FETCH_JOURNAL).exists() and not (d / collect.EXEC_ABORT).exists()
    if extra_cache:
        (raw / "wiki" / "unplanned.json").write_text('{"query": {"pages": []}}')
    return dict(dev_raw=dev_raw, raw=raw, reg=reg, d=d, ex=ex, c1=c1, c2=c2)


def _terminal_only(tmp_path, d, reg, dev_raw, c2, start="unreadable") -> dict:
    """The revised ruling 2 (audit r6 B1): one procedure_failure, exposure incomplete, no
    round-2 reservation or plan, both non-pass terminals admitted, ship refused."""
    entries = registry.load(reg)
    assert [(e["type"], e.get("status")) for e in entries] == [
        ("reservation", None),
        ("decision", "procedure_failure"),
    ]
    f = entries[-1]
    assert f["failure"]["start_record"] == start
    assert f["failure"]["exposure_complete"] is False
    v, probs = registry.check_reservation(entries, _res(rnd=2, cand=c2, seed=778, cdir="x"))
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    _, probs = failure.authenticate_failed_round(d, f)
    assert any("not established" in p for p in probs)
    with pytest.raises(SystemExit, match="exposure"):
        _plan(
            tmp_path, tmp_path / "c2x", dev_raw, reg, out="r2x", rnd=2, seed="778", cand=c2,
            earlier=[d],
        )  # fmt: skip
    assert not (tmp_path / "r2x" / "freeze_record.json").exists()
    assert len(registry.load(reg)) == 2
    assert registry.check_terminal(entries, "revert_0.3.3") == []
    assert registry.check_terminal(entries, "amendment") == []
    assert registry.check_terminal(entries, "ship")
    return f


def test_r5_add2_truncated_start_without_journal_is_terminal_only(tmp_path):
    # a real mid-write kill of the claim: truncated start record, no journal, cache as
    # planned. Revised ruling 2 (audit r6 B1): still never an established exposure
    s = _truncated_claim(tmp_path)
    d, reg = s["d"], s["reg"]
    raw_sha = sha256_file(d / collect.EXEC_START)
    with pytest.raises(SystemExit, match="already executed"):  # the round stays consumed
        collect.main(s["ex"])
    a = _archive(tmp_path, d, s["raw"])
    assert _register(d, a, reg, tmp_path / "fail", "--dry-run") == 0
    f = _terminal_only(tmp_path, d, reg, s["dev_raw"], s["c2"])
    assert f["failure"]["execution_start_sha256"] == raw_sha
    assert f["failure"]["fetch_journal_sha256"] is None and f["failure"]["kind"] == "interrupted"
    exp = read_json(tmp_path / "fail" / "failure.json")["exposure"]
    assert exp["refs_are"] == "diagnostic lower bound" and exp["complete"] is False
    assert exp["cache_equals_plan_inventory"] is True  # a diagnostic, never a proof
    # idempotent rerun
    assert _register(d, a, reg, tmp_path / "fail", "--dry-run") == 0
    assert len(registry.load(reg)) == 2


def test_r5_add2_truncated_start_without_journal_but_a_changed_cache_is_incomplete(tmp_path):
    s = _truncated_claim(tmp_path, extra_cache=True)
    d, reg = s["d"], s["reg"]
    assert _register(d, _archive(tmp_path, d, s["raw"]), reg, tmp_path / "f", "--dry-run") == 0
    f = registry.load(reg)[-1]["failure"]
    assert f["start_record"] == "unreadable" and f["exposure_complete"] is False
    v, probs = registry.check_reservation(
        registry.load(reg), _res(rnd=2, cand=s["c2"], seed=778, cdir="x")
    )
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)


@pytest.mark.parametrize("how", ["lost_tail_empty_journal", "after_requests"])
def test_r5_add2_truncated_start_with_a_journal_is_terminal_only(tmp_path, monkeypatch, how):
    if how == "lost_tail_empty_journal":
        # the start record's tail is lost but the claim goes on: the journal is created,
        # then the execution refuses (its start record no longer matches) before any request
        dev_raw, raw = _mock_cache(tmp_path)
        reg = tmp_path / "reg.jsonl"
        reg.write_text("")
        c1, c2 = _commits()
        _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
        real = collect.write_exclusive

        def lossy(path, data, mode=0o444):
            if Path(path).name == collect.EXEC_START:
                real(path, data[: len(data) // 2], mode)
                return hashlib.sha256(data).hexdigest()  # what the writer believes it wrote
            return real(path, data, mode)

        fetched = []
        with monkeypatch.context() as m:
            m.setattr(collect, "write_exclusive", lossy)
            m.setattr(collect, "_offline_fetch", lambda *a, **k: fetched.append(a))
            with pytest.raises(SystemExit):
                collect.main(ex)
        assert fetched == []
        d = tmp_path / "r1"
        assert (d / collect.FETCH_JOURNAL).read_bytes() == b""
        s = dict(raw=raw, reg=reg, d=d, c2=c2)
    else:
        s = _aborted_round1(tmp_path, monkeypatch)
        st = s["d"] / collect.EXEC_START
        os.chmod(st, 0o644)
        st.write_bytes(st.read_bytes()[:40])
    d, reg = s["d"], s["reg"]
    assert failure.start_unreadable(d)
    raw_sha = sha256_file(d / collect.EXEC_START)
    assert _register(d, _archive(tmp_path, d, s["raw"]), reg, tmp_path / "f", "--dry-run") == 0
    entries = registry.load(reg)
    assert [(e["type"], e.get("status")) for e in entries] == [
        ("reservation", None),
        ("decision", "procedure_failure"),
    ]
    f = entries[-1]["failure"]
    assert f["start_record"] == "unreadable" and f["execution_start_sha256"] == raw_sha
    assert f["exposure_complete"] is False
    exp = read_json(tmp_path / "f" / "failure.json")["exposure"]
    assert any("start record is unreadable" in p for p in exp["problems"])
    assert registry.check_terminal(entries, "revert_0.3.3") == []
    assert registry.check_terminal(entries, "amendment") == []
    assert registry.check_terminal(entries, "ship")
    v, probs = registry.check_reservation(entries, _res(rnd=2, cand=s["c2"], seed=778, cdir="x"))
    assert v == "refuse" and any("only the terminal outcomes" in p for p in probs)
    _, probs = failure.authenticate_failed_round(d, entries[-1])
    assert any("not established" in p for p in probs)


def test_r5_add2_truncated_start_still_needs_reservation_freeze_and_archive(tmp_path):
    s = _truncated_claim(tmp_path)
    d, reg = s["d"], s["reg"]
    a = _archive(tmp_path, d, s["raw"])
    # another archive (the start record's bytes differ) is refused
    bad = _archive(tmp_path, d, s["raw"], "bad.tar")
    st = d / collect.EXEC_START
    good = st.read_bytes()
    os.chmod(st, 0o644)
    st.write_bytes(good[:-3])
    with pytest.raises(SystemExit, match="collect/execution_start.json is not the round's"):
        _register(d, bad, reg, tmp_path / "o", "--dry-run")
    st.write_bytes(good)
    # a registry without the reservation is refused
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    with pytest.raises(SystemExit, match="reservation is not in the registry"):
        _register(d, a, empty, tmp_path / "o", "--dry-run")
    # a changed freeze record (no longer a fix-check freeze record) is refused
    fr = d / "freeze_record.json"
    keep = fr.read_bytes()
    fr.write_text(json.dumps(dict(json.loads(keep), kind="something else")))
    with pytest.raises(SystemExit, match="not a fix-check freeze record"):
        _register(d, _archive(tmp_path, d, s["raw"], "c.tar"), reg, tmp_path / "o", "--dry-run")
    fr.write_bytes(keep)
    assert len(registry.load(reg)) == 1 and not (tmp_path / "o").exists()
    assert _register(d, a, reg, tmp_path / "o", "--dry-run") == 0


def test_r5_add2_production_truncated_start_revalidates_a_fresh_freeze_receipt(
    tmp_path, monkeypatch
):
    """Production, in a temporary git repository: the gate's receipt was in the unreadable
    start record, so registration makes a receipt of the freeze record's bound files and
    re-validates it; a changed origin URL still refuses."""
    from fixcheck.test_r4 import _canonical_registry, _repo

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
        receipt_ref={"ref": "refs/remotes/origin/main"},
    )
    rp = out / "freeze_record.json"
    rp.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(freeze, "receipt_paths", lambda record_path, record: [rp, reg])
    # the claim's write cut short (no journal): half of a start record
    data = canonical_json({"kind": collect.START_KIND, "round": 1, "seed": 777}).encode()
    (out / collect.EXEC_START).write_bytes(data[: len(data) // 2])
    a = _archive(tmp_path, out, raw)
    _git(repo, "remote", "set-url", "origin", "https://example.invalid/another.git")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD~1")  # freeze not on the ref
    with pytest.raises(SystemExit, match="freeze receipt"):
        _register(out, a, reg, tmp_path / "o")
    assert [e["type"] for e in registry.load(reg)] == ["reservation"]
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "remote", "set-url", "origin", "https://example.invalid/never-contacted.git")
    assert _register(out, a, reg, tmp_path / "o") == 0
    f = registry.load(reg)[-1]
    assert f["status"] == "procedure_failure" and f["failure"]["start_record"] == "unreadable"
    assert f["failure"]["exposure_complete"] is False
    rcp = read_json(tmp_path / "o" / "failure.json")["receipt"]
    assert rcp["checked"] and rcp["problems"] == [] and "made at registration" in rcp["source"]


def _lose_journal(d: Path) -> None:
    (d / collect.FETCH_JOURNAL).unlink()


def _truncate_start(d: Path, n: int = 40) -> None:
    st = d / collect.EXEC_START
    os.chmod(st, 0o644)
    st.write_bytes(st.read_bytes()[:n])


def test_r6_b1_probe_a_lost_journal_with_abort_log_is_terminal_only(tmp_path, monkeypatch):
    # the audit: abort log of 60 requests, cache equal to the plan's, start truncated to 40
    # bytes, local journal lost; registration gave an empty complete exposure
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg = s["d"], s["reg"]
    n_log = len(read_json(d / collect.EXEC_ABORT)["fetch_log"])
    assert n_log > 0
    _truncate_start(d)
    _lose_journal(d)
    assert _register(d, _archive(tmp_path, d, s["raw"]), reg, tmp_path / "f", "--dry-run") == 0
    _terminal_only(tmp_path, d, reg, s["dev_raw"], s["c2"])
    exp = read_json(tmp_path / "f" / "failure.json")["exposure"]
    assert exp["recovered_by_source"]["abort fetch log"] > 0  # known requests kept
    for e in read_json(d / collect.EXEC_ABORT)["fetch_log"]:
        if e["cache"].startswith("epmc/"):
            assert build._norm_ref(Path(e["cache"]).stem) in set(exp["refs"])


def test_r6_b1_probe_b_archive_only_journal_refuses_then_terminal_only(tmp_path, monkeypatch):
    # the audit: the archive (made before the loss) still held the journal; archive_problems
    # ignored it, registration succeeded with empty complete exposure and round 2 ran
    s = _aborted_round1(tmp_path, monkeypatch)
    d, reg = s["d"], s["reg"]
    _truncate_start(d)
    a = _archive(tmp_path, d, s["raw"])
    _lose_journal(d)
    assert failure.archive_problems(a, d, s["raw"]) != []
    with pytest.raises(SystemExit, match="which the round directory lacks"):
        _register(d, a, reg, tmp_path / "f", "--dry-run")
    assert len(registry.load(reg)) == 1
    a2 = _archive(tmp_path, d, s["raw"], "now.tar")  # the evidence as it now is
    assert _register(d, a2, reg, tmp_path / "f", "--dry-run") == 0
    _terminal_only(tmp_path, d, reg, s["dev_raw"], s["c2"])


def test_r6_b1_archive_presence_agrees_both_ways(tmp_path, monkeypatch):
    s = _aborted_round1(tmp_path, monkeypatch)
    d, raw = s["d"], s["raw"]
    assert failure.archive_problems(_archive(tmp_path, d, raw), d, raw) == []
    # a local optional record missing from the archive
    import tarfile

    a = tmp_path / "partial.tar"
    with tarfile.open(a, "w") as tf:
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name != collect.EXEC_ABORT:
                tf.add(f, arcname=f"collect/{f.name}")
        tf.add(raw, arcname="raw")
    probs = failure.archive_problems(a, d, raw)
    assert any("lacks collect/execution_abort.json" in p for p in probs)


def test_r6_b1_lost_journal_failed_requests_unchanged_cache_is_terminal_only(tmp_path):
    # failed requests leave no body: the cache stays the plan's, the journal is lost
    from fixcheck.test_r7 import _hard_exit_round1

    s = _hard_exit_round1(tmp_path)
    d, reg, raw = s["d"], s["reg"], s["raw"]
    assert (
        read_json(d / "freeze_record.json")["initial_cache_inventory"]["sha256"]
        == (freeze.cache_inventory(raw)["sha256"])
    )
    _truncate_start(d)
    _lose_journal(d)
    assert _register(d, _archive(tmp_path, d, raw), reg, tmp_path / "f", "--dry-run") == 0
    _terminal_only(tmp_path, d, reg, s["dev_raw"], s["c2"])
    exp = read_json(tmp_path / "f" / "failure.json")["exposure"]
    assert exp["cache_equals_plan_inventory"] is True and exp["complete"] is False


def test_r6_b1_completed_collection_under_unreadable_start_is_terminal_only(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    assert collect.main(ex) == 0
    d = tmp_path / "r1"
    assert (d / collect.EXEC_DONE).exists()
    _truncate_start(d)
    a = _archive(tmp_path, d, raw)
    assert _register(d, a, reg, tmp_path / "f", "--dry-run", "--reason", "replay cannot run") == 0
    f = _terminal_only(tmp_path, d, reg, dev_raw, c2)
    assert f["failure"]["kind"] == "pre_label_step"
    assert f["collection_texts_sha256"] == sha256_file(d / "texts.jsonl")
    exp = read_json(tmp_path / "f" / "failure.json")["exposure"]
    assert build.read_exclusions(d / "texts.jsonl") <= set(exp["refs"])  # diagnostics


# --- ruling after audit r7 B1: completeness needs an authenticated endpoint ---------------

KILL_AFTER_N_FAILURES = r"""
import json, os, sys
from pathlib import Path

study4, work, argv_json, origin, n = sys.argv[1:6]
sys.path.insert(0, study4)
import build
from fixcheck import collect

exec(Path(work, "origin.py").read_text())
build.urllib.request.urlopen = origin_urlopen(origin)
build.time.sleep = lambda s: None
real_fetch = build.fetch
state = {"failed": 0}


def fetch(url, cache, refresh=False):
    if state["failed"] >= int(n):
        os._exit(9)  # hard exit at the request after the n-th failure: no abort record
    try:
        return real_fetch(url, cache, refresh)
    except BaseException:
        state["failed"] += 1
        raise


build.fetch = fetch
sys.exit(collect.main(json.loads(argv_json)))
"""


def _after_terminal_checks(tmp_path, s, out="f"):
    d, reg = s["d"], s["reg"]
    assert not failure.start_unreadable(d)  # a readable start record throughout
    assert _register(d, _archive(tmp_path, d, s["raw"], f"{out}.tar"), reg, tmp_path / out,
                     "--dry-run") == 0  # fmt: skip
    f = _terminal_only(tmp_path, d, reg, s["dev_raw"], s["c2"], start="authenticated")
    with pytest.raises(SystemExit, match="already executed"):  # no re-execution
        collect.main(s["ex"])
    assert len(registry.load(reg)) == 2
    return f, read_json(tmp_path / out / "failure.json")["exposure"]


def test_r7_b1_readable_start_missing_journal_is_terminal_only(tmp_path, monkeypatch):
    from fixcheck.test_r7 import _stopped_round1

    s = _stopped_round1(tmp_path, monkeypatch)
    (s["d"] / collect.FETCH_JOURNAL).unlink()
    _, exp = _after_terminal_checks(tmp_path, s)
    assert any("journal is missing" in p for p in exp["problems"])


def test_r7_b1_readable_start_zero_byte_journal_is_terminal_only(tmp_path, monkeypatch):
    from fixcheck.test_r7 import _stopped_round1

    s = _stopped_round1(tmp_path, monkeypatch)
    (s["d"] / collect.FETCH_JOURNAL).write_bytes(b"")
    _, exp = _after_terminal_checks(tmp_path, s)
    assert any("journal SHA-256 is not the journal's" in p for p in exp["problems"])


def test_r7_b1_valid_two_pair_prefix_after_ten_failures_and_hard_exit(tmp_path):
    # the audit: 10 failed fetches, a hard exit, the journal shortened to a valid prefix of
    # two request/outcome pairs; the readable-start branch accepted it as complete
    from fixcheck.test_r7 import ORIGIN

    dev_raw, origin = _mock_cache(tmp_path)
    hidden = tmp_path / "hidden"
    shutil.move(origin / "epmc", hidden)  # every article request fails at the origin
    (origin / "epmc").mkdir()
    raw = tmp_path / "cache1"
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1, offline=False)
    work = tmp_path / "work"
    work.mkdir()
    (work / "origin.py").write_text(ORIGIN)
    (work / "driver.py").write_text(KILL_AFTER_N_FAILURES)
    r = subprocess.run(
        [sys.executable, "-I", str(work / "driver.py"), str(HERE.parent), str(work),
         json.dumps(ex), str(origin), "10"],
        capture_output=True, text=True, timeout=180,
    )  # fmt: skip
    assert r.returncode == 9, r.stdout + r.stderr
    d = tmp_path / "r1"
    assert not (d / collect.EXEC_ABORT).exists() and not (d / collect.EXEC_DONE).exists()
    j = d / collect.FETCH_JOURNAL
    lines = j.read_bytes().splitlines(keepends=True)
    events = [json.loads(x) for x in lines]
    assert sum(1 for e in events if e["event"] == "outcome" and e.get("error")) == 10
    assert (
        raw.exists()
        and freeze.cache_inventory(raw)["sha256"]
        == (read_json(d / "freeze_record.json")["initial_cache_inventory"]["sha256"])
    )  # failed requests left the cache as planned
    j.write_bytes(b"".join(lines[:4]))  # a valid two-pair prefix
    pairs, trailing, jp = collect.journal_pairs(j, allow_trailing_request=True)
    assert jp == [] and len(pairs) == 2 and trailing is None
    s = dict(d=d, reg=reg, raw=raw, dev_raw=dev_raw, c2=c2, ex=ex)
    _, exp = _after_terminal_checks(tmp_path, s)
    assert any("no abort record" in p for p in exp["problems"])


def test_r7_b1_hash_mismatched_journal_with_a_valid_abort_is_terminal_only(tmp_path, monkeypatch):
    from fixcheck.test_r7 import _stopped_round1

    s = _stopped_round1(tmp_path, monkeypatch)
    j = s["d"] / collect.FETCH_JOURNAL
    events = [json.loads(x) for x in j.read_text().splitlines()]
    # the same events, other bytes: the pairs and the fetch log still agree, the hash not
    j.write_text(
        "".join(json.dumps(e, indent=None, separators=(", ", ": ")) + "\n" for e in events)
    )
    pairs, trailing, jp = collect.journal_pairs(j, allow_trailing_request=True)
    ab = read_json(s["d"] / collect.EXEC_ABORT)
    assert jp == [] and trailing is None
    assert [collect._journal_sig(e) for e in pairs] == [
        collect._journal_sig(x) for x in ab["fetch_log"]
    ]
    _, exp = _after_terminal_checks(tmp_path, s)
    assert exp["problems"] == ["endpoint: the abort record's journal SHA-256 is not the journal's"]


def test_r7_b1_endpoint_unit_rules(tmp_path, monkeypatch):
    from fixcheck.test_r7 import _stopped_round1

    s = _stopped_round1(tmp_path, monkeypatch)
    d = s["d"]
    j = d / collect.FETCH_JOURNAL
    pairs, trailing, _ = collect.journal_pairs(j, allow_trailing_request=True)
    assert failure.endpoint_problems(d, j, pairs, trailing, False) == (collect.EXEC_ABORT, [])
    # an unmatched final request after the endpoint
    t = dict(pairs[-1], seq=len(pairs))
    _, p = failure.endpoint_problems(d, j, pairs, t, False)
    assert any("does not end at the endpoint" in x for x in p)
    # a shortened fetch log in the abort record
    ab = d / collect.EXEC_ABORT
    a = json.loads(ab.read_text())
    ab.write_text(json.dumps(dict(a, fetch_log=a["fetch_log"][:-1])))
    _, p = failure.endpoint_problems(d, j, pairs, trailing, False)
    assert any("fetch log is not the journal's" in x for x in p)
    ab.write_text(json.dumps(dict(a, fetch_journal_sha256=None)))
    _, p = failure.endpoint_problems(d, j, pairs, trailing, False)
    assert any("no authenticating journal hash" in x for x in p)
    # a completed collection without a readable completion record
    _, p = failure.endpoint_problems(d, j, pairs, trailing, True)
    assert p == ["the completion or collection record cannot be read"]


# --- audit r8 M1: the abort record hashes the journal only after a successful barrier ----


def _outcome_barrier_fails(tmp_path, monkeypatch, persistent: bool):
    """Sol's probe: the first request's barrier passes, its outcome bytes are written in
    full, then that outcome's journal barrier fails (DurabilityError), and the collector
    aborts. `persistent`: every later barrier on the journal fails too (the abort writer's
    own re-applied barrier included); otherwise the abort writer's barrier succeeds."""
    dev_raw, raw = _mock_cache(tmp_path)
    reg = tmp_path / "reg.jsonl"
    reg.write_text("")
    c1, c2 = _commits()
    _, ex = _plan(tmp_path, raw, dev_raw, reg, cand=c1)
    real = collect.durable_sync
    n = {"journal": 0}

    def sync(fd, path):
        if Path(path).name == collect.FETCH_JOURNAL:
            n["journal"] += 1  # 1: claim creation, 2: request 0, 3: outcome 0, 4+: abort
            if n["journal"] == 3 or (persistent and n["journal"] > 3):
                raise durable.DurabilityError(errno.EIO, "injected journal barrier failure")
        return real(fd, path)

    with monkeypatch.context() as m:
        m.setattr(collect, "durable_sync", sync)
        with pytest.raises(collect.JournalBarrierFailure):
            collect.main(ex)
    d = tmp_path / "r1"
    events = [json.loads(x) for x in (d / collect.FETCH_JOURNAL).read_text().splitlines()]
    assert [e["event"] for e in events] == ["request", "outcome"]  # bytes fully written
    assert n["journal"] == 4  # the abort writer re-applied the journal barrier once
    return dict(d=d, reg=reg, raw=raw, dev_raw=dev_raw, c2=c2, ex=ex)


def test_r8_m1_outcome_barrier_fails_and_stays_broken_abort_has_no_hash(tmp_path, monkeypatch):
    s = _outcome_barrier_fails(tmp_path, monkeypatch, persistent=True)
    d = s["d"]
    ab = read_json(d / collect.EXEC_ABORT)  # closure preserved: the abort record exists
    assert ab["fetch_journal_sha256"] is None
    assert ab["fetch_journal_barrier"].startswith("failed: DurabilityError")
    assert len(ab["fetch_log"]) == 1
    _, exp = _after_terminal_checks(tmp_path, s)
    assert any("no authenticating journal hash" in p for p in exp["problems"])
    assert exp["endpoint"] is None


def test_r8_m1_outcome_barrier_fails_but_abort_barrier_succeeds_is_complete(tmp_path, monkeypatch):
    s = _outcome_barrier_fails(tmp_path, monkeypatch, persistent=False)
    d, reg = s["d"], s["reg"]
    ab = read_json(d / collect.EXEC_ABORT)
    assert ab["fetch_journal_barrier"] == "passed"
    assert ab["fetch_journal_sha256"] == sha256_file(d / collect.FETCH_JOURNAL)
    assert _register(d, _archive(tmp_path, d, s["raw"]), reg, tmp_path / "f", "--dry-run") == 0
    f = registry.load(reg)[-1]
    assert f["failure"]["exposure_complete"] is True
    exp = read_json(tmp_path / "f" / "failure.json")["exposure"]
    assert exp["endpoint"] == collect.EXEC_ABORT and exp["problems"] == []
    v, _ = registry.check_reservation(registry.load(reg), _res(rnd=2, cand=s["c2"], seed=778))
    assert v == "append"  # the lawful continuation remains


def test_r8_m1_abort_writer_barrier_order(tmp_path, monkeypatch):
    j = tmp_path / collect.FETCH_JOURNAL
    j.write_text("x\n")
    calls = []
    real = collect.durable_sync
    monkeypatch.setattr(
        collect, "durable_sync", lambda fd, path: (calls.append(Path(path).name), real(fd, path))
    )
    real_sha = collect.sha256_file
    monkeypatch.setattr(
        collect, "sha256_file", lambda p: (calls.append(("sha", Path(p).name)), real_sha(p))[1]
    )
    out = collect._journal_endpoint(j)
    assert calls == [collect.FETCH_JOURNAL, ("sha", collect.FETCH_JOURNAL)]  # barrier first
    assert out == {"fetch_journal_sha256": real_sha(j), "fetch_journal_barrier": "passed"}
    assert collect._journal_endpoint(tmp_path / "none") == {
        "fetch_journal_sha256": None,
        "fetch_journal_barrier": "no journal",
    }
