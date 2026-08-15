from __future__ import annotations

import ast
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "qa" / "acceptance_probe_insights.py"

EXPECTED_CAPTURE_NAMES = (
    "01-current-trouble-dark",
    "02-past-no-miss",
    "03-past-deleted",
    "04-past-empty",
    "05-future-due",
    "06-future-empty",
    "07-current-620x780",
    "08-current-150-percent",
    "09-current-200-percent",
    "10-current-light",
    "11-current-high-contrast",
    "12-current-after-restart",
)


def _probe_tree() -> ast.Module:
    return ast.parse(PROBE_PATH.read_text(encoding="utf-8"), filename=str(PROBE_PATH))


def _contract_namespace() -> dict[str, object]:
    tree = _probe_tree()
    selected = []
    names = {"EXPECTED_CAPTURE_NAMES", "EXPECTED_GATE_STAGES", "REQUIRED_GATE_FIELDS"}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "evidence_contract":
            selected.append(node)
    namespace: dict[str, object] = {"RESULTS": {}}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(PROBE_PATH), "exec"),
        namespace,
    )
    return namespace


def _readiness_namespace() -> dict[str, object]:
    function = next(
        node
        for node in _probe_tree().body
        if isinstance(node, ast.FunctionDef) and node.name == "direct_current_model_ready"
    )
    namespace: dict[str, object] = {"Any": Any, "date": date}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(PROBE_PATH), "exec"),
        namespace,
    )
    return namespace


def _semantics_namespace() -> dict[str, object]:
    tree = _probe_tree()
    selected = []
    names = {
        "EXPECTED_CAPTURE_NAMES",
        "CAPTURE_STATE_KEYS",
        "SEMANTIC_CONTRACTS",
    }
    functions = {"model_dom_items", "semantic_failures"}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
    namespace: dict[str, object] = {"Any": Any}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(PROBE_PATH), "exec"),
        namespace,
    )
    return namespace


def _model_for_state(state: str, iso_date: str) -> dict[str, object]:
    items = []
    if state == "current":
        items = [
            {
                "primary_text": "Card A",
                "secondary_text": "QA Insights::Anatomy",
                "count": 3,
                "count_label": "Again ×3",
            },
            {
                "primary_text": "Card B",
                "secondary_text": "QA Insights::Pharmacology",
                "count": 2,
                "count_label": "Again ×2",
            },
            {
                "primary_text": "Card C fallback field",
                "secondary_text": "QA Insights::Pathology",
                "count": 1,
                "count_label": "Again ×1",
            },
        ]
    elif state == "future_due":
        items = [
            {
                "primary_text": "QA Insights::Anatomy",
                "secondary_text": "",
                "count": 5,
                "count_label": "5 cards due",
            },
            {
                "primary_text": "QA Insights::Pharmacology",
                "secondary_text": "",
                "count": 3,
                "count_label": "3 cards due",
            },
            {
                "primary_text": "QA Insights::Pathology",
                "secondary_text": "",
                "count": 1,
                "count_label": "1 card due",
            },
        ]
    return {"date": iso_date, "items": items}


def _valid_semantic_dom(
    namespace: dict[str, object],
    capture_name: str,
    iso_date: str,
    model: dict[str, object],
) -> dict[str, object]:
    state = namespace["CAPTURE_STATE_KEYS"][capture_name]
    contract = namespace["SEMANTIC_CONTRACTS"][state]
    return {
        "selectedDate": iso_date,
        "detailsVisible": True,
        "insightBusy": "false",
        "insightTitle": contract["title"],
        "status": contract["status"],
        "browseHidden": False,
        "browseLabel": contract["browse_label"],
        "itemCount": contract["item_count"],
        "itemRows": namespace["model_dom_items"](model),
        "legacySummaryCount": 0,
        "detailsSummaryCount": 1,
        "summaryVisible": contract["summary_visible"],
    }


def _valid_results(namespace: dict[str, object]) -> dict[str, object]:
    capture_names = list(namespace["EXPECTED_CAPTURE_NAMES"])
    gate_fields = tuple(namespace["REQUIRED_GATE_FIELDS"])
    gates = []
    for stage in namespace["EXPECTED_GATE_STAGES"]:
        gate = {field: True for field in gate_fields}
        gate["stage"] = stage
        gates.append(gate)
    return {
        "captures": [{"name": name} for name in capture_names],
        "dom": {name: {} for name in capture_names},
        "gates": gates,
    }


class InsightsQaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = _probe_tree()
        self.namespace = _contract_namespace()
        self.contract = self.namespace["evidence_contract"]

    def _evaluate(self, results: dict[str, object]) -> dict[str, bool]:
        self.contract.__globals__["RESULTS"] = results
        return self.contract()

    def test_contract_accepts_exact_capture_and_gate_sequences(self) -> None:
        self.assertEqual(self.namespace["EXPECTED_CAPTURE_NAMES"], EXPECTED_CAPTURE_NAMES)
        self.assertEqual(self.namespace["EXPECTED_GATE_STAGES"], ("initial", "restart"))
        self.assertEqual(
            self._evaluate(_valid_results(self.namespace)),
            {"capture_contract": True, "gate_contract": True},
        )

    def test_capture_contract_fails_closed_for_missing_reordered_duplicate_or_extra_evidence(self) -> None:
        valid = _valid_results(self.namespace)
        variants = {}
        variants["missing"] = deepcopy(valid)
        variants["missing"]["captures"].pop()
        variants["reordered"] = deepcopy(valid)
        variants["reordered"]["captures"][0:2] = reversed(
            variants["reordered"]["captures"][0:2]
        )
        variants["duplicate"] = deepcopy(valid)
        variants["duplicate"]["captures"][-1] = deepcopy(
            variants["duplicate"]["captures"][-2]
        )
        variants["extra"] = deepcopy(valid)
        variants["extra"]["captures"].append({"name": "13-unexpected"})
        variants["extra"]["dom"]["13-unexpected"] = {}
        variants["missing-dom"] = deepcopy(valid)
        variants["missing-dom"]["dom"].pop(EXPECTED_CAPTURE_NAMES[-1])

        for name, results in variants.items():
            with self.subTest(name=name):
                self.assertFalse(self._evaluate(results)["capture_contract"])

    def test_gate_contract_fails_closed_for_wrong_count_order_duplicate_or_false_gate(self) -> None:
        valid = _valid_results(self.namespace)
        variants = {}
        variants["missing"] = deepcopy(valid)
        variants["missing"]["gates"].pop()
        variants["reordered"] = deepcopy(valid)
        variants["reordered"]["gates"].reverse()
        variants["duplicate"] = deepcopy(valid)
        variants["duplicate"]["gates"][1]["stage"] = "initial"
        variants["extra"] = deepcopy(valid)
        variants["extra"]["gates"].append(deepcopy(variants["extra"]["gates"][-1]))
        variants["false-field"] = deepcopy(valid)
        variants["false-field"]["gates"][1]["sync_gate"] = False

        for name, results in variants.items():
            with self.subTest(name=name):
                self.assertFalse(self._evaluate(results)["gate_contract"])

    def test_probe_publishes_candidate_hash_and_completion_uses_both_contracts(self) -> None:
        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn('RESULTS["candidate_sha256"] = EXPECTED_HASH', source)
        self.assertIn('"capture_contract": contracts["capture_contract"]', source)
        self.assertIn('"gate_contract": contracts["gate_contract"]', source)
        self.assertIn('RESULTS["complete"] = all(summary.values())', source)
        self.assertIn('profile.get("syncMedia", False)', source)

    def test_readiness_uses_direct_current_model_not_retired_snapshot_field(self) -> None:
        namespace = _readiness_namespace()
        ready = namespace["direct_current_model_ready"]
        current = {
            "date": date.today().isoformat(),
            "valid_answer_count": 9,
            "again_count": 7,
            "items": [{}, {}, {}],
        }
        self.assertTrue(ready(SimpleNamespace(errors={}), current))
        self.assertFalse(ready(SimpleNamespace(errors={"today": "failed"}), current))
        self.assertFalse(ready(SimpleNamespace(errors={}), {**current, "items": []}))
        self.assertFalse(ready(SimpleNamespace(errors={}), {**current, "items": None}))

        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("snapshot.today_insight", source)
        self.assertIn('record("today_insight_initial", models["current"])', source)
        self.assertIn('record("today_insight_after_restart", models["current"])', source)

    def test_async_timeout_paths_fail_and_close_instead_of_hanging(self) -> None:
        functions = {
            node.name: ast.unparse(node)
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("fail_and_close", functions["wait_for_insight_ready"])
        self.assertIn("fail_and_close", functions["wait_for_selected"])
        self.assertIn("fail_and_close", functions["start"])
        self.assertIn("fail_and_close", functions["eval_js"])
        self.assertIn("mw.close", functions["fail_and_close"])

    def test_all_twelve_captures_have_exact_state_and_contextual_summary_contracts(self) -> None:
        namespace = _semantics_namespace()
        capture_states = namespace["CAPTURE_STATE_KEYS"]
        contracts = namespace["SEMANTIC_CONTRACTS"]
        self.assertEqual(tuple(capture_states), EXPECTED_CAPTURE_NAMES)
        self.assertEqual(
            [name for name, state in capture_states.items() if state == "current"],
            [
                "01-current-trouble-dark",
                "07-current-620x780",
                "08-current-150-percent",
                "09-current-200-percent",
                "10-current-light",
                "11-current-high-contrast",
                "12-current-after-restart",
            ],
        )
        self.assertEqual(
            {state: value["summary_visible"] for state, value in contracts.items()},
            {
                "current": 3,
                "no_miss": 2,
                "deleted": 2,
                "past_empty": 2,
                "future_due": 1,
                "future_empty": 1,
            },
        )
        self.assertEqual(contracts["past_empty"]["browse_label"], "Browse this day’s cards")
        self.assertEqual(contracts["future_empty"]["browse_label"], "Browse due cards")

        failures = namespace["semantic_failures"]
        for capture_name, state in capture_states.items():
            with self.subTest(capture_name=capture_name):
                iso_date = "2026-08-15" if state == "current" else "2026-08-14"
                model = _model_for_state(state, iso_date)
                dom = _valid_semantic_dom(namespace, capture_name, iso_date, model)
                self.assertEqual(failures(capture_name, iso_date, dom, model), [])

    def test_semantics_fail_closed_for_unavailable_current_items_actions_and_summaries(self) -> None:
        namespace = _semantics_namespace()
        failures = namespace["semantic_failures"]
        capture_name = "01-current-trouble-dark"
        iso_date = "2026-08-15"
        model = _model_for_state("current", iso_date)
        valid = _valid_semantic_dom(namespace, capture_name, iso_date, model)
        mutations = {
            "unavailable": {"status": "Study insight unavailable."},
            "loading-title": {"insightTitle": "Study insight"},
            "wrong-rank": {"itemRows": list(reversed(valid["itemRows"]))},
            "hidden-browse": {"browseHidden": True, "browseLabel": ""},
            "legacy-summary": {"legacySummaryCount": 1},
            "duplicate-canonical-summary": {"detailsSummaryCount": 2},
            "wrong-context": {"summaryVisible": 2},
        }
        for name, changes in mutations.items():
            with self.subTest(name=name):
                dom = {**valid, **changes}
                self.assertTrue(failures(capture_name, iso_date, dom, model))

    def test_wait_for_selected_waits_for_exact_semantics_and_fails_closed(self) -> None:
        functions = {
            node.name: ast.unparse(node)
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        wait_source = functions["wait_for_selected"]
        self.assertIn("semantic_failures", wait_source)
        self.assertIn("model_for_capture", wait_source)
        self.assertIn("fail_and_close", wait_source)
        self.assertIn("DOM_SCRIPT", wait_source)
        self.assertNotIn("value.get('busy') == 'false'", wait_source)

        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("duplicateSummaryCount", source)
        self.assertIn("legacySummaryCount", source)
        self.assertIn("detailsSummaryCount", source)
        self.assertIn('"contextual_summary_contract"', source)
        self.assertIn('"current_dom_matches_backend"', source)
        self.assertIn('"exact_capture_semantics"', source)

    def test_future_due_transition_occurs_once(self) -> None:
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "select_future_due"
        )
        select_calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select_date"
        ]
        capture_calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "capture_state"
        ]
        self.assertEqual(len(select_calls), 1)
        self.assertEqual(len(capture_calls), 1)
        self.assertEqual(capture_calls[0].args[0].value, "05-future-due")


if __name__ == "__main__":
    unittest.main()
