# What a build's brief adds to the review's (D56)

`council run open council-implement` writes the review's brief, `review-brief.md`, and puts each
block below on its `{{NAME}}` line; a review's brief has those lines taken out. The role texts stay
in the review's brief, word for word, never copied here.

[BUILD]
## This change is a build

The council has just built this change from a plan. Its record is the plan, not the builders: the
behaviour lines under Intent are what it must do, and the book is what it must keep to. Neither
seat reads the builders' reports, the build log or `patches/`: judge the change itself. A
behaviour line the change does not meet, or meets only by a workaround (a retry, a skipped case, a
loosened check, a special case for the test), is a P1.
[BUILD_RUNNER]
- each test can fail: for each behaviour line, in the new clone break that behaviour on purpose
  (the smallest edit that undoes it), run the test or check meant to prove it and show it go red,
  then put the clone back (`git -C <clone> checkout -- .`). A test that stays green proves
  nothing: report it as a finding, with the line and the test; so is a line no test covers. Under
  your `checks:` line, one line each: `proved: <behaviour line> — <test> — red when broken |
  STAYED GREEN | no test`.
