"""Smoke tests for NGSL/NAWL coverage."""

from lexinspect import _lists, ngsl


def test_data_loads():
    ngsl_lemmas = {item["lemma"] for item in _lists.ngsl_forms().values()}
    nawl_lemmas = {item["lemma"] for item in _lists.nawl_forms().values()}
    assert len(ngsl_lemmas) == 2809
    assert len(nawl_lemmas) == 959


def test_returns_expected_keys(simple):
    out = ngsl.analyze(simple)
    assert {"counts", "coverage_pct", "ngsl_lemmas_found", "nawl_lemmas_found"} <= set(out)


def test_simple_text_high_ngsl_coverage(simple):
    out = ngsl.analyze(simple)
    assert out["coverage_pct"]["ngsl"] >= 80.0


def test_academic_text_has_nawl_hits(academic):
    out = ngsl.analyze(academic)
    assert out["counts"]["nawl_tokens"] >= 1
