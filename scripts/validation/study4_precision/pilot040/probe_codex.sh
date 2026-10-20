#!/usr/bin/env bash
# Study 4 0.4.0 pilot: context probe for labeller B's launch settings.
# Runs one Codex session under exactly the settings labelling will use, on
# dummy files, so its session file shows what context a labeller receives.
# Usage: probe_codex.sh OUT_DIR
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
prompt='This is a setup check, not a labelling task. Do not open any file or run any command. Report, quoting verbatim where you can, every instruction or piece of context you received other than this message: system and developer instructions, environment details (working directory, shell, date), any git or repository information, any AGENTS.md or other instruction files, any memory, any account details, any list of skills, plugins, apps, MCP servers or agents, and the tools you have. Say explicitly for each of these whether it is present or absent.'
off=(apps plugins remote_plugin hooks browser_use browser_use_external computer_use
  image_generation multi_agent skill_search skill_mcp_dependency_install goals tool_suggest
  in_app_browser)
flags=()
for f in "${off[@]}"; do flags+=(--disable "$f"); done
cd "$dir"
env -i HOME="$HOME" PATH="$PATH" USER="$USER" TMPDIR="$TMPDIR" LANG=en_US.UTF-8 \
  codex exec --ignore-user-config --ignore-rules --skip-git-repo-check -C "$dir" \
  -m gpt-6.1-sol -c model_reasoning_effort='"high"' -c web_search='"disabled"' \
  -s workspace-write "${flags[@]}" --json "$prompt" </dev/null >"$out/probe_stream.jsonl"
echo "$dir" >"$out/probe_dir.txt"
