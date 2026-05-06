# lexinspect

Local English text-analysis toolkit. CLI-first, JSON-out, designed to be driven by AI agents (Claude Code, Claude Skills) and to graduate to a FastAPI web app without rewriting.

A free, self-hosted complement to commercial tools like Text Inspector. Phase 1 covers four analysis families: readability statistics, lexical diversity, POS tagging, and Coxhead Academic Word List profiling. Future phases add CEFR vocabulary profiling, BNC/COCA frequency banding, phrasal expression detection, and metadiscourse markers.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:quangnd159/lexinspect.git
cd lexinspect
uv sync --extra dev --extra web
uv pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

Drop `--extra web` if you only need the CLI. Note that any future `uv sync` rebuilds the venv from the lockfile and drops the spaCy model — re-run the wheel install line if that happens.

## Use

Every command takes a file path or `-` for stdin and emits JSON by default. Pass `--format human` for a terminal-friendly view.

```bash
# All ten modules at once
uv run lexinspect analyze passage.txt

# Individual modules
uv run lexinspect readability passage.txt
uv run lexinspect statistics passage.txt
uv run lexinspect diversity passage.txt
uv run lexinspect tag passage.txt
uv run lexinspect awl passage.txt
uv run lexinspect bnc-coca passage.txt
uv run lexinspect ngsl passage.txt
uv run lexinspect phrase passage.txt
uv run lexinspect cefr passage.txt
uv run lexinspect metadiscourse passage.txt

# Optional: CEFR text-level classifier (requires --extra cefr-level)
uv run lexinspect cefr-level passage.txt

# Optional: spelling errors (requires --extra errors)
uv run lexinspect errors passage.txt --variant gb   # British (default)
uv run lexinspect errors passage.txt --variant us   # American

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

### statistics

Counts and ratios broken out as discrete fields: characters with/without spaces, sentence count, token count excluding pure-numeric tokens, unique types, syllable count, polysyllable-word count, plus the ratios Text Inspector surfaces on its Statistics tab — tokens per sentence, type/token ratio, syllables per word, syllables per sentence, syllables per 100 words, polysyllable percentage. Also reports the list of numeric tokens that were excluded (`excluded_digits`). Word numerals like `twenty` are kept as words; pure digit tokens like `2025` and `1.5` are excluded — matching Text Inspector's convention.

### diversity

Wraps [lexicalrichness](https://github.com/LSYS/LexicalRichness). Returns TTR, RTTR, CTTR, MSTTR, MATTR, MTLD, HD-D, Herdan, Summer, and Maas. MTLD and HD-D are the most reliable cross-text-length measures.

The `references` block surfaces the two published vocd-D reference ranges from Durán, Malvern, Richards & Chipere (2004) — Adult L2/ESL learner (D 40–70) and Adult native academic writing (D 80–105) — for awareness only. lexinspect (via lexicalrichness) computes **HD-D** (a hypergeometric probability bounded 0–1), not Durán's vocd-D (scale ~30–150). The two are rank-correlated but on different numeric scales, so direct comparison isn't valid; no auto-comparison is performed. Implementing vocd-D properly via the McKee/Malvern/Richards 2000 sub-sample procedure is a fair Phase-7 follow-up. Per-age longitudinal cohort bands shown on Text Inspector's "Bristol Charts" sit in separate typeset figures not in the manuscript text, so they aren't bundled either.

### tagger

POS tagging via spaCy (`en_core_web_sm`). Emits Penn Treebank tag counts (`JJ`, `NN`, `VBZ` ...) and Universal POS counts (`NOUN`, `VERB`, `ADJ` ...). Add `--tokens` to include the per-token list. The `summary` block aggregates the same numbers Text Inspector shows on its Tagger Summary tab — content tokens (excluding punctuation, numerals, symbols), unique types, type/token ratio, tokens per type, plus per-sentence rates of verbal elements (PTB `VB*`) and nominal elements (PTB `NN*`).

### awl

Coxhead Academic Word List (2000) coverage profile. Bundles 570 head words across 10 sublists, indexed by 3,111 inflected forms. Reports per-sublist token and family counts, overall coverage percentage, and the unique families found.

### bnc-coca

Nation BNC/COCA frequency-band profile. Bundles 9,998 head words across the first 10 thousand-word bands (CC0 mirror, headwords only — see [data/SOURCES.md](src/lexinspect/data/SOURCES.md) for the trade-off). Reports per-band tokens, headwords found, and a cumulative coverage curve — the standard ELT readout for "what proportion of this text is within the first N thousand words?".

### ngsl

NGSL + NAWL combined coverage (Browne, Culligan, Phillips). NGSL 1.2 covers ~92% of general English with 2,809 lemmas; NAWL 1.2 adds 959 academic lemmas for use after NGSL. Reports separate NGSL and NAWL coverage percentages plus the off-list residual.

### phrase

Martinez & Schmitt (2012) PHRASE list — 506 phrasal expressions across K1–K5 frequency bands. Detects multi-word spans (`HAVE TO`, `IN SPITE OF`, `ON THE OTHER HAND`) with verb-inflection tolerance, returning surface span, base form, rank, and band.

### cefr

CEFR vocabulary profile (A1–C2). Combines CEFR-J Vocabulary Profile 1.5 (Tono, TUFS — A1 to B2) with Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs, CC-BY-SA 4.0 — C1 and C2). 8,690 lemmas total. Reports per-level token and lemma counts, cumulative coverage, dominant level, and a 95th-percentile heuristic level. **Not Cambridge EVP** — the underlying corpora and methodology differ; cite CEFR-J + Octanove in any output.

### cefr-level (optional extra)

CEFR text-level classification (A1–C2) via UniversalCEFR `ModernBERT-base-cefr-all-classifier` (Imperial et al., EMNLP 2025; Apache 2.0). Returns a single CEFR band, a confidence value, the full per-level distribution, and the top-2 levels for borderline detection. Distinct from the `cefr` module: where `cefr` reports a vocabulary-coverage curve plus a 95th-percentile heuristic, `cefr-level` returns a *judgement* from a transformer fine-tuned on the 505k-text UniversalCEFR corpus.

Heavy extra. Install with `uv sync --extra cefr-level` (adds `transformers` + `torch`). First call downloads ~400MB into the HuggingFace cache; subsequent calls reuse the in-memory pipeline. CPU inference is ~2–5s per text. Lazy-loaded — the rest of lexinspect works without the extra.

Not bundled into `analyze` because of the cost; call it explicitly:

```bash
uv run lexinspect cefr-level passage.txt
```

Treat the output as an estimate. The same five caveats Text Inspector publishes for its Lexical Profile© apply to every CEFR classifier — see CAVEATS.md and the in-output `caveat` field.

### errors (optional extra)

Spelling-error detection via [spylls](https://github.com/zverok/spylls), a pure-Python port of Hunspell. Reports total errors, errors per sentence, errors per 100 words, and the deduplicated list of flagged tokens — the same shape Text Inspector's Errors tab produces. British (default) and American variants via `--variant gb|us`.

Install with `uv sync --extra errors` (adds `spylls`). The first call per variant downloads the LibreOffice English Hunspell dictionary (~1.5 MB combined) into `~/.cache/lexinspect/hunspell/`; subsequent calls reuse the cached files. Dictionaries: Kevin Atkinson's LGPL wordlist + Geoff Kuenning's BSD affix file.

Not bundled into `analyze` — like `cefr-level`, it requires opt-in installation. Call it explicitly:

```bash
uv run lexinspect errors passage.txt --variant gb
```

### metadiscourse

Hyland (2005) metadiscourse marker detection — 10 categories across two dimensions: *interactive* (transitions, frame markers, endophoric markers, evidentials, code glosses) and *interactional* (hedges, boosters, attitude markers, engagement markers, self-mentions). 490 markers total. Hedges are a verbatim Hyland 2005 Appendix A mirror (HLTCHKUST); the other nine categories are a curated reference subset from canonical reproductions in the L2 academic-writing literature. Reports density per 1,000 content tokens, per-category and per-dimension hits, and the full hit list with token positions.

## Serve as HTTP API + web UI

Same JSON envelope, same ten modules, exposed over HTTP for browsers, agents, or future Skills that prefer a network call to a subprocess. The same server also ships a clean single-file web UI at `/` — paste text, hit Analyze, see all nine modules in tabbed views with bar charts, hit lists, and key-stat chips.

```bash
uv run lexinspect serve                # 127.0.0.1:8000 — open / in a browser
uv run lexinspect serve --port 9000 --reload
```

Endpoints:

```
GET  /                   web UI (HTML shell + /static/{styles.css, *.js})
POST /v1/readability     {"text": "...", "source": "passage"}
POST /v1/statistics      (same body shape on every endpoint)
POST /v1/diversity
POST /v1/tag             (+ "include_tokens": true to get per-token list)
POST /v1/awl
POST /v1/bnc-coca
POST /v1/ngsl
POST /v1/phrase
POST /v1/cefr
POST /v1/cefr-level     (optional; requires the cefr-level extra; 503 if missing)
POST /v1/errors         (optional; requires the errors extra; body: {text, variant?})
POST /v1/metadiscourse
POST /v1/analyze         all ten modules in one response
GET  /v1/version
GET  /v1/schema          schema_version + module catalog
GET  /healthz
GET  /docs               auto-generated Swagger UI
```

Interactive docs at `http://127.0.0.1:8000/docs` (FastAPI auto-generates Swagger UI). Request body cap is 1 MB; CORS is open by default. Each worker holds spaCy in memory — `--workers N` if you need more parallelism. For production, put it behind a real reverse proxy and tighten CORS.

## Develop

```bash
uv run pytest                 # ~90 tests
uv run ruff check .
uv run ruff format .
```

The web UI is intentionally framework-free. `src/lexinspect/static/` ships the HTML shell, a stylesheet, and four JS files split by concern: `metric-info.js` (data: chip metadata, tab intros, fixtures), `ui-helpers.js` (DOM helpers — `el`, `kvTable`, `barChart`, `fmtNum`), `renderers.js` (one `render*` function per tab), and `app.js` (event wiring + the top-level orchestrator). FastAPI serves the directory at `/static/` via a standard mount; no build step.

Data refresh: see `scripts/build_data/README.md`.

## Caveats and improvement opportunities

`CAVEATS.md` at the repo root catalogues every conscious trade-off — per module, transport, and ops — with concrete upgrade paths. Read it before basing high-stakes decisions on lexinspect output.

## Roadmap

- **Phase 2** (done): BNC/COCA, NGSL + NAWL, Martinez–Schmitt PHRASE list.
- **Phase 3** (done): CEFR profiling via CEFR-J 1.5 + Octanove C1/C2 1.0.
- **Phase 4** (done): Metadiscourse markers (Hyland 2005 10-category framework).
- **Phase 5** (done): FastAPI wrapper. Same envelope as the CLI.

The analytical surface is complete. Next moves are application-layer: write Skills that pipe `lexinspect analyze` into specific workflows (IELTS reading-passage profiling, exam-writing checks, materials grading), or build a thin browser frontend on the API.

## Licence

Code: MIT. Bundled data files have their own provenance and licences — see [src/lexinspect/data/SOURCES.md](src/lexinspect/data/SOURCES.md). Cite original creators in any publication.
