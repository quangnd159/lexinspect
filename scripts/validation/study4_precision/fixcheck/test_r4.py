"""Harness audit r1 dispositions (B1-B6, S1-S5, M1-M2): every failing probe is a test.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import analyse  # noqa: E402
import build  # noqa: E402

from fixcheck import (  # noqa: E402
    accept,
    assign,
    collect,
    crosswalk,
    dryrun,
    freeze,
    ledger,
    package,
    registry,
    sampling,
    sessions,
    synthetic,
    worker,
)
from fixcheck import crosswalk as X  # noqa: E402
from fixcheck.common import (  # noqa: E402
    read_json,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)
from fixcheck.test_fixcheck import _mock_cache, _round, _write_frames, cw, mk  # noqa: E402

# --- B1: the plan binds the collection ------------------------------------------------


def _plan(tmp_path, raw, dev_raw, out="r1", seed="777", extra=()):
    argv = [
        "--round",
        "1",
        "--seed",
        seed,
        "--out",
        str(tmp_path / out),
        "--raw-cache",
        str(raw),
        "--dev-raw",
        str(dev_raw),
        "--offline",
        "--dry-run",
        *extra,
    ]
    assert collect.main([*argv, "--plan-only"]) == 0
    rec = read_json(tmp_path / out / "freeze_record.json")
    return rec, rec["execution_argv"][4:]  # [python, -I, cli.py, collect, *argv]


@pytest.fixture
def no_collector(monkeypatch):
    def reached(*a, **k):
        raise AssertionError("the collector was reached")

    monkeypatch.setattr(collect, "_collect_round", reached)


def test_plan_writes_the_literal_execution_argv_and_never_overwrites(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    rec, ex = _plan(tmp_path, raw, dev_raw)
    assert "--plan-only" not in rec["execution_argv"]
    assert ex[-3:] == ["--execute", "--freeze-record", str(tmp_path / "r1" / "freeze_record.json")]
    assert rec["seed"] == 777 and rec["production_eligible"] is False
    for k in (
        "pool_inventory",
        "initial_cache_inventory",
        "cache_policy",
        "dev_manifest",
        "candidate",
        "environment",
        "ledger",
        "protocol",
        "clarifications",
        "sources_sha256",
    ):
        assert k in rec
    with pytest.raises(SystemExit, match="never overwritten"):
        collect.main(
            [
                "--round",
                "1",
                "--seed",
                "777",
                "--out",
                str(tmp_path / "r1"),
                "--raw-cache",
                str(raw),
                "--dev-raw",
                str(dev_raw),
                "--offline",
                "--plan-only",
            ]
        )
    # the planned execution then runs, with execution metadata in execution.json
    assert collect.main(ex) == 0
    exj = read_json(tmp_path / "r1" / "execution.json")
    assert exj["freeze_record_sha256"] == sha256_file(tmp_path / "r1" / "freeze_record.json")
    assert (tmp_path / "r1" / "command.txt").read_text().count("--execute") == 1


def test_production_plan_and_execution_refuse_ineligible_inputs(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    base = [
        "--round",
        "1",
        "--seed",
        "777",
        "--raw-cache",
        str(raw),
        "--dev-raw",
        str(dev_raw),
        "--offline",
    ]
    # a production plan needs a fresh download cache (G5; round-2 harness audit r1 finding 4):
    # the pre-populated offline mock cache is refused before anything else is written
    with pytest.raises(SystemExit, match="is not fresh"):
        collect.main([*base, "--out", str(tmp_path / "p0"), "--plan-only"])
    assert not (tmp_path / "p0").exists()
    fresh = [*base]
    fresh[fresh.index("--raw-cache") + 1] = str(tmp_path / "rawfresh")
    # no candidate commit, DRAFT ledger, no components: not a production freeze
    with pytest.raises(SystemExit, match="not a production freeze"):
        collect.main([*fresh, "--out", str(tmp_path / "p"), "--plan-only"])
    with pytest.raises(SystemExit, match="two invocations"):
        collect.main([*fresh, "--out", str(tmp_path / "q")])
    rec, ex = _plan(tmp_path, raw, dev_raw, out="d")
    with pytest.raises(SystemExit, match="only --dry-run may execute it"):
        collect.main([a for a in ex if a != "--dry-run"])


BOUND_INPUTS = [
    "seed_in_argv",
    "different_raw_cache",
    "pool_listing",
    "raw_cache_contents",
    "ledger_markdown",
    "protocol",
    "environment",
    "harness_sources",
    "candidate_digest",
    "edited_freeze_record",
    "working_directory",
]


@pytest.mark.parametrize("what", BOUND_INPUTS)
def test_execution_refuses_each_changed_bound_input_before_any_fetch(
    tmp_path, monkeypatch, no_collector, what
):
    dev_raw, raw = _mock_cache(tmp_path)
    led = tmp_path / "LEDGER.md"
    led.write_text("**Status:** DRAFT\n")
    proto = tmp_path / "protocol.md"
    proto.write_text("protocol\n")
    monkeypatch.setattr(freeze, "PROTOCOL", proto)
    extra = ["--ledger-md", str(led)]
    if what == "candidate_digest":
        extra += ["--candidate-commit", "HEAD"]
    rec, ex = _plan(tmp_path, raw, dev_raw, extra=extra)
    if what == "seed_in_argv":
        ex[ex.index("--seed") + 1] = "778"
    elif what == "different_raw_cache":  # the audit probe: /AUDIT_DIFFERENT_RAW
        other = tmp_path / "AUDIT_DIFFERENT_RAW"
        shutil.copytree(raw, other)
        ex[ex.index("--raw-cache") + 1] = str(other)
    elif what == "pool_listing":
        pool = next(iter(sorted((dev_raw / "pools").glob("*.json"))))
        pool.write_text(pool.read_text() + " ")
    elif what == "raw_cache_contents":
        (raw / "epmc" / "PMC_EXTRA.xml").write_text("x")
    elif what == "ledger_markdown":
        led.write_text("**Status:** DRAFT\nedited\n")
    elif what == "protocol":
        proto.write_text("protocol, edited\n")
    elif what == "environment":
        env = freeze.environment_identity

        monkeypatch.setattr(
            freeze, "environment_identity", lambda c: dict(env(c), uv_lock_sha256="0" * 64)
        )
    elif what == "harness_sources":
        monkeypatch.setattr(collect, "source_hashes", lambda: {"fixcheck/x.py": "0" * 64})
    elif what == "candidate_digest":
        d = freeze.commit_src_digest

        monkeypatch.setattr(freeze, "commit_src_digest", lambda c: dict(d(c), tree_sha256="0" * 64))
    elif what == "edited_freeze_record":
        p = tmp_path / "r1" / "freeze_record.json"
        r = read_json(p)
        r["targets"] = dict(r["targets"], general=1)
        write_json(p, r)
    elif what == "working_directory":
        monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="does not match the freeze record|differs"):
        collect.main(ex)


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src" / "lexinspect").mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    (repo / "src" / "lexinspect" / "__init__.py").write_text("x = 1\n")
    (repo / "record.json").write_text("{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    # a configured origin (never contacted: every receipt check is local)
    _git(repo, "remote", "add", "origin", "https://example.invalid/never-contacted.git")
    return repo


def test_archive_receipt_is_local_git_only(tmp_path):
    repo = _repo(tmp_path)
    paths = [repo / "record.json"]
    ref = "refs/remotes/origin/main"  # audit r2 B1: only a full remote-tracking ref
    ok = freeze.archive_receipt(paths, repo, ref)
    assert ok["ok"] and ok["remote_commit"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert "no network" in ok["method"] and ok["remote_ref"] == ref
    # an uncommitted edit, an untracked file, a missing remote ref, an unpushed commit
    (repo / "record.json").write_text('{"edited": 1}\n')
    assert any(
        "differs from its committed" in p
        for p in freeze.archive_receipt(paths, repo, ref)["problems"]
    )
    (repo / "new.json").write_text("{}\n")
    r = freeze.archive_receipt([repo / "new.json"], repo, ref)
    assert any("not committed at HEAD" in p for p in r["problems"])
    assert not freeze.archive_receipt(paths, repo, "refs/remotes/origin/nope")["ok"]
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")
    r = freeze.archive_receipt([repo / "new.json"], repo, ref)
    assert any("push it" in p for p in r["problems"])
    _git(repo, "update-ref", ref, "HEAD")
    assert freeze.archive_receipt([repo / "new.json"], repo, ref)["ok"]
    assert not freeze.archive_receipt([tmp_path / "outside.json"], repo, ref)["ok"]


def _canonical_registry(repo, entries=()):
    from fixcheck import registry as REG

    path = repo / REG.REGISTRY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    for e in entries:
        REG.append_unchecked(path, e)
    return path


def test_execution_gate_needs_clean_tree_candidate_source_and_receipt(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    res = {"type": "reservation", "round": 1, "candidate_commit": "c", "seed": 1}
    reg = _canonical_registry(repo, [res])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reserve")
    ref = "refs/remotes/origin/main"
    _git(repo, "update-ref", ref, "HEAD")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    d = freeze.commit_src_digest(head, repo)
    rec = {
        "candidate": {"commit": head, "tree_sha256": d["tree_sha256"]},
        "registry": {"path": str(reg), "reservation_sha256": registry.entry_sha256(res)},
        "receipt_ref": {"ref": ref},
        "round": 1,
    }
    # the prerequisites are tested on their own below; here the gate's own checks
    monkeypatch.setattr(freeze, "production_prerequisites", lambda r: [])
    monkeypatch.setattr(freeze, "receipt_paths", lambda p, r: [repo / "record.json", reg])
    g = freeze.execution_gate(repo / "record.json", rec, repo, ref)
    assert g["ok"], g["problems"]
    assert any(
        "not the freeze record's receipt ref" in p
        for p in freeze.execution_gate(
            repo / "record.json", rec, repo, "refs/remotes/origin/other"
        )["problems"]
    )
    (repo / "src" / "lexinspect" / "__init__.py").write_text("x = 2\n")  # dirty and different
    g = freeze.execution_gate(repo / "record.json", rec, repo, ref)
    assert any("not clean" in p for p in g["problems"])
    assert any("differs from the candidate commit" in p for p in g["problems"])
    _git(repo, "checkout", "-q", "--", ".")
    # no reservation, or no registry at all: refused (no KeyError)
    bad = dict(rec, registry={"path": str(reg), "reservation_sha256": "0" * 64})
    assert any(
        "reservation is not in the registry" in p
        for p in freeze.execution_gate(repo / "record.json", bad, repo, ref)["problems"]
    )
    bad = {k: v for k, v in rec.items() if k != "registry"}
    assert any(
        "names no round registry" in p
        for p in freeze.execution_gate(repo / "record.json", bad, repo, ref)["problems"]
    )


def test_production_prerequisites_name_every_missing_bound_input():
    rec = {
        "candidate": {"commit": None},
        "ledger": {
            "markdown": {"path": "x", "sha256": "x", "draft": True},
            "components": {"path": None},
        },
        "protocol": {"sha256": "p"},
        "clarifications": {"sha256": "c"},
        "environment": {"uv_lock_sha256": "u"},
        "round": 1,
        "receipt_ref": {"ref": "HEAD"},
    }
    why = " | ".join(freeze.production_prerequisites(rec))
    for want in (
        "no candidate commit",
        "DRAFT",
        "no ledger_components.json",
        "no preregistration",
        "no delivery spec",
        "no registry",
        "dispositions and rulings",
        "not reserved in the canonical registry",
        "is not the registered refs/remotes/origin/study4-fix040-candidate",
    ):
        assert want in why, want


def test_commit_src_digest_matches_the_working_tree_digest(tmp_path):
    from fixcheck.run import pkg_digest

    repo = _repo(tmp_path)
    d = freeze.commit_src_digest("HEAD", repo)
    assert d["tree_sha256"] == pkg_digest(repo / "src" / "lexinspect")["tree_sha256"]


# --- B6: redirects and revisions keep their exact archived response ---------------------


def _pages(tmp_path, monkeypatch, calls):
    raw = tmp_path / "raw"
    (raw / "wiki").mkdir(parents=True)
    monkeypatch.setattr(build, "RAW", raw)
    rec = collect.FetchRecorder(raw)
    answers = {}
    for req, (pid, rev, title) in calls:
        f = raw / "wiki" / f"{build._key(req)}.json"
        f.write_text(json.dumps({"req": req, "pageid": pid, "revid": rev}))
        answers[req] = {"pageid": pid, "title": title, "revisions": [{"revid": rev}]}
    wp = rec.wrap_wiki_page(lambda t, refresh: answers[t])
    for req, _ in calls:
        wp(req, False)
    return raw, rec


def _wtext(pid, rev):
    return {
        "text_id": f"W{pid}-{rev}",
        "source": "Wikipedia",
        "source_id": f"wiki:{pid}",
        "revid": rev,
    }


def test_raw_files_follow_requested_title_redirects_and_revisions(tmp_path, monkeypatch):
    calls = [
        ("topic 0", (1, 10, "Topic 0")),  # normalised title
        ("Old name", (2, 20, "Topic 1")),  # redirect
        ("Topic 2", (3, 30, "Topic 2")),  # two titles, one page
        ("Topic two", (3, 30, "Topic 2")),
        ("Topic 3", (4, 40, "Topic 3")),  # two cached revisions of one page
        ("Topic 3 (alt)", (4, 41, "Topic 3")),
    ]
    raw, rec = _pages(tmp_path, monkeypatch, calls)
    texts = [_wtext(1, 10), _wtext(2, 20), _wtext(3, 30), _wtext(4, 40), _wtext(4, 41)]
    out = {r["text_id"]: r for r in collect.raw_files_of(texts, raw, rec)}
    assert out["W1-10"]["file"] == f"wiki/{build._key('topic 0')}.json"
    assert out["W1-10"]["canonical_title"] == "Topic 0"
    assert out["W2-20"]["file"] == f"wiki/{build._key('Old name')}.json"
    assert out["W2-20"]["requested_title"] == "Old name"
    assert out["W3-30"]["file"] == f"wiki/{build._key('Topic 2')}.json"
    assert out["W3-30"]["other_titles_same_page"] == ["Topic two"]
    assert out["W4-40"]["file"] == f"wiki/{build._key('Topic 3')}.json"
    assert out["W4-41"]["file"] == f"wiki/{build._key('Topic 3 (alt)')}.json"
    for r in out.values():  # the exact response file is hashed
        assert r["sha256"] == sha256_file(raw / r["file"])
    with pytest.raises(SystemExit, match="no logged wiki_page call"):
        collect.raw_files_of([_wtext(4, 42)], raw, rec)
    (raw / out["W1-10"]["file"]).unlink()
    with pytest.raises(SystemExit, match="missing"):
        collect.raw_files_of([_wtext(1, 10)], raw, rec)


def test_raw_file_changed_during_collection_is_refused(tmp_path, monkeypatch):
    raw, rec = _pages(tmp_path, monkeypatch, [("T", (5, 50, "T"))])
    f = raw / "wiki" / f"{build._key('T')}.json"
    rec.fetches.append({"seq": 0, "cache": f"wiki/{build._key('T')}.json", "sha256": "0" * 64})
    with pytest.raises(SystemExit, match="changed during the collection"):
        collect.raw_files_of([_wtext(5, 50)], raw, rec)
    assert f.exists()


# --- S5: replay authenticates the raw responses first ---------------------------------


def test_replay_refuses_tampered_raw_and_separates_metadata(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    _, ex = _plan(tmp_path, raw, dev_raw)
    assert collect.main(ex) == 0
    r1 = tmp_path / "r1"
    col = read_json(r1 / "collection.json")
    assert col["raw_files"] and col["fetch_log"] and col["selection_log"]
    assert collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep")]) == 0
    rep = read_json(tmp_path / "rep" / "replay.json")
    assert rep["raw_responses_authenticated"] and rep["text_reproducible"] and rep["logs_identical"]
    assert "metadata_differences" in rep
    victim = raw / col["raw_files"][0]["file"]
    victim.write_bytes(victim.read_bytes() + b" ")
    assert collect.authenticate_raw(col, raw)
    with pytest.raises(SystemExit, match="do not authenticate"):
        collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep2")])


# --- B4: two layers; span-resolution rule; siblings ------------------------------------


def _h(r, head, raw_marker):
    return dict(r, head_span=list(head), raw={"marker": raw_marker})


def test_b4_probe_1_i_believe_is_unresolved_and_cannot_pass():
    b = [_h(mk("a", (0, 9), "hedges", marker="I believe"), (2, 9), "I believe")]
    c = [_h(mk("x", (0, 1), "self_mentions", marker="I", config="C"), (0, 1), "I")]
    bl, _ = cw(b, c)
    assert bl["B:a"]["change_type"] == X.SPAN_CHANGED and bl["B:a"]["resolved"] is False
    # both payloads STRICT-correct: the old rule gave (0, 0); an unresolved link gives (0, 1)
    assert accept.loss_bounds(1, [(1, True)]) == (0, 0)
    assert accept.loss_bounds(1, [(1, False)]) == (0, 1)
    # ten such rows (census) against 100 baseline successes: possible loss 10/100 > .05
    frames, bs, refs, configs = _round(
        {X.SPAN_CHANGED: (10, {f"a{i}": (1, [(1, False)]) for i in range(10)})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    g = res["modules"]["metadiscourse"]["cumulative"]["STRICT"]
    assert g["passes"] is False and g["definite_losses_sampled"] == 0  # fails safely, no breach
    assert res["status"] == "inconclusive"
    old = _round(
        {X.SPAN_CHANGED: (10, {f"a{i}": (1, [(1, True)]) for i in range(10)})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    assert accept.compute(*old)["status"] == "pass"  # what the old nesting rule would report


def test_b4_probe_2_same_span_sibling_crosswalk():
    # baseline hedges + boosters at one span; the candidate keeps the hedges claim only
    b = [mk("h", (0, 5), "hedges"), mk("b", (0, 5), "boosters")]
    c = [mk("h", (0, 5), "hedges", config="C")]
    bl, _ = cw(b, c)
    assert bl["B:h"]["change_type"] == X.UNCHANGED
    # audit r2 B4 (ruling A2 withdrawn): a claim dropped at a retained span is not a
    # genuine deletion; it is its own affected cell, outside the removal gate
    assert bl["B:b"]["change_type"] == X.CLAIM_DROPPED
    assert bl["B:b"]["counterparts"] == [] and bl["B:b"]["siblings"] == ["C:h"]
    fr = crosswalk.frames_for(b, c, bl, {"C:h": {"change_type": X.C_UNCHANGED}})["metadiscourse"]
    assert fr["rows_with_same_span_sibling"][X.CLAIM_DROPPED] == 1
    assert fr["N_genuine_deletion"] == 0 and fr["N_claim_dropped_at_retained_span"] == 1


def _sibling_round(n_sib: int, with_siblings: bool):
    """n_sib dropped boosters (STRICT 0, LENIENT 1) whose hedge sibling is CORRECT, and
    100 - n_sib genuine deletions, definitely unsuccessful (REMOVED census); baseline
    success census of 150. With siblings (crosswalk/3) the dropped claims are the
    CLAIM_DROPPED cell; without, they are REMOVED rows (the pre-r4 crosswalk)."""
    drop = {f"s{i}": (1, [(1, True)]) for i in range(n_sib)}
    gone = {f"z{i}": (0, []) for i in range(100 - n_sib)}
    cells = (
        {X.REMOVED: (100 - n_sib, gone), X.CLAIM_DROPPED: (n_sib, drop)}
        if with_siblings
        else {X.REMOVED: (100, drop | gone)}
    )
    frames, bs, refs, configs = _round(
        cells,
        bs_md={"s1": (150, [1] * 150)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    fid = f"COMPLETE|metadiscourse|affected|{X.CLAIM_DROPPED if with_siblings else X.REMOVED}"
    for i in range(n_sib):
        row = f"s{i}"
        p = frames[fid]["rows"][row]
        refs[("metadiscourse", "STRICT")][p] = 0  # WRONG_CATEGORY -> hedges
        refs[("metadiscourse", "LENIENT")][p] = 1
        q = frames[fid]["counterparts"][row][0][0]
        frames[fid]["counterparts"][row] = [(q, True, "sibling")] if with_siblings else []
    return frames, bs, refs, configs


def test_b4_probe_2_sibling_retains_lenient_and_removes_a_spurious_certificate():
    old = accept.compute(*_sibling_round(10, with_siblings=False))
    om = old["modules"]["metadiscourse"]
    assert om["cumulative"]["LENIENT"]["definite_losses_sampled"] == 10
    assert om["cumulative"]["LENIENT"]["breach_certificate"]  # 10/150 > .05: spurious fail
    assert old["status"] == "fail"
    new = accept.compute(*_sibling_round(10, with_siblings=True))
    nm = new["modules"]["metadiscourse"]
    assert nm["cumulative"]["LENIENT"]["definite_losses_sampled"] == 0
    assert not nm["cumulative"]["LENIENT"]["breach_certificate"]
    assert nm["loss"]["LENIENT"]["U_loss"] == 0.0
    # STRICT needs the corresponding claim: siblings never retain under STRICT
    assert nm["cumulative"]["STRICT"]["definite_losses_sampled"] == 0  # STRICT 0 baseline
    # the removal gate counts genuine deletions only (audit r2 B4): the 90 REMOVED rows
    assert nm["removal"]["COMPLETE"]["N"] == 90 and nm["removal"]["COMPLETE"]["k_lo"] == 0
    assert nm["removal"]["COMPLETE"]["passes"]
    assert new["status"] == "pass"


def test_b4_sibling_never_retains_strict():
    frames, bs, refs, configs = _sibling_round(10, with_siblings=True)
    fid = f"COMPLETE|metadiscourse|affected|{X.CLAIM_DROPPED}"
    for i in range(10):
        refs[("metadiscourse", "STRICT")][frames[fid]["rows"][f"s{i}"]] = 1  # a correct boosters
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    assert md["cumulative"]["STRICT"]["definite_losses_sampled"] == 10
    assert md["cumulative"]["LENIENT"]["definite_losses_sampled"] == 0
    assert res["status"] == "fail"  # 10/150 STRICT definite losses: a true certificate


def test_b4_sibling_memberships_reach_the_key(tmp_path):
    run_dir = tmp_path / "run"
    _write_frames(run_dir)
    # add a same-span sibling case: a baseline row whose span keeps another claim
    base = read_jsonl(run_dir / "frames" / "BASELINE.hits.jsonl")
    cand = read_jsonl(run_dir / "frames" / "COMPLETE.hits.jsonl")
    keep = next(r for r in base if r["module"] == "metadiscourse")
    extra = mk(
        "sib", tuple(keep["span"]), "self_mentions", text=keep["source_id"][1:], config="BASELINE"
    )
    extra |= {"raw": dict(keep["raw"], category="self_mentions"), "text_id": keep["text_id"]}
    base.append(extra)
    if not any(r["hit_id"] == "COMPLETE:" + keep["hit_id"].split(":")[1] for r in cand):
        cand.append(
            dict(keep, hit_id="COMPLETE:" + keep["hit_id"].split(":")[1], config="COMPLETE")
        )
    write_jsonl(run_dir / "frames" / "BASELINE.hits.jsonl", base)
    write_jsonl(run_dir / "frames" / "COMPLETE.hits.jsonl", cand)
    assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(tmp_path / "diff")]) == 0
    links = {
        r["hit_id"]: r for r in read_jsonl(tmp_path / "diff" / "links" / "COMPLETE.baseline.jsonl")
    }
    sib_link = links["BASELINE:sib"]
    assert sib_link["change_type"] == X.CLAIM_DROPPED and sib_link["siblings"]
    fr = read_json(tmp_path / "diff" / "frames.json")
    assert fr["crosswalk_version"].startswith("fixcheck-crosswalk/3")
    assert (
        sampling.main(
            [
                "--run-dir",
                str(run_dir),
                "--diff-dir",
                str(tmp_path / "diff"),
                "--round-seed",
                "5",
                "--out",
                str(tmp_path / "sample"),
                "--plan-reps",
                "0",
                "--power-reps",
                "-1",
            ]
        )
        == 0
    )
    units = read_jsonl(tmp_path / "sample" / "units.jsonl")
    sib = [m for u in units for m in u["memberships"] if m["role"] == "sibling"]
    sel = read_json(tmp_path / "sample" / "selection.json")
    if (
        "BASELINE:sib"
        in sel["frames"][f"COMPLETE|metadiscourse|affected|{X.CLAIM_DROPPED}"]["selected"]
    ):
        assert any(m["of"] == "BASELINE:sib" for m in sib)
    for u in units:
        for m in u["memberships"]:
            if m["role"] in ("counterpart", "sibling"):
                assert isinstance(m["resolved"], bool)
    edges = assign.pair_edges(units)
    assert all(len(e) == 2 for e in edges)


# --- S1: shared reference variables ---------------------------------------------------


def test_s1_shared_payload_implies_zero_loss_and_distinct_hits_count_separately():
    # counterpart has the baseline's payload: one reference variable, resolved -> no loss
    assert accept.loss_bounds(None, [(None, True, "p")], "p") == (0, 0)
    assert accept.loss_bounds(None, [(None, True, "q")], "p") == (0, 1)
    # one-to-many: two links to one unresolved payload are one variable
    assert accept.loss_bounds(1, [(None, False, "q"), (None, True, "q")], "p") == (0, 1)
    assert accept.loss_bounds(1, [(None, True, "q"), (None, True, "q")], "p") == (0, 1)
    with pytest.raises(ValueError):
        accept.loss_bounds(1, [(1, True, "q"), (0, True, "q")], "p")
    # shared identity across configurations: two frames' rows with one payload use one reference
    frames, bs, refs, configs = _round(
        {X.REMOVED: (2, {"a": (None, []), "b": (None, [])})},
        rem_family=(2, {"a": (None, []), "b": (None, [])}),
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    for fid in (
        f"COMPLETE|metadiscourse|affected|{X.REMOVED}",
        f"MD-A|metadiscourse|affected|{X.REMOVED}",
    ):
        frames[fid]["rows"] = {"a": "shared", "b": "other"}
    for oc in ("STRICT", "LENIENT"):
        refs[("metadiscourse", oc)].update({"shared": None, "other": 0})
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    assert md["removal"]["COMPLETE"]["k_hi"] == md["removal"]["MD-A"]["k_hi"] == 1


# --- B5 / M1: operational power through the real path ---------------------------------


def test_b5_hand_counterexample_unresolved_census_cannot_pass():
    plan = sampling.cumulative_plan([(1, 1)], [(1, 1)], 1.0, 10, 7)
    assert "optimistic marginal benchmark" in plan["label"]
    assert plan["simulated_pass_probability_at_true_loss_fraction"]["0.0"]["p"] == 1.0  # optimistic
    assert plan["integer_targets"]["0.0"] == {"true_losses": 0, "baseline_successes": 1}
    frames, bs, refs, configs = _round(
        {X.SPAN_CHANGED: (1, {"a": (1, [(1, False)])})},
        bs_md={"s1": (1, [1])},
        bs_ph={"t1": (1, [1])},
    )
    md = accept.compute(frames, bs, refs, configs)["modules"]["metadiscourse"]
    g = md["cumulative"]["STRICT"]
    assert md["loss"]["STRICT"]["cells"][X.SPAN_CHANGED]["k_lo"] == 0
    assert md["loss"]["STRICT"]["cells"][X.SPAN_CHANGED]["k_hi"] == 1
    assert g["U_loss"] == 1.0 and g["L_success"] == 1.0 and g["fraction"] == 1.0
    assert g["passes"] is False


def test_b5_operational_power_on_the_integration_round(tmp_path):
    from fixcheck import power

    run_dir = tmp_path / "run"
    _write_frames(run_dir)
    assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(tmp_path / "diff")]) == 0
    assert (
        sampling.main(
            [
                "--run-dir",
                str(run_dir),
                "--diff-dir",
                str(tmp_path / "diff"),
                "--round-seed",
                "5",
                "--out",
                str(tmp_path / "sample"),
                "--plan-reps",
                "0",
                "--power-reps",
                "-1",
            ]
        )
        == 0
    )
    sel = read_json(tmp_path / "sample" / "selection.json")
    pw = power.operational_power(
        run_dir,
        tmp_path / "diff",
        sel,
        6,
        11,
        lambdas=(0.0, 0.05),
        structures=("all_loss", "none_loss"),
        calibrated=(),
    )
    assert pw["structure"]["unresolved_rows"]["metadiscourse"] > 0
    sc = {(s["lambda"], s["unresolved_structure"]): s for s in pw["scenarios"]}
    assert set(sc) == {
        (0.0, "all_loss"),
        (0.0, "none_loss"),
        (0.05, "all_loss"),
        (0.05, "none_loss"),
    }
    for s in sc.values():
        r = s["realised"]["metadiscourse"]
        assert r["baseline_successes"]["INV"] >= r["baseline_successes"]["STRICT"] > 0
        assert set(s["gates"]) >= {"ALL_REQUIRED_GATES_PASS", "FAIL_BY_CERTIFICATE"}
    # with every unresolved row a true loss, the realised loss is at least the unresolved losses
    r = sc[(0.0, "all_loss")]["realised"]["metadiscourse"]
    assert r["true_losses"]["INV"] >= r["unresolved_losses"] > 0
    assert sc[(0.0, "none_loss")]["realised"]["metadiscourse"]["unresolved_losses"] == 0
    # no true loss at lambda 0 when unresolved rows are retained (many-to-one counterparts
    # carry the highest level of the rows they retain)
    for m in ("metadiscourse", "phrase"):
        assert sc[(0.0, "none_loss")]["realised"][m]["true_losses"] == {"STRICT": 0, "INV": 0}
    # coherent references: a payload has one level in a scenario
    st = power.Structure(run_dir, tmp_path / "diff", sel)
    pop = power.population(st, "metadiscourse", 0.0, "none_loss", 11)
    assert all(v in (0, 1, 2) for v in pop["levels"].values())
    # feasible attainable bounds are actual compute results on the archived selection
    att = pw["attainable"]
    assert att["most_favourable_feasible"]["result"]["status"] in ("pass", "fail", "inconclusive")
    # deterministic given the seed
    pw2 = power.operational_power(
        run_dir,
        tmp_path / "diff",
        sel,
        6,
        11,
        lambdas=(0.0, 0.05),
        structures=("all_loss", "none_loss"),
        calibrated=(),
    )
    assert pw2["scenarios"] == pw["scenarios"]


def test_wilson_interval():
    from fixcheck.power import wilson

    lo, hi = wilson(0, 200)
    assert lo == 0.0 and 0.018 < hi < 0.02
    lo, hi = wilson(200, 200)
    assert hi == 1.0 and 0.98 < lo < 0.982
    assert wilson(0, 0) is None


# --- S3: the PHRASE lookup digest covers every rank's full content ------------------------


def test_s3_lookup_digest_changes_with_one_single_sense_entry():
    by_rank = {1: {"phrase": "a", "sense": "x", "example": "e"}, 2: {"phrase": "b", "sense": None}}
    siblings = {1: [], 2: []}
    d0 = worker.lookup_digest(by_rank, siblings)
    d1 = worker.lookup_digest(
        {**by_rank, 1: {"phrase": "a", "sense": "y", "example": "e"}}, siblings
    )
    d2 = worker.lookup_digest(
        {**by_rank, 1: {"phrase": "a", "sense": "x", "example": "f"}}, siblings
    )
    d3 = worker.lookup_digest(by_rank, {1: ["s"], 2: []})
    assert len({d0, d1, d2, d3}) == 4
    assert worker.lookup_digest(dict(reversed(list(by_rank.items()))), siblings) == d0


# --- S4: dry runs keyed by candidate digest -------------------------------------------


def test_s4_dry_run_is_keyed_by_digest_and_refuses_a_stale_resume(tmp_path, monkeypatch):
    state = {"digest": "a" * 64}

    def fake_cli(args):
        dest = Path(args[args.index("--dest") + 1])
        (dest / "lexinspect").mkdir(parents=True)
        write_json(
            dest / "CANDIDATE_SNAPSHOT.json",
            {
                "tree_sha256": state["digest"],
                "source": "working_tree",
                "label": "interim",
                "n_files": 1,
            },
        )
        return 0

    monkeypatch.setattr(dryrun, "_cli", fake_cli)
    out, key = dryrun.snapshot_and_key(tmp_path, None, None, False)
    assert out == tmp_path / ("a" * 16) and key["candidate_tree_sha256"] == "a" * 64
    assert key["production_eligible"] is False
    (out / "stage.json").write_text("{}")
    out2, _ = dryrun.snapshot_and_key(tmp_path, None, None, False)  # same digest: resume
    assert out2 == out and (out / "stage.json").exists()
    state["digest"] = "b" * 64
    with pytest.raises(SystemExit, match="refusing to resume"):
        dryrun.snapshot_and_key(tmp_path, out, None, False)
    assert (out / "stage.json").exists()
    assert read_json(out / "DRYRUN_KEY.json")["candidate_tree_sha256"] == "a" * 64
    out3, key3 = dryrun.snapshot_and_key(tmp_path, out, None, True)  # --overwrite regenerates
    assert out3 == out and not (out / "stage.json").exists()
    assert read_json(out / "candidate_src" / "CANDIDATE_SNAPSHOT.json")["tree_sha256"] == "b" * 64
    assert key3["candidate_tree_sha256"] == "b" * 64
    assert not list(tmp_path.glob(".snapshot-*"))


# --- S2: neutral sessions and the delivery spec --------------------------------------------


def test_s2_spec_pins_the_registered_prompt_materials_and_routes():
    spec = sessions.build_spec()
    assert sessions.check_spec(spec) == []
    tpl = spec["prompt_template"]
    assert tpl.startswith("You are labelling items for a research study")
    assert "⟨dir⟩/items.jsonl" in tpl and "⟨n⟩ items" in tpl
    assert spec["max_batch_size"] == 325
    assert spec["roles"]["adjudicator"]["model"] == "opencode/deepseek-v4.1-flash-free"
    ph = sessions.pilot_hashes()
    for m in spec["materials"].values():
        assert ph[m["source"]] == m["sha256"]
    bad = dict(spec, prompt_template=tpl + "extra")
    assert sessions.check_spec(bad)


def test_s2_material_mismatch_or_missing_pilot_hash_refuses(tmp_path, monkeypatch):
    fake = tmp_path / "guidelines.md"
    fake.write_text("not the frozen guidelines\n")
    monkeypatch.setitem(sessions.MATERIALS, "guidelines.md", fake)
    with pytest.raises(SystemExit):
        sessions.build_spec()
    with pytest.raises(SystemExit, match="pilot hashes"):
        sessions.build_spec(pilot=tmp_path / "missing.sha256")


def test_s2_batch_size_above_325_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="1..325"):
        assign.main(
            ["--sample-dir", str(tmp_path), "--out", str(tmp_path / "a"), "--batch-size", "326"]
        )
    for main in (assign.main_flash, assign.main_retry):
        with pytest.raises(SystemExit, match="1..325"):
            main(["--assign-dir", str(tmp_path), "--labels", "A=x", "B=y", "--batch-size", "400"])


# --- B2 / B3 / S2: a whole package -------------------------------------------------------


def _deliver(so, per_role):
    dryrun.deliver(so, per_role, so / "transcripts")


def _gather(so, role, dest):
    assert sessions.main_gather(["--stage-out", str(so), "--role", role, "--out", str(dest)]) == 0


def _receipt(P, stage, root):
    rc = root / "receipts" / f"{stage}.json"
    assert (
        sessions.main_stage_receipt(["--package", str(P), "--stage", stage, "--out", str(rc)]) == 0
    )
    return rc


@pytest.fixture(scope="module")
def pkg(tmp_path_factory):
    """A complete (dry-run) round package on the integration frames, with sessions, a bound
    delivery spec and a stage receipt before every export (audit r2 B3, B5)."""
    from fixcheck.common import source_hashes

    root = tmp_path_factory.mktemp("q")
    P = root / "pkg"
    run_dir = P / "run"
    _write_frames(run_dir)
    assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(P / "diff")]) == 0
    assert (
        sampling.main(
            [
                "--run-dir",
                str(run_dir),
                "--diff-dir",
                str(P / "diff"),
                "--round-seed",
                "5",
                "--out",
                str(P / "sample"),
                "--plan-reps",
                "0",
                "--power-reps",
                "2",
            ]
        )
        == 0
    )
    ad = P / "assign"
    assert (
        assign.main(["--sample-dir", str(P / "sample"), "--out", str(ad), "--batch-size", "100"])
        == 0
    )
    spec = root / "delivery_spec.json"
    write_json(spec, sessions.build_spec())
    # a dry-run collection part (development-style round, stamped ineligible), binding the spec
    c = P / "collect"
    c.mkdir()
    write_json(
        c / "freeze_record.json",
        {
            "kind": freeze.FREEZE_KIND,
            "version": freeze.FREEZE_VERSION,
            "dry_run": True,
            "round": 1,
            "seed": 5,
            "candidate": {"commit": None, "tree_sha256": "t"},
            "production_eligible": False,
            "ineligible_reasons": ["dry run"],
            "bound": {"delivery_spec": freeze.file_identity(spec)},
            "delivery": {"spec_sha256": read_json(spec)["spec_sha256"]},
            "sources_sha256": source_hashes(),
            "environment": freeze.environment_identity(freeze.REPO),
        },
    )
    (c / "texts.jsonl").write_text("")
    write_json(
        c / "collection.json",
        {
            "round": 1,
            "seed": 5,
            "status": "complete",
            "texts_jsonl_sha256": sha256_file(c / "texts.jsonl"),
            "freeze_record_sha256": sha256_file(c / "freeze_record.json"),
            "production_eligible": False,
        },
    )
    write_json(
        c / "execution.json",
        {
            "freeze_record_sha256": sha256_file(c / "freeze_record.json"),
            "collection_json_sha256": sha256_file(c / "collection.json"),
        },
    )
    sroot = root / "inbox"
    items = {r["id"]: r for r in read_jsonl(ad / "items.jsonl")}
    key = read_jsonl(ad / "key.jsonl")
    L = P / "labels"
    L.mkdir()
    so = P / "sessions" / "primary"
    sessions.export(spec, "primary", ad, sroot / "p", so, P, receipt=_receipt(P, "primary", root))
    la, lb = synthetic.random_primaries(key, items, 20261117)
    _deliver(so, {"A": la, "B": lb})
    for r in ("A", "B"):
        _gather(so, r, L / f"{r}.pass1.jsonl")
    assert (
        assign.main_retry(
            [
                "--assign-dir",
                str(ad),
                "--labels",
                f"A={L / 'A.pass1.jsonl'}",
                f"B={L / 'B.pass1.jsonl'}",
                "--batch-size",
                "100",
            ]
        )
        == 0
    )
    manifest = {r: analyse.read_id_file(ad / "retry" / f"retry_{r}.jsonl") for r in ("A", "B")}
    assert manifest["A"] and manifest["B"]
    sr = P / "sessions" / "retry"
    sessions.export(
        spec, "retry", ad / "retry", sroot / "r", sr, P, receipt=_receipt(P, "retry", root)
    )
    answers = {r: synthetic.retry_answers(ids, items, 7 + ord(r)) for r, ids in manifest.items()}
    _deliver(sr, answers)
    for r in ("A", "B"):
        _gather(sr, r, L / f"{r}.retry.jsonl")
        first = (L / f"{r}.pass1.jsonl").read_text().splitlines()
        merged, _ = analyse.merge_retry(
            first, (L / f"{r}.retry.jsonl").read_text().splitlines(), manifest[r]
        )
        (L / f"{r}.jsonl").write_text("".join(x + "\n" for x in merged))
    assert (
        assign.main_flash(
            [
                "--assign-dir",
                str(ad),
                "--labels",
                f"A={L / 'A.jsonl'}",
                f"B={L / 'B.jsonl'}",
                "--batch-size",
                "100",
            ]
        )
        == 0
    )
    fids = (ad / "flash" / "flash_ids.txt").read_text().split()
    assert fids
    sf = P / "sessions" / "flash"
    sessions.export(
        spec, "flash", ad / "flash", sroot / "f", sf, P, receipt=_receipt(P, "flash", root)
    )
    _deliver(sf, {"adjudicator": synthetic.random_adjudicator(fids, items, 3)})
    _gather(sf, "adjudicator", L / "adjudicator.jsonl")
    from fixcheck import verify

    verify.main(
        [
            "--out",
            str(P / "verify"),
            "--ledger-md",
            str(ledger.DRAFT_LEDGER_MD),
            "--assign-dir",
            str(ad),
            "--sample-dir",
            str(P / "sample"),
            "--run-dir",
            str(run_dir),
            "--flash-dir",
            str(ad / "flash"),
            "--retry-dir",
            str(ad / "retry"),
        ]
    )
    return P


# The only problems a dry-run package's labels chain may have: its stage receipts cannot be
# committed and pushed (no production archive receipt).
UNARCHIVED = "was not archived (committed and pushed) before delivery"


def _real(probs):
    return [x for x in probs if UNARCHIVED not in x]


def _copy(pkg, tmp_path):
    dst = tmp_path / "pkg"
    shutil.copytree(pkg, dst)
    return dst


def test_s2_session_directories_hold_exactly_the_three_files(pkg):
    idx = read_json(pkg / "sessions" / "primary" / "sessions_index.json")
    assert idx["sessions"]
    for s in idx["sessions"]:
        d = Path(s["dir"])
        assert sorted(x.name for x in d.iterdir()) == sorted(
            [*sessions.SESSION_FILES, "labels.jsonl"]
        )
        assert pkg.resolve() not in d.resolve().parents
        prompt = (pkg / "sessions" / "primary" / "prompts" / f"{s['token']}.txt").read_text()
        assert f"{d}/items.jsonl" in prompt and f"{s['n']} items" in prompt
        assert d.name == s["token"] and len(d.name) == 17 and int(d.name[1:], 16) >= 0
        assert s["n"] <= 325


def test_s2_non_neutral_session_root_is_refused(tmp_path):
    # audit r2 B3: the WHOLE resolved visible path is checked, not the last two components
    # (pytest's tmp_path itself names this test, i.e. a session: refused too)
    assert sessions.check_session_root(tmp_path / "x" / "flash_batches", None)
    assert sessions.check_session_root(tmp_path / "x" / "inbox", tmp_path / "x")
    assert sessions.check_session_root(tmp_path / "x" / "inbox", None)
    neutral = sessions.fresh_root()
    assert sessions.check_session_root(neutral, None) == []
    assert sessions.check_session_root(neutral / "q7", neutral / "elsewhere") == []


def test_b3_clean_package_labels_chain_has_no_problem(pkg):
    P = package.resolve(pkg)
    probs, info = package.check_labels(P)
    assert _real(probs) == [], probs
    assert sorted(x.split(":")[0] for x in probs) == ["flash", "primary", "retry"]
    assert all(v == 0 for v in info["never_delivered"].values())


@pytest.mark.parametrize(
    "mutation, expect",
    [
        ("stale_flash_omitted", "omitted"),
        ("stale_flash_extra", "extra"),
        ("altered_primary", "deterministic merge"),
        ("altered_definite_label", "deterministic merge"),
        ("skipped_retry", "skipped"),
        ("second_retry", "second retry"),
        ("never_delivered", "never delivered"),
        ("wrong_model", "is not the spec's"),
        ("relabelled_session", "labels.jsonl missing or differs"),
        ("selective_retry_manifest", "own retry list"),
    ],
)
def test_b3_provenance_failures(pkg, tmp_path, mutation, expect):
    P0 = _copy(pkg, tmp_path)
    L, ad = P0 / "labels", P0 / "assign"
    if mutation.startswith("stale_flash"):
        f = ad / "flash" / "flash_ids.txt"
        ids = f.read_text().split()
        if mutation.endswith("omitted"):
            ids = ids[1:]
        else:
            key = read_jsonl(ad / "key.jsonl")
            ids = sorted([*ids, next(k["id"] for k in key if k["id"] not in set(ids))])
        f.write_text("".join(i + "\n" for i in ids))
    elif mutation in ("altered_primary", "altered_definite_label"):
        lines = (L / "A.jsonl").read_text().splitlines()
        manifest = set(analyse.read_id_file(ad / "retry" / "retry_A.jsonl"))
        for i, x in enumerate(lines):
            r = json.loads(x)
            if r["id"] not in manifest and r.get("label") in ("CORRECT", "NOT_METADISCOURSE"):
                r["label"] = "NOT_METADISCOURSE" if r["label"] == "CORRECT" else "CORRECT"
                r["alt_category"] = None
                lines[i] = json.dumps(r)
                break
        (L / "A.jsonl").write_text("".join(x + "\n" for x in lines))
    elif mutation == "skipped_retry":
        (L / "A.retry.jsonl").unlink()
    elif mutation == "second_retry":
        shutil.copy(L / "A.retry.jsonl", L / "A.retry2.jsonl")
    elif mutation in ("never_delivered", "wrong_model"):
        so = P0 / "sessions" / "primary"
        recs = read_jsonl(so / "deliveries.jsonl")
        if mutation == "never_delivered":
            recs[0]["delivered"] = False
        else:
            recs[0]["model"] = "some-other-model"
        write_jsonl(so / "deliveries.jsonl", recs)
    elif mutation == "relabelled_session":
        so = P0 / "sessions" / "primary"
        recs = read_jsonl(so / "deliveries.jsonl")
        recs[0]["labels_sha256"] = "0" * 64
        write_jsonl(so / "deliveries.jsonl", recs)
    elif mutation == "selective_retry_manifest":
        f = ad / "retry" / "retry_A.jsonl"
        f.write_text("".join(f.read_text().splitlines(keepends=True)[1:]))
    probs, _ = package.check_labels(package.resolve(P0))
    assert any(expect in p for p in _real(probs)), probs


def test_b2_dry_package_is_math_only_and_never_registered(pkg, tmp_path, monkeypatch):
    calls = {}
    real = accept.compute

    def spy(frames, bs, refs, configs, rnd=1, procedure_problems=None, **kw):
        calls["problems"] = list(procedure_problems or [])
        return real(frames, bs, refs, configs, rnd=rnd, procedure_problems=procedure_problems, **kw)

    monkeypatch.setattr(accept, "compute", spy)
    assert accept.main(["--package", str(pkg), "--dry-run", "--out", str(tmp_path / "dry")]) == 0
    dry = read_json(tmp_path / "dry" / "acceptance.json")
    assert dry["production_eligible"] is False and dry["mathematical_status"] == dry["status"]
    assert dry["procedure_problems_not_applied"] and calls["problems"] == []
    assert dry["registry_entry"] is None and not (tmp_path / "dry" / "registration.json").exists()
    # production on a non-canonical registry is refused before any production step
    reg = tmp_path / "reg.jsonl"
    with pytest.raises(SystemExit, match="not the canonical registry"):
        accept.main(["--package", str(pkg), "--registry", str(reg), "--out", str(tmp_path / "p")])
    assert not (tmp_path / "p").exists() and not reg.exists()
    # the preview is the chain check only: no arithmetic, no status, no registration
    assert accept.main(["--package", str(pkg), "--check-only", "--out", str(tmp_path / "chk")]) == 0
    chk = read_json(tmp_path / "chk" / "package_check.json")
    assert chk["problems"] and "status" not in chk and "modules" not in chk
    assert not (tmp_path / "chk" / "acceptance.json").exists()


def test_b2_round_comes_from_the_package_not_the_cli(pkg, tmp_path):
    with pytest.raises(SystemExit):
        accept.main(["--package", str(pkg), "--round", "2", "--out", str(tmp_path / "x")])


def test_b2_chain_detects_a_changed_link(pkg, tmp_path):
    P0 = _copy(pkg, tmp_path)
    clean = package.check_package(P0)
    (P0 / "sample" / "units.jsonl").write_text((P0 / "sample" / "units.jsonl").read_text() + "\n")
    after = package.check_package(P0)
    new = set(after["problems"]) - set(clean["problems"])
    assert any("units.jsonl" in p for p in new)


def _res(rnd=1, cand="c1", seed=1, cdir="r1"):
    return {
        "type": "reservation",
        "round": rnd,
        "candidate_commit": cand,
        "candidate_tree_sha256": None,
        "seed": seed,
        "collect_dir": cdir,
    }


def _dec(
    rnd=1,
    cand="c1",
    seed=1,
    texts="t1",
    inputs="i1",
    status="inconclusive",
    refs=("s1",),
    res=None,
    r1=None,
):
    fam = list(ledger.FAMILIES)
    d = {
        "type": "decision",
        "round": rnd,
        "candidate_commit": cand,
        "candidate_tree_sha256": None,
        "seed": seed,
        "reservation_sha256": registry.entry_sha256(res or _res(rnd, cand, seed)),
        "collection_texts_sha256": texts,
        "source_refs": list(refs),
        "session_ids_sha256": [],
        "transcripts_sha256": [],
        "inputs_sha256": inputs,
        "status": status,
        "families": fam,
    }
    if r1 is not None:
        d["round1_entry_sha256"] = registry.entry_sha256(r1)
    return d


def test_b2_registry_rules():
    r1res = _res()
    assert registry.check_decision([], _dec())[0] == "refuse"  # no reservation
    assert registry.check_decision([r1res], _dec())[0] == "append"
    e = [r1res, _dec()]
    assert registry.check_decision(e, _dec())[0] == "idempotent"
    assert registry.check_decision(e, _dec(inputs="i2"))[0] == "refuse"  # new labels
    assert registry.check_decision(e, _dec(status="pass"))[0] == "refuse"
    assert registry.check_decision(e, _dec(cand="c2"))[0] == "refuse"  # identities charged
    # reservations: one per round; round 2 only after a registered round-1 non-pass
    assert registry.check_reservation([], _res())[0] == "append"
    assert registry.check_reservation([r1res], _res())[0] == "present"
    assert registry.check_reservation([r1res], _res(seed=9))[0] == "refuse"  # parallel package
    assert registry.check_reservation([r1res], _res(rnd=2, cand="c2", seed=2))[0] == "refuse"
    assert registry.check_reservation(e, _res(rnd=2, cand="c2", seed=2))[0] == "append"
    assert registry.check_reservation(e, _res(rnd=2, cand="c1", seed=2))[0] == "refuse"
    assert registry.check_reservation(e, _res(rnd=2, cand="c2", seed=1))[0] == "refuse"
    r2res = _res(rnd=2, cand="c2", seed=2, cdir="r2")
    e2 = [*e, r2res]
    ok2 = _dec(rnd=2, cand="c2", seed=2, texts="t2", refs=("s2",), res=r2res, r1=e[1])
    assert registry.check_decision(e2, ok2)[0] == "append"
    shared = dict(ok2, source_refs=["s1", "s2"])  # one shared canonical source identity
    assert registry.check_decision(e2, shared)[0] == "refuse"
    assert registry.check_decision(e2, dict(ok2, round1_entry_sha256="x"))[0] == "refuse"
    pass1 = [r1res, _dec(status="pass"), r2res]
    assert registry.check_decision(pass1, ok2)[0] == "refuse"
    assert registry.check_reservation([r1res, _dec(status="pass")], r2res)[0] == "refuse"
    bad = dict(_dec(), families=list(ledger.FAMILIES)[:-1])
    assert registry.check_decision([r1res], bad)[0] == "refuse"
    term = [*e2, ok2, {"type": "terminal", "outcome": "revert_0.3.3"}]
    assert registry.check_reservation(term, _res(rnd=2, cand="c3", seed=3))[0] == "refuse"
    assert registry.check_terminal([_dec(status="pass")], "ship") == []
    assert registry.check_terminal([_dec()], "ship")
    assert registry.check_terminal([*e2, ok2], "revert_0.3.3") == []
    assert registry.check_terminal(term, "amendment")


def test_b2_registry_append_only_against_head_and_history(tmp_path):
    repo = _repo(tmp_path)
    reg = _canonical_registry(repo, [_res()])
    i = registry.integrity(reg, repo)
    assert any("not committed at HEAD" in p for p in i["problems"])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reg")
    assert registry.integrity(reg, repo)["ok"]
    registry.append_unchecked(reg, _dec())
    assert registry.integrity(reg, repo)["ok"]  # an uncommitted append is an extension
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "decision")
    # a truncated working copy, a substituted path, a non-canonical line
    full = reg.read_text()
    reg.write_text(full.splitlines()[1] + "\n")
    assert any("append-only" in p for p in registry.integrity(reg, repo)["problems"])
    reg.write_text(full)
    other = repo / "elsewhere.jsonl"
    other.write_text(full)
    assert any("not the canonical" in p for p in registry.integrity(other, repo)["problems"])
    reg.write_text(full + '{"type":  "terminal"}\n')
    assert any("canonical JSON" in p for p in registry.integrity(reg, repo)["problems"])
    reg.write_text(full)
    # a committed rewrite of history (a reset registry committed at HEAD) is refused
    reg.write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reset")
    assert any("rewrites the registry" in p for p in registry.integrity(reg, repo)["problems"])
    # a missing registry is refused
    reg.unlink()
    assert any("missing" in p for p in registry.integrity(reg, repo)["problems"])


# --- M2: paired counts labelled; worst-case ranges ---------------------------------------


def test_m2_descriptive_labels_and_worst_case_range():
    d = accept.descriptive_interval(10, [1, 1, None, 0])
    assert "assigned_sample_worst_case_range" in d
    lo, hi = d["assigned_sample_worst_case_range"]
    assert lo == pytest.approx(2 / 4) and hi == pytest.approx(3 / 4)


def test_blinding_audit_keeps_two_same_named_retry_dirs_apart(pkg, tmp_path):
    from fixcheck import verify

    other = tmp_path / "favourable" / "retry"
    other.mkdir(parents=True)
    for r in ("A", "B"):
        (other / f"retry_{r}.jsonl").write_text("")  # an empty retry: no batches
    res = verify.blinding_audit(
        pkg / "assign", pkg / "sample", pkg / "run", retry_dirs=[pkg / "assign" / "retry", other]
    )
    assert res["ok"], res["problems"][:5]
    assert "retry A (assign/retry)" in res["roles"]
