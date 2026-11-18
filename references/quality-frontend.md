# Frontend Quality Reference — Carmack × Dodds

Philosophy: John Carmack. Specifics: Kent C. Dodds (React Testing Library, Epic React, AHA Programming).

Every finding must describe the **concrete cost of getting it wrong** — not just "this is bad practice."
Performance (memoization, bundle size, re-renders, Suspense, caching) is covered by **quality-performance.md**, the Performance seat. **Do not duplicate performance findings here.** Focus on correctness, maintainability, testability, and architectural quality.

---

## Applying this seat to another stack

Origin stack of the examples: Next.js App Router / React / TypeScript / tRPC / CSS Modules + BEM (not Tailwind).

The numbered principles are the constraint set; framework-specific checks are illustrations. On another stack, find the analogous construct and apply the principle to it. Origin-only checks sit at the end, by principle.

| In the origin stack | The general idea | Look for it in … |
|---|---|---|
| Components, custom hooks, Context | A view unit, reusable stateful logic, a scoped shared dependency | Vue composables and `provide`/`inject`; SwiftUI `@Environment`; Flutter `InheritedWidget` |
| `useState` synced by `useEffect` | Derivable state stored and kept in sync by hand | Vue `watch` into a `ref` instead of `computed`; SwiftUI `onChange` into `@State`; Compose state seeded from a parameter |
| tRPC / TanStack Query cache | Server data held in one cache, not copied into UI state | TanStack Query for Vue or Svelte; Apollo Client's cache; an Android repository exposing `Flow` |
| `isLoading`/`isError` flags vs a TypeScript union | One status value, so impossible states can't be represented | Kotlin sealed classes; Swift enums with associated values; Dart 3 sealed classes |
| React Testing Library, MSW | Test through what the user perceives; mock only the network | Testing Library for Vue, Svelte or Angular; Playwright `getByRole`; Compose `onNodeWithText` |
| Error Boundaries | Failures caught with a fallback, app-wide and per feature | Vue `onErrorCaptured`; Angular `ErrorHandler`; Flutter `ErrorWidget.builder` |
| `fetch` without `response.ok` | HTTP clients that don't fail on 4xx/5xx | Python `requests` without `raise_for_status()`; Go `http.Get`; Swift `URLSession` |
| Server Components, `use client` | Code runs where it must; only serialisable data crosses the boundary | Astro islands; Blazor render modes; Electron main ↔ renderer IPC |

---

## Principle 1: Duplication is local damage; wrong abstractions are systemic damage

*Carmack: simplicity over cleverness, concrete over abstract.*
*Dodds (AHA Programming): "prefer duplication over the wrong abstraction." — via Sandi Metz.*

Premature abstraction is the most expensive frontend mistake. Dodds: **"If you abstract early, you'll think the function or component is perfect for your use case and so you just bend the code to fit your new use case. This goes on several times until the abstraction is basically your whole application in `if` statements and loops."**

The cost isn't aesthetic — wrong abstractions are terrifying to change because every caller depends on the shape. Duplication is fixable locally; a bad abstraction propagates through every consumer.

### What to check

**Premature component splitting**
- Components split into multiple files when only used in one place. Dodds: "It's WAY easier to maintain it until it needs to be broken up than maintain a pre-mature abstraction."
- Dodds: **"You'll be surprised how simple a big render method can be when you just inline as much as you can."** A 200-line component with clear sequential logic is better than 8 files with 25 lines each connected by props.
- The concrete cost of premature splitting: more files → more props → more prop drilling → pressure to add Context/store → compounding complexity.
- Only split when one of these is concretely true: (a) same UI needed in multiple places, (b) can't tell which state relates to which markup, (c) need isolated testing of edge cases, (d) git conflicts are unmanageable.
- Severity: **P3** — unless the splitting has already caused prop drilling that triggered a global store (**P2**)

**Premature hook extraction**
- Custom hooks (or composables) extracted for "separation of concerns" with a single call site. Apply AHA: don't extract until reuse is real.
- Dodds: "Apply the AHA Programming principle and wait until the abstraction/optimization is screaming at you before applying it."
- Exception: context consumer hooks (e.g. `useAuth()`) are always appropriate — they enforce the provider boundary.
- Severity: **P3**

**Premature abstraction layers**
- Generic `<DataTable>` components with 15 props when only used for one table shape
- Component libraries with one consumer
- Wrapper components that just forward all props (the `{...rest}` anti-pattern without actual logic)
- Severity: **P3** — unless the abstraction is actively causing bugs due to if-statement branches (**P2**)

---

## Principle 2: Eliminate state that can be derived, then colocate what remains

*Carmack: minimise state — less state means fewer bugs.*
*Dodds: "Don't Sync State. Derive It."*

**This is the highest-alignment point between Carmack and Dodds.** Every piece of stored state that could be computed is a synchronisation bug waiting to happen. Dodds: **"The biggest problem with this is some of that state may fall out of sync with the true component state. It could fall out of sync because we forget to update it for a complex sequence of interactions."**

The fix: calculate during render. `const nextValue = calculateNextValue(squares)` has zero synchronisation risk because it's recomputed every render. Dodds: **"We don't need to worry about updating the derived state values because they're simply calculated every render."**

### What to check

**Derivable state stored as state**
- Any stored state (`useState`) whose value can be computed from other state or props. This is the #1 frontend correctness bug.
- Any effect or watcher (`useEffect`) that exists solely to synchronise two pieces of state — this is the "state sync" anti-pattern.
- URL or route params mirrored into local state — the URL is the source of truth; derive from it.
- Props copied into state and synced by an effect — just derive from props directly during render.
- Severity: **P1** when the derivable state controls a critical flow (payment, auth, data mutation). **P2** for UI state sync bugs.

**State lifted too high**
- State in a global store or root Context that's consumed by a single component or subtree. Dodds: "Ask yourself 'do I really need the modal's status (open/closed) state to be in Redux?'"
- Context providers at the app root that serve only one feature area. Dodds: "Not all of your context needs to be globally accessible!"
- The cost: every update to high-lifted state invalidates the entire tree beneath it, forcing memoisation (`React.memo`/`useMemo`/`useCallback`) everywhere, which Dodds calls **"death by a thousand cuts"** complexity.
- Severity: **P2** when it's causing real re-render cascades or complexity. **P3** when it's just misplaced but not causing harm yet.

**Server state treated as UI state**
- API response data manually stored in UI state instead of managed through a query cache. Dodds: "I would take the data I got from the server and treat it like it was UI state. I would mix it in with the actual UI state and this resulted in making *both* more complex."
- Bypassing an existing server cache (manual fetch + local state) is a quality regression.
- Severity: **P2**

**The state escalation framework** (check that the code follows this order):
1. Local state (`useState`) — for independent local state
2. Lift state up — to the closest common parent when siblings need it
3. Component composition — use `children`/slots to skip intermediate layers
4. A reducer (`useReducer`) — when state elements are interdependent (Dodds: "When one element of your state relies on the value of another element of your state in order to update")
5. Scoped context (React Context) — scoped to the relevant subtree, NOT at the app root
6. External library — only for server cache (tRPC/TanStack Query in the origin stack) or genuinely complex global state

---

## Principle 3: Use the type system as armour

*Carmack: "Use the type system as armour." Static analysis catches assumption violations before runtime.*
*Dodds: places static analysis at the base of the Testing Trophy — always on, catches entire categories of bugs, costs nearly nothing.*

Dodds: code with **"no logic in them at all (so any bugs could be caught by ESLint and Flow [TypeScript])"** doesn't need additional test coverage. The type system is testing that runs on every keystroke.

### What to check

**The armour is broken when you see:**
- Escape-hatch types (`any`) — they defeat the entire type system. Every one is a hole in the armour.
- Unchecked casts (`as`) — they bypass type checking. Each one is a developer saying "I know better than the compiler" (they usually don't).
- Catch blocks that cast the caught error to an assumed type (`error` to `Error`) instead of handling `unknown`. Dodds: "don't dismiss a compilation error or warning from TypeScript just because you think it's impossible." JavaScript can throw anything.
- State initialised to `null` or `undefined` with no type the checker can infer (`useState` without a type parameter).
- Severity: **P2** for escape hatches and casts on data boundaries (API inputs/outputs and responses, form data). **P3** for internal-only ones.

**Impossible states that types could prevent**
- Independent boolean flags (`isLoading`, `isError`, `isSuccess`) instead of a discriminated union status enum. Dodds: "By using a status variable rather than a simple isLoading indicator we enable our users to know exactly what the state is at any given point in time."
- The concrete bug: `isLoading: false, error: newError, data: staleData` — the render logic depends on check order and silently shows stale data or swallows errors.
- Fix: `type Status = 'idle' | 'pending' | 'resolved' | 'rejected'` — render logic becomes a switch on one value. Convenience booleans are fine **if derived**: `const isLoading = status === 'pending'`.
- Severity: **P2** when the boolean combination controls a data-critical flow. **P3** for simple UI toggles.

**Context without the fail-fast pattern**
- A context or injected dependency with a silent default (`createContext(undefined)` or `createContext(null)`) and no accessor that throws on misuse. Dodds' pattern: create with no default, export a custom hook that throws a descriptive error if used outside the provider. This makes incorrect usage crash immediately with a clear message instead of silently rendering with `undefined`.
- Dodds: "Toggle compound components cannot be rendered outside the Toggle component" — the error message tells you exactly what's wrong.
- Severity: **P2** — silent `undefined` from missing providers is a class of bug that's hard to trace.

---

## Principle 4: Test behaviour, not implementation

*Carmack: understand what the code does, not how it's structured.*
*Dodds: "The more your tests resemble the way your software is used, the more confidence they can give you."*

The Testing Trophy: Static (TypeScript/ESLint) → Unit (pure functions) → **Integration (the sweet spot)** → E2E (critical paths only). Dodds: **"Write tests. Not too many. Mostly integration."**

Why integration wins: **"It doesn't matter if your component `<A />` renders component `<B />` with props c and d if component `<B />` actually breaks if prop e is not supplied."** Testing units in isolation misses the integration contract. Testing integration catches both unit bugs and contract bugs.

### What to check

**Implementation detail testing (the core anti-pattern)**
- Tests that assert on internal state: `wrapper.state('count')` or accessing hook return values directly
- Tests that assert on component structure: `find('ComponentName')` or `container.querySelector('.internal-class')`
- Tests that call internal methods: `wrapper.instance().handleClick()`
- Tests that use shallow rendering (Enzyme pattern). Dodds: **"With shallow rendering, I can refactor my component's implementation and my tests break. With shallow rendering, I can break my application and my tests say everything's still working."**
- The two-question litmus test: (a) Will this test break when there's a mistake that would break the component in production? (b) Will this test continue to work after a backward-compatible refactor? Implementation-detail tests fail both.
- Severity: **P2** — these tests actively harm velocity by breaking on every refactor while providing false confidence.

**Wrong query priority — find elements the way users do**
- Query the way users find things, test IDs last. The priority hierarchy (enforced by `eslint-plugin-testing-library`):
  1. `getByRole` — top preference. Dodds: "There's not much you can't get with this. If you can't, it's possible your UI is inaccessible."
  2. `getByLabelText` — "really good for form fields"
  3. `getByPlaceholderText` — only when there's no label
  4. `getByText` — "text content is the main way users find elements"
  5. `getByDisplayValue` — current value of form elements
  6. `getByAltText`, `getByTitle` — semantic but less reliable
  7. `getByTestId` — escape hatch only. "The user cannot see (or hear) these."
- Flag: `data-testid` used when `getByRole('button', { name: /submit/i })` would work. Dodds: "I recommend you query by the actual text rather than using test IDs or other mechanisms everywhere."
- Severity: **P3** — won't cause bugs, but degrades test quality and misses accessibility issues.

**Over-mocking**
- Mocking internal modules, hooks, or components instead of testing through them. Dodds: "the biggest thing you can do to write more integration tests is to stop mocking so much stuff. When you mock something you're removing all confidence in the integration between what you're testing and what's being mocked."
- The only appropriate mocks: network requests (via MSW at the network boundary) and animation/timing dependencies.
- Flag: mocking your own hooks or child components (`jest.mock('./useMyHook')`, `jest.mock('./ChildComponent')`) — integration-confidence killers.
- Severity: **P2** when mocking hides a real integration bug. **P3** when it's just unnecessary.

**Bloated snapshot tests**
- Snapshot tests over ~20 lines. Dodds: "I've personally experienced this with a snapshot that's over 640 lines long. Nobody reviews it, the only care anyone puts into it is to nuke it and retake it whenever there's a change."
- Snapshots fail to encode authorial intent — when they break, developers update them without understanding why. This is a false-confidence anti-pattern.
- Acceptable snapshots: error messages, small focused data transformations, Babel plugin output. Use `toMatchInlineSnapshot()` and keep them small.
- Severity: **P3**

**Missing tests on critical paths**
- Dodds' prioritisation heuristic: "What part of your untested codebase would be really bad if it broke?" Start there.
- The "two users" test: end users (interact with rendered output) and developer users (render with props/context). Tests should exercise the component the way these two users interact with it.
- Flag: core flows (auth, payment, data mutations) without integration tests. Flag: custom hooks tested in isolation when they should be tested through their consuming component.
- Severity: **P2** for missing tests on data-critical paths. **P3** for missing tests on stable UI.

---

## Principle 5: Composition over configuration

*Carmack: make data flow visible and explicit.*
*Dodds: "Take advantage of component composition" — always before Context, always before external state.*

Dodds' compound component pattern: think of `<select>` and `<option>` — they don't make sense without each other. The pattern provides an expressive API without the "prop-ocalypse" of a single component accepting dozens of configuration props.

### What to check

**Prop drilling that skipped composition**
- Intermediate components forwarding props they don't use. Before reaching for Context, check: could the parent pass pre-composed `children` so intermediates never see the data?
- Dodds: "One of the things that really aggravates problems with prop drilling is breaking out your render method into multiple components unnecessarily."
- Severity: **P3** — unless it's already triggered the addition of a global store (**P2**)

**Compound components without the safety pattern**
- Compound components wired by cloning children (`React.cloneElement`) instead of shared context — fragile, breaks with wrapper elements.
- Compound components without an accessor that throws outside the provider — silent `undefined` bugs.
- Severity: **P2** for missing safety accessor. **P3** for clone-based wiring.

**Controlled/uncontrolled confusion**
- Components that accept a value prop but also manage internal state — unclear who owns the state.
- Dodds' Control Props pattern: if the user provides a value prop, defer to them; if not, manage internally. The component should never fight itself.
- Severity: **P2** when the confusion causes data loss (form inputs). **P3** for UI-only components.

---

## Principle 6: Errors are not exceptional — handle them structurally

*Carmack: deploy assertions as tripwires.*
*Dodds: unify error handling through Error Boundaries and status enums.*

### What to check

**Missing Error Boundaries**
- Any component tree with async operations (data fetching, mutations) but no error boundary (or the framework's equivalent) in its ancestry. Dodds co-maintains `react-error-boundary` and advocates: a top-level boundary to prevent white screens, plus granular boundaries around features.
- The cost: an unhandled runtime error takes down the entire UI tree — in React, a blank page. No logging, no recovery, no user guidance.
- Async errors often escape the boundary — route them to it explicitly.
- Severity: **P1** for no top-level error boundary at all. **P2** for missing granular boundaries around critical features.

**Boolean status flags instead of status enums**
- `{ isLoading, isError, data, error }` as independent values. The concrete bug: after an error, `isLoading` is false, `data` still has stale previous value, `error` has new error — render logic silently shows stale data depending on check order.
- Fix: `status: 'idle' | 'pending' | 'resolved' | 'rejected'` as single source of truth. Derive convenience booleans if needed. This makes the status a state machine — impossible states are unrepresentable.
- Note: if the data library already returns a status value (tRPC's `useQuery` does), flag only hand-built status tracking alongside it (duplication) or custom async operations outside it.
- Severity: **P2** when controlling data-critical UI. **P3** for simple loading indicators.

**The unchecked-status trap (`response.ok`)**
- Many HTTP clients fail only on network errors, NOT on 4xx/5xx (`window.fetch` only rejects on network errors). Any raw call to an external service must check the status and throw on failure.
- A client that already throws on error statuses (tRPC, for its own calls) is fine. Flag only raw calls without a status check.
- Severity: **P2**

**Untyped error handling**
- Catch blocks that assume the error's type or shape. Extract a message defensively instead.
- Severity: **P3**

---

## Principle 7: Colocate everything — tests, styles, utilities

*Carmack: code you can't see is code you can't reason about.*
*Dodds: "Place code as close to where it's relevant as possible."*

Dodds (quoting Dan Abramov): **"Things that change together should be located as close as reasonable."** The three costs of NOT co-locating: maintainability (files drift out of sync), applicability (people miss related files), ease of use (context-switching between directories).

The orphan utility problem: **"Later, your component is deleted, but the utility you wrote is out of sight, out of mind and it remains (along with its tests). Over the years, engineers work hard to make sure that the function and its tests continue to run and function properly without even realizing that it's no longer needed at all."**

### What to check

**Test file placement**
- Test files in a mirror directory tree (`__tests__/`) instead of next to source files, where the toolchain allows. Dodds: "co-locate our tests files with the file or group of files they are testing."
- The pattern: a component, its test and its styles in the same directory.
- Severity: **P3**

**Style placement and scope**
- Component styles in a separate `styles/` directory instead of next to their component.
- Selectors that reach into another component's elements — specificity leaking across component boundaries.
- Global styles that could be component-scoped — every global style is a potential specificity conflict.
- Severity: **P3** for placement. **P2** for specificity leaks that cause cross-component style bugs.

**Orphaned utilities**
- Functions in a `utils/` or `helpers/` directory consumed by only one component. Move them into the component file or directory until they're genuinely shared.
- Co-location means keeping related code together, even if that means multiple components or utilities in one file.
- Severity: **P3**

---

## Principle 8: Server-first, client only when required

*Carmack: don't run code where it doesn't need to run.*
*Dodds: bullish on RSC but critical of current Next.js implementation.*

Where components can run on the server or the client, default to the server; only state, event handlers and browser or device APIs need the client. On stacks with no such split, apply this to any process boundary (see the table above).

### What to check

**Unnecessary client components**
- Components shipped to the client that don't use state, effects, event handlers, or browser APIs (Next.js: marked `use client`). These should be server components.
- The client boundary placed too high in the tree — pushing more JavaScript to the client than necessary. Draw the boundary as deep as possible.
- Severity: **P3** — this overlaps with performance coverage (bundle size), so flag only when it's an architectural clarity issue, not a perf issue.

**Serialisation failures at the boundary**
- Attempting to pass functions, class instances, or other non-serialisable values across the boundary (from Server Components to Client Components — a hard error in RSC).
- The boundary is a data contract — only serialisable props cross it. Dodds doesn't have deep writing here, but the principle of explicit data modelling applies.
- Severity: **P1** if it causes runtime errors. **P2** if it's a latent bug (currently works by accident).

**Choosing the wrong data path**
- Where there are several ways to reach the server, match each to its job: a caching query client for reads and state-driven interactions; the simplest mutation path for forms and one-off writes.
- Flag: a mutation path used for data fetching (loses caching). Flag: a heavyweight client for a simple form submission.
- Severity: **P3** — choosing wrong adds complexity but isn't a correctness bug.

---

## Gaps: What This Doc Doesn't Cover

- **Performance**: memoization, React.memo, useMemo, useCallback, Suspense streaming, bundle splitting, lazy loading, re-render avoidance. Covered by **quality-performance.md**.
- **Accessibility**: Dodds' query hierarchy promotes accessible patterns, but this doc is not an a11y audit — that's the Accessibility seat, **quality-accessibility.md**.
- **RSC architecture depth**: Dodds hasn't published a dedicated RSC patterns post. His Epic React v2 covers basics, and his preferred framework, React Router, supports RSC only as an unstable preview (Framework Mode since v7.9.2). For Next.js-specific RSC patterns, supplement with Vercel docs and Lee Robinson's content.
- **CSS architecture at scale**: BEM + CSS Modules is well-established, but this doc doesn't cover design system architecture, theming patterns, or CSS custom properties strategies. Those are design decisions, not code quality issues.
- **Animation and transition patterns**: Not Dodds' domain.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | State bugs that corrupt data or crash the app | Derivable state controlling critical flows (payment, auth), missing top-level error boundary, serialisation failures at server/client boundary |
| **P2 — Fix Soon** | Patterns that actively cause bugs or kill velocity | State synced via effects (`useEffect`), server data copied into UI state, implementation-detail tests, over-mocking, boolean status flags on data-critical UI, Context without fail-fast accessors, global state for local concerns, `any`/`as` at data boundaries, specificity leaks across components |
| **P3 — Consider** | Hygiene that compounds over time | Premature component splits, single-use hooks, snapshot tests, `getByTestId` over role queries, test files in mirror directories, orphaned utilities, misplaced style files, unnecessary client components |

### The Overriding Filter

Before writing any finding, apply the Dodds-Carmack synthesis:

1. **Is this state necessary?** If derivable, flag it. (Carmack: eliminate. Dodds: derive.)
2. **Is this abstraction necessary?** If single-use, flag it. (Both: inline until forced.)
3. **Is the type system earning its keep?** If escape hatches, casts (`any`/`as`) or booleans where enums would work, flag it. (Both: armour only works when worn.)
4. **Do the tests test behaviour?** If asserting on internals, flag it. (Dodds: test use cases, not code.)
5. **Is everything colocated?** If scattered across directories, flag it. (Dodds: things that change together live together.)

---

## Origin-stack examples (Next.js / React / tRPC / CSS Modules + BEM)

### Principle 2 — Next.js URL state and tRPC's cache
- In Next.js App Router: derive URL state from `useSearchParams()`, never copy `searchParams` into `useState`.
- API data kept in `useState` instead of tRPC's query cache. tRPC already separates server cache from UI state via TanStack Query integration; manual `fetch` + `useState` for data that tRPC could manage is a quality regression.

### Principle 6 — react-error-boundary, TypeScript catch blocks
- For async errors that Error Boundaries can't catch natively: use `useErrorBoundary` hook from `react-error-boundary` to route async errors to the nearest boundary via `showBoundary(error)`.
- Catch blocks that assume `error instanceof Error`. Dodds: TypeScript correctly types catch errors as `unknown` because JavaScript can throw anything. Use a `getErrorMessage(error: unknown)` utility that duck-types for `.message`.

### Principle 7 — CSS Modules + BEM
- The pattern: `Button.tsx` + `Button.test.tsx` + `Button.module.css` in the same directory — not `.module.css` files in a separate `styles/` directory.
- BEM selectors that reference elements outside their own component's module — this is specificity leaking across component boundaries.
- Dodds: "And for heaven's sake, please DELETE THIS ESLINT RULE" — referring to `no-multi-comp`, the rule preventing multiple components per file.

### Principle 8 — Server Components, Server Actions, tRPC
- In the Next.js App Router, default to Server Components. `use client` is a boundary directive marking where the server→client transition happens; state, functions, and browser APIs require it.
- tRPC for data fetching from Client Components and complex state-driven API interactions that need TanStack Query (caching, polling, invalidation); Server Actions for form mutations and simple data updates benefiting from progressive enhancement and `revalidatePath`/`revalidateTag`.
- Flag: Server Actions used for data fetching (creates non-cacheable POST requests). Flag: tRPC used for simple form submissions where a Server Action would be simpler.
