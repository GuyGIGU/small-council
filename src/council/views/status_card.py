"""The status reading said three ways: as text (`council status`), as one notification line (`--line`) and as one
self-contained HTML fragment for a chat widget host (`--widget`: no page, no network, no local reads; every value
from the run is escaped, and the script only computes the snapshot's age from its time)."""
from __future__ import annotations

import html
import re
from typing import Any

from council.clock import utc_moment
from council.records.cells import clean
from council.views.status_names import check_name
from council.views.words import clock, listing, plural

Status = Any            # a reading, as status.interpret returns it
OLD_SNAPSHOT_MINUTES = 60  # a widget older than this tells the viewer to ask for a new one
LEFT_SHOWN = 12            # the closing card's "Left for you" items; the text lists them all (lists are capped: ADR)


def headline(state: dict[str, Any]) -> str:
    """The state said once: its label, then its summary when that adds something."""
    return "{}. {}".format(state["label"], state["summary"]) if state["summary"] else state["label"] + "."


def text(status: Status) -> str:
    run, state = status["run"], status["state"]
    if status.get("closing"):
        closing = status["closing"]
        lines = ["{} · {} · {}".format(run["project"] or "council", run["mode_label"], run["id"]),
                 "Status: " + headline(state),
                 "Asked: " + closing["request"], "Delivered: " + closing["deliverable"],
                 "Verified: " + closing["verification"], "Checks: " + closing["checks"],
                 "Spend: " + closing["spend"], "Agent runs: " + closing["agent_runs"], "Audit: " + closing["audit"]]
        if closing.get("chair"):
            lines.append("The Chair's own work: " + closing["chair"])
        lines.append("Left for you:")
        lines.extend("- " + item for item in closing["left_for_you"])
        return "\n".join(lines)
    now = utc_moment(status["snapshot_at"])
    lines = ["{} · {} · {}".format(run["project"] or "council", run["mode_label"], run["id"])]
    stage = status["run"]["stage"]
    where = run["phase_label"] + (" (stage {} of {})".format(stage["n"], stage["of"]) if stage else "")
    line = "Status: " + headline(state)
    if state["key"] not in ("completed", "interrupted"):
        line += " Stage: {}.".format(where)
    lines.append(line)
    if status["attention"]:
        for item in status["attention"]:
            lines.append("Needs you: " + item["text"] if item["severity"] >= 2 else "Note: " + item["text"])
    else:
        lines.append("Needs you: nothing right now.")
    lines.append("Seats: {} · Checks: {}".format(status["progress"]["seats"], status["progress"]["checks"]))
    if status["latest_check"]:
        c = status["latest_check"]
        lines.append("Latest check: {} {} at {}".format(c["name"], c["result"], c["clock"]))
    if status["progress"]["next"]:
        lines.append("Next: " + status["progress"]["next"][:200])
    if status.get("decisions"):
        lines.append("Decisions: " + " · ".join(d[:120] for d in status["decisions"]))
    if status["recent"]:
        lines.append("Recent: " + " · ".join("{} {}".format(i["clock"], i["text"]) for i in status["recent"][-4:]))
    fresh = status["freshness"]
    usage = status["usage"]
    lines.append("Token use: " + usage["text"] + ("" if usage["basis"] == "complete" else
                                                  " · Agent runs: " + usage["agent_runs_text"]))
    if usage.get("chair_text"):
        lines.append("The Chair's own work: " + usage["chair_text"])
    if usage["spend_text"]:
        lines.append("Spend: " + usage["spend_text"])
    lines.append("As of {} (last activity {}).".format(clock(now, now), fresh["last_activity_clock"] or "unknown"))
    return "\n".join(lines)


def notification_line(status: Status) -> str:
    """A short plain line for one owner notification, not a progress report."""
    run, state = status["run"], status["state"]
    priority = ("blocked", "waiting", "cap", "ceiling", "stop")
    top = next((item for kind in priority for item in status["attention"] if item["kind"] == kind), None)
    if state["key"] == "completed":
        message = "Run finished. See the closing card for the deliverable and next steps."
    elif top:
        message = top["text"]
    else:
        message = state["summary"] or state["label"] + "."
    line = "{} council: {}".format(run["project"] or "Project", message)
    line = re.sub(r"\s+", " ", clean(line))
    line = re.sub(r"[`*_#\[\]<>]", "", line).strip()
    return line if len(line) < 200 else line[:196].rstrip() + "..."


# --- the chat widget ------------------------------------------------------------------------------------------
STYLE = (
    "<style>"
    ".sc{font-size:14px;line-height:1.55;color:var(--text-primary)}"
    ".sc p{margin:0}"
    ".sc .card{background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem}"
    ".sc .row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}"
    ".sc .badge{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:var(--radius);"
    "font-weight:500}"
    ".sc .accent{background:var(--bg-accent);color:var(--text-accent)}"
    ".sc .warning{background:var(--bg-warning);color:var(--text-warning)}"
    ".sc .danger{background:var(--bg-danger);color:var(--text-danger)}"
    ".sc .success{background:var(--bg-success);color:var(--text-success)}"
    ".sc .neutral{background:var(--surface-1);color:var(--text-secondary)}"
    ".sc .muted{color:var(--text-secondary);font-size:13px}"
    ".sc .box{border-radius:var(--radius);padding:8px 12px;margin:12px 0 0}"
    ".sc .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0 0}"
    ".sc .tile{background:var(--surface-1);border-radius:var(--radius);padding:8px 12px}"
    ".sc ul{margin:4px 0 0;padding-left:18px}"
    ".sc .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
    "</style>")
SCRIPT = (
    "<script>(function(){var c=document.getElementById('sc-card');if(!c)return;"
    "var at=Date.parse(c.getAttribute('data-at'));if(isNaN(at))return;"
    "function f(){var m=Math.max(0,Math.round((Date.now()-at)/60000));"
    "var t=m<1?'just now':m<60?m+' min ago':m<2880?Math.floor(m/60)+' h '+(m%60)+' min ago':"
    "Math.floor(m/1440)+' days ago';"
    "var e=document.getElementById('sc-age');if(e)e.textContent=t;"
    "var o=document.getElementById('sc-old');if(o&&m>=" + str(OLD_SNAPSHOT_MINUTES) + ")o.hidden=false}"
    "f();setInterval(f,60000)})();</script>")
EYE = '<i class="ti ti-eye" aria-hidden="true"></i> '


def esc(value: str) -> str:
    return html.escape(clean(value), quote=True)


def _opening(status: Status, heading: str, muted: str, preview: bool, eye: str = "") -> list[str]:
    """The card's top, shared by the live and the closing card: the heading a screen reader hears, the preview
    note, the badge row (muted: its last words, escaped) and the summary."""
    run, state = status["run"], status["state"]
    now = utc_moment(status["snapshot_at"])
    out = [STYLE, '<div class="sc"><h2 class="sr">{}</h2>'.format(esc(heading)),
           '<div class="card" id="sc-card" data-at="{}">'.format(esc(status["snapshot_at"]))]
    if preview:
        out.append('<p class="box neutral" style="margin:0 0 12px">{}Preview built from a fixed snapshot taken {}. '
                   'It does not update.</p>'.format(eye, esc(clock(now, now))))
    out.append('<div class="row"><span class="badge {}"><i class="ti {}" aria-hidden="true"></i>{}</span>'
               '<span style="font-weight:500">{}</span><span class="muted">{}</span></div>'.format(
                   state["role"], state["icon"], esc(state["label"]), esc(run["project"] or "Council run"),
                   muted))
    if state["summary"]:
        out.append('<p style="margin-top:6px">{}</p>'.format(esc(state["summary"])))
    return out


def _closed(out: list[str], status: Status, preview: bool) -> str:
    """The card's end, shared by both cards: the age note, the details and the script, as ASCII."""
    if not preview:
        out.append('<p class="muted" id="sc-old" hidden>This card is over an hour old. Ask for the council status '
                   'to see the run now.</p>')
    out.extend((details(status), "</div></div>", SCRIPT))
    return "".join(out).encode("ascii", "xmlcharrefreplace").decode("ascii")


def closing_widget(status: Status, preview: bool = False) -> str:
    run, closing = status["run"], status["closing"]
    now = utc_moment(status["snapshot_at"])
    out = _opening(status, "{} {}: {}".format(run["project"], run["mode_label"], headline(status["state"])),
                   esc(run["mode_label"]), preview)
    for label, value in (("What you asked", closing["request"]), ("Delivered", closing["deliverable"]),
                         ("Verified", closing["verification"]), ("Machine checks", closing["checks"]),
                         ("Audit", closing["audit"])):
        out.append('<p style="margin-top:10px"><span class="muted">{}:</span> {}</p>'.format(esc(label), esc(value)))
    chair_tile = ('<div class="tile"><p class="muted">The Chair&#39;s own work</p><p>{}</p></div>'.format(
        esc(closing["chair"])) if closing.get("chair") else "")
    out.append('<div class="tiles"><div class="tile"><p class="muted">Spend</p><p>{}</p></div>'
               '<div class="tile"><p class="muted">Agent runs</p><p>{}</p></div>{}</div>'.format(
                   esc(closing["spend"]), esc(closing["agent_runs"]), chair_tile))
    left = closing["left_for_you"]
    if len(left) > LEFT_SHOWN:          # keep the card small; the last item (rulings) always shows
        left = left[:LEFT_SHOWN - 2] + ["{} more: council status lists them all.".format(len(left) - LEFT_SHOWN + 1),
                                        left[-1]]
    out.append('<div class="box neutral"><p style="font-weight:500">Left for you</p><ul>{}</ul></div>'.format(
        "".join("<li>{}</li>".format(esc(item)) for item in left)))
    out.append('<p class="muted" style="margin-top:12px">Snapshot {} (<span id="sc-age">{}</span>)</p>'.format(
        esc(clock(now, now)), "at " + esc(clock(now, now))))
    return _closed(out, status, preview)


def widget(status: Status, preview: bool = False, limit: int = 5) -> str:
    if status.get("closing"):
        return closing_widget(status, preview)
    run, state, prog = status["run"], status["state"], status["progress"]
    now = utc_moment(status["snapshot_at"])
    attention = status["attention"]
    heading = "{} {}: {} Seats: {}. {}".format(
        run["project"], run["mode_label"], headline(state), prog["seats"],
        "{} needs your attention.".format(plural(len(attention), "item")) if attention
        else "Nothing needs your attention.")
    out = _opening(status, heading, "{} · {}".format(
        esc(run["mode_label"]), esc("started " + run["started"] if run.get("started") else run["id"])), preview, EYE)
    out.append(_attention(attention, limit))
    out.append(_tiles(status))
    if status["latest_check"]:
        c = status["latest_check"]
        out.append('<p class="muted" style="margin-top:10px">Latest check: {} {} at {}</p>'.format(
            esc(c["name"]), esc(c["result"]), esc(c["clock"])))
    if prog["next"]:
        next_text = prog["next"] if len(prog["next"]) <= 220 else prog["next"][:219] + "…"
        out.append('<p style="margin-top:8px"><span class="muted">Next:</span> {}</p>'.format(esc(next_text)))
    if status.get("decisions"):
        out.append('<p class="muted" style="margin-top:10px">Decisions</p><ul>{}</ul>'.format(
            "".join("<li>{}</li>".format(esc(d[:200])) for d in status["decisions"])))
    if status["recent"]:
        out.append('<p class="muted" style="margin-top:10px">Recent{}</p><ul>{}</ul>'.format(
            "" if status["recent_source"] == "events" else " (from older records)",
            "".join("<li><span class=\"muted\">{}</span> {}</li>".format(esc(i["clock"]), esc(i["text"]))
                    for i in status["recent"][-limit:])))
    out.append('<p class="muted" style="margin-top:12px"><i class="ti ti-clock" aria-hidden="true"></i> '
               'Snapshot {} (<span id="sc-age">{}</span>) · last activity {}</p>'.format(
                   esc(clock(now, now)), "at " + esc(clock(now, now)),
                   esc(status["freshness"]["last_activity_clock"] or "unknown")))
    return _closed(out, status, preview)


def _attention(attention: list[dict[str, Any]], limit: int) -> str:
    if not attention:
        return ('<p class="muted" style="margin-top:8px"><i class="ti ti-check" aria-hidden="true"></i> '
                'Nothing needs you right now.</p>')
    top = attention[0]["severity"]
    role = "danger" if any(a["kind"] == "blocked" for a in attention) else ("warning" if top >= 1 else "neutral")
    return ('<div class="box {}"><p style="font-weight:500"><i class="ti ti-alert-triangle" aria-hidden="true"></i> '
            'Needs your attention</p><ul>{}</ul></div>'.format(
                role, "".join("<li>{}</li>".format(esc(a["text"])) for a in attention[:limit])))


def _tiles(status: Status) -> str:
    """The stage, seats and checks tiles, and the spend line under them."""
    run, state, prog, stage = status["run"], status["state"], status["progress"], status["run"]["stage"]
    tiles = [("Stage", "{}{}".format(run["phase_label"], " · {} of {}".format(stage["n"], stage["of"]) if stage else "")
              if state["key"] not in ("completed", "interrupted") else state["label"]),
             ("Seats", prog["seats"]), ("Checks", prog["checks"])]
    out = '<div class="tiles">' + "".join(
        '<div class="tile"><p class="muted">{}</p><p style="font-weight:500">{}</p></div>'.format(esc(k), esc(v))
        for k, v in tiles) + "</div>"
    if status["usage"]["spend_text"]:
        out += '<p style="margin-top:8px"><span class="muted">Spend:</span> {}</p>'.format(
            esc(status["usage"]["spend_text"]))
    return out


def details(status: Status, limit: int = 12) -> str:
    usage = status["usage"]
    rows = ['<p><span class="muted">Token use:</span> {}</p>'.format(esc(usage["text"]))]
    if usage["basis"] in ("complete", "running", "partial"):
        rows.append('<p class="muted">Token figures measure how large each agent\'s work grew, not what it '
                    'cost.</p>')
    if usage.get("chair_text"):
        rows.append('<p><span class="muted">The Chair&#39;s own work:</span> {}</p>'.format(esc(usage["chair_text"])))
    if usage["basis"] != "complete":
        rows.append('<p><span class="muted">Agent runs:</span> {}</p>'.format(esc(usage["agent_runs_text"])))
    if usage["corrected_seats"]:
        rows.append('<p class="muted">Corrected from source records: {}</p>'.format(
            esc(listing(usage["corrected_seats"], 6))))
    seats = status["seats"]
    if seats:
        shown = ["{} — {}{}".format(s["name"], s["state"], "" if not s["note"] else ": " + s["note"][:80])
                 for s in seats[-limit:]]
        more = len(seats) - len(shown)
        rows.append('<p class="muted" style="margin-top:8px">Seats{}</p><ul>{}</ul>'.format(
            " (latest {} of {})".format(len(shown), len(seats)) if more else "",
            "".join("<li>{}</li>".format(esc(line)) for line in shown)))
    checks = status["checks"]
    if checks:
        shown = checks[-limit:]
        rows.append('<p class="muted" style="margin-top:8px">Checks, latest result of each{}</p><ul>{}</ul>'.format(
            " (latest {} of {})".format(len(shown), len(checks)) if len(checks) > len(shown) else "",
            "".join("<li>{} — {}{}</li>".format(esc(check_name(c["name"])), esc(c["result"]),
                                                 esc(", recovered after failing") if c["recovered"] else "")
                    for c in shown)))
    rows.append('<p class="muted" style="margin-top:8px">Where the evidence is</p><ul>{}</ul>'.format(
        "".join("<li>{}: <code>{}</code></li>".format(esc(e["label"]), esc(e["path"])) for e in status["evidence"])))
    return '<details style="margin-top:10px"><summary class="muted">Details and evidence</summary>{}</details>'.format(
        "".join(rows))
