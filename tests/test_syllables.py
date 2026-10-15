"""Accuracy of the syllable heuristic (the last tier of `_syllables.count`).

The heuristic only answers for words CMUdict doesn't know, so its accuracy is
measured against CMUdict itself on words it *does* know: a seeded random sample,
so the number is reproducible and can't be tuned to a hand-picked list.
"""

from __future__ import annotations

import random

import pytest

from lexinspect import _syllables

SAMPLE_SIZE = 3000
MIN_ACCURACY = 0.88


@pytest.fixture(scope="module")
def cmu() -> dict[str, int]:
    return _syllables.cmudict()


def test_cmudict_loads(cmu):
    assert len(cmu) > 100_000
    assert cmu["syllable"] == 3
    assert cmu["the"] == 1


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_heuristic_accuracy_against_cmudict(cmu, seed):
    words = sorted(w for w in cmu if w.isalpha() and len(w) > 2)
    sample = random.Random(seed).sample(words, SAMPLE_SIZE)
    correct = sum(_syllables._heuristic(w) == cmu[w] for w in sample)
    accuracy = correct / SAMPLE_SIZE
    assert accuracy >= MIN_ACCURACY, f"heuristic accuracy {accuracy:.3f} < {MIN_ACCURACY}"


def test_heuristic_within_one_syllable_almost_always(cmu):
    words = sorted(w for w in cmu if w.isalpha() and len(w) > 2)
    sample = random.Random(99).sample(words, SAMPLE_SIZE)
    near = sum(abs(_syllables._heuristic(w) - cmu[w]) <= 1 for w in sample)
    assert near / SAMPLE_SIZE >= 0.98


@pytest.mark.parametrize(
    "word,expected",
    [
        ("create", 2),
        ("riot", 2),
        ("diet", 2),
        ("table", 2),
        ("jumped", 1),
        ("wanted", 2),
        ("makes", 1),
        ("buses", 2),
        ("lovely", 2),
        ("realism", 4),
    ],
)
def test_heuristic_rules(word, expected):
    assert _syllables._heuristic(word) == expected


def test_count_never_zero_for_words_and_zero_without_letters():
    assert _syllables.count("zzxq") >= 1
    assert _syllables.count("—") == 0
    assert _syllables.count("") == 0


def test_count_is_case_and_apostrophe_insensitive():
    assert _syllables.count("Colour") == _syllables.count("colour") == 2
    assert _syllables.count("don’t") == _syllables.count("don't") == 1
