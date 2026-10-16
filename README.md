<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/lexinspect/static/logo-dark.png">
  <img src="src/lexinspect/static/logo.png" alt="lexinspect logo: a magnifying glass over a page of text" width="96" height="96">
</picture>

# lexinspect

[![Quality](https://github.com/quangnd159/lexinspect/actions/workflows/quality.yml/badge.svg)](https://github.com/quangnd159/lexinspect/actions/workflows/quality.yml) [![Licence: MIT (code)](https://img.shields.io/badge/licence-MIT%20(code)-blue)](#licence) ![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

**Try it: [lexinspect.dqnotes.com](https://lexinspect.dqnotes.com)**. Free, nothing to sign in to.

English text-analysis toolkit. CLI-first, JSON-out, with an HTTP API and a web app on top of the same code. Designed to be driven by AI agents (Claude Code, Claude Skills) as well as by people.

A free, self-hosted complement to commercial tools like Text Inspector. It reports readability (eight published formulas), lexical diversity, POS tags, vocabulary profiles against CEFR-J/Octanove, Nation's BNC/COCA families, NGSL/NAWL and the Academic Word List, Martinez & Schmitt's PHRASE list, Hyland's metadiscourse markers, and British/American spelling.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/quangnd159/lexinspect.git
cd lexinspect
uv sync --extra dev --extra web
```

The spaCy model `en_core_web_sm` 3.8 is a regular dependency (pinned to the release wheel in `pyproject.toml`), so `uv sync` installs it. Every word list, CMUdict and both Hunspell dictionaries are bundled; nothing is downloaded at runtime. Drop `--extra web` if you don't need `lexinspect serve` (it only adds uvicorn).

## Use

Every command takes a file path or `-` for stdin and emits JSON by default. Pass `--format human` for a terminal-friendly view.

```bash
# Every module over one shared parse
uv run lexinspect analyze passage.txt
uv run lexinspect analyze passage.txt --variant us   # American spelling for the errors module

# Individual modules
uv run lexinspect readability passage.txt
uv run lexinspect statistics passage.txt
uv run lexinspect diversity passage.txt
uv run lexinspect tag passage.txt            # --tokens for the per-token list
uv run lexinspect awl passage.txt
uv run lexinspect bnc-coca passage.txt
uv run lexinspect ngsl passage.txt
uv run lexinspect phrase passage.txt
uv run lexinspect cefr passage.txt
uv run lexinspect metadiscourse passage.txt
uv run lexinspect errors passage.txt --variant gb   # British (default)
uv run lexinspect errors passage.txt --variant us   # American

# Optional: CEFR text-level classifier (requires --extra cefr-level)
uv run lexinspect cefr-level passage.txt

# Pipe from anywhere
echo "The empirical analysis demonstrates significant variation." | uv run lexinspect analyze -
```

`profile` (per-word list data, below) has no command of its own; it is part of `analyze`.

Install globally so any project can call it:

```bash
uv tool install --editable .
lexinspect analyze passage.txt
```

## Output

Single-module commands emit this envelope:

```json
{
  "schema_version": "2",
  "module": "readability",
  "input": { "source": "passage.txt", "char_count": 693 },
  "result": { ... }
}
```

The HTTP endpoints add `input.word_count`. `analyze` (CLI and `/v1/analyze`) returns `"module": "analyze"`, `input.word_count` and `input.sentence_count`, and a `results` object keyed by module name. `/v1/analyze` also returns `input.normalised_text` when normalisation changed the text (see below).

`schema_version` is the contract downstream agents depend on. It is bumped only on changes that aren't purely additive; version 2 came with the shared tokenisation described next, which changed what the word, sentence and token counts mean.

## How text is read

Every module reads one shared analysis (`src/lexinspect/_text.py`, `analyse()`), so a word count on one tab is the word count on every tab.

- **Normalisation.** Input is converted to NFC; soft hyphens and zero-width characters are removed; exotic spaces become plain spaces. Every character `span` in the output indexes this normalised text.
- **Parse.** spaCy `en_core_web_sm` 3.8 with named-entity recognition excluded, run once per request. A blank line always ends a sentence, so a heading without a full stop doesn't merge into the next sentence. A single line break does not.
- **Words** are orthographic words: a contraction (`don't`), a hyphenated compound (`well-known`) and `cannot` are one word each. Numbers count as words; modules that leave them out say so.
- **Lexical tokens** are what the vocabulary profilers look up: the parts of each word without clitics (`n't`, `'ll`) or the possessive `'s`, without numbers, and without letter–digit codes such as `R²` or `CO2`. A hyphenated compound contributes its parts unless the list carries the whole compound.
- **Lookups** try the token's forms, then its British/American respelling (VarCon pairs in `data/spelling.json`, plus rules for regular patterns). An inflected verb is looked up by its lemma only, so `found` counts as *find* and `left` as *leave*. Dotted initialisms (`e.g.`, `i.e.`) match undotted list entries.

## Modules

### readability

Eight formulas, implemented here to their published definitions on lexinspect's own word, sentence and syllable counts: Flesch Reading Ease (Flesch 1948), Flesch–Kincaid Grade (Kincaid et al. 1975), Gunning Fog with Gunning's exclusions of proper nouns, hyphenated compounds and `-es`/`-ed`/`-ing` forms (Gunning 1952), SMOG (McLaughlin 1969), ARI (Senter & Smith 1967), Coleman–Liau with its 0.0588 coefficient (Coleman & Liau 1975), New Dale–Chall with its familiarity rules (Chall & Dale 1995) and Linsear Write. `text_standard` is the median of the eight grade equivalents (Flesch Reading Ease and the Dale–Chall raw score are converted to grades first).

Syllables come from CMUdict, then the word's British/American variant in CMUdict, then a CMUdict stem plus suffix, then a rule-based estimate (about 90% exact, over 99% within one syllable, measured against CMUdict). Numerals are syllabified as spoken (`1,500` = one thousand five hundred; `50%` = fifty per cent). Also returns counts, averages, reading time at 238 words per minute (Brysbaert 2019), and a `reliability` block: `reliable` is false under 100 words, and `notes` flags SMOG extrapolation under 30 sentences.

### statistics

Counts and ratios as Text Inspector's Statistics tab shows them: characters with and without spaces, words excluding numbers, unique types, sentences, syllables, polysyllabic words, and the ratios built from them. The numbers it excluded are listed in `excluded_digits`. Word numerals like `twenty` are words; digit tokens such as `2025`, `1.5`, `3rd` and `1990s` are excluded.

### diversity

TTR, RTTR, CTTR, MSTTR, MATTR, MTLD, HD-D, vocd-D, Herdan, Summer and Maas, implemented here over lexinspect's words (lowercased, numbers excluded). The formulas follow lexicalrichness, except that MSTTR now drops only an incomplete final segment, not every final segment. vocd-D follows McKee, Malvern & Richards (2000) and is seeded, so the same text always gets the same D.

The `references` block carries the two vocd-D ranges stated in Durán, Malvern, Richards & Chipere (2004): adult L2/ESL learners (D 40–70) and adult native academic writing (D 80–105). Each band reports `position` (`below`, `within` or `above`) for the text's vocd-D. Measures that can't be computed on a short text are `null`, and texts under 50 tokens carry a `note`.

### tagger

POS tagging with spaCy. Emits Penn Treebank tag counts (`JJ`, `NN`, `VBZ` ...) and Universal POS counts (`NOUN`, `VERB`, `ADJ` ...) over spaCy tokens. Add `--tokens` (API: `"include_tokens": true`) for the per-token list. The `summary` block (Text Inspector's Tagger Summary) counts words from the shared analysis: content words (excluding punctuation, numerals and symbols), types, type/token ratio, tokens per type, and per-sentence rates of verbal elements (PTB `VB*` and `MD`) and nominal elements (PTB `NN*`).

### awl

Coxhead Academic Word List (2000): 570 word families across 10 sublists, 3,111 forms. Reports per-sublist token and family counts, overall coverage, the families found, and `families_detail` with each family's sublist, token count and character spans.

### bnc-coca

Paul Nation's BNC/COCA lists: 25 bands of 1,000 word families (75,679 forms, every family member included), plus his supplementary lists of proper names, marginal words, transparent compounds and acronyms. A token takes its family's band, so `clearly` and `unclear` count under *clear* in the 1k band. Reports per-band tokens and families with a cumulative coverage curve. Proper nouns and supplementary-list tokens are counted separately from off-list words; `coverage_with_supplementary_pct` and `cumulative_coverage_with_supplementary_pct` treat them as known, as Nation's convention does. Off-list and proper-noun words are listed with counts.

### ngsl

New General Service List 1.2 (2,809 lemmas; the "lemmatized for teaching" version, with inflections and UK/US forms) and New Academic Word List 1.2 (959 lemmas), by Browne, Culligan and Phillips. A token is NGSL if it is on NGSL, else NAWL, else a proper noun, else off-list. Reports NGSL, NAWL and combined coverage, the lemmas found, `nawl_words` with counts, proper nouns and the off-list words.

### phrase

Martinez & Schmitt (2012) PHRASE list: 506 phrasal expressions across K1–K5. Each entry's printed form is compiled at build time into its actual variants (`THERE IS/ARE` into *there is* and *there are*; `A BIT (OF)` with and without *of*; `ONE'S` as a possessive slot). Matching is inflection-aware (`dealt with` matches DEAL WITH), takes the longest non-overlapping match, and never crosses punctuation. Where an entry's own example shows `to` as infinitival or prepositional, `that` as complementiser or determiner, or a particle as adverbial rather than prepositional, the text must agree: "going to the park" is not GOING TO (FUTURE). Each hit has its band, sense, character span, and `also_possible` when another sense of the same form also fits.

### cefr

CEFR vocabulary profile (A1–C2) from CEFR-J Vocabulary Profile 1.5 (Tono, TUFS; A1–B2) and Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs, CC BY-SA 4.0). 8,845 headwords. Levels are per part of speech: *present* is A1 as a noun and B2 as a verb, and the token's spaCy tag decides which applies. Where the source has no level for that part of speech, the word's lowest level is used and the token is counted in `pos_fallback_tokens`. Reports per-level tokens and lemmas, cumulative coverage, `words_by_level`, `highest_level_present`, `dominant_level`, and `estimated_level_95th` (the lowest level at which coverage, counting proper nouns as known, reaches 95%). Proper nouns are counted separately from off-list words. **Not the Cambridge English Vocabulary Profile**: the corpora and methodology differ; cite CEFR-J and Octanove in any output.

### metadiscourse

Hyland (2005) metadiscourse markers in 10 categories across two dimensions: *interactive* (transitions, frame markers, endophoric markers, evidentials, code glosses) and *interactional* (hedges, boosters, attitude markers, engagement markers, self-mentions). 490 markers. A listed marker counts only when it passes a context rule on the parse: `and`/`but`/`so` only when joining clauses or opening a sentence, `table` only with a reference (`Table 2`), reporting verbs only with a clausal complement, `clear` only predicatively, `about` only before a number, and so on (the full list is in the module docstring). Each hit lands in exactly one category and lists any other categories the marker belongs to in `also_listed_as`. Reports densities per 1,000 words overall, per dimension and per category, and every hit with its character span.

### errors

Spelling check with Hunspell (via [spylls](https://github.com/zverok/spylls)) and the bundled LibreOffice en_GB / en_US dictionaries, chosen with `--variant gb|us` (default `gb`). Whole words are checked, so contractions, possessives and hyphenated compounds are judged as written. Rejected words are split into three groups:

- `errors`: not a word in either variety. These count toward `errors_per_sentence` and `errors_per_100_words`. Each comes with suggestions from a fast edit-distance search over BNC/COCA and NGSL forms, filtered to words valid in the chosen variety.
- `variant_mismatches`: correct in the other variety (`color` in British mode), with the respelling for the chosen one.
- `unknown_names`: capitalised words used as names, and all-capitals acronyms.

Words containing digits, URLs, email addresses and short abbreviations with a full stop (`e.g.`, `Dr.`) are not checked.

### profile

One row per lexical token: `[start, end, cefr, bnc, awl, ngsl]`, returned as a column table (`columns` plus `rows`) to keep large texts compact. `cefr` is a level, `"proper"` or null; `bnc` is a band 1–25, `"proper"`, `"supplementary"` or null; `awl` is a sublist or null; `ngsl` is `"ngsl"`, `"nawl"`, `"proper"` or null. Each value comes from the same lookup the list module makes, so a word highlighted as B2 is the word counted under B2. The web UI's in-text highlighting reads this.

### cefr-level (optional extra)

CEFR text-level classification (A1–C2) via UniversalCEFR `ModernBERT-base-cefr-all-classifier` (Imperial et al., EMNLP 2025; Apache 2.0). Returns a single CEFR band, a confidence value, the full per-level distribution, and the top two levels for borderline detection. Distinct from `cefr`: that module profiles vocabulary; this one returns a judgement from a transformer fine-tuned on the UniversalCEFR corpus.

Install with `uv sync --extra cefr-level` (adds `transformers` and `torch`). The first call downloads the model into the Hugging Face cache; later calls reuse the in-memory pipeline. Lazy-loaded, so the rest of lexinspect works without the extra. Not part of `analyze` because of the cost; call it explicitly. Treat the output as an estimate; see CAVEATS.md and the in-output `caveat` field.

## Serve as HTTP API and web UI

```bash
uv run lexinspect serve                # 127.0.0.1:8000, open / in a browser
uv run lexinspect serve --port 9000 --reload
```

Endpoints:

```
GET  /                   web UI (HTML shell + /static/*)
GET  /licences           data sources and licences
GET  /comparison         side-by-side comparison with Text Inspector
POST /v1/readability     {"text": "...", "source": "passage"}
POST /v1/statistics      (same body shape on every endpoint)
POST /v1/diversity
POST /v1/tag             (+ "include_tokens": true for the per-token list)
POST /v1/awl
POST /v1/bnc-coca
POST /v1/ngsl
POST /v1/phrase
POST /v1/cefr
POST /v1/metadiscourse
POST /v1/errors          (+ "variant": "gb" | "us")
POST /v1/cefr-level      (optional extra; 503 if not installed)
POST /v1/analyze         all twelve modules (+ "variant", + "modules": [...] for a subset)
GET  /v1/version
GET  /v1/schema          schema_version, module list, optional-module availability, limits, Turnstile site key
GET  /healthz
GET  /docs               Swagger UI
```

`/v1/analyze` runs readability, statistics, diversity, tagger, awl, bnc_coca, ngsl, phrase, cefr, metadiscourse, errors and profile. Requests over 50 KB of text (`LEXINSPECT_MAX_TEXT_BYTES`) get a 413. Responses over 2 KB are gzipped. CORS is open by default; set `LEXINSPECT_ALLOWED_ORIGINS` to a comma-separated list to restrict it. The app loads spaCy, CMUdict, the word lists and both dictionaries at startup (about a second), so the first request doesn't pay for them.

The web UI shows the analysed text with findings highlighted in place, one lens at a time: Spelling, CEFR, Frequency, Academic, NGSL, Phrases, Metadiscourse. Lenses are linked to the analysis tabs; hovering a word shows what each list says about it, clicking an item in a tab locates it in the text, and spelling suggestions apply with one click and re-analyse. It also has a UK/US toggle, sample texts, JSON copy and download, and follows the system's light or dark setting.

## Deployment

Hosted at `lexinspect.dqnotes.com` (also `lexinspect.vercel.app`). GitHub Actions builds with `vercel build` and deploys with `vercel deploy --prebuilt`. The Python function is `api/index.py`; `vercel.json` rewrites `/v1/*`, `/docs`, `/openapi.json` and `/healthz` to it. CI copies `src/lexinspect/static/` into `public/`, so the web UI is served from the CDN without invoking the function. The hosted build omits the `cefr-level` extra; `/v1/schema` reports that, and the UI hides the classifier.

The hosted API is for the web UI. Every POST under `/v1/` passes a Cloudflare Turnstile check: the page runs an invisible challenge (a click only when Cloudflare is unsure), sends the token in the `CF-Turnstile-Response` header, and gets an hour-long signed `lexinspect_pass` cookie so later analyses skip it. Set `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` in the Vercel project's Production environment to turn it on (preview deployments sit behind Vercel's login instead, and their hostnames aren't on the Turnstile widget); with neither set, as in local runs, tests and self-hosted copies, the API is open. Scripts and notebooks should run lexinspect themselves: the package, the CLI or `lexinspect serve`. The WAF rate limit (60 POSTs/min/IP on `/v1/`) stays in front of everything.

## Develop

```bash
uv run pytest                 # ~500 tests
uv run ruff check .
uv run ruff format .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose changes and [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

The web UI is framework-free with no build step. `src/lexinspect/static/` holds `index.html`, `licences.html`, `styles.css` and six scripts for the app: `dom.js` (DOM and formatting helpers), `human.js` (the Turnstile check, loaded only when the server has a site key), `copy.js` (explanatory text and samples), `reader.js` (the highlighted text and lenses), `panels.js` (one renderer per tab) and `app.js` (editor, requests, wiring). The comparison page has its own `comparison.html`, `comparison.css` and `comparison.js`, with its evidence files under `comparison/`. Locally, FastAPI serves the directory at `/static/`.

Data refresh: see `scripts/build_data/README.md`.

## Validity and caveats

[VALIDITY.md](VALIDITY.md) says what each number is for and not for, and what evidence stands behind it: the research on each measure, and lexinspect's own validation studies. lexinspect is for teaching, materials work, research description and diagnosis, not for high-stakes decisions about people.

[CAVEATS.md](CAVEATS.md) catalogues the known limitations and conscious trade-offs, per module, transport and operations.

## Licence

Code: MIT ([LICENSE](LICENSE)). The MIT licence does not cover the bundled data files: each keeps its creators' terms, several are CC BY-SA 4.0, and the AWL, PHRASE and metadiscourse lists are for educational and research use only. See [src/lexinspect/data/LICENSE.md](src/lexinspect/data/LICENSE.md) for a per-file summary and [SOURCES.md](src/lexinspect/data/SOURCES.md) for full provenance. Cite the original creators in any publication.
