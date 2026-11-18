"""Project a council synthesis and blind-verifier tables into an evidence ledger.

The Markdown remains authoritative. This is a deterministic, run-local index of its
claims and links, not an independent assessment of whether a claim is true. `build` writes it;
`check` builds it too, then checks it, and every command that needs it builds it (D44). `table --file`
reads one verifier file the same way, for the seat check that runs when a verifier stops.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

from council.records import paths
from council.records import plan as run_plan
from council.records import state as run_state
from council.records.cells import lines_of
from council.records.home import absolute

Claim = Dict[str, Any]

SCHEMA = 1
STATES = {"OBSERVED", "REPRODUCED", "INFERRED", "ASSUMED", "UNVERIFIED"}
VERDICT_WORD = re.compile(r"\b(CONFIRMED|REFUTED|UNCERTAIN|MISCITED)\b")
# A plan's recommendation rests on several task assumptions, one verifier row each: the worst stands.
WORST_FIRST = ("REFUTED", "UNCERTAIN", "MISCITED", "CONFIRMED")
TRUE_VERDICTS = ("CONFIRMED", "MISCITED")      # the claim holds (a miscited one, somewhere else)
CLAIM_MODES = ("council-review", "council-plan", "council-research")
SELF_CHECK = "verify-self.md"                  # a Solo run's Chair, checking its own items
ITEM = re.compile(r"^(C?[0-9]+)\s+·\s+(.+)$")
SEAT_SOURCE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)#([0-9]+)$")
MARKS = re.compile(r"[*_`]")
TABLE_HEAD = "| # | Item | Verdict | Evidence |"
MAX_INPUT = 1024 * 1024


class EvidenceError(Exception):
    pass


def read_file(path: Path, required: bool = True) -> str | None:
    """A run artifact's text (BOM dropped), refusing a link, a non-regular file and one over 1 MB; None when it
    is missing and not required. Only a newline ends a line (lines_of)."""
    data = paths.artifact(path, MAX_INPUT, required)
    return None if data is None else data.decode("utf-8-sig")


def within(parent: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def proof_link(run: Path, value: str) -> bool:
    """A reproduction must point to an existing, local run artifact."""
    name = Path(value.replace("\\", "/"))
    if (absolute(value) or not name.parts or
            any(part in (".", "..") for part in name.parts)):
        return False
    target = run / name
    if not within(run, target):
        return False
    cursor = run
    for part in name.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return False
    return target.is_file()


def optional(path: Path) -> str | None:
    return read_file(path, required=False)


def run_fields(run: Path) -> dict[str, Any]:
    mode = (run_state.field(run_state.text(run, read=optional), "mode").split() or [""])[0]
    plan = run_plan.keyed(run_plan.text(run, read=optional))
    return {"mode": mode,
            "self_check": (plan.get(("verification", "run", "level")) == "self" or
                           plan.get(("run", "run", "size")) == "solo")}


def seat_index_ids(body: str) -> set[str]:
    """Only the worker's Index, not a quoted example in its prose, proves an item exists."""
    inside = False
    ids = set()
    for line in lines_of(body):
        if line.strip() == "## Index":
            inside = True
            continue
        if inside and re.match(r"^#{2,3} ", line):
            break
        if inside:
            match = ITEM.match(line)
            if match:
                ids.add(match.group(1))
    return ids


def synthesis(run: Path) -> tuple[list[Claim], list[str]]:
    body = read_file(run / "synthesis.md")
    claims = []
    issues = []
    section = ""
    ids = set()
    kept_seen = False
    kept_content = False
    for line_no, line in enumerate(lines_of(body), 1):
        if line.startswith("## "):
            # A section is Kept or Cut by its first word, as council check reads it: "## Cut (not shipped)"
            # is the Cut section. Any other heading naming kept or cut is read by no one, so it is said.
            heading = MARKS.sub("", line[3:]).strip().lower()
            first = re.match(r"[a-z]*", heading).group(0)
            section = first if first in ("kept", "cut") else heading
            if section == "kept":
                kept_seen = True
            elif section != "cut" and re.search(r"\b(kept|cut)\b", heading):
                issues.append("synthesis.md:{}: heading '{}' is not read — start it with Kept or Cut".format(
                    line_no, line[3:].strip()))
            continue
        if section not in ("kept", "cut") or not line.strip():
            continue
        if line.startswith("(none)"):
            if section == "kept":
                kept_content = True
            continue
        if section == "kept":
            kept_content = True
        match = ITEM.match(line)
        if not match:
            issues.append("synthesis.md:{}: unreadable {} item".format(line_no, section))
            continue
        claim_id = match.group(1)
        if claim_id in ids:
            issues.append("synthesis.md:{}: duplicate claim id {}".format(line_no, claim_id))
            continue
        ids.add(claim_id)
        claim = claim_of(claim_id, section, match.group(2), line_no, issues)
        if claim is not None:
            claims.append(claim)
    if not kept_seen or not kept_content:
        issues.append("synthesis.md: ## Kept needs a claim or (none) line")
    return claims, issues


def claim_of(claim_id: str, section: str, rest: str, line_no: int, issues: list[str]) -> Claim | None:
    """One Kept or Cut item line, after its id, as its claim; None (its problem said) when it has too few parts."""
    parts = [part.strip() for part in rest.split(" · ")]
    if len(parts) < 4 or any(not part for part in parts[:4]):
        issues.append("synthesis.md:{}: claim needs strength, principle, citation and title".format(line_no))
        return None
    strength, principle, citation = parts[:3]
    title: list[str] = []
    fields: dict[str, str] = {}
    for part in parts[3:]:
        key, sep, value = part.partition(": ")
        if sep and key.lower() in ("state", "proof", "from", "why", "still-cut"):
            if key.lower() in fields:
                issues.append("synthesis.md:{}: repeated {} field".format(line_no, key.lower()))
            fields[key.lower()] = value.strip()
        else:
            title.append(part)
    if not title:
        issues.append("synthesis.md:{}: claim title is empty".format(line_no))
    state = fields.get("state", "UNVERIFIED").upper()
    if state not in STATES:
        issues.append("synthesis.md:{}: unknown evidence state {}".format(line_no, state))
        state = "UNVERIFIED"
    sources = [entry.strip() for entry in fields.get("from", "").split(",") if entry.strip()]
    proofs = [entry.strip() for entry in fields.get("proof", "").split(",") if entry.strip()]
    claim: Claim = {
        "schema": SCHEMA,
        "id": claim_id,
        "disposition": section,
        "strength": strength,
        "principle": principle,
        "claim": " · ".join(title),
        "citation": citation,
        "cut_reason": fields.get("why", ""),
        "evidence_state": state,
        "state_declared": "state" in fields,
        "proof": proofs,
        "provenance": sources,
        "source": "synthesis.md:{}".format(line_no),
        "verification": [],
        "verdict": "UNVERIFIED",
    }
    # Recorded only when they apply, so an older run's index stays current.
    if section == "kept" and claim_id.startswith("C"):
        claim["restored"] = True        # a cut claim the verifier found true, moved to Kept with its id
    if "still-cut" in fields:
        claim["still_cut"] = fields["still-cut"]
    return claim


def cells_of(line: str) -> list[str] | None:
    """A Markdown table row's cells — indented or not, with or without its closing pipe. An escaped \\|
    stays text, and so does one inside `code` (when the line's backticks pair up); an unescaped one
    elsewhere splits a cell, and the reader of an Evidence cell joins it back."""
    text = line.strip()
    if not text.startswith("|"):
        return None
    ticks = text.count("`") % 2 == 0
    cells, cell, code, prev = [], "", False, ""
    for ch in text[1:]:
        if ch == "`" and ticks:
            code = not code
        if ch == "|" and prev != "\\" and not code:
            cells.append(cell)
            cell = ""
        else:
            cell += ch
        prev = ch
    cells.append(cell)
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [cell.strip().replace("\\|", "|") for cell in cells]


def plain(cell: str) -> str:
    return MARKS.sub("", cell).strip()


def claim_id_of(cell: str) -> str:
    """The # cell as the synthesis writes the id: '**2**', '#2', '2.' and '`c1`' read as 2 and C1."""
    value = plain(cell).lstrip("#").strip().rstrip(".").strip()
    return value.upper() if re.fullmatch(r"[Cc][0-9]+", value) else value


def verdict_of(cell: str) -> str | None:
    """The Verdict cell's verdict: its first word, in any case and with any mark around it. Another verdict
    later in capitals makes it ambiguous; lower-case words after it are the verifier's own prose."""
    text = plain(cell)
    lead = re.match(r"[^A-Za-z]*(CONFIRMED|REFUTED|UNCERTAIN|MISCITED)\b", text, re.IGNORECASE)
    if not lead:
        return None
    verdict = lead.group(1).upper()
    return None if set(VERDICT_WORD.findall(text[lead.end():])) - {verdict} else verdict


def verdict_rows(name: str, body: str) -> tuple[list[tuple[int, list[str]]], list[str]]:
    """The rows of each table headed '# | Item | Verdict | Evidence' (the fourth heading may go on:
    'Evidence (path:line)'), as (line number, cells). A table split by a blank line carries on. A table
    with another heading whose rows carry a claim's number and verdict is named, never skipped quietly."""
    rows, issues = [], []
    table, seen, said = None, False, False   # table: None outside a table, else whether it is a verdict table
    for line_no, line in enumerate(lines_of(body), 1):
        cells = cells_of(line)
        if cells is None:
            table = None
            continue
        names = [plain(cell).lower() for cell in cells]
        if all(re.fullmatch(r":?-+:?", cell) for cell in names if cell):
            continue                   # the separator row
        if table is None:
            said = False
            table = (len(names) >= 4 and names[0] == "#" and names[2] == "verdict" and
                     names[3].startswith("evidence"))
            if table:
                seen = True
                continue
            table = (seen and len(cells) >= 4 and verdict_of(cells[2]) is not None   # it again, after a gap —
                     and re.fullmatch(r"C?[0-9]+|-",
                                      claim_id_of(cells[0])) is not None)   # never a later table's heading
        if table:
            rows.append((line_no, cells))
        elif not said and len(cells) > 2 and re.fullmatch(r"C?[0-9]+", claim_id_of(cells[0])) and \
                VERDICT_WORD.search(" ".join(plain(cell).upper() for cell in cells[1:])):
            said = True
            issues.append("{}:{}: this table's heading isn't '{}', so its verdicts were not read".format(
                name, line_no, TABLE_HEAD))
    return rows, issues


def read_links(path: Path, body: str, by_id: dict[str, Claim]) -> list[str]:
    """Link one verifier file's rows to their claims; its problems."""
    rows, issues = verdict_rows(path.name, body)
    for line_no, cells in rows:
        where = "{}:{}".format(path.name, line_no)
        claim_id = claim_id_of(cells[0])
        if claim_id in ("", "-"):
            continue                   # a plan's assumption that comes from no recommendation
        if claim_id not in by_id:
            # Build-task and post-game tables use other ids and verdicts; a claim verdict names a claim.
            if len(cells) > 2 and VERDICT_WORD.search(plain(cells[2]).upper()):
                issues.append("{}: verifier references unknown claim {} — the # column takes the item's "
                              "number exactly as the dispatch gave it (e.g. 4 or C2)".format(where, claim_id))
            continue
        if len(cells) < 4:
            issues.append("{}: expected four verification columns: {}".format(where, TABLE_HEAD))
            continue
        verdict = verdict_of(cells[2])
        if not verdict:
            issues.append("{}: unknown or ambiguous claim verdict — begin the Verdict cell with one of "
                          "CONFIRMED, REFUTED, UNCERTAIN or MISCITED, and name no other".format(where))
            continue
        evidence = " | ".join(cells[3:])
        links = by_id[claim_id]["verification"]
        if any(link["verdict"] == verdict and link["evidence"] == evidence for link in links):
            continue  # A copied row is the same evidence, not another independent verdict.
        link = {"ref": where, "verdict": verdict, "evidence": evidence}
        if path.name == SELF_CHECK:
            link["self"] = True
        links.append(link)
    return issues


def settle(claims: list[Claim], several: bool) -> list[str]:
    """Each claim's verdict from its links. An independent verifier's rows outrank the Chair's own check.
    Several rows are a conflict to resolve, except in a plan (several=True), where the worst stands."""
    issues = []
    for claim in claims:
        links = [link for link in claim["verification"] if not link.get("self")] or claim["verification"]
        if len(links) == 1:
            claim["verdict"] = links[0]["verdict"]
        elif len(links) > 1 and several:
            claim["verdict"] = next(v for v in WORST_FIRST if any(link["verdict"] == v for link in links))
        elif len(links) > 1:
            claim["verdict"] = "CONFLICT"
            issues.append("claim {}: multiple verifier rows; resolve before delivery".format(claim["id"]))
    return issues


def verifier_rows(run: Path, claims: list[Claim], several: bool | None = None) -> list[str]:
    """Link every verify-*.md row to its claim. several: may a claim have several rows (a plan)? By
    default the run's own mode says, so every reader of the index settles it the same way."""
    if several is None:
        several = run_fields(run)["mode"] == "council-plan"
    issues = []
    by_id = {claim["id"]: claim for claim in claims}
    for path in sorted(run.glob("verify-*.md")):
        issues += read_links(path, read_file(path), by_id)
    return issues + settle(claims, several)


def table_check(path: Path) -> list[str]:
    """One verifier file, read as the claim index reads it (the seat check runs this when a verifier
    stops): what the index could not read, the verifier fixes now. Rows are matched to the synthesis
    ids only in a mode that indexes claims; build and post-game tables are checked for shape."""
    run = path.parent
    fields = run_fields(run)
    rows, issues = verdict_rows(path.name, read_file(path))
    if fields["mode"] not in CLAIM_MODES or not (run / "synthesis.md").is_file():
        return issues + ["{}:{}: expected four columns: {}".format(path.name, n, TABLE_HEAD)
                         for n, cells in rows if len(cells) < 4 and claim_id_of(cells[0]) not in ("", "-")]
    if not rows and not issues:
        return ["{}: no verdict table headed '{}'".format(path.name, TABLE_HEAD)]
    claims, _ = synthesis(run)         # the synthesis's own problems are the Chair's, not the verifier's
    issues = read_links(path, read_file(path), {claim["id"]: claim for claim in claims})
    return issues + settle(claims, fields["mode"] == "council-plan")


def assess(run: Path, claims: list[Claim], self_check: bool = False) -> list[str]:
    issues = []
    for claim in claims:
        label = "claim {}".format(claim["id"])
        if not claim["state_declared"]:
            issues.append(label + ": no declared evidence state")
        if not claim["provenance"]:
            issues.append(label + ": no from: provenance")
        if not claim["citation"] or claim["citation"] == "-":
            issues.append(label + ": no evidence citation")
        own = bool(claim["verification"]) and all(link.get("self") for link in claim["verification"])
        if claim["disposition"] == "kept":
            if not claim["verification"]:
                issues.append(label + ": no verification link")
            elif own and not self_check:
                issues.append(label + ": only the Chair's own check ({}) — this run's plan calls for an "
                              "independent verifier".format(SELF_CHECK))
        if claim["disposition"] == "kept" and claim["verdict"] == "REFUTED":
            issues.append(label + ": kept, but its verifier REFUTED it — move it under ## Cut (id unchanged), or, if "
                          "the verifier was wrong, send it to a verifier again for a new verdict")
        if claim["disposition"] == "cut" and claim["strength"] == "P1" and not claim["verification"]:
            issues.append(label + ": cut P1 has no verification link")
        if claim["disposition"] == "cut" and claim["verdict"] in TRUE_VERDICTS and not claim.get("still_cut"):
            issues.append(label + ": cut, but its verifier found it {} — restore it to Kept (move the line under "
                          "## Kept, id unchanged), or say why it stays cut ('still-cut: <why>' before from:)".format(
                              claim["verdict"]))
        if claim["evidence_state"] == "REPRODUCED":
            if not claim["proof"]:
                issues.append(label + ": REPRODUCED needs a proof: run artifact")
            for proof in claim["proof"]:
                normalized = proof.replace("\\", "/")
                if not normalized.startswith("gates/") or not normalized.endswith(".json") or not proof_link(run,
                                                                                                             proof):
                    issues.append(label + ": proof needs a saved gate verdict inside this run: " + proof)
        for source in claim["provenance"]:
            match = SEAT_SOURCE.fullmatch(source)
            if match:
                seat_file = run / "seats" / (match.group(1) + ".md")
                body = read_file(seat_file, required=False)
                if body is None or match.group(2) not in seat_index_ids(body):
                    issues.append(label + ": source item is missing: " + source + (
                        " — a Solo run's own judgment is from: chair (no item number)" if match.group(1) == "chair"
                        else ""))
            elif source != "chair" and not re.fullmatch(r"gate:[A-Za-z0-9][A-Za-z0-9._-]*", source):
                issues.append(label + ": unknown provenance: " + source)
            elif source.startswith("gate:") and not proof_link(run, "gates/" + source[5:] + ".json"):
                issues.append(label + ": gate provenance has no saved verdict: " + source)
        for link in claim["verification"]:
            if not link["evidence"] or link["evidence"] == "-":
                issues.append(label + ": verifier gave no evidence at " + link["ref"])
    return issues


def render(claims: list[Claim]) -> str:
    return "".join(json.dumps(claim, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                   for claim in claims)


def indexed(run: Path, action: str) -> dict[str, Any]:
    """The run's fields, for a mode that keeps a claim index; a post-game's refusal, with the reason and the step."""
    fields = run_fields(run)
    if fields["mode"] == "council-postgame":
        raise EvidenceError("a post-game keeps no claim index: its verifier judges the work against the request (MET, "
                            "PARTLY MET, NOT MET, CAN'T TELL) in verify-*.md, and the closing card counts those rows "
                            "— nothing to " + action + "; go on with the run: council status --run " + run.name)
    return fields


def sourced(run: Path, several: bool) -> tuple[list[Claim], list[str]]:
    """The claims synthesis.md and every verify-*.md give now, and what in them could not be indexed."""
    claims, issues = synthesis(run)
    return claims, issues + verifier_rows(run, claims, several)


def write_index(run: Path, claims: list[Claim]) -> str:
    """claims.jsonl written from the claims, only when it differs: its one writer. '' once the file holds the index,
    else what couldn't be written and how to mend it; no caller's verdict waits on the write."""
    output, data = run / "claims.jsonl", render(claims).encode("utf-8")
    try:
        if output.is_file() and not output.is_symlink() and output.read_bytes() == data:
            with contextlib.suppress(OSError):   # dated now, so the audit's "older than a source" stays true
                os.utime(str(output))            # (a read-only index that already matches has nothing to mend)
        else:
            paths.atomic_write(output, data, prefix=".claims-", suffix=".tmp", refuse_link=True)
        return ""
    except (OSError, paths.RecordError) as fault:
        replacing = isinstance(fault, paths.RecordError) or getattr(fault, "filename2", None) is not None
        where = ("make {} a plain writable file (or move it aside)".format(output) if replacing
                 else "make the run folder {} writable".format(run))
        return "the claim index could not be saved ({}): {}".format(getattr(fault, "strerror", None) or fault, where)


def build(run: Path) -> tuple[list[Claim], str]:
    """The run's claim index, built now from its sources for any command that needs it (D44), and write_index's line;
    EvidenceError names each problem when the sources can't be indexed, and the index is left as it was."""
    claims, issues = sourced(run, indexed(run, "build")["mode"] == "council-plan")
    if issues:
        raise EvidenceError("; ".join(issues))
    return claims, write_index(run, claims)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "table"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--file", type=Path, help="table: the one verifier file to read")
    args = parser.parse_args(argv)
    if args.action == "table":
        if args.file is None:
            raise EvidenceError("table needs --file <verify file>")
        problems = table_check(args.file.absolute())
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    if args.run is None:
        raise EvidenceError(args.action + " needs --run <run folder>")
    run = args.run.absolute()
    if run.is_symlink() or not run.is_dir():
        raise EvidenceError("run must be a real directory: " + str(run))
    if args.action == "build":
        claims, unsaved = build(run)
        if unsaved:
            raise EvidenceError("{}, then council evidence build --run {}".format(unsaved, run.name))
        print("evidence: {} claim(s) indexed -> {}".format(len(claims), run / "claims.jsonl"))
        return 0
    fields = indexed(run, args.action)
    claims, issues = sourced(run, fields["mode"] == "council-plan")
    unsaved = "" if issues else write_index(run, claims)   # the check builds the index itself (D44)
    issues += assess(run, claims, fields["self_check"])
    if unsaved:
        print("evidence: {} — the verdict comes from the index built now; then council evidence check --run {} "
              "saves it".format(unsaved, run.name), file=sys.stderr)
    for issue in issues:
        print("evidence: " + issue)
    if issues:
        print("evidence: {} issue(s) across {} claim(s)".format(len(issues), len(claims)))
        return 1
    print("evidence: %d claim(s), all required links present (truth still requires independent review)" % len(claims))
    return 0

