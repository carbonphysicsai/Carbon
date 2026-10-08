"""Static SPECIFIED-content checks; no solver, model or hidden-store imports.

Toy arithmetic below illustrates document semantics, not a runtime judge,
reference uncertainty calibration, physical evidence or power calculation.
"""

import ast
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTION_DIR = ROOT / "docs/development/challenge_pipeline/question-laws"
PACKET_DIR = ROOT / "docs/development/challenge_pipeline/round1"
FAMILIES = {"f02", "f06", "f08", "f13", "f17"}
CONTROLS = {
    "edge-optimist",
    "over-cautious",
    "sign-error",
    "optimizer-or-lattice-aware",
}
LAW_HEAD = "63d641b65a7e54ee547c1dd7b2aafece3b4d1366"

# Exact #776 grid/continuous recommendations, not registered scientific values.
EXPECTED_AXES = {
    "f02": [
        ("peak_temperature_max", "degC", "<=", [90, 92.5, 95]),
        ("extra_delivered_energy_min", "J", ">=", [300, 600, 900]),
    ],
    "f06": [
        ("coupled_power_fraction_min", "1", ">=", [0.25, 0.30, 0.35]),
        ("reflected_power_fraction_max", "1", "<=", [0.05, 0.10, 0.15]),
    ],
    "f08": [
        ("dynamic_compliance_max", "mm/N", "<=", [0.10, 0.15, 0.20]),
        ("static_compliance_max", "mm/N", "<=", [0.02, 0.03, 0.04]),
        ("mass_max", "kg", "<=", [0.35, 0.45, 0.55]),
    ],
    "f13": [
        ("band_p10_transmission_loss_min", "dB", ">=", [3, 5, 7]),
        ("package_length_max", "mm", "<=", [240, 270, 300]),
        ("package_diameter_max", "mm", "<=", [120, 130, 140]),
    ],
    "f17": [
        ("mixing_index_min", "1", ">=", [0.75, 0.80, 0.85]),
        ("pressure_drop_max", "Pa", "<=", [200, 250, 300]),
        ("residence_time_max", "s", "<=", [15, 20, 25]),
    ],
}


class TestFoundationQuizContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads(
            (QUESTION_DIR / "foundation-quiz-proposals.json").read_text(
                encoding="utf-8"
            )
        )
        cls.rows = {row["family"]: row for row in cls.proposal["challenges"]}
        cls.requirements = json.loads(
            (PACKET_DIR / "requirements.json").read_text(encoding="utf-8")
        )
        cls.document = " ".join(
            (QUESTION_DIR / "foundation-quiz.md").read_text(encoding="utf-8").split()
        )

    def test_exact_five_family_scope_and_no_execution_permissions(self):
        self.assertEqual(self.proposal["ticket"], "CHALLENGE-QUESTION-LAWS-02")
        self.assertEqual(self.proposal["maturity"], "SPECIFIED")
        self.assertFalse(self.proposal["runtime_registration"])
        self.assertEqual(set(self.rows), FAMILIES)
        self.assertEqual(len(self.proposal["challenges"]), len(FAMILIES))
        permissions = self.proposal["permissions"]
        self.assertEqual(
            set(permissions),
            {
                "solver_execution",
                "model_execution",
                "hidden_material",
                "spend",
                "counted_campaign",
                "fresh_confirmation",
                "protocol_transition",
                "runtime_activation",
                "qualification",
            },
        )
        self.assertTrue(all(value is False for value in permissions.values()))

    def test_dependency_and_packet_authority_are_explicit(self):
        basis = self.proposal["basis"]
        self.assertEqual(basis["question_laws_head"], LAW_HEAD)
        self.assertEqual(basis["question_laws_pr"], 776)
        self.assertEqual(basis["packet_limit_authority"], self.requirements["decision"])
        self.assertTrue((QUESTION_DIR / basis["packet_requirements"]).is_file())
        self.assertTrue((QUESTION_DIR / basis["content"]).is_file())
        self.assertIn("PR Lead integrates it first", self.document)

    def test_new_scientific_choices_are_unregistered_recommendations(self):
        choices = self.proposal["common_choices"]
        self.assertTrue({"P", "Q", "w", "variant", "refined_truth"} <= set(choices))
        for name, choice in choices.items():
            with self.subTest(choice=name):
                self.assertEqual(choice["status"], "HUMAN_INPUT")
                self.assertIsNone(choice["registered"])
                self.assertIsNotNone(choice["recommendation"])
        for family, row in self.rows.items():
            with self.subTest(family=family):
                self.assertEqual(row["q3_law"]["status"], "HUMAN_INPUT")
                self.assertIsNone(row["q3_law"]["registered"])
        self.assertIn("Test Lead owns score use, power, thresholds", self.document)

    def test_packet_anchor_values_units_and_directions_are_preserved(self):
        expected_anchor_counts = {"f02": 1, "f06": 2, "f08": 3, "f13": 3, "f17": 3}
        for family, row in self.rows.items():
            packet = self.requirements["challenges"][family]
            self.assertEqual(row["packet"], packet["packet"])
            self.assertTrue((PACKET_DIR / row["packet"]).is_file())
            self.assertEqual(len(row["packet_anchors"]), expected_anchor_counts[family])
            axes = {axis["quantity"]: axis for axis in row["q3_law"]["axes"]}
            for anchor in row["packet_anchors"]:
                with self.subTest(family=family, anchor=anchor["quantity"]):
                    source = packet
                    for component in anchor["requirements_path"]:
                        source = source[component]
                    self.assertEqual(anchor["value"], source)
                    axis = axes[anchor["quantity"]]
                    self.assertEqual(anchor["op"], axis["op"])
                    self.assertEqual(anchor["unit"], axis["unit"])
                    self.assertIn(anchor["value"], axis["grid"])

    def test_law_axes_match_776_for_grid_and_continuous_variants(self):
        for family, expected in EXPECTED_AXES.items():
            axes = self.rows[family]["q3_law"]["axes"]
            self.assertEqual(len(axes), len(expected))
            for axis, (quantity, unit, op, grid) in zip(axes, expected):
                with self.subTest(family=family, axis=quantity):
                    self.assertEqual(axis["quantity"], quantity)
                    self.assertEqual(axis["unit"], unit)
                    self.assertEqual(axis["op"], op)
                    self.assertEqual(axis["grid"], grid)
                    self.assertEqual(axis["continuous"], [grid[0], grid[-1]])

    def test_raw_grid_counts_are_not_answer_diversity_claims(self):
        banks = {"f02": 9, "f06": 256, "f08": 256, "f13": 16, "f17": 45}
        for family, row in self.rows.items():
            law = row["q3_law"]
            raw_count = law["context_count"] * math.prod(
                len(axis["grid"]) for axis in law["axes"]
            )
            self.assertEqual(law["raw_question_grid_upper_bound"], raw_count)
            self.assertEqual(law["bank_candidates"], banks[family])
            self.assertEqual(law["context_count"], 24 if family == "f02" else 1)
            self.assertEqual(law["questions_per_batch"], 8)
            self.assertEqual(row["diversity_status"], "NOT_DEMONSTRATED")
            for field in (
                "expected_winners_P",
                "expected_winners_Q",
                "close_call_rate_P",
                "close_call_rate_Q",
            ):
                self.assertIsNone(row[field])

    def test_every_family_covers_q2_refinement_and_four_controls(self):
        self.assertEqual(set(self.proposal["bad_controls"]), CONTROLS)
        self.assertEqual(set(self.proposal["diagnostics"]), set("abcde"))
        self.assertEqual(len(self.proposal["good_baselines"]), 2)
        for family, row in self.rows.items():
            with self.subTest(family=family):
                self.assertTrue(row["customer_job"])
                self.assertTrue(row["panel"])
                self.assertTrue(row["refinement"])
                self.assertGreaterEqual(len(row["q2_strata"]), 4)
                self.assertEqual(set(row["control_focus"]), CONTROLS)
                self.assertTrue(all(row["control_focus"].values()))
                self.assertTrue(row["q3_law"]["regret_unit"])
        self.assertIn("Diagnostics a through e", self.document)

    def test_all_reference_routes_and_costs_remain_unmeasured(self):
        for family, row in self.rows.items():
            with self.subTest(family=family):
                self.assertEqual(row["reference_route"]["status"], "NOT_DEMONSTRATED")
                self.assertTrue(row["reference_route"]["solver"])
                self.assertTrue(row["reference_route"]["gap"])
                self.assertEqual(row["solve_cost_status"], "UNMEASURED")
                for field in (
                    "cpu_hours_per_case",
                    "bank_cpu_hours",
                    "refinement_cpu_hours",
                    "measured_peak_rss_gib",
                ):
                    self.assertIsNone(row[field])
                self.assertTrue(row["base_work"]["condition"])
        self.assertIn("Validators **never solve references**", self.document)

    def test_silencer_launch_count_is_frequency_work_not_model_queries(self):
        row = self.rows["f13"]
        frequencies = row["frequency_launches"]
        packet = self.requirements["challenges"]["f13"]
        self.assertEqual(frequencies["band_hz"], packet["acoustic"]["band_hz"])
        self.assertEqual(frequencies["initial_step_hz"], packet["acoustic"]["grid_hz"])
        start, stop = frequencies["band_hz"]
        count = (stop - start) // frequencies["initial_step_hz"] + 1
        self.assertEqual(count, 201)
        self.assertEqual(frequencies["frequencies_per_curve"], count)
        bank_launches = count * row["q3_law"]["bank_candidates"]
        self.assertEqual(frequencies["separate_frequency_bank_launches"], bank_launches)
        self.assertEqual(bank_launches, 3216)
        self.assertEqual(row["base_work"]["conditional_base_count"], bank_launches)
        self.assertEqual(
            frequencies["separate_feasibility_panel_launches"],
            count * frequencies["separate_feasibility_panel_cases"],
        )
        self.assertEqual(frequencies["separate_feasibility_panel_launches"], 6030)
        self.assertEqual(
            frequencies["packet_allowance_launches"], packet["grant"]["attempts"]
        )
        self.assertLess(frequencies["packet_allowance_launches"], count)
        self.assertFalse(frequencies["allowance_completes_one_curve"])
        self.assertFalse(frequencies["model_queries_are_reference_launches"])
        self.assertTrue(
            {"mesh rungs", "failed attempts"} <= set(frequencies["excluded"])
        )

    def test_fine_grating_cell_screen_is_not_memory_fit_evidence(self):
        memory = self.rows["f06"]["fine_grid_memory"]
        packet = self.requirements["challenges"]["f06"]
        self.assertEqual(memory["fine_grid_nm"], min(packet["optical"]["mesh_nm"]))
        self.assertEqual(
            memory["bare_cells_approximate_range"], [573000000, 1200000000]
        )
        self.assertEqual(set(memory["excluded"]), {"substrate", "air padding", "PML"})
        self.assertEqual(memory["packet_ceiling_gib"], packet["grant"]["memory_gib"])
        self.assertFalse(memory["ceiling_is_fit_evidence"])
        self.assertEqual(memory["forecast_status"], "NOT_DEMONSTRATED")
        self.assertIsNone(memory["measured_peak_rss_gib"])
        self.assertIn("UNRESOLVED", memory["unavailable_fine_truth"])

    def test_conditional_launch_arithmetic_never_becomes_cpu_hours(self):
        self.assertEqual(
            self.rows["f02"]["base_work"]["conditional_base_count"], 9 * 24
        )
        self.assertEqual(
            self.rows["f06"]["base_work"]["conditional_base_count"], 256 * 9
        )
        self.assertIn("ONLY IF", self.rows["f06"]["base_work"]["condition"])
        self.assertEqual(
            self.rows["f08"]["base_work"]["conditional_base_count"], 256 * 5
        )
        self.assertEqual(
            self.rows["f17"]["base_work"]["conditional_base_count"], 45 * 9 * 2
        )
        self.assertIn(
            "no assumed velocity reuse", self.rows["f17"]["base_work"]["condition"]
        )

    def test_no_redraw_and_battery_exception_end_are_explicit(self):
        rule = self.proposal["forward_rule"]
        self.assertFalse(rule["none_feasible_redraw"])
        self.assertFalse(rule["unresolved_redraw"])
        self.assertEqual(rule["no_opportunities"], "UNMEASURABLE")
        self.assertIn("never replace P", rule["power_population"])
        exception = rule["battery_exception"]
        self.assertEqual(exception["scope"], "already-sealed v8 only")
        self.assertEqual(exception["ends_at"], "next quiz version")
        self.assertIsNone(exception["next_version_number"])
        self.assertFalse(exception["historical_rescore"])
        self.assertIn("no redraws", self.document)
        self.assertIn("next quiz version", self.document)

    def test_witnesses_and_reference_disagreements_preserve_custody(self):
        custody = self.proposal["witness_custody"]
        self.assertEqual(
            set(custody["prohibited"]),
            {"hidden EVAL", "hidden STRESS", "hidden quiz", "hidden tuning"},
        )
        self.assertEqual(len(custody["permitted"]), 2)
        self.assertIn("never candidate failure", custody["tool_disagreement"])
        self.assertIn(
            "already-sealed results retain their original identity", self.document
        )
        self.assertIn("pointwise and decision agreement", self.document)

    def test_task_observers_are_not_unweighted_mean_or_scalar_global_optima(self):
        for phrase in (
            "unweighted mean is not a quantile",
            "Finite-bank best is not a global physical optimum",
            "a condition-level pass",  # case checked below
            "Threshold variation, model arms, idempotent replay and refinement never mint",
        ):
            self.assertIn(phrase.lower(), self.document.lower())
        self.assertIn("fifth ordered coupling", self.rows["f06"]["panel"])
        self.assertIn("minimum TL diagnostic only", self.rows["f13"]["panel"])
        self.assertIn("Positive axial-flux weighted", self.rows["f17"]["panel"])

    def test_reference_refinement_does_not_follow_candidate_or_change_truth(self):
        for phrase in (
            "Selection is independent of the submitted pick",
            "One settled feasible action establishes FEASIBLE_EXISTS",
            "No clean pass or credit for unresolved truth",
            "Missing/uncertain **candidate** predictions",
            "cannot turn settled reference truth into UNRESOLVED",
            "every** action to be demonstrably infeasible",
        ):
            self.assertIn(phrase, self.document)

    def test_no_solver_model_or_hidden_imports_in_this_static_suite(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
        self.assertEqual(imports, {"ast", "json", "math", "unittest", "pathlib"})

    def test_toy_occupancy_is_bank_bounded_and_keeps_none_mass(self):
        # Two toy winner regions have mass .2 each; .6 is NONE_FEASIBLE.
        # Do not renormalize the two winner regions to .5 each.
        k = 8
        unconditional = sum(1 - (1 - mass) ** k for mass in (0.2, 0.2))
        conditioned = sum(1 - (1 - mass) ** k for mass in (0.5, 0.5))
        self.assertLess(unconditional, conditioned)
        self.assertLessEqual(unconditional, min(k, 2))
        self.assertEqual(sum(1 - (1 - mass) ** k for mass in ()), 0)
        # Empty opportunity support is zero occupancy, not demonstrated power.
        self.assertEqual(
            self.proposal["forward_rule"]["no_opportunities"], "UNMEASURABLE"
        )


if __name__ == "__main__":
    unittest.main()
