"""council init's default roster: the catalog's seats as it names them (references/roster/expert-catalog.md, its
Canonical seats table), each with the surface markers the file list shows for it. No seat's "applies when" rule can be
decided from a file list alone (a UI may live in plain Python, a store in any file it writes), so the default roster
drops none: a seat the files show nothing for is included with no marker, and Assign judges it by its lens."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import cells

CATALOG = "references/roster/expert-catalog.md"
ALWAYS = ("fowler", "beck")
MARKERS = 6
UI = ("tsx", "jsx", "vue", "svelte", "astro", "dart", "xaml", "razor", "storyboard", "xib")
# What in a file list shows a seat's surface: file extensions, and words a folder or file name is made of.
EXTENSIONS = {"dodds": UI, "saarinen": UI + ("css", "scss", "sass", "less", "html"), "friedman": UI + ("html",),
              "pickering": UI + ("html",), "leach": ("sql", "prisma"), "nygard": ("tf",)}
WORDS = {
    "hunt": ("auth", "authn", "authz", "authentication", "login", "session", "sessions", "token", "tokens", "secret",
             "secrets", "crypto", "password", "passwords", "permissions"),
    "collina": ("api", "server", "routes", "router", "handlers", "controllers", "endpoints", "middleware"),
    "leach": ("migrations", "migrate", "schema", "models", "db", "database", "repository", "store", "storage"),
    "perf": ("bench", "benches", "benchmark", "benchmarks", "perf"),
    "willison": ("prompt", "prompts", "llm", "openai", "anthropic", "embedding", "embeddings"),
    "goetz": ("worker", "workers", "queue", "queues", "thread", "threads", "concurrent", "pool", "scheduler", "jobs"),
    "patterson": ("parse", "parser", "parsers", "parsing", "decode", "decoder", "upload", "uploads", "codec",
                  "protocol", "deserialize"),
    "nygard": ("dockerfile", "deploy", "deployment", "helm", "k8s", "kubernetes", "terraform", "workflows",
               "procfile"),
}
TEST_DIRS = ("test", "tests", "spec", "specs", "__tests__", "testing")
TEST_FILES = (("**/test_*.py", r"test_[^/]*\.py"), ("**/*_test.py", r"[^/]*_test\.py"),
              ("**/*_test.go", r"[^/]*_test\.go"),
              ("**/*.test.*", r"[^/]*\.test\.[^/.]+"), ("**/*.spec.*", r"[^/]*\.spec\.[^/.]+"),
              ("**/*Test.java", r"[^/]*Test\.java"), ("**/*Tests.cs", r"[^/]*Tests\.cs"),
              ("**/*_spec.rb", r"[^/]*_spec\.rb"))


class Seat(NamedTuple):
    """A catalog seat as the roster row writes it, with the markers the file list shows."""

    practitioner: str
    slug: str
    lens: str
    doc: str
    markers: tuple[str, ...]


def catalog(plugin: str) -> list[tuple[str, str, str, str]]:
    """(practitioner, slug, lens, references/<doc>) of each row of the catalog's Canonical seats table."""
    try:
        text = Path(plugin, CATALOG).read_bytes().decode("utf-8", "replace")
    except OSError:
        return []
    found, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Canonical seats"
            continue
        cut = [re.sub(r"[`*]", "", cell).strip() for cell in cells.table_cells(line)] if inside else []
        if len(cut) < 6 or cut[1] in ("Seat", "") or re.fullmatch(r":?-+:?", cut[1]):
            continue
        found.append((cut[1], cut[2], cut[3], "references/" + cut[4]))
    return found


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def markers(slug: str, files: list[str]) -> tuple[str, ...]:
    """The surface markers the file list shows for a seat: a glob per extension present, a folder or a file whose
    name is one of the seat's words, the test folders and file shapes for Beck; at most six, most files first."""
    counts: dict[str, int] = {}
    exts, words = EXTENSIONS.get(slug, ()), set(WORDS.get(slug, ()))
    for path in files:
        parts = path.split("/")
        for marker in _file_markers(slug, parts, exts, words):
            counts[marker] = counts.get(marker, 0) + 1
    if slug == "fowler":
        return ("whatever no other seat claims",)
    ranked = sorted(counts, key=lambda m: (-counts[m], m))
    return tuple(ranked[:MARKERS])


def _file_markers(slug: str, parts: list[str], exts: tuple[str, ...], words: set[str]) -> list[str]:
    """The markers one file path gives a seat."""
    found = []
    name = parts[-1]
    ext = name.rsplit(".", 1)[1].lower() if "." in name else ""
    if ext in exts:
        found.append("**/*." + ext)
    for i, part in enumerate(parts[:-1]):
        if words & set(_tokens(part)) or (slug == "beck" and part.lower() in TEST_DIRS):
            found.append("/".join(parts[:i + 1]) + "/**")
            break
    stem = name.rsplit(".", 1)[0] if "." in name else name
    if words & set(_tokens(stem)):
        found.append("**/" + name)
    if slug == "beck":
        found += [glob for glob, shape in TEST_FILES if re.fullmatch(shape, name)]
    return found


def default_roster(plugin: str, files: list[str]) -> list[Seat]:
    """Every catalog seat, in the catalog's order, each with its markers from the file list."""
    return [Seat(who, slug, lens, doc, markers(slug, files)) for who, slug, lens, doc in catalog(plugin)]


def row(seat: Seat, note: str) -> str:
    """The seat's Roster row: Seat, Slug, Lens, Surface, Reference, Recast note."""
    surface = ", ".join("`%s`" % m for m in seat.markers) if seat.markers else "no marker in the file list yet"
    if seat.slug == "fowler":
        surface = seat.markers[0]
    return "| %s | %s | %s | %s | %s | %s |" % (seat.practitioner, seat.slug, seat.lens, surface, seat.doc, note)
