"""council fingerprint [check]: the stack's fingerprint — the manifests at most two folders deep and the languages with
three files or more, from git's file list — and its hash; check compares it with the config's stack-fingerprint:
line and exits 1 when the stack changed (council doctor reads the same)."""
from __future__ import annotations

import re
import subprocess

from council.commands import cli
from council.records import config
from council.records import home as where

MANIFESTS = re.compile(
    r"package\.json|deno\.json|tsconfig\.json|pyproject\.toml|requirements\.txt|setup\.py|Pipfile|environment\.yml"
    r"|go\.mod|Cargo\.toml|pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|Gemfile|composer\.json|mix\.exs"
    r"|rebar\.config|pubspec\.yaml|Package\.swift|project\.pbxproj|Podfile|project\.godot|ProjectVersion\.txt"
    r"|.*\.uproject|CMakeLists\.txt|meson\.build|Makefile|west\.yml|platformio\.ini|Dockerfile|compose\.ya?ml"
    r"|docker-compose\.ya?ml|.*\.csproj|.*\.fsproj|.*\.sln|.*\.tf|flake\.nix|BUILD(\.bazel)?|WORKSPACE", re.S)
LANGUAGES = frozenset(
    ["py", "pyx", "ipynb", "ts", "tsx", "js", "jsx", "mjs", "cjs", "vue", "svelte", "go", "rs", "java", "kt", "kts",
     "scala", "clj", "groovy", "swift", "m", "mm", "c", "h", "cc", "cpp", "cxx", "hh", "hpp", "cs", "fs", "vb", "rb",
     "php", "ex", "exs", "erl", "hrl", "dart", "lua", "gd", "r", "jl", "sql", "sh", "bash", "ps1", "tf", "hcl",
     "proto", "graphql", "zig", "nim", "ml", "hs", "elm", "sol", "asm", "s", "ino", "glsl", "hlsl", "wgsl", "shader",
     "tscn", "nix"])
_WILD = re.compile(r".*\.(tf|csproj|fsproj|sln|uproject)\Z", re.S)
_EXT = re.compile(r".*\.([A-Za-z0-9+]{1,10})\Z", re.S)
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_ITEMS = re.compile(", | · |: ")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "fingerprint")
    if len(words) > 1 or words[:1] not in ([], ["check"]):
        raise cli.Refusal("usage: council fingerprint [check]")
    if _git("rev-parse", "--git-dir")[0] != 0:
        raise cli.Refusal("the stack fingerprint needs a git repository")
    if words:
        found, said = check()
        cli.say(said)
        return found
    summary = stack_summary()
    cli.say("stack-fingerprint: %s — %s" % (digest(summary), summary))
    return 0


def _git(*args: str, given: bytes | None = None, cwd: str | None = None) -> tuple[int, bytes]:
    try:
        done = subprocess.run(["git"] + list(args), input=given, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              cwd=cwd)
    except OSError:
        return 127, b""
    return done.returncode, done.stdout


def _bytes_key(text: str) -> bytes:
    return text.encode("utf-8", "surrogateescape")


def stack_summary() -> str:
    """'manifests: <names> · languages: <extensions>' (none for an empty list), each list in byte order."""
    top = _git("rev-parse", "--show-toplevel")[1].decode("utf-8", "surrogateescape").rstrip("\n")
    out = _git("-c", "core.quotePath=false", "ls-files", cwd=where.native(top) if top else None)[1]   # the whole repo
    files = out.decode("utf-8", "surrogateescape").rstrip("\n").split("\n")
    names = {_WILD.sub(r"*.\1", f.rsplit("/", 1)[-1]) for f in files
             if f.count("/") <= 2 and MANIFESTS.fullmatch(f.rsplit("/", 1)[-1])}
    seen: dict[str, int] = {}
    for f in files:
        ext = _EXT.match(f)
        word = ext.group(1).translate(_ASCII_LOWER) if ext else ""
        if word in LANGUAGES:
            seen[word] = seen.get(word, 0) + 1
    langs = sorted((w for w, n in seen.items() if n >= 3), key=_bytes_key)
    return "manifests: %s · languages: %s" % (", ".join(sorted(names, key=_bytes_key)) or "none",
                                              ", ".join(langs) or "none")


def digest(summary: str) -> str:
    """git hash-object of the summary, cut to 12 characters."""
    return _git("hash-object", "--stdin", given=summary.encode("utf-8", "surrogateescape"))[1].decode()[:12]


def minus(have: str, lacks: str) -> str:
    """Items of summary `have` that summary `lacks` doesn't list."""
    other = set(_ITEMS.split(lacks))
    return ", ".join(item for item in _ITEMS.split(have)
                     if item not in ("", "manifests", "languages", "none") and item not in other)


def check() -> tuple[int, str]:
    """(exit code, line): 1 when the stack changed since the config's fingerprint."""
    summary = stack_summary()
    hashed = digest(summary)
    line = config.field(where.council_home(), "stack-fingerprint")
    if line.startswith("stack-fingerprint: "):         # a pasted line that repeats the key still reads
        line = line[len("stack-fingerprint: "):]
    if not line:
        return 0, ("no stack-fingerprint in the config — a council-init refresh records one: stack-fingerprint: %s "
                   "— %s" % (hashed, summary))
    if line.split(" ", 1)[0] == hashed:
        return 0, "fingerprint: the stack is unchanged since council-init (%s)" % hashed
    recorded = line.split(" — ", 1)[1] if " — " in line else line
    return 1, ("fingerprint: the stack changed since council-init — added: %s · removed: %s. Suggest a council-init "
               "refresh." % (minus(summary, recorded) or "nothing", minus(recorded, summary) or "nothing"))
