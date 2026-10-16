#!/usr/bin/env bash
# Study 2 end to end: downloads the treebanks into .cache/validation/study2/ if
# absent, tags them with en_core_web_sm and en_core_web_trf, and writes
# docs/validation/study2-tagger.json. en_core_web_trf (and PyTorch) come from an
# ephemeral `uv run --with` environment; pyproject.toml and uv.lock are untouched.
set -euo pipefail
cd "$(dirname "$0")/../../.."
TRF="en_core_web_trf @ https://github.com/explosion/spacy-models/releases/download/en_core_web_trf-3.8.0/en_core_web_trf-3.8.0-py3-none-any.whl"
exec uv run --with "$TRF" python -I scripts/validation/study2_tagger/study2.py "$@"
