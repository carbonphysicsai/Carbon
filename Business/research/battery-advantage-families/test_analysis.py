"""Public/synthetic checks for the exploratory family comparison."""

import importlib.util
import json
import pathlib
import sys
import unittest

import numpy as np

PATH = pathlib.Path(__file__).with_name("analyze.py")
SPEC = importlib.util.spec_from_file_location("res10_research", PATH)
A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = A
SPEC.loader.exec_module(A)


class FamilyTests(unittest.TestCase):
    def test_trace_interpolation_retains_valid_nonreaching_node(self):
        first = {
            "voltage_v": [4.0, 4.3],
            "temperature_c": [25, 26],
            "plating_margin_v": 0.02,
        }
        second = {
            "voltage_v": [4.0, 4.18],
            "temperature_c": [25, 27],
            "plating_margin_v": 0.01,
        }
        mixed = A.blend_outputs([(first, 0.5), (second, 0.5)])
        np.testing.assert_allclose(mixed["voltage_v"], [4.0, 4.24])
        self.assertEqual(max(mixed["temperature_c"]), 26.5)
        self.assertAlmostEqual(mixed["plating_margin_v"], 0.015)
        self.assertEqual(set(mixed), {"voltage_v", "temperature_c", "plating_margin_v"})

    def test_trade_objective_does_not_fabricate_missing_timing(self):
        row = {"time_to_cv_onset_s": 120, "peak_temperature_c": 30}
        self.assertEqual(A.objective([row], [(29, 0.4)], 0.25), 1.25)
        self.assertIsNone(A.objective([None], [(29, 0.4)], 1))
        row["time_to_cv_onset_s"] = None
        self.assertIsNone(A.objective([row], [(29, 0.4)], 1))

    def test_temperature_preference_cannot_override_hard_failure(self):
        rev2, _, _ = A.dependencies()
        candidates = [{"id": "b", "c1": 1, "c2": 1}, {"id": "a", "c1": 2, "c2": 1}]
        assessed = {
            "b": {"objective": 10, "feasible": True},
            "a": {"objective": -100, "feasible": False},
        }
        self.assertEqual(rev2.shortlist(candidates, assessed, "b", 5), [])

    def test_fixed_orders_have_no_answer_input_or_free_fallback(self):
        candidates = [
            {"id": str(i), "c1": x, "c2": y}
            for i, (x, y) in enumerate([(0.5, 0.2), (0.75, 0.6), (0.75, 0.8), (1, 0.6)])
        ]
        for policy in (
            "low-current",
            "high-current",
            "fallback-c1-up",
            "fallback-c2-up",
        ):
            order = A.fixed_order(candidates, policy, "1")
            self.assertEqual(len(order), len(set(order)))
            self.assertNotIn("1", order)
        self.assertEqual(A.fixed_order(candidates, "fallback-c2-up", "1")[0], "2")
        self.assertEqual(A.fixed_order(candidates, "fallback-c1-up", "1")[0], "3")

    def test_composed_questions_cannot_acquire_fake_independent_ci(self):
        values = np.ones((2, 2))
        qs = [
            {"conditions": [(19, 0.2), (29, 0.4)]},
            {"conditions": [(19, 0.2), (38, 0.4)]},
        ]
        self.assertIsNone(A.block_ci(values, [0, 1], qs))
        self.assertIsNone(A.block_ci(values, [0], [{"conditions": [(29, 0.4)]}]))

    def test_published_empty_and_matched_scopes_stay_separate(self):
        result = json.loads(PATH.with_name("results.json").read_text(encoding="utf-8"))
        rows = result["profiles"]
        strict = next(
            r
            for r in rows
            if r["group"] == "single-verification-a20"
            and r["scope"] == "strict"
            and r["cap"] == 3
            and r["kappa_assumption"] == 0.1
        )
        matched = next(
            r
            for r in rows
            if r["group"] == strict["group"]
            and r["scope"] == "matched_full35_strict"
            and r["cap"] == 3
            and r["kappa_assumption"] == 0.1
        )
        self.assertEqual(strict["questions"], 3)
        self.assertEqual(matched["questions"], 1)
        self.assertGreater(strict["real_beat_retrospective_budget_envelope"], 0)
        self.assertEqual(matched["real_beat_retrospective_budget_envelope"], 0)
        for row in rows:
            if row["questions"] == 0:
                self.assertEqual(row["status"], "EMPTY_BANK_GAP")
                self.assertNotIn("bilinear_U", row)

    def test_retrospective_envelope_is_not_weaker_than_shown_maps(self):
        result = json.loads(PATH.with_name("results.json").read_text(encoding="utf-8"))
        for row in result["profiles"]:
            if row["questions"]:
                self.assertGreaterEqual(
                    row["retrospective_cheap_budget_envelope_U"],
                    max(0, row["bilinear_U"], row["nearest_U"]) - 1e-12,
                )

    def test_unchanged_single_full_grid_reproduces_res09(self):
        current = json.loads(PATH.with_name("results.json").read_text(encoding="utf-8"))
        old = json.loads(
            (PATH.parent.parent / "value-metric-v2-rev2-curves/results.json").read_text(
                encoding="utf-8"
            )
        )
        for split, population in (
            ("development", "nominal"),
            ("verification", "shifted"),
        ):
            row = next(
                r
                for r in current["profiles"]
                if r["group"] == f"single-{split}-a35"
                and r["scope"] == "strict"
                and r["cap"] == 3
                and r["kappa_assumption"] == 0.1
            )
            prior = next(
                r
                for r in old["profiles"]
                if r["curve"] == "population" and r["population"] == population
            )
            self.assertAlmostEqual(row["bilinear_U"], prior["cheap_U"], places=12)
            self.assertEqual(row["question_ids"], prior["question_ids"])

    def test_condition_costs_stay_multiplicative(self):
        data = json.loads(
            PATH.with_name("measurements.json").read_text(encoding="utf-8")
        )
        tokens = np.asarray(data["tokens"])
        for j, q in enumerate(data["questions"]):
            n = len(q["conditions"])
            self.assertTrue(np.all(tokens[:, j] % n == 0))
            self.assertTrue(np.all(tokens[:, j] <= n * np.arange(1, 6)))


if __name__ == "__main__":
    unittest.main()
