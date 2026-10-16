"""Study 5: how accurate are lexinspect's CEFR level estimates?

One command, end to end:

    uv run --extra cefr-level --with scikit-learn --with pandas --with scipy \
        python scripts/validation/study5_cefr/run.py

Steps:

1. Download the open English CEFR-labelled datasets into
   `.cache/validation/study5/raw/` if absent (pinned revisions, SHA-256
   checked). Nothing is committed; most are CC BY-NC(-SA).
2. Run lexinspect over every text (cached in
   `.cache/validation/study5/features_<version>.jsonl`).
3. Run the optional `cefr_level` classifier as shipped (cached in
   `.cache/validation/study5/classifier_<revision>.jsonl`).
4. Evaluate three estimators against the gold levels:
   (a) `cefr.estimated_level_95th` as shipped;
   (b) `cefr_level` (UniversalCEFR ModernBERT) as shipped;
   (c) an ordinal logistic regression on lexinspect's own features,
       cross-validated within each dataset, and trained once on reading texts
       then applied unchanged to every other dataset (transfer).
5. Write `docs/validation/study5-cefr.json`, and markdown tables to
   `.cache/validation/study5/tables.md` for the write-up.

Flags: `--skip-classifier` (no torch needed), `--limit N` (smoke test),
`--workers N`.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import math
import sys
import urllib.request
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation" / "study5"
RAW = CACHE / "raw"
OUT_JSON = ROOT / "docs" / "validation" / "study5-cefr.json"
TABLES_MD = CACHE / "tables.md"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_NUM = {lv: i + 1 for i, lv in enumerate(LEVELS)}
SEED = 0
N_FOLDS = 5

CLASSIFIER_ID = "UniversalCEFR/ModernBERT-base-cefr-all-classifier"
# The revision evaluated. `cefr_level` itself loads the latest revision; the
# script records whichever revision the Hugging Face cache resolved to.
CLASSIFIER_REVISION_EXPECTED = "87f23fd44a4775a54b1648b39531593bfc4323c8"

# --- datasets -----------------------------------------------------------------

HF = "https://huggingface.co/datasets/UniversalCEFR/{repo}/resolve/{rev}/{file}"

DATASETS: dict[str, dict[str, Any]] = {
    "ace_cefr": {
        "url": "https://arxiv.org/src/2506.14046v1/anc/ace_cefr_labeled.csv",
        "file": "ace_cefr_labeled.csv",
        "sha256": "3879a86934e24a8e1f56923f8539f382aca1ab329db2851d69ea63c5b30110cf",
        "licence": "CC0 1.0 (arXiv licence for 2506.14046 and its ancillary file)",
        "source": "Kogan et al. 2025, Ace-CEFR, arXiv:2506.14046 (ancillary file ace_cefr_labeled.csv, v1)",
        "text_type": "conversational passages (mixed sources: written for the task, LLM-generated, learner chats, web)",
        "construct": "conversational",
        "in_universalcefr": False,
    },
    "cambridge_exams": {
        "repo": "cambridge_exams_en",
        "rev": "27cb64a28f823e56638a5b029f3716e438311168",
        "file": "cambridge_exams.json",
        "sha256": "e762c547dbf513a05c551a03479a9f521fedab41e50267638c3259b4d9b862c5",
        "licence": "CC BY-NC-SA 4.0",
        "source": "Xia, Kochmar & Briscoe 2016 (Cambridge English exam reading passages), via UniversalCEFR",
        "text_type": "reading texts written for a level (Cambridge exam passages, KET-CPE)",
        "construct": "reading",
        "in_universalcefr": True,
    },
    "elg_cefr_en": {
        "repo": "elg_cefr_en",
        "rev": "5bcca039738fa3e611847964741234b73405718d",
        "file": "elg-cefr-en.json",
        "sha256": "5f748ae566c6470389681dbb1f3959dcf990b08a718e7bc81a176ed95eee2b98",
        "licence": "CC BY-NC 4.0 (dataset card; records say CC BY-NC-SA 4.0)",
        "source": "Breuker 2023, ELG CEFR Labelling (EDIA), via UniversalCEFR",
        "text_type": "reading texts written or graded for a level",
        "construct": "reading",
        "in_universalcefr": True,
    },
    "cefr_sp": {
        "repo": "cefr_sp_en",
        "rev": "b78901348bda9f5a823cd3da1f3fcb2dcc6c5725",
        "file": "cefr-sp.json",
        "sha256": "0456ee315659418fa39c48883b05972eebcefcc0a00b4e8cadb06f0ac02df25c",
        "licence": "CC BY-NC-SA 4.0",
        "source": "Arase, Uchida & Kajiwara 2022, CEFR-SP, via UniversalCEFR",
        "text_type": "single sentences (from simplification corpora) rated by English teachers",
        "construct": "sentence",
        "in_universalcefr": True,
    },
    "readme_en": {
        "repo": "readme_en",
        "rev": "88ce5b3736bdb666b1f64f738451676b12028a33",
        "file": "readme_en.json",
        "sha256": "6c5cb5608b5379115c911a5dfbbbc458556b03014287863088885e918185af89",
        "licence": "CC BY-NC-SA 4.0",
        "source": "Naous et al. 2024, ReadMe++ (English), via UniversalCEFR",
        "text_type": "single sentences from 112 domains rated for readability on the CEFR scale",
        "construct": "sentence",
        "in_universalcefr": True,
    },
    "icle500": {
        "repo": "icle500_en",
        "rev": "4230a70c3075c2f9cbde55420d8d29cedb875f89",
        "file": "icle500.json",
        "sha256": "7bb84c634a8f95b1bbf2ea30c8ad6de240328276e96fe0d12ac5eef53e9a3fa7",
        "licence": "CC BY-NC 4.0 (dataset card; records say CC0 1.0)",
        "source": "ICLE v3 essays rated by Thwaites, Vandeweerd & Paquot 2024, via UniversalCEFR",
        "text_type": "learner writing graded at a level (argumentative essays by university EFL learners)",
        "construct": "learner",
        "in_universalcefr": True,
    },
    "cefr_asag": {
        "repo": "cefr_asag_en",
        "rev": "5a64cc2fd5e3dce90a794a94ab9a5d9bd18ab684",
        "file": "cefr_asag.json",
        "sha256": "42a328a8cdeb478503f63bbff7f58f1aa05073a74819e8fa1a88ba736e40717f",
        "licence": "CC BY-NC-SA 4.0",
        "source": "Tack et al. 2017, CEFR-ASAG short answers, via UniversalCEFR",
        "text_type": "learner writing graded at a level (short answers by EFL learners)",
        "construct": "learner",
        "in_universalcefr": True,
    },
}

ORDER = [
    "ace_cefr",
    "cambridge_exams",
    "elg_cefr_en",
    "icle500",
    "cefr_asag",
    "cefr_sp",
    "readme_en",
]
TRANSFER_TRAIN = ["cambridge_exams", "elg_cefr_en"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch() -> None:
    for name, d in DATASETS.items():
        dest = RAW / name / d["file"]
        if not dest.exists():
            url = d.get("url") or HF.format(repo=d["repo"], rev=d["rev"], file=d["file"])
            print(f"downloading {name} from {url}", file=sys.stderr)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(dest)
        got = _sha256(dest)
        if got != d["sha256"]:
            sys.exit(f"{dest}: SHA-256 {got} does not match pinned {d['sha256']}")


def _ace_level(x: str) -> int | None:
    """Ace-CEFR scores are 1-6 with half steps (2.5 = A2+) and rater averages.
    Map to the nearest level, rounding .5 down so `+` levels stay in their band
    (the paper groups A2/A2+, B1/B1+, B2/B2+)."""
    if x is None or not str(x).strip():
        return None
    v = float(x)
    return int(min(6, max(1, math.ceil(v - 0.5))))


def load() -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    with (RAW / "ace_cefr" / DATASETS["ace_cefr"]["file"]).open(newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            recs.append(
                {
                    "dataset": "ace_cefr",
                    "idx": i,
                    "text": row["text"],
                    "level": _ace_level(row["label"]),
                    "raw_label": row["label"],
                    "split": row["train or test"],
                    "rater1": _ace_level(row["rater 1 label"]),
                    "rater2": _ace_level(row["rater 2 label"]),
                }
            )
    for name in ORDER[1:]:
        d = DATASETS[name]
        data = json.loads((RAW / name / d["file"]).read_text(encoding="utf-8"))
        for i, row in enumerate(data):
            lab = str(row["cefr_level"]).strip()
            base = lab.rstrip("+")
            if base not in LEVEL_NUM:  # ICLE has 7 'NA' rows
                continue
            recs.append(
                {
                    "dataset": name,
                    "idx": i,
                    "text": row["text"],
                    "level": LEVEL_NUM[base],
                    "raw_label": lab,
                }
            )
    # ELG-CEFR-EN re-indexes almost every Cambridge passage (same level, minor
    # whitespace and punctuation differences). Evaluate ELG only on the texts
    # that are not Cambridge passages, so the two datasets are independent.
    cam = {_norm_prefix(r["text"]): r["level"] for r in recs if r["dataset"] == "cambridge_exams"}
    global ELG_OVERLAP
    dup = [
        (cam[_norm_prefix(r["text"])], r["level"])
        for r in recs
        if r["dataset"] == "elg_cefr_en" and _norm_prefix(r["text"]) in cam
    ]
    ELG_OVERLAP = {"removed": len(dup), "same_level": sum(a == b for a, b in dup)}
    return [
        r for r in recs if not (r["dataset"] == "elg_cefr_en" and _norm_prefix(r["text"]) in cam)
    ]


ELG_OVERLAP: dict[str, int] = {}


def _norm_prefix(text: str) -> str:
    import re

    return re.sub(r"\W+", " ", text).strip().lower()[:200]


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# --- lexinspect features ---------------------------------------------------------


def _features_one(text: str) -> dict[str, Any]:
    from lexinspect import awl, bnc_coca, cefr, diversity, ngsl, readability, statistics
    from lexinspect._text import analyse

    a = analyse(text)
    c = cefr.analyze(text, analysis=a)
    # lexinspect 0.3.0's readability raises ValueError on a numeral with two
    # or more dots ("section 3.1.2"). For those texts take the averages from
    # `statistics` (same tokenisation), leave characters_per_word to the
    # imputer, and flag the text so the failures are counted.
    try:
        r = readability.analyze(text, analysis=a)
        avg = r["averages"]
        words, wps, spw, cpw, rd_err = (
            r["counts"]["words"],
            avg["words_per_sentence"],
            avg["syllables_per_word"],
            avg["characters_per_word"],
            None,
        )
    except ValueError as e:
        st = statistics.analyze(text, analysis=a)["averages"]
        words, wps, spw, cpw, rd_err = (
            a.word_count,
            st["tokens_per_sentence"],
            st["syllables_per_word"],
            None,
            str(e),
        )
    dv = diversity.analyze(text, analysis=a)
    b = bnc_coca.analyze(text, analysis=a)
    n = ngsl.analyze(text, analysis=a)
    w = awl.analyze(text, analysis=a)
    cc = c["counts"]
    tot = cc["content_tokens"]
    bc = b["counts"]
    return {
        "key": _key(text),
        "words": words,
        "readability_error": rd_err,
        "content_tokens": tot,
        "estimated_level_95th": c["estimated_level_95th"],
        "cefr_cov": {lv: c["per_level"][lv]["coverage_pct"] for lv in LEVELS},
        "cefr_proper_pct": round(cc["proper_noun_tokens"] / tot * 100, 3) if tot else 0.0,
        "cefr_off_pct": round(cc["off_list_tokens"] / tot * 100, 3) if tot else 0.0,
        "bnc_cum": {
            k: b["per_band"][k]["cumulative_coverage_pct"] for k in ("1", "2", "3", "4", "5", "10")
        },
        "bnc_off_pct": round(bc["off_list_tokens"] / bc["content_tokens"] * 100, 3)
        if bc["content_tokens"]
        else 0.0,
        "words_per_sentence": wps,
        "syllables_per_word": spw,
        "characters_per_word": cpw,
        "mtld": dv.get("scores", {}).get("mtld"),
        "mattr": dv.get("scores", {}).get("mattr"),
        "awl_pct": w["coverage_pct"],
        "ngsl_pct": n["coverage_pct"]["ngsl"],
        "ngsl_nawl_pct": n["coverage_pct"]["ngsl_plus_nawl"],
        "ngsl_off_pct": n["coverage_pct"]["off_list"],
    }


def features(recs: list[dict[str, Any]], workers: int) -> dict[str, dict[str, Any]]:
    from lexinspect import __version__

    path = CACHE / f"features_{__version__}.jsonl"
    have: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            have[row["key"]] = row
    todo = list({_key(r["text"]): r["text"] for r in recs if _key(r["text"]) not in have}.values())
    if todo:
        print(f"lexinspect: {len(todo)} texts to analyse ({len(have)} cached)", file=sys.stderr)
        with path.open("a", encoding="utf-8") as out, Pool(workers) as pool:
            for i, row in enumerate(pool.imap_unordered(_features_one, todo, chunksize=8), 1):
                have[row["key"]] = row
                out.write(json.dumps(row) + "\n")
                if i % 1000 == 0:
                    print(f"  {i}/{len(todo)}", file=sys.stderr)
    return have


# --- classifier -------------------------------------------------------------------


def _classifier_revision() -> str:
    try:
        from huggingface_hub import snapshot_download

        p = Path(snapshot_download(CLASSIFIER_ID, local_files_only=True))
        return p.name
    except Exception:
        return "unknown"


def classify(recs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], str]:
    from lexinspect import cefr_level

    cefr_level.analyze("Warm-up.")  # downloads the model on first use
    rev = _classifier_revision()
    path = CACHE / f"classifier_{rev[:12]}.jsonl"
    have: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            have[row["key"]] = row
    todo = list({_key(r["text"]): r["text"] for r in recs if _key(r["text"]) not in have}.items())
    if todo:
        print(
            f"classifier: {len(todo)} texts ({len(have)} cached), revision {rev}", file=sys.stderr
        )
        with path.open("a", encoding="utf-8") as out:
            for i, (k, text) in enumerate(todo, 1):
                res = cefr_level.analyze(text)
                row = {
                    "key": k,
                    "level": res["level"],
                    "confidence": res["confidence"],
                    "all_levels": res["all_levels"],
                }
                have[k] = row
                out.write(json.dumps(row) + "\n")
                if i % 500 == 0:
                    out.flush()
                    print(f"  {i}/{len(todo)}", file=sys.stderr)
    return have, rev


# --- ordinal model ------------------------------------------------------------------

FEATURE_NAMES = (
    [f"cefr_{lv}_pct" for lv in LEVELS]
    + ["cefr_proper_pct", "cefr_off_pct"]
    + [f"bnc_cum_{k}k_pct" for k in ("1", "2", "3", "4", "5", "10")]
    + ["bnc_off_pct", "words_per_sentence", "syllables_per_word", "characters_per_word"]
    + ["mtld", "mattr", "awl_pct", "ngsl_pct", "ngsl_nawl_pct", "ngsl_off_pct"]
)


def feature_row(f: dict[str, Any]) -> list[float]:
    def num(x: Any) -> float:
        return float("nan") if x is None else float(x)

    return (
        [f["cefr_cov"][lv] for lv in LEVELS]
        + [f["cefr_proper_pct"], f["cefr_off_pct"]]
        + [f["bnc_cum"][k] for k in ("1", "2", "3", "4", "5", "10")]
        + [
            f["bnc_off_pct"],
            f["words_per_sentence"],
            f["syllables_per_word"],
            num(f["characters_per_word"]),
        ]
        + [
            num(f["mtld"]),
            num(f["mattr"]),
            f["awl_pct"],
            f["ngsl_pct"],
            f["ngsl_nawl_pct"],
            f["ngsl_off_pct"],
        ]
    )


class OrdinalLogit:
    """Cumulative-link (proportional-odds) logistic regression with an L2
    penalty on the slopes. P(y <= k) = sigmoid(theta_k - x.w). Fitted on the
    standardised, median-imputed features; classes are the integer levels
    between the lowest and highest level seen in training."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X: np.ndarray, y: np.ndarray) -> OrdinalLogit:
        self.prep = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler()
        )
        Z = self.prep.fit_transform(X)
        Z = np.nan_to_num(Z)
        self.lo, self.hi = int(y.min()), int(y.max())
        K = self.hi - self.lo + 1
        yi = (y - self.lo).astype(int)
        p = Z.shape[1]
        n = len(y)

        def unpack(params):
            w = params[:p]
            t0 = params[p]
            gaps = np.exp(params[p + 1 :])
            theta = np.concatenate([[t0], t0 + np.cumsum(gaps)])
            return w, theta

        def nll(params):
            w, theta = unpack(params)
            eta = Z @ w
            # cumulative probs with -inf / +inf ends
            th = np.concatenate([[-np.inf], theta, [np.inf]])
            upper = th[yi + 1] - eta
            lower = th[yi] - eta
            pr = _sig(upper) - _sig(lower)
            pr = np.clip(pr, 1e-12, 1)
            return -np.log(pr).sum() / n + self.alpha * (w @ w) / n

        init = np.zeros(p + K - 1)
        if K > 1:
            cum = np.cumsum(np.bincount(yi, minlength=K))[:-1] / n
            cum = np.clip(cum, 1e-3, 1 - 1e-3)
            logits = np.log(cum / (1 - cum))
            init[p] = logits[0]
            init[p + 1 :] = np.log(np.maximum(np.diff(logits), 1e-2))
        res = minimize(nll, init, method="L-BFGS-B")
        self.w, self.theta = unpack(res.x)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Z = np.nan_to_num(self.prep.transform(X))
        eta = Z @ self.w
        cum = _sig(self.theta[None, :] - eta[:, None])
        cum = np.concatenate([np.zeros((len(eta), 1)), cum, np.ones((len(eta), 1))], axis=1)
        return np.diff(cum, axis=1)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(1) + self.lo


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def ridge_round(Xtr, ytr, Xte):
    m = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-2, 4, 25)),
    )
    m.fit(np.nan_to_num(Xtr, nan=np.nan), ytr)
    return np.clip(np.rint(m.predict(Xte)), 1, 6).astype(int)


def _choose_alpha(X, y) -> float:
    """Pick the L2 penalty by inner 3-fold CV on QWK."""
    best, best_a = -9.0, 1.0
    skf = StratifiedKFold(3, shuffle=True, random_state=SEED + 1)
    strat = _strat(y, 3)
    for a in (0.1, 1.0, 10.0, 100.0):
        preds = np.zeros_like(y)
        for tr, te in skf.split(X, strat):
            preds[te] = OrdinalLogit(a).fit(X[tr], y[tr]).predict(X[te])
        q = cohen_kappa_score(y, preds, weights="quadratic", labels=list(range(1, 7)))
        if q > best:
            best, best_a = q, a
    return best_a


def _strat(y: np.ndarray, k: int) -> np.ndarray:
    """Stratification labels: merge levels with fewer than k texts into a neighbour."""
    y = y.copy()
    counts = Counter(y.tolist())
    for lv, c in sorted(counts.items()):
        if c < k:
            others = [o for o in counts if o != lv and counts[o] >= k]
            if others:
                y[y == lv] = min(others, key=lambda o: abs(o - lv))
    return y


def cv_predict(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[float]]:
    ord_pred = np.zeros_like(y)
    ridge_pred = np.zeros_like(y)
    alphas: list[float] = []
    skf = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in skf.split(X, _strat(y, N_FOLDS)):
        a = _choose_alpha(X[tr], y[tr])
        alphas.append(a)
        ord_pred[te] = OrdinalLogit(a).fit(X[tr], y[tr]).predict(X[te])
        ridge_pred[te] = ridge_round(X[tr], y[tr], X[te])
    return ord_pred, ridge_pred, alphas


# --- metrics --------------------------------------------------------------------

BUCKETS = [
    (0, 19, "<20"),
    (20, 49, "20-49"),
    (50, 149, "50-149"),
    (150, 399, "150-399"),
    (400, 10**9, "400+"),
]


def _bucket(words: int) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= words <= hi:
            return name
    return "400+"


def metrics(
    y: np.ndarray,
    p: np.ndarray,
    words: np.ndarray | None = None,
    *,
    extra_col: np.ndarray | None = None,
) -> dict[str, Any]:
    y = np.asarray(y, int)
    p = np.asarray(p, int)
    n = len(y)
    if n == 0:
        return {"n": 0}
    err = p - y
    present = sorted(set(y.tolist()))
    out: dict[str, Any] = {
        "n": n,
        "exact": round(float((err == 0).mean()), 4),
        "within_one": round(float((np.abs(err) <= 1).mean()), 4),
        "off_by_two_or_more": round(float((np.abs(err) >= 2).mean()), 4),
        "macro_f1": round(
            float(f1_score(y, p, labels=present, average="macro", zero_division=0)), 4
        ),
        "weighted_f1": round(
            float(f1_score(y, p, labels=present, average="weighted", zero_division=0)), 4
        ),
        "qwk": _qwk(y, p),
        "mean_signed_error": round(float(err.mean()), 3),
        "mean_abs_error": round(float(np.abs(err).mean()), 3),
        "pred_distribution": {LEVELS[k - 1]: int((p == k).sum()) for k in range(1, 7)},
        "confusion_matrix": {
            "rows_gold_cols_pred": LEVELS,
            "matrix": confusion_matrix(y, p, labels=list(range(1, 7))).tolist(),
        },
    }
    if extra_col is not None:
        out["confusion_matrix"]["no_estimate_by_gold"] = [
            int(((y == k) & extra_col).sum()) for k in range(1, 7)
        ]
    if words is not None:
        bk = np.array([_bucket(int(w)) for w in words])
        out["by_length"] = {}
        for _, _, name in BUCKETS:
            m = bk == name
            if m.sum():
                e = err[m]
                out["by_length"][name] = {
                    "n": int(m.sum()),
                    "exact": round(float((e == 0).mean()), 4),
                    "within_one": round(float((np.abs(e) <= 1).mean()), 4),
                    "qwk": _qwk(y[m], p[m]) if m.sum() >= 10 else None,
                    "mean_signed_error": round(float(e.mean()), 3),
                }
    return out


def _qwk(y, p) -> float | None:
    if len(set(np.asarray(y).tolist()) | set(np.asarray(p).tolist())) < 2:
        return None
    k = cohen_kappa_score(y, p, weights="quadratic", labels=list(range(1, 7)))
    return None if math.isnan(k) else round(float(k), 4)


# --- main -------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-classifier", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="texts per dataset (smoke test)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    fetch()
    recs = [r for r in load() if r["level"] is not None]
    if args.limit:
        rng = np.random.default_rng(SEED)
        keep = []
        for name in ORDER:
            rs = [r for r in recs if r["dataset"] == name]
            idx = rng.choice(len(rs), min(args.limit, len(rs)), replace=False)
            keep += [rs[i] for i in sorted(idx)]
        recs = keep

    feats = features(recs, args.workers)
    clf, clf_rev = ({}, None) if args.skip_classifier else classify(recs)

    # Text duplicated across datasets (ELG contains Cambridge passages).

    results: dict[str, Any] = {"datasets": {}, "estimators": {}}
    per_ds: dict[str, dict[str, Any]] = {}

    for name in ORDER:
        rs = [r for r in recs if r["dataset"] == name]
        if not rs:
            continue
        y = np.array([r["level"] for r in rs])
        fs = [feats[_key(r["text"])] for r in rs]
        words = np.array([f["words"] for f in fs])
        X = np.array([feature_row(f) for f in fs], dtype=float)
        per_ds[name] = {"rs": rs, "y": y, "X": X, "words": words, "fs": fs}
        d = DATASETS[name]
        results["datasets"][name] = {
            "source": d["source"],
            "licence": d["licence"],
            "text_type": d["text_type"],
            "construct": d["construct"],
            "in_universalcefr_so_overlaps_classifier_training": d["in_universalcefr"],
            "n": len(rs),
            "n_per_level": {lv: int((y == LEVEL_NUM[lv]).sum()) for lv in LEVELS},
            "words_median": int(np.median(words)),
            "words_range": [int(words.min()), int(words.max())],
            "readability_crashes": sum(1 for f in fs if f.get("readability_error")),
        }
        if name == "elg_cefr_en":
            results["datasets"][name]["note"] = (
                f"{ELG_OVERLAP['removed']} ELG texts are Cambridge exam passages (matched on the first 200 "
                f"normalised characters; {ELG_OVERLAP['same_level']} carry the same level) and are excluded "
                "here; n counts only the remaining ELG texts."
            )

    # Modal-level baseline (in-sample, optimistic).
    base: dict[str, Any] = {}
    for name, D in per_ds.items():
        mode = Counter(D["y"].tolist()).most_common(1)[0][0]
        base[name] = metrics(D["y"], np.full_like(D["y"], mode), D["words"])
        base[name]["predicts"] = LEVELS[mode - 1]
    results["estimators"]["baseline_modal_level"] = base

    # (a) estimated_level_95th as shipped.
    heur: dict[str, Any] = {}
    for name, D in per_ds.items():
        raw = [f["estimated_level_95th"] for f in D["fs"]]
        none = np.array([x is None for x in raw])
        p = np.array([6 if x is None else LEVEL_NUM[x] for x in raw])
        m = metrics(D["y"], p, D["words"], extra_col=none)
        m["no_estimate_n"] = int(none.sum())
        m["no_estimate_handling"] = "null counted as C2 (the text's words go beyond the C2 lists)"
        m["answered_only"] = metrics(D["y"][~none], p[~none]) if (~none).sum() else {"n": 0}
        m["answered_only"].pop("confusion_matrix", None)
        heur[name] = m
    results["estimators"]["a_estimated_level_95th"] = heur

    # (b) cefr_level classifier as shipped.
    if clf:
        cl: dict[str, Any] = {}
        for name, D in per_ds.items():
            p = np.array(
                [
                    LEVEL_NUM[clf[_key(r["text"])]["level"]] if clf[_key(r["text"])]["level"] else 1
                    for r in D["rs"]
                ]
            )
            m = metrics(D["y"], p, D["words"])
            m["contaminated"] = DATASETS[name]["in_universalcefr"]
            if name == "ace_cefr":
                te = np.array([r["split"] == "test" for r in D["rs"]])
                m["ace_test_split_only"] = metrics(D["y"][te], p[te])
                m["ace_test_split_only"].pop("confusion_matrix", None)
            cl[name] = m
        results["estimators"]["b_cefr_level_classifier"] = cl

    # (c) ordinal model on lexinspect features.
    within: dict[str, Any] = {}
    ridge_within: dict[str, Any] = {}
    for name, D in per_ds.items():
        print(f"ordinal model CV: {name}", file=sys.stderr)
        po, pr, alphas = cv_predict(D["X"], D["y"])
        within[name] = metrics(D["y"], po, D["words"])
        within[name]["l2_alpha_per_fold"] = alphas
        ridge_within[name] = metrics(D["y"], pr, D["words"])
        ridge_within[name].pop("confusion_matrix")
    results["estimators"]["c_ordinal_within_dataset_cv"] = within
    results["estimators"]["c_ridge_round_within_dataset_cv"] = ridge_within

    # Transfer: train once on reading texts (Cambridge + ELG, deduplicated),
    # apply unchanged to every other dataset.
    seen: set[str] = set()
    Xt, yt = [], []
    for name in TRANSFER_TRAIN:
        if name not in per_ds:
            continue
        D = per_ds[name]
        for r, x, yy in zip(D["rs"], D["X"], D["y"], strict=True):
            k = _key(r["text"].strip())
            if k in seen:
                continue
            seen.add(k)
            Xt.append(x)
            yt.append(yy)
    transfer: dict[str, Any] = {}
    coefs: dict[str, float] = {}
    if Xt:
        Xt_a, yt_a = np.array(Xt), np.array(yt)
        alpha = _choose_alpha(Xt_a, yt_a)
        model = OrdinalLogit(alpha).fit(Xt_a, yt_a)
        coefs = {
            n: round(float(w), 3)
            for n, w in sorted(zip(FEATURE_NAMES, model.w, strict=True), key=lambda t: -abs(t[1]))
        }
        for name, D in per_ds.items():
            if name in TRANSFER_TRAIN:
                continue
            transfer[name] = metrics(D["y"], model.predict(D["X"]), D["words"])
        transfer["_train"] = {
            "datasets": TRANSFER_TRAIN,
            "n": len(yt),
            "l2_alpha": alpha,
            "levels_seen": [LEVELS[model.lo - 1], LEVELS[model.hi - 1]],
        }
    results["estimators"]["c_ordinal_transfer_from_reading_texts"] = transfer
    results["ordinal_model_coefficients_reading_texts"] = {
        "note": "Slopes on standardised features (positive = pushes towards a higher level). Features are strongly collinear; read signs and sizes together, not one by one.",
        "coefficients": coefs,
    }

    # Human ceiling on Ace-CEFR: rater 1 against rater 2.
    if "ace_cefr" in per_ds:
        rs = [
            r
            for r in per_ds["ace_cefr"]["rs"]
            if r["rater1"] is not None and r["rater2"] is not None
        ]
        r1 = np.array([r["rater1"] for r in rs])
        r2 = np.array([r["rater2"] for r in rs])
        hm = metrics(r1, r2)
        hm["note"] = (
            "Rater 2 scored against rater 1, both mapped to levels like the gold label; the gold label averages them, so this is a lower bound on gold-label reliability."
        )
        results["human_ceiling_ace_cefr_rater1_vs_rater2"] = hm

    results["features"] = FEATURE_NAMES
    results["method"] = {
        "levels": "A1=1 ... C2=6. '+' sub-levels (A2+, B1+, B2+) are folded into their base level. Ace-CEFR's 1-6 scores (half steps, rater averages) are mapped to the nearest level with .5 rounded down.",
        "heuristic_nulls": "estimated_level_95th is null when on-list plus proper-noun coverage never reaches 95%; scored as C2 and reported separately.",
        "classifier": "lexinspect.cefr_level.analyze(text) unchanged, top label.",
        "ordinal_model": f"Proportional-odds logistic regression, L2 penalty chosen by inner 3-fold CV on QWK from {{0.1, 1, 10, 100}}, median imputation (MTLD/MATTR are null under ~50 tokens), standardised. Within-dataset: stratified {N_FOLDS}-fold CV, seed {SEED}. Transfer: one model fitted on Cambridge + ELG reading texts (deduplicated), applied unchanged elsewhere.",
        "ridge_check": "RidgeCV regression on the same features, rounded and clipped to 1-6; reported as a robustness check.",
        "macro_f1": "Averaged over the levels present in the gold labels of that dataset.",
        "length_buckets": [b[2] for b in BUCKETS],
        "length_unit": "lexinspect word count (readability.counts.words)",
        "baseline": "Always predict the dataset's most frequent gold level (in-sample, so optimistic).",
    }
    import importlib.metadata as md

    from lexinspect._schema import provenance

    versions = {}
    for pkg in ("scikit-learn", "numpy", "scipy", "torch", "transformers"):
        with contextlib.suppress(md.PackageNotFoundError):
            versions[pkg] = md.version(pkg)
    results["provenance"] = {
        **provenance(),
        "classifier": {"model": CLASSIFIER_ID, "revision": clf_rev} if clf else None,
        "packages": versions,
        "limit": args.limit or None,
    }

    if args.limit:
        print(json.dumps(results, indent=1)[:4000])
        print("--limit set: not writing docs/validation output", file=sys.stderr)
        return
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    TABLES_MD.write_text(render_tables(results), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {TABLES_MD.relative_to(ROOT)}", file=sys.stderr)


def _pct(x):
    return "–" if x is None else f"{x * 100:.0f}%"


def _f(x, nd=2):
    return "–" if x is None else f"{x:.{nd}f}"


def render_tables(res: dict[str, Any]) -> str:
    L: list[str] = []
    est = res["estimators"]
    labels = {
        "baseline_modal_level": "Baseline: always the modal level",
        "a_estimated_level_95th": "(a) estimated_level_95th",
        "b_cefr_level_classifier": "(b) cefr_level classifier",
        "c_ordinal_transfer_from_reading_texts": "(c) ordinal model, trained on reading texts",
        "c_ordinal_within_dataset_cv": "(c) ordinal model, within-dataset CV",
        "c_ridge_round_within_dataset_cv": "(c') ridge + round, within-dataset CV",
    }
    L.append("| Dataset | Estimator | N | Exact | Within 1 | Macro-F1 | QWK | Bias (levels) |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for ds in ORDER:
        if ds not in res["datasets"]:
            continue
        for e, lab in labels.items():
            m = est.get(e, {}).get(ds)
            if not m:
                continue
            L.append(
                f"| {ds} | {lab} | {m['n']} | {_pct(m['exact'])} | {_pct(m['within_one'])} | {_f(m['macro_f1'])} | {_f(m['qwk'])} | {m['mean_signed_error']:+.2f} |"
            )
    L.append("")
    for e in (
        "a_estimated_level_95th",
        "b_cefr_level_classifier",
        "c_ordinal_transfer_from_reading_texts",
        "c_ordinal_within_dataset_cv",
    ):
        for ds in ORDER:
            m = est.get(e, {}).get(ds)
            if not m or "confusion_matrix" not in m:
                continue
            L.append(f"**{labels[e]} — {ds}** (rows gold, columns predicted)\n")
            cm = m["confusion_matrix"]
            extra = cm.get("no_estimate_by_gold")
            L.append(
                "| gold \\ pred | " + " | ".join(LEVELS) + (" | of which null |" if extra else " |")
            )
            L.append("|---" * (7 + (1 if extra else 0)) + "|")
            for i, lv in enumerate(LEVELS):
                if sum(cm["matrix"][i]) == 0:
                    continue
                L.append(
                    f"| {lv} | "
                    + " | ".join(str(v) for v in cm["matrix"][i])
                    + (f" | {extra[i]} |" if extra else " |")
                )
            L.append("")
    L.append("**By length** (exact / within one / bias)\n")
    L.append("| Dataset | Estimator | " + " | ".join(b[2] for b in BUCKETS) + " |")
    L.append("|---|---|" + "---:|" * len(BUCKETS))
    for ds in ORDER:
        for e in (
            "a_estimated_level_95th",
            "b_cefr_level_classifier",
            "c_ordinal_within_dataset_cv",
        ):
            m = est.get(e, {}).get(ds)
            if not m:
                continue
            cells = []
            for b in BUCKETS:
                x = m["by_length"].get(b[2])
                cells.append(
                    ""
                    if not x
                    else f"{_pct(x['exact'])} / {_pct(x['within_one'])} / {x['mean_signed_error']:+.1f} (n={x['n']})"
                )
            L.append(f"| {ds} | {labels[e]} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
