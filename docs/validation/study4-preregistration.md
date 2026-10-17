# Study 4 pre-registration: precision of metadiscourse and PHRASE detection

**Status: DRAFT, not registered.** This plan is registered in two archived stages (see "Registration and freeze"), both before any evaluation item is labelled. A local Git timestamp alone is not the registration date: each stage is deposited in a timestamped, externally retained record that names the Git commit and the hashes. Stage-1 placeholders identify the actual final development, model, code and simulation artefacts. Stage-2 placeholders identify the single evaluation build. Development values are never substituted for evaluation counts or results. Any deviation from this plan is reported with the results, giving its timing, its reason and its consequences.

## Question

When lexinspect flags a span as a metadiscourse marker in one of Hyland's (2005) ten categories, or as an expression from the PHRASE List (Martinez & Schmitt 2012), how often is the flag right? This is **precision**.

The study doesn't measure:

- recall (what lexinspect misses);
- whether the reference labels are themselves correct;
- how precise lexinspect is on kinds of text outside the evaluation population, including learner writing (see "Limitations").

## What is tested

- **Version and modules:** lexinspect ⟨freeze: version and commit⟩ with spaCy `en_core_web_sm` 3.8.0, modules `metadiscourse` and `phrase`, as shipped. The freeze manifest records the SHA-256 of the detector source and data, and of the lock file.
- **Scope:** results describe this version only. Any later change to matching needs a new measurement (see "After the study").

## Development and evaluation

The study keeps calibration and testing apart.

- **Development set** (seed 20261016, built 2026-10-16 with lexinspect 0.3.2): the pinned 120 texts, 40 per register, and a stratified sample of 1,300 hits. It is used only to develop the guidelines, the sense inventory, the matcher fixes, the labelling workflow and the analysis, and for the pilot below. No development label or result is reported as evidence of precision. The maintainer's practice labelling page uses development items and is training, never evaluation data.
- **Evaluation set:** fresh texts from the same sources, drawn once, by the procedure in "Registration and freeze".
  - **Exclusion:** the build excludes every source of the development set. It does this through the pinned development manifest (`.cache/validation/study4/texts.jsonl`, SHA-256 `5dba40ccbb99a853ef32e6f3def90f992810ff2320cf98f366e227d7112f1cc8`, 120 distinct texts), matched on every identifier: PMCID, Europe PMC and full-text URLs, DOI, title, Wikipedia page id, page title and revision URL.
  - **Overlap check:** after collection, the build checks overlap again and records it. The registered overlap must be zero.

### What development may change

- **Allowed changes:** before the protocol freeze, development may change:
  - text-extraction and matching defects;
  - the guidelines and the sense inventory;
  - the prompts;
  - the validation and delivery workflow.
- **The log:** every iteration is logged with its date, reason, changed files and their hashes, the development items, labels and results inspected, and the resulting version. The actual number of iterations is disclosed.
- **Old builds and labels** are kept. The development text set stays the pinned 120 texts. A matcher change may produce a new development hit sample, identified as such.
- **No pooling across versions:** labels produced under different guideline, inventory or prompt versions are not pooled for the final pilot rates or for choosing the adjudicator. When an applicable rule changes, the final common pilot is relabelled.
- **When the pilot ends:** when the final workflow runs without an unresolved delivery or validation defect, and the final versions and adjudicator choice have been reviewed and archived.
- **What the pilot can't change:** it doesn't authorise silent changes to the estimands, outcome mappings, reference rule, audit targets, phase-one targets, allocation, interval methods, α or reporting family. Any such change needs an explicit revised draft, reviewed before the protocol freeze.
- **Evaluation data:** no evaluation label, item judgement or result is used in development or selection.
- **After the freeze:** a substantive change after the protocol freeze needs a dated amendment and a newly identified evaluation build. After labelling starts, any change is reported as a deviation.

### Pilot

The pilot runs on the development set only, before registration.

1. **Labelling:** A and B each label the same complete development sample under the final pilot guidelines and inventory. Both get the single missing/invalid-record retry. Records from dry runs or earlier iterations are kept but never mixed with the final pilot records.
2. **What it measures:** how often the labellers disagree, how often items need adjudication, how often they end up unresolved, how often each label is used, and STRICT precision against the model reference, both unweighted and design-weighted. The main simulation scenario behind "Evidence for the analysis" uses the rounded design-weighted precision (.491 metadiscourse, .836 PHRASE) as its population target, and the unweighted per-item adjudication and non-resolution rates. It is set before the final validation run.
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

### Matcher fixes

Errors found in development are fixed before the protocol freeze. The version tested is the fixed version. Development scores are used only for development and calibration, never reported as evaluation precision.

## Registration and freeze

**Stage 1: protocol freeze.** Before any evaluation text is collected, we archive:

- the detector;
- the guidelines and inventory;
- the prompts and role-specific system or developer instructions, and the tool and file access each role gets;
- the analysis and sampling code, and the simulation and its results;
- the selected adjudicator;
- the collection targets and eligibility rules;
- the exact evaluation seed;
- the exclusion manifest;
- the policy for snapshotting the cache and source pools;
- the build command.

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

- **Guidelines:** `docs/validation/study4-guidelines.md`, version 3.2 (or the later version, if the pilot leads to one).
- **The PHRASE sense inventory** (`phrase_sense_inventory.md`, version 2.1 or later). It is part of the guidelines but is kept out of the public repository until the PHRASE List's authors permit redistribution. Its hash is published, and the file is published once permission is granted.
- **The labeller prompts**, given below.
- **Analysis code:** every script in `scripts/validation/study4_precision/` (`build.py`, `frame.py`, `batches.py`, `analyse.py`, `estimators.py`, `human_page.py`, `simulate_coverage.py`, `test_analyse.py`).
- **Environment:** `uv.lock`, and the Python and dependency versions.
- **The validation simulation's manifest** (see "Evidence for the analysis"). It identifies exactly which code was validated.

Nothing in this list changes after registration. A change found necessary after registration is a deviation and is reported as one.

## Labellers

All labellers work blind and independently. In a labelling session each role receives only:

- its assigned items: id, module, context, marked span, and the claimed category or PHRASE entry with its other listed senses;
- the frozen guidelines and sense inventory;
- in the maintainer's second pass only, the maintainer's own first-pass UNSURE note.

No role is given another labeller's responses, source or key information, or analysis results.

| Role | Labeller | Items |
|---|---|---|
| Primary A | Claude Sonnet 5.5 (Anthropic) | all phase-one items |
| Primary B | GPT-6.1-Sol (OpenAI) | all phase-one items |
| Adjudicator | DeepSeek V4.1 Flash (`opencode/deepseek-v4.1-flash-free`, reasoning "high"), chosen in the pilot by the rule in "Choosing the adjudicator": completeness 284/284, calibration agreement 193/200 = .965 (metadiscourse 95/100, PHRASE 98/100), no calibration non-votes; two UNSURE responses among the 86 adjudication requests. The GPT-6-Sol fallback was not run under the rule. | every item needing adjudication (below) |
| Maintainer H | the maintainer (Quang Nguyen) | the frozen audit sample, targeted at 300 per module and capped at phase-one availability |

The exact model identifiers, settings and run metadata are recorded in the freeze manifest and with the labels.

**Independence and conflicts.**

- **Who built lexinspect:** the repository history credits Claude Opus 4.7, 4.8 and 5.5 as co-authors of lexinspect's code, including the metadiscourse and PHRASE matching. Claude Opus 5.5 also wrote these guidelines, the sense inventory, the sampling and the analysis code.
- **Who labels:** none of those models labels any item. Labeller A, Claude Sonnet 5.5, is from the same provider as the code's authors. It might therefore lean towards accepting their rules.
- **How that is balanced:** if a DeepSeek model is selected, adjudication uses a third provider. The GPT-6-Sol fallback shares OpenAI with primary B; if it is selected, this exception is disclosed with it.
  - **How the reference is built:** it takes agreed definite A–B outcome values, and otherwise the adjudicator's definite value. It isn't a vote on full labels.
  - **What separation can't do:** keeping providers and sessions separate doesn't make their errors independent or establish correctness.
  - **Primary-only results:** precision with each primary labeller alone as the reference shows some differences between references. It can't detect errors they share.
- **GPT-6.1-Sol has two roles.** It reviewed the guidelines and the analysis code, and then this plan, in separate sessions before registration: eleven sessions (one study-design review, three guideline reviews, four analysis-code reviews, two reviews of this plan with the code, and one final-results verification). Three earlier study-design reviews were by another OpenAI model, GPT-6-Astra, which has no labelling role. It is also labeller B. During those reviews it saw development items, never evaluation items. Each labelling batch runs in a fresh session with no memory of the reviews.
- **The maintainer** created lexinspect and steered the guidelines. The audit therefore measures concordance with the maintainer, not with an independent expert. An independent trained annotator is the main improvement left for future work.

**Adapted framework.** The guidelines operationalise Hyland's (2005) model for single flagged spans. Where Hyland gives no ruling, they adopt explicit Study 4 conventions, each marked as such in the guidelines:

- the precedence for *see* with another text;
- proposition-based tests for transitions;
- *this paper* as a self-mention;
- the PHRASE construction rules C1–C5 and the sense rulings.

The `EXTERNAL_CONNECTIVE` label records Hyland's internal/external distinction for transitions (2005, pp. 50–51). Results are precision against this adapted, operational scheme.

**Batches and returned labels.**

- **Batches:** model labellers work in batches of up to 325 items, each in a fresh session with the full guidelines and inventory. The session has no inherited repository or review context. It is pointed at a directory holding only the guidelines, the inventory and its batch file. They must judge every item individually, with no scripts, keyword rules or other programmatic shortcuts.
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

**Expected precision.** With 300 items per module, the round-3 development simulations gave a mean interval width of about .20 after the second pass (about .24–.25 without it). In adverse settings it was about .34–.37. These are historical figures. The final pilot-calibrated run gives .146–.162 after the second pass, .201–.208 without it, and .334–.365 (.380–.414 without the second pass) in the adverse-concordance setting. The interval can rule out large differences only. **No equivalence, adequacy, interchangeability, gold-standard or certification claim is made from concordance.** Its results can prompt further work or matcher revision. They don't change this study's analysis.

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

**The main scenario is calibrated to the development pilot** (`main-pilot` in `simulate_coverage.py`, constants `PILOT` and `pilot_resolution`). Its model reference is the agreed A/B STRICT value, else the adjudicator's. Precision is the pilot's design-weighted estimate, because the simulation sets the share of correct hits in the whole population; the unweighted sample shares were .622 and .670. The resolution rates are unweighted, because they apply to each sampled item.

| Parameter | Metadiscourse | PHRASE | Where it comes from |
|---|---|---|---|
| Population STRICT precision | .491 | .836 | Pilot design-weighted precision. Each unit's probability is shifted by one common amount, so the population hits it exactly (to 1/N) for every seed. |
| Items whose STRICT reference needs the adjudicator | 63/1,000 = .063 | 8/300 = .027 | Pilot |
| Items left unresolved | 2/1,000 = .002 | (8/300) × (2/86) ≈ .0006 | Pilot. PHRASE had 0 of 8, too few to estimate, so its adjudication share is multiplied by the pooled adjudicator UNSURE rate, 2/86. |
| Non-resolution mechanism | random | random | Assumption. Outcome-dependent and fixed mechanisms are in the grid. |
| Spread of precision across sub-strata | U(.45, .97) plus register effects (general +.04, argumentative −.10), before the shift | same | Assumption, as in round 3 |
| Maintainer disagreement with the reference (each direction) | .02 | .02 | Assumption. The pilot has no maintainer labels. |
| Maintainer pass-1 UNSURE (agreeing / disagreeing items); share resolved in pass 2 | .05 / .05; .70 | same | Assumption. The pilot has no maintainer labels. |

- **Pilot figures not used as parameters:**
  - **A–B STRICT agreement** (.954 and .973): the simulation doesn't separate A/B splits from a primary UNSURE. The STRICT reference treats both the same way: the adjudicator decides.
  - **Secondary-only requests:** of 86 adjudication requests (6.6% of 1,300 items), 15 were secondary-only (1.15% of items; 17.4% of requests). Their agreed STRICT reference is unchanged, so this STRICT-only simulation omits those requests.
- **Pilot rates reproduced:** in a check through the real reference code, simulated replicates reproduced these rates (metadiscourse .063 adjudicated and .002 unresolved; PHRASE .026 and .0007).
- **The grid** keeps every earlier scenario unchanged, with identical random streams: the boundaries, non-resolution mechanisms, weights, thresholds, discordance and adverse concordance. It adds two:
  - `main-realistic`: the round-3/4 main scenario, with population precision about .72–.83, 3% unresolved, and 10% of the other items resolved by the adjudicator (about 13% sent to it). It now provides the high-precision cells.
  - `low-precision-050`: precision .50, with the pilot's resolution rates.

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

**The registered evidence** is the final run of the frozen code on the pilot-calibrated scenarios: `main-pilot` with 23,410 replicates × 3 population seeds × 2 modules, and the grid of 13 scenarios with 2,000 replicates × 2 seeds × 2 modules. That is 58 cells and 244,460 replicates, run 2026-10-16/17 and merged against the declared inventory. The merged-file and inventory hashes are in `sim_final/result_hashes.sha256` and will be included in the stage-1 freeze manifest. Main-scenario results:

| Interval | Largest tail error in the main scenario | Clopper–Pearson 95% upper bound | Mean width |
|---|---|---|---|
| Primary | 78/23,410 = .0033 | .0042 | .161–.170 |
| Resolution region | 69/23,410 = .0029 | .0037 | .162–.170 |
| Concordance | 0/23,410 in every cell and tail | .00016 | .146–.162 after pass 2 |
| Korn–Graubard (secondary) | 828/23,410 = .035 | n/a | n/a |

- **In the final grid:**
  - **Resolution region and concordance:** the observed tail-error rate was at most .003 in every tested cell and tail, including the outcome-dependent, fixed, boundary, extreme-weight, threshold and adverse cells. Individual Monte Carlo intervals are reported.
  - **Primary:** at most .0045 in every cell except those where non-resolution depends on the outcome, the case its assumption excludes. There, the lower-tail error reached .054 (`outcome-unresolved`) and .134 (`fixed-outcome-unresolved`).
  - **Korn–Graubard:** undercovered in most cells. It reached .185 at boundary-low precision, .51–.67 under outcome-dependent non-resolution, and .98 in `mixed-census-unobserved`. In that last scenario it is a represented-cells interval scored against full-population precision, so the figure reflects scope as well as approximation.

**Historical, not registered evidence: the round-3 development run.** Its main scenario is now the grid's `main-realistic`: population precision about .72–.83, rather than the pilot-calibrated population targets .491 and .836, with 23,410 replicates × 3 population seeds × 2 modules:

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

## References

- Clopper, C. J., & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika*, 26(4), 404–413.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46.
- Hoeffding, W. (1963). Probability inequalities for sums of bounded random variables. *Journal of the American Statistical Association*, 58(301), 13–30.
- Hyland, K. (2005). *Metadiscourse: Exploring interaction in writing*. Continuum.
- Korn, E. L., & Graubard, B. I. (1998). Confidence intervals for proportions with small expected number of positive counts estimated from survey data. *Survey Methodology*, 24(2), 193–201.
- Martinez, R., & Schmitt, N. (2012). A phrasal expressions list. *Applied Linguistics*, 33(3), 299–320.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212.
