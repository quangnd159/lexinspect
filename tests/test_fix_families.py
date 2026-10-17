"""0.4.0 matcher fixes: an executable specification of every rule and branch.

Each case states, for the hits overlapping `target` in `text`, the complete
multiset of hits in full (`H`: surface, claim, character span and canonical
marker or PHRASE expression); the claim is a metadiscourse category or a PHRASE
rank. `expected` is the 0.4.0 result, checked with the case's family alone (and
with all families on unless `expected_all` says otherwise); `before` is the
0.3.3 result, checked with every family off (`only([])`). None means no
overlapping hit. Limitations use a shorthand, (surface, claim) pairs, or a bare
category or rank for one hit whose surface is exactly `target`.

Kinds:
- "change": the rule changes the result (`expected` differs from `before`), so
  the test fails if the rule's behaviour disappears;
- "keep": a use the rule must not touch, or a use it keeps on purpose;
- "retain": a removed rule (Study 4 implementation audit r1): the 0.3.3
  behaviour is kept with every family on.

`branch` names the branch of a multi-branch rule a case exercises; `BRANCHES`
lists the branches each such rule must cover, and with which kinds.

Provenance. Sentences are constructed for these tests, except those marked
"audit-derived" (probes from the independent implementation audit,
.cache/validation/study4_fix040/sol_impl_audit_r1.md) or "audit-derived (r2)"
(its second round, sol_impl_audit_r2.md), both development-exposed and never
held-out evidence, or "guidelines example" (the published labelling
guidelines, docs/validation/study4-guidelines.md); such a label applies to the
case or limitation directly below it. None is taken from the Study 4
development or evaluation texts or copied from the PHRASE sense inventory.

Rule ids and families are those of the Study 4 candidate ledger. Tests are an
executable specification, not evidence of accuracy.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from typing import NamedTuple

import pytest

from lexinspect import metadiscourse, phrase
from lexinspect._fix_families import FAMILIES, enabled, only


class H(NamedTuple):
    """One hit in full: its surface, claim (metadiscourse category or PHRASE
    rank), character span, and canonical marker (metadiscourse) or expression
    (PHRASE)."""

    surface: str
    claim: object
    span: tuple[int, int]
    marker: str


class Case(NamedTuple):
    rule: str
    family: str
    kind: str  # change | keep | retain
    text: str
    target: str
    expected: object
    before: object
    expected_all: object = "same"  # with all families on, if it differs from family alone
    branch: str = ""  # the rule branch the case exercises (`BRANCHES`)


C = Case
CASES = [
    # --- MD-A: clause linking and transitions ------------------------------------
    # MD-01: a coordinator links propositions, a comma alone isn't enough
    C(
        "MD-01",
        "MD-A",
        "change",
        "They studied rivers, lakes, and wetlands across the region.",
        "and",
        None,
        (H("and", "transitions", (28, 31), "and"),),
    ),
    C(
        "MD-01",
        "MD-A",
        "change",
        "The samples were small, or in some cases damaged beyond use.",
        "or",
        None,
        (H("or", "transitions", (24, 26), "or"),),
    ),
    C(
        "MD-01",
        "MD-A",
        "keep",
        "The committee approved the budget, and the mayor signed it the next day.",
        "and",
        (H("and", "transitions", (35, 38), "and"),),
        (H("and", "transitions", (35, 38), "and"),),
    ),
    C(
        "MD-01",
        "MD-A",
        "keep",
        "The model fits well, but the sample is small.",
        "but",
        (H("but", "transitions", (21, 24), "but"),),
        (H("but", "transitions", (21, 24), "but"),),
    ),
    C(
        "MD-01",
        "MD-A",
        "keep",
        "Prices rose sharply; but wages stayed flat.",
        "but",
        (H("but", "transitions", (21, 24), "but"),),
        (H("but", "transitions", (21, 24), "but"),),
    ),
    C(
        "MD-01",
        "MD-A",
        "keep",
        "But the argument has a second weakness.",
        "But",
        (H("But", "transitions", (0, 3), "but"),),
        (H("But", "transitions", (0, 3), "but"),),
    ),
    # MD-02: non-finite verbs used as noun phrases
    C(
        "MD-02",
        "MD-A",
        "change",
        "Writing or editing such texts takes skill.",
        "or",
        None,
        (H("or", "transitions", (8, 10), "or"),),
    ),
    C(
        "MD-02",
        "MD-A",
        "change",
        "Interviewing and recording the witnesses took a week.",
        "and",
        None,
        (H("and", "transitions", (13, 16), "and"),),
    ),
    C(
        "MD-02",
        "MD-A",
        "keep",
        "Researchers collected and analysed the soil samples.",
        "and",
        (H("and", "transitions", (22, 25), "and"),),
        (H("and", "transitions", (22, 25), "and"),),
    ),
    C(
        "MD-02",
        "MD-A",
        "keep",
        "The council met in March and the plan was approved in May.",
        "and",
        (H("and", "transitions", (25, 28), "and"),),
        (H("and", "transitions", (25, 28), "and"),),
    ),
    # MD-03: subordinators only; `while` + subjectless participle
    C(
        "MD-03",
        "MD-A",
        "change",
        "While walking home, she noticed the fire.",
        "While",
        None,
        (H("While", "transitions", (0, 5), "while"),),
    ),
    C(
        "MD-03",
        "MD-A",
        "change",
        "Since then, prices have doubled.",
        "Since",
        None,
        (H("Since", "transitions", (0, 5), "since"),),
    ),
    C(
        "MD-03",
        "MD-A",
        "keep",
        "Since the data are incomplete, the estimate is uncertain.",
        "Since",
        (H("Since", "transitions", (0, 5), "since"),),
        (H("Since", "transitions", (0, 5), "since"),),
    ),
    C(
        "MD-03",
        "MD-A",
        "keep",
        "While the plan has merits, its costs are too high.",
        "While",
        (H("While", "transitions", (0, 5), "while"),),
        (H("While", "transitions", (0, 5), "while"),),
    ),
    # MD-05: aspectual `still`
    # audit-derived (S1)
    C(
        "MD-05",
        "MD-A",
        "change",
        "Still standing, the bridge remains safe.",
        "Still",
        None,
        (H("Still", "transitions", (0, 5), "still"),),
    ),
    C(
        "MD-05",
        "MD-A",
        "keep",
        "Still, the plan may work.",
        "Still",
        (H("Still", "transitions", (0, 5), "still"),),
        (H("Still", "transitions", (0, 5), "still"),),
    ),
    # MD-06: `rather than`; corrective `but rather`
    C(
        "MD-06",
        "MD-A",
        "change",
        "The town chose repair rather than replacement.",
        "rather",
        None,
        (H("rather", "hedges", (22, 28), "rather"),),
    ),
    C(
        "MD-06",
        "MD-A",
        "change",
        "Rather than wait, they left.",
        "Rather",
        None,
        (H("Rather", "transitions", (0, 6), "rather"),),
    ),
    C(
        "MD-06",
        "MD-A",
        "change",
        "The change was not sudden but rather gradual.",
        "rather",
        (H("rather", "transitions", (30, 36), "rather"),),
        (H("rather", "hedges", (30, 36), "rather"),),
    ),
    C(
        "MD-06",
        "MD-A",
        "keep",
        "The results were rather mixed.",
        "rather",
        (H("rather", "hedges", (17, 23), "rather"),),
        (H("rather", "hedges", (17, 23), "rather"),),
    ),
    # MD-25: `even if`
    C(
        "MD-25",
        "MD-A",
        "change",
        "Even if costs fall, demand may stay low.",
        "Even",
        (H("Even", "transitions", (0, 4), "even"),),
        (H("Even", "attitude_markers", (0, 4), "even"),),
    ),
    # guidelines example (Study 4 labelling guidelines A4)
    C(
        "MD-25",
        "MD-A",
        "keep",
        "Even experts disagree.",
        "Even",
        (H("Even", "attitude_markers", (0, 4), "even"),),
        (H("Even", "attitude_markers", (0, 4), "even"),),
    ),
    # --- MD-B: word-internal hyphens and brackets --------------------------------
    # MD-04, part of a hyphenated word
    C(
        "MD-04",
        "MD-B",
        "change",
        "The phone became a must-have item.",
        "must",
        None,
        (H("must", "attitude_markers", (19, 23), "must"),),
    ),
    C(
        "MD-04",
        "MD-B",
        "change",
        "The pattern was low-then-high.",
        "then",
        None,
        (H("then", "transitions", (20, 24), "then"),),
    ),
    # MD-04, an opening bracket opens no clause
    C(
        "MD-04",
        "MD-B",
        "change",
        "The results (still preliminary) look good.",
        "still",
        None,
        (H("still", "transitions", (13, 18), "still"),),
    ),
    # MD-04, marker + participle and spaced dashes keep their reading
    C(
        "MD-04",
        "MD-B",
        "keep",
        "The so-called reforms changed little.",
        "called",
        (H("called", "code_glosses", (7, 13), "called"),),
        (H("called", "code_glosses", (7, 13), "called"),),
    ),
    C(
        "MD-04",
        "MD-B",
        "keep",
        "The above-mentioned results support the model.",
        "above",
        (H("The above", "endophoric_markers", (0, 9), "the above"),),
        (H("The above", "endophoric_markers", (0, 9), "the above"),),
    ),
    C(
        "MD-04",
        "MD-B",
        "keep",
        "The vote was close - then the count was redone.",
        "then",
        (H("then", "transitions", (21, 25), "then"),),
        (H("then", "transitions", (21, 25), "then"),),
    ),
    # --- MD-C: frame and endophoric markers --------------------------------------
    # MD-07: ordinals as clause-initial adverbials
    C(
        "MD-07",
        "MD-C",
        "change",
        "First published in 1900, the novel sold slowly.",
        "First",
        None,
        (H("First", "frame_markers", (0, 5), "first"),),
    ),
    C(
        "MD-07",
        "MD-C",
        "change",
        "Overall survival was 64 per cent.",
        "Overall",
        None,
        (H("Overall", "frame_markers", (0, 7), "overall"),),
    ),
    C(
        "MD-07",
        "MD-C",
        "keep",
        "Firstly, the model ignores taxes.",
        "Firstly",
        (H("Firstly", "frame_markers", (0, 7), "firstly"),),
        (H("Firstly", "frame_markers", (0, 7), "firstly"),),
    ),
    # MD-08: the goal must be recognised as the present text's or study's
    C(
        "MD-08",
        "MD-C",
        "change",
        "The goal of the game is to score points.",
        "The goal",
        None,
        (H("The goal", "frame_markers", (0, 8), "the goal"),),
        branch="not-present",
    ),
    # audit-derived (S2)
    C(
        "MD-08",
        "MD-C",
        "change",
        "The purpose of this ritual is to honour ancestors.",
        "The purpose",
        None,
        (H("The purpose", "frame_markers", (0, 11), "the purpose"),),
        branch="not-present",
    ),
    # a relative clause mentioning a paper doesn't make the aim this text's
    # audit-derived (S2)
    C(
        "MD-08",
        "MD-C",
        "change",
        "The aim described in Smith's paper was to win the election.",
        "The aim",
        None,
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        branch="relative-clause",
    ),
    # guidelines example (Study 4 labelling guidelines A4)
    C(
        "MD-08",
        "MD-C",
        "keep",
        "The aim of this paper is to compare two methods.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        branch="present-of",
    ),
    C(
        "MD-08",
        "MD-C",
        "keep",
        "The purpose here is to compare two methods.",
        "The purpose",
        (H("The purpose", "frame_markers", (0, 11), "the purpose"),),
        (H("The purpose", "frame_markers", (0, 11), "the purpose"),),
        branch="here",
    ),
    # MD-09: stage labels clause-initially or after a present-text goal + `be`
    C(
        "MD-09",
        "MD-C",
        "change",
        "We may have to conclude that the record is lost.",
        "to conclude",
        (H("conclude", "boosters", (15, 23), "conclude"),),  # the 0.3.3 verb check, outside MD-09
        (H("to conclude", "frame_markers", (12, 23), "to conclude"),),
        branch="verb-complement",
    ),
    # audit-derived (S2)
    C(
        "MD-09",
        "MD-C",
        "change",
        "The aim of this plan is to begin construction in May.",
        "to begin",
        None,
        (H("to begin", "frame_markers", (24, 32), "to begin"),),
        branch="other-goal",
    ),
    C(
        "MD-09",
        "MD-C",
        "keep",
        "The purpose of this paper is to summarise the debate.",
        "to summarise",
        (H("to summarise", "frame_markers", (29, 41), "to summarise"),),
        (H("to summarise", "frame_markers", (29, 41), "to summarise"),),
        branch="present-of",
    ),
    C(
        "MD-09",
        "MD-C",
        "keep",
        "Our aim is to summarise the debate.",
        "to summarise",
        (H("to summarise", "frame_markers", (11, 23), "to summarise"),),
        (H("to summarise", "frame_markers", (11, 23), "to summarise"),),
        branch="present-our",
    ),
    C(
        "MD-09",
        "MD-C",
        "keep",
        "To conclude, the policy failed.",
        "To conclude",
        (H("To conclude", "frame_markers", (0, 11), "to conclude"),),
        (H("To conclude", "frame_markers", (0, 11), "to conclude"),),
        branch="initial",
    ),
    # MD-10: `by far` + superlative
    C(
        "MD-10",
        "MD-C",
        "change",
        "It is by far the largest lake in the country.",
        "by far",
        None,
        (H("by far", "frame_markers", (6, 12), "by far"),),
    ),
    # outside the rule's scope, unchanged (no claim that this is a frame marker)
    C(
        "MD-10",
        "MD-C",
        "keep",
        "The effect was larger by far.",
        "by far",
        (H("by far", "frame_markers", (22, 28), "by far"),),
        (H("by far", "frame_markers", (22, 28), "by far"),),
    ),
    # MD-11: a label in digits or short capitals after the marker's last word
    C(
        "MD-11",
        "MD-C",
        "change",
        "Leave a comment on the discussion page first.",
        "page",
        None,
        (H("page", "endophoric_markers", (34, 38), "page"),),
    ),
    C(
        "MD-11",
        "MD-C",
        "change",
        "The answer is on page one.",
        "page",
        None,
        (H("page", "endophoric_markers", (17, 21), "page"),),
    ),
    # MD-11, multiword markers (audit S3)
    # audit-derived (S3)
    C(
        "MD-11",
        "MD-C",
        "change",
        "We discuss the report in section 2.",
        "in section 2",
        (H("in section", "endophoric_markers", (22, 32), "in section"),),
        None,
    ),
    C(
        "MD-11",
        "MD-C",
        "change",
        "The proof is given in chapter IV.",
        "in chapter IV",
        (H("in chapter", "endophoric_markers", (19, 29), "in chapter"),),
        None,
    ),
    C(
        "MD-11",
        "MD-C",
        "change",
        "For details see table S2.",
        "see table S2",
        (H("see table", "endophoric_markers", (12, 21), "see table"),),
        (H("table", "endophoric_markers", (16, 21), "table"),),
    ),
    C(
        "MD-11",
        "MD-C",
        "keep",
        "The full results appear in Table S4.",
        "Table",
        (H("Table", "endophoric_markers", (27, 32), "table"),),
        (H("Table", "endophoric_markers", (27, 32), "table"),),
    ),
    C("MD-11", "MD-C", "keep", "The story is told in chapter one.", "in chapter one", None, None),
    C(
        "MD-11",
        "MD-C",
        "keep",
        "What we read in part I forget.",
        "in part I",
        (H("I", "self_mentions", (21, 22), "i"),),
        (H("I", "self_mentions", (21, 22), "i"),),
    ),
    # MD-12: prepositional objects and numbers
    C(
        "MD-12",
        "MD-C",
        "change",
        "The valley looked green from below.",
        "below",
        None,
        (H("below", "endophoric_markers", (29, 34), "below"),),
    ),
    C(
        "MD-12",
        "MD-C",
        "change",
        "The offer applies to people aged 60 and above.",
        "above",
        None,
        (H("above", "endophoric_markers", (40, 45), "above"),),
    ),
    C(
        "MD-12",
        "MD-C",
        "keep",
        "The results, as above, favour the second model.",
        "above",
        (H("above", "endophoric_markers", (16, 21), "above"),),
        (H("above", "endophoric_markers", (16, 21), "above"),),
    ),
    C(
        "MD-12",
        "MD-C",
        "keep",
        "The scores, as shown below, rose steadily.",
        "below",
        (H("shown below", "endophoric_markers", (15, 26), "shown below"),),
        (H("shown below", "endophoric_markers", (15, 26), "shown below"),),
    ),
    # MD-12 coordination branch removed (audit B8)
    # audit-derived (B8)
    C(
        "MD-12",
        "MD-C",
        "retain",
        "As discussed above and below, the estimates differ.",
        "above and below",
        (
            H("above", "endophoric_markers", (13, 18), "above"),
            H("below", "endophoric_markers", (23, 28), "below"),
        ),
        (
            H("above", "endophoric_markers", (13, 18), "above"),
            H("below", "endophoric_markers", (23, 28), "below"),
        ),
    ),
    # audit-derived (B8)
    C(
        "MD-12",
        "MD-C",
        "retain",
        "The evidence presented above and below supports our conclusion.",
        "above and below",
        (
            H("above", "endophoric_markers", (23, 28), "above"),
            H("below", "endophoric_markers", (33, 38), "below"),
        ),
        (
            H("above", "endophoric_markers", (23, 28), "above"),
            H("below", "endophoric_markers", (33, 38), "below"),
        ),
    ),
    # MD-30: `see` + a labelled part of this text
    C(
        "MD-30",
        "MD-C",
        "change",
        "The questionnaire is given in full (see Appendix B).",
        "see",
        (H("see", "endophoric_markers", (36, 39), "see"),),
        (H("see", "engagement_markers", (36, 39), "see"),),
    ),
    C(
        "MD-30",
        "MD-C",
        "keep",
        "The method is standard (see Smith 2010).",
        "see",
        (H("see", "engagement_markers", (24, 27), "see"),),
        (H("see", "engagement_markers", (24, 27), "see"),),
    ),
    # --- MD-D: code glosses -------------------------------------------------------
    # MD-13: relative `that`, clause-opening demonstrative subject
    C(
        "MD-13",
        "MD-D",
        "change",
        "This is a method that is widely used.",
        "that is",
        None,
        (H("that is", "code_glosses", (17, 24), "that is"),),
        branch="relative",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "That is not the question here.",
        "That is",
        None,
        (H("That is", "code_glosses", (0, 7), "that is"),),
        branch="sentence-start",
    ),
    # audit-derived (B2)
    C(
        "MD-13",
        "MD-D",
        "change",
        "I disagree; that is false.",
        "that is",
        None,
        (H("that is", "code_glosses", (12, 19), "that is"),),
        branch="semicolon",
    ),
    C(
        "MD-13",
        "MD-D",
        "keep",
        "The tax is regressive, that is, it falls hardest on the poor.",
        "that is",
        (H("that is", "code_glosses", (23, 30), "that is"),),
        (H("that is", "code_glosses", (23, 30), "that is"),),
        branch="rewording-comma",
    ),
    C(
        "MD-13",
        "MD-D",
        "keep",
        "That is, the median is the middle value.",
        "That is",
        (H("That is", "code_glosses", (0, 7), "that is"),),
        (H("That is", "code_glosses", (0, 7), "that is"),),
        branch="rewording-initial",
    ),
    # sentence-final rewording `that is` needs no punctuation before it (audit B2)
    C(
        "MD-13",
        "MD-D",
        "keep",
        "You can come too, if you pay that is.",
        "that is",
        (H("that is", "code_glosses", (29, 36), "that is"),),
        (H("that is", "code_glosses", (29, 36), "that is"),),
        branch="rewording-final",
    ),
    # MD-14: degree `particularly`/`especially`
    C(
        "MD-14",
        "MD-D",
        "change",
        "The winter was particularly cold this year.",
        "particularly",
        None,
        (H("particularly", "code_glosses", (15, 27), "particularly"),),
    ),
    C(
        "MD-14",
        "MD-D",
        "change",
        "The team worked especially hard.",
        "especially",
        None,
        (H("especially", "code_glosses", (16, 26), "especially"),),
    ),
    C(
        "MD-14",
        "MD-D",
        "change",
        "It was an especially good year.",
        "especially",
        None,
        (H("especially", "code_glosses", (10, 20), "especially"),),
    ),
    C(
        "MD-14",
        "MD-D",
        "keep",
        "Many birds, especially swallows, leave in autumn.",
        "especially",
        (H("especially", "code_glosses", (12, 22), "especially"),),
        (H("especially", "code_glosses", (12, 22), "especially"),),
    ),
    C(
        "MD-14",
        "MD-D",
        "keep",
        "Prices rose, particularly in the north.",
        "particularly",
        (H("particularly", "code_glosses", (13, 25), "particularly"),),
        (H("particularly", "code_glosses", (13, 25), "particularly"),),
    ),
    # MD-15: `known as` after `become`/`come`/`grow`, by form (audit S1)
    # audit-derived (S1)
    C(
        "MD-15",
        "MD-D",
        "change",
        "It became known as the null model.",
        "known as",
        None,
        (H("known as", "code_glosses", (10, 18), "known as"),),
    ),
    C(
        "MD-15",
        "MD-D",
        "keep",
        "The method is known as bootstrapping.",
        "known as",
        (H("known as", "code_glosses", (14, 22), "known as"),),
        (H("known as", "code_glosses", (14, 22), "known as"),),
    ),
    # MD-15 `called` registration removed (audit B9)
    # audit-derived (B9)
    C(
        "MD-15",
        "MD-D",
        "retain",
        "This phenomenon is called for convenience a phase transition.",
        "called",
        (H("called", "code_glosses", (19, 25), "called"),),
        (H("called", "code_glosses", (19, 25), "called"),),
    ),
    C(
        "MD-15",
        "MD-D",
        "retain",
        "This process is called erosion.",
        "called",
        (H("called", "code_glosses", (16, 22), "called"),),
        (H("called", "code_glosses", (16, 22), "called"),),
    ),
    # MD-21: reformulating `indeed`
    C(
        "MD-21",
        "MD-D",
        "change",
        "The plan was costly, or indeed ruinous.",
        "indeed",
        (H("indeed", "code_glosses", (24, 30), "indeed"),),
        (H("indeed", "boosters", (24, 30), "indeed"),),
    ),
    C(
        "MD-21",
        "MD-D",
        "change",
        "It was a success, indeed a triumph.",
        "indeed",
        (H("indeed", "code_glosses", (18, 24), "indeed"),),
        (H("indeed", "boosters", (18, 24), "indeed"),),
    ),
    C(
        "MD-21",
        "MD-D",
        "keep",
        "It was a bold and indeed reckless choice.",
        "indeed",
        (H("indeed", "boosters", (18, 24), "indeed"),),
        (H("indeed", "boosters", (18, 24), "indeed"),),
    ),
    C(
        "MD-21",
        "MD-D",
        "keep",
        "It was cheap and indeed popular.",
        "indeed",
        (H("indeed", "boosters", (17, 23), "indeed"),),
        (H("indeed", "boosters", (17, 23), "indeed"),),
    ),
    # --- MD-E: sources and evidentials --------------------------------------------
    # MD-16: not with the present text or study as object
    C(
        "MD-16",
        "MD-E",
        "change",
        "According to this study, rents rose.",
        "According to",
        None,
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="present-this",
    ),
    C(
        "MD-16",
        "MD-E",
        "change",
        "Based on our results, we recommend reform.",
        "Based on",
        None,
        (H("Based on", "evidentials", (0, 8), "based on"),),
        branch="present-our",
    ),
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to Smith, the canal opened in 1820.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="name",
    ),
    # a demonstrative doesn't make a person the present work
    # audit-derived (B1)
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to this historian, the treaty failed.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="person-noun",
    ),
    # MD-16 source-object whitelist removed (audit B1/S6)
    # audit-derived (S6)
    C(
        "MD-16",
        "MD-E",
        "retain",
        "According to the textbook, the reaction is reversible.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="whitelist-removed",
    ),
    # audit-derived (S6)
    C(
        "MD-16",
        "MD-E",
        "retain",
        "According to the witness, the door was open.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="whitelist-removed",
    ),
    # MD-17: the present study as subject is not a source
    C(
        "MD-17",
        "MD-E",
        "change",
        "This study shows that rents rose.",
        "shows",
        (H("shows", "boosters", (11, 16), "shows"),),
        (H("shows that", "evidentials", (11, 21), "shows that"),),
        branch="present-study",
    ),
    C(
        "MD-17",
        "MD-E",
        "change",
        "This analysis suggests that rents rose.",
        "suggests",
        (H("suggests", "hedges", (14, 22), "suggests"),),
        (H("suggests that", "evidentials", (14, 27), "suggests that"),),
        branch="present-analysis",
    ),
    # MD-17 in the MD-18 path: the present study's verb is not moved to evidentials
    C(
        "MD-17",
        "MD-E",
        "keep",
        "These findings suggest that rents rose.",
        "suggest",
        (H("suggest", "hedges", (15, 22), "suggest"),),
        (H("suggest", "hedges", (15, 22), "suggest"),),
        branch="present-hedge-path",
    ),
    # a source noun with `this`/`current` stays a source
    # audit-derived (B1)
    C(
        "MD-17",
        "MD-E",
        "keep",
        "This scientist argues that the result is false.",
        "argues",
        (H("argues that", "evidentials", (15, 26), "argues that"),),
        (H("argues that", "evidentials", (15, 26), "argues that"),),
        branch="person-noun",
    ),
    # audit-derived (B1)
    C(
        "MD-17",
        "MD-E",
        "keep",
        "The current literature suggests a different explanation.",
        "suggests",
        (H("suggests", "evidentials", (23, 31), "suggests"),),
        (H("suggests", "evidentials", (23, 31), "suggests"),),
        branch="source-noun",
    ),
    # MD-18: reporting verbs with a source subject are evidentials
    C(
        "MD-18",
        "MD-E",
        "change",
        "Johnson (2015) suggested that the tax was unfair.",
        "suggested",
        (H("suggested", "evidentials", (15, 24), "suggested"),),
        (H("suggested", "hedges", (15, 24), "suggested"),),
        branch="direct-name",
    ),
    C(
        "MD-18",
        "MD-E",
        "change",
        "Smith tested the claim and argued that it failed.",
        "argued",
        (H("argued", "evidentials", (27, 33), "argued"),),
        (H("argued", "hedges", (27, 33), "argued"),),
        branch="coordinated-verb",
    ),
    C(
        "MD-18",
        "MD-E",
        "keep",
        "I suggested that the tax was unfair.",
        "suggested",
        (H("suggested", "hedges", (2, 11), "suggested"),),
        (H("suggested", "hedges", (2, 11), "suggested"),),
        branch="writer",
    ),
    # MD-19: narrated discovery, `find out`
    C(
        "MD-19",
        "MD-E",
        "change",
        "When she opened the box, she found that it was empty.",
        "found",
        None,
        (H("found", "boosters", (29, 34), "found"),),
    ),
    C(
        "MD-19",
        "MD-E",
        "change",
        "We found out that the shop was closed.",
        "found",
        None,
        (H("found", "boosters", (3, 8), "found"),),
    ),
    # guidelines example (Study 4 labelling guidelines A4)
    C(
        "MD-19",
        "MD-E",
        "keep",
        "We found that response times doubled in every group.",
        "found",
        (H("found", "boosters", (3, 8), "found"),),
        (H("found", "boosters", (3, 8), "found"),),
    ),
    # --- MD-F: stance -----------------------------------------------------------------
    # MD-20: `not always`
    C(
        "MD-20",
        "MD-F",
        "change",
        "Such reforms do not always succeed.",
        "always",
        (H("always", "hedges", (20, 26), "always"),),
        (H("always", "boosters", (20, 26), "always"),),
    ),
    C(
        "MD-20",
        "MD-F",
        "keep",
        "Such reforms always fail.",
        "always",
        (H("always", "boosters", (13, 19), "always"),),
        (H("always", "boosters", (13, 19), "always"),),
    ),
    # MD-22: manner and degree uses; parenthetical disjuncts keep stance (audit B10)
    C(
        "MD-22",
        "MD-F",
        "change",
        "She explained the rules clearly.",
        "clearly",
        None,
        (H("clearly", "boosters", (24, 31), "clearly"),),
        branch="manner",
    ),
    C(
        "MD-22",
        "MD-F",
        "change",
        "They set a clearly defined goal.",
        "clearly",
        None,
        (H("clearly", "boosters", (11, 18), "clearly"),),
        branch="attributive",
    ),
    C(
        "MD-22",
        "MD-F",
        "change",
        "The results very clearly show a trend.",
        "clearly",
        None,
        (H("clearly", "boosters", (17, 24), "clearly"),),
        branch="graded",
    ),
    C(
        "MD-22",
        "MD-F",
        "keep",
        "Most surprisingly, the effect reversed.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (5, 17), "surprisingly"),),
        (H("surprisingly", "attitude_markers", (5, 17), "surprisingly"),),
        branch="graded-initial",
    ),
    # guidelines example (Study 4 labelling guidelines A4)
    C(
        "MD-22",
        "MD-F",
        "keep",
        "Clearly, the model fails here.",
        "Clearly",
        (H("Clearly", "boosters", (0, 7), "clearly"),),
        (H("Clearly", "boosters", (0, 7), "clearly"),),
        branch="initial",
    ),
    # audit-derived (B10)
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The evidence proves, clearly, that the model is false.",
        "clearly",
        (H("clearly", "boosters", (21, 28), "clearly"),),
        (H("clearly", "boosters", (21, 28), "clearly"),),
        branch="commas",
    ),
    # audit-derived (B10)
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The model failed, surprisingly, in every experiment.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
        branch="commas",
    ),
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The model failed, surprisingly.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
        branch="comma-final",
    ),
    # MD-23: `make (ADV) sure`; the writer as subject
    C(
        "MD-23",
        "MD-F",
        "change",
        "Please make sure that the door is locked.",
        "sure",
        None,
        (H("sure", "boosters", (12, 16), "sure"),),
    ),
    # audit-derived (S4)
    C(
        "MD-23",
        "MD-F",
        "change",
        "It is impossible to make absolutely sure that it holds.",
        "sure",
        None,
        (H("sure", "boosters", (36, 40), "sure"),),
    ),
    C(
        "MD-23",
        "MD-F",
        "change",
        "They are sure that the vote was fair.",
        "sure",
        None,
        (H("sure", "boosters", (9, 13), "sure"),),
    ),
    C(
        "MD-23",
        "MD-F",
        "keep",
        "I am sure that the vote was fair.",
        "sure",
        (H("sure", "boosters", (5, 9), "sure"),),
        (H("sure", "boosters", (5, 9), "sure"),),
    ),
    # MD-24: epistemic `must` across adverbs; possessive `must have`
    C(
        "MD-24",
        "MD-F",
        "change",
        "There must surely be another explanation.",
        "must",
        (H("must", "boosters", (6, 10), "must"),),
        (H("must", "attitude_markers", (6, 10), "must"),),
    ),
    C(
        "MD-24",
        "MD-F",
        "change",
        "Every member must have a valid card.",
        "must",
        (H("must", "attitude_markers", (13, 17), "must"),),
        (H("must", "boosters", (13, 17), "must"),),
    ),
    # an adverb between `have` and the participle
    # audit-derived (S4)
    C(
        "MD-24",
        "MD-F",
        "keep",
        "They must have surely been mistaken.",
        "must",
        (H("must", "boosters", (5, 9), "must"),),
        (H("must", "boosters", (5, 9), "must"),),
    ),
    C(
        "MD-24",
        "MD-F",
        "keep",
        "It must have been a mistake.",
        "must",
        (H("must", "boosters", (3, 7), "must"),),
        (H("must", "boosters", (3, 7), "must"),),
    ),
    # MD-26: `agree`/`prefer` of the writer
    C(
        "MD-26",
        "MD-F",
        "change",
        "Most voters agree with the plan.",
        "agree",
        None,
        (H("agree", "attitude_markers", (12, 17), "agree"),),
    ),
    C(
        "MD-26",
        "MD-F",
        "keep",
        "I agree that the plan is fair.",
        "agree",
        (H("agree", "attitude_markers", (2, 7), "agree"),),
        (H("agree", "attitude_markers", (2, 7), "agree"),),
    ),
    # MD-27: passive `expected` + to-infinitive hedges (audit S7); other passives keep 0.3.3 (audit r2 B3)
    # guidelines example (Study 4 labelling guidelines A4)
    C(
        "MD-27",
        "MD-F",
        "change",
        "Scores are expected to rise.",
        "expected",
        (H("expected", "hedges", (11, 19), "expected"),),
        (H("expected", "attitude_markers", (11, 19), "expected"),),
        branch="to-infinitive",
    ),
    C(
        "MD-27",
        "MD-F",
        "keep",
        "The result was expected.",
        "expected",
        (H("expected", "attitude_markers", (15, 23), "expected"),),
        (H("expected", "attitude_markers", (15, 23), "expected"),),
        branch="passive-no-complement",
    ),
    C(
        "MD-27",
        "MD-F",
        "keep",
        "As expected, attendance fell.",
        "expected",
        (H("expected", "attitude_markers", (3, 11), "expected"),),
        (H("expected", "attitude_markers", (3, 11), "expected"),),
        branch="as-expected",
    ),
    C(
        "MD-27",
        "MD-F",
        "keep",
        "The expected profit was small.",
        "expected",
        None,
        None,
        branch="attributive",
    ),
    # MD-28: non-epistemic `possible`
    C(
        "MD-28",
        "MD-F",
        "change",
        "They gave the best possible answer.",
        "possible",
        None,
        (H("possible", "hedges", (19, 27), "possible"),),
    ),
    C(
        "MD-28",
        "MD-F",
        "change",
        "We tested all possible combinations.",
        "possible",
        None,
        (H("possible", "hedges", (14, 22), "possible"),),
    ),
    C(
        "MD-28",
        "MD-F",
        "change",
        "The grant made it possible to hire staff.",
        "possible",
        None,
        (H("possible", "hedges", (18, 26), "possible"),),
    ),
    C(
        "MD-28",
        "MD-F",
        "keep",
        "It is possible that the scale is faulty.",
        "possible",
        (H("possible", "hedges", (6, 14), "possible"),),
        (H("possible", "hedges", (6, 14), "possible"),),
    ),
    # SX-03 removed (audit B11)
    # audit-derived (B11)
    C(
        "SX-03",
        "MD-F",
        "retain",
        "In my view, compulsory voting is desirable for every democracy.",
        "desirable",
        (H("desirable", "attitude_markers", (33, 42), "desirable"),),
        (H("desirable", "attitude_markers", (33, 42), "desirable"),),
    ),
    C(
        "SX-03",
        "MD-F",
        "retain",
        "Clean water is essential to human health.",
        "essential",
        (H("essential", "attitude_markers", (15, 24), "essential"),),
        (H("essential", "attitude_markers", (15, 24), "essential"),),
    ),
    # --- MD-G: reader/writer forms and directives ----------------------------------
    # MD-29: infinitives, modals, relative and conditional clauses
    C(
        "MD-29",
        "MD-G",
        "change",
        "Farmers need to consider the weather.",
        "consider",
        None,
        (H("consider", "engagement_markers", (16, 24), "consider"),),
        branch="infinitive",
    ),
    C(
        "MD-29",
        "MD-G",
        "change",
        "The birds we see in winter are mostly gulls.",
        "see",
        None,
        (H("see", "engagement_markers", (13, 16), "see"),),
        branch="relative",
    ),
    C(
        "MD-29",
        "MD-G",
        "change",
        "If you consider the cost, the plan fails.",
        "consider",
        None,
        (H("consider", "engagement_markers", (7, 15), "consider"),),
        branch="conditional",
    ),
    C(
        "MD-29",
        "MD-G",
        "change",
        "Visitors can rest here or consider the view.",
        "consider",
        None,
        (H("consider", "engagement_markers", (26, 34), "consider"),),
        branch="modal",
    ),
    # the extraposition exception needs an attitude adjective
    # audit-derived (S4)
    C(
        "MD-29",
        "MD-G",
        "change",
        "It is his job to consider every application.",
        "consider",
        None,
        (H("consider", "engagement_markers", (17, 25), "consider"),),
        branch="noun-predicate",
    ),
    # audit-derived (S4)
    C(
        "MD-29",
        "MD-G",
        "change",
        "It is unlikely to see a recovery this year.",
        "see",
        None,
        (H("see", "engagement_markers", (18, 21), "see"),),
        branch="non-directive-adjective",
    ),
    C(
        "MD-29",
        "MD-G",
        "keep",
        "Consider the case of a small farm.",
        "Consider",
        (H("Consider", "engagement_markers", (0, 8), "consider"),),
        (H("Consider", "engagement_markers", (0, 8), "consider"),),
        branch="imperative",
    ),
    C(
        "MD-29",
        "MD-G",
        "keep",
        "It is important to consider the weather.",
        "consider",
        (H("consider", "engagement_markers", (19, 27), "consider"),),
        (H("consider", "engagement_markers", (19, 27), "consider"),),
        branch="importance",
    ),
    C(
        "MD-29",
        "MD-G",
        "keep",
        "You will notice that the scale is logarithmic.",
        "notice",
        (H("notice that", "engagement_markers", (9, 20), "notice that"),),
        (H("notice that", "engagement_markers", (9, 20), "notice that"),),
        branch="reader-subject",
    ),
    # MD-31: `US` the country unless the whole text is in capitals (audit M2); lower-case `i`
    C(
        "MD-31",
        "MD-G",
        "change",
        "Exports to the US rose last year.",
        "US",
        None,
        (H("US", "engagement_markers", (15, 17), "us"),),
    ),
    # audit-derived (M2)
    C(
        "MD-31",
        "MD-G",
        "change",
        "US IMPORTS FELL. This is normal.",
        "US",
        None,
        (H("US", "engagement_markers", (0, 2), "us"),),
    ),
    C(
        "MD-31",
        "MD-G",
        "change",
        "Yesterday i went home.",
        "i",
        None,
        (H("i", "self_mentions", (10, 11), "i"),),
    ),
    C(
        "MD-31",
        "MD-G",
        "keep",
        "LET US NOW TURN TO THE SECOND QUESTION.",
        "LET US",
        (H("LET US", "engagement_markers", (0, 6), "let us"),),
        (H("LET US", "engagement_markers", (0, 6), "let us"),),
    ),
    C(
        "MD-31",
        "MD-G",
        "keep",
        "Let us now turn to the second question.",
        "us",
        (H("Let us", "engagement_markers", (0, 6), "let us"),),
        (H("Let us", "engagement_markers", (0, 6), "let us"),),
    ),
    # --- MD-H: quotation -----------------------------------------------------------
    C(
        "MD-32",
        "MD-H",
        "change",
        'The mayor said, "We must act now."',
        "We",
        None,
        (H("We", "engagement_markers", (17, 19), "we"),),
        branch="straight-double",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        "The mayor said, “We must act now.”",
        "We",
        None,
        (H("We", "engagement_markers", (17, 19), "we"),),
        branch="curly-double",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        "The mayor said, ‘We must act now.’",
        "We",
        None,
        (H("We", "engagement_markers", (17, 19), "we"),),
        branch="curly-single",
    ),
    # a single line break doesn't end the quotation
    # audit-derived (S5)
    C(
        "MD-32",
        "MD-H",
        "change",
        "He said, “We must act\nnow.”",
        "We",
        None,
        (H("We", "engagement_markers", (10, 12), "we"),),
        branch="line-break",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        'Critics call it a "clearly flawed" plan.',
        "clearly",
        None,
        (H("clearly", "boosters", (19, 26), "clearly"),),
        branch="scare-quotes",
    ),
    C(
        "MD-32",
        "MD-H",
        "keep",
        "We must all act now, the mayor argued.",
        "We",
        (H("We", "engagement_markers", (0, 2), "we"),),
        (H("We", "engagement_markers", (0, 2), "we"),),
        branch="outside",
    ),
    # an unmatched mark is ignored at a blank-line paragraph break
    C(
        "MD-32",
        "MD-H",
        "keep",
        "He said, “Act now.\n\nWe must all vote.",
        "We",
        (H("We", "engagement_markers", (20, 22), "we"),),
        (H("We", "engagement_markers", (20, 22), "we"),),
        branch="unmatched-blank-line",
    ),
    # apostrophes: inside a word, and after a plural possessive
    C(
        "MD-32",
        "MD-H",
        "keep",
        "The mayor’s view is that we must act.",
        "we",
        (H("we", "engagement_markers", (25, 27), "we"),),
        (H("we", "engagement_markers", (25, 27), "we"),),
        branch="apostrophe-in-word",
    ),
    C(
        "MD-32",
        "MD-H",
        "keep",
        "The voters’ view is that we must act.",
        "we",
        (H("we", "engagement_markers", (25, 27), "we"),),
        (H("we", "engagement_markers", (25, 27), "we"),),
        branch="possessive-outside",
    ),
    # --- MD-I: exclusive we ----------------------------------------------------------
    C(
        "SX-01",
        "MD-I",
        "change",
        "We recruited forty adults from local schools.",
        "We",
        (H("We", "self_mentions", (0, 2), "we"),),
        (H("We", "engagement_markers", (0, 2), "we"),),
    ),
    C(
        "SX-01",
        "MD-I",
        "keep",
        "We all know that habits are hard to break.",
        "We",
        (H("We", "engagement_markers", (0, 2), "we"),),
        (H("We", "engagement_markers", (0, 2), "we"),),
    ),
    C(
        "SX-01",
        "MD-I",
        "keep",
        "Our sample was smaller than planned.",
        "Our",
        (H("Our", "self_mentions", (0, 3), "our"),),
        (H("Our", "self_mentions", (0, 3), "our"),),
    ),
    # SX-01 research-noun branch rolled back (audit S6)
    # audit-derived (S6)
    C(
        "SX-01",
        "MD-I",
        "retain",
        "Our screen is too bright.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    # audit-derived (S6)
    C(
        "SX-01",
        "MD-I",
        "retain",
        "Our dataset is small.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    # audit-derived (S6)
    C(
        "SX-01",
        "MD-I",
        "retain",
        "Our datasets are small.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    # --- PH-A: USED TO and THAT IS -------------------------------------------------
    # PH-01
    C(
        "PH-01",
        "PH-A",
        "change",
        "The pump was used to drain the field.",
        "used to",
        None,
        (H("used to", 892, (13, 20), "USED TO (PAST)"),),
    ),
    C(
        "PH-01",
        "PH-A",
        "change",
        "The tool is used to cut glass.",
        "used to",
        None,
        (H("used to", 892, (12, 19), "USED TO (PAST)"),),
    ),
    C(
        "PH-01",
        "PH-A",
        "change",
        "Used to the noise, she slept well.",
        "Used to",
        None,
        (H("Used to", 2752, (0, 7), "USED TO (ACCUSTOMED)"),),
    ),
    C(
        "PH-01",
        "PH-A",
        "keep",
        "She used to live by the sea.",
        "used to",
        (H("used to", 892, (4, 11), "USED TO (PAST)"),),
        (H("used to", 892, (4, 11), "USED TO (PAST)"),),
    ),
    C(
        "PH-01",
        "PH-A",
        "keep",
        "He is used to the noise.",
        "used to",
        (H("used to", 2752, (6, 13), "USED TO (ACCUSTOMED)"),),
        (H("used to", 2752, (6, 13), "USED TO (ACCUSTOMED)"),),
    ),
    C(
        "PH-01",
        "PH-A",
        "keep",
        "They got used to the cold.",
        "used to",
        (H("used to", 2752, (9, 16), "USED TO (ACCUSTOMED)"),),
        (H("used to", 2752, (9, 16), "USED TO (ACCUSTOMED)"),),
    ),
    # PH-02: relative and demonstrative `that is` (audit B2)
    C(
        "PH-02",
        "PH-A",
        "change",
        "This is a method that is widely used.",
        "that is",
        None,
        (H("that is", 1764, (17, 24), "THAT IS (REPHRASING)"),),
        branch="relative",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "That is not the question here.",
        "That is",
        None,
        (H("That is", 1764, (0, 7), "THAT IS (REPHRASING)"),),
        branch="sentence-start",
    ),
    # audit-derived (B2)
    C(
        "PH-02",
        "PH-A",
        "change",
        "I disagree; that is false.",
        "that is",
        None,
        (H("that is", 1764, (12, 19), "THAT IS (REPHRASING)"),),
        branch="semicolon",
    ),
    # PH-02 recall correction: rewording `that` tagged RB
    C(
        "PH-02",
        "PH-A",
        "change",
        "It is cheap, that is, it costs little.",
        "that is",
        (H("that is", 1764, (13, 20), "THAT IS (REPHRASING)"),),
        None,
        branch="rb-recall",
    ),
    C(
        "PH-02",
        "PH-A",
        "keep",
        "You can come too, if you pay that is.",
        "that is",
        (H("that is", 1764, (29, 36), "THAT IS (REPHRASING)"),),
        (H("that is", 1764, (29, 36), "THAT IS (REPHRASING)"),),
        branch="rewording-final",
    ),
    C(
        "PH-02",
        "PH-A",
        "keep",
        "You may borrow it if you ask first, that is.",
        "that is",
        (H("that is", 1764, (36, 43), "THAT IS (REPHRASING)"),),
        (H("that is", 1764, (36, 43), "THAT IS (REPHRASING)"),),
        branch="rewording-final",
    ),
    # PHRASE counts inside quotations; `That is,` opens the quoted clause
    # audit-derived (B2)
    C(
        "PH-02",
        "PH-A",
        "keep",
        "He said, “That is, you must pay.”",
        "That is",
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="rewording-quoted",
    ),
    # --- PH-B: entry-specific constructions ---------------------------------------
    C(
        "PH-04",
        "PH-B",
        "change",
        "She solved it in a way that nobody expected.",
        "in a way",
        None,
        (H("in a way", 2823, (14, 22), "IN A WAY"),),
    ),
    C(
        "PH-04",
        "PH-B",
        "keep",
        "In a way, the delay helped us.",
        "In a way",
        (H("In a way", 2823, (0, 8), "IN A WAY"),),
        (H("In a way", 2823, (0, 8), "IN A WAY"),),
    ),
    C(
        "PH-05",
        "PH-B",
        "change",
        "It is a kind of tool for cutting wood.",
        "kind of",
        None,
        (H("kind of", 2445, (8, 15), "KIND OF"),),
    ),
    C(
        "PH-05",
        "PH-B",
        "keep",
        "I was kind of tired after the trip.",
        "kind of",
        (H("kind of", 2445, (6, 13), "KIND OF"),),
        (H("kind of", 2445, (6, 13), "KIND OF"),),
    ),
    C(
        "PH-06",
        "PH-B",
        "change",
        "The aim is to finish by May.",
        "is to",
        None,
        (H("is to", 845, (8, 13), "IS TO"),),
    ),
    C(
        "PH-06",
        "PH-B",
        "keep",
        "The train is to leave at noon.",
        "is to",
        (H("is to", 845, (10, 15), "IS TO"),),
        (H("is to", 845, (10, 15), "IS TO"),),
    ),
    # PH-09: WEALTH OF, A GOOD
    C(
        "PH-09",
        "PH-B",
        "change",
        "The wealth of the family grew.",
        "wealth of",
        None,
        (H("wealth of", 5306, (4, 13), "WEALTH OF"),),
    ),
    C(
        "PH-09",
        "PH-B",
        "keep",
        "The report offers a wealth of detail.",
        "wealth of",
        (H("wealth of", 5306, (20, 29), "WEALTH OF"),),
        (H("wealth of", 5306, (20, 29), "WEALTH OF"),),
    ),
    C(
        "PH-09",
        "PH-B",
        "change",
        "It was a good idea.",
        "a good",
        None,
        (H("a good", 4259, (7, 13), "A GOOD (‘AT LEAST’)"),),
    ),
    C(
        "PH-09",
        "PH-B",
        "keep",
        "We walked a good ten miles.",
        "a good",
        (H("a good", 4259, (10, 16), "A GOOD (‘AT LEAST’)"),),
        (H("a good", 4259, (10, 16), "A GOOD (‘AT LEAST’)"),),
    ),
    # PH-11: PUT IT, GET OFF
    C(
        "PH-11",
        "PH-B",
        "change",
        "The fire was small, so he put it out.",
        "put it",
        None,
        (H("put it", 2983, (26, 32), "PUT IT ('SAY')"),),
    ),
    C(
        "PH-11",
        "PH-B",
        "keep",
        "To put it simply, the plan failed.",
        "put it",
        (H("put it", 2983, (3, 9), "PUT IT ('SAY')"),),
        (H("put it", 2983, (3, 9), "PUT IT ('SAY')"),),
    ),
    C(
        "PH-11",
        "PH-B",
        "change",
        "The plane got off the ground late.",
        "got off",
        None,
        (H("got off", 2388, (10, 17), "GET ON/OFF (TRANs)"),),
    ),
    C(
        "PH-11",
        "PH-B",
        "keep",
        "He got off lightly.",
        "got off",
        (H("got off", 2388, (3, 10), "GET ON/OFF (TRANs)"),),
        (H("got off", 2388, (3, 10), "GET ON/OFF (TRANs)"),),
    ),
    # PH-11 UP TO branch removed (audit B6): the occurrence is kept
    # audit-derived (B6)
    C(
        "PH-11",
        "PH-B",
        "retain",
        "We looked up to forty words in each dictionary.",
        "up to",
        (H("up to", 3016, (10, 15), "UP TO (UNTIL)"),),
        (H("up to", 3016, (10, 15), "UP TO (UNTIL)"),),
    ),
    # PH-12: JUST AS
    C(
        "PH-12",
        "PH-B",
        "change",
        "The tower is just as tall as the church.",
        "just as",
        None,
        (H("just as", 5231, (13, 20), "JUST AS (‘WHEN’)"),),
    ),
    C(
        "PH-12",
        "PH-B",
        "keep",
        "Just as the bell rang, the door opened.",
        "Just as",
        (H("Just as", 5231, (0, 7), "JUST AS (‘WHEN’)"),),
        (H("Just as", 5231, (0, 7), "JUST AS (‘WHEN’)"),),
    ),
    # PH-12: AS LONG AS after a multiplier
    C(
        "PH-12",
        "PH-B",
        "change",
        "The second film is twice as long as the first.",
        "as long as",
        None,
        (H("as long as", 1931, (25, 35), "AS LONG AS"),),
    ),
    C(
        "PH-12",
        "PH-B",
        "keep",
        "You may stay as long as you keep quiet.",
        "as long as",
        (H("as long as", 1931, (13, 23), "AS LONG AS"),),
        (H("as long as", 1931, (13, 23), "AS LONG AS"),),
    ),
    # focusing `only`/`just` is not comparison
    # audit-derived (B7)
    C(
        "PH-12",
        "PH-B",
        "keep",
        "You can stay only as long as you keep quiet.",
        "as long as",
        (H("as long as", 1931, (18, 28), "AS LONG AS"),),
        (H("as long as", 1931, (18, 28), "AS LONG AS"),),
    ),
    # audit-derived (B7)
    C(
        "PH-12",
        "PH-B",
        "change",
        "You can stay just as long as you keep quiet.",
        "just as long as",
        (H("as long as", 1931, (18, 28), "AS LONG AS"),),
        (H("just as", 5231, (13, 20), "JUST AS (‘WHEN’)"),),
    ),
    # PH-03 removed (audit B3): concessives keep FOR ALL
    # audit-derived (B3)
    C(
        "PH-03",
        "PH-B",
        "retain",
        "For all modern medicine’s advances, many diseases remain incurable.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    # audit-derived (B3)
    C(
        "PH-03",
        "PH-B",
        "retain",
        "For all John’s wealth, he is unhappy.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    # audit-derived (B3)
    C(
        "PH-03",
        "PH-B",
        "retain",
        "For all science has achieved, much remains unknown.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    # PH-07 removed (audit B4)
    # audit-derived (B4)
    C(
        "PH-07",
        "PH-B",
        "retain",
        "This will remain the case.",
        "the case",
        (H("the case", 2022, (17, 25), "THE CASE ('TRUE')"),),
        (H("the case", 2022, (17, 25), "THE CASE ('TRUE')"),),
    ),
    C(
        "PH-07",
        "PH-B",
        "retain",
        "That is not the case here.",
        "the case",
        (H("the case", 2022, (12, 20), "THE CASE ('TRUE')"),),
        (H("the case", 2022, (12, 20), "THE CASE ('TRUE')"),),
    ),
    # PH-08 removed (audit B5)
    # audit-derived (B5)
    C(
        "PH-08",
        "PH-B",
        "retain",
        "We compared two periods: the latter period had lower inflation.",
        "the latter",
        (H("the latter", 1815, (25, 35), "THE LATTER (anaphor)"),),
        (H("the latter", 1815, (25, 35), "THE LATTER (anaphor)"),),
    ),
    # audit-derived (B5)
    C(
        "PH-08",
        "PH-B",
        "retain",
        "We compared the first and second halves; the latter half showed a decline.",
        "the latter",
        (H("the latter", 1815, (41, 51), "THE LATTER (anaphor)"),),
        (H("the latter", 1815, (41, 51), "THE LATTER (anaphor)"),),
    ),
    # --- PH-C: matching form ----------------------------------------------------------
    C(
        "PH-10",
        "PH-C",
        "change",
        "Trade in parts of the region slowed.",
        "in parts",
        None,
        (H("in parts", 2848, (6, 14), "IN PART"),),
    ),
    C(
        "PH-10",
        "PH-C",
        "keep",
        "The plan failed in part because of cost.",
        "in part",
        (H("in part", 2848, (16, 23), "IN PART"),),
        (H("in part", 2848, (16, 23), "IN PART"),),
    ),
    # audit-derived (S1)
    C(
        "PH-13",
        "PH-C",
        "change",
        "Several countries regulate trade in common-law jurisdictions.",
        "in common",
        None,
        (H("in common", 3457, (33, 42), "IN COMMON"),),
    ),
    C(
        "PH-13",
        "PH-C",
        "keep",
        "The two plans have much in common.",
        "in common",
        (H("in common", 3457, (24, 33), "IN COMMON"),),
        (H("in common", 3457, (24, 33), "IN COMMON"),),
    ),
    # Audit r1 addendum (maintainer): demonstrative after a coordinator; the
    # self-mention heads; MD-18 only for named sources. Guidelines example and
    # constructed sentences.
    C(
        "MD-17",
        "MD-E",
        "change",
        "This article shows that the policy failed.",
        "shows",
        (H("shows", "boosters", (13, 18), "shows"),),
        (H("shows that", "evidentials", (13, 23), "shows that"),),
        branch="present-article",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "The plan is cheap, but that is not the point.",
        "that is",
        None,
        (H("that is", "code_glosses", (23, 30), "that is"),),
        branch="coordinator",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "The plan is cheap, but that is not the point.",
        "that is",
        None,
        (H("that is", 1764, (23, 30), "THAT IS (REPHRASING)"),),
        branch="coordinator",
    ),
    C(
        "MD-18",
        "MD-E",
        "keep",
        "The data suggest a link.",
        "suggest",
        (H("suggest", "hedges", (9, 16), "suggest"),),
        (H("suggest", "hedges", (9, 16), "suggest"),),
        branch="unowned-source",
    ),
    C(
        "MD-18",
        "MD-E",
        "change",
        "Smith and Lee suggest that rents rose.",
        "suggest",
        (H("suggest", "evidentials", (14, 21), "suggest"),),
        (H("suggest", "hedges", (14, 21), "suggest"),),
        branch="coordinated-names",
    ),
    # Audit r2 (maintainer dispositions, AUDIT_R2_DISPOSITIONS.md). Constructed
    # sentences, except those marked "audit-derived (r2)".
    # R2-B1: an owner other than the writers defeats this/current (own_text)
    # audit-derived (r2)
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to Smith's current study, the treatment is ineffective.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="owner-name",
    ),
    # audit-derived (r2)
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to their current model, rents will rise.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="owner-pronoun",
    ),
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to the authors' current study, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="owner-noun",
    ),
    # audit-derived (r2)
    C(
        "MD-16",
        "MD-E",
        "keep",
        "According to this study by Smith, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="owner-by",
    ),
    C(
        "MD-16",
        "MD-E",
        "change",
        "According to our current study, rents rose.",
        "According to",
        None,
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="present-current-our",
    ),
    # a name in a topic phrase is not an owner
    C(
        "MD-16",
        "MD-E",
        "change",
        "According to this study of Smith's novels, rents rose.",
        "According to",
        None,
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="topic-pp",
    ),
    # audit-derived (r2)
    C(
        "MD-17",
        "MD-E",
        "keep",
        "Smith's current study suggests that the treatment is ineffective.",
        "suggests",
        (H("suggests that", "evidentials", (22, 35), "suggests that"),),
        (H("suggests that", "evidentials", (22, 35), "suggests that"),),
        branch="owner-name",
    ),
    # audit-derived (r2)
    C(
        "MD-17",
        "MD-E",
        "keep",
        "This study by Smith shows that rents rose.",
        "shows",
        (H("shows that", "evidentials", (20, 30), "shows that"),),
        (H("shows that", "evidentials", (20, 30), "shows that"),),
        branch="owner-by",
    ),
    C(
        "MD-17",
        "MD-E",
        "change",
        "Our current study shows that rents rose.",
        "shows",
        (H("shows", "boosters", (18, 23), "shows"),),
        (H("shows that", "evidentials", (18, 28), "shows that"),),
        branch="present-current-our",
    ),
    C(
        "MD-17",
        "MD-E",
        "change",
        "This study by us shows that rents rose.",
        "shows",
        (H("shows", "boosters", (17, 22), "shows"),),
        (H("shows that", "evidentials", (17, 27), "shows that"),),
        branch="owner-by-us",
    ),
    # audit-derived (r2)
    C(
        "MD-08",
        "MD-C",
        "change",
        "The aim of Smith's current study is to conclude the investigation.",
        "The aim",
        None,
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        branch="owner-name",
    ),
    # audit-derived (r2)
    C(
        "MD-09",
        "MD-C",
        "change",
        "The aim of Smith's current study is to conclude the investigation.",
        "to conclude",
        None,
        (H("to conclude", "frame_markers", (36, 47), "to conclude"),),
        branch="owner-name",
    ),
    C(
        "MD-08",
        "MD-C",
        "keep",
        "The aim of our current study is to compare two methods.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
        branch="present-current-our",
    ),
    # A2: a self-mention text noun as the object of `according to`
    C(
        "MD-16",
        "MD-E",
        "change",
        "According to this thesis, the policy failed.",
        "According to",
        None,
        (H("According to", "evidentials", (0, 12), "according to"),),
        branch="present-thesis",
    ),
    # R2-B2: the nominal branch of MD-18 needs a source noun
    # audit-derived (r2)
    C(
        "MD-18",
        "MD-E",
        "change",
        "Smith's study suggested that rents rose.",
        "suggested",
        (H("suggested", "evidentials", (14, 23), "suggested"),),
        (H("suggested", "hedges", (14, 23), "suggested"),),
        branch="nominal-source-possessor",
    ),
    C(
        "MD-18",
        "MD-E",
        "change",
        "The Smith study suggested a link.",
        "suggested",
        (H("suggested", "evidentials", (16, 25), "suggested"),),
        (H("suggested", "hedges", (16, 25), "suggested"),),
        branch="nominal-source-compound",
    ),
    # audit-derived (r2)
    C(
        "MD-18",
        "MD-E",
        "keep",
        "John's temperature suggests that he has an infection.",
        "suggests",
        (H("suggests", "hedges", (19, 27), "suggests"),),
        (H("suggests", "hedges", (19, 27), "suggests"),),
        branch="non-source-owned",
    ),
    # audit-derived (r2)
    C(
        "MD-18",
        "MD-E",
        "keep",
        "John's face suggests that he is angry.",
        "suggests",
        (H("suggests", "hedges", (12, 20), "suggests"),),
        (H("suggests", "hedges", (12, 20), "suggests"),),
        branch="non-source-owned",
    ),
    # R2-B3: passive `expected` with a finite clause hedges too
    # audit-derived (r2)
    C(
        "MD-27",
        "MD-F",
        "change",
        "It is expected that scores will rise.",
        "expected",
        (H("expected", "hedges", (6, 14), "expected"),),
        (H("expected", "attitude_markers", (6, 14), "expected"),),
        branch="finite-clause",
    ),
    # audit-derived (r2)
    C(
        "MD-27",
        "MD-F",
        "change",
        "It was widely expected that prices would fall.",
        "expected",
        (H("expected", "hedges", (14, 22), "expected"),),
        (H("expected", "attitude_markers", (14, 22), "expected"),),
        branch="finite-clause-adverb",
    ),
    C(
        "MD-27",
        "MD-F",
        "change",
        "The expected value is 3.",
        "expected",
        None,
        (H("expected", "attitude_markers", (4, 12), "expected"),),
        branch="attributive",
    ),
    # R2-S1: a straight single opening quote opens the clause
    # audit-derived (r2)
    C(
        "PH-02",
        "PH-A",
        "change",
        "He said, 'That is wrong.'",
        "That is",
        None,
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="quote-straight-single",
    ),
    # audit-derived (r2)
    C(
        "MD-13",
        "MD-D",
        "change",
        "He said, 'That is wrong.'",
        "That is",
        None,
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="quote-straight-single",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "He said, 'That is, in short, wrong.'",
        "That is",
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        None,
        branch="rewording-quoted-straight-single",
    ),
    C(
        "MD-13",
        "MD-D",
        "keep",
        "He said, 'That is, in short, wrong.'",
        "That is",
        (H("That is", "code_glosses", (10, 17), "that is"),),
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="rewording-quoted-straight-single",
    ),
    # A1 branches: subordinator, bracket, the other quotation marks
    C(
        "PH-02",
        "PH-A",
        "change",
        "If that is true, the plan fails.",
        "that is",
        None,
        (H("that is", 1764, (3, 10), "THAT IS (REPHRASING)"),),
        branch="subordinator",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "If that is true, the plan fails.",
        "that is",
        None,
        (H("that is", "code_glosses", (3, 10), "that is"),),
        branch="subordinator",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "The plan failed (that is not surprising).",
        "that is",
        None,
        (H("that is", 1764, (17, 24), "THAT IS (REPHRASING)"),),
        branch="bracket",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "The plan failed (that is not surprising).",
        "that is",
        None,
        (H("that is", "code_glosses", (17, 24), "that is"),),
        branch="bracket",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        'He said, "That is wrong."',
        "That is",
        None,
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="quote-straight-double",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        'He said, "That is wrong."',
        "That is",
        None,
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="quote-straight-double",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "He said, “That is wrong.”",
        "That is",
        None,
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="quote-curly-double",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "He said, “That is wrong.”",
        "That is",
        None,
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="quote-curly-double",
    ),
    C(
        "PH-02",
        "PH-A",
        "change",
        "He said, ‘That is wrong.’",
        "That is",
        None,
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="quote-curly-single",
    ),
    C(
        "MD-13",
        "MD-D",
        "change",
        "He said, ‘That is wrong.’",
        "That is",
        None,
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="quote-curly-single",
    ),
    C(
        "MD-13",
        "MD-D",
        "keep",
        "He said, “That is, you must pay.”",
        "That is",
        (H("That is", "code_glosses", (10, 17), "that is"),),
        (H("That is", "code_glosses", (10, 17), "that is"),),
        expected_all=None,  # MD-H: not the writer's metadiscourse inside a quotation
        branch="rewording-quoted",
    ),
    # R2-S2: brackets and paired dashes set a disjunct off, as commas do
    # audit-derived (r2)
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The evidence proves (clearly) that the model is false.",
        "clearly",
        (H("clearly", "boosters", (21, 28), "clearly"),),
        (H("clearly", "boosters", (21, 28), "clearly"),),
        branch="brackets",
    ),
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The evidence proves (very clearly) that the model is false.",
        "clearly",
        (H("clearly", "boosters", (26, 33), "clearly"),),
        (H("clearly", "boosters", (26, 33), "clearly"),),
        branch="brackets",
    ),
    # audit-derived (r2)
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The evidence proves—clearly—that the model is false.",
        "clearly",
        (H("clearly", "boosters", (20, 27), "clearly"),),
        (H("clearly", "boosters", (20, 27), "clearly"),),
        branch="dashes",
    ),
    C(
        "MD-22",
        "MD-F",
        "keep",
        "The evidence proves - clearly - that the model is false.",
        "clearly",
        (H("clearly", "boosters", (22, 29), "clearly"),),
        (H("clearly", "boosters", (22, 29), "clearly"),),
        branch="dashes",
    ),
    C(
        "MD-22",
        "MD-F",
        "change",
        "The model failed — surprisingly.",
        "surprisingly",
        None,
        (H("surprisingly", "attitude_markers", (19, 31), "surprisingly"),),
        branch="single-dash",
    ),
    # R2-S3: only adjectives of importance or necessity make a directive frame
    # audit-derived (r2)
    C(
        "MD-29",
        "MD-G",
        "change",
        "It is unfortunate to see children suffer.",
        "see",
        None,
        (H("see", "engagement_markers", (21, 24), "see"),),
        branch="affective",
    ),
    # audit-derived (r2)
    C(
        "MD-29",
        "MD-G",
        "change",
        "It is usual to see gulls on this coast.",
        "see",
        None,
        (H("see", "engagement_markers", (15, 18), "see"),),
        branch="habitual",
    ),
    C(
        "MD-29",
        "MD-G",
        "keep",
        "It is essential to note the date.",
        "note",
        (H("note", "engagement_markers", (19, 23), "note"),),
        (H("note", "engagement_markers", (19, 23), "note"),),
        branch="necessity",
    ),
    # R2-S4: apostrophes and closing marks inside a curly single quotation
    # audit-derived (r2)
    C(
        "MD-32",
        "MD-H",
        "change",
        "He said, ‘The students’ work is, clearly, flawed.’",
        "clearly",
        None,
        (H("clearly", "boosters", (33, 40), "clearly"),),
        branch="possessive-in-quote",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        "He said, ‘It’s clearly flawed.’",
        "clearly",
        None,
        (H("clearly", "boosters", (15, 22), "clearly"),),
        branch="contraction-in-quote",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        "He said, ‘We must blame the bosses’. Clearly we must.",
        "We",
        None,
        (H("We", "engagement_markers", (10, 12), "we"),),
        branch="s-final-closer",
    ),
    C(
        "MD-32",
        "MD-H",
        "keep",
        "He said, ‘We must blame the bosses’. Clearly we must.",
        "Clearly",
        (H("Clearly", "boosters", (37, 44), "clearly"),),
        (H("Clearly", "boosters", (37, 44), "clearly"),),
        branch="s-final-closer",
    ),
    C(
        "MD-32",
        "MD-H",
        "change",
        "She wrote, “He called it ‘clearly wrong’ and left.” Clearly we disagree.",
        "clearly",
        None,
        (H("clearly", "boosters", (26, 33), "clearly"),),
        branch="nesting",
    ),
    C(
        "MD-32",
        "MD-H",
        "keep",
        "She wrote, “He called it ‘clearly wrong’ and left.” Clearly we disagree.",
        "Clearly",
        (H("Clearly", "boosters", (52, 59), "clearly"),),
        (H("Clearly", "boosters", (52, 59), "clearly"),),
        branch="nesting",
    ),
    C(
        "MD-32",
        "MD-H",
        "keep",
        "He said, ‘The voters’ choice is clear. We must act.",
        "We",
        (H("We", "engagement_markers", (39, 41), "we"),),
        (H("We", "engagement_markers", (39, 41), "we"),),
        branch="unmatched-possessive",
    ),
]


# Rule ids the cases must cover exactly: every rule of the candidate ledger, and
# the rules removed after audit r1, which keep 0.3.3 behaviour.
RULES = (
    {f"MD-{n:02d}" for n in range(1, 33)}
    | {f"PH-{n:02d}" for n in range(1, 14) if n not in (3, 7, 8)}
    | {"SX-01"}
)
REMOVED = {"PH-03", "PH-07", "PH-08", "SX-03"}

# Multi-branch rules touched by the audit r1 addendum (A1-A3) and audit r2: the
# branches their cases must cover, and the kinds each needs. Every case of these
# rules names its branch.
BRANCHES: dict[str, dict[str, set[str]]] = {
    "MD-08": {
        "not-present": {"change"},
        "relative-clause": {"change"},
        "owner-name": {"change"},
        "present-of": {"keep"},
        "here": {"keep"},
        "present-current-our": {"keep"},
    },
    "MD-09": {
        "verb-complement": {"change"},
        "other-goal": {"change"},
        "owner-name": {"change"},
        "present-of": {"keep"},
        "present-our": {"keep"},
        "initial": {"keep"},
    },
    "MD-13": {
        "relative": {"change"},
        "sentence-start": {"change"},
        "semicolon": {"change"},
        "coordinator": {"change"},
        "subordinator": {"change"},
        "bracket": {"change"},
        "quote-straight-double": {"change"},
        "quote-curly-double": {"change"},
        "quote-curly-single": {"change"},
        "quote-straight-single": {"change"},
        "rewording-comma": {"keep"},
        "rewording-initial": {"keep"},
        "rewording-final": {"keep"},
        "rewording-quoted": {"keep"},
        "rewording-quoted-straight-single": {"keep"},
    },
    "PH-02": {
        "relative": {"change"},
        "sentence-start": {"change"},
        "semicolon": {"change"},
        "coordinator": {"change"},
        "subordinator": {"change"},
        "bracket": {"change"},
        "quote-straight-double": {"change"},
        "quote-curly-double": {"change"},
        "quote-curly-single": {"change"},
        "quote-straight-single": {"change"},
        "rb-recall": {"change"},
        "rewording-quoted-straight-single": {"change"},
        "rewording-final": {"keep"},
        "rewording-quoted": {"keep"},
    },
    "MD-16": {
        "present-this": {"change"},
        "present-our": {"change"},
        "present-current-our": {"change"},
        "present-thesis": {"change"},
        "topic-pp": {"change"},
        "name": {"keep"},
        "person-noun": {"keep"},
        "owner-name": {"keep"},
        "owner-pronoun": {"keep"},
        "owner-noun": {"keep"},
        "owner-by": {"keep"},
        "whitelist-removed": {"retain"},
    },
    "MD-17": {
        "present-study": {"change"},
        "present-analysis": {"change"},
        "present-article": {"change"},
        "present-current-our": {"change"},
        "owner-by-us": {"change"},
        "present-hedge-path": {"keep"},
        "person-noun": {"keep"},
        "source-noun": {"keep"},
        "owner-name": {"keep"},
        "owner-by": {"keep"},
    },
    "MD-18": {
        "direct-name": {"change"},
        "coordinated-verb": {"change"},
        "coordinated-names": {"change"},
        "nominal-source-possessor": {"change"},
        "nominal-source-compound": {"change"},
        "writer": {"keep"},
        "unowned-source": {"keep"},
        "non-source-owned": {"keep"},
    },
    "MD-22": {
        "manner": {"change"},
        "attributive": {"change"},
        "graded": {"change"},
        "single-dash": {"change"},
        "graded-initial": {"keep"},
        "initial": {"keep"},
        "commas": {"keep"},
        "comma-final": {"keep"},
        "brackets": {"keep"},
        "dashes": {"keep"},
    },
    "MD-27": {
        "to-infinitive": {"change"},
        "finite-clause": {"change"},
        "finite-clause-adverb": {"change"},
        "attributive": {"change", "keep"},
        "as-expected": {"keep"},
        "passive-no-complement": {"keep"},
    },
    "MD-29": {
        "infinitive": {"change"},
        "relative": {"change"},
        "conditional": {"change"},
        "modal": {"change"},
        "noun-predicate": {"change"},
        "non-directive-adjective": {"change"},
        "affective": {"change"},
        "habitual": {"change"},
        "imperative": {"keep"},
        "importance": {"keep"},
        "necessity": {"keep"},
        "reader-subject": {"keep"},
    },
    "MD-32": {
        "straight-double": {"change"},
        "curly-double": {"change"},
        "curly-single": {"change"},
        "line-break": {"change"},
        "scare-quotes": {"change"},
        "possessive-in-quote": {"change"},
        "contraction-in-quote": {"change"},
        "s-final-closer": {"change", "keep"},
        "nesting": {"change", "keep"},
        "outside": {"keep"},
        "unmatched-blank-line": {"keep"},
        "unmatched-possessive": {"keep"},
        "apostrophe-in-word": {"keep"},
        "possessive-outside": {"keep"},
    },
}


# Known limitations. Each pins the current output under all families, the family
# alone and none (`now`: one value for all three, or a dict per configuration), and
# states the right answer as a strict expected failure wherever `now` is wrong. A
# fix that corrects one makes its tests fail, and the entry must then be updated.
# The list is not exhaustive.
LIMITATIONS = [
    # removed rules: their motivating error classes
    (
        "PH-03",
        "PH-B",
        "The rule applies for all members.",
        "for all",
        4471,
        None,
        "removed: quantifier `for all` + noun phrase counts as FOR ALL",
    ),
    (
        "PH-07",
        "PH-B",
        "In the case of rain, the match stops.",
        "the case",
        2022,
        None,
        "removed: `in the case of` counts as THE CASE ('TRUE')",
    ),
    (
        "PH-08",
        "PH-B",
        "In the latter part of the year, sales rose.",
        "the latter",
        1815,
        None,
        "removed: temporal `the latter part` counts as THE LATTER (anaphor)",
    ),
    (
        "PH-11",
        "PH-B",
        "The team failed to live up to its promise.",
        "up to",
        3016,
        None,
        "removed: UP TO inside `live up to` (C3 fragment) counts",
    ),
    (
        "PH-12",
        "PH-B",
        "The second film is not as long as the first.",
        "as long as",
        1931,
        None,
        "comparative AS LONG AS with no multiplier counts",
    ),
    # audit-derived (B8)
    (
        "MD-12",
        "MD-C",
        "The lights shone above and below the bridge.",
        "above",
        "endophoric_markers",
        None,
        "removed: spatial coordinated `above` counts as endophoric",
    ),
    # audit-derived (B9)
    (
        "MD-15",
        "MD-D",
        "The meeting was called off.",
        "called",
        "code_glosses",
        None,
        "removed: phrasal `called off` counts as a code gloss",
    ),
    (
        "MD-16",
        "MD-E",
        "The books are arranged according to size.",
        "according to",
        "evidentials",
        None,
        "removed: `according to` + a criterion counts as an evidential",
    ),
    (
        "MD-16",
        "MD-E",
        "Patients were grouped based on age.",
        "based on",
        "evidentials",
        None,
        "removed: `based on` + a criterion counts as an evidential",
    ),
    (
        "SX-03",
        "MD-F",
        "This protein is important for muscle repair.",
        "important",
        "attitude_markers",
        None,
        "removed: descriptive `important for` counts as attitude",
    ),
    (
        "SX-01",
        "MD-I",
        "Our survey had a low response rate.",
        "Our",
        "engagement_markers",
        "self_mentions",
        "rolled back: exclusive `our` + a research noun outside the own-work class",
    ),
    # costs of the narrowed present-text recogniser (audit B1, S2)
    (
        "MD-08",
        "MD-C",
        "The aim of this essay is to compare two cities.",
        "The aim",
        {"all": None, "alone": None, "none": "frame_markers"},
        "frame_markers",
        "`essay` is outside the own-work class: the text goal is lost",
    ),
    (
        "MD-09",
        "MD-C",
        "Our goal is to summarise the debate.",
        "to summarise",
        {"all": None, "alone": None, "none": "frame_markers"},
        "frame_markers",
        "`goal` is outside the own-work class: the stage label is lost",
    ),
    (
        "MD-17",
        "MD-E",
        "This result shows that rents rose.",
        "shows",
        (("shows that", "evidentials"),),
        (("shows", "boosters"),),
        "singular `result` is outside the own-work class (writer's own result)",
    ),
    (
        "MD-29",
        "MD-G",
        "It is useful to imagine a world without roads.",
        "imagine",
        {"all": None, "alone": None, "none": "engagement_markers"},
        "engagement_markers",
        "`useful` is not listed as an attitude marker: the directive is lost",
    ),
    # costs of other revised rules
    (
        "MD-27",
        "MD-F",
        "Students are expected to attend every class.",
        "expected",
        {"all": "hedges", "alone": "hedges", "none": "attitude_markers"},
        None,
        "deontic passive `expected` + to-infinitive is read as a hedge",
    ),
    (
        "MD-11",
        "MD-C",
        "In Chapter V of his treatise, Locke argues that labour creates property.",
        "In Chapter",
        {"all": "endophoric_markers", "alone": "endophoric_markers", "none": None},
        None,
        "a labelled chapter of another work is read as endophoric",
    ),
    # other known costs
    (
        "SX-01",
        "MD-I",
        "As we saw above, the effect is small.",
        "we",
        {"all": "self_mentions", "alone": "self_mentions", "none": "engagement_markers"},
        "engagement_markers",
        "inclusive we with a past-tense verb is read as exclusive",
    ),
    (
        "MD-03",
        "MD-A",
        "While admitting the risks, the board approved the plan.",
        "While",
        {"all": None, "alone": None, "none": "transitions"},
        "transitions",
        "concessive while + participle is read as temporal",
    ),
    (
        "MD-03",
        "MD-A",
        "Since we arrived, it has rained every day.",
        "Since",
        "transitions",
        None,
        "temporal finite since-clause counts as a transition",
    ),
    (
        "MD-19",
        "MD-E",
        "Smith and Lee tested the claim, and they found that it held.",
        "found",
        {"all": None, "alone": None, "none": "boosters"},
        "evidentials",
        "they = cited authors: dropped rather than reassigned to evidentials",
    ),
    # guidelines example (Study 4 labelling guidelines A4)
    # audit-derived (§5)
    (
        "MD-14",
        "MD-D",
        "We use a range of particularly useful tools.",
        "particularly",
        "code_glosses",
        None,
        "degree word not straight after a determiner is read as a gloss",
    ),
    (
        "MD-24",
        "MD-F",
        "He must not have seen the sign.",
        "must",
        "attitude_markers",
        "boosters",
        "negated epistemic perfect is read as obligation",
    ),
    # audit-derived (S5)
    (
        "MD-32",
        "MD-H",
        "He said, 'We must act now.'",
        "We",
        "engagement_markers",
        None,
        "straight single quotes are not used for quotation",
    ),
    (
        "PH-02",
        "PH-A",
        "The flat is cheap if you can stand the noise that is.",
        "that is",
        {"all": None, "alone": None, "none": 1764},
        1764,
        "final rewording `that is` after a noun, parsed as relative (WDT)",
    ),
    # audit r2 dispositions
    (
        "MD-29",
        "MD-G",
        "It is necessary to consider the cost.",
        "consider",
        {"all": None, "alone": None, "none": "engagement_markers"},
        "engagement_markers",
        "`necessary` is not an attitude marker: the obligation directive is lost",
    ),
    (
        "MD-29",
        "MD-G",
        "It is crucial to note the date.",
        "note",
        {"all": None, "alone": None, "none": "engagement_markers"},
        "engagement_markers",
        "`crucial` is not an attitude marker: the obligation directive is lost",
    ),
    (
        "MD-08",
        "MD-C",
        "The aim of this study by Smith is to compare two methods.",
        "The aim",
        "frame_markers",
        None,
        "authorial `by` parsed on the goal noun, not the work noun: ownership unseen",
    ),
    (
        "MD-18",
        "MD-E",
        "The NHANES data suggest a link.",
        "suggest",
        {"all": "evidentials", "alone": "evidentials", "none": "hedges"},
        "hedges",
        "a named dataset as owner is read as an outside source",
    ),
    (
        "MD-18",
        "MD-E",
        "Smith's team argued that the method failed.",
        "argued",
        "hedges",
        "evidentials",
        "a person or group noun a name owns is outside the source-noun class: no evidential",
    ),
    (
        "MD-27",
        "MD-F",
        "It is expected that employees wear helmets.",
        "expected",
        {"all": "hedges", "alone": "hedges", "none": "attitude_markers"},
        None,
        "deontic passive `expected` + finite clause is read as a hedge",
    ),
    (
        "MD-22",
        "MD-F",
        "The evidence proves clearly that the model is false.",
        "clearly",
        {"all": None, "alone": None, "none": "boosters"},
        "boosters",
        "unpunctuated postverbal stance adverb is read as manner",
    ),
    (
        "MD-32",
        "MD-H",
        "He called them ‘our bosses’ men, and left.",
        "our",
        "engagement_markers",
        None,
        "closing `’` after an s-final word parsed as a possessive: the quote stays open",
    ),
]


def _module(family: str):
    return phrase if family.startswith("PH") else metadiscourse


def _claim(family: str, h: dict):
    return h["rank"] if family.startswith("PH") else h["category"]


def hits(family: str, text: str, target: str) -> tuple[H, ...]:
    """Every hit overlapping the first occurrence of `target`, in full, sorted."""
    s = text.index(target)
    e = s + len(target)
    found = _module(family).analyze(text)["hits"]
    name = "phrase" if family.startswith("PH") else "marker"
    return tuple(
        sorted(
            H(h["surface"], _claim(family, h), tuple(h["span"]), h[name])
            for h in found
            if h["span"][0] < e and s < h["span"][1]
        )
    )


def overlapping(family: str, text: str, target: str) -> tuple[tuple[str, object], ...]:
    """`hits` as sorted (surface, claim) pairs."""
    return tuple(sorted((h.surface, h.claim) for h in hits(family, text, target)))


def _want(spec, target: str) -> tuple:
    if spec is None:
        return ()
    if isinstance(spec, (str, int)):
        return ((target, spec),)
    return tuple(sorted(spec))


def _full(spec) -> bool:
    """`spec` lists hits in full (`H`), so span and marker are checked too."""
    return spec is None or (isinstance(spec, tuple) and all(isinstance(h, H) for h in spec))


def _got(spec, family: str, text: str, target: str) -> tuple:
    return hits(family, text, target) if _full(spec) else overlapping(family, text, target)


def _ids(cases):
    return [f"{c.rule}-{c.kind}-{c.text[:40]}" for c in cases]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_with_all_families(case):
    spec = case.expected if case.expected_all == "same" else case.expected_all
    assert _got(spec, case.family, case.text, case.target) == _want(spec, case.target)


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_with_its_family_alone(case):
    with only([case.family]):
        got = _got(case.expected, case.family, case.text, case.target)
    assert got == _want(case.expected, case.target)


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_with_no_family_gives_0_3_3(case):
    with only([]):
        got = _got(case.before, case.family, case.text, case.target)
    assert got == _want(case.before, case.target)


def test_cases_are_well_formed():
    """Every change case can detect its rule disappearing, every retain case keeps
    0.3.3, and every rule or removed rule has the cases its kind needs."""
    by_rule: dict[str, set[str]] = {}
    for c in CASES:
        assert c.family in FAMILIES
        assert c.kind in ("change", "keep", "retain")
        assert c.target in c.text
        want, before = _want(c.expected, c.target), _want(c.before, c.target)
        if c.kind == "change":
            assert want != before, c
        if c.kind == "retain":
            assert want == before, c
        by_rule.setdefault(c.rule, set()).add(c.kind)
    assert set(by_rule) == RULES | REMOVED
    for rule, kinds in by_rule.items():
        if rule in REMOVED:
            assert kinds == {"retain"}, rule
        else:
            assert {"change", "keep"} <= kinds, rule


def test_branches_are_covered():
    """Every declared branch has a case of each kind it needs, and every case
    of a multi-branch rule names a declared branch."""
    have: dict[tuple[str, str], set[str]] = {}
    for c in CASES:
        if c.rule in BRANCHES:
            assert c.branch in BRANCHES[c.rule], c
        else:
            assert not c.branch, c
        have.setdefault((c.rule, c.branch), set()).add(c.kind)
    for rule, branches in BRANCHES.items():
        for branch, kinds in branches.items():
            assert kinds <= have.get((rule, branch), set()), (rule, branch)


def test_straight_single_quote_opener():
    """Audit r2 S1: an opening straight single quote, not a possessive one."""
    from lexinspect._context import _opening_straight_single
    from lexinspect._text import ensure

    def quote(text):
        return next(t for t in ensure(text, None).doc if t.text == "'")

    assert _opening_straight_single(quote("He said, 'That is wrong.'"))
    assert not _opening_straight_single(quote("The students' view is that it is wrong."))
    assert not _opening_straight_single(quote("We took the Smiths' that is, the car."))


# --- known limitations -----------------------------------------------------------

_CONFIGS = ("all", "alone", "none")


def _run(config: str, family: str, text: str, target: str):
    if config == "all":
        return overlapping(family, text, target)
    with only([family] if config == "alone" else []):
        return overlapping(family, text, target)


def _now(now, config: str):
    return now[config] if isinstance(now, dict) else now


@pytest.mark.parametrize("config", _CONFIGS)
@pytest.mark.parametrize(
    ("rule", "family", "text", "target", "now", "right", "why"),
    LIMITATIONS,
    ids=[f"{lim[0]}-{lim[2][:40]}" for lim in LIMITATIONS],
)
def test_limitation_pins_current_output(config, rule, family, text, target, now, right, why):
    assert _run(config, family, text, target) == _want(_now(now, config), target), why


_WRONG = [
    pytest.param(config, *lim, id=f"{config}-{lim[0]}-{lim[2][:40]}")
    for lim in LIMITATIONS
    for config in _CONFIGS
    if _want(_now(lim[4], config), lim[3]) != _want(lim[5], lim[3])
]


@pytest.mark.xfail(strict=True, reason="known limitation")
@pytest.mark.parametrize(
    ("config", "rule", "family", "text", "target", "now", "right", "why"), _WRONG
)
def test_limitation_right_answer(config, rule, family, text, target, now, right, why):
    assert _run(config, family, text, target) == _want(right, target), why


# --- the switches ----------------------------------------------------------------


def test_all_families_on_by_default():
    assert all(enabled(f) for f in FAMILIES)


def test_only_restores_on_exit_and_nests():
    with only(["MD-A"]):
        assert enabled("MD-A") and not enabled("PH-A")
        with only([]):
            assert not any(enabled(f) for f in FAMILIES)
        assert enabled("MD-A") and not enabled("PH-A")
    assert all(enabled(f) for f in FAMILIES)


def test_only_restores_when_the_block_raises():
    with pytest.raises(RuntimeError), only(["MD-A"]):
        assert not enabled("PH-A")
        raise RuntimeError
    assert all(enabled(f) for f in FAMILIES)


def test_unknown_family_is_an_error():
    with pytest.raises(KeyError):
        enabled("MD-Z")
    with pytest.raises(KeyError), only(["MD-Z"]):
        pass
    assert all(enabled(f) for f in FAMILIES)


def test_switches_do_not_leak_between_threads():
    seen = {}

    def worker():
        seen["other"] = enabled("MD-A")

    with only([]):
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        seen["here"] = enabled("MD-A")
    assert seen == {"other": True, "here": False}


def test_child_contexts_inherit_and_stay_isolated():
    """Python ContextVar semantics: a task created inside `only(...)` or a copied
    context inherits the setting; its own override doesn't reach its parent or a
    sibling task."""

    async def child(families):
        if families is None:
            return enabled("MD-A")
        with only(families):
            await asyncio.sleep(0)
            return enabled("MD-A")

    async def main():
        with only([]):
            inherited = await asyncio.create_task(child(None))
            via_thread = await asyncio.to_thread(enabled, "MD-A")
        a, b = await asyncio.gather(child(["MD-A"]), child([]))
        return inherited, via_thread, a, b, enabled("MD-A")

    assert asyncio.run(main()) == (False, False, True, False, True)
    with only([]):
        ctx = contextvars.copy_context()
    assert ctx.run(enabled, "MD-A") is False
    assert enabled("MD-A")


def test_results_are_not_cached_across_switches():
    text = "They studied rivers, lakes, and wetlands across the region."
    on = overlapping("MD-A", text, "and")
    with only([]):
        off = overlapping("MD-A", text, "and")
    assert (on, off) == ((), (("and", "transitions"),))
    assert overlapping("MD-A", text, "and") == ()


def test_phrase_is_counted_inside_quotations():
    """MD-H removes metadiscourse in quotations, never PHRASE hits."""
    text = 'He said, "I used to live there."'
    assert overlapping("PH-A", text, "used to") == (("used to", 892),)
    with only(["MD-H"]):
        assert overlapping("PH-A", text, "used to") == (("used to", 892),)
