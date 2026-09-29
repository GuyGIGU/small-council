#!/usr/bin/env python3
"""Focused, no-network checks for the optional Phase 4 impact graph."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "impact.py"
CLI = ROOT / "bin" / "council"
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
           GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
results = []


def check(name, okay, detail=""):
    results.append((name, bool(okay), detail))


def run(cwd, *command):
    return subprocess.run(command, cwd=cwd, env=ENV, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def git(cwd, *args):
    result = run(cwd, "git", *args)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def write(root, path, content):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def table(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[0], [tuple(line.split("\t")) for line in lines[1:]]


with tempfile.TemporaryDirectory() as folder:
    repo = Path(folder) / "impact-fixture"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/math.py", "def median(values):\n    return values[0]\n")
    write(repo, "pkg/app.py", "from pkg.math import median\n\ndef report(values):\n    return median(values)\n")
    write(repo, "tests/test_math.py", "from pkg.math import median\n\ndef test_median():\n    assert median([1]) == 1\n")
    write(repo, "src/pkg/__init__.py", "")
    write(repo, "src/pkg/lib.py", "def get():\n    return 1\n")
    write(repo, "src/pkg/use.py", "from pkg.lib import get\n")
    write(repo, "dupe/lib.py", "def get():\n    return 1\n")
    write(repo, "dupe/use.py", "from dupe.lib import get\n")
    write(repo, "src/dupe/lib.py", "def get():\n    return 10\n")
    write(repo, "web/util.ts", "export function compute(x: number) {\n  return x;\n}\n")
    write(repo, "web/app.ts", "import { compute } from './util';\nexport const value = compute(1);\n")
    write(repo, "web/util.test.ts", "import { compute } from './util';\n")
    write(repo, "config/settings.yaml", "feature: off\n")
    write(repo, "legacy.py", "def legacy_name():\n    return 1\n")
    write(repo, "legacy_user.py", "from legacy import legacy_name\n")
    write(repo, "old.py", "def old_name():\n    return 1\n")
    write(repo, "old_user.py", "from old import old_name\n")
    # A script folder whose entry point imports its neighbours by bare name (its folder is on
    # sys.path when it runs); json, math and requests have no sibling file here.
    write(repo, "tools/main.py", "import json\nimport math\nimport requests\nimport helper\nimport shared as sh\n"
                                 "from settings_io import VALUE\nimport alpha, beta\nfrom sub import mod\n")
    siblings = ("helper", "shared", "settings_io", "alpha", "beta", "sub/mod")
    for name in siblings:
        write(repo, f"tools/{name}.py", "VALUE = 1\n")
    write(repo, "tools/sub/__init__.py", "")
    write(repo, "lone/runner.py", "import lib\n")       # lone.lib exists only as the src/lone/lib.py alias
    write(repo, "src/lone/lib.py", "VALUE = 1\n")
    write(repo, "pkg/model.py", "import types\n")       # in a package, a bare name is absolute: stdlib types
    write(repo, "pkg/types.py", "VALUE = 1\n")
    write(repo, "src/solo.py", "VALUE = 1\n")
    write(repo, "src/solo_user.py", "import solo\nfrom solo import VALUE\n")  # both providers agree
    write(repo, "run.sh", "#!/bin/sh\necho one\n")
    write(repo, "vendor/dep.py", "VALUE = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "baseline")
    base = git(repo, "rev-parse", "HEAD")

    write(repo, "pkg/math.py", "def median(values):\n    return sorted(values)[0]\n")
    git(repo, "add", "pkg/math.py")
    write(repo, "pkg/math.py", "def median(values):\n    return sorted(values)[len(values) // 2]\n")
    write(repo, "src/pkg/lib.py", "def get():\n    return 2\n")
    write(repo, "dupe/lib.py", "def get():\n    return 2\n")
    write(repo, "src/dupe/lib.py", "def get():\n    return 20\n")
    write(repo, "web/util.ts", "export function compute(x: number) {\n  return x + 1;\n}\n")
    write(repo, "config/settings.yaml", "feature: on\n")
    git(repo, "mv", "legacy.py", "renamed.py")
    git(repo, "rm", "-q", "old.py")
    write(repo, "new.py", "def new_name():\n    return 2\n")
    for name in siblings:
        write(repo, f"tools/{name}.py", "VALUE = 2\n")
    write(repo, "src/solo.py", "VALUE = 2\n")
    write(repo, "src/lone/lib.py", "VALUE = 2\n")
    write(repo, "pkg/types.py", "VALUE = 2\n")
    write(repo, "run.sh", "#!/bin/sh\necho two\n")
    write(repo, "notes.md", "# Notes\n")
    write(repo, "vendor/dep.py", "VALUE = 2\n")
    outside = Path(folder) / "outside.py"
    outside.write_text("def private_outside_symbol():\n    return 3\n", encoding="utf-8")
    try:
        (repo / "linked.py").symlink_to(outside)
        has_symlink = True
    except OSError:
        has_symlink = False  # Some Windows hosts do not grant symlink creation in tests.

    output = Path(folder) / "impact.tsv"
    first = run(repo, sys.executable, str(ENGINE), "--root", str(repo), "--base", base, "--output", str(output))
    header, rows = table(output)
    check("impact: provider exits successfully with a stable six-column header",
          first.returncode == 0 and header == "kind\tsource\ttarget\trelation\tevidence\tconfidence" and
          all(len(row) == 6 for row in rows), first.stdout + first.stderr)
    check("impact: versioned schema row", ("schema", "impact", "1", "version", "direct, bounded impact graph", "high") in rows)

    def matching(kind, source=None, target=None):
        return [row for row in rows if row[0] == kind and (source is None or row[1] == source) and
                (target is None or row[2] == target)]

    math_change = matching("change", "pkg/math.py")
    check("impact: one delta combines staged and unstaged changes",
          len(math_change) == 1 and math_change[0][3] == "M" and math_change[0][4] == "staged+unstaged",
          str(math_change))
    check("impact: rename retains the old path", any(row[2] == "legacy.py" and row[3] == "R" for row in matching("change", "renamed.py")))
    check("impact: importer of a renamed former path remains visible",
          any(row[3] == "former-path-importer" for row in matching("impact", "legacy.py", "legacy_user.py")))
    check("impact: deleted and untracked files stay visible",
          any(row[3] == "D" for row in matching("change", "old.py")) and
          any(row[3] == "?" and row[4] == "untracked" for row in matching("change", "new.py")))
    check("impact: importer of a deleted module remains visible", bool(matching("impact", "old.py", "old_user.py")))
    check("impact: Python AST identifies the changed definition", bool(matching("symbol", "pkg/math.py", "median")))
    check("impact: JS/TS diff identifies the changed definition", bool(matching("symbol", "web/util.ts", "compute")))
    check("impact: Python direct importers are separate from changed files",
          bool(matching("impact", "pkg/math.py", "pkg/app.py")) and
          not matching("change", "pkg/app.py"))
    check("impact: src-layout absolute Python imports resolve",
          bool(matching("impact", "src/pkg/lib.py", "src/pkg/use.py")))
    check("impact: exact package path wins over a competing src-layout alias",
          bool(matching("impact", "dupe/lib.py", "dupe/use.py")) and
          not matching("impact", "src/dupe/lib.py", "dupe/use.py"))
    check("impact: Python test link has import evidence",
          any(row[3] == "direct-import" and row[5] == "high" for row in matching("test", "pkg/math.py", "tests/test_math.py")))
    check("impact: JS/TS relative imports resolve to source and test files",
          bool(matching("impact", "web/util.ts", "web/app.ts")) and
          bool(matching("test", "web/util.ts", "web/util.test.ts")))
    check("impact: configuration surface is labelled as a path heuristic",
          any(row[2] == "configuration" and row[5] == "low" for row in matching("surface", "config/settings.yaml")))
    check("impact: external packages are not invented as local dependencies",
          not any(row[2].startswith("sorted") for row in rows if row[0] == "dependency"))

    def sibling_edge(target, line, text):
        return (("dependency", "tools/main.py", target, "imports", f"script-dir:tools/main.py:{line}:{text}", "medium")
                in rows and ("impact", target, "tools/main.py", "direct-importer", f"script-dir:tools/main.py:{line}",
                             "medium") in rows)

    check("impact: script-dir resolves `import X` to a sibling file, at medium confidence",
          sibling_edge("tools/helper.py", 4, "import helper"), str(matching("impact", "tools/helper.py")))
    check("impact: script-dir resolves `import X as Y`", sibling_edge("tools/shared.py", 5, "import shared"))
    check("impact: script-dir resolves `from X import Y`",
          sibling_edge("tools/settings_io.py", 6, "from settings_io import"))
    check("impact: script-dir resolves every name in `import X, Y`",
          sibling_edge("tools/alpha.py", 7, "import alpha") and sibling_edge("tools/beta.py", 7, "import beta"))
    check("impact: script-dir resolves a sibling package's submodule", sibling_edge("tools/sub/mod.py", 8, "from sub import"))
    check("impact: no edge for a name with no sibling file (json, math, requests)",
          {row[2] for row in matching("dependency", "tools/main.py")} == {f"tools/{name}.py" for name in siblings},
          str(matching("dependency", "tools/main.py")))
    check("impact: script-dir matches only the importer's own folder, never a src/ alias",
          not [row for row in rows if row[0] in ("dependency", "impact") and "lone/runner.py" in row[1:3]])
    check("impact: script-dir skips package folders, where a bare import is absolute",
          not [row for row in rows if row[0] in ("dependency", "impact") and "pkg/model.py" in row[1:3]])
    solo = matching("impact", "src/solo.py", "src/solo_user.py")
    check("impact: an import python-ast resolves is not repeated as a medium sibling edge",
          len(solo) == 2 and all(row[4].startswith("python-ast:") and row[5] == "high" for row in solo), str(solo))
    unread = {row[1]: row for row in rows if row[0] == "limit" and row[3] == "not-inspected"}
    check("impact: every changed file no provider reads gets a limit row (shell, Markdown, YAML)",
          all(path in unread and unread[path][2] == "-" and unread[path][5] == "high"
              for path in ("run.sh", "notes.md", "config/settings.yaml")), str(sorted(unread)))
    check("impact: a changed source file outside the import scan gets a limit row", "vendor/dep.py" in unread)
    check("impact: scanned, deleted and renamed source files get no not-inspected row",
          not set(unread) & {"pkg/math.py", "web/util.ts", "tools/helper.py", "old.py", "renamed.py"}, str(sorted(unread)))
    check("impact: the summary line counts the files not inspected",
          f", {4 + has_symlink} not inspected -> impact.tsv" in first.stdout, first.stdout)
    if has_symlink:
        check("impact: source symlinks are not followed outside the repository",
              bool(matching("change", "linked.py")) and not matching("symbol", "linked.py") and
              "private_outside_symbol" not in output.read_text(encoding="utf-8"))
    before = output.read_bytes()
    again = run(repo, sys.executable, str(ENGINE), "--root", str(repo), "--base", base, "--output", str(output))
    check("impact: the same repository state gives byte-identical output", again.returncode == 0 and output.read_bytes() == before)

    if BASH:
        write(repo, ".council/council.config.md", "# Council config — impact eval\n")
        opened = run(repo, BASH, str(CLI), "run", "open", "council-review")
        run_folder = Path(opened.stdout.strip())
        check("impact CLI: opens a temporary fixture run", opened.returncode == 0 and run_folder.is_dir(), opened.stdout + opened.stderr)
        premature = run(repo, BASH, str(CLI), "impact")
        check("impact CLI: needs an index baseline before refresh",
              premature.returncode == 2 and "run council index first" in premature.stderr,
              premature.stdout + premature.stderr)
        indexed = run(repo, BASH, str(CLI), "index", "--base", base)
        graph = run_folder / "impact.tsv"
        check("impact CLI: index keeps its existing result and adds a graph",
              indexed.returncode == 0 and indexed.stdout.startswith("index:") and graph.is_file(),
              indexed.stdout + indexed.stderr)
        refreshed = run(repo, BASH, str(CLI), "impact")
        check("impact CLI: explicit refresh uses the saved baseline",
              refreshed.returncode == 0 and "impact:" in refreshed.stdout and graph.is_file(),
              refreshed.stdout + refreshed.stderr)

# Real history: in this range scripts/status.py, history.py and tune.py import their neighbours
# after putting their own folder on sys.path, and the helper and a hook change too. A shallow
# clone (CI's default checkout) lacks these commits, so there the check is skipped, not failed.
RANGE = ("132dc3715053cefdac3b587a652681b8e50f853c", "869d5cf1b0dbd2c493a6401498e7c42e40e44eac")
if all(run(ROOT, "git", "cat-file", "-e", sha + "^{commit}").returncode == 0 for sha in RANGE):
    with tempfile.TemporaryDirectory() as folder:
        clone = Path(folder) / "range"
        git(ROOT, "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(clone))
        git(clone, "checkout", "-q", "--detach", RANGE[1])
        output = Path(folder) / "impact.tsv"
        ran = run(clone, sys.executable, str(ENGINE), "--root", str(clone), "--base", RANGE[0], "--output", str(output))
        real = table(output)[1] if ran.returncode == 0 else []
        edges = {(row[1], row[2]) for row in real
                 if row[0] == "dependency" and row[4].startswith("script-dir:") and row[5] == "medium"}
        check("impact: real history yields status->cockpit, history->cockpit/ledger, tune->history/ledger",
              {("scripts/status.py", "scripts/cockpit.py"), ("scripts/history.py", "scripts/cockpit.py"),
               ("scripts/history.py", "scripts/ledger.py"), ("scripts/tune.py", "scripts/history.py"),
               ("scripts/tune.py", "scripts/ledger.py")} <= edges, ran.stdout + ran.stderr + str(sorted(edges)))
        check("impact: real history names bin/council and hooks/session-start.sh as not inspected",
              {("limit", "bin/council", "not-inspected"), ("limit", "hooks/session-start.sh", "not-inspected")}
              <= {(row[0], row[1], row[3]) for row in real}, ran.stdout + ran.stderr)
else:
    print("[SKIP] impact: real-history check needs commits 132dc37 and 869d5cf (absent from a shallow clone)")

passed = sum(ok for _, ok, _ in results)
for name, okay, detail in results:
    print(f"[{'PASS' if okay else 'FAIL'}] {name}" + (f" ({detail[:400]})" if detail and not okay else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
