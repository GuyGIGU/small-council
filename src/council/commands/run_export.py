"""council run export --anon <run> <dest> [--transcript <session .jsonl>]: a copy of a run folder that holds what
`council run audit` reads and nothing else, anonymised (records/anon.py), so a run can be replayed elsewhere: a
fixture of evals/run_replay.py, or a run sent with a bug report.

Kept, with their times (the audit reads the order): session-state.md, events.tsv, run-plan.tsv, seats.tsv,
usage.tsv, agent-starts.tsv, cap-allowances.tsv, corrections.jsonl, claims.jsonl, and the session transcript's
part for this run as transcript.jsonl (run_export_log.py). Absolute paths become placeholders and session ids
stand-ins; the user's words (decisions, the go past a cap) and the Chair's notes become stand-ins of the same
shape. synthesis.md, verify-<n>.md and audit.md are kept as a line saying their contents were left out, with
their times (the audit reads only those, and synthesis.md's `from: chair`). Nothing else is copied: no ask.md,
no seat file, no brief, no gate output, no code.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from council.commands import audit, audit_checks, cli, resolve, run_export_log
from council.commands.help import USAGE as HELP
from council.records import anon as anonymous
from council.records import audit_file, cells, events, paths
from council.records import home as where
from council.records import seats as seat_files
from council.records import state as run_state
from council.records import plan as run_plan
from council.records.run_files import CLAIMS, SYNTHESIS

USAGE = "usage: council run export --anon <run> <dest> [--transcript <session .jsonl>]"
LEFT_OUT = "(contents left out by council run export --anon)\n"
KEPT_KEYS = ("status", "mode", "phase", "updated", "opened", "closed", "plan-schema", "events-schema", "actual",
             "ask-saved", "start-head", "waiting")
PATH_KEYS = ("deliverable", "ask", "input")
Swap = Callable[[str], str]


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run export", "anon", "transcript")
    if len(words) != 2:
        raise cli.Refusal(USAGE)
    if not args.value("anon"):
        raise cli.Refusal("run export copies a run only anonymised — pass --anon: " + USAGE[len("usage: "):])
    home = where.council_home()
    run = Path(where.native(resolve.run_path(words[0], home)))
    if not paths.is_run(run):
        raise cli.Refusal("not a run folder: %s — name a run folder, or a run's name under %s/runs (council run "
                          "status --all lists them)" % (words[0], home))
    dest = Path(where.native(words[1])).absolute()
    if paths.contained(dest, run):
        raise cli.Refusal("the copy can't go inside the run it copies (%s) — name a folder outside it" % run.as_posix())
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise cli.Refusal("%s is not an empty folder — name a new or empty one: the export never writes over files"
                          % dest.as_posix())
    log = _transcript(args, run)
    return export(run, dest, log)


def _transcript(args: cli.Args, run: Path) -> Path | None:
    given = args.value("transcript")
    if not given:
        return audit.find_transcript(resolve.field(run, "session").strip())
    log = Path(where.native(given))
    if not log.is_file():
        raise cli.Refusal("no such transcript file: %s — pass the session's .jsonl, or leave --transcript out to "
                          "look it up by the run's session id" % given)
    return log


def export(run: Path, dest: Path, log: Path | None) -> int:
    """Write the anonymised copy and say what it holds."""
    code_root = resolve.field(run, "code-root").strip()
    project = code_root if where.absolute(code_root) else str(Path(run).resolve().parents[2])
    anon = anonymous.Anon({"project": project, "plugin": where.plugin_root(), "home": str(Path.home())})
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in files(run, anon).items():
        _write(dest / name, text, run / name)
        written.append(name)
    for name in [SYNTHESIS, audit_file.NAME] + sorted(p.name for p in run.glob("verify-*.md")):
        if (run / name).is_file():
            marker = "from: chair\n" if name == SYNTHESIS and re.search(
                r"from:[ \t]*chair\b", paths.run_text(run, name)) else ""
            _write(dest / name, LEFT_OUT + marker, run / name)
            written.append(name)
    said = "no session transcript: pass --transcript <session .jsonl> to carry the Chair's steps"
    if log is not None:
        lines = run_export_log.lines(log, audit_checks.Run(run), anon, vocabulary(run))
        _write(dest / run_export_log.NAME, "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
               None)
        written.append(run_export_log.NAME)
        said = "%s: %d line(s) of the session's part for this run" % (run_export_log.NAME, len(lines))
    cli.say("exported %s to %s — %d file(s), anonymised: %s" % (run.name, dest.as_posix(), len(written),
                                                                 ", ".join(written)))
    cli.say(said)
    return 0


def _write(path: Path, text: str, source: Path | None) -> None:
    with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    if source is not None and source.is_file():
        stamp = source.stat()
        os.utime(str(path), (stamp.st_atime, stamp.st_mtime))


def files(run: Path, anon: anonymous.Anon) -> dict[str, str]:
    """Each kept run file's anonymised text, by name; a file the run doesn't hold is left out."""
    shaped = anonymous.shape
    found = {paths.STATE: state(run, anon),
             events.NAME: tsv(run, events.NAME, {"detail": lambda cell: detail(cell, anon)}),
             run_plan.NAME: tsv(run, run_plan.NAME, {"reason": shaped}),
             seat_files.SEATS: tsv(run, seat_files.SEATS, {"note": note}),
             seat_files.USAGE: tsv(run, seat_files.USAGE, {}),
             seat_files.STARTS: tsv(run, seat_files.STARTS, {"session": anon.session}),
             seat_files.ALLOWANCES: tsv(run, seat_files.ALLOWANCES, {"said": shaped}),
             seat_files.CORRECTIONS: jsonl(run, seat_files.CORRECTIONS, {"evidence": shaped}),
             CLAIMS: jsonl(run, CLAIMS, {"still_cut": shaped}, ("id", "disposition", "verdict", "still_cut"))}
    return {name: text for name, text in found.items() if text}


def state(run: Path, anon: anonymous.Anon) -> str:
    """session-state.md: the helper's own fields as they are, paths as placeholders, the session as its stand-in,
    any other field, the decisions and the notes as stand-ins (headings and each decision's time kept)."""
    out, header = [], True
    for line in cells.lines_of(run_state.text(run)):
        header = header and not line.startswith("## ")
        key, sep, value = line.partition(":")
        if line.startswith("#") or not line.strip():
            out.append(line)
        elif header and sep and run_state.KEY.fullmatch(key):
            value = value.strip()
            kept = value if key in KEPT_KEYS else anon.session(value) if key == "session" else \
                anon.paths(value) if key == "code-root" else _path(value, anon) if key in PATH_KEYS else \
                anonymous.shape(value)
            out.append("%s: %s" % (key, kept))
        else:
            lead = re.match(r"^(- (?:[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}: )?(?:task [0-9]+: )?)?(.*)$", line)
            out.append((lead.group(1) or "") + anonymous.shape(lead.group(2)))
    return "\n".join(out) + "\n" if out else ""


def _path(value: str, anon: anonymous.Anon) -> str:
    """A path field: placeholders for its root, its file name a stand-in (a slug can say what the work was)."""
    head, _, name = anon.paths(value).replace("\\", "/").rpartition("/")
    stem, dot, ext = name.rpartition(".")
    return (head + "/" if head else "") + (anonymous.shape(stem) + dot + ext if dot else anonymous.shape(name))


def note(cell: str) -> str:
    """A seat's note: its leading word (NEEDS:, BLOCKED:) kept, the rest a stand-in."""
    lead = re.match(r"^([A-Z]+:\s*)?(.*)$", cell)
    return (lead.group(1) or "") + anonymous.shape(lead.group(2))


def detail(cell: str, anon: anonymous.Anon) -> str:
    """An event's detail: the helper's keys and figures kept; a reason given (reason=, why=) a stand-in, a session
    (was=) its stand-in."""
    parts = []
    for part in cell.split(";"):
        key, sep, value = part.partition("=")
        value = anonymous.shape(value) if key in ("reason", "why") else anon.session(value) if key == "was" else value
        parts.append(key + sep + value)
    return ";".join(parts)


def tsv(run: Path, name: str, swaps: dict[str, Swap]) -> str:
    """A TSV run file with each named column's cells swapped; its header, comment lines and other cells as they are."""
    lines = [line for line in cells.lines_of(paths.run_text(run, name)) if line.strip()]
    rows = [line for line in lines if not line.startswith("#")]
    if not rows:
        return ""
    head = rows[0].split("\t")
    out = []
    for line in lines:
        if line.startswith("#") or line == rows[0]:
            out.append(line)
            continue
        found = line.split("\t")
        out.append("\t".join(swaps[head[n]](c) if n < len(head) and head[n] in swaps else c
                             for n, c in enumerate(found)))
    return "\n".join(out) + "\n"


def jsonl(run: Path, name: str, swaps: dict[str, Swap], only: tuple[str, ...] = ()) -> str:
    """A JSON-lines run file, each row cut to `only` (when given) and its named string fields swapped."""
    rows = cells.jsonl_rows(paths.run_text(run, name))
    out = []
    for row in rows:
        row = {k: v for k, v in row.items() if not only or k in only}
        out.append(json.dumps({k: swaps[k](v) if k in swaps and isinstance(v, str) else v for k, v in row.items()},
                              ensure_ascii=False))
    return "\n".join(out) + "\n" if out else ""


SHELL = ("bash", "sh", "cd", "tail", "head", "grep", "sed", "tee", "cat", "echo", "true", "false", "for", "in", "do",
         "done", "if", "then", "else", "elif", "fi", "case", "esac", "while", "until", "command", "which", "exec",
         "env", "nohup", "time", "exit", "set", "test", "council", "python", "python3", "git", "null", "dev")


def vocabulary(run: Path) -> frozenset[str]:
    """The words a command keeps as they are: the helper's own (its help text, the stages, the modes), the shell's,
    and this run's seat slugs, agent ids and gate names, which its files keep too."""
    modes = audit_checks.MODES
    found = set(re.findall(r"[a-z][a-z0-9-]*", HELP)) | set(SHELL) | set(audit_checks.STAGES) | {"build"}
    found |= set(modes) | {mode.split("-", 1)[1] for mode in modes}
    for row in seat_files.rows(run) + seat_files.usage_rows(run):
        found |= {row.get("slug", ""), row.get("agent", "")}
    found |= {e.get("subject", "") for e in events.records(run) if e.get("type") == "gate.finished"}
    return frozenset(w for w in found if w)
