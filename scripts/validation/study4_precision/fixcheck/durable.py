"""The platform durable-write barrier (audit r4 B1; R4 Addendum ruling 1).

Shared by the execution claim and request journal (collect.py) and every round-registry
append (registry.py): the same barrier, the same refusal on failure, no downgrade."""

from __future__ import annotations

import fcntl
import os
import sys
from pathlib import Path


class DurabilityError(OSError):
    """The platform's durable-write barrier is unavailable or failed (audit r4 B1). It is
    never downgraded: the execution refuses before the first (or the next) request."""


def durability_method(platform: str | None = None) -> str:
    """The durable-write barrier of this platform (audit r4 B1), or DurabilityError.

    - darwin: fcntl(fd, F_FULLFSYNC) on the written file, then on its parent directory
      (opened O_RDONLY), with the file descriptor kept open until both barriers return.
      macOS's fsync(2) only moves data to the drive, which may reorder or drop it on power
      loss; F_FULLFSYNC also asks the drive to flush its cache.
    - linux: fsync(file), then fsync(parent directory): the documented equivalent (Linux
      fsync flushes the device write cache where the device reports one).
    - anything else: no barrier is defined, so the execution refuses."""
    plat = sys.platform if platform is None else platform
    if plat == "darwin":
        if not hasattr(fcntl, "F_FULLFSYNC"):
            raise DurabilityError("darwin without fcntl.F_FULLFSYNC: no durable-write barrier")
        return "darwin: fcntl F_FULLFSYNC on the file, then on its parent directory"
    if plat.startswith("linux"):
        return "linux: fsync on the file, then fsync on its parent directory"
    raise DurabilityError(f"no durable-write barrier is defined for platform {plat!r}")


def _barrier(fd: int, what: str) -> None:
    """One full durable barrier on an open descriptor (no silent downgrade)."""
    durability_method()  # raises on an unsupported platform
    try:
        if sys.platform == "darwin":
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        else:
            os.fsync(fd)
    except OSError as e:
        raise DurabilityError(
            e.errno, f"the durable-write barrier failed on {what}: {e.strerror or e}"
        ) from e


def durable_sync(fd: int, path: Path) -> None:
    """Barrier on the file `fd` (still open), then on the parent directory of `path`."""
    _barrier(fd, str(path))
    try:
        dfd = os.open(path.parent, os.O_RDONLY)
    except OSError as e:
        raise DurabilityError(e.errno, f"cannot open {path.parent} for its barrier: {e}") from e
    try:
        _barrier(dfd, f"the directory {path.parent}")
    finally:
        os.close(dfd)


def fsync_dir(d: Path) -> None:
    """The durable barrier on a directory alone."""
    fd = os.open(d, os.O_RDONLY)
    try:
        _barrier(fd, f"the directory {d}")
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """os.write until every byte is written (a short write is continued, never accepted)."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise DurabilityError(f"os.write wrote {n} bytes: refusing a partial write")
        view = view[n:]
