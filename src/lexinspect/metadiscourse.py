"""Metadiscourse marker detection (Hyland 2005, 10-category framework).

Two dimensions, five categories each:
- Interactive (organise the text): transitions, frame markers, endophoric
  markers, evidentials, code glosses.
- Interactional (engage the reader): hedges, boosters, attitude markers,
  engagement markers, self-mentions.

Hyland's categories are *functional*: a word is metadiscourse only when it does
metadiscoursal work in context, and his own counts were checked by hand. The
marker lists are full of everyday words that usually don't — `for`, `so`,
`and`, `first`, `table`, `found`, `would`, `about`, `you` — and the old matcher
counted every occurrence, which made densities several times too high and
rewarded essays for simply containing common words.

Each marker here is matched against the text (longest match first, never
across punctuation) and then has to pass a context check built on spaCy's
tags and dependency parse — the automatable part of Hyland's hand-coding:

- clause-linking transitions (`and`, `but`, `or`, `so`, `yet`, `for`) only when
  they join clauses or open a sentence; temporal/sequencing adverbs (`still`,
  `then`, `now`, `next`, `first`, `finally`) only clause-initially;
  subordinators (`since`, `while`) only as subordinators;
- endophoric nouns (`table`, `figure`, `page`, `section`) only with a reference
  (`Table 2`); `above`/`below` only when not a spatial preposition;
- cognitive and reporting verbs (`find`, `show`, `think`, `feel`, `argue`,
  `suggest`) only with a clausal complement, and as evidentials only when the
  subject is a source (`Smith (2010) argues`, `the study shows`);
- epistemic adjectives as boosters (`clear`, `certain`, `true`) only
  predicatively (`it is clear that`, not `a clear sky`);
- modals only as modals; approximators (`about`, `around`) only before a number;
- engagement verbs (`consider`, `note`, `imagine`) only as imperatives or with
  a reader subject;
- `we`/`us`/`our`: self-mention with research and argument verbs (`we found`,
  `we argue`), otherwise inclusive reader engagement.

Each hit lands in exactly one category (the old matcher counted `in fact` as
three hits). Rule decisions are explainable: every hit carries the category it
was assigned and, where the marker is listed under others, `also_listed_as`.

Marker lists are curated from canonical Hyland 2005 reproductions; the hedges
category mirrors Appendix A. See data/SOURCES.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from importlib import resources
from typing import Any

from lexinspect._text import Analysis, ensure


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw = (
        resources.files("lexinspect.data")
        .joinpath("metadiscourse.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(raw)


@lru_cache(maxsize=1)
def _index() -> tuple[dict[tuple[str, ...], list[tuple[str, str]]], int]:
    """Marker tuple -> [(dimension, category), ...] in list order; and max length."""
    out: dict[tuple[str, ...], list[tuple[str, str]]] = defaultdict(list)
    max_len = 0
    for dimension, cats in _load()["categories"].items():
        for category, items in cats.items():
            for item in items:
                key = tuple(item.replace("’", "'").split())
                # `let's`, `one's`, `couldn't` are split by spaCy into two
                # tokens; store them the way they'll appear.
                key = tuple(p for w in key for p in _split_clitic(w))
                if key:
                    out[key].append((dimension, category))
                    max_len = max(max_len, len(key))
    return dict(out), max_len


def _split_clitic(word: str) -> tuple[str, ...]:
    for clitic in ("n't", "'s"):
        if word.endswith(clitic) and len(word) > len(clitic):
            return (word[: -len(clitic)], clitic)
    return (word,)


# --- context predicates ------------------------------------------------------

_CLAUSE_BREAKS = frozenset({",", ";", ":", "(", "—", "–", "-"})
_SOURCE_NOUNS = frozenset(
    {
        "study",
        "studies",
        "research",
        "researcher",
        "researchers",
        "author",
        "authors",
        "report",
        "reports",
        "survey",
        "surveys",
        "data",
        "evidence",
        "result",
        "results",
        "finding",
        "findings",
        "paper",
        "article",
        "scholar",
        "scholars",
        "expert",
        "experts",
        "scientist",
        "scientists",
        "analysis",
        "literature",
        "review",
        "theory",
        "statistics",
        "figures",
        "experiment",
        "experiments",
        "work",
        "writer",
        "writers",
        "critic",
        "critics",
    }
)
_RESEARCH_VERBS = frozenset(
    {
        "argue",
        "propose",
        "suggest",
        "show",
        "find",
        "conclude",
        "examine",
        "investigate",
        "analyse",
        "analyze",
        "present",
        "report",
        "discuss",
        "describe",
        "focus",
        "aim",
        "believe",
        "think",
        "conduct",
        "use",
        "collect",
        "claim",
        "demonstrate",
        "observe",
        "measure",
        "test",
        "compare",
        "identify",
        "explore",
        "outline",
        "consider",
        "note",
        "hypothesise",
        "hypothesize",
        "assume",
        "define",
        "adopt",
        "employ",
        "develop",
    }
)
_READER_SUBJECTS = frozenset({"you", "we", "us"})


def _prev(tok):
    return tok.doc[tok.i - 1] if tok.i > 0 else None


def _next(tok, k: int = 1):
    j = tok.i + k
    return tok.doc[j] if j < len(tok.doc) else None


def clause_initial(tok) -> bool:
    """First word of its sentence, or right after a clause break (`,` `;` `:`)."""
    if tok.is_sent_start:
        return True
    p = _prev(tok)
    while p is not None and p.is_space:
        p = _prev(p)
    return p is None or p.text in _CLAUSE_BREAKS or p.is_sent_start and p.is_punct


def joins_clauses(tok) -> bool:
    """A coordinator joining two clauses (`I came and he left`), or opening a sentence."""
    if clause_initial(tok):
        return True
    head = tok.head
    if tok.dep_ != "cc" or head.pos_ not in ("VERB", "AUX"):
        return False
    return any(c.dep_ == "conj" and c.pos_ in ("VERB", "AUX") for c in head.children)


def is_subordinator(tok) -> bool:
    return tok.dep_ == "mark"


def has_clause_complement(tok) -> bool:
    """A verb with a clausal complement: `found that…`, `seems to…`, `I think it…`."""
    if tok.pos_ not in ("VERB", "AUX"):
        return False
    n = _next(tok)
    if n is not None and n.lower_ in ("that", "to", "whether", "if", "how", "why", "what"):
        return True
    if any(c.dep_ in ("ccomp", "xcomp") for c in tok.children):
        return True
    # `it seems`, `it appears`: expletive subject
    return any(c.dep_ == "expl" or (c.dep_ == "nsubj" and c.lower_ == "it") for c in tok.children)


def has_source_subject(tok) -> bool:
    for c in tok.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            return (
                c.pos_ == "PROPN"
                or c.lower_ in _SOURCE_NOUNS
                or (c.pos_ == "NOUN" and c.lemma_.lower() in _SOURCE_NOUNS)
            )
    return False


def writer_subject(tok) -> bool:
    """The writer is the subject: `I believe`, `we suspect`. Mental-state verbs
    mark the writer's stance only when the stance is the writer's own; `some
    people believe that…` reports someone else's."""
    for c in tok.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            return c.lower_ in ("i", "we")
    # Coordinated verb sharing a subject: `I hope and believe that…`
    if tok.dep_ == "conj" and tok.head is not tok:
        return writer_subject(tok.head)
    return False


def is_verb(tok) -> bool:
    return tok.pos_ in ("VERB", "AUX")


def is_modal(tok) -> bool:
    return tok.tag_ == "MD"


def predicative(tok) -> bool:
    return tok.pos_ == "ADJ" and tok.dep_ != "amod"


def before_number(tok) -> bool:
    n = _next(tok)
    return n is not None and (n.like_num or n.pos_ == "NUM")


def has_reference(tok) -> bool:
    """`Table 2`, `Figure 3b`, `Section IV`, `Appendix A`."""
    n = _next(tok)
    if n is None:
        return False
    t = n.text
    return n.like_num or (len(t) <= 4 and (t.isupper() or t[:1].isdigit()))


def not_spatial(tok) -> bool:
    """`see below`, `the table above` — not `above the clouds`."""
    return not (tok.tag_ == "IN" and any(c.dep_ == "pobj" for c in tok.children))


def addresses_reader(tok) -> bool:
    """Imperative (`Consider…`, `Note that…`) or with a reader subject (`you will notice`)."""
    if not is_verb(tok):
        return False
    subj = [c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")]
    if not subj:
        return tok.tag_ == "VB"
    return subj[0].lower_ in _READER_SUBJECTS


def _governing_verb(tok):
    """The verb a pronoun belongs to: its head, climbing out of nominals."""
    h = tok.head
    for _ in range(3):
        if h.pos_ in ("VERB", "AUX") or h == h.head:
            return h
        h = h.head
    return h


def exclusive_we(tok) -> bool:
    """`we`-forms used by writers about their own work (`we found`, `our results`)."""
    v = _governing_verb(tok)
    if v.lemma_.lower() in _RESEARCH_VERBS:
        return True
    if tok.lower_ in ("our", "ours"):
        return tok.head.lower_ in (
            "results",
            "findings",
            "study",
            "analysis",
            "data",
            "research",
            "aim",
            "approach",
            "method",
            "sample",
            "argument",
            "model",
            "experiment",
            "paper",
        )
    return False


def epistemic_must(tok) -> bool:
    """`must be true`, `must have been` (booster) vs `must act` (obligation)."""
    n = _next(tok)
    return n is not None and n.lower_ in ("be", "have")


Rule = Callable[[Any], bool]

# Context checks per (marker, category). A marker/category with no entry here
# needs no check. The first category in `_PRIORITY` (or list order) whose check
# passes is the one the hit is assigned to.
_RULES: dict[tuple[str, str], Rule] = {}


def _rule(markers: str, category: str, fn: Rule) -> None:
    for m in markers.split("|"):
        _RULES[(m, category)] = fn


_rule("and|but|or|yet|so|for", "transitions", joins_clauses)
_rule("for", "transitions", lambda t: t.tag_ == "CC" or (clause_initial(t) and t.dep_ == "cc"))
_rule("still|then|now|again|further|equally|instead|rather", "transitions", clause_initial)
_rule(
    "since|while|though|although|whereas|because",
    "transitions",
    lambda t: is_subordinator(t) or clause_initial(t),
)
_rule(
    "first|second|third|next|finally|lastly|overall",
    "frame_markers",
    lambda t: clause_initial(t) and t.pos_ in ("ADV", "ADJ", "NUM", "INTJ"),
)
_rule(
    "example|examples|figure|figures|table|tables|page|in chapter|in section|in part|"
    "see chapter|see figure|see section|see table",
    "endophoric_markers",
    has_reference,
)
_rule("above|below", "endophoric_markers", not_spatial)
_rule(
    "see",
    "endophoric_markers",
    lambda t: (n := _next(t)) is not None and n.lower_ in ("above", "below"),
)
_rule(
    "argues|asserts|believes|claim|claims|concludes|contends|demonstrates|discusses|"
    "indicates|maintains|mentions|notes|observes|proposes|remarks|reports|shows|states|"
    "stresses|suggests|writes",
    "evidentials",
    lambda t: is_verb(t) and has_source_subject(t),
)
_rule(
    "argues that|asserts that|believes that|claims that|concludes that|demonstrates that|"
    "found that|indicates that|maintains that|notes that|observes that|proposes that|"
    "reports that|shows that|states that|suggests that|points out",
    "evidentials",
    lambda t: is_verb(t) and has_source_subject(t),
)
_rule("cited|quoted", "evidentials", is_verb)
_rule(
    "find|found|show|shown|shows|establish|established|prove|proven|proves|"
    "demonstrate|demonstrates|conclude",
    "boosters",
    has_clause_complement,
)
_rule("think|believe", "boosters", lambda t: has_clause_complement(t) and writer_subject(t))
_rule("clear|certain|sure|true|obvious|definite|undeniable|indisputable", "boosters", predicative)
_rule("must", "boosters", epistemic_must)
_rule("must", "attitude_markers", lambda t: not epistemic_must(t))
# Hedging verbs hedge with a plain object too (`results suggest a link`)...
_rule(
    "argue|argued|argues|claim|claimed|claims|indicate|indicated|indicates|suggest|suggested|"
    "suggests|estimate|estimated|postulate|postulated|postulates",
    "hedges",
    is_verb,
)
# ...but these have common literal senses (`felt the cold`, `appeared on stage`).
_rule("appear|appeared|appears", "hedges", has_clause_complement)
_rule(
    "feel|feels|felt|assume|assumed|suppose|supposes|suspect|suspects|guess",
    "hedges",
    lambda t: has_clause_complement(t) and writer_subject(t),
)
_rule(
    "supposed",
    "hedges",
    lambda t: has_clause_complement(t) and not ((n := _next(t)) is not None and n.lower_ == "to"),
)
_rule("would|could|should|might|may|ought|couldn't", "hedges", is_modal)
_rule("about|around", "hedges", before_number)
_rule("rather", "hedges", lambda t: not clause_initial(t))
_rule("doubt", "hedges", is_verb)
_rule("agree|prefer|preferred|expected", "attitude_markers", is_verb)
_rule(
    "consider|imagine|look|note|notice|picture|recall|see|think about|think of",
    "engagement_markers",
    addresses_reader,
)
_rule("we|us|our|ours|ourselves", "self_mentions", exclusive_we)
_rule(
    "say",
    "code_glosses",
    lambda t: (
        ((p := _prev(t)) is not None and p.text == ",")
        or ((n := _next(t)) is not None and n.text == ",")
    ),
)
_rule("called|known as", "code_glosses", lambda t: t.tag_ == "VBN")
_rule("meaning", "code_glosses", lambda t: t.tag_ == "VBG")
_rule("or", "code_glosses", lambda t: False)  # `or` as a gloss needs a human
_rule("as", "evidentials", lambda t: False)  # bare `as`: the multi-word evidentials cover it
_rule("earlier|later", "endophoric_markers", lambda t: False)  # bare: temporal, not textual
_rule(
    "the table|the figure|the example",
    "endophoric_markers",
    lambda t: (n := _next(t, 2)) is not None and n.lower_ in ("above", "below"),
)
_rule("you|your|yours", "engagement_markers", lambda t: True)

# Where a marker is listed under several categories, which to try first.
_PRIORITY: dict[str, tuple[str, ...]] = {
    "in fact": ("boosters", "code_glosses", "transitions"),
    "indeed": ("boosters", "code_glosses", "transitions"),
    "for example": ("code_glosses",),
    "for instance": ("code_glosses",),
    "in other words": ("code_glosses",),
    "in particular": ("code_glosses",),
    "namely": ("code_glosses",),
    "specifically": ("code_glosses",),
    "such as": ("code_glosses",),
    "particularly": ("code_glosses", "boosters"),
    "rather": ("transitions", "hedges"),
    "on the whole": ("hedges", "frame_markers"),
    "usually": ("hedges", "attitude_markers"),
    "see": ("endophoric_markers", "engagement_markers"),
    "must": ("boosters", "attitude_markers"),
    "we": ("self_mentions", "engagement_markers"),
    "us": ("self_mentions", "engagement_markers"),
    "our": ("self_mentions", "engagement_markers"),
    "ours": ("self_mentions", "engagement_markers"),
    "ourselves": ("self_mentions", "engagement_markers"),
}
for _m in ("argues", "claim", "claims", "indicates", "suggests"):
    _PRIORITY[_m] = ("evidentials", "hedges")
for _m in ("demonstrates", "shows"):
    _PRIORITY[_m] = ("evidentials", "boosters")


def _assign(marker: str, entries: list[tuple[str, str]], first_tok) -> tuple[str, str] | None:
    by_cat = {cat: dim for dim, cat in entries}
    order = list(_PRIORITY.get(marker, ())) + [c for _, c in entries]
    for cat in dict.fromkeys(order):
        if cat not in by_cat:
            continue
        check = _RULES.get((marker, cat))
        if check is None or check(first_tok):
            return by_cat[cat], cat
    return None


def _segments(doc):
    for sent in doc.sents:
        run = []
        for tok in sent:
            if tok.is_space:
                continue
            if tok.is_punct and tok.text not in ("'", "’"):
                if run:
                    yield run
                run = []
                continue
            run.append(tok)
        if run:
            yield run


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    a = ensure(text, analysis)
    index, max_len = _index()

    hits: list[dict[str, Any]] = []
    for run in _segments(a.doc):
        lowers = [t.lower_.replace("’", "'") for t in run]
        i, n = 0, len(run)
        while i < n:
            consumed = 1
            for span_len in range(min(max_len, n - i), 0, -1):
                window = tuple(lowers[i : i + span_len])
                entries = index.get(window)
                if not entries:
                    continue
                marker = " ".join(window)
                chosen = _assign(marker, entries, run[i])
                if chosen is None:
                    continue  # listed, but not doing metadiscourse work here
                dim, cat = chosen
                span = run[i : i + span_len]
                hit = {
                    "dimension": dim,
                    "category": cat,
                    "marker": marker,
                    "surface": a.text[span[0].idx : span[-1].idx + len(span[-1].text)],
                    "token_index": span[0].i,
                    "span": [span[0].idx, span[-1].idx + len(span[-1].text)],
                }
                others = sorted({c for _, c in entries} - {cat})
                if others:
                    hit["also_listed_as"] = others
                hits.append(hit)
                consumed = span_len
                break
            i += consumed

    words = a.word_count
    cat_counts: dict[str, int] = defaultdict(int)
    cat_unique: dict[str, set[str]] = defaultdict(set)
    dim_counts: dict[str, int] = defaultdict(int)
    for h in hits:
        cat_counts[h["category"]] += 1
        cat_unique[h["category"]].add(h["marker"])
        dim_counts[h["dimension"]] += 1

    cats_meta = _load()["categories"]
    return {
        "counts": {
            "content_tokens": words,
            "total_hits": len(hits),
            "interactive_hits": dim_counts.get("interactive", 0),
            "interactional_hits": dim_counts.get("interactional", 0),
        },
        "density_per_1000": _density(len(hits), words),
        "per_dimension": {
            dim: {
                "hits": dim_counts.get(dim, 0),
                "density_per_1000": _density(dim_counts.get(dim, 0), words),
            }
            for dim in cats_meta
        },
        "per_category": {
            cat: {
                "dimension": dim,
                "hits": cat_counts.get(cat, 0),
                "unique_markers": len(cat_unique.get(cat, set())),
                "density_per_1000": _density(cat_counts.get(cat, 0), words),
            }
            for dim, cats in cats_meta.items()
            for cat in cats
        },
        "hits": hits,
    }


def _density(n: int, total: int) -> float:
    return round(n / total * 1000, 3) if total else 0.0


def warm() -> None:
    _index()
