"""Metadiscourse marker detection (Hyland 2005, 10-category framework).

Two dimensions, five categories each:
- Interactive (organise the text): transitions, frame markers, endophoric
  markers, evidentials, code glosses.
- Interactional (engage the reader): hedges, boosters, attitude markers,
  engagement markers, self-mentions.

Hyland's categories are *functional*: a word is metadiscourse only when it does
metadiscoursal work in context, and his own counts were checked by hand. The
marker lists are full of everyday words that usually don't — `for`, `so`,
`and`, `first`, `table`, `found`, `would`, `about`, `you` — and the old matcher
counted every occurrence, which made densities several times too high and
rewarded essays for simply containing common words.

Each marker here is matched against the text (longest match first, never
across punctuation) and then has to pass a context check built on spaCy's
tags and dependency parse — the automatable part of Hyland's hand-coding. The
checks are syntactic and lexical proxies for functional categories: each
states the pattern it tests, and the categories it cannot decide are listed
as limitations.

- Quotation: nothing between paired quotation marks within a paragraph (curly
  double, straight double or curly single) counts, so scare quotes are
  excluded too, a known cost; a possessive `’` (`the students’ work`) doesn't
  close a curly single quotation; straight single quotes are not used, so
  text in them counts. Hyphenated words: no part of one counts (`second-order`),
  except marker + hyphen + participle (`so-called`, `above-mentioned`).
- `and`, `but`, `or`, `yet`, `so` as transitions: opening a sentence, after
  `;` `:` or a dash, or as a coordinator joining two verbs neither of which is
  a nominal constituent (`writing and editing texts takes skill` links none);
  a comma alone isn't enough. `for` only as a conjunction. Whether the
  relation is internal or external isn't decided.
- `still`, `then`, `now`, `next`, `first`, `finally` only clause-initially,
  where a word-internal hyphen or an opening bracket doesn't open a clause;
  not `still` + a non-modal verb or adjective (`still standing`), nor
  `rather than`;
  `but rather`/`or rather` correct. `since`, `while` only as subordinators,
  and not `while` + a participle with no subject (`while walking home`);
  concessive `while admitting…` is lost with it, and a finite temporal
  `since`/`while` clause (`since we arrived`) still counts. `even if` is a
  transition.
- Frame markers: ordinals (`first`, `firstly`, `overall`) only as
  clause-initial adverbials, not `first` + participle (`first published`);
  `the aim/goal/purpose` only when recognised as the present text's or
  study's (see below), and `to conclude` and the like clause-initially or
  after such a goal noun + `be`; not `by far` before a superlative or
  comparative.
- Endophoric markers: `table`, `figure`, `page`, `in section`, `see table`
  … only with a label in digits or short capitals after the marker
  (`Table 2`, `in section 4`, `see table S2`); `above`/`below` not as the
  object of a preposition other than `as` (`from below`) or after a number
  (`aged 60 and above`), other spatial uses not being recognised; `see` +
  `above`/`below` or a labelled table, figure or appendix.
- Code glosses: `that is` except relative `that` and a clause-opening
  demonstrative subject of `is` followed by a predicate (`That is not the
  point`, `but that is not`, `if that is right`, `He said, 'That is
  wrong.'`; not after a comma); `particularly`, `especially` not modifying
  an adverb or a predicative adjective (`particularly cold`), nor an
  attributive adjective when straight after a determiner (`an especially
  good way`); `known as` not after `become`/`come`/`grow`; `or indeed`
  reformulates.
- Present text or study: a noun phrase whose head is in the own-work class
  (`results`, `study`, `analysis`, `data`, `model`, `paper` …, and the
  text nouns of the listed self-mentions, `article`, `thesis`) with `this`,
  `these`, `our`, `my`, `present`, `current` or `here`, or a labelled part
  (`Table 1`). Nothing else is recognised as the present work: not `this
  historian` or `the current literature`, and also not `this essay` or `our
  goal`. An owner other than the writers overrides those words: a possessor
  other than `our`/`my` (`Smith's current study`, `their current model`) or
  an authorial `by` + a name or pronoun (`this study by Smith`).
- Evidentials: reporting verbs with a name or source noun as subject
  (`Smith (2010) argues`, `the survey shows`), not with the present text or
  study as subject (`this study shows`); a hedge or booster reporting verb
  moves to evidentials only with a named subject (`Smith suggests`) or a
  source noun a name owns or modifies (`Smith's study shows`), not an unowned
  source noun (`the data suggest` stays a hedge) or another noun with an
  owner (`John's face suggests` stays a hedge); a named owner is always taken
  as an outside source; `according to`/`based on` not with the present text
  or study as object. Whether another object is a source (`according to
  Smith`) or a criterion (`according to size`) isn't decided: both count.
- Evidence and cognitive verbs (`find`, `show`, `think`, `feel`, `appear`) as
  boosters or hedges only with a clausal complement; `find`/`show` not with
  `he`/`she`/`they`/`it` as subject or as `find out` (cited authors as `they`
  are lost); the hedging reporting verbs (`suggest`, `argue`, `indicate`)
  with any object (`the data suggest a link`).
- Stance: stance adverbs (`clearly`, `surprisingly`) not after the verb they
  modify, on an attributive participle or graded inside the clause, unless
  set off by commas (`failed, surprisingly, in…`) or enclosed by paired
  brackets or dashes (`proves (clearly) that`); epistemic adjectives as
  boosters (`clear`, `certain`, `true`) only predicatively; `sure` never in
  `make (ADV) sure` and, with a subject, only with `I`/`we`/`it`/`one`; `not
  always` hedges; `possible` not after a superlative or `every`/`all` or in
  `made it possible`; `expected` not attributive, and a hedge when passive
  with a to-infinitive or finite clause (`are expected to rise`, `it is
  expected that…`), otherwise as before; `agree`/`prefer` only with the
  writer as subject. Descriptive uses of attitude adjectives (`important
  for limb development`) aren't recognised.
- Modals only as modals; `must` is a booster before `be` or a perfect,
  across adverbs (`must surely be`, `must have surely been`), otherwise
  attitude, negated epistemic perfects included; approximators (`about`,
  `around`) only before a number.
- Engagement verbs (`consider`, `note`, `imagine`) as imperatives or with a
  reader subject outside relative and `if`/`when` clauses; not as
  to-infinitives, except extraposed after `it` + `be` + `important` or
  `essential` (`it is important to consider`), the listed attitude markers of
  importance or necessity.
- `we`/`us`/`our`: self-mention with research and argument verbs, `we`/`us`
  with a past-tense verb other than `be`/`have` (`we recruited`; inclusive
  `as we saw` is misread), or `our` + an own-work noun (`our results`);
  otherwise inclusive reader engagement. `US` is the country unless the
  whole text is in capitals, and lower-case `i` isn't the pronoun.

Each hit lands in exactly one category (the old matcher counted `in fact` as
three hits). Rule decisions are explainable: every hit carries the category it
was assigned and, where the marker is listed under others, `also_listed_as`.

Marker lists are curated from canonical Hyland 2005 reproductions; the hedges
category mirrors Appendix A. Self-mentions also include `this paper/study`
standing in for the writers, an adaptation of Hyland, who lists *the paper
proposes* among frame markers (2005, p. 51). See data/SOURCES.md.

The checks added in 0.4.0 belong to fix families (`_fix_families`) so the
Study 4 fix-check can measure each against 0.3.3; all of them are on.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._context import (
    SPECIFYING_NOUNS,
    in_hyphenated_word,
    is_hyphen,
    next_word,
    prev_word,
    rephrasing_that_is,
    spaced_hyphen,
)
from lexinspect._fix_families import enabled
from lexinspect._text import Analysis, ensure


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = (
        resources.files("lexinspect.data")
        .joinpath("metadiscourse.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> tuple[dict[tuple[str, ...], list[tuple[str, str]]], int]:
    """Marker tuple -> [(dimension, category), ...] in list order; and max length."""
    out: dict[tuple[str, ...], list[tuple[str, str]]] = defaultdict(list)
    max_len = 0
    for dimension, cats in _load()["categories"].items():
        for category, items in cats.items():
            for item in items:
                key = tuple(item.replace("’", "'").split())
                # `let's`, `one's`, `couldn't` are split by spaCy into two
                # tokens; store them the way they'll appear.
                key = tuple(p for w in key for p in _split_clitic(w))
                if key:
                    out[key].append((dimension, category))
                    max_len = max(max_len, len(key))
    return dict(out), max_len


def _split_clitic(word: str) -> tuple[str, ...]:
    for clitic in ("n't", "'s"):
        if word.endswith(clitic) and len(word) > len(clitic):
            return (word[: -len(clitic)], clitic)
    return (word,)


# --- context predicates ------------------------------------------------------

_CLAUSE_BREAKS = frozenset({",", ";", ":", "(", "—", "–", "-"})
_SOURCE_NOUNS = frozenset(
    {
        "study",
        "studies",
        "research",
        "researcher",
        "researchers",
        "author",
        "authors",
        "report",
        "reports",
        "survey",
        "surveys",
        "data",
        "evidence",
        "result",
        "results",
        "finding",
        "findings",
        "paper",
        "article",
        "scholar",
        "scholars",
        "expert",
        "experts",
        "scientist",
        "scientists",
        "analysis",
        "literature",
        "review",
        "theory",
        "statistics",
        "figures",
        "experiment",
        "experiments",
        "work",
        "writer",
        "writers",
        "critic",
        "critics",
    }
)
_RESEARCH_VERBS = frozenset(
    {
        "argue",
        "propose",
        "suggest",
        "show",
        "find",
        "conclude",
        "examine",
        "investigate",
        "analyse",
        "analyze",
        "present",
        "report",
        "discuss",
        "describe",
        "focus",
        "aim",
        "believe",
        "think",
        "conduct",
        "use",
        "collect",
        "claim",
        "demonstrate",
        "observe",
        "measure",
        "test",
        "compare",
        "identify",
        "explore",
        "outline",
        "consider",
        "note",
        "hypothesise",
        "hypothesize",
        "assume",
        "define",
        "adopt",
        "employ",
        "develop",
    }
)
_READER_SUBJECTS = frozenset({"you", "we", "us"})


def _prev(tok):
    return tok.doc[tok.i - 1] if tok.i > 0 else None


def _next(tok, k: int = 1):
    j = tok.i + k
    return tok.doc[j] if j < len(tok.doc) else None


def clause_initial(tok) -> bool:
    """First word of its sentence, or right after a clause break (`,` `;` `:`).

    MD-04: a hyphen joining the parts of a word (`second-order`) or an opening
    bracket opens no clause."""
    if tok.is_sent_start:
        return True
    p = prev_word(tok)
    if p is None:
        return True
    if enabled("MD-B") and (p.text == "(" or (is_hyphen(p) and not spaced_hyphen(p))):
        return False
    return p.text in _CLAUSE_BREAKS or p.is_sent_start and p.is_punct


def joins_clauses(tok) -> bool:
    """A coordinator joining two clauses (`I came and he left`), or opening a sentence."""
    if clause_initial(tok):
        return True
    head = tok.head
    if tok.dep_ != "cc" or head.pos_ not in ("VERB", "AUX"):
        return False
    return any(c.dep_ == "conj" and c.pos_ in ("VERB", "AUX") for c in head.children)


def is_subordinator(tok) -> bool:
    return tok.dep_ == "mark"


def has_clause_complement(tok) -> bool:
    """A verb with a clausal complement: `found that…`, `seems to…`, `I think it…`."""
    if tok.pos_ not in ("VERB", "AUX"):
        return False
    n = _next(tok)
    if n is not None and n.lower_ in ("that", "to", "whether", "if", "how", "why", "what"):
        return True
    if any(c.dep_ in ("ccomp", "xcomp") for c in tok.children):
        return True
    # `it seems`, `it appears`: expletive subject
    return any(c.dep_ == "expl" or (c.dep_ == "nsubj" and c.lower_ == "it") for c in tok.children)


def has_source_subject(tok) -> bool:
    """The subject is a source: a name or a source noun (`Smith argues`, `the
    survey shows`). MD-17: not one that refers to this text or study (`this
    study shows`, `our results suggest`, `Table 1 shows`): the writer's own
    study takes boosters or hedges (Study 4 guidelines A5)."""
    for c in tok.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            if enabled("MD-E") and own_text(c):
                return False
            return (
                c.pos_ == "PROPN"
                or c.lower_ in _SOURCE_NOUNS
                or (c.pos_ == "NOUN" and c.lemma_.lower() in _SOURCE_NOUNS)
            )
    return False


def _source_noun(tok) -> bool:
    """`tok` is in the 0.3.3 source-noun class, by form or, for a noun, lemma."""
    return tok.lower_ in _SOURCE_NOUNS or (
        tok.pos_ == "NOUN" and tok.lemma_.lower() in _SOURCE_NOUNS
    )


def named_source_subject(tok) -> bool:
    """MD-18: the subject is a named source outside the text: a name (`Smith
    argues`, `Smith and Lee suggest`), or a noun of the 0.3.3 source-noun class
    that a name owns or modifies (`Smith's study shows`, `the Smith study
    shows`). A noun outside that class keeps its 0.3.3 category whoever owns it
    (`John's temperature suggests that…` stays a hedge: the writer's inference
    from a sign). An unowned source noun (`the data suggest`, `research shows`)
    can be the writer's own and stays as 0.3.3 assigned it (guidelines A4: `The
    data ⟦suggest⟧ a link` is a hedge). A name as owner is taken as an outside
    source even when it names a dataset or an institution (`the NHANES data
    suggest`): who is making the claim is not resolved."""
    for c in tok.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            if own_text(c):
                return False
            return c.pos_ == "PROPN" or (
                _source_noun(c)
                and any(
                    g.pos_ == "PROPN" and g.dep_ in ("poss", "compound", "nmod") for g in c.children
                )
            )
    return False


def writer_subject(tok) -> bool:
    """The writer is the subject: `I believe`, `we suspect`. Mental-state verbs
    mark the writer's stance only when the stance is the writer's own; `some
    people believe that…` reports someone else's."""
    for c in tok.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            return c.lower_ in ("i", "we")
    # Coordinated verb sharing a subject: `I hope and believe that…`
    if tok.dep_ == "conj" and tok.head is not tok:
        return writer_subject(tok.head)
    return False


def is_verb(tok) -> bool:
    return tok.pos_ in ("VERB", "AUX")


def is_modal(tok) -> bool:
    return tok.tag_ == "MD"


def predicative(tok) -> bool:
    return tok.pos_ == "ADJ" and tok.dep_ != "amod"


def before_number(tok) -> bool:
    n = _next(tok)
    return n is not None and (n.like_num or n.pos_ == "NUM")


def has_reference(tok) -> bool:
    """`Table 2`, `Figure 3b`, `Section IV`, `Appendix A`."""
    n = _next(tok)
    if n is None:
        return False
    t = n.text
    return n.like_num or (len(t) <= 4 and (t.isupper() or t[:1].isdigit()))


def not_spatial(tok) -> bool:
    """`see below`, `the table above` — not `above the clouds`."""
    return not (tok.tag_ == "IN" and any(c.dep_ == "pobj" for c in tok.children))


def addresses_reader(tok) -> bool:
    """Imperative (`Consider…`, `Note that…`) or with a reader subject (`you will notice`)."""
    if not is_verb(tok):
        return False
    subj = [c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")]
    if not subj:
        return tok.tag_ == "VB"
    return subj[0].lower_ in _READER_SUBJECTS


def _governing_verb(tok):
    """The verb a pronoun belongs to: its head, climbing out of nominals."""
    h = tok.head
    for _ in range(3):
        if h.pos_ in ("VERB", "AUX") or h == h.head:
            return h
        h = h.head
    return h


# `our` + one of these is the writers' own work (`our results`).
_OWN_WORK_NOUNS = frozenset(
    {
        "results",
        "findings",
        "study",
        "analysis",
        "data",
        "research",
        "aim",
        "approach",
        "method",
        "sample",
        "argument",
        "model",
        "experiment",
        "paper",
    }
)


def exclusive_we(tok) -> bool:
    """`we`-forms used by writers about their own work (`we found`, `our results`).

    SX-01: also `we`/`us` with a past-tense main verb other than `be`/`have`,
    which usually reports the writers' own procedure (`we recruited`;
    Harwood 2005). Inclusive past-tense `we` (`as we saw above`) is misread
    as exclusive: a known cost."""
    v = _governing_verb(tok)
    if v.lemma_.lower() in _RESEARCH_VERBS:
        return True
    if tok.lower_ in ("our", "ours"):
        return tok.head.lower_ in _OWN_WORK_NOUNS
    return (
        enabled("MD-I")
        and tok.lower_ in ("we", "us")
        and v.tag_ == "VBD"
        and v.lemma_ not in ("be", "have")
    )


def epistemic_must(tok) -> bool:
    """`must be true`, `must have been` (booster) vs `must act` (obligation)."""
    n = _next(tok)
    return n is not None and n.lower_ in ("be", "have")


Rule = Callable[[Any], bool]

# Context checks per (marker, category). A marker/category with no entry here
# needs no check. The first category in `_PRIORITY` (or list order) whose check
# passes is the one the hit is assigned to.
_RULES: dict[tuple[str, str], Rule] = {}


def _rule(markers: str, category: str, fn: Rule) -> None:
    for m in markers.split("|"):
        _RULES[(m, category)] = fn


_rule("and|but|or|yet|so|for", "transitions", joins_clauses)
_rule("for", "transitions", lambda t: t.tag_ == "CC" or (clause_initial(t) and t.dep_ == "cc"))
_rule("still|then|now|again|further|equally|instead|rather", "transitions", clause_initial)
_rule(
    "since|while|though|although|whereas|because",
    "transitions",
    lambda t: is_subordinator(t) or clause_initial(t),
)
_rule(
    "first|second|third|next|finally|lastly|overall",
    "frame_markers",
    lambda t: clause_initial(t) and t.pos_ in ("ADV", "ADJ", "NUM", "INTJ"),
)
_rule(
    "example|examples|figure|figures|table|tables|page|in chapter|in section|in part|"
    "see chapter|see figure|see section|see table",
    "endophoric_markers",
    has_reference,
)
_rule("above|below", "endophoric_markers", not_spatial)
_rule(
    "see",
    "endophoric_markers",
    lambda t: (n := _next(t)) is not None and n.lower_ in ("above", "below"),
)
_rule(
    "argues|asserts|believes|claim|claims|concludes|contends|demonstrates|discusses|"
    "indicates|maintains|mentions|notes|observes|proposes|remarks|reports|shows|states|"
    "stresses|suggests|writes",
    "evidentials",
    lambda t: is_verb(t) and has_source_subject(t),
)
_rule(
    "argues that|asserts that|believes that|claims that|concludes that|demonstrates that|"
    "found that|indicates that|maintains that|notes that|observes that|proposes that|"
    "reports that|shows that|states that|suggests that|points out",
    "evidentials",
    lambda t: is_verb(t) and has_source_subject(t),
)
_rule("cited|quoted", "evidentials", is_verb)
_rule(
    "find|found|show|shown|shows|establish|established|prove|proven|proves|"
    "demonstrate|demonstrates|conclude",
    "boosters",
    has_clause_complement,
)
_rule("think|believe", "boosters", lambda t: has_clause_complement(t) and writer_subject(t))
_rule("clear|certain|sure|true|obvious|definite|undeniable|indisputable", "boosters", predicative)
_rule("must", "boosters", epistemic_must)
_rule("must", "attitude_markers", lambda t: not epistemic_must(t))
# Hedging verbs hedge with a plain object too (`results suggest a link`)...
_rule(
    "argue|argued|argues|claim|claimed|claims|indicate|indicated|indicates|suggest|suggested|"
    "suggests|estimate|estimated|postulate|postulated|postulates",
    "hedges",
    is_verb,
)
# ...but these have common literal senses (`felt the cold`, `appeared on stage`).
_rule("appear|appeared|appears", "hedges", has_clause_complement)
_rule(
    "feel|feels|felt|assume|assumed|suppose|supposes|suspect|suspects|guess",
    "hedges",
    lambda t: has_clause_complement(t) and writer_subject(t),
)
_rule(
    "supposed",
    "hedges",
    lambda t: has_clause_complement(t) and not ((n := _next(t)) is not None and n.lower_ == "to"),
)
_rule("would|could|should|might|may|ought|couldn't", "hedges", is_modal)
_rule("about|around", "hedges", before_number)
_rule("rather", "hedges", lambda t: not clause_initial(t))
_rule("doubt", "hedges", is_verb)
_rule("agree|prefer|preferred|expected", "attitude_markers", is_verb)
_rule(
    "consider|imagine|look|note|notice|picture|recall|see|think about|think of",
    "engagement_markers",
    addresses_reader,
)
_rule("we|us|our|ours|ourselves", "self_mentions", exclusive_we)
_rule(
    "say",
    "code_glosses",
    lambda t: (
        ((p := _prev(t)) is not None and p.text == ",")
        or ((n := _next(t)) is not None and n.text == ",")
    ),
)
_rule("called|known as", "code_glosses", lambda t: t.tag_ == "VBN")
_rule("meaning", "code_glosses", lambda t: t.tag_ == "VBG")
_rule("or", "code_glosses", lambda t: False)  # `or` as a gloss needs a human
_rule("as", "evidentials", lambda t: False)  # bare `as`: the multi-word evidentials cover it
_rule("earlier|later", "endophoric_markers", lambda t: False)  # bare: temporal, not textual
_rule(
    "the table|the figure|the example",
    "endophoric_markers",
    lambda t: (n := _next(t, 2)) is not None and n.lower_ in ("above", "below"),
)
_rule("you|your|yours", "engagement_markers", lambda t: True)


# --- 0.4.0 checks -------------------------------------------------------------
# Each replaces the 0.3.3 check for its markers while its fix family is enabled
# (`_fix_families`). Ids (MD-01 …) are those of the Study 4 fix ledger; the
# guideline references are to docs/validation/study4-guidelines.md.


def _fixed(family: str, markers: str, category: str, fn: Rule) -> None:
    for m in markers.split("|"):
        base = _RULES.get((m, category))

        def rule(tok, fn=fn, base=base) -> bool:
            if enabled(family):
                return fn(tok)
            return base is None or base(tok)

        _RULES[(m, category)] = rule


def subject_of(verb):
    """The subject of `verb`, or of the verb it's coordinated with or is the
    complement of (`they tried to show`)."""
    for c in verb.children:
        if c.dep_ in ("nsubj", "nsubjpass", "expl"):
            return c
    if verb.dep_ in ("conj", "xcomp") and verb.head != verb:
        return subject_of(verb.head)
    return None


# The present text or study (B1 of the Study 4 implementation audit). A noun
# phrase is recognised as the present work only affirmatively: its head is in
# the own-work class `_OWN_WORK_NOUNS` (by form or lemma) and it has one of
# these determiners or modifiers, or `here` as its own dependent; or its head
# names a part of a text and has a reference label (`Table 1`).
_OWN_TEXT_DETS = frozenset({"this", "these", "our", "my", "present", "current"})
_PART_NOUNS = frozenset(
    {
        "table",
        "tables",
        "figure",
        "figures",
        "fig",
        "fig.",
        "section",
        "chapter",
        "appendix",
        "eq",
        "eq.",
        "equation",
        "box",
        "panel",
        "supplement",
    }
)


@lru_cache(maxsize=1)
def _present_work_nouns() -> frozenset[str]:
    """The own-work class plus the head nouns of the listed self-mentions that
    name the present text (`this article`, `the present study`, `this thesis`):
    both pre-existing 0.3.3 data, not a list fitted to Study 4 development."""
    heads = {
        m.split()[-1]
        for m in _load()["categories"]["interactional"]["self_mentions"]
        if m.startswith(("this ", "the present ")) and m.split()[-1] not in ("author", "writer")
    }
    return _OWN_WORK_NOUNS | frozenset(heads)


# Possessive pronouns that name an owner other than the writers.
_OTHERS_POSSESSIVES = frozenset({"his", "her", "its", "their", "your"})
# Personal pronouns other than the writers' `me`/`us` (as the object of an
# authorial `by`).
_OTHERS_PRONOUNS = frozenset({"you", "he", "him", "she", "her", "it", "they", "them"})


def _owned_by_others(np) -> bool:
    """Audit r2 B1: the head `np` has an explicit owner other than the writers,
    as a direct dependent: a possessor other than `our`/`my` (`Smith's current
    study`, `the authors' current study`, `their current model`), or an
    authorial `by` whose object is a name or a personal pronoun other than
    `me`/`us` (`this study by Smith`). Only the head's own dependents are
    looked at: a name inside a topic phrase (`this study of Smith's novels`)
    is not an owner."""
    for c in np.children:
        if c.dep_ == "poss" and (c.lower_ in _OTHERS_POSSESSIVES or c.pos_ in ("NOUN", "PROPN")):
            return True
        if (
            c.dep_ == "prep"
            and c.lower_ == "by"
            and any(
                o.dep_ == "pobj"
                and (o.pos_ == "PROPN" or (o.tag_ == "PRP" and o.lower_ in _OTHERS_PRONOUNS))
                for o in c.children
            )
        ):
            return True
    return False


def own_text(np) -> bool:
    """`np` (its head token) refers to the present text or study: `this study`,
    `our analysis`, `the present findings`, `the results here`, `Table 1`.
    Not recognised, so treated as not the present work: person and source
    nouns (`this historian`, `the current literature`), other nouns with a
    demonstrative (`this ritual`, `this plan`), text nouns outside the class
    (`this essay`, `this chapter` without a label), the singular `result` and
    `finding` (the class lists only their plurals), and reference made only
    by a relative clause (`the results presented above`). An explicit owner
    other than the writers defeats `this`/`current`/`present`/`here`
    (`Smith's current study`, `their current model`, `this study by Smith`;
    `_owned_by_others`)."""
    if _owned_by_others(np):
        return False
    if np.lower_ in _PART_NOUNS:
        return has_label(np)
    if not ({np.lower_, np.lemma_.lower()} & _present_work_nouns()):
        return False
    return any(
        (c.dep_ in ("det", "poss", "amod") and c.lower_ in _OWN_TEXT_DETS) or c.lower_ == "here"
        for c in np.children
    )


# MD-A: clause linking and transitions -----------------------------------------

# After these a coordinator opens a new clause. Not after a comma, which also
# separates list items (`rivers, lakes, and wetlands`).
_STRONG_BREAKS = frozenset({";", ":", "—", "–"})
# A verb in one of these roles is a modifier or an argument, not a predication.
_CONSTITUENT_DEPS = frozenset({"amod", "compound", "nmod", "appos", "npadvmod", "pobj", "dobj"})
# Noun-phrase positions: subject, object, prepositional complement, modifier.
_NOMINAL_DEPS = frozenset(
    {
        "nsubj",
        "nsubjpass",
        "csubj",
        "csubjpass",
        "dobj",
        "pobj",
        "pcomp",
        "attr",
        "appos",
        "amod",
        "acl",
        "compound",
        "nmod",
    }
)


def _nonfinite_constituent(verb) -> bool:
    """A gerund or participle in a noun-phrase position with no subject or
    auxiliary of its own (`[writing] or editing texts`, `[written] and signed
    forms`): it names an activity or property, it asserts nothing (Huddleston
    & Pullum 2002, ch. 14; Biber et al. 1999 on participial adjectives)."""
    return (
        verb.pos_ in ("VERB", "AUX")
        and verb.tag_ in ("VBG", "VBN")
        and verb.dep_ in _NOMINAL_DEPS
        and not any(c.dep_ in ("nsubj", "nsubjpass", "aux", "auxpass") for c in verb.children)
    )


def links_propositions(tok) -> bool:
    """MD-01, MD-02. A coordinator relating two propositions (guidelines A4,
    transitions Q1; Hyland 2005, p. 49): it opens a sentence, follows `;` `:`
    or a dash, or joins two verbs. Constituent coordination doesn't count
    (Huddleston & Pullum 2002, ch. 15): nouns (`rivers and lakes`), verbs that
    are modifiers or objects, or non-finite verbs used as noun phrases.
    Shared-subject predicates (`collected and analysed the samples`) do."""
    if tok.is_sent_start:
        return True
    if tok.dep_ == "cc" and _nonfinite_constituent(tok.head):
        return False
    p = prev_word(tok)
    if p is not None and p.text in _STRONG_BREAKS:
        return True
    head = tok.head
    if tok.dep_ != "cc" or head.pos_ not in ("VERB", "AUX") or head.dep_ in _CONSTITUENT_DEPS:
        return False
    return any(
        c.dep_ == "conj" and c.pos_ in ("VERB", "AUX") and c.i > tok.i for c in head.children
    )


def subordinating(tok) -> bool:
    """MD-03. `since`/`while` only as subordinators (not `since 1900`). `while`
    + a participle clause with no subject is temporal, 'during' (`while
    walking home`; guidelines A4). Concessive `while admitting that…` is lost
    with it: a known cost."""
    if tok.dep_ != "mark":
        return False
    h = tok.head
    return not (
        tok.lower_ == "while"
        and h.tag_ in ("VBG", "VBN")
        and not any(c.dep_ in ("nsubj", "nsubjpass") for c in h.children)
    )


def concessive_still(tok) -> bool:
    """MD-05. `still` + verb or adjective is aspectual, 'continues to be'
    (`still standing`; guidelines A4; Biber et al. 1999 separate it from
    linking `still`). Before a modal it can still concede (`still, it may…`)."""
    n = next_word(tok)
    if n is not None and n.pos_ in ("VERB", "AUX", "ADJ") and n.tag_ != "MD":
        return False
    return clause_initial(tok)


def _before_than(tok) -> bool:
    n = next_word(tok)
    return n is not None and n.lower_ == "than"


def corrective_rather(tok) -> bool:
    """MD-06. `rather than` contrasts two phrases, not two propositions
    (guidelines A4, hedges); `but rather`/`or rather` set a proposition against
    another (Hyland 2005, p. 50, comparison)."""
    if _before_than(tok):
        return False
    p = prev_word(tok)
    return clause_initial(tok) or (p is not None and p.lower_ in ("but", "or"))


def downtoning_rather(tok) -> bool:
    """MD-06: hedging `rather large`, but not `rather than`."""
    return not _before_than(tok) and not clause_initial(tok)


_fixed("MD-A", "and|but|or|yet|so", "transitions", links_propositions)
_fixed("MD-A", "since|while", "transitions", subordinating)
_fixed("MD-A", "still", "transitions", concessive_still)
_fixed("MD-A", "rather", "transitions", corrective_rather)
_fixed("MD-A", "rather", "hedges", downtoning_rather)


# MD-C: frame and endophoric markers -------------------------------------------

# Roles in which an ordinal is attributive or nominal, not an adverbial that
# orders the text (`Overall survival`, `the first chapter`).
_NON_ADVERBIAL_DEPS = frozenset({"amod", "nummod", "compound", "npadvmod", "pobj", "nsubj", "dobj"})


def sequencing(tok) -> bool:
    """MD-07. Ordinals order the text only as clause-initial adverbials
    (guidelines A4, frame markers), and `first` + participle means 'for the
    first time' (`first described in 1850`)."""
    if not clause_initial(tok) or tok.dep_ in _NON_ADVERBIAL_DEPS:
        return False
    if tok.pos_ not in ("ADV", "ADJ", "NUM", "INTJ"):
        return False
    n = next_word(tok)
    return not (tok.lower_ in ("first", "firstly") and n is not None and n.tag_ == "VBN")


def present_goal(noun) -> bool:
    """MD-08, MD-09. A goal noun recognised as the present text's or study's:
    `of` + a noun phrase `own_text` recognises (`the aim of this paper`),
    `here` as its own dependent (`the aim here`), or recognised itself (`our
    aim`). Not `the purpose of the ritual` (guidelines A4) or `the aim
    described in Smith's paper`; nor, since `own_text` does not recognise
    them, `the aim of this essay` or `our goal`, which are lost."""
    if own_text(noun):
        return True
    for c in noun.children:
        if c.lower_ == "here":
            return True
        if (
            c.dep_ == "prep"
            and c.lower_ == "of"
            and any(o.dep_ == "pobj" and own_text(o) for o in c.children)
        ):
            return True
    return False


def text_goal(tok) -> bool:
    """MD-08. `the aim/goal/purpose` announce a discourse goal (Hyland 2005,
    p. 51) only of the present text or study (`present_goal`)."""
    noun = next_word(tok)
    return noun is not None and present_goal(noun)


# Goal nouns that, as the subject of `be` + infinitive (`the aim … is to
# summarise`), can make the infinitive a stage label of the text, if the goal
# is the present text's (MD-09).
_GOAL_SUBJECTS = SPECIFYING_NOUNS | {"object"}


def stage_label(tok) -> bool:
    """MD-09. `to conclude`, `to sum up`… label a stage of the text (Hyland
    2005, ch. 3) clause-initially, or as the complement of `be` after a goal
    noun recognised as the present text's (`the aim of this paper is to
    summarise`; `present_goal`). As the complement of `have` or `need` (`we may
    have to conclude that`) or after another goal (`the aim of this plan is to
    begin construction`) the verb is content."""
    if clause_initial(tok):
        return True
    v = tok.head
    if v.dep_ in ("xcomp", "attr", "ccomp") and v.head.lemma_ == "be":
        return any(
            c.dep_ == "nsubj" and c.lemma_.lower() in _GOAL_SUBJECTS and present_goal(c)
            for c in v.head.children
        )
    return False


def not_intensifying(tok) -> bool:
    """MD-10. `by far` before a superlative or comparative intensifies it and
    frames nothing (guidelines A4: `by far the largest city`)."""
    far = next_word(tok)
    after = next_word(far) if far is not None else None
    for x in (after, next_word(after) if after is not None else None):
        if x is not None and (
            x.tag_ in ("JJS", "RBS", "JJR", "RBR") or x.lower_ in ("most", "more", "less", "least")
        ):
            return False
    return True


def has_label(tok, words: int = 1) -> bool:
    """MD-11. `Table 2`, `Figure 3b`, `Table S2`, `Section IV`, `Appendix A`: a
    label in digits, or a short upper-case alphanumeric label (guidelines A4:
    `Figure/Table/Example/Page + number`), straight after the marker's last
    word (`tok` is its first of `words`: `in section 2`). Not a number word
    (`page one`, `the page first`) and not the pronoun `I`."""
    last = tok
    for _ in range(words - 1):
        last = next_word(last) if last is not None else None
    n = _next(last) if last is not None else None
    if n is None:
        return False
    t = n.text
    return t[:1].isdigit() or (len(t) <= 4 and t.isalnum() and t.isupper() and n.tag_ != "PRP")


def textual_above_below(tok) -> bool:
    """MD-12. `above`/`below` refer to the text (guidelines A4, endophoric) but
    not as the object of a preposition other than `as` (`from below`; `as
    above` stays) or after a number (`aged 60 and above`): those are spatial
    or scalar. Other spatial uses with no object of their own (`shone above
    and below the bridge`) are not recognised and still count."""
    if not not_spatial(tok):
        return False
    if tok.dep_ in ("pcomp", "pobj") and tok.head.lower_ != "as":
        return False
    p = prev_word(tok)
    pp = prev_word(p) if p is not None else None
    return not (p is not None and p.lower_ in ("and", "or") and pp is not None and pp.like_num)


def see_endophoric(tok) -> bool:
    """MD-30. `see above`, and `see` + a part of this text with its label
    (`see Appendix B`, `see Table 2`): guidelines A3, precedence 1."""
    n = _next(tok)
    if n is not None and n.lower_ in ("above", "below"):
        return True
    return any(
        x is not None and x.lower_ in _PART_NOUNS and has_label(x)
        for x in (_next(tok), _next(tok, 2))
    )


_fixed(
    "MD-C",
    "first|second|third|next|finally|lastly|overall|firstly|secondly|thirdly",
    "frame_markers",
    sequencing,
)
_fixed("MD-C", "the aim|the goal|the purpose", "frame_markers", text_goal)
_fixed(
    "MD-C",
    "to conclude|to summarise|to summarize|to sum up|to begin|to start with",
    "frame_markers",
    stage_label,
)
_fixed("MD-C", "by far", "frame_markers", not_intensifying)
_fixed(
    "MD-C",
    "example|examples|figure|figures|table|tables|page",
    "endophoric_markers",
    has_label,
)
_fixed(
    "MD-C",
    "in chapter|in section|in part|see chapter|see figure|see section|see table",
    "endophoric_markers",
    lambda t: has_label(t, 2),
)
_fixed("MD-C", "above|below", "endophoric_markers", textual_above_below)
_fixed("MD-C", "see", "endophoric_markers", see_endophoric)


# MD-D: code glosses -------------------------------------------------------------


def not_degree(tok) -> bool:
    """MD-14. `particularly`/`especially` modifying an adverb, a predicative
    adjective, or an attributive adjective when the degree word directly follows
    a determiner or possessive (`an especially good way`) grade it: degree words, which neither gloss nor boost
    (guidelines A4, code glosses; Huddleston & Pullum 2002, ch. 6). Focusing
    `especially swallows`, `and especially distributive justice` stay."""
    if tok.dep_ != "advmod":
        return True
    h = tok.head
    if h.pos_ == "ADV":
        return False
    if h.pos_ == "ADJ":
        if h.dep_ != "amod":
            return False
        p = prev_word(tok)
        return not (p is not None and (p.pos_ == "DET" or p.dep_ in ("det", "poss")))
    return True


# `become`/`come`/`grow` in every form. Matched by form as well as by lemma:
# sm leaves auxiliary `became`, `becomes` unlemmatised (`it became known as`).
_CHANGE_OF_STATE = frozenset(
    {
        "become",
        "becomes",
        "became",
        "becoming",
        "come",
        "comes",
        "came",
        "coming",
        "grow",
        "grows",
        "grew",
        "grown",
        "growing",
    }
)


def naming_known_as(tok) -> bool:
    """MD-15. `became/came/grew known as` reports a change of reputation, not
    the writer naming a term for the reader."""
    p = prev_word(tok)
    return tok.tag_ == "VBN" and not (
        p is not None and (p.lemma_ in ("become", "come", "grow") or p.lower_ in _CHANGE_OF_STATE)
    )


_fixed("MD-D", "that is", "code_glosses", rephrasing_that_is)  # MD-13
_fixed("MD-D", "particularly|especially", "code_glosses", not_degree)
_fixed("MD-D", "particularly", "boosters", not_degree)
_fixed("MD-D", "known as", "code_glosses", naming_known_as)


# MD-E: sources and evidentials ---------------------------------------------------


def source_object(tok) -> bool:
    """MD-16. `according to`/`based on` (`tok` is their first word) attribute
    content to a source outside the text, so not when their object is the
    present text or study as `own_text` recognises it (`according to this
    study`, guidelines A5). Whether another object is a source (`according to
    Smith`) or a criterion (`arranged according to size`, guidelines A4) is
    not decided: both count, as in 0.3.3, a known limitation."""
    prep = _next(tok)
    if prep is None:
        return True
    for o in prep.children:
        if o.dep_ in ("pobj", "pcomp"):
            return not own_text(o)
    return True


# Third-person pronouns as the subject of `find`/`show` narrate someone's
# discovery (`she found that it was empty`) rather than the writer's certainty.
_NARRATED_SUBJECTS = frozenset({"he", "she", "they", "it"})


def writer_finding(tok) -> bool:
    """MD-19. `find/show/prove…` boost the writer's claim (guidelines A4,
    boosters) with a clausal complement, but not with a third-person pronoun
    subject or as `find out`. When `they` are cited authors the occurrence is
    an evidential and is lost: a known cost."""
    if any(c.dep_ == "prt" for c in tok.children):
        return False
    s = subject_of(tok)
    if s is not None and s.lower_ in _NARRATED_SUBJECTS and s.dep_ != "expl":
        return False
    return has_clause_complement(tok)


_HEDGING_REPORT_VERBS = (
    "argue|argued|argues|claim|claimed|claims|indicate|indicated|indicates|"
    "suggest|suggested|suggests"
)
_EVIDENCE_VERBS = (
    "find|found|show|shown|shows|establish|established|prove|proven|proves|"
    "demonstrate|demonstrates|conclude"
)
# MD-18: these, claimed as hedges or boosters, report a source when it's the subject.
_REPORTING_VERBS = frozenset(f"{_HEDGING_REPORT_VERBS}|{_EVIDENCE_VERBS}".split("|"))

_fixed("MD-E", "based on|according to", "evidentials", source_object)
_fixed("MD-E", _EVIDENCE_VERBS, "boosters", writer_finding)


# MD-F: stance --------------------------------------------------------------------

# Words that grade an adverb inside its clause (`very clearly`, `most surprisingly`).
_GRADERS = frozenset({"most", "more", "very", "less", "so", "too"})


def _set_off_by_commas(tok) -> bool:
    """A comma before `tok` and, after it, a comma or the end of its sentence
    (only punctuation follows)."""
    p = prev_word(tok)
    if p is None or p.text != ",":
        return False
    n = next_word(tok)
    if n is not None and n.text == ",":
        return True
    return all(t.is_punct or t.is_space for t in tok.doc[tok.i + 1 : tok.sent.end])


_DASHES = frozenset({"—", "–"})


def _dash(tok) -> bool:
    """An em or en dash, or a hyphen typed with spaces on both sides as a dash."""
    return tok is not None and (tok.text in _DASHES or (tok.text == "-" and spaced_hyphen(tok)))


def _bracketed(tok) -> bool:
    """Audit r2 S2: the adverb phrase (`tok` with its degree modifiers) is
    enclosed, with nothing else, by a pair of round brackets (`proves (very
    clearly) that`) or a pair of dashes (`proves—clearly—that`). A single dash
    next to the adverb is not enough."""
    phrase = [tok, *(c for c in tok.children if c.dep_ == "advmod")]
    p = prev_word(min(phrase, key=lambda t: t.i))
    n = next_word(max(phrase, key=lambda t: t.i))
    if p is None or n is None:
        return False
    return (p.text == "(" and n.text == ")") or (_dash(p) and _dash(n))


def stance_adverb(tok) -> bool:
    """MD-22. Stance adverbs used for manner or degree are not stance
    (guidelines A4, boosters: `She explained it clearly`; Biber et al. 1999
    separate stance from circumstance adverbials): after the verb they modify,
    on an attributive participle, or graded inside the clause. An adverb set
    off by commas on both sides, or by a comma and the end of the sentence, is
    a disjunct and keeps its stance reading (`The model failed, surprisingly,
    in every experiment`), as does one enclosed with its degree modifiers by
    paired brackets or dashes (`proves (clearly) that`, `proves—clearly—that`),
    and a set-off, clause-initial graded disjunct (`Most surprisingly, …`).
    Word order outside those contexts is a proxy: a postverbal stance adverb
    with no punctuation (`proves clearly that`) is lost."""
    if tok.dep_ != "advmod":
        return True
    if _set_off_by_commas(tok) or _bracketed(tok):
        return True
    modifiers = [c for c in tok.children if c.dep_ == "advmod"]
    if any(c.lower_ in _GRADERS for c in modifiers):
        n = next_word(tok)
        return clause_initial(min([tok, *modifiers], key=lambda t: t.i)) and (
            n is not None and n.text == ","
        )
    h = tok.head
    if h.dep_ == "amod":
        return False
    return not (h.pos_ == "VERB" and tok.i > h.i)


def writer_sure(tok) -> bool:
    """MD-23. `sure` boosts only the writer's certainty: never in `make sure`
    (= ensure), across adverbs (`make absolutely sure`), and with a subject
    only when it is `I`, `we`, `it` or `one`. With no subject found (`Sure,
    …`) the 0.3.3 check, predicative `sure`, decides."""
    if not predicative(tok):
        return False
    p = prev_word(tok)
    while p is not None and p.pos_ == "ADV":
        p = prev_word(p)
    if p is not None and p.lemma_ == "make":
        return False
    s = subject_of(tok.head)
    if s is None:
        return True
    return s.lower_ in ("i", "we", "it", "one")


def _not(tok) -> bool:
    return tok.lower_.replace("’", "'") in ("not", "n't")


def epistemic_must_040(tok) -> bool:
    """MD-24. Epistemic `must` + `be` or a perfect, across adverbs before and
    after `have` (`must surely be`, `must have surely been`; Coates 1983);
    `must have` + noun phrase is possession, not perfect. Negation stops the
    search, so a negated epistemic perfect (`must not have seen`) is read as
    obligation, as in 0.3.3: a known limitation."""
    n = next_word(tok)
    while n is not None and n.pos_ in ("ADV", "PART") and not _not(n):
        n = next_word(n)
    if n is None:
        return False
    if n.lower_ == "be":
        return True
    if n.lower_ == "have":
        nn = next_word(n)
        while nn is not None and nn.pos_ in ("ADV", "PART") and not _not(nn):
            nn = next_word(nn)
        return nn is not None and nn.tag_ == "VBN"
    return False


def writers_attitude(tok) -> bool:
    """MD-26. `agree`/`prefer` express the writer's attitude only with the
    writer as subject (guidelines A4: `They preferred tea` is content)."""
    return is_verb(tok) and writer_subject(tok)


def writers_expectation(tok) -> bool:
    """MD-27. `expected` is attitude in `as expected` (`As expected, scores
    rose`) and not attributive (`the expected value`; guidelines A4, attitude
    markers). A passive prediction with a clausal complement is a hedge,
    assigned in `_assign` (`predicted_expected`). Anything else is left to the
    0.3.3 check, a verb (`The result was expected`, `We expected higher
    scores` count as attitude, as before)."""
    if not is_verb(tok) and tok.pos_ != "ADJ":
        return False
    p = prev_word(tok)
    if p is not None and p.lower_ == "as":
        return True
    if tok.dep_ == "amod":
        return False
    return is_verb(tok)


_FINITE = frozenset({"MD", "VBD", "VBZ", "VBP"})


def _finite(verb) -> bool:
    """`verb` heads a finite clause: it or one of its auxiliaries is tensed or modal."""
    return verb.tag_ in _FINITE or any(
        a.dep_ in ("aux", "auxpass") and a.tag_ in _FINITE for a in verb.children
    )


def predicted_expected(tok) -> bool:
    """MD-27. Passive `expected` (with a passive auxiliary or subject) and a
    clausal complement, the writer's tentative prediction (guidelines A4:
    `Scores are expected to rise` is a hedge): a to-infinitive, or a finite
    clause, adverbs between or not (`It is expected that scores will rise`,
    `It was widely expected that prices would fall`). A deontic passive
    (`Students are expected to attend`) is read as a hedge too: a known
    limitation."""
    if not any(c.dep_ in ("auxpass", "nsubjpass") for c in tok.children):
        return False
    return any(
        (c.dep_ == "xcomp" and any(a.dep_ == "aux" and a.lower_ == "to" for a in c.children))
        or (c.dep_ == "ccomp" and _finite(c))
        for c in tok.children
    )


def epistemic_possible(tok) -> bool:
    """MD-28. `possible` after a superlative or `every`/`all` (`the best
    possible answer`, guidelines A4: `all possible combinations`) or as the
    object complement of `make`/`render` (`made it possible`) is not epistemic."""
    p = prev_word(tok)
    if p is not None and (p.tag_ in ("JJS", "RBS") or p.lower_ in ("every", "all")):
        return False
    return not (tok.dep_ in ("oprd", "ccomp", "xcomp") and tok.head.lemma_ in ("make", "render"))


_fixed(
    "MD-F",
    "clearly|obviously|certainly|definitely|evidently|really|truly|surely|decidedly",
    "boosters",
    stance_adverb,
)
_fixed(
    "MD-F",
    "importantly|interestingly|surprisingly|remarkably|strikingly|dramatically|correctly|"
    "appropriately|curiously|unexpectedly",
    "attitude_markers",
    stance_adverb,
)
_fixed("MD-F", "sure", "boosters", writer_sure)
_fixed("MD-F", "must", "boosters", epistemic_must_040)
_fixed("MD-F", "must", "attitude_markers", lambda t: not epistemic_must_040(t))
_fixed("MD-F", "agree|prefer|preferred", "attitude_markers", writers_attitude)
_fixed("MD-F", "expected", "attitude_markers", writers_expectation)
_fixed("MD-F", "possible", "hedges", epistemic_possible)


# MD-G: reader and writer forms ----------------------------------------------------


@lru_cache(maxsize=1)
def _attitude_words() -> frozenset[str]:
    """The one-word attitude markers of metadiscourse.json."""
    items = _load()["categories"]["interactional"]["attitude_markers"]
    return frozenset(m for m in items if " " not in m)


# Audit r2 S3: the attitude markers of metadiscourse.json that say an action
# is required or advisable (importance, necessity), the obligation frames
# Hyland (2002) counts as directives. Affective, evaluative or habitual ones
# (`unfortunate`, `interesting`, `usual`) don't direct the reader.
_DIRECTIVE_ADJECTIVES = frozenset({"important", "essential"})


@lru_cache(maxsize=1)
def _directive_words() -> frozenset[str]:
    """`_DIRECTIVE_ADJECTIVES` as listed among the attitude markers."""
    return _DIRECTIVE_ADJECTIVES & _attitude_words()


def _extraposed_after_attitude(inf) -> bool:
    """The infinitive `inf` follows `it` + `be` + an adjective complement of
    importance or necessity listed as an attitude marker (`It is important to
    consider…`; `_DIRECTIVE_ADJECTIVES`), whether the parser hangs it on the
    adjective or on `be`."""
    g = inf.head
    if g == inf:
        return False
    if g.pos_ == "ADJ" and g.dep_ == "acomp":
        adj, be = g, g.head
    else:
        be = g
        adj = next((c for c in g.children if c.dep_ == "acomp" and c.pos_ == "ADJ"), None)
    return (
        adj is not None
        and adj.lower_ in _directive_words()
        and be.lemma_ == "be"
        and any(c.dep_ in ("nsubj", "expl") and c.lower_ == "it" for c in be.children)
    )


def directive(tok) -> bool:
    """MD-29. Imperative or with a reader subject. A subjectless base form with
    `to` is an infinitive, not an imperative (Huddleston & Pullum 2002,
    ch. 10), unless it is extraposed after `it` + `be` + `important` or
    `essential`, the attitude markers of metadiscourse.json that express
    importance or necessity (`it is important to consider`; Hyland 2002
    counts such obligation frames as directives). Other attitude adjectives
    (`it is unfortunate to see`, `it is usual to see`) and adjectives outside
    the list (`it is necessary to consider`, `it is useful to imagine`) don't
    qualify, so directives after `necessary`, `crucial`, `vital` or `useful`
    are lost. One with a modal isn't either. A reader-subject verb in a
    relative or `if`/`when` clause directs nobody."""
    if not is_verb(tok):
        return False
    subj = [c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")]
    if not subj:
        if tok.tag_ != "VB":
            return False
        h = tok
        aux = [c for c in tok.children if c.dep_ == "aux"]
        if not aux and tok.dep_ == "conj":
            h = tok.head
            aux = [c for c in h.children if c.dep_ == "aux"]
        if not aux:
            return True
        if not any(a.lower_ == "to" for a in aux):
            return False
        return _extraposed_after_attitude(h)
    if tok.dep_ in ("relcl", "acl"):
        return False
    if tok.dep_ == "advcl" and any(
        c.dep_ == "mark" and c.lower_ in ("if", "when", "whenever", "once") for c in tok.children
    ):
        return False
    return subj[0].lower_ in _READER_SUBJECTS


_fixed(
    "MD-G",
    "consider|imagine|look|note|notice|picture|recall|see|think about|think of",
    "engagement_markers",
    directive,
)


# Where a marker is listed under several categories, which to try first.
_PRIORITY: dict[str, tuple[str, ...]] = {
    "in fact": ("boosters", "code_glosses", "transitions"),
    "indeed": ("boosters", "code_glosses", "transitions"),
    "for example": ("code_glosses",),
    "for instance": ("code_glosses",),
    "in other words": ("code_glosses",),
    "in particular": ("code_glosses",),
    "namely": ("code_glosses",),
    "specifically": ("code_glosses",),
    "such as": ("code_glosses",),
    "particularly": ("code_glosses", "boosters"),
    "rather": ("transitions", "hedges"),
    "on the whole": ("hedges", "frame_markers"),
    "usually": ("hedges", "attitude_markers"),
    "see": ("endophoric_markers", "engagement_markers"),
    "must": ("boosters", "attitude_markers"),
    "we": ("self_mentions", "engagement_markers"),
    "us": ("self_mentions", "engagement_markers"),
    "our": ("self_mentions", "engagement_markers"),
    "ours": ("self_mentions", "engagement_markers"),
    "ourselves": ("self_mentions", "engagement_markers"),
}
for _m in ("argues", "claim", "claims", "indicates", "suggests"):
    _PRIORITY[_m] = ("evidentials", "hedges")
for _m in ("demonstrates", "shows"):
    _PRIORITY[_m] = ("evidentials", "boosters")


def _not_a_marker(marker: str, span, all_caps: bool) -> bool:
    """Occurrences that are no marker whatever the context. `all_caps`: the
    whole text is in capitals."""
    first, last = span[0], span[-1]
    # MD-31: `US` is the country unless the whole text is in capitals, and
    # lower-case `i` is not the pronoun (guidelines A3: names and
    # abbreviations). A text that writes the pronoun `US` in a capitalised
    # heading but is otherwise mixed case loses it.
    if enabled("MD-G") and (
        (marker == "us" and first.text == "US" and not all_caps)
        or (marker == "i" and first.text == "i")
    ):
        return True
    # MD-04: part of a hyphenated word is no discourse item, unless the
    # compound is marker + participle and keeps the marker's meaning
    # (`so-called`, `above-mentioned`, `below-listed`).
    if enabled("MD-B") and in_hyphenated_word(first, last):
        doc = first.doc
        p = doc[first.i - 1] if first.i > 0 else None
        n = doc[last.i + 1] if last.i + 1 < len(doc) else None
        after = doc[n.i + 1] if n is not None and n.i + 1 < len(doc) else None
        so_called = marker == "called" and is_hyphen(p) and p.i > 0 and doc[p.i - 1].lower_ == "so"
        participle = is_hyphen(n) and after is not None and after.tag_ == "VBN"
        return not (so_called or participle)
    return False


def _reassign(marker: str, chosen: tuple[str, str], tok) -> tuple[str, str]:
    """Category corrections that depend on the assigned category."""
    cat = chosen[1]
    # MD-18: reporting and evidence verbs whose subject is a source outside the
    # text report it: evidentials, not the writer's hedge or booster
    # (guidelines A5).
    if (
        enabled("MD-E")
        and cat in ("hedges", "boosters")
        and marker in _REPORTING_VERBS
        and is_verb(tok)
        and (named_source_subject(tok) or (tok.dep_ == "conj" and named_source_subject(tok.head)))
    ):
        return "interactive", "evidentials"
    if cat != "boosters":
        return chosen
    p = prev_word(tok)
    # MD-20: a negated universal, `not always`, limits how generally the claim
    # holds (guidelines A4, hedges).
    if enabled("MD-F") and marker == "always" and p is not None and _not(p):
        return "interactional", "hedges"
    # MD-21: `or indeed X`, or `, indeed,` before a noun phrase, offers a
    # reformulation (guidelines A5: in fact / indeed); `and indeed` + modifier
    # escalates and stays a booster.
    if (
        enabled("MD-D")
        and marker == "indeed"
        and p is not None
        and (p.lower_ == "or" or (p.text == "," and tok.head.pos_ in ("NOUN", "PROPN")))
    ):
        return "interactive", "code_glosses"
    return chosen


def _assign(
    marker: str, entries: list[tuple[str, str]], span, all_caps: bool = False
) -> tuple[str, str] | None:
    first_tok = span[0]
    if _not_a_marker(marker, span, all_caps):
        return None
    # MD-25: `even` in `even if` is part of the concessive connective, as in
    # the listed transition `even though` (guidelines A3, marked fragments).
    if enabled("MD-A") and marker == "even":
        n = next_word(first_tok)
        if n is not None and n.lower_ == "if":
            return "interactive", "transitions"
    # MD-27: passive `expected` + to-infinitive hedges (guidelines A4).
    if enabled("MD-F") and marker == "expected" and predicted_expected(first_tok):
        return "interactional", "hedges"
    by_cat = {cat: dim for dim, cat in entries}
    order = list(_PRIORITY.get(marker, ())) + [c for _, c in entries]
    for cat in dict.fromkeys(order):
        if cat not in by_cat:
            continue
        check = _RULES.get((marker, cat))
        if check is None or check(first_tok):
            return _reassign(marker, (by_cat[cat], cat), first_tok)
    return None


# MD-32: quotation marks, per paragraph. A paragraph ends at a blank line (a
# whitespace run with two newlines or more, as in `_nlp`); a single line
# break doesn't end it. Supported pairs: curly double, straight double and
# curly single quotes, where a curly single quote between letters is an
# apostrophe, and so is one the parser attaches to the word before it as a
# possessive (`the students’ work`; `_possessive_apostrophes`). Straight
# single quotes can't be told from apostrophes and are not used: text in them
# still counts (`He said, 'We must act.'`).
_PARAGRAPHS = re.compile(r"(\n[^\S\n]*\n\s*)")


def _possessive_apostrophes(doc) -> frozenset[int]:
    """Audit r2 S4: character offsets of `’` tokens that mark a possessive
    (dependency `case` or tag POS) of the word straight before them (`the
    students’ work`). Such a mark doesn't close a curly single quotation. One
    the parser takes for punctuation still closes it (`‘… the bosses’`)."""
    out = set()
    for t in doc:
        if t.text != "’" or t.i == 0 or not (t.dep_ == "case" or t.tag_ == "POS"):
            continue
        w = doc[t.i - 1]
        if t.head == w and not w.whitespace_:
            out.add(t.idx)
    return frozenset(out)


def _quoted(text: str, apostrophes: frozenset[int] = frozenset()) -> tuple[list[int], list[int]]:
    """Character ranges inside quotation marks, merged and sorted as (starts,
    ends). A mark still open at the end of its paragraph is ignored, so a stray
    quote never swallows a paragraph. `’` at an offset in `apostrophes` is not
    a quotation mark."""
    ranges = []
    pos = 0
    for k, para in enumerate(_PARAGRAPHS.split(text)):
        if k % 2:  # a paragraph break
            pos += len(para)
            continue
        stack: list[tuple[str, int]] = []
        for i, ch in enumerate(para):
            if ch == "“":
                stack.append(("double", i))
            elif ch == "”":
                if stack and stack[-1][0] == "double":
                    ranges.append((pos + stack.pop()[1], pos + i))
            elif ch == '"':
                if stack and stack[-1][0] == "straight":
                    ranges.append((pos + stack.pop()[1], pos + i))
                else:
                    stack.append(("straight", i))
            elif ch == "‘":
                stack.append(("single", i))
            elif ch == "’":
                prv = para[i - 1] if i else " "
                nxt = para[i + 1] if i + 1 < len(para) else " "
                if (prv.isalpha() and nxt.isalpha()) or pos + i in apostrophes:
                    continue  # apostrophe
                if stack and stack[-1][0] == "single":
                    ranges.append((pos + stack.pop()[1], pos + i))
        pos += len(para)
    starts: list[int] = []
    ends: list[int] = []
    for a, b in sorted(ranges):
        if starts and a < ends[-1]:
            ends[-1] = max(ends[-1], b)
        else:
            starts.append(a)
            ends.append(b)
    return starts, ends


def _inside(quoted: tuple[list[int], list[int]], idx: int) -> bool:
    """`idx` falls strictly between an opening and a closing mark."""
    starts, ends = quoted
    k = bisect_right(starts, idx - 1) - 1
    return k >= 0 and idx < ends[k]


def _segments(doc):
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
    index, max_len = _index()
    # MD-32: a quotation is someone else's voice, a mentioned word or a title
    # (guidelines A3); nothing inside one is the writer's metadiscourse.
    quoted = _quoted(a.doc.text, _possessive_apostrophes(a.doc)) if enabled("MD-H") else None
    all_caps = enabled("MD-G") and a.doc.text.isupper()  # MD-31, once per text

    hits: list[dict[str, Any]] = []
    for run in _segments(a.doc):
        lowers = [t.lower_.replace("’", "'") for t in run]
        i, n = 0, len(run)
        while i < n:
            consumed = 1
            if quoted is not None and _inside(quoted, run[i].idx):
                i += 1
                continue
            for span_len in range(min(max_len, n - i), 0, -1):
                window = tuple(lowers[i : i + span_len])
                entries = index.get(window)
                if not entries:
                    continue
                marker = " ".join(window)
                span = run[i : i + span_len]
                chosen = _assign(marker, entries, span, all_caps)
                if chosen is None:
                    continue  # listed, but not doing metadiscourse work here
                dim, cat = chosen
                hit = {
                    "dimension": dim,
                    "category": cat,
                    "marker": marker,
                    "surface": a.text[span[0].idx : span[-1].idx + len(span[-1].text)],
                    "token_index": span[0].i,
                    "span": [span[0].idx, span[-1].idx + len(span[-1].text)],
                }
                others = sorted({c for _, c in entries} - {cat})
                if others:
                    hit["also_listed_as"] = others
                hits.append(hit)
                consumed = span_len
                break
            i += consumed

    words = a.word_count
    cat_counts: dict[str, int] = defaultdict(int)
    cat_unique: dict[str, set[str]] = defaultdict(set)
    dim_counts: dict[str, int] = defaultdict(int)
    for h in hits:
        cat_counts[h["category"]] += 1
        cat_unique[h["category"]].add(h["marker"])
        dim_counts[h["dimension"]] += 1

    cats_meta = _load()["categories"]
    return {
        "counts": {
            "content_tokens": words,
            "total_hits": len(hits),
            "interactive_hits": dim_counts.get("interactive", 0),
            "interactional_hits": dim_counts.get("interactional", 0),
        },
        "density_per_1000": _density(len(hits), words),
        "per_dimension": {
            dim: {
                "hits": dim_counts.get(dim, 0),
                "density_per_1000": _density(dim_counts.get(dim, 0), words),
            }
            for dim in cats_meta
        },
        "per_category": {
            cat: {
                "dimension": dim,
                "hits": cat_counts.get(cat, 0),
                "unique_markers": len(cat_unique.get(cat, set())),
                "density_per_1000": _density(cat_counts.get(cat, 0), words),
            }
            for dim, cats in cats_meta.items()
            for cat in cats
        },
        "hits": hits,
    }


def _density(n: int, total: int) -> float:
    return round(n / total * 1000, 3) if total else 0.0


def warm() -> None:
    _index()
