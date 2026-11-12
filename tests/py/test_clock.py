from datetime import datetime, timezone
import unittest

import support  # noqa: F401  (puts src/ on the path)
from council import clock


class ClockTest(unittest.TestCase):
    def test_event_clock(self):
        moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.assertEqual(clock.event_clock("2026-01-02T03:04:05Z"), moment.astimezone().strftime("%H:%M:%S"))
        self.assertEqual(clock.event_clock("2026-01-02 03:04:05 local"), "03:04:05")

    def test_utc_and_iso_moments(self):
        want = datetime(2026, 9, 30, 10, 14, 16, tzinfo=timezone.utc)
        self.assertEqual(clock.utc_moment("2026-09-30T10:14:16Z"), want)
        self.assertIsNone(clock.utc_moment("2026-09-30T10:14:16.5Z"))
        self.assertEqual(clock.iso_moment("2026-09-30T10:14:16.894Z"), want)
        self.assertEqual(clock.iso_moment("2026-09-30T10:14:16+00:00"), want)
        self.assertIsNone(clock.iso_moment("yesterday"))

    def test_local_moment(self):
        self.assertEqual(clock.local_moment("2026-01-02 03:04").replace(tzinfo=None), datetime(2026, 1, 2, 3, 4))
        self.assertEqual(clock.local_moment("2026-01-02 03:04:05 extra").second, 5)
        self.assertIsNone(clock.local_moment(""))


if __name__ == "__main__":
    unittest.main()
