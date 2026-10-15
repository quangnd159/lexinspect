"""Turnstile gate on the analysis endpoints (siteverify is stubbed; no network)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lexinspect import _human
from lexinspect.api import app

TEXT = {"text": "The cat sat on the mat. It was warm."}


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setattr(_human, "SITE_KEY", "site-key")
    monkeypatch.setattr(_human, "SECRET_KEY", "secret-key")
    calls: list[str] = []

    def fake_siteverify(token, remote_ip):
        calls.append(token)
        return token == "good"

    monkeypatch.setattr(_human, "siteverify", fake_siteverify)
    with TestClient(app, base_url="https://testserver") as c:
        c.calls = calls
        yield c


def test_open_when_unconfigured():
    with TestClient(app) as c:
        assert c.post("/v1/analyze", json=TEXT).status_code == 200
        assert c.get("/v1/schema").json()["turnstile_site_key"] is None


def test_schema_advertises_site_key(gated):
    assert gated.get("/v1/schema").json()["turnstile_site_key"] == "site-key"


@pytest.mark.parametrize("path", ["/v1/analyze", "/v1/readability", "/v1/errors", "/v1/tag"])
def test_every_analysis_endpoint_needs_a_check(gated, path):
    r = gated.post(path, json=TEXT)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "challenge_required"


def test_bad_token_is_refused(gated):
    r = gated.post("/v1/analyze", json=TEXT, headers={_human.TOKEN_HEADER: "bad"})
    assert r.status_code == 403


def test_good_token_earns_a_pass_that_skips_siteverify(gated):
    r = gated.post("/v1/analyze", json=TEXT, headers={_human.TOKEN_HEADER: "good"})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert _human.COOKIE in cookie
    assert "httponly" in cookie.lower() and "samesite=strict" in cookie.lower()
    assert "secure" in cookie.lower()
    # The client keeps the cookie; the next request needs no token.
    assert gated.post("/v1/readability", json=TEXT).status_code == 200
    assert gated.calls == ["good"]


def test_forged_or_expired_pass_is_refused(gated):
    gated.cookies.set(_human.COOKIE, "9999999999.deadbeef", path="/v1/")
    assert gated.post("/v1/analyze", json=TEXT).status_code == 403
    expired = _human.issue_pass(now=0)
    gated.cookies.set(_human.COOKIE, expired, path="/v1/")
    assert gated.post("/v1/analyze", json=TEXT).status_code == 403


def test_pass_signature_is_tied_to_the_secret(monkeypatch):
    monkeypatch.setattr(_human, "SECRET_KEY", "one")
    value = _human.issue_pass()
    assert _human.valid_pass(value)
    monkeypatch.setattr(_human, "SECRET_KEY", "two")
    assert not _human.valid_pass(value)


def test_metadata_endpoints_stay_open(gated):
    assert gated.get("/v1/version").status_code == 200
    assert gated.get("/healthz").status_code == 200


def test_siteverify_outage_fails_closed(monkeypatch):
    monkeypatch.setattr(_human, "SECRET_KEY", "secret-key")
    monkeypatch.setattr(_human, "SITEVERIFY_URL", "http://127.0.0.1:9/unreachable")
    monkeypatch.setattr(_human, "SITEVERIFY_TIMEOUT", 0.5)
    with pytest.raises(_human.HTTPException) as e:
        _human.siteverify("token", None)
    assert e.value.status_code == 503
