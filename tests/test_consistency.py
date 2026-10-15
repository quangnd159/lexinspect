"""Cross-module invariants: every tab counts from the same units.

The rebuild's promise is that the word count on one tab is the word count on
the next, and that each profiler's buckets partition the same token stream.
These run every module over one shared parse per text (as `/v1/analyze` does).
"""

from __future__ import annotations

import pytest
from conftest import ACADEMIC, NARRATIVE, SIMPLE, analysed

from lexinspect import pipeline

HARD = (
    "Climate Policy in the U.S.\n\n"
    "Dr. Smith's well-known 2019 report doesn't mince words: emissions rose 3.5% in the 1990s, "
    "e.g. in London and New York. However, it is clear that we cannot wait. "
    "Table 2 shows that about 20 percent of firms — roughly 1,500 — are going to act. "
    "As well as this, the colour-coded programme was organised by James' team; they've "
    "travelled widely since 2010. In fact, the results suggest a link (Smith 2010).\n\n"
    "There's more to say. Teh end."
)
CURLY = "She’ll say it’s fine, but they’re not sure. The O’Neills’ house isn’t far."

TEXTS = {
    "simple": SIMPLE,
    "academic": ACADEMIC,
    "narrative": NARRATIVE,
    "hard": HARD,
    "curly": CURLY,
}


@pytest.fixture(scope="module", params=list(TEXTS))
def run(request):
    text = TEXTS[request.param]
    a = analysed(text)
    _, results = pipeline.run_all(text, analysis=a)
    return a, results


def test_core_modules_all_present(run):
    _, r = run
    assert {
        "readability", "statistics", "diversity", "tagger", "awl", "bnc_coca", "ngsl",
        "phrase", "cefr", "metadiscourse", "errors",
    } <= set(r)  # fmt: skip


def test_word_count_agrees(run):
    a, r = run
    assert r["readability"]["counts"]["words"] == a.word_count
    s = r["statistics"]["counts"]
    assert s["tokens_excluding_numbers"] + s["excluded_numeric_tokens"] == a.word_count
    assert r["diversity"]["counts"]["tokens"] == s["tokens_excluding_numbers"]
    assert r["metadiscourse"]["counts"]["content_tokens"] == a.word_count


def test_sentence_count_agrees(run):
    a, r = run
    n = a.sentence_count
    assert r["readability"]["counts"]["sentences"] == n
    assert r["statistics"]["counts"]["sentences"] == n
    assert r["tagger"]["counts"]["sentences"] == n
    assert r["errors"]["counts"]["sentences"] == n


def test_syllables_agree(run):
    _, r = run
    # Statistics excludes numerals from its syllable count; readability reads them aloud.
    assert r["statistics"]["counts"]["syllables"] <= r["readability"]["counts"]["syllables"]


def test_profilers_count_the_same_lexical_tokens(run):
    a, r = run
    n = len(a.lexical)
    for mod in ("awl", "bnc_coca", "ngsl", "cefr", "phrase"):
        assert r[mod]["counts"]["content_tokens"] == n, mod


def test_bnc_buckets_partition_tokens(run):
    _, r = run
    c = r["bnc_coca"]["counts"]
    assert (
        c["on_list_tokens"]
        + c["proper_noun_tokens"]
        + c["supplementary_tokens"]
        + c["off_list_tokens"]
        == c["content_tokens"]
    )
    assert sum(b["tokens"] for b in r["bnc_coca"]["per_band"].values()) == c["on_list_tokens"]
    assert sum(r["bnc_coca"]["supplementary"].values()) == c["supplementary_tokens"]
    assert sum(x["count"] for x in r["bnc_coca"]["proper_nouns"]) == c["proper_noun_tokens"]
    assert sum(x["count"] for x in r["bnc_coca"]["off_list"]) == c["off_list_tokens"]


def test_ngsl_buckets_partition_tokens(run):
    _, r = run
    c = r["ngsl"]["counts"]
    assert (
        c["ngsl_tokens"] + c["nawl_tokens"] + c["proper_noun_tokens"] + c["off_list_tokens"]
        == c["content_tokens"]
    )


def test_cefr_buckets_partition_tokens(run):
    _, r = run
    out = r["cefr"]
    c = out["counts"]
    assert (
        c["on_list_tokens"] + c["proper_noun_tokens"] + c["off_list_tokens"] == c["content_tokens"]
    )
    assert sum(lv["tokens"] for lv in out["per_level"].values()) == c["on_list_tokens"]
    assert c["pos_fallback_tokens"] <= c["on_list_tokens"]
    for lvl, items in out["words_by_level"].items():
        assert sum(i["count"] for i in items) <= out["per_level"][lvl]["tokens"]


def test_awl_counts_are_consistent(run):
    a, r = run
    out = r["awl"]
    assert sum(s["tokens"] for s in out["per_sublist"].values()) == out["counts"]["awl_tokens"]
    assert sum(f["tokens"] for f in out["families_detail"]) == out["counts"]["awl_tokens"]
    assert len(out["families_found"]) == out["counts"]["awl_families"]
    assert out["counts"]["awl_tokens"] <= out["counts"]["content_tokens"]
    for fam in out["families_detail"]:
        if "spans" in fam:  # per-family highlight offsets, when the module reports them
            assert len(fam["spans"]) == fam["tokens"]
            assert all(0 <= s < t <= len(a.text) for s, t in fam["spans"])


def test_bnc_cumulative_coverage_is_monotonic_and_bounded(run):
    _, r = run
    bands = r["bnc_coca"]["per_band"]
    assert list(bands) == [str(i) for i in range(1, 26)]
    for field in ("cumulative_coverage_pct", "cumulative_coverage_with_supplementary_pct"):
        cum = [bands[str(i)][field] for i in range(1, 26)]
        assert cum == sorted(cum), field
        assert cum[-1] <= 100.0 + 1e-9, field
    last = bands["25"]
    assert last["cumulative_coverage_pct"] == pytest.approx(r["bnc_coca"]["coverage_pct"], abs=0.01)
    assert last["cumulative_coverage_with_supplementary_pct"] == pytest.approx(
        r["bnc_coca"]["coverage_with_supplementary_pct"], abs=0.01
    )


def test_cefr_cumulative_coverage_is_monotonic_and_bounded(run):
    _, r = run
    levels = r["cefr"]["per_level"]
    cum = [levels[lv]["cumulative_coverage_pct"] for lv in ("A1", "A2", "B1", "B2", "C1", "C2")]
    assert cum == sorted(cum)
    assert cum[-1] <= 100.0 + 1e-9


def test_metadiscourse_hits_have_exactly_one_category(run):
    a, r = run
    out = r["metadiscourse"]
    cats = set(out["per_category"])
    for h in out["hits"]:
        assert isinstance(h["category"], str) and h["category"] in cats
        assert h["category"] not in h.get("also_listed_as", [])
        assert a.text[h["span"][0] : h["span"][1]] == h["surface"]
    assert sum(c["hits"] for c in out["per_category"].values()) == out["counts"]["total_hits"]
    assert out["counts"]["interactive_hits"] + out["counts"]["interactional_hits"] == len(
        out["hits"]
    )
    _assert_no_overlap([h["span"] for h in out["hits"]])


def test_phrase_hits_do_not_overlap_and_spans_match(run):
    a, r = run
    out = r["phrase"]
    for h in out["hits"]:
        assert a.text[h["span"][0] : h["span"][1]] == h["surface"]
    _assert_no_overlap([h["span"] for h in out["hits"]])
    assert sum(out["hits_per_k_band"].values()) == out["counts"]["total_hits"]


def test_error_spans_match_surfaces(run):
    a, r = run
    out = r["errors"]
    for bucket in ("errors", "variant_mismatches", "unknown_names"):
        for e in out[bucket]:
            assert len(e["spans"]) == e["count"]
            for s, t in e["spans"]:
                assert a.text[s:t] == e["surface"]


def test_profile_rows_agree_with_list_modules(run):
    a, r = run
    if "profile" not in r:
        pytest.skip("profile module not present")
    prof = r["profile"]
    rows = [dict(zip(prof["columns"], row, strict=True)) for row in prof["rows"]]
    assert len(rows) == len(a.lexical)
    for row in rows:
        assert 0 <= row["start"] < row["end"] <= len(a.text)
    cefr = r["cefr"]
    for lvl in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert sum(1 for x in rows if x["cefr"] == lvl) == cefr["per_level"][lvl]["tokens"]
    assert sum(1 for x in rows if x["awl"] is not None) == r["awl"]["counts"]["awl_tokens"]
    assert sum(1 for x in rows if x["ngsl"] == "nawl") == r["ngsl"]["counts"]["nawl_tokens"]
    assert sum(1 for x in rows if x["bnc"] is None) == r["bnc_coca"]["counts"]["off_list_tokens"]


def test_pipeline_run_all_honours_module_subset():
    a, r = pipeline.run_all(SIMPLE, modules=["errors", "readability"], analysis=analysed(SIMPLE))
    # Results come back in pipeline order, not request order.
    assert list(r) == ["readability", "errors"]
    assert a is analysed(SIMPLE)


def test_pipeline_variant_reaches_errors():
    text = "The colour of the centre."
    _, gb = pipeline.run_all(text, modules=["errors"], variant="gb", analysis=analysed(text))
    _, us = pipeline.run_all(text, modules=["errors"], variant="us", analysis=analysed(text))
    assert gb["errors"]["variant"] == "gb"
    assert gb["errors"]["counts"]["variant_mismatches"] == 0
    assert us["errors"]["counts"]["variant_mismatches"] == 2


def test_passing_analysis_gives_same_result_as_raw_text():
    from lexinspect import bnc_coca, readability

    assert readability.analyze(HARD) == readability.analyze(HARD, analysis=analysed(HARD))
    assert bnc_coca.analyze(HARD) == bnc_coca.analyze(HARD, analysis=analysed(HARD))


def _assert_no_overlap(spans):
    spans = sorted(spans)
    for (_s1, e1), (s2, _e2) in zip(spans, spans[1:], strict=False):
        assert e1 <= s2, spans
