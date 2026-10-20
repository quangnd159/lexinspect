"""Guard: the text-free export carries no text.

    uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/guard.py \\
        [--dir docs/validation/study4-textfree] [--fragments F]

Checks every file of the folder (gzip contents decompressed):
1. keys: no JSON key that holds text in the private files (`context`, `payload`, `raw`,
   `surface`, `claimed`, `note`, `gloss`, `example`, ...; `phrase`, `sense` and `marker`
   when their value is a string);
2. source and guideline text: no substring of 30 or more characters of any archived source
   text (development, 0.4.0 rebuild, both fix-check rounds), of the guidelines, of any copy
   of the PHRASE sense inventory, or of a gloss or example in src/lexinspect/data/phrase.json.
   Both the raw file and every decoded JSON string are scanned;
3. PHRASE headwords: no multiword PHRASE List expression (phrase.json), case-sensitive;
4. restricted fragments: the fix-check harness's own check (fixcheck/scan.py, `count`) with
   the private fragment file, on the raw and the decompressed bytes.
Output is file names, offsets and counts only; matched text is never printed.
Exit 0 = clean; 1 = something matched; 2 = the check could not be completed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
from fixcheck import scan  # noqa: E402

REPO = HERE.parents[3]
HOME = Path.home()
CACHE = REPO / ".cache" / "validation"
PRIVATE = HOME / "lexinspect-private"
OUT = REPO / "docs" / "validation" / "study4-textfree"
FRAGMENTS = PRIVATE / "study4-fix040" / "round2" / "inventory_fragments.txt"
K = 30
SEP = "\x00"
FORBIDDEN_KEYS = {
    "context",
    "payload",
    "raw",
    "surface",
    "claimed",
    "note",
    "notes",
    "text",
    "sentence",
    "gloss",
    "glosses",
    "example",
    "examples",
    "expression",
    "other_senses_in_list",
    "also_possible",
    "marker_key",
    "title",
    "authors",
    "journal",
    "prompt",
    "transcript",
    "detail",
}
STRING_VALUED_KEYS = {"phrase", "sense", "marker"}  # module names are keys too


def default_corpora() -> list[Path]:
    """Every archived source text, the guidelines and every inventory copy found."""
    globs = [
        (CACHE / "study4" / "texts", "*.txt"),
        (CACHE / "study4_v040" / "texts", "*.txt"),
        (PRIVATE / "study4-pilot040" / "selection" / "build" / "texts", "*.txt"),
        (REPO / "docs" / "validation" / "study4-fix040" / "round1" / "collect" / "texts", "*.txt"),
        (REPO / "docs" / "validation" / "study4-fix040" / "round2" / "collect" / "texts", "*.txt"),
        (PRIVATE / "study4-fix040" / "round1" / "materials", "*.md"),
        (PRIVATE / "study4-fix040" / "round2" / "materials", "*.md"),
    ]
    out = [p for d, g in globs if d.is_dir() for p in sorted(d.glob(g))]
    out += [
        p
        for p in (
            REPO / "docs" / "validation" / "study4-guidelines.md",
            CACHE / "study4" / "phrase_sense_inventory.md",
        )
        if p.is_file()
    ]
    return out


def phrase_data() -> tuple[list[str], list[str]]:
    """(glosses and examples, multiword headwords) from src/lexinspect/data/phrase.json."""
    d = json.loads((REPO / "src" / "lexinspect" / "data" / "phrase.json").read_text("utf-8"))
    strings, heads = [], set()
    for it in d["items"]:
        for k in ("example", "sense"):
            if isinstance(it.get(k), str):
                strings.append(it[k])
        if isinstance(it.get("phrase"), str) and " " in it["phrase"].strip():
            heads.add(it["phrase"].strip())
    return strings, sorted(heads)


# --- rolling hashes --------------------------------------------------------------------------


def _codes(s: str) -> np.ndarray:
    return np.frombuffer(s.encode("utf-32-le"), dtype=np.uint32).astype(np.uint64)


def window_hashes(s: str, k: int = K) -> np.ndarray:
    """A 64-bit polynomial hash of every k-character window of s (wrapping arithmetic)."""
    a = _codes(s)
    n = len(a) - k + 1
    if n <= 0:
        return np.zeros(0, dtype=np.uint64)
    h = np.zeros(n, dtype=np.uint64)
    b = np.uint64(1_000_003)
    for j in range(k):
        h = h * b + a[j : j + n]
    return h


class Corpus:
    def __init__(self, docs: Iterable[str]):
        uniq = sorted(set(docs))
        self.docs = uniq
        hs = [window_hashes(d) for d in uniq]
        self.hashes = np.unique(np.concatenate(hs)) if hs else np.zeros(0, dtype=np.uint64)

    def matches(self, s: str) -> list[tuple[int, int]]:
        """(offset, length) of every maximal run of s covered by shared k-windows."""
        h = window_hashes(s)
        if not len(h) or not len(self.hashes):
            return []
        idx = np.searchsorted(self.hashes, h).clip(0, len(self.hashes) - 1)
        cand = np.nonzero(self.hashes[idx] == h)[0]
        hits = [
            int(i)
            for i in cand
            if SEP not in (w := s[i : i + K]) and any(w in d for d in self.docs)
        ]
        runs: list[tuple[int, int]] = []
        for i in hits:
            if runs and i <= runs[-1][0] + runs[-1][1] - K + 1:
                runs[-1] = (runs[-1][0], i + K - runs[-1][0])
            else:
                runs.append((i, K))
        return runs


def load_corpus(paths: list[Path], extra: list[str] | None = None) -> Corpus:
    return Corpus([p.read_text(encoding="utf-8") for p in paths] + list(extra or []))


# --- scanning --------------------------------------------------------------------------------


def _json_docs(rel: str, text: str) -> list[Any]:
    name = rel.removesuffix(".gz")
    if name.endswith(".jsonl"):
        return [json.loads(x) for x in text.splitlines() if x.strip().startswith(("{", "["))]
    if name.endswith(".json"):
        return [json.loads(text)]
    return []


def _walk(o: Any, keys: list[tuple[str, Any]], strings: list[str]) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            keys.append((k, v))
            strings.append(k)
            _walk(v, keys, strings)
    elif isinstance(o, list):
        for v in o:
            _walk(v, keys, strings)
    elif isinstance(o, str):
        strings.append(o)


def _bad_key(k: str, v: Any) -> bool:
    if k in FORBIDDEN_KEYS:
        return True
    if k in STRING_VALUED_KEYS:
        return isinstance(v, str) or (isinstance(v, list) and any(isinstance(x, str) for x in v))
    return False


def scan_files(
    files: dict[str, bytes],
    corpus: Corpus | list[Path],
    headwords: list[str] | None = None,
    fragments: Path | None = FRAGMENTS,
) -> dict[str, Any]:
    """Scan in-memory files {relative path: bytes}. Returns counts and findings."""
    if not isinstance(corpus, Corpus):
        strings, heads = phrase_data()
        corpus = load_corpus(corpus, strings)
        headwords = heads if headwords is None else headwords
    headwords = headwords or []
    frags = scan.load_fragments(fragments) if fragments is not None else None
    findings: list[dict[str, Any]] = []
    for rel in sorted(files):
        data = files[rel]
        plain = gzip.decompress(data) if rel.endswith(".gz") else data
        text = plain.decode("utf-8")
        keys: list[tuple[str, Any]] = []
        strings: list[str] = []
        for doc in _json_docs(rel, text):
            _walk(doc, keys, strings)
        bad = sorted({k for k, v in keys if _bad_key(k, v)})
        if bad:
            findings.append({"file": rel, "check": "keys", "detail": f"text-bearing keys {bad}"})
        for where, s in (("raw", text), ("strings", SEP.join(strings))):
            for off, n in corpus.matches(s):
                findings.append(
                    {
                        "file": rel,
                        "check": "source_text",
                        "detail": f"{where} offset {off}, {n} chars",
                    }
                )
        hw = sum(1 for h in headwords if h in text)
        if hw:
            findings.append({"file": rel, "check": "phrase_headwords", "detail": f"{hw} headwords"})
        if frags is not None:
            n = max(scan.count(data, frags), scan.count(plain, frags))
            if n:
                findings.append(
                    {"file": rel, "check": "restricted_fragments", "detail": f"{n} fragments"}
                )
    return {
        "ok": not findings,
        "files": len(files),
        "corpus_documents": len(corpus.docs),
        "corpus_windows": int(len(corpus.hashes)),
        "headwords": len(headwords),
        "fragments": None if frags is None else len(frags),
        "findings": findings,
    }


def report(res: dict[str, Any]) -> str:
    lines = [
        f"guard: {res['files']} files; corpus {res['corpus_documents']} documents, "
        f"{res['corpus_windows']:,} distinct {K}-character windows; {res['headwords']} PHRASE "
        f"headwords; {res['fragments']} restricted fragments"
    ]
    lines += [f"  FOUND {f['check']}: {f['file']} ({f['detail']})" for f in res["findings"]]
    lines.append("guard: clean" if res["ok"] else f"guard: {len(res['findings'])} findings")
    return "\n".join(lines)


def read_folder(d: Path) -> dict[str, bytes]:
    return {
        p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, default=OUT)
    ap.add_argument("--fragments", type=Path, default=FRAGMENTS)
    args = ap.parse_args(argv)
    try:
        corpora = default_corpora()
        if not corpora:
            raise FileNotFoundError("no source text or guideline file found")
        res = scan_files(read_folder(args.dir), corpora, fragments=args.fragments)
    except (OSError, scan.ScanError) as e:
        print(f"guard: NOT COMPLETED: {e}", file=sys.stderr)
        return 2
    print(report(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
