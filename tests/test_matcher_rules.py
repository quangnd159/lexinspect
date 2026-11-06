"""Metadiscourse and PHRASE matcher rules: an executable specification.

Each case states, for the hits overlapping `target` in `text`, the complete
multiset of hits in full (`H`: surface, claim, character span and canonical
marker or PHRASE expression); the claim is a metadiscourse category or a PHRASE
rank. None means no overlapping hit. Limitations use a shorthand, (surface,
claim) pairs, or a bare category or rank for one hit whose surface is exactly
`target`.

Kinds:
- "change": a context check decides the result here; without the check the
  result would differ, so the test fails if the check's behaviour disappears;
- "keep": a use the check must not touch, or a use it keeps on purpose;
- "pinned": a marker or expression with no check of its own for this use. The
  case pins the current output, which counts every match of the words. Many
  are uses a stricter check was tried on and dropped because it rejected too
  many genuine markers.

`branch` names the branch of a multi-branch check a case exercises; `BRANCHES`
lists the branches each such check must cover, and with which kinds.

Every sentence was written for these tests or for the 0.4.0 matcher work. None
is copied from a collected text or from the PHRASE sense inventory. Tests are
an executable specification, not evidence of accuracy.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from lexinspect import metadiscourse, phrase
from lexinspect._text import ensure


class H(NamedTuple):
    """One hit in full: its surface, claim (metadiscourse category or PHRASE
    rank), character span, and canonical marker (metadiscourse) or expression
    (PHRASE)."""

    surface: str
    claim: object
    span: tuple[int, int]
    marker: str


class Case(NamedTuple):
    rule: str  # `md-…` for metadiscourse, `ph-…` for PHRASE
    kind: str  # change | keep | pinned
    text: str
    target: str
    expected: object
    branch: str = ""  # the branch of the check the case exercises (`BRANCHES`)


C = Case
CASES = [
    # --- metadiscourse: clause linking and transitions (pinned) -------------------
    # coordinators, whether or not they link propositions
    C(
        "md-coordinators",
        "pinned",
        "They studied rivers, lakes, and wetlands across the region.",
        "and",
        (H("and", "transitions", (28, 31), "and"),),
    ),
    C(
        "md-coordinators",
        "pinned",
        "The samples were small, or in some cases damaged beyond use.",
        "or",
        (H("or", "transitions", (24, 26), "or"),),
    ),
    C(
        "md-coordinators",
        "pinned",
        "The committee approved the budget, and the mayor signed it the next day.",
        "and",
        (H("and", "transitions", (35, 38), "and"),),
    ),
    C(
        "md-coordinators",
        "pinned",
        "The model fits well, but the sample is small.",
        "but",
        (H("but", "transitions", (21, 24), "but"),),
    ),
    C(
        "md-coordinators",
        "pinned",
        "Prices rose sharply; but wages stayed flat.",
        "but",
        (H("but", "transitions", (21, 24), "but"),),
    ),
    C(
        "md-coordinators",
        "pinned",
        "But the argument has a second weakness.",
        "But",
        (H("But", "transitions", (0, 3), "but"),),
    ),
    # non-finite verbs used as noun phrases
    C(
        "md-non-finite-verbs",
        "pinned",
        "Writing or editing such texts takes skill.",
        "or",
        (H("or", "transitions", (8, 10), "or"),),
    ),
    C(
        "md-non-finite-verbs",
        "pinned",
        "Interviewing and recording the witnesses took a week.",
        "and",
        (H("and", "transitions", (13, 16), "and"),),
    ),
    C(
        "md-non-finite-verbs",
        "pinned",
        "Researchers collected and analysed the soil samples.",
        "and",
        (H("and", "transitions", (22, 25), "and"),),
    ),
    C(
        "md-non-finite-verbs",
        "pinned",
        "The council met in March and the plan was approved in May.",
        "and",
        (H("and", "transitions", (25, 28), "and"),),
    ),
    # subordinators; `while` + subjectless participle
    C(
        "md-subordinators",
        "pinned",
        "While walking home, she noticed the fire.",
        "While",
        (H("While", "transitions", (0, 5), "while"),),
    ),
    C(
        "md-subordinators",
        "pinned",
        "Since then, prices have doubled.",
        "Since",
        (H("Since", "transitions", (0, 5), "since"),),
    ),
    C(
        "md-subordinators",
        "pinned",
        "Since the data are incomplete, the estimate is uncertain.",
        "Since",
        (H("Since", "transitions", (0, 5), "since"),),
    ),
    C(
        "md-subordinators",
        "pinned",
        "While the plan has merits, its costs are too high.",
        "While",
        (H("While", "transitions", (0, 5), "while"),),
    ),
    # aspectual `still`
    C(
        "md-still",
        "pinned",
        "Still standing, the bridge remains safe.",
        "Still",
        (H("Still", "transitions", (0, 5), "still"),),
    ),
    C(
        "md-still",
        "pinned",
        "Still, the plan may work.",
        "Still",
        (H("Still", "transitions", (0, 5), "still"),),
    ),
    # `rather than`; corrective `but rather`
    C(
        "md-rather",
        "pinned",
        "The town chose repair rather than replacement.",
        "rather",
        (H("rather", "hedges", (22, 28), "rather"),),
    ),
    C(
        "md-rather",
        "pinned",
        "Rather than wait, they left.",
        "Rather",
        (H("Rather", "transitions", (0, 6), "rather"),),
    ),
    C(
        "md-rather",
        "pinned",
        "The change was not sudden but rather gradual.",
        "rather",
        (H("rather", "hedges", (30, 36), "rather"),),
    ),
    C(
        "md-rather",
        "pinned",
        "The results were rather mixed.",
        "rather",
        (H("rather", "hedges", (17, 23), "rather"),),
    ),
    # `even if`
    C(
        "md-even-if",
        "pinned",
        "Even if costs fall, demand may stay low.",
        "Even",
        (H("Even", "attitude_markers", (0, 4), "even"),),
    ),
    C(
        "md-even-if",
        "pinned",
        "Even experts disagree.",
        "Even",
        (H("Even", "attitude_markers", (0, 4), "even"),),
    ),
    # --- metadiscourse: word-internal hyphens and brackets (pinned) ---------------
    # part of a hyphenated word
    C(
        "md-hyphens-brackets",
        "pinned",
        "The phone became a must-have item.",
        "must",
        (H("must", "attitude_markers", (19, 23), "must"),),
    ),
    C(
        "md-hyphens-brackets",
        "pinned",
        "The pattern was low-then-high.",
        "then",
        (H("then", "transitions", (20, 24), "then"),),
    ),
    # after an opening bracket
    C(
        "md-hyphens-brackets",
        "pinned",
        "The results (still preliminary) look good.",
        "still",
        (H("still", "transitions", (13, 18), "still"),),
    ),
    # marker + participle, and spaced dashes
    C(
        "md-hyphens-brackets",
        "pinned",
        "The so-called reforms changed little.",
        "called",
        (H("called", "code_glosses", (7, 13), "called"),),
    ),
    C(
        "md-hyphens-brackets",
        "pinned",
        "The above-mentioned results support the model.",
        "above",
        (H("The above", "endophoric_markers", (0, 9), "the above"),),
    ),
    C(
        "md-hyphens-brackets",
        "pinned",
        "The vote was close - then the count was redone.",
        "then",
        (H("then", "transitions", (21, 25), "then"),),
    ),
    # --- metadiscourse: frame and endophoric markers (pinned) ---------------------
    # ordinals as clause-initial adverbials
    C(
        "md-ordinals",
        "pinned",
        "First published in 1900, the novel sold slowly.",
        "First",
        (H("First", "frame_markers", (0, 5), "first"),),
    ),
    C(
        "md-ordinals",
        "pinned",
        "Overall survival was 64 per cent.",
        "Overall",
        (H("Overall", "frame_markers", (0, 7), "overall"),),
    ),
    C(
        "md-ordinals",
        "pinned",
        "Firstly, the model ignores taxes.",
        "Firstly",
        (H("Firstly", "frame_markers", (0, 7), "firstly"),),
    ),
    # goal frame markers, whether or not the goal is the present text's
    C(
        "md-goal-frames",
        "pinned",
        "The goal of the game is to score points.",
        "The goal",
        (H("The goal", "frame_markers", (0, 8), "the goal"),),
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The purpose of this ritual is to honour ancestors.",
        "The purpose",
        (H("The purpose", "frame_markers", (0, 11), "the purpose"),),
    ),
    # a relative clause mentioning a paper
    C(
        "md-goal-frames",
        "pinned",
        "The aim described in Smith's paper was to win the election.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The aim of this paper is to compare two methods.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The purpose here is to compare two methods.",
        "The purpose",
        (H("The purpose", "frame_markers", (0, 11), "the purpose"),),
    ),
    # stage labels
    C(
        "md-stage-labels",
        "pinned",
        "We may have to conclude that the record is lost.",
        "to conclude",
        (
            H("to conclude", "frame_markers", (12, 23), "to conclude"),
        ),  # the frame marker's own verb check
    ),
    C(
        "md-stage-labels",
        "pinned",
        "The aim of this plan is to begin construction in May.",
        "to begin",
        (H("to begin", "frame_markers", (24, 32), "to begin"),),
    ),
    C(
        "md-stage-labels",
        "pinned",
        "The purpose of this paper is to summarise the debate.",
        "to summarise",
        (H("to summarise", "frame_markers", (29, 41), "to summarise"),),
    ),
    C(
        "md-stage-labels",
        "pinned",
        "Our aim is to summarise the debate.",
        "to summarise",
        (H("to summarise", "frame_markers", (11, 23), "to summarise"),),
    ),
    C(
        "md-stage-labels",
        "pinned",
        "To conclude, the policy failed.",
        "To conclude",
        (H("To conclude", "frame_markers", (0, 11), "to conclude"),),
    ),
    # `by far` + superlative
    C(
        "md-by-far",
        "pinned",
        "It is by far the largest lake in the country.",
        "by far",
        (H("by far", "frame_markers", (6, 12), "by far"),),
    ),
    # current output only, no claim that this is a frame marker
    C(
        "md-by-far",
        "pinned",
        "The effect was larger by far.",
        "by far",
        (H("by far", "frame_markers", (22, 28), "by far"),),
    ),
    # endophoric nouns with a label in digits or short capitals
    C(
        "md-endophoric-labels",
        "pinned",
        "Leave a comment on the discussion page first.",
        "page",
        (H("page", "endophoric_markers", (34, 38), "page"),),
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "The answer is on page one.",
        "page",
        (H("page", "endophoric_markers", (17, 21), "page"),),
    ),
    # multiword endophoric markers
    C(
        "md-endophoric-labels",
        "pinned",
        "We discuss the report in section 2.",
        "in section 2",
        None,
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "The proof is given in chapter IV.",
        "in chapter IV",
        None,
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "For details see table S2.",
        "see table S2",
        (H("table", "endophoric_markers", (16, 21), "table"),),
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "The full results appear in Table S4.",
        "Table",
        (H("Table", "endophoric_markers", (27, 32), "table"),),
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "The story is told in chapter one.",
        "in chapter one",
        None,
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "What we read in part I forget.",
        "in part I",
        (H("I", "self_mentions", (21, 22), "i"),),
    ),
    # `above`/`below` with prepositional objects and numbers
    C(
        "md-above-below",
        "pinned",
        "The valley looked green from below.",
        "below",
        (H("below", "endophoric_markers", (29, 34), "below"),),
    ),
    C(
        "md-above-below",
        "pinned",
        "The offer applies to people aged 60 and above.",
        "above",
        (H("above", "endophoric_markers", (40, 45), "above"),),
    ),
    C(
        "md-above-below",
        "pinned",
        "The results, as above, favour the second model.",
        "above",
        (H("above", "endophoric_markers", (16, 21), "above"),),
    ),
    C(
        "md-above-below",
        "pinned",
        "The scores, as shown below, rose steadily.",
        "below",
        (H("shown below", "endophoric_markers", (15, 26), "shown below"),),
    ),
    # `above and below`
    C(
        "md-above-below",
        "pinned",
        "As discussed above and below, the estimates differ.",
        "above and below",
        (
            H("above", "endophoric_markers", (13, 18), "above"),
            H("below", "endophoric_markers", (23, 28), "below"),
        ),
    ),
    C(
        "md-above-below",
        "pinned",
        "The evidence presented above and below supports our conclusion.",
        "above and below",
        (
            H("above", "endophoric_markers", (23, 28), "above"),
            H("below", "endophoric_markers", (33, 38), "below"),
        ),
    ),
    # `see` + a labelled part of this text
    C(
        "md-see-labelled-part",
        "pinned",
        "The questionnaire is given in full (see Appendix B).",
        "see",
        (H("see", "engagement_markers", (36, 39), "see"),),
    ),
    C(
        "md-see-labelled-part",
        "pinned",
        "The method is standard (see Smith 2010).",
        "see",
        (H("see", "engagement_markers", (24, 27), "see"),),
    ),
    # --- metadiscourse: code glosses ----------------------------------------------
    # `that is`: relative `that`, clause-opening demonstrative subject
    C(
        "md-that-is",
        "change",
        "This is a method that is widely used.",
        "that is",
        None,
        branch="relative",
    ),
    C(
        "md-that-is",
        "change",
        "That is not the question here.",
        "That is",
        None,
        branch="sentence-start",
    ),
    C(
        "md-that-is",
        "change",
        "I disagree; that is false.",
        "that is",
        None,
        branch="semicolon",
    ),
    C(
        "md-that-is",
        "keep",
        "The tax is regressive, that is, it falls hardest on the poor.",
        "that is",
        (H("that is", "code_glosses", (23, 30), "that is"),),
        branch="rewording-comma",
    ),
    C(
        "md-that-is",
        "keep",
        "That is, the median is the middle value.",
        "That is",
        (H("That is", "code_glosses", (0, 7), "that is"),),
        branch="rewording-initial",
    ),
    # sentence-final rewording `that is` needs no punctuation before it
    C(
        "md-that-is",
        "keep",
        "You can come too, if you pay that is.",
        "that is",
        (H("that is", "code_glosses", (29, 36), "that is"),),
        branch="rewording-final",
    ),
    # degree `particularly`/`especially`
    C(
        "md-degree-words",
        "change",
        "The winter was particularly cold this year.",
        "particularly",
        None,
    ),
    C(
        "md-degree-words",
        "change",
        "The team worked especially hard.",
        "especially",
        None,
    ),
    C(
        "md-degree-words",
        "change",
        "It was an especially good year.",
        "especially",
        None,
    ),
    C(
        "md-degree-words",
        "keep",
        "Many birds, especially swallows, leave in autumn.",
        "especially",
        (H("especially", "code_glosses", (12, 22), "especially"),),
    ),
    C(
        "md-degree-words",
        "keep",
        "Prices rose, particularly in the north.",
        "particularly",
        (H("particularly", "code_glosses", (13, 25), "particularly"),),
    ),
    # `known as` after `become`/`come`/`grow`, matched by form too
    C(
        "md-known-as",
        "change",
        "It became known as the null model.",
        "known as",
        None,
    ),
    C(
        "md-known-as",
        "keep",
        "The method is known as bootstrapping.",
        "known as",
        (H("known as", "code_glosses", (14, 22), "known as"),),
    ),
    # `called` has only its participle check
    C(
        "md-known-as",
        "pinned",
        "This phenomenon is called for convenience a phase transition.",
        "called",
        (H("called", "code_glosses", (19, 25), "called"),),
    ),
    C(
        "md-known-as",
        "pinned",
        "This process is called erosion.",
        "called",
        (H("called", "code_glosses", (16, 22), "called"),),
    ),
    # reformulating `indeed`
    C(
        "md-indeed",
        "change",
        "The plan was costly, or indeed ruinous.",
        "indeed",
        (H("indeed", "code_glosses", (24, 30), "indeed"),),
    ),
    C(
        "md-indeed",
        "change",
        "It was a success, indeed a triumph.",
        "indeed",
        (H("indeed", "code_glosses", (18, 24), "indeed"),),
    ),
    C(
        "md-indeed",
        "keep",
        "It was a bold and indeed reckless choice.",
        "indeed",
        (H("indeed", "boosters", (18, 24), "indeed"),),
    ),
    C(
        "md-indeed",
        "keep",
        "It was cheap and indeed popular.",
        "indeed",
        (H("indeed", "boosters", (17, 23), "indeed"),),
    ),
    # --- metadiscourse: sources and evidentials (pinned) --------------------------
    # evidentials with the present text or study as object
    C(
        "md-evidential-objects",
        "pinned",
        "According to this study, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "Based on our results, we recommend reform.",
        "Based on",
        (H("Based on", "evidentials", (0, 8), "based on"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to Smith, the canal opened in 1820.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    # a demonstrative before a person
    C(
        "md-evidential-objects",
        "pinned",
        "According to this historian, the treaty failed.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    # evidentials with a source as object
    C(
        "md-evidential-objects",
        "pinned",
        "According to the textbook, the reaction is reversible.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to the witness, the door was open.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    # the present study as subject
    C(
        "md-present-study-subject",
        "pinned",
        "This study shows that rents rose.",
        "shows",
        (H("shows that", "evidentials", (11, 21), "shows that"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "This analysis suggests that rents rose.",
        "suggests",
        (H("suggests that", "evidentials", (14, 27), "suggests that"),),
    ),
    # the present study as subject of a reporting verb with `that`
    C(
        "md-present-study-subject",
        "pinned",
        "These findings suggest that rents rose.",
        "suggest",
        (H("suggest", "hedges", (15, 22), "suggest"),),
    ),
    # a source noun with `this`/`current`
    C(
        "md-present-study-subject",
        "pinned",
        "This scientist argues that the result is false.",
        "argues",
        (H("argues that", "evidentials", (15, 26), "argues that"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "The current literature suggests a different explanation.",
        "suggests",
        (H("suggests", "evidentials", (23, 31), "suggests"),),
    ),
    # reporting verbs with a source subject are evidentials
    C(
        "md-source-subject",
        "pinned",
        "Johnson (2015) suggested that the tax was unfair.",
        "suggested",
        (H("suggested", "hedges", (15, 24), "suggested"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "Smith tested the claim and argued that it failed.",
        "argued",
        (H("argued", "hedges", (27, 33), "argued"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "I suggested that the tax was unfair.",
        "suggested",
        (H("suggested", "hedges", (2, 11), "suggested"),),
    ),
    # narrated discovery, `find out`
    C(
        "md-find-out",
        "pinned",
        "When she opened the box, she found that it was empty.",
        "found",
        (H("found", "boosters", (29, 34), "found"),),
    ),
    C(
        "md-find-out",
        "pinned",
        "We found out that the shop was closed.",
        "found",
        (H("found", "boosters", (3, 8), "found"),),
    ),
    C(
        "md-find-out",
        "pinned",
        "We found that response times doubled in every group.",
        "found",
        (H("found", "boosters", (3, 8), "found"),),
    ),
    # --- metadiscourse: stance (pinned) -------------------------------------------
    # `not always`
    C(
        "md-not-always",
        "pinned",
        "Such reforms do not always succeed.",
        "always",
        (H("always", "boosters", (20, 26), "always"),),
    ),
    C(
        "md-not-always",
        "pinned",
        "Such reforms always fail.",
        "always",
        (H("always", "boosters", (13, 19), "always"),),
    ),
    # manner and degree uses; parenthetical disjuncts
    C(
        "md-manner-degree-stance",
        "pinned",
        "She explained the rules clearly.",
        "clearly",
        (H("clearly", "boosters", (24, 31), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "They set a clearly defined goal.",
        "clearly",
        (H("clearly", "boosters", (11, 18), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The results very clearly show a trend.",
        "clearly",
        (H("clearly", "boosters", (17, 24), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "Most surprisingly, the effect reversed.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (5, 17), "surprisingly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "Clearly, the model fails here.",
        "Clearly",
        (H("Clearly", "boosters", (0, 7), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves, clearly, that the model is false.",
        "clearly",
        (H("clearly", "boosters", (21, 28), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The model failed, surprisingly, in every experiment.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The model failed, surprisingly.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (18, 30), "surprisingly"),),
    ),
    # `make (ADV) sure`; the writer as subject
    C(
        "md-make-sure",
        "pinned",
        "Please make sure that the door is locked.",
        "sure",
        (H("sure", "boosters", (12, 16), "sure"),),
    ),
    C(
        "md-make-sure",
        "pinned",
        "It is impossible to make absolutely sure that it holds.",
        "sure",
        (H("sure", "boosters", (36, 40), "sure"),),
    ),
    C(
        "md-make-sure",
        "pinned",
        "They are sure that the vote was fair.",
        "sure",
        (H("sure", "boosters", (9, 13), "sure"),),
    ),
    C(
        "md-make-sure",
        "pinned",
        "I am sure that the vote was fair.",
        "sure",
        (H("sure", "boosters", (5, 9), "sure"),),
    ),
    # epistemic `must` across adverbs; possessive `must have`
    C(
        "md-epistemic-must",
        "pinned",
        "There must surely be another explanation.",
        "must",
        (H("must", "attitude_markers", (6, 10), "must"),),
    ),
    C(
        "md-epistemic-must",
        "pinned",
        "Every member must have a valid card.",
        "must",
        (H("must", "boosters", (13, 17), "must"),),
    ),
    # an adverb between `have` and the participle
    C(
        "md-epistemic-must",
        "pinned",
        "They must have surely been mistaken.",
        "must",
        (H("must", "boosters", (5, 9), "must"),),
    ),
    C(
        "md-epistemic-must",
        "pinned",
        "It must have been a mistake.",
        "must",
        (H("must", "boosters", (3, 7), "must"),),
    ),
    # `agree`/`prefer` of the writer
    C(
        "md-agree-prefer",
        "pinned",
        "Most voters agree with the plan.",
        "agree",
        (H("agree", "attitude_markers", (12, 17), "agree"),),
    ),
    C(
        "md-agree-prefer",
        "pinned",
        "I agree that the plan is fair.",
        "agree",
        (H("agree", "attitude_markers", (2, 7), "agree"),),
    ),
    # passive `expected` + to-infinitive, and other passives
    C(
        "md-passive-expected",
        "pinned",
        "Scores are expected to rise.",
        "expected",
        (H("expected", "attitude_markers", (11, 19), "expected"),),
    ),
    C(
        "md-passive-expected",
        "pinned",
        "The result was expected.",
        "expected",
        (H("expected", "attitude_markers", (15, 23), "expected"),),
    ),
    C(
        "md-passive-expected",
        "pinned",
        "As expected, attendance fell.",
        "expected",
        (H("expected", "attitude_markers", (3, 11), "expected"),),
    ),
    C(
        "md-passive-expected",
        "pinned",
        "The expected profit was small.",
        "expected",
        None,
    ),
    # non-epistemic `possible`
    C(
        "md-possible",
        "pinned",
        "They gave the best possible answer.",
        "possible",
        (H("possible", "hedges", (19, 27), "possible"),),
    ),
    C(
        "md-possible",
        "pinned",
        "We tested all possible combinations.",
        "possible",
        (H("possible", "hedges", (14, 22), "possible"),),
    ),
    C(
        "md-possible",
        "pinned",
        "The grant made it possible to hire staff.",
        "possible",
        (H("possible", "hedges", (18, 26), "possible"),),
    ),
    C(
        "md-possible",
        "pinned",
        "It is possible that the scale is faulty.",
        "possible",
        (H("possible", "hedges", (6, 14), "possible"),),
    ),
    # attitude adjectives
    C(
        "md-attitude-adjectives",
        "pinned",
        "In my view, compulsory voting is desirable for every democracy.",
        "desirable",
        (H("desirable", "attitude_markers", (33, 42), "desirable"),),
    ),
    C(
        "md-attitude-adjectives",
        "pinned",
        "Clean water is essential to human health.",
        "essential",
        (H("essential", "attitude_markers", (15, 24), "essential"),),
    ),
    # --- metadiscourse: reader/writer forms and directives (pinned) ---------------
    # reader forms in infinitives, modals, relative and conditional clauses
    C(
        "md-reader-forms",
        "pinned",
        "Farmers need to consider the weather.",
        "consider",
        (H("consider", "engagement_markers", (16, 24), "consider"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "The birds we see in winter are mostly gulls.",
        "see",
        (H("see", "engagement_markers", (13, 16), "see"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "If you consider the cost, the plan fails.",
        "consider",
        (H("consider", "engagement_markers", (7, 15), "consider"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "Visitors can rest here or consider the view.",
        "consider",
        (H("consider", "engagement_markers", (26, 34), "consider"),),
    ),
    # extraposition with and without an attitude adjective
    C(
        "md-reader-forms",
        "pinned",
        "It is his job to consider every application.",
        "consider",
        (H("consider", "engagement_markers", (17, 25), "consider"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is unlikely to see a recovery this year.",
        "see",
        (H("see", "engagement_markers", (18, 21), "see"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "Consider the case of a small farm.",
        "Consider",
        (H("Consider", "engagement_markers", (0, 8), "consider"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is important to consider the weather.",
        "consider",
        (H("consider", "engagement_markers", (19, 27), "consider"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "You will notice that the scale is logarithmic.",
        "notice",
        (H("notice that", "engagement_markers", (9, 20), "notice that"),),
    ),
    # `US` the country, a text in capitals, lower-case `i`
    C(
        "md-us-and-i",
        "pinned",
        "Exports to the US rose last year.",
        "US",
        # the country name `US` + a past-tense verb reads as exclusive
        # `us`, a known cost
        (H("US", "self_mentions", (15, 17), "us"),),
    ),
    C(
        "md-us-and-i",
        "pinned",
        "US IMPORTS FELL. This is normal.",
        "US",
        # the country name `US` + a past-tense verb reads as exclusive
        # `us`, a known cost
        (H("US", "self_mentions", (0, 2), "us"),),
    ),
    C(
        "md-us-and-i",
        "pinned",
        "Yesterday i went home.",
        "i",
        (H("i", "self_mentions", (10, 11), "i"),),
    ),
    C(
        "md-us-and-i",
        "pinned",
        "LET US NOW TURN TO THE SECOND QUESTION.",
        "LET US",
        (H("LET US", "engagement_markers", (0, 6), "let us"),),
    ),
    C(
        "md-us-and-i",
        "pinned",
        "Let us now turn to the second question.",
        "us",
        (H("Let us", "engagement_markers", (0, 6), "let us"),),
    ),
    # --- metadiscourse: quotation -------------------------------------------------
    C(
        "md-quotation",
        "change",
        'The mayor said, "We must act now."',
        "We",
        None,
        branch="straight-double",
    ),
    C(
        "md-quotation",
        "change",
        "The mayor said, “We must act now.”",
        "We",
        None,
        branch="curly-double",
    ),
    C(
        "md-quotation",
        "change",
        "The mayor said, ‘We must act now.’",
        "We",
        None,
        branch="curly-single",
    ),
    # a single line break doesn't end the quotation
    C(
        "md-quotation",
        "change",
        "He said, “We must act\nnow.”",
        "We",
        None,
        branch="line-break",
    ),
    C(
        "md-quotation",
        "change",
        'Critics call it a "clearly flawed" plan.',
        "clearly",
        None,
        branch="scare-quotes",
    ),
    C(
        "md-quotation",
        "keep",
        "We must all act now, the mayor argued.",
        "We",
        (H("We", "engagement_markers", (0, 2), "we"),),
        branch="outside",
    ),
    # an unmatched mark is ignored at a blank-line paragraph break
    C(
        "md-quotation",
        "keep",
        "He said, “Act now.\n\nWe must all vote.",
        "We",
        (H("We", "engagement_markers", (20, 22), "we"),),
        branch="unmatched-blank-line",
    ),
    # apostrophes: inside a word, and after a plural possessive
    C(
        "md-quotation",
        "keep",
        "The mayor’s view is that we must act.",
        "we",
        (H("we", "engagement_markers", (25, 27), "we"),),
        branch="apostrophe-in-word",
    ),
    C(
        "md-quotation",
        "keep",
        "The voters’ view is that we must act.",
        "we",
        (H("we", "engagement_markers", (25, 27), "we"),),
        branch="possessive-outside",
    ),
    # --- metadiscourse: exclusive we ----------------------------------------------
    C(
        "md-exclusive-we",
        "change",
        "We recruited forty adults from local schools.",
        "We",
        (H("We", "self_mentions", (0, 2), "we"),),
    ),
    C(
        "md-exclusive-we",
        "keep",
        "We all know that habits are hard to break.",
        "We",
        (H("We", "engagement_markers", (0, 2), "we"),),
    ),
    C(
        "md-exclusive-we",
        "keep",
        "Our sample was smaller than planned.",
        "Our",
        (H("Our", "self_mentions", (0, 3), "our"),),
    ),
    # `our` + a research noun outside the own-work nouns stays reader engagement
    C(
        "md-exclusive-we",
        "pinned",
        "Our screen is too bright.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    C(
        "md-exclusive-we",
        "pinned",
        "Our dataset is small.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    C(
        "md-exclusive-we",
        "pinned",
        "Our datasets are small.",
        "Our",
        (H("Our", "engagement_markers", (0, 3), "our"),),
    ),
    # --- phrase: USED TO and THAT IS ----------------------------------------------
    # USED TO (PAST) and USED TO (ACCUSTOMED)
    C(
        "ph-used-to",
        "change",
        "The pump was used to drain the field.",
        "used to",
        None,
    ),
    C(
        "ph-used-to",
        "change",
        "The tool is used to cut glass.",
        "used to",
        None,
    ),
    C(
        "ph-used-to",
        "change",
        "Used to the noise, she slept well.",
        "Used to",
        None,
    ),
    C(
        "ph-used-to",
        "keep",
        "She used to live by the sea.",
        "used to",
        (H("used to", 892, (4, 11), "USED TO (PAST)"),),
    ),
    C(
        "ph-used-to",
        "keep",
        "He is used to the noise.",
        "used to",
        (H("used to", 2752, (6, 13), "USED TO (ACCUSTOMED)"),),
    ),
    C(
        "ph-used-to",
        "keep",
        "They got used to the cold.",
        "used to",
        (H("used to", 2752, (9, 16), "USED TO (ACCUSTOMED)"),),
    ),
    # THAT IS: relative and demonstrative `that is`
    C(
        "ph-that-is",
        "change",
        "This is a method that is widely used.",
        "that is",
        None,
        branch="relative",
    ),
    C(
        "ph-that-is",
        "change",
        "That is not the question here.",
        "That is",
        None,
        branch="sentence-start",
    ),
    C(
        "ph-that-is",
        "change",
        "I disagree; that is false.",
        "that is",
        None,
        branch="semicolon",
    ),
    # THAT IS: rewording `that` tagged RB
    C(
        "ph-that-is",
        "change",
        "It is cheap, that is, it costs little.",
        "that is",
        (H("that is", 1764, (13, 20), "THAT IS (REPHRASING)"),),
        branch="rb-recall",
    ),
    C(
        "ph-that-is",
        "keep",
        "You can come too, if you pay that is.",
        "that is",
        (H("that is", 1764, (29, 36), "THAT IS (REPHRASING)"),),
        branch="rewording-final",
    ),
    C(
        "ph-that-is",
        "keep",
        "You may borrow it if you ask first, that is.",
        "that is",
        (H("that is", 1764, (36, 43), "THAT IS (REPHRASING)"),),
        branch="rewording-final",
    ),
    # PHRASE counts inside quotations; `That is,` opens the quoted clause
    C(
        "ph-that-is",
        "keep",
        "He said, “That is, you must pay.”",
        "That is",
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="rewording-quoted",
    ),
    # --- phrase: entry-specific constructions -------------------------------------
    C(
        "ph-in-a-way",
        "change",
        "She solved it in a way that nobody expected.",
        "in a way",
        None,
    ),
    C(
        "ph-in-a-way",
        "keep",
        "In a way, the delay helped us.",
        "In a way",
        (H("In a way", 2823, (0, 8), "IN A WAY"),),
    ),
    C(
        "ph-kind-of",
        "change",
        "It is a kind of tool for cutting wood.",
        "kind of",
        None,
    ),
    C(
        "ph-kind-of",
        "keep",
        "I was kind of tired after the trip.",
        "kind of",
        (H("kind of", 2445, (6, 13), "KIND OF"),),
    ),
    C(
        "ph-is-to",
        "change",
        "The aim is to finish by May.",
        "is to",
        None,
    ),
    C(
        "ph-is-to",
        "keep",
        "The train is to leave at noon.",
        "is to",
        (H("is to", 845, (10, 15), "IS TO"),),
    ),
    # WEALTH OF, A GOOD
    C(
        "ph-wealth-of-a-good",
        "change",
        "The wealth of the family grew.",
        "wealth of",
        None,
    ),
    C(
        "ph-wealth-of-a-good",
        "keep",
        "The report offers a wealth of detail.",
        "wealth of",
        (H("wealth of", 5306, (20, 29), "WEALTH OF"),),
    ),
    C(
        "ph-wealth-of-a-good",
        "change",
        "It was a good idea.",
        "a good",
        None,
    ),
    C(
        "ph-wealth-of-a-good",
        "keep",
        "We walked a good ten miles.",
        "a good",
        (H("a good", 4259, (10, 16), "A GOOD (‘AT LEAST’)"),),
    ),
    # PUT IT, GET OFF
    C(
        "ph-put-it-get-off",
        "change",
        "The fire was small, so he put it out.",
        "put it",
        None,
    ),
    C(
        "ph-put-it-get-off",
        "keep",
        "To put it simply, the plan failed.",
        "put it",
        (H("put it", 2983, (3, 9), "PUT IT ('SAY')"),),
    ),
    C(
        "ph-put-it-get-off",
        "change",
        "The plane got off the ground late.",
        "got off",
        None,
    ),
    C(
        "ph-put-it-get-off",
        "keep",
        "He got off lightly.",
        "got off",
        (H("got off", 2388, (3, 10), "GET ON/OFF (TRANs)"),),
    ),
    # UP TO inside a longer verb has no check: it counts
    C(
        "ph-put-it-get-off",
        "pinned",
        "We looked up to forty words in each dictionary.",
        "up to",
        (H("up to", 3016, (10, 15), "UP TO (UNTIL)"),),
    ),
    # JUST AS
    C(
        "ph-just-as-as-long-as",
        "change",
        "The tower is just as tall as the church.",
        "just as",
        None,
    ),
    C(
        "ph-just-as-as-long-as",
        "keep",
        "Just as the bell rang, the door opened.",
        "Just as",
        (H("Just as", 5231, (0, 7), "JUST AS (‘WHEN’)"),),
    ),
    # AS LONG AS after a multiplier
    C(
        "ph-just-as-as-long-as",
        "change",
        "The second film is twice as long as the first.",
        "as long as",
        None,
    ),
    C(
        "ph-just-as-as-long-as",
        "keep",
        "You may stay as long as you keep quiet.",
        "as long as",
        (H("as long as", 1931, (13, 23), "AS LONG AS"),),
    ),
    # focusing `only`/`just` is not comparison
    C(
        "ph-just-as-as-long-as",
        "keep",
        "You can stay only as long as you keep quiet.",
        "as long as",
        (H("as long as", 1931, (18, 28), "AS LONG AS"),),
    ),
    C(
        "ph-just-as-as-long-as",
        "change",
        "You can stay just as long as you keep quiet.",
        "just as long as",
        (H("as long as", 1931, (18, 28), "AS LONG AS"),),
    ),
    # FOR ALL has no check: concessives count
    C(
        "ph-for-all",
        "pinned",
        "For all modern medicine’s advances, many diseases remain incurable.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    C(
        "ph-for-all",
        "pinned",
        "For all John’s wealth, he is unhappy.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    C(
        "ph-for-all",
        "pinned",
        "For all science has achieved, much remains unknown.",
        "For all",
        (H("For all", 4471, (0, 7), "FOR ALL ('CONSIDERING')"),),
    ),
    # THE CASE has no check
    C(
        "ph-the-case",
        "pinned",
        "This will remain the case.",
        "the case",
        (H("the case", 2022, (17, 25), "THE CASE ('TRUE')"),),
    ),
    C(
        "ph-the-case",
        "pinned",
        "That is not the case here.",
        "the case",
        (H("the case", 2022, (12, 20), "THE CASE ('TRUE')"),),
    ),
    # THE LATTER has no check
    C(
        "ph-the-latter",
        "pinned",
        "We compared two periods: the latter period had lower inflation.",
        "the latter",
        (H("the latter", 1815, (25, 35), "THE LATTER (anaphor)"),),
    ),
    C(
        "ph-the-latter",
        "pinned",
        "We compared the first and second halves; the latter half showed a decline.",
        "the latter",
        (H("the latter", 1815, (41, 51), "THE LATTER (anaphor)"),),
    ),
    # --- phrase: matching form -----------------------------------------------------
    C(
        "ph-invariable-noun",
        "change",
        "Trade in parts of the region slowed.",
        "in parts",
        None,
    ),
    C(
        "ph-invariable-noun",
        "keep",
        "The plan failed in part because of cost.",
        "in part",
        (H("in part", 2848, (16, 23), "IN PART"),),
    ),
    C(
        "ph-hyphenated-words",
        "change",
        "Several countries regulate trade in common-law jurisdictions.",
        "in common",
        None,
    ),
    C(
        "ph-hyphenated-words",
        "keep",
        "The two plans have much in common.",
        "in common",
        (H("in common", 3457, (24, 33), "IN COMMON"),),
    ),
    # --- further branches ----------------------------------------------------------
    # a demonstrative after a coordinator; self-mention heads; named sources
    C(
        "md-present-study-subject",
        "pinned",
        "This article shows that the policy failed.",
        "shows",
        (H("shows that", "evidentials", (13, 23), "shows that"),),
    ),
    C(
        "md-that-is",
        "change",
        "The plan is cheap, but that is not the point.",
        "that is",
        None,
        branch="coordinator",
    ),
    C(
        "ph-that-is",
        "change",
        "The plan is cheap, but that is not the point.",
        "that is",
        None,
        branch="coordinator",
    ),
    C(
        "md-source-subject",
        "pinned",
        "The data suggest a link.",
        "suggest",
        (H("suggest", "hedges", (9, 16), "suggest"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "Smith and Lee suggest that rents rose.",
        "suggest",
        (H("suggest", "hedges", (14, 21), "suggest"),),
    ),
    # an owner other than the writers, with this/current
    C(
        "md-evidential-objects",
        "pinned",
        "According to Smith's current study, the treatment is ineffective.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to their current model, rents will rise.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to the authors' current study, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to this study by Smith, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "According to our current study, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    # a name in a topic phrase is not an owner
    C(
        "md-evidential-objects",
        "pinned",
        "According to this study of Smith's novels, rents rose.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "Smith's current study suggests that the treatment is ineffective.",
        "suggests",
        (H("suggests that", "evidentials", (22, 35), "suggests that"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "This study by Smith shows that rents rose.",
        "shows",
        (H("shows that", "evidentials", (20, 30), "shows that"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "Our current study shows that rents rose.",
        "shows",
        (H("shows that", "evidentials", (18, 28), "shows that"),),
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "This study by us shows that rents rose.",
        "shows",
        (H("shows that", "evidentials", (17, 27), "shows that"),),
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The aim of Smith's current study is to conclude the investigation.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
    ),
    C(
        "md-stage-labels",
        "pinned",
        "The aim of Smith's current study is to conclude the investigation.",
        "to conclude",
        (H("to conclude", "frame_markers", (36, 47), "to conclude"),),
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The aim of our current study is to compare two methods.",
        "The aim",
        (H("The aim", "frame_markers", (0, 7), "the aim"),),
    ),
    # a self-mention text noun as the object of `according to`
    C(
        "md-evidential-objects",
        "pinned",
        "According to this thesis, the policy failed.",
        "According to",
        (H("According to", "evidentials", (0, 12), "according to"),),
    ),
    # nominal reporting forms with and without a source noun
    C(
        "md-source-subject",
        "pinned",
        "Smith's study suggested that rents rose.",
        "suggested",
        (H("suggested", "hedges", (14, 23), "suggested"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "The Smith study suggested a link.",
        "suggested",
        (H("suggested", "hedges", (16, 25), "suggested"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "John's temperature suggests that he has an infection.",
        "suggests",
        (H("suggests", "hedges", (19, 27), "suggests"),),
    ),
    C(
        "md-source-subject",
        "pinned",
        "John's face suggests that he is angry.",
        "suggests",
        (H("suggests", "hedges", (12, 20), "suggests"),),
    ),
    # passive `expected` with a finite clause
    C(
        "md-passive-expected",
        "pinned",
        "It is expected that scores will rise.",
        "expected",
        (H("expected", "attitude_markers", (6, 14), "expected"),),
    ),
    C(
        "md-passive-expected",
        "pinned",
        "It was widely expected that prices would fall.",
        "expected",
        (H("expected", "attitude_markers", (14, 22), "expected"),),
    ),
    C(
        "md-passive-expected",
        "pinned",
        "The expected value is 3.",
        "expected",
        (H("expected", "attitude_markers", (4, 12), "expected"),),
    ),
    # a straight single opening quote opens the clause
    C(
        "ph-that-is",
        "change",
        "He said, 'That is wrong.'",
        "That is",
        None,
        branch="quote-straight-single",
    ),
    C(
        "md-that-is",
        "change",
        "He said, 'That is wrong.'",
        "That is",
        None,
        branch="quote-straight-single",
    ),
    C(
        "ph-that-is",
        "change",
        "He said, 'That is, in short, wrong.'",
        "That is",
        (H("That is", 1764, (10, 17), "THAT IS (REPHRASING)"),),
        branch="rewording-quoted-straight-single",
    ),
    C(
        "md-that-is",
        "keep",
        "He said, 'That is, in short, wrong.'",
        "That is",
        (H("That is", "code_glosses", (10, 17), "that is"),),
        branch="rewording-quoted-straight-single",
    ),
    # `that is` branches: subordinator, bracket, the other quotation marks
    C(
        "ph-that-is",
        "change",
        "If that is true, the plan fails.",
        "that is",
        None,
        branch="subordinator",
    ),
    C(
        "md-that-is",
        "change",
        "If that is true, the plan fails.",
        "that is",
        None,
        branch="subordinator",
    ),
    C(
        "ph-that-is",
        "change",
        "The plan failed (that is not surprising).",
        "that is",
        None,
        branch="bracket",
    ),
    C(
        "md-that-is",
        "change",
        "The plan failed (that is not surprising).",
        "that is",
        None,
        branch="bracket",
    ),
    C(
        "ph-that-is",
        "change",
        'He said, "That is wrong."',
        "That is",
        None,
        branch="quote-straight-double",
    ),
    C(
        "md-that-is",
        "change",
        'He said, "That is wrong."',
        "That is",
        None,
        branch="quote-straight-double",
    ),
    C(
        "ph-that-is",
        "change",
        "He said, “That is wrong.”",
        "That is",
        None,
        branch="quote-curly-double",
    ),
    C(
        "md-that-is",
        "change",
        "He said, “That is wrong.”",
        "That is",
        None,
        branch="quote-curly-double",
    ),
    C(
        "ph-that-is",
        "change",
        "He said, ‘That is wrong.’",
        "That is",
        None,
        branch="quote-curly-single",
    ),
    C(
        "md-that-is",
        "change",
        "He said, ‘That is wrong.’",
        "That is",
        None,
        branch="quote-curly-single",
    ),
    C(
        "md-that-is",
        "keep",
        "He said, “That is, you must pay.”",
        "That is",
        None,
        branch="rewording-quoted",
    ),
    # disjuncts set off by brackets and paired dashes, as by commas
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves (clearly) that the model is false.",
        "clearly",
        (H("clearly", "boosters", (21, 28), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves (very clearly) that the model is false.",
        "clearly",
        (H("clearly", "boosters", (26, 33), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves—clearly—that the model is false.",
        "clearly",
        (H("clearly", "boosters", (20, 27), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves - clearly - that the model is false.",
        "clearly",
        (H("clearly", "boosters", (22, 29), "clearly"),),
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The model failed — surprisingly.",
        "surprisingly",
        (H("surprisingly", "attitude_markers", (19, 31), "surprisingly"),),
    ),
    # directive frames with adjectives of importance or necessity
    C(
        "md-reader-forms",
        "pinned",
        "It is unfortunate to see children suffer.",
        "see",
        (H("see", "engagement_markers", (21, 24), "see"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is usual to see gulls on this coast.",
        "see",
        (H("see", "engagement_markers", (15, 18), "see"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is essential to note the date.",
        "note",
        (H("note", "engagement_markers", (19, 23), "note"),),
    ),
    # apostrophes and closing marks inside a curly single quotation
    C(
        "md-quotation",
        "change",
        "He said, ‘The students’ work is, clearly, flawed.’",
        "clearly",
        None,
        branch="possessive-in-quote",
    ),
    C(
        "md-quotation",
        "change",
        "He said, ‘It’s clearly flawed.’",
        "clearly",
        None,
        branch="contraction-in-quote",
    ),
    C(
        "md-quotation",
        "change",
        "He said, ‘We must blame the bosses’. Clearly we must.",
        "We",
        None,
        branch="s-final-closer",
    ),
    C(
        "md-quotation",
        "keep",
        "He said, ‘We must blame the bosses’. Clearly we must.",
        "Clearly",
        (H("Clearly", "boosters", (37, 44), "clearly"),),
        branch="s-final-closer",
    ),
    C(
        "md-quotation",
        "change",
        "She wrote, “He called it ‘clearly wrong’ and left.” Clearly we disagree.",
        "clearly",
        None,
        branch="nesting",
    ),
    C(
        "md-quotation",
        "keep",
        "She wrote, “He called it ‘clearly wrong’ and left.” Clearly we disagree.",
        "Clearly",
        (H("Clearly", "boosters", (52, 59), "clearly"),),
        branch="nesting",
    ),
    C(
        "md-quotation",
        "keep",
        "He said, ‘The voters’ choice is clear. We must act.",
        "We",
        (H("We", "engagement_markers", (39, 41), "we"),),
        branch="unmatched-possessive",
    ),
    # --- metadiscourse: more pinned uses ------------------------------------------
    # Current output for uses no check covers.
    C(
        "md-above-below",
        "pinned",
        "The lights shone above and below the bridge.",
        "above",
        "endophoric_markers",
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "The books are arranged according to size.",
        "according to",
        "evidentials",
    ),
    C(
        "md-evidential-objects",
        "pinned",
        "Patients were grouped based on age.",
        "based on",
        "evidentials",
    ),
    C(
        "md-attitude-adjectives",
        "pinned",
        "This protein is important for muscle repair.",
        "important",
        "attitude_markers",
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The aim of this essay is to compare two cities.",
        "The aim",
        "frame_markers",
    ),
    C(
        "md-stage-labels",
        "pinned",
        "Our goal is to summarise the debate.",
        "to summarise",
        "frame_markers",
    ),
    C(
        "md-present-study-subject",
        "pinned",
        "This result shows that rents rose.",
        "shows",
        (("shows that", "evidentials"),),
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is useful to imagine a world without roads.",
        "imagine",
        "engagement_markers",
    ),
    C(
        "md-passive-expected",
        "pinned",
        "Students are expected to attend every class.",
        "expected",
        "attitude_markers",
    ),
    C(
        "md-endophoric-labels",
        "pinned",
        "In Chapter V of his treatise, Locke argues that labour creates property.",
        "In Chapter",
        None,
    ),
    C(
        "md-subordinators",
        "pinned",
        "While admitting the risks, the board approved the plan.",
        "While",
        "transitions",
    ),
    C(
        "md-subordinators",
        "pinned",
        "Since we arrived, it has rained every day.",
        "Since",
        "transitions",
    ),
    C(
        "md-find-out",
        "pinned",
        "Smith and Lee tested the claim, and they found that it held.",
        "found",
        "boosters",
    ),
    C(
        "md-epistemic-must",
        "pinned",
        "He must not have seen the sign.",
        "must",
        "attitude_markers",
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is necessary to consider the cost.",
        "consider",
        "engagement_markers",
    ),
    C(
        "md-reader-forms",
        "pinned",
        "It is crucial to note the date.",
        "note",
        "engagement_markers",
    ),
    C(
        "md-goal-frames",
        "pinned",
        "The aim of this study by Smith is to compare two methods.",
        "The aim",
        "frame_markers",
    ),
    C(
        "md-source-subject",
        "pinned",
        "The NHANES data suggest a link.",
        "suggest",
        "hedges",
    ),
    C(
        "md-source-subject",
        "pinned",
        "Smith's team argued that the method failed.",
        "argued",
        "hedges",
    ),
    C(
        "md-passive-expected",
        "pinned",
        "It is expected that employees wear helmets.",
        "expected",
        "attitude_markers",
    ),
    C(
        "md-manner-degree-stance",
        "pinned",
        "The evidence proves clearly that the model is false.",
        "clearly",
        "boosters",
    ),
]


# Rules with a context check in the matchers. Each needs at least one case that
# the check changes and one it keeps.
CHECKED = {
    "md-that-is",
    "md-degree-words",
    "md-known-as",
    "md-indeed",
    "md-quotation",
    "md-exclusive-we",
    "ph-used-to",
    "ph-that-is",
    "ph-in-a-way",
    "ph-kind-of",
    "ph-is-to",
    "ph-wealth-of-a-good",
    "ph-invariable-noun",
    "ph-put-it-get-off",
    "ph-just-as-as-long-as",
    "ph-hyphenated-words",
}

# Uses with no check of their own: only "pinned" cases.
PINNED = {
    "md-coordinators",
    "md-non-finite-verbs",
    "md-subordinators",
    "md-hyphens-brackets",
    "md-still",
    "md-rather",
    "md-ordinals",
    "md-goal-frames",
    "md-stage-labels",
    "md-by-far",
    "md-endophoric-labels",
    "md-above-below",
    "md-evidential-objects",
    "md-present-study-subject",
    "md-source-subject",
    "md-find-out",
    "md-not-always",
    "md-manner-degree-stance",
    "md-make-sure",
    "md-epistemic-must",
    "md-even-if",
    "md-agree-prefer",
    "md-passive-expected",
    "md-possible",
    "md-reader-forms",
    "md-see-labelled-part",
    "md-us-and-i",
    "md-attitude-adjectives",
    "ph-for-all",
    "ph-the-case",
    "ph-the-latter",
}

# Multi-branch checks: the branches their cases must cover, and the kinds each
# needs. Every case of these checks names its branch.
BRANCHES: dict[str, dict[str, set[str]]] = {
    "md-that-is": {
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
    "ph-that-is": {
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
    "md-quotation": {
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


# Known limitations. Each pins the current output (`now`) and states the right
# answer as a strict expected failure wherever `now` is wrong. A fix that
# corrects one makes its tests fail, and the entry must then be updated. The
# list is not exhaustive.
LIMITATIONS = [
    # entries and markers with no check for these uses
    (
        "ph-for-all",
        "The rule applies for all members.",
        "for all",
        4471,
        None,
        "no check: quantifier `for all` + noun phrase counts as FOR ALL",
    ),
    (
        "ph-the-case",
        "In the case of rain, the match stops.",
        "the case",
        2022,
        None,
        "no check: `in the case of` counts as THE CASE ('TRUE')",
    ),
    (
        "ph-the-latter",
        "In the latter part of the year, sales rose.",
        "the latter",
        1815,
        None,
        "no check: temporal `the latter part` counts as THE LATTER (anaphor)",
    ),
    (
        "ph-put-it-get-off",
        "The team failed to live up to its promise.",
        "up to",
        3016,
        None,
        "no check: UP TO inside `live up to`, a fragment of a longer verb, counts",
    ),
    (
        "ph-just-as-as-long-as",
        "The second film is not as long as the first.",
        "as long as",
        1931,
        None,
        "comparative AS LONG AS with no multiplier counts",
    ),
    (
        "md-known-as",
        "The meeting was called off.",
        "called",
        "code_glosses",
        None,
        "no check: phrasal `called off` counts as a code gloss",
    ),
    (
        "md-exclusive-we",
        "Our survey had a low response rate.",
        "Our",
        "engagement_markers",
        "self_mentions",
        "no check: exclusive `our` + a research noun outside the own-work nouns",
    ),
    # other known costs
    (
        "md-exclusive-we",
        "As we saw above, the effect is small.",
        "we",
        "self_mentions",
        "engagement_markers",
        "inclusive we with a past-tense verb is read as exclusive",
    ),
    (
        "md-degree-words",
        "We use a range of particularly useful tools.",
        "particularly",
        "code_glosses",
        None,
        "degree word not straight after a determiner is read as a gloss",
    ),
    (
        "md-quotation",
        "He said, 'We must act now.'",
        "We",
        "engagement_markers",
        None,
        "straight single quotes are not used for quotation",
    ),
    (
        "ph-that-is",
        "The flat is cheap if you can stand the noise that is.",
        "that is",
        None,
        1764,
        "final rewording `that is` after a noun, parsed as relative (WDT)",
    ),
    (
        "md-quotation",
        "He called them ‘our bosses’ men, and left.",
        "our",
        "engagement_markers",
        None,
        "closing `’` after an s-final word parsed as a possessive: the quote stays open",
    ),
]


def _module(rule: str):
    return phrase if rule.startswith("ph-") else metadiscourse


def _claim(rule: str, h: dict):
    return h["rank"] if rule.startswith("ph-") else h["category"]


def hits(rule: str, text: str, target: str) -> tuple[H, ...]:
    """Every hit overlapping the first occurrence of `target`, in full, sorted."""
    s = text.index(target)
    e = s + len(target)
    found = _module(rule).analyze(text)["hits"]
    name = "phrase" if rule.startswith("ph-") else "marker"
    return tuple(
        sorted(
            H(h["surface"], _claim(rule, h), tuple(h["span"]), h[name])
            for h in found
            if h["span"][0] < e and s < h["span"][1]
        )
    )


def overlapping(rule: str, text: str, target: str) -> tuple[tuple[str, object], ...]:
    """`hits` as sorted (surface, claim) pairs."""
    return tuple(sorted((h.surface, h.claim) for h in hits(rule, text, target)))


def _want(spec, target: str) -> tuple:
    if spec is None:
        return ()
    if isinstance(spec, (str, int)):
        return ((target, spec),)
    return tuple(sorted(spec))


def _full(spec) -> bool:
    """`spec` lists hits in full (`H`), so span and marker are checked too."""
    return spec is None or (isinstance(spec, tuple) and all(isinstance(h, H) for h in spec))


def _got(spec, rule: str, text: str, target: str) -> tuple:
    return hits(rule, text, target) if _full(spec) else overlapping(rule, text, target)


def _ids(cases):
    return [f"{c.rule}-{c.kind}-{c.text[:40]}" for c in cases]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_case(case):
    assert _got(case.expected, case.rule, case.text, case.target) == _want(
        case.expected, case.target
    )


def test_cases_are_well_formed():
    """Every case names a known rule and kind, every checked rule has a case
    its check changes and one it keeps, and a rule with no check has only
    pinned cases."""
    assert not CHECKED & PINNED
    by_rule: dict[str, set[str]] = {}
    for c in CASES:
        assert c.kind in ("change", "keep", "pinned"), c
        assert c.target in c.text, c
        by_rule.setdefault(c.rule, set()).add(c.kind)
    assert set(by_rule) == CHECKED | PINNED
    for rule, kinds in by_rule.items():
        if rule in PINNED:
            assert kinds == {"pinned"}, rule
        else:
            assert {"change", "keep"} <= kinds, rule
    assert all(lim[0] in CHECKED | PINNED for lim in LIMITATIONS)


def test_branches_are_covered():
    """Every declared branch has a case of each kind it needs, and every case
    of a multi-branch check names a declared branch."""
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
    """An opening straight single quote, not a possessive one."""
    from lexinspect._context import _opening_straight_single

    def quote(text):
        return next(t for t in ensure(text, None).doc if t.text == "'")

    assert _opening_straight_single(quote("He said, 'That is wrong.'"))
    assert not _opening_straight_single(quote("The students' view is that it is wrong."))
    assert not _opening_straight_single(quote("We took the Smiths' that is, the car."))


def test_phrase_is_counted_inside_quotations():
    """Quotation removes metadiscourse, never PHRASE hits."""
    text = 'He said, "I used to live there."'
    assert overlapping("ph-used-to", text, "used to") == (("used to", 892),)


# --- known limitations -----------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "text", "target", "now", "right", "why"),
    LIMITATIONS,
    ids=[f"{lim[0]}-{lim[1][:40]}" for lim in LIMITATIONS],
)
def test_limitation_pins_current_output(rule, text, target, now, right, why):
    assert overlapping(rule, text, target) == _want(now, target), why


_WRONG = [
    pytest.param(*lim, id=f"{lim[0]}-{lim[1][:40]}")
    for lim in LIMITATIONS
    if _want(lim[3], lim[2]) != _want(lim[4], lim[2])
]


@pytest.mark.xfail(strict=True, reason="known limitation")
@pytest.mark.parametrize(("rule", "text", "target", "now", "right", "why"), _WRONG)
def test_limitation_right_answer(rule, text, target, now, right, why):
    assert overlapping(rule, text, target) == _want(right, target), why
