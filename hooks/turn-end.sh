#!/usr/bin/env bash
# Stop hook — the Small Council notices when the Chair stops for the user.
#
# When the session that drives an in-progress council run ends a turn with no seat working, the run waits
# on the user: the helper records the wait (council run turn-end) and, with notifications on, sends the
# Chair back once per wait to alert the owner — exit 2, the reason on stderr, which Claude Code hands to
# Claude. Anything else ends the turn silently: no council, no such run, a seat still working, a stop this
# hook already sent back (stop_hook_active), input it can't read, or any fault of the helper's. Nothing goes
# to stdout. In 33 real sessions the doctrine's own alert step was never taken: a hook keeps it instead. The
# same way, while a run's first status card is still due (its first dispatch, not yet shown), the helper
# sends the Chair back once to show it.
#
# Portability: bash 3.2 (macOS), Git Bash on Windows, Linux — no jq, no Python.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
[ -f "$ROOT/bin/council" ] || exit 0
input="$(cat)"

# A stop this hook sent back already ends here. Inside a JSON string every quote is escaped, so the key
# in its own quotes is the input's field, never text quoted in the Chair's message.
printf '%s' "$input" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && exit 0

# session_id and cwd, the input's top-level string values — read as agent-gate.sh reads them.
fields="$(printf '%s' "$input" | LC_ALL=C awk '
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
      if (depth != 1 || (k != "session_id" && k != "cwd") || (k in got)) continue
      if (p[i + 2] !~ /^[ \t\r\n]*:[ \t\r\n]*$/) continue
      v = p[i + 3]; gsub(/\\\//, "/", v)
      got[k] = undo(undo(v, "\002", "\""), "\001", "\\")
    }
    print got["session_id"]; print got["cwd"]
  }' 2>/dev/null)"
{ IFS= read -r sid; IFS= read -r cwd; } <<FIELDS
$fields
FIELDS
[ -n "$sid" ] || exit 0                  # no session: which run this turn belonged to can't be told

if [ -n "$cwd" ]; then
  case "$cwd" in [A-Za-z]:\\*) cwd="$(printf '%s' "$cwd" | tr '\\' '/')" ;; esac   # C:\Users\… as Git Bash takes it
  if [ -d "$cwd" ]; then cd "$cwd" >/dev/null 2>&1 || :; fi
fi

out="$("${BASH:-bash}" "$ROOT/bin/council" run turn-end --session "$sid" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 2 ]; then          # the helper's die exits 2 too, but says nothing on stdout: that ends the turn
  case "$out" in "Small Council:"*) printf '%s\n' "$out" >&2; exit 2 ;; esac
fi
exit 0
