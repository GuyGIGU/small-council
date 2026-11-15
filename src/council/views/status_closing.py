"""The closing card's reading of a finished run: what was asked, delivered and verified, what it cost, and what is
left for the user. Missing or stale evidence is named, never counted as zero."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from council.records import audit_file, paths, pushes
from council.records.cells import clean
from council.views import cockpit
from council.views.words import cut

VERDICT_NAMES = (("confirmed", "CONFIRMED", "confirmed"), ("refuted", "REFUTED", "refuted"),
                 ("miscited", "MISCITED", "cited in the wrong place"), ("uncertain", "UNCERTAIN", "unsure"),
                 ("conflict", "CONFLICT", "with conflicting verdicts"),
                 ("not_sent", "UNVERIFIED", "not sent to a verifier"))
CONVERGE_WORDS = (("partly", "partly met"), ("not_met", "not met"), ("blocked", "blocked"),   # a build's final check
                  ("other", "with an unclear result"))
NO_REQUEST = "No filed request recorded."


def filed_request(run_path: str | Path, filed: str) -> str:
    """Read only the filed, redacted request under this project's asks folder."""
    run = Path(run_path)
    if run.parent.name != "runs" or not filed:
        return NO_REQUEST
    root = run.parent.parent.parent
    asks = root / ".council" / "asks"
    path = Path(filed)
    if not path.is_absolute():
        path = root / path
    if paths.linked(asks) or not paths.contained(path, asks):
        return NO_REQUEST
    content = paths.text_of(path, asks, limit=65536)
    if not content:
        return NO_REQUEST
    lines = content.splitlines()
    title = cut(clean(lines[0].lstrip("# ")), 160) if lines else ""
    in_words = False
    for line in lines[1:]:
        if line.startswith("## "):
            in_words = line.lower().startswith("## in your words")
            continue
        if in_words and line.strip():
            words = cut(clean(line.strip()), 220)
            return "{} — {}".format(title, words) if title and words != title else (words or title)
    return title or "Filed request; no short description recorded."


def converge_counts(converge: dict[str, Any] | None) -> dict[str, int] | None:
    """How a build's tasks ended at its final check, or None when the build log gave no results."""
    if not converge or "rows" not in converge:
        return None
    counts = {"total": len(converge["rows"]), "met": 0, "partly": 0, "not_met": 0, "blocked": 0, "other": 0,
              "fixed_after": 0}
    for row in converge["rows"]:
        counts[row["result"]] += 1
        counts["fixed_after"] += 1 if row["fixed_after"] else 0
    return counts


def converge_text(converge: dict[str, Any] | None) -> str:
    """A build's Verified line, from its log's final check. Missing results are named, never counted as zero."""
    counts = converge_counts(converge)
    if counts is None:
        return "Final check unknown: {}.".format((converge or {}).get("missing") or "no build log recorded")
    met, total = counts["met"], counts["total"]
    said = "all {} tasks met".format(total) if met == total and total > 1 else "{} of {} {} met".format(
        met, total, "task" if total == 1 else "tasks")
    if counts["fixed_after"]:
        said += " ({} after a fix the check asked for)".format(counts["fixed_after"])
    rest = ["{} {}".format(counts[key], words) for key, words in CONVERGE_WORDS if counts[key]]
    return "Final check: " + said + ("; " + ", ".join(rest) if rest else "") + "."


def converge_open(converge: dict[str, Any] | None) -> list[str]:
    """Every task the final check left short, for "Left for you" (the card caps its list; the text shows all)."""
    words = dict(CONVERGE_WORDS)
    return ["Task {} {}: {}".format(row["task"], words[row["result"]], row["done_when"] or "see the build log")
            for row in (converge or {}).get("rows", []) if row["result"] != "met"]


def verified_of(claims: dict[str, Any]) -> tuple[str, dict[str, int] | None]:
    """The Verified line from the claim index: kept claims, and cut ones a verifier saw (an item the Chair set
    aside is no unverified finding), each verdict by its own name — a wrong place or an unsure verdict is
    still a verdict."""
    if claims["stale"]:
        return "Claim index out of date; verifier counts unknown.", None
    if not claims.get("shipped"):
        return ("No kept claims to verify." if claims["total"] else "No claim verdicts recorded."), None
    shipped = dict(claims["shipped"])
    counts = {key: shipped.pop(verdict, 0) for key, verdict, _ in VERDICT_NAMES}
    counts["other"] = sum(shipped.values())
    counts["self_checked"] = claims.get("self_checked", 0)
    verified = ", ".join("{} {}".format(counts[key], words) for key, _, words in VERDICT_NAMES
                         if counts[key] or key in ("confirmed", "refuted"))
    if counts["other"]:
        verified += ", {} with another verdict".format(counts["other"])
    if counts["self_checked"]:
        verified += " ({} checked by the Chair itself, not by an independent verifier)".format(
            "all" if counts["self_checked"] == sum(claims["shipped"].values()) else counts["self_checked"])
    return verified, counts


def closing_of(snap: dict[str, Any], run_path: Path, usage: dict[str, Any], check_text: str,
               attention: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A compact final reading, or None while the run is open."""
    run = snap["run"]
    if run.get("status", "").split(" ")[0] not in ("complete", "paused", "abandoned"):
        return None
    claims, converge = snap["claims"], None
    build = run.get("mode") == "council-implement"
    held = pushes.pushes(Path(run_path).parent.parent)[0] if build else ""
    if build and not claims.get("expected", True):
        # A build checks tasks, not claims: its final check is the log's Converge table.
        converge = cockpit.converge_of(run_path, run.get("deliverable", ""))
        verified, counts = converge_text(converge), None
    else:
        verified, counts = verified_of(claims)
    return {"request": filed_request(run_path, run.get("ask", "")),
            "deliverable": clean(run.get("deliverable") or "")[:240] or "No deliverable path recorded.",
            "verification": verified, "verdict_counts": counts, "converge": converge_counts(converge),
            "checks": check_text,
            "spend": usage["spend_text"] or usage["text"],
            "agent_runs": usage["agent_runs_text"] + (
                "" if "(limit " in usage["agent_runs_text"] else " (limit {})".format(usage["agent_cap"])),
            "chair": usage.get("chair_text"), "audit": audit_file.card_line(run_path),
            "left_for_you": [a["text"] for a in attention] + converge_open(converge)
                            + ([held[:1].upper() + held[1:] + " (`- pushes:` in the config)."] if held else [])
                            + ["Rulings and next steps: see the summary in chat."]}
