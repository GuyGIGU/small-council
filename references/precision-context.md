# Precision context v1

A context pack is a **run-local, seat-specific selection of evidence** prepared after the Chair
writes `<run>/brief.md`. It helps a worker start with material likely to matter to its assigned
slice, without copying the whole repository into the worker's window. It never becomes a second
source of orders: the brief, project hard constraints and each seat's full reference doc remain
authoritative. The Chair still owns scope and decides what the worker must inspect.

## Lifecycle and commands

1. Complete and validate `run-plan.tsv`; write the complete `brief.md` first.
2. `council context build <seat> [--run <folder>]` requires an exactly selected seat and reads
   its `context/<seat>/level` decision (`minimal`, `focused` or `full`) from that plan. A legacy
   run with no plan cannot infer the level and does not build a pack.
3. The optional Python 3.8+ provider writes `<run>/contexts/<seat>.md` and
   `<run>/contexts/<seat>.md.metrics.tsv`. `council context show <seat>` prints those paths and
   the metrics; it does not rebuild the pack. A successful build adds `context.built` to a run's
   event stream when one exists, including the level and expansion count.
4. Inspect the pack and omissions. When a needed repository path was left out, rebuild with one
   or more `--expand PATH` options and record the reason in the brief or run log. The expansion
   is explicit, not a silent change to routing or ownership. It must remain within the code root.
5. Give a worker the pack path only when it exists. The dispatch still points at the complete
   brief and reference docs. A missing pack is never a reason to weaken the brief.

The CLI calls the provider with `--root`, `--run`, `--seat`, `--level`, `--output`, and repeated
`--expand` values. It does not edit `CLAUDE.md`, choose a model, dispatch agents or change the
run plan. The pack and metrics are generated artifacts in the ignored run folder, not tracked
project memory. Even direct provider calls may write only under the run's `contexts/` directory,
never over another run artifact. Rebuild after a relevant code or brief change; `show` does not
assert freshness.

## Selection and accounting

The provider uses bounded, deterministic relevance signals from the run's brief and available
index/impact evidence, such as a seat's `- slice:` paths, changed files, direct static
relationships and likely tests. When an impact graph is absent, it marks an index-only fallback;
when the index is absent too, it uses the brief alone. A relevance signal is a candidate, not permission
to ignore an unselected file. Every level keeps the shared brief header and landscape, the exact
seat block, and the hard-constraints section. The levels cap included index entries and impact
rows at 8/16 (`minimal`), 24/64 (`focused`) and 80/200 (`full`) respectively. More context means
a wider evidence selection, not every source file. Source content is opened only with explicit
`--expand`; excerpts are capped at 4/12/32 KiB by level, with a 512 KiB source safety maximum.
Truncation and omitted paths remain visible.

The sidecar is a two-column UTF-8 TSV (`metric`, `value`) with baseline and included bytes,
reduction percent, selected and omitted path counts. Reduction can be negative when explicit
expansions make the pack larger than the baseline. It is accounting for context selection,
**not** a measure of correctness, coverage or token savings. The Chair should inspect any
provider limits, omitted paths and explicit expansions before claiming a seat had enough evidence.

## Boundaries and fallback

- Hard constraints and the exact user request belong in `brief.md` regardless of level. The pack
  cannot silently replace, relax or summarize them away. A worker must still follow its seat's
  reference doc and may open more files to answer its question.
- Static import links and filename/test hints are incomplete. Dynamic loading, generated files,
  aliases and runtime behavior may be invisible; an omitted path is not a clean bill of health.
- The provider must bound reads and reject paths that escape the code root, including symlinks.
  It reads evidence; it never executes project code or installs dependencies.
- If Python 3.8+ is unavailable or a build fails, the Chair uses the complete brief and reference
  docs as before, explicitly noting that no fresh pack was built. Other council commands and
  older runs remain valid.
