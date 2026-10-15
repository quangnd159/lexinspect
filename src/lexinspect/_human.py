"""Cloudflare Turnstile gate for the analysis endpoints.

Every POST under /v1/ parses a text with spaCy, which is the only thing on the
public deployment that costs money. The WAF rate limit caps what one IP can
spend; this caps what a script can spend at all, without asking people to sign
in.

Flow: the web UI runs an (almost always invisible) Turnstile challenge and sends
the token in the `CF-Turnstile-Response` header. The server checks it once with
Cloudflare's siteverify and answers with a signed cookie, so later analyses in
the next hour skip the challenge. Tokens are single-use and expire after five
minutes; the cookie is what keeps a working session quick.

Configuration (both or neither):
    TURNSTILE_SITE_KEY    public; the UI reads it from /v1/schema
    TURNSTILE_SECRET_KEY  private; also keys the cookie signature

With neither set the gate is off: local runs, tests and self-hosted copies keep
an open API. Set on the public deployment, the API is for browsers only; scripts
should run lexinspect themselves (`pip install`, the CLI or `lexinspect serve`).

If siteverify can't be reached the request fails with 503 rather than passing:
an outage at Cloudflare must not turn into an unmetered API.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException, Request, Response

SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()

TOKEN_HEADER = "CF-Turnstile-Response"
COOKIE = "lexinspect_pass"
PASS_SECONDS = 3600
ACTION = "analyse"
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SITEVERIFY_TIMEOUT = 5.0


def enabled() -> bool:
    return bool(SITE_KEY and SECRET_KEY)


def public_site_key() -> str | None:
    return SITE_KEY if enabled() else None


def _signature(expires: int) -> str:
    key = hmac.new(SECRET_KEY.encode(), b"lexinspect pass cookie v1", hashlib.sha256).digest()
    return hmac.new(key, str(expires).encode(), hashlib.sha256).hexdigest()


def issue_pass(now: float | None = None) -> str:
    expires = int(now if now is not None else time.time()) + PASS_SECONDS
    return f"{expires}.{_signature(expires)}"


def valid_pass(value: str | None, now: float | None = None) -> bool:
    if not value or "." not in value:
        return False
    raw, sig = value.split(".", 1)
    if not raw.isdigit():
        return False
    expires = int(raw)
    if expires < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(sig, _signature(expires))


def siteverify(token: str, remote_ip: str | None) -> bool:
    """True if Cloudflare accepts `token`. Raises HTTPException(503) if it can't be asked."""
    form = {"secret": SECRET_KEY, "response": token}
    if remote_ip:
        form["remoteip"] = remote_ip
    req = urllib.request.Request(
        SITEVERIFY_URL,
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=SITEVERIFY_TIMEOUT) as resp:
            result = json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise HTTPException(
            503,
            {
                "error": "challenge_unavailable",
                "detail": "The human check is unavailable. Try again in a moment.",
            },
        ) from e
    if not result.get("success"):
        return False
    # Cloudflare's test keys report no action; real widgets report the one we set.
    action = result.get("action")
    return not action or action == ACTION


def _client_ip(request: Request) -> str | None:
    ip = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "")
    ip = ip.split(",")[0].strip()
    return ip or (request.client.host if request.client else None)


def require(request: Request, response: Response) -> None:
    """FastAPI dependency: pass a signed cookie or a fresh Turnstile token, else 403."""
    if not enabled():
        return
    if valid_pass(request.cookies.get(COOKIE)):
        return
    token = request.headers.get(TOKEN_HEADER, "").strip()
    if token and len(token) <= 2048 and siteverify(token, _client_ip(request)):
        response.set_cookie(
            COOKIE,
            issue_pass(),
            max_age=PASS_SECONDS,
            httponly=True,
            secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
            samesite="strict",
            path="/v1/",
        )
        return
    raise HTTPException(
        403,
        {
            "error": "challenge_required",
            "detail": "Complete the human check to analyse text.",
        },
    )
