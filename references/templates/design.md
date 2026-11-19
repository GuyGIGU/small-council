# Design — <project>
<!-- The book's design page (references/run/book.md): every agent reads it before anything else. Two pages at most
     (about 120 lines). A line is here only if removing it would change what an agent does; a line that restates the
     code stays out. Each rule ends with its reason and its date: `— why: <the bug or decision it came from>
     (<YYYY-MM-DD>)`, or `— why: not recorded`, so it can be retired when its reason is gone. Written from the map at
     setup; kept true by each build for what it changed (references/run/book.md, After a build); a rule changed
     only on the owner's word. -->

## Parts
<One line per part: what it is, the folder it lives in, and which part it may call. Dependencies run one way.>

## Who owns each folder
| Folder | Owns | Never |
|---|---|---|

## The one way each job is done
The table is the map's `## One way per job` (.council/map.md), where the plan check reads it: one table, never a
copy here. Extend the row a job names; a second way beside it is a decision for the owner.

## Where new code goes
<One line per kind of addition: a command, a screen, a store, a test — the folder and the file next to it.>

## Rules
<- <rule> — why: <the bug or decision it came from> (<YYYY-MM-DD>)>
