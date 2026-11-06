"""Collect every interface message from the web UI into locales/messages.json.

    uv run python scripts/i18n/extract.py          # rewrite messages.json
    uv run python scripts/i18n/extract.py --check  # exit 1 if it is stale

Messages are found in:
- JS: t('…'), tr('…'), N_('…') and tn(n, '…', '…'), first arguments as
  single-quoted literals;
- HTML: data-i18n="…" text, the attributes named in data-i18n-attr, and
  <meta name="i18n-title" content="…">.

messages.json lists each message once, sorted, with the files it comes from
and, for plurals, both English forms. tests/test_i18n.py checks every locale
against it.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "lexinspect" / "static"
LOCALES = STATIC / "locales"
MESSAGES = LOCALES / "messages.json"

_STR = r"'((?:[^'\\\n]|\\.)*)'"
# A call is t(…) on its own or after a spread (...tr(…)), never a method
# such as x.t(…) or a longer name such as format(…).
_CALL = r"(?<![\w$])(?:(?<=\.\.\.)|(?<!\.))"
_SIMPLE = re.compile(_CALL + r"(t|tr|N_)\(\s*" + _STR)
# tn(<expr>, 'one', 'other'): <expr> may hold one level of parentheses.
_PLURAL = re.compile(_CALL + r"tn\((?:[^'()]|\([^()]*\))*?,\s*" + _STR + r"\s*,\s*" + _STR)
PLURAL_SEP = " | "


def unescape(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u" and s[i + 2 : i + 3] != "{":
                out.append(chr(int(s[i + 2 : i + 6], 16)))
                i += 6
                continue
            out.append({"n": "\n", "t": "\t"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if "data-i18n" in a and a["data-i18n"]:
            self.found.append(a["data-i18n"])
        for name in filter(None, a.get("data-i18n-attr", "").split("|")):
            if a.get(name):
                self.found.append(a[name])
        if tag == "meta" and a.get("name") == "i18n-title" and a.get("content"):
            self.found.append(a["content"])


def collect() -> dict[str, dict]:
    msgs: dict[str, dict] = {}

    def add(key: str, file: str, forms: list[str] | None = None) -> None:
        m = msgs.setdefault(key, {"files": set()})
        m["files"].add(file)
        if forms:
            m["plural"] = forms

    for path in sorted(STATIC.glob("*.js")):
        src = path.read_text(encoding="utf-8")
        for m in _PLURAL.finditer(src):
            one, other = unescape(m.group(1)), unescape(m.group(2))
            add(f"{one}{PLURAL_SEP}{other}", path.name, [one, other])
        # Plurals first, then blank them so their strings aren't read as t().
        stripped = _PLURAL.sub(lambda m: " " * len(m.group(0)), src)
        for m in _SIMPLE.finditer(stripped):
            add(unescape(m.group(2)), path.name)
    for path in sorted(STATIC.glob("*.html")):
        p = _Html()
        p.feed(path.read_text(encoding="utf-8"))
        for s in p.found:
            add(s, path.name)
    return msgs


def render(msgs: dict[str, dict]) -> str:
    out = []
    for key in sorted(msgs):
        m = msgs[key]
        row = {"key": key, "files": sorted(m["files"])}
        if "plural" in m:
            row["plural"] = m["plural"]
        out.append(row)
    return json.dumps(out, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    text = render(collect())
    if "--check" in sys.argv:
        if not MESSAGES.exists() or MESSAGES.read_text(encoding="utf-8") != text:
            print("locales/messages.json is stale: run scripts/i18n/extract.py", file=sys.stderr)
            return 1
        return 0
    LOCALES.mkdir(exist_ok=True)
    MESSAGES.write_text(text, encoding="utf-8")
    print(f"{len(json.loads(text))} messages -> {MESSAGES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
