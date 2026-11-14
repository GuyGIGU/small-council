"""council gate <name> [-- '<command>'] | gate --all [--at grounding|verify] | gate <name> --invalid "<why>":
run one check, or the project's configured set, and record each result in the run (gate_run). One call per run
at a time (gate_lock); a build's gate result is its repair record (gate_repair)."""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from council.commands import cli, closed, gate_lock, gate_output, gate_repair, gate_run, resolve, shell
from council.records import config, gate_notes, gate_table, gates, state_write, verdicts
from council.records import home as where

USAGE = "usage: council gate <name> [-- '<command>']   |   council gate --all [--at grounding|verify]"
PROOF_ID = re.compile(r"[0-9A-Za-z_-]+")
SEAT = re.compile(r"[0-9A-Za-z._-]+")
NEEDS_ASK = re.compile(r"credential|secret|token|password|api.key|apikey|hardware|device", re.DOTALL)
SAFE = ("none", "writes the tree", "writes files", "network", "-", "—")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "gate", "all", "at", "proof", "timeout", "invalid", "wait", "seat", "rerun", "--")
    every, command = args.value("all") == "1", given(args.after)
    if every:
        cli.no_words("gate --all", words)
        if command:
            raise cli.Refusal("gate --all runs the configured gates — it takes no command after --")
    elif args.value("at"):
        raise cli.Refusal("--at works only with gate --all")
    elif args.value("rerun"):
        raise cli.Refusal("--rerun works only with gate --all: a gate run by name always runs (council gate %s)"
                          % gate_run.qname(" ".join(words) or "<name>"))
    _seat(args)
    try:
        return shell.ran(_gate(args, words, command))
    finally:
        gate_lock.release()


def _seat(args: cli.Args) -> None:
    """--seat <slug>: the seat running this gate in its own tree (a builder in its worktree)."""
    seat = args.value("seat")
    if not seat:
        return
    if not SEAT.fullmatch(seat) or not seat.isascii():
        raise cli.Refusal("--seat takes the seat's slug — letters, digits, dots, dashes and underscores, as the run "
                          "plan names it: council gate <name> --seat builder-1 (got '%s')" % seat)
    if args.value("invalid"):
        raise cli.Refusal('--invalid marks a record and runs nothing, so it takes no --seat: council gate <name> '
                          '--invalid "<why>"')


def given(after: list[str]) -> str:
    """The command after --: one word is a shell command as written; several are kept intact, each quoted."""
    return after[0] if len(after) == 1 else shell.quote(after)


def _gate(args: cli.Args, words: list[str], command: str) -> int:
    run = resolve.run_folder(args)
    closed.refuse(run, "its checks are on record; run them in a new run")
    timeout = None
    if args.value("timeout"):
        timeout = config.limit_seconds(args.value("timeout"))
        if timeout is None:
            raise cli.Refusal("--timeout takes a time, in seconds or with m or h: 900, 15m (got '%s')"
                              % args.value("timeout"))
    wait = args.value("wait")
    limit = wait[1:] if wait.startswith("=") else str(gate_lock.WAIT_LIMIT)
    if args.value("invalid"):
        invalid(run.as_posix(), " ".join(words), args, bool(command) or timeout is not None, limit)
        return 0
    home = where.council_home()
    call = gate_run.Call(run.as_posix(), home, _top(run, args.value("seat")), bool(command), timeout,
                         args.value("proof"), False, args.value("seat") or "chair", args.value("rerun") == "1")
    mode = resolve.field(run, "mode")
    if call.proof:
        _proof(args, mode, " ".join(words))
    if wait.startswith("=") and (not limit.isdigit() or not limit.isascii() or limit == "0"):
        raise cli.Refusal("--wait=<seconds> takes a whole number of seconds above 0 (got '%s'); plain --wait waits "
                          "up to 20 minutes" % limit)
    state_write.clear_waiting(run)          # the run moves on: a wait it recorded is over
    if args.value("all") == "1":
        from council.commands import gate_set
        return gate_set.run_all(call, args.value("at"), mode, (bool(wait), limit))
    return one(call, " ".join(words), command, mode, (bool(wait), limit))


def _top(run: Path, seat: str) -> str:
    """Where the gate runs: the run's code root; for a seat's own run (--seat), the working tree it calls from."""
    root = resolve.field(run, "code-root") or where.this_tree()
    if not seat:
        return root
    tree = where.this_tree()
    if tree != root:
        cli.say("note: %s's gate runs in %s, the working tree it is called from, not the run's code root (%s)"
                % (seat, tree, root))
    return tree


def _proof(args: cli.Args, mode: str, name: str) -> None:
    if args.value("all") == "1" or args.value("at"):
        raise cli.Refusal("--proof takes one build before-<n> or after-<n> gate, not a gate set")
    if mode != "council-implement":
        raise cli.Refusal("--proof belongs to a council-implement run")
    if args.value("proof") not in ("change", "preserve"):
        raise cli.Refusal("--proof takes change or preserve")
    if not name.startswith(("before-", "after-")):
        raise cli.Refusal("--proof takes a before-<n> or after-<n> gate; regression proofs always show a change")
    proof_id = name.split("-", 1)[1]
    if not PROOF_ID.fullmatch(proof_id) or not proof_id.isascii():
        raise cli.Refusal("--proof needs a task id in before-<id> or after-<id>: a number, or a slug of letters, "
                          "digits, dashes and underscores (got '%s')" % proof_id)


def safe(side: str, needs: str, has_side: bool) -> bool:
    """May `gate --all` run this gate unasked? Only if the table has a Side effects column, every side effect is
    on the safe list (none, writes the tree, network) and Needs names no credentials or hardware. A command's
    wording is no evidence that it is safe."""
    if NEEDS_ASK.search(needs.translate(gate_output.ASCII_LOWER)) or not has_side or side == "-":
        return False
    items = [item.strip(" \t\n\v\f\r") for item in side.split(",")]
    return all(item.translate(gate_output.ASCII_LOWER) in SAFE for item in items if item)


def one(call: gate_run.Call, name: str, command: str, mode: str, wait: tuple[bool, str]) -> int:
    """One gate, by name: the config's command, or the one given after --."""
    if not name:
        raise cli.Refusal(USAGE)
    trail = ""
    if mode == "council-implement":      # three failed repair attempts stop it until the user's go is on record
        trail = gate_repair.trail(call.run, name)
        if trail.startswith("stop\t"):
            task = trail.split("\t")[1]
            raise cli.Refusal("gate %s is stopped: it failed three repair attempts for task %s (council repair show "
                              "%s). Change no more code for it; tell the user what failed and what is left, and ask "
                              "how to go on. Only on their go: council repair allow %s --user-said \"<their words>\" "
                              "— then it runs again" % (name, task, task, gate_run.qname(name)))
    gate_lock.take(call.run, *wait)
    if not command:
        command = _configured(call.home, name)
    for note in gate_notes.notes(command):
        cli.say("note: this gate command " + note)
    if gate_notes.backslash(command):
        cli.say("note: this gate command " + gate_notes.BACKSLASH)
    if gate_notes.winswitch(command):
        cli.say("note: this gate command " + gate_notes.WINSWITCH)
    configured = any(row.name == name and row.command == command for row in gate_table.gates(call.home))
    result = gate_run.run_gate(call, name, command, configured)
    gate_repair.record(call.run, name, result.code, trail, result.same)    # in a build, said last
    return result.code


def _configured(home: str, name: str) -> str:
    """The config's command for a gate run by name, its side effects said when it is not safe to run unasked."""
    row = next((gate for gate in gate_table.gates(home) if gate.name == name), None)
    if row is None:
        raise cli.Refusal("no gate named '%s' in council.config.md — pass the command after --" % name)
    if row.command == "-":
        raise cli.Refusal("gate '%s' has an empty Command cell in council.config.md — fill it in, or pass its "
                          "command: council gate %s -- '<command>'" % (name, gate_run.qname(name)))
    if row.ran == "not":
        cli.say("note: the config marks this gate not runnable here (%s)" % row.checked)
    if not safe(row.side, row.needs, row.has_side):
        extra = "" if row.needs == "-" else " · needs: " + row.needs
        if not row.has_side:
            cli.say("note: the Gates table has no Side effects column, so this gate's side effects are unknown%s — "
                    "run it only with the user's go-ahead" % extra)
        elif row.side == "-":
            cli.say("note: this gate's side effects aren't recorded%s — run it only with the user's go-ahead" % extra)
        else:
            cli.say("note: this gate has side effects (%s)%s — run it only with the user's go-ahead"
                    % (row.side, extra))
    return row.command


def invalid(run: str, name: str, args: cli.Args, runs_something: bool, limit: str) -> None:
    """council gate <name> --invalid "<why>": a red that proves nothing, said so on its record rather than left
    to count as a red. Nothing runs. The verdict gains "invalid", the output a closing line, a copy goes to
    gates/invalid/, and an event records it; running the gate again replaces it."""
    if args.value("all") == "1":
        raise cli.Refusal("--invalid marks one gate's record, not a set")
    if runs_something or args.value("proof"):
        raise cli.Refusal('--invalid runs nothing: council gate <name> --invalid "<why>" takes no command, --proof or '
                          "--timeout")
    if not name:
        raise cli.Refusal('usage: council gate <name> --invalid "<why the red proves nothing>"')
    why = re.sub("[\t\r\n]", " ", args.value("invalid")).strip(" \t\n\v\f\r")
    if not why:
        raise cli.Refusal("--invalid needs the reason, in words: --invalid \"the new test didn't compile\"")
    slug = gates.slug(name)
    base = "%s/gates/%s" % (run, slug)
    code = _markable(name, slug, base + ".json")
    gate_lock.take(run, args.value("wait") != "", limit)
    keep = _mark(run, slug, base, why)
    gate_run.event(run, name, "invalid", "exit=%s;why=%s" % (code, why.replace(";", ",")),
                   "the gate is marked invalid, but its event was not recorded")
    if name.startswith(("before-", "regress-")):
        cli.say("gate %s: marked invalid (%s) — its red proves nothing, so task %s has no proof yet. Fix the check, "
                "read it back, compile it with the cheapest check, then: council gate %s -- '<the check>'"
                % (name, why, name.split("-", 1)[1], gate_run.qname(name)))
    else:
        cli.say("gate %s: marked invalid (%s) — its red proves nothing; fix it and run it again" % (name, why))
    cli.say("    kept as gates/invalid/%s" % Path(keep).name)


def _markable(name: str, slug: str, verdict: str) -> str:
    """The exit code a red record holds; a refusal when there is none to mark."""
    if not os.path.isfile(verdict):
        raise cli.Refusal("gate %s has no record in this run (gates/%s.json) — nothing to mark" % (name, slug))
    code = verdicts.number(verdict, "exit")
    if not code:
        raise cli.Refusal("gate %s's record can't be read (gates/%s.json) — nothing was marked" % (name, slug))
    if int(code) == 0:
        raise cli.Refusal("gate %s passed (exit 0) — --invalid marks a red that proves nothing; a check that passed "
                          "for the wrong reason needs a better check, run again" % name)
    if '"invalid": "' in gate_output.text(verdict):
        raise cli.Refusal("gate %s's record is already marked invalid — run it again once the check is fixed" % name)
    return code


def _mark(run: str, slug: str, base: str, why: str) -> str:
    """Write the mark; the copy kept under gates/invalid/ (its .json path)."""
    folder = run + "/gates/invalid"
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        raise cli.Refusal("cannot write %s" % folder) from None
    k = 1
    while os.path.isfile("%s/%s-%d.json" % (folder, slug, k)):
        k += 1
    verdict, tail = base + ".json", ', "invalid": "%s"}' % gate_run.json_esc(why)
    lines = gate_output.lines(gate_output.text(verdict))
    try:
        with open(verdict + ".tmp", "wb") as handle:
            handle.write("".join(re.sub(r"[}][ \t\r]*\Z", "", line, count=1) + tail + "\n" for line in lines)
                         .encode("utf-8", "surrogateescape"))
        os.replace(verdict + ".tmp", verdict)
    except OSError:
        if os.path.exists(verdict + ".tmp"):
            os.remove(verdict + ".tmp")
        raise cli.Refusal("cannot update %s" % verdict) from None
    with open(base + ".txt", "ab") as handle:
        handle.write(("\ncouncil: marked invalid %s — %s. This red proves nothing; run the check again once it is "
                      "fixed.\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), why)).encode("utf-8", "surrogateescape"))
    keep = "%s/%s-%d" % (folder, slug, k)
    shutil.copyfile(verdict, keep + ".json")
    if os.path.isfile(base + ".txt"):
        shutil.copyfile(base + ".txt", keep + ".txt")
    return keep + ".json"
