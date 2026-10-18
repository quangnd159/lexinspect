# Study 4 fix check, round 2: narrowing disposition

**Status:** FINAL (set by the maintainer on 2026-10-19, after the final round-2 dry run)

**Decided by:** the maintainer, 2026-10-18, after the registered round-1 decision.

**Frozen identities.**

- Round-2 candidate commit: `16aa95ef10e0ec5fc8df9113e794c85d13c8aafc` (branch `study4-fix040-candidate`; `src/lexinspect` tree `e3b8db910707ae8d7ea09d5de40eda39c6453792`).
- Narrowing check: `docs/validation/study4-fix040/round2/NARROWING_CHECK.json`, SHA-256 `1413ca8f61c5c72a09c60cc22ef6b7b52e736edec62f9a9730eb44c3018b9082`, from the fresh final dry run of that commit against round 1's candidate `3d4df7012656defd5a44571410af00896f634a2d` (harness SHA-256 `7ecd312471d4526375d98cc94b2e2e8e60f2ab2e1cfe323710a5a53b2165c466`; round-2 ledger SHA-256 `ec4a8b22fb446c3213247d8195ed6e02ce7cb9a56374c9f6cd23070244f98d63`). Its `ok` is `true` and the published copy re-checks against the dry run with no problems. It is a development-text conformance check on the 120 development texts, not held-out validation.
- Kept families: MD-D, MD-H, MD-I, PH-A, PH-B, PH-C.
- Reverted families: MD-A, MD-B, MD-C, MD-E, MD-F, MD-G.

## 1. Basis

Round 1 is registered as a non-pass (`docs/validation/study4-fix040/round1/accept/acceptance.md`, status `fail`). The protocol allows a round-2 candidate to "narrow or revert the original families but [not] introduce new ones" (fix protocol, error budget section), and requires "a reviewed disposition for any narrowing of a family, bound into the round-2 freeze record" (clarifications 3.5). This document is that disposition.

The narrowing is chosen after seeing round-1 results. That is what round 2 is for. It is disclosed here in full. Round 2 is decided only on its own, new texts (disjoint from round 1's sources and from the development set), under the unchanged gates, error budget (J = 68, a = .05/68) and family identities. No round-1 label, count or bound is carried into the round-2 decision.

## 2. The round-2 candidate

| Family | Description | Round 2 | Round-1 evidence (removal frame: N, k_lo-k_hi correct removals, bound; certificate) |
|---|---|---|---|
| MD-A | clause linking and transitions | **reverted** | N 1741, n 200, 25-25, bound .2096 > .15 (no certificate) |
| MD-B | word-internal hyphens and brackets | **reverted** | census 89, 24-25, .281; breach certificate |
| MD-C | frame and endophoric markers | **reverted** | census 49, 12-12, .245; breach certificate |
| MD-D | code glosses | kept | census 139, 13-13, .094 |
| MD-E | sources and evidentials | **reverted** | census 27, 13-13, .481; breach certificate |
| MD-F | stance: hedges, boosters, attitude | **reverted** | census 72, 14-14, .194; breach certificate |
| MD-G | reader/writer forms and directives | **reverted** | census 88, 12-13, .148 (passed, at the limit) |
| MD-H | quotation (the writer's own voice) | kept | N 549, n 200, 4-5, .069 |
| MD-I | exclusive we | kept | no removal frame; reassignment frame N 252, n 200: 193 wrong-to-correct, 3 correct-to-wrong, 4 wrong-to-wrong (STRICT, unweighted) |
| PH-A | USED TO and THAT IS | kept | N 203, n 200, 5-5, .035 |
| PH-B | entry-specific constructions | kept | census 79, 0-0, .000 |
| PH-C | matching form | kept | census 29, 1-1, .035 |

Round 1's cumulative-loss gate failed for metadiscourse (STRICT fraction .070, LENIENT .080, limit .05) and passed for PHRASE (.0046). The round-1 result does not attribute cumulative loss to families; the reverted families include all four with breach certificates and the two others whose removal bound exceeded or nearly reached .15.

## 3. Reasons

- **MD-B, MD-C, MD-E, MD-F:** a deterministic breach certificate holds for each. Their removals delete correct detections at rates the protocol does not allow. They are reverted, not narrowed: no part of them has been shown safe on its own, and narrowing a family's rule set would need its own development evidence.
- **MD-A:** MD-A's removal bound was .2096, above .15. Although MD-A also made useful reassignments, we choose complete reversion rather than retain a subset of its existing rules. Such a subset could constitute permitted narrowing, but this disposition does not specify or establish a separately justified subset; no new condition or rule is introduced.
- **MD-G:** MD-G passed its round-1 removal gate: 12–13 correct removals among 88, worst-case share 13/88 = .1477, below .15. We nevertheless revert it pre-emptively because the observed frame leaves little margin, and any single failing gate fails the whole round-2 candidate. We do not estimate its probability of failing on new texts. This is an outcome-informed prudential revision, not a finding that MD-G failed or is unsafe elsewhere. It also removes MD-G's masking of MD-I on country US; that known cost and the combined candidate are evaluated afresh in round 2.
- **MD-D, MD-H, PH-A, PH-B, PH-C:** each passed its removal gate with margin. These are round-1 family-removal results only. They neither certify the revised COMPLETE candidate nor predict a round-2 pass. Round 2 recomputes every applicable gate, including both cumulative-loss outcomes, without pooling or offsetting gains against losses.
- **MD-I:** MD-I has no removal frame; this means no opportunity for deletion, not evidence of no harm. In round 1 its reassignment frame had 252 rows; among 200 sampled rows, the unweighted STRICT paired counts were 193 wrong-to-correct, 3 correct-to-wrong and 4 wrong-to-wrong. These descriptive results motivate retaining the unchanged rule for a new check; they do not establish acceptance, and corrections do not offset losses. With MD-G reverted, its existing country-US misclassification can be exposed. All reassignment harm and interactions remain subject to the round-2 COMPLETE cumulative-loss gates on new texts.

## 4. What "reverted" means

A reverted family keeps its identity (its name stays in `FAMILIES`, all twelve identities are kept), but its rules are removed: with only that family enabled, every output equals 0.3.3's, so the harness measures zero changes for it. For every subset S of {MD-D, MD-H, MD-I, PH-A, PH-B, PH-C}, the narrowed candidate with only S enabled has the same behaviour as round 1 (`3d4df70`) with only S enabled and all six reverted families off. Each reverted switch alone is baseline-equivalent and has no effect beside any kept subset. COMPLETE is evaluated afresh; it is not derived by subtracting round-1 effects. The round-2 COMPLETE configuration is not round 1's COMPLETE minus the reverted families: where a reverted family acted on an occurrence before a kept family in one code path (for example MD-G's country `US` check before MD-I's past-tense rule, or MD-B's hyphen veto before every category check), the kept family now acts on that occurrence as it did in round 1 with the reverted family off. On 842 local development and test texts, the comparison identifies 311 signed hit changes (302 round-2-only and 9 round-1-only), at 292 distinct module/start positions in 105 texts. Every changed position also has a reverted-family change in round 1 under the same module/start criterion. No non-overlapping interaction was observed on these texts. The harness measures round 2's COMPLETE afresh. The equivalence evidence is recorded in the round-2 candidate ledger, and the harness's round-2 dry run checks kept-family identity independently (`kept_family_identity`).

## 5. Disclosure

The round-2 report and the 0.4.0 release notes will state: round 1 failed; the six reverted families and the reasons above; that MD-G was reverted pre-emptively after passing; and that round 2 alone decides the narrowed candidate. If round 2 does not pass, the terminal outcome is `revert_0.3.3` or an amendment; there is no round 3.
