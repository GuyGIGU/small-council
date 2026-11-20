"""council init detect's watch lists: the shipped lists as references/watch-lists.md names them (its one table), each
with what the file list shows for it. No list's "applies when" rule can be decided from a file list alone (a UI may
live in plain Python, a store in any file it writes), so every list is printed: one the files show nothing for is
left to its rule, which setup judges with the owner."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import cells

PAGE = "references/watch-lists.md"
ALWAYS = {"refactoring": "every codebase has structure"}
MARKERS = 6
UI = ("tsx", "jsx", "vue", "svelte", "astro", "dart", "xaml", "razor", "storyboard", "xib")
# What in a file list shows a list's part of the stack: file extensions, and words a folder or file name is made of.
EXTENSIONS = {"quality-frontend": UI, "quality-ui": UI + ("css", "scss", "sass", "less", "html"),
              "quality-ux": UI + ("html",), "quality-accessibility": UI + ("html",),
              "quality-postgres": ("sql", "prisma"), "quality-operability": ("tf",)}
WORDS = {
    "security": ("auth", "authn", "authz", "authentication", "login", "session", "sessions", "token", "tokens",
                 "secret", "secrets", "crypto", "password", "passwords", "permissions"),
    "quality-backend": ("api", "server", "routes", "router", "handlers", "controllers", "endpoints", "middleware"),
    "quality-postgres": ("migrations", "migrate", "schema", "models", "db", "database", "repository", "store",
                         "storage"),
    "quality-performance": ("bench", "benches", "benchmark", "benchmarks", "perf"),
    "quality-llm": ("prompt", "prompts", "llm", "openai", "anthropic", "embedding", "embeddings"),
    "quality-concurrency": ("worker", "workers", "queue", "queues", "thread", "threads", "concurrent", "pool",
                            "scheduler", "jobs"),
    "untrusted-input": ("parse", "parser", "parsers", "parsing", "decode", "decoder", "upload", "uploads", "codec",
                        "protocol", "deserialize"),
    "quality-operability": ("dockerfile", "deploy", "deployment", "helm", "k8s", "kubernetes", "terraform",
                            "workflows", "procfile"),
}
TESTS = "quality-testing"
TEST_DIRS = ("test", "tests", "spec", "specs", "__tests__", "testing")
TEST_FILES = (("**/test_*.py", r"test_[^/]*\.py"), ("**/*_test.py", r"[^/]*_test\.py"),
              ("**/*_test.go", r"[^/]*_test\.go"),
              ("**/*.test.*", r"[^/]*\.test\.[^/.]+"), ("**/*.spec.*", r"[^/]*\.spec\.[^/.]+"),
              ("**/*Test.java", r"[^/]*Test\.java"), ("**/*Tests.cs", r"[^/]*Tests\.cs"),
              ("**/*_spec.rb", r"[^/]*_spec\.rb"))


class Listed(NamedTuple):
    """A shipped watch list as detect prints it, with the markers the file list shows."""

    name: str
    covers: str
    page: str
    markers: tuple[str, ...]


def shipped(plugin: str) -> list[tuple[str, str]]:
    """(name, what it covers) of each row of the watch-lists page's table, in its order."""
    try:
        text = Path(plugin, PAGE).read_bytes().decode("utf-8", "replace")
    except OSError:
        return []
    found = []
    for line in text.splitlines():
        cut = [re.sub(r"[`*]", "", cell).strip() for cell in cells.table_cells(line)] if line.startswith("|") else []
        if len(cut) < 4 or cut[1] in ("Watch list", "") or re.fullmatch(r":?-+:?", cut[1]):
            continue
        found.append((cut[1], cut[2]))
    return found


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def markers(name: str, files: list[str]) -> tuple[str, ...]:
    """What the file list shows for a list: a glob per extension present, a folder or a file whose name is one of
    the list's words, the test folders and file shapes for the tests list; at most six, most files first."""
    counts: dict[str, int] = {}
    exts, words = EXTENSIONS.get(name, ()), set(WORDS.get(name, ()))
    for path in files:
        parts = path.split("/")
        for marker in _file_markers(name, parts, exts, words):
            counts[marker] = counts.get(marker, 0) + 1
    ranked = sorted(counts, key=lambda m: (-counts[m], m))
    return tuple(ranked[:MARKERS])


def _file_markers(name: str, parts: list[str], exts: tuple[str, ...], words: set[str]) -> list[str]:
    """The markers one file path gives a list."""
    found = []
    file = parts[-1]
    ext = file.rsplit(".", 1)[1].lower() if "." in file else ""
    if ext in exts:
        found.append("**/*." + ext)
    for i, part in enumerate(parts[:-1]):
        if words & set(_tokens(part)) or (name == TESTS and part.lower() in TEST_DIRS):
            found.append("/".join(parts[:i + 1]) + "/**")
            break
    stem = file.rsplit(".", 1)[0] if "." in file else file
    if words & set(_tokens(stem)):
        found.append("**/" + file)
    if name == TESTS:
        found += [glob for glob, shape in TEST_FILES if re.fullmatch(shape, file)]
    return found


def found(plugin: str, files: list[str]) -> list[Listed]:
    """Every shipped watch list, in the page's order, each with its markers from the file list."""
    return [Listed(name, covers, "references/%s.md" % name, markers(name, files)) for name, covers in shipped(plugin)]


def line(listed: Listed) -> str:
    """One list as detect prints it: its name, what it covers, its page, and what the files show for it."""
    seen = ALWAYS.get(listed.name) or ", ".join(listed.markers) or \
        'nothing in the file list (its "applies when" rule decides)'
    return "watch list: %s · %s · %s · seen: %s" % (listed.name, listed.covers, listed.page, seen)
