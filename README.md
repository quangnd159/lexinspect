# lexinspect

Local English text-analysis toolkit. CLI-first, JSON-out, designed to be driven by AI agents (Claude Code, Claude Skills) and to graduate to a FastAPI web app without rewriting.

A free, self-hosted complement to commercial tools like Text Inspector. Phase 1 covers four analysis families: readability statistics, lexical diversity, POS tagging, and Coxhead Academic Word List profiling. Future phases add CEFR vocabulary profiling, BNC/COCA frequency banding, phrasal expression detection, and metadiscourse markers.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:quangnd159/lexinspect.git
cd lexinspect
uv sync --extra dev
uv pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

## Use

Every command takes a file path or `-` for stdin and emits JSON by default. Pass `--format human` for a terminal-friendly view.

```bash
# All seven modules at once
uv run lexinspect analyze passage.txt

# Individual modules
uv run lexinspect readability passage.txt
uv run lexinspect diversity passage.txt
uv run lexinspect tag passage.txt
uv run lexinspect awl passage.txt
uv run lexinspect bnc-coca passage.txt
uv run lexinspect ngsl passage.txt
uv run lexinspect phrase passage.txt

# Pipe from anywhere
echo "The empirical analysis demonstrates significant variation." | uv run lexinspect analyze -
```

Install globally so any project can call it:

```bash
uv tool install --editable .
lexinspect analyze passage.txt
```

## Output

Every command emits the same envelope shape:

```json
{
  "schema_version": "1",
  "module": "readability",
  "input": { "source": "passage.txt", "char_count": 693 },
  "result": { ... }
}
```

`schema_version` is the contract downstream agents depend on. Bumped only on breaking changes.

## Modules

### readability

Wraps [textstat](https://github.com/textstat/textstat). Returns counts (characters, words, syllables, sentences, mono/poly-syllable, long words, reading time), averages, and nine readability scores: Flesch Reading Ease, Flesch–Kincaid Grade, Gunning Fog, SMOG, ARI, Coleman-Liau, Dale-Chall, Linsear Write, and a consensus `text_standard`.

### diversity

Wraps [lexicalrichness](https://github.com/LSYS/LexicalRichness). Returns TTR, RTTR, CTTR, MSTTR, MATTR, MTLD, HD-D, Herdan, Summer, and Maas. MTLD and HD-D are the most reliable cross-text-length measures.

### tagger

POS tagging via spaCy (`en_core_web_sm`). Emits Penn Treebank tag counts (`JJ`, `NN`, `VBZ` ...) and Universal POS counts (`NOUN`, `VERB`, `ADJ` ...). Add `--tokens` to include the per-token list.

### awl

Coxhead Academic Word List (2000) coverage profile. Bundles 570 head words across 10 sublists, indexed by 3,111 inflected forms. Reports per-sublist token and family counts, overall coverage percentage, and the unique families found.

### bnc-coca

Nation BNC/COCA frequency-band profile. Bundles 9,998 head words across the first 10 thousand-word bands (CC0 mirror, headwords only — see [data/SOURCES.md](src/lexinspect/data/SOURCES.md) for the trade-off). Reports per-band tokens, headwords found, and a cumulative coverage curve — the standard ELT readout for "what proportion of this text is within the first N thousand words?".

### ngsl

NGSL + NAWL combined coverage (Browne, Culligan, Phillips). NGSL 1.2 covers ~92% of general English with 2,809 lemmas; NAWL 1.2 adds 959 academic lemmas for use after NGSL. Reports separate NGSL and NAWL coverage percentages plus the off-list residual.

### phrase

Martinez & Schmitt (2012) PHRASE list — 506 phrasal expressions across K1–K5 frequency bands. Detects multi-word spans (`HAVE TO`, `IN SPITE OF`, `ON THE OTHER HAND`) with verb-inflection tolerance, returning surface span, base form, rank, and band.

## Develop

```bash
uv run pytest                 # 41 tests
uv run ruff check .
uv run ruff format .
```

## Roadmap

- **Phase 2** (done): BNC/COCA, NGSL + NAWL, Martinez–Schmitt PHRASE list.
- **Phase 3**: CEFR profiling via CEFR-J Wordlist + Octanove C1/C2 (Open Language Profiles). Outputs band distribution; no single-number "score" — agents combine the components themselves.
- **Phase 4**: Metadiscourse marker detection (Hyland taxonomy).
- **Phase 5**: Optional FastAPI wrapper exposing the same functions over HTTP.

## Licence

Code: MIT. Bundled data files have their own provenance and licences — see [src/lexinspect/data/SOURCES.md](src/lexinspect/data/SOURCES.md). Cite original creators in any publication.
