"""PHRASE list detection: variants, sense constraints, overlap and spans."""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect import phrase


def hits(text: str) -> list[dict]:
    return phrase.analyze(text, analysis=analysed(text))["hits"]


def phrases(text: str) -> list[str]:
    return [h["phrase"] for h in hits(text)]


def test_data_loads():
    data = phrase._load()
    assert 500 <= data["item_count"] <= 510
    assert {it["k_band"] for it in data["items"]} == {1, 2, 3, 4, 5}
    assert all(it["variants"] for it in data["items"])


# --- senses --------------------------------------------------------------------


def test_going_to_a_place_is_not_future():
    assert "GOING TO (FUTURE)" not in phrases("We are going to the park.")


def test_going_to_plus_verb_is_future():
    assert phrases("We are going to leave soon.") == ["GOING TO (FUTURE)"]


def test_used_to_past_habit():
    assert phrases("It used to snow here every winter.") == ["USED TO (PAST)"]


def test_used_to_accustomed():
    assert phrases("I am used to the noise.") == ["USED TO (ACCUSTOMED)"]


def test_in_that_room_is_not_in_the_sense_that():
    assert "IN (THE SENSE) THAT" not in phrases("In that room, nobody spoke.")


def test_in_the_sense_that():
    assert phrases("I agree in the sense that it works.") == ["IN (THE SENSE) THAT"]


def test_made_out_of_wood_is_not_make_out():
    found = phrases("The box was made out of wood.")
    assert "MAKE OUT" not in found
    assert any(p.startswith("OUT OF") for p in found)


def test_make_out_the_words():
    assert "MAKE OUT" in phrases("I can't make out the words.")


# --- variants ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,surface",
    [
        ("There's a cat on the mat.", "There's"),
        ("There is a reason.", "There is"),
        ("There are many reasons.", "There are"),
    ],
)
def test_there_is_are(text, surface):
    (h,) = hits(text)
    assert h["phrase"] == "THERE IS/ARE"
    assert h["surface"] == surface


def test_there_is_with_curly_apostrophe():
    assert phrases("There’s a cat on the mat.") == ["THERE IS/ARE"]


def test_possessive_slot_shake_ones_head():
    (h,) = hits("He shook his head slowly.")
    assert h["phrase"] == "SHAKE ONE’S HEAD"
    assert h["surface"] == "shook his head"


def test_reflexive_slot_take_care_of():
    assert phrases("Take care of yourself.") == ["TAKE CARE OF"]


def test_optional_element_a_bit_of():
    assert [h["surface"] for h in hits("I want a bit of cake.")] == ["a bit of"]
    assert [h["surface"] for h in hits("Wait a bit.")] == ["a bit"]
    assert phrases("Wait a bit.") == ["A BIT (OF)"]


def test_inflections_match():
    assert phrases("They dealt with it.") == ["DEAL WITH"]
    assert phrases("He has to go.") == ["HAVE TO"]
    assert phrases("She had to go.") == ["HAVE TO"]


# --- overlap, punctuation, spans -----------------------------------------------


def test_as_well_as_counted_once():
    found = hits("She sings as well as dances.")
    assert [h["phrase"] for h in found] == ["AS WELL AS"]


def test_no_match_across_punctuation():
    # `of, course` must not match OF COURSE.
    assert "OF COURSE" not in phrases("It was made of, course grain.")


def test_ambiguous_sense_lists_alternatives():
    (h,) = hits("He went out of the house.")
    assert h["phrase"].startswith("OUT OF")
    assert h["also_possible"]
    assert all(p.startswith("OUT OF") for p in h["also_possible"])
    assert h["phrase"] not in h["also_possible"]


def test_spans_point_at_the_surface():
    text = "He has to go, of course, and there are reasons."
    a = analysed(text)
    out = phrase.analyze(text, analysis=a)
    assert {h["surface"] for h in out["hits"]} == {"has to", "of course", "there are"}
    for h in out["hits"]:
        assert text[h["span"][0] : h["span"][1]] == h["surface"]


def test_counts():
    text = "I have to call her, of course, and there are reasons."
    out = phrase.analyze(text, analysis=analysed(text))
    assert out["counts"]["total_hits"] == 3
    assert sum(out["hits_per_k_band"].values()) == 3
    assert out["counts"]["unique_phrases"] == 3
    # 3 hits over 11 words
    assert out["counts"]["hits_per_1000_words"] == pytest.approx(3 / 11 * 1000, abs=0.01)
    assert sum(out["phrase_frequency"].values()) == 3


def test_detects_in_spite_of():
    assert any("SPITE" in p for p in phrases("They went outside in spite of the rain."))


def test_no_hits_in_empty_text():
    out = phrase.analyze("")
    assert out["counts"]["total_hits"] == 0
    assert out["counts"]["hits_per_1000_words"] == 0.0


def test_to_go_remaining_needs_clause_end():
    def phrases(t):
        return [h["phrase"] for h in phrase.analyze(t)["hits"]]

    assert not any(p.startswith("TO GO") for p in phrases("People rely on trains to go to work."))
    assert any(p.startswith("TO GO") for p in phrases("Two more weeks to go."))


# --- what the list says about each hit -------------------------------------------


def run(text: str) -> dict:
    return phrase.analyze(text, analysis=analysed(text))


def expression(text: str, name: str) -> dict:
    (e,) = [e for e in run(text)["expressions"] if e["phrase"] == name]
    return e


def test_every_source_rating_is_in_the_legend():
    for item in phrase._load()["items"]:
        for r in phrase.REGISTERS:
            assert item[r] in phrase._RATINGS, (item["phrase"], r, item[r])


def test_register_ratings_follow_the_source_legend():
    # Source row: A LOT  * * *  *  x  (spoken, written general, written academic).
    e = expression("They go camping a lot in the summer.", "A LOT")
    assert e["register"] == {
        "spoken_general": "most_common",
        "written_general": "infrequent",
        "written_academic": "rare",
    }
    assert e["freq_per_100m"] == 22332
    assert e["example"] == "They go camping a lot in the summer."


def test_register_counts_every_hit_once_per_register():
    text = "I have to go, of course. I have to, and it is sort of late."
    out = run(text)
    for r in phrase.REGISTERS:
        assert sum(out["register"][r].values()) == out["counts"]["total_hits"]
    assert out["register"]["written_academic"]["rare"] == 1  # SORT OF


def test_expressions_group_hits_by_entry():
    out = run("I have to go. She had to stay. Of course.")
    assert [(e["phrase"], e["count"]) for e in out["expressions"]] == [
        ("HAVE TO", 2),
        ("OF COURSE", 1),
    ]
    assert sum(e["count"] for e in out["expressions"]) == out["counts"]["total_hits"]


def test_expression_lists_alternative_senses():
    e = expression("We made it out of wood.", "OUT OF (‘IN’/’FROM’)")
    assert {a["sense"] for a in e["also_possible"]} == {"USING", "DUE TO"}


def test_word_band_is_the_highest_band_of_its_words():
    e = expression("What is the limit in terms of price?", "IN TERMS OF")
    assert (e["k_band"], e["word_band"]) == (2, 1)
    # SPITE is a rarer word than IN SPITE OF is an expression.
    e = expression("They went outside in spite of the rain.", "IN SPITE OF")
    assert e["word_band"] > e["k_band"]


def test_word_band_needs_every_word_in_a_band():
    # `oh` is on Nation's marginal-words list, not in a band.
    assert expression("Oh dear, I forgot.", "OH DEAR")["word_band"] is None


# --- integrated profile ----------------------------------------------------------


def test_integrated_profile_equals_bnc_coca_without_expressions():
    from lexinspect import bnc_coca

    text = "The cat sat on the mat in London."
    a = analysed(text)
    ip = phrase.analyze(text, analysis=a)["integrated_profile"]
    words = bnc_coca.analyze(text, analysis=a)
    assert ip["counts"]["phrase_tokens"] == 0
    for b, row in words["per_band"].items():
        assert ip["per_band"][b] == {
            **{k: v for k, v in row.items() if k != "headwords"},
            "phrase_tokens": 0,
        }
    assert ip["coverage_with_supplementary_pct"] == words["coverage_with_supplementary_pct"]


def test_integrated_profile_counts_words_at_the_expressions_band():
    ip = run("What is the limit in terms of price?")["integrated_profile"]
    assert ip["per_band"]["2"]["phrase_tokens"] == 3
    assert ip["counts"]["phrase_tokens"] == 3
    assert ip["counts"]["raised_tokens"] == 3  # in, terms, of: all 1K words
    assert ip["counts"]["lowered_tokens"] == 0


def test_integrated_profile_can_lower_a_rare_word():
    ip = run("They went outside in spite of the rain.")["integrated_profile"]
    assert ip["counts"]["lowered_tokens"] == 1  # spite
    assert ip["counts"]["raised_tokens"] == 2  # in, of


def test_integrated_profile_keeps_every_token():
    ip = run("By and large, Mr Smith had to deal with it, oh well, in spite of everything.")[
        "integrated_profile"
    ]
    c = ip["counts"]
    in_bands = sum(row["tokens"] for row in ip["per_band"].values())
    assert in_bands == c["on_list_tokens"]
    total = in_bands + c["supplementary_tokens"] + c["proper_noun_tokens"] + c["off_list_tokens"]
    assert total == c["content_tokens"]
