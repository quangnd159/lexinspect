# Data build scripts

One-shot extractors that turn upstream sources into the JSON files in `src/lexinspect/data/`. Run them when an upstream version bumps.

Each script expects its inputs in `/tmp/lex<N>/` and writes outputs to the package data directory directly. They're idempotent and safe to re-run.

## Refresh procedure

Each phase directory needs the upstream files downloaded into `/tmp/lex<N>/` before running. See the script header for the exact list. Sources:

- **AWL** — `https://raw.githubusercontent.com/fildpauz/adaps/master/tools/CoxheadAWL.xml` → `/tmp/awl.xml`
- **BNC/COCA** — `https://raw.githubusercontent.com/lpmi-13/machine_readable_wordlists/master/General/BNC_COCA/BNC_COCA.json` → `/tmp/lex2/bnc_coca.json`
- **NGSL/NAWL** — `https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv` and `…/s/NAWL_12_lemmatized_for_research.csv` → `/tmp/lex2/ngsl.csv`, `nawl.csv` (NAWL is ISO-8859 — `iconv -f WINDOWS-1252 -t UTF-8`)
- **PHRASE** — `https://www.norbertschmitt.co.uk/_files/ugd/5f2482_63c555de9e3f4c09af4170ba051b3bbe.doc` → `/tmp/lex2/phrase.doc` (then `textutil -convert txt`)
- **CEFR** — `https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv` and `octanove-vocabulary-profile-c1c2-1.0.csv` → `/tmp/lex3/`
- **Metadiscourse hedges** — `https://raw.githubusercontent.com/HLTCHKUST/framing-bias-metric/main/data/lexicons/bias_related_lexicons/hedges_hyland2005.txt` → `/tmp/lex4/hedges.txt`

Run order: `build_awl.py`, then `build_phase2.py`, `build_phase3.py`, `build_phase4.py`. Verify with `uv run pytest` afterwards — failing tests usually mean a schema drift in the upstream file.
