"""Diagnostics for the public research estimands, costs and source identity."""
from pathlib import Path
import unittest

import analyze as a


class ResolutionTests(unittest.TestCase):
    def test_none_feasible_is_resolved_when_proven(self):
        r = {"references": {"q": {"split": "development", "status_counts": {"FEASIBLE": 0, "INFEASIBLE": 2, "UNRESOLVED": 0, "REFERENCE_UNAVAILABLE": 0}}},
             "decisions": {"m": {"q": {"outcome": {"kind": "CORRECT_ABSTENTION", "decision_loss": 0}}}}}
        row = a.question_rows(r, ["m"])[0]
        self.assertTrue(row["common_resolved"])
        self.assertTrue(row["fully_all_infeasible"])
        r["references"]["q"]["status_counts"].update({"INFEASIBLE": 1, "UNRESOLVED": 1})
        r["decisions"]["m"]["q"]["outcome"] = {"kind": "ABSTENTION_UNRESOLVED", "decision_loss": None}
        row = a.question_rows(r, ["m"])[0]
        self.assertFalse(row["common_resolved"])
        self.assertFalse(row["fully_all_infeasible"])
        self.assertTrue(row["no_known_feasible_but_uncertain"])

    def test_missing_member_is_not_resolved(self):
        r = {"references": {"q": {"split": "development", "status_counts": {"FEASIBLE": 1, "INFEASIBLE": 1, "UNRESOLVED": 0, "REFERENCE_UNAVAILABLE": 0}}}, "decisions": {}}
        row = a.question_rows(r, ["m"])[0]
        self.assertEqual(row["missing_member_records"], 1)
        self.assertFalse(row["common_resolved"])

    def test_planning_rounding_and_units(self):
        self.assertEqual(a.offers(27 / 48), 267)
        self.assertAlmostEqual(a.budget(27 / 48)["CPU_hours_ASSUMPTION"]["base"], 194.91)
        self.assertEqual(a.offers(7 / 12), 258)
        self.assertAlmostEqual(a.budget(1)["CPU_hours_ASSUMPTION"]["base"], 109.5)

    def test_public_masks_and_adverse_refinement(self):
        directory = Path(__file__).parent / "inputs"
        if not directory.exists():
            self.skipTest("Exact public blobs must be supplied; no automatic fetch")
        data, provenance = a.read_inputs(directory)
        result = a.run(data, provenance)
        p = result["pooled_EV4_EV5"]
        self.assertEqual((p["offered"], p["common_resolved"], p["missing_member_records"]), (48, 27, 0))
        self.assertEqual(p["fully_all_infeasible"], 9)
        ref = result["reference_refinement"]
        self.assertEqual((ref["cases"], ref["settling_resolved"], ref["status_counts"]["REFERENCE_SOLVER_FAILED"]), (27, 6, 5))
        self.assertEqual(len(ref["critical_cases_hindsight"]), 1)
        self.assertEqual([c["after"] for c in ref["outcome_changes"]], ["SELECTED_INFEASIBLE", "SELECTED_INFEASIBLE"])

    def test_export_lf_and_provenance(self):
        p = Path(__file__).parent / "results.json"
        if not p.exists():
            self.skipTest("Research result not generated")
        self.assertNotIn(b"\r", p.read_bytes())


if __name__ == "__main__":
    unittest.main()
