# evals/fixtures/

A tiny council-enabled project for behavioral drills D3 (bug caught), D4 (memory respected), and D9
(fix loop). Keep it small — a council review of a 40-line fixture should be fast and unambiguous.

**Run the drills on a copy, never in place:** copy this folder somewhere scratch, then
`git init && git add -A && git commit -m fixture` there, and open that folder in Claude Code with the
plugin loaded. (Inside this repo the fixture's `.council/` is not at a git root, so it is inert.)

## `sample.py` — seeded bug (D3) and an intentional choice (D4)

- **D3 target:** `average` divides by `len(values)` with no empty-input guard → a review must flag it
  (P1 or P2, numerical-correctness / structure / tests seat depending on the roster), with a "guard the
  empty case" fix and no code, CONFIRMED by the verifier.
- **D4 target:** `last_or_none` uses `items[len(items) - 1]` instead of `items[-1]` **on purpose** —
  it's Accepted Pattern AP-1 in `.council/conventions.md`. A review must NOT flag it.

## `.council/` — a ready-made council home

- `council.config.md` — a three-seat roster (Fowler, Beck, and a numerical seat recast from Willison)
  and one gate, in the current template's schema.
- `conventions.md` — the seeded memory: AP-1.

**Pass condition for D3 + D4:** `average` is in the findings; `last_or_none` is not.
