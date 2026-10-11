"""Structural tests of dependence, budget and release calculations."""

import unittest

import analyze as a


class BankStatisticsTests(unittest.TestCase):
    def test_frozen_duplicates_are_not_new_cases(self):
        self.assertEqual(a.effective_n([5] * 20, 1), 20)
        self.assertEqual(a.effective_n([5] * 20, 0), 100)
        self.assertEqual(a.effective_n([1] * 100, 1), 100)

    def test_unbalanced_reuse_loses_information(self):
        self.assertLess(a.effective_n([1, 9], 1), a.effective_n([5, 5], 1))

    def test_active_overlap_not_allowed(self):
        with self.assertRaises(ValueError):
            a.publication_lag(5, 1, 3)
        self.assertEqual(a.publication_lag(5, 3, 3), 15)
        self.assertEqual(a.publication_lag(1, 1, 3), 3)

    def test_yield_and_exposure_cost(self):
        self.assertEqual(a.cost_per_window(100, 5, 1), 20)
        self.assertEqual(a.cost_per_window(100, 5, 1, 0.5), 40)
        with self.assertRaises(ValueError):
            a.cost_per_window(100, 5, 1, 0)

    def test_random_tail_is_longer_than_one_case_mean(self):
        self.assertGreater(a.random_repeat_max_quantile(98, 0.049, 0.95), 1 / 0.049)
        r = a.report()
        self.assertEqual(
            r["classes"]["CFD_class"]["fresh_cases_per_100_appearances"], 5
        )


if __name__ == "__main__":
    unittest.main()
