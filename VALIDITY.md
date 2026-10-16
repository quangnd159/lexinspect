# Validity

What each lexinspect number is for, what it isn't for, and what evidence stands behind it. [CAVEATS.md](CAVEATS.md) lists the known limitations in detail; this file is the other half, the evidence.

## Intended uses

lexinspect describes English texts. It's built for:

- **Teaching and materials work:** choosing or adapting reading texts, checking the vocabulary load of a worksheet, giving learners feedback on their own writing.
- **Research description:** reporting the readability, vocabulary profile, diversity or metadiscourse of a corpus, with the version cited (see [Reproducibility](#reproducibility)).
- **Diagnosis and triage:** spotting the words or sentences that make a text hard, or the spelling slips in a draft, for a person to look at.

## Not intended for

- **High-stakes decisions about people:** admissions, placement, grading, certification or progression. No lexinspect number has been validated for these, and none should decide them, alone or as a fixed weight in a formula.
- **Judging an individual student without a teacher's review.** Scores on one short text are noisy; see the length notes per module.
- **Detecting AI-written or plagiarised text.** lexinspect has no such feature, and none of its measures should be read as one.

## Two kinds of evidence

Each module below is rated on both.

- **Computation:** does lexinspect compute the published definition correctly? Checked by tests against hand-worked values or reference implementations, and frozen by golden-output tests so results change only in a versioned release.
- **Meaning:** does the measure track what people take it to measure, such as difficulty, proficiency or diversity? This comes from the research literature on the measure, and, where noted, from lexinspect's own validation studies.

## Per module

| Module | Computation | Meaning: what the research supports | lexinspect's own validation |
|---|---|---|---|
| `readability` | Each formula is tested against values worked by hand from its published definition (`tests/test_readability_formulas.py`). Syllables come from CMUdict; the fallback rule is about 90% exact against CMUdict (`tests/test_syllables.py`). | **Weak.** On the CLEAR corpus (4,724 school reading excerpts ranked by teachers), Flesch, Flesch–Kincaid, ARI, SMOG and New Dale–Chall correlate r = .48–.56 with the teachers' ease scores (Crossley et al. 2023). Coleman–Liau and Linsear Write weren't tested. The formulas largely duplicate each other, and `text_standard` (their median) has no validation of its own. Normed on 20th-century US native-speaker readers. | **[Study 1](docs/validation/study1-readability.md):** on CLEAR, lexinspect's formulas reproduce the published correlations within .01 (\|r\| = .43–.57). A ridge model on 19 lexinspect features reaches cross-validated r = .65, against .71 for the CLEAR authors' 28-feature model and a reliability ceiling of about .88. **[Study 3](docs/validation/study3-agreement.md):** given the same counts, Flesch, Flesch–Kincaid, SMOG, ARI and Coleman–Liau match textstat exactly (r = 1.000). On raw text they differ (r = .90–.92 for most) because of documented counting choices: numerals read aloud, `U.S.` kept as one word, Gunning's and Chall & Dale's word rules. |
| `statistics` | Counts from the shared tokenisation; tested in `tests/test_statistics.py` and `tests/test_consistency.py`. | Descriptive counts; no construct claim. | Golden outputs (Study 6) |
| `diversity` | Formulas checked against independent re-implementations of lexicalrichness on identical token lists (`tests/test_diversity.py`). vocd-D is seeded, so it is deterministic. | **Good for MTLD and MATTR**, which are the most stable across text lengths from about 50 tokens (Zenker & Kyle 2021, 4,542 EFL essays; McCarthy & Jarvis 2010). HD-D, vocd-D and Maas: use with care. TTR and its transforms, and MSTTR, depend on text length. Results carry these `tiers`. | **[Study 3](docs/validation/study3-agreement.md):** on 300 open texts, given the same tokens, MATTR, HD-D, MSTTR, TTR, MTLD and vocd-D are identical to lexicalrichness and lexical-diversity (r = 1.000), and MTLD agrees with TAALED at r = .995. With each tool's own tokenisation, agreement with lexicalrichness stays at r ≥ .978. |
| `tagger` | spaCy `en_core_web_sm` 3.8: 97.29% tag accuracy and 89.92 labelled attachment on OntoNotes (spaCy's own release figures). | On written learner English, taggers trained on edited text make roughly two to three times as many errors (Berzak et al. 2016). Tags feed every vocabulary profile. | **[Study 2](docs/validation/study2-tagger.md):** on spoken learner English (UD ESLSpok), `sm` tags 95.3% of words correctly (UPOS) against 95.8% for `trf`. Tagging errors change 1.5% of what lexinspect reports per word, mostly function words moving between A1 and A2; `trf` would fix 0.4% at about 70 times the size. `estimated_level_95th` shifts by one level in about one text in five under either model. |
| `cefr` | Lookups tested in `tests/test_cefr.py`. | **Word-level only.** CEFR-J and Octanove give the level at which a word is typically learned. Reporting which levels a text's words come from is well established. `estimated_level_95th` (the lowest level covering 95% of words) is a rule of thumb. | **[Study 5](docs/validation/study5-cefr.md):** on graded reading texts of 50+ words, `estimated_level_95th` is within one level 84–89% of the time but exact only 42–54%, and rates C1–C2 texts low. On learner writing it carries almost no information (QWK 0.01–0.21). Results now flag it as unreliable under 50 words. |
| `bnc_coca`, `ngsl`, `awl` | Lookups tested per list. | **Established.** Frequency-band profiles and coverage thresholds (95% for adequate, 98% for comfortable reading) are standard in vocabulary research (Laufer & Ravenhorst-Kalovski 2010; Nation 2006). Word families versus lemmas remains debated. | Golden outputs (Study 6) |
| `phrase` | Matching rules tested in `tests/test_phrase.py`. | The PHRASE List itself is corpus-derived (Martinez & Schmitt 2012). No published precision or recall exists for automatic detection of its expressions. | Planned: Study 4 |
| `metadiscourse` | Marker matching and context rules tested in `tests/test_metadiscourse.py`. | Hyland's (2005) taxonomy is widely used, but markers are polysemous and no published precision or recall exists for automatic counting. | Planned: Study 4 |
| `errors` | Hunspell via spylls, with en_GB and en_US dictionaries. | On misspellings in learner TOEFL essays, Hunspell detection reached precision .81 and recall .99, and put the right correction first 68% of the time (Bexte et al. 2022). Real-word errors (*their*/*there*) are not detected. | Golden outputs (Study 6) |
| `cefr_level` (optional) | Runs the UniversalCEFR ModernBERT classifier unchanged. | **Modest.** 75.8 weighted F1 on English in its paper (Imperial et al. 2025); within-one-level accuracy not reported; C1–C2 barely represented in training. The model card's 0.95 is from an unspecified split and isn't comparable. Not in the hosted app. | **[Study 5](docs/validation/study5-cefr.md):** on Ace-CEFR, the one test set outside its training data (short conversational passages), 22% exact and 54% within one level, about 1.3 levels too low. Scores on UniversalCEFR data (58–91% exact) are inflated by training overlap. Labelled experimental. |

## Validation studies

Each study publishes its scripts and results under `docs/validation/`. Datasets with non-commercial licences are downloaded by the scripts, never committed.

| Study | Question | Data | Status |
|---|---|---|---|
| 1. Readability | How well do lexinspect's features predict teachers' difficulty rankings? | CLEAR corpus | **Done:** [results](docs/validation/study1-readability.md) |
| 2. Tagger on learner English | How often does the tagger mislabel learner English, and how often does that change a reported CEFR level or frequency band? | UD ESLSpok (learner speech) and UD EWT (web text); the written Treebank of Learner English needs Cambridge's approval to publish results | **Done:** [results](docs/validation/study2-tagger.md) |
| 3. Agreement with reference tools | Do lexinspect's indices match TAALED, textstat and lexicalrichness on the same texts? | 300 open texts: Project Gutenberg, Simple and English Wikipedia, ELLIPSE learner essays | **Done:** [results](docs/validation/study3-agreement.md). Found and fixed two bugs (0.3.2) |
| 4. Metadiscourse and phrase accuracy | What share of flagged markers and phrases are correct? | About 1,000 hits per module, labelled independently by two language models and checked against a human-labelled sample | Planned |
| 5. CEFR accuracy | How often is the CEFR estimate exact, or within one level? | 15,222 texts with known levels: Ace-CEFR and six UniversalCEFR subsets | **Done:** [results](docs/validation/study5-cefr.md) |
| 6. Golden outputs | Does the same text always give the same output within a version? | Fixtures in `tests/fixtures/` | **Done:** `tests/test_golden.py` fails CI on any unannounced change |

## Reproducibility

Every JSON result records `provenance`: the lexinspect version and the spaCy model that produced it. Within a version, output is deterministic and frozen by the golden-output tests; changes between versions are listed in [CHANGELOG.md](CHANGELOG.md). To cite lexinspect, use [CITATION.cff](CITATION.cff) with the version you ran, and cite the word lists and formulas you report on (see `src/lexinspect/data/SOURCES.md`).

## References

- Bexte, M., Laarmann-Quante, R., Horbach, A., & Zesch, T. (2022). LeSpell: A multi-lingual benchmark corpus of spelling errors to develop spellchecking methods for learner language. *LREC 2022*, 697–706.
- Berzak, Y., et al. (2016). Universal Dependencies for learner English. *ACL 2016*.
- Crossley, S. A., Heintz, A., Choi, J. S., Batchelor, J., Karimi, M., & Malatinszky, A. (2023). A large-scaled corpus for assessing text readability. *Behavior Research Methods*, 55(2), 491–507. doi:10.3758/s13428-022-01802-x
- Hyland, K. (2005). *Metadiscourse: Exploring interaction in writing*. Continuum.
- Imperial, J. M., Barayan, A., Stodden, R., et al. (2025). UniversalCEFR: Enabling open multilingual research on language proficiency assessment. *EMNLP 2025*. arXiv:2506.01419
- Laufer, B., & Ravenhorst-Kalovski, G. C. (2010). Lexical threshold revisited. *Reading in a Foreign Language*, 22(1), 15–30.
- Martinez, R., & Schmitt, N. (2012). A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.
- McCarthy, P. M., & Jarvis, S. (2010). MTLD, vocd-D, and HD-D: A validation study of sophisticated approaches to lexical diversity assessment. *Behavior Research Methods*, 42(2), 381–392.
- Nation, I. S. P. (2006). How large a vocabulary is needed for reading and listening? *Canadian Modern Language Review*, 63(1), 59–82.
- Zenker, F., & Kyle, K. (2021). Investigating minimum text lengths for lexical diversity indices. *Assessing Writing*, 47, 100505.
