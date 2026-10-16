# Study 3: computational agreement with reference tools

> **Version note.** These results were computed with lexinspect 0.3.0. The two bugs reported under "Suspected lexinspect bugs" were fixed in 0.3.2, so rerunning the script now gives slightly different figures for the affected texts.

**Question.** On the same texts, do lexinspect's indices agree with established reference implementations? Where they disagree, is the cause a documented design choice (tokenisation, sentence splitting, syllable counting, published-definition fixes) or a bug?

**Short answer.**

- **Diversity formulas agree.** Given the same token list, MATTR, HD-D, MSTTR and TTR are identical to TAALED, lexical-diversity and lexicalrichness on all 300 texts. MTLD and vocd-D are identical to lexicalrichness. MTLD runs 1 point (about 3%) below TAALED's original MTLD, because TAALED requires factors of at least 10 tokens and closes a factor only when TTR drops strictly below .72.
- **Diversity scores on real text differ by tokenisation.** With each tool tokenising for itself, lexinspect is still compatible with lexicalrichness (r = .978–.997). It is not compatible with TAALED/pylats (r = .83–.86): TAALED lemmatises and drops proper nouns and unattested words, which lowers its diversity scores (lexinspect MATTR +.03, MTLD +14).
- **Readability formulas agree.** Fed lexinspect's counts, textstat's formulas reproduce lexinspect's Flesch, Flesch–Kincaid, SMOG and ARI exactly (to rounding). Coleman–Liau differs by a constant +0.36, which is lexinspect's correction of textstat's coefficient (0.0588, not 0.058). Fog and Dale–Chall differ because lexinspect follows Gunning's and Chall & Dale's counting rules, as `readability.py` and CAVEATS.md describe.
- **Readability scores on real text are mostly not "compatible" with textstat.** Six of eight formulas fall below r = .95 (Coleman–Liau .997 and SMOG .963 pass). The differences come from counting: sentence splitting (`U.S.`, unpunctuated learner run-ons, dropped short sentences), numerals (lexinspect says `1992` as four syllables, textstat counts one), words that textstat glues together when it strips punctuation (`school,they`, `red-green`, curly-apostrophe contractions), and the syllable fallback for words outside CMUdict. Every word in CMUdict gets the same syllable count in both tools.
- **Two lexinspect bugs found** (not fixed here; see [Suspected lexinspect bugs](#suspected-lexinspect-bugs)):
  1. Words joined through a dash and a quote or comma are counted as one word and one diversity type: `last”—he`, `deep,—not`. This affects 53 of 300 texts, mostly 19th-century prose, and can move MTLD by up to 22%.
  2. Digit strings that aren't plain numbers (`1914–1918`, `11:00`, `1/4`) count as words with **0 syllables** and stay in the diversity tokens, which are meant to exclude numbers. This affects 51 texts.
- **vocd-D vs Text Inspector.** On the comparison passage, lexinspect's vocd-D of 245.48 is reproduced exactly by lexicalrichness, an independent implementation using scipy's unbounded curve fit. Text Inspector shows exactly 200.00. A least-squares optimum landing on a round 200.00 is implausible, so the likely cause is a ceiling or search bound at 200 in Text Inspector. That is an inference: Text Inspector's code was not inspected.

Results are from lexinspect 0.3.0 with `en_core_web_sm-3.8.0`. Every number is in [`study3-agreement.json`](study3-agreement.json); per-text values are in [`study3-agreement-per-text.csv`](study3-agreement-per-text.csv).

## Texts

| Source | N | Words (min / median / max) | Licence | Selection (seed 20261016) |
|---|---:|---|---|---|
| Project Gutenberg | 100 | 129 / 634 / 994 | Public domain in the USA; PG header and licence stripped | Fixed list of 30 books chosen for genre spread before sampling: fiction 34 passages, philosophy 13, children's 12, science 12, essay 11, memoir 6, practical 5, economics 5, politics 2. For each passage: a seeded random book, a start paragraph in the middle 80% of the book, and whole prose paragraphs up to a seeded random target of 100–1,000 words. PG italics markup (`_word_`) was removed. |
| Simple English Wikipedia | 50 | 398 / 952 / 997 | CC BY-SA 4.0 | 50 topics sampled from the 140 articles in Simple Wikipedia's *Very good articles* and *Good articles* categories, each with an English Wikipedia counterpart |
| English Wikipedia | 50 | 822 / 950 / 1,000 | CC BY-SA 4.0 | The same 50 topics' English articles |
| ELLIPSE corpus (train split) | 100 | 136 / 422 / 756 | CC BY-NC-SA 4.0 (Crossley et al. 2023), stated in the repository README | Seeded sample of the 3,816 training essays of 100–1,000 words; English learners in grades 8–12 |

Word counts are whitespace counts. Wikipedia text is the article's prose paragraphs from the top, with no headings, lists, tables or reference marks, cut at whole paragraphs at 1,000 words. Each article is fetched at the revision pinned in [`scripts/validation/study3_agreement/wikipedia_selection.json`](../../scripts/validation/study3_agreement/wikipedia_selection.json) (fetched 16 October 2026), so reruns see the same text. The texts are stored in `.cache/validation/study3/` (gitignored) and never committed. The JSON records the SHA-256 of every text so a rerun can be checked against this one.

## Tools

| Tool | Version | Licence | Role |
|---|---|---|---|
| lexinspect | 0.3.0, `en_core_web_sm` 3.8.0 | MIT | Tool under test |
| textstat | 0.7.13 | MIT | Readability reference. CMUdict via NLTK 3.10.3, Pyphen 0.18.1 fallback |
| TAALED | 0.32 | **CC BY-NC-SA 4.0**, per `License_CC-A-NC-SA-4.0.txt` in the GitHub repo; the PyPI package declares none | Diversity reference (Kyle's tool) |
| pylats | 0.64 | CC BY-NC-SA 4.0 (same) | TAALED's recommended preprocessing |
| lexical-diversity | 0.1.1 | PyPI classifier says MIT; licence field "UNKNOWN"; no licence file in the repo | Diversity reference (Kyle's earlier package) |
| lexicalrichness | 0.5.1 | MIT | Diversity reference, including vocd-D |

The reference packages are installed only in a throwaway `uv run --with` environment. None is vendored or added to `pyproject.toml`, so TAALED's non-commercial licence doesn't reach lexinspect. TAALED and pylats need `setuptools<81` because they still import `pkg_resources`. Python 3.12.5, pandas 3.0.6, scipy 1.18.1.

## Method

1. **Readability, each tool on the raw text.** lexinspect's `readability.analyze` was compared with textstat's formulas and counts (rounding off). For "Dale–Chall difficult words", textstat's count is the one its Dale–Chall formula uses: every word off the easy list. Its public `difficult_words()` defaults to words of 2+ syllables.
2. **Readability, formula only.** Each textstat formula was recomputed on lexinspect's counts with textstat's coefficients. For Fog and Dale–Chall, textstat's hard-word definitions were applied to lexinspect's words: Fog hard words are 3+ syllables and not on the easy list; Dale–Chall difficult words are anything off the easy list. A difference here is a definition difference, not a counting one.
3. **Syllables, word by word.** Every alphabetic word type in the corpus (14,887 types, 188,918 tokens) was counted by both syllable counters.
4. **Diversity, same tokens.** lexinspect's token list (`diversity.tokens`: lowercased words, contractions and hyphenated compounds whole, numerals excluded) was passed unchanged to each reference. TAALED `lexdiv`, lexical-diversity's functions and `LexicalRichness(tokens, preprocessor=None, tokenizer=None)` all use window 50, threshold .72, 42 draws, and for vocd-D, sizes 35–50 with 100 samples, 3 trials and seed 42.
5. **Diversity, own tokens.** Each reference on the raw text with its documented preprocessing:
   - TAALED via pylats `EnDefault` with the same spaCy model: lemma_POS tokens; punctuation, proper nouns, numbers and words not attested in COCA removed.
   - lexical-diversity: `flemmatize`.
   - lexicalrichness: its default `preprocess` and `tokenize`.
6. **Statistics.** For each metric: Pearson r, Spearman ρ, bias (mean of lexinspect − reference), mean absolute difference (MAD), and % of texts within a stated tolerance. The tolerances, chosen before results were seen:
   - counts: 2–10% relative;
   - Flesch Reading Ease: ±5;
   - grade formulas and the Dale–Chall raw score: ±0.5;
   - MATTR, HD-D, MSTTR, TTR: ±.01;
   - MTLD, vocd-D, token counts: 5% relative.

   **"Compatible" means r > .95. This is a working convention for this study, not a published standard.** A high r with a non-zero bias means the tools rank texts alike but sit on shifted scales.
7. **Disagreements.** The five texts with the largest absolute difference per metric are listed in the JSON (`top5`). The causes below come from comparing the tools' word, sentence and syllable lists on those texts.

## Results

### Readability: each tool's own counts (N = 300)

| Measure | r | ρ | Bias | MAD | Tolerance | % within | r > .95 |
|---|---:|---:|---:|---:|---|---:|:---:|
| Words | 1.000 | 1.000 | +1.07 | 1.07 | ±2% | 99.0 | yes |
| Sentences | .991 | .992 | −0.26 | 1.76 | ±10% | 81.7 | yes |
| Syllables | .997 | .998 | +37.0 | 37.0 | ±2% | 62.7 | yes |
| Syllables, words without digits | 1.000 | .999 | +11.1 | 11.1 | ±2% | 87.0 | yes |
| Polysyllabic words (3+) | .986 | .992 | +10.4 | 10.6 | ±5% | 48.0 | yes |
| Dale–Chall difficult words | .848 | .901 | −90.2 | 90.2 | ±5% | 0.0 | no |
| Flesch Reading Ease | .900 | .931 | −2.80 | 5.04 | ±5 | 63.7 | no |
| Flesch–Kincaid grade | .903 | .929 | +0.23 | 1.15 | ±0.5 | 42.3 | no |
| Gunning Fog | .923 | .946 | −0.69 | 1.17 | ±0.5 | 33.7 | no |
| SMOG | .963 | .954 | +0.38 | 0.63 | ±0.5 | 54.3 | yes |
| ARI | .921 | .961 | −1.03 | 1.27 | ±0.5 | 28.3 | no |
| Coleman–Liau | .997 | .997 | +0.30 | 0.32 | ±0.5 | 93.3 | yes |
| Dale–Chall raw score | .632 | .653 | −1.99 | 1.99 | ±0.5 | 3.0 | no |
| Linsear Write | .901 | .928 | +1.77 | 2.49 | ±0.5 | 23.7 | no |
| `text_standard` (different definitions) | .765 | .812 | +0.60 | 1.57 | ±1 | 54.3 | no |

By source, the formulas agree best on Gutenberg prose (Flesch, Flesch–Kincaid, Fog and SMOG all r ≥ .98). They agree least on Wikipedia, where numerals and `U.S.`-style abbreviations are common (FRE bias about −10 on both Wikipedias), and on learner essays, where sentence punctuation is irregular. See `by_source` in the JSON.

### Readability: formula only (textstat formulas on lexinspect's counts)

| Formula | r | Bias | MAD | % within ±0.01 | Reading |
|---|---:|---:|---:|---:|---|
| Flesch Reading Ease | 1.000 | 0.000 | 0.003 | 100 | Same formula (MAD is lexinspect's 2-dp rounding) |
| Flesch–Kincaid grade | 1.000 | 0.000 | 0.003 | 100 | Same formula |
| SMOG | 1.000 | 0.000 | 0.003 | 100 | Same formula (1.043 vs 1.0430) |
| ARI | 1.000 | 0.000 | 0.002 | 100 | Same formula, but see the note on characters below |
| Coleman–Liau | 1.000 | +0.357 | 0.357 | 0 | Coefficient: lexinspect 0.0588 (Coleman & Liau 1975), textstat 0.058 |
| Gunning Fog | .947 | −0.91 | 1.23 | 4 | Hard-word definition: lexinspect excludes proper nouns, hyphenated compounds and words that reach 3 syllables only through -es/-ed/-ing (Gunning 1952); textstat excludes words on the Dale–Chall easy list |
| Dale–Chall raw score | .641 | −1.93 | 1.93 | 0 | Familiarity: lexinspect counts inflections of listed words, proper names and numerals as familiar (Chall & Dale 1995 rules); textstat counts only exact list entries as familiar |

ARI is identical given the same counts, but the counts differ by definition: textstat divides *all* non-space characters, punctuation included, by a word count that includes punctuation-only "words". lexinspect counts letters and digits.

### Syllables, word by word (same words)

| Word types | Types | Tokens | % types identical | % tokens identical | % types within 1 | Mean diff (lexinspect − textstat) |
|---|---:|---:|---:|---:|---:|---:|
| All | 14,887 | 188,918 | 93.4 | 99.0 | 98.2 | +0.08 |
| In CMUdict | 12,770 | 184,678 | **100.0** | **100.0** | 100.0 | 0.00 |
| Not in CMUdict | 2,117 | 4,240 | 53.4 | 54.3 | 87.6 | +0.54 |

Both tools use CMUdict's first pronunciation, so every dictionary word agrees. Outside CMUdict, lexinspect uses spelling variants, stem plus suffix, and then rules; textstat uses Pyphen hyphenation points plus one. Pyphen undercounts: it won't hyphenate near word edges. The most frequent disagreements, with lexinspect's count first:

- correct by CMUdict's own `color`: `colour` 2 vs 1;
- `cassowaries` 4 vs 2;
- `megadeth` 3 vs 1;
- `youtube` 2 vs 1;
- `subspecies` 3 vs 2.

In nearly every case lexinspect's count is the one a speaker would give. A few go the other way (`extratropical` 5 vs 6, `vindver` 2 vs 3).

### Lexical diversity: same tokens (N = 300)

| Measure | Reference | r | Bias | MAD | % within tolerance | % identical |
|---|---|---:|---:|---:|---:|---:|
| MATTR (50) | TAALED / lexical-diversity / lexicalrichness | 1.000 | 0 | 0 | 100 (±.01) | 100 |
| HD-D | TAALED / lexical-diversity / lexicalrichness | 1.000 | 0 | 0 | 100 (±.01) | 100 |
| MSTTR (50), TTR | TAALED | 1.000 | 0 | 0 | 100 | 100 |
| MTLD | lexicalrichness | 1.000 | 0 | 0 | 100 (±5%) | 100 |
| MTLD | TAALED original (`mtldo`) = lexical-diversity | .995 | −1.04 | 1.32 | 84.0 (±5%) | 32.7 |
| MTLD | TAALED default (`mtld`, mean factor length) | .990 | −1.07 | 2.03 | 76.7 (±5%) | 0 |
| vocd-D | lexicalrichness | 1.000 | 0.000 | 0.000 | 100 (±5%) | 0.3* |
| Maas a² | TAALED | 1.000 | −0.029 | 0.029 | 0 | 0 |

\* vocd-D agrees to four decimal places on every text. The two tools draw the same samples, because Python's `random.Random(42)` and `random.seed(42)` produce one stream. They differ only in the optimiser: lexinspect's golden-section search versus scipy's `curve_fit`.

Maas differs only in log base: TAALED uses log₁₀ and lexinspect uses natural logs, so TAALED's value is ln 10 ≈ 2.30 times lexinspect's. r = 1.000; compare Maas values only within one tool.

### Lexical diversity: each tool's own tokenisation (N = 300)

| Measure | Reference | r | ρ | Bias | MAD | % within tolerance | r > .95 |
|---|---|---:|---:|---:|---:|---:|:---:|
| Tokens | TAALED/pylats | .975 | .964 | +48.8 | 51.8 | 59.7 (±5%) | yes |
| Tokens | lexical-diversity | .999 | .995 | −8.4 | 9.9 | 97.0 | yes |
| Tokens | lexicalrichness | 1.000 | .999 | −5.9 | 6.4 | 99.3 | yes |
| MATTR | TAALED/pylats | .859 | .851 | +.032 | .033 | 13.3 (±.01) | no |
| MATTR | lexical-diversity | .968 | .959 | +.017 | .018 | 25.7 | yes |
| MATTR | lexicalrichness | .995 | .995 | +.000 | .003 | 97.0 | yes |
| MTLD | TAALED/pylats (original) | .836 | .827 | +14.1 | 14.4 | 11.7 (±5%) | no |
| MTLD | TAALED/pylats (default) | .831 | .820 | +14.0 | 14.5 | 10.7 | no |
| MTLD | lexical-diversity | .943 | .948 | +6.6 | 7.4 | 25.3 | no |
| MTLD | lexicalrichness | .978 | .981 | +0.4 | 2.7 | 72.7 | yes |
| HD-D | TAALED/pylats | .857 | .843 | +.031 | .031 | 12.7 (±.01) | no |
| HD-D | lexical-diversity | .972 | .950 | +.017 | .017 | 27.0 | yes |
| HD-D | lexicalrichness | .997 | .995 | −.000 | .002 | 98.7 | yes |
| vocd-D | lexicalrichness | .994 | .995 | −0.1 | 1.4 | 93.7 (±5%) | yes |

### BNC/COCA K-band coverage

Skipped. No freely available Python implementation of Nation's BNC/COCA family profiling exists to compare against. AntWordProfiler and Range are desktop programs, and Text Inspector's guest view locks its profiles. A comparison would need someone to run AntWordProfiler by hand on a subset of these texts.

## Why they disagree: the largest differences

The JSON lists the top five texts per metric. Most share a handful of causes, grouped here.

### Sentences

| Text | lexinspect | textstat | Cause |
|---|---:|---:|---|
| wiki-en-030 (Japanese American internment) | 36 | 51 | textstat splits at every full stop: "About two-thirds were U. / S. / citizens." It then drops the fragments of 2 words or fewer, but still miscounts. lexinspect (spaCy) keeps `U.S.` whole. **Design choice, lexinspect correct.** |
| pg36-p00596 (*The War of the Worlds*) | 100 | 87 | textstat silently drops sentences of 2 words or fewer ("Good luck!", "I stared.", "Eh?"). **Design choice, documented in `readability.py`.** |
| ellipse-0022683E9EA5 | 25 | 14 | Learner essay with a paragraph break inside a sentence ("A⏎⏎problem is…") and unpunctuated run-ons. lexinspect breaks at every blank line (documented in `_text.py`), and spaCy's parser splits some run-ons. textstat waits for `.!?`. Neither count is "right" for unpunctuated text. |
| wiki-simple-013 (Mia Love) | 57 | 68 | `U.S.` again (six times). |
| pg37134-p00046 (*The Elements of Style*) | 48 | 38 | An outline ("A. Facts of composition… B. Kind of poem…" and numbered items). textstat drops the 1–2-word items; lexinspect counts them, including bare list numbers (`9`, `1`, `2`) as sentences. Edge case, not prose. |

### Words

The top five (wiki-en-026, ellipse-F1A4167422E2, pg36-p00596, pg74-p00649, pg2701-p01520; lexinspect +10 to +14) are all textstat merging words when it deletes punctuation. Examples:

- `red-green` → `redgreen` and `parents/teachers` → `parentsteachers`;
- learner text with no space after a comma: `school,they` → `schoolthey`, `home,eat,relax,and` → `homeeatrelaxand`;
- em-dashes in fiction: `nearer—I` → `nearerI`.

textstat also turns curly-apostrophe contractions into `didnt` and `Ive`, which then miss CMUdict. The word count is unchanged by that, but it moves syllables. lexinspect's counts are the right ones here, apart from the glued-word bug below, which pushes in the opposite direction.

### Syllables and polysyllables

Top five: wiki-en-020, wiki-simple-020, wiki-simple-021, wiki-simple-006, wiki-en-006, with lexinspect +190 to +230. Numerals cause most of it. lexinspect reads `1992` as *nineteen ninety-two* (4 syllables) and `2,000` as *two thousand*; textstat runs digits through Pyphen and gets 1. On wiki-en-020, 68 numerals give 246 syllables in lexinspect against 62 in textstat. This is documented in CAVEATS.md ("Numerals are an approximation of speech") and is a **design choice**. Excluding words with digits cuts the overall bias from +37 to +11 syllables per text, and r rises to 1.000.

The remaining +11 comes from:

- textstat's merged words going to Pyphen (`redgreen`: on wiki-en-026, +111);
- Pyphen undercounting non-dictionary words;
- curly-apostrophe contractions (`didn’t` → `didnt` → Pyphen).

### Readability scores

- **Flesch, Flesch–Kincaid, Fog, ARI.** The top five are mostly ELLIPSE essays with almost no full stops. On ellipse-5F67A5D3DBB0, textstat finds 5 sentences of 120+ words and gives FRE −26.9 and FK grade 47.4. lexinspect's parser finds 10 sentences and gives FRE 34.7 and FK grade 23.6. Neither is meaningful for unpunctuated text; lexinspect's is less extreme. The Wikipedia entries in the top five are the `U.S.` and numeral effects above.
- **SMOG.** wiki-en-030, wiki-en-045, wiki-en-041 (lexinspect +2.3 to +3.7) are numeral syllables plus `U.S.` splitting. ellipse-5F67… and ellipse-0022… are sentence counts.
- **Coleman–Liau.** The top five (wiki-en-030, wiki-simple-013, wiki-en-045, wiki-simple-029, wiki-simple-017) differ by 0.6–0.9: the 0.0588 coefficient (+0.36) plus `U.S.` sentence splitting. The best agreement of any formula.
- **Dale–Chall raw score.** Top five: ellipse-F57B95D17755, wiki-simple-006, pg16-p00161, ellipse-EC3F3F26E635, pg55-p00615, with lexinspect lower by 5–7. For example, ellipse-F57B95D17755 scores 1.71 in lexinspect and 8.41 in textstat. Two effects add up:
  - lexinspect treats inflections of listed words, names and numerals as familiar; textstat's list lacks `played`, `roles` and `cats`, and every name (`Plummer`, `Broadway`) counts as difficult.
  - Once lexinspect's share of difficult words falls below 5%, the formula's +3.6365 adjustment switches off. That step is why r is only .63.

  **Design choice** (Chall & Dale 1995 counting rules, documented in `readability.py` and CAVEATS.md). The low r means the two tools' Dale–Chall scores are not interchangeable.
- **Gunning Fog, formula only.** Top five: wiki-simple-006, wiki-simple-017, wiki-en-006, wiki-en-025, wiki-en-020, with lexinspect 5 points lower. These are biographies full of 3-syllable proper nouns (`Christopher`, `Barrymore`, `Montreal`) that Gunning excludes and textstat counts. **Design choice.**
- **Linsear Write.** Top five: pg2009-p00448, pg205-p00351, pg2009-p00366, wiki-en-041 (lexinspect +14 to +29) and ellipse-C265A20FB301 (−19). Both tools read the first 100 words; they count the sentence cut off at word 100 differently.
  - lexinspect counts the cut-off sentence proportionally. In *Origin of Species* the first 100 words are a 73-word sentence plus 27 of an 83-word one, giving 1.33 sentences.
  - textstat counts any started sentence as a whole one, giving 2.
  - So lexinspect scores long-sentence texts much higher: 52.1 against 23.0.

  The proportional rule is commented in `readability.py` but not in CAVEATS.md. It is a defensible reading of "sentences in the sample", but it makes Linsear Write very sensitive to one long sentence. **Design choice, worth documenting.**
- **`text_standard`.** Not comparable by design: lexinspect takes the median of eight grades, textstat a rounded mode with Dale–Chall's raw score in the vote. The large gaps (pg2009-p00366: 26.3 against 11.0) come from Linsear Write and Dale–Chall above.

### Diversity

- **MTLD vs TAALED, same tokens** (pg2701-p01047 126.3 vs 137.8; ellipse-AAD6A5CBDDB9 51.5 vs 61.0; wiki-en-009; pg25344-p00300; ellipse-1D47271C213D).
  - TAALED and lexical-diversity won't close a factor shorter than 10 tokens, and close one only when TTR drops strictly *below* .72. lexinspect and lexicalrichness close at ≤ .72 with no minimum.
  - Rerunning TAALED's MTLD with the 10-token minimum removed gives exactly lexinspect's 126.32 on pg2701-p01047. On ellipse-AAD6A5CBDDB9 it gives 56.5; the remaining gap is the < versus ≤.
  - **Implementation variant, not a bug.** McCarthy & Jarvis (2010) don't specify a minimum factor length. Report which MTLD you used.
- **Own tokens, TAALED/pylats** (wiki-simple-006, wiki-en-006, wiki-en-018, wiki-simple-021, wiki-simple-013 for tokens, MATTR and HD-D). On wiki-simple-006, a biography of Christopher Plummer, pylats keeps 604 tokens against lexinspect's 932, because it drops every proper noun and every word not attested in COCA. Lemmatising (`played`, `plays` → `play_VERB`) lowers diversity further. On narrative texts (pg45, pg205, pg36) TAALED's MTLD is 40–55% lower for the same reason. **Different construct:** TAALED measures lemma diversity of common vocabulary, lexinspect measures word-form diversity. Use one tool throughout a study.
- **Own tokens, lexical-diversity** (pg205-p00336, pg2680-p00081, …): `flemmatize` lemmatises, and it deletes punctuation before splitting, merging words like textstat does.
- **Own tokens, lexicalrichness** (pg205-p00336 159.8 vs 134.7; wiki-en-042; ellipse-194E86ED4117; pg98-p01114; pg36-p00327). lexicalrichness splits `don't` into `don` + `t` and deletes hyphens (`well-known` → `wellknown`); lexinspect keeps contractions and compounds whole, as CAVEATS.md documents. pg205-p00336 (*Walden*) is also the worst case of the glued-word bug: 8 bogus types such as `deep,—not` and `forests;—the`. Splitting those 8 tokens alone moves lexinspect's MTLD from 159.8 to 130.6.
- **vocd-D, own tokens** (pg36, pg74, pg2701, pg84, pg1342; lexicalrichness 8–12 higher). These are fiction with many contractions. lexicalrichness's `don` + `t` split adds frequent short "words" and raises its estimate. Tokenisation, not formula: on the same tokens the two agree to four decimal places.

## Suspected lexinspect bugs

Both are tokenisation issues in `_text.py` and `readability.py`. Neither changes a formula. They weren't fixed in this study.

### 1. Words glued through dashes, quotes or brackets count as one word

spaCy doesn't split `last”—he` or `was—“impressively”—big`: its infix rules split an em-dash only between two letters. lexinspect's `_group_words` then treats the token as one word, because it contains letters.

```python
>>> from lexinspect._text import analyse
>>> a = analyse("It was—“impressively”—big, he said “at last”—then left.")
>>> [w.text for w in a.words]
['It', 'was—“impressively”—big', 'he', 'said', 'at', 'last”—then', 'left']
>>> # expected 10 words: It was impressively big he said at last then left
```

In this corpus: 146 glued words in 53 of 300 texts. 41 are Gutenberg texts, where `,—` and `”—` are common, plus `great,[2`-style reference remnants and `quickly)and`. The word count moves by a median of 0.2% (max 1.6%) of tokens. MATTR barely moves (max .007). MTLD moves by a median of 0.2% but up to **22%** (*Walden*), because each glued word is a unique type. Syllables of glued words are summed over their letters, so readability is only slightly affected.

### 2. Digit strings that aren't plain numbers get 0 syllables and count as diversity tokens

`_text._NUMERIC` matches `1914` but not `1914–1918`, `11:00`, `1/4` or `3-4`. These are therefore not numeric. `_parts` finds no alphabetic part, so `word_syllables` returns 0. They still count as words in every readability denominator, and they stay in `diversity.tokens`, which the docs say excludes numerals.

```python
>>> from lexinspect._text import analyse
>>> from lexinspect import readability, diversity
>>> a = analyse("The war lasted from 1914–1918 and the meeting began at 11:00 in 1914.")
>>> [(w.text, readability.word_syllables(w), w.is_numeric) for w in a.words if any(c.isdigit() for c in w.text)]
[('1914–1918', 0, False), ('11:00', 0, False), ('1914', 4, True)]
>>> diversity.tokens(a)   # numerals are meant to be excluded
['the', 'war', 'lasted', 'from', '1914–1918', 'and', 'the', 'meeting', 'began', 'at', '11:00', 'in']
```

In this corpus: 155 such words in 51 texts, almost all Wikipedia (year and score ranges, times, fractions). The effect on any one score is small: each lowers syllables per word slightly, making a text look a little easier. But it contradicts both the "numerals excluded" rule in diversity and the "numerals are read as spoken" rule in readability.

## In plain English

- **The formulas themselves are right.** Fed the same words, lexinspect's diversity measures give the same numbers as three independent tools, to the last decimal. Its Flesch, Flesch–Kincaid, SMOG and ARI give the same numbers as textstat's when fed the same counts.
- **Different tools count text differently.** Fed real text, readability scores differ from textstat's by about 1 grade level on average, and by much more on texts with lots of numbers, abbreviations like "U.S." or missing full stops. That is because each tool counts words, sentences and syllables its own way, and lexinspect's way is usually the more defensible one.
- **A few formulas differ on purpose.** lexinspect deliberately follows the original Gunning Fog, Dale–Chall and Coleman–Liau definitions where textstat doesn't.
- **Don't mix tools in one study.** TAALED, the tool most often used in diversity research, lemmatises and throws away names. Its diversity scores are systematically lower than lexinspect's and rank texts only moderately alike (r ≈ .85). If you compare your numbers with a paper, use the tool the paper used.
- **vocd-D vs Text Inspector.** The 200 vs 245 gap almost certainly comes from Text Inspector capping vocd-D at 200, not from a mistake in lexinspect.
- **Two small lexinspect bugs.** Words stuck together by a dash and a quote, and number ranges like "1914–1918", are mishandled. They affect a minority of texts and rarely move a score much, but they should be fixed.

## vocd-D: lexinspect 245.48 vs Text Inspector 200.00

The values were reported the other way round in some notes. The source, [`reports/text-inspector-comparison/comparison.md`](../../reports/text-inspector-comparison/comparison.md), has **Text Inspector 200.00 and lexinspect 245.48**. On that passage (194 tokens, 153 types):

| Check | Result |
|---|---|
| lexinspect `vocd_d` (seed 42) | 245.48 |
| lexicalrichness `vocd()` on the same tokens (scipy `curve_fit`, unbounded) | 245.48 |
| lexinspect with seeds 1–20 | 241.98–249.50 (mean 246.0) |
| Squared error of the fit at D = 200 vs at the fitted D (243.4, trial 1) | 30 times larger at 200 |

lexinspect's `_fit_d` searches D in [1, 10,000], so it has no cap at 200. The fit is well defined (the error curve isn't flat near 200), and sampling noise moves D by only about ±4. So the 45-point gap is neither sampling nor a lexinspect fitting artefact.

A least-squares fit landing on exactly 200.00, in both of Text Inspector's views, points to a ceiling or a search bound of 200 in Text Inspector. Its own UI says values are "typically 0–200". This is an inference from the outputs; Text Inspector's code was not inspected. If it is right, Text Inspector reports 200 for any text whose true D is higher. Highly diverse, short texts like this passage are exactly where that happens.

## Limitations

- **Agreement, not validity.** Matching textstat or TAALED shows the arithmetic is consistent, not that any score measures difficulty or diversity well. Studies 1 and 5 address meaning.
- **References aren't ground truth.** Where tools disagree, the explanations above say which follows the published definition. On some questions (sentence breaks in unpunctuated learner text, Linsear's partial sentence, MTLD's minimum factor length) neither choice is canonical.
- **Text selection.** Gutenberg is 19th- and early-20th-century writing from 30 hand-picked books. Wikipedia topics come from Simple Wikipedia's featured articles, which skew to biographies, animals and places. ELLIPSE is US secondary-school English learners writing persuasive essays. No speech, no social media, no texts over 1,000 words.
- **Extraction artefacts.** A few Wikipedia paragraphs keep fragments of reference marks (`great,[2`). They are in the texts all tools saw, so they don't bias the comparison, but they add to bug 1's count.
- **One version each.** textstat 0.7.13, TAALED 0.32 and the others, pinned in `run.sh`. Earlier textstat versions counted differently.
- **AntWordProfiler not compared.** BNC/COCA coverage, NGSL and AWL still have no agreement check against a reference implementation.
- **Thresholds are conventions.** The r > .95 "compatible" line and the tolerances were chosen for this study. Read the bias and MAD columns too.

## Reproduce

```
bash scripts/validation/study3_agreement/run.sh
```

This downloads the texts into `.cache/validation/study3/` (pinned Wikipedia revisions, seeded samples), runs the comparison and the bug diagnostics, and rewrites `docs/validation/study3-agreement.json` and `study3-agreement-per-text.csv`. It needs network access on first run and takes about 20 minutes (most of it polite download delays); reruns use the cache. The reference tools are installed with `uv run --with`; `pyproject.toml` and `uv.lock` are not touched.

## References

- Chall, J. S., & Dale, E. (1995). *Readability revisited: The new Dale–Chall readability formula*. Brookline Books.
- Coleman, M., & Liau, T. L. (1975). A computer readability formula designed for machine scoring. *Journal of Applied Psychology*, 60(2), 283–284.
- Covington, M. A., & McFall, J. D. (2010). Cutting the Gordian knot: The moving-average type–token ratio (MATTR). *Journal of Quantitative Linguistics*, 17(2), 94–100.
- Crossley, S. A., Tian, Y., Baffour, P., Franklin, A., Kim, Y., Morris, W., Benner, B., Picou, A., & Boser, U. (2023). Measuring second language proficiency using the English Language Learner Insight, Proficiency and Skills Evaluation (ELLIPSE) Corpus. *International Journal of Learner Corpus Research*, 9(2), 248–269.
- Gunning, R. (1952). *The technique of clear writing*. McGraw-Hill.
- Kyle, K. TAALED: Tool for the Automatic Analysis of Lexical Diversity. https://github.com/LCR-ADS-Lab/TAALED
- McCarthy, P. M., & Jarvis, S. (2010). MTLD, vocd-D, and HD-D: A validation study of sophisticated approaches to lexical diversity assessment. *Behavior Research Methods*, 42(2), 381–392.
- McKee, G., Malvern, D., & Richards, B. (2000). Measuring vocabulary diversity using dedicated software. *Literary and Linguistic Computing*, 15(3), 323–337.
- O'Hayre, J. (1966). *Gobbledygook has gotta go*. US Bureau of Land Management.
- Zenker, F., & Kyle, K. (2021). Investigating minimum text lengths for lexical diversity indices. *Assessing Writing*, 47, 100505.
