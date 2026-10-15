"""Build CEFR data file for lexinspect Phase 3.

Inputs (already in /tmp/lex3):
  - cefrj.csv      — CEFR-J Vocabulary Profile 1.5 (A1–B2)
  - octanove.csv   — Octanove Vocabulary Profile C1/C2 1.0
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

DATA_OUT = Path(__file__).resolve().parents[2] / "src" / "lexinspect" / "data"
TMP = Path("/tmp/lex3")
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}


def _split_headword(hw: str) -> list[str]:
    """CEFR-J groups variants like 'a.m./A.M./am/AM' — explode them."""
    parts = re.split(r"[/,]", hw)
    out = []
    for p in parts:
        p = p.strip().lower()
        # drop leading 'to ' from infinitives, drop parenthetical glosses
        p = re.sub(r"\([^)]*\)", "", p).strip()
        if p.startswith("to "):
            p = p[3:].strip()
        if p and " " not in p:
            out.append(p)
    return out


def build() -> None:
    entries: dict[str, dict] = {}
    pos_counts: Counter[str] = Counter()

    # CEFR-J 1.5 (A1–B2)
    with (TMP / "cefrj.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            level = (row.get("CEFR") or "").strip().upper()
            if level not in LEVEL_RANK:
                continue
            pos = (row.get("pos") or "").strip().lower()
            for hw in _split_headword(row.get("headword", "")):
                _record(entries, hw, level, pos, "cefrj")
                pos_counts[pos] += 1

    # Octanove C1/C2 1.0
    with (TMP / "octanove.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            level = (row.get("CEFR") or "").strip().upper()
            if level not in LEVEL_RANK:
                continue
            pos = (row.get("pos") or "").strip().lower()
            for hw in _split_headword(row.get("headword", "")):
                _record(entries, hw, level, pos, "octanove")

    per_level = Counter(e["level"] for e in entries.values())
    out = {
        "source": "CEFR-J Wordlist 1.5 (Tono, TUFS) + Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs).",
        "version": "CEFR-J 1.5 + Octanove 1.0",
        "license": "CEFR-J: free for research and commercial use with citation; Octanove: CC-BY-SA-4.0.",
        "level_order": LEVEL_ORDER,
        "lemma_count": len(entries),
        "per_level_count": {lvl: per_level.get(lvl, 0) for lvl in LEVEL_ORDER},
        "lemmas": [
            {"lemma": lemma, "level": e["level"], "pos": e["pos"], "source": e["source"]}
            for lemma, e in sorted(entries.items())
        ],
    }
    (DATA_OUT / "cefr.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"CEFR: {out['lemma_count']} lemmas")
    print(f"  per level: {out['per_level_count']}")


def _record(entries: dict, lemma: str, level: str, pos: str, src: str) -> None:
    """Lowest level wins when a lemma is annotated at multiple levels (across POS)."""
    cur = entries.get(lemma)
    if cur is None or LEVEL_RANK[level] < LEVEL_RANK[cur["level"]]:
        entries[lemma] = {"level": level, "pos": pos, "source": src}


if __name__ == "__main__":
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    build()
