import os
import subprocess
import sys
import threading
import time
import unittest

import support
from council.records import locks


def dead_pid() -> int:
    """The id of a process that has just ended."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def put_owner(folder, value) -> None:
    """An owner file as bash writes one: the value and a newline, never a carriage return."""
    (folder / "owner").write_bytes("{}\n".format(value).encode())


def owner_of(folder) -> bytes:
    return (folder / "owner").read_bytes()


class LockTest(support.Scratch):
    def test_acquire_writes_the_owner_and_release_removes_the_lock(self):
        lock = self.tmp / "events.tsv.lock"
        self.assertTrue(locks.acquire(lock))
        self.assertEqual(owner_of(lock), "{}\n".format(os.getpid()).encode())
        self.assertTrue(locks.release(lock))
        self.assertFalse(lock.exists())
        self.assertFalse(locks.release(lock))

    def test_a_live_holder_is_waited_for_then_refused(self):
        lock = self.tmp / "seats.tsv.lock"
        self.assertTrue(locks.acquire(lock))
        started = time.time()
        self.assertFalse(locks.acquire(lock, tries=3))
        self.assertGreaterEqual(time.time() - started, 0.15)
        with self.assertRaisesRegex(locks.LockError, "event lock unavailable"):
            with locks.held(lock, tries=1):
                pass
        self.assertTrue(lock.is_dir())                     # the holder's lock is untouched

    def test_two_threads_never_hold_it_together(self):
        lock = self.tmp / "events.tsv.lock"
        counter = self.write("counter.txt", "0")
        inside, overlaps = [0], []

        def work():
            for _ in range(25):
                with locks.held(lock):
                    inside[0] += 1
                    if inside[0] > 1:
                        overlaps.append(1)
                    value = int(counter.read_text())
                    time.sleep(0.001)
                    counter.write_text(str(value + 1))
                    inside[0] -= 1

        threads = [threading.Thread(target=work) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(overlaps, [])
        self.assertEqual(counter.read_text(), "50")
        self.assertFalse(lock.exists())

    def test_a_lock_left_by_a_dead_writer_is_reclaimed(self):
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        put_owner(lock, dead_pid())
        self.assertTrue(locks.stale(lock))
        self.assertTrue(locks.acquire(lock, tries=5))
        self.assertEqual(owner_of(lock), "{}\n".format(os.getpid()).encode())
        self.assertFalse((self.tmp / "events.tsv.lock.recover").exists())
        locks.release(lock)

    def test_a_lock_without_an_owner_is_stale_only_once_old(self):
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        self.assertFalse(locks.stale(lock))               # a writer may be between mkdir and owner
        old = time.time() - 30
        os.utime(str(lock), (old, old))
        self.assertTrue(locks.stale(lock))
        put_owner(lock, "not a number")
        os.utime(str(lock), (old, old))
        self.assertTrue(locks.stale(lock))

    def test_an_owner_ending_in_a_carriage_return_is_no_number(self):
        lock = self.tmp / "x.lock"
        lock.mkdir()
        (lock / "owner").write_bytes("{}\r\n".format(os.getpid()).encode())
        self.assertFalse(locks.stale(lock))               # fresh: read by its age, as bash reads it
        old = time.time() - 30
        os.utime(str(lock), (old, old))
        self.assertTrue(locks.stale(lock))

    def test_a_live_owner_is_never_stale(self):
        lock = self.tmp / "x.lock"
        lock.mkdir()
        put_owner(lock, os.getpid())
        old = time.time() - 30
        os.utime(str(lock), (old, old))
        self.assertFalse(locks.stale(lock))
        self.assertFalse(locks.stale(self.tmp / "absent.lock"))

    def test_a_writer_yields_while_a_reclaim_is_under_way(self):
        lock = self.tmp / "events.tsv.lock"
        recovery = self.tmp / "events.tsv.lock.recover"
        recovery.mkdir()
        put_owner(recovery, os.getpid())                  # a live reclaimer
        self.assertFalse(locks.acquire(lock, tries=2))
        self.assertFalse(lock.exists())

    def test_a_stale_recovery_folder_is_cleared(self):
        lock = self.tmp / "events.tsv.lock"
        recovery = self.tmp / "events.tsv.lock.recover"
        recovery.mkdir()
        put_owner(recovery, dead_pid())
        self.assertTrue(locks.acquire(lock, tries=3))
        self.assertFalse(recovery.exists())
        locks.release(lock)


class ClaimTest(support.Scratch):
    """The owner file, not mkdir, decides who holds a lock (bin/council's lock_claim). Each test fakes
    uutils mkdir 0.10.0, which reports success when the directory is already there."""

    def setUp(self):
        super().setUp()
        self.other = os.getppid()                         # a live process that is not this one
        self.real_make = locks._make
        self.racer = None                                 # writes another's owner file inside the fake mkdir

        def lenient_make(folder):
            try:
                os.mkdir(str(folder))
            except FileExistsError:
                pass
            except OSError:
                return False
            if self.racer is not None:
                self.racer(folder)
            return True

        locks._make = lenient_make

    def tearDown(self):
        locks._make = self.real_make
        super().tearDown()

    def test_an_existing_lock_with_another_owner_is_not_taken(self):
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()
        put_owner(lock, self.other)
        self.assertFalse(locks.acquire(lock, tries=2))
        self.assertEqual(owner_of(lock), "{}\n".format(self.other).encode())   # touched nothing
        self.assertEqual(locks._claim(lock, "1"), locks.TAKEN)
        self.assertEqual(locks._claim(self.tmp / "gone.lock", "1"), locks.TAKEN)

    def test_an_ownerless_directory_is_held_only_through_the_exclusive_create(self):
        lock = self.tmp / "events.tsv.lock"
        lock.mkdir()                                       # made, owner not written yet
        self.racer = lambda folder: put_owner(folder, self.other) if folder == lock else None
        self.assertFalse(locks.acquire(lock, tries=2))     # the racer's create won
        self.assertEqual(owner_of(lock), "{}\n".format(self.other).encode())
        (lock / "owner").unlink()
        self.racer = None
        self.assertTrue(locks.acquire(lock, tries=2))      # no racer: this call's create wins
        self.assertEqual(owner_of(lock), "{}\n".format(os.getpid()).encode())
        self.assertTrue(locks.release(lock))

    def test_losing_the_recover_claim_leaves_it_in_place(self):
        lock = self.tmp / "events.tsv.lock"
        recovery = self.tmp / "events.tsv.lock.recover"
        lock.mkdir()
        put_owner(lock, dead_pid())                        # stale, so this call tries to reclaim it
        recovery.mkdir()
        put_owner(recovery, self.other)                    # another reclaimer got there first
        self.assertFalse(locks.acquire(lock, tries=2))
        self.assertEqual(owner_of(recovery), "{}\n".format(self.other).encode())
        self.assertTrue(lock.is_dir())                     # the reclaim is the other one's to finish


if __name__ == "__main__":
    unittest.main()
