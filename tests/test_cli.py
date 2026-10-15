"""End-to-end CLI tests via Typer's CliRunner."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lexinspect import pipeline
from lexinspect.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE = str(FIXTURES / "sample_simple.txt")
ACADEMIC = str(FIXTURES / "sample_academic.txt")

runner = CliRunner()


@pytest.mark.parametrize(
    "subcommand,fixture,envelope_module",
    [
        ("readability", SIMPLE, "readability"),
        ("statistics", SIMPLE, "statistics"),
        ("diversity", SIMPLE, "diversity"),
        ("tag", SIMPLE, "tagger"),
        ("awl", ACADEMIC, "awl"),
        ("bnc-coca", ACADEMIC, "bnc_coca"),
        ("ngsl", ACADEMIC, "ngsl"),
        ("phrase", SIMPLE, "phrase"),
        ("cefr", ACADEMIC, "cefr"),
        ("metadiscourse", ACADEMIC, "metadiscourse"),
        ("errors", SIMPLE, "errors"),
    ],
)
def test_subcommand_emits_valid_json(subcommand, fixture, envelope_module):
    result = runner.invoke(app, [subcommand, fixture])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "2"
    assert payload["module"] == envelope_module
    assert "result" in payload


def test_analyze_combines_modules():
    result = runner.invoke(app, ["analyze", ACADEMIC])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["module"] == "analyze"
    assert payload["schema_version"] == "2"
    assert list(payload["results"]) == list(pipeline.MODULES)
    assert "errors" in payload["results"]
    inp = payload["input"]
    assert inp["word_count"] == payload["results"]["readability"]["counts"]["words"]
    assert inp["sentence_count"] == payload["results"]["readability"]["counts"]["sentences"]


def test_analyze_variant(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("The color of the center.")
    gb = json.loads(runner.invoke(app, ["analyze", str(f), "--variant", "gb"]).stdout)
    us = json.loads(runner.invoke(app, ["analyze", str(f), "--variant", "us"]).stdout)
    assert gb["results"]["errors"]["counts"]["variant_mismatches"] == 2
    assert us["results"]["errors"]["counts"]["variant_mismatches"] == 0


def test_cli_and_api_agree():
    from lexinspect.api import AnalyzeIn, post_analyze

    text = Path(ACADEMIC).read_text()
    cli = json.loads(runner.invoke(app, ["analyze", ACADEMIC]).stdout)
    api = post_analyze(AnalyzeIn(text=text))
    assert cli["results"] == json.loads(json.dumps(api["results"]))


def test_human_format_runs():
    result = runner.invoke(app, ["readability", SIMPLE, "--format", "human"])
    assert result.exit_code == 0
    assert "readability" in result.stdout.lower()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()
