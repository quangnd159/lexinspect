"""Study 3, step 3: size the two suspected lexinspect bugs found in step 2.

Adds a `suspected_bugs` block to `docs/validation/study3-agreement.json`:

1. Words glued by punctuation. When spaCy leaves `last”—he` or
   `was—“impressively”—big` as one token (a dash next to a quote or comma, a
   closing bracket before a letter), lexinspect counts it as one word and
   one diversity type.
2. Digit strings that are not plain numerals (`1914–1918`, `11:00`, `1/4`,
   `3-4`) are not `is_numeric`, so they count as words with 0 syllables and
   stay in the diversity token list, which is meant to exclude numbers.
3. A closing single quote absorbed into the word before it (`‘quoted’` read
   as the word `quoted’`), found by an independent audit after step 2. Counted
   as words ending in a bare apostrophe after a letter other than s; a plural
   possessive (`students’`) is legitimate and not counted.

For each, the minimal reproducing example's actual output, how many corpus
texts are affected, and how much the affected texts' scores move when the
artefact is corrected by a simple split (an estimate, not a proposed fix).
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

from lexinspect import diversity, readability
from lexinspect._text import analyse

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation" / "study3"
OUT = ROOT / "docs" / "validation" / "study3-agreement.json"

# Punctuation that never sits inside a word. A bare en dash between letters
# (`Cretaceous–Paleogene`) is left alone: Wikipedia uses it inside compounds.
GLUE = re.compile(r"(?:--|[—\"“”()\[\],;:!?]|(?<=[\"“”,;:!?])–|–(?=[\"“”]))+")
DIGIT_NONNUMERIC = re.compile(r"\d")


def is_glued(text: str) -> bool:
    """A word whose letters are joined through punctuation that never joins a word."""
    if not any(c.isalpha() for c in text):
        return False
    parts = [p for p in GLUE.split(text) if re.search(r"\w", p)]
    return len(parts) > 1


def split_glued(tok: str) -> list[str]:
    parts = GLUE.split(tok)
    return [p.strip(".'’") for p in parts if re.search(r"[^\W\d_]", p)]


def repro() -> dict:
    t1 = "It was—“impressively”—big, he said “at last”—then left."
    a1 = analyse(t1)
    t2 = "The war lasted from 1914–1918 and the meeting began at 11:00 in 1914."
    a2 = analyse(t2)
    return {
        "glued_words": {
            "input": t1,
            "words": [w.text for w in a1.words],
            "word_count": readability.analyze(t1, analysis=a1)["counts"]["words"],
            "expected_word_count": 10,
            "diversity_tokens": diversity.tokens(a1),
        },
        "digit_strings": {
            "input": t2,
            "words_syllables_numeric": [
                [w.text, readability.word_syllables(w), w.is_numeric] for w in a2.words
            ],
            "diversity_tokens": diversity.tokens(a2),
        },
    }


def main() -> None:
    manifest = [json.loads(x) for x in (CACHE / "manifest.jsonl").read_text("utf-8").splitlines()]
    glued_texts, digit_texts, quote_texts = {}, {}, {}
    mtld_shift, mattr_shift, words_shift = [], [], []
    for m in manifest:
        a = analyse((CACHE / "texts" / f"{m['id']}.txt").read_text("utf-8"))
        glued = [w.text for w in a.words if is_glued(w.text)]
        digits = [
            w.text
            for w in a.words
            if not w.is_numeric
            and DIGIT_NONNUMERIC.search(w.text)
            and readability.word_syllables(w) == 0
        ]
        if digits:
            digit_texts[m["id"]] = digits
        quoted = [
            w.text
            for w in a.words
            if len(w.text) > 1 and w.text[-1] in "'’" and w.text[-2].lower() != "s"
        ]
        if quoted:
            quote_texts[m["id"]] = quoted
        if not glued:
            continue
        glued_texts[m["id"]] = glued
        toks = diversity.tokens(a)
        fixed = [p for t in toks for p in (split_glued(t) if is_glued(t) else [t])]
        words_shift.append(100 * (len(fixed) - len(toks)) / len(toks))
        if len(toks) >= 50:
            mtld_shift.append(
                100 * (diversity.mtld(toks) - diversity.mtld(fixed)) / diversity.mtld(fixed)
            )
            mattr_shift.append(diversity.mattr(toks) - diversity.mattr(fixed))

    def summ(xs):
        if not xs:
            return None
        return {
            "median": round(statistics.median(xs), 3),
            "max_abs": round(max(xs, key=abs), 3),
        }

    by_src = {}
    for tid in glued_texts:
        src = next(m["source"] for m in manifest if m["id"] == tid)
        by_src[src] = by_src.get(src, 0) + 1
    result = json.loads(OUT.read_text("utf-8"))
    result["suspected_bugs"] = {
        "minimal_reproductions": repro(),
        "glued_words": {
            "texts_affected": len(glued_texts),
            "texts_affected_by_source": by_src,
            "glued_words_total": sum(len(v) for v in glued_texts.values()),
            "examples": [w for v in list(glued_texts.values())[:6] for w in v[:2]],
            "effect_if_split_on_affected_texts": {
                "word_count_change_pct": summ(words_shift),
                "mtld_change_pct_lexinspect_vs_split": summ(mtld_shift),
                "mattr_change_abs_lexinspect_vs_split": summ(mattr_shift),
            },
        },
        "digit_strings_zero_syllables": {
            "texts_affected": len(digit_texts),
            "words_total": sum(len(v) for v in digit_texts.values()),
            "examples": sorted({w for v in digit_texts.values() for w in v})[:20],
        },
        "closing_quote_absorbed": {
            "texts_affected": len(quote_texts),
            "words_total": sum(len(v) for v in quote_texts.values()),
            "examples": sorted({w for v in quote_texts.values() for w in v})[:20],
        },
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(result["suspected_bugs"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
