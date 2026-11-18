#!/usr/bin/env python3
"""The release tree stands alone (D45): built by scripts/build_release.py, it holds only what runs, what
runs finds everything it needs inside it, and scripts/publish_release.py publishes exactly that tree.

    python evals/run_release.py               # build this checkout's tree (--worktree) into a temp folder, check it
    python evals/run_release.py --tree DIR    # check a tree built already (publish_release.py does, before it commits)

- the build: it exits 0, a second build is byte-identical, a non-empty folder is refused, and in a scratch
  repo a shipped file with uncommitted changes is refused unless --worktree says to build it as it is;
- the tree: its top-level entries are exactly REQUIRED (pinned here, not read from the build's list), it is
  under CEILING bytes, the scripts are executable (POSIX only: Windows keeps no mode), plugin.json names
  nothing in the dev tree, and its marketplace.json lists the tree itself ("./");
- every path plugin.json and hooks.json name exists, and every ${CLAUDE_PLUGIN_ROOT}/<path> a shipped
  skill, agent, reference or hook names; every relative Markdown link resolves inside the tree;
- no shipped file reaches a top-level name of this repository that doesn't ship (python_problems and
  script_problems say what they see: paths written out, not ones built at run time);
- the checks above are live: a copy with references/ taken off, and planted reads in the forms a review
  found (os.path.join from __file__, a tuple of parts, importlib, $(dirname "$0")/..), each fail them;
- a smoke run, on a copy of the tree, with its own bin/council in a scratch git repo (help, init scaffold
  --quick, run open council-review, doctor, run close), and each hook started as hooks.json starts it:
  exit 0, the SessionStart orientation printed, and a seat-gate and a bash-gate refusal;
- publishing, against a scratch bare repository: a first publish (no parent), the same tree again (no
  commit), a later version (one commit, the first its parent), the five scripts 100755 and no .pyc, the same
  or an older version with other files refused, a failed eval and a file found beside the build refused,
  and the token never in the eval's environment, a printed line, a config file or a git argument;
- and the suite leaves the tree it checks as it found it, byte for byte.
Mentions of a dev-tree path in shipped text (a docstring, a comment, a doc for a person) are no read;
they are listed as notes, and fail nothing.

Python 3.8+, standard library only; bash and git for the smoke run and the publishing scenarios.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_release  # noqa: E402  (the one list of what ships)

PY = sys.executable
BS = chr(92)
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
CEILING = 2_600_000                 # bytes: 2,088,506 measured at 1.1.0 (2026-11-18), plus a quarter
DEV = ("evals", "tests", "docs", "scripts", "examples")
# What the installed plugin needs at its top level, pinned here and not read from the build's own list,
# so that taking a needed entry off SHIPPED fails this suite instead of passing it.
REQUIRED = {".claude-plugin", ".gitattributes", "LICENSE", "NOTICE", "README.md", "agents", "bin", "hooks",
            "references", "skills", "src", "types"}
SHIPPED_DIRS = ("agents", "bin", "hooks", "references", "skills", "src", "types")
ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
           GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
for name in ("CLAUDE_CODE_SESSION_ID", "COUNCIL_ALLOW_NO_HOOKS", "COUNCIL_RUN", "COUNCIL_PLUGIN_ROOT", "COUNCIL_BASE"):
    ENV.pop(name, None)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
results, notes = [], []


def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))


def snapshot(tree):
    """Each file of the tree and the sha256 of its bytes."""
    return {f: hashlib.sha256((tree / f).read_bytes()).hexdigest() for f in files_of(tree)}


def files_of(tree):
    return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())


def text_of(tree, rel):
    return (tree / rel).read_text(encoding="utf-8", errors="replace")


# ---- what the tree holds -------------------------------------------------------------------------------

def build(dest):
    p = subprocess.run([PY, str(ROOT / "scripts" / "build_release.py"), "--worktree", str(dest)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def build_checks(scratch):
    first, second = scratch / "first", scratch / "second"
    code, out, err = build(first)
    check("build: exits 0 and says what it wrote", code == 0 and out.startswith("Wrote "), out + err)
    code2, _, err2 = build(second)
    same = code2 == 0 and files_of(first) == files_of(second) and all(
        (first / f).read_bytes() == (second / f).read_bytes() for f in files_of(first))
    check("build: a second build of the same checkout is byte-identical", same, err2)
    code3, out3, err3 = build(first)
    check("build: refuses a folder that is not empty (exit 2, stderr, names the next step)",
          code3 == 2 and not out3 and "empty" in err3, (code3, out3, err3))
    return first


def tree_checks(tree):
    tops = sorted(p.name for p in tree.iterdir())
    check("tree: its top-level entries are exactly REQUIRED, nothing else", tops == sorted(REQUIRED),
          "extra: %s; missing: %s" % (sorted(set(tops) - REQUIRED), sorted(REQUIRED - set(tops))))
    check("tree: the build's SHIPPED list names exactly REQUIRED's top-level entries",
          build_release.top_entries() == sorted(REQUIRED), build_release.top_entries())
    size = sum((tree / f).stat().st_size for f in files_of(tree))
    check("tree: %d files, %d bytes, under the ceiling of %d" % (len(files_of(tree)), size, CEILING), size <= CEILING)
    if os.name == "posix":
        executable = [f for f in ("bin/council", *sorted(p.relative_to(tree).as_posix() for p in (tree / "hooks").glob("*.sh")))
                      if os.access(str(tree / f), os.X_OK)]
        check("tree: bin/council and the hook scripts git marks executable are executable",
              {"bin/council", "hooks/session-start.sh", "hooks/agent-gate.sh", "hooks/bash-gate.sh",
               "hooks/seat-gate.sh"} <= set(executable), executable)
    plugin = json.loads(text_of(tree, ".claude-plugin/plugin.json"))
    market = json.loads(text_of(tree, ".claude-plugin/marketplace.json"))
    check("tree: plugin.json names nothing in the dev tree (no experimental.evals)",
          "evals" not in (plugin.get("experimental") or {}), plugin.get("experimental"))
    check("tree: marketplace.json lists the tree itself, source \"./\", by plugin.json's name",
          [(e.get("name"), e.get("source")) for e in market.get("plugins", [])] == [(plugin["name"], "./")],
          market.get("plugins"))


# ---- what the tree's files name ------------------------------------------------------------------------

def strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, str):
        yield value


def manifest_problems(tree):
    """Each path plugin.json or hooks.json names that isn't in the tree."""
    problems = []
    plugin = json.loads(text_of(tree, ".claude-plugin/plugin.json"))
    problems += ["plugin.json: %s" % v for v in strings(plugin) if v.startswith("./") and not (tree / v).exists()]
    hooks = json.loads(text_of(tree, "hooks/hooks.json"))
    problems += ["hooks.json: module %s" % m for m in hooks.get("modules", []) if not (tree / "hooks" / m).is_file()]
    for command in strings(hooks.get("hooks", {})):
        for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)", command):
            if not (tree / ref).is_file():
                problems.append("hooks.json: %s" % ref)
    return problems


def plugin_root_problems(tree):
    """Each ${CLAUDE_PLUGIN_ROOT}/<path> named in a shipped skill, agent, reference or hook that isn't in the tree."""
    problems = []
    for rel in files_of(tree):
        if rel.split("/")[0] not in ("skills", "agents", "references", "hooks"):
            continue
        for found in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`\"')\]|]*)", text_of(tree, rel)):
            path = found.group(1).rstrip("\\.,:;")
            if path and not any(c in path for c in "<*…{$") and not (tree / path).exists():
                problems.append("%s: ${CLAUDE_PLUGIN_ROOT}/%s" % (rel, path))
    return problems


def prose(text):
    """Markdown with its fenced blocks and code spans blanked: a link written as code is no link."""
    text = re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.MULTILINE | re.DOTALL)
    return re.sub(r"`[^`\n]*`", "", text)


def link_problems(tree):
    """Each relative Markdown link in a shipped .md file that doesn't resolve inside the tree."""
    problems, top = [], tree.resolve()
    for rel in [f for f in files_of(tree) if f.endswith(".md")]:
        for target in re.findall(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)", prose(text_of(tree, rel))):
            path = unquote(target.split("#")[0])
            if not path or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", path):
                continue
            resolved = ((tree / rel).parent / path).resolve()
            if top not in (resolved, *resolved.parents) or not resolved.exists():
                problems.append("%s: (%s)" % (rel, target))
    return problems


# ---- what the tree's code reads ------------------------------------------------------------------------

def off_tree():
    """Every top-level name of this repository that doesn't ship: what no shipped code may reach."""
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8")
    return ({path.split("/")[0] for path in listed.split("\0") if path} | set(DEV)) - REQUIRED


def docstrings(module):
    found = set()
    for node in ast.walk(module):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            found.add(id(body[0].value))
    return found


def roots(module):
    """Names bound, anywhere in the module, to a value built from the plugin's own folder."""
    names = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Assign) and touches_root(node.value, set()):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def touches_root(node, names):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and (n.id == "__file__" or n.id in names):
            return True
        if isinstance(n, ast.Call) and "plugin_root" in (getattr(n.func, "id", ""), getattr(n.func, "attr", "")):
            return True
    return False


def first_part(value):
    """A path's first name, past any leading ./, ../ or /: '../../docs/x' is 'docs'."""
    return re.split(r"[\\/]", re.sub(r"^(?:\.{1,2}[\\/]|[\\/])+", "", value), maxsplit=1)[0]


def str_constants(module):
    """Module-level names bound to a string, or to a tuple or list of strings: name -> its strings."""
    found = {}
    for node in module.body:
        if isinstance(node, ast.Assign):
            value = node.value
            items = [value] if isinstance(value, ast.Constant) else list(getattr(value, "elts", []))
            words = [i.value for i in items if isinstance(i, ast.Constant) and isinstance(i.value, str)]
            found.update({t.id: words for t in node.targets if isinstance(t, ast.Name) and words})
    return found


def imported(node):
    """The module names an import statement, importlib.import_module or __import__ names as literals."""
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        return [] if node.level else [node.module or ""]
    if isinstance(node, ast.Call) and (getattr(node.func, "attr", "") == "import_module" or
                                       getattr(node.func, "id", "") in ("import_module", "__import__")):
        return [a.value for a in node.args[:1] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return []


def python_problems(tree, rel, off):
    """A shipped Python file's imports of an unshipped name; its unshipped names joined to the plugin's
    folder (a literal, or a module-level name bound to a string or a tuple or list of them, anywhere in an
    expression built from __file__ or plugin_root()); and its constants under a shipped folder that match no
    file in the tree. It sees only literals: a path built at run time from a variable, a loop or the
    environment is not seen (the smoke run covers the paths it exercises)."""
    module, problems = ast.parse(text_of(tree, rel)), []
    skip, bound, consts = docstrings(module), roots(module), str_constants(module)
    for node in ast.walk(module):
        problems += ["%s:%d imports %s" % (rel, node.lineno, n) for n in imported(node) if n.split(".")[0] in off]
        if isinstance(node, (ast.BinOp, ast.Call, ast.JoinedStr)) and touches_root(node, bound):
            words = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            words += [w for n in ast.walk(node) if isinstance(n, ast.Name) for w in consts.get(n.id, [])]
            problems += ["%s:%d joins %r to the plugin's folder" % (rel, node.lineno, w)
                         for w in words if first_part(w) in off]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip \
                and first_part(node.value) in SHIPPED_DIRS and "/" in node.value:
            pattern = re.sub(r"%[0-9]*[sd]|\{[^}]*\}", "*", node.value).rstrip("/") or "."
            if not list(tree.glob(pattern)):
                problems.append("%s:%d names %s, not in the tree" % (rel, node.lineno, node.value))
    return problems


# A path on the plugin's folder in bash or TypeScript: $ROOT/…, ${CLAUDE_PLUGIN_ROOT}/…, ${root}/…, $(… pwd)/….
ON_ROOT = re.compile(r"(?:\$\{?[A-Z_]*ROOT\}?|\$\{root\}|pwd\))\"?/([A-Za-z0-9_.\-/]+)")
# A path on the script's own folder: $(dirname "$0")/…, $(dirname "${BASH_SOURCE[0]}")/…, ${BASH_SOURCE[0]%/*}/….
ON_SELF = re.compile(r"(?:\$\(dirname\s+\"?\$(?:0|\{?BASH_SOURCE(?:\[0\])?\}?)\"?\)|\$\{BASH_SOURCE\[0\]%[^}]*\})"
                     r"\"?/([A-Za-z0-9_.\-/]+)")


def script_problems(tree, rel):
    """A shipped bash or TypeScript file's paths on the plugin's folder or on its own folder, and relative
    imports, that are not in the tree. Like the Python check it sees paths written out, not ones a variable
    carries."""
    problems, top = [], tree.resolve()
    for number, line in enumerate(text_of(tree, rel).splitlines(), 1):
        if re.match(r"\s*(#|//)", line):
            continue
        targets = [tree / p for p in ON_ROOT.findall(line)] + [(tree / rel).parent / p for p in ON_SELF.findall(line)]
        for target in targets:
            resolved = Path(os.path.normpath(str(target)))
            if top not in (resolved, *resolved.parents) or not resolved.exists():
                problems.append("%s:%d reads %s" % (rel, number, os.path.relpath(str(resolved), str(top)).replace(BS, "/")))
        for spec in re.findall(r"from '(\.\.?/[^']+)'", line):
            base = ((tree / rel).parent / spec).resolve()
            if not any(Path(str(base) + ext).is_file() for ext in ("", ".ts", ".tsx", ".d.ts", "/index.d.ts", "/index.ts")):
                problems.append("%s:%d imports %s" % (rel, number, spec))
    return problems


def code_problems(tree, off=None):
    off = off_tree() if off is None else off
    problems = []
    for rel in files_of(tree):
        if rel.endswith(".py"):
            problems += python_problems(tree, rel, off)
        elif rel == "bin/council" or rel.startswith("hooks/") and rel.endswith((".sh", ".ts", ".tsx")):
            problems += script_problems(tree, rel)
    return list(dict.fromkeys(problems))     # a call and the sum inside it name the same join once


def mention_notes(tree):
    """Where shipped text names a dev-tree path for a person to read: no read, but a link that leads nowhere."""
    found = []
    pattern = re.compile(r"(?<![\w./-])((?:evals|docs|scripts)/[\w./-]+|tests/py[\w./-]*|CHANGELOG\.md|CONTRIBUTING\.md)")
    for rel in files_of(tree):
        if rel.endswith((".md", ".py", ".sh", ".ts", ".tsx", ".json")) or rel == "bin/council":
            for number, line in enumerate(text_of(tree, rel).splitlines(), 1):
                found += ["%s:%d names %s" % (rel, number, m) for m in pattern.findall(line)]
    return found


def static_checks(tree):
    for name, finder in (("plugin.json and hooks.json name only paths in the tree", manifest_problems),
                         ("every ${CLAUDE_PLUGIN_ROOT}/<path> a skill, agent, reference or hook names is in the tree",
                          plugin_root_problems),
                         ("every relative Markdown link resolves inside the tree", link_problems),
                         ("no dev-tree import, and every path the code joins to the plugin's folder is in the tree",
                          code_problems)):
        problems = finder(tree)
        check("tree: " + name, not problems, "; ".join(problems[:8]))
    notes.extend(mention_notes(tree))


# The four forms an independent review planted, each a read of a file that doesn't ship.
PLANTED = (
    ("src/planted_a.py", "import os\nfrom os.path import dirname\n"
                         "open(os.path.join(dirname(__file__), '..', '..', '..', 'CHANGELOG.md'))\n"),
    ("src/planted_b.py", "from pathlib import Path\nPARTS = ('docs', 'decisions.md')\n"
                         "Path(__file__).parents[3].joinpath(*PARTS).read_text()\n"),
    ("src/planted_c.py", "import importlib\nimportlib.import_module('evals.run_replay')\n"),
    ("hooks/planted_d.sh", 'cat "$(dirname "$0")/../docs/architecture.md"\n'),
)


def planted_checks(tree, scratch):
    """The static checks fail on a tree that lacks what runs, and on a planted dev-tree read."""
    cut = scratch / "cut"
    shutil.copytree(str(tree), str(cut))
    shutil.rmtree(str(cut / "references"), ignore_errors=True)
    check("planted: with references/ off the list, the ${CLAUDE_PLUGIN_ROOT} and code-path checks fail",
          plugin_root_problems(cut) and code_problems(cut))
    planted = scratch / "planted"
    shutil.copytree(str(tree), str(planted))
    (planted / "src" / "planted.py").write_text(
        "from evals import run_cli\nfrom council.records.home import plugin_root\nNOTES = 'docs/decisions.md'\n"
        "open(plugin_root() + '/' + NOTES)\n", encoding="utf-8")
    (planted / "hooks" / "planted.sh").write_text('bash "$ROOT/evals/run_hook.py"\n', encoding="utf-8")
    (planted / "skills" / "planted.md").write_text("See [the decisions](../docs/decisions.md).\n", encoding="utf-8")
    for rel, text in PLANTED:
        (planted / rel).write_text(text, encoding="utf-8")
    problems = code_problems(planted)
    first = [x for x in problems if x.startswith(("src/planted.py:", "hooks/planted.sh:"))]
    check("planted: a dev-tree import, a docs/ path joined to plugin_root() and a hook reading $ROOT/evals all fail",
          len(first) == 3, first)
    for rel, text in PLANTED:
        found = [x for x in problems if x.startswith(rel + ":")]
        check("planted: %s is caught (%s)" % (rel, text.strip().splitlines()[-1][:70]), found, found)
    check("planted: nothing but the planted files is reported", all("planted" in x for x in problems),
          [x for x in problems if "planted" not in x])
    check("planted: a Markdown link out to docs/ fails", link_problems(planted) == ["skills/planted.md: (../docs/decisions.md)"],
          link_problems(planted))


# ---- the smoke run -------------------------------------------------------------------------------------

def council(tree, repo, env, *words):
    p = subprocess.run([BASH, str(tree / "bin" / "council"), *words], cwd=str(repo), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120)
    return p.returncode, p.stdout, p.stderr


def hook(tree, repo, env, event, payload, matcher_for=None):
    """hooks.json's own command for the event (the group whose matcher takes matcher_for), run with bash -c."""
    groups = json.loads(text_of(tree, "hooks/hooks.json"))["hooks"][event]
    group = next(g for g in groups if matcher_for is None or re.search(g["matcher"], matcher_for))
    command = group["hooks"][0]["command"]
    p = subprocess.run([BASH, "-c", command], cwd=str(repo), input=json.dumps(payload), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def smoke_commands(tree, repo, env):
    for words in (["help"], ["init", "scaffold", "--quick"]):
        code, out, err = council(tree, repo, env, *words)
        check("smoke: council %s exits 0" % " ".join(words), code == 0 and out, (code, err[-400:]))
    code, out, err = council(tree, repo, env, "run", "open", "council-review")
    run = Path(out.strip().splitlines()[0]) if code == 0 and out.strip() else None
    check("smoke: council run open council-review exits 0 and opens a run folder",
          run is not None and (run / "session-state.md").is_file(), (code, out[-300:], err[-300:]))
    code, out, err = council(tree, repo, env, "doctor")
    check("smoke: council doctor exits 0", code == 0, (code, out[-300:], err[-300:]))
    code, out, err = council(tree, repo, env, "run", "close", "--status", "abandoned")
    check("smoke: council run close --status abandoned exits 0 and closes it", code == 0 and "abandoned" in out,
          (code, out[-300:], err[-300:]))


def smoke_hooks(tree, repo, env):
    base = {"session_id": "smoke-1", "cwd": str(repo), "transcript_path": "/x/t.jsonl"}
    tool = dict(base, hook_event_name="PreToolUse")
    worker = dict(base, hook_event_name="SubagentStop", agent_type="small-council:council-worker", agent_id="a1",
                  stop_hook_active=False)
    cases = (
        ("SessionStart prints the orientation", "SessionStart", dict(base, hook_event_name="SessionStart",
                                                                    source="startup"), None, 0),
        ("the agent gate lets an ordinary agent through", "PreToolUse", dict(tool, tool_name="Agent", tool_input={
            "description": "d", "prompt": "p", "subagent_type": "general-purpose"}), "Agent", 0),
        ("the bash gate lets ls through", "PreToolUse", dict(tool, tool_name="Bash", tool_input={"command": "ls"}),
         "Bash", 0),
        ("the Stop hook lets the turn end", "Stop", dict(base, hook_event_name="Stop", stop_hook_active=False), None, 0),
        ("the seat gate lets a BLOCKED worker stop", "SubagentStop",
         dict(worker, last_assistant_message="BLOCKED: smoke run"), worker["agent_type"], 0),
        ("the bash gate refuses council piped into head", "PreToolUse",
         dict(tool, tool_name="Bash", tool_input={"command": "council status | head"}), "Bash", 2),
        ("the seat gate sends back a worker with no Wrote line (through the tree's helper)", "SubagentStop",
         dict(worker, last_assistant_message="done"), worker["agent_type"], 2),
    )
    for label, event, payload, matcher_for, want in cases:
        code, out, err = hook(tree, repo, env, event, payload, matcher_for)
        check("smoke hook: %s (exit %d)" % (label, want), code == want and
              (event != "SessionStart" or "council" in out.lower()) and (want == 0 or err), (code, out[-300:], err[-300:]))


def smoke(tree, scratch):
    if not BASH or not shutil.which("git"):
        check("smoke: bash and git are on PATH", False, "the smoke run needs both")
        return
    home, repo, copy = scratch / "home", scratch / "repo", scratch / "smoke-tree"
    home.mkdir()
    repo.mkdir()
    shutil.copytree(str(tree), str(copy))     # Python writes __pycache__ beside what it runs: never into the tree
    tree = copy
    env = dict(ENV, HOME=str(home), XDG_CACHE_HOME=str(home / ".cache"), CLAUDE_PLUGIN_ROOT=str(tree),
               CLAUDE_PROJECT_DIR=str(repo))
    for words in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "start"]):
        subprocess.run(["git", *words], cwd=str(repo), env=env, capture_output=True)
    smoke_commands(tree, repo, env)
    smoke_hooks(tree, repo, env)


# ---- the build's rule, and publishing ------------------------------------------------------------------

EXECUTABLE = {"bin/council", "hooks/agent-gate.sh", "hooks/bash-gate.sh", "hooks/seat-gate.sh", "hooks/session-start.sh"}
IDENTITY = {"GIT_AUTHOR_NAME": "eval", "GIT_AUTHOR_EMAIL": "eval@example.invalid", "GIT_COMMITTER_NAME": "eval",
            "GIT_COMMITTER_EMAIL": "eval@example.invalid"}


def git_out(repo, *words):
    done = subprocess.run(["git", "-C", str(repo), *words], capture_output=True, env=ENV)
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def build_rule_checks(tree, scratch):
    """The build refuses shipped files with uncommitted changes unless told --worktree: in a scratch repo."""
    del tree
    mini = scratch / "mini"
    for rel in ("scripts/build_release.py", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        (mini / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(ROOT / rel), str(mini / rel))
    skill = mini / "skills" / "a" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes(b"one\n")
    for words in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "start"]):
        subprocess.run(["git", *words], cwd=str(mini), env=ENV, capture_output=True)
    skill.write_bytes(b"two\n")

    def run_build(*words):
        p = subprocess.run([PY, str(mini / "scripts" / "build_release.py"), *words], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr
    code, out, err = run_build(str(scratch / "mini-dirty"))
    check("build: refuses a shipped file with uncommitted changes (exit 2, stderr, names it and --worktree)",
          code == 2 and not out and "skills/a/SKILL.md" in err and "--worktree" in err
          and not (scratch / "mini-dirty").exists(), (code, out, err))
    code, out, err = run_build("--worktree", str(scratch / "mini-worktree"))
    check("build: --worktree builds the working tree as it is, edits and all",
          code == 0 and (scratch / "mini-worktree" / "skills" / "a" / "SKILL.md").read_bytes() == b"two\n", (code, err))


def variant(scratch, name, source, records, version=None, readme=b""):
    """A copy of a built tree with its version set or its README grown, and its records to match."""
    folder = scratch / name
    shutil.copytree(str(source), str(folder))
    if version:
        plugin = json.loads(text_of(folder, ".claude-plugin/plugin.json"))
        plugin["version"] = version
        (folder / ".claude-plugin" / "plugin.json").write_bytes(build_release.as_json(plugin))
    if readme:
        (folder / "README.md").write_bytes((folder / "README.md").read_bytes() + readme)
    return folder, [(p, m, hashlib.sha256((folder / p).read_bytes()).hexdigest()) for p, m, _ in records]


def published(remote):
    """The release branch's tip on the scratch remote: (commit, its parents, path -> mode, its message)."""
    commit = git_out(remote, "rev-parse", "release")
    parents = git_out(remote, "rev-list", "--parents", "-n", "1", "release").split()[1:]
    modes = {line.split("\t", 1)[1]: line.split()[0] for line in git_out(remote, "ls-tree", "-r", "release").splitlines()}
    return commit, parents, modes, git_out(remote, "log", "-1", "--format=%s", "release")


def attempt(step, *args, **kwargs):
    """A publish step's (0, its line) or (2, the refusal)."""
    try:
        return 0, step(*args, **kwargs)
    except build_release.Refusal as why:
        return 2, str(why)


def publish_checks(tree, scratch):
    """scripts/publish_release.py against a scratch bare repository: a first publish, the same tree again, a
    later version, the versions it refuses, a failed eval, a file found beside the build, and the token."""
    del tree
    import publish_release
    os.environ.update(IDENTITY)
    remote = scratch / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], env=ENV, capture_output=True)
    pub = scratch / "pub"
    records = build_release.build(pub, worktree=True)
    major, minor, patch = publish_release.version_of(text_of(pub, ".claude-plugin/plugin.json"))[:3]
    later, later2 = "%d.%d.%d" % (major, minor, patch + 1), "%d.%d.%d" % (major, minor, patch + 2)

    def publish(folder, recs):
        return attempt(publish_release.publish_tree, folder, recs, str(remote), "release")
    code, line = publish(pub, records)
    first, parents, modes, _ = published(remote)
    check("publish: a first publish makes the branch, one commit with no parent", code == 0 and first and not parents
          and "its first commit" in line, (code, line, parents))
    check("publish: the published tree is the build's records, the five scripts 100755, no .pyc",
          sorted(modes) == [p for p, _, _ in records] and {p for p, m in modes.items() if m == "100755"} == EXECUTABLE
          and not [p for p in modes if p.endswith(".pyc")], sorted(p for p, m in modes.items() if m == "100755"))
    code, line = publish(pub, records)
    check("publish: the same tree again is nothing to do (exit 0, no new commit)",
          code == 0 and line.startswith("Nothing to publish") and published(remote)[0] == first, (code, line))
    newer, newer_records = variant(scratch, "pub-later", pub, records, version=later)
    code, line = publish(newer, newer_records)
    second, parents, _, message = published(remote)
    check("publish: a later version adds one commit, the first as its parent, named for the version",
          code == 0 and parents == [first] and message == "Small Council v%s" % later, (code, line, parents, message))
    same, same_records = variant(scratch, "pub-same", newer, newer_records, readme=b"\nmore\n")
    code, line = publish(same, same_records)
    check("publish: the same version with other files is refused (exit 2, bump the version), nothing pushed",
          code == 2 and "bump version" in line and published(remote)[0] == second, (code, line))
    code, line = publish(pub, records)
    check("publish: an older version is refused (exit 2), nothing pushed",
          code == 2 and "bump version" in line and published(remote)[0] == second, (code, line))
    publish_built_checks(publish_release, scratch, newer, newer_records, remote, later2, second)


def publish_built_checks(publish_release, scratch, newer, newer_records, remote, later2, second):
    """The eval gates the publish, the folder must hold the build alone, and the token stays out of sight."""
    final, final_records = variant(scratch, "pub-final", newer, newer_records, version=later2)
    fails = [PY, "-c", "import sys; sys.exit(3)"]
    code, line = attempt(publish_release.publish_built, final, final_records, str(remote), "release", check=fails)
    check("publish: a tree the release eval fails is never published (exit 2), nothing pushed",
          code == 2 and "eval failed" in line and published(remote)[0] == second, (code, line))
    os.environ["PUBLISH_TOKEN"] = "planted-token-0123456789"  # noqa: S105  (a planted value, never a secret)
    try:
        blind = [PY, "-c", "import os, sys; sys.exit(9 if 'PUBLISH_TOKEN' in os.environ else 0)"]
        beside = final / "src" / "council" / "__pycache__" / "planted.cpython-38.pyc"
        beside.parent.mkdir(parents=True, exist_ok=True)
        beside.write_bytes(b"bytecode")
        code, line = attempt(publish_release.publish_built, final, final_records, str(remote), "release", check=blind)
        check("publish: the eval never sees the token, and a .pyc found beside the build is refused, nothing pushed",
              code == 2 and "found beside the build: src/council/__pycache__/planted" in line
              and published(remote)[0] == second, (code, line))
        beside.unlink()
        code, line = attempt(publish_release.publish_built, final, final_records, str(remote), "release", check=blind)
        env = publish_release.git_env()
        config = (remote / "config").read_text(encoding="utf-8")
        check("publish: with the token set it publishes; the token is in no line, no config and no git argument",
              code == 0 and published(remote)[1] == [second] and "planted-token" not in line + config
              and "planted-token" not in env.get("GIT_CONFIG_VALUE_0", "planted-token")
              and env.get("GIT_CONFIG_KEY_0") == "http.extraHeader", (code, line))
    finally:
        os.environ.pop("PUBLISH_TOKEN", None)


def main():
    parser = argparse.ArgumentParser(description="Prove the release tree stands alone.")
    parser.add_argument("--tree", help="check this tree, built already, instead of building one")
    opts = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="council-release-") as tmp:
        scratch = Path(tmp)
        tree = Path(opts.tree).resolve() if opts.tree else build_checks(scratch)
        if not (tree / ".claude-plugin" / "plugin.json").is_file():
            check("tree: %s holds a built release tree" % tree, False)
        else:
            before = snapshot(tree)
            for phase in (tree_checks, static_checks, planted_checks, smoke, build_rule_checks, publish_checks):
                try:        # a tree that lacks a file the checks open is one failed check, not a crash
                    phase(*(tree, scratch)[:phase.__code__.co_argcount])
                except (OSError, ValueError, KeyError, StopIteration, SyntaxError, subprocess.SubprocessError) as why:
                    check("%s: ran to the end" % phase.__name__, False, repr(why))
            after = snapshot(tree)
            changed = sorted(f for f in set(before) | set(after) if before.get(f) != after.get(f))
            check("the suite left the tree it checks as it found it (%d files, byte for byte)" % len(before),
                  not changed, "%d files differ, e.g. %s" % (len(changed), changed[:5]))
    for ok, name, detail in results:
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok or not detail else "\n      %s" % (detail,)))
    for line in notes:
        print("note: " + line)
    passed = sum(ok for ok, _, _ in results)
    print("\n%d/%d checks passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
