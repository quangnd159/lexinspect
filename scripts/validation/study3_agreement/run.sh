#!/usr/bin/env bash
# Study 3 end to end: fetch the texts, then compare lexinspect with textstat,
# TAALED, lexical-diversity and lexicalrichness. Writes
# docs/validation/study3-agreement.json and study3-agreement-per-text.csv.
#
#   bash scripts/validation/study3_agreement/run.sh
#
# Reference packages are pulled into a throwaway environment with `uv run
# --with`; pyproject.toml and uv.lock are untouched. setuptools<81 is needed
# because TAALED and pylats still import pkg_resources. textstat reads CMUdict
# through NLTK; NLTK_DATA points at the gitignored cache so a missing corpus is
# downloaded there rather than into the home directory.
set -euo pipefail
cd "$(dirname "$0")/../../.."

export NLTK_DATA="${NLTK_DATA:-$PWD/.cache/validation/study3/nltk_data}"
mkdir -p "$NLTK_DATA"

WITH=(
  --with "textstat==0.7.13"
  --with "taaled==0.32"
  --with "pylats==0.64"
  --with "lexical-diversity==0.1.1"
  --with "lexicalrichness==0.5.1"
  --with "pandas==3.0.6"
  --with "scipy==1.18.1"
  --with "setuptools<81"
)

uv run "${WITH[@]}" python -I -c "import nltk; nltk.download('cmudict', download_dir='$NLTK_DATA', quiet=True)"
uv run python -I scripts/validation/study3_agreement/fetch_texts.py
uv run "${WITH[@]}" python -I scripts/validation/study3_agreement/compare.py
uv run python -I scripts/validation/study3_agreement/diagnostics.py > /dev/null
