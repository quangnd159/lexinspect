"""Build `alternatives.json`: simpler same-POS synonyms for CEFR headwords.

    uv run --with lemminflect==0.2.3 python scripts/build_data/build_alternatives.py
    uv run --with lemminflect==0.2.3 python scripts/build_data/build_alternatives.py --show benefit,vital
    uv run --with lemminflect==0.2.3 python scripts/build_data/build_alternatives.py --sample 150

Downloads (pinned, SHA-256 verified, cached under `.cache/alternatives/`):

- Open English WordNet 2025 (WN-LMF XML, CC BY 4.0): synsets, sense order,
  usage labels and adjective `similar` links. Every suggestion comes from here.
- Princeton WordNet 3.0 database (WordNet 3.0 licence): only its `index.sense`
  SemCor tag counts are read, to tell a dominant sense from a rare one. OEWN
  keeps the 3.0 sense keys but ships every tag count as 0. No 3.0 text or
  relation is copied into the output.

For every single-word noun, verb, adjective or adverb on lexinspect's CEFR list
at A2 or above, the build keeps up to `MAX_ALTS` synonyms that are themselves
on the list, at a lower level, for the same part of speech. Precision matters
far more than recall — a wrong-sense suggestion ("benefit" -> "welfare") makes
the feature look stupid — so a candidate has to clear every one of these:

1. It shares a synset with the headword's *dominant* sense: the most-tagged
   sense, holding at least half the word's SemCor tags (sense 1 when the word
   is untagged and has at most two senses). Words with no dominant sense get
   only synonyms found in both of their top two senses.
2. That synset is also one of the *candidate's* own main senses, with SemCor
   evidence — shared by a rare sense of the candidate doesn't count
   (`understand` is not `get`).
3. Neither sense is labelled slang, colloquial, archaic, obscene, disparaging
   or an ethnic slur, and the candidate isn't on the offensive-word list.
4. It is lowercase (not a proper noun), alphabetic, one word, not a spelling
   variant of the headword, and not on the reviewed block lists below.

Adjective satellites also offer the members of their head synset (`vast` ->
`large`), ranked after true synonyms. Within a tier, candidates rank by CEFR
level, then BNC/COCA band. Every threshold below was set by reading random
samples of the output; the comments say what each one removed.

Inflected forms for the runtime's rule set: lemminflect (build time only, not a
runtime dependency) generates every form of every suggested word; the output
keeps only the forms the runtime's suffix rules would get wrong.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import random
import re
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src" / "lexinspect" / "data"
CACHE = ROOT / ".cache" / "alternatives"
sys.path.insert(0, str(ROOT / "src"))

from lexinspect.alternatives import regular_form  # noqa: E402  (the runtime rules, to diff against)

OEWN = {
    "url": "https://github.com/globalwordnet/english-wordnet/releases/download/2025-edition/english-wordnet-2025.xml.gz",
    "sha256": "9ca6d1dcb75f822fdd66617f7d9da48142ace38dd544d6ad5e2feca1674ad3fe",
    "file": "english-wordnet-2025.xml.gz",
}
PWN30 = {
    "url": "https://wordnetcode.princeton.edu/3.0/WNdb-3.0.tar.gz",
    "sha256": "658b1ba191f5f98c2e9bae3e25c186013158f30ef779f191d2a44e5d25046dc8",
    "file": "WNdb-3.0.tar.gz",
}

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_POS = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "r"}
MAX_ALTS = 5
# A tagged headword whose top sense holds less than this share of its tags is
# too ambiguous to simplify blind (`contribute`, `launch`, `trouble`).
TARGET_MIN_SHARE = 0.5
# ...and a word with many senses needs at least this many tags in all.
TARGET_MIN_TAGS = 3
# With no tag counts at all, sense order is the only evidence; trust sense 1
# only when the word has at most this many senses.
UNTAGGED_MAX_SENSES = 2
# Candidate side: its sense in the shared synset must hold this share of its
# SemCor tags, or the lower share with at least that many tags.
CAND_MIN_SHARE = 0.25
CAND_MIN_SHARE_FREQ = 0.2
CAND_MIN_COUNT_FREQ = 8
# A candidate sense seen only once in SemCor is too thin to trust (`opponent` ->
# `opposite`, `brilliantly` -> `brightly`).
CAND_MIN_COUNT = 2
# An adjective head reached through `similar` (`vast` -> `large`) is offered
# only when the headword's own sense has at least this many tags.
SIMILAR_MIN_TARGET_COUNT = 2
# An adjective's sense with a small share of a very polysemous candidate's tags
# still counts when it sits one step from the candidate's top sense
# (`significant` -> `important`, sense 2 of 4 tags out of 153). Tried for verbs
# too, and dropped: about half wrong (`preserve` -> `continue`, `act` -> `move`).
EXT_LOWSHARE = True
LOWSHARE_MIN_COUNT = 2
# A word with no dominant sense may still take a synonym found in *both* of its
# two top senses (`demonstrate` -> `show`, `allow` -> `let`).
EXT_SHARED2 = True
SHARED2_MIN_SHARE = 0.6
# Not used: verb hypernyms (`obtain` -> `get`, `stroll` -> `walk`) were right
# less than half the time in review (`select` -> `decide`, `rush` -> `go`).

# Members of the usage-domain synsets OEWN points `exemplifies` at. A sense
# or synset labelled with any of them is never suggested or used as evidence.
BAD_USAGE = {
    "archaism",
    "colloquialism",
    "slang",
    "argot",
    "obscenity",
    "dirty word",
    "vulgarism",
    "ethnic slur",
    "derogation",
    "disparagement",
    "figure of speech",
    "trope",
}

# On the CEFR list, but not something to offer a teacher as a one-click
# substitute (offensive, or mild swearing that a WordNet synset can surface).
OFFENSIVE = {
    "ass",
    "bastard",
    "bitch",
    "bloody",
    "crap",
    "damn",
    "dick",
    "fuck",
    "hell",
    "idiot",
    "piss",
    "pissed",
    "screw",
    "shit",
    "stupid",
    "sucker",
    "whore",
}

# Found by reviewing random samples of the build output. The statistics above
# can't catch these: WordNet's tagged top sense is not today's main meaning, or
# the shared synset is a sense learners never mean by the candidate.

# Headwords whose WordNet top sense is not their usual modern meaning.
BLOCK_TARGETS = {
    ("gay", "a"),  # top sense "bright and pleasant" -> sunny
    ("queer", "a"),  # "beyond the usual" -> singular
    ("patronize", "v"),  # sponsor; usually "talk down to"
    ("patronise", "v"),
    ("spare", "a"),  # "lacking excess flesh" -> thin, lean
    ("hitch", "v"),  # "walk impeded by injury" -> limp
    ("oath", "n"),  # "profane expression" -> curse
    ("very", "a"),  # "precisely as stated" -> precise
    ("journal", "n"),  # diary; usually an academic journal
    ("adoption", "n"),  # acceptance; usually of a child or a policy
    ("overnight", "a"),  # similar to long
}
# Candidate words never offered for this part of speech: their sense in the
# shared synset is archaic or marginal for a learner.
BLOCK_CANDIDATES: dict[str, set[str]] = {
    "a": {
        "singular",  # remarkable -> singular
        "violent",  # furious, fierce -> violent ("acting with great force")
        "dominant",  # paramount -> dominant
        "minimum",  # negligible -> minimum
        "regular",  # veritable -> regular (intensifier sense)
        "superior",  # eminent, superb -> superior
        "sacred",  # inspirational -> sacred
        "formidable",  # unnerving -> formidable
        "resonant",  # resounding -> resonant
        "continual",  # persistent -> continual
    },
    "r": {
        "all",  # wholly, completely -> all
        "yet",  # hitherto -> yet
        "curiously",  # inexplicably -> curiously
        "brightly",  # brilliantly -> brightly
    },
    "n": {
        "opposite",  # opponent -> opposite
        "force",  # personnel -> force
        "pot",  # commode -> pot
    },
    "v": {
        "suffer",  # tolerate -> suffer
        "counter",  # anticipate -> counter
        "unify",  # mingle -> unify
        "lend",  # contribute -> lend
        "engulf",  # engross -> engulf
    },
}
# Single pairs that are wrong while the candidate is fine elsewhere.
BLOCK_PAIRS: set[tuple[str, str, str]] = {
    ("state", "v", "tell"),  # "state that" -> "tell that"
    ("strip", "v", "deprive"),
    ("muddy", "a", "wet"),
    ("align", "v", "adjust"),
    ("flavor", "n", "feeling"),
    ("flavour", "n", "feeling"),
    ("consultation", "n", "interview"),
    ("genius", "n", "superstar"),
    ("soil", "n", "dirt"),
    ("manufacture", "n", "industry"),
    ("suppress", "v", "conquer"),
    ("unenviable", "a", "embarrassing"),
    ("utterly", "r", "perfectly"),
    ("absolutely", "r", "perfectly"),
    ("embarrassing", "a", "difficult"),
    ("embarrassing", "a", "hard"),
    ("fabricate", "v", "manufacture"),
    ("surrounding", "a", "close"),
    ("cheque", "n", "check"),  # a spelling variant VarCon doesn't pair at level 70
    ("picture", "v", "fancy"),
    ("thicket", "n", "brush"),
    ("concern", "v", "refer"),
}

# Reviewed pairs that the statistics reject but a teacher would want: the
# candidate's share of the shared sense is tiny (`ask` has 1 of 184 tags in
# "inquire"), or the pair sits in the headword's second sense. Each must still
# share a synset with one of the headword's top three senses in OEWN; the build
# fails if a new release drops one.
ALLOW_PAIRS: dict[tuple[str, str], list[str]] = {
    ("obtain", "v"): ["get"],
    ("inquire", "v"): ["ask"],
    ("enquire", "v"): ["ask"],
    ("respond", "v"): ["answer"],
    ("furious", "a"): ["angry"],
}
ALLOW_TOP_SENSES = 3

# lemminflect's first form is sometimes the less shared one.
FORM_OVERRIDES = {("get", "VBN"): "got", ("quit", "VBN"): "quit"}

TAGS = {
    "n": ("NNS",),
    "v": ("VBZ", "VBD", "VBN", "VBG"),
    "a": ("JJR", "JJS"),
    "r": ("RBR", "RBS"),
}


# --- download -------------------------------------------------------------------


def fetch(spec: dict[str, str]) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / spec["file"]
    if not path.exists() or _sha256(path) != spec["sha256"]:
        print(f"downloading {spec['url']}", file=sys.stderr)
        tmp = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(spec["url"], timeout=120) as r, tmp.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.replace(path)
    digest = _sha256(path)
    if digest != spec["sha256"]:
        raise SystemExit(f"{path.name}: SHA-256 {digest} != pinned {spec['sha256']}")
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# --- WordNet --------------------------------------------------------------------


@dataclass
class Sense:
    id: str
    synset: str
    key: str  # PWN-style sense key, e.g. benefit%1:21:00::
    count: int = 0
    bad: bool = False


@dataclass
class Synset:
    id: str
    pos: str  # n v a r (satellites folded into a)
    satellite: bool
    definition: str = ""
    members: list[str] = field(default_factory=list)  # lemmas, in OEWN order
    bad: bool = False
    similar: list[str] = field(default_factory=list)
    hypernyms: list[str] = field(default_factory=list)
    also: list[str] = field(default_factory=list)


@dataclass
class WordNet:
    # (lemma, pos) -> senses in OEWN order; lowercase single entries only
    entries: dict[tuple[str, str], list[Sense]]
    synsets: dict[str, Synset]
    proper: set[str]  # lemmas that also appear capitalised (names, places)


def load_wordnet(xml_gz: Path, counts: dict[str, int]) -> WordNet:
    entries: dict[tuple[str, str], list[Sense]] = defaultdict(list)
    synsets: dict[str, Synset] = {}
    sense_usage: dict[str, list[str]] = defaultdict(list)  # sense id -> exemplifies targets
    synset_usage: dict[str, list[str]] = defaultdict(list)
    sense_owner: dict[str, str] = {}  # sense id -> lemma (all entries, for usage lookup)
    proper: set[str] = set()

    with gzip.open(xml_gz, "rb") as f:
        for _ev, el in ET.iterparse(f, events=("end",)):
            if el.tag == "LexicalEntry":
                lemma_el = el.find("Lemma")
                form = lemma_el.get("writtenForm")
                pos = lemma_el.get("partOfSpeech")
                pos = "a" if pos == "s" else pos
                for s in el.findall("Sense"):
                    sense_owner[s.get("id")] = form.lower()
                    for rel in s.findall("SenseRelation"):
                        if rel.get("relType") == "exemplifies":
                            sense_usage[s.get("id")].append(rel.get("target"))
                if form != form.lower():
                    proper.add(form.lower())
                elif pos in ("n", "v", "a", "r"):
                    for s in el.findall("Sense"):
                        sid = s.get("id")
                        tail = sid.split("__", 1)[1]
                        key = form.replace(" ", "_") + "%" + tail.replace(".", ":")
                        entries[(form, pos)].append(
                            Sense(sid, s.get("synset"), key, counts.get(key, 0))
                        )
                el.clear()
            elif el.tag == "Synset":
                pos = el.get("partOfSpeech")
                ss = Synset(
                    el.get("id"),
                    "a" if pos == "s" else pos,
                    pos == "s",
                    el.findtext("Definition") or "",
                )
                for rel in el.findall("SynsetRelation"):
                    t = rel.get("relType")
                    if t == "similar":
                        ss.similar.append(rel.get("target"))
                    elif t == "hypernym":
                        ss.hypernyms.append(rel.get("target"))
                    elif t == "also":
                        ss.also.append(rel.get("target"))
                    elif t == "exemplifies":
                        synset_usage[ss.id].append(rel.get("target"))
                synsets[ss.id] = ss
                el.clear()

    # Synset members, in each entry's sense order (OEWN's `members` attribute
    # is entry ids; rebuilding from the senses avoids parsing those).
    for (lemma, _pos), senses in entries.items():
        for s in senses:
            synsets[s.synset].members.append(lemma)

    # Resolve the usage-domain labels.
    bad_synsets = {
        sid
        for sid, ss in synsets.items()
        if ss.pos == "n" and any(m in BAD_USAGE for m in ss.members)
    }
    bad_target_senses = {sid for sid, owner in sense_owner.items() if owner in BAD_USAGE}

    def is_bad(targets: list[str]) -> bool:
        return any(t in bad_synsets or t in bad_target_senses for t in targets)

    for sid, targets in synset_usage.items():
        if is_bad(targets):
            synsets[sid].bad = True
    for senses in entries.values():
        for s in senses:
            if is_bad(sense_usage.get(s.id, [])):
                s.bad = True
    return WordNet(dict(entries), synsets, proper)


def load_counts(tar_gz: Path) -> dict[str, int]:
    """PWN 3.0 `index.sense`: `sense_key synset_offset sense_number tag_cnt`."""
    out: dict[str, int] = {}
    with tarfile.open(tar_gz, "r:gz") as tf:
        member = tf.getmember("dict/index.sense")
        data = tf.extractfile(member).read().decode("utf-8")
    for line in io.StringIO(data):
        parts = line.split()
        if len(parts) == 4:
            out[parts[0]] = int(parts[3])
    return out


# --- selection ------------------------------------------------------------------


def dominant(senses: list[Sense]) -> Sense | None:
    """The sense a reader most likely means: the most-tagged one.

    Only that sense is used. Review of earlier builds found synonyms of a
    word's *second* sense acceptable about half the time, even when that
    sense had nearly as many tags (`clip` -> `time`, `strain` -> `tune`).
    It must also hold `TARGET_MIN_SHARE` of the word's tags. With no tag
    counts at all, sense 1 is trusted only for a word with few senses.
    """
    usable = [s for s in senses if not s.bad]
    if not usable:
        return None
    total = sum(s.count for s in senses)
    if total == 0:
        return usable[0] if len(senses) <= UNTAGGED_MAX_SENSES else None
    if total < TARGET_MIN_TAGS and len(senses) > UNTAGGED_MAX_SENSES:
        return None  # `mint`: six senses, one tag between them
    top = max(usable, key=lambda s: s.count)  # max() keeps the first of ties
    return top if top.count / total >= TARGET_MIN_SHARE else None


def candidate_share(senses: list[Sense], synset: str) -> tuple[int, float] | None:
    """(tag count, share of the word's tags) of its sense in `synset`, or None
    when that sense is unlabelled-bad or has no SemCor evidence at all.
    Untagged candidate senses were wrong about half the time in review
    (`jargon` -> `slang`, `knack` -> `hang`), and so were untagged
    single-sense ones (`denim` -> `jeans`, `virtuoso` -> `superstar`)."""
    total = sum(s.count for s in senses)
    for s in senses:
        if s.synset == synset:
            if s.bad:
                return None
            if not s.count:
                return None
            return s.count, s.count / total
    return None


def main_sense_of(senses: list[Sense], synset: str, *, similar: bool = False) -> bool:
    """Is `synset` one of this word's own main senses?

    A quarter of its tags, or an eighth when that is still five or more
    uses (`learner` -> `student`, `allege` -> `say`). An adjective head
    reached through `similar` needs the full quarter.
    """
    got = candidate_share(senses, synset)
    if got is None:
        return False
    count, share = got
    if count < CAND_MIN_COUNT:
        return False
    if share >= CAND_MIN_SHARE:
        return True
    return not similar and share >= CAND_MIN_SHARE_FREQ and count >= CAND_MIN_COUNT_FREQ


@dataclass
class Lists:
    cefr: dict[tuple[str, str], int]  # (lemma, wn pos) -> level index
    band: dict[str, int]
    gb_us: dict[str, str]
    us_gb: dict[str, str]


def load_lists() -> Lists:
    cefr_raw = json.loads((DATA / "cefr.json").read_text("utf-8"))
    cefr: dict[tuple[str, str], int] = {}
    for item in cefr_raw["lemmas"]:
        for p, lvl in (item.get("by_pos") or {}).items():
            if p in CEFR_POS:
                cefr[(item["lemma"], CEFR_POS[p])] = LEVELS.index(lvl)
    bnc = json.loads((DATA / "bnc_coca.json").read_text("utf-8"))
    band: dict[str, int] = {}
    for b, fams in sorted(bnc["bands"].items(), key=lambda kv: int(kv[0])):
        for head, members in fams.items():
            for form in (head, *members):
                band.setdefault(form, int(b))
    sp = json.loads((DATA / "spelling.json").read_text("utf-8"))
    return Lists(cefr, band, dict(sp["gb_to_us"]), dict(sp["us_to_gb"]))


_WORD = re.compile(r"^[a-z]+$")


_COMPASS = re.compile(r"^(north|south|east|west)")


def _related(wn: WordNet, a: str, b: str) -> bool:
    """Two synsets one step apart: hypernym either way, `similar`/`also`, or
    satellites of the same adjective head."""
    sa, sb = wn.synsets[a], wn.synsets[b]
    if b in sa.hypernyms or a in sb.hypernyms:
        return True
    if b in sa.similar or a in sb.similar or b in sa.also or a in sb.also:
        return True
    return bool(sa.satellite and sb.satellite and set(sa.similar) & set(sb.similar))


def top_synset(senses: list[Sense]) -> str | None:
    tagged = [s for s in senses if s.count]
    return max(tagged, key=lambda s: s.count).synset if tagged else None


def candidates(word: str, pos: str, wn: WordNet, lists: Lists) -> list[dict]:
    if (word, pos) in BLOCK_TARGETS:
        return []
    level = lists.cefr[(word, pos)]
    senses = wn.entries.get((word, pos), [])
    sense = dominant(senses)
    variants = {word, lists.gb_us.get(word, word), lists.us_gb.get(word, word)}
    found: dict[str, dict] = {}

    def consider(cand: str, synset: str, tier: int, via: str, *, require=None) -> None:
        if cand in variants or cand in found:
            return
        if not _WORD.match(cand) or cand in OFFENSIVE or cand in wn.proper:
            return
        clevel = lists.cefr.get((cand, pos))
        if clevel is None or clevel >= level:
            return
        if (word, pos, cand) in BLOCK_PAIRS or cand in BLOCK_CANDIDATES.get(pos, ()):
            return
        csenses = wn.entries.get((cand, pos), [])
        ok = main_sense_of(csenses, synset, similar=tier > 0)
        if not ok and EXT_LOWSHARE and via == "syn" and pos == "a":
            got = candidate_share(csenses, synset)
            top = top_synset(csenses)
            if got and got[0] >= LOWSHARE_MIN_COUNT and top and _related(wn, synset, top):
                ok, via = True, "lowshare"
        if not ok or (require is not None and not require(csenses)):
            return
        got = candidate_share(csenses, synset)
        found[cand] = {
            "word": cand,
            "level": clevel,
            "band": lists.band.get(cand, 99),
            "tier": tier,
            "via": via,
            "synset": synset,
            "gloss": wn.synsets[synset].definition,
            "t_count": sense.count if sense else 0,
            "c_count": got[0] if got else 0,
            "c_share": got[1] if got else 0.0,
        }

    if sense is not None and not wn.synsets[sense.synset].bad:
        ss = wn.synsets[sense.synset]
        for m in ss.members:
            consider(m, ss.id, 0, "syn")
        # `northwest` is similar to `north`, which is not a substitute for it.
        if (
            pos == "a"
            and ss.satellite
            and sense.count >= SIMILAR_MIN_TARGET_COUNT
            and not _COMPASS.match(word)
        ):
            for head_id in ss.similar:
                head = wn.synsets[head_id]
                if head.satellite or head.bad:
                    continue
                for m in head.members:
                    consider(m, head.id, 1, "similar")
    elif EXT_SHARED2 and senses:
        # No dominant sense: a word in both of the two top senses fits either.
        tagged = sorted((s for s in senses if s.count and not s.bad), key=lambda s: -s.count)
        total = sum(s.count for s in senses)
        if len(tagged) >= 2 and (tagged[0].count + tagged[1].count) / total >= SHARED2_MIN_SHARE:
            a, b = (wn.synsets[t.synset] for t in tagged[:2])
            if not (a.bad or b.bad):
                both = [m for m in a.members if m in b.members]
                for m in both:
                    consider(m, a.id, 0, "shared2")

    for cand in ALLOW_PAIRS.get((word, pos), []):
        _allow(word, pos, cand, wn, lists, found, level)

    ranked = sorted(found.values(), key=lambda c: (c["tier"], c["level"], c["band"], c["word"]))
    return ranked[:MAX_ALTS]


def _allow(word, pos, cand, wn, lists, found, level) -> None:
    top = sorted(wn.entries.get((word, pos), []), key=lambda s: -s.count)[:ALLOW_TOP_SENSES]
    shared = next((s for s in top if cand in wn.synsets[s.synset].members), None)
    if shared is None and pos == "a":
        # an adjective head the satellite sense is `similar` to
        shared = next(
            (s for s in top for h in wn.synsets[s.synset].similar if cand in wn.synsets[h].members),
            None,
        )
    clevel = lists.cefr.get((cand, pos))
    if shared is None or clevel is None or clevel >= level:
        raise SystemExit(f"ALLOW_PAIRS {word}|{pos} -> {cand}: not attested in OEWN or not simpler")
    if cand in found:
        return
    found[cand] = {
        "word": cand,
        "level": clevel,
        "band": lists.band.get(cand, 99),
        "tier": 0,
        "via": "allow",
        "synset": shared.synset,
        "gloss": wn.synsets[shared.synset].definition,
        "t_count": shared.count,
        "c_count": 0,
        "c_share": 0.0,
    }


# --- inflection table -------------------------------------------------------------


def inflection_exceptions(words_by_pos: dict[str, set[str]], lists: Lists) -> dict[str, dict]:
    """Forms of each suggested word that the runtime rules would get wrong.

    Value per tag: a string, or [us, gb] when the two spellings differ
    (`traveled`/`travelled`).
    """
    from lemminflect import getInflection

    out: dict[str, dict] = defaultdict(dict)
    for pos, words in words_by_pos.items():
        for w in sorted(words):
            for tag in TAGS[pos]:
                forms = getInflection(w, tag, inflect_oov=False)
                if (w, tag) in FORM_OVERRIDES:
                    forms = (FORM_OVERRIDES[(w, tag)],)
                if tag in ("JJR", "JJS", "RBR", "RBS") and not forms:
                    forms = ()  # periphrastic: the runtime writes "more X"
                if tag == "NNS" and not forms:
                    continue
                want = _choose(forms, lists)
                got = regular_form(w, tag)
                # lemminflect appends -er/-est to a final e (`trueer`, `vagueer`).
                if isinstance(want, str) and w.endswith("e") and want in (w + "er", w + "est"):
                    want = got
                if want != got:
                    out[w][tag] = want
    return dict(out)


def _choose(forms: tuple[str, ...], lists: Lists):
    if not forms:
        return None  # comparative/superlative: use more/most
    first = forms[0]
    if len(forms) > 1:
        gb = lists.us_gb.get(first)
        if gb and gb in forms:
            return [first, gb]
        for f in forms[1:]:
            if lists.gb_us.get(f) == first:
                return [first, f]
    return first


# --- main ----------------------------------------------------------------------


def build(wn: WordNet, lists: Lists) -> tuple[dict, dict[tuple[str, str], list[dict]]]:
    detail: dict[tuple[str, str], list[dict]] = {}
    for (word, pos), lvl in sorted(lists.cefr.items()):
        if lvl == 0 or not _WORD.match(word):
            continue
        alts = candidates(word, pos, wn, lists)
        if alts:
            detail[(word, pos)] = alts

    used: dict[str, set[str]] = defaultdict(set)
    gb: dict[str, str] = {}
    for (_w, pos), alts in detail.items():
        for c in alts:
            used[pos].add(c["word"])
            if c["word"] in lists.us_gb:
                gb[c["word"]] = lists.us_gb[c["word"]]

    entries: dict[str, list] = {}
    for (word, pos), alts in detail.items():
        entries[f"{word}|{pos}"] = [
            lists.cefr[(word, pos)],
            [[c["word"], c["level"], c["band"]] for c in alts],
        ]

    out = {
        "source": (
            "Open English WordNet 2025 (McCrae et al., globalwordnet/english-wordnet), "
            "filtered against the CEFR-J 1.5 + Octanove C1/C2 1.0 levels and Nation's "
            "BNC/COCA bands bundled with lexinspect. Sense dominance from Princeton "
            "WordNet 3.0 SemCor tag counts."
        ),
        "version": (
            f"OEWN 2025 ({OEWN['file']}, SHA-256 {OEWN['sha256'][:8]}…); "
            f"WordNet 3.0 ({PWN30['file']}, SHA-256 {PWN30['sha256'][:8]}…)"
        ),
        "license": (
            "CC-BY-SA-4.0: adapts Open English WordNet (CC BY 4.0) and carries CEFR levels "
            "and BNC/COCA bands from cefr.json and bnc_coca.json (CC BY-SA 4.0). "
            "WordNet 3.0 notice in SOURCES.md."
        ),
        "attribution": (
            "Synonyms from Open English WordNet 2025 (McCrae, J. P., Rademaker, A., Bond, F., "
            "Rudnicka, E., & Fellbaum, C. (2019). English WordNet 2019 – An open-source WordNet "
            "for English. GWC 2019), https://github.com/globalwordnet/english-wordnet, CC BY 4.0; "
            "derived from Princeton WordNet. Sense frequencies: WordNet 3.0 Copyright 2006 by "
            "Princeton University. All rights reserved. Levels: CEFR-J 1.5 (Tono, TUFS) and "
            "Octanove Labs C1/C2 1.0. Bands: Nation (2017), BNC/COCA word family lists."
        ),
        "level_order": LEVELS,
        "pos": {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"},
        "format": (
            "entries: 'lemma|pos' -> [level_index, [[word, level_index, bnc_band], ...]], "
            "best first; band 99 = not in BNC/COCA bands. forms: lemma -> {penn_tag: form | "
            "[us, gb] | null (use more/most)}, only where the runtime's suffix rules differ. "
            "gb: US-spelled suggestion -> British spelling."
        ),
        "entry_count": len(entries),
        "entries": entries,
        "forms": inflection_exceptions(used, lists),
        "gb": dict(sorted(gb.items())),
    }
    return out, detail


def _show(word: str, pos: str, wn: WordNet, lists: Lists, alts: list[dict] | None) -> None:
    lvl = LEVELS[lists.cefr[(word, pos)]]
    print(f"\n{word} ({pos}, {lvl})")
    for s in wn.entries.get((word, pos), [])[:4]:
        ss = wn.synsets[s.synset]
        flag = " BAD" if s.bad or ss.bad else ""
        print(
            f"   [{s.count:>3}] {s.key:<28} {', '.join(ss.members[:6])}: {ss.definition[:70]}{flag}"
        )
    for c in alts or []:
        print(
            f"   -> {c['word']:<14} {LEVELS[c['level']]} band {c['band']:<3} tier {c['tier']}  {c['gloss'][:60]}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="comma-separated lemmas to print in detail (no write)")
    ap.add_argument("--sample", type=int, help="print N random entries (no write)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    counts = load_counts(fetch(PWN30))
    wn = load_wordnet(fetch(OEWN), counts)
    lists = load_lists()
    out, detail = build(wn, lists)

    if args.show:
        for w in args.show.split(","):
            for pos in "nvar":
                if (w, pos) in lists.cefr and lists.cefr[(w, pos)] > 0:
                    _show(w, pos, wn, lists, detail.get((w, pos)))
        return
    if args.sample:
        keys = sorted(detail)
        random.Random(args.seed).shuffle(keys)
        for word, pos in keys[: args.sample]:
            alts = detail[(word, pos)]
            lvl = LEVELS[lists.cefr[(word, pos)]]
            shown = ", ".join(
                f"{c['word']}({LEVELS[c['level']]}{'~' if c['tier'] else ''})" for c in alts
            )
            print(f"{word}|{pos} {lvl}: {shown}    [{alts[0]['gloss'][:55]}]")
        return

    path = DATA / "alternatives.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", "utf-8")
    n_alts = sum(len(v[1]) for v in out["entries"].values())
    print(
        f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB): "
        f"{out['entry_count']} entries, {n_alts} suggestions, {len(out['forms'])} irregular lemmas"
    )


if __name__ == "__main__":
    main()
