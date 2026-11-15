#!/usr/bin/env bash
# Small Council — SessionStart hook (fires on startup, resume, clear, and right after a compaction).
#
# For a council-enabled project (one with a .council/ directory) the helper prints a short orientation into the
# session's context: which modes exist, where the map and settled decisions live, how many memory proposals await
# the user, and — most importantly — which council runs are still open. Right after a compaction it tells the agent
# to resume the run THIS session was driving (matched by session id) from disk instead of restarting it; every other
# open run is only reported. For every other project it prints nothing. In every project it leaves an empty per-user
# mark for the session id: proof for `council run open` that the plugin's hooks run in this session.
#
# The words are the helper's: its hook-only run session-start command (src/council/commands/session_start.py) reads
# this hook's input. It must never break a session: the helper's faults are silent here and the hook always exits 0.
# Portability: bash 3.2 (macOS), Git Bash on Windows, Linux — no jq.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)}"
input="$(cat 2>/dev/null || true)"
printf '%s' "$input" | CLAUDE_PLUGIN_ROOT="$ROOT" MSYS2_ENV_CONV_EXCL=CLAUDE_PLUGIN_ROOT "${BASH:-bash}" "$ROOT/bin/council" run session-start 2>/dev/null
exit 0
