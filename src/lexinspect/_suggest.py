"""Fast spelling suggestions.

spylls' Hunspell `suggest()` is faithful but pure Python: 0.3–0.6 s per word,
which on a public server is both slow and a cost lever an attacker could pull
by pasting gibberish. This is a Norvig-style corrector instead:

1. Candidates are known words within edit distance 1 (deletions, transpositions,
   substitutions, insertions), then distance 2 only if distance 1 found nothing.
   A "known word" is a form in Nation's BNC/COCA families or NGSL — real,
   frequency-banded English, British and American spellings both.
2. A candidate must also be accepted by the Hunspell dictionary for the chosen
   variant, so British mode suggests `colour`, never `color`.
3. Ranking: edit distance, then transposition (`teh` -> `the`), then frequency band (1k words before 10k words),
   then a small bonus for keeping the first letter (misspellings rarely change it).
4. Run-together words (`alot`, `infact`) get a split suggestion.

Each call is bounded: distance-2 search is skipped for long words, and the
caller caps how many distinct errors it asks about.
"""

from __future__ import annotations

import string
from functools import lru_cache

from lexinspect import _lists

_LETTERS = string.ascii_lowercase
MAX_DISTANCE2_LEN = 12


@lru_cache(maxsize=1)
def _vocab() -> dict[str, int]:
    """Known lowercase word -> frequency band (lower is more frequent)."""
    out: dict[str, int] = {}
    for form, fam in _lists.bnc_forms().items():
        if form.isalpha() or "'" in form or "-" in form:
            out[form] = min(out.get(form, 99), fam.band)
    for form, item in _lists.ngsl_forms().items():
        out[form] = min(out.get(form, 99), 1 if item.get("rank", 9999) <= 1000 else 2)
    return out


def _edits1(word: str) -> set[str]:
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = [a + b[1:] for a, b in splits if b]
    transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
    replaces = [a + c + b[1:] for a, b in splits if b for c in _LETTERS]
    inserts = [a + c + b for a, b in splits for c in _LETTERS]
    return set(deletes + transposes + replaces + inserts)


def _restore_case(original: str, suggestion: str) -> str:
    if original.isupper() and len(original) > 1:
        return suggestion.upper()
    if original[:1].isupper():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion


def suggest(word: str, dictionary, limit: int = 5) -> list[str]:
    """Up to `limit` corrections for `word`, valid in `dictionary` (a spylls Dictionary)."""
    low = word.lower()
    if not low.isascii() or len(low) > 30:
        return []
    vocab = _vocab()

    def accepted(cands):
        return [c for c in cands if c in vocab and c != low and dictionary.lookup(c)]

    ranked: list[tuple[int, int, int, int, str]] = []
    letters = sorted(low)
    found = accepted(_edits1(low))
    distance = 1
    if not found and len(low) <= MAX_DISTANCE2_LEN:
        e1 = _edits1(low)
        found = accepted({e2 for e in e1 for e2 in _edits1(e)} - e1)
        distance = 2
    for c in found:
        # Same letters in a different order (`teh`) is the commonest typo of all.
        anagram = 0 if sorted(c) == letters else 1
        ranked.append((distance, anagram, vocab[c], 0 if c[:1] == low[:1] else 1, c))

    # Run-together words: `alot` -> `a lot`, `infact` -> `in fact`.
    for i in range(1, len(low)):
        a, b = low[:i], low[i:]
        if (
            a in vocab
            and b in vocab
            and vocab[a] <= 2
            and vocab[b] <= 3
            and dictionary.lookup(a)
            and dictionary.lookup(b)
        ):
            ranked.append((1, 0, max(vocab[a], vocab[b]), 0, f"{a} {b}"))

    ranked.sort()
    out: list[str] = []
    for *_k, c in ranked:
        s = _restore_case(word, c)
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out
