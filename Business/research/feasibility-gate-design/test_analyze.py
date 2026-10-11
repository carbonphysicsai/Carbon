"""Research diagnostics: identity, gate semantics and estimand distinctions."""
import math
from pathlib import Path
import unittest

import analyze as a


class GateTests(unittest.TestCase):
    def test_strict_boundary_and_missing_fail_closed(self):
        self.assertTrue(a.fail(.05, .05, "at_or_above"))
        self.assertFalse(a.fail(.05, .05, "exceeds"))
        self.assertTrue(a.fail(None, .05, "exceeds"))

    def test_exact_interval_extremes(self):
        self.assertAlmostEqual(a.exact_ci(0, 78)[1], 1 - .025 ** (1 / 78))
        self.assertAlmostEqual(a.exact_ci(78, 78)[0], .025 ** (1 / 78))
        self.assertEqual(a.exact_ci(0, 0), [None, None])

    def test_floor_below_negative_scores(self):
        self.assertEqual(a.tau([-math.inf, -.2, -.1], [3, 2, 1]), 1)

    def test_alias_cluster(self):
        self.assertEqual(a.recipe("graphite-run5-p-fa70c075f903-s360154323"), a.recipe("graphite-run5-p-69268f1b74ec-s1551240143"))

    def test_unknown_is_not_safe(self):
        data = {"decisions": {"m": {"q": {"split": "verification", "outcome": {"kind": "SELECTED_UNRESOLVED", "decision_loss": None}}}}}
        self.assertEqual(a.state(data, "m", "verification"), "UNKNOWN_NO_UNSAFE_OBSERVED")
        data["decisions"]["m"]["q"]["outcome"] = {"kind": "SELECTED_INFEASIBLE", "decision_loss": 10}
        self.assertEqual(a.state(data, "m", "verification"), "UNSAFE_OBSERVED")

    def test_published_identity_and_historical_recall(self):
        directory = Path(__file__).parent / "inputs"
        if not directory.exists():
            self.skipTest("Public inputs must be supplied; never fetch automatically")
        data, provenance = a.read_inputs(directory)
        r = data["ev5.json"]
        near = {m: v["near_optimism_bands"] for m, v in data["analysis.json"]["gate"]["members"].items()}
        row = a.summarize_gate(r, near, 2, "at_or_above", "verification")
        self.assertEqual((row["caught_recipes_all_unsafe_seeds"], row["unsafe_recipes"]), (16, 78))
        self.assertEqual(row["fully_resolved_no_unsafe_recipes"], 0)
        self.assertIsNone(row["safe_rejection"])
        self.assertEqual(data["analysis.json"]["results_sha256"], "sha256:" + provenance["ev5.json"]["sha256"])


if __name__ == "__main__":
    unittest.main()
