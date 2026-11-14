"""council index [--base <rev>]: the change index — every file changed since the base (the merge-base with the default
branch, or --base) with its hunks, the definitions its diff names, their callers and the tests that name it — into
the run's index.md, and the base into its state; then the earlier council work on these files (records/earlier.py)
and the impact graph (council impact) are added after it."""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from council.commands import changed, cli, closed, impact, index_symbols, prior, resolve
from council.records import bytewise, citations, earlier, run_files, state_set
from council.records import home as where

LABELS = {"A": "added", "D": "deleted", "?": "new, untracked"}
INTRO = ("Symbols come from definitions in the diff; callers and tests are matched by name (git grep) —\n"
         "a starting point for tracing, not proof.\n\n")


def _git(*args: str) -> tuple[int, bytes]:
    try:
        done = subprocess.run(["git", "-c", "core.quotePath=false"] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError:
        return 127, b""
    return done.returncode, done.stdout


def _text(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


def records(data: bytes) -> list[str]:
    """Lines as awk reads them; Git Bash's awk drops a CR before each newline on Windows."""
    found = _text(data).split("\n")
    found = found[:-1] if found and found[-1] == "" else found
    return [line[:-1] if os.name == "nt" and line.endswith("\r") else line for line in found]


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "index", "base")
    cli.no_words("index", words)
    run = resolve.run_folder(args)
    closed.refuse(run, "its change index is on record; index the change in a new run")  # before anything is written
    postgame = resolve.field(run, "mode") == "council-postgame"
    home = "" if postgame else where.council_home()                     # from where the command was run
    top = resolve.field(run, "code-root") or where.this_tree()
    try:
        os.chdir(where.native(top))
    except OSError:
        raise cli.Refusal("cannot enter the code root: %s" % top) from None
    if _git("rev-parse", "--git-dir")[0] != 0:
        raise cli.Refusal("the code root is not a git repository — the change index needs git")
    ref = args.value("base") or changed.default_branch() or "HEAD"
    code, found = _git("merge-base", "HEAD", ref)
    base = _text(found).strip() if code == 0 else ""
    if not base:
        code, found = _git("rev-parse", "-q", "--verify", ref + "^{commit}")
        base = _text(found).strip() if code == 0 else ""
    if not base:
        raise cli.Refusal("unknown base: %s" % ref)
    index = Index(base, ref)
    index.every(changes(base))
    out = run / run_files.INDEX
    out.write_bytes(index.document(run.name).encode("utf-8", "surrogateescape"))
    if postgame:
        # A post-game's verifier reads index.md and must never see the plan, the logs or their verdicts.
        cli.say("index: earlier council work left out (a post-game's verifier reads this file) — run council prior "
                "yourself")
    record(run, base)
    shown = out.as_posix()
    if not index.n_files:
        cli.say("index: nothing changed since %s (%s) → %s" % (index.short, ref, shown))
    else:
        cli.say("index: %d files (+%d/-%d) → %s" % (index.n_files, index.added, index.deleted, shown))
    if index.n_over:
        cli.say("index: %d more past the %s-file cap — named at the end of the index but not indexed; give them an "
                "owner too" % (index.n_over, index.cap))
    if not postgame:
        earlier_work(run, home)
    if impact.refresh(run, top) != 0:
        cli.warn("council: optional impact graph was not refreshed; the change index is still valid")
    return 0


def earlier_work(run: Path, home: str) -> None:
    """The earlier council work on these files (40 mentions at most), at the end of the index. A post-game's Chair
    runs council prior for itself."""
    found = earlier.hits(home, earlier.indexed(run))[:prior.SHOWN]
    if not found:
        return
    listed = "".join("- %s\n" % earlier.line(row) for row in found)
    with open(str(run / run_files.INDEX), "ab") as out:
        out.write(b"## Earlier council work on these files\n" + bytewise.bytes_of(listed))
    cli.say("earlier council work on these files: %d mention(s), listed at the end of the index" % len(found))


def record(run: Path, base: str) -> None:
    """The base into the state (council state base=…)."""
    try:
        state_set.put(run, "base", base)
    except state_set.StateError as failure:
        if str(failure) == "closed":
            closed.refuse(run, "it takes only deliverable=, decision= (and ask save) now; open a new run for more "
                               "work")
        raise cli.Refusal(str(failure)) from None


def changes(base: str) -> list[tuple[str, str, str]]:
    """status, path, old path (a rename's or a copy's, else "-") for each changed file, by path, each once; an
    untracked folder (a nested repository or worktree) is not a changed file."""
    found = []
    for line in records(_git("diff", "-M", "--name-status", base, "--", ".")[1]):
        cells = line.split("\t")
        state = cells[0][:1]
        cell = (cells + ["", ""])
        found.append((state, cell[2], cell[1]) if state in ("R", "C") else (state, cell[1], "-"))
    for line in records(_git("ls-files", "--others", "--exclude-standard")[1]):
        if not line.endswith("/"):
            found.append(("?", line, "-"))
    seen, kept = set(), []
    for change in sorted(found, key=lambda change: change[1].encode("utf-8", "surrogateescape")):
        if change[1] not in seen:
            seen.add(change[1])
            kept.append(change)
    return kept


def _cap(name: str, default: str) -> tuple[str, int | None]:
    said = os.environ.get(name, "") or default
    return said, citations.bash_int(said)


def _binary(path: str) -> bool:
    """grep -qI -e '' fails: a file with a NUL in its first 32 KiB (an empty one is text)."""
    try:
        with open(path, "rb") as handle:
            return b"\0" in handle.read(32768)
    except OSError:
        return True


def _number(text: str) -> int | None:
    return int(text) if re.fullmatch(r"[0-9]+", text) else None


def hunks(diff: list[str]) -> str:
    """A diff's hunks as the new file numbers them: 12, 30-34, or removed near 7."""
    found = []
    for line in diff:
        if not line.startswith("@@"):
            continue
        mark = re.search(r"\+[0-9]+(,[0-9]+)?", line)
        if mark:
            parts = mark.group(0)[1:].split(",")
            start, count = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
            found.append("removed near %d" % start if count == 0 else
                         str(start) if count == 1 else "%d-%d" % (start, start + count - 1))
    return ", ".join(found)


class Index:
    """The index as it is built: each file's section, the files past the cap, and the counts."""

    def __init__(self, base: str, ref: str) -> None:
        self.base, self.ref = base, ref
        self.short = _text(_git("rev-parse", "--short", base)[1]).strip()
        self.head = _text(_git("rev-parse", "--short", "HEAD")[1]).strip()
        self.cap, self.most = _cap("COUNCIL_INDEX_CAP", "80")      # files indexed in full (the evals lower it)
        self.namecap, self.named = _cap("COUNCIL_INDEX_NAMECAP", "200")   # past the cap: how many are named
        self.body, self.over = [], []
        self.n_files = self.n_skip = self.n_over = self.n_new = self.added = self.deleted = 0
        self.search = index_symbols.Search()

    def every(self, found: list[tuple[str, str, str]]) -> None:
        for state, path, old in found:
            if not path or path.startswith(".council/"):   # the council's own files are never part of a change
                continue
            if index_symbols.not_indexed(path):
                self.n_skip += 1
                continue
            label = LABELS.get(state) or ("renamed from " + old if state == "R" else
                                          "copied from " + old if state == "C" else "modified")
            self.n_new += state == "?"
            if self.most is not None and self.n_files >= self.most:
                # Named, so each still gets an owner — but a repo-wide change would put hundreds of KB into a
                # file every seat reads, so past namecap they are counted instead of listed.
                self.n_over += 1
                if self.named is None or self.n_over <= self.named:
                    self.over.append("## %s  (%s — past the %s-file cap: not indexed)\n" % (path, label, self.cap))
                continue
            self.n_files += 1
            self.one(state, path, old, label)

    def one(self, state: str, path: str, old: str, label: str) -> None:
        if state == "?":
            if os.path.isfile(path) and os.path.getsize(path) and _binary(path):
                self.body.append("## %s  (%s, binary)\n\n" % (path, label))
                return
            try:
                data = Path(path).read_bytes()
                add = str(citations.count_lines(data))
            except OSError:
                data, add = b"", ""
            deleted, spans = "0", "1-" + (add or "0")
            diff = ["+" + line for line in records(data)[:400]]
        else:
            paths = [old, path] if state in ("R", "C") else [path]   # both paths, so git pairs them
            numbers = (records(_git("diff", "-M", "--numstat", self.base, "--", *paths)[1]) or [""])[0].split("\t")
            add, deleted = numbers[0], numbers[1] if len(numbers) > 1 else ""
            if add == "-":
                self.body.append("## %s  (%s, binary)\n\n" % (path, label))
                return
            diff = records(_git("diff", "-M", "-U0", self.base, "--", *paths)[1])
            spans = hunks(diff)
        self.section(path, label, (add, deleted), spans, diff)

    def section(self, path: str, label: str, counts: tuple[str, str], spans: str, diff: list[str]) -> None:
        names, callers, tests, note = [], "", "", ""
        if not index_symbols.no_symbols(path):
            names = index_symbols.symbols(diff)
            callers, note = self.search.callers(path, names)
            tests, note = self.search.tests(path, note)
        lines = ["## %s  (%s, +%s/-%s)\n" % (path, label, counts[0] or "0", counts[1] or "0"),
                 "- hunks: %s\n" % (spans or "-")]
        lines += ["- symbols: %s\n" % ", ".join(names)] if names else []
        lines += ["- callers: %s\n" % callers] if callers else []
        lines += ["- tests: %s\n" % tests] if tests else []
        lines += ["- note: %s\n" % note] if note else []
        self.body.append("".join(lines) + "\n")
        self.added += _number(counts[0]) or 0
        self.deleted += _number(counts[1]) or 0

    def document(self, name: str) -> str:
        """index.md: the header, each file's section, then the files past the cap."""
        dirty = self.n_new > 0 or bool(_git("--no-optional-locks", "status", "--porcelain",
                                            "--untracked-files=no")[1].split(b"\n", 1)[0])
        head = ["# Change index — %s\n" % name,
                "base: %s (%s) · head: %s%s · generated: %s\n" % (self.short, self.ref, self.head,
                                                                   " + uncommitted changes" if dirty else "",
                                                                   time.strftime("%Y-%m-%d %H:%M:%S")),
                "files: %d (+%d/-%d)" % (self.n_files, self.added, self.deleted)]
        if self.n_over:
            head.append(" · past the %s-file cap: %d (named at the end, not indexed — they still need an owner)"
                        % (self.cap, self.n_over))
        if self.n_skip:
            head.append(" · not indexed: %d (lockfiles, vendored or generated files)" % self.n_skip)
        head += ["\n", INTRO] + self.body
        if self.n_over:
            head.append("## Past the %s-file cap — %d more changed files, named but not indexed; each still needs an "
                        "owner\n" % (self.cap, self.n_over))
            head += self.over
            if self.named is not None and self.n_over > self.named:
                head.append("## … and %d more, not named one by one: git diff --name-only %s\n"
                            % (self.n_over - self.named, self.short))
            head.append("\n")
        return "".join(head)
