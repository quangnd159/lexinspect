# Changelog

Every change to lexinspect's output is listed here, by version. Output is deterministic within a version (see [VALIDITY.md](VALIDITY.md#reproducibility)), so cite the version you ran. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/): until 1.0, a minor version may change output values.

## [Unreleased]

No change to any existing number. `phrase` gains fields; everything else is the web app.

### Added

- **Export menu in the web app**, replacing Copy JSON and Download JSON. It offers a plain-text summary to copy, a printable report (also printed by Cmd/Ctrl+P after an analysis), an Excel workbook with one sheet per table and a codebook, a one-row summary CSV with stable columns for stacking texts, a word-by-word CSV, the full JSON, and an APA/BibTeX citation. Every file records the version, spaCy model, spelling variety, export time and a SHA-256 of the text. Files are built in the browser; nothing is sent again. See the README's [Export from the web app](README.md#export-from-the-web-app).
- **The PHRASE List's own data, used.** Every expression now carries what Martinez & Schmitt published with it: its frequency per 100 million words, its ratings in spoken, written and academic English, its example sentence, and the highest BNC/COCA band among its words (`expressions`). `register` counts the hits by rating. `integrated_profile` is the BNC/COCA profile with each expression's words counted at the expression's band, the way the PHRASE List merges into the word-family lists. In the web app, the Phrases tab shows register bars, the expressions rated rare or absent in each register, and each expression's ratings and example. The Frequency tab gains a *Words and phrases* view, and the reader card shows a phrase's ratings. Exports gain an Expressions sheet, phrase-aware columns on the BNC-COCA sheet, and five summary columns at the end (`bnc_band_95_with_phrases`, `bnc_band_98_with_phrases`, `phrase_words_pct`, `phrase_rare_*_hits`).

### Changed

- **Detection is unchanged.** The new phrase fields are derived from the hits. On the 120 Study 4 development texts, `hits` and the `bnc_coca` output are byte-identical to 0.4.0, so Study 4's precision estimate for 0.4.0 applies to this version's PHRASE hits too.
- **PHRASE names in the web app keep their optional parts.** IN (THE SENSE) THAT showed as "in that", and IN ADDITION (TO) as "in addition". Only the sense gloss is dropped now, and glosses that were abbreviations (`TRANs`, `+NP`, `adv.`) read in full. An expression with another possible sense names that sense ("could also be using, due to") instead of repeating the same words.
- **PHRASE List licence notes.** Both authors approved lexinspect's use of the list (Norbert Schmitt, 2026-10-16; Ron Martinez, 2026-10-30). `CAVEATS.md`, the data `LICENSE.md` and `SOURCES.md`, and the `/licences` page now say so. `phrase.json` is unchanged.

## [0.4.0] - 2026-10-19

Tightens when a metadiscourse marker or a PHRASE List expression counts. The changes come from matcher errors found on the Study 4 development texts. Before release they met the numerical loss gates of a pre-registered check on texts never used in development. One labeller's harness showed it repository metadata the protocol says labellers must not see. This is disclosed below, with a sensitivity analysis. Output changes only in `metadiscourse` and `phrase`. Every other module gives the same output as 0.3.3. `schema_version` stays `2`.

### Changed

- **metadiscourse: quotation.** Markers between paired quotation marks within a paragraph no longer count. These are curly double, straight double and curly single quotes. Quoted words are usually someone else's voice, not the writer's. The known costs: scare quotes are excluded too, and two straight inch marks (`5"` … `6"`) can be read as a quotation pair. A possessive `’` (`the students’ work`) doesn't close a curly single quotation. Straight single quotes are not treated as quotation marks, so text inside them still counts.
- **metadiscourse: code glosses.**
  - `that is` no longer counts with relative *that* (`a method that is used`). Nor does it count when a demonstrative *that* opens its clause as the subject of *is* and a predicate follows (`That is not the point`, `but that is not`). After a comma (`Yes, that is not the point`), it can still be counted.
  - `particularly` and `especially` don't count when they modify an adverb or a predicative adjective (`particularly cold`), or an attributive adjective straight after a determiner (`an especially good way`).
  - `known as` doesn't count when the word straight before it is a form of *become*, *come* or *grow*. With an adverb in between (`became widely known as`), it still counts.
  - `or indeed`, and `, indeed,` before a noun phrase, are read as code glosses (reformulation) rather than boosters.
- **metadiscourse: exclusive *we*.** *We* and *us* are now self-mentions, not reader engagement, when their governing verb is past tense and is not *be* or *have* (`we recruited`). The earlier research-verb and own-work-noun rules, such as `our results`, are unchanged. The known costs: an inclusive `as we saw` is misread as a self-mention, and so is the country name in `the US rose`.
- **phrase: USED TO and THAT IS.** USED TO (PAST) no longer matches after *be*, *get*, *become* or *grow*, or as a participle or modifier (`was used to drain`). USED TO (ACCUSTOMED) matches only after them. THAT IS follows the same two exclusions as the code gloss above. Otherwise it counts with or without punctuation around it, including when the tagger reads its *that* as an adverb.
- **phrase: entry-specific constructions.**
  - KIND OF counts only with no determiner or modifier on *kind* and an adjective, adverb, verb or punctuation after it (`kind of tired`, not `a kind of tool`). This also misses `kind of a genius`.
  - WEALTH OF counts only straight after *a*/*an*, so `a great wealth of` is missed. A GOOD counts only before a number.
  - IS TO doesn't count after a goal noun as subject (`the aim is to`).
  - IN A WAY doesn't count with a relative clause, comparison or prepositional phrase after *way*.
  - JUST AS doesn't count before an adjective or adverb (`just as tall`).
  - AS LONG AS doesn't count after a numeral, *twice*, *half* or *times*.
  - PUT IT doesn't count before a particle (`put it out`). GET OFF counts only with *off* as a particle, which wrongly drops `We got off the train` and keeps `He got off lightly` under the transport sense.
- **phrase: matching form.** Nothing inside a hyphenated word counts (`in common-law countries`). The bare noun of a preposition + noun idiom doesn't inflect: IN PART doesn't match `in parts of`, and FOR GOOD doesn't match `for goods`.
- The `metadiscourse` and `phrase` docstrings and README sections list the checks. Most other PHRASE entries have no entry-specific construction check, although the general form, tag and overlap rules still apply. Known gaps include THE CASE in `in the case of`. CAVEATS.md lists the known costs.

### Validation

- **Fix check.** The changes were grouped into twelve families and checked under a pre-registered protocol ([fix protocol](docs/validation/study4-fix-protocol.md), [clarifications](docs/validation/study4-fix-protocol-clarifications.md)). Each round used 60 new texts: 20 academic, 20 argumentative and 20 general.
  - **What was labelled:** frames of changed output, censused up to 200 rows and sampled at 200 above that, plus a stratified sample of 0.3.3's hits for the baseline denominator.
  - **Who labelled:** two language models, Claude Sonnet 5.5 and GPT-6.1-Sol, in separate sessions. DeepSeek V4.1 Flash adjudicated disagreements and non-votes. No human labelled the items.
  - **What it measures:** removal and cumulative loss of baseline detections against the operational model reference, including harm through reassignment under the strict reading. It does **not** estimate overall precision or recall.
- **Round 1 failed.** On metadiscourse, four families had breach certificates. The cumulative loss bound was .070 (strict) and .080 (lenient), against a limit of .05.
- **Six of the nine metadiscourse families were reverted to 0.3.3.** These are the clause-linking, hyphen, frame/endophoric, evidential, stance and reader/writer families. The reader/writer family had passed (.148 against .15). It was reverted as a precaution decided after seeing the results, because failing any required gate stops the combined candidate from passing. The reasons are in the [narrowing disposition](docs/validation/study4-fix040/round2/NARROWING_DISPOSITION.md).
- **Round 2 met every numerical gate, on a fresh set of 60 texts.** No removal frame's bound was above .049 (limit .15). The cumulative loss bound was .0052 (strict) and .0040 (lenient) for metadiscourse, and .0034 for PHRASE (limit .05). No breach certificates. An independent audit reproduced every gate in both rounds. The figures are in the [fix-check report](docs/validation/study4-fix-check.md) and the [registered acceptance](docs/validation/study4-fix040/round2/accept/acceptance.md).
- **Blinding deviation.** Claude Code showed labeller A (Claude Sonnet 5.5) a git-status snapshot in every session of both rounds. It held the branch name and recent commit subjects, including, in round 2's primary sessions, `round-2 candidate (narrowed)`. It contained no items, labels, or item-level version or family information. The protocol says labellers get no version information, and the harness's procedure check did not catch this. A sensitivity analysis replaced A's labels with B's. Its decision rule was committed before it ran, and every gate still passes: the largest removal bound is .049, and the largest cumulative bound is .0053. The same gates therefore pass under this alternative reference, without A's direct contribution. This does not establish what fully blinded A sessions would have judged, or retrospectively repair the blinding breach. Details are in the [report](docs/validation/study4-fix-check.md#deviations-and-corrections).
- **Other corrections and events.** Between the rounds, the acceptance code's status order was corrected to the protocol's stated rule, which puts procedure problems before certificates. The correction was reviewed before round 2 ([ruling A1](docs/validation/study4-fix040/round2/HARNESS_ROUND2_RULINGS.md)), and round 1's recorded result is the same under either order. A Flash server restart in round 1 duplicated 30 adjudicator records; the frozen duplicate rule turned 6 conflicting pairs into non-votes. Both events are disclosed in the report.
- **The Study 4 precision study has not been registered or run.** Its protocol is a [draft](docs/validation/study4-preregistration.md). Before registration, it still needs a rebuilt common development pilot under 0.4.0, recalibration, a full rerun of the simulation, and a final review. It will estimate precision and concordance with the maintainer, not recall.

## [0.3.3] - 2026-10-16

Finishes the tokenisation fixes of 0.3.2, which a rerun of Study 3 and an independent audit showed were incomplete, and fixes a closing-quote bug. Output changes for texts that contain these forms. `schema_version` stays `2`.

### Fixed

- Typewriter dashes (`with--and`, two or more hyphens), figure and horizontal dashes (`‒`, `―`), and punctuation left before any dash (`dishonest,--for`, `end,—but`) kept words glued together or kept the punctuation on the word, which then missed every word list.
- Brackets and punctuation glued to words by a missing space (`great,[2`, `burning[18`, `quickly)and`) made one word of two.
- Numerals written with Unicode characters (`1⁄12`, `30½`, `3‐4`, `5−3`, `8×8`, `~3.8`) and heights (`6'1`) counted as words with no syllables. They're now numerals.
- A closing single quote was attached to the word before it as if it were a possessive, so `‘quoted’` counted as the word `quoted’`, a separate diversity type from `quoted`. A bare apostrophe is now a possessive only after a word ending in *s* and when it doesn't close a single quotation opened earlier in the sentence (`the students’ books` still is).

### Changed

- Numerals with separators are read part by part with a joining word only where one is spoken: "to" for a range (`3-4`, three syllables) and "by" for a dimension (`8×8`); nothing for a time, fraction or date (`11:00`, five syllables). In 0.3.2 every separator added one syllable.
- Validation Studies 1, 2, 3 and 5 were rerun under 0.3.3; their write-ups and VALIDITY.md give the new figures. The `cefr` caveat now gives exact agreement as 43–54% (was 42–54%) and says that texts given no level are counted as C2.
- Two independent auditors (GPT-6.1-Sol and Claude Fable 5.1) checked every figure in the validation write-ups, CAVEATS.md and VALIDITY.md against the result files, over three rounds. Their findings are corrected. The largest: CAVEATS.md said most of the `cefr_level` classifier's errors are one level out, which holds on its training data (74–99%) but not on unseen text (40% on Ace-CEFR). Tagger accuracies now say whether punctuation is included. Study 1's results now record the Dale–Chall difficult-word comparison they quote.
- The app now says "not counting numbers" wherever a diversity measure needs 50 words, and vocd-D needs more than 50.
- The `diversity` tiers note now cites TAALED's description of HD-D for grouping vocd-D with it.

## [0.3.2] - 2026-10-16

Fixes two tokenisation bugs found by validation Study 3. Output changes for texts that contain them. `schema_version` stays `2`.

### Fixed

- Words joined by an em or en dash next to a quote mark (`was—“impressively”—big`, `last”—then`) counted as one word and one diversity type. Em and en dashes, and quote marks touching them, now separate words. Study 3 found this in 53 of 300 texts; it moved MTLD by up to 22%. (Incomplete: typewriter dashes, brackets and some Unicode forms were fixed in 0.3.3.)
- Times, fractions and hyphenated number ranges (`11:00`, `1/4`, `3-4`) counted as words with no syllables and as diversity types. They're now numerals, read part by part ("three to four"). En-dash ranges (`1914–1918`) split into two numerals.

### Added

- Study 3 results (agreement with textstat, TAALED, lexicalrichness and lexical-diversity) in `docs/validation/`.

## [0.3.1] - 2026-10-16

Acts on validation Studies 2 and 5. `schema_version` stays `2`.

### Fixed

- A numeral with two or more dots (a section number such as `3.1.2`, a version, an IP address) raised an error and failed the whole analysis. It's now read as "three point one point two".

### Added

- `cefr.estimate_reliability`: `estimated_level_95th` is flagged unreliable under 50 words, a missing estimate is explained as "more than 5% of words beyond the C2 lists" rather than read as C2, and every result notes that it isn't a proficiency rating.
- Validation results for Studies 1, 2 and 5 in `docs/validation/`, summarised in VALIDITY.md.

### Changed

- The `cefr` caveat and the web app give Study 5's accuracy for `estimated_level_95th`: within one level of graded reading texts 84–89% of the time, exact 42–54%.
- The optional `cefr_level` classifier is labelled experimental, with its Study 5 result on unseen data (22% exact on short conversational passages).

## [0.3.0] - 2026-10-16

Output values are unchanged from 0.2.0; every change is an addition. `schema_version` stays `2`.

### Added

- `provenance` on every JSON result: the lexinspect version and spaCy model (`en_core_web_sm-3.8.0`) that produced it.
- `readability.validity`: what the published evidence supports. On the CLEAR corpus the classic formulas correlate r = .48–.56 with teachers' difficulty rankings, and `text_standard` has no validation of its own.
- `diversity.tiers`: MTLD and MATTR recommended, HD-D, vocd-D and Maas with care, TTR-family indices length-dependent (after Zenker & Kyle 2021). The web app groups the indices by tier.
- [VALIDITY.md](VALIDITY.md): intended and unintended uses, and the evidence behind each module.
- Golden-output tests (`tests/test_golden.py`) that fail CI on any unannounced output change, including a new learner-writing fixture.
- CodeQL and OpenSSF Scorecard workflows; GitHub Actions pinned to commit SHAs.

### Changed

- The CEFR caveat calls `estimated_level_95th` a rule of thumb, and the web app labels it that way.
- The Readability tab explains that the formulas are a rough guide.

### Fixed

- Documentation: the tagging gap between spaCy's small and large models is 0.09 points on spaCy 3.8's own benchmarks, not 2; the optional classifier downloads ~575 MB, not 400; it was trained on reading and writing, not listening; and its paper reports 75.8 weighted F1 on English, which CAVEATS now gives instead of the model card's 0.95.

## [0.2.0] - 2026-10-16

First public release: CLI, HTTP API and the hosted web app at lexinspect.dqnotes.com.

### Changed

- Every module counts from one shared tokenisation: contractions and hyphenated compounds are one word; clitics and possessives aren't tokens. Word, sentence and token counts differ from 0.1.
- Readability is computed by lexinspect rather than textstat, and `text_standard` is the median grade.
- BNC/COCA uses Nation's full word families (25 bands).
- Metadiscourse assigns each hit to one category after a context check.
- `schema_version` 2; `input.word_count` added to envelopes.

### Added

- A rebuilt web app with in-text highlighting, the Cloudflare Turnstile human check, and the `/comparison` page.
- vocd-D, spelling-variant lookups and spelling suggestions.

## 0.1.0 - 2026-05-06

Initial development; not tagged.

[0.3.2]: https://github.com/quangnd159/lexinspect/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/quangnd159/lexinspect/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/quangnd159/lexinspect/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/quangnd159/lexinspect/releases/tag/v0.2.0
