"""FastAPI wrapper exposing every lexinspect module over HTTP.

Same JSON envelope as the CLI. Every request is normalised and parsed exactly
once (`lexinspect._text.analyse`) and the modules read that shared analysis,
so the numbers on one tab always agree with the numbers on the next.

Run locally:
    uv run lexinspect serve --port 8000

On Vercel the web UI's static files are served from the CDN (`public/`, copied
in CI from `src/lexinspect/static/`), so a page view costs no function time;
this app only answers `/v1/*`. The static routes below remain for local use.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lexinspect import (
    __version__,
    _human,
    awl,
    bnc_coca,
    cefr,
    cefr_level,
    diversity,
    errors,
    metadiscourse,
    ngsl,
    phrase,
    pipeline,
    readability,
    statistics,
    tagger,
)
from lexinspect._schema import SCHEMA_VERSION, envelope
from lexinspect._text import analyse

# Request cap. Analysis cost is linear in text length, so this bounds what one
# request can cost. 50 KB is ~8,000 words — an IELTS Task 2 essay is under 3 KB.
MAX_TEXT_BYTES = int(os.environ.get("LEXINSPECT_MAX_TEXT_BYTES", 50_000))

# Comma-separated origins allowed to call the API from a browser. The hosted UI
# is same-origin and needs nothing here; default "*" keeps the public API open
# to scripts and notebooks, which is the point of having one.
_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("LEXINSPECT_ALLOWED_ORIGINS", "*").split(",") if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load spaCy, CMUdict, every word list and both Hunspell dictionaries once,
    # single-threaded, before the first request. Sync handlers run on a
    # threadpool; lazy first-use loading under concurrency is how this app used
    # to race itself into 500s.
    pipeline.warm()
    yield


app = FastAPI(
    title="lexinspect",
    version=__version__,
    description=(
        "English text analysis: readability, lexical diversity, vocabulary profiles "
        "(CEFR, BNC/COCA, NGSL/NAWL, AWL), phrasal expressions, metadiscourse and spelling. "
        'Every endpoint takes `{"text": ...}` and returns the same envelope as the CLI.'
    ),
    lifespan=lifespan,
)

# A full analysis of a long text is a few hundred KB of JSON (mostly the
# per-word profile); it compresses ~10x.
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", _human.TOKEN_HEADER],
    max_age=86400,
)

# The UI renders user text back into the page, so `script-src` is the
# load-bearing header: it neutralises any rendering path that regresses to
# innerHTML. Its one third-party origin is Cloudflare Turnstile (script plus
# its challenge iframe). Mirrored in vercel.json for the CDN-served files.
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
        "frame-src https://challenges.cloudflare.com; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}
# Swagger UI loads from a CDN; it renders no user input.
_CSP_EXEMPT_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        if header == "Content-Security-Policy" and request.url.path in _CSP_EXEMPT_PATHS:
            continue
        response.headers.setdefault(header, value)
    if request.url.path.startswith("/v1/"):
        # Analyses are a pure function of the body; nothing to cache on GET
        # except the metadata endpoints, which set their own headers.
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_request",
            "detail": f"{where}: {first.get('msg', 'invalid')}".strip(": "),
        },
    )


# --- static UI (local; the CDN serves these on Vercel) -------------------------

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/licences", include_in_schema=False)
def licences() -> FileResponse:
    return FileResponse(_STATIC_DIR / "licences.html", headers={"Cache-Control": "no-cache"})


# --- request models -------------------------------------------------------------


class TextIn(BaseModel):
    text: str = Field(..., description="The text to analyse (UTF-8, up to the size cap).")
    source: str = Field(default="<api>", max_length=200, description="Optional label echoed back.")


class TagIn(TextIn):
    include_tokens: bool = Field(default=False, description="Include the per-token tag list.")


class ErrorsIn(TextIn):
    variant: Literal["gb", "us"] = Field(
        default="gb", description="British (gb) or American (us) English."
    )


class AnalyzeIn(TextIn):
    variant: Literal["gb", "us"] = Field(
        default="gb", description="Spelling variety for the errors module."
    )
    modules: list[str] | None = Field(
        default=None,
        description=f"Subset of modules to run (default: all). One of {list(pipeline.MODULES)}.",
    )


def _check(text: str) -> None:
    size = len(text.encode("utf-8"))
    if size > MAX_TEXT_BYTES:
        raise HTTPException(
            413,
            {
                "error": "text_too_large",
                "detail": f"Text is {size:,} bytes; the limit is {MAX_TEXT_BYTES:,}.",
                "limit_bytes": MAX_TEXT_BYTES,
            },
        )


def _run(module: str, body: TextIn, fn, **kw) -> dict[str, Any]:
    _check(body.text)
    a = analyse(body.text)
    return envelope(
        module, body.source, len(body.text), fn(a.text, analysis=a, **kw), words=a.word_count
    )


# --- metadata -------------------------------------------------------------------

_META_CACHE = {"Cache-Control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"}


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/version")
def version() -> JSONResponse:
    return JSONResponse(
        {"version": __version__, "schema_version": SCHEMA_VERSION}, headers=_META_CACHE
    )


_OPTIONAL_MODULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "cefr_level": ("cefr-level", ("transformers", "torch")),
}


def _installed(pkg: str) -> bool:
    try:
        return find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


@app.get("/v1/schema")
def schema() -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": SCHEMA_VERSION,
            "version": __version__,
            "modules": list(pipeline.MODULES),
            "modules_optional": {name: extra for name, (extra, _p) in _OPTIONAL_MODULES.items()},
            "optional_available": {
                name: all(_installed(p) for p in pkgs)
                for name, (_e, pkgs) in _OPTIONAL_MODULES.items()
            },
            "limits": {"max_text_bytes": MAX_TEXT_BYTES},
            # Public Turnstile site key when the human check is on, else null.
            "turnstile_site_key": _human.public_site_key(),
        },
        headers=_META_CACHE,
    )


# --- modules --------------------------------------------------------------------

# Every analysis parses the text, which is the cost worth protecting; see _human.
_GATED = [Depends(_human.require)]


@app.post("/v1/readability", dependencies=_GATED)
def post_readability(body: TextIn) -> dict[str, Any]:
    return _run("readability", body, readability.analyze)


@app.post("/v1/statistics", dependencies=_GATED)
def post_statistics(body: TextIn) -> dict[str, Any]:
    return _run("statistics", body, statistics.analyze)


@app.post("/v1/diversity", dependencies=_GATED)
def post_diversity(body: TextIn) -> dict[str, Any]:
    return _run("diversity", body, diversity.analyze)


@app.post("/v1/tag", dependencies=_GATED)
def post_tag(body: TagIn) -> dict[str, Any]:
    return _run("tagger", body, tagger.analyze, include_tokens=body.include_tokens)


@app.post("/v1/awl", dependencies=_GATED)
def post_awl(body: TextIn) -> dict[str, Any]:
    return _run("awl", body, awl.analyze)


@app.post("/v1/bnc-coca", dependencies=_GATED)
def post_bnc_coca(body: TextIn) -> dict[str, Any]:
    return _run("bnc_coca", body, bnc_coca.analyze)


@app.post("/v1/ngsl", dependencies=_GATED)
def post_ngsl(body: TextIn) -> dict[str, Any]:
    return _run("ngsl", body, ngsl.analyze)


@app.post("/v1/phrase", dependencies=_GATED)
def post_phrase(body: TextIn) -> dict[str, Any]:
    return _run("phrase", body, phrase.analyze)


@app.post("/v1/cefr", dependencies=_GATED)
def post_cefr(body: TextIn) -> dict[str, Any]:
    return _run("cefr", body, cefr.analyze)


@app.post("/v1/metadiscourse", dependencies=_GATED)
def post_metadiscourse(body: TextIn) -> dict[str, Any]:
    return _run("metadiscourse", body, metadiscourse.analyze)


@app.post("/v1/errors", dependencies=_GATED)
def post_errors(body: ErrorsIn) -> dict[str, Any]:
    try:
        return _run("errors", body, errors.analyze, variant=body.variant)
    except (errors.ErrorsExtraNotInstalled, errors.DictionaryFetchError) as e:
        raise HTTPException(503, {"error": "unavailable", "detail": str(e)}) from e


@app.post("/v1/cefr-level", dependencies=_GATED)
def post_cefr_level(body: TextIn) -> dict[str, Any]:
    """CEFR band from the UniversalCEFR ModernBERT classifier (optional extra; 503 if absent)."""
    _check(body.text)
    try:
        result = cefr_level.analyze(body.text)
    except cefr_level.CEFRLevelExtraNotInstalled as e:
        raise HTTPException(503, {"error": "unavailable", "detail": str(e)}) from e
    return envelope("cefr_level", body.source, len(body.text), result)


@app.post("/v1/analyze", dependencies=_GATED)
def post_analyze(body: AnalyzeIn) -> dict[str, Any]:
    _check(body.text)
    unknown = sorted(set(body.modules or ()) - set(pipeline.MODULES))
    if unknown:
        raise HTTPException(
            422, {"error": "invalid_request", "detail": f"unknown modules: {unknown}"}
        )
    a, results = pipeline.run_all(body.text, modules=body.modules, variant=body.variant)
    inp: dict[str, Any] = {
        "source": body.source,
        "char_count": len(body.text),
        "word_count": a.word_count,
        "sentence_count": a.sentence_count,
    }
    if a.text != body.text:
        # Every `span` indexes the normalised text (NFC, soft hyphens and
        # zero-width characters removed). Send it back when it differs so a
        # client can highlight the right characters.
        inp["normalised_text"] = a.text
    return {"schema_version": SCHEMA_VERSION, "module": "analyze", "input": inp, "results": results}
