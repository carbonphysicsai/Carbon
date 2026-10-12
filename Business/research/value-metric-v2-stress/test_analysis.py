"""Meaningful algebraic boundaries of the draft, without public data or solvers."""

import json
import unittest

import aggregate
import analyze_public as a
import numpy as np


class DraftBoundaryTests(unittest.TestCase):
    def test_aggregate_json_preserves_numpy_and_rejects_nonfinite(self):
        value = {"scores_real_100": [0.0, 2.0], "count": np.int64(2)}
        self.assertEqual(
            json.loads(aggregate.readable_json(value)),
            {"scores_real_100": [0.0, 2.0], "count": 2},
        )
        with self.assertRaises(ValueError):
            aggregate.readable_json({"U": float("nan")})
        with self.assertRaises(TypeError):
            aggregate.numpy_scalar(object())

    def test_abstention_zero_for_all_scenarios(self):
        for kappa in a.KAPPAS:
            for unit in a.UNITS:
                for eta in a.ETAS:
                    self.assertEqual(a.utility(0, 0, kappa, unit, 0, eta), 0)

    def test_positive_gain_can_have_negative_utility(self):
        useful_gross = a.utility(30, 1, 0.5, 120)
        self.assertLess(useful_gross, 0)
        self.assertEqual(a.rank_interval(0, [useful_gross])["best"], 1)

    def test_no_gain_baseline_is_not_zero_physical_gain(self):
        self.assertIsNone(a.clipped_gain_seconds("INFEASIBLE", 1000, 500))
        self.assertIsNone(a.clipped_gain_seconds("UNRESOLVED", 1000, 500))
        self.assertIsNone(a.clipped_gain_seconds("REFERENCE_UNAVAILABLE", None, 500))
        self.assertEqual(a.clipped_gain_seconds("FEASIBLE", 1000, 1100), 0)

    def test_coherent_units_preserve_ranks(self):
        gains = np.array([240.0, 30.0, 0.0])
        attempts = np.array([3, 1, 0])
        x = a.utility(gains, attempts, 0.1, 120)
        y = a.utility(gains, attempts, 0.05, 240)
        np.testing.assert_allclose(y, x / 2)
        self.assertEqual(a.tau(x, y), 1)

    def test_additional_checks_without_gain_cannot_raise_utility(self):
        for kappa in a.KAPPAS:
            self.assertLess(
                a.utility(120, 5, kappa, 120), a.utility(120, 1, kappa, 120)
            )

    def test_equal_gain_and_total_cost_do_not_order_unsafe_counts(self):
        # The draft's scalar has no unsafe-count term. A separate gate is needed.
        safe = a.utility(240, 3, 0.1, 120)
        two_rejected_unsafe_with_same_gain_and_attempts = a.utility(240, 3, 0.1, 120)
        self.assertEqual(safe, two_rejected_unsafe_with_same_gain_and_attempts)

    def test_zero_gain_controls_cannot_have_positive_net(self):
        for attempts in range(6):
            for kappa in a.KAPPAS:
                self.assertLessEqual(a.utility(0, attempts, kappa, 120), 0)

    def test_numeric_ties_keep_rank_interval(self):
        self.assertEqual(
            a.rank_interval(0, [1, 0, 0, -1]), {"best": 2, "worst": 4, "of": 5}
        )
        self.assertIsNone(a.tau([0, 0], [1, 1]))


if __name__ == "__main__":
    unittest.main()
