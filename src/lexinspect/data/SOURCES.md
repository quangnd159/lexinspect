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

**Adaptation:** `this paper`, `this study` and similar phrases standing in for the writers are counted as self-mentions. Hyland (2005, p. 51) lists *the paper proposes* among frame markers. lexinspect files these under self-mentions because they refer to the writers' own work.

**Caveat:** The marker lists are factual lexical inventories; the 10-category taxonomy is Hyland's intellectual contribution. Cite Hyland (2005) in any output. Numbers will not match Text Inspector's metadiscourse module: Text Inspector uses the Bax, Nakatsuhara & Waller (2019) 13-category extension, whose marker inventory is not public.

## phrase.json

**Martinez, R., & Schmitt, N. (2012).** A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.

506 phrasal expressions across K1–K5 BNC frequency bands, with example sentences and genre frequency markers (spoken general / written general / written academic). Sourced from Norbert Schmitt's [resources page](https://www.norbertschmitt.co.uk/vocabulary-resources). The published total is 505; lexinspect parses 506. All 506 are distinct; the extra entry is a slot-variant boundary case, not a duplicate.

`build_phrase_index.py` adds three fields to each entry: `variants` (the token sequences the printed form stands for, with `X/Y` alternatives and optional words expanded and `ONE'S`/`ONESELF` as slots), `sense` (the parenthetical gloss, if any) and `tags` (the Penn tag of each `to`, `that` or particle in the entry's own example sentence, which the matcher requires the text to share).

**Licence:** No SPDX-identifiable licence on the source page. Schmitt's resources page publishes the list without terms of use; the "freely available for research and pedagogical purposes" line on that page belongs to the Vocabulary Levels Tests, not the PHRASE List. Both authors gave lexinspect permission by email (Norbert Schmitt, 2026-10-16; Ron Martinez, 2026-10-30). It covers the free hosted app and this bundled file, variant fields included, with Martinez & Schmitt (2012) cited. It does not cover commercial use or reuse outside lexinspect; ask the authors for those. The replies are recorded in `docs/permissions.md` in the lexinspect repository.

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

## alternatives.json

Simpler same-POS synonyms for CEFR headwords at A2 and above, for `alternatives.py` (adapting a text to a target level). Built by `scripts/build_data/build_alternatives.py` from:

- **Open English WordNet 2025** (`english-wordnet-2025.xml.gz` from the [2025-edition release](https://github.com/globalwordnet/english-wordnet/releases/tag/2025-edition), SHA-256 `9ca6d1dcb75f822fdd66617f7d9da48142ace38dd544d6ad5e2feca1674ad3fe`). McCrae, J. P., Rademaker, A., Bond, F., Rudnicka, E., & Fellbaum, C. (2019). English WordNet 2019 – An open-source WordNet for English. *Proceedings of the 10th Global WordNet Conference (GWC 2019)*. Every suggestion is a member of an OEWN synset (or, for adjectives, of the head synset its satellite is `similar` to). **Licence: CC BY 4.0.**
- **Princeton WordNet 3.0** database (`WNdb-3.0.tar.gz` from wordnetcode.princeton.edu, SHA-256 `658b1ba191f5f98c2e9bae3e25c186013158f30ef779f191d2a44e5d25046dc8`). Only the SemCor tag counts in `index.sense` are read, to find each word's dominant sense; OEWN keeps the 3.0 sense keys but ships every count as 0. No WordNet 3.0 text or relation is copied. Fellbaum, C. (Ed.) (1998). *WordNet: An Electronic Lexical Database.* MIT Press.
- The CEFR levels in `cefr.json` and BNC/COCA bands in `bnc_coca.json`, which each suggestion carries.

656 headword–POS entries, 787 suggestions (at most 5 each), plus a table of the inflected forms of suggested words that the runtime's suffix rules would get wrong, generated at build time with [lemminflect](https://github.com/bjascob/LemmInflect) 0.2.3 (MIT; not a runtime dependency).

The selection favours precision over recall: only each word's dominant WordNet sense is used, a candidate's own main sense must be the shared one, usage-labelled (slang, archaic, obscene, disparaging) senses are dropped, and reviewed block lists remove what the statistics miss. In a spot check of 150 random entries, made by the AI agent that built the file and not by human judges, about 9 in 10 suggestions were acceptable substitutes in the word's main sense. Treat that as an engineering check, not a measured precision. They are suggestions for a human editor, not automatic rewrites.

**Licence: CC BY-SA 4.0.** The file adapts OEWN (CC BY 4.0, which allows a BY-SA adaptation) and carries values from `cefr.json` and `bnc_coca.json` (CC BY-SA 4.0). Credit Open English WordNet, the CEFR-J and Octanove lists and Paul Nation. OEWN derives from Princeton WordNet, and WordNet 3.0's tag counts shaped the selection, so its notice travels with the file:

> WordNet 3.0 Copyright 2006 by Princeton University. All rights reserved.
>
> Permission to use, copy, modify and distribute this software and database and its documentation for any purpose and without fee or royalty is hereby granted, provided that you agree to comply with the following copyright notice and statements, including the disclaimer, and that the same appear on ALL copies of the software, database and documentation, including modifications that you make for internal use or for distribution.
>
> THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED. BY WAY OF EXAMPLE, BUT NOT LIMITATION, PRINCETON UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES OF MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF THE LICENSED SOFTWARE, DATABASE OR DOCUMENTATION WILL NOT INFRINGE ANY THIRD PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR OTHER RIGHTS.
>
> The name of Princeton University or Princeton may not be used in advertising or publicity pertaining to distribution of the software and/or database. Title to copyright in this software, database and any associated documentation shall at all times remain with Princeton University and LICENSEE agrees to preserve same.

## cmudict.zip

**The Carnegie Mellon Pronouncing Dictionary**, version 0.7a, in the NLTK corpus distribution (`cmudict/cmudict` plus `cmudict/README`). Copyright (C) 1993–2008 Carnegie Mellon University.

Read directly from the zip by `_syllables.py` (no NLTK); syllables are the stress-marked vowels of each word's first listed pronunciation. **Licence:** BSD-style; redistribution must retain the copyright notice and conditions, which are in the bundled `cmudict/README`.

## dale_chall_easy_words.txt

The Dale–Chall familiar-word list as distributed with [textstat](https://github.com/textstat/textstat) (`textstat/resources/en/easy_words.txt`, 2,940 words, unchanged). The list itself is from Dale & Chall; see Chall, J. S., & Dale, E. (1995). *Readability Revisited: The New Dale–Chall Readability Formula.* Brookline Books.

**Licence:** textstat is MIT, Copyright (c) 2016 Shivam Bansal. The notice ships alongside the list in `LICENSES/textstat-MIT.txt`.

## level_model.json

Coefficients, thresholds and standardisation figures of the reading-text CEFR level estimate (`level.py`): a proportional-odds regression on lexinspect's own CEFR, BNC/COCA, readability and diversity outputs, built by `scripts/build_data/build_level_model.py`. Training data, downloaded at pinned revisions with SHA-256 checks (listed in the file) and not redistributed:

- **Xia, M., Kochmar, E., & Briscoe, T. (2016).** Text readability assessment for second language learners. *Proceedings of the 11th Workshop on Innovative Use of NLP for Building Educational Applications*, 12–22. Cambridge English exam reading passages, KET–CPE (A2–C2). **CC BY-NC-SA 4.0**; the dataset's terms also restrict information derived from it to non-commercial research and education.
- **Breuker, M. (2023).** CEFR labelling and assessment services. In G. Rehm (Ed.), *European Language Grid*. Springer. doi:10.1007/978-3-031-17258-8_16. ELG-CEFR-EN graded reading texts (A1–C1), minus the passages it shares with the Cambridge set. **CC BY-NC 4.0** (dataset card; records say CC BY-NC-SA 4.0).
- Both via **UniversalCEFR**: Imperial, J. M., et al. (2025). UniversalCEFR: Enabling open multilingual research on language proficiency assessment. *EMNLP 2025*. arXiv:2506.01419.

**Licence:** the file is an adaptation of those datasets and is **CC BY-NC-SA 4.0**. It holds no text from them. It is offered only in free, non-commercial lexinspect. The file also records its held-out evaluation, and a comparison with CVLA (Uchida, S., & Negishi, M. (2018). Assigning CEFR-J levels to English texts based on textual features. *Proceedings of the 4th Asia Pacific Corpus Linguistics Conference*, 463–467), whose published coefficients `level.cvla` implements.

## hunspell/ (en_GB, en_US)

**LibreOffice English dictionaries**: `.aff` affix files and `.dic` wordlists for British and American English.

Vendored from [LibreOffice/dictionaries](https://github.com/LibreOffice/dictionaries), pinned to commit `e7f163feb2beaf526135132d8716e68e19d2716e`. `spylls` implements the Hunspell algorithm but ships no dictionary data, so these files are required at runtime.

**Licences** (full texts in `LICENSES/`):
- **en_GB:** wordlist based on Kevin Atkinson's original English wordlist and updated by David Bartlett, Brian Kelk, Andrew Brown and Marco A. G. Pinto, **LGPL**; affix file by David Bartlett and Andrew Brown, also **LGPL** (`README_en_GB.txt`).
- **en_US:** wordlist from SCOWL, under the SCOWL copyright (Kevin Atkinson and others; permissive notices); affix file derived from Geoff Kuenning's Ispell `english.aff`, **BSD** (`README_en_US.txt`).

**Why vendored rather than downloaded:** they used to be fetched from GitHub on first use. On a serverless host the cache is ephemeral, so every cold start refetched them, and a burst of cold starts got HTTP 429. More seriously, `spylls` compiles the `.aff` file into Python regexes, so whatever that URL returned became code we executed. Pinning and vendoring makes the bytes we run auditable.
