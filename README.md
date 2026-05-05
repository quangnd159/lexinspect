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
# All four modules at once
uv run lexinspect analyze passage.txt

# Individual modules
uv run lexinspect readability passage.txt
uv run lexinspect diversity passage.txt
uv run lexinspect tag passage.txt
uv run lexinspect awl passage.txt

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

## Develop

```bash
uv run pytest                 # 25 tests
uv run ruff check .
uv run ruff format .
```

## Roadmap

- **Phase 2**: Nation BNC/COCA family-list profiling, NGSL/NAWL, Martinez–Schmitt PHRASE list.
- **Phase 3**: CEFR profiling via CEFR-J Wordlist + Octanove C1/C2 (Open Language Profiles). Outputs band distribution; no single-number "score" — agents combine the components themselves.
- **Phase 4**: Metadiscourse marker detection (Hyland taxonomy).
- **Phase 5**: Optional FastAPI wrapper exposing the same functions over HTTP.

## Licence

MIT. The bundled AWL data derives from Coxhead, A. (2000). *A new academic word list*. TESOL Quarterly, 34(2), 213–238 — cite accordingly in any publication.
