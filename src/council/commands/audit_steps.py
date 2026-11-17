"""The Chair's steps in a session transcript, for council run audit: the size and cost recorded before the first
dispatch, the status card at the first dispatch, the rulings as one question at Deliver, and the closing card after
the close. Each reads the run's own part of the transcript (audit.window) as tool calls (audit.tool_calls) and says
pass, warn or FAIL through say(verdict, label, words)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from council.clock import iso_moment
from council.commands.audit_calls import Call
from council.commands.audit_checks import MAX_FILE, Run, Say, clock
from council.records import seats as seat_files
from council.records.audit_file import FAIL, PASS, WARN

Entry = Tuple[Optional[datetime], str, Any]
ToolCall = Tuple[int, Optional[datetime], Dict[str, Any], List[Call], str]   # position, time, block, calls, output
AGENTS = ("Agent", "Task", "Workflow")
SIZED = re.compile(r"(?:^|\s)size=")
DELIVER = re.compile(r"(?:^|\s)phase=deliver\b")


def block_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def relayed(part: list[Entry], position: int, output: str) -> bool:
    """council status's Status: line passed on to the user in the text after it, before the next prompt."""
    status = next((line.split(":", 1)[1].strip() for line in output.splitlines() if line.startswith("Status:")), "")
    if not status:
        return False
    for _, kind, words in part[position + 1:]:
        if kind == "prompt":
            return False
        if kind == "text" and status[:40] in " ".join(words.split()):
            return True
    return False


def shows_status(part: list[Entry], call: ToolCall, found: list[Call]) -> bool:
    """A council status (not --line or --json) among found, relayed to the user after this call."""
    return any(i["sub"] == "status" and not {"--line", "--json"} & set(i["flags"]) for i in found) \
        and relayed(part, call[0], call[4])


def dispatches(calls: list[ToolCall]) -> list[int]:
    """Where agents went out after the run's open: an Agent, Task or Workflow call, or a seat recorded running or
    queued."""
    opened_at = next((n for n, t, block, found, _ in calls if any(i["sub"] == "run open" for i in found)), 0)
    return [n for n, t, block, found, _ in calls if n >= opened_at and (block.get("name") in AGENTS or any(
        i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(running|queued)\b", i["text"]) for i in found))]


def made_elsewhere(run: Run, part: list[Entry], sessions: set[str]) -> tuple[datetime | None, str]:
    """When the run's first dispatch was made, and where, when that was not in this transcript: another session
    (the agent gate's starts name theirs) or an earlier one; '' when it was here, or none was made."""
    starts = [(iso_moment(r.get("at")), r.get("session", "")) for r in seat_files.start_rows(run.folder, MAX_FILE)
              if not r.get("tool", "").startswith("before:")]
    starts += [(iso_moment(r.get("at")), "") for r in run.usage if r.get("kind") == "dispatched"]
    first_at, first_by = min([s for s in starts if s[0]], key=lambda s: (s[0], s[1] in ("", "-")), default=(None, ""))
    began = next((t for t, _, _ in part if t), None)
    if first_by not in ("", "-") and sessions and first_by not in sessions:
        return first_at, "session " + first_by
    if first_at and began and first_at < began:
        return first_at, "an earlier session"
    return first_at, ""


def size_first(run: Run, part: list[Entry], calls: list[ToolCall], sessions: set[str], say: Say) -> None:
    """The run's size and cost on record (council state size=…) before its first agent went out: the user approves a
    size and a cost before anything is dispatched (doctrine 01-convene, steps 5-9)."""
    label = "Size and cost before the first dispatch"
    first_at, elsewhere = made_elsewhere(run, part, sessions)
    if elsewhere:
        say(PASS, label, "not this transcript's to show: the run's first dispatch, at %s, was made in %s"
            % (clock(first_at), elsewhere))
        return
    sent = dispatches(calls)
    sized = [n for n, t, block, found, _ in calls
             if any(i["sub"] == "state" and SIZED.search(i["text"]) for i in found)]
    if not sent:
        say(PASS, label, "no agent was dispatched")
    elif sized and sized[0] < sent[0]:
        say(PASS, label, "recorded at %s, before the first agent went out at %s" % (clock(part[sized[0]][0]),
                                                                                 clock(part[sent[0]][0])))
    elif sized:
        say(FAIL, label, "the first agent went out at %s, before the run's size and cost were recorded at %s "
            "(council state size=…): the user approves a size and a cost before anything is dispatched"
            % (clock(part[sent[0]][0]), clock(part[sized[0]][0])))
    elif run.field("size"):
        say(WARN, label, "the first agent went out at %s with no council state size=… before it in this transcript; "
            "the state holds size: %s" % (clock(part[sent[0]][0]), run.field("size")[:80]))
    else:
        say(FAIL, label, "the first agent went out at %s and the run's size and cost were never recorded: council "
            "state size=\"<size — seats, est. ~<n> tokens>\" before the first dispatch" % clock(part[sent[0]][0]))


def first_card(run: Run, part: list[Entry], calls: list[ToolCall], sessions: set[str], say: Say) -> None:
    """The status card at the first dispatch: between the first agent sent (or recorded) and its first result.
    It is owed once per run, at the run's first dispatch (context-core, "Talking to the user"): a run carried
    on in a later session made that dispatch in an earlier one, so a transcript that didn't make it owes none."""
    label = "Status card at the first dispatch"
    first_at, elsewhere = made_elsewhere(run, part, sessions)
    if elsewhere:
        say(PASS, label, "not this transcript's to show: the run's first dispatch, at %s, was made in %s — the card "
            "is owed once per run" % (clock(first_at), elsewhere))
        return
    sent = dispatches(calls)
    if not sent:
        say(PASS, label, "no agent was dispatched, so none was due")
        return
    done = [n for n, t, block, found, _ in calls if n > sent[0]
            and any(i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(done|failed|blocked)\b",
                                                     i["text"]) for i in found)]
    end = done[0] if done else len(part)
    shown = any(sent[0] <= call[0] <= end and ("show_widget" in str(call[2].get("name", "")) or
                                               shows_status(part, call, call[3])) for call in calls)
    if shown:
        say(PASS, label, "shown after the first agent went out at %s" % clock(part[sent[0]][0]))
    else:
        say(FAIL, label, "not shown: the first agent went out at %s, and no show_widget call or relayed "
            "council status followed%s" % (clock(part[sent[0]][0]), " before its result was recorded at %s"
                                           % clock(part[end][0]) if done else ""))


def close_call(run: Run, part: list[Entry], calls: list[ToolCall]) -> tuple[int, int, str] | None:
    """This run's own close in the window: (position, which helper call of that tool call, its output). A close the
    helper refused (is_error, "Exit code …", and no "closed <this run>" line) is no close, and another run's close in
    the same window is not this one's: this run's last close that printed its line is — a pause before it is not —
    else the last one that went through."""
    mine = r"\bclosed %s\b" % re.escape(run.name)
    refused = set(b.get("tool_use_id") for _, kind, b in part if kind == "result"
                  and (b.get("is_error") or block_text(b.get("content")).startswith("Exit code ")))
    closes = [(n, k, output) for n, t, block, found,
              output in calls if block.get("id") not in refused or re.search(mine, output)
              for k, i in enumerate(found) if i["sub"] == "run close"]
    named = [c for c in closes if re.search(mine, c[2])]
    return (named[-1:] or closes[-1:] or [None])[0]


def closing_card(run: Run, part: list[Entry], calls: list[ToolCall], closed: datetime | None, say: Say) -> None:
    """The closing card: after this run's own close (close_call), to the end of that turn."""
    label = "Closing card"
    close_at = close_call(run, part, calls)
    if close_at is None:
        tried = any(i["sub"] == "run close" for c in calls for i in c[3])
        if closed or tried:
            say(WARN, label, "every council run close call in the window was refused, so the close can't be found"
                if tried else "no council run close call in the transcript's window, so it can't be checked")
        return
    n0, k0, _ = close_at
    shown = False
    for call in calls:
        n, _, block, found, _ = call
        if n < n0:
            continue
        if "show_widget" in str(block.get("name", "")) and n > n0:
            shown = True
        if shows_status(part, call, found[k0 + 1:] if n == n0 else found):
            shown = True
    if shown:
        say(PASS, label, "shown after the close at %s" % clock(part[n0][0]))
    else:
        say(FAIL, label, "not shown after the close at %s: no show_widget call, and no council status "
            "output passed on to the user" % clock(part[n0][0]))


def rulings_once(run: Run, part: list[Entry], calls: list[ToolCall], say: Say) -> None:
    """The rulings as one question (doctrine 09-deliver, step 6): at most one AskUserQuestion from the run's step into
    Deliver (council state phase=deliver, else its event's time) to its close. Its harmless items go together and
    each real hazard is a question of its own, all in that one call."""
    label = "Rulings as one question"
    delivered = [e for e in run.of_type("run.phase_changed") if e.get("value") == "deliver" and e["t"]]
    stepped = [n for n, t, block, found, _ in calls if any(i["sub"] == "state" and DELIVER.search(i["text"])
                                                          for i in found)]
    if not delivered and not stepped:
        return                                      # the run never reached Deliver: no rulings were due
    close_at = close_call(run, part, calls)
    end = close_at[0] if close_at else len(part)
    if stepped and stepped[-1] < end:
        start = stepped[-1]
    else:
        since = delivered[-1]["t"] - timedelta(seconds=1)
        start = next((n for n, (t, _, _) in enumerate(part) if t and t >= since), len(part))
    asked = [n for n, t, block, found, _ in calls if start <= n < end and "AskUserQuestion" in str(block.get("name"))]
    if len(asked) > 1:
        say(FAIL, label, "%d questions between Deliver and the close (%s): the rulings go to the user as one "
            "AskUserQuestion, the harmless items together and each hazard a question of its own inside it"
            % (len(asked), ", ".join(clock(part[n][0]) for n in asked[:4])))
    elif asked:
        say(PASS, label, "one question at %s" % clock(part[asked[0]][0]))
    else:
        say(PASS, label, "no question at Deliver: no rulings were asked")
