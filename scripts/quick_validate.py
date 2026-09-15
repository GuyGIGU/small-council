#!/usr/bin/env python3
"""Validate the Small Council plugin — will it load, and does everything it points at exist?

Hard errors (exit 1):
  - .claude-plugin/plugin.json or marketplace.json missing, malformed, or inconsistent;
  - a skill whose SKILL.md frontmatter is missing, unparseable, misnamed, has no description, uses a
    frontmatter key Claude Code doesn't recognise, or whose description exceeds Claude Code's cap;
  - an agent whose frontmatter is missing, misnamed, or uses a key plugin agents don't support
    (hooks / mcpServers / permissionMode are ignored for plugin agents — shipping them misleads);
  - hooks/hooks.json malformed, or a hook command pointing at a script that doesn't exist;
  - any ${CLAUDE_PLUGIN_ROOT}/<path> or references/<file>.md named in a skill or agent that isn't on
    disk (a dangling reference is a blind review lane);
  - a seat reference doc whose first line isn't a single "# Title" (workers echo it as proof of reading);
  - the helper or a hook script tracked in git without the executable bit.
Warnings: a description over this repo's own budget, a version set in the marketplace entry.

Standard library only; mirrors the rules in the Claude Code plugin, skills, and sub-agents docs.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
errors, warnings = [], []

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")
RESERVED_MARKETPLACES = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace", "anthropic-plugins",
    "agent-skills", "anthropic-agent-skills", "knowledge-work-plugins", "life-sciences",
    "claude-for-legal", "claude-for-financial-services", "financial-services-plugins",
    "first-party-plugins", "claude-tag-plugins", "healthcare",
}
SKILL_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
    "background", "hooks", "paths", "shell", "metadata", "license", "compatibility",
}
PLUGIN_AGENT_KEYS = {
    "name", "description", "model", "effort", "maxTurns", "tools", "disallowedTools", "skills",
    "memory", "background", "omitClaudeMd", "isolation", "color",
}
IGNORED_FOR_PLUGIN_AGENTS = {"hooks", "mcpServers", "permissionMode"}
DESCRIPTION_CAP = 1536       # Claude Code truncates description + when_to_use here
DESCRIPTION_BUDGET = 600     # this repo's own budget: descriptions load into every session
SEAT_DOCS = [
    "security.md", "refactoring.md", "quality-frontend.md", "quality-backend.md",
    "quality-postgres.md", "quality-performance.md", "quality-llm.md", "quality-ui.md",
    "quality-ux.md", "quality-testing.md",
]


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_json(path):
    try:
        return json.loads(read(path))
    except FileNotFoundError:
        errors.append(f"{rel(path)}: missing")
    except json.JSONDecodeError as e:
        errors.append(f"{rel(path)}: invalid JSON ({e})")
    return None


def frontmatter(path):
    """Parse a simple YAML frontmatter block of `key: value` lines. Returns (dict, body) or (None, text)."""
    text = read(path).replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None, text
    fields = {}
    for line in m.group(1).split("\n"):
        if not line.strip() or line.startswith((" ", "\t", "-", "#")):
            continue  # nested YAML / list items / comments belong to the previous key
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, text[m.end():]


# 1. Plugin + marketplace manifests
plugin = load_json(os.path.join(ROOT, ".claude-plugin", "plugin.json"))
market = load_json(os.path.join(ROOT, ".claude-plugin", "marketplace.json"))
if plugin is not None:
    if not KEBAB.match(plugin.get("name", "")):
        errors.append("plugin.json: name must be kebab-case")
    if "version" in plugin and not SEMVER.match(str(plugin["version"])):
        errors.append(f"plugin.json: version '{plugin['version']}' is not semver")
    if not plugin.get("description"):
        warnings.append("plugin.json: no description (shown in the plugin manager)")
if market is not None:
    name = market.get("name", "")
    if not KEBAB.match(name):
        errors.append("marketplace.json: name must be kebab-case")
    if name in RESERVED_MARKETPLACES:
        errors.append(f"marketplace.json: '{name}' is a reserved marketplace name")
    if not (market.get("owner") or {}).get("name"):
        errors.append("marketplace.json: owner.name is required")
    entries = market.get("plugins") or []
    if not entries:
        errors.append("marketplace.json: plugins[] is empty")
    for entry in entries:
        if plugin is not None and entry.get("name") != plugin.get("name"):
            errors.append(f"marketplace.json: entry '{entry.get('name')}' != plugin.json name '{plugin.get('name')}'")
        if entry.get("source") != "./":
            errors.append("marketplace.json: this repo is its own plugin — source must be \"./\"")
        if "version" in entry:
            warnings.append("marketplace.json: version in the entry is shadowed by plugin.json — drop it")

# 2. Skills
skills_dir = os.path.join(ROOT, "skills")
skill_texts = {}
for name in sorted(os.listdir(skills_dir)):
    sdir = os.path.join(skills_dir, name)
    if not os.path.isdir(sdir):
        continue
    path = os.path.join(sdir, "SKILL.md")
    if not os.path.isfile(path):
        errors.append(f"skills/{name}: missing SKILL.md")
        continue
    fm, body = frontmatter(path)
    skill_texts[name] = read(path)
    if fm is None:
        errors.append(f"skills/{name}/SKILL.md: no frontmatter block")
        continue
    if fm.get("name") != name:
        errors.append(f"skills/{name}/SKILL.md: frontmatter name '{fm.get('name')}' != folder '{name}'")
    if not KEBAB.match(name):
        errors.append(f"skills/{name}: folder name must be kebab-case")
    desc = fm.get("description", "")
    if not desc:
        errors.append(f"skills/{name}/SKILL.md: description is required")
    total = len(desc) + len(fm.get("when_to_use", ""))
    if total > DESCRIPTION_CAP:
        errors.append(f"skills/{name}: description + when_to_use is {total} chars (> {DESCRIPTION_CAP}, truncated)")
    elif total > DESCRIPTION_BUDGET:
        warnings.append(f"skills/{name}: description is {total} chars (budget {DESCRIPTION_BUDGET})")
    for key in fm:
        if key not in SKILL_KEYS:
            errors.append(f"skills/{name}/SKILL.md: unknown frontmatter key '{key}'")
    if os.path.isfile(os.path.join(sdir, "manifest.json")):
        warnings.append(f"skills/{name}: manifest.json is not read by Claude Code — remove it")

# 3. Agents
agents_dir = os.path.join(ROOT, "agents")
agent_texts = {}
for fname in sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []:
    if not fname.endswith(".md"):
        continue
    path = os.path.join(agents_dir, fname)
    fm, _ = frontmatter(path)
    agent_texts[fname] = read(path)
    stem = fname[:-3]
    if fm is None:
        errors.append(f"agents/{fname}: no frontmatter block")
        continue
    if fm.get("name") != stem:
        errors.append(f"agents/{fname}: name '{fm.get('name')}' != file name '{stem}'")
    if ":" in fm.get("name", "") or not KEBAB.match(fm.get("name", "")):
        errors.append(f"agents/{fname}: name must be lowercase-hyphenated, no ':'")
    if not fm.get("description"):
        errors.append(f"agents/{fname}: description is required")
    for key in fm:
        if key in IGNORED_FOR_PLUGIN_AGENTS:
            errors.append(f"agents/{fname}: '{key}' is ignored for plugin agents — don't ship it")
        elif key not in PLUGIN_AGENT_KEYS:
            errors.append(f"agents/{fname}: unknown frontmatter key '{key}'")

# 4. Hooks
hooks_path = os.path.join(ROOT, "hooks", "hooks.json")
if os.path.isfile(hooks_path):
    hooks = load_json(hooks_path)
    for event, groups in ((hooks or {}).get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)", hook.get("command", "")):
                    if not os.path.isfile(os.path.join(ROOT, *ref.split("/"))):
                        errors.append(f"hooks.json ({event}): command points at missing {ref}")

# 5. Every path a skill or agent names must exist
PLACEHOLDER = re.compile(r"[<\[]")
for label, text in [*(("skills/" + k, v) for k, v in skill_texts.items()),
                    *(("agents/" + k, v) for k, v in agent_texts.items())]:
    for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", text):
        ref = ref.rstrip(".,;:)")
        if ref.endswith("/") or PLACEHOLDER.search(ref):
            continue
        if not os.path.exists(os.path.join(ROOT, *ref.split("/"))):
            errors.append(f"{label}: names ${{CLAUDE_PLUGIN_ROOT}}/{ref}, which does not exist")
    for ref in re.findall(r"(?<![\w/.])references/([A-Za-z0-9_./-]+\.md)", text):
        if not os.path.isfile(os.path.join(ROOT, "references", *ref.split("/"))):
            errors.append(f"{label}: names references/{ref}, which does not exist")

# 6. Seat docs: present, and the first line is the single H1 workers echo as proof of reading
for doc in SEAT_DOCS:
    path = os.path.join(ROOT, "references", doc)
    if not os.path.isfile(path):
        errors.append(f"references/{doc}: seat doc missing")
        continue
    first = read(path).lstrip("﻿").split("\n", 1)[0]
    if not first.startswith("# ") or first.startswith("## "):
        errors.append(f"references/{doc}: first line must be a single '# Title' (the ref: canary)")

# 7. The helper and hook scripts: bash with a shebang, LF line endings (bash chokes on CR)
EXECUTABLES = ["bin/council", "hooks/session-start.sh", "hooks/seat-gate.sh"]
for rel in EXECUTABLES:
    path = os.path.join(ROOT, *rel.split("/"))
    if not os.path.isfile(path):
        errors.append(f"{rel}: missing")
        continue
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.startswith(b"#!/usr/bin/env bash"):
        errors.append(f"{rel}: must start with '#!/usr/bin/env bash'")
    if b"\r\n" in raw:
        errors.append(f"{rel}: has CRLF line endings — keep LF (see .gitattributes)")

# 8. Stage doctrine: ten files, each titled "# Stage N — <name>"
STAGES = ["convene", "prepare", "assign", "brief", "work", "collect", "judge", "challenge", "deliver", "learn"]
for i, stage in enumerate(STAGES, 1):
    rel = f"references/doctrine/{i:02d}-{stage}.md"
    path = os.path.join(ROOT, *rel.split("/"))
    if not os.path.isfile(path):
        errors.append(f"{rel}: missing")
    elif not read(path).startswith(f"# Stage {i} — "):
        errors.append(f"{rel}: first line must be '# Stage {i} — …'")

# 9. Seat docs number their principles "Principle N" — P1–P3 are severities, and the two must never look
#    alike (items cite "Principle 3", and a finding's severity is "P2")
for doc in SEAT_DOCS:
    path = os.path.join(ROOT, "references", doc)
    if os.path.isfile(path) and not re.search(r"^(#+ )?\**Principle 1\b", read(path), re.MULTILINE):
        errors.append(f"references/{doc}: principles must be numbered 'Principle 1…N' (P1–P3 are severities)")

# 10. The helper and hook scripts are executable in git: a checkout gets the mode git recorded, and a
#     100644 bin/council can't run as a command. Untracked files and non-git copies are skipped.
try:
    staged = subprocess.run(["git", "ls-files", "-s", "--", *EXECUTABLES], cwd=ROOT, capture_output=True,
                            text=True, timeout=30).stdout
except (OSError, subprocess.SubprocessError):
    staged = ""
for line in staged.splitlines():
    mode, path = line.split(" ", 1)[0], line.split("\t", 1)[-1]
    if mode != "100755":
        errors.append(f"{path}: tracked without the executable bit — run: git add --chmod=+x {path}")

for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")
if errors:
    print(f"\nvalidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1)
print(f"\nvalidation OK: {len(warnings)} warning(s)")
