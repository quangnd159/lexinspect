"""The shared tokenisation every module counts from (`lexinspect._text`).

If these units are wrong, every tab is wrong in the same direction, so the
cases here are the inputs that broke the old per-module tokenisers.
"""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect._text import is_numeric, lookup, normalise


def words(text: str) -> list[str]:
    return [w.text for w in analysed(text).words]


def sentences(text: str) -> list[list[str]]:
    return [[w.text for w in s] for s in analysed(text).sentences]


def lexical(text: str) -> list[str]:
    return [lex.surface for lex in analysed(text).lexical]


# --- words ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I don't know.", ["I", "don't", "know"]),
        ("She’ll come.", ["She’ll", "come"]),  # curly apostrophe
        ("They can’t go and won't stay.", ["They", "can’t", "go", "and", "won't", "stay"]),
        ("I'm sure they'd agree.", ["I'm", "sure", "they'd", "agree"]),
    ],
)
def test_contractions_are_one_word(text, expected):
    assert words(text) == expected


def test_possessives_are_one_word():
    text = "The children's toys and James' car and the dogs' bowls."
    assert words(text) == [
        "The", "children's", "toys", "and", "James'", "car", "and", "the", "dogs'", "bowls",
    ]  # fmt: skip


def test_hyphenated_compounds_are_one_word():
    assert words("A well-known, twenty-five-year-old e-mail.") == [
        "A",
        "well-known",
        "twenty-five-year-old",
        "e-mail",
    ]


def test_dashes_separate_words():
    # An em dash and a spaced hyphen are punctuation, not part of a word.
    assert words("He left — quickly - and quietly.") == ["He", "left", "quickly", "and", "quietly"]


def test_cannot_and_gonna_are_one_word():
    assert words("I cannot go. I'm gonna leave.") == ["I", "cannot", "go", "I'm", "gonna", "leave"]


def test_numerals_are_words_and_symbols_are_not():
    text = "It cost 1,500 dollars, rose 3.5% in the 1990s and came 3rd."
    assert words(text) == [
        "It", "cost", "1,500", "dollars", "rose", "3.5", "in", "the", "1990s", "and", "came", "3rd",
    ]  # fmt: skip
    numeric = [w.text for w in analysed(text).words if w.is_numeric]
    assert numeric == ["1,500", "3.5", "1990s", "3rd"]


@pytest.mark.parametrize(
    "token", ["2019", "1,500", "3.5", "3.5%", "1990s", "3rd", "21st", "$20", "£5", "'90s"]
)
def test_is_numeric_accepts(token):
    assert is_numeric(token)


@pytest.mark.parametrize("token", ["twenty", "B2", "COVID-19", "3D", "abc", "mp3"])
def test_is_numeric_rejects(token):
    assert not is_numeric(token)


def test_abbreviations_are_single_words_and_do_not_end_sentences():
    text = "Dr. Smith moved to the U.S. last year, e.g. in May. He left."
    assert words(text) == [
        "Dr.", "Smith", "moved", "to", "the", "U.S.", "last", "year", "e.g.", "in", "May", "He", "left",
    ]  # fmt: skip
    assert len(analysed(text).sentences) == 2


def test_punctuation_and_quotes_are_never_words():
    assert words("He said “hello” (twice) — then left!") == [
        "He",
        "said",
        "hello",
        "twice",
        "then",
        "left",
    ]


# --- normalisation -------------------------------------------------------------


def test_soft_hyphen_and_nbsp_are_normalised():
    text = "inter­national trade is big."
    assert words(text) == ["international", "trade", "is", "big"]
    assert analysed(text).text == "international trade is big."


@pytest.mark.parametrize("ch", ["​", "‌", "‍", "⁠", "﻿"])
def test_zero_width_characters_are_removed(ch):
    assert normalise(f"word{ch}s") == "words"


@pytest.mark.parametrize("ch", [" ", " ", " ", "　"])
def test_exotic_spaces_become_plain_spaces(ch):
    assert normalise(f"a{ch}b") == "a b"


def test_nfc_composition():
    decomposed = "café"
    assert normalise(decomposed) == "café"
    assert words(f"A {decomposed} opened.") == ["A", "café", "opened"]


def test_crlf_and_paragraph_separator():
    assert normalise("a\r\nb") == "a\nb"
    assert normalise("a b") == "a\n\nb"


# --- sentences -----------------------------------------------------------------


def test_blank_line_forces_a_sentence_break():
    text = "Introduction\n\nThis is the first sentence. This is the second."
    assert sentences(text) == [
        ["Introduction"],
        ["This", "is", "the", "first", "sentence"],
        ["This", "is", "the", "second"],
    ]


def test_title_line_without_full_stop_is_its_own_sentence():
    text = "Climate Change and Cities\n\nCities produce most emissions today. They must adapt."
    assert sentences(text)[0] == ["Climate", "Change", "and", "Cities"]
    assert len(sentences(text)) == 3


def test_windows_blank_line_breaks_too():
    text = "My Heading\r\n\r\nThe body text starts here."
    assert sentences(text) == [["My", "Heading"], ["The", "body", "text", "starts", "here"]]


def test_single_newline_is_not_a_break():
    # Text pasted from a PDF wraps mid-sentence; a lone newline must not split it.
    text = "The results were\nvery clear indeed."
    assert len(analysed(text).sentences) == 1


def test_sentences_without_words_are_not_counted():
    a = analysed("Wait ) . Hello there.")
    assert [[w.text for w in s] for s in a.sentences] == [["Wait"], ["Hello", "there"]]
    assert a.sentence_count == 2


def test_decimal_does_not_end_a_sentence():
    assert len(analysed("Growth was 3.5 percent last year. It slowed.").sentences) == 2


def test_empty_text():
    a = analysed("")
    assert a.word_count == 0
    assert a.sentence_count == 0
    assert a.lexical == []


# --- lexical tokens ------------------------------------------------------------


def test_lexical_tokens_drop_clitics_and_possessives():
    assert lexical("I don't think she'll mind the children's noise.") == [
        "i", "do", "think", "she", "mind", "the", "children", "noise",
    ]  # fmt: skip


def test_lexical_tokens_fix_split_artefacts():
    # spaCy splits can't -> ca|n't and won't -> wo|n't; the host is `can`/`will`.
    assert lexical("I can’t and won't.") == ["i", "can", "and", "will"]


def test_lexical_tokens_drop_numerals():
    assert lexical("In 2019, 1,500 people (3.5%) came 3rd.") == ["in", "people", "came"]


def test_lexical_tokens_of_hyphenated_compound_are_its_parts():
    a = analysed("A well-known fact.")
    lex = a.lexical
    assert [t.surface for t in lex] == ["a", "well", "known", "fact"]
    # The whole compound and its joined form are tried first, on the first part only.
    assert lex[1].keys[:2] == ("well-known", "wellknown")
    assert "well-known" not in lex[2].keys
    # Both parts belong to the same orthographic word.
    assert lex[1].word_index == lex[2].word_index


def test_bound_prefix_is_profiled_with_its_host():
    lex = analysed("We co-operate and re-enter.").lexical
    assert [t.surface for t in lex] == ["we", "operate", "and", "enter"]
    assert lex[1].keys[:2] == ("co-operate", "cooperate")


def test_inflected_verbs_are_looked_up_by_lemma_only():
    # `found` (VBD of find) must not be keyed as `found` (establish).
    lex = {t.surface: t for t in analysed("We found it and they left early.").lexical}
    assert lex["found"].keys == ("find",)
    assert lex["left"].keys == ("leave",)


def test_non_verb_keys_include_surface_then_lemma():
    lex = {t.surface: t for t in analysed("The children played.").lexical}
    assert lex["children"].keys == ("children", "child")


def test_proper_nouns_flagged():
    lex = {t.surface: t for t in analysed("Maria visited London with Smith.").lexical}
    assert lex["london"].is_proper
    assert lex["smith"].is_proper
    assert not lex["visited"].is_proper


def test_abbreviation_full_stop_stripped_as_fallback_key():
    lex = analysed("Dr. Brown agreed.").lexical[0]
    assert lex.keys[:2] == ("dr.", "dr")


def test_lookup_falls_back_to_spelling_variant_only_after_exact_keys():
    table = {"color": "us", "colour": "gb"}
    assert lookup(table, ("colour",)) == ("colour", "gb")
    assert lookup({"color": "us"}, ("colour",)) == ("color", "us")
    assert lookup({"centre": 1}, ("center",)) == ("centre", 1)
    assert lookup({}, ("colour",)) == (None, None)
