---
type: llm
focus: last_message
weight: 2
---
PASS only if the reply says tasks 1 and 2 fall short although each Done-when is met and each gate pair
is green: task 1 because it reads a setting from the environment itself, beside `settings.get()` (the
map's "Read a config setting" row), and task 2 because a bare ValueError crosses the API against
decision D-1; and that task 3 is OK. Calling task 1 or 2 OK because its tests pass, or faulting task 3,
fails.
