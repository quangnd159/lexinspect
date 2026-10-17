"""`register-failure`: register a failed, killed or aborted round execution as
`procedure_failure` (HARNESS_AUDIT_R3_DISPOSITIONS.md, Addendum 1; audit r4 S1).

A round whose execution-start record exists is consumed (collect.claim_execution). If
the execution did not complete (no execution.json, or an execution_abort.json exists),
the round can never be accepted: it is registered as `procedure_failure`, a non-pass,
without labels and without any acceptance arithmetic (kind "interrupted"). A completed
collection that cannot reach labels is closed the same way (R4 Addendum 2): kind
"shortfall" (collection status shortfall; acceptance of a shortfall is refused) or
"pre_label_step" (any post-collection step before labels that cannot complete; --reason
names it). Its exposure also includes the full collected text set, and its collection
must authenticate (collect.authenticate_collection). After registration the round
directory holds procedure_failure.json (hashes only), which makes later rounds exclude
the round's exposure, not just its texts.

    register-failure --round-dir D --archive A --out O [--registry REG] [--dry-run]

The command, under the round's execution lock (so no execution of D is running):
- authenticates the freeze record D/freeze_record.json, the immutable start record (bound
  to that freeze record, its reservation and the recorded execution argv), the abort
  record if any, and, in production, the archive receipt the execution gate checked
  (re-validated against committed objects: freeze.verify_receipt);
- finds the round's reservation in the registry (round, candidate and seed equal);
- checks the private failure archive A (a tar): it must hold collect/freeze_record.json,
  collect/execution_start.json and, when they exist, collect/fetch_journal.jsonl and
  collect/execution_abort.json byte for byte, and raw/ must be exactly the round's raw
  cache as it is now; the archive's SHA-256 is bound;
- reconstructs the exposure inventory (`exposure_inventory`);
- appends one decision line with status `procedure_failure` to the registry, atomically
  and idempotently (the same complete input identity registers once, acknowledged only
  after the durable barrier; anything else for the round is refused), writes the round
  marker D/procedure_failure.json, and then writes O/failure.json (private: it names
  sources), O/registration.json and O/manifest_register_failure.json, in that order.
  Rerunning the same command with the same O after an interruption at any point
  recovers without --overwrite: an existing O/failure.json must be byte for byte this
  registration's and an existing O/registration.json must record this registry line
  (audit r5 M1); otherwise it refuses (a fresh O, or --overwrite).

Exposure inventory of an interrupted round (the maintainer's disposition of audit r4 S1).
Every source identity whose request appears in the journal (requested, whether or not it
succeeded), every body in the round's raw cache, and every listing entry the seeded
selection reached before the interruption (and the one it would have requested next) is
exposed. The listing entries are reconstructed by re-running build.py's selection
offline with the recorded seed, targets and exclusions through the journal
(JournalReplay: every call must be the journal's next request; a completed outcome is
served from its authenticated cache file or raised again as its archived failure; at
the end of the journal, or at its one unmatched final request, the replay stops). An
identity is every identifier build.py's exclusion test uses (build.text_refs: source id,
article and full-text URLs, DOI and title; for Wikipedia the requested title and, from
a cached body, the page id, canonical title and revision URL), normalised
(build._norm_ref). The exposure is complete ONLY with an authenticated endpoint (ruling after audit r7 B1;
endpoint_problems): a completion record (execution.json) or an abort record whose
recorded journal SHA-256 and fetch log match the journal byte for byte, the journal
ending exactly there. A hard interruption leaves no endpoint, so its exposure is never
established; neither is it with a missing, empty, shortened or hash-mismatched journal
(absence of evidence never implies zero requests). Equally, if the journal fails its
integrity check (collect.journal_pairs), the replay diverges, or any cached body or request cannot be mapped to identities, the
exposure is NOT established: the failure is still registered (the round is consumed),
with `exposure_complete: false`, and the registry then admits no round 2: only the
terminal outcomes `revert_0.3.3` and `amendment` remain. A failed round 2 is terminal in
any case.

An unreadable start record (R5 Addendum ruling 2, revised after audit r6 B1: a claim
write cut short by power loss or a crash) is registrable, so the round is never stranded.
It is recorded as "unreadable" with its raw bytes hashed; the reservation, freeze record,
receipt (in production a receipt of the freeze record's bound files, made at
registration, since the gate's receipt was in the start record) and archive must still
authenticate. Its exposure is ALWAYS incomplete: neither a missing journal nor an
unchanged cache proves that no request was made. Only the terminal outcomes remain;
round-2 reservation and planning refuse. Identifiers recoverable from the surviving
evidence are recorded as a diagnostic lower bound only.

The archive must agree with the round directory both ways: every optional execution
record (journal, abort record, completion record, collection record, texts) is in the
archive exactly when it is in the round directory, with the same bytes.

Round-2 planning after a failed round 1 (collect._round2_part, collect.earlier_exclusions)
recomputes this inventory from the same evidence, requires it to be complete and equal
to the registered one, and excludes every exposed identity.

`--dry-run` is for dry-run freeze records only: a non-canonical registry, no receipt
(the record is not production-eligible); every other check is the same.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import urllib.parse
from pathlib import Path
from typing import Any

import build

from fixcheck import collect as CL
from fixcheck import freeze as FZ
from fixcheck.common import (
    canonical_json,
    read_json,
    set_command,
    sha256_file,
    sha256_text,
    source_hashes,
    write_json,
    write_step_manifest,
)
from fixcheck.ledger import FAMILIES

STATUS = "procedure_failure"
FAILURE_KIND = "fixcheck-procedure-failure"
FAILURE_FIELDS = (
    "execution_start_sha256",
    "fetch_journal_sha256",
    "execution_abort_sha256",
    "cache_inventory_sha256",
    "archive_sha256",
    "exposure_sha256",
    "exposure_complete",
    "n_exposed",
)


class Interrupted(BaseException):  # noqa: N818 - a control-flow signal, not an error
    """The replay reached the point where the original execution stopped. BaseException,
    so build.py's `except Exception` (a rejected article) can never swallow it."""


class JournalReplay(CL.LedgerReplay):
    """LedgerReplay over a failed execution's journal: the completed request/outcome
    pairs in order, then the stop. A call past the last pair raises Interrupted; if the
    journal ends with one unmatched request, that call must be exactly it."""

    def __init__(self, pairs: list[dict[str, Any]], trailing: dict[str, Any] | None, raw: Path):
        super().__init__(pairs, raw)
        self.trailing = trailing
        self.stopped_at: dict[str, Any] | None = None

    def __call__(self, url: str, cache: Path, refresh: bool = False) -> bytes:
        if self.pos < len(self.ledger):
            return super().__call__(url, cache, refresh)
        try:
            rel = Path(cache).resolve().relative_to(self.raw.resolve()).as_posix()
        except ValueError:
            rel = str(cache)
        self.stopped_at = {"url": url, "cache": rel, "refresh": bool(refresh)}
        t = self.trailing
        if t is not None and (t["url"], t["cache"], bool(t["refresh"])) != (url, rel, refresh):
            self.problems.append(
                "the journal's unmatched final request is not the seeded selection's next request"
            )
        raise Interrupted


FAILURE_RECORD = "procedure_failure.json"
KINDS = ("interrupted", "shortfall", "pre_label_step")
COMPLETED_KINDS = ("shortfall", "pre_label_step")


def start_unreadable(d: Path) -> bool:
    """D's execution-start record exists but cannot be read as a JSON object (a write cut
    short by power loss or a crash during the claim; R5 Addendum ruling 2)."""
    st = d / CL.EXEC_START
    return st.exists() and not isinstance(_read_record(st), dict)


def failed_execution(d: Path) -> bool:
    """D holds a claimed execution that did not complete (or completed and aborted)."""
    return (d / CL.EXEC_START).exists() and (
        not (d / CL.EXEC_DONE).exists() or (d / CL.EXEC_ABORT).exists()
    )


def completed_execution(d: Path) -> bool:
    """D holds a claimed execution that completed (no abort record)."""
    return (d / CL.EXEC_START).exists() and not failed_execution(d)


def registered_failure(d: Path) -> bool:
    """register-failure closed D (its round-directory record exists; R4 Addendum 2)."""
    return (d / FAILURE_RECORD).exists()


def failure_closed(d: Path) -> bool:
    """D is excluded as a failed round (exposure inventory), not as a decided collection."""
    return failed_execution(d) or registered_failure(d)


def _pool_maps(raw: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
    """Europe PMC rows by pmcid and Wikipedia titles by cache key, from the round's pool
    snapshot. An unreadable or malformed pool file is a problem (exposure not established),
    never a crash (audit r5 S2)."""
    rows: dict[str, dict[str, Any]] = {}
    titles: dict[str, str] = {}
    problems = []
    for f in sorted((raw / "pools").glob("*.json")):
        try:
            d = json.loads(f.read_bytes())
        except (OSError, ValueError) as e:
            problems.append(f"pools/{f.name}: the pool listing cannot be read ({type(e).__name__})")
            continue
        if not isinstance(d, dict):
            problems.append(f"pools/{f.name}: the pool listing is not a JSON object")
            continue
        prows, ptitles = d.get("rows") or [], d.get("titles") or []
        if not isinstance(prows, list) or not isinstance(ptitles, list):
            problems.append(f"pools/{f.name}: rows/titles are not lists")
            continue
        for r in prows:
            if not isinstance(r, dict) or not isinstance(r.get("pmcid"), str):
                problems.append(f"pools/{f.name}: a row without a string pmcid")
                continue
            rows[r["pmcid"]] = r
        for t in ptitles:
            if not isinstance(t, str):
                problems.append(f"pools/{f.name}: a listed title that is not a string")
                continue
            k = build._key(t)
            if k in titles and titles[k] != t:
                problems.append(f"two listed titles share the cache key {k}")
            titles[k] = t
    return rows, titles, problems


def _epmc_refs(pmcid: str, rows: dict[str, dict[str, Any]]) -> tuple[set[str], list[str]]:
    row = rows.get(pmcid)
    t = {
        "source": "Europe PMC",
        "source_id": pmcid,
        "url": f"https://europepmc.org/article/PMC/{pmcid}",
        "fulltext_url": f"{build.EPMC}/{pmcid}/fullTextXML",
        "doi": (row or {}).get("doi"),
        "title": (row or {}).get("title"),
    }
    return build.text_refs(t), ([] if row else [f"{pmcid} is not in the pool listings"])


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _wiki_body_refs(f: Path) -> tuple[set[str], list[str]]:
    """Identities in a cached Wikipedia response: page id, canonical title, revision URL.

    The whole schema is validated (audit r5 S2): a JSON object whose "query" is an object
    whose "pages" is a list of page objects; a page that is not "missing" has an integer
    "pageid" and a nonempty string "title", and "revisions", if present, is a list of
    objects with an integer "revid". An unreadable, truncated or schema-invalid body
    yields no body identities and a problem (the exposure is then not established; the
    caller keeps the requested title it knows from the journal or the listing). It never
    raises for a damaged body."""
    bad = f"{f.name}: the cached Wikipedia body"
    try:
        d = json.loads(f.read_bytes())
    except OSError as e:
        return set(), [f"{bad} cannot be read ({type(e).__name__})"]
    except ValueError:
        return set(), [f"{bad} is not valid JSON (unreadable or truncated)"]
    q = d.get("query") if isinstance(d, dict) else None
    pages = q.get("pages") if isinstance(q, dict) else None
    if not isinstance(pages, list):
        return set(), [f"{bad} has no query.pages list"]
    refs: set[str] = set()
    for i, pg in enumerate(pages):
        if not isinstance(pg, dict):
            return set(), [f"{bad}: page {i} is not an object"]
        if pg.get("missing"):
            continue
        if not _is_int(pg.get("pageid")) or not isinstance(pg.get("title"), str) or not pg["title"]:
            return set(), [f"{bad}: page {i} lacks an integer pageid or a title"]
        refs |= {f"pageid:{pg['pageid']}", pg["title"]}
        revs = pg.get("revisions", [])
        if not isinstance(revs, list):
            return set(), [f"{bad}: page {i}'s revisions is not a list"]
        for j, rev in enumerate(revs):
            if not isinstance(rev, dict) or not _is_int(rev.get("revid")):
                return set(), [f"{bad}: page {i} revision {j} is not an object with a revid"]
            refs.add(f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}")
    return {build._norm_ref(str(r)) for r in refs}, []


def _request_refs(
    e: dict[str, Any], raw: Path, rows: dict[str, dict[str, Any]]
) -> tuple[set[str], list[str]]:
    """The identities of one journalled request (whether or not it succeeded)."""
    cache = e["cache"]
    if cache.startswith("epmc/") and cache.endswith(".xml"):
        pmcid = cache[len("epmc/") : -len(".xml")]
        if e["url"] != f"{build.EPMC}/{pmcid}/fullTextXML":
            return set(), [f"request {e['seq']}: URL and cache key name different articles"]
        return _epmc_refs(pmcid, rows)
    if cache.startswith("wiki/") and cache.endswith(".json"):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(e["url"]).query)
        titles = q.get("titles") or []
        if len(titles) != 1 or f"wiki/{build._key(titles[0])}.json" != cache:
            return set(), [f"request {e['seq']}: no single requested title matching its cache key"]
        refs = {build._norm_ref(titles[0])}
        f = raw / cache
        if f.exists():
            more, p = _wiki_body_refs(f)
            return refs | more, p
        return refs, []
    if (
        cache.startswith("tmp/")
        and e.get("refresh")
        and e.get("error_class") == ("PoolRequeryForbidden")
    ):
        return set(), []  # a refused pool query: no request left the process, no source
    return set(), [f"request {e['seq']}: {cache} is not a known source request"]


def exposure_inventory(d: Path) -> dict[str, Any]:
    """The authenticated exposure inventory of a failed execution in round directory D."""
    problems: list[str] = []
    fr = read_json(d / "freeze_record.json")
    raw = Path(fr["paths"]["raw_cache"])
    journal = d / CL.FETCH_JOURNAL
    out: dict[str, Any] = {"round_dir": str(d), "raw_cache": str(raw)}
    if start_unreadable(d):
        return _unreadable_start_exposure(d, fr, raw, journal, out)
    completed = completed_execution(d)
    collected: set[str] = set()
    if completed:
        # R4 Addendum 2: a completed but unlabellable collection. The collection must
        # authenticate (texts, manifest, start record, journal reconstructing the fetch log,
        # no trailing request); its full collected text set is exposure.
        problems += [f"collection: {x}" for x in CL.authenticate_collection(d)]
        if (d / "texts.jsonl").exists():
            try:
                collected = build.read_exclusions(d / "texts.jsonl")
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                problems.append(f"texts.jsonl cannot be read ({type(e).__name__})")
    # 1. the journal (diagnostics may use a valid prefix and one final unmatched request)
    if journal.exists():
        pairs, trailing, jp = CL.journal_pairs(journal, allow_trailing_request=not completed)
        problems += [f"journal: {x}" for x in jp]
    else:  # absence of evidence never implies zero requests (audit r7 B1)
        pairs, trailing = [], None
    out["journal"] = {
        "present": journal.exists(),
        "sha256": sha256_file(journal) if journal.exists() else None,
        "completed_requests": len(pairs),
        "unmatched_final_request": trailing is not None,
    }
    # the authenticated endpoint (audit r7 B1 ruling): the ONLY basis for completeness
    endpoint, ep = endpoint_problems(d, journal, pairs, trailing, completed)
    out["endpoint"] = endpoint
    problems += [f"endpoint: {x}" for x in ep]
    # 2. the pool snapshot and exclusions the execution used
    rows, key_titles, pp = _pool_maps(raw)
    problems += pp
    pools_now = sorted((f"pools/{f.name}", sha256_file(f)) for f in (raw / "pools").glob("*.json"))
    if pools_now != sorted((x["file"], x["sha256"]) for x in fr["pool_inventory"]):
        problems.append("the round's pool snapshot differs from the freeze record's")
    try:
        exclude, _, _, digest = CL._exclusions(
            Path(fr["paths"]["dev_texts"]), [Path(x) for x in fr["paths"]["earlier"]], fr["round"]
        )
    except SystemExit as e:
        exclude, digest = set(), None
        problems.append(f"the exclusion set cannot be recomputed: {e}")
    if digest != fr["exclusions"]["refs_sha256"]:
        problems.append("the recomputed exclusion set differs from the freeze record's")
    # 3. the seeded selection, replayed offline through the journal
    selected: set[str] = set()
    ended = None
    replay = JournalReplay(pairs, trailing, raw)
    if not problems:
        before = FZ.cache_inventory(raw)["sha256"]
        rec = CL.FetchRecorder(raw)
        log: dict[str, Any] = {}
        tg = fr["targets"]
        texts: list[dict[str, Any]] = []
        try:
            with CL.build_settings(
                fr["seed"],
                raw,
                exclude,
                dict(tg["academic"]),
                tg["general"],
                tg["argumentative"],
                True,
                rec,
                replay,
            ):
                texts += build.collect_academic(False, log)
                texts += build.collect_wiki("general", False, log)
                texts += build.collect_wiki("essays", False, log)
            ended = "selection completed"
        except Interrupted:
            ended = "interrupted"
        except CL.ReplayedFetchFailure as e:
            ended = f"archived failure {e.original_class}"
        except Exception as e:  # noqa: BLE001 - any divergence means no established exposure
            problems.append(f"the selection replay failed: {type(e).__name__}: {e}")
        problems += [f"replay: {x}" for x in replay.problems]
        if replay.pos != len(pairs):
            problems.append(f"the replay consumed {replay.pos} of {len(pairs)} journalled requests")
        if trailing is not None and ended != "interrupted":
            problems.append("the journal's unmatched final request was never reached by the replay")
        if ended and ended.startswith("archived failure") and replay.pos != len(pairs):
            problems.append("the replayed failure is not the journal's last outcome")
        if FZ.cache_inventory(raw)["sha256"] != before:
            problems.append("the raw cache changed during the replay")
        if completed:
            replayed = set().union(*(build.text_refs(t) for t in texts)) if texts else set()
            if ended != "selection completed" or replayed != collected:
                problems.append("the replayed selection does not reproduce the collected texts")
        for t in texts:
            selected |= build.text_refs(t)
        # rows reached and requested but rejected (entries skipped by the exclusion set
        # were never selected or viewed: they are already excluded and are not exposure)
        for x in [r["pmcid"] for r in log.get("academic_rejected", [])]:
            selected.add(build._norm_ref(str(x)))
        for k in ("wiki_general_rejected", "wiki_essays_rejected"):
            selected |= {build._norm_ref(r["title"]) for r in log.get(k, [])}
        for pg in rec.pages:
            selected.add(build._norm_ref(pg["requested_title"]))
            if pg.get("pageid") is not None:
                selected |= {
                    build._norm_ref(f"pageid:{pg['pageid']}"),
                    build._norm_ref(pg["title"]),
                    build._norm_ref(f"https://en.wikipedia.org/w/index.php?oldid={pg['revid']}"),
                }
        if replay.stopped_at is not None:  # the entry the selection would have requested next
            r, p = _request_refs({"seq": "next", **replay.stopped_at}, raw, rows)
            selected |= r
            problems += p
    # 4. every journalled request
    requested: set[str] = set()
    for e in [*pairs, *([trailing] if trailing else [])]:
        r, p = _request_refs(e, raw, rows)
        requested |= r
        problems += p
    # 5. every body in the round cache
    cached: set[str] = set()
    for f in sorted(p for p in raw.rglob("*") if p.is_file()):
        rel = f.relative_to(raw).as_posix()
        if rel.startswith("pools/"):
            continue
        if rel.startswith("epmc/") and rel.endswith(".xml"):
            r, p = _epmc_refs(rel[len("epmc/") : -len(".xml")], rows)
        elif rel.startswith("wiki/") and rel.endswith(".json"):
            r, p = _wiki_body_refs(f)
            title = key_titles.get(rel[len("wiki/") : -len(".json")])
            if title is not None:
                r = r | {build._norm_ref(title)}
            elif not r:
                p = [*p, f"{rel}: a cached body with no identity"]
        else:
            r, p = set(), [f"{rel}: an unknown file in the round cache"]
        cached |= r
        problems += p
    refs = sorted(requested | cached | selected | collected)
    out |= {
        "completed_collection": completed,
        "n_collected_refs": len(collected),
        "rule": "requested in the journal + cached bodies + listing entries the seeded "
        "selection reached before the interruption (and the next one) + (a completed "
        "collection) the full collected text set; identities as build.text_refs, normalised "
        "by build._norm_ref",
        "ended": ended,
        "stopped_at": replay.stopped_at,
        "n_requested_refs": len(requested),
        "n_cached_refs": len(cached),
        "n_selected_refs": len(selected),
        "refs": refs,
        "refs_sha256": sorted(sha256_text(r) for r in refs),
        "exposure_sha256": hashlib.sha256("\n".join(refs).encode()).hexdigest(),
        "complete": not problems,
        "problems": problems,
    }
    return out


def endpoint_problems(
    d: Path,
    journal: Path,
    pairs: list[dict[str, Any]],
    trailing: dict[str, Any] | None,
    completed: bool,
) -> tuple[str | None, list[str]]:
    """Exposure completeness needs an authenticated endpoint (ruling after audit r7 B1).

    The full request history is fixed only by an endpoint record whose recorded journal
    SHA-256 was taken after a successful durable barrier on the journal (the completion
    writer: after every append's barrier passed; the abort writer: after re-applying the
    journal's barrier itself, recording no hash if it fails; audit r8 M1), and whose
    recorded hash and fetch log match the journal byte for byte: the completion record (execution.json, with collection.json's
    fetch log) of a completed collection, or the abort record (execution_abort.json, with
    its own fetch log) of a failed one, the journal ending exactly there (no unmatched
    request). Anything else (no endpoint record after a hard interruption; a missing,
    empty, shortened or hash-mismatched journal) is a problem: the exposure is then not
    established. Returns (the endpoint used, problems)."""
    if not journal.exists():
        return None, ["the fetch journal is missing: no authenticated endpoint"]
    jsha = sha256_file(journal)
    if completed:
        ex = _read_record(d / CL.EXEC_DONE)
        col = _read_record(d / "collection.json") if (d / "collection.json").exists() else None
        if not isinstance(ex, dict) or not isinstance(col, dict):
            return None, ["the completion or collection record cannot be read"]
        p = []
        if ex.get("fetch_journal_sha256") != jsha:
            p.append("the completion record's journal SHA-256 is not the journal's")
        if ex.get("collection_json_sha256") != sha256_file(d / "collection.json"):
            p.append("the completion record does not name collection.json")
        log = col.get("fetch_log")
        name = CL.EXEC_DONE
    else:
        if not (d / CL.EXEC_ABORT).exists():
            return None, [
                "no abort record: a hard interruption leaves no authenticated endpoint, so the "
                "journal may be shortened (absence of evidence never implies zero requests)"
            ]
        ab = _read_record(d / CL.EXEC_ABORT)
        if not isinstance(ab, dict):
            return None, ["the abort record cannot be read"]
        p = []
        if not ab.get("fetch_journal_sha256"):
            # audit r8 M1: the abort writer hashes the journal only after its barrier
            # succeeded; no hash means that barrier failed (or there was no journal)
            p.append(
                "the abort record holds no authenticating journal hash (the journal's "
                f"durable barrier did not succeed: {ab.get('fetch_journal_barrier')})"
            )
        elif ab.get("fetch_journal_sha256") != jsha:
            p.append("the abort record's journal SHA-256 is not the journal's")
        log = ab.get("fetch_log")
        name = CL.EXEC_ABORT
    if trailing is not None:
        p.append("the journal does not end at the endpoint (an unmatched final request)")
    if not isinstance(log, list) or not all(isinstance(x, dict) for x in log):
        p.append(f"{name} holds no fetch log")
    elif [CL._journal_sig(e) for e in pairs] != [CL._journal_sig(x) for x in log]:
        p.append(f"{name}'s fetch log is not the journal's requests")
    return (name if not p else None), p


def _unreadable_start_exposure(
    d: Path, fr: dict[str, Any], raw: Path, journal: Path, out: dict[str, Any]
) -> dict[str, Any]:
    """An unreadable start record (R5 Addendum ruling 2 as revised after audit r6 B1): the
    exposure is NEVER established. Neither a missing journal nor an unchanged cache shows
    that no request was made (evidence can be lost; a failed or cache-read request leaves
    the cache unchanged). Only the terminal outcomes remain. Identifiers recoverable from
    the surviving evidence (the journal if readable, the abort record's fetch log, the
    cached bodies, the collected texts) are recorded as a diagnostic lower bound only."""
    rows, key_titles, pp = _pool_maps(raw)
    diag: list[str] = [f"pools: {x}" for x in pp]
    refs: set[str] = set()
    sources: dict[str, int] = {}

    def add(name: str, r: set[str], p: list[str]) -> None:
        refs.update(r)
        sources[name] = sources.get(name, 0) + len(r)
        diag.extend(f"{name}: {x}" for x in p)

    if journal.exists():
        pairs, trailing, jp = CL.journal_pairs(journal, allow_trailing_request=True)
        diag += [f"journal: {x}" for x in jp]
        for e in [*pairs, *([trailing] if trailing else [])]:
            add("journal", *_request_refs(e, raw, rows))
    ab = _read_record(d / CL.EXEC_ABORT) if (d / CL.EXEC_ABORT).exists() else None
    log = ab.get("fetch_log") if isinstance(ab, dict) else None
    for e in log if isinstance(log, list) else []:
        if (
            isinstance(e, dict)
            and isinstance(e.get("cache"), str)
            and isinstance(e.get("url"), str)
        ):
            add("abort fetch log", *_request_refs({"seq": e.get("seq"), **e}, raw, rows))
    for f in sorted(x for x in raw.rglob("*") if x.is_file()):
        rel = f.relative_to(raw).as_posix()
        if rel.startswith("epmc/") and rel.endswith(".xml"):
            add("cache", *_epmc_refs(rel[len("epmc/") : -len(".xml")], rows))
        elif rel.startswith("wiki/") and rel.endswith(".json"):
            r, p = _wiki_body_refs(f)
            t = key_titles.get(rel[len("wiki/") : -len(".json")])
            add("cache", r | ({build._norm_ref(t)} if t else set()), p)
    if (d / "texts.jsonl").exists():
        try:
            add("collected texts", build.read_exclusions(d / "texts.jsonl"), [])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            diag.append(f"texts.jsonl cannot be read ({type(e).__name__})")
    init = (fr.get("initial_cache_inventory") or {}).get("sha256")
    out_refs = sorted(refs)
    out |= {
        "start_record": "unreadable",
        "completed_collection": (d / CL.EXEC_DONE).exists(),
        "rule": "unreadable start record: the exposure is never established (R5 Addendum "
        "ruling 2, revised after audit r6 B1); refs are a diagnostic lower bound recovered "
        "from the surviving evidence, never a complete inventory",
        "journal": {
            "present": journal.exists(),
            "sha256": sha256_file(journal) if journal.exists() else None,
        },
        "ended": None,
        "stopped_at": None,
        "refs_are": "diagnostic lower bound",
        "recovered_by_source": sources,
        "cache_equals_plan_inventory": FZ.cache_inventory(raw)["sha256"] == init,  # diagnostic
        "diagnostics": diag,
        "refs": out_refs,
        "refs_sha256": sorted(sha256_text(r) for r in out_refs),
        "exposure_sha256": hashlib.sha256("\n".join(out_refs).encode()).hexdigest(),
        "complete": False,
        "problems": [
            "the execution-start record is unreadable: the exposure is never established; "
            "only the terminal outcomes revert_0.3.3 and amendment remain (R5 Addendum "
            "ruling 2, revised after audit r6 B1)"
        ],
    }
    return out


def _tar_members(archive: Path) -> dict[str, str]:
    """{member name: SHA-256} of every regular file in the archive (read, never extracted)."""
    out = {}
    with tarfile.open(archive, "r:*") as tf:
        for m in tf.getmembers():
            if m.isfile():
                f = tf.extractfile(m)
                data = f.read() if f is not None else b""
                out[m.name.removeprefix("./")] = hashlib.sha256(data).hexdigest()
    return out


def archive_problems(archive: Path, d: Path, raw: Path) -> list[str]:
    if not archive.exists():
        return [f"{archive}: the failure archive is missing"]
    try:
        members = _tar_members(archive)
    except (tarfile.TarError, OSError) as e:
        return [f"{archive}: not a readable tar archive ({e})"]
    p = []
    optional = (CL.FETCH_JOURNAL, CL.EXEC_ABORT, CL.EXEC_DONE, "collection.json", "texts.jsonl")
    for name in ("freeze_record.json", CL.EXEC_START, *optional):
        f = d / name
        held = members.get(f"collect/{name}")
        if not f.exists():
            if name not in optional:
                p.append(f"{name} is missing from the round directory")
            elif held is not None:
                # audit r6 B1: presence must agree both ways (an archive-only journal is
                # never silently ignored)
                p.append(f"the archive holds collect/{name}, which the round directory lacks")
            continue
        if held is None:
            p.append(f"the archive lacks collect/{name}")
        elif held != sha256_file(f):
            p.append(f"the archive's collect/{name} is not the round's")
    inv = {x["file"]: x["sha256"] for x in FZ.cache_inventory(raw)["files"]}
    held = {k[len("raw/") :]: v for k, v in members.items() if k.startswith("raw/")}
    if held != inv:
        p.append("the archive's raw/ is not exactly the round's raw cache")
    return p


def failure_kind(d: Path, reason: str | None) -> tuple[str | None, str | None, list[str]]:
    """(kind, reason, problems). An interrupted execution is 'interrupted'. A completed one
    (R4 Addendum 2) is 'shortfall' if its collection is short, otherwise 'pre_label_step',
    which needs an explicit --reason naming the post-collection step that cannot complete."""
    if failed_execution(d):
        return "interrupted", reason, []
    col = read_json(d / "collection.json") if (d / "collection.json").exists() else {}
    if col.get("status") == "shortfall":
        return "shortfall", reason or f"shortfall: {col.get('shortfalls')}", []
    if not (reason or "").strip():
        return (
            None,
            None,
            [
                "the collection completed: it is closed as a procedure_failure only with --reason "
                "naming the pre-label procedure step that cannot complete (otherwise use accept)"
            ],
        )
    return "pre_label_step", reason.strip(), []


def evidence_problems(
    d: Path, fr: dict[str, Any], entries: list[dict[str, Any]], production: bool
) -> tuple[list[str], dict[str, Any]]:
    """The freeze record, the start/abort records, the reservation and (production) the
    receipt: refusal conditions (this is not this round's failed execution)."""
    from fixcheck import registry as REG

    p: list[str] = []
    rp = d / "freeze_record.json"
    if fr.get("kind") != FZ.FREEZE_KIND or fr.get("version") != FZ.FREEZE_VERSION:
        p.append("freeze_record.json is not a fix-check freeze record")
    if not (d / CL.EXEC_START).exists():
        return [*p, "no execution-start record: the round was never claimed"], {}
    if registered_failure(d):
        # idempotent reruns are allowed; the registry decides (same inputs or refused)
        pass
    st = _read_record(d / CL.EXEC_START)
    unreadable = not isinstance(st, dict)
    # R5 Addendum ruling 2: an unreadable (truncated) start record is recorded as such, its
    # raw bytes hashed, and does not stop the registration; the reservation, freeze record,
    # receipt and archive must still authenticate. A readable start record is checked fully.
    st = {} if unreadable else st
    fsha = sha256_file(rp)
    if unreadable:
        pass
    elif st.get("kind") != CL.START_KIND:
        p.append("execution_start.json is not an execution-start record")
    res_sha = (fr.get("registry") or {}).get("reservation_sha256")
    if not res_sha:
        p.append("the freeze record names no reservation")
    if not unreadable:
        if st.get("freeze_record_sha256") != fsha:
            p.append("execution_start.json does not name this freeze record")
        if st.get("reservation_sha256") != res_sha:
            p.append("execution_start.json does not name the freeze record's reservation")
        if production and st.get("mode") != "execute":
            p.append("a production round was not executed with --execute")
        if st.get("mode") == "execute" and st.get("argv") != fr.get("execution_argv"):
            p.append("execution_start.json's argv is not the recorded execution argv")
    ab = d / CL.EXEC_ABORT
    a = _read_record(ab) if ab.exists() else None
    # an unreadable abort record (best effort, possibly truncated by the crash it records)
    # is not a refusal: the start record is the guarantee, and exposure_inventory records
    # it as a problem (exposure not established; audit r5 S2). A readable abort record
    # that names another round is refused.
    if isinstance(a, dict):
        if a.get("kind") != CL.ABORT_KIND or a.get("freeze_record_sha256") != fsha:
            p.append("execution_abort.json is not this round's abort record")
        if not unreadable and a.get("execution_start_sha256") != sha256_file(d / CL.EXEC_START):
            # (an unreadable start record cannot match; its exposure is never established,
            # R5 Addendum ruling 2 as revised after audit r6 B1)
            p.append("execution_abort.json does not name execution_start.json")
    res = REG.find_entry(entries, res_sha)
    if res is None or res.get("type") != "reservation":
        p.append("the round's reservation is not in the registry")
    else:
        cand = fr.get("candidate") or {}
        want = {
            "round": fr.get("round"),
            "seed": fr.get("seed"),
            "candidate_commit": cand.get("commit"),
            "candidate_tree_sha256": cand.get("tree_sha256"),
        }
        if any(res.get(k) != v for k, v in want.items()):
            p.append("the reservation's round, candidate or seed is not the freeze record's")
    receipt: dict[str, Any] = {"checked": False}
    if production and not unreadable:
        gate = st.get("gate") or {}
        if gate.get("ok") is not True:
            p.append("the start record does not hold a passed execution gate")
        rprobs = FZ.verify_receipt(gate.get("receipt"), want=FZ.receipt_paths(rp, fr))
        p += [f"execution receipt: {x}" for x in rprobs]
        receipt = {
            "checked": True,
            "source": "the start record's execution gate",
            "problems": rprobs,
            "head": (gate.get("receipt") or {}).get("head"),
        }
    elif production:
        # the gate's receipt was in the unreadable start record: a receipt of the freeze
        # record's bound files is made now (local git only) and re-validated the same way
        ref = (fr.get("receipt_ref") or {}).get("ref") or FZ.DEFAULT_REMOTE_REF
        want = FZ.receipt_paths(rp, fr)
        fresh = FZ.archive_receipt(want, FZ.REPO, ref)
        rprobs = FZ.verify_receipt(fresh, want=want)
        p += [f"freeze receipt (start record unreadable): {x}" for x in rprobs]
        receipt = {
            "checked": True,
            "source": "a receipt of the freeze record's bound files, made at registration "
            "(the start record is unreadable)",
            "problems": rprobs,
            "head": fresh.get("head"),
        }
    return p, receipt


def failure_entry(fr: dict[str, Any], rec: dict[str, Any], failure_sha: str) -> dict[str, Any]:
    completed = rec["failure_kind"] in COMPLETED_KINDS
    cand = fr.get("candidate") or {}
    ex = rec["exposure"]
    entry = {
        "type": "decision",
        "round": fr["round"],
        "candidate_commit": cand.get("commit"),
        "candidate_tree_sha256": cand.get("tree_sha256"),
        "seed": fr["seed"],
        "reservation_sha256": (fr.get("registry") or {}).get("reservation_sha256"),
        "freeze_record_sha256": rec["freeze_record_sha256"],
        "collection_texts_sha256": rec["collection_texts_sha256"] if completed else None,
        "source_refs": ex["refs_sha256"],
        "session_ids_sha256": [],
        "transcripts_sha256": [],
        "inputs_sha256": rec["inputs_sha256"],
        "status": STATUS,
        "acceptance_sha256": failure_sha,
        "families": list(FAMILIES),
        "failure": {
            "execution_start_sha256": rec["execution_start_sha256"],
            "fetch_journal_sha256": rec["fetch_journal_sha256"],
            "execution_abort_sha256": rec["execution_abort_sha256"],
            "cache_inventory_sha256": rec["cache_inventory_sha256"],
            "archive_sha256": rec["archive"]["sha256"],
            "exposure_sha256": ex["exposure_sha256"],
            "exposure_complete": ex["complete"],
            "n_exposed": len(ex["refs"]),
            "kind": rec["failure_kind"],
            "reason": rec["failure_reason"],
            "start_record": rec["execution_start_record"],
        },
    }
    if fr["round"] == 2:
        entry["round1_entry_sha256"] = (fr.get("round2") or {}).get("round1_entry_sha256")
    return entry


def authenticate_failed_round(d: Path, r1: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Round-2 planning after a registered round-1 procedure_failure (audit r4 S1): the
    evidence in D is the registered one and its exposure is complete and unchanged."""
    p: list[str] = []
    f = r1.get("failure") or {}
    kind = f.get("kind", "interrupted")
    if kind == "interrupted" and not failed_execution(d):
        return {}, [f"{d} holds no failed execution"]
    if kind in COMPLETED_KINDS and not completed_execution(d):
        return {}, [f"{d} holds no completed collection"]
    rec = d / FAILURE_RECORD
    if not rec.exists() or read_json(rec).get("inputs_sha256") != r1.get("inputs_sha256"):
        p.append(f"{FAILURE_RECORD} is missing or is not the registered failure's")
    if kind in COMPLETED_KINDS and _maybe(d / "texts.jsonl") != r1.get("collection_texts_sha256"):
        p.append("texts.jsonl differs from the registered failure")
    now = {
        "execution_start_sha256": sha256_file(d / CL.EXEC_START),
        "fetch_journal_sha256": _maybe(d / CL.FETCH_JOURNAL),
        "execution_abort_sha256": _maybe(d / CL.EXEC_ABORT),
    }
    p += [f"{k} differs from the registered failure" for k, v in now.items() if f.get(k) != v]
    if not f.get("exposure_complete"):
        p.append(
            "round 1's exposure was not established at its registration: no round 2; only "
            "the terminal outcomes revert_0.3.3 and amendment remain"
        )
    ex = exposure_inventory(d)
    if not ex["complete"]:
        p.append(f"round 1's exposure cannot be reconstructed: {ex['problems'][:3]}")
    elif ex["exposure_sha256"] != f.get("exposure_sha256"):
        p.append("round 1's reconstructed exposure differs from the registered one")
    ident = {
        "freeze_record_sha256": sha256_file(d / "freeze_record.json"),
        "seed": read_json(d / "freeze_record.json")["seed"],
        "status": STATUS,
        **now,
        "exposure_sha256": ex["exposure_sha256"],
    }
    return ident, p


def _write_failure_record(d: Path, rec: dict[str, Any]) -> None:
    """The round-directory record of a registered failure (hashes only; public), written
    durably after the registry line. It marks D as failure-closed for later rounds'
    exclusions (collect.earlier_exclusions) even when its collection completed. An
    identical existing record is the idempotent rerun."""
    body = {
        "kind": FAILURE_KIND,
        "status": STATUS,
        "round": rec["round"],
        "seed": rec["seed"],
        "failure_kind": rec["failure_kind"],
        "inputs_sha256": rec["inputs_sha256"],
        "exposure_sha256": rec["exposure"]["exposure_sha256"],
        "exposure_complete": rec["exposure"]["complete"],
    }
    data = (canonical_json(body) + "\n").encode("utf-8")
    try:
        CL.write_exclusive(d / FAILURE_RECORD, data, mode=0o444)
    except FileExistsError:
        if (d / FAILURE_RECORD).read_bytes() != data:
            raise SystemExit(f"{d / FAILURE_RECORD} exists for another registration") from None


def _registered_line(entries: list[dict[str, Any]], entry: dict[str, Any]) -> dict[str, Any] | None:
    """The registry's line for this failure (as registered, with its registered_at)."""
    keys = ("round", "candidate_commit", "status", "inputs_sha256")
    return next(
        (
            e
            for e in entries
            if e.get("type") == "decision" and all(e.get(k) == entry.get(k) for k in keys)
        ),
        None,
    )


def _read_record(p: Path) -> Any:
    """A JSON record, or None if it cannot be read or parsed (a crash can truncate the
    best-effort abort record; audit r5 S2)."""
    try:
        return json.loads(p.read_bytes())
    except (OSError, ValueError):
        return None


def _maybe(p: Path) -> str | None:
    return sha256_file(p) if p.exists() else None


def main(argv: list[str]) -> int:
    set_command("register-failure", argv)
    from fixcheck import registry as REG

    ap = argparse.ArgumentParser(
        prog="fixcheck register-failure", description=__doc__.split("\n\n")[0]
    )
    ap.add_argument("--round-dir", type=Path, required=True, help="the round's collect directory")
    ap.add_argument("--archive", type=Path, required=True, help="the private failure archive (tar)")
    ap.add_argument("--registry", type=Path, default=REG.REGISTRY)
    ap.add_argument("--out", type=Path, required=True, help="private output directory")
    ap.add_argument(
        "--reason",
        help="a completed collection (R4 Addendum 2): the pre-label procedure step that cannot "
        "complete (a shortfall needs none)",
    )
    ap.add_argument("--dry-run", action="store_true", help="dry-run freeze records only")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    d = args.round_dir.resolve()
    out = args.out.resolve()
    rp = d / "freeze_record.json"
    if not rp.exists():
        raise SystemExit(f"{rp} missing")
    fr = read_json(rp)
    production = not args.dry_run
    if production and not fr.get("production_eligible"):
        raise SystemExit(f"{rp} is not a production freeze record: use --dry-run")
    if args.dry_run and fr.get("production_eligible"):
        raise SystemExit("a production round's failure is registered without --dry-run")
    reg_path = args.registry.resolve()
    if production:
        integ = REG.integrity(reg_path, REG.REPO)
        if not integ["ok"]:
            raise SystemExit("round registry refused:\n" + "\n".join(integ["problems"]))
    elif reg_path == REG.canonical_path(REG.REPO):
        raise SystemExit("a dry run never registers in the canonical registry")
    # under the execution lock: no execution of this round is running
    with CL.execution_lock(d):
        probs, receipt = evidence_problems(d, fr, REG.load(reg_path), production)
        raw = Path(fr["paths"]["raw_cache"])
        probs += archive_problems(args.archive.resolve(), d, raw)
        kind, reason, kp = failure_kind(d, args.reason) if not probs else (None, None, [])
        probs += kp
        if probs:
            raise SystemExit("register-failure refused:\n" + "\n".join(probs))
        exposure = exposure_inventory(d)
        rec: dict[str, Any] = {
            "kind": FAILURE_KIND,
            "status": STATUS,
            "round": fr["round"],
            "seed": fr["seed"],
            "candidate": fr.get("candidate"),
            "production_eligible": production,
            "reservation_sha256": (fr.get("registry") or {}).get("reservation_sha256"),
            "freeze_record_sha256": sha256_file(rp),
            "execution_start_sha256": sha256_file(d / CL.EXEC_START),  # raw bytes
            "execution_start_record": "unreadable" if start_unreadable(d) else "authenticated",
            "fetch_journal_sha256": _maybe(d / CL.FETCH_JOURNAL),
            "execution_abort_sha256": _maybe(d / CL.EXEC_ABORT),
            "execution_completed": (d / CL.EXEC_DONE).exists(),
            "failure_kind": kind,
            "failure_reason": reason,
            "collection_texts_sha256": _maybe(d / "texts.jsonl"),
            "cache_inventory_sha256": FZ.cache_inventory(raw)["sha256"],
            "archive": {"sha256": sha256_file(args.archive.resolve())},
            "receipt": receipt,
            "exposure": exposure,
            "sources_sha256": source_hashes(),
            "rule": "a failed, killed or aborted execution, or a completed collection that cannot "
            "reach labels (a shortfall or a pre-label step that cannot complete), consumes the "
            "round: procedure_failure (a non-pass; no labels, no acceptance arithmetic). Round 1: "
            "a fresh disjoint round 2 may follow only if the exposure is complete; round 2: "
            "terminal.",
        }
        rec["inputs_sha256"] = sha256_text(canonical_json(rec))
        data = (canonical_json(rec) + "\n").encode("utf-8")
        entry = failure_entry(fr, rec, hashlib.sha256(data).hexdigest())
        # audit r5 M1: same-output recovery. An existing private failure.json is accepted
        # only if it is byte for byte this registration's (an interrupted earlier run of
        # the same command); anything else is refused before the registry is touched,
        # unless --overwrite.
        if (
            (out / "failure.json").exists()
            and (out / "failure.json").read_bytes() != data
            and not args.overwrite
        ):
            raise SystemExit(
                f"{out / 'failure.json'} exists for another registration input; refused "
                "(use a fresh --out, or --overwrite)"
            )

        def make(entries):
            verdict, p = REG.check_decision(entries, entry)
            return verdict, p, entry

        if production:
            verdict, rprobs, written = REG.atomic_append(reg_path, make, REG.REPO)
        else:
            verdict, rprobs, written = make(REG.load(reg_path))
            if verdict == "append" and not rprobs:
                written = dict(entry, registered_at=FZ.now_iso())
                REG.append_unchecked(reg_path, written)
            elif verdict == "idempotent" and not rprobs:
                REG.acknowledge_unchecked(reg_path)
        if verdict not in ("append", "idempotent") or (verdict == "append" and rprobs):
            raise SystemExit("round registry refuses this failure:\n" + "\n".join(rprobs))
        registered = _registered_line(REG.load(reg_path), entry) or written or entry
        _write_failure_record(d, rec)
    # Write order: the registry line and the round marker (above, under the lock), then
    # the private failure.json, registration.json and the step manifest. A rerun of the
    # same command into the same --out after an interruption at any point recovers:
    # failure.json is identity-checked (above), registration.json is kept if it records
    # this registry and registered line, and the manifest is rewritten.
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "failure.json").exists() or args.overwrite:
        (out / "failure.json").write_bytes(data)
    reg_json = out / "registration.json"
    keep = False
    if reg_json.exists() and not args.overwrite:
        old = _read_record(reg_json)
        keep = (
            isinstance(old, dict)
            and old.get("registry") == str(reg_path)
            and old.get("entry") == registered
        )
        if not keep:
            raise SystemExit(
                f"{reg_json} exists and does not record this registration; refused "
                "(use a fresh --out, or --overwrite)"
            )
    if not keep:
        write_json(reg_json, {"registry": str(reg_path), "verdict": verdict, "entry": registered})
    write_step_manifest(out, "register_failure", [out / "failure.json", reg_json])
    tail = "" if exposure["complete"] else " (exposure NOT established: only terminal outcomes)"
    print(f"registered round {fr['round']}: {STATUS} ({verdict}){tail}")
    return 0


__all__ = [
    "main",
    "exposure_inventory",
    "authenticate_failed_round",
    "failed_execution",
    "failure_closed",
]
