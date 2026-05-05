"""Typer CLI for lexinspect.

JSON output by default. Use --format human for terminal-friendly tables.
Pass `-` as the file argument to read from stdin.
"""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from lexinspect import (
    __version__,
    awl,
    bnc_coca,
    cefr,
    diversity,
    metadiscourse,
    ngsl,
    phrase,
    readability,
    tagger,
)
from lexinspect._io import read_text
from lexinspect._schema import envelope

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Local English text-analysis toolkit. JSON-out by default.",
)

FormatOpt = Annotated[
    str, typer.Option("--format", "-f", help="Output format: json | human", case_sensitive=False)
]
FileArg = Annotated[str, typer.Argument(help="Path to a text file. Use '-' to read stdin.")]


def _emit(payload: dict[str, Any], fmt: str) -> None:
    if fmt.lower() == "human":
        _human(payload)
    else:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")


def _human(payload: dict[str, Any]) -> None:
    console = Console()
    module = payload.get("module", "?")
    src = payload.get("input", {}).get("source", "?")
    console.rule(f"[bold]{module}[/bold] :: {src}")
    result = payload.get("result") or payload.get("results") or {}
    _render(console, result)


def _render(console: Console, obj: Any, level: int = 0) -> None:
    if isinstance(obj, dict):
        flat = {k: v for k, v in obj.items() if not isinstance(v, (dict, list))}
        if flat:
            t = Table(show_header=False, box=None, pad_edge=False)
            for k, v in flat.items():
                t.add_row(str(k), str(v))
            console.print(t)
        for k, v in obj.items():
            if isinstance(v, dict):
                console.print(f"\n[bold cyan]{k}[/bold cyan]")
                _render(console, v, level + 1)
            elif isinstance(v, list) and v and not isinstance(v[0], (dict, list)):
                console.print(f"\n[bold cyan]{k}[/bold cyan] ({len(v)})")
                console.print(", ".join(map(str, v[:50])) + (" …" if len(v) > 50 else ""))


@app.command()
def readability_(file: FileArg, format: FormatOpt = "json") -> None:
    """Readability metrics + basic text statistics."""
    text, src = read_text(file)
    result = readability.analyze(text)
    _emit(envelope("readability", src, len(text), result), format)


# typer maps the function name; rename for the public command surface
app.command(name="readability")(readability_)


@app.command()
def diversity_(file: FileArg, format: FormatOpt = "json") -> None:
    """Lexical diversity metrics (MTLD, HD-D, MATTR, TTR family)."""
    text, src = read_text(file)
    result = diversity.analyze(text)
    _emit(envelope("diversity", src, len(text), result), format)


app.command(name="diversity")(diversity_)


@app.command()
def tag(
    file: FileArg,
    format: FormatOpt = "json",
    include_tokens: Annotated[
        bool, typer.Option("--tokens", help="Include per-token tag list in output.")
    ] = False,
) -> None:
    """POS tagging (Penn Treebank + Universal POS distributions) via spaCy."""
    text, src = read_text(file)
    result = tagger.analyze(text, include_tokens=include_tokens)
    _emit(envelope("tagger", src, len(text), result), format)


@app.command(name="awl")
def awl_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """Coxhead Academic Word List coverage profile."""
    text, src = read_text(file)
    result = awl.analyze(text)
    _emit(envelope("awl", src, len(text), result), format)


@app.command(name="bnc-coca")
def bnc_coca_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """Nation BNC/COCA frequency-band profile (1k–10k headwords, CC0 mirror)."""
    text, src = read_text(file)
    result = bnc_coca.analyze(text)
    _emit(envelope("bnc_coca", src, len(text), result), format)


@app.command(name="ngsl")
def ngsl_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """NGSL + NAWL coverage profile (Browne, Culligan, Phillips)."""
    text, src = read_text(file)
    result = ngsl.analyze(text)
    _emit(envelope("ngsl", src, len(text), result), format)


@app.command(name="phrase")
def phrase_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """PHRASE list detection (Martinez & Schmitt 2012, K1–K5 bands)."""
    text, src = read_text(file)
    result = phrase.analyze(text)
    _emit(envelope("phrase", src, len(text), result), format)


@app.command(name="cefr")
def cefr_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """CEFR profile (A1–C2) using CEFR-J 1.5 + Octanove C1/C2 1.0."""
    text, src = read_text(file)
    result = cefr.analyze(text)
    _emit(envelope("cefr", src, len(text), result), format)


@app.command(name="metadiscourse")
def metadiscourse_cmd(file: FileArg, format: FormatOpt = "json") -> None:
    """Hyland (2005) metadiscourse marker detection — 10 categories."""
    text, src = read_text(file)
    result = metadiscourse.analyze(text)
    _emit(envelope("metadiscourse", src, len(text), result), format)


@app.command()
def analyze(file: FileArg, format: FormatOpt = "json") -> None:
    """Run all modules and emit a combined report."""
    text, src = read_text(file)
    payload = {
        "schema_version": "1",
        "module": "analyze",
        "input": {"source": src, "char_count": len(text)},
        "results": {
            "readability": readability.analyze(text),
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
    _emit(payload, format)


@app.command()
def version() -> None:
    """Print lexinspect version."""
    typer.echo(__version__)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port.")] = 8000,
    reload: Annotated[bool, typer.Option(help="Auto-reload on code change (dev only).")] = False,
    workers: Annotated[int, typer.Option(help="Worker process count.")] = 1,
) -> None:
    """Run the FastAPI server (requires the `web` extra: uv sync --extra web)."""
    try:
        import uvicorn
    except ImportError as e:
        raise typer.Exit(
            "FastAPI/uvicorn not installed. Run: uv sync --extra web"
        ) from e
    uvicorn.run(
        "lexinspect.api:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
    )


if __name__ == "__main__":
    app()
