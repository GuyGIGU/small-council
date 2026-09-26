#!/usr/bin/env python3
"""Draft and file observed-failure memory proposals from verified run evidence.

The helper never decides that a failure matters or that the user agreed. `draft` turns one verified
run record into a proposal, `insert` files it under ## Proposed, and `move` applies the user's yes
or no. `insert` and `move` write a new copy of the memory file; bin/council checks that copy with
the same parser that serves memory, and that no other entry changed, before it replaces the original.
"""

import argparse
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402  (sibling script: the claim ledger's parser)
import repair    # noqa: E402  (sibling script: the repair trail's integrity check)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MAX_MEMORY = 1024 * 1024
FAILURE_VERDICTS = ("REFUTED", "MISCITED")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
FID = re.compile(r"(?<![A-Za-z0-9_])F-([0-9]+)(?![0-9])")
FIELD = re.compile(r"^\*\*([A-Za-z]+):\*\*[ \t]*(.*)$")


class MemoryError_(Exception):
    """The proposal cannot be drafted or filed safely."""


def one_line(text, limit=0, copied=True):
    """A field value: one line, and nothing the memory parser would read as a comment — nor, in text
    copied from a run artifact, as a field (**Scope:** …). A scope keeps its ** globs."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    text = text.replace("<!--", "<!-").replace("-->", "->")
    if copied:
        text = text.replace("**", "*").replace("`", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:·") + " …"
    return text


def rel(top, path):
    try:
        return path.resolve().relative_to(top.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def state_field(run, name):
    """A session-state value, read as bin/council's field() reads it."""
    body = evidence.read_file(run / "session-state.md", required=False) or ""
    match = re.search(r"^" + re.escape(name) + r":[ \t]*(.*)$", body, re.MULTILINE)
    return re.sub(r"[ \t]{2,}#.*$", "", match.group(1)).strip() if match else ""


def citation_paths(citation):
    """The file paths of a claim's citation ("src/a.py:12", "src/a.py:3-9, b.py:4")."""
    paths = []
    for piece in re.split(r"[,;]", citation or ""):
        piece = piece.strip().strip("`\"'")
        piece = re.sub(r"(:[0-9][0-9 -]*|#L?[0-9]+(-L?[0-9]+)?)$", "", piece).strip()
        if piece and ("/" in piece or re.search(r"\.[A-Za-z0-9]{1,8}$", piece)) and piece not in paths:
            paths.append(piece.replace("\\", "/"))
    return paths


def verifier_reason(run, ref, verdict):
    """The verdict cell of the verifier row a claim links to ("REFUTED — revoke runs first"), or ''."""
    name, _, number = ref.rpartition(":")
    body = evidence.read_file(run / name, required=False) or ""
    lines = body.splitlines()
    if not number.isdigit() or not 1 <= int(number) <= len(lines):
        return ""
    cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", lines[int(number) - 1])[1:-1]]
    return cells[2] if len(cells) > 2 and cells[2].upper().startswith(verdict) else ""


def block(title, fields):
    lines = ["### F-0: " + one_line(title, 90)]
    lines += ["**{}:** {}".format(name, value) for name, value in fields if value]
    return "\n".join(lines) + "\n"


def draft_claim(run, top, claim_id, scope, today):
    recorded = evidence.read_file(run / "claims.jsonl", required=False)
    if recorded is None:
        raise MemoryError_("no claims.jsonl in this run — run council evidence build after Challenge")
    claims, _ = evidence.synthesis(run)
    evidence.verifier_rows(run, claims)
    if recorded != evidence.render(claims):
        raise MemoryError_("claims.jsonl is stale — run council evidence build, then propose again")
    claim = next((item for item in claims if item["id"] == claim_id), None)
    if claim is None:
        raise MemoryError_("no claim {} in this run's claims.jsonl".format(claim_id))
    verdict = claim["verdict"]
    if verdict == "CONFIRMED":
        raise MemoryError_("claim {} was CONFIRMED — a real finding, not a council failure; "
                           "nothing to draft".format(claim_id))
    if verdict not in FAILURE_VERDICTS or len(claim["verification"]) != 1:
        raise MemoryError_("claim {} is {} — only a single REFUTED or MISCITED verifier row is "
                           "evidence of a council failure".format(claim_id, verdict))
    link = claim["verification"][0]
    paths = citation_paths(claim["citation"])
    if not scope and not paths:
        raise MemoryError_("claim {} cites no file to scope it by — pass --scope".format(claim_id))
    sources = [rel(top, run) + "/" + link["ref"]]
    deliverable = state_field(run, "deliverable")
    if deliverable:
        candidate = Path(deliverable) if os.path.isabs(deliverable) else top / deliverable
        if candidate.is_file():
            sources.append(rel(top, candidate))
    failure = '{} claimed "{}" at {}; a blind verifier returned {} (its evidence: {})'.format(
        one_line(", ".join(claim["provenance"]) or "an unattributed item", 80),
        one_line(claim["claim"], 200), one_line(claim["citation"], 120),
        one_line(verifier_reason(run, link["ref"], verdict) or verdict, 240), one_line(link["evidence"], 160))
    return block("{} claim: {}".format(verdict.lower(), one_line(claim["claim"], 60)), [
        ("Failure", failure),
        ("Scope", one_line(scope, 200, copied=False) if scope else ", ".join(paths)),
        ("Origin", "run {} ({})".format(run.name, one_line(state_field(run, "mode") or "unknown mode", 40))),
        ("Evidence", ", ".join(sources)),
        ("Verdict", verdict),
        ("Anchor", one_line(claim["citation"], 160) if paths else ""),
        ("Drafted", "{} by council memory propose from claim {} of run {}".format(today, claim_id, run.name)),
    ])


def draft_repair(run, top, task, scope, today):
    if state_field(run, "mode") != "council-implement":
        raise MemoryError_("repair proposals come from council-implement runs only")
    if not scope:
        raise MemoryError_("a repair proposal needs --scope: the paths, seats or mode the failure concerns")
    rows = [row for row in repair.load_ledger(run) if row.get("task") == task]
    if not rows:
        raise MemoryError_("no repair attempts recorded for task " + task)
    repair.inspect_rows(run, rows, check=True)
    failed = [row for row in rows if row.get("result") == "failed"]
    if not failed:
        raise MemoryError_("task {} has no failed gate attempt to remember".format(task))
    last = rows[-1]
    if last.get("action") == "stop":
        outcome = "the trail stopped after the third failure"
    elif last.get("action") == "resolved":
        outcome = "the same gate passed on attempt {}".format(last.get("attempt"))
    else:
        outcome = "the trail was still open when this was drafted"
    gate = one_line(failed[-1].get("gate"), 60)
    failure = ("gate {} failed on {} of {} recorded attempt(s) for build task {} (advisory category {}; "
               "baseline {}); last failure signal: {}; {}").format(
        gate, len(failed), len(rows), task, one_line(failed[-1].get("category"), 40),
        one_line(failed[-1].get("baseline"), 20), one_line(failed[-1].get("signal"), 200), outcome)
    run_rel = rel(top, run)
    return block("gate {} failed {} time(s) on task {}".format(gate, len(failed), task), [
        ("Failure", failure),
        ("Scope", one_line(scope, 200, copied=False)),
        ("Origin", "run {} (council-implement)".format(run.name)),
        ("Evidence", ", ".join([run_rel + "/" + row["proof_text"] for row in failed] + [run_rel + "/repairs.jsonl"])),
        ("Verdict", "OBSERVED"),
        ("Drafted", "{} by council memory propose from repair task {} of run {}".format(today, task, run.name)),
    ])


# ---------------------------------------------------------------------------------------------------
# The memory file: read it whole, and keep every byte of the lines this command does not touch.

def load_memory(path):
    if path.is_symlink():
        raise MemoryError_("the memory file is a symlink — edit it by hand")
    data = path.read_bytes()
    if len(data) > MAX_MEMORY:
        raise MemoryError_("the memory file is over 1 MB — consolidate it first")
    lines = [piece + "\n" for piece in data.decode("utf-8").split("\n")]
    lines[-1] = lines[-1][:-1]
    if lines[-1] == "":
        lines.pop()
    crlf = sum(line.endswith("\r\n") for line in lines)
    return lines, ("\r\n" if crlf and crlf * 2 >= len(lines) else "\n")


def visible(lines):
    """(index, text) for the lines the memory parser reads: outside HTML comments and code fences."""
    incom = fence = False
    for index, raw in enumerate(lines):
        text = raw.rstrip("\r\n")
        if index == 0:
            text = text.lstrip("\ufeff")
        if incom:
            incom = "-->" not in text
            continue
        if re.match(r"^[ \t]*<!--", text):
            incom = "-->" not in text
            continue
        if re.match(r"^[ \t]*(```|~~~)", text):
            fence = not fence
            continue
        if not fence:
            yield index, text


def entry_id(heading_text):
    """The id of a heading entry, as bin/council's memory parser reads one, or ''."""
    lower = heading_text.lower()
    bold = len(lower) - len(lower.lstrip("*_~"))
    match = re.match(r"(ap|ec|d|f)-?[0-9]+", lower[bold:])
    if not match:
        return ""
    rest = heading_text[bold + match.end():]
    dashed = "-" in match.group(0)
    if re.match(r"[A-Za-z0-9_]|-[A-Za-z0-9]", rest):
        return ""
    if not dashed and not re.match(r"([*_~]|[:.)]|[ \t]+(—|–|-|:)|[ \t]*$)", rest):
        return ""
    ident = match.group(0).upper()
    return ident if dashed else re.sub(r"([0-9]+)$", r"-\1", ident)


def headings(lines):
    """(index, level, text, entry id) for every heading the parser reads."""
    for index, text in visible(lines):
        match = HEADING.match(text)
        if match:
            level = len(match.group(1))
            yield index, level, match.group(2), (entry_id(match.group(2)) if 2 <= level <= 4 else "")


def section_kind(text):
    words = re.sub(r"[*_~`#]", "", text.lower())
    words = re.sub(r"^[^a-z0-9]+", "", words)
    name = re.split(r"[ \t]*(?:—|–|-[ \t]|\(|\[|;|:|,)", words, maxsplit=1)[0].strip()
    if name.startswith("propos"):
        return "proposed"
    if re.match(r"^(observed failures|failure history|failures)(\s|$)", name):
        return "observed"
    if name.startswith("reject"):
        return "rejected"
    return "other"


def sections(lines):
    """Level-1/2 section headings as (index, kind); a first level-1 heading is the file's title."""
    found, seen = [], False
    for index, level, text, ident in headings(lines):
        if level <= 2 and not ident and (level == 2 or seen):
            found.append((index, section_kind(text)))
        seen = True
    return found


def section_end(lines, start):
    """The index just past the section that opens at `start`: its next section heading, or EOF."""
    for index, level, _, ident in headings(lines):
        if index > start and level <= 2 and not ident:
            return index
    return len(lines)


def place(lines, at, new_lines, newline):
    """Insert new_lines at `at` with one blank line around them, never doubling blank lines."""
    before, after = lines[:at], lines[at:]
    while before and before[-1].strip() == "":
        before.pop()
    if before and not before[-1].endswith("\n"):
        before[-1] += newline
    chunk = ([newline] if before else []) + [line + newline for line in new_lines]
    while after and after[0].strip() == "":
        after.pop(0)
    if after:
        chunk.append(newline)
    return before + chunk + after


def cited(lines, key):
    pattern = re.compile(re.escape(key) + r"(?![0-9A-Za-z_./-])")
    return any(pattern.search(text.replace("\\", "/")) for _, text in visible(lines))


def first_evidence(entry_lines):
    for line in entry_lines:
        match = FIELD.match(line.strip())
        if match and match.group(1) == "Evidence":
            return match.group(2).split(",")[0].strip()
    return ""


def insert(memory, block_path, out):
    lines, newline = load_memory(memory)
    new = [line.rstrip("\r") for line in block_path.read_text(encoding="utf-8").strip("\n").split("\n")]
    head = HEADING.match(new[0]) if new else None
    if not head or entry_id(head.group(2)) != "F-0":
        raise MemoryError_("the draft does not open with its F-0 heading")
    key = first_evidence(new)
    if not key:
        raise MemoryError_("the draft names no evidence")
    if cited(lines, key):
        raise MemoryError_("memory already cites {} (an entry, a proposal or a rejected line) — "
                           "nothing drafted".format(key))
    number = 1 + max([0] + [int(m.group(1)) for _, text in visible(lines) for m in FID.finditer(text)])
    new[0] = re.sub(r"F-0\b", "F-{}".format(number), new[0], count=1)
    proposed = [index for index, kind in sections(lines) if kind == "proposed"]
    if proposed:
        lines = place(lines, section_end(lines, proposed[0]), new, newline)
    else:
        lines = place(lines, len(lines), ["## Proposed — awaiting the user's yes/no", ""] + new, newline)
    write(out, lines)
    print("F-{}".format(number))
    return 0


def find_entry(lines, wanted):
    hits = [(index, level) for index, level, _, ident in headings(lines) if ident == wanted]
    if len(hits) != 1:
        raise MemoryError_("{} must appear exactly once as a heading entry (found {}); move a "
                           "hand-written proposal by hand".format(wanted, len(hits)))
    start, level = hits[0]
    end = next((index for index, lvl, _, _ in headings(lines) if index > start and lvl <= level), len(lines))
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    return start, end


def move(memory, wanted, target, said_path, today, out):
    lines, newline = load_memory(memory)
    said = one_line(said_path.read_text(encoding="utf-8"), 300)
    if not said:
        raise MemoryError_("record the user's own words with --user-said")
    start, end = find_entry(lines, wanted)
    entry = [line.rstrip("\r\n") for line in lines[start:end]]
    rest = lines[:start] + lines[end:]
    if 0 < start < len(rest) and rest[start - 1].strip() == "" and rest[start].strip() == "":
        del rest[start]                                     # the gap it leaves is one blank line, not two
    if target == "observed":
        entry.append('**Approved:** {} — the user said: "{}"'.format(today, said))
        observed = [index for index, kind in sections(rest) if kind == "observed"]
        if observed:
            rest = place(rest, section_end(rest, observed[0]), entry, newline)
        else:
            proposed = [index for index, kind in sections(rest) if kind == "proposed"]
            head = ["## Observed Failures (F) — historical evidence, never a rule", ""]
            rest = place(rest, proposed[0] if proposed else len(rest), head + entry, newline)
    else:
        title = HEADING.match(entry[0]).group(2)
        title = re.sub(r"^[*_~]*F-[0-9]+[*_~]*[ \t]*[:.—–-]?[ \t]*", "", title)
        line = '- {} · {} · the user said: "{}" · was {}, evidence {}'.format(
            one_line(title, 90) or "observed failure", today, said, wanted, first_evidence(entry) or "none")
        rejected = [index for index, kind in sections(rest) if kind == "rejected"]
        if rejected:
            rest = place(rest, section_end(rest, rejected[0]), [line], newline)
        else:
            head = ["## Rejected — proposals the user said no to; never propose these again", ""]
            rest = place(rest, len(rest), head + [line], newline)
    write(out, rest)
    return 0


def write(out, lines):
    if out.exists() or out.is_symlink():
        raise MemoryError_("refusing to overwrite " + str(out))
    with open(out, "w", encoding="utf-8", newline="") as stream:
        stream.write("".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action")
    sub.required = True
    one = sub.add_parser("draft")
    one.add_argument("kind", choices=("claim", "repair"))
    one.add_argument("id")
    one.add_argument("--run", required=True, type=Path)
    one.add_argument("--top", required=True, type=Path)
    one.add_argument("--scope-file", type=Path, help="a file holding the scope (never an argument: Git Bash rewrites a leading /)")
    one.add_argument("--today", required=True)
    two = sub.add_parser("insert")
    two.add_argument("--memory", required=True, type=Path)
    two.add_argument("--block", required=True, type=Path)
    two.add_argument("--out", required=True, type=Path)
    three = sub.add_parser("move")
    three.add_argument("id")
    three.add_argument("--to", required=True, choices=("observed", "rejected"))
    three.add_argument("--memory", required=True, type=Path)
    three.add_argument("--said", required=True, type=Path)
    three.add_argument("--today", required=True)
    three.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "draft":
        run = args.run.absolute()
        if run.is_symlink() or not run.is_dir():
            raise MemoryError_("run must be a real directory")
        scope = args.scope_file.read_text(encoding="utf-8").strip() if args.scope_file else ""
        if args.kind == "claim":
            text = draft_claim(run, args.top.absolute(), args.id, scope, args.today)
        elif not repair.TASK.fullmatch(args.id):
            raise MemoryError_("task must be a short safe id")
        else:
            text = draft_repair(run, args.top.absolute(), args.id, scope, args.today)
        sys.stdout.write(text)
        return 0
    if args.action == "insert":
        return insert(args.memory, args.block, args.out)
    if not re.fullmatch(r"F-[0-9]+", args.id):
        raise MemoryError_("accept and reject take an observed-failure id such as F-3")
    return move(args.memory, args.id, args.to, args.said, args.today, args.out)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (MemoryError_, evidence.EvidenceError, repair.RepairError, OSError, UnicodeError, ValueError) as exc:
        print("memory: " + str(exc), file=sys.stderr)
        sys.exit(2)
