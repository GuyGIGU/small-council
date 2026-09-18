# Guardrails — the checks a project needs before any green report means anything

Read this at council-init's Phase C, and at a refresh. A council report is only as honest as the
commands behind it: with no gate configured, `council gate --all` says **NOTHING WAS CHECKED** and
exits 4, because a green report with nothing behind it is worse than no report.

The job here is the one a senior engineer does on day one: find what the project is missing, say in one
plain line what each missing check would catch, and — only on a yes — have it fitted.

## The five

| Check | What it catches, in plain words | If it's missing |
|---|---|---|
| **Formatter** | arguments about layout; diffs full of whitespace noise | reviews waste seats on style |
| **Linter** | unused variables and imports, shadowed names, unreachable and dead code, obvious foot-guns | exactly the "spaghetti" a user can't see |
| **Type check** | a value used as the wrong kind of thing; a call with the wrong arguments; a rename that missed a caller | breakage that only shows up when a user hits it |
| **Test runner** | behaviour that used to work and doesn't any more | nothing to prove a fix, and nothing to stop a bug coming back |
| **Dependency audit** | a package with a published security hole, or one abandoned years ago | a loophole nobody in the project wrote |

The first four are the project's own tools. The audit is the one check that reaches the network; it
belongs in the Gates table with `Side effects: network`, which `council gate --all` runs unasked, while
anything needing credentials or money still doesn't.

## The ratchet — `council changed`

Fitting a linter to an existing project whole-tree prints hundreds of complaints about code that was
already there, and the predictable result is that it gets switched off in week one. So a **newly
fitted** lint, format or type gate runs through the helper:

```
council changed --glob '*.py' -- ruff check
```

- It collects the files this change touches — **committed on this branch, staged, unstaged, and new
  files git doesn't track yet** — so it sees the code the council just wrote, before any commit.
- No files matched → it says so and exits 0. That is a pass, not a skip.
- Paths with spaces and unicode are passed through as single arguments; deleted and renamed-away files
  are dropped, so the tool is never handed a path that no longer exists.
- `--each` runs the tool once per file, for tools that only read their first argument (`bash -n`).
- Patterns are git pathspecs: `'*.{js,jsx}'` is spelled out as both, case matters, and a pattern with
  a `/` in it is anchored at the repo root — `'src/*.js'` covers every folder under a top-level
  `src/`, but not `web/src/`. A pattern that matches no file in the project is an error, not a pass
  forever.
- `--base <ref>` overrides the branch point; by default it is the merge-base with the default branch,
  and on a repo with no other branch, everything uncommitted.
- It is a plain command with no pipe, so it survives being written into a Gates table cell.

A whole-project type checker (`tsc`, `phpstan`, `srb`, or a compiler) is **never** ratcheted: handing it
a file list makes it ignore the project's own config and report errors that aren't real. Those rows run
over the project, as they always did.

Enter a ratcheted gate with **Mandatory: no** at first: green on day one, and it can only get stricter.
Count the pre-existing problems once — run the tool over the whole tree by hand — and write the number
in the config's `## Notes` as `N problems that were already here — not yours`. Never as a task list,
and never as something the next build must fix. A check the project already had keeps its own scope;
the ratchet is only for what the council fits.

## By stack — the command, never a pinned version

Pick the row the stack detection matched. If the project already has one of these, keep the project's
own invocation (an npm script, a Makefile target, a task runner) and only fill the gaps. `<c>` is
shorthand for the ratchet prefix `council changed --glob '<the stack's glob>' --`.

| Stack | Formatter | Linter | Type check | Test runner | Dependency audit |
|---|---|---|---|---|---|
| Node / TypeScript | `<c> npx prettier --check` | `<c> npx eslint --max-warnings=0` | `npx tsc --noEmit` | `npm test` | `npm audit --audit-level=high` |
| Node / JavaScript | `<c> npx prettier --check` | `<c> npx eslint --max-warnings=0` | `npx tsc --noEmit --allowJs --checkJs` (opt-in) | `npm test` | `npm audit --audit-level=high` |
| Python | `<c> ruff format --check` | `<c> ruff check` | `<c> mypy` | `pytest -q` | `pip-audit` |
| Go | `test -z "$(gofmt -l .)"` — `gofmt -l` prints names but always exits 0 | `go vet ./...` | the compiler: `go build ./...` | `go test ./...` | `govulncheck ./...` |
| Rust | `cargo fmt --check` | `cargo clippy --all-targets -- -D warnings` | the compiler: `cargo check` | `cargo test` | `cargo audit` |
| C# / .NET | `dotnet format --verify-no-changes` | `dotnet build -warnaserror` | the compiler: `dotnet build` | `dotnet test` | see **the .NET audit** below — the plain command exits 0 with vulnerable packages listed |
| Java (Maven) | `mvn -q spotless:check` | `mvn -q com.github.spotbugs:spotbugs-maven-plugin:check` | the compiler: `mvn -q compile` | `mvn test` | `mvn -DfailBuildOnCVSS=7 org.owasp:dependency-check-maven:check` |
| Java (Gradle) | `./gradlew spotlessCheck` | `./gradlew spotbugsMain` | the compiler: `./gradlew compileJava` | `./gradlew test` | `./gradlew dependencyCheckAnalyze` with `failBuildOnCVSS = 7f` |
| Ruby | `<c> bundle exec rubocop --only Layout` | `<c> bundle exec rubocop` | `bundle exec srb tc` (Sorbet, opt-in) | `bundle exec rspec` | `bundle exec bundle-audit check --update` |
| PHP | `<c> vendor/bin/php-cs-fixer fix --dry-run --diff` | — PHPStan is the type check; don't fit it twice | `vendor/bin/phpstan analyse` (raise the level over time) | `vendor/bin/phpunit` | `composer audit` |
| Swift | `<c> swift format lint --strict` | `<c> swiftlint lint --strict` | the compiler: `swift build` | `swift test` | — none exists; say so rather than fitting a green one |
| Godot (GDScript) | `<c> gdformat --check` | `<c> gdlint` | `council changed --glob '*.gd' --each -- godot --headless --check-only --script` | `godot --headless -s addons/gut/gut_cmdln.gd -gexit` | — add-ons are vendored; read `addons/` versions by hand |
| Unity (C#) | `dotnet format --verify-no-changes` | analyzers via the batchmode build | the compiler: Unity batchmode build | `-runTests -testPlatform EditMode -batchmode -nographics` | see **the .NET audit** below |
| C / C++ (CMake) | `<c> clang-format --dry-run --Werror` | `<c> clang-tidy -p build --warnings-as-errors='*'` | the compiler: `cmake --build build` | `ctest --test-dir build` | — system packages; read the lockfile by hand |
| Shell | `<c> shfmt -d` | `<c> shellcheck` | `council changed --glob '*.sh' --each -- bash -n` | `bats tests/` | — |

**The .NET audit** needs a wrapper, because `dotnet list package --vulnerable` exits 0 even when it
lists vulnerable packages:

```
out=$(dotnet list package --vulnerable --include-transitive); printf '%s\n' "$out"; case "$out" in *"has the following vulnerable"*) exit 1 ;; esac
```

**Tools that must be declared before they exist.** Spotless, SpotBugs, PMD and dependency-check are
Maven/Gradle plugins: until the plugin is declared in `pom.xml` / `build.gradle`, `mvn spotless:check`
fails with "No plugin found for prefix" and `./gradlew check -x test` silently passes without linting
anything. Declaring the plugin is part of the fitting task, not a footnote. `clang-tidy` likewise needs
`compile_commands.json` (`cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`), and OWASP dependency-check wants
an NVD API key — without one the first run is rate-limited into hours, so record `Needs: NVD API key`
and let `council gate --all` skip it rather than hang.

A stack not in this table gets the same five questions asked of its own ecosystem. Never invent a tool:
if the ecosystem has no type checker or no audit, the cell is "—" and the report says so rather than
fitting a command that can only pass.

## Every fitted gate is proved both ways

A gate that cannot fail is worse than no gate. Before a guardrails task is done, run it twice:

1. **On a deliberate violation** — an unformatted line, an unused import, a wrong type, a failing
   assertion — and watch it exit non-zero.
2. **With the violation removed** — and watch it exit 0.

A failing gate must exit with a code from 1 to 255. A runner that exits with its failure count (or a
raw Windows error code) reads as a pass when that number is a multiple of 256, because only the low 8
bits reach the helper — have it exit 1 on any failure.

Record both in the task's evidence. That is also the task's before-and-after proof: the before-check is
the tool run over the violation, never the ratchet on a clean tree (which exits 0 by design and would
be a before-check that never failed — `council check` calls that broken proof).

## Fitting them — a plan, not a side effect

council-init never installs anything itself: it writes `<home>/plans/guardrails.md` in council-plan's
task format — one task per missing check — and offers council-implement. Each install then gets
before-and-after evidence, a blind verifier and a log row, like any other build.

```
#### 1. Fit the linter (ruff)
| | |
|---|---|
| **Domain** | Guardrails (the project's own tools) × Carmack — verify by machine, not by feel |
| **Ref** | `references/guardrails.md` |
| **Depends on** | — |
| **Touches** | `pyproject.toml`, `.council/council.config.md` (Gates) |
| **Constraints** | "<any hard rule that binds this — a dependency policy, a pinned toolchain — quoted with its source>"; or — |
| **Done when** | `council changed --glob '*.py' -- ruff check` exits non-zero on a file with an unused import, and 0 once it's removed; the Gates row records **Run at** (grounding, verify), **Mandatory**, Probe, Needs and Side effects |
```

Order them cheapest-first: formatter, linter, type check, dependency audit, and the test runner last.

## The test runner, honestly

The first four cost no new code. A test runner is the exception: it means writing a test, and a weak
smoke test with a green tick is exactly the theatre `references/quality-testing.md` warns about. So:

- fit the runner plus **one** smoke test that proves the thing starts and does its most basic job;
- that task goes through the verifier like any other;
- and the report says what it is worth, in these words: *"your suite has 1 test; it proves the app
  starts and nothing else"* — never "tests: pass".

From then on the suite grows the honest way: every bug fixed leaves behind the test that caught it.

## What this never does

- No pinned versions, no new config file for the user to maintain, no CI service, no paid tool, no
  account, no token.
- No commit hook: a blocked commit a non-coder can't read is worse than an unchecked one.
- No coverage threshold: a suite at 90% of mock theatre reads greener than an honest one at 30%.
- Nothing is installed, and no file is written, before the user says yes.
