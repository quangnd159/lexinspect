# Dispositions of Sol harness audit r5 (sol_harness_audit_r5.md)

2026-10-17. Before any fix-check text or label. 0 BLOCKING. All findings adopted per the audit's "Exact fix"; no gate, J, allocation, family identity or exposure rule changes.

- **R5-S1.** Adopt: under the registry lock, apply the file+directory barrier before returning `present`/`idempotent`; persistent failure refuses; tests for broken-then-repaired retries for reservation and decision; terminal retry handling documented.
- **R5-S2.** Adopt: full schema validation in `_wiki_body_refs` (and the Europe PMC counterpart if analogous); anticipated corrupt-body/read/schema errors become incomplete-exposure diagnostics, never a crash; authentication failures still refuse. Real abort → registration tests for null/scalar page, null/scalar revision, unreadable/truncated body: one failure decision, exposure incomplete, both non-pass terminals allowed, no round 2.
- **R5-S3.** Adopt: explicit warning in the runbook and clarifications that a completed genuine shortfall exhausts its stratum for the frozen pool snapshot, so round 2 cannot fill it and only terminal / reviewed-amendment routes remain; distinguished from early interruption; real listing headroom (section 6 table) included with its limits.
- **R5-M1.** Adopt: same-output, identity-checked recovery without `--overwrite`; test interruption after each output write; correct the write-order prose.
- **R5-M2.** Adopt: section 9 keeps the shared append-only registry and omits empty-registry initialisation.
- **R5-M3.** Adopt: replace the shell scan with a small Python byte scanner (paths/counts only, fails on I/O errors, nonempty fragment file required, staged-blob coverage kept).

A short confirmation audit (r6) follows, scoped to these items and regressions.

## Addendum: maintainer rulings on HARNESS_R8_SUMMARY.md (2026-10-17)

1. **Identical terminal re-acknowledgement:** accepted as implemented (same outcome and basis, last registry line, passes the barrier → `present`; anything else refused).
2. **Truncated or unreadable start record.** Registrable as `procedure_failure`, so the round is never stranded, under these rules: the reservation, freeze record, receipt and failure archive must still authenticate; the start record is recorded as "unreadable" with its raw bytes hashed. Because the journal is created only after the start record is durably written, **if no journal file exists**, no request can have been made: exposure is the empty set and complete, and the normal round-1 continuation applies. **If a journal file exists** (whatever its state), exposure is recorded as incomplete and only the terminal routes remain. The consumed-round refusal is unchanged. Tests for both cases.

## Revision of Addendum ruling 2 after sol_harness_audit_r6.md R6-B1 (2026-10-17)

Ruling 2's zero-exposure exception is **withdrawn**. The maintainer's premise was wrong: the absence of a journal and an unchanged cache do not prove that no request was made, because evidence can be lost and failed or cache-read requests leave the cache unchanged. Corrected rule:

- An unreadable start record is still registrable as `procedure_failure` (the round is never stranded), with the same authentication requirements.
- Its exposure is **always incomplete**. Only the terminal routes remain (revert to 0.3.3 or a reviewed amendment); round-2 reservation and planning refuse. Any safely recoverable identifiers (abort fetch log, archive-held journal, cache entries) are recorded for diagnostics only, without claiming completeness.
- `archive_problems` requires bidirectional presence-and-hash agreement for every optional execution-evidence member: an archive member with no local counterpart, or a local file absent from the archive, is a problem.
- Regressions: both audit probes (A and B), missing journal with failed requests and unchanged cache, completed-collection evidence under an unreadable start; each gives incomplete exposure, round-2 refusal, and both non-pass terminals available. The existing changed-cache and present-journal tests stay.

## Ruling after sol_harness_audit_r7.md R7-B1 (2026-10-17): exposure completeness needs an authenticated endpoint

General rule, replacing all branch-specific inferences: a failed or interrupted round's exposure is **complete only if an authenticated endpoint record fixes the full request history**. That means one of:

- a completion record (`execution.json`) whose recorded journal SHA-256 and fetch log match the journal byte for byte; or
- an abort record whose recorded `fetch_journal_sha256` and fetch log match the journal byte for byte, with the journal ending exactly at that endpoint.

In every other case (hard interruption with no endpoint record; missing, empty, shortened or hash-mismatched journal; unreadable start), exposure is **incomplete** and only the terminal routes remain. Recoverable identities are kept as diagnostics only. Absence of evidence never implies zero requests. The abort/completion writers must record the journal hash (add if missing), written after the journal's final durable barrier. Regressions: the audit's three cases with a readable start (missing, zero-byte, valid two-pair prefix after 10 failed fetches and a hard exit), plus a hash-mismatched journal with a valid abort record; each gives incomplete exposure, round-2 refusal, no extra registry line, both non-pass terminals, and no re-execution. Keep the unreadable-start and two-way archive cases.
