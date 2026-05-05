"""Lazy spaCy pipeline loader. The model loads once per process."""

from __future__ import annotations

from functools import lru_cache

DEFAULT_MODEL = "en_core_web_sm"


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
