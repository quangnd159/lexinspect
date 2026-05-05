"""End-to-end API tests via FastAPI TestClient."""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from lexinspect.api import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE = (FIXTURES / "sample_simple.txt").read_text()
ACADEMIC = (FIXTURES / "sample_academic.txt").read_text()


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
    assert "lexinspect" in r.text
    assert "<textarea" in r.text


def test_version(client):
    r = client.get("/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "1"
    assert body["version"]


def test_schema_lists_all_modules(client):
    r = client.get("/v1/schema")
    assert r.status_code == 200
    assert set(r.json()["modules"]) == {
        "readability",
        "diversity",
        "tagger",
        "awl",
        "bnc_coca",
        "ngsl",
        "phrase",
        "cefr",
        "metadiscourse",
    }


@pytest.mark.parametrize(
    "endpoint,envelope_module,text",
    [
        ("/v1/readability", "readability", SIMPLE),
        ("/v1/diversity", "diversity", SIMPLE),
        ("/v1/tag", "tagger", SIMPLE),
        ("/v1/awl", "awl", ACADEMIC),
        ("/v1/bnc-coca", "bnc_coca", ACADEMIC),
        ("/v1/ngsl", "ngsl", ACADEMIC),
        ("/v1/phrase", "phrase", SIMPLE),
        ("/v1/cefr", "cefr", ACADEMIC),
        ("/v1/metadiscourse", "metadiscourse", ACADEMIC),
    ],
)
def test_module_endpoints(client, endpoint, envelope_module, text):
    r = client.post(endpoint, json={"text": text, "source": "fixture"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == "1"
    assert body["module"] == envelope_module
    assert body["input"]["source"] == "fixture"
    assert body["input"]["char_count"] == len(text)
    assert "result" in body


def test_analyze_endpoint(client):
    r = client.post("/v1/analyze", json={"text": ACADEMIC})
    assert r.status_code == 200
    body = r.json()
    assert body["module"] == "analyze"
    assert set(body["results"]) == {
        "readability",
        "diversity",
        "tagger",
        "awl",
        "bnc_coca",
        "ngsl",
        "phrase",
        "cefr",
        "metadiscourse",
    }


def test_tag_with_include_tokens(client):
    r = client.post("/v1/tag", json={"text": "Cats sleep.", "include_tokens": True})
    assert r.status_code == 200
    assert "tokens" in r.json()["result"]


def test_text_size_limit(client):
    big = "x" * 2_000_000
    r = client.post("/v1/readability", json={"text": big})
    assert r.status_code == 413


def test_missing_text_field(client):
    r = client.post("/v1/readability", json={"source": "no text"})
    assert r.status_code == 422
