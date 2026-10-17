"""Study 4: precision of metadiscourse and PHRASE detection from independent labels.

    uv run python scripts/validation/study4_precision/analyse.py \\
        --labels A=labels_a.jsonl B=labels_b.jsonl \\
        [--adjudicator C=labels_c.jsonl] [--maintainer maintainer.jsonl] \\
        [--frame frame.json] [--retry-manifest DIR] [--validate-only] \\
        [--disagreements IDS] [--json out.json] [--md out.md]

    # after the single registered retry, merge the re-requested labels:
    uv run python scripts/validation/study4_precision/analyse.py \\
        --merge-retry labels_a.jsonl retry_a.jsonl --manifest DIR/retry_A.jsonl \\
        --merged-out labels_a.merged.jsonl

    # the maintainer's validated first pass (after its single retry, if any):
    uv run python scripts/validation/study4_precision/analyse.py \\
        --validate-pass1 maintainer_RAW.jsonl \\
        [--pass1-retry maintainer_retry_RAW.jsonl --manifest DIR/retry_maintainer.jsonl] \\
        --validated-out maintainer_pass1_validated.jsonl \\
        --validation-log maintainer_pass1_validation.json

Statistical scope
-----------------
Precision refers to the finite population of detector hits on the frozen
texts. Intervals quantify item-sampling uncertainty conditional on these texts;
they exclude text-selection uncertainty and reference-label error.
Estimators and intervals are specified in estimators.py (its docstring is part
of this specification).

Inputs and checks
-----------------
- `key.jsonl`, `items.jsonl` (claimed category / PHRASE entry and
  `other_senses_in_list`) and the frame (`frame.json`: N_h and register counts
  per sub-stratum, from the full hit population; default next to the key).
  Without a frame, union-of-sub-strata domains are still exact, but register
  domains are flagged as estimated.
- The design is validated before anything else (`validate_design`): unique
  key, item and order ids; key and items describe the same items, modules,
  categories and expressions; N_sub and n_sub constant within a sub-stratum,
  0 < n_sub <= N_sub and n_sub = number of key rows; frame and key agree;
  maintainer metadata (`in_maintainer_sample`, `m_sub`) consistent; orders
  cover exactly the right ids. Any problem stops the analysis.
- Label files are validated as a whole (`validate_lines`) against the
  "Your output" section of the guidelines (version 3). Each record needs all
  of `id`, `label`, `alt_category` and `note` (null allowed); other keys
  (batch, position, timestamps) are metadata and ignored. A record is rejected if: a key is missing; a
  field has the wrong type (label string; alt_category, note string or null);
  the label is not one of the module's labels; the note exceeds 25
  whitespace-separated words; alt_category is non-null with a label other
  than WRONG_CATEGORY, WRONG_SENSE_LISTED or WRONG_SENSE_UNLISTED, or null or
  blank with one of them; EXTERNAL_CONNECTIVE is used on a claimed category
  other than transitions; WRONG_CATEGORY's alt_category is not exactly one of
  the ten keys (no stripping: " evidentials" is rejected) or equals the claim;
  WRONG_SENSE_LISTED's alt_category is not the `expression` of one of the
  item's `other_senses_in_list` (compared by `norm_sense`: case-folding,
  whitespace collapsing, straightened quotes); WRONG_SENSE_UNLISTED's gloss is
  not in capitals (alt != alt.upper()), is not 1-6 words, or names a listed
  sense or the claimed entry; UNSURE's note does not match
  `^\\s*([^:]+):\\s*\\S` or the part before the colon, split on `\\s+or\\s+`,
  does not give at least two distinct readings, each a label of the module
  (or, for metadiscourse, one of the ten category keys). Unknown and
  unassigned ids are reported and ignored. Duplicates: records of one id are
  equal when (norm_sense(label), norm_sense(alt_category) or null) agree;
  notes are ignored. An equal group of valid records collapses to its first
  record (whose note is kept); an unequal group is rejected as
  conflicting_duplicate and an equal group with an invalid record as
  invalid_duplicate, whatever the order of the lines. Expected ids without a
  valid label are "missing". The retry manifest is sorted by id;
  `--merge-retry` replaces every record of a manifest id.

Outcomes
--------
STRICT = CORRECT (primary). Metadiscourse LENIENT = CORRECT|WRONG_CATEGORY;
CONNECTIVE = CORRECT|WRONG_CATEGORY|EXTERNAL_CONNECTIVE (claimed transitions
only). PHRASE LIST_LENIENT = CORRECT|WRONG_SENSE_LISTED; PHRASAL =
CORRECT|WRONG_SENSE_LISTED|WRONG_SENSE_UNLISTED. UNSURE, missing and invalid
labels are non-votes.

Reference rule (per outcome)
----------------------------
1. Primaries A and B definite and equal -> that value. 2. Else the
adjudicator's definite value. 3. Otherwise unresolved. Maintainer labels never
enter the reference. The adjudicator is asked about every item on which the
primaries split under any reported outcome or either is UNSURE, missing or
invalid.

Domains reported
----------------
Every predefined domain, including empty ones: module ALL; metadiscourse by
the ten categories, both dimensions and the three registers; PHRASE by K1-K5,
multi-sense flag and register; CONNECTIVE for claimed transitions only.
CONFIRMATORY: STRICT precision for module ALL, each category (metadiscourse)
and each K-band (PHRASE). Everything else (other outcomes, dimensions,
multi-sense flag, registers, batches) is secondary or exploratory.

Results fixed in advance (no data-dependent selection)
------------------------------------------------------
The model reference uses labellers A and B and the adjudicator only: maintainer
labels never resolve a reference item, for any outcome. For every domain and
outcome (estimators.py specifies each):
- PRIMARY: the model-reference estimate over all sampled items with exact,
  pointwise, finite-population 95% limits obtained from a joint stratified
  tail bound (`ci95_exact`). They assume that, given the resolved counts, the
  resolved items are uniform random subsets of their cells, independently
  across sub-strata; cells without resolved items stay unknown. The point
  estimate `p` is reported only when every cell with population has a resolved
  item (`p_scope` = "domain"); otherwise `p` is null and `p_represented` (scope
  "represented_cells_only") is shown with that label.
- CO-PRIMARY: the exact pointwise 95% resolution region (`region95_exact`),
  which needs no assumption about unresolved items.
- SECONDARY: the Korn-Graubard modified Wilson interval (`ci95_approx`), the
  only approximate interval; and, as a separate analysis, the maintainer-only
  estimates (the maintainer sample is a second-phase SRS within each
  sub-stratum, so the composite is a stratified SRS, weights N_h / m_h; a
  sub-stratum audited in full, m_h = n_h, is simply the phase-one sample),
  with exact limits under their own assumptions; category-level results are
  exploratory.
Every limit is a separate pointwise 95% statement; nothing is claimed
simultaneously across domains, constructions or modules.

Maintainer labels: two blind passes
-----------------------------------
The maintainer labels the audit sample blind (first pass), then relabels, still
blind and before any unblinding, exactly the items they marked UNSURE (second
pass; `--maintainer-pass2`, ids from `second_pass_ids`, the page's second-pass
mode). The final label is the second-pass label for those items and the
first-pass label otherwise; both are recorded (`pass`, `pass1_label`,
`pass1_note`) and the pass counts are reported.

The validated first pass (`--validate-pass1`, `validated_pass1`). The raw
first-pass export, merged with its single retry export by `merge_retry` when
there is one (the retry manifest must equal the raw file's own retry list), is
validated as above. Only the validator-accepted records are kept, one per id,
sorted by id, each serialised as `json.dumps(record, ensure_ascii=False,
sort_keys=True)` (all of its keys kept): this text is the "validated form".
Rejected and missing ids become non-votes and are never relabelled by hand.
The JSON log records the rejected lines and non-vote ids with reasons, the
collapsed duplicates, the merge notes, the second-pass ids, the SHA-256 of
every input (raw, retry, manifest, key, items, maintainer sample) and of the
output, and the SHA-256 of this file. The same validated file assigns the
second pass (human_page.py --second-pass) and is passed as --maintainer; its
SHA-256 is the pass-1 stamp.

Registered mode (the default). When the analysis is run, second-pass ids are
written, or --maintainer-pass2 is given, --maintainer must be in validated
form, and every accepted second-pass record must carry `pass1_sha256` equal to
the SHA-256 of the --maintainer file. Every `pass1_sha256` value in the
second-pass file must be a 64-character lowercase hexadecimal string, checked
before any comparison. `--nonregistered-legacy` (synthetic or legacy inputs
only) accepts an unvalidated --maintainer and unstamped or partly stamped
second-pass records, with a warning; malformed or mismatched stamps are still
errors, and the report is marked NON-REGISTERED.

Concordance with the maintainer: descriptive only (per module)
-------------------------------------------------------------
Concordance is with the maintainer, not an independent gold standard, and it
never changes the reported estimates or the reference. On the audit sample,
R = model reference and H = the maintainer's final value (STRICT); an item is
comparable when both are definite. Reported: item comparability and
design-weighted comparability (sum over comparable items of N_h / m_h over the
module population); paired label counts (R outcome x maintainer label) and
disagreement directions; unweighted agreement and kappa (descriptive); D^, the
comparable-item weighted difference P_R - P_H (weights N_h / c_h), labelled as
not a full-population estimate; and for D = P_R - P_H the conservative
pointwise 95% worst-case-completion interval: each audit item gets bounds on
d = R - H ([R - H, R - H] if comparable; [R - 1, R] if H is missing;
[-H, 1 - H] if R is missing; [-1, 1] if both are), and with d_hi, d_lo the
item-level upper and lower completions,
    U = UCL(P[d_hi = +1]) - LCL(P[d_hi = -1]),
    L = LCL(P[d_lo = +1]) - UCL(P[d_lo = -1]),
each component an exact one-sided limit (estimators.exact_limits) at
CONCORDANCE_COMPONENT_ALPHA = .0125, so each tail of [L, U] errs with
probability at most .025. Sub-strata without audit items are wholly unknown.
No equivalence, adequacy or interchangeability claim is made.

Diagnostics: pairwise agreement and kappa; agreement and STRICT precision by
batch for each primary (no correction); STRICT precision with each primary
alone as the reference (sensitivity). Every estimator's warnings are
collected; those on primary estimates are printed with them.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estimators as E  # noqa: E402
from estimators import wilson  # noqa: E402,F401  (re-exported)

REPO = Path(__file__).resolve().parents[3]
DEFAULT_KEY = REPO / ".cache" / "validation" / "study4" / "key.jsonl"

MD_CATEGORIES = [
    "transitions",
    "frame_markers",
    "endophoric_markers",
    "evidentials",
    "code_glosses",
    "hedges",
    "boosters",
    "attitude_markers",
    "engagement_markers",
    "self_mentions",
]
DIMENSIONS = {
    "interactive": MD_CATEGORIES[:5],
    "interactional": MD_CATEGORIES[5:],
}
K_BANDS = [1, 2, 3, 4, 5]
REGISTERS = ["academic", "general", "argumentative"]
LABELS = {
    "metadiscourse": (
        "CORRECT",
        "WRONG_CATEGORY",
        "EXTERNAL_CONNECTIVE",
        "NOT_METADISCOURSE",
        "UNSURE",
    ),
    "phrase": (
        "CORRECT",
        "WRONG_SENSE_LISTED",
        "WRONG_SENSE_UNLISTED",
        "NOT_THE_EXPRESSION",
        "UNSURE",
    ),
}
LABEL_ABBR = {
    "CORRECT": "C",
    "WRONG_CATEGORY": "WC",
    "EXTERNAL_CONNECTIVE": "EC",
    "NOT_METADISCOURSE": "NM",
    "WRONG_SENSE_LISTED": "WL",
    "WRONG_SENSE_UNLISTED": "WU",
    "NOT_THE_EXPRESSION": "NE",
    "UNSURE": "U",
    "MISSING_OR_INVALID": "X",
}
OUTCOMES: dict[str, dict[str, frozenset[str]]] = {
    "metadiscourse": {
        "STRICT": frozenset({"CORRECT"}),
        "LENIENT": frozenset({"CORRECT", "WRONG_CATEGORY"}),
        "CONNECTIVE": frozenset({"CORRECT", "WRONG_CATEGORY", "EXTERNAL_CONNECTIVE"}),
    },
    "phrase": {
        "STRICT": frozenset({"CORRECT"}),
        "LIST_LENIENT": frozenset({"CORRECT", "WRONG_SENSE_LISTED"}),
        "PHRASAL": frozenset({"CORRECT", "WRONG_SENSE_LISTED", "WRONG_SENSE_UNLISTED"}),
    },
}
PRIMARY_OUTCOME = "STRICT"

# Decision rule thresholds (quoted in the pre-registration).
CONCORDANCE_COMPONENT_ALPHA = 0.0125  # one-sided, per component: each tail of D <= .025
CONFIRMATORY_PREFIXES = ("category=", "k_band=")

ALPHA = E.ALPHA
Z = E.norm_ppf(1 - ALPHA / 2)
MAINTAINER = "maintainer"
ADJUDICATOR = "adjudicator"
MODEL_SOURCES = ("primaries", ADJUDICATOR)


def cohen_kappa(a: list[Any], b: list[Any]) -> float | None:
    """Cohen's kappa; None when undefined (no pairs, or expected agreement 1)."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe >= 1 - 1e-12:
        return None
    return (po - pe) / (1 - pe)


def outcome_applies(outcome: str, row: dict[str, Any]) -> bool:
    return outcome != "CONNECTIVE" or row.get("category") == "transitions"


def outcome_value(module: str, outcome: str, label: str | None) -> int | None:
    if not isinstance(label, str) or label == "UNSURE" or label not in LABELS[module]:
        return None
    return int(label in OUTCOMES[module][outcome])


# --- reading -------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_id_file(path: Path) -> list[str]:
    """Ids from a text file (one per line) or a JSONL file with an `id` field (order kept)."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(json.loads(s)["id"] if s.startswith("{") else s)
    return out


# --- design validation ---------------------------------------------------------


class DesignError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__(f"{len(problems)} design problems:\n" + "\n".join(problems[:50]))
        self.problems = problems


def validate_design(
    key_rows: list[dict[str, Any]],
    item_list: list[dict[str, Any]],
    maintainer_ids: list[str] | None = None,
    orders: dict[str, Any] | None = None,
    frame: dict[str, Any] | None = None,
) -> list[str]:
    """All design consistency problems (empty list = consistent)."""
    p: list[str] = []
    kc = Counter(r.get("id") for r in key_rows)
    ic = Counter(it.get("id") for it in item_list)
    p += [f"duplicate key id {i}" for i, c in kc.items() if c > 1]
    p += [f"duplicate item id {i}" for i, c in ic.items() if c > 1]
    if set(kc) != set(ic):
        p.append(
            f"key and items differ: {len(set(kc) - set(ic))} key-only, "
            f"{len(set(ic) - set(kc))} item-only ids"
        )
    items = {it["id"]: it for it in item_list}
    subs: dict[str, dict[str, Any]] = {}
    for r in key_rows:
        rid, mod = r.get("id"), r.get("module")
        if mod not in LABELS:
            p.append(f"{rid}: unknown module {mod!r}")
            continue
        it = items.get(rid)
        if it is not None:
            claimed = it.get("claimed") or {}
            if it.get("module") != mod:
                p.append(f"{rid}: module differs between key and items")
            elif mod == "metadiscourse" and claimed.get("category") != r.get("category"):
                p.append(f"{rid}: category differs between key and items")
            elif mod == "phrase" and claimed.get("expression") != r.get("expression"):
                p.append(f"{rid}: expression differs between key and items")
        for f in ("N_sub", "n_sub"):
            v = r.get(f)
            if not isinstance(v, int) or isinstance(v, bool):
                p.append(f"{rid}: {f} is not an integer")
        h = r.get("substratum")
        s = subs.setdefault(
            h,
            {
                "module": mod,
                "N": r.get("N_sub"),
                "n": r.get("n_sub"),
                "rows": 0,
                "m": set(),
                "mi": 0,
            },
        )
        s["rows"] += 1
        if s["module"] != mod:
            p.append(f"sub-stratum {h} spans modules")
        if r.get("N_sub") != s["N"] or r.get("n_sub") != s["n"]:
            p.append(f"sub-stratum {h}: N_sub/n_sub not constant")
        if "m_sub" in r:
            s["m"].add(r["m_sub"])
        if r.get("in_maintainer_sample"):
            s["mi"] += 1
    for h, s in subs.items():
        if not (isinstance(s["n"], int) and isinstance(s["N"], int) and 0 < s["n"] <= s["N"]):
            p.append(f"sub-stratum {h}: need 0 < n_sub <= N_sub (got {s['n']}, {s['N']})")
        if s["rows"] != s["n"]:
            p.append(f"sub-stratum {h}: {s['rows']} key rows but n_sub = {s['n']}")
        if s["m"] and (len(s["m"]) > 1 or next(iter(s["m"])) != s["mi"]):
            p.append(f"sub-stratum {h}: m_sub {sorted(s['m'])} != maintainer items {s['mi']}")
    if maintainer_ids is not None:
        mc = Counter(maintainer_ids)
        p += [f"duplicate maintainer-sample id {i}" for i, c in mc.items() if c > 1]
        p += [f"maintainer-sample id {i} not in key" for i in mc if i not in kc]
        flagged = {r["id"] for r in key_rows if r.get("in_maintainer_sample")}
        if any("in_maintainer_sample" in r for r in key_rows) and flagged != set(mc):
            p.append("maintainer-sample ids differ from the key's in_maintainer_sample flags")
    if orders is not None:
        mids = set(maintainer_ids or ())
        for role, o in (orders.get("roles") or {}).items():
            oc = Counter(o.get("order", []))
            p += [f"orders[{role}]: duplicate id {i}" for i, c in oc.items() if c > 1]
            want = mids if role == MAINTAINER else set(kc)
            if set(oc) != want:
                p.append(
                    f"orders[{role}]: ids differ from the {'maintainer sample' if role == MAINTAINER else 'key'}"
                )
            bs = o.get("batch_size")
            if not isinstance(bs, int) or bs <= 0:
                p.append(f"orders[{role}]: batch_size must be a positive integer")
    if frame is not None:
        sampled_reg: dict[str, Counter] = defaultdict(Counter)
        for r in key_rows:
            sampled_reg[r.get("substratum")][r.get("register")] += 1
        if not isinstance(frame.get("modules"), dict):
            p.append("frame: no modules mapping")
        for mod in LABELS:
            fm = (frame.get("modules") or {}).get(mod, {})
            ks = {h for h, s in subs.items() if s["module"] == mod}
            if set(fm) != ks:
                p.append(f"frame/{mod}: sub-strata differ from the key")
            for h in ks & set(fm):
                where = f"frame/{mod}/{h}"
                fn = fm[h].get("N")
                if not _is_int(fn) or fn <= 0:
                    p.append(f"{where}: N must be a positive integer (got {fn!r})")
                    continue
                if fn != subs[h]["N"]:
                    p.append(f"{where}: N {fn} != key N_sub {subs[h]['N']}")
                br = fm[h].get("by_register")
                if br is None:
                    continue
                if not isinstance(br, dict):
                    p.append(f"{where}: by_register must be a mapping")
                    continue
                bad = sorted(str(g) for g in br if g not in REGISTERS)
                if bad:
                    p.append(f"{where}: unknown registers {bad}")
                if any(not _is_int(v) or v < 0 for v in br.values()):
                    p.append(f"{where}: register counts must be nonnegative integers")
                    continue
                if sum(br.values()) != fn:
                    p.append(f"{where}: register counts do not sum to N")
                for g, c in sampled_reg[h].items():
                    if c > br.get(g, 0):
                        p.append(f"{where}: {c} sampled {g} items but the frame has {br.get(g, 0)}")
    return p


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def frame_from_key(key_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback frame: N_h only (register counts unknown)."""
    out: dict[str, Any] = {"modules": {m: {} for m in LABELS}, "derived_from_key": True}
    for r in key_rows:
        out["modules"][r["module"]].setdefault(
            r["substratum"], {"N": r["N_sub"], "by_register": None}
        )
    return out


# --- label validation ----------------------------------------------------------


def norm_sense(s: str) -> str:
    s = s.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
    return re.sub(r"\s+", " ", s).strip().casefold()


REQUIRED_FIELDS = ("id", "label", "alt_category", "note")
ALT_LABELS = ("WRONG_CATEGORY", "WRONG_SENSE_LISTED", "WRONG_SENSE_UNLISTED")
MAX_NOTE_WORDS = 25
MAX_GLOSS_WORDS = 6
UNSURE_NOTE = re.compile(r"^\s*([^:]+):\s*\S")
UNSURE_SPLIT = re.compile(r"\s+or\s+")


def unsure_readings(note: str | None, module: str) -> tuple[list[str] | None, str | None]:
    """The readings named by an UNSURE note, or (None, reason)."""
    if note is None or not note.strip():
        return None, "unsure_without_note"
    m = UNSURE_NOTE.match(note)
    if not m:
        return None, "unsure_note_format"
    readings = [r.strip() for r in UNSURE_SPLIT.split(m.group(1).strip())]
    allowed = set(LABELS[module]) | (set(MD_CATEGORIES) if module == "metadiscourse" else set())
    if any(r not in allowed for r in readings):
        return None, "unsure_reading_invalid"
    if len(set(readings)) < 2:
        return None, "unsure_too_few_readings"
    return readings, None


def _type_error(rec: dict[str, Any]) -> str | None:
    missing = [f for f in REQUIRED_FIELDS if f not in rec]
    if missing:
        return "missing_field", f"missing {', '.join(missing)}"
    if not isinstance(rec["label"], str):
        return "invalid_field_type", "label must be a string"
    for f in ("alt_category", "note"):
        if rec[f] is not None and not isinstance(rec[f], str):
            return "invalid_field_type", f"{f} must be a string or null"
    # Other keys (batch, position, timestamps) are metadata and are not checked.
    return None


def check_record(rec: dict[str, Any], item: dict[str, Any]) -> tuple[str, str] | None:
    """(reason, detail) if the record is invalid for this item, else None."""
    terr = _type_error(rec)
    if terr:
        return terr
    module = item["module"]
    claimed = item.get("claimed") or {}
    label, alt, note = rec["label"], rec["alt_category"], rec["note"]
    if label not in LABELS[module]:
        return "invalid_label", f"{label!r} is not a {module} label"
    if note is not None and len(note.split()) > MAX_NOTE_WORDS:
        return "note_too_long", f"{len(note.split())} words (at most {MAX_NOTE_WORDS})"
    if alt is not None and label not in ALT_LABELS:
        return "alt_category_not_allowed", f"{label} takes alt_category null"
    if label == "EXTERNAL_CONNECTIVE" and claimed.get("category") != "transitions":
        return (
            "external_connective_not_transitions",
            f"claimed category is {claimed.get('category')!r}",
        )
    if label in ALT_LABELS and (alt is None or not alt.strip()):
        return "alt_category_missing", f"{label} needs alt_category"
    if label == "WRONG_CATEGORY":
        # Exact: the ten keys as written, no surrounding spaces.
        if alt not in MD_CATEGORIES:
            return "alt_category_invalid", f"{alt!r} is not one of the ten category keys"
        if alt == claimed.get("category"):
            return "alt_category_same_as_claimed", alt
    if label in ("WRONG_SENSE_LISTED", "WRONG_SENSE_UNLISTED"):
        listed = {norm_sense(o["expression"]) for o in claimed.get("other_senses_in_list") or []}
        if label == "WRONG_SENSE_LISTED" and norm_sense(alt) not in listed:
            return (
                "alt_sense_not_listed",
                f"{alt!r} is not among the item's other_senses_in_list"
                + ("" if listed else " (the item has none)"),
            )
        if label == "WRONG_SENSE_UNLISTED":
            if alt != alt.upper():
                return "gloss_not_capitals", f"{alt!r} must be in capitals"
            if not 1 <= len(alt.split()) <= MAX_GLOSS_WORDS:
                return "gloss_word_count", f"{alt!r} must be 1-{MAX_GLOSS_WORDS} words"
            if norm_sense(alt) in listed or norm_sense(alt) == norm_sense(
                claimed.get("expression") or ""
            ):
                return "alt_sense_is_listed", f"{alt!r} names a listed sense or the claimed entry"
    if label == "UNSURE":
        _, reason = unsure_readings(note, module)
        if reason:
            return reason, f"UNSURE note {note!r}: name two readings joined by 'or', then ':'"
    return None


def canonical(rec: dict[str, Any]) -> tuple[str, str | None]:
    """Duplicate-equality key: label and alt_category after norm_sense; notes ignored."""

    def s(v: Any) -> str | None:
        if v is None:
            return None
        v = v if isinstance(v, str) else json.dumps(v, sort_keys=True)
        return norm_sense(v) or None

    return (s(rec.get("label")) or "", s(rec.get("alt_category")))


@dataclass
class LabelSet:
    """A validated label file."""

    name: str
    labels: dict[str, dict[str, Any]]
    expected: list[str]
    problems: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    retry: list[dict[str, Any]] = field(default_factory=list)
    n_lines: int = 0

    def label(self, rid: str) -> str | None:
        rec = self.labels.get(rid)
        return rec.get("label") if rec else None

    def summary(self) -> dict[str, Any]:
        return {
            "lines": self.n_lines,
            "expected": len(self.expected),
            "valid": len(self.labels),
            "problems_by_reason": dict(sorted(Counter(p["reason"] for p in self.problems).items())),
            "retry": len(self.retry),
            "retry_by_reason": dict(sorted(Counter(r["reason"] for r in self.retry).items())),
            "warnings": len(self.warnings),
        }


def validate_lines(
    lines: Iterable[str],
    items: dict[str, dict[str, Any]],
    expected: Iterable[str] | None = None,
    name: str = "labels",
) -> LabelSet:
    """Validate a whole label file. See the module docstring for the rules."""
    exp = set(items) if expected is None else set(expected)
    problems: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    by_id: dict[str, list[tuple[int, dict[str, Any], tuple[str, str] | None]]] = defaultdict(list)
    n_lines = 0
    for lineno, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        n_lines += 1
        try:
            rec = json.loads(s)
        except json.JSONDecodeError as e:
            problems.append(
                {"line": lineno, "id": None, "reason": "malformed_json", "detail": str(e)}
            )
            continue
        if not isinstance(rec, dict):
            problems.append({"line": lineno, "id": None, "reason": "not_an_object", "detail": None})
            continue
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid:
            problems.append({"line": lineno, "id": None, "reason": "missing_id", "detail": None})
            continue
        if rid not in items:
            problems.append({"line": lineno, "id": rid, "reason": "unknown_id", "detail": None})
            continue
        if rid not in exp:
            problems.append({"line": lineno, "id": rid, "reason": "not_assigned", "detail": None})
            continue
        err = check_record(rec, items[rid])
        by_id[rid].append((lineno, rec, err))

    labels: dict[str, dict[str, Any]] = {}
    invalid: dict[str, tuple[str, str | None]] = {}
    for rid in sorted(by_id):
        recs = by_id[rid]
        lines_s = ", ".join(str(ln) for ln, _, _ in recs)
        canon = {canonical(rec) for _, rec, _ in recs}
        errs = sorted({e for _, _, e in recs if e is not None})
        if len(recs) > 1 and len(canon) > 1:
            invalid[rid] = ("conflicting_duplicate", f"differing records on lines {lines_s}")
        elif len(recs) > 1 and errs:
            invalid[rid] = ("invalid_duplicate", f"{errs[0][0]} on lines {lines_s}")
        elif errs:
            invalid[rid] = errs[0]
        else:
            if len(recs) > 1:
                warnings.append(
                    {
                        "line": recs[1][0],
                        "id": rid,
                        "reason": "identical_duplicate_collapsed",
                        "detail": f"lines {lines_s}",
                    }
                )
            labels[rid] = recs[0][1]
            continue
        problems.append(
            {"line": recs[0][0], "id": rid, "reason": invalid[rid][0], "detail": invalid[rid][1]}
        )
    retry = [{"id": rid, "reason": r, "detail": d} for rid, (r, d) in invalid.items()]
    retry += [
        {"id": rid, "reason": "missing", "detail": None}
        for rid in exp
        if rid not in labels and rid not in invalid
    ]
    retry.sort(key=lambda x: x["id"])
    problems.sort(key=lambda p: (p["line"], p["id"] or "", p["reason"]))
    return LabelSet(name, labels, sorted(exp), problems, warnings, retry, n_lines)


def load_labels(
    path: Path,
    items: dict[str, dict[str, Any]],
    expected: Iterable[str] | None = None,
    name: str | None = None,
) -> LabelSet:
    with path.open(encoding="utf-8") as f:
        return validate_lines(f.read().splitlines(), items, expected, name or path.stem)


def write_retry_manifest(ls: LabelSet, path: Path) -> None:
    """Deterministic: sorted by id, one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in ls.retry),
        encoding="utf-8",
    )


def merge_retry(
    original: list[str], retry: list[str], manifest_ids: Iterable[str]
) -> tuple[list[str], list[str]]:
    """Original lines minus every record of a manifest id, plus the retry's records for them."""
    want = set(manifest_ids)
    notes: list[str] = []

    def rid_of(line: str) -> str | None:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return None
        rid = rec.get("id") if isinstance(rec, dict) else None
        return rid if isinstance(rid, str) else None

    out = []
    for line in original:
        if not line.strip():
            continue
        rid = rid_of(line)
        if rid is None:
            notes.append("dropped a malformed original line")
        elif rid not in want:
            out.append(line)
    for i, line in enumerate(retry, 1):
        if not line.strip():
            continue
        rid = rid_of(line)
        if rid in want:
            out.append(line)
        else:
            notes.append(f"retry line {i}: id {rid!r} not in the manifest, ignored")
    return out, notes


# --- reference -----------------------------------------------------------------


def reference(
    rows: list[dict[str, Any]],
    outcome: str,
    primaries: list[LabelSet],
    adjudicator: LabelSet | None = None,
) -> dict[str, dict[str, Any]]:
    """Model-only reference: id -> {"y": 0/1/None, "source": primaries|adjudicator|unresolved}.

    Maintainer labels never resolve a reference item (they enter only the separate
    maintainer-only and concordance analyses)."""
    ref: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not outcome_applies(outcome, r):
            continue
        rid, mod = r["id"], r["module"]
        votes = [outcome_value(mod, outcome, p.label(rid)) for p in primaries]
        if votes and None not in votes and len(set(votes)) == 1:
            ref[rid] = {"y": votes[0], "source": "primaries"}
            continue
        adj = outcome_value(mod, outcome, adjudicator.label(rid)) if adjudicator else None
        ref[rid] = (
            {"y": adj, "source": ADJUDICATOR}
            if adj is not None
            else {"y": None, "source": "unresolved"}
        )
    return ref


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def second_pass_ids(pass1: LabelSet) -> list[str]:
    """Ids the maintainer labelled UNSURE in the first pass: the second-pass assignment."""
    return sorted(i for i, rec in pass1.labels.items() if rec["label"] == "UNSURE")


SHA256_HEX = re.compile(r"[0-9a-f]{64}")
PASS1_LOG_FORMAT = "study4-pass1-validation/1"
NONREGISTERED = "NON-REGISTERED (synthetic/legacy inputs)"


def validated_text(ls: LabelSet) -> str:
    """The validated form: accepted records, one per id, sorted by id, keys sorted."""
    return "".join(
        json.dumps(ls.labels[i], ensure_ascii=False, sort_keys=True) + "\n"
        for i in sorted(ls.labels)
    )


def validated_pass1(
    raw: list[str],
    items: dict[str, dict[str, Any]],
    sample: Iterable[str],
    retry: list[str] | None = None,
    manifest_ids: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """The validated first-pass file and its validation log (see the module docstring).

    Deterministic: the same inputs give the same bytes. Nothing is relabelled; records
    the validator rejects are left out and listed."""
    sample = sorted(set(sample))
    first = validate_lines(raw, items, sample, MAINTAINER)
    notes: list[str] = []
    lines = raw
    if retry is not None:
        own = [r["id"] for r in first.retry]
        if manifest_ids is None or list(manifest_ids) != own:
            raise ValueError(
                "the retry manifest must be the raw first pass's own retry list "
                f"({len(own)} ids, sorted): got {None if manifest_ids is None else len(manifest_ids)}"
            )
        lines, notes = merge_retry(raw, retry, manifest_ids)
    elif manifest_ids is not None:
        raise ValueError("a retry manifest was given without a retry export")
    final = validate_lines(lines, items, sample, MAINTAINER)
    text = validated_text(final)
    check = validate_lines(text.splitlines(), items, sample, MAINTAINER)
    if check.problems or check.warnings or check.labels != final.labels:
        raise AssertionError("the validated first pass does not revalidate to the same labels")
    log = {
        "format": PASS1_LOG_FORMAT,
        "rule": "records accepted by analyse.validate_lines (after merge_retry with the "
        "single retry export, if any), one per id, sorted by id, serialised with "
        "json.dumps(record, ensure_ascii=False, sort_keys=True); rejected and missing ids "
        "are non-votes, not relabelled",
        "raw_validation": first.summary(),
        "raw_rejected_lines": first.problems,  # line numbers of the raw export
        "retry_given": retry is not None,
        "retry_manifest_ids": list(manifest_ids) if manifest_ids is not None else None,
        "merge_notes": notes,
        "final_validation": final.summary(),
        "accepted": len(final.labels),
        "rejected_lines": final.problems,  # line numbers after merge_retry, if any
        "non_vote_ids": final.retry,
        "collapsed_duplicates": final.warnings,
        "second_pass_ids": second_pass_ids(final),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return text, log


def validated_form_problems(
    path: Path, items: dict[str, dict[str, Any]], sample: Iterable[str]
) -> list[str]:
    """Why `path` is not a validated first-pass file (empty if it is one)."""
    text = path.read_text(encoding="utf-8")
    ls = validate_lines(text.splitlines(), items, sample, MAINTAINER)
    out = [
        f"line {p['line']}"
        + (f" ({p['id']})" if p["id"] else "")
        + f": {p['reason']}"
        + (f": {p['detail']}" if p["detail"] else "")
        for p in ls.problems
    ]
    if out:
        out.insert(0, f"{len(ls.problems)} invalid first-pass record(s)")
    elif text != validated_text(ls):
        out.append("valid records, but not in validated form (one per id, sorted, canonical)")
    return out


def check_pass2_stamps(
    lines: list[str], pass2: LabelSet, pass1_sha: str, registered: bool
) -> dict[str, Any]:
    """Check every pass1_sha256 in the second-pass file against the first-pass file.

    Raises ValueError on a malformed stamp (anywhere in the file), a stamp of another
    file, or, in registered mode, an accepted record without a stamp."""
    bad = []
    stamps: set[str] = set()
    for lineno, line in enumerate(lines, 1):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # reported by the validator
        if not isinstance(rec, dict) or "pass1_sha256" not in rec:
            continue
        v = rec["pass1_sha256"]
        if not (isinstance(v, str) and SHA256_HEX.fullmatch(v)):
            bad.append(f"line {lineno}: {v!r}")
        else:
            stamps.add(v)
    if bad:
        raise ValueError(
            "pass1_sha256 must be a 64-character lowercase hexadecimal SHA-256: " + "; ".join(bad)
        )
    if stamps - {pass1_sha}:
        raise ValueError(
            f"made from a different first-pass file (pass1_sha256 {sorted(stamps - {pass1_sha})} "
            f"!= {pass1_sha} of --maintainer)"
        )
    unstamped = sorted(i for i, r in pass2.labels.items() if "pass1_sha256" not in r)
    if unstamped and registered:
        raise ValueError(
            f"{len(unstamped)} of {len(pass2.labels)} accepted second-pass records lack "
            f"pass1_sha256 (first: {unstamped[:5]}); registered mode requires it on every "
            "record (unstamped files only with --nonregistered-legacy)"
        )
    return {
        "mode": "registered" if registered else NONREGISTERED,
        "accepted_records": len(pass2.labels),
        "stamped": len(pass2.labels) - len(unstamped),
        "unstamped": len(unstamped),
    }


def combine_maintainer_passes(
    pass1: LabelSet, pass2: LabelSet | None
) -> tuple[LabelSet, dict[str, Any]]:
    """Final maintainer labels: the second-pass label for first-pass UNSURE items, else the
    first-pass label. Both passes are kept in the record (pass, pass1_label, pass1_note)."""
    ids2 = second_pass_ids(pass1)
    labels = {i: dict(rec, **{"pass": 1}) for i, rec in pass1.labels.items()}
    resolved = again = missing = 0
    for i in ids2:
        rec = pass2.labels.get(i) if pass2 is not None else None
        if rec is None:
            missing += 1
            labels[i]["second_pass"] = "missing_or_invalid" if pass2 is not None else "not_given"
            continue
        labels[i] = dict(
            rec, **{"pass": 2, "pass1_label": "UNSURE", "pass1_note": pass1.labels[i].get("note")}
        )
        if rec["label"] == "UNSURE":
            again += 1
        else:
            resolved += 1
    final = LabelSet(
        pass1.name,
        labels,
        pass1.expected,
        pass1.problems,
        pass1.warnings,
        pass1.retry,
        pass1.n_lines,
    )
    info = {
        "second_pass_given": pass2 is not None,
        "pass1_unsure": len(ids2),
        "resolved_in_second_pass": resolved,
        "unsure_again": again,
        "second_pass_missing_or_invalid": missing,
        "pass1_label_counts": dict(
            sorted(Counter(r["label"] for r in pass1.labels.values()).items())
        ),
        "final_label_counts": dict(sorted(Counter(r["label"] for r in labels.values()).items())),
        "second_pass_validation": pass2.summary() if pass2 is not None else None,
    }
    return final, info


def needs_adjudication(rows: list[dict[str, Any]], primaries: list[LabelSet]) -> list[str]:
    """Items where any primary is UNSURE/missing/invalid or the primaries split on any outcome."""
    out = []
    for r in rows:
        rid, mod = r["id"], r["module"]
        labels = [p.label(rid) for p in primaries]
        if any(lab is None or lab == "UNSURE" for lab in labels):
            out.append(rid)
            continue
        for oc in OUTCOMES[mod]:
            if outcome_applies(oc, r) and len({outcome_value(mod, oc, lab) for lab in labels}) > 1:
                out.append(rid)
                break
    return sorted(out)


# --- domains and estimation ------------------------------------------------------


def _stratum_of(sub: str) -> str:
    return sub.split("|", 1)[0]


@dataclass(frozen=True)
class Domain:
    name: str
    union: bool  # a union of whole sub-strata (exact population from the frame)
    sub_in: Callable[[str], bool] | None = None
    register: str | None = None
    exploratory: bool = False
    ids: frozenset[str] | None = None  # an explicit set of items (batch diagnostics)

    def contains(self, row: dict[str, Any]) -> bool:
        if self.ids is not None:
            return row["id"] in self.ids
        if self.union:
            return self.sub_in(row["substratum"])
        return row.get("register") == self.register


ALL_DOMAIN = Domain("ALL", True, lambda h: True)


def group_defs(module: str, outcome: str | None = None) -> list[Domain]:
    """Every predefined domain for the module and outcome (empty ones included)."""
    if outcome == "CONNECTIVE":
        return [Domain("category=transitions", True, lambda h: _stratum_of(h) == "transitions")]
    defs = [ALL_DOMAIN]
    if module == "metadiscourse":
        defs += [
            Domain(f"category={c}", True, lambda h, c=c: _stratum_of(h) == c) for c in MD_CATEGORIES
        ]
        defs += [
            Domain(f"dimension={d}", True, lambda h, cs=tuple(cs): _stratum_of(h) in cs)
            for d, cs in DIMENSIONS.items()
        ]
    else:
        defs += [
            Domain(f"k_band={k}", True, lambda h, k=k: _stratum_of(h).startswith(f"K{k}-"))
            for k in K_BANDS
        ]
        defs += [
            Domain(f"multi_sense={m}", True, lambda h, m=m: _stratum_of(h).endswith("-multi") == m)
            for m in (False, True)
        ]
    defs += [Domain(f"register={g}", False, None, g, exploratory=True) for g in REGISTERS]
    return defs


def outcome_subs(frame_mod: dict[str, Any], outcome: str) -> list[str]:
    subs = sorted(frame_mod)
    if outcome == "CONNECTIVE":
        subs = [h for h in subs if _stratum_of(h) == "transitions"]
    return subs


def build_strata(
    rows: list[dict[str, Any]],
    ref: dict[str, dict[str, Any]],
    domain: Domain,
    frame_mod: dict[str, Any],
    subs: list[str],
    phase_ids: set[str] | None = None,
) -> list[E.Stratum]:
    by_h: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_h[r["substratum"]].append(r)
    out = []
    for h in subs:
        fh = frame_mod[h]
        n_h = fh["N"]
        sample = by_h.get(h, [])
        if domain.union:
            m, exact = (n_h if domain.sub_in(h) else 0), True
        elif fh.get("by_register") is not None:
            m, exact = fh["by_register"].get(domain.register, 0), True
        else:
            k = sum(1 for r in sample if domain.contains(r))
            m, exact = (n_h * k / len(sample) if sample else 0.0), False
        phase = [r for r in sample if phase_ids is None or r["id"] in phase_ids]
        res = [r for r in phase if ref.get(r["id"], {}).get("y") is not None]
        out.append(
            E.Stratum(
                h,
                n_h,
                m,
                exact,
                [(domain.contains(r), ref[r["id"]]["y"]) for r in res],
                [ref.get(r["id"], {}).get("y") for r in phase if domain.contains(r)],
            )
        )
    return out


def estimate(
    rows: list[dict[str, Any]],
    ref: dict[str, dict[str, Any]],
    domain: Domain = ALL_DOMAIN,
    frame: dict[str, Any] | None = None,
    phase_ids: set[str] | None = None,
    df: float | None = None,
    outcome: str = PRIMARY_OUTCOME,
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """Domain estimate for one outcome. `rows`: every sampled item of the module."""
    mod = rows[0]["module"] if rows else "metadiscourse"
    frame = frame or frame_from_key(rows)
    fm = frame["modules"][mod]
    subs = outcome_subs(fm, outcome)
    rows = [r for r in rows if outcome_applies(outcome, r)]
    if df is None:
        df = E.design_df(build_strata(rows, ref, ALL_DOMAIN, fm, subs, phase_ids))
    est = E.domain_estimate(build_strata(rows, ref, domain, fm, subs, phase_ids), df, alpha)
    est["sources"] = dict(
        sorted(
            Counter(
                ref.get(r["id"], {}).get("source", "unresolved")
                for r in rows
                if domain.contains(r) and (phase_ids is None or r["id"] in phase_ids)
            ).items()
        )
    )
    est["exploratory"] = domain.exploratory
    est["confirmatory"] = outcome == PRIMARY_OUTCOME and is_confirmatory(domain.name)
    return est


def is_confirmatory(name: str) -> bool:
    return name == "ALL" or name.startswith(CONFIRMATORY_PREFIXES)


# --- agreement -----------------------------------------------------------------


def two_by_two(pairs: list[tuple[int, int]]) -> dict[str, int]:
    c = Counter(pairs)
    return {
        "ref1_maint1": c[(1, 1)],
        "ref1_maint0": c[(1, 0)],
        "ref0_maint1": c[(0, 1)],
        "ref0_maint0": c[(0, 0)],
    }


def agreement(a: LabelSet, b: LabelSet, rows: list[dict[str, Any]]) -> dict[str, Any]:
    both = [r for r in rows if r["id"] in a.labels and r["id"] in b.labels]
    la = [a.label(r["id"]) for r in both]
    lb = [b.label(r["id"]) for r in both]
    bin_pairs = []
    for r, x, y in zip(both, la, lb, strict=True):
        vx = outcome_value(r["module"], PRIMARY_OUTCOME, x)
        vy = outcome_value(r["module"], PRIMARY_OUTCOME, y)
        if vx is not None and vy is not None:
            bin_pairs.append((vx, vy))
    return {
        "n": len(both),
        "labels": {
            "agreement": (sum(x == y for x, y in zip(la, lb, strict=True)) / len(both))
            if both
            else None,
            "kappa": cohen_kappa(la, lb),
        },
        "strict": {
            "n": len(bin_pairs),
            "agreement": (sum(x == y for x, y in bin_pairs) / len(bin_pairs))
            if bin_pairs
            else None,
            "kappa": cohen_kappa([x for x, _ in bin_pairs], [y for _, y in bin_pairs]),
        },
    }


# --- decision ------------------------------------------------------------------


def _completion(r: int | None, m: int | None) -> tuple[int, int]:
    if r is not None and m is not None:
        return r - m, r - m
    if r is not None:
        return r - 1, r
    if m is not None:
        return -m, 1 - m
    return -1, 1


def concordance(
    rows: list[dict[str, Any]],
    ref_model: dict[str, dict[str, Any]],
    maintainer: LabelSet | None,
    maintainer_ids: set[str],
    frame: dict[str, Any] | None = None,
    passes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Descriptive concordance with the maintainer for one module (no decision; see docstring)."""
    if maintainer is None:
        return {"status": "not_evaluated", "reason": "no maintainer label file was given"}
    mod = rows[0]["module"]
    frame = frame or frame_from_key(rows)
    fm = frame["modules"][mod]
    subs = sorted(fm)
    n_total = sum(fm[h]["N"] for h in subs)
    by_h: dict[str, list[dict[str, Any]]] = defaultdict(list)
    vals: dict[str, tuple[int | None, int | None]] = {}
    paired: Counter = Counter()
    for r in rows:
        if r["id"] in maintainer_ids:
            by_h[r["substratum"]].append(r)
            ref = ref_model.get(r["id"], {})
            rv = ref.get("y") if ref.get("source") in MODEL_SOURCES else None
            lab = maintainer.label(r["id"])
            vals[r["id"]] = (rv, outcome_value(mod, PRIMARY_OUTCOME, lab))
            paired[(f"R={'unresolved' if rv is None else rv}", lab or "MISSING_OR_INVALID")] += 1
    pairs = {i: (a, b) for i, (a, b) in vals.items() if a is not None and b is not None}
    n_s, n_c = len(vals), len(pairs)
    w_comp = sum(
        fm[h]["N"] / len(by_h[h]) * sum(1 for r in by_h[h] if r["id"] in pairs) for h in by_h
    )
    same = sum(a == b for a, b in pairs.values())
    agree = same / n_c if n_c else None
    kappa = cohen_kappa([a for a, _ in pairs.values()], [b for _, b in pairs.values()])
    num = den = 0.0
    for h in subs:
        ds = [pairs[r["id"]][0] - pairs[r["id"]][1] for r in by_h.get(h, []) if r["id"] in pairs]
        if ds:
            num += fm[h]["N"] / len(ds) * sum(ds)
            den += fm[h]["N"]
    comp = {i: _completion(*v) for i, v in vals.items()}

    def cells(fn: Callable[[tuple[int, int]], bool]) -> list[tuple[int, int, int, int]]:
        out = []
        for h in subs:
            items = by_h.get(h, [])
            k = sum(1 for r in items if fn(comp[r["id"]]))
            out.append((fm[h]["N"], len(items), k, k))
        return out

    a1 = CONCORDANCE_COMPONENT_ALPHA
    ua = E.exact_limits(cells(lambda c: c[1] == 1), None, a1)
    lb = E.exact_limits(cells(lambda c: c[1] == -1), a1, None)
    la = E.exact_limits(cells(lambda c: c[0] == 1), a1, None)
    ub = E.exact_limits(cells(lambda c: c[0] == -1), None, a1)
    upper = min(1.0, ua["upper"] - lb["lower"])
    lower = max(-1.0, la["lower"] - ub["upper"])
    u = sum(fm[h]["N"] for h in subs if not by_h.get(h)) / n_total if n_total else 1.0
    warnings: list[str] = []
    if u > 0:
        warnings.append(f"{u:.1%} of the population is in sub-strata without audit items (unknown)")
    disagree = sorted(rid for rid, (a, b) in pairs.items() if a != b)
    return {
        "status": "descriptive",
        "maintainer_sample": n_s,
        "definite_comparisons": n_c,
        "comparable_share": n_c / n_s if n_s else 0.0,
        "weighted_comparable_share": w_comp / n_total if n_total else 0.0,
        "paired_label_counts": {f"{a} / {b}": c for (a, b), c in sorted(paired.items())},
        "table": two_by_two(list(pairs.values())),
        "disagreement_directions": {
            "ref1_maint0": [i for i in disagree if pairs[i] == (1, 0)],
            "ref0_maint1": [i for i in disagree if pairs[i] == (0, 1)],
        },
        "agreement": {
            "agree": same,
            "n": n_c,
            "p": agree,
            "wilson95_unweighted": wilson(agree, n_c) if n_c else None,
            "note": "descriptive, unweighted",
        },
        "kappa": kappa,
        "kappa_status": "undefined" if kappa is None else "defined",
        "difference": {
            "D_hat_comparable": num / den if den else None,
            "D_hat_scope": "comparable audit items only (weights N_h / c_h); "
            "not a full-population estimate",
            "interval95_worst_case_completion": (lower, upper),
            "interval_note": "conservative pointwise 95% for D = P_R - P_H: each tail <= .025 "
            "(component limits one-sided .0125); unknown pairs and unaudited sub-strata unknown",
            "unaudited_population_share": u,
            "components": {
                "UCL P[d_hi=+1]": ua["upper"],
                "LCL P[d_hi=-1]": lb["lower"],
                "LCL P[d_lo=+1]": la["lower"],
                "UCL P[d_lo=-1]": ub["upper"],
                "methods": sorted({x["method"] for x in (ua, lb, la, ub)}),
            },
        },
        "maintainer_passes": _module_passes(rows, maintainer, maintainer_ids, passes),
        "disagreements": disagree,
        "warnings": warnings,
    }


def _module_passes(
    rows: list[dict[str, Any]],
    final: LabelSet,
    maintainer_ids: set[str],
    passes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Second-pass counts for this module's audit items (from the combined records)."""
    recs = [final.labels.get(r["id"]) for r in rows if r["id"] in maintainer_ids]
    p2 = [x for x in recs if x and x.get("pass") == 2]
    miss = [x for x in recs if x and x.get("second_pass")]
    return {
        "second_pass_given": bool(passes and passes.get("second_pass_given")),
        "pass1_unsure": len(p2) + len(miss),
        "resolved_in_second_pass": sum(1 for x in p2 if x["label"] != "UNSURE"),
        "unsure_again": sum(1 for x in p2 if x["label"] == "UNSURE"),
        "second_pass_missing_or_invalid": len(miss)
        if passes and passes.get("second_pass_given")
        else 0,
    }


# --- batches -------------------------------------------------------------------


def batch_of(ls: LabelSet, orders: dict[str, Any] | None) -> dict[str, Any]:
    """id -> batch, from the label records or the build's orders.json (role = labeller name)."""
    out = {rid: rec["batch"] for rid, rec in ls.labels.items() if rec.get("batch") is not None}
    role = (orders or {}).get("roles", {}).get(ls.name)
    if role:
        bs = role["batch_size"]
        for pos, rid in enumerate(role["order"]):
            out.setdefault(rid, pos // bs + 1)
    return out


def batch_diagnostics(
    rows_by_mod: dict[str, list[dict[str, Any]]],
    primaries: list[LabelSet],
    orders: dict[str, Any] | None,
    frame: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in primaries:
        bmap = batch_of(p, orders)
        if not bmap:
            continue
        others = [q for q in primaries if q is not p]
        res: dict[str, Any] = {}
        for b in sorted(set(bmap.values()), key=str):
            row: dict[str, Any] = {}
            for mod, rows in rows_by_mod.items():
                ids = {r["id"] for r in rows if bmap.get(r["id"]) == b}
                if not ids:
                    continue
                single = {
                    r["id"]: {"y": outcome_value(mod, PRIMARY_OUTCOME, p.label(r["id"]))}
                    for r in rows
                }
                est = _batch_estimate(rows, single, ids, frame)
                agr = [
                    (
                        outcome_value(mod, PRIMARY_OUTCOME, p.label(i)),
                        outcome_value(mod, PRIMARY_OUTCOME, q.label(i)),
                    )
                    for i in ids
                    for q in others
                ]
                agr = [(a, c) for a, c in agr if a is not None and c is not None]
                row[mod] = {
                    "n": len(ids),
                    "strict_precision_self": est["p"],
                    "strict_precision_self_ci95_exact": est["ci95_exact"],
                    "unweighted_correct_share": est["unweighted"]["p"]
                    if est["unweighted"]
                    else None,
                    "agreement_with_other_primary": (sum(a == c for a, c in agr) / len(agr))
                    if agr
                    else None,
                    "n_agreement": len(agr),
                }
            res[str(b)] = row
        out[p.name] = res
    return out


def _batch_estimate(rows, ref, ids, frame) -> dict[str, Any]:
    """A batch as a random cross-class domain; its populations are estimated from the sample."""
    mod = rows[0]["module"]
    fm = {h: {"N": s["N"], "by_register": None} for h, s in frame["modules"][mod].items()}
    dom = Domain("batch", False, exploratory=True, ids=frozenset(ids))
    return estimate(rows, ref, dom, {"modules": {mod: fm}})


# --- main analysis -------------------------------------------------------------


def maintainer_ids_from(key_rows: list[dict[str, Any]], key_path: Path | None) -> list[str]:
    if any("in_maintainer_sample" in r for r in key_rows):
        return sorted(r["id"] for r in key_rows if r.get("in_maintainer_sample"))
    if key_path is not None and (key_path.parent / "human_sample_ids.txt").exists():
        return read_id_file(key_path.parent / "human_sample_ids.txt")
    return []


def label_counts(rows, domain: Domain, labellers: list[LabelSet | None], phase_ids=None) -> dict:
    out = {}
    for ls in labellers:
        if ls is None:
            continue
        exp = set(ls.expected)
        c: Counter = Counter()
        for r in rows:
            if (
                domain.contains(r)
                and r["id"] in exp
                and (phase_ids is None or r["id"] in phase_ids)
            ):
                c[ls.label(r["id"]) or "MISSING_OR_INVALID"] += 1
        out[ls.name] = dict(sorted(c.items()))
    return out


def analyse(
    key_rows: list[dict[str, Any]],
    primaries: list[LabelSet],
    adjudicator: LabelSet | None = None,
    maintainer: LabelSet | None = None,
    maintainer_ids: Iterable[str] | None = None,
    orders: dict[str, Any] | None = None,
    frame: dict[str, Any] | None = None,
    sensitivity: bool = True,
    maintainer_pass2: LabelSet | None = None,
    scope: str = "full",
) -> dict[str, Any]:
    """The whole registered analysis. scope="module" computes only what the module-level
    validation needs (STRICT, domain ALL, the concordance) through the same code path."""
    if len(primaries) != 2:
        raise ValueError("the registered design has exactly two primary labellers")
    if scope not in ("full", "module"):
        raise ValueError(f"unknown scope {scope!r}")
    full = scope == "full"
    mids = set(maintainer_ids or ())
    frame = frame or frame_from_key(key_rows)
    rows_by_mod: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in key_rows:
        rows_by_mod[r["module"]].append(r)
    passes = None
    pass1 = maintainer
    if maintainer is not None:
        maintainer, passes = combine_maintainer_passes(maintainer, maintainer_pass2)
    rep: dict[str, Any] = {
        "scope": scope,
        "outcomes": {m: {o: sorted(v) for o, v in d.items()} for m, d in OUTCOMES.items()},
        "concordance_parameters": {"CONCORDANCE_COMPONENT_ALPHA": CONCORDANCE_COMPONENT_ALPHA},
        "frame": "frame.json (full hit population)"
        if not frame.get("derived_from_key")
        else "derived from key (register populations estimated)",
        "labellers": {
            "primaries": [p.name for p in primaries],
            "adjudicator": adjudicator.name if adjudicator else None,
            "maintainer": maintainer is not None,
            "maintainer_second_pass": maintainer_pass2 is not None,
        },
        "validation": {
            ls.name: ls.summary() for ls in [*primaries, adjudicator, pass1] if ls is not None
        }
        | ({"maintainer_pass2": maintainer_pass2.summary()} if maintainer_pass2 else {}),
        "maintainer_passes": passes,
        "adjudication": {},
        "reference_sources": {},
        "model_reference": {},
        "primary": {},
        "maintainer_concordance": {},
        "maintainer_only": {},
        "sensitivity_single_primary": {},
        "agreement_pairs": {},
        "batches": batch_diagnostics(rows_by_mod, primaries, orders, frame) if full else {},
        "alt_categories": {},
        "warnings": [],
    }
    model_labellers = [*primaries, adjudicator]
    for mod in LABELS:
        rows = rows_by_mod.get(mod, [])
        if not rows:
            continue
        need = needs_adjudication(rows, primaries)
        rep["adjudication"][mod] = {
            "needed": len(need),
            "labelled": sum(1 for i in need if adjudicator and i in adjudicator.labels),
        }
        outcomes = list(OUTCOMES[mod]) if full else [PRIMARY_OUTCOME]
        refs = {oc: reference(rows, oc, primaries, adjudicator) for oc in outcomes}
        rep["reference_sources"][mod] = {
            oc: dict(sorted(Counter(v["source"] for v in ref.values()).items()))
            for oc, ref in refs.items()
        }
        rep["model_reference"][mod], rep["maintainer_only"][mod] = {}, {}
        for oc in outcomes:
            frows = [r for r in rows if outcome_applies(oc, r)]
            fm = frame["modules"][mod]
            subs = outcome_subs(fm, oc)
            df = E.design_df(build_strata(frows, refs[oc], ALL_DOMAIN, fm, subs))
            doms = group_defs(mod, oc) if full else [ALL_DOMAIN]
            table = {}
            for dom in doms:
                est = estimate(rows, refs[oc], dom, frame, df=df, outcome=oc)
                est["label_counts"] = label_counts(frows, dom, model_labellers)
                table[dom.name] = est
            rep["model_reference"][mod][oc] = table
            if maintainer is not None and full:
                mref = {
                    r["id"]: {
                        "y": outcome_value(mod, oc, maintainer.label(r["id"])),
                        "source": MAINTAINER,
                    }
                    for r in frows
                    if r["id"] in mids
                }
                mdf = E.design_df(build_strata(frows, mref, ALL_DOMAIN, fm, subs, mids))
                mt = {}
                for dom in doms:
                    est = estimate(rows, mref, dom, frame, phase_ids=mids, df=mdf, outcome=oc)
                    est["label_counts"] = label_counts(frows, dom, [maintainer], mids)
                    est["exploratory"] = True if dom.name != "ALL" else dom.exploratory
                    mt[dom.name] = est
                rep["maintainer_only"][mod][oc] = mt
        rep["maintainer_concordance"][mod] = concordance(
            rows, refs[PRIMARY_OUTCOME], maintainer, mids, frame, passes
        )
        prim = {
            name: est
            for name, est in rep["model_reference"][mod][PRIMARY_OUTCOME].items()
            if est["confirmatory"]
        }
        rep["primary"][mod] = {
            "estimates": prim,
            "warnings": [f"{g}: {w}" for g, est in prim.items() for w in est["warnings"]],
        }
        if not full:
            continue
        if sensitivity:
            for p in primaries:
                single = {
                    r["id"]: {
                        "y": outcome_value(mod, PRIMARY_OUTCOME, p.label(r["id"])),
                        "source": p.name,
                    }
                    for r in rows
                }
                rep["sensitivity_single_primary"].setdefault(p.name, {})[mod] = {
                    dom.name: estimate(rows, single, dom, frame) for dom in group_defs(mod)
                }
        present = [x for x in [*model_labellers, maintainer] if x is not None]
        rep["agreement_pairs"][mod] = {
            f"{a.name} vs {b.name}": agreement(a, b, rows)
            for a, b in itertools.combinations(present, 2)
        }
        for ls in present:
            c: Counter = Counter()
            for r in rows:
                rec = ls.labels.get(r["id"])
                if rec and rec["label"] in (
                    "WRONG_CATEGORY",
                    "WRONG_SENSE_LISTED",
                    "WRONG_SENSE_UNLISTED",
                ):
                    claimed = r.get("category") or r.get("expression")
                    c[f"{claimed} -> {rec['alt_category'].strip()}"] += 1
            rep["alt_categories"].setdefault(ls.name, {})[mod] = dict(c.most_common())
    for kind in ("model_reference", "maintainer_only"):
        for mod, tables in rep[kind].items():
            for oc, table in tables.items():
                for name, est in table.items():
                    rep["warnings"] += [f"{kind} {mod} {oc} {name}: {w}" for w in est["warnings"]]
    for mod, dec in rep["maintainer_concordance"].items():
        rep["warnings"] += [f"concordance {mod}: {w}" for w in dec.get("warnings", [])]
    return rep


def clean_json(x: Any) -> Any:
    """Replace non-finite floats with null (standard JSON)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: clean_json(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [clean_json(v) for v in x]
    return x


# --- Markdown ------------------------------------------------------------------


def _ci(ci) -> str:
    return "–" if not ci else f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def _num(x: float | None, nd: int = 3) -> str:
    return "–" if x is None else f"{x:.{nd}f}"


def _int(x: float | None) -> str:
    return "–" if x is None else f"{x:,.0f}"


def _kappa(k: float | None) -> str:
    return "undefined" if k is None else f"{k:.3f}"


METHOD_ABBR = {
    "korn_graubard_modified_wilson": "KG",
    "exact_stratified_chernoff": "joint",
    "exact_hypergeometric": "hyper",
    "census": "census",
    "census_and_unobserved": "census+unknown",
    None: "–",
}


def _m(x: str | None) -> str:
    return METHOD_ABBR.get(x, x or "–")


def _counts(lc: dict[str, dict[str, int]]) -> str:
    return "; ".join(
        f"{name}: " + " ".join(f"{LABEL_ABBR.get(k, k)}{v}" for k, v in c.items())
        for name, c in lc.items()
    )


def _table(table: dict[str, dict[str, Any]], title_p: str) -> list[str]:
    lines = [
        f"| Group | Items | Resolved | {title_p} | Exact 95% CI (primary) | "
        "Exact resolution region (co-primary) | KG 95% CI (approximate) | Population | "
        "Represented | Label counts |",
        "|---|---:|---:|---:|---|---|---|---:|---:|---|",
    ]
    for name, e in table.items():
        pop = f"{e['population']:,.0f}" if e["population_exact"] else f"≈{e['population']:,.0f}"
        kg = _ci(e["ci95_approx"])
        if e["ci95_approx"] and e["ci95_approx_scope"] == "represented_cells_only":
            kg += " (represented cells only)"
        tag = " (exploratory)" if e.get("exploratory") else ""
        pt = _num(e["p"])
        if e["p"] is None and e.get("p_represented") is not None:
            pt = f"– (represented cells only: {e['p_represented']:.3f})"
        lines.append(
            f"| {name}{tag} | {e['n_items']} | {e['n_resolved']} | {pt} | "
            f"{_ci(e['ci95_exact'])} {_m(e['ci95_exact_method'])} | "
            f"{_ci(e['region95_exact'])} | {kg} | {pop} | {_num(e['represented_share'])} | "
            f"{_counts(e.get('label_counts', {}))} |"
        )
    return lines


def to_markdown(rep: dict[str, Any]) -> str:
    L = ["# Study 4 precision report", ""]
    L += [
        "Precision refers to the finite population of detector hits on these texts. Limits "
        "quantify item-sampling uncertainty conditional on the texts; they exclude text-selection "
        "uncertainty and reference-label error.",
        "",
        "Fixed in advance. PRIMARY: the model-reference estimate (labellers A and B and the "
        "adjudicator only; maintainer labels never enter it) with exact, pointwise, "
        "finite-population 95% limits obtained from a joint stratified tail bound; they assume "
        "resolved items are uniform random subsets of their cells and keep cells without resolved "
        "items as unknown. CO-PRIMARY: the exact pointwise 95% resolution region, which makes no "
        "assumption about unresolved items. Each limit is a separate pointwise 95% statement: "
        "there is no simultaneous coverage across domains, constructions or modules. KG "
        "(Korn–Graubard modified Wilson) is the only approximate interval. Maintainer-only "
        "estimates are a separate secondary analysis (exact limits under their own assumptions). "
        "A point estimate is shown for a domain only when every cell with population has a "
        "resolved item; otherwise the represented-cells estimate is shown and labelled. Exact "
        "methods: hyper = exact hypergeometric (one sampled cell); joint = joint stratified "
        "Chernoff tail bound (estimators.py). Label counts: "
        + ", ".join(f"{v} = {k}" for k, v in LABEL_ABBR.items())
        + ".",
        "",
        "## Primary results (STRICT precision, model reference)",
        "",
    ]
    for mod, prim in rep["primary"].items():
        L += [f"### {mod}", ""] + _table(prim["estimates"], "Precision")
        if prim["warnings"]:
            L += ["", "Warnings affecting these estimates:", ""] + [
                f"- {w}" for w in prim["warnings"]
            ]
        L.append("")

    L += [
        "## Concordance with the maintainer (descriptive)",
        "",
        "Descriptive only: no equivalence, adequacy or gold-standard claim, and it never changes "
        "the reported estimates. D = P_R − P_H (model reference minus maintainer, STRICT). D^ uses "
        "comparable audit items only and is not a full-population estimate. The interval is a "
        "conservative pointwise 95% worst-case-completion interval (each tail ≤ .025; component "
        "limits one-sided .0125): unknown pairs and unaudited sub-strata count as unknown. "
        "Maintainer labels are final after the second blind pass on first-pass UNSURE items.",
        "",
        "| Module | Comparisons | Share | Weighted share | Agreement (unweighted) | κ | "
        "R1/M0 | R0/M1 | D^ (comparable items) | 95% interval for D (worst-case completion) | "
        "Second pass (UNSURE → resolved / again / missing) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for mod, dec in rep["maintainer_concordance"].items():
        if dec["status"] == "not_evaluated":
            L.append(f"| {mod} | not evaluated | – | – | – | – | – | – | – | – | – |")
            continue
        a, d, dd = dec["agreement"], dec["difference"], dec["disagreement_directions"]
        ps = dec.get("maintainer_passes") or {}
        sp = (
            f"{ps['pass1_unsure']} → {ps['resolved_in_second_pass']} / {ps['unsure_again']} / "
            f"{ps['second_pass_missing_or_invalid']}"
            if ps.get("second_pass_given")
            else f"not given ({ps.get('pass1_unsure', 0)} UNSURE)"
        )
        L.append(
            f"| {mod} | {dec['definite_comparisons']}/{dec['maintainer_sample']} | "
            f"{dec['comparable_share']:.3f} | {dec['weighted_comparable_share']:.3f} | "
            f"{_num(a['p'])} | {_kappa(dec['kappa'])} | {len(dd['ref1_maint0'])} | "
            f"{len(dd['ref0_maint1'])} | {_num(d['D_hat_comparable'])} | "
            f"{_ci(d['interval95_worst_case_completion'])} | {sp} |"
        )
    mf = rep.get("maintainer_files")
    if mf:
        L += [
            "",
            f"Maintainer files: first pass SHA-256 `{mf['pass1_sha256']}`; second pass "
            + (f"SHA-256 `{mf['pass2_sha256']}`." if mf["pass2_sha256"] else "not given."),
        ]
        if mf.get("mode", "registered") != "registered":
            L += [
                "",
                f"**{mf['mode']}:** the maintainer files were not checked as registered "
                "(validated first pass; every second-pass record stamped with its hash). "
                "Not evidence for the registered study.",
            ]
    L += ["", "Paired label counts (model reference outcome / maintainer final label):", ""]
    for mod, dec in rep["maintainer_concordance"].items():
        if dec["status"] != "not_evaluated":
            L.append(
                f"- {mod}: " + "; ".join(f"{k} {v}" for k, v in dec["paired_label_counts"].items())
            )
    L.append("")

    for mod, tables in rep["model_reference"].items():
        L += [f"## {mod}: model-reference estimates, all outcomes and domains", ""]
        for oc, table in tables.items():
            L += [f"### {oc}", ""] + _table(table, oc) + [""]
        if rep["maintainer_only"].get(mod):
            L += [
                f"## {mod}: maintainer-only estimates (separate secondary analysis; two-phase; "
                "exact limits under its assumptions; exploratory below module level)",
                "",
            ]
            for oc, table in rep["maintainer_only"][mod].items():
                L += [f"### {oc}", ""] + _table(table, oc) + [""]
        L += [f"### {mod}: STRICT with each primary alone as reference (sensitivity)", ""]
        L += ["| Primary | Precision | Exact 95% CI | Resolved |", "|---|---:|---|---:|"]
        for name, d in rep["sensitivity_single_primary"].items():
            e = d.get(mod, {}).get("ALL")
            if e:
                L.append(
                    f"| {name} | {_num(e['p'])} | {_ci(e['ci95_exact'])} | {e['n_resolved']} |"
                )
        L += ["", f"### {mod}: agreement", ""]
        L += [
            "| Pair | n | Agreement | κ (labels) | STRICT n | STRICT agreement | STRICT κ |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for pair, a in rep["agreement_pairs"][mod].items():
            L.append(
                f"| {pair} | {a['n']} | {_num(a['labels']['agreement'])} | {_kappa(a['labels']['kappa'])} | "
                f"{a['strict']['n']} | {_num(a['strict']['agreement'])} | {_kappa(a['strict']['kappa'])} |"
            )
        L.append("")

    L += ["## Label validation", "", "| Labeller | Lines | Expected | Valid | Retry | Problems |"]
    L += ["|---|---:|---:|---:|---:|---|"]
    for name, s in rep["validation"].items():
        probs = ", ".join(f"{k} {v}" for k, v in s["problems_by_reason"].items()) or "–"
        L.append(
            f"| {name} | {s['lines']} | {s['expected']} | {s['valid']} | {s['retry']} | {probs} |"
        )
    L.append("")
    if rep["batches"]:
        L += ["## Batches (diagnostic, no correction)", ""]
        L += [
            "| Primary | Batch | Module | n | STRICT (self) [exact] | Agreement with other primary |"
        ]
        L += ["|---|---|---|---:|---|---:|"]
        for name, bs in rep["batches"].items():
            for b, mods in bs.items():
                for mod, d in mods.items():
                    L.append(
                        f"| {name} | {b} | {mod} | {d['n']} | {_num(d['strict_precision_self'])} "
                        f"{_ci(d['strict_precision_self_ci95_exact'])} | "
                        f"{_num(d['agreement_with_other_primary'])} |"
                    )
        L.append("")
    if rep["warnings"]:
        L += ["## All warnings", ""] + [f"- {w}" for w in rep["warnings"]] + [""]
    return "\n".join(L)


# --- synthetic labels ----------------------------------------------------------


def _truth(row: dict[str, Any], item: dict[str, Any], p_correct: float) -> tuple[str, Any]:
    r = random.Random(f"truth-{row['id']}")
    if r.random() < p_correct:
        return "CORRECT", None
    return _wrong(row, item, r)


def _wrong(row: dict[str, Any], item: dict[str, Any], r: random.Random) -> tuple[str, Any]:
    claimed = item.get("claimed") or {}
    if row["module"] == "metadiscourse":
        opts: list[tuple[str, Any]] = [("NOT_METADISCOURSE", None)]
        cat = claimed.get("category", row.get("category"))
        opts.append(("WRONG_CATEGORY", r.choice([c for c in MD_CATEGORIES if c != cat])))
        if cat == "transitions":
            opts.append(("EXTERNAL_CONNECTIVE", None))
    else:
        opts = [("NOT_THE_EXPRESSION", None), ("WRONG_SENSE_UNLISTED", "SOME OTHER SENSE")]
        others = claimed.get("other_senses_in_list") or []
        if others:
            opts.append(("WRONG_SENSE_LISTED", r.choice(others)["expression"]))
    return r.choice(opts)


def make_dummy_labels(
    key_rows: list[dict[str, Any]],
    items: dict[str, dict[str, Any]],
    seed: int,
    p_correct: float = 0.8,
    p_flip: float = 0.1,
    p_unsure: float = 0.03,
) -> list[dict[str, Any]]:
    """Synthetic labels: a latent truth per item, changed per labeller with p_flip."""
    r = random.Random(seed)
    out = []
    for row in key_rows:
        item = items.get(row["id"], {"claimed": {}})
        label, alt = _truth(row, item, p_correct)
        note = None
        if r.random() < p_unsure:
            first = (
                "NOT_METADISCOURSE" if row["module"] == "metadiscourse" else "NOT_THE_EXPRESSION"
            )
            label, alt, note = "UNSURE", None, f"CORRECT or {first}: two readings (synthetic)"
        elif r.random() < p_flip:
            label, alt = ("CORRECT", None) if label != "CORRECT" else _wrong(row, item, r)
        out.append({"id": row["id"], "label": label, "alt_category": alt, "note": note})
    return out


def _write_jsonl(path: Path, recs: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in recs), "utf-8")


# --- CLI -----------------------------------------------------------------------


def _spec(spec: str, default_name: str | None = None) -> tuple[str, Path]:
    if "=" in spec:
        name, _, path = spec.partition("=")
        return name, Path(path)
    return default_name or Path(spec).stem, Path(spec)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY)
    ap.add_argument("--items", type=Path, help="items.jsonl (default: next to the key)")
    ap.add_argument("--frame", type=Path, help="frame.json (default: next to the key)")
    ap.add_argument("--labels", nargs="*", default=[], help="primary files, NAME=PATH (A, B)")
    ap.add_argument("--adjudicator", help="adjudicator labels, NAME=PATH or PATH")
    ap.add_argument("--adjudicator-ids", type=Path, help="ids assigned to the adjudicator")
    ap.add_argument("--maintainer", "--human", dest="maintainer", type=Path, help="first pass")
    ap.add_argument(
        "--maintainer-pass2", type=Path, help="second blind pass on the first-pass UNSURE items"
    )
    ap.add_argument(
        "--second-pass-ids", type=Path, metavar="OUT", help="write the second-pass ids and stop"
    )
    ap.add_argument("--maintainer-ids", type=Path, help="override the maintainer sample ids")
    ap.add_argument("--orders", type=Path, help="orders.json from build.py (batches)")
    ap.add_argument("--retry-manifest", type=Path, metavar="DIR")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--disagreements", type=Path, metavar="IDS")
    ap.add_argument("--merge-retry", nargs=2, type=Path, metavar=("ORIGINAL", "RETRY"))
    ap.add_argument("--manifest", type=Path, help="retry manifest for --merge-retry")
    ap.add_argument("--merged-out", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--write-dummy", type=Path, metavar="DIR")
    ap.add_argument(
        "--validate-pass1",
        type=Path,
        metavar="RAW",
        help="build the validated first-pass file from the raw export, then stop",
    )
    ap.add_argument("--pass1-retry", type=Path, metavar="RETRY", help="the single retry export")
    ap.add_argument("--validated-out", type=Path, help="validated first-pass file to write")
    ap.add_argument("--validation-log", type=Path, help="JSON log of --validate-pass1")
    ap.add_argument(
        "--nonregistered-legacy",
        action="store_true",
        help="NON-REGISTERED, synthetic/legacy inputs only: accept an unvalidated "
        "--maintainer and second-pass records without pass1_sha256",
    )
    args = ap.parse_args(argv)

    if args.merge_retry:
        if not (args.manifest and args.merged_out):
            ap.error("--merge-retry needs --manifest and --merged-out")
        orig = args.merge_retry[0].read_text(encoding="utf-8").splitlines()
        retry = args.merge_retry[1].read_text(encoding="utf-8").splitlines()
        merged, notes = merge_retry(orig, retry, read_id_file(args.manifest))
        args.merged_out.write_text("".join(x + "\n" for x in merged), encoding="utf-8")
        for n in notes:
            print(n, file=sys.stderr)
        print(f"merged {len(merged)} lines -> {args.merged_out}", file=sys.stderr)
        return 0

    key_rows = read_jsonl(args.key)
    items_path = args.items or args.key.parent / "items.jsonl"
    item_list = read_jsonl(items_path)
    mid_list = (
        read_id_file(args.maintainer_ids)
        if args.maintainer_ids
        else maintainer_ids_from(key_rows, args.key)
    )
    orders_path = args.orders or args.key.parent / "orders.json"
    orders = json.loads(orders_path.read_text()) if orders_path.exists() else None
    frame_path = args.frame or args.key.parent / "frame.json"
    frame = json.loads(frame_path.read_text()) if frame_path.exists() else None
    problems = validate_design(key_rows, item_list, mid_list, orders, frame)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(f"design validation failed ({len(problems)} problems)")
    if frame is None:
        print("no frame.json: register populations will be estimated", file=sys.stderr)
    items = {it["id"]: it for it in item_list}
    mids = set(mid_list)

    if args.validate_pass1:
        if not (args.validated_out and args.validation_log):
            ap.error("--validate-pass1 needs --validated-out and --validation-log")
        if bool(args.pass1_retry) != bool(args.manifest):
            ap.error("--pass1-retry and --manifest go together")
        for out in (args.validated_out, args.validation_log):
            if out.exists():
                raise SystemExit(f"{out} exists: refusing to overwrite (write to a new path)")
        raw = args.validate_pass1.read_text(encoding="utf-8").splitlines()
        retry = (
            args.pass1_retry.read_text(encoding="utf-8").splitlines() if args.pass1_retry else None
        )
        man = read_id_file(args.manifest) if args.manifest else None
        try:
            text, log = validated_pass1(raw, items, mids, retry, man)
        except ValueError as e:
            raise SystemExit(f"--validate-pass1: {e}") from None
        args.validated_out.write_text(text, encoding="utf-8")
        log |= {
            "tool": {
                "command": [sys.executable, *sys.argv] if argv is None else ["analyse.py", *argv],
                "analyse_sha256": file_sha256(Path(__file__)),
            },
            "inputs": {
                name: {"path": str(path), "sha256": file_sha256(path)}
                for name, path in (
                    ("raw_first_pass", args.validate_pass1),
                    ("retry_export", args.pass1_retry),
                    ("retry_manifest", args.manifest),
                    ("key", args.key),
                    ("items", items_path),
                    ("maintainer_ids", args.maintainer_ids),
                )
                if path is not None
            },
            "maintainer_sample_sha256": hashlib.sha256(
                "".join(i + "\n" for i in sorted(mids)).encode("utf-8")
            ).hexdigest(),
            "output": {"path": str(args.validated_out), "sha256": file_sha256(args.validated_out)},
        }
        if log["output"]["sha256"] != log["output_sha256"]:
            raise SystemExit("the written validated file does not match its computed hash")
        args.validation_log.write_text(
            json.dumps(clean_json(log), indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(
            f"{log['accepted']} accepted, {len(log['non_vote_ids'])} non-vote ids, "
            f"{len(log['second_pass_ids'])} second-pass ids -> {args.validated_out} "
            f"(sha256 {log['output_sha256']}); log -> {args.validation_log}",
            file=sys.stderr,
        )
        return 0

    if args.write_dummy:
        d = args.write_dummy
        d.mkdir(parents=True, exist_ok=True)
        a = make_dummy_labels(key_rows, items, 1)
        b = make_dummy_labels(key_rows, items, 2)
        lines_a = [json.dumps(x) for x in a]
        lines_a[5] = lines_a[5][:-3]  # a malformed line, to exercise validation
        lines_a.append(json.dumps(a[7]))  # an identical duplicate
        (d / "A.jsonl").write_text("\n".join(lines_a) + "\n", encoding="utf-8")
        _write_jsonl(d / "B.jsonl", b)
        la = validate_lines(lines_a, items, name="A")
        lb = validate_lines([json.dumps(x) for x in b], items, name="B")
        need = set(needs_adjudication(key_rows, [la, lb]))
        _write_jsonl(d / "adjudicator_ids.jsonl", ({"id": i} for i in sorted(need)))
        _write_jsonl(
            d / "C.jsonl", make_dummy_labels([r for r in key_rows if r["id"] in need], items, 4)
        )
        m1 = make_dummy_labels([r for r in key_rows if r["id"] in mids], items, 3, p_flip=0.03)
        text, _ = validated_pass1([json.dumps(x) for x in m1], items, mids)
        (d / "maintainer.jsonl").write_text(text, encoding="utf-8")  # validated form
        unsure = {x["id"] for x in m1 if x["label"] == "UNSURE"}
        m2 = make_dummy_labels([r for r in key_rows if r["id"] in unsure], items, 5, p_unsure=0.2)
        sha1 = file_sha256(d / "maintainer.jsonl")
        _write_jsonl(d / "maintainer_pass2.jsonl", (x | {"pass1_sha256": sha1} for x in m2))
        print(f"wrote synthetic labels to {d}", file=sys.stderr)
        return 0

    primaries: list[LabelSet] = []
    for spec in args.labels:
        name, path = _spec(spec)
        primaries.append(load_labels(path, items, None, name))
    adjudicator = None
    if args.adjudicator:
        name, path = _spec(args.adjudicator, ADJUDICATOR)
        exp = (
            read_id_file(args.adjudicator_ids)
            if args.adjudicator_ids
            else needs_adjudication(key_rows, primaries)
        )
        adjudicator = load_labels(path, items, exp, name)
    maintainer = load_labels(args.maintainer, items, mids, MAINTAINER) if args.maintainer else None
    registered = not args.nonregistered_legacy
    pass1_form: list[str] | None = None
    if maintainer is not None:
        pass1_form = validated_form_problems(args.maintainer, items, mids)
        uses_pass1 = args.second_pass_ids or args.maintainer_pass2
        if (
            pass1_form
            and registered
            and (uses_pass1 or not (args.validate_only or args.disagreements))
        ):
            raise SystemExit(
                f"{args.maintainer}: not a validated first-pass file: "
                + "; ".join(pass1_form[:10])
                + ". Labels must not be corrected by hand: build it with analyse.py "
                "--validate-pass1 (see the module docstring) and pass that file as --maintainer "
                "(--nonregistered-legacy for synthetic/legacy inputs only)"
            )
    if args.second_pass_ids:
        if maintainer is None:
            ap.error("--second-pass-ids needs --maintainer")
        ids2 = second_pass_ids(maintainer)
        args.second_pass_ids.write_text("".join(i + "\n" for i in ids2), encoding="utf-8")
        print(f"{len(ids2)} second-pass ids -> {args.second_pass_ids}", file=sys.stderr)
        return 0
    pass2 = None
    stamp_info = None
    if args.maintainer_pass2:
        if maintainer is None:
            ap.error("--maintainer-pass2 needs --maintainer")
        pass2 = load_labels(
            args.maintainer_pass2, items, second_pass_ids(maintainer), "maintainer_pass2"
        )
        try:
            stamp_info = check_pass2_stamps(
                args.maintainer_pass2.read_text(encoding="utf-8").splitlines(),
                pass2,
                file_sha256(args.maintainer),
                registered,
            )
        except ValueError as e:
            raise SystemExit(f"{args.maintainer_pass2}: {e}") from None
        if stamp_info["unstamped"]:
            print(
                f"maintainer_pass2 [{NONREGISTERED}]: {stamp_info['unstamped']} of "
                f"{stamp_info['accepted_records']} records carry no pass1_sha256",
                file=sys.stderr,
            )

    for ls in [*primaries, adjudicator, maintainer, pass2]:
        if ls is None:
            continue
        for p in ls.problems:
            where = f"line {p['line']}" + (f" ({p['id']})" if p["id"] else "")
            print(f"[{ls.name}] {where}: {p['reason']}: {p['detail'] or ''}", file=sys.stderr)
        if args.retry_manifest:
            write_retry_manifest(ls, args.retry_manifest / f"retry_{ls.name}.jsonl")
    if args.retry_manifest:
        print(f"retry manifests -> {args.retry_manifest}", file=sys.stderr)
    if args.disagreements:
        ids = needs_adjudication(key_rows, primaries)
        args.disagreements.write_text("".join(i + "\n" for i in ids), encoding="utf-8")
        print(f"{len(ids)} items need adjudication -> {args.disagreements}", file=sys.stderr)
    if args.validate_only or args.disagreements:
        return 0

    rep = clean_json(
        analyse(
            key_rows,
            primaries,
            adjudicator,
            maintainer,
            mids,
            orders,
            frame,
            maintainer_pass2=pass2,
        )
    )
    if maintainer is not None:
        rep["maintainer_files"] = {
            "mode": "registered" if registered else NONREGISTERED,
            "pass1_sha256": file_sha256(args.maintainer),
            "pass1_validated_form": not pass1_form,
            "pass2_sha256": file_sha256(args.maintainer_pass2) if args.maintainer_pass2 else None,
            "pass2_stamps": stamp_info,
        }
    md = to_markdown(rep)
    if args.json:
        args.json.write_text(
            json.dumps(rep, indent=1, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
