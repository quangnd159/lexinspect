"""Tests for the text-free export, its guard and the recompute.

    uv run --offline --no-sync python -I -m pytest scripts/validation/study4_precision/textfree/test_textfree.py

The shape and guard tests use synthetic records. The end-to-end tests read the published
export folder (and skip when it is absent); `export --check` reads the private archive and
skips when it is absent.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import analyse  # noqa: E402
import common as C  # noqa: E402
import guard as G  # noqa: E402
import recompute as RC  # noqa: E402

EXPORT = RC.EXPORT
PRIVATE = Path.home() / "lexinspect-private" / "study4-fix040" / "round2"

SOURCE = (
    'The committee said that the new bridge would "certainly" open next spring, at least '
    "according to the minutes of the meeting held in the town hall on Tuesday evening."
)
GUIDELINE = "Label an item CORRECT only when the highlighted words do the job the claim names."


# --- synthetic label files ------------------------------------------------------------------------


def _md(cat: str) -> dict:
    return {"module": "metadiscourse", "context": SOURCE, "claimed": {"category": cat}}


PH = {
    "module": "phrase",
    "context": SOURCE,
    "claimed": {
        "expression": "AT LEAST",
        "sense": None,
        "example": "Well, you could email me at least.",
        "other_senses_in_list": [
            {"expression": "AT LEAST (MINIMUM)"},
            {"expression": "in terms of"},
        ],
    },
}
# (item, record or raw line, expected reason or None)
CASES = [
    (_md("hedges"), {"label": "CORRECT", "alt_category": None, "note": None}, None),
    (
        _md("hedges"),
        {"label": "WRONG_CATEGORY", "alt_category": "boosters", "note": "the town hall says so"},
        None,
    ),
    (
        _md("hedges"),
        {"label": "WRONG_CATEGORY", "alt_category": "hedges", "note": None},
        "alt_category_same_as_claimed",
    ),
    (
        _md("hedges"),
        {"label": "WRONG_CATEGORY", "alt_category": " boosters", "note": None},
        "alt_category_invalid",
    ),
    (
        _md("hedges"),
        {"label": "WRONG_CATEGORY", "alt_category": "certainly opens", "note": None},
        "alt_category_invalid",
    ),
    (
        _md("hedges"),
        {
            "label": "UNSURE",
            "alt_category": None,
            "note": "hedges or boosters: the bridge would certainly open",
        },
        None,
    ),
    (
        _md("hedges"),
        {"label": "UNSURE", "alt_category": None, "note": "CORRECT or NOT_METADISCOURSE:quoted"},
        None,
    ),
    (
        _md("hedges"),
        {"label": "UNSURE", "alt_category": None, "note": "hedges: the minutes"},
        "unsure_too_few_readings",
    ),
    (
        _md("hedges"),
        {"label": "UNSURE", "alt_category": None, "note": "maybe the minutes are wrong"},
        "unsure_note_format",
    ),
    (
        _md("hedges"),
        {"label": "UNSURE", "alt_category": None, "note": "hedges or bridges: the minutes"},
        "unsure_reading_invalid",
    ),
    (
        _md("hedges"),
        {"label": "UNSURE", "alt_category": None, "note": "   "},
        "unsure_without_note",
    ),
    (
        _md("hedges"),
        {"label": "NOT_METADISCOURSE", "alt_category": None, "note": " ".join(["lorem"] * 30)},
        "note_too_long",
    ),
    (
        _md("hedges"),
        {"label": "EXTERNAL_CONNECTIVE", "alt_category": None, "note": None},
        "external_connective_not_transitions",
    ),
    (
        _md("transitions"),
        {"label": "EXTERNAL_CONNECTIVE", "alt_category": None, "note": None},
        None,
    ),
    (
        _md("hedges"),
        {"label": "CORRECT", "alt_category": "boosters", "note": None},
        "alt_category_not_allowed",
    ),
    (_md("hedges"), {"label": "correct", "alt_category": None, "note": None}, "invalid_label"),
    (
        _md("hedges"),
        {"label": "Correct!? maybe", "alt_category": None, "note": None},
        "invalid_label",
    ),
    (_md("hedges"), {"label": 3, "alt_category": None, "note": None}, "invalid_field_type"),
    (_md("hedges"), {"label": "CORRECT", "alt_category": None}, "missing_field"),
    (
        PH,
        {"label": "WRONG_SENSE_LISTED", "alt_category": "at least  (minimum)", "note": None},
        None,
    ),
    (
        PH,
        {"label": "WRONG_SENSE_LISTED", "alt_category": "SOMETHING ELSE", "note": None},
        "alt_sense_not_listed",
    ),
    (
        PH,
        {"label": "WRONG_SENSE_UNLISTED", "alt_category": "BARE MINIMUM AMOUNT", "note": None},
        None,
    ),
    (
        PH,
        {"label": "WRONG_SENSE_UNLISTED", "alt_category": "bare minimum", "note": None},
        "gloss_not_capitals",
    ),
    (
        PH,
        {"label": "WRONG_SENSE_UNLISTED", "alt_category": "IN TERMS OF", "note": None},
        "alt_sense_is_listed",
    ),
    (
        PH,
        {"label": "WRONG_SENSE_UNLISTED", "alt_category": "AT LEAST", "note": None},
        "alt_sense_is_listed",
    ),
    (
        PH,
        {
            "label": "WRONG_SENSE_UNLISTED",
            "alt_category": "ONE TWO THREE FOUR FIVE SIX SEVEN",
            "note": None,
        },
        "gloss_word_count",
    ),
    (
        PH,
        {"label": "WRONG_SENSE_UNLISTED", "alt_category": "   ", "note": None},
        "alt_category_missing",
    ),
    (
        PH,
        {
            "label": "UNSURE",
            "alt_category": None,
            "note": "CORRECT or NOT_THE_EXPRESSION: at least the minutes",
        },
        None,
    ),
]


def synthetic() -> tuple[dict, list[str], list[str]]:
    items, lines, ids = {}, [], []
    for i, (it, rec, _) in enumerate(CASES):
        rid = f"{i:010x}"
        items[rid] = {"id": rid, **json.loads(json.dumps(it))}
        lines.append(json.dumps({"id": rid, **rec}))
        ids.append(rid)
    dup, bad_dup, conflict = (f"{len(CASES) + k:010x}" for k in range(3))
    items[dup] = {"id": dup, **_md("boosters")}
    items[bad_dup] = {"id": bad_dup, **_md("boosters")}
    items[conflict] = {"id": conflict, **PH}
    lines += [
        json.dumps({"id": dup, "label": "CORRECT", "alt_category": None, "note": "first copy"}),
        "",
        json.dumps({"id": dup, "label": "CORRECT", "alt_category": None, "note": "second copy"}),
        json.dumps({"id": bad_dup, "label": "CORRECT", "alt_category": None, "note": None}),
        json.dumps({"id": bad_dup, "label": "correct", "alt_category": "", "note": None}),
        json.dumps(
            {
                "id": conflict,
                "label": "WRONG_SENSE_UNLISTED",
                "alt_category": "BARE MINIMUM",
                "note": None,
            }
        ),
        json.dumps(
            {
                "id": conflict,
                "label": "WRONG_SENSE_UNLISTED",
                "alt_category": "TOWN HALL",
                "note": None,
            }
        ),
        '{"id": "'
        + dup
        + '", "label": "CORRECT", "note": "the bridge would certainly',  # malformed
        json.dumps(["the committee said"]),
        json.dumps({"label": "CORRECT", "alt_category": None, "note": None}),
        json.dumps(
            {
                "id": "the-minutes-of-the-meeting",
                "label": "CORRECT",
                "alt_category": None,
                "note": None,
            }
        ),
    ]
    return items, lines, ids + [dup, bad_dup, conflict]


def test_shapes_keep_the_validator_result_and_carry_no_text():
    items, lines, _ = synthetic()
    reg = C.Registry()
    C.encode_file(lines, items, reg)
    reg.freeze()
    shapes = C.encode_file(lines, items, reg)
    pseudo = {i: C.pseudo_item(C.item_shape(it)) for i, it in items.items()}
    summary = C.verify_labels(lines, shapes, items, pseudo, None, "synthetic")
    reasons = set(summary["problems_by_reason"])
    for _, _, want in CASES:
        if want is not None:
            assert want in reasons, want
    assert {
        "conflicting_duplicate",
        "invalid_duplicate",
        "malformed_json",
        "not_an_object",
        "missing_id",
        "unknown_id",
    } <= reasons
    assert summary["warnings"] == 1  # the identical duplicate, notes ignored
    text = "\n".join(shapes)
    for s in (
        "bridge",
        "minutes",
        "MINIMUM",
        "minimum",
        "TOWN",
        "town",
        "SOMETHING",
        "terms",
        "certainly",
        "lorem",
    ):
        assert s not in text, s
    assert len(shapes) == len(lines) and shapes[lines.index("")] == ""


def test_shapes_number_glosses_per_dataset_not_per_file():
    items, _, ids = synthetic()
    rid = ids[-1]

    def rec(gloss: str) -> list[str]:
        return [
            json.dumps(
                {"id": rid, "label": "WRONG_SENSE_UNLISTED", "alt_category": gloss, "note": None}
            )
        ]

    reg = C.Registry()
    for f in (rec("TOWN HALL"), rec("BARE MINIMUM"), rec("town  hall")):
        C.encode_file(f, items, reg)
    reg.freeze()
    alt = [
        json.loads(C.encode_file(f, items, reg)[0])["alt_category"]
        for f in (rec("TOWN HALL"), rec("BARE MINIMUM"), rec("town  hall"))
    ]
    assert alt == ["G1 X", "G0 X", "g1 x"]


def test_retry_merge_commutes_with_shapes():
    items, lines, ids = synthetic()
    retry = [
        json.dumps({"id": ids[2], "label": "CORRECT", "alt_category": None, "note": "fixed it"})
    ]
    reg = C.Registry()
    for f in (lines, retry):
        C.encode_file(f, items, reg)
    reg.freeze()
    real, _ = analyse.merge_retry(lines, retry, [ids[2]])
    shaped, _ = analyse.merge_retry(
        C.encode_file(lines, items, reg), C.encode_file(retry, items, reg), [ids[2]]
    )
    assert shaped == C.encode_file(real, items, reg)


def test_substratum_codes_preserve_order():
    names = {
        "hedges|rest",
        "hedges|marker=may",
        "hedges|marker=might",
        "K3-multi|marker=UP TO (UNTIL)",
        "K3-multi|rest",
        "K1-single|marker=SUCH AS",
    }
    codes = C.SubstratumCodes(names)
    assert [codes(n) for n in sorted(names)] == sorted(codes(n) for n in names)
    assert codes("hedges|rest") == "hedges|rest"
    assert all("UP TO" not in codes(n) and "may" not in codes(n) for n in names)
    assert codes.replace_in({"K3-multi|marker=UP TO (UNTIL)": ["K1-single|marker=SUCH AS"]}) == {
        codes("K3-multi|marker=UP TO (UNTIL)"): [codes("K1-single|marker=SUCH AS")]
    }
    with pytest.raises(ValueError):
        C.SubstratumCodes({"hedges|other"})


# --- guard --------------------------------------------------------------------------------------


@pytest.fixture
def corpus() -> G.Corpus:
    return G.Corpus([SOURCE, GUIDELINE])


@pytest.fixture
def fragments(tmp_path: Path) -> Path:
    p = tmp_path / "fragments.txt"
    p.write_text("a restricted inventory fragment line\n", encoding="utf-8")
    return p


def scan(files: dict[str, bytes], corpus: G.Corpus, fragments: Path) -> dict:
    return G.scan_files(files, corpus, headwords=["AT LEAST", "IN TERMS OF"], fragments=fragments)


def jl(*recs: dict) -> bytes:
    return C.dump_jsonl([C.dump_line(r) for r in recs])


def test_guard_passes_clean_shapes(corpus, fragments):
    items, lines, _ = synthetic()
    reg = C.Registry()
    C.encode_file(lines, items, reg)
    reg.freeze()
    files = {
        "labels.jsonl.gz": C.gz(C.dump_jsonl(C.encode_file(lines, items, reg))),
        "items.jsonl": jl(*(C.item_shape(it) for it in items.values())),
        "frame.json": C.dump_json({"modules": {"phrase": {"K1-single|rest": {"N": 3}}}}),
        "README.md": b"A text-free export.\n",
    }
    res = scan(files, corpus, fragments)
    assert res["ok"], res["findings"]


@pytest.mark.parametrize(
    "rec, check",
    [
        ({"id": "x", "context": "a sentence"}, "keys"),
        ({"id": "x", "label": "CORRECT", "note": "short"}, "keys"),
        ({"id": "x", "gloss": "BARE MINIMUM"}, "keys"),
        ({"id": "x", "claimed": {"category": "hedges"}}, "keys"),
        ({"id": "x", "marker": "at least"}, "keys"),
        ({"id": "x", "alt_category": SOURCE[40:75]}, "source_text"),  # 35 chars of a source
        ({"id": "x", "alt_category": SOURCE[30:62]}, "source_text"),  # spans a JSON-escaped quote
        ({"id": "x", "rule": GUIDELINE[10:45]}, "source_text"),  # guideline text
        ({"id": "x", "alt_category": "AT LEAST"}, "phrase_headwords"),
        ({"id": "x", "v": "see a restricted inventory fragment line here"}, "restricted_fragments"),
    ],
)
def test_guard_catches_injected_text(corpus, fragments, rec, check):
    for rel, data in (("x.jsonl", jl(rec)), ("x.jsonl.gz", C.gz(jl(rec)))):
        res = scan({rel: data, "ok.json": C.dump_json({"a": 1})}, corpus, fragments)
        assert not res["ok"]
        assert {f["check"] for f in res["findings"]} >= {check}, res["findings"]
        assert all(f["file"] == rel for f in res["findings"])
        assert SOURCE[40:75] not in G.report(res)


def test_guard_catches_text_in_plain_files(corpus, fragments):
    res = scan({"README.md": ("Quoted: " + SOURCE[60:100]).encode()}, corpus, fragments)
    assert [f["check"] for f in res["findings"]] == ["source_text"]


def test_guard_allows_module_names_as_keys(corpus, fragments):
    res = scan(
        {"f.json": C.dump_json({"modules": {"phrase": {}, "metadiscourse": {}}})}, corpus, fragments
    )
    assert res["ok"]


def test_guard_window_hash_is_exact_on_short_strings():
    c = G.Corpus([SOURCE])
    assert c.matches(SOURCE[:29]) == []
    assert c.matches("xx" + SOURCE[5:35] + "yy") == [(2, 30)]
    assert c.matches(SOURCE[5:70]) == [(0, 65)]


# --- end to end ----------------------------------------------------------------------------------

needs_export = pytest.mark.skipif(not (EXPORT / "SHA256SUMS").exists(), reason="no export folder")


@needs_export
def test_recompute_reproduces_every_published_value(tmp_path: Path):
    out = tmp_path / "report.json"
    assert RC.main(["--export", str(EXPORT), "--json", str(out)]) == 0
    rep = json.loads(out.read_text())
    targets = {r["target"] for r in rep["checks"]}
    assert {"1 pilot040", "2 pilot032", "3 gates", "4 sensitivity"} <= targets
    assert rep["failed"] == 0


@needs_export
def test_recompute_detects_a_changed_label(tmp_path: Path):
    ex = tmp_path / "export"
    shutil.copytree(EXPORT, ex)
    rel = "fixcheck/round2/labels/B.jsonl.gz"
    lines = C.read_lines(ex / rel)
    i = next(k for k, x in enumerate(lines) if '"label":"CORRECT"' in x)
    lines[i] = lines[i].replace('"label":"CORRECT"', '"label":"NOT_METADISCOURSE"')
    (ex / rel).write_bytes(C.gz(C.dump_jsonl(lines)))
    assert RC.main(["--export", str(ex)]) == 1  # SHA256SUMS no longer matches
    sums = (ex / "SHA256SUMS").read_text().splitlines()
    sums = [f"{C.sha256_file(ex / rel)}  {rel}" if s.endswith("  " + rel) else s for s in sums]
    (ex / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    out = tmp_path / "report.json"
    assert RC.main(["--export", str(ex), "--json", str(out)]) == 1
    failed = {r["target"] for r in json.loads(out.read_text())["checks"] if not r["ok"]}
    assert failed == {"3 gates", "4 sensitivity"}


@needs_export
def test_export_folder_passes_the_guard():
    if not G.default_corpora():
        pytest.skip("no source texts")
    res = G.scan_files(
        G.read_folder(EXPORT),
        G.default_corpora(),
        fragments=G.FRAGMENTS if G.FRAGMENTS.exists() else None,
    )
    assert res["ok"], res["findings"]


@pytest.mark.skipif(not PRIVATE.exists(), reason="no private archive")
def test_export_is_deterministic():
    import export as EX

    assert EX.main(["--check", "--no-guard"]) == 0


def test_gzip_is_deterministic():
    data = b'{"a":1}\n' * 100
    assert C.gz(data) == C.gz(data) and gzip.decompress(C.gz(data)) == data
