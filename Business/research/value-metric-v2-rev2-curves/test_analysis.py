"""Semantic regression checks; synthetic fixtures cannot enter live scoring."""

import importlib.util
import json
import pathlib
import sys
import unittest

import numpy as np

PATH = pathlib.Path(__file__).with_name("analyze.py")
SPEC = importlib.util.spec_from_file_location("rev2_research", PATH)
A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = A
SPEC.loader.exec_module(A)


class Rev2ContractTests(unittest.TestCase):
    def test_band_unresolved_is_not_complete(self):
        truth = {"b": {"status": "FEASIBLE"}, "a": {"status": "UNRESOLVED"}}
        self.assertFalse(A.strict_bank(truth, "b"))
        truth["a"]["status"] = "INFEASIBLE"
        self.assertTrue(A.strict_bank(truth, "b"))
        truth["b"]["status"] = "REFERENCE_UNAVAILABLE"
        self.assertFalse(A.strict_bank(truth, "b"))

    def test_validator_filters_nonimprovement_and_freezes_unique_order(self):
        candidates = [{"id": x, "c1": i, "c2": 0} for i, x in enumerate("bacd")]
        assessed = {
            x: {"feasible": True, "objective": v}
            for x, v in zip("bacd", [10, 12, 9, 8], strict=True)
        }
        self.assertEqual(A.shortlist(candidates, assessed, "b", 1), ["d"])
        self.assertEqual(A.shortlist(candidates, assessed, "b", 5), ["d", "c"])
        assessed["d"]["feasible"] = False
        self.assertEqual(A.shortlist(candidates, assessed, "b", 5), ["c"])
        assessed["b"]["objective"] = None
        self.assertEqual(A.shortlist(candidates, assessed, "b", 5), [])
        self.assertEqual(A.shortlist(candidates, assessed, "b", 5, 11), ["c"])

    def test_safety_only_breaks_exact_utility_ties(self):
        ranks = A.lex_ranks([1, 1, 1 + 1e-13, 1], [0, 1, 99, 0], [0, 0, 99, 1])
        self.assertLess(ranks[2], ranks[0])
        self.assertLess(ranks[0], ranks[3])
        self.assertLess(ranks[3], ranks[1])

    def test_shared_conditions_are_not_independent_signs(self):
        self.assertEqual(A.sign_test_p([1, 1, 1], ["same"] * 3, 0), 0.5)
        self.assertEqual(A.sign_test_p([1, 1, 1], ["a", "b", "c"], 0), 0.125)
        self.assertEqual(A.sign_test_p([1, 1], ["a", "b"], 1), 1)
        self.assertGreaterEqual(A.sign_test_p([1, 1], ["a", "b"], 2), 0.5)

    def test_paired_question_bootstrap_keeps_same_denominator(self):
        _, inherited = A.inherited_modules()
        values = np.array([[1, 5], [0, 2]])
        boot = inherited.boot_means(values, [0, 1], np.array([[1, 1], [0, 2], [0, 0]]))
        self.assertEqual((boot[0, 0] - boot[0, 1]), 2)
        self.assertEqual((boot[1, 0] - boot[1, 1]), 3)
        self.assertTrue(np.isnan(boot[2]).all())

    def test_condition_token_charge_rescaling_is_coherent(self):
        analysis, _ = A.inherited_modules()
        gain = np.array([30, 120])
        tokens = np.array([3, 4])
        old = analysis.utility(gain, tokens, 0.1, 120)
        new = analysis.utility(gain, tokens, 0.05, 240)
        np.testing.assert_allclose(old / 2, new)
        self.assertLess(old[0], 30 / 120 - 0.1)

    def test_no_empty_population_assigned_zero_utility(self):
        data = json.loads(PATH.with_name("results.json").read_text(encoding="utf-8"))
        empty = [p for p in data["profiles"] if p["n"] == 0]
        self.assertTrue(empty)
        for row in empty:
            self.assertEqual(row["status"], "EMPTY_BANK_NOT_ZERO_VALUE")
            self.assertNotIn("cheap_U", row)
            self.assertNotIn("always_abstain_U", row)
        for row in data["profiles"]:
            if row["n"] == 1:
                self.assertFalse(row["paired_CI_available"])
                self.assertIsNone(row["paired_CI95_lower_positive"])
                self.assertTrue(
                    all(m["paired_CI95"] is None for m in row["per_member"])
                )


if __name__ == "__main__":
    unittest.main()
