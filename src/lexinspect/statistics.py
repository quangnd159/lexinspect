"""Text statistics — counts and ratios that aren't readability scores.

Surfaces the breakouts Text Inspector shows under "Statistics": sentence
count, token count excluding numeric tokens, unique types, syllable count,
count and percentage of polysyllabic words (>2 syllables), average syllables
per sentence, syllables per 100 words, type/token ratio, plus the list of
numeric tokens that were excluded.

`readability` reports a similar `counts` block, but mixed with formula scores.
This module exposes the same fields as discrete top-level ratios so an agent
can read them directly. Tokenization uses spaCy (so `excluded_digits` reflects
real numeric tokens), syllable counts come from textstat for parity with the
readability module.

Numeric tokens are detected strictly: a token is numeric only if it consists
of digits with optional decimal points or commas (e.g. ``2025``, ``1.5``,
``1,000``). Word numerals (``one``, ``twenty-fifth``) are kept as words —
matching Text Inspector's "Excluded Digits" list, which contains only digits.
"""

from __future__ import annotations

from typing import Any

import textstat

from lexinspect._nlp import get_doc


def analyze(text: str, *, doc=None) -> dict[str, Any]:
    doc = get_doc(text, doc)

    excluded_digits: list[str] = []
    word_token_count = 0
    types: set[str] = set()

    for tok in doc:
        if tok.is_space or tok.is_punct:
            continue
        if _is_numeric_token(tok.text):
            excluded_digits.append(tok.text)
            continue
        word_token_count += 1
        types.add(tok.text.lower())

    type_count = len(types)
    sentence_count = sum(1 for _ in doc.sents)

    ts = textstat.textstat
    ts.set_lang("en_US")
    syllable_count = ts.syllable_count(text)
    polysyllable_count = ts.polysyllabcount(text)

    return {
        "counts": {
            "characters_with_spaces": len(text),
            "characters_without_spaces": ts.char_count(text, ignore_spaces=True),
            "tokens_excluding_numbers": word_token_count,
            "unique_types_excluding_numbers": type_count,
            "sentences": sentence_count,
            "syllables": syllable_count,
            "polysyllable_words": polysyllable_count,
            "excluded_numeric_tokens": len(excluded_digits),
        },
        "averages": {
            "tokens_per_sentence": _ratio(word_token_count, sentence_count),
            "type_token_ratio": _ratio(type_count, word_token_count),
            "syllables_per_word": _ratio(syllable_count, word_token_count),
            "syllables_per_sentence": _ratio(syllable_count, sentence_count),
            "syllables_per_100_words": _ratio(syllable_count * 100, word_token_count),
            "polysyllable_pct": _ratio(polysyllable_count * 100, word_token_count),
        },
        "excluded_digits": excluded_digits,
    }


def _is_numeric_token(text: str) -> bool:
    """True iff `text` is a purely numeric token (digits, optional , and .)."""
    if not text:
        return False
    cleaned = text.replace(",", "").replace(".", "")
    return cleaned.isdigit()


def _ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 3)
