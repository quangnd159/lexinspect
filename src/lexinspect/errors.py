"""Spelling-error detection (British or American English).

Wraps `spylls`, a pure-Python port of Hunspell, to flag tokens that aren't in
the chosen dictionary. Reports total errors, errors per sentence, errors per
100 words, and the deduplicated error list — the same shape Text Inspector's
Errors tab surfaces.

The `errors` extra ships only the `spylls` runtime; the actual `.aff` / `.dic`
files are downloaded on first use into the user's cache directory
(``~/.cache/lexinspect/hunspell/``). Each variant downloads independently the
first time it's requested. Source: LibreOffice's English dictionary mirror,
covered by Kevin Atkinson's LGPL wordlist licence and Geoff Kuenning's BSD
affix licence.

Tokenisation uses spaCy. Pure-numeric tokens, punctuation, URLs, and emails
are skipped; everything else is looked up as-is. spaCy splits possessive
``'s`` from its host noun, so a token like ``children's`` is checked as
``children`` plus ``'s`` (the latter skipped) — Hunspell's full possessive
handling is bypassed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from lexinspect._nlp import get_doc

# Pinned to the LibreOffice dictionaries master branch. The English files have
# been stable since 2018; if upstream ever moves, switch to a tagged commit.
_DICT_URLS: dict[str, dict[str, str]] = {
    "gb": {
        "aff": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB.aff",
        "dic": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB.dic",
    },
    "us": {
        "aff": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US.aff",
        "dic": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US.dic",
    },
}

VALID_VARIANTS: tuple[str, ...] = ("gb", "us")

CAVEAT = (
    "Hunspell-based detection. False positives on proper nouns, brand names, "
    "neologisms, and rare technical vocabulary are routine — Hunspell can only "
    "flag tokens its dictionary doesn't recognise. spaCy splits possessive 's "
    "from its host word, so possessive forms are not checked as wholes. "
    "Switch variants with --variant gb|us. Dictionaries: LibreOffice English "
    "(LGPL wordlist + BSD affix file)."
)

DICTIONARY_LICENCE = (
    "LibreOffice English (en_GB / en_US): wordlist by Kevin Atkinson (LGPL); "
    "affix file by Geoff Kuenning (BSD). Mirror: github.com/LibreOffice/dictionaries."
)


class ErrorsExtraNotInstalled(RuntimeError):
    """Raised when the optional `errors` extra (spylls) is not installed."""


class DictionaryFetchError(RuntimeError):
    """Raised when a Hunspell dictionary cannot be downloaded or loaded."""


def _cache_dir() -> Path:
    """Per-user cache for downloaded Hunspell files. Created on demand.

    Serverless hosts mount the deployment read-only and give you `/tmp` as the
    only writable path, so `$LEXINSPECT_CACHE_DIR` overrides the home-directory
    default. The cache survives for the life of a warm instance and re-downloads
    on a cold one — ~1.5 MB, so that's an acceptable trade rather than a bug.
    """
    override = os.environ.get("LEXINSPECT_CACHE_DIR")
    base = Path(override) if override else Path.home() / ".cache" / "lexinspect"
    try:
        hunspell = base / "hunspell"
        hunspell.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only home (serverless). Fall back to the one writable path.
        hunspell = Path(tempfile.gettempdir()) / "lexinspect" / "hunspell"
        hunspell.mkdir(parents=True, exist_ok=True)
    return hunspell


def _ensure_dict_files(variant: str) -> Path:
    """Make sure both .aff and .dic exist on disk; download if missing.

    Returns the base path (without extension) suitable for spylls' loader.
    Atomic writes — partial downloads land in `.tmp` files that get renamed
    on success, so a half-finished download never gets loaded by spylls.
    """
    if variant not in _DICT_URLS:
        raise ValueError(f"Unknown variant '{variant}'. Choose from {VALID_VARIANTS}.")

    cache = _cache_dir()
    base = cache / f"en_{variant.upper()}"
    aff_path = base.with_suffix(".aff")
    dic_path = base.with_suffix(".dic")

    if aff_path.exists() and dic_path.exists():
        return base

    print(
        f"[lexinspect] Downloading en_{variant.upper()} Hunspell dictionary "
        f"(first run, ~1.5 MB)…",
        file=sys.stderr,
    )
    for ext, url in _DICT_URLS[variant].items():
        target = base.with_suffix(f".{ext}")
        if target.exists():
            continue
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            urllib.request.urlretrieve(url, tmp)
        except (urllib.error.URLError, OSError) as e:
            tmp.unlink(missing_ok=True)
            raise DictionaryFetchError(
                f"Could not download {url} into {target}.\n"
                f"Cause: {e}\n"
                f"Workaround: download the file manually and place it at the path above."
            ) from e
        tmp.replace(target)

    return base


@lru_cache(maxsize=2)
def _dictionary(variant: str):
    """Load (and cache) the spylls Dictionary for the given variant."""
    try:
        from spylls.hunspell import Dictionary  # type: ignore
    except ImportError as e:
        # spylls is a base dependency, so this should be unreachable in a sane
        # install. Kept as a clear failure for partial/broken environments.
        raise ErrorsExtraNotInstalled(
            "spylls is missing, so the errors module cannot run.\n"
            "Reinstall lexinspect's dependencies:\n"
            "    uv sync"
        ) from e

    base = _ensure_dict_files(variant)
    try:
        return Dictionary.from_files(str(base))
    except Exception as e:  # spylls raises a variety of internal errors
        raise DictionaryFetchError(
            f"Failed to load Hunspell dictionary at {base}.{{aff,dic}}.\n"
            f"Cause: {e}\n"
            f"Try removing the cache directory and re-running: rm -rf {_cache_dir()}"
        ) from e


def analyze(text: str, *, variant: str = "gb", doc=None) -> dict[str, Any]:
    """Spell-check `text` against the chosen English variant.

    Args:
        text: input text.
        variant: ``"gb"`` (British, default — matches Text Inspector's default)
            or ``"us"`` (American).
    """
    if variant not in VALID_VARIANTS:
        raise ValueError(f"variant must be one of {VALID_VARIANTS}, got {variant!r}")

    dictionary = _dictionary(variant)
    doc = get_doc(text, doc)

    sentence_count = sum(1 for _ in doc.sents)
    tokens_checked = 0
    error_counter: Counter[str] = Counter()

    for tok in doc:
        if not _is_checkable(tok):
            continue
        tokens_checked += 1
        word = tok.text
        # Hunspell handles case sensitivity itself; pass the surface form
        # exactly as spaCy tokenised it.
        if not dictionary.lookup(word):
            error_counter[word] += 1

    errors_total = sum(error_counter.values())
    errors = [
        {"surface": w, "count": n}
        for w, n in sorted(error_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    return {
        "variant": variant,
        "counts": {
            "tokens_checked": tokens_checked,
            "sentences": sentence_count,
            "errors_total": errors_total,
            "unique_errors": len(error_counter),
        },
        "rates": {
            "errors_per_sentence": _ratio(errors_total, sentence_count),
            "errors_per_100_words": _ratio(errors_total * 100, tokens_checked),
        },
        "errors": errors,
        "dictionary": {
            "variant": variant,
            "source": f"LibreOffice en_{variant.upper()}.aff/.dic",
            "licence": DICTIONARY_LICENCE,
        },
        "caveat": CAVEAT,
    }


def _is_checkable(tok) -> bool:
    """A token is spell-checked iff it has alphabetic characters and is not a
    URL, email, or pure-numeric token."""
    if tok.is_space or tok.is_punct:
        return False
    if tok.like_url or tok.like_email:
        return False
    return any(c.isalpha() for c in tok.text)


def _ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 3)
