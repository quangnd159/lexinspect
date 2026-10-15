"""Spelling-error detection (British or American English).

Hunspell (via `spylls`, a pure-Python port) with LibreOffice's en_GB / en_US
dictionaries, vendored under data/hunspell/. What's checked is lexinspect's
*words*, not spaCy's fragments: the old module checked `children's` as
`children` + `'s` and `don't` as `do` + `n't`, and reported `'s`, `n't` and
`Dr.` as spelling errors in almost every text. Hunspell knows contractions,
possessives and hyphenated compounds as wholes; when a whole compound isn't
listed, it's accepted if each part is.

A word Hunspell rejects is sorted into one of three buckets — only the first
counts toward the error rate:

- **errors** — not a word in either variant. Each comes with suggestions
  (`_suggest`: edit-distance candidates from Nation's word families, valid in
  the chosen variant, ranked by distance and frequency).
- **variant_mismatches** — correct in the *other* variety (`color` in British
  mode, `colour` in American). Mixing varieties is a common examiner comment,
  so these are reported with the variant-appropriate spelling, not as errors.
- **unknown_names** — capitalised words that aren't in the dictionary but are
  used as names: tagged as proper nouns and not only seen at the start of a
  sentence, or written in capitals (acronyms). Hunspell can't know every name,
  and a misspelt word at the start of a sentence still counts as an error.

Numerals, URLs, emails and abbreviations with internal full stops (`e.g.`,
`U.S.`) are not checked.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from lexinspect import _suggest
from lexinspect._spelling import spelling_variants
from lexinspect._text import Analysis, Word, ensure

VALID_VARIANTS: tuple[str, ...] = ("gb", "us")
SUGGEST_LIMIT = 40  # distinct errors that get suggestions per request

CAVEAT = (
    "Hunspell-based detection: it flags words its dictionary doesn't contain, so rare "
    "technical terms and neologisms can appear as errors, and a real word used wrongly "
    "(their/there) is not caught. Capitalised words used as names are listed separately, "
    "not counted as errors. Dictionaries: LibreOffice English (en_GB: LGPL; en_US: SCOWL "
    "wordlist, Ispell BSD affix file)."
)

DICTIONARY_LICENCE = (
    "LibreOffice English. en_GB: wordlist and affix file (David Bartlett, Andrew Brown) "
    "under the LGPL. en_US: wordlist from SCOWL by Kevin Atkinson (permissive SCOWL "
    "licence); affix file from Geoff Kuenning's Ispell (BSD). "
    "Mirror: github.com/LibreOffice/dictionaries."
)


class ErrorsExtraNotInstalled(RuntimeError):
    """Raised when spylls is missing (it's a base dependency; this is a broken install)."""


class DictionaryFetchError(RuntimeError):
    """Raised when a bundled Hunspell dictionary can't be loaded."""


def _bundled_base(variant: str) -> Path:
    return Path(__file__).parent / "data" / "hunspell" / f"en_{variant.upper()}"


@lru_cache(maxsize=2)
def _dictionary(variant: str):
    if variant not in VALID_VARIANTS:
        raise ValueError(f"variant must be one of {VALID_VARIANTS}, got {variant!r}")
    try:
        from spylls.hunspell import Dictionary
    except ImportError as e:
        raise ErrorsExtraNotInstalled(
            "spylls is missing; reinstall dependencies with `uv sync`."
        ) from e
    base = _bundled_base(variant)
    try:
        return Dictionary.from_files(str(base))
    except Exception as e:  # spylls raises a variety of internal errors
        print(f"[lexinspect] failed to load {base}: {e}", file=sys.stderr)
        raise DictionaryFetchError(f"Failed to load the en_{variant.upper()} dictionary.") from e


_ABBREVIATION = re.compile(r"^(?:[A-Za-z]\.){2,}$|^[A-Za-z]{1,4}\.$")
_APOS = str.maketrans({"’": "'", "ʼ": "'"})


def _candidates(word: Word) -> list[str]:
    """Forms to try, most faithful first."""
    text = word.text.translate(_APOS)
    forms = [text]
    if text.endswith("'"):
        forms.append(text[:-1])  # James' -> James
    return forms


def _accepted(dic, word: Word) -> bool:
    for form in _candidates(word):
        if dic.lookup(form):
            return True
    parts = [t.text.translate(_APOS) for t in word.tokens if any(c.isalpha() for c in t.text)]
    hosts = [p for p in parts if not p.startswith("'") and p.lower() != "n't"]
    if len(parts) > 1 and hosts:
        # Whole compound unknown: accept if every part is a word (`climate-related`).
        return all(dic.lookup(p) for p in hosts)
    return False


def _common_word_typo(word: Word, dic) -> bool:
    """`Goverment` mid-sentence: one edit from a very common word, and no proper
    noun beside it. Real surnames that sit one letter from a common word
    (`Browne`) almost always travel with a title or first name, which keeps
    them in names."""
    low = word.text.lower()
    if len(low) < 6 or not low.isascii():
        return False
    first, last = word.tokens[0], word.tokens[-1]
    for nb in (
        first.nbor(-1) if first.i > 0 else None,
        last.nbor(1) if last.i + 1 < len(last.doc) else None,
    ):
        if nb is not None and nb.text[:1].isupper() and nb.pos_ == "PROPN":
            return False
    vocab = _suggest._vocab()
    return any(vocab.get(c, 99) <= 2 and dic.lookup(c) for c in _suggest._edits1(low) if c != low)


def _skip(word: Word) -> bool:
    text = word.text
    # Words with digits in them (`mp3`, `CO2`, `R²`) are codes and symbols, skipped
    # the way word processors skip them by default.
    if word.is_numeric or not any(c.isalpha() for c in text) or any(c.isdigit() for c in text):
        return True
    t = word.tokens[0]
    if t.like_url or t.like_email:
        return True
    return bool(_ABBREVIATION.match(text)) and len(word.tokens) == 1


def analyze(text: str, *, variant: str = "gb", analysis: Analysis | None = None) -> dict[str, Any]:
    if variant not in VALID_VARIANTS:
        raise ValueError(f"variant must be one of {VALID_VARIANTS}, got {variant!r}")
    dic = _dictionary(variant)
    other = _dictionary("us" if variant == "gb" else "gb")
    a = ensure(text, analysis)

    # Capitalised forms seen somewhere other than sentence-initial position.
    # "Sentence-initial" is generous: spaCy's boundary, or anything right after
    # `.`/`!`/`?` — a sentence after `U.S.` can be merged into the previous one,
    # and its misspelt first word must not pass for a name.
    sentence_starts = {s[0].start for s in a.sentences if s}
    for w in a.words:
        prev = w.tokens[0].nbor(-1) if w.start > 0 else None
        while prev is not None and prev.is_space and prev.i > 0:
            prev = prev.nbor(-1)
        if prev is None or prev.text.endswith((".", "!", "?", ":", '"', "“", "”")):
            sentence_starts.add(w.start)
    capitalised_midsentence = {
        w.text for w in a.words if w.text[:1].isupper() and w.start not in sentence_starts
    }

    errors: Counter[str] = Counter()
    mismatches: Counter[str] = Counter()
    names: Counter[str] = Counter()
    spans: dict[str, list[list[int]]] = defaultdict(list)
    checked = 0

    for w in a.words:
        if _skip(w):
            continue
        checked += 1
        if _accepted(dic, w):
            continue
        start = w.tokens[0].idx
        span = [start, start + len(w.text)]
        if _accepted(other, w):
            mismatches[w.text] += 1
        elif (w.text.isupper() and len(w.text) > 1) or (
            w.text in capitalised_midsentence
            and (w.is_proper or w.start not in sentence_starts)
            and not _common_word_typo(w, dic)
        ):
            names[w.text] += 1
        else:
            errors[w.text] += 1
        spans[w.text].append(span)

    error_list = []
    for i, (surface, count) in enumerate(sorted(errors.items(), key=lambda kv: (-kv[1], kv[0]))):
        error_list.append(
            {
                "surface": surface,
                "count": count,
                "suggestions": _suggest.suggest(surface, dic) if i < SUGGEST_LIMIT else [],
                "spans": spans[surface],
            }
        )

    mismatch_list = []
    for surface, count in sorted(mismatches.items(), key=lambda kv: (-kv[1], kv[0])):
        fixes = [v for v in spelling_variants(surface.lower()) if dic.lookup(v)]
        mismatch_list.append(
            {
                "surface": surface,
                "count": count,
                "suggestions": [_suggest._restore_case(surface, f) for f in fixes[:3]],
                "spans": spans[surface],
            }
        )

    total = sum(errors.values())
    n_sent = a.sentence_count
    return {
        "variant": variant,
        "counts": {
            "tokens_checked": checked,
            "sentences": n_sent,
            "errors_total": total,
            "unique_errors": len(errors),
            "variant_mismatches": sum(mismatches.values()),
            "unknown_names": sum(names.values()),
        },
        "rates": {
            "errors_per_sentence": _ratio(total, n_sent),
            "errors_per_100_words": _ratio(total * 100, checked),
        },
        "errors": error_list,
        "variant_mismatches": mismatch_list,
        "unknown_names": [
            {"surface": s, "count": c, "spans": spans[s]} for s, c in names.most_common()
        ],
        "dictionary": {
            "variant": variant,
            "source": f"LibreOffice en_{variant.upper()}.aff/.dic",
            "licence": DICTIONARY_LICENCE,
        },
        "caveat": CAVEAT,
    }


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def warm() -> None:
    _dictionary("gb")
    _dictionary("us")
    _suggest._vocab()
