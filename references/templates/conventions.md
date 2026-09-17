# Conventions — <project>
<!-- Small Council memory. Every council run reads this file first. Entries record the USER's
     decisions: agents may only PROPOSE (the Proposed section); the user confirms. Keep it under ~25 KB —
     past that, the council proposes a consolidation as numbered operations (merge, retire), never a
     rewrite.
     Every entry may carry **Scope:** (paths, globs or seat slugs it concerns — leave it out and every
     run reads the entry) and **Anchor:** (the paths, symbols or path:lines it is about, separated by
     commas; a path:line may list lines, as in `src/api/auth.py:42,60-71` — a path or a symbol
     survives edits; a line number can drift). Brief reads only the entries in scope
     (`council memory select`); `council memory check` flags an entry whose anchored file, line or
     symbol is gone.
     An entry is a heading (### AP-1: title) or a bullet (- **AP-1 — title** …). Runs read entries only
     under Accepted Patterns, Enforced Conventions and Decisions (a heading that says Adopted or
     Settled counts too) — never under Proposed, Rejected, Retired or a section of another name. -->


## Accepted Patterns (AP) — intentional; never flag these
<!-- ### AP-1: <title>
     **Pattern:** <what the code does on purpose> · **Why:** <reason> · **Origin:** <deliverable or date>
     **Scope:** <src/api/**, hunt> · **Anchor:** <src/api/auth.py:42> -->

## Enforced Conventions (EC) — always / never rules
<!-- ### EC-1: <title>
     **Rule:** <always … / never …> · **Why:** <reason> · **Origin:** <deliverable or date> -->

## Decisions (D) — the user's rulings; agents never author these
<!-- ### D-1: <title>
     **Decision:** <what the user decided, in their words> · **Why:** <their reason> · **Date:** <YYYY-MM-DD> -->

## Proposed — awaiting the user's yes/no
<!-- One line per proposal, written the moment it is proposed so it survives the session. Format:
     "- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; from <deliverable>, <date>)"
     Yes → move it up with the next number. No → move it to Rejected. -->

## Rejected — proposals the user said no to; never propose these again
<!-- One line each: <title> · <date> · <the user's reason, if they gave one> -->

## Retired — entries the user withdrew; no run reads them
<!-- To retire an entry, move it here whole and add a line:
     **Retired:** <YYYY-MM-DD> — <why, e.g. superseded by EC-9> -->
