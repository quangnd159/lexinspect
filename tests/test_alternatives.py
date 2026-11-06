"""Simpler-alternative suggestions: data integrity, inflection, precision, text API."""

from __future__ import annotations

import json
import time
from importlib import resources

import pytest
from conftest import analysed

from lexinspect import _lists, alternatives, cefr, errors
from lexinspect.alternatives import LEVELS, inflect, match_case, suggest

CEFR_POS = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}


@pytest.fixture(scope="module")
def data():
    return alternatives._data()


# --- data integrity --------------------------------------------------------------


def test_metadata_and_size(data):
    path = resources.files("lexinspect.data").joinpath("alternatives.json")
    assert len(path.read_bytes()) < 1_500_000
    for key in ("source", "version", "license", "attribution"):
        assert data[key], key
    assert "Open English WordNet" in data["attribution"]
    assert "CC-BY-SA-4.0" in data["license"]
    assert data["level_order"] == list(LEVELS)
    assert data["entry_count"] == len(data["entries"]) > 500
    meta = alternatives.meta()
    assert set(meta) == {"source", "version", "license", "attribution"}


def test_every_suggestion_is_lower_level_same_pos(data):
    entries = _lists.cefr_entries()
    bands = _lists.bnc_forms()
    for key, (lvl, alts) in data["entries"].items():
        lemma, pos = key.split("|")
        label = CEFR_POS[pos]
        # The headword's stored level is the CEFR list's level for that POS.
        assert LEVELS[lvl] == entries[lemma]["by_pos"][label], key
        assert lvl > 0, key  # A1 words are never simplified
        assert 1 <= len(alts) <= 5, key
        words = [w for w, _, _ in alts]
        assert len(set(words)) == len(words), key
        for word, wlvl, band in alts:
            assert word != lemma, key
            assert word.isalpha() and word.islower(), (key, word)
            assert wlvl < lvl, (key, word)
            # Same POS, and the level stored is the list's level for that POS.
            assert LEVELS[wlvl] == entries[word]["by_pos"][label], (key, word)
            fam = bands.get(word)
            assert band == (fam.band if fam else 99), (key, word)


def test_no_offensive_or_blocked_words(data):
    offensive = {"bloody", "damn", "hell", "crap", "shit", "bitch", "bastard", "piss", "screw"}
    for key, (_lvl, alts) in data["entries"].items():
        assert not offensive & {w for w, _, _ in alts}, key


def test_forms_table_shape(data):
    for lemma, tags in data["forms"].items():
        for tag, form in tags.items():
            assert tag in {"NNS", "VBZ", "VBD", "VBN", "VBG", "JJR", "JJS", "RBR", "RBS"}
            assert form is None or isinstance(form, str) or len(form) == 2, (lemma, tag)


def test_loads_fast():
    alternatives._data.cache_clear()
    alternatives._gb_to_lemma.cache_clear()
    t = time.perf_counter()
    alternatives.warm()
    assert time.perf_counter() - t < 0.1


# --- inflection -----------------------------------------------------------------


@pytest.mark.parametrize(
    "lemma,tag,expected",
    [
        ("help", "VBZ", "helps"),
        ("help", "VBD", "helped"),
        ("help", "VBG", "helping"),
        ("investigate", "VBD", "investigated"),
        ("investigate", "VBG", "investigating"),
        ("try", "VBZ", "tries"),
        ("try", "VBD", "tried"),
        ("fix", "VBZ", "fixes"),
        ("go", "VBZ", "goes"),
        ("lie", "VBG", "lying"),
        ("see", "VBG", "seeing"),
        ("stop", "VBG", "stopping"),
        ("stop", "VBD", "stopped"),
        ("buy", "VBD", "bought"),
        ("hide", "VBN", "hidden"),
        ("hide", "VBD", "hid"),
        ("get", "VBN", "got"),
        ("quit", "VBN", "quit"),
        ("think", "VBD", "thought"),
        ("large", "JJR", "larger"),
        ("big", "JJR", "bigger"),
        ("big", "JJS", "biggest"),
        ("happy", "JJR", "happier"),
        ("bad", "JJR", "worse"),
        ("true", "JJR", "truer"),
        ("important", "JJR", "more important"),
        ("important", "JJS", "most important"),
        ("city", "NNS", "cities"),
        ("box", "NNS", "boxes"),
        ("child", "NNS", "children"),
        ("life", "NNS", "lives"),
        ("help", "VB", "help"),
        ("help", "VBP", "help"),
        ("help", "NN", "help"),
        ("big", "JJ", "big"),
    ],
)
def test_inflect(lemma, tag, expected):
    assert inflect(lemma, tag) == expected


def test_inflect_respects_pos():
    # A noun suggestion doesn't take a verb's ending, and vice versa.
    assert inflect("help", "VBZ", pos="noun") == "help"
    assert inflect("help", "NNS", pos="verb") == "help"
    assert inflect("help", "VBZ", pos="VERB") == "helps"


def test_inflect_variant_spelling():
    assert inflect("cruel", "JJR", variant="gb") == "crueller"
    assert inflect("cruel", "JJR", variant="us") == "crueler"


def test_match_case():
    assert match_case("Benefits", "helps") == "Helps"
    assert match_case("CONCEALED", "hid") == "HID"
    assert match_case("larger", "bigger") == "bigger"
    assert match_case("A", "big") == "Big"  # one capital letter is a capitalised word


# --- suggest() -------------------------------------------------------------------


def test_suggest_shape_and_inflection():
    out = suggest("assist", "verb", "A2", "VBZ")
    assert out[0] == {"word": "help", "level": "A1", "band": 1, "form": "helps"}
    assert suggest("purchase", "VERB", "A1", "VBD")[0]["form"] == "bought"
    assert [s["form"] for s in suggest("enormous", "ADJ", "A1", "JJR")] == ["bigger", "larger"]
    assert suggest("conceal", "v", "B1", "VBN")[0]["form"] == "hidden"
    assert suggest("assist", "verb", "A2")[0]["form"] == "help"


def test_suggest_filters_by_target():
    # Already at or below the target: nothing to simplify.
    assert suggest("assist", "verb", "B1") == []
    assert suggest("assist", "verb", "C2") == []
    # Suggestions above the target are dropped.
    immense = suggest("immense", "adjective", "A1")
    assert immense and all(s["level"] == "A1" for s in immense)
    assert {s["word"] for s in suggest("immense", "adjective", "B1")} >= {"huge", "big"}


def test_suggest_unknowns():
    assert suggest("zzzz", "noun", "A1") == []
    assert suggest("assist", "noun", "A1") == []  # no noun entry
    assert suggest("assist", "PRON", "A1") == []
    with pytest.raises(ValueError):
        suggest("assist", "verb", "D1")


def test_suggest_british_spelling(data):
    us, gb = next(iter(data["gb"].items()))
    key = next(k for k, (_l, alts) in data["entries"].items() if us in {a[0] for a in alts})
    lemma, pos = key.split("|")
    below = LEVELS[data["entries"][key][0] - 1]
    gb_words = {s["word"] for s in suggest(lemma, pos, below, variant="gb")}
    us_words = {s["word"] for s in suggest(lemma, pos, below, variant="us")}
    assert gb in gb_words and us in us_words


# --- hand-curated precision ---------------------------------------------------------
# Words a teacher plausibly wants to simplify, with an expected plain synonym.
# Each must be offered (in the word's main sense) to a reader at that level.

EXPECTED = [
    ("significant", "adjective", "A1", "important"),
    ("demonstrate", "verb", "A2", "show"),
    ("allow", "verb", "A1", "let"),
    ("assist", "verb", "A1", "help"),
    ("purchase", "verb", "A1", "buy"),
    ("acquire", "verb", "A1", "get"),
    ("obtain", "verb", "A1", "get"),
    ("require", "verb", "A2", "need"),
    ("conceal", "verb", "A1", "hide"),
    ("enormous", "adjective", "A1", "big"),
    ("immense", "adjective", "B1", "huge"),
    ("massive", "adjective", "A1", "large"),
    ("vast", "adjective", "A1", "large"),
    ("huge", "adjective", "A1", "big"),
    ("rapid", "adjective", "A1", "fast"),
    ("swift", "adjective", "A1", "fast"),
    ("approximately", "adverb", "A1", "about"),
    ("frequently", "adverb", "A1", "often"),
    ("nevertheless", "adverb", "A2", "however"),
    ("hence", "adverb", "B1", "therefore"),
    ("merely", "adverb", "A1", "just"),
    ("scarcely", "adverb", "B1", "hardly"),
    ("largely", "adverb", "A2", "mostly"),
    ("occur", "verb", "A1", "happen"),
    ("encounter", "verb", "A1", "meet"),
    ("remain", "verb", "A1", "stay"),
    ("inhabit", "verb", "A1", "live"),
    ("vanish", "verb", "B1", "disappear"),
    ("cease", "verb", "A1", "stop"),
    ("alter", "verb", "A1", "change"),
    ("construct", "verb", "A1", "build"),
    ("diminish", "verb", "B1", "decrease"),
    ("accumulate", "verb", "B1", "collect"),
    ("utilize", "verb", "A1", "use"),
    ("attempt", "verb", "A2", "try"),
    ("select", "verb", "A1", "choose"),
    ("inquire", "verb", "A1", "ask"),
    ("respond", "verb", "A1", "answer"),
    ("prohibit", "verb", "B1", "forbid"),
    ("envisage", "verb", "B1", "imagine"),
    ("recollect", "verb", "A1", "remember"),
    ("wealthy", "adjective", "A1", "rich"),
    ("exhausted", "adjective", "A1", "tired"),
    ("frightened", "adjective", "A1", "afraid"),
    ("terrified", "adjective", "A2", "frightened"),
    ("delighted", "adjective", "A2", "pleased"),
    ("furious", "adjective", "A1", "angry"),
    ("peculiar", "adjective", "A2", "strange"),
    ("challenging", "adjective", "A1", "difficult"),
    ("tedious", "adjective", "A2", "boring"),
    ("lengthy", "adjective", "A1", "long"),
    ("brief", "adjective", "A1", "short"),
    ("entire", "adjective", "A2", "whole"),
    ("initial", "adjective", "A1", "first"),
    ("assistance", "noun", "A2", "help"),
    ("deficiency", "noun", "A2", "lack"),
    ("controversy", "noun", "B1", "argument"),
    ("perspiration", "noun", "B1", "sweat"),
    ("photograph", "noun", "A1", "photo"),
    ("author", "noun", "A1", "writer"),
    ("pupil", "noun", "A1", "student"),
    ("tale", "noun", "A1", "story"),
    ("edifice", "noun", "A1", "building"),
    ("tomb", "noun", "B1", "grave"),
    ("characteristic", "noun", "A2", "feature"),
    ("exterior", "noun", "B2", "outside"),
]


@pytest.mark.parametrize("lemma,pos,target,expected", EXPECTED)
def test_curated_suggestions(lemma, pos, target, expected):
    words = [s["word"] for s in suggest(lemma, pos, target)]
    assert expected in words, (lemma, words)


# Wrong-sense or off-register suggestions WordNet's synsets would produce, and
# the filters must keep out.
FORBIDDEN = [
    ("benefit", "noun", "welfare"),
    ("benefit", "verb", "profit"),
    ("gay", "adjective", "sunny"),
    ("state", "verb", "tell"),
    ("oath", "noun", "curse"),
    ("patronize", "verb", "sponsor"),
    ("fantastic", "adjective", "strange"),
    ("contribute", "verb", "lend"),
    ("hitch", "verb", "limp"),
    ("genius", "noun", "superstar"),
    ("remarkable", "adjective", "singular"),
    ("anticipate", "verb", "counter"),
    ("psychiatrist", "noun", "shrink"),
    ("jargon", "noun", "slang"),
    ("clip", "noun", "time"),
    ("render", "verb", "supply"),
    ("select", "verb", "decide"),
    ("northwest", "adjective", "north"),
]


@pytest.mark.parametrize("lemma,pos,bad", FORBIDDEN)
def test_curated_exclusions(lemma, pos, bad):
    assert bad not in [s["word"] for s in suggest(lemma, pos, "A1")]
    assert bad not in [s["word"] for s in suggest(lemma, pos, "C1")]


def test_ranking_prefers_true_synonyms():
    # `huge` and `vast` share `immense`'s synset; `big`/`large` come from the
    # adjective head it is similar to, so they rank after.
    words = [s["word"] for s in suggest("immense", "adjective", "B1")]
    assert words.index("huge") < words.index("big")
    assert len(words) <= 5


# --- analyze() --------------------------------------------------------------------

TEXT = (
    "Benefits are huge. The committee purchased enormous quantities and CONCEALED them. "
    "She assists her neighbours. Huge rooms. The vast hall. Mr Huge Smith smiled."
)


@pytest.fixture(scope="module")
def result():
    a = analysed(TEXT)
    return alternatives.analyze(a.text, analysis=a)


def _item(result, lemma):
    return next(it for it in result["items"] if it["lemma"] == lemma)


def test_analyze_schema(result):
    assert set(result) == {"items", "source"}
    assert "Open English WordNet" in result["source"]
    for it in result["items"]:
        assert set(it) == {"lemma", "pos", "level", "count", "suggestions", "occurrences"}
        assert it["level"] != "A1"
        assert len(it["suggestions"]) <= 5
        assert it["count"] == len(it["occurrences"])
        for s in it["suggestions"]:
            assert set(s) == {"word", "level", "band"}
            assert LEVELS.index(s["level"]) < LEVELS.index(it["level"])
        for o in it["occurrences"]:
            assert set(o) == {"span", "surface", "tag", "replacements"}
            start, end = o["span"]
            assert TEXT[start:end] == o["surface"]
            assert set(o["replacements"]) == {s["word"] for s in it["suggestions"]}


def test_analyze_inflects_and_capitalises(result):
    occ = _item(result, "purchase")["occurrences"][0]
    assert occ["surface"] == "purchased" and occ["replacements"] == {"buy": "bought"}
    occ = _item(result, "conceal")["occurrences"][0]
    assert occ["replacements"] == {"hide": "HID"}
    occ = _item(result, "assist")["occurrences"][0]
    assert occ["replacements"] == {"help": "helps"}
    huge = _item(result, "huge")
    assert [o["replacements"]["big"] for o in huge["occurrences"]] == ["big", "Big"]


def test_analyze_keeps_items_without_suggestions(result):
    benefit = _item(result, "benefit")
    assert benefit["suggestions"] == []
    assert benefit["occurrences"][0]["replacements"] == {}


def test_analyze_excludes_proper_nouns(result):
    # "Huge" in "Mr Huge Smith" is a name: only the two adjective uses count.
    assert _item(result, "huge")["count"] == 2


def test_analyze_levels_agree_with_cefr_module(result):
    out = cefr.analyze(TEXT, analysis=analysed(TEXT))
    by_level = {w["word"].lower(): lvl for lvl, ws in out["words_by_level"].items() for w in ws}
    for it in result["items"]:
        for o in it["occurrences"]:
            assert by_level[o["surface"].lower()] == it["level"], o["surface"]


def test_analyze_sorted_by_level_then_count(result):
    keys = [(-LEVELS.index(it["level"]), -it["count"]) for it in result["items"]]
    assert keys == sorted(keys)


def test_analyze_excludes_misspellings():
    text = "The comittee purchassed enormus quantities and concealed them."
    a = analysed(text)
    lemmas = {it["lemma"] for it in alternatives.analyze(text, analysis=a)["items"]}
    assert "conceal" in lemmas
    flagged = errors.analyze(text, analysis=a)
    with_errors = alternatives.analyze(text, analysis=a, errors_result=flagged)
    flagged_starts = {s[0] for e in flagged["errors"] for s in e["spans"]}
    for it in with_errors["items"]:
        for o in it["occurrences"]:
            assert o["span"][0] not in flagged_starts


def test_analyze_excludes_errors_module_flags():
    text = "They purchased food."
    a = analysed(text)
    start = text.index("purchased")
    fake = {"errors": [{"surface": "purchased", "spans": [[start, start + 9]]}]}
    out = alternatives.analyze(text, analysis=a, errors_result=fake)
    assert "purchase" not in {it["lemma"] for it in out["items"]}


def test_analyze_without_analysis():
    out = alternatives.analyze("They purchased enormous boxes.")
    assert {"purchase", "enormous"} <= {it["lemma"] for it in out["items"]}


def test_analyze_output_is_json_serialisable(result):
    json.dumps(result)


# --- for_analysis() -----------------------------------------------------------------


def test_for_analysis_filters_by_target():
    a = analysed(TEXT)
    out = alternatives.for_analysis(a, None, "A2")
    assert out["target_level"] == "A2"
    lemmas = {it["lemma"] for it in out["items"]}
    assert "enormous" not in lemmas  # A2: not above the target
    assert {"huge", "purchase", "conceal"} <= lemmas
    for it in out["items"]:
        assert LEVELS.index(it["level"]) > LEVELS.index("A2")
        assert all(LEVELS.index(s["level"]) <= LEVELS.index("A2") for s in it["suggestions"])
        words = {s["word"] for s in it["suggestions"]}
        assert all(set(o["replacements"]) == words for o in it["occurrences"])


def test_for_analysis_short_circuits_on_cefr_result():
    text = "The cat sat on the mat."
    a = analysed(text)
    out = alternatives.for_analysis(a, cefr.analyze(text, analysis=a), "B2")
    assert out["items"] == []
