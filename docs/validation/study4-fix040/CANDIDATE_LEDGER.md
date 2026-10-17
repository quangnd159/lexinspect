# Study 4 fix work: candidate ledger, round 1 (lexinspect 0.4.0 candidate)

**Status:** FINAL (2026-10-17). Frozen with candidate commit `3d4df7012656defd5a44571410af00896f634a2d` (branch `study4-fix040-candidate`), the fix-check harness and the acceptance code, before any fix-check round-1 text is collected (FIX_PROTOCOL v3, committed as `docs/validation/study4-fix-protocol.md` at 646f7ca; clarifications in `docs/validation/study4-fix-protocol-clarifications.md`).

**Sources:**
- the fix proposals: `TAXONOMY_REPORT.md` §5;
- the rule statements: the simulated patches in `scripts/fixes.py`.

The implemented code must reproduce the simulated output for the selected rules on the 120 development texts, or document every difference.

**Known when this was written:**
- the 0.3.2 development labels;
- the taxonomy and its in-sample development effects.

Nothing existed yet for fix code in `src/`, fix-check texts or fix-check labels.

## Decisions

- **Parser:** keep `en_core_web_sm` 3.8.0 (TAXONOMY §6.5). Parser errors are about 1% of weighted error. md loses reference-CORRECT hits; lg and trf exceed the deployment budget. There is no parser family.
- **Included:** every proposed rule MD-01…MD-32 and PH-01…PH-13 except PH-03, PH-07 and PH-08, which were removed after the implementation audit (log, 2026-10-17 audit r1). Several included rules were narrowed then; the rule table below gives each family's current contents. Also one optional, construct-backed meaning heuristic, inside a family as listed below:
  - **SX-01:** exclusive *we*/*us* with a past-tense verb other than *be*/*have*, reassigned to self-mentions. *our* uses the 0.3.3 own-work noun class.
  - SX-03 (descriptive *important/essential … for/to* + NP) was included in round 1 and removed after the audit.
- **PH-02 scope:** it also includes the recall correction from TAXONOMY §8 row 20: accept rewording *that* tagged RB. Since the audit revision, it applies wherever PH-02's construction check accepts the occurrence (no punctuation requirement). Hits it adds are new outputs, reported under the protocol's additions rules.
- **Excluded:**
  - **SX-02,** procedure sequencing: rejected for 12/26 collateral in development.
  - **SX-05,** OUT OF sense contexts: deleting senses would be a construct change.
  - **Removing *as far as* from evidentials:** a construct change, so it needs an amendment. Not in 0.4.0; documented as a known limitation.
  - **Any trained disambiguation model.**
- **Documentation-only changes,** which don't change behaviour, ship with the release:
  - the docstrings say "propositions", not "clauses";
  - the hedging-verb clausal-complement claim is corrected;
  - SOURCES.md documents the self-mention adaptation (*this paper/study*).

## Families (F = 12, all module-specific)

| Family | Module | Rules | Prerequisites |
|---|---|---|---|
| MD-A clause linking and transitions | metadiscourse | MD-01, MD-02, MD-03, MD-05, MD-06, MD-25 | none |
| MD-B word-internal hyphens and brackets | metadiscourse | MD-04 | none |
| MD-C frame and endophoric markers | metadiscourse | MD-07, MD-08, MD-09, MD-10, MD-11, MD-12 (without the coordination branch), MD-30 | none |
| MD-D code glosses | metadiscourse | MD-13, MD-14, MD-15 (*known as* only), MD-21 | none |
| MD-E sources and evidentials | metadiscourse | MD-16 (own-text veto only), MD-17, MD-18, MD-19 | none |
| MD-F stance (hedges, boosters, attitude) | metadiscourse | MD-20, MD-22, MD-23, MD-24, MD-26, MD-27, MD-28 | none |
| MD-G reader/writer forms and directives | metadiscourse | MD-29, MD-31 | none |
| MD-H quotation (writer's voice) | metadiscourse | MD-32 | none |
| MD-I exclusive *we* | metadiscourse | SX-01 (past-tense *we*/*us* only) | none |
| PH-A USED TO and THAT IS | phrase | PH-01, PH-02 (with the recall correction) | none |
| PH-B entry-specific constructions | phrase | PH-04, PH-05, PH-06, PH-09, PH-11 (PUT IT, GET OFF), PH-12 | none |
| PH-C matching form | phrase | PH-10, PH-13 | none |

**Rules as revised after audits r1 and r2** (where the round-1 statement changed; the code is in `src/lexinspect/metadiscourse.py`, `phrase.py` and `_context.py`; r2 = `AUDIT_R2_DISPOSITIONS.md`):

| Rule | Family | Revised statement |
|---|---|---|
| own_text (used by MD-08/09, MD-16, MD-17/18) | MD-C, MD-E | A noun phrase is the present text or study only if its head (form or lemma) is in the 0.3.3 own-work class `_OWN_WORK_NOUNS` or among the head nouns of the 0.3.3 self-mentions naming the text (A2: adds *article*, *thesis*) with *this/these/present/current/our/my* as determiner or modifier or *here* as a direct dependent, or it is a text-part noun with a reference label. The descendant *here/above/below* shortcut is removed. r2 B1: never when the head has, as a direct dependent, a possessor other than *our/my* (*his/her/its/their/your*, or a noun or proper noun) or an authorial *by* whose object is a proper noun or a personal pronoun other than *me/us*. |
| MD-08 | MD-C | *the aim/goal/purpose* only if the goal noun is recognised by own_text, has *here* as a direct dependent, or has an *of*-object recognised by own_text. The relative-clause subtree shortcut and the pronoun objects *this/ours* are removed. |
| MD-09 | MD-C | Non-initial stage labels only after a goal-noun subject of *be* that passes the MD-08 test. |
| MD-11 | MD-C | The label is checked after the marker's last word (multiword *in section*, *see table* …). |
| MD-12 | MD-C | The two coordination returns are removed; the prepositional-object and numeric checks stay. |
| MD-13 / PH-02 | MD-D / PH-A | The punctuation requirement is replaced by two exclusions: relative *that* (WDT, or subject of a relative clause); a demonstrative subject that opens its clause (sentence start; after `;` `:`, an opening quotation mark or bracket, or a coordinator or subordinator (A1); r2 S1: after a straight single quote that is a token of its own, not `case`/POS, with whitespace or the text start before it and no space after it), is the subject of *is*, with a non-punctuation word straight after *is*. Everything else keeps the rephrasing reading. |
| MD-15 | MD-D | The *called* registration is removed; *known as* not after *become/come/grow* stays. |
| MD-16 | MD-E | The source-object whitelist is removed; only the veto for an object recognised by own_text stays. |
| MD-18 | MD-E | A3: a hedge or booster reporting verb moves to evidentials only with a named source subject: a proper noun, or (r2 B2) a noun of the 0.3.3 source-noun class `_SOURCE_NOUNS` (form, or lemma for a noun) with a proper-noun `poss`/`compound`/`nmod` dependent, not recognised by own_text. Other nouns, owned or not, keep their 0.3.3 category. |
| MD-22 | MD-F | An adverb set off by commas on both sides, or by a comma and the end of the sentence, keeps its stance reading; r2 S2: so does one whose phrase (the adverb with its `advmod` dependents) is enclosed by a paired `(`…`)` or paired dashes (`—`, `–`, or a hyphen with spaces on both sides). A single dash is not enough. The manner/degree suppression applies only outside those contexts. |
| MD-23 | MD-F | *make* (ADV) *sure* is rejected; with no subject the 0.3.3 check decides. |
| MD-24 | MD-F | Adverbs between *have* and the participle are skipped. |
| MD-27 | MD-F | Passive *expected* (an `auxpass` or `nsubjpass` dependent) with a to-infinitive `xcomp` or (r2 B3) a finite `ccomp` (a tensed or modal verb or auxiliary) is reassigned to hedges (guidelines A4); *as expected* stays attitude; attributive *expected* is no marker. r2 B3: everything else keeps the 0.3.3 check (a verb counts as attitude), passives with no clausal complement included. |
| MD-29 | MD-G | The extraposition exception needs *it* + *be* + an adjective complement; r2 S3: *important* or *essential* only, the `attitude_markers` of `metadiscourse.json` that express importance or necessity. |
| MD-31 | MD-G | All capitals is computed once per text, not per sentence. |
| MD-32 | MD-H | The quote state resets only at blank-line paragraph breaks; straight single quotes are not supported. r2 S4: a `’` token with dependency `case` or tag POS, attached to the word straight before it, doesn't close a curly single quotation. |
| PH-11 | PH-B | The UP TO verb check is removed; PUT IT and GET OFF stay. |
| PH-12 | PH-B | *only/just/not* are removed from the comparative set; numerals, *twice*, *half*, *times* stay. |
| SX-01 | MD-I | The research-noun class is rolled back; *our* uses `_OWN_WORK_NOUNS`. |
| PH-03, PH-07, PH-08, SX-03 | PH-B, MD-F | Removed; documented limitations. |

**Order.** Each family is measured alone against the 0.3.3 baseline. Its prerequisite is none: the 0.3.3 code plus that family. The complete candidate enables all twelve. Where two families can act on the same hit, the complete-candidate frame counts the effect once (protocol, "Diff and label transfer").

## Error budget

- **J:** 4(F + 5) = 4 × 17 = **68** one-sided components. This reserves, for each of 2 rounds × 2 modules: 12 family-removal upper bounds, 1 complete-candidate removal upper bound, 2 loss-total upper bounds (STRICT and LENIENT, or STRICT and LIST_LENIENT) and 2 baseline-success lower bounds.
- **Reservations.** Reserving family bounds under the module a family doesn't touch is deliberately conservative. Those identities are reserved and recorded as not applicable, never recycled.
- **Allocation:** a = .05/68 = **0.000735294…** per component.
- **Component identities:** `R{round}.{module}.{family|COMPLETE}.{removal|loss_STRICT|loss_INV|success_STRICT|success_INV}`, enumerated in `ledger_components.json` when the ledger is frozen.

## Implementation requirements

- **Toggles.** Each family is a named rule set in `src/lexinspect/` that can be toggled for development measurement, for example a private module-level set of enabled families. The shipped default enables all twelve, and the toggle is not part of the public API.
- **Equivalence check.** On the 120 development texts, the implemented candidate with all families on must equal the simulation (`scripts/simulate.py` with the same rule set) hit for hit, or every difference must be listed and explained. The same holds for each family alone. For the rules revised after audit r1, which the simulation does not model, this comparison is superseded by a diff against the round-1 candidate's output, every changed hit attributed to a disposition (`equivalence_report_r2.md`), and, for audit r2, by a diff against the r2 candidate's output with every changed hit attributed to an r2 disposition (same report, section (c)); the `only([])` identity with 0.3.3 still holds.
- **Tests:** constructed minimal pairs for every rule, both positive and negative, including the caveats named in TAXONOMY §5.1 (concessive *while* + participle, scare quotes, *they* = cited authors, *above-mentioned*). Development fixtures are allowed only when labelled with their provenance. Since audit r1: every remaining rule has a case that changes behaviour against 0.3.3 and a retention case, and the declared multi-branch matrix requires the appropriate change, keep or retain kinds for each branch; every removed rule has a 0.3.3-retention case; assertions cover the complete set of hits overlapping the target; limitations pin the current output under all families, the family alone and none, and state the right answer as a strict expected failure. Audit probes used as fixtures are labelled "audit-derived" (r1) or "audit-derived (r2)". Since audit r2: every case states its overlapping hits in full (surface, claim, exact character span, canonical marker or PHRASE expression); the covered rule-ID set is asserted exactly; the multi-branch rules touched by A1–A3 and r2 have branch-labelled cases checked against a declared branch matrix.
- **Full suite:** the existing tests (`uv run pytest`) pass, ruff is clean, and the deployment bundle and latency are unchanged in kind.

## Log

- 2026-10-17: drafted from TAXONOMY_REPORT.md (Opus 5.5 research agent, run lexinspect-fix040-taxonomy-r1).
- 2026-10-17 audit r1 revisions: the independent implementation audit (`sol_impl_audit_r1.md`, verdict REVISE) and the maintainer's dispositions (`AUDIT_R1_DISPOSITIONS.md`), implemented by an Opus 5.5 agent (`IMPLEMENTATION_REPORT_r2.md`). These changes are audit-driven, made before any fix-check collection; the audit's probe sentences are development-exposed. Removed: PH-03, PH-07, PH-08, SX-03, the UP TO branch of PH-11, MD-12's coordination branch, MD-15's *called* branch, MD-16's source-object whitelist, SX-01's research-noun class. Narrowed or corrected: own_text (MD-08/09, MD-16, MD-17/18), MD-11, MD-13/PH-02, MD-22, MD-23, MD-24, MD-27 (reassignment to hedges), MD-29, MD-31, MD-32, PH-12. Family assignment is unchanged; no family is empty, so F = 12 and J = 68 stand. Development output changes against the round-1 candidate: `equivalence_report_r2.md`; `only([])` stays byte-identical to 0.3.3 on the 120 development texts.
- 2026-10-17 audit r1 addendum (maintainer, AUDIT_R1_DISPOSITIONS.md A1–A3). These narrow or correct rules inside their existing families; F and J are unchanged:
  - **A1, MD-13/PH-02:** the demonstrative clause opener also covers a coordinator, a subordinator and an opening quotation mark or bracket.
  - **A2, own_text:** the class adds the self-mention text nouns *article* and *thesis* from 0.3.3 data.
  - **A3, MD-18:** reassignment only with a named source subject.
- 2026-10-17 audit r2 revisions: the independent implementation audit round 2 (`sol_impl_audit_r2.md`, verdict REVISE) and the maintainer's dispositions (`AUDIT_R2_DISPOSITIONS.md`), implemented by an Opus 5.5 agent (`IMPLEMENTATION_REPORT_r3.md`). These changes are audit-driven, made before any fix-check collection; the r2 probe sentences are development-exposed. All stay inside their families; F = 12 and J = 68 stand.
  - **MD-E (and MD-C through own_text, MD-08/09):** R2-B1, an owner other than the writers defeats *this/current/present/here* in own_text; R2-B2, MD-18's nominal branch needs a 0.3.3 source noun.
  - **MD-F:** R2-B3, MD-27 also reassigns passive *expected* + finite clause to hedges and otherwise keeps the 0.3.3 check instead of deleting; R2-S2, MD-22 keeps disjuncts enclosed by paired brackets or dashes.
  - **MD-G:** R2-S3, the MD-29 exception is narrowed to *important*/*essential*.
  - **MD-H:** R2-S4, a possessive `’` does not close a curly single quotation.
  - **MD-D / PH-A:** R2-S1, a straight single opening quote opens the clause for MD-13/PH-02.
  - Tests (R2-S5), SOURCES.md wording (R2-M1) and the S8 snapshot refresh (R2-M2) change no rule. Development output changes against the r2 candidate: `equivalence_report_r2.md` section (c), all attributed; `only([])` stays byte-identical to 0.3.3 on the 120 development texts.
- 2026-10-17 audit r3: the third implementation audit (`sol_impl_audit_r3.md`) found the candidate READY TO FREEZE, with no blocking or should-fix finding. Its three minor findings were documentation only and were applied by the maintainer (changelog wording and two limitation bullets, report and ledger wording, the `not_degree` docstring). After the harness audit r4 restricted-content check, one illustrative example in a `_context.py` comment was reworded; no behaviour changed.
- 2026-10-17 freeze: status set to FINAL by the maintainer at candidate commit `3d4df70`, after the harness confirmation audit r8 (READY TO FREEZE) and its minor fix. Component identities are enumerated in `ledger_components.json` (68, a = .05/68).
