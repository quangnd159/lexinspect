"""lexinspect — local English text-analysis toolkit."""

__version__ = "0.1.0"

from lexinspect import awl, bnc_coca, diversity, ngsl, phrase, readability, tagger

__all__ = [
    "__version__",
    "readability",
    "diversity",
    "tagger",
    "awl",
    "bnc_coca",
    "ngsl",
    "phrase",
]
