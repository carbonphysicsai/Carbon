"""Tests of falsifiable research calculations; no physical model runs."""

import unittest
from pathlib import Path
from unittest.mock import patch

import analyze as a


class AttackAuditTests(unittest.TestCase):
    def test_band_is_no_return_without_relabelling(self):
        self.assertEqual(a.service_loss({"kind": "SELECTED_UNRESOLVED"}, 120), 1)
        self.assertIsNone(
            a.service_loss({"kind": "SELECTED_REFERENCE_UNAVAILABLE"}, 120)
        )

    def test_verified_regret_is_bounded_and_oriented(self):
        self.assertEqual(
            a.service_loss(
                {"kind": "SELECTED_FEASIBLE", "gap_to_best_in_set_s": 0}, 120
            ),
            0,
        )
        self.assertEqual(
            a.service_loss(
                {"kind": "SELECTED_FEASIBLE", "gap_to_best_in_set_s": 240}, 120
            ),
            1,
        )
        with self.assertRaises(ValueError):
            a.service_loss(
                {"kind": "SELECTED_FEASIBLE", "gap_to_best_in_set_s": -1}, 120
            )

    def test_gate_counts_respect_strictness(self):
        self.assertEqual(a.count_allowance(74, 0.05), 3)
        self.assertEqual(a.count_allowance(100, 0.05), 5)
        self.assertEqual(a.count_allowance(100, 0.05, False), 4)
        self.assertEqual(a.count_allowance(74, 0.005), 0)

    def test_tied_ranks_not_arbitrary(self):
        self.assertEqual(a.interval_rank(0.8, [0.9, 0.8, 0.8, 0.7]), [2, 4])
        self.assertEqual(a.tau([0.9, 0.8, 0.7], [0.1, 0.2, 0.3]), 1)
        self.assertIsNone(a.tau([1, 1], [0.1, 0.2]))

    def test_digest_mismatch_fails_before_analysis(self):
        with (
            patch.object(Path, "read_bytes", return_value=b"{}"),
            self.assertRaisesRegex(ValueError, "Public input mismatch"),
        ):
            a.run(Path("public-fixture"))


if __name__ == "__main__":
    unittest.main()
