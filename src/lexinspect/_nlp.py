"""spaCy pipeline: loaded once per process, parsing serialised.

Use `lexinspect._text.analyse()` rather than calling `parse()` directly — it
normalises the input and builds the shared word/sentence view every module
reads from.
"""

from __future__ import annotations

import threading
from functools import lru_cache

from spacy.language import Language

DEFAULT_MODEL = "en_core_web_sm"

# Named-entity recognition is ~40% of parse time and nothing reads it: proper
# nouns come from the tagger's NNP/NNPS. Excluded at load, not just disabled,
# so its weights never occupy memory.
_EXCLUDE = ("ner",)

# One `nlp` object is shared by every request in the process. Serverless hosts
# that pack concurrent requests into one instance run sync handlers on separate
# threads, and spaCy mutates a shared `Vocab`/`StringStore` while tokenising, so
# two threads parsing at once can race. Serialising costs nothing real: the
# instance has one vCPU, so the work was never going to overlap anyway.
_PARSE_LOCK = threading.Lock()


@Language.component("lexinspect_paragraph_breaks")
def _paragraph_breaks(doc):
    """Force a sentence boundary after every blank line.

    A heading, a bullet, or a list item without a full stop otherwise merges
    with the following sentence — a title line followed by a 20-word sentence
    became one 24-word "sentence", which skews every per-sentence average and
    every readability formula built on them. A single newline is *not* a
    boundary: text pasted from PDFs wraps mid-sentence.
    """
    for tok in doc[:-1]:
        if tok.is_space and tok.text.count("\n") >= 2:
            doc[tok.i + 1].is_sent_start = True
    return doc


@lru_cache(maxsize=2)
def get_nlp(model: str = DEFAULT_MODEL):
    import spacy

    try:
        nlp = spacy.load(model, exclude=list(_EXCLUDE))
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model}' is not installed. Reinstall dependencies: uv sync"
        ) from e
    _split_dashes(nlp)
    nlp.add_pipe("lexinspect_paragraph_breaks", before="parser")
    return nlp


# spaCy splits `word—word` but not `was—“impressively”—big` or `last”—then`:
# a quote beside the dash defeats its infix rules, and the whole run became one
# "word" (Study 3 found it in 53 of 300 texts, moving MTLD by up to 22%).
# Em and en dashes always separate words; so does a quote mark touching one.
# Apostrophes inside words (`don't`, `o'clock`) are untouched.
_DASH_INFIXES = (
    r"[—–]",
    r"(?<=[—–])[\"“”‘’]",
    r"[\"“”‘’](?=[—–])",
)


def _split_dashes(nlp) -> None:
    from spacy.util import compile_infix_regex

    infixes = list(nlp.Defaults.infixes) + list(_DASH_INFIXES)
    nlp.tokenizer.infix_finditer = compile_infix_regex(infixes).finditer


def parse(text: str):
    with _PARSE_LOCK:
        return get_nlp()(text)
