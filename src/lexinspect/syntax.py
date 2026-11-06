"""Syntactic complexity from the shared dependency parse.

The fourteen indices are those of Lu's (2010) L2 Syntactic Complexity Analyzer
(L2SCA; Lu, "Automatic analysis of syntactic complexity in second language
writing", International Journal of Corpus Linguistics 15(4): 474-496). L2SCA
counts its units with Tregex patterns over Stanford Parser *constituency*
trees. lexinspect has a spaCy *dependency* parse (en_core_web_sm), already
built once per request, so every unit here is an **approximation** of the
Tregex original, rewritten as rules over dependency labels and Penn tags. The
rules follow the Tregex patterns rather than the prose definitions where the
two differ, and each says so. Spring & Johnson (2022, ANLP 28: 319-322) found
that even plain counts of UD labels track L2SCA's clause count closely
(r = .90) but its dependent clauses (.63) and coordinate phrases (.68) less
well, and could not recover T-units or verb phrases at all; the rules below walk
the tree instead of counting labels, which is what T-units and VPs need.

Units
-----

- **W (words)** — the shared `Analysis` words (a contraction is one word).
  L2SCA counts Penn tokens, so `don't` is two words there.
- **S (sentences)** — the shared `Analysis` sentences, wordless ones skipped.
- **Finite verb** — a verb or auxiliary heading its own phrase (not itself an
  `aux`) whose tag is VBD/VBZ/VBP/MD, or which has an `aux`/`auxpass` child
  with one of those tags (`has eaten`, `will go`, `was stolen`). L2SCA's head
  test, `<# MD|VBZ|VBP|VBD`.
- **C (clause)** — a finite verb (or a sentence-root imperative: bare VB, no
  subject, no `to`; L2SCA's `S > ROOT <, (VP <# VB)`). A finite verb joined to
  another verb by `conj` (likewise `xcomp`/`dep`) is a clause only if it has
  its own subject (`nsubj`, `nsubjpass`, `csubj`, `csubjpass`, `expl`): `He
  came and sat` is one clause with a coordinated VP, as in L2SCA, where both
  VPs sit under one S. Lu's prose says a clause needs a subject; the Tregex
  pattern doesn't, and neither does this rule for other relations (`as is
  known`).
- **DC (dependent clause)** — a clause attached as `advcl`, `relcl`, `acl`,
  `ccomp`, `csubj`, `csubjpass` or `pcomp` (L2SCA: a finite S under SBAR —
  adverbial, relative and nominal clauses, with or without `that`). A clause
  coordinated (`conj`/`parataxis`) with a dependent clause is dependent too
  (`because he came and she left`). A sentence-root clause with a
  subordinator (`Because he was tired.`) is a dependent clause. A `ccomp`
  *before* its head with no complementizer or wh-word (fronted reported
  speech, `He is coming, she said`) is a clause but not a dependent one: the
  Stanford tree has a bare S there, not SBAR.
- **T (T-unit)** — each independent clause: the sentence-root clause, and every
  clause coordinated with it (`conj`/`parataxis`) that has its own subject.
  en_core_web_sm attaches the first of two clauses joined by `;` or `:` as a
  fronted `ccomp` of the second; across a semicolon or colon that is read as
  coordination (Stanford: S(S ; S), two T-units). A
  sentence with clauses but no independent clause (`Because he was tired.`,
  `The man who came.`) is one fragment T-unit, as L2SCA's FRAG rule counts it.
  A sentence with no clause at all — a heading, `Thanks!` — is no T-unit and
  no clause (see divergences).
- **CT (complex T-unit)** — a T-unit with a dependent clause anywhere below it
  (each clause belongs to its nearest independent-clause ancestor).
- **CP (coordinate phrase)** — one per coordination (a head and its chain of
  `conj` dependents, with a `cc` somewhere in it) whose head is a noun or
  pronoun (NP), adjective (ADJP), adverb (ADVP) or verb (VP); L2SCA's
  `ADJP|ADVP|NP|VP < CC`. A verb coordination counts only if some conjunct has
  no subject of its own: coordinated *clauses* are not coordinate phrases.
  Prepositional, numeral and asyndetic (no `cc`) coordinations don't count.
- **CN (complex nominal)** — the sum of L2SCA's three patterns. (1) A maximal
  noun phrase — a noun or pronoun that isn't a `compound`, `poss`, `nmod`,
  `appos` or a conjunct of another nominal (those sit inside a larger NP, and
  Tregex counts only `NP !> NP`) — whose subtree contains an adjective
  (JJ/JJR/JJS), a possessive `'s` (POS), a VBG, a prepositional phrase, an
  appositive, or a clause (`relcl`, `acl`, `ccomp`, `advcl`, `xcomp`, `pcomp`,
  `csubj`). As in Tregex, possessive pronouns (`his`) don't qualify, and an NP
  inside a PP is a separate candidate (`the book on the old table` is two).
  (2) A nominal clause: `csubj`/`csubjpass`, or `ccomp` of a verb, introduced by
  `that`, `for`, a wh-pronoun, or nothing (a finite clause) — not by
  `whether`/`if`/`how`/`when`, which Tregex's `<# WHNP | <# that|for | <, S`
  leaves out. (3) A gerund or infinitive subject (`Swimming is fun`, `To err is
  human`).
- **VP (verb phrase)** — one per clause (L2SCA's `VP > S`: a coordinated VP is
  one VP), plus each non-finite verb heading a clause-like dependent: `xcomp`,
  `advcl`, `ccomp`, `csubj`, `pcomp`, `parataxis`, a non-finite root, a
  `to`-infinitive `acl` (`a way to do it`), or a VBG verb as subject or object.
  Reduced relatives (`the man sitting there`) and prenominal participles are
  not VPs: Tregex puts them under NP, not S.

Ratios are L2SCA's: MLS = W/S, MLT = W/T, MLC = W/C, then C/S, VP/T, C/T, DC/C,
DC/T, T/S, CT/T, CP/T, CP/C, CN/T, CN/C. `None` when the denominator is zero.

Beyond L2SCA
------------

- **Mean dependency distance** (Liu 2008, Journal of Cognitive Science 9(2):
  159-191): mean |position(word) - position(head)| over every word-to-head
  link within a sentence, punctuation removed before positions are taken, the
  root excluded. Text MDD pools all links (total distance / total links), as
  Liu does; each sentence also gets its own.
- **Passive clauses** — clauses with an `nsubjpass`, `csubjpass` or `auxpass`
  dependent; count and share of all clauses.
- **Parse depth** — links on the longest root-to-word path (punctuation
  excluded; a one-word sentence is 0); text value is the mean over sentences.
- **Phrasal (noun-phrase) complexity** (Biber, Gray & Poonpon 2011, TESOL
  Quarterly 45(1): 5-35): attributive adjectives (`amod` JJ* on a noun),
  prepositional post-modifiers of nouns (`prep` after a noun head), and
  pre-modifying nouns (`compound` common noun before a noun head), each per
  1,000 words.

Known divergences
-----------------

- A different parser: spaCy's small model and the Stanford PCFG make different
  attachment errors, and learner English (missing subjects, run-ons, agreement
  errors) parses worse on both, so counts on learner texts are noisier than on
  edited prose.
- Verbless sentences: L2SCA counts a FRAG root as one clause and one T-unit but
  an NP root as neither, and which one the Stanford parser builds can't be
  reproduced here. They count as neither, which keeps headings from deflating
  MLC and MLT; their words still count in W, as in L2SCA.
- Fragment T-units with a dependent clause count as complex T-units here;
  L2SCA's CT pattern requires a real S T-unit.
- Clauses coordinated inside a dependent clause count as dependent clauses
  here; Tregex misses them (the SBAR's S then has no VP child).
- Reduced relatives with a past participle (`the car stolen yesterday`) make
  a complex nominal here, following Lu's prose ("participle"); Tregex only
  catches them when a PP or other listed tag is inside.
- Comma splices and `parataxis` with a subject start a new T-unit; Stanford
  trees sometimes nest a parenthetical clause in PRN instead.
"""

from __future__ import annotations

from typing import Any

from lexinspect._text import Analysis, ensure

MIN_WORDS_RELIABLE = 100
MIN_SENTENCES_RELIABLE = 5

_FINITE_TAGS = frozenset({"VBD", "VBZ", "VBP", "MD"})
_SUBJECTS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})
_PASSIVE = frozenset({"nsubjpass", "csubjpass", "auxpass"})
_AUX = frozenset({"aux", "auxpass"})
# Relations under which a finite verb is a dependent clause (L2SCA: S under SBAR).
_DC_DEPS = frozenset({"advcl", "relcl", "acl", "ccomp", "csubj", "csubjpass", "pcomp"})
# Relations that join two clauses as equals.
_COORD_DEPS = frozenset({"conj", "parataxis"})
# Relations under which a finite verb is a clause only with a subject of its own.
_NEEDS_SUBJECT = frozenset({"conj", "xcomp", "dep"})
_CLAUSE_DEPS = _DC_DEPS | _COORD_DEPS | _NEEDS_SUBJECT | {"ROOT"}
# Non-finite verbs under these relations head a VP that Tregex finds under S.
_NONFINITE_VP_DEPS = frozenset(
    {"xcomp", "advcl", "ccomp", "csubj", "csubjpass", "pcomp", "parataxis", "ROOT"}
)
_GERUND_ARG_DEPS = frozenset({"nsubj", "nsubjpass", "dobj", "pobj", "attr"})

_NOMINAL = frozenset({"NOUN", "PROPN", "PRON"})
_NOUN = frozenset({"NOUN", "PROPN"})
_VERBAL = frozenset({"VERB", "AUX"})
# A nominal under these relations is inside a larger NP (Tregex `NP > NP`).
_INNER_NP_DEPS = frozenset({"compound", "poss", "nmod", "appos"})
_CN_TAGS = frozenset({"JJ", "JJR", "JJS", "POS", "VBG"})
_CN_DEPS = frozenset(
    {"prep", "appos", "relcl", "acl", "ccomp", "advcl", "xcomp", "pcomp", "csubj", "csubjpass"}
)
_ADJ_TAGS = frozenset({"JJ", "JJR", "JJS"})
_CP_CATEGORY = {
    "NOUN": "NP",
    "PROPN": "NP",
    "PRON": "NP",
    "ADJ": "ADJP",
    "ADV": "ADVP",
    "VERB": "VP",
    "AUX": "VP",
}

VALIDITY: dict[str, Any] = {
    "status": "approximation",
    "method": (
        "Lu's (2010) L2SCA units re-derived from spaCy's dependency parse "
        "(en_core_web_sm) instead of Tregex patterns over Stanford constituency trees. "
        "Rules follow the Tregex patterns; counts will differ from L2SCA's on the same "
        "text wherever the two parsers or the two representations disagree."
    ),
    "evidence": (
        "Not yet validated against L2SCA output. A cruder UD label-counting approach "
        "correlated r = .90 with L2SCA's clause count, .63 for dependent clauses and .68 "
        "for coordinate phrases on 135 Japanese EFL paragraphs (Spring & Johnson 2022)."
    ),
    "population": (
        "Parsers are trained on edited native-speaker English; learner English parses "
        "less accurately, so counts on learner texts carry more error."
    ),
}


# --- token predicates --------------------------------------------------------


def _is_verbal(t) -> bool:
    return t.pos_ in _VERBAL and t.dep_ not in _AUX


def _has_subject(t) -> bool:
    return any(c.dep_ in _SUBJECTS for c in t.children)


def _is_finite(t) -> bool:
    if t.tag_ in _FINITE_TAGS:
        return True
    return any(c.dep_ in _AUX and c.tag_ in _FINITE_TAGS for c in t.children)


def _is_imperative(t, is_root: bool) -> bool:
    return (
        is_root
        and t.tag_ == "VB"
        and not _has_subject(t)
        and not any(c.dep_ in _AUX and c.tag_ == "TO" for c in t.children)
    )


def _is_clause(t, is_root: bool) -> bool:
    if not _is_verbal(t):
        return False
    dep = "ROOT" if is_root else t.dep_
    if dep not in _CLAUSE_DEPS:
        return False
    if not (_is_finite(t) or _is_imperative(t, is_root)):
        return False
    return dep not in _NEEDS_SUBJECT or _has_subject(t)


def _is_passive(t) -> bool:
    return any(c.dep_ in _PASSIVE for c in t.children)


def _has_to(t) -> bool:
    return any(c.dep_ in _AUX and c.tag_ == "TO" for c in t.children)


# --- per-sentence analysis ---------------------------------------------------


class _Sentence:
    """Units of one sentence, from its dependency tree."""

    def __init__(self, sent) -> None:
        self.sent = sent
        lo, hi = sent.start, sent.end
        toks = [t for t in sent if not t.is_space]
        self.roots = {t.i for t in sent if t.head.i == t.i or not (lo <= t.head.i < hi)}
        self.clauses = [t for t in toks if _is_clause(t, t.i in self.roots)]
        clause_ids = {t.i for t in self.clauses}

        # Role of each clause: main (independent), dependent, or other.
        role: dict[int, str] = {}

        def role_of(t) -> str:
            if t.i in role:
                return role[t.i]
            role[t.i] = "other"  # guard against cycles in malformed trees
            r = self._role(t, clause_ids, role_of)
            role[t.i] = r
            return r

        for c in self.clauses:
            role_of(c)
        mains = [c for c in self.clauses if role[c.i] == "main"]
        dependents = [c for c in self.clauses if role[c.i] == "dependent"]
        main_ids = {c.i for c in mains}

        # Each clause belongs to its nearest independent-clause ancestor (itself,
        # if independent); a clause with none belongs to a fragment T-unit.
        t_units: dict[int, list] = {i: [] for i in main_ids}
        fragment: list = []
        for c in self.clauses:
            owner = self._owner(c, main_ids)
            (t_units[owner] if owner is not None else fragment).append(c)
        if fragment:
            t_units[-1] = fragment
        dep_ids = {c.i for c in dependents}
        self.t_units = len(t_units)
        self.complex_t_units = sum(
            1 for members in t_units.values() if any(c.i in dep_ids for c in members)
        )
        self.dependent_clauses = len(dependents)
        self.passive = sum(1 for c in self.clauses if _is_passive(c))
        self.verb_phrases = len(self.clauses) + sum(
            1 for t in toks if self._is_nonfinite_vp(t, clause_ids)
        )
        self.coordinate_phrases = self._coordinate_phrases(toks)
        self.complex_nominals = sum(1 for t in toks if self._is_complex_nominal(t, clause_ids))

        # Dependency distance and depth over non-punctuation tokens.
        words = [t for t in toks if not _is_punct(t)]
        pos = {t.i: k for k, t in enumerate(words)}
        self.links = 0
        self.distance = 0
        for t in words:
            if t.i in self.roots or t.head.i not in pos:
                continue
            self.links += 1
            self.distance += abs(pos[t.i] - pos[t.head.i])
        self.depth = _depth(words, self.roots)

    def _role(self, t, clause_ids, role_of) -> str:
        if t.i in self.roots:
            return "dependent" if any(c.dep_ == "mark" for c in t.children) else "main"
        fronted = _fronted_bare_ccomp(t)
        if fronted == "coordinate":
            head = t.head
            if head.i in clause_ids:
                return "main" if role_of(head) == "main" else "dependent"
            return "main" if head.i in self.roots else "other"
        if fronted == "quote":
            return "other"
        if t.dep_ in _DC_DEPS:
            return "dependent"
        if t.dep_ in _COORD_DEPS:
            # Climb the coordination chain to its first member.
            top = t.head
            while top.i not in clause_ids and top.dep_ in _COORD_DEPS and top.i not in self.roots:
                top = top.head
            if top.i in clause_ids:
                return "main" if role_of(top) == "main" else "dependent"
            # Coordinated with a non-clause root (a heading, a non-finite root):
            # the first real independent clause.
            return "main" if top.i in self.roots else "other"
        return "other"

    def _owner(self, c, main_ids) -> int | None:
        t = c
        seen = set()
        while t.i not in seen:
            if t.i in main_ids:
                return t.i
            seen.add(t.i)
            if t.i in self.roots:
                return None
            t = t.head
        return None

    def _is_nonfinite_vp(self, t, clause_ids) -> bool:
        if t.i in clause_ids or not _is_verbal(t):
            return False
        dep = "ROOT" if t.i in self.roots else t.dep_
        if dep in _NONFINITE_VP_DEPS:
            return True
        if dep == "acl":
            return _has_to(t)
        return dep in _GERUND_ARG_DEPS and t.tag_ == "VBG"

    def _coordinate_phrases(self, toks) -> int:
        n = 0
        for h in toks:
            if h.dep_ == "conj" and h.i not in self.roots:
                continue  # counted with the head of its chain
            members = _conj_chain(h)
            if len(members) < 2 or h.pos_ not in _CP_CATEGORY:
                continue
            if not any(c.dep_ in ("cc", "preconj") for m in members for c in m.children):
                continue
            if _CP_CATEGORY[h.pos_] == "VP" and all(_has_subject(m) for m in members[1:]):
                continue  # coordinated clauses, not a coordinated VP
            n += 1
        return n

    def _is_complex_nominal(self, t, clause_ids) -> bool:
        is_root = t.i in self.roots
        if t.pos_ in _NOMINAL:
            # (1) a maximal NP with a qualifying modifier anywhere inside it.
            if not is_root and (
                t.dep_ in _INNER_NP_DEPS or (t.dep_ == "conj" and t.head.pos_ in _NOMINAL)
            ):
                return False
            return any(d.i != t.i and (d.tag_ in _CN_TAGS or d.dep_ in _CN_DEPS) for d in t.subtree)
        if is_root or not _is_verbal(t):
            return False
        subject = t.dep_ in ("csubj", "csubjpass")
        if subject or (
            t.dep_ == "ccomp" and t.head.pos_ in _VERBAL and _fronted_bare_ccomp(t) is None
        ):
            # (2) a nominal clause, introduced by that/for, a wh-pronoun, or nothing.
            marks = [c.lower_ for c in t.children if c.dep_ == "mark"]
            if marks:
                return any(m in ("that", "for") for m in marks)
            if t.i in clause_ids:
                first = t.left_edge
                return first.tag_ != "WRB" and first.lower_ not in ("whether", "if", "how")
            # (3) a gerund or infinitive subject.
            return subject and (t.tag_ == "VBG" or _has_to(t))
        # (3) a gerund tagged as a verb in subject position.
        return t.dep_ in ("nsubj", "nsubjpass") and t.tag_ == "VBG"


def _fronted_bare_ccomp(t) -> str | None:
    """A `ccomp` before its head with no complementizer or wh-word.

    en_core_web_sm attaches the first of two clauses joined by a semicolon or
    colon as a `ccomp` of the second (`Planting takes an hour; growing takes
    decades`), the structure it also gives fronted reported speech (`He is
    coming, she said`). In a Stanford tree the first is S(S ; S), two T-units;
    the second is a bare S, a clause but not under SBAR, so not a dependent
    clause. Returns "coordinate", "quote", or None (an ordinary ccomp).
    """
    if t.dep_ != "ccomp" or t.i > t.head.i:
        return None
    if any(c.dep_ == "mark" for c in t.children) or t.left_edge.tag_ in ("WP", "WDT", "WP$", "WRB"):
        return None
    between = t.doc[t.right_edge.i + 1 : t.head.i]
    return "coordinate" if any(x.text in (";", ":") for x in between) else "quote"


def _is_punct(t) -> bool:
    return t.is_punct or t.dep_ == "punct" or t.is_space


def _conj_chain(h) -> list:
    out = [h]
    stack = [c for c in h.children if c.dep_ == "conj"]
    while stack:
        c = stack.pop(0)
        out.append(c)
        stack.extend(g for g in c.children if g.dep_ == "conj")
    return out


def _depth(words, roots) -> int:
    """Links on the longest path from a root down to a word."""
    memo: dict[int, int] = {}
    best = 0
    for t in words:
        path = []
        cur = t
        while cur.i not in memo and cur.i not in roots and cur.head.i != cur.i:
            if len(path) > len(words):  # malformed tree: stop rather than loop
                break
            path.append(cur.i)
            cur = cur.head
        base = memo.get(cur.i, 0)
        for k, i in enumerate(reversed(path), start=1):
            memo[i] = base + k
        best = max(best, memo.get(t.i, 0))
    return best


# --- phrasal complexity (Biber et al. 2011) ----------------------------------


def _phrasal(doc) -> dict[str, int]:
    adj = prep = noun = 0
    for t in doc:
        head = t.head
        if head.i == t.i or head.pos_ not in _NOUN:
            continue
        if t.dep_ == "amod" and t.tag_ in _ADJ_TAGS:
            adj += 1
        elif t.dep_ == "prep" and t.i > head.i:
            prep += 1
        elif t.dep_ == "compound" and t.pos_ == "NOUN" and t.i < head.i:
            noun += 1
    return {
        "attributive_adjectives": adj,
        "prepositional_postmodifiers": prep,
        "premodifying_nouns": noun,
    }


# --- entry point --------------------------------------------------------------


def _ratio(numerator: float, denominator: float, places: int = 3) -> float | None:
    return round(numerator / denominator, places) if denominator else None


def _span(sent) -> list[int]:
    toks = [t for t in sent if not t.is_space]
    first, last = toks[0], toks[-1]
    return [first.idx, last.idx + len(last.text)]


def analyze(text: str, *, analysis: Analysis | None = None) -> dict[str, Any]:
    """Syntactic complexity of `text`.

    Sentence `span`s are `[start, end)` character offsets into `analysis.text`
    (the normalised input), trimmed of surrounding whitespace, so
    `analysis.text[start:end]` is exactly the sentence.
    """
    a = ensure(text, analysis)
    word_tokens = a.word_index_of_token
    # The same filter as the shared sentences: a spaCy sentence with no word in
    # it (a stray bracket) isn't a sentence. Pairs one-to-one with a.sentences.
    sents = [s for s in a.doc.sents if any(t.i in word_tokens for t in s)]
    parsed = [_Sentence(s) for s in sents]

    n_w = a.word_count
    n_s = len(parsed)
    c = sum(len(p_.clauses) for p_ in parsed)
    dc = sum(p_.dependent_clauses for p_ in parsed)
    t = sum(p_.t_units for p_ in parsed)
    ct = sum(p_.complex_t_units for p_ in parsed)
    cp = sum(p_.coordinate_phrases for p_ in parsed)
    cn = sum(p_.complex_nominals for p_ in parsed)
    vp = sum(p_.verb_phrases for p_ in parsed)
    passive = sum(p_.passive for p_ in parsed)
    links = sum(p_.links for p_ in parsed)
    distance = sum(p_.distance for p_ in parsed)
    phrasal = _phrasal(a.doc)

    sentences = [
        {
            "span": _span(p_.sent),
            "words": len(words),
            "clauses": len(p_.clauses),
            "dependent_clauses": p_.dependent_clauses,
            "t_units": p_.t_units,
            "passive": p_.passive,
            "depth": p_.depth,
            "mdd": _ratio(p_.distance, p_.links),
        }
        for p_, words in zip(parsed, a.sentences, strict=True)
    ]

    notes: list[str] = []
    if n_w < MIN_WORDS_RELIABLE:
        notes.append(
            f"Only {n_w} words. Syntactic complexity ratios need {MIN_WORDS_RELIABLE}+ words; "
            "on shorter texts one sentence swings every index."
        )
    if n_s < MIN_SENTENCES_RELIABLE:
        notes.append(
            f"Only {n_s} sentence{'' if n_s == 1 else 's'}. Per-sentence and per-T-unit "
            f"ratios need {MIN_SENTENCES_RELIABLE}+ sentences to mean much."
        )

    return {
        "counts": {
            "words": n_w,
            "sentences": n_s,
            "clauses": c,
            "dependent_clauses": dc,
            "t_units": t,
            "complex_t_units": ct,
            "coordinate_phrases": cp,
            "complex_nominals": cn,
            "verb_phrases": vp,
            "passive_clauses": passive,
        },
        "indices": {
            "mls": _ratio(n_w, n_s),
            "mlt": _ratio(n_w, t),
            "mlc": _ratio(n_w, c),
            "c_s": _ratio(c, n_s),
            "vp_t": _ratio(vp, t),
            "c_t": _ratio(c, t),
            "dc_c": _ratio(dc, c),
            "dc_t": _ratio(dc, t),
            "t_s": _ratio(t, n_s),
            "ct_t": _ratio(ct, t),
            "cp_t": _ratio(cp, t),
            "cp_c": _ratio(cp, c),
            "cn_t": _ratio(cn, t),
            "cn_c": _ratio(cn, c),
        },
        "dependency": {
            "mean_dependency_distance": _ratio(distance, links),
            "mean_parse_depth": _ratio(sum(p_.depth for p_ in parsed), n_s),
        },
        "passive": {
            "clauses": passive,
            "share_of_clauses": _ratio(passive, c),
        },
        "phrasal": {
            **phrasal,
            **{f"{k}_per_1000_words": _ratio(v * 1000, n_w, 2) for k, v in phrasal.items()},
        },
        "sentences": sentences,
        "reliability": {
            "reliable": n_w >= MIN_WORDS_RELIABLE and n_s >= MIN_SENTENCES_RELIABLE,
            "notes": notes,
        },
        "validity": VALIDITY,
    }
