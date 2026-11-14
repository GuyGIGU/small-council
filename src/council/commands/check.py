"""council check [<file> …] [--base <rev>]: every item's citation in the run's synthesis (or its seat files, or the
files named), each request part's quote of the user's words, a post-game's next tasks, a build's proofs and, on a
just-me council, the council ids a build left in shared text — into check.md, with a verdict line and exit 1 when
anything is broken. Redaction is still bash's (S8), so bin/council runs this twice: COUNCIL_REDACT=words writes
the request's words and the quotes for it to redact, then COUNCIL_REDACT=done checks against what it left."""
from __future__ import annotations

import contextlib
import os
import re
import time
from collections import Counter
from pathlib import Path

from council.commands import check_proofs, cite_check, cite_origin, cli, event_note, gate_output, hygiene, resolve
from council.records import citations, quotes, request, run_files, seat_files
from council.records import home as where
from council.records import sharing as shared

STAGE = "COUNCIL_REDACT"
REQUEST = ".request.txt"
IMPLEMENT, POSTGAME = "council-implement", "council-postgame"
REDACT_IT = "SECRET (it holds a secret-looking string — quote the redacted words the filed request has)"
KEPT = re.compile(r"(^|[^a-z])(kept|cut)([^a-z]|$)")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "check", "base")
    for word in words:
        if not os.path.isfile(where.native(word)):
            raise cli.Refusal("check: no such file: %s" % word)
    stage = os.environ.get(STAGE, "")
    if stage not in ("words", "done"):
        raise cli.Refusal("check redacts the request's words in bin/council before it checks them — run: council "
                          "check")
    run = resolve.run_folder(args)
    mode = resolve.field(run, "mode")
    files = chosen(run, words, mode)
    if stage == "words":
        return to_redact(run, files, mode)
    return Check(run, args, mode).every(files)


def chosen(run: Path, words: list[str], mode: str) -> list[str]:
    """The files named; else synthesis.md, else every seat file (in a build, not a diagnosis: it cites the code
    before its fix, lines that moved on)."""
    if words:
        return words
    folder = run.as_posix()
    if (run / run_files.SYNTHESIS).is_file():
        return [folder + "/" + run_files.SYNTHESIS]
    found = [folder + "/seats/" + name for name in seat_files.listed(run / "seats", "*.md")]
    return [path for path in found if not (mode == IMPLEMENT and path.rsplit("/", 1)[-1].startswith("diagnose-"))]


def _write(path: Path, lines: list[str]) -> None:
    path.write_bytes("".join(line + "\n" for line in lines).encode("utf-8", "surrogateescape"))


def to_redact(run: Path, files: list[str], mode: str) -> int:
    """The first pass: the user's own words (ask.md and the filed request, from "## In your words" on) in
    .request.txt.raw, and each item quote's words, one a line, in .request.txt.quotes; the run folder on stdout."""
    said = []
    for path in (run / request.ASK, request.filed(run)):
        if path is not None and os.path.isfile(where.native(str(path))):
            said += request.in_your_words("\n".join(quotes.file_lines(where.native(str(path)))))
    _write(run / (REQUEST + ".raw"), said)
    found = [quote.words for path in files if os.path.isfile(where.native(path))
             for quote in quotes.item_quotes(where.native(path), "", mode) if quote.words]
    _write(run / (REQUEST + ".quotes"), found)
    cli.say(run.as_posix())
    return 0


def _taken(path: Path) -> str:
    try:
        text = path.read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return ""
    with contextlib.suppress(OSError):
        path.unlink()
    return text


def label(path: str) -> str:
    """basename <file> .md"""
    name = re.sub(r"^.*/", "", path.rstrip("/") or path, flags=re.S)
    return name[:-3] if name.endswith(".md") and name != ".md" else name


class Check:
    """One check of a run: its scope, the user's redacted words, what is counted, and check.md's rows."""

    def __init__(self, run: Path, args: cli.Args, mode: str) -> None:
        self.run, self.mode, self.given = run, mode, args.value("base")
        self.top = resolve.field(run, "code-root") or where.this_tree()
        self.base = self.given or resolve.field(run, "base")
        self.scope = cite_check.scope(self.top, self.base, run.as_posix(), mode)
        self.said = _taken(run / REQUEST)
        self.secret = iter(_taken(run / (REQUEST + ".secret")).split())
        self.n: Counter = Counter()
        self.extra = ""
        self.table = ["# Citation check — " + time.strftime("%Y-%m-%d %H:%M:%S"),
                      "base: " + (self.base or "unknown — origin not checked"), "",
                      "| item | cite | status | origin |", "|---|---|---|---|"]

    def row(self, *cells: str) -> None:
        self.table.append("| %s |" % " | ".join(cells))

    def every(self, files: list[str]) -> int:
        for path in files:
            self.one(path)
        if self.mode == POSTGAME:
            self.next_tasks()
        if self.mode == IMPLEMENT:
            self.proofs()
        if self.mode == IMPLEMENT and shared.sharing(where.council_home()) == "just me":
            self.hygiene()
        return self.verdict()

    def one(self, path: str) -> None:
        """One file's items, their citations and quotes. Item lines it can't read, or none at all, are never a
        pass: nothing would have been checked."""
        file = where.native(path)
        if not os.path.isfile(file):
            self.n["gone"] += 1
            self.n["other"] += 1
            cli.say("check: %s — no such file" % path)
            return
        self.n["files"] += 1
        lab = label(path)
        kept = any(re.match(r"##[ \t]", line) and KEPT.search(seat_files.lower(line))
                   for line in seat_files.lines(file))
        sections, heading = ("Kept|Cut", "## Kept or ## Cut") if kept else ("Index", "## Index")
        shape = seat_files.shape(file, sections)
        if shape.unparsed:
            self.n["other"] += shape.unparsed
            self.n["unread"] += shape.unparsed
            cli.say("%s: %d item line(s) check can't read — write each as '<n> · <severity> · <principle> · "
                    "<path:line> · <title>'" % (lab, shape.unparsed))
        if not shape.parsed and not shape.none and not shape.unparsed:
            self.n["other"] += 1
            self.n["empty"] += 1
            cli.say("%s: no items under %s — nothing was checked (write '(none) — <why>' when there is nothing)"
                    % (lab, heading))
        for item in seat_files.items(file):
            self.item(lab, item)
        for quote in quotes.item_quotes(file, self.said, self.mode):
            self.quote(lab, quote)

    def item(self, lab: str, item: seat_files.Item) -> None:
        self.n["rows"] += 1
        found = citations.rows(self.top, item.cite)          # read once, for the status and the origin alike
        state, origin = cite_check.status(self.scope, found), ""
        if state == "ok" or state.startswith("deleted"):
            origin = cite_origin.origin(self.scope, found) if self.base else ""
        elif state.startswith("no-line"):
            self.n["noline"] += 1
        elif state.startswith("n/a"):
            self.n["unchecked"] += 1
        else:
            self.n["bad"] += 1
        shown = item.cite.replace("`", "").replace('"', "")
        self.row("%s#%s" % (lab, item.n), shown, state, origin or "-")
        cli.say("%s#%s  %s  %s%s" % (lab, item.n, shown, state, " · " + origin if origin else ""))

    def quote(self, lab: str, quote: quotes.Quote) -> None:
        self.n["quotes"] += 1
        state = quote.status
        if quote.words and next(self.secret, "0") != "0" and state != "ok":
            state = REDACT_IT                                    # a secret in a quote would reach a tracked file
        self.n["found" if state == "ok" else "bad"] += 1
        self.row("%s#%s" % (lab, quote.n), "quote", state, "-")
        cli.say("%s#%s  quote  %s" % (lab, quote.n, state))

    def next_tasks(self) -> None:
        """A post-game's next tasks, once its deliverable is recorded: each closes a gap against the request."""
        named = resolve.field(self.run, "deliverable")
        if named and not (named.startswith("/") or re.match(r"[A-Za-z]:", named)):
            named = os.path.dirname(where.council_home()) + "/" + named
        if not named or not os.path.isfile(where.native(named)):
            return
        wrong = 0
        for task in quotes.next_tasks(where.native(named), self.said):
            self.n["rows"] += 1
            if task.status != "ok":
                self.n["bad"] += 1
                wrong += 1
            self.row("next task " + task.n, "done-when", task.status, "-")
            cli.say("next task %s  done-when  %s · %s" % (task.n, task.status, gate_output.clip(task.title, 70)))
        if wrong:
            cli.say("check: %d next task(s) quote no part of the request — a next task closes a gap against the "
                    "request's own words (its Done-when: part <#>: \"<that part's quote>\"); a checker's note or a "
                    "latent gap in a helper goes under Noticed, not tasked, with its reach today" % wrong)

    def proofs(self) -> None:
        """council-implement: every fix's own proof, checked rather than taken on trust."""
        tally = check_proofs.proofs(self.run, self.top)
        self.n["proofs"] = len(tally.rows)
        self.n["rows"] += len(tally.rows)
        self.n["bad"] += tally.broke + (not tally.rows)
        for proof in tally.rows:
            self.row(proof.who, "proof", proof.status, proof.note)
        self.table += ["", "build tier: " + check_proofs.summary(tally, where.council_home())]

    def hygiene(self) -> None:
        """Just me: nothing teammates read may cite the council. Only what the build added is read; hits are
        counted on their own, never as citations."""
        since = hygiene.base(self.run, self.top, self.given)
        if not since:
            cli.say("hygiene  this run has no recorded start, so only uncommitted work and the PR body were read")
        found = hygiene.hits(self.run, self.top, since, resolve.field(self.run, "opened"))
        for count, hit in enumerate(found, 1):
            self.row("hygiene", hit.place, hit.what, "-")
            words = hit.line.decode("utf-8", "surrogateescape").rstrip("\t").lstrip(" \t\n\v\f\r")
            if count <= 20:
                cli.say("hygiene  %s  %s — teammates can't open the council; say it in plain words: %s"
                        % (hit.place, hit.what, gate_output.clip(words, 90)))
        if len(found) > 20:
            cli.say("hygiene  … and %d more in check.md" % (len(found) - 20))
        if found:
            self.extra += " · %d council reference(s) in shared text (just me)" % len(found)
        self.n["hygiene"] = len(found)

    def verdict(self) -> int:
        """The closing line, check.md, the verification.finished event, and the exit code."""
        n = self.n
        if not n["files"] and not n["gone"] and self.mode != IMPLEMENT:
            n["other"] += 1
            cli.say("check: nothing to check — no synthesis.md and no seat files")
        if not n["quotes"] and self.mode == POSTGAME:
            n["bad"] += 1
            cli.say("check: no quotes found — each part of a post-game quotes the request (quote: \"…\")")
        if n["quotes"] and n["proofs"]:
            what = "(citations, quotes and proof)"
        elif n["quotes"]:
            what = "(citations and quotes)"
        elif n["proofs"] or self.mode == IMPLEMENT:            # NO PROOF is a broken proof
            what = "(citations and proof)"
        else:
            what = "citation(s)"
        extra = self.extra + "".join(" · %d %s" % (n[key], words) for key, words in (
            ("noline", "name a path but no line"), ("unchecked", "not checked (a command, a link, an area or no path)"),
            ("unread", "item line(s) check can't read"), ("empty", "section(s) with nothing to check")) if n[key])
        out = self.run.as_posix() + "/" + run_files.CHECK
        _write(self.run / run_files.CHECK, self.table)
        found = " · %d of %d quotes found in the request" % (n["found"], n["quotes"]) if n["quotes"] else ""
        cli.say("check: %d items, %d broken %s%s%s → %s" % (n["rows"], n["bad"], what, extra, found, out))
        failed = n["bad"] + n["other"] + n["hygiene"]
        event_note.append(self.run, "verification.finished", "run", "failed" if failed else "passed",
                          "items=%d;broken=%d;other=%d%s" % (n["rows"], n["bad"], n["other"],
                                                             ";hygiene=%d" % n["hygiene"] if n["hygiene"] else ""),
                          "verification finished, but its event was not recorded")
        return 1 if failed else 0
