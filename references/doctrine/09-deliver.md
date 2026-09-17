# Stage 9 — Deliver

## Steps

1. **File the request:** `council ask save` copies ask.md to `.council/asks/` — secret-looking
   strings redacted (tell the user when it says so) — records `ask=`, and prints the path.
2. **Write the deliverable** to your mode's tracked path, starting with this frontmatter so later
   runs can find it:

   ```
   ---
   title: <…>
   kind: review | plan | log | research | postgame
   areas: <the paths or globs it covers>
   date: <YYYY-MM-DD>
   status: final | partial
   run: <run folder name>
   ---
   ```

   Under its `# Title`, point at the request: ``**Your request:** `.council/asks/<file>` — "<its first
   ~12 words>…"``, quoted from that filed copy, where secrets are already redacted. It goes in the body because `council prior` reads bodies, so later runs — and a
   post-game — find the whole chain from it.
3. `council state deliverable=<path>`.
4. **In chat, your mode's summary**, in plain words: say what a seat checks before its name — "Data
   integrity (Leach)". No internal labels: no bare principle numbers, no "lanes", no "AP/EC".
   **A mode that changed code carries one line, as written:** `Checked by machine:` followed by the
   gates' verdict line (`gates: 3 ran — 2 pass, 1 FAIL (lint, not mandatory)`) — or, when the helper
   exited 4, its own NOTHING WAS CHECKED line quoted, because it names the real cause. A run that
   proved nothing by machine says so; it never reads as a clean pass. A mode that changed nothing
   (plan, research, a review of someone else's work) leaves the line out: its gates were only for
   grounding, and an alarm on every run is an alarm nobody reads — mention the missing checks once,
   in the offer. council-implement's receipt holds this line, and adds `Shortcuts I took:` and
   `Not proved:` — where `none` and `nothing` are answers, and silence isn't.
5. **The cost:** "This run used ~<actual>k tokens across <n> agents (estimated ~<estimate>k)", from
   the progress line or `seats.tsv`.
6. **Then, numbered, in the chat:** the rulings needed (from synthesis.md), then the next step your
   mode offers.

## Done when

The deliverable is on disk and the summary is shown. → `council state phase=learn`
