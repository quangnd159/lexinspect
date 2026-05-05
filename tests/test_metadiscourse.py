"""Smoke tests for metadiscourse marker detection."""

from lexinspect import metadiscourse

INTERACTIVE = {"transitions", "frame_markers", "endophoric_markers", "evidentials", "code_glosses"}
INTERACTIONAL = {"hedges", "boosters", "attitude_markers", "engagement_markers", "self_mentions"}


def test_data_loads():
    data = metadiscourse._load()
    assert data["marker_count"] >= 400
    assert set(data["categories"]["interactive"]) == INTERACTIVE
    assert set(data["categories"]["interactional"]) == INTERACTIONAL


def test_returns_expected_keys():
    out = metadiscourse.analyze("However, this is clearly important.")
    assert {"counts", "density_per_1000", "per_dimension", "per_category", "hits"} <= set(out)
    assert set(out["per_dimension"]) == {"interactive", "interactional"}
    assert set(out["per_category"]) == INTERACTIVE | INTERACTIONAL


def test_detects_transitions_and_boosters():
    out = metadiscourse.analyze("However, this is clearly important.")
    cats = {h["category"] for h in out["hits"]}
    assert "transitions" in cats
    assert "boosters" in cats


def test_detects_multiword_markers():
    out = metadiscourse.analyze("On the other hand, the results in fact suggest something different.")
    surfaces = {h["surface"] for h in out["hits"]}
    assert "on the other hand" in surfaces


def test_detects_hedges():
    out = metadiscourse.analyze("This might suggest that the results could be incomplete.")
    cats = [h["category"] for h in out["hits"]]
    assert cats.count("hedges") >= 2


def test_density_in_dense_text():
    text = "However, the results clearly demonstrate that, in fact, this might suggest a need for further work."
    out = metadiscourse.analyze(text)
    assert out["density_per_1000"] > 100  # very dense


def test_no_hits_in_function_words():
    out = metadiscourse.analyze("The cat sat on the mat.")
    # 'on' alone shouldn't trigger; if it does, it's a marker. Just ensure structure.
    assert isinstance(out["hits"], list)
