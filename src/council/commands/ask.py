"""council ask save [slug]: file the run's ask.md, the user's words, where later runs and a post-game find them. A new
request becomes .council/asks/<date>-<slug>.md (line 1, then run: and mode:, then the rest of ask.md as written); a
run that continues one (the state's ask:) puts its new words in one dated section, replaced where it stands if this
run saved before. Either way secret-looking strings are redacted and the state records ask= and ask-saved=."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from council.commands import cli, resolve
from council.records import home as where
from council.records import ignores, redact, request, state_set

USAGE = "usage: council ask save [slug]   (after writing the user's words to <run>/ask.md)"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "ask")
    if len(words) > 2:
        raise cli.Refusal("usage: council ask save [slug]")
    if not words or words[0] != "save":
        raise cli.Refusal(USAGE)
    return save(resolve.run_folder(args), words[1] if len(words) > 1 else "")


def _read(path: str) -> bytes:
    try:
        with open(where.native(path), "rb") as stream:
            return stream.read()
    except OSError:
        return b""


def _real(folder: str) -> str:
    """cd -P <folder> && here: the folder with its links resolved, '' when it isn't one."""
    folder = where.native(folder)
    return Path(os.path.realpath(folder)).as_posix() if os.path.isdir(folder) else ""


def save(run: Path, slug: str) -> int:
    folder = run.as_posix()
    ask = folder + "/" + request.ASK
    if not os.path.isfile(where.native(ask)):
        raise cli.Refusal("no ask.md in %s — write the user's words there first" % folder)
    data = _read(ask)
    body, later = request.ask_words(data), request.ask_later(data)
    if not re.search(rb"[^ \t\n\v\f\r]", body.rstrip(b"\n")):
        raise cli.Refusal("ask.md has no words under '## In your words'")
    no_words = [line for line in body.replace(b"\r", b"").split(b"\n")
                if not re.fullmatch(rb"[ \t\v\f\r]*", line)] == [b"(no new words)"]
    home = where.council_home()
    asks = home + "/asks"
    if os.path.islink(where.native(asks)) or (os.path.exists(where.native(asks))
                                              and _real(asks) != _real(home) + "/asks"):
        raise cli.Refusal("%s/asks is a link or a file, not a folder — requests are filed only in a real asks/ folder; "
                          "replace it with one" % home)
    mode = resolve.field(run, "mode")
    filing = Filing(run, home, mode, request.continued(run))
    if not filing.current and no_words:
        raise cli.Refusal("ask.md says (no new words) but names no request to continue — add continues: <path> to "
                          "it, or run council state ask=<path>")
    if ignores.keep_out(home):
        cli.warn("council: %s/.gitignore now ignores asks/, so new requests stay on this machine; the ones already in "
                 "git stay tracked. To share requests with the team, write '!asks/' in place of that line."
                 % os.path.basename(home))
    try:
        os.makedirs(where.native(asks), exist_ok=True)
    except OSError:
        raise cli.Refusal("cannot create %s" % asks) from None
    status, red = filing.new(data, slug) if not filing.current or filing.own else filing.more(data, no_words, later)
    return filing.record(status, red)


class Filing:
    """Where this run's words go: a new request, its own again, or the request it continues."""

    def __init__(self, run: Path, home: str, mode: str, current: str) -> None:
        self.run, self.home, self.mode, self.current = run, home, mode, current
        self.root, self.name, self.own, self.target = os.path.dirname(home), run.name, False, ""
        if current:
            self.target = self.continued()
            second = request.lines_kept(_read(self.target))[1:2]
            self.own = [line.replace(b"\r", b"").rstrip(b"\n") for line in second] == [b"run: " + self.name.encode()]

    def continued(self) -> str:
        """The filed request this run continues: only a real file inside asks/ — no ".." step, no link, and the
        folder it resolves to is asks/ (or below it), compared after resolving both."""
        cur = self.current.replace("\\", "/")
        target = cur if cur.startswith("/") or re.match(r"[A-Za-z]:", cur) else self.root + "/" + cur
        elsewhere = "a request is filed under %s/asks/, not %s — copy the words into ask.md instead" % (self.home, cur)
        if "/../" in "/" + cur + "/":
            raise cli.Refusal(elsewhere)
        rdir, rasks = _real(os.path.dirname(target) or "."), _real(self.home + "/asks")
        if not (rdir + "/").startswith(rasks + "/"):
            raise cli.Refusal(elsewhere)
        if not rasks:
            raise cli.Refusal("the request this run continues is missing: %s" % cur)
        target = self.home + "/asks" + rdir[len(rasks):] + "/" + target.rsplit("/", 1)[-1]
        if not os.path.isfile(where.native(target)):
            raise cli.Refusal("the request this run continues is missing: %s" % cur)
        if os.path.islink(where.native(target)):
            raise cli.Refusal("a request is filed under %s/asks/, not %s (a link) — copy the words into ask.md "
                              "instead" % (self.home, cur))
        return target

    def new(self, data: bytes, slug: str) -> tuple[str, int]:
        """A new request, or this run's own filed again: the sections later runs added stay, as written."""
        lines = request.lines_kept(data)
        if not self.current:
            self.target = self.free(slug or self.title_slug(lines[0] if lines else b""))
        words = (lines[0] if lines else b"") + b"run: %s\nmode: %s\n" % (
            self.name.encode(), (self.mode or "-").encode("utf-8", "surrogateescape")) + b"".join(lines[1:])
        shown, red = redact.redact(words)
        if self.own:
            filed = _read(self.target)
            at = request.ask_sections(filed)
            if at:
                shown += b"\n" + b"".join(request.lines_kept(filed)[at[0] - 1:])
        self.write(shown, "cannot write %s")
        return "new", red

    def title_slug(self, first: bytes) -> str:
        """From the title as filed, so a pasted key never names the file."""
        shown = redact.redact(first)[0]
        shown = re.sub(rb"\[redacted[^]]*\]", b"", re.sub(rb"^#[ \t\n\v\f\r]*[Aa]sk", b"", shown, count=1))
        return shown.decode("utf-8", "surrogateescape")

    def free(self, slug: str) -> str:
        name = slug.replace("\r", "").encode("utf-8", "surrogateescape").lower()
        name = re.sub(rb"^-+", b"", re.sub(rb"[^a-z0-9]+", b"-", name.rstrip(b"\n")))
        name = re.sub(rb"-*$", b"", name[:40]).decode("utf-8", "surrogateescape") or "request"
        base = "%s/asks/%s-%s" % (self.home, time.strftime("%Y-%m-%d"), name)
        target, n = base + ".md", 2
        while os.path.lexists(where.native(target)):
            target, n = "%s-%d.md" % (base, n), n + 1
        return target

    def more(self, data: bytes, no_words: bool, later: bytes) -> tuple[str, int]:
        """A continuing request: this run's words in one dated section, replaced where it stands if this run saved
        before; every other run's section stays."""
        shown, red, status = b"", 0, "no new words"
        if not (no_words and not later):
            section = ("\n## %s — %s, run %s\n" % (time.strftime("%Y-%m-%d"), self.mode or "-", self.name)).encode(
                "utf-8", "surrogateescape")
            shown, red = redact.redact(section + request.ask_words(data) + request.ask_later(data))
            status = "continued"
        filed = _read(self.target)
        mine = request.ask_sections(filed, self.name) if status != "no new words" else []
        if mine:
            lines, at = request.lines_kept(filed), mine[0]
            after = [n for n in request.ask_sections(filed) if n > at]
            keep = at - 1                                     # the blank line before the heading goes with it
            if keep >= 1 and not re.sub(rb"[ \t\n\v\f\r]", b"", lines[keep - 1]):
                keep -= 1
            rest = b"\n" + b"".join(lines[after[0] - 1:]) if after else b""
            self.write(b"".join(lines[:keep]) + shown + rest, "cannot update %s")
        elif shown:
            self.write(shown, "cannot append to %s", append=True)
        return status, red

    def write(self, data: bytes, failed: str, append: bool = False) -> None:
        try:
            with open(where.native(self.target), "ab" if append else "r+b" if os.path.exists(
                    where.native(self.target)) else "wb") as stream:
                stream.write(data)
                stream.truncate()
        except OSError:
            raise cli.Refusal(failed % self.target) from None

    def record(self, status: str, red: int) -> int:
        target = self.target
        rel = target[len(self.root) + 1:] if target.startswith(self.root + "/") else target
        try:
            state_set.put_all(self.run, [("ask", rel), ("ask-saved", time.strftime("%Y-%m-%d %H:%M"))],
                              after_close=True)
        except state_set.StateError as failure:
            raise cli.Refusal(str(failure)) from None
        if red:
            cli.say("ask: redacted %d secret-looking string(s) — tell the user; it catches common shapes only, so "
                    "check %s for others before sharing it" % (red, rel))
        cli.say("ask: %s (%s)" % (rel, status))
        return 0
