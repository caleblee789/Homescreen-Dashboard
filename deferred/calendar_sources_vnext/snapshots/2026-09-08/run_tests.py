"""Run the preserved calendar tests without importing the active Anki add-on."""

from pathlib import Path
import sys
from types import ModuleType
import unittest


def main() -> int:
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required for the deferred calendar tests.")
    snapshot = Path(__file__).resolve().parent
    sys.path.insert(0, str(snapshot.parents[1] / "_vendor"))
    # Preserve the original imports and mock targets in these historical tests.
    package = ModuleType("home_dashboard_overhaul")
    package.__path__ = [str(snapshot)]
    sys.modules[package.__name__] = package
    suite = unittest.defaultTestLoader.discover(str(snapshot / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
