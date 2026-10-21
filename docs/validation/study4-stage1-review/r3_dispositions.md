# Study 4 Stage-1 review, round 3: dispositions

**Review:** [`r3_review.md`](r3_review.md), a verification round by GPT-6.1-Sol (reasoning high) as independent methodology reviewer, 2026-10-21, at `07d6ad0`. Verdict READY FOR STAGE-1 DEPOSIT: 0 BLOCKING, 0 SHOULD-FIX, 2 NIT. It found every round-2 finding resolved. Its own provenance controls passed, and its re-collection of the eight pilot label and retry files was byte-identical. It agreed that the two local legacy test failures are unrelated to the package.

**Dispositions written:** 2026-10-21 by the maintainer's session (Claude Code acting for the maintainer). Both nits were accepted and applied in the reviewer's exact text, in the commit that adds this file. The freeze manifest was then rebuilt and checked. Neither nit changes a scientific input, a number or a decision.

## R3-1 NIT: the snapshot described itself as the live log

**Accepted.** The two body paragraphs of `study4-access-log.stage1.md` are replaced with the reviewer's text. The snapshot now says that it is immutable, is hashed by the manifest and is never appended to. The dated empty table is kept.

## R3-2 NIT: one F1 summary dropped the retained-records qualification

**Accepted.** The "disclosure changes" bullet of `study4-pilot040/CORRECTION_F1.md` is replaced with the reviewer's text. The first-draft quotation is left as history, as the review allows.

## Also done

The prereg's Stage-1 review count now records all three rounds and links their reports and dispositions. The reviewer's deposit list (r3 report, "What should enter the Stage-1 deposit") is the specification for the deposit package.
