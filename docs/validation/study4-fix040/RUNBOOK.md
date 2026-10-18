# Study 4 fix check (lexinspect 0.4.0): production runbook

**Scope.** This runbook covers the steps from the candidate commit to `collect --execute`, then labels, acceptance and the terminal outcome. It covers round 1. Round 2 is in section 9.

**Governing documents.** This runbook follows:

- `docs/validation/study4-fix-protocol.md`;
- `docs/validation/study4-fix-protocol-clarifications.md`;
- the harness dispositions and rulings bound in step 3.3.

These Addendum rulings are applied (`HARNESS_AUDIT_R1_DISPOSITIONS.md`, Addendum; the guidelines ruling is `HARNESS_AUDIT_R2_DISPOSITIONS.md`, Addendum 4):

1. The maintainer finalises the ledger at the freeze.
2. The freeze files live in this directory. Nothing under `.cache/` is force-added. Every file is checked for PHRASE List text before commit.
3. The delivery routes are the registered ones.
4. The span-change rule is the strict reading.
5. The power model is accepted, with the module-calibrated scenarios reported for information.
6. The candidate is committed, then dry-run in a fresh directory.
7. The guidelines are not committed in the fix-check freeze. They are bound by SHA-256 (the pilot-frozen hash) and kept in the private archive, like the sense inventory (section 0.4).
8. The collection is executed once (`HARNESS_AUDIT_R3_DISPOSITIONS.md`, R3-B1). There is no resume, retry or overwrite (section 5).
9. A failed, killed or aborted execution consumes the round. It is registered as `procedure_failure`, a non-pass (`HARNESS_AUDIT_R3_DISPOSITIONS.md`, Addendum 1; `HARNESS_AUDIT_R4_DISPOSITIONS.md`, R4-S1). A completed collection that cannot reach labels (a shortfall, or any pre-label step that cannot complete) is closed the same way; a shortfall is never accepted (`HARNESS_AUDIT_R4_DISPOSITIONS.md`, Addendum 2). After round 1, a fresh disjoint round 2 may follow; after round 2, only a terminal outcome (section 5, "Failure").

**Placeholders.** The only placeholders are the following. Replace each one everywhere before running anything.

| Placeholder | Meaning |
|---|---|
| `<CAND>` | the full 40-character candidate commit id |
| `<SEED>` | the round-1 seed, a decimal integer. It must not be the development seed, and the maintainer chooses it at freeze. |
| `<REPO>` | absolute path of this repository's checkout |
| `<R1>` | absolute path of the private round-1 package directory. It must be outside `<REPO>`, on storage that is never published. |
| `<PINNED>` | absolute path, outside `<REPO>`, for the pinned 0.3.3 checkout |
| `<ARCHIVE>` | absolute path of the private archive (restricted materials) |

The plan writes `command.txt` itself, with every placeholder resolved. Step 5 runs that file and nothing else.

**How to run commands.**

- Every command runs from `<REPO>`.
- Every harness command below is written out in full. To shorten typing, you may define this shell function once per shell; it works in zsh, bash and sh:

      fix() { uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py "$@"; }

  Then `fix collect …` is the same as the full `uv run … cli.py collect …`. Do not store the command in a variable: zsh does not split it into words (R4-M1).
- The registered receipt ref is `refs/remotes/origin/study4-fix040-candidate`. Every push in this runbook is `git push origin study4-fix040-candidate`.
- A receipt is checked with local git only. A successful push updates the remote-tracking ref that the receipt reads.

## 0. Public allowlist and private archive

**Public (committed and pushed).** Only these files are committed. Each one is checked before commit (section 0.3).

1. **Harness code.**
   - `scripts/validation/study4_precision/`: the five frozen inputs, `build.py`, `analyse.py`, `estimators.py`, `frame.py` and `batches.py`, whose SHA-256 values must be unchanged;
   - the other study scripts and tests;
   - `fixcheck/*.py`.
2. **The candidate.** `src/lexinspect/**` at `<CAND>`, and its tests under `tests/`.
3. **Protocol documents.**
   - `docs/validation/study4-fix-protocol.md`
   - `docs/validation/study4-fix-protocol-clarifications.md`
   - `docs/validation/study4-preregistration.md`

   The guidelines, `docs/validation/study4-guidelines.md`, are not on this list. They stay private (section 0.4).
4. **This directory, `docs/validation/study4-fix040/`.**
   - `RUNBOOK.md`
   - `CANDIDATE_LEDGER.md`
   - `ledger_components.json` and `manifest_ledger.json`
   - `delivery_spec.json`
   - `round_registry.jsonl`
   - `HARNESS_AUDIT_R1_DISPOSITIONS.md`, `HARNESS_AUDIT_R2_DISPOSITIONS.md`, `HARNESS_AUDIT_R3_DISPOSITIONS.md`, `HARNESS_AUDIT_R4_DISPOSITIONS.md`, `HARNESS_AUDIT_R5_DISPOSITIONS.md` and `HARNESS_RULINGS.md`
5. **Round-1 freeze and execution records,** in `docs/validation/study4-fix040/round1/collect/`:
   - `freeze_record.json`
   - `command.txt`
   - `manifest_plan.json`
   - `execution_start.json` (the single-execution claim: hashes, argv, round, seed, times)
   - `procedure_failure.json`, only if the round was closed by `register-failure` (hashes only)
   - `execution.json`
   - `manifest_collect.json`
6. **Round-1 receipts,** in `docs/validation/study4-fix040/round1/receipts/`:
   - `primary.json`, `retry.json` and `flash.json` (stage receipts: SHA-256 values only);
   - `private_archive.sha256`.
7. **Round-1 decision,** in `docs/validation/study4-fix040/round1/accept/`:
   - `acceptance.json`
   - `acceptance.md`
   - `ledger_components_result.json`
   - `registration.json`
   - `manifest_accept.json`

Round 2 adds its own files under `docs/validation/study4-fix040/round2/` (section 9).

**Private (never committed).** These are kept in `<R1>` and archived to `<ARCHIVE>`. Their SHA-256 values are public through the stage receipts and `private_archive.sha256`.

- **The collection bodies:**
  - `docs/validation/study4-fix040/round1/collect/collection.json`;
  - `texts.jsonl` and `texts/`;
  - `fetch_journal.jsonl` and, if the execution aborted, `execution_abort.json` (both hold the request log);
  - the raw download cache at `<R1>/raw`;
  - after a failed execution, `<R1>/failure` (`failure.json` names every exposed source).
- **The lock file** `docs/validation/study4-fix040/round1/collect/execution.lock` is never committed and never deleted.
- **The frozen labelling materials:** the guidelines (`docs/validation/study4-guidelines.md`) and the sense inventory (`.cache/validation/study4/phrase_sense_inventory.md`). Their byte copies go into `<R1>/materials` and the private archive (section 0.4). Only their SHA-256 values are public, in `delivery_spec.json` and `private_archive.sha256`.
- **The packaged candidate and its outputs:** `<R1>/candidate`, `<R1>/run`, `<R1>/diff`, `<R1>/sample`. These hold hit payloads, frames and selections.
- **The labelling material:** `<R1>/assign` (units, items, key, batches, retry and Flash), `<R1>/sessions`, `<R1>/labels`, `<R1>/transcripts`, `<R1>/verify`.
- **Anything containing PHRASE List glosses, examples or sense-inventory text,** including every session directory. Session directories are created under the system temporary directory and archived into `<R1>/sessions/<stage>/delivered/` by `gather-labels`.

### 0.1 The package map

The collect part must sit inside the repository, because its freeze record is receipted. Every other part is private. Write `<R1>/package.json` once, before step 6:

```json
{
  "collect": "<REPO>/docs/validation/study4-fix040/round1/collect",
  "replay": "replay",
  "candidate": "candidate",
  "run": "run",
  "diff": "diff",
  "sample": "sample",
  "assign": "assign",
  "retry": "assign/retry",
  "flash": "assign/flash",
  "sessions": "sessions",
  "labels": "labels",
  "verify": "verify"
}
```

### 0.2 Staging rule

- Stage files by explicit path only. Never use `git add -A`, `git add .` or `git add -f`.
- Before every commit in this runbook, compare the staged list with the paths the step names. The output must be empty:

      git diff --cached --name-only | LC_ALL=C sort > "<R1>/staged.txt"
      LC_ALL=C sort "<R1>/allowed.txt" | diff - "<R1>/staged.txt"

  Here `<R1>/allowed.txt` holds exactly the paths named in that step, one per line.

### 0.3 Restricted-content check

The check is a small Python byte scanner (`scan-restricted`; `HARNESS_AUDIT_R5_DISPOSITIONS.md`, R5-M3). It prints paths and counts only, never a matched fragment.

**Fragments.** Write the private fragment file once, into `<R1>`:

    mkdir -p <R1>
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py scan-restricted fragments --inventory .cache/validation/study4/phrase_sense_inventory.md --out "<R1>/inventory_fragments.txt"

**Staged check.** Run this before every commit:

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py scan-restricted staged --fragments "<R1>/inventory_fragments.txt"

It prints `ok: <path>` for each staged file, then a count line, then `scan finished: clean`, and exits with status 0. Anything else stops the runbook:

- **status 1:** a `RESTRICTED (staged blob)` or `RESTRICTED (working tree)` line names a file that holds a fragment;
- **status 2:** `NOT COMPLETED`. The check could not finish. Causes: the fragment file is missing, unreadable or empty; a line in it is shorter than 20 characters; or a git command, a listing or a read failed. The completion marker is printed only after every input has been read.

**What is scanned.** The check reads the staged blob of each staged file (what the commit will contain) and also its working-tree file. A staged version can differ from its working-tree file, so both are read. Matching is on bytes, so binary files are covered.

**What the check matches.** It matches every fragment of 20 characters or more of the private inventory. A fragment is a piece of a line between table bars, semicolons, quotation marks or asterisks. The fragment file is written into `<R1>`, which is private.

**The check is a floor.** Every staged file is also read before commit.

**Whole publication set (R4-S3).** The staged check sees one commit at a time. Before the candidate commit (step 1.1) and again before the freeze commit (step 3.5), scan every file the allowlist will ever publish, as it is in the working tree:

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py scan-restricted whole-set --fragments "<R1>/inventory_fragments.txt"

The set is fixed in the scanner: every file under `scripts/validation/study4_precision`, `src/lexinspect`, `tests` and `docs/validation/study4-fix040` (not `__pycache__`, `.pytest_cache` or `.pyc`); the protocol, the clarifications and the preregistration; and, from `.cache/validation/study4_fix040/`, the files that step 3 copies: `CANDIDATE_LEDGER.md`, `HARNESS_AUDIT_R1_DISPOSITIONS.md`, `HARNESS_AUDIT_R2_DISPOSITIONS.md`, `HARNESS_AUDIT_R3_DISPOSITIONS.md`, `HARNESS_AUDIT_R4_DISPOSITIONS.md`, `HARNESS_AUDIT_R5_DISPOSITIONS.md` and `HARNESS_RULINGS.md`. A missing or unreadable file is status 2, not a pass. The output must end with `scan finished: clean` and the status must be 0. Any `RESTRICTED` line stops the runbook. There is no exemption: rephrase or remove the matching text (without changing behaviour) and scan again. The harness tests `test_r4_s3_whole_publication_set_has_no_inventory_fragment` and `test_r5_m3_*` run the same check over the same set.

**The guidelines (settled).** `docs/validation/study4-guidelines.md` matches one short inventory fragment. Under the maintainer's ruling (`HARNESS_AUDIT_R2_DISPOSITIONS.md`, Addendum 4) the guidelines are not committed in the fix-check freeze. They are bound by SHA-256 `276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e` (the pilot-frozen hash, recorded in `delivery_spec.json`) and kept in the private archive, like the sense inventory, until the PHRASE List author's permission question is settled. Their publication is a Stage-1 preregistration matter, not a fix-check prerequisite. The guidelines are never staged; if this check reports them, unstage them.

### 0.4 Private copies of the frozen labelling materials

Before step 4, copy both frozen materials into private storage and check their hashes against the bound ones:

    mkdir -p <R1>/materials
    cp docs/validation/study4-guidelines.md <R1>/materials/guidelines.md
    cp .cache/validation/study4/phrase_sense_inventory.md <R1>/materials/phrase_sense_inventory.md
    (cd <R1>/materials && shasum -a 256 guidelines.md phrase_sense_inventory.md > SHA256SUMS)
    cat <R1>/materials/SHA256SUMS

The two lines must be exactly:

    276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e  guidelines.md
    a761f159541023fd51f5ca45e1fc44432b572ab22ffcad74f414b1e35a776a5d  phrase_sense_inventory.md

These are the `materials` hashes in `delivery_spec.json`. Any other value stops the runbook. `<R1>/materials` goes into both private archives (sections 7.1 and 8). Only the hashes are public.

## 1. The candidate commit

1. **Commit the candidate.** First run the whole-set scan of section 0.3 (first write `<R1>/inventory_fragments.txt` with its `fragments` command). The candidate agent then commits the candidate source (`src/lexinspect/**` and its tests) on a branch `study4-fix040-candidate` created from `main`. The resulting commit is `<CAND>`.
2. **Final dry run in a fresh directory** (Addendum 6; the S2 resume identity refuses a reused directory):

       uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py dryrun --commit <CAND> --out-root <REPO>/.cache/validation/study4_fix040/harness_dryrun/final --require-fresh --jobs 8 --plan-reps 200 --power-reps 200

3. **Read the summary.** In `dryrun_summary.json`, the following must hold:
   - `verify_baseline.identical` is `true`;
   - every value in `determinism` is `true`;
   - `verify_ok`, `ledger_ok` and `blinding_ok` are `true`.

   Then read `operational_power_headline`: this gives the power under the declared and module-calibrated scenarios. It is informational, and there is no gate on it.

   In round 2 the dry run also takes `--ledger-md` and the kept-family identity check (section 9.1).

## 2. Pinned baseline

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py prepare-pinned --dest <PINNED>

This uses the registered pinned commit, `dec79bc`, which is the default.

## 3. Freeze files (maintainer)

1. **Ledger.** (Round 1 only. In round 2, skip this step: section 9.3.)
   - Copy `.cache/validation/study4_fix040/CANDIDATE_LEDGER.md` to `docs/validation/study4-fix040/CANDIDATE_LEDGER.md`.
   - Set its status line to `**Status:** FINAL`. Only the maintainer does this.
   - Then write the components:

         uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py ledger --out <REPO>/docs/validation/study4-fix040

2. **Delivery spec.**
   - `docs/validation/study4-fix040/delivery_spec.json` is already generated. It holds the registered prompt (extracted verbatim from the preregistration), material hashes and routes; it contains no material text.
   - Confirm the three routes against Addendum 3:
     - A: `claude-sonnet-5-5`, effort high;
     - B: `gpt-6.1-sol`, reasoningEffort high;
     - adjudicator: `opencode/deepseek-v4.1-flash-free`, reasoning high.
   - If any route string must change, regenerate the spec:

         uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py delivery-spec --out <REPO>/docs/validation/study4-fix040/delivery_spec.json --overwrite

3. **Dispositions and rulings.**
   - Copy these six files into `docs/validation/study4-fix040/`, unchanged:
     - `.cache/validation/study4_fix040/HARNESS_AUDIT_R1_DISPOSITIONS.md`
     - `.cache/validation/study4_fix040/HARNESS_AUDIT_R2_DISPOSITIONS.md`
     - `.cache/validation/study4_fix040/HARNESS_AUDIT_R3_DISPOSITIONS.md`
     - `.cache/validation/study4_fix040/HARNESS_AUDIT_R4_DISPOSITIONS.md`
     - `.cache/validation/study4_fix040/HARNESS_AUDIT_R5_DISPOSITIONS.md`
     - `.cache/validation/study4_fix040/HARNESS_RULINGS.md`
   - Ruling A2 in `HARNESS_RULINGS.md` is superseded by R2-B4.
4. **Registry.** `docs/validation/study4-fix040/round_registry.jsonl` exists and is empty (0 bytes). Do not edit it by hand, ever.
5. **Check, commit and push.**
   - Run the whole-set scan of section 0.3 again. Then run the checks in sections 0.2 and 0.3 on exactly these paths:
     - the harness paths of allowlist item 1;
     - the three documents of item 3 (never the guidelines);
     - the files of item 4.
   - Then:

         git commit -m "Study 4 fix check: freeze files for round 1"
         git push origin study4-fix040-candidate

   - After the push:
     - `git status --porcelain --untracked-files=no` must print nothing;
     - `git rev-parse refs/remotes/origin/study4-fix040-candidate` must equal `git rev-parse HEAD`;
     - `git merge-base --is-ancestor <CAND> HEAD` must succeed.

## 4. Plan: reserve the round and write the freeze record

    mkdir -p <R1>
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py collect --round 1 --seed <SEED> --out <REPO>/docs/validation/study4-fix040/round1/collect --raw-cache <R1>/raw --candidate-commit <CAND> --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R1_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R2_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R3_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R4_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R5_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_RULINGS.md --plan-only

**What the defaults bind.** The plan takes these from its defaults:

- the ledger, `docs/validation/study4-fix040/CANDIDATE_LEDGER.md`;
- the components, `ledger_components.json`;
- the delivery spec, `delivery_spec.json`;
- the registry, `round_registry.jsonl`;
- the preregistration;
- the receipt ref, `refs/remotes/origin/study4-fix040-candidate`.

**What the plan does.**

- It reserves the round in the canonical registry, atomically.
- It writes `freeze_record.json`, `command.txt` and `manifest_plan.json`.
- It refuses unless the record is production-eligible.

**Commit and push the plan.**

- Check (sections 0.2 and 0.3) exactly these paths:
  - `docs/validation/study4-fix040/round_registry.jsonl` (now one reservation line);
  - `docs/validation/study4-fix040/round1/collect/freeze_record.json`;
  - `docs/validation/study4-fix040/round1/collect/command.txt`;
  - `docs/validation/study4-fix040/round1/collect/manifest_plan.json`.
- Then:

      git commit -m "Study 4 fix check: round 1 reservation and freeze record"
      git push origin study4-fix040-candidate

## 5. Execute the collection (once)

**One shot.** The collection is executed exactly once per reservation. There is no resume, retry, overwrite or second execution, by the harness or by hand. Before running anything, check that no execution evidence exists:

    ls <REPO>/docs/validation/study4-fix040/round1/collect/

If `execution_start.json`, `execution.json`, `execution_abort.json`, `fetch_journal.jsonl` or `collection.json` is present, the round has already been executed. Stop; do not run `command.txt`.

**Run `command.txt` exactly, once:**

    sh <REPO>/docs/validation/study4-fix040/round1/collect/command.txt

Its form is:

    cd <REPO> && uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py collect … --execute --freeze-record <REPO>/docs/validation/study4-fix040/round1/collect/freeze_record.json

**Checks before any fetch.** The execution first takes an exclusive lock on `execution.lock` in the round directory and holds it until it finishes; a second invocation while it runs is refused. Under the lock it refuses if any execution evidence exists, and then unless all of the following hold:

- the argv, the working directory and every bound input equal the freeze record;
- the tracked tree is clean;
- `src/lexinspect` equals `<CAND>`'s;
- the reservation is in the registry;
- every bound file is committed and byte-equal on `refs/remotes/origin/study4-fix040-candidate`.

**The claim, before the first fetch.** It then creates `execution_start.json` with exclusive creation, bound to the reservation, the freeze record, the argv and the gate it passed (with the archive receipt). It creates `fetch_journal.jsonl`, which records every request before it is made and its outcome after. Only then does it fetch.

**Durability (R4-B1).** Each of these writes (the start record, the journal's creation, and every journal line before its request) passes a full durable-write barrier before the harness goes on:

- **macOS:** `fcntl(F_FULLFSYNC)` on the file, then on its directory, with the file still open. Plain `fsync` on macOS can leave writes in the drive's cache, in any order, after a power loss; `F_FULLFSYNC` also asks the drive to flush that cache.
- **Linux:** `fsync` on the file, then on its directory.
- **Any other platform:** the execution refuses before the claim.

**Registry appends** (reservation, decision, failure, terminal) pass the same barrier on `round_registry.jsonl` and its directory (`HARNESS_AUDIT_R4_DISPOSITIONS.md`, Addendum 1). On a platform without a barrier the append is refused before anything is written. If the barrier fails after the line was written, the command stops. Do not continue: run the same command again. The rerun finds the line and never appends it twice: a reservation is `present`, a decision or failure is `idempotent`, and the identical terminal outcome (same `--outcome` and `--basis`) is `present`. Each of these is acknowledged only after the same file-plus-directory barrier has passed again on the registry as it is now (`HARNESS_AUDIT_R5_DISPOSITIONS.md`, R5-S1). If the barrier still fails, the rerun is refused too; do not continue until a rerun succeeds. A different terminal outcome after a registered one is refused ("already registered").

If a barrier fails, nothing is downgraded: the execution stops before the next request. If that happens during the claim, no request has been made, but the start record may exist, so the round is consumed (register it as a failure, below). **Residual dependence:** the guarantee holds only if the storage device honours a full flush. Run the execution on the machine's internal disk, not on a network share, a virtual disk or an external drive whose cache may ignore flushes.

**After the claim, the round is consumed.** This holds whatever happens next: completion, a shortfall, a fetch failure, any other error, Ctrl-C, a kill, a crash or a power loss (backed by the barrier above). Every later invocation refuses. Never delete, move or edit `execution_start.json`, `fetch_journal.jsonl`, `execution_abort.json` or `execution.lock`. Never re-run `command.txt`.

**Completion.** A completed execution writes `execution.json` (completion) and `manifest_collect.json`, without touching the start record. If the command exits with status 2 and reports `SHORTFALL`, the collection cannot be accepted: go to **Failure** below (a shortfall). Otherwise commit and push the execution record:

- Check (sections 0.2 and 0.3) exactly:
  - `docs/validation/study4-fix040/round1/collect/execution_start.json`;
  - `docs/validation/study4-fix040/round1/collect/execution.json`;
  - `docs/validation/study4-fix040/round1/collect/manifest_collect.json`.
- Then:

      git commit -m "Study 4 fix check: round 1 execution record"
      git push origin study4-fix040-candidate

**Failure.** The same route closes three cases, each as `procedure_failure`:

- **an interrupted execution** (failure, abort, kill, crash or power loss);
- **a shortfall:** the collection completed with status `shortfall`, which is never accepted;
- **a pre-label step that cannot complete:** after a complete collection, any step of sections 6 and 7 before labels exist (replay, candidate, run, diff, sample, assign, a stage receipt or the session export) fails and cannot be completed under the frozen procedure. Once any label exists, the round is decided by `accept` instead.

If the execution fails, the harness writes `execution_abort.json` when it can. It holds the error, the request log and the journal's SHA-256. After a hard exit or a power loss there is no abort record, but the start record and the journal remain; the round can then only be closed with a terminal outcome (below). In every failure case the round is consumed and is registered as `procedure_failure` (Addendum 1 of `HARNESS_AUDIT_R3_DISPOSITIONS.md`; R4-S1). Never re-run `command.txt`, and never delete, edit or move `fetch_journal.jsonl`, `execution_abort.json` or `<R1>/raw`: round 2 is derived from them.

1. Archive the round directory and its cache privately, and record the archive's hash:

       mkdir -p <ARCHIVE> <REPO>/docs/validation/study4-fix040/round1/receipts
       tar -cf <ARCHIVE>/round1-aborted.tar -C <REPO>/docs/validation/study4-fix040/round1 collect -C <R1> raw materials
       shasum -a 256 <ARCHIVE>/round1-aborted.tar | sed 's#  .*/#  #' >> <REPO>/docs/validation/study4-fix040/round1/receipts/private_archive.sha256

2. Register the failure (no labels, no acceptance arithmetic):

       uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py register-failure --round-dir <REPO>/docs/validation/study4-fix040/round1/collect --archive <ARCHIVE>/round1-aborted.tar --out <R1>/failure

   The same command closes an interrupted execution and a shortfall. For a pre-label step that cannot complete, add `--reason "<the step and why it cannot complete>"`. Without it, a complete collection is refused.

   **A shortfall exhausts its stratum (R5-S3).** Read this before choosing a route after a shortfall. A completed collection is short only after the frozen selection has reached every entry of the short stratum that was not already excluded: each academic discipline runs until its quota or the end of its listing, and each Wikipedia list is walked to its end. Under the exposure rule, every one of those entries is now exposed, whether its request failed, its text was rejected or it was collected. Round 2 uses the same frozen pool snapshot, so it has **no** eligible unexposed source left in that stratum and would be short again. A new seed, a new candidate, or a source that has since become available again does not restore eligibility. After a genuine shortfall, only `revert_0.3.3` or a reviewed amendment can resolve the exhausted stratum. This differs from an interrupted execution or a pre-label failure that stopped early, where the unexposed remainder of each stratum may still be large.

   Listing headroom in the archived dry-run pool snapshot (`sol_harness_audit_r5.md`, section 6):

   | Stratum | Listed | After development exclusion | Round target |
   |---|---:|---:|---:|
   | Sciences (4 journals) | 3,516 | 3,502 | 7 |
   | Social sciences (8 journals) | 7,699 | 7,686 | 7 |
   | Humanities (8 journals) | 610 | 597 | 6 |
   | General Wikipedia | 1,001 | 961 | 20 |
   | Wikipedia essays | 2,080 (after the slash-title filter) | 2,040 | 20 |

   These are listing counts, not counts of retrievable eligible texts. They come before licence, length, parse, redirect, duplicate, category and retrieval checks, and they cannot certify future availability. They show only that a shortfall is not forced by pool size: it would need severe attrition or a systematic source or service failure.

   Under the round's execution lock, it checks:
   - the freeze record, the start record (bound to that freeze record, its reservation and the recorded argv) and any abort record;
   - the archive receipt that the execution gate passed, re-validated against the committed objects;
   - the reservation in the registry;
   - that the archive holds the round's freeze, start, journal and abort records byte for byte (for a completed collection also `execution.json`, `collection.json` and `texts.jsonl`), and that its `raw/` is exactly `<R1>/raw` as it is now;
   - for a completed collection, that it authenticates (texts, manifest, start record, journal).

   **The exposure inventory.** It then reconstructs what the execution exposed:
   - every source whose request is in the journal, whether or not the request succeeded;
   - every body in `<R1>/raw`;
   - every listing entry the seeded selection reached before the interruption, and the one it would have requested next. These are found by re-running the selection offline through the journal;
   - for a completed collection, the full collected text set.

   **Registration.** It appends one `procedure_failure` line to `round_registry.jsonl`, atomically, with the durable barrier. It then writes `procedure_failure.json` into the round directory (hashes only; later rounds exclude the round's whole exposure because of it). Only then does it write the private outputs in `<R1>/failure/`: `failure.json` (it names the exposed sources), `registration.json` and `manifest_register_failure.json`, in that order. If it is interrupted at any point, run exactly the same command again, with the same `--out` and without `--overwrite` (R5-M1). The registry line is acknowledged as `idempotent`, the round-directory record is kept if identical, an existing `failure.json` must be byte for byte this registration's, and an existing `registration.json` must record this registry line; the missing outputs are then written. Anything else is refused. A second registration with other evidence is refused.

   **An unreadable start record (R5 Addendum ruling 2, revised after audit r6 B1).** If the claim's own write was cut short (power loss or a crash while `execution_start.json` was written), the start record cannot be read. The round is still consumed, and the same command registers it, so the round is never stranded. The start record is recorded as `unreadable`, with the SHA-256 of its raw bytes. The reservation, the freeze record, the receipt and the archive must still authenticate. In production the receipt is made at registration for the freeze record's bound files and re-validated, because the gate's receipt was inside the unreadable record. **The exposure is never established**, whatever else survives: a missing journal or an unchanged `<R1>/raw` does not prove that no request was made. Only `revert_0.3.3` or `amendment` remain; round 2 is refused. Identifiers recovered from the surviving evidence (journal, abort record, cache, collected texts) are recorded in `failure.json` for diagnosis only.

   **The archive must match the round directory both ways.** Each of `fetch_journal.jsonl`, `execution_abort.json`, `execution.json`, `collection.json` and `texts.jsonl` must be in the archive exactly when it is in the round directory, with the same bytes. An archive made before a file was lost or changed is refused: archive the evidence as it is now.

   **Established only with an authenticated endpoint (audit r7 B1).** The exposure is established only if an endpoint record fixes the full request history: `execution.json` for a completed collection, or `execution_abort.json` for a failed one. Its recorded journal SHA-256 and fetch log must match `fetch_journal.jsonl` byte for byte, and the journal must end exactly there. The completion record hashes the journal only after every append to it has passed its durable barrier (a failed barrier aborts the collection instead). The abort record first applies the journal's file-plus-directory barrier again and hashes the journal only if that barrier succeeds; if it cannot succeed, the abort record is still written but carries no journal hash, so the exposure is not established (audit r8 M1). A hard exit, a kill or a power loss leaves no endpoint record. So does a journal that is missing, empty, shortened or changed in any byte. In each of these cases the exposure is not established, and only `revert_0.3.3` or `amendment` remain. Absence of evidence never counts as zero requests. Round 2 after a round-1 failure is therefore possible only when the harness itself recorded the stop (an abort record) or completed the collection.

   **Exposure not established.** If the journal fails its integrity check, an abort record cannot be read, a cached response cannot be read or does not have the expected structure (for example a truncated body, or a page or revision that is not an object), or the exposure cannot otherwise be reconstructed, the failure is still registered, with `exposure_complete: false`, and the command says so (R5-S2). Never repair, replace or delete a damaged cached response or record to change this. Round 2 is then impossible. A failed authentication (freeze record, a readable start record that names another round, reservation, receipt or archive) is different: the command refuses and registers nothing.
3. Commit and push. Check (sections 0.2 and 0.3) exactly:
   - `docs/validation/study4-fix040/round1/collect/execution_start.json`;
   - `docs/validation/study4-fix040/round1/collect/procedure_failure.json`;
   - for a completed collection also `execution.json` and `manifest_collect.json` in that directory, if not yet committed;
   - `docs/validation/study4-fix040/round_registry.jsonl`;
   - `docs/validation/study4-fix040/round1/receipts/private_archive.sha256`.

   Then:

       git commit -m "Study 4 fix check: round 1 procedure failure"
       git push origin study4-fix040-candidate

4. Continue only by one of these routes. `accept` for this round refuses permanently.
   - **Round 1, exposure established:** either round 2 (section 9), or a terminal outcome. After a genuine shortfall, round 2 cannot fill the exhausted stratum (see above), so choose a terminal outcome or a reviewed amendment:

         uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py register-terminal --outcome revert_0.3.3 --basis "round 1 procedure_failure"

     (or `--outcome amendment`), checked, committed and pushed as in section 8, step 5.
   - **Round 1, exposure not established:** only `revert_0.3.3` or `amendment`, with the command above.
   - **Round 2:** the same four steps with `round2` and `<R2>` in place of `round1` and `<R1>`. A failed round 2 is terminal: only `revert_0.3.3` or `amendment`.

## 6. Replay and the pre-label package

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py collect --replay-round <REPO>/docs/validation/study4-fix040/round1/collect --out <R1>/replay

**The replay must pass.** `replay.json` must report every one of these true:

- `identical`;
- `logs_identical`;
- `text_reproducible`;
- `archived_dates_consistent`;
- `cache_files_unchanged`;
- `raw_responses_authenticated`.

**Build the pre-label package:**

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py prepare-candidate --commit <CAND> --dest <R1>/candidate
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py run --round-dir <REPO>/docs/validation/study4-fix040/round1/collect --out <R1>/run --candidate-src <R1>/candidate --pinned-checkout <PINNED> --jobs 8
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py diff --run-dir <R1>/run --out <R1>/diff
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py sample --run-dir <R1>/run --diff-dir <R1>/diff --out <R1>/sample --plan-reps 200 --power-reps 200 --jobs 8
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py assign --sample-dir <R1>/sample --out <R1>/assign

**What `run` must report:** `verify-baseline: identical=True`, and the run must be production-eligible.

**What `sample` writes, before any label:**

- the selection;
- the label units;
- the decision plan;
- `operational_power.json`, with the grid and module-calibrated scenarios and the feasible attainable values.

## 7. Labelling

**Session rules:**

- One fresh session per batch.
- Each session reads only the files in its directory, as the delivery spec's prompt says.
- Each session's transcript is kept at `<R1>/transcripts/<stage>/<token>.txt`.

### 7.1 Primary pass

**1. Private archive and stage receipt** (the pre-label package; before delivery):

    mkdir -p <ARCHIVE> <REPO>/docs/validation/study4-fix040/round1/receipts
    tar -cf <ARCHIVE>/round1-prelabel.tar -C <R1> package.json materials raw replay candidate run diff sample assign -C <REPO>/docs/validation/study4-fix040/round1 collect
    shasum -a 256 <ARCHIVE>/round1-prelabel.tar | sed 's#  .*/#  #' >> <REPO>/docs/validation/study4-fix040/round1/receipts/private_archive.sha256
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py stage-receipt --package <R1>/package.json --stage primary --out <REPO>/docs/validation/study4-fix040/round1/receipts/primary.json

The archive holds the byte copies of the frozen guidelines and sense inventory, with `materials/SHA256SUMS` (section 0.4).

**2. Commit and push the receipts.**

- Check (sections 0.2 and 0.3) exactly:
  - `docs/validation/study4-fix040/round1/receipts/primary.json`;
  - `docs/validation/study4-fix040/round1/receipts/private_archive.sha256`.
- Then:

      git commit -m "Study 4 fix check: round 1 primary stage receipt"
      git push origin study4-fix040-candidate

**3. Export the sessions.** Each session gets a fresh random directory under the system temporary directory:

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py export-sessions --spec <REPO>/docs/validation/study4-fix040/delivery_spec.json --stage primary --stage-dir <R1>/assign --fresh-session-root --package <R1>/package.json --receipt <REPO>/docs/validation/study4-fix040/round1/receipts/primary.json --out <R1>/sessions/primary

**4. Deliver.**

- For each line of `<R1>/sessions/primary/deliveries.template.jsonl`, open a fresh session on that line's route.
- Give it `<R1>/sessions/primary/prompts/<token>.txt` verbatim.
- Save the transcript to `<R1>/transcripts/primary/<token>.txt`.

**5. Write `<R1>/sessions/primary/deliveries.jsonl`.** It has one line per delivered session, completing the template's fields:

- `delivered`: true;
- `session_id`: the provider's id;
- `transcript`: the absolute path;
- `transcript_sha256`;
- `labels_sha256`: of the session's `labels.jsonl`;
- `delivered_at`;
- `access_review`: a non-empty note that the transcript was read and only the listed files were used.

A session that was never run is left out. It then counts as never delivered, which is a procedure problem; it is not a non-vote.

**6. Gather the labels:**

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py gather-labels --stage-out <R1>/sessions/primary --role A --out <R1>/labels/A.pass1.jsonl
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py gather-labels --stage-out <R1>/sessions/primary --role B --out <R1>/labels/B.pass1.jsonl

### 7.2 The single registered retry

**1. Write the retry manifests:**

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py retry --assign-dir <R1>/assign --labels A=<R1>/labels/A.pass1.jsonl B=<R1>/labels/B.pass1.jsonl

**2. If either `<R1>/assign/retry/retry_A.jsonl` or `retry_B.jsonl` is non-empty:**

- Write the stage receipt:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py stage-receipt --package <R1>/package.json --stage retry --out <REPO>/docs/validation/study4-fix040/round1/receipts/retry.json

- Check (sections 0.2 and 0.3) exactly `docs/validation/study4-fix040/round1/receipts/retry.json`, then:

      git commit -m "Study 4 fix check: round 1 retry stage receipt"
      git push origin study4-fix040-candidate

- Export the retry sessions:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py export-sessions --spec <REPO>/docs/validation/study4-fix040/delivery_spec.json --stage retry --stage-dir <R1>/assign/retry --fresh-session-root --package <R1>/package.json --receipt <REPO>/docs/validation/study4-fix040/round1/receipts/retry.json --out <R1>/sessions/retry

- Deliver as in 7.1 steps 4 and 5, with transcripts under `<R1>/transcripts/retry/`.
- Gather each role whose manifest is non-empty:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py gather-labels --stage-out <R1>/sessions/retry --role A --out <R1>/labels/A.retry.jsonl
      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py gather-labels --stage-out <R1>/sessions/retry --role B --out <R1>/labels/B.retry.jsonl

**3. Merge with the frozen code, for each role.** If the role has a retry file:

    uv run --offline --frozen python -I scripts/validation/study4_precision/analyse.py --merge-retry <R1>/labels/A.pass1.jsonl <R1>/labels/A.retry.jsonl --manifest <R1>/assign/retry/retry_A.jsonl --merged-out <R1>/labels/A.jsonl

If its manifest is empty, use no retry file:

    uv run --offline --frozen python -I scripts/validation/study4_precision/analyse.py --merge-retry <R1>/labels/A.pass1.jsonl /dev/null --manifest <R1>/assign/retry/retry_A.jsonl --merged-out <R1>/labels/A.jsonl

Do the same for B, with `B` in place of `A`.

### 7.3 Flash adjudication

**1. Write the Flash set:**

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py flash --assign-dir <R1>/assign --labels A=<R1>/labels/A.jsonl B=<R1>/labels/B.jsonl

**2. If `<R1>/assign/flash/flash_ids.txt` is non-empty:**

- Write the stage receipt:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py stage-receipt --package <R1>/package.json --stage flash --out <REPO>/docs/validation/study4-fix040/round1/receipts/flash.json

- Check (sections 0.2 and 0.3) exactly `docs/validation/study4-fix040/round1/receipts/flash.json`, then:

      git commit -m "Study 4 fix check: round 1 Flash stage receipt"
      git push origin study4-fix040-candidate

- Export the adjudicator sessions:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py export-sessions --spec <REPO>/docs/validation/study4-fix040/delivery_spec.json --stage flash --stage-dir <R1>/assign/flash --fresh-session-root --package <R1>/package.json --receipt <REPO>/docs/validation/study4-fix040/round1/receipts/flash.json --out <R1>/sessions/flash

- Deliver as in 7.1 steps 4 and 5, with transcripts under `<R1>/transcripts/flash/`.
- Gather the adjudicator's labels:

      uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py gather-labels --stage-out <R1>/sessions/flash --role adjudicator --out <R1>/labels/adjudicator.jsonl

## 8. Verification, acceptance and the terminal outcome

**1. Verify** (round 2 adds `--ledger-md`, section 9.8):

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py verify --out <R1>/verify --assign-dir <R1>/assign --sample-dir <R1>/sample --run-dir <R1>/run --flash-dir <R1>/assign/flash --retry-dir <R1>/assign/retry

**2. Optional preview of the chain.** This checks the hash chain only. It reveals no gate arithmetic and makes no decision:

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py accept --package <R1>/package.json --check-only --out <R1>/accept_check

**3. The decision.** It is always registered:

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py accept --package <R1>/package.json --out <REPO>/docs/validation/study4-fix040/round1/accept

- **Registry checks first.** The registry's integrity is checked first, and a damaged registry refuses before any step.
- **The frozen runtime.** Acceptance runs in the frozen runtime: the same checkout state (`src/lexinspect` equal to `<CAND>`'s, the same `uv.lock`), the same virtual environment and Python build, and the same installed numpy, scipy, spaCy, thinc, model and lexinspect files. The check computes this identity afresh. If it differs from the freeze record's `environment`, acceptance refuses before any decision and registers nothing (R3-S3).
- **Receipts and the registry.** The execution receipt covers the registry as it was at the freeze. Later reservation, decision and terminal lines extend it and remain valid. A rewritten, truncated or reordered registry is refused (R3-S1).
- **Chain problems.** Any problem in the chain makes the package production-ineligible and is passed to the acceptance calculation as a procedure problem. Any procedure problem (a chain problem, or one the calculation finds itself) makes every module and the result `inconclusive`: never a pass and never a `fail`, even if the labels give a breach certificate, which is still reported in `breach_certificates` (clarifications section 3.4, "Incomplete procedure"). Before 2026-10-18 `accept.compute` selected `fail` for a breach certificate before considering procedure problems; round-2 harness ruling A1 (`round2/HARNESS_ROUND2_RULINGS.md`, after review 2, N2) amended the frozen `accept.py` to the clarifications' rule. Round 1 was decided with no procedure problems, so the change does not affect it.
- **Registration.** The decision is checked and appended to `round_registry.jsonl` atomically. A refused registration writes nothing.

**4. Archive and publish.**

- Archive the labelled package privately and record its hash:

      tar -cf <ARCHIVE>/round1-labelled.tar -C <R1> package.json materials raw replay candidate run diff sample assign sessions labels transcripts verify -C <REPO>/docs/validation/study4-fix040/round1 collect
      shasum -a 256 <ARCHIVE>/round1-labelled.tar | sed 's#  .*/#  #' >> <REPO>/docs/validation/study4-fix040/round1/receipts/private_archive.sha256

- Check (sections 0.2 and 0.3) exactly these paths:
  - `docs/validation/study4-fix040/round_registry.jsonl`;
  - `docs/validation/study4-fix040/round1/receipts/private_archive.sha256`;
  - in `docs/validation/study4-fix040/round1/accept/`: `acceptance.json`, `acceptance.md`, `ledger_components_result.json`, `registration.json` and `manifest_accept.json`.
- Then:

      git commit -m "Study 4 fix check: round 1 decision"
      git push origin study4-fix040-candidate

**5. Terminal outcome** (after a round-1 pass, or when not going to round 2):

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py register-terminal --outcome ship --basis <REPO>/docs/validation/study4-fix040/round1/accept/acceptance.json

- `ship` needs a pass.
- `revert_0.3.3` and `amendment` need a non-pass.
- Check (sections 0.2 and 0.3) exactly `docs/validation/study4-fix040/round_registry.jsonl`, then commit with `git commit -m "Study 4 fix check: terminal outcome"` and push with `git push origin study4-fix040-candidate`.

## 9. Round 2 (only after a registered round-1 non-pass)

Round 2 repeats sections 1 to 8 with the changes in this section. The harness rulings for round 2 (gaps G1 to G5, G7, G10 and G12, as revised after the round-2 harness review) are in `docs/validation/study4-fix040/round2/HARNESS_ROUND2_RULINGS.md`.

**Never overwrite round 1's files.** Round 1 must stay re-checkable. These files stay byte-equal, and are never edited, regenerated, recopied or deleted:

- everything under `docs/validation/study4-fix040/round1/`, including the untracked private bodies in `round1/collect/` (`collection.json`, `texts.jsonl`, `texts/`, `fetch_journal.jsonl`, `execution.lock`), until the round-2 decision is registered;
- `docs/validation/study4-fix040/CANDIDATE_LEDGER.md` (round 1's ledger), `ledger_components.json`, `manifest_ledger.json` and `delivery_spec.json`;
- the five `HARNESS_AUDIT_R*_DISPOSITIONS.md` files and `HARNESS_RULINGS.md`;
- the protocol, the clarifications and the preregistration;
- `<R1>/raw` and `<R1>` as a whole.

Never run `git clean`. The repository stays at the same absolute path, because the bound paths are absolute. Round-2 planning refuses if any file bound by round 1's freeze record has changed, if round 1's `command.txt` or `manifest_plan.json` is missing or changed, or if round 1's execution receipt no longer re-validates against the committed objects (G1). Only the append-only registry and the reviewed round-2 harness sources (`fixcheck/*.py`) are exempt from byte equality. Round-2 acceptance repeats these checks; a problem there is a chain problem: the result is `inconclusive`, never a pass or a `fail` (section 8, step 3, "Chain problems").

**Substitutions.**

- the revised candidate is a new commit, `<CAND2>`, written in place of `<CAND>`. Its `src/lexinspect` must differ from round 1's: the registry refuses a new commit with round 1's tree digest (G3);
- the seed is a new one, `<SEED2>`, written in place of `<SEED>`. It must differ from round 1's seed (2026101801) and from the development seed;
- `<R2>` replaces `<R1>`. It is a new private directory outside `<REPO>`, next to `<R1>`;
- `round2` replaces `round1` in every repository path and archive name (`round2/collect`, `round2/receipts`, `round2/accept`, `<ARCHIVE>/round2-prelabel.tar`, and so on);
- **the registry is kept (R5-M2).** `docs/validation/study4-fix040/round_registry.jsonl` is shared by both rounds. It is append-only and already holds round 1's reservation and decision (and nothing else). Skip the empty-registry requirement of step 3.4: never reset, truncate, replace or hand-edit the registry, and never copy an empty one over it. The round-2 plan appends its reservation after round 1's lines, and every check requires that history.

**Public files of round 2.** The section 0 allowlist extends to these files, all under `docs/validation/study4-fix040/round2/`:

- `CANDIDATE_LEDGER.md`, `NARROWING_CHECK.json`, `NARROWING_DISPOSITION.md` and `HARNESS_ROUND2_RULINGS.md`;
- `collect/freeze_record.json`, `collect/command.txt` and `collect/manifest_plan.json`, then `collect/execution_start.json`, `collect/execution.json` and `collect/manifest_collect.json` (and `collect/procedure_failure.json` only after a failure);
- `receipts/primary.json`, `receipts/retry.json`, `receipts/flash.json` and `receipts/private_archive.sha256`;
- `accept/acceptance.json`, `accept/acceptance.md`, `accept/ledger_components_result.json`, `accept/registration.json` and `accept/manifest_accept.json`.

The private files of section 0 are private in round 2 too, under `round2/collect/` and `<R2>`.

### 9.1 The candidate and the round-2 dry run (section 1)

1. **Fragments and scan.** Write `<R2>/inventory_fragments.txt` with the `scan-restricted fragments` command of section 0.3 (with `<R2>` for `<R1>`), then run the whole-set scan.
2. **Commit the candidate** on `study4-fix040-candidate` and push. The commit is `<CAND2>`.
3. **The round-2 ledger first, final.** Write the round-2 ledger as in 9.3 step 1, at `docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md`, and finalize it (`**Status:** FINAL`) now. The harness changes are in place and committed. Finalize the ledger before the final fresh dry run. Any later change to candidate bytes, ledger bytes, harness bytes or comparison settings requires another fresh dry run and renewed review of its conformance evidence before planning.
4. **Final dry run in a fresh directory,** with the round-2 ledger and the narrowing check (G10):

       uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py dryrun --commit <CAND2> --out-root <REPO>/.cache/validation/study4_fix040/round2/harness_dryrun --require-fresh --jobs 8 --plan-reps 200 --power-reps 200 --ledger-md <REPO>/docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md --compare-candidate 3d4df7012656defd5a44571410af00896f634a2d --kept MD-D,MD-H,MD-I,PH-A,PH-B,PH-C

   `--compare-candidate` is round 1's candidate commit; the dry run resolves it to the full commit id. `--commit` is required with it. `--kept` lists the families the narrowing disposition keeps; every other family must change nothing. Besides BASELINE and each family alone, both candidates run every combination of two or more kept families (all 64 subsets of the six kept switches, the empty one being BASELINE). That adds 57 worker runs per candidate.
5. **Read the summary and the narrowing check.** In `dryrun_summary.json`, the following must hold:
   - `verify_baseline.identical` is `true`;
   - every value in `determinism` is `true`;
   - `verify_ok`, `ledger_ok` and `blinding_ok` are `true`, and `ledger_md` is the round-2 ledger;
   - `kept_family_identity.ok` is `true`.

   The dry run writes the same result, with the identities it rests on, to `NARROWING_CHECK.json` in its directory. This file holds counts and hashes only. Its `ok` is `true` only if every input authenticated and:
   - the BASELINE frame, each kept family's frame and each of the 57 kept combinations are byte-equal to round 1's candidate's on the same texts;
   - every other family has zero affected rows, candidate and baseline counts equal to its rows' counts, and a hit sequence identical to BASELINE's;
   - the new candidate's COMPLETE is identical to the six kept families together;
   - the dry run's own checks above passed.

   Production planning and round-2 acceptance validate the published file itself, not only its `ok`: its nested result must name the same candidate and comparison commits and trees as the document and the plan, and the development round the canonical development manifest gives; no recorded boolean may contradict the counts beside it (`narrowing.problems`; round-2 harness review 2, N1).

   An input that does not authenticate stops the dry run with a nonzero exit. Then read `operational_power_headline` (informational, no gate). If any of these fails, stop: the candidate does not match the narrowing disposition.

   G10 is a development-text conformance check, not held-out validation or proof of equivalence on all possible texts. Production planning requires its authenticated result for the exact frozen candidate, round-1 comparison candidate, final ledger, harness and reviewed kept/reverted lists. The separate source audit establishes that no new rule or condition was introduced, including under an existing family identity. The six kept families are unchanged; the six specified reverted families are inactive. COMPLETE and interactions are evaluated afresh in round 2.

   What the check does not cover: other combinations that include a reverted family (with fewer than all six kept families, or reverted families only) are not run, and every result holds for the 120 development texts only.
6. **Publish the narrowing check.** Copy it byte for byte, then re-check the copy against the dry run (it must exit 0):

       cp <REPO>/.cache/validation/study4_fix040/round2/harness_dryrun/<KEY>/NARROWING_CHECK.json <REPO>/docs/validation/study4-fix040/round2/NARROWING_CHECK.json
       uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py narrowing-check --dryrun-dir <REPO>/.cache/validation/study4_fix040/round2/harness_dryrun/<KEY> --evidence <REPO>/docs/validation/study4-fix040/round2/NARROWING_CHECK.json

   `<KEY>` is the dry run's directory name, the first 16 hex of the candidate digest. Record the copy's SHA-256 (`shasum -a 256`) for the narrowing disposition (9.3 step 2).

### 9.2 Pinned baseline (section 2)

Reuse `<PINNED>`. Do not run `prepare-pinned` again: it refuses a non-empty destination. `run --pinned-checkout <PINNED>` re-verifies it against `dec79bc`.

### 9.3 Freeze files (section 3)

1. **Ledger.** Do not do section 3, step 1. Do not copy anything over `docs/validation/study4-fix040/CANDIDATE_LEDGER.md`, and do not run the `ledger` command.
   - The round-2 ledger is a new file, `docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md`. It names `<CAND2>`. The maintainer sets its status line to `**Status:** FINAL`.
   - Its family table keeps four cells and the original rule identities. A reverted family's rules cell keeps its rule list and marks the reversion in parentheses (for example `MD-01, … (reverted to 0.3.3 in round 2: no rule active)`). Writing `none` or adding a fifth column fails `verify`.
   - Reuse `docs/validation/study4-fix040/ledger_components.json` unchanged. It enumerates the identities of both rounds. The plan's default `--ledger-components` names it.
   - Preflight (writes only under `<R2>`); it must exit 0 with `ledger.ok` true:

         uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py verify --out <R2>/preflight/verify_ledger --ledger-md <REPO>/docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md

2. **Narrowing disposition.** The reviewed disposition is `docs/validation/study4-fix040/round2/NARROWING_DISPOSITION.md`, written after the final dry run. Its status line is `**Status:** FINAL`. It names `<CAND2>` (at least its first 12 characters) and the full SHA-256 of `round2/NARROWING_CHECK.json`. It states the kept families (MD-D, MD-H, MD-I, PH-A, PH-B, PH-C) and the reverted families (MD-A, MD-B, MD-C, MD-E, MD-F, MD-G). The plan refuses a disposition that is outside the repository, git-ignored, without a status line, not FINAL, or that does not name `<CAND2>` or the narrowing check's SHA-256 (G2, G10). The same tracking check applies to the ledger, its components and the narrowing check. The harness checks the family lists in the narrowing check against the authorized lists; it does not parse them from the disposition.
3. **Round-2 harness rulings.** The maintainer reviews and adopts `round2/HARNESS_ROUND2_RULINGS.md`, replacing its status with `**Status:** FINAL` and recording the adoption date before the plan. Bind that exact committed file with `--dispositions`. The FINAL check on `--narrowing-disposition` does not validate the status of this separate rulings file.
4. **Delivery spec, dispositions and rulings:** unchanged, already in place.
5. **Registry:** kept (above).
6. **Check, commit and push.** Run the whole-set scan again. Then run the checks of sections 0.2 and 0.3 on exactly the round-2 ledger, the narrowing disposition, the round-2 rulings and any harness change. Then:

       git commit -m "Study 4 fix check: freeze files for round 2"
       git push origin study4-fix040-candidate

   Include `round2/NARROWING_CHECK.json` in these checks and in the commit. After the push, check as in section 3, step 5, with `<CAND2>`.
7. **Private copies of the materials** (section 0.4) into `<R2>/materials`, with the same two hashes.
8. **Optional preflight of the plan** (no network, no draw, a scratch registry). Copy the registry to `<R2>/preflight/registry.jsonl`, then run the 9.4 command with `--out <R2>/preflight/collect --raw-cache <R2>/preflight/raw --registry <R2>/preflight/registry.jsonl --offline --dry-run` in place of the corresponding arguments. The only acceptable `ineligible_reasons` are the dry run itself and the scratch registry's.

### 9.4 Plan (section 4)

Every path is absolute, because the argv is frozen verbatim:

    mkdir -p <R2>
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py collect --round 2 --seed <SEED2> --out <REPO>/docs/validation/study4-fix040/round2/collect --raw-cache <R2>/raw --candidate-commit <CAND2> --ledger-md <REPO>/docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md --earlier <REPO>/docs/validation/study4-fix040/round1/collect --narrowing-disposition <REPO>/docs/validation/study4-fix040/round2/NARROWING_DISPOSITION.md --narrowing-check <REPO>/docs/validation/study4-fix040/round2/NARROWING_CHECK.json --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R1_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R2_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R3_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R4_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_AUDIT_R5_DISPOSITIONS.md --dispositions <REPO>/docs/validation/study4-fix040/HARNESS_RULINGS.md --dispositions <REPO>/docs/validation/study4-fix040/round2/HARNESS_ROUND2_RULINGS.md --plan-only

**The flags round 2 adds.**

- `--round 2`;
- `--earlier <REPO>/docs/validation/study4-fix040/round1/collect`, which must be the registered round 1;
- `--narrowing-disposition`, the reviewed disposition of 9.3 step 2;
- `--narrowing-check <REPO>/docs/validation/study4-fix040/round2/NARROWING_CHECK.json`, the published narrowing check of 9.1 step 6 (G10). The plan validates it before the reservation, the execution validates it again, the freeze record and its receipt bind it, and acceptance checks it again;
- `--ledger-md`, the round-2 ledger. Without it the plan would bind round 1's ledger, and the plan refuses that (G1);
- `--raw-cache <R2>/raw`, a new, empty private cache. The plan refuses a cache inside the repository (the default `<out>/raw` is), round 1's cache or any directory inside or containing it, a directory inside round 1's private directory `<R1>`, a cache holding a symbolic link into `<R1>/raw` or `<R1>`, and a cache holding anything other than byte-equal copies of the frozen pool listings (G5);
- the round-2 rulings as a seventh `--dispositions`.

The other defaults stay: `--ledger-components`, `--delivery-spec`, `--preregistration`, `--registry` (the canonical one) and `--remote-ref`.

**Raw cache.** Keep round 1's raw cache, `<R1>/raw`, in place. The plan authenticates the earlier collection and derives the exclusions from it. `<R2>` must not be inside `<R1>`: the plan treats the parent of round 1's raw cache as round 1's private directory.

**After a round-1 `procedure_failure`.** `--earlier` is the failed round-1 directory, `<REPO>/docs/validation/study4-fix040/round1/collect`, with its private journal, any abort record or collected texts, its `procedure_failure.json`, and `<R1>/raw` still in place. The plan:

- checks that the start, journal and abort records (and the collected texts, for a shortfall or a pre-label failure) are the registered ones;
- reconstructs the exposure inventory again, and requires it to be established and equal to the registered one;
- excludes every exposed source.

**After a round-1 shortfall.** The plan admits round 2 if the exposure was established, but every short stratum is exhausted for the frozen pool snapshot (section 5, "A shortfall exhausts its stratum"). Round 2 would have no eligible source in it and would be short again. Use a terminal outcome or a reviewed amendment instead.

**What the plan refuses.** It refuses if any of the following holds:

- round 1 is not registered or is a pass;
- `--earlier` is not round 1;
- round 1 is a `procedure_failure` whose exposure was not established, or whose evidence or exposure differs from the registered one;
- a file bound by round 1's freeze record has changed, round 1's `command.txt` or `manifest_plan.json` is missing or changed, round 1's execution receipt does not re-validate, or `--ledger-md` is round 1's ledger (G1);
- a frozen Study 4 input differs from round 1's (G4);
- the narrowing disposition, the ledger or its components fail the checks of 9.3 (G2);
- `<CAND2>` has round 1's commit id or round 1's `src/lexinspect` tree (G3);
- the narrowing check is missing, outside the repository or git-ignored, is not named by the disposition, or does not validate: its candidate commit and tree, round 1's candidate commit and tree, the ledger's SHA-256, the harness, the development manifest, the kept and reverted lists, every per-family and per-combination result and `ok` (G10);
- the raw cache is inside the repository, overlaps round 1's cache, is inside round 1's private directory, links into either, or is not fresh (G5).

Planning authenticates round 1 and freezes its canonical-source exclusion set. Collection skips excluded sources, and acceptance checks disjointness of the actual collected source identities.

The freeze record also discloses `round2.candidate_changes_vs_round1` (the changed, added and removed files under `src/lexinspect`, with both tree digests) and `round2.harness_changed_vs_round1`.

**Same receipt ref.** The receipt ref is the same: `refs/remotes/origin/study4-fix040-candidate`.

**Commit and push the plan.** Check (sections 0.2 and 0.3) exactly `docs/validation/study4-fix040/round_registry.jsonl` (now three lines) and the three plan files in `docs/validation/study4-fix040/round2/collect/`. Then:

    git commit -m "Study 4 fix check: round 2 reservation and freeze record"
    git push origin study4-fix040-candidate

No harness change is possible from here to the round-2 decision: the freeze record binds the harness hashes.

### 9.5 to 9.7 Execute, the pre-label package and labelling (sections 5 to 7)

As in sections 5 to 7, with `round2` and `<R2>`:

- run `sh <REPO>/docs/validation/study4-fix040/round2/collect/command.txt` once;
- `<R2>/package.json` is the section 0.1 map with `collect` = `<REPO>/docs/validation/study4-fix040/round2/collect`;
- `prepare-candidate --commit <CAND2> --dest <R2>/candidate`, then `run --pinned-checkout <PINNED>`, `diff`, `sample` and `assign`, all under `<R2>`;
- every labelling session is fresh: the registry refuses a round-1 session id or transcript.

A failed round 2 is terminal (section 5, "Failure"): only `revert_0.3.3` or `amendment`.

### 9.8 Verification, acceptance and the terminal outcome (section 8)

`verify` needs the round-2 ledger. Without `--ledger-md`, it checks round 1's ledger and acceptance reports a chain problem ("verify.json checked another ledger than the freeze record's"): never a pass (see the chain-problem note at the end of this section):

    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py verify --out <R2>/verify --ledger-md <REPO>/docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md --assign-dir <R2>/assign --sample-dir <R2>/sample --run-dir <R2>/run --flash-dir <R2>/assign/flash --retry-dir <R2>/assign/retry
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py accept --package <R2>/package.json --check-only --out <R2>/accept_check
    uv run --offline --frozen python -I scripts/validation/study4_precision/fixcheck/cli.py accept --package <R2>/package.json --out <REPO>/docs/validation/study4-fix040/round2/accept

Archive to `<ARCHIVE>/round2-labelled.tar`, then commit the registry, `round2/receipts/private_archive.sha256` and the five `round2/accept/` files, and push. Register the terminal outcome with `--basis <REPO>/docs/validation/study4-fix040/round2/accept/acceptance.json`: `ship` after a round-2 pass, otherwise `revert_0.3.3` or `amendment`. There is no round 3.

A reverted family's removal frames are empty in round 2 (`N = 0`, `not_applicable`). That is no opportunity for removal, not evidence about the family.

Round-2 acceptance also rechecks round 1's preservation (its bound files, `command.txt`, `manifest_plan.json` and its execution receipt) and the bound narrowing check. A problem there is a chain problem: the acceptance calculation makes every module and the result `inconclusive`, never a pass or a `fail`, whatever the labels give; a breach certificate the labels give is still reported, not registered as a breach (clarifications section 3.4; harness ruling A1). The registered status is that inconclusive.
