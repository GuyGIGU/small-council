"""What a build's proof command reached, read from its words (the helper's gate_test_path and run_folder_only):
the test file it ran that the project keeps, and whether it ran nothing but scripts kept in a run folder."""
from __future__ import annotations

import os
import re
import subprocess

from council.records import home as where

DROP = str.maketrans("", "", "\"'`")
CONFIG = re.compile(r".*\.(log|ini|cfg|conf|toml|json|yaml|yml|xml|txt|md|lock|csv)", re.S)
TEST_NAME = re.compile(r"(test_|test-|spec_|tests\.|test\.).*|.*(_test\.|-test\.|\.test\.|\.spec\.|_spec\.|-spec\.).*",
                       re.S)
TEST_FOLDER = re.compile(r".*/(tests|test|spec|specs|__tests__|evals)/.*", re.S)
UP = re.compile(r"[^/][^/]*/\.\./")
SKIPPED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*|(env|time|exec|command|nohup|then|do|else|!)", re.S)
TOOLS = re.compile(r"(echo|printf|test|true|false|grep|egrep|cat|diff|cmp|head|tail|wc|sort|uniq|tee|sed|awk|rm|"
                   r"mkdir|cp|mv|ls|touch|sleep|export|set|exit|return|wait|if|fi|for|while|until|done|case|esac|in)")
RUNNER = re.compile(r"(^|/)(ba|z|da|k)?sh$|(^|/)(python[0-9.]*|node|ruby|perl|php|swift|deno|bun|pwsh|powershell|"
                    r"osascript|lua|tclsh)$")
RUNS = ".council/runs/"


def _up(path: str) -> str:
    """A path that walks back up, one `<part>/../` at a time: webapp/backend/../../tests/x is tests/x."""
    while "/../" in path:
        shorter = UP.sub("", path, count=1)
        if shorter == path:
            break
        path = shorter
    return path


def _git(top: str, *args: str) -> int:
    try:
        return subprocess.run(["git", "-C", top] + list(args), stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode
    except OSError:
        return 127


def _inside(top: str, sub: str, root: str) -> bool:
    """cd <sub> from the project, then pwd -P: the folder it lands in is the project or under it."""
    folder = os.path.join(top, where.native(sub))
    if not os.path.isdir(folder):
        return False
    landed = os.path.realpath(folder)
    return landed == root or landed.startswith(root.rstrip(os.sep) + os.sep)


class _Words:
    """Where the command's words have moved so far: the folder a cd or --prefix named, and whether it left."""

    def __init__(self) -> None:
        self.sub, self.want, self.away = "", False, False


def _token(word: str) -> str:
    word = word.translate(DROP)
    word = word[:-1] if word.endswith(";") else word
    word = word[1:] if word.startswith("(") else word
    return word[:-1] if word.endswith(")") else word


def _moved(token: str, state: _Words) -> str | None:
    """A word that moves the command (cd, pushd, --prefix …) or names the folder it moves to: None to skip it."""
    if state.want:
        state.want, state.sub, state.away = False, token[:-1] if token.endswith("/") else token, False
    if token in ("cd", "pushd", "--prefix", "--cwd", "--dir", "-C"):
        state.want = True
        return None
    if token.startswith(("--prefix=", "--cwd=", "--dir=")):
        sub = token.split("=", 1)[1]
        state.sub, state.away = sub[:-1] if sub.endswith("/") else sub, False
    elif token.startswith("-") and "=" in token[1:]:
        token = token.split("=", 1)[1]
    return token


def _named(token: str, state: _Words) -> str | None:
    """The path a word names, as it lands from the project, when it can be a test the project keeps."""
    if token.startswith("res://"):
        token = token[len("res://"):]
    if "::" in token:
        token = token[:token.index("::")]
    if token.startswith("-") or token in (".", "./") or "*" in token or "?" in token or not re.search(r"[/.]", token):
        return None
    base = token.rsplit("/", 1)[-1].translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                                                            "abcdefghijklmnopqrstuvwxyz"))
    if CONFIG.fullmatch(base) or state.away:          # a config, a log or a report is never the test that was saved
        return None
    path = token
    if not (token.startswith("/") or re.match(r"[A-Za-z]:", token)) and state.sub:
        path = state.sub + "/" + token
    if not TEST_NAME.fullmatch(base):                 # a test folder, by the path as it lands, inside the project
        landed = _up(path)
        if landed.startswith(("/", "../")) or re.match(r"[A-Za-z]:", landed):
            return None
        if not TEST_FOLDER.fullmatch("/" + (landed[2:] if landed.startswith("./") else landed)):
            return None
    return path


def test_path(top: str, command: str) -> str:
    """The first test file the command names that the project keeps (tracked, or there and not ignored), its
    path walked back up; '' when none is, or the command left the project before naming one."""
    top = where.native(top)
    if not os.path.isdir(top):
        return ""
    root, state = os.path.realpath(top), _Words()
    for word in re.split(r"[ \t\n]+", command):
        if not word:
            continue
        token = _moved(_token(word), state)
        if token is None:
            continue
        if state.sub and not state.away and not _inside(top, state.sub, root):
            state.away = True                         # out of the project: nothing is confirmed, never the wrong file
        if token in ("cd", "pushd") or token.startswith(("--prefix=", "--cwd=", "--dir=")):
            continue
        path = _named(token, state)
        if path is None or not os.path.isfile(os.path.join(top, where.native(path))):
            continue
        if _git(top, "ls-files", "--error-unmatch", "--", where.native(path)) == 0 \
                or _git(top, "check-ignore", "-q", "--", where.native(path)) == 1:
            hit = _up(path)
            return hit[2:] if hit.startswith("./") else hit
    return ""


def _parts(command: str) -> list[str]:
    said = re.sub(r"[\"'`]", " ", command)
    said = re.sub(r"[0-9]*>&[0-9]*|&>|[0-9]*>>?|[0-9]*<", " > ", said)      # redirections: never a command
    return re.sub(r"&&|\|\||[;|&()]", "\n", said).split("\n") if said else []


def run_folder_only(command: str) -> bool:
    """Each program the command starts is a script kept in a run folder (.council/runs/…) — directly, through
    an interpreter, or after a cd into one — or a plain shell tool. Unknown words count as the project's."""
    ran = other = 0
    in_run = False
    for part in _parts(command):
        words = re.split(r"[ \t]+", part)
        j = 0
        while j < len(words) and (words[j] == "" or SKIPPED.fullmatch(words[j])):
            j += 1
        if j >= len(words) or words[j] == ">":
            continue
        exe = words[j]
        if exe in ("cd", "pushd"):
            in_run = j + 1 < len(words) and RUNS in words[j + 1]
            continue
        if not re.match(r"[A-Za-z0-9_./~$]", exe) or TOOLS.fullmatch(exe):
            continue
        program = exe
        if RUNNER.search(exe):
            program = next((word for word in words[j + 1:] if word and not word.startswith("-")), "")
        if RUNS in program or (in_run and program != "" and not program.startswith(("/", "$", "~"))):
            ran += 1
        else:
            other += 1
    return ran > 0 and other == 0
