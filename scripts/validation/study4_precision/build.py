"""Study 4: build the labelling set for metadiscourse and PHRASE precision.

One command reproduces steps 1-4 of the study protocol:

    uv run python -I scripts/validation/study4_precision/build.py

1. Collect openly licensed English texts in three registers (seeded):
   - academic: CC BY / CC0 research articles, full-text JATS XML from Europe PMC,
     balanced across sciences, social sciences and humanities by journal pools;
     abstract + body only (references, tables, figures, captions, formulas,
     footnotes and back-matter sections stripped);
   - general: English Wikipedia articles from the Level-3 Vital Articles list
     (CC BY-SA 4.0);
   - argumentative: essays from Category:Wikipedia essays (CC BY-SA 4.0).
     No openly licensed *student* essay corpus could be verified (PERSUADE 2.0
     and ELLIPSE are CC BY-NC-SA 4.0, PELIC is CC BY-NC-ND 4.0, args.me is CC BY
     as a collection but "individual rights to the content still apply"), so
     Wikipedia essays stand in for argumentative writing.
   Every text is capped at 50,000 UTF-8 bytes (lexinspect's API limit), cut at a
   paragraph boundary.
2. Run lexinspect's pipeline (metadiscourse and phrase modules) on each text and
   record every hit with its character span (population: hits.jsonl).
3. Draw a stratified, seeded sample (see `plan_stratum`): metadiscourse by
   assigned category (target 100 each), PHRASE by K-band x single/multi-sense
   (target 300 in total; "multi-sense" = the entry's form has more than one
   sense in the list, which includes every hit with `also_possible`). Within a
   stratum any marker whose proportional share would exceed 15% becomes its own
   sub-stratum capped at 15%; the remaining
   markers form one pooled sub-stratum sampled by simple random sampling. Every
   item carries its sub-stratum population N and sample n, so precision can be
   re-weighted to the population (weight = N/n).
4. Write the blind labeller file (items.jsonl), the key (key.jsonl), the
   population summary, the maintainer sample, per-labeller orders and batches
   (orders.json, batches/<role>/batch/batch_XX.jsonl; see batches.py) and a manifest
   recording the seed, the lexinspect version, the git commit and whether the
   source tree was dirty.

Development set vs evaluation sample
------------------------------------
The default build (seed 20261016, --out .cache/validation/study4) reproduces
the DEVELOPMENT set of 120 texts, used for pilot labelling, guideline
calibration and matcher fixes. Its files, including the original human-check
sample (15 per metadiscourse category, up to 5 per PHRASE stratum), are left
as they were.

The EVALUATION sample is built later, after the guidelines and matcher are
frozen, from fresh texts of the same sources:

    uv run python -I scripts/validation/study4_precision/build.py --set evaluation \\
        --seed NEW_SEED --out .cache/validation/study4_eval \\
        [--exclude-texts MORE.txt] [--raw-cache .cache/validation/study4/raw]

`--set evaluation` always excludes the canonical development source manifest
(DEV_TEXTS, .cache/validation/study4/texts.jsonl, or --dev-texts): it must
have the pinned SHA-256 (DEV_TEXTS_SHA256) and hold all 120 development texts
(120 distinct source ids, 40 per register), or the build stops. Every
identifier of every development text is excluded; `--exclude-texts` adds
optional further exclusions (text source ids, URLs, DOIs or titles, one per
line, or a texts.jsonl). It also requires a seed other than the development
seed and an output directory other than the development one. The manifest
records the development manifest's path, SHA-256 and text count, the extra
file's path and SHA-256, and the number of excluded identifiers. Matching texts are skipped while
drawing, and after collection the build stops if any identifier of any
collected text is in the exclusion set. Pointing `--raw-cache` at the
development cache reuses its pool listings (the same sampling frame) and only
downloads new texts; it adds files there but never rewrites any. An
evaluation build refuses to run from a source tree with uncommitted changes
under src/ unless --allow-dirty is given. No build overwrites an existing one
(development or frozen) without `--overwrite`.

The build also writes `frame.json`: N_h and the register counts of every
sub-stratum, from the full hit population (analyse.py's exact domain
populations).

For --set evaluation, the maintainer sample (the second phase, labelled by
the maintainer) is allocated across EVERY sub-stratum of each module: min(2, n_h)
items in each, the rest of the module total (default 300 metadiscourse, 300
PHRASE) proportional to N_h, capped at n_h (largest remainder), then a seeded
simple random sample within each sub-stratum. The PHRASE phase-one sample has
300 items, so its maintainer sample is the whole of phase one (m_h = n_h in
every sub-stratum; the two-phase weights N_h / m_h then equal the phase-one
weights). Each key row records `in_maintainer_sample` and the sub-stratum's
maintainer allocation `m_sub`, so analyse.py's two-phase estimator (weights
N_h / m_h) is exact.

Downloads are cached under <raw-cache> (default <out>/raw); once cached,
rebuilding is offline and deterministic. `--refresh` re-queries pools and texts
(results will then reflect the sources' current state).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batches  # noqa: E402
import frame as frame_mod  # noqa: E402

SEED = 20261016  # development set; set by --seed
DEV_SEED = 20261016
REPO = Path(__file__).resolve().parents[3]
DEV_OUT = REPO / ".cache" / "validation" / "study4"
OUT = DEV_OUT  # set by --out
RAW = OUT / "raw"  # set by --raw-cache
EXCLUDE: set[str] = set()  # set for evaluation builds
DEV_TEXTS = DEV_OUT / "texts.jsonl"
DEV_TEXTS_SHA256 = "5dba40ccbb99a853ef32e6f3def90f992810ff2320cf98f366e227d7112f1cc8"
DEV_TEXTS_N = 120
DEV_TEXTS_PER_REGISTER = 40
UA = "lexinspect-validation/0.3 (+https://github.com/quangnd159/lexinspect; study 4)"
MAX_BYTES = 50_000

MD_TARGET = 100  # per metadiscourse category
PHRASE_TARGET = 300  # PHRASE total, spread evenly over K-band x sense strata
CAP_FRAC = 0.15  # max share of one marker / PHRASE entry within a stratum
HUMAN_MD_PER_CAT = 15  # development set's original human-check sample
HUMAN_PHRASE_PER_STRATUM = 5
MAINTAINER_TOTALS = {
    "metadiscourse": 300,
    "phrase": 300,
}  # new builds (PHRASE: census of phase one)
MAINTAINER_MIN_PER_SUB = 2

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
WIKI = "https://en.wikipedia.org/w/api.php"

# Journal pools per discipline. Large journals are restricted to one year so a
# pool can be listed in full; small journals span 2018-2025.
BIG_YEARS = "PUB_YEAR:2022"
SMALL_YEARS = "PUB_YEAR:[2018 TO 2025]"
ACADEMIC_POOLS: dict[str, list[tuple[str, str]]] = {
    "sciences": [
        ("eLife", BIG_YEARS),
        ("PLoS biology", BIG_YEARS),
        ("PLoS computational biology", BIG_YEARS),
        ("Royal Society open science", BIG_YEARS),
    ],
    "social_sciences": [
        ("Frontiers in psychology", BIG_YEARS),
        ("Humanit Soc Sci Commun", SMALL_YEARS),
        ("Political behavior", SMALL_YEARS),
        ("Journal of business ethics", SMALL_YEARS),
        ("Social indicators research", SMALL_YEARS),
        ("Journal of happiness studies", SMALL_YEARS),
        ("Journal of youth and adolescence", SMALL_YEARS),
        ("Sociology", SMALL_YEARS),
    ],
    "humanities": [
        ("Synthese", SMALL_YEARS),
        ("Philosophical studies", SMALL_YEARS),
        ("Erkenntnis", SMALL_YEARS),
        ("Topoi", SMALL_YEARS),
        ("Medical history", SMALL_YEARS),
        ("Journal of the history of biology", SMALL_YEARS),
        ("History of the human sciences", SMALL_YEARS),
        ("Philosophy, ethics, and humanities in medicine", SMALL_YEARS),
    ],
}
ACADEMIC_TARGETS = {"sciences": 14, "social_sciences": 13, "humanities": 13}
ACADEMIC_MIN_WORDS = 1500
WIKI_TARGET = 40
WIKI_MIN_WORDS = 1000
ESSAY_TARGET = 40
ESSAY_MIN_WORDS = 500

MD_CATEGORIES = [
    "transitions",
    "frame_markers",
    "endophoric_markers",
    "evidentials",
    "code_glosses",
    "hedges",
    "boosters",
    "attitude_markers",
    "engagement_markers",
    "self_mentions",
]


def rng(label: str) -> random.Random:
    return random.Random(f"{SEED}-{label}")


def today() -> str:
    return dt.date.today().isoformat()


# --- HTTP with on-disk cache ---------------------------------------------------


def fetch(url: str, cache: Path, refresh: bool = False) -> bytes:
    if cache.exists() and not refresh:
        return cache.read_bytes()
    cache.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            cache.write_bytes(data)
            time.sleep(0.2)
            return data
        except Exception as e:  # noqa: BLE001 - retried, then re-raised
            last = e
            time.sleep(2**attempt)
    raise RuntimeError(f"fetch failed: {url}: {last}")


def fetch_json(url: str, cache: Path, refresh: bool = False) -> Any:
    return json.loads(fetch(url, cache, refresh))


def _key(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:16]


# --- shared text helpers -------------------------------------------------------


def cap_bytes(paragraphs: list[str]) -> tuple[str, bool]:
    out: list[str] = []
    size = 0
    for p in paragraphs:
        b = len(p.encode()) + 2
        if size + b > MAX_BYTES:
            return "\n\n".join(out), True
        out.append(p)
        size += b
    return "\n\n".join(out), False


def ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --- academic: Europe PMC JATS -------------------------------------------------

DROP_TAGS = {
    "table-wrap",
    "table-wrap-group",
    "table",
    "fig",
    "fig-group",
    "disp-formula",
    "disp-formula-group",
    "supplementary-material",
    "ref-list",
    "fn-group",
    "fn",
    "graphic",
    "media",
    "boxed-text",
    "caption",
    "label",
    "inline-graphic",
    "chem-struct-wrap",
    "code",
    "preformat",
    "alternatives",
    "tex-math",
}
INLINE_REPLACE = {"inline-formula": "[formula]"}
DROP_SECTION = re.compile(
    r"acknowledg|funding|author.?s?.? contribution|contributions|data (and code )?availability|"
    r"code availability|materials availability|competing interest|conflicts? of interest|"
    r"declaration|ethic|consent|supporting information|supplementa|abbreviation|"
    r"reporting summary|open access|publisher.?s note|additional information|"
    r"availability of data|key resources table|resource availability|appendix",
    re.I,
)


def _remove(parent: ET.Element, child: ET.Element, replacement: str = "") -> None:
    """Remove `child`, keeping its tail text (and an optional replacement)."""
    kids = list(parent)
    i = kids.index(child)
    keep = replacement + (child.tail or "")
    if keep:
        if i == 0:
            parent.text = (parent.text or "") + keep
        else:
            prev = kids[i - 1]
            prev.tail = (prev.tail or "") + keep
    parent.remove(child)


def _strip(el: ET.Element) -> None:
    for parent in list(el.iter()):
        for child in list(parent):
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag in DROP_TAGS:
                _remove(parent, child)
            elif tag in INLINE_REPLACE:
                _remove(parent, child, INLINE_REPLACE[tag])
            elif tag == "sec":
                title = child.find("title")
                ttl = "".join(title.itertext()) if title is not None else ""
                if (child.get("sec-type") or "").lower() in (
                    "supplementary-material",
                    "data-availability",
                    "ack",
                    "kwd-group",
                    "history",
                    "COI-statement".lower(),
                ) or (ttl and DROP_SECTION.search(ttl)):
                    _remove(parent, child)


def _top_paragraphs(el: ET.Element) -> list[str]:
    parents = {c: p for p in el.iter() for c in p}
    out = []
    for p in el.iter("p"):
        a = parents.get(p)
        nested = False
        while a is not None:
            if a.tag == "p":
                nested = True
                break
            a = parents.get(a)
        if nested:
            continue
        t = ws("".join(p.itertext()))
        if len(t.split()) >= 5:
            out.append(t)
    return out


def jats_licence(root: ET.Element) -> str | None:
    perm = root.find(".//article-meta/permissions")
    if perm is None:
        return None
    blob = " ".join(
        [v for e in perm.iter() for k, v in e.attrib.items() if k.endswith("href")]
        + ["".join(perm.itertext())]
    ).lower()
    m = re.search(r"creativecommons\.org/licenses/([a-z-]+)/(\d\.\d)", blob)
    if m:
        kind, ver = m.groups()
        if kind == "by":
            return f"CC BY {ver}"
        return None  # by-nc, by-nd, by-sa, ...: not accepted for this set
    if "creativecommons.org/publicdomain/zero" in blob:
        return "CC0 1.0"
    if "public domain" in blob and "not subject to copyright" in blob:
        return "Public domain (US government work)"
    return None


def jats_text(root: ET.Element) -> list[str]:
    paras: list[str] = []
    meta = root.find(".//article-meta")
    if meta is not None:
        for ab in meta.findall("abstract"):
            if ab.get("abstract-type"):
                continue  # graphical, teaser, eLife digest, ...
            _strip(ab)
            paras += _top_paragraphs(ab)
    body = root.find(".//body")
    if body is not None:
        _strip(body)
        paras += _top_paragraphs(body)
    return paras


def epmc_pool(journal: str, years: str, refresh: bool) -> list[dict[str, Any]]:
    q = (
        f'JOURNAL:"{journal}" AND IN_EPMC:y AND OPEN_ACCESS:y AND {years} '
        f'AND PUB_TYPE:"research-article"'
    )
    cache = RAW / "pools" / f"epmc_{_key(q)}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    rows: list[dict[str, Any]] = []
    cursor = "*"
    while True:
        url = f"{EPMC}/search?" + urllib.parse.urlencode(
            {
                "query": q,
                "format": "json",
                "pageSize": 1000,
                "cursorMark": cursor,
                "resultType": "lite",
            }
        )
        d = json.loads(fetch(url, RAW / "tmp" / f"{_key(url)}.json", refresh=True))
        for r in d["resultList"]["result"]:
            if r.get("pmcid"):
                rows.append(
                    {
                        k: r.get(k)
                        for k in (
                            "pmcid",
                            "doi",
                            "title",
                            "authorString",
                            "journalTitle",
                            "pubYear",
                        )
                    }
                )
        nxt = d.get("nextCursorMark")
        if not nxt or nxt == cursor or not d["resultList"]["result"]:
            break
        cursor = nxt
    rows = sorted({r["pmcid"]: r for r in rows}.values(), key=lambda r: r["pmcid"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({"query": q, "retrieved": today(), "rows": rows}, ensure_ascii=False)
    )
    return json.loads(cache.read_text())


def collect_academic(refresh: bool, log: dict[str, Any]) -> list[dict[str, Any]]:
    texts: list[dict[str, Any]] = []
    log["academic_pools"] = {}
    log["academic_rejected"] = []
    for discipline, journals in ACADEMIC_POOLS.items():
        pools = {}
        for journal, years in journals:
            pool = epmc_pool(journal, years, refresh)
            rows = list(pool["rows"])
            rng(f"pool-{journal}").shuffle(rows)
            pools[journal] = rows
            log["academic_pools"][journal] = {
                "discipline": discipline,
                "query": pool["query"],
                "retrieved": pool["retrieved"],
                "size": len(rows),
            }
        order = list(pools)
        rng(f"journals-{discipline}").shuffle(order)
        taken = 0
        cursors = dict.fromkeys(order, 0)
        while taken < ACADEMIC_TARGETS[discipline]:
            progressed = False
            for journal in order:
                if taken >= ACADEMIC_TARGETS[discipline]:
                    break
                rows = pools[journal]
                while cursors[journal] < len(rows):
                    row = rows[cursors[journal]]
                    cursors[journal] += 1
                    progressed = True
                    t = _academic_text(row, discipline, refresh, log)
                    if t is not None:
                        texts.append(t)
                        taken += 1
                        break
            if not progressed:
                break
    return texts


def _norm_ref(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().casefold()
    for pre in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(pre):
            s = s[len(pre) :]
    return s.rstrip("/")


def text_refs(t: dict[str, Any]) -> set[str]:
    """Every identifier of a collected text, normalised (for exclusion and overlap checks)."""
    refs = {t.get(k) for k in ("source_id", "url", "fulltext_url", "doi", "title")}
    if t.get("source") == "Europe PMC":
        refs |= {f"https://europepmc.org/article/PMC/{t['source_id']}"}
    if t.get("revid"):
        refs |= {f"https://en.wikipedia.org/w/index.php?oldid={t['revid']}"}
    return {_norm_ref(str(r)) for r in refs if r}


def read_exclusions(path: Path) -> set[str]:
    """Source ids / URLs / DOIs / titles, one per line, or a texts.jsonl."""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("{"):
            rec = json.loads(s)
            out |= text_refs(rec)
        else:
            out.add(_norm_ref(s))
    return out


def load_dev_exclusions(path: Path) -> tuple[set[str], dict[str, Any]]:
    """Every identifier of the canonical development texts, after checking identity and size."""
    if not path.exists():
        raise SystemExit(f"development source manifest {path} not found")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != DEV_TEXTS_SHA256:
        raise SystemExit(
            f"{path} is not the canonical development manifest (sha256 {digest}, "
            f"expected {DEV_TEXTS_SHA256})"
        )
    texts = [json.loads(x) for x in data.decode("utf-8").splitlines() if x.strip()]
    ids = {t.get("source_id") for t in texts}
    regs = Counter(t.get("register") for t in texts)
    if (
        len(texts) != DEV_TEXTS_N
        or len(ids) != DEV_TEXTS_N
        or None in ids
        or set(regs.values()) != {DEV_TEXTS_PER_REGISTER}
    ):
        raise SystemExit(f"{path}: expected {DEV_TEXTS_N} distinct development texts")
    refs: set[str] = set()
    for t in texts:
        r = text_refs(t)
        if not r:
            raise SystemExit(f"{path}: a development text has no identifier")
        refs |= r
    return refs, {"file": str(path), "sha256": digest, "n_texts": len(texts), "n_refs": len(refs)}


def exclusion_overlap(texts: list[dict[str, Any]], exclude: set[str]) -> list[str]:
    """Identifiers shared by collected texts and the exclusion set (must be empty)."""
    return sorted({r for t in texts for r in text_refs(t)} & exclude)


def excluded(*refs: Any) -> bool:
    return any(r and _norm_ref(str(r)) in EXCLUDE for r in refs)


def _academic_text(row, discipline, refresh, log) -> dict[str, Any] | None:
    pmcid = row["pmcid"]
    if excluded(
        pmcid,
        f"https://europepmc.org/article/PMC/{pmcid}",
        f"{EPMC}/{pmcid}/fullTextXML",
        row.get("doi"),
        row.get("title"),
    ):
        log.setdefault("excluded_texts", []).append(pmcid)
        return None
    url = f"{EPMC}/{pmcid}/fullTextXML"
    try:
        raw = fetch(url, RAW / "epmc" / f"{pmcid}.xml", refresh)
        root = ET.fromstring(raw)
    except Exception as e:  # noqa: BLE001
        log["academic_rejected"].append({"pmcid": pmcid, "reason": f"fetch/parse: {e}"})
        return None
    lic = jats_licence(root)
    if lic is None:
        log["academic_rejected"].append({"pmcid": pmcid, "reason": "licence not CC BY/CC0"})
        return None
    paras = jats_text(root)
    words = sum(len(p.split()) for p in paras)
    if words < ACADEMIC_MIN_WORDS:
        log["academic_rejected"].append({"pmcid": pmcid, "reason": f"too short ({words} words)"})
        return None
    text, truncated = cap_bytes(paras)
    retrieved = dt.date.fromtimestamp((RAW / "epmc" / f"{pmcid}.xml").stat().st_mtime)
    return {
        "register": "academic",
        "discipline": discipline,
        "source": "Europe PMC",
        "source_id": pmcid,
        "title": row.get("title"),
        "authors": row.get("authorString"),
        "journal": row.get("journalTitle"),
        "year": row.get("pubYear"),
        "doi": row.get("doi"),
        "url": f"https://europepmc.org/article/PMC/{pmcid}",
        "fulltext_url": url,
        "licence": lic,
        "retrieved": retrieved.isoformat(),
        "truncated": truncated,
        "text": text,
    }


# --- Wikipedia -----------------------------------------------------------------

WIKI_STOP = re.compile(
    r"^(see also|references|notes|footnotes|further reading|external links|bibliography|"
    r"sources|citations|works cited|notes and references|references and notes|"
    r"explanatory notes|general and cited sources|cited sources|primary sources|"
    r"secondary sources)$",
    re.I,
)


def _strip_displaystyle(s: str) -> str:
    out, i = [], 0
    while True:
        j = s.find("{\\displaystyle", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        depth, k = 0, j
        while k < len(s):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append("[formula]")
        i = k + 1
    return "".join(out)


def wiki_paragraphs(extract: str) -> list[str]:
    paras: list[str] = []
    for line in extract.split("\n"):
        line = line.strip()
        m = re.match(r"^(=+)\s*(.*?)\s*\1$", line)
        if m:
            if WIKI_STOP.match(m.group(2)):
                break
            continue
        line = ws(_strip_displaystyle(line))
        if len(line.split()) >= 3:
            paras.append(line)
    return paras


def wiki_list(params: dict[str, Any], key: str, cache: Path, refresh: bool) -> dict[str, Any]:
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    out: list[str] = []
    cont: dict[str, str] = {}
    while True:
        p = {"format": "json", "formatversion": 2, **params, **cont}
        url = f"{WIKI}?" + urllib.parse.urlencode(p)
        d = json.loads(fetch(url, RAW / "tmp" / f"{_key(url)}.json", refresh=True))
        out += key_extract(d, key)
        if "continue" not in d:
            break
        cont = d["continue"]
    res = {"params": params, "retrieved": today(), "titles": sorted(set(out))}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(res, ensure_ascii=False))
    return res


def key_extract(d: dict[str, Any], key: str) -> list[str]:
    if key == "links":
        return [lk["title"] for pg in d["query"]["pages"] for lk in pg.get("links", [])]
    return [m["title"] for m in d["query"]["categorymembers"]]


def wiki_page(title: str, refresh: bool) -> dict[str, Any] | None:
    params = {
        "action": "query",
        "prop": "extracts|revisions|categories|info",
        "explaintext": 1,
        "exsectionformat": "wiki",
        "rvprop": "ids|timestamp",
        "cllimit": "max",
        "inprop": "url",
        "redirects": 1,
        "titles": title,
        "format": "json",
        "formatversion": 2,
    }
    url = f"{WIKI}?" + urllib.parse.urlencode(params)
    d = fetch_json(url, RAW / "wiki" / f"{_key(title)}.json", refresh)
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    return pages[0]


def collect_wiki(kind: str, refresh: bool, log: dict[str, Any]) -> list[dict[str, Any]]:
    if kind == "general":
        lst = wiki_list(
            {
                "action": "query",
                "prop": "links",
                "titles": "Wikipedia:Vital articles/Level/3",
                "redirects": 1,
                "plnamespace": 0,
                "pllimit": "max",
            },
            "links",
            RAW / "pools" / "wiki_vital3.json",
            refresh,
        )
        target, min_words, register = WIKI_TARGET, WIKI_MIN_WORDS, "general"
        pool_page = "https://en.wikipedia.org/wiki/Wikipedia:Vital_articles/Level/3"
    else:
        lst = wiki_list(
            {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": "Category:Wikipedia essays",
                "cmnamespace": 4,
                "cmlimit": "max",
            },
            "members",
            RAW / "pools" / "wiki_essays.json",
            refresh,
        )
        target, min_words, register = ESSAY_TARGET, ESSAY_MIN_WORDS, "argumentative"
        pool_page = "https://en.wikipedia.org/wiki/Category:Wikipedia_essays"
    titles = [t for t in lst["titles"] if "/" not in t or kind == "general"]
    rng(f"wiki-{kind}").shuffle(titles)
    log[f"wiki_{kind}_pool"] = {
        "page": pool_page,
        "retrieved": lst["retrieved"],
        "size": len(titles),
    }
    rejected = log.setdefault(f"wiki_{kind}_rejected", [])
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for title in titles:
        if len(out) >= target:
            break
        if excluded(title):
            log.setdefault("excluded_texts", []).append(title)
            continue
        pg = wiki_page(title, refresh)
        rev_url = (
            f"https://en.wikipedia.org/w/index.php?oldid={pg['revisions'][0]['revid']}"
            if pg is not None and pg.get("revisions")
            else None
        )
        if pg is not None and excluded(f"pageid:{pg['pageid']}", pg["title"], rev_url):
            log.setdefault("excluded_texts", []).append(f"pageid:{pg['pageid']}")
            continue
        if pg is None or pg["pageid"] in seen:
            rejected.append({"title": title, "reason": "missing or duplicate"})
            continue
        cats = [c["title"] for c in pg.get("categories", [])]
        if kind == "essays" and any("humor" in c.lower() for c in cats):
            rejected.append({"title": title, "reason": "humour essay"})
            continue
        paras = wiki_paragraphs(pg.get("extract", ""))
        words = sum(len(p.split()) for p in paras)
        if words < min_words:
            rejected.append({"title": title, "reason": f"too short ({words} words)"})
            continue
        seen.add(pg["pageid"])
        text, truncated = cap_bytes(paras)
        rev = pg["revisions"][0]
        out.append(
            {
                "register": register,
                "discipline": None,
                "source": "English Wikipedia",
                "source_id": f"pageid:{pg['pageid']}",
                "title": pg["title"],
                "authors": "Wikipedia contributors",
                "journal": None,
                "year": rev["timestamp"][:4],
                "doi": None,
                "url": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
                "revid": rev["revid"],
                "rev_timestamp": rev["timestamp"],
                "licence": "CC BY-SA 4.0",
                "retrieved": dt.date.fromtimestamp(
                    (RAW / "wiki" / f"{_key(title)}.json").stat().st_mtime
                ).isoformat(),
                "truncated": truncated,
                "text": text,
            }
        )
    return out


# --- lexinspect ----------------------------------------------------------------


def run_lexinspect(texts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict]:
    from lexinspect import pipeline

    analyses = {}
    hits: list[dict[str, Any]] = []
    for t in texts:
        a, res = pipeline.run_all(t["text"], modules=["metadiscourse", "phrase"])
        t["text"] = a.text  # normalised text: the one spans index into
        sents = list(a.doc.sents)
        starts = [s.start for s in sents]
        analyses[t["text_id"]] = (a, sents, starts)
        for h in res["metadiscourse"]["hits"]:
            hits.append({"module": "metadiscourse", "text_id": t["text_id"], **h})
        for h in res["phrase"]["hits"]:
            hits.append({"module": "phrase", "text_id": t["text_id"], **h})
    return hits, analyses


def _sent_index(starts: list[int], tok_i: int) -> int:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= tok_i:
            lo = mid
        else:
            hi = mid - 1
    return lo


MAX_CONTEXT = 1200


def context_for(hit: dict[str, Any], analysis) -> tuple[str, list[int]]:
    a, sents, starts = analysis
    k = _sent_index(starts, hit["token_index"])
    sent = sents[k]
    prev = sents[k - 1] if k > 0 else None
    s, e = hit["span"]
    begin = prev.start_char if prev is not None else sent.start_char
    end = sent.end_char
    text = a.text
    before, mid, after = text[begin:s], text[s:e], text[e:end]
    before, after = ws(before), ws(after)
    lead = " " if before and text[s - 1 : s].isspace() else ""
    trail = " " if after and text[e : e + 1].isspace() else ""
    # Keep the whole current sentence where possible; trim the previous one first.
    if len(before) + len(mid) + len(after) > MAX_CONTEXT:
        room = MAX_CONTEXT - len(mid)
        keep_after = min(len(after), max(room // 2, room - len(before)))
        keep_before = room - keep_after
        if len(after) > keep_after:
            after = after[:keep_after].rsplit(" ", 1)[0] + " …"
        if len(before) > keep_before:
            before = "… " + before[-keep_before:].split(" ", 1)[-1]
    ctx = f"{before}{lead}⟦{ws(mid)}⟧{trail}{after}".strip()
    return ctx, [sent.start_char, sent.end_char]


# --- sampling ------------------------------------------------------------------


def plan_stratum(
    by_marker: dict[str, list[Any]], n_target: int, cap_frac: float
) -> list[tuple[str, list[Any], int]]:
    """Sub-strata for one stratum: [(name, population, n_to_draw)].

    Markers whose proportional share would exceed the cap become their own
    sub-stratum with n = cap; all other markers are pooled ("rest") and drawn
    by simple random sampling. The cap is at least n/len(markers) so a stratum
    with few distinct markers can still reach its target.
    """
    total = sum(len(v) for v in by_marker.values())
    n = min(n_target, total)
    if n == 0:
        return []
    cap = max(math.ceil(cap_frac * n), math.ceil(n / len(by_marker)))
    own: dict[str, int] = {}
    while True:
        rest = {m: v for m, v in by_marker.items() if m not in own}
        n_rest = n - sum(own.values())
        n_pop_rest = sum(len(v) for v in rest.values())
        over = [m for m, v in rest.items() if n_pop_rest and n_rest * len(v) / n_pop_rest > cap]
        if not over:
            break
        for m in over:
            own[m] = min(cap, len(by_marker[m]))
    rest_pop = [h for m in sorted(rest) for h in by_marker[m]]
    n_rest = min(n - sum(own.values()), len(rest_pop))
    # If the pooled markers can't absorb their share (few distinct markers),
    # lift the capped ones, largest first, rather than fall short of n.
    short = n - sum(own.values()) - n_rest
    for m in sorted(own, key=lambda m: (-len(by_marker[m]), m)):
        add = min(short, len(by_marker[m]) - own[m])
        own[m] += add
        short -= add
    plan = [(f"marker={m}", by_marker[m], own[m]) for m in sorted(own)]
    if rest_pop:
        plan.append(("rest", rest_pop, n_rest))
    return plan


def water_fill(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Spread `total` as evenly as possible over strata, never above a stratum's size."""
    alloc = dict.fromkeys(sizes, 0)
    left = min(total, sum(sizes.values()))
    while left > 0:
        open_ = [k for k in sorted(sizes) if alloc[k] < sizes[k]]
        share = max(1, left // len(open_))
        for k in open_:
            add = min(share, sizes[k] - alloc[k], left)
            alloc[k] += add
            left -= add
            if left == 0:
                break
    return alloc


def draw(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sampled: list[dict[str, Any]] = []
    design: dict[str, Any] = {"metadiscourse": {}, "phrase": {}}

    md = [h for h in hits if h["module"] == "metadiscourse"]
    for cat in MD_CATEGORIES:
        pop = [h for h in md if h["category"] == cat]
        by_m: dict[str, list] = defaultdict(list)
        for h in pop:
            by_m[h["marker"]].append(h)
        plan = plan_stratum(by_m, MD_TARGET, CAP_FRAC)
        design["metadiscourse"][cat] = _execute(plan, cat, f"md-{cat}", sampled)
        design["metadiscourse"][cat]["N"] = len(pop)

    ph = [h for h in hits if h["module"] == "phrase"]
    poly = polysemous_ranks()
    strata: dict[str, list] = defaultdict(list)
    for h in ph:
        h["has_also_possible"] = bool(h.get("also_possible"))
        h["multi_sense"] = h["has_also_possible"] or h["rank"] in poly
        strata[_phrase_stratum(h)].append(h)
    alloc = water_fill({k: len(v) for k, v in strata.items()}, PHRASE_TARGET)
    for name in sorted(strata):
        by_m = defaultdict(list)
        for h in strata[name]:
            by_m[h["phrase"]].append(h)
        plan = plan_stratum(by_m, alloc[name], CAP_FRAC)
        design["phrase"][name] = _execute(plan, name, f"ph-{name}", sampled)
        design["phrase"][name]["N"] = len(strata[name])
    return sampled, design


def polysemous_ranks() -> set[int]:
    """PHRASE entries whose surface form is shared with another entry (another sense).

    Hit-level `also_possible` is rare (only where tags can't separate the senses,
    e.g. OUT OF), so "multi-sense" is defined at list level: the form has more
    than one sense in the list, whether or not lexinspect could pick between
    them by tag. `has_also_possible` is kept per item in the key.
    """
    from lexinspect import phrase

    by_var: dict[tuple, set[int]] = defaultdict(set)
    for it in phrase._load()["items"]:
        for v in it["variants"]:
            by_var[tuple(v)].add(it["rank"])
    return {r for ranks in by_var.values() if len(ranks) > 1 for r in ranks}


def _phrase_stratum(h: dict[str, Any]) -> str:
    return f"K{h['k_band']}-{'multi' if h['multi_sense'] else 'single'}"


def _execute(plan, stratum: str, seed_label: str, sampled: list) -> dict[str, Any]:
    out = {"n": 0, "substrata": {}}
    for sub, pop, n in plan:
        pop = sorted(pop, key=lambda h: (h["text_id"], h["span"][0], h["span"][1]))
        picks = rng(f"{seed_label}-{sub}").sample(pop, n)
        for h in picks:
            h["stratum"] = stratum
            h["substratum"] = f"{stratum}|{sub}"
            h["N_sub"] = len(pop)
            h["n_sub"] = n
            h["weight"] = len(pop) / n
            sampled.append(h)
        out["substrata"][sub] = {"N": len(pop), "n": n}
        out["n"] += n
    return out


# --- output --------------------------------------------------------------------


def phrase_lookup() -> tuple[dict[int, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    from lexinspect import phrase

    items = phrase._load()["items"]
    by_rank = {it["rank"]: it for it in items}
    by_var: dict[tuple, list[int]] = defaultdict(list)
    for it in items:
        for v in it["variants"]:
            by_var[tuple(v)].append(it["rank"])
    siblings: dict[int, list[dict[str, Any]]] = {}
    for it in items:
        ranks = {r for v in it["variants"] for r in by_var[tuple(v)]} - {it["rank"]}
        siblings[it["rank"]] = [
            {
                "expression": by_rank[r]["phrase"],
                "sense": by_rank[r].get("sense"),
                "example": by_rank[r]["example"],
            }
            for r in sorted(ranks)
        ]
    return by_rank, siblings


def claimed_for(h: dict[str, Any], by_rank, siblings) -> dict[str, Any]:
    if h["module"] == "metadiscourse":
        return {"category": h["category"], "dimension": h["dimension"]}
    it = by_rank[h["rank"]]
    return {
        "expression": it["phrase"],
        "sense": it.get("sense"),
        "example": it["example"],
        "other_senses_in_list": siblings[h["rank"]],
    }


def human_sample(items_key: list[dict[str, Any]]) -> list[str]:
    by: dict[str, list[str]] = defaultdict(list)
    for k in items_key:
        by[(k["module"], k["stratum"])].append(k["id"])
    out: list[str] = []
    for (module, stratum), ids in sorted(by.items()):
        n = HUMAN_MD_PER_CAT if module == "metadiscourse" else HUMAN_PHRASE_PER_STRATUM
        out += rng(f"human-{module}-{stratum}").sample(sorted(ids), min(n, len(ids)))
    rng("human-order").shuffle(out)
    return out


def allocate_maintainer(
    subs: dict[str, tuple[int, int]], total: int, minimum: int = MAINTAINER_MIN_PER_SUB
) -> dict[str, int]:
    """Maintainer items per sub-stratum h, from {h: (N_h, n_h)}.

    min(minimum, n_h) in every sub-stratum, the rest of `total` proportional to
    N_h, never above n_h (iterative capping, then largest remainder; ties by name).
    """
    alloc = {h: min(minimum, n) for h, (_, n) in subs.items()}
    if sum(alloc.values()) > total:
        raise ValueError(
            f"total {total} is below the minimum allocation {sum(alloc.values())} "
            f"({len(subs)} sub-strata)"
        )
    left = min(total, sum(n for _, n in subs.values())) - sum(alloc.values())
    while left > 0:
        open_ = sorted(h for h, (_, n) in subs.items() if alloc[h] < n)
        tot_n = sum(subs[h][0] for h in open_)
        quota = {h: left * subs[h][0] / tot_n for h in open_}
        room = {h: subs[h][1] - alloc[h] for h in open_}
        full = [h for h in open_ if quota[h] >= room[h]]
        if full:
            for h in full:
                alloc[h] += room[h]
                left -= room[h]
            continue
        base = {h: int(quota[h]) for h in open_}
        for h in open_:
            alloc[h] += base[h]
        left -= sum(base.values())
        for h in sorted(open_, key=lambda h: (-(quota[h] - base[h]), h))[:left]:
            alloc[h] += 1
        left = 0
    return alloc


def maintainer_sample(
    key: list[dict[str, Any]], totals: dict[str, int]
) -> tuple[list[str], dict[str, dict[str, int]]]:
    """Second-phase sample: SRS of the allocated size within every sub-stratum."""
    by_sub: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for k in key:
        by_sub[(k["module"], k["substratum"])].append(k)
    chosen: list[str] = []
    allocs: dict[str, dict[str, int]] = {}
    for module in sorted({m for m, _ in by_sub}):
        subs = {h: (rows[0]["N_sub"], len(rows)) for (m, h), rows in by_sub.items() if m == module}
        alloc = allocate_maintainer(subs, totals[module])
        allocs[module] = dict(sorted(alloc.items()))
        for h in sorted(subs):
            ids = sorted(r["id"] for r in by_sub[(module, h)])
            chosen += rng(f"maintainer-{module}-{h}").sample(ids, alloc[h])
    return sorted(chosen), allocs


def git_info() -> dict[str, Any]:
    """HEAD commit of the checkout and whether lexinspect's source (src/) has changes."""
    import subprocess

    try:
        head = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain", "--", "src"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None, "dirty_paths": []}
    return {"commit": head, "dirty": bool(dirty), "dirty_paths": [d[3:] for d in dirty]}


def git_commit() -> str | None:
    """Commit of the checkout, with "-dirty" if lexinspect's source differs (manifest field)."""
    g = git_info()
    if g["commit"] is None:
        return None
    return g["commit"] + ("-dirty" if g["dirty"] else "")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    global SEED, OUT, RAW, EXCLUDE
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="re-download pools and texts")
    ap.add_argument("--seed", type=int, default=DEV_SEED)
    ap.add_argument("--out", type=Path, default=DEV_OUT)
    ap.add_argument("--raw-cache", type=Path, help="download cache (default <out>/raw)")
    ap.add_argument(
        "--exclude-texts", type=Path, help="extra exclusions: ids/URLs/titles or a texts.jsonl"
    )
    ap.add_argument("--dev-texts", type=Path, default=DEV_TEXTS, help="development texts.jsonl")
    ap.add_argument("--maintainer-md", type=int, default=MAINTAINER_TOTALS["metadiscourse"])
    ap.add_argument("--maintainer-phrase", type=int, default=MAINTAINER_TOTALS["phrase"])
    ap.add_argument("--batch-size", type=int, default=325, help="model labellers' batch size")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument(
        "--set",
        choices=("development", "evaluation"),
        default="development",
        help="development: the frozen dev design (seed 20261016, no exclusions); evaluation: "
        "fresh texts (development texts always excluded), a new --seed and a new --out",
    )
    ap.add_argument("--overwrite", action="store_true", help="allow replacing an existing build")
    args = ap.parse_args(argv)
    SEED, OUT = args.seed, args.out.resolve()
    RAW = (args.raw_cache or OUT / "raw").resolve()
    extra = read_exclusions(args.exclude_texts) if args.exclude_texts else set()
    dev = args.set == "development"
    dev_info: dict[str, Any] | None = None
    if dev and (SEED != DEV_SEED or extra):
        raise SystemExit("--set development means seed 20261016 and no exclusions")
    if not dev:
        if SEED == DEV_SEED:
            raise SystemExit("--set evaluation needs a new --seed")
        if DEV_OUT.resolve() == OUT:
            raise SystemExit("--set evaluation needs a new --out")
        dev_refs, dev_info = load_dev_exclusions(args.dev_texts)
        extra |= dev_refs
    EXCLUDE = extra
    existing = [
        f for f in ("items.jsonl", "key.jsonl", "manifest.json", "hits.jsonl") if (OUT / f).exists()
    ]
    if existing and not args.overwrite:
        raise SystemExit(
            f"{OUT} already holds a build ({', '.join(existing)}); --overwrite to replace"
        )
    git = git_info()
    if not dev and git["dirty"] and not args.allow_dirty:
        raise SystemExit(f"src/ has uncommitted changes: {git['dirty_paths']} (--allow-dirty)")
    OUT.mkdir(parents=True, exist_ok=True)
    log: dict[str, Any] = {}

    # 1. texts
    texts = (
        collect_academic(args.refresh, log)
        + collect_wiki("general", args.refresh, log)
        + collect_wiki("essays", args.refresh, log)
    )
    overlap = exclusion_overlap(texts, EXCLUDE)
    if overlap:
        raise SystemExit(f"collected texts overlap the exclusion set: {overlap[:5]}")
    for i, t in enumerate(texts):
        t["text_id"] = f"T{i + 1:03d}"
    print(f"texts: {Counter(t['register'] for t in texts)}", file=sys.stderr)

    # 2. lexinspect
    hits, analyses = run_lexinspect(texts)
    write_jsonl(
        OUT / "texts.jsonl",
        [{k: v for k, v in t.items() if k != "text"} | {"n_chars": len(t["text"])} for t in texts],
    )
    (OUT / "texts").mkdir(exist_ok=True)
    for t in texts:
        (OUT / "texts" / f"{t['text_id']}.txt").write_text(t["text"], encoding="utf-8")
    reg = {t["text_id"]: t for t in texts}
    write_jsonl(OUT / "hits.jsonl", hits)

    # 3. sample
    sampled, design = draw(hits)

    # 4. items and key
    by_rank, siblings = phrase_lookup()
    r = rng("ids")
    ids: set[str] = set()
    while len(ids) < len(sampled):
        ids.add(f"{r.getrandbits(40):010x}")
    id_list = sorted(ids)
    r.shuffle(id_list)
    order = list(range(len(sampled)))
    rng("item-order").shuffle(order)
    items, key = [], []
    from lexinspect._schema import provenance

    prov = provenance()
    for new_id, idx in zip(id_list, order, strict=True):
        h = sampled[idx]
        t = reg[h["text_id"]]
        ctx, sent_span = context_for(h, analyses[h["text_id"]])
        items.append(
            {
                "id": new_id,
                "module": h["module"],
                "context": ctx,
                "marker": h["surface"],
                "claimed": claimed_for(h, by_rank, siblings),
            }
        )
        rec = {
            "id": new_id,
            "module": h["module"],
            "text_id": h["text_id"],
            "register": t["register"],
            "discipline": t["discipline"],
            "source": t["source"],
            "source_id": t["source_id"],
            "title": t["title"],
            "url": t["url"],
            "licence": t["licence"],
            "span": h["span"],
            "sentence_span": sent_span,
            "token_index": h["token_index"],
            "surface": h["surface"],
            "stratum": h["stratum"],
            "substratum": h["substratum"],
            "N_sub": h["N_sub"],
            "n_sub": h["n_sub"],
            "weight": h["weight"],
            "provenance": prov,
        }
        if h["module"] == "metadiscourse":
            rec |= {
                "category": h["category"],
                "dimension": h["dimension"],
                "marker_key": h["marker"],
                "also_listed_as": h.get("also_listed_as", []),
            }
        else:
            rec |= {
                "rank": h["rank"],
                "expression": h["phrase"],
                "k_band": h["k_band"],
                "multi_sense": h["multi_sense"],
                "has_also_possible": h["has_also_possible"],
                "also_possible": h.get("also_possible", []),
            }
        key.append(rec)
    allocs: dict[str, dict[str, int]] | None = None
    if dev:
        hs = human_sample(key)  # the development set's original sample, unchanged
    else:
        totals = {"metadiscourse": args.maintainer_md, "phrase": args.maintainer_phrase}
        hs_sorted, allocs = maintainer_sample(key, totals)
        chosen = set(hs_sorted)
        for k in key:
            k["in_maintainer_sample"] = k["id"] in chosen
            k["m_sub"] = allocs[k["module"]][k["substratum"]]
        hs = batches.role_order(hs_sorted, SEED, "maintainer")
        write_jsonl(
            OUT / "maintainer_sample.jsonl",
            [
                {
                    "id": k["id"],
                    "module": k["module"],
                    "substratum": k["substratum"],
                    "N_sub": k["N_sub"],
                    "n_sub": k["n_sub"],
                    "m_sub": k["m_sub"],
                    "phase2_inclusion": k["m_sub"] / k["n_sub"],
                }
                for k in sorted(key, key=lambda k: k["id"])
                if k["in_maintainer_sample"]
            ],
        )
    items_sorted = sorted(zip(items, key, strict=True), key=lambda p: p[0]["id"])
    # Labeller file order is the shuffled order, not id order.
    write_jsonl(OUT / "items.jsonl", items)
    write_jsonl(OUT / "key.jsonl", [k for _, k in items_sorted])
    (OUT / "human_sample_ids.txt").write_text("\n".join(hs) + "\n")

    # Per-labeller orders and batches.
    orders = batches.make_orders([i["id"] for i in items], hs, SEED, args.batch_size)
    (OUT / "orders.json").write_text(json.dumps(orders, indent=1))
    items_by_id = {i["id"]: i for i in items}
    for role in ("A", "B", "maintainer"):
        batches.write_batches(items_by_id, orders, role, OUT, replace=args.overwrite)

    # Sampling frame: N_h and register counts per sub-stratum, from every hit.
    fr = frame_mod.build_frame(
        hits, {t["text_id"]: t["register"] for t in texts}, design, polysemous_ranks()
    )
    if not fr["checks"]["design_N_match"]:
        raise SystemExit("frame does not match the design: " + "; ".join(fr["checks"]["problems"]))
    fr["source"] = {
        "hits_sha256": hashlib.sha256((OUT / "hits.jsonl").read_bytes()).hexdigest(),
        "n_hits": len(hits),
    }
    (OUT / "frame.json").write_text(json.dumps(fr, indent=1, ensure_ascii=False))

    # population summary
    pop: dict[str, Any] = {"metadiscourse": {}, "phrase": {}}
    poly = polysemous_ranks()
    for h in hits:
        t = reg[h["text_id"]]
        if h["module"] == "metadiscourse":
            d = pop["metadiscourse"].setdefault(
                h["category"], {"N": 0, "by_register": Counter(), "by_marker": Counter()}
            )
            d["by_marker"][h["marker"]] += 1
        else:
            h.setdefault("multi_sense", bool(h.get("also_possible")) or h["rank"] in poly)
            d = pop["phrase"].setdefault(
                _phrase_stratum(h), {"N": 0, "by_register": Counter(), "by_marker": Counter()}
            )
            d["by_marker"][h["phrase"]] += 1
        d["N"] += 1
        d["by_register"][t["register"]] += 1
    for mod in pop.values():
        for d in mod.values():
            d["by_register"] = dict(d["by_register"])
            d["by_marker"] = dict(d["by_marker"].most_common())
    (OUT / "population.json").write_text(json.dumps(pop, indent=1, ensure_ascii=False))

    licences = Counter(t["licence"] for t in texts)
    manifest = {
        "study": "lexinspect Study 4: precision of metadiscourse and PHRASE detection",
        "built": today(),
        "seed": SEED,
        "set": "development" if dev else "evaluation",
        "provenance": prov,
        "lexinspect_version": prov.get("lexinspect"),
        "lexinspect_commit": git_commit(),
        "git": git,
        "exclusions": {
            "development_manifest": dev_info,
            "extra_file": str(args.exclude_texts) if args.exclude_texts else None,
            "extra_sha256": hashlib.sha256(args.exclude_texts.read_bytes()).hexdigest()
            if args.exclude_texts
            else None,
            "n_refs": len(EXCLUDE),
            "overlap_after_collection": 0,
        },
        "orders": {
            r: {"seed": o["seed"], "batch_size": o["batch_size"], "n": o["n"]}
            for r, o in orders["roles"].items()
        },
        "maintainer_sample": (
            {"allocation": "original human-check sample (15 per category, 5 per PHRASE stratum)"}
            if dev
            else {
                "totals": {"metadiscourse": args.maintainer_md, "phrase": args.maintainer_phrase},
                "min_per_substratum": MAINTAINER_MIN_PER_SUB,
                "allocation": allocs,
            }
        ),
        "pipeline_call": "lexinspect.pipeline.run_all(text, modules=['metadiscourse', 'phrase'])",
        "max_text_bytes": MAX_BYTES,
        "design": {
            "metadiscourse_target_per_category": MD_TARGET,
            "phrase_target_total": PHRASE_TARGET,
            "marker_cap_fraction": CAP_FRAC,
            "weights": "weight = N_sub / n_sub per sub-stratum (key.jsonl)",
            "strata": design,
        },
        "texts": {
            "n": len(texts),
            "by_register": dict(Counter(t["register"] for t in texts)),
            "by_discipline": dict(Counter(t["discipline"] for t in texts if t["discipline"])),
            "licences": dict(licences),
            "truncated": sum(t["truncated"] for t in texts),
        },
        "population": {
            "metadiscourse_hits": sum(1 for h in hits if h["module"] == "metadiscourse"),
            "phrase_hits": sum(1 for h in hits if h["module"] == "phrase"),
        },
        "items": {
            "n": len(items),
            "by_module": dict(Counter(i["module"] for i in items)),
            "max_items_from_one_text": max(Counter(k["text_id"] for k in key).values()),
            "human_sample": len(hs),
            "maintainer_sample": len(hs),
        },
        "selection_log": log,
        "publication_note": (
            "All texts are CC BY, CC0/public domain or CC BY-SA 4.0, so items.jsonl may be "
            "published with attribution (texts.jsonl lists title, authors, URL and licence "
            "per text). Because it includes CC BY-SA Wikipedia excerpts, the published "
            "items file must itself be released under CC BY-SA 4.0. The `claimed` field "
            "quotes PHRASE List entries, glosses and example sentences (Martinez & Schmitt "
            "2012), which carry no open licence: cite the list, and consider whether "
            "quoting them in a public dataset needs permission."
        ),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({k: manifest[k] for k in ("texts", "population", "items")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
