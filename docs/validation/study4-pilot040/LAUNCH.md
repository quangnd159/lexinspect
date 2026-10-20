# Study 4 0.4.0 pilot: how labelling sessions are launched

**Date:** 2026-10-20. Committed before any 0.4.0 pilot labelling request.

**Applies to:** the 0.4.0 common development pilot (`PLAN.md`), and is proposed for evaluation labelling in Stage 1.

## Why the launch changed

The prereg says each model labeller works in "a fresh session ... [with] no inherited repository or review context ... pointed at a directory holding only the guidelines, the inventory and its batch file". Earlier Study 4 sessions were started as delegated tasks of a T3 Code thread whose project is this repository. Every such session therefore inherited the repository as its working environment. This was found on 2026-10-20 by reading the archived session records (finding F1 below).

Labelling sessions are now started directly with each provider's command-line tool, by `scripts/validation/study4_precision/pilot040/launch.py`, from a new directory outside any git repository.

## Settings per role

Every session runs in `$TMPDIR/<12 hex>/<16 hex>`, which holds only `guidelines.md` (SHA-256 `276d35e8…`), `phrase_sense_inventory.md` (`a761f159…`) and `items.jsonl`. The launcher stops if that directory is inside a git repository. The environment is cleared down to `HOME`, `PATH`, `USER`, `TMPDIR` and `LANG`, plus the role's variables below. The prompt is the registered one (template SHA-256 `86985e10…`, verified against the prereg text).

| Role | Command and settings |
|---|---|
| A, Claude Sonnet 5.5 | `claude -p` with `--model claude-sonnet-5-5 --effort high`, account `CLAUDE_CONFIG_DIR=~/.claude_extra`; tools limited to Read, Write and Edit; `--strict-mcp-config` (no MCP servers); auto-memory off |
| B, GPT-6.1-Sol | `codex exec` with `-m gpt-6.1-sol`, reasoning high; `--ignore-user-config --ignore-rules`; web search off; workspace-write sandbox with network access off; apps, plugins, hooks, browser, computer use, image generation, multi-agent, skill search, goals and tool suggestions off |
| C, DeepSeek V4.1 Flash | `opencode run --standalone` with `opencode/deepseek-v4.1-flash-free#high`; `OPENCODE_DISABLE_CLAUDE_CODE=1` (no Claude Code instruction files); web fetch, web search and skills denied |

**Tools.** Role A has no command-execution tool. Tools restrict execution; the transcript review checks compliance with the no-programmatic-labelling rule. Roles B and C keep their shell tools; for them, as before, the transcript review enforces the no-code rule.

## Evidence that the context is clean

1. **Probes.** One probe session per role ran under these settings on dummy files and was asked to list every piece of context it had received (`pilot040/probe_*.sh`).
2. **Dry run.** One full session per role ran through `launch.py` with the registered prompt on two made-up items, which are in no development or evaluation set.
3. **Screen.** `pilot040/check_sessions.py` searches the injected context of each archived session. It looks for:
   - repository, study and private-path names;
   - git-status blocks;
   - the maintainer's own instruction file.

   It searches the injected context only, because the guidelines themselves name lexinspect. It also lists file paths outside the session's own files and calls that look like code.
   - **Positive control:** an archived 16 Oct A transcript was flagged on every marker.
   - **The dry run:** all three sessions were clean. Each read only its three files and wrote its labels by hand.

**Screen statuses and acceptance (tightened 2026-10-21, after the Stage-1 review, finding R1-4).** The screen used to report a missing provider record as clean. It now gives each session one of three statuses:

- **`technical_failure`:**
  - `session.json` is missing or the session wasn't delivered;
  - the session id is missing or inconsistent;
  - an archived file is missing, unlisted or differs from its recorded hash;
  - the provider record is missing, empty or lacks its expected context fields.
- **`flagged`:**
  - a context marker;
  - a path outside the session's own files, or a relative, `~/`, `$HOME`, `file://` or glob path;
  - a code-like call;
  - a shell command other than reading commands;
  - a tool the role wasn't given.
- **`clean`:** none of the above.

The screen also fails if the archive has no sessions, or if its launch log and session records disagree. With `--expect`, it also fails unless every assigned batch has exactly one delivered session. The launcher records a session as delivered only if its provider record was archived and passes the context checks.

`collect_role.py` requires the screen result (`--screen`) and collects nothing from a session that isn't clean. A flagged session can be accepted only through a recorded human ruling (`--rulings`), after the maintainer has examined the flagged calls in the transcript. The ruling is bound to the session's `session.json` hash and to the hash of its exact flag set. A context-marker hit and a technical failure can't be accepted by any ruling. A stopped batch waits for technical recovery or a relaunch; no label is generated or chosen.

**The 0.4.0 pilot under the tightened screen.** All 10 sessions and the 3 dry-run sessions have complete provider records and no technical failure. Twelve are clean. primary-A-02 is flagged for its one code-like Edit of its own labels file, examined on 2026-10-20 (`RESULTS.md`). That examination is recorded as a ruling in [`screen_rulings.jsonl`](screen_rulings.jsonl). Re-collecting all four pilot label sets with the tightened collector and that ruling reproduces the archived label files and retry manifests byte for byte. The launch inputs (argv, environment, prompt and copied files) are unchanged, and a test checks them against every archived `session.json`.

The probe and dry-run records, with SHA-256 lists, are in the private archive (`lexinspect-private/study4-pilot040/probes/` and `dryrun/`).

**What each role still receives.** All of it is generic, and none of it is repository, review or study context:

- **A:** Claude Code's standard system prompt; the environment block, with "Git repository: false"; the date; and the account's email address, which Claude Code adds as an attachment.
- **B:** Codex's standard instructions; the environment block (working directory, shell, date, time zone and sandbox rules); the multi-agent role text; and a list of 65 generic skills installed for the maintainer's other work. None of the skills relates to text analysis, metadiscourse or PHRASE.
- **C:** OpenCode's standard instructions, with "Is directory a git repo: no", the date, the environment block and its tool catalogue.

## Archive per session

`launch.py` archives under `lexinspect-private/study4-pilot040/sessions/<role>/<token>/`:

- the command's event stream and stderr;
- the delivered `labels.jsonl`;
- the provider's own session record, which is the effective context:
  - the Claude transcript, with its prompt snapshots;
  - the Codex rollout;
  - the OpenCode instruction state and messages;
- `session.json`, which has the argv, the environment, the prompt, the times, the exit code and the SHA-256 of every input and archived file.

`launch_log.jsonl` gets one line per call. The launcher never retries, and a command-line session can't resume by itself after a usage-limit failure. A relaunch is a new call in a new directory.

## F1. Context inherited by earlier Study 4 labelling sessions

The archived records of earlier sessions show the following.

- **Labeller A** (Claude Code, through T3) received a git-status snapshot in the 16 Oct pilot and in both fix-check rounds. The snapshot holds the branch, untracked paths and recent commit subjects. A also received the maintainer's personal instruction file (`~/.claude/CLAUDE.md`, three lines on when to pause for input). The fix-check write-up discloses the snapshot. It does not mention the instruction file.
- **Labeller B** (Codex, through T3) ran with the repository as its working directory in every session: the 16 Oct pilot (4 batches, plus the GPT-6-Sol dry run) and fix-check rounds 1 (10 sessions) and 2 (9 sessions). Its environment block named that directory, `/Users/quangnguyendang/webapps/lexinspect`, as the working root, and its filesystem access was not restricted to the batch directory. No git status, branch or commit was in its context. The session records of the 16 Oct pilot also carry T3's orchestration instructions.
- **The adjudicator** (OpenCode, through T3) ran in the repository directory too. The Flash session records of both fix-check rounds (round 1: 2 sessions plus 1 superseded export; round 2: 2 sessions) have `directory: /Users/quangnguyendang/webapps/lexinspect`. No OpenCode session record of the 16 Oct pilot's adjudicator runs was found, so its context can't be checked; it was launched the same way.

**What the extra context could reveal.** For B and C, it adds nothing about versions, candidates or labels. The product name it exposes is already in the guidelines (21 mentions). For A, the snapshot is the deviation already analysed in the fix-check sensitivity plan. The earlier transcript reviews checked each session's file reads. For the Stage-1 package they are rechecked with `check_sessions.py` for any path outside the batch directory.

**Disposition.** This is a disclosure gap in the 16 Oct pilot record, the prereg's labelling statement and the published fix-check write-up (`docs/validation/study4-fix-check.md`). The correction (`CORRECTION_F1.md`) went to the independent Stage-1 review and was applied to the fix-check write-up and the prereg on 2026-10-21, in the reviewer's wording. No 0.4.0 pilot label depends on these sessions (`PLAN.md` section 3).
