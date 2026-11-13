"""python -m council: the helper's ported commands. bin/council runs this file with python -I, which puts
neither the project's folder nor this one on the path, so the package's own folder is added here."""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from council.commands import dispatch  # noqa: E402  (after the path is set)

if __name__ == "__main__":
    sys.exit(dispatch.main(sys.argv[1:]))
