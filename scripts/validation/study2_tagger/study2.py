"""Study 2: tagger accuracy on learner English, and its effect on what lexinspect reports.

Run through `run.sh` (it supplies en_core_web_trf with `uv run --with`):

    bash scripts/validation/study2_tagger/run.sh

Steps:

1. Download two Universal Dependencies treebanks at a pinned release into
   `.cache/validation/study2/` (gitignored), if absent:
   - UD_English-ESLSpok (learner English, spoken; CC BY-SA 4.0), all splits.
   - UD_English-EWT test split (edited web text; CC BY-SA 4.0), the baseline.
   The Treebank of Learner English (UD_English-ESL) is not used: its text
   needs the Cambridge FCE dataset, which needs a registration form and a
   non-commercial licence that forbids releasing statistics derived from it
   without Cambridge's prior approval.
2. Cut each treebank into texts of at least 150 words (consecutive whole
   sentences) and build a spaCy Doc from the *gold* tokens for each text, so
   tokenisation is identical in every condition and only tagging differs.
3. Tag each Doc with en_core_web_sm and en_core_web_trf through lexinspect's own
   pipeline loader (`lexinspect._nlp.get_nlp`, NER excluded), and build a third
   "gold" Doc: gold XPOS + gold UPOS, lemmas from spaCy's rule lemmatiser
   applied to the gold tags (ESLSpok has no gold lemmas); on EWT, also a
   variant with EWT's gold lemmas.
4. Score UPOS / XPOS / lemma accuracy against gold.
5. Build lexinspect `Analysis` objects from each Doc and run lexinspect's own
   lookups per lexical token (CEFR level, BNC/COCA band, NGSL/NAWL, AWL,
   proper-noun status) and its own module `analyze()` functions per text, and
   compare conditions.
6. Time both models on raw text through lexinspect's pipeline, measure installed
   size, and write `docs/validation/study2-tagger.json`.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

import spacy
from spacy.tokens import Doc

from lexinspect import _lists, awl, bnc_coca, cefr, ngsl
from lexinspect._nlp import get_nlp
from lexinspect._schema import provenance
from lexinspect._text import Analysis, _group_sentences, _group_words, lookup

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / ".cache" / "validation" / "study2"
OUT_JSON = REPO / "docs" / "validation" / "study2-tagger.json"

UD_RELEASE = "r2.18"
DATASETS = {
    "learner_eslspok": {
        "repo": "UD_English-ESLSpok",
        "files": [f"en_eslspok-ud-{s}.conllu" for s in ("train", "dev", "test")],
        "licence": "CC BY-SA 4.0",
        "description": "UD_English-ESLSpok (Kyle et al. 2022): spoken L2 English, "
        "Japanese learners, NICT JLE interviews; all splits",
    },
    "baseline_ewt": {
        "repo": "UD_English-EWT",
        "files": ["en_ewt-ud-test.conllu"],
        "licence": "CC BY-SA 4.0",
        "description": "UD_English-EWT test split (Silveira et al. 2014): edited English web text",
    },
}
MODELS = {"sm": "en_core_web_sm", "trf": "en_core_web_trf"}
MIN_TEXT_WORDS = 150
BOOTSTRAP = 1000
SEED = 20261016
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

_CLITICS = {"'s", "n't", "'m", "'ll", "'re", "'d", "'ve", "'", "s'"}
_NO_SPACE_BEFORE = {".", ",", "?", "!", ";", ":", ")", "]", "%", "..."}
_NO_SPACE_AFTER = {"(", "["}


# --- data -------------------------------------------------------------------------


def fetch() -> dict[str, list[dict]]:
    """Download the treebanks if absent; return per-dataset file provenance."""
    info: dict[str, list[dict]] = {}
    for name, ds in DATASETS.items():
        d = CACHE / ds["repo"]
        d.mkdir(parents=True, exist_ok=True)
        info[name] = []
        for f in ds["files"]:
            path = d / f
            url = (
                f"https://raw.githubusercontent.com/UniversalDependencies/{ds['repo']}/"
                f"{UD_RELEASE}/{f}"
            )
            if not path.exists():
                print(f"downloading {url}", file=sys.stderr)
                tmp = path.with_suffix(".part")
                urllib.request.urlretrieve(url, tmp)
                tmp.rename(path)
            info[name].append(
                {"file": f, "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    return info


@dataclass
class Tok:
    form: str
    upos: str
    xpos: str
    lemma: str | None
    space: bool = True


@dataclass
class Sent:
    sid: str
    toks: list[Tok] = field(default_factory=list)


def read_conllu(path: Path, detokenise: bool) -> list[Sent]:
    sents: list[Sent] = []
    cur: Sent | None = None
    mwt_end = -1
    mwt_space = True
    for line in path.read_text("utf-8").splitlines():
        if line.startswith("# sent_id"):
            cur = Sent(line.split("=", 1)[1].strip())
            continue
        if not line.strip():
            if cur and cur.toks:
                sents.append(cur)
            cur = None
            mwt_end = -1  # multiword-token ranges never cross sentences
            continue
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if "." in cols[0]:
            continue  # empty node
        misc = cols[9]
        if "-" in cols[0]:
            a, b = cols[0].split("-")
            mwt_end = int(b)
            mwt_space = "SpaceAfter=No" not in misc
            continue
        idx = int(cols[0])
        if idx < mwt_end:
            space = False
        elif idx == mwt_end:
            space = mwt_space
        else:
            space = "SpaceAfter=No" not in misc
        lemma = None if cols[2] == "_" and cols[1] != "_" else cols[2]
        cur.toks.append(Tok(cols[1], cols[3], cols[4], lemma, space))
    if cur and cur.toks:
        sents.append(cur)
    if detokenise:
        for s in sents:
            _detokenise(s.toks)
    return sents


def _alnum(s: str) -> bool:
    return any(c.isalnum() for c in s)


def _detokenise(toks: list[Tok]) -> None:
    """ESLSpok gives only space-separated tokens. Restore the spacing a writer
    would use, which only affects lexinspect's grouping of tokens into words
    (`do n't` -> `don't`, `part - time` -> `part-time`), never the tags."""
    for t in toks:
        t.space = True
    for k, t in enumerate(toks):
        low = t.form.lower()
        if k > 0 and (low in _CLITICS or t.form in _NO_SPACE_BEFORE):
            toks[k - 1].space = False
        if t.form in _NO_SPACE_AFTER:
            t.space = False
        if (
            t.form == "-"
            and 0 < k < len(toks) - 1
            and _alnum(toks[k - 1].form)
            and _alnum(toks[k + 1].form)
        ):
            toks[k - 1].space = False
            t.space = False
    toks[-1].space = True


def chunk(sents: list[Sent]) -> list[list[Sent]]:
    """Consecutive whole sentences, at least MIN_TEXT_WORDS non-punctuation tokens each."""
    texts: list[list[Sent]] = []
    cur: list[Sent] = []
    n = 0
    for s in sents:
        cur.append(s)
        n += sum(t.upos != "PUNCT" for t in s.toks)
        if n >= MIN_TEXT_WORDS:
            texts.append(cur)
            cur, n = [], 0
    if cur:
        if texts and n < MIN_TEXT_WORDS / 2:
            texts[-1].extend(cur)
        else:
            texts.append(cur)
    return texts


def load_dataset(name: str) -> list[list[Sent]]:
    ds = DATASETS[name]
    sents: list[Sent] = []
    for f in ds["files"]:
        sents.extend(read_conllu(CACHE / ds["repo"] / f, detokenise=name == "learner_eslspok"))
    if name == "learner_eslspok":
        # Splits are random samples; regroup by interview file so a text holds
        # one speaker's sentences where possible. sent_id = fileNNNNN.txt_K.
        def key(s: Sent):
            f, _, k = s.sid.rpartition("_")
            return (f, int(k))

        sents.sort(key=key)
    return chunk(sents)


# --- docs -------------------------------------------------------------------------


def gold_tokens(text: list[Sent]) -> tuple[list[Tok], list[bool]]:
    toks: list[Tok] = []
    starts: list[bool] = []
    for s in text:
        for k, t in enumerate(s.toks):
            toks.append(t)
            starts.append(k == 0)
    return toks, starts


def blank_doc(nlp, toks: list[Tok], starts: list[bool]) -> Doc:
    return Doc(
        nlp.vocab,
        words=[t.form for t in toks],
        spaces=[t.space for t in toks],
        sent_starts=starts,
    )


def tag_with(nlp, toks, starts) -> Doc:
    return nlp(blank_doc(nlp, toks, starts))


def gold_doc(nlp_sm, toks, starts, gold_lemmas: bool) -> Doc:
    """Gold XPOS and UPOS; morphology from spaCy's tag map applied to the gold
    XPOS; lemmas from spaCy's rule lemmatiser over the gold tags, or the
    treebank's own lemmas when `gold_lemmas`."""
    doc = blank_doc(nlp_sm, toks, starts)
    for tok, g in zip(doc, toks, strict=False):
        tok.tag_ = g.xpos
    doc = nlp_sm.get_pipe("attribute_ruler")(doc)
    for tok, g in zip(doc, toks, strict=False):
        tok.pos_ = g.upos
    doc = nlp_sm.get_pipe("lemmatizer")(doc)
    if gold_lemmas:
        for tok, g in zip(doc, toks, strict=False):
            if g.lemma is not None:
                tok.lemma_ = g.lemma
    return doc


def analysis_of(doc: Doc) -> Analysis:
    """lexinspect's `analyse()` minus the parse: same word and sentence grouping."""
    words = _group_words(doc)
    return Analysis(text=doc.text, doc=doc, words=words, sentences=_group_sentences(doc, words))


# --- lexinspect lookups -----------------------------------------------------------


def token_outcomes(a: Analysis) -> list[dict]:
    """Per lexical token, what each lexinspect profile reports. Mirrors the loop
    bodies of cefr.analyze, bnc_coca.analyze, ngsl.analyze and awl.analyze using
    the same lookup functions and tables (checked against them in `check_counts`)."""
    entries = _lists.cefr_entries()
    ngsl_f, nawl_f, awl_f = _lists.ngsl_forms(), _lists.nawl_forms(), _lists.awl_forms()
    out = []
    for lex in a.lexical:
        _k, entry = lookup(entries, lex.keys)
        if entry is None:
            c = "PROPER" if lex.is_proper else "OFF"
            pos_match = None
        else:
            c, pos_match = _lists.cefr_level(entry, lex.pos)
        kind, value = bnc_coca.classify(lex)
        if kind == "band":
            b = f"{value.band}k"
        else:
            b = f"supp:{value}" if kind == "supplementary" else kind
        _k, item = lookup(ngsl_f, lex.keys)
        if item is not None:
            n = "NGSL"
        else:
            _k, item = lookup(nawl_f, lex.keys)
            n = "NAWL" if item is not None else ("proper" if lex.is_proper else "off")
        _k, fam = lookup(awl_f, lex.keys)
        out.append(
            {
                "i": lex.i,
                "surface": lex.surface,
                "lemma": lex.lemma,
                "tag": lex.tag,
                "pos": lex.pos,
                "proper": lex.is_proper,
                "cefr": c,
                "cefr_pos_match": pos_match,
                "bnc": b,
                "ngsl": n,
                "awl": f"AWL{fam['sublist']}" if fam is not None else "-",
            }
        )
    return out


def text_measures(a: Analysis) -> dict:
    """What lexinspect reports for the text, from its own module functions."""
    c = cefr.analyze(a.text, analysis=a)
    b = bnc_coca.analyze(a.text, analysis=a)
    n = ngsl.analyze(a.text, analysis=a)
    w = awl.analyze(a.text, analysis=a)
    nt = c["counts"]["content_tokens"]

    def pct(x):
        return x / nt * 100 if nt else 0.0

    m = {f"cefr_{lv}": c["per_level"][lv]["coverage_pct"] for lv in CEFR_LEVELS}
    m["cefr_proper"] = pct(c["counts"]["proper_noun_tokens"])
    m["cefr_off_list"] = pct(c["counts"]["off_list_tokens"])
    m["cefr_coverage"] = c["coverage_pct"]
    for k in (1, 2, 3):
        m[f"bnc_{k}k"] = b["per_band"][str(k)]["coverage_pct"]
    m["bnc_4k_plus"] = sum(b["per_band"][str(k)]["coverage_pct"] for k in range(4, 26))
    m["bnc_proper"] = pct(b["counts"]["proper_noun_tokens"])
    m["bnc_off_list"] = pct(b["counts"]["off_list_tokens"])
    m["bnc_coverage_with_supplementary"] = b["coverage_with_supplementary_pct"]
    m["ngsl"] = n["coverage_pct"]["ngsl"]
    m["nawl"] = n["coverage_pct"]["nawl"]
    m["ngsl_proper"] = n["coverage_pct"]["proper_nouns"]
    m["ngsl_off_list"] = n["coverage_pct"]["off_list"]
    m["awl"] = w["coverage_pct"]
    return {
        "measures": m,
        "estimated_level_95th": c["estimated_level_95th"],
        "highest_level_present": c["highest_level_present"],
        "counts": {
            "content_tokens": nt,
            "cefr_on_list": c["counts"]["on_list_tokens"],
            "cefr_proper": c["counts"]["proper_noun_tokens"],
            "bnc_proper": b["counts"]["proper_noun_tokens"],
            "ngsl_tokens": n["counts"]["ngsl_tokens"],
            "awl_tokens": w["counts"]["awl_tokens"],
        },
    }


def check_counts(toks: list[dict], tm: dict) -> None:
    c = tm["counts"]
    assert c["content_tokens"] == len(toks)
    assert c["cefr_on_list"] == sum(t["cefr"] in CEFR_LEVELS for t in toks)
    assert c["cefr_proper"] == sum(t["cefr"] == "PROPER" for t in toks)
    assert c["bnc_proper"] == sum(t["bnc"] == "proper" for t in toks)
    assert c["ngsl_tokens"] == sum(t["ngsl"] == "NGSL" for t in toks)
    assert c["awl_tokens"] == sum(t["awl"] != "-" for t in toks)


# --- scoring ----------------------------------------------------------------------


def bootstrap_ci(per_text: list[tuple[float, float]], rng: random.Random) -> list[float]:
    """95% percentile CI of sum(num)/sum(den), resampling texts."""
    n = len(per_text)
    vals = []
    for _ in range(BOOTSTRAP):
        num = den = 0.0
        for _ in range(n):
            a, b = per_text[rng.randrange(n)]
            num += a
            den += b
        vals.append(num / den * 100 if den else 0.0)
    vals.sort()
    return [round(vals[int(0.025 * BOOTSTRAP)], 2), round(vals[int(0.975 * BOOTSTRAP) - 1], 2)]


def rate(per_text: list[tuple[float, float]], rng: random.Random) -> dict:
    num = sum(a for a, _ in per_text)
    den = sum(b for _, b in per_text)
    return {
        "pct": round(num / den * 100, 2) if den else None,
        "ci95": bootstrap_ci(per_text, rng) if den else None,
        "n": int(num),
        "of": int(den),
    }


def accuracy(texts_docs: list[dict], cond: str, rng, gold_lemma_available: bool) -> dict:
    keys = {
        "upos": lambda t, g: t.pos_ == g.upos,
        "xpos": lambda t, g: t.tag_ == g.xpos,
        # Annotation-convention differences rather than errors: ESLSpok tags
        # every `to` TO where OntoNotes (spaCy) tags prepositional `to` IN, and
        # treebanks differ on quote-mark tags.
        "xpos_lenient": lambda t, g: (
            t.tag_ == g.xpos
            or (t.lower_ == "to" and {t.tag_, g.xpos} <= {"TO", "IN"})
            or {t.tag_, g.xpos} <= {'"', "``", "''"}
        ),
    }
    res: dict = {}
    for scope in ("all_tokens", "lexical_tokens"):
        for k, f in keys.items():
            per = []
            for td in texts_docs:
                doc, toks = td[cond], td["gold_toks"]
                idx = range(len(toks)) if scope == "all_tokens" else td["lex_i"]
                per.append((sum(f(doc[i], toks[i]) for i in idx), len(idx)))
            res[f"{k}_{scope}"] = rate(per, rng)
        if gold_lemma_available:
            per, per_ci = [], []
            for td in texts_docs:
                doc, toks = td[cond], td["gold_toks"]
                idx = range(len(toks)) if scope == "all_tokens" else td["lex_i"]
                idx = [i for i in idx if toks[i].lemma is not None]
                per.append((sum(doc[i].lemma_ == toks[i].lemma for i in idx), len(idx)))
                per_ci.append(
                    (sum(doc[i].lemma_.lower() == toks[i].lemma.lower() for i in idx), len(idx))
                )
            res[f"lemma_{scope}"] = rate(per, rng)
            res[f"lemma_ci_{scope}"] = rate(per_ci, rng)
    # Proper-noun detection (NNP/NNPS), the tag lexinspect uses to exclude names.
    tp = fp = fn = 0
    for td in texts_docs:
        doc, toks = td[cond], td["gold_toks"]
        for i in td["lex_i"]:
            p = doc[i].tag_ in ("NNP", "NNPS")
            g = toks[i].xpos in ("NNP", "NNPS")
            tp += p and g
            fp += p and not g
            fn += g and not p
    res["proper_noun_tag"] = {
        "precision": round(tp / (tp + fp) * 100, 2) if tp + fp else None,
        "recall": round(tp / (tp + fn) * 100, 2) if tp + fn else None,
        "gold_proper_tokens": tp + fn,
        "predicted_proper_tokens": tp + fp,
    }
    return res


def confusions(texts_docs, cond: str, attr: str, top: int = 12) -> list:
    c: Counter = Counter()
    for td in texts_docs:
        doc, toks = td[cond], td["gold_toks"]
        for t, g in zip(doc, toks, strict=False):
            pred = t.tag_ if attr == "xpos" else t.pos_
            gold = g.xpos if attr == "xpos" else g.upos
            if pred != gold:
                c[(gold, pred)] += 1
    return [{"gold": g, "pred": p, "count": n} for (g, p), n in c.most_common(top)]


OUTCOMES = ("cefr", "bnc", "ngsl", "awl")


def token_impact(texts_docs, a: str, b: str, rng) -> dict:
    """How often what lexinspect reports for a lexical token differs between
    conditions `a` and `b`."""
    per: dict[str, list] = defaultdict(list)
    examples: dict[str, Counter] = defaultdict(Counter)
    for td in texts_docs:
        A, B = td["tok_out"][a], td["tok_out"][b]
        n = len(A)
        cnt: Counter = Counter()
        for x, y in zip(A, B, strict=False):
            assert x["i"] == y["i"]
            changed = {o: x[o] != y[o] for o in OUTCOMES}
            cnt["tag_differs"] += x["tag"] != y["tag"]
            cnt["upos_differs"] += x["pos"] != y["pos"]
            cnt["lemma_differs"] += x["lemma"] != y["lemma"]
            cnt["proper_flag"] += x["proper"] != y["proper"]
            for o in OUTCOMES:
                cnt[o] += changed[o]
            cnt["any_profile"] += any(changed.values())
            # CEFR breakdown
            xa, ya = x["cefr"] in CEFR_LEVELS, y["cefr"] in CEFR_LEVELS
            cnt["cefr_level_shift"] += xa and ya and x["cefr"] != y["cefr"]
            cnt["cefr_on_off_list"] += xa != ya
            cnt["cefr_proper_vs_off"] += (not xa) and (not ya) and x["cefr"] != y["cefr"]
            cnt["cefr_proper_status"] += (x["cefr"] == "PROPER") != (y["cefr"] == "PROPER")
            # BNC breakdown
            xb, yb = x["bnc"].endswith("k"), y["bnc"].endswith("k")
            cnt["bnc_band_shift"] += xb and yb and x["bnc"] != y["bnc"]
            cnt["bnc_proper_status"] += (x["bnc"] == "proper") != (y["bnc"] == "proper")
            cnt["bnc_on_off_list"] += (x["bnc"] == "off") != (y["bnc"] == "off")
            cnt["ngsl_proper_status"] += (x["ngsl"] == "proper") != (y["ngsl"] == "proper")
            cnt["awl_membership"] += (x["awl"] == "-") != (y["awl"] == "-")
            cnt["reported_proper_status_any"] += (
                (x["cefr"] == "PROPER") != (y["cefr"] == "PROPER")
                or (x["bnc"] == "proper") != (y["bnc"] == "proper")
                or (x["ngsl"] == "proper") != (y["ngsl"] == "proper")
            )
            if changed["cefr"]:
                examples["cefr"][
                    (x["surface"], f"{x['tag']}->{y['tag']}", f"{x['cefr']}->{y['cefr']}")
                ] += 1
            if changed["bnc"]:
                examples["bnc"][
                    (x["surface"], f"{x['tag']}->{y['tag']}", f"{x['bnc']}->{y['bnc']}")
                ] += 1
        for k in (
            "tag_differs", "upos_differs", "lemma_differs", "proper_flag", *OUTCOMES, "any_profile",
            "cefr_level_shift", "cefr_on_off_list", "cefr_proper_vs_off", "cefr_proper_status",
            "bnc_band_shift", "bnc_proper_status", "bnc_on_off_list", "ngsl_proper_status",
            "awl_membership", "reported_proper_status_any",
        ):  # fmt: skip
            per[k].append((cnt[k], n))
    res = {k: rate(v, rng) for k, v in per.items()}
    res["top_changes"] = {
        k: [{"word": w, "tag": t, "change": ch, "count": c} for (w, t, ch), c in v.most_common(15)]
        for k, v in examples.items()
    }
    return res


def text_impact(texts_docs, a: str, b: str) -> dict:
    """Absolute difference, in percentage points, in what lexinspect reports
    per text."""
    diffs: dict[str, list[float]] = defaultdict(list)
    est_same = high_same = 0
    est_steps: Counter = Counter()
    max_cefr = []
    for td in texts_docs:
        A, B = td["text_out"][a], td["text_out"][b]
        for k, v in A["measures"].items():
            diffs[k].append(abs(v - B["measures"][k]))
        max_cefr.append(
            max(
                abs(A["measures"][f"cefr_{lv}"] - B["measures"][f"cefr_{lv}"]) for lv in CEFR_LEVELS
            )
        )
        est_same += A["estimated_level_95th"] == B["estimated_level_95th"]
        ea, eb = A["estimated_level_95th"], B["estimated_level_95th"]
        if ea != eb:
            if ea is None or eb is None:
                est_steps["one side none"] += 1
            else:
                est_steps[f"{abs(CEFR_LEVELS.index(ea) - CEFR_LEVELS.index(eb))} level(s)"] += 1
        high_same += A["highest_level_present"] == B["highest_level_present"]
    n = len(texts_docs)

    def summ(xs):
        xs = sorted(xs)
        return {
            "mean": round(statistics.fmean(xs), 3),
            "median": round(statistics.median(xs), 3),
            "p95": round(xs[min(n - 1, int(0.95 * n))], 3),
            "max": round(xs[-1], 3),
        }

    out = {k: summ(v) for k, v in diffs.items()}
    out["cefr_mean_over_levels"] = round(
        statistics.fmean(statistics.fmean(diffs[f"cefr_{lv}"]) for lv in CEFR_LEVELS), 3
    )
    out["cefr_largest_level_shift_per_text"] = summ(max_cefr)
    out["estimated_level_95th_agreement_pct"] = round(est_same / n * 100, 2)
    out["estimated_level_95th_disagreements"] = dict(est_steps)
    out["highest_level_present_agreement_pct"] = round(high_same / n * 100, 2)
    out["texts"] = n
    return out


# --- speed and size ---------------------------------------------------------------


def speed(model: str, raw_texts: list[str], word_counts: list[int]) -> dict:
    nlp = get_nlp(model)
    for t in raw_texts[:5]:
        nlp(t)
    t0 = time.perf_counter()
    for t in raw_texts:
        nlp(t)  # one text at a time, as lexinspect's parse() does
    dt = time.perf_counter() - t0
    words = sum(word_counts)
    return {"words": words, "seconds": round(dt, 2), "words_per_sec": round(words / dt, 1)}


def load_time(model: str) -> float:
    code = (
        "import time;t=time.perf_counter();import spacy;"
        f"spacy.load('{model}',exclude=['ner']);print(time.perf_counter()-t)"
    )
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip().splitlines()[-1]), 2)
    except (ValueError, IndexError):
        return float("nan")


def dist_size(name: str) -> int:
    d = metadata.distribution(name)
    total = 0
    for f in d.files or ():
        p = Path(d.locate_file(f))
        if p.is_file():
            total += p.stat().st_size
    return total


def sizes() -> dict:
    """Model packages, and everything the trf model adds over the project env."""
    venv = (REPO / ".venv").resolve()
    extra = {}
    for d in metadata.distributions():
        loc = Path(d.locate_file("")).resolve()
        if venv not in loc.parents and loc != venv:
            extra[d.metadata["Name"]] = dist_size(d.metadata["Name"])
    mb = 1024 * 1024
    return {
        "en_core_web_sm_mb": round(dist_size("en_core_web_sm") / mb, 1),
        "en_core_web_trf_mb": round(dist_size("en_core_web_trf") / mb, 1),
        "trf_added_dependencies_mb": {
            k: round(v / mb, 1) for k, v in sorted(extra.items(), key=lambda kv: -kv[1])
        },
        "trf_total_added_mb": round(sum(extra.values()) / mb, 1),
        "note": "trf_added_dependencies lists every distribution outside the project "
        "venv in this run (installed by `uv run --with`): the trf model and the "
        "packages it pulls in (PyTorch, spacy-curated-transformers, ...).",
    }


# --- main -------------------------------------------------------------------------


def machine() -> dict:
    cpu = platform.processor()
    with contextlib.suppress(OSError):
        cpu = (
            subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
            ).stdout.strip()
            or cpu
        )
    info = {"platform": platform.platform(), "cpu": cpu, "python": platform.python_version()}
    try:
        import torch

        info["torch"] = torch.__version__
        info["torch_threads"] = torch.get_num_threads()
    except ImportError:
        pass
    return info


def main() -> None:
    rng = random.Random(SEED)
    data_info = fetch()
    nlps = {k: get_nlp(m) for k, m in MODELS.items()}
    nlp_sm = nlps["sm"]
    results: dict = {
        "study": "Study 2: tagger accuracy on learner English",
        "provenance": provenance(),
        "models": {k: f"{m}-{metadata.version(m)}" for k, m in MODELS.items()},
        "spacy": spacy.__version__,
        "ud_release": UD_RELEASE,
        "data": {},
        "accuracy": {},
        "token_impact": {},
        "text_impact": {},
        "confusions": {},
    }
    raw_for_speed: dict[str, tuple[list[str], list[int]]] = {}

    for name, ds in DATASETS.items():
        print(f"[{name}] loading", file=sys.stderr)
        texts = load_dataset(name)
        has_gold_lemma = name == "baseline_ewt"
        conds = ["sm", "trf", "gold"] + (["gold_lemma"] if has_gold_lemma else [])
        tds = []
        t0 = time.perf_counter()
        for ti, text in enumerate(texts):
            toks, starts = gold_tokens(text)
            td = {"gold_toks": toks}
            for k in ("sm", "trf"):
                td[k] = tag_with(nlps[k], toks, starts)
            td["gold"] = gold_doc(nlp_sm, toks, starts, gold_lemmas=False)
            if has_gold_lemma:
                td["gold_lemma"] = gold_doc(nlp_sm, toks, starts, gold_lemmas=True)
            td["tok_out"], td["text_out"] = {}, {}
            for c in conds:
                a = analysis_of(td[c])
                td["tok_out"][c] = token_outcomes(a)
                td["text_out"][c] = text_measures(a)
                check_counts(td["tok_out"][c], td["text_out"][c])
            td["lex_i"] = [x["i"] for x in td["tok_out"]["gold"]]
            # Lexical tokens are decided by text alone, so identical across conditions.
            for c in conds:
                assert [x["i"] for x in td["tok_out"][c]] == td["lex_i"]
            tds.append(td)
            if ti % 25 == 0:
                print(
                    f"  text {ti + 1}/{len(texts)} ({time.perf_counter() - t0:.0f}s)",
                    file=sys.stderr,
                )

        n_tok = sum(len(td["gold_toks"]) for td in tds)
        n_lex = sum(len(td["lex_i"]) for td in tds)
        results["data"][name] = {
            "description": ds["description"],
            "licence": ds["licence"],
            "files": data_info[name],
            "sentences": sum(len(t) for t in texts),
            "tokens": n_tok,
            "lexical_tokens": n_lex,
            "texts": len(texts),
            "text_words_min": MIN_TEXT_WORDS,
            "gold_lemmas": has_gold_lemma,
        }
        results["accuracy"][name] = {
            k: accuracy(tds, k, rng, has_gold_lemma) for k in ("sm", "trf")
        }
        results["confusions"][name] = {
            k: {"xpos": confusions(tds, k, "xpos"), "upos": confusions(tds, k, "upos")}
            for k in ("sm", "trf")
        }
        pairs = [("sm", "gold"), ("trf", "gold"), ("sm", "trf")]
        if has_gold_lemma:
            pairs += [("sm", "gold_lemma"), ("trf", "gold_lemma")]
        results["token_impact"][name] = {
            f"{a}_vs_{b}": token_impact(tds, a, b, rng) for a, b in pairs
        }
        results["text_impact"][name] = {f"{a}_vs_{b}": text_impact(tds, a, b) for a, b in pairs}
        raw_for_speed[name] = (
            [td["sm"].text for td in tds],
            [analysis_of(td["sm"]).word_count for td in tds],
        )
        del tds

    print("timing", file=sys.stderr)
    results["speed"] = {
        "method": "Raw text strings (one per study text) through lexinspect's pipeline "
        "(get_nlp: tokeniser, tagger, parser, attribute ruler, lemmatiser; NER excluded), "
        "one text per call, CPU only, after 5 warm-up texts. Words are lexinspect words.",
        "machine": machine(),
    }
    for k, m in MODELS.items():
        results["speed"][k] = {name: speed(m, *raw_for_speed[name]) for name in DATASETS}
        results["speed"][k]["load_seconds"] = load_time(m)
    results["size"] = sizes()

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {OUT_JSON}", file=sys.stderr)
    summary(results)


def summary(r: dict) -> None:
    for name in DATASETS:
        print(
            f"\n== {name}: {r['data'][name]['sentences']} sents, {r['data'][name]['tokens']} tokens, "
            f"{r['data'][name]['lexical_tokens']} lexical, {r['data'][name]['texts']} texts"
        )
        for m in ("sm", "trf"):
            acc = r["accuracy"][name][m]
            line = (
                f"  {m}: UPOS {acc['upos_all_tokens']['pct']} XPOS {acc['xpos_all_tokens']['pct']}"
            )
            if "lemma_all_tokens" in acc:
                line += f" lemma {acc['lemma_all_tokens']['pct']} (ci {acc['lemma_ci_all_tokens']['pct']})"
            print(
                line,
                "PROPN P/R",
                acc["proper_noun_tag"]["precision"],
                acc["proper_noun_tag"]["recall"],
            )
        for pair, ti in r["token_impact"][name].items():
            print(
                f"  {pair}: any {ti['any_profile']['pct']} cefr {ti['cefr']['pct']} bnc {ti['bnc']['pct']} "
                f"ngsl {ti['ngsl']['pct']} awl {ti['awl']['pct']} proper {ti['reported_proper_status_any']['pct']}"
            )
            tx = r["text_impact"][name][pair]
            print(
                f"     text: cefr mean|d| {tx['cefr_mean_over_levels']} pp, largest/text mean "
                f"{tx['cefr_largest_level_shift_per_text']['mean']} max {tx['cefr_largest_level_shift_per_text']['max']}, "
                f"est95 agree {tx['estimated_level_95th_agreement_pct']}%"
            )
    print("\nspeed", {k: r["speed"][k] for k in MODELS})
    print(
        "size",
        r["size"]["en_core_web_sm_mb"],
        r["size"]["en_core_web_trf_mb"],
        r["size"]["trf_total_added_mb"],
    )


if __name__ == "__main__":
    main()
