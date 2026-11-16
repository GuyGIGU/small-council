"""council patch's parts: the report head, the diff reader, the removals held against Removed, the workaround
signs, the task's slice and the third-fix-round rule (references/run/builder-report.md)."""
from __future__ import annotations

import unittest

import support

from council import diff
from council.commands import patch_checks, rounds
from council.records import report_head

HEAD = ("# Report — task 2\n\nCause: the lock was released early · state: REPRODUCED\nOwner: src/pay.py\n"
        "Removed: none\nAssumed: nothing\n\nProse the helper never reads. Removed: x\n")

DIFF = """diff --git a/tests/test_pay.py b/tests/test_pay.py
deleted file mode 100644
--- a/tests/test_pay.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def test_once():
-    assert pay() == 1
diff --git a/src/pay.py b/src/pay.py
--- a/src/pay.py
+++ b/src/pay.py
@@ -3,3 +3,4 @@ def pay():
     x = 1
-    assert x == 1
+    assert x >= 1
+++ a line that looks like a header
+    time.sleep(0.5)
diff --git a/docs/rules.md b/docs/rules.md
--- a/docs/rules.md
+++ b/docs/rules.md
@@ -1,3 +1,2 @@
-- Never pay twice.
-- Keep receipts always.
 - Ask first.
diff --git a/docs/more.md b/docs/more.md
new file mode 100644
--- /dev/null
+++ b/docs/more.md
@@ -0,0 +1 @@
+- **Keep receipts always.**
diff --git a/old.png b/new.png
similarity index 100%
rename from old.png
rename to new.png
"""


class HeadTest(support.Scratch):
    def head(self, text: str) -> tuple:
        return report_head.read(self.write("report-2.md", text))

    def test_a_head_after_a_title_is_read_and_the_prose_is_not(self) -> None:
        head, problems = self.head(HEAD)
        self.assertEqual(problems, [])
        self.assertEqual((head.cause, head.state, head.owner, head.removed), (
            "the lock was released early", "REPRODUCED", "src/pay.py", "none"))
        self.assertTrue(head.fix() and head.removed_none())

    def test_cause_none_is_a_first_build(self) -> None:
        head, _ = self.head(HEAD.replace("the lock was released early · state: REPRODUCED", "none — a first build"))
        self.assertFalse(head.fix())

    def test_a_missing_line_an_unread_state_and_a_wrong_order_are_problems(self) -> None:
        self.assertIn("no Assumed: line", self.head(HEAD.replace("Assumed: nothing\n", ""))[1][0])
        self.assertIn("no evidence state", self.head(HEAD.replace("· state: REPRODUCED", ""))[1][0])
        self.assertIn("no evidence state", self.head(HEAD.replace("REPRODUCED", "PROBABLY"))[1][0])
        swapped = HEAD.replace("Owner: src/pay.py\nRemoved: none", "Removed: none\nOwner: src/pay.py")
        self.assertIn("out of order", self.head(swapped)[1][0])
        self.assertIn("isn't there", report_head.read(self.tmp / "none.md")[1][0])

    def test_a_redesign_line_is_kept(self) -> None:
        head, _ = self.head(HEAD.replace("Assumed: nothing\n", "Assumed: nothing\nRedesign: key by id\n"))
        self.assertEqual(head.redesign, "key by id")


class DiffTest(unittest.TestCase):
    def test_files_their_kinds_and_line_numbers(self) -> None:
        found = {file.path: file for file in diff.files(DIFF)}
        self.assertEqual(list(found), ["tests/test_pay.py", "src/pay.py", "docs/rules.md", "docs/more.md", "new.png"])
        self.assertTrue(found["tests/test_pay.py"].deleted and found["docs/more.md"].created)
        self.assertEqual(found["src/pay.py"].removed, [diff.Line(4, "    assert x == 1")])
        self.assertEqual([line.number for line in found["src/pay.py"].added], [4, 5, 6])
        self.assertEqual(found["src/pay.py"].added[1].text, "++ a line that looks like a header")

    def test_a_hunk_header_as_git_writes_it_and_nothing_else(self) -> None:
        self.assertEqual(diff.header("@@ -1,2 +5,3 @@ def f():"), (1, 5, 3))
        self.assertEqual(diff.header("@@ -1 +5 @@"), (1, 5, 1))
        self.assertEqual(diff.header("@@ -1 +05,0 @@"), (1, 5, 0))
        for odd in ("@@ -1 +x @@", "@@ -1 +5,x @@", "@@ -1 +5@@", "@@ -1,2 @@ +7,2", "@@ -1 5 @@",
                    "@@@ -1 -2 +5,3 @@@", "@@\t-1\t+5,3\t@@", "@@  -1  +5,3  @@", "+@@ -1 +5 @@"):
            self.assertIsNone(diff.header(odd), odd)

    def test_a_malformed_header_keeps_the_numbering_in_force(self) -> None:
        text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +7 @@\n+a\n@@ -1 +x @@\n+b\n"
        self.assertEqual([line.number for line in diff.files(text)[0].added], [7, 8])


class ChecksTest(unittest.TestCase):
    def test_removals_a_test_file_an_assertion_and_a_rule_but_not_a_moved_one(self) -> None:
        found = patch_checks.removals(diff.files(DIFF))
        self.assertEqual([(r.kind, r.path, r.line) for r in found], [
            ("test file", "tests/test_pay.py", 1), ("assertion", "src/pay.py", 4), ("rule", "docs/rules.md", 1)])

    def test_unlisted_reads_the_file_or_the_test_name(self) -> None:
        found = patch_checks.removals(diff.files(DIFF))
        self.assertEqual(len(patch_checks.unlisted(found, "none", True)), 3)
        left = patch_checks.unlisted(found, "test_pay.py moved to test_api.py; the rule in docs/rules.md", False)
        self.assertEqual([r.path for r in left], ["src/pay.py"])

    def test_signs_are_listed_from_added_code_lines_only(self) -> None:
        kinds = [(s.kind, s.line) for s in patch_checks.signs(diff.files(DIFF))]
        self.assertEqual(kinds, [("changed expectation", 4), ("sleep", 6)])
        for line, kind in (("    except:", "catch-all"), ("@pytest.mark.skip", "skipped test"),
                           ("for attempt in retry(3):", "retry"), ("timeout=600", "time limit"),
                           ("assert x == approx(1.0)", "looser expectation"), ("} catch (e) {", "catch-all")):
            added = [diff.File("a.py", False, False, [], [diff.Line(1, line)])]
            self.assertIn(kind, [s.kind for s in patch_checks.signs(added)], line)

    def kinds(self, path: str, added: list[str], removed: tuple[str, ...] = ()) -> list[str]:
        lines = [diff.Line(n, text) for n, text in enumerate(added, 1)]
        gone = [diff.Line(n, text) for n, text in enumerate(removed, 1)]
        return [s.kind for s in patch_checks.signs([diff.File(path, False, False, gone, lines)])]

    def test_an_added_line_that_says_it_makes_up_for_something_is_a_sign(self) -> None:
        for line in ("# a workaround for the gateway's double charge", "# Work-around: git 2.30 drops the flag",
                     "use_hack_path = True", "    # hacky, see below", "return [] # for now",
                     "# temporarily off", "x = 1  # until the parser is fixed", "TEMPORARY = True"):
            self.assertEqual(self.kinds("a.py", [line]), ["workaround words"], line)

    def test_ordinary_words_near_a_workaround_word_are_not_signs(self) -> None:
        for line in ("temporary_dir = tempfile.mkdtemp()", "with tempfile.TemporaryDirectory() as root:",
                     "# write a temporary file beside it first", "team = 'hackathon'", "shack = network_around()",
                     "for nowhere in places_seen:", "# loop until the queue is empty", "fixed = until_done()"):
            self.assertEqual(self.kinds("a.py", [line]), [], line)

    def test_an_added_todo_fixme_or_xxx_is_a_sign_and_a_mask_or_a_word_is_not(self) -> None:
        for line in ("# TODO: take this out", "// FIXME the order", "# XXX: wrong on Windows"):
            self.assertEqual(self.kinds("a.js", [line]), ["todo"], line)
        for line in ("todo_items = load()", "STATUS_TODO = 3", "card = 'XXX-XXXX-1234'", "mask = 'XXXX'"):
            self.assertEqual(self.kinds("a.js", [line]), [], line)
        self.assertEqual(self.kinds("a.py", ["# TODO: drop this until the gateway is fixed"]),
                         ["workaround words", "todo"])

    def test_the_two_new_signs_skip_documents_and_removed_lines(self) -> None:
        said = ["- TODO: a workaround for now, until the gateway is fixed", "A temporary hack. FIXME"]
        self.assertEqual(self.kinds("docs/notes.md", said), [])
        self.assertEqual(self.kinds("a.py", ["return gateway(card)"], ("# TODO: a workaround for now",)), [])

    def test_the_slice_and_what_lies_outside_it(self) -> None:
        given = patch_checks.slice_paths(["`src/pay/` — Charge a card", "`tests/test_pay.py:12`, README.md, ./docs"])
        self.assertEqual(given, ["src/pay/", "tests/test_pay.py", "README.md", "docs"])
        self.assertEqual(patch_checks.outside(["src/pay/a.py", "docs/x.md", "README.md", "src/mail.py"], given),
                         ["src/mail.py"])
        self.assertEqual(patch_checks.slice_paths(["`a/b.py`", "`a/b.py`, `c.md`", "a/b.py:3"]), ["a/b.py", "c.md"])


class ThirdRoundTest(support.Scratch):
    def test_a_third_fix_round_in_the_same_files_is_refused_and_another_file_is_not(self) -> None:
        run = self.run_folder("2026-01-02-030405-council-implement")
        earlier = [(["a.py"], "", "2026-01-02T03:05:00Z"), (["a.py", "b.py"], "", "2026-01-02T03:06:00Z"),
                   (["a.py"], "", "2026-01-02T03:07:00Z")]
        self.assertIsNone(rounds.third_fix_round(run, 1, earlier[:2], ["a.py"], ""))
        self.assertIn("third fix round", rounds.third_fix_round(run, 1, earlier, ["a.py"], "") or "")
        self.assertIsNone(rounds.third_fix_round(run, 1, earlier, ["c.py"], ""))
        renewed = earlier[:2] + [(["a.py"], "key by id", "2026-01-02T03:07:00Z")]
        self.assertIsNone(rounds.third_fix_round(run, 1, renewed + [(["a.py"], "", "x")], ["a.py"], ""))


if __name__ == "__main__":
    unittest.main()
