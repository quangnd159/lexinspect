#!/usr/bin/env bash
# Study 4 0.4.0 pilot: context probe for the adjudicator's launch settings.
# Runs one OpenCode session under exactly the settings adjudication will use,
# on dummy files, and exports the session so its effective context is visible.
# Usage: probe_opencode.sh OUT_DIR
set -euo pipefail
out=$(cd "$1" && pwd)
dir="$TMPDIR/$(openssl rand -hex 6)/$(openssl rand -hex 8)"
mkdir -p "$dir"
printf '# Guidelines\n\nDummy file for a setup check.\n' >"$dir/guidelines.md"
printf '# Sense inventory\n\nDummy file for a setup check.\n' >"$dir/phrase_sense_inventory.md"
printf '{"id": "probe00001", "module": "metadiscourse", "context": "This is a test.", "marker": "test", "claimed": "dummy"}\n' >"$dir/items.jsonl"
if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
  echo "refusing: $dir is inside a git repository" >&2
  exit 1
fi
prompt='This is a setup check, not a labelling task. Do not open any file or run any command. Report, quoting verbatim where you can, every instruction or piece of context you received other than this message: system instructions, environment details (working directory, platform, date), any git or repository information, any AGENTS.md, CLAUDE.md or other instruction files, any memory, any account details, any list of skills, MCP servers or agents, and the tools you have. Say explicitly for each of these whether it is present or absent.'
cd "$dir"
env -i HOME="$HOME" PATH="$PATH" USER="$USER" TMPDIR="$TMPDIR" LANG=en_US.UTF-8 \
  OPENCODE_DISABLE_CLAUDE_CODE=1 \
  OPENCODE_CONFIG_CONTENT='{"permission": {"webfetch": "deny", "websearch": "deny", "skill": "deny"}}' \
  opencode run --standalone --auto --model 'opencode/deepseek-v4.1-flash-free#high' \
  --format json --print-logs --log-level debug "$prompt" </dev/null \
  >"$out/probe_stream.jsonl" 2>"$out/probe_debug.log"
echo "$dir" >"$out/probe_dir.txt"
