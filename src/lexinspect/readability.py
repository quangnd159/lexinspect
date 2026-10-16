"""Readability formulas, computed on lexinspect's own word/sentence/syllable counts.

This used to wrap textstat. Three things made that untenable for a tool whose
numbers people act on:

- **Counts disagreed with the rest of the app.** textstat splits sentences on
  every `.`/`!`/`?` (so `Dr.` and `U.S.` end sentences) and then silently drops
  any sentence of two words or fewer (`I agree.` vanished). Its word count was a
  different tokeniser again. Every formula below is a function of words,
  sentences and syllables, so those disagreements went straight into the scores.
- **Some definitions departed from the published formulas.** Coleman–Liau used
  0.058 for the letters coefficient instead of 0.0588. Dale–Chall counted
  inflections of familiar words (`books`, `played`) and proper names as
  unfamiliar, which the Dale–Chall counting rules explicitly don't. Gunning Fog
  counted every 3+ syllable word, including the proper nouns, compounds and
  `-ed`/`-es`/`-ing` forms Gunning excluded.
- **It cached every text it saw** (an LRU keyed on the full input, per function,
  across ~30 functions), which on a long-lived server is memory held for nothing.

Each formula below cites its definition. All of them are only meaningful on
running prose of reasonable length; `reliability` says when a score shouldn't be
leaned on.
"""

from __future__ import annotations

import math
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect import _syllables
from lexinspect._text import Analysis, Word, ensure, is_clitic

# Brysbaert (2019), "How many words do we read per minute?", J. Memory and
# Language 109: 238 wpm is the mean silent reading rate for English non-fiction.
READING_WPM = 238

# Below these sizes a formula is still computed, but flagged. SMOG was normed
# on 30-sentence samples (McLaughlin 1969); every formula here was fitted on
# passages of 100+ words.
MIN_WORDS_RELIABLE = 100
MIN_SENTENCES_SMOG = 30


@lru_cache(maxsize=1)
def _easy_words() -> frozenset[str]:
    raw = (
        resources.files("lexinspect.data").joinpath("dale_chall_easy_words.txt").read_text("utf-8")
    )
    return frozenset(w.strip().lower() for w in raw.splitlines() if w.strip())


# --- per-word measures -------------------------------------------------------


def _parts(word: Word) -> list:
    """The alphabetic parts of a word: no clitics, no hyphens."""
    return [t for t in word.tokens if not is_clitic(t) and any(c.isalpha() for c in t.text)]


_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _say_int(n: int) -> list[str]:
    if n == 0:
        return ["zero"]
    out: list[str] = []
    for value, name in ((10**9, "billion"), (10**6, "million"), (1000, "thousand")):
        if n >= value:
            out += _say_int(n // value) + [name]
            n %= value
    if n >= 100:
        out += [_ONES[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        out.append(_TENS[n // 10])
        n %= 10
    if n:
        out.append(_ONES[n])
    return out


def _numeral_syllables(text: str) -> int:
    """Syllables of a numeral as read aloud: `1,500` -> one thousand five hundred.

    Readability formulas count syllables as spoken. Pure integers are spelled
    out; anything else (decimals, ordinals, percentages) is approximated by
    reading each digit group, which is how it would be spoken digit by digit.
    """
    digits = "".join(c for c in text if c.isdigit() or c == ".")
    if not digits:
        return 1
    # `3.1.2` (a section number, a version, an IP address) is read
    # "three point one point two": every group after a dot is a fraction.
    whole, *fracs = digits.split(".")
    total = 0
    if whole:
        n = int(whole)
        # Four-digit years are read in pairs: 1987 -> nineteen eighty-seven.
        if len(whole) == 4 and 1100 <= n <= 2099 and n % 100 != 0 and not (2000 <= n <= 2009):
            words = _say_int(n // 100) + _say_int(n % 100)
        else:
            words = _say_int(n) if n < 10**12 else ["number"] * len(whole)
        total += sum(_syllables.count(w) for w in words)
    for frac in fracs:
        if frac:
            total += 1 + sum(_syllables.count(_ONES[int(d)] or "zero") for d in frac)  # "point ..."
    return max(1, total)


def word_syllables(word: Word) -> int:
    if word.is_numeric:
        n = _numeral_syllables(word.text)
        # `%` is its own token, never part of the word: `50%` is read "fifty per cent".
        last = word.tokens[-1]
        if last.i + 1 < len(last.doc) and last.nbor(1).text == "%" and not last.whitespace_:
            n += 2
        return n
    parts = _parts(word)
    if not parts:
        return 0
    # Contractions are syllabified whole when CMUdict knows them (`don't` = 1).
    whole = word.lower
    if "-" not in whole and whole in _syllables.cmudict():
        return _syllables.cmudict()[whole]
    return sum(_syllables.count(t.text) for t in parts)


def _letters(word: Word) -> int:
    return sum(1 for c in word.text if c.isalnum())


def _is_familiar(word: Word) -> bool:
    """Dale–Chall familiarity (Chall & Dale 1995 counting rules).

    Familiar: on the list; a regular inflection of a listed word (-s, -es, -ed,
    -ing, -er, -est); a proper name; a numeral; a hyphenated compound whose
    parts are all familiar.
    """
    if word.is_numeric or word.is_proper:
        return True
    easy = _easy_words()
    parts = _parts(word)
    if not parts:
        return True
    for t in parts:
        low = t.lower_
        if low in easy or t.lemma_.lower() in easy:
            continue
        if low in ("ca", "wo", "sha"):
            continue
        return False
    return True


_FOG_SUFFIXES = ("es", "ed", "ing")


def _is_fog_complex(word: Word, syllables: int) -> bool:
    """Gunning (1952) "hard words": three or more syllables, except proper
    nouns, hyphenated compounds, and words that reach three syllables only by
    adding -es, -ed or -ing."""
    if syllables < 3 or word.is_numeric or word.is_proper or word.is_hyphenated:
        return False
    low = word.lower
    if low.endswith(_FOG_SUFFIXES):
        parts = _parts(word)
        if parts:
            lemma = parts[-1].lemma_.lower()
            if lemma != low and _syllables.count(lemma) < 3:
                return False
    return True


# --- formulas ----------------------------------------------------------------


def _linsear_write(analysis: Analysis, syll: dict[int, int]) -> float:
    """Linsear Write (O'Hayre 1966): on a 100-word sample, easy words (≤2
    syllables) score 1 and hard words (≥3) score 3; divide by the sample's
    sentences; then halve, subtracting 2 first if the result is ≤ 20."""
    sample_ids: set[int] = set()
    easy = hard = 0
    for w in analysis.words:
        if len(sample_ids) >= 100:
            break
        sample_ids.add(id(w))
        if syll[id(w)] >= 3:
            hard += 1
        else:
            easy += 1
    if not sample_ids:
        return 0.0
    # Sentences touched by the sample; the last may be partial, which counts
    # proportionally rather than as a whole sentence.
    sentences = 0.0
    for sent in analysis.sentences:
        inside = sum(1 for w in sent if id(w) in sample_ids)
        if inside:
            sentences += inside / len(sent) if inside < len(sent) else 1
    r = (easy + 3 * hard) / max(sentences, 1e-9)
    return (r / 2) if r > 20 else (r - 2) / 2


def _dale_chall_grade(raw: float) -> float:
    """Chall & Dale (1995) raw score -> grade level (midpoint of each band)."""
    for ceiling, grade in (
        (5.0, 4.0),
        (6.0, 5.5),
        (7.0, 7.5),
        (8.0, 9.5),
        (9.0, 11.5),
        (10.0, 14.0),
    ):
        if raw < ceiling:
            return grade
    return 16.0


def _flesch_grade(fre: float) -> float:
    """Flesch (1948) reading-ease band -> school grade (midpoint of each band)."""
    for floor, grade in ((90, 5.0), (80, 6.0), (70, 7.0), (60, 8.5), (50, 11.0), (30, 14.0)):
        if fre >= floor:
            return grade
    return 16.0


def _consensus(scores: dict[str, float]) -> float:
    """Median US grade across the eight formulas.

    textstat's `text_standard` took the *mode* of floor/ceil/round of each
    score, put Dale–Chall's raw score (not a grade) into that vote, and broke
    ties by list order — so a 1% change in one count could move the answer
    eight grades. The median of grade-equivalents is stable and has a plain
    reading: half the formulas say harder, half say easier.
    """
    grades = sorted(
        [
            scores["flesch_kincaid_grade"],
            scores["gunning_fog"],
            scores["smog_index"],
            scores["automated_readability_index"],
            scores["coleman_liau_index"],
            scores["linsear_write_formula"],
            _dale_chall_grade(scores["dale_chall_readability_score"]),
            _flesch_grade(scores["flesch_reading_ease"]),
        ]
    )
    mid = len(grades) // 2
    return (grades[mid - 1] + grades[mid]) / 2


# What the published evidence supports, shipped with every result so a reader
# of the JSON sees it as well as a reader of the UI.
VALIDITY: dict[str, Any] = {
    "status": "legacy",
    "evidence": (
        "On the CLEAR corpus (4,724 school reading excerpts ranked by teachers), Flesch, "
        "Flesch-Kincaid, ARI, SMOG and New Dale-Chall correlate r = .48-.56 with the "
        "teachers' ease scores, about a quarter to a third of the variance (Crossley et "
        "al. 2023, Behavior Research Methods, doi:10.3758/s13428-022-01802-x). Coleman-Liau "
        "and Linsear Write weren't tested. The formulas largely duplicate each other."
    ),
    "text_standard": (
        "The median of the eight grades: a convenience summary with no validation of its own."
    ),
    "population": (
        "Normed on 20th-century US native-speaker readers; evidence for second-language "
        "readers is thinner."
    ),
}


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    words = a.words
    n_words = len(words)
    n_sent = a.sentence_count

    syll = {id(w): word_syllables(w) for w in words}
    n_syll = sum(syll.values())
    poly = sum(1 for w in words if syll[id(w)] >= 3)
    mono = sum(1 for w in words if syll[id(w)] == 1)
    letters = sum(_letters(w) for w in words)
    long_words = sum(1 for w in words if _letters(w) > 6)
    unfamiliar = sum(1 for w in words if not _is_familiar(w))
    fog_complex = sum(1 for w in words if _is_fog_complex(w, syll[id(w)]))

    if not n_words or not n_sent:
        zeros = dict.fromkeys(
            (
                "flesch_reading_ease",
                "flesch_kincaid_grade",
                "gunning_fog",
                "smog_index",
                "automated_readability_index",
                "coleman_liau_index",
                "dale_chall_readability_score",
                "linsear_write_formula",
                "text_standard",
            ),
            0.0,
        )
        return {
            "counts": {
                "characters": len("".join(text.split())),
                "characters_with_spaces": len(text),
                "words": 0,
                "syllables": 0,
                "sentences": 0,
                "polysyllable_words": 0,
                "monosyllable_words": 0,
                "long_words": 0,
                "difficult_words": 0,
                "reading_time_seconds": 0.0,
            },
            "averages": {
                "words_per_sentence": 0.0,
                "syllables_per_word": 0.0,
                "characters_per_word": 0.0,
            },
            "scores": zeros,
            "reliability": {"reliable": False, "notes": ["No words to measure."]},
            "validity": VALIDITY,
        }

    asl = n_words / n_sent  # average sentence length
    asw = n_syll / n_words  # average syllables per word
    pdw = 100 * unfamiliar / n_words  # Dale–Chall percentage of difficult words

    scores = {
        # Flesch (1948).
        "flesch_reading_ease": 206.835 - 1.015 * asl - 84.6 * asw,
        # Kincaid, Fishburne, Rogers & Chissom (1975).
        "flesch_kincaid_grade": 0.39 * asl + 11.8 * asw - 15.59,
        # Gunning (1952).
        "gunning_fog": 0.4 * (asl + 100 * fog_complex / n_words),
        # McLaughlin (1969), normalised to a 30-sentence sample.
        "smog_index": 1.0430 * math.sqrt(poly * 30 / n_sent) + 3.1291,
        # Senter & Smith (1967).
        "automated_readability_index": 4.71 * letters / n_words + 0.5 * asl - 21.43,
        # Coleman & Liau (1975): L and S are per 100 words.
        "coleman_liau_index": 0.0588 * (100 * letters / n_words)
        - 0.296 * (100 * n_sent / n_words)
        - 15.8,
        # Chall & Dale (1995) raw score, with the adjustment above 5% difficult words.
        "dale_chall_readability_score": 0.1579 * pdw + 0.0496 * asl + (3.6365 if pdw > 5 else 0.0),
        "linsear_write_formula": _linsear_write(a, syll),
    }
    scores["text_standard"] = _consensus(scores)
    scores = {k: round(v, 2) for k, v in scores.items()}

    notes: list[str] = []
    if n_words < MIN_WORDS_RELIABLE:
        notes.append(
            f"Only {n_words} words. Readability formulas were fitted on passages of "
            f"{MIN_WORDS_RELIABLE}+ words; on shorter texts one long word or sentence swings "
            "every score."
        )
    if n_sent < MIN_SENTENCES_SMOG:
        notes.append(
            f"SMOG was normed on 30-sentence samples; this text has {n_sent}, so the "
            "SMOG score is extrapolated."
        )

    return {
        "counts": {
            "characters": len("".join(a.text.split())),
            "characters_with_spaces": len(a.text),
            "words": n_words,
            "syllables": n_syll,
            "sentences": n_sent,
            "polysyllable_words": poly,
            "monosyllable_words": mono,
            "long_words": long_words,
            "difficult_words": unfamiliar,
            "reading_time_seconds": round(n_words / READING_WPM * 60, 1),
        },
        "averages": {
            "words_per_sentence": round(asl, 3),
            "syllables_per_word": round(asw, 3),
            "characters_per_word": round(letters / n_words, 3),
        },
        "scores": scores,
        # Only text length makes the whole set unreliable; the SMOG note is
        # about SMOG alone, and would otherwise flag every text under 30 sentences.
        "reliability": {"reliable": n_words >= MIN_WORDS_RELIABLE, "notes": notes},
        "validity": VALIDITY,
    }
