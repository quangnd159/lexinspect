# Study 3: computational agreement with reference tools

> **Version note.** These results were computed with lexinspect 0.3.3. Run under 0.3.0, this study found tokenisation bugs, which were fixed in 0.3.2 and 0.3.3. [Tokenisation bugs](#tokenisation-bugs) gives what was found, what was fixed and what remains.

**Question.** On the same texts, do lexinspect's indices agree with established reference implementations? Where they disagree, is the cause a documented design choice (tokenisation, sentence splitting, syllable counting, published-definition fixes) or a bug?

**Short answer.**

- **Diversity formulas agree.** Given the same token list, MATTR and HD-D are identical to TAALED, lexical-diversity and lexicalrichness on all 300 texts. MSTTR is identical to TAALED and lexical-diversity, and TTR to TAALED and lexicalrichness (the JSON summarises the TAALED comparisons; the per-text CSV has all four). MTLD is identical to lexicalrichness, and vocd-D agrees with it to four decimal places. MTLD runs 1.2 points (about 1.7%) below TAALED's original MTLD on average, because TAALED requires factors of at least 10 tokens and closes a factor only when TTR drops strictly below .72.
- **Diversity scores on real text differ by tokenisation.** With each tool tokenising for itself, lexinspect is still compatible with lexicalrichness (r = .975–.997). It is not compatible with TAALED/pylats (r = .83–.86): TAALED lemmatises and drops proper nouns and unattested words, which lowers its diversity scores (lexinspect MATTR +.03, MTLD +13).
- **Readability formulas agree.** Fed lexinspect's counts, textstat's formulas reproduce lexinspect's Flesch, Flesch–Kincaid, SMOG and ARI exactly (to rounding). Coleman–Liau does not match: it sits 0.36 higher on average (at most 0.45), which is lexinspect's correction of textstat's coefficient (0.0588, not 0.058). Fog and Dale–Chall differ because lexinspect follows Gunning's and Chall & Dale's counting rules, as `readability.py` and CAVEATS.md describe.
- **Readability scores on real text are mostly not "compatible" with textstat.** Six of eight formulas fall below r = .95 (Coleman–Liau .997 and SMOG .961 pass). The differences come from counting: sentence splitting (`U.S.`, unpunctuated learner run-ons, dropped short sentences), numerals (lexinspect says `1992` as four syllables, textstat counts one), words that textstat glues together when it strips punctuation (`school,they`, `red-green`, curly-apostrophe contractions), and the syllable fallback for words outside CMUdict. Every word in CMUdict gets the same syllable count in both tools.
- **Tokenisation bugs found and fixed** (see [Tokenisation bugs](#tokenisation-bugs)). Run under 0.3.0, this study found two:
  1. Words joined through a dash and a quote or comma counted as one word and one diversity type: `last”—he`, `deep,—not`. This affected 53 of 300 texts, mostly 19th-century prose, and moved MTLD by up to 22%.
  2. Digit strings that aren't plain numbers (`1914–1918`, `11:00`, `1/4`) counted as words with **0 syllables** and stayed in the diversity tokens, which are meant to exclude numbers. This affected 51 texts.

  0.3.2 and 0.3.3 fixed these. Under 0.3.3, the diagnostics still flag 19 glued words in 13 texts (6 of them false positives: numbers with a thousands comma inside a hyphenated compound) and 7 zero-syllable digit strings in 4 texts; splitting every flagged word would move MTLD by at most 5.6%. These are known limitations of 0.3.3.
- **vocd-D vs Text Inspector.** On the comparison passage, lexinspect's vocd-D of 245.48 is reproduced exactly by lexicalrichness, an independent implementation using scipy's unbounded curve fit. Text Inspector shows exactly 200.00. A least-squares optimum landing on a round 200.00 is implausible, so the likely cause is a ceiling or search bound at 200 in Text Inspector. That is an inference: Text Inspector's code was not inspected.

Results are from lexinspect 0.3.3 with `en_core_web_sm-3.8.0`. Every number is in [`study3-agreement.json`](study3-agreement.json); per-text values are in [`study3-agreement-per-text.csv`](study3-agreement-per-text.csv).

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
| lexinspect | 0.3.3, `en_core_web_sm` 3.8.0 | MIT | Tool under test |
| textstat | 0.7.13 | MIT | Readability reference. CMUdict via NLTK 3.10.3, Pyphen 0.18.1 fallback |
| TAALED | 0.32 | **CC BY-NC-SA 4.0**, per `License_CC-A-NC-SA-4.0.txt` in the GitHub repo; the PyPI package declares none | Diversity reference (Kyle's tool) |
| pylats | 0.64 | CC BY-NC-SA 4.0 (same) | TAALED's recommended preprocessing |
| lexical-diversity | 0.1.1 | PyPI classifier says MIT; licence field "UNKNOWN"; no licence file in the repo | Diversity reference (Kyle's earlier package) |
| lexicalrichness | 0.5.1 | MIT | Diversity reference, including vocd-D |

The reference packages are installed only in a throwaway `uv run --with` environment. None is vendored or added to `pyproject.toml`, so TAALED's non-commercial licence doesn't reach lexinspect. TAALED and pylats need `setuptools<81` because they still import `pkg_resources`. Python 3.12.5, pandas 3.0.6, scipy 1.18.1.

## Method

1. **Readability, each tool on the raw text.** lexinspect's `readability.analyze` was compared with textstat's formulas and counts (rounding off). For "Dale–Chall difficult words", textstat's count is the one its Dale–Chall formula uses: every word off the easy list. Its public `difficult_words()` defaults to words of 2+ syllables.
2. **Readability, formula only.** Each textstat formula was recomputed on lexinspect's counts with textstat's coefficients. For Fog and Dale–Chall, textstat's hard-word definitions were applied to lexinspect's words: Fog hard words are 3+ syllables and not on the easy list; Dale–Chall difficult words are anything off the easy list. A difference here is a definition difference, not a counting one.
3. **Syllables, word by word.** Every alphabetic word type in the corpus (14,914 types, 189,218 tokens) was counted by both syllable counters.
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
| Words | 1.000 | 1.000 | +1.84 | 1.84 | ±2% | 98.0 | yes |
| Sentences | .991 | .991 | −0.19 | 1.78 | ±10% | 80.3 | yes |
| Syllables | .997 | .997 | +39.8 | 39.8 | ±2% | 61.3 | yes |
| Syllables, words without digits | 1.000 | .999 | +11.2 | 11.2 | ±2% | 87.0 | yes |
| Polysyllabic words (3+) | .985 | .992 | +10.9 | 11.0 | ±5% | 48.0 | yes |
| Dale–Chall difficult words | .849 | .902 | −90.3 | 90.3 | ±5% | 0.0 | no |
| Flesch Reading Ease | .896 | .929 | −2.97 | 5.15 | ±5 | 63.3 | no |
| Flesch–Kincaid grade | .901 | .928 | +0.25 | 1.16 | ±0.5 | 44.0 | no |
| Gunning Fog | .923 | .946 | −0.71 | 1.16 | ±0.5 | 34.0 | no |
| SMOG | .961 | .954 | +0.39 | 0.64 | ±0.5 | 55.0 | yes |
| ARI | .921 | .959 | −1.06 | 1.29 | ±0.5 | 25.3 | no |
| Coleman–Liau | .997 | .996 | +0.27 | 0.30 | ±0.5 | 93.7 | yes |
| Dale–Chall raw score | .633 | .652 | −2.00 | 2.00 | ±0.5 | 3.0 | no |
| Linsear Write | .899 | .924 | +1.72 | 2.49 | ±0.5 | 23.7 | no |
| `text_standard` (different definitions) | .765 | .811 | +0.60 | 1.58 | ±1 | 55.3 | no |

By source, the formulas agree best on Gutenberg prose (Flesch, Flesch–Kincaid, Fog and SMOG all r ≥ .98). They agree least on Wikipedia, where numerals and `U.S.`-style abbreviations are common (FRE bias −11.3 on English and −9.8 on Simple Wikipedia), and on learner essays, where sentence punctuation is irregular. See `by_source` in the JSON.

### Readability: formula only (textstat formulas on lexinspect's counts)

| Formula | r | Bias | MAD | % within ±0.01 | Reading |
|---|---:|---:|---:|---:|---|
| Flesch Reading Ease | 1.000 | 0.000 | 0.003 | 100 | Same formula (MAD is lexinspect's 2-dp rounding) |
| Flesch–Kincaid grade | 1.000 | 0.000 | 0.003 | 100 | Same formula |
| SMOG | 1.000 | 0.000 | 0.003 | 100 | Same formula (1.043 vs 1.0430) |
| ARI | 1.000 | 0.000 | 0.002 | 100 | Same formula, but see the note on characters below |
| Coleman–Liau | 1.000 | +0.357 | 0.357 | 0 | Coefficient: lexinspect 0.0588 (Coleman & Liau 1975), textstat 0.058 |
| Gunning Fog | .945 | −0.94 | 1.24 | 5 | Hard-word definition: lexinspect excludes proper nouns, hyphenated compounds and words that reach 3 syllables only through -es/-ed/-ing (Gunning 1952); textstat excludes words on the Dale–Chall easy list |
| Dale–Chall raw score | .639 | −1.94 | 1.94 | 0 | Familiarity: lexinspect counts inflections of listed words, proper names and numerals as familiar (Chall & Dale 1995 rules); textstat counts only exact list entries as familiar |

ARI is identical given the same counts, but the counts differ by definition: textstat divides *all* non-space characters, punctuation included, by a word count that includes punctuation-only "words". lexinspect counts letters and digits.

### Syllables, word by word (same words)

| Word types | Types | Tokens | % types identical | % tokens identical | % types within 1 | Mean diff (lexinspect − textstat) |
|---|---:|---:|---:|---:|---:|---:|
| All | 14,914 | 189,218 | 93.4 | 99.0 | 98.2 | +0.08 |
| In CMUdict | 12,790 | 184,962 | **100.0** | **100.0** | 100.0 | 0.00 |
| Not in CMUdict | 2,124 | 4,256 | 53.4 | 54.3 | 87.6 | +0.54 |

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
| MTLD | TAALED original (`mtldo`) = lexical-diversity | .993 | −1.17 | 1.50 | 82.0 (±5%) | 30.3 |
| MTLD | TAALED default (`mtld`, mean factor length) | .988 | −1.21 | 2.17 | 76.3 (±5%) | 0 |
| vocd-D | lexicalrichness | 1.000 | 0.000 | 0.000 | 100 (±5%) | 0.3* |
| Maas a² | TAALED | 1.000 | −0.029 | 0.029 | 0 | 0 |

\* vocd-D agrees to four decimal places on every text. The two tools draw the same samples, because Python's `random.Random(42)` and `random.seed(42)` produce one stream. They differ only in the optimiser: lexinspect's golden-section search versus scipy's `curve_fit`.

Maas differs only in log base: TAALED uses log₁₀ and lexinspect uses natural logs, so TAALED's value is ln 10 ≈ 2.30 times lexinspect's. r = 1.000; compare Maas values only within one tool.

### Lexical diversity: each tool's own tokenisation (N = 300)

| Measure | Reference | r | ρ | Bias | MAD | % within tolerance | r > .95 |
|---|---|---:|---:|---:|---:|---:|:---:|
| Tokens | TAALED/pylats | .976 | .965 | +48.7 | 51.6 | 59.3 (±5%) | yes |
| Tokens | lexical-diversity | .999 | .995 | −8.6 | 10.6 | 95.3 | yes |
| Tokens | lexicalrichness | 1.000 | .999 | −6.0 | 6.5 | 99.3 | yes |
| MATTR | TAALED/pylats | .860 | .852 | +.032 | .033 | 13.3 (±.01) | no |
| MATTR | lexical-diversity | .968 | .958 | +.017 | .018 | 25.7 | yes |
| MATTR | lexicalrichness | .996 | .995 | −.000 | .003 | 97.0 | yes |
| MTLD | TAALED/pylats (original) | .833 | .826 | +13.5 | 13.9 | 12.7 (±5%) | no |
| MTLD | TAALED/pylats (default) | .828 | .820 | +13.5 | 13.9 | 11.7 | no |
| MTLD | lexical-diversity | .945 | .947 | +6.1 | 6.9 | 27.7 | no |
| MTLD | lexicalrichness | .975 | .981 | −0.1 | 2.8 | 72.0 | yes |
| HD-D | TAALED/pylats | .858 | .843 | +.031 | .031 | 13.0 (±.01) | no |
| HD-D | lexical-diversity | .971 | .949 | +.016 | .017 | 27.0 | yes |
| HD-D | lexicalrichness | .997 | .995 | −.000 | .002 | 99.0 | yes |
| vocd-D | lexicalrichness | .995 | .995 | −0.3 | 1.4 | 94.7 (±5%) | yes |

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
| pg37134-p00046 (*The Elements of Style*) | 49 | 38 | An outline ("A. Facts of composition… B. Kind of poem…" and numbered items). textstat drops the 1–2-word items; lexinspect counts them, including bare list numbers (`9`, `1`, `2`) as sentences. Edge case, not prose. |

### Words

The top five (wiki-en-043, pg36-p00596, pg25344-p00216, pg74-p00649, wiki-en-026; lexinspect +14 to +17) are all strings without a space that textstat counts as one word and lexinspect splits. Examples:

- `red-green` → `redgreen` and `parents/teachers` → `parentsteachers`;
- learner text with no space after a comma: `school,they` → `schoolthey`, `home,eat,relax,and` → `homeeatrelaxand`;
- em-dashes in fiction: `nearer—I` → `nearerI`;
- number ranges such as `1985–86`, which lexinspect has read as two numerals since 0.3.2 (wiki-en-043 has 17).

textstat also turns curly-apostrophe contractions into `didnt` and `Ive`, which then miss CMUdict. The word count is unchanged by that, but it moves syllables. lexinspect's counts are the right ones here, apart from the few glued words that remain (see [Tokenisation bugs](#tokenisation-bugs)), which push in the opposite direction.

On this measure lexinspect moved further from textstat after 0.3.0: identical counts on 50.0% of texts, down from 62.7%, and a bias of +1.84 words, up from +1.07. That is not a regression. Between 0.3.0 and 0.3.3, lexinspect's word count changed in 68 texts, always upwards, and every one of them (39 Gutenberg and 29 Wikipedia texts) contains strings like those above that lexinspect now splits and textstat still counts as one word.

### Syllables and polysyllables

Top five: wiki-en-020, wiki-simple-020, wiki-simple-021, wiki-simple-006, wiki-en-006, with lexinspect +204 to +231. Numerals cause most of it. lexinspect reads `1992` as *nineteen ninety-two* (4 syllables) and `2,000` as *two thousand*; textstat runs digits through Pyphen and gets 1. On wiki-en-020, the 70 words containing digits (68 numbers, plus `MoistCr1tikal` and `A100`) give 250 syllables in lexinspect against 70 in textstat. This is documented in CAVEATS.md ("Numerals are an approximation of speech") and is a **design choice**. Excluding words with digits cuts the overall bias from +40 to +11 syllables per text, and r rises to 1.000.

The remaining +11 comes from:

- textstat's merged words going to Pyphen (`redgreen`: on wiki-en-026, +111);
- Pyphen undercounting non-dictionary words;
- curly-apostrophe contractions (`didn’t` → `didnt` → Pyphen).

### Readability scores

- **Flesch, Flesch–Kincaid, Fog, ARI.** The top five are mostly ELLIPSE essays with almost no full stops. On ellipse-5F67A5D3DBB0, textstat finds 5 sentences of 120+ words and gives FRE −26.9 and FK grade 47.4. lexinspect's parser finds 10 sentences and gives FRE 34.3 and FK grade 23.7. Neither is meaningful for unpunctuated text; lexinspect's is less extreme. The Wikipedia entries in the top five are the `U.S.` and numeral effects above.
- **SMOG.** wiki-en-030, wiki-en-043, wiki-en-045 and wiki-simple-019 (lexinspect +2.4 to +3.7) are numeral syllables (96–211 syllables in words with digits in lexinspect, 23–43 in textstat), plus `U.S.` splitting on some. ellipse-5F67… (−3.1) is sentence counts.
- **Coleman–Liau.** The top five (wiki-en-030, wiki-simple-013, wiki-en-045, wiki-simple-017, wiki-simple-029) differ by 0.6–0.9: the 0.0588 coefficient (+0.36) plus `U.S.` sentence splitting. The best agreement of any formula.
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

- **MTLD vs TAALED, same tokens** (pg25344-p00300 97.3 vs 113.8; pg2701-p01047 126.3 vs 137.8; pg45-p00678; pg1400-p00592; ellipse-AAD6A5CBDDB9 51.5 vs 61.0).
  - TAALED and lexical-diversity won't close a factor shorter than 10 tokens, and close one only when TTR drops strictly *below* .72. lexinspect and lexicalrichness close at ≤ .72 with no minimum.
  - Rerunning TAALED's MTLD with the 10-token minimum removed gives exactly lexinspect's 126.32 on pg2701-p01047. On ellipse-AAD6A5CBDDB9 it gives 56.5; the remaining gap is the < versus ≤.
  - **Implementation variant, not a bug.** McCarthy & Jarvis (2010) don't specify a minimum factor length. Report which MTLD you used.
- **Own tokens, TAALED/pylats** (wiki-simple-006, wiki-en-006, wiki-en-018, wiki-simple-021, wiki-simple-013 for tokens, MATTR and HD-D). On wiki-simple-006, a biography of Christopher Plummer, pylats keeps 604 tokens against lexinspect's 931, because it drops every proper noun and every word not attested in COCA. Lemmatising (`played`, `plays` → `play_VERB`) lowers diversity further. On narrative texts such as pg45-p00678 and pg36-p00596, TAALED's MTLD is about 40% lower (39% and 38%) for the same reason. **Different construct:** TAALED measures lemma diversity of common vocabulary, lexinspect measures word-form diversity. Use one tool throughout a study.
- **Own tokens, lexical-diversity** (pg2680-p00081, pg25344-p00566, …): `flemmatize` lemmatises, and it deletes punctuation before splitting, merging words like textstat does.
- **Own tokens, lexicalrichness** (pg36-p00596 96.8 vs 120.1; wiki-en-042 127.8 vs 110.9; ellipse-194E86ED4117; pg1661-p00251; pg25344-p00492). lexicalrichness splits `don't` into `don` + `t` and deletes hyphens (`well-known` → `wellknown`); lexinspect keeps contractions and compounds whole, as CAVEATS.md documents. Under 0.3.0, pg205-p00336 (*Walden*) topped this list and was the worst case of the glued-word bug: 8 bogus types such as `deep,—not` and `forests;—the` raised its MTLD to 159.8 (lexicalrichness 134.7). Splitting those 8 tokens alone moved its MTLD to 130.6, which is what 0.3.3 gives.
- **vocd-D, own tokens** (pg36, pg74, pg1342, pg84, pg2701; lexicalrichness 8.6–11.2 higher). These are fiction with many contractions. lexicalrichness's `don` + `t` split adds frequent short "words" and raises its estimate. Tokenisation, not formula: on the same tokens the two agree to four decimal places.

## Tokenisation bugs

All were tokenisation issues, fixed in `_nlp.py`, `_text.py` and `readability.py`. None changed a formula.

### Found under 0.3.0

**1. Words glued through dashes, quotes or brackets counted as one word.** spaCy doesn't split `last”—he` or `was—“impressively”—big`: its infix rules split an em-dash only between two letters. lexinspect 0.3.0's `_group_words` then treated the token as one word, because it contains letters. Under 0.3.0:

```python
>>> from lexinspect._text import analyse
>>> a = analyse("It was—“impressively”—big, he said “at last”—then left.")
>>> [w.text for w in a.words]
['It', 'was—“impressively”—big', 'he', 'said', 'at', 'last”—then', 'left']
>>> # expected 10 words: It was impressively big he said at last then left
```

Under 0.3.3 the same call gives the ten expected words.

In this corpus under 0.3.0: 146 glued words in 53 of 300 texts. 41 were Gutenberg texts, where `,—` and `”—` are common, plus `great,[2`-style reference remnants and `quickly)and`. Splitting them moved the word count by a median of 0.2% (max 1.6%) of tokens. MATTR barely moved (max .007). MTLD moved by a median of 0.2% but up to **22%** (*Walden*), because each glued word is a unique type. Syllables of glued words were summed over their letters, so readability was only slightly affected.

**2. Digit strings that aren't plain numbers got 0 syllables and counted as diversity tokens.** In 0.3.0, `_text._NUMERIC` matched `1914` but not `1914–1918`, `11:00`, `1/4` or `3-4`. These were therefore not numeric. `_parts` found no alphabetic part, so `word_syllables` returned 0. They still counted as words in every readability denominator, and they stayed in `diversity.tokens`, which the docs say excludes numerals. Under 0.3.0:

```python
>>> from lexinspect._text import analyse
>>> from lexinspect import readability, diversity
>>> a = analyse("The war lasted from 1914–1918 and the meeting began at 11:00 in 1914.")
>>> [(w.text, readability.word_syllables(w), w.is_numeric) for w in a.words if any(c.isdigit() for c in w.text)]
[('1914–1918', 0, False), ('11:00', 0, False), ('1914', 4, True)]
>>> diversity.tokens(a)   # numerals are meant to be excluded
['the', 'war', 'lasted', 'from', '1914–1918', 'and', 'the', 'meeting', 'began', 'at', '11:00', 'in']
```

Under 0.3.3 the range is two numerals of 4 syllables each, `11:00` is a numeral of 5 syllables, and none of them is a diversity token.

In this corpus under 0.3.0: 155 such words in 51 texts, almost all Wikipedia (year and score ranges, times, fractions). Each lowered syllables per word slightly, making a text look a little easier. They contradicted both the "numerals excluded" rule in diversity and the "numerals are read as spoken" rule in readability.

### Fixed in 0.3.2 and 0.3.3

- **0.3.2** made em and en dashes, and quote marks touching them, separate words. It made times, fractions and hyphenated number ranges numerals, read part by part, and split en-dash ranges into two numerals.
- **0.3.3** extended them after a rerun of this study and an independent audit showed the 0.3.2 fixes were incomplete. It handles typewriter dashes (`--`), figure and horizontal dashes, punctuation left before a dash, brackets and punctuation glued to words by a missing space (`great,[2`, `quickly)and`), and numerals written with Unicode characters (`30½`, `1⁄12`). The audit also found a closing single quote absorbed into the word before it as if it were a possessive (`‘quoted’` read as the word `quoted’`, a separate diversity type). 0.3.3 fixed that too, and the diagnostics now check for it.

[CHANGELOG.md](../../CHANGELOG.md) has the details.

### What remains under 0.3.3

The diagnostics (`scripts/validation/study3_agreement/diagnostics.py`), rerun under 0.3.3, find:

- **19 glued words in 13 texts** (2 Gutenberg, 9 Wikipedia, 2 ELLIPSE). Six are false positives of the detector: a number with a thousands comma inside a hyphenated compound (`2,148-foot`, `80,000-capacity`), which is rightly one word. Three are footnote markers in *The Federalist Papers* (`power(1`, `party(1`, `Constitution(2`), three are letters in brackets inside a word (`piece(s`, `loud[er`, `do[es`), and seven join two words through a bracket, quote or punctuation mark with no space (`rocket(Falcon`, `Netherlands),and`, `stronger?,I`). Splitting them would change the word count of the affected texts by a median of 0.1% (max 0.5%), MATTR by at most .002 and MTLD by at most 5.6%.
- **7 digit strings with 0 syllables in 4 texts:** equation and footnote markers (`8)`, `"(2`), a fraction with a space before the fraction slash (`29 ⁄2`, which leaves `⁄2` as a word), and `39½.` with a full stop attached.
- **No closing quotes absorbed into words.** The check counts words that end in a bare apostrophe after a letter other than *s*.

These are known limitations of 0.3.3.

## In plain English

- **The formulas themselves are right.** Fed the same words, lexinspect's MATTR, HD-D, MSTTR, TTR, MTLD and vocd-D each give the same number as at least one independent tool, to four decimal places. Maas differs only in log base. Its Flesch, Flesch–Kincaid, SMOG and ARI give the same numbers as textstat's when fed the same counts.
- **Different tools count text differently.** Fed real text, readability scores differ from textstat's by about 1 grade level on average, and by much more on texts with lots of numbers, abbreviations like "U.S." or missing full stops. That is because each tool counts words, sentences and syllables its own way, and lexinspect's way is usually the more defensible one.
- **A few formulas differ on purpose.** lexinspect deliberately follows the original Gunning Fog, Dale–Chall and Coleman–Liau definitions where textstat doesn't.
- **Don't mix tools in one study.** TAALED, the tool most often used in diversity research, lemmatises and throws away names. Its diversity scores are systematically lower than lexinspect's and rank texts only moderately alike (r ≈ .85). If you compare your numbers with a paper, use the tool the paper used.
- **vocd-D vs Text Inspector.** The 200 vs 245 gap most likely comes from a ceiling of 200 in Text Inspector rather than a mistake in lexinspect. This is inferred from its outputs (see below), not from its code.
- **Tokenisation bugs, now mostly fixed.** In 0.3.0, words stuck together by a dash and a quote, and number ranges like "1914–1918", were mishandled. 0.3.2 and 0.3.3 fixed them. A few rarer forms remain in 0.3.3: the diagnostics flag 19 glued words (6 of them false positives) and 7 digit strings in 300 texts, and splitting every flagged word would move MTLD by at most 5.6%.

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
- **Extraction artefacts.** A few Wikipedia paragraphs keep fragments of reference marks (`great,[2`). They are in the texts all tools saw, so they don't bias the comparison, but they added to the glued-word count under 0.3.0.
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
