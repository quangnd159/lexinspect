# Study 4 fix check: lexinspect 0.4.0 matcher changes

**Recorded result: pass (round 2, registered 2026-10-19), with one disclosed blinding deviation.** The round-2 changes to the `metadiscourse` and `phrase` matchers met every numerical loss gate in the pre-registered fix protocol. The gates were measured against a reference built from language-model labels, on 60 texts never used in development. An independent recomputation reproduces every gate.

The final audit also found a deviation. The harness for one of the two labellers showed it repository metadata that the protocol says labellers must not see (see [Deviations](#deviations-and-corrections)). We tested that labeller's influence with a post-hoc sensitivity analysis, whose decision rule was committed before it ran. Every gate also passes under a reference built without that labeller's labels.

This check asks whether the changes lose reference-positive baseline detections too often. That can happen through deletion, or through harm to a claim that is kept, such as an incorrect reassignment under the strict reading. It does not show that every change is an improvement, and it does not estimate overall precision or recall. The Study 4 precision study has not been registered or run. Its [draft protocol](study4-preregistration.md) estimates precision against the operational reference, and concordance with the maintainer. It does not estimate recall.

## Why this check exists

The Study 4 development texts showed clear matcher errors. Exclusive *we* counted as reader engagement. Relative *that is* counted as a code gloss or PHRASE entry. Passive *used to* was read as the past habit. Errors fixed on the same texts used to judge the fix would overstate the gain. Each change, and the combined candidate, was therefore checked on previously unused texts against engineering margins for removal and cumulative loss, chosen in advance. The rules were written down and reviewed before any check text was collected:

- [fix protocol](study4-fix-protocol.md);
- [clarifications](study4-fix-protocol-clarifications.md);
- the run procedure, [RUNBOOK](study4-fix040/RUNBOOK.md);
- harness rulings for [round 1](study4-fix040/HARNESS_RULINGS.md) and [round 2](study4-fix040/round2/HARNESS_ROUND2_RULINGS.md).

## Design in brief

- **Families.** The changes are grouped into twelve families: nine for metadiscourse (MD-A to MD-I) and three for PHRASE (PH-A to PH-C). Each can be switched on alone over the 0.3.3 baseline (`src/lexinspect/_fix_families.py`). The candidate ledgers list the rules: [round 1](study4-fix040/CANDIDATE_LEDGER.md) and [round 2](study4-fix040/round2/CANDIDATE_LEDGER.md).
- **Texts.** Each round collected 60 new texts from the study's sources: 20 academic, 20 argumentative and 20 general. The audit checked source identifiers and full-text hashes: there is no overlap with the development set, or between rounds. The collection seed, command and plan were committed before collection.
- **What was labelled.** Three kinds of frame were labelled.
  - **Change frames:** each non-empty frame of affected baseline hits (by change type), and each frame of added or changed output. A frame was labelled in full when it had 200 or fewer rows, and randomly sampled at 200 otherwise.
  - **Counterparts:** a selected affected hit brought in every counterpart or same-span sibling needed to judge what replaced it.
  - **Baseline sample:** a separate stratified sample from the full 0.3.3 hit population, affected and unaffected alike, gave the denominator: 1,000 metadiscourse and 300 PHRASE hits.

  Identical judgement payloads were labelled once, keeping every sampling membership. Round 2 had 2,314 distinct labelled payloads.
- **Labellers.** There were two labellers, each working in separate fresh sessions under the same frozen item instructions:
  - **A:** Claude Sonnet 5.5, through Claude Code (`claude-sonnet-5-5`, effort high);
  - **B:** GPT-6.1-Sol, through Codex (`gpt-6.1-sol`, reasoning effort high).

  The item payloads contained no versions, families, pairings or other labellers' answers. DeepSeek V4.1 Flash (`opencode/deepseek-v4.1-flash-free`, reasoning high) adjudicated the items that the registered rule selects: all disagreements and non-votes, 99 items in round 2. The maintainer reviewed every session transcript against the access rules before its labels were accepted. No model that wrote matcher code labelled.
- **Gates (per module).**
  - **Removal:** for each family alone, and for all families together, the upper bound on the share of removals that the reference judges correct must be at most .15.
  - **Cumulative loss:** the upper bound on correct detections lost, divided by the lower bound on correct detections at baseline, must be at most .05. It is computed under the strict and the lenient reading of the guidelines. It counts deletions and, under the strict reading, correct hits moved to a wrong category.
  - **Error budget:** a total of .05 is divided across 68 reserved one-sided bounds covering both rounds and modules, so each uses a = .05/68. Unused allocation is not recycled. Unresolved labels count against the candidate.
  - **Certificates and procedure problems:** a deterministic breach certificate, a proof from the labels alone that a gate fails, fails the round. A procedure problem detected by the harness makes the round inconclusive.
- **What the bounds cover.** Coverage is conditional on the archived frames and on the model reference. It does not cover mistakes that the models share, uncertainty in which texts were selected, or transfer to other kinds of text. The .15 and .05 limits were chosen in advance as engineering tolerances. They are not established acceptable losses for educational or assessment use.
- **Two rounds at most.** Round 2 could only narrow or revert round 1's families, on new texts. There is no round 3.

## Round 1: fail

[Registered acceptance](study4-fix040/round1/accept/acceptance.md). Metadiscourse failed and PHRASE passed. "Judged correct" means the removal deleted a detection that the reference judges correct.

| Frame | Removals (N) | Judged correct | Upper bound | ≤ .15 |
|---|---|---|---|---|
| All metadiscourse families | 2,625 (200 sampled) | 23–24 | .205 | no |
| MD-A clause linking | 1,741 (200 sampled) | 25 | .210 | no |
| MD-B hyphens and brackets | 89 | 24–25 | .281 | no, certificate |
| MD-C frame and endophoric | 49 | 12 | .245 | no, certificate |
| MD-E sources and evidentials | 27 | 13 | .481 | no, certificate |
| MD-F stance | 72 | 14 | .194 | no, certificate |
| MD-G reader/writer forms | 88 | 12–13 | .148 | yes |
| MD-D code glosses | 139 | 13 | .094 | yes |
| MD-H quotation | 549 (200 sampled) | 4–5 | .069 | yes |

Metadiscourse's cumulative loss was .070 under the strict reading and .080 under the lenient one, against .05. PHRASE's was .0046.

## Narrowing

The maintainer reverted six families to 0.3.3: MD-A, MD-B, MD-C, MD-E, MD-F and MD-G.

- Four of them carried breach certificates, and MD-A's bound was over .15.
- MD-G passed at .148 but was reverted as a precaution. This was decided after seeing the result, and is disclosed as such.

The six kept families are unchanged: no rule was added or edited. The reasons are in the [narrowing disposition](study4-fix040/round2/NARROWING_DISPOSITION.md). The [narrowing check](study4-fix040/round2/NARROWING_CHECK.json) records the mechanical evidence: with only kept families on, the round-2 candidate behaves as round 1 did, and each reverted switch on its own behaves as 0.3.3.

## Round 2: pass

[Registered acceptance](study4-fix040/round2/accept/acceptance.md): 60 new texts, no breach certificates. The harness reported no procedure problems, but its list does not include the blinding deviation below.

| Module | Frame | Removals (N) | Judged correct | Upper bound | ≤ .15 |
|---|---|---|---|---|---|
| metadiscourse | all families | 675 (200 sampled) | 2 | .049 | yes |
| metadiscourse | MD-D code glosses | 118 | 4 | .034 | yes |
| metadiscourse | MD-H quotation | 560 (200 sampled) | 0 | .029 | yes |
| phrase | all families | 321 (200 sampled) | 2 | .037 | yes |
| phrase | PH-A USED TO, THAT IS | 182 | 3 | .016 | yes |
| phrase | PH-B constructions | 116 | 0 | .000 | yes |
| phrase | PH-C matching form | 24 | 0 | .000 | yes |

MD-I (exclusive *we*) only reassigns categories, so it has no removal frame. Its effect, like every family's, is in the cumulative gate.

| Module | Reading | Cumulative loss | ≤ .05 |
|---|---|---|---|
| metadiscourse | strict | .0052 | yes |
| metadiscourse | lenient | .0040 | yes |
| phrase | strict | .0034 | yes |
| phrase | list-lenient | .0034 | yes |

Across the 60 round-2 texts, the complete candidate gives 15,632 metadiscourse hits, against 0.3.3's 16,307. It gives 4,910 PHRASE hits, against 5,227. Added hits do not offset lost ones in the gates.

The terminal outcome, `ship`, is registered in [`round_registry.jsonl`](study4-fix040/round_registry.jsonl).

## Deviations and corrections

- **Repository metadata reached labeller A (both rounds).** The protocol says labellers receive only the judgement payloads, with no version, diff direction or family. Claude Code nevertheless added a git-status snapshot to every session of labeller A. It contained the branch name (`study4-fix040-candidate`), untracked file paths and the five most recent commit subjects, which in round 2's primary sessions included `round-2 candidate (narrowed)`. This affected 10 primary and 1 retry sessions in round 1, and 8 primary and 1 retry in round 2.

  The snapshot contained no item, label or expected answer. Nor did it say which items were baseline or candidate output, which family they belonged to, or that they were paired. Labeller B and the adjudicator did not receive it.

  The maintainer's access review noted the snapshot but did not treat it as a deviation. That was an error, found by the final audit. We cannot establish that the metadata had no effect on A's labels.
- **Sensitivity analysis for that deviation (post hoc).** The [plan and decision rule](study4-fix040/round2/BLINDING_DEVIATION_SENSITIVITY_PLAN.md) were committed before the analysis ran. The rule: ship only if every gate also passes without labeller A. The analysis reran the frozen acceptance calculation with labeller B's labels in place of A's, so the reference is B's label, or Flash's where B gave none. All other inputs were unchanged. Every gate passes:

  | Module | Frame or reading | Registered | Without labeller A |
  |---|---|---|---|
  | metadiscourse | all families (removal) | .049 | .049 |
  | metadiscourse | MD-D (removal) | .034 | .025 |
  | metadiscourse | MD-H (removal) | .029 | .0375 |
  | metadiscourse | strict / lenient (cumulative) | .0052 / .0040 | .0053 / .0040 |
  | phrase | all families (removal) | .037 | .037 |
  | phrase | PH-A / PH-B / PH-C (removal) | .016 / .000 / .000 | .016 / .000 / .000 |
  | phrase | strict / list-lenient (cumulative) | .0034 / .0034 | .0036 / .0036 |

  A control run of the same script with the real labels reproduces the registered result exactly. The outputs and their hashes are in [`round2/sensitivity/`](study4-fix040/round2/sensitivity/). The same numerical gates pass under this alternative reference: B's labels, with Flash only for B's non-votes. This shows the result is robust to removing A's direct contribution to the round-2 reference. It doesn't establish what fully blinded A sessions would have judged, make the historical execution protocol-conformant, or replace the registered decision.

  The frozen plan says "the exposure could not have produced the pass by itself". That refers only to this reproduced pass under the alternative reference. It is not a causal finding about A's labels, or about the counterfactual reference that two fully blinded primaries would have produced.

  The verification audit independently reproduced both runs. As its own exploratory check, it also kept B alone, treated B's 22 non-votes as unresolved and used no Flash labels. Every gate still met its margin: the largest removal bound was .055 (MD-H), and the largest cumulative bound was .0056. That check was not in the pre-committed plan and is not confirmatory.
- **Acceptance precedence (ruling A1).** The clarifications (section 3.4) say a procedure problem makes a round inconclusive, even when a certificate holds. Between the rounds we found that the frozen acceptance code chose `fail` for a certificate before checking for procedure problems. It was amended to the stated rule and independently reviewed before round 2 was frozen. Round 1's recorded procedure-problem list was empty, so A1 alone leaves its recorded `fail` unchanged. The opening summary in `fixcheck/accept.py` still describes the old order. The function's own docstring and code follow A1, and the frozen file is left as it is. The frozen [narrowing disposition](study4-fix040/round2/NARROWING_DISPOSITION.md) also uses "any single failing gate fails the whole round-2 candidate" as shorthand. The precise rule: failure to meet any required gate prevents a pass. A formal `fail` requires a deterministic breach certificate; otherwise the result can be `inconclusive`. The frozen disposition is also kept unchanged.
- **Round-1 adjudicator delivery.** A Flash server restart caused 30 records to be written twice. The final file had 210 lines for 180 assigned items. Under the frozen duplicate rule, 24 identical pairs collapsed and 6 conflicting pairs became adjudicator non-votes, leaving 174 valid adjudicator records. The maintainer chose no answer from any conflicting pair. The earlier copy, the final copy, the transcripts and the ruling, made before any gate was computed, are retained. Acceptance used the final file, with unresolved references counted worst-case.
- **Round-2 labelling retries.** Under the registered retry rule, 25 of labeller A's records were redelivered, because the alternative category repeated the claimed one. One of labeller B's records was redelivered, for an invalid label. The receipts are in [`round2/receipts/`](study4-fix040/round2/receipts/).

## Review

GPT-6.1-Sol had two roles, in separate sessions: primary labeller B, and methodological reviewer. Before the release audit, the retained fix-work reports were:

- 3 protocol reviews;
- 3 implementation reviews;
- 8 initial-harness reviews;
- 1 narrowed-candidate review;
- 3 round-2 harness reviews.

That makes 18 in total. After those came the final release audit, which reproduced every gate in both rounds and confirmed that the shipped code matches the checked candidate. A usage-limit interruption meant it was run twice, and both runs reported the same findings. A verification round then checked the corrections and the sensitivity analysis, and judged the release ready to ship with this disclosure. The draft precision protocol separately records 11 earlier Sol review sessions and 3 design reviews by GPT-6-Astra.

These counts describe repeated review by one model family. They are not independent human validation, and no trained human reference labelled the fix-check items. This directory publishes the rulings and dispositions. The original review reports are kept privately and are not all published.

## What is not public

The full fix-check packages are kept in a private archive. They contain:

- source texts, under the individual Creative Commons licences recorded in the collection manifests;
- PHRASE glosses and sense-inventory material, whose redistribution permission is still unresolved.

We have not published a separate, attribution-complete reproducibility package. The public SHA-256 receipts authenticate the retained packages ([round 1](study4-fix040/round1/receipts/), [round 2](study4-fix040/round2/receipts/)). They don't let readers recompute the gates without the sampling memberships, labels and reference inputs. The guidelines are bound by SHA-256 `276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e`, and are intended for publication with the precision-study registration. That deposit will state any access route and any remaining restrictions.

## Limits

- **Scope of the pass.** The registered calculation passed the loss safeguards against the model reference on round 2's archived frames. This covers deletions and, under the strict reading, harm through reassignment. It does not establish:
  - higher overall precision, or recall;
  - complete counts of the construct;
  - semantic correctness;
  - acceptable loss for any particular educational use.
- **The labels come from language models.** No human labelled the fix-check items.
- **Known rule gaps.** [CAVEATS.md](../../CAVEATS.md) lists them. Some genuine expressions are now missed, for example GET OFF in `We got off the train`, and `kind of a genius`. Some known errors remain. Constructed examples like these are not prevalence estimates. The gates measure aggregate loss and do not validate each rule.
- **Coverage.** The texts are English academic, argumentative and general prose from the study's sources. Learner writing is not covered.
- **Scope.** The result applies to the 0.4.0 matchers with spaCy `en_core_web_sm` 3.8.0. Any later change to matching needs its own check.
