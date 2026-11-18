#!/usr/bin/env bash
# Small Council — SessionStart hook (fires on startup, resume, clear, and right after a compaction).
#
# For a council-enabled project (one with a .council/ directory) the helper prints a short orientation into the
# session's context: which modes exist, where the map and settled decisions live, how many memory proposals await
# the user, and — most importantly — which council runs are still open. Right after a compaction it tells the agent
# to resume the run THIS session was driving (matched by session id) from disk instead of restarting it; every other
# open run is only reported. For every other project it prints nothing. In every project it leaves an empty per-user
# mark for the session id: proof for `council run open` that the plugin's hooks run in this session.
# The words are the helper's (src/council/commands/session_start.py, the hook-only run session-start), which exits 0
# on its own faults; exit 2 is the launcher's: no Python 3.8+, said in one line where a council home may be.
# It must never break a session: the hook always exits 0. Portability: bash 3.2 (macOS), Git Bash, Linux — no jq.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)}"
input="$(cat 2>/dev/null || true)"
printf '%s' "$input" | CLAUDE_PLUGIN_ROOT="$ROOT" MSYS2_ENV_CONV_EXCL=CLAUDE_PLUGIN_ROOT "${BASH:-bash}" "$ROOT/bin/council" run session-start 2>/dev/null
[ $? -ne 2 ] || ! . "${BASH_SOURCE[0]%[/\\\\]*}/session-mark.sh" 2>/dev/null || no_council "${CLAUDE_PROJECT_DIR:-$PWD}" || printf '%s\n' "[Small Council] Small Council needs Python 3.8 or newer, and none was found: its checks are off in this session until it is installed (python.org); then start a new session."
exit 0
