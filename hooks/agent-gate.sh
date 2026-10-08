#!/usr/bin/env bash
# PreToolUse hook (Agent, Task, Workflow) — the Small Council's agent stop.
#
# While a council run this session may be driving is at its agent cap or past its token ceiling, and no
# go of the user's covers the next agent (council cap allow), the call is refused: exit 2, the reason on
# stderr, which Claude Code hands to Claude. A Small Council agent (subagent_type council-worker or
# council-verifier) is also held to the record: refused when no council run is open for it, or when its
# dispatch names a seat the run's plan doesn't select. Anything else lets the call through, silently: no
# council, no in-progress run, a run within its limits, an ordinary agent, input it can't read, or any
# fault of the helper's. The decision is the helper's (council cap check); this script only reads the
# input. A call it lets through is counted as an agent start of the run this session drives (a Workflow
# as one, however many agents it starts), so agents started together, or recorded late, still count.
# Nothing goes to stdout, which Claude Code may read as JSON.
#
# Portability: bash 3.2 (macOS), Git Bash on Windows, Linux — no jq, no Python.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
[ -f "$ROOT/bin/council" ] || exit 0

# session_id, cwd and tool_name, the input's top-level string values, with the escapes \\ \" \/ undone.
# Escaped backslashes and quotes are set aside first, so every " left bounds a string: a key quoted inside
# a value (a prompt that says "cwd": …) stays inside that value, and only the outer object's keys count.
# Only the short stretches between strings are walked character by character.
# Then, for a Small Council agent only (tool_input's own subagent_type), what its dispatch message names:
# the seat — a "Seat: <slug>" line, else the file it writes (seats/<slug>.md for a worker, verify-<n>.md
# for a verifier) when one name stands out, preferring those on a line that says write — and the run
# folder (runs/<date-time>-<mode>) that file is in, else the one run folder the message names. What it
# can't pick out stays empty, and the helper judges nothing on it.
fields="$(LC_ALL=C awk '
  function undo(v, c, r,   q, m, j, out) { m = split(v, q, c); out = q[1]; for (j = 2; j <= m; j++) out = out r q[j]; return out }
  { s = s $0 "\n" }
  END {
    gsub(/\\\\/, "\001", s); gsub(/\\"/, "\002", s)
    sub(/\n+$/, "", s)                                           # macOS awk splits at a line break too
    n = split(s, p, "\"")
    for (i = 1; i + 3 <= n; i += 2) {
      t = p[i]
      for (c = 1; c <= length(t); c++) {
        ch = substr(t, c, 1)
        if (ch == "{" || ch == "[") depth++
        else if (ch == "}" || ch == "]") depth--
      }
      if (depth < 2) inner = 0                                   # back out of tool_input
      k = p[i + 1]
      if (depth == 1 && k == "tool_input" && p[i + 2] ~ /^[ \t\r\n]*:[ \t\r\n]*\{/) inner = 1
      if ((k in got) || p[i + 2] !~ /^[ \t\r\n]*:[ \t\r\n]*$/) continue
      if (!(depth == 1 && (k == "session_id" || k == "cwd" || k == "tool_name")) &&
          !(depth == 2 && inner && (k == "subagent_type" || k == "prompt"))) continue
      v = p[i + 3]
      if (k == "prompt") { gsub(/\\n/, "\003", v); gsub(/\\[rt]/, " ", v) }   # a line break: kept apart, as split() breaks at one
      gsub(/\\\//, "/", v)
      got[k] = undo(undo(v, "\002", "\""), "\001", "\\")
    }
    gsub("\003", "\n", got["prompt"])
    print got["session_id"]; print got["cwd"]; print got["tool_name"]
    ty = got["subagent_type"]; seat = ""; run = ""
    if (ty != "small-council:council-worker" && ty != "small-council:council-verifier") ty = ""
    for (i = 1; i <= n; i += 2) { t = p[i]; bal += gsub(/[{[]/, "", t) - gsub(/[]}]/, "", t) }
    if (n % 2 == 0 || bal != 0) ty = ""                         # a cut-off input: nothing judged on its message
    if (ty != "") {
      runre = "runs/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]-[a-z][a-z0-9-]*"
      fre = (ty ~ /worker$/) ? "seats/[A-Za-z0-9_-]+[.]md" : "verify-[A-Za-z0-9_-]+[.]md"
      P = got["prompt"]; gsub(/\\/, "/", P)                     # a Windows path reads as one with /
      nl = split(P, L, "\n")
      for (j = 1; j <= nl && seat == ""; j++)
        if (match(L[j], /^[ \t>*_#-]*[Ss]eat[*_]*:[*_ \t]*[A-Za-z0-9._-]+/)) {
          seat = substr(L[j], RSTART, RLENGTH); sub(/^[ \t>*_#-]*[Ss]eat[*_]*:[*_ \t]*/, "", seat); sub(/[.]+$/, "", seat)
        }
      for (j = 1; j <= nl; j++) {
        line = L[j]; rest = line; off = 0
        while (match(rest, fre)) {
          at = off + RSTART; m = substr(rest, RSTART, RLENGTH); rest = substr(rest, RSTART + RLENGTH); off = at + length(m) - 1
          if (ty !~ /worker$/ && at > 1 && substr(line, at - 1, 1) ~ /[A-Za-z0-9_.-]/) continue   # preverify-1.md is no verdict file
          slug = (ty ~ /worker$/) ? substr(m, 7, length(m) - 9) : substr(m, 1, length(m) - 3)
          tok = ""; for (b = at - 1; b >= 1 && substr(line, b, 1) ~ /[A-Za-z0-9._\/:~-]/; b--) tok = substr(line, b, 1) tok
          sub(/\/$/, "", tok); r = ""
          if (match(tok, runre "$")) r = substr(tok, RSTART + 5)
          if (!(slug in cand)) { cand[slug] = 1; nc++; last = slug }
          if (r != "" && crun[slug] == "") crun[slug] = r
          if (line ~ /[Ww]rit/ && !(slug in wrote)) { wrote[slug] = 1; nw++; wlast = slug }
        }
      }
      if (seat == "" && nc == 1) seat = last
      else if (seat == "" && nw == 1) seat = wlast
      if (seat != "" && crun[seat] != "") run = crun[seat]
      else {
        rest = P
        while (match(rest, runre)) {
          r = substr(rest, RSTART + 5, RLENGTH - 5); rest = substr(rest, RSTART + RLENGTH)
          if (!(r in seen)) { seen[r] = 1; nr++; run = r }
        }
        if (nr != 1) run = ""
      }
    }
    print ty; print seat; print run
  }' 2>/dev/null)"
{ IFS= read -r sid; IFS= read -r cwd; IFS= read -r tool; IFS= read -r atype; IFS= read -r aseat; IFS= read -r arun; } <<FIELDS
$fields
FIELDS

if [ -n "$cwd" ]; then
  case "$cwd" in [A-Za-z]:\\*) cwd="$(printf '%s' "$cwd" | tr '\\' '/')" ;; esac   # C:\Users\… as Git Bash takes it
  if [ -d "$cwd" ]; then cd "$cwd" >/dev/null 2>&1 || :; fi
fi

if [ -n "$sid" ]; then set -- cap check --session "$sid"; else set -- cap check; fi
case "$tool" in
  Agent|Task|Workflow)
    set -- "$@" "$tool"                                                # about to start: counted if let through
    if [ -n "$atype" ]; then                                           # a Small Council agent: held to the record
      set -- "$@" "type=$atype"
      [ -z "$aseat" ] || set -- "$@" "seat=$aseat"
      [ -z "$arun" ] || set -- "$@" "run=$arun"
    fi ;;
esac
out="$("${BASH:-bash}" "$ROOT/bin/council" "$@" 2>/dev/null)"; rc=$?
if [ "$rc" -eq 2 ]; then          # the helper's die exits 2 too, but says nothing on stdout: that lets the call through
  case "$out" in "Small Council:"*) printf '%s\n' "$out" >&2; exit 2 ;; esac
fi
exit 0
