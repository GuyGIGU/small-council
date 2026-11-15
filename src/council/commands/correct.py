"""council correct <seat> tokens= agents= [unrecorded=yes] evidence="…": a line per field in corrections.jsonl."""
from __future__ import annotations

import json
import re
from pathlib import Path

from council import clock
from council.commands import cli, event_note, resolve, seat
from council.records import ledger, seat_rows, seats

USAGE = ('usage: council correct <seat> tokens=<exact> agents=<exact> [unrecorded=yes] evidence="<where the figure '
         'comes from>"')
DROPPED = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "correct")
    if not words or not words[0]:
        raise cli.Refusal(USAGE)
    slug, got = words[0], _fields(words[0], words[1:])
    run = resolve.run_folder(args)
    event_note.writable(run)
    added, name = got["unrecorded"], run.name
    if added and not (got["agents"] and int(got["agents"]) > 0):
        _refuse("unrecorded=yes adds an agent run the record missed — give agents= (1 or more), and tokens= if the "
                "source shows its figure")
    if added and seat_rows.cell(run, slug, "slug"):
        _refuse("%s is already a seat of %s — correct it without unrecorded=yes" % (slug, name))
    if added and any(fix["added"] for (one, _), fix in seats.corrections(run).items() if one == slug):
        _refuse("%s was already added — name a second missed agent run with a new slug" % slug)
    if not added and not seat_rows.cell(run, slug, "slug"):
        _refuse("%s is not a seat of %s — only a recorded seat can be corrected (an agent run never recorded: "
                "unrecorded=yes)" % (slug, name))
    lock = Path(str(seats.path(run)) + ".lock")
    seat.under(lock, "seat lock unavailable: " + lock.as_posix(), lambda: _write(run, slug, got),
               "corrected, but the seat lock could not be released")
    if resolve.field(run, "status") == "complete":       # the ledger is a copy of the record: refresh it
        cli.say("ledger: %d seat row(s) of %s refreshed" % (ledger.record(run), name))
    return 0


def _refuse(why: str) -> None:
    raise cli.Refusal("correct: " + why)


def _count(value: str, digits: int, most: int, what: str, too_many: str) -> str:
    if not re.fullmatch("[0-9]+", value):
        _refuse("%s, got: %s" % (what, value))
    count = value.lstrip("0") or "0"
    if len(count) > digits or int(count) > most:
        _refuse(too_many % value)
    return count


def _fields(slug: str, words: list[str]) -> dict[str, str]:
    if not re.fullmatch("[A-Za-z0-9._-]+", slug):
        _refuse("bad seat slug: " + slug)
    got = {"tokens": "", "agents": "", "evidence": "", "unrecorded": ""}
    for word in words:
        key, equals, value = word.partition("=")
        if equals and key == "tokens":
            got[key] = _count(value, 12, 10 ** 12, "tokens= takes the exact whole number the evidence shows (no k, M "
                              "or commas)", "tokens=%s is more than any agent run reports")
        elif equals and key == "agents":
            got[key] = _count(value, 4, 1000, "agents= takes the exact number of agent runs, 0 or more",
                              "agents= takes a count from 0 to 1000, got: %s")
        elif equals and key == "evidence":
            flat = DROPPED.sub("", re.sub("[\t\r\n]", " ", value)).encode("utf-8", "surrogateescape")
            got[key] = flat[:1000].decode("utf-8", "surrogateescape")       # cut -c: bytes
        elif word == "unrecorded=yes":
            got["unrecorded"] = "1"
        else:
            _refuse("unknown field %s (use tokens=, agents=, unrecorded=yes, evidence=)" % word)
    tokens, agents = got["tokens"], got["agents"]
    if not tokens + agents:
        _refuse("give tokens=, agents= or both")
    if not re.search("[A-Za-z0-9]", got["evidence"]) or len(got["evidence"]) < 12:
        _refuse("evidence= must say where the exact figure comes from (a file and line, a message id) — a correction "
                "without its source is a guess")
    if tokens and tokens != "0" and int(tokens) < 1000:
        _refuse("tokens=%s is below any real agent run (1,000); a seat no agent ran for is tokens=0 agents=0" % tokens)
    if tokens == "0" and agents and int(agents) > 0:
        _refuse("tokens=0 with agents=%s — an agent run always costs something; if its figure is unknown, leave "
                "tokens= out" % agents)
    return got


def _write(run: Path, slug: str, got: dict[str, str]) -> None:
    """One line per field given, its event, and what changed, all under the seat lock."""
    file = seats.path(run, seats.CORRECTIONS)
    for field, column in (("tokens", "tokens"), ("agents", "agents")):
        to = got[field]
        if not to:
            continue
        was = seat_rows.cell(run, slug, column)
        line = {"schema": 1, "at": clock.now_utc(), "seat": slug, "field": field, "from": was, "to": int(to),
                **({"added": True} if got["unrecorded"] else {}), "evidence": got["evidence"]}
        try:
            with open(str(file), "ab") as stream:
                stream.write((json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
                             .encode("utf-8", "surrogateescape"))
        except OSError:
            raise cli.Refusal("cannot write " + file.as_posix()) from None
        event_note.need(run, "seat.usage_corrected", slug, field, "from=%s;to=%s" % (was, to),
                        "corrected, but the event could not be recorded")
        cli.say("corrected %s %s: %s → %s (seats.tsv keeps the original; corrections.jsonl keeps the evidence)"
                % (slug, field, was or "blank", to))
