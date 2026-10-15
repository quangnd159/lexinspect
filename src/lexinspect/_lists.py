"""Loaders for the bundled word lists, shaped for token lookup.

Each loader parses its JSON once per process and returns a flat
`form -> entry` mapping, so a profiler does one dict probe per lookup key.
`warm()` loads them all; the API calls it at startup so the first request
doesn't pay for it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any


def _json(name: str) -> dict[str, Any]:
    return json.loads(resources.files("lexinspect.data").joinpath(name).read_text("utf-8"))


# --- BNC/COCA -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Family:
    headword: str
    band: int


@lru_cache(maxsize=1)
def bnc_raw() -> dict[str, Any]:
    return _json("bnc_coca.json")


@lru_cache(maxsize=1)
def bnc_forms() -> dict[str, Family]:
    """Every family member -> its family. A form listed in several families
    (homographs) keeps the most frequent band, as Range does."""
    out: dict[str, Family] = {}
    for band_str, families in sorted(bnc_raw()["bands"].items(), key=lambda kv: int(kv[0])):
        band = int(band_str)
        for head, members in families.items():
            fam = Family(head, band)
            for form in (head, *members):
                out.setdefault(form, fam)
    return out


@lru_cache(maxsize=1)
def bnc_supplementary() -> dict[str, str]:
    """Form -> supplementary list name (proper_names, marginal_words, ...)."""
    out: dict[str, str] = {}
    for name, forms in bnc_raw()["supplementary"].items():
        for f in forms:
            out.setdefault(f, name)
    return out


# --- NGSL / NAWL ------------------------------------------------------------------


@lru_cache(maxsize=1)
def ngsl_forms() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in _json("ngsl.json")["lemmas"]:
        for form in item["forms"]:
            out.setdefault(form, item)
    return out


@lru_cache(maxsize=1)
def nawl_forms() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in _json("nawl.json")["lemmas"]:
        for form in (item["lemma"], *item["forms"]):
            out.setdefault(form, item)
    return out


# --- AWL --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def awl_forms() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for fam in _json("awl.json")["families"]:
        for form in (fam["headword"], *fam["forms"]):
            out.setdefault(form, fam)
    return out


# --- CEFR -------------------------------------------------------------------------


@lru_cache(maxsize=1)
def cefr_raw() -> dict[str, Any]:
    return _json("cefr.json")


@lru_cache(maxsize=1)
def cefr_entries() -> dict[str, dict[str, Any]]:
    return {item["lemma"]: item for item in cefr_raw()["lemmas"]}


# spaCy Universal POS -> the POS labels CEFR-J / Octanove use.
_UPOS_TO_CEFR: dict[str, tuple[str, ...]] = {
    "NOUN": ("noun",),
    "PROPN": ("noun",),
    "VERB": ("verb",),
    "AUX": ("be-verb", "do-verb", "have-verb", "modal auxiliary", "verb"),
    "ADJ": ("adjective",),
    "ADV": ("adverb",),
    "PRON": ("pronoun",),
    "ADP": ("preposition",),
    "DET": ("determiner",),
    "CCONJ": ("conjunction",),
    "SCONJ": ("conjunction", "preposition"),
    "NUM": ("number",),
    "INTJ": ("interjection",),
    "PART": ("infinitive-to", "adverb"),
}


def cefr_level(entry: dict[str, Any], upos: str) -> tuple[str, bool]:
    """Level of `entry` for a token tagged `upos`: (level, matched_pos).

    Uses the level listed for that part of speech when there is one; otherwise
    the entry's lowest level, flagged as a POS miss.
    """
    by_pos = entry.get("by_pos") or {}
    for pos in _UPOS_TO_CEFR.get(upos, ()):
        if pos in by_pos:
            return by_pos[pos], True
    return entry["level"], False


def warm() -> None:
    bnc_forms()
    bnc_supplementary()
    ngsl_forms()
    nawl_forms()
    awl_forms()
    cefr_entries()
