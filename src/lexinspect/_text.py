"""One canonical reading of a text, shared by every module.

Before this existed, each module tokenised for itself: readability used
textstat's regex split, diversity used lexicalrichness's, the profilers used
raw spaCy tokens. The same essay reported three different word counts and two
different sentence counts on adjacent tabs, and the vocabulary profilers
counted the possessive `'s` and the `n't` of `don't` as words in their own
right. A user comparing tabs had no way to tell which number was right.

`Analysis` fixes the units once:

- **Word** — what a person counts as a word, and what Word / Google Docs count:
  a contraction (`don't`, `she'll`) is one word, a hyphenated compound
  (`well-known`, `twenty-five`) is one word, `cannot` is one word. Numbers are
  words here too (`2019` is a word in a word count); modules that exclude them
  say so. Punctuation and symbols are never words.
- **Lexical token** — the unit vocabulary profiling looks up in a word list:
  each word's lexical parts, without clitics (`n't`, `'s`, `'ll`) or the
  possessive, without numbers. A hyphenated compound contributes its parts
  (`well`, `known`) — the convention of Range and AntWordProfiler — unless the
  whole compound or its joined form is itself a list entry (`e-mail`, `email`),
  which the lookup keys handle.
- **Sentence** — spaCy's dependency-based segmentation, which knows `Dr.`,
  `U.S.`, `e.g.`, `3.5` aren't sentence ends, plus a hard break at every blank
  line so a title or a bullet without a full stop doesn't merge into the next
  sentence. Sentences with no words in them (a stray `)`) are not counted.

Build it once per request with `analyse(text)` and pass it to every module.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property

from lexinspect._nlp import parse

# --- input normalisation -----------------------------------------------------

# Characters that arrive with text pasted from Word, PDFs and web pages and
# silently break tokenisation: a soft hyphen splits `inter­national` into
# two "words", a zero-width space glues two words into one.
_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"), None)
_SPACES = dict.fromkeys(map(ord, "     　"), " ")
_LINE_SEPS = {ord(" "): "\n", ord(" "): "\n\n", ord("\r"): None}


def normalise(text: str) -> str:
    """Canonical form of user input. Analysis always runs on this.

    NFC so that `é` typed two ways is one character; invisible formatting
    characters removed; exotic spaces mapped to a plain space. Apostrophes and
    quotes are left alone — spaCy handles curly ones, and character counts
    should reflect what the user wrote.
    """
    text = unicodedata.normalize("NFC", text)
    return text.translate(_INVISIBLE).translate(_SPACES).translate(_LINE_SEPS)


# --- token classification ----------------------------------------------------

_APOSTROPHES = "'’ʼ`"
# Clitics spaCy splits off a host word. They attach to the preceding word and
# never count as words or lexical tokens of their own.
_CLITICS = frozenset({"n't", "'s", "'re", "'ve", "'ll", "'d", "'m", "'", "s'"})
# Hosts whose surface form is an artefact of the split: `ca|n't`, `wo|n't`,
# `sha|n't`. Their lemma is right; their surface isn't a word.
_HOST_SURFACE_FIX = {"ca": "can", "wo": "will", "sha": "shall", "ai": "ai"}
_HYPHENS = frozenset({"-", "‐", "‑"})
_NUMERIC = re.compile(
    # Also times, fractions and hyphenated ranges (`11:00`, `1/4`, `3-4`): Study 3
    # found them treated as words, with no syllables, in 51 of 300 texts.
    r"^(?:[+\-−±]?[$£€¥]?(?:\d[\d.,]*(?:[:/\-]\d[\d.,]*)*|\.\d+)%?|\d+(?:st|nd|rd|th|s|'s)|'\d\ds)$",
    re.IGNORECASE,
)
# Bound prefixes that, hyphenated, aren't words of their own: `e-mail`,
# `co-operate`, `re-enter`, `non-native`. Profiled with their host.
_BOUND_PREFIXES = frozenset(
    {
        "e",
        "x",
        "co",
        "re",
        "pre",
        "non",
        "anti",
        "semi",
        "multi",
        "sub",
        "inter",
        "mid",
        "post",
        "pro",
        "ex",
        "un",
        "de",
        "bi",
        "tri",
        "mis",
        "neo",
        "micro",
        "macro",
        "mega",
        "mini",
        "over",
        "under",
        "counter",
        "cross",
        "extra",
        "ultra",
        "hyper",
        "pseudo",
    }
)


def _norm_apos(s: str) -> str:
    for a in _APOSTROPHES[1:]:
        s = s.replace(a, "'")
    return s


def is_clitic(tok) -> bool:
    return _norm_apos(tok.lower_) in _CLITICS


def is_numeric(text: str) -> bool:
    return bool(_NUMERIC.match(_norm_apos(text)))


def _is_code(text: str) -> bool:
    """Letters mixed with digits (`R²`, `CO2`, `mp3`, `A4`): symbols and codes,
    not vocabulary. No word list carries them, so profiling them would only add
    off-list noise. They still count as words for readability and statistics."""
    return any(c.isdigit() for c in text) and any(c.isalpha() for c in text)


def _has_alnum(s: str) -> bool:
    return any(c.isalnum() for c in s)


@dataclass(frozen=True, slots=True)
class LexToken:
    """One lookup unit for vocabulary profiling.

    `keys` are the forms to try against a word list, in order: joined compound
    forms first (when this token stands for a whole compound), then the
    surface form, then the lemma. `analysis.lookup()` adds spelling variants.
    """

    surface: str  # lowercased, apostrophes normalised, artefacts fixed (`ca` -> `can`)
    lemma: str  # lowercased spaCy lemma
    pos: str  # Universal POS
    tag: str  # Penn Treebank tag
    i: int  # spaCy token index of the (last) part
    word_index: int
    is_proper: bool  # tagged NNP/NNPS
    keys: tuple[str, ...]


@dataclass(slots=True)
class Word:
    """One orthographic word: a run of spaCy tokens with nothing between them."""

    tokens: list = field(default_factory=list)
    text: str = ""

    @property
    def start(self) -> int:
        return self.tokens[0].i

    @property
    def is_numeric(self) -> bool:
        return is_numeric(self.text)

    @property
    def is_hyphenated(self) -> bool:
        return any(t.text in _HYPHENS for t in self.tokens)

    @property
    def lower(self) -> str:
        return _norm_apos(self.text.lower())

    @property
    def is_proper(self) -> bool:
        heads = [t for t in self.tokens if not is_clitic(t) and t.text not in _HYPHENS]
        return bool(heads) and all(t.tag_ in ("NNP", "NNPS") for t in heads)


@dataclass
class Analysis:
    text: str
    doc: object
    words: list[Word]
    sentences: list[list[Word]]

    # -- derived views -------------------------------------------------------

    @cached_property
    def word_count(self) -> int:
        return len(self.words)

    @cached_property
    def sentence_count(self) -> int:
        return len(self.sentences)

    @cached_property
    def non_numeric_words(self) -> list[Word]:
        return [w for w in self.words if not w.is_numeric]

    @cached_property
    def lexical(self) -> list[LexToken]:
        """Lexical tokens for vocabulary profiling, in text order."""
        out: list[LexToken] = []
        for wi, word in enumerate(self.words):
            if word.is_numeric or _is_code(word.text):
                continue
            out.extend(_lexical_parts(word, wi))
        return out

    @cached_property
    def word_index_of_token(self) -> dict[int, int]:
        return {t.i: wi for wi, w in enumerate(self.words) for t in w.tokens}

    def lookup(self, table, lex: LexToken):
        """First (key, value) of `lex` found in `table`, or (None, None).

        Tries the token's own keys, then their British/American respellings.
        A respelling is only consulted after every exact key has missed, so it
        can't override a real match.
        """
        return lookup(table, lex.keys)


def lookup(table, keys):
    for k in keys:
        v = table.get(k)
        if v is not None:
            return k, v
    from lexinspect._spelling import spelling_variants

    for k in keys:
        for variant in spelling_variants(k):
            v = table.get(variant)
            if v is not None:
                return variant, v
    return None, None


def _lexical_parts(word: Word, wi: int) -> list[LexToken]:
    toks = [t for t in word.tokens if not is_clitic(t)]
    parts = [t for t in toks if t.text not in _HYPHENS and _has_alnum(t.text)]
    if not parts:
        return []
    if len(parts) == 1:
        return [_lex(parts[0], wi, ())]

    # Hyphenated or otherwise joined (`cannot`, `gonna`) compound.
    joined_h = _norm_apos("".join(t.text for t in toks).lower())
    joined = joined_h.replace("-", "").replace("‐", "").replace("‑", "")
    whole = (joined_h, joined) if word.is_hyphenated else (joined,)

    out: list[LexToken] = []
    pending_prefix = ""
    for idx, t in enumerate(parts):
        low = t.lower_
        if word.is_hyphenated and low in _BOUND_PREFIXES and idx < len(parts) - 1:
            pending_prefix += low
            continue
        extra: tuple[str, ...] = ()
        if pending_prefix:
            extra = (pending_prefix + low, pending_prefix + t.lemma_.lower())
            pending_prefix = ""
        # The compound as a whole is tried first on the first part only, so a
        # list that carries `e-mail` matches it once rather than once per part.
        if idx == 0 or (extra and len(out) == 0):
            extra = whole + extra
        out.append(_lex(t, wi, extra))
    # A compound that is entirely a listed whole (`e-mail`) should be one token,
    # not two; the profilers resolve that by checking the first token's keys.
    return out


_DOTTED = re.compile(r"(?:[a-z]\.){2,}")
_VERB_INFLECTIONS = frozenset({"VBD", "VBN", "VBZ", "VBG"})


def _is_english(word: str) -> bool:
    from lexinspect._lists import bnc_forms

    return word in bnc_forms()


def _lex(t, wi: int, extra_keys: tuple[str, ...]) -> LexToken:
    surface = _norm_apos(t.lower_)
    surface = _HOST_SURFACE_FIX.get(surface, surface)
    lemma = _norm_apos(t.lemma_.lower())
    # `Dr.`, `etc.`: lists carry abbreviations without the full stop, if at all.
    # Dotted initialisms (`e.g.`, `i.e.`, `a.m.`) are listed undotted (`eg`, `ie`).
    if surface.endswith(".") and surface.count(".") == 1:
        bare = surface.rstrip(".")
    elif _DOTTED.fullmatch(surface):
        bare = surface.replace(".", "")
    else:
        bare = surface
    if t.tag_ in _VERB_INFLECTIONS and lemma != surface and _is_english(lemma):
        # An inflected verb is looked up by its lemma only. Its surface form is
        # often a different word's base form — `found` (find / found a
        # company), `left` (leave / the left), `saw`, `felt`, `lay`, `rose`,
        # `wound`, `ground` — and a surface-first lookup credited the token to
        # the wrong lexeme (AWL `found`, CEFR B2). The surface is still the
        # fallback when the lemmatiser produced something that isn't a word.
        keys = tuple(dict.fromkeys((*extra_keys, lemma)))
    else:
        keys = tuple(dict.fromkeys((*extra_keys, surface, bare, lemma)))
    return LexToken(
        surface=surface,
        lemma=lemma,
        pos=t.pos_,
        tag=t.tag_,
        i=t.i,
        word_index=wi,
        is_proper=t.tag_ in ("NNP", "NNPS"),
        keys=keys,
    )


# --- building ---------------------------------------------------------------


def _group_words(doc) -> list[Word]:
    """Merge spaCy tokens into orthographic words.

    Two adjacent tokens with no whitespace between them belong to the same word
    when both are alphanumeric (`can|not`, `gon|na`, `do|n't`), or when a
    single hyphen joins two alphanumeric tokens (`well|-|known`). Everything
    else — punctuation, symbols, dashes — separates words and is not one.
    """
    words: list[Word] = []
    cur: list = []

    def flush():
        if cur:
            words.append(Word(tokens=list(cur), text="".join(t.text_with_ws for t in cur).strip()))
            cur.clear()

    n = len(doc)
    for k, tok in enumerate(doc):
        if tok.is_space:
            flush()
            continue
        if _has_alnum(tok.text) or is_clitic(tok):
            if (
                cur
                and cur[-1].whitespace_ == ""
                and (_has_alnum(cur[-1].text) or is_clitic(cur[-1]) or cur[-1].text in _HYPHENS)
            ):
                cur.append(tok)
                continue
            flush()
            if is_clitic(tok) and not _has_alnum(tok.text):
                # A lone apostrophe that isn't attached to anything is punctuation.
                continue
            cur.append(tok)
            continue
        if (
            tok.text in _HYPHENS
            and cur
            and cur[-1].whitespace_ == ""
            and tok.whitespace_ == ""
            and k + 1 < n
            and _has_alnum(doc[k + 1].text)
        ):
            cur.append(tok)
            continue
        flush()
    flush()
    return words


def _group_sentences(doc, words: list[Word]) -> list[list[Word]]:
    by_start: dict[int, int] = {}
    for idx, w in enumerate(words):
        for t in w.tokens:
            by_start[t.i] = idx
    sentences: list[list[Word]] = []
    for sent in doc.sents:
        seen: list[int] = []
        for t in sent:
            idx = by_start.get(t.i)
            if idx is not None and (not seen or seen[-1] != idx):
                seen.append(idx)
        if seen:
            sentences.append([words[i] for i in seen])
    return sentences


def analyse(text: str) -> Analysis:
    """Normalise, parse once, and segment `text`. The one entry point."""
    text = normalise(text)
    doc = parse(text)
    words = _group_words(doc)
    return Analysis(text=text, doc=doc, words=words, sentences=_group_sentences(doc, words))


def ensure(text: str, analysis: Analysis | None) -> Analysis:
    return analysis if analysis is not None else analyse(text)
