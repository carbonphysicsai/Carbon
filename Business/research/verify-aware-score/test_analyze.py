"""Contract and statistical diagnostics; no physical computation."""

import math
import unittest
from unittest.mock import MagicMock

import analyze as a
import numpy as np


class VerifyAwareTests(unittest.TestCase):
    def test_no_unverified_candidate_can_be_returned(self):
        refs = {
            "unsafe": {"status": "INFEASIBLE"},
            "band": {"status": "UNRESOLVED"},
            "good": {"status": "FEASIBLE", "value": 1000},
        }
        self.assertEqual(
            a.verify_list(["unsafe", "band", "good"], refs, 3, 2)["loss"], 1
        )
        result = a.verify_list(["unsafe", "band", "good"], refs, 3, 3)
        self.assertEqual(result["loss"], 0)
        self.assertEqual(result["value"], 1000)
        self.assertEqual(result["attempts"], 3)

    def test_best_verified_design_and_budget_are_not_model_predictions(self):
        refs = {
            "poor": {"status": "FEASIBLE", "value": 1100},
            "best": {"status": "FEASIBLE", "value": 1000},
        }
        self.assertAlmostEqual(
            a.verify_list(["poor", "best"], refs, 2, 1)["loss"], 100 / 120
        )
        self.assertEqual(a.verify_list(["poor", "best"], refs, 2, 2)["loss"], 0)
        self.assertEqual(a.verify_list(["poor", "best"], refs, 1, 2)["attempts"], 1)

    def test_reference_failure_and_none_verified_remain_separate(self):
        refs = {
            "failed": {"status": "REFERENCE_UNAVAILABLE"},
            "good": {"status": "FEASIBLE", "value": 1000},
        }
        self.assertIsNone(a.verify_list(["failed", "good"], refs, 2, 2)["loss"])
        self.assertEqual(a.verify_list([], refs, 2, 2)["loss"], 1)
        self.assertIsNone(
            a.return_loss({"kind": "SELECTED_REFERENCE_UNAVAILABLE"}, 120)
        )
        self.assertEqual(a.return_loss({"kind": "SELECTED_UNRESOLVED"}, 120), 1)
        self.assertEqual(a.return_loss({"kind": "CORRECT_ABSTENTION"}, 120), 1)

    def test_duplicate_action_cannot_buy_extra_budget(self):
        refs = {"good": {"status": "FEASIBLE", "value": 1000}}
        with self.assertRaises(ValueError):
            a.verify_list(["good", "good"], refs, 2, 2)
        with self.assertRaises(ValueError):
            a.verify_list(["secret"], refs, 1, 1)
        with self.assertRaises(ValueError):
            a.verify_list(["good"], refs, 1, 1, unit=0)
        with self.assertRaises(ValueError):
            a.verify_list(
                ["good"], {"good": {"status": "FEASIBLE", "value": float("nan")}}, 1, 1
            )

    def test_tau_ties_gates_and_direction(self):
        self.assertEqual(a.tau([0.8, 0.7, 0.6], [0.1, 0.2, 0.3]), 1)
        self.assertEqual(a.tau([0.8, 0.7, 0.6], [0.3, 0.2, 0.1]), -1)
        self.assertIsNone(a.tau([0.5, 0.5], [0.1, 0.2]))
        self.assertAlmostEqual(
            a.tau([0.8, 0.8, 0.6], [0.1, 0.2, 0.3]), 2 / math.sqrt(6)
        )
        self.assertEqual(
            a.passing([0.05, None], 0.05, "exceeds").tolist(), [True, False]
        )
        self.assertEqual(
            a.passing([0.05, None], 0.05, "at_least").tolist(), [False, False]
        )

    def test_bounds_do_not_invent_missing_ranks(self):
        def data(f, fa, fr, u, kind, selected="first"):
            return {
                "references": {
                    "V-T20-S.2": {
                        "split": "verification",
                        "status_counts": {
                            "FEASIBLE": f,
                            "INFEASIBLE": 5,
                            "UNRESOLVED": u,
                        },
                    }
                },
                "decisions": {
                    "m-s0": {
                        "V-T20-S.2": {
                            "agreement": {
                                "false_acceptances": fa,
                                "false_rejections": fr,
                            },
                            "outcome": {"kind": kind, "selected": selected},
                        }
                    }
                },
            }

        uncertain = data(2, 3, 0, 2, "SELECTED_INFEASIBLE")
        self.assertEqual(
            a.shortlist_bounds(uncertain, ["m-s0"], "verification", 2)[
                "feasible_return_fraction_bounds"
            ],
            [0, 1],
        )
        self.assertEqual(
            a.shortlist_bounds(uncertain, ["m-s0"], "verification", 6)[
                "feasible_return_fraction_bounds"
            ],
            [1, 1],
        )
        self.assertEqual(
            a.shortlist_bounds(uncertain, ["m-s0"], "verification", 7)[
                "mean_service_loss_bounds"
            ],
            [0, 0],
        )
        rejected_all = data(2, 3, 2, 0, "SELECTED_INFEASIBLE")
        self.assertEqual(
            a.shortlist_bounds(rejected_all, ["m-s0"], "verification", 6)[
                "feasible_return_fraction_bounds"
            ],
            [0, 0],
        )
        abstains = data(2, 0, 2, 0, "MISSED_OPPORTUNITY", None)
        self.assertEqual(
            a.shortlist_bounds(abstains, ["m-s0"], "verification", 6)[
                "feasible_return_fraction_bounds"
            ],
            [0, 0],
        )

    def test_public_hash_refuses_mutation(self):
        directory = MagicMock()
        directory.__truediv__.return_value.read_bytes.return_value = b"{}"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            a.read_inputs(directory)

    def test_verifier_harness_controls_obvious_attack(self):
        refs = {
            "bad": {"status": "INFEASIBLE"},
            "best": {"status": "FEASIBLE", "value": 1000},
            "worse": {"status": "FEASIBLE", "value": 1120},
        }
        # Padding with an unsafe decoy spends a scarce slot, and cannot help.
        good = a.verify_list(["worse", "best"], refs, 2, 2)
        attacked = a.verify_list(["bad", "worse", "best"], refs, 3, 2)
        self.assertEqual(good["loss"], 0)
        self.assertEqual(attacked["loss"], 1)
        # Any numeric accuracy/predicted objective changes with the same frozen
        # order have no input path to the pure verified-return score.
        for _ in np.linspace(-100, 100, 7):
            self.assertEqual(a.verify_list(["worse", "best"], refs, 2, 2), good)


if __name__ == "__main__":
    unittest.main()
