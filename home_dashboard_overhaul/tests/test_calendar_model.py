from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CalendarModelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the dependency-free calendar model test")
    def test_dependency_free_javascript_calendar_model(self) -> None:
        result = subprocess.run(
            ["node", str(ROOT / "tests" / "calendar_model_test.js")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("calendar model tests passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
