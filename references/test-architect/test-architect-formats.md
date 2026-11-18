# Test Architect — output formats

Loaded by the `test-architect` skill at the step that writes each artifact. Load only the section you
need.

---

## Audit report

```
# Test Audit: [scope description]

**Audited:** [N] test files covering [N] source files
**Untested high-risk files:** [list or "none"]

---

## P1 — Fix Now

### 1. [Title]

| | |
|---|---|
| **Test file** | `path/to/file.test.ts` |
| **Source file** | `path/to/file.ts` |
| **Principle** | Principle N — [name] from quality-testing.md |

**Finding:** [1-2 sentences. What's wrong with this test.]

**Consequence:** [1 sentence. What false confidence this creates.]

**Fix:** [1-2 sentences. What the test should do instead.]

---

## P2 — Fix Soon

[same format, omit Consequence for brevity]

---

## P3 — Consider

[short paragraph per finding]

---

## Summary

| # | Finding | Severity | Principle | File |
|---|---------|----------|-----------|------|
| 1 | [title] | P1 | [N] | [test file] |

## Verdict

[One paragraph: overall test suite health. What's the single biggest risk? What should be fixed first?]
```

## Audit summary (in chat — never just "audit complete")

```
## Test Audit Complete — [N] Findings

| # | Finding | Severity | Principle | File |
|---|---------|----------|-----------|------|
| 1 | [title] | P1 | [N] | [file] |

**Totals:** [N] P1, [N] P2, [N] P3

**Start with:** [1-2 sentence triage — which finding to fix first and why]

**Full report:** [report path]
```

---

## Test specification

```
# Test Specification: [feature name]

**Source:** [spec file or source file path]
**Test file:** [where the test file should live]
**Dependencies:** [list with classification: internal / database / external-service / non-deterministic]

## Test Setup

[Describe what the test environment needs. Be specific:]
- Database: [temp/in-memory DB with seed rows required, or "no database"]
- Fixtures: [sample input records, baseline/golden snapshots, sample data files, etc.]
- Mocks: [ONLY external system boundary mocks — list each one and what it should return for success AND failure cases]

MOCK BUDGET: [N] mocks maximum. If more are needed, the code should be refactored.

---

## Tests

### T1: [Behavioral description — NOT method name]

**Variant:** [happy path / error / edge / state]
**Desiderata priority:** [which Beck properties matter most — e.g., Behavioral + Predictive]

**Given:** [precondition — specific, with real values]
**When:** [action — single trigger]
**Then:** [assertions — specific expected values or structural invariants]

**Assertions (IMMUTABLE — do not modify):**
- `result.status` equals `'completed'`
- `result.items` is an array with length ≥ 5
- Each item has `id`, `type`, `content`, `score`
- All scores are between 0 and 100

**Mock configuration for this test:**
- [mock name] returns [specific realistic success data — provide the actual fixture]

**This test MUST FAIL if:**
- The function returns an empty result
- The function returns items without scores
- The function skips a required processing step

---

### T2: [next behavioral variant]
...

---

## Traceability Matrix

Every Gherkin scenario from the source spec must appear here with at least one test reference. Empty test columns are coverage gaps that must be justified in "What is NOT tested."

| # | Scenario (from spec) | Story | Unit | Integration | Component | E2E |
|---|---|---|---|---|---|---|
| 1 | [scenario name] | [story ref] | | T1 | T15 | |
| 2 | [scenario name] | [story ref] | T2 | | T16, T17 | |

**Coverage:** [N] of [M] scenarios covered ([percentage]%)
**Gaps:** [N] scenarios in "What is NOT tested"

---

## What is NOT tested (and why)

- [function/behavior]: [reason — e.g., "simple delegation with no conditional logic"]
- [function/behavior]: [reason — e.g., "trivially correct, tested implicitly by T3"]

## Cheating detection

The implementing agent MUST NOT:
- Modify any expected value listed above
- Remove or comment out any assertion
- Add `.skip`, `.todo`, or `.xit` to any test
- Mock internal modules — only external boundaries listed in Test Setup
- Create tests that pass with `return null` or `return {}` in the function body

If the test fails, fix the implementation, not the test. If the test specification appears wrong, STOP and ask.
```

## Specify summary (in chat — the traceability matrix is the headline)

```
## Test Specification: [feature name]

### Traceability: [N] of [M] acceptance scenarios covered

| # | Scenario | Story | Unit | Integration | Component | E2E |
|---|---|---|---|---|---|---|
| 1 | ... | ... | | T1 | T20 | |

**Gaps:** [list any uncovered scenarios and why]

### Test breakdown

| Layer | Count | File |
|---|---|---|
| Unit | [N] | [unit test file/dir] |
| Integration | [N] | [integration test file/dir] |
| Component | [N] | [component test file/dir] |
| E2E | [N] | [E2E test file/dir, if any] |
| **Total** | **[N]** | |

**Regression/determinism guards** (cross-cutting): [baseline or byte-parity checks this change must keep green, or "none in this project"]
**Mock budget:** [N] mocks (unit: [N], integration: [N])
**Not tested:** [list of explicitly skipped items with justifications]

Full spec: [spec path]
```

---

## Determinism & regression — the three-tier decomposition

When the target is a **deterministic computational core** — the calculations, rules, or state machine
that decide an outcome — apply Principle 8's three tiers.

### Tier 1: Deterministic unit tests
- **Decision functions** — given a hand-built input with a known-correct answer, assert the rule fires; and, just as important, given a near-miss input, assert it does NOT fire. Test the boundaries: first/last element, exact-threshold, off-by-one window edges.
- **Scoring / gate logic** — given specific inputs, assert deterministic outputs.
- **Numerical / malformed edges** — feed NaN/inf/empty/gap inputs and assert the documented behavior (no silent corruption).

These tests use **explicit expected values with tolerances** for floating-point (never `==` on computed reals). No randomness, no network.

### Tier 2: Regression tests (baseline / golden-master)
- **Coverage regression** — run the core over a frozen set of known-good cases and assert it still produces the expected outcomes. This catches a change that silently drops behavior.
- **Baseline / snapshot** — compare current output against a stored baseline; an unexplained diff is a failure. Regenerate the baseline only when the change is intended, and say so.
- These are deterministic because the inputs are pinned fixtures, not live data.

Provide the fixtures as part of the test specification: name the frozen case set and the baseline file the spec depends on.

### Tier 3: Byte-parity & invariants (for refactors)
- For any change claimed to be **behavior-preserving** (extracting a shared helper, a DRY fold): capture output before, apply the change, capture after, assert **bit-identical**.
- For genuinely new logic, assert **structural invariants** the result must always satisfy (e.g. a lower bound never above its upper bound, a width non-negative, a rank within range) rather than exact values.
- Keep slow, whole-system runs out of the fast unit suite.
