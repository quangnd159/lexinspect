"""Environment defaults that must be set before third-party imports.

Two of our dependencies reach for the network or the home directory the first
time they are used. Both are fine on a laptop and both bite on a read-only,
ephemeral serverless filesystem, where they showed up as HTTP 500s and
eleven-second requests in production. Import this module before `textstat` or
anything that pulls in `matplotlib`.

Nothing here overrides an operator who has already set these variables.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _bundled_nltk_data() -> str | None:
    """Path to the vendored nltk corpora, or None if absent.

    Deliberately `__file__`-relative rather than `importlib.resources.as_file`:
    for a directory that helper copies to a temp location and deletes it when
    its context manager exits, so the path handed to nltk pointed at nothing.
    lexinspect always installs as real files, never zipimported, so the plain
    path is both correct and cheaper.
    """
    candidate = Path(__file__).parent / "data" / "nltk_data"
    if (candidate / "corpora" / "cmudict.zip").is_file():
        return str(candidate)
    return None


def configure() -> None:
    # textstat asks nltk for the CMU Pronouncing Dictionary to count syllables.
    # nltk's answer, if it isn't on disk, is to download it — at request time,
    # into $HOME. On a serverless host $HOME is read-only, the download lands in
    # a temp dir that dies with the instance, and concurrent requests race each
    # other extracting the archive: "[nltk_data] Extraction error for
    # cmudict/cmudict", then a 500. We ship the corpus and point nltk at it.
    if "NLTK_DATA" not in os.environ:
        bundled = _bundled_nltk_data()
        if bundled is not None:
            os.environ["NLTK_DATA"] = bundled

    # matplotlib (pulled in by lexicalrichness, which we only use for diversity
    # metrics) builds a font cache on first import. With no writable config dir
    # it rebuilds every time a new instance starts — "generated new fontManager",
    # ~11 s. Give it somewhere to write so it pays that once per instance.
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "lexinspect-mpl"))


configure()
