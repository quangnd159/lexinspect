"""British <-> American spelling variants, for dictionary lookups only.

Every bundled word list was compiled in one spelling convention, and most of
lexinspect's users write in the other: an IELTS essay says `colour`, `analysed`,
`programme`, `centre`, and NGSL — compiled with American spellings — used to
report all four as off-list, which reads as "rare vocabulary" when it is the
opposite. CMUdict has the same blind spot for syllables.

`spelling_variants()` proposes candidate respellings in *both* directions. It
never decides anything by itself: callers accept a candidate only when the
original form misses their table and the candidate hits it. That keeps the
rules safe to apply broadly — a rule that turns `four` into `for` is harmless,
because `four` is found first and the candidate is never consulted.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def _varcon() -> tuple[dict[str, str], dict[str, str]]:
    """VarCon's curated British<->American pairs (see data/SOURCES.md)."""
    raw = resources.files("lexinspect.data").joinpath("spelling.json").read_text("utf-8")
    data = json.loads(raw)
    return data["gb_to_us"], data["us_to_gb"]


# Pairs VarCon lists above our commonness cut-off, or not at all. British -> American.
_IRREGULAR_GB_US: dict[str, str] = {
    "aeroplane": "airplane",
    "aluminium": "aluminum",
    "cheque": "check",
    "cosy": "cozy",
    "doughnut": "donut",
    "draught": "draft",
    "draughts": "drafts",
    "grey": "gray",
    "jewellery": "jewelry",
    "kerb": "curb",
    "manoeuvre": "maneuver",
    "mould": "mold",
    "moult": "molt",
    "moustache": "mustache",
    "plough": "plow",
    "pyjamas": "pajamas",
    "sceptic": "skeptic",
    "sceptical": "skeptical",
    "scepticism": "skepticism",
    "smoulder": "smolder",
    "storey": "story",
    "sulphur": "sulfur",
    "tyre": "tire",
    "tyres": "tires",
    "practise": "practice",
    "practised": "practiced",
    "practising": "practicing",
    "programme": "program",
    "programmes": "programs",
    "ageing": "aging",
    "judgement": "judgment",
    "acknowledgement": "acknowledgment",
    "arguement": "argument",
    "fulfil": "fulfill",
    "fulfilment": "fulfillment",
    "enrol": "enroll",
    "enrolment": "enrollment",
    "instil": "instill",
    "distil": "distill",
    "skilful": "skillful",
    "wilful": "willful",
    "licence": "license",
    "defence": "defense",
    "offence": "offense",
    "pretence": "pretense",
    "analyse": "analyze",
    "paralyse": "paralyze",
    "catalyse": "catalyze",
    "whisky": "whiskey",
    "gaol": "jail",
    "kilometre": "kilometer",
    "metre": "meter",
    "litre": "liter",
}
_IRREGULAR_US_GB = {us: gb for gb, us in _IRREGULAR_GB_US.items()}

# Regular correspondences, as (british_regex, american_replacement) pairs and
# their inverses. Each is anchored to the end of the word, or to a suffix
# boundary, so they only fire on the morphology they describe.
_SUFFIX_TAIL = r"(s|ed|ing|al|ally|er|ers|ful|fully|less|ism|ist|ists|ite|ites|able|ably|ary|y|ly|ous|ation|ations)?$"

_GB_TO_US: tuple[tuple[re.Pattern[str], str], ...] = (
    # colour/color, behaviour/behavior, favourite/favorite, honourable/honorable
    (re.compile(r"(?<=[a-z])our" + _SUFFIX_TAIL), r"or\1"),
    # organise/organize, realisation/realization, analysing -> handled by yse
    (re.compile(r"(?<=[a-z]{2})is(e|es|ed|ing|er|ers|ation|ations|able)$"), r"iz\1"),
    (re.compile(r"(?<=[a-z])ys(e|es|ed|ing|er|ers|ation)$"), r"yz\1"),
    # centre/center, theatre/theater, fibre/fiber (consonant + re)
    (re.compile(r"(?<=[^aeiou])re(s|d)?$"), r"er\1"),
    # catalogue/catalog, dialogue/dialog, analogue/analog
    (re.compile(r"(?<=[a-z])ogue(s)?$"), r"og\1"),
    # travelled/traveled, cancelling/canceling, modeller/modeler
    (re.compile(r"(?<=[aeiou])ll(ed|ing|er|ers|ery)$"), r"l\1"),
    # anaemia/anemia, encyclopaedia/encyclopedia, oestrogen/estrogen
    (re.compile(r"ae(?=[a-z])"), "e"),
    (re.compile(r"(?<=[a-z])oe(?=[a-z])"), "e"),
    # defence/defense handled as irregular; -ence nouns that switch are few
)

_US_TO_GB: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<=[a-z])or" + _SUFFIX_TAIL), r"our\1"),
    (re.compile(r"(?<=[a-z]{2})iz(e|es|ed|ing|er|ers|ation|ations|able)$"), r"is\1"),
    (re.compile(r"(?<=[a-z])yz(e|es|ed|ing|er|ers|ation)$"), r"ys\1"),
    (re.compile(r"(?<=[^aeiou])er(s|ed)?$"), r"re\1"),
    (re.compile(r"(?<=[a-z])og(s)?$"), r"ogue\1"),
    (re.compile(r"(?<=[aeiou])l(ed|ing|er|ers)$"), r"ll\1"),
)


@lru_cache(maxsize=65536)
def spelling_variants(word: str) -> tuple[str, ...]:
    """Candidate respellings of a lowercase `word`, most specific first.

    The word itself is never included. Candidates are not validated — the
    caller checks them against its own table.
    """
    w = word.lower()
    out: list[str] = []
    for table in (*_varcon(), _IRREGULAR_GB_US, _IRREGULAR_US_GB):
        if w in table and table[w] not in out:
            out.append(table[w])
    for rules in (_GB_TO_US, _US_TO_GB):
        for pattern, repl in rules:
            candidate = pattern.sub(repl, w, count=1)
            if candidate != w and candidate not in out:
                out.append(candidate)
    return tuple(out)
