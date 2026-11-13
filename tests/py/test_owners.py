"""Who holds a lock (records/owners.py, D33): a live owner, a dead one, a Windows id handed to a later
process, and what a waiter that gives up says."""
import os
import re
import subprocess
import sys
import time
import unittest

import support

from council.records import locks, owners


def dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class AliveTest(support.Scratch):
    def test_this_process_is_alive_and_an_ended_one_is_not(self) -> None:
        self.assertTrue(owners.alive(os.getpid()))
        self.assertFalse(owners.alive(dead_pid()))

    def test_a_holder_that_wrote_its_owner_file_is_alive(self) -> None:
        owner = self.write("x.lock/owner", "%d\n" % os.getpid())
        self.assertTrue(owners.holder_alive(os.getpid(), owner))
        self.assertFalse(owners.holder_alive(dead_pid(), owner))


class ReuseTest(support.Scratch):
    def test_made_more_than_two_seconds_after_the_owner_file_is_another_process(self) -> None:
        written = 1000.0
        self.assertFalse(owners.reused(written - 50, written))         # made before: the holder
        self.assertFalse(owners.reused(written + 2, written))          # inside the slack
        self.assertTrue(owners.reused(written + 2.01, written))        # past it: the id was reused
        self.assertFalse(owners.reused(None, written))                 # no start time: no evidence

    @unittest.skipUnless(os.name == "nt", "Windows reuses ids soon; elsewhere a live owner is the holder")
    def test_on_windows_a_live_process_made_after_the_owner_file_is_not_its_holder(self) -> None:
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        owner = self.write("events.tsv.lock/owner", "%d\n" % os.getpid())
        old = time.time() - 30 * 24 * 3600                              # written long before this process began
        os.utime(str(owner), (old, old))
        self.assertTrue(owners.alive(os.getpid()))
        self.assertFalse(owners.holder_alive(os.getpid(), owner))
        self.assertTrue(locks.stale(lock))
        self.assertTrue(locks.acquire(lock, tries=2))                   # reclaimed, and now this process's
        self.assertTrue(locks.release(lock))

    @unittest.skipIf(os.name == "nt", "the reuse check is Windows only")
    def test_elsewhere_a_live_owner_is_the_holder_however_old_its_file(self) -> None:
        owner = self.write("x.lock/owner", "%d\n" % os.getpid())
        old = time.time() - 30 * 24 * 3600
        os.utime(str(owner), (old, old))
        self.assertTrue(owners.holder_alive(os.getpid(), owner))


class RefusalTest(support.Scratch):
    def test_names_the_lock_the_holder_its_age_and_the_next_step(self) -> None:
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        self.write("events.tsv.lock/owner", "4321\n")
        old = time.time() - 25
        os.utime(str(lock), (old, old))
        said = owners.unavailable(lock)
        self.assertTrue(said.startswith("event lock unavailable: %s (held by process 4321, age " % lock), said)
        self.assertRegex(said, r"age 2[5-7] s\)")
        self.assertIn("run this again once that call ends; if process 4321 is not a council call, "
                      "remove that folder first", said)

    def test_a_lock_with_no_holder_named(self) -> None:
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        future = time.time() + 300                                      # a clock ahead reads as no age
        os.utime(str(lock), (future, future))
        said = owners.unavailable(lock)
        self.assertEqual(said, "event lock unavailable: %s (no holder named in it, age 0 s) — run this again" % lock)
        self.assertIsNotNone(re.search("run this again$", owners.unavailable(self.tmp / "gone.lock")))


if __name__ == "__main__":
    unittest.main()
