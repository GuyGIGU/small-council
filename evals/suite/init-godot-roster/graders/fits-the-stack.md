---
type: llm
focus: last_message
weight: 2
---
The repo is a small Godot 4 game in GDScript: scenes (.tscn), scripts (.gd) including a JSON save system (FileAccess), combat math and GUT tests. It has no web frontend, no server, no SQL database and no LLM.

PASS if the proposed council does all three:
- does not keep web-specific seats unchanged: a web frontend or web backend seat is recast to the game with a reason, or dropped with a reason;
- covers the save file, through a data-integrity seat recast from the database default or an untrusted-input seat;
- covers the engine side: a project-local engine seat, or a seat recast onto Godot's scene tree, signals or frame loop.

FAIL if it proposes the default web roster unchanged, or leaves the save system or the engine uncovered.
