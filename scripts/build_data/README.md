# Data build scripts

One-shot extractors that turn upstream sources into the data files in `src/lexinspect/data/`. Run them when an upstream version bumps. They write into the package data directory directly and are safe to re-run. Provenance and licences for every file are in `src/lexinspect/data/SOURCES.md`.

| Script | Writes | Inputs |
|---|---|---|
| `build_awl.py` | `awl.json` | `/tmp/awl.xml` |
| `build_phase2.py` | `nawl.json`, base `phrase.json` (also old-format `bnc_coca.json` and `ngsl.json`, which `build_lists.py` overwrites) | `/tmp/lex2/` |
| `build_phase4.py` | `metadiscourse.json` | `/tmp/lex4/hedges.txt` |
| `build_lists.py SRC_DIR` | `bnc_coca.json`, `ngsl.json`, `cefr.json`, `spelling.json` | files in `SRC_DIR` |
| `build_phrase_index.py` | adds `variants`, `sense` and `tags` to `phrase.json` in place | `phrase.json`, spaCy `en_core_web_sm` |

`build_phase3.py` (the old `cefr.json` builder) is superseded by `build_lists.py`. The scripts write into `src/lexinspect/data/` relative to the checkout.

`cmudict.zip`, `dale_chall_easy_words.txt` and `hunspell/` are vendored as downloaded, with no build step.

## Sources

Download into the directories above (for `build_lists.py`, any directory you pass as `SRC_DIR`):

- **AWL** — `https://raw.githubusercontent.com/fildpauz/adaps/master/tools/CoxheadAWL.xml` → `/tmp/awl.xml`
- **NAWL** — `NAWL_12_lemmatized_for_research.csv` from [newgeneralservicelist.com](https://www.newgeneralservicelist.com/) → `/tmp/lex2/nawl.csv` (Windows-1252: `iconv -f WINDOWS-1252 -t UTF-8`)
- **PHRASE** — `https://www.norbertschmitt.co.uk/_files/ugd/5f2482_63c555de9e3f4c09af4170ba051b3bbe.doc` → `/tmp/lex2/phrase.doc`, then `textutil -convert txt` to `phrase.txt`
- **Metadiscourse hedges** — `https://raw.githubusercontent.com/HLTCHKUST/framing-bias-metric/main/data/lexicons/bias_related_lexicons/hedges_hyland2005.txt` → `/tmp/lex4/hedges.txt`

`build_phase2.py` also expects `/tmp/lex2/bnc_coca.json` and `/tmp/lex2/ngsl.csv` for its now-superseded outputs; give it the old inputs or comment those two calls out.

For `build_lists.py`, `SRC_DIR` must contain:

- `BNC_COCA_25000/` — `basewrd1.txt` … `basewrd34.txt`, extracted from `BNC_COCA_25000.zip` on [Paul Nation's vocabulary lists page](https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/vocabulary-lists). Bands 1–25 are the families; 31–34 the supplementary lists.
- `NGSL_12_stats.csv` and `NGSL_12_lemmatized_for_teaching.csv` — from [newgeneralservicelist.com](https://www.newgeneralservicelist.com/).
- `cefrj-vocabulary-profile-1.5.csv` and `octanove-vocabulary-profile-c1c2-1.0.csv` — from `https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/`.
- `varcon.txt` — from a VarCon release on [SourceForge](https://sourceforge.net/projects/wordlist/files/VarCon/) (see the [VarCon README](http://wordlist.aspell.net/varcon-readme/)). Read as Latin-1; only pairs at SCOWL level 70 or below are kept.

## Refresh procedure

```bash
uv run python scripts/build_data/build_awl.py
uv run python scripts/build_data/build_phase2.py
uv run python scripts/build_data/build_phase4.py
uv run python scripts/build_data/build_lists.py SRC_DIR
uv run python scripts/build_data/build_phrase_index.py
uv run pytest
```

Order matters: `build_lists.py` must run after `build_phase2.py` so its `bnc_coca.json` and `ngsl.json` win, and `build_phrase_index.py` must run after any rebuild of `phrase.json`, because `build_phase2.py` writes it without the compiled fields the matcher needs. `build_phrase_index.py` prints the entries whose example sentence doesn't contain the phrase; those get no tag constraints. Failing tests afterwards usually mean schema drift in an upstream file.
