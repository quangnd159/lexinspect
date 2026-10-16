"""lexinspect — English text-analysis toolkit: CLI, HTTP API, and hosted web app."""

__version__ = "0.3.0"

from lexinspect import (
    awl,
    bnc_coca,
    cefr,
    cefr_level,
    diversity,
    errors,
    metadiscourse,
    ngsl,
    phrase,
    readability,
    statistics,
    tagger,
)

__all__ = [
    "__version__",
    "readability",
    "statistics",
    "diversity",
    "tagger",
    "awl",
    "bnc_coca",
    "ngsl",
    "phrase",
    "cefr",
    "cefr_level",
    "metadiscourse",
    "errors",
]
