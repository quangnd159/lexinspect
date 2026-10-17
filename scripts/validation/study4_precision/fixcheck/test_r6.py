"""Harness audit r3 dispositions (R3-B1, R3-S1, R3-S3): every executed probe is a regression.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck

R3-B1 two-process and hard-exit regressions run real subprocesses (a small driver
script written into the test's temporary directory) with synthetic fetch functions;
no request ever leaves the process (urllib's urlopen is replaced by a function that
raises).
"""

from __future__ import annotations

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

from fixcheck import accept, collect, freeze, package, registry  # noqa: E402
from fixcheck.common import read_json, sha256_file, write_json  # noqa: E402
from fixcheck.test_fixcheck import _collect_r1, _mock_cache  # noqa: E402
from fixcheck.test_r4 import (  # noqa: E402, F401  (pkg: a module-scoped fixture)
    _canonical_registry,
    _git,
    _repo,
    _res,
    pkg,
)

# --- R3-B1: one reserved round executes at most once -------------------------------------

DRIVER = r"""
import contextlib, json, os, sys, time
from pathlib import Path

study4, mode, work, argv_json = sys.argv[1:5]
sys.path.insert(0, study4)
import build
from fixcheck import collect

work = Path(work)
argv = json.loads(argv_json)
pid = os.getpid()
_sleep = time.sleep  # build.time is the time module: keep a real sleep for the barrier


def no_network(*a, **k):
    with (work / "urlopen_calls").open("a") as f:
        f.write(f"{pid}\n")
    raise OSError("synthetic network failure (no network in this test)")


build.urllib.request.urlopen = no_network
build.time.sleep = lambda s: None  # build.fetch's back-off


def barrier(name, n=2, timeout=3.0):
    (work / f"{name}.{pid}").write_text("")
    t = time.monotonic()
    while len(list(work.glob(f"{name}.*"))) < n and time.monotonic() - t < timeout:
        _sleep(0.005)
    return len(list(work.glob(f"{name}.*")))


if mode in ("barrier_lock", "barrier_checks"):
    real_offline = collect._offline_fetch

    def fetch(url, cache, refresh=False):
        (work / f"fetched.{pid}").touch()
        _sleep(0.001)
        return real_offline(url, cache, refresh)

    collect._offline_fetch = fetch
    if mode == "barrier_lock":  # both pass the early check, then race for the lock
        real_lock = collect.execution_lock

        @contextlib.contextmanager
        def lock(out):
            barrier("arrived")
            with real_lock(out):
                yield

        collect.execution_lock = lock
    else:  # the audit's probe: a barrier where the gate checks run
        real_checks = collect._execute_checks

        def checks(args, record_path):
            (work / f"checks_seen.{pid}").write_text(str(barrier("checks")))
            return real_checks(args, record_path)

        collect._execute_checks = checks
else:  # hard exits around a failed request (the victim body is not in the cache)
    real_fetch = build.fetch
    state = {"failed": False}

    def fetch(url, cache, refresh=False):
        if state["failed"]:
            os._exit(9)  # killed at the next request, after the failure was journalled
        try:
            return real_fetch(url, cache, refresh)
        except BaseException:
            if mode == "hardexit_in_request":
                os._exit(9)  # killed inside the failing request: no outcome, no handler
            state["failed"] = True
            raise

    build.fetch = fetch
try:
    rc = collect.main(argv)
except SystemExit as e:
    print(f"REFUSED: {e}", flush=True)
    sys.exit(3)
sys.exit(rc)
"""


def _plan(tmp_path, raw, dev_raw, offline=True, out="r1"):
    argv = [
        "--round",
        "1",
        "--seed",
        "777",
        "--out",
        str(tmp_path / out),
        "--raw-cache",
        str(raw),
        "--dev-raw",
        str(dev_raw),
        *(["--offline"] if offline else []),
        "--dry-run",
    ]
    assert collect.main([*argv, "--plan-only"]) == 0
    rec = read_json(tmp_path / out / "freeze_record.json")
    return rec, rec["execution_argv"][4:]


def _driver(tmp_path, mode, argv) -> subprocess.Popen:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    script = work / "driver.py"
    script.write_text(DRIVER)
    return subprocess.Popen(
        [sys.executable, "-I", str(script), str(HERE.parent), mode, str(work), json.dumps(argv)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


@pytest.mark.parametrize("where", ["barrier_lock", "barrier_checks"])
def test_r3_b1_two_processes_one_execution(tmp_path, where):
    dev_raw, raw = _mock_cache(tmp_path)
    _, ex = _plan(tmp_path, raw, dev_raw)
    procs = [_driver(tmp_path, where, ex) for _ in range(2)]
    outs = [(p.wait(timeout=120), p.stdout.read()) for p in procs]
    rcs = sorted(rc for rc, _ in outs)
    assert rcs == [0, 3], outs  # the audit's probe gave CONCURRENT_EXECUTIONS [0, 0]
    refused = next(o for rc, o in outs if rc == 3)
    assert "is held" in refused or "already executed" in refused
    work = tmp_path / "work"
    fetched = sorted(work.glob("fetched.*"))
    assert len(fetched) == 1  # exactly one process ever reached a fetch
    winner = int(fetched[0].suffix[1:])
    start = read_json(tmp_path / "r1" / collect.EXEC_START)
    assert start["pid"] == winner and start["argv"][4:] == ex
    if where == "barrier_checks":
        # the loser never reached the gate checks: they run under the execution lock
        seen = list(work.glob("checks_seen.*"))
        assert [int(p.suffix[1:]) for p in seen] == [winner] and seen[0].read_text() == "1"
    assert not (work / "urlopen_calls").exists()
    assert not (tmp_path / "r1" / collect.EXEC_ABORT).exists()
    assert collect.authenticate_collection(tmp_path / "r1") == []


@pytest.mark.parametrize("mode", ["hardexit_in_request", "hardexit_after_failure"])
def test_r3_b1_hard_exit_after_a_failed_request_consumes_the_round(tmp_path, monkeypatch, mode):
    from fixcheck.test_r5 import _first_fetched_epmc

    rel = _first_fetched_epmc(tmp_path)
    dev_raw, raw = _mock_cache(tmp_path)
    (raw / rel).unlink()  # uncached: the execution must request it, and the request fails
    rec, ex = _plan(tmp_path, raw, dev_raw, offline=False)
    p = _driver(tmp_path, mode, ex)
    assert p.wait(timeout=120) == 9, p.stdout.read()
    out = tmp_path / "r1"
    # no exception handler ran: no completion and no abort record ...
    assert not (out / collect.EXEC_DONE).exists() and not (out / collect.EXEC_ABORT).exists()
    # ... and the failed request left no cache file: the cache is exactly the initial one
    assert not (raw / rel).exists()
    assert freeze.cache_inventory(raw)["sha256"] == rec["initial_cache_inventory"]["sha256"]
    # the durable claim and the journal of the attempt exist
    start = read_json(out / collect.EXEC_START)
    assert start["freeze_record_sha256"] == sha256_file(out / "freeze_record.json")
    assert start["mode"] == "execute" and start["argv"][4:] == ex
    journal = [json.loads(x) for x in (out / collect.FETCH_JOURNAL).read_text().splitlines()]
    victim = [e for e in journal if e["cache"] == rel]
    assert victim and victim[0]["event"] == "request"
    if mode == "hardexit_after_failure":
        assert victim[-1]["event"] == "outcome" and victim[-1]["error_class"] == "RuntimeError"
        assert journal[-1]["event"] == "request"  # the request it was killed in
    else:
        assert journal[-1] == victim[-1] and journal[-1]["event"] == "request"
    assert len((tmp_path / "work" / "urlopen_calls").read_text().split()) == 4
    # every later invocation refuses before any request, in-process and in a new process

    def forbidden(*a, **k):
        raise AssertionError("a refused execution made a request")

    monkeypatch.setattr(build.urllib.request, "urlopen", forbidden)
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex)
    q = _driver(tmp_path, "barrier_checks", ex)
    assert q.wait(timeout=60) == 3 and "already executed" in q.stdout.read()
    assert not list((tmp_path / "work").glob("fetched.*"))
    assert freeze.cache_inventory(raw)["sha256"] == rec["initial_cache_inventory"]["sha256"]


def test_r3_b1_failure_after_collect_with_build_returns_is_final(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    _, ex = _plan(tmp_path, raw, dev_raw)
    out = tmp_path / "r1"
    seen = []
    real = collect._offline_fetch

    def fetch(url, cache, refresh=False):
        # the claim precedes the first possible fetch, and each request is journalled first
        if not seen:
            assert (out / collect.EXEC_START).exists()
            assert (out / collect.FETCH_JOURNAL).read_text().count('"event":"request"') == 1
        seen.append(url)
        return real(url, cache, refresh)

    def boom(*a, **k):
        raise RuntimeError("post-fetch mapping failure")  # the audit's injected failure

    monkeypatch.setattr(collect, "_offline_fetch", fetch)
    monkeypatch.setattr(collect, "raw_files_of", boom)
    with pytest.raises(RuntimeError, match="post-fetch mapping failure"):
        collect.main(ex)
    assert seen
    # the audit printed POST_FETCH_EXCEPTION_FINAL_MARKER False: now the claim is final
    assert (out / collect.EXEC_START).exists() and not (out / collect.EXEC_DONE).exists()
    ab = read_json(out / collect.EXEC_ABORT)
    assert ab["aborted"] == "RuntimeError: post-fetch mapping failure"
    assert ab["execution_start_sha256"] == sha256_file(out / collect.EXEC_START)
    assert len(ab["fetch_log"]) == len(seen)  # the fetch evidence is preserved
    assert collect.journal_problems(out / collect.FETCH_JOURNAL, ab["fetch_log"]) == []
    monkeypatch.setattr(collect, "raw_files_of", lambda *a, **k: [])
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex)
    assert len(seen) == len(ab["fetch_log"])  # no second request
    # a one-step dry run into an executed directory never re-executes, even with --overwrite
    with pytest.raises(SystemExit, match="already executed"):
        _collect_r1(tmp_path, raw, dev_raw, extra=("--offline", "--overwrite"))


def test_r3_b1_completed_round_cannot_run_again_and_its_claim_is_checked(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    rec, ex = _plan(tmp_path, raw, dev_raw)
    assert collect.main(ex) == 0
    d = tmp_path / "r1"
    exj = read_json(d / collect.EXEC_DONE)
    assert exj["execution_start_sha256"] == sha256_file(d / collect.EXEC_START)
    assert oct((d / collect.EXEC_START).stat().st_mode & 0o777) == "0o444"
    man = read_json(d / "manifest_collect.json")["outputs"]
    assert collect.EXEC_START in man and collect.FETCH_JOURNAL in man
    with pytest.raises(SystemExit, match="already executed"):
        collect.main(ex)
    col = read_json(d / "collection.json")
    assert collect.execution_record_problems(d, exj, rec, col) == []
    # production records require the claim; an abort record or a changed journal is caught
    prod = dict(rec, production_eligible=True)
    assert collect.execution_record_problems(d, exj, prod, col) == []
    tmp = tmp_path / "copy"
    shutil.copytree(d, tmp)
    os.chmod(tmp / collect.EXEC_START, 0o644)
    (tmp / collect.EXEC_START).unlink()
    assert any("missing" in x for x in collect.execution_record_problems(tmp, exj, prod, col))
    shutil.rmtree(tmp)
    shutil.copytree(d, tmp)
    (tmp / collect.EXEC_ABORT).write_text("{}")
    assert any("aborted" in x for x in collect.execution_record_problems(tmp, exj, rec, col))
    (tmp / collect.EXEC_ABORT).unlink()
    with (tmp / collect.FETCH_JOURNAL).open("a") as f:
        f.write(json.dumps({"event": "request", "seq": 999}) + "\n")
    probs = collect.execution_record_problems(tmp, exj, rec, col)
    # R7 (audit r4 S2): the appended line lacks the request fields, so the state-machine
    # validator reports it as malformed (it reported "out of order" before)
    assert any("malformed request" in x for x in probs) and any("does not name" in x for x in probs)


def test_r3_b1_lock_is_exclusive_across_processes(tmp_path):
    out = tmp_path / "r"
    out.mkdir()
    holder = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import fcntl, os, sys, time; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT); "
            "fcntl.flock(fd, fcntl.LOCK_EX); print('locked', flush=True); time.sleep(30)",
            str(out / collect.EXEC_LOCK),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(SystemExit, match="is held"), collect.execution_lock(out):
            pass
    finally:
        holder.kill()
        holder.wait()
    with collect.execution_lock(out):  # released by the holder's exit
        pass
    assert (out / collect.EXEC_LOCK).exists()  # never removed


# --- R3-S1: the receipt authenticates the registry as a historical prefix ----------------


def _receipted_registry(tmp_path, monkeypatch, entries):
    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    monkeypatch.setattr(freeze, "REPO", repo)
    reg = _canonical_registry(repo, entries)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reservation")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    rc = freeze.archive_receipt([reg, repo / "record.json"], repo, "refs/remotes/origin/main")
    assert rc["ok"], rc["problems"]
    return repo, reg, rc


def _decision(res, inputs="i1", status="inconclusive"):
    from fixcheck.test_r4 import _dec

    return _dec(cand=res["candidate_commit"], seed=res["seed"], inputs=inputs, status=status)


def test_r3_s1_audit_probe_legitimate_append_keeps_the_receipt_valid(tmp_path, monkeypatch):
    assert freeze.APPEND_ONLY_RECEIPTED == (registry.REGISTRY_REL,)
    res = _res(cand="c1", seed=5)
    repo, reg, rc = _receipted_registry(tmp_path, monkeypatch, [res])
    assert freeze.verify_receipt(rc, repo) == []  # RECEIPT_BEFORE_APPEND []
    registry.append_unchecked(reg, _decision(res))
    # the audit: RECEIPT_AFTER_LEGITIMATE_APPEND ['...round_registry.jsonl: changed since the
    # receipt']; now the receipted blob is a historical prefix of a valid extension
    assert freeze.verify_receipt(rc, repo) == []
    assert freeze.verify_receipt(rc) == []  # the call-time default repository
    registry.append_unchecked(reg, {"type": "terminal", "outcome": "revert_0.3.3", "basis": "x"})
    assert freeze.verify_receipt(rc, repo) == []
    # immutable inputs keep exact byte equality
    (repo / "record.json").write_text('{"edited": 1}\n')
    assert freeze.verify_receipt(rc, repo) == ["record.json: changed since the receipt"]


@pytest.mark.parametrize("damage", ["rewritten", "truncated", "non_prefix", "duplicate", "rule"])
def test_r3_s1_rewritten_truncated_or_inadmissible_registry_refuses(tmp_path, monkeypatch, damage):
    res = _res(cand="c1", seed=5)
    repo, reg, rc = _receipted_registry(tmp_path, monkeypatch, [res])
    line = reg.read_text()
    if damage == "rewritten":
        reg.write_text(line.replace('"seed":5', '"seed":6'))
    elif damage == "truncated":
        reg.write_text("")
    elif damage == "non_prefix":
        reg.write_text(json.dumps({"type": "terminal"}, separators=(",", ":")) + "\n" + line)
    elif damage == "duplicate":
        registry.append_unchecked(reg, res)  # an identical reservation line, appended again
    else:  # a canonical, committed-prefix append the rules refuse: a parallel round-1 package
        registry.append_unchecked(reg, _res(cand="c1", seed=9, cdir="r1b"))
    probs = freeze.verify_receipt(rc, repo)
    assert probs and all(p.startswith(registry.REGISTRY_REL) for p in probs), probs


def _production_package(pkg, tmp_path, monkeypatch):  # noqa: F811
    """A copy of the dry-run package whose collect part is a receipted production record in a
    temporary git repository (the remaining, constant problems are the dry package's)."""
    res = _res(cand="c1", seed=5)
    repo, reg, rc = _receipted_registry(tmp_path, monkeypatch, [res])
    P = tmp_path / "pkg"
    shutil.copytree(pkg, P)
    c = P / "collect"
    fr = read_json(c / "freeze_record.json")
    fr.update(
        dry_run=False,
        production_eligible=True,
        ineligible_reasons=[],
        candidate={"commit": "c1", "tree_sha256": None},
        registry={"path": str(reg), "reservation_sha256": registry.entry_sha256(res)},
        ledger={"markdown": {"path": str(repo / "LEDGER.md")}, "components": {"path": None}},
        protocol={"path": str(repo / "record.json")},
        clarifications={"path": str(repo / "record.json")},
    )
    fr["bound"] = dict(fr["bound"], registry=freeze.file_identity(reg, repo))
    write_json(c / "freeze_record.json", fr)
    col = read_json(c / "collection.json")
    col["freeze_record_sha256"] = sha256_file(c / "freeze_record.json")
    write_json(c / "collection.json", col)
    write_json(
        c / "execution.json",
        {
            "freeze_record_sha256": col["freeze_record_sha256"],
            "collection_json_sha256": sha256_file(c / "collection.json"),
            "gate": {"production": True, "ok": True, "receipt": rc},
        },
    )
    return repo, reg, res, P


def _registry_problems(chk):
    return [p for p in chk["problems"] if registry.REGISTRY_REL in p]


def test_r3_s1_registered_decision_recheck_reaccept_and_recovery(pkg, tmp_path, monkeypatch):  # noqa: F811
    repo, reg, res, P = _production_package(pkg, tmp_path, monkeypatch)
    chk0 = package.check_package(P)  # the real package check, unmocked
    assert chk0["collection"]["production"] is True and _registry_problems(chk0) == []
    assert any("execution receipt" in p for p in chk0["problems"])  # its constant problems
    # a decision registered, then the process dies before writing acceptance.json
    real_append = registry.atomic_append

    def crash_after_fsync(*a, **k):
        real_append(*a, **k)
        raise RuntimeError("crash after the registry fsync")

    monkeypatch.setattr(registry, "atomic_append", crash_after_fsync)
    out1 = tmp_path / "acc1"
    with pytest.raises(RuntimeError, match="crash after the registry fsync"):
        accept.main(["--package", str(P), "--registry", str(reg), "--out", str(out1)])
    monkeypatch.setattr(registry, "atomic_append", real_append)
    lines = registry.load(reg)
    assert [e["type"] for e in lines] == ["reservation", "decision"]
    assert not (out1 / "acceptance.json").exists()
    # the same package, nothing changed: the check is identical (no self-invalidating receipt)
    chk1 = package.check_package(P)
    assert chk1["problems"] == chk0["problems"] and chk1["inputs_sha256"] == chk0["inputs_sha256"]
    # recovery into the same directory, and reacceptance elsewhere: idempotent, same status
    for out in (out1, tmp_path / "acc2"):
        assert accept.main(["--package", str(P), "--registry", str(reg), "--out", str(out)]) == 0
        assert read_json(out / "registration.json")["verdict"] == "idempotent"
        assert read_json(out / "acceptance.json")["status"] == lines[1]["status"]
    assert len(registry.load(reg)) == 2
    assert package.check_package(P)["problems"] == chk0["problems"]


@pytest.mark.parametrize("damage", ["rewritten", "truncated", "non_prefix"])
def test_r3_s1_package_check_refuses_a_damaged_registry(pkg, tmp_path, monkeypatch, damage):  # noqa: F811
    repo, reg, res, P = _production_package(pkg, tmp_path, monkeypatch)
    registry.append_unchecked(reg, _decision(res))
    text = reg.read_text()
    if damage == "rewritten":
        reg.write_text(text.replace('"seed":5', '"seed":6', 1))
    elif damage == "truncated":
        reg.write_text("")
    else:
        reg.write_text(text.splitlines()[1] + "\n" + text.splitlines()[0] + "\n")
    chk = package.check_package(P)
    assert any("execution receipt" in p for p in _registry_problems(chk)), chk["problems"]
    with pytest.raises(SystemExit, match="registry refused"):
        accept.main(["--package", str(P), "--registry", str(reg), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()


# --- R3-S3: the runtime doing acceptance is the frozen runtime ----------------------------


def test_r3_s3_runtime_identity_covers_numerical_parser_model_and_installed_source():
    env = freeze.environment_identity(freeze.REPO)
    for k in ("python", "python_build", "machine", "uv_lock_sha256", "numerical"):
        assert k in env
    assert set(env["artifacts"]) == {"numpy", "scipy", "spacy", "en_core_web_sm", "thinc"} | {
        "lexinspect"
    }
    assert env["artifacts"]["numpy"]["n_files"] > 0  # numpy's installed files are hashed
    src = env["lexinspect_source"]
    from fixcheck.run import pkg_digest

    assert src["tree_sha256"] == pkg_digest(freeze.lexinspect_source_root())["tree_sha256"]


def test_r3_s3_source_identity_is_content_not_path(tmp_path, monkeypatch):
    # found by the r6 dry run: a byte-identical candidate snapshot earlier on sys.path must
    # not change the identity (the path is observation detail, not identity)
    here = freeze.environment_identity(freeze.REPO)
    copy = tmp_path / "snapshot" / "lexinspect"
    shutil.copytree(
        freeze.lexinspect_source_root(), copy, ignore=shutil.ignore_patterns("__pycache__")
    )
    monkeypatch.setattr(freeze, "lexinspect_source_root", lambda: copy)
    assert freeze.environment_identity(freeze.REPO) == here
    assert freeze.acceptance_runtime()["lexinspect_source_root"] == str(copy)
    (copy / "__init__.py").write_text((copy / "__init__.py").read_text() + "# changed\n")
    assert (
        freeze.environment_identity(freeze.REPO)["lexinspect_source"] != here["lexinspect_source"]
    )


def _changed(what):
    real = freeze.environment_identity

    def fake(checkout=freeze.REPO):
        env = real(checkout)
        if what == "python_build":
            env["python_build"] = env["python_build"] + " (another build)"
        elif what == "numpy":
            env["artifacts"] = dict(
                env["artifacts"], numpy=dict(env["artifacts"]["numpy"], files_sha256="0" * 64)
            )
        else:
            env["lexinspect_source"] = dict(env["lexinspect_source"], tree_sha256="1" * 64)
        return env

    return fake


@pytest.mark.parametrize("what", ["python_build", "numpy", "lexinspect_source"])
def test_r3_s3_changed_acceptance_runtime_refuses_production(pkg, tmp_path, monkeypatch, what):  # noqa: F811
    from fixcheck import common

    repo, reg, res, P = _production_package(pkg, tmp_path, monkeypatch)
    before = {part: package.part_files(package.resolve(P), part) for part in package.PARTS}
    clean = package.check_package(P)
    assert clean["links"]["runtime"]["ok"]
    common.environment_sha256()  # a populated process cache must not stand in for the check
    # the audit's first probe: a historical manifest agreeing with its freeze still agrees
    # (manifests are historical); the new check is on the process doing acceptance
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "x.json").write_text("{}\n")
    common.write_step_manifest(hist, "probe", [hist / "x.json"])
    frozen = {
        "sources_sha256": common.source_hashes(),
        "environment": freeze.environment_identity(),
    }
    monkeypatch.setattr(freeze, "environment_identity", _changed(what))
    assert package.check_manifest(hist, "probe", ["x.json"], frozen) == []
    chk = package.check_package(P)
    probs = chk["links"]["runtime"]["problems"]
    assert len(probs) == 1 and what.split("_")[0] in probs[0]
    assert chk["inputs_sha256"] != clean["inputs_sha256"]  # the observed identity is bound
    assert set(chk["problems"]) - set(clean["problems"]) == {f"[runtime] {probs[0]}"}
    with pytest.raises(SystemExit, match="refused before any decision"):
        accept.main(["--package", str(P), "--registry", str(reg), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()
    assert [e["type"] for e in registry.load(reg)] == ["reservation"]  # nothing registered
    after = {part: package.part_files(package.resolve(P), part) for part in package.PARTS}
    assert after == before  # every historical file untouched


def test_r3_s3_dry_package_reports_the_runtime_and_previews_it(pkg, tmp_path, monkeypatch):  # noqa: F811
    chk = package.check_package(pkg)
    assert chk["links"]["runtime"]["ok"]
    rt = chk["acceptance_runtime"]
    assert rt["environment"] == freeze.environment_identity(freeze.REPO)
    assert chk["chain_summary"]["acceptance_runtime_sha256"] == rt["environment_sha256"]
    monkeypatch.setattr(freeze, "environment_identity", _changed("numpy"))
    assert not package.check_package(pkg)["links"]["runtime"]["ok"]


def test_r3_s3_acceptance_imports_no_distribution_outside_the_identity(pkg):  # noqa: F811
    code = (
        "import json, sys; sys.path.insert(0, sys.argv[1]);"
        "from fixcheck import accept, cli, freeze, package;"
        "chk = package.check_package(sys.argv[2]);"
        "print(json.dumps([freeze.imported_distributions(), "
        "chk['acceptance_runtime']['imported_outside_identity']]))"
    )
    r = subprocess.run(
        [sys.executable, "-I", "-c", code, str(HERE.parent), str(pkg)],
        capture_output=True,
        text=True,
        check=True,
    )
    imported, outside = json.loads(r.stdout.strip().splitlines()[-1])
    assert "numpy" in imported  # the frozen estimators.py's numerical dependency
    assert outside == [] and set(imported) <= set(freeze.ARTIFACT_DISTS), imported


# --- R3-S2: the runbook keeps restricted material private --------------------------------

RUNBOOK = freeze.FREEZE_DIR / "RUNBOOK.md"
INVENTORY = freeze.REPO / ".cache" / "validation" / "study4" / "phrase_sense_inventory.md"


def _fragments() -> set[str]:
    """The runbook's own split (section 0.3): table bars, semicolons, quotes, asterisks;
    trimmed fragments of at least 20 characters. Never printed."""
    import re

    text = INVENTORY.read_text(encoding="utf-8")
    return {f.strip() for f in re.split(r'[|;"*\n]', text) if len(f.strip()) >= 20}


@pytest.mark.skipif(not INVENTORY.exists(), reason="private inventory not present")
def test_r3_s2_public_documents_carry_no_inventory_fragment():
    # the audit's executed content check: count literal matches without printing them
    frags = _fragments()
    assert len(frags) > 100
    public = [
        *sorted(freeze.FREEZE_DIR.glob("*")),
        freeze.CLARIFICATIONS,
    ]
    counts = {p.name: sum(f in p.read_text(encoding="utf-8") for f in frags) for p in public}
    assert counts and all(v == 0 for v in counts.values()), counts
    # the guidelines still hold the one known match: why they stay private (Addendum 4)
    guidelines = freeze.REPO / "docs" / "validation" / "study4-guidelines.md"
    if guidelines.exists():
        text = guidelines.read_text(encoding="utf-8")
        assert sum(f in text for f in frags) == 1


def test_r3_s2_runbook_allowlist_staging_archive_and_scan():
    text = RUNBOOK.read_text(encoding="utf-8")
    allow = text[text.index("**Public (committed and pushed).**") : text.index("**Private")]
    assert "study4-guidelines.md`\n" not in allow  # not a listed public file
    assert "are not on this list" in allow
    assert "Whether that line may be published" not in text and "step 3.5 stops" not in text
    assert (
        "Addendum 4" in text
        and "276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e" in text
    )
    spec = read_json(freeze.FREEZE_DIR / "delivery_spec.json")["materials"]
    for name, m in spec.items():
        assert f"{m['sha256']}  {name}" in text  # 0.4: private copies checked against the spec
    for tar in ("round1-prelabel.tar", "round1-labelled.tar", "round1-aborted.tar"):
        line = next(x for x in text.splitlines() if f"<ARCHIVE>/{tar}" in x and "tar -cf" in x)
        assert " materials" in line, tar
    # the staged blob is scanned, not only the worktree (since R5-M3 by the Python scanner,
    # scan.scan_staged: `git cat-file blob :<path>` plus the working-tree file)
    assert "scan-restricted staged" in text and "staged blob" in text
    freeze_step = text[text.index("5. **Check, commit and push.**") :]
    assert "never the guidelines" in freeze_step[:600]
    one_shot = text[text.index("## 5. Execute") : text.index("## 6.")]
    for word in ("no resume", "Never re-run", "execution_start.json", "fetch_journal.jsonl"):
        assert word in one_shot
