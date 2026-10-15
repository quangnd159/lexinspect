"""Build Phase 2 data files for lexinspect.

Inputs (already downloaded to /tmp/lex2):
  - bnc_coca.json  — lpmi-13 CC0 BNC/COCA 10-band headwords
  - ngsl.csv       — NGSL 1.2 stats (lemma + SFI rank + freq)
  - nawl.csv       — NAWL 1.2 lemmatized (lemma + inflected forms)
  - phrase.txt     — Martinez & Schmitt PHRASE list (textutil-converted)

Outputs into /Users/quangnguyendang/webapps/lexinspect/src/lexinspect/data/.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA_OUT = Path("/Users/quangnguyendang/webapps/lexinspect/src/lexinspect/data")
TMP = Path("/tmp/lex2")


def build_bnc_coca() -> None:
    raw = json.loads((TMP / "bnc_coca.json").read_text())
    bands_sorted = sorted(raw.keys(), key=int)
    bands = {}
    headword_to_band: dict[str, int] = {}
    for b in bands_sorted:
        band_num = int(b) // 1000  # "1000" -> 1, "2000" -> 2
        words = sorted(set(w.strip().lower() for w in raw[b] if w.strip()))
        bands[str(band_num)] = words
        for w in words:
            if w not in headword_to_band:
                headword_to_band[w] = band_num
    out = {
        "source": "Nation, P. BNC/COCA word-family lists (headwords). Mirror: lpmi-13/machine_readable_wordlists (CC0).",
        "version": "BNC/COCA 10-band headwords (CC0 mirror)",
        "license": "CC0-1.0",
        "band_count": len(bands),
        "headword_count": sum(len(v) for v in bands.values()),
        "bands": bands,
    }
    (DATA_OUT / "bnc_coca.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"BNC/COCA: {out['headword_count']} headwords across {out['band_count']} bands")


def build_ngsl() -> None:
    rows = []
    with (TMP / "ngsl.csv").open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            lemma = r["Lemma"].strip().lower()
            if not lemma:
                continue
            rows.append(
                {
                    "lemma": lemma,
                    "rank": int(r["SFI Rank"]),
                    "sfi": float(r["SFI"]),
                    "freq_per_million": float(r["Adjusted Frequency per Million (U)"]),
                }
            )
    out = {
        "source": "Browne, C., Culligan, B., & Phillips, J. (2013). The New General Service List 1.2 (CC-BY-SA 4.0).",
        "version": "NGSL 1.2 stats",
        "license": "CC-BY-SA-4.0",
        "lemma_count": len(rows),
        "lemmas": rows,
    }
    (DATA_OUT / "ngsl.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"NGSL: {len(rows)} lemmas")


def build_nawl() -> None:
    items = []
    with (TMP / "nawl.csv").open() as f:
        for line in f:
            parts = [p.strip().lower() for p in line.split(",") if p.strip()]
            if not parts:
                continue
            items.append({"lemma": parts[0], "forms": sorted(set(parts))})
    out = {
        "source": "Browne, C., Culligan, B., & Phillips, J. (2013). The New Academic Word List 1.2 (CC-BY-SA 4.0).",
        "version": "NAWL 1.2 lemmatized for research",
        "license": "CC-BY-SA-4.0",
        "lemma_count": len(items),
        "lemmas": items,
    }
    (DATA_OUT / "nawl.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"NAWL: {len(items)} lemmas")


def build_phrase() -> None:
    """Parse textutil-converted PHRASE list. Structure per item (8 visible lines):
        rank
        PHRASE
        frequency (int)
        spoken general (* / ** / *** / x)
        written general
        written academic
        example sentence
    Section markers `... end of Nk` between bands.
    """
    text = (TMP / "phrase.txt").read_text()
    lines = [ln.rstrip() for ln in text.splitlines()]

    items = []
    current_k = 1
    i = 0
    n = len(lines)

    # Skip preamble until the first integer rank that begins an entry.
    while i < n:
        ln = lines[i].strip()
        if re.fullmatch(r"\d+", ln) and i + 1 < n and lines[i + 1].strip():
            # Heuristic: a rank line is followed by a non-empty phrase line.
            break
        i += 1

    while i < n:
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        if "end of" in ln and "k" in ln.lower():
            m = re.search(r"end of (\d+)k", ln, re.IGNORECASE)
            if m:
                current_k = int(m.group(1)) + 1
            i += 1
            continue
        if not re.fullmatch(r"\d+", ln):
            i += 1
            continue
        # Found a rank line; collect 8 fields.
        try:
            rank = int(ln)
            phrase = lines[i + 1].strip()
            freq = int(re.sub(r"[^\d]", "", lines[i + 2]))
            spoken = lines[i + 3].strip()
            wgen = lines[i + 4].strip()
            wacad = lines[i + 5].strip()
            example = lines[i + 6].strip()
        except (IndexError, ValueError):
            i += 1
            continue
        items.append(
            {
                "rank": rank,
                "phrase": phrase,
                "k_band": current_k,
                "freq_per_100m": freq,
                "spoken_general": spoken,
                "written_general": wgen,
                "written_academic": wacad,
                "example": example,
            }
        )
        i += 7

    out = {
        "source": "Martinez, R., & Schmitt, N. (2012). A phrasal expressions list. Applied Linguistics, 33(3), 299–320.",
        "version": "PHRASE List (505 items, K1–K5 bands)",
        "license": "Free for educational and research use (no SPDX). Cite Martinez & Schmitt (2012).",
        "item_count": len(items),
        "items": items,
    }
    (DATA_OUT / "phrase.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"PHRASE: {len(items)} items")
    if items:
        from collections import Counter

        bands = Counter(it["k_band"] for it in items)
        print(f"  per K-band: {dict(sorted(bands.items()))}")


if __name__ == "__main__":
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    build_bnc_coca()
    build_ngsl()
    build_nawl()
    build_phrase()
