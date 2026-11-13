"""gates/<name>.json and gates/<name>.txt: each gate run's verdict and output, as `council gate` saves them."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from council.records import cells, paths

FOLDER = "gates"


def slug(name: str) -> str:
    """A gate's file name stem, as the helper's byte-wise `tr -c 'A-Za-z0-9._-' '_'` makes it."""
    return "".join(chr(byte) if (65 <= byte <= 90 or 97 <= byte <= 122 or 48 <= byte <= 57 or byte in (46, 95, 45))
                   else "_" for byte in name.encode("utf-8"))


def files(run: Path, stem: str, baseline: bool = False) -> tuple[Path, Path]:
    """(verdict .json, output .txt) of a gate's saved run, or of its baseline run before the build."""
    folder = Path(run) / FOLDER / "baseline" if baseline else Path(run) / FOLDER
    return folder / (stem + ".json"), folder / (stem + ".txt")


def kind(name: str) -> str:
    """'proof' for a build's before-proof or a review fix's regress-proof (both meant to fail first),
    'probe' for a dry run, 'check' for a check of the work. Every view takes this rule."""
    if name.startswith(("before-", "regress-")):
        return "proof"
    if name.startswith("probe-"):
        return "probe"
    return "check"


def void_of(data: dict[str, Any]) -> str:
    """Why a red proves nothing, as council check reads it: marked invalid, stopped at its time limit,
    or a command that never ran (exit 127). Empty when the result may count."""
    if cells.clean(data.get("invalid", "")):
        return "marked invalid ({})".format(cells.clean(data.get("invalid", "")))
    if data.get("timed_out") is True:
        return "timed out"
    if cells.integer(data.get("exit")) == 127:
        return "never ran (exit 127)"
    return ""


def failed_as_planned(gate: dict[str, Any]) -> bool:
    """A change-proof that failed did its job: it showed the problem before the fix. A before-check
    declared --proof preserve must pass, and a void red (void_of) showed nothing."""
    return (kind(gate["name"]) == "proof" and gate["exit"] not in (0, None) and gate.get("proof") != "preserve"
            and not gate.get("void"))


def results(run: Path) -> list[dict[str, Any]]:
    """Every saved verdict with an exit, in time order: name, exit, seconds, when, command, note, proof,
    void. A link, a file outside the run or one that does not parse is left out."""
    run = Path(run)
    found = []
    folder = run / FOLDER
    if not folder.is_dir() or paths.linked(folder):
        return found
    for verdict in sorted(folder.glob("*.json")):
        data = cells.parse_json(paths.text_of(verdict, run) or "{}")
        if isinstance(data, dict) and "exit" in data:
            found.append({"name": cells.clean(data.get("gate", verdict.stem)) or verdict.stem,
                          "exit": cells.integer(data.get("exit")), "seconds": cells.integer(data.get("seconds")) or 0,
                          "when": cells.clean(data.get("when", "")),
                          "command": cells.clean(data.get("command", ""))[:200],
                          "note": cells.clean(data.get("note", "")), "proof": cells.clean(data.get("proof", "change")),
                          "void": void_of(data)})
    return sorted(found, key=lambda gate: gate["when"])
