"""Study 4 Stage 1: build the freeze manifest, docs/validation/study4-freeze.json.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/freeze.py [--check]

It records, with SHA-256 throughout, every input the Stage-1 package depends on:

- the release: lexinspect 0.4.0, tag v0.4.0 and its commit. The working tree's
  src/, pyproject.toml and uv.lock must equal the tag blob for blob, with no
  extra files under src/; otherwise the build stops;
- the detector: every tracked file under src/;
- the environment: Python, spaCy, en_core_web_sm (its RECORD hash, and every
  installed file checked against the RECORD), the lock file and pyproject.toml;
- the guidelines, the sense inventory, the registered prompt template and the
  delivery spec;
- the labelling code and effective launch settings per role, and the CLI
  versions recorded in the 0.4.0 pilot's own session archive;
- all Study 4 code: every tracked file under scripts/validation/study4_precision/;
- the 0.4.0 pilot: public records, the rebuild, and every file of the private
  archive (selection, sessions with their provider records, labels, validation,
  analysis, probes, dry run);
- the 0.3.2 history: the original development build, the 16 Oct pilot cache, its
  provider session records (copied into the private archive on 2026-10-21) and
  the historical simulation with its key and frame;
- the evaluation pool cache: every file of .cache/validation/study4/raw, which
  the evaluation copy is verified against;
- both simulation bundles, file by file, and the tail-table tool;
- the fix check: its tracked public records; every current file named in the
  stage receipts; the unchanged archived tars; the later access-review addenda;
  the post-decision event archive, including its checksums and their targets;
  and the versioned inventory of retained launch/access-review scripts and cited
  review reports. The manifest separately identifies the immutable
  decision-time packages and the later disclosure evidence. Both are required
  and checked against the deposited hashes;
- the exclusions, the evaluation seed, preparation and command;
- the protocol documents, the archive inventory, the Stage-1 snapshot of the
  access log, the effects report, the public text-free export and the Stage-1
  review records.

Every SHA256SUMS file in a bound private folder is checked against the current
bytes. The pinned baseline checkout (pinned-dec79bc/) is checked blob for blob
against its commit, apart from its .venv, which is an environment cache.

The live access log, docs/validation/study4-access-log.md, is an
append-only administrative record: the manifest names it but doesn't hash it,
so recording an access request never requires rebuilding the manifest. Its
Stage-1 state is the hashed snapshot docs/validation/study4-access-log.stage1.md.

Every input is required. A missing file, a receipt or tar whose current bytes
differ from its recorded hash, a model file that differs from its RECORD, or a
working tree that differs from the tag stops the build with exit 2.

--check rebuilds the manifest in memory and exits 1 if it differs from the file
on disk. It ignores the "observed" section (build time, the commit it was built
from, the CLI versions installed now), which it reports as information. The
external deposit's receipt is kept in a separate file,
docs/validation/study4-freeze-deposit.json, so recording it doesn't change the
manifest.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import importlib.metadata as md
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
S4 = REPO / "scripts" / "validation" / "study4_precision"
sys.path.insert(0, str(S4))
sys.path.insert(0, str(S4 / "pilot040"))
import build  # noqa: E402
import launch  # noqa: E402

OUT = REPO / "docs" / "validation" / "study4-freeze.json"
DEPOSIT = REPO / "docs" / "validation" / "study4-freeze-deposit.json"
PRIVATE = Path.home() / "lexinspect-private"
PILOT040 = PRIVATE / "study4-pilot040"
FIX040 = PRIVATE / "study4-fix040"
CACHE = REPO / ".cache" / "validation"
DEV = CACHE / "study4"
V040 = CACHE / "study4_v040"
PILOT032 = CACHE / "study4_pilot"
SCRATCH = CACHE / "study4_scratch"
SIM040 = SCRATCH / "sim040"
SIM032 = SCRATCH / "sim_final"
DEV032 = SCRATCH / "dev032"
EVAL_SEED = 3195330621
EVAL_SEED_RULE = 'int(sha256("study4-v040-evaluation|20261016").hexdigest()[:8], 16)'
EXCLUSIONS = REPO / "docs" / "validation" / "study4-exclusions" / "exclusions.jsonl"
SKIP_NAMES = {".DS_Store"}
FIXCACHE = CACHE / "study4_fix040"
PINNED = FIX040 / "pinned-dec79bc"
ACCESS_LOG = REPO / "docs" / "validation" / "study4-access-log.md"
ACCESS_LOG_STAGE1 = REPO / "docs" / "validation" / "study4-access-log.stage1.md"

# Files the package cannot do without. They are also hashed inside the trees
# below; listing them here makes their absence a build failure, not just a
# smaller tree.
KEY_FILES = [
    *(
        PILOT040 / "labels" / n
        for n in (
            "A_batch.jsonl",
            "A_retry.jsonl",
            "A_merged.jsonl",
            "B_batch.jsonl",
            "needs_adjudication.txt",
            "adjudicator_adjudication.jsonl",
        )
    ),
    PILOT040 / "analysis" / "pilot.json",
    PILOT040 / "analysis" / "flash_diagnostics.json",
    PILOT040 / "selection" / "build" / "SHA256SUMS",
    PILOT040 / "sessions" / "launch_log.jsonl",
    *(V040 / n for n in ("texts.jsonl", "hits.jsonl", "items.jsonl", "key.jsonl", "frame.json")),
    *(DEV / n for n in ("texts.jsonl", "hits.jsonl", "items.jsonl", "key.jsonl", "manifest.json")),
    *(
        SIM040 / n
        for n in (
            "frozen_sources.sha256",
            "inventory.json",
            "all.json",
            "final.json",
            "final.md",
            "result_hashes.sha256",
            "SUMMARY.md",
            "tail_table.txt",
        )
    ),
    *(SIM032 / n for n in ("inventory.json", "final.json", "result_hashes.sha256")),
    DEV032 / "key.jsonl",
    DEV032 / "frame.json",
    *(FIX040 / f"round{r}" / "transcripts" / "ACCESS_REVIEW_RULINGS.md" for r in (1, 2)),
    FIX040 / "post_decision_events" / "README.md",
    FIX040 / "post_decision_events" / "SHA256SUMS",
    PINNED / "PINNED_COMMIT.json",
    *(FIXCACHE / "final_audit" / n for n in ("RESPONSES_r1.md", "sol_final_audit_r2.md")),
    ACCESS_LOG_STAGE1,
]

PROBLEMS: list[str] = []


def problem(msg: str) -> None:
    PROBLEMS.append(msg)


def label(p: Path) -> str:
    for root, name in ((REPO, ""), (PRIVATE, "lexinspect-private/")):
        if p.is_relative_to(root):
            return name + str(p.relative_to(root))
    return str(p)


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def need(p: Path) -> str | None:
    h = sha(p)
    if h is None:
        problem(f"missing: {label(p)}")
    return h


def files(paths: list[Path]) -> dict[str, str | None]:
    return {label(p): need(p) for p in paths}


def tree(root: Path, exclude: tuple[str, ...] = ()) -> dict[str, str | None]:
    """Every file under root, keyed by its path relative to root."""
    if not root.is_dir():
        problem(f"missing directory: {label(root)}")
        return {}
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or p.name in SKIP_NAMES or "__pycache__" in rel.parts:
            continue
        if any(str(rel) == e or str(rel).startswith(e + "/") for e in exclude):
            continue
        out[str(rel)] = h = sha(p)
        if h is None:
            problem(f"unreadable: {label(p)}")
    if not out:
        problem(f"empty directory: {label(root)}")
    return out


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def tracked(prefix: str) -> dict[str, str | None]:
    names = git("ls-files", prefix).splitlines()
    if not names:
        problem(f"no tracked files under {prefix}")
    return {f: need(REPO / f) for f in names}


def release_equality() -> dict[str, Any]:
    """Compare the working tree with tag v0.4.0, blob for blob."""
    listing = git("ls-tree", "-r", "v0.4.0", "--", "src", "pyproject.toml", "uv.lock")
    tag = {}
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        tag[path] = meta.split()[2]
    differ = []
    for path, blob in tag.items():
        p = REPO / path
        if not p.is_file() or git("hash-object", "--", path) != blob:
            differ.append(path)
    extra = sorted(
        str(p.relative_to(REPO))
        for p in (REPO / "src").rglob("*")
        if p.is_file()
        and p.name not in SKIP_NAMES
        and "__pycache__" not in p.parts
        and str(p.relative_to(REPO)) not in tag
    )
    for path in differ:
        problem(f"working tree differs from v0.4.0: {path}")
    for path in extra:
        problem(f"file under src/ not in v0.4.0: {path}")
    return {"files_compared": len(tag), "differ": differ, "extra": extra}


def model_record() -> dict[str, Any]:
    try:
        dist = md.distribution("en_core_web_sm")
    except md.PackageNotFoundError:
        problem("en_core_web_sm is not installed")
        return {}
    rec = next((f for f in dist.files or [] if f.name == "RECORD"), None)
    if rec is None:
        problem("en_core_web_sm has no RECORD")
        return {"version": dist.version}
    rec_path = Path(dist.locate_file(rec))
    checked, bad = 0, []
    for line in rec_path.read_text().splitlines():
        parts = line.rsplit(",", 2)
        if len(parts) != 3 or not parts[1].startswith("sha256="):
            continue  # RECORD itself and files listed without a hash
        p = Path(dist.locate_file(parts[0]))
        want = parts[1][len("sha256=") :]
        got = (
            base64.urlsafe_b64encode(hashlib.sha256(p.read_bytes()).digest()).rstrip(b"=").decode()
            if p.is_file()
            else None
        )
        checked += 1
        if got != want:
            bad.append(parts[0])
    for path in bad:
        problem(f"en_core_web_sm file differs from its RECORD: {path}")
    return {
        "version": dist.version,
        "record_sha256": sha(rec_path),
        "files_checked_against_record": checked,
    }


def pilot_cli_versions() -> dict[str, Any]:
    """CLI versions as recorded in the 0.4.0 pilot's own session archive."""
    found: dict[str, set[str]] = {"A": set(), "B": set()}
    for role, name, key in (
        ("A", "stream.jsonl", "claude_code_version"),
        ("B", "rollout.jsonl", "cli_version"),
    ):
        for p in sorted((PILOT040 / "sessions" / role).glob(f"*/{name}")):
            for line in p.read_text().splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stack = [rec]
                while stack:
                    x = stack.pop()
                    if isinstance(x, dict):
                        if isinstance(x.get(key), str):
                            found[role].add(x[key])
                        stack.extend(x.values())
                    elif isinstance(x, list):
                        stack.extend(x)
    for role in ("A", "B"):
        if not found[role]:
            problem(f"no CLI version recorded in the pilot archive for role {role}")
    return {
        "A (claude)": sorted(found["A"]),
        "B (codex)": sorted(found["B"]),
        "C (opencode)": "not recorded in the OpenCode session record",
    }


def cli_versions_now() -> dict[str, str]:
    out = {}
    for name in ("claude", "codex", "opencode"):
        try:
            r = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=60)
            out[name] = (r.stdout or r.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            out[name] = f"unavailable: {e.__class__.__name__}"
    return out


def fixcheck_receipts(verify_tars: bool = True) -> dict[str, Any]:
    """Check every file named in each round's stage receipts against its current bytes."""
    out: dict[str, Any] = {}
    for r in (1, 2):
        rdir = FIX040 / f"round{r}"
        pub = REPO / "docs" / "validation" / "study4-fix040" / f"round{r}"
        for stage in ("primary", "retry", "flash"):
            rec_path = pub / "receipts" / f"{stage}.json"
            rec = json.loads(rec_path.read_text())
            n = 0
            for part, entries in rec["parts"].items():
                for rel, want in entries.items():
                    if part == "collect":
                        p = pub / "collect" / rel
                    elif part in ("retry", "flash"):
                        p = rdir / "assign" / part / rel
                    else:
                        p = rdir / part / rel
                    n += 1
                    if sha(p) != want:
                        problem(f"receipt mismatch: round {r} {stage} {part}/{rel}")
            for rel, want in rec["labels"].items():
                n += 1
                if sha(rdir / "labels" / rel) != want:
                    problem(f"receipt mismatch: round {r} {stage} labels/{rel}")
            out[f"round{r}/{stage}"] = {"receipt_sha256": sha(rec_path), "files_checked": n}
        tars = pub / "receipts" / "private_archive.sha256"
        lines = tars.read_text().splitlines()
        if verify_tars:
            for line in lines:
                want, name = line.split()
                if sha(FIX040 / "archive" / name) != want:
                    problem(f"archive tar mismatch: {name}")
        out[f"round{r}/private_archive"] = {
            "receipt_sha256": sha(tars),
            "tars_checked": len(lines) if verify_tars else "skipped",
        }
    return out


def checksums(sums: Path) -> dict[str, Any]:
    """Check every entry of a SHA256SUMS file against the current bytes of its target."""
    want = need(sums)
    if want is None:
        return {}
    listed, bad = {}, []
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        h, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        listed[name] = h
        if sha(sums.parent / name) != h:
            bad.append(name)
    for name in bad:
        problem(f"checksum mismatch: {label(sums.parent / name)}")
    if not listed:
        problem(f"empty checksum file: {label(sums)}")
    return {"sha256": want, "entries": len(listed), "mismatched": bad}


def git_blob(p: Path) -> str:
    data = p.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def pinned_baseline() -> dict[str, Any]:
    """The pinned checkout must equal its commit, blob for blob (its .venv aside)."""
    rec = json.loads(PINNED.joinpath("PINNED_COMMIT.json").read_text())
    listing = git("ls-tree", "-r", rec["commit"]).splitlines()
    tag = {line.split("\t", 1)[1]: line.split()[2] for line in listing}
    differ = sorted(
        f for f, blob in tag.items() if not (PINNED / f).is_file() or git_blob(PINNED / f) != blob
    )
    present = tree(PINNED, exclude=(".venv",))
    extra = sorted(set(present) - set(tag) - {"PINNED_COMMIT.json"})
    for f in differ:
        problem(f"pinned baseline differs from {rec['commit'][:8]}: {f}")
    for f in extra:
        problem(f"pinned baseline file not in {rec['commit'][:8]}: {f}")
    return {
        "record": rec,
        "record_sha256": sha(PINNED / "PINNED_COMMIT.json"),
        "files_compared": len(tag),
        "differ": differ,
        "extra": extra,
        "files": present,
        "not_compared": ".venv (environment cache, rebuilt from the pinned uv.lock)",
    }


def later_evidence() -> dict[str, Any]:
    """Fix-check evidence written after the decision-time tars."""
    return {
        "note": (
            "written after the decision-time tars; the tars are not substituted for it. "
            "round1/ and round2/ are the unpacked packages with their later addenda."
        ),
        "access_review_addenda": files(
            [FIX040 / f"round{r}" / "transcripts" / "ACCESS_REVIEW_RULINGS.md" for r in (1, 2)]
        ),
        "round1": tree(FIX040 / "round1"),
        "round2": tree(FIX040 / "round2"),
        "materials_checksums": {
            f"round{r}": checksums(FIX040 / f"round{r}" / "materials" / "SHA256SUMS")
            for r in (1, 2)
        },
        "post_decision_events": {
            "files": tree(FIX040 / "post_decision_events"),
            "checksums": checksums(FIX040 / "post_decision_events" / "SHA256SUMS"),
        },
        "launch_and_access_review_scripts": tree(FIX040 / "tools"),
        "pinned_baseline": pinned_baseline(),
        "review_reports": {
            "path": ".cache/validation (restricted working material, held by the custodian)",
            "fix040_reports": files(sorted(FIXCACHE.glob("*.md"))),
            "fix040_round2_reports": files(sorted((FIXCACHE / "round2").glob("*.md"))),
            "fix040_scripts": tree(FIXCACHE / "scripts"),
            "final_audit": tree(FIXCACHE / "final_audit"),
            "round2_harness_audits": files(
                [CACHE / f"sol_round2_harness_audit_r{i}.md" for i in (1, 2, 3)]
            ),
        },
    }


def build_manifest(verify_tars: bool = True) -> dict[str, Any]:
    PROBLEMS.clear()
    tag_commit = git("rev-parse", "v0.4.0^{commit}")
    import spacy

    roles = {}
    for r in ("A", "B", "C"):
        argv, env = launch.argv_for(r, Path("<session dir>"), "<registered prompt>")
        roles[r] = {
            "model": launch.MODELS[r],
            "argv": argv,
            "env": {k: v for k, v in env.items() if k not in ("HOME", "PATH", "USER", "TMPDIR")}
            | {"inherited": ["HOME", "PATH", "USER", "TMPDIR"]},
        }
    for p in KEY_FILES:
        need(p)
    dev_refs, dev_info = build.load_dev_exclusions(build.DEV_TEXTS)
    extra = build.read_exclusions(EXCLUSIONS)
    m: dict[str, Any] = {
        "study": "lexinspect Study 4: precision of metadiscourse and PHRASE detection",
        "stage": 1,
        "format": "study4-freeze/2",
        "status": "not registered until the external deposit is recorded in study4-freeze-deposit.json",
        "release": {
            "version": "0.4.0",
            "tag": "v0.4.0",
            "commit": tag_commit,
            "src_tree": git("rev-parse", "v0.4.0:src"),
            "working_tree_equals_tag": release_equality(),
        },
        "detector": {"files": tracked("src")},
        "environment": {
            "python": platform.python_version(),
            "spacy": spacy.__version__,
            "en_core_web_sm": model_record(),
            "tokenizer_customisation": "infix rules in src/lexinspect/_nlp.py (hashed under detector)",
            "uv.lock": need(REPO / "uv.lock"),
            "pyproject.toml": need(REPO / "pyproject.toml"),
        },
        "judgement_materials": {
            "guidelines": {
                "path": "docs/validation/study4-guidelines.md",
                "sha256": need(launch.GUIDELINES),
                "version": "3.2",
            },
            "inventory": {
                "path": "phrase_sense_inventory.md (private)",
                "sha256": need(launch.INVENTORY),
                "version": "2.1",
            },
            "prompt_template_sha256": launch.PROMPT_SHA256,
            "delivery_spec": files([launch.DELIVERY_SPEC]),
        },
        "labelling": {
            "roles": roles,
            "adjudicator": "opencode/deepseek-v4.1-flash-free, variant high (selected 2026-10-16)",
            "pilot_cli_versions": pilot_cli_versions(),
            "launch_record": files([REPO / "docs/validation/study4-pilot040/LAUNCH.md"]),
        },
        "code": tracked("scripts/validation/study4_precision"),
        "pilot_0_4_0": {
            "records": tracked("docs/validation/study4-pilot040"),
            "build": tree(V040),
            "private_archive": tree(PILOT040),
            "private_checksums": {
                n: checksums(PILOT040 / n / "SHA256SUMS") for n in ("selection/build", "probes")
            },
        },
        "history_0_3_2": {
            "development_build": tree(DEV, exclude=("raw",)),
            "pilot_2026_10_16": tree(PILOT032),
            "pilot_2026_10_16_session_records": tree(PRIVATE / "study4-pilot032-transcripts"),
            "pilot_2026_10_16_session_checksums": checksums(
                PRIVATE / "study4-pilot032-transcripts" / "SHA256SUMS"
            ),
            "simulation_key_frame": files([DEV032 / "key.jsonl", DEV032 / "frame.json"]),
            "simulation": tree(SIM032),
        },
        "evaluation_pool_cache": {
            "path": ".cache/validation/study4/raw",
            "files": tree(DEV / "raw"),
        },
        "simulation_0_4_0": {
            "bundle": tree(SIM040),
            "tail_table_tool": files([SCRATCH / "tools" / "tail_table.py"]),
        },
        "fix_check": {
            "records": tracked("docs/validation/study4-fix040"),
            "decision_time_packages": {"receipts_verified": fixcheck_receipts(verify_tars)},
            "later_evidence": later_evidence(),
        },
        "exclusions": {
            "development_manifest": dev_info,
            "additional_manifest": {
                "path": str(EXCLUSIONS.relative_to(REPO)),
                "sha256": need(EXCLUSIONS),
                "n_refs": len(extra),
            },
            "union_n_refs": len(extra | dev_refs),
            "folder": tracked("docs/validation/study4-exclusions"),
        },
        "evaluation": {
            "seed": EVAL_SEED,
            "seed_rule": EVAL_SEED_RULE,
            "preparation": [
                "set -e",
                "mkdir .cache/validation/study4_eval",
                "cp -Rp .cache/validation/study4/raw .cache/validation/study4_eval/raw",
            ],
            "pool_check": "every file of the copy equals evaluation_pool_cache before collection",
            "command": (
                "uv run --offline --no-sync python -I scripts/validation/study4_precision/build.py "
                f"--set evaluation --seed {EVAL_SEED} --out .cache/validation/study4_eval "
                "--raw-cache .cache/validation/study4_eval/raw "
                "--exclude-texts docs/validation/study4-exclusions/exclusions.jsonl"
            ),
        },
        "protocol": files(
            [
                REPO / "docs/validation/study4-preregistration.md",
                REPO / "docs/validation/study4-fix-protocol.md",
                REPO / "docs/validation/study4-fix-protocol-clarifications.md",
                REPO / "docs/validation/study4-fix-check.md",
                REPO / "docs/validation/study4-development-effects.md",
                REPO / "docs/validation/study4-development-effects.json",
                REPO / "docs/validation/study4-archive.md",
                ACCESS_LOG_STAGE1,
            ]
        ),
        "administrative_records": {
            "access_log": str(ACCESS_LOG.relative_to(REPO)),
            "note": (
                "append-only and versioned in git; not hashed here, so recording an access "
                "request leaves this manifest unchanged. Its Stage-1 state is the snapshot "
                "under protocol. Each inspection records the access-log version and hash."
            ),
        },
        "textfree_export": tracked("docs/validation/study4-textfree"),
        "stage1_review": tracked("docs/validation/study4-stage1-review"),
        "deposit": {
            "record": str(DEPOSIT.relative_to(REPO)),
            "note": "the external deposit's service, identifier and receipt are kept in the record file, outside this manifest",
        },
    }
    m["observed"] = {
        "built": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "built_from_commit": git("rev-parse", "HEAD"),
        "platform": platform.platform(),
        "cli_versions_now": cli_versions_now(),
    }
    return m


def differences(old: Any, new: Any, path: str = "") -> list[str]:
    """Paths at which two manifests differ, ignoring the top-level "observed" section."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for k in sorted(set(old) | set(new)):
            if path == "" and k == "observed":
                continue
            out += differences(old.get(k), new.get(k), f"{path}/{k}")
        return out
    return [] if old == new else [path or "/"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    m = build_manifest()
    if PROBLEMS:
        print("freeze manifest NOT built: required inputs failed", file=sys.stderr)
        for p in PROBLEMS:
            print("  " + p, file=sys.stderr)
        return 2
    if args.check:
        old = json.loads(OUT.read_text())
        for k in ("platform", "cli_versions_now"):
            if old.get("observed", {}).get(k) != m["observed"][k]:
                print(f"note: observed {k} changed since the build: {m['observed'][k]}")
        diff = differences(old, m)
        if diff:
            print("freeze manifest differs:")
            for d in diff[:50]:
                print("  " + d)
            if len(diff) > 50:
                print(f"  ... and {len(diff) - 50} more")
            return 1
        print("freeze manifest matches")
        return 0
    OUT.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
