from __future__ import annotations

import unittest
from pathlib import Path

from home_dashboard_overhaul import ui_primitives as ui


class SharedUiPrimitiveContractTests(unittest.TestCase):
    def test_content_modes_are_exact_and_closed(self) -> None:
        self.assertEqual(ui.CONTENT_MODES, ("extra-wide", "intermediate", "narrow"))
        self.assertEqual(ui.normalize_content_mode("extra-wide"), "extra-wide")
        self.assertEqual(ui.normalize_content_mode("unknown"), "narrow")

    def test_every_requested_primitive_is_registered_once(self) -> None:
        expected = {
            "dashboard-header",
            "dashboard-panel",
            "calendar-context-bar",
            "statistics-card",
            "summary-metrics-grid",
            "bible-verse-card",
            "metric-row",
            "alert-banner",
            "recovery-card",
            "loading-card",
            "tooltip",
            "event-marker",
            "due-hatch",
            "settings-sidebar",
            "settings-footer",
            "form-control",
            "list-or-table-row",
            "contextual-action-group",
            "editor-dialog",
        }
        self.assertEqual(set(ui.PRIMITIVE_NAMES), expected)
        self.assertEqual(len(ui.PRIMITIVE_NAMES), len(set(ui.PRIMITIVE_NAMES)))

    def test_interaction_and_completion_tokens_are_shared(self) -> None:
        self.assertEqual(ui.INTERACTION_TARGET_MIN_PX, 34)
        self.assertEqual(ui.VISUAL_CHROME_PX, 34)
        self.assertEqual((ui.FOCUS_RING_PX, ui.FOCUS_RING_OFFSET_PX), (3, 2))
        self.assertEqual(ui.COMPLETION_TOKEN_ROLE, "completion")

    def test_shared_registry_is_in_the_release_allowlist(self) -> None:
        build = (
            Path(__file__).resolve().parents[1] / "tools" / "build_ankiaddon.py"
        ).read_text(encoding="utf-8")
        allowlist = build.split("PACKAGE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertIn('"ui_primitives.py"', allowlist)


if __name__ == "__main__":
    unittest.main()
