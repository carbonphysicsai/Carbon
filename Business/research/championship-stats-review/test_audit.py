"""Numerical diagnostic checks; no owner-provided files required by test discovery."""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "championship_audit", Path(__file__).with_name("audit.py")
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditTest(unittest.TestCase):
    def test_original_fixed_seed_null_count(self):
        self.assertEqual(AUDIT.original_null_count(), 36)

    def test_holm_step_down_and_stop(self):
        normal = AUDIT.NORMAL
        z = np.array(
            [
                [normal.inv_cdf(1 - p) for p in row]
                for row in [[0.02, 0.03], [0.03, 0.04]]
            ]
        )
        np.testing.assert_array_equal(
            AUDIT.holm_rejections(z, 0.05), [[True, True], [False, False]]
        )

    def test_pair_permutation_does_not_change_holm(self):
        z = np.array([[3.0, 1.0, 2.8]])
        expected = AUDIT.holm_rejections(z, 0.05)
        np.testing.assert_array_equal(
            AUDIT.holm_rejections(z[:, ::-1], 0.05), expected[:, ::-1]
        )

    def test_negative_evidence_cannot_cross(self):
        mask = AUDIT.crossings(np.full((4, 14), -1000.0), 2000, 0.46, 0.05)
        self.assertFalse(mask.any())

    def test_increasing_variance_proxy_raises_boundary(self):
        counts = np.array([2000, 4000, 28000])
        self.assertTrue(
            np.all(
                AUDIT.boundary(2000, 0.92, 0.05, counts)
                > AUDIT.boundary(2000, 0.46, 0.05, counts)
            )
        )

    def test_zero_count_interval_and_invalid_trials(self):
        low, point, high = AUDIT.wilson(0, 100)
        self.assertEqual(low, 0)
        self.assertEqual(point, 0)
        self.assertTrue(math.isclose(high, 0.03699349820698568))
        with self.assertRaises(ValueError):
            AUDIT.wilson(1, 0)


if __name__ == "__main__":
    unittest.main()
