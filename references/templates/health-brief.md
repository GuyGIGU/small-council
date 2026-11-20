# What a health pass's brief adds to the review's (D65)

`council run open council-health` writes the review's brief, `review-brief.md`, and puts the block
below on its `{{HEALTH}}` line. The role texts stay in the review's brief, word for word, never
copied here.

[HEALTH]
## This is a health pass, not a review of a change

There is no change and no change index. Read "the change" in your role as the whole project as it
is now (Target), and its record as the book. The question: where has the project drifted from its
book, and which refactor would bring it back? Start from the design page's parts and the map. Report
each place the code no longer matches the design page (a part doing a job the page gives another, a
second way beside a job's one way, code where the page says new code does not go), the stack page
(something in use it does not list, or listed and no longer used), or a recorded decision; and a
known problem that has grown worse since it was noted. Each item is a proposal: `Recommendation:`
the refactor; `What it costs:` the work it takes (an hour, a day, a week of one builder) and what it
risks; `What happens:` what goes wrong, or gets harder to change, if nothing is done; and one more
line, `- Can it be undone: easily | with work (<what it takes>) | hard (<why>)`. `Origin:` is
`pre-existing` for every item, and the rule against what was already so before the change does not
apply: what is already so is the subject. At most ten items, the ones the owner would act on first;
end your file with `## Noticed`, one line and a `path:line` for each other thing, or `none`. The
runner is started only when an item needs a check run to be shown; its dispatch then names that
check on a `Check:` line, and it runs that one check in one clone of the project as it is.
