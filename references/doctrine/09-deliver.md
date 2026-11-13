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
   ~12 words>…"``, quoted from that filed copy, where secrets are already redacted. It goes in the
   body, which `council prior` reads, so later runs find the chain.
3. `council state deliverable=<path>`. Each shipped claim keeps its evidence trail
   (`references/run/evidence-model.md`, In the deliverable).
4. **In chat, your mode's summary**, in plain words (context-core, Talking to the user).
   **A mode that changed code carries one line, as written:** `Checked by machine:` followed by the
   gates' verdict line (`gates: 3 ran — 2 pass, 1 FAIL (lint, not mandatory)`) — or, when the helper
   exited 4, its own NOTHING WAS CHECKED line quoted, because it names the real cause. A run that
   proved nothing by machine says so; it never reads as a clean pass. A mode that changed nothing
   (plan, research, a review of someone else's work) leaves the line out, and mentions the missing
   checks once, in the offer. council-implement's receipt holds this line.
5. **The cost:** quote the spend line from `council status`, including its estimate and any ceiling.
   Do not work it out from seat rows; the helper keeps partial and unknown figures honest.
6. **Then the rulings, as one question** (from synthesis.md; a build's open items): ONE
   AskUserQuestion (without it, one plain question in the chat), never as a numbered list of notes:
   - the harmless items together, under one plain sentence — "nothing here can break the app or
     lose work";
   - the recommended option first, and each option saying what happens next and what it costs;
   - a real hazard (lost work or data, a broken app, a security hole) as its own question, with
     *fix now* as the default;
   - the detail (verifier notes, paths) in the log or the deliverable, not in the question.

   Then the next step your mode offers.

## Done when

The deliverable is on disk and the summary is shown. → `council state phase=learn`
The closing card follows `council run close` in Learn, when its status and cost are final.
