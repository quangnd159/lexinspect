"""End-to-end CLI tests via Typer's CliRunner."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lexinspect.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE = str(FIXTURES / "sample_simple.txt")
ACADEMIC = str(FIXTURES / "sample_academic.txt")

runner = CliRunner()


@pytest.mark.parametrize(
    "subcommand,fixture,envelope_module",
    [
        ("readability", SIMPLE, "readability"),
        ("diversity", SIMPLE, "diversity"),
        ("tag", SIMPLE, "tagger"),
        ("awl", ACADEMIC, "awl"),
        ("bnc-coca", ACADEMIC, "bnc_coca"),
        ("ngsl", ACADEMIC, "ngsl"),
        ("phrase", SIMPLE, "phrase"),
        ("cefr", ACADEMIC, "cefr"),
    ],
)
def test_subcommand_emits_valid_json(subcommand, fixture, envelope_module):
    result = runner.invoke(app, [subcommand, fixture])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert payload["module"] == envelope_module
    assert "result" in payload


def test_analyze_combines_modules():
    result = runner.invoke(app, ["analyze", ACADEMIC])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["module"] == "analyze"
    assert set(payload["results"]) == {
        "readability",
        "diversity",
        "tagger",
        "awl",
        "bnc_coca",
        "ngsl",
        "phrase",
        "cefr",
    }


def test_human_format_runs():
    result = runner.invoke(app, ["readability", SIMPLE, "--format", "human"])
    assert result.exit_code == 0
    assert "readability" in result.stdout.lower()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()
