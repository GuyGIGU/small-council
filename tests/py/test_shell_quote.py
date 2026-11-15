"""The pasted-command quoting and the bash a status names, where the old-against-new comparison can't reach:
the quoters' own rule, and the terminal-view command where there is no cygpath (every system but Git Bash)."""
import os
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (puts src/ on the path)

from council.commands import script_cmds, shell


class QuoteTest(unittest.TestCase):
    def test_bin_councils_sh_quote_and_ps_quote(self) -> None:
        self.assertEqual([shell.sh_quote("a'b$c`d"), shell.ps_quote("a'b$c`d")], ["'a'\\''b$c`d'", "'a''b$c`d'"])

    def test_trailing_newlines_go_as_command_substitution_dropped_them(self) -> None:
        self.assertEqual(shell.sh_quote("a\nb\n\n"), "'a\nb'")

    def test_without_cygpath_one_plain_bash_command(self) -> None:
        with mock.patch("shutil.which", return_value=None), mock.patch.dict(os.environ, {"COUNCIL_BASH": "/bin/bash"}):
            self.assertEqual(shell.bash_exe(), "")
            self.assertEqual(shell.helper_bash(), "/bin/bash")
            words = script_cmds.tui_commands(Path("/x/it's"))
        council = script_cmds.where.here(script_cmds.ROOT) + "/bin/council"
        folder = script_cmds.where.here(Path("/x/it's"))
        self.assertEqual(words, ["--tui-command", "bash '%s' tui --watch --run '%s'"
                                 % (council, folder.replace("'", "'\\''"))])


if __name__ == "__main__":
    unittest.main()
