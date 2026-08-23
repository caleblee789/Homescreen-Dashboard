from __future__ import annotations

import unittest

from home_dashboard_overhaul.qa.color_system_audit import (
    PACKAGE_ROOT,
    contrast_audit,
    hardcoded_color_audit,
)


class ColorSystemAuditTests(unittest.TestCase):
    def test_production_components_have_no_unclassified_raw_colors(self) -> None:
        report = hardcoded_color_audit(PACKAGE_ROOT)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["component_hardcoding_count"], 0)
        self.assertGreater(report["category_counts"]["1"]["count"], 0)
        self.assertGreater(report["category_counts"]["2"]["count"], 0)
        self.assertGreater(report["category_counts"]["3"]["count"], 0)

    def test_all_gated_contrast_pairs_pass(self) -> None:
        report = contrast_audit()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["failed_count"], 0)
        self.assertGreaterEqual(report["check_count"], 450)
        groups = {item["group"] for item in report["checks"]}
        self.assertTrue(
            {
                "interface text",
                "calendar footer text",
                "primary button text",
                "secondary control text",
                "complete heat date text",
                "reviews due date text",
                "reviews due bottom marker",
                "selected outline on completion heat",
                "today ring on future date",
                "event marker on completion heat",
                "important control boundary",
                "selected control boundary",
            }.issubset(groups)
        )


if __name__ == "__main__":
    unittest.main()
