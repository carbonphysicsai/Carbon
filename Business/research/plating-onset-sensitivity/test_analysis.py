"""Synthetic structural tests; no production thresholds or public data needed."""

import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "plating_sensitivity", Path(__file__).with_name("analyze.py")
)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def row(margin, reach="PASS", plating="FAIL", temperature="PASS"):
    return {
        "status": "INFEASIBLE",
        "quantities": [{"plating_margin_v": margin}],
        "checks": [
            {
                "reach_cv_in_window": reach,
                "no_plating_onset": plating,
                "peak_temperature": temperature,
            }
        ],
    }


class SensitivityTests(unittest.TestCase):
    def test_distance_bins_are_signed_symmetric_and_upper_inclusive(self):
        for value, expected in [
            (0, "0-0.5"),
            (0.0005, "0-0.5"),
            (0.001, "0.5-1"),
            (0.002, "1-2"),
            (0.004, "2-4"),
            (0.00401, ">4"),
        ]:
            self.assertEqual(analysis.distance_bin(value), expected)
            self.assertEqual(analysis.distance_bin(-value), expected)

    def test_plating_only_censors_without_mutating_original(self):
        source = row(-0.001)
        changed = analysis.sensitive(source, 0.002, "plating_only")
        self.assertEqual(changed["status"], "UNRESOLVED")
        self.assertEqual(source["status"], "INFEASIBLE")
        self.assertEqual(source["checks"][0]["no_plating_onset"], "FAIL")

    def test_independent_failure_remains_infeasible(self):
        for name in ("reach", "temperature"):
            changed = analysis.sensitive(
                row(0.001, **{name: "FAIL"}), 0.002, "plating_only"
            )
            self.assertEqual(changed["status"], "INFEASIBLE")

    def test_far_plating_failure_is_unchanged(self):
        source = row(-0.003)
        self.assertEqual(analysis.sensitive(source, 0.002, "plating_only"), source)

    def test_failed_reference_is_never_resolved(self):
        source = {"status": "REFERENCE_UNAVAILABLE", "objective": None}
        self.assertEqual(analysis.sensitive(source, 0.002, "plating_only"), source)

    def test_literal_censor_is_explicitly_different(self):
        source = row(0.001, reach="FAIL")
        self.assertEqual(
            analysis.sensitive(source, 0.002, "literal_status_censor")["status"],
            "UNRESOLVED",
        )
        self.assertEqual(
            analysis.sensitive(source, 0.002, "plating_only")["status"], "INFEASIBLE"
        )

    def test_empty_or_tied_tau_is_null(self):
        self.assertIsNone(analysis.tau([], []))
        self.assertIsNone(analysis.tau([1, 1], [2, 2]))

    def test_rank_order_direction_and_null_exclusion(self):
        result = analysis.rank_comparison(
            {"a": 1, "b": 2, "c": None}, {"a": 2, "b": 1, "c": None}
        )
        self.assertEqual(result["tau_b"], -1)
        self.assertEqual(result["strict_reversals"], 1)
        self.assertEqual(result["excluded_non_numeric"], 1)


if __name__ == "__main__":
    unittest.main()
