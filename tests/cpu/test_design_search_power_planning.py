"""Synthetic checks for the development-only power-planning model."""

import json
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.dev import design_search_power_planning as planning

MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs/development/challenge_pipeline/power-planning/assumptions.v1.json"
)


def _small_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["replicates"] = 3
    manifest["windows"] = [1, 2]
    for challenge in manifest["challenges"]:
        challenge["independent_banks"] = [1, 8]
        challenge["questions_per_batch"] = [4]
        challenge["exposure_limits"] = [5]
    return manifest


class PowerPlanningTests(unittest.TestCase):
    def test_sign_test_respects_independent_bank_count(self):
        self.assertEqual(planning.exact_sign_power(4, 1.0, 0.05), 0)
        self.assertEqual(planning.exact_sign_power(5, 1.0, 0.05), 1)
        self.assertEqual(planning.exact_sign_power(1, 0.9, 0.05), 0)
        self.assertLessEqual(planning.exact_sign_power(32, 0.5, 0.05), 0.05)
        self.assertGreater(
            planning.exact_sign_power(32, 0.8, 0.05),
            planning.exact_sign_power(32, 0.6, 0.05),
        )

    def test_shared_exposure_is_charged_across_question_ids_and_windows(self):
        path = planning._path_cluster_counts(
            bank_questions=25,
            independent_banks=1,
            exposure=5,
            k=4,
            windows=2,
            seed="toy",
        )
        self.assertEqual(path, [1, None])
        self.assertEqual(
            planning._path_cluster_counts(
                bank_questions=25,
                independent_banks=1,
                exposure=5,
                k=8,
                windows=1,
                seed="toy",
            ),
            [None],
        )

    def test_simulation_replays_and_never_invents_one_bank_power(self):
        manifest = _small_manifest()
        first = planning.simulate(manifest)
        self.assertEqual(first, planning.simulate(manifest))
        self.assertTrue(first)
        self.assertTrue(all("case" not in row and "winner" not in row for row in first))
        for row in first:
            if row["independent_bank_clusters_ASSUMPTION"] == 1:
                self.assertIn(row["detection_probability_ASSUMPTION"], (0, None))
        self.assertTrue(
            any(
                row["independent_bank_clusters_ASSUMPTION"] == 8
                and row["detection_probability_ASSUMPTION"] is not None
                for row in first
            )
        )

    def test_incomplete_or_invalid_assumptions_are_refused(self):
        edits = [
            lambda m: m["challenges"][0]["severity_levels"][0]["by_quantity"].pop(
                "every_charge_plating"
            ),
            lambda m: m["challenges"][0]["effect_assumptions"].pop("path_aware"),
            lambda m: m["challenges"][0]["effect_assumptions"][
                "edge_optimist"
            ].__setitem__(0, float("nan")),
            lambda m: m["challenges"][0]["independent_banks"].append(26),
        ]
        for edit in edits:
            with self.subTest(edit=edit):
                manifest = deepcopy(_small_manifest())
                edit(manifest)
                with self.assertRaises(ValueError):
                    planning.simulate(manifest)


if __name__ == "__main__":
    unittest.main()
