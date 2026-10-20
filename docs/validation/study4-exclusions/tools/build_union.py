"""Build the Study 4 evaluation exclusion union (identifiers only; no text bodies).

Run from the repo with: uv run --offline --no-sync python -I build_union.py
Reads only; writes only under .cache/validation/study4_eval_exclusions/.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/Users/quangnguyendang/webapps/lexinspect")
PRIV = Path("/Users/quangnguyendang/lexinspect-private/study4-fix040")
OUT = REPO / ".cache/validation/study4_eval_exclusions"
sys.path.insert(0, str(REPO / "scripts/validation/study4_precision"))
import build  # noqa: E402

EPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DEV_TEXTS = REPO / ".cache/validation/study4/texts.jsonl"
DEV_MANIFEST = REPO / ".cache/validation/study4/manifest.json"
DEV_RAW = REPO / ".cache/validation/study4/raw"
FIX = REPO / "docs/validation/study4-fix040"
S3_MANIFEST = REPO / ".cache/validation/study3/manifest.jsonl"
S3_SELECTION = REPO / "scripts/validation/study3_agreement/wikipedia_selection.json"
CLEAR = REPO / ".cache/validation/clear/CLEAR_corpus_final.xlsx"
CLEAR_WIKI = Path(sys.argv[1])  # identifiers extracted from CLEAR by clear_wiki.py

inputs: dict[str, dict] = {}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def note_input(p: Path, role: str, **extra) -> None:
    inputs[str(p)] = {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size, "role": role, **extra}


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------- pools
pool_rows: dict[str, dict] = {}
for f in sorted((DEV_RAW / "pools").glob("epmc_*.json")):
    for r in json.loads(f.read_text())["rows"]:
        pool_rows.setdefault(r["pmcid"], r)
vital = set(json.loads((DEV_RAW / "pools/wiki_vital3.json").read_text())["titles"])
essays = set(json.loads((DEV_RAW / "pools/wiki_essays.json").read_text())["titles"])
for f in sorted((DEV_RAW / "pools").glob("*.json")):
    note_input(f, "pool listing (metadata only; used for DOI/title lookup and pool membership)")
for r in ("round1", "round2"):
    for f in sorted((PRIV / r / "raw/pools").glob("*.json")):
        twin = DEV_RAW / "pools" / f.name
        assert twin.exists() and twin.read_bytes() == f.read_bytes(), f


def wiki_register(title: str) -> str:
    if title in vital:
        return "English Wikipedia: Level-3 Vital Articles pool (general)"
    if title in essays:
        return "English Wikipedia: Category:Wikipedia essays pool (argumentative)"
    return "English Wikipedia: not in the cached Study 4 pools"


# ---------------------------------------------------------------- source store
class Src:
    def __init__(self, kind: str, key: str):
        self.kind, self.key = kind, key
        self.pmcid = self.doi = self.pageid = None
        self.titles: list[str] = []  # first = primary
        self.revids: list[int] = []
        self.urls: list[str] = []
        self.exposures: list[dict] = []
        self.register_source: str | None = None
        self.in_dev = False

    def add_title(self, t):
        if t and t not in self.titles:
            self.titles.append(t)

    def add_rev(self, r):
        if r and int(r) not in self.revids:
            self.revids.append(int(r))

    def add_url(self, u):
        if u and u not in self.urls:
            self.urls.append(u)

    def expose(self, label, **detail):
        e = {"exposure": label, **detail}
        if e not in self.exposures:
            self.exposures.append(e)


srcs: dict[str, Src] = {}
title_to_pageid: dict[str, int] = {}


def epmc(pmcid: str) -> Src:
    k = f"epmc:{pmcid}"
    if k not in srcs:
        s = srcs[k] = Src("Europe PMC", k)
        s.pmcid = pmcid
        s.register_source = "Europe PMC CC BY/CC0 full text (academic)"
        row = pool_rows.get(pmcid)
        if row:
            s.doi = row.get("doi")
            s.add_title(row.get("title"))
        s.add_url(f"https://europepmc.org/article/PMC/{pmcid}")
        s.add_url(f"{EPMC_REST}/{pmcid}/fullTextXML")
    return srcs[k]


def enwiki(pageid: int | None, title: str | None) -> Src:
    if pageid is None and title is not None:
        pageid = title_to_pageid.get(build._norm_ref(title))
    k = f"enwiki:pageid:{pageid}" if pageid is not None else f"enwiki:title:{build._norm_ref(title)}"
    if k not in srcs:
        s = srcs[k] = Src("English Wikipedia", k)
        s.pageid = pageid
    s = srcs[k]
    s.add_title(title)
    if pageid is not None and title:
        title_to_pageid.setdefault(build._norm_ref(title), pageid)
    if s.register_source is None and title:
        s.register_source = wiki_register(title)
    return s


def simplewiki(title: str) -> Src:
    k = f"simplewiki:title:{build._norm_ref(title)}"
    if k not in srcs:
        s = srcs[k] = Src("Simple English Wikipedia", k)
        s.register_source = "Simple English Wikipedia (not a Study 4 source; title kept as an alias)"
    s = srcs[k]
    s.add_title(title)
    return s


# ---------------------------------------------------------------- local wiki page index
raw_wiki_dirs = [DEV_RAW / "wiki", PRIV / "round1/raw/wiki", PRIV / "round2/raw/wiki"]
raw_pages: dict[str, dict] = {}  # path -> page meta
for d in raw_wiki_dirs:
    for f in sorted(d.glob("*.json")):
        q = json.loads(f.read_text())
        pages = q.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            raw_pages[str(f)] = {"missing": True}
            continue
        p = pages[0]
        raw_pages[str(f)] = {
            "pageid": p["pageid"],
            "title": p["title"],
            "revid": p["revisions"][0]["revid"] if p.get("revisions") else None,
            "fullurl": p.get("fullurl"),
            "redirects": [r.get("from") for r in q["query"].get("redirects", [])],
            "normalized": [r.get("from") for r in q["query"].get("normalized", [])],
        }
        title_to_pageid.setdefault(build._norm_ref(p["title"]), p["pageid"])

# ---------------------------------------------------------------- development (auto-excluded)
note_input(DEV_TEXTS, "canonical development manifest (excluded automatically by build.py)")
note_input(DEV_MANIFEST, "development build manifest (selection and rejection log)")
dev_refs, dev_info = build.load_dev_exclusions(DEV_TEXTS)
dev_texts = jl(DEV_TEXTS)
dev_ids = {t["source_id"] for t in dev_texts}
for t in dev_texts:
    if t["source"] == "Europe PMC":
        s = epmc(t["source_id"])
        s.doi = s.doi or t.get("doi")
        s.add_title(t.get("title"))
    else:
        s = enwiki(int(t["source_id"].split(":")[1]), t["title"])
        s.add_rev(t.get("revid"))
        s.add_url(t.get("url"))
    s.in_dev = True
    s.expose("development_selected", manifest=str(DEV_TEXTS), text_id=t.get("id") or t.get("text_id"))

dev_log = json.loads(DEV_MANIFEST.read_text())["selection_log"]
dev_epmc_files = sorted(p.stem for p in (DEV_RAW / "epmc").glob("*.xml"))
dev_rej_reason = {r["pmcid"]: r["reason"] for r in dev_log["academic_rejected"]}
for pmcid in dev_epmc_files:
    if pmcid in dev_ids:
        continue
    s = epmc(pmcid)
    s.expose(
        "development_fetched_rejected",
        detail=f"full text fetched into the development raw cache, rejected by build.py: {dev_rej_reason.get(pmcid, 'reason not logged')}",
    )
assert set(dev_rej_reason) <= set(dev_epmc_files)
dev_wiki_rej = {}
for k in ("wiki_general_rejected", "wiki_essays_rejected"):
    for r in dev_log[k]:
        dev_wiki_rej[r["title"]] = r["reason"]
for f, p in raw_pages.items():
    if not f.startswith(str(DEV_RAW)) or p.get("missing"):
        continue
    if f"pageid:{p['pageid']}" in dev_ids:
        continue
    # recover the requested title through the cache key
    req = [t for t in dev_wiki_rej if build._key(t) == Path(f).stem]
    s = enwiki(p["pageid"], p["title"])
    for t in req:
        s.add_title(t)
    s.add_rev(p["revid"])
    s.expose(
        "development_fetched_rejected",
        detail=f"page fetched into the development raw cache, rejected by build.py: {dev_wiki_rej.get(req[0]) if req else 'reason not logged'}",
    )

# ---------------------------------------------------------------- fix-check rounds
for rnd in ("round1", "round2"):
    cdir = FIX / rnd / "collect"
    for name in ("texts.jsonl", "collection.json", "fetch_journal.jsonl", "manifest_collect.json",
                 "manifest_plan.json", "freeze_record.json", "execution.json", "execution_start.json", "command.txt"):
        note_input(cdir / name, f"fix-check {rnd} collection record")
    texts = jl(cdir / "texts.jsonl")
    coll = json.loads((cdir / "collection.json").read_text())
    assert coll["texts_jsonl_sha256"] == sha(cdir / "texts.jsonl")
    sel_ids = {t["source_id"] for t in texts}
    for t in texts:
        if t["source"] == "Europe PMC":
            s = epmc(t["source_id"])
            s.doi = s.doi or t.get("doi")
            s.add_title(t.get("title"))
        else:
            s = enwiki(int(t["source_id"].split(":")[1]), t["title"])
            s.add_rev(t.get("revid"))
            s.add_url(t.get("url"))
        s.expose(f"fixcheck_{rnd}_selected", manifest=str(cdir / "texts.jsonl"), text_id=t["text_id"],
                 detail="collected, sampled and labelled in the fix check")
    rej = {r["pmcid"]: r["reason"] for r in coll["selection_log"]["academic_rejected"]}
    fetched_epmc = []
    for line in (cdir / "fetch_journal.jsonl").read_text().splitlines():
        j = json.loads(line)
        if j["event"] == "outcome" and j["url"].startswith(EPMC_REST):
            fetched_epmc.append(j["url"].split("/")[-2])
    for pmcid in fetched_epmc:
        if pmcid in sel_ids:
            continue
        epmc(pmcid).expose(f"fixcheck_{rnd}_fetched_rejected",
                           detail=f"full text fetched into the private {rnd} raw cache, rejected: {rej.get(pmcid, 'reason not logged')}")
    assert set(rej) <= set(fetched_epmc), rnd
    wrej = {}
    for k in ("wiki_general_rejected", "wiki_essays_rejected"):
        for r in coll["selection_log"][k]:
            wrej[r["title"]] = r["reason"]
    for p in coll["wiki_page_log"]:
        if p.get("pageid") is None:
            continue
        s = enwiki(p["pageid"], p["title"])
        s.add_title(p.get("requested_title"))
        s.add_rev(p.get("revid"))
        if f"pageid:{p['pageid']}" not in sel_ids:
            s.expose(f"fixcheck_{rnd}_fetched_rejected",
                     detail=f"page fetched into the private {rnd} raw cache, rejected: {wrej.get(p.get('requested_title'), 'reason not logged')}")
    # cross-check the public page log against the private raw cache
    priv = {(v["pageid"], v["revid"]) for f, v in raw_pages.items() if f.startswith(str(PRIV / rnd)) and not v.get("missing")}
    logd = {(p["pageid"], p["revid"]) for p in coll["wiki_page_log"] if p.get("pageid") is not None}
    assert priv == logd, (rnd, priv ^ logd)
    priv_epmc = {f.stem for f in (PRIV / rnd / "raw/epmc").glob("*.xml")}
    assert priv_epmc == set(fetched_epmc), rnd

# ---------------------------------------------------------------- Study 3 (equivalence evidence)
note_input(S3_MANIFEST, "Study 3 manifest (300 texts; 842-text round-2 equivalence evidence)")
note_input(S3_SELECTION, "Study 3 Wikipedia selection (titles and revisions)")
s3 = jl(S3_MANIFEST)
sel = json.loads(S3_SELECTION.read_text())["topics"]
by_en_rev = {t["en_revid"]: t for t in sel}
by_simple_rev = {t["simple_revid"]: t for t in sel}
s3_counts = Counter(r["source"] for r in s3)
for r in s3:
    if r["source"] == "English Wikipedia":
        rev = r["selection"]["revid"]
        t = by_en_rev[rev]
        s = enwiki(None, t["en_title"])
        s.add_rev(rev)
        s.add_url(r["url"])
        s.expose("study3_equivalence", manifest=str(S3_MANIFEST), local_id=r["id"],
                 detail="Study 3 text; one of the 842 texts in the round-2 equivalence check")
    elif r["source"] == "Simple English Wikipedia":
        rev = r["selection"]["revid"]
        t = by_simple_rev[rev]
        s = simplewiki(t["simple_title"])
        s.simple_revid = rev
        s.add_url(r["url"])
        s.en_counterpart = t["en_title"]
        s.expose("study3_equivalence", manifest=str(S3_MANIFEST), local_id=r["id"],
                 detail="Study 3 text (Simple English Wikipedia); one of the 842 texts in the round-2 equivalence check")

# ---------------------------------------------------------------- Study 1 (CLEAR excerpts from Wikipedia)
note_input(CLEAR, "Study 1 CLEAR corpus (4,724 excerpts; 549 cite a Wikipedia URL)")
clear_rows = json.loads(CLEAR_WIKI.read_text())
for r in clear_rows:
    u = r["url"].strip()
    pu = urllib.parse.urlsplit(u)
    title = urllib.parse.unquote(pu.path.split("/wiki/", 1)[1]).replace("_", " ").strip()
    if pu.netloc == "en.wikipedia.org":
        s = enwiki(None, title)
    elif pu.netloc == "simple.wikipedia.org":
        s = simplewiki(title)
    else:
        raise SystemExit(u)
    s.add_url(u)
    s.expose("study1_clear_excerpt", corpus=str(CLEAR), local_id=f"CLEAR:{r['clear_id']}",
             detail="CLEAR excerpt (pre-2021 revision, revision id not recorded) analysed in Study 1")

# ---------------------------------------------------------------- register (pool membership over all titles)
sel_register = {}
for p in [DEV_TEXTS, FIX / "round1/collect/texts.jsonl", FIX / "round2/collect/texts.jsonl"]:
    for t in jl(p):
        if t["source"] == "English Wikipedia":
            sel_register[f"enwiki:pageid:{t['source_id'].split(':')[1]}"] = t["register"]
for k, s in srcs.items():
    if s.kind != "English Wikipedia":
        continue
    regs = {wiki_register(t) for t in s.titles} - {wiki_register("\x00")}
    if len(regs) == 1:
        s.register_source = regs.pop()
    elif k in sel_register:
        s.register_source = {"general": wiki_register(next(iter(vital))), "argumentative": wiki_register(next(iter(essays)))}[sel_register[k]] + " [selected; title not in cached pool]"
    else:
        s.register_source = wiki_register("\x00")


# ---------------------------------------------------------------- records
def wiki_url(host: str, title: str) -> str:
    return f"https://{host}/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="/:(),'!*$@&=+;~")


records, alias_records = [], []
for k, s in sorted(srcs.items()):
    if s.in_dev and all(e["exposure"] == "development_selected" for e in s.exposures):
        continue  # canonical development text only: excluded by build.py itself
    exp = sorted({e["exposure"] for e in s.exposures})
    base = {"exposure": exp, "exposure_detail": s.exposures, "register_source": s.register_source,
            "source": s.kind, "union_key": k}
    if s.kind == "Europe PMC":
        rec = {**base, "source_id": s.pmcid, "doi": s.doi, "title": s.titles[0] if s.titles else None,
               "url": f"https://europepmc.org/article/PMC/{s.pmcid}", "fulltext_url": f"{EPMC_REST}/{s.pmcid}/fullTextXML"}
        extra_titles = s.titles[1:]
        extra_revs = []
    elif s.kind == "English Wikipedia":
        title = s.titles[0] if s.titles else None
        sid = f"pageid:{s.pageid}" if s.pageid is not None else wiki_url("en.wikipedia.org", title)
        revs = sorted(s.revids)
        rec = {**base, "source_id": sid, "title": title, "doi": None,
               "fulltext_url": wiki_url("en.wikipedia.org", title)}
        if revs:
            rec["revid"] = revs[-1]
            rec["url"] = f"https://en.wikipedia.org/w/index.php?oldid={revs[0]}"
            extra_revs = revs[1:-1]
        else:
            rec["url"] = None
            extra_revs = []
        rec["all_revids"] = revs
        extra_titles = s.titles[1:]
        extra_urls = [u for u in s.urls if build._norm_ref(u) not in build.text_refs(rec)]
        assert all("oldid=" in u and int(u.split("oldid=")[1]) in revs or "/wiki/" in u for u in extra_urls), extra_urls
        extra_titles += [urllib.parse.unquote(u.split("/wiki/")[1]).replace("_", " ") for u in extra_urls if "/wiki/" in u
                         and urllib.parse.unquote(u.split("/wiki/")[1]).replace("_", " ") not in s.titles]
    else:  # Simple English Wikipedia: no revid field (it would mint an en.wikipedia oldid URL)
        title = s.titles[0]
        rev = getattr(s, "simple_revid", None)
        rec = {**base, "source_id": f"simplewiki:{wiki_url('simple.wikipedia.org', title)}", "title": title, "doi": None,
               "url": f"https://simple.wikipedia.org/w/index.php?oldid={rev}" if rev else None,
               "fulltext_url": wiki_url("simple.wikipedia.org", title), "simple_revid": rev,
               "english_counterpart_title": getattr(s, "en_counterpart", None)}
        extra_titles, extra_revs = s.titles[1:], []
    rec["all_titles"] = s.titles
    records.append(rec)
    for t in extra_titles:
        alias_records.append({"record": "alias", "alias_of": k, "source": s.kind, "title": t, "exposure": exp,
                              "register_source": s.register_source, "alias_kind": "title"})
    for r in extra_revs:
        alias_records.append({"record": "alias", "alias_of": k, "source": s.kind, "revid": r,
                              "url": f"https://en.wikipedia.org/w/index.php?oldid={r}", "exposure": exp,
                              "register_source": s.register_source, "alias_kind": "revision"})

ORDER = {"Europe PMC": 0, "English Wikipedia": 1, "Simple English Wikipedia": 2}
records.sort(key=lambda r: (ORDER[r["source"]], r["union_key"]))
alias_records.sort(key=lambda r: (ORDER[r["source"]], r["alias_of"], r.get("title") or "", r.get("revid") or 0))
OUT.mkdir(parents=True, exist_ok=True)
excl = OUT / "exclusions.jsonl"
with excl.open("w", encoding="utf-8") as fh:
    for r in records + alias_records:
        fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

# ---------------------------------------------------------------- checks
extra = build.read_exclusions(excl)
union = extra | dev_refs
fail = []
for s in srcs.values():
    # every observed identity of every source, in the form build.py would generate
    ids = set()
    if s.kind == "Europe PMC":
        ids |= build.text_refs({"source": "Europe PMC", "source_id": s.pmcid, "doi": s.doi,
                                "url": f"https://europepmc.org/article/PMC/{s.pmcid}",
                                "fulltext_url": f"{EPMC_REST}/{s.pmcid}/fullTextXML"})
    elif s.kind == "English Wikipedia":
        if s.pageid is not None:
            ids.add(build._norm_ref(f"pageid:{s.pageid}"))
        for r in s.revids:
            ids.add(build._norm_ref(f"https://en.wikipedia.org/w/index.php?oldid={r}"))
    for t in s.titles:
        ids.add(build._norm_ref(t))
    missing = sorted(ids - union)
    probe = {"source": s.kind, "source_id": f"pageid:{s.pageid}" if s.pageid is not None else (s.pmcid or None),
             "title": s.titles[0] if s.titles else None, "doi": s.doi}
    hit = build.exclusion_overlap([probe], union)
    if missing or not hit:
        fail.append({"key": s.key, "missing": missing, "overlap": hit})

# the actual dev records against the union too
for t in dev_texts:
    if not build.exclusion_overlap([t], union):
        fail.append({"key": t["source_id"], "missing": ["dev record not matched"]})
for rnd in ("round1", "round2"):
    for t in jl(FIX / rnd / "collect/texts.jsonl"):
        if not build.exclusion_overlap([t], union) or not build.text_refs(t) <= union:
            fail.append({"key": t["source_id"], "missing": [f"{rnd} record not fully matched"]})
for r in records:
    if not build.exclusion_overlap([r], union):
        fail.append({"key": r["union_key"], "missing": ["own record not matched"]})

json.dump({"srcs": {k: {"kind": s.kind, "exposures": [e["exposure"] for e in s.exposures], "in_dev": s.in_dev,
                        "titles": s.titles, "revids": s.revids, "pageid": s.pageid, "pmcid": s.pmcid, "doi": s.doi,
                        "register": s.register_source}
                    for k, s in srcs.items()},
           "n_records": len(records), "n_alias": len(alias_records), "n_extra_refs": len(extra),
           "n_union_refs": len(union), "dev_info": dev_info, "fail": fail, "inputs": inputs,
           "s3_counts": s3_counts, "clear_rows": len(clear_rows)},
          open("/tmp/s4excl_scripts/state.json", "w"), ensure_ascii=False, indent=1, default=list)
print("records", len(records), "alias", len(alias_records), "extra refs", len(extra), "union", len(union), "fail", len(fail))
print(Counter(r["source"] for r in records))
print(Counter(tuple(r["exposure"]) for r in records).most_common())
print(fail[:10])
