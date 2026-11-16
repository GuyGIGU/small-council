"""What council patch save finds in a round's diff before the verifier sees it (references/run/builder-report.md):
the tests, assertions and document rules it removed, the files it changed outside the task's slice, and the added
lines that look like a workaround. The removals are held against the head's Removed line; the rest are questions
for the verifier, never verdicts. They are patterns: they miss what they don't name."""
from __future__ import annotations

import fnmatch
import re
from typing import NamedTuple

from council import diff

DOCS = (".md", ".mdx", ".markdown", ".rst", ".txt", ".adoc")
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|specs?|evals?)/|(^|/)test_[^/]*$|_test\.[^/]+$|\.(test|spec)\.[^/]+$"
                       r"|(Tests?|Spec)\.[A-Za-z]+$")
TEST_DEF = re.compile(r"(?:async\s+)?def\s+(test\w*)|func\s+(Test\w+)|(?:it|test|describe)\s*\(\s*['\"`]([^'\"`]+)"
                      r"|(?:public\s+)?void\s+(test\w*)|#\[test\]|@Test\b")
ASSERTION = re.compile(r"^\s*assert\b|\bassert\w*!?\s*\(|\bexpect\s*\(|\.should\b|\brequire\.\w+\s*\(|"
                       r"\bt\.(?:Error|Fatal)f?\s*\(|\bself\.fail\w*\s*\(")
RULE = re.compile(r"\b(never|always|must|only|refuse[sd]?|required?|do not|don't|cannot|can't|may not|at most|"
                  r"at least|no more than)\b", re.IGNORECASE)
SIGNS = (
    ("retry", re.compile(r"\bretr(?:y|ies|ied|ying)\b|\bbackoff\b|\bmax_?attempts\b", re.IGNORECASE)),
    ("sleep", re.compile(r"\b(?:time\.)?sleep\s*\(|\bsleep\s+[0-9.]+|\busleep\b|\bThread\.sleep\b|\bsetTimeout\s*\(|"
                         r"\bwait_for_timeout\b|\btime\.Sleep\b")),
    ("catch-all", re.compile(r"\bexcept\s*:|\bexcept\s+\(?\s*(?:Base)?Exception\b|"
                             r"\bcatch\s*\(\s*(?:\.\.\.|(?:Exception|Throwable|Error)(?:\s+\w+)?|\w{1,5})?\s*\)|"
                             r"\bcatch\s*\{|\brescue\s*(?:=>|$)|\|\|\s*true\b|On Error Resume Next")),
    ("skipped test", re.compile(r"\b(?:pytest\.mark\.skip\w*|pytest\.skip|unittest\.skip\w*|skipTest|xfail)\b|"
                                r"\b(?:it|test|describe)\.skip\b|\bx(?:it|describe|test)\s*\(|\bt\.Skip\w*\(|"
                                r"#\[ignore\]|@(?:Disabled|Ignore)\b")),
    ("time limit", re.compile(r"(?=.*[0-9])(?:\btime_?outs?\b|\btime[ _-]?limit\b|\bdeadline\b|--timeout\b)",
                              re.IGNORECASE)),
    ("looser expectation", re.compile(r"\b(?:approx|assertAlmostEqual|toBeCloseTo|isclose|allclose)\b|"
                                      r"\b(?:rtol|atol|tolerance|epsilon|places|delta)\s*=")),
    ("workaround words", re.compile(r"(?<![a-z])work[-_ ]?arounds?(?![a-z])|(?<![a-z])hack(?:s|y)?(?![a-z])|"
                                    r"\btemporar(?:y|ily)\b(?!\s+(?:files?|dir(?:ectory|ectories|s)?|folders?|copy))|"
                                    r"\bfor\s+now\b|\buntil\b.*?\b(?:is|are|gets?|been)\s+fixed\b", re.IGNORECASE)),
    ("todo", re.compile(r"\b(?:TODO|FIXME)\b|(?<![\w-])XXX(?![\w-])")),
)


class Removal(NamedTuple):
    """A test, an assertion or a document rule the round took out: its kind, file, old line, a name (a test's)
    and the line's text."""

    kind: str
    path: str
    line: int
    name: str
    text: str


class Sign(NamedTuple):
    """An added line that looks like a workaround: what it looks like, where, and its text."""

    kind: str
    path: str
    line: int
    text: str


def _flat(text: str) -> str:
    """A line as a move is matched: list and quote markers, backticks and spacing dropped, lower case."""
    text = re.sub(r"^[\s>#*|+-]*(?:[0-9]+[.)]\s*)?", "", text).replace("`", "").replace("*", "")
    return " ".join(text.lower().split())


def _doc(path: str) -> bool:
    return path.lower().endswith(DOCS)


def removals(found: list[diff.File]) -> list[Removal]:
    """The tests, assertions and document rules taken out: a deleted test file as one; else each removed line that
    defines a test, asserts, or (in a document) states a rule, unless the same words were added anywhere in the
    round (a move, not a removal)."""
    kept = {_flat(line.text) for file in found for line in file.added}
    out = []
    for file in found:
        if file.deleted and TEST_PATH.search(file.path):
            out.append(Removal("test file", file.path, 1, file.path.rsplit("/", 1)[-1], ""))
            continue
        for line in file.removed:
            flat = _flat(line.text)
            if not flat or flat in kept:
                continue
            kind, named = _kind(file.path, line.text)
            if kind:
                out.append(Removal(kind, file.path, line.number, named, line.text.strip()))
    return out


def _kind(path: str, text: str) -> tuple[str, str]:
    """What a removed line was: ('test', its name), ('assertion', ''), ('rule', '') or ('', '')."""
    if _doc(path):
        return ("rule", "") if RULE.search(text) else ("", "")
    defined = TEST_DEF.search(text.strip())
    if defined and (defined.start() == 0 or TEST_PATH.search(path)):
        return "test", next((group for group in defined.groups() if group), "")
    return ("assertion", "") if ASSERTION.search(text) else ("", "")


def unlisted(found: list[Removal], removed: str, none: bool) -> list[Removal]:
    """The removals the head's Removed line doesn't name: all of them under 'none'; else each whose file (its path
    or its name) and, for a test, whose test name the line doesn't hold."""
    if none:
        return found
    words = removed.lower()
    out = []
    for item in found:
        named = _names(words, item.path) or _names(words, item.path.rsplit("/", 1)[-1])
        if item.kind == "test" and item.name:
            named = named or _names(words, item.name)
        if not named:
            out.append(item)
    return out


def _names(words: str, name: str) -> bool:
    """The words hold the name as a word of its own: pay.py is not named by test_pay.py, nor a.py by src/a.py."""
    return re.search(r"(?<![\w./-])" + re.escape(name.lower()) + r"(?![\w/-])", words) is not None


def signs(found: list[diff.File]) -> list[Sign]:
    """Each added line of code (not a document) that retries, sleeps, catches everything, skips a test, sets a
    time limit, loosens an expected value, says it is a workaround or for now, or leaves a TODO; and an assertion
    changed in place, which may have been loosened."""
    out = []
    for file in found:
        if _doc(file.path):
            continue
        asserted = any(ASSERTION.search(line.text) for line in file.removed)
        gone = {_flat(line.text) for line in file.removed}
        for line in file.added:
            kinds = [kind for kind, pattern in SIGNS if pattern.search(line.text)]
            if asserted and ASSERTION.search(line.text) and _flat(line.text) not in gone:
                kinds.append("changed expectation")
            out += [Sign(kind, file.path, line.number, line.text.strip()) for kind in kinds]
    return out


def slice_paths(cells: list[str]) -> list[str]:
    """The paths a task's Owner and Touches cells (and the map row they name) give: each word holding a '/' or a
    file name with an extension, backticks, quotes and a trailing :line or punctuation dropped; each path once, in
    the order first named."""
    found = []
    for cell in cells:
        for word in re.split(r"[\s,;]+", cell or ""):
            word = re.sub(r":[0-9]+(?:-[0-9]+)?$", "", word.strip("`'\"()[]*,;:").rstrip("."))
            if "/" in word or re.fullmatch(r"[\w.*-]+\.[A-Za-z0-9]+", word):
                found.append(word[2:] if word.startswith("./") else word)
    return list(dict.fromkeys(found))


def outside(files: list[str], paths: list[str]) -> list[str]:
    """The changed files in none of the slice's paths: not the path itself, under it as a folder, matching it as
    a pattern, or (a bare file name) named by it."""
    def inside(path: str) -> bool:
        for given in paths:
            folder = given.rstrip("/")
            if path == folder or path.startswith(folder + "/") or fnmatch.fnmatchcase(path, given) \
                    or ("/" not in given and path.rsplit("/", 1)[-1] == given):
                return True
        return False
    return [path for path in files if not inside(path)]
