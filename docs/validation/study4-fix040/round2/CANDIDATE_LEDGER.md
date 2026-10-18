# Study 4 fix work: candidate ledger, round 2 (lexinspect 0.4.0 narrowed candidate)

**Status:** FINAL (set by the maintainer on 2026-10-19). Frozen with the round-2 candidate commit `16aa95ef10e0ec5fc8df9113e794c85d13c8aafc` (branch `study4-fix040-candidate`), the reviewed round-2 harness changes disclosed in `round2.harness_changed_vs_round1`, the acceptance calculation with its bounds and gates unchanged apart from the procedure-precedence amendment to `fixcheck/accept.py` (round-2 rulings, A1), and the reviewed narrowing disposition, before any fix-check round-2 text is collected (FIX_PROTOCOL v3, committed as `docs/validation/study4-fix-protocol.md` at 646f7ca; clarifications in `docs/validation/study4-fix-protocol-clarifications.md`, §3.5 "Round 2"). Only the maintainer sets FINAL. The frozen copy lives at `docs/validation/study4-fix040/round2/CANDIDATE_LEDGER.md`, and the plan binds it with `--ledger-md`. The round-1 ledger at `docs/validation/study4-fix040/CANDIDATE_LEDGER.md` stays byte-equal (ROUND2_PLAN.md §1.2).

**Sources:**
- the round-1 ledger: `docs/validation/study4-fix040/CANDIDATE_LEDGER.md`, FINAL 2026-10-17, candidate `3d4df7012656defd5a44571410af00896f634a2d`;
- the registered round-1 decision: `docs/validation/study4-fix040/round1/accept/acceptance.md`, status **fail** (metadiscourse fail, PHRASE pass);
- the narrowing disposition: `docs/validation/study4-fix040/round2/NARROWING_DISPOSITION.md`, reviewed and bound into the round-2 freeze record (its draft is `.cache/validation/study4_fix040/round2/NARROWING_DISPOSITION.md`).

**Known when this was written:**
- the round-1 outcome, its per-family removal frames, bounds and certificates, and the cumulative-loss results;
- every round-1 check text and label, which are now development-exposed (protocol, "Decision and re-check").

The round-2 candidate was chosen after seeing them; that is what round 2 is for. Round 2 is decided only on its own new texts. Those are disjoint from the development set and from round 1's sources, with a new seed, under the unchanged gates and error budget. No round-1 label, count or bound enters the round-2 decision.

## Decisions

- **Narrowing, not new behaviour.** The round-2 candidate keeps six families exactly as in the round-1 candidate and reverts six completely to 0.3.3 (protocol, "Error budget": a round-2 candidate "may narrow or revert the original families but may not introduce new ones"). No rule is added, changed or narrowed inside a kept family.
  - **Kept, unchanged:** MD-D, MD-H, MD-I, PH-A, PH-B, PH-C.
  - **Reverted to 0.3.3:** MD-A, MD-B, MD-C, MD-E, MD-F, MD-G. Their rules are removed from `src/lexinspect`.
- **Identities.** All twelve family identities are kept. `_fix_families.FAMILIES` is unchanged and `enabled()`/`only()` accept all twelve names. A reverted family's switch is a valid name that gates nothing, so `only([F])` for a reverted F equals `only([])` equals 0.3.3. Its round-2 removal frames are therefore empty and its removal components not applicable: no opportunity for removal, and no evidence about the family.
- **Reasons.** These are in the narrowing disposition: breach certificates for MD-B, MD-C, MD-E and MD-F; a removal bound above .15 for MD-A; and a pre-emptive reversion of MD-G, which passed at .148, disclosed as prudential.
- **Unchanged from round 1:**
  - the parser (`en_core_web_sm` 3.8.0);
  - the exclusions (SX-02, SX-05, the *as far as* construct change, any trained model);
  - PH-03, PH-07, PH-08, removed after audit r1. SX-03, also removed after audit r1, belonged to MD-F and stays removed.
- **Documentation-only changes, no behaviour:**
  - the `metadiscourse.py` docstring describes only the 0.3.3 checks plus the kept families;
  - `_fix_families.py` marks the six reverted switches;
  - `data/SOURCES.md` drops the paragraph on the present-text recogniser, which only reverted families used, and keeps the self-mention adaptation note (0.3.3 data, unchanged);
  - a `_context.py` comment no longer refers to MD-09.

## Families (F = 12, all module-specific)

The rule lists are the original identities, as in `fixcheck/ledger.py` `FAMILY_RULES`. The round-2 state is in parentheses.

| Family | Module | Rules | Prerequisites |
|---|---|---|---|
| MD-A clause linking and transitions | metadiscourse | MD-01, MD-02, MD-03, MD-05, MD-06, MD-25 (all reverted to 0.3.3 in round 2: no rule active) | none |
| MD-B word-internal hyphens and brackets | metadiscourse | MD-04 (reverted to 0.3.3 in round 2: no rule active) | none |
| MD-C frame and endophoric markers | metadiscourse | MD-07, MD-08, MD-09, MD-10, MD-11, MD-12, MD-30 (all reverted to 0.3.3 in round 2: no rule active) | none |
| MD-D code glosses | metadiscourse | MD-13, MD-14, MD-15 (*known as* only), MD-21 (kept, unchanged from round 1) | none |
| MD-E sources and evidentials | metadiscourse | MD-16, MD-17, MD-18, MD-19 (all reverted to 0.3.3 in round 2: no rule active) | none |
| MD-F stance (hedges, boosters, attitude) | metadiscourse | MD-20, MD-22, MD-23, MD-24, MD-26, MD-27, MD-28 (all reverted to 0.3.3 in round 2: no rule active) | none |
| MD-G reader/writer forms and directives | metadiscourse | MD-29, MD-31 (all reverted to 0.3.3 in round 2: no rule active) | none |
| MD-H quotation (writer's voice) | metadiscourse | MD-32 (kept, unchanged from round 1) | none |
| MD-I exclusive *we* | metadiscourse | SX-01 (past-tense *we*/*us* only; kept, unchanged from round 1) | none |
| PH-A USED TO and THAT IS | phrase | PH-01, PH-02 (with the recall correction; kept, unchanged from round 1) | none |
| PH-B entry-specific constructions | phrase | PH-04, PH-05, PH-06, PH-09, PH-11 (PUT IT, GET OFF), PH-12 (kept, unchanged from round 1) | none |
| PH-C matching form | phrase | PH-10, PH-13 (kept, unchanged from round 1) | none |

The rule statements of the kept families are those of the round-1 ledger ("Rules as revised after audits r1 and r2": MD-13/PH-02, MD-15, MD-32, SX-01, PH-11, PH-12, and the original statements otherwise). The round-1 entries for own_text, MD-08, MD-09, MD-11, MD-12, MD-16, MD-18, MD-22, MD-23, MD-24, MD-27, MD-29 and MD-31 describe reverted rules. They do not apply to the round-2 candidate.

**Order.** Each family is measured alone against the 0.3.3 baseline; the prerequisite is none. The complete candidate enables all twelve, which in round 2 equals enabling the six kept families. Where two families can act on the same hit, the complete-candidate frame counts the effect once (protocol, "Diff and label transfer").

## Code of the round-2 candidate

These are the files changed against the round-1 candidate (`3d4df70`). Against 0.3.3 (`dec79bc`), the candidate differs only by the kept families' code.

- **`src/lexinspect/metadiscourse.py`.** It is rebuilt from the 0.3.3 file plus the kept-family code, copied verbatim from round 1:
  - **MD-D:** `_fixed`, `not_degree`, `_CHANGE_OF_STATE`, `naming_known_as`, the four `_fixed("MD-D", …)` registrations, and `_reassign` with the MD-21 branch only;
  - **MD-H:** `_PARAGRAPHS`, `_possessive_apostrophes`, `_quoted`, `_inside`, and the quotation skip in `analyze`;
  - **MD-I:** `_OWN_WORK_NOUNS` and the past-tense branch of `exclusive_we`.

  `clause_initial`, `has_source_subject` and `_assign`'s signature are 0.3.3's again. The construction script is `.cache/validation/study4_fix040/round2/build_narrowed_metadiscourse.py`.
- **`src/lexinspect/_context.py`.** `spaced_hyphen` is removed; only MD-B and MD-F used it. A comment changes. Everything else, used by MD-D and the PH families, is unchanged.
- **`src/lexinspect/phrase.py`:** byte-identical to round 1.
- **`src/lexinspect/_fix_families.py`:** comments and docstring only. `FAMILIES`, `enabled` and `only` are unchanged.
- **`src/lexinspect/data/SOURCES.md`:** documentation (see Decisions).
- **Tests.**
  - `tests/test_metadiscourse.py` is 0.3.3's again; round 1 had changed one case for MD-11.
  - `tests/test_fix_families.py`: the 152 round-1 cases of reverted families become kind `reverted`, with `expected` equal to the 0.3.3 `before`. The 21 round-1 limitations of reverted families become `reverted` cases pinning their 0.3.3 output. All 103 kept-family cases and all 12 kept-family limitations are unchanged. Two reverted MD-G cases change expected_all to record MD-I's unchanged behaviour when MD-G is off (see Interactions).
  - New tests cover the twelve identities, each reverted family alone giving 0.3.3, and all twelve families equalling the kept six, on every case and limitation text.

## Interactions between kept and reverted families

**In the code.** Where a kept and a reverted family met in one code path in round 1, the kept family now behaves exactly as round 1 did with that reverted family off:

- **MD-G and MD-I, `_not_a_marker` before `exclusive_we`.** In round 1, MD-31 dropped a country `US` before MD-I's past-tense rule could reassign it to self-mentions. With MD-G reverted, MD-I reads `the US rose` as exclusive *us*, as round 1 did with MD-G off. Two `expected_all` values in `tests/test_fix_families.py` record this.
- **MD-B and MD-D, MD-I, `_not_a_marker`.** In round 1, the MD-B hyphen veto ran before every category check. With it gone, the MD-D and MD-I rules see such occurrences, as round 1 did with MD-B off. MD-H's quotation skip runs before `_assign`, so it is unaffected.
- **MD-E, MD-F and MD-D, `_reassign`.** The MD-18 and MD-20 branches ran before MD-21. Their markers (`_REPORTING_VERBS`, *always*) are disjoint from MD-21's *indeed*, so there is no behavioural interaction.
- **MD-A, MD-F, `_assign` early returns.** MD-25 (*even*) and MD-27 (*expected*) involve no kept-family marker.
- **`_fixed` wrappers.** No (marker, category) key is wrapped by two families in round 1, so removing the reverted wrappers leaves the MD-D wrappers' base checks (0.3.3) unchanged.
- **MD-B and `clause_initial`.** No kept-family rule calls `clause_initial`.
- **MD-D and PH-A share `_context.rephrasing_that_is`.** Both are kept.

**Measured.** This compares the kept families' effect in round 2 (all on versus 0.3.3) with their effect in round 1 (all on versus the reverted families alone), hit by hit, on the 842 texts below (fresh rerun on authenticated trees, `interaction_results.json`). A signed hit change is a hit removed or added; a position is (text id, module, start offset). 5,054 signed hit changes are common to both rounds. **311 signed hit changes differ (302 round-2-only, 9 round-1-only), at 292 distinct module/start positions in 105 texts** (273 positions with one change, 19 with two). Every one of these positions also has a reverted-family change in round 1 under the same module/start criterion; this shows co-location, not by itself a causal explanation.
- An example of the round-2-only kind: a quoted coordinator removed by MD-H that MD-A had already removed.
- An example of the round-1-only kind: a quoted *even if* that only existed as a transition through MD-25.

No non-overlapping (context or cascade) change was observed on the tested 842 texts. This is an observation on the tested corpus, not a proof that none exists on other texts. So the round-2 COMPLETE configuration is not round 1's COMPLETE minus the reverted families' changes. The kept families act at positions the reverted ones used to take first. The harness measures COMPLETE afresh, so this is sound, and it is disclosed here.

## Equivalence evidence (Task 1, 2026-10-18)

The script is `.cache/validation/study4_fix040/round2/equiv_check.py` (with `equiv_worker.py` and `evidence_provenance.py`), with results in `equiv_results.json` and `equiv_results.md`, regenerated fresh after review (provenance SHA-256 `fabde949c8159861f8ac087701ed02938e35596bb230d8826e3123ea2155280d`; the R1 and P trees are fresh `git archive` exports authenticated per blob, N the working tree checked byte for byte; every output binds the tree, script, configuration and per-text hashes, and reuse is refused unless all match). It compares, for each text and module, the SHA-256 of the complete output (counts, per-category tables, every hit). Three source trees are compared: N, the narrowed working tree; R1, the round-1 candidate `3d4df70`; P, the pinned 0.3.3 `dec79bc`.

There are 842 texts:
- the 120 Study 4 development texts, identical to the round-1 final dry run's `round_dev`;
- 300 Study 3 essays;
- 4 test fixtures;
- 418 sentences from the round-1 `test_fix_families.py`, `test_metadiscourse.py` and `test_phrase.py`.

The round-1 check texts were not used. All **143 of 143** checks are identical on all 842 texts in both modules:
- **(a) Kept families, 65 checks.** N `only(S)` equals R1 `only(S)` for all 64 subsets S of the kept families: each alone, all six together, and the empty set. N with all twelve on equals R1 `only(kept six)`.
- **(b) Reverted families, 76 checks.**
  - For each reverted F, N `only([F])` equals N `only([])` (6 checks) and equals P (6 checks).
  - N `only(S ∪ reverted six)` equals N `only(S)` for all 64 kept subsets S.
- **(c) Baseline, 2 checks.** N `only([])` equals P. As a sanity check, R1 `only([])` equals P.

**Hit totals over the 842 texts:**
- 0.3.3 (and N `only([])`) gives 51,174 metadiscourse and 14,578 PHRASE hits.
- N with all twelve on, and R1 with the kept six, both give 47,634 metadiscourse and 13,680 PHRASE hits.

**Shared parse.** Each text is parsed once per tree. The fresh-parse re-check, as executed, covered 16 texts (4 per text set) for each tree: R1 and N each in all 64 kept-subset configurations (64 unique configuration names, 1,024 text/configuration comparisons each), and P in its single configuration (16). All gave outputs identical to the shared parse (0 mismatches; worker SHA-256 `225af19ddea50014fb2586a29008548f9c5248126d1728cceaf99c575c627df3`). Overall success required both the 143 checks and these re-checks.

## Reviewed candidate snapshot

The narrowed candidate reviewed in `.cache/validation/study4_fix040/sol_round2_candidate_audit_r1.md` and used for the fresh evidence above (SHA-256, re-verified 2026-10-18; `src/lexinspect/phrase.py` is byte-identical to round 1):

| File | SHA-256 |
|---|---|
| `src/lexinspect/_context.py` | `0f468aca86cf84ed33baf84b26f72fd1462748a641f26bcf6db3204fe5cf17c9` |
| `src/lexinspect/_fix_families.py` | `b4b15798562f0113317b8a4e92db754937b949926083983926ed698a448ce3fa` |
| `src/lexinspect/data/SOURCES.md` | `2db7139ed803a70ccc3424045246a4aff94fee8105bc423ce5db1be6a45f6464` |
| `src/lexinspect/metadiscourse.py` | `4edd31600e12f09294ab2aee419bcf7b3e50d0983ac2c58cfa964be5f6ad03c3` |
| `tests/test_fix_families.py` | `67e258c16b41cb8f1b94ab346259670c2bbf55acabff96d00e5bb86b8420b6be` |
| `tests/test_metadiscourse.py` | `dc81ef094fd2e8e371d6e4ddf7cf5e87128932e61b1527d0ef139aafd7ea8e70` |

The N tree in the evidence run (all 78 `src/` files) has tree SHA-256 `1239a183270b7d5b…` (per-file hashes in `equiv_work/provenance.json`). The committed candidate `16aa95ef10e0ec5fc8df9113e794c85d13c8aafc` must reproduce these hashes.

## Error budget

- **J:** 4(F + 5) = 4 × 17 = **68** one-sided components, unchanged from round 1. This reserves, for each of 2 rounds × 2 modules: 12 family-removal upper bounds, 1 complete-candidate removal upper bound, 2 loss-total upper bounds (STRICT, and LENIENT or LIST_LENIENT) and 2 baseline-success lower bounds.
- **Allocation:** a = .05/68 = **0.000735294…** per component; unused allocation is never recycled.
- **Round 2 uses its reserved identities:** `R2.{module}.{family|COMPLETE}.{kind}`.
  - Reverted families have empty removal frames in both modules, so their R2 removal components are recorded as not applicable, never recycled.
  - Kept families' R2 removal components apply if their frames are non-empty.
  - The COMPLETE components are required as in round 1.
- **Component identities.** `docs/validation/study4-fix040/ledger_components.json` is the round-invariant enumeration of all 68 identities for both rounds (the content of `ledger.ledger_document()`). It is reused unchanged for round 2 and not regenerated. Its internal title still reads "round 1", a cosmetic leftover that cannot change without breaking round 1's binding.

## Implementation requirements

- **Toggles.** As in round 1, with the twelve names. The shipped default enables all twelve, which in round 2 means the kept six.
- **Equivalence.**
  - The kept families equal the round-1 candidate for every kept subset.
  - Each reverted family alone equals 0.3.3.
  - `only([])` equals 0.3.3.

  All three hold on the 842 texts above. The harness-level confirmation is the round-2 dry run's frames, compared with the round-1 final dry run (ROUND2_PLAN.md §3.1a): reverted families `N_affected = 0`, kept families' `hits.jsonl` byte-equal.
- **Tests.** Every kept rule keeps its change and keep cases, branch matrix and limitations from round 1. Every reverted rule has only `reverted` cases, which pin 0.3.3. The covered rule-ID set is asserted exactly.
- **Full suite.** `uv run --offline --frozen pytest -q -o addopts= -p no:cacheprovider`: 1421 passed, 3 skipped, 34 xfailed. The `test_fix_families.py` part is 883 passed and 34 xfailed. ruff check and format are clean on the changed files. Harness suite: 539 passed, 1 failed. The failure is `test_r6.py::test_r3_s2_public_documents_carry_no_inventory_fragment`, an `IsADirectoryError` on the `round1/` directory that has existed since the round-1 plan. It is unrelated to the candidate; its content check, run on the regular files, finds 0 fragments. The five frozen Study 4 inputs keep their SHA-256 values.

## Log

- 2026-10-18: round 1 registered as fail (`round1/accept/acceptance.md`). Maintainer decision: keep MD-D, MD-H, MD-I, PH-A, PH-B, PH-C; revert MD-A, MD-B, MD-C, MD-E, MD-F, MD-G; no new behaviour.
- 2026-10-18: narrowed candidate implemented in the working tree, not committed, by an Opus 5.5 agent (`.cache/validation/study4_fix040/round2/IMPLEMENTATION_REPORT.md`). Equivalence evidence and interaction counts were recorded above. This ledger was drafted as DRAFT.
- 2026-10-18: after independent review (audit r1, findings 2–4 and 6), the equivalence and interaction evidence was regenerated fresh with authenticated trees and hash-bound outputs (`EVIDENCE_REVISION_REPORT.md`); interaction counts relabelled as signed hit changes and positions; fresh-parse coverage stated as executed; reviewed candidate snapshot recorded. Status stays DRAFT.
