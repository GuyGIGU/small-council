# What a large test audit's brief adds to the review's (D75)

`council run open test-architect` writes the review's brief, `review-brief.md`, and puts the blocks
below on its `{{AUDIT}}` and `{{AUDIT_READERS}}` lines. The role texts stay in the review's brief,
word for word, never copied here.

[AUDIT]
## This is a test audit, not a review of a change

There is no change and no change index. Read "the change" in your role as the project's tests as
they are now (Target), and its record as what each test's name, comments and assertions claim. The
question: which tests prove nothing, and which code that matters would break with no test noticing?

Reading, for every seat: `<the plugin's folder>/references/quality-testing.md`. Its numbered
principles are what "proves nothing" means here; cite one (`Principle <n>`) only for a problem you
found in a test, never because the page lists it.

Shares: <each reader's share of the test files, one line each: `<reader|reader-2|reader-3> · <its folders or files>`; every test file in exactly one share>
Riskiest code: <the high-risk source files from the surface map (the core decision logic, anything that writes durable data), five at most, for the runner>

- readers: read only your share. For each test file ask, in this order: can a test in it fail at
  all (no assertion, or only trivial ones; the function body replaced by `return null` and it still
  passes); does any test set its dependencies up for success and assert on the whole result; do the
  assertions check what the code did or only that a mock was called; do the expected values come
  from the implementation itself. Then the smaller things: a test that breaks on a refactor with no
  change of behaviour, more test code on trivial code than on the logic that decides an outcome,
  retries and widened tolerances, skipped or weakened assertions. One item per problem, the worst
  first; the same problem across many files is one item that names them. Severity: P1 a test that
  gives false confidence, P2 a gap or a test tied to the code's shape, P3 upkeep.
- runner: your clone is of the project as it is: one clone, `now` in the scratch folder named above, no
  old end.
  Run the test suite once, whole, and record what it does. Then, for each file under Riskiest code,
  one at a time: break its main decision on purpose in the clone (return a constant, flip a
  comparison, drop a write), run the tests that should cover it, write down which tests failed,
  and put the code back before the next break. An item for each break no test noticed: `Shown by:`
  the break (`path:line`, what you changed) and the command that still passed. Never break anything
  outside the clone.
- Every seat ends its file with `## Noticed`: source files that matter and have no test at all, one
  line and a path each, or `none`.

[AUDIT_READERS]

### reader-2 — reads its share of the test files for tests that prove nothing
- ref: none
- out: seats/reader-2.md
- only when the plan selects it
- slice: its line under Shares
- cap: 10 · budget: ~100 tool calls
- role: the reader's role above, word for word, on its own share. Never open another reader's file.

### reader-3 — reads its share of the test files for tests that prove nothing
- ref: none
- out: seats/reader-3.md
- only when the plan selects it
- slice: its line under Shares
- cap: 10 · budget: ~100 tool calls
- role: the reader's role above, word for word, on its own share. Never open another reader's file.
