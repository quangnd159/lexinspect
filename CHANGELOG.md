# Changelog

Every change to lexinspect's output is listed here, by version. Output is deterministic within a version (see [VALIDITY.md](VALIDITY.md#reproducibility)), so cite the version you ran. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/): until 1.0, a minor version may change output values.

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

[0.3.0]: https://github.com/quangnd159/lexinspect/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/quangnd159/lexinspect/releases/tag/v0.2.0
