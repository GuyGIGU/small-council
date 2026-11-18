# Untrusted Input Reference — Carmack × Patterson

Philosophy: John Carmack. Specifics: Meredith L. Patterson, co-founder with Sergey Bratus and Len Sassaman of language-theoretic security (LangSec). This seat guards the code that first touches outside bytes, where one malformed input becomes a crash, memory corruption, a wrong result or an attacker's foothold. LangSec's core idea: every accepted format is a language, and code that acts on input before recognising all of it is where exploits live.

The Carmack filter here is reachability: a finding names the boundary, who controls the bytes beyond it (a stranger on the network, someone sharing a save file, a failing disk) and what one malformed input does. A parser for a file only the app writes must still fail cleanly, but it is rarely a P1.

## When this seat applies

Any parser, decoder, loader or handler for bytes that cross one of the boundaries in Principle 2; the more of it is hand-written, the more the seat earns its place. Example surface markers, rewritten in the repo's idioms:

- **Web or backend:** `**/handlers/**`, `multipart`, `yaml.load`, `pickle`, `extractall`
- **Native mobile:** `onNewIntent`, `openURL`, `ContentProvider`, `NSKeyedUnarchiver`
- **Desktop:** `**/import/**`, URL-scheme handlers, `QDataStream`, drop handlers
- **Game:** `**/save*/**`, `**/mods/**`, `*.pak`, `LoadGame`, packet handlers
- **Embedded:** `rx_buf`, `uart`, `ota`, `memcpy(`, frame decoders
- **CLI or library:** `argv`, `getenv`, `**/parse*`, `**/decode*`

Drop it only when every outside input goes through mature libraries with nothing hand-written around them. With a thin slice (a couple of handlers, one loader), pair it with Security in one worker.

## Applying this seat to another stack

- **Web and backend:** bodies, headers, uploads, webhooks, queue payloads, third-party responses; Principles 1, 3 and 7 weigh most.
- **Mobile:** deep links, intents from other apps, push payloads, shared-in files, WebView bridges.
- **Desktop:** opened documents, URL schemes, drag-and-drop, clipboard, plugins, local IPC.
- **CLI:** arguments, environment, stdin, config, text echoed to a terminal, argument injection when shelling out.
- **Embedded:** radio, serial and bus frames, OTA images; in memory-unsafe code Principles 3 and 9 dominate.
- **Games:** saves, replays, mods, maps and multiplayer packets; console jailbreaks have shipped as crafted saves.
- **Ownership:** Security (Hunt) owns who can reach an input (auth, access control, secrets, dependencies) and the attack surface as a whole; this seat owns what the code does with the bytes once they arrive. Injection into an interpreter (SQL, shell command strings, HTML, templates) stays Security's (security.md Principle 1) whenever Hunt has a worker; this seat covers it only when paired with Security or when Security isn't seated. This seat owns archive entry names, paths from parsed input, argument injection, terminal escapes, deserialisation and parse-at-the-boundary design. The LLM seat (Willison) owns prompt injection and model output inside an LLM pipeline; with one on the roster, model output is its lens. With a small input surface, pair this seat with Security in one worker.

## Principle 1: Define the input language, then recognise all of it before acting

Every format is a language, written down or not. Write it down (a schema, a grammar, a layout with its constraints), parse input against it at the boundary into a typed value, and reject whatever doesn't parse: Alexis King's "parse, don't validate". The failure it prevents is what LangSec calls shotgun parsing, checks scattered through processing code where one missed check is a bug.

### What to check

- Raw input deep in business logic: `body["amount"]` read three calls in, a C handler indexing `rx_buf` in five places.
- A validator that returns a boolean and passes the unparsed original on, so checked and used values can diverge.
- Side effects before recognition: an import that commits record 1 before record 50 is found malformed.
- An input language more powerful than needed (expressions, templates or script hooks where a fixed structure would do), or a hand-rolled parser where a mature, fuzzed one exists.

### What not to flag

- Re-validation between already-parsed, typed values inside the program.
- Documented leniency written into the grammar.

## Principle 2: Every boundary is a trust boundary — name them

Bytes enter through the network, files, IPC, environment, arguments, clipboard, devices, other processes and model output. Data isn't trusted because it came from disk, a cache, a queue or "our own" service: each can be corrupted, replayed, written by an older version, or controlled by whoever owns the neighbour. Ask who can write the bytes, not who usually does.

### What to check

- "Internal" payloads trusted blind: a queue consumer that trusts any message, a service trusting a gateway header while reachable around the gateway.
- The app's own files read back unchecked; saves, caches and settings get edited, corrupted and written by older versions.
- Results the client computes that the server should: a checkout price, a score or hit in a multiplayer packet.
- Update or firmware images parsed before their signature is checked.

### What not to flag

- Values that never leave one process or get serialised.
- Build-time inputs reviewed like code, unless untrusted people can change them.

## Principle 3: Lengths, counts, offsets and depths come from the attacker

A length prefix, element count, offset, nesting depth, image dimension or decompressed size read from input is a claim. Check it against a limit you chose and against the bytes actually present before you allocate, index, copy, loop or recurse, and do the arithmetic with overflow in mind.

### What to check

- Allocation sized by an uncapped field, or by `count * size` that can overflow and under-allocate.
- Offsets and lengths used to index or copy without a bounds check: memory corruption in C, C++ and unsafe blocks.
- Expansion bombs: archives, compressed streams, huge declared image sizes, XML entity expansion. Cap output, not only input.
- Recursion with no depth limit, regexes that backtrack catastrophically on attacker text, and no caps on body size, field count or archive entries.

### What not to flag

- Generous but present limits, unless they can exhaust real memory on the target hardware.
- Bounds enforced by a layer you can point to, such as a proxy's body limit.

## Principle 4: Normalise once, then compare only normalised values

Text and paths have many spellings: Unicode forms, look-alike characters, case, percent-encoding, `..` segments, symlinks, Windows short names. Decode and normalise exactly once at the boundary, then check, compare and store only the canonical form. Checking one form and using another, or decoding twice, is how filters get bypassed.

### What to check

- A check on the raw form and use of the decoded one: an allowlist tested before URL-decoding or Unicode normalisation.
- Double decoding: `%252e%252e%252f` decodes to `%2e%2e%2f`, then to `../`.
- Locale-sensitive case folding (the Turkish dotless i); un-normalised names that let look-alikes become separate accounts.
- Text decoded with the platform's default encoding; CR and LF passed into headers or log lines.

### What not to flag

- Display-only text never compared, used as a key or passed to a sink.
- Framework normalisation at the boundary, if nothing downstream decodes again.

## Principle 5: Paths, names and fragments are data, never code

A string built from input and handed to the filesystem, a shell, SQL, a template engine, HTML or a terminal goes through an API that takes it as an argument, never through concatenation. For files, resolve the final path and prove it lies under the intended root before opening it.

### What to check

- Archive extraction that joins entry names onto the target without checking the resolved path ("zip slip"), including symlink entries; Python's `tarfile` extraction without `filter='data'` on 3.13 or earlier (3.14 defaults to `'data'`), or with `filter='fully_trusted'` on any version.
- Paths from user-supplied names, symlinks followed out of a sandbox, check-then-open races.
- Shell strings, queries or markup built by string formatting instead of argument lists, parameters or auto-escaping; input starting with `-` passed to a tool without `--`.
- Windows traps (device names like `CON` and `NUL`, alternate data streams, UNC paths) and raw escape sequences written to a terminal.

### What not to flag

- Paths and commands built only from constants and values the program generated.
- Interpolation of constants or enum values from code.

## Principle 6: Deserialising untrusted data must never let the data choose the types

A deserialiser that reads a type name from its input lets the input choose which code runs. Native object serialisers (Python's pickle, Java serialisation, .NET's BinaryFormatter, PHP's unserialize, Ruby's Marshal) and YAML loaders that build arbitrary objects are unsafe on untrusted data by design. Use a data-only format mapped onto types the code picks.

### What to check

- Native serialisers across a boundary: pickle in a shared cache or a downloaded model checkpoint, BinaryFormatter for shared game saves.
- YAML loaded with an object-constructing loader; in PyYAML, use `safe_load` or `SafeLoader` for anything untrusted.
- Polymorphic JSON driven by a type field: Jackson `enableDefaultTyping`, or `activateDefaultTyping` with `LaissezFaireSubTypeValidator`; Json.NET `TypeNameHandling` other than `None` with no `SerializationBinder`.
- Apple's `NSKeyedUnarchiver` without secure coding; serialised objects round-tripped through cookies or client storage.

### What not to flag

- Native serialisation inside one trust domain, with no other writer.
- Data-only formats that happen to be called deserialisation (JSON into a plain struct).
- Polymorphism limited to an allowlist the code controls (a restrictive Jackson validator, a Json.NET binder that rejects unexpected types, `NSKeyedUnarchiver` with secure coding and explicit classes).

## Principle 7: Two parsers, two answers — share one parser

When two components parse the same input (proxy and app, validator and consumer, signature checker and loader, old and new version), any input they read differently lets one side approve what the other executes. Parse once and pass the parsed value on, or share one parser with one configuration.

### What to check

- Checked with one parser, used with another: a URL matched by regex and fetched by the HTTP client.
- Framing disagreements between hops, such as HTTP request smuggling over Content-Length versus Transfer-Encoding.
- Ambiguities parsers resolve differently: duplicate JSON keys, repeated headers, two archive entries with one name where the verifier checks one and the loader uses the other.
- A signature covering one region while the loader reads beyond it; a writer and reader for one format maintained separately.

### What not to flag

- Disagreements that only change display or logging.
- Re-parsing a canonical form the first parser produced.

## Principle 8: Fail closed and loud

Malformed input is rejected with a clear error and nothing downstream runs. "Repairing" it (truncating, skipping bad records, guessing values, carrying on after a failed signature) turns an attack or a corruption into silently wrong state far from its cause.

### What to check

- Parse errors swallowed: an import that skips bad records uncounted; a save loader that returns fresh state and then overwrites the real save.
- Silent coercion: truncation, `"yes"` read as true, unknown fields dropped where the format should reject them.
- Verification that logs a warning and continues.
- A "legacy" path that accepts old formats with none of the new checks.

### What not to flag

- Versioned formats that skip unknown optional fields by design while checking every known one.
- Normalisation done once before parsing (Principle 4).

## Principle 9: Fuzz what you hand-wrote

Every hand-written parser, decoder, format reader and protocol handler gets a fuzzer or property tests: the inputs that break parsers are the ones nobody writes as examples. Cheap, high-yield properties are round-trip equality and "never crashes, hangs or allocates past the limit". Seed the corpus with real files and every input that ever caused a bug.

### What to check

- Custom parsers tested only on well-formed examples.
- A fixed parser bug with no regression test holding its input.
- Fuzzers that don't run in CI or on a schedule, or memory-unsafe code fuzzed without AddressSanitizer or UndefinedBehaviorSanitizer.
- The ecosystem's tool unused where cheap: libFuzzer or AFL++ (C, C++), `go test -fuzz`, cargo-fuzz, Atheris (Python), Jazzer (JVM); Hypothesis, fast-check or proptest for properties.

### What not to flag

- Parsing delegated to a mature, widely fuzzed library, unless the glue does real work.
- Parsers that only read the project's own build-time assets.

## Know your gaps

- Signature and key soundness is Security's call; this seat checks only that verification precedes parsing and fails closed.
- Designing a new format (a grammar, the least powerful language that does the job) is design work, not review.
- Rate limits and fleet-level denial of service belong to Security and Operability; this seat covers what one input costs.

## Quick Reference: Severity Guide

- **P1 — Fix now:** attacker-reachable input that yields code execution, memory corruption, writes outside the target, data loss or a crash-on-demand of a shared service. Pickle on shared data, argument injection, an archive entry written outside the target (zip slip, including `tarfile` extracted without the `'data'` filter), an unchecked length used to copy in C, a fail-open signature check, a save loader that overwrites progress after a parse error.
- **P2 — Fix soon:** one mistake from P1, or silently corrupting. Validation separate from use, no size or depth limits on a reachable parser, double decoding, silent repair, an unfuzzed hand-written parser, "internal" payloads trusted blind.
- **P3 — Consider:** hygiene. No written grammar for a custom format, errors that don't say what was wrong, unexplained limits, a fuzzer with no regression corpus.

## The Overriding Filter

Name the boundary, who controls the bytes beyond it, and the one malformed input that breaks the code; if you can't name all three, it's pattern-matching. If you can, ask Carmack's question: a real problem in this codebase at this scale? A crafted file that only crashes its own user's session is minor; on a shared server, or in a file people download and open, it is not.
