# Study 4 evaluation exclusion union (built 2026-10-21)

The frozen additional exclusion file is docs/validation/study4-exclusions/exclusions.jsonl, SHA-256 477f2197ce00e402441d810c4825e6d98517be4fa1e50d59ee2d4c0800f9b263. It contains 909 JSON source records, 331 plain identifier/title aliases and one comment (1,241 physical lines). build.read_exclusions returns 3,132 identifiers; together with the canonical development manifest's 440, there are 3,563 distinct identifiers. The former 909-record file is retained as exclusions_v1_before_pageids.jsonl; its counts and decisions are historical. The final machine inventory is inventory.json; the former inventory is retained unchanged as inventory_v1_historical.json and is historical too.

The one evaluation build passes it through `--exclude-texts` (the command in `docs/validation/study4-preregistration.md`, "The evaluation build, as frozen at stage 1"), from a clean checkout of the stage-1 commit:

```
uv run --offline --no-sync python -I scripts/validation/study4_precision/build.py \
    --set evaluation --seed 3195330621 \
    --out .cache/validation/study4_eval --raw-cache .cache/validation/study4_eval/raw \
    --exclude-texts docs/validation/study4-exclusions/exclusions.jsonl
```

build.py always excludes the canonical development manifest itself (`.cache/validation/study4/texts.jsonl`, SHA-256 `5dba40cc…f1cc8`, 120 texts, 440 normalised identifiers). This file adds every other exposed source.

| File | SHA-256 |
|---|---|
| `exclusions.jsonl` (frozen: 909 records, 331 alias lines, 1 comment) | `477f2197ce00e402441d810c4825e6d98517be4fa1e50d59ee2d4c0800f9b263` |
| `inventory.json` (final inventory, written by `tools/final_inventory.py`) | `11daffc283629070c502f5558e648057e757bbc112638ccf6ee8c2edbed36641` |
| `exclusions_v1_before_pageids.jsonl` (historical: the 909-record v1 file) | `5d8cace25244a1795c2ef242918507200ecffd985d4500a89eea875234fd0c75` |
| `inventory_v1_historical.json` (historical: the v1 inventory, formerly `inventory.json`, byte for byte) | `118ff3dc4417eb74b569b0497be1d4a24ed4d218f7b217cf4c6a5c42f356d58a` |
| `tools/clear_wiki.py`, `tools/build_union.py`, `tools/inventory.py` (built v1; rerun in that order), `tools/add_pageids.py` (added the aliases) | in `inventory.json` under `builders` |
| `tools/final_inventory.py` (writes `inventory.json`; `--check` rebuilds it in memory and compares) | – |
| `pageid_lookup/` (the 2026-10-21 lookup and its raw responses) | in `inventory.json` under `pageid_lookup` |

The sections below, up to the addendum, describe the v1 build. Its source records are unchanged in the frozen file; its identifier counts and open questions are historical.

Every v1 line, and every `{` line of the frozen file, is a JSON object that `build.read_exclusions` reads through `build.text_refs`. The fields it uses are `source`, `source_id`, `url`, `fulltext_url`, `doi`, `title` and `revid`. The extra fields (`exposure`, `exposure_detail`, `register_source`, `all_titles`, `all_revids`, `union_key`) are for people and are ignored by build.py. Lines are sorted by source (Europe PMC, English Wikipedia, Simple English Wikipedia) and then by key. No text body, guideline text or PHRASE List material is in any output. A scan against the private fragment file found 0 restricted fragments.

## What is excluded

There are 1,027 distinct sources in total: 118 Europe PMC, 585 English Wikipedia and 324 Simple English Wikipedia. The 118 that are only development texts are left to build.py; the other 909 are in the file.

| Exposure | Europe PMC | English Wikipedia | Simple English Wikipedia |
|---|---|---|---|
| Development texts (auto-excluded by build.py; listed for completeness) | 40 | 80 | – |
| Development candidates fetched, then rejected | 19 | 66 | – |
| Fix-check round 1 texts (labelled) | 20 | 40 | – |
| Round 1 candidates fetched, then rejected | 7 | 26 | – |
| Fix-check round 2 texts (labelled) | 20 | 40 | – |
| Round 2 candidates fetched, then rejected | 13 | 21 | – |
| Study 3 texts (part of the 842-text round-2 equivalence check) | – | 50 | 50 |
| Study 1 CLEAR excerpts citing a Wikipedia URL | – | 274 | 274 |

Some sources have more than one exposure; the inventory lists each one. Development plus the two rounds give exactly 240 distinct labelled sources, and the three sets are disjoint. The 146 rejected candidates are all distinct from those 240.

- **Normalised identifiers (v1, historical).** `build.read_exclusions` on the v1 file gives 2,801. Together with the development manifest's 440 that made 3,232, with 9 shared. The frozen file gives 3,132 and 3,563 (see the addendum).
- **Identities covered.**
  - Europe PMC: PMCID, the Europe PMC article URL, the full-text XML URL, DOI and title. For rejected candidates, the DOI and title come from the 2026-10-16 pool cache.
  - English Wikipedia: `pageid:N` where it is known, every observed canonical and requested title, the `/wiki/` URL, and every observed revision as an oldid URL. No source had more than two revisions, so the `url` and `revid` slots hold them all.
- **Self-check (passed, 0 failures).** For each of the 120 development texts, the 120 fix-check texts and the 909 union records, `build.exclusion_overlap([record], read_exclusions(file) | dev_refs)` is non-empty and all of the record's `text_refs` are in the set. Every observed alias of every source (all titles, revisions, page id, PMCID, both URLs and DOI) is in the set too.

## How it was found

1. I read the exclusion code in build.py, to see which forms it matches and when:
   - Europe PMC: PMCID, article URL, full-text URL, DOI and title, before fetching.
   - Wikipedia: the pool title before fetching; page id, canonical title and current revision URL after.
2. I read the round 1 and round 2 collect records: texts, collection log and fetch journal. Every fetch that was not selected was a logged rejection (licence not CC BY/CC0, too short, or a humour essay).
   - I cross-checked the private raw caches against the fetch journals, file for file.
   - I listed the five archive tars: their raw file sets, texts.jsonl and fetch journals equal the live round directories. There are no superseded or extra rounds, and round_registry.jsonl has only the two.
3. I compared the development raw cache with the development selection: 19 PMCIDs and 66 Wikipedia pages were fetched but rejected. The 0.4.0 rebuild cache and the scratch copy are byte-identical to it.
4. I swept `.cache`, `docs`, `scripts`, `tests`, `src` and `lexinspect-private` for PMCIDs and page ids, and accounted for every hit. Harness dry runs, the 0.4.0 pilot and the 16 Oct pilot all use the 120 development texts. The rest were pool listings or synthetic test ids.
5. I checked Studies 1, 2, 3 and 5:
   - Study 3 has 50 English plus 50 Simple English Wikipedia texts at pinned revisions.
   - Study 1's CLEAR corpus has 548 Wikipedia excerpt URLs (549 rows).
   - Study 2 has none.
   - Study 5's CEFR-SP sentences come partly from Wiki-Auto but carry no article identifiers.

The inventory's `not_excluded` section lists what was judged not to need exclusion, each with a reason:
- the pools themselves
- Gutenberg and ELLIPSE texts
- the 4 constructed fixtures
- the 418 constructed, audit-derived or guidelines test sentences
- the constructed audit probes
- the synthetic ids
- the made-up pilot dry-run items
- Studies 2 and 5

## Simple English Wikipedia

Simple English Wikipedia is a different site. Its page ids and revisions say nothing about English pages, so the records have no `revid` field (build.py would turn it into an en.wikipedia oldid URL) and use a `simplewiki:` source id. The titles are kept, so build.py's title check also skips an English article with the same title.

I recommend keeping these titles, to be conservative: Study 3 paired each Simple text with its English counterpart on the same topic, so the same title points at closely related content. Where the English counterpart has a different title, it has its own English record.

## Open questions for the maintainer (v1, historical; resolved in the addendum below)

1. **Study 1 CLEAR is the biggest call.** I included it to be conservative, but CLEAR was only used for readability, never in Study 4 fix development, so the contamination risk is negligible.
   - The cost: 117 of the 1,001 cached Level-3 Vital titles are excluded only because of Study 1 (47 through English URLs, 70 through Simple-title aliases), mostly core science and history.
   - Overall, 203 Vital titles are excluded: 40 development, 42 rejected candidates and fix-check, 4 Study 3, 117 Study 1. Essays lose 186 of 2,190, none of them because of Study 1.
   - Dropping the 541 records whose only exposure is `study1_clear_excerpt` would restore those 117 titles. Please decide, and state the decision in the prereg.
2. **317 English records are title-only** (Study 3 and CLEAR pages without a local page id). A page renamed since it was exposed could slip through if the pool lists only its new title. A one-off API lookup (title to page id, following redirects) before Stage 1 would close this; I did not do it because this task allowed no network access.
3. **Rejected candidates are included** (146 sources: licence, length or humour rejects). They were never sampled or labelled, but eligibility can change (for example, development rejects "Genghis Khan" and "Nile" were too short in October 2026). Keep or drop?
4. **PMIDs and PMC version ids are not recorded locally**, and build.py does not match them.
5. **The pools are the 2026-10-16 cache.** If the evaluation build refreshes them, check the overlap again against the new pool.
6. **Freeze.** Record this file's SHA-256 in the prereg and freeze file, and pass it unchanged through `--exclude-texts`. Any edit after a decision above means a new hash.

## Addendum, 2026-10-21: page ids, and the decisions on the open questions

**Page ids.** 317 English Wikipedia records matched by title only. Their page ids were looked up through the public Wikipedia API on 2026-10-21. The responses are in `pageid_lookup/`, and `lookup.json` is the parsed result.

- All 317 titles resolved, with no missing page.
- 14 titles now redirect to a renamed page, so a title-only match would have missed them.
- `tools/add_pageids.py` appends 331 plain alias lines to the v1 records, which are otherwise unchanged: 317 `pageid:N` lines and the 14 current titles. `read_exclusions` reads both forms.
- The v1 file is kept as `exclusions_v1_before_pageids.jsonl`.

| File | SHA-256 |
|---|---|
| `exclusions.jsonl` (the frozen file: 909 records + 331 alias lines) | `477f2197ce00e402441d810c4825e6d98517be4fa1e50d59ee2d4c0800f9b263` |
| `pageid_lookup/lookup.json` | `f19442526f3939306c73a59f5eeaf668994e61af9e6982f1fafd4ecfb76f7ba1` |

`build.read_exclusions(exclusions.jsonl)` gives 3,132 normalised identifiers. With the development manifest's 440, the union holds 3,563.

**Decisions, by the maintainer's session; reviewed with the Stage-1 package.**

1. **The Study 1 CLEAR excerpts stay excluded.** They were never used in Study 4 development, but excluding them costs little: about 800 eligible Level-3 Vital titles remain for 40 general texts.
2. **The fetched-then-rejected candidates stay excluded.** The registered exclusion rule covers every text "collected or inspected", and these were downloaded.
3. **PMIDs:** none are recorded locally, and `build.py` doesn't match on them. Europe PMC texts are matched on PMCID, both URLs, DOI and title.
4. **The pools:** the evaluation build uses the 2026-10-16 pool snapshot. A byte copy of `.cache/validation/study4/raw` is made into the evaluation build's own cache, with no `--refresh`. The development cache is never written to. If the pools were ever refreshed, the overlap check would be rerun on the refreshed pools.
