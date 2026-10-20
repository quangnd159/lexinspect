# Proposed correction to the fix-check write-up (finding F1)

**Status:** proposed on 2026-10-21. It goes to the independent Stage-1 review and is applied to `docs/validation/study4-fix-check.md` only after that review. The evidence is in `LAUNCH.md`, section F1.

**What is wrong.** The write-up's first deviation says that labeller A's sessions received a git-status snapshot and that "Labeller B and the adjudicator did not receive it." Both statements are true, but the disclosure is incomplete in two ways:

1. Labeller A's sessions also received the maintainer's personal instruction file, `~/.claude/CLAUDE.md`. It is three lines on when to pause for the maintainer's input, and it says nothing about the study.
2. Labeller B's and the adjudicator's sessions ran with the repository as their working directory:
   - B: 10 primary sessions in round 1 and 9 in round 2;
   - the adjudicator: 2 Flash sessions in each round.

   Their environment therefore named `/Users/quangnguyendang/webapps/lexinspect`, and B's filesystem access was not limited to its batch directory. No git status, branch, commit or candidate information reached them.

## Proposed replacement for the deviation's second paragraph

> The snapshot contained no item, label or expected answer. Nor did it say which items were baseline or candidate output, which family they belonged to, or that they were paired.
>
> Labeller B and the adjudicator did not receive the snapshot, but their sessions were also not free of repository context. They ran with the repository as their working directory, so its path, which names the product, appeared in their environment, and labeller B's file access was not limited to its batch directory. No branch, commit, candidate or label information was in their context, and the product name is also in the guidelines. Labeller A's sessions also received the maintainer's personal instruction file, three lines about when to pause for input. This was found on 2026-10-20, after the release, while setting up the 0.4.0 pilot. Later labelling sessions run outside any repository ([launch record](study4-pilot040/LAUNCH.md)).

## Effect on the result

- **No gate changes.** The sensitivity analysis already replaces labeller A, whose context carried the version-direction information. B's and the adjudicator's extra context carried no version, family or label information.
- **The disclosure changes.** The blinding statement for B and the adjudicator becomes "no version, family or label information" rather than "no repository context".
- **The rereview, done 2026-10-21.** Every archived labelling session of B and of the adjudicator was rescreened for file access outside its batch directory:
  - **B:** 24 Codex sessions, those whose first instruction is the labelling prompt: the 16 Oct pilot's 4 batches and the GPT-6-Sol dry run, 10 round-1 sessions and 9 round-2 sessions;
  - **the adjudicator:** the 5 fix-check Flash transcripts.

  Every path in their tool calls lies inside the session's own batch directory, and none ran a command with a relative path. With the repository as working directory, a relative path would have read repository files. No session read or listed a file outside its batch directory. Review sessions that only quote the prompt are not labelling sessions and are excluded by the first-instruction rule.
