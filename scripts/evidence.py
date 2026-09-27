#!/usr/bin/env python3
"""Project a council synthesis and blind-verifier tables into an evidence ledger.

The Markdown remains authoritative. This is a deterministic, run-local index of its
claims and links, not an independent assessment of whether a claim is true.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SCHEMA = 1
STATES = {"OBSERVED", "REPRODUCED", "INFERRED", "ASSUMED", "UNVERIFIED"}
VERDICTS = {"CONFIRMED", "REFUTED", "UNCERTAIN", "MISCITED"}
ITEM = re.compile(r"^(C?[0-9]+)\s+·\s+(.+)$")
SEAT_SOURCE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)#([0-9]+)$")
MAX_INPUT = 1024 * 1024


class EvidenceError(Exception):
    """Invalid or unsafe run artifact."""


def read_file(path, required=True):
    if path.is_symlink() or path.parent.is_symlink():
        raise EvidenceError("symlink artifact is not allowed: " + str(path))
    if not path.exists():
        if required:
            raise EvidenceError("missing artifact: " + str(path))
        return None
    if not path.is_file() or path.stat().st_size > MAX_INPUT:
        raise EvidenceError("artifact is not a regular file under 1 MB: " + str(path))
    return path.read_text(encoding="utf-8-sig")


def within(parent, candidate):
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def proof_link(run, value):
    """A reproduction must point to an existing, local run artifact."""
    name = Path(value.replace("\\", "/"))
    if (name.is_absolute() or re.match(r"^[A-Za-z]:", value) or not name.parts or
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


def seat_index_ids(body):
    """Only the worker's Index, not a quoted example in its prose, proves an item exists."""
    inside = False
    ids = set()
    for line in body.splitlines():
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


def synthesis(run):
    body = read_file(run / "synthesis.md")
    claims = []
    issues = []
    section = ""
    ids = set()
    kept_seen = False
    kept_content = False
    for line_no, line in enumerate(body.splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip().lower()
            if section == "kept":
                kept_seen = True
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
        parts = [part.strip() for part in match.group(2).split(" · ")]
        if len(parts) < 4 or any(not part for part in parts[:4]):
            issues.append("synthesis.md:{}: claim needs strength, principle, citation and title".format(line_no))
            continue
        strength, principle, citation = parts[:3]
        title = []
        fields = {}
        for part in parts[3:]:
            key, sep, value = part.partition(": ")
            if sep and key.lower() in ("state", "proof", "from", "why"):
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
        claims.append({
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
        })
    if not kept_seen or not kept_content:
        issues.append("synthesis.md: ## Kept needs a claim or (none) line")
    return claims, issues


def verifier_rows(run, claims):
    issues = []
    by_id = {claim["id"]: claim for claim in claims}
    for path in sorted(run.glob("verify-*.md")):
        body = read_file(path)
        header = None
        for line_no, line in enumerate(body.splitlines(), 1):
            if not line.startswith("|"):
                continue
            cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
            if [cell.lower() for cell in cells[:4]] == ["#", "item", "verdict", "evidence"]:
                header = True
                continue
            if not header or not cells or re.match(r"^:?-+:?$", cells[0]):
                continue
            claim_id = cells[0]
            if claim_id not in by_id:
                # Build-task and post-game verification tables use other ids and verdicts.
                if re.fullmatch(r"C?[0-9]+", claim_id) and re.search(
                        r"\b(?:CONFIRMED|REFUTED|UNCERTAIN|MISCITED)\b", cells[2].upper() if len(cells) > 2 else ""):
                    issues.append("{}:{}: verifier references unknown claim {}".format(path.name, line_no, claim_id))
                continue
            if len(cells) != 4:
                issues.append("{}:{}: expected four verification columns".format(path.name, line_no))
                continue
            words = set(re.findall(r"\b(?:CONFIRMED|REFUTED|UNCERTAIN|MISCITED)\b", cells[2].upper()))
            leading = re.match(r"^(CONFIRMED|REFUTED|UNCERTAIN|MISCITED)\b", cells[2].upper())
            if len(words) != 1 or not leading:
                issues.append("{}:{}: unknown or ambiguous claim verdict".format(path.name, line_no))
                continue
            by_id[claim_id]["verification"].append({
                "ref": "{}:{}".format(path.name, line_no),
                "verdict": words.pop(),
                "evidence": cells[3],
            })
    for claim in claims:
        links = claim["verification"]
        if len(links) == 1:
            claim["verdict"] = links[0]["verdict"]
        elif len(links) > 1:
            claim["verdict"] = "CONFLICT"
            issues.append("claim {}: multiple verifier rows; resolve before delivery".format(claim["id"]))
    return issues


def assess(run, claims):
    issues = []
    for claim in claims:
        label = "claim {}".format(claim["id"])
        if not claim["state_declared"]:
            issues.append(label + ": no declared evidence state")
        if not claim["provenance"]:
            issues.append(label + ": no from: provenance")
        if not claim["citation"] or claim["citation"] == "-":
            issues.append(label + ": no evidence citation")
        if claim["disposition"] == "kept":
            if not claim["verification"]:
                issues.append(label + ": no verification link")
        if claim["disposition"] == "cut" and claim["strength"] == "P1" and not claim["verification"]:
            issues.append(label + ": cut P1 has no verification link")
        if claim["evidence_state"] == "REPRODUCED":
            if not claim["proof"]:
                issues.append(label + ": REPRODUCED needs a proof: run artifact")
            for proof in claim["proof"]:
                normalized = proof.replace("\\", "/")
                if not normalized.startswith("gates/") or not normalized.endswith(".json") or not proof_link(run, proof):
                    issues.append(label + ": proof needs a saved gate verdict inside this run: " + proof)
        for source in claim["provenance"]:
            match = SEAT_SOURCE.fullmatch(source)
            if match:
                seat_file = run / "seats" / (match.group(1) + ".md")
                body = read_file(seat_file, required=False)
                if body is None or match.group(2) not in seat_index_ids(body):
                    issues.append(label + ": source item is missing: " + source)
            elif source != "chair" and not re.fullmatch(r"gate:[A-Za-z0-9][A-Za-z0-9._-]*", source):
                issues.append(label + ": unknown provenance: " + source)
            elif source.startswith("gate:") and not proof_link(run, "gates/" + source[5:] + ".json"):
                issues.append(label + ": gate provenance has no saved verdict: " + source)
        for link in claim["verification"]:
            if not link["evidence"] or link["evidence"] == "-":
                issues.append(label + ": verifier gave no evidence at " + link["ref"])
    return issues


def render(claims):
    return "".join(json.dumps(claim, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                   for claim in claims)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "show", "check"))
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    run = args.run.absolute()
    if run.is_symlink() or not run.is_dir():
        raise EvidenceError("run must be a real directory: " + str(run))
    output = run / "claims.jsonl"
    if args.action == "show":
        body = read_file(output)
        expected, issues = synthesis(run)
        issues += verifier_rows(run, expected)
        if issues or body != render(expected):
            raise EvidenceError("claims.jsonl is stale or source artifacts are invalid — run council evidence build")
        claims = [json.loads(line) for line in body.splitlines() if line.strip()]
        for claim in claims:
            links = ",".join(item["ref"] for item in claim["verification"]) or "none"
            print("{} {} {} | {} @ {} | from {} | {} @ {}".format(
                claim["id"], claim["disposition"], claim["claim"], claim["evidence_state"],
                claim["citation"], ",".join(claim["provenance"]) or "none", claim["verdict"], links))
        print("evidence: {} claim(s) -> {}".format(len(claims), output))
        return 0
    claims, issues = synthesis(run)
    issues += verifier_rows(run, claims)
    if args.action == "build":
        if issues:
            raise EvidenceError("; ".join(issues))
        data = render(claims)
        if output.is_symlink():
            raise EvidenceError("symlink output is not allowed: " + str(output))
        fd, temporary = tempfile.mkstemp(prefix=".claims-", suffix=".tmp", dir=str(run))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(data)
            os.replace(temporary, output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print("evidence: {} claim(s) indexed -> {}".format(len(claims), output))
        return 0
    recorded = read_file(output, required=False)
    if recorded is None or recorded != render(claims):
        issues.append("claims.jsonl is missing or stale — run council evidence build")
    issues += assess(run, claims)
    for issue in issues:
        print("evidence: " + issue)
    if issues:
        print("evidence: {} issue(s) across {} claim(s)".format(len(issues), len(claims)))
        return 1
    print("evidence: {} claim(s), all required links present (truth still requires independent review)".format(len(claims)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EvidenceError, UnicodeError, OSError, ValueError) as exc:
        print("evidence: " + str(exc), file=sys.stderr)
        sys.exit(2)
