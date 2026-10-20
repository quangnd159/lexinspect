from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path("/Users/quangnguyendang/webapps/lexinspect")
PRIV = Path("/Users/quangnguyendang/lexinspect-private")
OUT = REPO / ".cache/validation/study4_eval_exclusions"
sys.path.insert(0, str(REPO / "scripts/validation/study4_precision"))
import build  # noqa: E402

st = json.load(open("/tmp/s4excl_scripts/state.json"))
excl = OUT / "exclusions.jsonl"
recs = [json.loads(x) for x in excl.read_text().splitlines() if x.strip()]
extra = build.read_exclusions(excl)
dev_refs, dev_info = build.load_dev_exclusions(REPO / ".cache/validation/study4/texts.jsonl")
union = extra | dev_refs


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


srcs = st["srcs"]
# ---- self-check (recomputed here, independently of the builder)
fix = REPO / "docs/validation/study4-fix040"
checks = []
dev_texts = [json.loads(x) for x in (REPO / ".cache/validation/study4/texts.jsonl").read_text().splitlines() if x.strip()]
for t in dev_texts:
    ov = build.exclusion_overlap([t], union)
    checks.append({"set": "development_manifest", "source_id": t["source_id"], "n_overlap": len(ov),
                   "all_ids_covered": build.text_refs(t) <= union})
for r in ("round1", "round2"):
    for t in [json.loads(x) for x in (fix / r / "collect/texts.jsonl").read_text().splitlines() if x.strip()]:
        ov = build.exclusion_overlap([t], union)
        checks.append({"set": f"fixcheck_{r}", "source_id": t["source_id"], "n_overlap": len(ov),
                       "all_ids_covered": build.text_refs(t) <= union})
for rec in recs:
    ov = build.exclusion_overlap([rec], union)
    checks.append({"set": "union_record", "source_id": rec["source_id"], "n_overlap": len(ov),
                   "all_ids_covered": build.text_refs(rec) <= union})
# every observed identity per source (all titles, all revisions, page id, PMCID, both EPMC URLs, DOI)
alias_missing = st["fail"]
n_fail = sum(1 for c in checks if c["n_overlap"] == 0 or not c["all_ids_covered"]) + len(alias_missing)
by_set = Counter(c["set"] for c in checks)

# ---- counts
def kinds(v):
    return v["kind"]


distinct = Counter(v["kind"] for v in srcs.values())
exp_counts = Counter()
exp_by_source = Counter()
for v in srcs.values():
    for e in sorted(set(v["exposures"])):
        exp_counts[e] += 1
        exp_by_source[f"{e} | {v['kind']}"] += 1
reg_counts = Counter(v["register"] for v in srcs.values())
in_file = Counter(r["source"] for r in recs)
dev_only = sum(1 for v in srcs.values() if set(v["exposures"]) == {"development_selected"})

# Simple English titles with no same-title English source in the union, and pool hits
vital = set(json.loads((REPO / ".cache/validation/study4/raw/pools/wiki_vital3.json").read_text())["titles"])
essays = set(json.loads((REPO / ".cache/validation/study4/raw/pools/wiki_essays.json").read_text())["titles"])
en_titles = {build._norm_ref(t) for v in srcs.values() if v["kind"] == "English Wikipedia" for t in v["titles"]}
simple_only = [v["titles"][0] for v in srcs.values() if v["kind"] == "Simple English Wikipedia"
               and build._norm_ref(v["titles"][0]) not in en_titles]
simple_only_in_pool = sorted(t for t in simple_only if t in vital or t in essays)
pool_hits = {
    "vital3_titles_in_pool": len(vital),
    "essays_titles_in_pool": len(essays),
    "vital3_pool_titles_matched_by_union_or_dev": sum(1 for t in vital if build._norm_ref(t) in union),
    "essays_pool_titles_matched_by_union_or_dev": sum(1 for t in essays if build._norm_ref(t) in union),
    "vital3_pool_titles_matched_by_extra_file_only": sum(1 for t in vital if build._norm_ref(t) in extra and build._norm_ref(t) not in dev_refs),
    "essays_pool_titles_matched_by_extra_file_only": sum(1 for t in essays if build._norm_ref(t) in extra and build._norm_ref(t) not in dev_refs),
    "simple_titles_without_same_title_english_source": len(simple_only),
    "of_which_in_vital3_or_essays_pool": simple_only_in_pool,
}
pmc_pool_n = 0
pmc_pool = set()
for f in (REPO / ".cache/validation/study4/raw/pools").glob("epmc_*.json"):
    for r in json.loads(f.read_text())["rows"]:
        pmc_pool.add(r["pmcid"])
def _refs(sel):
    out = set()
    for r in recs:
        if sel(set(r["exposure"]), r):
            out |= build.text_refs(r)
    return out
_tiers = [
    ("development_manifest", dev_refs),
    ("development_rejected_or_fixcheck", _refs(lambda e, r: any(x.startswith("fixcheck") or x == "development_fetched_rejected" for x in e))),
    ("study3_equivalence", _refs(lambda e, r: "study3_equivalence" in e)),
    ("study1_clear_only", _refs(lambda e, r: e == {"study1_clear_excerpt"})),
]
_bd = Counter()
_s1_simple = _refs(lambda e, r: e == {"study1_clear_excerpt"} and r["source"] == "Simple English Wikipedia")
_s1_en = _refs(lambda e, r: e == {"study1_clear_excerpt"} and r["source"] == "English Wikipedia")
for t in vital:
    n = build._norm_ref(t)
    for name, rs in _tiers:
        if n in rs:
            _bd[name] += 1
            if name == "study1_clear_only" and n in _s1_simple and n not in _s1_en:
                _bd["study1_clear_only_via_simple_title_alias"] += 1
            break
pool_hits["vital3_titles_excluded_by_first_matching_tier"] = dict(_bd)
pool_hits["epmc_pool_pmcids"] = len(pmc_pool)
pool_hits["epmc_pool_pmcids_in_union_or_dev"] = sum(1 for p in pmc_pool if build._norm_ref(p) in union)

# ---- other manifests checked (copies / dry runs), hashed
other = []
for p in [
    REPO / ".cache/validation/study4_v040/texts.jsonl",
    PRIV / "study4-pilot040/selection/build/texts.jsonl",
    REPO / ".cache/validation/study4_scratch/dev032/texts.jsonl",
    REPO / ".cache/validation/study4_scratch/devcopy/texts.jsonl",
    REPO / ".cache/validation/study4_fix040/harness_dryrun/round_dev/texts.jsonl",
    REPO / ".cache/validation/study4_fix040/harness_dryrun/final/51ed081b43a8895a/round_dev/texts.jsonl",
    REPO / ".cache/validation/study4_fix040/round2/harness_dryrun/eb233ecaea8f2699/round_dev/texts.jsonl",
    REPO / ".cache/validation/study4_fix040/round2/harness_dryrun/final/eb233ecaea8f2699/round_dev/texts.jsonl",
    REPO / ".cache/validation/study4_fix040/s8_harness_snapshot/round_dev/texts.jsonl",
]:
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    ids = {r["source_id"] for r in rows}
    other.append({"path": str(p), "sha256": sha(p), "n_texts": len(rows),
                  "same_sources_as_development": ids == {t["source_id"] for t in dev_texts},
                  "role": "copy or relabelled replay of the development texts (dry runs, 0.4.0 rebuild, pilot selection)"})
for p in sorted((PRIV / "study4-fix040/archive").glob("*.tar")):
    other.append({"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size,
                  "role": "archived round snapshot; member listing checked: raw/epmc and raw/wiki file sets, texts.jsonl and fetch_journal.jsonl equal the live round directories (the INCOMPLETE tar is truncated; its readable members are a subset)"})
raw_copies = [
    {"path": str(REPO / d), "role": "development raw cache or byte-identical copy (205 epmc+wiki files; combined listing hash 7ba21b6996d53b1b)"}
    for d in (".cache/validation/study4/raw", ".cache/validation/study4_v040/raw", ".cache/validation/study4_scratch/rawcopy")
]

not_excluded = [
    {"what": "Europe PMC search results and Wikipedia list pages (raw/pools, raw/tmp; ~11,700 PMCIDs and ~2,100 essay page ids)",
     "reason": "Pool metadata (ids, titles, DOIs) only; no text body was fetched or read. These pools are the evaluation sampling frame itself, so excluding them would empty it."},
    {"what": "Titles skipped by the rounds' exclusion pre-check (round 1: 'Information', 'Wikipedia:Wikipedia is not a gazetteer'; round 2: PMC8846514, PMC9604947, PMC11341679, 'Machine', 'Chinese folk religion', 'Natural rubber', 'Land', \"Wikipedia:Don't panic\")",
     "reason": "Each matched an earlier development or round-1 source and was skipped before any fetch, so it is already in the union (it was checked)."},
    {"what": "Study 3 Project Gutenberg (100) and ELLIPSE (100) texts, part of the 842-text round-2 equivalence set",
     "reason": "Neither is a Study 4 source, so no evaluation candidate can share their identity. Their titles are novel or essay titles, not Wikipedia page titles of the same text."},
    {"what": "4 test fixtures (tests/fixtures/sample_academic.txt, sample_learner.txt, sample_narrative.txt, sample_simple.txt)",
     "reason": "Constructed sample texts with no source URL, PMCID or page id. No identifier exists to exclude."},
    {"what": "418 test sentences (round-1 tests/test_fix_families.py, tests/test_metadiscourse.py, tests/test_phrase.py)",
     "reason": "The test_fix_families.py provenance header says they are constructed, audit-derived (constructed probes from sol_impl_audit_r1/r2) or guidelines examples (Hyland 2005 quotations), and none comes from the Study 4 development or evaluation texts. A local test id is not a source identity. The sweep found no PMCID or Wikipedia page id or revision in them except synthetic test values."},
    {"what": "Audit probe sentences (sol_impl_audit_r1/r2/r3, sol_final_audit_r1a/r1b, harness audits)",
     "reason": "The audits label them as constructed examples (r1: 'Probes below are constructed audit examples unless explicitly identified as an inventory example'). An 'inventory example' is a PHRASE sense-inventory example, not a Europe PMC or Wikipedia text. No public-source identifier found in them."},
    {"what": "Synthetic identifiers in tests and logs: PMC9000001, PMC9000002, PMC9000003 (round-2 full-suite log), PMC9999999 (fixcheck/test_r7.py), pageid 1, 3, 424242 (fixcheck/test_r8.py), pageid 42, 43 (test_analyse.py)",
     "reason": "Made-up ids in unit tests; no text was fetched for them. Excluding them would only drop unrelated real records that happen to share the id."},
    {"what": "Harness dry runs (.cache/validation/study4_fix040/harness_dryrun, round2/harness_dryrun*, s8_harness_snapshot) and the 0.4.0 pilot dry run (lexinspect-private/study4-pilot040/dryrun)",
     "reason": "The harness dry runs replay the 120 development texts (same source ids, checked). collect_plan_round1 holds pool listings only. The pilot dry run used two made-up items (docs/validation/study4-pilot040/LAUNCH.md)."},
    {"what": "0.4.0 rebuild and common development pilot (.cache/validation/study4_v040, lexinspect-private/study4-pilot040/selection), the 16 Oct pilot (.cache/validation/study4_pilot) and the study4_scratch dev copies",
     "reason": "All are built on the canonical development texts (texts.jsonl SHA-256 5dba40cc...; raw cache byte-identical). These are covered by the development manifest."},
    {"what": "Labelling transcripts and post-decision events (lexinspect-private/study4-fix040/round*/, post_decision_events/)",
     "reason": "Swept for PMCIDs and page ids: only round or development sources appear."},
    {"what": "Study 2 corpora (UD English-EWT, UD English-ESLSpok)",
     "reason": "Web genres and learner speech, not Europe PMC or Wikipedia."},
    {"what": "Study 5 corpora (CEFR-SP, ReadMe++, ELG CEFR, Cambridge exams, CEFR-ASAG, ICLE500, Ace-CEFR)",
     "reason": "CEFR-SP has single sentences drawn partly from Wiki-Auto (English and Simple Wikipedia), but with no article title, page id or revision (title 'na'), so they cannot be mapped to a source without a network lookup. They were not used in Study 4 fix development. See open questions."},
]

open_questions = [
    "Study 1 CLEAR (largest judgement call): 274 English Wikipedia and 274 Simple English Wikipedia excerpt sources are included conservatively. CLEAR was used only for readability (Study 1), never for Study 4 fix development or equivalence, so the contamination risk is negligible. The cost is real, though: 117 of the 1,001 cached Level-3 Vital titles are excluded only because of Study 1 records (47 through English URLs, 70 through Simple-title aliases), on top of those excluded by development, rejected-candidate, fix-check and Study 3 exposures (see pool_impact.vital3_titles_excluded_by_first_matching_tier). That removes about 20% of the general frame, mostly core science and history topics. Dropping the 541 records whose only exposure is study1_clear_excerpt would restore those 117 titles. This is the maintainer's decision; record it in the prereg either way.",
    "Title-only English records (Study 3 and CLEAR, 317 sources with no page id in any local cache) are matched by title and /wiki/ URL only. build.py checks the pool title before fetching and the canonical title, page id and current revision after. So a page renamed since its exposure, with the pool listing only the new title, would not be caught. Resolving page ids needs a Wikipedia API lookup, which this task did not allow. Recommend a one-off lookup (titles to page ids, following redirects) before Stage 1, adding pageid:N to these records.",
    "Simple English Wikipedia is a different site, so its page ids and revisions are not English identities. The records carry no revid field (build.text_refs would turn it into an en.wikipedia oldid URL) and use a simplewiki-prefixed source_id. Their titles are kept, so build.py's title check also excludes a same-title English article. Recommended conservatively: Study 3 paired each Simple text with its English counterpart, and the topic is shared. Only a few Simple-only titles fall in the cached pools (listed in pool_impact).",
    "Fetched-but-rejected candidates (development, round 1, round 2: licence not CC BY/CC0, too short, humour essay) are included. Their bodies sat in a raw cache but were never sampled, labelled or analysed. Reasons: the reviewer named failed attempts, and eligibility can change (licence metadata, page growth), e.g. development rejects 'Genghis Khan' and 'Nile' (too short in Oct 2026). Excluding them costs at most a few pool members; keep or drop is your call.",
    "Only build.text_refs fields are matched. For Wikipedia records, 'url' is the earliest and 'revid' the latest observed revision; no source had more than two. PMIDs and PMC version ids are not recorded locally, and build.py does not match them.",
    "The pool caches are those of 2026-10-16 (the same files in development and both rounds). If the evaluation build refreshes the pools, re-run the overlap check on the new pool. Page id and PMCID matching stay valid; title matching depends on the titles.",
]

inv = {
    "purpose": "Frozen evaluation exclusion union for Study 4 (precision of metadiscourse and PHRASE detection). exclusions.jsonl is the ADDITIONAL file for build.py --exclude-texts; build.py always excludes the development manifest itself.",
    "built": "2026-10-21",
    "method": "Identifiers only. Read build.read_exclusions/text_refs/_norm_ref/exclusion_overlap/excluded/load_dev_exclusions and the collectors. Read every fix-check collect record and fetch journal, and listed the private round caches and archive tars without modifying them. Swept .cache, docs, scripts, tests, src and lexinspect-private for PMCIDs and Wikipedia page ids and resolved every hit, and checked Studies 1, 2, 3 and 5 for Europe PMC and Wikipedia sources. No network access; build.py was not run; no text body was copied.",
    "output_files": {
        "exclusions.jsonl": {"path": str(excl), "sha256": sha(excl), "n_lines": len(recs),
                              "n_records_by_source": dict(in_file)},
    },
    "identifier_rule": "build.text_refs (source_id, url, fulltext_url, doi, title, Europe PMC article URL for source 'Europe PMC', en.wikipedia oldid URL from revid), normalised by build._norm_ref",
    "n_normalised_identifiers": {
        "exclusions_file": len(extra),
        "development_manifest": len(dev_refs),
        "union_file_plus_development": len(union),
        "overlap_file_and_development": len(extra & dev_refs),
    },
    "development_manifest": dev_info,
    "input_manifests": sorted(st["inputs"].values(), key=lambda x: x["path"]),
    "other_manifests_checked": other,
    "raw_caches_checked": raw_copies,
    "distinct_sources": {
        "total": len(srcs),
        "by_source": dict(distinct),
        "development_selected_only (excluded by build.py, not in the file)": dev_only,
        "in_exclusions_file": len(recs),
        "by_register_source": dict(reg_counts),
    },
    "sources_by_exposure": dict(sorted(exp_counts.items())),
    "sources_by_exposure_and_source": dict(sorted(exp_by_source.items())),
    "named_counts_check": {
        "development_selected": exp_counts["development_selected"],
        "fixcheck_round1_selected": exp_counts["fixcheck_round1_selected"],
        "fixcheck_round2_selected": exp_counts["fixcheck_round2_selected"],
        "distinct_dev_plus_rounds_selected": sum(1 for v in srcs.values() if set(v["exposures"]) & {"development_selected", "fixcheck_round1_selected", "fixcheck_round2_selected"}),
        "study3_wikipedia_texts": {"English Wikipedia": st["s3_counts"].get("English Wikipedia"), "Simple English Wikipedia": st["s3_counts"].get("Simple English Wikipedia")},
        "clear_rows_with_wikipedia_url": st["clear_rows"],
    },
    "pool_impact": pool_hits,
    "not_excluded": not_excluded,
    "self_check": {
        "rule": "for every source in the union and in the development manifest, build.exclusion_overlap([record], build.read_exclusions(exclusions.jsonl) | dev_refs) is non-empty, and every text_refs identity of the record is in that set; and for every source, every observed identity (all titles incl. requested pool titles, all revisions, page id, PMCID, Europe PMC article and full-text URLs, DOI) is in that set",
        "records_checked": dict(by_set),
        "alias_failures": alias_missing,
        "failures": n_fail,
        "passed": n_fail == 0,
    },
    "open_questions": open_questions,
}
(OUT / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1, sort_keys=False) + "\n")
print(json.dumps({k: inv[k] for k in ("n_normalised_identifiers", "distinct_sources", "sources_by_exposure", "self_check", "pool_impact")}, indent=1, ensure_ascii=False)[:5000])
