"""The memory file's reader (records/memory_entries.py, memory.py): the rows and paths bin/council's memory_entries
and memory_file gave, written out."""
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


VERDICTS = "OBSERVED, REPRODUCED, CONFIRMED, REFUTED, MISCITED, REGRESSION, INCOMPLETE or SCOPE-CREEP"
ROWS = [  # what bin/council's memory_entries printed for MEMORY: id title scope anchor state section meaning origin
    # evidence verdict
    ("AP-0", "top of the file is settled", "src/**", "-", "settled", "# Conventions — café", "-", "-", "-", "-"),
    ("AP-1", "revoke before lookup", "council-review", "src/auth/session.py::revoke", "settled",
     "## Accepted Patterns — never re-propose these", "revoke first", "-", "-", "-"),
    ("EC-1", "a bold id", "council-plan", "-", "settled", "## Enforced Conventions (EC)", "always", "-", "-", "-"),
    ("F-1", "a full observed failure", "src/cache/**", "-", "observed", "## Observed Failures (F)",
     "the cache went stale", "review 2026-09-26", "src/cache/x.py:3", "OBSERVED"),
    ("F-2", "a guess is never served", "src/**", "-", "unknown",
     "failure entry: its verdict, INFERRED, does not establish a failure (%s)" % VERDICTS, "maybe", "x", "src/a.py:1",
     "INFERRED"),
    ("F-3", "no scope", "-", "-", "unknown", "failure entry: it has no Scope", "x", "x", "x", "CONFIRMED"),
    ("F-4", "drafted", "-", "-", "off", "## Proposed", "x", "-", "-", "-"),
    ("D-1", "under another heading", "ü/**", "-", "unknown", "## Notes", "-", "-", "-", "-")]
SKIPPED = b"AP-2 (line 12)"   # MEM_SKIP=1: the entries the parser could not read


class SameRowsTest(support.Scratch):
    def assert_rows(self, data: bytes, rows: bytes, skipped: bytes = SKIPPED) -> None:
        path = self.write("conventions.md", data, binary=True).as_posix()
        self.assertEqual(b"".join(bytewise.bytes_of(row) + b"\n" for row in memory.rows(path)), rows)
        self.assertEqual(bytewise.bytes_of(memory_entries.skipped(path)).rstrip(b"\n"), skipped)

    def test_one_file_reads_as_the_helper_read_it(self) -> None:
        rows = "".join("\t".join(row) + "\n" for row in ROWS).encode("utf-8")
        self.assert_rows(MEMORY.encode("utf-8"), rows)
        self.assert_rows(b"\xef\xbb\xbf" + MEMORY.replace("\n", "\r\n").encode("utf-8"), rows)
        self.assert_rows(MEMORY.encode("utf-8").replace(b"caf\xc3\xa9", b"caf\xe9"),
                         rows.replace(b"caf\xc3\xa9", b"caf\xe9"))
        self.assert_rows(b"", b"", b"")


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

    def test_a_section_files_by_the_parsers_words(self) -> None:
        said = {name: memory_entries.section(name) for name in (
            "Proposed " + bytewise.EM + " awaiting", "Proposals", "Pending proposals", "Draft", "Declined ideas",
            "Retired", "Decisions (proposed)", "_Proposed_", "Rejected " + bytewise.EM + " never again",
            "Observed Failures (F)", "Observed failures pending review", "Accepted Patterns")}
        self.assertEqual([name for name, word in said.items() if word == "proposed"],
                         ["Proposed " + bytewise.EM + " awaiting", "Proposals"])
        self.assertEqual([name for name, word in said.items() if word == "rejected"],
                         ["Rejected " + bytewise.EM + " never again"])
        self.assertEqual([name for name, word in said.items() if word == "observed"], ["Observed Failures (F)"])

    def test_the_line_tests_an_editor_shares(self) -> None:
        lines = ["# M", "<!-- ### F-1: hidden", "-->", "```", "### F-2: fenced", "```", "####### F-3: seven", "x"]
        self.assertEqual([at for at, _ in memory_entries.visible(lines)], [0, 6, 7])
        self.assertEqual(memory_entries.heading_of("####### F-3: seven "), (7, "F-3: seven"))
        self.assertIsNone(memory_entries.heading_of("#F-3"))
        self.assertEqual([memory_entries.entry_id(t) for t in ("**ap3**: x", "F-6 follow up", "F-6x", "D-15")],
                         ["AP-3", "F-6", "", "D-15"])
        self.assertEqual([memory_entries.cand_id(t) for t in ("F-6 " + bytewise.EM + " x", "F-6 follow up", "f6:")],
                         ["F-6", "", "F-6"])


class LocateTest(support.Scratch):
    """memory.locate: the MEM, MEM_CONF, MEM_NOTE, MEM_ALT and MEM_ALT_N bin/council's memory_file set ({t}: the
    scratch folder)."""

    def assert_found(self, *said: object) -> None:
        found = memory.locate((self.tmp / ".council").as_posix())
        self.assertEqual([found.path, found.conf, found.note, found.alt, found.alt_n],
                         [s.format(t=self.tmp.as_posix()) if isinstance(s, str) else s for s in said])

    def test_the_default_then_a_root_file(self) -> None:
        self.write(".council/council.config.md", "# Council config\n")
        self.assert_found("{t}/.council/conventions.md", "", "", "", 0)
        self.write("conventions.md", MEMORY)
        self.assert_found("{t}/conventions.md", "", "", "", 0)

    def test_a_configured_path_with_a_note_and_a_second_file(self) -> None:
        self.write(".council/council.config.md", "# c\n## Memory\n- conventions: `docs/My Notes/mem.md` (shared)\n")
        self.write("docs/My Notes/mem.md", MEMORY)
        self.write(".council/conventions.md", MEMORY)
        self.assert_found("{t}/docs/My Notes/mem.md", "{t}/docs/My Notes/mem.md", "", "{t}/.council/conventions.md", 8)

    def test_a_missing_configured_file_gives_way_and_says_so(self) -> None:
        self.write(".council/council.config.md", "# c\r\n## Memory\r\n- conventions: docs/gone.md — moved\r\n")
        self.write(".council/conventions.md", MEMORY)
        self.assert_found("{t}/.council/conventions.md", "{t}/docs/gone.md", "the config's memory path, docs/gone.md, "
                          "doesn't exist — reading .council/conventions.md instead", "", 0)


if __name__ == "__main__":
    unittest.main()
