"""Tests for the Study 4 sampling and analysis.

uv run --with pytest pytest -q scripts/validation/study4_precision/test_analyse.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import analyse as A  # noqa: E402
import batches as B  # noqa: E402
import build  # noqa: E402
import estimators as E  # noqa: E402
import frame as F  # noqa: E402
import human_page  # noqa: E402
import simulate_coverage as S  # noqa: E402

# --- fixtures ------------------------------------------------------------------


def key_row(i, module="metadiscourse", stratum="hedges", sub="rest", N=100, n=None, **extra):
    row = {
        "id": f"id{i}",
        "module": module,
        "stratum": stratum,
        "substratum": f"{stratum}|{sub}",
        "N_sub": N,
        "n_sub": n,
        "register": "academic",
        "text_id": f"T{i}",
    }
    if module == "metadiscourse":
        row |= {"category": stratum, "dimension": "interactional"}
    else:
        row |= {"k_band": 1, "multi_sense": False, "expression": "HAVE TO"}
    return row | extra


def fix_n(rows):
    """Set n_sub to the number of rows per sub-stratum."""
    c = {}
    for r in rows:
        c[r["substratum"]] = c.get(r["substratum"], 0) + 1
    for r in rows:
        r["n_sub"] = c[r["substratum"]]
    return rows


def item_for(row, others=()):
    if row["module"] == "metadiscourse":
        claimed = {"category": row["category"], "dimension": row["dimension"]}
    else:
        claimed = {
            "expression": row.get("expression", "HAVE TO"),
            "sense": None,
            "example": "x",
            "other_senses_in_list": [{"expression": o} for o in others],
        }
    return {"id": row["id"], "module": row["module"], "claimed": claimed}


def lset(mapping, name="X", expected=None):
    labels = {}
    for i, v in mapping.items():
        lab, alt = v if isinstance(v, tuple) else (v, None)
        labels[i] = {"id": i, "label": lab, "alt_category": alt, "note": "n"}
    return A.LabelSet(name, labels, sorted(expected if expected is not None else mapping))


def ref_of(mapping, source="primaries"):
    return {
        i: {"y": y, "source": source if y is not None else "unresolved"} for i, y in mapping.items()
    }


def frame_for(rows, registers=None):
    """Frame from rows: N per sub-stratum; optional {sub: {register: count}}."""
    fm = {}
    for r in rows:
        fm.setdefault(r["module"], {})[r["substratum"]] = {
            "N": r["N_sub"],
            "by_register": (registers or {}).get(r["substratum"]),
        }
    return {"modules": {m: fm.get(m, {}) for m in A.LABELS}}


REG = {g: A.Domain(f"register={g}", False, None, g, True) for g in A.REGISTERS}


def R(rid, label, alt=None, note=None, **extra):
    """A complete label record (all four required keys)."""
    return {"id": rid, "label": label, "alt_category": alt, "note": note, **extra}


def J(**kw):
    kw.setdefault("alt_category", None)
    kw.setdefault("note", None)
    return json.dumps(kw)


# --- basic statistics -----------------------------------------------------------


def test_wilson_known_values():
    lo, hi = E.wilson(0.5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    lo, hi = E.wilson(1.0, 20)
    assert hi == 1.0 and lo == pytest.approx(0.8389, abs=1e-4)
    assert E.wilson(0.5, 0) is None


def test_quantiles():
    assert E.norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-5)
    for df, t in ((1, 12.7062), (2, 4.3027), (5, 2.5706), (30, 2.0423)):
        assert E.t_ppf(0.975, df) == pytest.approx(t, abs=1e-3)
    assert E.t_ppf(0.975, math.inf) == pytest.approx(1.959964, abs=1e-5)
    assert E.t_ppf(0.9875, 10) == pytest.approx(2.6338, abs=1e-3)


def test_cohen_kappa_textbook_and_undefined():
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert A.cohen_kappa(a, b) == pytest.approx(0.4)
    assert A.cohen_kappa([1, 1, 1], [1, 1, 1]) is None
    assert A.cohen_kappa([], []) is None


def test_outcome_maps():
    v = A.outcome_value
    md, ph = A.LABELS["metadiscourse"], A.LABELS["phrase"]
    assert [v("metadiscourse", "STRICT", x) for x in md] == [1, 0, 0, 0, None]
    assert [v("metadiscourse", "LENIENT", x) for x in md] == [1, 1, 0, 0, None]
    assert [v("metadiscourse", "CONNECTIVE", x) for x in md] == [1, 1, 1, 0, None]
    assert [v("phrase", "LIST_LENIENT", x) for x in ph] == [1, 1, 0, 0, None]
    assert [v("phrase", "PHRASAL", x) for x in ph] == [1, 1, 1, 0, None]
    assert v("phrase", "STRICT", None) is None and v("phrase", "STRICT", "WRONG_CATEGORY") is None
    assert v("phrase", "STRICT", ["CORRECT"]) is None


# --- exact finite-population bounds -----------------------------------------------


def test_hypergeometric_interval_has_exact_coverage():
    M, n = 20, 5
    worst = 1.0
    for T in range(M + 1):
        cover = 0.0
        for k in range(n + 1):
            pk = E._pmf(k, M, T, n)
            if pk == 0:
                continue
            lo, hi = E.hyper_count_ci(k, n, M, 0.05)
            cover += pk * (lo <= T <= hi)
        worst = min(worst, cover)
    assert worst >= 0.95
    assert E.hyper_count_ci(3, 10, 10, 0.05) == (3, 3)  # census


def test_one_sided_hypergeometric_limits_are_the_inversions():
    M, n, k, a1 = 200, 20, 15, 0.025
    lo, hi = E.hyper_lcl(k, n, M, a1), E.hyper_ucl(k, n, M, a1)
    assert E.hyper_sf(k, M, lo, n) > a1 >= E.hyper_sf(k, M, lo - 1, n)
    assert E.hyper_cdf(k, M, hi, n) > a1 >= E.hyper_cdf(k, M, hi + 1, n)
    assert E.hyper_lcl(0, n, M, a1) == 0 and E.hyper_ucl(n, n, M, a1) == M
    assert E.hyper_count_ci(k, n, M, 0.05) == (lo, hi)


def _exact_coverage(Ms, ns, alpha=0.05):
    """Exact (enumerated) minimum coverage of exact_limits over every T configuration."""
    outcomes = list(itertools.product(*[range(n + 1) for n in ns]))
    lim = {}
    for ks in outcomes:
        r = E.exact_limits(
            [(m, n, k, k) for m, n, k in zip(Ms, ns, ks, strict=True)], alpha / 2, alpha / 2
        )
        lim[ks] = (r["lower"], r["upper"])
    tot, worst, worst_lo, worst_hi = sum(Ms), 1.0, 1.0, 1.0
    for Ts in itertools.product(*[range(m + 1) for m in Ms]):
        pt = sum(Ts) / tot
        cov = miss_lo = miss_hi = 0.0
        for ks in outcomes:
            pr = math.prod(E._pmf(k, m, t, n) for m, n, t, k in zip(Ms, ns, Ts, ks, strict=True))
            if pr == 0:
                continue
            lo, hi = lim[ks]
            if pt < lo - 1e-12:
                miss_lo += pr
            elif pt > hi + 1e-12:
                miss_hi += pr
            else:
                cov += pr
        worst, worst_lo, worst_hi = (
            min(worst, cov),
            min(worst_lo, 1 - miss_lo),
            min(worst_hi, 1 - miss_hi),
        )
    return worst, worst_lo, worst_hi


@pytest.mark.parametrize(
    "Ms,ns,fpc_max",
    [
        ((12, 9), (4, 3), 2500),
        ((12, 9), (4, 3), 0),  # binomial-dominance branch
        ((30, 10), (3, 8), 2500),
        ((10, 10, 10), (3, 3, 3), 2500),
        ((40, 25), (6, 2), 0),
    ],
)
def test_joint_exact_limits_cover_by_enumeration(monkeypatch, Ms, ns, fpc_max):
    monkeypatch.setattr(E, "FPC_EXACT_MAX_M", fpc_max)
    worst, lo, hi = _exact_coverage(Ms, ns)
    assert worst >= 0.95 and lo >= 0.975 and hi >= 0.975


def test_joint_limit_is_much_narrower_than_bonferroni():
    rng = random.Random(3)
    cells = []
    for _ in range(29):
        big_m, n = rng.randint(50, 3000), rng.choice([15, 15, 40, 70, 100])
        k = sum(rng.random() < 0.8 for _ in range(n))
        cells.append((big_m, n, k))
    ex = E.exact_limits([(m, n, k, k) for m, n, k in cells], 0.025, 0.025)
    bf = E.bonferroni_hypergeometric(cells, 0.05)
    assert ex["method"] == "exact_stratified_chernoff"
    assert bf[0] <= ex["lower"] and ex["upper"] <= bf[1]
    assert ex["upper"] - ex["lower"] < 0.5 * (bf[1] - bf[0])


def test_exact_limit_methods_depend_on_resolved_counts_only():
    assert E.exact_limits([(10, 10, 7, 7)], 0.025, 0.025)["method"] == "census"
    assert E.exact_limits([(10, 10, 7, 7), (20, 0, 0, 0)], 0.025, 0.025) == {
        "lower": 7 / 30,
        "upper": 27 / 30,
        "method": "census_and_unobserved",
        "unobserved_share": 20 / 30,
    }
    one = E.exact_limits([(10, 10, 7, 7), (100, 5, 5, 5)], 0.025, 0.025)
    assert one["method"] == "exact_hypergeometric"
    assert one["lower"] == pytest.approx((7 + E.hyper_lcl(5, 5, 100, 0.025)) / 110)
    assert one["upper"] == pytest.approx(107 / 110)
    two = E.exact_limits([(100, 5, 5, 5), (100, 5, 0, 0)], 0.025, 0.025)
    assert two["method"] == "exact_stratified_chernoff" and two["lower"] < 0.5 < two["upper"]


# --- label validation -----------------------------------------------------------


@pytest.fixture
def vitems():
    rows = [
        key_row(1, stratum="transitions"),
        key_row(2, stratum="hedges"),
        key_row(3, module="phrase", stratum="K3-multi", expression="UP TO (UNTIL)"),
        key_row(4, module="phrase", stratum="K1-single"),
    ]
    items = {
        "id1": item_for(rows[0]),
        "id2": item_for(rows[1]),
        "id3": item_for(rows[2], others=["UP TO (MAXIMUM)", "OUT OF (‘IN’/’FROM’)"]),
        "id4": item_for(rows[3]),
    }
    return rows, items


@pytest.mark.parametrize(
    "rec,reason",
    [
        ({"id": "id2", "label": "CORRECT", "alt_category": None}, "missing_field"),
        ({"id": "id2", "label": "CORRECT", "note": None}, "missing_field"),
        ({"id": "id2", "alt_category": None, "note": None}, "missing_field"),
        (R("id2", "WRONG_SENSE_LISTED", "X"), "invalid_label"),
        (R("id2", "correct"), "invalid_label"),
        (R("id2", "EXTERNAL_CONNECTIVE"), "external_connective_not_transitions"),
        (R("id2", "WRONG_CATEGORY"), "alt_category_missing"),
        (R("id2", "WRONG_CATEGORY", "  "), "alt_category_missing"),
        (R("id2", "WRONG_CATEGORY", "hedging"), "alt_category_invalid"),
        (R("id2", "WRONG_CATEGORY", " evidentials"), "alt_category_invalid"),
        (R("id2", "WRONG_CATEGORY", "Evidentials"), "alt_category_invalid"),
        (R("id2", "WRONG_CATEGORY", "hedges"), "alt_category_same_as_claimed"),
        (R("id2", "CORRECT", "boosters"), "alt_category_not_allowed"),
        (R("id2", "NOT_METADISCOURSE", ""), "alt_category_not_allowed"),
        (R("id4", "NOT_THE_EXPRESSION", "X"), "alt_category_not_allowed"),
        (R("id3", "WRONG_SENSE_LISTED", "UP TO (DECISIONS)"), "alt_sense_not_listed"),
        (R("id3", "WRONG_SENSE_LISTED", "UP TO"), "alt_sense_not_listed"),
        (R("id4", "WRONG_SENSE_LISTED", "X"), "alt_sense_not_listed"),
        (R("id3", "WRONG_SENSE_UNLISTED"), "alt_category_missing"),
        (R("id3", "WRONG_SENSE_UNLISTED", "from inside"), "gloss_not_capitals"),
        (R("id3", "WRONG_SENSE_UNLISTED", "A B C D E F G"), "gloss_word_count"),
        (R("id3", "WRONG_SENSE_UNLISTED", "UP  TO (MAXIMUM)"), "alt_sense_is_listed"),
        (R("id3", "WRONG_SENSE_UNLISTED", "UP TO (UNTIL)"), "alt_sense_is_listed"),
        (R("id2", "CORRECT", None, " ".join(["w"] * 26)), "note_too_long"),
        (R("id2", "UNSURE", None, " "), "unsure_without_note"),
        (R("id2", "UNSURE"), "unsure_without_note"),
        (R("id2", "UNSURE", None, "two readings here"), "unsure_note_format"),
        (R("id2", "UNSURE", None, "CORRECT or NOT_METADISCOURSE:"), "unsure_note_format"),
        (R("id2", "UNSURE", None, "CORRECT or maybe: unclear"), "unsure_reading_invalid"),
        (R("id2", "UNSURE", None, "correct or boosters: case"), "unsure_reading_invalid"),
        (R("id2", "UNSURE", None, "CORRECT, NOT_METADISCOURSE: list"), "unsure_reading_invalid"),
        (
            R("id4", "UNSURE", None, "CORRECT or hedges: md key on a PHRASE item"),
            "unsure_reading_invalid",
        ),
        (R("id2", "UNSURE", None, "CORRECT or CORRECT: same"), "unsure_too_few_readings"),
        (R("id2", "UNSURE", None, "CORRECT: only one"), "unsure_too_few_readings"),
        ({"id": "id2", "label": [], "alt_category": None, "note": None}, "invalid_field_type"),
        ({"id": "id2", "label": {}, "alt_category": None, "note": None}, "invalid_field_type"),
        (R("id2", "CORRECT", 5), "invalid_field_type"),
        (R("id2", "UNSURE", None, ["x"]), "invalid_field_type"),
    ],
)
def test_each_rejection_reason(vitems, rec, reason):
    _, items = vitems
    ls = A.validate_lines([json.dumps(rec)], items)
    assert rec["id"] not in ls.labels
    assert [p["reason"] for p in ls.problems] == [reason]
    retry = {r["id"]: r["reason"] for r in ls.retry}
    assert retry[rec["id"]] == reason
    assert all(retry[i] == "missing" for i in items if i != rec["id"])


def test_valid_records_accepted(vitems):
    _, items = vitems
    lines = [
        J(id="id1", label="EXTERNAL_CONNECTIVE", alt_category=None, note=None, batch=2, position=7),
        J(id="id2", label="WRONG_CATEGORY", alt_category="boosters", note=None),
        J(id="id3", label="WRONG_SENSE_LISTED", alt_category="out of ('in'/'from')"),
        J(id="id4", label="WRONG_SENSE_UNLISTED", alt_category="A DUTY TO ACT, NOT CHOICE"),
    ]
    lines.append(J(id="id1x", label="CORRECT"))
    ls = A.validate_lines(lines[:4], items)
    assert set(ls.labels) == {"id1", "id2", "id3", "id4"} and not ls.problems and not ls.retry
    meta = A.validate_lines([J(id="id2", label="CORRECT", batch="1", position=True, at="x")], items)
    assert "id2" in meta.labels  # metadata fields are ignored


@pytest.mark.parametrize(
    "rid,note",
    [
        (
            "id1",
            "CORRECT or EXTERNAL_CONNECTIVE: the clause may concede a point or only relate two events",
        ),
        (
            "id2",
            "self_mentions or engagement_markers: we could be the authors only or authors and readers",
        ),
        ("id2", "  hedges  or  boosters or  CORRECT :x"),
        ("id2", "CORRECT or NOT_METADISCOURSE: reason: with a second colon"),
        ("id3", "CORRECT or WRONG_SENSE_LISTED: until or maximum"),
        ("id2", " ".join(["CORRECT or UNSURE:"] + ["w"] * 22)),  # exactly 25 words
    ],
)
def test_valid_unsure_notes(vitems, rid, note):
    _, items = vitems
    ls = A.validate_lines([J(id=rid, label="UNSURE", note=note)], items, [rid])
    assert rid in ls.labels, ls.problems


def test_guideline_examples_validate():
    """The eight example records in the guidelines' "Your output" section are valid."""
    guide = (A.REPO / "docs" / "validation" / "study4-guidelines.md").read_text()
    section = guide.split("## Your output", 1)[1].split("\n## ", 1)[0]
    block = section.split("```json", 1)[1].split("```", 1)[0]
    recs = [json.loads(x) for x in block.strip().splitlines()]
    claims = ["hedges", "engagement_markers", "hedges", "transitions", "self_mentions"]
    items = {
        r["id"]: {"id": r["id"], "module": "metadiscourse", "claimed": {"category": c}}
        for r, c in zip(recs[:5], claims, strict=True)
    }
    phrase = [
        ("UP TO (UNTIL)", ["UP TO (MAXIMUM)", "UP TO (DECISIONS)"]),
        ("OUT OF ('IN'/'FROM')", ["OUT OF ('USING')", "OUT OF ('DUE TO')"]),
        ("USED TO (PAST)", []),
    ]
    for r, (expr, others) in zip(recs[5:], phrase, strict=True):
        items[r["id"]] = {
            "id": r["id"],
            "module": "phrase",
            "claimed": {
                "expression": expr,
                "other_senses_in_list": [{"expression": o} for o in others],
            },
        }
    ls = A.validate_lines([json.dumps(r) for r in recs], items)
    assert len(recs) == 8 and not ls.problems and len(ls.labels) == 8


def test_malformed_lines_unknown_and_unassigned_ids(vitems):
    _, items = vitems
    lines = [
        '{"id": "id1", "label": "CORRECT"',
        "[1, 2]",
        J(label="CORRECT"),
        J(id="zzz", label="CORRECT"),
        J(id="id2", label="CORRECT"),
        "",
        J(id="id3", label="CORRECT"),
    ]
    ls = A.validate_lines(lines, items, expected=["id1", "id2", "id4"])
    assert [(p["line"], p["reason"]) for p in ls.problems] == [
        (1, "malformed_json"),
        (2, "not_an_object"),
        (3, "missing_id"),
        (4, "unknown_id"),
        (7, "not_assigned"),
    ]
    assert set(ls.labels) == {"id2"}
    assert [r["id"] for r in ls.retry] == ["id1", "id4"]


def test_duplicates_compare_label_and_normalised_alt_ignoring_notes(vitems):
    _, items = vitems
    lines = [
        J(id="id1", label="CORRECT", note="a"),
        J(id="id1", label="CORRECT", note="b"),  # notes ignored: collapse, first note kept
        J(id="id2", label="CORRECT"),
        J(id="id2", label="NOT_METADISCOURSE"),  # labels differ: conflicting
        J(id="id3", label="WRONG_SENSE_LISTED", alt_category="UP TO (MAXIMUM)", note="x"),
        J(
            id="id3", label="WRONG_SENSE_LISTED", alt_category="up  to (maximum)"
        ),  # equal after norm_sense
        J(id="id4", label="WRONG_SENSE_UNLISTED", alt_category="FROM INSIDE"),
        J(
            id="id4", label="WRONG_SENSE_UNLISTED", alt_category="INSIDE"
        ),  # alts differ: conflicting
    ]
    ls = A.validate_lines(lines, items)
    assert ls.labels["id1"]["note"] == "a"
    assert ls.labels["id3"]["alt_category"] == "UP TO (MAXIMUM)" and ls.labels["id3"]["note"] == "x"
    reasons = {r["id"]: r["reason"] for r in ls.retry}
    assert reasons == {"id2": "conflicting_duplicate", "id4": "conflicting_duplicate"}
    assert any(w["reason"] == "identical_duplicate_collapsed" for w in ls.warnings)


def test_equal_duplicates_with_an_invalid_record_are_rejected(vitems):
    _, items = vitems
    # Same (label, alt) after normalisation, but " evidentials" is invalid for WRONG_CATEGORY.
    lines = [
        J(id="id2", label="WRONG_CATEGORY", alt_category="evidentials"),
        J(id="id2", label="WRONG_CATEGORY", alt_category=" evidentials"),
    ]
    for perm in (lines, lines[::-1]):
        ls = A.validate_lines(perm, items, ["id2"])
        assert not ls.labels and ls.retry[0]["reason"] == "invalid_duplicate"


def test_duplicate_handling_is_order_independent(vitems):
    _, items = vitems
    recs = [
        J(id="id2", label="UNSURE", note="CORRECT or boosters: two readings"),
        J(id="id2", label="UNSURE", note=""),  # equal key, but this record is invalid
        J(id="id1", label=[]),
        J(id="id1", label=[]),
        J(id="id3", label="CORRECT", note="p"),
        J(id="id3", label="WRONG_SENSE_LISTED", alt_category="UP TO (MAXIMUM)"),
        J(id="id4", label="CORRECT", note="first"),
        J(id="id4", label="CORRECT", note="second"),
    ]
    results = set()
    for perm in itertools.permutations(recs):
        ls = A.validate_lines(list(perm), items)
        results.add((tuple(sorted(ls.labels)), tuple((r["id"], r["reason"]) for r in ls.retry)))
    assert len(results) == 1
    ((labels, retry),) = results
    assert labels == ("id4",)
    assert dict(retry) == {
        "id1": "invalid_duplicate",
        "id2": "invalid_duplicate",
        "id3": "conflicting_duplicate",
    }


def test_retry_manifest_is_deterministic(vitems, tmp_path):
    _, items = vitems
    lines = [
        J(id="id2", label="WRONG_CATEGORY"),
        J(id="id3", label="UNSURE"),
        J(id="id1", label="CORRECT"),
        "garbage",
    ]
    outs = set()
    for k, perm in enumerate(itertools.permutations(lines)):
        p = tmp_path / f"m{k}.jsonl"
        A.write_retry_manifest(A.validate_lines(list(perm), items), p)
        outs.add(p.read_bytes())
    assert len(outs) == 1
    ids = [json.loads(x)["id"] for x in next(iter(outs)).decode().splitlines()]
    assert ids == ["id2", "id3", "id4"]


def test_merge_retry_then_still_invalid_is_missing(vitems):
    _, items = vitems
    orig = [
        J(id="id1", label="CORRECT"),
        J(id="id2", label="WRONG_CATEGORY"),
        "broken",
        J(id="id3", label="NOT_THE_EXPRESSION"),
    ]
    ls = A.validate_lines(orig, items)
    manifest = [r["id"] for r in ls.retry]
    assert manifest == ["id2", "id4"]
    retry = [
        J(id="id2", label="WRONG_CATEGORY", alt_category="boosters"),
        J(id="id4", label="UNSURE"),
        J(id="id1", label="NOT_METADISCOURSE"),
    ]
    merged, notes = A.merge_retry(orig, retry, manifest)
    assert any("not in the manifest" in n for n in notes)
    ls2 = A.validate_lines(merged, items)
    assert (
        ls2.labels["id1"]["label"] == "CORRECT" and ls2.labels["id2"]["alt_category"] == "boosters"
    )
    assert [r["id"] for r in ls2.retry] == ["id4"]


# --- design validation ------------------------------------------------------------


def _design():
    rows = fix_n(
        [key_row(i, sub="a", N=10) for i in range(3)]
        + [key_row(i, sub="b", N=5) for i in range(3, 5)]
    )
    return rows, [item_for(r) for r in rows]


def test_clean_design_passes():
    rows, items = _design()
    orders = B.make_orders([r["id"] for r in rows], ["id0"], 1)
    assert A.validate_design(rows, items, ["id0"], orders, frame_for(rows)) == []


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda r, it: r.append(dict(r[0])), "duplicate key id"),
        (lambda r, it: it.append(dict(it[0])), "duplicate item id"),
        (lambda r, it: it.pop(), "key and items differ"),
        (lambda r, it: it[0]["claimed"].update(category="boosters"), "category differs"),
        (
            lambda r, it: [x.update(n_sub=20) for x in r if x["substratum"].endswith("|a")],
            "need 0 < n_sub <= N_sub",
        ),
        (lambda r, it: r[0].update(N_sub=11), "not constant"),
        (
            lambda r, it: [x.update(n_sub=4) for x in r if x["substratum"].endswith("|a")],
            "key rows but n_sub",
        ),
        (lambda r, it: r[0].update(N_sub="10"), "not an integer"),
    ],
)
def test_design_problems_detected(mutate, needle):
    rows, items = _design()
    mutate(rows, items)
    probs = A.validate_design(rows, items)
    assert any(needle in p for p in probs), probs


def test_duplicate_key_row_would_have_changed_the_estimate():
    # The reviewer's case: duplicating the correct row of a 2-item 50% sample.
    rows = fix_n([key_row(1, sub="h", N=10), key_row(2, sub="h", N=10)])
    rows.append(dict(rows[0]))
    assert any(
        "duplicate key id" in p for p in A.validate_design(rows, [item_for(r) for r in rows[:2]])
    )


def test_maintainer_orders_and_frame_problems_detected():
    rows, items = _design()
    for r in rows:
        r["in_maintainer_sample"] = r["id"] == "id0"
        r["m_sub"] = 2 if r["substratum"].endswith("|a") else 0
    probs = A.validate_design(rows, items, ["id0", "zz"])
    assert any("m_sub" in p for p in probs) and any("not in key" in p for p in probs)
    orders = B.make_orders([r["id"] for r in rows], ["id0"], 1)
    orders["roles"]["A"]["order"].append("id1")
    orders["roles"]["B"]["batch_size"] = 0
    fr = frame_for(rows, {"hedges|a": {"academic": 9}})
    probs = A.validate_design(rows, items, ["id0"], orders, fr)
    assert any("orders[A]: duplicate" in p for p in probs)
    assert any("orders[B]: batch_size" in p for p in probs)
    assert any("register counts do not sum" in p for p in probs)


def test_reviewer_frame_counterexample_is_rejected_not_repaired():
    # Round-3 finding 3: N=100, n=2, both sampled items academic, frame academic=1.
    rows = fix_n([key_row(1, sub="h", N=100), key_row(2, sub="h", N=100)])
    items = [item_for(r) for r in rows]
    fr = frame_for(rows, {"hedges|h": {"academic": 1, "general": 99}})
    probs = A.validate_design(rows, items, frame=fr)
    assert any("2 sampled academic items but the frame has 1" in p for p in probs), probs
    with pytest.raises(ValueError, match="below the 2 sampled"):
        A.estimate(rows, ref_of({"id1": 1, "id2": 0}), REG["academic"], fr)


@pytest.mark.parametrize(
    "bad,needle",
    [
        ({"hedges|a": {"N": 0, "by_register": None}}, "positive integer"),
        ({"hedges|a": {"N": 10.0, "by_register": None}}, "positive integer"),
        ({"hedges|a": {"N": True, "by_register": None}}, "positive integer"),
        ({"hedges|a": {"N": 11, "by_register": None}}, "!= key N_sub"),
        ({"hedges|a": {"N": 10, "by_register": [10]}}, "must be a mapping"),
        ({"hedges|a": {"N": 10, "by_register": {"legal": 10}}}, "unknown registers"),
        ({"hedges|a": {"N": 10, "by_register": {"academic": -1, "general": 11}}}, "nonnegative"),
        ({"hedges|a": {"N": 10, "by_register": {"academic": 2.5, "general": 7.5}}}, "nonnegative"),
        ({"hedges|zz": {"N": 10, "by_register": None}}, "sub-strata differ"),
    ],
)
def test_frame_inputs_are_checked_strictly(bad, needle):
    rows, items = _design()
    fr = frame_for(rows)
    fr["modules"]["metadiscourse"].update(bad)
    probs = A.validate_design(rows, items, frame=fr)
    assert any(needle in p for p in probs), probs
    assert any(
        "no modules mapping" in p for p in A.validate_design(rows, items, frame={"modules": []})
    )


@pytest.mark.parametrize(
    "cell",
    [
        (10, 5, 3, 2),
        (10, 5, 6, 6),
        (10, 11, 1, 1),
        (10, 5, -1, 1),
        (10.5, 5, 1, 1),
        (10, 5, 1),
        (10, 5, True, 1),
    ],
)
def test_exact_limits_reject_invalid_cells(cell):
    with pytest.raises(ValueError):
        E.exact_limits([cell, (20, 4, 1, 1)], 0.025, 0.025)


@pytest.mark.parametrize("M", [1.0, 1.5, 11.0, -1.0])
def test_exact_cell_population_is_checked_not_repaired(M):
    s = E.Stratum("h", 10, M, True, [(True, 1), (True, 0)], [1, 0])
    with pytest.raises(ValueError):
        E._cell_m(s)
    assert E._cell_m(E.Stratum("h", 10, 1.2, False, [], [1, 0])) == 2  # estimated: ceil, >= n


@pytest.mark.parametrize(
    "M,a,exact_branch",
    [
        (2500, 125, True),
        (2501, 126, False),
        (2500, 124, False),
        (2000, 100, True),
        (2000, 99, False),
    ],
)
def test_mgf_branch_thresholds_and_binomial_dominance(monkeypatch, M, a, exact_branch):
    calls = []
    real = E._hyper_lmgf

    def spy(*args):
        calls.append(args[:2])
        return real(*args)

    monkeypatch.setattr(E, "_hyper_lmgf", spy)
    cells = [(M, a, a // 2, a // 2), (300, 30, 20, 20)]
    r = E.exact_limits(cells, 0.025, 0.025)
    assert ((M, a) in calls) == exact_branch
    assert r["lower"] < (a // 2 / a * M + 200) / (M + 300) < r["upper"]
    # the binomial bound dominates the exact log-MGF, so either branch is valid
    lams, mus = np.logspace(-2, 3, 9), np.logspace(-2, 3, 9)
    hyp = E._phi(lams, mus, [(1.0, a, M)])
    monkeypatch.setattr(E, "FPC_EXACT_MAX_M", 0)
    binom = E._phi(lams, mus, [(1.0, a, M)])
    if exact_branch:
        assert np.all(binom >= hyp - 2e-9)  # up to the deliberate +1e-9 slack


# --- reference ---------------------------------------------------------------------


def test_reference_rule_per_outcome_with_fallthrough():
    rows = [key_row(i) for i in range(1, 7)]
    a = lset(
        {
            "id1": "CORRECT",
            "id2": ("WRONG_CATEGORY", "boosters"),
            "id3": "CORRECT",
            "id4": "UNSURE",
            "id5": "CORRECT",
            "id6": "CORRECT",
        },
        "A",
    )
    b = lset(
        {
            "id1": "CORRECT",
            "id2": "CORRECT",
            "id3": "NOT_METADISCOURSE",
            "id4": "CORRECT",
            "id5": "NOT_METADISCOURSE",
        },
        "B",
    )
    adj = lset({"id2": "NOT_METADISCOURSE", "id3": "UNSURE", "id4": "CORRECT"}, "C")
    strict = A.reference(rows, "STRICT", [a, b], adj)
    assert strict["id1"] == {"y": 1, "source": "primaries"}
    assert strict["id2"] == {"y": 0, "source": "adjudicator"}
    assert strict["id3"] == {"y": None, "source": "unresolved"}  # no maintainer fallback
    assert strict["id4"] == {"y": 1, "source": "adjudicator"}
    assert strict["id5"]["source"] == "unresolved"
    assert strict["id6"] == {"y": None, "source": "unresolved"}
    lenient = A.reference(rows, "LENIENT", [a, b], adj)
    assert lenient["id2"] == {"y": 1, "source": "primaries"}
    with pytest.raises(TypeError):  # the model reference takes no maintainer argument
        A.reference(rows, "STRICT", [a, b], adj, lset({}, "M"), {"id3"})
    assert A.needs_adjudication(rows, [a, b]) == ["id2", "id3", "id4", "id5", "id6"]


def test_adjudication_triggered_by_secondary_outcome_only():
    rows = [key_row(1, stratum="transitions"), key_row(2, module="phrase", stratum="K1")]
    a = lset({"id1": "NOT_METADISCOURSE", "id2": "NOT_THE_EXPRESSION"})
    b = lset({"id1": "EXTERNAL_CONNECTIVE", "id2": ("WRONG_SENSE_UNLISTED", "X")})
    assert A.needs_adjudication(rows, [a, b]) == ["id1", "id2"]
    conn = A.reference(rows, "CONNECTIVE", [a, b])
    assert set(conn) == {"id1"} and conn["id1"]["source"] == "unresolved"


# --- domain estimation ---------------------------------------------------------------


def _register_rows():
    rows = [key_row(i, sub="h1", N=1000, register="academic") for i in range(5)]
    rows += [key_row(i, sub="h1", N=1000, register="general") for i in range(5, 10)]
    rows += [key_row(i, sub="h2", N=100, register="academic") for i in range(10, 19)]
    rows += [key_row(19, sub="h2", N=100, register="general")]
    y = {
        r["id"]: int(r["substratum"].endswith("h1") == (r["register"] == "academic")) for r in rows
    }
    return fix_n(rows), y


def test_register_domain_not_recalibrated_and_population_from_frame():
    rows, y = _register_rows()
    fr = frame_for(
        rows,
        {
            "hedges|h1": {"academic": 480, "general": 520},
            "hedges|h2": {"academic": 92, "general": 8},
        },
    )
    e = A.estimate(rows, ref_of(y), REG["academic"], fr)
    assert e["p"] == pytest.approx(500 / 590)  # weights 100 and 10 from the full sample
    assert e["p"] != pytest.approx(1000 / 1100)  # recalibrating the subset would give this
    assert e["N_hat"] == pytest.approx(590)
    assert e["population"] == 572 and e["population_exact"]  # from the frame, not the sample
    assert A.estimate(rows, ref_of(y), A.ALL_DOMAIN, fr)["population"] == 1100


def test_population_never_exact_from_sample_composition():
    # Every sampled item is academic, but the frame says 40 of 100 are not.
    rows = fix_n([key_row(i, sub="h", N=100, register="academic") for i in range(2)])
    y = {"id0": 1, "id1": 1}
    without = A.estimate(rows, ref_of(y), REG["academic"])
    assert not without["population_exact"]
    assert any("estimated" in w for w in without["warnings"])
    withf = A.estimate(
        rows,
        ref_of(y),
        REG["academic"],
        frame_for(rows, {"hedges|h": {"academic": 60, "general": 40}}),
    )
    assert withf["population"] == 60 and withf["population_exact"]


def test_domain_nonresponse_adjusts_within_substratum():
    rows = fix_n([key_row(1, sub="X", N=10), key_row(2, sub="X", N=10), key_row(3, sub="Y", N=30)])
    e = A.estimate(rows, ref_of({"id1": 1, "id2": None, "id3": 0}))
    assert e["p"] == pytest.approx(10 / 40)
    lo, hi = e["bounds_unresolved_wrong_right"]
    assert lo == pytest.approx(5 / 40) and hi == pytest.approx(10 / 40)


# --- variance and intervals --------------------------------------------------------------


def test_reviewer_hand_calculation():
    # h1: N=12, r=4, domain 1,1,0,0, y 1,0,1,0; h2: N=6, r=3, domain 1,1,0, y 1,1,0.
    s1 = E.Stratum("1", 12, 6, True, [(True, 1), (True, 0), (False, 1), (False, 0)], [1, 0])
    s2 = E.Stratum("2", 6, 4, True, [(True, 1), (True, 1), (False, 0)], [1, 1])
    e = E.domain_estimate([s1, s2], df=5)
    assert e["p"] == pytest.approx(0.7) and e["N_hat"] == pytest.approx(10)
    assert e["var"] == pytest.approx(0.045)
    n_e = 0.21 / 0.045 * (E.t_ppf(0.975, 3) / E.t_ppf(0.975, 5)) ** 2
    assert e["n_eff"] == pytest.approx(min(n_e, 4))  # truncated at n_d = 4
    assert e["ci95_approx"] == E.wilson(0.7, 4)
    assert e["ci95_approx"] == pytest.approx((0.26664623, 0.93739744))
    assert e["ci95_approx_method"] == "korn_graubard_modified_wilson"
    assert e["ci95_exact_method"] == "exact_stratified_chernoff"


def test_linearised_variance_and_design_df():
    rows = fix_n(
        [key_row(i, sub="h1", N=10) for i in range(3)]
        + [key_row(i, sub="h2", N=20) for i in range(3, 5)]
    )
    y = {"id0": 1, "id1": 1, "id2": 0, "id3": 1, "id4": 0}
    e = A.estimate(rows, ref_of(y))
    assert e["p"] == pytest.approx(5 / 9)
    v1 = 10**2 * (1 - 3 / 10) * (27 / 270**2) / 3
    v2 = 20**2 * (1 - 2 / 20) * (40.5 / 270**2) / 2
    assert e["var"] == pytest.approx(v1 + v2)
    assert e["df"] == 3  # 5 resolved items - 2 sub-strata
    n_e = (5 / 9) * (4 / 9) / (v1 + v2) * (E.t_ppf(0.975, 4) / E.t_ppf(0.975, 3)) ** 2
    assert e["n_eff"] == pytest.approx(min(n_e, 5))


def _enumerate(pop_by_h, n_by_h):
    per_h = [
        [list(c) for c in itertools.combinations(units, n_by_h[h])] for h, units in pop_by_h.items()
    ]
    out = []
    for combo in itertools.product(*per_h):
        rows = [u for part in combo for u in part]
        e = A.estimate(rows, ref_of({u["id"]: u["y"] for u in rows}))
        out.append((e["p"], e["var"]))
    return out


def test_exact_enumeration_srs_variance_is_unbiased_with_fpc():
    ys = [1, 1, 1, 0, 0, 1]
    pop = {"h": [key_row(i, sub="h", N=6, n=3) | {"y": y} for i, y in enumerate(ys)]}
    res = _enumerate(pop, {"h": 3})
    P = 4 / 6
    true_var = (1 - 3 / 6) * (sum((y - P) ** 2 for y in ys) / 5) / 3
    assert sum(p for p, _ in res) / 20 == pytest.approx(P)
    assert sum((p - P) ** 2 for p, _ in res) / 20 == pytest.approx(true_var)
    assert sum(v for _, v in res) / 20 == pytest.approx(true_var)


def test_exact_enumeration_stratified():
    pop = {
        "a": [key_row(i, sub="a", N=5, n=2) | {"y": y} for i, y in enumerate([1, 1, 0, 1, 0])],
        "b": [key_row(10 + i, sub="b", N=4, n=2) | {"y": y} for i, y in enumerate([1, 0, 0, 0])],
    }
    res = _enumerate(pop, {"a": 2, "b": 2})
    P, m = 4 / 9, len(res)
    assert sum(p for p, _ in res) / m == pytest.approx(P)
    assert sum(v for _, v in res) / m == pytest.approx(sum((p - P) ** 2 for p, _ in res) / m)


def test_census_gives_a_point():
    rows = fix_n([key_row(i, sub="h", N=4) for i in range(4)])
    e = A.estimate(rows, ref_of({"id0": 1, "id1": 0, "id2": 1, "id3": 1}))
    assert e["var"] == 0 and e["census_strata"] == ["hedges|h"]
    assert e["ci95_exact"] == (0.75, 0.75) and e["ci95_exact_method"] == "census"
    assert e["region95_exact"] == (0.75, 0.75) and e["ci95_approx"] == (0.75, 0.75)


def test_reviewer_boundary_counterexample():
    # N1=10,000 with 2 sampled, N2=148 census; everything observed correct.
    rows = fix_n(
        [key_row(i, sub="big", N=10_000) for i in range(2)]
        + [key_row(10 + i, sub="small", N=148) for i in range(148)]
    )
    e = A.estimate(rows, ref_of({r["id"]: 1 for r in rows}))
    assert e["p"] == 1.0 and e["ci95_exact_method"] == "exact_hypergeometric"
    lo, hi = e["ci95_exact"]
    assert hi == 1.0 and lo < 0.8029  # covers the reviewer's 80%-in-stratum-1 population
    assert lo == pytest.approx((E.hyper_lcl(2, 2, 10_000, 0.025) + 148) / 10_148)
    assert lo == pytest.approx(0.170, abs=1e-3)
    assert e["ci95_approx"] is None and "not reported" in e["ci95_approx_status"]


def test_reviewer_unresolved_stratum_is_never_dropped():
    # Round-2 finding 1: A has N=1,000, 100 resolved, 50 correct; B has N=9,000, nothing resolved.
    rows = fix_n(
        [key_row(i, sub="A", N=1000) for i in range(100)]
        + [key_row(1000 + i, sub="B", N=9000) for i in range(10)]
    )
    y = {r["id"]: (i % 2 if r["substratum"].endswith("A") else None) for i, r in enumerate(rows)}
    e = A.estimate(rows, ref_of(y))
    assert e["p"] is None and e["p_scope"] == "represented_cells_only"  # round-3 finding 4
    assert e["p_represented"] == pytest.approx(0.5)
    assert any("no domain point estimate" in w for w in e["warnings"])
    lo, hi = e["ci95_exact"]
    assert lo <= 0.05 and hi >= 0.95  # P = .05 (B all wrong) and P = .95 (B all right) covered
    assert e["unobserved_share_exact"] == pytest.approx(0.9)
    assert e["represented_share"] == pytest.approx(0.1)
    assert e["ci95_approx_scope"] == "represented_cells_only"
    assert any("no resolved domain item" in w for w in e["warnings"])
    rlo, rhi = e["region95_exact"]
    assert rlo <= lo and rhi >= hi


def test_resolution_region_needs_no_assumption_about_unresolved_items():
    # Census of 10 with the 4 wrong items unresolved: the primary limits (which assume
    # exchangeable resolution) miss P = 0.6; the region does not.
    rows = fix_n([key_row(i, sub="h", N=10) for i in range(10)])
    y = {f"id{i}": (1 if i < 6 else None) for i in range(10)}
    e = A.estimate(rows, ref_of(y))
    assert e["p"] == 1.0 and e["ci95_exact"][0] > 0.6
    assert e["region95_exact"] == (0.6, 1.0) and e["region95_exact_method"] == "census"


def test_zero_variance_interior_reports_exact_limits_only():
    rows = fix_n(
        [key_row(i, sub="a", N=500) for i in range(5)]
        + [key_row(i, sub="b", N=500) for i in range(5, 10)]
    )
    y = {r["id"]: int(r["substratum"].endswith("a")) for r in rows}
    e = A.estimate(rows, ref_of(y))
    assert e["p"] == 0.5 and e["var"] == 0 and e["ci95_approx"] is None
    lo, hi = e["ci95_exact"]
    assert lo < 0.5 < hi and hi - lo > 0.2


def test_singleton_strata_are_flagged():
    rows = fix_n([key_row(1, sub="a", N=50)] + [key_row(i, sub="b", N=500) for i in range(2, 22)])
    y = {r["id"]: (1 if r["id"] == "id1" else int(int(r["id"][2:]) % 3 != 0)) for r in rows}
    e = A.estimate(rows, ref_of(y))
    assert e["singleton_strata"] == ["hedges|a"]
    assert any("single resolved" in w for w in e["warnings"])
    lo, hi = e["ci95_exact"]
    assert lo <= e["p"] <= hi


def test_nothing_resolved_reports_population_and_unit_limits():
    rows = fix_n([key_row(1, sub="a", N=40), key_row(2, sub="a", N=40)])
    e = A.estimate(rows, ref_of({"id1": None, "id2": None}))
    assert e["p"] is None and e["ci95_approx"] is None
    assert e["ci95_exact"] == (0.0, 1.0) and e["region95_exact"][0] == 0.0
    assert e["bounds_unresolved_wrong_right"] == (0.0, 1.0)
    assert e["population"] == 40 and e["n_items"] == 2 and e["represented_share"] == 0
    assert e["resolution_rate"] == 0


def test_empty_domains_are_reported(tmp_path):
    rows = fix_n(
        [key_row(i, stratum="hedges") for i in range(4)]
        + [key_row(10 + i, module="phrase", stratum="K1-single") for i in range(3)]
    )
    labs = {r["id"]: "CORRECT" for r in rows}
    rep = A.analyse(rows, [lset(labs, "A"), lset(labs, "B")])
    md = rep["model_reference"]["metadiscourse"]["STRICT"]
    assert {f"category={c}" for c in A.MD_CATEGORIES} <= set(md)
    assert md["category=boosters"]["n_items"] == 0 and md["category=boosters"]["p"] is None
    assert {f"k_band={k}" for k in A.K_BANDS} <= set(rep["model_reference"]["phrase"]["STRICT"])
    assert set(rep["model_reference"]["metadiscourse"]["CONNECTIVE"]) == {"category=transitions"}


def test_simulated_coverage_of_the_complete_procedure(capsys):
    # End to end through analyse(scope="module"): label files -> reference -> limits.
    key = []
    for h, (big_n, n) in {"x": (400, 20), "y": (1500, 15), "z": (60, 15), "w": (250, 25)}.items():
        key += [key_row(f"{h}{j}", sub=h, N=big_n) for j in range(n)]
    fix_n(key)
    spec = {"mech": "outcome", "pu1": 0.03, "pu0": 0.25, "maintainer_total": 30}
    task = {
        "spec": spec,
        "key_rows": key,
        "frame": None,
        "module": "metadiscourse",
        "pop_seed": 4,
        "cell_seed": "9",
        "start": 0,
        "reps": 150,
    }
    recs, seen = S._chunk(task)
    assert seen == S.source_hashes()
    world = S.population(S.BASE | spec, key, None, "metadiscourse", 4)
    res = S.summarise({"P": world["P"], "D": world["D"]}, recs)
    with capsys.disabled():
        print(
            f"\ntoy outcome-dependent (150 reps): primary {res['primary']['coverage']:.3f}, "
            f"region {res['region']['coverage']:.3f}, KG {res['kg']['coverage']:.3f}, "
            f"concordance {res['concordance_pass2']['coverage']:.3f}"
        )
    assert res["region"]["miss_low"] + res["region"]["miss_high"] <= 3
    assert res["region"]["mean_width"] >= res["primary"]["mean_width"]
    assert (
        res["concordance_pass2"]["mean_width"]
        <= res["concordance_pass1_only"]["mean_width"] + 1e-12
    )
    assert S.clopper_pearson(0, 23_410)[1] == pytest.approx(1.5756e-4, rel=1e-3)
    lo, hi = S.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.18709, abs=1e-4) and hi == pytest.approx(0.81291, abs=1e-4)


def test_simulated_phrase_labels_parse_through_the_module_outcomes():
    key = fix_n(
        [key_row(i, module="phrase", stratum="K1-single", sub="a", N=80) for i in range(12)]
    )
    task = {
        "spec": {"maintainer_total": 12},
        "key_rows": key,
        "frame": None,
        "module": "phrase",
        "pop_seed": 1,
        "cell_seed": "2",
        "start": 0,
        "reps": 3,
    }
    recs, _ = S._chunk(task)
    assert all(r[0] is not None and r[2][0] <= r[2][1] for r in recs)


def _sim_key():
    return fix_n(
        [key_row(i, module="phrase", stratum="K1-single", sub="a", N=50) for i in range(10)]
    )


def test_simulation_is_independent_of_worker_count():
    # Sol's round-4 probe design: one cell N=50, n=10, PHRASE, 120 replicates (3 chunks).
    key = _sim_key()
    args = ("main-realistic", {}, "phrase", key, None, 120, 101, 12345)
    r1 = S.run(*args, workers=1)
    r2 = S.run(*args, workers=2)
    assert A.clean_json(r1) == A.clean_json(r2)
    assert r1["cell_seed"] == "12345|main-realistic|phrase|pop=101"
    # a cell's stream does not depend on which other cells run or in what order
    assert S.replicate_rng("x", 7).random() == S.replicate_rng("x", 7).random()
    assert S.replicate_rng("x", 7).random() != S.replicate_rng("x", 8).random()


def _sim_args(kp, scenarios=("boundary-high",), reps=50, seeds=("101",), extra=()):
    return [
        "--key",
        str(kp),
        "--scenario",
        *scenarios,
        "--modules",
        "phrase",
        "--grid-reps",
        str(reps),
        "--main-reps",
        str(reps),
        "--grid-pop-seeds",
        *seeds,
        "--pop-seeds",
        *seeds,
        "--workers",
        "1",
        *extra,
    ]


def _sim_key_file(tmp_path):
    kp = tmp_path / "key.jsonl"
    kp.write_text("".join(json.dumps(r) + "\n" for r in _sim_key()))
    return kp


def _strip_seconds(cells):
    return [{k: v for k, v in c.items() if k != "seconds"} for c in cells]


def test_simulation_manifest_resume_and_merge_are_verified(tmp_path):
    kp = _sim_key_file(tmp_path)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert S.main([*_sim_args(kp), "--out", str(a)]) == 0
    da = json.loads(a.read_text())
    m = da["manifest"]
    assert set(m["sources_sha256"]) == set(S.SOURCES) and m["key_sha256"] == S.sha256_file(kp)
    assert m["environment"]["numpy"]
    assert m["scenario_parameters"]["boundary-high"]["phrase"]["p_range"] == [0.97, 1.0]
    assert m["command"] and "fixed logical chunks of 50" in m["chunk_scheme"]
    # status, distinct checkpoint and completion times, structured arguments
    assert m["status"] == "complete" and m["completed_time"] and m["checkpoint_time"]
    assert m["format"] == S.FORMAT and set(S.REQUIRED_MANIFEST) <= set(m)
    assert m["arguments"]["scenario"] == ["boundary-high"] and m["arguments"]["grid_reps"] == 50
    assert m["inventory"] == [
        {
            "scenario": "boundary-high",
            "module": "phrase",
            "pop_seed": 101,
            "replicate_start": 0,
            "replicate_stop": 50,
            "cell_seed": "20261016|boundary-high|phrase|pop=101",
            "parameters": m["scenario_parameters"]["boundary-high"]["phrase"],
        }
    ]
    assert m["inventory_sha256"] == S.sha256_json(m["inventory"])
    c = da["cells"][0]
    assert (c["replicate_start"], c["replicate_stop"], c["reps"]) == (0, 50, 50)
    # resuming a complete file with the same request leaves it byte-identical
    before = a.read_bytes()
    assert S.main([*_sim_args(kp), "--out", str(a), "--resume"]) == 0
    assert a.read_bytes() == before
    # an existing output is never overwritten without --resume
    with pytest.raises(SystemExit, match="exists: use --resume"):
        S.main([*_sim_args(kp), "--out", str(a)])
    assert S.main([*_sim_args(kp, ("boundary-low",)), "--out", str(b)]) == 0
    inv = tmp_path / "final_inventory.json"
    assert (
        S.main([*_sim_args(kp, ("boundary-high", "boundary-low")), "--write-inventory", str(inv)])
        == 0
    )
    out = tmp_path / "merged.json"
    assert S.main(["--merge", str(a), str(b), "--out", str(out), "--inventory", str(inv)]) == 0
    mg = json.loads(out.read_text())
    assert len(mg["cells"]) == 2 and len(mg["manifest"]["merge_provenance"]) == 2
    assert mg["manifest"]["status"] == "complete"
    assert mg["manifest"]["inventory_file"]["sha256"] == S.sha256_file(inv)
    assert [x["cell_seed"] for x in mg["cells"]] == [
        e["cell_seed"] for e in json.loads(inv.read_text())["cells"]
    ]
    # identical copies of a cell in two parts collapse
    out2 = tmp_path / "merged2.json"
    assert (
        S.main(["--merge", str(a), str(b), str(a), "--out", str(out2), "--inventory", str(inv)])
        == 0
    )
    assert json.loads(out2.read_text())["cells"] == mg["cells"]
    # merge needs the declared inventory
    with pytest.raises(SystemExit):
        S.main(["--merge", str(a), str(b), "--out", str(out)])
    # a manifest mismatch (different base seed) is refused by merge and by resume
    c7 = tmp_path / "c.json"
    assert S.main([*_sim_args(kp, ("boundary-low",)), "--out", str(c7), "--seed", "7"]) == 0
    with pytest.raises(SystemExit, match="manifest differs"):
        S.main(["--merge", str(a), str(c7), "--out", str(out), "--inventory", str(inv)])
    with pytest.raises(SystemExit, match="different manifest"):
        S.main([*_sim_args(kp, ("boundary-low",)), "--out", str(c7), "--resume"])


def test_simulation_resume_never_skips_a_shorter_cell(tmp_path):
    # Sol's round-5 probe: 2 replicates saved, then --resume asking for 99.
    kp = _sim_key_file(tmp_path)
    out = tmp_path / "r.json"
    probe = ("main-realistic",)
    assert S.main([*_sim_args(kp, probe, reps=2, seeds=("77",)), "--out", str(out)]) == 0
    saved = out.read_bytes()
    with pytest.raises(SystemExit) as e:
        S.main([*_sim_args(kp, probe, reps=99, seeds=("77",)), "--out", str(out), "--resume"])
    msg = str(e.value)
    assert "different request" in msg and "saved replicates [0, 2) but requested [0, 99)" in msg
    assert "never extends or shortens a cell" in msg
    assert out.read_bytes() == saved  # nothing written
    # a file whose inventory asks for 99 but whose cell holds 2 is rejected, not skipped
    d = json.loads(saved)
    d["manifest"]["inventory"][0]["replicate_stop"] = 99
    d["manifest"]["inventory_sha256"] = S.sha256_json(d["manifest"]["inventory"])
    out.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match=r"holds 2 replicates \[0, 2\) but 99 are required"):
        S.main([*_sim_args(kp, probe, reps=99, seeds=("77",)), "--out", str(out), "--resume"])
    # extra requested or unrequested cells are also a different request
    out.write_bytes(saved)
    with pytest.raises(SystemExit, match="requested but not in the saved run"):
        S.main([*_sim_args(kp, probe, reps=2, seeds=("77", "78")), "--out", str(out), "--resume"])


def test_simulation_interrupted_run_resumes_to_the_uninterrupted_result(tmp_path, monkeypatch):
    kp = _sim_key_file(tmp_path)
    args = _sim_args(kp, ("boundary-low",), reps=60, seeds=("101", "202"))
    full = tmp_path / "full.json"
    assert S.main([*args, "--out", str(full)]) == 0
    part = tmp_path / "part.json"
    real_run, calls = S.run, []

    def crash_second(*a, **k):
        calls.append(a)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return real_run(*a, **k)

    monkeypatch.setattr(S, "run", crash_second)
    with pytest.raises(KeyboardInterrupt):
        S.main([*args, "--out", str(part)])
    monkeypatch.setattr(S, "run", real_run)
    cp = json.loads(part.read_text())
    assert cp["manifest"]["status"] == "running" and cp["manifest"]["completed_time"] is None
    assert len(cp["cells"]) == 1
    # a running checkpoint cannot be merged
    inv = tmp_path / "inv.json"
    assert S.main([*args, "--write-inventory", str(inv)]) == 0
    with pytest.raises(SystemExit, match="not 'complete'"):
        S.main(["--merge", str(part), "--out", str(tmp_path / "m.json"), "--inventory", str(inv)])
    assert S.main([*args, "--out", str(part), "--resume"]) == 0
    done = json.loads(part.read_text())
    assert done["manifest"]["status"] == "complete"
    assert done["manifest"]["started"] == cp["manifest"]["started"]
    assert done["manifest"]["checkpoint_time"] >= cp["manifest"]["checkpoint_time"]
    assert done["manifest"]["completed_time"] >= done["manifest"]["checkpoint_time"]
    assert done["manifest"]["resumed_from"]["status"] == "running"
    assert _strip_seconds(done["cells"]) == _strip_seconds(json.loads(full.read_text())["cells"])


def test_simulation_manifest_and_merge_checks(tmp_path):
    kp = _sim_key_file(tmp_path)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert S.main([*_sim_args(kp, reps=20), "--out", str(a)]) == 0
    assert S.main([*_sim_args(kp, ("boundary-low",), reps=20), "--out", str(b)]) == 0
    inv = tmp_path / "inv.json"
    both = ("boundary-high", "boundary-low")
    assert S.main([*_sim_args(kp, both, reps=20), "--write-inventory", str(inv)]) == 0
    out = tmp_path / "m.json"

    def merge(*paths, inventory=inv):
        return S.main(
            ["--merge", *map(str, paths), "--out", str(out), "--inventory", str(inventory)]
        )

    def edited(src, name, fn):
        d = json.loads(src.read_text())
        fn(d)
        p = tmp_path / name
        p.write_text(json.dumps(d))
        return p

    # the union must equal the declared inventory: a missing part, an undeclared cell
    with pytest.raises(SystemExit, match="missing"):
        merge(a)
    inv_a = tmp_path / "inv_a.json"
    assert S.main([*_sim_args(kp, reps=20), "--write-inventory", str(inv_a)]) == 0
    with pytest.raises(SystemExit, match="not declared"):
        merge(a, b, inventory=inv_a)
    # a declared count that the parts do not hold
    inv_40 = tmp_path / "inv_40.json"
    assert S.main([*_sim_args(kp, both, reps=40), "--write-inventory", str(inv_40)]) == 0
    with pytest.raises(SystemExit, match="but 40 are required"):
        merge(a, b, inventory=inv_40)
    # missing required manifest fields; an old (round-4) manifest without status
    for field in ("status", "arguments", "inventory", "completed_time"):
        bad = edited(a, f"no_{field}.json", lambda d, f=field: d["manifest"].pop(f))
        with pytest.raises(SystemExit, match="lacks required fields"):
            merge(bad, b)
    bad = edited(a, "complete_no_time.json", lambda d: d["manifest"].update(completed_time=None))
    with pytest.raises(SystemExit, match="with completed_time"):
        merge(bad, b)
    bad = edited(a, "inv_tamper.json", lambda d: d["manifest"]["inventory"][0].update(pop_seed=7))
    with pytest.raises(SystemExit, match="inventory_sha256"):
        merge(bad, b)
    # a duplicated cell inside one file, a differing copy across files, a tampered cell
    bad = edited(a, "dup.json", lambda d: d["cells"].append(d["cells"][0]))
    with pytest.raises(SystemExit, match="more than once"):
        merge(bad, b)
    bad = edited(a, "differ.json", lambda d: d["cells"][0].update(mean_point=0.5))
    with pytest.raises(SystemExit, match="differs from an earlier file"):
        merge(a, bad, b)
    bad = edited(a, "reps.json", lambda d: d["cells"][0].update(reps=19))
    with pytest.raises(SystemExit, match="holds 19 replicates"):
        merge(bad, b)
    bad = edited(a, "seed.json", lambda d: d["cells"][0].update(cell_seed="x"))
    with pytest.raises(SystemExit, match="not in the inventory"):
        merge(bad, b)
    # inventory files are checked too
    bad_inv = edited(inv, "inv_bad.json", lambda d: d["cells"][0]["parameters"].update(q2=0.1))
    with pytest.raises(SystemExit, match="cells_sha256"):
        merge(a, b, inventory=bad_inv)

    def reseal(d):
        d["cells"][0]["parameters"]["q2"] = 0.1
        d["cells_sha256"] = S.sha256_json(d["cells"])

    with pytest.raises(SystemExit, match="parameters differ"):
        merge(a, b, inventory=edited(inv, "inv_params.json", reseal))
    with pytest.raises(SystemExit, match="base seed"):
        merge(a, b, inventory=edited(inv, "inv_seed.json", lambda d: d.update(base_seed=1)))
    assert merge(a, b) == 0
    # options that would create duplicate or unknown cells are refused up front
    with pytest.raises(SystemExit, match="repeated"):
        S.main(_sim_args(kp, seeds=("101", "101")))
    with pytest.raises(SystemExit, match="unknown --scenario"):
        S.main(_sim_args(kp, ("no-such",)))


# Values computed with the round-4 sources (sim_r4_frozen_sources.sha256) before the
# round-6 changes: one PHRASE cell N=50, n=10, 60 replicates, base seed 12345, pop 101.
R4_PINNED = {
    "main-realistic": (0.66, -0.02, 0.6548611111111111, 0.522, 0.5353333333333334, 0.697),
    "boundary-high": (1.0, 0.02, 1.0, 0.27466666666666667, 0.31033333333333335, 0.727),
    "adverse-concordance": (
        0.66,
        0.0,
        0.6487037037037038,
        0.5453333333333333,
        0.586,
        0.8246666666666668,
    ),
    "fixed-outcome-unresolved": (
        0.62,
        0.02,
        0.6986772486772487,
        0.5416666666666666,
        0.6073333333333333,
        0.8360000000000001,
    ),
}


@pytest.mark.parametrize("name", sorted(R4_PINNED))
def test_existing_scenarios_reproduce_round4_results(name):
    r = S.run(name, (S.MAIN | S.GRID)[name], "phrase", _sim_key(), None, 60, 101, 12345, 1)
    got = (
        r["P"],
        r["D"],
        r["mean_point"],
        r["primary"]["mean_width"],
        r["region"]["mean_width"],
        r["concordance_pass2"]["mean_width"],
    )
    assert got == R4_PINNED[name]
    assert r["p_shift"] is None


def test_pilot_calibrated_scenarios():
    pilot = S.PILOT
    for m in ("metadiscourse", "phrase"):
        e = S.effective(S.MAIN["main-pilot"], m)
        adj = pilot[m]["adjudicated"] / pilot[m]["items"]
        assert e["pu1"] == e["pu0"]
        assert e["pu1"] + (1 - e["pu1"]) * e["p_adj"] == pytest.approx(adj, abs=1e-15)
        assert e["p_target"] == pilot[m]["precision"] and e["mech"] == "random"
        # maintainer and heterogeneity parameters are BASE's (the pilot has no maintainer data)
        for k in ("q_unsure", "q_unsure_disc", "q2", "f10", "f01", "p_range", "maintainer_total"):
            assert e[k] == S.BASE[k]
        assert "by_module" not in e
    assert S.effective(S.MAIN["main-pilot"], "metadiscourse")["pu1"] == 2 / 1000
    assert S.effective(S.MAIN["main-pilot"], "phrase")["pu1"] == pytest.approx(8 / 300 * 2 / 86)
    assert (pilot["metadiscourse"]["precision"], pilot["phrase"]["precision"]) == (0.491, 0.836)
    assert pilot["adjudication_requests"] == 86 and pilot["adjudicator_unsure"] == 2
    assert S.effective(S.GRID["low-precision-050"], "phrase")["p_target"] == 0.5
    for kept in ("boundary-high", "boundary-low", "adverse-concordance", "main-realistic"):
        assert kept in S.GRID
    # the population hits the target exactly, also with fixed non-resolution
    key = fix_n(
        [key_row(f"a{i}", sub="a", N=400) for i in range(20)]
        + [key_row(f"b{i}", sub="b", N=90) for i in range(9)]
    )
    for target, mech in (
        (0.491, "random"),
        (0.5, "fixed-outcome"),
        (0.0, "random"),
        (1.0, "random"),
    ):
        spec = S.BASE | {"p_target": target, "mech": mech, "pu1": 0.1, "pu0": 0.3}
        w = S.population(spec, key, None, "metadiscourse", 5)
        assert w["P"] == round(target * w["N"]) / w["N"]
        units = [u for us in w["pop"].values() for u in us]
        if mech.startswith("fixed"):
            assert any(u["hard"] for u in units)
    with pytest.raises(ValueError, match="exact_share"):
        S.population(S.BASE | {"p_target": 0.5, "exact_share": 0.5}, key, None, "metadiscourse", 5)
    assert S._target_shift([(0.5, 0.1), (0.5, 0.9)], 0.5) == pytest.approx(0.0)


# --- maintainer two-phase estimator -------------------------------------------------------


def test_maintainer_two_phase_and_uncovered_substratum():
    rows = fix_n(
        [key_row(i, sub="h1", N=100) for i in range(4)]
        + [key_row(i, sub="h2", N=300) for i in range(4, 7)]
    )
    mref = {"id0": {"y": 1}, "id1": {"y": 0}}
    e = A.estimate(rows, mref, phase_ids={"id0", "id1"})
    assert e["p"] is None and e["p_represented"] == pytest.approx(0.5)
    assert e["N_hat"] == pytest.approx(100)
    assert e["population"] == 400 and e["represented_share"] == pytest.approx(0.25)
    assert e["resolution_rate"] == 1.0
    lo, hi = e["bounds_unresolved_wrong_right"]
    assert lo == pytest.approx(50 / 400) and hi == pytest.approx(350 / 400)


def test_maintainer_domain_bounds_include_unrepresented_domain_mass():
    # Reviewer finding 3: phase one has academic items in h, the maintainer sample only general ones.
    rows = fix_n(
        [
            key_row(1, sub="h", N=90, register="academic"),
            key_row(2, sub="h", N=90, register="general"),
            key_row(3, sub="h", N=90, register="general"),
        ]
        + [
            key_row(4, sub="g", N=30, register="academic"),
            key_row(5, sub="g", N=30, register="academic"),
        ]
    )
    fr = frame_for(
        rows, {"hedges|h": {"academic": 60, "general": 30}, "hedges|g": {"academic": 30}}
    )
    mref = {"id2": {"y": 1}, "id3": {"y": 1}, "id4": {"y": 1}, "id5": {"y": 1}}
    e = A.estimate(rows, mref, REG["academic"], fr, phase_ids=set(mref))
    lo, hi = e["bounds_unresolved_wrong_right"]
    assert e["population"] == 90
    assert lo == pytest.approx(30 / 90) and hi == pytest.approx(1.0)  # the 60 in h are unknown
    assert e["represented_share"] == pytest.approx(1 / 3)  # round-2 finding 4 (was 1.0)
    assert e["ci95_exact"][0] <= 1 / 3 and e["ci95_exact"][1] == 1.0


# --- concordance with the maintainer (descriptive) ----------------------------------------


def _audit(n_per=400, strata=3, N=1000, discord=0, unres_model=0, unsure=0):
    rows = []
    for s in range(strata):
        rows += [key_row(s * 1000 + j, sub=f"s{s}", N=N) for j in range(n_per)]
    fix_n(rows)
    ref, labs = {}, {}
    for k, r in enumerate(rows):
        truth = int(k % 5 != 0)
        h = 1 - truth if k < discord else truth
        ref[r["id"]] = (
            {"y": None, "source": "unresolved"}
            if k >= len(rows) - unres_model
            else {"y": truth, "source": "primaries"}
        )
        labs[r["id"]] = (
            "UNSURE"
            if unsure > 0 and k % (len(rows) // unsure) == 1
            else ("CORRECT" if h else "NOT_METADISCOURSE")
        )
    mids = {r["id"] for r in rows}
    return rows, ref, lset(labs, "maintainer", expected=mids), mids


VERDICT_WORDS = ("equivalen", "not_shown", "criteria", "margin", "adequa", "verdict")


def _no_verdict(obj):
    text = json.dumps(A.clean_json(obj)).lower()
    return not any(w in text for w in VERDICT_WORDS)


def test_concordance_is_descriptive_with_no_verdict():
    rows, ref, m, mids = _audit()
    d = A.concordance(rows, ref, m, mids, frame_for(rows))
    assert d["status"] == "descriptive" and _no_verdict(d)
    diff = d["difference"]
    lo, hi = diff["interval95_worst_case_completion"]
    assert diff["D_hat_comparable"] == 0 and -0.05 < lo < 0 < hi < 0.05
    assert "not a full-population estimate" in diff["D_hat_scope"]
    assert d["comparable_share"] == 1 and d["weighted_comparable_share"] == pytest.approx(1)
    assert d["table"]["ref1_maint1"] == 960 and d["table"]["ref0_maint0"] == 240
    assert d["paired_label_counts"] == {"R=0 / NOT_METADISCOURSE": 240, "R=1 / CORRECT": 960}
    assert d["agreement"]["p"] == 1 and d["agreement"]["n"] == 1200


def test_concordance_reports_directions_and_covers_a_real_difference():
    rows, ref, m, mids = _audit(discord=200)  # 160 items d = +1, 40 d = -1: D = 0.10
    d = A.concordance(rows, ref, m, mids, frame_for(rows))
    dirs = d["disagreement_directions"]
    assert len(dirs["ref1_maint0"]) == 160 and len(dirs["ref0_maint1"]) == 40
    assert len(d["disagreements"]) == 200 and d["difference"]["D_hat_comparable"] == 0.1
    lo, hi = d["difference"]["interval95_worst_case_completion"]
    assert 0 < lo < 0.1 < hi
    assert _no_verdict(d)


def test_concordance_interval_widens_with_maintainer_unsure():
    rows, ref, m, mids = _audit()
    rows2, ref2, m2, mids2 = _audit(unsure=400)
    d1 = A.concordance(rows, ref, m, mids, frame_for(rows))
    d2 = A.concordance(rows2, ref2, m2, mids2, frame_for(rows2))
    assert d2["comparable_share"] == pytest.approx(800 / 1200)
    w = [x["difference"]["interval95_worst_case_completion"] for x in (d1, d2)]
    assert w[1][1] - w[1][0] > w[0][1] - w[0][0] + 0.2


def test_reviewer_counterexample_low_weighted_comparability_is_reported():
    # 120 agreeing comparisons representing N=120; 30 model-unresolved items representing N=10,000.
    agree = fix_n([key_row(i, sub="small", N=120) for i in range(120)])
    unres = fix_n([key_row(1000 + i, sub="big", N=10_000) for i in range(30)])
    rows = agree + unres
    ref = {r["id"]: {"y": 1, "source": "primaries"} for r in agree}
    ref |= {r["id"]: {"y": None, "source": "unresolved"} for r in unres}
    m = lset({r["id"]: "CORRECT" for r in rows}, "maintainer")
    mids = {r["id"] for r in rows}
    d = A.concordance(rows, ref, m, mids, frame_for(rows))
    assert d["comparable_share"] == pytest.approx(0.8)
    assert d["weighted_comparable_share"] == pytest.approx(120 / 10_120)
    assert d["difference"]["interval95_worst_case_completion"][0] < -0.9
    assert d["paired_label_counts"]["R=unresolved / CORRECT"] == 30
    assert _no_verdict(d)


def test_unaudited_substrata_count_as_unknown():
    rows, ref, m, mids = _audit()
    other = fix_n([key_row(9000 + i, sub="unaudited", N=1000) for i in range(3)])
    d = A.concordance(rows + other, ref, m, mids, frame_for(rows + other))
    assert d["difference"]["unaudited_population_share"] == pytest.approx(0.25)
    lo, hi = d["difference"]["interval95_worst_case_completion"]
    assert lo <= -0.25 and hi >= 0.25 and d["warnings"]


def test_concordance_not_evaluated_without_maintainer():
    rows = fix_n([key_row(1)])
    d = A.concordance(rows, {"id1": {"y": 1, "source": "primaries"}}, None, set())
    assert d["status"] == "not_evaluated"
    rep = A.analyse(rows, [lset({"id1": "CORRECT"}, "A"), lset({"id1": "CORRECT"}, "B")])
    assert rep["primary"]["metadiscourse"]["estimates"]["ALL"]["p"] == 1.0
    assert "not evaluated" in A.to_markdown(rep)


def test_concordance_never_changes_the_reported_estimates():
    rows = fix_n([key_row(i, sub=f"s{i % 3}", N=300) for i in range(60)])
    labs = {r["id"]: "CORRECT" if i % 4 else "NOT_METADISCOURSE" for i, r in enumerate(rows)}
    mids = {r["id"] for r in rows[:30]}
    agree = lset({i: labs[i] for i in mids}, "maintainer", expected=mids)
    clash = lset({i: "NOT_METADISCOURSE" for i in mids}, "maintainer", expected=mids)
    prim = [lset(labs, "A"), lset(labs, "B")]
    r1 = A.analyse(rows, prim, None, agree, mids)
    r2 = A.analyse(rows, prim, None, clash, mids)
    assert (
        r1["maintainer_concordance"]["metadiscourse"]["table"]
        != r2["maintainer_concordance"]["metadiscourse"]["table"]
    )
    for k in ("primary", "model_reference", "reference_sources"):
        assert r1[k] == r2[k]
    assert set(r1["primary"]["metadiscourse"]["estimates"]) == {"ALL"} | {
        f"category={c}" for c in A.MD_CATEGORIES
    }


def _blocking1_design():
    """Sol's N=n=4 census (two model-unresolved items) plus a sampled sub-stratum with
    model-unresolved items, everything in the maintainer sample."""
    rows = fix_n(
        [key_row(i, sub="census", N=4) for i in range(4)]
        + [key_row(10 + i, sub="big", N=500) for i in range(12)]
    )
    a, b = {}, {}
    for r in rows:
        i = int(r["id"][2:])
        if i in (0, 10, 11, 12):
            a[r["id"]] = b[r["id"]] = "CORRECT"
        elif i in (1, 13, 14):
            a[r["id"]] = b[r["id"]] = "NOT_METADISCOURSE"
        elif i in (15, 16):
            a[r["id"]], b[r["id"]] = "CORRECT", "NOT_METADISCOURSE"  # disagreement
        else:
            a[r["id"]] = b[r["id"]] = "UNSURE"
    adj = {r["id"]: "UNSURE" for r in rows if r["id"] in ("id15",)}  # still unresolved
    mids = {r["id"] for r in rows}
    for r in rows:
        r["in_maintainer_sample"] = True
        r["m_sub"] = r["n_sub"]
    need = A.needs_adjudication(rows, [lset(a, "A"), lset(b, "B")])
    return rows, lset(a, "A"), lset(b, "B"), lset(adj, "C", expected=need), mids


@pytest.mark.parametrize("scope", ["full", "module"])
def test_blocking1_primary_results_invariant_to_the_maintainer(scope):
    rows, a, b, c, mids = _blocking1_design()
    fr = frame_for(rows)
    all_right = lset({i: "CORRECT" for i in mids}, "maintainer", expected=mids)
    all_wrong = lset({i: "NOT_METADISCOURSE" for i in mids}, "maintainer", expected=mids)
    unsure = lset({i: "UNSURE" for i in mids}, "maintainer", expected=mids)
    variants = [None, all_right, all_wrong, unsure]
    reps = [
        A.clean_json(A.analyse(rows, [a, b], c, h, mids if h else None, None, fr, scope=scope))
        for h in variants
    ]
    base = reps[0]
    est = base["primary"]["metadiscourse"]["estimates"]["ALL"]
    assert base["reference_sources"]["metadiscourse"]["STRICT"]["unresolved"] == 9
    assert est["n_resolved"] == 7 and "maintainer" not in json.dumps(base["reference_sources"])
    for r in reps[1:]:
        for k in ("primary", "model_reference", "reference_sources", "adjudication"):
            assert r[k] == base[k], k
    # the census cell keeps its two unresolved items unresolved in the region
    assert est["region95_exact"] != est["ci95_exact"]
    conc = [r["maintainer_concordance"]["metadiscourse"] for r in reps[1:]]
    assert conc[0]["table"] != conc[1]["table"]


def test_concordance_kappa_undefined_when_all_correct():
    rows = fix_n([key_row(i, sub="s", N=1000) for i in range(150)])
    ref = {r["id"]: {"y": 1, "source": "primaries"} for r in rows}
    mids = {r["id"] for r in rows}
    d = A.concordance(
        rows, ref, lset({i: "CORRECT" for i in mids}, "maintainer"), mids, frame_for(rows)
    )
    assert d["kappa"] is None and d["kappa_status"] == "undefined"


def test_concordance_parameters_and_no_equivalence_code():
    assert A.CONCORDANCE_COMPONENT_ALPHA == 0.0125
    for gone in ("equivalence", "EQUIV_MARGIN", "EQUIV_ALPHA", "MIN_COMPARABLE_SHARE"):
        assert not hasattr(A, gone), gone
    rows, ref, m, mids = _audit(n_per=40)
    d = A.concordance(rows, ref, m, mids, frame_for(rows))
    assert "(component limits one-sided .0125)" in d["difference"]["interval_note"]


# Enumeration of the retained concordance interval with integer probabilities.
# Item types: (observed model value or None, maintainer label, true d = R - H).
TYPES = {
    "agree1": (1, "CORRECT", 0),
    "agree0": (0, "NOT_METADISCOURSE", 0),
    "plus": (1, "NOT_METADISCOURSE", 1),
    "minus": (0, "CORRECT", -1),
    "Rmiss_plus": (None, "NOT_METADISCOURSE", 1),  # true R = 1, model unresolved
    "Rmiss_minus": (None, "CORRECT", -1),  # true R = 0, model unresolved
    "Rmiss_zero": (None, "CORRECT", 0),  # true R = 1
    "Hmiss_plus": (1, "UNSURE", 1),  # true H = 0, maintainer unsure
    "Hmiss_zero": (0, "UNSURE", 0),
}


def _compositions(total, parts):
    for cut_ in itertools.combinations(range(total + parts - 1), parts - 1):
        b = (-1, *cut_, total + parts - 1)
        yield tuple(b[i + 1] - b[i] - 1 for i in range(parts))


def _enumerate_concordance(types, Ns, ns):
    """Exact max lower- and upper-tail error over every population of the given types."""
    t = list(types)
    lim = {}

    def interval(counts):  # counts: per stratum, a tuple over types
        if counts not in lim:
            rows, ref, labs = [], {}, {}
            for h, (bign, cs) in enumerate(zip(Ns, counts, strict=True)):
                for ti, c in enumerate(cs):
                    for _ in range(c):
                        r = key_row(len(rows), sub=f"h{h}", N=bign)
                        rows.append(r)
                        y, lab, _ = TYPES[t[ti]]
                        ref[r["id"]] = {
                            "y": y,
                            "source": "primaries" if y is not None else "unresolved",
                        }
                        labs[r["id"]] = lab
            fix_n(rows)
            mids = set(labs)
            fr = {
                "modules": {
                    "metadiscourse": {
                        f"hedges|h{h}": {"N": bn, "by_register": None} for h, bn in enumerate(Ns)
                    },
                    "phrase": {},
                }
            }
            d = A.concordance(rows, ref, lset(labs, "maintainer", expected=mids), mids, fr)
            lim[counts] = d["difference"]["interval95_worst_case_completion"]
        return lim[counts]

    worst_lo = worst_hi = 0.0
    tot = sum(Ns)
    pops = [list(_compositions(bn, len(t))) for bn in Ns]
    samples = [list(_compositions(n, len(t))) for n in ns]
    for pop in itertools.product(*pops):
        true_d = sum(K * TYPES[t[i]][2] for P in pop for i, K in enumerate(P)) / tot
        miss_lo = miss_hi = 0
        denom = math.prod(math.comb(bn, n) for bn, n in zip(Ns, ns, strict=True))
        for smp in itertools.product(*samples):
            w = math.prod(
                math.comb(K, k)
                for P, S_ in zip(pop, smp, strict=True)
                for K, k in zip(P, S_, strict=True)
            )
            if not w:
                continue
            lo, hi = interval(smp)
            miss_lo += w * (lo > true_d + 1e-12)
            miss_hi += w * (hi < true_d - 1e-12)
        worst_lo, worst_hi = max(worst_lo, miss_lo / denom), max(worst_hi, miss_hi / denom)
    return worst_lo, worst_hi


@pytest.mark.parametrize(
    "types,Ns,ns",
    [
        (("agree1", "plus", "minus"), (6, 5), (3, 2)),  # ternary, comparable only
        (("agree1", "plus", "minus"), (7, 4), (2, 4)),  # with a census
        (("agree0", "plus", "Rmiss_minus", "Hmiss_plus"), (5, 4), (2, 2)),
        (("agree1", "Rmiss_plus", "Rmiss_zero", "minus"), (5, 4), (3, 1)),
        (("agree1", "plus", "minus", "Hmiss_zero"), (9,), (3,)),
    ],
)
def test_concordance_interval_tails_by_integer_enumeration(types, Ns, ns):
    lo_err, hi_err = _enumerate_concordance(types, Ns, ns)
    assert lo_err <= 0.025 and hi_err <= 0.025, (lo_err, hi_err)


# --- maintainer second pass ---------------------------------------------------------------


def test_second_pass_combines_and_records_both_passes():
    mids = ["id1", "id2", "id3", "id4"]
    p1 = lset(
        {"id1": "CORRECT", "id2": "UNSURE", "id3": "UNSURE", "id4": "UNSURE"},
        "maintainer",
        expected=mids,
    )
    assert A.second_pass_ids(p1) == ["id2", "id3", "id4"]
    p2 = lset(
        {"id2": "NOT_METADISCOURSE", "id3": "UNSURE"},
        "maintainer_pass2",
        expected=["id2", "id3", "id4"],
    )
    final, info = A.combine_maintainer_passes(p1, p2)
    assert final.label("id1") == "CORRECT" and final.labels["id1"]["pass"] == 1
    assert final.label("id2") == "NOT_METADISCOURSE"
    assert final.labels["id2"]["pass"] == 2 and final.labels["id2"]["pass1_label"] == "UNSURE"
    assert final.label("id3") == "UNSURE"
    assert final.label("id4") == "UNSURE"  # missing in pass 2: stays unresolved
    assert final.labels["id4"]["second_pass"] == "missing_or_invalid"
    assert A.outcome_value("metadiscourse", "STRICT", final.label("id4")) is None
    assert info["pass1_unsure"] == 3 and info["resolved_in_second_pass"] == 1
    assert info["unsure_again"] == 1 and info["second_pass_missing_or_invalid"] == 1
    final0, info0 = A.combine_maintainer_passes(p1, None)
    assert final0.label("id2") == "UNSURE" and info0["second_pass_given"] is False


def test_second_pass_items_outside_the_assignment_are_rejected():
    rows = fix_n([key_row(i) for i in range(1, 4)])
    items = {r["id"]: item_for(r) for r in rows}
    p1 = A.validate_lines(
        [
            J(id="id1", label="CORRECT"),
            J(id="id2", label="UNSURE", note="CORRECT or NOT_METADISCOURSE: x"),
        ],
        items,
        ["id1", "id2"],
        "maintainer",
    )
    p2 = A.validate_lines(
        [J(id="id1", label="NOT_METADISCOURSE"), J(id="id2", label="CORRECT")],
        items,
        A.second_pass_ids(p1),
        "maintainer_pass2",
    )
    assert p2.label("id1") is None and p2.label("id2") == "CORRECT"
    assert any("not_assigned" in str(x) or "not assigned" in str(x) for x in p2.problems)
    final, _ = A.combine_maintainer_passes(p1, p2)
    assert final.label("id1") == "CORRECT"  # a second-pass label never overrides pass 1


def test_second_pass_is_used_by_the_maintainer_analyses():
    rows = fix_n([key_row(i, sub="s", N=200) for i in range(40)])
    labs = {r["id"]: "CORRECT" for r in rows}
    mids = {r["id"] for r in rows[:20]}
    p1 = lset(
        {i: ("UNSURE" if int(i[2:]) < 10 else "CORRECT") for i in mids}, "maintainer", expected=mids
    )
    p2 = lset(
        {i: "NOT_METADISCOURSE" for i in A.second_pass_ids(p1)},
        "maintainer_pass2",
        expected=A.second_pass_ids(p1),
    )
    prim = [lset(labs, "A"), lset(labs, "B")]
    r1 = A.analyse(rows, prim, None, p1, mids)
    r2 = A.analyse(rows, prim, None, p1, mids, maintainer_pass2=p2)
    c1 = r1["maintainer_concordance"]["metadiscourse"]
    c2 = r2["maintainer_concordance"]["metadiscourse"]
    assert c1["definite_comparisons"] == 10 and c2["definite_comparisons"] == 20
    assert (
        c2["table"]["ref1_maint0"] == 10
        and r2["maintainer_passes"]["resolved_in_second_pass"] == 10
    )
    assert r2["maintainer_only"]["metadiscourse"]["STRICT"]["ALL"]["p"] == pytest.approx(0.5)
    assert r1["primary"] == r2["primary"]
    assert c2["maintainer_passes"] == {
        "second_pass_given": True,
        "pass1_unsure": 10,
        "resolved_in_second_pass": 10,
        "unsure_again": 0,
        "second_pass_missing_or_invalid": 0,
    }
    assert c1["maintainer_passes"]["second_pass_given"] is False
    md = A.to_markdown(A.clean_json(r2))
    assert "second pass" in md.lower()


def test_completion_bounds():
    assert A._completion(1, 0) == (1, 1)
    assert A._completion(1, None) == (0, 1)
    assert A._completion(None, 1) == (-1, 0)  # [-H, 1-H]
    assert A._completion(None, 0) == (0, 1)
    assert A._completion(None, None) == (-1, 1)


# --- full pipeline -------------------------------------------------------------------------


def _synthetic_build(tmp_path):
    rows = []
    for i, c in enumerate(A.MD_CATEGORIES * 8):
        rows.append(
            key_row(
                i,
                stratum=c,
                sub="rest",
                N=60 + 10 * A.MD_CATEGORIES.index(c),
                register=A.REGISTERS[i % 3],
                dimension="interactive" if c in A.MD_CATEGORIES[:5] else "interactional",
            )
        )
    for i in range(30):
        rows.append(
            key_row(
                200 + i,
                module="phrase",
                stratum=f"K{1 + i % 3}-single",
                sub="rest",
                N=150,
                k_band=1 + i % 3,
                register=A.REGISTERS[i % 3],
            )
        )
    fix_n(rows)
    items = {
        r["id"]: item_for(r, others=["OTHER SENSE"] if r["module"] == "phrase" else ())
        for r in rows
    }
    for r in rows:
        r["in_maintainer_sample"] = int(r["id"][2:]) % 3 == 0
    by = {}
    for r in rows:
        by.setdefault(r["substratum"], 0)
        by[r["substratum"]] += r["in_maintainer_sample"]
    for r in rows:
        r["m_sub"] = by[r["substratum"]]
    regs = {}
    for r in rows:
        regs.setdefault(r["substratum"], {g: 0 for g in A.REGISTERS})
    for h, d in regs.items():
        big_n = next(r["N_sub"] for r in rows if r["substratum"] == h)
        d["academic"], d["general"] = big_n // 2, big_n // 3
        d["argumentative"] = big_n - d["academic"] - d["general"]
    fr = frame_for(rows, regs)
    (tmp_path / "key.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "items.jsonl").write_text("".join(json.dumps(items[r["id"]]) + "\n" for r in rows))
    (tmp_path / "frame.json").write_text(json.dumps(fr))
    return rows, items, fr


def test_full_analysis_on_synthetic_labels(tmp_path):
    rows, items, fr = _synthetic_build(tmp_path)
    a = A.validate_lines(
        [json.dumps(x) for x in A.make_dummy_labels(rows, items, 1)], items, name="A"
    )
    b = A.validate_lines(
        [json.dumps(x) for x in A.make_dummy_labels(rows, items, 2)], items, name="B"
    )
    need = A.needs_adjudication(rows, [a, b])
    c = A.validate_lines(
        [
            json.dumps(x)
            for x in A.make_dummy_labels([r for r in rows if r["id"] in need], items, 4)
        ],
        items,
        need,
        "C",
    )
    mids = {r["id"] for r in rows if r["in_maintainer_sample"]}
    m = A.validate_lines(
        [
            json.dumps(x)
            for x in A.make_dummy_labels([r for r in rows if r["id"] in mids], items, 3)
        ],
        items,
        mids,
        "maintainer",
    )
    orders = B.make_orders(sorted(items), sorted(mids), 5, batch_size=25)
    assert A.validate_design(rows, list(items.values()), sorted(mids), orders, fr) == []
    rep = A.clean_json(A.analyse(rows, [a, b], c, m, mids, orders, fr))
    json.dumps(rep, allow_nan=False)  # standard JSON: no Infinity / NaN
    md = rep["model_reference"]["metadiscourse"]
    assert set(md) == {"STRICT", "LENIENT", "CONNECTIVE"}
    assert md["STRICT"]["ALL"]["n_items"] == 80
    assert md["STRICT"]["register=academic"]["population_exact"]
    assert md["STRICT"]["register=academic"]["exploratory"]
    assert "label_counts" in rep["maintainer_only"]["metadiscourse"]["STRICT"]["ALL"]
    assert set(rep["sensitivity_single_primary"]) == {"A", "B"}
    assert set(rep["batches"]) == {"A", "B"}
    assert all(
        e["df_status"] in ("finite", "too_small", "infinite", "undefined")
        for e in md["STRICT"].values()
    )
    text = A.to_markdown(rep)
    assert "Concordance with the maintainer (descriptive)" in text and "Label counts" in text
    assert "no equivalence, adequacy" in text and "equivalen" not in json.dumps(rep).lower()
    assert "not shown" not in text.lower() and "equivalent" not in text.lower()
    assert "simultaneous" in text and "pointwise" in text
    assert md["STRICT"]["ALL"]["confirmatory"] and not md["LENIENT"]["ALL"]["confirmatory"]
    assert "human" not in json.dumps(rep).lower()


def test_primary_section_shows_warnings():
    rows = fix_n([key_row(1, sub="a", N=50)] + [key_row(i, sub="b", N=500) for i in range(2, 30)])
    labs = {r["id"]: "CORRECT" if int(r["id"][2:]) % 4 else "NOT_METADISCOURSE" for r in rows}
    rep = A.analyse(rows, [lset(labs, "A"), lset(labs, "B")])
    assert rep["primary"]["metadiscourse"]["warnings"]
    text = A.to_markdown(rep)
    assert "Warnings affecting these estimates" in text.split("## Concordance")[0]
    assert "Primary results" in text and "co-primary" in text


def test_cli_end_to_end(tmp_path):
    _synthetic_build(tmp_path)
    key = tmp_path / "key.jsonl"
    d = tmp_path / "dummy"
    assert A.main(["--key", str(key), "--write-dummy", str(d)]) == 0
    out_json, out_md, retry = tmp_path / "rep.json", tmp_path / "rep.md", tmp_path / "retry"
    args = ["--key", str(key), "--labels", f"A={d / 'A.jsonl'}", f"B={d / 'B.jsonl'}"]
    args += ["--adjudicator", f"C={d / 'C.jsonl'}", "--maintainer", str(d / "maintainer.jsonl")]
    assert (
        A.main(
            [*args, "--retry-manifest", str(retry), "--json", str(out_json), "--md", str(out_md)]
        )
        == 0
    )
    rep = json.loads(out_json.read_text())
    assert rep["labellers"]["primaries"] == ["A", "B"]
    assert rep["labellers"]["maintainer_second_pass"] is False
    ids_out = tmp_path / "pass2_ids.txt"
    assert A.main([*args, "--second-pass-ids", str(ids_out)]) == 0
    pass1 = [json.loads(x) for x in (d / "maintainer.jsonl").read_text().splitlines()]
    assert ids_out.read_text().split() == sorted(r["id"] for r in pass1 if r["label"] == "UNSURE")
    assert ids_out.read_text().split()
    out2 = tmp_path / "rep2.json"
    args2 = [*args, "--maintainer-pass2", str(d / "maintainer_pass2.jsonl")]
    assert A.main([*args2, "--json", str(out2), "--md", str(tmp_path / "rep2.md")]) == 0
    rep2 = json.loads(out2.read_text())
    assert rep2["labellers"]["maintainer_second_pass"] is True
    # the synthetic files follow the registered workflow: validated pass 1, stamped pass 2
    mf = rep2["maintainer_files"]
    assert mf["mode"] == "registered" and mf["pass1_validated_form"] is True
    assert mf["pass2_stamps"]["unstamped"] == 0 and mf["pass2_stamps"]["stamped"] > 0
    assert rep2["maintainer_passes"]["pass1_unsure"] == len(ids_out.read_text().split())
    assert rep2["primary"] == rep["primary"]
    man = [json.loads(x) for x in (retry / "retry_A.jsonl").read_text().splitlines()]
    assert len(man) == 1 and man[0]["reason"] == "missing"
    (tmp_path / "retryA.jsonl").write_text(J(id=man[0]["id"], label="CORRECT") + "\n")
    merged = tmp_path / "A.merged.jsonl"
    assert (
        A.main(
            [
                "--merge-retry",
                str(d / "A.jsonl"),
                str(tmp_path / "retryA.jsonl"),
                "--manifest",
                str(retry / "retry_A.jsonl"),
                "--merged-out",
                str(merged),
            ]
        )
        == 0
    )
    items = {
        json.loads(x)["id"]: json.loads(x)
        for x in (tmp_path / "items.jsonl").read_text().splitlines()
    }
    ls = A.load_labels(merged, items)
    assert not ls.retry and not ls.problems


def test_cli_stops_on_design_problems(tmp_path):
    rows, _, _ = _synthetic_build(tmp_path)
    with (tmp_path / "key.jsonl").open("a") as f:
        f.write(json.dumps(rows[0]) + "\n")
    with pytest.raises(SystemExit):
        A.main(["--key", str(tmp_path / "key.jsonl"), "--validate-only"])


# --- build, frame and batches ---------------------------------------------------------------


def test_allocate_maintainer_minimum_proportional_and_caps():
    subs = {"a": (5000, 85), "b": (100, 15), "c": (40, 1), "d": (900, 40), "e": (3, 3)}
    alloc = build.allocate_maintainer(subs, 60)
    assert sum(alloc.values()) == 60 and alloc["c"] == 1 and alloc["b"] >= 2 and alloc["e"] >= 2
    assert all(alloc[h] <= n for h, (_, n) in subs.items()) and alloc["a"] > alloc["d"] > alloc["b"]
    assert build.allocate_maintainer(subs, 10_000) == {h: n for h, (_, n) in subs.items()}
    with pytest.raises(ValueError):
        build.allocate_maintainer(subs, 5)


def test_registered_maintainer_totals_and_phrase_census():
    assert build.MAINTAINER_TOTALS == {"metadiscourse": 300, "phrase": 300}
    subs = {"K1|a": (4000, 120), "K2|b": (900, 100), "K3|c": (50, 50), "K1|d": (30, 2)}
    assert build.allocate_maintainer(subs, 300) == {h: n for h, (_, n) in subs.items()}
    assert build.allocate_maintainer(subs, 272) == {h: n for h, (_, n) in subs.items()}
    md = {f"c{i}": (100 * (i + 1) ** 2, 40) for i in range(20)}
    alloc = build.allocate_maintainer(md, 300)
    assert sum(alloc.values()) == 300 and min(alloc.values()) >= 2
    assert alloc["c19"] > alloc["c10"] > alloc["c0"] == 2 and max(alloc.values()) <= 40


def test_two_phase_census_equals_the_one_phase_estimate():
    rows = fix_n(
        [key_row(i, sub="h1", N=100) for i in range(8)]
        + [key_row(i, sub="h2", N=300) for i in range(8, 20)]
    )
    y = {r["id"]: int(int(r["id"][2:]) % 3 != 0) for r in rows}
    one = A.estimate(rows, ref_of(y))
    two = A.estimate(rows, {i: {"y": v} for i, v in y.items()}, phase_ids=set(y))
    for k in ("p", "ci95_exact", "region95_exact", "var", "N_hat", "represented_share"):
        assert two[k] == pytest.approx(one[k]), k


def test_maintainer_sample_covers_every_substratum():
    key = []
    for h, (big_n, n) in {"x": (1000, 30), "y": (20, 2), "z": (300, 10)}.items():
        key += [
            {"id": f"{h}{i}", "module": "metadiscourse", "substratum": h, "N_sub": big_n}
            for i in range(n)
        ]
    key += [{"id": f"p{i}", "module": "phrase", "substratum": "p", "N_sub": 50} for i in range(5)]
    build.SEED = 99
    try:
        ids, allocs = build.maintainer_sample(key, {"metadiscourse": 12, "phrase": 3})
        got = {h: sum(1 for i in ids if i.startswith(h)) for h in "xyz"}
        assert got == allocs["metadiscourse"] and min(got.values()) >= 2 and sum(got.values()) == 12
        assert ids == build.maintainer_sample(key, {"metadiscourse": 12, "phrase": 3})[0]
    finally:
        build.SEED = build.DEV_SEED


def test_exclusions_cover_every_identifier_type(tmp_path):
    dev = [
        {
            "source": "Europe PMC",
            "source_id": "PMC123",
            "url": "https://europepmc.org/article/PMC/PMC123",
            "fulltext_url": "https://x/PMC123/fullTextXML",
            "doi": "10.1/ABC",
            "title": "A  Study",
        },
        {
            "source": "English Wikipedia",
            "source_id": "pageid:42",
            "url": "https://en.wikipedia.org/w/index.php?oldid=777",
            "revid": 777,
            "title": "Justice",
        },
    ]
    p = tmp_path / "texts.jsonl"
    p.write_text("".join(json.dumps(t) + "\n" for t in dev) + "PMC999\n")
    ex = build.read_exclusions(p)
    build.EXCLUDE = ex
    try:
        assert build.excluded("pmc123") and build.excluded("https://doi.org/10.1/abc")
        assert build.excluded("a study") and build.excluded("https://x/PMC123/fullTextXML")
        assert build.excluded("pageid:42") and build.excluded(
            "https://en.wikipedia.org/w/index.php?oldid=777"
        )
        assert build.excluded("PMC999") and not build.excluded("PMC5")
    finally:
        build.EXCLUDE = set()
    fresh = [
        {
            "source": "English Wikipedia",
            "source_id": "pageid:43",
            "url": "u43",
            "revid": 1,
            "title": "Law",
        }
    ]
    assert build.exclusion_overlap(fresh, ex) == []
    clash = [{"source": "Europe PMC", "source_id": "PMC777", "title": "a study", "doi": None}]
    assert build.exclusion_overlap(clash, ex) == ["a study"]


@pytest.mark.parametrize(
    "args,msg",
    [
        (["--set", "evaluation", "--seed", "5", "--dev-texts", "/nonexistent"], "not found"),
        (["--set", "development", "--seed", "5"], "seed 20261016"),
    ],
)
def test_build_refuses_unsafe_configurations(tmp_path, args, msg):
    with pytest.raises(SystemExit, match=msg):
        build.main([*args, "--out", str(tmp_path / "o")])


def test_build_refuses_dev_seed_for_evaluation_and_existing_outputs(tmp_path):
    ex = tmp_path / "ex.txt"
    ex.write_text("PMC1\n")
    with pytest.raises(SystemExit, match="new --seed"):
        build.main(
            ["--set", "evaluation", "--exclude-texts", str(ex), "--out", str(tmp_path / "o")]
        )
    out = tmp_path / "built"
    out.mkdir()
    (out / "key.jsonl").write_text("{}\n")
    with pytest.raises(SystemExit, match="already holds a build"):
        build.main(["--out", str(out)])


def test_evaluation_always_excludes_the_verified_development_manifest(tmp_path, monkeypatch):
    fake = tmp_path / "texts.jsonl"
    fake.write_text(json.dumps({"source_id": "PMC1", "register": "academic"}) + "\n")
    with pytest.raises(SystemExit, match="not the canonical development manifest"):
        build.main(
            [
                "--set",
                "evaluation",
                "--seed",
                "5",
                "--dev-texts",
                str(fake),
                "--out",
                str(tmp_path / "o"),
            ]
        )
    monkeypatch.setattr(build, "DEV_TEXTS_SHA256", hashlib.sha256(fake.read_bytes()).hexdigest())
    with pytest.raises(SystemExit, match="expected 120"):
        build.load_dev_exclusions(fake)
    if build.DEV_TEXTS.exists():
        monkeypatch.undo()
        refs, info = build.load_dev_exclusions(build.DEV_TEXTS)
        assert info["n_texts"] == 120 and info["sha256"] == build.DEV_TEXTS_SHA256
        dev = [json.loads(x) for x in build.DEV_TEXTS.read_text().splitlines() if x.strip()]
        assert all(build.text_refs(t) <= refs for t in dev)
        assert build.exclusion_overlap(dev, refs)


def test_batches_cli_rejects_duplicates_before_writing(tmp_path):
    rows, items, _ = _synthetic_build(tmp_path)
    with (tmp_path / "items.jsonl").open("a") as f:
        f.write(json.dumps(dict(items[rows[0]["id"]], claimed={"category": "boosters"})) + "\n")
    with pytest.raises(SystemExit, match="duplicate item id"):
        B.main(["--dir", str(tmp_path), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()
    _synthetic_build(tmp_path)
    ids = tmp_path / "ids.txt"
    ids.write_text(f"{rows[0]['id']}\n{rows[0]['id']}\n")
    assert B.main(["--dir", str(tmp_path), "--out", str(tmp_path / "o")]) == 0
    with pytest.raises(SystemExit, match="requested ids: duplicate"):
        B.main(
            [
                "--dir",
                str(tmp_path),
                "--orders",
                str(tmp_path / "o" / "orders.json"),
                "--role",
                "A",
                "--ids",
                str(ids),
                "--out",
                str(tmp_path / "o"),
                "--prefix",
                "retry",
            ]
        )


def test_frame_from_hits_and_design_check():
    design = {
        "metadiscourse": {
            "hedges": {"substrata": {"marker=may": {"N": 2, "n": 2}, "rest": {"N": 1, "n": 1}}}
        },
        "phrase": {"K1-single": {"substrata": {"rest": {"N": 1, "n": 1}}}},
    }
    hits = [
        {"module": "metadiscourse", "category": "hedges", "marker": "may", "text_id": "T1"},
        {"module": "metadiscourse", "category": "hedges", "marker": "may", "text_id": "T2"},
        {"module": "metadiscourse", "category": "hedges", "marker": "often", "text_id": "T2"},
        {"module": "phrase", "k_band": 1, "rank": 5, "phrase": "A BIT", "text_id": "T1"},
    ]
    fr = F.build_frame(hits, {"T1": "academic", "T2": "general"}, design, set())
    assert fr["modules"]["metadiscourse"]["hedges|marker=may"] == {
        "N": 2,
        "by_register": {"academic": 1, "general": 1},
    }
    assert fr["checks"]["design_N_match"]
    design["metadiscourse"]["hedges"]["substrata"]["rest"]["N"] = 5
    assert not F.build_frame(hits, {"T1": "academic", "T2": "general"}, design, set())["checks"][
        "design_N_match"
    ]


def test_orders_independent_seeded_and_checked():
    ids = [f"i{k:03d}" for k in range(700)]
    o1 = B.make_orders(ids, ids[:50], 1)
    assert o1 == B.make_orders(ids, ids[:50], 1)
    assert o1["roles"]["A"]["order"] != o1["roles"]["B"]["order"]
    assert [len(b) for b in B.batches_for(o1, "A")] == [325, 325, 50]
    assert sum(len(b) for b in B.batches_for(o1, "adjudicator", set(ids[:10]))) == 10
    with pytest.raises(ValueError, match="not in role"):
        B.batches_for(o1, "maintainer", {ids[600]})
    with pytest.raises(ValueError):
        B.make_orders(ids, [], 1, batch_size=0)
    with pytest.raises(ValueError):
        B.make_orders([*ids, ids[0]], [], 1)
    ls = A.LabelSet("A", {i: {"label": "CORRECT"} for i in ids}, ids)
    assert A.batch_of(ls, o1)[o1["roles"]["A"]["order"][400]] == 2


def test_batch_files_fresh_or_atomically_replaced(tmp_path):
    ids = [f"i{k:03d}" for k in range(700)]
    items = {i: {"id": i} for i in ids}
    o = B.make_orders(ids, ids[:10], 1)
    paths = B.write_batches(items, o, "adjudicator", tmp_path, prefix="adjudication")
    assert len(paths) == 3
    with pytest.raises(FileExistsError):
        B.write_batches(items, o, "adjudicator", tmp_path, {ids[0]}, prefix="adjudication")
    paths = B.write_batches(
        items, o, "adjudicator", tmp_path, {ids[0]}, prefix="adjudication", replace=True
    )
    d = paths[0].parent
    assert sorted(p.name for p in d.iterdir()) == [
        "adjudication_01.jsonl",
        "adjudication_manifest.json",
    ]
    man = json.loads((d / "adjudication_manifest.json").read_text())
    assert man["n"] == 1 and man["batches"][0]["ids"] == [ids[0]] and man["restricted_to_ids"]
    assert not [p for p in d.parent.iterdir() if p.name.startswith(".")]  # no temp leftovers


# --- maintainer page ----------------------------------------------------------------------


def test_guideline_anchors_used_by_the_page_exist():
    guide = (A.REPO / "docs" / "validation" / "study4-guidelines.md").read_text()
    assert "## Part B." in guide
    for c in A.MD_CATEGORIES:
        assert f"#### `{c}`" in guide


def test_page_builds_with_label_rules(tmp_path):
    rows, items, _ = _synthetic_build(tmp_path)
    orders = B.make_orders(sorted(items), [r["id"] for r in rows if r["in_maintainer_sample"]], 3)
    (tmp_path / "orders.json").write_text(json.dumps(orders))
    out = tmp_path / "page.html"
    human_page.main(["--dir", str(tmp_path), "--out", str(out)])
    html = out.read_text()
    for needle in (
        "EXTERNAL_CONNECTIVE",
        "WRONG_SENSE_LISTED",
        "WRONG_SENSE_UNLISTED",
        '<option value="">— choose —</option>',
        "c !== it.claimed.category",
        "a.download = EXPORT_PREFIX + `${done.length}of${ITEMS.length}.jsonl`",
        '"maintainer_";',
        'it.claimed.category === "transitions"',
        '"#### `" + it.claimed.category + "`"',
        '"## Part B."',
        "normSense(o) === normSense(alt)",
        "function unsureProblem(note, module)",
        "/^\\s*([^:]+):\\s*\\S/",
        "split(/\\s+or\\s+/)",
        "words(alt) > 6",
        "words(note) > 25",
    ):
        assert needle in html, needle
    assert "const PASS = 1;" in html


def _unsure_note(item, tag=""):
    other = "NOT_METADISCOURSE" if item["module"] == "metadiscourse" else "NOT_THE_EXPRESSION"
    return f"CORRECT or {other}: note {tag}".strip()


def _page_setup(tmp_path):
    rows, items, _ = _synthetic_build(tmp_path)
    mids = [r["id"] for r in rows if r["in_maintainer_sample"]]
    orders = B.make_orders(sorted(items), mids, 3)
    (tmp_path / "orders.json").write_text(json.dumps(orders))
    return items, orders["roles"]["maintainer"]["order"]


def _page_ids(html):
    return [
        it["id"] for it in json.loads(html.split("const ITEMS = ")[1].split(";\nconst GUIDE")[0])
    ]


def _validate_pass1(tmp_path, raw, name="validated", retry=None, manifest=None):
    out, log = tmp_path / f"{name}.jsonl", tmp_path / f"{name}.log.json"
    argv = ["--key", str(tmp_path / "key.jsonl"), "--validate-pass1", str(raw)]
    if retry is not None:
        argv += ["--pass1-retry", str(retry), "--manifest", str(manifest)]
    assert A.main([*argv, "--validated-out", str(out), "--validation-log", str(log)]) == 0
    return out, json.loads(log.read_text())


def test_second_pass_page_holds_only_first_pass_unsure_items(tmp_path):
    items, order = _page_setup(tmp_path)
    unsure = set(order[1::4])
    lines = [
        J(id=i, label="UNSURE", note=_unsure_note(items[i], i))
        if i in unsure
        else J(id=i, label="CORRECT")
        for i in order
    ]
    raw = tmp_path / "maintainer_raw.jsonl"
    raw.write_text("\n".join(lines) + "\n")
    out = tmp_path / "p2.html"
    # a raw export (valid, but not the validated file) is refused, pointing to the command
    with pytest.raises(SystemExit) as e:
        human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(raw)])
    assert "not in validated form" in str(e.value) and "--validate-pass1" in str(e.value)
    assert "fix them" not in str(e.value) and not out.exists()
    p1, _ = _validate_pass1(tmp_path, raw)
    human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(p1)])
    html = out.read_text()
    assert _page_ids(html) == [i for i in order if i in unsure]
    assert "const PASS = 2;" in html and '"maintainer_pass2_"' in html
    assert "study4-maintainer-pass2-" in html
    sha = hashlib.sha256(p1.read_bytes()).hexdigest()
    assert f'const PASS1_SHA = "{sha}";' in html and "store[it.id].pass1_sha256 = PASS1_SHA" in html
    assert f"note {sorted(unsure)[0]}" in html
    shown = json.loads(html.split("const ITEMS = ")[1].split(";\nconst GUIDE")[0])
    assert "model" not in json.dumps(shown).lower()  # still blind
    p1.write_text(J(id="zz", label="UNSURE", note="CORRECT or NOT_METADISCOURSE: x") + "\n")
    with pytest.raises(SystemExit, match="unknown_id"):
        human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(p1)])


@pytest.mark.parametrize(
    "case,reason",
    [
        ("invalid_note", "unsure_without_note"),
        ("invalid_alt", "alt"),
        ("missing_keys", "missing_field"),
        ("conflicting_duplicate", "duplicate"),
        ("identical_duplicate", None),
        ("missing_item", None),
    ],
)
def test_page_and_analyser_second_pass_assignments_agree(tmp_path, case, reason):
    items, order = _page_setup(tmp_path)
    md = [i for i in order if items[i]["module"] == "metadiscourse"]
    u1, u2, bad = md[0], md[1], md[2]
    recs = {i: J(id=i, label="CORRECT") for i in order}
    recs[u1] = J(id=u1, label="UNSURE", note=_unsure_note(items[u1]))
    recs[u2] = J(id=u2, label="UNSURE", note=_unsure_note(items[u2]))
    extra = []
    if case == "invalid_note":
        recs[bad] = J(id=bad, label="UNSURE", note=None)  # Sol's example
    elif case == "invalid_alt":
        recs[bad] = J(
            id=bad, label="WRONG_CATEGORY", alt_category=items[bad]["claimed"]["category"]
        )
    elif case == "missing_keys":
        recs[bad] = json.dumps({"id": bad, "label": "UNSURE"})
    elif case == "conflicting_duplicate":
        extra = [J(id=u1, label="CORRECT")]
    elif case == "identical_duplicate":
        extra = [recs[u1]]
    elif case == "missing_item":
        del recs[bad]
    raw = tmp_path / "maintainer_raw.jsonl"
    raw.write_text("\n".join([*recs.values(), *extra]) + "\n")
    key = str(tmp_path / "key.jsonl")
    out = tmp_path / "p2.html"
    # the raw export is refused by the page; invalid records are listed with their reason
    with pytest.raises(SystemExit) as e:
        human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(raw)])
    msg = str(e.value)
    assert "--validate-pass1" in msg and "by hand" in msg and not out.exists()
    if reason is not None:
        assert "invalid first-pass record" in msg and reason in msg, msg
    # the validated file keeps exactly the accepted records; the page builds from it
    p1, log = _validate_pass1(tmp_path, raw)
    ids_out = tmp_path / "ids.txt"
    assert A.main(["--key", key, "--maintainer", str(p1), "--second-pass-ids", str(ids_out)]) == 0
    analyser = ids_out.read_text().split()
    human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(p1)])
    assert _page_ids(out.read_text()) == [i for i in order if i in set(analyser)]
    assert sorted(analyser) == log["second_pass_ids"]
    # the same assignment as the (non-registered) analyser on the raw export
    raw_ids = tmp_path / "raw_ids.txt"
    argv = ["--key", key, "--maintainer", str(raw), "--second-pass-ids", str(raw_ids)]
    with pytest.raises(SystemExit, match="not a validated first-pass file"):
        A.main(argv)
    assert A.main([*argv, "--nonregistered-legacy"]) == 0
    assert raw_ids.read_text().split() == analyser
    assert bad not in analyser
    non_votes = {r["id"]: r["reason"] for r in log["non_vote_ids"]}
    if reason is not None:
        rejected = non_votes[u1 if case == "conflicting_duplicate" else bad]
        assert reason in rejected
        assert any(reason in p["reason"] for p in log["rejected_lines"])
    if case == "conflicting_duplicate":
        assert u1 not in analyser
    if case == "missing_item":
        assert non_votes[bad] == "missing"
    if case == "identical_duplicate":
        assert log["collapsed_duplicates"] and not log["rejected_lines"]


def test_validated_pass1_with_retry_is_deterministic_and_logged(tmp_path):
    items, order = _page_setup(tmp_path)
    md = [i for i in order if items[i]["module"] == "metadiscourse"]
    u, bad, gone = md[0], md[1], md[2]
    recs = {i: J(id=i, label="CORRECT", labelled_at="t") for i in order}
    recs[u] = J(id=u, label="UNSURE", note=_unsure_note(items[u]))
    recs[bad] = J(id=bad, label="UNSURE", note=None)
    del recs[gone]
    raw = tmp_path / "raw.jsonl"
    raw.write_text("\n".join(recs.values()) + "\nnot json\n")
    key = str(tmp_path / "key.jsonl")
    # the registered retry manifest comes from validating the raw export
    retry_dir = tmp_path / "retry"
    argv = ["--key", key, "--maintainer", str(raw), "--validate-only"]
    assert A.main([*argv, "--retry-manifest", str(retry_dir)]) == 0
    manifest = retry_dir / "retry_maintainer.jsonl"
    assert A.read_id_file(manifest) == sorted([bad, gone])
    retry = tmp_path / "retry_export.jsonl"
    retry.write_text(J(id=bad, label="UNSURE", note=_unsure_note(items[bad])) + "\n")
    v1, log = _validate_pass1(tmp_path, raw, "v1", retry, manifest)
    v2, log2 = _validate_pass1(tmp_path, raw, "v2", retry, manifest)
    assert v1.read_bytes() == v2.read_bytes()  # deterministic
    assert log["output_sha256"] == A.file_sha256(v1) == log["output"]["sha256"]
    assert {k: log[k] for k in log if k not in ("tool", "output")} == {
        k: log2[k] for k in log2 if k not in ("tool", "output")
    }
    assert log["inputs"]["raw_first_pass"]["sha256"] == A.file_sha256(raw)
    assert log["inputs"]["retry_export"]["sha256"] == A.file_sha256(retry)
    assert log["inputs"]["retry_manifest"]["sha256"] == A.file_sha256(manifest)
    assert log["inputs"]["key"]["sha256"] == A.file_sha256(tmp_path / "key.jsonl")
    assert log["tool"]["analyse_sha256"] == A.file_sha256(Path(A.__file__))
    assert log["retry_given"] and log["retry_manifest_ids"] == sorted([bad, gone])
    assert log["second_pass_ids"] == sorted([u, bad])
    assert {r["id"]: r["reason"] for r in log["non_vote_ids"]} == {gone: "missing"}
    raw_rejected = {(p["id"], p["reason"]) for p in log["raw_rejected_lines"]}
    assert (None, "malformed_json") in raw_rejected and (bad, "unsure_without_note") in raw_rejected
    assert "dropped a malformed original line" in log["merge_notes"]
    assert log["rejected_lines"] == []  # after the retry, nothing invalid remains
    lines = v1.read_text().splitlines()
    assert [json.loads(x)["id"] for x in lines] == sorted(set(order) - {gone})
    assert json.loads(lines[0]).get("labelled_at") in ("t", None)  # metadata kept
    assert A.validated_form_problems(v1, items, order) == []
    # no overwriting; the manifest must be the raw file's own retry list
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        _validate_pass1(tmp_path, raw, "v1", retry, manifest)
    manifest.write_text(json.dumps({"id": bad}) + "\n")  # a selective retry
    with pytest.raises(SystemExit, match="own retry list"):
        _validate_pass1(tmp_path, raw, "v3", retry, manifest)


def test_zero_item_second_pass_exits_cleanly(tmp_path, capsys):
    items, order = _page_setup(tmp_path)
    raw = tmp_path / "maintainer_raw.jsonl"
    raw.write_text("".join(J(id=i, label="CORRECT") + "\n" for i in order))
    p1, _ = _validate_pass1(tmp_path, raw)
    out = tmp_path / "p2.html"
    human_page.main(["--dir", str(tmp_path), "--out", str(out), "--second-pass", str(p1)])
    assert human_page.NO_SECOND_PASS in capsys.readouterr().out
    assert human_page.NO_SECOND_PASS == "No second-pass items: your first pass had no UNSURE labels"
    assert not out.exists()


def _stamp_setup(tmp_path):
    items, order = _page_setup(tmp_path)
    u, w = order[0], order[1]
    raw = tmp_path / "maintainer_raw.jsonl"
    raw.write_text(
        "".join(
            (
                J(id=i, label="UNSURE", note=_unsure_note(items[i]))
                if i in (u, w)
                else J(id=i, label="CORRECT")
            )
            + "\n"
            for i in order
        )
    )
    p1, _ = _validate_pass1(tmp_path, raw)
    return raw, p1, u, w


def test_pass2_from_a_different_first_pass_is_rejected(tmp_path):
    raw, p1, u, w = _stamp_setup(tmp_path)
    p2 = tmp_path / "pass2.jsonl"
    key = str(tmp_path / "key.jsonl")
    base = ["--key", key, "--maintainer", str(p1), "--maintainer-pass2", str(p2), "--validate-only"]
    p2.write_text(J(id=u, label="CORRECT", pass1_sha256="0" * 64) + "\n")
    with pytest.raises(SystemExit, match="different first-pass file"):
        A.main(base)
    with pytest.raises(SystemExit, match="different first-pass file"):
        A.main([*base, "--nonregistered-legacy"])
    # the raw export's hash is not the pass-1 stamp: the validated file's is
    p2.write_text(J(id=u, label="CORRECT", pass1_sha256=A.file_sha256(raw)) + "\n")
    with pytest.raises(SystemExit, match="different first-pass file"):
        A.main(base)
    p2.write_text(J(id=u, label="CORRECT", pass1_sha256=A.file_sha256(p1)) + "\n")
    assert A.main(base) == 0


@pytest.mark.parametrize(
    "stamp",
    [[], 123, None, {"a": 1}, "A" * 64, "0" * 63, "0" * 65, " " + "0" * 64, "g" * 64, ""],
)
def test_malformed_pass1_stamps_fail_cleanly(tmp_path, stamp):
    raw, p1, u, w = _stamp_setup(tmp_path)
    p2 = tmp_path / "pass2.jsonl"
    good = A.file_sha256(p1)
    p2.write_text(
        J(id=u, label="CORRECT", pass1_sha256=good)
        + "\n"
        + J(id=w, label="CORRECT", pass1_sha256=stamp)
        + "\n"
    )
    base = ["--key", str(tmp_path / "key.jsonl"), "--maintainer", str(p1)]
    for extra in ([], ["--nonregistered-legacy"]):
        with pytest.raises(SystemExit, match="64-character lowercase hexadecimal"):
            A.main([*base, "--maintainer-pass2", str(p2), "--validate-only", *extra])
    # checked before any set is built, also on a record the validator rejects
    p2.write_text(
        J(id=u, label="CORRECT", pass1_sha256=good)
        + "\n"
        + json.dumps({"id": w, "label": "CORRECT", "pass1_sha256": stamp})
        + "\n"
    )
    with pytest.raises(SystemExit, match="64-character lowercase hexadecimal"):
        A.main([*base, "--maintainer-pass2", str(p2), "--validate-only"])
    ls = A.LabelSet("p2", {u: {"id": u, "label": "CORRECT", "pass1_sha256": stamp}}, [u])
    with pytest.raises(ValueError, match="64-character"):
        A.check_pass2_stamps([json.dumps({"id": u, "pass1_sha256": stamp})], ls, good, True)


def test_registered_mode_requires_every_stamp_and_the_validated_pass1(tmp_path):
    raw, p1, u, w = _stamp_setup(tmp_path)
    key = str(tmp_path / "key.jsonl")
    sha = A.file_sha256(p1)
    p2 = tmp_path / "pass2.jsonl"
    rep = tmp_path / "rep.json"
    d = tmp_path / "dummy"
    assert A.main(["--key", key, "--write-dummy", str(d)]) == 0
    prim = ["--labels", f"A={d / 'A.jsonl'}", f"B={d / 'B.jsonl'}"]
    full = ["--key", key, *prim, "--json", str(rep), "--md", str(tmp_path / "rep.md")]
    cases = {
        "unstamped": [J(id=u, label="CORRECT"), J(id=w, label="CORRECT")],
        "mixed": [J(id=u, label="CORRECT", pass1_sha256=sha), J(id=w, label="CORRECT")],
    }
    for name, lines in cases.items():
        p2.write_text("\n".join(lines) + "\n")
        argv = [*full, "--maintainer", str(p1), "--maintainer-pass2", str(p2)]
        with pytest.raises(SystemExit, match="lack pass1_sha256"):
            A.main(argv)
        assert A.main([*argv, "--nonregistered-legacy"]) == 0
        mf = json.loads(rep.read_text())["maintainer_files"]
        assert mf["mode"] == A.NONREGISTERED
        assert mf["pass2_stamps"]["unstamped"] == (2 if name == "unstamped" else 1)
        assert "NON-REGISTERED" in (tmp_path / "rep.md").read_text()
    p2.write_text(
        J(id=u, label="CORRECT", pass1_sha256=sha)
        + "\n"
        + J(id=w, label="UNSURE", note=None, pass1_sha256=sha)
        + "\n"
    )  # an invalid (rejected) second-pass record does not need to count as stamped
    assert A.main([*full, "--maintainer", str(p1), "--maintainer-pass2", str(p2)]) == 0
    mf = json.loads(rep.read_text())["maintainer_files"]
    assert mf["mode"] == "registered" and mf["pass1_validated_form"] is True
    assert mf["pass2_stamps"] == {
        "mode": "registered",
        "accepted_records": 1,
        "stamped": 1,
        "unstamped": 0,
    }
    assert "NON-REGISTERED" not in (tmp_path / "rep.md").read_text()
    # the raw first pass is refused as --maintainer in registered mode, with or without pass 2
    with pytest.raises(SystemExit, match="--validate-pass1"):
        A.main([*full, "--maintainer", str(raw)])
    assert A.main([*full, "--maintainer", str(raw), "--nonregistered-legacy"]) == 0
    assert json.loads(rep.read_text())["maintainer_files"]["pass1_validated_form"] is False
    # but validating the raw export (to write its retry manifest) is allowed
    assert A.main(["--key", key, "--maintainer", str(raw), "--validate-only"]) == 0


def test_practice_page_is_bannered_separate_and_outside_the_sample(tmp_path):
    items, order = _page_setup(tmp_path)
    outside = sorted(set(items) - set(order))[:4]
    ids = tmp_path / "practice.txt"
    ids.write_text("\n".join(outside) + "\n")
    out = tmp_path / "practice.html"
    human_page.main(["--dir", str(tmp_path), "--out", str(out), "--practice", str(ids)])
    html = out.read_text()
    assert _page_ids(html) == outside and "const PASS = 0;" in html
    assert "PRACTICE — not counted" in html and "study4-PRACTICE-not-counted-" in html
    assert '"PRACTICE_not_counted_"' in html
    ids.write_text(order[0] + "\n")
    with pytest.raises(SystemExit, match="in the maintainer sample"):
        human_page.main(["--dir", str(tmp_path), "--out", str(out), "--practice", str(ids)])
