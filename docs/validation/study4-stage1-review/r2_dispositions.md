# Study 4 Stage-1 review, round 2: dispositions

**Review:** [`r2_review.md`](r2_review.md), by GPT-6.1-Sol (reasoning high) as independent methodology reviewer, 2026-10-21, at `587f836`. Verdict NOT READY: 1 BLOCKING, 4 SHOULD-FIX, 1 NIT. It found R1-5 to R1-8 resolved and R1-1 to R1-4 partly resolved. Its arithmetic, text-removal and pilot-delivery checks all passed.

**Dispositions written:** 2026-10-21 by the maintainer's session (Claude Code acting for the maintainer). The changes are in the commit that adds this file. Every finding was accepted, and the reviewer's exact texts were used where it gave them. No finding needed a detector change, new labels, a new simulation run, a further fix-check round or a change to any historical tar or receipt.

## R2-1 BLOCKING: late provenance evidence was not bound

**Accepted.** `pilot040/freeze.py` now has two separate parts under `fix_check`:

- **`decision_time_packages`:** the receipts and the archive tars, checked as before and unchanged.
- **`later_evidence`**, all required:
  - **The access-review addenda:** `round{1,2}/transcripts/ACCESS_REVIEW_RULINGS.md`, as they are now, including the amended round-2 ruling. These are also key files, so a missing one stops the build.
  - **The unpacked rounds:** every file of `lexinspect-private/study4-fix040/round1/` and `round2/` (510 and 529 files, about 1.1 GB; like every tree in the manifest, `.DS_Store` files and `__pycache__` bytecode are skipped, which accounts for 23 of round 2's 552 files), and both `materials/SHA256SUMS` checked against their targets.
  - **The post-decision event archive:** every file, and its `SHA256SUMS` checked entry by entry, so a changed resumed-session transcript or rewritten working copy stops the build.
  - **The scripts:** the historical launch and access-review scripts in `study4-fix040/tools/`.
  - **The pinned baseline:** `pinned-dec79bc/` compared blob for blob with commit `dec79bc0…`, and its file hashes. Its `.venv` is an environment cache and is not compared.
  - **The cited review reports:** under `.cache/validation/study4_fix040/`, the top-level reports and dispositions, `round2/*.md`, `final_audit/` and `scripts/`, plus `.cache/validation/sol_round2_harness_audit_r1–3.md`. They are not deposited, since they are restricted working material. The manifest gives each one's exact hash, and the archive inventory gives where it's kept (the custodian's machine) and its access tier (3).

Every other `SHA256SUMS` in a bound private folder is checked too: the 0.4.0 selection build, the probes and the 16 Oct session records.

**Text used:** the freeze builder's fix-check bullet and the addition to archive §7 ("Later evidence") use the reviewer's text. The archive's integrity cells for these folders now say what the manifest binds.

**Negative controls** (`pilot040/test_freeze.py`, now 36 tests):

- **Changes the manifest:** changing any of the following:
  - the late access-review ruling;
  - a resumed-session transcript;
  - a post-decision checksum target (this also stops the build with a checksum mismatch);
  - the post-decision README;
  - an access-review script;
  - a pinned-baseline file;
  - the cited final review;
  - a cited harness audit.
- **Stops the build:** removing the late ruling, the post-decision README or the cited final review.

## R2-2 SHOULD-FIX: the access log made `--check` fail on first use

**Accepted.**

- **Two files.** `study4-access-log.stage1.md` is the Stage-1 snapshot. The manifest hashes it, and its absence stops the build. The live `study4-access-log.md` is append-only and versioned in git. The manifest names it under `administrative_records`, but doesn't hash it.
- **Wording.** The archive's "Preserved inputs" paragraph is the reviewer's replacement text. The log's header explains the split. The log's table has a new column for the log version (commit and SHA-256) that each inspection records.
- **Controls:**
  - changing the live log leaves the manifest identical, with no problem;
  - changing the snapshot is detected;
  - changing the live log and a late-evidence input together is still detected.

## R2-3 SHOULD-FIX: the collector trusted a stale archive screen and accepted an empty stage

**Accepted.**

- **`collect_role.py` checks the archive as it is now before reading any label.** It stops, writing nothing, in any of these cases:
  - the current archive has an inventory problem against its launch log;
  - the saved screen was made from a different launch log (`check_sessions.py` now records `launch_log_sha256`);
  - the saved screen doesn't list exactly the sessions now archived;
  - any session's `session.json` has changed since the screen.
- **An empty `batches` list** is reported as "not applicable" (exit 3) before anything is written.
- **Docstring:** the collector's description is the reviewer's text, followed by the detailed list.
- **New controls in `test_pilot040.py`, now 67 tests:**
  - a missing-session log entry appended after the screen;
  - an archive removed after the screen;
  - an unlogged archive added after the screen;
  - a logged session added after the screen;
  - a screen listing a different set of sessions;
  - an empty assignment.
- **The real pilot.** The four pilot label sets were re-collected from the private archive into `/tmp` with a fresh screen and the existing ruling. All four label files and all four retry manifests are byte-identical to the archived ones.

## R2-4 SHOULD-FIX: the pilot ruling was agent-produced

**Accepted.** No separate human approval of this ruling has been documented, so the departure is disclosed:

- **LAUNCH.md:** the reviewer's paragraph is added after the pilot-screen paragraph. It says that a Claude Code session acting for the maintainer examined the flag, and that the retained ruling doesn't document a human transcript examination. It discloses this as a departure from the human-review procedure. Evaluation flags require the maintainer's dated examination and approval before collection.
- **"Human ruling" is no longer used.** The prereg, LAUNCH and the collector now say "recorded ruling". They add that the collector verifies the ruling's completeness and binding, and that the maintainer's examination and approval is an operational commitment the code can't establish.
- **The original ruling is unchanged.** If the maintainer approves it personally later, that will be a separate record giving the date, the person, the session hash and the flag hash.

## R2-5 SHOULD-FIX: remaining overclaims

**Accepted; replaced with the reviewer's texts:**

- **Archive §3.5:** the OpenCode gap now says the missing labels did contribute to historical development and to the adjudicator qualification.
- **CORRECTION_F1.md:** the two "reached them" and "carried no … information" sentences (the review's `:14` and `:26`) are now the retained-records statement. The rescreen paragraph (`:32`) is replaced.
- **LAUNCH.md:** its matching claim for B and C ("What the extra context could reveal") is replaced the same way.
- **The text-free README:**
  - the bypass bullet is replaced;
  - a paragraph after the comparison table says the empty `procedure_problems` input and the label-file metadata aren't a fresh procedural audit;
  - the exclusion-union point now gives the counts.

The union counts were rechecked independently with the frozen `build.text_refs`. The export's development metadata yield 320 identifiers, which give 3,448 with the additional manifest; 115 canonical identifiers are missing.

## R2-6 NIT: documentation

**Accepted.**

- **The text-free README:**
  - its status line, the 16 label files and the licence line are the reviewer's text;
  - open points 1 and 3 are replaced as given, under the heading "Points recorded for the maintainer";
  - its `SHA256SUMS` was regenerated, and `export.py --check` passes (47 files, 0 differ).
- **The round-1 dispositions:** an erratum is appended for "22" (it is 16). The original text is unchanged.
- **The archive:**
  - the row for the 6 tracked `study4-pilot040/` files;
  - the committed `/2` manifest with its separate deposit record;
  - the historical simulation's integrity cell.
- **`final_inventory.py`:** the lint note is replaced. `inventory.json` was rebuilt (`11daffc2…`), `--check` passes, and the exclusions README hash is updated. Only the note text changed in the inventory.

## Also done for the deposit

- **The prereg's Stage-1 review count** (line ~304) now names the two rounds and their records. The Stage-2 placeholders are left as they are.
- **This review and these dispositions** are tracked in `docs/validation/study4-stage1-review/`, which the manifest binds.
