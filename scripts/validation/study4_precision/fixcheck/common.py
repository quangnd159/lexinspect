"""Shared helpers: canonical JSON, hashing, derived seeds, output manifests.

Every subcommand ends with `write_step_manifest`, which records the SHA-256 of
every file it wrote, the exact command line, the SHA-256 of every harness and
frozen Study 4 source file, and the git state. Nothing here touches labels.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fixcheck import HERE, REPO, STUDY4

HARNESS_VERSION = "fixcheck/1"
FROZEN_INPUTS = (
    "build.py",
    "analyse.py",
    "estimators.py",
    "frame.py",
    "batches.py",
    "human_page.py",
    "simulate_coverage.py",
    "test_analyse.py",
)


def canonical_json(obj: Any) -> str:
    """The one serialisation used for every hash: sorted keys, no spaces, UTF-8 kept."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def payload_sha256(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


def derive_seed(round_seed: int, label: str) -> int:
    """Independent integer seed for one frame: first 64 bits of
    sha256("fixcheck-v1|{round_seed}|{label}"). Declared rule; archived per frame."""
    h = hashlib.sha256(f"fixcheck-v1|{round_seed}|{label}".encode()).hexdigest()
    return int(h[:16], 16)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


_COMMAND: list[str] | None = None


def set_command(subcommand: str, argv: list[str]) -> None:
    """Record the exact invocation of a subcommand (archived by every step manifest)."""
    global _COMMAND
    _COMMAND = [sys.executable, "-I", str(HERE / "cli.py"), subcommand, *argv]


def _command_list() -> list[str]:
    return list(_COMMAND) if _COMMAND is not None else [sys.executable, *sys.argv]


def command_line() -> str:
    return shlex.join(_command_list())


def git_state(repo: Path = REPO) -> dict[str, Any]:
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--", "src"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return {"repo": str(repo), "commit": None, "src_dirty": None, "src_dirty_paths": []}
    return {
        "repo": str(repo),
        "commit": head,
        "src_dirty": bool(dirty),
        "src_dirty_paths": [d[3:] for d in dirty],
    }


def source_hashes() -> dict[str, str]:
    """SHA-256 of every harness source file and every frozen Study 4 input."""
    out = {f"fixcheck/{p.name}": sha256_file(p) for p in sorted(HERE.glob("*.py"))}
    for name in FROZEN_INPUTS:
        p = STUDY4 / name
        if p.exists():
            out[name] = sha256_file(p)
    return out


_ENV_SHA: dict[str, str] = {}


def environment_sha256() -> str:
    """SHA-256 of freeze.environment_identity() (uv.lock, Python, spaCy, model and installed
    artifact hashes), computed once per process; every step manifest records it and the
    package check compares it with the freeze record's (audit r2 B5). Manifest stamping
    only: acceptance never relies on this cache, it observes a fresh identity
    (freeze.acceptance_runtime, audit r3 S3)."""
    if "v" not in _ENV_SHA:
        from fixcheck.freeze import environment_identity

        _ENV_SHA["v"] = sha256_text(canonical_json(environment_identity(REPO)))
    return _ENV_SHA["v"]


def refuse_existing(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise SystemExit(f"{path} already exists; refusing to overwrite (pass --overwrite)")


def write_step_manifest(
    out_dir: Path, step: str, files: Iterable[Path], extra: dict[str, Any] | None = None
) -> Path:
    """manifest_<step>.json: sha256 and size of every output, command, sources, git, env."""
    entries = {}
    for f in sorted({Path(p) for p in files}):
        entries[str(f.relative_to(out_dir))] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
    man = {
        "harness": HARNESS_VERSION,
        "step": step,
        "written": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "command": command_line(),
        "python": platform.python_version(),
        "git": git_state(),
        "sources_sha256": source_hashes(),
        "environment_sha256": environment_sha256(),
        "outputs": entries,
        **(extra or {}),
    }
    path = out_dir / f"manifest_{step}.json"
    write_json(path, man)
    return path
