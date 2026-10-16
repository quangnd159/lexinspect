# Study 1: readability against human judgement

**Question.** How well do lexinspect's readability outputs track teachers' judgements of how hard a text is? Specifically: (a) do lexinspect's eight formulas correlate with human difficulty as strongly as the published values say they should, which checks that lexinspect computes them comparably; and (b) how much better can a simple, transparent model built from lexinspect's existing features do?

**Short answer.** The formulas behave as published: |r| = .43–.57 with teachers' ease scores, within about .01 of the published values for the five that were published. `text_standard` (the median of the eight) gets r = −.56, no better than the best single formula. A ridge model on 19 lexinspect features reaches cross-validated r = .65 (R² = .42), which is clearly better than any formula (the best, SMOG, has |r| = .57; Dale–Chall alone, cross-validated, gets r = .56, R² = .32). It still falls short of the CLEAR authors' 28-feature model (r = .71) and GPT-4 Turbo zero-shot (r = .76).

Results come from lexinspect 0.3.3 with `en_core_web_sm-3.8.0`. Every number below is in [`study1-readability.json`](study1-readability.json).

## Data

| | |
|---|---|
| Corpus | CommonLit Ease of Readability (CLEAR) corpus |
| Source | <https://github.com/scrosseye/CLEAR-Corpus>, file `CLEAR_corpus_final.xlsx` at commit `dbf1cf0df30bf6be8b0691d2c078b75043ca6199` (SHA-256 `e87a19a2…2cc7`, checked by the script) |
| Licence | CC BY-NC-SA 4.0, as stated in the repository README since 2024-04-17. CommonLit's 2021 announcement said MIT; we follow the stricter, more recent terms. The data is downloaded by the script into `.cache/validation/clear/` (gitignored) and is never committed. Only aggregate statistics are published here. Individual excerpts carry their own licences (most public domain, some CC). |
| N | 4,724 excerpts, 129–208 words each (median 176), US school reading for grades 3–12, literary and informational |
| Criterion | `BT_easiness`: a Bradley–Terry ease score fitted to 111,347 pairwise "which is easier?" judgements by 1,116 teachers. Higher means easier. Mean −0.96, SD 1.03, range −3.68 to 1.71, roughly symmetric (skew −0.13). |
| Citation | Crossley, S. A., Heintz, A., Choi, J. S., Batchelor, J., Karimi, M., & Malatinszky, A. (2023). A large-scaled corpus for assessing text readability. *Behavior Research Methods*, 55(2), 491–507. doi:10.3758/s13428-022-01802-x |

**Reliability of the criterion.** The paper reports split-half reliability only. BT scores fitted to two random halves of the judgements correlate r = .63 with each other and about .85 with the full-data scores; it gives no inter-rater figure. Two quick estimates put the reliability of the full-data scores at about .77, an approximation of ours that the paper does not report:

- Spearman–Brown on .63 gives .77.
- One minus the mean squared standard error over the score variance (mean s.e. 0.49, SD 1.03) also gives .77.

So, by this estimate, the ceiling for any predictor's correlation is roughly √.77 ≈ .88, not 1. Note too that the split-half .63 is a correlation between two *halves* of the judgements, so it is a lower bound on human agreement, not a target for a model.

## Method

1. **Features.** `pipeline.run_all(text, modules=[readability, statistics, diversity, awl, bnc_coca, ngsl, phrase, cefr])` on each excerpt exactly as given, newlines included. `errors`, `metadiscourse`, `tagger` and `profile` were skipped because no feature uses them, and skipping them doesn't change the others. Features are cached per lexinspect and spaCy version in `.cache/validation/`.
2. **Formula correlations.** Pearson and Spearman correlations of `BT_easiness` with each of the eight formula scores and `text_standard`. 95% CIs come from the Fisher z transform (for Spearman, with the Bonett–Wright standard error). For the five formulas whose scores the CLEAR file also ships (computed by the authors with ARTE 1.1), we also report:
   - the correlation of the file's score with BT on the same texts;
   - the correlation between lexinspect's score and the file's;
   - a paired bootstrap CI (2,000 resamples) for the difference in |r|.
3. **Models.** Three feature sets, fixed before any model was run:
   - **surface_3:** words per sentence, syllables per word, characters per word.
   - **surface_plus_dale_chall_4:** the above plus the share of Dale–Chall difficult words.
   - **full_19:** the above plus:
     - CEFR token shares at A2, B1, B2, C1, C2 and off-list (A1 is the reference);
     - BNC/COCA share of tokens beyond K1, K2, K3 and K5 (proper nouns and supplementary lists count as known);
     - AWL coverage, NGSL coverage, MTLD, MATTR, and PHRASE List hits per 1,000 words.

   Each model is a standardised ridge regression (`StandardScaler` → `RidgeCV`, 29 alphas from 10⁻³ to 10⁴). Alpha is chosen by leave-one-out *inside each training fold*, so the test fold never influences it (nested CV). Evaluation is 10-fold CV repeated with 5 shuffling seeds. We report out-of-fold r, R² and RMSE as mean ± SD across seeds, plus the per-fold mean. OLS and single-formula linear fits go through the same folds for comparison. Coefficients come from one fit on all 4,724 texts.
4. **Checks.** Failures, missing values, distributions, intercorrelations of the formulas, variance inflation factors (VIF), and agreement with the authors' own formula scores.

## Results

### Data checks

- **Failures and missing values.** lexinspect analysed all 4,724 excerpts with no exceptions and no missing values (MTLD and MATTR were defined everywhere). No excerpt is under 100 words, so none is flagged unreliable.
- **Sentence counts.** These agree with the corpus's own `Sentence Count` column at r = .99, and are identical for 83% of excerpts. lexinspect finds 0.2 fewer sentences on average.
- **Outliers.** A handful of excerpts are one or two sentences of 90+ words, such as treaty text and diplomatic memoirs. They produce extreme grades: FKGL up to 42.8, ARI 51.4, Linsear Write 112.6. The ARTE scores in the file show the same extremes, so this is how the formulas behave on such text, not a lexinspect fault. The models use syllables per word and similar averages, not the formulas, so they are not dominated by these cases.
- **The anchor text.** One text has `s.e.` = 0. It is presumably the Bradley–Terry reference text, fixed at 0. It was kept.

### Formula correlations with BT_easiness (N = 4,724)

Higher BT_easiness means easier, so grade-level formulas correlate negatively and Flesch Reading Ease positively.

| Formula | Pearson r [95% CI] | Spearman ρ [95% CI] | Published \|r\| | CLEAR-file score r (same texts) | r(lexinspect, CLEAR file) |
|---|---|---|---|---|---|
| Flesch Reading Ease | .548 [.527, .567] | .563 [.542, .584] | .55 | .547 | .974 |
| Flesch–Kincaid Grade | −.525 [−.545, −.504] | −.556 [−.577, −.535] | .52 | −.517 | .977 |
| Gunning Fog | −.515 [−.535, −.493] | −.542 [−.563, −.520] | not tested | | |
| SMOG | −.571 [−.590, −.552] | −.579 [−.600, −.559] | .56 | −.563 | .961 |
| ARI | −.485 [−.506, −.463] | −.521 [−.543, −.498] | .48 | −.485 | .981 |
| Coleman–Liau | −.478 [−.500, −.456] | −.492 [−.514, −.468] | not tested | | |
| Dale–Chall (raw score) | −.562 [−.582, −.543] | −.594 [−.613, −.573] | .56 (New Dale–Chall) | −.558 | .840 |
| Linsear Write | −.434 [−.457, −.411] | −.483 [−.506, −.459] | not tested | | |
| `text_standard` (median grade) | −.559 [−.578, −.539] | −.575 [−.595, −.554] | none | | |

**Comparability check: passed.** For every published formula, lexinspect's |r| is within about .01 of the published value: within .005 for four of them, and .011 above it for SMOG (.571 against .56). The direct test is against the CLEAR-file scores on the same texts. There lexinspect's |r| differs from the file score's by .008 at most, and the paired bootstrap CI for each difference includes zero or lies within ±.017. lexinspect's FKGL and SMOG are very slightly *more* predictive (+.008 each; CIs [.002, .014] and [.001, .015]). The eight formulas intercorrelate highly (FKGL vs ARI .98, vs Gunning Fog .98, vs `text_standard` .98), so they largely duplicate one another.

### Models (10-fold CV × 5 seeds, nested alpha; N = 4,724)

| Model | Features | CV r (mean ± SD over seeds) | CV R² | CV RMSE | Per-fold r (mean ± SD) |
|---|---|---|---|---|---|
| Flesch Reading Ease alone (OLS) | 1 | .547 ± .000 | .300 | .865 | .547 ± .032 |
| `text_standard` alone (OLS) | 1 | .558 ± .000 | .312 | .858 | .559 ± .030 |
| Dale–Chall alone (OLS) | 1 | .562 ± .000 | .316 | .855 | .562 ± .029 |
| surface_3 (ridge) | 3 | .551 ± .000 | .304 | .863 | .551 ± .031 |
| surface + Dale–Chall % (ridge) | 4 | .591 ± .000 | .349 | .834 | .591 ± .026 |
| **full_19 (ridge)** | 19 | **.650 ± .001** | **.422** | **.786** | .650 ± .022 |
| *Reference:* CLEAR paper, 28 of 107 NLP features | 28 | .712 | .507 | .726 | |
| *Reference:* GPT-4 Turbo zero-shot (Trott & Rivière 2024) | | .76 | | | |
| *Reference:* BT split-half (two halves of the raters) | | .63 | | | |

Ridge and OLS gave the same CV r to three decimals for every set: with 4,724 texts and at most 19 features, overfitting is not the issue. The selected alpha was 17.8 in every fold for full_19.

### Coefficients (full_19, standardised, fit on all texts; alpha = 17.8)

Sign convention: negative means harder.

| Feature | β | Single-feature r with BT | VIF |
|---|---|---|---|
| characters_per_word | +0.306 | −.41 | 8.4 |
| words_per_sentence | −0.277 | −.37 | 1.1 |
| dale_chall_difficult_pct | −0.271 | −.51 | 12.5 |
| syllables_per_word | −0.250 | −.45 | 10.3 |
| ngsl_pct | +0.185 | +.38 | 3.0 |
| cefr_off_list_pct | −0.179 | −.44 | 4.0 |
| bnc_beyond_k3_pct | +0.177 | −.34 | 7.7 |
| mtld | −0.101 | −.12 | 3.2 |
| cefr_C1_pct | −0.101 | −.25 | 1.2 |
| bnc_beyond_k5_pct | −0.100 | −.31 | 3.6 |
| cefr_B2_pct | −0.096 | −.35 | 1.8 |
| bnc_beyond_k1_pct | +0.092 | −.49 | 12.1 |
| cefr_B1_pct | −0.083 | −.35 | 2.9 |
| cefr_C2_pct | −0.081 | −.22 | 1.1 |
| cefr_A2_pct | −0.047 | −.19 | 1.5 |
| bnc_beyond_k2_pct | −0.043 | −.49 | 11.1 |
| mattr | +0.033 | −.09 | 3.1 |
| awl_pct | +0.015 | −.34 | 3.9 |
| phrase_per_1000 | −0.006 | +.08 | 1.1 |

**Multicollinearity.** Word length (characters and syllables), Dale–Chall difficult words and the nested BNC/COCA "beyond Kn" shares have VIFs of 8–12. Their individual coefficients are not interpretable on their own. Positive βs for characters per word, beyond-K1 and beyond-K3, where the raw correlations are negative, are suppression effects among correlated predictors, not evidence that longer or rarer words make text easier. Read them as a block: the word-difficulty block and sentence length carry most of the weight, CEFR level shares add a little, and diversity (MTLD, MATTR), AWL and phrase density add almost nothing once vocabulary level is in.

## What this means

- **lexinspect computes the classic formulas comparably to the published tool.** On 4,724 texts, its scores correlate .96–.98 with the authors' ARTE scores for Flesch, FKGL, SMOG and ARI, and they predict teacher judgements just as well, to within .01.
- **Each formula explains about a quarter to a third of the variation in teachers' judgements.** That is real but modest. Choosing among them barely matters, and `text_standard` is about as good as the best of them without being better.
- **Vocabulary profiles add real information.** Adding lexinspect's word-level features (Dale–Chall familiarity, CEFR levels, frequency bands, NGSL) to sentence and word length raises cross-validated r from .55 to .65 and R² from .30 to .42. A teacher choosing texts should read the vocabulary profile, not just the grade.
- **lexinspect is not a state-of-the-art difficulty predictor.** The CLEAR authors' model, with cohesion, semantic and syntactic indices lexinspect doesn't compute, reaches .71; a large language model reaches .76. Our estimate of the criterion's reliability (about .77) puts the ceiling for any predictor near .88, so there is room left that lexinspect's features don't reach.

## Observations for lexinspect

These are notes, not bugs.

- **Dale–Chall differs most from ARTE** (r = .84 between the two scores; lexinspect's is 1.2 lower on average), yet predicts equally well (|r| .562 vs .558). The difference comes from two places:
  - lexinspect applies the Chall & Dale (1995) counting rules: inflections of familiar words, proper names and numerals count as familiar. So it finds fewer difficult words: a mean of 14.5% of words, against 19.6% implied by the ARTE scores (inverting the formula with the CLEAR file's word and sentence counts; 22 of the 4,724 excerpts can't be inverted consistently and are left out; `checks.agreement_with_clear_file_scores.dale_chall_difficult_pct`).
  - Below 5% difficult words the formula drops its +3.6365 constant. 15% of CLEAR excerpts fall there, so the score has a step at 5%.

  Both follow the published definition. In passing, we noticed that a version without the step correlates slightly better (−.573). That was not tested properly and is not a recommendation.
- **Numerals are read aloud for syllables** ("41.7%" counts as 8 syllables, "-143,188" as 14). On statistics-heavy excerpts this pushes syllables per word, and so FKGL, SMOG and Flesch, well above ARTE's. One census excerpt has 2.33 syllables per word in lexinspect against about 1.5 for ARTE. This explains most of lexinspect's mean offsets from ARTE: Flesch −3.6, FKGL +0.6, SMOG +1.0. It is a deliberate design choice and does not hurt the correlations, but users comparing absolute scores with other tools should expect it.
- **Sentence segmentation** is not where the differences lie. Where lexinspect's FKGL differs from ARTE's by 10+ grades on texts with only two sentences, ARTE's scores imply *more* sentences than the corpus's own sentence count. ARTE splits differently, likely at semicolons or colons. lexinspect matches the corpus's count.

## Limitations

- **Population.** CLEAR is US school reading (grades 3–12) judged by US teachers for first-language students. Nothing here validates lexinspect for second-language readers, adult learners or CEFR levels.
- **Criterion.** The criterion is teachers' *comparative* judgement of difficulty, not measured comprehension. It is reliable at about .77, not perfectly.
- **Text type.** Excerpts are 129–208 words of edited prose, most of it from before 1950. Results may not carry over to short texts, learner writing or other genres.
- **Feature set.** The model uses only features lexinspect computes today. It is a lower bound on what lexinspect's *outputs* can tell you, not a proposed scoring formula, and its coefficients should not be used as one: they are fitted to this corpus and are collinear.
- **Comparing with the reference models.** The CLEAR paper's r = .71 used stepwise feature selection within its CV, and GPT-4's r = .76 is from a different evaluation. Neither is directly comparable to our nested CV. Published formula values were read from the paper's Figure 2 as cited in VALIDITY.md. The same-text CLEAR-file correlations in the table are the more exact comparison.
- **Version.** All numbers are for lexinspect 0.3.3 with `en_core_web_sm-3.8.0` and may move slightly with later releases. The JSON records the provenance.

## Reproduce

```sh
uv run --with scikit-learn --with pandas --with openpyxl --with scipy python scripts/validation/study1_readability/run.py
```

This downloads the corpus if it is absent, verifies its checksum, analyses each excerpt (about one minute on six cores; cached afterwards) and rewrites `docs/validation/study1-readability.json`.

## References

- Bonett, D. G., & Wright, T. A. (2000). Sample size requirements for estimating Pearson, Kendall and Spearman correlations. *Psychometrika*, 65(1), 23–28.
- Choi, J. S., & Crossley, S. A. (2020). ARTE: Automatic Readability Tool for English (version 1.1).
- Crossley, S. A., Heintz, A., Choi, J. S., Batchelor, J., Karimi, M., & Malatinszky, A. (2023). A large-scaled corpus for assessing text readability. *Behavior Research Methods*, 55(2), 491–507. doi:10.3758/s13428-022-01802-x
- Trott, S., & Rivière, P. (2024). Measuring and modifying the readability of English texts with GPT-4. *Proceedings of the Third Workshop on Text Simplification, Accessibility and Readability (TSAR 2024)*, 126–134.
