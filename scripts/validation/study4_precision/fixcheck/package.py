"""The round package and its hash chain (audit r1 B2, B3; audit r2 B3, B5).

A round package is one directory (or a package.json mapping each part to a
path; relative paths resolve against the package.json's directory):

  collect/    freeze_record.json, collection.json, execution.json, texts.jsonl,
              texts/, manifest_collect.json
  replay/     replay.json (collect --replay-round of collect/)
  candidate/  CANDIDATE_SNAPSHOT.json, lexinspect/        (prepare-candidate)
  run/        run.json, pinned.json, verify_baseline.json, frames/
  diff/       frames.json, links/
  sample/     selection.json, units.jsonl, decision_plan.json, operational_power.json
  assign/     items.jsonl, key.jsonl, orders.json, assignments.json, batches/
  retry/      retry.json, retry_<role>.jsonl, orders_<role>.json, batches/  (default assign/retry)
  flash/      flash_ids.txt, orders.json, flash_assignment.json, batches/ (default assign/flash)
  sessions/   primary/, retry/, flash/    (export-sessions --out; deliveries.jsonl, delivered/)
  labels/     A.pass1.jsonl, B.pass1.jsonl, [A.retry.jsonl], [B.retry.jsonl],
              A.jsonl, B.jsonl (merged), [adjudicator.jsonl]
  verify/     verify.json

`check_package` verifies, link by link, collection -> replay -> candidate ->
run -> pinned-baseline verification -> diff -> selection and pre-label
decision plan -> assignment -> stage receipts -> session deliveries -> first
pass, retry, merge, Flash -> verification -> ledger, and returns every
problem found. In production any problem makes the package production-ineligible
and is passed to the acceptance calculation as a procedure problem, which makes
every module and the result inconclusive: never pass and never fail, even with a
breach certificate, which is still reported (clarifications section 3.4, "Incomplete
procedure"; accept.py amended after audit r2 N2, harness ruling A1). A dry-run
package is computed but stamped production_eligible false.

Authenticated derived facts (audit r2 B5). Parent hashes alone are not
enough: a self-consistent rewrite of a child with recomputed hashes would
pass. So every derived design fact is recomputed from its authenticated
parents at acceptance, with the CURRENT harness (whose source hashes must equal
the freeze record's):
- collection: quotas from texts.jsonl, the exclusion set from the bound
  development manifest and earlier rounds (and no collected identifier in it),
  per-text digests, the raw-response ledger (collect.authenticate_raw), the
  archived execution gate's receipt re-validated against committed objects
  (freeze.verify_receipt), and an authenticated replay record; for round 2, round 1's
  preservation (collect.round1_preservation_problems) and the bound narrowing check
  (narrowing.problems) again (round2_chain_problems);
- run: the configuration inventory (BASELINE, BASELINE_PINNED, COMPLETE and the
  12 families, hits and meta files) and the pinned-baseline verification;
- diff: the crosswalk, partition, frames and links are recomputed from the run
  frames into a scratch directory and must be byte-identical;
- sample: the selection (every N, N_h, n_h, seed and selected id), the label
  units (memberships and links) and the decision plan are re-derived from the
  seed and the authenticated diff and run, byte for byte;
- assign, retry, flash: items, key, orders, batches, retry manifests and the
  Flash assignment are re-derived from their authenticated inputs, byte for byte.
Every step manifest must hold its mandatory output inventory (REQUIRED), every
listed output must have its hash, and its harness source hashes and runtime
environment identity must equal the freeze record's.

Delivery (audit r2 B3). The delivery spec is the one BOUND in the freeze
record (path, file SHA-256, spec_sha256), re-checked against the registered
routes, prompt, preregistration and pilot hashes (sessions.check_spec). Each
stage's expected sessions are rebuilt from its authenticated batch manifests;
ids and batch bytes are compared; every primary role must be covered exactly
once; a missing expected session is never-delivered. Session ids, transcripts
and transcript paths are unique across the round's stages. Each stage was
exported only after its stage receipt (`stage-receipt`) was written; in
production that receipt is committed and on the registered receipt ref before
the export (pre-delivery archive), and acceptance re-validates it against the
committed objects and the package bytes.

Retry and Flash provenance (B3), recomputed with the frozen analyse.py
functions only:
- each role's retry manifest is analyse.write_retry_manifest of its validated
  first-pass file, byte for byte; retry.json names that first-pass file's hash;
- a non-empty manifest needs exactly one retry file (none: "skipped retry";
  more than one: "second retry"); an empty one forbids a retry file; the retry
  sessions' items must be exactly the manifest ids;
- the final file must equal analyse.merge_retry(first pass, retry, manifest
  ids), serialised as analyse.py --merge-retry writes it;
- analyse.needs_adjudication recomputed from the FINAL A and B files must equal
  flash_ids.txt as a set; flash_assignment.json must name the final files'
  hashes; the adjudicator sessions' items must be exactly the Flash ids;
- delivered-but-non-vote (a delivered session whose record is missing or
  invalid) is a legitimate unresolved label; an item in a NEVER-DELIVERED
  session (no delivery, or labels not matching the delivery record) is a
  procedure problem, in every stage.

The idempotence identity `inputs_sha256` (registry.py) is the SHA-256 of the
complete authenticated chain: every file of every part (path and SHA-256), the
freeze record, the bound delivery spec, the stage receipts, the acceptance
source identity (the harness source hashes) and the acceptance runtime identity.

Acceptance runtime (audit r3 S3). Historical manifests carry the runtime of the
stage that wrote them; that is not the runtime doing acceptance. `check_package`
therefore computes the runtime identity afresh in its own process
(freeze.acceptance_runtime: Python build, uv.lock, numpy/scipy, spaCy, thinc and
model package file hashes, the installed lexinspect distribution and the source
digest of the lexinspect it imports) and requires it to equal the freeze
record's `environment` (link "runtime"); production acceptance refuses before
any decision if it differs. The observed identity enters `inputs_sha256` and the
output (`acceptance_runtime`, with the imported third-party distributions).
"""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path
from typing import Any

import analyse

from fixcheck import common as C
from fixcheck.common import canonical_json, read_json, read_jsonl, sha256_file, sha256_text
from fixcheck.ledger import BASELINE, COMPLETE, FAMILIES, ledger_document

PARTS = (
    "collect",
    "replay",
    "candidate",
    "run",
    "diff",
    "sample",
    "assign",
    "retry",
    "flash",
    "sessions",
    "labels",
    "verify",
)
DEFAULT_PATHS = {"retry": "assign/retry", "flash": "assign/flash"}
ROLES = ("A", "B")
STAGES = ("primary", "retry", "flash")
RECEIPT_KIND = "fixcheck-stage-receipt"
# Parts (whole directories) and label files covered by each stage's pre-delivery receipt.
RECEIPT_PARTS = {
    "primary": ("collect", "replay", "candidate", "run", "diff", "sample", "assign"),
    "retry": ("retry",),
    "flash": ("flash",),
}
RECEIPT_LABELS = {
    "primary": (),
    "retry": ("A.pass1.jsonl", "B.pass1.jsonl"),
    "flash": (
        "A.pass1.jsonl",
        "B.pass1.jsonl",
        "A.retry.jsonl",
        "B.retry.jsonl",
        "A.jsonl",
        "B.jsonl",
    ),
}


def resolve(package: Path) -> dict[str, Path]:
    """Part -> path. A package.json maps parts to paths relative to its directory."""
    package = Path(package).resolve()
    spec = read_json(package) if package.is_file() else {}
    base = package.parent if package.is_file() else package
    return {"_root": base} | {
        k: (base / spec.get(k, DEFAULT_PATHS.get(k, k))).resolve() for k in PARTS
    }


def _need(p: Path, problems: list[str]) -> bool:
    if not p.exists():
        problems.append(f"missing {p}")
        return False
    return True


def part_files(P: dict[str, Path], part: str) -> dict[str, str]:
    """rel path -> SHA-256 of every file of one part, excluding nested other parts."""
    d = P[part]
    others = [P[k] for k in PARTS if k != part and P[k] != d and P[k].is_relative_to(d)]
    out = {}
    if d.is_dir():
        for f in sorted(d.rglob("*")):
            if (
                f.is_file()
                and "__pycache__" not in f.relative_to(d).parts
                and not any(f.is_relative_to(o) for o in others)
            ):
                out[f.relative_to(d).as_posix()] = sha256_file(f)
    return out


def environment_sha256(env: dict[str, Any] | None) -> str | None:
    return None if env is None else sha256_text(canonical_json(env))


def check_manifest(
    d: Path,
    step: str,
    required: list[str] | None = None,
    freeze: dict[str, Any] | None = None,
) -> list[str]:
    """manifest_<step>.json: every output has its recorded hash; the mandatory inventory is
    listed (REQUIRED, audit r2 B5); its harness sources and runtime environment are the
    freeze record's."""
    m = d / f"manifest_{step}.json"
    if not m.exists():
        return [f"missing {m}"]
    man = read_json(m)
    probs = []
    outs = man.get("outputs") or {}
    for rel, e in outs.items():
        f = d / rel
        if not f.exists() or sha256_file(f) != e["sha256"]:
            probs.append(f"{d.name}/{rel} differs from manifest_{step}.json")
    miss = sorted(set(required or []) - set(outs))
    if miss:
        probs.append(f"manifest_{step}.json omits mandatory outputs {miss[:5]}")
    if freeze is not None:
        if man.get("sources_sha256") != freeze.get("sources_sha256"):
            probs.append(f"manifest_{step}.json: harness sources differ from the freeze record's")
        if man.get("environment_sha256") != environment_sha256(freeze.get("environment")):
            probs.append(f"manifest_{step}.json: runtime environment differs from the freeze's")
    return probs


@contextlib.contextmanager
def _quiet_step():
    """Run another subcommand's main without disturbing the caller's recorded command."""
    saved = C._COMMAND
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        C._COMMAND = saved


def _rederive(name: str, run, expect_dir: Path, only: list[str] | None = None) -> list[str]:
    """Run `run(tmp)` into a scratch directory and require every file it writes (manifests
    excepted; `only` limits the comparison) to be byte-identical in `expect_dir`."""
    p: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "x"
        try:
            with _quiet_step():
                rc = run(tmp)
        except SystemExit as e:
            return [f"{name}: re-derivation refused: {e}"]
        if rc not in (0, None, 2):
            p.append(f"{name}: re-derivation exited {rc}")
        got = {
            f.relative_to(tmp).as_posix(): f
            for f in sorted(tmp.rglob("*"))
            if f.is_file() and not f.name.startswith("manifest_")
        }
        if only is not None:
            got = {k: v for k, v in got.items() if k in only}
        for rel, f in got.items():
            g = expect_dir / rel
            if not g.exists() or g.read_bytes() != f.read_bytes():
                p.append(f"{name}: {rel} is not what its authenticated inputs derive")
    return p


# --- collection ----------------------------------------------------------------------


def check_collect(P: dict[str, Path]) -> tuple[list[str], dict[str, Any]]:
    from fixcheck import collect as CL
    from fixcheck import freeze as FZ

    p: list[str] = []
    d = P["collect"]
    info: dict[str, Any] = {}
    for f in ("freeze_record.json", "collection.json", "execution.json", "texts.jsonl"):
        _need(d / f, p)
    if p:
        return p, info
    fr = read_json(d / "freeze_record.json")
    col = read_json(d / "collection.json")
    ex = read_json(d / "execution.json")
    if fr.get("kind") != FZ.FREEZE_KIND or fr.get("version") != FZ.FREEZE_VERSION:
        p.append("freeze record is not of this kind/version")
    fsha = sha256_file(d / "freeze_record.json")
    if col.get("freeze_record_sha256") != fsha:
        p.append("collection.json does not name this freeze record")
    if ex.get("freeze_record_sha256") != fsha:
        p.append("execution.json does not name this freeze record")
    if ex.get("collection_json_sha256") != sha256_file(d / "collection.json"):
        p.append("execution.json does not name this collection.json")
    if col.get("texts_jsonl_sha256") != sha256_file(d / "texts.jsonl"):
        p.append("texts.jsonl differs from collection.json")
    if col.get("status") != "complete":
        p.append(f"collection status {col.get('status')}: shortfall {col.get('shortfalls')}")
    production = fr.get("production_eligible") is True
    if not production:
        p.append(
            "freeze record not production-eligible: " + "; ".join(fr.get("ineligible_reasons", []))
        )
    if not col.get("production_eligible"):
        p.append("collection not production-eligible")
    if col.get("round") != fr.get("round") or col.get("seed") != fr.get("seed"):
        p.append("collection round/seed differ from the freeze record")
    texts = read_jsonl(d / "texts.jsonl")
    # quotas, recomputed from the texts (not the collection's own counts)
    p += _quota_problems(texts, col, CL)
    # per-text digests and the complete manifest (authenticate_collection)
    p += [f"collection: {x}" for x in CL.authenticate_collection(d)]
    # single execution (audit r3 B1): the start claim and the request journal are mandatory
    # outputs of a production collection (collect.execution_record_problems, through
    # authenticate_collection above, checks their bindings)
    claim = [CL.EXEC_START, CL.FETCH_JOURNAL] if production else []
    p += check_manifest(
        d,
        "collect",
        ["freeze_record.json", "texts.jsonl", "collection.json", "execution.json", *claim]
        + [f"texts/{t['text_id']}.txt" for t in texts],
        fr,
    )
    # the exclusion set and the raw-response ledger, recomputed from the bound inputs
    paths = fr.get("paths")
    if not paths:
        p.append("the freeze record has no collection paths (not a collect freeze record)")
    else:
        try:
            exclude, dev_info, earlier_info, digest = CL._exclusions(
                Path(paths["dev_texts"]), [Path(x) for x in paths["earlier"]], fr["round"]
            )
            if digest != (fr.get("exclusions") or {}).get("refs_sha256"):
                p.append("the recomputed exclusion set differs from the freeze record's")
            if dev_info.get("sha256") != (fr.get("dev_manifest") or {}).get("sha256"):
                p.append("the development manifest differs from the freeze record's")
            if canonical_json(earlier_info) != canonical_json(fr.get("earlier_rounds")):
                p.append("an earlier round differs from the freeze record's")
            import build

            overlap = build.exclusion_overlap(texts, exclude)
            if overlap:
                p.append(f"collected texts overlap the exclusion set: {overlap[:3]}")
        except (SystemExit, OSError, KeyError) as e:
            p.append(f"exclusions cannot be recomputed: {e}")
        raw = Path(paths["raw_cache"])
        auth = CL.authenticate_raw(col, raw) if raw.exists() else [f"raw cache {raw} missing"]
        p += [f"raw responses: {x}" for x in auth]
        if fr.get("round") == 2:
            p += round2_chain_problems(fr, paths)
    gate = ex.get("gate") or {}
    if production:
        if gate.get("ok") is not True:
            p.append("the execution gate (clean tree, candidate commit, archive receipt) failed")
        want = FZ.receipt_paths(d / "freeze_record.json", fr)
        p += [f"execution receipt: {x}" for x in FZ.verify_receipt(gate.get("receipt"), want=want)]
    info = {
        "round": fr.get("round"),
        "seed": fr.get("seed"),
        "candidate": fr.get("candidate"),
        "freeze_record": fr,
        "freeze_record_sha256": fsha,
        "collection_json_sha256": sha256_file(d / "collection.json"),
        "texts_jsonl_sha256": col.get("texts_jsonl_sha256"),
        "source_refs_sha256": source_refs_sha256(d / "texts.jsonl"),
        "ledger": fr.get("ledger"),
        "dry_run": fr.get("dry_run"),
        "production": production,
        "reservation_sha256": (fr.get("registry") or {}).get("reservation_sha256"),
        "round2": fr.get("round2"),
    }
    return p, info


def round2_chain_problems(fr: dict[str, Any], paths: dict[str, Any]) -> list[str]:
    """Round 2 at acceptance (round-2 harness audit r1, findings 1 and 2). Round 1 must still
    be as it was frozen and receipted (collect.round1_preservation_problems: its bound
    files, command.txt, manifest_plan.json and its execution receipt), and the narrowing
    check bound by the round-2 freeze record must still have its bound bytes and validate
    against that record (narrowing.problems: the round-2 candidate, round 1's registered
    candidate, the bound ledger, the frozen harness, the development manifest and the
    development round it gives). These are chain problems: any of them makes the package
    production-ineligible, and accept.compute then makes the status inconclusive, never
    pass or fail, whatever the labels give (audit r2 N2; see the module docstring)."""
    from fixcheck import collect as CL
    from fixcheck import narrowing as NC

    earlier = paths.get("earlier") or []
    if len(earlier) != 1:
        return ["a round-2 freeze record must name exactly one earlier round (round 1)"]
    d1 = Path(earlier[0])
    p = [f"round 1 preservation: {x}" for x in CL.round1_preservation_problems(d1)]
    r2 = fr.get("round2") or {}
    # round 1's candidate as the plan read it from the registered round-1 entry (bound by
    # round2.round1_entry_sha256, which registration checks against the registry)
    r1_cand = r2.get("round1_candidate") or {}
    nc = r2.get("narrowing_check") or {}
    path = Path(nc["path"]) if nc.get("path") else None
    if path is None or not nc.get("sha256"):
        p.append("the round-2 freeze record binds no narrowing check")
    elif not path.is_file() or sha256_file(path) != nc["sha256"]:
        p.append(f"the narrowing check {path} is missing or differs from the freeze record's")
    else:
        p += [
            f"narrowing check: {x}"
            for x in NC.file_problems(
                path,
                candidate=fr.get("candidate") or {},
                round1_candidate=r1_cand,
                ledger_md_sha256=((fr.get("ledger") or {}).get("markdown") or {}).get("sha256"),
                sources_sha256=fr.get("sources_sha256"),
                dev_texts_sha256=(fr.get("dev_manifest") or {}).get("sha256"),
                dev_round_texts_sha256=NC.dev_round_texts_sha256(
                    Path(paths["dev_texts"]) if paths.get("dev_texts") else None
                ),
            )
        ]
    return p


def _quota_problems(texts: list[dict[str, Any]], col: dict[str, Any], CL) -> list[str]:
    from collections import Counter

    p = []
    reg = Counter(t["register"] for t in texts)
    disc = Counter(t["discipline"] for t in texts if t["register"] == "academic")
    want_reg = {
        "academic": sum(CL.FIXCHECK_ACADEMIC_TARGETS.values()),
        "general": CL.FIXCHECK_WIKI_TARGET,
        "argumentative": CL.FIXCHECK_ESSAY_TARGET,
    }
    if dict(reg) != want_reg or len(texts) != CL.FIXCHECK_N:
        p.append(f"texts by register {dict(reg)} are not the registered quotas {want_reg}")
    if dict(disc) != CL.FIXCHECK_ACADEMIC_TARGETS:
        p.append(f"academic texts by discipline {dict(disc)} are not the registered quotas")
    if col.get("by_register") not in (None, dict(reg)):
        p.append("collection.json's register counts are not its texts'")
    return p


def source_refs_sha256(texts_jsonl: Path) -> list[str]:
    """The canonical source identities of a round's texts (build.read_exclusions: source id,
    URLs, DOI, title, normalised), each as a SHA-256: the registry's disjointness test."""
    import build

    return sorted(sha256_text(r) for r in build.read_exclusions(texts_jsonl))


def check_replay(P: dict[str, Path], cinfo: dict[str, Any]) -> list[str]:
    """An authenticated offline replay of the collection (audit r2 S3, S5)."""
    p: list[str] = []
    d = P["replay"]
    if not _need(d / "replay.json", p):
        return p
    r = read_json(d / "replay.json")
    for k in (
        "raw_responses_authenticated",
        "identical",
        "logs_identical",
        "text_reproducible",
        "archived_dates_consistent",
        "cache_files_unchanged",
    ):  # texts_jsonl_identical may differ on `retrieved` only (a restored file mtime, S3)
        if r.get(k) is not True:
            p.append(f"replay: {k} is not true")
    if r.get("texts_jsonl_sha256") != cinfo.get("texts_jsonl_sha256"):
        p.append("replay.json is not of this collection")
    if Path(r.get("round_dir") or "/nonexistent").resolve() != P["collect"].resolve():
        p.append("replay.json replayed another directory")
    p += check_manifest(d, "replay_round", ["replay.json"], cinfo.get("freeze_record"))
    return p


# --- candidate and run -------------------------------------------------------------


def check_candidate(P: dict[str, Path], cinfo: dict[str, Any]) -> list[str]:
    from fixcheck.run import pkg_digest

    p: list[str] = []
    d = P["candidate"]
    if not _need(d / "CANDIDATE_SNAPSHOT.json", p):
        return p
    snap = read_json(d / "CANDIDATE_SNAPSHOT.json")
    if pkg_digest(d / "lexinspect")["tree_sha256"] != snap.get("tree_sha256"):
        p.append("candidate snapshot changed after it was frozen")
    if not snap.get("production_eligible"):
        p.append(f"candidate snapshot: {snap.get('label', 'not from a commit')}")
    cand = cinfo.get("candidate") or {}
    if snap.get("commit") != cand.get("commit"):
        p.append("candidate snapshot commit is not the freeze record's candidate commit")
    if snap.get("tree_sha256") != cand.get("tree_sha256"):
        p.append("candidate snapshot digest is not the freeze record's candidate digest")
    if cinfo.get("production") and cand.get("commit"):
        from fixcheck import freeze as FZ

        try:
            if FZ.commit_src_digest(cand["commit"])["tree_sha256"] != snap.get("tree_sha256"):
                p.append("candidate snapshot is not the commit's src/lexinspect (git objects)")
        except SystemExit as e:
            p.append(f"candidate commit unreadable: {e}")
    return p


def check_run(P: dict[str, Path], cinfo: dict[str, Any]) -> list[str]:
    from fixcheck import run as R

    p: list[str] = []
    d = P["run"]
    for f in ("run.json", "verify_baseline.json", "pinned.json"):
        _need(d / f, p)
    if p:
        return p
    rj = read_json(d / "run.json")
    if rj.get("collection_sha256") != cinfo.get("collection_json_sha256"):
        p.append("run.json does not name this collection.json")
    if rj.get("texts_jsonl_sha256") != cinfo.get("texts_jsonl_sha256"):
        p.append("run texts differ from the collection's")
    if Path(rj.get("candidate_src") or "/nonexistent").resolve() != P["candidate"].resolve():
        p.append("run did not import the package's candidate snapshot")
    snap = rj.get("candidate_snapshot") or {}
    if snap.get("tree_sha256") != (cinfo.get("candidate") or {}).get("tree_sha256"):
        p.append("run's candidate snapshot is not the frozen candidate")
    if not rj.get("production_eligible"):
        p.append("run not production-eligible: " + "; ".join(rj.get("ineligible_reasons", [])))
    # configuration inventory (audit r2 B5)
    want = R.all_configs()
    if canonical_json(rj.get("configs")) != canonical_json(want):
        p.append("run configurations are not BASELINE, COMPLETE and the 12 families")
    configs = [*want, R.PINNED]
    req = [f"frames/{c}.{s}" for c in configs for s in ("hits.jsonl", "meta.json")]
    req += ["pinned.json", "verify_baseline.json", "run.json"]
    fenv = (cinfo.get("freeze_record") or {}).get("environment") or {}
    if rj.get("checkout_uv_lock_sha256") != fenv.get("uv_lock_sha256"):
        p.append("the run's uv.lock is not the freeze record's")
    vb = R.verify_baseline(d)
    if not vb["identical"]:
        p.append("pinned baseline verification failed: " + "; ".join(vb["problems"]))
    if read_json(d / "verify_baseline.json").get("identical") is not True:
        p.append("archived verify_baseline.json is not identical")
    p += check_manifest(d, "run", req, cinfo.get("freeze_record"))
    return p


# --- diff, sample, assign: re-derived ----------------------------------------------


def check_diff(P: dict[str, Path], cinfo: dict[str, Any] | None = None) -> list[str]:
    from fixcheck import crosswalk as X

    p: list[str] = []
    d, r = P["diff"], P["run"]
    if not _need(d / "frames.json", p):
        return p
    fr = read_json(d / "frames.json")
    if fr.get("run_json_sha256") != sha256_file(r / "run.json"):
        p.append("frames.json does not name this run.json")
    if fr.get("baseline_hits_sha256") != sha256_file(r / "frames" / f"{BASELINE}.hits.jsonl"):
        p.append("frames.json does not name this BASELINE frame")
    for c, h in (fr.get("candidate_hits_sha256") or {}).items():
        if h != sha256_file(r / "frames" / f"{c}.hits.jsonl"):
            p.append(f"frames.json does not name this {c} frame")
    configs = [COMPLETE, *FAMILIES]
    if list(fr.get("configs", [])) != configs:
        p.append(f"diff configurations {fr.get('configs')} are not COMPLETE + the 12 families")
    req = ["frames.json"] + [
        f"links/{c}.{s}.jsonl" for c in configs for s in ("baseline", "candidate")
    ]
    p += check_manifest(d, "diff", req, (cinfo or {}).get("freeze_record"))
    p += _rederive("diff", lambda t: X.main(["--run-dir", str(r), "--out", str(t)]), d)
    return p


def check_sample(P: dict[str, Path], cinfo: dict[str, Any]) -> list[str]:
    from fixcheck import sampling as S

    p: list[str] = []
    d = P["sample"]
    for f in ("selection.json", "units.jsonl", "decision_plan.json", "operational_power.json"):
        if not (d / f).exists():
            p.append(
                f"missing {d / f}"
                + (" (pre-label decision plan)" if "plan" in f or "power" in f else "")
            )
    if p:
        return p
    sel = read_json(d / "selection.json")
    if sel["inputs"].get("frames_json_sha256") != sha256_file(P["diff"] / "frames.json"):
        p.append("selection.json does not name this frames.json")
    if sel["inputs"].get("baseline_hits_sha256") != sha256_file(
        P["run"] / "frames" / f"{BASELINE}.hits.jsonl"
    ):
        p.append("selection.json does not name this BASELINE frame")
    if sel.get("round_seed") != cinfo.get("seed"):
        p.append("selection seed is not the collection's seed")
    if not sel.get("production_eligible"):
        p.append("selection not production-eligible")
    pw = read_json(d / "operational_power.json")
    if pw.get("reps", 0) <= 0 or not pw.get("scenarios"):
        p.append("operational power was not simulated")
    if pw.get("selection_sha256") not in (None, sha256_file(d / "selection.json")):
        p.append("operational_power.json is not of this selection")
    plan = read_json(d / "decision_plan.json")
    p += check_manifest(
        d,
        "sample",
        ["selection.json", "units.jsonl", "decision_plan.json", "operational_power.json"],
        cinfo.get("freeze_record"),
    )
    # the registered draw, re-derived from the seed and the authenticated parents
    argv = [
        "--run-dir",
        str(P["run"]),
        "--diff-dir",
        str(P["diff"]),
        "--round-seed",
        str(cinfo.get("seed")),
        "--plan-reps",
        str(plan.get("reps", 0)),
        "--power-reps",
        "-1",
    ]
    p += _rederive("sample", lambda t: S.main([*argv, "--out", str(t)]), d)
    return p


def _batch_files(stage_dir: Path, role: str, prefix: str) -> list[str]:
    man = stage_dir / "batches" / role / prefix / f"{prefix}_manifest.json"
    if not man.exists():
        return []
    rel = man.relative_to(stage_dir).as_posix()
    base = man.parent.relative_to(stage_dir).as_posix()
    return [rel] + [f"{base}/{b['file']}" for b in read_json(man)["batches"]]


def check_assign(P: dict[str, Path], cinfo: dict[str, Any]) -> list[str]:
    import batches

    from fixcheck import assign as AS

    p: list[str] = []
    d = P["assign"]
    for f in ("items.jsonl", "key.jsonl", "orders.json", "assignments.json"):
        _need(d / f, p)
    if p:
        return p
    a = read_json(d / "assignments.json")
    if a.get("units_sha256") != sha256_file(P["sample"] / "units.jsonl"):
        p.append("assignments.json does not name this units.jsonl")
    if a.get("selection_sha256") != sha256_file(P["sample"] / "selection.json"):
        p.append("assignments.json does not name this selection.json")
    o = read_json(d / "orders.json")
    if o.get("seed") != cinfo.get("seed"):
        p.append("assignment seed is not the round seed")
    sizes = set()
    for role, r in o["roles"].items():
        sizes.add(r.get("requested_batch_size", r["batch_size"]))
        if r["batch_size"] > batches.MODEL_BATCH_SIZE:
            p.append(f"role {role} batch size {r['batch_size']} exceeds 325")
    req = ["items.jsonl", "key.jsonl", "orders.json", "assignments.json"]
    for role in ROLES:
        req += _batch_files(d, role, "batch") or [f"batches/{role}/batch/batch_manifest.json"]
    p += check_manifest(d, "assign", req, cinfo.get("freeze_record"))
    if len(sizes) == 1:
        bs = str(sizes.pop())
        p += _rederive(
            "assign",
            lambda t: AS.main(
                ["--sample-dir", str(P["sample"]), "--out", str(t), "--batch-size", bs]
            ),
            d,
        )
    else:
        p.append("assignment roles have different batch sizes")
    return p


# --- stage receipts (pre-delivery archive) -----------------------------------------


def stage_receipt(P: dict[str, Path], stage: str, spec_path: Path | None) -> dict[str, Any]:
    """The pre-delivery receipt of one stage: SHA-256 of every file it covers (hashes and
    relative names only; no payload, gloss or example text)."""
    cfr = P["collect"] / "freeze_record.json"
    rec: dict[str, Any] = {
        "kind": RECEIPT_KIND,
        "stage": stage,
        "freeze_record_sha256": sha256_file(cfr) if cfr.exists() else None,
        "parts": {part: part_files(P, part) for part in RECEIPT_PARTS[stage]},
        "labels": {
            n: sha256_file(P["labels"] / n)
            for n in RECEIPT_LABELS[stage]
            if (P["labels"] / n).exists()
        },
        "delivery_spec_sha256": sha256_file(spec_path) if spec_path else None,
    }
    return rec


def check_stage_receipt(
    P: dict[str, Path], stage: str, index: dict[str, Any], spec_path: Path | None, production: bool
) -> list[str]:
    """The stage's export named a receipt that (a) still matches the package bytes and (b) in
    production was committed and on the registered receipt ref before the export."""
    from fixcheck import freeze as FZ

    sr = index.get("stage_receipt") or {}
    if not sr.get("path"):
        return [f"{stage}: the sessions were exported without a pre-delivery stage receipt"]
    p: list[str] = []
    rp = Path(sr["path"])
    if not rp.exists() or sha256_file(rp) != sr.get("sha256"):
        return [f"{stage}: stage receipt {rp} missing or changed since the export"]
    rec = read_json(rp)
    want = stage_receipt(P, stage, spec_path)
    if rec.get("kind") != RECEIPT_KIND or rec.get("stage") != stage:
        p.append(f"{stage}: {rp.name} is not a {stage} stage receipt")
    for k in ("freeze_record_sha256", "delivery_spec_sha256"):
        if rec.get(k) != want.get(k):
            p.append(f"{stage}: stage receipt {k} differs from the package")
    for part, files in want["parts"].items():
        if canonical_json(rec.get("parts", {}).get(part)) != canonical_json(files):
            p.append(f"{stage}: {part} changed since its pre-delivery receipt")
    if canonical_json(rec.get("labels")) != canonical_json(want["labels"]):
        p.append(f"{stage}: label files changed since the pre-delivery receipt")
    archive = sr.get("archive")
    if production:
        p += [f"{stage}: receipt archive: {x}" for x in FZ.verify_receipt(archive, want=[rp])]
    elif not archive:
        p.append(
            f"{stage}: the stage receipt was not archived (committed and pushed) before delivery"
        )
    return p


# --- labels and deliveries ---------------------------------------------------------


def _requested(role_order: dict[str, Any]) -> int:
    return role_order.get("requested_batch_size", role_order["batch_size"])


def _merged_bytes(pass1: Path, retry: Path | None, manifest_ids: list[str]) -> bytes:
    orig = pass1.read_text(encoding="utf-8").splitlines()
    rt = retry.read_text(encoding="utf-8").splitlines() if retry is not None else []
    merged, _ = analyse.merge_retry(orig, rt, manifest_ids)
    return "".join(x + "\n" for x in merged).encode("utf-8")


def bound_spec(cinfo: dict[str, Any]) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    """The delivery spec bound in the freeze record (audit r2 B3), re-checked."""
    from fixcheck import sessions as S

    fr = cinfo.get("freeze_record") or {}
    b = (fr.get("bound") or {}).get("delivery_spec") or {}
    want_sha = (fr.get("delivery") or {}).get("spec_sha256")
    if not b.get("path") or not want_sha:
        return None, None, ["the freeze record binds no delivery spec"]
    path = Path(b["path"])
    if not path.exists() or sha256_file(path) != b.get("sha256"):
        return None, path, ["the bound delivery spec is missing or changed since the freeze"]
    spec = read_json(path)
    p = []
    if spec.get("spec_sha256") != want_sha:
        p.append("the bound delivery spec is not the freeze record's spec_sha256")
    p += [f"delivery spec: {x}" for x in S.check_spec(spec)]
    return spec, path, p


def check_labels(
    P: dict[str, Path], cinfo: dict[str, Any] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """First pass, retry, merge and Flash provenance (B3) plus session deliveries (S2) under
    the bound spec, rebuilt expected sessions and pre-delivery receipts (audit r2 B3, B5)."""
    from fixcheck import assign as AS
    from fixcheck import sessions as S

    if cinfo is None:
        _, cinfo = check_collect(P)
    p: list[str] = []
    info: dict[str, Any] = {"never_delivered": {}, "delivered_non_votes": {}}
    a, L, sess = P["assign"], P["labels"], P["sessions"]
    spec, spec_path, sp = bound_spec(cinfo)
    p += sp
    if spec is None:
        return p, info
    production = bool(cinfo.get("production"))
    stage_dirs = {"primary": a, "retry": P["retry"], "flash": P["flash"]}

    def stage(st: str, label_file: Path, role: str) -> dict[str, Any]:
        res = S.check_stage(sess / st, label_file, role, st, stage_dirs[st], spec)
        info["never_delivered"][f"{st}|{role}"] = len(res["never_delivered"].get(role, []))
        return res

    for st in STAGES:
        ix = sess / st / "sessions_index.json"
        if ix.exists():
            idx = read_json(ix)
            p += check_stage_receipt(P, st, idx, spec_path, production)
            if production and not idx.get("production_fresh_root"):
                p.append(f"{st}: sessions were not exported to a fresh neutral temporary root")
    items = {r["id"]: r for r in read_jsonl(a / "items.jsonl")}
    key = read_jsonl(a / "key.jsonl")
    retry_dir = P["retry"]
    retry_rec = read_json(retry_dir / "retry.json") if (retry_dir / "retry.json").exists() else None
    if retry_rec is None:
        p.append("missing retry.json: the registered retry step was not run")
    finals = {}
    for role in ROLES:
        pass1, final = L / f"{role}.pass1.jsonl", L / f"{role}.jsonl"
        if not (_need(pass1, p) and _need(final, p)):
            continue
        res = stage("primary", pass1, role)
        p += [f"primary {role}: {x}" for x in res["problems"]]
        ls1 = analyse.load_labels(pass1, items, None, role)
        with tempfile.TemporaryDirectory() as td:
            man = Path(td) / "m.jsonl"
            analyse.write_retry_manifest(ls1, man)
            want_manifest = man.read_bytes()
        arch = retry_dir / f"retry_{role}.jsonl"
        if not arch.exists() or arch.read_bytes() != want_manifest:
            p.append(f"retry manifest of {role} is not the first-pass file's own retry list")
        if retry_rec is not None and (retry_rec["roles"].get(role) or {}).get(
            "labels_sha256"
        ) != sha256_file(pass1):
            p.append(f"retry.json does not name {role}'s first-pass file")
        manifest_ids = [r["id"] for r in ls1.retry]
        retries = sorted(L.glob(f"{role}.retry*.jsonl"))
        if len(retries) > 1:
            p.append(
                f"{role}: more than one retry file ({[x.name for x in retries]}): a second retry"
            )
        rfile = L / f"{role}.retry.jsonl"
        if manifest_ids and not rfile.exists():
            p.append(
                f"{role}: {len(manifest_ids)} records needed the registered retry, which was skipped"
            )
        if not manifest_ids and rfile.exists():
            p.append(f"{role}: a retry file exists with an empty retry manifest")
        if manifest_ids and rfile.exists():
            rs = stage("retry", rfile, role)
            p += [f"retry {role}: {x}" for x in rs["problems"]]
            idx = (
                read_json(sess / "retry" / "sessions_index.json")
                if (sess / "retry" / "sessions_index.json").exists()
                else {"sessions": []}
            )
            ids = sorted(i for s in idx["sessions"] if s["role"] == role for i in s["ids"])
            if ids != sorted(manifest_ids):
                p.append(f"retry sessions of {role} do not hold exactly the retry manifest ids")
        merged = _merged_bytes(pass1, rfile if rfile.exists() else None, manifest_ids)
        if final.read_bytes() != merged:
            p.append(f"{role}.jsonl is not the deterministic merge of its first pass and retry")
        finals[role] = final
    if retry_rec is not None and set(finals) == set(ROLES):
        bs = {
            _requested(read_json(retry_dir / f"orders_{r}.json")["roles"][r])
            for r in ROLES
            if (retry_dir / f"orders_{r}.json").exists()
        }
        argv = ["--assign-dir", str(a), "--labels"]
        argv += [f"{r}={L / f'{r}.pass1.jsonl'}" for r in ROLES]
        argv += ["--batch-size", str(bs.pop() if len(bs) == 1 else 325)]
        p += _rederive("retry", lambda t: AS.main_retry([*argv, "--out", str(t)]), retry_dir)
        p += check_manifest(
            retry_dir,
            "retry",
            ["retry.json"]
            + [
                f
                for r in ROLES
                for f in (
                    f"retry_{r}.jsonl",
                    f"orders_{r}.json",
                    *_batch_files(retry_dir, r, "retry"),
                )
            ],
            cinfo.get("freeze_record"),
        )
    if set(finals) != set(ROLES):
        return p, info
    prim = [analyse.load_labels(finals[r], items, None, r) for r in ROLES]
    for ls in prim:
        info["delivered_non_votes"][ls.name] = len(ls.retry)
    rows = [{"id": k["id"], "module": k["module"], "category": k["category"]} for k in key]
    need = analyse.needs_adjudication(rows, prim)
    fd = P["flash"]
    if not _need(fd / "flash_ids.txt", p):
        return p, info
    fids = (fd / "flash_ids.txt").read_text().split()
    if set(fids) != set(need):
        p.append(
            f"Flash set differs from needs_adjudication on the final A/B files "
            f"({len(set(need) - set(fids))} omitted, {len(set(fids) - set(need))} extra)"
        )
    fa = read_json(fd / "flash_assignment.json") if (fd / "flash_assignment.json").exists() else {}
    want = {r: sha256_file(finals[r]) for r in ROLES}
    if fa.get("label_files_sha256") != want:
        p.append("flash_assignment.json does not name the final A/B files")
    p += check_manifest(
        fd,
        "flash",
        ["flash_ids.txt", "orders.json", "flash_assignment.json"]
        + _batch_files(fd, "adjudicator", "batch"),
        cinfo.get("freeze_record"),
    )
    fo = read_json(fd / "orders.json") if (fd / "orders.json").exists() else {"roles": {}}
    fbs = _requested(fo["roles"].get("adjudicator") or {"batch_size": 325})
    fargv = ["--assign-dir", str(a), "--labels", f"A={finals['A']}", f"B={finals['B']}"]
    fargv += ["--batch-size", str(fbs)]
    p += _rederive("flash", lambda t: AS.main_flash([*fargv, "--out", str(t)]), fd)
    adj = L / "adjudicator.jsonl"
    if fids:
        if _need(adj, p):
            rs = stage("flash", adj, "adjudicator")
            p += [f"flash: {x}" for x in rs["problems"]]
            fx = sess / "flash" / "sessions_index.json"
            idx = read_json(fx) if fx.exists() else {"sessions": []}
            ids = sorted(i for s in idx["sessions"] for i in s["ids"])
            if ids != sorted(fids):
                p.append("adjudicator sessions do not hold exactly the Flash ids")
    elif adj.exists():
        p.append("adjudicator labels exist but no item needed adjudication")
    for k, v in info["never_delivered"].items():
        if v:
            p.append(f"{k}: {v} items were never delivered (procedure gap, not non-votes)")
    ident = S.session_identities([sess / st for st in STAGES])
    p += [f"sessions: {x}" for x in ident["problems"]]
    info["sessions"] = {k: ident[k] for k in ("session_ids_sha256", "transcripts_sha256")}
    info["label_files_sha256"] = {
        f.name: sha256_file(f) for f in sorted(L.glob("*.jsonl")) if f.is_file()
    }
    return p, info


# --- verify and ledger -----------------------------------------------------------------


def check_verify(P: dict[str, Path], cinfo: dict[str, Any] | None = None) -> list[str]:
    """verify.json was run on exactly this package's run, ledger, sample, assignment, retry
    and Flash directories (audit r2 B5), and is ok."""
    p: list[str] = []
    d = P["verify"]
    if not _need(d / "verify.json", p):
        return p
    v = read_json(d / "verify.json")
    if not v.get("ok"):
        p.append("verify.json is not ok")
    if "blinding" not in v:
        p.append("verify.json has no blinding audit")
    inp = v.get("inputs", {})
    for name, path in (
        ("key_jsonl_sha256", P["assign"] / "key.jsonl"),
        ("items_jsonl_sha256", P["assign"] / "items.jsonl"),
        ("selection_json_sha256", P["sample"] / "selection.json"),
        ("run_json_sha256", P["run"] / "run.json"),
    ):
        if not path.exists() or inp.get(name) != sha256_file(path):
            p.append(f"verify.json was not run on this package ({name})")
    led = ((cinfo or {}).get("ledger") or {}).get("markdown") or {}
    if inp.get("ledger_md_sha256") != led.get("sha256"):
        p.append("verify.json checked another ledger than the freeze record's")
    stages = v.get("stage_inputs") or {}
    want = {
        "retry": [_maybe(P["retry"] / "retry.json")],
        "flash": [_maybe(P["flash"] / "flash_ids.txt")],
    }
    for k, w in want.items():
        if sorted(x for x in stages.get(k, []) if x) != sorted(x for x in w if x):
            p.append(f"verify.json did not audit exactly this package's {k} directory")
    p += check_manifest(d, "verify", ["verify.json"], (cinfo or {}).get("freeze_record"))
    return p


def check_ledger(cinfo: dict[str, Any]) -> list[str]:
    from fixcheck import freeze as FZ

    p: list[str] = []
    led = cinfo.get("ledger") or {}
    md = Path((led.get("markdown") or {}).get("path") or "/nonexistent")
    comp = Path((led.get("components") or {}).get("path") or "/nonexistent")
    now = FZ.ledger_identity(md, comp if comp.exists() else None)
    if now["markdown"].get("sha256") is None or now["markdown"]["sha256"] != (
        led.get("markdown") or {}
    ).get("sha256"):
        p.append("ledger Markdown missing or changed since the freeze")
    if now["components"].get("sha256") is None or now["components"]["sha256"] != (
        led.get("components") or {}
    ).get("sha256"):
        p.append("ledger_components.json missing or changed since the freeze")
    if now["markdown"].get("draft", True) is not False:
        p.append(f"ledger status is {now['markdown'].get('status')!r}, not final")
    if comp.exists() and read_json(comp) != ledger_document():
        p.append("ledger_components.json differs from the harness's 68 identities")
    return p


# --- the package ---------------------------------------------------------------------------


def check_package(package: Path) -> dict[str, Any]:
    P = resolve(package)
    out: dict[str, Any] = {"package": str(P["_root"]), "problems": [], "links": {}}

    def add(name: str, probs: list[str]) -> None:
        out["links"][name] = {"ok": not probs, "problems": probs}
        out["problems"] += [f"[{name}] {x}" for x in probs]

    cp, cinfo = check_collect(P)
    add("collect", cp)
    add("replay", check_replay(P, cinfo))
    add("candidate", check_candidate(P, cinfo))
    add("run", check_run(P, cinfo))
    add("diff", check_diff(P, cinfo))
    add("sample", check_sample(P, cinfo))
    add("assign", check_assign(P, cinfo))
    lp, linfo = check_labels(P, cinfo)
    add("labels", lp)
    add("verify", check_verify(P, cinfo))
    add("ledger", check_ledger(cinfo))
    # audit r3 S3: the runtime doing this check, observed now, must be the frozen runtime
    from fixcheck import freeze as FZ

    observed = FZ.acceptance_runtime()
    frozen_env = (cinfo.get("freeze_record") or {}).get("environment")
    add("runtime", FZ.runtime_problems(frozen_env, observed))
    out["acceptance_runtime"] = observed
    out["collection"] = {k: v for k, v in cinfo.items() if k != "freeze_record"}
    out["labels"] = linfo
    out["sessions"] = linfo.get("sessions") or {"session_ids_sha256": [], "transcripts_sha256": []}
    spec = (cinfo.get("freeze_record") or {}).get("bound", {}).get("delivery_spec") or {}
    receipts = {}
    for st in STAGES:
        ix = P["sessions"] / st / "sessions_index.json"
        if ix.exists():
            receipts[st] = (read_json(ix).get("stage_receipt") or {}).get("sha256")
    chain = {
        "freeze_record_sha256": cinfo.get("freeze_record_sha256"),
        "delivery_spec_sha256": spec.get("sha256"),
        "stage_receipts": receipts,
        "parts": {part: part_files(P, part) for part in PARTS},
        "acceptance_sources_sha256": C.source_hashes(),
        "acceptance_runtime": observed["environment"],
    }
    out["chain_summary"] = {
        "freeze_record_sha256": chain["freeze_record_sha256"],
        "delivery_spec_sha256": chain["delivery_spec_sha256"],
        "stage_receipts": receipts,
        "n_files": {k: len(v) for k, v in chain["parts"].items()},
        "parts_sha256": {k: sha256_text(canonical_json(v)) for k, v in chain["parts"].items()},
        "acceptance_sources_sha256": sha256_text(
            canonical_json(chain["acceptance_sources_sha256"])
        ),
        "acceptance_runtime_sha256": observed["environment_sha256"],
    }
    out["inputs_sha256"] = sha256_text(canonical_json(chain))
    out["production_eligible"] = not out["problems"]
    return out


def _maybe(p: Path) -> str | None:
    return sha256_file(p) if p.exists() else None
