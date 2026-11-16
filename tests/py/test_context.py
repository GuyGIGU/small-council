"""council context build's task pack: the shared task-number word, the parts it builds from a plan task and the map,
the config's hard rules, and the ceiling — whole parts dropped from the end, named under Left out, and the last
line counting the printed bytes."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import support

from council.commands import context, task_slice
from council.records import config, patches, tasks
from council.records import home as where
from test_plan_tasks import MAP, plan, task


def printed(lines: list[str]) -> int:
    return len("".join(line + "\n" for line in lines).encode("utf-8"))


class NumberTest(unittest.TestCase):
    def test_a_task_is_named_by_its_number_alone_or_after_t_or_task(self) -> None:
        for word in ("3", "T3", "t3", "task-3", "Task3", "task3", "003"):
            self.assertEqual(tasks.number(word), 3, word)
        for word in ("x", "task 3", "T3a", "-3", "", "T", "task-"):
            self.assertIsNone(tasks.number(word), word)


class SliceTest(support.Scratch):
    def cut(self, body: str, number: int = 1, ways: str | None = MAP) -> task_slice.Slice:
        run = self.run_folder("2026-01-02-030405-implement")
        if ways is not None:
            self.write(".council/map.md", ways)
        return task_slice.cut(run, ".council/plans/x.md", plan(body), number)

    def test_the_slice_is_owner_touches_and_the_map_row_the_owner_names(self) -> None:
        found = self.cut(task(1).replace("| **Done when**", "| **Touches** | `src/pay/webhook.py` |\n| **Done when**"))
        self.assertEqual([way.job for way in found.owned], ["Charge a card"])
        self.assertEqual(found.paths, ["src/pay/", "src/pay/webhook.py", "src/pay/", "src/pay/charge.py"])

    def test_no_such_task_and_no_plan_give_no_task(self) -> None:
        self.assertIsNone(self.cut(task(1), number=2).task)
        run = self.run_folder("2026-01-02-030406-implement")
        self.assertEqual(task_slice.cut(run, "", plan(task(1)), 1), task_slice.Slice("", None, None, [], []))


class PartsTest(support.Scratch):
    def slice_of(self, body: str, ways: str | None = MAP) -> task_slice.Slice:
        run = self.tmp / ".council" / "runs" / "2026-01-02-030405-implement"
        run.mkdir(parents=True, exist_ok=True)
        (self.tmp / ".council" / "map.md").unlink(missing_ok=True)
        if ways is not None:
            self.write(".council/map.md", ways)
        return task_slice.cut(run, ".council/plans/x.md", plan(body), 1)

    @property
    def folder(self) -> Path:
        return self.tmp / ".council" / "runs" / "2026-01-02-030405-implement"

    def test_part_one_quotes_the_task_as_the_plan_writes_it(self) -> None:
        rests = "a unique key (OBSERVED); the provider retries (ASSUMED, outside); a hunch"
        found = self.slice_of(task(1, rests=rests))
        self.assertEqual(context.task(self.folder, found.task), [
            "## The task", "Task 1: Task 1", 'Serves: "Charge the card once"',
            "Done when: a retried webhook charges once", "Rests on:", "- a unique key (OBSERVED)",
            "- the provider retries (ASSUMED, outside)", "- a hunch (no evidence state)", ""])
        self.assertIn("Rests on: nothing", context.task(self.folder, self.slice_of(task(1, rests="—")).task))
        self.assertIn("Rests on: (the plan gives no Rests on row)",
                      context.task(self.folder, self.slice_of(task(1, rests=None)).task))

    def test_part_one_shows_a_needs_stop_on_the_tasks_own_seat(self) -> None:
        found = self.slice_of(task(1))
        self.write(".council/runs/2026-01-02-030405-implement/seats.tsv",
                   "slug\tstate\tagent\ttokens\tupdated\tnote\n"
                   "T1\tdone\t\t\t10:00\tNEEDS: fix a.py:2 · does: x · should: y · seen: z\n"
                   "task-2\tdone\t\t\t10:00\tNEEDS: is the key unique?\n"
                   "1\tdone\t\t\t10:00\tall done\n")
        self.assertEqual(context.task(self.folder, found.task)[-2:],
                         ["Stopped earlier: NEEDS: fix a.py:2 · does: x · should: y · seen: z", ""])

    def test_part_two_names_the_owner_row_the_slice_and_the_rows_inside_touches(self) -> None:
        body = task(1).replace("| **Done when**", "| **Touches** | `src/mail/outbox.py` |\n| **Ref** | "
                                                  "references/quality-backend.md |\n| **Done when**")
        out = context.owner(self.slice_of(body))
        self.assertEqual(out[:3], ["## Owner", "Owner: src/pay/ — Charge a card", "The one way: Charge a card · "
                                   "src/pay/ · charge() through the gateway client · src/pay/charge.py"])
        self.assertIn("Slice: src/pay/, src/mail/outbox.py, src/pay/charge.py", out)
        self.assertIn("Other map rows inside Touches:", out)
        self.assertIn("- Send an email · src/mail/ · the outbox queue · src/mail/outbox.py", out)
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": ""}):
            self.assertIn("Ref: %s/references/quality-backend.md — read it there; it is not copied here"
                          % where.plugin_root(), context.owner(self.slice_of(body)))

    def test_a_ref_is_whole_only_for_a_file_the_plugin_has(self) -> None:
        self.write("plugin/references/refactoring.md", "# R\n")
        root = (self.tmp / "plugin").as_posix()
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": root}):
            self.assertEqual(context.plugin_paths("`references/refactoring.md` → Principle 2; references/none.md, "
                                                   "docs/references/refactoring.md"),
                             "`%s/references/refactoring.md` → Principle 2; references/none.md, "
                             "docs/references/refactoring.md" % root)

    def test_part_two_says_when_there_is_no_table_or_a_new_way(self) -> None:
        self.assertIn("The one way: the map has no one-way-per-job table",
                      context.owner(self.slice_of(task(1), ways=None)))
        self.assertIn("The one way: none — the task adds a New way, a ruling for the user",
                      context.owner(self.slice_of(task(1, owner="New way: no mail module yet"))))

    def test_part_five_names_other_tasks_rounds_on_the_slice_only(self) -> None:
        found = self.slice_of(task(1))
        run = self.tmp / ".council" / "runs" / "2026-01-02-030405-implement"
        for number, files, cause in ((2, ["src/pay/charge.py", "README.md"], "it ran twice"),
                                     (3, ["src/mail/a.py"], ""), (1, ["src/pay/charge.py"], "")):
            head = {"cause": cause or "none", "state": "REPRODUCED" if cause else ""}
            patches.write(run, patches.Round(number, 1, number, "t", "a", "b", files, 1, 0, head, [], [], ""), b"")
        self.assertEqual(context.earlier(run, found), [
            "## Earlier changes to these files",
            "- task 2 round 1 (T2-1.patch): src/pay/charge.py · Cause: it ran twice (REPRODUCED)", ""])


class HardRulesTest(support.Scratch):
    def test_the_section_word_for_word_without_the_template_placeholder(self) -> None:
        self.write(".council/council.config.md", "# c\n## Hard rules\n- <non-negotiables every worker obeys, e.g.\n"
                   "  \"never write\">\n\n- never write to prod  \n  (the users said so)\n\n## Memory\n- x\n"
                   "## Hard rules\n- a second section is not read\n")
        self.assertEqual(config.hard_rules(self.tmp / ".council"), ["- never write to prod  ", "  (the users said so)"])

    def test_none_when_the_config_or_the_section_is_missing(self) -> None:
        self.assertEqual(config.hard_rules(self.tmp / ".council"), [])
        self.write(".council/council.config.md", "# c\n## Hard rules\n- <only the placeholder>\n")
        self.assertEqual(config.hard_rules(self.tmp / ".council"), [])


class CeilingTest(unittest.TestCase):
    HEADING = ("# Task pack — task 1 · x.md", "")

    def parts(self, *sizes: int) -> list[list[str]]:
        return [["## " + name, "x" * size, ""] for name, size in zip(context.NAMES, sizes)]

    def test_a_pack_under_the_ceiling_keeps_every_part_and_counts_its_own_bytes(self) -> None:
        out = context.fit(list(self.HEADING), self.parts(100, 100, 100, 100, 100))
        self.assertEqual([line for line in out if line.startswith("## ")],
                         ["## " + name for name in context.NAMES] + ["## Left out"])
        self.assertEqual(out[-1], "pack: %d bytes of 8000; left out: nothing" % printed(out))

    def test_over_the_ceiling_whole_parts_go_from_the_end_and_are_named(self) -> None:
        out = context.fit(list(self.HEADING), self.parts(100, 100, 4000, 4000, 3000))
        self.assertLessEqual(printed(out), context.CEILING)
        self.assertNotIn("## Rulings and standing rules", out)
        self.assertIn("## Hard constraints and memory", out)
        self.assertIn("- Earlier changes to these files (part 5): over the 8000-byte ceiling, dropped whole", out)
        self.assertEqual(out[-1], "pack: %d bytes of 8000; left out: Rulings and standing rules, Earlier changes "
                                  "to these files" % printed(out))

    def test_a_first_part_over_the_ceiling_leaves_the_heading_and_left_out(self) -> None:
        out = context.fit(list(self.HEADING), self.parts(9000, 1, 1, 1, 1))
        self.assertEqual(out[:3], [*self.HEADING, "## Left out"])
        self.assertEqual(out[-1], "pack: %d bytes of 8000; left out: %s" % (printed(out), ", ".join(context.NAMES)))

    def test_the_count_holds_where_its_own_digits_tip_it_over(self) -> None:
        for size in range(7000, 7200):
            out = context.fit(list(self.HEADING), self.parts(size))
            self.assertLessEqual(printed(out), context.CEILING, size)
            self.assertEqual(out[-1].split()[1], str(printed(out)), size)
        self.assertEqual(printed(["é"]), 3)


if __name__ == "__main__":
    unittest.main()
