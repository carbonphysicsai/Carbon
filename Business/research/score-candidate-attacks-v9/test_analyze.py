"""Public toy controls for the research audit; no model or evaluator runs."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "research_attacks_v9", Path(__file__).with_name("analyze.py")
)
assert SPEC is not None and SPEC.loader is not None
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def registry_fixture():
    return {
        "candidates": [
            {"id": "A", "weights": {"a": 1}},
            {"id": "R", "weights": {"r": 1}},
            {"id": "P", "weights": {"p": 1}},
            {"id": "ARP", "weights": {"a": 1 / 3, "r": 1 / 3, "p": 1 / 3}},
            {"id": "V3", "weights": {"v3": 1}},
            {"id": "ARP-V3", "weights": {"a": 0.25, "r": 0.25, "p": 0.25, "v3": 0.25}},
            {
                "id": "ENV/ARP",
                "weights": {"a": 1 / 3, "r": 1 / 3, "p": 1 / 3},
                "gate": {"measure": "envelope", "cutoff": 1},
            },
            {
                "id": "ENV/ARP-V3",
                "weights": {"a": 0.25, "r": 0.25, "p": 0.25, "v3": 0.25},
                "gate": {"measure": "envelope", "cutoff": 1},
            },
            {"id": "A-Q", "weights": {"a": 0.5, "q": 0.5}},
            {
                "id": "G-FEAS/A-Q>",
                "kind": "gate_sweep",
                "base": "A-Q",
                "measure": "feasibility",
                "grid": [0.05],
                "comparison": "exceeds",
            },
        ]
    }


class ResearchAttacksV9Tests(unittest.TestCase):
    def test_missing_legs_are_not_fabricated(self):
        self.assertIsNone(A.geometric({"a": 0.9}, {"a": 1 / 3, "r": 1 / 3, "p": 1 / 3}))
        self.assertEqual(A.geometric({"a": 0.9}, {"a": 1}), 0.9)

    def test_pessimism_is_invisible_to_one_sided_optimism(self):
        for row in A.structural_attacks(registry_fixture())["one_sided_pessimism"]:
            self.assertEqual(row["p"], 1)
            self.assertEqual(row["envelope_optimism"], 0)
            self.assertEqual(row["predicted_feasible_actions"], 0)
            self.assertEqual(row["verified_service_loss"], 1)

    def test_boundary_credit_can_compensate_under_ARP_but_not_this_V3_toy(self):
        for row in A.structural_attacks(registry_fixture())["boundary_gate"]:
            rules = row["rules"]
            self.assertGreater(rules["ARP"]["score_delta"], 0)
            self.assertTrue(rules["ENV/ARP"]["attack"]["admissible"])
            self.assertTrue(rules["G-FEAS/A-Q>@0.05"]["attack"]["admissible"])
            self.assertLess(rules["V3"]["score_delta"], 0)
            self.assertGreater(row["attack_service_loss"], row["base_service_loss"])

    def test_fixed_lists_protect_V3_while_blends_gain_credit(self):
        row = A.structural_attacks(registry_fixture())["fixed_list_blend"][1]
        self.assertEqual(row["verified_value_delta"], 0)
        self.assertEqual(row["rules"]["V3"], 0)
        self.assertGreater(row["rules"]["ARP-V3"], 0)
        self.assertGreater(row["rules"]["G-FEAS/A-Q>@0.05"], 0)

    def test_padding_duplicates_and_overlength_are_refused(self):
        toy = A.structural_attacks(registry_fixture())["list_padding"]
        self.assertEqual(toy["fixed_first_three"]["loss"], 1)
        self.assertEqual(toy["fixed_first_three"]["attempts"], 3)
        self.assertEqual(
            toy["overlength_padding_refused"]["status"], "REFUSED_COMMITMENT"
        )
        self.assertEqual(toy["duplicates_refused"]["status"], "REFUSED_COMMITMENT")
        self.assertEqual(toy["valid_safe_first"]["loss"], 0)

    def test_reference_failure_is_not_candidate_failure(self):
        bank = {"x": {"status": "REFERENCE_UNAVAILABLE", "value": None}}
        self.assertIsNone(A.verify_list(["x"], bank, 3, 1200)["loss"])
        self.assertIsNone(
            A.service_loss({"kind": "SELECTED_REFERENCE_UNAVAILABLE"}, 120)
        )
        self.assertEqual(A.service_loss({"kind": "SELECTED_UNRESOLVED"}, 120), 1)
        bank["good"] = {"status": "FEASIBLE", "value": 100}
        self.assertIsNone(A.verify_list(["good"], bank, 3, 1200)["loss"])

    def test_invalid_reference_and_units_are_refused(self):
        with self.assertRaises(ValueError):
            A.verify_list([], {"bad": {"status": "UNKNOWN"}}, 3, 1200)
        with self.assertRaises(ValueError):
            A.verify_list([], {}, 3, 0)
        with self.assertRaises(ValueError):
            A.service_loss(
                {"kind": "SELECTED_FEASIBLE", "gap_to_best_in_set_s": -1}, 120
            )

    def test_no_feasible_certificate_is_not_always_NONE_FEASIBLE(self):
        self.assertEqual(
            A.reference_family_state({"INFEASIBLE": 2}), "SETTLED_NONE_FEASIBLE"
        )
        self.assertEqual(
            A.reference_family_state({"INFEASIBLE": 2, "UNRESOLVED": 1}),
            "UNRESOLVED_NO_CERTIFIED_FEASIBLE",
        )
        self.assertEqual(
            A.reference_family_state({"FEASIBLE": 1, "REFERENCE_UNAVAILABLE": 1}),
            "REFERENCE_UNAVAILABLE",
        )
        self.assertEqual(A.reference_family_state({}), "NO_REFERENCE_EVIDENCE")

    def test_integer_gate_boundaries_and_registered_strictness(self):
        self.assertEqual(A.allowance(100, 0.05), 5)
        self.assertEqual(A.allowance(100, 0.05, False), 4)
        self.assertEqual(A.allowance(74, 0.005), 0)
        self.assertEqual(A.allowance(74, 0.02), 1)
        self.assertEqual(A.allowance(74, 0.05), 3)

    def test_unknown_and_outside_conditions_are_distinct(self):
        self.assertIs(A.condition_inside("V-T39-S0.24"), False)
        self.assertIs(A.condition_inside("D-T16-S0.30"), True)
        self.assertIsNone(A.condition_inside("other-public-id"))

    def test_tau_and_tied_ranks_and_clone_sensitivity(self):
        self.assertEqual(A.tau([3, 2, 1], [1, 2, 3]), 1)
        self.assertIsNone(A.tau([1, 1], [1, 2]))
        self.assertEqual(A.rank_interval(2, [3, 2, 2, 1]), [2, 4])
        before = A.tau([3, 2, 1], [1, 3, 2])
        after = A.tau([3, 2, 1, 2, 2], [1, 3, 2, 3, 3])
        self.assertNotEqual(before, after)

    def test_digest_refusal_precedes_analysis(self):
        with (
            patch.object(Path, "read_bytes", return_value=b"{}"),
            self.assertRaisesRegex(ValueError, "Public input digest mismatch"),
        ):
            A.load_public(Path("public-toy"))


if __name__ == "__main__":
    unittest.main()
