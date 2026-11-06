"""Interface translations: every catalogue covers every message, intact.

Messages come from scripts/i18n/extract.py; see static/i18n.js for the format.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "lexinspect" / "static"
LOCALES = STATIC / "locales"

_spec = importlib.util.spec_from_file_location("extract", ROOT / "scripts" / "i18n" / "extract.py")
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)

# The languages offered in i18n.js, except English (the source).
CODES = re.findall(r"\['([\w-]+)', '", (STATIC / "i18n.js").read_text(encoding="utf-8"))
TARGETS = [c for c in CODES if c != "en"]

# CLDR plural categories each language uses for integers (Intl.PluralRules).
PLURALS = {
    "ar": {"zero", "one", "two", "few", "many", "other"},
    "de": {"one", "other"},
    "es": {"one", "many", "other"},
    "fr": {"one", "many", "other"},
    "id": {"other"},
    "ja": {"other"},
    "ko": {"other"},
    "pt-BR": {"one", "many", "other"},
    "tr": {"one", "other"},
    "vi": {"other"},
    "zh-CN": {"other"},
}
_PH = re.compile(r"\{(\w+)\}")
_TAG = re.compile(r"</?(\w+)>")


def _messages() -> dict[str, dict]:
    return {m["key"]: m for m in json.loads((LOCALES / "messages.json").read_text("utf-8"))}


def test_messages_json_is_current():
    assert (LOCALES / "messages.json").read_text("utf-8") == extract.render(extract.collect()), (
        "run: uv run python scripts/i18n/extract.py"
    )


def test_locale_list_matches_plural_table():
    assert set(TARGETS) == set(PLURALS)


def test_no_script_shadows_the_translation_functions():
    """A local `t`, `tn` or `tr` would hide the global and break t('…') in that scope."""
    bad = re.compile(
        r"(?:\b(?:const|let|var)\s+(?:t|tn|tr|N_)\b)"
        r"|(?:\(\s*(?:t|tn|tr)\s*\)\s*=>)|(?:[(,]\s*(?:t|tn|tr)\s*[,)]\s*(?:=>|\{))"
    )
    hits = []
    for path in STATIC.glob("*.js"):
        if path.name == "i18n.js":
            continue
        for i, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if bad.search(line):
                hits.append(f"{path.name}:{i}: {line.strip()[:80]}")
    assert not hits, "\n".join(hits)


def test_messages_are_literals():
    """t()/tr()/tn() with a template literal or double quotes escape extraction."""
    call = r"(?<![\w$])(?:(?<=\.\.\.)|(?<!\.))"
    bad = re.compile(call + r"(?:t|tr|N_)\(\s*[`\"]|" + call + r"tn\([^;]*?,\s*[`\"]")
    hits = [
        f"{p.name}:{i}"
        for p in STATIC.glob("*.js")
        for i, line in enumerate(p.read_text("utf-8").splitlines(), 1)
        if bad.search(line)
    ]
    assert not hits, hits


@pytest.mark.parametrize("code", TARGETS)
def test_catalogue_complete_and_intact(code):
    path = LOCALES / f"{code}.json"
    assert path.exists(), f"missing {path.name}"
    cat = json.loads(path.read_text("utf-8"))
    msgs = _messages()
    missing = sorted(set(msgs) - set(cat))
    extra = sorted(set(cat) - set(msgs))
    assert not missing, f"{code}: {len(missing)} untranslated, e.g. {missing[:5]}"
    assert not extra, f"{code}: {len(extra)} stale, e.g. {extra[:5]}"
    problems = []
    for key, m in msgs.items():
        v = cat[key]
        sources = m.get("plural", [key])
        want_ph = set().union(*(set(_PH.findall(s)) for s in sources))
        want_tags = sorted(_TAG.findall(sources[-1]))
        if "plural" in m:
            if not isinstance(v, dict) or "other" not in v:
                problems.append(f"{key!r}: plural needs an object with 'other'")
                continue
            if not set(v) <= PLURALS[code]:
                problems.append(
                    f"{key!r}: categories {sorted(set(v) - PLURALS[code])} not used in {code}"
                )
            forms = list(v.values())
        else:
            if not isinstance(v, str) or not v.strip():
                problems.append(f"{key!r}: empty")
                continue
            forms = [v]
        for f in forms:
            got = set(_PH.findall(f))
            # A plural form may leave out {n} ("one word"), never add placeholders.
            if not got <= want_ph or (want_ph - {"n"}) - got:
                problems.append(f"{key!r}: placeholders {sorted(got)} != {sorted(want_ph)}")
            if sorted(_TAG.findall(f)) != want_tags:
                problems.append(f"{key!r}: tags {sorted(_TAG.findall(f))} != {want_tags}")
    assert not problems, f"{code}:\n" + "\n".join(problems[:30])
