"""python -m council: the helper's ported commands (D24).

bin/council starts this file with no version probe, so it parses under any Python from 2.7 on (ASCII,
no annotations, no f-strings) and refuses one older than 3.8 with exit 85 before it imports anything but
sys; bin/council then tries its next Python. It runs with -E -s, not -I, which 2.7 and 3.0-3.3 stop on
before reading this file: so the folder this file is in comes off the path here, as -I would leave it,
and the package's own folder goes on."""
import sys

if sys.version_info < (3, 8):  # noqa: UP036  (the point: an older Python must reach this line)
    sys.exit(85)

import os  # noqa: E402  (only after the version check)

if not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from council.commands import dispatch  # noqa: E402  (after the path is set)

if __name__ == "__main__":
    sys.exit(dispatch.main(sys.argv[1:]))
