---
name: verifier-calibration
---
Use the small-council:council-verifier agent to check these four claims about sample.py against the real code. Pass it only the claims below, not your own view of them. There is no brief; the code root is this folder. It should write its verdicts to verify-1.md in this folder, with the title line `# Verification — calibration`.

1 · average() raises ZeroDivisionError when it is given an empty list — sample.py:8
2 · last_or_none() raises IndexError when it is given an empty list — sample.py:12
3 · average() returns the arithmetic mean of a non-empty list — sample.py:4-8
4 · `total` is a module-level variable shared between calls to average() — sample.py:5
