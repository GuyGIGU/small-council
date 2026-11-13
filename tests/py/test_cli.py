"""The command line of the ported commands, against bin/council's main(): flags, words and refusals."""
import unittest

import support  # noqa: F401  (puts src/ on the path)

from council.commands import cli, home, sharing
from council.records import sharing as setting


class ParseTest(unittest.TestCase):
    def refusal(self, *argv: str) -> str:
        with self.assertRaises(cli.Refusal) as caught:
            cli.parse(list(argv))
        return str(caught.exception)

    def test_flags_and_words_in_any_order(self) -> None:
        args = cli.parse(["--run", "r1", "run", "status", "--all", "--surface=a", "--surface", "b"])
        self.assertEqual(args.words, ["run", "status"])
        self.assertEqual(args.flags, ["run", "all", "surface", "surface"])
        self.assertEqual(args.value("run"), "r1")
        self.assertEqual(args.value("all"), "1")
        self.assertEqual(args.lists["surface"], ["a", "b"])

    def test_after_the_double_dash(self) -> None:
        args = cli.parse(["gate", "x", "--", "echo", "--run"])
        self.assertEqual(args.words, ["gate", "x"])
        self.assertEqual(args.after, ["echo", "--run"])

    def test_glob_words_pass_through(self) -> None:
        self.assertEqual(cli.parse(["changed", "--glob", "*.py", "--each", "--glob=x"]).words,
                         ["changed", "--glob", "*.py", "--each", "--glob=x"])

    def test_refusals_say_what_is_missing(self) -> None:
        self.assertEqual(self.refusal("home", "--run"), "--run needs a folder")
        self.assertEqual(self.refusal("x", "--base"), "--base needs a ref")
        self.assertEqual(self.refusal("x", "--at"), "--at needs grounding or verify")
        self.assertEqual(self.refusal("x", "--task"), "--task needs a value")
        self.assertEqual(self.refusal("x", "--timeout"), "--timeout needs a value")
        self.assertEqual(self.refusal("x", "--run="), "--run needs a value")
        self.assertEqual(self.refusal("x", "--wait="), "--wait needs a value")
        self.assertEqual(self.refusal("x", "--all=1"), "--all takes no value")
        self.assertEqual(self.refusal("x", "--nope"), "unknown option '--nope' — see: council help")
        self.assertEqual(self.refusal("x", "-q"), "unknown option '-q' — see: council help")

    def test_takes_flags_and_no_words(self) -> None:
        args = cli.parse(["run", "status", "--json"])
        with self.assertRaises(cli.Refusal) as caught:
            cli.takes_flags(args, "run status", "all")
        self.assertEqual(str(caught.exception), "run status doesn't take --json — see: council help")
        cli.takes_flags(cli.parse(["home", "--run", "r"]), "home")          # --run is taken everywhere
        with self.assertRaises(cli.Refusal) as caught:
            cli.takes_flags(cli.parse(["home", "--", "x"]), "home")
        self.assertEqual(str(caught.exception), "home takes nothing after -- — see: council help")
        with self.assertRaises(cli.Refusal) as caught:
            cli.no_words("home rule", ["a", "b"])
        self.assertEqual(str(caught.exception), "home rule doesn't take 'a b' — see: council help")


class HomeRuleTest(unittest.TestCase):
    def test_windows_drive_lower_case_no_colon_blanks_kept(self) -> None:
        self.assertEqual(home.rule("C:/Users/Me/My Project/.council"), "Edit(//c/Users/Me/My Project/.council/**)")

    def test_posix_path(self) -> None:
        self.assertEqual(home.rule("/home/me/p/.council"), "Edit(//home/me/p/.council/**)")


BEGIN, END = sharing.NOTE_BEGIN, sharing.NOTE_END


class WithoutBlockTest(unittest.TestCase):
    def test_block_and_one_blank_line_go_line_endings_kept(self) -> None:
        data = b"# Project\r\n\r\n<!-- small-council:begin -->\r\nnote\r\n<!-- small-council:end -->\r\n\r\nmore\r\n"
        self.assertEqual(sharing.without_block(data, BEGIN, END), (sharing.REMOVED, b"# Project\r\n\r\nmore\r\n"))

    def test_only_blank_lines_left(self) -> None:
        data = b"<!-- ultra-council:begin -->\nx\n<!-- ultra-council:end -->\n\n"
        self.assertEqual(sharing.without_block(data, BEGIN, END), (sharing.EMPTIED, b""))

    def test_no_block_and_no_end(self) -> None:
        self.assertEqual(sharing.without_block(b"a\n", BEGIN, END)[0], sharing.NO_BLOCK)
        self.assertEqual(sharing.without_block(b"<!-- small-council:begin -->\na\n", BEGIN, END)[0], sharing.UNENDED)

    def test_a_last_line_without_newline_gets_one(self) -> None:
        data = b"keep\n<!-- small-council:begin -->\n<!-- small-council:end -->"
        self.assertEqual(sharing.without_block(data, BEGIN, END), (sharing.REMOVED, b"keep\n"))

    def test_trailing_blank_before_a_block_at_the_end_goes(self) -> None:
        data = b"keep\n\n<!-- small-council:begin -->\n<!-- small-council:end -->\n"
        self.assertEqual(sharing.without_block(data, BEGIN, END), (sharing.REMOVED, b"keep\n"))


class WithSharingTest(unittest.TestCase):
    def test_replaced_where_it_is(self) -> None:
        data = b"# C\r\n- sharing: team\r\n- sharing: x\r\n"
        self.assertEqual(setting.with_sharing(data, "just me"), b"# C\r\n- sharing: just me\r\n- sharing: x\r\n")

    def test_added_under_run_preferences(self) -> None:
        self.assertEqual(setting.with_sharing(b"## Run preferences\n- a: b\n", "team"),
                         b"## Run preferences\n- sharing: team\n- a: b\n")

    def test_new_section_at_the_end(self) -> None:
        self.assertEqual(setting.with_sharing(b"# C", "team"), b"# C\n\n## Run preferences\n- sharing: team\n")
        self.assertEqual(setting.with_sharing(b"", "team"), b"\n## Run preferences\n- sharing: team\n")


if __name__ == "__main__":
    unittest.main()
