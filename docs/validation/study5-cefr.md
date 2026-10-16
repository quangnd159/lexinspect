# Study 5: CEFR accuracy

**Question.** Given English texts with known CEFR levels, how often does lexinspect's CEFR estimate get the level exactly right, or within one level?

**Short answer.** Not often enough to report a single level as *the* level of a text.

- **(a) `cefr.estimated_level_95th`.** On reading texts of 50+ words it lands within one level 84–89% of the time, but is exactly right only 43–54% of the time. It places C1–C2 texts about a level too low. On short sentences it overestimates by about one level, because a sentence with one rare word never reaches 95% coverage. On learner writing it carries almost no information (QWK 0.02–0.21; ICLE's within-one rate is below the always-guess-B2 baseline).
- **(b) The optional `cefr_level` classifier.** It scores 58–91% exact on UniversalCEFR data, but it was trained on that data, so those figures are inflated. On Ace-CEFR, the one dataset it hasn't seen, it is **22% exact and 54% within one level**, about 1.3 levels too low on average. That is worse than (a) on the same texts.
- **(c) A model on lexinspect's own features.** Fitted within each dataset, an ordinal model reaches 89–98% within one level and 40–64% exact. On Ace-CEFR it reaches QWK 0.82, against 0.88 for one trained rater scored against another, a comparison that favours the model (see Interpretation 5). Fitted once on reading texts and applied elsewhere, it is worse than (a) on Ace-CEFR (QWK 0.53 vs 0.69) and CEFR-SP (0.41 vs 0.47), similar on ReadMe++ (0.37 vs 0.35), and better on ICLE (0.32 vs 0.21) and CEFR-ASAG (0.48 vs 0.02). The features carry signal, but how they map to levels depends on the genre.

## Data

All data is downloaded by the script into `.cache/validation/study5/raw/` (gitignored) at pinned revisions with SHA-256 checks. Nothing is committed. No dataset used here is gated. EFCAMDAT, the bulk of UniversalCEFR's English data, needs registration and isn't used.

| Dataset | Text type | Construct | N | A1 / A2 / B1 / B2 / C1 / C2 | Median words | Licence | In classifier training? |
|---|---|---|---:|---|---:|---|---|
| Ace-CEFR (Kogan et al. 2025, arXiv:2506.14046, ancillary `ace_cefr_labeled.csv` v1) | Short conversational passages: written for the task, LLM-generated, learner chats, web | conversational | 890 | 127 / 143 / 164 / 188 / 145 / 123 | 10 | CC0 1.0 | **No** (out of distribution) |
| Cambridge exams (Xia et al. 2016), via UniversalCEFR `cambridge_exams_en` | Exam reading passages, KET–CPE | reading text written for a level | 331 | 0 / 64 / 60 / 71 / 67 / 69 | 561 | CC BY-NC-SA 4.0 | Yes |
| ELG-CEFR-EN (Breuker 2023), via UniversalCEFR `elg_cefr_en`, **minus Cambridge passages** | Reading texts written or graded for a level | reading text | 388 | 25 / 78 / 151 / 104 / 30 / 0 | 268 | CC BY-NC 4.0 (card) / CC BY-NC-SA 4.0 (records) | Yes |
| ICLE500 (Granger et al. 2020; Thwaites et al. 2024), via UniversalCEFR `icle500_en` | University EFL learners' argumentative essays | learner writing graded at a level | 488 | 0 / 1 / 114 / 218 / 91 / 64 | 580 | CC BY-NC 4.0 (card) / CC0 (records) | Yes |
| CEFR-ASAG (Tack et al. 2017), via UniversalCEFR `cefr_asag_en` | EFL learners' short answers | learner writing graded at a level | 299 | 18 / 59 / 113 / 74 / 30 / 5 | 58 | CC BY-NC-SA 4.0 | Yes |
| CEFR-SP (Arase et al. 2022), via UniversalCEFR `cefr_sp_en` | Single sentences rated by teachers | sentence | 10,004 | 124 / 1,271 / 3,305 / 3,330 / 1,744 / 230 | 13 | CC BY-NC-SA 4.0 | Yes |
| ReadMe++ English (Naous et al. 2024), via UniversalCEFR `readme_en` | Single sentences from 112 domains | sentence | 2,822 | 182 / 673 / 623 / 896 / 377 / 71 | 17 | CC BY-NC-SA 4.0 | Yes |

Notes on the data:

- **Folded levels.** Sub-levels (`A2+`, `B1+`, `B2+`) are folded into their base level. Ace-CEFR scores run 1–6 in half steps and are averaged over raters. They are mapped to the nearest level, with .5 rounded down so that A2+ stays A2, as the paper groups them.
- **Overlap between ELG and Cambridge.** ELG-CEFR-EN re-indexes 324 of the 331 Cambridge passages, all with the same level. They are removed from ELG here, so the two reading-text sets are independent. ELG is left with no C2 texts.
- **ICLE.** Seven essays labelled `NA` are dropped.
- **Classifier contamination.** The `cefr_level` model (`UniversalCEFR/ModernBERT-base-cefr-all-classifier`, revision `87f23fd`) was fine-tuned on UniversalCEFR. Its training log shows about 436k texts per epoch, about 86% of the corpus's 505k. Every UniversalCEFR text above has therefore probably been seen in training. **Its numbers on those datasets are not evidence of accuracy.** Ace-CEFR is not part of UniversalCEFR; only one of its 890 texts matches any UniversalCEFR English text.
- **Different constructs.** Reading texts are written or chosen for learners at a level. Learner writing is graded at the writer's proficiency. A B2 essay can be written in B1 vocabulary, so the two are reported separately. Sentence-level sets are a third kind again: whole-text measures computed on one sentence.

## Method

Each text is analysed by lexinspect 0.3.3 (spaCy `en_core_web_sm` 3.8.0).

| Estimator | What it does |
|---|---|
| Baseline | Always predicts the dataset's most frequent level. In-sample, so optimistic. |
| (a) `estimated_level_95th` | Used as shipped. When it is null (coverage never reaches 95%), it is scored as C2 and the null count is reported. Answered-only figures are in the JSON. |
| (b) `cefr_level.analyze` | Used as shipped, taking the top label. |
| (c) Ordinal model | Proportional-odds logistic regression on 24 existing lexinspect outputs: CEFR per-level coverage A1–C2, proper-noun and off-list share, BNC/COCA cumulative coverage at 1k–5k and 10k plus off-list share, words per sentence, syllables and characters per word, MTLD, MATTR, AWL coverage, and NGSL, NGSL+NAWL and off-list coverage. Text length is excluded on purpose, because longer texts mean higher levels in several of these corpora and the model would learn that instead of difficulty. Features are median-imputed (MTLD and MATTR are null under about 50 tokens) and standardised. The L2 penalty is chosen by inner 3-fold CV on QWK. |
| (c) within | Stratified 5-fold CV inside each dataset, seed 0. An upper bound: calibrated to that dataset. |
| (c) transfer | One model fitted on Cambridge + ELG reading texts (n = 718), then applied unchanged to every other dataset. This is what a level lexinspect shipped would face. |
| (c′) Ridge and round | Ridge regression rounded to the nearest level, as a robustness check. Its within-one accuracy agrees with (c) to within 3.3 points everywhere; exact accuracy differs by up to 11 points (Ace-CEFR: 36% vs 47%). |

Metrics:

- exact accuracy and within-one-level accuracy;
- macro-F1 over the levels present in each dataset's gold labels;
- quadratic weighted kappa (QWK);
- mean signed error in levels (positive means the estimate is too high);
- confusion matrices;
- results by length in lexinspect words.

With N ≈ 300–500, a percentage near 50% carries a 95% interval of roughly ±5 points.

## Results

### Headline

| Dataset | Estimator | N | Exact | Within 1 | Macro-F1 | QWK | Bias (levels) |
|---|---|---:|---:|---:|---:|---:|---:|
| **Ace-CEFR** (out of distribution) | Baseline (modal level) | 890 | 21% | 56% | 0.06 | 0.00 | +0.49 |
| | (a) estimated_level_95th | 890 | 36% | 73% | 0.32 | 0.69 | −0.23 |
| | (b) cefr_level classifier | 890 | **22%** | **54%** | 0.17 | 0.49 | **−1.33** |
| | (c) ordinal, trained on reading texts | 890 | 30% | 75% | 0.30 | 0.53 | −0.16 |
| | (c) ordinal, within-dataset CV | 890 | 47% | 90% | 0.48 | 0.82 | −0.04 |
| | *Human: rater 2 against rater 1* | *890* | *53%* | *96%* | – | *0.88* | *−0.10* |
| **Cambridge exams** (reading texts) | Baseline | 331 | 21% | 60% | 0.07 | 0.00 | −0.05 |
| | (a) estimated_level_95th | 331 | 54% | 89% | 0.54 | 0.75 | −0.34 |
| | (b) classifier *(seen in training)* | 331 | 87% | 99% | 0.87 | 0.96 | +0.06 |
| | (c) ordinal, within-dataset CV | 331 | 64% | 98% | 0.64 | 0.88 | −0.04 |
| **ELG-CEFR-EN** minus Cambridge (reading texts) | Baseline | 388 | 39% | 86% | 0.11 | 0.00 | −0.09 |
| | (a) estimated_level_95th | 388 | 43% | 84% | 0.33 | 0.55 | +0.31 |
| | (b) classifier *(seen in training)* | 388 | 68% | 96% | 0.66 | 0.78 | +0.26 |
| | (c) ordinal, within-dataset CV | 388 | 56% | 97% | 0.39 | 0.68 | +0.03 |
| **ICLE500** (learner essays) | Baseline | 488 | 45% | 87% | 0.12 | 0.00 | −0.21 |
| | (a) estimated_level_95th | 488 | 40% | 81% | 0.24 | 0.21 | −0.28 |
| | (b) classifier *(seen in training)* | 488 | 58% | 96% | 0.47 | 0.68 | +0.32 |
| | (c) ordinal, trained on reading texts | 488 | 41% | 87% | 0.26 | 0.32 | −0.38 |
| | (c) ordinal, within-dataset CV | 488 | 48% | 89% | 0.28 | 0.37 | −0.19 |
| **CEFR-ASAG** (learner short answers) | Baseline | 299 | 38% | 82% | 0.09 | 0.00 | −0.18 |
| | (a) estimated_level_95th | 299 | 25% | 62% | 0.21 | 0.02 | +0.42 |
| | (b) classifier *(seen in training)* | 299 | 78% | 94% | 0.75 | 0.81 | −0.20 |
| | (c) ordinal, trained on reading texts | 299 | 40% | 86% | 0.25 | 0.48 | −0.07 |
| | (c) ordinal, within-dataset CV | 299 | 40% | 89% | 0.24 | 0.50 | −0.02 |
| **CEFR-SP** (sentences) | Baseline | 10,004 | 33% | 84% | 0.08 | 0.00 | +0.40 |
| | (a) estimated_level_95th | 10,004 | 24% | 65% | 0.22 | 0.47 | +0.86 |
| | (b) classifier *(seen in training)* | 10,004 | 91% | 100% | 0.88 | 0.95 | −0.01 |
| | (c) ordinal, trained on reading texts | 10,004 | 32% | 78% | 0.24 | 0.41 | +0.24 |
| | (c) ordinal, within-dataset CV | 10,004 | 59% | 98% | 0.43 | 0.74 | +0.00 |
| **ReadMe++** (sentences) | Baseline | 2,822 | 32% | 67% | 0.08 | 0.00 | +0.71 |
| | (a) estimated_level_95th | 2,822 | 19% | 55% | 0.19 | 0.35 | +1.23 |
| | (b) classifier *(seen in training)* | 2,822 | 90% | 99% | 0.89 | 0.96 | −0.00 |
| | (c) ordinal, trained on reading texts | 2,822 | 24% | 66% | 0.20 | 0.37 | +0.89 |
| | (c) ordinal, within-dataset CV | 2,822 | 51% | 92% | 0.41 | 0.72 | +0.01 |

**Null estimates from (a).** The heuristic returns no level for:

- 225 of 890 Ace-CEFR texts;
- 21 of 331 Cambridge texts and 49 of 388 ELG texts;
- 40 of 488 ICLE essays and 63 of 299 short answers;
- 4,843 of 10,004 CEFR-SP sentences;
- 1,328 of 2,822 ReadMe++ sentences.

On answered texts only, it scores:

| Dataset | Exact | Within one | QWK | Bias |
|---|---:|---:|---:|---:|
| Ace-CEFR | 37% | 77% | 0.63 | −0.72 |
| Cambridge | 55% | 89% | 0.77 | −0.43 |
| ELG | 49% | 92% | 0.54 | +0.07 |
| ICLE | 40% | 83% | 0.16 | −0.43 |
| CEFR-SP | 42% | 91% | 0.56 | −0.06 |
| ReadMe++ | 32% | 81% | 0.46 | +0.36 |

**Comparison points from the literature.**

- **Ace-CEFR trained raters.** The paper reports QWK 0.89, with about 8% of labels more than one level apart on its half-step scale. On whole levels, rater 2 against rater 1 gives QWK 0.88, 53% exact and 4% two or more levels apart. Because the gold label averages the two raters, this is a lower bound on how reliable the gold label is.
- **Classifier paper.** Imperial et al. 2025 report 75.8 weighted F1 on English. Here its weighted F1 is 0.58–0.91 on data it was trained on, and **0.16 on Ace-CEFR**.

### Confusion matrices

Rows are gold levels, columns are predictions. For (a), the "null" column counts how many of the texts scored as C2 actually had no estimate.

**(a) estimated_level_95th: Cambridge exams**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 | of which null |
|---|---|---|---|---|---|---|---|
| A2 | 1 | 48 | 11 | 1 | 1 | 2 | 2 |
| B1 | 0 | 11 | 47 | 2 | 0 | 0 | 0 |
| B2 | 0 | 0 | 36 | 32 | 1 | 2 | 2 |
| C1 | 0 | 0 | 4 | 26 | 25 | 12 | 11 |
| C2 | 0 | 0 | 2 | 25 | 16 | 26 | 6 |

**(a) estimated_level_95th: Ace-CEFR**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 | of which null |
|---|---|---|---|---|---|---|---|
| A1 | 106 | 14 | 3 | 1 | 0 | 3 | 3 |
| A2 | 72 | 50 | 11 | 3 | 0 | 7 | 7 |
| B1 | 39 | 42 | 44 | 13 | 1 | 25 | 24 |
| B2 | 14 | 27 | 53 | 38 | 6 | 50 | 50 |
| C1 | 0 | 8 | 30 | 41 | 1 | 65 | 64 |
| C2 | 1 | 1 | 6 | 19 | 14 | 82 | 77 |

**(a) estimated_level_95th: ICLE500 (learner essays)**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 | of which null |
|---|---|---|---|---|---|---|---|
| A2 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| B1 | 0 | 0 | 48 | 52 | 4 | 10 | 9 |
| B2 | 0 | 2 | 69 | 128 | 8 | 11 | 9 |
| C1 | 0 | 0 | 19 | 57 | 4 | 11 | 9 |
| C2 | 0 | 0 | 7 | 38 | 6 | 13 | 13 |

**(b) cefr_level classifier: Ace-CEFR (out of distribution)**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 |
|---|---|---|---|---|---|---|
| A1 | 118 | 8 | 1 | 0 | 0 | 0 |
| A2 | 83 | 58 | 2 | 0 | 0 | 0 |
| B1 | 67 | 85 | 12 | 0 | 0 | 0 |
| B2 | 23 | 107 | 50 | 7 | 0 | 1 |
| C1 | 12 | 28 | 75 | 29 | 1 | 0 |
| C2 | 2 | 7 | 19 | 70 | 21 | 4 |

**(b) cefr_level classifier: Cambridge exams (seen in training)**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 |
|---|---|---|---|---|---|---|
| A2 | 0 | 60 | 4 | 0 | 0 | 0 |
| B1 | 0 | 3 | 47 | 9 | 1 | 0 |
| B2 | 0 | 0 | 0 | 58 | 12 | 1 |
| C1 | 0 | 0 | 0 | 0 | 63 | 4 |
| C2 | 0 | 0 | 0 | 1 | 9 | 59 |

**(c) ordinal model, within-dataset CV: Ace-CEFR**

| gold \ pred | A1 | A2 | B1 | B2 | C1 | C2 |
|---|---|---|---|---|---|---|
| A1 | 83 | 31 | 8 | 5 | 0 | 0 |
| A2 | 25 | 70 | 39 | 9 | 0 | 0 |
| B1 | 5 | 42 | 63 | 43 | 10 | 1 |
| B2 | 0 | 8 | 53 | 85 | 34 | 8 |
| C1 | 0 | 1 | 7 | 61 | 42 | 34 |
| C2 | 1 | 0 | 3 | 19 | 26 | 74 |

Every confusion matrix, for every estimator and dataset, is in `study5-cefr.json`.

### By text length

Each cell gives exact / within one / bias, with n.

| Dataset | Estimator | <20 words | 20–49 | 50–149 | 150–399 | 400+ |
|---|---|---|---|---|---|---|
| Ace-CEFR | (a) | 38% / 75% / −0.1 (723) | 27% / 65% / −0.6 (161) | 17% / 50% / −1.5 (6) | | |
| | (b) | 27% / 59% / −1.2 (723) | 4% / 33% / −1.8 (161) | 0% / 17% / −2.8 (6) | | |
| | (c) within | 46% / 90% / −0.1 (723) | 48% / 94% / +0.0 (161) | 67% / 100% / −0.3 (6) | | |
| Cambridge | (a) | | | 70% / 93% / +0.3 (57) | 69% / 98% / −0.2 (59) | 45% / 85% / −0.5 (215) |
| | (b) | | | 95% / 100% / −0.1 (57) | 85% / 98% / +0.1 (59) | 85% / 99% / +0.1 (215) |
| | (c) within | | | 72% / 96% / +0.1 (57) | 69% / 100% / +0.0 (59) | 60% / 97% / −0.1 (215) |
| CEFR-ASAG | (a) | 20% / 51% / −0.0 (55) | 24% / 55% / +0.7 (74) | 26% / 67% / +0.5 (141) | 38% / 79% / +0.3 (29) | |
| | (b) | 53% / 80% / −0.7 (55) | 85% / 96% / −0.1 (74) | 82% / 99% / −0.1 (141) | 93% / 97% / +0.1 (29) | |
| | (c) within | 35% / 78% / −0.2 (55) | 30% / 84% / +0.1 (74) | 46% / 94% / +0.0 (141) | 52% / 97% / −0.0 (29) | |
| ReadMe++ | (a) | 16% / 47% / +1.6 (1,639) | 23% / 65% / +0.8 (1,102) | 31% / 86% / +0.1 (81) | | |
| | (b) | 90% / 100% / +0.0 (1,639) | 90% / 99% / −0.0 (1,102) | 93% / 98% / −0.1 (81) | | |
| | (c) within | 51% / 91% / +0.0 (1,639) | 52% / 94% / −0.0 (1,102) | 49% / 88% / +0.2 (81) | | |
| CEFR-SP | (a) | 24% / 63% / +0.9 (8,437) | 26% / 72% / +0.6 (1,567) | | | |

ELG texts all fall in 150–399 except three. ICLE essays are all 400+. Both are in the JSON.

### What the ordinal model leans on

The transfer model was fitted on reading texts. All 24 of its standardised slopes are listed below, largest first; positive means a higher level. The features are strongly collinear, so individual slopes are unstable: read them together, not one at a time.

| Feature | Slope |
|---|---:|
| C2-word share | +1.142 |
| BNC/COCA 4k coverage | +0.915 |
| B1-word share | +0.762 |
| MTLD | +0.734 |
| words per sentence | +0.652 |
| BNC/COCA 5k coverage | −0.607 |
| NGSL+NAWL coverage | +0.587 |
| A1-word share | −0.571 |
| syllables per word | −0.544 |
| NGSL coverage | −0.415 |
| characters per word | −0.406 |
| B2-word share | +0.405 |
| A2-word share | +0.346 |
| C1-word share | +0.269 |
| CEFR off-list share | +0.203 |
| BNC/COCA 3k coverage | −0.189 |
| BNC/COCA 2k coverage | −0.169 |
| MATTR | +0.164 |
| BNC/COCA 1k coverage | +0.163 |
| NGSL off-list share | +0.117 |
| CEFR proper-noun share | −0.106 |
| AWL coverage | +0.086 |
| BNC/COCA 10k coverage | +0.046 |
| BNC/COCA off-list share | −0.016 |

The model is driven by the vocabulary profile, plus sentence length and lexical diversity.

## Interpretation

1. **The 95% rule of thumb is a rough vocabulary indicator, not a text level.** On reading passages of 50 words or more:
   - it is within one level 84–89% of the time (Cambridge 89%, ELG 84%) and exactly right about half the time;
   - that beats always guessing the commonest level on Cambridge (60% within one), but falls 2 points short of it on ELG (84% against 86%);
   - it reliably calls C1 and C2 passages B2 or C1 (bias −0.34 on Cambridge, and 25 of 69 C2 passages called B2), because CEFR-J/Octanove coverage saturates: most of the words in a C2 text are B2-or-lower words.
2. **It is close to meaningless on learner writing.** On ICLE essays, QWK is 0.21 and within one is 81%, against 87% for always saying B2. On short answers, QWK is 0.02. A learner's proficiency band isn't recoverable from which list levels their words come from. This is a different construct, and the module shouldn't be read that way.
3. **It is unreliable on very short texts.** Under 20 words:
   - one off-list word decides between a level and a null;
   - nulls are scored as C2 and give a positive bias of +0.9 to +1.6 on sentences;
   - within-one accuracy falls to 47–63%.

   Ace-CEFR is the exception (75% within one), because its A1–A2 items are so plain.
4. **The classifier's own high numbers can't be trusted here.**
   - It reaches 90%+ exact on CEFR-SP and ReadMe++ sentences. That is far above anything its paper reports (75.8 weighted F1 for English overall), which is what you'd expect from texts it was trained on.
   - On Ace-CEFR, which it hasn't seen, it is 22% exact (21% on Ace's own test split) and 54% within one, with bias −1.33. Always guessing the commonest level does about as well on exact accuracy (21%) and better within one (56%), though the classifier's predictions do track the levels (QWK 0.49 against 0). It is worse than (a).
   - It calls 96% of Ace B1–C2 items (595 of 620) a level or more too low, and gets worse as passages get longer (4% exact at 20–49 words).

   Ace-CEFR is short conversational text, which is a genre the classifier wasn't built for. So this result shows it doesn't generalise outside its training distribution; it doesn't by itself measure the contamination. Either way, lexinspect has no evidence that the classifier is more accurate than the heuristic on unseen text.
5. **The same features can do better, but only when calibrated to the genre.**
   - Fitted within a dataset, the ordinal model improves on (a) everywhere. Within one goes from 73% to 90% on Ace, 89% to 98% on Cambridge and 65% to 98% on CEFR-SP, and bias goes to about zero.
   - On Ace it comes within about 6 points of the rater-against-rater ceiling (QWK 0.82 against 0.88; 90% against 96% within one). The comparison favours the model: the ceiling scores one rater against the other, while the model is scored against the average of both raters.
   - Trained on reading texts and moved to another genre, it loses most of that. On Ace it gets QWK 0.53 against 0.69 for (a); on sentences, 0.37–0.41.

   A single fitted model shipped in lexinspect would replace a transparent rule of thumb with an opaque one that isn't much better outside its training genre.

## Recommendation for lexinspect

- **Don't present any single number as "the CEFR level of this text".** Keep the per-level coverage distribution as the primary output; it is what the evidence supports.
- **Keep `estimated_level_95th`, but rename how it is shown and add a range.** For example: "Vocabulary level (95% coverage, CEFR-J/Octanove): B1. Usually within one level of a text's graded level for reading passages; exact about half the time; tends to read C1–C2 texts as B2–C1." In the UI:
  - show it as a band ("about B1, range A2–B2") rather than a bare level (not yet done);
  - suppress it, or mark it unreliable, under 50 words (done in 0.3.1);
  - on null, say "more than 5% of words are beyond the C2 lists" rather than implying C2 (done in 0.3.1);
  - say outright that it describes the vocabulary used, not the writer's proficiency, so it shouldn't be used to grade learner writing (done in 0.3.1).
- **Keep `cefr_level` optional and change its caveat.** Its only out-of-distribution result here is 22% exact and 54% within one, about 1.3 levels too low. Its high scores on UniversalCEFR data reflect training overlap. Until it is validated on unseen documents, label it "experimental; trained on UniversalCEFR; unvalidated outside it" (done in 0.3.1). Don't show it for texts under 50 words (not yet done), and don't present it as more authoritative than the vocabulary profile.
- **Don't ship the ordinal model as a level.** It shows how much signal the features carry within a genre, not a portable estimator. A genre-specific calibrated model would need its own validation study.
- **Update VALIDITY.md and CAVEATS.md.**
  - Change the `cefr` row from "Planned: Study 5" to these figures (done in 0.3.1).
  - In `cefr_level`, keep the 75.8 weighted-F1 figure from the paper, and add that this study found 0.16 weighted F1 on unseen Ace-CEFR passages (not yet done).

## Limitations

- **Only one out-of-distribution set, and it is unusual.** Ace-CEFR passages are very short (median 10 words) and conversational, so its classifier result mixes domain shift with length. A held-out document-level reading set outside UniversalCEFR would be the right next test. No such set was found with an open licence.
- **Gold labels are noisy.**
  - ELG and Cambridge levels come from publishers' or exam-board grading.
  - ICLE levels come from crowdsourced comparative judgement, mapped to CEFR.
  - Ace-CEFR levels average two raters, and those raters agree with each other at QWK 0.88.
  - No estimator can be expected to exceed the agreement of the labels themselves.
- **Uneven coverage of levels.** ICLE has almost no A-level essays, ELG (after deduplication) has no C2, and CEFR-ASAG has 5 C2 answers. Macro-F1 is computed over the levels present.
- **Contaminated training data.** The UniversalCEFR train/test split for the classifier isn't published, so contaminated and clean UniversalCEFR texts can't be separated. All UniversalCEFR results for (b) should be read as optimistic.
- **Null handling.** Scoring a null from (a) as C2 is a choice. Answered-only figures are in the JSON and change the conclusions little, except on sentences, where nulls are about half the data.
- **Two lexinspect defects found on the way:**
  - Under 0.3.0, `readability.analyze` raised `ValueError` on a numeral with two or more dots, e.g. "see section 3.1.2". This hit 6 texts. Fixed in 0.3.1.
  - `diversity.analyze` returns `scores: {}` (no keys) for a text with no tokens, unlike its usual null-filled scores. Still open in 0.3.3; the script works around it.

## Reproduce

```
uv run --extra cefr-level --with scikit-learn --with pandas --with scipy python scripts/validation/study5_cefr/run.py
```

This downloads the open data if absent, then analyses about 15,400 texts and runs the classifier on each; expect tens of minutes on a laptop CPU. It writes `docs/validation/study5-cefr.json`, with provenance: lexinspect 0.3.3, `en_core_web_sm-3.8.0`, classifier revision `87f23fd44a4775a54b1648b39531593bfc4323c8`, and package versions. Full tables go to `.cache/validation/study5/tables.md`.

## References

- Arase, Y., Uchida, S., & Kajiwara, T. (2022). CEFR-based sentence-difficulty annotation and assessment. *EMNLP 2022*.
- Breuker, M. (2023). CEFR labelling and assessment services. In G. Rehm (Ed.), *European Language Grid*. Springer. doi:10.1007/978-3-031-17258-8_16
- Granger, S., Dupont, M., Meunier, F., Naets, H., & Paquot, M. (2020). *The International Corpus of Learner English, version 3*. Presses universitaires de Louvain.
- Imperial, J. M., et al. (2025). UniversalCEFR: Enabling open multilingual research on language proficiency assessment. *EMNLP 2025*. arXiv:2506.01419
- Kogan, D., Schumacher, M., Nguyen, S., Suzuki, M., Smith, M., Bellows, C. S., & Bernstein, J. (2025). Ace-CEFR: A dataset for automated evaluation of the linguistic difficulty of conversational texts for LLM applications. arXiv:2506.14046
- Naous, T., Ryan, M. J., Lavrouk, A., Chandra, M., & Xu, W. (2024). ReadMe++: Benchmarking multilingual language models for multi-domain readability assessment. *EMNLP 2024*.
- Tack, A., François, T., Roekhaut, S., & Fairon, C. (2017). Human and automated CEFR-based grading of short answers. *BEA 2017*.
- Thwaites, P., Vandeweerd, N., & Paquot, M. (2024). Crowdsourced comparative judgement for evaluating learner texts. *Applied Linguistics*.
- Xia, M., Kochmar, E., & Briscoe, T. (2016). Text readability assessment for second language learners. *BEA 2016*.
