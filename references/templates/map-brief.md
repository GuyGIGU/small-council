# Brief — mapping <project>
<!-- A large repository's map (council-init, Phase D; D72): the main session writes this to <run>/brief.md, one
     `### map-<area>` block per top-level area (four at most), every <…> filled. Each area is mapped by a plain
     `small-council:council-worker`, recorded with `council seat`, on the model the config's `- models: map=` names (D78). -->
Deliverable: one seat file per area, <run folder>/seats/map-<area>.md; the main session merges them into <council home>/map.md
Code root: <code root> · Council home: <council home> · Run: <run folder>

Each seat maps one area of this repository for the agents that will work in it later: where things
live, the flows that matter, the vocabulary, and the conventions new code must match. Map, don't
review: no findings, no opinions on quality. Keep to what the code does not say by itself.

## Seats
### map-<area> — maps <the area's paths>
- ref: none
- out: seats/map-<area>.md
- slice: <the area's paths, as globs from the code root>
- cap: 8 · budget: ~30 tool calls
- role:

> Map your area, and only your area. Read its entry points, its folder layout and enough of each
> part to say what it is for; follow one or two of its main flows from where they start to where
> they store or show a result. Use git history for the hot spots (`git log --since=12.months
> --name-only --format= -- <your paths> | sort | uniq -c | sort -rn | head`). Do not read every
> file, and run nothing but small read-only commands.

## Format

Line 2 of your file: `ref: none`. Then an `## Index` of at most 8 rows, each
`<n> · map · <section> · <path> · <one-line fact>`, where `<section>` is one of the map template's
sections (Shape, Where things live, Flows, Hot spots, Vocabulary, Conventions, One way per job).
Then, under a heading per section, your area's lines for it, a path on every line. For One way per
job: each recurring job your area owns, the one way it is done, and the file that does it.

## Hard constraints — do not forget
- Change nothing in the project. Your file is the only thing you write.
- A line with no path is not a map line. A guess is marked `(unverified)`.
- The project's hard rules, word for word: <the config's `## Hard rules`, or none>
