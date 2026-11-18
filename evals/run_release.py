#!/usr/bin/env python3
"""The release tree stands alone (D45): built by scripts/build_release.py, it holds only what runs, and
what runs finds everything it needs inside it.

    python evals/run_release.py               # build this checkout's tree into a temp folder, then check it
    python evals/run_release.py --tree DIR    # check a tree built already (.github/workflows/release.yml)

- the build: it exits 0, a second build of the same checkout is byte-identical, and a non-empty folder is
  refused (exit 2, the next step named);
- the tree: its top-level entries are SHIPPED's and nothing else, it is under CEILING bytes, the files git
  marks executable are executable (POSIX only: Windows keeps no mode), plugin.json names nothing in the
  dev tree, and its marketplace.json lists the tree itself ("./");
- every path plugin.json and hooks.json name exists, and every ${CLAUDE_PLUGIN_ROOT}/<path> a shipped
  skill, agent, reference or hook names;
- every relative Markdown link between shipped files resolves inside the tree;
- no shipped Python file imports from evals/, tests/, docs/ or scripts/, and every path shipped code joins
  to the plugin's own folder is in the tree (bash and TypeScript: $ROOT/…, ${root}/…, a relative import;
  Python: a constant under a shipped folder, and no dev-tree name joined to the plugin's folder);
- the checks above are live: a copy of the tree with references/ taken off, and one with a planted
  dev-tree read, each fail them;
- a smoke run with the tree's own bin/council in a scratch git repo (help, init scaffold --quick, run open
  council-review, doctor, run close), and each hook started as hooks.json starts it with CLAUDE_PLUGIN_ROOT
  set to the tree: exit 0, the SessionStart orientation printed, and a seat-gate and a bash-gate refusal
  that only a working hook gives.
Mentions of a dev-tree path in shipped text (a docstring, a comment, a doc for a person) are no read;
they are listed as notes, and fail nothing.

Python 3.8+, standard library only; bash and git for the smoke run.
"""
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
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_release  # noqa: E402  (the one list of what ships)

PY = sys.executable
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
CEILING = 2_600_000                 # bytes: 2,088,506 measured at 1.1.0 (2026-11-18), plus a quarter
DEV = ("evals", "tests", "docs", "scripts", "examples")
SHIPPED_DIRS = ("agents", "bin", "hooks", "references", "skills", "src", "types")
ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
           GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
for name in ("CLAUDE_CODE_SESSION_ID", "COUNCIL_ALLOW_NO_HOOKS", "COUNCIL_RUN", "COUNCIL_PLUGIN_ROOT", "COUNCIL_BASE"):
    ENV.pop(name, None)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
results, notes = [], []


def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))


def files_of(tree):
    return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())


def text_of(tree, rel):
    return (tree / rel).read_text(encoding="utf-8", errors="replace")


# ---- what the tree holds -------------------------------------------------------------------------------

def build(dest):
    p = subprocess.run([PY, str(ROOT / "scripts" / "build_release.py"), str(dest)], capture_output=True,
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
    check("tree: its top-level entries are SHIPPED's, nothing else", tops == build_release.top_entries(),
          "extra: %s; missing: %s" % (sorted(set(tops) - set(build_release.top_entries())),
                                      sorted(set(build_release.top_entries()) - set(tops))))
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
    return re.split(r"[\\/]", value, maxsplit=1)[0]


def python_problems(tree, rel):
    """A shipped Python file's dev-tree imports, its dev-tree names joined to the plugin's folder, and its
    constants under a shipped folder that match no file in the tree."""
    module, problems = ast.parse(text_of(tree, rel)), []
    for node in ast.walk(module):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
        problems += ["%s:%d imports %s" % (rel, node.lineno, n) for n in names if first_part(n.replace(".", "/")) in DEV]
    skip, bound = docstrings(module), roots(module)
    consts = {t.id: n.value.value for n in module.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
              and isinstance(n.value.value, str) for t in n.targets if isinstance(t, ast.Name)}
    for node in ast.walk(module):
        if isinstance(node, (ast.BinOp, ast.Call, ast.JoinedStr)) and touches_root(node, bound):
            words = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            words += [consts[n.id] for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in consts]
            problems += ["%s:%d joins %r to the plugin's folder" % (rel, node.lineno, w)
                         for w in words if first_part(w.lstrip("/")) in DEV]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip \
                and first_part(node.value) in SHIPPED_DIRS and "/" in node.value:
            pattern = re.sub(r"%[0-9]*[sd]|\{[^}]*\}", "*", node.value).rstrip("/") or "."
            if not list(tree.glob(pattern)):
                problems.append("%s:%d names %s, not in the tree" % (rel, node.lineno, node.value))
    return problems


def script_problems(tree, rel):
    """A shipped bash or TypeScript file's paths on the plugin's folder, and relative imports, not in the tree."""
    problems = []
    for number, line in enumerate(text_of(tree, rel).splitlines(), 1):
        if re.match(r"\s*(#|//)", line):
            continue
        for path in re.findall(r"(?:\$\{?[A-Z_]*ROOT\}?|\$\{root\}|pwd\))\"?/([A-Za-z0-9_.\-/]+)", line):
            if not (tree / path).exists():
                problems.append("%s:%d reads %s" % (rel, number, path))
        for spec in re.findall(r"from '(\.\.?/[^']+)'", line):
            base = ((tree / rel).parent / spec).resolve()
            if not any(Path(str(base) + ext).is_file() for ext in ("", ".ts", ".tsx", ".d.ts", "/index.d.ts", "/index.ts")):
                problems.append("%s:%d imports %s" % (rel, number, spec))
    return problems


def code_problems(tree):
    problems = []
    for rel in files_of(tree):
        if rel.endswith(".py"):
            problems += python_problems(tree, rel)
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
    problems = code_problems(planted)
    check("planted: a dev-tree import, a docs/ path joined to plugin_root() and a hook reading $ROOT/evals all fail",
          len(problems) == 3, problems)
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
    home, repo = scratch / "home", scratch / "repo"
    home.mkdir()
    repo.mkdir()
    env = dict(ENV, HOME=str(home), XDG_CACHE_HOME=str(home / ".cache"), CLAUDE_PLUGIN_ROOT=str(tree),
               CLAUDE_PROJECT_DIR=str(repo))
    for words in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "start"]):
        subprocess.run(["git", *words], cwd=str(repo), env=env, capture_output=True)
    smoke_commands(tree, repo, env)
    smoke_hooks(tree, repo, env)


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
            for phase in (tree_checks, static_checks, planted_checks, smoke):
                try:        # a tree that lacks a file the checks open is one failed check, not a crash
                    phase(*(tree, scratch)[:phase.__code__.co_argcount])
                except (OSError, ValueError, KeyError, StopIteration, SyntaxError, subprocess.SubprocessError) as why:
                    check("%s: ran to the end" % phase.__name__, False, repr(why))
    for ok, name, detail in results:
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok or not detail else "\n      %s" % (detail,)))
    for line in notes:
        print("note: " + line)
    passed = sum(ok for ok, _, _ in results)
    print("\n%d/%d checks passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
