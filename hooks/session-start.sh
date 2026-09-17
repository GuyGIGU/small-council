#!/usr/bin/env bash
# Small Council — SessionStart hook (fires on startup, resume, clear, and right after a compaction).
#
# For a council-enabled project (one with a .council/ directory) it prints a short orientation into
# the session's context: which modes exist, where the map and settled decisions live, how many memory
# proposals await the user, and — most importantly — which council runs are still open. Right after a
# compaction it tells the agent to resume the run THIS session was driving (matched by session id)
# from disk instead of restarting it; every other open run is only reported. A run another session
# updated recently may still be live there, so it is never offered for re-dispatch or closing. For
# every other project it prints nothing, so it costs nothing there.
#
# It sources bin/council, so the hook and the helper find the council home the same way. It must never
# break a session: every failure path is silent and the script always exits 0. It must also stay well
# inside Claude Code's 15 s limit however many runs were left open: every state file is read in one
# pass, only this tree's runs are described (at most 5), and other trees' runs are summed up.

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
NL='
'

if [ -f "$home/council.config.md" ]; then
  say "[Small Council] Council-enabled project. Council home: $home"
  say "- Substantial work? Check for a council mode first (council-review, council-plan, council-implement, council-research, council-postgame, spec-writer, test-architect). Propose it with its size and estimated cost, and wait for a go-ahead before any multi-agent run."
  say "- The \`council\` helper does the bookkeeping (\`council run status\`, \`council doctor\`); if it isn't on PATH, run it as: bash \"$ROOT/bin/council\""
else
  # No config: the folder holds a post-game's results, or an unfinished council-init. One line, no nudges.
  say "[Small Council] $home holds council results, but the council isn't set up here (No council.config.md yet). council-init sets it up for reviews, plans, builds and research; a post-game needs none."
fi

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
driving=""
runs="$(list_runs "$home" 100000 open)"
if [ -n "$runs" ]; then
  # Split them: this tree's runs (a run with no code-root counts as this tree's), other trees' runs, and
  # runs whose working tree no longer exists. Other trees' runs are only summed up.
  mine=""; here_n=0; others=""; n_other=0; gone=""; n_gone=0
  while IFS="$TAB" read -r dir mode phase croot updated status actual rsid; do
    [ -n "$dir" ] || continue
    if [ "$croot" = - ] || [ "$croot" = "$top" ]; then     # rows keep "-" for an empty value (read merges tabs)
      mine="$mine$dir$TAB$mode$TAB$phase$TAB$updated$TAB$status$TAB$rsid$NL"; here_n=$((here_n + 1))
    elif [ -d "$croot" ]; then
      n_other=$((n_other + 1))
      [ "$phase" != - ] || phase="?"
      [ "$n_other" -gt 5 ] || others="$others${others:+; }${dir##*/} ($(mode_skill "$mode"), phase $phase, code root $croot)"
    else
      n_gone=$((n_gone + 1))
      [ "$n_gone" -gt 5 ] || gone="$gone${gone:+, }${dir##*/} (code root $croot)"
    fi
  done <<RUNS
$runs
RUNS

  # After a compaction, only the run this session was driving is resumed: the in-progress run whose
  # session: matches this session's id, or — for a run that recorded none — the newest in-progress run
  # on this tree, if it was touched in the last 12 hours. Every other open run is only listed.
  if [ "$event" = compact ]; then
    fallback=""
    while IFS="$TAB" read -r dir mode phase updated status rsid; do
      [ -n "$dir" ] || continue
      [ "$status" = in-progress ] || continue
      [ "$rsid" != - ] || rsid=""
      if [ -n "$sid" ] && [ "$rsid" = "$sid" ]; then driving="$dir"; break; fi
      if [ -z "$fallback" ] && { [ -z "$rsid" ] || [ -z "$sid" ]; } \
         && [ -n "$(find "$dir/session-state.md" -mmin -720 2>/dev/null)" ]; then
        fallback="$dir"
      fi
    done <<RUNS
$mine
RUNS
    [ -n "$driving" ] || driving="$fallback"
  fi

  # Described first: the run being resumed, then in-progress runs, then paused ones (each newest first).
  ordered=""
  for pass in driving in-progress other; do
    while IFS="$TAB" read -r dir mode phase updated status rsid; do
      [ -n "$dir" ] || continue
      case "$pass" in
        driving)     [ "$dir" = "$driving" ] || continue ;;
        in-progress) [ "$dir" != "$driving" ] && [ "$status" = in-progress ] || continue ;;
        other)       [ "$dir" != "$driving" ] && [ "$status" != in-progress ] || continue ;;
      esac
      ordered="$ordered$dir$TAB$mode$TAB$phase$TAB$updated$TAB$status$TAB$rsid$NL"
    done <<RUNS
$mine
RUNS
  done

  shown=0; more=""; n_more=0
  while IFS="$TAB" read -r dir mode phase updated status rsid; do
    [ -n "$dir" ] || continue
    name="${dir##*/}"
    if [ "$shown" -ge 5 ]; then
      n_more=$((n_more + 1))
      [ "$n_more" -gt 5 ] || more="$more${more:+, }$name ($status)"
      continue
    fi
    shown=$((shown + 1))
    [ "$phase" != - ] || phase=""
    [ "$updated" != - ] || updated=""
    [ "$rsid" != - ] || rsid=""
    skill="$(mode_skill "$mode")"
    runflag=""
    [ "$here_n" -le 1 ] || runflag=" Several runs are open on this tree: pass --run $name to every council command for this one."
    if [ "$status" = paused ]; then
      say "- PAUSED COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}). Resume it only when the user asks: council run resume --run $name, then re-invoke the $skill skill and read its session-state.md."
    elif [ "$event" = compact ] && [ "$dir" = "$driving" ]; then
      case "$phase" in
        build) redo="re-read its build loop and the build log" ;;    # a build replaces the stages between Prepare and Challenge
        *)     redo="re-read the doctrine for that phase" ;;
      esac
      seats="$(seat_summary "$dir")"
      say "- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}). Re-invoke the $skill skill (it loads context-core), read $dir/session-state.md (and ask.md, if present), $redo, and continue from there.${seats:+ Seats — $seats.} Do not restart, do not re-dispatch seats that are running or done (wait for their notifications), do not skip the completeness check.$runflag"
    elif [ "$event" = compact ]; then
      say "- Also open on this working tree, not this session's run: $name ($skill, phase ${phase:-?}). Leave it unless the user asks."
    elif [ -n "$rsid" ] && [ "$rsid" != "$sid" ] && [ -n "$(find "$dir" -type f -mmin -120 2>/dev/null | head -n 1)" ]; then
      # Another session id touched it in the last 2 hours: that session may still be driving it.
      if [ "$event" = clear ]; then
        seats="$(seat_summary "$dir")"
        say "- COUNCIL RUN OPEN, updated in the last 2 hours by another session id: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}).${seats:+ Seats — $seats.} If this window was driving it before /clear, carry on: council run resume --run $name, then re-invoke the $skill skill and read its session-state.md; seats marked running are still working, so wait for their notifications. Otherwise it may still be live in another session: leave it, and don't resume it, re-dispatch its seats or close it unless the user says so.$runflag"
      else
        say "- COUNCIL RUN OPEN, updated in the last 2 hours by another session: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}). It may still be running in that session: leave it, and don't resume it, re-dispatch its seats or close it. If the user says that session has ended: council run resume --run $name, then re-invoke the $skill skill.$runflag"
      fi
    else
      if [ "$event" = clear ]; then
        seats="$(seat_summary "$dir")"
      else
        seats="$(seat_summary "$dir" "were running when that session ended (they are gone — re-dispatch each once if you resume)")"
      fi
      say "- UNFINISHED COUNCIL RUN: $dir ($skill, phase: ${phase:-unknown}, updated: ${updated:-unknown}).${seats:+ Seats — $seats.} Before new council work, ask the user whether to resume it (council run resume --run $name, then re-invoke the $skill skill and read its session-state.md) or close it (council run close --run $name --status abandoned).$runflag"
    fi
  done <<RUNS
$ordered
RUNS
  if [ "$n_more" -gt 0 ]; then
    [ "$n_more" -le 5 ] || more="$more, …"
    say "- And $n_more more open on this working tree: $more — council run status lists them all. Leave them unless the user asks."
  fi

  if [ "$n_other" -gt 5 ]; then others="$others; and $((n_other - 5)) more"; fi
  if [ "$n_other" -eq 1 ]; then
    say "- Another council run is open in a different working tree: $others. Leave it alone."
  elif [ "$n_other" -gt 1 ]; then
    say "- $n_other council runs are open in different working trees: $others. Leave them alone (council run status lists them)."
  fi
  if [ "$n_gone" -gt 5 ]; then gone="$gone, and $((n_gone - 5)) more"; fi
  if [ "$n_gone" -eq 1 ]; then
    say "- A council run was left open in a working tree that no longer exists: $gone. Ask the user, then close it: council run close --run ${gone%% *} --status abandoned."
  elif [ "$n_gone" -gt 1 ]; then
    say "- $n_gone council runs were left open in a working tree that no longer exists: $gone. Ask the user, then close each: council run close --run <name> --status abandoned."
  fi
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
            rsid="$(field session "$state")"
            final=""                           # an older run's final deliverable: it is probably finished
            for f in "$run"/FINAL-*.md "$run"/PLAN-*.md "$run"/*implementation-log*; do
              if [ -f "$f" ]; then final="${f##*/}"; break; fi
            done
            if [ "$event" = compact ]; then
              # The same rule as for runs under runs/: this session's by session id, or — with none
              # recorded, nothing else resumed and no final deliverable — touched in the last 12 hours.
              if { [ -n "$sid" ] && [ "$rsid" = "$sid" ]; } \
                 || { [ -z "$rsid" ] && [ -z "$driving" ] && [ -z "$final" ] \
                      && [ -n "$(find "$state" -mmin -720 2>/dev/null)" ]; }; then
                say "- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}). Re-invoke that mode's skill, read $state, and resume at that phase. Do not restart, do not re-dispatch seats whose files exist, do not skip the completeness check."
              else
                say "- Also open (an older run layout), not this session's run: $run (${mode:-unknown mode}, phase: ${phase:-unknown})${final:+ — it holds $final, so it is probably finished}. Leave it unless the user asks."
              fi
            elif [ -n "$final" ]; then
              say "- UNFINISHED COUNCIL RUN (an older run layout): $run (${mode:-unknown mode}, phase: ${phase:-unknown}, updated: ${updated:-unknown}). It holds its final deliverable ($final), so it is probably finished: ask the user, then close it as complete (council run close --run \"$run\" --status complete)."
            else
              say "- UNFINISHED COUNCIL RUN: $run (${mode:-unknown mode}, phase: ${phase:-unknown}, updated: ${updated:-unknown}). Before new council work, ask the user whether to resume it (council run resume --run \"$run\", then re-invoke that mode's skill) or close it (council run close --run \"$run\" --status abandoned)."
            fi
            ;;
        esac
      fi
      ;;
  esac
fi

exit 0
