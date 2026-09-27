# ADR: a run's status as a chat widget, from records that can be trusted

## Problem

Council runs are started from chat, but a run's state could only be seen through the Chair's
messages, or through `council tui --watch` in a separate terminal typed with the helper's full path.
The records behind any view were not trustworthy either. The one real long run (September 2026)
showed:
- token counts typed in thousands (160 for 160,360);
- counts rounded, or matching no source figure;
- five Workflows of 26–49 agents logged as one agent each;
- eight agent runs with no record at all;
- a token reader that took the first number it saw.

## Constraints

- **Chat-first, read-only.** No run control from the view: no cancel, retry or approve.
- **No new service.** No daemon, no website, no polling server.
- **The TUI stays** as the fallback. Its changes are limited to compatibility and fixes.
- **Old runs stay readable.** Their figures are never totalled or guessed.
- **One interpretation** shared by every view, not business logic per interface.

## What the host allows (checked, not assumed)

- The Claude desktop app's Code tab has a `visualize` tool pair (`read_me`, `show_widget`). It renders
  an HTML fragment inline in chat, inside a sandbox. It is undocumented in the Claude Code docs.
- **Checked in this session:** four cards rendered, with inline styles, the host's CSS variables, one
  inline script, and a native `<details>`.
- **Reported (not checked here):**
  - `show_widget` is also available on claude.ai/code;
  - it is absent from the terminal and the IDE extensions;
  - a card cannot read local files, reach localhost, or refresh itself;
  - a card's life after an app restart is unclear.
- **So a card is a snapshot of the records at the moment it is drawn.** "Live" would be false.

## Decision

1. **Trustworthy records first** (`references/run-accounting.md`):
   - every dispatch and usage report goes into `usage.tsv`;
   - the seat figures are derived from it: per agent id the latest report counts, a Workflow reports
     `agents=N`, and a role name or implausible count is refused at input;
   - a basis says how far a figure goes (complete, running, partial, suspect, older, none);
   - blank means unknown, never zero;
   - corrections are evidence-backed and never edit the original row.
2. **One per-seat rule, written twice and tested as one.** The helper's `seat_rows` (bash: the close
   line, the ledger) and the scripts' `seat_usage` (Python: the widget, `tui`, history, tune) are fed
   the same helper-written runs, and the tests require the same answer.
3. **One reading of a run:** `scripts/status.py` `interpret()`, taken from the cockpit snapshot. The
   widget, the text summary and the TUI's headline all render it. It holds:
   - a state (starting, running, waiting, failing, recovering, blocked, completed, interrupted,
     stale, unknown);
   - an attention list;
   - progress without a percentage;
   - the latest check and recent activity;
   - freshness;
   - cost only on a complete basis;
   - where the evidence is.
4. **The widget is `council status --widget`:** one self-contained, ASCII-only fragment.
   - Every record value is escaped. There is no network, and one inline script, which only turns the
     snapshot's time into its age.
   - The state is given in words and an icon, never colour alone.
   - It is compact by default, with details behind a native disclosure.
   - Lists are capped with "latest N of M". A long run stays under 16 KB.
5. **When the card appears.** The Chair shows it once, right after the first dispatch, and again only
   when the user asks. It is never a card per progress line.
   - Where `show_widget` is absent, the Chair relays `council status`, which ends with the exact
     terminal-view command for PowerShell and Git Bash, quoted literally.
   - A new session can show any open run's card, because reading changes nothing.

## Alternatives rejected

- **A live card polling a local server:** a new service, and it breaks the host's sandbox.
- **An Artifact page:** a hosted website, ruled out for this iteration.
- **The Claude Code status line:** a settings change the plugin can't make, and it isn't where the
  user reads.
- **A refresh button that sends a prompt:** it adds a chat message and a model call, and could
  interleave with a busy Chair. Asking in words does the same, plainly.
- **Inferring 160 means 160,000:** a guess. Such rows stay "older", or are corrected from source
  evidence.

## Tradeoffs

- The card is always a snapshot. Its age is shown and counts up, and after an hour it says to ask
  again.
- The per-seat rule exists twice (bash and Python). A test holds them together.
- Resumed agents are assumed to report running totals, as observed. A smaller later figure is added.

## Revisit when

- The host documents a stable widget API with refresh or data binding.
- The harness exposes per-agent usage directly, so the Chair no longer relays figures.
- Enough complete runs exist for the history dashboard (deferred).
