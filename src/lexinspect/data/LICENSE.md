# Data licences

lexinspect's code is MIT (the `LICENSE` file at the repository root). **That licence does not cover the files in this directory.** Each one comes from published research or an open project and keeps its creators' terms. Full provenance, versions and citations are in [SOURCES.md](SOURCES.md).

| File | Source | Terms |
| --- | --- | --- |
| `bnc_coca.json` | Paul Nation, BNC/COCA word-family lists | CC BY-SA 4.0 (this adaptation too) |
| `ngsl.json`, `nawl.json` | Browne, Culligan & Phillips, NGSL 1.2 / NAWL 1.2 | CC BY-SA 4.0 (adaptations too) |
| `cefr.json` | CEFR-J Vocabulary Profile 1.5 (Tono Laboratory, TUFS) merged with Octanove C1/C2 1.0 | CEFR-J: free for research and commercial use with citation. Octanove: CC BY-SA 4.0, so the merged file is CC BY-SA 4.0 |
| `awl.json` | Coxhead (2000), Academic Word List | Freely usable for educational and research purposes; no open licence |
| `phrase.json` | Martinez & Schmitt (2012), PHRASE List | No open licence. Used in lexinspect with both authors' permission (Schmitt 2026-10-16, Martinez 2026-10-30) |
| `metadiscourse.json` | After Hyland (2005); hedges from a public mirror of Appendix A | No stated licence; used for research and education |
| `spelling.json` | VarCon (Kevin Atkinson, Benjamin Titze) | Permissive notice, reproduced in SOURCES.md |
| `hunspell/` | LibreOffice English dictionaries | en_GB: LGPL. en_US: SCOWL wordlist (permissive) and Ispell affix file (BSD). Full texts in `hunspell/LICENSES/` |
| `cmudict.zip` | Carnegie Mellon Pronouncing Dictionary 0.7a | BSD-style; notice in the zip's `cmudict/README` |
| `dale_chall_easy_words.txt` | Dale–Chall list as distributed with textstat | MIT, Copyright (c) 2016 Shivam Bansal; notice in `LICENSES/textstat-MIT.txt` |

What this means in practice:

- **Redistributing lexinspect or its data:** keep this file, `SOURCES.md` and the `LICENSES/` folders with it. The CC BY-SA files must stay CC BY-SA and credit their creators.
- **Free educational or research use** (what the hosted app is) fits every licence above.
- **Commercial use:** the AWL, PHRASE and metadiscourse lists have no open licence. Ask their authors for permission first, or replace those files. The PHRASE authors' permission covers lexinspect's free use, not commercial use or reuse elsewhere.
- **Publications:** cite the original creators listed in `SOURCES.md`, not just lexinspect.
