"""event_note.locked: a with block under a run file's lock, refused in the site's own words."""
from __future__ import annotations

import unittest
from unittest import mock

import support

from council.commands import cli, event_note
from council.records import locks


class LockedTest(support.Scratch):
    def test_the_block_runs_under_the_lock_and_leaves_it_free(self) -> None:
        lock = self.tmp / "seats.tsv.lock"
        with event_note.locked(lock, "seat lock unavailable"):
            self.assertTrue(lock.is_dir())
        self.assertFalse(lock.exists())

    def test_a_held_lock_is_refused_with_its_holder_then_the_words(self) -> None:
        lock = self.tmp / "events.tsv.lock"
        self.assertTrue(locks.acquire(lock))
        ran = []
        with mock.patch.object(locks, "acquire", lambda lock: False), \
                self.assertRaises(cli.Refusal) as refused, event_note.locked(lock, "the go was not recorded"):
            ran.append(1)
        self.assertEqual(ran, [])
        said = str(refused.exception).split("\n")
        self.assertIn("lock unavailable", said[0])
        self.assertEqual(said[1], "council: the go was not recorded")
        self.assertTrue(lock.is_dir())                     # the holder's lock is untouched

    def test_a_lock_that_stays_held_is_refused_only_when_unreleased_is_given(self) -> None:
        with mock.patch.object(locks, "release", lambda lock: False):
            with event_note.locked(self.tmp / "a.lock", "unavailable"):
                pass
            with self.assertRaisesRegex(cli.Refusal, "^changed, but its lock could not be released$"), \
                    event_note.locked(self.tmp / "b.lock", "busy", "changed, but its lock could not be released"):
                pass

    def test_a_failing_block_keeps_its_own_error_and_frees_the_lock(self) -> None:
        lock = self.tmp / "state.lock"
        with self.assertRaisesRegex(cli.Refusal, "^cannot update$"), \
                event_note.locked(lock, "unavailable", "never said"):
            raise cli.Refusal("cannot update")
        self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
