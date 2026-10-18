"""`collect`: plan, execute and replay one fix-check round's collection (protocol
"Collection and scope"; audit r1 B1, B6, S5).

Exactly 60 texts: 20 academic (7 sciences, 7 social sciences, 6 humanities),
20 general (Wikipedia Level-3 vital articles), 20 argumentative (Wikipedia
essays). Source pools, eligibility, extraction and truncation are build.py's
own functions (collect_academic, collect_wiki, jats_text, wiki_paragraphs,
cap_bytes, ...), called with build.py's module settings changed only for the
seed, the cache, the exclusion set and the per-pool targets; build.py itself
is not edited.

Plan and execute (B1; audit r2 B1, B2). A production round runs in two invocations:

  collect --plan-only --round R --seed S --out D --candidate-commit C
          --ledger-md M --ledger-components L --delivery-spec DS --registry REG
          --dispositions F1 [--dispositions F2 ...] --remote-ref
          refs/remotes/origin/<branch> --raw-cache RAW [--earlier ...]
          [round 2: --narrowing-disposition ND --narrowing-check NC]
  collect <the same arguments, without --plan-only> --execute --freeze-record D/freeze_record.json

`--plan-only` copies the development pool listings into the round's cache,
reserves the round in the canonical registry (registry.check_reservation; an
atomic append) and writes the immutable round package D/freeze_record.json
(freeze.py lists what it binds, including the reservation, the delivery spec,
the preregistration, the dispositions and the receipt ref) and D/command.txt,
the literal execution command. Nothing is fetched. The record and command.txt
are never overwritten. The maintainer then commits them with the registry and
pushes them to the receipt ref. `--execute` refuses, before any fetch, unless:
- its argv and working directory are exactly the recorded execution argv;
- every bound input recomputed from this invocation equals the record (seed,
  round, paths, pool inventory, initial cache inventory, development manifest,
  earlier rounds, exclusion set, candidate commit and digest, environment and
  artifact hashes, ledger, protocol, clarifications, preregistration, delivery
  spec, registry bytes and reservation, dispositions, receipt ref, harness and
  frozen-source hashes);
- (production) the tracked working tree is clean at a descendant of the
  candidate commit with src/lexinspect byte-equal to it, the registry is intact
  and holds the reservation, and the local archive receipt holds
  (freeze.execution_gate).
Single execution (audit r3 B1). Under an exclusive lock on D/execution.lock,
held from the gate recheck through completion, `--execute` refuses if any
execution evidence exists, reruns every check above, and then, before the first
possible fetch, creates the immutable start record D/execution_start.json with
exclusive creation (bound to the reservation, the freeze record and the argv)
and the request journal D/fetch_journal.jsonl (each request is journalled before
it is made). Every one of these writes passes the platform's full durable-write
barrier (durable_sync; audit r4 B1: F_FULLFSYNC on the file and its directory on
macOS, fsync on both on Linux; any other platform, or a failed barrier, refuses
before the next request, never downgrading). Once the
start record exists the round is never executed again: not after completion,
failure, abort, kill or a hard crash; there is no overwrite or resume.
Completion metadata goes to D/execution.json and abort evidence (for example a
Wikipedia fetch failure, which build.py does not catch, or any later failure)
to D/execution_abort.json, each created exclusively; neither replaces the start
record. command.txt is left as planned. A failed fetch is never retried.

Round 2 (audit r2 B2): --earlier must be exactly the registered round 1's
collection (texts, freeze record and seed equal to its registry entry),
authenticated (authenticate_collection); its identifiers are excluded. After a
registered round-1 procedure_failure (audit r4 S1; failure.py) --earlier is the
failed round-1 directory: its failure evidence must be the registered one, and its
authenticated exposure inventory (failure.exposure_inventory) is excluded instead;
if that exposure was not established, round 2 refuses (only terminal outcomes).
Round-2 hardening (docs/validation/study4-fix040/round2/HARNESS_ROUND2_RULINGS.md): round
1's bound files, its receipted command.txt and manifest_plan.json and its execution receipt
must be unchanged (G1, round1_preservation_problems; rechecked at acceptance), and round 2
needs its own ledger file (G1); the frozen Study 4 inputs must equal round 1's (G4); a
production round 2 needs the final dry run's narrowing check, `--narrowing-check
round2/NARROWING_CHECK.json` (G10, narrowing.py), validated before the reservation and
bound in the freeze record; and a production round's raw cache must be outside the
repository, disjoint from an earlier round's cache and private directory, free of links into
them, and fresh at planning (G5).

`--dry-run` marks a record and everything collected under it
`production_eligible: false`. It skips the production prerequisites (candidate
commit, final ledger, receipt) but keeps every equality check. Without
--plan-only or --execute, `--dry-run` plans and executes in one invocation (tests
and demonstrations). A production record cannot be executed with --dry-run,
nor a dry-run record without it.

Exclusions: the canonical development manifest (build.py's hash and size
guard, `load_dev_exclusions`) and every earlier fix-check round (its
texts.jsonl, checked against its collection.json). Every identifier of every
excluded text is excluded (build.text_refs); after collection the run stops if
any identifier of any collected text is in the exclusion set.

Pool and cache snapshot policy (declared): the sampling frame is the
development build's pool listings, byte for byte. They are copied into
<round raw cache>/pools/ at planning (an existing copy must be identical);
pools are never re-queried. build.py reaches its pool-query fetches
(`fetch(..., refresh=True)`) only when a listing is missing, and here they
always raise PoolRequeryForbidden before any request. Article and page
downloads go to the round's own cache, never to the development cache.
`--offline` forbids every network request.

Fetch instrumentation (B6, S5). build.fetch and build.wiki_page are wrapped,
never edited. Every fetch is logged (URL, cache path, cache hit, SHA-256 and
size of the returned bytes, the cache file's date, or the error), and every
wiki_page call (requested title, cache path, returned page id, revision id and
canonical title). A selected Wikipedia text is mapped to the first wiki_page
call that returned its page id and revision id, so its raw response is the
file under the REQUESTED title's cache key, even after a redirect or title
normalisation; two titles resolving to one page and two cached revisions are
told apart by page id and revision id. Nothing is renamed or refetched.

Replay (`--replay-round ROUND_DIR --out DIR`, S5; audit r2 S3): first
authenticates the archived evidence. Every logged successful fetch's cache file
and every selected raw file must still have its archived SHA-256, a failed
fetch's cache file must be absent, and the pool snapshot, development manifest
and earlier rounds must match the freeze record. Then it re-collects with the
recorded seed, round, targets and exclusions through the archived ordered
request/failure ledger (LedgerReplay): every request must be the ledger's next
entry (URL, cache key, refresh flag), every archived failure is raised again
with its original class and message without any request, and every archived
success is served from the authenticated cache file. It compares the texts
(bytes and metadata), the selection log, the fetch log (sequence, request,
outcome, failure class and message) and the wiki_page log. build.py derives a
text's `retrieved` field from its cache file's modification date (Wikipedia and
Europe PMC). The original retrieval date is archived in the fetch ledger
(`mtime_date`, written when the response was fetched); texts.jsonl must agree
with it, and a restored file's different mtime is reported as a metadata
difference, never as the record. The result is `identical` only if the texts,
the logs and the archived dates all agree; ROUND_DIR is never written.

Shortfalls and failures: if any quota is not met the round is written with
status "shortfall" and the command exits with status 2. A shortfall is never accepted:
production `accept` refuses it, and the round is closed with `register-failure` as a
procedure_failure (R4 Addendum 2; failure.py).

Text bytes: each text is archived as lexinspect's normalised form
(lexinspect._text.normalise), with the SHA-256 of the extracted and the
normalised text.

`--replay-development` re-runs the development collection (seed 20261016)
offline against the development cache and checks that it reproduces
.cache/validation/study4/texts.jsonl and the archived text bytes exactly.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import build

from fixcheck import REPO
from fixcheck import freeze as FZ
from fixcheck.common import (
    _command_list,
    canonical_json,
    git_state,
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    sha256_text,
    source_hashes,
    write_json,
    write_jsonl,
    write_step_manifest,
)
from fixcheck.durable import (  # noqa: F401  (re-exported: collect.DurabilityError, ...)
    DurabilityError,
    _write_all,
    durability_method,
    durable_sync,
    fsync_dir,
)
from fixcheck.ledger import LEDGER_COMPONENTS, LEDGER_MD
from fixcheck.registry import REGISTRY as REG_DEFAULT

DELIVERY_SPEC = FZ.FREEZE_DIR / "delivery_spec.json"

FIXCHECK_ACADEMIC_TARGETS = {"sciences": 7, "social_sciences": 7, "humanities": 6}
FIXCHECK_WIKI_TARGET = 20
FIXCHECK_ESSAY_TARGET = 20
FIXCHECK_N = 60
DEV_RAW = build.DEV_OUT / "raw"
POOL_POLICY = (
    "Sampling frame = the development build's pool listings byte for byte: every file in "
    "<dev raw>/pools/ copied into <round raw>/pools/ (existing copies must be identical) at "
    "planning; pools are never re-queried (refresh=False; refresh=True raises "
    "PoolRequeryForbidden); article/page downloads go to the round's own raw cache, never to "
    "the development cache."
)
TARGETS = {
    "academic": FIXCHECK_ACADEMIC_TARGETS,
    "general": FIXCHECK_WIKI_TARGET,
    "argumentative": FIXCHECK_ESSAY_TARGET,
    "total": FIXCHECK_N,
}


class NetworkForbidden(RuntimeError):
    pass


class PoolRequeryForbidden(RuntimeError):
    """build.py tried to re-query a pool: its listing is missing from the round's snapshot."""


def _no_network(*_a: Any, **_k: Any) -> Any:
    raise NetworkForbidden("network access is forbidden in this run (--offline)")


def _offline_fetch(url: str, cache: Path, refresh: bool = False) -> bytes:
    """build.fetch for --offline: cache hits only. build.fetch itself would catch the
    urlopen guard's exception, retry with back-off and re-raise a generic RuntimeError."""
    if cache.exists() and not refresh:
        return cache.read_bytes()
    raise NetworkForbidden(f"network access is forbidden in this run (--offline): {url}")


class ReplayedFetchFailure(RuntimeError):
    """An archived fetch failure, reproduced by replay without any request (audit r2 S3)."""

    def __init__(self, original_class: str, message: str):
        super().__init__(message)
        self.original_class = original_class


class ReplayDivergence(RuntimeError):
    pass


class LedgerReplay:
    """build.fetch for replay: walks the archived ordered request/failure ledger.

    Each call must be the ledger's next entry (URL, cache key, refresh flag). An
    archived failure is raised again as ReplayedFetchFailure with the original class
    and message; an archived success returns the cache file, which must still have
    its archived SHA-256. No request is ever made."""

    replaying = True

    def __init__(self, ledger: list[dict[str, Any]], raw: Path):
        self.ledger = ledger
        self.raw = raw
        self.pos = 0
        self.problems: list[str] = []

    def __call__(self, url: str, cache: Path, refresh: bool = False) -> bytes:
        i = self.pos
        self.pos += 1
        try:
            rel = Path(cache).resolve().relative_to(self.raw.resolve()).as_posix()
        except ValueError:
            rel = str(cache)
        if i >= len(self.ledger):
            self.problems.append(f"call {i}: {url} is not in the archived ledger")
            raise ReplayDivergence(f"replay made more requests than archived: {url}")
        e = self.ledger[i]
        if (e["url"], e["cache"], bool(e["refresh"])) != (url, rel, bool(refresh)):
            self.problems.append(f"call {i}: {url} {rel} differs from ledger entry {e['seq']}")
            raise ReplayDivergence(f"replay diverged from the archived ledger at {i}")
        if "error" in e:
            cls = e.get("error_class") or e["error"].split(":", 1)[0]
            msg = e.get("error_message")
            if msg is None:
                msg = e["error"].split(": ", 1)[1] if ": " in e["error"] else ""
            raise ReplayedFetchFailure(cls, msg)
        f = Path(cache)
        if not f.exists() or sha256_file(f) != e.get("sha256"):
            self.problems.append(f"call {i}: {rel} is missing or differs from the ledger")
            raise ReplayDivergence(f"archived response {rel} is missing or changed")
        return f.read_bytes()

    def finished(self) -> list[str]:
        left = len(self.ledger) - self.pos
        return self.problems + ([f"{left} archived requests were not replayed"] if left else [])


def _no_pool_requery(fetch):
    """Wrap build.fetch: a refresh=True call (a pool query) raises before any request."""

    def guarded(url: str, cache: Path, refresh: bool = False) -> bytes:
        if refresh:
            raise PoolRequeryForbidden(
                "a pool listing is missing from the round's snapshot and build.py tried to "
                f"re-query it: {url}"
            )
        return fetch(url, cache, refresh)

    return guarded


class JournalBarrierFailure(BaseException):  # noqa: N818 - deliberately not an Exception
    """A journal append or its durable barrier failed (audit r4 B1/S2). The execution stops
    at once, before the request: a BaseException, so build.py's per-article
    `except Exception` (a rejected article) can never swallow it and go on to the next
    request. The abort record is still written (_collect_round)."""


class FetchRecorder:
    """Logs every build.fetch and build.wiki_page call of one collection (B6, S5).

    With `journal` (production and dry-run executions; audit r3 B1), every request is
    appended to the journal and made durable (durable_sync, audit r4 B1) BEFORE it is
    made, and its outcome after, so a hard exit or power loss (no exception handler runs)
    still leaves the evidence of each attempt."""

    def __init__(self, raw: Path, journal: Path | None = None):
        self.raw = raw
        self.journal = journal
        self.fetches: list[dict[str, Any]] = []
        self.pages: list[dict[str, Any]] = []

    def _journal(self, entry: dict[str, Any]) -> None:
        if self.journal is not None:
            try:
                append_fsync(self.journal, canonical_json(entry) + "\n")
            except OSError as e:
                raise JournalBarrierFailure(f"{type(e).__name__}: {e}") from e

    def _rel(self, p: Path) -> str:
        try:
            return Path(p).resolve().relative_to(self.raw.resolve()).as_posix()
        except ValueError:
            return str(p)

    def wrap_fetch(self, fetch):
        def recorded(url: str, cache: Path, refresh: bool = False) -> bytes:
            rec: dict[str, Any] = {
                "seq": len(self.fetches),
                "url": url,
                "cache": self._rel(cache),
                "refresh": bool(refresh),
                "cache_hit": bool(Path(cache).exists() and not refresh),
            }
            self._journal({"event": "request", **rec})  # durable before the request
            self.fetches.append(rec)
            try:
                data = fetch(url, cache, refresh)
            except BaseException as e:
                cls = getattr(e, "original_class", type(e).__name__)
                rec["error"] = f"{cls}: {e}"
                rec["error_class"] = cls
                rec["error_message"] = str(e)
                self._journal({"event": "outcome", **rec})
                raise
            rec["sha256"] = hashlib.sha256(data).hexdigest()
            rec["bytes"] = len(data)
            if Path(cache).exists():
                # the original retrieval date, archived here (replay never infers it from mtime)
                rec["mtime_date"] = dt.date.fromtimestamp(Path(cache).stat().st_mtime).isoformat()
            if getattr(fetch, "replaying", False):
                rec.pop("mtime_date", None)
            self._journal({"event": "outcome", **rec})
            return data

        return recorded

    def wrap_wiki_page(self, wiki_page):
        def recorded(title: str, refresh: bool):
            cache = build.RAW / "wiki" / f"{build._key(title)}.json"
            rec: dict[str, Any] = {
                "seq": len(self.pages),
                "requested_title": title,
                "cache": self._rel(cache),
            }
            self.pages.append(rec)
            pg = wiki_page(title, refresh)
            if pg is not None:
                rev = (pg.get("revisions") or [{}])[0]
                rec |= {"pageid": pg.get("pageid"), "revid": rev.get("revid"), "title": pg["title"]}
            else:
                rec["missing"] = True
            return pg

        return recorded


@contextlib.contextmanager
def build_settings(
    seed: int,
    raw: Path,
    exclude: set[str],
    academic: dict[str, int],
    wiki: int,
    essays: int,
    offline: bool,
    recorder: FetchRecorder | None = None,
    replay: LedgerReplay | None = None,
):
    """Temporarily set build.py's module-level settings (restored afterwards)."""
    names = ("SEED", "RAW", "EXCLUDE", "ACADEMIC_TARGETS", "WIKI_TARGET", "ESSAY_TARGET")
    old = {n: getattr(build, n) for n in names}
    old_open = build.urllib.request.urlopen
    old_fetch = build.fetch
    old_page = build.wiki_page
    try:
        build.SEED, build.RAW, build.EXCLUDE = seed, raw, set(exclude)
        build.ACADEMIC_TARGETS = dict(academic)
        build.WIKI_TARGET, build.ESSAY_TARGET = wiki, essays
        if offline or replay is not None:
            build.urllib.request.urlopen = _no_network  # belt and braces
        if replay is not None:
            fetch = replay  # the ledger reproduces every archived outcome, pool guard included
        else:
            fetch = _no_pool_requery(_offline_fetch if offline else old_fetch)
        if recorder is not None:
            fetch = recorder.wrap_fetch(fetch)
            build.wiki_page = recorder.wrap_wiki_page(old_page)
        build.fetch = fetch
        yield
    finally:
        for n, v in old.items():
            setattr(build, n, v)
        build.urllib.request.urlopen = old_open
        build.fetch = old_fetch
        build.wiki_page = old_page


def earlier_exclusions(dirs: list[Path], round_no: int) -> tuple[set[str], list[dict[str, Any]]]:
    """Every identifier of every earlier fix-check round's texts, after checking each manifest."""
    refs: set[str] = set()
    info = []
    rounds = []
    for d in dirs:
        from fixcheck import failure as FL

        if FL.failure_closed(d):
            # a registered procedure_failure (audit r4 S1): its authenticated exposure
            # inventory is excluded; refused if the exposure cannot be established
            ex = FL.exposure_inventory(d)
            if not ex["complete"]:
                raise SystemExit(
                    f"{d}: the failed round's exposure cannot be established "
                    f"({ex['problems'][:3]}): no later round; only terminal outcomes remain"
                )
            fr = read_json(d / "freeze_record.json")
            refs |= set(ex["refs"])
            rounds.append(fr["round"])
            info.append(
                {
                    "dir": str(d),
                    "round": fr["round"],
                    "seed": fr["seed"],
                    "status": FL.STATUS,
                    "freeze_record_sha256": sha256_file(d / "freeze_record.json"),
                    "execution_start_sha256": sha256_file(d / EXEC_START),
                    "exposure_sha256": ex["exposure_sha256"],
                    "production_eligible": fr.get("production_eligible", False),
                    "n_refs": len(ex["refs"]),
                }
            )
            continue
        col = read_json(d / "collection.json")
        texts_path = d / "texts.jsonl"
        digest = sha256_file(texts_path)
        if digest != col["texts_jsonl_sha256"]:
            raise SystemExit(f"{texts_path}: sha256 {digest} != collection.json's record")
        r = build.read_exclusions(texts_path)
        refs |= r
        rounds.append(col["round"])
        fr = d / "freeze_record.json"
        info.append(
            {
                "dir": str(d),
                "round": col["round"],
                "seed": col["seed"],
                "texts_jsonl_sha256": digest,
                "collection_json_sha256": sha256_file(d / "collection.json"),
                "freeze_record_sha256": sha256_file(fr) if fr.exists() else None,
                "production_eligible": col.get("production_eligible", False),
                "n_texts": len(read_jsonl(texts_path)),
                "n_refs": len(r),
            }
        )
    if sorted(rounds) != list(range(1, round_no)):
        raise SystemExit(
            f"round {round_no} needs exactly the manifests of rounds 1..{round_no - 1}; got {sorted(rounds)}"
        )
    return refs, info


def snapshot_pools(dev_raw: Path, raw: Path) -> list[dict[str, Any]]:
    src = dev_raw / "pools"
    if not src.is_dir():
        raise SystemExit(f"pool snapshot source {src} not found")
    dst = raw / "pools"
    dst.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(src.glob("*.json")):
        target = dst / f.name
        if target.exists():
            if target.read_bytes() != f.read_bytes():
                raise SystemExit(f"{target} differs from the development pool listing {f}")
        else:
            shutil.copyfile(f, target)
        out.append({"file": f"pools/{f.name}", "sha256": sha256_file(target)})
    extra = sorted({p.name for p in dst.glob("*.json")} - {f.name for f in src.glob("*.json")})
    if extra:
        raise SystemExit(f"{dst} holds pool listings not in the development snapshot: {extra}")
    return out


def collect_with_build(
    seed: int,
    raw: Path,
    exclude: set[str],
    academic: dict[str, int],
    wiki: int,
    essays: int,
    offline: bool,
    recorder: FetchRecorder | None = None,
    replay: LedgerReplay | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    log: dict[str, Any] = {}
    with build_settings(seed, raw, exclude, academic, wiki, essays, offline, recorder, replay):
        texts = (
            build.collect_academic(False, log)
            + build.collect_wiki("general", False, log)
            + build.collect_wiki("essays", False, log)
        )
        overlap = build.exclusion_overlap(texts, set(exclude))
    if overlap:
        raise SystemExit(f"collected texts overlap the exclusion set: {overlap[:5]}")
    ids = [t["source_id"] for t in texts]
    if len(set(ids)) != len(ids):
        raise SystemExit("a source was collected twice")
    return texts, log


def shortfalls(
    texts: list[dict[str, Any]], academic: dict[str, int], wiki: int, essays: int
) -> dict[str, dict[str, int]]:
    got_d = Counter(t["discipline"] for t in texts if t["register"] == "academic")
    got_r = Counter(t["register"] for t in texts)
    want = {f"academic/{d}": n for d, n in academic.items()} | {
        "general": wiki,
        "argumentative": essays,
    }
    have = {f"academic/{d}": got_d.get(d, 0) for d in academic} | {
        "general": got_r.get("general", 0),
        "argumentative": got_r.get("argumentative", 0),
    }
    return {k: {"target": want[k], "got": have[k]} for k in want if have[k] < want[k]}


def raw_files_of(
    texts: list[dict[str, Any]], raw: Path, rec: FetchRecorder
) -> list[dict[str, Any]]:
    """The exact archived response behind each selected text (B6).

    Europe PMC: the cache file of <pmcid>.xml. Wikipedia: the cache file of the
    first wiki_page call that returned the text's page id and revision id (the
    file is keyed by the REQUESTED title). Refuses if no logged call matches."""
    out = []
    for t in texts:
        if t["source"] == "Europe PMC":
            cache = f"epmc/{t['source_id']}.xml"
            entry = {"text_id": t.get("text_id"), "source": t["source"], "file": cache}
            entry["url"] = t["fulltext_url"]
        else:
            pageid = int(str(t["source_id"]).split(":", 1)[1])
            match = [
                p
                for p in rec.pages
                if p.get("pageid") == pageid and p.get("revid") == t.get("revid")
            ]
            if not match:
                raise SystemExit(
                    f"{t['source_id']} rev {t.get('revid')}: no logged wiki_page call returned it"
                )
            p = match[0]
            cache = p["cache"]
            entry = {
                "text_id": t.get("text_id"),
                "source": t["source"],
                "file": cache,
                "requested_title": p["requested_title"],
                "canonical_title": p["title"],
                "pageid": pageid,
                "revid": t.get("revid"),
                "wiki_page_seq": p["seq"],
                "other_titles_same_page": sorted(
                    {q["requested_title"] for q in rec.pages if q.get("pageid") == pageid}
                    - {p["requested_title"]}
                ),
            }
        f = raw / cache
        if not f.exists():
            raise SystemExit(f"{t['source_id']}: archived response {f} is missing")
        entry["sha256"] = sha256_file(f)
        fetched = [x for x in rec.fetches if x["cache"] == cache and "sha256" in x]
        entry["fetch_seq"] = [x["seq"] for x in fetched]
        if fetched and {x["sha256"] for x in fetched} != {entry["sha256"]}:
            raise SystemExit(f"{cache}: the response file changed during the collection")
        entry["retrieved_metadata"] = t.get("retrieved")
        out.append(entry)
    return out


def finish_texts(texts: list[dict[str, Any]], round_no: int | None) -> list[dict[str, Any]]:
    """Text ids, normalised text and hashes (lexinspect._text.normalise, as the dev build stored)."""
    from lexinspect._text import normalise

    for i, t in enumerate(texts):
        t["text_id"] = f"T{i + 1:03d}"
        t["extracted_sha256"] = sha256_text(t["text"])
        t["text"] = normalise(t["text"])
        t["text_sha256"] = sha256_text(t["text"])
        t["n_chars"] = len(t["text"])
        if round_no is not None:
            t["fixcheck_round"] = round_no
    return texts


def replay_development(out: Path, dev_raw: Path, overwrite: bool) -> int:
    refuse_existing(out / "replay.json", overwrite)
    out.mkdir(parents=True, exist_ok=True)
    before = sorted(str(p.relative_to(dev_raw)) for p in dev_raw.rglob("*") if p.is_file())
    texts, _ = collect_with_build(
        build.DEV_SEED,
        dev_raw,
        set(),
        dict(build.ACADEMIC_TARGETS),
        build.WIKI_TARGET,
        build.ESSAY_TARGET,
        offline=True,
    )
    after = sorted(str(p.relative_to(dev_raw)) for p in dev_raw.rglob("*") if p.is_file())
    dev = read_jsonl(build.DEV_TEXTS)
    texts = finish_texts(texts, None)
    problems = []
    if len(texts) != len(dev):
        problems.append(f"{len(texts)} texts replayed, {len(dev)} in the development manifest")
    for t, d in zip(texts, dev, strict=False):
        meta = {k: v for k, v in t.items() if k not in ("text", "extracted_sha256", "text_sha256")}
        if meta != d:
            diff = sorted(k for k in set(meta) | set(d) if meta.get(k) != d.get(k))
            problems.append(f"{d['text_id']}: metadata differs in {diff}")
        archived = (build.DEV_OUT / "texts" / f"{d['text_id']}.txt").read_text(encoding="utf-8")
        if t["text"] != archived:
            problems.append(f"{d['text_id']}: normalised text differs from the archived bytes")
    rec = {
        "replayed_texts": len(texts),
        "development_manifest": str(build.DEV_TEXTS),
        "development_manifest_sha256": sha256_file(build.DEV_TEXTS),
        "identical": not problems,
        "problems": problems,
        "dev_cache_files_unchanged": before == after,
        "production_eligible": False,
    }
    write_json(out / "replay.json", rec)
    write_step_manifest(out, "replay_development", [out / "replay.json"])
    print(
        f"replay: identical={rec['identical']} cache_unchanged={rec['dev_cache_files_unchanged']}"
    )
    return 0 if rec["identical"] and rec["dev_cache_files_unchanged"] else 1


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    """The exact text write_jsonl writes for `rows`."""
    import json

    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def _exclusions(dev_texts: Path, earlier: list[Path], round_no: int):
    dev_refs, dev_info = build.load_dev_exclusions(dev_texts)
    earlier_refs, earlier_info = earlier_exclusions(earlier, round_no)
    exclude = dev_refs | earlier_refs
    digest = hashlib.sha256("\n".join(sorted(exclude)).encode()).hexdigest()
    return exclude, dev_info, earlier_info, digest


def _fetch_sig(f: dict[str, Any]) -> list[Any]:
    """The meaningful part of a fetch-log entry (no file dates): request, outcome, failure."""
    return [
        f["seq"],
        f["url"],
        f["cache"],
        f["refresh"],
        f.get("sha256"),
        f.get("error_class"),
        f.get("error_message"),
    ]


def authenticate_raw(col: dict[str, Any], raw: Path) -> list[str]:
    """S5: every logged response and every selected raw file still has its archived hash."""
    problems = []
    log = col.get("fetch_log", [])
    if [f.get("seq") for f in log] != list(range(len(log))):
        problems.append("the fetch ledger is not one ordered sequence")
    for f in log:
        if "sha256" not in f:
            later_ok = any(g["cache"] == f["cache"] and "sha256" in g for g in log)
            if not later_ok and (raw / f["cache"]).exists():
                problems.append(
                    f"fetch {f['seq']}: failed, but {f['cache']} now exists in the raw cache"
                )
            if "error" not in f:
                problems.append(f"fetch {f['seq']}: neither a response hash nor a failure")
            continue
        p = raw / f["cache"]
        if not p.exists():
            problems.append(f"fetch {f['seq']}: {f['cache']} is missing")
        elif sha256_file(p) != f["sha256"]:
            problems.append(f"fetch {f['seq']}: {f['cache']} differs from its archived hash")
    for r in col.get("raw_files", []):
        p = raw / r["file"]
        if not p.exists() or sha256_file(p) != r["sha256"]:
            problems.append(f"{r['text_id']}: raw file {r['file']} is missing or changed")
    return problems


def replay_round(round_dir: Path, out: Path, raw_override: Path | None, overwrite: bool) -> int:
    """Re-collect an archived round offline from its own cache; authenticate and compare it."""
    if out == round_dir:
        raise SystemExit("--out must not be the round being replayed")
    refuse_existing(out / "replay.json", overwrite)
    fr_path, col_path = round_dir / "freeze_record.json", round_dir / "collection.json"
    fr, col = read_json(fr_path), read_json(col_path)
    if sha256_file(fr_path) != col["freeze_record_sha256"]:
        raise SystemExit(f"{fr_path} does not match collection.json's record")
    if sha256_file(round_dir / "texts.jsonl") != col["texts_jsonl_sha256"]:
        raise SystemExit(f"{round_dir / 'texts.jsonl'} does not match collection.json's record")
    raw = (raw_override or Path(fr["paths"]["raw_cache"])).resolve()
    auth = authenticate_raw(col, raw)
    if auth:
        raise SystemExit(f"archived raw responses do not authenticate: {auth[:5]}")
    exclude, dev_info, earlier_info, digest = _exclusions(
        Path(fr["paths"]["dev_texts"]), [Path(d) for d in fr["paths"]["earlier"]], fr["round"]
    )
    if dev_info["sha256"] != fr["dev_manifest"]["sha256"]:
        raise SystemExit("the development manifest differs from the one archived for the round")
    if canonical_json(earlier_info) != canonical_json(fr["earlier_rounds"]):
        raise SystemExit("an earlier round changed since the round was collected")
    if digest != fr["exclusions"]["refs_sha256"]:
        raise SystemExit("the recomputed exclusion set differs from the archived one")
    pools_now = sorted((f"pools/{f.name}", sha256_file(f)) for f in (raw / "pools").glob("*.json"))
    if pools_now != sorted((d["file"], d["sha256"]) for d in fr["pool_inventory"]):
        raise SystemExit(f"{raw / 'pools'} differs from the archived pool snapshot")
    tg = fr["targets"]
    before = sorted(str(p.relative_to(raw)) for p in raw.rglob("*") if p.is_file())
    rec = FetchRecorder(raw)
    ledger = LedgerReplay(col["fetch_log"], raw)
    texts, log = collect_with_build(
        fr["seed"],
        raw,
        exclude,
        dict(tg["academic"]),
        tg["general"],
        tg["argumentative"],
        offline=True,
        recorder=rec,
        replay=ledger,
    )
    after = sorted(str(p.relative_to(raw)) for p in raw.rglob("*") if p.is_file())
    texts = finish_texts(texts, fr["round"])
    archived = read_jsonl(round_dir / "texts.jsonl")
    rows = [{k: v for k, v in t.items() if k != "text"} for t in texts]
    text_problems, meta_diffs = [], []
    if len(rows) != len(archived):
        text_problems.append(f"{len(rows)} texts replayed, {len(archived)} archived")
    archived_dates = {}
    for m in col.get("raw_files", []):
        dates = {
            f.get("mtime_date")
            for f in col["fetch_log"]
            if f["cache"] == m["file"] and "sha256" in f and f.get("mtime_date")
        }
        archived_dates[m["text_id"]] = sorted(dates)
    date_problems = []
    for a in archived:
        want = archived_dates.get(a["text_id"]) or []
        if want and a.get("retrieved") not in want:
            date_problems.append(
                f"{a['text_id']}: archived retrieved {a.get('retrieved')} is not the ledger's "
                f"retrieval date {want}"
            )
    for r, a in zip(rows, archived, strict=False):
        diff = sorted(k for k in set(r) | set(a) if r.get(k) != a.get(k))
        if [k for k in diff if k != "retrieved"]:
            text_problems.append(f"{a['text_id']}: differs in {diff}")
        elif diff:
            meta_diffs.append(
                {
                    "text_id": a["text_id"],
                    "field": "retrieved",
                    "archived": a.get("retrieved"),
                    "archived_ledger_date": archived_dates.get(a["text_id"]),
                    "replayed": r.get("retrieved"),
                    "cause": "cache file modification date (build.py); the archived date is "
                    "the original fetch ledger's",
                }
            )
    for t in texts:
        f = round_dir / "texts" / f"{t['text_id']}.txt"
        if not f.exists() or f.read_bytes() != t["text"].encode("utf-8"):
            text_problems.append(f"{t['text_id']}: text bytes differ from {f}")
    log_problems = [f"ledger: {x}" for x in ledger.finished()] + date_problems
    if canonical_json(log) != canonical_json(col["selection_log"]):
        log_problems.append("the selection log differs")
    if [_fetch_sig(f) for f in rec.fetches] != [_fetch_sig(f) for f in col["fetch_log"]]:
        log_problems.append("the fetch log differs")
    if canonical_json(rec.pages) != canonical_json(col["wiki_page_log"]):
        log_problems.append("the wiki_page log differs")
    try:
        mapping = raw_files_of(texts, raw, rec)
        strip = ("retrieved_metadata",)
        same_map = [{k: v for k, v in m.items() if k not in strip} for m in mapping] == [
            {k: v for k, v in m.items() if k not in strip} for m in col["raw_files"]
        ]
        if not same_map:
            log_problems.append("the text-to-raw-response mapping differs")
    except SystemExit as e:
        log_problems.append(f"raw mapping: {e}")
    jsonl_identical = _jsonl_text(rows).encode("utf-8") == (round_dir / "texts.jsonl").read_bytes()
    rec_out = {
        "round_dir": str(round_dir),
        "round": fr["round"],
        "seed": fr["seed"],
        "raw_cache": str(raw),
        "raw_responses_authenticated": True,
        "replayed_texts": len(texts),
        "texts_jsonl_sha256": col["texts_jsonl_sha256"],
        "texts_jsonl_identical": jsonl_identical,
        "text_reproducible": not text_problems,
        "text_problems": text_problems,
        "metadata_differences": meta_diffs,
        "metadata_note": "build.py derives `retrieved` from the cache file's modification date; "
        "the archived date is the original fetch ledger's mtime_date, which texts.jsonl must "
        "match (archived_dates_consistent)",
        "archived_dates_consistent": not date_problems,
        "replay_method": "archived ordered request/failure ledger (LedgerReplay): every request "
        "matched in order, every archived failure reproduced without a request",
        "logs_identical": not log_problems,
        "log_problems": log_problems,
        "identical": not text_problems and not log_problems,
        "problems": text_problems + log_problems,
        "cache_files_unchanged": before == after,
        "offline": True,
        "production_eligible": fr.get("production_eligible", False),
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "replay.json", rec_out)
    write_step_manifest(out, "replay_round", [out / "replay.json"])
    print(
        f"replay round {fr['round']}: text_reproducible={rec_out['text_reproducible']} "
        f"logs_identical={rec_out['logs_identical']} metadata_differences={len(meta_diffs)}"
    )
    return 0 if rec_out["identical"] and rec_out["cache_files_unchanged"] else 1


# --- freeze record ------------------------------------------------------------------


def _paths(args: argparse.Namespace) -> dict[str, Any]:
    out = args.out.resolve()
    return {
        "out": str(out),
        "raw_cache": str((args.raw_cache or out / "raw").resolve()),
        "dev_raw": str(args.dev_raw.resolve()),
        "dev_texts": str(args.dev_texts.resolve()),
        "earlier": [str(d.resolve()) for d in args.earlier],
    }


def execution_argv_of_plan(cmd: list[str], record_path: Path) -> list[str]:
    """The literal execution argv: the planning argv without --plan-only and --overwrite,
    with --execute --freeze-record <path> appended."""
    keep = [a for a in cmd if a not in ("--plan-only", "--overwrite")]
    return [*keep, "--execute", "--freeze-record", str(record_path)]


def authenticate_collection(d: Path) -> list[str]:
    """An archived round collection is self-consistent and every output is as recorded."""
    p: list[str] = []
    for f in ("freeze_record.json", "collection.json", "execution.json", "texts.jsonl"):
        if not (d / f).exists():
            return [f"{d / f} missing"]
    col = read_json(d / "collection.json")
    if col.get("freeze_record_sha256") != sha256_file(d / "freeze_record.json"):
        p.append("collection.json does not name its freeze record")
    if col.get("texts_jsonl_sha256") != sha256_file(d / "texts.jsonl"):
        p.append("texts.jsonl differs from collection.json")
    ex = read_json(d / "execution.json")
    if ex.get("collection_json_sha256") != sha256_file(d / "collection.json"):
        p.append("execution.json does not name collection.json")
    for t in read_jsonl(d / "texts.jsonl"):
        f = d / "texts" / f"{t['text_id']}.txt"
        if not f.exists() or sha256_text(f.read_text(encoding="utf-8")) != t["text_sha256"]:
            p.append(f"{t['text_id']}: text bytes differ from texts.jsonl")
    p += execution_record_problems(d, ex, read_json(d / "freeze_record.json"), col)
    m = d / "manifest_collect.json"
    if not m.exists():
        p.append("manifest_collect.json missing")
    else:
        for rel, e in read_json(m)["outputs"].items():
            if not (d / rel).exists() or sha256_file(d / rel) != e["sha256"]:
                p.append(f"{rel} differs from manifest_collect.json")
    return p


def execution_record_problems(
    d: Path, ex: dict[str, Any], fr: dict[str, Any], col: dict[str, Any]
) -> list[str]:
    """The single-execution evidence of a collected round (audit r3 B1): the start record
    exists (required for a production record; checked whenever present), is the one
    execution.json names, is bound to this freeze record, reservation and argv; no abort
    record exists; the durable journal is a valid request/outcome stream that reconstructs
    the fetch log (journal_problems)."""
    start_path = d / EXEC_START
    if not start_path.exists():
        return (
            ["execution_start.json missing (no single-execution claim)"]
            if fr.get("production_eligible")
            else []
        )
    p = []
    st = read_json(start_path)
    if st.get("kind") != START_KIND:
        p.append("execution_start.json is not an execution-start record")
    if ex.get("execution_start_sha256") != sha256_file(start_path):
        p.append("execution.json does not name execution_start.json")
    if st.get("freeze_record_sha256") != sha256_file(d / "freeze_record.json"):
        p.append("execution_start.json does not name this freeze record")
    if st.get("reservation_sha256") != (fr.get("registry") or {}).get("reservation_sha256"):
        p.append("execution_start.json does not name the freeze record's reservation")
    if fr.get("production_eligible") and st.get("mode") != "execute":
        p.append("a production round was not executed with --execute")
    if st.get("mode") == "execute" and st.get("argv") != fr.get("execution_argv"):
        p.append("execution_start.json's argv is not the recorded execution argv")
    if (d / EXEC_ABORT).exists():
        p.append("execution_abort.json exists: the execution aborted")
    p += journal_problems(d / FETCH_JOURNAL, col.get("fetch_log", []))
    journal = d / FETCH_JOURNAL
    if journal.exists() and ex.get("fetch_journal_sha256") != sha256_file(journal):
        p.append("execution.json does not name fetch_journal.jsonl")
    return p


def _registry_part(args: argparse.Namespace, cand: dict[str, Any]) -> dict[str, Any]:
    """The registry identity and this round's reservation (read only; audit r2 B2)."""
    from fixcheck import registry as REG

    if args.registry is None:
        return {"path": None, "sha256": None, "reservation_sha256": None, "problems": ["none"]}
    path = args.registry.resolve()
    entries = REG.load(path)
    want = reservation_of(args, cand)
    found = [
        e
        for e in REG.reservations(entries)
        if all(e.get(k) == v for k, v in want.items() if k != "type")
    ]
    integ = REG.integrity(path, REPO)
    return {
        "path": str(path),
        "sha256": integ.get("sha256"),
        "n_entries": len(entries),
        "reservation": found[0] if found else None,
        "reservation_sha256": REG.entry_sha256(found[0]) if found else None,
        "problems": integ["problems"],
    }


def reservation_of(args: argparse.Namespace, cand: dict[str, Any]) -> dict[str, Any]:
    out = args.out.resolve()
    try:
        cdir = out.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        cdir = str(out)
    return {
        "type": "reservation",
        "round": args.round,
        "candidate_commit": cand.get("commit"),
        "candidate_tree_sha256": cand.get("tree_sha256"),
        "seed": args.seed,
        "collect_dir": cdir,
    }


def round1_bound_problems(fr1: dict[str, Any]) -> list[str]:
    """Round 1's bound files must still be byte-equal to round 1's freeze record (gap G1):
    the ledger Markdown and components, the protocol, the clarifications and every `bound`
    file except the append-only registry. Round 1 stays re-checkable (clarifications 3.3:
    every other receipted file stays byte-equal)."""
    led = fr1.get("ledger") or {}
    files: list[tuple[str, Any]] = [
        ("ledger Markdown", led.get("markdown")),
        ("ledger components", led.get("components")),
        ("protocol", fr1.get("protocol")),
        ("clarifications", fr1.get("clarifications")),
    ]
    for name, b in sorted((fr1.get("bound") or {}).items()):
        if name != "registry":
            files += [(name.replace("_", " "), f) for f in (b if isinstance(b, list) else [b])]
    p = []
    for name, f in files:
        if not isinstance(f, dict) or not f.get("path") or not f.get("sha256"):
            continue  # nothing was bound under this name
        path = Path(f["path"])
        now = sha256_file(path) if path.is_file() else None
        if now != f["sha256"]:
            how = "is missing" if now is None else "has changed"
            p.append(f"round 1's {name} {path} {how} since round 1's freeze record")
    return p


# The harness sources a receipt lists under this prefix (fixcheck/*.py) are the reviewed
# round-2 harness changes: disclosed (round2.harness_changed_vs_round1) and bound by the
# round-2 freeze record, so round 1's receipted versions of them are not compared (G1).
HARNESS_RECEIPT_PREFIX = "scripts/validation/study4_precision/fixcheck/"
ROUND1_RECEIPTED = ("command.txt", "manifest_plan.json")


def _reviewed_harness_entry(rel: str) -> bool:
    if not rel.startswith(HARNESS_RECEIPT_PREFIX):
        return False
    rest = rel[len(HARNESS_RECEIPT_PREFIX) :]
    return "/" not in rest and rest.endswith(".py")


def round1_receipted_problems(d: Path, fr1: dict[str, Any]) -> list[str]:
    """Round 1's receipted plan files stay present and byte-equal (gap G1, audit of the
    round-2 harness r1 finding 2): command.txt and manifest_plan.json are required.

    A production round 1: the archive receipt its execution gate checked (in the start
    record, execution_start.json) is re-validated against the committed objects
    (freeze.verify_receipt: the receipt commit, its receipt ref and origin URL, each listed
    file's historical git blob), and every listed file must still be byte-equal on disk,
    except the append-only registry (checked as an extension of its receipted version) and
    the reviewed round-2 harness sources fixcheck/*.py. The frozen Study 4 inputs stay
    compared (G4 refuses them separately). A dry-run round 1 has no receipt: its
    manifest_plan.json must still list command.txt and the freeze record with their
    hashes (self-consistency only)."""
    from fixcheck.package import check_manifest

    p = [
        f"round 1's receipted {n} {d / n} is missing"
        for n in ROUND1_RECEIPTED
        if not (d / n).is_file()
    ]
    if not fr1.get("production_eligible"):
        if not p:
            p += [
                f"round 1's {x}"
                for x in check_manifest(d, "plan", ["freeze_record.json", "command.txt"])
            ]
        return p
    st_path = d / EXEC_START
    try:
        st = read_json(st_path) if st_path.is_file() else None
    except (OSError, ValueError):
        st = None
    receipt = ((st or {}).get("gate") or {}).get("receipt") if isinstance(st, dict) else None
    if not receipt:
        return [*p, f"round 1's execution receipt is unavailable ({st_path} unreadable or absent)"]
    files = receipt.get("files") or {}
    kept = {rel: f for rel, f in files.items() if not _reviewed_harness_entry(rel)}
    want = [d / "freeze_record.json", *(d / n for n in ROUND1_RECEIPTED)]
    p += [
        f"round 1's execution receipt: {x}"
        for x in FZ.verify_receipt(dict(receipt, files=kept), want=want)
    ]
    for w in want:
        rel = FZ._rel(w, FZ.REPO)
        expected = (files.get(rel) or {}).get("sha256") if rel else None
        if not expected or not w.is_file() or sha256_file(w) != expected:
            p.append(f"round 1's receipted {rel or w} is missing or changed")
    return p


def round1_preservation_problems(d: Path) -> list[str]:
    """Round 1 stays as it was frozen and receipted (gap G1): the files its freeze record
    binds (round1_bound_problems) and its receipted plan files and receipt
    (round1_receipted_problems). Shared by round-2 planning (_round2_part, so execution
    rechecks it too) and the round-2 package check (package.check_collect), where any
    problem is a chain problem: inconclusive, never a pass or a fail
    (package.round2_chain_problems; accept.compute, audit r2 N2)."""
    d = Path(d).resolve()
    fp = d / "freeze_record.json"
    if not fp.is_file():
        return [f"round 1's freeze record {fp} is missing"]
    fr1 = read_json(fp)
    return round1_bound_problems(fr1) + round1_receipted_problems(d, fr1)


def same_ledger_as_round1(ledger_md: Path, fr1: dict[str, Any], dry_run: bool) -> bool:
    """Round 2 names round 1's ledger file (gap G1): refused for a production plan and for
    any plan whose round 1 is production-eligible (so the round-2 preflight against the real
    round 1 sees it); a dry run of a dry-run round 1 keeps the default ledger."""
    r1_ledger = ((fr1.get("ledger") or {}).get("markdown") or {}).get("path")
    if not r1_ledger or (dry_run and not fr1.get("production_eligible")):
        return False
    return Path(ledger_md).resolve() == Path(r1_ledger).resolve()


def harness_vs_round1(fr1: dict[str, Any]) -> list[str]:
    """The harness files that differ from round 1's freeze (gap G4, for disclosure). Refuses
    if any frozen Study 4 input (every non-fixcheck entry of source_hashes) differs."""
    now, then = source_hashes(), fr1.get("sources_sha256") or {}
    keys = sorted(set(now) | set(then))
    frozen = [k for k in keys if not k.startswith("fixcheck/") and now.get(k) != then.get(k)]
    if frozen:
        raise SystemExit(
            f"round 2 refused: the frozen Study 4 inputs {frozen} differ from round 1's "
            "freeze record (they must be unchanged)"
        )
    return [k for k in keys if k.startswith("fixcheck/") and now.get(k) != then.get(k)]


def candidate_changes(r1: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any] | None:
    """The round-2 candidate's src/lexinspect against round 1's, from git objects (gap G2,
    for disclosure): changed, added and removed files and both tree digests. None when
    either commit is not in the repository."""
    if not cand.get("commit") or not r1.get("candidate_commit"):
        return None
    try:
        a = FZ.commit_src_digest(r1["candidate_commit"])
        b = FZ.commit_src_digest(cand["commit"])
    except FZ.FreezeError:
        return None
    fa, fb = a["files"], b["files"]
    return {
        "round1_commit": a["commit"],
        "round1_tree_sha256": a["tree_sha256"],
        "round1_tree_matches_registry": a["tree_sha256"] == r1.get("candidate_tree_sha256"),
        "candidate_commit": b["commit"],
        "candidate_tree_sha256": b["tree_sha256"],
        "root": a["root"],
        "changed": sorted(f for f in set(fa) & set(fb) if fa[f] != fb[f]),
        "added": sorted(set(fb) - set(fa)),
        "removed": sorted(set(fa) - set(fb)),
    }


def narrowing_check_identity(
    path: Path | None,
    cand: dict[str, Any],
    round1_candidate: dict[str, Any],
    ledger_md: Path,
    sources_sha256: dict[str, str],
) -> dict[str, Any]:
    """The round-2 narrowing check (gap G10; narrowing.py): its file identity and tracking
    state, and its validation problems against this round's candidate, round 1's registered
    candidate, the ledger and the harness. Bound in the freeze record (and receipted), so
    the execution's rebuilt record re-validates it."""
    from fixcheck import narrowing as NC

    return {
        **FZ.file_identity(path),
        **FZ.tracking_identity(path),
        "problems": NC.file_problems(
            path,
            candidate=cand,
            round1_candidate=round1_candidate,
            ledger_md_sha256=sha256_file(ledger_md) if ledger_md.is_file() else None,
            sources_sha256=sources_sha256,
            dev_texts_sha256=build.DEV_TEXTS_SHA256,
            dev_round_texts_sha256=NC.dev_round_texts_sha256(build.DEV_TEXTS),
        ),
    }


def _round2_part(args: argparse.Namespace, cand: dict[str, Any] | None = None) -> dict[str, Any]:
    """Round 2 is bound to the REGISTERED round 1 (audit r2 B2): --earlier must be exactly
    that round's collection, authenticated, with its texts, freeze record and seed.

    Round-2 hardening (HARNESS_ROUND2_RULINGS.md): round 1's bound files must be unchanged
    (G1), the round-2 ledger must not be round 1's ledger file (G1; for a production plan,
    and for any plan whose round 1 is production-eligible), and the frozen Study 4 inputs
    must equal round 1's (G4). The record discloses the harness files changed since round 1
    (G4), the candidate's changes against round 1 (G2), and the narrowing disposition's and
    the ledger's tracking state (G2, checked by freeze.round2_problems)."""
    from fixcheck import registry as REG

    entries = REG.load(args.registry.resolve()) if args.registry else []
    r1 = REG.round1_entry(entries)
    if r1 is None or r1["status"] == "pass":
        raise SystemExit("round 2 needs a registered round-1 non-pass decision")
    if len(args.earlier) != 1:
        raise SystemExit("round 2 needs exactly one --earlier: the registered round 1")
    d = args.earlier[0].resolve()
    if r1["status"] == "procedure_failure":
        # audit r4 S1: round 1 failed; its failure evidence and exposure are authenticated
        from fixcheck import failure as FL

        ident, probs = FL.authenticate_failed_round(d, r1)
        ident_r = {k: r1.get(k) for k in ("freeze_record_sha256", "seed")}
        bad = [k for k, v in ident_r.items() if ident.get(k) != v]
        if bad:
            probs.append(f"--earlier is not the registered round 1 (differs in {bad})")
        if probs:
            raise SystemExit(f"round 2 after a round-1 procedure_failure refused: {probs}")
    else:
        auth = authenticate_collection(d)
        if auth:
            raise SystemExit(f"the earlier round does not authenticate: {auth[:5]}")
        col = read_json(d / "collection.json")
        ident = {
            "collection_texts_sha256": sha256_file(d / "texts.jsonl"),
            "freeze_record_sha256": sha256_file(d / "freeze_record.json"),
            "seed": col["seed"],
        }
        bad = [k for k, v in ident.items() if r1.get(k) != v]
        if bad:
            raise SystemExit(f"--earlier is not the registered round 1 (differs in {bad})")
    # round 1's freeze record, authenticated above against the registered round 1
    fr1 = read_json(d / "freeze_record.json")
    probs = round1_preservation_problems(d)
    if probs:
        raise SystemExit(
            f"round 2 refused: round 1's bound and receipted files must stay byte-equal "
            f"(G1): {probs}"
        )
    if same_ledger_as_round1(args.ledger_md, fr1, bool(args.dry_run)):
        raise SystemExit(
            f"round 2 refused: --ledger-md {args.ledger_md} is round 1's ledger; round 2 needs "
            "its own ledger file (docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md)"
        )
    harness_changed = harness_vs_round1(fr1)
    cand = cand or {}
    nd = args.narrowing_disposition.resolve() if args.narrowing_disposition else None
    comps = args.ledger_components.resolve() if args.ledger_components else None
    r1_cand = {"commit": r1.get("candidate_commit"), "tree_sha256": r1.get("candidate_tree_sha256")}
    nc = narrowing_check_identity(
        args.narrowing_check.resolve() if args.narrowing_check else None,
        cand,
        r1_cand,
        args.ledger_md.resolve(),
        source_hashes(),
    )
    return {
        "round1_entry_sha256": REG.entry_sha256(r1),
        "earlier_identity": ident,
        "narrowing_disposition": FZ.disposition_identity(nd, cand.get("commit"), None, nc),
        "round1_candidate": r1_cand,  # the registered round-1 entry's (the comparison)
        "narrowing_check": nc,
        "tracking": {
            "ledger_markdown": FZ.tracking_identity(args.ledger_md.resolve()),
            "ledger_components": FZ.tracking_identity(comps),
        },
        "candidate_changes_vs_round1": candidate_changes(r1, cand),
        "harness_changed_vs_round1": harness_changed,
    }


def _delivery_part(args: argparse.Namespace) -> dict[str, Any]:
    """The registered delivery: spec identity, routes, prompt, preregistration, pilot hashes."""
    from fixcheck import sessions as S

    path = args.delivery_spec.resolve() if args.delivery_spec else None
    if path is None or not path.exists():
        return {"path": None, "problems": ["delivery spec missing"]}
    spec = read_json(path)
    return {
        "path": str(path),
        "spec_sha256": spec.get("spec_sha256"),
        "roles": spec.get("roles"),
        "prompt_template_sha256": spec.get("prompt_template_sha256"),
        "prompt_source": spec.get("prompt_source"),
        "materials": spec.get("materials"),
        "pilot_hashes": spec.get("pilot_hashes"),
        "problems": S.check_spec(spec, prereg=args.preregistration.resolve()),
    }


def build_record(args: argparse.Namespace, execution_argv: list[str]) -> dict[str, Any]:
    """The freeze record as recomputed from one invocation (no side effects)."""
    paths = _paths(args)
    raw = Path(paths["raw_cache"])
    exclude, dev_info, earlier_info, digest = _exclusions(
        Path(paths["dev_texts"]), [Path(d) for d in paths["earlier"]], args.round
    )
    if args.seed in {e["seed"] for e in earlier_info}:
        raise SystemExit("the seed was used by an earlier round")
    cand: dict[str, Any] = {"commit": None, "tree_sha256": None, "n_files": None}
    if args.candidate_commit:
        d = FZ.commit_src_digest(args.candidate_commit)
        cand = {"commit": d["commit"], "tree_sha256": d["tree_sha256"], "n_files": d["n_files"]}
    round2 = _round2_part(args, cand) if args.round == 2 else None
    ref_problems = (
        []
        if FZ._RECEIPT_REF.fullmatch(args.remote_ref or "")
        else FZ.receipt_ref_problems(args.remote_ref, REPO)[1]
    )
    rec: dict[str, Any] = {
        "kind": FZ.FREEZE_KIND,
        "version": FZ.FREEZE_VERSION,
        "dry_run": bool(args.dry_run),
        "round": args.round,
        "seed": args.seed,
        "execution_argv": execution_argv,
        "execution_command": "uv run --offline --frozen python -I "
        + shlex.join(execution_argv[2:]),
        "cwd": os.getcwd(),
        "paths": paths,
        "targets": TARGETS,
        "offline": bool(args.offline),
        "pool_inventory": FZ.pool_inventory(Path(paths["dev_raw"])),
        "cache_policy": POOL_POLICY,
        "fetch_failure_policy": FZ.FETCH_FAILURE_POLICY,
        "initial_cache_inventory": FZ.cache_inventory(raw),
        "dev_manifest": dev_info,
        "earlier_rounds": earlier_info,
        "exclusions": {
            "n_refs": len(exclude),
            "refs_sha256": digest,
            "identifier_rule": "build.text_refs (source id, url, fulltext_url, doi, title, Europe "
            "PMC article URL, Wikipedia revision URL), normalised by build._norm_ref",
        },
        "candidate": cand,
        "environment": FZ.environment_identity(REPO),
        "ledger": FZ.ledger_identity(
            args.ledger_md.resolve(),
            args.ledger_components.resolve() if args.ledger_components else None,
        ),
        "protocol": FZ.file_identity(FZ.PROTOCOL),
        "clarifications": FZ.file_identity(FZ.CLARIFICATIONS),
        "bound": {
            "preregistration": FZ.file_identity(args.preregistration.resolve()),
            "delivery_spec": FZ.file_identity(
                args.delivery_spec.resolve() if args.delivery_spec else None
            ),
            "registry": FZ.file_identity(args.registry.resolve() if args.registry else None),
            "dispositions": [FZ.file_identity(x.resolve()) for x in args.dispositions],
        },
        "delivery": _delivery_part(args),
        "registry": _registry_part(args, cand),
        "receipt_ref": {
            "ref": args.remote_ref,
            "remote": FZ.RECEIPT_REMOTE,
            "remote_url": FZ.remote_url(REPO),
            "problems": ref_problems,
        },
        "sources_sha256": source_hashes(),
        "round2": round2,
    }
    why = FZ.production_prerequisites(rec)
    rec["production_eligible"] = not args.dry_run and not why
    rec["ineligible_reasons"] = (["dry run"] if args.dry_run else []) + why
    return rec


def _reserve(args: argparse.Namespace) -> None:
    """Append this round's reservation to the registry, atomically (audit r2 B2)."""
    from fixcheck import registry as REG

    cand = {"commit": None, "tree_sha256": None}
    if args.candidate_commit:
        d = FZ.commit_src_digest(args.candidate_commit)
        cand = {"commit": d["commit"], "tree_sha256": d["tree_sha256"]}
    want = reservation_of(args, cand)

    def make(entries):
        verdict, probs = REG.check_reservation(entries, want)
        return verdict, probs, want

    path = args.registry.resolve()
    if args.dry_run:
        if path == REG.canonical_path(REPO):
            raise SystemExit("a dry run never reserves a round in the canonical registry")
        verdict, probs, _ = make(REG.load(path))
        if verdict == "append":
            REG.append_unchecked(path, dict(want, registered_at=FZ.now_iso()))
        elif verdict == "present" and not probs:
            REG.acknowledge_unchecked(path)
    else:
        verdict, probs, _ = REG.atomic_append(path, make, REPO)
    if verdict == "refuse":
        raise SystemExit("the round registry refuses this reservation:\n" + "\n".join(probs))


def _plan(args: argparse.Namespace, out: Path, raw: Path) -> tuple[dict[str, Any], Path]:
    record_path = out / "freeze_record.json"
    for f in (record_path, out / "command.txt"):
        if f.exists() and not (args.dry_run and args.overwrite):
            raise SystemExit(f"{f} exists; a freeze record and its command are never overwritten")
    if not args.dry_run:
        refuse_used_raw_cache(raw, args.dev_raw)  # G5: before the pool snapshot is copied in
    out.mkdir(parents=True, exist_ok=True)
    snapshot_pools(args.dev_raw.resolve(), raw)
    exec_argv = execution_argv_of_plan(_command_list(), record_path)
    rec = build_record(args, exec_argv)
    if not args.dry_run:
        pending = [
            r
            for r in rec["ineligible_reasons"]
            if r != "the round is not reserved in the canonical registry"
        ]
        if pending:
            raise SystemExit(f"not a production freeze: {pending} (or pass --dry-run)")
    if args.registry is not None:
        _reserve(args)
        rec = build_record(args, exec_argv)
    if not args.dry_run and not rec["production_eligible"]:
        raise SystemExit(
            f"not a production freeze: {rec['ineligible_reasons']} (or pass --dry-run)"
        )
    rec["planned_at"] = FZ.now_iso()
    rec["planned_by"] = {"git": git_state(), "planning_argv": _command_list()}
    write_json(record_path, rec)
    (out / "command.txt").write_text(
        f"cd {shlex.quote(rec['cwd'])} && {rec['execution_command']}\n", encoding="utf-8"
    )
    write_step_manifest(out, "plan", [record_path, out / "command.txt"])
    return rec, record_path


def _execute_checks(args: argparse.Namespace, record_path: Path) -> tuple[dict[str, Any], dict]:
    """Every B1 check, before any fetch. Returns (record, gate)."""
    planned = read_json(record_path)
    if planned.get("kind") != FZ.FREEZE_KIND or planned.get("version") != FZ.FREEZE_VERSION:
        raise SystemExit(f"{record_path} is not a fix-check freeze record")
    if planned["production_eligible"] and args.dry_run:
        raise SystemExit("a production freeze record cannot be executed with --dry-run")
    if not planned["production_eligible"] and not args.dry_run:
        raise SystemExit(
            f"{record_path} is not production-eligible ({planned['ineligible_reasons']}); "
            "only --dry-run may execute it"
        )
    problems = []
    if _command_list() != planned["execution_argv"]:
        problems.append("argv is not the recorded execution argv")
    if os.getcwd() != planned["cwd"]:
        problems.append(f"working directory {os.getcwd()} is not the recorded {planned['cwd']}")
    now = build_record(args, _command_list())
    problems += FZ.compare_records(planned, now)
    if problems:
        raise SystemExit(f"execution does not match the freeze record: {problems}")
    gate: dict[str, Any] = {"production": planned["production_eligible"]}
    if planned["production_eligible"]:
        gate |= FZ.execution_gate(record_path, planned, REPO, args.remote_ref)
        if not gate["ok"]:
            raise SystemExit(f"production execution refused before any fetch: {gate['problems']}")
    return planned, gate


# --- single execution (audit r3 B1) ----------------------------------------------------
#
# A reserved round executes at most once. The execution argv and the freeze record pin the
# round directory (`--out` = the reservation's collect_dir), so the directory is the
# reservation's unique execution location. Under a stable exclusive lock on
# <out>/execution.lock (never deleted), the invocation rechecks that no execution evidence
# exists and reruns every gate; then, BEFORE the first possible fetch, it creates the
# immutable execution-start record <out>/execution_start.json with exclusive creation
# (O_CREAT | O_EXCL), bound to the reservation, the freeze record and the argv, and makes it
# and its directory entry durable (durable_sync, audit r4 B1). Once that file exists no collection invocation for the directory
# ever proceeds again: not after completion, failure, abort, kill or crash, and there is no
# overwrite or resume option. Every request is journalled (durably) to
# <out>/fetch_journal.jsonl before it is made. Completion (execution.json) and abort
# (execution_abort.json) are separate, exclusively created records; neither replaces the
# start claim. The abort record preserves the fetch evidence on any exception, but the
# single-execution guarantee rests on the start record, not on an exception handler.

EXEC_LOCK = "execution.lock"
EXEC_START = "execution_start.json"
EXEC_ABORT = "execution_abort.json"
EXEC_DONE = "execution.json"
FETCH_JOURNAL = "fetch_journal.jsonl"
EXECUTION_EVIDENCE = (EXEC_START, EXEC_ABORT, EXEC_DONE, "collection.json", FETCH_JOURNAL)
START_KIND = "fixcheck-execution-start"
ABORT_KIND = "fixcheck-execution-abort"


def write_exclusive(path: Path, data: bytes, mode: int = 0o444) -> str:
    """Create `path` exclusively (FileExistsError if it exists), read-only by default, and
    make it durable with its directory entry (durable_sync) before returning. Returns the
    SHA-256 of `data`."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        _write_all(fd, data)
        durable_sync(fd, path)
    finally:
        os.close(fd)
    return hashlib.sha256(data).hexdigest()


def append_fsync(path: Path, text: str) -> None:
    """Append `text` (looping over short writes) and make it durable (durable_sync) before
    returning: a request is journalled durably before it may be made."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)  # created by claim_execution
    try:
        _write_all(fd, text.encode("utf-8"))
        durable_sync(fd, path)
    finally:
        os.close(fd)


def executed_evidence(out: Path) -> list[str]:
    return [n for n in EXECUTION_EVIDENCE if (out / n).exists()]


def refuse_if_executed(out: Path) -> None:
    ev = executed_evidence(out)
    if ev:
        raise SystemExit(
            f"{out}: this round was already executed ({', '.join(ev)}); an execution is final "
            "(completed, failed, aborted or crashed): it is never resumed, retried or overwritten"
        )


@contextlib.contextmanager
def execution_lock(out: Path):
    """The per-reservation execution lock, held from the gate recheck through completion."""
    out.mkdir(parents=True, exist_ok=True)
    fd = os.open(out / EXEC_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                f"{out / EXEC_LOCK} is held: another invocation is executing this reservation; "
                "refused"
            ) from None
        yield
    finally:
        os.close(fd)  # releases the lock; the lock file itself is never removed


def claim_execution(
    out: Path, rec: dict[str, Any], record_path: Path, gate: dict[str, Any], started: str
) -> dict[str, Any]:
    """Create the immutable execution-start record (exclusive creation) and the empty fetch
    journal, each made durable with its directory entry by the platform's full barrier
    (durable_sync; audit r4 B1), before the first possible fetch. An unsupported platform
    refuses before anything is written; a failed barrier refuses before any request (the
    start record may then exist, so the round is consumed with no request made)."""
    try:
        method = durability_method()
    except DurabilityError as e:
        raise SystemExit(
            f"refused before the execution claim and before any request: {e}"
        ) from None
    start = {
        "kind": START_KIND,
        "round": rec["round"],
        "seed": rec["seed"],
        "collect_dir": str(out),
        "freeze_record": str(record_path),
        "freeze_record_sha256": sha256_file(record_path),
        "reservation_sha256": (rec.get("registry") or {}).get("reservation_sha256"),
        "argv": _command_list(),
        "mode": "execute" if "--execute" in _command_list() else "one-step dry run",
        "cwd": os.getcwd(),
        "production_eligible": rec["production_eligible"],
        "gate_ok": gate.get("ok") if gate.get("production") else None,
        # the gate as checked under the lock, archive receipt included (audit r4 S1: a failed
        # execution's registration re-validates this receipt)
        "gate": gate,
        "durability": method,
        "started_at": started,
        "claimed_at": FZ.now_iso(),
        "pid": os.getpid(),
        "rule": "one execution per reservation: this file is created once, before the first "
        "possible fetch; while it exists no collection invocation for this round proceeds",
    }
    data = (canonical_json(start) + "\n").encode("utf-8")
    try:
        sha = write_exclusive(out / EXEC_START, data)
        write_exclusive(out / FETCH_JOURNAL, b"", mode=0o644)  # append-only (append_fsync)
    except FileExistsError:
        raise SystemExit(f"{out / EXEC_START} exists: this round was already executed") from None
    except DurabilityError as e:
        raise SystemExit(
            f"the durable-write barrier failed during the execution claim; refused before any "
            f"request (the round is consumed; register it with register-failure): {e}"
        ) from None
    return dict(start, sha256=sha)


def _journal_endpoint(journal: Path) -> dict[str, Any]:
    """The abort record's journal binding (audit r8 M1). The journal's file-plus-directory
    durable barrier must succeed first, and only then is its SHA-256 taken, so an
    authenticating hash always follows the journal's final successful barrier. If the
    barrier cannot succeed (for example the failure being recorded is that barrier's own
    failure, after the outcome bytes were written), the abort record is still written
    (closure is preserved) but carries no journal hash: the exposure is then not
    established (failure.endpoint_problems), and only terminal outcomes remain."""
    if not journal.exists():
        return {"fetch_journal_sha256": None, "fetch_journal_barrier": "no journal"}
    try:
        fd = os.open(journal, os.O_WRONLY | os.O_APPEND)
        try:
            durable_sync(fd, journal)
        finally:
            os.close(fd)
    except OSError as e:  # DurabilityError included: never downgraded to a hash
        return {
            "fetch_journal_sha256": None,
            "fetch_journal_barrier": f"failed: {type(e).__name__}: {e}",
        }
    return {"fetch_journal_sha256": sha256_file(journal), "fetch_journal_barrier": "passed"}


def _write_abort(
    out: Path,
    record_path: Path,
    rec: dict[str, Any],
    start: dict[str, Any],
    recorder: FetchRecorder,
    err: BaseException,
) -> None:
    """Abort evidence (best effort; the start record is the guarantee)."""
    import traceback

    ab = {
        "kind": ABORT_KIND,
        "freeze_record": str(record_path),
        "freeze_record_sha256": sha256_file(record_path),
        "execution_start_sha256": start["sha256"],
        "argv": _command_list(),
        "started_at": start["started_at"],
        "aborted_at": FZ.now_iso(),
        "aborted": f"{type(err).__name__}: {err}",
        "traceback_tail": traceback.format_exception(err)[-3:],
        "production_eligible": rec["production_eligible"],
        "fetch_log": recorder.fetches,
        "wiki_page_log": recorder.pages,
        **_journal_endpoint(out / FETCH_JOURNAL),
        "final": "an aborted execution is final: the round is never executed again",
    }
    try:
        write_exclusive(out / EXEC_ABORT, (canonical_json(ab) + "\n").encode("utf-8"), 0o644)
    except OSError as e:  # never mask the original failure
        print(f"could not write {out / EXEC_ABORT}: {e}", file=sys.stderr)


JOURNAL_EVENTS = ("request", "outcome")
REQUEST_FIELDS = {"seq": int, "url": str, "cache": str, "refresh": bool, "cache_hit": bool}


def read_journal(journal: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """The journal's events, or integrity problems: a truncated (unterminated) last line,
    undecodable or non-JSON lines, an unknown event name, missing or mistyped fields, an
    outcome that is neither one response nor one failure (audit r4 S2)."""
    data = journal.read_bytes()
    lines = data.split(b"\n")
    problems = []
    if lines[-1]:
        problems.append(f"{journal.name}: truncated (the last line is incomplete)")
    events = []
    for n, raw in enumerate(lines[:-1], 1):
        try:
            e = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            problems.append(f"{journal.name} line {n}: malformed (not one JSON object)")
            continue
        if not isinstance(e, dict):
            problems.append(f"{journal.name} line {n}: malformed (not one JSON object)")
            continue
        ev = e.get("event")
        if ev not in JOURNAL_EVENTS:
            problems.append(f"{journal.name} line {n}: unknown event {ev!r}")
            continue
        bad = sorted(
            k
            for k, t in REQUEST_FIELDS.items()
            if not isinstance(e.get(k), t) or (t is int and isinstance(e.get(k), bool))
        )
        if bad:
            problems.append(f"{journal.name} line {n}: malformed {ev} (missing or bad {bad})")
            continue
        if ev == "outcome":
            ok = "sha256" in e and isinstance(e["sha256"], str)
            failed = all(isinstance(e.get(k), str) for k in ("error", "error_class"))
            failed = failed and "error_message" in e
            if ok == failed:
                problems.append(
                    f"{journal.name} line {n}: malformed outcome (not exactly one of a response "
                    "hash and a failure)"
                )
                continue
        elif any(k in e for k in ("sha256", "error", "error_class", "error_message")):
            problems.append(f"{journal.name} line {n}: malformed request (it carries an outcome)")
            continue
        events.append(e)
    return events, problems


def journal_pairs(
    journal: Path, allow_trailing_request: bool
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """Validate the chronological journal as a state machine (audit r4 S2).

    The only valid stream is request(0), outcome(0), request(1), outcome(1), ...: strictly
    increasing sequence numbers from 0, each outcome immediately after its own request,
    with the request identity (seq, url, cache, refresh, cache_hit) equal across the pair.
    `allow_trailing_request` (the failure validator of a killed execution) admits one final
    request with no outcome. Returns (completed pairs as outcome records, the trailing
    request or None, problems). Any malformed line or state violation is a problem; the
    stream is not interpreted past the first violation."""
    events, problems = read_journal(journal)
    if problems:
        return [], None, problems
    pairs: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for n, e in enumerate(events, 1):
        ev = e["event"]
        rec = {k: v for k, v in e.items() if k != "event"}
        if pending is None:
            if ev != "request":
                return pairs, None, [f"{journal.name} event {n}: an outcome without its request"]
            if rec["seq"] != len(pairs):
                return (
                    pairs,
                    None,
                    [
                        f"{journal.name} event {n}: request seq {rec['seq']} out of order "
                        f"(expected {len(pairs)})"
                    ],
                )
            pending = rec
            continue
        if ev != "outcome":
            return (
                pairs,
                None,
                [f"{journal.name} event {n}: a request before the outcome of {pending['seq']}"],
            )
        if any(rec.get(k) != pending.get(k) for k in REQUEST_FIELDS):
            return (
                pairs,
                None,
                [f"{journal.name} event {n}: the outcome's request identity is not its request's"],
            )
        pairs.append(rec)
        pending = None
    if pending is not None and not allow_trailing_request:
        return pairs, None, [f"{journal.name}: request {pending['seq']} has no outcome"]
    return pairs, pending, []


def _journal_sig(f: dict[str, Any]) -> list[Any]:
    return [*_fetch_sig(f), f.get("cache_hit")]


def journal_problems(journal: Path, fetch_log: list[dict[str, Any]]) -> list[str]:
    """A completed collection: the journal is a valid request/outcome stream with no
    trailing request, and its pairs reconstruct the archived fetch log exactly."""
    if not journal.exists():
        return [f"{journal.name} missing"]
    pairs, _, p = journal_pairs(journal, allow_trailing_request=False)
    if p:
        return p
    if [_journal_sig(e) for e in pairs] != [_journal_sig(f) for f in fetch_log]:
        return [f"{journal.name} does not reconstruct the fetch log"]
    return []


def _collect_round(
    args: argparse.Namespace,
    out: Path,
    raw: Path,
    rec: dict[str, Any],
    record_path: Path,
    gate: dict[str, Any],
    start: dict[str, Any],
) -> int:
    """Collect under an existing execution-start claim (claim_execution)."""
    if not (out / EXEC_START).exists() or sha256_file(out / EXEC_START) != start["sha256"]:
        raise SystemExit("no execution-start claim: refusing to collect")
    recorder = FetchRecorder(raw, journal=out / FETCH_JOURNAL)
    try:
        return _collect_body(out, raw, rec, record_path, gate, start, recorder)
    except BaseException as e:
        _write_abort(out, record_path, rec, start, recorder, e)
        raise


def _collect_body(
    out: Path,
    raw: Path,
    rec: dict[str, Any],
    record_path: Path,
    gate: dict[str, Any],
    start: dict[str, Any],
    recorder: FetchRecorder,
) -> int:
    exclude, _, _, digest = _exclusions(
        Path(rec["paths"]["dev_texts"]), [Path(d) for d in rec["paths"]["earlier"]], rec["round"]
    )
    if digest != rec["exclusions"]["refs_sha256"]:
        raise SystemExit("exclusion set changed")
    snapshot_pools(Path(rec["paths"]["dev_raw"]), raw)
    texts, log = collect_with_build(
        rec["seed"],
        raw,
        exclude,
        FIXCHECK_ACADEMIC_TARGETS,
        FIXCHECK_WIKI_TARGET,
        FIXCHECK_ESSAY_TARGET,
        rec["offline"],
        recorder,
    )
    short = shortfalls(
        texts, FIXCHECK_ACADEMIC_TARGETS, FIXCHECK_WIKI_TARGET, FIXCHECK_ESSAY_TARGET
    )
    texts = finish_texts(texts, rec["round"])
    raw_files = raw_files_of(texts, raw, recorder)  # before any output: refuses cleanly
    files = [record_path, out / EXEC_START, out / FETCH_JOURNAL]
    (out / "texts").mkdir(exist_ok=True)
    for t in texts:
        p = out / "texts" / f"{t['text_id']}.txt"
        p.write_text(t["text"], encoding="utf-8")
        files.append(p)
    write_jsonl(out / "texts.jsonl", [{k: v for k, v in t.items() if k != "text"} for t in texts])
    files.append(out / "texts.jsonl")
    col = {
        "round": rec["round"],
        "seed": rec["seed"],
        "status": "shortfall" if short else "complete",
        "shortfalls": short,
        "n_texts": len(texts),
        "by_register": dict(Counter(t["register"] for t in texts)),
        "by_discipline": dict(Counter(t["discipline"] for t in texts if t["discipline"])),
        "truncated": sum(bool(t["truncated"]) for t in texts),
        "texts_jsonl_sha256": sha256_file(out / "texts.jsonl"),
        "freeze_record_sha256": sha256_file(record_path),
        "production_eligible": rec["production_eligible"],
        "candidate": rec["candidate"],
        "raw_files": raw_files,
        "fetch_log": recorder.fetches,
        "wiki_page_log": recorder.pages,
        "selection_log": log,
        "offline": rec["offline"],
    }
    write_json(out / "collection.json", col)
    files.append(out / "collection.json")
    ex = {
        "freeze_record": str(record_path),
        "freeze_record_sha256": sha256_file(record_path),
        "execution_start_sha256": start["sha256"],
        "fetch_journal_sha256": sha256_file(out / FETCH_JOURNAL),
        "argv": _command_list(),
        "cwd": os.getcwd(),
        "started_at": start["started_at"],
        "finished_at": FZ.now_iso(),
        "production_eligible": rec["production_eligible"],
        "gate": gate,
        "collection_json_sha256": sha256_file(out / "collection.json"),
        "git": git_state(),
    }
    write_exclusive(
        out / EXEC_DONE,
        (json.dumps(ex, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8"),
        mode=0o644,
    )
    files.append(out / EXEC_DONE)
    write_step_manifest(out, "collect", files)
    print(f"round {rec['round']}: {len(texts)} texts, status {col['status']}", file=sys.stderr)
    if short:
        print(f"SHORTFALL: {short}", file=sys.stderr)
        return 2
    return 0


def _walk_no_follow(root: Path) -> list[Path]:
    """Every entry under `root` (files, directories and symbolic links), never following a
    link."""
    out: list[Path] = []
    if root.is_dir():
        for base, dirs, files in os.walk(root, followlinks=False):
            out += [Path(base) / n for n in sorted(dirs) + sorted(files)]
    return sorted(out)


def refuse_unsafe_raw_cache(raw: Path, earlier: list[Path]) -> None:
    """A production round's download cache is private and its own (gap G5; round-2 harness
    audit r1 finding 4), checked at planning and at execution before anything is written.
    Refused: a cache inside the repository (it holds downloaded bodies, never committed);
    a cache that, after resolution, is an earlier round's recorded raw cache, lies inside
    it, or contains it; a cache inside the earlier round's private directory (the parent of
    its raw cache); and a cache holding a symbolic link that resolves into the earlier
    round's raw cache or private directory. Round 1's cache and private directory stay as
    they were: failure registration and round-1 replay read them recursively."""
    raw = Path(raw).resolve()
    if raw.is_relative_to(REPO.resolve()):
        raise SystemExit(
            f"the round's download cache {raw} is inside the repository: give a private "
            "--raw-cache outside it"
        )
    for d in earlier:
        fr = d.resolve() / "freeze_record.json"
        old = (read_json(fr).get("paths") or {}).get("raw_cache") if fr.is_file() else None
        if not old:
            continue
        old_raw = Path(old).resolve()
        if old_raw == raw:
            raise SystemExit(
                f"the round's download cache {raw} is the raw cache of the earlier round "
                f"{d}: give a fresh --raw-cache"
            )
        if raw.is_relative_to(old_raw) or old_raw.is_relative_to(raw):
            raise SystemExit(
                f"the round's download cache {raw} overlaps the raw cache {old_raw} of the "
                f"earlier round {d}: round 2 needs a raw cache disjoint from round 1's cache"
            )
        private = old_raw.parent
        if raw.is_relative_to(private):
            raise SystemExit(
                f"the round's download cache {raw} is inside the earlier round's private "
                f"directory {private}: give a fresh --raw-cache outside it"
            )
        for p in _walk_no_follow(raw):
            if p.is_symlink():
                target = p.resolve()
                if target.is_relative_to(old_raw) or target.is_relative_to(private):
                    raise SystemExit(
                        f"{p} in the round's download cache links into the earlier round's "
                        f"preserved material ({target}): give a fresh --raw-cache"
                    )


def refuse_used_raw_cache(raw: Path, dev_raw: Path) -> None:
    """A production plan's download cache is fresh (gap G5; round-2 harness audit r1
    finding 4), checked before the pool snapshot is copied in: the cache does not exist, is
    empty, or holds nothing but byte-equal copies of the frozen development pool listings
    (pools/<name>.json). Any other file (a pre-existing response body, such as a copy of an
    earlier round's bodies) is refused. Not applied at execution: planning legitimately
    copied the pool listings in, and the frozen initial cache inventory is the execution
    check."""
    raw = Path(raw).resolve()
    if not raw.exists():
        return
    if not raw.is_dir():
        raise SystemExit(f"the round's download cache {raw} is not a directory")
    src = Path(dev_raw).resolve() / "pools"
    used = []
    for p in _walk_no_follow(raw):
        if p.is_dir() and not p.is_symlink():
            continue
        rel = p.relative_to(raw).as_posix()
        listing = src / p.name
        if (
            p.is_symlink()
            or p.parent != raw / "pools"
            or p.suffix != ".json"
            or not listing.is_file()
            or p.read_bytes() != listing.read_bytes()
        ):
            used.append(rel)
    if used:
        raise SystemExit(
            f"the round's download cache {raw} is not fresh: it holds {len(used)} file(s) other "
            f"than the frozen development pool listings (first: {used[:3]}); give a new, "
            "empty --raw-cache"
        )


def main(argv: list[str]) -> int:
    set_command("collect", argv)
    ap = argparse.ArgumentParser(prog="fixcheck collect", description=__doc__.split("\n\n")[0])
    ap.add_argument("--round", type=int, choices=(1, 2))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--raw-cache", type=Path, help="round download cache (default <out>/raw)")
    ap.add_argument("--dev-raw", type=Path, default=DEV_RAW, help="pool snapshot source")
    ap.add_argument("--dev-texts", type=Path, default=build.DEV_TEXTS)
    ap.add_argument(
        "--earlier", type=Path, action="append", default=[], help="earlier round dir (repeat)"
    )
    ap.add_argument("--offline", action="store_true", help="forbid every network request")
    ap.add_argument("--plan-only", action="store_true", help="write the freeze record and stop")
    ap.add_argument("--execute", action="store_true", help="collect under --freeze-record")
    ap.add_argument("--freeze-record", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="production_eligible: false")
    ap.add_argument("--candidate-commit", help="the frozen candidate commit (production)")
    ap.add_argument("--ledger-md", type=Path, default=LEDGER_MD)
    ap.add_argument(
        "--ledger-components",
        type=Path,
        default=LEDGER_COMPONENTS,
        help="ledger_components.json (tracked freeze location)",
    )
    ap.add_argument(
        "--registry",
        type=Path,
        help=f"the canonical round registry (production: {REG_DEFAULT}); dry runs may name "
        "another file or none",
    )
    ap.add_argument(
        "--delivery-spec", type=Path, default=DELIVERY_SPEC, help="registered delivery spec"
    )
    ap.add_argument("--preregistration", type=Path, default=FZ.PREREG)
    ap.add_argument(
        "--dispositions",
        type=Path,
        action="append",
        default=[],
        help="a disposition or rulings file bound into the freeze (repeat)",
    )
    ap.add_argument("--narrowing-disposition", type=Path, help="reviewed disposition (round 2)")
    ap.add_argument(
        "--narrowing-check",
        type=Path,
        help="round 2: the final dry run's NARROWING_CHECK.json (round2/NARROWING_CHECK.json)",
    )
    ap.add_argument(
        "--remote-ref",
        default=FZ.DEFAULT_REMOTE_REF,
        help="the receipt ref: a full refs/remotes/origin/<branch> ref",
    )
    ap.add_argument("--replay-development", action="store_true")
    ap.add_argument("--replay-round", type=Path, metavar="ROUND_DIR")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    if args.registry is None and not args.dry_run:
        args.registry = REG_DEFAULT  # production: the canonical registry, always
    out = args.out.resolve()
    if args.replay_development:
        return replay_development(out, args.dev_raw.resolve(), args.overwrite)
    if args.replay_round:
        return replay_round(args.replay_round.resolve(), out, args.raw_cache, args.overwrite)
    if args.round is None or args.seed is None:
        ap.error("--round and --seed are required")
    if args.plan_only and args.execute:
        ap.error("--plan-only and --execute are separate invocations")
    if args.seed == build.DEV_SEED:
        raise SystemExit("a fix-check round needs a seed other than the development seed")
    if out == build.DEV_OUT.resolve():
        raise SystemExit("a fix-check round needs its own --out")
    raw = (args.raw_cache or out / "raw").resolve()
    if raw == args.dev_raw.resolve():
        raise SystemExit("the round's download cache must not be the development cache")
    if not args.dry_run:
        refuse_unsafe_raw_cache(raw, args.earlier)
    started = FZ.now_iso()
    if args.plan_only:
        rec, path = _plan(args, out, raw)
        print(f"wrote {path} (production_eligible={rec['production_eligible']})")
        return 0
    if args.execute:
        if args.freeze_record is None:
            ap.error("--execute needs --freeze-record")
        record_path = args.freeze_record.resolve()
        refuse_if_executed(out)  # early refusal; rechecked under the lock (audit r3 B1)
        with execution_lock(out):
            refuse_if_executed(out)
            rec, gate = _execute_checks(args, record_path)
            start = claim_execution(out, rec, record_path, gate, started)
            return _collect_round(args, out, raw, rec, record_path, gate, start)
    if not args.dry_run:
        raise SystemExit(
            "a production collection is two invocations: --plan-only, then --execute "
            "--freeze-record (or pass --dry-run for an ineligible one-step collection)"
        )
    # one-step dry run: the same single-execution claim (an executed directory is final;
    # --overwrite never re-executes it: use a fresh --out)
    refuse_if_executed(out)
    with execution_lock(out):
        refuse_if_executed(out)
        rec, record_path = _plan(args, out, raw)
        gate = {"production": False}
        start = claim_execution(out, rec, record_path, gate, started)
        return _collect_round(args, out, raw, rec, record_path, gate, start)


__all__ = ["main", "REPO"]
