# Study 4: text-free export (tier 2)

**Draft for the maintainer; not yet committed or registered.**

**Date:** 2026-10-21. Built by `scripts/validation/study4_precision/textfree/export.py` from the private archive and the local caches, which were read and not changed.

**What it is for.** It is the access route for an external methodologist (tier 2 in [`study4-archive.md`](../study4-archive.md), section 7). From this folder and the public repository alone they can recompute, with the frozen project code:

1. the 0.4.0 common development pilot (`study4-pilot040/RESULTS.md`);
2. the 0.3.2 development pilot of 16 October, as reported in the preregistration and in the RESULTS.md history line;
3. both fix-check gates (`study4-fix040/round{1,2}/accept/acceptance.json`);
4. the round-2 blinding sensitivity analysis and its control (`study4-fix040/round2/sensitivity/`).

**What it contains.** Identifiers, codes, offsets, strata, weights, sampling memberships, labels and hashes. It holds no source text, no matched words, no PHRASE List expression, gloss, example or sense wording, no guideline text, no label note, no prompt and no transcript (see "How the text was removed" and "Guard").

## Commands

```sh
# rebuild the folder from the private files (maintainer only); refuses if the guard finds text
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/export.py
# deterministic: rebuild in memory and compare byte for byte with this folder
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/export.py --check
# recompute everything from this folder and compare with the published values (exit 1 on any difference)
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/recompute.py [--json report.json]
# scan the folder for text (needs the private corpora; maintainer only)
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/guard.py
# tests
uv run --offline --no-sync python -I -m pytest scripts/validation/study4_precision/textfree/test_textfree.py
```

`recompute.py` needs only this folder and a checkout of the repository at the commit that adds it (the frozen code in `scripts/validation/study4_precision/` and the published documents it compares with).

## What recompute does

It turns the export back into a text-free "shadow package" in a temporary directory, then runs the frozen entry points on it unchanged:

- **Pilots:** `analyse.main` with its default options. It runs design validation, label validation, references, estimates and intervals, agreement and batch diagnostics. This is exactly how the private `analysis/pilot.json` was produced: run on the private files with the same arguments, it reproduces that file byte for byte (SHA-256 `f3aa1dd8…`, published in RESULTS.md).
- **Gates and sensitivity:** `fixcheck.accept.acceptance_of`. It runs label loading and validation, `refs_from_labels`, `frames_from_key` and `compute`, the same calls as the registered decision and `round2/sensitivity/run_sensitivity.py.txt`. S-B passes B's labels as A's.

**Bypassed:**

- `fixcheck.package.check_package`: it hashes every file of the full package, including texts and transcripts.
- The registry and runtime checks of `accept.main`.

The label-file SHA-256 values that `acceptance.json` reports are those of the private files. Recompute compares them with the source hashes recorded in `manifest.json`.

**Compared, and the result on 2026-10-21: 72 checks, 0 failed.**

| Target | Compared with | Result |
|---|---|---|
| 1. 0.4.0 pilot | Every figure in RESULTS.md: the expected phrase is built from the recomputed numbers and must appear verbatim. Also the whole recomputed analysis against `pilot040/reference/pilot_textfree.json`, the change-status diagnostics against `pilot040/reference/flash_diagnostics.json`, and A's retry merge. | identical |
| 2. 0.3.2 pilot | The preregistration's history, simulation-parameter, adjudicator and agreement sentences, and the RESULTS.md history line (.491/.622, 63 adjudicated, 2 unresolved; .836/.670, 8 and 0; 86 requests, 2 UNSURE; agreement .954/.973). Unrounded: .49140 and .83556. | identical |
| 3. Gates | Every computed field of `round{1,2}/accept/acceptance.json` (`a`, `components`, `decision_wording`, `labels`, `modules`, `procedure_problems`, `reference_sources`, `round`, `status`). Round 1 fails and round 2 passes, as registered. | identical |
| 4. Sensitivity | `S-B_acceptance.json` and `control_acceptance.json` in full, after checking both files against their `SHA256SUMS` | identical |

**Two notes on the comparison:**

- **Sub-stratum names in the published acceptance files.** These files name the baseline-success strata by their original sub-stratum names. The export uses codes instead (see below). Recompute pairs the published names with the codes in sort order, which the codes preserve, and requires each pair to have the same stratum and kind. Everything attached to the names is then compared exactly.
- **Package fields.** `package_check`, `acceptance_runtime`, `candidate`, `registry_entry`, `mode`, `production_eligible` and `mathematical_status` describe the package and the production run, not the arithmetic. They are not recomputed.

## What can't be recomputed from this folder

- **Whether a label is right for its item.** That needs the source text, the guidelines and the PHRASE inventory (tiers 3 and 4).
- **Rerunning the matchers, the frames or the sampling from the texts.** That needs the texts. The hit-frame identities that the gates use are in the keys' memberships, but the full per-configuration hit frames (`run/`, `diff/`) are not exported: the gates don't read them.
- **The package hash chain.** The receipts in `study4-fix040/round*/receipts/` authenticate the private files. This folder records each source file's SHA-256, so a later tier-3 release can be matched to it.
- **The PHRASE part of `pilot.json`'s `alt_categories`.** It counts claimed expressions against the senses or glosses given, so it is removed from the reference copy and not compared. The metadiscourse part is kept and compared.
- **The adjudicator selection of 16 October** (completeness 284/284, calibration agreement 193/200). The adjudicator's 198 calibration labels are in `pilot032/labels/adjudicator.jsonl.gz` (validated as `not_assigned`), but the calibration ids and scoring are not exported or checked.
- **The exclusion union.** `texts/development.jsonl` carries the development identifiers it needs, but recompute does not check it.

## How the text was removed

- **Fields dropped.**
  - Keys: `surface`, `marker_key`, `expression`, `also_possible`, `title`, `url`, `licence` and `source` (the last three are kept per text in `texts/`).
  - Items: everything but the id, the module, the claimed category, and for PHRASE the word counts of the claimed expression and of each other listed sense.
  - Label records: other metadata keys (batch, position, times).
  - Retry manifests: the `detail` field.
  - `orders.json`: its descriptive `note` string.
  - Text manifests: title, authors and journal.
- **Sub-stratum names.** A name such as `<stratum>|marker=<words>` embeds a marker or a PHRASE expression. It becomes `<stratum>|marker=m<NNN>`, numbered in the sorted order of all 50 original names across the four sets (31 are coded). `<stratum>|rest` is kept. Because the order is kept, every sort the frozen code does (`analyse.outcome_subs`, `accept.compute`) visits the sub-strata in the original order, so the results are bit-identical. The mapping is not published.
- **Label shapes** (`common.py` documents them in full). The frozen validator reads three text-bearing things: the note, the PHRASE alternative, and the item's claimed entry. Each is replaced by exactly what the validator's checks read:
  - `note_shape`: null, the note's word count, or, for an UNSURE note in the required form, the named readings (label or category codes) and the word count.
  - `alt_category`: metadiscourse codes are kept as written. A PHRASE value becomes `s<i>` (the item's i-th other listed sense), `e` (the claimed entry) or `g<j>` (the j-th distinct free gloss for that item within the set, so the same gloss gets the same token in every role's file). It is padded with `x` to the original word count and written in capitals exactly when the original was.
  - Line structure is kept, including blank, malformed and duplicate lines.

  **The proof.** For each of the 22 label files, `export.py` runs `analyse.validate_lines` on the real file and on its shapes and requires identical results: summary, valid ids and labels, problems, warnings and retry list. `recompute.py` rebuilds the records with `common.synth_line` and `common.pseudo_item`.
- **What remains is not text.** Payload SHA-256 values are hashes of whole sentence contexts. Offsets, token indexes, PHRASE ranks and K-bands are numbers. A rank identifies a PHRASE List entry only through the List itself.

## Files

Every `.jsonl.gz` is gzip of UTF-8 JSON lines with sorted keys, written with mtime 0 and no file name. Every `.json` is indented with sorted keys. Sizes are in `manifest.json`. In total, 47 files, 2.2 MB on disk and 9.9 MB uncompressed.

| File | Contents |
|---|---|
| `manifest.json` | For every file: description, byte size, SHA-256, line count, and the path and SHA-256 of each private or local file it was derived from. For label files, also the validator summary. Also the sub-stratum code scheme and the dropped fields. |
| `SHA256SUMS` | SHA-256 of every other file in the folder, this README included |
| `texts/development.jsonl` | The 120 development texts: `text_id`, `register`, `discipline`, `source`, `source_id`, `doi`, `url` (Wikipedia `oldid` link), `fulltext_url`, `revid`, `rev_timestamp`, `licence`, `retrieved`, `truncated`, `n_chars`, `year`, `text_sha256`. The SHA-256 values are of the archived texts (byte-identical cache copies, checked against `selection/build/SHA256SUMS`). They were private until now. |
| `texts/round1.jsonl`, `texts/round2.jsonl` | The 60 texts of each fix-check round: as above, plus `extracted_sha256` and `fixcheck_round`. Each source manifest was checked against `manifest_collect.json`. |
| `pilot{032,040}/key.jsonl.gz` | The 1,300 sampled items: `id`, `module`, `text_id`, `register`, `discipline`, `source_id`, `span`, `sentence_span`, `token_index`, `stratum`, `substratum` (coded), `N_sub`, `n_sub`, `weight`, `provenance`, `category`, `dimension`, `also_listed_as` (category codes), and for PHRASE `rank`, `k_band`, `multi_sense`, `has_also_possible` |
| `pilot{032,040}/items.jsonl.gz` | Item shapes: `id`, `module`, then `category`, or `expression_words` and `other_sense_words` |
| `pilot{032,040}/frame.json` | `N` and register counts per (coded) sub-stratum. For 0.3.2 this is `study4_scratch/dev032/frame.json`, whose key is byte-identical to the pilot's. |
| `pilot{032,040}/orders.json` | Seeds, orders and batch sizes per role |
| `pilot{032,040}/maintainer_sample_ids.txt` | The maintainer audit sample (ids only; no maintainer labels exist) |
| `pilot{032,040}/labels/A_original`, `A_retry`, `A`, `B`, `adjudicator` (`.jsonl.gz`) | Label shapes: `id`, `label`, `alt_category`, `note_shape`, one line per line of the source file. `A` is the merged file; recompute checks `merge_retry(A_original, A_retry, A_retry_ids) = A`. The 0.3.2 adjudicator file also holds the 198 calibration labels. |
| `pilot{032,040}/labels/A_retry_ids.txt`, `needs_adjudication.txt` | The retry manifest's ids; the adjudicator's assignment |
| `pilot040/reference/pilot_textfree.json` | `analysis/pilot.json` with `alt_categories.<role>.phrase` removed and the sub-stratum names coded; otherwise unchanged |
| `pilot040/reference/flash_diagnostics.json` | A byte copy of `analysis/flash_diagnostics.json` (text-free; SHA-256 published in RESULTS.md) |
| `pilot040/dev032_hits.jsonl.gz` | The 44,529 hits of the 0.3.2 development build: `module`, `text_id`, `span`, and `category` or PHRASE `rank` (for the change status) |
| `fixcheck/round{1,2}/key.jsonl.gz` | One line per label unit (3,215; 2,314): `id`, `module`, `category`, `payload_sha256`, `memberships` (`frame`, `role`, `row`, `substratum` (coded), `inclusion`, and for links `of` and `resolved`), `occurrences` (source id, text SHA-256, module, start, end) |
| `fixcheck/round{1,2}/items.jsonl.gz` | Item shapes, as above |
| `fixcheck/round{1,2}/selection.json` | `sample/selection.json` with the sub-stratum names coded: frame sizes `N` and `n`, selected rows, seeds, the baseline-success strata (`N_h`, `n_h`, selected rows), label-unit counts, input hashes |
| `fixcheck/round{1,2}/flash_ids.txt` | The adjudicator's assignment |
| `fixcheck/round{1,2}/labels/{A,B,adjudicator}.jsonl.gz` | Label shapes of the final label files that acceptance read |

## Provenance

Paths are relative to the repository or to the private archive root (`lexinspect-private/`). Files under `.cache/` are the maintainer's local caches. The 0.3.2 pilot files have no contemporaneous public hash except the adjudicator file's (`study4-archive.md`, section 4).

| Export file | Derived from | SHA-256 |
|---|---|---|
| `fixcheck/round1/flash_ids.txt` | `lexinspect-private/study4-fix040/round1/assign/flash/flash_ids.txt` | `36567cfd37678cd164bc428748cf35e4b0a056ece0794ec66a8ac608a52ae4a6` |
| `fixcheck/round1/items.jsonl.gz` | `lexinspect-private/study4-fix040/round1/assign/items.jsonl` | `c4a3a23fda8525f8130cd105549a7ef6c9508349d021573d9a8763e34bd06624` |
| `fixcheck/round1/key.jsonl.gz` | `lexinspect-private/study4-fix040/round1/assign/key.jsonl` | `fbb62df13087294b9206619e725bdfb4d188d61bb02ae0ed77a28f0f8574d246` |
| `fixcheck/round1/labels/A.jsonl.gz` | `lexinspect-private/study4-fix040/round1/labels/A.jsonl` | `0bfcd3ad6fc30fb738869ecd43562738afc7ea39a78d330869bdd0440e746662` |
| `fixcheck/round1/labels/B.jsonl.gz` | `lexinspect-private/study4-fix040/round1/labels/B.jsonl` | `04fac175f864cc951ccb36b4c14a07da8e35d680997e51ba419ad5deb48eec8b` |
| `fixcheck/round1/labels/adjudicator.jsonl.gz` | `lexinspect-private/study4-fix040/round1/labels/adjudicator.jsonl` | `1f57f688ba6099b95027d83f66e65fadc60a060dcca52f0597426b469f981ad4` |
| `fixcheck/round1/selection.json` | `lexinspect-private/study4-fix040/round1/sample/selection.json` | `6da078f58eb7719812fec95da23f4744c7706c26f5bae52fbde351d1798120e0` |
| `fixcheck/round2/flash_ids.txt` | `lexinspect-private/study4-fix040/round2/assign/flash/flash_ids.txt` | `5bff8a84745a5529fe0e88a449429de5661167e28df9e806869b0f0307f63735` |
| `fixcheck/round2/items.jsonl.gz` | `lexinspect-private/study4-fix040/round2/assign/items.jsonl` | `003acbba167ec1b99a2daa51f97105b4b50d180d1cd3da862b56bffc7f9180e2` |
| `fixcheck/round2/key.jsonl.gz` | `lexinspect-private/study4-fix040/round2/assign/key.jsonl` | `af3ce6d4527705113ae52ea722cb1410750a45f868aa2ead4f1b74cf8154a770` |
| `fixcheck/round2/labels/A.jsonl.gz` | `lexinspect-private/study4-fix040/round2/labels/A.jsonl` | `4e7634e4eb330b6073d2cd8dee1a4e31d9aadca4fd3f170758d26dda46966cfa` |
| `fixcheck/round2/labels/B.jsonl.gz` | `lexinspect-private/study4-fix040/round2/labels/B.jsonl` | `6b8a32167b41d9a98743da4fe3b69c96171b57327c779fe6c73b171e77ef8802` |
| `fixcheck/round2/labels/adjudicator.jsonl.gz` | `lexinspect-private/study4-fix040/round2/labels/adjudicator.jsonl` | `6f030e5d009b107d78e92941f4df912da80f6605841c3975e17489a62d6123ec` |
| `fixcheck/round2/selection.json` | `lexinspect-private/study4-fix040/round2/sample/selection.json` | `2c30bb7117a2e463c75d5b11dae8ad4ea78d64e137e16c11db77e5038e91a390` |
| `pilot032/frame.json` | `.cache/validation/study4_scratch/dev032/frame.json` | `c1d083d7aaf074746e5b685710e3dff3bfa389a9fcb6966298232218097bbf46` |
| `pilot032/items.jsonl.gz` | `.cache/validation/study4/items.jsonl` | `966a880676eb5782ba24fd720f05fb0cd883a13f81c7c41aa7754abd697c79e5` |
| `pilot032/key.jsonl.gz` | `.cache/validation/study4/key.jsonl` | `5796bc2acefdf99d557630e5c196ed4fb19816207aa34da250ebf7b273e1b655` |
| `pilot032/labels/A.jsonl.gz` | `.cache/validation/study4_pilot/labels_A.jsonl` | `53acd4a96cde4aa66ee78e9fa2c563809260dcc39b8aed3bac2242ce95276103` |
| `pilot032/labels/A_original.jsonl.gz` | `.cache/validation/study4_pilot/labels_A_original.jsonl` | `e33510cbf4e836ff1866394b4c8115be251059f6e3fa6a7957121e651a33bfa7` |
| `pilot032/labels/A_retry.jsonl.gz` | `.cache/validation/study4_pilot/raw/A_retry.jsonl` | `6505ccda9ee50a54812085ae1e8cb1266c45abfaa6d9e0a318f06b2b0bb55537` |
| `pilot032/labels/A_retry_ids.txt` | `.cache/validation/study4_pilot/retry_A_manifest.jsonl` | `dc7c46e5541a4ef0525ef8103b0080df586fc69ed7088a48da12034ec0c886cb` |
| `pilot032/labels/B.jsonl.gz` | `.cache/validation/study4_pilot/labels_B.jsonl` | `21078903be63966401e23007b3209b907a69c047fe7f9e92d05c6608e8feb7ff` |
| `pilot032/labels/adjudicator.jsonl.gz` | `.cache/validation/study4_pilot/raw/DSF2_flash.jsonl` | `9f3297a9d5b9baa30c6b7c26669ed194e5bb5187f7b95982d7ad2f9016cf97ea` |
| `pilot032/labels/needs_adjudication.txt` | `.cache/validation/study4_pilot/needs_adjudication.txt` | `eaca38000318024d7a8bf9e185297f03c3bf6bf1f629b2a52d5ec69667d7b2fd` |
| `pilot032/maintainer_sample_ids.txt` | `.cache/validation/study4/human_sample_ids.txt` | `7f2608dbbb0a9f0669c8a71bc4e8c32e3ce30f02ab0457f5d540cab4e048f786` |
| `pilot032/orders.json` | `.cache/validation/study4_pilot/orders.json` | `37aa98df0ce7849bf76fca9069c63d51468b997958602ea13f6b12a5924948b2` |
| `pilot040/dev032_hits.jsonl.gz` | `.cache/validation/study4/hits.jsonl` | `98053a49dbe2a0470c1081423d94d6155125c842547d9ce61aea2d32d46d2fb2` |
| `pilot040/frame.json` | `lexinspect-private/study4-pilot040/selection/build/frame.json` | `55a1d909f54df8fadb27e1c17313ab1c1ba8135709813f6684a3cab172b872dc` |
| `pilot040/items.jsonl.gz` | `lexinspect-private/study4-pilot040/selection/build/items.jsonl` | `2556ae7f5c44daff48bdee8170e6dfeb4b04a23c7fd0ef7f59bc148853d72eb3` |
| `pilot040/key.jsonl.gz` | `lexinspect-private/study4-pilot040/selection/build/key.jsonl` | `c95e7820cf0369164074b395aab6525615c7f7912fb656eea870f4bc3b66e24d` |
| `pilot040/labels/A.jsonl.gz` | `lexinspect-private/study4-pilot040/labels/A_merged.jsonl` | `43b3d1a89434ee062e1b0a35a7b8f6581d7d76e5ceed873d8d914284c499a7d1` |
| `pilot040/labels/A_original.jsonl.gz` | `lexinspect-private/study4-pilot040/labels/A_batch.jsonl` | `ac020889769028bf0760ebfe176e093985d3a0a3504ba7a6a6f126f1233db57f` |
| `pilot040/labels/A_retry.jsonl.gz` | `lexinspect-private/study4-pilot040/labels/A_retry.jsonl` | `f8be163fe1f67d3dbde6b20725f4359e5e95b4859221b8e0d3e075f547682107` |
| `pilot040/labels/A_retry_ids.txt` | `lexinspect-private/study4-pilot040/labels/A_batch_retry.jsonl` | `41e92cacefabd01777fbff3c1d112d16e264f2254134066e97a60e2ce8c6f028` |
| `pilot040/labels/B.jsonl.gz` | `lexinspect-private/study4-pilot040/labels/B_batch.jsonl` | `b8b529442a101183db3241d10a92f9e829718106af12df444f7652edf3fbdf4e` |
| `pilot040/labels/adjudicator.jsonl.gz` | `lexinspect-private/study4-pilot040/labels/adjudicator_adjudication.jsonl` | `52bfa59fc0035678d6ef697445a2128dc67d8c8962955483e88e72c6918cf62d` |
| `pilot040/labels/needs_adjudication.txt` | `lexinspect-private/study4-pilot040/labels/needs_adjudication.txt` | `4e545200556de4e1e7c150feead3d7c2af759defd04a7334dea91d5f073f4d5f` |
| `pilot040/maintainer_sample_ids.txt` | `lexinspect-private/study4-pilot040/selection/build/human_sample_ids.txt` | `75b7acce9e20d36908c38f4f1a1610636f4ef74ec8ba99e9ae5df871db12aea5` |
| `pilot040/orders.json` | `lexinspect-private/study4-pilot040/selection/build/orders.json` | `bb4d335d5ae3381294c494e8f5e3dc55ba7be10cf88e85ed18e33311b0e481e1` |
| `pilot040/reference/flash_diagnostics.json` | `lexinspect-private/study4-pilot040/analysis/flash_diagnostics.json` | `e3d2d90dbb6673fd386b4c36a5b94a5963dbd532972e6b8e139342568a953d38` |
| `pilot040/reference/pilot_textfree.json` | `lexinspect-private/study4-pilot040/analysis/pilot.json` | `f3aa1dd84cff957a2272fba354e4fa055cc5ff178eb235700ff261d99b8d24b4` |
| `texts/development.jsonl` | `.cache/validation/study4/texts.jsonl` | `5dba40ccbb99a853ef32e6f3def90f992810ff2320cf98f366e227d7112f1cc8` |
| | `lexinspect-private/study4-pilot040/selection/build/SHA256SUMS` | `81d61c2ab8dd9cc125e4e74b0d2a1eed614681b2675ca7b174b1763e5b650fd1` |
| `texts/round1.jsonl` | `docs/validation/study4-fix040/round1/collect/texts.jsonl` | `e517be6ab16f60b4a8180dee9c4401e520b7fae3d74b638bb35bbd27da5dc5dc` |
| | `docs/validation/study4-fix040/round1/collect/manifest_collect.json` | `359758e97100c5f9ba25c0ff0f9aa3295054ca1c3f7a8c39f25a8e385a5df531` |
| `texts/round2.jsonl` | `docs/validation/study4-fix040/round2/collect/texts.jsonl` | `50679c97fe3952d92a8fb2b0794f84dd4c741cbbc26e84b6b647d129d2b0f798` |
| | `docs/validation/study4-fix040/round2/collect/manifest_collect.json` | `f08a29da60cb51888997a906f1f6179a771477b766cdf29f100e024800deebf2` |

**A correction to the archive inventory.** In `.cache/validation/study4_pilot/`, `retry_A.jsonl` (`dc7c46e5…`, listed among the labels in `study4-archive.md`, section 4) is A's retry *manifest*, identical to `retry_A_manifest.jsonl`. The retry labels are `raw/A_retry.jsonl` (`6505ccda…`). The merged `labels_A.jsonl` is exactly `merge_retry(labels_A_original.jsonl, raw/A_retry.jsonl)`.

## Guard

`guard.py` scans every file, with gzip contents decompressed. It checks:

- for keys that hold text in the private files;
- for any substring of 30 or more characters of a source text, the guidelines, an inventory copy, or a gloss or example in `src/lexinspect/data/phrase.json`. Both the raw file and every decoded JSON string are scanned, so JSON escaping can't hide a match;
- for any multiword PHRASE headword;
- for the fix-check harness's restricted fragments (`fixcheck/scan.py`'s own `count`, private fragment file).

`export.py` runs the guard before writing anything.

**Result on 2026-10-21: clean.** It scanned 47 files against 793 corpus documents: the 120 development texts, which the 0.4.0 rebuild and its archived copy repeat byte for byte; both rounds' 60 texts; the guidelines; the inventory copies; and the PHRASE glosses and examples. That is 6,866,468 distinct 30-character windows, plus 506 headwords and 175 fragments.

**The repository's restricted scan** (`fixcheck/cli.py scan-restricted whole-set --fragments …/round2/inventory_fragments.txt`):

- on the repository: 354 files, 0 restricted (this includes the new `textfree/` code);
- on a scratch tree whose `docs/validation/study4-fix040/` held a copy of this folder plus the decompressed gzip contents: 82 files, 0 restricted.

## Licence and the texts

- **Licence (suggested):** CC BY 4.0 for this folder; the maintainer is to confirm. It contains no CC BY-SA text: no Wikipedia or Europe PMC wording, no titles, no matched words. The guard confirms that no source substring of 30 or more characters occurs. Identifiers, URLs, offsets and hashes remain.
- **No PHRASE List material:** no expression, gloss, example or sense wording; only ranks, K-bands and word counts.
- **The texts** are re-obtainable from the identifiers in `texts/*.jsonl`: the PMCID, DOI and full-text URL for Europe PMC, and the page id and revision (`oldid`) for Wikipedia. The limits are those of `study4-archive.md`, section 6: neither source guarantees the same bytes later. `text_sha256` lets a refetch be checked. With this folder, that now holds for the development texts too, whose per-text hashes were only private until now (archive inventory, open point 3).

## Open points for the maintainer

1. **Licence:** confirm CC BY 4.0 for this folder.
2. **The published acceptance files already name some sub-strata by PHRASE expression.** `study4-fix040/round{1,2}/accept/acceptance.json` and both sensitivity files use the original baseline-success sub-stratum names, which include five PHRASE expressions, for example `K3-multi|marker=…`. This folder codes them, but the published files do not.
3. **Freeze record:** if this folder is registered, add its `SHA256SUMS` hash and the building commit to `study4-freeze.json` (archive inventory, open point 2).
