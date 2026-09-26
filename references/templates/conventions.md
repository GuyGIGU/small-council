# Conventions — <project>
<!-- Small Council memory. Every council run reads this file first. Settled entries record the USER's
     decisions: agents may only PROPOSE (the Proposed section); the user confirms. Keep it under ~25 KB —
     past that, the council proposes a consolidation as numbered operations (merge, retire), never a
     rewrite.
     Every entry may carry **Scope:** (paths, globs or seat slugs it concerns — leave it out and every
     run reads the entry) and **Anchor:** (the paths, symbols or path:lines it is about, separated by
     commas; a path:line may list lines, as in `src/api/auth.py:42,60-71` — a path or a symbol
     survives edits; a line number can drift). Brief reads only the entries in scope
     (`council memory select`); `council memory check` flags an entry whose anchored file, line or
     symbol is gone. Give a one-line **Pattern:**, **Rule:** or **Decision:** and **Origin:** when
     accepting a new entry; selection includes those fields so a title alone need not carry the rule.
     An entry is a heading (### AP-1: title), a bullet (- **AP-1 — title** …) or a numbered item
     (1. **AP-1 — title** …); a bullet inside a heading entry belongs to that entry. Runs read entries
     only under Accepted Patterns, Enforced Conventions and Decisions (a heading that says Adopted or
     Settled counts too) — never under Proposed, Rejected, Retired or a section of another name. What
     a section is called decides that, not a word further along its heading, so "Accepted Patterns —
     never re-propose these" still holds entries the runs read. Observed Failures are selected as
     historical evidence, explicitly not as instructions. `council memory` lists every entry it
     does not serve, and every line that looks like an entry but could not be read. -->


## Accepted Patterns (AP) — intentional; never flag these
<!-- ### AP-1: <title>
     **Pattern:** <what the code does on purpose> · **Why:** <reason> · **Origin:** <deliverable or date>
     **Scope:** <src/api/**, hunt> · **Anchor:** <src/api/auth.py:42> -->

## Enforced Conventions (EC) — always / never rules
<!-- ### EC-1: <title>
     **Rule:** <always … / never …> · **Why:** <reason> · **Origin:** <dated user approval> -->

## Decisions (D) — the user's rulings; agents never author these
<!-- ### D-1: <title>
     **Decision:** <what the user decided, in their words> · **Why:** <their reason>
     **Origin:** <dated user ruling or ask path> · **Date:** <YYYY-MM-DD> -->

## Observed Failures (F) — historical evidence, never a rule
<!-- User-confirmed entries only. A failure is served only with all five fields below, a scope that
     names paths, seats or a mode (never "all", "none" or "*"), and a verdict that establishes it;
     otherwise it is listed as NOT SERVED with the reason. Keep the observation separate from any
     future rule: a **Rule:** written into an F entry is never shown with it.
     ### F-1: <brief title>
     **Failure:** <what was observed, not an assumed cause>
     **Scope:** <paths, globs, seat or mode slugs; required>
     **Origin:** <run or deliverable and date>
     **Evidence:** <paths to the gate output, verifier row or trace, e.g. .council/runs/<run>/verify-1.md:14>
     **Verdict:** <OBSERVED or REPRODUCED (seen, or seen again, in a named artifact), or the verifier's
                  CONFIRMED, REFUTED, MISCITED, REGRESSION, INCOMPLETE or SCOPE-CREEP — never
                  INFERRED, ASSUMED, UNVERIFIED or UNCERTAIN>
     **Anchor:** <code path or symbol, if one exists>
     Selection opens the evidence each time: an entry whose files are gone, or whose cited lines
     no longer show a verifier's verdict, reaches no brief until it is re-anchored or retired, and
     `council memory check` says which. `council memory propose` drafts one under ## Proposed from
     a run's verified record; `council memory accept F-<n> --user-said "<their words>"` files it
     here on the user's yes (`reject` on their no). -->


## Proposed — awaiting the user's yes/no
<!-- One line per proposal, written the moment it is proposed so it survives the session. Format:
     "- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; from <deliverable>, <date>)"
     Yes → move it up with the next number. No → move it to Rejected. -->

## Rejected — proposals the user said no to; never propose these again
<!-- One line each: <title> · <date> · <the user's reason, if they gave one> -->

## Retired — entries the user withdrew; no run reads them
<!-- To retire an entry, move it here whole and add a line:
     **Retired:** <YYYY-MM-DD> — <why, e.g. superseded by EC-9> -->
