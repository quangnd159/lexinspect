# Study 2: Tagger accuracy on learner English

**Status:** done, for lexinspect 0.3.0 with `en_core_web_sm-3.8.0` (and `en_core_web_trf-3.8.0` for comparison). All numbers below come from [`study2-tagger.json`](study2-tagger.json), which records provenance, data checksums and every figure quoted here.

## Question

lexinspect tags every text with spaCy `en_core_web_sm`. The tags decide which part of speech picks a word's CEFR level, which lemma a word is looked up by, and whether an off-list word counts as a proper noun. So we asked three things:

1. How accurate is `sm` on learner English, and on edited text for comparison?
2. How much better is the transformer model, `en_core_web_trf`?
3. Most important: how often does a tagging difference change what lexinspect actually reports? That means a token's CEFR level, its BNC/COCA band, its NGSL/NAWL or AWL status, its proper-noun status, and each text's coverage percentages.

## Data

| | Learner English | Baseline |
|---|---|---|
| Treebank | UD_English-ESLSpok, all splits (train + dev + test) | UD_English-EWT, test split |
| What it is | Transcribed speech of Japanese learners of English, from NICT JLE oral proficiency interviews | Edited English web text: blogs, reviews, emails, newsgroups, answers |
| Release | UD r2.18 | UD r2.18 |
| Licence | CC BY-SA 4.0 | CC BY-SA 4.0 |
| Sentences / tokens | 2,320 / 21,312 | 2,077 / 25,094 |
| lexinspect lexical tokens | 17,438 | 21,143 |
| Texts (≥150 words) | 116 | 138 |
| Gold annotation | XPOS (Penn Treebank) manual; UPOS converted from XPOS and checked manually; **no lemmas** | UPOS, XPOS, lemmas, all manual |

**Why not the Treebank of Learner English (TLE, UD_English-ESL)?** Its annotations are CC BY-SA 4.0 but are released without the text. The text comes from the Cambridge CLC FCE Dataset. To get it you have to fill in a registration form and accept a licence agreement with Cambridge University Press & Assessment. That licence allows non-commercial research and educational use only. It also says: "Do not release items (e.g. models, data statistics) derived from the corpus without prior approval of CUP&A." Publishing this study's numbers from TLE would therefore need Cambridge's approval, and nobody can sign that agreement on the project's behalf by script. We used ESLSpok instead. It is the only freely available UD treebank of learner English that includes its text. Unlike TLE, it is spoken rather than written, and every speaker shares one first language (see Limitations).

Data are downloaded by the script into `.cache/validation/study2/` (gitignored) and are never committed. SHA-256 checksums are in the JSON.

## Method

**Same tokens everywhere.** For every text we build a spaCy `Doc` from the treebank's own tokens and sentence boundaries. Each model then tags that Doc, so tokenisation and sentence splitting are identical across conditions and only tagging and lemmatisation differ. In real use, spaCy also tokenises the text itself, so tokeniser errors on learner spelling are not measured here. ESLSpok gives only space-separated tokens, so before building the Docs we restore normal spacing (`do n't` becomes `don't`, `part - time` becomes `part-time`, no space before punctuation). This affects only how lexinspect groups tokens into words, never the tags.

**Three conditions per token.**

- `sm`: `en_core_web_sm` 3.8.0, loaded through lexinspect's own loader (`lexinspect._nlp.get_nlp`, NER excluded).
- `trf`: `en_core_web_trf` 3.8.0, through the same loader, on CPU.
- `gold`: the treebank's XPOS and UPOS. Morphology comes from spaCy's tag map, and lemmas come from spaCy's rule lemmatiser run over the gold tags, because ESLSpok has no gold lemmas. On EWT we also report `gold+lemma`, which uses the treebank's own lemmas.

**Accuracy** is the share of tokens whose predicted UPOS, XPOS or lemma equals the gold value, over all tokens and over lexinspect's lexical tokens. "Lenient XPOS" counts two convention differences as correct. ESLSpok tags every *to* as `TO`, where spaCy, following OntoNotes, tags prepositional *to* as `IN`, and treebanks disagree on quote-mark tags.

**Impact on lexinspect.** From each tagged Doc we build a lexinspect `Analysis` using the same word and sentence grouping as `lexinspect._text.analyse`. We then classify each lexical token with lexinspect's own lookups:

- CEFR: `lookup` on `cefr_entries`, then `_lists.cefr_level` by UPOS, or proper/off-list.
- BNC/COCA: `bnc_coca.classify`.
- NGSL, then NAWL, then proper/off-list.
- AWL sublist.

For each text we also run lexinspect's module functions themselves (`cefr.analyze`, `bnc_coca.analyze`, `ngsl.analyze`, `awl.analyze`). A check asserts that the per-token classifications add up to exactly the modules' counts. A "lexical token" is lexinspect's `content_tokens`: every word part except clitics, numbers and codes, so function words are included. Lexical tokens depend only on the text, so they line up one to one across conditions.

**Texts** are runs of consecutive whole sentences totalling at least 150 words, about one short learner essay. ESLSpok's sentences are a random sample, so we sort them by interview file first, which keeps one speaker's sentences together where possible. 95% confidence intervals come from a bootstrap that resamples texts (1,000 replicates, fixed seed).

**Speed** is measured by feeding each study text as a raw string through lexinspect's pipeline, one text per call (as `parse()` does), after a warm-up. That covers tokeniser, tagger, parser, attribute ruler and lemmatiser, on an Apple M3 Pro CPU with PyTorch using 5 threads. **Size** is the installed size of the model package, plus everything the trf model pulls in.

## Results

### 1. Tag accuracy (all tokens)

| | Learner (ESLSpok) `sm` | Learner `trf` | Baseline (EWT) `sm` | Baseline `trf` |
|---|---|---|---|---|
| UPOS | 95.3% [94.9–95.6] | 95.8% [95.5–96.1] | 92.5% [91.8–93.1] | 94.3% [93.8–94.8] |
| XPOS | 95.4% [95.0–95.7] | 96.0% [95.7–96.3] | 92.2% [91.6–92.8] | 94.7% [94.1–95.1] |
| XPOS, lenient | 96.7% [96.4–97.0] | 97.4% [97.1–97.6] | 92.3% | 94.7% |
| Lemma, exact / ignoring case | n/a (no gold) | n/a | 94.3% / 97.2% | 95.1% / 97.4% |
| Proper-noun tag (NNP/NNPS) precision / recall | 82.9% / 97.1% | 88.4% / 98.6% | 74.6% / 93.0% | 84.5% / 96.8% |

On lexical tokens alone, accuracy is within about 1 point of these figures (JSON: `*_lexical_tokens`).

Two things stand out. First, both models score below spaCy's in-domain OntoNotes figure (97.3% for `sm`) on both datasets. Second, the learner speech is *easier* to tag than the web text. The learners' sentences are short and use common words, while EWT is full of names, URLs, email addresses and headings. The biggest learner "errors" are mostly convention clashes:

- *to* tagged `TO` vs `IN`: 232 tokens.
- Discourse *so* tagged as an adverb in gold but a conjunction by spaCy.
- Japanese words that gold tags `FW` and spaCy tags `NNP`.

On EWT the largest single error is common nouns and adjectives tagged as proper nouns: 370 `NN` and 126 `JJ` tokens tagged `NNP` by `sm`. `trf` is better on every measure, by 0.5–0.7 points on learner speech and 1.8–2.5 points on web text.

### 2. What changes in lexinspect's output, per lexical token

Each cell is the % of lexical tokens where the two conditions give a different result, with a 95% CI.

**Learner (ESLSpok), 17,438 lexical tokens**

| Change | `sm` vs gold | `trf` vs gold | `sm` vs `trf` |
|---|---|---|---|
| XPOS tag differs | 5.12 [4.73–5.52] | 4.32 [3.96–4.68] | 2.89 |
| Lemma differs | 0.38 | 0.27 | 0.29 |
| **Any profile outcome differs** | **1.51 [1.32–1.69]** | **1.15 [0.97–1.33]** | 1.24 |
| CEFR outcome (level, proper or off-list) | 1.45 [1.26–1.62] | 1.14 [0.98–1.32] | 1.16 |
| of which, level shift on the list | 0.92 | 0.75 | 0.71 |
| of which, on-list vs not | 0.13 | 0.09 | 0.09 |
| BNC/COCA outcome | 0.13 [0.08–0.19] | 0.12 | 0.15 |
| of which, band shift | 0.00 | 0.00 | 0.00 |
| NGSL/NAWL outcome | 0.42 | 0.29 | 0.40 |
| AWL membership | 0.00 | 0.00 | 0.00 |
| Reported proper-noun status (any profile) | 0.47 [0.35–0.59] | 0.32 [0.21–0.44] | 0.45 |

**Baseline (EWT), 21,143 lexical tokens**

| Change | `sm` vs gold | `trf` vs gold | `sm` vs `trf` | `sm` vs gold+lemma |
|---|---|---|---|---|
| XPOS tag differs | 7.31 [6.65–8.06] | 4.67 [4.24–5.11] | 5.38 | 7.31 |
| Lemma differs | 1.21 | 0.85 | 0.77 | 3.04 |
| **Any profile outcome differs** | **3.42 [3.04–3.82]** | **2.20 [1.96–2.48]** | 2.43 | 4.12 |
| CEFR outcome | 3.03 [2.70–3.39] | 1.99 [1.76–2.23] | 2.19 | 3.63 |
| of which, level shift on the list | 0.92 | 0.77 | 0.65 | 0.93 |
| of which, on-list vs not | 0.47 | 0.29 | 0.33 | 1.13 |
| BNC/COCA outcome | 0.67 [0.54–0.83] | 0.31 | 0.55 | 1.03 |
| of which, band shift | 0.01 | 0.00 | 0.01 | 0.02 |
| NGSL/NAWL outcome | 2.00 | 1.10 | 1.40 | 2.29 |
| AWL membership | 0.00 | 0.00 | 0.00 | 0.05 |
| Reported proper-noun status (any profile) | 2.31 [1.98–2.63] | 1.26 [1.04–1.51] | 1.65 | 2.48 |

**What actually changes.**

- **CEFR level shifts** are almost all function words that the CEFR lists rate differently by part of speech. *so* as adverb (A2) vs conjunction (A1) accounts for 38 of 160 learner shifts. *for*, *in*, *all*, *as*, *over* and *up* move between A1 and A2 depending on preposition, adverb or particle tags. A few content words shift too: *present* (adjective B1 vs noun A1), *skiing* and *relaxing* (verb vs noun or adjective).
- **Proper-noun swaps** move a token between "proper noun" and "off-list". Examples: Japanese words in learner speech (*pasokon*, *kaishain*), and *e-mail*, *T-Mobile*, file names and phone numbers in web text.
- **BNC/COCA bands** are looked up by word form within Nation's families, so tags almost never move a token to another band (3 tokens out of 21,143). Tags matter to BNC/COCA only for proper-noun status.
- **AWL** coverage never changed under any model's tags. The 0.05% under `gold+lemma` comes from EWT's lemma conventions, not from tagging.

Only about a third of `sm`'s tag errors change anything lexinspect reports: 1.51% of tokens out of 5.12% mistagged on learner speech, and 3.42% out of 7.31% on web text.

### 3. What changes at text level

Each cell is the mean absolute difference per text in percentage points (pp), with the maximum over all texts in brackets.

| Measure | Learner `sm` vs gold | Learner `trf` vs gold | EWT `sm` vs gold | EWT `trf` vs gold |
|---|---|---|---|---|
| CEFR coverage per level, mean over A1–C2 | 0.27 | 0.22 | 0.26 | 0.23 |
| Largest per-level CEFR shift in a text | 0.81 (max 2.76) | 0.66 (max 2.07) | 0.78 (max 3.95) | 0.71 (max 2.63) |
| CEFR A1 coverage | 0.62 (max 2.76) | 0.56 | 0.50 (max 3.95) | 0.52 |
| CEFR off-list % | 0.49 (max 2.72) | 0.33 | 1.25 (max 6.12) | 0.88 |
| CEFR proper-noun % | 0.41 (max 2.67) | 0.29 | 1.38 (max 6.90) | 0.88 |
| BNC/COCA 1k / 2k / 3k coverage | ≤0.01 | 0 | ≤0.02 | ≤0.02 |
| BNC/COCA coverage incl. supplementary + proper | 0.13 (max 1.38) | 0.12 | 0.53 (max 3.95) | 0.31 |
| NGSL coverage | 0.01 | 0.00 | 0.02 | 0.02 |
| AWL coverage | 0 | 0 | 0 | 0 |
| `estimated_level_95th` same as gold | **81% of texts** | **91%** | **80%** | **82%** |
| `highest_level_present` same as gold | 97% | 99% | 99% | 98% |

When `estimated_level_95th` disagrees with gold, the gap is usually one level. On learner speech under `sm`, 19 of the 22 disagreeing texts are one level apart, and in the other 3 one condition never reaches 95% coverage. On EWT, most `sm` disagreements (21 of 28) are cases where one condition reaches 95% and the other doesn't. That happens because a handful of names flip between "proper noun", which counts as known, and "off-list". `sm` and `trf` disagree with each other on 16% of learner texts and 20% of EWT texts.

### 4. Speed and size

| | `en_core_web_sm` 3.8.0 | `en_core_web_trf` 3.8.0 |
|---|---|---|
| Speed, learner texts | 11,500 words/s | 1,820 words/s |
| Speed, EWT texts | 11,400 words/s | 1,640 words/s |
| Model load | 2.6 s | 3.7 s |
| Model package | 14.5 MB | 477.5 MB |
| Extra dependencies | none | PyTorch (500 MB), sympy, networkx, spacy-curated-transformers and others: **about 1.0 GB in total** with the model |

Measured on an Apple M3 Pro, on CPU only. `trf` is about 6–7 times slower and about 70 times larger, before counting PyTorch.

## Interpretation

**Does the small model materially change what users see? Mostly no.** The exception is one number.

- For about 98.5% of tokens in learner speech (96.6% in web text), `sm` gives the same CEFR level, band, list membership and proper-noun status as gold tags would. Switching to `trf` would fix about 0.4% of tokens in learner speech and 1.2% in web text.
- Frequency-band (BNC/COCA), NGSL and AWL coverage figures are essentially immune to tagging. Band and list coverage move by hundredths of a point. The only way tags reach them is through proper-noun status, which shifts the "off-list" and "assumed known" shares by about 0.1 pp (learner) to 0.5 pp (web text) on average.
- CEFR per-level coverage moves by about a quarter of a point on average, and by under 2 pp in 95% of texts. Most of the movement is function words switching between A1 and A2, which no user would act on.
- **The exception is `estimated_level_95th`.** Because it is a threshold on cumulative coverage, a fraction of a point can push a text across a level boundary. Under `sm`, it differs from the gold-tag result in about one text in five, nearly always by one level. Under `trf`, that drops to about one in ten on learner speech but stays near one in five on web text. `sm` and `trf` also disagree with each other on one text in five or six. This is a fragility of the estimate itself, not something a better tagger fixes. It supports what VALIDITY.md already says: the estimate is a rule of thumb, not a text's level.
- On this learner corpus, `sm` tags learner speech no worse than edited web text. The "two to three times as many errors" from Berzak et al. (2016), for written learner essays and the parsers they tested, did not show up here. But this is speech from short interviews with simple vocabulary, so it is not evidence about written learner essays.

## Recommendation

**Keep `en_core_web_sm` as the default.**

- Switching to `trf` would change about 0.4% of reported token outcomes on learner English and about 1.2% on web text.
- It would cost about 1 GB of installed size and 6–7 times the CPU time, which rules it out for the hosted function.
- If offered at all, `trf` should be an optional local extra for research users whose texts are rich in names, as `cefr_level` is.

Tagging is not the weak point. Better targets are:

- **Report `estimated_level_95th` with its sensitivity.** For example, flag texts whose coverage sits within about 1 pp of the threshold, or show the coverage that produced it.
- **Look at `sm`'s proper-noun precision:** 83% on learner speech, 75% on web text. Its false proper nouns, such as foreign words, capitalised common nouns and URLs, account for most of the off-list vs proper-noun swaps.

## Limitations

- **Spoken, single-L1 learner data.** ESLSpok is transcribed interview speech from Japanese learners. Written learner essays, the main lexinspect use case, may behave differently: they have longer sentences, more misspellings and different capitalisation. TLE, which is written and covers 10 first languages, could not be used without a Cambridge licence and approval to publish results (see Data).
- **Gold tokenisation.** Feeding gold tokens isolates tagging. In real use, spaCy's tokeniser runs on raw text, and misspelt or run-together learner words add errors not measured here.
- **Gold lemmas.** ESLSpok has none, so its "gold" condition uses spaCy's rule lemmatiser on gold tags. Lemmatiser errors that don't come from tags are therefore invisible there. On EWT, comparing with the treebank's own lemmas (`gold+lemma`) raises the any-outcome change rate from 3.4% to 4.1%. Part of that rise is real lemmatiser error and part is lemma conventions.
- **Annotation conventions count as errors.** UD/PTB and OntoNotes disagree on some tags, such as *to* and discourse *so*. Some "changes vs gold" are convention, not mistakes. The lenient XPOS row shows the size of the largest such clash.
- **ESLSpok UPOS is partly automatic.** It was converted from manual XPOS and then checked manually.
- **Texts are assembled.** They are runs of sentences of at least 150 words, not natural documents. Effects on `estimated_level_95th` depend on text length.
- **Speed is from one machine.** It was measured on one laptop CPU, one text at a time. `trf` would be much faster on a GPU, and `sm` faster with batching.

## Reproduce

```
bash scripts/validation/study2_tagger/run.sh
```

This downloads both treebanks into `.cache/validation/study2/` if they're absent, installs `en_core_web_trf` into a throwaway `uv run --with` environment, and rewrites `docs/validation/study2-tagger.json`. It takes a few minutes on an M3 Pro, plus the one-off ~450 MB model download. Accuracy and impact figures are deterministic. Speed varies by machine.

## References

- Berzak, Y., Kenney, J., Spadine, C., Wang, J. X., Lam, L., Mori, K. S., Garza, S., & Katz, B. (2016). Universal Dependencies for learner English. *ACL 2016*, 737–746.
- Honnibal, M., Montani, I., Van Landeghem, S., & Boyd, A. (2020). *spaCy: Industrial-strength natural language processing in Python*. doi:10.5281/zenodo.1212303
- Izumi, E., Uchimoto, K., & Isahara, H. (2004). The NICT JLE Corpus: Exploiting the language learners' speech database for research and education. *International Journal of the Computer, the Internet and Management*, 12(2), 119–125.
- Kyle, K., Eguchi, M., Miller, A., & Sither, T. (2022). A dependency treebank of spoken second language English. *Proceedings of the 17th Workshop on Innovative Use of NLP for Building Educational Applications (BEA 2022)*, 39–45.
- Silveira, N., Dozat, T., de Marneffe, M.-C., Bowman, S., Connor, M., Bauer, J., & Manning, C. D. (2014). A gold standard dependency corpus for English. *LREC 2014*.
- Yannakoudakis, H., Briscoe, T., & Medlock, B. (2011). A new dataset and method for automatically grading ESOL texts. *ACL-HLT 2011*. (Source text of TLE; not used here.)
