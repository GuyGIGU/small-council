---
type: llm
focus: last_message
weight: 2
---
The repo is a small Godot 4 game in GDScript: scenes (.tscn), scripts (.gd) including a JSON save system (FileAccess), combat math and GUT tests. It has no web frontend, no server, no SQL database and no LLM.

PASS if the proposed stack page (each part with its reason and its watch lists, D72, D73) does all three:
- names no web-specific watch list as it stands: `quality-frontend` or `quality-backend` is applied to the game with a reason, or left out with one;
- covers the save file, through `quality-postgres`'s data-integrity rules or `untrusted-input` on the save system's row;
- covers the engine side: a project's own watch list under `.council/refs/` for Godot's scene tree, signals or frame loop, or a shipped list applied to them with a reason.

FAIL if it recruits a roster of expert seats, names the web lists unchanged, or leaves the save system or the engine uncovered.
