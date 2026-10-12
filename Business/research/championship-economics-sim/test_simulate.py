"""Research invariants, analytical controls and synthetic grading checks."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "economics_research", Path(__file__).with_name("simulate.py")
)
assert SPEC is not None and SPEC.loader is not None
SIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SIM)
MANIFEST = json.loads(
    Path(__file__).with_name("assumptions.json").read_text(encoding="utf-8")
)


class EconomicsTests(unittest.TestCase):
    def cfg(self, **changes):
        return {**SIM.base_config(MANIFEST), **changes}

    def test_strict_margin_and_noise_and_king_tie(self):
        observed = np.array([[1.0, 0.9775], [1.0, 0.95], [1.0, 1.0]])
        se = np.array([[0.0, 0.001], [0.0, 0.02], [0.0, 0.0]])
        np.testing.assert_array_equal(
            SIM.select_winner(observed, se, np.zeros(3, dtype=int), 0.0225, 3.09),
            [0, 0, 0],
        )

    def test_exact_copy_has_zero_difference_and_cannot_win(self):
        q = np.ones((500, 11))
        ids = np.zeros_like(q, dtype=int)
        inc = np.zeros(500, dtype=int)
        obs, se = SIM.shared_batch(
            np.random.default_rng(9), q, inc, ids, ids, self.cfg()
        )
        np.testing.assert_allclose(
            obs, np.repeat(obs[:, :1], 11, axis=1), atol=0, rtol=0
        )
        np.testing.assert_array_equal(se, np.zeros_like(q))
        np.testing.assert_array_equal(
            SIM.select_winner(obs, se, inc, 0.0225, 3.09), inc
        )

    def test_equal_best_qualifiers_keep_king(self):
        observed = np.array([[1.0, 0.95, 0.95]])
        se = np.array([[0.0, 0.001, 0.001]])
        np.testing.assert_array_equal(
            SIM.select_winner(observed, se, np.array([0]), 0.0225, 3.09), [0]
        )

    def test_shared_gaussian_mean_and_variance_match_theory(self):
        n = 20000
        q = np.ones((n, 3))
        ids = np.broadcast_to(np.arange(3), q.shape)
        inc = np.zeros(n, dtype=int)
        obs, se = SIM.shared_batch(
            np.random.default_rng(9), q, inc, ids, np.full_like(ids, -1), self.cfg()
        )
        d = obs[:, :1] - obs[:, 1:]
        expected_var = 2 * 0.4**2 * (1 - 0.75) / 4000
        self.assertAlmostEqual(float(np.var(d[:, 0])) / expected_var, 1, delta=0.03)
        self.assertAlmostEqual(
            float(np.mean(se[:, 1] ** 2)) / expected_var, 1, delta=0.002
        )
        self.assertAlmostEqual(float(np.corrcoef(d.T)[0, 1]), 0.5, delta=0.025)

    def test_t_large_df_value_and_belief_cdf(self):
        # Independent SciPy value checked during research; no SciPy dependency.
        self.assertAlmostEqual(
            SIM.t_critical(0.01, 10, 4000), 3.0922715798958316, delta=1e-9
        )
        self.assertLess(SIM.t_critical(0.01, 10, 4000), SIM.t_critical(0.01, 10, 2000))
        for x in np.linspace(-8, 8, 81):
            self.assertAlmostEqual(
                float(SIM.normal_cdf(x)), SIM.NORMAL.cdf(float(x)), delta=8e-8
            )

    def test_geometric_rent_and_array_hazards(self):
        self.assertAlmostEqual(float(SIM.rent(1000, 0.25, 0.5, 0, 1, horizon=90)), 500)
        self.assertAlmostEqual(float(SIM.rent(1000, 0.25, 1, 0, 1, horizon=90)), 22500)
        v = SIM.rent(1000, 0.25, 0.9, np.array([0.01, 0.1]), 0.99)
        self.assertGreater(v[0], v[1])

    def test_self_advance_is_not_crown_change_or_primary_clock_reset(self):
        grow = {"expert": 0.02, "steady": 0, "imitator": 0, "holder": 0, "newcomer": 0}
        cfg = self.cfg(
            days=90,
            behavior="fixed",
            experts=1,
            steady=0,
            imitators=0,
            holders=1,
            newcomers=1,
            growth_by_role=grow,
            breakthrough_probability=0,
            case_sd=0.001,
            self_reset=False,
        )
        primary = SIM.run_population(cfg, 8)["metrics"]
        changed = SIM.run_population({**cfg, "self_reset": True}, 8)["metrics"]
        self.assertGreater(primary["self_advances"]["base"], 0)
        self.assertEqual(primary["crown_changes_per_30_days"]["base"], 0)
        self.assertEqual(primary["payout_clock_resets"]["base"], 0)
        self.assertAlmostEqual(
            primary["paid_fraction_of_challenge_allocation"]["base"], 2 / 90
        )
        self.assertGreater(
            changed["paid_fraction_of_challenge_allocation"]["base"],
            primary["paid_fraction_of_challenge_allocation"]["base"],
        )

    def test_fixed_effort_split_and_decay_do_not_change_scientific_trajectory(self):
        a = SIM.run_population(
            self.cfg(days=90, behavior="fixed", decay=0.5, challenges=4), 8
        )
        b = SIM.run_population(
            self.cfg(days=90, behavior="fixed", decay=0.9, challenges=8), 8
        )
        self.assertEqual(
            a["metrics"]["crown_changes_per_30_days"],
            b["metrics"]["crown_changes_per_30_days"],
        )
        self.assertEqual(
            a["metrics"]["log_accuracy_improvement"],
            b["metrics"]["log_accuracy_improvement"],
        )
        self.assertGreater(
            b["metrics"]["paid_fraction_of_challenge_allocation"]["base"],
            a["metrics"]["paid_fraction_of_challenge_allocation"]["base"],
        )

    def test_reproducibility_conservation_and_parameter_refusal(self):
        cfg = self.cfg(days=90, behavior="adaptive")
        a = SIM.run_population(cfg, 6)
        self.assertEqual(a, SIM.run_population(cfg, 6))
        self.assertLessEqual(
            a["metrics"]["paid_fraction_of_challenge_allocation"]["base"], 1
        )
        self.assertAlmostEqual(
            a["metrics"]["paid_fraction_of_subnet_miner_pool"]["base"],
            a["metrics"]["paid_fraction_of_challenge_allocation"]["base"] / 4,
        )
        with self.assertRaises(ValueError):
            SIM.run_population({**cfg, "decay": 1.1}, 6)


if __name__ == "__main__":
    unittest.main()
