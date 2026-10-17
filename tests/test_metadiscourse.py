"""Metadiscourse detection: context-gated markers, one category per hit."""

from __future__ import annotations

import pytest
from conftest import analysed

from lexinspect import metadiscourse

INTERACTIVE = {"transitions", "frame_markers", "endophoric_markers", "evidentials", "code_glosses"}
INTERACTIONAL = {"hedges", "boosters", "attitude_markers", "engagement_markers", "self_mentions"}


def hits(text: str) -> list[dict]:
    return metadiscourse.analyze(text, analysis=analysed(text))["hits"]


def by_marker(text: str) -> dict[str, str]:
    return {h["marker"]: h["category"] for h in hits(text)}


def test_data_loads():
    data = metadiscourse._load()
    assert data["marker_count"] >= 400
    assert set(data["categories"]["interactive"]) == INTERACTIVE
    assert set(data["categories"]["interactional"]) == INTERACTIONAL


def test_every_rule_names_a_real_category():
    for _marker, category in metadiscourse._RULES:
        assert category in INTERACTIVE | INTERACTIONAL
    for cats in metadiscourse._PRIORITY.values():
        assert set(cats) <= INTERACTIVE | INTERACTIONAL


def test_returns_expected_keys():
    out = metadiscourse.analyze("However, this is clearly important.")
    assert {"counts", "density_per_1000", "per_dimension", "per_category", "hits"} <= set(out)
    assert set(out["per_dimension"]) == {"interactive", "interactional"}
    assert set(out["per_category"]) == INTERACTIVE | INTERACTIONAL


# --- negatives: everyday uses of listed words are not metadiscourse ------------


@pytest.mark.parametrize(
    "text,word",
    [
        ("It was so good.", "so"),
        ("We waited for a while.", "for"),
        ("She sat on a certain chair.", "certain"),
        ("The table in the kitchen is old.", "table"),
        ("They talked about the war.", "about"),
        ("He has lived here since 2010.", "since"),
        ("Birds flew above the clouds.", "above"),
        ("The first time I saw it was magical.", "first"),
        ("She felt the cold wind.", "felt"),
        ("He appeared on stage.", "appeared"),
        ("A clear sky stretched out.", "clear"),
        ("The figure walked away.", "figure"),
        ("I will look at the menu later.", "later"),
    ],
)
def test_no_hit_for_non_metadiscourse_use(text, word):
    assert word not in {h["marker"] for h in hits(text)}, hits(text)


# --- positives -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,marker,category",
    [
        ("However, the results differ.", "however", "transitions"),
        ("Table 2 shows the results.", "table", "endophoric_markers"),
        # 0.4.0 (MD-11): the label after the longer listed marker `see figure` counts
        ("See Figure 3 for details.", "see figure", "endophoric_markers"),
        ("As noted above, it fails.", "as noted above", "endophoric_markers"),
        ("About 20 percent agreed.", "about", "hedges"),
        ("It is clear that we lost.", "clear", "boosters"),
        ("Smith (2010) argues that it works.", "argues that", "evidentials"),
        ("Consider the data carefully.", "consider", "engagement_markers"),
        ("This must be true.", "must", "boosters"),
        ("We must act now.", "must", "attitude_markers"),
        ("First, we analyse the data.", "first", "frame_markers"),
        ("In fact, the results suggest a link.", "in fact", "boosters"),
        ("The results might be incomplete.", "might", "hedges"),
        ("I came but he left.", "but", "transitions"),
        ("Since it rained, we stayed in.", "since", "transitions"),
        ("This helps you decide.", "you", "engagement_markers"),
        ("On the other hand, prices rose.", "on the other hand", "transitions"),
    ],
)
def test_detects_marker_in_category(text, marker, category):
    assert by_marker(text).get(marker) == category, hits(text)


def test_we_found_that_is_detected_with_self_mention():
    found = by_marker("We found that the effect was small.")
    assert found.get("we") == "self_mentions"
    assert any(m.startswith("found") for m in found)


def test_inclusive_we_is_engagement():
    assert by_marker("We must act now.").get("we") == "engagement_markers"


def test_and_joining_noun_phrases_is_not_a_transition():
    assert "and" not in by_marker("I bought apples and pears.")


def test_and_joining_clauses_is_a_transition():
    assert by_marker("I came and he left.").get("and") == "transitions"


def test_each_hit_in_exactly_one_category_with_also_listed_as():
    out = hits("In fact, the results in fact suggest something different.")
    in_fact = [h for h in out if h["marker"] == "in fact"]
    assert len(in_fact) == 2  # two occurrences, one hit each (not three categories each)
    for h in in_fact:
        assert h["category"] == "boosters"
        assert set(h["also_listed_as"]) == {"code_glosses", "transitions"}


def test_multiword_marker_surface_keeps_case_and_span():
    text = "On the other hand, the results in fact suggest something different."
    out = hits(text)
    on = next(h for h in out if h["marker"] == "on the other hand")
    assert on["surface"] == "On the other hand"
    assert on["span"] == [0, 17]
    for h in out:
        assert text[h["span"][0] : h["span"][1]] == h["surface"]


def test_longest_match_wins():
    out = hits("As noted above, it fails.")
    assert [h["marker"] for h in out] == ["as noted above"]


def test_density_per_1000_words():
    text = "However, the results clearly demonstrate that, in fact, this might suggest a need for further work."
    out = metadiscourse.analyze(text, analysis=analysed(text))
    words = analysed(text).word_count
    assert out["counts"]["content_tokens"] == words
    assert out["density_per_1000"] == pytest.approx(len(out["hits"]) / words * 1000, abs=0.001)
    assert out["density_per_1000"] > 100


def test_detects_hedges():
    cats = [h["category"] for h in hits("This might suggest that the results could be incomplete.")]
    assert cats.count("hedges") >= 2


def test_no_hits_in_plain_sentence():
    assert hits("The cat sat on the mat.") == []


@pytest.mark.parametrize(
    "text", ["We found that the effect was small.", "This shows that it works."]
)
def test_evidentials_need_a_source_subject(text):
    assert "evidentials" not in {h["category"] for h in hits(text)}, hits(text)


@pytest.mark.parametrize(
    "text, marker",
    [
        ("Some people believe that taxes are too high.", "believe"),
        ("Others think that roads help everyone.", "think"),
        ("Researchers assume that the model holds.", "assume"),
    ],
)
def test_reported_mental_state_is_not_writer_stance(text, marker):
    hits = metadiscourse.analyze(text)["hits"]
    assert marker not in [h["marker"] for h in hits]


@pytest.mark.parametrize(
    "text, marker, category",
    [
        ("I strongly believe that buses help.", "believe", "boosters"),
        ("We assume that the model holds.", "assume", "hedges"),
        ("It appears that prices rose.", "appears", "hedges"),
    ],
)
def test_writer_mental_state_is_stance(text, marker, category):
    hits = metadiscourse.analyze(text)["hits"]
    assert (marker, category) in [(h["marker"], h["category"]) for h in hits]
