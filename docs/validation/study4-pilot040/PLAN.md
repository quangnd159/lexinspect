# Study 4: the 0.4.0 common development pilot (declaration)

**Date:** 2026-10-20

**Applies to:** `docs/validation/study4-fix-protocol.md`, section "After the candidate passes", items 1–2. It is the first step of the Stage-1 preparation of the precision study (`docs/validation/study4-preregistration.md`).

**Timing:** this file is committed **before** the 0.4.0 development population is rebuilt and before any pilot item exists. No 0.4.0 pilot label exists.

## 1. Rebuild

The full 0.4.0 hit population is rebuilt on the original 120 development texts. The command, run at the commit that adds this file (lexinspect 0.4.0, `src/` identical to tag `v0.4.0`), is:

```
uv run --offline --no-sync python -I scripts/validation/study4_precision/build.py \
    --set development --sample-seed 473840911 \
    --out .cache/validation/study4_v040 --raw-cache .cache/validation/study4_v040/raw
```

- The download cache `.cache/validation/study4_v040/raw` is a byte copy of the development cache `.cache/validation/study4/raw`. The original cache and the 0.3.2 build are not touched.
- Texts are collected with the development seed 20261016, exactly as in the 0.3.2 build.
- **Text identity check.** The rebuild is valid only if the new `texts.jsonl` has the pinned SHA-256 `5dba40cc…` and every `texts/T###.txt` is byte-identical to the 0.3.2 build's. Otherwise the build is discarded and nothing is sampled from it.

## 2. Draw

The pilot is drawn by the registered algorithm (`build.draw`: metadiscourse 100 per category, PHRASE 300 over K-band × sense strata, a 15% marker cap, weights N_h/n_h). The targets are 1,000 metadiscourse and 300 PHRASE, capped at availability.

- **A new sampling seed.** Every sampling step (selection, item ids, item order, human-check sample and labeller orders) uses the seed **473840911**. The rule that fixes it is: the first 8 hex digits of `sha256("study4-v040-common-pilot|20261016")` read as an integer (`1c3e3d0f…` → 473840911). Using a new seed gives the pilot new item ids, so no 0.4.0 id can be confused with a 0.3.2 id. If any new id equals a 0.3.2 pilot id, the draw is not used and the collision is reported.
- The selection is not assembled from old survivors plus changed hits. It is a fresh draw from the full 0.4.0 frame.
- The seed, manifest, key, frame and the items' SHA-256 hashes are archived before any labelling request.

## 3. Labels: no reuse

The protocol allows an old label to be reused when the whole displayed payload and the guideline, inventory and prompt versions are identical. **This pilot reuses no label.** Every selected item gets new labeller A and labeller B labels, then adjudication under the registered rule.

The reason is that the 16 Oct pilot's A sessions did not meet the labelling conditions. The transcripts of the four delivered A batches (A-01 to A-04, the `-r2` relaunches on 2026-10-16) show that Claude Code added a git-status snapshot to each session. That snapshot held the branch (`main`), the untracked paths (including `docs/validation/study4-guidelines.md`, `docs/validation/study4-preregistration.md` and `scripts/validation/study4_precision/`) and the three latest commit subjects (0.3.3 and earlier). It held no item, label, version under test or review content. The prereg nevertheless promises labellers "no inherited repository or review context". Reusing those labels would carry this deviation into the 0.4.0 pilot. Not reusing is the stricter of the two options the protocol allows.

The 16 Oct pilot stays as history: its build, labels, adjudicator selection and simulation are kept unchanged. Its snapshot is disclosed in the prereg.

## 4. Labelling conditions

- Labeller A (Claude Sonnet 5.5, effort high), labeller B (GPT-6.1-Sol, reasoning high) and the adjudicator (DeepSeek V4.1 Flash, `opencode/deepseek-v4.1-flash-free`, variant high) work in fresh sessions with the frozen guidelines (`276d35e8…`), the frozen inventory (`a761f159…`) and the registered prompts.
- Their working directory is outside any git repository. Before any labelling request, a probe session under the same launch settings proves that its effective context has no git status, repository path, memory or review content. The effective context of every labelling session is archived.
- A labelling session that fails (for example on a usage limit) is cancelled at once. A relaunch gets its own working folder.
- Adjudication follows the prereg's registered reference procedure, outcome by outcome. Flash stays the adjudicator (protocol item 4). Its completeness and agreement diagnostics are reported on this pilot.

## 5. What follows

Pilot quantities, recalibration under the retained `pilot_resolution` rule, the frozen 58-cell simulation and the prereg updates follow the protocol's items 2, 3 and 5. They are recorded in this folder.
