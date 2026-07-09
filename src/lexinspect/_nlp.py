"""Lazy spaCy pipeline loader. The model loads once per process."""

from __future__ import annotations

import threading
from functools import lru_cache

DEFAULT_MODEL = "en_core_web_sm"

# One `nlp` object is shared by every request in the process. Serverless hosts
# that pack concurrent requests into one instance run our sync handlers on
# separate threads, and spaCy mutates a shared `Vocab`/`StringStore` while
# tokenising, so two threads parsing at once can race. Serialising parses costs
# us nothing real: the box has a single vCPU, so the work was never going to
# overlap anyway.
_PARSE_LOCK = threading.Lock()


@lru_cache(maxsize=2)
def get_nlp(model: str = DEFAULT_MODEL):
    import spacy

    try:
        return spacy.load(model)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model '{model}' is not installed. Run:\n"
            f"  uv run python -m spacy download {model}"
        ) from e


def get_doc(text: str, doc=None):
    """Return `doc` if the caller already parsed `text`, else parse it.

    Every module used to parse independently, so `/v1/analyze` ran the whole
    pipeline once per module — nine times over identical input, and the parse
    dominates each module's cost. Callers that need several modules parse once
    and thread the `Doc` through.
    """
    if doc is not None:
        return doc
    with _PARSE_LOCK:
        return get_nlp()(text)
