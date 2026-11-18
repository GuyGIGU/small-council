# <Seat> — <lens> card for <project>
source: references/<doc>.md · written: <YYYY-MM-DD> @ <short-sha> · stack: <stack-fingerprint hash>
<!-- A seat card is the seat's reference doc translated to THIS project — at most ~1.5k tokens (6 KB).
     Workers read it first; its first line is what they copy onto their ref: line. They open the full
     doc only for the principles they cite; the brief gives its absolute path on a `- doc:` line,
     because source: is relative to the plugin (references/…) or the repo (.council/refs/…).
     How it is written — these rules live here, and only here:
     - When: the first run that selects the seat, at Brief, before its seat block (doctrine 04-brief.md,
       Cards first). Setup writes none, and a Solo run, which briefs no seat, writes none. A
       council-init refresh rewrites a card that exists when the seat's doc, surface or stack changed.
     - From: the roster row (its slug names the file, `.council/cards/<slug>.md`), its Reference doc,
       the surface markers, the map's hot spots when there is a map, and the project's memory.
     - How: one seat at a time, saved before the next. List the doc's principles
       (`grep -n '^## Principle' <doc>`) and read each principle's section only as you write its line.
       After a compaction, carry on from the first selected seat without a card.
     - Translate the doc; never paste it. Leave these comments out of the card. -->

## Principles, applied here
1. <the principle's title, numbered as in the source doc> — here: <what it means in this repo: the construct, a path or an idiom>
2. <…>
<!-- Every principle from the doc, with the same numbers. "— here: not applicable (<why>)" is allowed. -->

## Severity here
- P1: <this lens's P1 in this repo, e.g. "an unvalidated save file reaching the loader">
- P2: <…>
- P3: <…>

## Where to look
- <path or glob> — <why it matters to this lens: a hot spot, an entry point, a known trap>

## Not a finding here
- <deliberate choices this lens must not flag in this repo — cite the memory id if there is one>
