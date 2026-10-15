# Caveats and improvement opportunities

What lexinspect doesn't do well today, and where to look first if you decide to fix it. Organised by shared tokenisation, then per module, then transport and operations. Most caveats are conscious trade-offs (licence cleanliness, scope, time), not bugs. None are blockers for ELT or IELTS work; they're flags for when you push harder.

## Shared tokenisation

**Everything rests on `en_core_web_sm`.** The small spaCy model is fast but roughly 2 percentage points less accurate on tags than `en_core_web_lg`. Tags decide more than the tagger tab: proper-noun status (NNP/NNPS) in every vocabulary profile, the part of speech that picks a CEFR level, whether an inflected verb is looked up by its lemma, the tag constraints in `phrase`, and every context rule in `metadiscourse`. A capitalised common word at the start of a sentence can be tagged as a proper noun and drop out of the off-list count; a mis-tagged `present` gets the wrong CEFR level. Swapping to `lg` means changing `DEFAULT_MODEL` in `_nlp.py` and the model dependency in `pyproject.toml`, and adds several hundred MB to the bundle.

**Inflected verbs are looked up by lemma only.** That's what stops `found` being credited to *found* (a company) and `left` to *the left*. The cost is the reverse case: when spaCy tags a non-verb use as a verb, or lemmatises wrongly, the token goes to the lemma's entry. The surface form is used only when the lemma isn't an English word at all.

**Hyphenated compounds are profiled by their parts** (`well-known` as *well* + *known*), the convention of Range and AntWordProfiler, unless the list carries the whole compound. Lists that rate a compound differently from its parts will disagree with lexinspect.

**Spelling-variant lookup can over-match.** A form that misses a list is retried with its British/American respelling, from VarCon plus regular-pattern rules (`-our`/`-or`, `-ise`/`-ize`, `-re`/`-er`, doubled `l`). The rules only fire after the exact form has missed, but a rare word that happens to rewrite into a listed one is credited to it.

## readability

**Formulas see only surface features.** All eight are functions of word length (syllables or letters), sentence length, and, for Dale–Chall, a familiar-word list. They cannot see vocabulary level beyond that, grammar, cohesion or topic. Read them alongside the vocabulary profiles.

**`text_standard` is a heuristic.** It is the median of the eight grade equivalents, which is stable and easy to explain, but the median of eight formulas fitted on different populations is not itself a validated measure. Flesch Reading Ease and the Dale–Chall raw score are mapped to grades by band midpoints.

**Syllables beyond CMUdict are estimated.** CMUdict (American pronunciations, first listed pronunciation) answers most words; a British/American respelling or a stem plus suffix answers more. The rule-based fallback for the rest is about 90% exact and over 99% within one syllable when measured against CMUdict itself. It handles rare, technical and invented words, which is exactly where errors concentrate.

**Numerals are an approximation of speech.** Integers and four-digit years are spelled out as spoken; decimals are read digit by digit after "point"; `%` adds "per cent". Ordinals and decades are read as the cardinal number (`3rd` as *three*, `1990s` as *nineteen ninety*).

**The Dale–Chall easy-word list is textstat's.** It has 2,940 entries, slightly fewer than the roughly 3,000 in Chall & Dale (1995). Familiarity accepts a listed word, its spaCy lemma, proper nouns, numerals, and hyphenated compounds whose parts are all familiar. Edge cases in the 1995 counting rules that need human judgement are not modelled.

**Linsear Write reads only the first 100 words**, as the formula specifies. On a long text it describes the opening, not the whole.

**Short texts are flagged, not blocked.** Every score is computed regardless of length; `reliability.reliable` is false under 100 words, and the SMOG note appears under 30 sentences, because SMOG is normalised to a 30-sentence sample and is extrapolated below it.

**Reading time is a single rate.** 238 words per minute (Brysbaert 2019, silent reading of English non-fiction). It doesn't model genre, density or reader proficiency.

## diversity

**Sample-size dependence.** Every measure moves with text length. Measures that can't be computed are returned as `null` rather than a bad number: HD-D needs 42 tokens, MSTTR and MATTR 50, MTLD is suppressed below 50, and vocd-D needs more than 50. Texts under 50 tokens carry a `note`.

**Tokens differ from other tools.** Diversity counts lexinspect's words: contractions and hyphenated compounds whole, lowercased, numbers excluded. lexicalrichness split `don't` into `don` and `t`; CLAN works on CHAT transcripts with its own conventions. Scores will not match those tools exactly, even where the formulas do.

**vocd-D is stochastic, but seeded.** It averages random samples (100 per size from 35 to 50 tokens, three trials) and fits D to the curve. The fixed seed makes a given text always score the same, but any edit changes which samples are drawn, so small edits can move D by sampling noise alone. Treat differences of a few points as noise.

**Reference bands are approximate comparisons.** The Durán, Malvern, Richards & Chipere (2004) ranges (adult L2/ESL D 40–70, adult native academic D 80–105) were computed with CLAN on their corpora. lexinspect's vocd-D follows the same procedure but not the same tokenisation, so `position` (below/within/above) is a guide, not a classification. Technical prose with many unique terms can score well above both bands.

**Per-age cohort bands aren't bundled.** Text Inspector's "Bristol Charts" show vocd-D bands for nine cohorts. Only the two adult ranges are stated in the paper's freely available abstract; the rest sit in typeset figures the public manuscript doesn't include.

**MTLD threshold is fixed at 0.72** (McCarthy & Jarvis 2010 default). Some research uses other values; expose `threshold` as a parameter if you're matching a specific paper. No MTLD reference bands are bundled.

## tagger

**Distributions and summary count different units.** PTB and UPOS distributions are over spaCy tokens (`don't` is `do` + `n't`); the `summary` block counts words from the shared analysis. Both are deliberate, but the totals differ.

**No syntactic parsing exposed.** The dependency parse runs (sentence segmentation and the metadiscourse rules need it), but the module only emits POS counts. Surfacing dependency relations would allow L2 Syntactic Complexity Analyzer-style measures (mean length of T-unit, clauses per sentence).

## awl

**Coxhead 2000 is the original AWL, not the AVL.** The 570 families are still the standard for IELTS preparation, but Gardner & Davies's (2014) Academic Vocabulary List is built from a much larger corpus. Adding it as an opt-in list would let users compare.

**Families are static.** Coxhead's families follow Bauer & Nation (1993) Level 6. Derivations outside the listed forms don't match.

## bnc_coca

**Homographs take the most frequent band.** A form listed in more than one family keeps the lowest band, as Range does. A rare sense of a common spelling counts as common.

**Proper nouns depend on the tagger and on the lists.** A token no family claims is a proper noun if Nation's proper-names list has it or spaCy tags it NNP/NNPS. A name that is also a common word (`Bath`, `Brown`) is matched to its family first and counted in that band.

**"Assumed known" is a convention.** `coverage_with_supplementary_pct` counts proper nouns and supplementary-list words as known, following Nation. Use `coverage_pct` if you want the strict figure.

## ngsl

**NGSL is general English; NAWL is academic.** The combined `ngsl_plus_nawl` figure is convenient but mixes two reference points; the separate figures are the ones to report.

**No NGSL Spoken, TSL or BSL.** Browne, Culligan and Phillips publish specialised lists on the same site; they could be added as opt-ins.

## phrase

**Parsed count is 506 vs published 505.** All 506 are distinct; the extra entry is a slot-variant boundary case from the `.doc` parse. Not material for analysis.

**Senses rest on one example each.** The tag constraints (`to` as TO or IN, `that` as IN or DT, particles as RP/RB or IN) are read from each entry's own example sentence at build time. An entry whose example doesn't contain the phrase gets no constraint; the build script lists those. A mis-tagged token in the user's text can also accept or reject a sense wrongly.

**Longest match hides overlaps.** `as well as` is one hit, not also `as well`. When two senses of the same form both fit, the more frequent is chosen and the others are listed in `also_possible`; nothing decides between them semantically.

**Licence is unstated.** Norbert Schmitt's site says the materials are "freely available for research and pedagogical purposes". See Operations below.

## cefr

**Not Cambridge EVP.** Noted in the module's `caveat` field and in `SOURCES.md`. Numbers will diverge from EVP-based tools; CEFR-J and Octanove use different corpora and methods.

**`dominant_level` is misleading on its own.** It's the argmax of token counts, and function words make it A1 for almost any text. Read the distribution, `highest_level_present` and the upper-level word lists instead.

**`estimated_level_95th` can be null.** Proper nouns are counted as known, but a text with more than 5% off-list words (technical terms, rare words) never reaches 95% and gets no estimate.

**POS fallback.** When the source lists no level for the token's part of speech, the lowest listed level is used and counted in `pos_fallback_tokens`. A high count means the levels are less specific than they look.

## cefr_level (optional, requires `cefr-level` extra)

**Estimate, not a verdict.** This is the universal limit on every CEFR text classifier, free or commercial. Text Inspector's published wording for its Lexical Profile applies here too: only an estimate, not for high-stakes decisions, vocabulary-dominated signal, calibrated on writing/reading/listening rather than speech, limited feature set.

**Adjacent-level confusion is irreducible.** Most misclassifications fall one band up or down. Human raters also disagree at this granularity; within-one-level reliability is the realistic target.

**Vocabulary dominates the signal.** The model under-weights syntactic complexity, discourse organisation and topic familiarity.

**Domain and genre drift the calibration.** UniversalCEFR's training corpus mixes reference texts and learner production across 13 languages. Domain-specific calibration is not modelled.

**Convergence is diagnostic.** When `cefr_level` agrees with the `cefr` 95th-percentile heuristic and the readability grade, the verdict is robust; when they disagree, the disagreement is the signal.

**Heavy.** A large model download on first call, cached by Hugging Face afterwards; CPU inference takes seconds per text. Not in `analyze`, and not in the hosted build. The web UI offers it on demand when the extra is installed.

**Stderr noise on first call.** transformers' own logs are silenced, but `huggingface_hub` may warn about unauthenticated requests and `tqdm` prints a progress bar. JSON on stdout is unaffected. Set `HF_HUB_DISABLE_PROGRESS_BARS=1` and either `HF_TOKEN` or `HF_HUB_DISABLE_TELEMETRY=1` for silence.

## errors

**Hunspell can't catch real-word errors.** A real word used wrongly (*their*/*there*, *form*/*from*) passes. It also only knows what's in its dictionary: rare technical terms and neologisms show up as errors. Treat the list as a triage signal, not a verdict.

**Capitalised misspellings can still pass as names.** A capitalised word the dictionary rejects, anywhere but the start of a sentence, goes to `unknown_names`. The exception is a word one edit from a very common word (six letters or more) with no proper noun beside it, so *the Goverment said* is an error. *The Enviroment Agency* is still reported as a name, because its neighbour looks like part of a name. Words written in capitals are treated as acronyms.

**Hyphenated compounds are accepted part by part.** If the whole compound isn't in the dictionary, it passes when every part is a word, so an invented compound of real words is never flagged.

**Suggestions are bounded.** The suggester looks for BNC/COCA and NGSL forms within one edit (two for words up to 12 letters, if one finds nothing), filtered to words valid in the chosen variety. Words outside those lists are never suggested, and only the 40 most frequent distinct errors per request get suggestions.

**The rate counts checked words.** `errors_per_100_words` divides by `tokens_checked`, which excludes numbers, codes, URLs and abbreviations, so it can differ slightly from a rate over the full word count.

**No grammar checking.** Tools like LanguageTool parse agreement and tense; that is a different class of problem.

## metadiscourse

**Automated, not hand-coded.** Hyland's categories are functional, and his counts were checked by hand. lexinspect approximates that with context rules on the parse (clause-linking `and`, `Table 2`, reporting verbs with a clausal complement, predicative `clear`, and so on). The rules remove most false positives from everyday words, but they inherit tagger and parser errors, and some judgements are out of reach: `or` as a code gloss and bare `as` as an evidential are never counted.

**Marker lists are partial.** Hedges mirror Hyland 2005 Appendix A; the other nine categories are curated subsets of 23–60 markers each. Coverage is enough for ELT diagnostic work but will under-report against a full-appendix tool. Markers are literal strings: inflected forms count only when listed.

**One category per hit.** A marker listed in several categories is assigned by a fixed priority order and its context rules; the others are recorded in `also_listed_as`, not counted.

**Not Bax, Nakatsuhara & Waller (2019).** Text Inspector uses that 13-category extension, whose marker list isn't public. Numbers will not match Text Inspector's.

## CLI

**`--format human` is basic.** A single-level Rich table with nested fields printed recursively. Module-specific formatters would read better.

**Plain text only.** Reads UTF-8 text. For PDF, DOCX or HTML, convert upstream.

**No batch mode.** One text per call; use a shell loop for a corpus.

**CLI and API envelopes differ slightly.** API single-module responses include `input.word_count`; CLI single-module output doesn't. `/v1/analyze` returns `input.normalised_text` when normalisation changed the text; the CLI's `analyze` doesn't, although its spans also index the normalised text.

## API

**CORS is open by default.** `allow_origins=["*"]` with `allow_credentials=False`. Not a security boundary: the only cookie is the Turnstile pass, which is `SameSite=Strict` and never sent cross-origin. Set `LEXINSPECT_ALLOWED_ORIGINS` to restrict it.

**No accounts; a human check instead.** Deliberate: the hosted app is free and open, with nothing to sign in to. Abuse is bounded by the 50 KB request cap (`MAX_TEXT_BYTES`, overridable via `$LEXINSPECT_MAX_TEXT_BYTES`), a Vercel WAF rate limit of 60 POSTs/min/IP on `/v1/` returning 429 (no persistent block, because schools share one NAT IP), a 10 s `maxDuration`, and Cloudflare Turnstile on every analysis endpoint (`_human.py`). The durable protection is still that a request is cheap: the full pipeline takes about 0.09 s of CPU for 3 KB and about 0.8 s for a maximum-size 50 KB text.

**What Turnstile does and doesn't stop.** It stops scripts that can't run a browser challenge. A passed check earns a signed cookie valid for an hour, not bound to an IP or device, so someone who passes once by hand can reuse the cookie from a script for that hour, still under the per-IP rate limit. Tokens are single-use and verified server-side (`siteverify`); if Cloudflare can't be reached, analyses fail with 503 rather than run unchecked. People with Turnstile blocked by a content blocker, or with JavaScript off, can't use the hosted app. With the keys set, the hosted API no longer serves scripts or notebooks; they should run lexinspect locally. Rotating `TURNSTILE_SECRET_KEY` invalidates every cookie.

**No async, no streaming.** Each request is synchronous and CPU-bound. Serverless hosts pack concurrent requests into one process and run sync handlers on a threadpool, which is why `_nlp.parse()` serialises parses behind a lock: spaCy mutates a shared `Vocab`/`StringStore` while tokenising. Locally, use `--workers N` for parallelism.

**No structured logging or metrics.** The access log is the only observability.

**No file upload endpoint.** The body is JSON with the text inline.

## Operations

**Data refresh is manual.** The scripts in `scripts/build_data/` are one-shot and need the upstream files downloaded by hand. These lists move slowly.

**Deployed at `lexinspect.vercel.app`.** GitHub Actions runs `vercel build` and `vercel deploy --prebuilt`; Vercel's own git builds are off (`git.deploymentEnabled: false`). The function is `api/index.py` (`maxDuration` 10 s, 1024 MB); the web UI is copied to `public/` and served from the CDN. The hosted build omits the `cefr-level` extra. The Linux function bundle is about 280 MB, mostly spaCy, blis and numpy shared objects that ship with debug symbols (macOS wheels are far smaller, so a local `vercel build` understates it). That is over the builder's standard limit, so CI sets `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` and pins Vercel CLI 53.0.1: without the flag the builder falls back to installing packages at cold start, which failed every request on both CLI 53 and 64. CI prints the size in the job summary.

**Keep runtime downloads out.** Every dictionary and list is vendored under `src/lexinspect/data/`. Earlier versions fetched the Hunspell dictionaries and NLTK's CMUdict at request time; on an ephemeral serverless filesystem that meant re-downloading on cold starts, HTTP 429s under bursts, a concurrency race that produced live 500s, and, because spylls compiles `.aff` files into regexes, a supply-chain hole. The app also loads everything once at startup, single-threaded (`pipeline.warm()`, about a second), because lazy first-use loading under concurrency is how it used to race itself.

**Spend Management must not be armed with the pause action.** Its pause applies to every project on the team, with a several-minute detection delay and manual un-pausing. To fail closed on this project alone, use the spend webhook to call `POST /v1/projects/{projectId}/pause`.

**Serving the data publicly changes the licence position.** `/licences` carries the attribution for every bundled dataset, because CC BY-SA terms run to whoever receives the work, not just whoever reads the repo. Points to keep in mind:

- `bnc_coca.json`, `ngsl.json` and `nawl.json` are adaptations of CC BY-SA 4.0 lists and are therefore CC BY-SA 4.0 themselves. `cefr.json` merges CEFR-J (citation terms) with Octanove (CC BY-SA 4.0); share it under CC BY-SA with both credits.
- The PHRASE list is "freely available for research and pedagogical purposes", and `SOURCES.md` has long said to seek explicit permission if lexinspect is wrapped in a web product. That is arguably now the case, even though the product is free.
- The Hyland 2005 hedges lexicon mirror has no stated licence.
- VarCon's and CMUdict's permissive notices require the copyright and permission text to accompany copies; `SOURCES.md` and `data/hunspell/LICENSES/` carry them.

**No telemetry on which modules are used.** If the CLI ships beyond personal use, an opt-in counts file would show whether `phrase` justifies its build complexity.

## What's not in scope today

- **Non-English text.** Every module assumes English. CEFR-J-style profiles exist for other languages; adding them is a per-language data file plus a `--lang` option.
- **Speaking and listening assessment.** The toolkit analyses written text. Spoken-mode features need a different pipeline.
- **Generation.** lexinspect describes texts; it doesn't write or simplify them.
