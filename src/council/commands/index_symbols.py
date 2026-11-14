"""What `council index` says about one changed file beyond its hunks (the helper's diff_symbols, not_indexed,
no_symbols and is_test_path): the definitions its diff names, where else each name is used, and the tests that
name the file — a starting point for tracing, not proof. Heuristic and language-agnostic: def/class/func/fn/…,
const-arrow functions, Go methods, shell "name() {", and C-style signatures, never a bare call."""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess

COMMON = ("if for while return switch catch else elif function def class self this true false null none nil new try "
          "with from import export async await public private protected static void int string bool var let const "
          "func fn match case default print main")
SKIP = frozenset(COMMON.split())             # words too common to trace
METHOD = re.compile(r"func[ \t]*\([^)]*\)[ \t]*[A-Za-z_][A-Za-z0-9_]*")
KEYWORD = re.compile(r"[ \t](def|class|function|func|fn|sub|interface|struct|enum|trait|type|module|signal|class_name)"
                     r"[ \t]+[A-Za-z_][A-Za-z0-9_]*")
ARROW = re.compile(r"[ \t](const|let|var)[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*=[ \t]*(async[ \t]*)?(\(|function)")
SHELL = re.compile(r"[ \t]*[A-Za-z_][A-Za-z0-9_]*[ \t]*\(\)[ \t]*(\{|$)")
FLOW = re.compile(r"(if|for|while|switch|return|else|do|case|catch|elif)[ \t(]")
SIGNATURE = re.compile(r"[A-Za-z_][A-Za-z0-9_:<>,*& \t]*[ \t*&][A-Za-z_][A-Za-z0-9_]*[ \t]*\(")
SEARCHED = "callers and tests not searched (search budget spent)"
TEST_GLOBS = (":(glob)**/test/**", ":(glob)**/tests/**", ":(glob)**/spec/**", ":(glob)**/__tests__/**",
              ":(glob)**/test_*", ":(glob)**/*_test.*", ":(glob)**/*.test.*", ":(glob)**/*.spec.*",
              ":(glob)**/*_spec.*", ":(glob)**/*Test.*")
NOT_INDEXED = ("*package-lock.json", "*yarn.lock", "*pnpm-lock.yaml", "*poetry.lock", "*Pipfile.lock", "*Cargo.lock",
               "*go.sum", "*composer.lock", "*Gemfile.lock", "*.lock", "node_modules/*", "*/node_modules/*",
               "vendor/*", "*/vendor/*", "dist/*", "*/dist/*", "build/*", "*/build/*", "*.min.js", "*.min.css",
               "*.map")
NO_SYMBOLS = ("*.md", "*.markdown", "*.txt", "*.rst", "*.adoc", "*.json", "*.yml", "*.yaml", "*.toml", "*.ini",
              "*.cfg", "*.conf", "*.csv", "*.tsv", "*.svg", "*.xml", "*.html", "*.css", "*.scss", "*.lock", "*.env")
TEST_PATHS = ("test/*", "tests/*", "spec/*", "*/test/*", "*/tests/*", "*/spec/*", "*/__tests__/*", "*/testing/*",
              "test_*", "*/test_*", "*_test.*", "*.test.*", "*.spec.*", "*_spec.*", "*Test.*", "*Tests.*")


def _any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def not_indexed(path: str) -> bool:
    """Lockfiles, vendored and generated files: never part of the index."""
    return _any(path, NOT_INDEXED)


def no_symbols(path: str) -> bool:
    """Text and data files: their hunks are listed, but they have no symbols worth tracing."""
    return _any(path, NO_SYMBOLS)


def is_test_path(path: str) -> bool:
    return _any(path, TEST_PATHS)


def definition(line: str) -> str:
    """The name a line defines, or ''."""
    padded = " " + line
    found = METHOD.search(padded)
    if found:
        return re.sub(r"^.*[) \t]", "", found.group(0), count=1)
    found = KEYWORD.search(padded)
    if found:
        return re.sub(r"^.*[ \t]", "", found.group(0), count=1)
    found = ARROW.search(padded)
    if found:
        return re.sub(r"[ \t]*=.*$", "", re.sub(r"^[ \t]*(const|let|var)[ \t]+", "", found.group(0), count=1), count=1)
    found = SHELL.match(line)
    if found:
        return re.sub(r"[ \t]*\(.*$", "", found.group(0).lstrip(" \t"), count=1)
    if not re.match(r"[ \t]", line) and not re.search(r";[ \t]*$", line) and not FLOW.match(line):
        found = SIGNATURE.match(line)
        if found:
            return re.sub(r"^.*[ \t*&:]", "", re.sub(r"[ \t]*\($", "", found.group(0), count=1), count=1)
    return ""


def symbols(diff: list[str]) -> list[str]:
    """Up to 8 names defined in a diff's lines (+/-) and its hunk headers' context, each once."""
    found: list[str] = []
    for line in diff:
        if len(found) >= 8:
            break
        if line.startswith("@@"):
            name = definition(re.sub(r"^@@[^@]*@@[ \t]*", "", line, count=1))
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith(("+", "-")):
            name = definition(line[1:])
        else:
            continue
        if len(name.encode("utf-8", "surrogateescape")) >= 3 and name not in found and name not in SKIP:
            found.append(name)
    return found


def _grep(*args: str) -> list[str]:
    try:
        done = subprocess.run(["git", "grep"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL)
    except OSError:
        return []
    found = done.stdout.decode("utf-8", "surrogateescape").split("\n")
    found = found[:-1] if found and found[-1] == "" else found
    return [line[:-1] if os.name == "nt" and line.endswith("\r") else line for line in found]


class Search:
    """The run's git grep budget: 80 searches across the whole index."""

    def __init__(self) -> None:
        self.budget = 80

    def callers(self, path: str, names: list[str]) -> tuple[str, str]:
        """Where else each name is used (four places a name), and a note when the budget ran out first."""
        found = []
        for name in names:
            if self.budget <= 0:
                return " · ".join(found), SEARCHED
            self.budget -= 1
            hits = [line for line in _grep("-n", "-I", "-w", "-F", "-e", name, "--", ".", ":(exclude)" + path)
                    if not line.startswith(".council/")][:4]
            said = " · ".join("%s:%s (%s)" % ((line.split(":") + [""])[0], (line.split(":") + ["", ""])[1], name)
                              for line in hits)
            if said:
                found.append(said)
        return " · ".join(found), ""

    def tests(self, path: str, note: str) -> tuple[str, str]:
        """The test files that name the file's stem (four), '(this is a test file)', or the budget's note."""
        stem = path.rsplit("/", 1)[-1]
        stem = stem[:stem.rindex(".")] if "." in stem else stem
        if is_test_path(path):
            return "(this is a test file)", note
        if len(stem) < 3 or note:
            return "", note
        if self.budget <= 0:
            return "", SEARCHED
        self.budget -= 1
        named = _grep("-l", "-I", "-w", "-F", "-e", stem, "--", *TEST_GLOBS, ":(exclude)" + path)[:4]
        return ",".join(named).replace(",", ", "), note
