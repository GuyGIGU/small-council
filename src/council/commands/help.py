"""council help and council version; council, -h and --help print the same command list."""
from __future__ import annotations

import sys

from council.commands import cli

COUNCIL_VERSION = "0.23.0"   # .claude-plugin/plugin.json and the newest CHANGELOG release say the same

USAGE = """\
council — the Small Council's helper (bash + git)

  council home                           where the council lives (.council/ of the main checkout)
  council home rule                      the Edit permission rule for that folder, in the form Claude Code
                                         matches (on Windows the drive as //c/…, never //C:/…)
  council sharing [just-me|team]         who sees the council: team (the default — .council/ is committed and
                                         CLAUDE.md points at it) or just me (git ignores it through its own
                                         exclude list, and the CLAUDE.md note goes); no word shows what's left
  council pushes [check git push|gh pr create]  the push freeze · check: the bash gate's decision (exit 2 while held)
  council run open <mode> [--alongside] [--session=ID]
                                         open a run for a mode, e.g. council-review; prints its folder
  council run status [--all]             open runs, this tree's first (the last 20 with --all)
  council run close [--status complete|abandoned|paused]
                                         close the run (complete only once it came through Deliver);
                                         then its audit's FAIL lines and a reminder to show the user
                                         its closing card
  council run resume [--run <folder>]    carry on with an open run (a paused one too) in this session:
                                         in progress again, this session recorded as its driver
  council run plan [check|show]          validate the run plan (Full size only once a decision of the
                                         user's is on record) · show its decisions in plain language
  council run events [show|check|repair] inspect, validate or mend (a torn last line) the run's event stream
  council run audit [--transcript <session .jsonl>]
                                         after close: check the run against the method from its
                                         records, and with the session transcript what the Chair
                                         showed and ran — pass, warn or FAIL per item, exit 1 on a
                                         FAIL; reads only (optional Python 3.8+)
  council state [key=value …]            show or update the run's session-state header; phase= takes a
                                         stage name and records its next step (skip="<why>" to pass over
                                         a stage the mode must enter); waiting="<question>" prints
                                         the alert reminder; decision="<the user's words>" goes under
                                         Decisions so far
  council seat <slug> <state> [agent=ID] [tokens=N] [agents=N] [note=TEXT]
                                         record a worker: queued|running|done|failed|blocked|skipped;
                                         tokens= and agents= (a Workflow's agent count) come with the
                                         finished run's usage report, once per agent run; the run's first
                                         dispatch also prints a reminder to show the user the run's status;
                                         in a build, a task's third check (verify-<n>c, or verify-<n>
                                         again) starts only after a diagnose-<n> seat or the user's go
  council cap                            agent runs used against the cap, tokens against the ceiling, the
                                         user's go on record, and whether new agents are stopped now
  council cap allow <n> --user-said "…"  the user's go past the cap or ceiling, in their words: n more
                                         agent runs may start before the stop holds again
  council run turn-end --session ID      the turn-end hook's decision (hooks/turn-end.sh): records that
                                         a run this session drives waits on the user, and once per wait
                                         exits 2 with the owner's alert to send
  council cap check [--session ID] [<tool> [type=<agent type>] [seat=<slug>] [run=<folder>] [file=<slug>]]
                                         the agent gate's decision (hooks/agent-gate.sh): exit 2 and the
                                         reason while a run this session may be driving is stopped; with
                                         the tool about to start, a pass counts it as an agent start; a
                                         council-worker or council-verifier (type=) is refused with no open
                                         run for it, or for a seat (seat=, else the file= it writes) its
                                         plan doesn't select
  council correct <seat> tokens=N agents=N [unrecorded=yes] evidence="<source>"
                                         lay an exact, evidence-backed figure over a seat's record
                                         (or add an agent run the record missed); seats.tsv keeps
                                         the original, corrections.jsonl the evidence
  council index [--base REF]             change index → <run>/index.md (hunks, symbols, callers, tests)
  council evidence build|show|check       index claims, provenance, states and verifier links from
                                         synthesis.md and verify-*.md into run-local claims.jsonl
  council repair record <task> <gate>     snapshot one completed gate attempt, classify its failure
  council repair show|check [task]        inspect bounded repair advice or check saved proof
  council repair allow <gate> --user-said "…"
                                         the user's go, in their words, for a gate stopped at three
                                         failed repair attempts: it may run again
  council gate <name> [-- '<command>']   run one gate — quote the whole command, so && and quotes stay
                                         inside it; output, exit code and the tree it ran on → <run>/gates/
  council gate before-<id>|after-<id> --proof change|preserve -- '<command>'   (id: a task number or a slug)
  council gate --wait[=<seconds>] <name>  queue behind a running gate call (20 minutes unless given), then run
                                         build proof: a failing then passing check, or an invariant
                                         passing on both versions (declare preserve before the edit)
  council gate --all [--at grounding|verify] [--rerun]   the configured gates, one call per run at a time
                                         (a second: exit 2); one green on this same tree runs only with --rerun
  council gate … --seat <slug>           a seat's own run (a builder's), in the working tree it calls from
  council gate … --timeout <time>        this call's time limit per gate (900, 15m). Without it: the
                                         largest of 3× the gate's green baseline, the config's
                                         "- gate time limit:" and 120 s; with neither, 9 min for a
                                         command after --, 30 min for a configured gate. Past it the gate
                                         and all it started are stopped: exit 124, TIMED OUT — no proof
  council gate <name> --invalid "<why>"  mark a red that proves nothing (the new check didn't compile, the
                                         probe was broken); council check reads that proof as no proof yet
  council gates                          list the configured gates
  council changed [--glob '<pat>'] [--each] -- <cmd>
                                         run <cmd> over just the files this change touches (0 when none);
                                         inside a gate, since the run's recorded base
  council collect                        check every seat file: the brief's, a war room's debate.md's, and
                                         any other .md in seats/ (a Workflow's agents skip the seat hook)
  council check [file …] [--base REF]    check citations and origin (default: synthesis.md)
  council patch save <task> [<report>]   a build round: its report's head checked against its diff, then both
                                         saved → <run>/patches/ · patch show <task>: the task's rounds
  council map status                     how far the map is behind HEAD, by area
  council map touch <dir>="<line>" …     the user's line for each top-level area, under today's
                                         ## Changes in the map; map-commit moves to HEAD once every
                                         area changed since it has a line
  council fingerprint [check]            the stack's fingerprint; check compares it with the config
  council memory [index|check|tidy]      memory's one-line index · stale anchors and failure evidence · the
                                         merges and retirements reading alone can find, numbered (writes nothing)
  council memory select [path|slug …]    scoped rules and observed failures with provenance
  council memory propose claim|repair <id> [--scope …]
                                         draft an observed failure from the run's verified record
                                         under ## Proposed (a claim refuted or miscited by the
                                         verifier; a build task's failed gate trail, --scope needed)
  council memory accept|reject F-<n> --user-said "…"
                                         the user's answer, in their words: file it under Observed
                                         Failures, or move it to ## Rejected
  council prior [path …]                 earlier council work on these paths (default: the index)
  council ask save [slug]                file the run's ask.md — the user's words — under .council/asks/;
                                         secret-looking strings are redacted; records ask= in the state
  council ledger [N]                     each seat's record over the last N completed runs (default 10)
  council ledger advice [N] [--json]     how much each seat's record can support over the last N runs
                                         (default 20), and advice only past the bar (optional Python 3.8+)
  council route recommend --task TEXT [--risk low|medium|high] [--complexity 1..10]
                         [--uncertainty low|medium|high] [--surface NAME ...]
                         [--agent-cap N] [--budget-tokens N] [--classic] [--mode review|plan|implement|research|postgame]
                                         advisory TSV recommendation; does not open or alter a run
  council status [--widget [--preview] | --json | --line]
                                         the run in plain words: what is happening, whether it moves,
                                         what needs the user, where the evidence is; --widget prints
                                         a snapshot card for a chat widget host; --line gives a short
                                         notification sentence (optional Python 3.8+)
  council doctor                         drift scan; every finding comes with a fix

Run-scoped commands act on the one in-progress run on this working tree; otherwise pass --run <folder>
(a path, or a folder name under runs/). Every flag also takes the --flag=value form. A command refuses
any word or flag it doesn't take.
"""  # noqa: E501


def main(args: cli.Args, words: list[str]) -> int:
    command = args.words[0]
    cli.takes_flags(args, command)
    cli.no_words(command, words)
    if command == "version":
        cli.say("council " + COUNCIL_VERSION)
        return 0
    return usage()


def usage() -> int:
    sys.stdout.write(USAGE)
    return 0
