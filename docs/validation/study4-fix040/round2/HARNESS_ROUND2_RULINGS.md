# Study 4 fix check, round 2: harness rulings

**Status:** DRAFT (for the maintainer's review before the round-2 freeze)

**Scope.** These rulings harden the harness for round 2. They address gaps G1 to G5, G7, G10 and G12 of the round-2 plan (`.cache/validation/study4_fix040/round2/ROUND2_PLAN.md`, section 4), as revised after the first review of the round-2 harness (`.cache/validation/sol_round2_harness_audit_r1.md`, findings 1 to 5) and the second (`.cache/validation/sol_round2_harness_audit_r2.md`, findings N1 to N3). Ruling A1 amends the frozen `accept.py` (review 2, N2). Each ruling states what the code enforces and what remains a prerequisite for the operator or for review. G6, G8, G9 and G11 are not changed: G6 and G8 are cosmetic or already enforced elsewhere, G9 is handled by the ledger convention in RUNBOOK section 9, and G11 is a disclosure, not a defect. The regression tests are in `scripts/validation/study4_precision/fixcheck/test_r9.py` and `test_r10.py`.

**Why a separate file.** Round 1's freeze record binds `docs/validation/study4-fix-protocol-clarifications.md` by SHA-256. Ruling G1 below refuses round-2 planning if that file has changed. So these rulings are not added to clarifications section 3.5; they are recorded here instead. They extend section 3.5 ("Round 2"). The maintainer reviews and adopts this file, replacing its status with `**Status:** FINAL` and recording the adoption date before the plan, and the round-2 plan binds that exact committed file with `--dispositions` (RUNBOOK section 9.3). The harness does not check this file's status: the FINAL check on `--narrowing-disposition` does not validate the status of this separate rulings file.

**Where the refusals happen.** The refusals of G1 to G5 and the narrowing-check refusals of G10 happen in round-2 planning, before the round-2 reservation is appended, and are repeated when the execution rebuilds the freeze record, unless a ruling says otherwise. The G10 conformance check itself runs in the dry run: a failing comparison or an input that does not authenticate makes the dry run exit nonzero. Production planning then refuses unless it is given that dry run's authenticated, passing result (the narrowing check). Nothing here changes the protocol, the gates, the error budget, the twelve family identities or any bound of the acceptance calculation. The one change to a frozen file is ruling A1: the acceptance status rule now makes any procedure problem inconclusive, as the clarifications already require; no calculation changes.

## Round-2 planning (`collect --round 2`)

**G1. Round 1 stays as it was frozen and receipted.** Round-2 planning first authenticates round 1 against the registry, as before. It then refuses if:

- any file bound by round 1's freeze record no longer has its recorded SHA-256, or is missing: the ledger Markdown, the ledger components, the protocol, the clarifications, and every `bound` file except the append-only registry (the preregistration, the delivery spec and every disposition and rulings file);
- round 1's `command.txt` or `manifest_plan.json` is missing or changed;
- for a production round 1, the archive receipt its execution gate checked (in `execution_start.json`) does not re-validate against the committed objects: the receipt must have held when it was made, its commit must still be on its receipt ref, the origin URL must be the receipt's, every listed file must be that commit's blob, and every listed file must still be byte-equal on disk.

Two kinds of receipted file are exempt from byte equality. The append-only registry is checked as an extension of its receipted version instead. The reviewed round-2 harness sources (`scripts/validation/study4_precision/fixcheck/*.py`) are disclosed in `round2.harness_changed_vs_round1` and bound by the round-2 freeze record. The frozen Study 4 inputs remain compared (G4 also refuses them). A dry-run round 1 has no receipt; its `manifest_plan.json` must still list `command.txt` and the freeze record with their hashes, which is a self-consistency check only. These checks apply to dry runs too. (`collect.round1_preservation_problems`, `collect.round1_bound_problems`, `collect.round1_receipted_problems`.)

The same checks run again at round-2 acceptance (`package.round2_chain_problems`, from `package.check_collect`), so a round-1 file altered after round 2's execution is still found. There, as for every other chain problem, a problem makes the package production-ineligible and is passed to the acceptance calculation as a procedure problem. The acceptance calculation (`accept.compute`, as amended by ruling A1) then makes every module and the round `inconclusive`: never `pass` and never `fail`, whatever the labels give. A breach certificate the labels give is still reported (`breach_certificates`) but is not registered as a breach.

**G1, the ledger file.** Planning refuses when `--ledger-md` resolves to round 1's ledger path. Round 2 uses its own file, `docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md`. The refusal applies to a production plan, and to a dry run whose round 1 is production-eligible, so the round-2 preflight against the real round 1 sees it. A dry run of a dry-run round 1 (tests and demonstrations) keeps the default ledger. This exception is limited to ineligible demonstrations; it gains no production eligibility and no extra round. (`collect.same_ledger_as_round1`.)

**G4. The frozen inputs equal round 1's.** Planning refuses when any non-fixcheck entry of the harness source hashes differs from round 1's recorded `sources_sha256`, including a file added or missing. Those entries are all eight frozen Study 4 inputs the harness hashes (`common.FROZEN_INPUTS`): `build.py`, `analyse.py`, `estimators.py`, `frame.py`, `batches.py`, `human_page.py`, `simulate_coverage.py` and `test_analyse.py`. All eight were already in round 1's source hashes and receipt. Comparing them enforces existing frozen provenance; it creates no statistical component and does not change alpha. The fixcheck files that differ are recorded in the freeze record as `round2.harness_changed_vs_round1`, for disclosure. (`collect.harness_vs_round1`.)

**G2, disclosure of the candidate's changes.** The freeze record holds `round2.candidate_changes_vs_round1`: round 1's and round 2's candidate commits, both `src/lexinspect` tree digests (from git objects), and the changed, added and removed files. It also records whether round 1's commit still has its registered tree digest. A new tree digest does not by itself show narrowing; G10 and the source audit address that. (`collect.candidate_changes`.)

## Round-2 production prerequisites

**G2. The narrowing disposition.** A production round-2 freeze refuses a narrowing disposition that:

- is outside the repository;
- is git-ignored (checked with `git check-ignore --no-index`, so a force-added file under `.cache/` is refused too, although Git permits force-adding it);
- has no `**Status:**` line;
- has any status other than `FINAL` (for example `DRAFT`);
- does not contain the first 12 characters of the round-2 candidate commit;
- does not contain the full SHA-256 of the narrowing check it rests on (G10).

The same tracking check applies to the ledger Markdown, the ledger components and the narrowing check: a path outside the repository, or one matched by the ignore rules, is refused, with distinct messages. The prerequisites also refuse when the candidate's changes against round 1 could not be recorded (both commits must be in the repository), or when round 1's commit no longer has its registered tree digest. A production plan reports every one of these before the reservation; a dry run lists them among its `ineligible_reasons`. (`freeze.disposition_identity`, `freeze.tracking_identity`, `freeze.tracking_problems`, `freeze.round2_problems`, called from `freeze.production_prerequisites`.)

That the disposition's content was reviewed remains a human review. Mechanically, a FINAL file naming the candidate and the narrowing check's SHA-256 is sufficient.

**G10. The narrowing check is a production prerequisite.** G10 is a development-text conformance check, not held-out validation or proof of equivalence on all possible texts. Production planning requires its authenticated result for the exact frozen candidate, round-1 comparison candidate, final ledger, harness and reviewed kept/reverted lists. The separate source audit establishes that no new rule or condition was introduced, including under an existing family identity. The six kept families are unchanged; the six specified reverted families are inactive. COMPLETE and interactions are evaluated afresh in round 2.

The round-2 plan takes `--narrowing-check docs/validation/study4-fix040/round2/NARROWING_CHECK.json`, a byte copy of the file the final fresh dry run wrote (below). The plan refuses, before the reservation, if the file is missing, outside the repository, git-ignored or not named by the disposition, or if any of the following does not hold. A bare `ok` flag is never accepted:

- the document is a `fixcheck-narrowing-check`, version 1;
- its candidate commit and tree are the plan's `--candidate-commit` and its `src/lexinspect` tree digest;
- its comparison commit and tree are round 1's registered candidate commit and tree digest;
- its kept families are exactly MD-D, MD-H, MD-I, PH-A, PH-B, PH-C, and its reverted families exactly MD-A, MD-B, MD-C, MD-E, MD-F, MD-G, in that order (`narrowing.KEPT`, `narrowing.REVERTED`, the authorized disposition);
- its ledger hash is the SHA-256 of the plan's `--ledger-md`, and its harness hash is that of the plan's harness source hashes;
- its development manifest is the canonical one;
- its nested result (`kept_family_identity`) names the same candidate commit and tree and the same comparison commit and tree as the document and the plan, and a development-round `texts.jsonl` SHA-256 equal to the one the development manifest gives (`narrowing.dev_round_texts_sha256`: each manifest row with its text's SHA-256); a missing or different nested identity is refused (round-2 harness review 2, N1);
- the dry run's own checks passed (verification, ledger, blinding, pinned baseline, determinism, and the verified ledger being the keyed one);
- every per-family and per-combination result holds:
  - BASELINE, each kept family and each of the 57 combinations of two or more kept families have equal, nonempty hashes for the two candidates and are byte-equal;
  - each reverted family has zero affected rows and equal candidate and baseline counts in both modules, equal to the rows' counts, a baseline row count equal to BASELINE's, a hit sequence identical to BASELINE's, and `zero_affected`, `counts_match_rows` and `identical_to_baseline` all `true`;
  - COMPLETE is identical to the six kept families together, with its hit count equal to the kept union's and to the six-kept combination's;
  - no recorded boolean may contradict the counts beside it (review 2, N1);
- `kept_family_identity.ok` and `ok` are both `true`.

The freeze record binds the file's identity and the validation result (`round2.narrowing_check`), with round 1's registered candidate (`round2.round1_candidate`). The file is in `freeze.receipt_paths`, so the archive receipt covers it. The execution rebuilds the record, so a changed file, ledger or harness is refused before any fetch. Round-2 acceptance re-validates it against the freeze record (`package.round2_chain_problems`); a problem is a chain problem: the result is `inconclusive`, never `pass` or `fail` (ruling A1). (`narrowing.py`; `collect.narrowing_check_identity`; `freeze.round2_problems`.)

## The registry

**G3. A revised candidate needs a revised tree.** A round-2 reservation, and a round-2 decision, are refused when the candidate's `src/lexinspect` tree digest equals round 1's registered digest, even under a new commit id. Both digests must be recorded for the comparison; older entries without a digest are not compared. Supported production collection always records both. (`registry.same_tree_as_round1`, called by `check_reservation` and `check_decision`.)

## The download cache

**G5. A production round's raw cache is private, disjoint and fresh.** Without `--dry-run`, `collect` refuses, at planning and at execution and before anything is written, a raw cache that:

- is inside the repository (including the default `<out>/raw` when `--out` is in the repository);
- after resolution is an `--earlier` round's recorded `paths.raw_cache`, lies inside it, or contains it;
- is inside that earlier round's private directory (the parent of its raw cache);
- holds a symbolic link that resolves into the earlier round's raw cache or private directory.

At production planning only, before the pool snapshot is copied in, the cache must also be fresh: it does not exist, is empty, or holds nothing but byte-equal copies of the frozen development pool listings. Any other file, such as a pre-existing response body or a copy of round 1's bodies, is refused. This is not applied at execution, where planning has legitimately copied the pool listings in and the frozen initial cache inventory is the check. Round 2 therefore needs an explicit, new `--raw-cache <R2>/raw` outside `<R1>`. (`collect.refuse_unsafe_raw_cache`, `collect.refuse_used_raw_cache`.)

## The dry run

**G7. The dry run takes the ledger.** `dryrun --ledger-md <file>` (default: the DRAFT working copy, as before) is the ledger bound by the demonstration plan and by the development round's freeze record, and checked by both `verify` calls. The ledger path and its SHA-256 are part of the dry run's resume identity. For round 2, finalize the ledger before the final fresh dry run. Any later change to candidate bytes, ledger bytes, harness bytes or comparison settings requires another fresh dry run and renewed review of its conformance evidence before planning.

**G10, the dry run that produces the narrowing check.** `dryrun --commit <CAND2> --compare-candidate <commit> --kept <F1,F2,...>` needs `--commit`, and resolves the comparison commit to its full id before the resume key. On the same 120 development texts it then runs:

- the comparison candidate's BASELINE and each kept family alone (into `compare/`);
- the new candidate's BASELINE, COMPLETE and every family alone;
- for both candidates, every combination of two or more kept families (`subsets/`, `compare/subsets/`). With BASELINE and the singletons, these are all 64 subsets of the six kept switches.

Before comparing anything, `dryrun.kept_family_identity` authenticates every input; any problem is a nonzero exit:

- both candidate snapshots have a nonempty commit and tree digest, are the requested commits, and their bytes and the commits' git objects give that digest;
- every run, every set of combinations and the diff holds each required file in its step manifest, with its hash;
- every worker imported its own snapshot and ran its configuration and family list on the one development text manifest;
- every worker's meta names its hit file's SHA-256 and the rows' actual per-module counts;
- the diff is of this run;
- the development round is the canonical development manifest.

It then compares counts and hashes only, and writes the result, with the identities the plan validates, to `NARROWING_CHECK.json`. The dry run exits nonzero unless that file's `ok` is true. `narrowing-check --dryrun-dir <D> --evidence <file>` re-checks a copy against the dry run that produced it, exit 0 only if it reproduces and is ok.

What it does not establish: every result holds for the 120 development texts only, and combinations that include a reverted family with fewer than all six kept families (or reverted families only) are not run. It is not a proof of rule identity on arbitrary texts or for every combination; the source audit and round 2 itself carry those claims.

## Tests

**G12. The public-document content check.** `test_r6.py::test_r3_s2_public_documents_carry_no_inventory_fragment` failed with `IsADirectoryError` once `round1/` existed. It now reads the regular files of `docs/validation/study4-fix040/`, the git-tracked files under its round directories (`git ls-files`) and the clarifications. It never reads the untracked private collection bodies. New public round-2 files are read once they are tracked; the mandatory whole-set and staged restricted-content scan remains necessary before that. This is no exemption for restricted material in public files.

## Amendment to the frozen acceptance calculation

**A1 (2026-10-18). Amendment to frozen `accept.py`: incomplete-procedure precedence (round-2 harness review 2, N2).** Maintainer decision of 2026-10-18 (option 1 of `.cache/validation/study4_fix040/round2/HARNESS_ROUND2_REPORT_r3.md`).

*What changed.* Only the status rule of `accept.compute` (`scripts/validation/study4_precision/fixcheck/accept.py`). Before: a module was `fail` if it had any breach certificate, otherwise `pass` if every gate passed and there was no procedure problem, otherwise `inconclusive`; the round was `fail` if any module failed, `pass` if every module passed and there was no procedure problem, otherwise `inconclusive`. After: if the procedure-problem list is nonempty, every module and the round are `inconclusive`, selected before `fail` and before `pass`. With an empty list the rule is exactly the old one. The list is the one the result reports as `procedure_problems`: in production every package chain problem (`accept.main` passes `problems = list(chk["problems"])`), the problems `acceptance_of` adds (adjudication labels missing, configurations missing), and the problems the calculation itself finds (a sample size other than min(200, N), an affected row without a labelled counterpart or same-span sibling, a baseline-success row count other than n_h). A problem found only in a later module also makes the earlier modules inconclusive. The file's SHA-256 changes from `a9284160930d843f309235d23a052966b39ea9966ad96d98c5f8a113b329d813` (round 1's freeze record, `sources_sha256["fixcheck/accept.py"]`) to `166ab3ffc88603b5f8a3c719e7b0dc5caff85cb7e3ea670df3e688129f3d6c19`.

*What did not change.* Certificate detection and every bound (removal bounds, U_loss, L_success, the cumulative fraction), the tolerances .15 and .05, J = 68, alpha = .05/68, the component identities and their values, the error allocation, sampling, blinding, the `decision_wording` texts and the registry entry format. `breach_certificates` and each gate's `breach_certificate` flag are still computed and reported, so `acceptance.json` still shows what the labels said. Under an incomplete procedure such a certificate is not an established breach, which is what the `inconclusive` wording ("no breach established") states.

*Why.* Clarifications section 3.4, already bound by round 1's freeze record, says: "**Incomplete procedure.** In production, any missing or failed link in the package's hash chain makes the result inconclusive. This follows the protocol's "a required procedure is incomplete". The inconclusive result is registered." Review 2 (N2) reproduced the frozen code registering `fail` for a detected chain problem together with breach labels. The amendment brings the code into line with that bound rule; it adds no rule. It applies the same precedence to the calculation's own procedure problems, which were already reported as `procedure_problems` and already blocked a pass; they are incomplete procedure in the protocol's sense too.

*Round 1.* The old precedence existed from round 1's freeze. It did not affect round 1: round 1's registered decision (`round1/accept/acceptance.json`) has `procedure_problems: []`, for which the old and new rules coincide. Recomputing round 1's acceptance read-only from its private package with the amended code gives the registered result (`fail`; metadiscourse `fail` with certificates removal MD-B, MD-C, MD-E, MD-F; phrase `pass`), with equal components, modules and wording. Nothing under `round1/` or in `round_registry.jsonl` changes, and round 1's authentication and preservation checks still report no problem.

*Disclosure.* `accept.py` is a top-level `fixcheck/*.py` harness source. G4 (`collect.harness_vs_round1`) refuses only a changed frozen Study 4 input (a non-fixcheck entry), and lists changed fixcheck entries; `fixcheck/accept.py` is therefore listed in the round-2 freeze record's `round2.harness_changed_vs_round1`, and its new hash is bound by that record's `sources_sha256`. G1 exempts the same files from byte equality with round 1's receipt. The change is disclosed, not refused.

*Effect on dry runs and power.* `accept --dry-run` still computes `mathematical_status` with the package's chain problems not applied (`procedure_problems_not_applied`); the calculation's own problems apply, now with the amended precedence. `power.py` calls the same calculation; its replicates have no procedure problems when every affected row has its labelled link, which holds for the round-2 rehearsal structure (checked: no such row), so its operating characteristics are unchanged there.

*Tests.* `test_r10.py`: `test_n2_chain_problem_with_breach_labels_is_inconclusive` (no longer expected to fail), `test_n2_inconclusive_still_reports_the_breach_certificates`, `test_n2_problem_found_in_a_later_module_makes_every_module_inconclusive`. No existing test expected `fail` together with a procedure problem.

This amendment needs the same review and FINAL adoption as the rest of this file.

## What stays procedure

- The kept and reverted family lists are the maintainer's decision. The harness holds the authorized lists (`narrowing.KEPT`, `narrowing.REVERTED`) and the round-2 plan requires the narrowing check to carry exactly those lists. It does not parse the disposition's prose; the disposition must state the lists and name the check's SHA-256, and its review is human.
- That no new rule or condition was introduced, including under an existing family identity, is established by the separate source audit, not by the harness.
- The ledger table convention (RUNBOOK section 9) is unchanged: `verify` still checks round 1's rule lists as the family identities (G9).
- Round 1's private bodies under `round1/collect/` and `<R1>/raw` stay in place, untracked, until the round-2 decision.
