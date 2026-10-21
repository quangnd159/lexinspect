# Study 4 Stage-1 review, round 3: dispositions

**Review:** [`r3_review.md`](r3_review.md), a verification round by GPT-6.1-Sol (reasoning high) as independent methodology reviewer, 2026-10-21, at `07d6ad0`. Verdict READY FOR STAGE-1 DEPOSIT: 0 BLOCKING, 0 SHOULD-FIX, 2 NIT. It found every round-2 finding resolved. Its own provenance controls passed, and its re-collection of the eight pilot label and retry files was byte-identical. It agreed that the two local legacy test failures are unrelated to the package.

**Dispositions written:** 2026-10-21 by the maintainer's session (Claude Code acting for the maintainer). Both nits were accepted and applied in the reviewer's exact text, in the commit that adds this file. The freeze manifest was then rebuilt and checked. Neither nit changes a scientific input, a number or a decision.

## R3-1 NIT: the snapshot described itself as the live log

**Accepted.** The two body paragraphs of `study4-access-log.stage1.md` are replaced with the reviewer's text. The snapshot now says that it is immutable, is hashed by the manifest and is never appended to. The dated empty table is kept.

## R3-2 NIT: one F1 summary dropped the retained-records qualification

**Accepted.** The "disclosure changes" bullet of `study4-pilot040/CORRECTION_F1.md` is replaced with the reviewer's text. The first-draft quotation is left as history, as the review allows.

## Also done

The prereg's Stage-1 review count now records all three rounds and links their reports and dispositions. The reviewer's deposit list (r3 report, "What should enter the Stage-1 deposit") is the specification for the deposit package.

## Addendum, 2026-10-21: the two stale local tests

The round-2 brief reported two local failures, and this review agreed they don't affect the package. They are now dealt with properly, and no file under `fixcheck/` is edited. Today's `fixcheck/` is still byte-identical to the harness bound in round 2's freeze record; only the disclosed `build.py`, `simulate_coverage.py` and `test_analyse.py` differ.

- **Why they fail.** Both assert something about the live tree that held while the fix check ran and stopped holding afterwards, by design:
  - `test_r9.py::test_g1_g4_real_round1_still_authenticates_against_this_tree` is the G1 gate for collecting round 2: round 1's bound files must equal the live tree. The preregistration was edited for Stage 1 after round 2 was registered.
  - `test_fixcheck.py::test_pinned_src_record_checks_tree_and_lock` uses the live repository as the `--pinned-src` candidate checkout. The repository now holds the v0.4.0 lock file, not dec79bc's.
- **What replaces them.** `scripts/validation/study4_precision/pilot040/test_fixcheck_history.py` checks what they protected against history:
  - round 1's bound files are byte-identical at the commit that registered round 2, and round 2's freeze record binds the same preregistration;
  - today only the preregistration differs; its first change (`5edbf61`, 2026-10-20) is after round 2's registration (2026-10-19T03:48:54Z), and no later version returns to round 1's text;
  - `pinned_src_record` gives the right answer both ways: true for a checkout holding dec79bc's lock, false for the repository's v0.4.0 lock;
  - both registered rounds ran the full pinned checkout of dec79bc in its own environment, with dec79bc's own lock file.
- **The old tests still run.** `scripts/validation/study4_precision/conftest.py` marks the two tests as strict expected failures. If either one passes, or fails with anything other than an assertion, the suite fails.
- **Two harness details found on the way,** recorded in the new test's docstring rather than corrected in the frozen files:
  - `run.py`'s docstring says `--pinned-src` was "used for the real candidate", but both registered rounds used `--pinned-checkout`;
  - in those rounds' `pinned.json`, the field `uv_lock_sha256_commit` holds the git blob id (SHA-1) of dec79bc's `uv.lock`, not a SHA-256.

  Neither affects a decision.
