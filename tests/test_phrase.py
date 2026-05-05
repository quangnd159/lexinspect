"""Smoke tests for PHRASE list detection."""

from lexinspect import phrase


def test_data_loads():
    data = phrase._load()
    assert 500 <= data["item_count"] <= 510
    bands = {it["k_band"] for it in data["items"]}
    assert bands == {1, 2, 3, 4, 5}


def test_detects_have_to():
    out = phrase.analyze("I have to leave now.")
    phrases = [h["phrase"] for h in out["hits"]]
    assert any("HAVE TO" in p for p in phrases)


def test_detects_in_spite_of():
    out = phrase.analyze("They went outside in spite of the rain.")
    phrases = [h["phrase"] for h in out["hits"]]
    assert any("SPITE" in p for p in phrases)


def test_no_hits_in_empty_text():
    out = phrase.analyze("")
    assert out["counts"]["total_hits"] == 0


def test_per_band_sum_matches_total():
    out = phrase.analyze("I have to call her, of course, and there are reasons.")
    assert sum(out["hits_per_k_band"].values()) == out["counts"]["total_hits"]
