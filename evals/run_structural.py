#!/usr/bin/env python3
"""Structural evals for the Small Council (blocking) — framework invariants, no LLM.

scripts/quick_validate.py answers "will the plugin load?". This answers "is the design intact?":
  - the plugin layout, and the kernel's laws and stage index;
  - the ten stage doctrine files and their hand-offs;
  - every `council …` command a text mentions existing in the helper;
  - the modes' stage sections and deliverable paths, the agents' contracts, the hooks' wiring;
  - the templates' schemas, the catalog, the size budgets, bash portability, the rename, and version
    consistency.

Wording-level rule checks live in run_phrases.py and are advisory: a reworded rule shouldn't fail the
build, and a phrase being present doesn't prove behaviour. Behaviour belongs to the drills.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def read(*parts):
    path = os.path.join(ROOT, *parts)
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def flat(text):
    return " ".join(text.split())


def description(text):
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


SKILLS = ["context-core", "council-init", "council-review", "council-plan", "council-implement",
          "council-research", "council-postgame", "spec-writer", "test-architect"]
MODES = ["council-review", "council-plan", "council-implement", "council-research", "council-postgame"]
STAGES = ["convene", "prepare", "assign", "brief", "work", "collect", "judge", "challenge", "deliver", "learn"]
DOCTRINE = [f"{i:02d}-{s}.md" for i, s in enumerate(STAGES, 1)]

# 1. Layout
for path in [(".claude-plugin", "plugin.json"), (".claude-plugin", "marketplace.json"), ("bin", "council"),
             ("agents", "council-worker.md"), ("agents", "council-verifier.md"),
             ("hooks", "hooks.json"), ("hooks", "session-start.sh"), ("hooks", "seat-gate.sh")]:
    check(f"layout: {'/'.join(path)} exists", os.path.isfile(os.path.join(ROOT, *path)))
for s in SKILLS:
    check(f"layout: skills/{s}/SKILL.md exists", bool(read("skills", s, "SKILL.md")))
for d in DOCTRINE:
    check(f"layout: references/doctrine/{d} exists", bool(read("references", "doctrine", d)))
check("layout: references/war-room.md exists", bool(read("references", "war-room.md")))
check("layout: references/guardrails.md exists", bool(read("references", "guardrails.md")))
check("layout: no using-council skill (the hook replaced it)", not os.path.isdir(os.path.join(ROOT, "skills", "using-council")))
check("layout: no per-skill manifest.json", not any(os.path.isfile(os.path.join(ROOT, "skills", s, "manifest.json")) for s in SKILLS))

skill = {s: read("skills", s, "SKILL.md") for s in SKILLS}
core = skill["context-core"]
doctrine = {d: read("references", "doctrine", d) for d in DOCTRINE}
worker, verifier = read("agents", "council-worker.md"), read("agents", "council-verifier.md")
hook, gate, cli = read("hooks", "session-start.sh"), read("hooks", "seat-gate.sh"), read("bin", "council")
warroom = read("references", "war-room.md")
guardrails = read("references", "guardrails.md")

# 2. Kernel
LAWS = ["One head", "Parallel readers, one writer", "Gather once, share with everyone", "The disk is the memory",
        "Scripts do the mechanics", "Read a stage's doctrine as you enter it", "Evidence or it didn't happen",
        "Aggregate, then judge", "The user rules; the council proposes",
        "Every run is sized, budgeted, reported and closed", "The council learns this project"]
for i, law in enumerate(LAWS, 1):
    check(f"kernel: law {i} — {law}", f"{i}. **{law}" in core)
pos = [core.find(f"`{d}`") for d in DOCTRINE]
check("kernel: the stage table lists all ten doctrine files, in order", -1 not in pos and pos == sorted(pos), str(pos))
check("kernel: points at the doctrine folder", "${CLAUDE_PLUGIN_ROOT}/references/doctrine/" in core)
check("kernel: exit 4 from the gates is never a pass", "NOTHING WAS CHECKED" in core)
check("02-prepare: says what exit 4 means", "Exit 4" in doctrine["02-prepare.md"])
check("09-deliver: a mode that changed code says what the machine checked",
      "Checked by machine:" in doctrine["09-deliver.md"])
check("kernel: agent cap of 10, verifiers included", re.search(r"\b10\b[^.]*verifiers included", flat(core)) is not None)
check("kernel: approval threshold from the config", "approve without asking" in core)
check("kernel: cards and the ledger have a home", "`cards/<slug>.md`" in core and "`ledger.tsv`" in core)
check("kernel: resuming a run records this session as its driver (council run resume)",
      "council run resume" in core[core.find("## Resume"):])

# 3. Stage doctrine
for i, (d, stage) in enumerate(zip(DOCTRINE, STAGES), 1):
    t = doctrine[d]
    check(f"{d}: titled '# Stage {i} — …'", t.startswith(f"# Stage {i} — "))
    if i < len(STAGES):
        check(f"{d}: hands off to {STAGES[i]}", f"council state phase={STAGES[i]}" in t)
    check(f"{d}: ≤ 6,000 chars", len(t) <= 6000, str(len(t)))
check("01-convene: opens the run with the helper", "council run open" in doctrine["01-convene.md"])
check("02-prepare: builds the change index", "council index" in doctrine["02-prepare.md"])
check("01-convene: checks the stack fingerprint", "council fingerprint check" in doctrine["01-convene.md"])
check("01-convene: a config with no stack fingerprint is offered a refresh too", "no stack-fingerprint" in doctrine["01-convene.md"])
check("04-brief: a seat gets its card as its ref, and its doc's absolute path",
      "cards/<slug>.md" in doctrine["04-brief.md"] and "- doc:" in doctrine["04-brief.md"])
check("04-brief: memory in scope comes from council memory select", "council memory select" in doctrine["04-brief.md"])
check("10-learn: close records the ledger", "ledger" in doctrine["10-learn.md"])
check("03-assign: records every seat's state", "council seat" in doctrine["03-assign.md"])
check("03-assign: files past the change index's cap still need an owner", "past the 80-file cap" in doctrine["03-assign.md"])
check("04-brief: seat blocks carry ref / out / cap for collect", all(k in doctrine["04-brief.md"] for k in ["### <slug>", "- ref:", "- out:", "- cap:"]))
check("05-work: records each worker with its agent id", "council seat <slug> running agent=" in doctrine["05-work.md"])
check("06-collect: runs council collect", "council collect" in doctrine["06-collect.md"])
check("07-judge: writes synthesis.md in the index-line format", "synthesis.md" in doctrine["07-judge.md"] and "1 · P1 ·" in doctrine["07-judge.md"])
check("08-challenge: mechanical pre-check first", "council check" in doctrine["08-challenge.md"])
check("08-challenge: one verify-<n>.md per verifier", "verify-<n>.md" in doctrine["08-challenge.md"])
check("10-learn: closes the run", "council run close" in doctrine["10-learn.md"])
check("10-learn: a paused run comes back with council run resume", "council run resume" in doctrine["10-learn.md"])
check("kernel: requests and post-games have a home", "`asks/`" in core and "`postgames/`" in core)
check("01-convene: saves the user's request in ask.md", "ask.md" in doctrine["01-convene.md"])
check("06-collect: checks a war room's round-2 files", "debate.md" in doctrine["06-collect.md"])
check("09-deliver: files the request and knows the postgame kind",
      "council ask save" in doctrine["09-deliver.md"] and "postgame" in doctrine["09-deliver.md"])

# 4. Every `council …` command the texts mention exists in the helper
usage = cli[cli.find("usage() {"):cli.find("main() {")]
known = set(re.findall(r"^\s+council ([a-z]+)", usage, re.MULTILINE))
check("helper: usage lists its commands", {"run", "state", "seat", "index", "gate", "collect", "check", "map", "ask", "doctor"} <= known, ", ".join(sorted(known)))
for c in sorted(known):
    check(f"helper: '{c}' is dispatched in main", re.search(rf"^\s+{c}\)", cli, re.MULTILINE) is not None)
texts = {**{f"skills/{s}": skill[s] for s in SKILLS}, **{f"doctrine/{d}": doctrine[d] for d in DOCTRINE},
         "agents/worker": worker, "agents/verifier": verifier, "hooks/session-start.sh": hook,
         "references/war-room.md": warroom, "references/guardrails.md": guardrails}
flag_src = cli[cli.find("main() {"):] + cli[cli.find("cmd_changed() {"):cli.find("cmd_changed() {") + 2000]
flags = {alt.split("=")[0]                  # case patterns may list several: --run|--base=*)
         for alts in re.findall(r"^\s+((?:--[a-z][a-z-]*(?:=\*)?\|)*--[a-z][a-z-]*(?:=\*)?)\)", flag_src, re.MULTILINE)
         for alt in alts.split("|")}
bad, bad_flags = [], []
for label, t in texts.items():
    for m in re.finditer(r"`council ([a-z]+)([^`]*)`", t):
        c, rest = m.group(1), m.group(2).replace("\\", " ").split()   # the hook escapes backticks: \`…\`
        own = rest[:rest.index("--")] if "--" in rest else rest        # past `--` the words are the user's command
        bad_flags += [f"{label}: council {c} {f}" for f in re.findall(r"--[a-z][a-z-]*", " ".join(own)) if f not in flags]
        if c not in known:
            bad.append(f"{label}: council {c}")
        elif c == "run" and (not rest or rest[0] not in {"open", "close", "status", "resume"}):
            bad.append(f"{label}: council run {' '.join(rest[:1])}")
        elif c == "map" and (not rest or rest[0] != "status"):
            bad.append(f"{label}: council map {' '.join(rest[:1])}")
check("every `council …` command mentioned exists in the helper", not bad, "; ".join(bad[:8]))
check("every --option those mentions use exists in the helper", bool(flags) and not bad_flags, "; ".join(bad_flags[:8]))

# 5. Modes
for m in MODES:
    heads = re.findall(r"^## At ([A-Za-z]+)", skill[m], re.MULTILINE)
    check(f"{m}: invokes context-core", "context-core" in skill[m])
    check(f"{m}: every '## At <Stage>' names a real stage", heads and all(h.lower() in STAGES for h in heads), ", ".join(heads))
WANT = {"council-review": ["Convene", "Prepare", "Brief", "Work", "Judge", "Deliver", "Learn"],
        "council-plan": ["Convene", "Prepare", "Brief", "Work", "Collect", "Judge", "Challenge", "Deliver"],
        "council-research": ["Convene", "Prepare", "Assign", "Brief", "Work", "Judge", "Challenge", "Deliver", "Learn"],
        "council-implement": ["Convene", "Prepare", "Challenge", "Deliver"],
        "council-postgame": ["Convene", "Prepare", "Judge", "Challenge", "Deliver", "Learn"]}
for m, want in WANT.items():
    missing = [w for w in want if f"## At {w}" not in skill[m]]
    check(f"{m}: has its stage sections", not missing, ", ".join(missing))
for m in ["council-review", "council-plan", "council-research", "council-postgame"]:
    check(f"{m}: per-item format has an index line", "Index line: `<n> ·" in skill[m])
    check(f"{m}: description says propose with its size and cost", "size and cost" in description(skill[m]))
for m, path in [("council-review", "<home>/reviews/"), ("council-plan", "<home>/plans/"),
                ("council-implement", "<home>/logs/"), ("council-research", "<home>/research/"),
                ("council-postgame", "<home>/postgames/")]:
    check(f"{m}: deliverable under {path}", path in skill[m])
for s in SKILLS:
    if s != "council-init":
        check(f"{s}: no legacy <mode>-output run paths", "-output/" not in skill[s])
check("init: never offers a blanket council allowlist (gate and changed run arbitrary commands)",
      '"Bash(council *)"' not in skill["council-init"] and '"Bash(council gate:' not in skill["council-init"]
      and '"Bash(council changed' not in skill["council-init"]
      and "`Bash(council *)`" in skill["council-init"])   # named only to warn against it
review, plan, impl, research, init = (skill[k] for k in ["council-review", "council-plan", "council-implement", "council-research", "council-init"])
for label, text, needles in [
    ("review", review, ["merge-base", "council index --base", "Origin:", "Basis:", "Refuted if:", "Not a finding", "council-implement"]),
    ("plan", plan, ["specs/", "Touches", "Done when", "Constraints", "council-research", "war-room.md", "debate.md",
                    "## How the council decided", "ask.md", "council ask save"]),
    ("implement", impl, ["fix mode", "Before-evidence", "After-evidence", "clean-context diagnosis", "converge", "council gate --all",
                         "small-council:council-verifier", "Notes for later tasks", "diagnose-<n>.md", "verify-<n>b.md",
                         "council-postgame", "Start:", "## Converge", "Post-game:", "Three kinds of input",
                         "NOTHING WAS CHECKED", "## Shortcuts and concessions", "Shortcuts I took:", "Not proved:",
                         "Checked by machine:", "Works?:", "guardrails.md", "council check", "gates/baseline/",
                         "older Gates layout"]),
    ("research", research, ["scout", "Strength:"]),
    ("postgame", skill["council-postgame"], ["ask.md", "council ask save", "council run open council-postgame", "Ruled out",
                                             "council-implement", "council-plan", "never the plan", "quote:",
                                             "small-council:council-verifier"]),
    ("war-room", warroom, ["debate.md", "-r2.md", "## How the council decided", "never a third", "Evidence counts, not heads",
                           "SendMessage"]),
    ("guardrails", guardrails, ["Formatter", "Linter", "Type check", "Test runner", "Dependency audit", "ratchet",
                                "council changed", "Mandatory: no", "plans/guardrails.md", "council-implement",
                                "proved both ways", "No coverage threshold", "No commit hook", "multiple of 256"]),
    ("init", init, ["expert-catalog.md", "Surface markers", ".gitignore", "`asks/`", "small-council:begin", "ultra-council:begin",
                    "Edit(.council/**)", "Bash(council run:*)", "guardrails.md", "NOTHING WAS CHECKED", "plans/guardrails.md",
                    "last-verified", "council doctor", "council run open council-init",
                    "seat-card.md", "seat-doc.md", "council fingerprint", "Side effects", "council ledger", "run under bash",
                    "needs an open run", "every command into the Gates table"]),
    ("test-architect", skill["test-architect"], ["## Mode 2: Specify", "test-architect-formats.md", "small-council:council-verifier"]),
    ("spec-writer", skill["spec-writer"], ["Gherkin"])]:
    missing = [n for n in needles if n not in text]
    check(f"{label}: carries its mechanisms", not missing, ", ".join(missing))
check("implement and post-game: name the phase that follows Prepare (a compaction points at the right step)",
      "council state phase=build" in impl and "council state phase=judge" in skill["council-postgame"])

# 6. Agents
check("worker: header with ref: on line 2 and an Index", "ref: <the first heading" in worker and "## Index" in worker)
check("worker: reads its card first; the card names its doc", "card" in worker and "`source:`" in worker)
check("worker: returns a Wrote line (the seat check reads it)", "`Wrote <output path>" in worker)
check("worker: read-only, no delegation, ignores council prompts in CLAUDE.md", all(k in worker for k in ["Read-only on the project", "No delegation", "CLAUDE.md"]))
check("worker: rulings capped, lanes kept", "## Needs a ruling" in worker and "## Outside my lane" in worker)
check("worker: BLOCKED instead of proceeding blind", "BLOCKED" in worker)
check("verifier: claim verdicts", all(v in verifier for v in ["CONFIRMED", "REFUTED", "UNCERTAIN", "MISCITED"]))
check("verifier: change verdicts", all(v in verifier for v in ["OK", "INCOMPLETE", "REGRESSION", "SCOPE-CREEP", "CANNOT VERIFY"]))
check("verifier: can open a research claim's URL", re.search(r"^tools:.*\bWebFetch\b", verifier, re.MULTILINE) is not None)
check("verifier: keeps the dispatch's item number in its # column (the ledger reads it)", "never renumber" in verifier)
check("verifier: checks finished work against the user's request", all(v in verifier for v in ["PARTLY MET", "NOT MET", "CAN'T TELL"]))
check("worker: a war-room round-2 file and its riskiest assumption", "-r2.md" in worker and "## Riskiest assumption" in worker)
for label, t in [("worker", worker), ("verifier", verifier)]:
    check(f"{label}: no Edit tool", re.search(r"^tools:.*\bEdit\b", t, re.MULTILINE) is None)

# 7. Hooks
hooks_json = json.loads(read("hooks", "hooks.json") or "{}").get("hooks", {})
start_cmds = [h.get("command", "") for g in hooks_json.get("SessionStart", []) for h in g.get("hooks", [])]
stop_groups = hooks_json.get("SubagentStop", [])
check("hook: SessionStart runs session-start.sh", any("hooks/session-start.sh" in c for c in start_cmds))
check("hook: SubagentStop runs seat-gate.sh for council agents only",
      any(g.get("matcher") == "^small-council:council-(worker|verifier)$" and any("hooks/seat-gate.sh" in h.get("command", "") for h in g.get("hooks", []))
          for g in stop_groups))
check("hook: session-start shares the helper's resolver", '. "$ROOT/bin/council"' in hook)
check("hook: session-start always exits 0", hook.rstrip().endswith("exit 0"))
check("hook: silent outside council projects", '[ -d "$home" ] || exit 0' in hook)
check("hook: seat-gate never blocks twice", "stop_hook_active" in gate)
check("hook: seat-gate passes only a line that starts with BLOCKED", "grep -q '^BLOCKED'" in gate)
check("hook: session-start resumes only this session's run", "field session" in hook and "session_id" in hook)
check("helper: run open records Claude Code's session id", "CLAUDE_CODE_SESSION_ID" in cli)

# 8. Templates
cfg, conv, mp = read("references", "templates", "council.config.md"), read("references", "templates", "conventions.md"), read("references", "templates", "map.md")
check("template config: last-verified stamp", "last-verified:" in cfg)
check("template config: run preferences", "## Run preferences" in cfg and "approve without asking: up to squad" in cfg and "agent cap: 10" in cfg)
check("template config: roster has slugs and surface markers", "| Seat | Slug | Lens | Surface | Reference | Recast note |" in cfg)
check("template config: gates table", "| Gate | Command | Run at | Mandatory | Checked |" in cfg)
check("template conventions: AP / EC / D / Proposed / Rejected", all(s in conv for s in ["## Accepted Patterns", "## Enforced Conventions", "## Decisions", "## Proposed", "## Rejected"]))
check("template conventions: no live PROPOSED line (the hook would count it)", re.search(r"^- PROPOSED", conv, re.MULTILINE) is None)
check("template map: map-commit stamp", "map-commit:" in mp)
card_t, seatdoc_t = read("references", "templates", "seat-card.md"), read("references", "templates", "seat-doc.md")
check("template seat card: source line, principles applied here, severity here",
      all(k in card_t for k in ["source:", "## Principles, applied here", "## Severity here"]))
check("template seat doc: draft status, numbered principles with repo evidence",
      all(k in seatdoc_t for k in ["status: draft", "## Principle 1:", "### Evidence in this repo"]))
check("template config: stack fingerprint and gate side effects", "stack-fingerprint:" in cfg and "| Side effects |" in cfg)
check("template config: the words each gate cell takes, and that commands run under bash",
      all(k in cfg for k in ["Run at: grounding", "Mandatory: yes", "under bash"]))
check("template conventions: scope and anchor fields", "**Scope:**" in conv and "**Anchor:**" in conv)
for label, rel in [("fixture", ("evals", "fixtures", ".council", "council.config.md")), ("example", ("examples", "chrollo", "council.config.md"))]:
    t = read(*rel)
    check(f"{label} config: current schema (surface markers, run preferences)", "| Surface |" in t and "## Run preferences" in t)

# 9. Catalog and seat docs
catalog = read("references", "roster", "expert-catalog.md")
slugs = re.findall(r"^\| \*\*[^|]+\*\* \| ([a-z-]+) \|", catalog, re.MULTILINE)
check("catalog: fourteen canonical seats with slugs", len(slugs) == 14, ", ".join(slugs))
seat_docs = re.findall(r"^\| \*\*[^|]+\*\* \| [a-z-]+ \| [^|]+ \| `([a-z-]+\.md)` \|", catalog, re.MULTILINE)
check("catalog: every seat names its doc", len(seat_docs) == len(slugs), ", ".join(seat_docs))
NEW_LENSES = {"quality-accessibility.md", "quality-concurrency.md", "untrusted-input.md", "quality-operability.md"}
for doc in seat_docs:
    text = read("references", doc)
    check(f"catalog: {doc} exists", bool(text))
    check(f"{doc}: says how to apply it to another stack", "## Applying this seat to another stack" in text)
    if doc not in NEW_LENSES:
        check(f"{doc}: keeps its origin-stack examples in a final section", "## Origin-stack examples" in text)
    check(f"{doc}: numbers its principles 'Principle N'", re.search(r"^(#+ )?\**Principle 1\b", text, re.MULTILINE) is not None)
check("catalog: no external/unshipped seat docs", "external (" not in catalog)
check("template config: example slugs match the catalog",
      all(s in slugs for s in re.findall(r"^\| [A-Z][^|]+ \| ([a-z-]+) \|", cfg, re.MULTILINE)))

# 10. Size budgets — Claude Code re-attaches only the first ~5k tokens of each skill after compaction
for s in SKILLS:
    n = len(skill[s])
    check(f"{s}: ≤ 20,000 chars", n <= 20000, str(n))
    check(f"{s}: ≤ 500 lines", skill[s].count("\n") <= 500, str(skill[s].count("\n")))
    check(f"{s}: description ≤ 600 chars", len(description(skill[s])) <= 600, str(len(description(skill[s]))))
check("kernel: ≤ 14,000 chars (read on every run)", len(core) <= 14000, str(len(core)))
for label, t in [("worker", worker), ("verifier", verifier)]:
    check(f"{label}: ≤ 8,000 chars", len(t) <= 8000, str(len(t)))

# 11. Bash portability (macOS ships bash 3.2)
for label, t in [("bin/council", cli), ("hooks/session-start.sh", hook), ("hooks/seat-gate.sh", gate)]:
    code_only = "\n".join(l for l in t.split("\n") if not l.lstrip().startswith("#"))   # comments may name what's avoided
    hit = re.search(r"declare -A|\bmapfile\b|\breadarray\b|,,\}|\^\^\}", code_only)
    check(f"{label}: bash 3.2 portable (no declare -A, mapfile, readarray, case-conversion expansions)",
          hit is None, hit.group(0) if hit else "")
# bash 3.2 calls an empty "$@" or $* unbound under set -u, so the argument dispatch always guards them.
bare = []
for fn in ("main", "takes_flags", "no_words", "cmd_check"):
    body = re.search(r"^%s\(\) \{\n(.*?)^\}" % fn, cli, re.S | re.M)
    for i, line in enumerate((body.group(1) if body else "").split("\n"), 1):
        bit = re.sub(r"\$\{[0-9]\+[^}]*\}", "", re.sub(r"#.*$", "", line))    # ${1+"$@"} is the guarded form
        if re.search(r'"\$@"|\$\*', bit) and not re.search(r"\[ \$# -", bit):
            bare.append(f"{fn}:{i}: {line.strip()}")
if not re.search(r'^if \[ "\$\{BASH_SOURCE\[0\]\}" = "\$0" \]; then main \$\{1\+"\$@"\}; fi', cli, re.M):
    bare.append("the file's own dispatch line calls main without a guard")
check("bin/council: the argument dispatch never expands an empty \"$@\" or $* (unbound in bash 3.2 under set -u)",
      not bare, "; ".join(bare))

# 12. Rename, and no project leakage in anything that ships as behaviour
shipped = {**{f"skills/{s}": skill[s] for s in SKILLS}, **{f"doctrine/{d}": doctrine[d] for d in DOCTRINE},
           "agents/worker": worker, "agents/verifier": verifier, "hooks/session-start.sh": hook,
           "hooks/seat-gate.sh": gate, "bin/council": cli}
for d in ["references", os.path.join("references", "roster"), os.path.join("references", "templates")]:
    for f in os.listdir(os.path.join(ROOT, d)):
        if f.endswith(".md"):
            shipped[f"{d}/{f}"] = read(d, f)
for label, text in shipped.items():
    stale = re.sub(r"ultra-council:(begin|end)", "", text)
    check(f"{label}: no 'Ultra Council' branding", re.search(r"ultra[ -]?council", stale, re.IGNORECASE) is None)
    check(f"{label}: no hard-coded project leakage", "chrollo" not in text.lower())

# 13. Versions agree: plugin.json, the newest CHANGELOG release, and the helper
plugin = json.loads(read(".claude-plugin", "plugin.json") or "{}")
released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.MULTILINE)
helper_version = re.search(r'^COUNCIL_VERSION="([^"]+)"', cli, re.MULTILINE)
check("version: plugin.json matches the latest CHANGELOG release", bool(released) and plugin.get("version") == released[0], f"{plugin.get('version')} vs {released[:1]}")
check("version: the helper matches plugin.json", bool(helper_version) and helper_version.group(1) == plugin.get("version"),
      helper_version.group(1) if helper_version else "none")

# 14. The behavioural suite (claude plugin eval): found by the manifest, every case has a prompt and a
#     grader, every scaffold exists, every tool a grader counts is one the run can call (a tool the case
#     doesn't list is removed from the session, so "used it 0 times" would pass by construction), every
#     grader regex compiles, the near-misses assert no mode starts yet still check the ask was handled,
#     and every kind of case is there
GRANTABLE = {"Bash", "Write", "Edit", "WebFetch", "WebSearch"}   # granted by --allow-tools, not by the case
suite_rel = (plugin.get("experimental") or {}).get("evals", "")
suite = os.path.join(ROOT, *suite_rel.split("/")) if suite_rel else ""
check("suite: plugin.json points experimental.evals at an existing directory", bool(suite_rel) and os.path.isdir(suite), suite_rel)
cases = sorted(d for d in os.listdir(suite) if d != "results" and os.path.isdir(os.path.join(suite, d))) if os.path.isdir(suite) else []
check("suite: at least ten cases", len(cases) >= 10, ", ".join(cases))
suite_tags = set()
for c in cases:
    cdir = os.path.join(suite, c)
    prompt_t, case_t = read(suite_rel, c, "prompt.md"), read(suite_rel, c, "case.yaml")
    gdir = os.path.join(cdir, "graders")
    grader_files = sorted(f for f in os.listdir(gdir) if f.endswith(".md")) if os.path.isdir(gdir) else []
    graders = {f: read(suite_rel, c, "graders", f) for f in grader_files}
    check(f"suite/{c}: has a prompt and at least one grader", bool(prompt_t or case_t) and (bool(grader_files) or "graders:" in case_t))
    m = re.search(r"^\s*scaffold_script:\s*(\S+)", case_t, re.MULTILINE)
    if m:
        check(f"suite/{c}: its scaffold script exists", os.path.isfile(os.path.join(cdir, m.group(1))))
    m = re.search(r"^tags:\s*\[([^\]]*)\]", prompt_t + "\n" + case_t, re.MULTILINE)
    if m:
        suite_tags |= {t.strip() for t in m.group(1).split(",") if t.strip()}
    # prompt.md frontmatter overrides case.yaml
    m = (re.search(r"^\s*allowed_tools:\s*\[([^\]]*)\]", prompt_t, re.MULTILINE)
         or re.search(r"^\s*allowed_tools:\s*\[([^\]]*)\]", case_t, re.MULTILINE))
    allowed = {t.strip() for t in m.group(1).split(",") if t.strip()} if m else set()
    for f, g in graders.items():
        m = re.search(r"^tool:\s*(\w+)", g, re.MULTILINE)
        if m:
            check(f"suite/{c}/{f}: counts a tool the run can call ({m.group(1)})", m.group(1) in allowed | GRANTABLE,
                  "allowed_tools: " + ", ".join(sorted(allowed)))
        for key in ("pattern", "input_match"):
            m = re.search(rf"^{key}:\s*'((?:[^']|'')*)'\s*$", g, re.MULTILINE)
            if m:
                try:
                    re.compile(m.group(1).replace("''", "'"))
                    compiled = ""
                except re.error as e:
                    compiled = str(e)
                check(f"suite/{c}/{f}: its {key} compiles", not compiled, compiled)
    if c.startswith("near-miss"):
        body = "".join(graders.values())
        check(f"suite/{c}: asserts no council mode starts, in both arms", "max: 0" in body and "arm: both" in body)
        check(f"suite/{c}: also checks the ask was handled, so a run that never started can't pass",
              any("max: 0" not in g for g in graders.values()))
want_tags = {"triggering", "near-miss", "sizing", "dispatch", "fixture", "calibration", "resume", "adaptation",
             "postgame", "war-room"}
check("suite: covers triggering, near-misses, sizing, an end-to-end dispatch, a seeded fixture, calibration, resume, "
      "adaptation, the post-game and the war room",
      want_tags <= suite_tags, ", ".join(sorted(want_tags - suite_tags)))

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
