#!/usr/bin/env bash
# Study 4 0.4.0 pilot: context probe for labeller A's launch settings.
# Runs one Claude Code session under exactly the settings labelling will use,
# on dummy files, so its transcript shows what context a labeller receives.
# Usage: probe_claude.sh OUT_DIR
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
prompt='This is a setup check, not a labelling task. Do not open any file. Report, quoting verbatim where you can, every instruction or piece of context you received other than this message: system prompt sections, environment details (working directory, platform, date), any git or repository information, any user or project instruction files such as CLAUDE.md, any memory, any email address or account details, any list of skills, MCP servers or agents, and the tools you have. Say explicitly for each of these whether it is present or absent.'
cd "$dir"
env -i HOME="$HOME" PATH="$PATH" USER="$USER" TMPDIR="$TMPDIR" LANG=en_US.UTF-8 \
  CLAUDE_CONFIG_DIR="$HOME/.claude_extra" \
  claude -p "$prompt" \
  --model claude-sonnet-5-5 --effort high \
  --tools Read,Write,Edit --strict-mcp-config --permission-mode acceptEdits \
  --settings '{"autoMemoryEnabled": false}' \
  --output-format stream-json --verbose </dev/null >"$out/probe_stream.jsonl"
echo "$dir" >"$out/probe_dir.txt"
