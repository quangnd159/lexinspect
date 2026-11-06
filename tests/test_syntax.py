"""Syntactic complexity (L2SCA units approximated on spaCy's dependency parse).

Each hand-worked example gives the count L2SCA's Tregex patterns would give on a
correct Stanford parse, and checks that the dependency rules reach the same
number on en_core_web_sm's parse. Examples were chosen so the small model
parses them correctly: they test the rules, not the parser.
"""

from __future__ import annotations

import pytest
from conftest import ACADEMIC, NARRATIVE, analysed

from lexinspect import syntax

UNITS = (
    "words",
    "sentences",
    "clauses",
    "dependent_clauses",
    "t_units",
    "complex_t_units",
    "coordinate_phrases",
    "complex_nominals",
    "verb_phrases",
    "passive_clauses",
)
INDICES = (
    "mls",
    "mlt",
    "mlc",
    "c_s",
    "vp_t",
    "c_t",
    "dc_c",
    "dc_t",
    "t_s",
    "ct_t",
    "cp_t",
    "cp_c",
    "cn_t",
    "cn_c",
)


def run(text: str) -> dict:
    return syntax.analyze(text, analysis=analysed(text))


def counts(text: str) -> dict:
    return run(text)["counts"]


def units(text: str, **expected: int) -> None:
    got = counts(text)
    assert {k: got[k] for k in expected} == expected, text


# --- schema -------------------------------------------------------------------


def test_schema_is_stable():
    out = run("The cat sat on the mat.")
    assert set(out) == {
        "counts",
        "indices",
        "dependency",
        "passive",
        "phrasal",
        "sentences",
        "reliability",
        "validity",
    }
    assert tuple(out["counts"]) == UNITS
    assert tuple(out["indices"]) == INDICES
    assert set(out["dependency"]) == {"mean_dependency_distance", "mean_parse_depth"}
    assert set(out["passive"]) == {"clauses", "share_of_clauses"}
    assert set(out["phrasal"]) == {
        "attributive_adjectives",
        "prepositional_postmodifiers",
        "premodifying_nouns",
        "attributive_adjectives_per_1000_words",
        "prepositional_postmodifiers_per_1000_words",
        "premodifying_nouns_per_1000_words",
    }
    assert set(out["sentences"][0]) == {
        "span",
        "words",
        "clauses",
        "dependent_clauses",
        "t_units",
        "passive",
        "depth",
        "mdd",
    }
    assert set(out["reliability"]) == {"reliable", "notes"}


def test_empty_text():
    out = syntax.analyze("")
    assert all(v == 0 for v in out["counts"].values())
    assert all(v is None for v in out["indices"].values())
    assert out["dependency"] == {"mean_dependency_distance": None, "mean_parse_depth": None}
    assert out["passive"] == {"clauses": 0, "share_of_clauses": None}
    assert out["phrasal"]["attributive_adjectives_per_1000_words"] is None
    assert out["sentences"] == []
    assert out["reliability"]["reliable"] is False


def test_without_shared_analysis_gives_the_same_result():
    text = "I think that he left because she cried."
    assert syntax.analyze(text) == run(text)


# --- clauses, T-units, dependent clauses ----------------------------------------


def test_simple_sentence():
    # L2SCA: one S, one VP, no SBAR, no NP with a modifier (the PP hangs off the verb).
    units(
        "The cat sat on the mat.",
        sentences=1,
        words=6,
        clauses=1,
        t_units=1,
        dependent_clauses=0,
        complex_t_units=0,
        coordinate_phrases=0,
        complex_nominals=0,
        verb_phrases=1,
    )


def test_coordinated_clauses_are_separate_t_units():
    # S(S He came, and, S she left): two clauses, two T-units, no CP (S isn't in CP's list).
    units(
        "He came and she left.",
        clauses=2,
        t_units=2,
        dependent_clauses=0,
        coordinate_phrases=0,
        verb_phrases=2,
    )


def test_coordinated_vp_is_one_clause_and_a_coordinate_phrase():
    # S(NP He, VP(VP came, CC and, VP sat down)): one clause, one VP > S, one VP < CC.
    units("He came and sat down.", clauses=1, t_units=1, coordinate_phrases=1, verb_phrases=1)


def test_clause_coordination_and_np_coordination_together():
    units(
        "We bought bread, cheese and wine, but we forgot the glasses.",
        clauses=2,
        t_units=2,
        coordinate_phrases=1,  # bread, cheese and wine
    )


def test_relative_clause():
    # NP(NP the man, SBAR(who lives here)): DC; the NP containing S is a complex nominal.
    units(
        "The man who lives here bought a car.",
        clauses=2,
        dependent_clauses=1,
        t_units=1,
        complex_t_units=1,
        complex_nominals=1,
    )


def test_zero_relative_clause():
    units("The house that Jack built was sold.", dependent_clauses=1, complex_nominals=1)


def test_adverbial_clause():
    units(
        "I left because she cried.",
        clauses=2,
        dependent_clauses=1,
        t_units=1,
        complex_t_units=1,
        complex_nominals=0,
    )


def test_complement_clause_is_dependent_and_nominal():
    # VP(think, SBAR(that, S)): a DC, and CN2 (SBAR headed by `that` under VP).
    units("I think that he left.", clauses=2, dependent_clauses=1, complex_nominals=1)


def test_whether_clause_is_dependent_but_not_a_complex_nominal():
    # SBAR(IN whether, S): DC yes; CN2 needs WHNP, that/for, or a bare S.
    units("I wonder whether he left.", dependent_clauses=1, complex_nominals=0)


def test_free_relative_under_preposition_is_dependent():
    units("She is good at what she does.", clauses=2, dependent_clauses=1, complex_t_units=1)


def test_stranded_subordinate_clause_is_a_fragment_t_unit():
    # L2SCA's FRAG rule: one T-unit, and the clause is a dependent clause.
    units("Because he was tired.", clauses=1, dependent_clauses=1, t_units=1)


def test_clauses_coordinated_inside_a_dependent_clause_are_dependent():
    # A documented divergence: Tregex counts 0 DCs here (the SBAR's S has no VP).
    units(
        "I left because he came and she cried.",
        clauses=3,
        dependent_clauses=2,
        t_units=1,
        complex_t_units=1,
    )


def test_imperative_is_a_clause():
    # S > ROOT <, (VP <# VB): an imperative is a clause; its coordinated VP is a CP.
    units("Close the door and sit down.", clauses=1, t_units=1, coordinate_phrases=1)


def test_contraction():
    # `don't` is one word (L2SCA's Penn tokens would make it two); clause and DC as usual.
    out = run("I don't know what he said.")
    assert out["counts"]["words"] == 6
    assert out["counts"]["clauses"] == 2
    assert out["counts"]["dependent_clauses"] == 1
    assert out["counts"]["complex_nominals"] == 1  # SBAR headed by WHNP `what` under VP
    # Links over Penn tokens I do n't know what he said, punctuation out:
    # I-know 3, do-know 2, n't-know 1, what-said 2, he-said 1, said-know 3 -> 12 / 6.
    assert out["dependency"]["mean_dependency_distance"] == 2.0
    assert out["sentences"][0]["depth"] == 2  # know -> said -> what


def test_question_with_negated_auxiliary():
    units("Can't you see it?", words=4, clauses=1, t_units=1)


# --- headings and verbless sentences ----------------------------------------------


def test_heading_is_a_sentence_but_not_a_clause_or_t_unit():
    out = run("My Summer Holiday\n\nWe went to the beach.")
    c = out["counts"]
    assert (c["sentences"], c["words"], c["clauses"], c["t_units"]) == (2, 8, 1, 1)
    head, body = out["sentences"]
    assert (head["words"], head["clauses"], head["t_units"]) == (3, 0, 0)
    assert (body["words"], body["clauses"], body["t_units"]) == (5, 1, 1)
    # The heading's words still count in W, as in L2SCA.
    assert out["indices"]["mlt"] == 8.0
    assert out["indices"]["t_s"] == 0.5


def test_verbless_text_has_no_denominators():
    out = run("Thanks!")
    assert out["counts"]["clauses"] == 0
    assert out["indices"]["mlc"] is None
    assert out["indices"]["c_s"] == 0.0
    assert out["sentences"][0]["mdd"] is None  # one word, no links
    assert out["sentences"][0]["depth"] == 0


# --- passives ----------------------------------------------------------------------


def test_passive_clause():
    out = run("The letter was written by John.")
    assert out["counts"]["passive_clauses"] == 1
    assert out["passive"] == {"clauses": 1, "share_of_clauses": 1.0}
    assert out["sentences"][0]["passive"] == 1


def test_passive_share_of_clauses():
    out = run("The house that Jack built was sold.")
    assert out["passive"] == {"clauses": 1, "share_of_clauses": 0.5}


def test_coordinated_passive_vp_is_one_passive_clause():
    units(
        "The data were collected and analysed carefully.",
        clauses=1,
        passive_clauses=1,
        coordinate_phrases=1,
    )


# --- complex nominals -----------------------------------------------------------------


def test_complex_nominals_count_maximal_nps_and_nps_in_pps():
    # NP(NP(NP John 's) old book, PP(on, NP(NP the table, PP(near NP the window)))):
    # the outer NP (POS, JJ, PP) and `the table near the window` (PP); `the window`
    # has no modifier and `John 's` is NP > NP. `big and heavy` is ADJP < CC.
    units(
        "John's old book on the table near the window is big and heavy.",
        complex_nominals=2,
        coordinate_phrases=1,
    )


def test_adjective_and_pp_modifiers():
    # `the old school bus with red seats` (JJ, PP) and `red seats` inside the PP (JJ).
    units("The old school bus with red seats stopped.", complex_nominals=2)


def test_appositive_is_a_complex_nominal():
    units("Paris, the capital of France, is beautiful.", complex_nominals=1)


def test_possessive_pronoun_is_not_a_complex_nominal():
    # Tregex lists POS (`'s`), not PRP$.
    units("His book is here.", complex_nominals=0)


def test_nominal_clause_as_subject():
    units("What he said is true.", clauses=2, dependent_clauses=1, complex_nominals=1)


def test_infinitive_subject():
    # S < (VP <# TO) $+ VP: CN3, and the infinitive is a non-finite VP.
    units("To err is human.", clauses=1, complex_nominals=1, verb_phrases=2)


def test_gerund_subject():
    # The gerund clause is CN3; `a language` has no modifier.
    units("Learning a language takes time.", complex_nominals=1, verb_phrases=2)


# --- verb phrases ----------------------------------------------------------------------


def test_infinitive_complement_is_a_verb_phrase():
    units("I want to go home.", clauses=1, verb_phrases=2)


def test_for_to_clause_is_a_verb_phrase_not_a_clause():
    units("It is important for students to read widely.", clauses=1, verb_phrases=2)


# --- dependency measures and phrasal complexity ---------------------------------------


def test_mean_dependency_distance_and_depth():
    out = run("The cat sat on the mat.")
    # The-cat 1, cat-sat 1, on-sat 1, the-mat 1, mat-on 2 -> 6 / 5.
    assert out["dependency"]["mean_dependency_distance"] == 1.2
    assert out["sentences"][0]["mdd"] == 1.2
    assert out["sentences"][0]["depth"] == 3  # sat -> on -> mat -> the
    assert out["dependency"]["mean_parse_depth"] == 3.0


def test_text_mdd_pools_links_across_sentences():
    out = run("The cat sat on the mat. I don't know what he said.")
    assert out["dependency"]["mean_dependency_distance"] == round((6 + 12) / (5 + 6), 3)


def test_phrasal_complexity_per_1000_words():
    out = run("The old school bus with red seats stopped.")
    p = out["phrasal"]
    assert (p["attributive_adjectives"], p["prepositional_postmodifiers"]) == (2, 1)
    assert p["premodifying_nouns"] == 1  # school
    assert p["attributive_adjectives_per_1000_words"] == round(2 * 1000 / 8, 2)
    assert p["premodifying_nouns_per_1000_words"] == 125.0


def test_proper_name_is_not_a_premodifying_noun():
    assert run("John Smith arrived.")["phrasal"]["premodifying_nouns"] == 0


# --- sentence spans ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "The cat sat on the mat. I don't know what he said.",
        "  Leading spaces.\n\nMy Summer Holiday\n\nWe went to the beach.   ",
        "Dr. Smith arrived at 3.5 p.m. on Monday. “Hello,” she said — quietly.\n",
        "Inter­national trade grew. It grew fast!",  # soft hyphen, removed by normalise
        "A list:\n- one item\n- another item\n\n(\n) Then a sentence.",
    ],
)
def test_spans_align_with_sentence_text(text):
    a = analysed(text)
    out = syntax.analyze(text, analysis=a)
    sents = out["sentences"]
    assert len(sents) == a.sentence_count
    prev_end = 0
    for s, words in zip(sents, a.sentences, strict=True):
        start, end = s["span"]
        segment = a.text[start:end]
        assert segment == segment.strip() and segment
        assert start >= prev_end
        prev_end = end
        # Every word of the sentence lies inside its span, in order.
        pos = 0
        for w in words:
            k = segment.find(w.text, pos)
            assert k >= 0, (w.text, segment)
            pos = k + len(w.text)
        assert s["words"] == len(words)


# --- a longer passage ----------------------------------------------------------------------

PASSAGE = (
    "The Case for Urban Trees\n\n"
    "Although it is often claimed that cities are unhealthy places, the evidence "
    "suggests otherwise. Researchers who studied forty European cities found that "
    "residents of greener districts lived longer. The effect was strongest in poor "
    "neighbourhoods, where access to parks is usually limited. Trees cool the air, "
    "absorb rainwater and reduce noise. They are cheap to plant, but they must be "
    "maintained carefully. When councils cut maintenance budgets, young trees often "
    "die within a few years. Planting a tree takes an hour; growing one takes decades. "
    "City planners should therefore treat the urban forest as essential infrastructure "
    "rather than decoration. The benefits of this investment are shared by everyone "
    "who lives in the city, and they increase every year."
)


def test_longer_passage_is_internally_consistent():
    out = run(PASSAGE)
    c, idx = out["counts"], out["indices"]
    assert c["words"] >= 100 and c["sentences"] >= 5
    assert out["reliability"] == {"reliable": True, "notes": []}
    # Unit relations L2SCA's definitions imply.
    assert c["dependent_clauses"] <= c["clauses"]
    assert c["complex_t_units"] <= c["t_units"] <= c["clauses"]
    assert c["verb_phrases"] >= c["clauses"]
    assert c["passive_clauses"] <= c["clauses"]
    # Per-sentence rows add up to the text totals.
    for key in ("clauses", "dependent_clauses", "t_units"):
        assert sum(s[key] for s in out["sentences"]) == c[key]
    assert sum(s["passive"] for s in out["sentences"]) == c["passive_clauses"]
    # Indices are the ratios of the counts.
    assert idx["mlt"] == round(c["words"] / c["t_units"], 3)
    assert idx["dc_c"] == round(c["dependent_clauses"] / c["clauses"], 3)
    assert idx["cn_t"] == round(c["complex_nominals"] / c["t_units"], 3)
    # Plausible ranges for edited expository prose.
    assert 10 < idx["mlt"] < 30
    assert 1.0 <= idx["c_t"] < 3.0
    assert 1.5 < out["dependency"]["mean_dependency_distance"] < 4.0
    # The heading has no clause.
    assert out["sentences"][0]["t_units"] == 0


def test_passage_matches_hand_count():
    # Hand count in L2SCA's terms, sentence by sentence (heading, then the body):
    #   clauses 0+3+3+2+1+2+2+2+1+3 = 19; DCs 0+2+2+1+0+0+1+0+0+1 = 7;
    #   T-units 0+1+1+1+1+2+1+2+1+2 = 12 (`but`, `;`, `, and` join clauses);
    #   complex T-units 5; passives `is claimed`, `be maintained`, `are shared`;
    #   one coordinate phrase (`cool ..., absorb ... and reduce ...`).
    c = run(PASSAGE)["counts"]
    assert {k: c[k] for k in UNITS if k not in ("complex_nominals", "verb_phrases")} == {
        "words": 123,
        "sentences": 10,
        "clauses": 19,
        "dependent_clauses": 7,
        "t_units": 12,
        "complex_t_units": 5,
        "coordinate_phrases": 1,
        "passive_clauses": 3,
    }


def test_passage_hand_counts():
    out = run(PASSAGE)
    rows = out["sentences"]
    # "Although it is often claimed that cities are unhealthy places, the evidence
    # suggests otherwise." -> 3 clauses (suggests, claimed, are), 2 DCs, 1 T-unit.
    assert (rows[1]["clauses"], rows[1]["dependent_clauses"], rows[1]["t_units"]) == (3, 2, 1)
    assert rows[1]["passive"] == 1  # it is claimed
    # "They are cheap to plant, but they must be maintained carefully." -> 2 T-units.
    assert (rows[5]["clauses"], rows[5]["t_units"], rows[5]["passive"]) == (2, 2, 1)
    # "Planting a tree takes an hour; growing one takes decades." -> 2 T-units, no DC
    # (spaCy attaches the first clause as a fronted ccomp of the second).
    assert (rows[7]["clauses"], rows[7]["dependent_clauses"], rows[7]["t_units"]) == (2, 0, 2)


def test_fronted_reported_speech_is_a_clause_but_not_dependent():
    # Stanford: S(S He is coming, NP she, VP said) - a bare S, not SBAR.
    units("He is coming, she said.", clauses=2, dependent_clauses=0, t_units=1)


def test_academic_prose_has_more_complex_nominals_per_clause_than_narrative():
    assert run(ACADEMIC)["indices"]["cn_c"] > run(NARRATIVE)["indices"]["cn_c"]


def test_short_text_is_flagged():
    out = run("He came and she left.")
    assert out["reliability"]["reliable"] is False
    assert len(out["reliability"]["notes"]) == 2


def test_deterministic():
    assert syntax.analyze(PASSAGE) == syntax.analyze(PASSAGE)
