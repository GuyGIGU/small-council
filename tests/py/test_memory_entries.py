"""The memory file's reader (records/memory_entries.py, memory.py) against the bash that stays for the session-start
hook and run open (bin/council's memory_entries and memory_file, until S8b): one file, the same rows."""
from __future__ import annotations

import unittest

import support

from council.records import bytewise, memory, memory_entries

MEMORY = (
    "# Conventions — café\n\n"
    "### AP-0: top of the file is settled\n**Scope:** src/**\n\n"
    "## Accepted Patterns — never re-propose these\n"
    "### AP-1: revoke before lookup\n**Pattern:** revoke first · **Why:** tokens\n**Scope:** src/auth/**, `beck`\n"
    "**Anchor:** src/auth/session.py::revoke\n\n"
    "- **AP-2 — retired flags stay registered.** text\n  **Scope:** council-review\n\n"
    "1. **ap 3 — numbered, lower-case id.** body\n\n"
    "## Enforced Conventions (EC)\n### **EC-1**: a bold id\n**Rule:** always · **Why:** x\n**Scope:** council-plan\n\n"
    "## Observed Failures (F)\n"
    "### F-1: a full observed failure\n**Failure:** the cache went stale\n**Scope:** src/cache/**\n"
    "**Origin:** review 2026-09-26\n**Evidence:** src/cache/x.py:3\n**Verdict:** OBSERVED\n\n"
    "### F-2: a guess is never served\n**Failure:** maybe\n**Scope:** src/**\n**Origin:** x\n"
    "**Evidence:** src/a.py:1\n**Verdict:** INFERRED\n\n"
    "### F-3: no scope\n**Failure:** x\n**Origin:** x\n**Evidence:** x\n**Verdict:** CONFIRMED\n\n"
    "## Proposed\n### F-4: drafted\n**Failure:** x\n\n"
    "## Rejected\n- refuted claim: was F-5\n\n"
    "## Notes\n### D-1: under another heading\n**Scope:** ü/**\n"
    "AP-9 is named here but opens no entry\n"
    "- **AP-10** without a dash or title\n"
)


class SameRowsTest(support.Scratch):
    def bash_rows(self, path: str, skip: bool = False) -> bytes:
        return support.helper_bash(self, 'memory_entries "$1"', path, env={"MEM_SKIP": "1"} if skip else None)[1]

    def assert_same(self, data: bytes) -> None:
        path = self.write("conventions.md", data, binary=True).as_posix()
        python = b"".join(bytewise.bytes_of(row) + b"\n" for row in memory.rows(path))
        self.assertEqual(self.bash_rows(path), python)
        self.assertEqual(self.bash_rows(path, skip=True).rstrip(b"\n"),
                         bytewise.bytes_of(memory_entries.skipped(path)).rstrip(b"\n"))

    def test_one_file_reads_the_same(self) -> None:
        self.assert_same(MEMORY.encode("utf-8"))
        ids = [memory_entries.cells(r)[0] for r in memory.rows((self.tmp / "conventions.md").as_posix())]
        self.assertEqual(ids, ["AP-0", "AP-1", "EC-1", "F-1", "F-2", "F-3", "F-4", "D-1"])

    def test_crlf_and_a_bom_read_the_same(self) -> None:
        self.assert_same(b"\xef\xbb\xbf" + MEMORY.replace("\n", "\r\n").encode("utf-8"))

    def test_a_stray_byte_and_an_empty_file_read_the_same(self) -> None:
        self.assert_same(MEMORY.encode("utf-8").replace(b"caf\xc3\xa9", b"caf\xe9"))
        self.assert_same(b"")


class StatesTest(support.Scratch):
    def states(self) -> dict[str, tuple[str, str]]:
        path = self.write("conventions.md", MEMORY).as_posix()
        return {c[0]: (c[4], c[5]) for c in (memory_entries.cells(r) for r in memory.rows(path))}

    def test_sections_decide_the_state(self) -> None:
        states = self.states()
        self.assertEqual(states["AP-0"][0], "settled")
        self.assertEqual(states["AP-1"][0], "settled")
        self.assertEqual(states["EC-1"][0], "settled")
        self.assertEqual(states["F-1"][0], "observed")
        self.assertEqual(states["F-4"][0], "off")
        self.assertEqual(states["D-1"][0], "unknown")

    def test_an_observed_failure_lacking_a_field_or_a_verdict_is_unknown_with_why(self) -> None:
        states = self.states()
        self.assertEqual(states["F-2"][0], "unknown")
        self.assertIn("failure entry", states["F-2"][1])
        self.assertEqual(states["F-3"][0], "unknown")
        self.assertIn("failure entry", states["F-3"][1])


class LocateTest(support.Scratch):
    def bash_locate(self, home: str) -> list[str]:
        out = support.helper_bash(self, 'memory_file "$1"; printf "%s\\n" "$MEM" "$MEM_CONF" "$MEM_NOTE" '
                                  '"$MEM_ALT" "$MEM_ALT_N"', home)[1]
        return out.decode("utf-8").split("\n")[:5]

    def assert_same(self) -> memory.Located:
        home = (self.tmp / ".council").as_posix()
        found = memory.locate(home)
        self.assertEqual(self.bash_locate(home), [found.path, found.conf, found.note, found.alt,
                                                  str(found.alt_n)])
        return found

    def test_the_default_then_a_root_file(self) -> None:
        self.write(".council/council.config.md", "# Council config\n")
        self.assertTrue(self.assert_same().path.endswith("/.council/conventions.md"))
        self.write("conventions.md", MEMORY)
        self.assertTrue(self.assert_same().path.endswith("/conventions.md"))

    def test_a_configured_path_with_a_note_and_a_second_file(self) -> None:
        self.write(".council/council.config.md", "# c\n## Memory\n- conventions: `docs/My Notes/mem.md` (shared)\n")
        self.write("docs/My Notes/mem.md", MEMORY)
        self.write(".council/conventions.md", MEMORY)
        found = self.assert_same()
        self.assertTrue(found.path.endswith("docs/My Notes/mem.md"))
        self.assertTrue(found.alt.endswith(".council/conventions.md") and found.alt_n > 0)

    def test_a_missing_configured_file_gives_way_and_says_so(self) -> None:
        self.write(".council/council.config.md", "# c\r\n## Memory\r\n- conventions: docs/gone.md — moved\r\n")
        self.write(".council/conventions.md", MEMORY)
        found = self.assert_same()
        self.assertIn("doesn't exist", found.note)


if __name__ == "__main__":
    unittest.main()
