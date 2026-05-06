# Caveats and improvement opportunities

What lexinspect doesn't do well today, and where to look first if you decide to fix it. Organised per module, then transport, then ops. Honest framing: most caveats are conscious trade-offs (licence cleanliness, scope, time), not bugs. None are blockers for ELT or IELTS work — they're flags for when you push harder.

## readability

**Syllable counter has known errors on rare words.** textstat falls back to Pyphen for syllabification, which is dictionary-based and will mis-count technical, medical, or low-frequency vocabulary. Affects FK Grade and Gunning Fog at the margins on jargon-dense texts. Upgrade path: Carnegie Mellon Pronouncing Dictionary (`cmudict` PyPI package) for the words it covers, fall back to Pyphen.

**`text_standard` is a consensus heuristic, not validated.** textstat picks the median grade from the seven scores and rounds — useful for quick triage, not for high-stakes placement.

**Reading-time formula is a single fixed ms-per-character constant.** Doesn't model genre, density, or reader proficiency. If you need a real reading-time estimate, use words-per-minute by reader level instead.

## diversity

**vocd-D / HD-D are sample-size dependent.** Both fail or wobble on texts under ~50 tokens. The module returns `None` for failed metrics rather than a bad number, but downstream code should check.

**MTLD threshold is fixed at 0.72 (the published default).** Some research uses 0.71 or 0.5 — if you're matching a specific paper, expose `threshold` as a parameter.

**No comparability scale.** Raw MTLD numbers don't map to a level without reference data. Duran et al. 2004 gave A1–C2 reference bands for academic English; you could bundle those as a lookup table to convert MTLD into a CEFR-equivalent diversity grade.

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

**Parsed count is 506 vs published 505.** One duplicate or boundary case from the `.doc` parse. Not material for analysis but worth tracing if you ever publish the data file. Run `python3 -c "import json; d=json.load(open('src/lexinspect/data/phrase.json'))['items']; from collections import Counter; print(Counter(it['phrase'] for it in d).most_common(3))"` to find the duplicate.

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

**Not in the web UI yet.** The web UI is hardcoded to the 9 always-available `analyze` modules; `cefr_level` is reachable only via CLI (`lexinspect cefr-level`) and HTTP (`POST /v1/cefr-level`). Adding a UI tab is a follow-up — different fetch, extras-installed check, separate render path.

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

**CORS is open by default.** Fine for local dev; tighten for production via a proxy or a `LEXINSPECT_ALLOWED_ORIGINS` env var.

**No authentication, no rate limiting.** If you expose the API publicly, put it behind a real reverse proxy (Caddy, nginx) or a managed gateway with API keys + quotas. The 1 MB request cap is the only built-in protection.

**No async / no streaming.** Each request is synchronous and CPU-bound (spaCy parse). Long requests block the worker. For high concurrency, run multiple uvicorn workers (`--workers N`) or reach for a job-queue pattern.

**No OpenTelemetry / structured logging.** uvicorn's default access log is the only observability. Add `structlog` + Prometheus metrics if you operate this beyond local use.

**No multipart file upload endpoint.** Body is JSON with the text inline. Add `POST /v1/upload` accepting `multipart/form-data` if you want browser drag-and-drop.

## Operations

**spaCy model gets dropped on every `uv sync`.** uv rebuilds the venv from the lockfile, and the model is installed via wheel URL, not a tracked dependency. README documents the re-install line. A cleaner fix is a post-sync hook script or shipping the model in the lockfile via a `dependency-groups` block once uv supports it for non-PyPI wheels.

**Data refresh is manual.** Build scripts in `scripts/build_data/` exist but are one-shot. A CI workflow that re-runs them on a schedule + opens a PR with diffs would catch upstream version bumps automatically. Low priority — these lists move slowly.

**No Docker / no deploy recipe.** A 30-line Dockerfile (slim Python + uv + wheel-install spaCy) gets you a portable image. Add when there's a deploy target.

**No telemetry on which modules are actually used.** When the CLI ships beyond personal use, it would be worth knowing whether `phrase` justifies its build complexity. A simple opt-in counts file would do.

## What's not in scope today

- **Non-English text.** Every module assumes English. Many CEFR-J levels exist for German, French, etc. — adding them is a per-language data file, not a code change. CLI flags would need a `--lang` option.
- **Speaking / listening assessment.** The toolkit analyses written text. Spoken-mode features (filled pauses, repair phenomena) need a different pipeline.
- **Generation.** lexinspect describes texts; it doesn't write or simplify them. Pair with an LLM for the generative side.
