"""Study 4 Stage 1: build the freeze manifest, docs/validation/study4-freeze.json.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/pilot040/freeze.py [--check]

It records, with SHA-256 throughout:

- the release: lexinspect 0.4.0, tag v0.4.0 and its commit, and whether the
  checkout's src/, pyproject.toml and uv.lock equal the tag;
- the detector: every tracked file under src/ and the tag's git tree id of src/;
- the environment: Python, spaCy, en_core_web_sm (version and the hash of its
  installed RECORD), the lock file and pyproject.toml;
- the guidelines, the sense inventory, the registered prompt template and the
  delivery spec;
- the labelling launcher, screen and collector, and the effective launch settings
  per role (launch.argv_for with placeholder paths);
- the analysis, sampling and simulation code;
- the 0.4.0 pilot (build files, selection record, results record, label and
  analysis files in the private archive);
- the 0.4.0 simulation (frozen sources, inventory, merged result when present)
  and the historical 0.3.2 run's result hashes;
- the exclusions (the canonical development manifest and the additional
  manifest, with identifier counts) and the evaluation seed and command;
- the protocol documents: the prereg, the fix protocol and clarifications, the
  fix-check write-up, the development effects report, the archive inventory, and
  every file in docs/validation/study4-fix040/, study4-pilot040/ and
  study4-exclusions/.

A missing optional input is recorded as null with a note, never silently
skipped. --check rebuilds the manifest in memory and exits 1 if it differs
from the file on disk (ignoring the "built" time).
"""

from __future__ import annotations

import argparse
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
PRIVATE = Path.home() / "lexinspect-private" / "study4-pilot040"
V040 = REPO / ".cache" / "validation" / "study4_v040"
SIM040 = REPO / ".cache" / "validation" / "study4_scratch" / "sim040"
SIM032 = REPO / ".cache" / "validation" / "study4_scratch" / "sim_final"
EVAL_SEED = 3195330621
EVAL_SEED_RULE = 'int(sha256("study4-v040-evaluation|20261016").hexdigest()[:8], 16)'
EXCLUSIONS = REPO / "docs" / "validation" / "study4-exclusions" / "exclusions.jsonl"


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def tracked(prefix: str) -> dict[str, str | None]:
    return {f: sha(REPO / f) for f in git("ls-files", prefix).splitlines()}


def files(paths: list[Path]) -> dict[str, str | None]:
    return {str(p.relative_to(REPO) if p.is_relative_to(REPO) else p): sha(p) for p in paths}


def model_record() -> dict[str, Any]:
    try:
        dist = md.distribution("en_core_web_sm")
    except md.PackageNotFoundError:
        return {"version": None, "note": "en_core_web_sm not installed"}
    rec = next((f for f in dist.files or [] if f.name == "RECORD"), None)
    return {
        "version": dist.version,
        "record_sha256": sha(Path(dist.locate_file(rec))) if rec else None,
    }


def build_manifest() -> dict[str, Any]:
    tag_commit = git("rev-parse", "v0.4.0^{commit}")
    same = (
        subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "diff",
                "--quiet",
                "v0.4.0",
                "HEAD",
                "--",
                "src",
                "pyproject.toml",
                "uv.lock",
            ]
        ).returncode
        == 0
    )
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
    dev_refs, dev_info = build.load_dev_exclusions(build.DEV_TEXTS)
    extra = build.read_exclusions(EXCLUSIONS)
    pilot_private = [
        PRIVATE / "labels" / n
        for n in (
            "A_batch.jsonl",
            "A_retry.jsonl",
            "A_merged.jsonl",
            "B_batch.jsonl",
            "needs_adjudication.txt",
            "adjudicator_adjudication.jsonl",
        )
    ] + [PRIVATE / "analysis" / "pilot.json", PRIVATE / "analysis" / "flash_diagnostics.json"]
    v040_files = [
        V040 / n
        for n in (
            "texts.jsonl",
            "hits.jsonl",
            "items.jsonl",
            "key.jsonl",
            "frame.json",
            "manifest.json",
            "orders.json",
            "population.json",
        )
    ]
    v040_files += sorted((V040 / "batches").rglob("*.json*"))
    sim_files = [
        SIM040 / n
        for n in (
            "frozen_sources.sha256",
            "inventory.json",
            "all.json",
            "final.json",
            "result_hashes.sha256",
            "environment.txt",
        )
    ]
    m: dict[str, Any] = {
        "study": "lexinspect Study 4: precision of metadiscourse and PHRASE detection",
        "stage": 1,
        "status": "draft: not registered until the external deposit receipt is recorded here",
        "built": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "checkout_commit": git("rev-parse", "HEAD"),
        "release": {
            "version": "0.4.0",
            "tag": "v0.4.0",
            "commit": tag_commit,
            "src_tree": git("rev-parse", "v0.4.0:src"),
            "checkout_src_pyproject_lock_equal_tag": same,
        },
        "detector": {"files": tracked("src")},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "spacy": spacy.__version__,
            "en_core_web_sm": model_record(),
            "tokenizer_customisation": "infix rules in src/lexinspect/_nlp.py (hashed under detector)",
            "uv.lock": sha(REPO / "uv.lock"),
            "pyproject.toml": sha(REPO / "pyproject.toml"),
        },
        "judgement_materials": {
            "guidelines": {
                "path": "docs/validation/study4-guidelines.md",
                "sha256": sha(launch.GUIDELINES),
                "version": "3.2",
            },
            "inventory": {
                "path": "phrase_sense_inventory.md (private)",
                "sha256": sha(launch.INVENTORY),
                "version": "2.1",
            },
            "prompt_template_sha256": launch.PROMPT_SHA256,
            "delivery_spec": files([launch.DELIVERY_SPEC]),
        },
        "labelling": {
            "code": files(
                sorted((S4 / "pilot040").glob("*.py")) + sorted((S4 / "pilot040").glob("*.sh"))
            ),
            "roles": roles,
            "adjudicator": "opencode/deepseek-v4.1-flash-free, variant high (selected 2026-10-16)",
            "launch_record": files([REPO / "docs/validation/study4-pilot040/LAUNCH.md"]),
        },
        "analysis_code": files(sorted(S4.glob("*.py"))),
        "pilot_0_4_0": {
            "records": files(sorted((REPO / "docs/validation/study4-pilot040").glob("*"))),
            "build": files(v040_files),
            "private_labels_and_analysis": files(pilot_private),
        },
        "simulation_0_4_0": files(sim_files),
        "simulation_0_3_2_historical": files(
            [SIM032 / "result_hashes.sha256", SIM032 / "inventory.json", SIM032 / "final.json"]
        ),
        "exclusions": {
            "development_manifest": dev_info,
            "additional_manifest": {
                "path": str(EXCLUSIONS.relative_to(REPO)),
                "sha256": sha(EXCLUSIONS),
                "n_refs": len(extra),
            },
            "union_n_refs": len(extra | dev_refs),
            "folder": files(sorted(p for p in EXCLUSIONS.parent.rglob("*") if p.is_file())),
        },
        "evaluation": {
            "seed": EVAL_SEED,
            "seed_rule": EVAL_SEED_RULE,
            "pool_policy": "byte copy of .cache/validation/study4/raw (2026-10-16 snapshot) into .cache/validation/study4_eval/raw; no --refresh",
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
            ]
        ),
        "fix_check_records": tracked("docs/validation/study4-fix040"),
        "deposit": {
            "service": None,
            "identifier": None,
            "receipt": None,
            "note": "filled after the external deposit",
        },
    }
    missing = sorted(k for sec in ("simulation_0_4_0",) for k, v in m[sec].items() if v is None)
    m["notes"] = {"missing_at_build": missing}
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    m = build_manifest()
    if args.check:
        old = json.loads(OUT.read_text())
        old.pop("built", None)
        new = dict(m)
        new.pop("built", None)
        if old != new:
            diff = sorted(k for k in new if old.get(k) != new[k])
            print("freeze manifest differs:", diff)
            return 1
        print("freeze manifest matches")
        return 0
    OUT.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}; missing: {m['notes']['missing_at_build']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
