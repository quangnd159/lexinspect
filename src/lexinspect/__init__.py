"""lexinspect — English text-analysis toolkit: CLI, HTTP API, and hosted web app."""

__version__ = "0.1.0"

# Must precede every other import: it points nltk at the bundled CMU dictionary
# and gives matplotlib a writable cache dir, before either gets imported and
# decides to fetch from the network or write to a read-only home. Plain `import`
# rather than `from`, so import sorting keeps it above the submodules.
import lexinspect._env  # noqa: F401  (side effect; must stay first)
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
