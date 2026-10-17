"""Tests for the Study 4 fix-check harness.

    uv run pytest scripts/validation/study4_precision/fixcheck

No network, no real fix-check text, no spaCy except in the one worker test.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import analyse  # noqa: E402
import build  # noqa: E402
import estimators as E  # noqa: E402

from fixcheck import accept, assign, collect, crosswalk, ledger, sampling, worker  # noqa: E402
from fixcheck import crosswalk as X  # noqa: E402
from fixcheck.common import derive_seed, payload_sha256, read_json, read_jsonl  # noqa: E402

A = ledger.A


# --- fixtures --------------------------------------------------------------------------


def md_claimed(cat: str) -> dict:
    return {
        "category": cat,
        "dimension": "interactive" if cat in analyse.MD_CATEGORIES[:5] else "interactional",
    }


def mk(
    hid,
    span,
    claim="transitions",
    module="metadiscourse",
    text="1",
    ctx=None,
    marker="and",
    config="B",
):
    """A hit row as worker.py writes it (payload built from context, marker, claimed)."""
    if module == "metadiscourse":
        cl = {"category": claim}
        claimed = md_claimed(claim)
    else:
        cl = {"expression": claim, "rank": hash(claim) % 1000, "sense": None}
        claimed = {"expression": claim, "sense": None, "example": "e", "other_senses_in_list": []}
    payload = {
        "module": module,
        "context": ctx if ctx is not None else f"text{text} ⟦{marker}⟧ at {span[0]}",
        "marker": marker,
        "claimed": claimed,
    }
    return {
        "hit_id": f"{config}:{hid}",
        "config": config,
        "module": module,
        "text_id": f"T{text}",
        "source_id": f"S{text}",
        "text_sha256": f"h{text}",
        "span": list(span),
        "claim": cl,
        "claim_key": worker.claim_key(f"S{text}", f"h{text}", module, list(span), cl),
        "payload": payload,
        "payload_sha256": payload_sha256(payload),
    }


def cw(base, cand):
    bl, cl = crosswalk.crosswalk(base, cand)
    assert crosswalk.check_partition(base, cand, bl, cl) == []
    return bl, cl


def core(link):
    """The emitted-claim disposition of a baseline link (without the loss-layer fields)."""
    return {k: link[k] for k in ("change_type", "counterparts", "resolved")}


# --- ledger: J and a ------------------------------------------------------------------


def test_ledger_inventory():
    assert ledger.F == 12 and ledger.J == 68 and ledger.J == 4 * (ledger.F + 5)
    assert pytest.approx(0.05 / 68) == ledger.A and f"{ledger.A:.9f}" == "0.000735294"
    comps = ledger.ledger_components()
    ids = [c["id"] for c in comps]
    assert len(ids) == 68 == len(set(ids))
    pat = re.compile(
        r"^R[12]\.(metadiscourse|phrase)\.(MD-[A-I]|PH-[ABC]|COMPLETE)\."
        r"(removal|loss_STRICT|loss_INV|success_STRICT|success_INV)$"
    )
    assert all(pat.match(i) for i in ids)
    for rnd in (1, 2):
        for m in ledger.MODULES:
            sub = [c for c in comps if c["round"] == rnd and c["module"] == m]
            assert len(sub) == 17
            assert sum(c["kind"] == "removal" for c in sub) == 13
            assert {c["kind"] for c in sub if c["who"] == "COMPLETE"} == set(ledger.COMPONENT_KINDS)
    assert all(c["applicability"] == "reserved_round_2" for c in comps if c["round"] == 2)
    r1 = [c for c in comps if c["round"] == 1 and c["who"] in ledger.FAMILIES]
    assert sum(c["applicability"] == "applicable_if_frame_nonempty" for c in r1) == 12
    assert all(c["alpha"] == ledger.A for c in comps)
    # 45 proposed rules + SX-01 + SX-03, less the four removed after audit r1
    # (PH-03, PH-07, PH-08, SX-03); each remaining rule in exactly one family, none empty
    rules = [r for f in ledger.FAMILIES for r in ledger.FAMILY_RULES[f]]
    assert len(rules) == len(set(rules)) == 43
    proposed = {f"MD-{i:02d}" for i in range(1, 33)} | {f"PH-{i:02d}" for i in range(1, 14)}
    assert (proposed | {"SX-01"}) - {"PH-03", "PH-07", "PH-08"} == set(rules)
    assert all(ledger.FAMILY_RULES[f] for f in ledger.FAMILIES)
    assert all(
        ledger.FAMILY_MODULE[f] == ("metadiscourse" if f[:2] == "MD" else "phrase")
        for f in ledger.FAMILIES
    )


# --- crosswalk and partition ----------------------------------------------------------


def test_unchanged_identical_payload_outside_frame():
    b = [mk("a", (0, 3))]
    c = [mk("a", (0, 3), config="C")]
    bl, cl = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.UNCHANGED,
        "counterparts": ["C:a"],
        "resolved": True,
    }
    assert cl["C:a"]["change_type"] == X.C_UNCHANGED
    fr = crosswalk.frames_for(b, c, bl, cl)["metadiscourse"]
    assert fr["N_affected"] == 0 and fr["N_unchanged"] == 1


def test_display_context_only_change():
    b = [mk("a", (0, 3), ctx="old sentence ⟦and⟧")]
    c = [mk("a", (0, 3), ctx="new sentence ⟦and⟧", config="C")]
    bl, cl = cw(b, c)
    assert bl["B:a"]["change_type"] == X.DISPLAY and bl["B:a"]["resolved"] is True
    assert cl["C:a"]["change_type"] == X.C_DISPLAY
    fr = crosswalk.frames_for(b, c, bl, cl)["metadiscourse"]
    assert fr["affected_sizes"][X.DISPLAY] == 1 and fr["final_sizes"]["CHANGED"] == 1


def test_reassignment_same_span_is_not_deletion():
    b = [mk("a", (5, 8), "boosters")]
    c = [mk("x", (5, 8), "code_glosses", config="C")]
    bl, cl = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.REASSIGNED,
        "counterparts": ["C:x"],
        "resolved": True,
    }
    assert cl["C:x"] == {"change_type": X.C_REASSIGNED, "linked_baseline": ["B:a"]}
    fr = crosswalk.frames_for(b, c, bl, cl)["metadiscourse"]
    assert fr["N_genuine_deletion"] == 0


def test_genuine_deletion_and_unrelated_addition():
    b = [mk("a", (0, 3))]
    c = [mk("x", (10, 14), "hedges", config="C")]
    bl, cl = cw(b, c)
    assert core(bl["B:a"]) == {"change_type": X.REMOVED, "counterparts": [], "resolved": None}
    assert cl["C:x"] == {"change_type": X.ADDED, "linked_baseline": []}


def test_span_shift_nested_without_the_rule_is_unresolved():
    # audit r1 B4: geometric nesting alone never resolves (different marker string)
    b = [mk("a", (0, 11), marker="in order to")]
    c = [mk("x", (0, 8), marker="in order", config="C")]
    bl, _ = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.SPAN_CHANGED,
        "counterparts": ["C:x"],
        "resolved": False,
    }
    assert bl["B:a"]["links"] == [{"hit": "C:x", "resolved": False}]


def _with_head(r, head, raw_marker=None):
    r = dict(r, head_span=list(head))
    if raw_marker is not None:
        r["raw"] = {"marker": raw_marker}
    return r


def test_span_rule_same_marker_and_head_token_resolves():
    # same normalised marker and category, candidate span contains the baseline head
    b = [_with_head(mk("a", (4, 12), marker="of course"), (7, 12), "of course")]
    c = [_with_head(mk("x", (4, 13), marker="of course,", config="C"), (7, 12), "Of  Course")]
    bl, _ = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.SPAN_CHANGED,
        "counterparts": ["C:x"],
        "resolved": True,
    }
    # the same geometry without head tokens: unresolved (no geometric fallback)
    b2 = [dict(b[0], head_span=None)]
    bl2, _ = cw(b2, c)
    assert bl2["B:a"]["resolved"] is False
    # head token outside the other span both ways: unresolved
    b3 = [_with_head(mk("a", (4, 12), marker="of course"), (4, 6), "of course")]
    c3 = [_with_head(mk("x", (6, 13), marker="of course", config="C"), (12, 13), "of course")]
    bl3, _ = cw(b3, c3)
    assert bl3["B:a"]["resolved"] is False


def test_audit_i_believe_versus_i_is_unresolved():
    # audit r1 B4 probe: baseline `I believe` (boosters) -> candidate `I` (self_mentions)
    b = [_with_head(mk("a", (0, 9), "boosters", marker="I believe"), (2, 9), "I believe")]
    c = [_with_head(mk("x", (0, 1), "self_mentions", marker="I", config="C"), (0, 1), "I")]
    bl, _ = cw(b, c)
    assert bl["B:a"]["change_type"] == X.SPAN_CHANGED and bl["B:a"]["resolved"] is False
    assert bl["B:a"]["links"] == [{"hit": "C:x", "resolved": False}]
    # same marker, same head, but a different category (a span-changing reassignment)
    c2 = [
        _with_head(mk("x", (0, 10), "hedges", marker="I believe", config="C"), (2, 9), "I believe")
    ]
    bl2, _ = cw(b, c2)
    assert bl2["B:a"]["resolved"] is False


def test_span_shift_crossing_is_unresolved():
    b = [mk("a", (0, 6))]
    c = [mk("x", (4, 10), config="C")]
    bl, _ = cw(b, c)
    assert bl["B:a"]["change_type"] == X.SPAN_CHANGED and bl["B:a"]["resolved"] is False


def test_one_to_many_overlap_unresolved_and_same_span_one_to_many():
    b = [mk("a", (0, 10))]
    c = [mk("x", (0, 4), config="C"), mk("y", (5, 10), config="C")]
    bl, cl = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.SPAN_CHANGED,
        "counterparts": ["C:x", "C:y"],
        "resolved": False,
    }
    assert cl["C:x"]["change_type"] == cl["C:y"]["change_type"] == X.C_SPAN
    # two new claims on the same span: reassignment with two counterparts, resolved
    b2 = [mk("a", (0, 3), "boosters")]
    c2 = [mk("x", (0, 3), "hedges", config="C"), mk("y", (0, 3), "code_glosses", config="C")]
    bl2, _ = cw(b2, c2)
    assert core(bl2["B:a"]) == {
        "change_type": X.REASSIGNED,
        "counterparts": ["C:x", "C:y"],
        "resolved": True,
    }


def test_many_to_one_overlap_unresolved():
    b = [mk("a", (0, 4)), mk("b", (5, 9))]
    c = [mk("x", (0, 9), config="C")]
    bl, cl = cw(b, c)
    assert bl["B:a"]["resolved"] is False and bl["B:b"]["resolved"] is False
    assert cl["C:x"]["linked_baseline"] == ["B:a", "B:b"]


def test_duplicates_multiplicity_both_directions():
    b = [mk("a", (0, 3)), mk("a2", (0, 3))]
    c = [mk("x", (0, 3), config="C")]
    bl, cl = cw(b, c)
    assert bl["B:a"]["change_type"] == bl["B:a2"]["change_type"] == X.MULTIPLICITY
    assert bl["B:a"]["counterparts"] == ["C:x"] and bl["B:a"]["resolved"] is True
    assert cl["C:x"] == {"change_type": X.C_MULT, "linked_baseline": ["B:a", "B:a2"]}
    b = [mk("a", (0, 3))]
    c = [mk("x", (0, 3), config="C"), mk("y", (0, 3), config="C")]
    bl, cl = cw(b, c)
    assert core(bl["B:a"]) == {
        "change_type": X.MULTIPLICITY,
        "counterparts": ["C:x", "C:y"],
        "resolved": True,
    }
    fr = crosswalk.frames_for(b, c, bl, cl)["metadiscourse"]
    assert fr["final_sizes"] == {"ADDED": 0, "CHANGED": 2}


def test_consumed_candidates_are_not_reused():
    # baseline a is exactly kept; baseline b overlaps a's candidate only -> b is a deletion
    b = [mk("a", (0, 5), "transitions"), mk("b", (3, 8), "hedges")]
    c = [mk("a", (0, 5), "transitions", config="C")]
    bl, _ = cw(b, c)
    assert bl["B:a"]["change_type"] == X.UNCHANGED
    assert bl["B:b"]["change_type"] == X.REMOVED
    # a same-span counterpart (step 2) is not reused as an overlap counterpart (step 3)
    b = [mk("a", (0, 5), "boosters"), mk("b", (2, 9), "hedges")]
    c = [mk("x", (0, 5), "attitude_markers", config="C")]
    bl, _ = cw(b, c)
    assert bl["B:a"]["change_type"] == X.REASSIGNED and bl["B:b"]["change_type"] == X.REMOVED


def test_text_and_module_isolation():
    b = [mk("a", (0, 3), text="1")]
    c = [
        mk("x", (0, 3), text="2", config="C"),
        mk("y", (0, 3), "IN ORDER TO", module="phrase", config="C"),
    ]
    bl, cl = cw(b, c)
    assert bl["B:a"]["change_type"] == X.REMOVED
    assert {cl["C:x"]["change_type"], cl["C:y"]["change_type"]} == {X.ADDED}


def test_partition_exhaustive_exclusive_and_order_independent():
    r = random.Random(7)
    cats = ["transitions", "hedges", "boosters"]
    base, cand = [], []
    for i in range(300):
        s = r.randrange(0, 400)
        base.append(
            mk(f"b{i}", (s, s + r.randrange(1, 12)), r.choice(cats), text=str(r.randrange(3)))
        )
    for i in range(300):
        s = r.randrange(0, 400)
        cand.append(
            mk(
                f"c{i}",
                (s, s + r.randrange(1, 12)),
                r.choice(cats),
                text=str(r.randrange(3)),
                config="C",
            )
        )
    cand += [dict(b, hit_id=b["hit_id"].replace("B:", "C:k"), config="C") for b in base[:100]]
    bl, cl = cw(base, cand)
    assert set(bl) == {b["hit_id"] for b in base}
    assert all(v["change_type"] in X.BASE_TYPES for v in bl.values())
    fr = crosswalk.frames_for(base, cand, bl, cl)
    for m in ledger.MODULES:
        f = fr[m]
        assert f["N_unchanged"] + f["N_affected"] == f["N_baseline"]
        cells = [set(v) for v in f["affected_cells"].values()]
        assert sum(map(len, cells)) == len(set().union(*cells))
    base2, cand2 = base[:], cand[:]
    r.shuffle(base2)
    r.shuffle(cand2)
    assert crosswalk.crosswalk(base2, cand2) == (bl, cl)


def test_check_partition_catches_a_false_unchanged():
    b = [mk("a", (0, 3), ctx="one")]
    c = [mk("a", (0, 3), ctx="two", config="C")]
    bl, cl = crosswalk.crosswalk(b, c)
    bl["B:a"]["change_type"] = X.UNCHANGED
    assert any("identical-payload" in p for p in crosswalk.check_partition(b, c, bl, cl))
    with pytest.raises(ValueError):
        crosswalk.crosswalk(b + b, c)


# --- sampling ------------------------------------------------------------------------


def test_derive_seed_is_fixed():
    assert derive_seed(1, "x") == derive_seed(1, "x")
    assert derive_seed(1, "x") != derive_seed(1, "y") != derive_seed(2, "x")
    import hashlib

    assert derive_seed(5, "F|m|affected|REMOVED") == int(
        hashlib.sha256(b"fixcheck-v1|5|F|m|affected|REMOVED").hexdigest()[:16], 16
    )


def test_srs_determinism_census_and_empty():
    pop = [f"h{i:04d}" for i in range(1000)]
    s1 = sampling.srs(pop, 11, "F1")
    s2 = sampling.srs(list(reversed(pop)), 11, "F1")
    assert s1 == s2 and s1["n"] == 200 and len(set(s1["selected"])) == 200
    assert s1["inclusion_probability"] == 0.2 and not s1["census"]
    assert sampling.srs(pop, 11, "F2")["selected"] != s1["selected"]
    assert sampling.srs(pop, 12, "F1")["selected"] != s1["selected"]
    c = sampling.srs(pop[:200], 11, "F1")
    assert c["census"] and c["n"] == 200 and c["selected"] == sorted(pop[:200])
    e = sampling.srs([], 11, "F0")
    assert e["N"] == 0 and e["n"] == 0 and e["inclusion_probability"] is None
    expected = sorted(random.Random(derive_seed(11, "F1")).sample(sorted(pop), 200))
    assert s1["selected"] == expected


def _fake_base(n_md=400, n_ph=150, seed=3):
    r = random.Random(seed)
    rows = []
    for i in range(n_md):
        cat = analyse.MD_CATEGORIES[i % 10]
        marker = f"m{r.randrange(8)}"
        raw = {
            "dimension": "interactive",
            "category": cat,
            "marker": marker,
            "surface": marker,
            "token_index": i,
            "span": [i * 10, i * 10 + 3],
        }
        rows.append(
            {
                "hit_id": f"BASELINE:md{i:05d}",
                "module": "metadiscourse",
                "text_id": f"T{i % 7:03d}",
                "span": raw["span"],
                "raw": raw,
            }
        )
    for i in range(n_ph):
        rank = r.randrange(1, 40)
        raw = {
            "rank": rank,
            "phrase": f"P{rank}",
            "k_band": 1 + rank % 5,
            "surface": "p",
            "sense": None,
            "token_index": i,
            "span": [i * 10, i * 10 + 2],
        }
        rows.append(
            {
                "hit_id": f"BASELINE:ph{i:05d}",
                "module": "phrase",
                "text_id": f"T{i % 7:03d}",
                "span": raw["span"],
                "raw": raw,
            }
        )
    return rows


def test_baseline_success_sample_uses_registered_allocation():
    base = _fake_base()
    s1 = sampling.baseline_success_sample(base, {3, 4, 5}, 99)
    s2 = sampling.baseline_success_sample(list(reversed(base)), {3, 4, 5}, 99)
    assert s1 == s2
    assert s1["N"] == {"metadiscourse": 400, "phrase": 150}
    # 40 per category < 100 target: census of metadiscourse; PHRASE 150 < 300: census
    assert s1["n"] == {"metadiscourse": 400, "phrase": 150}
    assert build.SEED == build.DEV_SEED  # restored
    big = _fake_base(n_md=3000, n_ph=900)
    s3 = sampling.baseline_success_sample(big, {3, 4, 5}, 99)
    assert s3["n"]["metadiscourse"] == 1000 and s3["n"]["phrase"] == 300
    for m in ledger.MODULES:
        assert sum(d["N_h"] for d in s3["strata"][m].values()) == s3["N"][m]
        assert all(len(d["selected"]) == d["n_h"] <= d["N_h"] for d in s3["strata"][m].values())


def test_removal_plan_bounds():
    p = sampling.removal_plan(100, 100)
    assert p["attainable_upper_bound_if_no_success"] == 0 and p["max_k_hi_passing"] == 15
    assert (
        p["breach_certificate_attainable"]
        and p["min_definite_successes_for_breach_certificate"] == 16
    )
    p = sampling.removal_plan(5000, 200)
    assert p["attainable_upper_bound_if_no_success"] == E.hyper_ucl(0, 200, 5000, A) / 5000
    assert p["gate_passable"] and not p["breach_certificate_attainable"]
    assert sampling.removal_plan(0, 0)["status"].startswith("not_applicable")


# --- blinding and assignment ----------------------------------------------------------


def test_item_has_only_labeller_fields():
    pl = {
        "module": "metadiscourse",
        "context": "a ⟦b⟧",
        "marker": "b",
        "claimed": md_claimed("hedges"),
    }
    it = assign.item_of("00ff00ff00", pl)
    assert list(it) == ["id", "module", "context", "marker", "claimed"]
    with pytest.raises(ValueError):
        assign.item_of("x", pl | {"config": "COMPLETE"})


def test_separated_order_keeps_pairs_apart():
    ids = [f"i{k:03d}" for k in range(50)]
    conflicts = {}
    for k in range(0, 50, 2):
        conflicts.setdefault(ids[k], set()).add(ids[k + 1])
        conflicts.setdefault(ids[k + 1], set()).add(ids[k])
    order, bs = assign.separated_order(ids, conflicts, 325)  # one batch would hold every pair
    assert sorted(order) == ids and bs == 25
    batches = [set(order[i : i + bs]) for i in range(0, len(order), bs)]
    assert len(batches) == 2
    assert all(not (conflicts[x] & b) for b in batches for x in b)
    assert assign.separated_order(ids, conflicts, 325) == (order, bs)
    order, bs = assign.separated_order(ids, {}, 325)
    assert bs == 50 and order == ids
    # A triangle needs three batches: the batch count is at least 1 + the largest degree.
    tri = {"a": {"b", "c"}, "b": {"a", "c"}, "c": {"a", "b"}}
    order, bs = assign.separated_order(["a", "b", "c"], tri, 325)
    assert bs == 1 and sorted(order) == ["a", "b", "c"]


def test_within_batch_shuffle_keeps_membership_and_is_seeded():
    ids = [f"i{k:03d}" for k in range(60)]
    conflicts = {}
    for k in range(0, 60, 2):
        conflicts.setdefault(ids[k], set()).add(ids[k + 1])
        conflicts.setdefault(ids[k + 1], set()).add(ids[k])
    plain, bs = assign.separated_order(ids, conflicts, 325)
    shuf, bs2 = assign.separated_order(ids, conflicts, 325, shuffle_seed=11)
    assert bs == bs2
    cut = lambda o: [set(o[i : i + bs]) for i in range(0, len(o), bs)]  # noqa: E731
    assert cut(plain) == cut(shuf) and plain != shuf
    assert assign.separated_order(ids, conflicts, 325, shuffle_seed=11) == (shuf, bs)
    # The swap repair puts moved items first in a batch; after the shuffle they are spread.
    moved = [x for x in ids if plain.index(x) % bs == 0]
    assert moved and any(shuf.index(x) % bs != 0 for x in moved)


def test_occurrence_conflicts_cover_unlinked_versions_of_one_occurrence():
    def unit(p, *occ):
        return {"payload_sha256": p, "memberships": [], "occurrences": [list(o) for o in occ]}

    units = [
        unit("b1", ("S1", "h1", "metadiscourse", 0, 5)),  # baseline-success item
        unit("c1", ("S1", "h1", "metadiscourse", 0, 5)),  # sampled CHANGED final output
        unit("c2", ("S1", "h1", "metadiscourse", 3, 9)),  # overlapping span
        unit("x", ("S1", "h1", "metadiscourse", 9, 12)),  # adjacent, no overlap
        unit("p", ("S1", "h1", "phrase", 0, 5)),  # other module
        unit("t", ("S2", "h2", "metadiscourse", 0, 5)),  # other text
    ]
    edges = assign.occurrence_edges(units)
    assert edges == {("b1", "c1"), ("b1", "c2"), ("c1", "c2")}
    assert assign.pair_edges(units) == set()  # no sampled-row link: the old rule saw nothing


# --- acceptance arithmetic ------------------------------------------------------------


@pytest.mark.parametrize(
    "y_b, cps, expected",
    [
        (0, [], (0, 0)),
        (0, [(0, True)], (0, 0)),
        (1, [], (1, 1)),
        (None, [], (0, 1)),
        (1, [(1, True)], (0, 0)),
        (1, [(0, True)], (1, 1)),
        (1, [(None, True)], (0, 1)),
        (1, [(1, False)], (0, 1)),  # merely overlapping output never proves retention
        (1, [(0, False)], (1, 1)),
        (None, [(1, True)], (0, 0)),
        (None, [(0, True)], (0, 1)),
        (1, [(0, True), (1, True)], (0, 0)),  # one baseline hit, several counterparts
        (1, [(0, True), (None, False)], (0, 1)),
    ],
)
def test_loss_bounds(y_b, cps, expected):
    assert accept.loss_bounds(y_b, cps) == expected


def _brute_ucl(k, n, N, a):
    """Largest T with P(X <= k | T) > a, X ~ Hypergeometric(N, T, n) (independent check)."""
    best = None
    for T in range(N + 1):
        p = sum(math.comb(T, x) * math.comb(N - T, n - x) for x in range(0, k + 1)) / math.comb(
            N, n
        )
        if p > a:
            best = T
    return best


def test_removal_component_hand_cases():
    r = accept.removal_component(0, [])
    assert (
        r["status"] == "not_applicable" and r["bound"] is None and r["breach_certificate"] is False
    )
    r = accept.removal_component(10, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # census
    assert r["bound"] == 0.1 and r["passes"] and not r["breach_certificate"]
    r = accept.removal_component(10, [1, 1, None, 0, 0, 0, 0, 0, 0, 0])
    assert (r["k_lo"], r["k_hi"]) == (2, 3) and r["bound"] == 0.3 and not r["passes"]
    assert r["breach_lower"] == 0.2 and r["breach_certificate"]  # 2/10 > .15
    r = accept.removal_component(40, [None] + [0] * 19)  # unresolved stays in n, counts in k_hi
    assert r["n"] == 20 and r["k_hi"] == 1 and r["k_lo"] == 0
    assert r["bound"] == _brute_ucl(1, 20, 40, A) / 40 == E.hyper_ucl(1, 20, 40, A) / 40
    r = accept.removal_component(1000, [0] * 200)
    assert r["bound"] == _brute_ucl(0, 200, 1000, A) / 1000
    assert r["passes"] is (r["bound"] <= 0.15)


def test_u_loss_and_l_success_hand_cases():
    assert accept.u_loss([])["U_loss"] == 0.0
    assert accept.u_loss([(0, 0, 0, 0)])["U_loss"] == 0.0  # empty affected frame
    r = accept.u_loss([(5, 5, 1, 2), (3, 3, 0, 0)])  # census cells: exactly the high count
    assert r["U_loss"] == pytest.approx(2.0) and r["method"] == "census"
    r = accept.u_loss([(5, 5, 1, 2), (4, 0, 0, 0)])  # a positive-size unsampled cell stays in
    assert r["U_loss"] == pytest.approx(6.0) and r["method"] == "census_and_unobserved"
    r = accept.u_loss([(5, 5, 0, 1), (40, 20, 0, 1)])  # one sampled cell: exact hypergeometric
    assert r["method"] == "exact_hypergeometric"
    assert r["U_loss"] == pytest.approx(1 + _brute_ucl(1, 20, 40, A))
    r = accept.l_success([(10, 10, 7, 9)])
    assert r["L_success"] == pytest.approx(7.0)
    assert accept.l_success([])["L_success"] is None
    r = accept.l_success([(10, 10, 7, 9), (40, 20, 15, 18)])
    assert r["method"] == "exact_hypergeometric"
    lcl = 40 - _brute_ucl(
        20 - 15, 20, 40, A
    )  # lower limit of successes = N - upper limit of failures
    assert r["L_success"] == pytest.approx(7 + E.hyper_lcl(15, 20, 40, A)) == pytest.approx(7 + lcl)


def test_cumulative_gate_rules():
    assert accept.cumulative_gate(1.0, None)["status"] == "not_assessable"
    g = accept.cumulative_gate(1.0, 0.0)
    assert g["status"] == "not_assessable" and g["fraction"] is None
    assert accept.cumulative_gate(0.3, 10)["fraction"] == pytest.approx(0.03)
    assert accept.cumulative_gate(0.3, 10)["passes"]
    g = accept.cumulative_gate(20, 10)
    assert g["fraction"] == 1.0 and not g["passes"]
    assert accept.cumulative_gate(0.0, 10)["fraction"] == 0.0


def test_descriptive_interval_census_and_worst_case():
    d = accept.descriptive_interval(4, [1, 0, None, 1])
    assert d["interval95"] == [0.5, 0.75]
    assert (d["definite_correct"], d["definite_incorrect"], d["unresolved"]) == (2, 1, 1)
    assert accept.descriptive_interval(0, [])["interval95"] is None


def _round(cells_md, rem_family=None, bs_md=None, bs_ph=None, ph_removed=None):
    """Hand-built round: frames for COMPLETE and every family, baseline strata, references."""
    frames, refs = {}, {(m, oc): {} for m in ledger.MODULES for oc in analyse.OUTCOMES[m]}
    configs = ["COMPLETE", *ledger.FAMILIES]
    for c in configs:
        for m in ledger.MODULES:
            for cell in X.AFFECTED_CELLS:
                frames[f"{c}|{m}|affected|{cell}"] = {
                    "N": 0,
                    "n": 0,
                    "rows": {},
                    "counterparts": {},
                }
            for fr in X.FINAL_FRAMES:
                frames[f"{c}|{m}|final|{fr}"] = {"N": 0, "n": 0, "rows": {}, "counterparts": {}}

    def put(fid, N, rows):
        f = frames[fid]
        f["N"], f["n"] = N, len(rows)
        for row, (yb, cps) in rows.items():
            p = f"p-{fid}-{row}"
            f["rows"][row] = p
            for oc in ("STRICT", "LENIENT", "CONNECTIVE"):
                refs[("metadiscourse", oc)][p] = yb if oc != "CONNECTIVE" else None
            out = []
            for j, (yc, res) in enumerate(cps):
                q = f"q-{fid}-{row}-{j}"
                out.append((q, res))
                refs[("metadiscourse", "STRICT")][q] = yc
                refs[("metadiscourse", "LENIENT")][q] = yc
            f["counterparts"][row] = out

    for cell, (N, rows) in cells_md.items():
        put(f"COMPLETE|metadiscourse|affected|{cell}", N, rows)
    if rem_family:
        N, rows = rem_family
        put(f"MD-A|metadiscourse|affected|{X.REMOVED}", N, rows)
    bs = {m: {} for m in ledger.MODULES}
    for m, spec in (("metadiscourse", bs_md), ("phrase", bs_ph)):
        for sub, (N_h, ys) in (spec or {}).items():
            rows = {}
            for k, yv in enumerate(ys):
                p = f"s-{m}-{sub}-{k}"
                rows[f"r{k}"] = p
                for oc in analyse.OUTCOMES[m]:
                    refs[(m, oc)][p] = yv
            bs[m][sub] = {"N_h": N_h, "n_h": len(ys), "rows": rows}
    if ph_removed:
        N, ys = ph_removed
        fid = f"COMPLETE|phrase|affected|{X.REMOVED}"
        frames[fid]["N"], frames[fid]["n"] = N, len(ys)
        for k, yv in enumerate(ys):
            p = f"ph-{k}"
            frames[fid]["rows"][f"x{k}"] = p
            for oc in analyse.OUTCOMES["phrase"]:
                refs[("phrase", oc)][p] = yv
    return frames, bs, refs, configs


def test_compute_pass_with_census_cells():
    frames, bs, refs, configs = _round(
        {
            X.REMOVED: (3, {"a": (0, []), "b": (0, []), "c": (0, [])}),
            X.REASSIGNED: (2, {"d": (1, [(1, True)]), "e": (0, [(1, True)])}),
        },
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    assert md["removal"]["COMPLETE"]["bound"] == 0.0
    assert md["loss"]["STRICT"]["U_loss"] == 0.0 and md["success"]["STRICT"]["L_success"] == 100
    assert md["cumulative"]["STRICT"]["fraction"] == 0.0 and md["status"] == "pass"
    assert md["removal"]["MD-A"]["status"] == "not_applicable"  # empty deletion frame
    ph = res["modules"]["phrase"]
    assert (
        ph["status"] == "pass" and ph["loss"]["LIST_LENIENT"]["U_loss"] == 0.0
    )  # empty affected frame
    assert res["status"] == "pass"
    r1 = [c for c in ledger.ledger_components() if c["round"] == 1]
    assert set(res["components"]) == {c["id"] for c in r1}
    assert res["components"]["R1.metadiscourse.COMPLETE.loss_INV"]["value"] == 0.0
    assert res["components"]["R1.metadiscourse.MD-A.removal"]["status"] == "not_applicable"


def test_compute_removal_breach_certificate_fails():
    frames, bs, refs, configs = _round(
        {X.REMOVED: (10, {f"r{i}": (1 if i < 2 else 0, []) for i in range(10)})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    assert md["removal"]["COMPLETE"]["breach_certificate"]  # 2/10 > .15
    assert md["status"] == "fail" and res["status"] == "fail"
    assert md["breach_certificates"] == ["removal COMPLETE"]


def test_compute_cumulative_breach_certificate_and_family_removal():
    # 6 definite losses among 100 baseline hits: 6/100 > .05
    frames, bs, refs, configs = _round(
        {X.REASSIGNED: (6, {f"r{i}": (1, [(0, True)]) for i in range(6)})},
        rem_family=(4, {"z": (0, []), "y": (0, []), "x": (0, []), "w": (0, [])}),
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    g = md["cumulative"]["STRICT"]
    assert (
        g["definite_losses_sampled"] == 6 and g["breach_lower"] == 0.06 and g["breach_certificate"]
    )
    assert g["U_loss"] == pytest.approx(6.0) and g["fraction"] == pytest.approx(0.06)
    assert md["removal"]["MD-A"]["bound"] == 0.0 and md["status"] == "fail"


def test_compute_inconclusive_unresolved_and_zero_denominators():
    # unresolved baseline items: possible losses only -> bound above .05 but no certificate
    frames, bs, refs, configs = _round(
        {X.REASSIGNED: (6, {f"r{i}": (None, [(0, True)]) for i in range(6)})},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
    )
    res = accept.compute(frames, bs, refs, configs)
    md = res["modules"]["metadiscourse"]
    assert md["cumulative"]["STRICT"]["definite_losses_sampled"] == 0
    assert md["cumulative"]["STRICT"]["fraction"] == pytest.approx(0.06)
    assert md["status"] == "inconclusive" and res["status"] == "inconclusive"
    # zero baseline successes in a census: L_success = 0, cumulative gate not assessable
    frames, bs, refs, configs = _round(
        {}, bs_md={"s1": (10, [0] * 10)}, bs_ph={"t1": (50, [1] * 50)}
    )
    res = accept.compute(frames, bs, refs, configs)
    g = res["modules"]["metadiscourse"]["cumulative"]["STRICT"]
    assert g["status"] == "not_assessable" and g["fraction"] is None
    assert res["modules"]["metadiscourse"]["status"] == "inconclusive"
    # unresolved baseline-success references cannot establish successes
    frames, bs, refs, configs = _round(
        {}, bs_md={"s1": (10, [None] * 10)}, bs_ph={"t1": (50, [1] * 50)}
    )
    res = accept.compute(frames, bs, refs, configs)
    assert res["modules"]["metadiscourse"]["success"]["STRICT"]["L_success"] == 0.0
    # empty baseline population
    frames, bs, refs, configs = _round({}, bs_md={}, bs_ph={"t1": (50, [1] * 50)})
    res = accept.compute(frames, bs, refs, configs)
    assert (
        res["modules"]["metadiscourse"]["cumulative"]["STRICT"]["reason"]
        == "empty baseline population"
    )
    assert res["status"] == "inconclusive"


def test_compute_procedure_problem_blocks_pass():
    frames, bs, refs, configs = _round(
        {}, bs_md={"s1": (100, [1] * 100)}, bs_ph={"t1": (50, [1] * 50)}
    )
    res = accept.compute(frames, bs, refs, configs, procedure_problems=["labels missing"])
    assert res["status"] == "inconclusive"


def test_compute_phrase_removal_uses_list_lenient():
    frames, bs, refs, configs = _round(
        {},
        bs_md={"s1": (100, [1] * 100)},
        bs_ph={"t1": (50, [1] * 50)},
        ph_removed=(5, [0, 0, 0, 0, 1]),
    )
    res = accept.compute(frames, bs, refs, configs)
    r = res["modules"]["phrase"]["removal"]["COMPLETE"]
    assert (
        r["bound"] == 0.2
        and r["breach_certificate"]
        and res["modules"]["phrase"]["status"] == "fail"
    )


# --- collection (mocked cache, no network) --------------------------------------------


def _words(tag: str, n: int) -> str:
    return " ".join(f"{tag}w{i}" for i in range(n))


def _jats(pmcid: str, words: int, licence: str = "by") -> str:
    lic = f"https://creativecommons.org/licenses/{licence}/4.0/"
    return (
        '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
        f'<permissions><license xlink:href="{lic}"><p>Open access</p></license></permissions>'
        f"<abstract><p>{_words(pmcid + 'a', 40)}</p></abstract></article-meta></front>"
        f"<body><sec><title>Intro</title><p>{_words(pmcid, words)}</p></sec></body></article>"
    )


def _mock_cache(tmp: Path, n_per_journal: int = 3, dev_pmcid: str | None = None):
    dev_raw, raw = tmp / "devraw", tmp / "raw"
    (dev_raw / "pools").mkdir(parents=True)
    (raw / "epmc").mkdir(parents=True)
    (raw / "wiki").mkdir(parents=True)
    k = 0
    for _disc, journals in build.ACADEMIC_POOLS.items():
        for journal, years in journals:
            q = f'JOURNAL:"{journal}" AND IN_EPMC:y AND OPEN_ACCESS:y AND {years} AND PUB_TYPE:"research-article"'
            rows = []
            for _ in range(n_per_journal):
                k += 1
                pmcid = f"PMC9{k:06d}"
                rows.append(
                    {
                        "pmcid": pmcid,
                        "doi": f"10.1/x{k}",
                        "title": f"Article {k}",
                        "authorString": "A",
                        "journalTitle": journal,
                        "pubYear": "2022",
                    }
                )
                (raw / "epmc" / f"{pmcid}.xml").write_text(_jats(pmcid, 1600))
            if dev_pmcid and k == 3:
                rows.append(
                    {
                        "pmcid": dev_pmcid,
                        "doi": None,
                        "title": "dev",
                        "authorString": "A",
                        "journalTitle": journal,
                        "pubYear": "2022",
                    }
                )
            (dev_raw / "pools" / f"epmc_{build._key(q)}.json").write_text(
                json.dumps({"query": q, "retrieved": "2026-10-16", "rows": rows})
            )
    for name, prefix, words in (
        ("wiki_vital3.json", "Topic", 1100),
        ("wiki_essays.json", "Wikipedia:Essay", 600),
    ):
        titles = [f"{prefix} {i}" for i in range(30)]
        (dev_raw / "pools" / name).write_text(
            json.dumps({"params": {}, "retrieved": "2026-10-16", "titles": titles})
        )
        for i, t in enumerate(titles):
            pid = (1 if prefix == "Topic" else 2) * 100000 + i
            page = {
                "pageid": pid,
                "title": t,
                "extract": f"{_words(t.replace(' ', ''), words)}\n\n== See also ==\nx",
                "revisions": [{"revid": pid * 10, "timestamp": "2026-01-01T00:00:00Z"}],
                "categories": [],
            }
            (raw / "wiki" / f"{build._key(t)}.json").write_text(
                json.dumps({"query": {"pages": [page]}})
            )
    return dev_raw, raw


def _r1_registry(path: Path, r1: Path, status: str = "inconclusive") -> Path:
    """A scratch (non-canonical) registry holding round 1's reservation and decision, as
    round-2 dry runs need (audit r2 B2: round 2 is bound to the REGISTERED round 1)."""
    from fixcheck import registry as REG
    from fixcheck.common import sha256_file

    col = read_json(r1 / "collection.json")
    res = {
        "type": "reservation",
        "round": 1,
        "candidate_commit": None,
        "candidate_tree_sha256": None,
        "seed": col["seed"],
        "collect_dir": str(r1),
        "registered_at": "2026-10-17T00:00:00+00:00",
    }
    dec = {
        "type": "decision",
        "round": 1,
        "candidate_commit": "c1",
        "candidate_tree_sha256": None,
        "seed": col["seed"],
        "reservation_sha256": REG.entry_sha256(res),
        "freeze_record_sha256": sha256_file(r1 / "freeze_record.json"),
        "collection_texts_sha256": sha256_file(r1 / "texts.jsonl"),
        "source_refs": [],
        "inputs_sha256": "i1",
        "status": status,
        "families": list(ledger.FAMILIES),
    }
    path.write_text("")
    REG.append_unchecked(path, res)
    REG.append_unchecked(path, dec)
    return path


def test_collect_offline_quota_exclusions_and_rounds(tmp_path, monkeypatch):
    dev = read_jsonl(build.DEV_TEXTS)
    dev_pmcid = next(t["source_id"] for t in dev if t["source"] == "Europe PMC")
    dev_raw, raw = _mock_cache(tmp_path, dev_pmcid=dev_pmcid)
    out1 = tmp_path / "r1"
    rc = collect.main(
        [
            "--round",
            "1",
            "--seed",
            "777",
            "--out",
            str(out1),
            "--raw-cache",
            str(raw),
            "--dev-raw",
            str(dev_raw),
            "--offline",
            "--dry-run",
        ]
    )
    assert rc == 0
    col = read_json(out1 / "collection.json")
    assert col["status"] == "complete" and col["n_texts"] == 60
    assert col["by_register"] == {"academic": 20, "general": 20, "argumentative": 20}
    assert col["by_discipline"] == {"sciences": 7, "social_sciences": 7, "humanities": 6}
    texts = read_jsonl(out1 / "texts.jsonl")
    assert dev_pmcid not in {t["source_id"] for t in texts}
    pre = read_json(out1 / "freeze_record.json")
    assert pre["seed"] == 777 and pre["dev_manifest"]["sha256"] == build.DEV_TEXTS_SHA256
    assert len(pre["pool_inventory"]) == len(list((dev_raw / "pools").glob("*.json")))
    assert pre["dry_run"] is True and pre["production_eligible"] is False
    assert col["production_eligible"] is False
    cmd = (out1 / "command.txt").read_text().strip()
    assert "--offline" in cmd and cmd.endswith(
        f"--execute --freeze-record {out1 / 'freeze_record.json'}"
    )
    assert (out1 / "manifest_collect.json").exists()
    for t in texts:
        body = (out1 / "texts" / f"{t['text_id']}.txt").read_text(encoding="utf-8")
        assert len(body.encode()) <= build.MAX_BYTES and payload_sha256 is not None
    assert build.SEED == build.DEV_SEED and build.WIKI_TARGET == 40  # build settings restored
    # Round 2 needs round 1's manifest and excludes every identifier of it.
    reg = _r1_registry(tmp_path / "reg.jsonl", out1)
    with pytest.raises(SystemExit):  # no registered round 1
        collect.main(
            [
                "--round",
                "2",
                "--seed",
                "778",
                "--out",
                str(tmp_path / "r2n"),
                "--raw-cache",
                str(raw),
                "--dev-raw",
                str(dev_raw),
                "--offline",
                "--dry-run",
                "--earlier",
                str(out1),
            ]
        )
    with pytest.raises(SystemExit):
        collect.main(
            [
                "--round",
                "2",
                "--seed",
                "778",
                "--out",
                str(tmp_path / "r2x"),
                "--raw-cache",
                str(raw),
                "--dev-raw",
                str(dev_raw),
                "--offline",
                "--dry-run",
                "--registry",
                str(reg),
            ]
        )
    with pytest.raises(SystemExit):  # the seed of an earlier round
        collect.main(
            [
                "--round",
                "2",
                "--seed",
                "777",
                "--out",
                str(tmp_path / "r2y"),
                "--raw-cache",
                str(raw),
                "--dev-raw",
                str(dev_raw),
                "--offline",
                "--dry-run",
                "--earlier",
                str(out1),
                "--registry",
                str(reg),
            ]
        )
    rc = collect.main(
        [
            "--round",
            "2",
            "--seed",
            "778",
            "--out",
            str(tmp_path / "r2"),
            "--raw-cache",
            str(raw),
            "--dev-raw",
            str(dev_raw),
            "--offline",
            "--dry-run",
            "--earlier",
            str(out1),
            "--registry",
            str(reg),
        ]
    )
    t2 = read_jsonl(tmp_path / "r2" / "texts.jsonl")
    assert not ({t["source_id"] for t in t2} & {t["source_id"] for t in texts})
    assert not ({t["title"] for t in t2} & {t["title"] for t in texts})
    assert rc == 2 and read_json(tmp_path / "r2" / "collection.json")["status"] == "shortfall"
    assert read_json(tmp_path / "r2" / "collection.json")["shortfalls"]
    with pytest.raises(SystemExit):  # the development seed is refused
        collect.main(["--round", "1", "--seed", str(build.DEV_SEED), "--out", str(tmp_path / "r3")])


def test_collect_never_touches_the_network(tmp_path):
    dev_raw, raw = _mock_cache(tmp_path)
    (raw / "wiki" / f"{build._key('Topic 0')}.json").unlink()  # one uncached page
    with pytest.raises(collect.NetworkForbidden):
        collect.main(
            [
                "--round",
                "1",
                "--seed",
                "779",
                "--out",
                str(tmp_path / "r"),
                "--raw-cache",
                str(raw),
                "--dev-raw",
                str(dev_raw),
                "--offline",
                "--dry-run",
            ]
        )
    assert build.urllib.request.urlopen is not collect._no_network


# --- worker (payloads) ------------------------------------------------------------------


def test_worker_families_interface_mocked(monkeypatch):
    calls = []
    mod = types.ModuleType("fake_families")
    mod.FAMILIES = ledger.FAMILIES
    state = {"on": set(ledger.FAMILIES)}

    import contextlib

    @contextlib.contextmanager
    def only(fams):
        calls.append(list(fams))
        old = state["on"]
        state["on"] = set(fams)
        yield
        state["on"] = old

    mod.only = only
    mod.enabled = lambda f: f in state["on"]
    monkeypatch.setitem(sys.modules, "fake_families", mod)
    ctx, fam = worker.families_context("fake_families", ["MD-A"])
    with ctx:
        assert [f for f in ledger.FAMILIES if fam.enabled(f)] == ["MD-A"]
    assert calls == [["MD-A"]]
    ctx, _ = worker.families_context("fake_families", [])
    with ctx:
        assert not any(mod.enabled(f) for f in ledger.FAMILIES)  # only([]) = 0.3.3
    mod.FAMILIES = ("MD-A",)
    with pytest.raises(SystemExit):
        worker.families_context("fake_families", [])
    with pytest.raises(SystemExit):
        worker.families_context("none", ["MD-A"])


def test_worker_payload_matches_build_items(tmp_path):
    pytest.importorskip("spacy")
    from lexinspect import pipeline

    text = "However, we argue that this may be important. In other words, the result is clear."
    t = {"text_id": "T001", "source_id": "S1", "text_sha256": "h", "register": "academic"}
    a, res = pipeline.run_all(text, modules=["metadiscourse", "phrase"])
    sents = list(a.doc.sents)
    by_rank, siblings = build.phrase_lookup()
    rows = worker.hit_rows(
        "C",
        t,
        {m: res[m]["hits"] for m in worker.MODULES_RUN},
        (a, sents, [s.start for s in sents]),
        by_rank,
        siblings,
    )
    assert rows and len({r["hit_id"] for r in rows}) == len(rows)
    for r in rows:
        h = {"module": r["module"], "text_id": "T001", **r["raw"]}
        ctx, _ = build.context_for(h, (a, sents, [s.start for s in sents]))
        assert r["payload"] == {
            "module": r["module"],
            "context": ctx,
            "marker": h["surface"],
            "claimed": build.claimed_for(h, by_rank, siblings),
        }
        assert r["payload_sha256"] == payload_sha256(r["payload"])
        assert "⟦" in r["payload"]["context"]
    rows2 = worker.hit_rows(
        "C",
        t,
        {m: res[m]["hits"] for m in worker.MODULES_RUN},
        (a, sents, [s.start for s in sents]),
        by_rank,
        siblings,
    )
    assert rows == rows2


# --- integration without spaCy: diff -> sample -> assign -> flash -> accept -------------


def _write_frames(run_dir: Path):
    """BASELINE / COMPLETE / family frames with every change type, written like worker.py."""
    r = random.Random(5)
    frames = {"BASELINE": [], **{c: [] for c in ("COMPLETE", *ledger.FAMILIES)}}
    for t in range(4):
        for i in range(120):
            s = i * 20
            cat = analyse.MD_CATEGORIES[i % 10]
            b = mk(f"md{t}-{i}", (s, s + 4), cat, text=str(t), config="BASELINE")
            b["raw"] = {
                "dimension": "interactive",
                "category": cat,
                "marker": f"m{i % 6}",
                "surface": "and",
                "token_index": i,
                "span": [s, s + 4],
            }
            b["text_id"] = f"T{t:03d}"
            frames["BASELINE"].append(b)
            if i % 40 == 7:  # a second claim at the same span (CLAIM_DROPPED where dropped)
                cat2 = analyse.MD_CATEGORIES[(i + 3) % 10]
                x = mk(f"md{t}-{i}x", (s, s + 4), cat2, text=str(t), config="BASELINE")
                x["raw"] = dict(b["raw"], category=cat2)
                x["text_id"] = f"T{t:03d}"
                frames["BASELINE"].append(x)
        for i in range(40):
            s = 5000 + i * 20
            p = mk(
                f"ph{t}-{i}",
                (s, s + 4),
                f"P{i % 9}",
                module="phrase",
                text=str(t),
                config="BASELINE",
            )
            p["raw"] = {
                "rank": i % 9 + 1,
                "phrase": f"P{i % 9}",
                "k_band": 1 + i % 5,
                "surface": "p",
                "sense": None,
                "token_index": 1000 + i,
                "span": [s, s + 4],
            }
            p["text_id"] = f"T{t:03d}"
            frames["BASELINE"].append(p)
    for c in frames:
        if c == "BASELINE":
            continue
        for b in frames["BASELINE"]:
            u = r.random()
            if b["hit_id"].endswith("x") and c in ("COMPLETE", "MD-A"):
                continue  # the second claim is dropped; the first may be kept
            if c in ("COMPLETE", "MD-A") and b["module"] == "metadiscourse":
                if u < 0.15:
                    continue  # removed
                if u < 0.2:
                    nb = mk(
                        b["hit_id"].split(":")[1] + "r",
                        tuple(b["span"]),
                        "code_glosses",
                        text=b["source_id"][1:],
                        config=c,
                    )
                    frames[c].append(
                        nb
                        | {"raw": dict(b["raw"], category="code_glosses"), "text_id": b["text_id"]}
                    )
                    continue
                if u < 0.23:
                    s0, s1 = b["span"]
                    nb = mk(
                        b["hit_id"].split(":")[1] + "s",
                        (s0, s1 - 1),
                        b["claim"]["category"],
                        text=b["source_id"][1:],
                        config=c,
                    )
                    frames[c].append(nb | {"raw": b["raw"], "text_id": b["text_id"]})
                    continue
                if u < 0.25:
                    nb = dict(
                        b,
                        hit_id=f"{c}:" + b["hit_id"].split(":")[1],
                        config=c,
                        payload=dict(b["payload"], context=b["payload"]["context"] + " (new)"),
                    )
                    nb["payload_sha256"] = payload_sha256(nb["payload"])
                    frames[c].append(nb)
                    continue
            if c in ("COMPLETE", "PH-A") and b["module"] == "phrase" and u < 0.2:
                continue
            frames[c].append(dict(b, hit_id=f"{c}:" + b["hit_id"].split(":")[1], config=c))
        if c in ("COMPLETE", "MD-A"):
            extra = mk("added1", (9990, 9995), "hedges", text="0", config=c)
            frames[c].append(extra | {"raw": {"category": "hedges"}, "text_id": "T000"})
    (run_dir / "frames").mkdir(parents=True)
    for c, rows in frames.items():
        with (run_dir / "frames" / f"{c}.hits.jsonl").open("w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (run_dir / "frames" / "BASELINE.meta.json").write_text(json.dumps({"polysemous_ranks": [2, 3]}))
    (run_dir / "run.json").write_text(json.dumps({"configs": {c: [] for c in frames}}))


def test_end_to_end_integration(tmp_path):
    run_dir = tmp_path / "run"
    _write_frames(run_dir)
    assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(tmp_path / "diff")]) == 0
    fr = read_json(tmp_path / "diff" / "frames.json")
    md = fr["frames"]["COMPLETE"]["metadiscourse"]
    assert all(md["affected_sizes"][c] > 0 for c in X.AFFECTED_CELLS if c != X.MULTIPLICITY)
    assert fr["frames"]["MD-B"]["metadiscourse"]["N_affected"] == 0
    assert fr["frames"]["MD-A"]["phrase"]["N_affected"] == 0
    assert (
        sampling.main(
            [
                "--run-dir",
                str(run_dir),
                "--diff-dir",
                str(tmp_path / "diff"),
                "--round-seed",
                "5",
                "--out",
                str(tmp_path / "sample"),
                "--plan-reps",
                "3",
                "--power-reps",
                "4",
            ]
        )
        == 0
    )
    sel = read_json(tmp_path / "sample" / "selection.json")
    assert sel["production_eligible"] is False  # run.json is not production-eligible
    pw = read_json(tmp_path / "sample" / "operational_power.json")
    assert pw["reps"] == 4 and len(pw["scenarios"]) == 17  # 5 x 3 grid + 2 calibrated
    for sc in pw["scenarios"]:
        g = sc["gates"]["ALL_REQUIRED_GATES_PASS"]
        assert g["reps"] == 4 and 0 <= g["wilson95"][0] <= g["p"] <= g["wilson95"][1] <= 1
        assert set(sc["realised"]) == {"metadiscourse", "phrase"}
    assert "most_favourable_feasible" in pw["attainable"]
    assert (
        "optimistic marginal benchmark"
        in read_json(tmp_path / "sample" / "decision_plan.json")["cumulative"][
            "metadiscourse|STRICT"
        ]["label"]
    )
    assert sel["frames"]["COMPLETE|metadiscourse|affected|REMOVED"]["n"] == min(
        200, md["affected_sizes"]["REMOVED"]
    )
    units = read_jsonl(tmp_path / "sample" / "units.jsonl")
    assert len({u["payload_sha256"] for u in units}) == len(units)
    # identical payloads labelled once, membership kept in every frame (family and COMPLETE)
    multi = [u for u in units if len({m["frame"].split("|")[0] for m in u["memberships"]}) > 1]
    assert multi
    plan = read_json(tmp_path / "sample" / "decision_plan.json")
    assert "COMPLETE|metadiscourse|affected|REMOVED" in plan["removal"]
    assert (
        assign.main(
            [
                "--sample-dir",
                str(tmp_path / "sample"),
                "--round-seed",
                "5",
                "--out",
                str(tmp_path / "assign"),
                "--batch-size",
                "100",
            ]
        )
        == 0
    )
    items = read_jsonl(tmp_path / "assign" / "items.jsonl")
    assert len(items) == len(units)
    forbidden = re.compile(
        r"BASELINE|COMPLETE|MD-[A-I]|PH-[ABC]|REMOVED|REASSIGNED|counterpart|payload", re.I
    )
    for it in items:
        assert list(it) == ["id", "module", "context", "marker", "claimed"]
        assert re.fullmatch(r"[0-9a-f]{10}", it["id"])
        assert not forbidden.search(json.dumps({k: v for k, v in it.items() if k != "context"}))
    raw_items = (tmp_path / "assign" / "items.jsonl").read_text()
    assert "hit_id" not in raw_items and "config" not in raw_items
    key = read_jsonl(tmp_path / "assign" / "key.jsonl")
    id_of = {k["payload_sha256"]: k["id"] for k in key}
    pairs = assign.pair_edges(units)
    assert pairs
    for role in ("A", "B"):
        man = read_json(tmp_path / "assign" / "batches" / role / "batch" / "batch_manifest.json")
        for b in man["batches"]:
            ids = set(b["ids"])
            assert not any(id_of[x] in ids and id_of[y] in ids for x, y in pairs)
            data = (tmp_path / "assign" / "batches" / role / "batch" / b["file"]).read_text()
            assert all(
                list(json.loads(line)) == list(assign.ITEM_FIELDS) for line in data.splitlines()
            )
    # synthetic labels, Flash, acceptance
    itemd = {i["id"]: i for i in items}
    rows = [{"id": k["id"], "module": k["module"], "category": k["category"]} for k in key]
    la = analyse.make_dummy_labels(rows, itemd, 1)
    lb = analyse.make_dummy_labels(rows, itemd, 2)
    lb = lb[5:]  # B misses five items: non-votes go to Flash
    (tmp_path / "A.jsonl").write_text("".join(json.dumps(x) + "\n" for x in la))
    (tmp_path / "B.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lb))
    assert (
        assign.main_flash(
            [
                "--assign-dir",
                str(tmp_path / "assign"),
                "--labels",
                f"A={tmp_path / 'A.jsonl'}",
                f"B={tmp_path / 'B.jsonl'}",
                "--round-seed",
                "5",
                "--batch-size",
                "100",
            ]
        )
        == 0
    )
    fids = (tmp_path / "assign" / "flash" / "flash_ids.txt").read_text().split()
    va = analyse.validate_lines([json.dumps(x) for x in la], itemd, None, "A")
    vb = analyse.validate_lines([json.dumps(x) for x in lb], itemd, None, "B")
    assert fids == analyse.needs_adjudication(rows, [va, vb])
    assert {x["id"] for x in la[:5]} <= set(fids)
    lc = analyse.make_dummy_labels(
        [r for r in rows if r["id"] in set(fids)], itemd, 3, p_unsure=0.2
    )
    (tmp_path / "C.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lc))
    res = accept.acceptance_of(
        tmp_path / "assign",
        tmp_path / "sample",
        {"A": tmp_path / "A.jsonl", "B": tmp_path / "B.jsonl"},
        tmp_path / "C.jsonl",
        1,
        [],
    )
    assert res["status"] in ("pass", "fail", "inconclusive")
    assert res["labels"]["n_flash"] == len(fids)
    assert len(res["components"]) == 34  # the round-1 identities
    # Recompute U_loss for one module by hand from the archived pieces.
    md_res = res["modules"]["metadiscourse"]
    cells = [
        (d["N_h"], d["n_h"], d["k_lo"], d["k_hi"])
        for d in md_res["loss"]["STRICT"]["cells"].values()
    ]
    pos = [c for c in cells if c[0] > 0]
    assert md_res["loss"]["STRICT"]["U_loss"] == pytest.approx(
        sum(c[0] for c in pos) * E.exact_limits(pos, None, A)["upper"]
    )


# --- additions: pool snapshot guard, round replay, pinned baseline, verify ------------


def _collect_r1(tmp_path, raw, dev_raw, seed="777", out="r1", extra=()):
    return collect.main(
        [
            "--round",
            "1",
            "--seed",
            seed,
            "--out",
            str(tmp_path / out),
            "--raw-cache",
            str(raw),
            "--dev-raw",
            str(dev_raw),
            "--dry-run",
            *extra,
        ]
    )


def test_missing_pool_listing_is_never_requeried_online(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    next(iter(sorted((dev_raw / "pools").glob("epmc_*.json")))).unlink()
    calls = []

    def urlopen(*a, **k):
        calls.append(a)
        raise AssertionError("network used")

    monkeypatch.setattr(build.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(build.time, "sleep", lambda s: None)
    with pytest.raises(collect.PoolRequeryForbidden):
        _collect_r1(tmp_path, raw, dev_raw)  # online mode: the guard, not --offline, stops it
    assert calls == []
    assert build.fetch.__name__ == "fetch"  # build settings restored


def test_round_replays_offline_byte_for_byte(tmp_path, monkeypatch):
    dev_raw, raw = _mock_cache(tmp_path)
    assert _collect_r1(tmp_path, raw, dev_raw, extra=("--offline",)) == 0
    r1 = tmp_path / "r1"
    before = (r1 / "texts.jsonl").read_bytes()
    rc = collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep")])
    rep = read_json(tmp_path / "rep" / "replay.json")
    assert rc == 0 and rep["identical"] and rep["texts_jsonl_identical"]
    assert rep["cache_files_unchanged"] and rep["replayed_texts"] == 60
    assert (r1 / "texts.jsonl").read_bytes() == before  # the round is never written
    # Round 2 replays with round 1 as its earlier manifest.
    reg = _r1_registry(tmp_path / "reg.jsonl", r1)
    rc2 = collect.main(
        [
            "--round",
            "2",
            "--seed",
            "778",
            "--out",
            str(tmp_path / "r2"),
            "--raw-cache",
            str(raw),
            "--dev-raw",
            str(dev_raw),
            "--offline",
            "--dry-run",
            "--earlier",
            str(r1),
            "--registry",
            str(reg),
        ]
    )
    assert rc2 == 2  # the small mock pool runs short; replay still checks it
    assert (
        collect.main(["--replay-round", str(tmp_path / "r2"), "--out", str(tmp_path / "rep2")]) == 0
    )
    # A changed text byte is reported, not hidden.
    t1 = r1 / "texts" / "T001.txt"
    t1.write_text(t1.read_text(encoding="utf-8") + " ", encoding="utf-8")
    rc = collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep3")])
    rep3 = read_json(tmp_path / "rep3" / "replay.json")
    assert rc == 1 and not rep3["identical"]
    assert any("T001: text bytes differ" in p for p in rep3["problems"])
    # A changed manifest no longer matches collection.json: refused outright.
    (r1 / "texts.jsonl").write_bytes(before + b"\n")
    with pytest.raises(SystemExit):
        collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep4")])
    # A changed pool snapshot is refused.
    (r1 / "texts.jsonl").write_bytes(before)
    pool = next(iter(sorted((raw / "pools").glob("*.json"))))
    pool.write_text(pool.read_text() + " ")
    with pytest.raises(SystemExit):
        collect.main(["--replay-round", str(r1), "--out", str(tmp_path / "rep5")])


def _fake_lexinspect(root: Path, marker: str) -> None:
    pkg = root / "lexinspect"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("__version__ = 'fake'\n")
    for mod in ("pipeline", "phrase"):  # build.phrase_lookup imports phrase first
        (pkg / f"{mod}.py").write_text(f"raise RuntimeError({marker!r})\n")


def test_worker_import_root_runs_the_given_tree(tmp_path):
    import subprocess

    rd = tmp_path / "round"
    (rd / "texts").mkdir(parents=True)
    text = "However, this is a text."
    (rd / "texts" / "T001.txt").write_text(text, encoding="utf-8")
    row = {"text_id": "T001", "source_id": "S1", "text_sha256": worker.sha256_text(text)}
    (rd / "texts.jsonl").write_text(json.dumps(row) + "\n")
    _fake_lexinspect(tmp_path / "fake", "FAKE-PIPELINE-REACHED")

    def go(root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(HERE / "worker.py"),
                "--texts",
                str(rd),
                "--config",
                "BASELINE_PINNED",
                "--families-module",
                "none",
                "--out",
                str(tmp_path / "o"),
                "--import-root",
                str(root),
            ],
            capture_output=True,
            text=True,
        )

    r = go(tmp_path / "fake")
    assert r.returncode != 0 and "FAKE-PIPELINE-REACHED" in r.stderr
    (tmp_path / "empty").mkdir()
    r = go(tmp_path / "empty")  # nothing to import there: the environment's copy is refused
    assert r.returncode != 0 and "not from" in r.stderr


PINNED_SRC = HERE.parents[3] / ".cache/validation/study4_fix040/equivalence/baseline_033_src"


@pytest.mark.skipif(not PINNED_SRC.exists(), reason="pinned source archive not present")
def test_pinned_src_record_checks_tree_and_lock(tmp_path):
    import shutil

    from fixcheck import run

    rec = run.pinned_src_record(PINNED_SRC, "dec79bc", HERE.parents[3])
    assert rec["tree_identical"] and rec["n_files"] > 50
    assert rec["commit"].startswith("dec79bc")
    assert rec["environment_identical"]
    copy = tmp_path / "src"
    shutil.copytree(PINNED_SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
    f = copy / "lexinspect" / "phrase.py"
    f.write_text(f.read_text() + "\n# edited\n")
    (copy / "lexinspect" / "new.py").write_text("x = 1\n")
    bad = run.pinned_src_record(copy, "dec79bc", HERE.parents[3])
    assert not bad["tree_identical"]
    assert "differs lexinspect/phrase.py" in bad["tree_problems"]
    assert "extra lexinspect/new.py" in bad["tree_problems"]
    lock = tmp_path / "co"
    lock.mkdir()
    (lock / "uv.lock").write_text("not the lock\n")
    assert not run.pinned_src_record(PINNED_SRC, "dec79bc", lock)["environment_identical"]


def test_verify_baseline_requires_identical_sequence_and_lookup(tmp_path):
    from fixcheck import run

    rows = [mk("a", (0, 3)), mk("b", (5, 9)), mk("c", (5, 9), "hedges")]
    for r, k in zip(rows, range(3), strict=True):
        r["raw"] = {"k": k}
    meta = {
        "phrase_lookup_sha256": "x",
        "polysemous_ranks": [1],
        "texts_jsonl_sha256": "t",
        "n_texts": 1,
    }

    good_pin = {"commit": run.PINNED_FULL, "tree_identical": True, "environment_identical": True}

    def write(base, pinned, meta_b=meta, pin=good_pin):
        d = tmp_path / f"r{len(list(tmp_path.iterdir()))}"
        (d / "frames").mkdir(parents=True)
        if pin is not None:
            (d / "pinned.json").write_text(json.dumps(pin))
        for name, rs, m in (("BASELINE", base, meta), ("BASELINE_PINNED", pinned, meta_b)):
            (d / "frames" / f"{name}.hits.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rs)
            )
            (d / "frames" / f"{name}.meta.json").write_text(json.dumps(m))
        return run.verify_baseline(d)

    ok = write(rows, [dict(r, hit_id="P:" + r["hit_id"]) for r in rows])
    assert ok["identical"] and ok["problems"] == []  # hit ids carry the config name: ignored
    swapped = write(rows, [rows[0], rows[2], rows[1]])
    assert not swapped["identical"] and swapped["same_multiset"]
    lookup = write(rows, rows, dict(meta, phrase_lookup_sha256="y"))
    assert not lookup["identical"] and "phrase_lookup_sha256 differs" in lookup["problems"]
    fewer = write(rows, rows[:2])
    assert not fewer["identical"] and fewer["only_in_a"] == 1
    # audit r1 B2/S3: the pinned code must be verified against the full dec79bc commit,
    # and the packaged PHRASE inventory must be the same
    nopin = write(rows, rows, pin=None)
    assert not nopin["identical"] and any("not verified" in x for x in nopin["problems"])
    short = write(rows, rows, pin=dict(good_pin, commit="0" * 40))
    assert not short["identical"] and any("is not dec79bc0e642" in x for x in short["problems"])
    unchecked = write(rows, rows, pin={"commit": run.PINNED_FULL})
    assert not unchecked["identical"]
    inv = write(rows, rows, dict(meta, phrase_inventory_sha256="z"))
    assert "phrase_inventory_sha256 differs" in inv["problems"]


def test_src_tree_digest_tracks_every_file(tmp_path):
    from fixcheck import run

    pkg = tmp_path / "src" / "lexinspect"
    (pkg / "__pycache__").mkdir(parents=True)
    (pkg / "a.py").write_text("a\n")
    (pkg / "__pycache__" / "a.pyc").write_bytes(b"\0")
    d1 = run.src_tree_digest(tmp_path)
    (pkg / "__pycache__" / "a.pyc").write_bytes(b"\1")
    assert run.src_tree_digest(tmp_path)["tree_sha256"] == d1["tree_sha256"]
    (pkg / "a.py").write_text("b\n")
    assert run.src_tree_digest(tmp_path)["tree_sha256"] != d1["tree_sha256"]
    assert d1["n_files"] == 1


def test_separated_order_reaches_the_needed_batch_count():
    # n = 9 with a 4-clique: 4 batches are needed; ceil(9 / ceil(9 / 4)) would give only 3.
    ids = [f"i{k}" for k in range(9)]
    clique = ids[:4]
    conflicts = {x: set(clique) - {x} for x in clique}
    order, bs = assign.separated_order(ids, conflicts, 325, shuffle_seed=1)
    batches = [set(order[i : i + bs]) for i in range(0, len(order), bs)]
    assert len(batches) >= 4 and sorted(order) == ids
    assert all(len(b & set(clique)) <= 1 for b in batches)


def test_ledger_check_against_the_candidate_ledger(tmp_path):
    from fixcheck import verify

    if not ledger.DRAFT_LEDGER_MD.exists():
        pytest.skip("candidate ledger not present")
    res = verify.ledger_check(ledger.DRAFT_LEDGER_MD)
    assert res["ok"], res["problems"]
    assert res["n_components"] == 68 and set(res["per_round_module"].values()) == {17}
    assert res["ledger_md"]["families_in_table"] == sorted(ledger.FAMILIES)
    bad = tmp_path / "L.md"
    bad.write_text(ledger.DRAFT_LEDGER_MD.read_text().replace("MD-29, MD-31", "MD-29"))
    assert any("MD-G" in p for p in verify.ledger_check(bad)["problems"])
    # A parenthetical with a comma inside is a qualifier, not two rules.
    fam = verify.ledger_check(ledger.DRAFT_LEDGER_MD)["ledger_md"]["families_in_table"]
    assert fam == sorted(ledger.FAMILIES)
    assert ledger.FAMILY_RULES["PH-B"][-2:] == ("PH-11", "PH-12")


def test_blinding_audit_and_determinism_on_the_integration_round(tmp_path):
    from fixcheck import verify

    run_dir = tmp_path / "run"
    _write_frames(run_dir)

    def chain(d: Path) -> None:
        assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(d / "diff")]) == 0
        args = ["--run-dir", str(run_dir), "--diff-dir", str(d / "diff"), "--round-seed", "5"]
        assert sampling.main([*args, "--out", str(d / "sample"), "--plan-reps", "3"]) == 0
        args = ["--sample-dir", str(d / "sample"), "--round-seed", "5", "--batch-size", "100"]
        assert assign.main([*args, "--out", str(d / "assign")]) == 0

    chain(tmp_path / "one")
    chain(tmp_path / "two")
    for step in ("diff", "sample", "assign"):
        cmp = verify.compare_dirs(tmp_path / "one" / step, tmp_path / "two" / step)
        assert cmp["identical"] and cmp["n_files"] > 0, cmp
    one = tmp_path / "one"
    res = verify.blinding_audit(one / "assign", one / "sample", run_dir)
    assert res["ok"], res["problems"][:5]
    assert res["roles"]["A"]["conflicting_pairs_in_one_batch"] == 0
    assert res["n_conflicts"] >= res["n_pair_edges"] > 0
    # Tampering is caught: a leaked token in `claimed`, and a batch record edited.
    items = (one / "assign" / "items.jsonl").read_text().splitlines()
    it = json.loads(items[0])
    batch_dir = one / "assign" / "batches" / "A" / "batch"
    bfile = next(iter(sorted(batch_dir.glob("batch_*.jsonl"))))
    lines = bfile.read_text().splitlines()
    lines[0] = lines[0].replace('"marker": "', '"marker": "x', 1)
    bfile.write_text("\n".join(lines) + "\n")
    it["claimed"] = dict(it["claimed"], note="COMPLETE")
    items[0] = json.dumps(it, ensure_ascii=False)
    (one / "assign" / "items.jsonl").write_text("\n".join(items) + "\n")
    bad = verify.blinding_audit(one / "assign", one / "sample", run_dir)
    assert not bad["ok"]
    assert any("COMPLETE" in p for p in bad["problems"])
    assert any("differs from items.jsonl" in p for p in bad["problems"])
    assert any("payload differs" in p for p in bad["problems"])


def test_round_seed_is_the_archived_collection_seed(tmp_path):
    rd = tmp_path / "round"
    rd.mkdir()
    (rd / "collection.json").write_text(json.dumps({"seed": 99}))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps({"round_dir": str(rd)}))
    assert sampling.round_seed_of(run_dir, None) == 99
    assert sampling.round_seed_of(run_dir, 99) == 99
    with pytest.raises(SystemExit):
        sampling.round_seed_of(run_dir, 98)  # no seed shopping after the frames are seen
    (run_dir / "run.json").write_text(json.dumps({}))
    with pytest.raises(SystemExit):
        sampling.round_seed_of(run_dir, None)
    assert sampling.round_seed_of(run_dir, 7) == 7


def test_density_counts_per_1000_words():
    texts = [{"text_id": "T1", "register": "academic"}, {"text_id": "T2", "register": "general"}]
    words = {"T1": 2000, "T2": 500}
    rows = [
        {
            "module": "metadiscourse",
            "register": "academic",
            "claim": {"category": "hedges"},
            "raw": {},
        },
        {
            "module": "metadiscourse",
            "register": "general",
            "claim": {"category": "hedges"},
            "raw": {},
        },
        {"module": "phrase", "register": "general", "claim": {}, "raw": {"k_band": 2}},
    ]
    d = crosswalk.density({"BASELINE": rows}, texts, words)
    md = d["configs"]["BASELINE"]["metadiscourse"]
    assert d["words"] == {"academic": 2000, "all": 2500, "general": 500}
    assert md["academic"]["hedges"] == {"hits": 1, "per_1000_words": 0.5}
    assert md["all"]["all"] == {"hits": 2, "per_1000_words": 0.8}
    assert d["configs"]["BASELINE"]["phrase"]["general"]["K2"]["per_1000_words"] == 2.0


def test_retry_batches_keep_conflicting_items_apart(tmp_path):
    run_dir = tmp_path / "run"
    _write_frames(run_dir)
    assert crosswalk.main(["--run-dir", str(run_dir), "--out", str(tmp_path / "diff")]) == 0
    args = ["--run-dir", str(run_dir), "--diff-dir", str(tmp_path / "diff"), "--round-seed", "5"]
    assert sampling.main([*args, "--out", str(tmp_path / "sample"), "--plan-reps", "1"]) == 0
    ad = tmp_path / "assign"
    assert assign.main(["--sample-dir", str(tmp_path / "sample"), "--out", str(ad)]) == 0
    with pytest.raises(SystemExit):  # the assignment's seed is the sample's
        assign.main(
            [
                "--sample-dir",
                str(tmp_path / "sample"),
                "--round-seed",
                "6",
                "--out",
                str(tmp_path / "x"),
            ]
        )
    key = read_jsonl(ad / "key.jsonl")
    units = read_jsonl(tmp_path / "sample" / "units.jsonl")
    id_of = {k["payload_sha256"]: k["id"] for k in key}
    x, y = next(iter(sorted(assign.conflict_edges(units))))
    x, y = id_of[x], id_of[y]
    items = {i["id"]: i for i in read_jsonl(ad / "items.jsonl")}
    rows = [{"id": k["id"], "module": k["module"], "category": k["category"]} for k in key]
    la = analyse.make_dummy_labels(rows, items, 1)
    lb = [r for r in analyse.make_dummy_labels(rows, items, 2) if r["id"] not in (x, y)]
    (tmp_path / "A.jsonl").write_text("".join(json.dumps(r) + "\n" for r in la))
    (tmp_path / "B.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lb))
    rc = assign.main_retry(
        [
            "--assign-dir",
            str(ad),
            "--labels",
            f"A={tmp_path / 'A.jsonl'}",
            f"B={tmp_path / 'B.jsonl'}",
        ]
    )
    assert rc == 0
    man_b = read_jsonl(ad / "retry" / "retry_B.jsonl")
    assert {x, y} <= {r["id"] for r in man_b}
    # The manifest is exactly analyse.py's.
    ls = analyse.load_labels(tmp_path / "B.jsonl", items, None, "B")
    analyse.write_retry_manifest(ls, tmp_path / "expect_B.jsonl")
    assert (tmp_path / "expect_B.jsonl").read_bytes() == (
        ad / "retry" / "retry_B.jsonl"
    ).read_bytes()
    bm = read_json(ad / "retry" / "batches" / "B" / "retry" / "retry_manifest.json")
    where = {i: b["batch"] for b in bm["batches"] for i in b["ids"]}
    assert set(where) == {r["id"] for r in man_b}
    assert where[x] != where[y]  # batches.py alone would have put both in one retry batch
    assert read_json(ad / "retry" / "retry.json")["roles"]["A"]["n_retry"] == 0
    from fixcheck import verify

    res = verify.blinding_audit(ad, tmp_path / "sample", run_dir, retry_dirs=[ad / "retry"])
    assert res["ok"], res["problems"][:5]
    assert res["roles"]["retry B (retry)"]["n_items"] == len(man_b)


def test_prepare_candidate_freezes_an_importable_copy(tmp_path, monkeypatch):
    from fixcheck import run

    monkeypatch.setattr(run, "python_cmd", lambda checkout: [sys.executable, "-I"])
    co = tmp_path / "co"
    pkg = co / "src" / "lexinspect"
    (pkg / "__pycache__").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "_fix_families.py").write_text("FAMILIES = ()\n")
    (pkg / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (co / "uv.lock").write_text("lock\n")
    rec = run.prepare_candidate(co, tmp_path / "snap")
    assert rec["tree_sha256"] == run.pkg_digest(tmp_path / "snap" / "lexinspect")["tree_sha256"]
    assert rec["tree_sha256"] == run.src_tree_digest(co)["tree_sha256"]
    assert not (tmp_path / "snap" / "lexinspect" / "__pycache__").exists()
    assert rec["uv_lock_sha256"] == run.sha256_file(co / "uv.lock")
    with pytest.raises(SystemExit):  # never into a non-empty directory
        run.prepare_candidate(co, tmp_path / "snap")
    (pkg / "__init__.py").write_text("from lexinspect._context import missing\n")
    with pytest.raises(SystemExit, match="does not import"):  # a half-edited tree is refused
        run.prepare_candidate(co, tmp_path / "snap2")
    assert not (tmp_path / "snap2" / "lexinspect").exists()
    # run refuses a snapshot edited after it was frozen, before any worker starts
    (tmp_path / "snap" / "lexinspect" / "__init__.py").write_text("x = 1\n")
    (tmp_path / "round").mkdir()
    with pytest.raises(SystemExit, match="no longer matches"):
        run.main(
            [
                "--round-dir",
                str(tmp_path / "round"),
                "--out",
                str(tmp_path / "out"),
                "--checkout",
                str(co),
                "--candidate-src",
                str(tmp_path / "snap"),
            ]
        )
