"""The one canonical round registry (audit r1 B2, audit r2 B2).

Path: docs/validation/study4-fix040/round_registry.jsonl, tracked in git and
bound into every freeze record (path, SHA-256 of its bytes, SHA-256 of its
committed HEAD blob). No other path is accepted in production: `integrity`
refuses a missing, uncommitted, substituted or rewritten file (the committed
HEAD version must be a byte prefix of the file, and every line must be one
canonical JSON object). Each line is one entry:

  {"type": "reservation", "round", "candidate_commit", "candidate_tree_sha256",
   "seed", "collect_dir", "registered_at"}
      written by `collect --plan-only` before the freeze record, which binds it
      (reservation_sha256 = SHA-256 of the canonical line). The reservation is
      part of the receipted freeze: `collect --execute` refuses without it.
  {"type": "decision", "round", "candidate_commit", "candidate_tree_sha256",
   "seed", "reservation_sha256", "freeze_record_sha256",
   "collection_texts_sha256", "source_refs", "session_ids_sha256",
   "transcripts_sha256", "inputs_sha256", "status", "acceptance_sha256",
   "families", "round1_entry_sha256" (round 2), "registered_at"}
      appended by production `accept` only, atomically (`atomic_append`: an
      exclusive lock, the integrity check and the rule check on the file as it is
      under the lock, then the append and the platform durable barrier of durable.py,
      R4 Addendum ruling 1). A production decision without
      registration does not exist: `accept --preview` is ineligible.
  {"type": "terminal", "outcome": "ship"|"revert_0.3.3"|"amendment", "basis",
   "registered_at"}

Rules:
- Reservations (`check_reservation`): none after a terminal entry; one
  reservation per round, for one (candidate, seed, collection directory); an
  identical reservation is already present (no second line); round 1 not after
  a round-1 decision; round 2 only after a registered round-1 non-pass, for a
  different candidate commit and a different seed.
- Decisions (`check_decision`): the decision must name a registered reservation
  with the same round, candidate and seed. A (candidate, round) already decided:
  identical complete input identity (inputs_sha256, which covers the whole
  authenticated chain, package.py) and status is idempotent; anything else (new
  labels, a new seed, a new package, a changed delivery) is refused. A round's
  component identities are charged once. Round 2 needs a registered round-1
  non-pass, a different candidate commit, the original family identities, a
  distinct seed, the registered round-1 entry as its earlier round, canonical
  source identities DISJOINT from round 1's (not merely a different manifest
  hash), and fresh sessions (no session id or transcript of round 1).
- A failed, killed or aborted execution, or a completed collection that cannot reach
  labels (a shortfall, or a pre-label step that cannot complete; R4 Addendum 2), is
  registered by `register-failure` as a
  decision with status "procedure_failure" (a non-pass; audit r4 S1; failure.py): no
  labels, no acceptance arithmetic; its "source_refs" are the hashed identities of its
  exposure inventory and "failure" binds the evidence. That round is consumed: no other
  decision for it is ever admitted. After a round-1 procedure_failure, round 2 follows
  the round-2 rules above, its sources disjoint from the exposure, only if the exposure
  was established ("exposure_complete"); otherwise only revert_0.3.3 or amendment. A
  round-2 procedure_failure is terminal like any round-2 non-pass.
- After a round-1 pass, the only further entry is the terminal "ship".
- After round 2, or after any terminal entry, no further decision is accepted.
  "ship" needs the latest decision to be a pass; "revert_0.3.3" and
  "amendment" need it to be a non-pass.
- There is no pooling and no subset rescue: a decision covers the whole
  candidate and both modules.

Receipts (audit r3 S1): a receipt made at the freeze covers the registry as it was
then. `extension_problems` accepts the current registry only as a byte-for-byte
extension of that receipted version whose appended lines the rules above admit in
order; freeze.verify_receipt uses it for this one file.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fixcheck import REPO
from fixcheck.common import canonical_json, sha256_text
from fixcheck.durable import DurabilityError, durability_method, durable_sync
from fixcheck.freeze import git, now_iso
from fixcheck.ledger import FAMILIES

TERMINAL = ("ship", "revert_0.3.3", "amendment")
ACCEPT_STATUSES = ("pass", "fail", "inconclusive")
FAILURE_STATUS = "procedure_failure"
STATUSES = (*ACCEPT_STATUSES, FAILURE_STATUS)
FAILURE_KEYS = (
    "execution_start_sha256",
    "fetch_journal_sha256",
    "execution_abort_sha256",
    "cache_inventory_sha256",
    "archive_sha256",
    "exposure_sha256",
    "exposure_complete",
    "n_exposed",
)
REGISTRY_REL = "docs/validation/study4-fix040/round_registry.jsonl"
REGISTRY = REPO / REGISTRY_REL


def canonical_path(repo: Path = REPO) -> Path:
    return (repo / REGISTRY_REL).resolve()


def load(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def entry_sha256(entry: dict[str, Any]) -> str:
    return sha256_text(canonical_json(entry))


def find_entry(entries: list[dict[str, Any]], sha: str | None) -> dict[str, Any] | None:
    if not sha:
        return None
    return next((e for e in entries if entry_sha256(e) == sha), None)


def decisions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("type") == "decision"]


def reservations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("type") == "reservation"]


def integrity(path: Path, repo: Path = REPO) -> dict[str, Any]:
    """Is `path` the canonical, committed, append-only registry? Never raises."""
    problems: list[str] = []
    path = Path(path).resolve()
    out: dict[str, Any] = {"path": str(path), "canonical": str(canonical_path(repo))}
    if path != canonical_path(repo):
        problems.append(f"{path} is not the canonical registry {REGISTRY_REL}")
    if not path.exists():
        problems.append("the registry file is missing")
        return out | {"problems": problems, "ok": False}
    data = path.read_bytes()
    out["sha256"] = sha256_text(data.decode("utf-8"))
    rel = REGISTRY_REL
    r = git("cat-file", "blob", f"HEAD:{rel}", repo=repo, text=False, check=False)
    if r.returncode != 0:
        problems.append(f"{rel} is not committed at HEAD")
    else:
        out["head_sha256"] = sha256_text(r.stdout.decode("utf-8"))
        if not data.startswith(r.stdout):
            problems.append(f"{rel} is not an append-only extension of its committed version")
    problems += history_problems(repo)
    for i, line in enumerate(data.decode("utf-8").splitlines(), 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"line {i} is not JSON")
            continue
        if canonical_json(obj) != line:
            problems.append(f"line {i} is not one canonical JSON object")
    out["n_entries"] = len(load(path))
    return out | {"problems": problems, "ok": not problems}


def history_problems(repo: Path = REPO) -> list[str]:
    """Every committed version of the registry extends the one before it (audit r2 B2).

    Walks `git rev-list --reverse HEAD -- <registry>` (local objects only): a commit that
    deletes the file, or whose version is not a byte prefix-extension of the previous
    committed version, is a rewritten history."""
    out = git("rev-list", "--reverse", "HEAD", "--", REGISTRY_REL, repo=repo, check=False)
    if out.returncode != 0:
        return ["the registry's git history cannot be read"]
    prev = b""
    problems = []
    for c in out.stdout.split():
        r = git("cat-file", "blob", f"{c}:{REGISTRY_REL}", repo=repo, text=False, check=False)
        if r.returncode != 0:
            problems.append(f"commit {c[:12]} deletes the registry")
            prev = b""
            continue
        if not r.stdout.startswith(prev):
            problems.append(
                f"commit {c[:12]} rewrites the registry (not an append-only extension of the "
                "previous committed version)"
            )
        prev = r.stdout
    return problems


def extension_problems(path: Path, prefix: bytes, repo: Path = REPO) -> list[str]:
    """The registry now on disk extends a receipted historical version (audit r3 S1).

    `prefix` is the committed blob a receipt authenticated. The current file must start
    with exactly those bytes (append-only), pass `integrity` (canonical path, committed
    HEAD version a prefix, every committed version extending the previous, canonical
    lines), and every entry appended after the prefix must be one the rules admit given
    the entries before it: a new reservation (check_reservation 'append'), a new decision
    (check_decision 'append') or a terminal outcome (check_terminal). A duplicate line, a
    rule violation, a rewrite, a truncation or a non-prefix file is a problem."""
    path = Path(path)
    if not path.exists():
        return ["the registry file is missing (changed since the receipt)"]
    data = path.read_bytes()
    if not data.startswith(prefix):
        return ["changed since the receipt: not an append-only extension of the receipted registry"]
    if prefix and not prefix.endswith(b"\n"):
        return ["the receipted registry does not end at a line boundary"]
    problems = list(integrity(path, repo)["problems"])
    entries = [json.loads(x) for x in prefix.decode("utf-8").splitlines() if x.strip()]
    for i, line in enumerate(data[len(prefix) :].decode("utf-8").splitlines(), 1):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"appended line {i} is not JSON")
            continue
        kind = e.get("type")
        if kind == "reservation":
            verdict, probs = check_reservation(entries, e)
        elif kind == "decision":
            verdict, probs = check_decision(entries, e)
        elif kind == "terminal":
            probs = check_terminal(entries, e.get("outcome"))
            verdict = "refuse" if probs else "append"
        else:
            verdict, probs = "refuse", [f"unknown entry type {kind!r}"]
        if verdict != "append":
            problems.append(
                f"appended line {i} ({kind}) is not admitted by the registry rules "
                f"after the receipted entries: {probs or verdict}"
            )
        entries.append(e)
    return problems


def _decision_for(entries, rnd: int) -> dict[str, Any] | None:
    d = [e for e in decisions(entries) if e["round"] == rnd]
    return d[0] if d else None


def round1_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _decision_for(entries, 1)


def no_round2_after(r1: dict[str, Any]) -> list[str]:
    """A round-1 procedure_failure whose exposure was not established admits no round 2
    (audit r4 S1): only the terminal outcomes revert_0.3.3 and amendment remain."""
    if r1.get("status") == FAILURE_STATUS and not (r1.get("failure") or {}).get(
        "exposure_complete"
    ):
        return [
            "round 1 is a procedure_failure whose exposure was not established: no round 2; "
            "only the terminal outcomes revert_0.3.3 and amendment remain"
        ]
    return []


def check_reservation(entries: list[dict[str, Any]], res: dict[str, Any]) -> tuple[str, list[str]]:
    """('append' | 'present' | 'refuse', problems)."""
    problems: list[str] = []
    ident = ("round", "candidate_commit", "candidate_tree_sha256", "seed", "collect_dir")
    if res.get("type") != "reservation":
        return "refuse", ["not a reservation"]
    if any(e.get("type") == "terminal" for e in entries):
        problems.append("a terminal outcome is registered: no further round can be reserved")
    same = [e for e in reservations(entries) if all(e.get(k) == res.get(k) for k in ident)]
    other = [e for e in reservations(entries) if e["round"] == res["round"] and e not in same]
    if other:
        problems.append(
            f"round {res['round']} is already reserved for candidate "
            f"{str(other[0]['candidate_commit'])[:12]} seed {other[0]['seed']}: one reservation "
            "per round (parallel packages are refused)"
        )
    if res["round"] == 1:
        if round1_entry(entries) and not same:
            problems.append("round 1 is already decided")
    elif res["round"] == 2:
        r1 = round1_entry(entries)
        if r1 is None:
            problems.append("round 2 needs a registered round-1 decision")
        else:
            if r1["status"] == "pass":
                problems.append("round 1 passed: a second round is not allowed (terminal: ship)")
            if r1["candidate_commit"] == res["candidate_commit"]:
                problems.append("round 2 needs a separately frozen revised candidate")
            if r1["seed"] == res["seed"]:
                problems.append("round 2 needs a seed distinct from round 1's")
            problems += no_round2_after(r1)
        if _decision_for(entries, 2) and not same:
            problems.append("round 2 is already decided")
    else:
        problems.append(f"round {res['round']}: only rounds 1 and 2 are permitted")
    if problems:
        return "refuse", problems
    return ("present" if same else "append"), []


def check_decision(entries: list[dict[str, Any]], entry: dict[str, Any]) -> tuple[str, list[str]]:
    """('append' | 'idempotent' | 'refuse', problems)."""
    problems: list[str] = []
    decs = decisions(entries)
    if any(e.get("type") == "terminal" for e in entries):
        problems.append("a terminal outcome is registered: no further decision is accepted")
    status = entry.get("status")
    if status not in STATUSES:
        problems.append(f"status {status!r} is not one of {STATUSES}")
    if status == FAILURE_STATUS:
        f = entry.get("failure")
        if not isinstance(f, dict) or any(k not in f for k in FAILURE_KEYS):
            problems.append("a procedure_failure needs its failure evidence (register-failure)")
        kind = (f or {}).get("kind", "interrupted") if isinstance(f, dict) else None
        if kind not in ("interrupted", "shortfall", "pre_label_step"):
            problems.append(f"unknown procedure_failure kind {kind!r}")
        elif (entry.get("collection_texts_sha256") is None) != (kind == "interrupted"):
            problems.append(
                "a procedure_failure names a collected text set exactly when its collection "
                "completed (kind shortfall or pre_label_step; R4 Addendum 2)"
            )
    failed = [
        e
        for e in decs
        if e["round"] == entry.get("round")
        and e.get("status") == FAILURE_STATUS
        and not (e["inputs_sha256"] == entry.get("inputs_sha256") and status == FAILURE_STATUS)
    ]
    if failed:
        problems.append(
            f"round {entry.get('round')} is registered as a procedure_failure: the round is "
            "consumed and never accepted, retried or decided again"
        )
    res = find_entry(entries, entry.get("reservation_sha256"))
    if res is None or res.get("type") != "reservation":
        problems.append("the decision names no registered reservation")
    elif any(
        res.get(k) != entry.get(k)
        for k in ("round", "candidate_commit", "candidate_tree_sha256", "seed")
    ):
        problems.append("the decision's round, candidate or seed is not its reservation's")
    same = [
        e
        for e in decs
        if e["candidate_commit"] == entry["candidate_commit"] and e["round"] == entry["round"]
    ]
    if same:
        prev = same[0]
        if prev["inputs_sha256"] == entry["inputs_sha256"] and prev["status"] == entry["status"]:
            return ("idempotent", problems) if not problems else ("refuse", problems)
        problems.append(
            f"round {entry['round']} of candidate {entry['candidate_commit'][:12]} is already "
            "registered with other inputs: new labels, seeds, packages or deliveries under used "
            "identities are refused"
        )
    others = [e for e in decs if e["round"] == entry["round"] and e not in same]
    if others:
        problems.append(
            f"the round-{entry['round']} component identities are already charged to candidate "
            f"{others[0]['candidate_commit'][:12]}"
        )
    if list(entry.get("families", [])) != list(FAMILIES):
        problems.append("the decision's family identities are not the ledger's original families")
    r1 = round1_entry(entries)
    if entry["round"] == 2:
        if r1 is None:
            problems.append("round 2 needs a registered round-1 decision")
        else:
            if r1["status"] == "pass":
                problems.append("round 1 passed: a second round is not allowed (terminal: ship)")
            if r1["candidate_commit"] == entry["candidate_commit"]:
                problems.append("round 2 needs a separately frozen revised candidate")
            if r1["seed"] == entry["seed"]:
                problems.append("round 2 needs a seed distinct from round 1's")
            if entry.get("round1_entry_sha256") != entry_sha256(r1):
                problems.append("round 2 does not name the registered round-1 decision")
            problems += no_round2_after(r1)
            shared = set(r1.get("source_refs", [])) & set(entry.get("source_refs", []))
            # a failed round 2 may have exposed nothing; a decided one must name its sources
            if shared or (not entry.get("source_refs") and status != FAILURE_STATUS):
                problems.append(
                    f"round 2 needs canonical source identities disjoint from round 1's "
                    f"({len(shared)} shared)"
                )
            for k in ("session_ids_sha256", "transcripts_sha256"):
                if set(r1.get(k, [])) & set(entry.get(k, [])):
                    problems.append(f"round 2 reuses a round-1 session ({k})")
    elif entry["round"] != 1:
        problems.append(f"round {entry['round']}: only rounds 1 and 2 are permitted")
    return ("refuse" if problems else "append"), problems


ACK_VERDICTS = ("present", "idempotent")


def same_terminal(entries: list[dict[str, Any]], outcome: str, basis: str) -> bool:
    """The registry's last entry is already this terminal (outcome and basis): the rerun of
    a register-terminal whose barrier failed (audit r5 S1), acknowledged as 'present'."""
    terms = [e for e in entries if e.get("type") == "terminal"]
    return (
        len(terms) == 1
        and entries[-1] is terms[0]
        and terms[0].get("outcome") == outcome
        and terms[0].get("basis") == basis
    )


def check_terminal(entries: list[dict[str, Any]], outcome: str) -> list[str]:
    problems = []
    if outcome not in TERMINAL:
        problems.append(f"terminal outcome must be one of {TERMINAL}")
    if any(e.get("type") == "terminal" for e in entries):
        problems.append("a terminal outcome is already registered")
    decs = decisions(entries)
    if not decs:
        problems.append("no registered decision to terminate")
        return problems
    last = max(decs, key=lambda e: e["round"])
    if outcome == "ship" and last["status"] != "pass":
        problems.append("'ship' needs the latest registered decision to be a pass")
    if outcome in ("revert_0.3.3", "amendment") and last["status"] == "pass":
        problems.append(f"'{outcome}' follows a non-pass decision only")
    return problems


@contextlib.contextmanager
def _locked(path: Path):
    with Path(path).open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def atomic_append(
    path: Path,
    make: Callable[[list[dict[str, Any]]], tuple[str, list[str], dict[str, Any] | None]],
    repo: Path = REPO,
    require_integrity: bool = True,
) -> tuple[str, list[str], dict[str, Any] | None]:
    """Lock the registry, check its integrity and the rule on the file as it is now, then
    append the entry `make` returns (verdict 'append') and pass the durable barrier. `make(entries)` returns
    (verdict, problems, entry). Nothing is written unless the verdict is 'append'."""
    path = Path(path)
    if not path.exists():
        return "refuse", [f"{path}: the registry file is missing"], None
    try:
        durability_method()
    except DurabilityError as e:  # refused before anything is written (R4 Addendum 1)
        return "refuse", [f"registry append refused: {e}"], None
    with _locked(path) as f:
        if require_integrity:
            integ = integrity(path, repo)
            if not integ["ok"]:
                return "refuse", [f"registry: {x}" for x in integ["problems"]], None
        f.seek(0)
        entries = [json.loads(x) for x in f.read().splitlines() if x.strip()]
        verdict, problems, entry = make(entries)
        if verdict in ACK_VERDICTS and not problems:
            # audit r5 S1: an existing identical line is acknowledged only after the same
            # file-plus-directory barrier, so a rerun after a failed barrier rechecks it
            # (a persistent failure still refuses; no second line is ever written)
            _durable(f, path, rerun=True)
            return verdict, problems, entry
        if verdict != "append" or problems or entry is None:
            return ("refuse" if problems else verdict), problems, entry
        entry = dict(entry, registered_at=entry.get("registered_at") or now_iso())
        f.seek(0, os.SEEK_END)
        f.write(canonical_json(entry) + "\n")
        f.flush()
        _durable(f, path)
        return "append", [], entry


def _durable(f, path: Path, rerun: bool = False) -> None:
    """The execution claim's platform barrier on the registry file and its directory
    (R4 Addendum ruling 1: F_FULLFSYNC on Darwin, fsync on Linux). A failure is never
    downgraded: the command stops with SystemExit. The line may then be on disk without
    the guarantee; rerunning the same command finds it (reservation 'present', decision
    'idempotent', identical terminal 'present') and acknowledges it only after this
    barrier succeeds on the file as it is (audit r5 S1), never appending twice."""
    try:
        durable_sync(f.fileno(), path)
    except DurabilityError as e:
        what = (
            "the registry line is already present but the durable-write barrier failed again"
            if rerun
            else "the registry line was written but its durable-write barrier failed"
        )
        raise SystemExit(
            f"{path}: {what}; refused (do not continue: rerun the same command to recheck): {e}"
        ) from None


def append_unchecked(path: Path, entry: dict[str, Any]) -> None:
    """Tests and dry runs only: append without the canonical-path integrity check (the
    same durable barrier as atomic_append)."""
    with _locked(path) as f:
        f.seek(0, os.SEEK_END)
        f.write(canonical_json(entry) + "\n")
        f.flush()
        _durable(f, Path(path))


def acknowledge_unchecked(path: Path) -> None:
    """Tests and dry runs only: the barrier atomic_append applies before acknowledging an
    existing identical line ('present' / 'idempotent'; audit r5 S1)."""
    with _locked(path) as f:
        _durable(f, Path(path), rerun=True)
