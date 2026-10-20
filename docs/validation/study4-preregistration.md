# Study 4 pre-registration: precision of metadiscourse and PHRASE detection

**Status: DRAFT, not registered.** This plan is registered in two archived stages (see "Registration and freeze"), both before any evaluation item is labelled. A local Git timestamp alone is not the registration date: each stage is deposited in a timestamped, externally retained record that names the Git commit and the hashes. Stage-1 placeholders identify the actual final development, model, code and simulation artefacts. Stage-2 placeholders identify the single evaluation build. Development values are never substituted for evaluation counts or results. Any deviation from this plan is reported with the results, giving its timing, its reason and its consequences.

## Question

When lexinspect flags a span as a metadiscourse marker in one of Hyland's (2005) ten categories, or as an expression from the PHRASE List (Martinez & Schmitt 2012), how often is the flag right? This is **precision**.

The study doesn't measure:

- recall (what lexinspect misses);
- whether the reference labels are themselves correct;
- how precise lexinspect is on kinds of text outside the evaluation population, including learner writing (see "Limitations").

## What is tested

- **Version and modules:** lexinspect 0.4.0 at commit `0556d0826001112eb6a82d08883e3592d05010ea` (tag `v0.4.0`), with spaCy 3.8.14 and the pipeline package `en_core_web_sm` 3.8.0, on Python 3.12.5, modules `metadiscourse` and `phrase`, as shipped in that release. lexinspect customises the tokenizer's infix rules (`src/lexinspect/_nlp.py`). Stage 1 records the source and data hashes, the lock file (`uv.lock`), the environment, the tokenizer and pipeline customisations and the release identity (`docs/validation/study4-freeze.json`). The evaluation executes this archived configuration.
- **Scope:** results describe this version only. Any later change to matching needs a new measurement (see "After the study").

## Development and evaluation

The study keeps calibration and testing apart.

- **Development sets.** Each is development data, and no development label or result is reported as evidence of precision.
  - **The original development set** (seed 20261016, built 2026-10-16 with lexinspect 0.3.2): the pinned 120 texts, 40 per register, and a stratified sample of 1,300 hits. It was used to develop the guidelines, the sense inventory, the matcher fixes, the labelling workflow and the analysis, and for the 0.3.2 pilot.
  - **The 0.4.0 common development pilot** (2026-10-20): the full 0.4.0 hit population on the same 120 text bytes, and a newly identified sample of 1,300 hits drawn with sample seed 473840911 (`docs/validation/study4-pilot040/`). It calibrates the final simulation (see "Pilot").
  - **The fix-check sets:** two disjoint rounds of 60 new texts each, collected for the 0.4.0 fix check (`docs/validation/study4-fix-protocol.md`, `docs/validation/study4-fix-check.md`, `docs/validation/study4-fix040/`). Each has its own manifest.
  - **Training:** the maintainer's practice labelling page uses development items and is training, never evaluation data.
- **Evaluation set:** fresh texts from the same sources, drawn once, by the procedure in "Registration and freeze".
  - **Exclusion:** the evaluation build excludes the canonical 120-text development source manifest and a separately frozen manifest containing every fix-check or additional fix-development text collected or inspected in any round, including failed, inconclusive and superseded rounds. Canonical-development and additional-exclusion paths, hashes, source counts and normalised identifier counts are recorded in stage 1. Exclusion uses all available source identifiers, titles, DOIs, article/page identities and revision/full-text URLs; a new revision of an exposed source does not make it evaluation-eligible. The frozen evaluation build command passes the additional manifest through `--exclude-texts`. Local T-number identifiers alone are not used to establish source separation.
    - **The canonical development manifest:** `.cache/validation/study4/texts.jsonl`, SHA-256 `5dba40ccbb99a853ef32e6f3def90f992810ff2320cf98f366e227d7112f1cc8`, 120 distinct texts. `build.py` checks this hash and always excludes every identifier of these texts.
    - **The additional exclusion manifest:** `docs/validation/study4-exclusions/exclusions.jsonl`, SHA-256 `477f2197ce00e402441d810c4825e6d98517be4fa1e50d59ee2d4c0800f9b263`, with its inventory, tools and README in the same folder. It lists 909 sources beyond the 118 that are only development texts. Together with those, there are 1,027 distinct exposed sources: 118 Europe PMC, 585 English Wikipedia and 324 Simple English Wikipedia.
      - **Labelled texts:** the 120 development texts and the 2 × 60 fix-check texts (240 distinct, disjoint);
      - **Fetched but rejected:** 146 candidates fetched and rejected by the eligibility filters in development or either round;
      - **Study 3:** the 50 English and 50 Simple English Wikipedia texts (part of the fix check's equivalence evidence);
      - **Study 1:** 548 CLEAR excerpts (274 English and 274 Simple English pages) that cite a Wikipedia URL. They were never used in Study 4 development and are excluded as a precaution.

      `build.read_exclusions` gives 3,132 normalised identifiers. With the development manifest's 440, the union holds 3,563. English Wikipedia sources are matched by page id as well as by title and revision. The page ids of the 317 records that had only titles were looked up on 2026-10-21; 14 of those pages had been renamed. Simple English titles are kept as aliases, so a same-title English article is excluded too. The constructed test sentences and fixtures are not sources and are not listed.
    - **Pools:** the evaluation build uses the 2026-10-16 pool snapshot, through a byte copy of the development download cache made into the evaluation build's own cache, with no `--refresh`.
  - **Overlap check:** after collection, the evaluation build checks all evaluation source identities against the union of these exclusions, records the result and requires zero overlap. Known duplicate copies or aliases of exposed texts are also excluded and documented. The same exclusion union applies to any later remeasurement, together with all evaluation sources.

### What development may change

- **Allowed changes:** before the protocol freeze, development may change:
  - text-extraction and matching defects;
  - the guidelines and the sense inventory;
  - the prompts;
  - the validation and delivery workflow.
- **The log:** every iteration is logged with its date, reason, changed files and their hashes, the development items, labels and results inspected, and the resulting version. The actual number of iterations is disclosed.
- **Old builds and labels** are kept. The original development text set stays the pinned 120 texts. Additional fix-check texts form separately identified development sets with separate manifests; they are never merged into evaluation or silently substituted for that original set. A matcher change may produce a new development hit sample, identified as such.
- **No pooling across versions:** labels produced under different guideline, inventory or prompt versions are not pooled for the final pilot rates or for choosing the adjudicator. When an applicable rule changes, the final common pilot is relabelled.
- **When the pilot ends:** when the final workflow runs without an unresolved delivery or validation defect, and the final versions and adjudicator choice have been reviewed and archived.
- **What the pilot can't change:** it doesn't authorise silent changes to the estimands, outcome mappings, reference rule, audit targets, phase-one targets, allocation, interval methods, α or reporting family. Any such change needs an explicit revised draft, reviewed before the protocol freeze.
- **Evaluation data:** no evaluation label, item judgement or result is used in development or selection.
- **After the freeze:** a substantive change after the protocol freeze needs a dated amendment and a newly identified evaluation build. After labelling starts, any change is reported as a deviation.

### Pilot

The pilot runs on the development set only, before registration.

1. **Labelling:** A and B each label the same complete development sample under the final pilot guidelines and inventory. Both get the single missing/invalid-record retry. Records from dry runs or earlier iterations are kept but never mixed with the final pilot records.
2. **What it measures:** how often the labellers disagree, how often items need adjudication, how often they end up unresolved, how often each label is used, and STRICT precision against the model reference, both unweighted and design-weighted.
   - **History.** The original lexinspect 0.3.2 development pilot yielded unweighted STRICT precision .622 metadiscourse and .670 PHRASE, and design-weighted estimates .491 and .836, against the operational model reference. These historical figures motivated development and are retained with their original records. Its labelling sessions inherited repository context (see "Labellers").
   - **The final pilot.** The final 0.4.0 common development pilot is separately identified by its sampling, label and version manifests (`docs/validation/study4-pilot040/`). Its unweighted and design-weighted estimates, adjudication and non-resolution counts are reported with actual denominators:
     - **STRICT precision, unweighted:** 693/999 = .694 metadiscourse, 230/300 = .767 PHRASE;
     - **design-weighted (N_h/r_h):** .554 and .870;
     - **STRICT reference from the adjudicator:** 54 metadiscourse and 12 PHRASE items; **unresolved:** 1 and 0;
     - **adjudication requests:** 84 (67 and 17), with 1 adjudicator UNSURE and no missing or invalid record;
     - **A–B STRICT agreement:** .961 (945/983) and .960 (288/300).

     No label from the 0.3.2 pilot was reused.
   - **The simulation.** The final simulation's main-pilot targets and resolution parameters use that final pilot; every parameter in "Evidence for the analysis" names its source pilot/version. Reusing the same numerical value requires actual support from the final pilot or an explicit decision to treat it as an assumption, not simply carrying the old label forward. The parameters are set before the final validation run.
3. **Reporting:** pilot results are reported as development results.

### Choosing the adjudicator

The rule is fixed and archived, with its date and hash, before any candidate output is inspected.

**Calibration set.**

- **Eligible items:** valid, definite A and B STRICT values that agree.
- **Drawing it:** eligible ids are sorted separately by module and shuffled with `random.Random("study4-adjudicator-calibration-20261016-" + module)` under the recorded Python version. The first 100 per module are taken.
- **Too few eligible items:** if either module has fewer than 100, selection stops, and the protocol is amended and reviewed before registration. The denominator is never reduced after seeing candidate results.
- **Archiving:** the 200 ids and their file hashes are archived before any candidate runs.

**The candidates' items.** The development adjudication set comes from the same `needs_adjudication` rule used in evaluation. Each candidate labels the union of the two sets, deduplicated by id. The labelling is blind and uses the same instructions and retry rule as the primary roles. All candidates receive the same union, in the frozen adjudicator-role order.

**Candidates.** In order of preference:

1. DeepSeek V4.1 Flash, through OpenCode's free route (`opencode/deepseek-v4.1-flash-free`, reasoning "high");
2. the fallback, GPT-6-Sol (OpenAI, reasoning "high").

GPT-6.1-Sol can't adjudicate, because it is labeller B. DeepSeek V4 Pro and the paid DeepSeek routes were not available to the project.

The exact route and effective settings are recorded.

**Data disclosure.** The free route's terms may allow the provider to keep or train on submitted data. The items include PHRASE List glosses and examples, and the sense inventory, whose redistribution the list's first author has not yet approved. The maintainer accepted this risk on 2026-10-16. It is reported with the results.

**Scores.**

- **Completeness:** valid distinct assigned ids after the retry, divided by all distinct assigned ids.
- **Calibration agreement:** the number of the 200 calibration items on which the candidate gives a valid, definite STRICT value equal to the agreed A–B value, divided by 200. Missing, invalid and UNSURE values count as 0.
- **No rounding:** no figure is rounded before it is compared.
- **Qualifying:** completeness ≥ .98 and calibration agreement ≥ .85.

**Choosing.**

- If Flash qualifies, Flash is chosen.
- If Flash doesn't qualify, or can't be run, GPT-6-Sol runs on the same blind sets and must meet the same qualification rule.
- If GPT-6-Sol also fails or can't be run, registration stops until a dated, independently reviewed replacement is specified.
- After registration, the adjudicator never changes automatically.
- Transport errors may be resumed from the archived assignment. They never justify extra judgement retries, or choosing among several valid responses.

**What the disputed-item outputs are for.** They are archived and summarised as development diagnostics. They don't select the adjudicator, tune the thresholds or affect evaluation precision.

**What the .85 floor is.** It is a pragmatic consistency screen, not a validated correctness floor. Calibration excludes A–B STRICT disagreements but can retain mistakes the primaries share. It establishes neither correctness nor performance on disputed items. So we report, for each candidate, by module:

- the prevalence of each target value;
- agreement in each direction;
- detailed-label agreement;
- non-votes.

**Publication.** The chosen model, route, settings, scores, denominators, non-votes and rejected candidates are published with the development report.

**The qualification's scope.** Flash's original qualification (193/200 agreement with definite agreed primary STRICT values) concerns the archived original calibration set. It is not a correctness estimate or a guarantee for the final detector's changed hit distribution. Flash remains the selected adjudicator unless a prospectively reviewed amendment is needed; it is not replaced to improve development precision. On the final common pilot we report its completeness, unresolved responses and agreement diagnostics by module and change status, including new/changed claims. If a new qualification or candidate-selection procedure is required, its assignment, criteria and fallback rule are archived before the corresponding candidate outcomes are inspected. A semantic change to the reference instructions invokes the common-pilot and selection amendment rules; it cannot inherit the old qualification as if nothing changed.

**On the final pilot** (`docs/validation/study4-pilot040/RESULTS.md`):

- Flash was complete: 84 of 84 requests got valid records, with 1 UNSURE and no missing or invalid record.
- Of the pilot's 1,300 items, 9 are new or changed claims under 0.4.0 (7 metadiscourse, 2 PHRASE). None needed adjudication, so every request concerned a claim unchanged since 0.3.2.
- On STRICT, Flash agreed with A on 39/58 metadiscourse and 15/17 PHRASE requests, and with B on 31/58 and 7/17.

No guideline, inventory or prompt changed, so no new qualification was run.

### Matcher fixes

Errors found in development are fixed before the protocol freeze. The version tested is the fixed version. Development scores are used only for development and calibration, never reported as evaluation precision.

Before stage 1, lexinspect 0.4.0 was developed using the original 0.3.2 pilot and the separately identified fix-check process. The archived fix protocol, amendments and candidate ledger record the rules tried, evidence inspected, code/model identities, accepted and rejected changes, checks, non-votes, collateral loss and actual number of iterations. Every fix-check set is development data and is excluded from evaluation. The study measures the frozen final version's precision; it does not test a pre-registered hypothesis that 0.4.0 improves on 0.3.2 or 0.3.3. Development before/after differences cannot establish that comparative claim.

**What happened** (`docs/validation/study4-fix-check.md`):

1. **The baseline.** The 0.3.2 pilot exposed matcher errors. Release 0.3.3 first fixed tokenisation defects found by Study 3, and 0.3.3 is the fix check's baseline.
2. **The candidate.** The candidate grouped its changes into twelve families: MD-A to MD-I for metadiscourse and PH-A to PH-C for PHRASE. Two rounds of independent methodology audit revised them before any check text was collected, including the maintainer's addenda A1–A3 (`study4-fix040/CANDIDATE_LEDGER.md`).
3. **Round 1** (60 new texts) failed for metadiscourse and passed for PHRASE.
4. **Narrowing.** Six metadiscourse families were reverted to 0.3.3: MD-A, MD-B, MD-C, MD-E, MD-F and MD-G. MD-G had passed at .148, so its reversion was a precaution decided after seeing the result.
5. **Round 2** (60 further new texts) checked the narrowed candidate. It passed every gate, and it was the last round the protocol allowed.
6. **The disclosed deviation.** Labeller A's sessions in both rounds carried a git-status snapshot of repository metadata. A post-hoc sensitivity analysis, specified before its retained execution, found that the same numerical gates pass under B's labels with Flash only for B's non-votes, removing A's direct contribution to the round-2 reference. This does not reconstruct fully context-isolated primary judgements or repair the historical procedure. Labeller B and the adjudicator also ran with the repository as working directory (finding F1; correction in `docs/validation/study4-fix-check.md`).
7. **The release.** 0.4.0 ships the round-2 candidate.

On the 60 round-2 texts, metadiscourse output fell from 16,307 to 15,632 hits and PHRASE from 5,227 to 4,910. These are development diagnostics, not precision or recall estimates.

**Complete output changes** (`docs/validation/study4-development-effects.md`, with every number in its JSON). This gives hit counts and hits per 1,000 words by category or K-band and register for 0.3.2, 0.3.3 and 0.4.0 on the 120 development texts, and for 0.3.3 against each round's candidate on the fix-check texts. It also gives each family's net change and summarises the published gates, losses, unresolved references and added or changed output. Every count comes from archived detector output.

## Registration and freeze

**Stage 1: protocol freeze.** Before any evaluation text is collected, we archive:

- the detector: the 0.4.0 release identity, source and data hashes, lock file and environment;
- the guidelines and inventory;
- the prompts and role-specific system or developer instructions, the tool and file access each role gets, and the effective context of each role's launch settings (`docs/validation/study4-pilot040/LAUNCH.md`);
- the analysis and sampling code, and the simulation and its results (the historical 0.3.2 run and the final 0.4.0 run);
- the selected adjudicator;
- the original 0.3.2 pilot and the final 0.4.0 common pilot: sampling, label and version manifests, results and hashes;
- the fix protocol, its clarifications and amendments, both candidates and rounds, the candidate ledgers, sampling and judgement identities, decisions and review dispositions (`docs/validation/study4-fix040/`);
- the collection targets and eligibility rules;
- the exact evaluation seed;
- the exclusion manifests (canonical development and additional exposure), with their hashes and counts;
- the policy for snapshotting the cache and source pools;
- the build command.

**The evaluation build, as frozen at stage 1.**

- **Seed:** 3195330621. The rule is the first 8 hex digits of `sha256("study4-v040-evaluation|20261016")`, read as an integer. It was fixed on 2026-10-21, before any evaluation text existed.
- **Pools:** the 2026-10-16 pool snapshot. Before the build, the development download cache is copied byte for byte:

  ```
  set -e
  mkdir .cache/validation/study4_eval
  cp -Rp .cache/validation/study4/raw .cache/validation/study4_eval/raw
  ```

  This is the one-time preparation for the unopened evaluation destination. If `.cache/validation/study4_eval` already exists, any retained attempt is investigated before proceeding. The copy, including every pool file, is verified against the cache's file-hash inventory frozen in `docs/validation/study4-freeze.json` before collection. Recovery from an incomplete build follows the registered technical-failure rule.

- **Command,** run from a clean checkout of the stage-1 commit:

  ```
  uv run --offline --no-sync python -I scripts/validation/study4_precision/build.py \
      --set evaluation --seed 3195330621 \
      --out .cache/validation/study4_eval --raw-cache .cache/validation/study4_eval/raw \
      --exclude-texts docs/validation/study4-exclusions/exclusions.jsonl
  ```

  With no `--refresh`, cached pool listings are reused and only new texts are downloaded. The maintainer-sample totals and batch size are the defaults (300 and 300; 325). `build.py` refuses a tree with uncommitted changes under `src/`, checks the canonical development manifest's hash, excludes both manifests' identifiers while drawing, and stops if any collected text overlaps the union.

**Stage 2: one evaluation build.** We generate exactly one evaluation build from that specification. Before any evaluation label is requested or inspected, we archive the final registration package: the build's inputs, allocations, orders, counts and hashes, linked to the stage-1 record.

**Between the stages:** no substantive procedure or seed changes.

**No selecting builds.** Builds are never redrawn or chosen on the basis of detector output, apparent difficulty, precision, concordance or labels.

- **Failed or incomplete builds:** they and their logs are kept.
- **Technical failure:** it is repaired with the same seed and frozen inputs. If that's impossible, a dated amendment explains the failure and the replacement procedure before another build is collected.
- **Evaluation sources:** they stay excluded from later development whether or not a build completes.

**Where the record is kept.** The timestamped record is an institutional archive, a public repository deposit with an independently recorded receipt, or a registration service. The protocol and code commit are recorded inside the package. The final registration commit is identified in the external receipt and in the results.

## Texts and population

- **Registers:** the same three as the development set, with a target of 40 texts each (academic: 14 sciences, 13 social sciences, 13 humanities). These are seeded selections from the frozen journal/year and Wikipedia pool lists in `build.py`, under its eligibility filters. They are not a probability sample of any wider text population. Actual totals: ⟨freeze⟩.
  - **academic:** CC BY or CC0 research articles from Europe PMC (full-text JATS XML; abstract and body only), balanced across sciences, social sciences and humanities by journal pools;
  - **general:** English Wikipedia Level-3 Vital Articles (CC BY-SA 4.0);
  - **argumentative:** Category:Wikipedia essays (CC BY-SA 4.0), excluding subpage titles and detected humour categories.
- **Eligibility:**
  - **Minimum length:** 1,500, 1,000 and 500 whitespace words for academic, general and essay texts, assessed before truncation.
  - **Academic articles:** the build also accepts qualifying US-government public-domain articles; this stays enabled in the evaluation build.
  - **Shortfalls:** shortfalls and rejection reasons are reported. No new pools or relaxed filters are introduced to fill a shortfall without an amendment.
  - **Logs:** the frozen pool listings and selection log are archived.
- **Length:** every text is capped at 50,000 UTF-8 bytes, cut at a paragraph boundary.
- **Population:** every hit the tested version produces on the evaluation texts: ⟨freeze⟩ metadiscourse hits and ⟨freeze⟩ PHRASE hits. Overlapping hits are separate units when the detector emits them separately.
- **The estimand:** precision in this finite population of hits, conditional on these texts. Confidence limits cover the uncertainty from sampling hits. They don't cover the uncertainty from choosing texts, or error in the reference labels.
- **Where results apply:** to these hits. They suggest, but don't establish, precision on edited academic, encyclopedic and argumentative English of similar kinds. They say nothing about learner or student writing. We did not identify a learner or student corpus whose terms allow the unrestricted redistribution we intend: the alternatives we checked carry non-commercial or no-derivatives restrictions (PERSUADE 2.0 and ELLIPSE CC BY-NC-SA 4.0, PELIC CC BY-NC-ND 4.0).
- **Sources:** each text's URL, revision or article ID, and licence are recorded in the build. `scripts/validation/study4_precision/build.py` rebuilds the set from the cached downloads, which are preserved with the build.

## Sample

**Phase one: the labelled sample.** It is drawn within strata, and within each sub-stratum h it is a simple random sample without replacement of n_h hits from N_h. Sub-strata are sampled independently.

- **Metadiscourse:** a target of 100 per category, capped at the available hits.
- **PHRASE:** up to 300 items in total, spread across the non-empty strata of frequency band (K1–K5) × single/multi-sense.
  - **Allocation:** the frozen `water_fill` algorithm makes the allocation as even as possible, never exceeding a stratum's population. Spare capacity is redistributed, with remainder ties broken in sorted stratum-name order.
  - **Multi-sense:** the matched entry shares a variant wording with another entry, or the hit has `also_possible` alternatives (`polysemous_ranks` and `_phrase_stratum`).
- **Marker sub-strata.** Within each phase-one stratum, let n be its target, capped at the available hits, and J its number of marker or PHRASE-entry groups.
  - **Initial cap:** `max(ceil(.15·n), ceil(n/J))`.
  - **Separate markers:** repeatedly, a marker whose proportional allocation from the remaining population exceeds the cap gets its own sub-stratum. The rest are pooled.
  - **Filling the target:** if the pool can't fill the remaining target, the capped allocations are raised, largest marker population first, ties by name, until the target or the population runs out.
  - **What 15% means:** a design target that can be exceeded, not an absolute cap. The sub-strata are part of the design, not exclusions made after sampling.
  - **Sampling:** each sub-stratum is a simple random sample without replacement. Its actual N_h and n_h are archived.
- **Recorded before labelling:** the allocations, including any stratum with fewer hits than its target, are recorded in the key. The frame (`frame.json`) records N_h and the register counts of every sub-stratum from the complete hit population.

**Phase two: the maintainer audit.**

- **Size:** a target of 300 metadiscourse items and 300 PHRASE items, drawn from phase one and capped at its size. Actual totals: ⟨freeze⟩.
- **Metadiscourse:** each sub-stratum gets min(2, n_h) items. The remainder is allocated in proportion to N_h, capped at n_h, using the frozen largest-remainder rule with ties broken by name. Within each sub-stratum the items are a seeded simple random sample from phase one.
- **PHRASE:** phase one holds 300 or fewer items, so the audit includes all of them. This is a census of the PHRASE phase-one sample, not of all PHRASE hits.
- **Inclusion probability:** an audit item's composite inclusion probability is m_h/N_h.
- **Fixed in advance:** the audit is never enlarged, reallocated or replaced on the basis of labels.

**Orders and batches.**

- **Orders:** every labeller role gets its own seeded, independently shuffled order of its items. The seed for role R is "⟨freeze: seed⟩-order-R".
- **Model batches:** up to 325 items each; the last batch may be smaller.
- **Records:** batch assignments are recorded in manifests with file hashes (`batches.py`).
- **Later assignments:** adjudication and retry assignments depend on labels, so they can't be in the stage-2 package. Their generation algorithm and base order are frozen. Each derived manifest is archived, with its parent hashes and derivation time, before that assignment is delivered.

**Frozen files.** The SHA-256 of each is recorded in the freeze manifest:

- **Evaluation build:** `texts.jsonl`, `hits.jsonl`, `frame.json`, `population.json`, `items.jsonl`, `key.jsonl`, `orders.json` and `manifest.json`, plus every batch manifest.

## What is frozen

The following are frozen at stage 1, and their SHA-256 values are recorded in the freeze manifest:

- **Guidelines:** `docs/validation/study4-guidelines.md`, version 3.2, SHA-256 `276d35e86ffa9da147d09734cf0c3fd9ed89bd6694d9d44a860cb6e851f0466e`.
- **The PHRASE sense inventory** (`phrase_sense_inventory.md`, version 2.1, SHA-256 `a761f159541023fd51f5ca45e1fc44432b572ab22ffcad74f414b1e35a776a5d`). It is part of the guidelines but is kept out of the public repository until the PHRASE List's authors permit redistribution. Its hash is published, and the file is published once permission is granted.
- **The labeller prompts**, given below.
- **Analysis code:** every script in `scripts/validation/study4_precision/` (`build.py`, `frame.py`, `batches.py`, `analyse.py`, `estimators.py`, `human_page.py`, `simulate_coverage.py`, `test_analyse.py`), and the labelling launcher and screen in `pilot040/` (`launch.py`, `check_sessions.py`, `collect_role.py`).
- **Environment:** `uv.lock`, and the Python and dependency versions.
- **The validation simulation's manifest** (see "Evidence for the analysis"). It identifies exactly which code was validated.

Nothing in this list changes after registration. A change found necessary after registration is a deviation and is reported as one.

## Labellers

All labellers work blind and independently. In addition to the generic provider context explicitly inventoried in the launch record (`docs/validation/study4-pilot040/LAUNCH.md`), each labelling role receives only the following study-specific materials:

- its assigned items: id, module, context, marked span, and the claimed category or PHRASE entry with its other listed senses;
- the frozen guidelines and sense inventory;
- in the maintainer's second pass only, the maintainer's own first-pass UNSURE note.

No role is given another labeller's responses, source or key information, or analysis results.

| Role | Labeller | Items |
|---|---|---|
| Primary A | Claude Sonnet 5.5 (Anthropic) | all phase-one items |
| Primary B | GPT-6.1-Sol (OpenAI) | all phase-one items |
| Adjudicator | DeepSeek V4.1 Flash (`opencode/deepseek-v4.1-flash-free`, reasoning "high"), chosen in the original 0.3.2 pilot by the rule in "Choosing the adjudicator": completeness 284/284, calibration agreement 193/200 = .965 (metadiscourse 95/100, PHRASE 98/100) on that pilot's calibration set, no calibration non-votes; two UNSURE responses among its 86 adjudication requests. This qualification is historical and doesn't guarantee performance on 0.4.0's hits (see "The qualification's scope"). On the final 0.4.0 pilot: 84/84 valid, 1 UNSURE. The GPT-6-Sol fallback was not run under the rule. | every item needing adjudication (below) |
| Maintainer H | the maintainer (Quang Nguyen) | the frozen audit sample, targeted at 300 per module and capped at phase-one availability |

The exact model identifiers, settings and run metadata are recorded in the freeze manifest and with the labels.

**Independence and conflicts.**

- **Who built lexinspect:** the repository history credits Claude Opus 4.7, 4.8 and 5.5 as co-authors of lexinspect's code, including the metadiscourse and PHRASE matching. Claude Opus 5.5 also wrote these guidelines, the sense inventory, the sampling and the analysis code.
- **Who labels:** none of those models labels any item. Labeller A, Claude Sonnet 5.5, is from the same provider as the code's authors. It might therefore lean towards accepting their rules.
- **How that is balanced:** if a DeepSeek model is selected, adjudication uses a third provider. The GPT-6-Sol fallback shares OpenAI with primary B; if it is selected, this exception is disclosed with it.
  - **How the reference is built:** it takes agreed definite A–B outcome values, and otherwise the adjudicator's definite value. It isn't a vote on full labels.
  - **What separation can't do:** keeping providers and sessions separate doesn't make their errors independent or establish correctness.
  - **Primary-only results:** precision with each primary labeller alone as the reference shows some differences between references. It can't detect errors they share.
- **GPT-6.1-Sol has two roles.** It is labeller B, and it was also the methodology reviewer, in separate sessions before registration:
  - **before the fix check:** eleven sessions (one study-design review, three guideline reviews, four analysis-code reviews, two reviews of this plan with the code, and one final-results verification);
  - **the fix check:** eighteen fix-work reviews (three protocol, three implementation, eight initial-harness, one narrowed-candidate and three round-2 harness reviews);
  - **the release audit:** run twice because of a usage-limit interruption, then one verification round;
  - **the Stage-1 package:** ⟨stage-1 review count⟩.

  Three earlier study-design reviews were by another OpenAI model, GPT-6-Astra, which has no labelling role. During its reviews GPT-6.1-Sol saw development and fix-check items, never evaluation items. Each labelling batch runs in a fresh session with no memory of the reviews. Review sessions by one model family are not independent annotators, and they are not human validation.
- **The maintainer** created lexinspect and steered the guidelines. The audit therefore measures concordance with the maintainer, not with an independent expert. An independent trained annotator is the main improvement left for future work.

**Adapted framework.** The guidelines operationalise Hyland's (2005) model for single flagged spans. Where Hyland gives no ruling, they adopt explicit Study 4 conventions, each marked as such in the guidelines:

- the precedence for *see* with another text;
- proposition-based tests for transitions;
- *this paper* as a self-mention;
- the PHRASE construction rules C1–C5 and the sense rulings.

The `EXTERNAL_CONNECTIVE` label records Hyland's internal/external distinction for transitions (2005, pp. 50–51). Results are precision against this adapted, operational scheme.

**Batches and returned labels.**

- **Batches:** model labellers work in batches of up to 325 items, each in a fresh session with the full guidelines and inventory. The session has no inherited repository or review context. It is pointed at a directory holding only the guidelines, the inventory and its batch file. They must judge every item individually, with no scripts, keyword rules or other programmatic shortcuts.
- **How the sessions are launched** (`docs/validation/study4-pilot040/LAUNCH.md`, `scripts/validation/study4_precision/pilot040/launch.py`). Each session is started with its provider's command-line tool, in a new neutrally named directory outside any git repository, with a cleared environment.
  - **The settings:** no MCP servers, memory or user or project instruction files. Role A's tools are only Read, Write and Edit. Role B's network access is off. The adjudicator's web tools are denied.
  - **The evidence:** context probes, a dry run and a per-session screen (`check_sessions.py`, with a positive control) check the archived effective context for the declared markers. Missing or unreadable context is a technical failure. The screen is supplemented by transcript review of file access and code-like calls; absence of marker hits alone is not proof that no prohibited context or access occurred. Labels are collected only from clean sessions, or from flagged sessions covered by a recorded human ruling bound to the session record and its exact flags. A context-marker hit or a technical failure can't be accepted by a ruling; it stops acceptance pending technical recovery or a relaunch, and no label is generated or chosen (`LAUNCH.md`, "Screen statuses and acceptance").
  - **The archive:** each session's own provider record, its effective context, is archived with its hashes. The final 0.4.0 pilot used these settings, and the evaluation uses the same ones.
  - **CLI versions:** the pilot ran Claude Code 2.1.304 and Codex 0.163.0, as recorded in its session archive (OpenCode records no version; v2.1.1 was installed at the freeze). These are pinned in the freeze manifest. The command-line tools update themselves, so the evaluation records the version each session ran. Any difference from the pilot versions is reported, and the evaluation's probes and dry run are repeated under the versions actually used before labelling starts.
- **Earlier sessions inherited context (disclosed).** The 0.3.2 pilot and the fix-check sessions were started as delegated tasks of a coding-agent thread whose project is this repository.
  - **Labeller A** received a git-status snapshot (branch, untracked paths, recent commit subjects) and the maintainer's personal instruction file.
  - **Labeller B and the adjudicator** ran with the repository as their working directory, so its path appeared in their environment.

  The retained records disclose no item-level baseline/candidate or family assignments and no other labeller's responses; A nevertheless received the branch and commit information described above. That is why the 0.4.0 pilot reused no earlier label (`LAUNCH.md`, finding F1).
- **Validation:** returned records are checked by the frozen validator: required keys, allowed labels, alternatives, note length, the form of an UNSURE note, and the duplicate rule.
- **Retries:** missing or invalid records are requested once more, in a fresh session, using an archived retry manifest. Anything still missing or invalid after that is a non-vote.
- **No selective retries:** no valid definite label is ever retried because of disagreement. Original and retry files are kept and merged deterministically.

**Prompt given to each model labeller, per batch:**

> You are labelling items for a research study on the precision of an English text analyser. Read the guidelines in full, and the sense inventory, then label every item in the batch file, one JSON line per item, exactly as the guidelines specify. Judge each item yourself, one at a time, from its context and the guidelines. Do not write or run code, regular expressions or keyword rules to produce labels, and do not consult any other file, website or source. Write the labels to the output path given. Don't summarise the items. When you finish, report only the number of items labelled and the count of each label.
>
> Files. Read ONLY these three files; do not open, list or search any other file or directory on this machine:
> - Guidelines: ⟨dir⟩/guidelines.md
> - Sense inventory, part of the guidelines (see B6): ⟨dir⟩/phrase_sense_inventory.md
> - Batch file, ⟨n⟩ items: ⟨dir⟩/items.jsonl
> - Output path: ⟨dir⟩/labels.jsonl
>
> You may write the output file with a file-writing tool, as long as you composed every label yourself. You may write it in several appends if that helps.

Each session's transcript is kept and checked: the session must read only the listed files and write the labels by hand. A check of the output's format (ids, keys, note length) is allowed. Generating labels by program is not.

The adjudicator receives the same prompt, the same blind item records and neutral file names. It is not explicitly told that the items are disputed, and it never sees A's or B's labels or reasons. Software can't prove that a model doesn't infer from the items' difficulty that they were selected. The candidates in the pilot work under the same restrictions.

**The maintainer:**

- **Labelling page:** the maintainer labels on a self-contained offline page built by `human_page.py`. It shows one item at a time with the guidelines alongside, applies the validator's rules on save, and shows no model label, source or analysis result.
- **Second pass:** before any unblinding, the maintainer makes a second blind pass over their own **validated** first-pass UNSURE items, seeing their first-pass note.
  - Definite first-pass labels can't be revised.
  - Missing or invalid first-pass records don't qualify for the second pass.
  - A valid second-pass label replaces the UNSURE. A second UNSURE stays unresolved. A missing or invalid second-pass label leaves the original UNSURE in place.
- **Invalid first-pass records:** the first pass gets the same single retry as the model labellers. Its retry manifest is the raw export's own retry list, written by `analyse.py --maintainer RAW --validate-only --retry-manifest DIR`. After that:
  - **Archived:** the original and retry exports, the retry manifest and the validation log.
  - **Non-votes:** records that are still invalid or missing become non-votes. They are not relabelled again by hand.
  - **The validated first-pass file:** `analyse.py --validate-pass1 RAW [--pass1-retry RETRY --manifest DIR/retry_maintainer.jsonl] --validated-out VALIDATED --validation-log LOG` builds it deterministically.
    - It merges the retry export with `merge_retry`. The manifest must equal the raw export's own retry list, so a selective retry is refused.
    - It keeps only the records the validator accepts, one per id, sorted by id, in a fixed serialisation.
    - The JSON log records:
      - the rejected lines and the non-vote ids, with their reasons;
      - the collapsed duplicates and the merge notes;
      - the second-pass ids;
      - the SHA-256 of every input (raw export, retry export, manifest, key, items, maintainer sample) and of the output;
      - the SHA-256 of `analyse.py`.
    - The file and the log are archived.
  - **One file throughout:** that same file assigns the second pass (`human_page.py --second-pass VALIDATED`) and is passed as `--maintainer` in the final analysis. Its hash is the pass-1 hash stamped on every second-pass record.
  - **What leaving a record out means:** it is a recorded validation step, not a correction of a label.
  - **How the retry is delivered:** the maintainer receives the archived retry ids, revisits only those ids on the original blind page, and exports a separate retry file. The merge keeps the original records outside the retry manifest and takes retry records only for manifest ids, so a full-page retry export is permitted; changes to ids outside the manifest are ignored. The retry is not the second pass, and definite labels in the archived original are never altered. The page, the inventory, the retry assignment and both exports are archived.
- **The sense inventory:** `human_page.py` embeds the guidelines but not the separate sense inventory. The maintainer receives the frozen inventory file and reads it alongside the page in both passes.
- **What the software enforces:**
  - **The page:** `human_page.py --second-pass` refuses any file that isn't in validated form, including an ordinary page export that is not already in that canonical form, and names the validation command. Canonical form alone doesn't prove provenance, so the raw-to-validated log is always archived.
  - **The analysis:** registered mode is the default. In it, `analyse.py` requires `--maintainer` in validated form whenever it writes second-pass ids, reads a second pass or produces results. Every accepted second-pass record must carry a `pass1_sha256` equal to the SHA-256 of `--maintainer`.
  - **The stamps:** every stamp present, including one on a rejected record, must be a 64-character lowercase hexadecimal string matching the first-pass file. In registered mode every accepted second-pass record must have that stamp. Malformed or mismatched stamps fail in every mode; missing stamps on accepted records fail in registered mode.
  - **The legacy flag:** `--nonregistered-legacy` accepts unvalidated or unstamped files, for synthetic and legacy inputs only. The report then marks those maintainer results NON-REGISTERED, and the registered analysis doesn't use it.
- **Before unblinding:** both exports and their hashes are archived. Only then is the maintainer shown any model or adjudicator label, source or key information, or concordance result.
- **What software can't check:** it can't verify that the maintainer stayed blind. Blinding is an operational commitment, reported as such.

## Outcomes

| Outcome | Module | 1 when the label is | Status |
|---|---|---|---|
| STRICT | both | `CORRECT` | **primary** |
| LENIENT | metadiscourse | `CORRECT`, `WRONG_CATEGORY` | secondary |
| CONNECTIVE | metadiscourse, claimed `transitions` only | `CORRECT`, `WRONG_CATEGORY`, `EXTERNAL_CONNECTIVE` | secondary |
| LIST_LENIENT | PHRASE | `CORRECT`, `WRONG_SENSE_LISTED` | secondary |
| PHRASAL | PHRASE | `CORRECT`, `WRONG_SENSE_LISTED`, `WRONG_SENSE_UNLISTED` | secondary |

Every other definite label is 0. `UNSURE`, missing and invalid labels are non-votes.

## Model reference

For each item and outcome:

1. If A and B both give a definite value and the values are equal, that value is the reference. Agreement on the outcome is enough, even if the detailed labels differ.
2. Otherwise, the adjudicator's definite value is the reference.
3. Otherwise, the item is **unresolved** for that outcome.

Adjudication is requested for every item where either primary is missing, invalid or UNSURE, or where A and B split on any outcome that applies to the item.

The maintainer never resolves a model-reference item. There is no maintainer fallback, no hybrid headline estimate, no adequacy gate and no choice of reference that depends on the data.

## Analysis

All estimates are computed by the frozen `analyse.py` and `estimators.py`.

**Estimands.**

- **Confirmatory:** STRICT precision for each module overall, for each of the ten metadiscourse categories, and for each PHRASE band K1–K5. Each has pointwise uncertainty.
- **Secondary or exploratory:**
  - the other outcomes;
  - the Hyland dimensions;
  - registers;
  - PHRASE single- vs multi-sense entries;
  - precision with each primary labeller alone as the reference;
  - batch diagnostics;
  - agreement statistics.
- **All predefined domains are reported,** including empty ones.
- **No familywise claim:** no familywise or simultaneous 95% statement is made across domains, modules or analysis methods.

### Primary: resolution-adjusted estimates with exact pointwise limits

**Point estimate.**

- **Weights:** for each outcome, let r_h be the number of phase-one items in sub-stratum h with a resolved reference. Each resolved item gets weight N_h/r_h.
- **Domain precision:** the weighted ratio Σ I_d·w·y / Σ I_d·w, using the module-level resolved weights with no domain recalibration.
- **Reported with each estimate:**
  - item and resolved counts;
  - the resolution rate;
  - the share of the population represented;
  - counts of reference sources and detailed labels;
  - warnings.
- **When part of a domain is unrepresented:** if a sub-stratum cell of a domain has hits in the population but no resolved item, no full-domain point estimate is given. The ratio over the represented cells is reported separately, labelled "represented cells only". Nothing is imputed.

**Assumption.** The limits assume that, given the resolved counts, the resolved items in each cell are a uniform random subset of that cell. They also assume this holds independently across sub-strata: whether an item gets resolved is exchangeable with whether it is correct. Equal resolution rates alone don't establish this, and the assumption can't be tested from the resolved labels. The co-primary region below drops it. Resolved labels are treated as fixed reference values: error in them is outside these limits.

**Limits.** These are exact, pointwise, finite-population 95% limits obtained from a joint stratified tail bound, with .025 in each tail.

- **Censuses** contribute known counts.
- **Unknown cells:** a cell with no resolved item contributes its whole population as unknown.
- **One uncertain cell:** inverted exactly from the hypergeometric distribution.
- **Two or more uncertain cells:** a joint Chernoff tail bound. The unknown cell totals are handled by a Lagrangian (weak-duality) upper envelope, so any evaluated grid point gives a valid bound.
  - **When the exact MGF is used:** the exact hypergeometric moment-generating function, for cells with M ≤ 2,500 and a/M ≥ .05.
  - **Otherwise:** the binomial MGF, which bounds the hypergeometric one for sampling without replacement (Hoeffding 1963, §6).
  - **Effect of approximations:** relaxing the integer totals and optimising on a finite grid can only widen the limits.
- **How the method is chosen:** only by population sizes and resolved counts, never by the observed outcomes. The grid, tolerances and code are frozen.
- **What "exact" means:** tail control that doesn't rely on large-sample approximations, given the sampling design, a correct frame, the assumption above and accurate numerical evaluation. It doesn't mean coverage equals 95%, that the labels are right, or that limits hold jointly across results.

### Co-primary: resolution region, allowing any pattern of unresolved items

Every primary estimate is reported with a co-primary pointwise 95% resolution region for the same precision. The region uses all sampled domain items:

1. For the lower completion, an item is 1 only if it is resolved correct.
2. For the upper completion, an item is 0 only if it is resolved incorrect.
3. The region runs from the exact lower limit of the lower completion to the exact upper limit of the upper completion, each one-sided at .025, under the original sampling design.

Cells without sampled items stay wholly unknown.

**What it assumes:** nothing about which items get resolved. It still requires a correct frame, the stated sampling design and correct definite labels.

**What it doesn't do:** it doesn't correct errors in resolved labels.

The primary interval and the region are always both shown; neither is chosen according to the results. Each is a pointwise 95% statement on its own; joint coverage of the two is not claimed. The weighted all-unresolved-wrong and all-unresolved-right sample endpoints are also reported, as descriptive sensitivity figures. They are not confidence bounds.

### Secondary: Korn–Graubard intervals

The modified Wilson interval of Korn and Graubard (1998), as in SAS PROC SURVEYFREQ, is reported as an approximation.

- **Variance:** Taylor-linearised for the ratio, with finite-population corrections.
- **Degrees of freedom:** for each module and outcome, the total number of resolved sampled items minus the number of sub-strata containing any. n_d is the number of resolved items in the reported domain.
- **Effective sample size:** P̂(1−P̂)/V̂ × (t_{n_d−1,.975}/t_{df,.975})², capped at n_d.
- **When it is shown:** only for 0 < P̂ < 1, V̂ > 0, n_d ≥ 2 and df ≥ 1. Singletons are warned about, and the represented-cell scope is stated where it applies. A fully resolved census of the population is reported as a point interval.

It supports no confirmatory claim and never replaces the primary interval or the region. In development simulations it undercovered (see "Evidence for the analysis").

### Secondary: maintainer-only precision

Precision is also estimated from the maintainer's final audit labels alone. The two-phase audit is, marginally, a simple random sample of m_h from N_h, so the same estimator, limits and region apply. They use the audit's own resolved counts, and the limits make the same exchangeability assumption.

PHRASE's audit is a census of phase one, so its analysis reduces to the phase-one design. Category and band results from the maintainer are exploratory. Maintainer-only results never replace the model-reference results.

### Concordance with the maintainer (descriptive)

Concordance compares the model-only STRICT reference R with the maintainer's final STRICT value H, separately for each module. **It is descriptive only.** There is no equivalence test, acceptance margin, pass/fail rule or fallback.

**Reported for each module:**

- item comparability and design-weighted comparability, using audit weights N_h/m_h;
- the paired label counts and the comparable 2×2 table;
- the direction of each disagreement;
- unweighted agreement with a Wilson interval and Cohen's kappa, both labelled as unweighted diagnostics;
- the second-pass counts: first-pass UNSURE, resolved in pass 2, UNSURE again, missing or invalid.

**D̂:** the comparable-item difference, using weights N_h/c_h, where c_h is the number of comparable audit items in h. It is restricted to comparable items and is not a full-population estimate.

**Interval for D = P_R − P_H:** a conservative pointwise 95% interval by worst-case completion. Each audit item contributes a range for its difference:

| Item | Contribution |
|---|---|
| R and H both definite | R − H |
| only R definite | [R−1, R] |
| only H definite | [−H, 1−H] |
| neither definite | [−1, 1] |

With d_lo and d_hi the lower and upper completions:

```
L = LCL Pr(d_lo = +1) − UCL Pr(d_lo = −1)
U = UCL Pr(d_hi = +1) − LCL Pr(d_hi = −1)
```

- **Components:** each is an exact one-sided stratified finite-population limit at .0125, using N_h and m_h. By the union bound, each end of the interval errs with probability at most .025.
- **Unknown mass:** unknown values and unaudited sub-strata stay unknown. No comparability threshold discards them.
- **Assumptions:** none about why values are missing. It does treat definite labels as fixed, so it doesn't protect against errors the model reference and the maintainer share.

**Expected precision.** With 300 items per module, the round-3 development simulations gave a mean interval width of about .20 after the second pass (about .24–.25 without it). In adverse settings it was about .34–.37. These are historical figures, and so are those of the 0.3.2-calibrated run of 2026-10-16/17: .146–.162 after the second pass, .201–.208 without it, and .334–.365 (.380–.414 without the second pass) in the adverse-concordance setting. The final 0.4.0-calibrated run gives .139–.162 after the second pass and .192–.208 without it in the main scenario, and .341–.354 (.387–.403 without the second pass) in the adverse-concordance setting. The interval can rule out large differences only. **No equivalence, adequacy, interchangeability, gold-standard or certification claim is made from concordance.** Its results can prompt further work or matcher revision. They don't change this study's analysis.

### Agreement and errors

- **Agreement:** for every available pair of labellers:
  - **Label agreement:** unweighted agreement and Cohen's kappa on the label strings, over items with valid records from both. UNSURE counts as a label here. The alternative category or sense is not part of this comparison.
  - **STRICT agreement:** agreement and kappa over pairs where both give a definite STRICT value.
  - **Denominators:** each one is reported, and kappa is reported as undefined where it is.
  - **The adjudicator:** comparisons involving it cover only the items sent for adjudication.
  - **What agreement shows:** no agreement figure certifies correctness or reliability in the population.
- **Where flags go wrong:** the categories and senses labellers move hits to.
- **Batch diagnostics:** for each primary labeller, its STRICT precision and its agreement with the other primary, grouped by its frozen batches. These are exploratory. They don't test for trends by position within a batch. Batch-domain populations are estimated, so any batch limits are heuristic, not exact design-based confidence statements.

## Evidence for the analysis

These checks were done before registration, on development data.

**Small-population enumeration.** It uses whole-number `math.comb` probabilities, independent of the implementation's own distribution code. It checks the exact limits and the concordance interval on small populations: censuses, unaudited cells, singletons, precision of 0 or 1, and extreme weights. Every tail error is at most .025. This supports the general argument in the code's documentation but doesn't replace it.

**End-to-end simulation.** It runs the real module-level STRICT path (reference assembly, both maintainer passes, estimation and concordance through `analyse()`) on synthetic labels, on the development design (1,000 metadiscourse and 300 PHRASE phase-one items, 300 audit items per module).

- **Coverage:** finite populations from several seeds, with:
  - boundaries;
  - unequal weights;
  - mixtures of censuses and unobserved cells;
  - the MGF thresholds;
  - fixed and outcome-dependent non-resolution;
  - adverse discordance;
  - high and low precision.
- **Not covered:** it doesn't test the labelling-file workflow, semantic judgement, the category, band and register tables, the secondary outcomes or the maintainer-only analysis.
- **Monte Carlo error:** tail-error rates are reported with Clopper–Pearson intervals, which are individual, not simultaneous. Module outputs from the same replicate are paired and aren't pooled as independent.

**The main scenario is calibrated to the final 0.4.0 common development pilot** (`main-pilot` in `simulate_coverage.py`, constants `PILOT` and `pilot_resolution`; `docs/validation/study4-pilot040/RESULTS.md`). Its model reference is the agreed A/B STRICT value, else the adjudicator's. Precision is the pilot's design-weighted estimate, because the simulation sets the share of correct hits in the whole population; the unweighted sample shares were 693/999 = .694 and 230/300 = .767. The resolution rates are unweighted, because they apply to each sampled item. The simulation uses the 0.4.0 pilot's key and frame (`.cache/validation/study4_v040/`).

| Parameter | Metadiscourse | PHRASE | Where it comes from |
|---|---|---|---|
| Population STRICT precision | .554 | .870 | 0.4.0 pilot design-weighted precision (.55375, .87002), rounded to three places. Each unit's probability is shifted by one common amount, so the population hits it exactly (to 1/N) for every seed. |
| Items whose STRICT reference needs the adjudicator | 55/1,000 = .055 | 12/300 = .040 | 0.4.0 pilot |
| Items left unresolved | 1/1,000 = .001 | (12/300) × (1/84) ≈ .00048 | 0.4.0 pilot. PHRASE had 0 of 12, too few to estimate, so its adjudication share is multiplied by the pooled adjudicator UNSURE rate, 1/84 (the retained `pilot_resolution` rule). |
| Non-resolution mechanism | random | random | Assumption. Outcome-dependent and fixed mechanisms are in the grid. |
| Spread of precision across sub-strata | U(.45, .97) plus register effects (general +.04, argumentative −.10), before the shift | same | Assumption, as in round 3 |
| Maintainer disagreement with the reference (each direction) | .02 | .02 | Assumption. No pilot has maintainer labels. |
| Maintainer pass-1 UNSURE (agreeing / disagreeing items); share resolved in pass 2 | .05 / .05; .70 | same | Assumption. No pilot has maintainer labels. |

**History.** The 0.3.2 pilot's parameters were .491 and .836 (precision), 63/1,000 and 8/300 (adjudicator needed), and 2/1,000 and (8/300) × (2/86) (unresolved). They calibrated the historical 2026-10-16/17 run below.

- **Pilot figures not used as parameters:**
  - **A–B STRICT agreement** (.961 and .960; it was .954 and .973 in the 0.3.2 pilot): the simulation doesn't separate A/B splits from a primary UNSURE. The STRICT reference treats both the same way: the adjudicator decides.
  - **Secondary-only requests:** of the 84 adjudication requests (6.5% of 1,300 items), 17 were sent only because A and B split on a secondary outcome (67 STRICT-relevant: 55 + 12). Their agreed STRICT reference is unchanged, so this STRICT-only simulation omits those requests.
- **Pilot rates reproduced:** in a check through the real reference code (population seed 101), simulated replicates reproduced these rates.
  - **Metadiscourse** (150 replicates, 150,000 items): .0551 needed the adjudicator, against .055, and .00093 stayed unresolved, against .001.
  - **PHRASE** (400 replicates, 120,000 items): .0409 needed the adjudicator, against .040, and .00036 stayed unresolved, against .00048. That is 43 events where about 57 were expected, a Monte Carlo difference of about two standard errors in a very rare event.

  The check's script and output are in the simulation archive (`sim040/ratecheck/`).
- **The grid.** The final run retains all 13 scenarios from the historical 0.3.2-calibrated grid: the boundaries, non-resolution mechanisms, weights, thresholds, discordance and adverse concordance, `main-realistic` and `low-precision-050`. The low-precision-050 scenario retains population precision .50 and is recalibrated to the final pilot's resolution rates. The other twelve scenarios retain their numerical settings and seed scheme. Every dev/mixed scenario uses the new 0.4.0 frame, so equal seeds do not imply identical realised finite populations or replicate samples. The main-realistic scenario has the earlier main scenario's settings: 3% unresolved and 10% of resolved items adjudicated (12.7% adjudicator-needed in expectation). In this final four-cell grid its realised population precision is .661–.748.

**Reproducibility and completeness.**

- **Before the run:** a declared inventory of required cells is frozen (`--write-inventory`). Each cell is a scenario, module and population seed with its replicate range, its seed and its effective parameters.
- **What every result file records:**
  - the source, key and frame hashes;
  - the scenario settings per module and the pilot figures;
  - the environment, the command and the parsed arguments, as structured data;
  - random streams that don't depend on the number of workers;
  - its status (`running` or `complete`), checkpoint time and completion time.
- **When a file is complete:** only when every required cell is present with exactly its replicate range and count, and the end-of-run source check passed.
- **Resuming:** a resumed run must make the same request. A cell saved with a different replicate count is refused, never skipped.
- **Merging:** the merge accepts only complete parts with matching frozen settings, run by the same code. Cells must be unique, and their union must equal the declared inventory.
- **In the freeze manifest:** the final merged file's hash and the inventory's hash.

**The registered evidence** is the final run of the frozen code on the 0.4.0-calibrated scenarios: `main-pilot` with 23,410 replicates × 3 population seeds × 2 modules, and the grid of 13 scenarios with 2,000 replicates × 2 seeds × 2 modules. That is 58 cells and 244,460 replicates, merged against the declared inventory (`sim040/inventory.json`, frozen with every source hash before the run started).

- **Run:** started 2026-10-20 17:02 UTC. The first invocation stopped when the maintainer's session ended, with 4 of 58 cells saved. The same request was resumed with `--resume` at 21:22 UTC after the code, key, frame and inventory hashes were checked, and it completed at 22:24 UTC with status `complete`. The merge against the declared inventory succeeded: 58 cells, exactly the inventory. Summary: `sim040/SUMMARY.md`.
- **Hashes:** merged file `final.json` `0e93658f030ed0788d8ef13de3b65bc2d278665150ed0d2190f19808dd6871fe`; inventory `f17f920f8b69d459c9ce67fcf268e5a8c41e96ad89f63ff33c55c7d2e56fb80e`; run file `all.json` `c3a90db164ab051dc0fb33a920453859bd9753e182324c9c8680dbdf1a3f4ad4` (`sim040/result_hashes.sha256`), also in the stage-1 freeze manifest.

| Interval | Largest tail error in the main scenario | Clopper–Pearson 95% upper bound | Mean width |
|---|---|---|---|
| Primary | 66/23,410 = .0028 | .0036 | .149–.162 |
| Resolution region | 61/23,410 = .0026 | .0033 | .149–.163 |
| Concordance | 0/23,410 in every cell and tail | .00016 | .139–.162 after pass 2 |
| Korn–Graubard (secondary) | 903/23,410 = .039 | n/a | n/a |

- **In the final grid:**
  - **Resolution region:** the observed tail-error rate was at most .005 in every tested cell and tail (the maximum, 10/2,000, in `low-precision-050`), and at most .0015 under outcome-dependent non-resolution.
  - **Concordance:** 0 in every cell and tail.
  - **Primary:** at most .005 in every cell except those where non-resolution depends on the outcome, the case its assumption excludes. There, the lower-tail error reached .1515 (`outcome-unresolved`) and .140 (`fixed-outcome-unresolved`).
  - **Korn–Graubard:** undercovered in most cells. It reached .094–.102 at the precision boundaries, .47–.57 under outcome-dependent non-resolution, and .549 in `mixed-census-unobserved`, where it is a represented-cells interval scored against full-population precision.
  - **Why the outcome-dependent figures differ from the 0.3.2 run:** the outcome-dependent scenarios retain their settings and seed scheme, but their synthetic populations are regenerated on the 0.4.0 frame. For outcome-unresolved, MD population precision changes from .797–.832 to .661–.676; the corresponding MD lower-tail errors change from .0045–.0095 to .0900–.1515. More incorrect hits are exposed to the higher non-resolution probability, alongside changes in cell composition and weighting. The old scenario-wide maximum .0535 came from PHRASE. These are synthetic assumption-stress results, not measured version effects. The resolution region remains within .0015 in every outcome-dependent cell and tail.
  - Individual Monte Carlo intervals are reported in `sim040/final.md` and `tail_table.txt`.

**Historical, not registered evidence: the 0.3.2-calibrated run** (2026-10-16/17). It ran the same 58 cells and 244,460 replicates with the 0.3.2 pilot's key, frame and parameters, merged against its declared inventory. Its hashes are in `sim_final/result_hashes.sha256`. It is kept unchanged as evidence for the 0.3.2 design, not relabelled as a 0.4.0 validation. Main-scenario results:

| Interval | Largest tail error in the main scenario | Clopper–Pearson 95% upper bound | Mean width |
|---|---|---|---|
| Primary | 78/23,410 = .0033 | .0042 | .161–.170 |
| Resolution region | 69/23,410 = .0029 | .0037 | .162–.170 |
| Concordance | 0/23,410 in every cell and tail | .00016 | .146–.162 after pass 2 |
| Korn–Graubard (secondary) | 828/23,410 = .035 | n/a | n/a |

- **In its grid:**
  - **Resolution region and concordance:** the observed tail-error rate was at most .003 in every tested cell and tail, including the outcome-dependent, fixed, boundary, extreme-weight, threshold and adverse cells. Individual Monte Carlo intervals are reported.
  - **Primary:** at most .0045 in every cell except those where non-resolution depends on the outcome, the case its assumption excludes. There, the lower-tail error reached .054 (`outcome-unresolved`) and .134 (`fixed-outcome-unresolved`).
  - **Korn–Graubard:** undercovered in most cells. It reached .185 at boundary-low precision, .51–.67 under outcome-dependent non-resolution, and .98 in `mixed-census-unobserved`. In that last scenario it is a represented-cells interval scored against full-population precision, so the figure reflects scope as well as approximation.

**Historical, not registered evidence: the round-3 development run.** Its main scenario is now the grid's `main-realistic`: population precision about .72–.83 on the historical development frame, rather than the pilot-calibrated population targets, with 23,410 replicates × 3 population seeds × 2 modules:

| Interval | Largest tail error in the main scenario | Clopper–Pearson 95% upper bound | Mean width |
|---|---|---|---|
| Primary | 59/23,410 | .0032 | .145–.209 |
| Resolution region | 25/23,410 | .0016 | .173–.235 |
| Concordance | 0/23,410 in every cell and tail | .00016 | .196–.204 after pass 2 |
| Korn–Graubard (secondary) | 1,401/23,410 = .060 | n/a | n/a |

- **In the round-3 wider grid:**
  - The Korn–Graubard upper-tail error reached .19 at low precision.
  - When non-resolution depended on the outcome, the primary lower-tail error reached .14. This is the case its assumption excludes.
  - For the resolution region and the concordance interval, the observed tail-error rates were below .025 in every tested cell. Individual Monte Carlo intervals are reported.
- **The round-4 run:** its completed six-cell main-scenario run used the same earlier scenario (the superseded grid was stopped before saving output), and its sources are archived. It is also historical.
- **What zero failures mean:** zero observed failures don't establish a zero error rate. For each cell and tail we report a confidence interval for the Monte Carlo error rate. Its upper end is a confidence bound with the stated coverage, not a guaranteed bound on the true error rate.

## What is published

Regardless of what the results show:

- **Results:** `docs/validation/study4-precision.md` and `.json`, with this plan and its freeze manifest.
- **Labels:** every label from A, B, the adjudicator and the maintainer's two passes, keyed by item id, with each item's span offsets and its text's URL and revision.
- **Item text:**
  - **Contexts:** they come from CC BY, CC0, CC BY-SA and public-domain sources. They are released under CC BY-SA 4.0 with each source's licence notice, its exact revision and attribution, and a notice of modification (excerpting).
  - **PHRASE List content:** the glosses and examples in `claimed`, and the sense inventory, are not part of that release. They are published only if the list's authors agree. Until then, PHRASE items are published as ids, offsets and expression names.
- **Changes to lexinspect:** precision per category and per band goes into VALIDITY.md and the CHANGELOG, and the app shows it next to the counts it describes.
- **Problems:** every deviation and every failed check is reported.
- **Fix-process disclosure.** Publish the original and final development pilot summaries, the 0.3.2→0.3.3→0.4.0 bridge, the dated protocol/iteration ledger, all candidate-family dispositions, every check round and its exposure/exclusion manifest, all sampling probabilities and decisions, unresolved labels, per-family and combined losses, additions/reassignments, and complete output-count changes (`docs/validation/study4-development-effects.md`). Link the final source and release identities and any construct amendments. Label all of this as development evidence. Report the evaluation regardless of its precision; do not select the published version or headline after seeing evaluation outcomes.
- **Private material.** The guidelines, the PHRASE sense inventory and the private text bodies of the fix-check rounds are kept out of the public repository; their hashes are published. Whether the guidelines and inventory are published with stage 1 depends on the PHRASE List authors' permission, which is pending; the PHRASE content of items is likewise published only with that permission. Until then their hashes are published. The archive inventory, licences, label provenance and access tiers are in `docs/validation/study4-archive.md`. A public text-free export with a recompute script (`docs/validation/study4-textfree/`) reproduces both pilots' quantities, both fix-check rounds' gates and the sensitivity analysis from public files; the full packages are available for supervised inspection (access log: `docs/validation/study4-access-log.md`).

## After the study

- **Fixing:** errors found in evaluation can be used to fix the matcher. The fixed version is not re-scored on these items, because that would measure fit to the test set.
- **Re-measuring:** a fixed version is measured on a new sample. That sample uses new texts from the same sources, excluding the development and evaluation texts. It uses the same frozen procedure, or a new registered version of it.

## Limitations, stated in advance

- **No learner writing.** lexinspect's main users analyse student and learner texts. These results don't show how precise it is on them.
- **The reference is operational.** It comes from two language models and an adjudicator. They may share systematic errors: independent prompting doesn't make their judgements independent evidence of truth.
- **The maintainer isn't independent.** The concordance check uses the maintainer, who built lexinspect and steered the guidelines. Blinding reduces exposure bias but not that dependence. An independent trained annotator is future work.
- **Concordance is imprecise.** With 300 items per module, the concordance interval is about ±.10, so small differences between the model reference and the maintainer can't be ruled out.
- **The primary limits rely on an assumption.** They assume resolution is exchangeable with correctness, which the data can't test. The co-primary region doesn't need it but is wider.
- **The results are conditional.** They are conditional on the evaluation texts. Text-selection uncertainty is not in the intervals.
- **Subgroup results are sparse.** Category, band and register limits are wide, and register estimates are exploratory.
- **The framework is adapted.** Precision is measured against an operational adaptation of Hyland's model and the PHRASE List, with documented Study 4 conventions. Other operationalisations could give different results.
- **Recall and output coverage.** We sample detector outputs, not all construct occurrences in text. Neither Study 4 nor the development fix-check estimates recall, establishes non-inferior recall, or validates count completeness. The fix-check quantifies loss among baseline-detected occurrences on its fixed texts against the operational reference; it cannot find occurrences missed by both versions. Better precision therefore does not establish a more complete detector, valid absolute construct-frequency measurement, or comparable category/sense counts across versions.
- **The fix process used development data repeatedly.** The matcher was revised on the development texts and two fix-check rounds, with one precautionary reversion decided after seeing a result. Development and fix-check figures are not evidence of improvement, and they are not reported as such.
- **Earlier labelling sessions inherited context.** The 0.3.2 pilot and fix-check sessions are disclosed under "Labellers". The final pilot and the evaluation use the clean launch settings.
- **No independent human reference.** The planned human work is concordance with the maintainer, not independent expert validation. The reference is the models' operational judgement.

## References

- Clopper, C. J., & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika*, 26(4), 404–413.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46.
- Hoeffding, W. (1963). Probability inequalities for sums of bounded random variables. *Journal of the American Statistical Association*, 58(301), 13–30.
- Hyland, K. (2005). *Metadiscourse: Exploring interaction in writing*. Continuum.
- Korn, E. L., & Graubard, B. I. (1998). Confidence intervals for proportions with small expected number of positive counts estimated from survey data. *Survey Methodology*, 24(2), 193–201.
- Martinez, R., & Schmitt, N. (2012). A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212.
