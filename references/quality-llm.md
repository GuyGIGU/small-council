# LLM Pipeline Quality — Carmack × Willison

Philosophy: John Carmack. LLM-pipeline expertise: Simon Willison (creator of Datasette and the `llm`
CLI, coined the term *prompt injection*, relentless documenter of how language models actually fail in
production).

This doc covers building and reviewing any system that puts a large language model on a critical path:
prompt construction, output handling, tool / function calling, retrieval grounding (RAG), evals,
cost/latency, and model versioning. The governing stance: **an LLM is a non-deterministic, untrusted,
sometimes adversarially-steerable component.** Treat everything that flows into its prompt and everything
that flows out of it with the suspicion you'd give any external system.

Every finding must describe the **concrete failure mode** — not "this is bad LLM practice." A pipeline
that emits a confident wrong answer is worse than one that crashes, because a human downstream believes
it. Secrets and auth are Hunt's domain (security.md); deserialization is the Untrusted input seat's
(Patterson), Hunt's when Patterson isn't seated. Async and API plumbing is the backend seat
(quality-backend.md). Datastore integrity is the data seat (quality-postgres.md). This doc
covers: prompt injection, output validation, grounding/hallucination, non-determinism, context-window
and truncation, tool-call safety, evals, cost/latency, data governance in prompts/logs, and model
migration.

---

## Applying this seat to another stack

The examples come from the origin stack: an application calling a hosted LLM API, with Python snippets (`json.loads`).

The numbered principles are the constraint set; provider- and language-specific checks are illustrations. On another stack, find the analogous construct and apply the principle to it.

| In the origin stack | The general idea | Look for it in … |
|---|---|---|
| Prompt built from untrusted text | Untrusted data mixed into instructions | SQL or shell built by string concatenation; user formulas passed to `eval` |
| JSON mode + `json.loads` | Parse and schema-check at the boundary; handle the reject | Pydantic validation; Rust `serde`; Go `encoding/json` plus explicit checks |
| Tool / function calling | Side effects chosen by an untrusted decision-maker | MCP servers; webhook handlers; plugin or mod APIs |
| Context window, token budget | A hard size limit whose overflow is silent | Integer overflow and float precision loss; MySQL non-strict mode truncating strings; fixed-size buffers in firmware |
| Pinned model id, logged prompt | Reproducing a non-deterministic or versioned dependency | Pinned NumPy/SciPy versions plus a fixed RNG seed; a deterministic simulation's recorded inputs |
| Eval set | Regression checks on properties of the output | Golden-file tests; property-based tests (Hypothesis, proptest); `numpy.testing.assert_allclose` |

**Recast as numerical / simulation correctness.** A project with no LLM — a deterministic compute engine — may have `council-init` recast this seat while keeping this doc: apply the principles to numbers instead of tokens. What carries over: Principle 2 (parse defensively at the boundary; check shapes, dtypes and units; quarantine NaN, inf and malformed values before they propagate), Principle 5 (silent overflow, precision loss and dropped rows), Principle 4 (pin versions, seed RNGs, record inputs for reproducibility), Principle 7 (guard every result with a regression check) and Principle 10 (upgrades that shift results). The rest apply where their construct exists — untrusted input, side-effecting tools, user data. The recast is a per-project decision recorded in `.council/council.config.md`, not baked into this doc.

---

## Principle 1: Prompt injection — untrusted text in the prompt is code you didn't write

*Carmack: "If a vulnerability is syntactically possible, it statistically exists in your codebase."*
*Willison: "Prompt injection is the most serious unsolved security problem of the LLM era — you cannot
reliably tell the model to ignore instructions that arrive inside its own input."*

The moment you concatenate untrusted content — a user message, a web page, a retrieved document, a tool
result, an email body — into a prompt, that content can override your system instructions. There is no
reliable escaping, no `htmlspecialchars` equivalent. This is the single most dangerous class of LLM bug
because it is **silent and often flattering**: the demo works, and the exploit only shows up when someone
crafts input designed to hijack the model.

### What to check

**The lethal trifecta**
- The severe case is a pipeline that combines, in one agent, all three of: **access to untrusted
  content**, **access to private data**, and **the ability to exfiltrate** (send an email, make a
  request, render a link). Any two are survivable; all three means injected text can read secrets and
  ship them out. If a review finds all three converging on one model call, that is the headline finding.
- Severity: **P1** whenever injected content can reach a side effect or private data.

**Instructions and data are not separated**
- Untrusted content pasted directly after the system prompt with no delimiting, no role separation, and
  an implicit assumption that "the model will obey the system message over the injected one." It won't,
  reliably. Delimit untrusted spans, keep them in a user/tool role, and never let their text be treated
  as authoritative instructions.
- Severity: **P1** when the injected span can trigger an action; **P2** when it can only skew a
  read-only answer.

**Trusting the model to police itself**
- "We added a line telling it to refuse malicious instructions" is not a control. Guardrails that are
  themselves prompts are bypassable. Real defense is *outside* the model: constrain what the tools can
  do, validate output, and gate side effects on checks the model can't talk its way past.
- Severity: **P2** for a prompt-only defense presented as a security boundary.

---

## Principle 2: Never trust model output — validate, constrain, parse defensively

*Carmack: "Every input is a potential source of errors."*
*Willison: "Treat the output of an LLM like you'd treat input from an untrusted user — because
effectively that's what it is."*

The model returns free-form text even when you asked for JSON. It will add a prose preamble, a stray
markdown fence, a trailing apology, or an almost-valid object with one hallucinated field. Code that
does `parse(response)` with no failure path crashes on the first non-conforming answer — and in a batch
job, nobody is watching.

### What to check

**Unvalidated structured output**
- `json.loads(response)` / `parse(...)` with no try/except and no schema check. Use the provider's
  structured-output / function-calling / JSON-mode where available — it reduces malformed output but
  does **not** eliminate it. Always validate the parsed object against a schema and handle the reject.
- Severity: **P1** if unvalidated output drives a side effect or a downstream decision; **P2** for a
  display-only path.

**Output rendered without escaping (injection round two)**
- Model output interpolated into HTML, a shell command, a SQL string, or a file path is exactly as
  dangerous as any untrusted string in those sinks — now with the twist that an attacker may have
  *steered* the model into producing it (Principle 1). Markdown that renders as HTML can carry an
  exfiltrating image URL.
- Severity: **P1** for model output reaching an eval/exec/HTML/SQL sink.

**Assuming the shape without checking it**
- "The model always returns a list of three items" holds until it returns two, or four, or an empty
  string on a refusal. Bound and check counts, types, and enum membership before use.
- Severity: **P2**.

---

## Principle 3: Grounding and hallucination — an answer with no source is a guess

*Carmack: "Don't build on assumptions you can't verify."*
*Willison: "The model is a very confident intern who has read everything and remembers nothing exactly —
make it show its sources."*

A model will produce fluent, plausible, wrong answers with total confidence. For anything factual, the
answer must be **grounded** in supplied context (retrieval), and you must be able to check that it
actually was. A fabricated citation is worse than none.

### What to check

**No grounding path for factual claims**
- A user-facing factual answer generated from the model's parametric memory alone, with no retrieved
  context and no citation, is unverifiable by construction. Provide the context, instruct the model to
  answer *only* from it, and give it an explicit "the context doesn't say" path.
- Severity: **P1** for ungrounded user-facing factual output; **P2** for internal/low-stakes use.

**Citations that aren't checked**
- Asking the model to "cite sources" invites *hallucinated* citations — real-looking IDs pointing at
  nothing. If citations matter, validate that each returned reference exists in the supplied context;
  don't render an unverified one.
- Severity: **P2**.

**No abstention path**
- If the only options the prompt affords are "answer" or "answer," the model always answers — including
  when it shouldn't. A retrieval miss should be able to surface "I don't have that," not a confabulation.
- Severity: **P2** for a missing "I don't know" branch on a decision path.

---

## Principle 4: Non-determinism and reproducibility — pin the model, record the call

*Carmack: "If you can't reproduce a bug, you can't fix it."*
*Willison: "Log everything. When an LLM does something weird you get one chance to understand it, and
only if you captured the exact prompt, model, and parameters."*

The same prompt returns different answers across calls, across temperature settings, and — worst — across
silent provider-side model updates. A pipeline you can't reproduce is a pipeline you can't debug or
regression-test.

### What to check

**Unpinned model identifier on a critical path**
- Calling a moving alias (a bare `latest`-style name) means the provider can change the model under you
  with no code change and no warning, shifting behavior and breaking evals. Pin to a specific, dated
  model id; upgrade deliberately (Principle 10).
- Severity: **P1** for an unpinned model on a critical path.

**Unlogged prompt / model / params**
- If the exact rendered prompt, model id, temperature, and seed (where supported) aren't recorded with
  the output, a bad result is a dead end — you can't reproduce it. Capture them, redacting per Principle 9.
- Severity: **P2**.

**Assuming temperature 0 means deterministic**
- Even at temperature 0 most hosted models are not bit-for-bit deterministic (batching, hardware, MoE
  routing). Don't build an equality/caching assumption on exact-output stability; key caches on the
  input, not the output.
- Severity: **P2** for a determinism assumption that doesn't hold.

---

## Principle 5: Context windows and truncation — dropped tokens are silent

*Carmack: "The structure of the code should make the intended behavior obvious."*
*Willison: "Everything is about the context window — what you put in it, and what silently falls out."*

Prompts that grow — accumulated chat history, a pile of retrieved chunks, a giant pasted document —
overflow the context window. Depending on the layer, the call errors, or the middle of the prompt is
quietly dropped, and models attend worst to the middle ("lost in the middle"). Either way, information
you thought was in the prompt wasn't.

### What to check

**No token budget**
- Building a prompt by concatenation with no token accounting means it works on short inputs and
  silently degrades or errors on long ones. Count tokens before sending; know the model's limit and
  reserve headroom for the completion.
- Severity: **P1** for silent truncation of instructions or critical context; **P2** for a hard error
  on overflow with no graceful path.

**Truncation by luck instead of by design**
- When the prompt must be trimmed, decide *what* to keep (system instructions, the most relevant
  retrieved chunks, the latest turns) rather than letting a naive slice drop whatever falls off the end
  — which is often the very instructions that keep the model on task.
- Severity: **P2**.

**Unbounded history growth**
- A chat loop that appends every turn forever will eventually blow the window and the per-call cost.
  Summarize, window, or evict old turns deliberately.
- Severity: **P2**.

---

## Principle 6: Tool and function calling — the model can request dangerous actions

*Carmack: "If a mistake is possible, it will eventually happen."*
*Willison: "The agent will call the tool with the wrong arguments, or be talked into calling it, so the
authorization has to live in the tool, not in the prompt."*

When the model can invoke tools, it can pick the wrong tool, pass the wrong arguments, or be steered
(Principle 1) into a destructive call. The model's *request* to do something is never authorization to
do it.

### What to check

**Side-effecting tools driven purely by model output**
- A tool that deletes, sends, pays, writes, or mutates, invoked directly on the model's say-so with no
  independent check, is a prompt injection away from being weaponized. Validate arguments, enforce
  authorization in the tool implementation, and require confirmation for destructive/irreversible
  actions.
- Severity: **P1** for an unguarded side-effecting tool.

**No read/write separation**
- Bundling read-only and mutating capabilities behind one loosely-scoped agent widens the blast radius.
  Prefer least-privilege tools; keep the ones that can only observe separate from the ones that can act.
- Severity: **P2**.

**Unbounded tool/agent loops**
- An agent that can call tools in a loop needs a step budget and a cost ceiling, or a confused run bills
  and acts indefinitely. Bound iterations and detect non-progress.
- Severity: **P2**.

---

## Principle 7: Evals and regression — you cannot eyeball quality at scale

*Carmack: "If it isn't tested, it's broken."*
*Willison: "The teams that win at LLMs are the ones that build good evals — everything else is vibes."*

Without an eval set, every prompt or model change is a blind change: you fix one case by hand and
silently regress ten you didn't look at. LLM quality has to be measured against a fixed set of examples,
not judged by the last demo.

### What to check

**A prompt/model change with no before/after eval**
- Editing the prompt or bumping the model on a critical path with no eval run is unverified. Keep a
  golden set of representative inputs with expected properties, and diff behavior across the change.
- Severity: **P1** for an unevaluated change to a critical prompt/model; **P2** for a missing eval
  harness on a lower-stakes path.

**LLM-as-judge taken at face value**
- Using a model to grade a model is useful but carries its own bias, non-determinism, and gameability.
  Anchor it with some human-labeled examples, check judge agreement, and don't treat its score as ground
  truth.
- Severity: **P2**.

**Evals that test the framework, not the behavior**
- An eval asserting "a response came back" or mocking the model call proves plumbing, not quality. The
  assertion has to be on a *property of the answer* the pipeline is supposed to guarantee.
- Severity: **P2**.

---

## Principle 8: Cost and latency — tokens are money and every call is a round-trip

*Carmack: "Find the simplest solution possible, and only increase complexity when needed."*
*Willison: "The cost of a careless pipeline is a real number on a real invoice — measure the tokens."*

Each model call costs tokens and a network round-trip. The economics only show up under real volume, so
they're easy to ignore until the bill or the p95 latency arrives.

### What to check

**Per-item calls over a large collection**
- A loop that calls the model once per row / document / user is an O(n) cost and latency multiplier.
  Batch where the API allows, or reconsider whether every item needs the model at all.
- Severity: **P2** for avoidable cost/latency; **P1** if it blows a wall-clock budget (a request
  timeout, an interactive response target).

**No caching of stable prompts**
- A large, unchanging system prompt or context resent on every call wastes tokens; provider prompt
  caching (or an application-level cache keyed on the input) removes that cost. Cache what's stable and
  hot; never cache what must be fresh.
- Severity: **P2**.

**Oversized model for the job / no streaming**
- Reaching for the biggest model when a smaller/cheaper one passes the eval is waste. And a
  long completion delivered as one blocking response feels broken even when it's fast — stream it to
  the user.
- Severity: **P2**.

---

## Principle 9: Data governance in prompts and logs — prompts and traces leak

*Carmack: "State is the enemy — the less you hold, the less you can lose."*
*Willison: "Remember that everything you put in a prompt may be logged, retained, and used — by your
own observability stack and possibly by the provider."*

Prompts routinely carry user data; observability captures prompts; providers may retain them. Data you'd
never write to a public log can end up in a trace, and data policy forbids can end up on a third-party
server.

### What to check

**Secrets / PII flowing into prompts or traces**
- API keys, credentials, or regulated personal data concatenated into a prompt, then captured verbatim
  by tracing/logging that crosses a trust boundary. Redact before logging; minimize what enters the
  prompt in the first place.
- Severity: **P1** for secrets/PII crossing a trust boundary via prompt or log.

**Sending data to a provider that policy forbids**
- Routing regulated or contractually-restricted data to a hosted model without checking retention/DPA
  terms. Confirm the data class is allowed on the chosen endpoint; consider redaction or a
  self-hosted/regional model where required.
- Severity: **P1** for a policy-violating data flow; **P2** for an unreviewed one.

**Unbounded prompt/response retention**
- Storing full prompts and completions forever, unredacted, is a growing liability. Retain deliberately
  and redact sensitive spans.
- Severity: **P3**.

---

## Principle 10: Model migration and versioning — behavior drifts under you

*Carmack: "Assertions catch assumption violations before they become exploitable."*
*Willison: "A new model version is a new dependency — it will change formatting and behavior in ways your
prompt quietly relied on."*

Providers deprecate models and ship new versions that reformat output, change refusal behavior, or shift
capability. A pipeline coupled to a specific model's quirks breaks on upgrade — or worse, gets silently
migrated.

### What to check

**Unmanaged / silent migration**
- Relying on a provider default that can be swapped, or upgrading a pinned model without re-running evals.
  Treat model+prompt+eval as one coupled unit: pin the model, and on any change re-run the eval before
  shipping.
- Severity: **P1** if a silent model swap changes a previously-validated behavior with no re-eval;
  **P2** for an unmanaged-but-visible migration.

**Deprecation with no plan**
- A model on a published sunset date with no migration path is a scheduled outage. Track deprecations;
  have the successor evaluated before the shutoff.
- Severity: **P2**.

**Prompt overfit to one model**
- A prompt hand-tuned to exploit one model's exact formatting habits is brittle across versions and
  vendors. Prefer robust instructions and output validation over fragile format-coaxing.
- Severity: **P3**.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Injection to a side effect, unvalidated output driving action, ungrounded facts, unreproducible/unevaluated critical calls, data leak | The lethal trifecta on one agent, raw output parsed (`json.loads`) straight into a mutation, model output into an HTML/SQL/exec sink, ungrounded user-facing facts, unpinned model on a critical path, secrets/PII in a prompt or trace, a silent model swap with no re-eval |
| **P2 — Fix Soon** | Weaker guardrails, missing abstention, unmanaged budgets, thin evals | Prompt-only "guardrail," hallucinated-but-unchecked citations, no token budget, truncation by luck, no read/write tool split, LLM-as-judge taken at face value, per-item calls at volume, unmanaged migration |
| **P3 — Consider** | Hygiene that compounds | Unbounded prompt/response retention, model-overfit prompts, missing streaming on long completions |

### The Overriding Filter

Before writing any finding, apply the Willison–Carmack synthesis:

1. **Could untrusted text reach the prompt and trigger a side effect?** If untrusted input, private
   data, and an exfiltration path meet on one call, flag it first. (Prompt injection is the worst bug —
   silent and unsolved.)
2. **Is model output validated before it's used or rendered?** If it's parsed, executed, or shown with
   no schema/escape, flag it. (Treat output as untrusted input.)
3. **Is a factual claim grounded and checkable, or a guess?** If there's no context and no verifiable
   citation, flag it.
4. **Is the call pinned and reproducible?** If the model is a moving alias or the prompt/params aren't
   logged, flag it. (No reproduction, no debugging.)
5. **Can context silently truncate?** If the prompt can overflow with no budget, flag the silent drop.
6. **Is every side-effecting tool authorized independent of the model?** If a destructive action fires
   on the model's say-so alone, flag it.
7. **Is there an eval guarding this prompt/model?** If a critical change ships on vibes, flag it.

---

## Origin-stack examples (hosted LLM APIs)

Nothing here is origin-specific: the principles are written for LLM pipelines in general, and the one language-specific snippet (Python's `json.loads`, Principle 2) stands for any parser.
