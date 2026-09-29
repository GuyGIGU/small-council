#!/usr/bin/env python3
"""Read-only, conservative comparison of finding citations with later Git changes.

"Changed after the run" describes timing only; it does not show that a council finding caused
the change. Claims without a trustworthy closed-run snapshot are left as can't tell.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cockpit  # noqa: E402

SCHEMA = "council.outcomes/1"
OUTCOMES = ("changed at cited lines", "file changed elsewhere", "unchanged", "file gone or renamed", "can't tell")
MAX_CLAIMS = 2000
MAX_ARTIFACT = 2 * 1024 * 1024
SAFE_PATH = re.compile(r"^[A-Za-z0-9_./@+-]+$")
CITATION = re.compile(r"^(.+):([1-9][0-9]*)(?:-([1-9][0-9]*))?$")


def git(repo, *args):
    try:
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        # A diff carries the project's own bytes, which the locale's code page may not decode; only
        # Git's ASCII headers are parsed, so an undecodable byte is replaced rather than fatal.
        result = subprocess.run(["git", "-C", str(repo)] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8", errors="replace", timeout=20, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def state_fields(path):
    fields = {}
    try:
        if path.is_symlink() or path.stat().st_size > 128 * 1024:
            return fields
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("## "):
                break
            key, sep, value = line.partition(":")
            if sep and key not in fields:
                fields[key.strip()] = value.strip()
    except (OSError, UnicodeError):
        pass
    return fields


def run_code_root(state, default):
    """Use a run's recorded working tree; only legacy runs without one use the caller's tree."""
    recorded = state.get("code-root")
    if not recorded or recorded == "-":
        return default
    if "\x00" in recorded:
        return None
    try:
        root = Path(recorded)
        return root if root.is_absolute() else None
    except (OSError, ValueError):
        return None


def parse_citation(value):
    if not isinstance(value, str):
        return None
    match = CITATION.fullmatch(value.strip())
    if not match:
        return None
    path = match.group(1).replace("\\", "/")
    if (not SAFE_PATH.fullmatch(path) or path.startswith("/") or
            any(part in ("", ".", "..") for part in path.split("/")) or
            re.match(r"^[A-Za-z]:", path)):
        return None
    start, end = int(match.group(2)), int(match.group(3) or match.group(2))
    if end < start or end - start > 100000:
        return None
    return path, start, end


def read_claims(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARTIFACT:
        return None
    claims = []
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    return None
                claims.append(row)
                if len(claims) > MAX_CLAIMS:
                    return None
    except (OSError, UnicodeError, ValueError):
        return None
    return claims


def reviewed_uncommitted(index):
    """Recognize the explicit dirty-tree marker written by council index."""
    try:
        if index.is_symlink() or not index.is_file() or index.stat().st_size > MAX_ARTIFACT:
            return False
        with index.open("r", encoding="utf-8-sig") as stream:
            first = stream.readline(4096)
            second = stream.readline(4096)
        return first.startswith("# Change index") and "+ uncommitted changes" in second
    except (OSError, UnicodeError):
        return False


def commit_at_close(repo, closed):
    if not closed:
        return None
    return git(repo, "rev-list", "-1", "--before=" + closed, "HEAD")


def tracked(repo, commit, path):
    return git(repo, "cat-file", "-e", commit + ":" + path) is not None


def parse_hunks(diff):
    """Return old-side line spans from unified diff; a zero-length span is an insertion after `start`."""
    spans = []
    for line in diff.splitlines():
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", line)
        if match:
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            spans.append((start, start + count - 1, count == 0))
    return spans


def file_changes(repo, close_commit, head, path):
    """One file's change from close to HEAD: an outcome for every citation of it, or its old-side hunks."""
    if not tracked(repo, close_commit, path):
        # A citation that was not present at the run's recorded close cannot be compared reliably.
        return "can't tell"
    if not tracked(repo, head, path):
        # git diff --name-status is consulted to distinguish a rename from a plain deletion.
        names = git(repo, "diff", "--no-color", "--name-status", "-M", close_commit, head, "--", path)
        if names:
            for row in names.splitlines():
                columns = row.split("\t")
                if columns and columns[0].startswith("R"):
                    return "file gone or renamed"
                if columns and columns[0] == "D":
                    return "file gone or renamed"
        return "file gone or renamed"
    # --no-color: a colour setting of "always" would wrap the @@ headers in escape codes.
    # --ignore-cr-at-eol: a file whose only change is its line endings (LF to CRLF) has no hunks.
    diff = git(repo, "diff", "--no-color", "--no-ext-diff", "--no-renames", "--ignore-cr-at-eol",
               "--unified=0", close_commit, head, "--", path)
    if diff is None:
        return "can't tell"
    if any(line.startswith("Binary files ") for line in diff.splitlines()):
        return "file changed elsewhere"
    # With no hunk, no line changed: Git may still print the file's header (or a mode change) when
    # every change was ignored, so an empty list, not empty output, is what reads as unchanged.
    return parse_hunks(diff)


def classify(repo, close_commit, head, claim, cache=None):
    """Sort one claim; `cache` is shared by one run's claims, so a file cited twice is compared once."""
    parsed = parse_citation(claim.get("citation"))
    if parsed is None or close_commit is None or head is None:
        return "can't tell"
    path, first, last = parsed
    cache = {} if cache is None else cache
    key = (close_commit, head, path)
    if key not in cache:
        cache[key] = file_changes(repo, close_commit, head, path)
    spans = cache[key]
    if isinstance(spans, str):
        return spans
    if not spans:
        return "unchanged"
    for start, end, insertion in spans:
        if insertion:
            # Lines inserted after old line `start`, inside or right next to the cited span, touch it:
            # a missing guard can only be cited by the lines around the gap (the helper's cite_hunks rule).
            touched = first - 1 <= start <= last
        else:
            # A modified or deleted old-side span must overlap the cited lines.
            touched = start <= last and end >= first
        if touched:
            return "changed at cited lines"
    return "file changed elsewhere"


def add_count(target, disposition, outcome):
    counts = target.setdefault(disposition, {name: 0 for name in OUTCOMES})
    counts[outcome] += 1


def outcomes(home, repo):
    home, repo = Path(home), Path(repo)
    head = git(repo, "rev-parse", "--verify", "HEAD")
    runs = []
    modes, seats = {}, {}
    totals = {"kept": {name: 0 for name in OUTCOMES}, "cut": {name: 0 for name in OUTCOMES}}
    runs_root = home / "runs"
    if home.is_dir() and not cockpit.linked(home) and runs_root.is_dir() and not cockpit.linked(runs_root):
        for folder in sorted((p for p in runs_root.iterdir() if p.is_dir() and not cockpit.linked(p)),
                             key=lambda p: p.name)[-1000:]:
            state = state_fields(folder / "session-state.md")
            if state.get("status") != "complete" or not state.get("closed"):
                continue
            claims = read_claims(folder / "claims.jsonl")
            if claims is None:
                continue
            # A council home can hold runs for several working trees. Compare each citation with
            # the code root recorded by that run; a missing recorded root is unknown, not a reason
            # to silently compare it with the caller's unrelated repository.
            run_repo = run_code_root(state, repo)
            run_head = git(run_repo, "rev-parse", "--verify", "HEAD") if run_repo else None
            close_commit = commit_at_close(run_repo, state["closed"]) if run_repo else None
            # `base` is council index's merge-base, not a close-time snapshot. The index's explicit
            # dirty marker is the available evidence that the run reviewed uncommitted files.
            if close_commit is None or reviewed_uncommitted(folder / "index.md"):
                close_commit = None
            mode = cockpit.clean(state.get("mode") or "unknown") or "unknown"
            run_data = {"run": cockpit.clean(folder.name), "mode": mode, "claims": []}
            cache = {}  # this run's claims share each cited file's tracked checks and diff
            for claim in claims:
                disposition = str(claim.get("disposition", "")).lower()
                if disposition not in ("kept", "cut"):
                    disposition = "kept" if disposition == "keep" else "unknown"
                if disposition == "unknown":
                    continue
                outcome = classify(run_repo, close_commit, run_head, claim, cache)
                sources = claim.get("provenance")
                if not isinstance(sources, list):
                    sources = []
                claim_data = {"id": str(claim.get("id", "?")), "disposition": disposition,
                              "citation": claim.get("citation", "-"), "outcome": outcome,
                              "seats": sorted(set(cockpit.clean(source.split("#", 1)[0]) for source in sources
                                                  if isinstance(source, str) and source and
                                                  not source.startswith("gate:") and cockpit.clean(source.split("#", 1)[0])))}
                run_data["claims"].append(claim_data)
                add_count(totals, disposition, outcome)
                add_count(modes.setdefault(mode, {}), disposition, outcome)
                for seat in claim_data["seats"]:
                    add_count(seats.setdefault(seat, {}), disposition, outcome)
            if run_data["claims"]:
                counts = {kind: {name: 0 for name in OUTCOMES} for kind in ("kept", "cut")}
                for item in run_data["claims"]:
                    counts[item["disposition"]][item["outcome"]] += 1
                run_data["summary"] = counts
                runs.append(run_data)
    return {"schema": SCHEMA, "head": head, "runs": runs, "totals": totals,
            "by_mode": {key: modes[key] for key in sorted(modes)},
            "by_seat": {key: seats[key] for key in sorted(seats)},
            "note": "Changed after the run describes timing; it does not show that a council finding caused the change."}


def render(data):
    kept, cut = data["totals"]["kept"], data["totals"]["cut"]
    lines = ["council outcomes · {} run(s) · {} Kept · {} Cut".format(
        len(data["runs"]), sum(kept.values()), sum(cut.values()))]
    lines.append("Kept: {} at cited lines · {} elsewhere · {} unchanged · {} gone or renamed · {} can't tell".format(
        kept[OUTCOMES[0]], kept[OUTCOMES[1]], kept[OUTCOMES[2]], kept[OUTCOMES[3]], kept[OUTCOMES[4]]))
    lines.append("Cut comparison: {} at cited lines · {} elsewhere · {} unchanged · {} gone or renamed · {} can't tell".format(
        cut[OUTCOMES[0]], cut[OUTCOMES[1]], cut[OUTCOMES[2]], cut[OUTCOMES[3]], cut[OUTCOMES[4]]))
    if data["runs"]:
        run_lines = []
        for run in data["runs"]:
            parts = []
            for kind in ("kept", "cut"):
                counts = run["summary"][kind]
                n = sum(counts.values())
                parts.append("{} {}/{} at cited lines".format(kind.title(), counts[OUTCOMES[0]], n))
            run_lines.append("{} [{}]: {}".format(run["run"], run["mode"], ", ".join(parts)))
        lines.append("By run: " + " · ".join(run_lines))
    if data["by_mode"]:
        lines.append("By mode: " + " · ".join(group_text(mode, grouped)
                                             for mode, grouped in data["by_mode"].items()))
    if data["by_seat"]:
        lines.append("By seat: " + " · ".join(group_text(seat, grouped)
                                             for seat, grouped in data["by_seat"].items()))
    lines.append(data["note"])
    return "\n".join(lines)


def group_text(label, grouped):
    parts = []
    for kind in ("kept", "cut"):
        counts = grouped.get(kind)
        if counts:
            parts.append("{} {}/{} at cited lines".format(kind.title(), counts[OUTCOMES[0]], sum(counts.values())))
    return "{}: {}".format(label, ", ".join(parts) if parts else "no claims")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = outcomes(args.home, args.repo)
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
