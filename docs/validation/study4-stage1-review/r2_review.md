NOT READY

Independent Stage-1 methodology review, round 2, 2026-10-21. Reviewed main at `587f836088863fba7b114521040a1c2edc9ff7e2` and the complete change set `8a566f0..587f836` (code/prose inspection and exhaustive regenerated/hash/schema checks of the machine-readable additions). Arithmetic reproduces; the remaining blocker is an incomplete binding of later provenance evidence. Bounded workflow and wording fixes are listed below. No new labels, detector change, third fix-check round or full simulation rerun is indicated.

In the table, document names are under `docs/validation/`; Python launcher/screen/collector names are under `scripts/validation/study4_precision/pilot040/`.

| Finding | Status | Evidence |
|---|---|---|
| R1-1 | **Partly resolved**: public arithmetic/access specification supplied; access operation needs R2-2 | `study4-archive.md:183–193`: “Open, CC BY 4.0” and “Custodian: the maintainer, Quang Nguyen” specify the public export and supervised route. The recompute run gives 72 checks / 0 differences; independent calculations below reproduce STRICT precision and both round-2 COMPLETE removal gates. README status/licence wording remains stale (R2-6). The request-log freeze conflict needs R2-2; no new access mechanism is needed. |
| R1-2 | **Partly resolved**: R2-1 remains BLOCKING | `pilot040/freeze.py:331–465` hashes the expanded inventory, including `"private_archive": tree(PILOT040)` and `"receipts_verified": fixcheck_receipts(verify_tars)`; release/model contents are checked. The committed `--check` passes. Own controls detect the previously omitted inputs, but not later provenance records outside the tars (R2-1). |
| R1-3 | **Partly resolved**: correction applied; residual overclaims in R2-5 | `study4-fix-check.md:101`: “the absence of observed out-of-directory access does not prove that context had no effect” applies the bounded F1 correction; prereg `:148,275,330` and effects `:310` use the requested qualifications. `CORRECTION_F1.md:3` marks the correction applied; some surrounding assertions still lack the retained-records qualification (R2-5). |
| R1-4 | **Partly resolved**: retained-pilot claim verified; R2-3 and R2-4 remain | `check_sessions.py:165–297,476–557` fails closed on absent records/context/hash mismatch; `collect_role.py:118–151` requires `and not r.get("context_forbidden_hits")` and `and not r.get("technical_failures")`. All 64 existing tests pass; own controls expose stale/empty inventory acceptance (R2-3), and the “human” attribution is unsupported by its recorded reviewer (R2-4). |
| R1-5 | Resolved | Prereg `:574`: “equal seeds do not imply identical realised finite populations or replicate samples”; `:607,624` distinguish synthetic changes/history. The current .661–.748 range reproduces. |
| R1-6 | Resolved | Exclusions README `:3`: “The final machine inventory is inventory.json; the former inventory is retained unchanged as inventory_v1_historical.json”. `final_inventory.py --check` passes; frozen counts/hash and v1 preservation reproduce. |
| R1-7 | Resolved | RESULTS `:39`: “UNSURE records remain semantic non-votes under the frozen outcome mapping”; `:38,65` distinguish missing/invalid; prereg `:68,129,393` is consistent. |
| R1-8 | Resolved | Prereg `:179` specifies `mkdir .cache/validation/study4_eval`; `:183` says “The copy, including every pool file, is verified against the cache's file-hash inventory”. No evaluation operation was run. |

## Recomputations and controls

Reviewed checkout: main, `587f836088863fba7b114521040a1c2edc9ff7e2`. The repository already has four unrelated untracked design/privacy artifacts; they are outside this review. No repository/private input is changed. Python uses `uv run --offline --no-sync python -I -B`; `-B` suppresses repository bytecode writes and temporary outputs are directed to `/tmp`.

- Public `textfree/recompute.py --json /tmp/s4r2_recompute.json`: exit 0, **72 checks, 0 failed**, both pilots, both rounds, sensitivity and control.
- `pilot040/freeze.py --check`: exit 0, **freeze manifest matches**.
- `textfree/guard.py`: exit 0, **47 files; 793 documents; 6,866,468 distinct 30-character windows; 506 headwords; 175 restricted fragments; clean**.
- Own independent schema/content pass: 301,932 JSON string values inspected; no text-bearing keys; every item/label shape restricted to its expected code/count fields. Across all 240 unique archived source texts plus guidelines and inventory (242 files), 1,103,775 normalised eight-token windows had zero matches to multiword data-value windows. None of 5,714 substantive original label-note records (at least 20 characters) equals an export string value. This supplements, rather than replaces, the supplied raw/decompressed/decoded-string guard. It is evidence for this export, not a general proof that every possible future export is text-free.

Own `/tmp/s4r2_independent.py` imports **no project analysis, validator, reference or estimator code**. It reads the gzip JSONL exports, constructs the definite A–B agreement/otherwise adjudicator reference, then calculates `sum_h N_h k_h/r_h / sum_h N_h` with exact rational arithmetic:

| Pilot 0.4.0 STRICT | Metadiscourse | PHRASE |
|---|---:|---:|
| Weighted precision | 5299099906/9569411775 = 0.5537539851554774 | 2937021859/3375797607 = 0.8700230881465875 |
| Unweighted | 693/999 | 230/300 |
| Reference from primaries / adjudicator / unresolved | 945 / 54 / 1 | 288 / 12 / 0 |

The last-bit difference from the frozen floating-point sum (.5537539851554772 and .8700230881465874) is ordinary summation rounding; the substantive quantities agree.

For round 2's COMPLETE removal gate, my code selects the sampled REMOVED memberships itself, maps the inventory outcome independently, and inverts the finite-population hypergeometric CDF with integer binomial coefficients at alpha = .05/[4*(12+5)] = 1/1360. It uses the strict `CDF > alpha` acceptance convention and compares the resulting bound and pass/certificate flags with the published acceptance:

| COMPLETE removal, round 2 | Metadiscourse | PHRASE |
|---|---:|---:|
| N / n / k_lo / k_hi | 675 / 200 / 2 / 2 | 321 / 200 / 2 / 2 |
| Exact upper population count | 33 | 12 |
| Upper fraction | .04888888888888889 | .037383177570093455 |
| CDF at upper / next count | .0008016571208971007 / .0005864425336653075 | .0013723523993952578 / .0005773069842509802 |
| ≤ .15 / breach certificate | pass / none | pass / none |

All compared fields agree exactly. Detailed stratum counts and results: `/tmp/s4r2_independent.json`. Existing screen/launcher/collector suite: **64 passed** (`/tmp/s4r2_screen_tests.log`).

### Adapter, bypass and access assessment

`textfree/export.py --check` exits 0: **47 files rebuilt, 0 differ, 0 extra**, after running the real guard. The equivalence assertion was actually run against **16 source label files** (five per pilot and three per fix-check round), not the README/dispositions' stated 22. Every `validator_summary` entry in `manifest.json` is accounted for. `common.py:330–365` compares summaries, accepted ids and labels (and MD alternative categories), line positions/reasons, warning/retry lists and canonical label outcomes. The actual round-1 adjudicator's six conflicting duplicates and 24 collapsed duplicate warnings survive; the historical pilot's 198 out-of-assignment calibration rows remain out of the pilot calculation. Per-dataset alternative token numbering and sort-preserving stratum codes avoid changing those duplicate classes or numerical summation order. The full public recomputation checks the resulting arithmetic against the retained results. I find no changed reported precision, interval, agreement, reference, gate or sensitivity result in this dataset. The explicitly omitted PHRASE alternative-wording diagnostics and historical adjudicator qualification cannot be independently reproduced by this route. The supplied schema/content assertions do not release actual wording in these stand-ins.

Bypassing `package.check_package` is **acceptable for conditional numerical recomputation**, provided it is not called independent certification of production eligibility, delivery, sampling provenance or the registered package chain. That function does much more than hash text-bearing files: `fixcheck/package.py:33–62,81–101` re-derives crosswalks, selections/assignments, delivery/retry provenance and checks runtime. `recompute.py:630–637` supplies an empty external procedure-problem list and substitutes recorded source paths/hashes for the synthetic label files. The equality of those reported metadata is a consistency check against the export manifest, not an independent hash of the private original by a public reader. `export --check`, run here against the preserved originals, establishes this projection's fidelity; supervised access remains necessary for full provenance/semantic inspection. No report should turn the 72 checks into a claim of 72 independent integrity tests or correct semantic labels.

The tier-3 route is concrete enough in its basic specification: `study4-archive.md:189–195` names Quang Nguyen, a repository issue URL/title, requested information, permitted commands/inspection, no-transfer conditions, a preserved-input check and an access log. An external reader can initiate it without a private address or unspecified future agreement. I did not contact the custodian, test issue creation or make any network request; there has been no real access request, so response time/availability has not been demonstrated. A service-level guarantee or institutional custodian is not needed to resolve R1-1, but the immutable-log conflict below must be corrected. Supervised permission to inspect is an access commitment, not proof of legal clearance or of an independent human reference.

### Freeze controls

Own in-memory controls: `/tmp/s4r2_freeze_controls.py`, results `/tmp/s4r2_freeze_controls.json`. Baseline reproduces the committed manifest, including real receipt/tar verification. Twenty substituted dependency digests are all detected: pool, final-pilot provider/receipt/validation/checksum list, historical pilot labels/key/provider and historical simulation key, ratecheck, SUMMARY, fix-check calculation code, receipt target, immutable archive tar, detector source, final-pilot label, access log, text-free key, review dispositions and screen ruling. Receipt-target and tar changes raise integrity problems rather than merely changing a manifest field. Model `config.cfg` byte substitution is rejected against RECORD; a substituted release working-tree blob is rejected against `v0.4.0`. Five omitted-enumeration controls change the manifest and are caught by comparison. A direct missing mandatory `A_merged.jsonl` control produces missing/unreadable problems. Changes confined to `observed` are intentionally ignored.

The builder's blanket phrase “Every input is required” overstates *standalone construction*: most recursively inventoried files are not independently required by `KEY_FILES`, so omitting a provider file can yield a smaller manifest without a construction problem. Crucially, comparison against the already committed manifest still detects this deletion. I do not treat that alone as another deposit blocker, provided the verified complete manifest is the external anchor and it is never silently regenerated to legitimise a missing file. The late-evidence omissions below are different: those files have no entry to compare at all.

Own additional controls (`/tmp/s4r2_freeze_gaps.py`, `/tmp/s4r2_freeze_gaps.json`) find no difference and no problem for changed bytes of the later `round2/transcripts/ACCESS_REVIEW_RULINGS.md`, `post_decision_events/SHA256SUMS`, its README, historical access-review tooling, or the final release-audit r2 report. The immutable labelled tar independently authenticates an older round-2 ruling: tar member SHA-256 `4bca7adbe6120b025b08c5228e1c7f250b09207c7ca308c1c14b34f7b52f1c8b`; current amended ruling `866e73651ef94dbcc333ee403e9494cd9ed3f43a15a6dd3c8ae46c25384cb5f6`. The post-decision directory is not in those tars. Merely freezing tar receipts does not bind these later records. I repeated the two decisive substitutions (the amended ruling and a resumed-session transcript) with full tar verification enabled and a baseline equal to the committed manifest: both still give zero differences and zero problems (`/tmp/s4r2_freeze_gap_fullcheck.json`).

### Screen, rulings and re-collection

`/tmp/s4r2_recollect.py` screens the real archive with all four operational assignment manifests. Ten pilot sessions plus three dry-run sessions have no technical/context failure or inventory/coverage problem. Twelve are clean; primary-A-02 has exactly the known code-like Edit flag. With the committed exact ruling, all **four delivered label files and four retry manifests** match the archived bytes. Original per-batch validation information also agrees; new screen/ruling/code provenance fields legitimately differ from the earlier validation reports. This independently verifies the maintainer's re-collection claim without touching any input.

Own synthetic controls in `/tmp/s4r2_screen_controls.py` verify: a valid session is accepted; missing provider context, empty base instructions and a context marker are rejected even with a correctly bound acceptance ruling; a path flag is rejected without a ruling and accepted with its exact ruling. Thus a ruling cannot accept a *detected* context-marker hit or technical failure (`collect_role.py:118–126`). The screen remains a heuristic backed by transcript examination, as the revised prereg now says. It is not a filesystem sandbox or proof that no unrecognised access occurred.

Two own negative controls still pass improperly: after a clean screen is saved, appending a launch-log entry for an absent session leaves collection permitted; an assignment manifest with `batches: []` produces an empty label file and successful validation. Details are below. Separately, the committed “human” ruling credits a Claude Code review session; its human attribution needs correction or an actual human approval record.

### Simulation, exclusions, effects and overall protocol

Own `/tmp/s4r2_sim_check.py` and `/tmp/s4r2_sim_check.json` verify **58 unique cells / 244,460 replicates in each historical/final bundle**, the exact main/grid scenario × module × population-seed inventory, replicate ranges, parameter identities, complete statuses, raw-run/merged cell equality, result-file hashes, current final-run source hashes and both key/frame hashes. The only grid parameter changes are the four low-precision-050 cells; all six main-pilot cells are also recalibrated. All other grid parameters/seeds are retained. I regenerated the finite synthetic populations, not the hundreds of thousands of sampling replicates: all **116** populations match the retained P, D, N, allocations, census/unobserved counts and shifts. Repeating that population construction using the public coded keys/frames gives the same ordered numerical unit attributes in every cell. Coded names change identifiers but preserve the design and random-draw allocation. This supports using the public designs for synthetic reruns with the appropriate frozen scenario/source version; the README should explain the changed input hashes rather than implying they are the original raw keys.

Independent binomial-tail inversion (log-combinatorial probabilities, no project CP implementation and no SciPy dependency) gives:

| Final main scenario | Largest tail count / 23,410 | CP two-sided-95% upper endpoint | Mean-width range |
|---|---:|---:|---:|
| Primary | 66 | .0035854739 | .1489448–.1617773 |
| Resolution region | 61 | .0033459202 | .1494403–.1626831 |
| Concordance, pass 2 | 0 | .0001575647 | .1388809–.1621894 |
| Concordance, pass 1 only | 0 | .0001575647 | .1915873–.2080213 |
| Korn–Graubard | 903 | .0411194612 | .0854371–.1153146 |

Final main-realistic population precisions are .6612292635, .7484693365, .6757255855 and .6631536686: the revised .661–.748 range is correct. Grid primary/region maxima are .1515/.005 (historical .134/.003); all concordance tails in both complete bundles have zero misses. The revised SUMMARY and prereg correctly distinguish matched-cell changes from scenario-wide maxima and synthetic stresses from version effects. No estimator source was changed by the reviewed commits, and no simulation rerun is indicated. The original checkpoint-body evidential limitation described in round 1 remains; the current complete run/merge and execution log are retained. Full sampling-replicate coverage was not independently rerun in this review.

`final_inventory.py --check` succeeds (inventory SHA-256 `ab50507744faa38adb14e313b0339ed8d6c8e56a55ab018ca1a07d4ec3672314`). Its computed inventory has 909 JSON records, 331 aliases, one comment, 1,241 lines, 3,132 additional identifiers, 440 canonical-development identifiers, nine shared and 3,563 in union; the v1 file/inventory remain unchanged. No exclusion source or evaluation command changed in this diff. The documented mkdir/copy preparation addresses R1-8. I ran no evaluation command and fetched no evaluation text. The public metadata alone omit title aliases, as detailed in R2-5; that is an access/recomputation limitation, not a demonstrated failure of the actual frozen exclusion union.

The effects JSON and detector bytes are unchanged from the independently recomputed round-1 package; the only effects change is the appropriately qualified procedure-disclosure sentence, mirrored in its generator. The new freeze checks the working-tree release blobs and every stage-receipt target and immutable tar. The 16 October provider archive contains 14 session records plus its README and checksum list; all 15 checksum targets verify, and all 16 files are bound in the new manifest. The missing original OpenCode context remains explicitly unrecoverable. No absent transcript has been manufactured or treated as current-pilot evidence.

The prereg continues to specify precision conditional on the finite hit population, a model-only operational reference, both resolution-adjusted limits and a worst-case region, pointwise coverage, descriptive maintainer concordance, no learner-writing or recall/completeness inference and no independent human reference. Those limits are coherent. The new CLI-version sentence (`prereg:325`) is a reasonable prospective allowance: it records pilot versions and requires evaluation probes/dry run under the versions used, rather than silently treating installed 2.1.305 as pilot 2.1.304. Operationally, archive the actual evaluation client version for every role (including an external version record for OpenCode), and stop before accepting labels if a later auto-update introduces a version not covered by the successful probes/dry run. A substantive prompt/tool/context change still invokes the registered amendment/deviation rules; repeating probes does not authorise a different reference procedure.

## New findings

### R2-1 BLOCKING — Freeze the late provenance addenda and their verification dependencies

**Locations:** `scripts/validation/study4_precision/pilot040/freeze.py:291–327,411–414,441–454`; `docs/validation/study4-archive.md:73–74,89,113,192,201`; private `lexinspect-private/study4-fix040/round2/transcripts/ACCESS_REVIEW_RULINGS.md:13` and `post_decision_events/README.md:19–36`.

**Evidence:** the rewritten builder binds the historical round tars and receipt targets, but not the later amended round-2 access ruling or the separate post-decision evidence. Own digest substitutions at each of those paths leave the manifest identical and `PROBLEMS` empty. The real tar contains the earlier ruling hash given above, not the current R2-4 addition. The resumed-task records document rewritten working copies, their separation from archived deliveries and cancellation; they are specifically promised for tier-3 verification. `post_decision_events/` is outside the frozen tars. Historical launcher/access-review scripts and the final release-audit r2 report are also unbound. These are provenance/disposition inputs, not disposable synthetic harness output. The current freeze therefore cannot authenticate all of the final account promised to an external inspector. This is the residual part of R1-2; the substantial improvements to arithmetic-input drift checking pass.

**Required fix:** add a required, explicit inventory of the late access-review addenda, the entire post-decision record directory and the historical verification scripts actually needed to reproduce the access reviews. Bind the specific retained release-review reports/dispositions cited as evidence (or a versioned immutable bundle containing them), without recursively freezing the irrelevant 14 GB working area. Existing immutable tars/receipts must stay unchanged. Include this review and the maintainer's round-2 dispositions in the final public package. Add in-memory controls showing that changing or removing a late ruling, resumed-session transcript, post-decision checksum target or cited final review is detected. If some report is intentionally not a deposited scientific input, identify its exact hash, preservation location and access limitation rather than treating all private working material alike.

**Exact replacement for the freeze builder's “fix check” inventory bullet (`:27–29`), to implement and then state:**

> The fix check: its tracked public records; every current file named in the stage receipts; the unchanged archived tars; the later access-review addenda; the post-decision event archive, including its checksums and their targets; and the versioned inventory of retained launch/access-review scripts and cited review reports. The manifest separately identifies the immutable decision-time packages and the later disclosure evidence. Both are required and checked against the deposited hashes.

**Exact addition after archive `:192`, once implemented:**

> The freeze includes both the unchanged decision-time packages and the separately identified later evidence: the amended round-2 access-review ruling, the post-decision event archive and the verification/review records named in its dependency inventory. Earlier tar members are not substituted for later addenda. A changed or missing required record stops verification.

This is a preservation fix. It does not reopen the numerical decision or require replacing a historical tar.

### R2-2 SHOULD-FIX — Separate the mutable access log from the immutable scientific manifest

**Locations:** `scripts/validation/study4_precision/pilot040/freeze.py:441–451`; `docs/validation/study4-archive.md:192–193`; `docs/validation/study4-access-log.md:3–8`.

**Evidence:** every request/session must enter the log, and `freeze.py --check` must pass before an inspection. The same check compares the current log bytes with the Stage-1 log hash. My in-memory changed-access-log control yields a manifest difference at `/protocol/docs/validation/study4-access-log.md`. Thus the first recorded request makes the pre-inspection check fail even with every scientific input intact. Regenerating the scientific manifest after each access request would defeat the external freeze.

**Required fix:** preserve the deposit-time log snapshot/hash in Stage 1, and keep subsequent access entries in a separately versioned append-only administrative record. Scientific `--check` must continue checking every fixed input while treating only that named administrative record as mutable. Record the exact request-log version/hash with each inspection; do not generally ignore archive-policy, review or input changes.

**Exact replacement for archive `:192–193`:**

> Preserved inputs: before each inspection, `pilot040/freeze.py --check` verifies the immutable scientific inputs against the Stage-1 manifest. Stage 1 retains the initial access-log snapshot and its hash. Subsequent requests and inspections are appended to a separately versioned access log, outside the immutable scientific-input comparison; recording an access request never requires rebuilding the scientific manifest. Each inspection records its date, requester, request issue, inspected material, commands, outcome and the access-log version/hash.

Mirror this distinction in the builder and access-log header, and verify that appending a request leaves scientific checking usable while a changed pilot/late-evidence input still fails.

### R2-3 SHOULD-FIX — Refresh archive-level checks at collection and reject empty assigned stages

**Locations:** `scripts/validation/study4_precision/pilot040/collect_role.py:59–74,155–179,224–249`; `check_sessions.py:566–602,619–625,653–667`.

**Evidence:** `load_screen` trusts the saved archive-level `inventory_problems`, while `accept` refreshes only each matched session. In my `/tmp` fixture, a screen is clean, then a logged delivered A session with no archive is appended to the launch log. A fresh archive screen reports the missing archive, but `collect_role.main` returns 0 and writes B's labels using the earlier screen. Separately, `batches: []` skips all checks and writes an empty label file, empty retry manifest and success report. `check_sessions.coverage` rejects such an assignment only if explicitly invoked; the collector neither requires that coverage nor rejects the empty manifest itself. These are negative controls, not claims that either occurred in the retained pilot.

**Required fix:** recheck the current archive/log inventory at collection and ensure the saved screen is tied to that inventory (for example, current launch-log digest and session inventory). Require the non-empty assignment manifest for an invoked collection stage; when no adjudication/retry is assigned, record that as a not-applicable stage rather than a fabricated successful collection. Fail before writing output. Keep the existing exact-session/ruling checks.

**Exact replacement for the collector's description of acceptance (`:10–17`):**

> The collector checks the current archive against its launch log and the non-empty assignment manifest before accepting any labels. The saved screen must match the current archive inventory and the session records. Missing, additional or inconsistent records stop collection pending technical recovery. A stage with no assigned items is recorded as not applicable and is not collected. No label is generated or chosen.

Add controls for an appended missing-session log entry after screening, a removed/unlogged archive after screening, and an empty assignment list. All four real pilot label/retry outputs must remain byte-identical.

### R2-4 SHOULD-FIX — Identify the actual reviewer of the pilot flag

**Locations:** `docs/validation/study4-pilot040/screen_rulings.jsonl:1`; `docs/validation/study4-pilot040/LAUNCH.md:54–56`; prereg `:323`; `scripts/validation/study4_precision/pilot040/collect_role.py:19–26,88–126`.

**Evidence:** the policy and collector call this a “recorded human ruling”, but the actual record identifies its reviewer as `maintainer (Claude Code session acting for the maintainer)`. It says the examination was made in that session. This is an accountable agent-produced record, but it is not evidence that Quang Nguyen personally examined the transcript. The code only requires a non-empty reviewer string; it cannot establish the reviewer's identity. My technical recheck supports the flag's stated narrow disposition and the byte-identical label outputs; it does not supply the absent human act.

**Required fix:** record a dated, actual maintainer review/approval of this specific call, if performed, keeping the agent's original examination in the provenance; otherwise explicitly disclose the pilot's agent-produced ruling as a departure from the stated human-review procedure and retain the human-review requirement for evaluation. Do not retrospectively describe agent examination as human validation. This concerns the single procedural flag, not a new human labelling study.

**Exact truthful addition to LAUNCH after the pilot-screen paragraph, unless a separate human approval is actually documented:**

> The pilot flag was examined by a Claude Code session acting for the maintainer, as the ruling's reviewer field records. The retained ruling does not document a human transcript examination. Its technical disposition and the unchanged collected bytes were independently reproduced in Stage-1 review. This agent-produced pilot ruling is disclosed as a departure from the human-review procedure; evaluation flags require the maintainer's dated examination and approval before collection.

If the maintainer personally approves it later, add a separate approval with the actual date, person, session hash and flag hash; preserve the original record. Clarify in the collector documentation that it verifies the ruling's completeness and binding, while human identity/approval is an operational commitment.

### R2-5 SHOULD-FIX — Bound the remaining historical-context and package-verification claims

**Locations:** `docs/validation/study4-archive.md:128`; `study4-pilot040/CORRECTION_F1.md:14,26–27,32`; `study4-pilot040/LAUNCH.md:89`; `docs/validation/study4-textfree/README.md:42,53,65,68`; `scripts/validation/study4_precision/fixcheck/package.py:33–62,81–101`.

**Evidence:** the applied F1 paragraph is appropriately bounded, but surrounding current text still says no branch/candidate/label information “reached” B/C and “No session read or listed a file outside its batch directory”, without consistently restricting that to retained records. The original pilot adjudicator record is missing. The archive's “no 0.4.0 or evaluation result depends on those sessions” is stronger than no direct label reuse: the chosen evaluation adjudicator qualified using that pilot and its labels; historical development informed the detector. These indirect dependencies are explicitly acknowledged in prereg `:125,139,287`.

The recompute README describes the bypassed package checker as a file-hashing operation and says its empty `procedure_problems` field is reproduced. In fact, the checker also re-derives design/delivery facts and checks runtime, and the adapter supplies `[]` as its external problems input. Arithmetic reproduction is sound, but it must not be mistaken for revalidated procedure completeness. Its exclusion note also says the public development manifest carries the identifiers the union needs. In fact, it drops all 120 title references: it reconstructs 320 of the original 440 development identifiers and a 3,448-identifier union, missing 115 identifiers not present in the additional manifest. Exact union verification still needs the archived canonical manifest. These are wording corrections; I accept the bypass for its declared numerical purpose.

**Exact replacement for archive `:128`:**

> Not recovered: no OpenCode session record of the 16 October adjudicator runs was found. This is an irretrievable gap in historical effective-context evidence. No label from those runs is reused in the 0.4.0 common pilot or evaluation. Those labels did contribute to historical development and to the original adjudicator qualification retained for evaluation; the missing context cannot be independently inspected.

**Exact replacement for CORRECTION_F1 `:14`'s final sentence and `:26`'s final sentence, and the corresponding assertion at LAUNCH `:89`:**

> In the retained model-visible records inspected, we found no branch/commit snapshot, candidate-direction information, item-level version/family assignments or other labellers' responses. This conclusion is limited to those records; the original pilot adjudicator's effective context was not recovered.

**Exact replacement for CORRECTION_F1 `:32`:**

> In the retained labelling records included in the rescreen, we found no read or listing outside the session's batch directory and no command with a relative path. This does not establish the contents of unrecovered records or undisclosed provider-side context. Review sessions that only quote the prompt are excluded by the first-instruction rule.

**Exact replacement for the README bypass bullet `:42`, with an addition after its comparison table:**

> `fixcheck.package.check_package` is not run. Besides checking private-file hashes, it re-derives crosswalks, selections and assignments, authenticates delivery/retry provenance and checks runtime. The text-free run verifies the conditional arithmetic from exported keys and labels; it does not independently revalidate those production/provenance conditions.
>
> The external `procedure_problems` input is set to an empty list, matching the retained arithmetic run; its equality is not a fresh procedural audit. Reported original label-file paths and hashes are checked against the export's recorded source metadata, not derived by hashing the synthetic files. Full-chain verification requires the preserved packages and supervised inspection.

**Exact replacement for README `:68`:**

> The exact exclusion union cannot be reconstructed from this export alone. Its development metadata preserve 320 of the canonical manifest’s 440 normalised identifiers; the 120 title references were omitted. Combining it with the public additional manifest gives 3,448 identifiers, rather than the frozen 3,563. Exact union verification requires the archived canonical development manifest through supervised access.

### R2-6 NIT — Finish the status, licence and inventory documentation

**Locations:** `docs/validation/study4-textfree/README.md:3,85,190,194–198`; `docs/validation/study4-stage1-review/r1_dispositions.md:12–13`; `docs/validation/study4-archive.md:55,58,114`; `docs/validation/study4-exclusions/tools/final_inventory.py:302`.

**Evidence:** the committed export still calls itself “not yet committed”, suggests a licence that archive section 7 now grants, and retains fulfilled freeze/licence open points. It says 22 label files; the manifest and exporter have **16**. The archive still says five pilot records and a “proposed” correction, and calls the committed `/2` manifest an “untracked draft” with empty deposit fields. The historical-simulation row describes only three manifest hashes although the entire bundle is now inventoried. The new exclusion inventory's lint note says all `*.py` are excluded even though the config correctly excludes only four archived builders. These are documentation defects, not numerical defects.

**Exact replacements:**

- Export `:3`: “**Status:** committed public text-free export for Stage-1 review; not externally registered until the Stage-1 deposit receipt is recorded.”
- Export `:85`: “For each of the **16** source label files, `export.py` checks equivalence under the frozen validator (five files per pilot and three per fix-check round).” Retain the description of which result fields are compared.
- Export `:190` opening: “**Licence:** CC BY 4.0 for this folder, as confirmed in `study4-archive.md`, section 7.” Keep the factual content-removal description. Replace open point 1 with “Licence confirmed: CC BY 4.0”; replace open point 3 with “The committed freeze manifest inventories the export and its `SHA256SUMS`; the final registration commit and deposit receipt will identify the externally deposited version.” Append an erratum to the round-1 dispositions' “22” claim rather than silently rewriting the historical response.
- Archive `:55`: “`study4-pilot040/` (6 tracked files): plan, launch record, results, applied F1 correction, selection hashes and screen ruling; the Stage-1 manifest binds all six.”
- Archive `:58`: “`study4-freeze.json`: committed Stage-1 scientific-input manifest, format `study4-freeze/2`; the external deposit service, identifier, final package commit and receipt are recorded separately in `study4-freeze-deposit.json`.”
- Archive `:114` integrity cell: “`result_hashes.sha256`; the complete bundle is inventoried file by file in `study4-freeze.json`.”
- Final-inventory generator `:302`: “Excludes only the four archived builders from ruff; `final_inventory.py` remains linted. This configuration builds nothing and changes no scientific output.” Rebuild its JSON and update the README inventory hash after that correction.

## What should enter the Stage-1 deposit

After the listed fixes, deposit an identified, immutable package with a top-level file/hash index and a short offline verification README. It should contain:

1. **The final preregistration and public scientific record.** Include the fix protocol/clarifications, both rounds' public decisions/receipts/rulings, sensitivity plan/results/control, complete effects report/JSON, exclusion folder and access policy. Fill the **Stage-1** reviewer-count slot at prereg `:304` with the actual two methodology-review rounds and their identities/links; retain the intentional **Stage-2** evaluation-count/build placeholders. Preserve the disclosure of this reviewer's shared model family with labeller B. Do not represent repeated model review as independent human validation.
2. **The final `/2` freeze manifest and its versioned dependency inventory**, after binding the late evidence and final review records. Include r1/r2 review reports and their dated maintainer dispositions, with unresolved objections explicitly disposed. The exact final package commit belongs in the external deposit record; it is distinct from detector release commit `0556d0826001112eb6a82d08883e3592d05010ea`. Recheck the final committed package. A receipt sidecar must identify OSF service/record or immutable version, UTC deposit time, the final package commit, manifest digest and receipt/link. If the receipt is obtained after upload, retain it as a clearly linked supplemental record; do not regenerate the scientific manifest to insert it. The absence of a receipt before depositing is expected.
3. **All 47 text-free export files**, with corrected README, `manifest.json` and `SHA256SUMS`, plus the frozen `textfree/` code and the analysis/acceptance code it imports. Include a Python/dependency/environment record and the lock file. Keep the limitations on PHRASE alternative wording, original adjudicator qualification, exact exclusion-title aliases, production provenance and semantic correctness explicit.
4. **Both complete simulation bundles**, `study4_scratch/sim040/` (16 files) and `sim_final/` (12), including inventories, raw and merged outputs, Markdown summaries, logs/checkpoint metadata, tail tables, source/result checksums, and the final run's ratecheck script/output. Also include the separately inventoried `study4_scratch/tools/tail_table.py`, which is outside either bundle. Preserve the correct simulation source versions: all six historical source hashes match the files at `v0.4.0`; the final run's `simulate_coverage.py` and `build.py` are later versions. Include those small matching source snapshots, or an immutable repository artifact preserving both revisions, rather than only a link to a moving branch. The public pilot keys/frames provide equivalent coded simulation designs (verified above); document how to use them and that their hashes/names differ from the original restricted inputs. Exact original-input inspection remains tier 3.
5. **A custody/access index for restricted inputs**, keyed to the final manifest. It should identify the unchanged round tars, original and final pilot inputs/labels/provider records, late addenda/post-decision evidence and the historical OpenCode gap; identify which bytes are held only on the custodian's machine and covered by supervised access. Public OSF upload need not contain source bodies, PHRASE inventory/guideline material, note-bearing labels or transcripts. Hashes/access commitments do not establish independent off-machine preservation of restricted files; make that custody limit explicit. Retain the initial access-log snapshot and the separately versioned ongoing log as fixed under R2-2.

The proposed OSF selection is therefore substantially correct. Its important additions are the separate tail-table tool, source versions needed for the historical simulation, a precise restricted-evidence index including the late records, the final review/disposition pair and a usable administrative receipt/access-log boundary. No evaluation collection/build, labelling or deposit was performed in this review. Evaluation remains unopened until Stage 1 is externally retained and its receipt is recorded; Stage 2 remains the single later build deposited before evaluation labels.

## Audit limits and final disposition

This is a read-only methodology/package review. All authored files, synthetic fixtures and calculation outputs are under `/tmp`; repository/private inputs are unchanged, and the original four unrelated untracked files are unchanged. No state-changing Git command, network request, model-label generation, source collection, detector build or deposit was run. The requested label re-collection only reads existing deliveries and writes `/tmp` outputs. No additional agents were used. I did not independently relabel the corpus, establish linguistic correctness or adjudicate redistribution rights. Provider-side hidden state and future access responsiveness cannot be certified from retained local records.

Round-1 findings R1-5 to R1-8 are resolved. R1-1 to R1-4 are substantially improved but partly resolved for the specific reasons above. The arithmetic, text removal and retained pilot delivery claims pass the requested controls. R2-1 remains a deposit blocker because the final provenance account still lacks a complete external binding; the remaining changes are bounded workflow, attribution and documentation fixes.

**Final finding counts: 1 BLOCKING, 4 SHOULD-FIX, 1 NIT.**

NOT READY — 1 BLOCKING, 4 SHOULD-FIX, 1 NIT.
