# Stage 9 — Deliver

## Steps

1. **Write the deliverable** to your mode's tracked path, starting with this frontmatter so later
   runs can find it:

   ```
   ---
   title: <…>
   kind: review | plan | log | research
   areas: <the paths or globs it covers>
   date: <YYYY-MM-DD>
   status: final | partial
   run: <run folder name>
   ---
   ```

2. `council state deliverable=<path>`.
3. **In chat, your mode's summary**, in plain words: say what a seat checks before its name — "Data
   integrity (Leach)". No internal labels: no bare principle numbers, no "lanes", no "AP/EC".
4. **The cost:** "This run used ~<actual>k tokens across <n> agents (estimated ~<estimate>k)", from
   the progress line or `seats.tsv`.
5. **Then, numbered, in the chat:** the rulings needed (from synthesis.md), then the next step your
   mode offers.

## Done when

The deliverable is on disk and the summary is shown. → `council state phase=learn`
