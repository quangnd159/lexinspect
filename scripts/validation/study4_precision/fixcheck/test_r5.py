"""Harness audit r2 dispositions (R2-B1..B5, R2-S1..S5, R2-M1): every executed probe is a
regression that now refuses, is inconclusive or gives the exact number.

uv run pytest -p no:warnings scripts/validation/study4_precision/fixcheck
"""

from __future__ import annotations

import itertools
import json
import os
import random
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402

from fixcheck import (  # noqa: E402
    accept,
    collect,
    dryrun,
    freeze,
    ledger,
    package,
    registry,
    sessions,
)
from fixcheck import crosswalk as X  # noqa: E402
from fixcheck.common import (  # noqa: E402
    canonical_json,
    read_json,
    read_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)
from fixcheck.test_fixcheck import (  # noqa: E402
    _collect_r1,
    _jats,
    _mock_cache,
    _r1_registry,
    _round,
    cw,
    mk,
)
from fixcheck.test_r4 import (  # noqa: E402, F401  (pkg: a module-scoped fixture)
    UNARCHIVED,
    _canonical_registry,
    _copy,
    _dec,
    _git,
    _real,
    _repo,
    _res,
    pkg,
)

# --- R2-B4: the removal gate is the genuine-deletion population ---------------------------


def test_r2_b4_census_dilution_numbers():
    # The audit's exact census counterexample: the genuine-deletion gate certifies breach;
    # adding ten unsuccessful dropped sibling claims to its denominator would pass it.
    a = accept.removal_component(10, [1, 1] + [0] * 8)
    assert a["bound"] == pytest.approx(0.2) and a["passes"] is False
    assert a["breach_certificate"] is True
    b = accept.removal_component(20, [1, 1] + [0] * 18)
    assert b["bound"] == pytest.approx(0.1) and b["passes"] is True
    assert b["breach_certificate"] is False


def _dilution_frames():
    """Ten genuine deletions (two successful) and ten claims dropped at spans that keep an
    unsuccessful sibling claim, as the crosswalk sees them."""
    base, cand = [], []
    for i in range(10):
        base.append(mk(f"g{i}", (100 * i, 100 * i + 4), "hedges", text="1"))
    for i in range(10):
        s = 5000 + 100 * i
        base.append(mk(f"k{i}", (s, s + 4), "hedges", text="1"))
        base.append(mk(f"d{i}", (s, s + 4), "boosters", text="1"))
        cand.append(mk(f"k{i}", (s, s + 4), "hedges", text="1", config="C"))
    return base, cand


def test_r2_b4_crosswalk_keeps_dropped_claims_out_of_the_deletion_frame():
    base, cand = _dilution_frames()
    bl, cl = cw(base, cand)
    fr = X.frames_for(base, cand, bl, cl)["metadiscourse"]
    assert fr["affected_sizes"][X.REMOVED] == 10  # genuine deletions only
    assert fr["affected_sizes"][X.CLAIM_DROPPED] == 10
    assert fr["N_genuine_deletion"] == 10
    for i in range(10):
        assert bl[f"B:d{i}"]["change_type"] == X.CLAIM_DROPPED
        assert bl[f"B:d{i}"]["siblings"] == [f"C:k{i}"]
        assert bl[f"B:g{i}"]["change_type"] == X.REMOVED and bl[f"B:g{i}"]["siblings"] == []
    # check_partition refuses either population assigned to the other cell
    bad = dict(bl)
    bad["B:d0"] = dict(bl["B:d0"], change_type=X.REMOVED)
    assert any("REMOVED although" in p for p in X.check_partition(base, cand, bad, cl))
    bad = dict(bl)
    bad["B:g0"] = dict(bl["B:g0"], change_type=X.CLAIM_DROPPED)
    assert any("CLAIM_DROPPED without" in p for p in X.check_partition(base, cand, bad, cl))


def _dilution_round(dropped_in_removal_frame: bool):
    """The census example through accept.compute, with every other gate passing."""
    genuine = {f"g{i}": (1 if i < 2 else 0, []) for i in range(10)}
    dropped = {f"d{i}": (0, [(0, True)]) for i in range(10)}  # sibling unsuccessful too
    if dropped_in_removal_frame:  # the withdrawn ruling A2
        cells = {X.REMOVED: (20, genuine | {k: (0, []) for k in dropped})}
    else:
        cells = {X.REMOVED: (10, genuine), X.CLAIM_DROPPED: (10, dropped)}
    frames, bs, refs, configs = _round(
        cells,
        bs_md={"s1": (5000, [1] * 200)},
        bs_ph={"t1": (500, [1] * 200)},
    )
    if not dropped_in_removal_frame:
        fid = f"COMPLETE|metadiscourse|affected|{X.CLAIM_DROPPED}"
        frames[fid]["counterparts"] = {
            r: [(q, res, "sibling") for q, res in v] for r, v in frames[fid]["counterparts"].items()
        }
    return accept.compute(frames, bs, refs, configs)


def test_r2_b4_no_other_gate_fails_so_only_the_genuine_deletion_gate_vetoes():
    res = _dilution_round(dropped_in_removal_frame=False)
    md = res["modules"]["metadiscourse"]
    rem = md["removal"]["COMPLETE"]
    assert (rem["N"], rem["n"], rem["k_lo"], rem["k_hi"]) == (10, 10, 2, 2)
    assert rem["bound"] == pytest.approx(0.2) and rem["breach_certificate"] is True
    for oc in ("STRICT", "LENIENT"):  # the cumulative safeguards pass: they cannot veto
        g = md["cumulative"][oc]
        assert g["passes"] is True and g["breach_certificate"] is False
    assert md["breach_certificates"] == ["removal COMPLETE"]
    assert res["modules"]["phrase"]["status"] == "pass"
    assert md["status"] == "fail" and res["status"] == "fail"
    assert res["procedure_problems"] == []
    # the withdrawn reading would have passed the same candidate
    old = _dilution_round(dropped_in_removal_frame=True)
    assert old["modules"]["metadiscourse"]["removal"]["COMPLETE"]["passes"] is True
    assert old["status"] == "pass"


def test_r2_b4_claim_dropped_row_without_its_sibling_is_a_procedure_problem():
    frames, bs, refs, configs = _round(
        {X.CLAIM_DROPPED: (1, {"d": (1, [])})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    assert any("no labelled same-span sibling" in p for p in res["procedure_problems"])
    assert res["status"] != "pass"


# --- R2-S1: exact per-row loss for any number of variables --------------------------------


def _brute(y_b, cps, b_payload):
    """Enumerate every completion of the unresolved reference variables (test oracle)."""
    bvar = b_payload if b_payload is not None else "\0b"
    cps = [
        (c[0], c[1], c[2] if len(c) > 2 and c[2] is not None else f"\0c{i}")
        for i, c in enumerate(cps)
    ]
    known = {bvar: y_b}
    for y, _, p in cps:
        if known.get(p) is None:
            known[p] = y
    unknown = sorted(p for p, v in known.items() if v is None)
    lo, hi = 1, 0
    for bits in itertools.product((0, 1), repeat=len(unknown)):
        val = dict(known) | dict(zip(unknown, bits, strict=True))
        if val[bvar] != 1:
            lo = 0
            continue
        hi = max(hi, int(not any(val[p] == 1 and res is True for _, res, p in cps)))
        lo = min(lo, int(not any(val[p] == 1 for _, _, p in cps)))
    return lo, hi


def test_r2_s1_more_than_twelve_variables_is_exact():
    # the audit probe: 13 unknown payloads, the identical resolved counterpart forces zero
    cps = [(None, True, "b")] + [(None, True, f"q{i}") for i in range(12)]
    assert accept.loss_bounds(None, cps, "b") == (0, 0)
    cps = [(None, True, "b")] + [(None, False, f"q{i}") for i in range(40)]
    assert accept.loss_bounds(1, cps, "b") == (0, 0)
    assert accept.loss_bounds(1, [(None, False, f"q{i}") for i in range(40)], "b") == (0, 1)
    assert accept.loss_bounds(1, [(0, True, f"q{i}") for i in range(40)], "b") == (1, 1)


def test_r2_s1_analytic_equals_enumeration():
    r = random.Random(17)
    for _ in range(3000):
        k = r.randint(0, 6)
        pool = ["b", "q1", "q2", "q3"]
        y_b = r.choice((0, 1, None))
        known = {"b": y_b}
        cps = []
        for _ in range(k):
            p = r.choice(pool + [None])
            y = r.choice((0, 1, None)) if p is None or known.get(p) is None else known[p]
            if p is not None and known.get(p) is None and y is not None:
                known[p] = y
            cps.append((y, r.random() < 0.6, p))
        try:
            got = accept.loss_bounds(y_b, cps, "b")
        except ValueError:
            continue
        assert got == _brute(y_b, cps, "b"), (y_b, cps)


def test_r2_s1_coupled_rows_cell_total_is_a_declared_conservative_relaxation():
    # rows x->y and y->x with unknown payloads: per-row exact maxima 1 + 1 = 2, but every
    # joint completion gives x(1-y) + y(1-x) <= 1. The harness sums per-row extrema
    # (clarifications 1.2: a conservative relaxation, it can only raise U_loss).
    row1 = accept.loss_bounds(None, [(None, True, "y")], "x")
    row2 = accept.loss_bounds(None, [(None, True, "x")], "y")
    assert row1 == row2 == (0, 1)
    joint = max(x * (1 - y) + y * (1 - x) for x in (0, 1) for y in (0, 1))
    assert joint == 1 and row1[1] + row2[1] == 2 >= joint


# --- R2-B1: the archive receipt accepts only a full remote-tracking ref -------------------


def test_r2_b1_audit_probe_head_is_not_a_receipt():
    # the audit's executed probe, on the actual repository (read only)
    r = freeze.archive_receipt([freeze.PROTOCOL], remote_ref="HEAD")
    assert r["ok"] is False
    assert any("not a full remote-tracking ref" in p for p in r["problems"])


@pytest.mark.parametrize(
    "spelling",
    [
        "HEAD",
        "main",  # a local branch
        "refs/heads/main",
        "v1",  # a tag
        "refs/tags/v1",
        "OBJECT_ID",  # a raw full object id
        "OBJECT_ID_SHORT",  # an abbreviated object id
        "origin/main",  # an abbreviated remote ref
        "remotes/origin/main",
        "refs/remotes/origin/main~0",  # revision expressions
        "refs/remotes/origin/main^{commit}",
        "refs/remotes/origin/main@{0}",
        "refs/remotes/origin/main:record.json",
        "refs/remotes/origin/HEAD",  # a symbolic ref
        "refs/remotes/upstream/main",  # another remote
        "refs/remotes/origin/local-only",  # not on any remote: a local commit under that name
    ],
)
def test_r2_b1_local_only_commit_cannot_qualify(tmp_path, spelling):
    repo = _repo(tmp_path)
    # an unpushed local commit, reachable from every forbidden spelling
    (repo / "record.json").write_text('{"local": 1}\n')
    _git(repo, "commit", "-q", "-am", "local only")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "tag", "v1")
    _git(repo, "update-ref", "refs/remotes/upstream/main", "HEAD")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    ref = {"OBJECT_ID": head, "OBJECT_ID_SHORT": head[:12]}.get(spelling, spelling)
    if spelling.endswith("local-only"):
        # even a well-formed name is only as good as its target: it must hold HEAD; here it
        # names the old remote commit, so the local commit is not on it
        _git(repo, "update-ref", ref, "refs/remotes/origin/main")
    r = freeze.archive_receipt([repo / "record.json"], repo, ref)
    assert r["ok"] is False, spelling
    # the registered full ref, once the commit really is on it, qualifies
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    ok = freeze.archive_receipt([repo / "record.json"], repo, "refs/remotes/origin/main")
    assert ok["ok"], ok["problems"]
    assert ok["remote_ref"] == "refs/remotes/origin/main" and ok["remote_commit"] == head
    assert ok["remote_url"] == "https://example.invalid/never-contacted.git"


def test_r2_b1_receipt_covers_every_bound_file(tmp_path):
    d = tmp_path / "plan"
    rec = {
        "ledger": {
            "markdown": {"path": str(tmp_path / "LEDGER.md")},
            "components": {"path": str(tmp_path / "ledger_components.json")},
        },
        "protocol": {"path": str(tmp_path / "protocol.md")},
        "clarifications": {"path": str(tmp_path / "clarifications.md")},
        "bound": {
            "preregistration": {"path": str(tmp_path / "prereg.md")},
            "delivery_spec": {"path": str(tmp_path / "delivery_spec.json")},
            "registry": {"path": str(tmp_path / "round_registry.jsonl")},
            "dispositions": [
                {"path": str(tmp_path / "D1.md")},
                {"path": str(tmp_path / "RULINGS.md")},
            ],
        },
        "round2": None,
    }
    got = {Path(x).name for x in freeze.receipt_paths(d / "freeze_record.json", rec)}
    for want in (
        "freeze_record.json",
        "command.txt",
        "manifest_plan.json",
        "LEDGER.md",
        "ledger_components.json",
        "protocol.md",
        "clarifications.md",
        "prereg.md",
        "delivery_spec.json",
        "round_registry.jsonl",
        "D1.md",
        "RULINGS.md",
        "package.py",
        "build.py",
        "analyse.py",
    ):
        assert want in got, want


def test_r2_b1_archived_receipt_is_revalidated_against_committed_objects(tmp_path):
    repo = _repo(tmp_path)
    ref = "refs/remotes/origin/main"
    rc = freeze.archive_receipt([repo / "record.json"], repo, ref)
    assert rc["ok"] and freeze.verify_receipt(rc, repo, [repo / "record.json"]) == []
    # a receipt that merely says ok: its commit is not in the repository
    fake = dict(rc, head="0" * 40)
    assert freeze.verify_receipt(fake, repo)
    # a file not covered, a file changed since, a ref moved off the commit
    assert freeze.verify_receipt(rc, repo, [repo / "src" / "lexinspect" / "__init__.py"])
    (repo / "record.json").write_text("{}\n{}\n")
    assert any("changed since the receipt" in p for p in freeze.verify_receipt(rc, repo))
    _git(repo, "checkout", "-q", "--", ".")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "other")
    _git(repo, "update-ref", ref, "HEAD~1~0")
    other = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    _git(repo, "update-ref", ref, other)  # still a descendant: fine
    assert freeze.verify_receipt(rc, repo) == []


# --- R2-B2: one canonical registry; reservation; atomic registration ----------------------


def _prod_check(real, reservation, seed=5, inputs=None):
    def check(package_path):
        chk = real(package_path)
        coll = dict(chk["collection"])
        coll.update(
            dry_run=False,
            production=True,
            round=1,
            seed=seed,
            candidate={"commit": "c1", "tree_sha256": None},
            reservation_sha256=registry.entry_sha256(reservation),
        )
        out = dict(chk, collection=coll)
        if inputs is not None:
            out["inputs_sha256"] = inputs
        return out

    return check


def test_r2_b2_production_registers_atomically_and_refuses_reuse(pkg, tmp_path, monkeypatch):  # noqa: F811
    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    res = _res(cand="c1", seed=5)
    reg = _canonical_registry(repo, [res])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reserve")
    real = package.check_package
    monkeypatch.setattr(package, "check_package", _prod_check(real, res))
    out = tmp_path / "acc"
    assert accept.main(["--package", str(pkg), "--registry", str(reg), "--out", str(out)]) == 0
    acc = read_json(out / "acceptance.json")
    # a dry-run package's problems are procedure problems in production: never pass (the
    # random synthetic labels here also hold a breach certificate, so the status is fail)
    assert acc["status"] != "pass" and acc["procedure_problems"]
    lines = registry.load(reg)
    assert [e["type"] for e in lines] == ["reservation", "decision"]
    assert lines[1]["status"] == acc["status"]
    assert lines[1]["acceptance_sha256"] == sha256_file(out / "acceptance.json")
    assert read_json(out / "registration.json")["verdict"] == "append"
    # identical complete inputs: idempotent, no second line
    assert (
        accept.main(
            ["--package", str(pkg), "--registry", str(reg), "--out", str(tmp_path / "again")]
        )
        == 0
    )
    assert len(registry.load(reg)) == 2
    assert read_json(tmp_path / "again" / "registration.json")["verdict"] == "idempotent"
    # anything else under the used identity (a changed delivery, new labels): refused,
    # and nothing is written
    monkeypatch.setattr(package, "check_package", _prod_check(real, res, inputs="0" * 64))
    with pytest.raises(SystemExit, match="refuses this decision"):
        accept.main(["--package", str(pkg), "--registry", str(reg), "--out", str(tmp_path / "x")])
    assert not (tmp_path / "x").exists() and len(registry.load(reg)) == 2


@pytest.mark.parametrize("damage", ["truncated", "missing", "alternate", "uncommitted"])
def test_r2_b2_registry_boundary_probe_now_refuses(pkg, tmp_path, monkeypatch, damage):  # noqa: F811
    # the audit's probe: verify_append_only failing, a nonexistent alternate registry; both
    # used to give status pass / verdict append. Now refused before any production step.
    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    res = _res(cand="c1", seed=5)
    reg = _canonical_registry(repo, [res, _dec(cand="c1", seed=5)])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reg")
    target = reg
    if damage == "truncated":
        reg.write_text(reg.read_text().splitlines()[0] + "\n")
    elif damage == "missing":
        reg.unlink()
    elif damage == "alternate":
        target = tmp_path / "fresh_registry.jsonl"
    else:
        _git(repo, "rm", "-q", "--cached", str(reg))
        _git(repo, "commit", "-q", "-m", "untrack")
    called = []
    monkeypatch.setattr(package, "check_package", lambda p: called.append(p))
    with pytest.raises(SystemExit, match="registry refused"):
        accept.main(
            ["--package", str(pkg), "--registry", str(target), "--out", str(tmp_path / "o")]
        )
    assert called == [] and not (tmp_path / "o").exists()


def test_r2_b2_register_terminal_has_the_same_integrity_checks(tmp_path, monkeypatch):
    from fixcheck import cli

    repo = _repo(tmp_path)
    monkeypatch.setattr(registry, "REPO", repo)
    reg = _canonical_registry(repo, [_res(), _dec()])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reg")
    other = tmp_path / "other.jsonl"
    other.write_text(reg.read_text())
    with pytest.raises(SystemExit, match="refused"):
        cli.main(
            [
                "register-terminal",
                "--outcome",
                "revert_0.3.3",
                "--basis",
                "x",
                "--registry",
                str(other),
            ]
        )
    with pytest.raises(SystemExit, match="refused"):  # 'ship' needs a pass
        cli.main(["register-terminal", "--outcome", "ship", "--basis", "x", "--registry", str(reg)])
    assert (
        cli.main(
            [
                "register-terminal",
                "--outcome",
                "revert_0.3.3",
                "--basis",
                "x",
                "--registry",
                str(reg),
            ]
        )
        == 0
    )
    assert registry.load(reg)[-1]["outcome"] == "revert_0.3.3"
    with pytest.raises(SystemExit, match="already registered"):
        cli.main(
            ["register-terminal", "--outcome", "amendment", "--basis", "x", "--registry", str(reg)]
        )


def test_r2_b2_concurrent_reservations_one_round_one_package(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    reg = _canonical_registry(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "empty registry")

    def make(res):
        return lambda entries: (*registry.check_reservation(entries, res), res)

    a = registry.atomic_append(reg, make(_res(seed=1, cdir="pkgA")), repo)
    b = registry.atomic_append(reg, make(_res(seed=2, cdir="pkgB")), repo)
    assert a[0] == "append" and b[0] == "refuse"
    assert any("parallel packages are refused" in p for p in b[1])
    assert [e["seed"] for e in registry.load(reg)] == [1]


def _round1_collected(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    assert _collect_r1(tmp_path, raw, dev_raw, extra=("--offline",)) == 0
    return dev_raw, raw, tmp_path / "r1"


def _r2_argv(tmp_path, raw, dev_raw, earlier, reg, out="r2", seed="778"):
    return [
        "--round",
        "2",
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
        "--plan-only",
        "--earlier",
        str(earlier),
        "--registry",
        str(reg),
    ]


def test_r2_b2_substituted_earlier_round_is_refused(tmp_path):
    dev_raw, raw, r1 = _round1_collected(tmp_path)
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    # a different, self-consistent directory labelled round 1
    fake = tmp_path / "fake_r1"
    shutil.copytree(r1, fake)
    texts = read_jsonl(fake / "texts.jsonl")
    write_jsonl(fake / "texts.jsonl", texts[1:])
    col = read_json(fake / "collection.json")
    col["texts_jsonl_sha256"] = sha256_file(fake / "texts.jsonl")
    write_json(fake / "collection.json", col)
    ex = read_json(fake / "execution.json")
    ex["collection_json_sha256"] = sha256_file(fake / "collection.json")
    write_json(fake / "execution.json", ex)
    from fixcheck.common import write_step_manifest

    write_step_manifest(
        fake,
        "collect",
        [
            fake / "freeze_record.json",
            fake / "texts.jsonl",
            fake / "collection.json",
            fake / "execution.json",
            *sorted((fake / "texts").glob("*.txt")),
        ],
    )
    assert collect.authenticate_collection(fake) == []  # self-consistent
    with pytest.raises(SystemExit, match="not the registered round 1"):
        collect.main(_r2_argv(tmp_path, raw, dev_raw, fake, reg))
    # the registered round 1 itself is accepted
    assert collect.main(_r2_argv(tmp_path, raw, dev_raw, r1, reg)) == 0


@pytest.mark.parametrize("history", ["round1_pass", "terminal", "none", "round2_reserved"])
def test_r2_b2_round2_collection_needs_the_registered_history(tmp_path, history):
    dev_raw, raw, r1 = _round1_collected(tmp_path)
    reg = _r1_registry(
        tmp_path / "reg.jsonl", r1, status="pass" if history == "round1_pass" else "inconclusive"
    )
    if history == "terminal":
        registry.append_unchecked(reg, {"type": "terminal", "outcome": "revert_0.3.3"})
    elif history == "none":
        reg.write_text("")
    elif history == "round2_reserved":
        registry.append_unchecked(reg, _res(rnd=2, cand=None, seed=990, cdir="elsewhere"))
    with pytest.raises(SystemExit):
        collect.main(_r2_argv(tmp_path, raw, dev_raw, r1, reg))
    assert not (tmp_path / "r2" / "freeze_record.json").exists()


def test_r2_b2_shared_texts_in_differently_serialised_manifests(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    t = {
        "source_id": "PMC123",
        "title": "A Title",
        "doi": "10.1/X",
        "url": "https://u/1",
        "fulltext_url": None,
        "source": "Europe PMC",
    }
    a.write_text(json.dumps(t, sort_keys=True) + "\n")
    b.write_text(
        json.dumps(dict(reversed(list(t.items()))))
        + "\n"
        + json.dumps(
            {
                "source_id": "PMC999",
                "title": "Other",
                "doi": None,
                "url": "https://u/2",
                "fulltext_url": None,
                "source": "Europe PMC",
            }
        )
        + "\n"
    )
    assert sha256_file(a) != sha256_file(b)  # different manifests ...
    ra, rb = package.source_refs_sha256(a), package.source_refs_sha256(b)
    assert set(ra) & set(rb)  # ... one shared canonical source identity
    r1res, r2res = _res(), _res(rnd=2, cand="c2", seed=2, cdir="r2")
    e = [r1res, _dec(refs=ra), r2res]
    d2 = _dec(rnd=2, cand="c2", seed=2, texts="t2", refs=rb, res=r2res, r1=e[1])
    v, probs = registry.check_decision(e, d2)
    assert v == "refuse" and any("disjoint" in p for p in probs)


# --- R2-B3: the delivery chain ----------------------------------------------------------


def test_r2_b3_unregistered_model_with_recomputed_hash_is_refused():
    spec = sessions.build_spec()
    bad = json.loads(json.dumps(spec))
    bad["roles"]["A"]["model"] = "UNREGISTERED"
    body = {k: v for k, v in bad.items() if k != "spec_sha256"}
    from fixcheck.common import sha256_text

    bad["spec_sha256"] = sha256_text(canonical_json(body))
    assert sessions.check_spec(spec) == []
    assert any("registered model routes" in p for p in sessions.check_spec(bad))


def test_r2_b3_ancestor_path_leak_is_refused():
    p = sessions.check_session_root(Path("/tmp/COMPLETE_MD-A_candidate/neutral/inbox"), None)
    assert p and any("COMPLETE_MD-A_candidate" in x for x in p)
    for leak in (
        "/tmp/x/v0.4.0/inbox",
        "/tmp/r2/inbox",
        "/tmp/fix040/inbox",
        "/tmp/sonnet/inbox",
        "/tmp/PH-B/inbox",
    ):
        assert sessions.path_problems(Path(leak)), leak


def test_r2_b3_one_session_for_every_delivery_is_refused(pkg, tmp_path):  # noqa: F811
    # the audit's patched-read probe, now on the bytes: one session id and one transcript
    # for every delivery of every role and stage
    P0 = _copy(pkg, tmp_path)
    tr = next((P0 / "sessions" / "primary").glob("deliveries.jsonl"))
    first = read_jsonl(tr)[0]
    for st in ("primary", "retry", "flash"):
        f = P0 / "sessions" / st / "deliveries.jsonl"
        recs = read_jsonl(f)
        for r in recs:
            r["session_id"] = "ONE_SESSION_ALL_ROLES_STAGES"
            r["transcript"] = first["transcript"]
            r["transcript_sha256"] = first["transcript_sha256"]
        write_jsonl(f, recs)
    probs, _ = package.check_labels(package.resolve(P0))
    real = _real(probs)
    assert any("session ids are used by more than one delivery" in p for p in real), real
    assert any("transcripts are used by more than one delivery" in p for p in real)


def test_r2_b3_absent_primary_role_is_never_delivered(pkg, tmp_path):  # noqa: F811
    # the audit's helper probe: remove every B session from the primary index and delivery
    # list and present an empty B first-pass file
    P0 = _copy(pkg, tmp_path)
    so = P0 / "sessions" / "primary"
    idx = read_json(so / "sessions_index.json")
    idx["sessions"] = [s for s in idx["sessions"] if s["role"] != "B"]
    write_json(so / "sessions_index.json", idx)
    toks = {s["token"] for s in idx["sessions"]}
    write_jsonl(
        so / "deliveries.jsonl",
        [d for d in read_jsonl(so / "deliveries.jsonl") if d["token"] in toks],
    )
    (P0 / "labels" / "B.pass1.jsonl").write_text("")
    P = package.resolve(P0)
    spec = read_json(
        Path(read_json(P0 / "collect" / "freeze_record.json")["bound"]["delivery_spec"]["path"])
    )
    res = sessions.check_stage(
        so, P0 / "labels" / "B.pass1.jsonl", "B", "primary", P["assign"], spec
    )
    n_b = sum(
        len(json.loads(x)["ids"])
        for x in [
            json.dumps(b)
            for b in read_json(P["assign"] / "batches" / "B" / "batch" / "batch_manifest.json")[
                "batches"
            ]
        ]
    )
    assert len(res["never_delivered"]["B"]) == n_b > 0
    assert any("expected session" in p and "missing" in p for p in res["problems"])


def test_r2_b3_substituted_session_material_and_symlink_are_refused(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    so = P0 / "sessions" / "primary"
    tok = read_json(so / "sessions_index.json")["sessions"][0]["token"]
    arch = so / "delivered" / tok
    g = arch / "guidelines.md"
    g.write_text(g.read_text() + "\nextra instruction\n")
    probs, _ = package.check_labels(package.resolve(P0))
    assert any("is not the spec's material" in p for p in _real(probs))
    # a symlink in place of an archived file
    g.unlink()
    g.symlink_to(sessions.MATERIALS["guidelines.md"])
    probs, _ = package.check_labels(package.resolve(P0))
    assert any("not a regular file" in p for p in _real(probs))


def test_r2_b3_spec_changed_after_the_freeze_is_refused(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    fr = read_json(P0 / "collect" / "freeze_record.json")
    spec_path = Path(fr["bound"]["delivery_spec"]["path"])
    copy = tmp_path / "spec_copy.json"
    shutil.copy(spec_path, copy)
    fr["bound"]["delivery_spec"]["path"] = str(copy)
    write_json(P0 / "collect" / "freeze_record.json", fr)
    spec = read_json(copy)
    spec["roles"]["A"]["settings"] = {"effort": "low"}
    write_json(copy, spec)
    probs, _ = package.check_labels(package.resolve(P0))
    assert any("bound delivery spec is missing or changed" in p for p in probs)


# --- R2-B5: derived facts recomputed from authenticated parents ---------------------------


def test_r2_b5_hand_round_shows_what_a_trusted_denominator_would_buy():
    # 10 censused unresolved span changes against 100 censused baseline successes ...
    cells = {X.SPAN_CHANGED: (10, {f"u{i}": (None, [(None, False)]) for i in range(10)})}

    def run(n_h):
        frames, bs, refs, configs = _round(
            cells, bs_md={"s1": (100, [1] * 100)}, bs_ph={"t1": (50, [1] * 50)}
        )
        bs["metadiscourse"]["s1"]["N_h"] = n_h  # ... with only the asserted N_h changed
        return accept.compute(frames, bs, refs, configs)["modules"]["metadiscourse"]

    a = run(100)
    assert a["cumulative"]["STRICT"]["fraction"] == pytest.approx(0.1)
    assert a["status"] == "inconclusive"
    b = run(10_000)
    assert b["cumulative"]["STRICT"]["fraction"] == pytest.approx(0.0010743446497636442)
    assert b["status"] == "pass"


def test_r2_b5_rehashed_population_size_is_caught(pkg, tmp_path):  # noqa: F811
    # the audit's probe: multiply every baseline-success N_h by 100 and recompute the
    # selection's manifest hash; the parents are unchanged
    P0 = _copy(pkg, tmp_path)
    sp = P0 / "sample" / "selection.json"
    sel = read_json(sp)
    for strata in sel["baseline_success"]["strata"].values():
        for d in strata.values():
            d["N_h"] *= 100
    write_json(sp, sel)
    man = read_json(P0 / "sample" / "manifest_sample.json")
    man["outputs"]["selection.json"]["sha256"] = sha256_file(sp)
    write_json(P0 / "sample" / "manifest_sample.json", man)
    assert package.check_manifest(P0 / "sample", "sample") == []  # hashes alone pass
    probs = package.check_sample(package.resolve(P0), {"seed": sel["round_seed"]})
    assert any("selection.json is not what its authenticated inputs derive" in p for p in probs)


def test_r2_b5_removed_manifest_entry_and_changed_source_or_environment(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    fr = read_json(P0 / "collect" / "freeze_record.json")
    d = P0 / "sample"
    req = ["selection.json", "units.jsonl", "decision_plan.json", "operational_power.json"]
    assert package.check_manifest(d, "sample", req, fr) == []
    man = read_json(d / "manifest_sample.json")
    del man["outputs"]["units.jsonl"]
    write_json(d / "manifest_sample.json", man)
    assert any("omits mandatory outputs" in p for p in package.check_manifest(d, "sample", req))
    man["outputs"]["units.jsonl"] = {"sha256": sha256_file(d / "units.jsonl"), "bytes": 0}
    man["sources_sha256"] = dict(man["sources_sha256"], **{"fixcheck/sampling.py": "0" * 64})
    write_json(d / "manifest_sample.json", man)
    assert any("harness sources differ" in p for p in package.check_manifest(d, "sample", req, fr))
    man["sources_sha256"] = fr["sources_sha256"]
    man["environment_sha256"] = "0" * 64
    write_json(d / "manifest_sample.json", man)
    assert any("runtime environment" in p for p in package.check_manifest(d, "sample", req, fr))


def test_r2_b5_stale_verification_is_caught(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    P = package.resolve(P0)
    cinfo = {"ledger": {"markdown": {"sha256": sha256_file(ledger.DRAFT_LEDGER_MD)}}}
    assert [p for p in package.check_verify(P, cinfo) if "manifest_verify" not in p] == []
    v = read_json(P0 / "verify" / "verify.json")
    v["stage_inputs"]["retry"] = ["0" * 64]  # verified another retry directory
    v["inputs"]["run_json_sha256"] = "0" * 64  # ... and another run
    write_json(P0 / "verify" / "verify.json", v)
    probs = package.check_verify(P, cinfo)
    assert any("retry directory" in p for p in probs)
    assert any("run_json_sha256" in p for p in probs)


def test_r2_b5_changed_delivery_with_same_labels_changes_the_identity(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    before = package.check_package(P0)["inputs_sha256"]
    f = P0 / "sessions" / "flash" / "deliveries.jsonl"
    recs = read_jsonl(f)
    recs[0]["access_review"] = "another review note"  # the labels are unchanged
    write_jsonl(f, recs)
    after = package.check_package(P0)["inputs_sha256"]
    assert after != before
    r1res = _res()
    e = [r1res, _dec(inputs=before)]
    assert registry.check_decision(e, _dec(inputs=after))[0] == "refuse"


def test_r2_b5_stage_receipt_mismatch_and_missing_archive(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    P = package.resolve(P0)
    idx = read_json(P0 / "sessions" / "primary" / "sessions_index.json")
    spec = Path(read_json(P0 / "collect" / "freeze_record.json")["bound"]["delivery_spec"]["path"])
    assert package.check_stage_receipt(P, "primary", idx, spec, False) == [
        f"primary: the stage receipt {UNARCHIVED}"
    ]
    probs = package.check_stage_receipt(P, "primary", idx, spec, True)
    assert any("no archive receipt" in p for p in probs)
    (P0 / "sample" / "decision_plan.json").write_text("{}\n")  # changed after the receipt
    probs = package.check_stage_receipt(P, "primary", idx, spec, False)
    assert any("sample changed since its pre-delivery receipt" in p for p in probs)


def test_r2_b5_export_refuses_a_receipt_that_is_not_the_package(pkg, tmp_path):  # noqa: F811
    P0 = _copy(pkg, tmp_path)
    rc = tmp_path / "receipt.json"
    assert (
        sessions.main_stage_receipt(["--package", str(P0), "--stage", "primary", "--out", str(rc)])
        == 0
    )
    (P0 / "assign" / "orders.json").write_text("{}\n")
    spec = Path(read_json(P0 / "collect" / "freeze_record.json")["bound"]["delivery_spec"]["path"])
    with pytest.raises(SystemExit, match="not the package's current primary state"):
        sessions.export(
            spec, "primary", P0 / "assign", sessions.fresh_root(), tmp_path / "o", P0, receipt=rc
        )
    with pytest.raises(SystemExit, match="outside every package part"):
        sessions.main_stage_receipt(
            ["--package", str(P0), "--stage", "primary", "--out", str(P0 / "run" / "r.json")]
        )


# --- R2-S2: dry-run resume identity -----------------------------------------------------


def _fake_snapshots(monkeypatch, state):
    def fake_cli(args):
        dest = Path(args[args.index("--dest") + 1])
        (dest / "lexinspect").mkdir(parents=True)
        write_json(
            dest / "CANDIDATE_SNAPSHOT.json",
            {
                "tree_sha256": state["digest"],
                "source": "commit" if state.get("commit") else "working_tree",
                "commit": state.get("commit"),
                "label": "interim",
                "n_files": 1,
            },
        )
        return 0

    monkeypatch.setattr(dryrun, "_cli", fake_cli)


def test_r2_s2_same_bytes_new_commit_does_not_resume(tmp_path, monkeypatch):
    state = {"digest": "a" * 64}
    _fake_snapshots(monkeypatch, state)
    out, key = dryrun.snapshot_and_key(tmp_path, None, None, False, settings={"plan_reps": 2})
    (out / "stage.json").write_text("{}")
    state["commit"] = "NEW_COMMIT"  # the audit's probe: identical bytes, a new commit
    with pytest.raises(SystemExit, match="refusing to resume"):
        dryrun.snapshot_and_key(tmp_path, out, "NEW_COMMIT", False, settings={"plan_reps": 2})
    k = read_json(out / "DRYRUN_KEY.json")
    assert k["commit"] is None and (out / "stage.json").exists()  # nothing rewritten
    snap = read_json(out / "candidate_src" / "CANDIDATE_SNAPSHOT.json")
    assert snap.get("commit") is None
    state.pop("commit")
    with pytest.raises(SystemExit, match="settings"):
        dryrun.snapshot_and_key(tmp_path, out, None, False, settings={"plan_reps": 3})
    monkeypatch.setattr(dryrun, "snapshot_and_key", dryrun.snapshot_and_key)
    from fixcheck import common

    real = common.source_hashes
    monkeypatch.setattr(common, "source_hashes", lambda: dict(real(), x="0"))
    with pytest.raises(SystemExit, match="harness_sha256"):
        dryrun.snapshot_and_key(tmp_path, out, None, False, settings={"plan_reps": 2})
    monkeypatch.setattr(common, "source_hashes", real)
    out2, k2 = dryrun.snapshot_and_key(tmp_path, out, None, False, settings={"plan_reps": 2})
    assert out2 == out and k2 == k  # an identical identity resumes
    with pytest.raises(SystemExit, match="fresh, unique"):
        dryrun.snapshot_and_key(tmp_path, out, None, False, settings={}, require_fresh=True)
    assert not list(tmp_path.glob(".snapshot-*"))


# --- R2-S3: replay of failures, rejected bodies and restored dates ------------------------


def _first_fetched_epmc(tmp_path) -> str:
    """The first Europe PMC body the seed-777 collection of the mock pools fetches."""
    dev_raw, raw = _mock_cache(tmp_path / "probe")
    assert _collect_r1(tmp_path / "probe", raw, dev_raw, extra=("--offline",)) == 0
    log = read_json(tmp_path / "probe" / "r1" / "collection.json")["fetch_log"]
    return next(f["cache"] for f in log if f["cache"].startswith("epmc/"))


def test_r2_s3_network_failure_is_replayed_without_a_request(tmp_path, monkeypatch):
    rel = _first_fetched_epmc(tmp_path)
    dev_raw, raw = _mock_cache(tmp_path)
    victim = raw / rel
    victim.unlink()  # uncached: the collection must fetch it, and the fetch fails
    calls = []

    def urlopen(*a, **k):
        calls.append(a)
        raise OSError("synthetic network failure")

    monkeypatch.setattr(build.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(build.time, "sleep", lambda s: None)
    rc = _collect_r1(tmp_path, raw, dev_raw)
    assert rc in (0, 2) and len(calls) == 4  # build.fetch's own four attempts, once
    col = read_json(tmp_path / "r1" / "collection.json")
    failed = [f for f in col["fetch_log"] if "error" in f]
    assert len(failed) == 1 and failed[0]["error_class"] == "RuntimeError"
    assert "synthetic network failure" in failed[0]["error_message"]
    assert any("fetch failed" in r["reason"] for r in col["selection_log"]["academic_rejected"])

    def forbidden(*a, **k):
        raise AssertionError("replay made a request")

    monkeypatch.setattr(build.urllib.request, "urlopen", forbidden)
    assert (
        collect.main(["--replay-round", str(tmp_path / "r1"), "--out", str(tmp_path / "rep")]) == 0
    )
    rep = read_json(tmp_path / "rep" / "replay.json")
    assert rep["identical"] and rep["logs_identical"] and rep["raw_responses_authenticated"]
    # the old comparison: an offline fetch at that path raises another error entirely
    with pytest.raises(collect.NetworkForbidden):
        collect._offline_fetch(failed[0]["url"], raw / failed[0]["cache"])
    # a body appearing later where the archive recorded a failure is not authentic
    victim.write_text("late")
    assert any("now exists" in p for p in collect.authenticate_raw(col, raw))


def test_r2_s3_successful_but_ineligible_body_is_authenticated(tmp_path):
    first = _first_fetched_epmc(tmp_path)
    dev_raw, raw = _mock_cache(tmp_path)
    rejected = raw / first
    rejected.write_text(_jats(rejected.stem, 1600, licence="by-nc"))
    assert _collect_r1(tmp_path, raw, dev_raw, extra=("--offline",)) in (0, 2)
    col = read_json(tmp_path / "r1" / "collection.json")
    rel = f"epmc/{rejected.name}"
    assert any(f["cache"] == rel and "sha256" in f for f in col["fetch_log"])
    assert any("licence" in r["reason"] for r in col["selection_log"]["academic_rejected"])
    assert collect.main(["--replay-round", str(tmp_path / "r1"), "--out", str(tmp_path / "a")]) in (
        0,
    )
    rejected.write_text(_jats(rejected.stem, 1600, licence="by"))  # now it would be eligible
    assert any(rel in p for p in collect.authenticate_raw(col, raw))
    with pytest.raises(SystemExit, match="do not authenticate"):
        collect.main(["--replay-round", str(tmp_path / "r1"), "--out", str(tmp_path / "b")])


def test_r2_s3_restored_mtime_is_a_metadata_difference_for_both_sources(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    assert _collect_r1(tmp_path, raw, dev_raw, extra=("--offline",)) == 0
    col = read_json(tmp_path / "r1" / "collection.json")
    by_src = {}
    for m in col["raw_files"]:
        by_src.setdefault(m["source"], m)
    assert set(by_src) == {"Europe PMC", "English Wikipedia"}
    old = 946684800  # 2000-01-01: a restored archive copy's file date
    for m in by_src.values():
        os.utime(raw / m["file"], (old, old))
    assert (
        collect.main(["--replay-round", str(tmp_path / "r1"), "--out", str(tmp_path / "rep")]) == 0
    )
    rep = read_json(tmp_path / "rep" / "replay.json")
    assert rep["identical"] and rep["text_reproducible"] and rep["archived_dates_consistent"]
    diffs = {d["text_id"]: d for d in rep["metadata_differences"]}
    for m in by_src.values():
        d = diffs[m["text_id"]]
        assert d["replayed"] == "2000-01-01" and d["archived"] in d["archived_ledger_date"]
    # an archived date that disagrees with the original fetch ledger is refused
    texts = read_jsonl(tmp_path / "r1" / "texts.jsonl")
    texts[0]["retrieved"] = "1999-12-31"
    write_jsonl(tmp_path / "r1" / "texts.jsonl", texts)
    c2 = dict(col, texts_jsonl_sha256=sha256_file(tmp_path / "r1" / "texts.jsonl"))
    write_json(tmp_path / "r1" / "collection.json", c2)
    collect.main(["--replay-round", str(tmp_path / "r1"), "--out", str(tmp_path / "rep2")])
    rep2 = read_json(tmp_path / "rep2" / "replay.json")
    assert not rep2["archived_dates_consistent"] and not rep2["identical"]


# --- R2-S5: defaults point to the tracked freeze location --------------------------------


def test_r2_s5_defaults_are_the_tracked_freeze_location():
    base = freeze.REPO / "docs" / "validation" / "study4-fix040"
    assert base / "round_registry.jsonl" == registry.REGISTRY
    assert base / "CANDIDATE_LEDGER.md" == ledger.LEDGER_MD
    assert base / "ledger_components.json" == ledger.LEDGER_COMPONENTS
    assert base / "delivery_spec.json" == collect.DELIVERY_SPEC
    assert base == freeze.FREEZE_DIR
    from fixcheck import verify

    assert verify.LEDGER_MD == ledger.LEDGER_MD
    assert accept.REG_DEFAULT == registry.REGISTRY


# --- R2-S4: power reporting -------------------------------------------------------------


@pytest.fixture(scope="module")
def power_round(tmp_path_factory):
    from fixcheck import power, sampling
    from fixcheck.test_fixcheck import _write_frames

    t = tmp_path_factory.mktemp("power")
    run_dir = t / "run"
    _write_frames(run_dir)
    assert X.main(["--run-dir", str(run_dir), "--out", str(t / "diff")]) == 0
    args = ["--run-dir", str(run_dir), "--diff-dir", str(t / "diff"), "--round-seed", "5"]
    args += ["--out", str(t / "sample"), "--plan-reps", "0", "--power-reps", "-1"]
    assert sampling.main(args) == 0
    sel = read_json(t / "sample" / "selection.json")
    pw = power.operational_power(
        run_dir, t / "diff", sel, 6, 11, lambdas=(0.0,), structures=("all_loss", "none_loss")
    )
    return run_dir, t / "diff", sel, pw


def test_r2_s4_module_calibrated_scenarios_report_target_and_realised_loss(power_round):
    from fixcheck import power

    *_, pw = power_round
    cal = {s["calibrated_variant"]: s for s in pw["scenarios"] if s["kind"] == "module_calibrated"}
    assert set(cal) == {"S8_definite", "S8_upper"}
    t = pw["assumptions"]["module_calibrated_targets"]
    assert (
        t["S8_definite"]["metadiscourse"]["INV"]["num"],
        t["S8_definite"]["metadiscourse"]["INV"]["den"],
    ) == (3, 690)
    assert (
        t["S8_definite"]["metadiscourse"]["STRICT"]["num"],
        t["S8_definite"]["metadiscourse"]["STRICT"]["den"],
    ) == (2, 621)
    assert (t["S8_definite"]["phrase"]["INV"]["num"], t["S8_definite"]["phrase"]["INV"]["den"]) == (
        1,
        202,
    )
    assert (
        t["S8_definite"]["phrase"]["STRICT"]["num"],
        t["S8_definite"]["phrase"]["STRICT"]["den"],
    ) == (1, 201)
    assert (
        t["S8_upper"]["metadiscourse"]["INV"]["num"],
        t["S8_upper"]["metadiscourse"]["STRICT"]["num"],
    ) == (31, 6)
    assert t["S8_upper"]["phrase"] == t["S8_definite"]["phrase"]
    # the exact numbers on the integration round (seed 11): target and realised kept apart
    d = cal["S8_definite"]["realised"]["metadiscourse"]
    assert d["target_lambda"] == {"INV": 3 / 690, "STRICT": 2 / 621}
    assert (d["target_losses_INV"], d["target_losses_STRICT"]) == (1, 1)
    assert d["true_losses"] == {"STRICT": 1, "INV": 1}
    assert d["baseline_successes"] == {"STRICT": 227, "INV": 250}
    u = cal["S8_upper"]["realised"]["metadiscourse"]
    assert (u["target_losses_INV"], u["target_losses_STRICT"]) == (11, 2)
    assert u["true_losses"] == {"STRICT": 2, "INV": 11}
    assert u["loss_fraction"]["INV"] == 11 / 258
    for s in cal.values():
        assert s["lambda"] is None and s["nominal_zero_with_realised_losses"] is False
        g = s["gates"]
        for k in ("ALL_REQUIRED_GATES_PASS", "metadiscourse|module_pass", "phrase|module_pass"):
            assert g[k]["reps"] == 6 and g[k]["wilson95"] == power.wilson(g[k]["k"], 6)
        assert any(k.endswith("|removal|COMPLETE") for k in g)
        assert any("|cumulative|" in k for k in g)


def test_r2_s4_nominal_zero_scenario_with_realised_losses_is_flagged(power_round):
    *_, pw = power_round
    grid = {s["unresolved_structure"]: s for s in pw["scenarios"] if s["kind"] == "lambda_grid"}
    a = grid["all_loss"]
    assert a["lambda"] == 0.0 and a["nominal_zero_with_realised_losses"] is True
    assert a["realised"]["metadiscourse"]["true_losses"] == {"STRICT": 8, "INV": 8}
    assert a["realised"]["metadiscourse"]["nominal_zero_with_realised_losses"] is True
    assert grid["none_loss"]["nominal_zero_with_realised_losses"] is False


def test_r2_s4_greedy_value_is_named_and_counted_not_called_a_best(power_round):
    *_, pw = power_round
    att = pw["attainable"]
    assert "greedy_best_cumulative" not in att
    g = att["greedy_search_feasible"]
    assert g["label"].startswith("a feasible value found by the declared greedy search")
    assert "not a certified optimum" in g["label"]
    for m in ("metadiscourse", "phrase"):
        r = g["result"][m]
        assert set(r["removal_sampled_successes"]) == set(r["removal_bounds"])
        for c in r["removal_sampled_successes"].values():
            assert 0 <= c["k_lo"] <= c["k_hi"] <= c["n"] <= c["N"]
        assert r["sampled_losses"]
    assert "inverse inference" in pw["reading"]
    from fixcheck import power

    doc = power.__doc__
    assert "best attainable value is at most" in doc and "greedy best" not in doc


def test_r2_s4_no_threshold_n_or_grid_change():
    from fixcheck import power, sampling

    assert sampling.PLAN_LOSS_FRACTIONS == (0.0, 0.005, 0.01, 0.02, 0.05)
    assert sampling.SRS_MAX == 200
    assert power.STRUCTURES == ("all_loss", "none_loss", "dev_share")
    assert (accept.CUMULATIVE_TOLERANCE, accept.REMOVAL_TOLERANCE) == (0.05, 0.15)


# --- R2-M1: the span rule on its own merits ------------------------------------------------


def test_r2_m1_overlapping_nonnested_pair_can_resolve():
    b = mk("x", (0, 6), "hedges", text="1")
    c = mk("x", (3, 9), "hedges", text="1", config="C")
    b = dict(b, head_span=[3, 4], raw={"marker": "may"})
    c = dict(c, head_span=[3, 4], raw={"marker": "may"})
    assert not X._nested(b["span"], c["span"])  # the old nesting predicate is false
    assert X.span_rule_holds(b, c)
    bl, _ = cw([b], [c])
    assert bl["B:x"]["change_type"] == X.SPAN_CHANGED and bl["B:x"]["resolved"] is True
