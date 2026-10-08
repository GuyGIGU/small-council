#!/usr/bin/env python3
"""Focused, no-network checks for Phase 5 seat context packs."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "context.py"
CLI = ROOT / "bin" / "council"
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
           GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
ENV.pop("CLAUDE_CODE_SESSION_ID", None)   # never inherit the session the eval runs in (run open would check its hooks)
results = []


def check(name, okay, detail=""):
    results.append((name, bool(okay), detail))


def run(cwd, *command):
    return subprocess.run(command, cwd=cwd, env=ENV, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def write(root, name, content):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return target


def produce(repo, seat, level, output, *extra, run_path=None):
    target_run = run_path or repo / ".council/runs/fixture"
    return run(repo, sys.executable, str(ENGINE), "--root", str(repo), "--run", str(target_run),
               "--seat", seat, "--level", level, "--output", str(output), *extra)


def text_at(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def metrics_at(path):
    """Return a TSV's rows without coupling tests to its chosen column labels."""
    if not path.is_file():
        return []
    return [line.split("\t") for line in text_at(path).splitlines() if line.strip()]


with tempfile.TemporaryDirectory() as folder:
    temp = Path(folder)
    repo = temp / "fixture-repo"
    repo.mkdir()
    run_dir = repo / ".council/runs/fixture"
    run_dir.mkdir(parents=True)
    write(repo, "src/math.py", "def median(values):\n    return sorted(values)[len(values) // 2]\n")
    write(repo, "src/report.py", "from src.math import median\n\ndef summary(values):\n    return median(values)\n")
    write(repo, "tests/test_math.py", "from src.math import median\n\ndef test_median():\n    assert median([3, 1, 2]) == 2\n")
    write(repo, "web/ui.ts", "export const widget = 'beta only';\n")
    write(repo, "docs/seat-rules.md", "# Statistical review reference\n")
    write(repo, "docs/addendum.md", "EXPANDED_NOTE_ONLY_FOR_ALPHA: preserve the median edge case.\n")
    write(repo, "docs/long.md", "L" * 14000 + "\nFULL_LEVEL_TAIL_MARKER\n")
    write(run_dir, "brief.md",
          "# Brief — fixture\n"
          "Deliverable: review the changed files.\n"
          "Intent: keep the report correct.\n"
          "Out of scope: the billing service.\n"
          "Code root: fixture-repo\n\n"
          "## Landscape\n"
          "Two independent surfaces: Python statistics and a web widget.\n\n"
          "## Seats\n"
          "### alpha — statistics review (Reviewer)\n"
          f"- ref: {repo / 'docs/seat-rules.md'}\n"
          f"- doc: {repo / 'docs/seat-rules.md'}\n"
          "- out: seats/alpha.md\n"
          "- slice: src/math.py\n"
          "- objective: verify median and report behavior.\n"
          "- key questions: do direct importers and tests still work?\n"
          "- start at: src/math.py\n\n"
          "### report-review — report impact review (Reviewer)\n"
          "- ref: none\n"
          "- out: seats/report-review.md\n"
          "- slice: src/report.py\n"
          "- objective: REPORT_ONLY_IMPORTER_OBJECTIVE checks the unchanged importer.\n\n"
          "### stats_v2 — alternate statistics review (Reviewer)\n"
          "- ref: none\n"
          "- out: seats/stats_v2.md\n"
          "- slice: src/math.py\n"
          "- objective: STATS_V2_SLUG_OBJECTIVE checks the changed function.\n\n"
          "### beta — widget review (Reviewer)\n"
          "- ref: none\n"
          "- out: seats/beta.md\n"
          "- slice: web/ui.ts\n"
          "- objective: evaluate BETA_PRIVATE_WIDGET_OBJECTIVE and animation timing.\n"
          "- key questions: does the widget animate?\n"
          "- start at: web/ui.ts\n\n"
          "## Seats not called\n"
          "- gamma — database: no database change.\n\n"
          "## Hard constraints — do not forget\n"
          "- CRITICAL_SHARED_RULE_417: do not make network calls.\n"
          "- Cite path:line or drop the item.\n")
    write(run_dir, "index.md",
          "# Change index — fixture\n"
          "base: abc123 (main) · head: def456\n"
          "files: 2 (+3/-1)\n\n"
          "## src/math.py  (modified, +2/-1)\n"
          "- hunks: 1-2\n"
          "- symbols: median\n"
          "- callers: src/report.py:3 (median)\n"
          "- tests: tests/test_math.py\n\n"
          "## web/ui.ts  (modified, +1/-0)\n"
          "- hunks: 1\n"
          "- symbols: widget\n"
          "- beta-only notes: " + ("animation timing is unrelated to statistics. " * 40) + "\n\n")
    impact = write(run_dir, "impact.tsv",
                   "kind\tsource\ttarget\trelation\tevidence\tconfidence\n"
                   "schema\timpact\t1\tversion\tdirect, bounded impact graph\thigh\n"
                   "change\tsrc/math.py\t-\tM\tunstaged\thigh\n"
                   "change\tweb/ui.ts\t-\tM\tunstaged\thigh\n"
                   "impact\tsrc/math.py\tsrc/report.py\tdirect-import\tfrom src.math import median\thigh\n"
                   "test\tsrc/math.py\ttests/test_math.py\tdirect-import\tfrom src.math import median\thigh\n")
    outputs = {}
    for level in ("minimal", "focused", "full"):
        path = run_dir / "contexts" / f"alpha-{level}.md"
        result = produce(repo, "alpha", level, path)
        outputs[level] = (path, result, text_at(path))
        check(f"context: {level} pack builds successfully", result.returncode == 0 and path.is_file(),
              result.stdout + result.stderr)
        check(f"context: {level} retains the hard constraint and assigned source",
              "CRITICAL_SHARED_RULE_417" in outputs[level][2] and "src/math.py" in outputs[level][2] and
              "seat-rules.md" in outputs[level][2],
              outputs[level][2][:600])
        check(f"context: {level} excludes the other seat's private brief",
              "BETA_PRIVATE_WIDGET_OBJECTIVE" not in outputs[level][2], outputs[level][2][:600])

    minimal = outputs["minimal"][2]
    focused = outputs["focused"][2]
    full = outputs["full"][2]
    expanded_by_level = {}
    for level in ("minimal", "focused", "full"):
        path = run_dir / "contexts" / f"expanded-{level}.md"
        result = produce(repo, "alpha", level, path, "--expand", "docs/long.md")
        expanded_by_level[level] = text_at(path)
        check(f"context: {level} explicit large-file expansion builds", result.returncode == 0 and path.is_file(),
              result.stdout + result.stderr)
    check("context: levels increase the explicit expansion budget without dropping critical context",
          len(expanded_by_level["minimal"].encode("utf-8")) <
          len(expanded_by_level["focused"].encode("utf-8")) <
          len(expanded_by_level["full"].encode("utf-8")) and
          "FULL_LEVEL_TAIL_MARKER" not in expanded_by_level["minimal"] and
          "FULL_LEVEL_TAIL_MARKER" not in expanded_by_level["focused"] and
          "FULL_LEVEL_TAIL_MARKER" in expanded_by_level["full"] and
          all("CRITICAL_SHARED_RULE_417" in text for text in expanded_by_level.values()),
          "expanded bytes: " + ", ".join(str(len(expanded_by_level[level].encode("utf-8")))
                                        for level in ("minimal", "focused", "full")))
    check("context: direct importer and test remain visible in a focused pack",
          "src/report.py" in focused and "tests/test_math.py" in focused, focused[:800])
    report_path = run_dir / "contexts/report-review.md"
    report_result = produce(repo, "report-review", "focused", report_path)
    report_text = text_at(report_path)
    check("context: an unchanged importer seat receives its directly linked changed file",
          report_result.returncode == 0 and "src/report.py" in report_text and "src/math.py" in report_text and
          "direct-import" in report_text and "web/ui.ts" not in report_text and
          "BETA_PRIVATE_WIDGET_OBJECTIVE" not in report_text,
          report_result.stdout + report_result.stderr + report_text[:700])
    alt_slug_path = run_dir / "contexts/stats_v2.md"
    alt_result = produce(repo, "stats_v2", "minimal", alt_slug_path)
    check("context: underscore seat slug resolves its own block",
          alt_result.returncode == 0 and "STATS_V2_SLUG_OBJECTIVE" in text_at(alt_slug_path) and
          "BETA_PRIVATE_WIDGET_OBJECTIVE" not in text_at(alt_slug_path),
          alt_result.stdout + alt_result.stderr)
    check("context: focused pack is smaller than the full run inputs while retaining critical content",
          bool(focused) and len(focused.encode("utf-8")) <
          (run_dir / "brief.md").stat().st_size + (run_dir / "index.md").stat().st_size + impact.stat().st_size and
          "CRITICAL_SHARED_RULE_417" in focused and "src/math.py" in focused,
          f"focused bytes={len(focused.encode('utf-8'))}")

    focused_path = outputs["focused"][0]
    metrics_path = Path(str(focused_path) + ".metrics.tsv")
    metric_rows = metrics_at(metrics_path)
    metric_map = {row[0]: row[1] for row in metric_rows[1:] if len(row) == 2}
    check("context: machine-readable metrics accompany the pack",
          bool(metric_rows) and metric_rows[0] == ["metric", "value"] and
          all(len(row) == 2 for row in metric_rows) and
          {"baseline_bytes", "included_bytes", "reduction_percent", "selected_paths", "omitted_paths"} <= set(metric_map),
          text_at(metrics_path)[:600])
    check("context: metrics describe a reduced pack with selected paths",
          metric_map.get("baseline_bytes", "").isdigit() and metric_map.get("included_bytes", "").isdigit() and
          int(metric_map.get("baseline_bytes", "0")) > int(metric_map.get("included_bytes", "0")) > 0 and
          int(metric_map.get("selected_paths", "0")) >= 1,
          text_at(metrics_path)[:600])
    before = (focused_path.read_bytes() if focused_path.is_file() else b"",
              metrics_path.read_bytes() if metrics_path.is_file() else b"")
    again = produce(repo, "alpha", "focused", focused_path)
    check("context: unchanged inputs produce byte-identical pack and metrics",
          again.returncode == 0 and focused_path.is_file() and metrics_path.is_file() and
          before == (focused_path.read_bytes(), metrics_path.read_bytes()), again.stdout + again.stderr)

    expanded = run_dir / "contexts/expanded.md"
    result = produce(repo, "alpha", "focused", expanded, "--expand", "docs/addendum.md")
    check("context: explicit in-repository expansion is included",
          result.returncode == 0 and "EXPANDED_NOTE_ONLY_FOR_ALPHA" in text_at(expanded),
          result.stdout + result.stderr + text_at(expanded)[:500])
    deduped = run_dir / "contexts/deduped.md"
    result = produce(repo, "alpha", "focused", deduped, "--expand", "docs/addendum.md",
                     "--expand", "docs/addendum.md")
    check("context: repeated expansion is deduplicated",
          result.returncode == 0 and text_at(deduped).count("EXPANDED_NOTE_ONLY_FOR_ALPHA") == 1,
          result.stdout + result.stderr + text_at(deduped)[:500])
    outside = write(temp, "private.txt", "OUTSIDE_SECRET_MUST_NOT_LEAK\n")
    rejected_path = run_dir / "contexts/outside.md"
    rejected = produce(repo, "alpha", "focused", rejected_path, "--expand", str(outside))
    check("context: expansion rejects an outside path without leaking its content",
          rejected.returncode != 0 and "OUTSIDE_SECRET_MUST_NOT_LEAK" not in
          (rejected.stdout + rejected.stderr + text_at(rejected_path)), rejected.stdout + rejected.stderr)
    events_file = write(run_dir, "events.tsv", "RUN_HISTORY_MUST_REMAIN_INTACT\n")
    rejected = produce(repo, "alpha", "focused", events_file)
    check("context: provider cannot overwrite another run artifact",
          rejected.returncode != 0 and text_at(events_file) == "RUN_HISTORY_MUST_REMAIN_INTACT\n",
          rejected.stdout + rejected.stderr)
    try:
        (repo / "linked-private.txt").symlink_to(outside)
        has_symlink = True
    except OSError:
        has_symlink = False  # Symlink creation can require privileges on Windows.
    if has_symlink:
        linked_path = run_dir / "contexts/linked.md"
        rejected = produce(repo, "alpha", "focused", linked_path, "--expand", "linked-private.txt")
        check("context: expansion rejects a symlink escaping the repository",
              rejected.returncode != 0 and "OUTSIDE_SECRET_MUST_NOT_LEAK" not in
              (rejected.stdout + rejected.stderr + text_at(linked_path)), rejected.stdout + rejected.stderr)
        output_link = run_dir / "contexts/output-link.md"
        output_link.parent.mkdir(parents=True, exist_ok=True)  # report failed builds instead of crashing here
        output_link.symlink_to(outside)
        rejected = produce(repo, "alpha", "focused", output_link)
        check("context: a pre-existing output symlink cannot redirect writes outside the run",
              rejected.returncode != 0 and text_at(outside) == "OUTSIDE_SECRET_MUST_NOT_LEAK\n",
              rejected.stdout + rejected.stderr)
        linked_run = repo / ".council/runs/linked-context"
        linked_run.mkdir()
        write(linked_run, "brief.md", text_at(run_dir / "brief.md"))
        write(linked_run, "index.md", text_at(run_dir / "index.md"))
        outside_dir = temp / "outside-contexts"
        outside_dir.mkdir()
        (linked_run / "contexts").symlink_to(outside_dir, target_is_directory=True)
        rejected = produce(repo, "alpha", "focused", linked_run / "contexts/alpha.md", run_path=linked_run)
        check("context: a pre-existing contexts directory symlink cannot redirect output",
              rejected.returncode != 0 and not (outside_dir / "alpha.md").exists(),
              rejected.stdout + rejected.stderr)

    # A root reached through a link resolves (macOS /var -> /private/var, a Windows 8.3 temp name),
    # while the run and output paths beside it arrive spelled through the link.
    alias = temp / "repo-alias"
    try:
        if os.name == "nt":
            aliased = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(repo)],
                                     capture_output=True).returncode == 0
        else:
            os.symlink(str(repo), str(alias))
            aliased = True
    except OSError:
        aliased = False
    if aliased:
        via_run = alias / ".council/runs/fixture"
        via = run(repo, sys.executable, str(ENGINE), "--root", str(alias), "--run", str(via_run),
                  "--seat", "alpha", "--level", "focused", "--output", str(via_run / "contexts/via-link.md"),
                  "--expand", str(alias / "docs/addendum.md"))
        check("context: a root reached through a link accepts its run, output and expansion spelled that way",
              via.returncode == 0 and "EXPANDED_NOTE_ONLY_FOR_ALPHA" in text_at(run_dir / "contexts/via-link.md"),
              via.stdout + via.stderr)
        escape = run(repo, sys.executable, str(ENGINE), "--root", str(alias), "--run", str(via_run),
                     "--seat", "alpha", "--level", "focused", "--output", str(via_run / "contexts/via-escape.md"),
                     "--expand", os.path.join(str(alias), "..", outside.name))
        check("context: a root reached through a link still refuses an expansion that climbs out of it",
              escape.returncode != 0 and "OUTSIDE_SECRET_MUST_NOT_LEAK" not in
              (escape.stdout + escape.stderr + text_at(run_dir / "contexts/via-escape.md")),
              escape.stdout + escape.stderr)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "rmdir", str(alias)], capture_output=True)
        else:
            alias.unlink()

    rename_graph = text_at(impact).replace(
        "change\tsrc/math.py\t-\tM\tunstaged\thigh",
        "change\tsrc/math.py\tsrc/old_math.py\tR\tstaged\thigh")
    rename_graph += "impact\tsrc/old_math.py\tsrc/legacy_report.py\tformer-path-importer\told import\thigh\n"
    with impact.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(rename_graph)
    renamed_pack = run_dir / "contexts/renamed.md"
    result = produce(repo, "alpha", "focused", renamed_pack)
    check("context: a renamed file's former-path importer remains in its seat pack",
          result.returncode == 0 and "src/old_math.py" in text_at(renamed_pack) and
          "src/legacy_report.py" in text_at(renamed_pack),
          result.stdout + result.stderr + text_at(renamed_pack)[:700])

    impact.unlink()
    fallback = run_dir / "contexts/index-only.md"
    result = produce(repo, "alpha", "focused", fallback)
    check("context: index-only fallback builds without impact.tsv",
          result.returncode == 0 and "src/math.py" in text_at(fallback) and
          "CRITICAL_SHARED_RULE_417" in text_at(fallback), result.stdout + result.stderr)
    check("context: index-only fallback still includes likely caller and test paths",
          "src/report.py" in text_at(fallback) and "tests/test_math.py" in text_at(fallback), text_at(fallback)[:700])
    (run_dir / "index.md").unlink()
    brief_only = run_dir / "contexts/brief-only.md"
    result = produce(repo, "alpha", "minimal", brief_only)
    check("context: brief-only fallback preserves seat and hard constraints before indexing",
          result.returncode == 0 and "src/math.py" in text_at(brief_only) and
          "CRITICAL_SHARED_RULE_417" in text_at(brief_only) and
          "BETA_PRIVATE_WIDGET_OBJECTIVE" not in text_at(brief_only),
          result.stdout + result.stderr + text_at(brief_only)[:500])

    if BASH:
        cli_repo = temp / "cli-repo"
        cli_repo.mkdir()
        init = run(cli_repo, "git", "init", "-q")
        run(cli_repo, "git", "symbolic-ref", "HEAD", "refs/heads/main")
        write(cli_repo, ".council/council.config.md", "# Council config — context eval\n")
        write(cli_repo, "src/math.py", "def median(xs):\n    return xs[0]\n")
        run(cli_repo, "git", "add", ".")
        run(cli_repo, "git", "commit", "-qm", "baseline")
        opened = run(cli_repo, BASH, str(CLI), "run", "open", "council-review")
        cli_run = Path(opened.stdout.strip())
        check("context CLI: opens a temporary fixture run", init.returncode == 0 and opened.returncode == 0 and
              cli_run.is_dir(), opened.stdout + opened.stderr)
        if cli_run.is_dir():
            state = text_at(cli_run / "session-state.md")
            plan = [
                ("kind", "id", "field", "value", "reason"),
                ("schema", "plan", "version", "1", "test contract"),
                ("run", "run", "id", cli_run.name, "bind to fixture run"),
                ("run", "run", "mode", "council-review", "fixture mode"),
                ("run", "run", "size", "squad", "one worker"),
                ("assessment", "run", "risk", "low", "small fixture"),
                ("assessment", "run", "complexity", "low", "small fixture"),
                ("assessment", "run", "uncertainty", "low", "known fixture"),
                ("budget", "run", "agent-cap", "2", "fixture cap"),
                ("budget", "run", "estimated-tokens", "1000", "fixture estimate"),
                ("verification", "run", "level", "self", "focused check"),
            ]
            for slug, role in (("chair", "chair"), ("alpha", "worker")):
                plan.extend((("seat", slug, "disposition", "selected", "fixture selection"),
                             ("seat", slug, "role", role, "fixture role"),
                             ("context", slug, "level", "focused", "fixture context"),
                             ("budget", slug, "tool-calls", "10", "fixture budget")))
            plan.extend((("seat", "beta", "disposition", "skipped", "out of scope"),
                         ("seat", "beta", "role", "worker", "fixture role")))
            write(cli_run, "run-plan.tsv", "\n".join("\t".join(row) for row in plan) + "\n")
            write(cli_run, "brief.md",
                  "# Brief — CLI fixture\n## Seats\n### alpha — statistics review\n"
                  "- ref: none\n- out: seats/alpha.md\n- slice: src/math.py\n"
                  "## Hard constraints — do not forget\n- CLI_SHARED_RULE_882: stay read-only.\n")
            write(cli_run, "index.md", "# Change index\n## src/math.py  (modified, +1/-0)\n- hunks: 1\n")
            checked = run(cli_repo, BASH, str(CLI), "run", "plan", "check")
            check("context CLI: fixture run plan is valid", checked.returncode == 0,
                  checked.stdout + checked.stderr + state[:150])
            built = run(cli_repo, BASH, str(CLI), "context", "build", "alpha")
            pack = cli_run / "contexts/alpha.md"
            check("context CLI: builds a selected seat's pack at its run-local path",
                  built.returncode == 0 and pack.is_file() and "CLI_SHARED_RULE_882" in text_at(pack),
                  built.stdout + built.stderr)
            check("context CLI: writes metrics beside the seat pack",
                  Path(str(pack) + ".metrics.tsv").is_file(), built.stdout + built.stderr)
            write(cli_repo, "docs/addendum.md", "CLI_EXPANDED_NOTE_113\n")
            expanded_cli = run(cli_repo, BASH, str(CLI), "context", "build", "alpha",
                               "--expand", "docs/addendum.md", "--expand", "docs/addendum.md")
            check("context CLI: forwards repeated expansion flags without duplicating content",
                  expanded_cli.returncode == 0 and text_at(pack).count("CLI_EXPANDED_NOTE_113") == 1,
                  "count=" + str(text_at(pack).count("CLI_EXPANDED_NOTE_113")) + " " +
                  expanded_cli.stdout + expanded_cli.stderr + text_at(pack)[-500:])
            shown = run(cli_repo, BASH, str(CLI), "context", "show", "alpha")
            check("context CLI: show exposes the pack and metrics paths",
                  shown.returncode == 0 and str(pack).replace("\\", "/") in shown.stdout.replace("\\", "/") and
                  (str(pack) + ".metrics.tsv").replace("\\", "/") in shown.stdout.replace("\\", "/"),
                  shown.stdout + shown.stderr)
            skipped = run(cli_repo, BASH, str(CLI), "context", "build", "beta")
            check("context CLI: refuses a skipped seat", skipped.returncode != 0 and not
                  (cli_run / "contexts/beta.md").exists(), skipped.stdout + skipped.stderr)

passed = sum(ok for _, ok, _ in results)
for name, okay, detail in results:
    print(f"[{'PASS' if okay else 'FAIL'}] {name}" + (f" ({detail[:400]})" if detail and not okay else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
