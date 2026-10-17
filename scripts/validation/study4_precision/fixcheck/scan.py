"""`scan-restricted`: the restricted-content check before every commit (RUNBOOK 0.3;
audit r4 S3, audit r5 M3).

    scan-restricted fragments --inventory INV --out F   write the private fragment file
    scan-restricted staged    --fragments F             every staged blob + working file
    scan-restricted whole-set --fragments F             the whole publication set

A fragment is a piece of the private inventory between table bars, semicolons, quotation
marks, asterisks or line ends, stripped, of 20 characters or more. Matching is on bytes
(binary files included). Output is paths and counts only: a fragment is never printed.

Exit status: 0 = every input was read and nothing matched (the last line is the
completion marker, printed only then); 1 = at least one input matched; 2 = the check
could not be completed (missing, unreadable or empty fragment file; a git, read or
listing error). Anything but 0 stops the runbook.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from fixcheck import REPO

MIN_FRAGMENT = 20
SPLIT = r'[|;"*\n]'
FIX040 = Path(".cache/validation/study4_fix040")
TREES = (
    "scripts/validation/study4_precision",
    "src/lexinspect",
    "tests",
    "docs/validation/study4-fix040",
)
FILES = (
    "docs/validation/study4-fix-protocol.md",
    "docs/validation/study4-fix-protocol-clarifications.md",
    "docs/validation/study4-preregistration.md",
)
# the ledger, dispositions and rulings step 3 copies into docs/validation/study4-fix040/
COPIED = (
    "CANDIDATE_LEDGER.md",
    "HARNESS_AUDIT_R1_DISPOSITIONS.md",
    "HARNESS_AUDIT_R2_DISPOSITIONS.md",
    "HARNESS_AUDIT_R3_DISPOSITIONS.md",
    "HARNESS_AUDIT_R4_DISPOSITIONS.md",
    "HARNESS_AUDIT_R5_DISPOSITIONS.md",
    "HARNESS_RULINGS.md",
)
DONE = "scan finished: clean"


class ScanError(Exception):
    """The check could not be completed (exit 2)."""


def fragments_of(text: str) -> list[str]:
    return sorted({f.strip() for f in re.split(SPLIT, text) if len(f.strip()) >= MIN_FRAGMENT})


def load_fragments(path: Path) -> list[bytes]:
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise ScanError(f"the fragment file cannot be read ({type(e).__name__})") from None
    frags = [x for x in data.split(b"\n") if x.strip()]
    if not frags:
        raise ScanError("the fragment file is empty")
    if any(len(x.decode("utf-8", "replace")) < MIN_FRAGMENT for x in frags):
        raise ScanError(f"the fragment file holds a line shorter than {MIN_FRAGMENT} characters")
    return frags


def count(data: bytes, frags: list[bytes]) -> int:
    return sum(f in data for f in frags)


def _tree(repo: Path, rel: str) -> list[Path]:
    root = repo / rel
    if not root.is_dir():
        raise ScanError(f"{rel}: not a directory")
    errors: list[OSError] = []
    out = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=errors.append):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", ".pytest_cache"))
        for n in sorted(filenames):
            if not n.endswith(".pyc"):
                out.append(Path(dirpath) / n)
    if errors:
        raise ScanError(f"{rel}: the directory listing failed ({type(errors[0]).__name__})")
    return out


def publication_set(repo: Path = REPO) -> list[Path]:
    """Every file the runbook's public allowlist publishes, as it is now."""
    files = [p for rel in TREES for p in _tree(repo, rel)]
    files += [repo / f for f in FILES]
    files += [repo / FIX040 / n for n in COPIED]
    return files


def _git(repo: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if r.returncode != 0:
        raise ScanError(f"git {args[0]} failed (status {r.returncode})")
    return r.stdout


def _read(p: Path, rel: str) -> bytes:
    try:
        return p.read_bytes()
    except OSError as e:
        raise ScanError(f"{rel}: cannot be read ({type(e).__name__})") from None


def scan_staged(repo: Path, frags: list[bytes], emit) -> int:
    names = [
        n.decode("utf-8", "surrogateescape")
        for n in _git(repo, "diff", "--cached", "--name-only", "--diff-filter=d", "-z").split(b"\0")
        if n
    ]
    bad = 0
    for n in names:
        hits = count(_git(repo, "cat-file", "blob", f":{n}"), frags)
        wt = repo / n
        if hits:
            emit(f"RESTRICTED (staged blob): {n} ({hits} fragments)")
        elif wt.exists() and (hits := count(_read(wt, n), frags)):
            emit(f"RESTRICTED (working tree): {n} ({hits} fragments)")
        else:
            emit(f"ok: {n}")
        bad += bool(hits)
    emit(f"staged files read: {len(names)}; restricted: {bad}")
    return bad


def scan_whole(repo: Path, frags: list[bytes], emit) -> int:
    files = publication_set(repo)
    bad = 0
    for p in files:
        rel = p.relative_to(repo).as_posix()
        if not p.is_file():
            raise ScanError(f"{rel}: missing")
        hits = count(_read(p, rel), frags)
        if hits:
            emit(f"RESTRICTED: {rel} ({hits} fragments)")
            bad += 1
    emit(f"publication-set files read: {len(files)}; restricted: {bad}")
    return bad


def main(argv: list[str], emit=print) -> int:
    ap = argparse.ArgumentParser(prog="fixcheck scan-restricted", description=__doc__)
    ap.add_argument("mode", choices=("fragments", "staged", "whole-set"))
    ap.add_argument("--inventory", type=Path, help="fragments: the private sense inventory")
    ap.add_argument("--out", type=Path, help="fragments: the private fragment file")
    ap.add_argument("--fragments", type=Path, help="staged/whole-set: the fragment file")
    ap.add_argument("--repo", type=Path, default=REPO)
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.mode == "fragments":
            if not args.inventory or not args.out:
                raise ScanError("fragments needs --inventory and --out")
            try:
                text = args.inventory.read_text(encoding="utf-8")
            except (OSError, ValueError) as e:
                raise ScanError(f"the inventory cannot be read ({type(e).__name__})") from None
            frags = fragments_of(text)
            if not frags:
                raise ScanError("the inventory yields no fragment")
            try:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text("\n".join(frags) + "\n", encoding="utf-8")
            except OSError as e:
                raise ScanError(
                    f"the fragment file cannot be written ({type(e).__name__})"
                ) from None
            emit(f"fragments written: {len(frags)}")
            return 0
        if not args.fragments:
            raise ScanError(f"{args.mode} needs --fragments")
        frags = load_fragments(args.fragments)
        bad = (scan_staged if args.mode == "staged" else scan_whole)(repo, frags, emit)
    except ScanError as e:
        print(f"scan-restricted: NOT COMPLETED: {e}", file=sys.stderr)
        return 2
    if bad:
        print("scan-restricted: RESTRICTED content found", file=sys.stderr)
        return 1
    emit(DONE)
    return 0


__all__ = ["main", "publication_set", "fragments_of", "load_fragments", "DONE"]
