#!/usr/bin/env bash
# PreToolUse hook (Agent, Task, Workflow) — the Small Council's agent stop.
#
# While a council run this session may be driving is at its agent cap or past its token ceiling, and no
# go of the user's covers the next agent (council cap allow), the call is refused: exit 2, the reason on
# stderr, which Claude Code hands to Claude. Anything else lets the call through, silently: no council,
# no in-progress run, a run within its limits, input it can't read, or any fault of the helper's. The
# decision is the helper's (council cap check); this script only reads the input. A call it lets through
# is counted as an agent start of the run this session drives (a Workflow as one, however many agents
# it starts), so agents started together, or recorded late, still count. Nothing goes to stdout, which
# Claude Code may read as JSON.
#
# Portability: bash 3.2 (macOS), Git Bash on Windows, Linux — no jq, no Python.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
[ -f "$ROOT/bin/council" ] || exit 0

# session_id, cwd and tool_name, the input's top-level string values, with the escapes \\ \" \/ undone.
# Escaped backslashes and quotes are set aside first, so every " left bounds a string: a key quoted inside
# a value (a prompt that says "cwd": …) stays inside that value, and only the outer object's keys count.
# Only the short stretches between strings are walked character by character.
fields="$(LC_ALL=C awk '
  function undo(v, c, r,   q, m, j, out) { m = split(v, q, c); out = q[1]; for (j = 2; j <= m; j++) out = out r q[j]; return out }
  { s = s $0 "\n" }
  END {
    gsub(/\\\\/, "\001", s); gsub(/\\"/, "\002", s)
    n = split(s, p, "\"")
    for (i = 1; i + 3 <= n; i += 2) {
      t = p[i]
      for (c = 1; c <= length(t); c++) {
        ch = substr(t, c, 1)
        if (ch == "{" || ch == "[") depth++
        else if (ch == "}" || ch == "]") depth--
      }
      k = p[i + 1]
      if (depth != 1 || (k != "session_id" && k != "cwd" && k != "tool_name") || (k in got)) continue
      if (p[i + 2] !~ /^[ \t\r\n]*:[ \t\r\n]*$/) continue
      v = p[i + 3]; gsub(/\\\//, "/", v)
      got[k] = undo(undo(v, "\002", "\""), "\001", "\\")
    }
    print got["session_id"]; print got["cwd"]; print got["tool_name"]
  }' 2>/dev/null)"
{ IFS= read -r sid; IFS= read -r cwd; IFS= read -r tool; } <<FIELDS
$fields
FIELDS

if [ -n "$cwd" ]; then
  case "$cwd" in [A-Za-z]:\\*) cwd="$(printf '%s' "$cwd" | tr '\\' '/')" ;; esac   # C:\Users\… as Git Bash takes it
  if [ -d "$cwd" ]; then cd "$cwd" >/dev/null 2>&1 || :; fi
fi

if [ -n "$sid" ]; then set -- cap check --session "$sid"; else set -- cap check; fi
case "$tool" in Agent|Task|Workflow) set -- "$@" "$tool" ;; esac     # about to start: counted if let through
out="$("${BASH:-bash}" "$ROOT/bin/council" "$@" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 2 ]; then          # the helper's die exits 2 too, but says nothing on stdout: that lets the call through
  case "$out" in "Small Council:"*) printf '%s\n' "$out" >&2; exit 2 ;; esac
fi
exit 0
