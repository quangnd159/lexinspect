"""Vocabulary-profile accuracy: the lookups behind CEFR, BNC/COCA, NGSL and AWL.

Each case here is a word the old profilers got wrong in a way a user would
notice: British spellings reported as rare, derived forms off their family,
names counted as unknown vocabulary, homographs credited to the wrong word.
"""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect import awl, bnc_coca, cefr, ngsl

BRITISH = ["colour", "centre", "programme", "organised", "analysed", "travelled", "behaviour"]


def _lex(text: str, surface: str):
    (lex,) = [t for t in analysed(text).lexical if t.surface == surface]
    return lex


@pytest.mark.parametrize("word", BRITISH)
def test_british_spellings_are_on_ngsl_or_nawl(word):
    text = f"She mentioned the {word} yesterday."
    out = ngsl.analyze(text, analysis=analysed(text))
    assert out["counts"]["off_list_tokens"] == 0, out["off_list"]


@pytest.mark.parametrize("word", BRITISH)
def test_british_spellings_are_in_a_bnc_band(word):
    kind, fam = bnc_coca.classify(_lex(f"She mentioned the {word} yesterday.", word))
    assert kind == "band"
    assert fam.band <= 3


def test_british_spellings_full_sentence_all_on_list():
    text = "The colour of the centre programme was organised and analysed; she travelled with good behaviour."
    a = analysed(text)
    assert ngsl.analyze(text, analysis=a)["counts"]["off_list_tokens"] == 0
    assert bnc_coca.analyze(text, analysis=a)["counts"]["off_list_tokens"] == 0


@pytest.mark.parametrize(
    "word", ["color", "center", "program", "organized", "analyzed", "traveled", "behavior"]
)
def test_american_spellings_are_in_a_bnc_band(word):
    kind, _fam = bnc_coca.classify(_lex(f"She mentioned the {word} yesterday.", word))
    assert kind == "band"


@pytest.mark.parametrize(
    "text,word,headword,band",
    [
        ("He clearly agreed.", "clearly", "clear", 1),
        ("It was unclear.", "unclear", "clear", 1),
        ("It is possibly true.", "possibly", "possible", 1),
        ("He was obviously tired.", "obviously", "obvious", 1),
        ("The children played.", "children", "child", 1),
        ("She organised it.", "organised", "organize", 2),
    ],
)
def test_derived_forms_belong_to_their_family(text, word, headword, band):
    kind, fam = bnc_coca.classify(_lex(text, word))
    assert (kind, fam.headword, fam.band) == ("band", headword, band)


@pytest.mark.parametrize("module", [bnc_coca, ngsl, cefr])
def test_proper_nouns_are_not_off_list(module):
    text = "London and Smith met Okonkwo in Paris."
    out = module.analyze(text, analysis=analysed(text))
    off = {x["word"] for x in out["off_list"]}
    assert not off & {"london", "smith", "okonkwo", "paris"}


def test_bnc_proper_nouns_bucket():
    text = "London and Smith met Okonkwo in Paris."
    out = bnc_coca.analyze(text, analysis=analysed(text))
    assert {x["word"] for x in out["proper_nouns"]} >= {"london", "paris", "okonkwo"}
    # Nation's convention: names are assumed known.
    assert out["coverage_with_supplementary_pct"] == 100.0


def test_bnc_marginal_words_are_supplementary():
    text = "Oh, hmm, I see."
    out = bnc_coca.analyze(text, analysis=analysed(text))
    assert out["supplementary"].get("marginal_words") == 2


def test_contraction_clitics_are_not_profiled():
    text = "She'll say it's fine but they don't know."
    out = bnc_coca.analyze(text, analysis=analysed(text))
    assert out["counts"]["off_list_tokens"] == 0
    # she, say, it, fine, but, they, do, know
    assert out["counts"]["content_tokens"] == 8


def test_numerals_are_not_profiled():
    text = "In 2019, 1,500 people came."
    assert bnc_coca.analyze(text, analysis=analysed(text))["counts"]["content_tokens"] == 3


def test_hyphenated_compound_parts_are_profiled():
    text = "A well-known twenty-five-year-old author."
    out = bnc_coca.analyze(text, analysis=analysed(text))
    # a, well, known, twenty, five, year, old, author
    assert out["counts"]["content_tokens"] == 8
    assert out["counts"]["off_list_tokens"] == 0


def test_latin_abbreviations_are_not_off_list():
    text = "Some fruits, e.g. apples, are sweet, i.e. sugary."
    out = bnc_coca.analyze(text, analysis=analysed(text))
    assert {x["word"] for x in out["off_list"]} == set()


# --- homographs ----------------------------------------------------------------


def test_found_as_past_of_find_is_not_awl_found():
    text = "We found the answer."
    assert awl.analyze(text, analysis=analysed(text))["families_found"] == []


def test_founded_a_company_is_awl_found():
    text = "They founded a company."
    out = awl.analyze(text, analysis=analysed(text))
    assert out["families_found"] == ["found"]
    (detail,) = out["families_detail"]
    assert (detail["headword"], detail["sublist"], detail["tokens"]) == ("found", 9, 1)


def test_left_as_past_of_leave():
    lex = _lex("She left early.", "left")
    kind, fam = bnc_coca.classify(lex)
    assert (kind, fam.headword) == ("band", "leave")


# --- CEFR per-POS --------------------------------------------------------------


def _cefr_level_of(text: str, word: str) -> str:
    out = cefr.analyze(text, analysis=analysed(text))
    levels = [
        lvl for lvl, items in out["words_by_level"].items() if any(i["word"] == word for i in items)
    ]
    assert len(levels) == 1, out["words_by_level"]
    return levels[0]


def test_cefr_present_noun_is_a1():
    assert _cefr_level_of("She gave me a present.", "present") == "A1"


def test_cefr_present_verb_is_b2():
    assert _cefr_level_of("They will present their findings.", "present") == "B2"


def test_cefr_pos_fallback_counted():
    # `the` is listed only as a determiner/article; whatever spaCy tags it, the
    # count of POS misses never exceeds the on-list count and is reported.
    text = "They will present their findings."
    c = cefr.analyze(text, analysis=analysed(text))["counts"]
    assert 0 <= c["pos_fallback_tokens"] <= c["on_list_tokens"]


def test_cefr_highest_level_and_95th_percentile():
    text = "They will present their findings."
    out = cefr.analyze(text, analysis=analysed(text))
    assert out["highest_level_present"] == "B2"
    assert out["estimated_level_95th"] == "B2"


def test_cefr_95th_counts_proper_nouns_as_known():
    # Every non-name word is A1; names alone must not push the estimate up or to None.
    text = "Tom and Maria saw London and Paris."
    out = cefr.analyze(text, analysis=analysed(text))
    assert out["counts"]["off_list_tokens"] == 0
    assert out["estimated_level_95th"] == "A1"


def test_cefr_british_spelling_found():
    text = "I like the colour."
    out = cefr.analyze(text, analysis=analysed(text))
    assert out["counts"]["off_list_tokens"] == 0


def test_ngsl_vs_nawl_split():
    text = "The empirical hypothesis was tested."
    out = ngsl.analyze(text, analysis=analysed(text))
    assert "hypothesis" in out["nawl_lemmas_found"] or "empirical" in out["nawl_lemmas_found"]
    assert "the" in out["ngsl_lemmas_found"]
