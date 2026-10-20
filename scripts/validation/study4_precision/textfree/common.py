"""Shared pieces of the text-free export: writers, sub-stratum codes, label and item shapes.

Label shapes
------------
The frozen validator (analyse.validate_lines / check_record) reads three text-bearing
things: the label's `note` (word count; for UNSURE the readings before the colon), the
`alt_category` (for PHRASE a listed sense expression or a free gloss) and the item's
`claimed` entry (PHRASE expression and other listed senses). The export replaces each by
a text-free shape that carries exactly what those checks read:

- `note_shape`: null (note null), an integer (the note's whitespace word count), or, for
  an UNSURE record whose note matches the UNSURE pattern, {"unsure": [readings],
  "words": n}; readings that are not labels or category keys become "?".
- `alt_category`: metadiscourse codes are kept as written; any other value becomes a
  token. PHRASE values become `s<i>` (the item's i-th other listed sense), `e` (the
  claimed entry) or `g<j>` (the j-th distinct free gloss written for this item in the
  dataset), padded with `x` to the original word count and in capitals exactly when the
  original was (alt == alt.upper()).
- PHRASE items keep only the word counts of the claimed expression and of each other
  listed sense.

`synth_line` turns a shape back into a record the frozen validator accepts as input; the
export proves for every label file that the validator gives the same result on the
synthetic lines as on the real ones (`verify_labels`).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import analyse

MALFORMED = "#malformed"  # not JSON: the validator's malformed_json, merge_retry's drop
NOT_OBJECT = "[]"
ID_RE = re.compile(r"[0-9a-f]{10}")
LABEL_RE = re.compile(r"[A-Za-z_\- ]{1,40}")
CODE_RE = re.compile(r"\s*[A-Za-z_]{1,40}\s*")
MD_CODES = {
    analyse.norm_sense(c)
    for c in [*analyse.MD_CATEGORIES, *analyse.LABELS["metadiscourse"], *analyse.LABELS["phrase"]]
}


# --- deterministic writers --------------------------------------------------------------


def dump_json(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()


def dump_line(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def dump_jsonl(lines: list[str]) -> bytes:
    return "".join(x + "\n" for x in lines).encode()


def gz(data: bytes) -> bytes:
    """gzip with a fixed header (mtime 0, no file name): deterministic for one zlib."""
    return gzip.compress(data, compresslevel=9, mtime=0)


def read_bytes(path: Path) -> bytes:
    data = Path(path).read_bytes()
    return gzip.decompress(data) if str(path).endswith(".gz") else data


def read_lines(path: Path) -> list[str]:
    """The file's lines (gzip transparent), blank lines kept."""
    return read_bytes(path).decode("utf-8").splitlines()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in read_lines(path) if x.strip()]


def read_json(path: Path) -> Any:
    return json.loads(read_bytes(path))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


# --- sub-stratum codes ------------------------------------------------------------------


class SubstratumCodes:
    """Order-preserving codes for sub-stratum names that embed a marker or PHRASE expression.

    `<stratum>|rest` is kept; `<stratum>|marker=<words>` becomes `<stratum>|marker=m<NNN>`,
    numbered in the sorted order of all original names, so every sort the frozen code does
    (analyse.outcome_subs, accept.compute) visits the sub-strata in the original order."""

    def __init__(self, names: set[str]):
        self.names = sorted(names)
        self.map: dict[str, str] = {}
        marker = [n for n in self.names if n.split("|", 1)[1].startswith("marker=")]
        width = max(3, len(str(len(marker))))
        idx = {n: i for i, n in enumerate(marker)}
        for n in self.names:
            stratum, rest = n.split("|", 1)
            if rest == "rest":
                self.map[n] = n
            elif rest.startswith("marker="):
                self.map[n] = f"{stratum}|marker=m{idx[n]:0{width}d}"
            else:
                raise ValueError(f"unexpected sub-stratum form ({stratum}|...)")
        coded = [self.map[n] for n in self.names]
        if coded != sorted(coded) or len(set(coded)) != len(coded):
            raise ValueError("sub-stratum codes do not preserve the sort order")

    def __call__(self, name: str) -> str:
        return self.map[name]

    def replace_in(self, obj: Any) -> Any:
        """Replace every dict key or string equal to a name, and names inside strings."""
        long_first = sorted((n for n in self.names if n != self.map[n]), key=len, reverse=True)

        def s(x: str) -> str:
            if x in self.map:
                return self.map[x]
            for n in long_first:
                if n in x:
                    x = x.replace(n, self.map[n])
            return x

        def walk(o: Any) -> Any:
            if isinstance(o, dict):
                return {s(k): walk(v) for k, v in o.items()}
            if isinstance(o, list):
                return [walk(v) for v in o]
            return s(o) if isinstance(o, str) else o

        return walk(obj)


# --- item shapes --------------------------------------------------------------------------


def words(s: Any) -> int:
    return len(s.split()) if isinstance(s, str) else 0


def item_shape(it: dict[str, Any]) -> dict[str, Any]:
    claimed = it.get("claimed") or {}
    out: dict[str, Any] = {"id": it["id"], "module": it["module"]}
    if it["module"] == "metadiscourse":
        out["category"] = claimed.get("category")
    else:
        out["expression_words"] = words(claimed.get("expression"))
        out["other_sense_words"] = [
            words(o.get("expression")) for o in claimed.get("other_senses_in_list") or []
        ]
    return out


def _padded(base: str, n: int) -> str:
    return " ".join([base] + ["x"] * (n - 1)) if n > 0 else ""


def claimed_placeholder(shape: dict[str, Any]) -> str | None:
    return _padded("e", shape["expression_words"]) if shape["module"] == "phrase" else None


def pseudo_item(shape: dict[str, Any]) -> dict[str, Any]:
    """An item the frozen validator accepts: the shape's codes and placeholder strings."""
    if shape["module"] == "metadiscourse":
        claimed: dict[str, Any] = {"category": shape["category"]}
    else:
        claimed = {
            "expression": claimed_placeholder(shape),
            "other_senses_in_list": [
                {"expression": _padded(f"s{i}", n)}
                for i, n in enumerate(shape["other_sense_words"])
            ],
        }
    return {"id": shape["id"], "module": shape["module"], "claimed": claimed}


# --- label shapes ---------------------------------------------------------------------------


class Registry:
    """Per-dataset token numbering for free values (glosses, odd labels, unknown ids).

    Collect mode records every value; after freeze() a value's token is its index in the
    sorted list of distinct normalised values of its (kind, id), so the same gloss gets
    the same token in every file and role of the dataset."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], set[str]] = {}
        self.frozen: dict[tuple[str, str], list[str]] | None = None

    def index(self, kind: str, rid: Any, value: str) -> int:
        k = (kind, str(rid))
        if self.frozen is None:
            self.values.setdefault(k, set()).add(value)
            return 0
        return self.frozen[k].index(value)

    def freeze(self) -> None:
        self.frozen = {k: sorted(v) for k, v in self.values.items()}


def _type_placeholder(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | float):
        return v
    return [] if isinstance(v, list) else {}


def _encode_alt(v: Any, item: dict[str, Any] | None, rid: Any, reg: Registry) -> Any:
    if not isinstance(v, str):
        return _type_placeholder(v)
    if not v.strip():
        return v
    ns = analyse.norm_sense(v)
    module = item["module"] if item else None
    if module == "phrase":
        claimed = item.get("claimed") or {}
        listed = [
            analyse.norm_sense(o["expression"]) for o in claimed.get("other_senses_in_list") or []
        ]
        if ns in listed:
            base = f"s{listed.index(ns)}"
        elif ns == analyse.norm_sense(claimed.get("expression") or ""):
            base = "e"
        else:
            base = f"g{reg.index('gloss', rid, ns)}"
        ph = _padded(base, words(v))
        return ph.upper() if v == v.upper() else ph
    if ns in MD_CODES and CODE_RE.fullmatch(v):
        return v
    return f"alt{reg.index('alt', rid, ns)}"


def _encode_note(v: Any, label: Any, module: str | None) -> Any:
    if not isinstance(v, str):
        return _type_placeholder(v)
    n = words(v)
    if label == "UNSURE" and module is not None and v.strip():
        m = analyse.UNSURE_NOTE.match(v)
        if m:
            readings = [r.strip() for r in analyse.UNSURE_SPLIT.split(m.group(1).strip())]
            allowed = set(analyse.LABELS[module]) | (
                set(analyse.MD_CATEGORIES) if module == "metadiscourse" else set()
            )
            if all(r in allowed for r in readings):
                return {"unsure": readings, "words": n}
            return {"unsure": ["?"], "words": n}
    return n


def encode_line(raw: str, items: dict[str, dict[str, Any]], reg: Registry) -> str:
    """One label-file line -> its text-free shape line ("" for a blank line)."""
    s = raw.strip()
    if not s:
        return ""
    try:
        rec = json.loads(s)
    except json.JSONDecodeError:
        return MALFORMED
    if not isinstance(rec, dict):
        return NOT_OBJECT
    out: dict[str, Any] = {}
    rid = rec.get("id")
    item = items.get(rid) if isinstance(rid, str) else None
    if "id" in rec:
        if not isinstance(rid, str):
            out["id"] = _type_placeholder(rid)
        elif rid in items or ID_RE.fullmatch(rid) or rid == "":
            out["id"] = rid
        else:
            out["id"] = f"unknown:{reg.index('unknown', '', rid)}"
    if "label" in rec:
        lab = rec["label"]
        if not isinstance(lab, str):
            out["label"] = _type_placeholder(lab)
        elif LABEL_RE.fullmatch(lab):
            out["label"] = lab
        else:
            out["label"] = f"label{reg.index('label', rid, analyse.norm_sense(lab))}"
    if "alt_category" in rec:
        out["alt_category"] = _encode_alt(rec["alt_category"], item, rid, reg)
    if "note" in rec:
        out["note_shape"] = _encode_note(rec["note"], rec.get("label"), item and item["module"])
    return dump_line(out)


def encode_file(lines: list[str], items: dict[str, dict[str, Any]], reg: Registry) -> list[str]:
    return [encode_line(x, items, reg) for x in lines]


def synth_note(shape: Any) -> Any:
    if isinstance(shape, int) and not isinstance(shape, bool):
        return " ".join(["x"] * shape)
    if isinstance(shape, dict) and "unsure" in shape:
        r = shape["unsure"]
        prefix = " or ".join(r) + ":"
        rest = shape["words"] - sum(words(x) for x in r) - (len(r) - 1)
        return prefix + (" " + " ".join(["x"] * rest) if rest > 0 else "x")
    return shape


def synth_line(line: str) -> str:
    """A text-free shape line -> a label record for the frozen validator."""
    if not line.strip() or line in (MALFORMED, NOT_OBJECT):
        return line
    rec = json.loads(line)
    out = {k: v for k, v in rec.items() if k != "note_shape"}
    if "note_shape" in rec:
        out["note"] = synth_note(rec["note_shape"])
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


# --- proof of equivalence ---------------------------------------------------------------------


def _outcome(ls: analyse.LabelSet, known: set[str]) -> dict[str, Any]:
    def i(x: Any) -> Any:
        return x if x in known else "<unknown>"

    return {
        "summary": ls.summary(),
        "n_lines": ls.n_lines,
        "expected": ls.expected,
        "labels": {
            k: (r["label"], r["alt_category"] if r["label"] == "WRONG_CATEGORY" else None)
            for k, r in sorted(ls.labels.items())
        },
        "problems": [(p["line"], i(p["id"]), p["reason"]) for p in ls.problems],
        "warnings": [(w["line"], i(w["id"]), w["reason"]) for w in ls.warnings],
        "retry": [(r["id"], r["reason"]) for r in ls.retry],
    }


def verify_labels(
    real_lines: list[str],
    shape_lines: list[str],
    items: dict[str, dict[str, Any]],
    pseudo: dict[str, dict[str, Any]],
    expected: list[str] | None,
    name: str,
) -> dict[str, Any]:
    """The frozen validator gives the same result on the real file and on its shapes."""
    real = analyse.validate_lines(real_lines, items, expected, name)
    synth = analyse.validate_lines([synth_line(x) for x in shape_lines], pseudo, expected, name)
    a, b = _outcome(real, set(items)), _outcome(synth, set(items))
    if a != b:
        diff = [k for k in a if a[k] != b[k]]
        raise ValueError(f"{name}: shapes change the validator's result ({diff})")
    for rid in real.labels:  # same canonical duplicate classes, same non-vote status
        if analyse.canonical(real.labels[rid])[0] != analyse.canonical(synth.labels[rid])[0]:
            raise ValueError(f"{name}: {rid} label differs")
    return real.summary()


def label_counts(lines: list[str]) -> Counter:
    return Counter(json.loads(x).get("label") for x in lines if x.startswith("{"))
