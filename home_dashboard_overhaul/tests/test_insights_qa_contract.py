from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _validator_module():
    path = ROOT / "qa" / "validate_revised_ui_contract.py"
    spec = importlib.util.spec_from_file_location("hdo_revised_ui_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load revised UI validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CorrectedInsightQaContractTests(unittest.TestCase):
    def test_machine_readable_revised_ui_contract_passes(self) -> None:
        self.assertEqual(_validator_module().validate(ROOT), [])

    def test_most_missed_is_capability_only_and_loaded_lazily(self) -> None:
        models = (ROOT / "models.py").read_text(encoding="utf-8")
        insights = (ROOT / "insights.py").read_text(encoding="utf-8")
        javascript = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
        for removed_model in (
            "InsightPreviewKind",
            "InsightItemKind",
            "class InsightItem",
            "insight_items",
            "answer_preview",
        ):
            self.assertNotIn(removed_model, models + insights + renderer)
        self.assertIn("requestMostMissedCapability(day)", javascript)
        self.assertIn('send("date_insight"', javascript)
        self.assertIn("state.mostMissed[day.date] = null", javascript)
        self.assertNotIn("pointerenter\", function () { requestMostMissed", javascript)

    def test_exact_browser_target_is_controller_owned(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        for marker in (
            "open_most_missed_in_browser",
            "target = insight.browse_target",
            "self._open_browser_target(target)",
            "browser_will_search",
            "ordered_card_ids",
        ):
            self.assertIn(marker, controller)


if __name__ == "__main__":
    unittest.main()
