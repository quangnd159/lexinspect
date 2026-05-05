# Data sources and licences

Each bundled JSON file derives from a published vocabulary resource. Cite the original creators in any publication that uses lexinspect output.

## awl.json

**Coxhead, A. (2000).** *A new academic word list.* TESOL Quarterly, 34(2), 213–238.

570 head words across 10 sublists, 3,111 inflected forms. Sourced from the [fildpauz/adaps](https://github.com/fildpauz/adaps) `CoxheadAWL.xml` mirror. The list itself is freely usable for educational and research purposes; redistributing the data is standard practice in ELT tooling.

## bnc_coca.json

**Nation, P.** BNC/COCA word-family lists (1k–10k headwords).

Sourced from the [lpmi-13/machine_readable_wordlists](https://github.com/lpmi-13/machine_readable_wordlists) **CC0 1.0 Universal** mirror (`General/BNC_COCA/BNC_COCA.json`). 9,998 head words across 10 bands of 1,000.

**Trade-off:** This mirror contains head words only — Nation's full family-level data with derivational members lives in his WordFamilyFinder desktop app and is not exposed as a clean download. lexinspect compensates by trying surface form first, then spaCy lemma. Tokens like *analytical* or *analytically* will under-detect against the *analyse* head word; this is the documented cost of staying CC0.

For richer family-level matching see the `wen-zhi/the-bnc-coca-lists` 1k–9k CSV (unstated licence — opt-in only).

## ngsl.json

**Browne, C., Culligan, B., & Phillips, J. (2013).** The New General Service List 1.2.

2,809 lemmas with SFI rank and adjusted frequency per million. Source: [newgeneralservicelist.com](https://www.newgeneralservicelist.com/). **Licence: CC-BY-SA 4.0** — redistribution permitted with attribution and same-licence sharing of any derivative.

## nawl.json

**Browne, C., Culligan, B., & Phillips, J. (2013).** The New Academic Word List 1.2.

959 academic lemmas with inflected forms, designed for use after NGSL. Source: [newgeneralservicelist.com](https://www.newgeneralservicelist.com/). **Licence: CC-BY-SA 4.0**.

## phrase.json

**Martinez, R., & Schmitt, N. (2012).** A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.

506 phrasal expressions across K1–K5 BNC frequency bands, with example sentences and genre frequency markers (spoken general / written general / written academic). Sourced from Norbert Schmitt's [resources page](https://www.norbertschmitt.co.uk/vocabulary-resources). The published total is 505; lexinspect parses 506 (one duplicate or boundary case in the source `.doc`; not material for analysis).

**Licence:** No SPDX-identifiable licence on the source page. The author's site states the materials are "freely available for research and pedagogical purposes." Treat as non-commercial educational use; cite Martinez & Schmitt (2012) in any publication. If lexinspect is later wrapped in a commercial web product, request explicit redistribution permission.
