"""Readability and basic text statistics. Wraps textstat."""

from __future__ import annotations

from typing import Any

import textstat


def analyze(text: str) -> dict[str, Any]:
    ts = textstat.textstat
    ts.set_lang("en_US")
    return {
        "counts": {
            "characters": ts.char_count(text, ignore_spaces=True),
            "characters_with_spaces": len(text),
            "words": ts.lexicon_count(text, removepunct=True),
            "syllables": ts.syllable_count(text),
            "sentences": ts.sentence_count(text),
            "polysyllable_words": ts.polysyllabcount(text),
            "monosyllable_words": ts.monosyllabcount(text),
            "long_words": ts.long_word_count(text),
            "reading_time_seconds": round(ts.reading_time(text, ms_per_char=14.69), 2),
        },
        "averages": {
            "words_per_sentence": _safe_div(
                ts.lexicon_count(text, removepunct=True), ts.sentence_count(text)
            ),
            "syllables_per_word": _safe_div(
                ts.syllable_count(text), ts.lexicon_count(text, removepunct=True)
            ),
            "characters_per_word": _safe_div(
                ts.char_count(text, ignore_spaces=True),
                ts.lexicon_count(text, removepunct=True),
            ),
        },
        "scores": {
            "flesch_reading_ease": ts.flesch_reading_ease(text),
            "flesch_kincaid_grade": ts.flesch_kincaid_grade(text),
            "gunning_fog": ts.gunning_fog(text),
            "smog_index": ts.smog_index(text),
            "automated_readability_index": ts.automated_readability_index(text),
            "coleman_liau_index": ts.coleman_liau_index(text),
            "dale_chall_readability_score": ts.dale_chall_readability_score(text),
            "linsear_write_formula": ts.linsear_write_formula(text),
            "text_standard": ts.text_standard(text, float_output=True),
        },
    }


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 3) if b else 0.0
