"""Simpler alternatives for words above a target CEFR level.

For a teacher adapting a text to, say, B1: every word the CEFR module rates
above B1 gets a short list of same-POS synonyms at or below B1, each already
inflected to fit the original token (`benefits`/VBZ -> `helps`, `larger`/JJR
-> `bigger`), so the UI can swap it in with one click.

The data (`data/alternatives.json`, built by
`scripts/build_data/build_alternatives.py`) comes from Open English WordNet,
restricted to each word's dominant senses and to synonyms whose own main
sense is the shared one. It is a suggestion list for a human editor, not an
automatic rewriter: a synonym is right for the word's *usual* meaning, and a
reader still has to check it fits the sentence.

Inflection is a small suffix rule set plus a table, generated at build time,
of every form of every suggested word that the rules would get wrong
(`go`/VBD -> `went`, `stop`/VBG -> `stopping`, `important`/JJR -> `more
important`). So no inflection library is loaded at runtime.

Levels come from the same lookup as `cefr.py` and `profile.py`, so a word
flagged here is the word coloured at that level on the CEFR tab.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Every spelling a caller might use for the part of speech -> WordNet letter.
_POS = {
    "n": "n",
    "noun": "n",
    "NOUN": "n",
    "v": "v",
    "verb": "v",
    "VERB": "v",
    "a": "a",
    "s": "a",
    "adj": "a",
    "adjective": "a",
    "ADJ": "a",
    "r": "r",
    "adv": "r",
    "adverb": "r",
    "ADV": "r",
}
_POS_NAME = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}
# Penn tags that change a lemma's form, per part of speech. Any other tag
# (NN, VB, VBP, JJ, RB, or a tag that disagrees with the POS) keeps the lemma.
_INFLECTING = {
    "n": frozenset({"NNS"}),
    "v": frozenset({"VBZ", "VBD", "VBN", "VBG"}),
    "a": frozenset({"JJR", "JJS"}),
    "r": frozenset({"RBR", "RBS"}),
}
_VOWELS = frozenset("aeiou")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("alternatives.json").read_text("utf-8")
    return json.loads(raw)


def warm() -> None:
    _data()


def meta() -> dict[str, str]:
    """Source, version, licence and attribution of the bundled data."""
    d = _data()
    return {k: d[k] for k in ("source", "version", "license", "attribution")}


# --- inflection ------------------------------------------------------------------


def regular_form(lemma: str, tag: str) -> str:
    """The form the suffix rules alone give `lemma` for Penn `tag`.

    Deliberately simple: no consonant doubling, no irregulars. Whatever this
    gets wrong for a suggested word is stored in the data's `forms` table.
    """
    w = lemma
    if tag in ("NNS", "VBZ"):
        if w.endswith(("s", "x", "z", "ch", "sh")):
            return w + "es"
        if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
            return w[:-1] + "ies"
        if tag == "VBZ" and w.endswith("o") and len(w) > 1 and w[-2] not in _VOWELS:
            return w + "es"
        return w + "s"
    if tag in ("VBD", "VBN"):
        if w.endswith("e"):
            return w + "d"
        if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
            return w[:-1] + "ied"
        return w + "ed"
    if tag == "VBG":
        if w.endswith("ie"):
            return w[:-2] + "ying"
        if w.endswith("e") and not w.endswith(("ee", "ye", "oe")) and len(w) > 2:
            return w[:-1] + "ing"
        return w + "ing"
    if tag in ("JJR", "JJS", "RBR", "RBS"):
        suffix = "r" if tag in ("JJR", "RBR") else "st"
        if w.endswith("e"):
            return w + suffix
        if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
            return w[:-1] + "i" + "e" + suffix
        return w + "e" + suffix
    return w


def inflect(lemma: str, tag: str | None, *, pos: str | None = None, variant: str = "gb") -> str:
    """`lemma` in the form Penn `tag` asks for: `inflect("help", "VBZ") == "helps"`.

    `pos` (any spelling `suggest` accepts) limits which tags inflect, so a
    noun given a verb's tag stays as it is. `variant` picks British or
    American spelling where the two differ (`travelled` / `traveled`).
    """
    if not tag:
        return lemma
    if pos is not None:
        p = _POS.get(pos)
        if p is None or tag not in _INFLECTING[p]:
            return lemma
    elif not any(tag in tags for tags in _INFLECTING.values()):
        return lemma
    # The table is keyed by the data's (US) spelling; rules run on the word as given.
    table = _data()["forms"].get(_lemma_of(lemma))
    if table is not None and tag in table:
        form = table[tag]
        if form is None:  # no -er/-est form: periphrastic comparison
            return ("more " if tag in ("JJR", "RBR") else "most ") + lemma
        if isinstance(form, list):
            return form[1] if variant == "gb" else form[0]
        return form
    return regular_form(lemma, tag)


def match_case(original: str, replacement: str) -> str:
    """Give `replacement` the capitalisation of `original` (`Large` -> `Big`)."""
    if len(original) > 1 and original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


# --- lookup ------------------------------------------------------------------------


def _level_index(level: str) -> int:
    try:
        return LEVELS.index(level.upper())
    except (ValueError, AttributeError):
        raise ValueError(
            f"target_level must be one of {', '.join(LEVELS)}; got {level!r}"
        ) from None


def _spell(word: str, variant: str) -> str:
    return _data()["gb"].get(word, word) if variant == "gb" else word


def suggest(
    lemma: str,
    pos: str,
    target_level: str,
    penn_tag: str | None = None,
    *,
    variant: str = "gb",
) -> list[dict[str, Any]]:
    """Simpler synonyms of `lemma` at or below `target_level`, best first.

    `pos` is a CEFR label (`noun`), a spaCy UPOS (`NOUN`) or a WordNet letter
    (`n`). Returns `[{"word", "level", "band", "form"}]`: `word` is the
    suggestion's lemma, `form` that word inflected for `penn_tag` (equal to
    `word` when no tag is given), `band` its BNC/COCA band (None when it is
    beyond the 25 bands). Empty when the word is already at or below the
    target, isn't on the CEFR list for that POS, or has no safe alternative.
    """
    target = _level_index(target_level)
    p = _POS.get(pos)
    if p is None:
        return []
    entry = _data()["entries"].get(f"{lemma.lower()}|{p}")
    if entry is None or entry[0] <= target:
        return []
    out = []
    for word, lvl, band in entry[1]:
        if lvl > target:
            continue
        spelt = _spell(word, variant)
        out.append(
            {
                "word": spelt,
                "level": LEVELS[lvl],
                "band": band if band != 99 else None,
                "form": inflect(spelt, penn_tag, pos=p, variant=variant),
            }
        )
    return out


SOURCE = (
    "Synonyms: Open English WordNet 2025 (CC BY 4.0); sense frequencies: WordNet 3.0 "
    "(Princeton). Levels: CEFR-J 1.5 + Octanove C1/C2. Bands: Nation BNC/COCA."
)


def analyze(
    text: str,
    *,
    analysis=None,
    variant: str = "gb",
    errors_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Every distinct lemma at A2 or above in a text, with simpler alternatives.

    Target-independent: the client filters, showing items above the reader's
    target and the suggestions at or below it. Returns

        {"items": [{"lemma", "pos", "level", "count",
                    "suggestions": [{"word", "level", "band"}],   # <= 5, best first
                    "occurrences": [{"span": [start, end], "surface", "tag",
                                     "replacements": {word: form_to_insert}}]}],
         "source": "..."}

    `level` is the level the CEFR module gives these tokens (same lookup, same
    per-POS level). `replacements` maps each suggestion to the form that fits
    the occurrence: inflected for its Penn tag and capitalised like it
    (`Benefits`/VBZ -> `Helps`). A preceding `a`/`an` is not adjusted.
    Items with no safe alternative keep an empty `suggestions` list. Items are
    sorted by level (highest first), then count, then first appearance.

    Left out: proper nouns, parts of hyphenated compounds, tokens whose CEFR
    level is a fallback from another part of speech, and misspellings. Pass
    the errors module's result as `errors_result` to exclude exactly the words
    it flags (errors and unknown names); without it, a token whose surface
    form is in none of the bundled word lists is treated as a misspelling.
    """
    from lexinspect import _lists
    from lexinspect._text import ensure, lookup

    a = ensure(text, analysis)
    entries = _lists.cefr_entries()
    flagged: set[int] | None = None
    if errors_result is not None:
        flagged = {
            span[0]
            for key in ("errors", "unknown_names")
            for e in errors_result.get(key, [])
            for span in e.get("spans", [])
        }
    known = _lists.bnc_forms()

    items: dict[tuple[str, str], dict[str, Any]] = {}
    for lex in a.lexical:
        p = _POS.get(lex.pos)
        word = a.words[lex.word_index]
        if p is None or lex.is_proper or word.is_hyphenated:
            continue
        key, entry = lookup(entries, lex.keys)
        if entry is None:
            continue
        level, matched = _lists.cefr_level(entry, lex.pos)
        if not matched or level == LEVELS[0]:
            continue
        tok = a.doc[lex.i]
        if flagged is not None:
            if word.tokens[0].idx in flagged:
                continue
        elif lex.surface not in known and lex.surface not in entries:
            continue
        item = items.get((key, p))
        if item is None:
            item = items[(key, p)] = {
                "lemma": key,
                "pos": _POS_NAME[p],
                "level": level,
                "count": 0,
                "suggestions": [
                    {"word": s["word"], "level": s["level"], "band": s["band"]}
                    for s in suggest(key, p, LEVELS[LEVELS.index(level) - 1], variant=variant)
                ],
                "occurrences": [],
                "_first": len(items),
            }
        item["count"] += 1
        reps = {}
        for s in item["suggestions"]:
            form = inflect(s["word"], lex.tag, pos=p, variant=variant)
            reps[s["word"]] = match_case(tok.text, form)
        item["occurrences"].append(
            {
                "span": [tok.idx, tok.idx + len(tok.text)],
                "surface": tok.text,
                "tag": lex.tag,
                "replacements": reps,
            }
        )
    ordered = sorted(
        items.values(), key=lambda it: (-LEVELS.index(it["level"]), -it["count"], it["_first"])
    )
    for it in ordered:
        del it["_first"]
    return {"items": ordered, "source": SOURCE}


@lru_cache(maxsize=1)
def _gb_to_lemma() -> dict[str, str]:
    return {gb: us for us, gb in _data()["gb"].items()}


def _lemma_of(word: str) -> str:
    """The data's own spelling of a (possibly British-respelt) suggestion."""
    return _gb_to_lemma().get(word, word)


def for_analysis(
    analysis,
    cefr_result: dict[str, Any] | None,
    target_level: str,
    *,
    variant: str = "gb",
    errors_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`analyze` narrowed to one target level, for callers that know it.

    Keeps the items above `target_level` and, in each, the suggestions at or
    below it (and their replacements). `cefr_result`, the CEFR module's
    output for the same text, is optional: when given and nothing in the text
    is above the target, this returns at once without a lookup pass.
    """
    target = _level_index(target_level)
    out: dict[str, Any] = {"target_level": LEVELS[target], "items": [], "source": SOURCE}
    if cefr_result is not None:
        top = cefr_result.get("highest_level_present")
        if top is None or LEVELS.index(top) <= target:
            return out
    full = analyze(analysis.text, analysis=analysis, variant=variant, errors_result=errors_result)
    for it in full["items"]:
        if LEVELS.index(it["level"]) <= target:
            continue
        keep = [s for s in it["suggestions"] if LEVELS.index(s["level"]) <= target]
        words = {s["word"] for s in keep}
        out["items"].append(
            {
                **it,
                "suggestions": keep,
                "occurrences": [
                    {
                        **o,
                        "replacements": {w: f for w, f in o["replacements"].items() if w in words},
                    }
                    for o in it["occurrences"]
                ],
            }
        )
    return out
