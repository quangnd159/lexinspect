# Study 4: matcher fix protocol for lexinspect 0.4.0 (development only)

**Status:** v3 (final for fix work), 2026-10-17. Reviewed by GPT-6.1-Sol in rounds r1–r3; r3 verdict READY TO COMMIT.

**History:**
- v1 (`FIX_PROTOCOL_v1.md`, sha256 `90d6d08b…`) was written before any fix was designed. When it was written, the known development evidence was the 0.3.2 pilot labels and the error breakdown in `dev_error_table.jsonl`.
- v2 (`FIX_PROTOCOL_v2.md`, sha256 `96aab609…`) adopts GPT-6.1-Sol's protocol review r1 (`sol_protocol_review_r1.md`).
- v3 adopts review r2 (`sol_protocol_review_r2.md`).

v2 and v3 were written while an error taxonomy was being prepared (`TAXONOMY_REPORT.md`, development labels only). They come before any fix is implemented, any fix-check text is collected and any check label exists.

Each revision is kept with its hash. The protocol is committed and pushed to the public repository, so it has an independent timestamp, before fix-check texts are collected. Later amendments state which outputs or labels were already known when they were written. No local timestamp alone proves prospective specification.

This protocol and its checks are development records. Stage 1 is not complete until the following are archived together, with an external receipt:
- the final detector;
- the pilot;
- the simulation;
- the exclusions;
- the procedure.

## Why this protocol exists

The pre-registration says: "Errors found in development are fixed before the protocol freeze. The version tested is the fixed version." That carries two risks:
- **Overfitting.** Fixing a detector against the labels that revealed its errors can overfit.
- **Gaming.** A precision study can be gamed by deletion: fewer, safer hits raise precision while the tool stops finding genuine markers.

The rules below guard against both. The study measures the frozen final version's precision. It does not test a hypothesis that 0.4.0 improves on 0.3.2 or 0.3.3, and development before/after differences cannot establish that comparison.

## Inputs and baseline

- **Development set:**
  - **Contents:** 120 pinned texts and 1,300 labelled hits, built with lexinspect 0.3.2.
  - **References:** outcome-specific references come from the original validated A, B and adjudicator records, each assembled separately by the registered rule, in `dev_error_table.jsonl` (field `refs`). The fields are:
    - metadiscourse: STRICT and LENIENT for all claims; CONNECTIVE only for claimed transitions. On other claims an absent CONNECTIVE key means not applicable, not unresolved or incorrect;
    - PHRASE: STRICT, LIST_LENIENT and PHRASAL.
- **Evaluation texts:** none exists. None may be collected, viewed or used until the stage-1 freeze.
- **Baseline code:** lexinspect 0.3.3 at the full commit for `dec79bc`, in its pinned environment.
  - Preserve the original 0.3.2 build.
  - Measure, on the same archived development text bytes:
    - the 0.3.2→0.3.3 bridge;
    - the 0.3.3→0.4.0 change;
    - the cumulative 0.3.2→0.4.0 effect.
  - Never identify unchanged judgements by sampled item ID or token index alone.

## What a lost detection means

We distinguish two things:
- whether the emitted category or sense is correct;
- whether an occurrence in the target inventory is detected at all.

A removed WRONG_CATEGORY or WRONG_SENSE_LISTED item is not harmless merely because its STRICT value is zero. Reassigning an occurrence to a supported category or listed sense is different from deleting it.

- A baseline **STRICT success is harmed** when the final output no longer contains a corresponding STRICT-correct claim.
- A baseline **LENIENT or LIST_LENIENT success is lost** when the final output contains no corresponding occurrence in that inventory.
- PHRASE PHRASAL and transition CONNECTIVE are also reported, as diagnostics.

These quantities are separate, and all are evaluated against the same frozen operational construct. An uncertain correspondence or unresolved reference is handled conservatively in the acceptance bounds. It is never counted as a successful removal.

Where the linguistic rule supports it, prefer correcting a wrong category or listed sense to deleting the occurrence. This is not permission to choose the alternative category from check labels.

## What may change

1. **Matching defects.** These are tokenisation, rule-logic and data-list errors, where the matcher does not do what its own documented rules say.
2. **Rule gaps.** A context check is missing that implements one of these:
   - a published definition: Hyland 2005; Hyland & Tse 2004; the PHRASE List entry and its sense inventory;
   - an existing Study 4 convention;
   - a grammatical fact (Biber et al. 1999; Huddleston & Pullum 2002).

   A grammar citation supports only the grammatical facts it establishes, not an untested semantic classification. New conventions are construct amendments; see below.
3. **Parser choice.**
   - **Before trying alternatives:** record the candidate packages, exact versions, rationale and deployment criteria. Keep every candidate tried and its development results.
   - **For the final pipeline,** record:
     - its components and exclusions;
     - its tokenizer and sentence-boundary customisations;
     - its model and package hashes;
     - the lock file and environment.
   - **Gates:** a pipeline replacement is its own fix family. It is subject to complete-output diffing, label-payload identity checks and the combined held-out gates.
   - **Deployment:** check it in the actual shipped configuration. Document bundle size, latency, failures and affected modules.
   - **Study 2:** it stays historical evidence for its named versions and configurations, and for its fixed-token tagging and lemmatisation design. If the shipped shared pipeline changes, rerun the relevant Study 2 comparisons and impact checks, or explicitly limit those claims to the old configuration.
   - **Other studies:** Study 2 does not validate dependency parsing or sentence boundaries. Document how any shared preprocessing change affects the other earlier studies.
4. **Meaning distinctions.** These are:
   - internal versus external connectives;
   - inclusive versus exclusive *we*;
   - epistemic versus deontic modals.

   Heuristics are allowed only as stated general rules that pass the held-out gates. Otherwise the limitation is documented, not patched.

## What may not change

- **No blocklists.** No blocklist of development sentences, texts or titles, and no fixed-expression exception accumulated from development error strings. Every fixed-expression exception is listed exhaustively, with an independent justification and its general scope.
- **No construct changes by the back door.** No marker, sense or category is removed because its development precision is low. A change to the target construct is a separately identified draft amendment. It comes with its justification, revised guidelines or inventory where needed, a relabelled common pilot and a new check under that construct. Its results are not presented as a repair validated against the unchanged construct.
- **No tuned thresholds.** No thresholds or weights are tuned to maximise development precision.
- **No disguised changes.** No change to the guidelines, the sense inventory, the prompts or the estimands is made under cover of a "matcher fix". The prereg's "What development may change" rules apply.
- **No exceptions after results.** No construct exception is granted after results are seen. Every rejected, narrowed or overridden proposal is disclosed, and an override cannot be called a passed check.

## Each fix records

- **Identity and rule:** its id, family and rule.
- **Justification:** the published definition or existing Study 4 convention it implements, with page, entry or section, and an explanation linking it to the actual code condition.
- **Tests:** grammatical minimal pairs, positive and negative, plus counterexamples that should keep genuine uses. These cover ambiguity, negation, quotation and plausible register variation where relevant.
  - Tests are an executable specification, not evidence of population accuracy.
  - Constructed sentences are preferred. Any fixture taken from development or check texts is labelled with its provenance and never presented as held-out validation.
- **Development collateral.** This is reported for every family and for the complete candidate:
  - baseline hits removed;
  - STRICT successes harmed;
  - LENIENT and LIST_LENIENT successes lost.

  Sample counts and design estimates are reported only where the sampling design supports the stated population.
  - **Original sampling probabilities** apply only to units selected from the original 0.3.2 frame, and only with valid label transfer or newly obtained labels for the required paired judgements.
  - **Hits that don't inherit them:** hits added in the 0.3.2→0.3.3 bridge and new 0.4.0 outputs. They are accounted for by a separately identified census or probability sample, or reported as sample-only counts without a population estimate.
  - **Combined estimators:** any estimator that combines the old sampled component with a bridge census or another sampled component names those populations and their inclusion probabilities.
  - **Changed success denominator:** if the baseline-success denominator changes, the appropriate full baseline frame is reconstructed and the estimator stated. The old weights are not silently reused.

  Each loss is shown both as a share of the affected baseline hits and as a share of all baseline successes for that outcome and module. Development figures are screening diagnostics, because these labels informed the fixes. They are not held-out evidence.

## Diff and label transfer

The diff specification is archived before fix-check labelling and cannot be revised using check labels.

- **Matching key.** It matches on:
  - source identity and the archived normalised text hash;
  - module and character span;
  - the emitted claim: category, or PHRASE entry, rank and sense.
- **Change types.** It records removed, added, reassigned, span-changed, duplicate and display-context-changed outputs separately.
- **Crosswalk.** A deterministic occurrence crosswalk separates a genuine deletion from a replacement at the same occurrence. An unresolved crosswalk counts conservatively as a possible loss.
- **Label reuse.** Each judgement payload includes the entire displayed context, the marker and the claimed object, including the other listed senses. An old label is reused only when this whole payload and the applicable guideline, inventory and prompt versions are identical. The old-to-new ID map and payload hashes are archived. Otherwise A and B label the new item and the registered reference procedure applies.
- **The ledger.** The family definitions and their dependency and order map are frozen in the candidate ledger before check collection.
- **Frames.** Full baseline and candidate hit frames are kept, not just labelled hits.
- **Measurement.** Each family is measured against the baseline with its declared prerequisites, and the complete candidate is measured against the baseline. Overlapping effects are counted once in cumulative totals.
- **Combination.** The combined candidate must pass even if every family passed alone. Removing a family after seeing its check is a candidate revision, governed by the re-check rule.

## Held-out check (fix-check sets)

### Collection and scope

- **Size and quotas.** Round 1 collects exactly 60 new texts, 20 per register. The academic quotas are 7 sciences, 7 social sciences and 6 humanities.
- **Collection rules.** The same applies as for the development set: source pools, eligibility, extraction and truncation rules.
- **Fixed before collection.** These are archived first:
  - the seed;
  - the collection command;
  - the pool and cache snapshot policy;
  - the exclusion inputs: the canonical development manifest and every earlier check manifest.
- **Shortfalls and failures** are kept and reported. No text, seed or build is chosen from its detector outputs or labels.
- **Scope of inference.** All inference is conditional on the archived texts. Inadequate evidence makes a check inconclusive. It never triggers a label-driven expansion.

### Candidate and frames

The candidate commit, environment, family ledger and diff algorithm are frozen before its check texts are collected. Baseline and candidate run on identical text bytes. Before labels are requested, we build the full decision frames for each module:
- removed baseline hits;
- new outputs;
- changed-claim pairs;
- baseline hits, for the cumulative-loss denominator.

Each frame is identified by family where applicable and by output-change type, and the complete-candidate frames are built as well. Before labelling we also archive:
- all frame sizes and overlaps;
- seeds and selected IDs;
- inclusion probabilities.

**Exhaustive affected-baseline frame.**
- **What it holds.** For each family configuration and for the complete candidate, this frame contains every baseline hit whose emitted claim, span, multiplicity, judgement payload or occurrence correspondence changes. That covers display-context-only changes, span-only changes and duplicate changes, as well as deletions and reassignments.
- **Counting.** Each baseline emitted hit is one counting unit and appears once in the combined affected frame.
- **Change types.** Before collection, a deterministic, mutually exclusive partition into change types is frozen, with its precedence rule. Building the frame uses no labels.
- **Hits outside it.** A hit outside the frame must have an archived identical-payload, unchanged-correspondence match that establishes zero loss. Otherwise it enters the frame conservatively.

**Counterparts.** Each affected row records its baseline payload and every linked final counterpart.
- A deletion has no corresponding final counterpart.
- A replacement is not counted as a deletion merely because its claim key changed.
- The genuine-deletion subset feeds the removal gate.
- For each selected baseline row, we obtain the baseline reference, plus references for every counterpart needed to decide retention. This is subject to valid payload reuse and blind, separate assignments.
- All sampling memberships are preserved.
- These linked counterpart judgements are not a simple random sample of final outputs for precision estimation. The separate final-output sampling frames remain for that purpose.

**Definite and possible losses.** For each gated outcome:
- A definite loss needs a definitely successful baseline hit and no corresponding final success under that outcome.
  - For STRICT, success means a supported, correct emitted claim.
  - For LENIENT or LIST_LENIENT, it means a supported occurrence in the same target inventory.
- A definitely incorrect baseline hit can't contribute loss.
- A definitely successful corresponding final output establishes retention only when the correspondence is resolved.
- For every other case where the baseline, the counterpart or the correspondence is unresolved, we compute the lowest and highest loss consistent with the available references and the crosswalk. Acceptance uses the highest.
- Neither a merely overlapping output nor a replacement with an unresolved reference counts as proof of retention.
- Each baseline hit counts once, even if several final outputs correspond to it. Each combined effect counts once, whatever families it belongs to.
- Final additions don't offset baseline losses.

### Allocation

- **Changed-hit frames.** Draw a simple random sample without replacement of min(200, N) from each frame, and from each non-empty change-type cell of the affected-baseline frame. Frames with N ≤ 200 are censused, and zero frames are reported.
- **Baseline-success denominator.** Draw a separate sample using the registered category/band and marker-substratum allocation, targeting 1,000 metadiscourse and 300 PHRASE hits, capped at availability. Record the actual N_h and n_h.
- **Shared payloads.** An identical payload is labelled once and keeps its membership in every relevant frame.
- **Seeds.** Frames use independent seeds.
- **No changes after labels.** No item is replaced and no sample enlarged after labels are seen.
- **Before labelling,** we archive the attainable decision bounds for each actual frame and the design's power at specified loss rates.

### Blind labelling

- **A and B.** They label in fresh, independent sessions, under the frozen Study 4 instructions and the retry and validation rules. They receive only the ordinary judgement payloads. They get none of the following:
  - the version, the diff direction or the family;
  - the proposed fix or an expected label;
  - any paired old/new output;
  - the development error table;
  - the other labeller's answers.
- **Changed claims** are labelled as separate ordinary items, in separate assignments, without exposing that they are paired.
- **Flash** receives only the blinded assignment that the registered `needs_adjudication` rule prescribes. That includes all non-votes and all disagreements across the applicable outcomes.
- **Reference.** The registered outcome-wise agreement-or-adjudicator reference is used.
- **Retained records:** raw responses, assignments, retries, validation and rejection logs, and effective settings.

### Estimation, uncertainty and unresolved labels

**Frozen acceptance calculation.** One construction is used for every acceptance decision.
- **When it is frozen.** Its implementation, tests, source hashes and component identities are archived before the first check labels. The frame and crosswalk algorithm is frozen before collection.
- **No switching.** No alternative interval or estimator is chosen from observed outcomes.
- **Combined estimates** use the separately sampled complete-candidate frames. Overlapping family estimates are never summed.

Let a = .05/J. The three bounds are:

1. **Removal upper bound.** This is computed for each family and module genuine-deletion frame, and for the complete-candidate and module genuine-deletion frame.
   - Let N be the frame size and n its assigned SRS size.
   - Let k_hi be the number of sampled baseline items that are definitely or possibly successful on LENIENT or LIST_LENIENT.
   - The bound is `hyper_ucl(k_hi, n, N, a) / N`, using the archived `estimators.py`.
   - An unresolved sampled reference stays in n and counts towards k_hi.
2. **Loss-total upper bound, U_loss.** This is computed for each complete-candidate, module and outcome loss total, over the mutually exclusive cells of the affected-baseline frame.
   - For cell h, record `(N_h, n_h, k_lo_h, k_hi_h)`, where k_lo and k_hi are the lowest and highest sampled loss counts.
   - Get the joint one-sided upper proportion from `estimators.exact_limits(cells, alpha_lo=None, alpha_hi=a)`, and multiply it by the total affected-frame size.
   - Unaffected baseline hits contribute exactly zero. An empty affected frame has U_loss = 0.
   - Never substitute a resolution-adjusted sample of resolved items for n_h.
3. **Baseline-success lower bound, L_success.** This is computed for each complete-candidate, module and outcome baseline-success total, using the separately selected stratified baseline sample.
   - Supply its full assigned n_h. k_lo is the definite successes; k_hi is the definite successes plus the unresolved references.
   - Get the joint lower proportion from `estimators.exact_limits(cells, alpha_lo=a, alpha_hi=None)`, and multiply it by the full baseline-frame size.

**Implementation details.** `estimators.exact_limits` returns a dictionary.
- **Non-empty affected population:** read `loss_limits["upper"]` from the upper-only call. Then U_loss = sum(N_h over affected cells) × `loss_limits["upper"]`.
- **Non-empty baseline population:** read `success_limits["lower"]` from the lower-only call. Then L_success = sum(N_h over baseline cells) × `success_limits["lower"]`.
- **Unsampled cells:** keep positive-size unsampled cells in the calculation.
- **No positive-size affected cells:** set U_loss = 0, without multiplying a None result.
- **Empty baseline population:** its success total is zero and its loss fraction undefined. Its required cumulative gate is then not assessable, which makes the candidate inconclusive.
- **N = 0:** skip the removal ratio and record that gate as not applicable.
- **Endpoints:** read only the requested endpoint. The census and unobserved-only branch may fill both endpoints even when the other tail argument is None.

**The cumulative loss fraction** is `min(1, U_loss / L_success)` when L_success > 0. Shared labels and dependence between the numerator and denominator estimates don't justify reducing J. Simultaneous coverage across components is used without assuming those bounds are independent.

**Descriptive intervals.** Precision of additions and changed claims is not gated. It is reported with separately identified pointwise 95% intervals, using worst-case resolution and the same finite-population sampling principles. Those intervals sit outside the simultaneous acceptance family. They can't be used to choose a passing candidate or to change the loss gates.

**Reporting and unresolved labels.**
- **Reporting:** every outcome and frame shows definite-correct, definite-incorrect and unresolved counts.
- **Acceptance uses worst-case completion:**
  - unresolved affected items count as potentially harmful in loss bounds;
  - unresolved new outputs count as potentially incorrect in precision bounds;
  - unresolved baseline items can't establish successes;
  - non-votes are never dropped.

### Error budget

Before the first check labels, the ledger fixes an upper bound J on the number of one-sided component bounds that the acceptance decisions need. It covers both modules, all families, the complete candidate, all gated outcomes and both permitted rounds. The ledger enumerates them, including any stratum-level components.

A total error budget of .05 is allocated equally, at .05/J each. Unused allocation is not recycled. A round-2 candidate may narrow or revert the original families but may not introduce new ones.

**Reserved components.** With F original families, reserve the following for each of two rounds and each of two modules:
- F family-removal upper bounds;
- one complete-candidate removal upper bound;
- two complete-candidate loss-total upper bounds, one for STRICT and one for the module's inventory outcome;
- two baseline-success lower bounds.

So J = 4(F + 5). Identities are reserved even for an inactive family, an empty frame, a census or an unused round. A joint stratified total uses one component, not one per stratum. Round 2 reuses the same family identities.

**Changing the construction.** Any extra acceptance criterion, or a different component construction, needs an amended ledger and a reviewed prospective budget before any check labels.

**What the coverage covers.** The simultaneous coverage is conditional on the archived text frames and the operational reference procedure. It does not cover shared semantic mistakes, model-reference error, text selection or transfer to other texts.

### Acceptance gates (per module)

1. **Removal gate.** For each family and for the combined candidate, the upper bound on the proportion of removed hits that were LENIENT or LIST_LENIENT successes is at most .15.
2. **Cumulative-loss gate.** For the combined candidate, the upper bound on the loss of baseline successes is at most .05 of baseline successes. This is checked separately for STRICT harm and for LENIENT or LIST_LENIENT loss.

The .15 and .05 figures are engineering tolerances chosen before any check, not established acceptable losses.

**Empty frames.**
- **Empty deletion frame:** its removal proportion is undefined. It is recorded as not applicable, meaning there was no opportunity for removal.
  - It doesn't stop an otherwise eligible candidate from passing the other applicable gates.
  - It is no evidence of how the family behaves elsewhere.
- **Empty affected-baseline frame:** its loss total is zero.
- **Zero baseline-success lower bound:** the cumulative gate is inconclusive.
  - If a fully labelled census shows zero baseline successes, the fraction is reported as undefined, not zero, and that module's cumulative gate is not assessable.
  - A candidate with a required cumulative gate that can't be assessed is inconclusive.

**Decision statuses.**
- **Pass:** a candidate passes only when every applicable removal gate and every required cumulative gate meets its upper-bound tolerance under the frozen calculation.
- **Fail:** recorded only when a deterministic lower bound establishes a breach, in either of two ways. These use only losses that are logically unavoidable in the population, need no extra confidence allocation, and are sufficient but not necessary criteria.
  - The distinct sampled definitely successful deletions, divided by all deletions, exceed .15.
  - The distinct sampled definite baseline losses, divided by the full baseline hit count, exceed .05.
- **Inconclusive:** the candidate doesn't pass and no breach is established, or a required procedure is incomplete.

Neither fail nor inconclusive allows keeping the checked candidate. An upper bound above the margin is not, on its own, proof that the true loss exceeds it.

**Additions and changed claims.** These get no separate acceptance gate. For each family, each module and the complete candidate, we report design-based precision on STRICT and on the broader outcomes, using the same uncertainty and unresolved-label accounting. Changed claims are reported as paired old/new outcomes, covering both repaired errors and newly harmed successes. The decision is therefore called "passed the loss safeguards", not "all fixes validated". The precision study remains responsible for estimating precision.

### Decision and re-check

- **One judgement.** The first candidate is judged once.
- **Exposure.** Once its outcomes are seen, every text in that round counts as development-exposed.
- **At most one revision.** At most one revised combined candidate is allowed. It is frozen before a second, disjoint 60-text set is collected, under the same rules. That set has a separate seed and excludes the development set and every earlier check text.
- **The second round** has its own prospectively allocated error budget and rechecks all active changes and their combination.
- **No pooling.** No first-round outcome is pooled as confirmation.
- **On a second failure or inconclusive result,** we don't select a subset of families, revert selected families, or otherwise change the second candidate and describe the result as having passed. There are two options:
  - **Keep the baseline:** retain the entire unchanged 0.3.3 baseline at the pinned commit and environment, abandoning all candidate fixes. That reversion is the fallback. It is not a passed fix-check or a 0.4.0 validation result.
  - **Amend:** stop, and issue a dated, independently reviewed protocol amendment before any further candidate check.

  Any other combination, including one made of individually passing families, needs its own prospectively authorised complete-candidate check and final pilot before stage 1.

### What these figures are called

We report:
- the reference-positive fraction of removed hits;
- the fraction of baseline reference-positive detections lost;
- the precision of new outputs;
- reassignments.

These are removal and baseline-retention diagnostics. They are **not recall estimates.**

We also report complete output counts and hits per 1,000 words, by module, category or band, and register, before and after, on the development and check texts. These describe output density, not linguistic recall.

## After the candidate passes

1. **Rebuild and resample the development pilot.** Rebuild the full 0.4.0 hit population on the original 120 development text bytes.
   - Draw a newly identified common development pilot under the registered sampling algorithm, with its seed and manifest archived before labelling. The targets are 1,000 metadiscourse and 300 PHRASE hits.
   - Recompute the frame, strata, N_h, n_h and weights.
   - Reuse labels only under the payload-identity rule. Every other selected item gets validated A/B labels and adjudication.
   - Do not build the pilot from convenient old survivors plus added hits.
2. **Recompute the final common pilot.** Report, by module, with actual numerators and denominators:
   - STRICT precision, unweighted and resolution-adjusted design-weighted (N_h/r_h);
   - unresolved mass;
   - primary disagreements;
   - STRICT adjudicator-needed counts;
   - all-outcome adjudication requests;
   - adjudicator non-votes;
   - final non-resolution, outcome by outcome.

   **Recalibration.** Recalibrate every pilot-dependent simulation parameter from its declared count or estimate on the current pilot. Parameters with no pilot evidence keep explicit assumption labels.

   **The existing `pilot_resolution` rule is kept,** applied to the current counts:
   - Use the observed per-item non-resolution when it is nonzero.
   - Otherwise, use the module's STRICT adjudication share times the pooled adjudicator UNSURE rate among all adjudication requests.
   - If the module has zero STRICT adjudication requests, its non-resolution parameter is zero. It is labelled explicitly as a modelling assumption, because only zero events support it. No 0/0 ratio is evaluated.

   **If a quantity is undefined.** If any required calibration quantity remains undefined, including a missing full-domain weighted precision target, stop. Resolve it in a dated, independently reviewed amendment before the simulation. Do not choose among smoothing rules, and do not substitute changed-hit check rates for the common-pilot rates.

   **What these numbers are.** They are fitted development calibration inputs, not unbiased evidence of improvement. The final pilot is not another chance to tune the candidate.

   **Later changes.**
   - Any later substantive change to the detector or the reference rule needs its own newly authorised fresh-text complete-candidate check and a final common pilot under that version.
   - If the two-round allowance is used up, amend the protocol and have it independently reviewed before any further checking.
   - Packaging-only changes are documented separately, and must preserve the checked behaviour and judgement rules.
3. **Simulation.** Keep the 2026-10-16/17 run unchanged, as historical evidence for the 0.3.2 design. For 0.4.0:
   - First freeze the new key and frame, the calibration constants, the sources, the environment and the declared cell inventory.
   - Rerun the full 58-cell inventory: main-pilot at 23,410 replicates × 3 seeds × 2 modules, plus the 13-scenario grid at 2,000 replicates × 2 seeds × 2 modules.
   - Use the existing completeness, resume and merge checks.
   - Update every prereg claim the run affects.
4. **Adjudicator.** Flash's qualification (193/200) concerns the original calibration set. It is not a guarantee for the changed hit mixture.
   - Flash stays the adjudicator unless a reviewed amendment is needed. It is never replaced to improve development precision.
   - On the final pilot, report its completeness, unresolved responses and agreement diagnostics by module and by change status.
   - A semantic change to the reference instructions invokes the prereg's selection amendment rules.
5. **Prereg updates.** Apply the exact text changes listed in `sol_protocol_review_r1.md` BLOCKING 7 and SHOULD-FIX 3 and 5:
   - exclusions;
   - the "Matcher fixes" disclosure;
   - the version line;
   - the historical pilot rates, kept alongside the 0.4.0 rates;
   - the adjudicator caveat;
   - limitations on recall and output coverage;
   - fix-process disclosure.

   The evaluation build passes the frozen union of all fix-check manifests through `--exclude-texts`. Exposed sources are excluded under every identifier.
6. **Release.** Update the CHANGELOG and docs, and tag 0.4.0. No GitHub release until Zenodo is enabled. The released code must have exactly the checked behaviour, and any packaging-only changes are documented.
7. **Review.** GPT-6.1-Sol reviews:
   - this protocol, before check labels;
   - the final diff, the development and check effects, the candidate dispositions, the new pilot and the simulation package, before stage 1.

   Sol's review sessions are separate from labelling but share model B's identity. That dual role and the number of reviews are disclosed. Review doesn't replace a trained independent semantic reference.

## Log

- 2026-10-17 v1 drafted (sha256 90d6d08b…).
- 2026-10-17 v2: all BLOCKING, SHOULD-FIX and MINOR findings of Sol protocol review r1 adopted. An outcome-specific reference field was added to `dev_error_table.jsonl` (metadiscourse LENIENT 690/998 definite-correct; PHRASE LIST_LENIENT 202/300). Known at the time: the 0.3.2 development labels, plus the taxonomy then in progress. No fix code, check text or check label existed.
- 2026-10-17 v3: Sol review r2 (verdict REVISE). All three BLOCKING findings were adopted in substance, with editorial restructuring:
  - no subset fallback;
  - the exhaustive affected-baseline frame and loss accounting;
  - the frozen acceptance calculation, with J = 4(F+5).

  All three SHOULD-FIX and the MINOR were adopted too:
  - empty frames and decision statuses;
  - the final-pilot calibration and post-check rules;
  - the limits of the original weights;
  - CONNECTIVE applicability.

  Sol r2 also independently reproduced `dev_error_table.jsonl`, matching byte for byte (sha256 299204a7…). Known at the time: the 0.3.2 development labels; the 0.3.2→0.3.3 bridge (`rerun_diff.json`: all 1,300 sampled claims matched; 2 MD and 2 PHRASE hits added); the taxonomy then in progress. No fix code, check text or check label existed.
- 2026-10-17 v3 (final): Sol review r3 verdict **READY TO COMMIT**. No BLOCKING or SHOULD-FIX findings. Its two optional MINOR clarifications were adopted: explicit `exact_limits` endpoint handling, and the log wording above. Nothing new was known since v3: no fix code, check text or check label.
