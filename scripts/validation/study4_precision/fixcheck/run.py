"""`run`, `prepare-pinned`, `verify-baseline`: full hit frames for every configuration.

Configurations (ledger "Order"): BASELINE = only([]) (0.3.3 behaviour),
COMPLETE = only(all twelve families), and each family alone, only([f]) (its
declared prerequisites are none). Each runs in its own process (worker.py) on
the identical archived text bytes of one round, in the uv environment of
`--checkout` (default: this repository).

Frozen candidate (audit r1 B1). `prepare-candidate --commit C` extracts
src/lexinspect from `git archive C` (never the working tree); its digest must
equal the commit's git-object digest (freeze.commit_src_digest), the checkout's
uv.lock must be the commit's, and the snapshot must import. Only such a
snapshot is production-eligible. `prepare-candidate --from-working-tree`
copies <checkout>/src/lexinspect instead (digest equal before, during and after
the copy; the copy must import) and is stamped "interim candidate digest",
production_eligible false: for dry runs only. `run --candidate-src DIR` then makes every
configuration import lexinspect from DIR, in the checkout's uv environment
(worker --import-root). Edits to the working tree during a run can then
reach no configuration. Without it, the checkout's src/ itself is run. That
requires a clean tree unless --allow-dirty is given, and the src/ digest is
taken before and after the workers: a change in between stops the run.

Verification of the baseline: does only([]) behave as 0.3.3? The pinned
0.3.3 code runs as configuration BASELINE_PINNED, in one of two ways:
- `run --pinned-src DIR` (used for the real candidate). DIR holds an archive
  of src/ at the pinned commit (default dec79bc), such as
  .cache/validation/study4_fix040/equivalence/baseline_033_src. It runs, as
  it is and with no toggle module, in the candidate checkout's uv
  environment (worker --import-root DIR). Before anything runs, two checks
  must pass (`pinned_src_record`):
  - every file of `git ls-tree -r <commit> src/lexinspect` is present in DIR
    with the same git blob hash, and DIR holds no other file (__pycache__
    ignored);
  - the checkout's uv.lock is byte-identical to the commit's, so the
    environment is the pinned one.
- `run --pinned-checkout DIR`: a full checkout of the commit, extracted by
  `prepare-pinned` with `git archive`, run in its own uv environment. Before
  anything runs (`pinned_checkout_record`, audit r1 B2): every file of `git
  ls-tree -r <commit>` is present in DIR with the same git blob hash and DIR
  holds no other file (the uv environment .venv, __pycache__ and
  PINNED_COMMIT.json ignored), so DIR's uv.lock, pyproject and sources are the
  commit's.
Either way the commit must resolve to the full pinned commit PINNED_FULL
(dec79bc0e642…); any other commit runs but is not production-eligible.

`verify-baseline` passes only if BASELINE (only([]) in the candidate) and
BASELINE_PINNED emit the same hit sequence, in the same order. A hit here is
its claim key, payload hash and raw hit record. The PHRASE lookup and the
polysemous-rank set must also be identical, and with --pinned-src the
source-tree and uv.lock checks above must hold too. Every difference is
listed.
"""

from __future__ import annotations

import argparse
import hashlib
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fixcheck import HERE, REPO
from fixcheck.common import (
    canonical_json,
    git_state,
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    write_json,
    write_step_manifest,
)
from fixcheck.ledger import BASELINE, COMPLETE, FAMILIES

PINNED_COMMIT = "dec79bc"
PINNED_FULL = "dec79bc0e642035d2ec686997b284da2ceadd11c"
INTERIM = "interim candidate digest (working-tree snapshot; production_eligible false)"
PINNED = "BASELINE_PINNED"


def all_configs() -> dict[str, list[str]]:
    """Configuration name -> families enabled."""
    out = {BASELINE: [], COMPLETE: list(FAMILIES)}
    out |= {f: [f] for f in FAMILIES}
    return out


def python_cmd(checkout: Path) -> list[str]:
    return ["uv", "run", "--project", str(checkout), "--frozen", "python", "-I"]


def worker_cmd(
    checkout: Path, round_dir: Path, config: str, fam_mod: str, enable: list[str], out: Path
) -> list[str]:
    return [
        *python_cmd(checkout),
        str(HERE / "worker.py"),
        "--texts",
        str(round_dir),
        "--config",
        config,
        "--families-module",
        fam_mod,
        "--enable",
        ",".join(enable),
        "--out",
        str(out),
    ]


def _run(cmd: list[str], env_extra: dict[str, str] | None, log: Path) -> int:
    import os

    env = dict(os.environ, **(env_extra or {}))
    with log.open("w", encoding="utf-8") as f:
        f.write(shlex.join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env).returncode


def compare_frames(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    """Equality of the (claim_key, payload_sha256, raw hit) sequences of two frames."""

    def sig(r: dict[str, Any]) -> str:
        return canonical_json([r["claim_key"], r["payload_sha256"], r["raw"]])

    sa, sb = list(map(sig, a)), list(map(sig, b))
    ca, cb = Counter(sa), Counter(sb)
    only_a = list((ca - cb).elements())
    only_b = list((cb - ca).elements())
    return {
        "n_a": len(a),
        "n_b": len(b),
        "identical": sa == sb,
        "same_multiset": not only_a and not only_b,
        "only_in_a": len(only_a),
        "only_in_b": len(only_b),
        "examples_only_in_a": only_a[:20],
        "examples_only_in_b": only_b[:20],
    }


def pinned_src_record(src: Path, commit: str, checkout: Path) -> dict[str, Any]:
    """Does `src` hold exactly src/lexinspect at `commit`, and is the checkout's uv.lock the commit's?"""

    def git(*a: str, text: bool = True) -> Any:
        return subprocess.run(
            ["git", "-C", str(REPO), *a], capture_output=True, text=text, check=True
        ).stdout

    full = git("rev-parse", f"{commit}^{{commit}}").strip()
    tree = {}
    for line in git("ls-tree", "-r", full, "--", "src/lexinspect").splitlines():
        meta, path = line.split("\t", 1)
        tree[path.removeprefix("src/")] = meta.split()[2]
    have = {
        str(p.relative_to(src)): p
        for p in sorted(src.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    problems = [f"missing {f}" for f in sorted(set(tree) - set(have))]
    problems += [f"extra {f}" for f in sorted(set(have) - set(tree))]
    for f in sorted(set(tree) & set(have)):
        blob = subprocess.run(
            ["git", "hash-object", str(have[f])], capture_output=True, text=True, check=True
        ).stdout.strip()
        if blob != tree[f]:
            problems.append(f"differs {f}")
    lock_commit = hashlib.sha256(git("show", f"{full}:uv.lock", text=False)).hexdigest()
    lock_checkout = sha256_file(checkout / "uv.lock") if (checkout / "uv.lock").exists() else None
    return {
        "method": "pinned source tree run in the candidate checkout's environment",
        "commit": full,
        "src": str(src),
        "n_files": len(tree),
        "tree_identical": not problems,
        "tree_problems": problems,
        "uv_lock_sha256_commit": lock_commit,
        "uv_lock_sha256_checkout": lock_checkout,
        "environment_identical": lock_commit == lock_checkout,
    }


PINNED_CHECKOUT_IGNORED = (".venv", "__pycache__", "PINNED_COMMIT.json")


def pinned_checkout_record(pc: Path, commit: str) -> dict[str, Any]:
    """Does the full checkout `pc` hold exactly the tree of `commit` (uv.lock included)?"""

    def git(*a: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True
        ).stdout

    full = git("rev-parse", f"{commit}^{{commit}}").strip()
    tree = {}
    for line in git("ls-tree", "-r", full).splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind == "blob":
            tree[path] = blob
    have = {
        str(p.relative_to(pc)): p
        for p in sorted(pc.rglob("*"))
        if (p.is_file() or p.is_symlink())
        and not any(x in PINNED_CHECKOUT_IGNORED for x in p.relative_to(pc).parts)
    }
    problems = [f"missing {f}" for f in sorted(set(tree) - set(have))]
    problems += [f"extra {f}" for f in sorted(set(have) - set(tree))]
    common = sorted(set(tree) & set(have))
    if common:
        blobs = subprocess.run(
            ["git", "hash-object", "--no-filters", "--stdin-paths"],
            input="".join(str(have[f]) + "\n" for f in common),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        problems += [f"differs {f}" for f, b in zip(common, blobs, strict=True) if b != tree[f]]
    return {
        "method": "full checkout of the pinned commit run in its own uv environment",
        "commit": full,
        "checkout": str(pc),
        "n_files": len(tree),
        "tree_identical": not problems,
        "tree_problems": problems[:50],
        "uv_lock_sha256_commit": tree.get("uv.lock"),
        "uv_lock_sha256_checkout": sha256_file(pc / "uv.lock")
        if (pc / "uv.lock").exists()
        else None,
        "environment_identical": not problems,
        "environment_note": "the checkout's uv.lock is the commit's (tree check); it runs with "
        "uv run --frozen in its own environment",
    }


def src_tree_digest(checkout: Path) -> dict[str, Any]:
    """SHA-256 of every file under <checkout>/src/lexinspect (__pycache__ ignored), and of
    the sorted (path, sha256) list: identifies the candidate code even in a dirty tree."""
    return pkg_digest(checkout / "src" / "lexinspect")


def pkg_digest(root: Path) -> dict[str, Any]:
    """The same digest for a lexinspect package directory `root`."""
    files = {
        str(p.relative_to(root)): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    return {
        "root": str(root),
        "n_files": len(files),
        "tree_sha256": hashlib.sha256(canonical_json(sorted(files.items())).encode()).hexdigest(),
        "files": files,
    }


def _import_probe(checkout: Path, dest: Path) -> subprocess.CompletedProcess:
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]); import lexinspect, lexinspect._fix_families;"
        "from pathlib import Path; assert Path(lexinspect.__file__).resolve()"
        ".is_relative_to(Path(sys.argv[1]).resolve()), lexinspect.__file__"
    )
    return subprocess.run(
        [*python_cmd(checkout), "-B", "-c", probe, str(dest)], capture_output=True, text=True
    )


def prepare_candidate_commit(checkout: Path, dest: Path, commit: str) -> dict[str, Any]:
    """Freeze the candidate from git objects: `git archive <commit> src/lexinspect`.

    Accepted only if the extracted digest equals the commit's git-object digest, the
    checkout's uv.lock equals the commit's, and the snapshot imports. Production-eligible."""
    from fixcheck import freeze

    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty")
    full = freeze.full_commit(commit)
    want = freeze.commit_src_digest(full)
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", full, "src/lexinspect"],
        capture_output=True,
        check=True,
    ).stdout
    tmp = dest / ".extract"
    tmp.mkdir()
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive, check=True)
    shutil.move(str(tmp / "src" / "lexinspect"), str(dest / "lexinspect"))
    shutil.rmtree(tmp)
    copy = pkg_digest(dest / "lexinspect")
    if copy["tree_sha256"] != want["tree_sha256"]:
        shutil.rmtree(dest / "lexinspect")
        raise SystemExit("the archived snapshot's digest differs from the commit's")
    lock_commit = hashlib.sha256(
        subprocess.run(
            ["git", "-C", str(REPO), "show", f"{full}:uv.lock"], capture_output=True, check=True
        ).stdout
    ).hexdigest()
    if lock_commit != sha256_file(checkout / "uv.lock"):
        shutil.rmtree(dest / "lexinspect")
        raise SystemExit("the checkout's uv.lock differs from the candidate commit's")
    r = _import_probe(checkout, dest)
    if r.returncode != 0:
        shutil.rmtree(dest / "lexinspect")
        raise SystemExit(f"the candidate snapshot does not import:\n{r.stderr[-2000:]}")
    rec = {
        "method": "git archive <commit> src/lexinspect; digest equal to the commit's git objects",
        "source": "commit",
        "commit": full,
        "commit_src_digest": want["tree_sha256"],
        "production_eligible": True,
        "checkout": str(checkout),
        "git": git_state(checkout),
        "tree_sha256": copy["tree_sha256"],
        "n_files": copy["n_files"],
        "files": copy["files"],
        "uv_lock_sha256": lock_commit,
        "import_check": "ok",
    }
    write_json(dest / "CANDIDATE_SNAPSHOT.json", rec)
    return rec


def prepare_candidate(checkout: Path, dest: Path) -> dict[str, Any]:
    """INTERIM (dry runs only): copy <checkout>/src/lexinspect into <dest>/lexinspect.

    The copy is accepted only if the source digest is the same before and after the copy,
    the copy's digest equals it, and the copy imports (with its toggle module) in the
    checkout's locked environment from <dest> itself. CANDIDATE_SNAPSHOT.json records
    the digest, every file hash, the git state and the uv.lock hash."""
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty")
    src = checkout / "src" / "lexinspect"
    before = pkg_digest(src)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest / "lexinspect", ignore=shutil.ignore_patterns("__pycache__"))
    after, copy = pkg_digest(src), pkg_digest(dest / "lexinspect")
    if not before["tree_sha256"] == after["tree_sha256"] == copy["tree_sha256"]:
        shutil.rmtree(dest / "lexinspect")
        raise SystemExit("candidate source changed while it was being copied; try again")
    r = _import_probe(checkout, dest)
    if r.returncode != 0:
        shutil.rmtree(dest / "lexinspect")
        raise SystemExit(f"the candidate snapshot does not import:\n{r.stderr[-2000:]}")
    rec = {
        "method": "copy of <checkout>/src/lexinspect; digest equal before, after and in the copy",
        "source": "working_tree",
        "label": INTERIM,
        "production_eligible": False,
        "checkout": str(checkout),
        "git": git_state(checkout),
        "tree_sha256": copy["tree_sha256"],
        "n_files": copy["n_files"],
        "files": copy["files"],
        "uv_lock_sha256": sha256_file(checkout / "uv.lock"),
        "import_check": "ok",
    }
    write_json(dest / "CANDIDATE_SNAPSHOT.json", rec)
    return rec


def verify_baseline(run_dir: Path) -> dict[str, Any]:
    a = read_jsonl(run_dir / "frames" / f"{BASELINE}.hits.jsonl")
    b = read_jsonl(run_dir / "frames" / f"{PINNED}.hits.jsonl")
    res = compare_frames(a, b)
    res["frames_identical"] = res["identical"]
    res["a"] = f"{BASELINE} (only([]) in the candidate checkout)"
    res["b"] = f"{PINNED} (pinned 0.3.3 code, no toggle module)"
    meta_a = read_json(run_dir / "frames" / f"{BASELINE}.meta.json")
    meta_b = read_json(run_dir / "frames" / f"{PINNED}.meta.json")
    res["meta_a"], res["meta_b"] = meta_a, meta_b
    problems = [] if res["identical"] else ["hit sequences differ"]
    for k in (
        "phrase_lookup_sha256",
        "phrase_inventory_sha256",
        "polysemous_ranks",
        "texts_jsonl_sha256",
        "n_texts",
    ):
        if meta_a.get(k) != meta_b.get(k):
            problems.append(f"{k} differs")
    pinned = run_dir / "pinned.json"
    if pinned.exists():
        res["pinned"] = read_json(pinned)
        if res["pinned"].get("tree_identical") is False:
            problems.append("pinned source tree differs from the commit")
        if res["pinned"].get("environment_identical") is False:
            problems.append("checkout uv.lock differs from the commit's")
        if res["pinned"].get("commit") != PINNED_FULL:
            problems.append(f"pinned commit {res['pinned'].get('commit')} is not {PINNED_FULL}")
        if "tree_identical" not in res["pinned"]:
            problems.append("pinned code was not verified against the commit")
    else:
        problems.append("no pinned.json: the pinned code was not verified")
    res["problems"] = problems
    res["identical"] = not problems
    return res


def prepare_pinned(commit: str, dest: Path) -> dict[str, Any]:
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty")
    full = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"{full}^{{tree}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", full], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    rec = {
        "commit": full,
        "tree": tree,
        "dest": str(dest),
        "method": "git archive <commit> | tar -x",
        "uv_lock_sha256": sha256_file(dest / "uv.lock") if (dest / "uv.lock").exists() else None,
    }
    write_json(dest / "PINNED_COMMIT.json", rec)
    return rec


def main(argv: list[str]) -> int:
    set_command("run", argv)
    ap = argparse.ArgumentParser(prog="fixcheck run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--round-dir", type=Path, required=True, help="collection dir")
    ap.add_argument("--out", type=Path, required=True, help="run dir")
    ap.add_argument("--checkout", type=Path, default=REPO)
    ap.add_argument("--families-module", default="lexinspect._fix_families")
    ap.add_argument("--configs", default="all", help="comma-separated, or 'all'")
    ap.add_argument("--pinned-checkout", type=Path, help="full checkout of the pinned commit")
    ap.add_argument("--pinned-src", type=Path, help="archive of src/ at the pinned commit")
    ap.add_argument("--pinned-commit", default=PINNED_COMMIT)
    ap.add_argument(
        "--candidate-src",
        type=Path,
        help="frozen candidate snapshot (prepare-candidate): every configuration imports "
        "lexinspect from it, in the checkout's environment",
    )
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--allow-shortfall", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true", help="candidate checkout src/ dirty")
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for workers (repeat)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    round_dir, out = args.round_dir.resolve(), args.out.resolve()
    col_path = round_dir / "collection.json"
    col = read_json(col_path) if col_path.exists() else None
    if col is not None:
        if col["status"] != "complete" and not args.allow_shortfall:
            raise SystemExit(f"round has status {col['status']}: pass --allow-shortfall to run it")
        if sha256_file(round_dir / "texts.jsonl") != col["texts_jsonl_sha256"]:
            raise SystemExit("texts.jsonl does not match collection.json")
    refuse_existing(out / "run.json", args.overwrite)
    configs = all_configs()
    if args.configs != "all":
        want = args.configs.split(",")
        configs = {c: configs[c] for c in want}
    checkout = args.checkout.resolve()
    gs = git_state(checkout)
    cand = args.candidate_src.resolve() if args.candidate_src else None
    snapshot = None
    if cand is not None:
        snapshot = read_json(cand / "CANDIDATE_SNAPSHOT.json")
        if pkg_digest(cand / "lexinspect")["tree_sha256"] != snapshot["tree_sha256"]:
            raise SystemExit(f"{cand} no longer matches its CANDIDATE_SNAPSHOT.json")
        if snapshot["uv_lock_sha256"] != sha256_file(checkout / "uv.lock"):
            raise SystemExit("the checkout's uv.lock differs from the snapshot's")
    elif gs["src_dirty"] and not args.allow_dirty:
        raise SystemExit(
            f"candidate checkout src/ has uncommitted changes: {gs['src_dirty_paths']}"
        )

    def cand_digest() -> dict[str, Any]:
        return pkg_digest(cand / "lexinspect") if cand is not None else src_tree_digest(checkout)

    env_extra = dict(e.split("=", 1) for e in args.env)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    extra = ["--import-root", str(cand)] if cand is not None else []
    jobs: list[tuple[str, list[str]]] = [
        (c, [*worker_cmd(checkout, round_dir, c, args.families_module, en, out / "frames"), *extra])
        for c, en in configs.items()
    ]
    pinned_rec = None
    if args.pinned_checkout and args.pinned_src:
        raise SystemExit("give --pinned-checkout or --pinned-src, not both")
    if args.pinned_src:
        ps = args.pinned_src.resolve()
        pinned_rec = pinned_src_record(ps, args.pinned_commit, checkout)
        if not (pinned_rec["tree_identical"] and pinned_rec["environment_identical"]):
            write_json(out / "pinned.json", pinned_rec)
            raise SystemExit(
                f"pinned source or environment is not the commit's: {out / 'pinned.json'}"
            )
        cmd = worker_cmd(checkout, round_dir, PINNED, "none", [], out / "frames")
        jobs.append((PINNED, [*cmd, "--import-root", str(ps)]))
        write_json(out / "pinned.json", pinned_rec)
    if args.pinned_checkout:
        pc = args.pinned_checkout.resolve()
        pinned_rec = pinned_checkout_record(pc, args.pinned_commit)
        write_json(out / "pinned.json", pinned_rec)
        if not pinned_rec["tree_identical"]:
            raise SystemExit(f"pinned checkout is not the commit's tree: {out / 'pinned.json'}")
        jobs.append((PINNED, worker_cmd(pc, round_dir, PINNED, "none", [], out / "frames")))
    src_before = cand_digest()
    # The first job alone (lets uv prepare the environment once), then the rest in parallel.
    rc = {}
    first, rest = jobs[0], jobs[1:]
    rc[first[0]] = _run(first[1], env_extra, out / "logs" / f"{first[0]}.log")
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {c: ex.submit(_run, cmd, env_extra, out / "logs" / f"{c}.log") for c, cmd in rest}
        rc |= {c: f.result() for c, f in futs.items()}
    failed = {c: r for c, r in rc.items() if r != 0}
    if failed:
        raise SystemExit(f"worker failures {failed}; see {out / 'logs'}")
    src_after = cand_digest()
    if src_after["tree_sha256"] != src_before["tree_sha256"]:
        changed = sorted(
            f
            for f in set(src_before["files"]) | set(src_after["files"])
            if src_before["files"].get(f) != src_after["files"].get(f)
        )
        raise SystemExit(f"candidate source changed while the configurations ran: {changed}")
    metas = {c: read_json(out / "frames" / f"{c}.meta.json") for c, _ in jobs}
    if cand is not None:
        wrong = [c for c in configs if metas[c]["import_root"] != str(cand)]
        if wrong:
            raise SystemExit(f"configurations {wrong} did not import the candidate snapshot")
    texts_hashes = {m["texts_jsonl_sha256"] for m in metas.values()}
    if len(texts_hashes) != 1:
        raise SystemExit("configurations ran on different texts.jsonl files")
    warnings = []
    lookups = {c: m["phrase_lookup_sha256"] for c, m in metas.items()}
    if len(set(lookups.values())) > 1:
        warnings.append(f"PHRASE list lookup differs between configurations: {lookups}")
    record: dict[str, Any] = {
        "round_dir": str(round_dir),
        "collection_sha256": sha256_file(col_path) if col else None,
        "texts_jsonl_sha256": texts_hashes.pop(),
        "checkout": str(checkout),
        "checkout_git": gs,
        "checkout_src": src_before,
        "candidate_src": str(cand) if cand is not None else None,
        "candidate_snapshot": snapshot,
        "checkout_uv_lock_sha256": sha256_file(checkout / "uv.lock")
        if (checkout / "uv.lock").exists()
        else None,
        "families_module": args.families_module,
        "configs": configs,
        "commands": {c: shlex.join(cmd) for c, cmd in jobs},
        "worker_env": env_extra,
        "metas": metas,
        "warnings": warnings,
        "allow_shortfall": args.allow_shortfall,
    }
    files = [out / "frames" / f"{c}.{s}" for c, _ in jobs for s in ("hits.jsonl", "meta.json")]
    if pinned_rec is not None:
        files.append(out / "pinned.json")
    if args.pinned_checkout or args.pinned_src:
        vb = verify_baseline(out)
        write_json(out / "verify_baseline.json", vb)
        files.append(out / "verify_baseline.json")
        record["verify_baseline_identical"] = vb["identical"]
        print(f"verify-baseline: identical={vb['identical']} {vb['problems']}", file=sys.stderr)
    reasons = []
    if col is None or not col.get("production_eligible", False):
        reasons.append("collection is not production-eligible")
    if snapshot is None:
        reasons.append("no frozen candidate snapshot (--candidate-src)")
    elif not snapshot.get("production_eligible", False):
        reasons.append(f"candidate snapshot: {snapshot.get('label', 'not from a commit')}")
    elif col is not None and (col.get("candidate") or {}).get("commit") != snapshot.get("commit"):
        reasons.append("candidate snapshot commit differs from the collection's frozen commit")
    elif col is not None and col["candidate"].get("tree_sha256") != snapshot.get("tree_sha256"):
        reasons.append("candidate snapshot digest differs from the collection's frozen digest")
    if not record.get("verify_baseline_identical", False):
        reasons.append("pinned baseline not verified identical")
    if args.configs != "all":
        reasons.append("not every configuration ran")
    if args.allow_dirty or args.allow_shortfall or env_extra:
        reasons.append("--allow-dirty / --allow-shortfall / --env used")
    record["production_eligible"] = not reasons
    record["ineligible_reasons"] = reasons
    write_json(out / "run.json", record)
    files.append(out / "run.json")
    write_step_manifest(out, "run", files)
    return 0 if record.get("verify_baseline_identical", True) else 1


def main_prepare_pinned(argv: list[str]) -> int:
    set_command("prepare-pinned", argv)
    ap = argparse.ArgumentParser(prog="fixcheck prepare-pinned")
    ap.add_argument("--commit", default=PINNED_COMMIT)
    ap.add_argument("--dest", type=Path, required=True)
    args = ap.parse_args(argv)
    rec = prepare_pinned(args.commit, args.dest.resolve())
    print(f"pinned {rec['commit']} at {rec['dest']}")
    return 0


def main_verify(argv: list[str]) -> int:
    set_command("verify-baseline", argv)
    ap = argparse.ArgumentParser(prog="fixcheck verify-baseline")
    ap.add_argument("--run-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    vb = verify_baseline(args.run_dir.resolve())
    write_json(args.run_dir / "verify_baseline.json", vb)
    print(f"identical={vb['identical']} ({vb['n_a']} vs {vb['n_b']} hits)")
    return 0 if vb["identical"] else 1


def main_prepare_candidate(argv: list[str]) -> int:
    set_command("prepare-candidate", argv)
    ap = argparse.ArgumentParser(prog="fixcheck prepare-candidate")
    ap.add_argument("--checkout", type=Path, default=REPO)
    ap.add_argument("--dest", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--commit", help="candidate commit: snapshot from git archive (production)")
    g.add_argument(
        "--from-working-tree",
        action="store_true",
        help="copy the working tree's src/ (interim candidate digest; not production-eligible)",
    )
    args = ap.parse_args(argv)
    if args.commit:
        rec = prepare_candidate_commit(args.checkout.resolve(), args.dest.resolve(), args.commit)
    else:
        rec = prepare_candidate(args.checkout.resolve(), args.dest.resolve())
    print(f"candidate snapshot {rec['tree_sha256'][:16]} ({rec['n_files']} files) at {args.dest}")
    return 0
