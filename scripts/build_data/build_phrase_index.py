"""Compile phrase.json's base forms into matchable variants and sense constraints.

    uv run python scripts/build_data/build_phrase_index.py

Reads and rewrites src/lexinspect/data/phrase.json in place, adding to each item:

- `variants`: every token sequence the entry stands for. The printed base forms
  pack alternatives and optional words into one string, and the old matcher
  read them literally — `THERE IS/ARE` became the never-matching sequence
  `there is are`, `A GOOD/GREAT DEAL` became `a good great deal`. Now:
  `ONE'S` / `ONESELF` become possessive / reflexive slots (`shook his head`);
  `X/Y` expands to alternatives; `(OF)`, `(TO)`, `(BE)`, `(WITH)`, `(THE SENSE)`,
  `A(N)`, `DO(ING)` and similar mark optional material and expand to with/without;
  quoted or lower-case parentheses (`('CAUSE')`, `(anaphor)`, `(PAST)`) are sense
  glosses and are dropped from the form but kept as `sense`.
- `tags`: for each `to` / `that` / particle in the phrase, the Penn tag (`TO` infinitival vs `IN`
  prepositional) it carries in the entry's own example sentence. The matcher
  requires the same tag, which is what separates GOING TO (FUTURE) from "going to
  the park", and USED TO (PAST) "used to snow" from USED TO (ACCUSTOMED) "used
  to the noise".

Variants are tokenised with spaCy's tokenizer, so `ONE'S` splits exactly as it
will in running text.
"""

from __future__ import annotations

import json
import re
from itertools import product
from pathlib import Path

import spacy

DATA = Path(__file__).resolve().parents[2] / "src" / "lexinspect" / "data" / "phrase.json"

# Upper-case parentheticals that are optional words, not sense labels. Checked
# by hand against each entry's example sentence.
OPTIONAL = {"OF", "TO", "WITH", "FOR", "AS", "AT", "BE", "THE SENSE", "AGAIN"}
# Parentheses glued to a word are optional suffixes: A(N), DO(ING).
_GLUED = re.compile(r"(\w+)\((\w+)\)")
_PAREN = re.compile(r"\(([^)]*)\)")


def _alternatives(phrase: str) -> tuple[list[list[str]], str | None]:
    """Return (list of word sequences, sense gloss)."""
    sense = None

    def gloss(m: re.Match[str]) -> str:
        nonlocal sense
        inner = m.group(1).strip()
        if inner.upper() in OPTIONAL and inner == inner.upper():
            return f" [{inner}] "
        sense = inner.strip("'‘’ ")
        return " "

    p = _GLUED.sub(lambda m: f"{m.group(1)}{{{m.group(2)}}}", phrase)
    p = _PAREN.sub(gloss, p)
    words = p.split()
    # Each slot becomes a list of options; "" means "omit".
    slots: list[list[str]] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w.startswith("["):
            # optional span, possibly multi-word: [THE SENSE]
            span = [w.strip("[]")]
            while not words[i].endswith("]"):
                i += 1
                span.append(words[i].strip("[]"))
            slots.append([" ".join(span), ""])
        elif "{" in w:
            stem, suffix = w.rstrip("}").split("{")
            if stem == "DO" and suffix == "ING":
                slots.append(["DO", "DOING"])
            else:  # A(N) -> A / AN
                slots.append([stem, stem + suffix])
        elif "/" in w:
            slots.append(w.split("/"))
        else:
            slots.append([w])
        i += 1
    seqs = []
    for combo in product(*slots):
        seq = " ".join(x for x in combo if x).lower().replace("’", "'")
        if seq and seq not in seqs:
            seqs.append(seq)
    return [s.split() for s in seqs], sense


POSS, REFL = "<poss>", "<refl>"
POSSESSIVES = {"my", "your", "his", "her", "its", "our", "their", "one's"}
REFLEXIVES = {
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "ourselves",
    "yourselves",
    "themselves",
    "oneself",
}
# Tokens whose tag separates the phrase from a look-alike: infinitival `to`
# (TO) vs preposition (IN); complementiser `that` (IN) vs determiner (DT/WDT).
# Particles: phrasal-verb particle (RP/RB) vs preposition (IN) — MAKE OUT is
# "make out what he said", not "made out of wood".
_PARTICLE_TAGS = ("RP", "RB", "IN")
CONSTRAINED = {
    "to": ("TO", "IN"),
    "that": ("IN", "DT", "WDT"),
    **{p: _PARTICLE_TAGS for p in ("out", "up", "off", "on", "down", "back", "away", "over", "in")},
}


def _slots(toks: list[str]) -> list[str]:
    """`one 's` -> <poss>, `oneself` -> <refl>: generic-person slots."""
    out: list[str] = []
    i = 0
    while i < len(toks):
        if toks[i] == "one" and i + 1 < len(toks) and toks[i + 1] == "'s":
            out.append(POSS)
            i += 2
            continue
        out.append(REFL if toks[i] == "oneself" else toks[i])
        i += 1
    return out


def main() -> None:
    nlp = spacy.load("en_core_web_sm", exclude=["ner"])
    data = json.loads(DATA.read_text("utf-8"))
    unmatched = []
    for item in data["items"]:
        seqs, sense = _alternatives(item["phrase"])
        variants = []
        for seq in seqs:
            toks = [t.lower_.replace("’", "'") for t in nlp.tokenizer(" ".join(seq))]
            variants.append(_slots(toks))
        item["variants"] = variants
        item["sense"] = sense

        # Find the phrase in its own example to read the tag of each `to`.
        ex = nlp(item.get("example") or "")
        lowers = [t.lower_.replace("’", "'") for t in ex]
        lemmas = [t.lemma_.lower() for t in ex]
        to_tags = None
        for var in sorted(variants, key=len, reverse=True):
            for start in range(len(ex) - len(var) + 1):
                if all(
                    lowers[start + k] == w
                    or lemmas[start + k] == w
                    or (w == POSS and lowers[start + k] in POSSESSIVES)
                    or (w == REFL and lowers[start + k] in REFLEXIVES)
                    for k, w in enumerate(var)
                ):
                    to_tags = {
                        w: ex[start + k].tag_
                        for k, w in enumerate(var)
                        if w in CONSTRAINED and ex[start + k].tag_ in CONSTRAINED[w]
                    }
                    break
            if to_tags is not None:
                break
        if to_tags is None:
            unmatched.append(item["phrase"])
        item["tags"] = to_tags or {}
        item.pop("to_tags", None)
    data["variants_note"] = (
        "variants/sense/to_tags compiled by scripts/build_data/build_phrase_index.py"
    )
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"compiled {len(data['items'])} items; {len(unmatched)} examples didn't contain their phrase"
    )
    for p in unmatched:
        print("  -", p)


if __name__ == "__main__":
    main()
