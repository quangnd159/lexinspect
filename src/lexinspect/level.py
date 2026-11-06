"""Estimated CEFR level of a reading text, from the other modules' results.

`estimate(results)` takes the dict that `pipeline.run_all` returns (it needs
`readability`, `diversity`, `awl`, `bnc_coca`, `ngsl`, `phrase` and `cefr`)
and applies a proportional-odds (ordinal logistic) model whose coefficients
live in `data/level_model.json`:

    z_j   = clip((x_j - mean_j) / sd_j, +-z_clip)    (missing x_j -> training median)
    eta   = sum_j w_j * z_j
    P(level <= k) = sigmoid(theta_k - eta)      k = A1 .. C1

The model was fitted by `scripts/build_data/build_level_model.py` on exam and
graded reading passages (Cambridge English exams and ELG-CEFR-EN), with every
slope constrained to the direction a teacher would expect (more words above
B1 can only push the level up, and so on), so the listed contributions read
sensibly. Its held-out accuracy ships in the same JSON and is returned with
every estimate.

It describes reading material written or chosen for learners. It is not a
measure of a writer's proficiency and must not be used to grade learner
writing: on learner essays it does no better than always answering B2.

Pure standard library: this runs inside the size-limited serverless bundle.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
MODEL_PATH = Path(__file__).parent / "data" / "level_model.json"
REQUIRED_MODULES = ("readability", "diversity", "awl", "bnc_coca", "ngsl", "phrase", "cefr")
RANGE_MASS = 0.8

Results = dict[str, Any]


# --- features ----------------------------------------------------------------------
#
# Every feature is a share or an average that doesn't grow with text length.
# Raw length is left out on purpose: in the training corpora longer passages
# are higher-level passages, and a model would learn that instead of difficulty.


def _pct_of(n: float, total: float) -> float | None:
    return n / total * 100 if total else None


def _cefr_above(level: str) -> Callable[[Results], float | None]:
    """Share of words above `level` on the CEFR-J/Octanove lists, off-list
    words included, proper nouns left out of the count."""

    def f(r: Results) -> float | None:
        c = r["cefr"]
        n = c["counts"]["content_tokens"]
        if not n:
            return None
        proper = c["counts"]["proper_noun_tokens"] / n * 100
        return max(0.0, 100.0 - c["per_level"][level]["cumulative_coverage_pct"] - proper)

    return f


def _beyond_band(module: str, band: str) -> Callable[[Results], float | None]:
    """Share of words beyond the first `band` thousand BNC/COCA families, with
    proper nouns and the supplementary lists counted as known."""

    def f(r: Results) -> float | None:
        prof = r["phrase"]["integrated_profile"] if module == "phrase" else r["bnc_coca"]
        if not prof["counts"]["content_tokens"]:
            return None
        cum = prof["per_band"][band]["cumulative_coverage_with_supplementary_pct"]
        return max(0.0, 100.0 - cum)

    return f


def _get(*path: str) -> Callable[[Results], float | None]:
    def f(r: Results) -> float | None:
        v: Any = r
        for p in path:
            if not isinstance(v, dict) or p not in v:
                return None
            v = v[p]
        return None if v is None else float(v)

    return f


def _readability_share(key: str) -> Callable[[Results], float | None]:
    def f(r: Results) -> float | None:
        c = r["readability"]["counts"]
        return _pct_of(c[key], c["words"])

    return f


def _cefr_proper(r: Results) -> float | None:
    c = r["cefr"]["counts"]
    return _pct_of(c["proper_noun_tokens"], c["content_tokens"])


def _cefr_off(r: Results) -> float | None:
    c = r["cefr"]["counts"]
    return _pct_of(c["off_list_tokens"], c["content_tokens"])


def _bnc_off(r: Results) -> float | None:
    c = r["bnc_coca"]["counts"]
    return _pct_of(c["off_list_tokens"], c["content_tokens"])


def _not(f: Callable[[Results], float | None]) -> Callable[[Results], float | None]:
    def g(r: Results) -> float | None:
        v = f(r)
        return None if v is None else 100.0 - v

    return g


_K = {"1": "1,000", "2": "2,000", "3": "3,000", "4": "4,000", "5": "5,000", "10": "10,000"}

# name -> (plain-words label, unit, extractor). The model file lists which of
# these it uses; a name in the file that isn't here is a build error.
FEATURES: dict[str, tuple[str, str, Callable[[Results], float | None]]] = {
    **{
        f"cefr_above_{lv}_pct": (
            f"share of words above {lv} (CEFR-J/Octanove)",
            "%",
            _cefr_above(lv),
        )
        for lv in LEVELS[:5]
    },
    "cefr_off_list_pct": ("share of words beyond the C2 lists", "%", _cefr_off),
    "cefr_proper_noun_pct": ("share of proper nouns", "%", _cefr_proper),
    **{
        f"bnc_beyond_{k}k_pct": (
            f"share of words beyond the {_K[k]} most frequent word families (BNC/COCA)",
            "%",
            _beyond_band("bnc_coca", k),
        )
        for k in ("1", "2", "3", "4", "5", "10")
    },
    "bnc_off_list_pct": ("share of words on no BNC/COCA list", "%", _bnc_off),
    **{
        f"phrase_beyond_{k}k_pct": (
            f"share of words beyond the {_K[k]} band, counting phrasal expressions (PHRASE)",
            "%",
            _beyond_band("phrase", k),
        )
        for k in ("1", "2", "3", "4", "5", "10")
    },
    "words_per_sentence": (
        "average sentence length",
        "words",
        _get("readability", "averages", "words_per_sentence"),
    ),
    "syllables_per_word": (
        "average word length in syllables",
        "syllables",
        _get("readability", "averages", "syllables_per_word"),
    ),
    "characters_per_word": (
        "average word length in letters",
        "letters",
        _get("readability", "averages", "characters_per_word"),
    ),
    "polysyllable_pct": (
        "share of words with three or more syllables",
        "%",
        _readability_share("polysyllable_words"),
    ),
    "dale_chall_difficult_pct": (
        "share of words not on the Dale-Chall easy-word list",
        "%",
        _readability_share("difficult_words"),
    ),
    "mtld": ("vocabulary variety (MTLD)", "", _get("diversity", "scores", "mtld")),
    "mattr": ("vocabulary variety (MATTR)", "", _get("diversity", "scores", "mattr")),
    "awl_pct": ("share of Academic Word List words", "%", _get("awl", "coverage_pct")),
    "outside_ngsl_pct": (
        "share of words outside the New General Service List",
        "%",
        _not(_get("ngsl", "coverage_pct", "ngsl")),
    ),
    "outside_ngsl_nawl_pct": (
        "share of words outside the NGSL and New Academic Word List",
        "%",
        _not(_get("ngsl", "coverage_pct", "ngsl_plus_nawl")),
    ),
    "ngsl_off_list_pct": (
        "share of words on neither the NGSL nor the NAWL (names excluded)",
        "%",
        _get("ngsl", "coverage_pct", "off_list"),
    ),
}


def features(results: Results) -> dict[str, float | None]:
    """Every feature in `FEATURES`, computed from run_all's results. None means
    the module couldn't compute it (MTLD and MATTR under about 50 tokens)."""
    out: dict[str, float | None] = {}
    for name, (_, _, f) in FEATURES.items():
        try:
            v = f(results)
        except (KeyError, TypeError, ZeroDivisionError):
            v = None
        out[name] = None if v is None or not math.isfinite(v) else float(v)
    return out


def word_count(results: Results) -> int:
    return int(results["readability"]["counts"]["words"])


# --- model ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def model() -> dict[str, Any]:
    m = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    unknown = [f["name"] for f in m["features"] if f["name"] not in FEATURES]
    if unknown:
        raise ValueError(f"level_model.json uses unknown features: {unknown}")
    if len(m["thresholds"]) != len(m["levels"]) - 1:
        raise ValueError("level_model.json: need one threshold fewer than levels")
    return m


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def probabilities(feats: dict[str, float | None], m: dict[str, Any] | None = None):
    """Per-level probabilities and per-feature contributions to the linear
    predictor (positive pushes towards a higher level)."""
    m = m or model()
    clip = m["z_clip"]
    contrib: dict[str, float] = {}
    eta = 0.0
    for f in m["features"]:
        x = feats.get(f["name"])
        if x is None:
            x = f["median"]
        z = (x - f["mean"]) / f["sd"] if f["sd"] else 0.0
        c = f["weight"] * max(-clip, min(clip, z))
        contrib[f["name"]] = c
        eta += c
    cum = [_sigmoid(t - eta) for t in m["thresholds"]] + [1.0]
    probs, prev = [], 0.0
    for c in cum:
        probs.append(max(0.0, c - prev))
        prev = c
    s = sum(probs)
    probs = [p / s for p in probs]
    return dict(zip(m["levels"], probs, strict=True)), contrib, eta


def level_range(probs: dict[str, float], mass: float = RANGE_MASS) -> list[str]:
    """The shortest run of adjacent levels whose probabilities sum to at least
    `mass`; ties go to the run with more probability."""
    levels = list(probs)
    p = [probs[lv] for lv in levels]
    for width in range(1, len(p) + 1):
        best, best_s = None, -1.0
        for i in range(len(p) - width + 1):
            s = sum(p[i : i + width])
            if s >= mass - 1e-12 and s > best_s:
                best, best_s = i, s
        if best is not None:
            return levels[best : best + width]
    return levels


def _extrapolated(feats: dict[str, float | None], m: dict[str, Any]) -> list[str]:
    """Names of the features (with a non-zero weight) beyond the clip, i.e.
    more extreme than nearly every training text."""
    out = []
    for f in m["features"]:
        x = feats.get(f["name"])
        if x is not None and f["weight"] and f["sd"] and abs(x - f["mean"]) > m["z_clip"] * f["sd"]:
            out.append(f["name"])
    return out


def _confidence(probs: dict[str, float], rng: list[str], beyond: list[str]) -> dict[str, Any]:
    top = max(probs.values())
    if len(rng) == 1:
        label, text = "high", f"Most of the probability ({top:.0%}) is on one level."
    elif len(rng) == 2:
        label, text = "moderate", "The text sits between two adjacent levels."
    else:
        label, text = (
            "low",
            f"The probability is spread over {len(rng)} levels; treat the level as a rough guide.",
        )
    if beyond:
        text += (
            " The text is more extreme than almost every training passage on: "
            + "; ".join(FEATURES[n][0] for n in beyond)
            + ". The estimate there is an extrapolation."
        )
    return {
        "label": label,
        "top_probability": round(top, 3),
        "description": text,
        "beyond_training_range": [FEATURES[n][0] for n in beyond],
        "beyond_training_features": beyond,
    }


def _explain(
    feats: dict[str, float | None], contrib: dict[str, float], m: dict[str, Any], k: int = 3
) -> list[dict[str, Any]]:
    spec = {f["name"]: f for f in m["features"]}
    ranked = sorted((n for n in contrib if contrib[n] != 0.0), key=lambda n: (-abs(contrib[n]), n))[
        :k
    ]
    out = []
    for n in ranked:
        f = spec[n]
        label, unit, _ = FEATURES[n]
        x = feats.get(n)
        typical = f["mean"]
        # The slopes are sign-constrained, so a push up always means "more than
        # in a typical training text" for features where more = harder.
        high = (x if x is not None else f["median"]) > typical
        direction = "up" if contrib[n] > 0 else "down"
        unit_s = "%" if unit == "%" else (f" {unit}" if unit else "")
        val = "missing (training median used)" if x is None else f"{x:.1f}{unit_s}"
        out.append(
            {
                "feature": n,
                "label": label,
                "value": None if x is None else round(x, 3),
                "typical": round(typical, 3),
                "effect": round(contrib[n], 3),
                "direction": direction,
                "text": (
                    f"{label[0].upper()}{label[1:]} is {'high' if high else 'low'} "
                    f"({val}; typical training text {typical:.1f}{unit_s}), "
                    f"which {'raises' if direction == 'up' else 'lowers'} the estimate."
                ),
            }
        )
    return out


# --- CVLA (Uchida & Negishi 2018), as published -------------------------------------
#
# Uchida, S. & Negishi, M. (2018). Assigning CEFR-J levels to English texts
# based on textual features. Proceedings of the 4th Asia Pacific Corpus
# Linguistics Conference, 463-467. hdl:2324/2244112. Reading-mode regressions
# (section 3.5), fitted on A1-B2 coursebooks with A1=1, A2=2, B1=3, B2=4:
CVLA_READING = {
    "ari": (0.4298, -1.27085),
    "verbs_per_sentence": (2.1075, -2.01),
    "avr_diff": (7.2961, -8.4442),
    "b_per_a": (16.3043, -0.1087),
}
# Upper bounds of the 12 CEFR-J levels on that scale; the final level is the
# mean of the four estimates. Above 6 the paper gives no level: C2.
CVLA_BANDS = [
    (0.5, "Pre-A1"),
    (0.84, "A1.1"),
    (1.17, "A1.2"),
    (1.5, "A1.3"),
    (2.0, "A2.1"),
    (2.5, "A2.2"),
    (3.0, "B1.1"),
    (3.5, "B1.2"),
    (4.0, "B2.1"),
    (4.5, "B2.2"),
    (5.0, "C1"),
    (math.inf, "C2"),
]
_CVLA_CONTENT_UPOS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})
_CVLA_LEVEL_NUM = {"A1": 1, "A2": 2, "B1": 3, "B2": 4}


def cvla_label(score: float) -> tuple[str, str]:
    """(CEFR-J level, CEFR level) for a CVLA score."""
    fine = next(lab for ub, lab in CVLA_BANDS if score < ub)
    coarse = "A1" if fine == "Pre-A1" else fine[:2]
    return fine, coarse


def cvla_indices(analysis: Any, ari: float) -> dict[str, float | None]:
    """CVLA's four indices from a lexinspect `Analysis` (and its ARI).

    Our reading of the paper's definitions, with lexinspect's tools in place of
    TreeTagger and CEFR-J 1.3:
    - verbs_per_sentence: tokens tagged VB* (auxiliaries included, as in the
      paper's "was written" example; modals, MD, not counted) per sentence;
    - avr_diff: mean CEFR-J level (A1=1 ... B2=4) of the content words
      (nouns, verbs, adjectives, adverbs; proper nouns and auxiliaries out)
      that CEFR-J 1.5 lists at A1-B2 (C1/C2 and unlisted words are ignored);
    - b_per_a: B-level content words / A-level content words.
    """
    from lexinspect import _lists
    from lexinspect._text import lookup

    n_sent = analysis.sentence_count
    verbs = sum(1 for t in analysis.doc if t.tag_.startswith("VB"))
    entries = _lists.cefr_entries()
    levels: list[int] = []
    for lex in analysis.lexical:
        if lex.pos not in _CVLA_CONTENT_UPOS or lex.is_proper:
            continue
        _, entry = lookup(entries, lex.keys)
        if entry is None:
            continue
        lv, _ = _lists.cefr_level(entry, lex.pos)
        if lv in _CVLA_LEVEL_NUM:
            levels.append(_CVLA_LEVEL_NUM[lv])
    n_a = sum(1 for v in levels if v <= 2)
    n_b = len(levels) - n_a
    return {
        "ari": float(ari),
        "verbs_per_sentence": verbs / n_sent if n_sent else None,
        "avr_diff": sum(levels) / len(levels) if levels else None,
        "b_per_a": n_b / n_a if n_a else None,
    }


def cvla(indices: dict[str, float | None]) -> dict[str, Any]:
    """CVLA's published Reading-mode estimate from its four indices."""
    per: dict[str, Any] = {}
    scores = []
    for name, (slope, icpt) in CVLA_READING.items():
        x = indices.get(name)
        if x is None:
            per[name] = {"value": None, "score": None, "level": None}
            continue
        s = slope * x + icpt
        scores.append(s)
        per[name] = {"value": round(x, 4), "score": round(s, 4), "level": cvla_label(s)[0]}
    if not scores:
        return {"score": None, "cefr_j_level": None, "level": None, "indices": per}
    final = sum(scores) / len(scores)
    fine, coarse = cvla_label(final)
    return {"score": round(final, 4), "cefr_j_level": fine, "level": coarse, "indices": per}


# Fewest different word forms a text needs before the estimate applies.
MIN_TYPES = 40


def estimate(results: Results) -> dict[str, Any]:
    """Estimated CEFR level of a reading text, from run_all's results."""
    m = model()
    base: dict[str, Any] = {
        "applicable": False,
        "reason": None,
        "level": None,
        "range": None,
        "probabilities": None,
        "confidence": None,
        "contributions": [],
        "evaluation": m["summary_for_users"],
        "caveat": m["caveat"],
    }
    missing = [mod for mod in REQUIRED_MODULES if not isinstance(results.get(mod), dict)]
    if missing:
        base["reason"] = f"Needs the results of: {', '.join(missing)}."
        return base
    words = word_count(results)
    floor = m["min_words"]
    if words < floor:
        base["reason"] = (
            f"The text has {words} word{'' if words == 1 else 's'}; the level estimate needs "
            f"at least {floor}. On short texts one or two words decide the level."
        )
        return base
    # Word count alone lets through lists of numbers or one word repeated, which
    # look nothing like a reading text: require words the lists can rate, and variety.
    lexical = int(results["cefr"]["counts"]["content_tokens"])
    types = int((results["diversity"].get("counts") or {}).get("types", 0))
    if lexical < floor or types < MIN_TYPES:
        base["reason"] = (
            "The text has too few distinct words to compare with reading texts: "
            f"{lexical} rated words and {types} different word forms (the estimate needs "
            f"{floor} and {MIN_TYPES})."
        )
        return base
    feats = features(results)
    probs, contrib, _ = probabilities(feats, m)
    lv = max(probs, key=lambda k: (probs[k], -LEVELS.index(k)))
    rng = level_range(probs)
    return {
        **base,
        "applicable": True,
        "level": lv,
        "range": rng,
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "confidence": _confidence(probs, rng, _extrapolated(feats, m)),
        "contributions": _explain(feats, contrib, m),
    }
