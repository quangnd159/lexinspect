"""Fit and evaluate the reading-text CEFR level model; write data/level_model.json.

    uv run --with numpy --with scipy --with scikit-learn \
        python scripts/build_data/build_level_model.py [--workers N]

numpy/scipy/scikit-learn are needed here only, for training and evaluation.
The shipped estimator (`lexinspect.level`) is pure standard library: it reads
the coefficients this script exports.

Steps:

1. Download the Study 5 datasets if absent (pinned revisions, SHA-256 checked;
   `scripts/validation/study5_cefr/run.py` owns the list) into
   `.cache/validation/study5/raw/`. ELG-CEFR-EN loses the passages it shares
   with the Cambridge exams set, as in Study 5.
2. Run `lexinspect.pipeline.run_all` on every text and keep the parts the
   model reads (cached in `.cache/validation/level_model/`). Features come
   from `lexinspect.level.features`, the same function the estimator uses.
3. Train ONLY on reading texts: Cambridge exams + ELG-CEFR-EN.
4. Evaluate: stratified 5-fold CV (L2 penalty chosen by inner 3-fold CV),
   leave-one-dataset-out, by length bucket, and, purely to document misuse,
   Ace-CEFR passages of 50+ words and ICLE learner essays.
5. Fit the final model on all reading texts and write
   `src/lexinspect/data/level_model.json` with the evaluation and metadata.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.metadata as md
import importlib.util
import json
import math
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "validation" / "level_model"
OUT = ROOT / "src" / "lexinspect" / "data" / "level_model.json"
STUDY5 = ROOT / "scripts" / "validation" / "study5_cefr" / "run.py"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
SEED = 0
N_FOLDS = 5
ALPHAS = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
MIN_WORDS = 100
# Standardised features are clipped to +-Z_CLIP so a text far outside the
# training range can't drive the logit (and its probabilities) to 0 or 1.
Z_CLIP = 3.0
TRAIN = ["cambridge_exams", "elg_cefr_en"]
BUCKETS = [(0, 149, "<150"), (150, 300, "150-300"), (301, 10**9, "300+")]

# Feature sets. Every slope except proper-noun share is constrained to the
# sign a teacher would expect (positive = more of it, higher level), which
# makes the listed contributions readable; the unconstrained fit is reported
# alongside as a check on what the constraint costs.
STUDY5_SET = [
    *(f"cefr_above_{lv}_pct" for lv in LEVELS[:5]),
    "cefr_off_list_pct",
    "cefr_proper_noun_pct",
    *(f"bnc_beyond_{k}k_pct" for k in ("1", "2", "3", "4", "5", "10")),
    "bnc_off_list_pct",
    "words_per_sentence",
    "syllables_per_word",
    "characters_per_word",
    "mtld",
    "mattr",
    "awl_pct",
    "outside_ngsl_pct",
    "outside_ngsl_nawl_pct",
    "ngsl_off_list_pct",
]
EXTENDED_SET = [
    *STUDY5_SET,
    *(f"phrase_beyond_{k}k_pct" for k in ("1", "2", "3", "4", "5", "10")),
    "polysyllable_pct",
    "dale_chall_difficult_pct",
]
FREE_SIGN = {"cefr_proper_noun_pct"}
# CVLA's four indices (Uchida & Negishi 2018), read from the Analysis rather
# than from run_all's results, so a model using them would need the Analysis.
CVLA_SET = ["cvla_ari", "cvla_verbs_per_sentence", "cvla_avr_diff", "cvla_b_per_a"]


def _load_study5():
    spec = importlib.util.spec_from_file_location("study5_run", STUDY5)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# --- lexinspect over every text ------------------------------------------------------


def _slim(results: dict[str, Any]) -> dict[str, Any]:
    """The parts of run_all's results that `level.features` reads (plus the
    95th-percentile heuristic, for comparison), so the cache stays small."""
    ph = results["phrase"]
    return {
        "readability": {k: results["readability"][k] for k in ("counts", "averages")},
        "diversity": {"scores": results["diversity"].get("scores", {})},
        "awl": {"coverage_pct": results["awl"]["coverage_pct"]},
        "bnc_coca": {k: results["bnc_coca"][k] for k in ("counts", "per_band")},
        "ngsl": {"coverage_pct": results["ngsl"]["coverage_pct"]},
        "phrase": {
            "counts": ph["counts"],
            "integrated_profile": {k: ph["integrated_profile"][k] for k in ("counts", "per_band")},
        },
        "cefr": {k: results["cefr"][k] for k in ("counts", "per_level", "estimated_level_95th")},
    }


def _analyse_one(item: tuple[str, str]) -> dict[str, Any]:
    from lexinspect import level
    from lexinspect.pipeline import run_all

    key, text = item
    a, results = run_all(text, modules=level.REQUIRED_MODULES)
    ari = results["readability"]["scores"]["automated_readability_index"]
    return {"key": key, "results": _slim(results), "cvla": level.cvla_indices(a, ari)}


def analyse_all(
    texts: dict[str, str], workers: int
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """(slim run_all results, CVLA indices) per text key."""
    from lexinspect import __version__

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"results_{__version__}.jsonl"
    have: dict[str, dict[str, Any]] = {}
    cv: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            have[row["key"]] = row["results"]
            cv[row["key"]] = row["cvla"]
    todo = [(k, t) for k, t in texts.items() if k not in have]
    if todo:
        print(f"run_all: {len(todo)} texts to analyse ({len(have)} cached)", file=sys.stderr)
        with path.open("a", encoding="utf-8") as out, Pool(workers) as pool:
            for i, row in enumerate(pool.imap_unordered(_analyse_one, todo, chunksize=4), 1):
                have[row["key"]] = row["results"]
                cv[row["key"]] = row["cvla"]
                out.write(json.dumps(row) + "\n")
                if i % 200 == 0:
                    out.flush()
                    print(f"  {i}/{len(todo)}", file=sys.stderr)
    return have, cv


# --- model -----------------------------------------------------------------------------


def _sig(x):
    return 0.5 * (1.0 + np.tanh(0.5 * x))


class OrdinalLogit:
    """Proportional-odds logistic regression, P(y <= k) = sigmoid(theta_k - x.w),
    on median-imputed, standardised features, with an L2 penalty on the slopes
    and optional sign bounds. Classes run from the lowest to the highest level
    seen in training (levels are 1..6)."""

    def __init__(self, alpha: float, signs: list[int] | None = None):
        self.alpha = alpha
        self.signs = signs  # +1: slope >= 0; 0: free

    def _prep(self, X: np.ndarray) -> np.ndarray:
        X = np.where(np.isnan(X), self.median, X)
        return np.clip((X - self.mean) / self.sd, -Z_CLIP, Z_CLIP)

    def fit(self, X: np.ndarray, y: np.ndarray) -> OrdinalLogit:
        self.median = np.nanmedian(X, axis=0)
        self.median = np.where(np.isnan(self.median), 0.0, self.median)
        Xi = np.where(np.isnan(X), self.median, X)
        self.mean = Xi.mean(axis=0)
        self.sd = Xi.std(axis=0)
        self.sd = np.where(self.sd > 1e-9, self.sd, 1.0)
        Z = np.clip((Xi - self.mean) / self.sd, -Z_CLIP, Z_CLIP)
        self.lo, self.hi = int(y.min()), int(y.max())
        K = self.hi - self.lo + 1
        yi = (y - self.lo).astype(int)
        n, p = Z.shape

        def unpack(params):
            w = params[:p]
            theta = params[p] + np.concatenate([[0.0], np.cumsum(np.exp(params[p + 1 :]))])
            return w, theta

        def nll_grad(params):
            w, theta = unpack(params)
            eta = Z @ w
            th = np.concatenate([[-np.inf], theta, [np.inf]])
            u = th[yi + 1] - eta
            lo_ = th[yi] - eta
            Fu, Fl = _sig(u), _sig(lo_)
            P = np.clip(Fu - Fl, 1e-12, None)
            fu = np.where(np.isfinite(u), Fu * (1 - Fu), 0.0)
            fl = np.where(np.isfinite(lo_), Fl * (1 - Fl), 0.0)
            loss = -np.log(P).sum() / n + self.alpha * (w @ w) / n
            g_eta = (fu - fl) / P / n
            gw = Z.T @ g_eta + 2 * self.alpha * w / n
            # d loss / d theta_j for j = 0..K-2
            gth = np.zeros(K - 1)
            np.add.at(gth, yi[yi < K - 1], -(fu / P / n)[yi < K - 1])
            np.add.at(gth, yi[yi > 0] - 1, (fl / P / n)[yi > 0])
            g = np.zeros_like(params)
            g[:p] = gw
            g[p] = gth.sum()
            gaps = np.exp(params[p + 1 :])
            # theta_j depends on gap m (1-based) for m <= j
            g[p + 1 :] = gaps * np.cumsum(gth[::-1])[::-1][1:]
            return loss, g

        init = np.zeros(p + K - 1)
        cum = np.clip(np.cumsum(np.bincount(yi, minlength=K))[:-1] / n, 1e-3, 1 - 1e-3)
        logits = np.log(cum / (1 - cum))
        init[p] = logits[0]
        init[p + 1 :] = np.log(np.maximum(np.diff(logits), 1e-2))
        signs = self.signs or [0] * p
        bounds = [(0.0, None) if s > 0 else (None, None) for s in signs] + [(None, None)] * (K - 1)
        res = minimize(
            nll_grad,
            init,
            jac=True,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 5000, "gtol": 1e-8},
        )
        self.converged = bool(res.success)
        self.w, self.theta = unpack(res.x)
        return self

    def proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilities over all six levels (zero outside the trained range)."""
        eta = self._prep(X) @ self.w
        cum = _sig(self.theta[None, :] - eta[:, None])
        cum = np.concatenate([np.zeros((len(eta), 1)), cum, np.ones((len(eta), 1))], axis=1)
        p = np.diff(cum, axis=1)
        full = np.zeros((len(eta), 6))
        full[:, self.lo - 1 : self.hi] = p
        return full

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.proba(X).argmax(1) + 1


def _strat(y: np.ndarray, k: int) -> np.ndarray:
    y = y.copy()
    counts = Counter(y.tolist())
    for lv, c in sorted(counts.items()):
        if c < k:
            others = [o for o in counts if o != lv and counts[o] >= k]
            if others:
                y[y == lv] = min(others, key=lambda o: abs(o - lv))
    return y


def _qwk(y, p) -> float | None:
    if len(set(np.asarray(y).tolist()) | set(np.asarray(p).tolist())) < 2:
        return None
    k = cohen_kappa_score(y, p, weights="quadratic", labels=list(range(1, 7)))
    return None if math.isnan(k) else round(float(k), 4)


def choose_alpha(X, y, signs) -> float:
    """L2 penalty by inner 3-fold CV on QWK (ties: the larger penalty)."""
    best, best_a = -9.0, ALPHAS[0]
    skf = StratifiedKFold(3, shuffle=True, random_state=SEED + 1)
    for a in ALPHAS:
        preds = np.zeros_like(y)
        for tr, te in skf.split(X, _strat(y, 3)):
            preds[te] = OrdinalLogit(a, signs).fit(X[tr], y[tr]).predict(X[te])
        q = _qwk(y, preds) or -9.0
        if q >= best:
            best, best_a = q, a
    return best_a


def fit(X, y, signs) -> OrdinalLogit:
    return OrdinalLogit(choose_alpha(X, y, signs), signs).fit(X, y)


def cv_proba(X, y, signs) -> tuple[np.ndarray, list[float]]:
    P = np.zeros((len(y), 6))
    alphas = []
    skf = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in skf.split(X, _strat(y, N_FOLDS)):
        m = fit(X[tr], y[tr], signs)
        alphas.append(m.alpha)
        P[te] = m.proba(X[te])
    return P, alphas


# --- metrics -------------------------------------------------------------------------


def _range_idx(p: np.ndarray, mass: float = 0.8) -> tuple[int, int]:
    from lexinspect.level import level_range

    rng = level_range(dict(zip(LEVELS, p.tolist(), strict=True)), mass)
    return LEVELS.index(rng[0]) + 1, LEVELS.index(rng[-1]) + 1


def _bucket(w: int) -> str:
    return next(name for lo, hi, name in BUCKETS if lo <= w <= hi)


def metrics(y, pred, P=None, words=None, *, buckets=True) -> dict[str, Any]:
    y = np.asarray(y, int)
    pred = np.asarray(pred, int)
    n = len(y)
    if not n:
        return {"n": 0}
    err = pred - y
    present = sorted(set(y.tolist()))
    out: dict[str, Any] = {
        "n": n,
        "exact": round(float((err == 0).mean()), 4),
        "within_one": round(float((np.abs(err) <= 1).mean()), 4),
        "off_by_two_or_more": round(float((np.abs(err) >= 2).mean()), 4),
        "qwk": _qwk(y, pred),
        "macro_f1": round(
            float(f1_score(y, pred, labels=present, average="macro", zero_division=0)), 4
        ),
        "mean_signed_error": round(float(err.mean()), 3),
        "mean_abs_error": round(float(np.abs(err).mean()), 3),
        "n_per_gold_level": {LEVELS[k - 1]: int((y == k).sum()) for k in range(1, 7)},
        "pred_distribution": {LEVELS[k - 1]: int((pred == k).sum()) for k in range(1, 7)},
        "confusion_matrix": {
            "rows_gold_cols_pred": LEVELS,
            "matrix": confusion_matrix(y, pred, labels=list(range(1, 7))).tolist(),
        },
    }
    if P is not None:
        rngs = [_range_idx(p) for p in P]
        inside = [lo <= g <= hi for g, (lo, hi) in zip(y, rngs, strict=True)]
        out["range_80"] = {
            "gold_inside": round(float(np.mean(inside)), 4),
            "mean_width_levels": round(float(np.mean([hi - lo + 1 for lo, hi in rngs])), 3),
            "width_distribution": dict(
                sorted(Counter(str(hi - lo + 1) for lo, hi in rngs).items())
            ),
        }
    if words is not None and buckets:
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
                    "qwk": _qwk(y[m], pred[m]) if m.sum() >= 10 else None,
                    "mean_signed_error": round(float(e.mean()), 3),
                }
    return out


def short(m: dict[str, Any]) -> dict[str, Any]:
    keep = ("n", "exact", "within_one", "qwk", "mean_signed_error", "range_80")
    return {k: m[k] for k in keep if k in m}


# --- main ------------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT, help="where to write the model JSON")
    ap.add_argument("--features-only", action="store_true", help="only fill the cache")
    args = ap.parse_args()

    from lexinspect import __version__, level
    from lexinspect._schema import provenance

    s5 = _load_study5()
    s5.fetch()
    recs = [r for r in s5.load() if r["level"] is not None]
    wanted = {*TRAIN, "ace_cefr", "icle500"}
    recs = [r for r in recs if r["dataset"] in wanted]
    texts = {_key(r["text"]): r["text"] for r in recs}
    res, cvl = analyse_all(texts, args.workers)
    if args.features_only:
        return

    feat_cache: dict[str, dict[str, float | None]] = {}

    def feats_of(k: str) -> dict[str, float | None]:
        if k not in feat_cache:
            feat_cache[k] = {
                **level.features(res[k]),
                **{f"cvla_{n}": v for n, v in cvl[k].items()},
            }
        return feat_cache[k]

    def table(names: list[str], rows: list[dict[str, Any]]):
        X = np.array(
            [
                [np.nan if (v := feats_of(_key(r["text"]))[f]) is None else v for f in names]
                for r in rows
            ],
            dtype=float,
        )
        y = np.array([r["level"] for r in rows])
        w = np.array([level.word_count(res[_key(r["text"])]) for r in rows])
        return X, y, w

    by_ds = {name: [r for r in recs if r["dataset"] == name] for name in wanted}
    # Pooled training set, deduplicated on exact text (Study 5's ELG filter
    # already removed the Cambridge passages ELG re-indexes).
    seen: set[str] = set()
    train_rows = []
    for name in TRAIN:
        for r in by_ds[name]:
            k = _key(r["text"].strip())
            if k not in seen:
                seen.add(k)
                train_rows.append(r)
    ds_of = np.array([r["dataset"] for r in train_rows])

    configs = {
        "study5_24_signed": (STUDY5_SET, True),
        "study5_24_unconstrained": (STUDY5_SET, False),
        "extended_signed": (EXTENDED_SET, True),
        "extended_unconstrained": (EXTENDED_SET, False),
        "extended_plus_cvla_indices_signed": (EXTENDED_SET + CVLA_SET, True),
        "cvla_indices_refitted_signed": (CVLA_SET, True),
    }
    evals: dict[str, Any] = {}
    cv_store: dict[str, Any] = {}
    for cname, (names, signed) in configs.items():
        print(f"evaluating {cname}", file=sys.stderr)
        signs = [0 if (not signed or f in FREE_SIGN) else 1 for f in names]
        X, y, w = table(names, train_rows)
        P, alphas = cv_proba(X, y, signs)
        pred = P.argmax(1) + 1
        app = w >= MIN_WORDS
        e: dict[str, Any] = {
            "cv_all": metrics(y, pred, P, w),
            "cv_applicable": metrics(y[app], pred[app], P[app], w[app]),
            "cv_alpha_per_fold": alphas,
            "cv_by_dataset_applicable": {
                d: short(
                    metrics(y[app & (ds_of == d)], pred[app & (ds_of == d)], P[app & (ds_of == d)])
                )
                for d in TRAIN
            },
        }
        lodo = {}
        for test in TRAIN:
            (trn,) = (d for d in TRAIN if d != test)
            Xa, ya, _ = table(names, by_ds[trn])
            Xb, yb, wb = table(names, by_ds[test])
            m = fit(Xa, ya, signs)
            Pb = m.proba(Xb)
            pb = Pb.argmax(1) + 1
            ok = wb >= MIN_WORDS
            cv_store.setdefault(f"{cname}:lodo", {})[test] = Pb
            lodo[f"train_{trn}_test_{test}"] = {
                "trained_levels": [LEVELS[m.lo - 1], LEVELS[m.hi - 1]],
                "l2_alpha": m.alpha,
                "all": metrics(yb, pb, Pb, wb),
                "applicable": metrics(yb[ok], pb[ok], Pb[ok], wb[ok]),
            }
        e["leave_one_dataset_out"] = lodo
        evals[cname] = e
        cv_store[cname] = (X, y, w, P, signs, names)

    # Choice rule, fixed before looking: the sign-constrained set with the
    # higher CV QWK on applicable texts (sign constraints are chosen a priori
    # for readable contributions; the unconstrained fits are the check).
    chosen = max(
        ("study5_24_signed", "extended_signed"),
        key=lambda c: (evals[c]["cv_applicable"]["qwk"], evals[c]["cv_applicable"]["within_one"]),
    )
    X, y, w, P, signs, names = cv_store[chosen]
    print(f"chosen: {chosen}", file=sys.stderr)
    app = w >= MIN_WORDS

    # CVLA as published (no fitting), on the same texts, and a simple
    # ensemble: the mean of the ordinal model's expected level and CVLA's
    # level, rounded.
    def cvla_of(rows) -> tuple[np.ndarray, np.ndarray]:
        out_lv, out_sc = [], []
        for r in rows:
            c = level.cvla(cvl[_key(r["text"])])
            out_lv.append(LEVELS.index(c["level"]) + 1 if c["level"] else 3)
            out_sc.append(c["score"] if c["score"] is not None else 3.0)
        return np.array(out_lv), np.array(out_sc)

    def ens(Pm: np.ndarray, cv_lv: np.ndarray) -> np.ndarray:
        e_lv = Pm @ np.arange(1, 7)
        return np.clip(np.floor((e_lv + cv_lv) / 2 + 0.5), 1, 6).astype(int)

    cv_lv_tr, cv_sc_tr = cvla_of(train_rows)
    cvla_eval: dict[str, Any] = {
        "what": "CVLA Reading mode as published (Uchida & Negishi 2018, sec. 3.5): mean of "
        "four per-index regressions on ARI, verbs per sentence, mean CEFR-J level of "
        "content words, and B/A content-word ratio; CEFR-J level from the published "
        "bands, folded to six levels (Pre-A1 and A1.x = A1, ..., B2.x = B2, C1 < 5, "
        "C2 >= 5). Computed with lexinspect's spaCy tags and CEFR-J 1.5 (the paper used "
        "TreeTagger and CEFR-J 1.3). Calibrated on A1-B2 coursebooks, so C1/C2 are "
        "extrapolation.",
        "training_texts_all": metrics(y, cv_lv_tr, None, w),
        "training_texts_applicable": metrics(y[app], cv_lv_tr[app], None, w[app]),
        "by_dataset_applicable": {
            d: short(metrics(y[app & (ds_of == d)], cv_lv_tr[app & (ds_of == d)])) for d in TRAIN
        },
        "score_by_gold_level_mean": {
            LEVELS[k - 1]: round(float(cv_sc_tr[y == k].mean()), 3)
            for k in range(1, 7)
            if (y == k).any()
        },
    }
    ens_eval: dict[str, Any] = {
        "what": f"round((expected level under {chosen} + CVLA level) / 2)",
        "cv_applicable": short(metrics(y[app], ens(P, cv_lv_tr)[app])),
        "leave_one_dataset_out_applicable": {},
    }
    for test in TRAIN:
        rows_t = by_ds[test]
        _, yb, wb = table(names, rows_t)
        ok = wb >= MIN_WORDS
        lv_b, _ = cvla_of(rows_t)
        (trn,) = (d for d in TRAIN if d != test)
        ens_eval["leave_one_dataset_out_applicable"][f"train_{trn}_test_{test}"] = short(
            metrics(yb[ok], ens(cv_store[f"{chosen}:lodo"][test], lv_b)[ok])
        )
        cvla_eval.setdefault("as_leave_one_dataset_out_test_sets_applicable", {})[test] = short(
            metrics(yb[ok], lv_b[ok])
        )

    # Final model on all reading texts.
    final = fit(X, y, signs)
    assert (final.lo, final.hi) == (1, 6), "training data must span A1-C2"

    # Misuse checks: the final model on Ace-CEFR (50+ words) and ICLE essays.
    misuse = {}
    for name, floor, what in (
        ("ace_cefr", 50, "Ace-CEFR conversational passages of 50+ words"),
        ("icle500", 0, "ICLE learner essays (graded at the writer's level)"),
    ):
        Xo, yo, wo = table(names, by_ds[name])
        keep = wo >= floor
        Po = final.proba(Xo[keep])
        po = Po.argmax(1) + 1
        mode = Counter(yo[keep].tolist()).most_common(1)[0][0]
        heur = np.array(
            [
                6
                if (h := res[_key(r["text"])]["cefr"]["estimated_level_95th"]) is None
                else LEVELS.index(h) + 1
                for r, k in zip(by_ds[name], keep, strict=True)
                if k
            ]
        )
        rows_k = [r for r, k in zip(by_ds[name], keep, strict=True) if k]
        misuse[name] = {
            "what": what,
            "model": metrics(yo[keep], po, Po, wo[keep]),
            "cvla_published": short(metrics(yo[keep], cvla_of(rows_k)[0])),
            "baseline_always_modal_level": {
                "predicts": LEVELS[mode - 1],
                **short(metrics(yo[keep], np.full_like(yo[keep], mode))),
            },
            "estimated_level_95th": short(metrics(yo[keep], heur)),
        }
        if name == "ace_cefr":
            misuse[name]["note"] = (
                "Only a handful of Ace-CEFR passages reach 50 words, and none reaches the "
                f"{MIN_WORDS}-word floor, so the shipped estimator would answer none of them; "
                "the figures are the raw model, for completeness only."
            )
            keep20 = wo >= 20
            P20 = final.proba(Xo[keep20])
            misuse[name]["model_20_plus_words_for_context"] = short(
                metrics(yo[keep20], P20.argmax(1) + 1, P20)
            )

    # Baselines on the training texts, for context.
    mode = Counter(y[app].tolist()).most_common(1)[0][0]
    heur = np.array(
        [
            6
            if (h := res[_key(r["text"])]["cefr"]["estimated_level_95th"]) is None
            else LEVELS.index(h) + 1
            for r in train_rows
        ]
    )
    baselines = {
        "always_modal_level": {
            "predicts": LEVELS[mode - 1],
            **short(metrics(y[app], np.full_like(y[app], mode))),
        },
        "estimated_level_95th_null_as_C2": short(metrics(y[app], heur[app])),
        "estimated_level_95th_by_dataset": {
            d: short(metrics(y[app & (ds_of == d)], heur[app & (ds_of == d)])) for d in TRAIN
        },
        "note": "estimated_level_95th is not fitted to these texts, so its figures are "
        "out-of-sample; compare it with the leave-one-dataset-out figures as well as CV.",
    }

    ev = evals[chosen]
    cv_w1 = ev["cv_applicable"]["within_one"]
    lodo_w1 = {k: v["applicable"]["within_one"] for k, v in ev["leave_one_dataset_out"].items()}
    ship = cv_w1 >= 0.85 and min(lodo_w1.values()) >= 0.80
    decision = {
        "rule": "Don't ship if cross-validated within-one accuracy is below 85% or either "
        "leave-one-dataset-out within-one accuracy is below 80% (texts of 100+ words).",
        "cv_within_one": cv_w1,
        "leave_one_dataset_out_within_one": lodo_w1,
        "passes": ship,
    }

    cvm = ev["cv_applicable"]
    worst_lodo = min(lodo_w1.values())
    summary = {
        "held_out_within_one": cvm["within_one"],
        "held_out_exact": cvm["exact"],
        "held_out_qwk": cvm["qwk"],
        "range_contains_true_level": cvm["range_80"]["gold_inside"],
        "cross_dataset_within_one_worst": worst_lodo,
        "n_texts": cvm["n"],
        "text": (
            f"Tested on {cvm['n']} exam and graded reading passages it hadn't seen "
            f"(5-fold cross-validation), the estimate was within one level of the "
            f"published level {cvm['within_one']:.0%} of the time and exactly right "
            f"{cvm['exact']:.0%} of the time; the shown range contained the published "
            f"level {cvm['range_80']['gold_inside']:.0%} of the time. Trained on one "
            f"collection and tested on the other, within-one accuracy was "
            f"{worst_lodo:.0%} at worst. It is for reading texts, not for grading writing."
        ),
    }

    feats_out = []
    for i, f in enumerate(names):
        label, unit, _ = level.FEATURES[f]
        feats_out.append(
            {
                "name": f,
                "label": label,
                "unit": unit,
                "mean": round(float(final.mean[i]), 6),
                "sd": round(float(final.sd[i]), 6),
                "median": round(float(final.median[i]), 6),
                "weight": round(float(final.w[i]), 6),
                "sign_constraint": "free" if signs[i] == 0 else ">= 0",
            }
        )

    n_per_level = {
        d: {lv: int(sum(1 for r in by_ds[d] if r["level"] == i + 1)) for i, lv in enumerate(LEVELS)}
        for d in TRAIN
    }
    versions = {}
    for pkg in ("numpy", "scipy", "scikit-learn"):
        with contextlib.suppress(md.PackageNotFoundError):
            versions[pkg] = md.version(pkg)

    citations = {
        "cambridge_exams": "Xia, M., Kochmar, E., & Briscoe, T. (2016). Text readability "
        "assessment for second language learners. Proceedings of the 11th Workshop on "
        "Innovative Use of NLP for Building Educational Applications (BEA), 12-22. "
        "Distributed via UniversalCEFR (Imperial et al. 2025, arXiv:2506.01419).",
        "elg_cefr_en": "Breuker, M. (2023). CEFR labelling and assessment services. In G. "
        "Rehm (Ed.), European Language Grid (pp. 277-282). Springer. "
        "doi:10.1007/978-3-031-17258-8_16. Distributed via UniversalCEFR (Imperial et al. "
        "2025, arXiv:2506.01419).",
    }
    out = {
        "schema_version": 1,
        "licence": "CC BY-NC-SA 4.0 (derived from the training datasets listed in "
        "metadata.training_data)",
        "model": "proportional-odds (cumulative logit) regression: "
        "P(level <= k) = sigmoid(theta_k - sum_j weight_j * clip((x_j - mean_j) / sd_j, "
        "-z_clip, z_clip)); a missing x_j takes the training median.",
        "levels": LEVELS,
        "thresholds": [round(float(t), 6) for t in final.theta],
        "min_words": MIN_WORDS,
        "z_clip": Z_CLIP,
        "features": feats_out,
        "caveat": (
            "An estimate of the CEFR level of a reading text (material written or chosen for "
            "learners), learned from Cambridge exam passages and ELG-CEFR-EN graded texts. "
            "It describes the text, not a writer's proficiency: do not use it to grade "
            "learner writing, where it does no better than always answering B2. Not "
            "applicable under 100 words."
        ),
        "summary_for_users": summary,
        "evaluation": {
            "chosen_config": chosen,
            "choice_rule": "The sign-constrained feature set with the higher cross-validated QWK "
            "on texts of 100+ words (sign constraints fixed in advance, for readable "
            "contributions). Only sets computable from run_all's results were eligible; the "
            "CVLA-index sets need the parsed Analysis and are reported for comparison.",
            "decision": decision,
            "configs": evals,
            "baselines_on_training_texts_100_plus_words": baselines,
            "not_for_these_uses": misuse,
            "cvla_published": cvla_eval,
            "ensemble_ordinal_plus_cvla": ens_eval,
            "final_model_l2_alpha": final.alpha,
            "final_model_converged": final.converged,
            "method": (
                f"Stratified {N_FOLDS}-fold CV (seed {SEED}) on the pooled reading texts; "
                "within each training fold the L2 penalty is chosen from "
                f"{list(ALPHAS)} by inner 3-fold CV on QWK, and the imputation medians, "
                "means and SDs are fitted on the training fold only. Leave-one-dataset-out "
                "fits on one collection and tests on the other; a model fitted on one "
                "collection can only predict the levels it saw. 'applicable' = texts of "
                f"{MIN_WORDS}+ lexinspect words, the floor below which the estimator "
                "declines. range_80 is the shortest run of adjacent levels holding 80% of "
                "the probability. Length is lexinspect's readability word count."
            ),
        },
        "metadata": {
            "built": dt.date.today().isoformat(),
            "lexinspect_version": __version__,
            "provenance": provenance(),
            "training_packages": versions,
            "training_data": {
                d: {
                    "citation": citations[d],
                    "source": s5.DATASETS[d]["source"],
                    "licence": s5.DATASETS[d]["licence"],
                    "revision": s5.DATASETS[d].get("rev"),
                    "sha256": s5.DATASETS[d]["sha256"],
                    "n": len(by_ds[d]),
                    "n_per_level": n_per_level[d],
                }
                for d in TRAIN
            },
            "training_n": len(train_rows),
            "training_note": (
                f"ELG-CEFR-EN minus the {s5.ELG_OVERLAP.get('removed')} passages it shares "
                "with the Cambridge exams set (as in Study 5). ELG has no C2 texts and "
                "Cambridge no A1 texts, so A1 rests on ELG alone and C2 on Cambridge alone."
            ),
            "licence_note": (
                "The coefficients, thresholds and standardisation figures in this file are "
                "derived from datasets licensed CC BY-NC 4.0 and CC BY-NC-SA 4.0 (Xia, "
                "Kochmar & Briscoe 2016; Breuker 2023; both via UniversalCEFR), and the "
                "Cambridge readability data's own terms limit information derived from it "
                "to non-commercial research and education. This file is therefore treated "
                "as an adaptation and licensed CC BY-NC-SA 4.0. No text from the datasets "
                "is included. The estimate is offered in free, non-commercial lexinspect; "
                "the MIT licence of lexinspect's code does not extend to this file."
            ),
            "open_alternative_checked": (
                "No openly licensed (CC BY / CC BY-SA / CC0) CEFR-labelled set of reading "
                "passages of comparable size was found: OneStopEnglish (CC BY-SA 4.0) has "
                "three non-CEFR levels; Ace-CEFR (CC0) is short conversational text "
                "(median 10 words); CLEAR is CC BY-NC-SA and US-grade based."
            ),
            "cvla_reference": "Uchida, S., & Negishi, M. (2018). Assigning CEFR-J levels to "
            "English texts based on textual features. Proceedings of the 4th Asia Pacific "
            "Corpus Linguistics Conference, 463-467. hdl:2324/2244112",
            "build_command": "uv run --with numpy --with scipy --with scikit-learn "
            "python scripts/build_data/build_level_model.py",
        },
    }
    print(json.dumps({"chosen": chosen, "decision": decision, "summary": summary}, indent=1))
    args.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
