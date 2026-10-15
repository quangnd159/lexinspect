"""Build the vocabulary-list data files from their upstream sources.

    uv run python scripts/build_data/build_lists.py SRC_DIR

SRC_DIR must contain the files listed in `SOURCES` below (download commands in
scripts/build_data/README.md). Writes into src/lexinspect/data/. Idempotent.

Replaces the phase-2/3 builders for bnc_coca.json, ngsl.json and cefr.json, and
adds spelling.json. What changed and why:

- bnc_coca.json — was the CC0 headwords-only mirror: 9,998 headwords, no family
  members, so `clearly`, `possibly`, `unclear`, `colour` fell off-list. Now
  Nation's official BNC/COCA 25,000 Level-6 word families (75,679 forms) plus
  his supplementary lists of proper names, marginal words, transparent
  compounds and acronyms (CC BY-SA 4.0).
- ngsl.json — was lemmas only, so British spellings missed. Now carries every
  inflected and UK/US form from the official "lemmatized for teaching" list.
- cefr.json — collapsed multi-POS entries to the lowest level, so *present*
  (noun A1, verb B2) was always A1. Now keeps a level per part of speech, and
  splits slash-variant headwords (`a.m./A.M./am/AM`) into separate keys.
- spelling.json — British <-> American pairs from VarCon (SCOWL), for the
  lookups and syllable counts that need them.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_OUT = Path(__file__).resolve().parents[2] / "src" / "lexinspect" / "data"

SOURCES = {
    "bnc_dir": "BNC_COCA_25000/ (basewrd1.txt … basewrd34.txt, extracted from BNC_COCA_25000.zip)",
    "ngsl_stats": "NGSL_12_stats.csv",
    "ngsl_teach": "NGSL_12_lemmatized_for_teaching.csv",
    "cefrj": "cefrj-vocabulary-profile-1.5.csv",
    "octanove": "octanove-vocabulary-profile-c1c2-1.0.csv",
    "varcon": "varcon.txt",
}

# VarCon "level" is SCOWL's commonness scale (10 = most common, 95 = obscure).
# 70 keeps every variant a learner or an exam text plausibly uses.
VARCON_MAX_LEVEL = 70


def _write(name: str, obj) -> None:
    path = DATA_OUT / name
    path.write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(f"wrote {path.relative_to(DATA_OUT.parents[2])} ({path.stat().st_size // 1024} KB)")


# --- BNC/COCA ------------------------------------------------------------------


def _read_families(path: Path) -> list[tuple[str, list[str]]]:
    """Range format: headword at column 0, members indented, each `WORD 0`."""
    families: list[tuple[str, list[str]]] = []
    for raw in path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        if not raw.strip():
            continue
        word = raw.strip().split()[0].lower()
        if raw[0] in " \t":
            if families:
                families[-1][1].append(word)
        else:
            families.append((word, []))
    return families


def build_bnc_coca(src: Path) -> None:
    d = src / "BNC_COCA_25000"
    bands: dict[str, dict[str, list[str]]] = {}
    for n in range(1, 26):
        bands[str(n)] = {head: members for head, members in _read_families(d / f"basewrd{n}.txt")}
    supplementary = {}
    for n, key in (
        (31, "proper_names"),
        (32, "marginal_words"),
        (33, "transparent_compounds"),
        (34, "acronyms"),
    ):
        fams = _read_families(d / f"basewrd{n}.txt")
        supplementary[key] = sorted({w for head, members in fams for w in (head, *members)})
    _write(
        "bnc_coca.json",
        {
            "source": (
                "Nation, I. S. P. (2017). The BNC/COCA Level 6 word family lists (Version 1.0.0). "
                "Victoria University of Wellington. "
                "https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/vocabulary-lists"
            ),
            "version": "BNC/COCA 25,000 word families (BNC_COCA_25000.zip, SHA-256 ac81c7a6…)",
            "license": "CC-BY-SA-4.0",
            "band_count": 25,
            "family_count": sum(len(b) for b in bands.values()),
            "bands": bands,
            "supplementary": supplementary,
        },
    )


# --- NGSL ----------------------------------------------------------------------


def build_ngsl(src: Path) -> None:
    stats: dict[str, dict] = {}
    with (src / SOURCES["ngsl_stats"]).open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lemma = row["Lemma"].strip().lower()
            if lemma:
                stats[lemma] = {
                    "rank": int(row["SFI Rank"]),
                    "sfi": float(row["SFI"]),
                    "freq_per_million": float(row["Adjusted Frequency per Million (U)"]),
                }
    forms: dict[str, set[str]] = defaultdict(set)
    with (src / SOURCES["ngsl_teach"]).open(encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("##") or not line.strip():
                continue
            cells = [c.strip().lower() for c in line.strip().split(",") if c.strip()]
            forms[cells[0]].update(cells)
    lemmas = []
    for lemma, st in sorted(stats.items(), key=lambda kv: kv[1]["rank"]):
        lemmas.append({"lemma": lemma, **st, "forms": sorted(forms.get(lemma, {lemma}) | {lemma})})
    missing = sorted(set(forms) - set(stats))
    if missing:
        print(
            f"  ngsl: {len(missing)} teaching headwords without stats (kept as forms only): {missing[:8]}"
        )
    _write(
        "ngsl.json",
        {
            "source": "Browne, C., Culligan, B., & Phillips, J. (2013). The New General Service List 1.2.",
            "version": "NGSL 1.2 stats + lemmatized for teaching (UK/US forms)",
            "license": "CC-BY-SA-4.0",
            "lemma_count": len(lemmas),
            "lemmas": lemmas,
        },
    )


# --- CEFR ----------------------------------------------------------------------

_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _cefr_rows(path: Path, source: str):
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            level = (row.get("CEFR") or "").strip().upper()
            pos = (row.get("pos") or "").strip().lower()
            if level not in _LEVELS:
                continue
            for head in re.split(r"\s*/\s*", row["headword"].strip()):
                head = head.strip().lower()
                if head:
                    yield head, pos, level, source


def build_cefr(src: Path) -> None:
    entries: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for path, source in (
        (src / SOURCES["cefrj"], "cefrj"),
        (src / SOURCES["octanove"], "octanove"),
    ):
        for head, pos, level, s in _cefr_rows(path, source):
            prev = entries[head].get(pos)
            # Same headword + POS listed twice: keep the lower level.
            if prev is None or _LEVELS.index(level) < _LEVELS.index(prev[0]):
                entries[head][pos] = (level, s)
    lemmas = [
        {
            "lemma": head,
            "level": min((lv for lv, _ in by_pos.values()), key=_LEVELS.index),
            "by_pos": {pos: lv for pos, (lv, _) in sorted(by_pos.items())},
            "source": sorted({s for _, s in by_pos.values()}),
        }
        for head, by_pos in sorted(entries.items())
    ]
    per_level = {lv: sum(1 for x in lemmas if x["level"] == lv) for lv in _LEVELS}
    _write(
        "cefr.json",
        {
            "source": "CEFR-J Wordlist 1.5 (Tono, TUFS) + Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs).",
            "version": "CEFR-J 1.5 + Octanove 1.0, per-POS levels",
            "license": "CEFR-J: free for research and commercial use with citation; Octanove: CC-BY-SA-4.0.",
            "level_order": _LEVELS,
            "lemma_count": len(lemmas),
            "per_level_count": per_level,
            "lemmas": lemmas,
        },
    )


# --- spelling ------------------------------------------------------------------

_VARCON_LINE = re.compile(r"^([A-Za-z ]+): (.+)$")


def build_spelling(src: Path) -> None:
    gb_to_us: dict[str, str] = {}
    us_to_gb: dict[str, str] = {}
    level = 100
    for line in (src / SOURCES["varcon"]).read_text(encoding="latin-1").splitlines():
        if line.startswith("#"):
            m = re.search(r"\(level (\d+)\)", line)
            level = int(m.group(1)) if m else 100
            continue
        if not line.strip() or level > VARCON_MAX_LEVEL:
            continue
        # e.g. "A Z: colorize / B: colourise" — tags before the colon name the
        # dialects (A = American, B = British -ise, Z = British -ize, C =
        # Canadian, D = Australian); a lower-case `v` marks a variant spelling.
        primary_us = primary_gb = None
        for chunk in line.split(" / "):
            tags, _, word = chunk.partition(": ")
            word = word.strip().lower()
            if not word or " " in word:
                continue
            tagset = tags.split()
            if "A" in tagset and primary_us is None:
                primary_us = word
            if "B" in tagset and primary_gb is None:
                primary_gb = word
        if primary_us and primary_gb and primary_us != primary_gb:
            gb_to_us.setdefault(primary_gb, primary_us)
            us_to_gb.setdefault(primary_us, primary_gb)
    _write(
        "spelling.json",
        {
            "source": "VarCon (Variant Conversion Info), SCOWL / en-wl. Copyright 2000-2020 Kevin Atkinson and Benjamin Titze.",
            "license": "MIT-like (VarCon copyright notice); see SOURCES.md",
            "max_level": VARCON_MAX_LEVEL,
            "gb_to_us": dict(sorted(gb_to_us.items())),
            "us_to_gb": dict(sorted(us_to_gb.items())),
        },
    )


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    build_bnc_coca(src)
    build_ngsl(src)
    build_cefr(src)
    build_spelling(src)


if __name__ == "__main__":
    main()
