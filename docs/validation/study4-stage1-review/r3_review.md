READY FOR STAGE-1 DEPOSIT

Independent Stage-1 methodology review, round 3 (verification), 2026-10-21. Reviewed `main` at `07d6ad0cd8702eb6cc2f7d87fad85c3b05b32855`, both earlier review/disposition pairs in full (including the R1 erratum), the complete `587f836..07d6ad0` response, and the seven Stage-1 obligations in `.cache/validation/study4_fix040/final_audit/sol_final_audit_r2.md:158–164`. The previous deposit blocker is resolved. Two non-blocking editorial nits remain below; neither requires new labels, another fix-check round, detector changes, a simulation rerun or another methodology-review round. This verdict concerns readiness to deposit the identified package, not an already completed registration or validation against independent human judgements.

Paths below are relative to the repository unless prefixed `lexinspect-private/`, which denotes `/Users/quangnguyendang/lexinspect-private/`. Pilot Python files are under `scripts/validation/study4_precision/pilot040/`.

| Finding | Status | Current text/code and verification |
|---|---|---|
| R2-1; residual R1-2 | **Resolved** | `freeze.py:406–437` inventories the later evidence; `:528–530` separates `decision_time_packages` from `later_evidence`. Archive `docs/validation/study4-archive.md:193`: “Earlier tar members are not substituted for later addenda. A changed or missing required record stops verification.” Full-tar baseline and all six requested changed/missing-input controls pass. Details below. |
| R2-2; residual R1-1 | **Resolved substantively** | `freeze.py:566,571–578` hashes the Stage-1 snapshot and names the live log under `administrative_records`. Archive `:192`: “recording an access request never requires rebuilding the scientific manifest.” Live-log changes do not affect the comparison; snapshot and simultaneous scientific-input changes do. The snapshot's copied self-description is misleading (R3-1 NIT). |
| R2-3; residual R1-4 | **Resolved** | `collect_role.py:94–124` checks the current log/inventory, exact screened session set and every `session.json`; `:213–221` reports an empty assignment as “not applicable” and returns 3 before output. `check_sessions.py:663–665` records `launch_log_sha256`. Own stale-inventory controls reject before writing. All four real label/retry pairs reproduce byte for byte. |
| R2-4; residual R1-4 | **Resolved** | `docs/validation/study4-pilot040/LAUNCH.md:59`: “The retained ruling does not document a human transcript examination” and “evaluation flags require the maintainer's dated examination and approval before collection.” Prereg `:323` and `collect_role.py:32–39` distinguish a technically bound ruling from the operational human-approval commitment. The original agent-produced ruling is preserved; no human act has been manufactured. |
| R2-5; residual R1-3 | **Resolved substantively** | Archive `:128` acknowledges historical-development/adjudicator-qualification dependence and the unrecoverable context. `CORRECTION_F1.md:12,26,32,34` bounds the assertions to retained records and states the limits. Text-free README `:42,55,70` correctly distinguishes conditional arithmetic, external procedural input and the incomplete exported exclusion union. One shorthand summary still merits qualification (R3-2 NIT). |
| R2-6 | **Resolved** | Text-free README `:3,87,192,198–200` gives committed status, 16 source label files, confirmed licence and the existing freeze. R1 dispositions `:114–116` preserve the original statement and append the count erratum. Archive `:55,58,114` fixes the pilot/freeze/history rows. Final-inventory note at `docs/validation/study4-exclusions/tools/final_inventory.py:302–303` and rebuilt inventory match. |
| R1-5, R1-6, R1-7, R1-8 | **Remain resolved** | The final simulation narrative, actual exclusion data, distinction between UNSURE and missing/invalid records, and one-time cache-copy preparation remain consistent. The response changes no detector, label, estimator, simulation result or exclusion membership. |

The R1-1 access route is now concrete and compatible with the freeze; R1-2's dependency binding is complete for the promised scientific/provenance account; R1-3's applied correction is bounded; R1-4's actual-pilot evidence and prospective acceptance checks pass. Remaining limitations are disclosed limitations, not undisposed blockers.

## Verification results

### 1. Committed freeze and late provenance

The normal command, `uv run --offline --no-sync python -I -B scripts/validation/study4_precision/pilot040/freeze.py --check`, exits **0**, reporting **“freeze manifest matches”**. This call verifies the four real decision-time tars against their unchanged receipts. The reviewed manifest SHA-256 is `bb3d0b228c4a05bbc33f357a5a97f60ad96ce4fe57524f877612506d74f5b370`.

I inspected the complete manifest diff structurally and verified the generated object against all current dependencies, rather than treating its 1,485 added lines as unverified prose. The old receipt-verification object moves under `decision_time_packages`; it is not replaced by the later trees. The new inventory binds:

- 510 round-1 and 529 round-2 files, including both current access-review addenda;
- all 26 post-decision files;
- 15 historical tool files (the raw directory count also includes skipped bytecode);
- 173 pinned-baseline commit files, plus the separately hashed `PINNED_COMMIT.json`; no differing or extra baseline file;
- 50 top-level fix-work reports, 12 round-2 reports, 29 script-directory files, four final-audit files and three separately located harness audits.

`freeze.py:355–373` verifies checksum targets, not merely the checksum-list digest. Independent enumeration finds **six** `SHA256SUMS` files in the bound private directories, **202 entries** total: selection 142, probes 17, historical sessions 15, two materials lists of two each, and post-decision events 24. Every target matches. The blanket checksum claim is true for this committed inventory; the implementation calls these six lists explicitly rather than discovering arbitrary future checksum lists recursively.

Own controls: `/tmp/s4r3_freeze_controls.py`; results `/tmp/s4r3/freeze_controls.json`. The baseline uses real tar verification and equals the committed manifest. Each control substitutes one dependency's digest in memory; the pinned-file control also substitutes its Git blob result. Unchanged digests are cached for repeated runs. Only volatile CLI observations are stubbed in this control script; the separate normal `--check` uses the real observations. No repository/private bytes are changed.

| Target | Changed | Missing |
|---|---|---|
| Round-2 late access ruling | 2 differing manifest paths | 2 differences; 3 integrity problems |
| Resumed-session transcript | 2 differences; checksum problem | 2 differences; 2 problems |
| Rewritten post-decision checksum target | 2 differences; checksum problem | 2 differences; 2 problems |
| Cited final release review | 1 difference | 1 difference; 2 problems |
| Historical access-review script | 1 difference | 1 difference; 1 problem |
| Pinned-baseline `pyproject.toml` | 2 differences; blob mismatch | 2 differences; 2 problems |

Thus all twelve requested change/removal cases stop successful verification. Ordinary changed ruling/review bytes can leave `PROBLEMS` empty while changing the manifest: `--check` rejects such drift with exit 1; a separately detected integrity failure gives exit 2. Neither case is successful verification. As in round 2, not every recursively inventoried file is independently required during standalone construction; deletion is nevertheless caught against the externally anchored complete manifest. Never rebuild that anchor merely to legitimise missing evidence.

**Remaining binding assessment:** I found no additional unbound record needed to support the final provenance account promised to a tier-3 inspector. The late ruling, resumed records, checksum targets, launch/access tools, pinned baseline and cited reviews now have explicit bindings. The irrelevant full 14 GB working area need not be frozen. The missing original OpenCode record remains explicitly unrecoverable, not silently represented as bound. These hashes authenticate locally retained evidence; they do not prove provider-side hidden state, human identity, off-machine custody or future access responsiveness. The final public account states that the restricted bytes stay with the custodian.

### 2. Access-log boundary

Own in-memory live-log change/removal controls leave the manifest identical and `PROBLEMS` empty. Snapshot changes create a difference; its simulated removal also produces required-input problems. Changing the live log and the late ruling together still produces the ruling differences. The scientific comparison therefore excludes precisely the named administrative record and continues checking scientific evidence. Removing the live log is outside this scientific check; maintaining it remains the separate administrative commitment.

The live log, `docs/validation/study4-access-log.md:5`, specifies that an inspection records the log's commit and SHA-256 **before** the inspection entry is appended, avoiding a self-hash problem. Snapshot wording needs R3-1, but the executable boundary works.

### 3. Current screening, empty stages and retained deliveries

The supplied freeze and pilot suites pass **103 tests: 36 + 67**, with `-I -B`, disabled pytest cache, and scratch fixtures confined to `/tmp`. No real labelling client is invoked by the launcher controls.

My separate `/tmp/s4r3_screen_controls.py` constructs fresh synthetic archives using the existing fixture writer, then calls the production screen/collector. Results: `/tmp/s4r3_screen_controls.json`. A clean session succeeds. After a clean screen, each of the following is rejected with no output directory: appended log entry for a missing session; removed archive; added unlogged archive; added logged session; screen missing a session; changed `session.json` belonging to another role. Empty `batches` returns **3**, prints “not applicable”, and writes nothing. A missing batches key also yields that safe no-output result. The collector's exact current-session and per-selected-session fresh-screen checks remain in place.

Own repeated retained-delivery concatenation: `/tmp/s4r3_recollect.py`, outputs and hashes in `/tmp/s4r3_recollect/result.json`. Fresh screening uses all four actual assignment manifests. Ten pilot sessions plus three dry-run sessions have no inventory, coverage, technical or context-marker problem. Twelve are clean; primary-A-02 has the known Edit flag. With the unchanged recorded ruling, these **four label files and four retry manifests** are byte-identical to the retained originals:

| Retained output | Bytes | SHA-256 prefix |
|---|---:|---|
| `A_batch.jsonl` | 122,214 | `ac020889769028bf` |
| `A_batch_retry.jsonl` | 358 | `41e92cacefabd017` |
| `B_batch.jsonl` | 109,643 | `b8b529442a101183` |
| `B_batch_retry.jsonl` | 0 | `e3b0c44298fc1c14` |
| `A_retry.jsonl` | 308 | `f8be163fe1f67d3d` |
| `A_retry_retry.jsonl` | 0 | `e3b0c44298fc1c14` |
| `adjudicator_adjudication.jsonl` | 8,548 | `52bfa59fc0035678` |
| `adjudicator_adjudication_retry.jsonl` | 0 | `e3b0c44298fc1c14` |

Original per-batch validation data also agree; new screen/ruling/code provenance fields legitimately differ from the old validation reports. This reads already delivered labels; it produces no new judgement and runs no corpus collection/build.

### 4. Numerical/export regressions and the broader package

- Text-free `export.py --check`: **47 files rebuilt, 0 differ, 0 extra**; its real restricted-text guard is clean (793 documents, 6,866,468 distinct 30-character windows, 506 headwords, 175 fragments). `recompute.py`: **72 checks, 0 failed**, including both pilots, both gate rounds, sensitivity and control. These remain conditional arithmetic checks, with the documented production/provenance bypasses.
- Repeated the round-2 independent arithmetic script, which imports no project analysis/estimator/validator: `/tmp/s4r3_independent.py` and `.json`. Final STRICT weighted precision reproduces as exact-rational .5537539851554774 MD and .8700230881465875 PHRASE (ordinary last-bit summation differences from the frozen floats); unweighted 693/999 and 230/300; reference sources 945/54/1 and 288/12/0. Independent integer-combinatorial COMPLETE removal upper counts remain 33/675 and 12/321, both passing. No gate reversal.
- Repeated `/tmp/s4r3_sim_check.py`: each bundle has **58 unique cells / 244,460 replicates**, correct required cell inventory, complete status, replicate ranges, raw/merged equality and result hashes. Final source/key/frame hashes match. All **116** reconstructed synthetic populations match retained numerical attributes and the corresponding public coded designs. This regenerates populations, not all sampling replicates. Only the six main-pilot and four low-precision cells change effective parameters between versions. Current main-realistic precision is .661–.748; grid primary/region maxima remain .1515/.005. The existing narrative correctly separates synthetic stress results from detector version effects. No full simulation rerun is indicated.
- `final_inventory.py --check` matches SHA-256 `11daffc283629070c502f5558e648057e757bbc112638ccf6ee8c2edbed36641`. The response changes only its lint note. The actual exclusion membership and frozen evaluation command remain unchanged; the union is 3,563, while the public exported-development metadata alone can form only 3,448 with the additional file. README `:70` now discloses this correctly.
- `pilot040/effects.py --check` passes. Effects data, detector bytes and the previously independently checked count/density cells are unchanged in this response. The freeze separately verifies release equality and all archived scientific dependencies.

The seven Stage-1 obligations are now met to the point at which deposit itself can proceed: final-pilot population/labels/delivery evidence, numerical calibration, complete final simulation, exclusion union/seed/cache/command, final history/disclosures/effects, concrete access/custody and joint independent review. The external timestamp/receipt part of obligation 7 is necessarily still the next action, not something this review claims to have performed. Stage 2 remains later.

### 5. The two reported legacy failures

I reproduced both failures with the exact two tests, disabled cache and `/tmp` test scratch. Results: `/tmp/s4r3_fix_tests.log`; source/hash investigation: `/tmp/s4r3_legacy_check.json`.

1. `fixcheck/test_fixcheck.py:1551–1560` compares a real dec79bc source snapshot with **the current repository's lock file**, then asserts `environment_identical`. The 76 source files match dec79bc; its lock SHA-256 is `d9fe8ce6…`, whereas the current/v0.4.0 lock is `559f6fd9…`. The preserved pinned checkout has the correct dec79bc lock and passes that equality. The current lock was already identical at `587f836`; this failure is pre-existing, not caused by the response.
2. `fixcheck/test_r9.py:252–259` asserts that historical round-1 bound files still equal their current working paths. The only reported bound-file difference is the preregistration. Round 1 pins `459c2cbe…`; the prereg at `587f836` already hashes to `ffccead4…`, and the present file to `963a91ff…`. The original is recoverable byte-for-byte from commit `1a0c502` and matches the bound hash. The round-1 tar does **not** contain a separate preregistration member; preserving repository history/source snapshots therefore matters. Applying final Stage-1 disclosures to the live prereg must not entail rewriting round 1's record.

The maintainer is right about the causes and their pre-existence. These failures do **not** indicate damage to the currently checked Stage-1 dependencies or require changed scientific results. They also do not justify saying that the whole validation suite passes. Future test maintenance should compare the historical fixture with its historical lock/prereg bytes, retain explicit current-drift detection, and separately test the final Stage-1 manifest; simply weakening the checks would lose useful protection.

“Both skip in CI” is imprecise. `.github/workflows/quality.yml:33–34` runs ordinary `uv run pytest`; `pyproject.toml:104–106` restricts default discovery to `tests/`, so these scripts are **not collected** by that job. The pinned-source test has an absent-private-fixture skip, but the R9 skip checks a tracked round-1 freeze-record path and is not a generic CI exemption. Accurate replacement for any validation summary is: “The two legacy checks fail locally for their historical/current-tree assumptions. The default CI test job does not collect the validation-script suites; their results are reported separately.” This correction concerns the supplied brief, not a sentence found in `r2_dispositions.md`.

## New findings

### R3-1 NIT — The frozen snapshot describes itself as the mutable, unhashed log

**Location:** `docs/validation/study4-access-log.stage1.md:3,5`.

**Evidence:** the heading identifies a Stage-1 snapshot, but the copied body says requests are “recorded here”, that “this file” is not hashed and that entries are appended. The code correctly hashes this file. The live log and archive policy explain the intended split correctly. This is a documentation ambiguity, not the old executable R2-2 problem.

**Exact replacement for the two body paragraphs at lines 3 and 5:**

> This file is the immutable Stage-1 snapshot of the restricted-material access log, retained on 2026-10-21 and hashed by `study4-freeze.json`. The access arrangement is in [`study4-archive.md`](study4-archive.md), section 7.
>
> Subsequent requests, inspections and corrections are appended only to the separately versioned live log, [`study4-access-log.md`](study4-access-log.md), which is named but not hashed by the scientific manifest. This snapshot is never appended to. Before each inspection, `pilot040/freeze.py --check` verifies the scientific inputs; the live-log entry records that log's commit and SHA-256 as it stood before the entry was added.

Keep the dated empty table/history. If adopted before deposit, rebuild and check the final manifest after this editorial change.

### R3-2 NIT — One F1 summary still drops the retained-records qualification

**Location:** `docs/validation/study4-pilot040/CORRECTION_F1.md:27`.

**Evidence:** the adjacent detailed assertions are now bounded correctly, but the summary still says the blinding statement “becomes ‘no version, family or label information’”. Read alone, this is the broader assurance R2-5 sought to avoid. The applied paragraph and limits make the intended interpretation clear, so this is a minor consistency issue rather than an unresolved methodological finding. The explicitly historical first-draft quotation at `:14–18` can remain as history.

**Exact replacement for line 27:**

> - **The disclosure changes.** For B and the adjudicator, the claim is limited to the retained records inspected: no branch/commit snapshot, candidate-direction information, item-level version/family assignments or other labellers' responses were found there. It does not claim absence of repository context or establish the contents of unrecovered records.

No new substantive error was found in the committed R2 dispositions. Their inventory counts, controls, unchanged historical receipts and byte-identical retained outputs are supported. “Exact texts” describes the substantive replacements; it should not be read as a guarantee that every surrounding summary has already been made equally precise.

## What should enter the Stage-1 deposit

The round-2 list remains correct, with this round and its disposition added. Deposit an immutable, identified package with a top-level file/hash index and short offline verification README. The README must distinguish public arithmetic recomputation from the custodian-only full `freeze.py --check`, which requires the restricted files and local Git objects.

1. **Final public scientific record:** preregistration, fix protocol/clarifications, both rounds' public decisions/receipts/rulings, sensitivity plan/results/control, full effects report/JSON, exclusion folder and archive/access policy. Preserve explicit model-only reference, reviewer/labeller model-family overlap, lack of independent human validation, historical context loss, agent-produced pilot ruling and prospective human-approval requirement. The current prereg `:304` truthfully records two methodology rounds and provides for later verification; record this third round and its disposition accurately in the final package. Leave Stage-2 build/count placeholders intact.
2. **Final `/2` manifest and review records:** include r1/r2 reviews and dated dispositions, this r3 report and its dated disposition. If the optional wording edits or final review records are incorporated, commit them and rebuild/check the manifest once against that complete pre-deposit package. This is expected final packaging, not permission for post-deposit scientific drift. The digest above identifies the reviewed starting manifest, not an as-yet-uncreated final packaging version. Use a separate receipt record containing OSF service/immutable record or version, UTC time, final package commit, final manifest digest and receipt/link. A later receipt may be retained as a linked supplement without regenerating the scientific manifest.
3. **All 47 text-free export files:** README, manifest, checksums and payloads; frozen export/recompute/guard code and every imported analysis/acceptance dependency; Python/environment/dependency record and lock file. Preserve the documented limitations on semantic correctness, PHRASE alternative wording, original adjudicator qualification, exact title-alias union and production provenance.
4. **Both complete simulation bundles:** `sim040/` (16 files), historical `sim_final/` (12), and the separate `study4_scratch/tools/tail_table.py`. Include raw/merged results, summaries, logs/checkpoint metadata, checksums, tail tables and ratecheck script/output. Preserve matching historical and final source versions and explain use of the equivalent public coded designs, including their different names/hashes. An immutable Git bundle preserving the necessary commits/tags and history is particularly useful: it retains the historical source versions, original round-1 preregistration and Git objects needed by equality checks. An exported current tree alone does not do that.
5. **Restricted custody/access index:** key it to the final manifest and include the unchanged tars, unpacked rounds with later addenda, post-decision events, historical launch/access tools, pinned baseline, cited private reviews, both pilots' inputs/labels/provider records and the unrecoverable OpenCode gap. Identify which bytes remain only on the custodian's machine and the supervised request/access terms. Public OSF upload need not contain source bodies, guidelines, PHRASE inventory, note-bearing labels or transcripts. Include the hashed access-log snapshot and an initial copy/link/version for the separately maintained live administrative log. A hash and access promise are not an independent off-machine backup.

The absence of an OSF receipt now is expected. Evaluation collection remains unopened until Stage 1 is externally retained and its receipt is recorded. Stage 2 remains the single later evaluation build deposited before evaluation labelling.

## Limits and final disposition

This was a read-only verification review. All authored scripts, synthetic fixtures, output concatenations and this report are under `/tmp`; bytecode and pytest repository-cache writes were disabled. The same four unrelated untracked files remain. No state-changing Git command, new labelling, corpus collection, detector/evaluation build, deposit, network fetch or communication to another person was performed. The expressly requested retained-label re-collection only reads existing deliveries and writes scratch outputs. No additional agents were used. I did not rerun all sampling replicates, independently relabel items, adjudicate redistribution rights or test a real external access request. Earlier independent calculations were rerun where stated; other unchanged results retain the earlier rounds' verification rather than being presented as freshly re-derived here.

The package is ready for the Stage-1 deposit with its disclosed limits. The two editorial nits are recommended final polishing and do not reopen the scientific design or require a fourth review. Final manifest/index/receipt preparation remains ordinary deposit work.

**Final finding counts: 0 BLOCKING, 0 SHOULD-FIX, 2 NIT.**

READY FOR STAGE-1 DEPOSIT — 0 BLOCKING, 0 SHOULD-FIX, 2 NIT.
