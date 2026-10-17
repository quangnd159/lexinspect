# Study 4 fix-check protocol: clarifications

**Date:** 2026-10-17 (revised the same day, after the second independent harness audit)

**Applies to:** `docs/validation/study4-fix-protocol.md` (the protocol). The protocol itself is not edited.

**Timing:** recorded before any fix-check text was collected and before any fix-check label existed. The file is committed with the freeze, and its hash is bound into every round's freeze record.

**Source:** the maintainer's dispositions of the independent harness audits r1 (B2, B4, B5) and r2 (R2-B1 to R2-B5, R2-S1, R2-S4, R2-M1).

These clarifications record how the harness reads the protocol's existing text. They are not amendments. They change no gate, tolerance, sample size, error budget (J = 68 components at a = .05/68) or decision rule. Each item below states its own effect. Where an item is a relaxation or is not monotone, it says so. It is not described as conservative unless it is.

**Withdrawn.** An earlier version of this file (item 1.1) put a claim dropped at a retained span into the removal gate's deletion frame, calling that conservative. That reading (maintainer ruling A2) is **withdrawn**. Enlarging the deletion frame with such claims can dilute the success share among deletions, so a candidate that breaches the protocol's removal gate could pass the enlarged one. Item 1.1 now uses the protocol's genuine-deletion population only.

## 1. Removal population and occurrence retention

The crosswalk gives each baseline emitted hit exactly one change type. The change types, in precedence order, are:

1. unchanged, multiplicity or display-context changed (key match);
2. reassigned;
3. span changed;
4. claim dropped at a retained span;
5. removed.

Two separate uses are made of this partition.

### 1.1 Removal gate: genuine deletions only

- **Population.** The removal gate's frame is the protocol's genuine-deletion subset: baseline hits with **no counterpart at the same occurrence**. That means:
  - no retained claim at the same span;
  - no span change, resolved or unresolved;
  - no reassignment.

  The harness calls this cell REMOVED. One simple random sample of min(200, N) serves both the removal bound and the REMOVED cell of U_loss.
- **A dropped claim at a retained span is not a genuine deletion.** Suppose the baseline made several claims at one span, and the candidate drops one of them but still emits another claim at that exact span. The dropped claim is in its own cell, CLAIM_DROPPED. It belongs to the affected-baseline frame and enters loss accounting (item 1.2). It never enters the removal gate's frame.
- **No extra screen.** No emitted-claim removal screen is added, and J stays 68.
- **Unresolved span changes.**
  - **Placement.** A baseline hit whose only candidate counterpart is an unresolved span change stays in the SPAN_CHANGED cell, under maintainer ruling A3, which the r2 dispositions do not withdraw. It is not in the removal frame. In U_loss it takes the worst case: it is a possible loss whenever its reference can be successful.
  - **Effect on the removal gate.** Putting these rows into the removal frame would not be uniformly stricter. Unsuccessful rows would dilute the success share, and successful rows would raise it.
  - **The reading kept.** The harness therefore keeps the population the frozen ruling defines: a hit with an overlapping candidate counterpart is not a proven deletion.
  - **The disposition's wording.** The r2 disposition lists "no resolved span change" among the conditions. Read with ruling A3, an unresolved span change is still a counterpart at the same occurrence, so it excludes the hit from the removal frame. This reading is recorded here so that it can be reviewed.

### 1.2 Loss accounting: occurrence retention

Loss accounting is U_loss and the definite and possible losses of "Definite and possible losses". It uses **occurrence-retention links**, which are kept separately from the change types.

**Links:**

- **Counterpart links.** Every baseline row links to each candidate counterpart that the crosswalk assigns to it. Each link has its own resolution (item 1.3).
- **Sibling links.** Every baseline row also links to each other candidate hit at exactly the same span: same source, same text, same module. These are its siblings. They include siblings that the crosswalk already matched to another baseline claim. A sibling has an identical span, so it is a same-occurrence link and is resolved.

**Retention rules:**

- **LENIENT and LIST_LENIENT.** The protocol defines success under these outcomes as "a supported occurrence in the same target inventory". So a definitely successful resolved sibling establishes retention. A CLAIM_DROPPED row is therefore retained under these outcomes if such a sibling remains.
- **STRICT.** Success means "a supported, correct emitted claim", so the row's own counterpart is required. A sibling never establishes STRICT retention. A correct CLAIM_DROPPED claim is a STRICT loss.
- **Unchanged rules.** Every other rule of the section stands:
  - an unresolved correspondence never proves retention;
  - merely overlapping output never proves retention;
  - acceptance uses the highest loss consistent with the references and the crosswalk, computed as item 1.4 states;
  - each baseline hit counts once;
  - additions never offset losses.

### 1.3 The span-change resolution rule (frozen)

**Purpose.** A span-change link between a baseline hit and a candidate hit counts as a resolved correspondence only when lexical and syntactic evidence shows that the two hits are the same occurrence of the same marker or expression. A link is resolved only if all three of the following hold.

1. **Same canonical marker or expression.**
   - Metadiscourse: the same normalised marker string (the hit's lexicon marker, case-folded, whitespace collapsed) and the same category.
   - PHRASE: the same list rank.
2. **Head token.** The candidate span contains the baseline hit's head token, or the baseline span contains the candidate hit's head token.
   - The head token is the syntactic root of the hit's span in the analysed text.
   - If the head token is not available, this condition fails.
3. **One to one.** The pairs meeting conditions 1 and 2 must be one to one. The baseline hit has exactly one such candidate, and that candidate has exactly one such baseline hit. Otherwise every link involved is unresolved.

**Further readings recorded here:**

- **Reassignment target.** The disposition allows "the same category, or the reassignment target". The harness has no declared map of reassignment targets, so the same category is required. A change that alters both the span and the category stays unresolved.
- **Geometry.** Nesting or overlap alone never resolves a link. Conversely, a pair that meets conditions 1 to 3 resolves whatever its geometry. For example, two overlapping spans that are not nested resolve if they share the marker, the category and the head token.
- **Everything else.** Any other span change is unresolved and takes the worst-case loss.

**This rule is not a restriction of an earlier rule.** It is described on its own merits. Compared with geometric nesting, it can resolve some links that nesting would not resolve, and it leaves unresolved some that nesting would resolve.

**The only before/after comparison made** concerns the archived development frames (development dry run r4). For COMPLETE, the earlier nesting rule left 62 of 74 metadiscourse span-change rows unresolved; this rule leaves all 74. Both rules leave all 6 PHRASE span-change rows unresolved. These counts describe those frames only. They are not a property of the rule.

### 1.4 Loss bounds with shared references: exact per row, relaxed per cell

**Shared payloads.** Two hits with an identical judgement payload share one reference variable.

**Per row (exact).**

- **Method.** For each sampled baseline row, the lowest and highest loss over every completion of the unresolved reference variables are computed analytically.
- **Exactness.** The computation is exact for any number of variables, with no enumeration and no fallback.
- **Shared variable.** A resolved counterpart that shares the baseline's reference variable makes the row's loss identically zero.

**Per cell (a declared relaxation).**

- **Method.** A cell's lowest and highest loss totals are the sums of the per-row extrema. The highest total therefore lets each row take its own worst completion, even where one variable cannot take both values for two rows at once.
  - Example: a variable x is a counterpart of a row whose baseline variable is y, and y is a counterpart of a row whose baseline variable is x.
- **Direction.** This is a **conservative relaxation**. The cell's highest total is at least the joint highest consistent completion, so U_loss can only be higher than the joint completion would give.
- **What it is not.** It is not the protocol's joint highest consistent completion. It is stated here as a relaxation, not as that completion.

## 2. Accepting that a round may be inconclusive (B5)

**The gates are deliberately strict.** Before any label exists, the harness reports two things.

- **Operational power of the frozen acceptance path.**
  - It runs by simulation through the real calculation, the actual crosswalk and the registered sampling design.
  - It reports the probability that every required statistical gate passes (conditional on a valid procedure), each module passes, each gate passes, and a breach certificate occurs.
  - Each probability comes with a Wilson 95% Monte Carlo interval.
  - The scenarios are declared before any label: the loss grid, the unresolved-row structures, and two module-calibrated scenarios at the development rates.
  - For each scenario, the target loss and the realised loss of the simulated population are reported separately. A nominally zero-loss scenario whose population nevertheless contains losses is flagged.
- **Feasible values on the archived selection.** Every reported configuration is one coherent set of references. This includes "a feasible value found by the declared greedy search", reported with its exact sampled loss and removal counts. Each value is attainable, and none is claimed to be an optimum.

**How to read these figures.** They are probabilities of outcomes under declared populations. An observed status does **not** license an inverse inference to a true loss level. In particular, an inconclusive result is not evidence of any particular loss.

**What an inconclusive result means.** It means 0.4.0 does not ship on that round. The only continuations are those in "Decision and re-check":

- one revised candidate, checked in round 2;
- reverting to the 0.3.3 baseline;
- or a dated, independently reviewed amendment before any further check.

**The maintainer's acceptance.**

- The maintainer accepts, now and prospectively, the chance of an inconclusive result shown by the reported power, which may be low.
- The maintainer will not seek an amendment prompted by labels or outcomes.
- This acceptance changes no gate. Nothing in the power report is chosen from check outcomes.

## 3. The round registry, the freeze and the archive (B2, R2-B1, R2-B2, R3-B1, R3-S1, R3-S3, R4-B1, R4-S1, R4-S2, R5-S1 to R5-S3, R5-M1, R5-M2)

### 3.1 The canonical registry

**One file.** There is exactly one round registry: `docs/validation/study4-fix040/round_registry.jsonl`.

- It is a tracked file, committed empty before round 1.
- Every freeze record binds its path and committed hash.

**Append-only.** The registry may only grow.

- The version committed at HEAD must be a byte prefix of the file.
- Every committed version in the history must extend the version before it.

**Refusal.** A missing, uncommitted, truncated, rewritten or substituted registry refuses before any production step. No other registry path is accepted in production.

**Lines.** The registry holds three kinds of line:

- **reservation:** written at planning, before collection;
- **decision:** written by acceptance, or, for a failed execution, by `register-failure` with the status `procedure_failure` (section 3.4);
- **terminal outcome:** written by `register-terminal`.

### 3.2 Reservation and freeze

**Reserving the round.** Planning reserves the round in the registry, atomically under a file lock. The reservation names the round, the candidate commit and tree digest, the seed and the collection directory.

**What the freeze binds.** The reservation is part of the freeze. The freeze record binds:

- the reservation;
- the registry;
- the delivery specification (routes and settings, prompt, preregistration hash, pilot-material hashes);
- the dispositions and rulings;
- the ledger and its components;
- this file and the protocol;
- the harness and runtime identities.

**Production collection refuses** without the reservation and without an archive receipt.

**One execution per reservation (R3-B1).** The protocol permits one frozen collection attempt, so a reserved round is executed at most once.

- The execution takes an exclusive lock on the round directory and holds it from the gate checks through completion. A concurrent invocation is refused.
- Under the lock, before the first possible fetch, it creates an immutable execution-start record with exclusive creation, bound to the reservation, the freeze record and the argv, and flushes it to disk.
- Every request is journalled before it is made.
- **Registry durability (R4 Addendum 1).** Every registry append (reservation, decision, `procedure_failure`, terminal) passes the same barrier on the registry file and its directory. Without a barrier the append is refused before anything is written. A failed barrier stops the command, and rerunning it never appends a line twice. The rerun finds the existing identical line (a reservation `present`, a decision or failure `idempotent`, the identical terminal outcome `present`) and acknowledges it only after the same barrier passes again on the registry as it is; a persistent failure refuses again (R5-S1). A different terminal outcome after a registered one is refused.
- **Durability (R4-B1).** "Flushed to disk" means a full durable-write barrier on the file and then on its directory, before the harness goes on. This applies to the start record, the journal's creation and every journal line written before its request. On macOS the barrier is `F_FULLFSYNC`, because plain `fsync` there does not order or guarantee writes across a power loss. On Linux it is `fsync`. Any other platform refuses before the claim. A failed barrier is never downgraded: the execution stops before the next request. The guarantee assumes that the storage device honours a full flush.
- **Journal integrity (R4-S2).** The journal is read as a strict sequence: request 0, outcome 0, request 1, outcome 1, and so on. Sequence numbers increase by one, only those two event names are allowed, and each outcome carries exactly its own request's identity and either one response or one failure. A completed collection has no request without an outcome, and its pairs must reproduce the fetch log. A failed execution's journal may end with one request that has no outcome. A malformed or truncated line is an integrity failure.
- Once the start record exists, no later invocation proceeds. This holds after completion, failure, abort, kill or crash. There is no overwrite or resume.
- Completion and abort evidence are written separately and never replace the start record.
- A production collection without a start record bound to its freeze record and reservation is an incomplete procedure. So is one with an abort record, or whose journal does not reproduce its fetch log.

### 3.3 The archive receipt

**Where the bound files must be.** Every bound file must be committed and byte-equal on the registered receipt ref, `refs/remotes/origin/study4-fix040-candidate`.

**Ref forms.** Only a full `refs/remotes/origin/<branch>` ref is accepted. HEAD, local branches, tags, raw object ids and revision expressions are refused. Round 2 uses the same registered ref.

**What the receipt records:**

- the canonical ref;
- the commit it resolves to;
- the remote's URL.

**How it is checked.** The check is local git only, with no network.

- It therefore depends on the remote-tracking ref being up to date. A successful `git push` of the branch updates it.
- Acceptance re-validates the archived receipt against the committed objects.

**The registry under a receipt (R3-S1).** The registry is the one receipted file that grows after its receipt. A receipt authenticates the registry's committed version as a historical prefix. The registry on disk must extend that prefix byte for byte and pass the current integrity, history and rule checks. A later reservation, decision or terminal line therefore keeps the receipt valid, and an identical package rechecks and re-accepts idempotently. A rewritten, truncated or reordered registry, a duplicate line or a line the rules refuse is a receipt failure. Every other receipted file must stay byte-equal.

### 3.4 Decisions

**Registration is atomic.** Production acceptance checks and appends the decision under the same lock.

- A production decision always registers.
- A computation that is not registered is a preview, and it is not a decision.
- The preview (`accept --check-only`) checks the hash chain only and reveals no gate arithmetic.

**What a decision line records:**

- the round;
- the candidate commit and digest;
- the seed and the reservation;
- the freeze record;
- the collected texts and canonical source identities;
- the delivered session ids and transcript hashes;
- a hash over the complete authenticated input chain;
- the status and the family identities.

**Idempotence.** Recomputing on an identical complete input identity with the same status is idempotent.

**Reused identities are refused.** A new decision is refused if it uses any of:

- new labels, a new seed, or a new package;
- a second candidate under an identity that is already used;
- a session or transcript already used.

**No pooling.** There is no pooling and no subset rescue. A decision covers the whole candidate and both modules.

**Dry runs.** A dry-run package may be computed, but it is stamped not production-eligible and is never registered.

**The acceptance runtime (R3-S3).** The process doing acceptance computes its runtime identity afresh. This covers the Python build, `uv.lock`, the file hashes of numpy, scipy, spaCy, thinc, the model package and the installed lexinspect distribution, and the source digest of the lexinspect it imports. That identity must equal the freeze record's. If it differs, production acceptance refuses before computing any decision, and nothing is registered. The observed identity is part of the complete input identity and of the output.

**A failed execution (R4-S1; R3 Addendum 1).** A failed, killed or aborted execution consumes its round. `register-failure` registers it as a decision with the status `procedure_failure`, which is a non-pass. It uses no labels and no acceptance arithmetic. The line binds:

- the reservation, the freeze record and the immutable start record;
- the journal, the abort record and the raw-cache inventory, where they exist;
- the hash of the private failure archive;
- a complete input identity;
- the hashed identities of the exposure inventory.

The archive receipt that the execution gate passed is re-validated against the committed objects. Registration is atomic and idempotent. No other decision for that round is ever admitted, and production acceptance of it refuses before any arithmetic.

**Write order and recovery (R5-M1).** The command appends the registry line, then writes the round-directory record, then the private `failure.json`, `registration.json` and step manifest. Rerunning the same command into the same output directory after an interruption at any of these points recovers without `--overwrite`: the existing outputs must be identical to this registration's (byte for byte for `failure.json`; the same registry line for `registration.json`), otherwise it refuses.

**A completed collection that cannot reach labels (R4 Addendum 2)** is closed the same way. This covers a shortfall, and any post-collection step before labels that cannot complete, named with `--reason`. Accepting a shortfall is forbidden: production acceptance refuses it before any arithmetic. The collection must authenticate, and its line names its collected text set. Its exposure adds the full collected text set to the three sets below. The continuation and terminal rules are those of an interrupted round. A record in the round directory (`procedure_failure.json`, hashes only) makes later rounds exclude the whole exposure rather than only the texts.

**Exposure completeness needs an authenticated endpoint (ruling after audit r7 B1).** A failed or interrupted round's exposure is complete only if an endpoint record fixes the full request history. That is either the completion record (`execution.json`) or the abort record. Its recorded journal SHA-256 and fetch log must match the journal byte for byte, and the journal must end exactly at that endpoint. The completion record hashes the journal only after every append to it has passed its durable barrier (a failed barrier aborts the collection instead). The abort record first applies the journal's file-plus-directory barrier again and hashes the journal only if that barrier succeeds; if it cannot succeed, the abort record is still written but carries no journal hash, so the exposure is not established (audit r8 M1). In every other case the exposure is incomplete, and only the terminal routes remain. This covers a hard interruption with no endpoint record; a missing, empty, shortened or hash-mismatched journal; and an unreadable start record. Recoverable identities are kept as diagnostics only. Absence of evidence never implies zero requests.

**The exposure inventory** is the union of three sets:

- every source whose request appears in the journal, whether or not the request succeeded;
- every body in the round's raw cache;
- every listing entry the seeded selection reached before the interruption, and the next one it would have requested.

The listing entries are found by re-running the selection offline through the journal. Entries skipped because they were already excluded are not exposure. If the journal fails its integrity check, the abort record cannot be read or disagrees with it, the replay diverges, or any body or request cannot be identified, the exposure is not established. The failure is still registered, with `exposure_complete: false`.

**Damaged evidence never blocks the closure (R5-S2).** Every cached response is validated against its full expected structure before identities are read from it. An unreadable, truncated or structurally unexpected response (for example a page or revision that is not an object) gives no identities from its body and a recorded problem: the exposure is not established, and the requested title known from the journal or listing is still counted. It never stops the registration. The same holds for an unreadable abort record or pool listing. Failed authentication of the freeze record, reservation, receipt or archive, or a readable start record that names another round, is different: registration refuses.

**An unreadable start record (R5 Addendum ruling 2, revised after audit r6 B1)** is registrable as `procedure_failure`, so a consumed round is never stranded. It is recorded as "unreadable", with its raw bytes hashed. The reservation, freeze record, receipt and failure archive must still authenticate; in production the receipt is made at registration for the freeze record's bound files, because the gate's receipt was inside the unreadable record. Its exposure is always incomplete: neither a missing journal nor an unchanged cache proves that no request was made, because evidence can be lost and failed or cache-read requests leave the cache unchanged. Only the terminal outcomes remain; round-2 reservation and planning refuse. Identifiers recoverable from the surviving evidence are recorded as diagnostics only. The consumed-round refusal is unchanged.

**The failure archive agrees with the round directory both ways.** Every optional execution record (journal, abort record, completion record, collection record, collected texts) is in the archive exactly when it is in the round directory, with the same bytes.

**Incomplete procedure.** In production, any missing or failed link in the package's hash chain makes the result inconclusive. This follows the protocol's "a required procedure is incomplete". The inconclusive result is registered.

### 3.5 Round 2

Round 2 requires all of the following:

- a registered round-1 decision that is not a pass;
- `--earlier` equal to that registered round 1 (texts, freeze record and seed), with the earlier collection authenticated and its exclusions derived from it;
- canonical source identities disjoint from round 1's, not merely different manifest hashes;
- a separately frozen revised candidate with a different commit, keeping the original family identities;
- a reviewed disposition for any narrowing of a family, bound into the round-2 freeze record;
- a distinct seed, excluding the development set and every earlier check text.

**After a round-1 `procedure_failure` (R4-S1).** "The registered round 1" is the failed round-1 directory. Round-2 planning checks that its start, journal and abort records are the registered ones. It reconstructs the exposure inventory again, requires it to be established and equal to the registered one, and excludes every exposed source. The round-2 decision's sources must be disjoint from that exposure. If round 1's exposure was not established, no round 2 is reserved or decided.

**A shortfall exhausts its stratum (R5-S3).** A completed collection is short only after the frozen selection has reached every entry of the short stratum that was not already excluded (each academic discipline runs to its quota or the end of its listing; each Wikipedia list is walked to its end). All of those entries are then exposed. Round 2 uses the same frozen pool snapshot, so it has no eligible unexposed source in that stratum and would be short again. A new seed, a new candidate or a source that has become available again does not restore eligibility. After a genuine shortfall, round 2 is permitted by the registry if the exposure was established, but it cannot fill the stratum: only "revert to 0.3.3" or a reviewed amendment can resolve it. An interrupted execution or an early pre-label failure is different, since most of each stratum may remain unexposed. In the archived dry-run pool snapshot, the listings after development exclusion hold 3,502 (sciences), 7,686 (social sciences), 597 (humanities), 961 (general Wikipedia) and 2,040 (Wikipedia essays) entries, against round targets of 7, 7, 6, 20 and 20. These are listing counts before licence, length, parse, redirect, duplicate, category and retrieval checks; they cannot certify future availability. They show only that a shortfall is not forced by pool size.

**The shared registry (R5-M2).** Round 2 appends to the same append-only registry, after round 1's lines. It is never reset, truncated, replaced or edited by hand.

### 3.6 After the decisions

- **After a round-1 pass,** the only further entry is the terminal outcome "ship".
- **After a round-1 `procedure_failure` whose exposure was not established,** only "revert to 0.3.3" or "amendment" remain.
- **After round 2** (decided or `procedure_failure`), or after any terminal entry, only terminal outcomes are accepted:
  - **ship:** needs the latest decision to be a pass;
  - **revert to 0.3.3:** needs a non-pass;
  - **amendment:** needs a non-pass.

## 4. Delivery (R2-B3)

**Expected sessions.** Each stage's expected sessions are rebuilt from the authenticated batch manifests and compared, id by id and byte by byte, with the delivered sessions.

- Every primary role must cover its assigned items exactly once.
- A missing expected session counts as never delivered, which is a procedure problem. A delivered session with a missing or invalid record is a non-vote.

**Uniqueness.** Session ids and transcripts are unique across the round and against earlier rounds.

**Session paths.**

- In production, session directories are created under a fresh, randomly named directory in the system temporary directory.
- No component of a session's resolved path may reveal a family, a version, a role or the round.

**Archiving before delivery.** Before each stage is delivered, its stage receipt (file hashes only) is committed and pushed. Acceptance re-validates it.
