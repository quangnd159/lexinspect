# Correction to the fix-check write-up (finding F1)

**Status:** proposed on 2026-10-21 and sent to the independent Stage-1 review (round 1, finding R1-3). The review found it accurate in substance and tightened its wording. The reviewed text was applied to `docs/validation/study4-fix-check.md` ("Deviations and corrections") on 2026-10-21; it is in "Applied text" below. The evidence is in `LAUNCH.md`, section F1.

**What is wrong.** The write-up's first deviation says that labeller A's sessions received a git-status snapshot and that "Labeller B and the adjudicator did not receive it." Both statements are true, but the disclosure is incomplete in two ways:

1. Labeller A's sessions also received the maintainer's personal instruction file, `~/.claude/CLAUDE.md`. It is three lines on when to pause for the maintainer's input, and it says nothing about the study.
2. Labeller B's and the adjudicator's sessions ran with the repository as their working directory:
   - B: 10 primary sessions in round 1; 8 primary sessions and 1 retry in round 2;
   - the adjudicator: 2 Flash sessions in each round.

   Their environment therefore named `/Users/quangnguyendang/webapps/lexinspect`, and B's filesystem access was not limited to its batch directory. In the retained model-visible records inspected, we found no branch/commit snapshot, candidate-direction information, item-level version/family assignments or other labellers' responses. This conclusion is limited to those records; the original pilot adjudicator's effective context was not recovered.

## Proposed replacement for the deviation's second paragraph (as first drafted)

> The snapshot contained no item, label or expected answer. Nor did it say which items were baseline or candidate output, which family they belonged to, or that they were paired.
>
> Labeller B and the adjudicator did not receive the snapshot, but their sessions were also not free of repository context. They ran with the repository as their working directory, so its path, which names the product, appeared in their environment, and labeller B's file access was not limited to its batch directory. No branch, commit, candidate or label information was in their context, and the product name is also in the guidelines. Labeller A's sessions also received the maintainer's personal instruction file, three lines about when to pause for input. This was found on 2026-10-20, after the release, while setting up the 0.4.0 pilot. Later labelling sessions run outside any repository ([launch record](study4-pilot040/LAUNCH.md)).

## Applied text (after the review)

> Labeller B and the adjudicator did not receive the git-status snapshot, but their sessions were not free of repository context: they ran with the repository as working directory, and B's filesystem access was not restricted to its batch directory. In the retained model-visible records we found no branch/commit snapshot, candidate-direction information, item-level version or family assignments, or other labellers' responses. The product name already appeared in the judgement materials. Labeller A also received the maintainer's personal instruction file. The additional context was identified on 2026-10-20. It is a disclosed departure from the intended context isolation; the absence of observed out-of-directory access does not prove that context had no effect. Later labelling uses the direct CLI launch described in the launch record. The numerical decisions and historical records remain unchanged. The sensitivity analysis below removes A's direct contribution to the round-2 reference; it does not erase historical context exposure or establish what fully context-isolated sessions would have judged.

## Effect on the result

- **No gate changes.** The sensitivity analysis already replaces labeller A, whose context carried the version-direction information. In the retained model-visible records inspected, we found no branch/commit snapshot, candidate-direction information, item-level version/family assignments or other labellers' responses. This conclusion is limited to those records; the original pilot adjudicator's effective context was not recovered.
- **The disclosure changes.** For B and the adjudicator, the claim is limited to the retained records inspected: no branch/commit snapshot, candidate-direction information, item-level version/family assignments or other labellers' responses were found there. It does not claim absence of repository context or establish the contents of unrecovered records.
- **The rereview, done 2026-10-21.** Every archived labelling session of B and of the adjudicator was rescreened for file access outside its batch directory:
  - **B:** 24 Codex sessions, those whose first instruction is the labelling prompt: the 16 Oct pilot's 4 batches and the GPT-6-Sol dry run, 10 round-1 sessions and 9 round-2 sessions;
  - **the adjudicator:** the 5 fix-check Flash transcripts.

  In the retained labelling records included in the rescreen, we found no read or listing outside the session's batch directory and no command with a relative path. This does not establish the contents of unrecovered records or undisclosed provider-side context. Review sessions that only quote the prompt are excluded by the first-instruction rule.

- **Limits (added after the review).** The rescreen supports the correction; it does not establish a causal zero effect of the repository context. The existing post-hoc sensitivity removes A's direct contribution to the round-2 reference; it does not erase historical context exposure or establish what fully context-isolated sessions would have judged. The original pilot adjudicator's effective context could not be recovered. The reviewer found no basis to require a third fix-check round, selective relabelling, a new adjudicator qualification or detector changes.
