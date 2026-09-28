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
        result = subprocess.run(["git", "-C", str(repo)] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, timeout=20, env=env)
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


def commit_at_close(repo, closed):
    if not closed:
        return None
    return git(repo, "rev-list", "-1", "--before=" + closed, "HEAD")


def tracked(repo, commit, path):
    return git(repo, "cat-file", "-e", commit + ":" + path) is not None


def parse_hunks(diff):
    """Return old-side line spans from unified diff; zero-length spans are insertions."""
    spans = []
    for line in diff.splitlines():
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", line)
        if match:
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            spans.append((start, start + count - 1, count == 0))
    return spans


def classify(repo, close_commit, head, claim):
    parsed = parse_citation(claim.get("citation"))
    if parsed is None or close_commit is None or head is None:
        return "can't tell"
    path, first, last = parsed
    if not tracked(repo, close_commit, path):
        # A citation that was not present at the run's recorded close cannot be compared reliably.
        return "can't tell"
    if not tracked(repo, head, path):
        # git diff --name-status is consulted to distinguish a rename from a plain deletion.
        names = git(repo, "diff", "--name-status", "-M", close_commit, head, "--", path)
        if names:
            for row in names.splitlines():
                columns = row.split("\t")
                if columns and columns[0].startswith("R"):
                    return "file gone or renamed"
                if columns and columns[0] == "D":
                    return "file gone or renamed"
        return "file gone or renamed"
    diff = git(repo, "diff", "--no-ext-diff", "--no-renames", "--unified=0", close_commit, head, "--", path)
    if diff is None:
        return "can't tell"
    spans = parse_hunks(diff)
    if not spans:
        return "unchanged"
    for start, end, insertion in spans:
        if not insertion and start <= last and end >= first:
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
            close_commit = commit_at_close(repo, state["closed"])
            # A recorded base that differs from the close snapshot means the run may have reviewed
            # intervening work; do not attribute later diffs to its citations.
            if not re.fullmatch(r"[0-9a-fA-F]{40,64}", state.get("base", "")) or \
                    close_commit is None or state.get("base", "").lower() != close_commit.lower():
                close_commit = None
            mode = state.get("mode") or "unknown"
            run_data = {"run": folder.name, "mode": mode, "claims": []}
            for claim in claims:
                disposition = str(claim.get("disposition", "")).lower()
                if disposition not in ("kept", "cut"):
                    disposition = "kept" if disposition == "keep" else "unknown"
                if disposition == "unknown":
                    continue
                outcome = classify(repo, close_commit, head, claim)
                sources = claim.get("provenance")
                if not isinstance(sources, list):
                    sources = []
                claim_data = {"id": str(claim.get("id", "?")), "disposition": disposition,
                              "citation": claim.get("citation", "-"), "outcome": outcome,
                              "seats": sorted(set(source.split("#", 1)[0] for source in sources
                                                  if isinstance(source, str) and source and
                                                  not source.startswith("gate:")))}
                run_data["claims"].append(claim_data)
                add_count(totals, disposition, outcome)
                add_count(modes.setdefault(mode, {}), disposition, outcome)
                for seat in claim_data["seats"]:
                    add_count(seats.setdefault(seat, {}), disposition, outcome)
            if run_data["claims"]:
                counts = {name: 0 for name in OUTCOMES}
                for item in run_data["claims"]:
                    counts[item["outcome"]] += 1
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
    if data["by_mode"]:
        lines.append("By mode: " + " · ".join("{}: {} claim(s)".format(mode, sum(
            sum(values.values()) for values in grouped.values())) for mode, grouped in data["by_mode"].items()))
    if data["by_seat"]:
        lines.append("By seat: " + " · ".join("{}: {} claim(s)".format(seat, sum(
            sum(values.values()) for values in grouped.values())) for seat, grouped in data["by_seat"].items()))
    lines.append(data["note"])
    return "\n".join(lines)


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
