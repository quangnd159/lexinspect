"""Token-context helpers shared by the metadiscourse and PHRASE matchers."""

from __future__ import annotations

from lexinspect._text import _HYPHENS


def prev_word(tok):
    """The nearest token before `tok` that isn't whitespace, or None."""
    doc = tok.doc
    j = tok.i - 1
    while j >= 0 and doc[j].is_space:
        j -= 1
    return doc[j] if j >= 0 else None


def next_word(tok):
    """The nearest token after `tok` that isn't whitespace, or None."""
    doc = tok.doc
    j = tok.i + 1
    while j < len(doc) and doc[j].is_space:
        j += 1
    return doc[j] if j < len(doc) else None


def spaced_before(tok) -> bool:
    """Whitespace (or the start of the text) comes right before `tok`."""
    if tok.i == 0:
        return True
    p = tok.doc[tok.i - 1]
    return bool(p.whitespace_) or p.is_space


def is_hyphen(tok) -> bool:
    return tok is not None and tok.text in _HYPHENS


def in_hyphenated_word(first, last) -> bool:
    """Tokens `first`…`last` are part of a hyphenated word: a hyphen is joined,
    with no space, to `first` and the word before it (`common-sense`,
    `so-called`), or to `last` and the word after it (`second-order`).
    Hyphenated compounds are single words (Huddleston & Pullum 2002, ch. 19)."""
    doc = first.doc
    p = doc[first.i - 1] if first.i > 0 else None
    n = doc[last.i + 1] if last.i + 1 < len(doc) else None
    before = is_hyphen(p) and not p.whitespace_ and not spaced_before(p)
    after = is_hyphen(n) and not last.whitespace_ and not n.whitespace_
    return before or after


# Rewording `that is` is an appositive linking adverbial (Biber et al. 1999,
# linking adverbials of apposition): `the median, that is, the middle value`.
# Two constructions share its words (Study 4 guidelines B4, C1): relative
# `that` (`a method that is used`) and demonstrative `that` as the subject of
# `is` (`That is my car`). They are told apart by the clause role of `that`,
# not by punctuation, which the rewording use need not have (`…, as long as
# you pay that is.`).
_CLAUSE_OPENERS = frozenset({";", ":", "(", "[", "“", "‘", '"'})


def _opening_straight_single(p) -> bool:
    """Audit r2 S1: `p` is a straight single quote opening a quotation: a
    token of its own, not a possessive (dependency `case`, tag POS: `the
    students' view`), with whitespace or the start of the text before it and
    the quoted clause straight after it (`He said, 'That is wrong.'`)."""
    return (
        p.text == "'"
        and p.dep_ != "case"
        and p.tag_ != "POS"
        and spaced_before(p)
        and not p.whitespace_
    )


def rephrasing_that_is(that) -> bool:
    """`that is` (`that` its first word) keeps the rephrasing reading unless
    `that` is relative (tagged WDT, or the subject of a relative clause) or a
    demonstrative subject: opening its clause (at the start of the sentence,
    after `;` `:`, an opening quotation mark, a straight single one included
    (`He said, 'That is wrong.'`), or bracket, or a coordinator or
    subordinator: `but that is`, `if that is`), the subject of `is`, with a
    word, not punctuation, straight after `is` (`That is not the point`, `…;
    that is false`). `That is, …` and a sentence-final `… that is.` keep it. A
    demonstrative after a comma is not recognised and keeps it too: a comma
    also comes before the rewording use (`…, that is, …`)."""
    if that.tag_ == "WDT":
        return False
    subject = that.dep_ in ("nsubj", "nsubjpass")
    if subject and that.head.dep_ == "relcl":
        return False
    is_ = next_word(that)
    if is_ is None or not subject:
        return True
    p = prev_word(that)
    opens = (
        that.is_sent_start
        or p is None
        or p.text in _CLAUSE_OPENERS
        or _opening_straight_single(p)
        or p.pos_ in ("CCONJ", "SCONJ")
        or p.dep_ in ("cc", "mark")
    )
    of_is = that.head == is_ or any(
        c == is_ and c.dep_ in ("aux", "auxpass") for c in that.head.children
    )
    n = next_word(is_)
    return not (opens and of_is and n is not None and not n.is_punct)


# Specifying (goal and role) nouns. As the subject of `be` + to-infinitive
# they make a specificational clause (`our goal here is to measure drift`): the infinitive
# identifies the aim or role (Huddleston & Pullum 2002, ch. 4, specifying
# be), so the `is to` is not the PHRASE entry IS TO (PH-06).
SPECIFYING_NOUNS = frozenset(
    {
        "aim",
        "goal",
        "task",
        "purpose",
        "objective",
        "intention",
        "idea",
        "ambition",
        "aspiration",
        "mission",
        "role",
        "function",
        "job",
        "challenge",
        "solution",
        "plan",
        "strategy",
        "approach",
        "point",
        "hope",
        "priority",
        "step",
        "duty",
        "responsibility",
        "intent",
    }
)
