"""End-to-end API tests via FastAPI TestClient."""

from __future__ import annotations

import pytest
from conftest import ACADEMIC, SIMPLE

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from lexinspect import pipeline  # noqa: E402
from lexinspect.api import MAX_TEXT_BYTES, app  # noqa: E402

CORE_MODULES = {
    "readability", "statistics", "diversity", "tagger", "awl", "bnc_coca", "ngsl", "phrase",
    "cefr", "metadiscourse", "errors",
}  # fmt: skip


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<textarea" in r.text
    assert 'href="/privacy"' in r.text


def test_privacy_page(client):
    r = client.get("/privacy")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # every name the page lists is one the site actually stores
    for name in (
        "lexinspect_pass",
        "lexinspect:draft",
        "lexinspect:variant",
        "lexinspect:pass-until",
    ):
        assert name in r.text


def test_version(client):
    r = client.get("/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "2"
    assert body["version"]


def test_schema(client):
    r = client.get("/v1/schema")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "2"
    assert body["modules"] == list(pipeline.MODULES)
    assert set(body["modules"]) >= CORE_MODULES
    assert body["limits"] == {"max_text_bytes": MAX_TEXT_BYTES}
    assert "cefr_level" in body["modules_optional"]
    assert "public" in r.headers["cache-control"]


@pytest.mark.parametrize(
    "endpoint,envelope_module,text",
    [
        ("/v1/readability", "readability", SIMPLE),
        ("/v1/statistics", "statistics", SIMPLE),
        ("/v1/diversity", "diversity", SIMPLE),
        ("/v1/tag", "tagger", SIMPLE),
        ("/v1/awl", "awl", ACADEMIC),
        ("/v1/bnc-coca", "bnc_coca", ACADEMIC),
        ("/v1/ngsl", "ngsl", ACADEMIC),
        ("/v1/phrase", "phrase", SIMPLE),
        ("/v1/cefr", "cefr", ACADEMIC),
        ("/v1/metadiscourse", "metadiscourse", ACADEMIC),
        ("/v1/errors", "errors", SIMPLE),
    ],
)
def test_module_endpoints(client, endpoint, envelope_module, text):
    r = client.post(endpoint, json={"text": text, "source": "fixture"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == "2"
    assert body["module"] == envelope_module
    assert body["input"]["source"] == "fixture"
    assert body["input"]["char_count"] == len(text)
    assert body["input"]["word_count"] == len(text.split())  # fixtures are plain prose
    assert "result" in body
    assert r.headers["cache-control"] == "no-store"


def test_analyze_runs_every_module_including_errors(client):
    r = client.post("/v1/analyze", json={"text": ACADEMIC})
    assert r.status_code == 200
    body = r.json()
    assert body["module"] == "analyze"
    assert body["schema_version"] == "2"
    assert list(body["results"]) == list(pipeline.MODULES)
    assert set(body["results"]) >= CORE_MODULES
    inp = body["input"]
    assert inp["word_count"] == body["results"]["readability"]["counts"]["words"]
    assert inp["sentence_count"] == body["results"]["readability"]["counts"]["sentences"]
    assert inp["char_count"] == len(ACADEMIC)


def test_analyze_module_subset_and_variant(client):
    r = client.post(
        "/v1/analyze",
        json={"text": "The color is nice.", "modules": ["errors", "readability"], "variant": "gb"},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert list(results) == ["readability", "errors"]
    assert results["errors"]["variant"] == "gb"
    assert results["errors"]["variant_mismatches"][0]["suggestions"] == ["colour"]

    r = client.post(
        "/v1/analyze", json={"text": "The color is nice.", "modules": ["errors"], "variant": "us"}
    )
    assert r.json()["results"]["errors"]["variant_mismatches"] == []


def test_analyze_unknown_module_is_422(client):
    r = client.post("/v1/analyze", json={"text": "Hi.", "modules": ["readability", "nope"]})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_request"
    assert "nope" in detail["detail"]


def test_analyze_bad_variant_is_422(client):
    r = client.post("/v1/analyze", json={"text": "Hi.", "variant": "fr"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


def test_errors_endpoint_rejects_bad_variant(client):
    r = client.post("/v1/errors", json={"text": "hello", "variant": "fr"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "invalid_request"
    assert body["detail"].startswith("variant:")


def test_errors_endpoint_finds_errors(client):
    r = client.post("/v1/errors", json={"text": "I recieve mail.", "variant": "us"})
    assert r.status_code == 200
    (e,) = r.json()["result"]["errors"]
    assert e["surface"] == "recieve"
    assert e["suggestions"][0] == "receive"


def test_tag_with_include_tokens(client):
    r = client.post("/v1/tag", json={"text": "Cats sleep.", "include_tokens": True})
    assert r.status_code == 200
    assert [t["text"] for t in r.json()["result"]["tokens"]] == ["Cats", "sleep", "."]


def test_text_size_limit_shape(client):
    big = "x" * (MAX_TEXT_BYTES + 1)
    for endpoint in ("/v1/readability", "/v1/analyze", "/v1/errors"):
        r = client.post(endpoint, json={"text": big})
        assert r.status_code == 413, endpoint
        detail = r.json()["detail"]
        assert detail["error"] == "text_too_large"
        assert detail["limit_bytes"] == MAX_TEXT_BYTES
        assert f"{MAX_TEXT_BYTES:,}" in detail["detail"]


def test_size_limit_counts_utf8_bytes(client):
    # 2-byte characters: under the limit in characters, over it in bytes.
    text = "é" * (MAX_TEXT_BYTES // 2 + 1)
    assert len(text) < MAX_TEXT_BYTES
    assert client.post("/v1/statistics", json={"text": text}).status_code == 413


def test_missing_text_field_shape(client):
    r = client.post("/v1/readability", json={"source": "no text"})
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_request", "detail": "text: Field required"}


def test_source_too_long_is_422(client):
    r = client.post("/v1/readability", json={"text": "Hi.", "source": "s" * 201})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


@pytest.mark.parametrize("path", ["/healthz", "/v1/version", "/v1/schema", "/"])
def test_security_headers_on_get(client, path):
    h = client.get(path).headers
    assert "script-src 'self'" in h["content-security-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"


def test_security_headers_and_no_store_on_post(client):
    for r in (
        client.post("/v1/readability", json={"text": "Hi there."}),
        client.post("/v1/analyze", json={"text": "Hi there.", "modules": ["statistics"]}),
        client.post("/v1/readability", json={}),  # 422
        client.post("/v1/readability", json={"text": "x" * (MAX_TEXT_BYTES + 1)}),  # 413
    ):
        assert r.headers["cache-control"] == "no-store"
        assert "content-security-policy" in r.headers
        assert r.headers["x-content-type-options"] == "nosniff"


def test_docs_are_exempt_from_csp(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers
    assert r.headers["x-frame-options"] == "DENY"


def test_static_assets_served(client):
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert r.headers["content-type"].split(";")[0] in {"application/javascript", "text/javascript"}


def test_export_menu_wired(client):
    # export.js reads LEVELS from panels.js and is used by app.js: order matters.
    page = client.get("/").text
    assert (
        page.index("/static/panels.js")
        < page.index("/static/export.js")
        < page.index("/static/app.js")
    )
    assert 'id="exportMenu"' in page and 'id="report"' in page
    js = client.get("/static/export.js")
    assert js.status_code == 200
    assert "summaryCsv" in js.text
