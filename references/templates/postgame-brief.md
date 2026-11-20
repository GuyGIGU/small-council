# What a post-game's brief adds to the review's (D68)

`council run open council-postgame` writes the review's brief, `review-brief.md`, and puts the block
below on its `{{POSTGAME}}` line. The role texts stay in the review's brief, word for word, never
copied here.

[POSTGAME]
## This is a post-game: the finished work against the owner's request

The question here is not what will hurt the project but: does the work do what the owner asked,
all of it, and nothing they did not ask for? Read "the change" in your role as the work in the
range (Target), and its record as the owner's request: ask.md and its numbered parts below. Never
read the plan, the build logs, the council's reviews or post-games, or `patches/`: they say what was
meant to be built, and you show what was. A document saying a part was built is not evidence that
it was.

Parts: <the request's numbered parts, one line each: `<#> · "<its quote, word for word>"`>

- reader: for each part, trace the code that should do it from where a user reaches it. A part done
  only on paper (written but never called, behind a switch that is off, a stub) is not met.
- runner: for each part a run can show, show it at the new end in your clone (the test that covers
  it, or a small probe), and at the old end too when the part asks for a change of behaviour. Say
  which parts no run can show. The project's checks at both ends still run, as your role says.
- Your `## Index` has one line for every part, in its number, then any other, in this form instead
  of the item format below:
  `<n> · <MET | PARTLY MET | NOT MET | CAN'T TELL> · <part <#> | asked, not covered | built, not asked> · <path:line> · <title>`
  "asked, not covered" is something ask.md asks that no part covers; "built, not asked" is work in
  the range that serves no part. Under each, `### <n>. <title>` with `- Shown by:`, `- What
  happens:` (what the owner would see), `- Recommendation:` and `- Refuted if:`. A CAN'T TELL says
  what would settle it.
- Code quality and style are not findings here. A serious problem outside the parts: one line and
  its `path:line` under `## Noticed` at the end of your file, or `none`.
