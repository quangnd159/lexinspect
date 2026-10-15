"""Syllable counting: CMU Pronouncing Dictionary first, a tuned heuristic after.

Every readability formula multiplies by a syllable count, so this is the number
most of the readability tab rests on. The order of preference:

1. The word itself in CMUdict (first listed pronunciation; vowels carry stress
   digits, so syllables = phones ending in a digit).
2. Its spelling variant in CMUdict. CMUdict is American, so British spellings
   (`colour`, `realise`, `programme`) used to miss and fall through to a
   hyphenation dictionary that undercounts short words — `colour` scored 1.
3. An inflectional stem in CMUdict plus the syllables the suffix adds.
4. A rule-based estimate, measured against CMUdict itself (see
   `tests/test_syllables.py`).

The previous implementation (textstat) used Pyphen for step 4. Pyphen is a
*hyphenation* dictionary: it won't break near word edges, so it systematically
misses syllables (`naïve` → 1, `colour` → 1).
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path

from lexinspect._spelling import spelling_variants

_CMU_ZIP = Path(__file__).parent / "data" / "cmudict.zip"


@lru_cache(maxsize=1)
def cmudict() -> dict[str, int]:
    """Lowercase word -> syllable count of its first pronunciation."""
    out: dict[str, int] = {}
    with zipfile.ZipFile(_CMU_ZIP) as zf:
        raw = zf.read("cmudict/cmudict").decode("latin-1")
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        word = parts[0].lower()
        if word in out:  # keep the first pronunciation, as CMUdict orders them
            continue
        out[word] = sum(1 for p in parts[2:] if p[-1].isdigit())
    return out


_VOWELS = "aeiouy"
_VOWEL_RUN = re.compile(r"[aeiouy]+")

# Vowel pairs that are usually pronounced as two syllables (`cre-ate`,
# `ri-ot`, `di-et`). Applied after the run count, which treats them as one.
_HIATUS = re.compile(
    r"(?:(?<![cgstx])i(?:a|o(?!u)|u)|(?<![gq])ua|(?<![gq])uo|eo|ea(?=te|tion|l$|lity|lism|list)|ie(?=t|r$|st|nt))"
)
# `-ism` adds a syllable the vowel-run count misses (`real-is-m`).
_ISM_END = re.compile(r"[^aeiouy]ism$")
# `-bled`, `-ples`, `-tles`: the -le syllable survives the inflection.
_LE_INFLECTED = re.compile(r"[bcdfgkptz]l(?:ed|es)$")
# Silent-e and friends that the vowel-run count over-counts.
_SILENT_E = re.compile(r"[^aeiouy]e$")
_LE_END = re.compile(r"[^aeiouy]le$")  # `table`, `little`: the e is silent but `le` is a syllable
_ED_SILENT = re.compile(r"[^dt]ed$")  # `jumped`, `walked`: no extra syllable
_ES_SILENT = re.compile(r"[^cgsxz]es$|(?<![cgsxz]h)(?<=[^aeiouy])es$")


def _heuristic(word: str) -> int:
    w = word
    if not w:
        return 0
    if len(w) <= 3:
        return max(1, len(_VOWEL_RUN.findall(w)))
    count = len(_VOWEL_RUN.findall(w))
    count += len(_HIATUS.findall(w))
    if w.endswith("e") and not w.endswith(("ee", "ye", "le")) and _SILENT_E.search(w):
        count -= 1
    elif _LE_END.search(w):
        pass  # vowel run already counted `le`'s e; the consonant cluster keeps it a syllable
    if _ISM_END.search(w):
        count += 1
    if _LE_INFLECTED.search(w):
        pass
    elif (
        w.endswith("ed")
        and _ED_SILENT.search(w)
        and count > 1
        or (
            w.endswith("es")
            and not w.endswith(("ies", "ees"))
            and count > 1
            and _ES_SILENT.search(w)
            # `makes`, `hopes` (silent) vs `buses`, `changes` (voiced extra syllable)
            and not re.search(r"(?:[cgsxz]|ch|sh)es$", w)
        )
    ):
        count -= 1
    if w.endswith("ely") and count > 1 and re.search(r"[^aeiouy]ely$", w):
        count -= 1  # `lovely`, `completely`: the e stays silent before -ly
    return max(1, count)


# Inflectional endings: (suffix, minimum stem length, syllables added on top of
# the stem, list of stem reconstructions to try).
_INFLECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("'s", ("",)),
    ("’s", ("",)),
    ("s", ("",)),
    ("es", ("", "e")),
    ("ies", ("y",)),
    ("ed", ("", "e")),
    ("ing", ("", "e")),
    ("ly", ("", "le")),
    ("er", ("", "e")),
    ("est", ("", "e")),
)


def _from_stem(word: str, cmu: dict[str, int]) -> int | None:
    for suffix, rebuilds in _INFLECTIONS:
        if not word.endswith(suffix) or len(word) - len(suffix) < 3:
            continue
        base = word[: -len(suffix)]
        for rebuild in rebuilds:
            stem = base + rebuild
            n = cmu.get(stem)
            if n is None:
                continue
            # How many syllables does the ending add? Compare the full word's
            # heuristic with the stem's heuristic rather than hard-coding, so
            # `jumped` (+0) and `wanted` (+1) both come out right.
            return n + max(0, _heuristic(word) - _heuristic(stem))
    return None


def _clean(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(c for c in word if not unicodedata.combining(c))
    return "".join(c for c in word.lower() if c.isalpha() or c in "'’")


@lru_cache(maxsize=65536)
def count(word: str) -> int:
    """Syllables in a single word. 0 for tokens with no letters."""
    cmu = cmudict()
    raw = word.lower().replace("’", "'")
    if raw in cmu:
        return cmu[raw]
    w = _clean(word).replace("’", "'")
    if not w:
        return 0
    if w in cmu:
        return cmu[w]
    for variant in spelling_variants(w):
        if variant in cmu:
            return cmu[variant]
    stem = _from_stem(w, cmu)
    if stem is not None:
        return stem
    for variant in spelling_variants(w):
        stem = _from_stem(variant, cmu)
        if stem is not None:
            return stem
    return _heuristic(w.replace("'", ""))


def source(word: str) -> str:
    """Which tier answered — for diagnostics and tests, not for output."""
    cmu = cmudict()
    w = _clean(word).replace("’", "'")
    if word.lower() in cmu or w in cmu:
        return "cmudict"
    if any(v in cmu for v in spelling_variants(w)):
        return "variant"
    if _from_stem(w, cmu) is not None:
        return "stem"
    return "heuristic"
