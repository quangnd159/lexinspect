# Study 4: archive inventory and access arrangements

**Draft for the Stage-1 review; the access arrangement is the maintainer's to confirm.**

**Date:** 2026-10-21. The inventory was surveyed on this date from the repository, the local caches and the private archive. No file was changed.

**Applies to:** the development and fix-check material of Study 4, and the 0.4.0 common development pilot. It fulfils the promise in [`study4-fix-check.md`](study4-fix-check.md), "What is not public", that the precision-study registration "will state any access route and any remaining restrictions".

**What this file contains:** paths, counts, sizes, file types, identifiers, licence names and SHA-256 values. It quotes no source text, PHRASE List gloss, example or sense inventory, guideline text or label note.

## 1. Summary

- **Public now:** code, protocols, rulings, receipts, acceptance results, hashes, the effects report, the pilot design and results, and the exclusion manifests. These let a reader check what was decided and authenticate the private files. On their own they don't let anyone recompute a gate or a pilot quantity.
- **Restricted:** the full packages. They hold three kinds of material that the maintainer can't release on their own terms:
  - copies of the source texts (Creative Commons, per text);
  - PHRASE List material (no open licence; permission pending);
  - model transcripts, which quote both.
- **The gap and the proposed fix:** a text-free release of memberships, frames and labels (tier 2 in section 7) would let an external methodologist recompute the gates and the pilot quantities. It doesn't exist yet.

## 2. Licences and permissions

### Source texts

Each text's licence is recorded in its collection manifest (`texts.jsonl`, field `licence`). The collector accepts a Europe PMC article only when its JATS permissions give CC BY, CC0 or a US public-domain statement. It rejects every other Creative Commons licence, including NC, ND and SA (`build.jats_licence`; tested in `fixcheck/test_r5.py`). English Wikipedia text is recorded as CC BY-SA 4.0.

| Set | Texts | Europe PMC | English Wikipedia | Manifest (SHA-256) |
|---|---:|---|---|---|
| Development (0.3.2 build; reused byte-identically by the 0.4.0 rebuild) | 120 | 40: 39 CC BY 4.0, 1 CC BY 3.0 | 80 CC BY-SA 4.0 (40 general, 40 argumentative) | `.cache/validation/study4/texts.jsonl`, `5dba40cc…` (pinned in the prereg) |
| Fix-check round 1 | 60 | 20 CC BY 4.0 | 40 CC BY-SA 4.0 | `round1/collect/texts.jsonl`, `e517be6a…` |
| Fix-check round 2 | 60 | 20 CC BY 4.0 | 40 CC BY-SA 4.0 | `round2/collect/texts.jsonl`, `50679c97…` |

- **No text has an NC or ND licence.** None is CC0 or public domain either.
- **No Simple English Wikipedia text is a Study 4 text.** Simple English Wikipedia appears only as identifiers in the exclusion manifests (Study 1 and Study 3 sources).
- **Attribution.** Each manifest record holds the title, the authors (Europe PMC), journal, DOI, PMCID or page id, URL and licence. For Wikipedia the URL is a permanent revision link (`oldid`). That is enough for CC BY and CC BY-SA attribution.
- **Share-alike.** Any published file that includes Wikipedia excerpts, such as item contexts, must itself be released under CC BY-SA 4.0. This is already noted in the build manifest's `publication_note`.

### Other material

| Material | Owner and terms | Status |
|---|---|---|
| PHRASE List entries, glosses, examples and the sense inventory (`phrase_sense_inventory.md`, v2.1, `a761f159…`) | Martinez & Schmitt (2012). No stated terms of use and no open licence (`src/lexinspect/data/LICENSE.md`). | Redistribution permission pending: Schmitt agreed on 2026-10-16; Martinez has not yet answered. |
| Guidelines (`docs/validation/study4-guidelines.md`, v3.2, `276d35e8…`, 63,682 bytes) | The maintainer's own text, but it embeds PHRASE material. | Follows the PHRASE permission. The file is gitignored (`.gitignore` line 53). |
| Model labels and session transcripts | Outputs of Claude Sonnet 5.5, GPT-6.1-Sol and DeepSeek V4.1 Flash, made under the maintainer's accounts. The labels' `note` fields and the transcripts quote source text, and transcripts quote the guidelines and the inventory, which the sessions read in full. | See section 5 for which fields are text-free. Claude transcripts also carry the account's email address (`study4-pilot040/LAUNCH.md`), and all transcripts carry local paths. |
| Code (`scripts/validation/study4_precision/`, `src/`) | The maintainer. MIT, which covers the code only (`LICENSE`). | Public. |
| Protocols, rulings and reports in `docs/` | The maintainer. | Public. No licence is stated for the documents; the maintainer may want to add one (for example CC BY 4.0). |

## 3. Inventory

### 3.1 Public: the repository

| Path (under `docs/validation/` unless stated) | Contents | Integrity record |
|---|---|---|
| `study4-preregistration.md`, `study4-fix-protocol.md`, `study4-fix-protocol-clarifications.md`, `study4-fix-check.md` | Protocols and the fix-check write-up | git history |
| `study4-fix040/` (51 tracked files) | Runbook, harness rulings and audit dispositions, candidate ledgers, delivery spec, manifest ledger, round registry. Per round: `accept/` (acceptance, registration, ledger components), `collect/` manifests (command, execution, freeze record, `manifest_collect.json`, `manifest_plan.json`), `receipts/`. Round 2 also has the narrowing check and disposition, and `sensitivity/`. | `receipts/primary.json`, `retry.json` and `flash.json` hold the SHA-256 of every package part (assign, candidate, collect, diff, replay, run, sample) and of the labels. `receipts/private_archive.sha256` holds the archive tars. `manifest_collect.json` lists the bytes and SHA-256 of every text file. |
| `study4-pilot040/` (5 files) | Plan, launch record (with finding F1), results, the proposed F1 correction, `selection.json` | `selection.json` (21 build files); the `RESULTS.md` hash table (10 label and analysis files) |
| `study4-exclusions/` (17 files) | Exclusion manifest (`exclusions.jsonl`, 1,241 lines, `477f2197…`), the pre-page-id version, inventory, page-id lookup, builder tools | prereg; README |
| `study4-development-effects.md` and `.json` | Development and fix-check effects report | git history |
| `study4-freeze.json` (untracked draft) | Stage-1 freeze manifest; the deposit fields are empty | becomes the registered record |
| `scripts/validation/study4_precision/` | Build, sampling, analysis, simulation, the fix-check harness (`fixcheck/`) and the pilot launcher and screen (`pilot040/`) | git; tag `v0.4.0` |

**Gitignored files in the working tree.** Each round's `study4-fix040/round*/collect/` also holds `collection.json`, `execution.lock`, `fetch_journal.jsonl`, `texts.jsonl` and `texts/T001–T060.txt` (1.8 MB per round). These are kept out of git on purpose (`.gitignore` lines 46–51). The same files are inside the round's labelled tar. `texts.jsonl`, `collection.json` and `fetch_journal.jsonl` hold no text bodies: they are attribution metadata, the selection log and the fetch log.

### 3.2 Private archive: `lexinspect-private/study4-fix040/` (3.8 GB)

| Path | Contents | Files, size | Integrity record |
|---|---|---|---|
| `archive/round1-prelabel.tar` | Round-1 package before labelling: assign, candidate, collect, diff, materials, raw, replay, run, sample | 543 MB | `round1/receipts/private_archive.sha256`: `0d9129b2…`, matches |
| `archive/round1-labelled.tar` | The above plus labels, sessions, transcripts, verify | 577 MB | `f6b90123…`, matches |
| `archive/round2-prelabel.tar` | Round 2, as above | 552 MB | `round2/receipts/private_archive.sha256`: `d1f2987f…`, matches |
| `archive/round2-labelled.tar` | Round 2, as above | 577 MB | `e30afd83…`, matches |
| `archive/round1-labelled.INCOMPLETE-missing-collect.tar` | A superseded first attempt. It has no `collect/`, and `tar -t` reports it truncated. | 575 MB | No receipt. SHA-256 `b1485d2d…`. Kept as history; not used. |
| `round1/`, `round2/` | The unpacked packages (see the next table) | 510 files, 547 MB; 552 files, 552 MB | receipts; `materials/SHA256SUMS`; `sessions/*/deliveries.jsonl` |
| `post_decision_events/` | Transcripts and rewritten working copies from old delegated tasks that resumed on 2026-10-19, after both decisions were registered, with a README | 26 files, 17 MB | `SHA256SUMS`, 24 entries, all OK |
| `tools/` | The maintainer's launch and access-review scripts (`run_*_strict.py`, `review_*.py`) | 18 files, 72 KB | none |
| `pinned-dec79bc/` | A `git archive` export of commit `dec79bc0…` (tree `425ee29c…`) used as the pinned baseline | 5,231 files, 126 MB | `PINNED_COMMIT.json`, including the `uv.lock` SHA-256 |

**Per-round folders** (files and size: round 1; round 2):

| Folder | Contents | Round 1 | Round 2 | Holds text? |
|---|---|---|---|---|
| `materials/` | Guidelines and the PHRASE inventory, with `SHA256SUMS` (both OK) | 3, 84 KB | 3, 84 KB | Guidelines and PHRASE |
| `raw/` | Download cache: Europe PMC XML, Wikipedia API JSON, candidate pools | 115, 9.6 MB | 116, 9.9 MB | Source text |
| `run/` | Hit frames for each configuration (baseline, pinned baseline, complete candidate, each family), logs, run manifest | 49, 404 MB | 49, 413 MB | Item payloads |
| `diff/` | Baseline-to-candidate links per configuration | 28, 85 MB | 28, 86 MB | No |
| `sample/` | `units.jsonl` (3,215; 2,314 distinct payloads with memberships), selection, decision plan, operational power | 5, 3.4 MB | 5, 2.5 MB | `units.jsonl` payloads |
| `assign/` | `items.jsonl` and `key.jsonl` (one line per payload), orders, batches, retry and adjudication manifests | 42, 6.9 MB | 40, 5.1 MB | Items and batches |
| `labels/` | A, B and adjudicator labels: pass 1, retry, merged, delivery checks | 10, 1.4 MB | 12, 1.0 MB | `note` fields |
| `sessions/` | Launch logs, prompts, delivered labels, delivery records (`deliveries.jsonl`: labels and transcript SHA-256 per session), session exports | 129, 6.2 MB | 115, 4.8 MB | Prompts and exports |
| `transcripts/` | Text exports of every labelling session, access-review rulings | 28, 24 MB | 24, 18 MB | Yes |
| `candidate/` | Snapshot of the candidate source tree | 79, 6.7 MB | 102, 6.9 MB | No (code) |
| `replay/`, `verify/`, `accept_check/` | Replay of the baseline, verification and the package check before acceptance (round 1 also keeps a superseded check) | 2 + 2 + 2 | 2 + 2 + 2 | No |
| `preflight/` | Round-2 preflight before freezing | – | 29, 3.7 MB | Partly (dry-run items) |
| Top-level logs and scans | Stage logs, `allowed.txt`, staged and whole-set access scans, transcript reviews (round 2) | – | – | Scan excerpts may quote paths and notes |

### 3.3 Private archive: `lexinspect-private/study4-pilot040/` (31 MB)

| Path | Contents | Files, size | Integrity record |
|---|---|---|---|
| `selection/build/` | The 0.4.0 development rebuild, archived before labelling: `texts/` (120), `texts.jsonl`, `hits.jsonl` (42,454 hits), `items.jsonl` and `key.jsonl` (1,300), frame, orders, population, batches (A, B, maintainer), build log | 143, 14 MB | `SHA256SUMS`, 142 entries (120 per-text hashes), all OK; 21 of them are public in `selection.json` |
| `sessions/A`, `B`, `C` | 10 sessions (A: 4 primary + 1 retry; B: 4; C: 1 adjudication), each with labels, event stream, stderr, the provider's session record and `session.json`; `launch_log.jsonl`; the `check_sessions.py` screens | 61, 14 MB | `session.json` (SHA-256 of every input and archived file) |
| `labels/` | A batch, retry and merged; B batch; adjudicator; validation files; `needs_adjudication.txt` | 14, 388 KB | `RESULTS.md` hash table; 5 entries rechecked today, all match |
| `analysis/` | `pilot.json`, `pilot.md`, `flash_diagnostics.json` | 3, 284 KB | `RESULTS.md` |
| `probes/` | One or two context probes per role, on dummy files | 18, 340 KB | `SHA256SUMS`, 17 entries, all OK |
| `dryrun/` | Dry run on two made-up items, one session per role | 17, 1.4 MB | `session.json` per session |

### 3.4 Local caches (gitignored, under `.cache/validation/`)

| Path | Contents | Files, size | Integrity record | Status |
|---|---|---|---|---|
| `study4/` | The original development set and the 0.3.2 build (2026-10-16): `texts/` (120), `texts.jsonl`, `hits.jsonl` (44,529), `items.jsonl` (1,300), key, population, manifest, `human_labelling.html`, a copy of the PHRASE inventory, `raw/` (264 files: 59 Europe PMC, 146 Wikipedia, 22 pools, 37 temporary) | 393, 41 MB | `texts.jsonl` pinned `5dba40cc…`. There are no separate per-text hashes, but the texts are byte-identical to the archived 0.4.0 copies (`selection.json` check), whose hashes are in `selection/build/SHA256SUMS`. | Restricted: texts and PHRASE |
| `study4_v040/` | The 0.4.0 rebuild; `raw/` is a byte copy of the development cache | 410, 42 MB | The archived copy is `study4-pilot040/selection/build/` | Restricted |
| `study4_pilot/` | The 16 Oct 0.3.2 pilot: labels, raw session outputs, retry manifests, adjudicator-selection files (`adj_r5/`), plan, log and disagreement review | 47, 2.4 MB | `frozen_inputs.sha256` covers the guidelines and inventory only. The labels have no contemporaneous public hash; see section 4. | Restricted: the notes quote text |
| `study4_fix040/` | Fix-work material: implementation, harness and audit reports and dispositions; Sol reviews; harness dry runs (2.4 GB); equivalence runs (355 MB); a round-2 working area (10 GB); a harness snapshot (1.6 GB); the final audit | 9,996, 14 GB | None as a set. The registered inputs are the archived packages, not these. | Restricted working material. The public dispositions and rulings summarise it; the original review reports are not all published (`study4-fix-check.md`). |
| `study4_scratch/sim_final/` | The 0.3.2-calibrated historical simulation | 12, 764 KB | `result_hashes.sha256`; three hashes in `study4-freeze.json` | Text-free; publishable |
| `study4_scratch/sim040/` | The 0.4.0-calibrated registered simulation: frozen sources, inventory, run and merged results, `SUMMARY.md`, `tail_table.txt`, rate check | 16 files | `result_hashes.sha256`; hashes in the prereg and `study4-freeze.json` | Text-free; publishable |
| `study4_scratch/` (the rest) | Handoffs, reviews, prototype builds and copies of the development texts and raw cache (`devcopy/`, `dev032*/`, `rawcopy/`, `src032/`), practice pages | ~300 files | none | Working material; the copies hold text |

**Not in the archive.** The delivered session transcripts of the 16 Oct pilot (A `-r2`, B, the adjudicator) were not copied into the private archive or a cache. As far as this survey found, they exist only in the providers' local session stores on the maintainer's machine; the F1 rescreen read the Codex sessions there (`study4-pilot040/CORRECTION_F1.md`).

- `post_decision_events/resumed_s4pilot_A_0N_*.jsonl` are copies of four A session files that resumed on 2026-10-19. Each has 18 records dated 2026-10-16. That fits the first A launches, which failed at start, rather than the delivered `-r2` sessions; this was not checked further.
- No OpenCode session record of the 16 Oct adjudicator runs was found (`LAUNCH.md`, F1).

## 4. Label sets and their provenance

**No label is reused.** No label from the 16 Oct 0.3.2 pilot or from either fix-check round is used for the 0.4.0 pilot or for the evaluation. The 0.4.0 pilot relabelled every item in fresh A and B sessions (`study4-pilot040/PLAN.md`, section 3; `selection.json`: `"labels": "none exist; no reuse"`). The reason is finding F1 (`LAUNCH.md`): every earlier session was started as a delegated task of a T3 Code thread whose project is this repository, so it inherited repository context. Reuse would carry that deviation forward. The evaluation draws new texts under its own seed and its labels don't exist yet.

| Label set | Roles and models | Dates (UTC) | Launch route | Context restrictions, as recorded | Records |
|---|---|---|---|---|---|
| 16 Oct pilot (0.3.2, development texts) | A: Claude Sonnet 5.5, effort high. B: GPT-6.1-Sol, reasoning high. Adjudicator: DeepSeek V4.1 Flash, high (selected by the r5 rule). Also a GPT-6-Sol dry run, never used. | 2026-10-16 | T3 `delegate_task`. A's first launches failed on a rate limit and were relaunched on the second Claude account (`-r2`). | Working folders in `/tmp/s4pilot/` holding only the three files. **But (F1):** A received a git-status snapshot and the maintainer's `~/.claude/CLAUDE.md`. B ran with the repository as its working directory, and its context also carried T3's orchestration instructions. The adjudicator was launched the same way, but no record survives to check. | A 1,300 (5 retried), B 1,300, adjudicator 284 (86 disputed plus the calibration set) |
| Fix-check round 1 (60 new texts) | A: Sonnet 5.5. B: GPT-6.1-Sol. Adjudicator: Flash. | 2026-10-17, 17:33–17:51 | T3 `delegate_task`. Ten first A launches on the primary Claude account were refused and superseded; they resumed on 2026-10-19 (`post_decision_events/`). | Batch directories under `$TMPDIR`. **But:** A got the git-status snapshot (with the candidate branch name) and `CLAUDE.md`. B and the adjudicator ran with the repository as working directory. The rescreen found no file access outside the batch directories (`CORRECTION_F1.md`). | 3,215 payloads. A 3,215 (39 retried), B 3,215, adjudicator 210 lines for 180 items (174 valid). 10 + 10 primary, 1 retry and 2 adjudicator sessions. |
| Fix-check round 2 (60 new texts) | as round 1 | 2026-10-18 23:49 to 2026-10-19 00:11 | T3 `delegate_task` | As round 1. A's snapshot named the narrowed candidate. The deviation is analysed in `round2/BLINDING_DEVIATION_SENSITIVITY_PLAN.md` and `sensitivity/`. | 2,314 payloads (1,735 metadiscourse, 579 PHRASE). A 2,314 (25 retried), B 2,314 (1 retried), adjudicator 99. 8 + 8 primary, 1 + 1 retry and 2 adjudicator sessions. |
| 0.4.0 pilot (development texts, new seed 473840911) | A: Sonnet 5.5, effort high. B: GPT-6.1-Sol, reasoning high. C: Flash, variant high. | 2026-10-20, 16:44–16:57 | Direct command-line launch by `pilot040/launch.py` | A fresh directory outside any git repository; a cleared environment; per-role tool and config limits (`LAUNCH.md`). Probes and a dry run first. The `check_sessions.py` screen found no marker in any session. | A 1,300 (4 retried), B 1,300, adjudicator 84 |

**SHA-256 of the 16 Oct pilot labels.** These were computed on 2026-10-21 for this inventory. They are not contemporaneous; the only contemporaneous hash is the adjudicator file's, in the private pilot log, and it matches.

| `.cache/validation/study4_pilot/` | SHA-256 |
|---|---|
| `labels_A_original.jsonl` | `e33510cbf4e836ff1866394b4c8115be251059f6e3fa6a7957121e651a33bfa7` |
| `labels_A.jsonl` (after the retry merge) | `53acd4a96cde4aa66ee78e9fa2c563809260dcc39b8aed3bac2242ce95276103` |
| `labels_B.jsonl` | `21078903be63966401e23007b3209b907a69c047fe7f9e92d05c6608e8feb7ff` |
| `retry_A.jsonl` | `dc7c46e5541a4ef0525ef8103b0080df586fc69ed7088a48da12034ec0c886cb` |
| `needs_adjudication.txt` | `eaca38000318024d7a8bf9e185297f03c3bf6bf1f629b2a52d5ec69667d7b2fd` |
| `raw/DSF2_flash.jsonl` (adjudicator) | `9f3297a9d5b9baa30c6b7c26669ed194e5bb5187f7b95982d7ad2f9016cf97ea` |
| `raw/G6S_dryrun.jsonl` (not used) | `604c7bf7f5b77e0769f94885e522b91d15471e4792b773455f0c2210d8f15b21` |

## 5. What can be published without text

| File type | Text-free fields | Fields that carry text or PHRASE material |
|---|---|---|
| Text manifests (`texts.jsonl`) | All fields: text id, source, PMCID or page id, DOI, URL or `oldid`, revision id and timestamp, licence, register, discipline, length, hashes, title, authors | none (title and authors are attribution) |
| Hit frames (`run/frames/*.hits.jsonl`), `hits.jsonl` | `hit_id`, `text_id`, `source_id`, `text_sha256`, `module`, `config`, `span`, `sentence_span`, `head_span`, `token_index`, `occurrence`, the claim's category or PHRASE rank, `payload_sha256` | `payload` (sentence context and claim); `raw`; `surface` (the matched words) |
| Units, keys and memberships (`units.jsonl`, `key.jsonl`) | `payload_sha256`, memberships (frame, role, row, substratum, inclusion), occurrence locators (source id, text hash, offsets), category, stratum, weights | `payload`; the matched surface in occurrence locators |
| Items (`items.jsonl`, batches) | `id`, `module`, `marker` | `context` (source text). For PHRASE, `claimed` holds the expression, sense, example and other senses. |
| Labels | `id`, `label`, `alt_category` | `note` |
| Diff links, orders, assignments, decision plans, acceptance, analysis outputs | all | none found |
| Session records and transcripts | launch metadata, times, exit codes, hashes | the rest |

**The matched surface** (a marker or PHRASE expression, a few words) is a short quotation of the source. Releasing it is the maintainer's call. Without it, offsets and a refetched text recover it.

## 6. Can the texts be refetched by identifier?

**Not byte-for-byte reliably.** Every manifest records an identifier and a retrieval date, but neither source guarantees the same bytes on a later fetch.

- **Europe PMC.** The PMCID, DOI and the `fullTextXML` URL are recorded. No article version is recorded, and the endpoint serves the current version, which can change after corrections or reprocessing. For the fix-check rounds, the SHA-256 of each downloaded XML file (`collection.json`, `raw_files`; `fetch_journal.jsonl`) and of each extracted text (`texts.jsonl`; public in `manifest_collect.json`) let a refetch be checked. The development set records no raw-XML hashes. Its per-text hashes are only in the private `selection/build/SHA256SUMS`.
- **Wikipedia.** All 160 Wikipedia texts record the revision id (`revid`, or `oldid` in the URL; rounds 1 and 2 also record its timestamp). The exact revision is therefore identifiable. But the collector took plain text from the TextExtracts API (`prop=extracts`, `explaintext`), which serves only a page's current revision. Re-extracting an old revision needs another route, such as parsing the `oldid`, and that is unlikely to reproduce the same bytes. Rendering changes in templates and modules can also alter output for the same revision.
- **Consequence.** Identifiers let a methodologist obtain essentially the same texts, and hashes let them detect any difference. Exact recomputation of the frames from refetched texts can't be promised. Exact verification needs the archived copies (tier 3), or the frames themselves (tier 2).

## 7. Access arrangement — DRAFT, for the maintainer to confirm

| Tier | What | Terms |
|---|---|---|
| **1. Public now** | Everything in the repository: code, protocols, rulings, receipts, acceptance results, hashes, the effects report, the pilot plan, launch record, results and selection hashes, the exclusion manifests | As published |
| **2. Publishable without text** (the maintainer's decision) | A text-free export of each set, with the fields in section 5: text manifests (attribution metadata), hit-frame identities, sampling memberships, keys and weights, diff links, orders, labels without notes, adjudication lists, and the SHA-256 of every file it was derived from. Texts are re-obtainable by identifier, with the limits in section 6. | Open; CC BY 4.0 suggested. It contains no CC BY-SA text. |
| **3. Restricted: on request, for verification only** | The full packages: the archive tars, the unpacked rounds, the pilot selection and sessions, the 16 Oct pilot cache. These include copies of the source texts (licensed per text, with the attribution recorded in the manifests) and the transcripts. | For an independent methodologist, for verification only, with no redistribution. Access is a supervised share or a time-limited private transfer, logged in this folder. |
| **4. Withheld until the PHRASE List authors agree** | Glosses, examples and the sense inventory; the guidelines (`276d35e8…`) | Published with the registration or the results once permission is given. Their SHA-256 values are already public, so the released files can be checked against them. |

**A conflict between tiers 3 and 4 to resolve.** The full packages also contain PHRASE material: `materials/` (the guidelines and inventory), the `claimed` field of every PHRASE item and frame payload, and the transcripts, which read both files in full. The maintainer needs to choose one of two options:

- **(a)** Until permission, tier-3 releases leave out `materials/` and the PHRASE fields. The archive tars can then be checked only part by part, against the receipts.
- **(b)** Tier-3 access is limited to inspection in a supervised session, with no copy leaving the maintainer's machine, until permission.

**What an external methodologist can recompute at each tier:**

| Tier | Can recompute or check | Cannot |
|---|---|---|
| 1 | That the published decisions follow from the published registered rules; the simulation code and design; the exclusion builders; that any later-released file matches its public hash | Any gate or pilot quantity. The exclusion union can't be recomputed either, because it also needs the development manifest's identifiers. |
| 2 | **The fix-check gates**, for both rounds: memberships, frame identities, diff links, and A, B and adjudicator labels, with the reference built by the registered rule. This includes the sensitivity analysis without A and the worst-case handling of unresolved items. **The 0.4.0 and 0.3.2 pilot quantities and the simulation recalibration:** keys with strata and weights, plus labels. **Agreement and adjudicator diagnostics. The exclusion union**, from the development identifiers. | Whether a label is right for its text (needs the text and the guidelines); rerunning the matchers. The frozen `accept.py` reads the full package and checks file hashes, so recomputing from tier 2 needs a short text-free recompute script. That script doesn't exist yet. |
| 3 | Everything in tier 2 with the frozen code at the pinned commit; rerunning the matchers on the archived texts; the transcript access reviews and the F1 rescreen; the post-decision events | Judging PHRASE items as the labellers saw them, under option (a) |
| 4 | Relabelling items under the frozen guidelines and inventory; checking the guideline and inventory hashes | – |

## 8. Open points

1. **PHRASE permission.** Martinez's answer is pending (Schmitt agreed on 2026-10-16). The conflict between tiers 3 and 4 is open until then.
2. **The tier-2 export and recompute script** don't exist yet. If they are made, their hashes and the commit that builds them belong in `study4-freeze.json`.
3. **Development per-text hashes** are only in the private archive. Publishing the 120 hashes (text-free) would let refetches of the development texts be checked publicly, as the rounds' texts already can be.
4. **The 16 Oct pilot transcripts** are only in the providers' local stores. If they are to be retained, they should be copied into the private archive with a `SHA256SUMS`. The section-4 label hashes are not contemporaneous.
5. **The documents in `docs/`** have no stated licence.
6. **Personal data in transcripts:** the account's email address in Claude transcripts, and local paths in all of them. Remove or accept these before any tier-3 transfer.
7. **The simulation outputs** (`sim_final/`, `sim040/`) are text-free but only in the local cache. They are intended as files of the Stage-1 deposit.
