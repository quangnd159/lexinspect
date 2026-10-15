"""Smoke tests for BNC/COCA band profiling."""

from lexinspect import _lists, bnc_coca


def test_data_loads():
    data = _lists.bnc_raw()
    assert data["band_count"] == 25
    assert len(data["bands"]) == 25
    assert sum(len(fams) for fams in data["bands"].values()) == 25_000
    assert {f.band for f in _lists.bnc_forms().values()} == set(range(1, 26))
    assert set(_lists.bnc_supplementary().values()) == {
        "proper_names",
        "marginal_words",
        "transparent_compounds",
        "acronyms",
    }


def test_returns_expected_keys(academic):
    out = bnc_coca.analyze(academic)
    assert {
        "counts",
        "coverage_pct",
        "coverage_with_supplementary_pct",
        "per_band",
        "supplementary",
        "proper_nouns",
        "off_list",
        "off_list_sample",
    } <= set(out)
    assert list(out["per_band"]) == [str(b) for b in range(1, 26)]


def test_simple_text_concentrates_in_band_1(simple):
    out = bnc_coca.analyze(simple)
    band1 = out["per_band"]["1"]["tokens"]
    higher = sum(out["per_band"][str(b)]["tokens"] for b in range(2, 26))
    assert band1 > higher


def test_cumulative_coverage_monotonic(academic):
    out = bnc_coca.analyze(academic)
    cum = [out["per_band"][str(b)]["cumulative_coverage_pct"] for b in range(1, 26)]
    assert cum == sorted(cum)
