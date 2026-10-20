# Study 4: the 0.4.0 common development pilot, results

**Date:** labelling on 2026-10-20 (16:44–16:57 UTC); this record was written 2026-10-21, before the 0.4.0 simulation was run.

**Design and selection:** `PLAN.md` and `selection.json`. **Launch and context evidence:** `LAUNCH.md`.

**What these numbers are.** They are fitted development calibration inputs for the simulation (protocol, "After the candidate passes", item 2). They are not unbiased evidence that 0.4.0 is better than 0.3.2. The pilot's texts are the development texts that the matcher fixes were developed on.

## Sessions

There were 10 sessions, each fresh and each in its own directory. All were delivered with exit code 0.

| Session | Role and model | Items | Time (UTC) |
|---|---|---:|---|
| primary-A-01 to A-04 | A, Claude Sonnet 5.5, effort high | 4 × 325 | 16:44–16:49 |
| primary-B-01 to B-04 | B, GPT-6.1-Sol, reasoning high | 4 × 325 | 16:44–16:49 |
| retry-A-01 | A, retry of 4 invalid records | 4 | 16:50 |
| adjudication-01 | adjudicator, DeepSeek V4.1 Flash, variant high | 84 | 16:51–16:57 |

**Screen** (`check_sessions.py`):

- The injected context had no repository, study, private-path, git-status or instruction-file marker in any session.
- No session's tool calls mentioned a path outside its own directory.
- One call was flagged as code-like, in primary-A-02. It is an Edit of its own labels file, and the match is ordinary wording in a hand-written note; role A has no command tool.

**Transcript review by the maintainer's session:**

- **A:** read the three files with Read and wrote labels with Write or Edit.
- **B:** read the files with `cat` and `sed` in chunks and wrote labels by hand, in heredoc or `apply_patch` appends of 15–50 lines.
- **Flash:** used only read, write and edit.

No session generated labels by program.

## Validation and retry

- **A:** 1,296/1,300 valid. The 4 invalid records gave the claimed category as the alternative category. They were retried once in a fresh session from the archived retry manifest; all 4 came back valid, and the files were merged with `analyse.py --merge-retry`.
- **B:** 1,300/1,300 valid, with no retry.
- **Adjudicator:** 84/84 valid, so completeness is 1.0 and no retry was needed. There were no non-votes in any role after the retry.

**Labels by role:**

| Role | C | WC | EC | NM | WL | WU | NE | U |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A (merged) | 903 | 62 | 32 | 224 | 6 | 37 | 27 | 9 |
| B | 914 | 71 | 31 | 203 | 4 | 39 | 29 | 9 |
| adjudicator (84 items) | 47 | 10 | 3 | 13 | 2 | 8 | 0 | 1 |

C = CORRECT, WC = WRONG_CATEGORY, EC = EXTERNAL_CONNECTIVE, NM = NOT_METADISCOURSE, WL / WU = WRONG_SENSE_LISTED / UNLISTED, NE = NOT_THE_EXPRESSION, U = UNSURE.

## Pilot quantities

| Quantity | Metadiscourse | PHRASE |
|---|---|---|
| Items | 1,000 | 300 |
| STRICT precision, design-weighted (N_h/r_h) | **.554** (.55375); exact 95% [.473, .634] | **.870** (.87002); exact 95% [.785, .934] |
| STRICT precision, unweighted | 693/999 = .694 | 230/300 = .767 |
| STRICT reference from A–B agreement | 945 | 288 |
| STRICT reference from the adjudicator | 54 | 12 |
| STRICT unresolved | 1 | 0 |
| Adjudicator needed for STRICT (split, or a primary UNSURE) | 55 | 12 |
| All-outcome adjudication requests | 67 | 17 |
| A–B STRICT agreement | 945/983 = .961, κ .91 | 288/300 = .960, κ .89 |
| A–B full-label agreement | .934, κ .86 | .943, κ .86 |
| Adjudicator non-votes / UNSURE | 0 / 1 | 0 / 0 |

Pooled over both modules there were 84 adjudication requests, of which the adjudicator answered 1 UNSURE.

**Unresolved mass.** One metadiscourse item (a self-mention) is unresolved. Its bounds on the weighted estimate are [.55354, .55380]. PHRASE has none.

**History.** The 0.3.2 pilot (16 Oct) is kept unchanged. It had metadiscourse at .491 weighted and .622 unweighted, with 63 adjudicated and 2 unresolved, and PHRASE at .836 weighted and .670 unweighted, with 8 adjudicated and 0 unresolved. It had 86 requests, 2 of them UNSURE. Its labels were made under the conditions described in `LAUNCH.md` F1.

## Change status and adjudicator diagnostics

**Change status.** An item is *unchanged* when a 0.3.2 development hit with the same module, text, span and claim (category or PHRASE rank) exists. 993 metadiscourse items and 298 PHRASE items are unchanged; 7 and 2 are new or changed. None of the 9 new or changed items needed adjudication.

| Module, change status | Requests | Valid | UNSURE | Adjudicator = A on STRICT | Adjudicator = B on STRICT |
|---|---:|---:|---:|---:|---:|
| metadiscourse, unchanged | 67 | 67 | 1 | 39/58 | 31/58 |
| phrase, unchanged | 17 | 17 | 0 | 15/17 | 7/17 |

On disputed PHRASE items the adjudicator sided with A far more often than with B. This is a diagnostic only. Flash stays the adjudicator: the protocol never replaces it to improve development precision, and nothing here invokes the selection amendment rules.

## Simulation recalibration

The recalibration (`simulate_coverage.py`, `PILOT` and `pilot_resolution`) uses the retained rule:

- **`p_target`** is .554 for metadiscourse and .870 for PHRASE, the design-weighted estimates rounded to three places as in the 0.3.2 code.
- **Adjudication share:** 55/1,000 and 12/300.
- **Non-resolution:**
  - for metadiscourse, the observed 1/1,000;
  - for PHRASE, whose observed value is zero, the adjudication share times the pooled adjudicator UNSURE rate, (12/300) × (1/84).

Every quantity is defined, so no amendment is needed. The maintainer parameters keep their BASE assumption labels, because the pilot has no maintainer labels.

## Hashes (private archive `lexinspect-private/study4-pilot040/`)

| File | SHA-256 |
|---|---|
| labels/A_batch.jsonl | `ac020889769028bf0760ebfe176e093985d3a0a3504ba7a6a6f126f1233db57f` |
| labels/A_retry.jsonl | `f8be163fe1f67d3dbde6b20725f4359e5e95b4859221b8e0d3e075f547682107` |
| labels/A_merged.jsonl | `43b3d1a89434ee062e1b0a35a7b8f6581d7d76e5ceed873d8d914284c499a7d1` |
| labels/B_batch.jsonl | `b8b529442a101183db3241d10a92f9e829718106af12df444f7652edf3fbdf4e` |
| labels/needs_adjudication.txt | `4e545200556de4e1e7c150feead3d7c2af759defd04a7334dea91d5f073f4d5f` |
| labels/adjudicator_adjudication.jsonl | `52bfa59fc0035678d6ef697445a2128dc67d8c8962955483e88e72c6918cf62d` |
| retry manifest (A) | `8e52821565b82fe17944fda833e9ec80fbe6dde0d8c58cc5256fe8add1f44ab6` |
| adjudication manifest | `45669e67d66e9e79e5a9fb8654673fa3cb20993bd65fbab34a6ca89e8ca4c91a` |
| analysis/pilot.json | `f3aa1dd84cff957a2272fba354e4fa055cc5ff178eb235700ff261d99b8d24b4` |
| analysis/flash_diagnostics.json | `e3d2d90dbb6673fd386b4c36a5b94a5963dbd532972e6b8e139342568a953d38` |
