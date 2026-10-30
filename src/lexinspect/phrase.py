"""PHRASE list detection (Martinez & Schmitt 2012).

506 phrasal expressions across K1–K5 frequency bands. Each entry's printed base
form is compiled at build time (scripts/build_data/build_phrase_index.py) into
its real variants — `THERE IS/ARE` into `there is` and `there are`,
`A BIT (OF)` into `a bit of` and `a bit` — with sense glosses set aside and
`ONE'S`/`ONESELF` as possessive/reflexive slots.

Matching, per sentence, never across punctuation:

- **Inflection.** A word in the phrase matches its own form or any form with
  the same lemma, so DEAL WITH matches `dealt with` and HAVE TO matches `had to`.
  Contractions read as their full forms (`there's` = `there is`). The bare
  noun of a preposition + word idiom is invariable: IN PART doesn't match
  `in parts of`, FOR GOOD doesn't match `for goods`.
- **Senses.** Where an entry's example sentence shows its `to` as infinitival
  (TO) or prepositional (IN), or its `that` as complementiser or determiner,
  the text must agree. That's what keeps "going to the park" from counting as
  GOING TO (FUTURE), and picks USED TO (PAST) for "used to snow" but USED TO
  (ACCUSTOMED) for "used to the noise".
- **Constructions.** Some entries also need their construction, not just
  their words (Study 4 guidelines B3, C1–C5). Each check tests a stated
  syntactic pattern:
  USED TO (PAST) not after `be`/`get`/`become`/`grow` (`was used to drain`)
  or as a participle or modifier, and USED TO (ACCUSTOMED) only after them;
  THAT IS not with relative `that` (`a method that is used`) or a
  clause-opening demonstrative subject of `is` followed by a predicate
  (`That is my car`, `…; that is false`), and otherwise counted with or
  without punctuation (`…, as long as you pay that is.`), also when the parser
  tags its `that` as an adverb; KIND OF only with no determiner or modifier on
  `kind` and an adjective, adverb, verb or punctuation after (`kind of tired`,
  not `a kind of tool`); WEALTH OF only after `a`/`an`; A GOOD only before a
  number; IS TO not after a goal noun as subject (`the aim is to`); IN A WAY
  not with a relative clause, comparison or prepositional phrase after `way`
  (`in a way that`); JUST AS not before an adjective or adverb (`just as
  tall`); AS LONG AS not after a numeral, `twice`, `half` or `times` (`twice
  as long as`); PUT IT not before a particle (`put it out`); GET OFF only
  with `off` as a particle. Nothing inside a hyphenated word counts (`in
  common-law countries`).
  Not checked, so counted wherever the words match: THE CASE (`in the case
  of`), THE LATTER (`the latter part of the year`), FOR ALL (`for all
  members`), UP TO inside a longer verb (`live up to`), and comparative AS
  LONG AS with no multiplier (`not as long as the book`).
- **Overlap.** Longest match wins and consumes its tokens: `as well as` is one
  hit, not also `as well`. (The old matcher counted both.)

When two senses of one form both fit (`out of`: 'IN/FROM', 'USING', 'DUE TO'),
the hit takes the more frequent sense and lists the others in `also_possible`.

The checks added in 0.4.0 belong to fix families (`_fix_families`) so the
Study 4 fix-check can measure each against 0.3.3; all of them are on.

Beyond the hits, the output carries what the list itself says about them.
These are all derived from the hits, so they never change which hits count:

- **Expressions.** One row per distinct entry, with its frequency per 100
  million words, the register ratings, the published example and the highest
  BNC/COCA band among its words. `rank` is the list's Integrated List Rank:
  the item's place when the PHRASE List and the BNC word-family lists are
  merged, so HAVE TO (rank 107) is the 107th most frequent item of the two.
- **Register.** The list rates each expression in spoken general, written
  general and written academic English. Its legend: `* * *` "most common in
  this genre (or as common)", `* *` "less common", `*` "infrequent", `x` "rare
  or non-existent". The ratings compare genres for one expression; they are
  not frequencies, and two expressions with the same rating can differ widely
  in `freq_per_100m`.
- **Integrated profile.** The list's bands are built to sit inside the 1K
  word-family bands, which is what lets an expression replace its words in a
  frequency profile. `integrated_profile` is the `bnc_coca` profile with every
  word inside an expression counted at the expression's band: `in terms of`
  is three 1K words to `bnc_coca` and three K2 tokens here. 446 of the 501
  entries whose words are all in the bands sit above their highest word, so
  the integrated profile is usually the harder one.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect import bnc_coca
from lexinspect._context import (
    SPECIFYING_NOUNS,
    in_hyphenated_word,
    next_word,
    prev_word,
    rephrasing_that_is,
)
from lexinspect._fix_families import enabled
from lexinspect._text import Analysis, ensure

POSS, REFL = "<poss>", "<refl>"

# The published list's register columns and its legend for them.
REGISTERS = ("spoken_general", "written_general", "written_academic")
_RATINGS = {"* * *": "most_common", "* *": "less_common", "*": "infrequent", "x": "rare"}
_POSSESSIVES = frozenset({"my", "your", "his", "her", "its", "our", "their", "one's"})
_REFLEXIVES = frozenset(
    {
        "myself",
        "yourself",
        "himself",
        "herself",
        "itself",
        "ourselves",
        "yourselves",
        "themselves",
        "oneself",
    }
)
_CLITIC_FULL = {
    "n't": "not",
    "'re": "are",
    "'m": "am",
    "'ve": "have",
    "'ll": "will",
    "ca": "can",
    "wo": "will",
    "sha": "shall",
}


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = resources.files("lexinspect.data").joinpath("phrase.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> dict[str, list[tuple[tuple[str, ...], dict[str, Any]]]]:
    """First phrase word -> [(variant, item)], longest variants first, then by rank."""
    out: dict[str, list[tuple[tuple[str, ...], dict[str, Any]]]] = {}
    for item in _load()["items"]:
        for var in item["variants"]:
            out.setdefault(var[0], []).append((tuple(var), item))
    for cands in out.values():
        cands.sort(key=lambda c: (-len(c[0]), c[1]["rank"]))
    return out


def _norm(tok) -> str:
    text = tok.lower_.replace("’", "'")
    if text == "'s":
        lemma = tok.lemma_.lower()
        if lemma in ("be", "have"):
            return "is" if lemma == "be" else "has"
        # spaCy lemmatises a curly `’s` to `’`, so fall back on the tag: a verb
        # `'s` before a past participle is `has` (`it's been`), otherwise `is`.
        if tok.tag_ == "VBZ":
            nxt = tok.nbor(1) if tok.i + 1 < len(tok.doc) else None
            return "has" if nxt is not None and nxt.tag_ == "VBN" else "is"
        return "'s"
    if text == "'d":
        return "would" if tok.tag_ == "MD" else "had"
    return _CLITIC_FULL.get(text, text)


def _first_keys(norm: str, lemma: str) -> tuple[str, ...]:
    keys = [norm, lemma]
    if norm in _POSSESSIVES:
        keys.append(POSS)
    if norm in _REFLEXIVES:
        keys.append(REFL)
    return tuple(dict.fromkeys(keys))


def _matches(tok, norm: str, target: str) -> bool:
    if target == POSS:
        return norm in _POSSESSIVES
    if target == REFL:
        return norm in _REFLEXIVES
    return norm == target or tok.lemma_.lower() == target


# Tags that play the same role for sense purposes: an adverbial particle is
# tagged RP or RB depending on the parse, and both mean "not a preposition".
_TAG_CLASS = {"RP": "particle", "RB": "particle", "RBR": "particle", "WDT": "DT"}


def _tag_class(tag: str) -> str:
    return _TAG_CLASS.get(tag, tag)


def _clause_final(tok) -> bool:
    """Nothing but punctuation (or the end of the text) follows `tok`."""
    nxt = tok.nbor(1) if tok.i + 1 < len(tok.doc) else None
    return nxt is None or nxt.is_punct or nxt.is_space


Check = Callable[[list], bool]

# Construction checks per entry rank, each with the fix family it belongs to
# (None: always on). Every check that applies must pass.
_CONTEXT: dict[int, list[tuple[str | None, Check]]] = {}


def _context(family: str | None, ranks: tuple[int, ...], check: Check) -> None:
    for rank in ranks:
        _CONTEXT.setdefault(rank, []).append((family, check))


# Senses the tagger can't separate. TO GO ('REMAINING') — "two more to go" —
# is tagged exactly like the infinitive in "trains to go to work"; the
# remaining sense ends its clause.
_context(None, (5463,), lambda span: _clause_final(span[-1]))

# Ranks of the entries the 0.4.0 checks name.
_USED_TO_PAST, _USED_TO_ACCUSTOMED = 892, 2752
_THAT_IS = 1764
_IS_TO, _KIND_OF, _IN_A_WAY = 845, 2445, 2823
_WEALTH_OF, _A_GOOD = 5306, 4259
_PUT_IT, _GET_ON_OFF = 2983, 2388
_JUST_AS, _AS_LONG_AS = 5231, 1931


# PH-A: USED TO and THAT IS ------------------------------------------------------

# `be used to` (ACCUSTOMED) and its near-synonymous linking verbs.
_ACCUSTOMED_VERBS = frozenset({"be", "get", "become", "grow"})


def _after_be_or_get(tok) -> bool:
    """`tok` follows `be`/`get`/`become`/`grow`, across adverbs (`is not used
    to`), or the parser gave it one as auxiliary."""
    if any(c.dep_ in ("auxpass", "aux") and c.lemma_ in _ACCUSTOMED_VERBS for c in tok.children):
        return True
    p = prev_word(tok)
    while p is not None and p.pos_ in ("ADV", "PART") and p.lower_ != "to":
        p = prev_word(p)
    return p is not None and p.lemma_ in _ACCUSTOMED_VERBS


def _used_to_past(span) -> bool:
    """PH-01. Semi-modal USED TO (PAST) is a finite verb: not passive `was used
    to drain` (guidelines B3, C1) and not a participle or modifier (Biber et
    al. 1999 separate semi-modal `used to` from `be used to`)."""
    u = span[0]
    return not (_after_be_or_get(u) or u.tag_ == "VBN" or u.dep_ in ("acl", "relcl", "amod"))


_context("PH-A", (_USED_TO_PAST,), _used_to_past)
_context("PH-A", (_USED_TO_ACCUSTOMED,), lambda span: _after_be_or_get(span[0]))  # PH-01
_context("PH-A", (_THAT_IS,), lambda span: rephrasing_that_is(span[0]))  # PH-02


# PH-B: entry-specific constructions ---------------------------------------------


# Words after `way` that make it the manner noun with a dependent: a relative
# (`in a way that`, `which`, `where`), a comparison (`as`, `similar`, `to`) or a
# prepositional phrase (`in`, `of`).
_MANNER_DEPENDENTS = frozenset({"that", "which", "in", "as", "similar", "of", "to", "where"})


def _not_manner_noun(span) -> bool:
    """PH-04. IN A WAY ('to some extent') isn't `in a way` + relative clause,
    comparison or prepositional phrase: there `way` heads an ordinary noun
    phrase, 'manner' (guidelines B3, C2)."""
    way = span[-1]
    if any(c.dep_ in ("relcl", "acl", "amod", "prep") for c in way.children if c.i > way.i):
        return False
    n = next_word(way)
    return not (n is not None and n.lower_ in _MANNER_DEPENDENTS)


# Determiners before `kind` make it the noun 'type' (`a kind of`, `this kind of`).
_KIND_DETERMINERS = frozenset({"what", "which", "this", "that", "some", "any", "every", "each"})


def _softening_kind_of(span) -> bool:
    """PH-05. KIND OF is the adverb 'somewhat' (`kind of tired`), not the noun
    `kind` heading a noun phrase (`a kind of tool`; guidelines B3, C2): no
    determiner or modifier on `kind`, and an adjective, adverb, verb or
    punctuation after."""
    kind = span[-2]
    if kind.lower_ != "kind" or any(
        c.dep_ in ("det", "poss", "amod", "nummod") for c in kind.children
    ):
        return False
    p = prev_word(kind)
    if p is not None and (p.pos_ == "DET" or p.lower_ in _KIND_DETERMINERS):
        return False
    n = next_word(span[-1])
    return n is None or n.pos_ in ("ADJ", "ADV", "VERB", "AUX") or n.is_punct


def _not_specifying(span) -> bool:
    """PH-06. IS TO isn't specifying `be` + infinitive after a goal noun (`the
    aim is to finish`): the infinitive identifies the aim."""
    return not any(
        c.dep_ in ("nsubj", "nsubjpass") and c.lemma_.lower() in SPECIFYING_NOUNS
        for c in span[0].children
    )


def _a_wealth_of(span) -> bool:
    """PH-09. WEALTH OF is the quantifier `a wealth of`, not the noun `wealth`
    with an owner (`the wealth of the family`; guidelines B3, C2)."""
    p = prev_word(span[0])
    return p is not None and p.lower_ in ("a", "an")


def _before_number(span) -> bool:
    """PH-09. A GOOD ('AT LEAST') is `a good` + a number (`a good ten miles`)."""
    n = next_word(span[-1])
    return n is not None and (n.like_num or n.pos_ == "NUM")


def _not_before_particle(span) -> bool:
    """PH-11. PUT IT ('SAY') isn't `put it` + particle (`put it out`, C3)."""
    n = next_word(span[-1])
    return not (n is not None and (n.tag_ == "RP" or n.dep_ == "prt"))


def _particle_off(span) -> bool:
    """PH-11. GET ON/OFF: `off` must be the particle, as `on` must (the tags
    come from the one example sentence, which shows only `on`)."""
    return span[-1].lower_ != "off" or span[-1].tag_ == "RP"


def _not_comparative_just_as(span) -> bool:
    """PH-12. JUST AS ('WHEN') isn't `just as` + adjective or adverb, the
    comparative `as … as` (`just as tall`; guidelines B3, C2)."""
    n = next_word(span[-1])
    return not (n is not None and n.pos_ in ("ADJ", "ADV") and n.lower_ != "as")


# Multipliers before comparative `as long as` (`twice as long as`). Focusing
# and negating words (`only`, `just`, `not`) are not evidence of comparison:
# `only as long as you keep quiet` is the condition. A comparative with no
# multiplier (`not as long as the book`, `as long as the hall`) still counts
# as AS LONG AS, a known limitation.
_COMPARATIVE_DEGREE = frozenset({"twice", "half", "times"})


def _not_comparative_as_long_as(span) -> bool:
    """PH-12. AS LONG AS ('provided that') isn't a multiplier (a numeral,
    `twice`, `half`, `times`) + comparative `as long as` (guidelines B3,
    C2)."""
    p = prev_word(span[0])
    return not (p is not None and (p.lower_ in _COMPARATIVE_DEGREE or p.like_num))


_context("PH-B", (_IN_A_WAY,), _not_manner_noun)
_context("PH-B", (_KIND_OF,), _softening_kind_of)
_context("PH-B", (_IS_TO,), _not_specifying)
_context("PH-B", (_WEALTH_OF,), _a_wealth_of)
_context("PH-B", (_A_GOOD,), _before_number)
_context("PH-B", (_PUT_IT,), _not_before_particle)
_context("PH-B", (_GET_ON_OFF,), _particle_off)
_context("PH-B", (_JUST_AS,), _not_comparative_just_as)
_context("PH-B", (_AS_LONG_AS,), _not_comparative_as_long_as)


def _context_ok(rank: int, span) -> bool:
    if any(
        (fam is None or enabled(fam)) and not check(span) for fam, check in _CONTEXT.get(rank, ())
    ):
        return False
    # PH-13: no part of a hyphenated word is an expression (`in common-law`, C4).
    return not (enabled("PH-C") and in_hyphenated_word(span[0], span[-1]))


# PH-10: prepositions whose two-word idioms with a bare word (IN PART, FOR GOOD,
# AT LAST) are invariable: the second word matches only in its listed form.
_PREPOSITIONS = frozenset(
    {"in", "on", "at", "by", "for", "of", "from", "to", "with", "under", "out", "into", "without"}
)


def _invariable(var: tuple[str, ...]) -> bool:
    return len(var) == 2 and var[0] in _PREPOSITIONS and var[1] not in (POSS, REFL)


def _tags_agree(item: dict[str, Any], var: tuple[str, ...], span) -> bool:
    tags = item.get("tags") or {}
    for tok, w in zip(span, var, strict=True):
        if w not in tags or _tag_class(tok.tag_) == _tag_class(tags[w]):
            continue
        # PH-02: sm sometimes tags rewording `that` as an adverb, so the DT its
        # example shows would reject the real expression (`…, that is, …`). An
        # RB `that` is accepted wherever the construction check accepts it.
        if (
            item["rank"] == _THAT_IS
            and w == "that"
            and tok.tag_ == "RB"
            and enabled("PH-A")
            and rephrasing_that_is(tok)
        ):
            continue
        return False
    return True


def _segments(doc):
    """Runs of word tokens within a sentence, broken at punctuation."""
    for sent in doc.sents:
        run = []
        for tok in sent:
            if tok.is_space:
                continue
            if tok.is_punct and tok.text not in ("'", "’"):
                if run:
                    yield run
                run = []
                continue
            run.append(tok)
        if run:
            yield run


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    index = _index()

    hits: list[dict[str, Any]] = []
    # Per hit: its entry, the other entries that fit the same words, its tokens.
    matched: list[tuple[dict[str, Any], list[dict[str, Any]], list[int]]] = []
    for run in _segments(a.doc):
        norms = [_norm(t) for t in run]
        i, n = 0, len(run)
        while i < n:
            found: list[tuple[tuple[str, ...], dict[str, Any]]] = []
            for key in _first_keys(norms[i], run[i].lemma_.lower()):
                for var, item in index.get(key, ()):
                    if i + len(var) > n or (found and len(var) < len(found[0][0])):
                        continue
                    if not all(_matches(run[i + k], norms[i + k], w) for k, w in enumerate(var)):
                        continue
                    if enabled("PH-C") and _invariable(var) and norms[i + 1] != var[1]:
                        continue  # PH-10
                    span = run[i : i + len(var)]
                    if not _tags_agree(item, var, span) or not _context_ok(item["rank"], span):
                        continue
                    if found and len(var) > len(found[0][0]):
                        found = []
                    found.append((var, item))
            if not found:
                i += 1
                continue
            found.sort(key=lambda f: f[1]["rank"])
            var, item = found[0]
            span = run[i : i + len(var)]
            hit = {
                "rank": item["rank"],
                "phrase": item["phrase"],
                "k_band": item["k_band"],
                "surface": a.text[span[0].idx : span[-1].idx + len(span[-1].text)],
                "sense": item.get("sense"),
                "token_index": span[0].i,
                "span": [span[0].idx, span[-1].idx + len(span[-1].text)],
            }
            others = [f[1]["phrase"] for f in found[1:] if f[1]["rank"] != item["rank"]]
            if others:
                hit["also_possible"] = others
            hits.append(hit)
            alternatives = [f[1] for f in found[1:] if f[1]["rank"] != item["rank"]]
            matched.append((item, alternatives, [t.i for t in span]))
            i += len(var)

    per_band = {str(k): 0 for k in range(1, 6)}
    for h in hits:
        per_band[str(h["k_band"])] += 1
    return {
        "counts": {
            "total_hits": len(hits),
            "unique_phrases": len({h["rank"] for h in hits}),
            "content_tokens": len(a.lexical),
            "hits_per_1000_words": round(len(hits) / a.word_count * 1000, 2)
            if a.word_count
            else 0.0,
        },
        "hits_per_k_band": per_band,
        "hits": sorted(hits, key=lambda h: (h["rank"], h["token_index"])),
        "phrase_frequency": dict(Counter(h["phrase"] for h in hits).most_common()),
        **_derived(a, matched),
    }


def _derived(a: Analysis, matched) -> dict[str, Any]:
    """Expressions, register counts and the integrated profile, from the hits."""
    lex_at = {lex.i: lex for lex in a.lexical}
    phrase_band: dict[int, int] = {}  # lexical token index -> its expression's band
    register = {r: dict.fromkeys(_RATINGS.values(), 0) for r in REGISTERS}
    rows: dict[int, dict[str, Any]] = {}
    for item, alternatives, token_ids in matched:
        lexes = [lex_at[i] for i in token_ids if i in lex_at]
        for lex in lexes:
            phrase_band[lex.i] = item["k_band"]
        for r in REGISTERS:
            register[r][_RATINGS[item[r]]] += 1
        row = rows.get(item["rank"])
        if row is None:
            row = rows[item["rank"]] = {
                "rank": item["rank"],
                "phrase": item["phrase"],
                "sense": item.get("sense"),
                "k_band": item["k_band"],
                "count": 0,
                "freq_per_100m": item["freq_per_100m"],
                "register": {r: _RATINGS[item[r]] for r in REGISTERS},
                "word_band": None,
                "example": item["example"],
                "also_possible": [],
            }
        row["count"] += 1
        for alt in alternatives:
            if all(x["rank"] != alt["rank"] for x in row["also_possible"]):
                row["also_possible"].append(
                    {"rank": alt["rank"], "phrase": alt["phrase"], "sense": alt.get("sense")}
                )
        wb = _word_band(lexes)
        if wb is not None and (row["word_band"] is None or wb > row["word_band"]):
            row["word_band"] = wb
    return {
        "expressions": sorted(rows.values(), key=lambda e: (-e["count"], e["rank"])),
        "register": register,
        "integrated_profile": _integrated_profile(a, phrase_band),
    }


def _word_band(lexes) -> int | None:
    """Highest BNC/COCA band among an occurrence's words; None unless every
    word is in a band (`oh` is on the marginal-words list, not in a band)."""
    bands = []
    for lex in lexes:
        kind, fam = bnc_coca.classify(lex)
        if kind != "band":
            return None
        bands.append(fam.band)
    return max(bands) if bands else None


def _integrated_profile(a: Analysis, phrase_band: dict[int, int]) -> dict[str, Any]:
    """The `bnc_coca` profile with each word inside an expression counted at
    the expression's band (Martinez & Schmitt's integrated list). Same tokens,
    same supplementary and proper-noun rules, so the two profiles differ only
    where an expression is."""
    lexical = a.lexical
    n = len(lexical)
    band_tokens: Counter[int] = Counter()
    phrase_tokens: Counter[int] = Counter()
    kinds: Counter[str] = Counter()
    raised = lowered = 0
    for lex in lexical:
        kind, value = bnc_coca.classify(lex)
        band = phrase_band.get(lex.i)
        if band is not None:
            band_tokens[band] += 1
            phrase_tokens[band] += 1
            if kind == "band":
                raised += band > value.band
                lowered += band < value.band
        elif kind == "band":
            band_tokens[value.band] += 1
        else:
            kinds[kind] += 1
    on_list = sum(band_tokens.values())
    assumed_known = kinds["supplementary"] + kinds["proper"]
    per_band = {
        b: {"tokens": row.pop("tokens"), "phrase_tokens": phrase_tokens[int(b)], **row}
        for b, row in bnc_coca.coverage_by_band(band_tokens, n, assumed_known).items()
    }
    return {
        "counts": {
            "content_tokens": n,
            "phrase_tokens": sum(phrase_tokens.values()),
            "raised_tokens": raised,
            "lowered_tokens": lowered,
            "on_list_tokens": on_list,
            "proper_noun_tokens": kinds["proper"],
            "supplementary_tokens": kinds["supplementary"],
            "off_list_tokens": kinds["off"],
        },
        "coverage_pct": bnc_coca.pct(on_list, n),
        "coverage_with_supplementary_pct": bnc_coca.pct(on_list + assumed_known, n),
        "per_band": per_band,
    }
