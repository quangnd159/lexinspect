"""The production freeze record of one fix-check round, and its local archive receipt.

Audit r1 B1 (HARNESS_AUDIT_R1_DISPOSITIONS.md). A round has two steps:

1. `collect --plan-only` writes the immutable round package `freeze_record.json`
   and `command.txt` (the literal execution command). Nothing is fetched.
2. `collect --execute --freeze-record <path>` recomputes every bound input from
   its own invocation and refuses on any difference before the first fetch.

The freeze record binds:
- the literal execution argv (the planning argv with the planning flag replaced
  by `--execute --freeze-record <path>`), the numeric round and seed;
- the full pool inventory (every development pool listing, with SHA-256);
- the cache and fetch-failure policy, and the initial inventory of the round's
  download cache (after the pool snapshot was copied in);
- the canonical development manifest identity and every earlier round's
  identities (texts.jsonl, collection.json and freeze record hashes);
- the candidate: full commit id and the SHA-256 tree digest of
  src/lexinspect at that commit (read from git objects, never the working tree);
- the environment: uv.lock hash, the Python build, and the installed files of
  numpy, scipy, spaCy, thinc, the model package and lexinspect, with the source
  digest of the lexinspect the interpreter imports (production acceptance must
  observe the same identity afresh, audit r3 S3);
- the candidate ledger: CANDIDATE_LEDGER.md hash and DRAFT status, and the
  `ledger_components.json` hash (its content must equal ledger.ledger_document());
- the protocol and its clarifications file;
- the SHA-256 of every harness and frozen Study 4 source;
- for round 2: the round registry, the registered round-1 entry and the reviewed
  narrowing disposition, with its status, tracking state and whether it names the
  candidate and the narrowing check; the narrowing check (the final dry run's
  NARROWING_CHECK.json, narrowing.py) with its validation problems; the tracking state of
  the ledger and its components; the candidate's src/lexinspect changes against round 1's
  and the harness files changed since round 1 (round-2 rulings G2, G4 and G10,
  docs/validation/study4-fix040/round2/HARNESS_ROUND2_RULINGS.md).

Production execution additionally requires, before any fetch (`execution_gate`):
- a clean tracked working tree whose HEAD descends from the candidate commit,
  with src/lexinspect byte-equal to the candidate commit's;
- the canonical round registry (registry.py), intact and committed, holding this
  round's reservation (audit r2 B2);
- the archive receipt (`archive_receipt`, audit r2 B1): every bound file (the
  freeze record, command.txt, the plan manifest, the ledger and its components,
  the protocol and clarifications, the preregistration, the delivery spec, the
  registry, the dispositions and rulings, every harness and frozen source file, and for
  round 2 the narrowing disposition and the narrowing check)
  is committed at HEAD (byte-equal to `git cat-file blob HEAD:<path>`), and HEAD
  is an ancestor of the registered remote-tracking ref. Only a full ref
  `refs/remotes/origin/<branch>` is accepted (round 1:
  `refs/remotes/origin/study4-fix040-candidate`); HEAD, local branches, tags,
  raw object ids, abbreviations and revision expressions are refused. The
  receipt records the canonical ref, the commit it resolves to and `git remote
  get-url origin`. Only local git objects, refs and configuration are read; there
  is no network call, so the receipt is only as current as the remote-tracking
  ref, which `git push` (or `git fetch`) updates. `verify_receipt` re-validates an
  archived receipt against the committed objects later (package checks); the
  append-only registry is checked as an extension of its receipted version
  (audit r3 S1).

Dry-run records (`--dry-run`) skip the production prerequisites and are stamped
`production_eligible: false`; nothing downstream accepts them as a decision.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

from fixcheck import HERE, REPO, STUDY4
from fixcheck.common import (
    FROZEN_INPUTS,
    canonical_json,
    read_json,
    sha256_file,
)

FREEZE_KIND = "fixcheck-freeze-record"
FREEZE_VERSION = 2
PROTOCOL = REPO / "docs" / "validation" / "study4-fix-protocol.md"
CLARIFICATIONS = REPO / "docs" / "validation" / "study4-fix-protocol-clarifications.md"
PREREG = REPO / "docs" / "validation" / "study4-preregistration.md"
FREEZE_DIR = REPO / "docs" / "validation" / "study4-fix040"
RECEIPT_REMOTE = "origin"
ROUND1_RECEIPT_REF = "refs/remotes/origin/study4-fix040-candidate"
DEFAULT_REMOTE_REF = ROUND1_RECEIPT_REF
REGISTERED_RECEIPT_REF = ROUND1_RECEIPT_REF
_RECEIPT_REF = re.compile(r"refs/remotes/origin/[A-Za-z0-9][A-Za-z0-9._/-]*")
FETCH_FAILURE_POLICY = (
    "Article and page bodies not in the round's cache are fetched once through build.fetch "
    "(its own four attempts with back-off). A body that still fails is a rejection recorded "
    "in the selection log and the fetch log; it is never retried later, refreshed or "
    "replaced by hand. Pool listings are never re-queried (PoolRequeryForbidden)."
)
# Receipted files that legitimately grow after the receipt (audit r3 S1): the canonical
# append-only round registry. Every other receipted file is immutable (exact bytes).
APPEND_ONLY_RECEIPTED = ("docs/validation/study4-fix040/round_registry.jsonl",)
# Fields that differ legitimately between the plan and its execution.
VOLATILE = ("planned_at", "planned_by")


class FreezeError(SystemExit):
    pass


def git(*args: str, repo: Path = REPO, text: bool = True, check: bool = True) -> Any:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=text)
    if check and r.returncode != 0:
        err = r.stderr if text else r.stderr.decode(errors="replace")
        raise FreezeError(f"git {' '.join(args)} failed: {err.strip()}")
    return r


def full_commit(commit: str, repo: Path = REPO) -> str:
    return git("rev-parse", "--verify", f"{commit}^{{commit}}", repo=repo).stdout.strip()


def commit_src_digest(commit: str, repo: Path = REPO, sub: str = "src/lexinspect") -> dict:
    """The candidate digest of `sub` at `commit`, read from git objects only.

    Same construction as run.pkg_digest: SHA-256 of canonical JSON of the sorted
    (path relative to `sub`, file SHA-256) list."""
    full = full_commit(commit, repo)
    files: dict[str, str] = {}
    for line in git("ls-tree", "-r", full, "--", sub, repo=repo).stdout.splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind != "blob":
            continue
        data = git("cat-file", "blob", blob, repo=repo, text=False).stdout
        rel = path[len(sub) + 1 :]
        if "__pycache__" in Path(rel).parts:
            continue
        files[rel] = hashlib.sha256(data).hexdigest()
    return {
        "commit": full,
        "root": sub,
        "n_files": len(files),
        "tree_sha256": hashlib.sha256(canonical_json(sorted(files.items())).encode()).hexdigest(),
        "files": files,
    }


def tracked_changes(repo: Path = REPO) -> list[str]:
    out = git("status", "--porcelain", "--untracked-files=no", repo=repo).stdout
    return [line for line in out.splitlines() if line.strip()]


def receipt_ref_problems(ref: str, repo: Path = REPO) -> tuple[str | None, list[str]]:
    """(commit, problems) for a candidate receipt ref (audit r2 B1).

    Accepted: exactly an existing full ref refs/remotes/origin/<branch>. Refused:
    HEAD, local branches, tags, raw object ids, abbreviated names, revision
    expressions (~ ^ @ : ..), and a branch called HEAD."""
    if not _RECEIPT_REF.fullmatch(ref or ""):
        return None, [
            f"receipt ref {ref!r} is not a full remote-tracking ref refs/remotes/origin/<branch> "
            "(HEAD, local branches, tags, object ids and revision expressions are refused)"
        ]
    if ".." in ref or "//" in ref or ref.endswith((".lock", "/")) or ref.endswith("/HEAD"):
        return None, [f"receipt ref {ref!r} is not a plain branch ref"]
    out = git(
        "for-each-ref",
        "--format=%(refname)%00%(objectname)%00%(objecttype)%00%(symref)",
        "refs/remotes/origin/",
        repo=repo,
        check=False,
    ).stdout
    refs = {}
    for line in out.splitlines():
        name, obj, kind, symref = line.split("\0")
        refs[name] = (obj, kind, symref)
    if ref not in refs:
        return None, [f"remote-tracking ref {ref} not found locally (push the branch first)"]
    obj, kind, symref = refs[ref]
    if symref or kind != "commit":
        return None, [f"receipt ref {ref} is a symbolic ref or not a commit"]
    return obj, []


def remote_url(repo: Path = REPO) -> str | None:
    r = git("remote", "get-url", RECEIPT_REMOTE, repo=repo, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def _rel(p: Path, repo: Path) -> str | None:
    try:
        return Path(p).resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return None


def archive_receipt(
    paths: list[Path], repo: Path = REPO, remote_ref: str = DEFAULT_REMOTE_REF
) -> dict[str, Any]:
    """Local-only proof that `paths` are committed at HEAD and HEAD is on the receipt ref."""
    problems: list[str] = []
    head = git("rev-parse", "--verify", "HEAD^{commit}", repo=repo).stdout.strip()
    remote, rp = receipt_ref_problems(remote_ref, repo)
    problems += rp
    url = remote_url(repo)
    if url is None:
        problems.append(f"no remote {RECEIPT_REMOTE!r} is configured")
    if remote is not None:
        anc = git("merge-base", "--is-ancestor", head, remote, repo=repo, check=False)
        if anc.returncode != 0:
            problems.append(f"HEAD {head[:12]} is not on {remote_ref} ({remote[:12]}): push it")
    files = {}
    for p in sorted({Path(x).resolve() for x in paths}):
        rel = _rel(p, repo)
        if rel is None:
            problems.append(f"{p} is outside the repository; it cannot be archived there")
            continue
        blob = git("cat-file", "blob", f"{head}:{rel}", repo=repo, text=False, check=False)
        if blob.returncode != 0:
            problems.append(f"{rel} is not committed at HEAD")
            files[rel] = {"committed": False}
            continue
        same = p.exists() and p.read_bytes() == blob.stdout
        if not same:
            problems.append(f"{rel} differs from its committed version at HEAD")
        files[rel] = {
            "committed": True,
            "byte_equal": same,
            "sha256": hashlib.sha256(blob.stdout).hexdigest(),
        }
    return {
        "method": "local git only: git cat-file blob <HEAD>:<path>; git merge-base "
        "--is-ancestor <HEAD> <receipt ref>; git for-each-ref; git remote get-url; no network",
        "note": "as current as the local remote-tracking ref (updated by git push / git fetch)",
        "head": head,
        "remote": RECEIPT_REMOTE,
        "remote_url": url,
        "remote_ref": remote_ref,
        "remote_commit": remote,
        "files": files,
        "problems": problems,
        "ok": not problems,
    }


def verify_receipt(
    receipt: dict[str, Any] | None, repo: Path | None = None, want: list[Path] | None = None
) -> list[str]:
    """Re-validate an archived receipt against committed objects (not its own boolean).

    The receipt's commit must still be on its receipt ref, each listed file must be
    that commit's blob (by SHA-256), and every path in `want` must be listed. Immutable
    inputs must still be byte-equal on disk. The canonical round registry is append-only
    (audit r3 S1): the receipt authenticates its committed blob as a HISTORICAL PREFIX, and
    the registry now on disk must extend that prefix byte for byte and pass the current
    integrity, history and rule checks (registry.extension_problems); a legitimate later
    reservation, decision or terminal line therefore does not invalidate the receipt, while
    a rewritten, truncated or non-prefix registry still does. `repo` defaults to this
    module's REPO at call time."""
    repo = REPO if repo is None else repo
    if not receipt:
        return ["no archive receipt"]
    p = list(receipt.get("problems") or [])
    if not receipt.get("ok") or p:
        return [*p, "the archived receipt did not hold when it was made"]
    head = receipt.get("head") or ""
    if git("cat-file", "-e", f"{head}^{{commit}}", repo=repo, check=False).returncode != 0:
        return [f"receipt commit {head[:12]} is not in the repository"]
    remote, rp = receipt_ref_problems(receipt.get("remote_ref", ""), repo)
    if rp:
        return rp
    if git("merge-base", "--is-ancestor", head, remote, repo=repo, check=False).returncode:
        p.append(f"receipt commit {head[:12]} is no longer on {receipt['remote_ref']}")
    if receipt.get("remote_url") != remote_url(repo):
        p.append("the origin remote URL differs from the receipt's")
    files = receipt.get("files") or {}
    for rel, f in sorted(files.items()):
        blob = git("cat-file", "blob", f"{head}:{rel}", repo=repo, text=False, check=False)
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != f.get("sha256"):
            p.append(f"{rel}: not the committed blob named by the receipt")
            continue
        cur = repo / rel
        if rel in APPEND_ONLY_RECEIPTED:
            from fixcheck import registry as REG

            p += [f"{rel}: {x}" for x in REG.extension_problems(cur, blob.stdout, repo)]
            continue
        if not cur.exists() or cur.read_bytes() != blob.stdout:
            p.append(f"{rel}: changed since the receipt")
    for w in want or []:
        rel = _rel(Path(w), repo)
        if rel is None or rel not in files:
            p.append(f"{w}: not covered by the receipt")
    return p


def cache_inventory(root: Path) -> dict[str, Any]:
    files = []
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                files.append(
                    {
                        "file": p.relative_to(root).as_posix(),
                        "sha256": sha256_file(p),
                        "bytes": p.stat().st_size,
                    }
                )
    return {
        "root": str(root),
        "n_files": len(files),
        "sha256": hashlib.sha256(canonical_json(files).encode()).hexdigest(),
        "files": files,
    }


def pool_inventory(dev_raw: Path) -> list[dict[str, Any]]:
    src = dev_raw / "pools"
    if not src.is_dir():
        raise FreezeError(f"pool snapshot source {src} not found")
    return [
        {"file": f"pools/{f.name}", "sha256": sha256_file(f), "bytes": f.stat().st_size}
        for f in sorted(src.glob("*.json"))
    ]


def dist_digest(dist: str) -> dict[str, Any] | None:
    """SHA-256 of every installed file of one distribution (RECORD list; bytecode ignored)."""
    try:
        d = importlib.metadata.distribution(dist)
    except importlib.metadata.PackageNotFoundError:
        return None
    files = []
    for f in d.files or []:
        p = Path(str(f.locate()))
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            files.append((str(f), sha256_file(p)))
    files.sort()
    direct = d.read_text("direct_url.json")
    return {
        "version": d.version,
        "n_files": len(files),
        "files_sha256": hashlib.sha256(canonical_json(files).encode()).hexdigest(),
        "direct_url": direct.strip() if direct else None,
    }


# Installed distributions whose file hashes are part of the runtime identity: the numerical
# dependencies (numpy, imported by the frozen estimators.py; scipy, recorded as absent or
# present), the parser and its model, and the installed lexinspect distribution (audit r2
# B5, audit r3 S3). test_r6 checks that the acceptance path imports no other third-party
# distribution.
ARTIFACT_DISTS = ("numpy", "scipy", "spacy", "en_core_web_sm", "thinc", "lexinspect")
# Imported at interpreter start-up by a .pth hook (setuptools' distutils shim), not by code.
STARTUP_ONLY_MODULES = ("_distutils_hack",)


def lexinspect_source_root() -> Path | None:
    """The directory of the lexinspect package this interpreter would import (find_spec,
    no import)."""
    import importlib.util

    spec = importlib.util.find_spec("lexinspect")
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent


def lexinspect_source_identity() -> dict[str, Any] | None:
    """The source digest of the lexinspect package this interpreter imports (an editable
    install's RECORD lists no source files, so the installed bytes are hashed directly).
    Content only: the same bytes at another path (a byte-identical candidate snapshot on
    sys.path) are the same identity; the path is reported by acceptance_runtime."""
    root = lexinspect_source_root()
    if root is None:
        return None
    from fixcheck.run import pkg_digest

    d = pkg_digest(root)
    return {"n_files": d["n_files"], "tree_sha256": d["tree_sha256"]}


def environment_identity(checkout: Path = REPO) -> dict[str, Any]:
    """uv.lock, Python, the numerical, parser and model distributions and the installed
    lexinspect, with file hashes (audit r2 B5, audit r3 S3). Computed afresh on every call
    (no process cache): production acceptance compares a fresh value with the frozen one
    (acceptance_runtime, runtime_problems)."""
    import sys

    def ver(dist: str) -> str | None:
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            return None

    lock = checkout / "uv.lock"
    return {
        "uv_lock_sha256": sha256_file(lock) if lock.exists() else None,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_build": sys.version,
        "machine": platform.machine(),
        "spacy": ver("spacy"),
        "spacy_model": {"en_core_web_sm": ver("en_core_web_sm")},
        "numerical": {d: ver(d) for d in ("numpy", "scipy")},
        "artifacts": {d: dist_digest(d) for d in ARTIFACT_DISTS},
        "lexinspect_source": lexinspect_source_identity(),
    }


def imported_distributions() -> list[str]:
    """The installed third-party distributions providing a module this process has imported
    (start-up hooks excepted)."""
    import sys

    owners = importlib.metadata.packages_distributions()
    tops = {m.split(".", 1)[0] for m in list(sys.modules)} - set(STARTUP_ONLY_MODULES)
    return sorted({d for t in tops for d in owners.get(t, [])})


def acceptance_runtime(checkout: Path | None = None) -> dict[str, Any]:
    """The runtime identity observed NOW by the process doing acceptance (audit r3 S3)."""
    import fixcheck

    env = environment_identity(fixcheck.REPO if checkout is None else checkout)
    imported = imported_distributions()
    return {
        "environment": env,
        "environment_sha256": hashlib.sha256(canonical_json(env).encode()).hexdigest(),
        "imported_distributions": imported,
        "imported_outside_identity": sorted(set(imported) - set(ARTIFACT_DISTS)),
        "lexinspect_source_root": str(lexinspect_source_root()),
        "observed_at": now_iso(),
    }


def runtime_problems(frozen: dict[str, Any] | None, observed: dict[str, Any]) -> list[str]:
    """The acceptance runtime must equal the runtime frozen in the freeze record."""
    if not frozen:
        return ["the freeze record binds no runtime identity"]
    now = observed["environment"]
    diff = []
    for k in sorted(set(frozen) | set(now)):
        a, b = frozen.get(k), now.get(k)
        if canonical_json(a) == canonical_json(b):
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            diff += [
                f"{k}.{kk}"
                for kk in sorted(set(a) | set(b))
                if canonical_json(a.get(kk)) != canonical_json(b.get(kk))
            ]
        else:
            diff.append(k)
    if diff:
        return [f"the acceptance runtime is not the frozen runtime (differs in {diff})"]
    return []


def ledger_identity(ledger_md: Path, components: Path | None) -> dict[str, Any]:
    from fixcheck.ledger import ledger_document

    md: dict[str, Any] = {"path": str(ledger_md), "sha256": None, "draft": None}
    if ledger_md.exists():
        text = ledger_md.read_text(encoding="utf-8")
        md["sha256"] = sha256_file(ledger_md)
        status = re.search(r"^\*\*Status:\*\*\s*([A-Z]+)", text, re.M)
        md["status"] = status.group(1) if status else None
        md["draft"] = (status is None) or status.group(1) == "DRAFT"
    comp: dict[str, Any] = {"path": None if components is None else str(components)}
    if components is not None and components.exists():
        comp["sha256"] = sha256_file(components)
        comp["content_equals_ledger_py"] = canonical_json(read_json(components)) == canonical_json(
            ledger_document()
        )
    return {"markdown": md, "components": comp}


def file_identity(path: Path | None, repo: Path = REPO) -> dict[str, Any]:
    if path is None:
        return {"path": None, "sha256": None, "in_repository": False}
    path = Path(path).resolve()
    return {
        "path": str(path),
        "sha256": sha256_file(path) if path.exists() else None,
        "in_repository": _rel(path, repo) is not None,
    }


_STATUS_LINE = re.compile(r"^\*\*Status:\*\*\s*([A-Z]+)", re.M)
IGNORED_NOTE = (
    "git check-ignore --no-index: refused even when force-added, which Git permits; a bound "
    "round-2 file must be an ordinary tracked file"
)


def tracking_problems(what: str, t: dict[str, Any] | None) -> list[str]:
    """Why a bound round-2 file (`tracking_identity`) cannot be an ordinary tracked file of
    the repository: outside it (the archive receipt covers only files committed in it), or
    matched by its ignore rules, or not checkable. Nothing given: no problem here."""
    t = t or {}
    if not t.get("path"):
        return []
    if not t.get("in_repository"):
        return [
            f"the {what} is outside the repository (the archive receipt covers only files "
            "committed in it)"
        ]
    if t.get("git_ignored") is True:
        return [f"the {what} is git-ignored ({IGNORED_NOTE})"]
    if t.get("git_ignored") is not False:
        return [f"the {what} could not be checked against the repository's ignore rules"]
    return []


def git_ignored(path: Path | None, repo: Path | None = None) -> bool | None:
    """Whether git's ignore rules match `path` inside `repo`, tracked or not (`git
    check-ignore --no-index`, so a force-added file under an ignored directory counts as
    ignored). None for a path outside the repository or when git cannot answer. `repo`
    defaults to this module's REPO at call time."""
    repo = REPO if repo is None else repo
    if path is None:
        return None
    rel = _rel(Path(path), repo)
    if rel is None:
        return None
    r = git("check-ignore", "-q", "--no-index", "--", rel, repo=repo, check=False)
    return {0: True, 1: False}.get(r.returncode)


def tracking_identity(path: Path | None, repo: Path | None = None) -> dict[str, Any]:
    """Where a bound file sits with respect to the repository (round 2, gap G2)."""
    repo = REPO if repo is None else repo
    if path is None:
        return {"path": None, "in_repository": False, "git_ignored": None}
    path = Path(path).resolve()
    return {
        "path": str(path),
        "in_repository": _rel(path, repo) is not None,
        "git_ignored": git_ignored(path, repo),
    }


def disposition_identity(
    path: Path | None,
    candidate_commit: str | None,
    repo: Path | None = None,
    narrowing_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The round-2 narrowing disposition (gap G2): its bytes, where it sits, its `**Status:**`
    line, whether it names the round-2 candidate commit (its first 12 characters) and
    whether it names the narrowing check it rests on (that file's full SHA-256; G10)."""
    nc_sha = (narrowing_check or {}).get("sha256")
    ident: dict[str, Any] = {
        **file_identity(path),
        **tracking_identity(path, repo),
        "status": None,
        "candidate_prefix": candidate_commit[:12] if candidate_commit else None,
        "names_candidate": False,
        "narrowing_check_sha256": nc_sha,
        "names_narrowing_check": False,
    }
    if path is not None and Path(path).is_file():
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        m = _STATUS_LINE.search(text)
        ident["status"] = m.group(1) if m else None
        ident["names_candidate"] = bool(candidate_commit) and candidate_commit[:12] in text
        ident["names_narrowing_check"] = bool(nc_sha) and nc_sha in text
    return ident


def round2_problems(r2: dict[str, Any]) -> list[str]:
    """The round-2 production prerequisites beyond the registered round 1 (gaps G2, G10): the
    narrowing disposition is inside the repository, not git-ignored, FINAL and names the
    candidate and the narrowing check; the narrowing check (narrowing.py) is given, inside
    the repository, not git-ignored and validates against this round (its recorded
    problems are empty); the ledger and its components are tracked (not git-ignored); the
    candidate's changes against round 1 are recorded for disclosure. A failure here
    surfaces at planning, before the reservation, and again when the execution rebuilds
    the record."""
    why = []
    nc = r2.get("narrowing_check") or {}
    if not nc.get("sha256"):
        why.append(
            "round 2 needs the final dry run's development-text narrowing check "
            "(--narrowing-check round2/NARROWING_CHECK.json)"
        )
    else:
        why += tracking_problems("narrowing check", nc)
        why += [f"narrowing check: {x}" for x in nc.get("problems") or []]
        if "problems" not in nc:
            why.append("narrowing check: it was not validated")
    nd = r2.get("narrowing_disposition") or {}
    if nd.get("sha256") and nc.get("sha256") and not nd.get("names_narrowing_check"):
        why.append(
            "the narrowing disposition does not name the narrowing check's SHA-256 "
            f"({nc['sha256']})"
        )
    if nd.get("sha256"):
        why += tracking_problems("narrowing disposition", nd)
        if nd.get("status") is None:
            why.append("the narrowing disposition has no **Status:** line")
        elif nd["status"] != "FINAL":
            why.append(f"the narrowing disposition has status {nd['status']}, not FINAL")
        if not nd.get("names_candidate"):
            why.append(
                "the narrowing disposition does not name the round-2 candidate commit "
                f"({nd.get('candidate_prefix')})"
            )
    for name, t in sorted((r2.get("tracking") or {}).items()):
        why += tracking_problems(name.replace("_", " "), t)
    ch = r2.get("candidate_changes_vs_round1")
    if not ch:
        why.append("round 2 could not record its candidate's changes against round 1's")
    elif not ch.get("round1_tree_matches_registry"):
        why.append("round 1's candidate commit no longer has its registered tree digest")
    return why


def receipt_paths(record_path: Path, record: dict[str, Any]) -> list[Path]:
    """Every file the archive receipt must find committed at HEAD (audit r2 B1)."""
    d = record_path.parent
    paths = [record_path, d / "command.txt", d / "manifest_plan.json"]
    led = record["ledger"]
    paths.append(Path(led["markdown"]["path"]))
    if led["components"]["path"]:
        paths.append(Path(led["components"]["path"]))
    paths += [Path(record["protocol"]["path"]), Path(record["clarifications"]["path"])]
    for b in (record.get("bound") or {}).values():
        for f in b if isinstance(b, list) else [b]:
            if f and f.get("path"):
                paths.append(Path(f["path"]))
    paths += sorted(HERE.glob("*.py"))
    paths += [STUDY4 / n for n in FROZEN_INPUTS if (STUDY4 / n).exists()]
    r2 = record.get("round2") or {}
    for name in ("narrowing_disposition", "narrowing_check"):
        if (r2.get(name) or {}).get("path"):
            paths.append(Path(r2[name]["path"]))
    return paths


def compare_records(planned: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """Every top-level field (and every key of nested dicts) that differs."""
    problems = []
    for k in sorted(set(planned) | set(now)):
        if k in VOLATILE:
            continue
        a, b = planned.get(k), now.get(k)
        if canonical_json(a) == canonical_json(b):
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            sub = sorted(
                kk
                for kk in set(a) | set(b)
                if canonical_json(a.get(kk)) != canonical_json(b.get(kk))
            )
            problems.append(f"{k}: differs in {sub}")
        else:
            problems.append(f"{k}: differs")
    return problems


def production_prerequisites(record: dict[str, Any]) -> list[str]:
    """Reasons a record cannot be a production freeze (checked at planning and execution)."""
    why = []
    cand = record["candidate"]
    if not cand.get("commit") or not cand.get("tree_sha256"):
        why.append("no candidate commit (--candidate-commit)")
    led = record["ledger"]
    if led["markdown"]["sha256"] is None:
        why.append("candidate ledger not found")
    elif led["markdown"]["draft"]:
        why.append("candidate ledger is DRAFT (the maintainer must finalise it first)")
    if not led["components"].get("sha256"):
        why.append("no ledger_components.json (--ledger-components)")
    elif not led["components"].get("content_equals_ledger_py"):
        why.append("ledger_components.json differs from ledger.ledger_document()")
    if record["protocol"]["sha256"] is None:
        why.append("protocol not found")
    if record["clarifications"]["sha256"] is None:
        why.append("protocol clarifications file not found")
    if record["environment"]["uv_lock_sha256"] is None:
        why.append("uv.lock not found")
    bound = record.get("bound") or {}
    for name in ("preregistration", "delivery_spec", "registry"):
        f = bound.get(name) or {}
        if not f.get("sha256"):
            why.append(f"no {name.replace('_', ' ')} (--{name.replace('_', '-')})")
        elif not f.get("in_repository"):
            why.append(f"the {name.replace('_', ' ')} is not inside the repository")
    if not bound.get("dispositions") or not all(
        f.get("sha256") and f.get("in_repository") for f in bound["dispositions"]
    ):
        why.append("the dispositions and rulings are not all given, present and tracked")
    dl = record.get("delivery") or {}
    if dl.get("problems"):
        why.append(f"delivery spec: {dl['problems']}")
    rg = record.get("registry") or {}
    if rg.get("problems"):
        why.append(f"round registry: {rg['problems']}")
    if not rg.get("reservation_sha256"):
        why.append("the round is not reserved in the canonical registry")
    rr = record.get("receipt_ref") or {}
    if rr.get("problems"):
        why.append(f"receipt ref: {rr['problems']}")
    if rr.get("ref") != REGISTERED_RECEIPT_REF:
        # round 1's registered ref (dispositions R2-B1); no other ref is registered, so round 2
        # uses the same one (the conservative reading, HARNESS_R5 notes)
        why.append(f"receipt ref {rr.get('ref')!r} is not the registered {REGISTERED_RECEIPT_REF}")
    if record["round"] == 2:
        r2 = record.get("round2") or {}
        if not r2.get("round1_entry_sha256"):
            why.append("round 2 needs a registered round-1 non-pass decision")
        if not (r2.get("narrowing_disposition") or {}).get("sha256"):
            why.append("round 2 needs a reviewed narrowing disposition (--narrowing-disposition)")
        why += round2_problems(r2)
    return why


def execution_gate(
    record_path: Path,
    record: dict[str, Any],
    repo: Path = REPO,
    remote_ref: str = DEFAULT_REMOTE_REF,
) -> dict[str, Any]:
    """Production-only checks before any fetch: clean tree at the candidate, archive receipt."""
    problems = list(production_prerequisites(record))
    changes = tracked_changes(repo)
    if changes:
        problems.append(f"tracked working tree is not clean: {changes[:5]}")
    cand = record["candidate"]
    head = git("rev-parse", "HEAD", repo=repo).stdout.strip()
    if cand.get("commit"):
        anc = git("merge-base", "--is-ancestor", cand["commit"], head, repo=repo, check=False)
        if anc.returncode != 0:
            problems.append(f"HEAD {head[:12]} does not descend from the candidate commit")
        from fixcheck.run import pkg_digest

        wt = pkg_digest(repo / "src" / "lexinspect")["tree_sha256"]
        if wt != cand["tree_sha256"]:
            problems.append("src/lexinspect differs from the candidate commit's")
    if remote_ref != (record.get("receipt_ref") or {}).get("ref"):
        problems.append(f"--remote-ref {remote_ref} is not the freeze record's receipt ref")
    from fixcheck import registry as REG

    rg = record.get("registry") or {}
    if not rg.get("path"):
        problems.append("the freeze record names no round registry")
    else:
        reg = REG.integrity(Path(rg["path"]), repo)
        problems += [f"registry: {x}" for x in reg["problems"]]
        if not REG.find_entry(REG.load(Path(rg["path"])), rg.get("reservation_sha256")):
            problems.append("the round's reservation is not in the registry")
    receipt = archive_receipt(receipt_paths(record_path, record), repo, remote_ref)
    problems += receipt["problems"]
    return {"head": head, "receipt": receipt, "problems": problems, "ok": not problems}


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
