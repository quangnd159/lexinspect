# Study 4 Stage-1 review, round 1: dispositions

**Review:** [`r1_review.md`](r1_review.md), by GPT-6.1-Sol (reasoning high) as independent methodology reviewer, 2026-10-21, at `8a566f0`. Verdict NOT READY: 2 BLOCKING, 5 SHOULD-FIX, 1 NIT. Its numerical checks of the pilot, the simulation, the effects report and the exclusions all reproduced.

**Dispositions written:** 2026-10-21 by the maintainer's session. Changes are in commits `6819a36` (R1-2 to R1-8, and the access route) and `6b27573` (the text-free export). Every finding was accepted. None needed a detector change, new labels, a new simulation run or a further fix-check round.

## R1-1 BLOCKING: no settled external recomputation route

**Accepted.** The maintainer chose the route on 2026-10-21. It has both parts the review allowed.

- **Public text-free export** (`docs/validation/study4-textfree/`, `scripts/validation/study4_precision/textfree/`):
  - **Contents:** memberships, keys, frame identities and links, labels, adjudication lists and text manifests, with the SHA-256 of each private source file. Notes and PHRASE alternatives are replaced by text-free stand-ins, and the frozen validator gives identical results on the real files and on the stand-ins for all 22 label files.
  - **Recompute:** `recompute.py` runs the frozen `analyse.main` and `accept.acceptance_of` unchanged on a text-free copy of each package. It bypasses only the full-package hash check and the registry and runtime checks. It reproduces the 0.4.0 and 0.3.2 pilot quantities, every computed field of both rounds' `acceptance.json`, and the sensitivity and control files: 72 checks, 0 differences.
  - **Guard:** every file is checked against the source texts (30-character windows), the guidelines, the inventory and the restricted fragments.
  - **Reproducible:** `export.py --check` rebuilds the folder byte for byte.
  - **Licence:** CC BY 4.0.
- **Full packages: supervised inspection only,** until the PHRASE permission is resolved. No package copy is transferred. The custodian is the maintainer. Requests go through a GitHub issue; no personal address is published. The conditions, the preserved inputs (bound by the freeze manifest) and the access log ([`study4-access-log.md`](../study4-access-log.md)) are in `study4-archive.md` section 7, using the review's own policy wording. That section separates the per-text Creative Commons terms from the restriction, which comes from the embedded PHRASE material and personal data.
- **Historical session evidence:**
  - The 16 Oct pilot's provider session records existed only in the providers' local stores. They were copied byte for byte into `lexinspect-private/study4-pilot032-transcripts/` (14 sessions, `SHA256SUMS`, read-only), and the freeze manifest binds them.
  - The 16 Oct adjudicator's OpenCode records were never found. `study4-archive.md` §3.5 lists them as an irretrievable gap.
- **Deposit contents:** the Stage-1 deposit will include the text-free simulation bundles, these review records and the freeze manifest.

**Noted from the export work.** The published `acceptance.json` and sensitivity files name five sub-strata by their PHRASE expression, for example `K3-multi|marker=…`. These are headwords only. The released package already ships them in `src/lexinspect/data/phrase.json`, so they add no new PHRASE material. No glosses, examples or inventory text are involved. The export codes these names anyway.

## R1-2 BLOCKING: the freeze builder missed dependencies and couldn't check drift

**Accepted; rewritten** (`pilot040/freeze.py`, format `study4-freeze/2`).

- **Inputs:** every input is now required, and a missing file, an unreadable file or an empty tree stops the build with exit 2. The manifest binds:
  - the evaluation pool cache, file by file;
  - the 0.4.0 rebuild, and the whole private pilot archive: selection, sessions with provider records, labels, validation logs, analysis, probes and dry run;
  - the 0.3.2 build, its pilot cache, its session records, and the historical simulation with its key and frame;
  - both simulation bundles (with SUMMARY, the tail table, the rate check and the tail-table tool);
  - every tracked Study 4 file, including `fixcheck/` and `textfree/`;
  - the fix-check records, the exclusions, the text-free export, the access log and these review records.
- **Receipts are checked, not just recorded:** every file named in each round's primary, retry and flash receipts is compared with its current bytes (and the archive tars with `private_archive.sha256`).
- **Release:** the working tree's `src/`, `pyproject.toml` and `uv.lock` are compared with the v0.4.0 tag blob for blob, and an extra file under `src/` fails the build.
- **Model:** every installed `en_core_web_sm` file is checked against its RECORD.
- **CLI versions:** the versions recorded in the pilot's own session archive are pinned (Claude Code 2.1.304, Codex 0.163.0; OpenCode doesn't record one). The versions installed at build time are reported separately.
- **Drift check:** `--check` ignores only the `observed` section (build time, the commit built from, the platform and the CLIs installed now). So a new commit with identical inputs passes. The deposit receipt lives in a sidecar, `study4-freeze-deposit.json`, so recording it doesn't change the manifest.
- **Negative controls** (`pilot040/test_freeze.py`, 20 tests): changing any one of the following makes the rebuilt manifest differ:
  - a pool file, a provider record, a session receipt, a validation log or the selection checksum list;
  - a historical label, the historical key or the historical simulation key;
  - the rate check or the simulation summary;
  - a fix-check source file or a receipt target;
  - a detector file or the final pilot labels.

  Deleting a required file fails the build. The manifest is built and `--check` run on the committed package; see the round-2 brief.

## R1-3 SHOULD-FIX: apply F1 with a bounded claim

**Accepted; applied in the reviewer's wording.**

- **Fix-check write-up:** `study4-fix-check.md` ("Deviations and corrections") has the dated correction paragraph, plus the limits sentence on what the sensitivity analysis does and doesn't establish.
- **`CORRECTION_F1.md`:** marked applied. It records the applied text and the corrected session count (round 2: 8 primary sessions and 1 retry), and adds the limits paragraph.
- **Prereg:** the deviation item, the "receives only" sentence (now qualified by the generic provider context listed in LAUNCH) and the item-level assignments sentence use the reviewer's text.
- **Effects report:** the sentence is now "The frozen acceptance objects recorded no procedure problem; the later-discovered context-isolation deviations…", changed in `effects.py` and regenerated.
- **LAUNCH.md:** its F1 disposition now says the correction is applied.

## R1-4 SHOULD-FIX: the session screen failed open

**Accepted.**

- **`check_sessions.py`:**
  - Each session gets one status: `technical_failure`, `flagged` or `clean`.
  - **Technical failure:** a missing or unreadable `session.json`, an undelivered status, a missing or inconsistent session id, missing, unlisted or mismatched archived files, or a provider record that is missing, empty or lacks its expected fields.
  - **Flagged:** relative, `~/`, `$HOME`, `file://` and glob paths are review items. Shell commands other than reading commands are flagged, and so are tools the role wasn't given.
  - **Whole archive:** it fails when it has no sessions or its launch log disagrees with the sessions. With `--expect`, it compares coverage with the assigned batches.
- **`launch.py`:** a session is recorded as delivered only if its provider record was archived and passes the context checks.
- **`collect_role.py`:** it requires the screen result and refuses sessions that aren't clean. Flagged sessions can be accepted only through a recorded human ruling, bound to the `session.json` hash and the hash of the exact flag set. A context-marker hit or a technical failure can't be ruled acceptable.
- **No change to what a session receives:** a test checks argv, environment and prompt against every archived `session.json`.
- **Tests:** 64 in `test_pilot040.py`, with missing-record, valid-record and ruling fixtures.
- **Real archive:** all 13 sessions have complete records, and 12 are clean. primary-A-02 is flagged for its Edit of its own labels file. It was examined on 2026-10-20, and that examination is now a ruling in `study4-pilot040/screen_rulings.jsonl`. Re-collecting all four pilot label sets with the new collector and this ruling reproduces the archived files byte for byte.
- **Wording:** the prereg and LAUNCH text use the reviewer's wording, and LAUNCH now says "has no command-execution tool".

## R1-5 SHOULD-FIX: simulation narrative

**Accepted.** The prereg's grid paragraph and its outcome-dependent explanation, `sim040/SUMMARY.md` and the historical round-3 sentence use the reviewer's text. Specifically:

- the main-realistic precision is .661–.748;
- the grid contains all 13 scenarios, with only low-precision-050 recalibrated;
- equal seeds don't give equal realised populations;
- the change in matched MD cells (.0045–.0095 to .0900–.1515) is separated from the comparison of maxima (.0535 was a PHRASE cell);
- these are synthetic stress results, not version effects.

No number changed.

## R1-6 SHOULD-FIX: stale exclusion inventory

**Accepted.**

- **Inventories:** `inventory.json` is now the final inventory, written by `tools/final_inventory.py`, whose `--check` rebuilds it. The old one is kept byte for byte as `inventory_v1_historical.json`.
- **The final inventory binds:**
  - the frozen file and its counts: 909 records, 331 aliases, 1 comment, 1,241 lines; 3,132 additional, 440 development, 9 shared and 3,563 union identifiers;
  - the page-id lookup and responses, and the builders;
  - the 1,027 sources by origin and by exposure class.

  It also reconciles each v1 open question with its dated decision.
- **README:** its opening is the reviewer's text, and its usage example uses the frozen path, seed and command.
- **`tools/ruff.toml`:** now excludes only the four archived builders.

## R1-7 SHOULD-FIX: "no non-votes"

**Accepted.** RESULTS.md and the prereg now distinguish missing or invalid records (none) from valid UNSURE records (9 each from A and B, 1 from the adjudicator), which are non-votes under the frozen outcome mapping. The table row heading was changed as proposed. The outcome rule is unchanged.

## R1-8 NIT: cache-copy preparation

**Accepted.** The prereg and the freeze manifest give `set -e; mkdir .cache/validation/study4_eval; cp -Rp …/study4/raw …/study4_eval/raw`, the rule for an existing destination, and verification of the copy against the pool-cache file inventory frozen in `study4-freeze.json`, before collection.

## Also corrected

`study4-archive.md` §4 listed the 0.3.2 pilot's `retry_A.jsonl` as labels. It is A's retry manifest. The retry labels are `raw/A_retry.jsonl` (`6505ccda…`), and both are now listed.

## Erratum, 2026-10-21 (after review round 2)

Under R1-1, "for all 22 label files" is wrong. The export's manifest and `export.py` check **16** source label files: five per pilot and three per fix-check round. The round-2 review found this (R2-6); the text above is left as written.
