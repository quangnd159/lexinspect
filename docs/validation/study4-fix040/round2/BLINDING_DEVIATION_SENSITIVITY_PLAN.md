# Round 2: metadata-blinding deviation and sensitivity plan

**Written 2026-10-19, after the registered round-2 decision and before this sensitivity analysis was run.** This file is committed and pushed before the analysis is run, and that commit is its timestamp.

## The deviation

The fix protocol ("Blind labelling") says labellers A and B receive only the ordinary judgement payloads, and nothing about the version, the diff direction or the family. An independent final audit (GPT-6.1-Sol, 2026-10-19) found that Claude Code, the harness for labeller A (Claude Sonnet 5.5), added a git-status snapshot to every A session. The snapshot contained:

- the branch name `study4-fix040-candidate`;
- the paths of untracked files, including the round-1 and round-2 collection directories;
- the subjects of the five most recent commits. In round 2's primary sessions these included `Study 4 fix check: round-2 candidate (narrowed)`.

This affected every A delivery in both rounds: 10 primary and 1 retry in round 1, and 8 primary and 1 retry in round 2 (counts from the audit). The maintainer's access-review notes recorded that sessions see this snapshot (round 1, and `ACCESS_REVIEW_RULINGS.md` for round 2), but it was not treated as a deviation or disclosed. That was an error.

What the snapshot did **not** contain:

- any item, label or expected answer;
- which items were 0.3.3 output and which were candidate output;
- which family an item belonged to, or that items were paired;
- the other labeller's labels.

Labeller B (GPT-6.1-Sol through Codex) did not receive it: the branch appears only in the Codex session metadata record, not in any message sent to the model. Nor did the adjudicator (DeepSeek V4.1 Flash through OpenCode), whose sessions contain only the guidelines and items.

## Why a sensitivity analysis

The registered decision stands as registered: the registry is append-only and is not rewritten. The question is whether A's exposure could have produced the pass. If the snapshot biased A, for example towards judging removed detections incorrect, the bias would reach the reference only through A's labels.

## The analysis (fixed before it is run)

**S-B: reference without labeller A.** Run the frozen acceptance calculation (`fixcheck/accept.py`, `acceptance_of`, the same code and constants as the registered decision) on round 2's package, with B's final label file supplied in place of A's. A and B then agree wherever B gave a valid label, so the reference is B's label. Where B gave no valid label, the frozen rule applies: Flash's label where Flash labelled the item, otherwise unresolved, counted worst-case. Nothing else changes: the frames, samples, weights, a = .05/68 and both gates. Output goes to `/tmp` and is then copied into `round2/sensitivity/` with its hashes.

## Decision rule (fixed before it is run)

- **If every applicable gate in both modules passes under S-B** (no removal bound above .15, no cumulative fraction above .05, no breach certificate), the exposure could not have produced the pass by itself. 0.4.0 ships, and the deviation and this analysis are disclosed in the public report and the CHANGELOG as a deviation with a post-hoc sensitivity analysis.
- **If any gate fails or cannot be computed under S-B**, the pass is not treated as protocol-conformant. 0.4.0's matcher changes are not shipped: the release keeps 0.3.3's matching. Both permitted rounds are used, so a further check needs a reviewed amendment to the protocol. The result is disclosed in either case.

This analysis is post hoc and is reported as such. It does not replace the registered decision. It also cannot show that A's labels were unaffected. It shows only whether the pass depends on them.

## Future labelling

Labelling sessions must not receive repository context. For Claude Code sessions, that means running outside any git repository, or with git-status injection disabled, and archiving the effective context.
