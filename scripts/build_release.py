#!/usr/bin/env python3
"""Build the release tree: the files of this checkout that run, and nothing else (D45).

    python scripts/build_release.py <out-dir>

Writes into <out-dir>, which must be empty or not exist yet, every file git tracks under SHIPPED, with
its bytes as they are in this checkout and its mode as git records it (bin/council and the hook scripts
stay executable), and three files written for the tree: plugin.json without what points into the dev
tree, a marketplace.json whose entry is the tree itself ("./"), and a short README.md. Untracked and
ignored files (.venv, caches) never go, and nothing in the tree depends on the time or the machine, so
two builds of one commit are byte-identical. .github/workflows/release.yml runs it at each v* tag and
commits the tree to the release branch; CONTRIBUTING.md (Releasing) has the same steps by hand.

Python 3.8+, standard library only.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every path that ships, and why: the one list. A folder ships every tracked file under it.
SHIPPED = (
    (".claude-plugin/plugin.json", "the manifest Claude Code loads; written: experimental.evals points into evals/"),
    (".claude-plugin/marketplace.json", "the tree as its own marketplace (source \"./\"), for <repo>#release; written"),
    (".gitattributes", "LF line ends in the clone Claude Code makes, so bash can run the hooks on Windows"),
    ("agents", "the worker, verifier and builder contracts Claude Code loads"),
    ("bin", "bin/council, the helper's launcher, on the Bash tool's PATH"),
    ("hooks", "hooks.json, the hook scripts, and the council pane's mod (council-view.tsx, council-scene.ts)"),
    ("skills", "the modes and the standalone skills Claude Code loads"),
    ("references", "doctrine, run contracts, seat docs, templates: read by the Chair, the agents and the helper"),
    ("src", "the helper's Python package, which bin/council starts"),
    ("types", "plugin.json's types (./types/index.d.ts), which the mod imports"),
    ("LICENSE", "the licence, which every copy carries"),
    ("NOTICE", "the credits the licences ask for"),
    ("README.md", "written for the tree: what it is, its version, where the repository is"),
)
WRITTEN = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "README.md")
DEV_ONLY_KEYS = ("evals",)          # plugin.json's experimental keys that name a dev-tree path


class Refusal(Exception):
    """A build that can't go on: the message says why, and what to do next (D19)."""


def git(*words: str) -> bytes:
    done = subprocess.run(["git", "-C", str(ROOT), *words], capture_output=True)
    if done.returncode != 0:
        raise Refusal("git %s failed in %s (%s): run the build from a git checkout of Small Council"
                      % (" ".join(words), ROOT, done.stderr.decode("utf-8", "replace").strip()))
    return done.stdout


def top_entries() -> list:
    """The tree's top-level names, as the release eval expects them."""
    return sorted({path.split("/")[0] for path, _ in SHIPPED})


def tracked() -> list:
    """(path, mode) of every tracked file under SHIPPED, the written ones left out, in git's order."""
    paths = [p for p, _ in SHIPPED if p not in WRITTEN]
    found = []
    for record in git("ls-files", "-s", "-z", "--", *paths).split(b"\0"):
        if not record:
            continue
        head, path = record.decode("utf-8").split("\t", 1)
        mode = head.split(" ")[0]
        if mode not in ("100644", "100755"):
            raise Refusal("%s is tracked as mode %s (a link or a submodule), which the release tree can't carry: "
                          "make it a plain file, or take it off SHIPPED in scripts/build_release.py" % (path, mode))
        found.append((path, mode))
    return found


def manifest(name: str) -> dict:
    return json.loads((ROOT / ".claude-plugin" / name).read_text(encoding="utf-8"))


def plugin_json() -> dict:
    """main's plugin.json without the experimental keys that name a dev-tree path."""
    plugin = manifest("plugin.json")
    extra = {k: v for k, v in (plugin.get("experimental") or {}).items() if k not in DEV_ONLY_KEYS}
    plugin.pop("experimental", None)
    if extra:
        plugin["experimental"] = extra
    return plugin


def marketplace_json() -> dict:
    """main's marketplace.json with each entry's source the tree itself."""
    market = manifest("marketplace.json")
    for entry in market.get("plugins") or []:
        entry["source"] = "./"
    return market


def readme(plugin: dict) -> str:
    repo = plugin.get("repository", "")
    market = manifest("marketplace.json")["name"]
    return "\n".join([
        "# %s %s" % (plugin.get("displayName") or plugin["name"], plugin.get("version", "")),
        "",
        plugin.get("description", ""),
        "",
        "This is the release branch: only the files the plugin runs. It is built from a tagged commit of",
        "main by [its build script](%s/blob/main/scripts/build_release.py) and never edited by hand. The" % repo,
        "source, the docs, the tests and the changelog are in the repository: %s" % repo,
        "",
        "Install, in Claude Code:",
        "",
        "```",
        "/plugin marketplace add %s" % repo.split("github.com/")[-1],
        "/plugin install %s@%s" % (plugin["name"], market),
        "```",
        "",
        "Licence: MIT, see [LICENSE](LICENSE). Credits: [NOTICE](NOTICE).",
        "",
    ])


def as_json(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def written() -> dict:
    plugin = plugin_json()
    return {".claude-plugin/plugin.json": as_json(plugin), ".claude-plugin/marketplace.json": as_json(marketplace_json()),
            "README.md": readme(plugin).encode("utf-8")}


def place(out: Path, path: str, data: bytes, mode: str) -> None:
    target = out.joinpath(*path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    os.chmod(str(target), 0o755 if mode == "100755" else 0o644)


def build(out: Path) -> tuple:
    """Write the tree into out; (files, bytes, the executable paths)."""
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise Refusal("%s is not an empty folder: name a new or empty one (the build never writes over files)" % out)
    files = tracked()
    missing = [path for path, _ in files if not (ROOT / path).is_file()]
    if missing:
        raise Refusal("tracked but not on disk: %s — restore them (git checkout -- <path>) or commit their removal"
                      % ", ".join(missing[:5]))
    out.mkdir(parents=True, exist_ok=True)
    size = 0
    for path, mode in files:
        data = (ROOT / path).read_bytes()
        place(out, path, data, mode)
        size += len(data)
    for path, data in written().items():
        place(out, path, data, "100644")
        size += len(data)
    return len(files) + len(WRITTEN), size, [path for path, mode in files if mode == "100755"]


def main(words: list) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")    # Windows consoles default to cp1252
    if len(words) != 1 or words[0].startswith("-"):
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        print("build_release: name the folder to write the tree into, one new or empty folder", file=sys.stderr)
        return 2
    out = Path(words[0]).resolve()
    try:
        count, size, executable = build(out)
    except Refusal as why:
        print("build_release: %s" % why, file=sys.stderr)
        return 2
    print("Wrote %s — %d files, %d bytes, version %s" % (out.as_posix(), count, size, plugin_json().get("version")))
    print("executable: %s" % " ".join(executable))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
