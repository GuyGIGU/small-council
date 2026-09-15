---
type: llm
focus: last_message
weight: 2
---
The repo has an unfinished council review of sample.py: both seats have reported, and the next step is to judge their findings (write the synthesis).

PASS if the reply brings up this unfinished review and either asks the user whether to resume it or close it, or resumes it at the judging step using the seat files already on disk.

FAIL if the reply doesn't mention the unfinished review, proposes a brand-new review from scratch, or says it will re-run the seats.
