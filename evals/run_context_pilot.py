#!/usr/bin/env python3
"""Reproducible local Phase 5.5 context-delivery comparison (no model calls).

The control points a worker at the brief. The treatment points it at the same
brief plus a generated pack. Byte counts describe referenced files, not tokens
actually consumed by an agent or the quality of its findings.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "scripts" / "context.py"
IMPACT_HEADER = "kind\tsource\ttarget\trelation\tevidence\tconfidence\n"


def write(base, relative, content):
    path = base / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return path


def brief(seat, slice_path, objective, other_objective):
    return (
        "# Brief — pilot\n"
        "Deliverable: review the changed behavior.\n"
        "Intent: find a real regression without inventing one.\n"
        "Ask: inspect the assigned change and its consumers.\n"
        "Question for every seat: what would break?\n\n"
        "## Landscape\n"
        "A small fixture repository with changed code and independent surfaces.\n\n"
        "## Seats\n"
        f"### {seat} — primary review (Reviewer)\n"
        "- ref: none\n"
        f"- out: seats/{seat}.md\n"
        f"- slice: {slice_path}\n"
        f"- objective: {objective}\n"
        f"- start at: {slice_path}\n\n"
        "### unrelated — other review (Reviewer)\n"
        "- ref: none\n"
        "- out: seats/unrelated.md\n"
        "- slice: web/unrelated.ts\n"
        f"- objective: {other_objective}\n\n"
        "## Hard constraints — do not forget\n"
        "- PILOT_CRITICAL_RULE: cite the actual source; never claim a check ran if it did not.\n"
    )


def index(entries):
    header = "# Change index — pilot\nbase: fixture\n\n"
    return header + "\n\n".join(
        f"## {path}  (modified, +2/-1)\n- hunks: 1-8\n- symbols: {symbol}"
        for path, symbol in entries
    ) + "\n"


def cases():
    noise = [(f"web/noise_{n}.ts", "widget") for n in range(12)]
    return [
        {
            "name": "isolated-edit", "seat": "format", "level": "minimal",
            "slice": "src/format.py", "objective": "inspect the formatting edge case",
            "other": "UNRELATED_WIDGET_OBJECTIVE", "expected": ["src/format.py"],
            "files": {
                "src/format.py": "def label(value):\n    return value.strip()\n",
                "web/unrelated.ts": "export const widget = true;\n",
            },
            "entries": [("src/format.py", "label")], "impact": "",
        },
        {
            "name": "cross-module", "seat": "math", "level": "focused",
            "slice": "src/math.py", "objective": "inspect median and its consumers",
            "other": "UNRELATED_WIDGET_OBJECTIVE",
            "expected": ["src/math.py", "src/report.py", "tests/test_math.py"],
            "files": {
                "src/math.py": "def median(values):\n    return sorted(values)[len(values) // 2]\n",
                "src/report.py": "from src.math import median\n",
                "tests/test_math.py": "from src.math import median\n",
                "web/unrelated.ts": "export const widget = true;\n",
            },
            "entries": [("src/math.py", "median"), ("web/unrelated.ts", "widget")] + noise,
            "impact": IMPACT_HEADER
            + "change\tsrc/math.py\t-\tM\tfixture\thigh\n"
            + "impact\tsrc/math.py\tsrc/report.py\tdirect-import\tfrom src.math import median\thigh\n"
            + "test\tsrc/math.py\ttests/test_math.py\tdirect-import\tfrom src.math import median\thigh\n",
        },
        {
            "name": "risky-auth", "seat": "security", "level": "full",
            "slice": "app/auth.py", "objective": "inspect missing-token admission",
            "other": "UNRELATED_WIDGET_OBJECTIVE",
            "expected": ["app/auth.py", "tests/test_auth.py", "migrations/002_role.sql"],
            "files": {
                "app/auth.py": "def token_ok(given, expected):\n    if not given:\n        return True\n    return given == expected\n",
                "tests/test_auth.py": "from app.auth import token_ok\n",
                "migrations/002_role.sql": "ALTER TABLE users ADD COLUMN role TEXT;\n",
                "web/unrelated.ts": "export const widget = true;\n",
            },
            "entries": [("app/auth.py", "token_ok"), ("migrations/002_role.sql", "role"),
                        ("web/unrelated.ts", "widget")] + noise,
            "impact": IMPACT_HEADER
            + "change\tapp/auth.py\t-\tM\tfixture\thigh\n"
            + "test\tapp/auth.py\ttests/test_auth.py\tdirect-import\tfrom app.auth import token_ok\thigh\n"
            + "dependency\tapp/auth.py\tmigrations/002_role.sql\tfixture-link\trole contract\tmedium\n",
        },
    ]


def run_case(parent, case):
    repo = parent / case["name"]
    run = repo / ".council" / "runs" / "pilot"
    run.mkdir(parents=True)
    for relative, content in case["files"].items():
        write(repo, relative, content)
    brief_path = write(run, "brief.md", brief(case["seat"], case["slice"],
                                               case["objective"], case["other"]))
    index_path = write(run, "index.md", index(case["entries"]))
    impact_path = write(run, "impact.tsv", case["impact"]) if case["impact"] else None
    output = run / "contexts" / (case["seat"] + ".md")
    command = [sys.executable, str(PROVIDER), "--root", str(repo), "--run", str(run),
               "--seat", case["seat"], "--level", case["level"], "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(case["name"] + ": " + result.stderr.strip())
    pack = output.read_text(encoding="utf-8")
    brief_bytes = brief_path.stat().st_size
    pack_bytes = output.stat().st_size
    full_bytes = brief_bytes + index_path.stat().st_size + (impact_path.stat().st_size if impact_path else 0)
    retained = all(marker in pack for marker in case["expected"])
    excluded = case["other"] not in pack
    hard_rule = "PILOT_CRITICAL_RULE" in pack
    return {
        "case": case["name"], "level": case["level"],
        "control_brief_bytes": brief_bytes,
        "treatment_brief_plus_pack_bytes": brief_bytes + pack_bytes,
        "added_pack_bytes": pack_bytes,
        "unfiltered_brief_index_impact_bytes": full_bytes,
        "pack_vs_unfiltered_percent": round(100 * (pack_bytes - full_bytes) / full_bytes, 2),
        "treatment_vs_control_percent": round(100 * pack_bytes / brief_bytes, 2),
        "known_paths_retained": retained, "other_seat_excluded": excluded,
        "hard_rule_retained": hard_rule,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="council-context-pilot-") as directory:
        rows = [run_case(Path(directory), case) for case in cases()]
    print(json.dumps({"measurement": "referenced UTF-8 bytes; not model tokens or outcomes",
                      "cases": rows}, indent=2))
    return 0 if all(row["known_paths_retained"] and row["other_seat_excluded"]
                    and row["hard_rule_retained"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
