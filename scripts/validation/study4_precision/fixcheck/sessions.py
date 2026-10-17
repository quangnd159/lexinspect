"""`delivery-spec`, `export-sessions`, `gather-labels`: neutral labelling sessions (audit r1 S2).

Preregistration "Batches and returned labels": every batch is labelled in a
fresh session pointed at a directory holding ONLY guidelines.md,
phrase_sense_inventory.md and the batch file items.jsonl; the output is
labels.jsonl in that directory; the prompt is the registered one.

`delivery-spec` writes the delivery specification, frozen before any label:
- the prompt template, extracted verbatim from the preregistration ("Prompt
  given to each model labeller, per batch"), its SHA-256 and the
  preregistration's SHA-256;
- the session materials with their SHA-256, which must equal the frozen pilot
  hashes (.cache/validation/study4_pilot/frozen_inputs.sha256); a missing file,
  a missing pilot hash or a mismatch stops it;
- the model route and settings per role (A, B, adjudicator), as registered;
- the maximum batch size (325) and the session file names.

`export-sessions` makes one neutral directory per batch of one stage (primary
A/B, retry, flash) under --session-root: a random-looking token name (SHA-256
of the spec hash, stage, role, batch and batch hash), holding exactly the
three files, copied byte for byte and hash-checked against the spec. The role,
stage, seed, manifests, key and the rendered prompt live OUTSIDE the session
directories, in --out: sessions_index.json, prompts/<token>.txt and
deliveries.template.jsonl. --session-root must not lie inside the round package
and its name and its parent's name must not contain any word that
verify.FORBIDDEN flags, or a role, stage or study name.

deliveries.jsonl (completed by the operator, one record per session):
  {"token", "delivered": true|false, "provider", "model", "settings",
   "session_id", "transcript", "transcript_sha256", "labels_sha256",
   "delivered_at", "access_review"}
A delivered session must have the spec's provider/model/settings for its role,
a kept transcript with matching hash, labels.jsonl with matching hash, a
session directory still holding only the three materials (unchanged) plus
labels.jsonl, and a non-empty access-review note (the transcript was read: the
session read only the listed files and wrote the labels by hand). A session
with delivered false is NEVER DELIVERED: its items are procedure gaps, not
non-votes.

`gather-labels` concatenates the delivered sessions' labels.jsonl bytes of one
stage and role in batch order into the label file analyse.py reads (first pass
<role>.pass1.jsonl, retry <role>.retry.jsonl, adjudicator.jsonl). accept
recomputes this concatenation (check_stage).
"""

from __future__ import annotations

import argparse
import re
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any

import analyse
import batches

from fixcheck import REPO
from fixcheck.common import (
    canonical_json,
    read_json,
    read_jsonl,
    refuse_existing,
    set_command,
    sha256_file,
    sha256_text,
    write_json,
    write_jsonl,
    write_step_manifest,
)

SPEC_KIND = "fixcheck-delivery-spec"
SPEC_VERSION = 1
PREREG = REPO / "docs" / "validation" / "study4-preregistration.md"
PILOT_HASHES = REPO / ".cache" / "validation" / "study4_pilot" / "frozen_inputs.sha256"
MATERIALS = {
    "guidelines.md": REPO / "docs" / "validation" / "study4-guidelines.md",
    "phrase_sense_inventory.md": REPO
    / ".cache"
    / "validation"
    / "study4"
    / "phrase_sense_inventory.md",
}
BATCH_FILE = "items.jsonl"
OUTPUT_FILE = "labels.jsonl"
SESSION_FILES = (*MATERIALS, BATCH_FILE)
# Registered routes (preregistration "Labellers"; pilot PILOT_PLAN.md / PILOT_LOG.md).
ROLES = {
    "A": {
        "provider": "anthropic (T3 delegate_task, Claude Code)",
        "model": "claude-sonnet-5-5",
        "settings": {"effort": "high"},
    },
    "B": {
        "provider": "openai (codex)",
        "model": "gpt-6.1-sol",
        "settings": {"reasoningEffort": "high"},
    },
    "adjudicator": {
        "provider": "opencode (free route)",
        "model": "opencode/deepseek-v4.1-flash-free",
        "settings": {"reasoning": "high"},
    },
}
STAGES = {
    "primary": ("A", "B"),
    "retry": ("A", "B"),
    "flash": ("adjudicator",),
}
# A visible path component must not name the study, the harness, a stage, a role, a
# family, a version, a round or a model (audit r2 B3); short tokens only when delimited.
NEUTRAL_FORBIDDEN = re.compile(
    r"study|fix|lexinspect|retry|flash|adjud|label|role|baseline|candidate|famil|"
    r"version|round|primar|stage|batch|session|check|pilot|precision|"
    r"claude|sonnet|anthropic|gpt|openai|codex|opencode|deepseek|"
    r"(^|[-_. ])(a|b|md|ph|sx|r[12]|v\d[\w.]*|0\.\d[\w.]*)([-_. ]|$)",
    re.IGNORECASE,
)
FRESH_SESSION_RULE = (
    "one fresh session per batch, no inherited repository or review context; transcript "
    "kept and reviewed (read only the listed files; labels by hand)"
)
DELIVERY_FIELDS = (
    "token",
    "delivered",
    "provider",
    "model",
    "settings",
    "session_id",
    "transcript",
    "transcript_sha256",
    "labels_sha256",
    "delivered_at",
    "access_review",
)


def prompt_template(prereg: Path = PREREG) -> str:
    """The registered per-batch prompt, verbatim (block-quote markers removed)."""
    lines = prereg.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, x in enumerate(lines) if "Prompt given to each model labeller" in x)
    except StopIteration:
        raise SystemExit(f"{prereg}: no registered prompt section") from None
    out: list[str] = []
    for x in lines[start + 1 :]:
        if x.startswith(">"):
            out.append(x[2:] if x.startswith("> ") else x[1:])
        elif out and x.strip():
            break
    text = "\n".join(out).strip() + "\n"
    if "⟨dir⟩" not in text or "⟨n⟩" not in text:
        raise SystemExit("registered prompt lacks the ⟨dir⟩ / ⟨n⟩ placeholders")
    return text


def render_prompt(template: str, session_dir: Path, n: int) -> str:
    return template.replace("⟨dir⟩", str(session_dir)).replace("⟨n⟩", str(n))


def pilot_hashes(path: Path = PILOT_HASHES) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, rel = line.split(None, 1)
            out[rel.strip()] = h
    return out


def build_spec(prereg: Path = PREREG, pilot: Path = PILOT_HASHES) -> dict[str, Any]:
    if not pilot.exists():
        raise SystemExit(f"frozen pilot hashes {pilot} missing")
    ph = pilot_hashes(pilot)
    mats = {}
    for name, src in MATERIALS.items():
        if not src.resolve().is_relative_to(REPO.resolve()):
            raise SystemExit(f"session material {src} is not in the repository")
        rel = str(src.resolve().relative_to(REPO.resolve()))
        if not src.exists():
            raise SystemExit(f"session material {src} missing")
        if rel not in ph:
            raise SystemExit(f"no frozen pilot hash for {rel}")
        h = sha256_file(src)
        if h != ph[rel]:
            raise SystemExit(
                f"{rel}: sha256 {h[:12]} differs from the frozen pilot hash {ph[rel][:12]}"
            )
        mats[name] = {"source": rel, "sha256": h}
    tpl = prompt_template(prereg)
    spec = {
        "kind": SPEC_KIND,
        "version": SPEC_VERSION,
        "prompt_template": tpl,
        "prompt_template_sha256": sha256_text(tpl),
        "prompt_placeholders": {"⟨dir⟩": "absolute session directory", "⟨n⟩": "items in the batch"},
        "prompt_source": {"path": str(prereg.relative_to(REPO)), "sha256": sha256_file(prereg)},
        "materials": mats,
        "pilot_hashes": {"path": str(pilot.relative_to(REPO)), "sha256": sha256_file(pilot)},
        "roles": ROLES,
        "max_batch_size": batches.MODEL_BATCH_SIZE,
        "session_files": list(SESSION_FILES),
        "output_file": OUTPUT_FILE,
        "fresh_session_rule": FRESH_SESSION_RULE,
    }
    spec["spec_sha256"] = sha256_text(canonical_json(spec))
    return spec


def check_spec(
    spec: dict[str, Any], prereg: Path | None = None, pilot: Path | None = None
) -> list[str]:
    """The spec is the REGISTERED delivery (audit r2 B3), not merely self-consistent.

    Its self-hash holds; its prompt is the preregistration's registered prompt, verbatim,
    and names that preregistration's SHA-256; its roles are exactly the registered routes
    and settings (ROLES, preregistration "Labellers", maintainer Addendum item 3); its
    materials are exactly guidelines.md and phrase_sense_inventory.md with the frozen
    pilot hashes, still present with those bytes; batch size, file names and the fresh-
    session rule are the registered ones."""
    p = []
    body = {k: v for k, v in spec.items() if k != "spec_sha256"}
    if spec.get("kind") != SPEC_KIND or spec.get("version") != SPEC_VERSION:
        p.append("not a delivery spec of this version")
    if sha256_text(canonical_json(body)) != spec.get("spec_sha256"):
        p.append("delivery spec content differs from its spec_sha256")
    if sha256_text(spec.get("prompt_template", "")) != spec.get("prompt_template_sha256"):
        p.append("prompt template differs from its hash")
    try:
        src = prereg or (REPO / spec["prompt_source"]["path"])
        if prompt_template(src) != spec["prompt_template"]:
            p.append("prompt template is not the registered prompt")
        if sha256_file(src) != spec["prompt_source"]["sha256"]:
            p.append("the spec names another preregistration version")
    except (KeyError, SystemExit, OSError) as e:
        p.append(f"registered prompt unreadable: {e}")
    if canonical_json(spec.get("roles")) != canonical_json(ROLES):
        p.append("roles are not the registered model routes and settings")
    if spec.get("max_batch_size") != batches.MODEL_BATCH_SIZE:
        p.append("max_batch_size is not the registered 325")
    if spec.get("session_files") != list(SESSION_FILES) or spec.get("output_file") != OUTPUT_FILE:
        p.append("session file names are not the registered ones")
    if spec.get("fresh_session_rule") != FRESH_SESSION_RULE:
        p.append("the fresh-session rule is not the registered one")
    try:
        pp = pilot or (REPO / spec["pilot_hashes"]["path"])
        ph = pilot_hashes(pp)
        if sha256_file(pp) != spec["pilot_hashes"]["sha256"]:
            p.append("the frozen pilot hash file changed")
    except (KeyError, OSError) as e:
        return [*p, f"frozen pilot hashes unreadable: {e}"]
    want = {k: str(v.resolve().relative_to(REPO.resolve())) for k, v in MATERIALS.items()}
    for name, m in spec.get("materials", {}).items():
        src = REPO / m["source"]
        if want.get(name) != m["source"]:
            p.append(f"{name}: not the registered material file")
        if ph.get(m["source"]) != m["sha256"]:
            p.append(f"{name}: spec hash is not the frozen pilot hash")
        if not src.exists() or sha256_file(src) != m["sha256"]:
            p.append(f"{name}: {src} missing or changed")
    if set(spec.get("materials", {})) != set(MATERIALS):
        p.append("materials are not exactly guidelines.md and phrase_sense_inventory.md")
    return p


def stage_batches(stage: str, stage_dir: Path) -> list[dict[str, Any]]:
    """[{role, batch, file, sha256, ids}] of one stage, from batches.py's manifests."""
    prefix = {"primary": "batch", "retry": "retry", "flash": "batch"}[stage]
    out = []
    for role in STAGES[stage]:
        man_path = stage_dir / "batches" / role / prefix / f"{prefix}_manifest.json"
        if not man_path.exists():
            continue
        man = read_json(man_path)
        if man["batch_size"] > batches.MODEL_BATCH_SIZE:
            raise SystemExit(f"{man_path}: batch size {man['batch_size']} exceeds 325")
        for b in man["batches"]:
            f = man_path.parent / b["file"]
            if sha256_file(f) != b["sha256"]:
                raise SystemExit(f"{f}: differs from its batch manifest")
            out.append(
                {
                    "role": role,
                    "batch": b["batch"],
                    "file": f,
                    "sha256": b["sha256"],
                    "ids": b["ids"],
                }
            )
    return out


def token_of(spec_sha: str, stage: str, role: str, batch: int, batch_sha: str) -> str:
    return "s" + sha256_text(f"{spec_sha}|{stage}|{role}|{batch}|{batch_sha}")[:16]


def expected_sessions(spec_sha: str, stage: str, stage_dir: Path) -> dict[str, dict[str, Any]]:
    """token -> the session a stage must deliver, rebuilt from its batch manifests."""
    return {
        token_of(spec_sha, stage, b["role"], b["batch"], b["sha256"]): {
            "role": b["role"],
            "batch": b["batch"],
            "batch_sha256": b["sha256"],
            "ids": list(b["ids"]),
            "n": len(b["ids"]),
        }
        for b in stage_batches(stage, stage_dir)
    }


def path_problems(path: Path, what: str = "session path") -> list[str]:
    """Every component of the resolved visible path must be neutral (audit r2 B3)."""
    p = []
    for part in Path(path).resolve().parts:
        if NEUTRAL_FORBIDDEN.search(part) or _forbidden(part):
            p.append(f"{what} component {part!r} is not neutral")
    return p


def check_session_root(root: Path, package: Path | None) -> list[str]:
    p = []
    r = Path(root).resolve()
    if package is not None and r.is_relative_to(Path(package).resolve()):
        p.append("session root lies inside the round package")
    if r.is_relative_to(REPO.resolve()):
        p.append("session root lies inside the repository")
    return p + path_problems(r, "session root path")


def fresh_root() -> Path:
    """A fresh, neutral session root: a random name directly under the system temp dir."""
    base = Path(tempfile.gettempdir()).resolve()
    for _ in range(100):
        d = base / secrets.token_hex(6)
        if not d.exists() and not path_problems(d):
            return d
    raise SystemExit(f"no neutral random directory under {base}: set TMPDIR to a neutral path")


def _forbidden(s: str) -> bool:
    from fixcheck.verify import FORBIDDEN

    return bool(FORBIDDEN.search(s))


def receipt_for_export(
    package: Path, stage: str, receipt: Path | None, spec_path: Path
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    """(stage_receipt record, production, problems) for an export (audit r2 B5).

    The package's freeze record decides production. The receipt must hold exactly the
    package's current bytes for the stage (package.stage_receipt) and name this spec; in
    production it must also be committed and on the registered receipt ref
    (freeze.archive_receipt), i.e. archived before any session is delivered."""
    from fixcheck import freeze as FZ
    from fixcheck import package as PK

    P = PK.resolve(package)
    fr_path = P["collect"] / "freeze_record.json"
    fr = read_json(fr_path) if fr_path.exists() else {}
    production = fr.get("production_eligible") is True
    p: list[str] = []
    bspec = (fr.get("bound") or {}).get("delivery_spec") or {}
    if production and (
        Path(bspec.get("path") or "/nonexistent").resolve() != Path(spec_path).resolve()
        or bspec.get("sha256") != sha256_file(spec_path)
    ):
        p.append("--spec is not the delivery spec bound in the freeze record")
    if receipt is None:
        return None, production, p + ["no stage receipt (--receipt; fixcheck stage-receipt)"]
    receipt = Path(receipt).resolve()
    if any(receipt.is_relative_to(P[k]) for k in PK.PARTS):
        p.append("the stage receipt lies inside a package part")
    rec = read_json(receipt)
    want = PK.stage_receipt(P, stage, spec_path)
    for k in ("kind", "stage", "freeze_record_sha256", "delivery_spec_sha256", "parts", "labels"):
        if canonical_json(rec.get(k)) != canonical_json(want.get(k)):
            p.append(f"the stage receipt's {k} is not the package's current {stage} state")
    archive = None
    if production:
        archive = FZ.archive_receipt([receipt], REPO, FZ.REGISTERED_RECEIPT_REF)
        p += [f"stage receipt archive: {x}" for x in archive["problems"]]
    out = {"path": str(receipt), "sha256": sha256_file(receipt), "archive": archive}
    return out, production, p


def export(
    spec_path: Path,
    stage: str,
    stage_dir: Path,
    session_root: Path,
    out: Path,
    package: Path | None,
    production: bool = False,
    receipt: Path | None = None,
) -> dict[str, Any]:
    spec = read_json(spec_path)
    root = Path(session_root).resolve()
    probs = check_spec(spec) + check_session_root(root, package)
    stage_receipt = None
    if package is not None:
        stage_receipt, pkg_production, rp = receipt_for_export(package, stage, receipt, spec_path)
        production = production or pkg_production
        if pkg_production or receipt is not None:
            probs += rp
    if production:
        if root.exists():
            probs.append("production session roots are fresh: the directory already exists")
        if root.parent != Path(tempfile.gettempdir()).resolve():
            probs.append("production session roots lie directly under the system temp dir")
    if probs:
        raise SystemExit("export-sessions refused:\n" + "\n".join(probs))
    root.mkdir(parents=True, exist_ok=not production)
    rows = stage_batches(stage, stage_dir)
    index = []
    templates = []
    for b in rows:
        tok = token_of(spec["spec_sha256"], stage, b["role"], b["batch"], b["sha256"])
        d = root / tok
        if d.exists():
            raise SystemExit(f"{d} exists")
        d.mkdir(parents=True)
        shutil.copyfile(b["file"], d / BATCH_FILE)
        for name, m in spec["materials"].items():
            shutil.copyfile(REPO / m["source"], d / name)
            if sha256_file(d / name) != m["sha256"]:
                raise SystemExit(f"{d / name}: copy differs from the frozen hash")
        if sorted(x.name for x in d.iterdir()) != sorted(SESSION_FILES):
            raise AssertionError("session directory holds other files")
        prompt = render_prompt(spec["prompt_template"], d, len(b["ids"]))
        (out / "prompts").mkdir(parents=True, exist_ok=True)
        (out / "prompts" / f"{tok}.txt").write_text(prompt, encoding="utf-8")
        index.append(
            {
                "token": tok,
                "dir": str(d),
                "stage": stage,
                "role": b["role"],
                "batch": b["batch"],
                "batch_file": str(b["file"]),
                "batch_sha256": b["sha256"],
                "n": len(b["ids"]),
                "ids": b["ids"],
                "prompt_sha256": sha256_text(prompt),
                "materials_sha256": {k: m["sha256"] for k, m in spec["materials"].items()},
                "route": spec["roles"][b["role"]],
            }
        )
        templates.append(
            dict.fromkeys(DELIVERY_FIELDS) | {"token": tok, **spec["roles"][b["role"]]}
        )
    rec = {
        "stage": stage,
        "spec": str(spec_path),
        "spec_sha256": spec["spec_sha256"],
        "session_root": str(root),
        "production_fresh_root": production,
        "stage_receipt": stage_receipt,
        "sessions": index,
    }
    write_json(out / "sessions_index.json", rec)
    write_jsonl(out / "deliveries.template.jsonl", templates)
    return rec


def _regular_tree(d: Path) -> list[str]:
    """A session directory and its files are real files and directories, not symlinks."""
    p = []
    if d.is_symlink():
        p.append(f"{d.name} is a symlink")
    for x in d.iterdir() if d.exists() else []:
        if x.is_symlink() or not x.is_file():
            p.append(f"{d.name}/{x.name} is not a regular file")
    return p


def archive_delivered(index: dict[str, Any], stage_out: Path) -> list[str]:
    """Copy every delivered session directory into <stage_out>/delivered/<token>/ (byte for
    byte, regular files only), so the package keeps what each session saw and wrote even
    after the temporary session root is gone."""
    p = []
    for s in index["sessions"]:
        src = Path(s["dir"])
        if not (src / OUTPUT_FILE).exists():
            continue
        p += _regular_tree(src)
        dst = stage_out / "delivered" / s["token"]
        dst.mkdir(parents=True, exist_ok=True)
        for x in sorted(src.iterdir()):
            if x.is_file() and not x.is_symlink():
                shutil.copyfile(x, dst / x.name)
    return p


def check_deliveries(
    index: dict[str, Any],
    deliveries: list[dict[str, Any]],
    spec: dict[str, Any],
    expected: dict[str, dict[str, Any]] | None = None,
    stage_out: Path | None = None,
) -> dict[str, Any]:
    """Problems, delivered and never-delivered ids per role, labels bytes per session.

    With `expected` (rebuilt from the authenticated batch manifests, audit r2 B3) the
    index must hold exactly the expected sessions, every expected session that is not
    validly delivered is never-delivered, and batch bytes are compared with the
    expected hashes, not the index's. With `stage_out` the archived delivered copy
    and the rendered prompt are checked too."""
    problems: list[str] = []
    by_tok: dict[Any, dict[str, Any]] = {}
    for d in deliveries:
        if d.get("token") in by_tok:
            problems.append(f"session {d.get('token')}: more than one delivery record")
        by_tok[d.get("token")] = d
    sessions = {s["token"]: s for s in index["sessions"]}
    if expected is not None:
        for tok, e in expected.items():
            s = sessions.get(tok)
            if s is None:
                problems.append(f"expected session {tok} ({e['role']} batch {e['batch']}) missing")
                continue
            if any(s.get(k) != e[k] for k in ("role", "batch", "batch_sha256", "ids", "n")):
                problems.append(f"session {tok}: not the prescribed batch")
        extra_idx = sorted(set(sessions) - set(expected))
        if extra_idx:
            problems.append(f"sessions not prescribed by the batch manifests: {extra_idx[:5]}")
    extra = set(by_tok) - set(sessions)
    if extra:
        problems.append(f"delivery records for unknown sessions {sorted(map(str, extra))[:5]}")
    delivered: dict[str, list[str]] = {}
    never: dict[str, list[str]] = {}
    labels_of: dict[str, bytes] = {}
    want_all = (
        expected
        if expected is not None
        else {
            t: {k: s[k] for k in ("role", "batch", "batch_sha256", "ids", "n")}
            for t, s in sessions.items()
        }
    )
    for tok, e in sorted(want_all.items()):
        role, d, s = e["role"], by_tok.get(tok), sessions.get(tok)
        delivered.setdefault(role, [])
        never.setdefault(role, [])
        if s is None or d is None or d.get("delivered") is not True:
            never[role] += e["ids"]
            if s is not None and d is None:
                problems.append(f"session {tok}: no delivery record")
            continue
        live = Path(s["dir"])
        arch = stage_out / "delivered" / tok if stage_out is not None else None
        sd = arch if arch is not None and arch.exists() else live
        if stage_out is not None and (arch is None or not arch.exists()):
            problems.append(f"session {tok}: no archived delivered copy (gather-labels)")
        if live.exists() and arch is not None and arch.exists():
            for x in sorted(set(SESSION_FILES) | {OUTPUT_FILE}):
                if (live / x).exists() and (live / x).read_bytes() != (arch / x).read_bytes():
                    problems.append(f"session {tok}: live {x} differs from the archived copy")
        problems += [f"session {tok}: {x}" for x in path_problems(live)]
        problems += [f"session {tok}: {x}" for x in _regular_tree(sd)]
        if not live.resolve().is_relative_to(Path(index["session_root"]).resolve()):
            problems.append(f"session {tok}: directory lies outside the session root")
        if live.exists() and live.resolve() != live:
            problems.append(f"session {tok}: the session path is not its resolved path")
        want_route = spec["roles"][role]
        for k in ("provider", "model", "settings"):
            if d.get(k) != want_route[k]:
                problems.append(
                    f"session {tok}: {k} {d.get(k)!r} is not the spec's {want_route[k]!r}"
                )
        if not str(d.get("access_review") or "").strip():
            problems.append(f"session {tok}: no access-review note")
        if not d.get("session_id"):
            problems.append(f"session {tok}: no session/transcript id")
        tr = Path(d["transcript"]) if d.get("transcript") else None
        if tr is None or not tr.exists() or sha256_file(tr) != d.get("transcript_sha256"):
            problems.append(f"session {tok}: transcript missing or differs from its hash")
        names = sorted(x.name for x in sd.iterdir()) if sd.exists() else []
        if names != sorted([*SESSION_FILES, OUTPUT_FILE]):
            problems.append(f"session {tok}: directory holds {names}")
        for name, m in spec["materials"].items():
            if not (sd / name).exists() or sha256_file(sd / name) != m["sha256"]:
                problems.append(f"session {tok}: {name} is not the spec's material")
        if not (sd / BATCH_FILE).exists() or sha256_file(sd / BATCH_FILE) != e["batch_sha256"]:
            problems.append(f"session {tok}: batch file is not the prescribed batch")
        if stage_out is not None:
            pf = stage_out / "prompts" / f"{tok}.txt"
            want_prompt = render_prompt(spec["prompt_template"], live, e["n"])
            if not pf.exists() or pf.read_text(encoding="utf-8") != want_prompt:
                problems.append(f"session {tok}: prompt is not the registered prompt rendered")
            elif sha256_text(want_prompt) != s.get("prompt_sha256"):
                problems.append(f"session {tok}: prompt hash differs from the index")
        lab = sd / OUTPUT_FILE
        if not lab.exists() or sha256_file(lab) != d.get("labels_sha256"):
            problems.append(f"session {tok}: labels.jsonl missing or differs from its hash")
            never[role] += e["ids"]
            continue
        labels_of[tok] = lab.read_bytes()
        delivered[role] += e["ids"]
    return {
        "problems": problems,
        "delivered": delivered,
        "never_delivered": never,
        "labels": labels_of,
    }


def session_identities(stage_outs: list[Path]) -> dict[str, Any]:
    """Every delivered session's provider id and transcript, across a round's stages: each
    must be unique (one fresh session per batch; audit r2 B3)."""
    ids, trs, paths = [], [], []
    for so in stage_outs:
        f = so / "deliveries.jsonl"
        for d in read_jsonl(f) if f.exists() else []:
            if d.get("delivered") is True:
                ids.append(str(d.get("session_id")))
                trs.append(str(d.get("transcript_sha256")))
                paths.append(str(Path(d["transcript"]).resolve()) if d.get("transcript") else "")
    problems = []
    for name, vals in (("session id", ids), ("transcript", trs), ("transcript path", paths)):
        dup = sorted({v for v in vals if vals.count(v) > 1})
        if dup:
            problems.append(f"{len(dup)} {name}s are used by more than one delivery")
    return {
        "problems": problems,
        "session_ids_sha256": sorted(sha256_text(i) for i in set(ids)),
        "transcripts_sha256": sorted(set(trs)),
    }


def gathered(index: dict[str, Any], labels_of: dict[str, bytes], role: str) -> bytes:
    """The delivered sessions' labels of one role, concatenated in batch order."""
    parts = []
    for s in sorted((s for s in index["sessions"] if s["role"] == role), key=lambda s: s["batch"]):
        if s["token"] in labels_of:
            b = labels_of[s["token"]]
            parts.append(b if b.endswith(b"\n") or not b else b + b"\n")
    return b"".join(parts)


def check_stage(
    stage_out: Path,
    label_file: Path,
    role: str,
    stage: str | None = None,
    stage_dir: Path | None = None,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute a stage's gathered label file for one role and compare its bytes.

    With stage, stage_dir and the BOUND spec (package checks), the expected sessions are
    rebuilt from the stage's batch manifests and the index must have been exported under
    exactly that spec."""
    if not (stage_out / "sessions_index.json").exists():
        never = {}
        if stage is not None and stage_dir is not None and spec is not None:
            for e in expected_sessions(spec["spec_sha256"], stage, stage_dir).values():
                never.setdefault(e["role"], []).extend(e["ids"])
        return {
            "problems": [
                f"{stage_out / 'sessions_index.json'} missing: sessions were not exported"
            ],
            "delivered": {},
            "never_delivered": never,
            "spec_sha256": None,
        }
    index = read_json(stage_out / "sessions_index.json")
    problems = []
    if spec is None:
        spec = read_json(Path(index["spec"]))
        problems += check_spec(spec)
    expected = None
    if stage is not None and stage_dir is not None:
        expected = {
            t: e
            for t, e in expected_sessions(spec["spec_sha256"], stage, stage_dir).items()
            if e["role"] == role or stage == "flash"
        }
        index = dict(
            index, sessions=[s for s in index["sessions"] if s["role"] == role or stage == "flash"]
        )
    deliveries = (
        read_jsonl(stage_out / "deliveries.jsonl")
        if (stage_out / "deliveries.jsonl").exists()
        else []
    )
    toks = {s["token"] for s in index["sessions"]} | set(expected or {})
    res = check_deliveries(
        index,
        [d for d in deliveries if d.get("token") in toks],
        spec,
        expected,
        stage_out if expected is not None else None,
    )
    res["problems"] = problems + res["problems"]
    if not (stage_out / "deliveries.jsonl").exists():
        res["problems"].append(f"{stage_out / 'deliveries.jsonl'} missing")
    if spec["spec_sha256"] != index["spec_sha256"]:
        res["problems"].append("sessions were exported under another delivery spec")
    res["problems"] += path_problems(Path(index["session_root"]), "session root path")
    want = gathered(index, res["labels"], role)
    if not label_file.exists() or label_file.read_bytes() != want:
        res["problems"].append(
            f"{label_file.name} is not the concatenation of the delivered sessions"
        )
    res["spec_sha256"] = spec["spec_sha256"]
    res.pop("labels")
    return res


# --- CLI ---------------------------------------------------------------------------


def main_spec(argv: list[str]) -> int:
    set_command("delivery-spec", argv)
    ap = argparse.ArgumentParser(prog="fixcheck delivery-spec")
    ap.add_argument("--out", type=Path, required=True, help="delivery_spec.json path")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    refuse_existing(args.out, args.overwrite)
    spec = build_spec()
    write_json(args.out, spec)
    print(f"delivery spec {spec['spec_sha256'][:16]} -> {args.out}")
    return 0


def main_export(argv: list[str]) -> int:
    set_command("export-sessions", argv)
    ap = argparse.ArgumentParser(prog="fixcheck export-sessions")
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--stage", choices=sorted(STAGES), required=True)
    ap.add_argument(
        "--stage-dir", type=Path, required=True, help="assign dir, retry dir or flash dir"
    )
    root = ap.add_mutually_exclusive_group(required=True)
    root.add_argument("--session-root", type=Path, help="neutral parent of the session dirs")
    root.add_argument(
        "--fresh-session-root",
        action="store_true",
        help="a fresh random directory directly under the system temp dir (production)",
    )
    ap.add_argument("--package", type=Path, required=True, help="round package dir or package.json")
    ap.add_argument("--receipt", type=Path, help="this stage's receipt (fixcheck stage-receipt)")
    ap.add_argument("--out", type=Path, required=True, help="index dir (outside the sessions)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    out = args.out.resolve()
    refuse_existing(out / "sessions_index.json", args.overwrite)
    session_root = fresh_root() if args.fresh_session_root else args.session_root
    if out.is_relative_to(Path(session_root).resolve()):
        raise SystemExit("--out must lie outside --session-root")
    rec = export(
        args.spec.resolve(),
        args.stage,
        args.stage_dir.resolve(),
        session_root,
        out,
        args.package,
        production=bool(args.fresh_session_root),
        receipt=args.receipt,
    )
    write_step_manifest(
        out,
        "export_sessions",
        [
            out / "sessions_index.json",
            out / "deliveries.template.jsonl",
            *sorted((out / "prompts").glob("*.txt")),
        ],
    )
    if args.fresh_session_root:
        print(f"fresh session root: {rec['session_root']}")
    print(f"{len(rec['sessions'])} sessions under {rec['session_root']}")
    return 0


def main_stage_receipt(argv: list[str]) -> int:
    """`stage-receipt`: write one stage's pre-delivery receipt (hashes only)."""
    set_command("stage-receipt", argv)
    from fixcheck import package as PK

    ap = argparse.ArgumentParser(prog="fixcheck stage-receipt")
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--stage", choices=PK.STAGES, required=True)
    ap.add_argument("--out", type=Path, required=True, help="receipt JSON (outside every part)")
    args = ap.parse_args(argv)
    P = PK.resolve(args.package)
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"{out} exists; a stage receipt is never overwritten")
    if any(out.is_relative_to(P[k]) for k in PK.PARTS):
        raise SystemExit("the stage receipt must lie outside every package part")
    _, cinfo = PK.check_collect(P)
    spec, spec_path, sp = PK.bound_spec(cinfo)
    if spec_path is None:
        raise SystemExit(f"no bound delivery spec: {sp}")
    rec = PK.stage_receipt(P, args.stage, spec_path)
    write_json(out, rec)
    print(f"stage receipt {args.stage} {sha256_file(out)[:16]} -> {out}")
    return 0


def main_gather(argv: list[str]) -> int:
    set_command("gather-labels", argv)
    ap = argparse.ArgumentParser(prog="fixcheck gather-labels")
    ap.add_argument("--stage-out", type=Path, required=True, help="export-sessions --out dir")
    ap.add_argument("--role", required=True)
    ap.add_argument("--out", type=Path, required=True, help="label file to write")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    refuse_existing(args.out, args.overwrite)
    index = read_json(args.stage_out / "sessions_index.json")
    spec = read_json(Path(index["spec"]))
    # keep what each delivered session saw and wrote, in the package (audit r2 B3)
    arch = archive_delivered(index, args.stage_out.resolve())
    if arch:
        raise SystemExit("gather-labels refused:\n" + "\n".join(arch))
    res = check_deliveries(index, read_jsonl(args.stage_out / "deliveries.jsonl"), spec)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(gathered(index, res["labels"], args.role))
    log = {k: v for k, v in res.items() if k != "labels"}
    write_json(args.out.with_suffix(".delivery_check.json"), log)
    print(
        f"{args.role}: delivered {len(res['delivered'].get(args.role, []))}, never delivered "
        f"{len(res['never_delivered'].get(args.role, []))}, problems {len(res['problems'])}"
    )
    return 0 if not res["problems"] else 1


__all__ = ["analyse", "build_spec", "check_stage", "export"]
