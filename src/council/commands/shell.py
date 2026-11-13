"""Running a project's own command under bash, as bin/council ran it: the bash on PATH, and the environment the
helper had. bin/council starts Python with MSYS2_ARG_CONV_EXCL='*' (its arguments arrive as typed); a command
started from here gets the value the helper had back, so Git Bash converts its paths as it always did."""
from __future__ import annotations

import os
import subprocess
import sys

OUTER = "COUNCIL_ARG_CONV_EXCL"     # bin/council's python_run: "set:<value>", or empty when it was unset


def bash() -> str:
    """The bash a command line is run with: the first on PATH, as bin/council's own `bash -c` found it."""
    import shutil                                  # only a command that runs one needs it (D34)
    return shutil.which("bash") or "bash"


def argv_for(argv: list[str]) -> list[str] | str:
    """Popen's args for a bash started from here, each word arriving as it is. On Windows they travel as one
    command line, which Git Bash's runtime splits by its own rule — inside double quotes \\ and \\" are escapes,
    and a word left unquoted is split at a quote mark — not the rule subprocess writes for."""
    if os.name != "nt":
        return argv
    return " ".join('"%s"' % word.replace("\\", "\\\\").replace('"', '\\"') for word in argv)


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for a project's command: the helper's own, plus extra."""
    env = dict(os.environ)
    outer = env.pop(OUTER, None)
    if outer is not None:
        if outer.startswith("set:"):
            env["MSYS2_ARG_CONV_EXCL"] = outer[len("set:"):]
        else:
            env.pop("MSYS2_ARG_CONV_EXCL", None)
    env.update(extra or {})
    return env


def status(code: int) -> int:
    """An exit status as bash reports it: a process killed by signal n is 128 + n."""
    return 128 - code if code < 0 else code


def flush() -> None:
    """What this process printed so far goes out before a child writes to the same streams."""
    sys.stdout.flush()
    sys.stderr.flush()


def words(argv: list[str]) -> int:
    """Run argv as bash runs "${words[@]}" (a builtin, a function-free PATH lookup, a script): its exit code."""
    flush()
    try:
        done = subprocess.run(argv_for([bash(), "-c", '"$@"', "council"] + argv), env=child_env())
    except OSError:
        return 127
    return status(done.returncode)


SPECIAL = frozenset(" \t\n\"$&'()*;<>?[\\]^`{|}!,")   # bash's backslash_table: each is written \<char>
NAMED = {"\a": "a", "\b": "b", "\033": "E", "\f": "f", "\n": "n", "\r": "r", "\t": "t", "\v": "v", "\\": "\\",
         "'": "'"}


def quote(argv: list[str]) -> str:
    """Words as bash's `printf '%q '` writes them, joined by spaces: the command `council gate <name> -- <words>`
    runs when its words come separately, each kept intact."""
    return " ".join(_quoted(word) for word in argv)


def _utf8() -> bool:
    """The locale's characters are UTF-8 (LC_ALL, else LC_CTYPE, else LANG; none set is the C locale)."""
    for name in ("LC_ALL", "LC_CTYPE", "LANG"):
        value = os.environ.get(name, "")
        if value:
            return "utf-8" in value.lower() or "utf8" in value.lower()
    return False


def _printable(char: str, utf8: bool) -> bool:
    if char < "\x80":
        return " " <= char < "\x7f"
    import unicodedata
    if not utf8 or "\udc80" <= char <= "\udcff" or (os.name == "nt" and char > "￿"):   # Git Bash: 16-bit wchar_t
        return False
    return unicodedata.category(char) not in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp")


def _quoted(word: str) -> str:
    if not word:
        return "''"
    utf8 = _utf8()
    if all(_printable(char, utf8) for char in word):
        out = []
        for at, char in enumerate(word):
            if char in SPECIAL or (char == "#" and at == 0) or (char == "~" and (at == 0 or word[at - 1] in ":=")):
                out.append("\\")
            out.append(char)
        return "".join(out)
    out = []
    for char in word:
        if char in NAMED:
            out.append("\\" + NAMED[char])
        elif _printable(char, utf8):
            out.append(char)
        else:
            out.extend("\\%03o" % byte for byte in char.encode("utf-8", "surrogateescape"))
    return "$'" + "".join(out) + "'"


RETRIED = (85, 126, 127, 49)     # bin/council's python_run tries its next Python on these


def ran(code: int) -> int:
    """The exit code of a command that ran a project's own command. One of the codes bin/council's python_run
    takes for "this Python could not start" (a gate whose tool was not found exits 127) is marked as this
    Python's own, in the file COUNCIL_RAN names, so the command is not run again under the next Python."""
    marker = os.environ.get("COUNCIL_RAN", "")
    if code in RETRIED and marker:
        try:
            open(marker, "w").close()
        except OSError:                     # bash then tries the next Python, as it did before the marker
            return code
    return code
