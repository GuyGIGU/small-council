"""What a gate's saved output says beyond its exit code: that no test ran, which tests failed, that cmd opened a
prompt and ran nothing, that `python -m <tool>` had no such tool. Each reads the output as bin/council's awk,
grep and sed did, line by line, a carriage return dropped where they dropped it."""
from __future__ import annotations

import re
from pathlib import Path

ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
SPACE = " \t\n\v\f\r"
RAN = re.compile(r"(running|ran)[ \t]+[1-9][0-9]*[ \t]+tests?([^a-z]|$)|tests run:[ \t]*[1-9]"
                 r"|(^|[^0-9])[1-9][0-9]*[ \t]+(passed|passing)([^a-z]|$)")
NONE_SKIPPED = re.compile(r"(skip|fail|error|ignor|pend)[a-z]*:?[ \t]*0 tests?")
NONE_RAN = re.compile(r"collected 0 items|no tests ran|ran 0 tests|no tests found|no test files|no tests to run"
                      r"|(^|[^0-9.])0 passing")
ZERO_TESTS = re.compile(r"(^|[^0-9.])0 tests?([ \t]+(ran|run|found|collected|executed|in)([^a-z]|$)|[ \t]*[.,;]|[ \t]*$)")
TEST_RUNNERS = ("pytest", "jest", "mocha", "vitest", "rspec", "phpunit", "unittest", "ctest ", " go test", "cargo test",
                "npm test", "npm run test", "yarn test", "pnpm test", "dotnet test", "mvn test", "gradle test")
ANSI = re.compile("\033\\[[0-9;]*[A-Za-z]")
FAILURE_LINES = (
    (re.compile(r"[ \t]*(FAILED|ERROR)[ \t]+[^ \t]"), "rest"),
    (re.compile(r"[ \t]*---[ \t]+(FAIL|ERROR):[ \t]+[^ \t]"), "rest"),
    (re.compile(r"[ \t]*(FAIL|ERROR):[ \t]+[^ \t]"), "rest"),
    (re.compile("[ \t]*(✖|✗|✕|×|❌)[ \t]+[^ \t]"), "rest"),
    (re.compile(r"[ \t]*not ok[ \t]+[0-9]+[ \t]*-?[ \t]*"), "after"),
    (re.compile(r"[ \t]*test[ \t]+[^ \t]+[ \t]+\.\.\.[ \t]+(FAILED|failed)"), "second"),
    (re.compile(r"[ \t]*[^ \t]+[ \t]+FAILED([ \t]|$)"), "first"),
    (re.compile(r"[ \t]*FAIL[ \t]+[^ \t]"), "rest"),
)
MISSING_MODULE = re.compile(r"^.*: No module named ([A-Za-z0-9_.]+)[ \t\n\v\f\r]*$")


def text(path: str | Path) -> str:
    """A saved output's text, its bytes kept (surrogateescape); '' when it can't be read."""
    try:
        return Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return ""


def lines(content: str) -> list[str]:
    """Lines as awk and grep read them: on newline only, a last line without one still a line."""
    found = content.split("\n")
    return found[:-1] if found and found[-1] == "" else found


def clip(line: str, width: int) -> str:
    """The helper's clip: a line past width cut at its last space within it, then ' …'."""
    if len(line) <= width:
        return line
    cut = line[:width]
    space = cut.rfind(" ")
    return (cut[:space] if space >= 0 else cut) + " …"


def zero_tests(content: str) -> str:
    """The line of a passing gate's output that says no test ran, clipped to 120 — unless another line shows
    tests did run (go's "ok <package>", cargo's "running 5 tests", maven's "Tests run: 5", "5 passed")."""
    ran, hit = False, None
    for line in lines(content):
        line = line.replace("\r", "")
        lower = line.lower()
        if re.match(r"ok[ \t]+[^ \t]+\t", lower) and "[no test" not in lower:
            ran = True
        if RAN.search(lower):
            ran = True
        if NONE_SKIPPED.search(lower):               # none skipped is not none ran
            continue
        if hit is None and (NONE_RAN.search(lower) or ZERO_TESTS.search(lower)):
            hit = line
    return clip(hit, 120) if hit and not ran else ""


def _norm(name: str) -> str:
    name = re.sub(r"[ \t]*\([0-9][0-9.,]*[ \t]*(ms|s|sec|secs|seconds)\)[ \t]*$", "", name, count=1)
    name = re.sub(r"[ \t]+-[ \t].*$", "", name, count=1)       # pytest appends " - AssertionError: …"
    return re.sub(r"^[ \t\[]+|[ \t,.:;\]]+$", "", name)


def failure_ids(content: str) -> list[str]:
    """The failing tests a runner's output names, in order, once each, run times dropped: pytest, go, unittest,
    node --test, jest/vitest, TAP and cargo. A log line naming a moment is no test."""
    found: list[str] = []
    for raw in lines(content):
        line = ANSI.sub("", raw.replace("\r", ""))
        for rule, take in FAILURE_LINES:
            match = rule.match(line)
            if not match:
                continue
            fields = re.split(r"[ \t\n]+", raw.strip(" \t\n"))
            name = {"rest": line[match.end() - 1:], "after": line[match.end():],
                    "second": fields[1] if len(fields) > 1 else "", "first": fields[0]}[take]
            name = _norm(name)
            if name and not re.match(r"[0-9]+[-:/.][0-9]", name) and name not in found:
                found.append(name)
            break
    return found


def never_ran(content: str) -> bool:
    """cmd.exe that never got its /c switch: its version banner first, a prompt last, and nothing else ran."""
    found = lines(content)
    if not content or not found:
        return False
    return found[0].startswith("Microsoft Windows [Version") and re.search(r">[ ]*$", found[-1].replace("\r", "")) is not None


def missing_module(content: str) -> str:
    """The module `python -m <module>` could not find, when Python's one line saying so is all a gate printed
    besides `council changed`'s own lines; '' otherwise (a traceback's ModuleNotFoundError is a check that ran)."""
    said = [line for line in lines(content) if line.strip(SPACE) and not line.startswith("changed: ")]
    if len(said) != 1:
        return ""
    found = MISSING_MODULE.match(said[0])
    return found.group(1).replace("\r", "") if found else ""


def is_test_gate(name: str, command: str) -> bool:
    """A test gate, told by its name or by a runner in its command, never by an argument (src tests)."""
    if "test" in name.translate(ASCII_LOWER) or "spec" in name.translate(ASCII_LOWER):
        return True
    padded = " " + command.translate(ASCII_LOWER) + " "
    return any(runner in padded for runner in TEST_RUNNERS)


def blank(content: str) -> bool:
    return content.strip(SPACE) == ""


def tail(content: str, count: int) -> list[str]:
    """`tail -n count` as $( ) keeps it: trailing empty lines dropped."""
    return "\n".join(lines(content)[-count:]).rstrip("\n").split("\n")
