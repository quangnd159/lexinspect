"""FastAPI wrapper exposing every lexinspect module over HTTP.

Same JSON envelope shape as the CLI, so a client (Skill, browser, agent)
can call either transport identically. spaCy loads once at startup via the
lifespan handler — keep this in mind when scaling: each worker holds the
model in memory.

Run:
    uv run lexinspect serve --port 8000
    # or
    uvicorn lexinspect.api:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /v1/<module>      one per analytical module
    POST /v1/analyze       run all 9 modules
    GET  /v1/version       package version
    GET  /v1/schema        schema version + module catalog
    GET  /healthz          liveness probe
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from lexinspect import (
    __version__,
    awl,
    bnc_coca,
    cefr,
    cefr_level,
    diversity,
    errors,
    metadiscourse,
    ngsl,
    phrase,
    readability,
    statistics,
    tagger,
)
from lexinspect._nlp import get_nlp
from lexinspect._schema import SCHEMA_VERSION, envelope

MAX_TEXT_BYTES = 1_000_000  # 1 MB request cap; raise via env later if needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm spaCy + bundled data so the first real request is fast.
    get_nlp()
    bnc_coca._word_to_band()
    ngsl._ngsl()
    ngsl._nawl()
    awl._form_to_family()
    cefr._lemma_to_level()
    phrase._index()
    metadiscourse._index()
    yield


app = FastAPI(
    title="lexinspect",
    version=__version__,
    description="Local English text-analysis toolkit. Same JSON envelope as the CLI.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Static assets (CSS + per-concern JS modules) live next to index.html in the
# packaged `static/` directory. Mounted at /static so the HTML shell can load
# them via `<link>` and `<script src=...>`. Served with `Cache-Control:
# no-cache` so UI iterations land immediately on a normal reload — this is a
# self-hosted dev/teaching tool, not a high-traffic site, so the lost
# caching is essentially free.
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        return response


_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", NoCacheStaticFiles(directory=str(_STATIC_DIR)), name="static")


class TextIn(BaseModel):
    text: str = Field(..., description="The text to analyse.")
    source: str = Field(default="<api>", description="Optional label for the input.")


class TagIn(TextIn):
    include_tokens: bool = Field(default=False, description="Include per-token tag list.")


def _check(text: str) -> None:
    if not isinstance(text, str):
        raise HTTPException(422, "text must be a string")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise HTTPException(413, f"text exceeds {MAX_TEXT_BYTES} bytes")


def _wrap(module_name: str, body: TextIn, result: dict[str, Any]) -> dict[str, Any]:
    return envelope(module_name, body.source, len(body.text), result)


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = resources.files("lexinspect.static").joinpath("index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/version")
def version() -> dict[str, str]:
    return {"version": __version__, "schema_version": SCHEMA_VERSION}


@app.get("/v1/schema")
def schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "modules": [
            "readability",
            "statistics",
            "diversity",
            "tagger",
            "awl",
            "bnc_coca",
            "ngsl",
            "phrase",
            "cefr",
            "metadiscourse",
        ],
        # Optional modules require extras and are advertised separately so they
        # don't change the always-available `modules` contract. Each entry maps
        # to the pip extra that activates it.
        "modules_optional": {
            "cefr_level": "cefr-level",
            "errors": "errors",
        },
    }


@app.post("/v1/readability")
def post_readability(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("readability", body, readability.analyze(body.text))


@app.post("/v1/statistics")
def post_statistics(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("statistics", body, statistics.analyze(body.text))


@app.post("/v1/diversity")
def post_diversity(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("diversity", body, diversity.analyze(body.text))


@app.post("/v1/tag")
def post_tag(body: TagIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("tagger", body, tagger.analyze(body.text, include_tokens=body.include_tokens))


@app.post("/v1/awl")
def post_awl(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("awl", body, awl.analyze(body.text))


@app.post("/v1/bnc-coca")
def post_bnc_coca(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("bnc_coca", body, bnc_coca.analyze(body.text))


@app.post("/v1/ngsl")
def post_ngsl(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("ngsl", body, ngsl.analyze(body.text))


@app.post("/v1/phrase")
def post_phrase(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("phrase", body, phrase.analyze(body.text))


@app.post("/v1/cefr")
def post_cefr(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("cefr", body, cefr.analyze(body.text))


@app.post("/v1/cefr-level")
def post_cefr_level(body: TextIn) -> dict[str, Any]:
    """Classify the text into a CEFR band (A1–C2) via UniversalCEFR ModernBERT.

    Requires the `cefr-level` extra. Returns 503 with install hint if missing.
    Heavier than the other endpoints: ~2–5s CPU inference per request.
    """
    _check(body.text)
    try:
        result = cefr_level.analyze(body.text)
    except cefr_level.CEFRLevelExtraNotInstalled as e:
        raise HTTPException(503, str(e)) from e
    return _wrap("cefr_level", body, result)


@app.post("/v1/metadiscourse")
def post_metadiscourse(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    return _wrap("metadiscourse", body, metadiscourse.analyze(body.text))


class ErrorsIn(TextIn):
    variant: str = Field(
        default="gb",
        description='English variant: "gb" (British, default) or "us" (American).',
    )


@app.post("/v1/errors")
def post_errors(body: ErrorsIn) -> dict[str, Any]:
    """Hunspell-based spelling-error detection.

    Requires the `errors` extra. Returns 503 with install hint if missing.
    First call per variant downloads the dictionary (~1.5 MB) into the user
    cache; subsequent calls reuse the in-memory dictionary.
    """
    _check(body.text)
    if body.variant not in errors.VALID_VARIANTS:
        raise HTTPException(
            422, f"variant must be one of {errors.VALID_VARIANTS}, got {body.variant!r}"
        )
    try:
        result = errors.analyze(body.text, variant=body.variant)
    except errors.ErrorsExtraNotInstalled as e:
        raise HTTPException(503, str(e)) from e
    except errors.DictionaryFetchError as e:
        raise HTTPException(502, str(e)) from e
    return _wrap("errors", body, result)


@app.post("/v1/analyze")
def post_analyze(body: TextIn) -> dict[str, Any]:
    _check(body.text)
    text = body.text
    return {
        "schema_version": SCHEMA_VERSION,
        "module": "analyze",
        "input": {"source": body.source, "char_count": len(text)},
        "results": {
            "readability": readability.analyze(text),
            "statistics": statistics.analyze(text),
            "diversity": diversity.analyze(text),
            "tagger": tagger.analyze(text),
            "awl": awl.analyze(text),
            "bnc_coca": bnc_coca.analyze(text),
            "ngsl": ngsl.analyze(text),
            "phrase": phrase.analyze(text),
            "cefr": cefr.analyze(text),
            "metadiscourse": metadiscourse.analyze(text),
        },
    }
