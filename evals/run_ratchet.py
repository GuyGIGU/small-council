#!/usr/bin/env python3
"""The ratchet: size and structure numbers that may only go down (architecture §8, cleanup plan S2).

    python evals/run_ratchet.py             # measure, compare with evals/ratchet.json; exit 1 on a regression
    python evals/run_ratchet.py --update    # write today's numbers to the baseline; refuses to raise one
    python evals/run_ratchet.py --show      # also print every file the counts below name
    python evals/run_ratchet.py --self-test # plant each kind of regression in a scratch tree and catch it

What it measures, over bin/council, hooks/*.sh, scripts/*.py and src/**/*.py:
- per file: its lines, its longest function and, when shellcheck is on PATH, its ShellCheck warnings
  (bash only). A bash function runs from `name() {` at column 0 to the last column-0 `}` before the
  next function starts (or the file ends); one on a single line is one line long. A Python function
  is every def, nested or not, from its `def` line to its last line (ast).
- parsers: files outside src/council/records/ that parse a council file themselves. A file parses one
  when its code, outside comments and docstrings, holds a string that is one of COUNCIL_FILES or
  ends in `/` and one of them. COUNCIL_FILES is every file architecture §4's two tables name, read from
  the doc, and NOT_IN_ARCHITECTURE, the files the code parses that §4 doesn't name yet.
- config readers: functions that read council.config.md by that same rule, outside a bash
  `configured_*` function and src/council/records/config.py (top-level code counts as one per file).
- call-backs: Python files that run bin/council: a subprocess or os process call whose command holds
  the string `bin/council` or a name or attribute with "council" in it (architecture §2's cycle).
A Python file the baseline doesn't list is new and is held to the plan's rule 6: no function over
60 lines, no module over 500. So is every Python file in src/council/, listed or not: the package grows
as commands are ported, so its files are held to those limits rather than frozen at their sizes (the
user's call, 2026-11-14). bin/council, the hooks and scripts/ stay frozen. Any import in scripts/ or src/ that is neither the standard library
nor the project's own module fails outright (D32).

Python 3.8+, standard library only.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "evals/ratchet.json"
ARCHITECTURE = "docs/architecture.md"
# Council files the code reads or writes that architecture §4's tables do not name yet. Name a file in §4
# and take it off this list; the doc is the list's source, this is its known gap.
NOT_IN_ARCHITECTURE = ("claims.jsonl", "corrections.jsonl", "cap-allowances.tsv", "repair-allowances.tsv",
                       "tools.tsv", "tuning.md")
CONFIG = "council.config.md"


def architecture_files(text: str) -> list[str]:
    """The council files by name that the tables of architecture §4 list in their first column: the home
    files and the run folder's files. A folder (`runs/`), a pattern (`verify-<n>.md`) and a word are no name."""
    section = re.search(r"^## 4\..*?(?=^## 5\.)", text, re.MULTILINE | re.DOTALL)
    found = []
    for line in (section.group(0) if section else "").splitlines():
        if line.startswith("|"):
            found += re.findall(r"`([A-Za-z][A-Za-z0-9-]*(?:\.[a-z]+)+)`", line.split("|")[1])
    return [name for name in dict.fromkeys(found) if name.rsplit(".", 1)[1] in ("md", "tsv", "jsonl")]


def council_files(root: Path) -> tuple[str, ...]:
    """Every council file the ratchet guards: architecture §4's, then the known gap in it."""
    doc = root / ARCHITECTURE
    named = architecture_files(doc.read_text(encoding="utf-8", errors="replace")) if doc.is_file() else []
    return tuple(dict.fromkeys(named + list(NOT_IN_ARCHITECTURE)))


COUNCIL_FILES = council_files(ROOT)
NEW_FUNCTION, NEW_MODULE = 60, 500
CAPPED = "src/council/"                    # the package's sizes are held to rule 6, not frozen (2026-11-14)
SIZES = (("lines", "lines"), ("longest", "longest function"), ("shellcheck", "ShellCheck warnings"))
COUNTS = (("parsers", "files that parse a council file"), ("config_readers", "council.config.md readers"),
          ("callbacks", "scripts that run bin/council"))
BASH_START = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{")
PROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput",
                 "system", "popen"}


def write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as out:     # LF on Windows too, as the repo has it
        out.write(text)


def measured(root: Path) -> list[str]:
    """The files the ratchet measures, as posix paths relative to root."""
    found = [root / "bin" / "council"] + sorted((root / "hooks").glob("*.sh")) + \
        sorted((root / "scripts").glob("*.py")) + sorted((root / "src").rglob("*.py"))
    return [p.relative_to(root).as_posix() for p in found if p.is_file()]


def names_council_file(text: str) -> list[str]:
    """The council files a string names, by the parse rule: the whole string, or a `/` and the name at its end."""
    return [name for name in COUNCIL_FILES if text == name or text.endswith("/" + name)]


def bash_functions(lines: list[str]) -> list[tuple[str, int, int]]:
    """(name, first line, last line), 1-based, of each function by the rule in the module docstring."""
    starts = [i for i, line in enumerate(lines) if BASH_START.match(line)]
    found = []
    for k, start in enumerate(starts):
        name = lines[start].split("(", 1)[0]
        rest = re.sub(r"\$\{[^}]*\}", "", lines[start].split("{", 1)[1])
        if rest.count("}") > rest.count("{"):              # the function's own } closes on its first line
            found.append((name, start + 1, start + 1))
            continue
        stop = starts[k + 1] if k + 1 < len(starts) else len(lines)
        closes = [i for i in range(start + 1, stop) if lines[i].startswith("}")]
        found.append((name, start + 1, (closes[-1] if closes else stop - 1) + 1))
    return found


def bash_file(lines: list[str]) -> dict:
    functions = bash_functions(lines)
    longest = max(functions, key=lambda f: f[2] - f[1], default=("", 0, -1))
    parses, readers = set(), set()
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        named = [n for n in COUNCIL_FILES if re.search(r"/" + re.escape(n) + r"(?![\w.-])", line)]
        parses.update(named)
        if CONFIG in named:
            inside = [f[0] for f in functions if f[1] <= number <= f[2]]
            if not (inside and inside[-1].startswith("configured_")):
                readers.add(inside[-1] if inside else "<top level>")
    return {"lines": len(lines), "longest": longest[2] - longest[1] + 1, "longest_name": longest[0],
            "parses": sorted(parses), "config_readers": sorted(readers), "callback": False, "imports": []}


def docstrings(tree: ast.AST) -> set:
    found = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            found.add(id(body[0].value))
    return found


def runs_helper(call: ast.Call) -> bool:
    """A process call whose command names the helper, by the call-back rule in the module docstring."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    module = getattr(func.value, "id", "") if isinstance(func, ast.Attribute) else ""
    if not (name in PROCESS_CALLS or name.startswith(("exec", "spawn"))) or module not in ("", "subprocess", "os"):
        return False
    command = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "args"), None)
    for node in ast.walk(command) if command is not None else []:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "bin/council" in node.value:
            return True
        word = node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "") if isinstance(node, ast.Name) else ""
        if "council" in word.lower():
            return True
    return False


def python_file(text: str, path: str) -> dict:
    tree = ast.parse(text, filename=path)
    skip = docstrings(tree)
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    longest = max(functions, key=lambda f: f.end_lineno - f.lineno, default=None)
    parses, readers = set(), set()
    owners = {}
    for function in functions:            # innermost wins: ast.walk visits outer functions first
        for node in ast.walk(function):
            owners[id(node)] = function.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            named = names_council_file(node.value)
            parses.update(named)
            if CONFIG in named and path != "src/council/records/config.py":
                readers.add(owners.get(id(node), "<top level>"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            imports.append(node.module.split(".")[0])
    return {"lines": len(text.splitlines()),
            "longest": longest.end_lineno - longest.lineno + 1 if longest else 0,
            "longest_name": longest.name if longest else "", "parses": sorted(parses),
            "config_readers": sorted(readers), "imports": sorted(set(imports)),
            "callback": any(isinstance(n, ast.Call) and runs_helper(n) for n in ast.walk(tree))}


def shellcheck_warnings(root: Path, path: str, tool: str) -> int:
    out = subprocess.run([tool, "-S", "warning", "-f", "json1", path], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    try:
        return len(json.loads(out.stdout)["comments"])
    except (ValueError, KeyError) as exc:
        raise SystemExit("run_ratchet.py: shellcheck gave no report for %s (exit %d): %s" % (
            path, out.returncode, (out.stderr or str(exc)).strip()[:300])) from None


def standard_library() -> set:
    names = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
    return names or set(sys.builtin_module_names)


def is_standard(module: str, known: set) -> bool:
    if known and module in known:
        return True
    if hasattr(sys, "stdlib_module_names"):
        return False
    import importlib.util            # Python 3.8 and 3.9 have no list: ask where the module lives
    import sysconfig
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return False
    origin = (spec.origin or "") if spec else ""
    stdlib = os.path.normcase(sysconfig.get_paths()["stdlib"])
    return origin in ("built-in", "frozen") or (os.path.normcase(origin).startswith(stdlib)
                                                 and "site-packages" not in origin)


def measure(root: Path, shellcheck: str | None) -> dict:
    """Every number the ratchet compares, plus what the messages name."""
    files, counts, foreign = {}, {"parsers": [], "config_readers": [], "callbacks": []}, []
    local = {p.stem for p in (root / "scripts").glob("*.py")} | {p.name for p in (root / "src").glob("*")}
    known = standard_library()
    for path in measured(root):
        text = (root / path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        python = path.endswith(".py")
        info = python_file(text, path) if python else bash_file(text.split("\n")[:-1] if text.endswith("\n")
                                                                  else text.split("\n"))
        entry = {"lines": info["lines"], "longest": info["longest"], "longest_name": info["longest_name"]}
        if not python and shellcheck:
            entry["shellcheck"] = shellcheck_warnings(root, path, shellcheck)
        files[path] = entry
        if info["parses"] and not path.startswith("src/council/records/"):
            counts["parsers"].append(path)
        counts["config_readers"] += ["%s: %s" % (path, f) for f in info["config_readers"]]
        if info["callback"]:
            counts["callbacks"].append(path)
        foreign += ["%s: imports %s" % (path, m) for m in info["imports"]
                    if m not in local and not is_standard(m, known)]
    return {"files": files, "counts": {k: {"value": len(v), "items": v} for k, v in counts.items()},
            "foreign": foreign}


def compare(base: dict, now: dict) -> tuple[list[str], list[str]]:
    """(regressions, gains): one line each, naming the file, the measure, the baseline and the new value."""
    bad, good = [], []
    for path, entry in now["files"].items():
        old = base["files"].get(path)
        if old is None or (path.startswith(CAPPED) and path.endswith(".py")):
            kind = "new file, " if old is None else ""
            if path.endswith(".py") and entry["longest"] > NEW_FUNCTION:
                bad.append("%s: %slongest function %d lines (%s), rule 6 allows %d" % (
                    path, kind, entry["longest"], entry["longest_name"], NEW_FUNCTION))
            if path.endswith(".py") and entry["lines"] > NEW_MODULE:
                bad.append("%s: %s%d lines, rule 6 allows %d" % (path, kind, entry["lines"], NEW_MODULE))
            if entry.get("shellcheck"):
                bad.append("%s: new file, %d ShellCheck warnings, a new file starts at 0" % (path, entry["shellcheck"]))
            continue
        for key, label in SIZES:
            if key not in entry or key not in old:
                continue
            extra = " (%s)" % entry["longest_name"] if key == "longest" else ""
            if entry[key] > old[key]:
                bad.append("%s: %s %d, baseline %d%s" % (path, label, entry[key], old[key], extra))
            elif entry[key] < old[key]:
                good.append("%s: %s %d, baseline %d" % (path, label, entry[key], old[key]))
    good += ["%s: gone, still in the baseline" % path for path in base["files"] if path not in now["files"]]
    for key, label in COUNTS:
        old, new = base["counts"].get(key, {"value": 0, "items": []}), now["counts"][key]
        if new["value"] > old["value"]:
            added = [item for item in new["items"] if item not in old["items"]]
            bad.append("%s: %d, baseline %d%s" % (label, new["value"], old["value"],
                                                  " (new: %s)" % ", ".join(added) if added else ""))
        elif new["value"] < old["value"]:
            good.append("%s: %d, baseline %d" % (label, new["value"], old["value"]))
    bad += ["%s, outside the standard library (D32)" % line for line in now["foreign"]]
    return bad, good


def baseline_of(now: dict, base: dict | None) -> dict:
    """Today's numbers as a baseline. ShellCheck counts not measured this time are kept from the old one."""
    files = {}
    for path, entry in now["files"].items():
        files[path] = dict(entry)
        old = (base or {}).get("files", {}).get(path, {})
        if "shellcheck" not in entry and "shellcheck" in old:
            files[path]["shellcheck"] = old["shellcheck"]
    return {"about": "Written by python evals/run_ratchet.py --update; numbers here may only go down.",
            "files": files, "counts": now["counts"]}


def run(root: Path, update: bool = False, show: bool = False, shellcheck: str | None = None) -> tuple[int, list[str]]:
    """The ratchet over root: (exit code, output lines)."""
    now = measure(root, shellcheck)
    target = root / BASELINE
    base = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
    out = []
    if show:
        for key, label in COUNTS:
            out += ["%s (%d):" % (label, now["counts"][key]["value"])] + \
                ["  " + item for item in now["counts"][key]["items"]]
    sc = "ShellCheck measured" if shellcheck else "ShellCheck skipped (not on PATH)"
    if base is None and not update:
        return 2, out + ["ratchet: no %s yet; write it with: python evals/run_ratchet.py --update" % BASELINE]
    if base is None:                       # the first baseline: today's numbers are the start, whatever they are
        bad, good = ["%s, outside the standard library (D32)" % line for line in now["foreign"]], []
    else:
        bad, good = compare(base, now)
    if update:
        if bad:
            return 2, out + ["REGRESSION " + line for line in bad] + [
                "ratchet: --update refused: it never raises a number. Bring the %d above back down first" % len(bad)]
        write(target, json.dumps(baseline_of(now, base), indent=1, sort_keys=True) + "\n")
        return 0, out + ["ratchet: wrote %s (%d files; %d numbers went down); %s" % (BASELINE, len(now["files"]),
                                                                                     len(good), sc)]
    total = sum(len([k for k, _ in SIZES if k in e]) for e in now["files"].values()) + len(COUNTS) + 1
    out += ["REGRESSION " + line for line in bad]
    hint = "; %d went down: keep the gain with --update" % len(good) if good else ""
    out.append("%d/%d checks passed: %s; %s%s" % (total - len(bad), total, "%d regression%s" % (len(bad), "" if len(bad) == 1 else "s") if bad
                                                  else "no number rose above " + BASELINE, sc, hint))
    return (1 if bad else 0), out


def main() -> int:
    parser = argparse.ArgumentParser(description="Size and structure numbers that may only go down.")
    parser.add_argument("--update", action="store_true", help="write today's numbers; refuses to raise one")
    parser.add_argument("--show", action="store_true", help="also print the files each count names")
    parser.add_argument("--self-test", action="store_true", help="plant each regression in a scratch tree")
    opts = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if opts.self_test:
        return self_test()
    code, out = run(ROOT, opts.update, opts.show, shutil.which("shellcheck"))
    print("\n".join(out))
    return code


# --- self-test: each check plants one thing in a scratch tree and runs the ratchet over it ----------

BASH = """#!/usr/bin/env bash
die() { printf '%s\\n' "$1" >&2; exit 2; }
configured_cap() {
  awk '/cap/' "$home/council.config.md"
}
reader() {
  # a comment naming session-state.md is not a parse
  awk '
function trim(s) {
  return s
}
' "$home/council.config.md"
}
"""
SCRIPT = '''"""A script. Its docstring names events.tsv, which is not a parse."""
import json
import subprocess
from sibling import thing


def show(run):
    rows = (run / "events.tsv").read_text()
    return json.dumps(rows)


def ask(self, words):
    return subprocess.run([self.bash, self.council] + list(words))
'''
SIBLING = 'import subprocess\nPATHS = ["hooks/gate.sh"]\nthing = subprocess.run(["git", "ls-files", *PATHS])\n'


def scratch_tree(top: Path) -> Path:
    for rel, text in (("bin/council", BASH), ("hooks/gate.sh", "#!/usr/bin/env bash\nexit 0\n"),
                      ("scripts/show.py", SCRIPT), ("scripts/sibling.py", SIBLING),
                      ("src/council/lib.py", "def f():\n    return 1\n")):
        (top / rel).parent.mkdir(parents=True, exist_ok=True)
        write(top / rel, text)
    (top / "evals").mkdir(exist_ok=True)
    return top


def edit(path: Path, old: str, new: str) -> None:
    write(path, path.read_text(encoding="utf-8").replace(old, new, 1))


def self_test() -> int:
    results = []

    def check(name: str, ok: bool, detail: object = "") -> None:
        results.append(ok)
        print("[%s] %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))

    with tempfile.TemporaryDirectory() as tmp:
        top = scratch_tree(Path(tmp))
        now = measure(top, None)
        files = now["files"]
        check("bash: a one-line function is 1 line; an awk program's column-0 } stays inside its function",
              files["bin/council"]["longest"] == 8 and files["bin/council"]["longest_name"] == "reader", files)
        check("python: the longest def is measured through ast", files["scripts/show.py"]["longest"] == 3, files)
        counts = {k: v["items"] for k, v in now["counts"].items()}
        check("parsers: a path to events.tsv counts; a docstring or comment naming one does not",
              counts["parsers"] == ["bin/council", "scripts/show.py"], counts["parsers"])
        check("config readers: configured_* is the one way; another function reading the config counts",
              counts["config_readers"] == ["bin/council: reader"], counts["config_readers"])
        check("call-backs: a process call naming self.council counts; git with a list of paths does not",
              counts["callbacks"] == ["scripts/show.py"], counts["callbacks"])
        code, out = run(top)
        check("no baseline: refused, naming --update", code == 2 and "--update" in out[-1], out)
        code, out = run(top, update=True)
        check("--update writes the first baseline", code == 0 and (top / BASELINE).is_file(), out)
        code, out = run(top)
        check("unchanged tree: exit 0 and no regression", code == 0 and "REGRESSION" not in "\n".join(out), out)
        edit(top / "scripts/show.py", "    return json.dumps(rows)", "    rows = rows\n    return json.dumps(rows)")
        code, out = run(top)
        check("a function one line longer fails, naming the file, the measure, the baseline and the new value",
              code == 1 and "REGRESSION scripts/show.py: longest function 4, baseline 3 (show)" in out, out)
        saved = (top / BASELINE).read_text(encoding="utf-8")
        code, out = run(top, update=True)
        check("--update refuses to raise a number and leaves the baseline alone",
              code == 2 and "refused" in out[-1] and (top / BASELINE).read_text(encoding="utf-8") == saved, out)
        edit(top / "scripts/show.py", "    rows = rows\n", "")
        code, out = run(top)
        check("the regression removed: exit 0 again", code == 0, out)
        edit(top / "bin/council", "  return s\n", "")
        code, out = run(top)
        check("a number that went down passes and says --update keeps it", code == 0 and "--update" in out[-1], out)
        code, out = run(top, update=True)
        check("--update lowers it", code == 0 and json.loads((top / BASELINE).read_text())["files"]["bin/council"]
              ["longest"] == 7, out)
        edit(top / "scripts/show.py", "import json\n", "import json\nimport requests\n")
        code, out = run(top)
        check("an import outside the standard library fails (D32)",
              code == 1 and any("scripts/show.py: imports requests" in line for line in out), out)
        edit(top / "scripts/show.py", "import requests\n", "")
        new = top / "scripts" / "fresh.py"
        write(new, "def long():\n" + "    x = 1\n" * 60)
        code, out = run(top)
        check("a new file's 61-line function fails rule 6",
              code == 1 and any("fresh.py: new file, longest function 61" in line for line in out), out)
        write(new, "def long():\n" + "    x = 1\n" * 59)
        check("a new file's 60-line function passes", run(top)[0] == 0, run(top)[1])
        write(new, "x = 1\n" * 501)
        code, out = run(top)
        check("a new 501-line module fails rule 6", code == 1 and any("501 lines" in line for line in out), out)
        write(new, 'LOG = "runs/x/seats.tsv"\n')
        code, out = run(top)
        check("a new file that parses a council file raises the count and is named",
              code == 1 and any("files that parse a council file: 3, baseline 2 (new: scripts/fresh.py)" in line
                                for line in out), out)
        write(new, 'import json\nCLAIMS = "claims.jsonl"\n')
        code, out = run(top)
        check("a new file that parses claims.jsonl (not in the old list of seven) raises the count and is named",
              code == 1 and any("files that parse a council file: 3, baseline 2 (new: scripts/fresh.py)" in line
                                for line in out), out)
        new.unlink()
        check("with the planted parser removed, the count is back at its baseline", run(top)[0] == 0, run(top)[1])
        lib = top / "src/council/lib.py"
        write(lib, "def f():\n" + "    x = 1\n" * 59)
        code, out = run(top)
        check("a src/council file that grows within rule 6 passes: the package is held to limits, not frozen",
              code == 0 and "lib.py" not in "\n".join(out), out)
        write(lib, "def f():\n" + "    x = 1\n" * 60)
        code, out = run(top)
        check("a src/council file's 61-line function fails rule 6, though the baseline lists the file",
              code == 1 and "REGRESSION src/council/lib.py: longest function 61 lines (f), rule 6 allows 60" in out,
              out)
        write(lib, "x = 1\n" * 501)
        code, out = run(top)
        check("a src/council file of 501 lines fails rule 6",
              code == 1 and "REGRESSION src/council/lib.py: 501 lines, rule 6 allows 500" in out, out)
        write(lib, "def f():\n    return 1\n")
        check("every council file architecture §4 names is guarded, and no folder or pattern is",
              set(architecture_files((ROOT / ARCHITECTURE).read_text(encoding="utf-8"))) <= set(COUNCIL_FILES)
              and not any("/" in n or "<" in n for n in COUNCIL_FILES), COUNCIL_FILES)
        sample = ("## 4. x\n| File | W |\n|---|---|\n| `a.md` (memory) | x |\n| `b.tsv`, `c.jsonl` | `d.md` |\n"
                  + "| `runs/<t>/`, `e-<n>.md`, `f/` | y |\n## 5. y\n| `g.md` | z |\n")
        check("§4's first column gives the names; other columns, folders, patterns and later sections do not",
              architecture_files(sample) == ["a.md", "b.tsv", "c.jsonl"], architecture_files(sample))
        sc = shutil.which("shellcheck")
        code, out = run(top, shellcheck=None)
        check("without shellcheck, its counts are reported as skipped", "ShellCheck skipped" in out[-1], out)
        if sc:
            run(top, update=True, shellcheck=sc)
            edit(top / "hooks/gate.sh", "exit 0", "cd /tmp\nexit 0")
            code, out = run(top, shellcheck=sc)
            check("with shellcheck, a new warning fails", code == 1 and any("ShellCheck warnings 1, baseline 0" in l
                                                                            for l in out), out)
    passed = sum(results)
    print("\n%d/%d checks passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
