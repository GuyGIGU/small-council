"""The session transcript's part for one run, anonymised, for council run export --anon: transcript.jsonl.

Read through the audit's own reader (audit.read_transcript, audit.window), so the copy holds the run's window of the
main thread and nothing else: no agent's own lines, no lines before the run opened or after the turn that closed it.
Each line keeps its time and what the audit reads of it. A prompt is a stand-in of the same shape (a slash
command's tags kept). A Bash or PowerShell command keeps its helper calls word for word and stands in for every other
word (anon.command), checked to read as the same calls. A tool's result keeps only the helper's lines (`council: …`,
`Status: …`, `closed <run> …`) and an `Exit code` lead, paths as placeholders; the Chair's text is a stand-in, but
for a status line it passed on, which is kept as the line itself. Other tools keep their name; an agent its type.
"""
from __future__ import annotations

import re
from datetime import timezone
from pathlib import Path
from typing import Any, Collection

from council.commands import audit
from council.commands.audit_steps import AGENTS, block_text
from council.commands.audit_calls import heredoc_free, invocations
from council.commands.audit_checks import Run
from council.records import anon as anonymous

NAME = "transcript.jsonl"
KEPT = re.compile(r"^(?:council: |Status: |closed \S+ )")
SHELLS = ("Bash", "PowerShell")
TEXT_MOST = 300


def lines(source: Path, run: Run, anon: anonymous.Anon, keep: Collection[str]) -> list[dict[str, Any]]:
    """The run's window of the transcript at source, as anonymised transcript lines."""
    entries, sessions = audit.read_transcript(source)
    part = audit.window(entries, audit.spans(run))
    session = anon.session(run.field("session") or next(iter(sorted(sessions)), ""))
    statuses = [line[len("Status:"):].strip() for _, kind, block in part if kind == "result"
                for line in block_text(block.get("content")).splitlines() if line.startswith("Status:")]
    out = []
    for when, kind, payload in part:
        line = {"type": "assistant" if kind in ("use", "text") else "user", "sessionId": session,
                "isSidechain": False}
        if when is not None:
            line["timestamp"] = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                "%03dZ" % (when.microsecond // 1000)
        line["message"] = {"role": line["type"], "content": _content(kind, payload, anon, keep, statuses)}
        out.append(line)
    return out


def _content(kind: str, payload: Any, anon: anonymous.Anon, keep: Collection[str], statuses: list[str]) -> Any:
    if kind == "prompt":
        return anonymous.shape(payload)
    if kind == "text":
        relayed = [s for s in statuses if s and s[:40] in " ".join(payload.split())]
        return [{"type": "text", "text": "Status: " + relayed[0] if relayed else anonymous.shape(payload[:TEXT_MOST])}]
    if kind == "use":
        return [{"type": "tool_use", "id": payload.get("id", ""), "name": payload.get("name", ""),
                 "input": _input(payload, anon, keep)}]
    kept = [anon.paths(line) for line in block_text(payload.get("content")).splitlines() if KEPT.match(line)]
    lead = block_text(payload.get("content")).split("\n", 1)[0]
    if lead.startswith("Exit code "):
        kept.insert(0, lead)
    return [{"type": "tool_result", "tool_use_id": payload.get("tool_use_id", ""), "content": "\n".join(kept),
             "is_error": bool(payload.get("is_error"))}]


def _input(block: dict[str, Any], anon: anonymous.Anon, keep: Collection[str]) -> dict[str, Any]:
    given = block.get("input") if isinstance(block.get("input"), dict) else {}
    name = block.get("name", "")
    if name in SHELLS:
        command = heredoc_free(str(given.get("command", "")))
        found = {"command": shell(command, anon, keep)}
        if given.get("run_in_background"):
            found["run_in_background"] = True
        return found
    if name in AGENTS:
        kind = str(given.get("subagent_type", ""))
        return {"subagent_type": kind if kind.startswith("small-council:") or not kind else "agent"}
    return {}


def shell(command: str, anon: anonymous.Anon, keep: Collection[str]) -> str:
    """A command anonymised so that it still reads as the same helper calls: when the stood-in words change how it
    reads, each helper call's own words, anonymised, on a line of its own (with the tail or head that cut it)."""
    made = anon.command(command, keep)
    if _calls(made) == _calls(command):
        return made
    return "\n".join(anon.command(i["text"], keep) + (" | " + i["cut"].split()[0] if i["cut"] else "")
                     for i in invocations(command))


def _calls(command: str) -> list[tuple]:
    return [(i["form"], i["sub"], tuple(i["flags"]), bool(i["cut"])) for i in invocations(command)]

