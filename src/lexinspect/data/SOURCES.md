# Data sources and licences

Each bundled data file derives from a published resource. Cite the original creators in any publication that uses lexinspect output. Build scripts and upstream file names are in `scripts/build_data/README.md`.

## awl.json

**Coxhead, A. (2000).** *A new academic word list.* TESOL Quarterly, 34(2), 213–238.

570 word families across 10 sublists, 3,111 forms. Sourced from the [fildpauz/adaps](https://github.com/fildpauz/adaps) `CoxheadAWL.xml` mirror. The list is freely usable for educational and research purposes; redistributing it is standard practice in ELT tooling.

## bnc_coca.json

**Nation, I. S. P. (2017).** *The BNC/COCA Level 6 word family lists* (Version 1.0.0). Victoria University of Wellington. [Paul Nation's vocabulary lists](https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/vocabulary-lists).

Built from `BNC_COCA_25000.zip` (`basewrd1.txt` … `basewrd34.txt`). Bands 1–25: 25,000 Level 6 word families, 1,000 per band, every family member included (75,679 forms). Lists 31–34 are kept as supplementary lists: proper names, marginal words, transparent compounds and acronyms.

**Licence: CC BY-SA 4.0.** `bnc_coca.json` is an adaptation (reformatted, lowercased, families keyed by headword) and is therefore also CC BY-SA 4.0. Credit Paul Nation and keep the same licence on any redistribution.

Earlier versions bundled the CC0 headwords-only mirror from lpmi-13/machine_readable_wordlists (10 bands, no family members), which left `clearly`, `unclear` and `colour` off-list. It is no longer used.

## ngsl.json

**Browne, C., Culligan, B., & Phillips, J. (2013).** The New General Service List 1.2.

2,809 lemmas with SFI rank, SFI and adjusted frequency per million (from `NGSL_12_stats.csv`), and every inflected and UK/US form from the "lemmatized for teaching" list (`NGSL_12_lemmatized_for_teaching.csv`), 8,514 forms in all. Source: [newgeneralservicelist.com](https://www.newgeneralservicelist.com/). **Licence: CC BY-SA 4.0**; `ngsl.json` is an adaptation under the same licence.

## nawl.json

**Browne, C., Culligan, B., & Phillips, J. (2013).** The New Academic Word List 1.2.

959 academic lemmas with inflected forms (British and American spellings both appear), from the "lemmatized for research" file. Designed for use after NGSL. Source: [newgeneralservicelist.com](https://www.newgeneralservicelist.com/). **Licence: CC BY-SA 4.0**; `nawl.json` is an adaptation under the same licence.

## cefr.json

Two combined sources covering A1–C2:

**CEFR-J Vocabulary Profile 1.5 (A1–B2).** Compiled by Yukio Tono, Tokyo University of Foreign Studies. Source: [openlanguageprofiles/olp-en-cefrj](https://github.com/openlanguageprofiles/olp-en-cefrj) (`cefrj-vocabulary-profile-1.5.csv`). **Terms of use:** free for research and commercial use with citation. Copyright Tono Laboratory, TUFS.

**Octanove Vocabulary Profile C1/C2 1.0.** Octanove Labs. Same repo (`octanove-vocabulary-profile-c1c2-1.0.csv`). **Licence: CC BY-SA 4.0**.

Combined: 8,845 headwords (A1 1,084; A2 1,272; B1 2,174; B2 2,490; C1 929; C2 896, counted at each headword's lowest level). Slash-variant headwords (`a.m./A.M./am/AM`) are split into separate keys. Each headword keeps a level per part of speech (`present`: noun A1, adjective B1, verb B2); the same headword and part of speech listed twice keeps the lower level. Because the file merges Octanove's CC BY-SA data, share `cefr.json` under CC BY-SA 4.0 with both credits.

**Not Cambridge English Vocabulary Profile.** Different corpora, different methodology; outputs will diverge from EVP-based tools. Do not present results as EVP-equivalent. Cite Tono (CEFR-J) and Octanove Labs in any publication.

## metadiscourse.json

**Hyland, K. (2005).** *Metadiscourse: Exploring Interaction in Writing.* Continuum, London and New York.

10-category framework (interactive: transitions, frame markers, endophoric markers, evidentials, code glosses; interactional: hedges, boosters, attitude markers, engagement markers, self-mentions). 490 markers.

**Provenance:**
- **Hedges (100 markers):** mirror of Hyland 2005 Appendix A from [HLTCHKUST/framing-bias-metric](https://github.com/HLTCHKUST/framing-bias-metric/blob/main/data/lexicons/bias_related_lexicons/hedges_hyland2005.txt), lowercased and deduplicated. No stated licence; treated as research and educational use.
- **Other 9 categories (23–60 markers each):** curated reference subset drawn from canonical Hyland 2005 reproductions widely cited in the L2 academic-writing literature. Not the full Appendix A.

The context rules that decide when a listed marker counts live in `metadiscourse.py`, not in this file.

**Caveat:** The marker lists are factual lexical inventories; the 10-category taxonomy is Hyland's intellectual contribution. Cite Hyland (2005) in any output. Numbers will not match Text Inspector's metadiscourse module: Text Inspector uses the Bax, Nakatsuhara & Waller (2019) 13-category extension, whose marker inventory is not public.

## phrase.json

**Martinez, R., & Schmitt, N. (2012).** A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.

506 phrasal expressions across K1–K5 BNC frequency bands, with example sentences and genre frequency markers (spoken general / written general / written academic). Sourced from Norbert Schmitt's [resources page](https://www.norbertschmitt.co.uk/vocabulary-resources). The published total is 505; lexinspect parses 506. All 506 are distinct; the extra entry is a slot-variant boundary case, not a duplicate.

`build_phrase_index.py` adds three fields to each entry: `variants` (the token sequences the printed form stands for, with `X/Y` alternatives and optional words expanded and `ONE'S`/`ONESELF` as slots), `sense` (the parenthetical gloss, if any) and `tags` (the Penn tag of each `to`, `that` or particle in the entry's own example sentence, which the matcher requires the text to share).

**Licence:** No SPDX-identifiable licence on the source page. The author's site states the materials are "freely available for research and pedagogical purposes." Treat as non-commercial educational use and cite Martinez & Schmitt (2012). If lexinspect is wrapped in a commercial web product, request explicit redistribution permission.

## spelling.json

**VarCon** (Variant Conversion Info), part of SCOWL, by Kevin Atkinson and Benjamin Titze. [wordlist.aspell.net/varcon-readme](http://wordlist.aspell.net/varcon-readme/).

British ↔ American pairs from `varcon.txt`, restricted to SCOWL commonness level 70 and below: 5,962 British-to-American and 5,961 American-to-British single-word pairs, primary spellings only. Used only to retry list and CMUdict lookups under the other spelling; `_spelling.py` adds a few irregular pairs and regular-pattern rules of its own.

**Licence:** VarCon's permissive notice (the same text is reproduced in `hunspell/LICENSES/README_en_US.txt`):

> Copyright 2000-2016 by Kevin Atkinson
>
> Permission to use, copy, modify, distribute and sell this array, the associated software, and its documentation for any purpose is hereby granted without fee, provided that the above copyright notice appears in all copies and that both that copyright notice and this permission notice appear in supporting documentation. Kevin Atkinson makes no representations about the suitability of this array for any purpose. It is provided "as is" without express or implied warranty.
>
> Copyright 2016 by Benjamin Titze
>
> Permission to use, copy, modify, distribute and sell this array, the associated software, and its documentation for any purpose is hereby granted without fee, provided that the above copyright notice appears in all copies and that both that copyright notice and this permission notice appear in supporting documentation. Benjamin Titze makes no representations about the suitability of this array for any purpose. It is provided "as is" without express or implied warranty.

The release used carries copyright years 2000–2020; the terms are unchanged.

## cmudict.zip

**The Carnegie Mellon Pronouncing Dictionary**, version 0.7a, in the NLTK corpus distribution (`cmudict/cmudict` plus `cmudict/README`). Copyright (C) 1993–2008 Carnegie Mellon University.

Read directly from the zip by `_syllables.py` (no NLTK); syllables are the stress-marked vowels of each word's first listed pronunciation. **Licence:** BSD-style; redistribution must retain the copyright notice and conditions, which are in the bundled `cmudict/README`.

## dale_chall_easy_words.txt

The Dale–Chall familiar-word list as distributed with [textstat](https://github.com/textstat/textstat) (`textstat/resources/en/easy_words.txt`, 2,940 words, unchanged). The list itself is from Dale & Chall; see Chall, J. S., & Dale, E. (1995). *Readability Revisited: The New Dale–Chall Readability Formula.* Brookline Books.

**Licence:** textstat is MIT, Copyright (c) 2016 Shivam Bansal.

## hunspell/ (en_GB, en_US)

**LibreOffice English dictionaries**: `.aff` affix files and `.dic` wordlists for British and American English.

Vendored from [LibreOffice/dictionaries](https://github.com/LibreOffice/dictionaries), pinned to commit `e7f163feb2beaf526135132d8716e68e19d2716e`. `spylls` implements the Hunspell algorithm but ships no dictionary data, so these files are required at runtime.

**Licences** (full texts in `LICENSES/`):
- **en_GB:** wordlist based on Kevin Atkinson's original English wordlist and updated by David Bartlett, Brian Kelk, Andrew Brown and Marco A. G. Pinto, **LGPL**; affix file by David Bartlett and Andrew Brown, also **LGPL** (`README_en_GB.txt`).
- **en_US:** wordlist from SCOWL, under the SCOWL copyright (Kevin Atkinson and others; permissive notices); affix file derived from Geoff Kuenning's Ispell `english.aff`, **BSD** (`README_en_US.txt`).

**Why vendored rather than downloaded:** they used to be fetched from GitHub on first use. On a serverless host the cache is ephemeral, so every cold start refetched them, and a burst of cold starts got HTTP 429. More seriously, `spylls` compiles the `.aff` file into Python regexes, so whatever that URL returned became code we executed. Pinning and vendoring makes the bytes we run auditable.
