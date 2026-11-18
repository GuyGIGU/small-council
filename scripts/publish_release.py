#!/usr/bin/env python3
"""Publish the release tree: build it, check it, and add it to the release branch as one commit (D45).

    python scripts/publish_release.py <remote> <branch>       # e.g. origin release

<remote> is a remote of this checkout by name (origin), a URL or a path. In order, stopping at the first
step that fails, with nothing pushed:
1. build the tree of this checkout into a folder of its own (scripts/build_release.py, which refuses a
   checkout whose shipped files have uncommitted changes) and keep the build's records: each file's path,
   git mode and the sha256 of its bytes;
2. run the release eval on that folder (evals/run_release.py --tree); a tree it fails is never published;
3. check the folder holds exactly the build's records: nothing changed, nothing found beside them;
4. read the branch's tip on the remote, if it has one. The same tree is nothing to do (exit 0). Another
   tree whose plugin.json version is not greater than the tip's is refused (exit 2: bump the version), since
   an installed copy updates only when the version changes;
5. commit the records alone, with the build's modes (never the file system's), in a scratch repository,
   the tip as parent (none on a first publish), message "Small Council v<version>", and push it, never forced.
This checkout's own .git is never written. With PUBLISH_TOKEN set (the release workflow), git authenticates
to the remote with it through its environment (GIT_CONFIG_COUNT/KEY/VALUE, an http.extraHeader): the token is
never printed, never on a command line and never in a config file, and the eval never sees it.
Versions compare as major.minor.patch, a pre-release (1.2.0-rc1) below its release; two pre-releases of
one version compare equal.

Python 3.8+, standard library only.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import build_release
from build_release import Refusal

ROOT = build_release.ROOT
CHECK = [sys.executable, str(ROOT / "evals" / "run_release.py"), "--tree"]
PLUGIN = ".claude-plugin/plugin.json"


def version_of(text: str) -> tuple:
    """(major, minor, patch, 1 for a release or 0 for a pre-release) of a plugin.json's text; () if unreadable."""
    try:
        value = str(json.loads(text).get("version", ""))
    except (ValueError, AttributeError):
        return ()
    found = re.match(r"(\d+)\.(\d+)\.(\d+)(-)?", value)
    return (int(found.group(1)), int(found.group(2)), int(found.group(3)), 0 if found.group(4) else 1) if found else ()


def git_env() -> dict:
    """The environment for git: the token, when there is one, as an http header git reads from it."""
    env = {k: v for k, v in os.environ.items() if k not in ("PUBLISH_TOKEN", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    token = os.environ.get("PUBLISH_TOKEN", "")
    if token:
        basic = base64.b64encode(("x-access-token:" + token).encode("utf-8")).decode("ascii")
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                   GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + basic)
    return env


def git(repo: Path, *words: str, data: bytes = b"", ok: tuple = (0,)) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), *words], input=data, capture_output=True, env=git_env())
    if done.returncode not in ok:
        raise Refusal("git %s failed (exit %d: %s): nothing was pushed; check the remote and your access to it"
                      % (words[0], done.returncode, done.stderr.decode("utf-8", "replace").strip()[-300:]))
    return done.stdout


def remote_url(remote: str) -> str:
    """A remote of this checkout by name as its URL; a folder as its absolute path; anything else as given."""
    named = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", remote], capture_output=True, text=True)
    if named.returncode == 0 and named.stdout.strip():
        return named.stdout.strip()
    return str(Path(remote).resolve()) if Path(remote).is_dir() else remote


def changes(folder: Path, records: list) -> list:
    """What in folder differs from the build's records: a file changed, missing or found beside them."""
    want = {path: digest for path, _, digest in records}
    found = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    out = ["found beside the build: %s" % p for p in found if p not in want]
    for path, digest in sorted(want.items()):
        target = folder / path
        if not target.is_file():
            out.append("missing: %s" % path)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            out.append("changed: %s" % path)
    return out


def tree_of(repo: Path, folder: Path, records: list) -> str:
    """The git tree of the records alone: their bytes from folder, their modes from the build."""
    paths = "".join(str(folder.joinpath(*path.split("/"))) + "\n" for path, _, _ in records)
    shas = git(repo, "hash-object", "-w", "--stdin-paths", data=paths.encode("utf-8")).decode("ascii").split()
    info = "".join("%s %s\t%s\n" % (mode, sha, path) for (path, mode, _), sha in zip(records, shas))
    git(repo, "update-index", "--index-info", data=info.encode("utf-8"))
    return git(repo, "write-tree").decode("ascii").strip()


def tip(repo: Path, url: str, branch: str) -> tuple:
    """The branch's tip on the remote, fetched into repo: (commit, tree, version), or () when it has none."""
    if not git(repo, "ls-remote", "--heads", url, "refs/heads/" + branch).strip():
        return ()
    git(repo, "fetch", "--quiet", "--no-tags", "--depth=1", url, "refs/heads/" + branch)
    commit = git(repo, "rev-parse", "FETCH_HEAD").decode("ascii").strip()
    tree = git(repo, "rev-parse", "FETCH_HEAD^{tree}").decode("ascii").strip()
    shown = git(repo, "show", "FETCH_HEAD:" + PLUGIN, ok=(0, 128)).decode("utf-8", "replace")
    return commit, tree, version_of(shown)


def publish_tree(folder: Path, records: list, remote: str, branch: str) -> str:
    """Commit the records onto the branch on the remote, or say there is nothing to do; refuse a version
    that is not newer than the branch's. Returns the line to print."""
    text = (folder / PLUGIN).read_text(encoding="utf-8")
    version, named = version_of(text), json.loads(text).get("version", "")
    if not version:
        raise Refusal("the tree's plugin.json has no version git can compare (%r): set one, major.minor.patch" % named)
    url = remote_url(remote)
    with tempfile.TemporaryDirectory(prefix="council-publish-") as tmp:
        repo = Path(tmp)
        git(repo, "init", "--quiet")
        tree, top = tree_of(repo, folder, records), tip(repo, url, branch)
        if top and top[1] == tree:
            return "Nothing to publish: %s already holds this tree (Small Council v%s)" % (branch, named)
        if top and not top[2]:
            raise Refusal("%s's tip %s has no plugin.json with a version, so it is no release tree: name the "
                          "release branch, or a new one" % (branch, top[0][:12]))
        if top and version <= top[2]:
            raise Refusal("%s holds version %s and this tree is %s with other files: an installed copy only updates "
                          "when the version rises — bump version in %s (and help.py, CHANGELOG.md), then publish again"
                          % (branch, ".".join(map(str, top[2][:3])) or "unreadable", named, PLUGIN))
        parent = ["-p", top[0]] if top else []
        commit = git(repo, "commit-tree", tree, *parent, "-m", "Small Council v%s" % named).decode("ascii").strip()
        git(repo, "push", "--quiet", url, "%s:refs/heads/%s" % (commit, branch))
    return "Published %s at %s: Small Council v%s (%s)" % (branch, commit, named,
                                                          "parent %s" % top[0] if top else "its first commit")


def publish_built(folder: Path, records: list, remote: str, branch: str, check: list = CHECK) -> str:
    """Run the release eval on the built folder, check it still holds the build alone, then publish it."""
    env = {k: v for k, v in os.environ.items() if k != "PUBLISH_TOKEN"}
    done = subprocess.run([*check, str(folder)], env=env)
    if done.returncode != 0:
        raise Refusal("the release eval failed on the built tree (exit %d): fix what it names, then publish "
                      "again; nothing was pushed" % done.returncode)
    moved = changes(folder, records)
    if moved:
        raise Refusal("the built tree changed after the build (%s): nothing was pushed; publish again from a "
                      "clean checkout" % "; ".join(moved[:5]))
    return publish_tree(folder, records, remote, branch)


def main(words: list) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")    # Windows consoles default to cp1252
    if len(words) != 2 or any(w.startswith("-") for w in words):
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        print("publish_release: name the remote and the branch, as in: origin release", file=sys.stderr)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="council-release-") as tmp:
            folder = Path(tmp) / "tree"
            line = publish_built(folder, build_release.build(folder), *words)
    except Refusal as why:
        print("publish_release: %s" % why, file=sys.stderr)
        return 2
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
