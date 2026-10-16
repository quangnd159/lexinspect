"""Study 3, step 2: agreement between lexinspect and reference implementations.

Reads the texts assembled by `fetch_texts.py` and, for every text, computes:

- Readability: lexinspect's eight formulas and their inputs (words, sentences,
  syllables, polysyllables, difficult words) against textstat, each tool
  reading the raw text its own way. Each textstat score is also recomputed
  from lexinspect's own counts with textstat's coefficients and word
  definitions, which splits every difference into a counting part
  (tokenisation, sentence splitting, syllables) and a formula part.
- Syllables, word by word: lexinspect's counter against textstat's on the same
  word types, so syllable counting is isolated from tokenisation.
- Lexical diversity, same tokens: lexinspect's token list fed unchanged to
  TAALED, lexical-diversity and lexicalrichness (isolates the formulas).
- Lexical diversity, own tokens: each tool on the raw text with its own
  documented preprocessing (TAALED via pylats, lexical-diversity's
  `flemmatize`, lexicalrichness's default tokenizer).
- vocd-D on the Text Inspector comparison passage.

Writes per-text numbers to `docs/validation/study3-agreement-per-text.csv`
and the summary to `docs/validation/study3-agreement.json`. Run with
`python -I` (the texts are downloaded data).
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import platform
import sys
import warnings
from collections import Counter
from importlib.metadata import version
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation" / "study3"
DOCS = ROOT / "docs" / "validation"
PASSAGE = ROOT / "reports" / "text-inspector-comparison" / "passage.txt"

import pandas as pd
import spacy
import textstat
from scipy import stats

with contextlib.redirect_stdout(io.StringIO()):
    from lexical_diversity import lex_div
    from lexicalrichness import LexicalRichness
    from pylats import lats
    from taaled import ld as taaled

from lexinspect import _syllables, diversity, readability
from lexinspect._schema import provenance
from lexinspect._text import analyse

textstat.set_lang("en_US")
textstat.set_rounding_points(None)

COMPATIBLE_R = 0.95  # working convention for "compatible", not a standard


class PylatsParams(lats.EnDefault):
    """pylats' English defaults with the same spaCy model lexinspect uses."""

    model = "en_core_web_sm"
    nlp = spacy.load("en_core_web_sm")
    mwuDict = None


# --- textstat internals used for the decomposition ----------------------------

from textstat.backend.counts import (
    count_difficult_words as ts_count_difficult_words,
)
from textstat.backend.counts import (
    count_letters as ts_count_letters,
)
from textstat.backend.selections._list_words import list_words as ts_list_words
from textstat.backend.utils._get_lang_easy_words import get_lang_easy_words

TS_EASY = get_lang_easy_words("en_US")


def ts_syllables_word(w: str) -> int:
    return textstat.syllable_count(w)


# --- per-text computation -----------------------------------------------------


def lexinspect_row(text: str) -> tuple[dict, list[str], object]:
    a = analyse(text)
    r = readability.analyze(text, analysis=a)
    c = r["counts"]
    s = r["scores"]
    words = a.words
    syll = [readability.word_syllables(w) for w in words]
    letters = sum(readability._letters(w) for w in words)
    # textstat's definitions applied to lexinspect's words and syllables:
    # Fog "complex" = 3+ syllables and not on the easy-word list; Dale–Chall
    # "difficult" = not on the easy-word list (no lemma, name or numeral rules).
    ts_fog_hard = sum(
        1 for w, n in zip(words, syll, strict=False) if n >= 3 and w.lower not in TS_EASY
    )
    ts_dc_hard = sum(1 for w in words if w.lower not in TS_EASY)
    fog_hard = sum(
        1 for w, n in zip(words, syll, strict=False) if readability._is_fog_complex(w, n)
    )
    row = {
        "li_words": c["words"],
        "li_sentences": c["sentences"],
        "li_syllables": c["syllables"],
        "li_polysyllables": c["polysyllable_words"],
        "li_difficult_words": c["difficult_words"],
        "li_letters": letters,
        "li_syllables_no_digits": sum(
            n for w, n in zip(words, syll, strict=False) if not any(c.isdigit() for c in w.text)
        ),
        "li_fog_complex": fog_hard,
        "li_ts_def_fog_complex": ts_fog_hard,
        "li_ts_def_dc_difficult": ts_dc_hard,
    }
    for k, v in s.items():
        row[f"li_{k}"] = v
    toks = diversity.tokens(a)
    return row, toks, a


def textstat_row(text: str) -> dict:
    return {
        "ts_words": textstat.lexicon_count(text, removepunct=True),
        "ts_sentences": textstat.sentence_count(text),
        "ts_syllables": textstat.syllable_count(text),
        "ts_polysyllables": textstat.polysyllabcount(text),
        # What textstat's Dale–Chall formula counts (threshold 0: every word off
        # the easy list). Its public `difficult_words()` defaults to 2+ syllables.
        "ts_difficult_words": ts_count_difficult_words(text, "en_US", 0),
        "ts_syllables_no_digits": sum(
            textstat.syllable_count(w)
            for w in ts_list_words(text)
            if not any(c.isdigit() for c in w)
        ),
        "ts_letters": ts_count_letters(text),
        "ts_flesch_reading_ease": textstat.flesch_reading_ease(text),
        "ts_flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
        "ts_gunning_fog": textstat.gunning_fog(text),
        "ts_smog_index": textstat.smog_index(text),
        "ts_automated_readability_index": textstat.automated_readability_index(text),
        "ts_coleman_liau_index": textstat.coleman_liau_index(text),
        "ts_dale_chall_readability_score": textstat.dale_chall_readability_score(text),
        "ts_linsear_write_formula": textstat.linsear_write_formula(text),
        "ts_text_standard": textstat.text_standard(text, float_output=True),
    }


def textstat_formulas_on_lexinspect_counts(r: dict) -> dict:
    """textstat's formulas (coefficients and hard-word definitions) on lexinspect's counts."""
    W, S, Y = r["li_words"], r["li_sentences"], r["li_syllables"]
    L, P = r["li_letters"], r["li_polysyllables"]
    asl, asw = W / S, Y / W
    pdw = 100 * r["li_ts_def_dc_difficult"] / W
    return {
        "x_flesch_reading_ease": 206.835 - 1.015 * asl - 84.6 * asw,
        "x_flesch_kincaid_grade": 0.39 * asl + 11.8 * asw - 15.59,
        "x_gunning_fog": 0.4 * (asl + 100 * r["li_ts_def_fog_complex"] / W),
        "x_smog_index": 1.043 * math.sqrt(30 * P / S) + 3.1291,
        "x_automated_readability_index": 4.71 * L / W + 0.5 * asl - 21.43,
        "x_coleman_liau_index": 0.058 * 100 * L / W - 0.296 * 100 * S / W - 15.8,
        "x_dale_chall_readability_score": 0.1579 * pdw + 0.0496 * asl + (3.6365 if pdw > 5 else 0),
    }


def li_diversity(toks: list[str]) -> dict:
    n = len(toks)
    out = {"li_div_tokens": n, "li_div_types": len(set(toks))}
    out["li_ttr"] = diversity.ttr(toks)
    out["li_maas"] = diversity.maas(toks)
    out["li_msttr"] = diversity.msttr(toks) if n >= 50 else None
    out["li_mattr"] = diversity.mattr(toks) if n >= 50 else None
    out["li_mtld"] = diversity.mtld(toks) if n >= 50 else None
    out["li_hdd"] = diversity.hdd(toks) if n >= 42 else None
    out["li_vocd_d"] = diversity.vocd_d(toks) if n > 50 else None
    return out


def taaled_values(toks: list[str], prefix: str) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        v = taaled.lexdiv(list(toks)).vald
    return {
        f"{prefix}_tokens": v["ntokens"],
        f"{prefix}_ttr": v["ttr"],
        f"{prefix}_maas": v["maas"],
        f"{prefix}_msttr": v["msttr"],
        f"{prefix}_mattr": v["mattr"],
        f"{prefix}_mtld_original": v["mtldo"],
        f"{prefix}_mtld_mfl": v["mtld"],
        f"{prefix}_hdd": v["hdd"],
    }


def lexdiv_values(toks: list[str], prefix: str) -> dict:
    return {
        f"{prefix}_tokens": len(toks),
        f"{prefix}_mattr": lex_div.mattr(toks),
        f"{prefix}_msttr": lex_div.msttr(toks),
        f"{prefix}_mtld": lex_div.mtld(toks),
        f"{prefix}_hdd": lex_div.hdd(toks),
    }


def lexrich_values(lr: LexicalRichness, prefix: str) -> dict:
    out = {f"{prefix}_tokens": lr.words, f"{prefix}_ttr": lr.ttr}
    n = lr.words
    out[f"{prefix}_mattr"] = lr.mattr(window_size=50) if n >= 50 else None
    out[f"{prefix}_mtld"] = lr.mtld(threshold=0.72)
    out[f"{prefix}_hdd"] = lr.hdd(draws=42) if n >= 42 else None
    try:
        out[f"{prefix}_vocd_d"] = float(
            lr.vocd(ntokens=50, within_sample=100, iterations=3, seed=42)
        )
    except Exception:  # noqa: BLE001  (curve_fit failure or too short)
        out[f"{prefix}_vocd_d"] = None
    return out


def pylats_tokens(text: str) -> list[str]:
    with contextlib.redirect_stdout(io.StringIO()):
        return lats.Normalize(lats.preProcess(text, PylatsParams), PylatsParams).toks


# --- statistics -----------------------------------------------------------------


def agreement(x, y, tol: float, rel: bool) -> dict:
    """x = lexinspect, y = reference. Bias and differences are x - y."""
    d = pd.DataFrame({"x": x, "y": y}).dropna().astype(float)
    n = len(d)
    if n < 3:
        return {"n": n}
    diff = d.x - d.y
    within = (diff.abs() <= tol * d.y.abs()).mean() if rel else (diff.abs() <= tol + 1e-09).mean()
    exact = (diff.abs() < 1e-9).mean()
    if d.x.std() == 0 or d.y.std() == 0:
        r = rho = float("nan")
    else:
        r = stats.pearsonr(d.x, d.y).statistic
        rho = stats.spearmanr(d.x, d.y).statistic
    return {
        "n": n,
        "pearson_r": round(float(r), 4),
        "spearman_rho": round(float(rho), 4),
        "mean_lexinspect": round(float(d.x.mean()), 4),
        "mean_reference": round(float(d.y.mean()), 4),
        "bias": round(float(diff.mean()), 4),
        "mean_abs_diff": round(float(diff.abs().mean()), 4),
        "max_abs_diff": round(float(diff.abs().max()), 4),
        "tolerance": f"±{tol:g}" + (" (relative)" if rel else ""),
        "pct_within_tolerance": round(100 * float(within), 1),
        "pct_identical": round(100 * float(exact), 1),
        "compatible_r_gt_0_95": bool(r > COMPATIBLE_R) if not math.isnan(r) else None,
    }


def top_disagreements(df: pd.DataFrame, x: str, y: str, k: int = 5) -> list[dict]:
    d = df[["id", "source", x, y]].dropna().copy()
    d["diff"] = d[x] - d[y]
    d = d.reindex(d["diff"].abs().sort_values(ascending=False).index).head(k)
    return [
        {
            "id": r.id,
            "source": r.source,
            "lexinspect": round(float(r[x]), 4),
            "reference": round(float(r[y]), 4),
            "diff": round(float(r["diff"]), 4),
        }
        for _, r in d.iterrows()
    ]


# --- comparisons ------------------------------------------------------------------

# (label, lexinspect column, reference column, tolerance, relative?)
READABILITY = [
    ("Words", "li_words", "ts_words", 0.02, True),
    ("Sentences", "li_sentences", "ts_sentences", 0.10, True),
    ("Syllables", "li_syllables", "ts_syllables", 0.02, True),
    (
        "Syllables in words without digits",
        "li_syllables_no_digits",
        "ts_syllables_no_digits",
        0.02,
        True,
    ),
    ("Polysyllabic words (3+)", "li_polysyllables", "ts_polysyllables", 0.05, True),
    ("Dale–Chall difficult words", "li_difficult_words", "ts_difficult_words", 0.05, True),
    ("Flesch Reading Ease", "li_flesch_reading_ease", "ts_flesch_reading_ease", 5.0, False),
    ("Flesch–Kincaid grade", "li_flesch_kincaid_grade", "ts_flesch_kincaid_grade", 0.5, False),
    ("Gunning Fog", "li_gunning_fog", "ts_gunning_fog", 0.5, False),
    ("SMOG", "li_smog_index", "ts_smog_index", 0.5, False),
    ("ARI", "li_automated_readability_index", "ts_automated_readability_index", 0.5, False),
    ("Coleman–Liau", "li_coleman_liau_index", "ts_coleman_liau_index", 0.5, False),
    (
        "Dale–Chall raw score",
        "li_dale_chall_readability_score",
        "ts_dale_chall_readability_score",
        0.5,
        False,
    ),
    ("Linsear Write", "li_linsear_write_formula", "ts_linsear_write_formula", 0.5, False),
    ("text_standard (different definitions)", "li_text_standard", "ts_text_standard", 1.0, False),
]

FORMULA_ONLY = [
    ("Flesch Reading Ease", "li_flesch_reading_ease", "x_flesch_reading_ease", 0.01, False),
    ("Flesch–Kincaid grade", "li_flesch_kincaid_grade", "x_flesch_kincaid_grade", 0.01, False),
    ("Gunning Fog", "li_gunning_fog", "x_gunning_fog", 0.01, False),
    ("SMOG", "li_smog_index", "x_smog_index", 0.01, False),
    ("ARI", "li_automated_readability_index", "x_automated_readability_index", 0.01, False),
    ("Coleman–Liau", "li_coleman_liau_index", "x_coleman_liau_index", 0.01, False),
    (
        "Dale–Chall raw score",
        "li_dale_chall_readability_score",
        "x_dale_chall_readability_score",
        0.01,
        False,
    ),
]

DIV_SAME = [
    ("MATTR (50) vs TAALED", "li_mattr", "taaled_same_mattr", 0.01, False),
    ("MATTR (50) vs lexical-diversity", "li_mattr", "lexdiv_same_mattr", 0.01, False),
    ("MATTR (50) vs lexicalrichness", "li_mattr", "lexrich_same_mattr", 0.01, False),
    ("MTLD vs TAALED (original, mtldo)", "li_mtld", "taaled_same_mtld_original", 0.05, True),
    ("MTLD vs TAALED (default, mean factor length)", "li_mtld", "taaled_same_mtld_mfl", 0.05, True),
    ("MTLD vs lexical-diversity", "li_mtld", "lexdiv_same_mtld", 0.05, True),
    ("MTLD vs lexicalrichness", "li_mtld", "lexrich_same_mtld", 0.05, True),
    ("HD-D vs TAALED", "li_hdd", "taaled_same_hdd", 0.01, False),
    ("HD-D vs lexical-diversity", "li_hdd", "lexdiv_same_hdd", 0.01, False),
    ("HD-D vs lexicalrichness", "li_hdd", "lexrich_same_hdd", 0.01, False),
    ("vocd-D vs lexicalrichness", "li_vocd_d", "lexrich_same_vocd_d", 0.05, True),
    ("MSTTR (50) vs TAALED", "li_msttr", "taaled_same_msttr", 0.01, False),
    ("TTR vs TAALED", "li_ttr", "taaled_same_ttr", 0.01, False),
    ("Maas a² vs TAALED (log10)", "li_maas", "taaled_same_maas", 0.01, False),
]

DIV_OWN = [
    ("Tokens vs TAALED/pylats", "li_div_tokens", "taaled_own_tokens", 0.05, True),
    ("Tokens vs lexical-diversity", "li_div_tokens", "lexdiv_own_tokens", 0.05, True),
    ("Tokens vs lexicalrichness", "li_div_tokens", "lexrich_own_tokens", 0.05, True),
    ("MATTR (50) vs TAALED/pylats", "li_mattr", "taaled_own_mattr", 0.01, False),
    ("MATTR (50) vs lexical-diversity", "li_mattr", "lexdiv_own_mattr", 0.01, False),
    ("MATTR (50) vs lexicalrichness", "li_mattr", "lexrich_own_mattr", 0.01, False),
    ("MTLD vs TAALED/pylats (original, mtldo)", "li_mtld", "taaled_own_mtld_original", 0.05, True),
    ("MTLD vs TAALED/pylats (default)", "li_mtld", "taaled_own_mtld_mfl", 0.05, True),
    ("MTLD vs lexical-diversity", "li_mtld", "lexdiv_own_mtld", 0.05, True),
    ("MTLD vs lexicalrichness", "li_mtld", "lexrich_own_mtld", 0.05, True),
    ("HD-D vs TAALED/pylats", "li_hdd", "taaled_own_hdd", 0.01, False),
    ("HD-D vs lexical-diversity", "li_hdd", "lexdiv_own_hdd", 0.01, False),
    ("HD-D vs lexicalrichness", "li_hdd", "lexrich_own_hdd", 0.01, False),
    ("vocd-D vs lexicalrichness", "li_vocd_d", "lexrich_own_vocd_d", 0.05, True),
]


def syllable_agreement(words: Counter) -> dict:
    """lexinspect vs textstat syllables on the same word types (single alphabetic words)."""
    rows = []
    for w, freq in words.items():
        li = _syllables.count(w)
        ts = ts_syllables_word(w)
        rows.append((w, freq, li, ts, _syllables.source(w)))
    d = pd.DataFrame(rows, columns=["word", "freq", "li", "ts", "li_source"])
    d["exact"] = d.li == d.ts
    d["within1"] = (d.li - d.ts).abs() <= 1
    cmu = _syllables.cmudict()
    d["in_cmudict"] = d.word.isin(cmu.keys())

    def summ(sub):
        tok = sub.freq.sum()
        return {
            "types": int(len(sub)),
            "tokens": int(tok),
            "pct_types_exact": round(100 * float(sub.exact.mean()), 2) if len(sub) else None,
            "pct_tokens_exact": round(100 * float((sub.exact * sub.freq).sum() / tok), 2)
            if tok
            else None,
            "pct_types_within_1": round(100 * float(sub.within1.mean()), 2) if len(sub) else None,
            "mean_diff_types": round(float((sub.li - sub.ts).mean()), 4) if len(sub) else None,
        }

    out = {
        "all": summ(d),
        "in_cmudict": summ(d[d.in_cmudict]),
        "not_in_cmudict": summ(d[~d.in_cmudict]),
    }
    out["by_lexinspect_source"] = {s: summ(g) for s, g in d.groupby("li_source")}
    miss = d[~d.exact].sort_values("freq", ascending=False).head(25)
    out["most_frequent_mismatches"] = [
        {
            "word": r.word,
            "freq": int(r.freq),
            "lexinspect": int(r.li),
            "textstat": int(r.ts),
            "lexinspect_source": r.li_source,
        }
        for r in miss.itertuples()
    ]
    return out


def vocd_passage() -> dict:
    text = PASSAGE.read_text("utf-8").strip()
    toks = diversity.tokens(analyse(text))
    li = diversity.vocd_d(toks)
    lr = float(LexicalRichness(toks, preprocessor=None, tokenizer=None).vocd(seed=42))
    # The fitted curve's error at D = 200 vs at lexinspect's optimum, on the
    # same sampled points (first trial), to show 200 is not a near-flat optimum.
    import random

    rng = random.Random(diversity.VOCD_SEED)
    pts = []
    for size in range(diversity.VOCD_MIN_N, diversity.VOCD_MAX_N + 1):
        m = sum(len(set(rng.sample(toks, size))) / size for _ in range(diversity.VOCD_SAMPLES))
        pts.append((size, m / diversity.VOCD_SAMPLES))
    d1 = diversity._fit_d(pts)

    def sse(d):
        return sum((y - diversity._ttr_model(x, d)) ** 2 for x, y in pts)

    per_seed = []
    for seed in range(1, 21):
        per_seed.append(diversity.vocd_d(toks, seed=seed))
    return {
        "passage": str(PASSAGE.relative_to(ROOT)),
        "tokens": len(toks),
        "types": len(set(toks)),
        "lexinspect_vocd_d": round(li, 2),
        "lexicalrichness_vocd_d_same_tokens": round(lr, 2),
        "text_inspector_reported": 200.0,
        "trial1_fitted_d": round(d1, 2),
        "trial1_sse_at_fit": sse(d1),
        "trial1_sse_at_200": sse(200.0),
        "trial1_sse_ratio_200_vs_fit": round(sse(200.0) / sse(d1), 2),
        "lexinspect_vocd_d_seeds_1_20": {
            "min": round(min(per_seed), 2),
            "max": round(max(per_seed), 2),
            "mean": round(sum(per_seed) / len(per_seed), 2),
        },
    }


def main() -> None:
    manifest = [
        json.loads(line) for line in (CACHE / "manifest.jsonl").read_text("utf-8").splitlines()
    ]
    if "--limit" in sys.argv:  # smoke test: first N texts, nothing written
        manifest = manifest[: int(sys.argv[sys.argv.index("--limit") + 1])]
    rows = []
    word_types: Counter = Counter()
    for i, m in enumerate(manifest, 1):
        text = (CACHE / "texts" / f"{m['id']}.txt").read_text("utf-8")
        row = {"id": m["id"], "source": m["source"], "genre": m["genre"]}
        li, toks, a = lexinspect_row(text)
        row |= li
        row |= textstat_row(text)
        row |= textstat_formulas_on_lexinspect_counts(li)
        row |= li_diversity(toks)
        row |= taaled_values(toks, "taaled_same")
        row |= lexdiv_values(toks, "lexdiv_same")
        row |= lexrich_values(
            LexicalRichness(list(toks), preprocessor=None, tokenizer=None), "lexrich_same"
        )
        row |= taaled_values(pylats_tokens(text), "taaled_own")
        row |= lexdiv_values(lex_div.flemmatize(text), "lexdiv_own")
        row |= lexrich_values(LexicalRichness(text), "lexrich_own")
        for w in a.words:
            low = w.lower
            if low.isalpha():
                word_types[low] += 1
        rows.append(row)
        if i % 25 == 0:
            print(f"  {i}/{len(manifest)}", file=sys.stderr)
    df = pd.DataFrame(rows)
    if "--limit" in sys.argv:
        print(df.T.to_string())
        return
    DOCS.mkdir(parents=True, exist_ok=True)
    df.round(6).to_csv(DOCS / "study3-agreement-per-text.csv", index=False)

    def block(spec):
        out = {}
        for label, x, y, tol, rel in spec:
            out[label] = agreement(df[x], df[y], tol, rel) | {
                "lexinspect_column": x,
                "reference_column": y,
                "top5": top_disagreements(df, x, y),
            }
        return out

    by_source = {}
    for src, g in df.groupby("source"):
        by_source[src] = {
            label: {
                k: v
                for k, v in agreement(g[x], g[y], tol, rel).items()
                if k in ("n", "pearson_r", "bias", "mean_abs_diff", "pct_within_tolerance")
            }
            for label, x, y, tol, rel in READABILITY[:10]
            + DIV_SAME[:1]
            + DIV_SAME[3:4]
            + DIV_SAME[7:8]
            + DIV_OWN[3:4]
            + DIV_OWN[6:7]
        }

    corpus = Counter(m["source"] for m in manifest)
    lengths = df["li_words"].describe().round(1).to_dict()
    result = {
        "study": "Study 3: computational agreement with reference tools",
        "provenance": provenance(),
        "environment": {
            "python": platform.python_version(),
            "textstat": version("textstat"),
            "taaled": version("taaled"),
            "pylats": version("pylats"),
            "lexical-diversity": version("lexical-diversity"),
            "lexicalrichness": version("lexicalrichness"),
            "spacy": version("spacy"),
            "en_core_web_sm": version("en_core_web_sm"),
            "pandas": version("pandas"),
            "scipy": version("scipy"),
            "nltk": version("nltk"),
            "pyphen": version("pyphen"),
        },
        "texts": {
            "n": len(manifest),
            "by_source": dict(corpus),
            "lexinspect_words": lengths,
            "manifest_sha256": {m["id"]: m["sha256"] for m in manifest},
        },
        "conventions": {
            "difference": "lexinspect minus reference",
            "compatible": f"Pearson r > {COMPATIBLE_R} (a working convention for this study, not a published standard)",
        },
        "readability_own_counts": block(READABILITY),
        "readability_formula_only": block(FORMULA_ONLY),
        "syllables_same_words": syllable_agreement(word_types),
        "diversity_same_tokens": block(DIV_SAME),
        "diversity_own_tokens": block(DIV_OWN),
        "by_source": by_source,
        "vocd_text_inspector_passage": vocd_passage(),
    }
    (DOCS / "study3-agreement.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    print_tables(result)


def print_tables(res: dict) -> None:
    for key in (
        "readability_own_counts",
        "readability_formula_only",
        "diversity_same_tokens",
        "diversity_own_tokens",
    ):
        print(f"\n### {key}\n")
        print("| Measure | n | r | rho | bias | MAD | tolerance | % within | % identical |")
        print("|---|---:|---:|---:|---:|---:|---|---:|---:|")
        for label, a in res[key].items():
            if "pearson_r" not in a:
                continue
            print(
                f"| {label} | {a['n']} | {a['pearson_r']:.3f} | {a['spearman_rho']:.3f} | {a['bias']:+.3f} | "
                f"{a['mean_abs_diff']:.3f} | {a['tolerance']} | {a['pct_within_tolerance']:.1f} | {a['pct_identical']:.1f} |"
            )
    print("\n### syllables\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in res["syllables_same_words"].items()
                if k != "most_frequent_mismatches"
            },
            indent=1,
        )
    )
    print("\n### vocd passage\n")
    print(json.dumps(res["vocd_text_inspector_passage"], indent=1))


if __name__ == "__main__":
    main()
