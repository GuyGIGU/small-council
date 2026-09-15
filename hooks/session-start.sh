#!/usr/bin/env bash
# Small Council — SessionStart hook (fires on startup, resume, clear, and right after a compaction).
#
# For a council-enabled project (one with a .council/ directory) it prints a short orientation into
# the session's context: which modes exist, where the map and settled decisions live, how many memory
# proposals await the user, and — most importantly — which council runs are still open. Right after a
# compaction it tells the agent to resume the run THIS session was driving (matched by session id)
# from disk instead of restarting it; every other open run is only reported. For every other project
# it prints nothing, so it costs nothing there.
#
# It sources bin/council, so the hook and the helper find the council home the same way. It must never
# break a session: every failure path is silent and the script always exits 0.

set -u

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)}"
# shellcheck source=../bin/council
. "$ROOT/bin/council" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
case "$input" in
  *'"source":"compact"'* | *'"source": "compact"'*) event=compact ;;
  *'"source":"clear"'* | *'"source": "clear"'*) event=clear ;;
  *) event=start ;;
esac
sid="$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"

if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0; fi
home="$(council_home)"
[ -d "$home" ] || exit 0
root="$(dirname "$home")"
top="$(this_tree)"

say "[Small Council] Council-enabled project. Council home: $home"
[ -f "$home/council.config.md" ] || say "- No council.config.md yet: run council-init before the first council mode."
say "- Substantial work? Check for a council mode first (council-review, council-plan, council-implement, council-research, spec-writer, test-architect). Propose it with its size and estimated cost, and wait for a go-ahead before any multi-agent run."
say "- The \`council\` helper does the bookkeeping (\`council run status\`, \`council doctor\`); if it isn't on PATH, run it as: bash \"$ROOT/bin/council\""

if [ -f "$home/map.md" ]; then
  sha="$(sed -n 's/^map-commit:[[:space:]]*\([0-9a-fA-F]\{7,40\}\).*/\1/p' "$home/map.md" 2>/dev/null | head -n 1)"
  behind=""
  [ -n "$sha" ] && behind="$(git rev-list --count "$sha..HEAD" 2>/dev/null || true)"
  if [ -n "$behind" ] && [ "$behind" -gt 0 ] 2>/dev/null; then
    say "- Orientation: $home/map.md lists where things live, hot spots and vocabulary — check it before exploring unfamiliar code ($behind commits behind HEAD: trust its structure, verify details)."
  else
    say "- Orientation: $home/map.md lists where things live, hot spots and vocabulary — check it before exploring unfamiliar code."
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

# Open runs (0.3+: every run folder under runs/ carries its own status, so several can be open at once).
runs="$(list_runs "$home" 20 open)"
if [ -n "$runs" ]; then
  here_n="$(printf '%s\n' "$runs" | TOP="$top" awk -F'\t' '$4 == ENVIRON["TOP"] || $4 == "-" { n++ } END { print n + 0 }')"
  # After a compaction, only the run this session was driving is resumed: the one whose session: matches
  # this session's id, or — for a run that recorded none — the newest in-progress run on this tree, if
  # it was touched in the last 12 hours. Every other open run is only listed.
  driving=""; fallback=""
  if [ "$event" = compact ]; then
    while IFS="$TAB" read -r dir mode phase croot updated status actual; do
      [ -n "$dir" ] || continue
      croot="$(undash "$croot")"
      { [ -z "$croot" ] || [ "$croot" = "$top" ]; } || continue
      [ "$status" = in-progress ] || continue
      rsid="$(field session "$dir/session-state.md")"
      if [ -n "$sid" ] && [ "$rsid" = "$sid" ]; then driving="$dir"; break; fi
      if [ -z "$fallback" ] && { [ -z "$rsid" ] || [ -z "$sid" ]; } \
         && [ -n "$(find "$dir/session-state.md" -mmin -720 2>/dev/null)" ]; then
        fallback="$dir"
      fi
    done <<RUNS
$runs
RUNS
    [ -n "$driving" ] || driving="$fallback"
  fi
  printf '%s\n' "$runs" | while IFS="$TAB" read -r dir mode phase croot updated status actual; do
    [ -n "$dir" ] || continue
    croot="$(undash "$croot")"; phase="$(undash "$phase")"; updated="$(undash "$updated")"
    skill="$(mode_skill "$(undash "$mode")")"
    runflag=""
    [ "${here_n:-0}" -le 1 ] 2>/dev/null || runflag=" Several runs are open on this tree: pass --run ${dir##*/} to every council command for this one."
    if [ -n "$croot" ] && [ "$croot" != "$top" ]; then
      say "- Another council run is open in a different working tree: ${dir##*/} ($skill, phase ${phase:-?}, code root $croot). Leave it alone."
    elif [ "$status" = paused ]; then
      say "- PAUSED COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}). Resume it only when the user asks."
    elif [ "$event" = compact ] && [ "$dir" = "$driving" ]; then
      seats="$(seat_summary "$dir")"
      say "- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}). Re-invoke the $skill skill (it loads context-core), read $dir/session-state.md, re-read the doctrine for that phase, and continue from there.${seats:+ Seats — $seats.} Do not restart, do not re-dispatch seats that are running or done (wait for their notifications), do not skip the completeness check.$runflag"
    elif [ "$event" = compact ]; then
      say "- Also open on this working tree, not this session's run: ${dir##*/} ($skill, phase ${phase:-?}). Leave it unless the user asks."
    else
      if [ "$event" = clear ]; then
        seats="$(seat_summary "$dir")"
      else
        seats="$(seat_summary "$dir" "were running when that session ended (they are gone — re-dispatch each once if you resume)")"
      fi
      say "- UNFINISHED COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}).${seats:+ Seats — $seats.} Before new council work, ask the user whether to resume it (re-invoke the $skill skill, read its session-state.md) or close it (council run close --run ${dir##*/} --status abandoned).$runflag"
    fi
  done
fi

# Older layouts (0.1/0.2) kept one pointer to the in-flight run; runs outside runs/ are only found here.
if [ -s "$home/active-run" ]; then
  run="$(head -n 1 "$home/active-run" | tr -d '\r')"
  case "$run" in
    /* | [A-Za-z]:*) ;;
    *) run="$root/$run" ;;
  esac
  state="$run/session-state.md"
  case "$run" in
    "$home/runs/"*) ;;
    *)
      if [ -n "$run" ] && [ -f "$state" ]; then
        status="$(field status "$state")"
        case "$status" in
          complete* | abandoned*) ;;
          *)
            mode="$(field mode "$state")"
            if [ -z "$mode" ]; then
              case "$run" in *-output/*) m="${run%-output/*}"; m="${m##*/}"; mode="council-${m#council-} (legacy run)" ;; esac
            fi
            phase="$(field phase "$state")"
            updated="$(field updated "$state")"
            if [ "$event" = compact ]; then
              say "- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}). If this session was running it, re-invoke that mode's skill, read $state, and resume at that phase. Do not restart, do not re-dispatch seats whose files exist, do not skip the completeness check."
            else
              say "- UNFINISHED COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}, updated: ${updated:-unknown}). Before new council work, ask the user whether to resume it or close it (council run close --run \"$run\" --status abandoned)."
            fi
            ;;
        esac
      fi
      ;;
  esac
fi

exit 0
