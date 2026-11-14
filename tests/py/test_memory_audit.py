"""What the memory's anchors name (records/memory_anchors.py), the support behind each observed failure
(records/memory_audit.py), and the one guarded way to rewrite the memory file (records/memory.py)."""
from __future__ import annotations

import shutil
import unittest

import support

from council.records import memory, memory_anchors, memory_audit, memory_entries

FAILURE = ("### {id}: {title}\n**Failure:** x\n**Scope:** {scope}\n**Origin:** r\n**Evidence:** {evidence}\n"
           "**Verdict:** OBSERVED\n")
MEMORY = ("# M\n## Accepted Patterns\n### AP-1: revoke\n**Pattern:** x\n"
          "**Anchor:** src/a.py::revoke, src/gone.py:3, NoSuchName\n## Observed Failures\n"
          + FAILURE.format(id="F-1", title="seen", scope="src/**", evidence="src/a.py:1")
          + FAILURE.format(id="F-2", title="gone evidence", scope="src/**", evidence="src/missing.py:9")
          + FAILURE.format(id="F-3", title="far lines", scope="src/**", evidence="src/a.py:40-44")
          + "## Proposed\n")


class MemoryTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.write("src/a.py", "def revoke():\n    pass\n")
        self.top = self.tmp.as_posix()
        self.home = self.top + "/.council"
        self.mem = self.write(".council/conventions.md", MEMORY).as_posix()

    def copy(self, name: str, text: str | None = None) -> str:
        path = self.home + "/" + name
        if text is None:
            shutil.copyfile(self.mem, path)
        else:
            self.write(".council/" + name, text)
        return path


class AnchorsTest(MemoryTest):
    def test_each_anchor_piece_is_one_row(self) -> None:
        self.assertEqual(memory_anchors.rows(memory.rows(self.mem)), [
            "AP-1\tsrc/a.py::revoke\tF\tsrc/a.py", "AP-1\tsrc/a.py::revoke\tN\tsrc/a.py\trevoke",
            "AP-1\tsrc/gone.py:3\tC\tsrc/gone.py\t3", "AP-1\tNoSuchName\tS\tNoSuchName"])

    def test_read_fields_as_bash_read_splits(self) -> None:
        self.assertEqual(memory_anchors.read_fields("\ta\t\tb\tc d\t", 2), ["a", "b\tc d"])
        self.assertEqual(memory_anchors.read_fields("x", 3), ["x", "", ""])


class AuditTest(MemoryTest):
    def test_missing_evidence_and_lines_past_the_end_are_fatal(self) -> None:
        said = memory_audit.audit(memory.rows(self.mem), self.home, self.top, self.mem)
        self.assertIn("F-2\tnote\tevidence src/missing.py:9 can't be found in this project", said)
        self.assertIn("F-3\tnote\tevidence src/a.py:40-44: the file has 2 line(s), not 40-44", said)
        self.assertEqual(sorted(line.split("\t")[0] for line in said if "\tfatal\t" in line), ["F-2", "F-3"])

    def test_served_turns_an_unsupported_failure_unknown(self) -> None:
        found = memory.rows(self.mem)
        served = {c[0]: c for c in map(memory_entries.cells, memory.served(found, memory_audit.audit(
            found, self.home, self.top, self.mem)))}
        self.assertEqual(served["F-1"][4], "observed")
        self.assertEqual((served["F-2"][4], served["F-2"][5]),
                         ("unknown", "failure entry: none of its evidence can be found and read as cited"))
        self.assertEqual(memory.would_serve(self.mem, "F-1", self.home, self.top, self.mem), "")
        self.assertIn("none of its evidence", memory.would_serve(self.mem, "F-2", self.home, self.top, self.mem))

    def test_spans_and_verdict_words(self) -> None:
        self.assertEqual([memory_audit.span(s) for s in ("12", "40-44", "0", "1234567890")],
                         [(12, 12), (40, 44), None, None])
        self.assertTrue(memory_audit.says("was REFUTED here", "REFUTED"))
        self.assertFalse(memory_audit.says("refuted", "REFUTED"))

    def test_a_shared_id_is_said_loud(self) -> None:
        self.write(".council/conventions.md", MEMORY + FAILURE.format(id="F-1", title="again", scope="src/x/**",
                                                                      evidence="src/a.py:2"))
        self.assertIn("gives one id to more than one entry: F-1", " ".join(memory.unread(self.mem)))
        self.assertEqual(memory.absolute("/r", "x/y.md"), "/r/x/y.md")
        self.assertEqual(memory.absolute("/r", "./a.md"), "/r/a.md")


class ReplaceTest(MemoryTest):
    def test_a_proposal_lands_under_proposed_alone(self) -> None:
        before = self.copy("before.md")
        after = self.copy("after.md", MEMORY + "### F-4: drafted\n**Failure:** x\n")
        self.assertEqual(memory.replace(self.mem, before, after, "F-4", "proposed", self.home, self.top), "")
        self.assertIn("### F-4: drafted", support.Path(self.mem).read_text(encoding="utf-8"))

    def test_an_edit_that_touches_another_entry_writes_nothing(self) -> None:
        before = self.copy("before.md")
        after = self.copy("after.md", MEMORY.replace("**Pattern:** x", "**Pattern:** y") + "### F-4: d\n")
        self.assertEqual(memory.replace(self.mem, before, after, "F-4", "proposed", self.home, self.top),
                         "the edit would change other memory entries too — nothing written")
        self.assertEqual(support.Path(self.mem).read_text(encoding="utf-8"), MEMORY)

    def test_an_unsupported_failure_is_never_accepted(self) -> None:
        before = self.copy("before.md")
        after = self.copy("after.md", MEMORY.replace("src/missing.py:9", "src/also-missing.py:9"))
        said = memory.replace(self.mem, before, after, "F-2", "observed", self.home, self.top)
        self.assertTrue(said.startswith("F-2 would not be served (none of its evidence"), said)

    def test_a_file_changed_since_the_copy_writes_nothing(self) -> None:
        before = self.copy("before.md")
        after = self.copy("after.md", MEMORY + "### F-4: drafted\n")
        self.write(".council/conventions.md", MEMORY + "\n")
        said = memory.replace(self.mem, before, after, "F-4", "proposed", self.home, self.top)
        self.assertIn("changed while this ran — nothing written", said)


if __name__ == "__main__":
    unittest.main()
