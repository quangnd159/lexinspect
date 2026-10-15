"""Text statistics — counts and ratios that aren't readability scores.

Surfaces the breakouts Text Inspector shows under "Statistics": sentence count,
token count excluding numbers, unique types, syllables, polysyllabic words,
and the ratios built from them, plus the list of numeric tokens excluded.

Every count comes from the shared `Analysis`, so `sentences` and `syllables`
here are the same numbers the readability tab reports. Numeric tokens are
detected strictly — digits with optional `.`/`,`, a currency sign or `%`, an
ordinal or decade suffix (`2025`, `1.5`, `1,000`, `3rd`, `1990s`). Word
numerals (`twenty`) are words, matching Text Inspector's "Excluded Digits".
"""

from __future__ import annotations

from typing import Any

from lexinspect._text import Analysis, ensure
from lexinspect.readability import word_syllables


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    excluded = [w.text for w in a.words if w.is_numeric]
    words = a.non_numeric_words
    n_words = len(words)
    n_types = len({w.lower for w in words})
    n_sent = a.sentence_count
    syll = [word_syllables(w) for w in words]
    n_syll = sum(syll)
    poly = sum(1 for s in syll if s >= 3)

    return {
        "counts": {
            "characters_with_spaces": len(a.text),
            "characters_without_spaces": len("".join(a.text.split())),
            "tokens_excluding_numbers": n_words,
            "unique_types_excluding_numbers": n_types,
            "sentences": n_sent,
            "syllables": n_syll,
            "polysyllable_words": poly,
            "excluded_numeric_tokens": len(excluded),
        },
        "averages": {
            "tokens_per_sentence": _ratio(n_words, n_sent),
            "type_token_ratio": _ratio(n_types, n_words),
            "syllables_per_word": _ratio(n_syll, n_words),
            "syllables_per_sentence": _ratio(n_syll, n_sent),
            "syllables_per_100_words": _ratio(n_syll * 100, n_words),
            "polysyllable_pct": _ratio(poly * 100, n_words),
        },
        "excluded_digits": excluded,
    }


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0
