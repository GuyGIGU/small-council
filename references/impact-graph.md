# Impact graph v1

`council index` still writes the human-readable `index.md`. When Python 3.8+ is available, it also
writes a run-local `impact.tsv` from the same saved Git baseline. `council impact` refreshes that
file after the working tree changes. Neither command edits project code or chooses seats. If the
optional provider is unavailable or fails, the existing index remains valid and the helper says
the graph was not refreshed. It removes any prior generated graph for that run so an old one is
not mistaken for current evidence.

The graph separates files that **changed** from files that **directly depend on a changed path**.
It is evidence for the Chair's scope, seat and verification decisions, not a claim of complete
coverage. The Chair still checks the actual code, roster Surface markers and tests. Phase 5 can
use these relationships for progressive context, but Phase 4 does not dispatch or trim context.

## Contract

The UTF-8 TSV has exactly six columns:

```text
kind	source	target	relation	evidence	confidence
```

The first data row is `schema / impact / 1 / version`. Rows are sorted for reproducibility. A
literal tab, newline, carriage return or backslash inside a cell is escaped as `\t`, `\n`, `\r`
or `\\`; other control bytes are escaped as `\xNN`. `-` means not applicable. Consumers should
decode escapes before interpreting a path.

| Kind | Source → target | Meaning |
|---|---|---|
| `change` | changed path → former path or `-` | Git status `A`, `M`, `D`, `R`, `C` or `?`; evidence names committed, staged, unstaged or untracked provenance. |
| `symbol` | changed path → definition name | A Python AST definition touched by changed lines, or a nearby JS/TS declaration; the provider is named in evidence. |
| `dependency` | importer → imported path | A resolved, direct static import involving a changed path. |
| `impact` | changed or former path → importer | A direct reverse dependency. `former-path-importer` means a consumer still names a renamed path. |
| `test` | changed path → likely test | `direct-import` has resolved import evidence; `name-match` is only a low-confidence filename hint. |
| `surface` | changed path → domain | Low-confidence path/extension hint: configuration, persistent data, security, frontend or public interface. |
| `limit` | scan or path → reason | Explicitly records files omitted or a provider that could not inspect a file. |

`high` confidence means Git or Python AST evidence was observed, **not** that the dependent code
executes at runtime or a test covers the behavior. `medium` is used for JS/TS lexical import and declaration hints;
`low` is used for path and filename heuristics. A missing row is never proof of no impact.

## Providers and bounds

The Git provider combines the index baseline with the current working tree, including committed,
staged, unstaged, untracked, renamed and deleted paths. The Python provider uses the standard
library AST for static `import` and `from` statements, including relative imports and common
`src/` layouts (exact package paths take precedence over `src/` aliases). The JS/TS provider
resolves literal relative `import`, `export from`, `require` and `import()` paths; it does not run
a compiler or resolve package aliases. Both follow direct links only. Imports of deleted files
and former rename paths remain visible when a consumer still uses them. Nonliteral dynamic
imports, multi-hop re-exports, runtime dispatch, generated code and actual test coverage are
not inferred.

Scanning is bounded to 2,000 source files, 64 MiB total and 512 KiB per file, with changed files
considered first. Definition extraction and filename test hints consider at most 200 changed files
each. `limit` rows disclose truncation, large/binary files and Python syntax errors.
Source-file symlinks are not followed; a changed symlink remains in the Git delta, but its target
is not read by the provider.
The graph is deliberately a lightweight run artifact rather than a persistent repository-wide
database. It never runs project code or installs a parser. Python itself is optional to Small
Council: the Bash/Git change index is the fallback on hosts without Python 3.8+.
