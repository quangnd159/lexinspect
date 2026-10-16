"""Study 1: lexinspect readability against human judgement (CLEAR corpus).

One command, end to end:

    uv run --with scikit-learn --with pandas --with openpyxl --with scipy \
        python scripts/validation/study1_readability/run.py

Steps: download the CLEAR corpus (pinned commit, checksum-verified) into
`.cache/validation/clear/` if absent; run lexinspect over every excerpt (cached
in `.cache/validation/study1_features_<version>.jsonl`); correlate each formula
with the teachers' BT_easiness; fit ridge models with nested cross-validation;
write `docs/validation/study1-readability.json`.

The data is CC BY-NC-SA 4.0 (per the repository README) and is never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.request
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation"
DATA_DIR = CACHE / "clear"
OUT_JSON = ROOT / "docs" / "validation" / "study1-readability.json"

CLEAR_REPO = "https://github.com/scrosseye/CLEAR-Corpus"
CLEAR_COMMIT = "dbf1cf0df30bf6be8b0691d2c078b75043ca6199"
CLEAR_FILE = "CLEAR_corpus_final.xlsx"
CLEAR_URL = f"https://raw.githubusercontent.com/scrosseye/CLEAR-Corpus/{CLEAR_COMMIT}/{CLEAR_FILE}"
CLEAR_SHA256 = "e87a19a29c12a441e0c4f11a4e49897ff24ac7dff240ee7397283a050a902cc7"
CLEAR_LICENCE = "CC BY-NC-SA 4.0 (stated in the repository README since 2024-04-17)"

# Modules the features come from. `errors`, `metadiscourse`, `tagger` and
# `profile` are not used by any feature below, so they are skipped for speed.
MODULES = ["readability", "statistics", "diversity", "awl", "bnc_coca", "ngsl", "phrase", "cefr"]

FORMULAS = [
    "flesch_reading_ease",
    "flesch_kincaid_grade",
    "gunning_fog",
    "smog_index",
    "automated_readability_index",
    "coleman_liau_index",
    "dale_chall_readability_score",
    "linsear_write_formula",
    "text_standard",
]

# Published |r| with BT_easiness (Crossley et al. 2023, Fig. 2, as cited in
# VALIDITY.md), and the column in the CLEAR file that holds the authors' own
# score (computed with ARTE 1.1).
PUBLISHED = {
    "flesch_reading_ease": (0.55, "Flesch-Reading-Ease"),
    "flesch_kincaid_grade": (0.52, "Flesch-Kincaid-Grade-Level"),
    "automated_readability_index": (0.48, "Automated Readability Index"),
    "smog_index": (0.56, "SMOG Readability"),
    "dale_chall_readability_score": (0.56, "New Dale-Chall Readability Formula"),
}

# Pre-specified feature sets; fixed before looking at any model result.
SURFACE = ["words_per_sentence", "syllables_per_word", "characters_per_word"]
SURFACE_DC = SURFACE + ["dale_chall_difficult_pct"]
FULL = SURFACE_DC + [
    # CEFR: share of tokens at each level; A1 is the omitted reference.
    "cefr_A2_pct",
    "cefr_B1_pct",
    "cefr_B2_pct",
    "cefr_C1_pct",
    "cefr_C2_pct",
    "cefr_off_list_pct",
    # BNC/COCA word families: share of tokens beyond the first n thousand.
    "bnc_beyond_k1_pct",
    "bnc_beyond_k2_pct",
    "bnc_beyond_k3_pct",
    "bnc_beyond_k5_pct",
    "awl_pct",
    "ngsl_pct",
    "mtld",
    "mattr",
    "phrase_per_1000",
]
MODEL_SETS = {"surface_3": SURFACE, "surface_plus_dale_chall_4": SURFACE_DC, "full_19": FULL}

ALPHAS = np.logspace(-3, 4, 29)
SEEDS = [0, 1, 2, 3, 4]
FOLDS = 10


# --- data --------------------------------------------------------------------


def ensure_data() -> Path:
    path = DATA_DIR / CLEAR_FILE
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {CLEAR_URL}", file=sys.stderr)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(CLEAR_URL, tmp)
        tmp.rename(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != CLEAR_SHA256:
        sys.exit(f"Checksum mismatch for {path}: {digest}")
    return path


def load_clear() -> pd.DataFrame:
    df = pd.read_excel(ensure_data())
    df["ID"] = df["ID"].astype(int)
    return df


# --- features ----------------------------------------------------------------

_worker_ready = False


def _init_worker() -> None:
    global _worker_ready
    from lexinspect import pipeline

    pipeline.warm()
    _worker_ready = True


def flat_features(results: dict[str, Any]) -> dict[str, Any]:
    rd = results["readability"]
    f: dict[str, Any] = {f: rd["scores"][f] for f in FORMULAS}
    f.update(rd["averages"])
    words = rd["counts"]["words"]
    f["words"] = words
    f["sentences"] = rd["counts"]["sentences"]
    f["dale_chall_difficult_pct"] = 100 * rd["counts"]["difficult_words"] / words if words else None
    f["reliable"] = rd["reliability"]["reliable"]

    cefr = results["cefr"]
    for lvl in ("A1", "A2", "B1", "B2", "C1", "C2"):
        f[f"cefr_{lvl}_pct"] = cefr["per_level"][lvl]["coverage_pct"]
    content = cefr["counts"]["content_tokens"]
    f["cefr_off_list_pct"] = 100 * cefr["counts"]["off_list_tokens"] / content if content else None

    bands = results["bnc_coca"]["per_band"]
    for k in (1, 2, 3, 5):
        f[f"bnc_beyond_k{k}_pct"] = (
            100 - bands[str(k)]["cumulative_coverage_with_supplementary_pct"]
        )

    f["awl_pct"] = results["awl"]["coverage_pct"]
    f["ngsl_pct"] = results["ngsl"]["coverage_pct"]["ngsl"]
    div = results["diversity"]["scores"]
    f["mtld"] = div["mtld"]
    f["mattr"] = div["mattr"]
    f["phrase_per_1000"] = results["phrase"]["counts"]["hits_per_1000_words"]
    return f


def _extract(item: tuple[int, str]) -> dict[str, Any]:
    from lexinspect import pipeline

    ident, text = item
    try:
        _, results = pipeline.run_all(text, modules=MODULES)
        return {"ID": ident, "error": None, **flat_features(results)}
    except Exception as exc:  # recorded, not hidden
        return {"ID": ident, "error": f"{type(exc).__name__}: {exc}"}


def features(df: pd.DataFrame, workers: int) -> tuple[pd.DataFrame, dict[str, str]]:
    from lexinspect._schema import provenance

    prov = provenance()
    cache = CACHE / f"study1_features_{prov['lexinspect']}_{prov['spacy_model']}.jsonl"
    done: dict[int, dict[str, Any]] = {}
    if cache.exists():
        for line in cache.read_text("utf-8").splitlines():
            row = json.loads(line)
            done[row["ID"]] = row
    todo = [(int(i), t) for i, t in zip(df["ID"], df["Excerpt"], strict=True) if int(i) not in done]
    if todo:
        print(f"Analysing {len(todo)} excerpts with {workers} workers", file=sys.stderr)
        CACHE.mkdir(parents=True, exist_ok=True)
        with cache.open("a", encoding="utf-8") as out, Pool(workers, _init_worker) as pool:
            for n, row in enumerate(pool.imap_unordered(_extract, todo, chunksize=16), 1):
                done[row["ID"]] = row
                out.write(json.dumps(row) + "\n")
                if n % 500 == 0:
                    print(f"  {n}/{len(todo)}", file=sys.stderr)
    feats = pd.DataFrame([done[int(i)] for i in df["ID"]])
    return feats, prov


# --- statistics --------------------------------------------------------------


def fisher_ci(r: float, n: int, se_scale: float = 1.0) -> tuple[float, float]:
    z = math.atanh(r)
    se = se_scale / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def correlate(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    n = len(x)
    pr = float(stats.pearsonr(x, y)[0])
    sr = float(stats.spearmanr(x, y)[0])
    # Spearman CI uses the Bonett & Wright (2000) standard error.
    return {
        "n": n,
        "pearson": round(pr, 4),
        "pearson_ci95": [round(v, 4) for v in fisher_ci(pr, n)],
        "spearman": round(sr, 4),
        "spearman_ci95": [round(v, 4) for v in fisher_ci(sr, n, math.sqrt(1 + sr**2 / 2))],
    }


def paired_boot_diff(a: np.ndarray, b: np.ndarray, y: np.ndarray, reps: int = 2000) -> list[float]:
    """95% percentile bootstrap CI for |r(a,y)| - |r(b,y)|, resampling texts."""
    rng = np.random.default_rng(20261016)
    n = len(y)
    out = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        out[i] = abs(np.corrcoef(a[idx], y[idx])[0, 1]) - abs(np.corrcoef(b[idx], y[idx])[0, 1])
    return [round(float(v), 4) for v in np.percentile(out, [2.5, 97.5])]


def describe(s: pd.Series) -> dict[str, float]:
    d = s.describe(percentiles=[0.05, 0.5, 0.95])
    return {
        "mean": round(float(d["mean"]), 3),
        "sd": round(float(d["std"]), 3),
        "min": round(float(d["min"]), 3),
        "p5": round(float(d["5%"]), 3),
        "median": round(float(d["50%"]), 3),
        "p95": round(float(d["95%"]), 3),
        "max": round(float(d["max"]), 3),
        "skew": round(float(stats.skew(s)), 3),
    }


def vif(X: pd.DataFrame) -> dict[str, float]:
    inv = np.linalg.pinv(np.corrcoef(X.to_numpy(), rowvar=False))
    return {c: round(float(v), 2) for c, v in zip(X.columns, np.diag(inv), strict=True)}


def ridge() -> Any:
    # RidgeCV picks alpha by efficient leave-one-out *within the training data
    # it is fitted on*; inside the outer folds this is nested CV.
    return make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS))


def cv_eval(X: np.ndarray, y: np.ndarray, make_model: Any) -> dict[str, Any]:
    pooled_r, pooled_rmse, fold_r, fold_rmse, alphas = [], [], [], [], []
    for seed in SEEDS:
        pred = np.empty_like(y)
        for tr, te in KFold(FOLDS, shuffle=True, random_state=seed).split(X):
            m = make_model().fit(X[tr], y[tr])
            pred[te] = m.predict(X[te])
            fold_r.append(np.corrcoef(pred[te], y[te])[0, 1])
            fold_rmse.append(math.sqrt(np.mean((pred[te] - y[te]) ** 2)))
            last = m[-1] if hasattr(m, "__getitem__") else m
            if hasattr(last, "alpha_"):
                alphas.append(float(last.alpha_))
        pooled_r.append(np.corrcoef(pred, y)[0, 1])
        pooled_rmse.append(math.sqrt(np.mean((pred - y) ** 2)))

    def ms(v: list[float]) -> dict[str, float]:
        return {"mean": round(float(np.mean(v)), 4), "sd": round(float(np.std(v, ddof=1)), 4)}

    res = {
        "pooled_oof_r": ms(pooled_r),
        "pooled_oof_rmse": ms(pooled_rmse),
        "pooled_oof_r2": ms([r**2 for r in pooled_r]),
        "per_fold_r": ms(fold_r),
        "per_fold_rmse": ms(fold_rmse),
    }
    if alphas:
        res["alpha_selected"] = {
            "median": float(np.median(alphas)),
            "min": float(min(alphas)),
            "max": float(max(alphas)),
        }
    return res


def full_fit(X: pd.DataFrame, y: np.ndarray) -> dict[str, Any]:
    m = ridge().fit(X.to_numpy(), y)
    rc = m[-1]
    return {
        "alpha": float(rc.alpha_),
        "intercept": round(float(rc.intercept_), 4),
        "standardised_coefficients": {
            c: round(float(b), 4)
            for c, b in sorted(zip(X.columns, rc.coef_, strict=True), key=lambda t: -abs(t[1]))
        },
        "in_sample_r": round(float(np.corrcoef(m.predict(X.to_numpy()), y)[0, 1]), 4),
    }


# --- main --------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    clear = load_clear()
    feats, prov = features(clear, args.workers)
    data = clear[
        ["ID", "BT_easiness", "s.e.", "Excerpt", "Sentence Count"]
        + [c for _, c in PUBLISHED.values()]
    ].merge(feats, on="ID")
    failures = data[data["error"].notna()][["ID", "error"]].to_dict("records")
    ok = data[data["error"].isna()].copy()
    y = ok["BT_easiness"].to_numpy(float)

    missing = {c: int(ok[c].isna().sum()) for c in FORMULAS + FULL if ok[c].isna().any()}

    # 1. Formula correlations.
    formula_rows = {}
    for f in FORMULAS:
        x = ok[f].to_numpy(float)
        row = correlate(x, y)
        if f in PUBLISHED:
            pub, col = PUBLISHED[f]
            clear_x = ok[col].to_numpy(float)
            row["published_abs_r"] = pub
            row["clear_file_column"] = col
            row["clear_file_pearson"] = round(float(np.corrcoef(clear_x, y)[0, 1]), 4)
            row["r_with_clear_file_score"] = round(float(np.corrcoef(x, clear_x)[0, 1]), 4)
            row["abs_r_minus_clear_file_abs_r_ci95"] = paired_boot_diff(x, clear_x, y)
        formula_rows[f] = row

    # 2. Single-feature correlations for every model feature.
    feature_rows = {c: correlate(ok[c].to_numpy(float), y) for c in FULL}

    # 3. Models. Rows with a missing feature (e.g. MTLD on a very short text)
    #    are dropped from every model so all models see the same texts.
    mdata = ok.dropna(subset=FULL)
    my = mdata["BT_easiness"].to_numpy(float)
    models = {}
    for name, cols in MODEL_SETS.items():
        X = mdata[cols]
        models[name] = {
            "features": cols,
            "ridge_nested_cv": cv_eval(X.to_numpy(float), my, ridge),
            "ols_cv": cv_eval(X.to_numpy(float), my, LinearRegression),
            "full_fit": full_fit(X, my),
            "vif": vif(X),
        }
    # Single-formula baselines through the same CV, for a like-for-like comparison.
    for f in ("flesch_reading_ease", "dale_chall_readability_score", "text_standard"):
        X = mdata[[f]].to_numpy(float)
        models[f"single_{f}"] = {"features": [f], "ols_cv": cv_eval(X, my, LinearRegression)}

    formula_intercorr = ok[FORMULAS].corr().round(3).to_dict()

    # Agreement with the authors' own (ARTE 1.1) scores shipped in the file.
    agreement = {
        "sentence_count_vs_clear_column": {
            "pearson": round(float(ok["sentences"].corr(ok["Sentence Count"])), 4),
            "share_identical": round(float((ok["sentences"] == ok["Sentence Count"]).mean()), 4),
            "mean_lexinspect_minus_clear": round(
                float((ok["sentences"] - ok["Sentence Count"]).mean()), 3
            ),
        }
    }
    for f, (_, col) in PUBLISHED.items():
        diff = ok[f] - ok[col]
        agreement[f] = {
            "mean_lexinspect_minus_arte": round(float(diff.mean()), 3),
            "sd_of_difference": round(float(diff.std()), 3),
            "n_abs_difference_over_2": int((diff.abs() > 2).sum()),
        }

    out = {
        "study": "Study 1: readability against human judgement",
        "provenance": prov,
        "data": {
            "name": "CommonLit Ease of Readability (CLEAR) corpus",
            "source": CLEAR_REPO,
            "commit": CLEAR_COMMIT,
            "file": CLEAR_FILE,
            "url": CLEAR_URL,
            "sha256": CLEAR_SHA256,
            "licence": CLEAR_LICENCE,
            "citation": (
                "Crossley, S. A., Heintz, A., Choi, J. S., Batchelor, J., Karimi, M., & "
                "Malatinszky, A. (2023). A large-scaled corpus for assessing text readability. "
                "Behavior Research Methods, 55(2), 491-507. doi:10.3758/s13428-022-01802-x"
            ),
            "n_excerpts": int(len(clear)),
        },
        "checks": {
            "n_analysed": int(len(ok)),
            "failures": failures,
            "missing_values": missing,
            "n_used_in_models": int(len(mdata)),
            "n_unreliable_under_100_words": int((~ok["reliable"].astype(bool)).sum()),
            "words_per_excerpt": describe(ok["words"]),
            "sentences_per_excerpt": describe(ok["sentences"]),
            "bt_easiness": describe(ok["BT_easiness"]),
            "bt_standard_error": describe(ok["s.e."]),
            "formula_distributions": {f: describe(ok[f]) for f in FORMULAS},
            "formula_intercorrelations": formula_intercorr,
            "agreement_with_clear_file_scores": agreement,
        },
        "formula_correlations": formula_rows,
        "feature_correlations": feature_rows,
        "models": models,
        "cv": {"folds": FOLDS, "seeds": SEEDS, "alphas": [float(a) for a in ALPHAS]},
        "baselines": {
            "clear_paper_28_feature_model_r": 0.712,
            "gpt4_turbo_zero_shot_r": 0.76,
            "bt_split_half_r": 0.63,
            "bt_full_vs_half_r": 0.85,
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", "utf-8")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}", file=sys.stderr)

    # Console summary.
    print(f"lexinspect {prov['lexinspect']} / {prov['spacy_model']}; N = {len(ok)} analysed")
    for f, r in formula_rows.items():
        extra = ""
        if "published_abs_r" in r:
            extra = (
                f"  published {r['published_abs_r']:.2f}  CLEAR-file {r['clear_file_pearson']:+.3f}"
                f"  r(lex,file) {r['r_with_clear_file_score']:.3f}"
            )
        print(f"{f:32s} r {r['pearson']:+.3f}  rho {r['spearman']:+.3f}{extra}")
    for name, m in models.items():
        key = "ridge_nested_cv" if "ridge_nested_cv" in m else "ols_cv"
        cv = m[key]
        print(
            f"{name:40s} {key:16s} r {cv['pooled_oof_r']['mean']:.3f}±{cv['pooled_oof_r']['sd']:.3f}"
            f"  RMSE {cv['pooled_oof_rmse']['mean']:.3f}"
        )


if __name__ == "__main__":
    main()
