#!/usr/bin/env bash
# Small Council — SessionStart hook (fires on startup, resume, clear, and right after a compaction).
#
# For a council-enabled project (one with a .council/ directory) it prints a short orientation into
# the session's context: which modes exist, where the codebase map and settled decisions live, how
# many memory proposals await the user, and — most importantly — whether a council run was left
# unfinished. Right after a compaction it tells the agent to resume that run from disk instead of
# restarting it. For every other project it prints nothing, so it costs nothing there.
#
# It must never break a session: every failure path is silent and the script always exits 0.

set -u

say() { printf '%s\n' "$*"; }
field() { sed -n "s/^$1:[[:space:]]*//p" "$2" 2>/dev/null | head -n 1 | tr -d '\r'; }

input="$(cat 2>/dev/null || true)"
case "$input" in
  *'"source":"compact"'* | *'"source": "compact"'*) event=compact ;;
  *) event=start ;;
esac

if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0; fi
proj="$(pwd -W 2>/dev/null || pwd)"

# Council home: the MAIN checkout's .council/ (shared by every linked worktree), else ./.council.
home=""
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -n "$common" ] && [ -d "$(dirname "$common")/.council" ]; then
  home="$(dirname "$common")/.council"
elif [ -d "$proj/.council" ]; then
  home="$proj/.council"
fi
[ -n "$home" ] || exit 0
root="$(dirname "$home")"

say "[Small Council] Council-enabled project. Council home: $home"
[ -f "$home/council.config.md" ] || say "- No council.config.md yet: run council-init before the first council mode."
say "- Substantial work? Check for a council mode first (council-review, council-plan, council-implement, council-research, spec-writer, test-architect). Propose it with its size and estimated cost, and wait for a go-ahead before any multi-agent run."

if [ -f "$home/map.md" ]; then
  sha="$(sed -n 's/^map-commit:[[:space:]]*\([0-9a-fA-F]\{7,40\}\).*/\1/p' "$home/map.md" 2>/dev/null | head -n 1)"
  behind=""
  [ -n "$sha" ] && behind="$(git rev-list --count "$sha..HEAD" 2>/dev/null || true)"
  if [ -n "$behind" ] && [ "$behind" -gt 0 ] 2>/dev/null; then
    say "- Orientation: read $home/map.md before exploring the code ($behind commits behind HEAD: trust its structure, verify details)."
  else
    say "- Orientation: read $home/map.md before exploring the code."
  fi
fi

conv="$home/conventions.md"
[ -f "$conv" ] || conv="$root/conventions.md"
if [ -f "$conv" ]; then
  say "- Settled decisions: $conv (respect them; never re-litigate)."
  pending="$(grep -c '^- PROPOSED' "$conv" 2>/dev/null || true)"
  if [ "${pending:-0}" -gt 0 ] 2>/dev/null; then
    say "- $pending memory proposal(s) in that file await the user's yes/no. Raise them at a natural pause."
  fi
fi

if [ -s "$home/active-run" ]; then
  run="$(head -n 1 "$home/active-run" | tr -d '\r')"
  case "$run" in
    /* | [A-Za-z]:*) ;;
    *) run="$root/$run" ;;
  esac
  state="$run/session-state.md"
  if [ -n "$run" ] && [ -f "$state" ]; then
    status="$(field status "$state")"
    case "$status" in
      complete* | abandoned*) ;;
      *)
        mode="$(field mode "$state")"
        if [ -z "$mode" ]; then
          case "$run" in # a 0.1 run: .council/<mode>-output/<TS>
            *-output/*) m="${run%-output/*}"; m="${m##*/}"; mode="council-${m#council-} (legacy run)" ;;
          esac
        fi
        phase="$(field phase "$state")"
        updated="$(field updated "$state")"
        if [ "$event" = compact ]; then
          say "- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}). Re-invoke the context-core skill, read $state, and resume at that phase. Do not restart, do not re-dispatch seats whose files exist, do not skip the completeness gate."
        else
          say "- UNFINISHED COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}, updated: ${updated:-unknown}). Before new council work, ask the user whether to resume it (re-invoke context-core, read $state) or close it (set status: abandoned and empty active-run)."
        fi
        ;;
    esac
  fi
fi

exit 0
