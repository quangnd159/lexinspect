# Dispositions of Sol harness audit r3 (sol_harness_audit_r3.md)

2026-10-17. Maintainer decisions, before any fix-check text or label. All findings adopted exactly as the audit's "Exact fix" states; no gate, threshold, n or allocation changes.

- **R3-B1 (single execution).** Adopt. Per-reservation exclusive execution lock held from gate recheck through completion; immutable execution-start record created with exclusive creation (O_EXCL), bound to reservation/freeze/argv, fsynced with its directory, before the first possible fetch; any later invocation for that reservation refuses forever (including after failure/abort/crash). Completion/abort evidence written separately; no production overwrite/resume. Fetch evidence preserved on exceptions, but the guarantee rests on the start record, not the handler. Regressions: two-process barrier, hard exit (subprocess `os._exit`) including a failed request leaving no cache file, failure after `collect_with_build` returns.
- **R3-S1 (registry vs receipt).** Adopt. The receipt authenticates the registry's committed blob as a historical prefix; the current registry must extend that prefix byte-for-byte and pass integrity/history/rule checks. Immutable inputs keep exact equality. Integration regression through the real package check: receipt → registered decision → recheck/reaccept/recovery stays valid and idempotent; rewritten/truncated/non-prefix registry refuses.
- **R3-S2 (runbook restricted content).** Adopt. Remove `study4-guidelines.md` from the public allowlist and staging set; replace the stale stop paragraph with the Addendum ruling (guidelines hash-bound, private). The pre-label private archive explicitly includes byte copies of the frozen guidelines and sense inventory with SHA-256; public files carry hashes only. The restricted-content scan checks staged blobs (`git show :path`) as well as the worktree.
- **R3-S3 (acceptance runtime).** Adopt. Production acceptance freshly computes runtime/artifact identity (Python, numpy/scipy and other numerical dependencies actually imported, spaCy and model package file hashes, installed lexinspect source hash) and requires equality with the frozen identity before deciding; the observed identity enters the complete-input identity and output. Real package-check regression with changed current runtime and untouched historical files ⇒ production refusal.
- **R3-M1.** Adopt: report observed R4 vs R5 counts (198 → 199 at .005/development-share) and the cause; keep both archives.
- **R3-M2.** Adopt: the Addendum's sentence in HARNESS_AUDIT_R2_DISPOSITIONS.md is qualified (below).

## Correction to HARNESS_AUDIT_R2_DISPOSITIONS.md Addendum, "Calibrated scenarios"

The sentence "The fix-check therefore effectively decides between these two development pictures" is withdrawn. Corrected reading: under the two specified synthetic populations, with the declared loss allocation and reference model and a valid procedure, the all-gates pass frequencies are .980 and 0. This is a contrast between those two constructed populations only; no inference about true loss will be drawn from a future pass or non-pass.

## Addendum: maintainer rulings on HARNESS_R6_SUMMARY.md (2026-10-17)

1. **A failed, killed or aborted execution consumes the round.** The round is registered as `procedure_failure`, which is a non-pass. If it is round 1, round 2 may follow under the protocol's re-check rule (fresh, disjoint collection, distinct seed, separately frozen candidate); if it is round 2, the outcome is terminal: revert to 0.3.3 or a reviewed amendment. No retry of the same round, ever.
2. **R3-M2 annotation** in HARNESS_AUDIT_R2_DISPOSITIONS.md is kept (annotated, not deleted); its hash change is expected.
3. **Runtime frozen until acceptance:** the venv, `uv.lock` and lexinspect source bytes are not changed between freeze and acceptance.
4. **Wider spaCy dependencies:** not hashed individually. They are pinned with wheel hashes by `uv.lock` (installed with `uv sync --frozen`), and the run stage is verified by the pinned-baseline byte-equality check and the committed-candidate dry run. Disclosed in the runbook.
5. Remaining freeze steps are maintainer actions after harness audit r4.
