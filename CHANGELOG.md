# Changelog

Every change to lexinspect's output is listed here, by version. Output is deterministic within a version (see [VALIDITY.md](VALIDITY.md#reproducibility)), so cite the version you ran. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/): until 1.0, a minor version may change output values.

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
