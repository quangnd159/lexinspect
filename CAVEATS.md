# Caveats and improvement opportunities

What lexinspect doesn't do well today, and where to look first if you decide to fix it. Organised per module, then transport, then ops. Honest framing: most caveats are conscious trade-offs (licence cleanliness, scope, time), not bugs. None are blockers for ELT or IELTS work — they're flags for when you push harder.

## readability

**Syllable counter has known errors on rare words.** textstat falls back to Pyphen for syllabification, which is dictionary-based and will mis-count technical, medical, or low-frequency vocabulary. Affects FK Grade and Gunning Fog at the margins on jargon-dense texts. Upgrade path: Carnegie Mellon Pronouncing Dictionary (`cmudict` PyPI package) for the words it covers, fall back to Pyphen.

**`text_standard` is a consensus heuristic, not validated.** textstat picks the median grade from the seven scores and rounds — useful for quick triage, not for high-stakes placement.

**Reading-time formula is a single fixed ms-per-character constant.** Doesn't model genre, density, or reader proficiency. If you need a real reading-time estimate, use words-per-minute by reader level instead.

## diversity

**vocd-D / HD-D are sample-size dependent.** Both fail or wobble on texts under ~50 tokens. The module returns `None` for failed metrics rather than a bad number, but downstream code should check. Exact floors: `hdd` needs 42 tokens (its `draws`), `mattr` 50 (its window), `msttr` 51.

**MTLD used to be the exception, and it lied.** Unlike the others it never raises — its factor-count fallback always returns a number — so on short text it produced confident nonsense (twelve all-unique words scored 12.0, which reads as maximally repetitive when it is maximally diverse) while the UI promised the module returns nothing rather than a misleading value. It is now suppressed below `MIN_TOKENS_MTLD` (50), and short results carry a `note`. `Herdan`/`Summer`/`Maas` are likewise guarded: a text with one distinct type made `log(types)` zero and raised, which was a live HTTP 500.

**MTLD threshold is fixed at 0.72 (the published default).** Some research uses 0.71 or 0.5 — if you're matching a specific paper, expose `threshold` as a parameter.

**lexinspect computes HD-D, not vocd-D.** The `references.vocd_d_bands` block bundles the two published vocd-D ranges from Durán, Malvern, Richards & Chipere 2004 (Adult L2/ESL D 40–70, Adult native academic D 80–105) for **awareness only**. The library we wrap (`lexicalrichness`) exposes HD-D — bounded 0–1, McCarthy & Jarvis 2007 — not vocd-D. The two are highly rank-correlated but on completely different numeric scales, so a direct numeric comparison would be wrong, and no auto-comparison is performed. To do a real vocd-D vs. reference comparison, implement vocd-D via the McKee/Malvern/Richards 2000 sub-sample TTR curve-fitting procedure — a Phase-7 follow-up worth about a day's work.

**Per-age cohort bands aren't bundled.** Text Inspector's "Bristol Charts" show vocd-D bands for nine cohorts (18, 24, 30, 36, 42, 60 months + 6+ MFL French + Adult ESL + Academic). Only the Adult ESL and Academic bands are stated explicitly in the paper's freely-available abstract; the per-age figures sit in separate typeset images of Durán et al. 2004 that the public manuscript doesn't include. Until those numbers can be sourced cleanly, lexinspect bundles only the two ranges it can cite verbatim.

**MTLD has no reference bands bundled.** McCarthy & Jarvis 2010 give genre-stratified ranges that could be added later.

## tagger

**Uses `en_core_web_sm` for speed.** The small model is ~12MB and fast but ~2 percentage points less accurate than `en_core_web_lg` (~750MB) on tag accuracy. Acceptable for ELT work; swap to `lg` if you start using lexinspect for syntactic-complexity analysis where one mis-tagged token cascades.

**No syntactic parsing exposed.** spaCy's dependency parser runs by default but the module only emits POS counts. Adding `spacy_parse` or surfacing dependency relations would unlock L2 Syntactic Complexity Analyzer (Lu)-style features (mean length of T-unit, clauses per sentence, etc.) — Phase 6 candidate.

## awl

**Coxhead 2000 is the original AWL, not the AVL.** The 570 head words are still the standard for IELTS preparation, but Gardner & Davies (2014) Academic Vocabulary List (AVL) is methodologically stronger — built from a much larger corpus (Davies's 120M-word academic sub-corpus of COCA). AVL is `https://www.academicvocabulary.info/` and freely accessible. Adding an `--list avl` opt-in would let users compare. Gardner & Davies also published NAWL-style derivative lists.

**Family-level matching is correct but families are static.** Coxhead's families are based on Bauer & Nation 1993 Level 6, which excludes some derivational patterns. Tokens like *analytically* (adverbial form of *analyse*) match because they're in the inflected forms; obscure derivations might not.

## bnc_coca

**Headwords only, 10 bands.** The bundled `lpmi-13` mirror is CC0-clean but lacks family-level data with all derivational members. Surface form + spaCy lemma fallback partially mitigates, but `analytical` won't match `analyse` because spaCy's lemmatizer only inflects, not derives.

**Upgrade path 1 — wen-zhi families CSV (1k–9k).** Adds inflected forms, better recall. Licence unstated. Ship as a `[bnc_coca_extended]` opt-in extra; users download separately if they accept the licence ambiguity.

**Upgrade path 2 — Nation's full 25-band families.** Bundled inside Laurence Anthony's WordFamilyFinder app, not a standalone download. Would require either repackaging (legally awkward) or a one-time scrape with explicit permission.

**Off-list residual is just a sample of 50.** For corpus profiling you'd want the full off-list with frequencies. Easy to add a `--full-off-list` flag.

## ngsl

**NGSL is general English; NAWL is academic.** Combining them with a "NGSL+NAWL" coverage number is convenient but conflates two different reference points. The current output keeps them separate, which is correct.

**No NGSL Spoken or NGSL TOEIC variants.** Browne, Culligan, Phillips publish several specialised variants on the same site (NGSL-Spoken, TSL for TOEIC, BSL for business). Easy to add as `--variant` opt-ins later if useful.

## phrase

**Parsed count is 506 vs published 505.** All 506 are distinct — there is **no duplicate**, contrary to what this file used to claim. Running the check (`Counter(it['phrase'] for it in items).most_common(3)`) returns nothing with a count above 1. The extra entry is a slot-variant boundary case from the `.doc` parse. Not material for analysis.

**Slot phrases are partially handled.** `BE EXPECTED TO` matches all `be` inflections, but `(MAY/MIGHT) HAVE TO` and other modal-slot phrases are not explicitly handled — the parser just took the first variant before the slash. If you need full slot expansion, regenerate the JSON with all alternants.

**Licence is unstated.** Norbert Schmitt's site says "freely available for research and pedagogical purposes." Fine for personal/educational use; if lexinspect ever powers a commercial product, request explicit redistribution permission.

## cefr

**Not Cambridge EVP.** Already noted in the module's `caveat` output field and in `SOURCES.md`. Numbers will diverge from EVP-based tools. The CEFR-J methodology is solid (Tono lab) but the underlying corpus is different.

**`dominant_level` is misleading on its own.** It's argmax of token counts, which means function words ("the", "of") usually dominate any text and the answer is almost always A1. Fine when reading the full distribution; do not surface this number alone in a UI.

**`estimated_level_95th` returns null when off-list residual is large.** Most academic texts have >5% off-list (proper nouns, technical terms), so the heuristic refuses to estimate. Honest behaviour, but a UI may want a fallback like "highest level reached" when the heuristic is null.

**Lowest-level-wins on multi-POS lemmas.** A word annotated as A2 noun and B1 verb is recorded as A2. The other reading was thrown away. Acceptable for level estimation; a cleaner approach would store per-POS levels and use spaCy's POS tag at lookup time.

## cefr_level (optional, requires `cefr-level` extra)

**Estimate, not a verdict.** This is the universal limit on every CEFR text classifier — free or commercial. Text Inspector's own published wording on the Lexical Profile© applies verbatim here: only an estimate, not for high-stakes decisions, vocabulary-and-metadiscourse-dominant signal, calibrated on writing/reading/listening (not speech), limited feature set. Inherited from the same construct, not from any flaw specific to lexinspect.

**Adjacent-level confusion is irreducible.** Most misclassifications fall on the next band up or down. Even professional human raters disagree at this granularity (inter-rater Cohen's κ ≈ 0.5–0.7 on 6-class CEFR). The realistic target is within-one-level reliability, not exact match.

**Vocabulary dominates the signal.** The model under-weights syntactic complexity, discourse organisation, and topic familiarity. Two passages with very similar vocabulary distributions but different rhetorical structure may receive the same classification when a human rater would split them.

**Domain and genre drift the calibration.** UniversalCEFR's training corpus mixes reference texts and learner production across 13 languages. Domain-specific calibration (academic vs narrative vs business) is not modelled.

**Single-classifier output is uninformative; convergence is diagnostic.** When the `cefr_level` call agrees with the simpler `cefr` 95th-percentile heuristic and the readability grade, the verdict is robust. When they disagree, the disagreement itself is the signal that the text sits between bands or that one feature family is being misled. Do not surface a single classifier number as ground truth.

**~400MB model download on first call.** Cached in the standard HuggingFace location after that. The pipeline is loaded lazily and cached in-process; subsequent calls reuse it. CPU inference is ~2–5s per text. Not in `analyze` because it would slow the all-modules call from <2s to ~7s and force the heavy extras on every install.

**Web UI runs cefr-level on demand, not as part of Analyze.** The tab opens with a "Run CEFR classifier" button rather than pre-filling from `/v1/analyze`, because (a) the module is not in `/v1/analyze` and (b) the user should make an explicit choice before paying the ~3–5s inference cost. 503 responses (extra not installed) are surfaced as an inline install hint.

**Stderr noise on first call.** transformers' internal info/warning logs are silenced via `transformers.logging.set_verbosity_error()` inside the module. Two lines still surface from sibling libraries: an "unauthenticated requests to the HF Hub" warning from `huggingface_hub`, and a weight-loading progress bar from `tqdm`. The JSON output to stdout is unaffected (agent consumption is clean). For full silence, set `HF_HUB_DISABLE_PROGRESS_BARS=1` and either `HF_TOKEN=<token>` or `HF_HUB_DISABLE_TELEMETRY=1` in the environment.

## errors

**Hunspell only knows what's in its dictionary.** Proper nouns, brand names, recent neologisms, and rare technical vocabulary will routinely show up as false positives. The LibreOffice English dictionaries we ship with — Kevin Atkinson's wordlist (LGPL) plus Geoff Kuenning's affix file (BSD) — are well-maintained but not exhaustive. Treat the error list as a triage signal, not a verdict.

**spaCy splits possessive `'s` from its host noun**, so possessive forms like `children's` are spell-checked as `children` plus `'s` (the latter skipped, never flagged). Hunspell's full possessive-handling affix rules are bypassed. If a single word with `'s` looks suspicious, check the bare lemma yourself.

**No suggestions returned by default.** spylls' `dictionary.suggest()` is available but slow (often 100ms+ per word). Adding suggestions to the output would multiply request latency on long texts; if you need them, call `errors.suggest()` (not yet exposed) on individual surface forms.

**Dictionary download is unauthenticated.** First call per variant fetches `https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_<variant>.{aff,dic}` over HTTPS, with no checksum check. GitHub's TLS is the only integrity guarantee. Pin to a specific commit hash if you need reproducibility for compliance reasons.

**No grammar checking.** This module flags individual tokens against a dictionary; it does not parse syntax, agreement, or tense. Tools like LanguageTool do that and live in a different complexity class.

## metadiscourse

**9 of 10 categories are curated reference subsets, not the full Hyland 2005 Appendix A.** Hedges are the only verbatim mirror. The rest are 30–60 canonical items per category. Coverage is enough for IELTS/ELT diagnostic work but will under-report on a long academic text vs a complete-Appendix tool.

**Not Bax/Nakatsuhara/Waller (2019) 13-category extension.** That's what Text Inspector uses, but the marker list isn't public. If you ever obtain it (paper authors, Cambridge English request), expanding to 13 categories is a drop-in replacement of the data file.

**Greedy longest-match is correct for spans but loses overlap signal.** When `in fact` (booster + code gloss) matches, both categories get +1 hit. When two markers overlap (e.g. `as a result of the fact that`), only the longest match wins. Acceptable trade-off; flag if you start studying overlapping markers specifically.

**No regex-pattern markers.** Some categories (especially evidentials) benefit from patterns like `<author> argues that` rather than literal strings. fatihbozdag's `metadiscourse_analysis` repo is regex-first and worth borrowing patterns from.

## CLI

**`--format human` is basic.** Renders a single-level Rich table; nested fields print as a heading + recursive call. For a polished CLI experience you'd want module-specific formatters (e.g. CEFR distribution as a horizontal bar chart, BNC/COCA as a coverage curve).

**No `--input-format` switch.** Reads UTF-8 plain text. PDF / DOCX / HTML support would help when you want to grade real-world documents — wrap with `marker-pdf` or `defuddle` upstream rather than baking it in.

**No batch mode.** `lexinspect analyze passage.txt` runs one text. For a corpus you'd run a shell loop. A `lexinspect batch dir/ --module cefr --output results.csv` command would be a clean Phase 6 addition.

## API

**CORS is open.** `allow_origins=["*"]` with `allow_credentials=False`. Not a security boundary for an unauthenticated public API — a cross-origin caller gains nothing it couldn't get server-to-server, and there are no cookies or sessions to steal. Tighten via a `LEXINSPECT_ALLOWED_ORIGINS` env var if the API ever grows auth.

**No authentication.** Deliberate: the hosted app is free and open. Abuse is bounded by three things instead — the 50 KB request cap (`MAX_TEXT_BYTES`, overridable via `$LEXINSPECT_MAX_TEXT_BYTES`), a Vercel WAF rate limit of 60 POSTs/min/IP on `/v1/` returning 429 (no persistent block, because schools share one NAT IP), and a 30s `maxDuration`. The durable protection is that a request is cheap: the worst legal request is ~0.9s of CPU. It was ~165s before the parse-once and `phrase` bucketing work.

**No async / no streaming.** Each request is synchronous and CPU-bound (spaCy parse). Long requests block the worker. For high concurrency, run multiple uvicorn workers (`--workers N`) or reach for a job-queue pattern. Note that serverless hosts pack concurrent requests into one process and run these sync handlers on a threadpool, which is why `_nlp.get_doc()` serialises parses behind a lock — spaCy mutates a shared `Vocab`/`StringStore` while tokenising.

**No OpenTelemetry / structured logging.** uvicorn's default access log is the only observability. Add `structlog` + Prometheus metrics if you operate this beyond local use.

**No multipart file upload endpoint.** Body is JSON with the text inline. Add `POST /v1/upload` accepting `multipart/form-data` if you want browser drag-and-drop.

## Operations

**Data refresh is manual.** Build scripts in `scripts/build_data/` exist but are one-shot. A CI workflow that re-runs them on a schedule + opens a PR with diffs would catch upstream version bumps automatically. Low priority — these lists move slowly.

**Deployed at `lexinspect.vercel.app`.** GitHub Actions runs `vercel build` and `vercel deploy --prebuilt`, so Vercel build compute stays near zero; Vercel's own git builds are off via `git.deploymentEnabled: false`. The hosted build omits the `cefr-level` extra — `/v1/schema` reports `optional_available`, and the web UI hides tabs whose module isn't installed.

**The bundle is 509.67 MB against a 500 MB limit — the top thing to fix.** It only deploys because the large-functions beta is enabled (`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, set both as a project env var and inline in the workflows, because off-platform builds don't receive project env vars). Any dependency bump can push it over.

The cure is to **drop `lexicalrichness` and vendor MTLD + HD-D**. It is the sole reason `scipy` (82 MB), `pandas` (48 MB), `matplotlib` (26 MB) and `textblob` are in the bundle — `diversity.py` is the only module that imports it, and it uses ten metrics, all of which are pure Python plus `math.comb` for HD-D's hypergeometric term. `textstat` needs only `pyphen` + `nltk`; nltk's scipy dependency is extras-only. Expected outcome:

- ~350 MB bundle, comfortably under the standard limit; the beta opt-in and the CI env-var workaround both go away.
- Cold start drops sharply. `lexicalrichness` costs ~1.7s to import, and `matplotlib` rebuilds its font cache on every new instance ("generated new fontManager") — most of the ~11s cold requests visible in the runtime logs. `_env.py` gives matplotlib a writable `MPLCONFIGDIR` so it pays that once per instance rather than failing, but the only real fix is not importing it.

Do it carefully: these are numbers users read. Port the exact formulas and assert byte-identical output against the current `lexicalrichness` results across a randomised corpus before deleting the dependency — the same way the `phrase` index rewrite was verified across 33 fixtures.

**Two runtime downloads were removed; don't reintroduce the pattern.** `spylls` ships no dictionary data and `textstat` asks `nltk` for the CMU dictionary. Both used to fetch at request time. On a read-only, ephemeral serverless filesystem that meant re-downloading on every cold start, HTTP 429s under bursts, a concurrency race that produced live HTTP 500s (`[nltk_data] Extraction error for cmudict/cmudict`), and — because spylls compiles the `.aff` file into regexes — a supply-chain hole where a force-push upstream became code we ran. Both are now vendored under `src/lexinspect/data/`, and `_env.py` points `$NLTK_DATA` at the bundled corpus before textstat imports. The FastAPI lifespan also touches `readability.analyze()` once, single-threaded, because `nltk.data.find()` is not thread-safe on first call.

**Spend Management must not be armed with the pause action.** Its pause applies to *every project on the team*, with a several-minute detection delay and manual un-pausing. To fail-closed on this project alone, use the spend webhook to call `POST /v1/projects/{projectId}/pause`.

**Serving the data publicly changed the licence position.** `/licences` (linked from the footer) carries the CC BY-SA 4.0 attribution for NGSL/NAWL/Octanove and the CEFR-J citation, because those terms run to whoever receives the work, not just whoever reads the repo. Two open questions worth resolving: the PHRASE list is "freely available for research and pedagogical purposes" and the note in `SOURCES.md` says to seek explicit permission if lexinspect is ever wrapped in a web product — arguably now true, even though it's free; and the Hyland 2005 hedges lexicon has **no stated licence** at all.

**No telemetry on which modules are actually used.** When the CLI ships beyond personal use, it would be worth knowing whether `phrase` justifies its build complexity. A simple opt-in counts file would do.

## What's not in scope today

- **Non-English text.** Every module assumes English. Many CEFR-J levels exist for German, French, etc. — adding them is a per-language data file, not a code change. CLI flags would need a `--lang` option.
- **Speaking / listening assessment.** The toolkit analyses written text. Spoken-mode features (filled pauses, repair phenomena) need a different pipeline.
- **Generation.** lexinspect describes texts; it doesn't write or simplify them. Pair with an LLM for the generative side.
