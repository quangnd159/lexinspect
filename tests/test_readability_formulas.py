"""Readability formulas against values computed by hand from the published definitions.

Each text is small enough to count words, sentences, syllables and letters by
eye. Syllables are CMUdict's (checked individually in `test_syllable_spot_checks`).
Expected values are the arithmetic in the comments, not the module's output.
"""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect import _syllables, readability

APPROX = 0.006  # scores are rounded to 2 dp


def scores(text: str) -> dict[str, float]:
    return readability.analyze(text, analysis=analysed(text))["scores"]


# ---------------------------------------------------------------------------
# Text A: "The cat sat on the mat. The dog ran."
#   words      W = 6 + 3 = 9           sentences S = 2       ASL = 4.5
#   syllables  all monosyllables = 9   ASW = 1.0             polysyllables = 0
#   letters    3+3+3+2+3+3 + 3+3+3 = 26
#   Dale–Chall: every word on the easy list -> PDW = 0
# ---------------------------------------------------------------------------
TEXT_A = "The cat sat on the mat. The dog ran."


def test_text_a_counts():
    out = readability.analyze(TEXT_A)
    c = out["counts"]
    assert (c["words"], c["sentences"], c["syllables"]) == (9, 2, 9)
    assert (c["polysyllable_words"], c["monosyllable_words"], c["difficult_words"]) == (0, 9, 0)
    assert out["averages"]["characters_per_word"] == pytest.approx(26 / 9, abs=1e-3)


@pytest.mark.parametrize(
    "name,expected",
    [
        # 206.835 - 1.015*4.5 - 84.6*1.0 = 206.835 - 4.5675 - 84.6
        ("flesch_reading_ease", 117.6675),
        # 0.39*4.5 + 11.8*1.0 - 15.59 = 1.755 + 11.8 - 15.59
        ("flesch_kincaid_grade", -2.035),
        # 0.4 * (4.5 + 100*0/9)
        ("gunning_fog", 1.8),
        # 1.0430*sqrt(0*30/2) + 3.1291
        ("smog_index", 3.1291),
        # 4.71*26/9 + 0.5*4.5 - 21.43 = 13.6067 + 2.25 - 21.43
        ("automated_readability_index", -5.5733),
        # L = 100*26/9 = 288.89, S = 100*2/9 = 22.22
        # 0.0588*288.89 - 0.296*22.22 - 15.8 = 16.9867 - 6.5778 - 15.8
        ("coleman_liau_index", -5.3911),
        # 0.1579*0 + 0.0496*4.5 (no +3.6365: PDW <= 5)
        ("dale_chall_readability_score", 0.2232),
        # easy=9, hard=0: r = 9/2 = 4.5 <= 20 -> (4.5 - 2)/2
        ("linsear_write_formula", 1.25),
        # grade equivalents sorted: ARI -5.57, CLI -5.39, FKGL -2.04, Linsear 1.25, Fog 1.8,
        # SMOG 3.13, Dale–Chall band(0.22)=4.0, Flesch band(117.7)=5.0 -> (1.25+1.8)/2
        ("text_standard", 1.525),
    ],
)
def test_text_a_scores(name, expected):
    assert scores(TEXT_A)[name] == pytest.approx(expected, abs=APPROX)


# ---------------------------------------------------------------------------
# Text B: "Education is important. Students study history."
#   words      W = 3 + 3 = 6     sentences S = 2     ASL = 3
#   syllables  ed-u-ca-tion 4, is 1, im-por-tant 3, stu-dents 2, stud-y 2, his-to-ry 3 = 15
#              ASW = 2.5; polysyllables (>=3) = education, important, history = 3
#   Fog hard words: the same three (none proper, hyphenated or -es/-ed/-ing)
#   letters    9 + 2 + 9 + 8 + 5 + 7 = 40
#   Dale–Chall: `education` and `students` are not on the easy list -> PDW = 2/6 = 33.33%
# ---------------------------------------------------------------------------
TEXT_B = "Education is important. Students study history."


def test_text_b_counts():
    c = readability.analyze(TEXT_B)["counts"]
    assert (c["words"], c["sentences"], c["syllables"]) == (6, 2, 15)
    assert (c["polysyllable_words"], c["monosyllable_words"], c["difficult_words"]) == (3, 1, 2)
    assert c["long_words"] == 4  # >6 letters: education, important, students, history


@pytest.mark.parametrize(
    "name,expected",
    [
        # 206.835 - 1.015*3 - 84.6*2.5 = 206.835 - 3.045 - 211.5
        ("flesch_reading_ease", -7.71),
        # 0.39*3 + 11.8*2.5 - 15.59 = 1.17 + 29.5 - 15.59
        ("flesch_kincaid_grade", 15.08),
        # 0.4 * (3 + 100*3/6) = 0.4 * 53
        ("gunning_fog", 21.2),
        # 1.0430*sqrt(3*30/2) + 3.1291 = 1.0430*6.7082 + 3.1291
        ("smog_index", 10.1258),
        # 4.71*40/6 + 0.5*3 - 21.43 = 31.4 + 1.5 - 21.43
        ("automated_readability_index", 11.47),
        # L = 666.67, S = 33.33: 0.0588*666.67 - 0.296*33.33 - 15.8 = 39.2 - 9.8667 - 15.8
        ("coleman_liau_index", 13.5333),
        # 0.1579*33.333 + 0.0496*3 + 3.6365 = 5.2633 + 0.1488 + 3.6365
        ("dale_chall_readability_score", 9.0486),
        # easy=3, hard=3: r = (3 + 3*3)/2 = 6 -> (6 - 2)/2
        ("linsear_write_formula", 2.0),
    ],
)
def test_text_b_scores(name, expected):
    assert scores(TEXT_B)[name] == pytest.approx(expected, abs=APPROX)


# ---------------------------------------------------------------------------
# Text C: "Washington created beautiful buildings."   (Gunning's exclusions)
#   W = 4, S = 1; syllables 3 + 3 + 3 + 2 = 11; polysyllables (SMOG) = 3
#   Fog hard words: Washington excluded (proper noun); created excluded (cre-ate is 2,
#   it reaches 3 only via -ed); beautiful counts -> 1
#   Dale–Chall: Washington familiar (proper name); `created` unfamiliar -> PDW = 25%
# ---------------------------------------------------------------------------
TEXT_C = "Washington created beautiful buildings."


@pytest.mark.parametrize(
    "name,expected",
    [
        # 0.4 * (4 + 100*1/4) = 0.4 * 29
        ("gunning_fog", 11.6),
        # 1.0430*sqrt(3*30/1) + 3.1291 = 1.0430*9.4868 + 3.1291
        ("smog_index", 13.0239),
        # 0.1579*25 + 0.0496*4 + 3.6365 = 3.9475 + 0.1984 + 3.6365
        ("dale_chall_readability_score", 7.7824),
        # easy=1, hard=3: r = (1 + 9)/1 = 10 -> (10 - 2)/2
        ("linsear_write_formula", 4.0),
        # 206.835 - 1.015*4 - 84.6*2.75 = 206.835 - 4.06 - 232.65
        ("flesch_reading_ease", -29.875),
    ],
)
def test_text_c_scores(name, expected):
    assert scores(TEXT_C)[name] == pytest.approx(expected, abs=APPROX)


def test_hyphenated_words_are_not_fog_complex():
    # `well-educated` has 5 syllables but Gunning excludes hyphenated compounds.
    out = readability.analyze("A well-educated man.")
    assert out["counts"]["polysyllable_words"] == 1
    assert out["scores"]["gunning_fog"] == pytest.approx(0.4 * 3, abs=APPROX)


def test_dale_chall_inflections_proper_nouns_and_numerals_are_familiar():
    out = readability.analyze("The boys played with books in London in 2019.")
    assert out["counts"]["difficult_words"] == 0


def test_coleman_liau_uses_0_0588():
    # Same letters/sentences as text A; 0.058 would give 16.756 - 6.578 - 15.8 = -5.62.
    assert scores(TEXT_A)["coleman_liau_index"] == pytest.approx(-5.39, abs=APPROX)


def test_reading_time_is_238_wpm():
    text = " ".join(["word"] * 238) + "."
    assert readability.analyze(text)["counts"]["reading_time_seconds"] == 60.0


def test_reliability_flags_short_texts():
    rel = readability.analyze(TEXT_A)["reliability"]
    assert rel["reliable"] is False
    assert any("9 words" in n for n in rel["notes"])
    assert any("SMOG" in n for n in rel["notes"])


def test_reliable_on_long_text():
    text = " ".join(["The cat sat on the mat today."] * 30)
    rel = readability.analyze(text)["reliability"]
    assert rel == {"reliable": True, "notes": []}


def test_dr_and_us_do_not_end_sentences_in_readability():
    out = readability.analyze("Dr. Smith went to the U.S. in May. I agree.")
    # textstat split at every full stop and dropped `I agree.`; both were wrong.
    assert out["counts"]["sentences"] == 2
    assert out["counts"]["words"] == 10


# --- syllables -----------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected,sources",
    [
        ("colour", 2, {"variant"}),  # CMUdict is American: found via `color`
        ("realise", 2, {"cmudict", "variant"}),
        ("programme", 2, {"cmudict", "variant"}),
        ("behavioural", 4, {"cmudict", "variant", "stem"}),
        ("datasets", 3, None),
        ("naïve", 2, {"cmudict"}),
        ("the", 1, {"cmudict"}),
        ("table", 2, {"cmudict"}),
        ("created", 3, {"cmudict"}),
        ("jumped", 1, {"cmudict"}),
        ("everything", 3, {"cmudict"}),
    ],
)
def test_syllable_spot_checks(word, expected, sources):
    assert _syllables.count(word) == expected
    if sources is not None:
        assert _syllables.source(word) in sources


def test_unknown_inflection_uses_stem_plus_suffix():
    # `tweeted`/`texting` aren't in CMUdict; `tweet` and `text` are.
    assert (_syllables.count("tweeted"), _syllables.source("tweeted")) == (2, "stem")
    assert (_syllables.count("texting"), _syllables.source("texting")) == (2, "stem")
    # Not in CMUdict in either spelling; still counted right.
    assert _syllables.count("recolouring") == 4  # re-col-our-ing


def _word_syllables(text: str) -> int:
    (w,) = analysed(text).words
    return readability.word_syllables(w)


@pytest.mark.parametrize(
    "numeral,expected",
    [
        ("2019", 4),  # twen-ty nine-teen
        ("1987", 6),  # nine-teen eight-y sev-en
        ("2005", 4),  # two thou-sand five
        ("1,500", 6),  # one thou-sand five hun-dred
        ("7", 2),  # sev-en
        ("3.5", 3),  # three point five
    ],
)
def test_numerals_are_counted_as_spoken(numeral, expected):
    assert _word_syllables(numeral) == expected


def test_contraction_syllabified_whole():
    assert _word_syllables("don't") == 1
    assert _word_syllables("children's") == 2


def test_percentage_read_as_per_cent():
    # "50%" is spoken "fif-ty per cent" = 4 syllables.
    out = readability.analyze("Sales rose 50%.")
    # sales 1 + rose 1 + fifty 2 + per cent 2
    assert out["counts"]["syllables"] == 6


def test_smog_note_alone_does_not_make_scores_unreliable():
    # 120 words in 12 sentences: long enough for the formulas, short of SMOG's 30 sentences.
    text = " ".join(["The small cat sat quietly on the old mat by the door."] * 10)
    rel = readability.analyze(text)["reliability"]
    assert rel["reliable"] is True
    assert len(rel["notes"]) == 1 and "SMOG" in rel["notes"][0]
