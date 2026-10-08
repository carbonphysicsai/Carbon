"""Static route/panel arithmetic; no reference, model, runner or hidden imports."""

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUND1 = ROOT / "docs/development/challenge_pipeline/round1"
FAMILIES = {"f02", "f06", "f08", "f13", "f17"}


class TestReferenceRouteProposals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads(
            (ROUND1 / "reference-route-panels.json").read_text(encoding="utf-8")
        )
        cls.rows = cls.proposal["families"]
        cls.requirements = json.loads(
            (ROUND1 / "requirements.json").read_text(encoding="utf-8")
        )["challenges"]
        cls.doc = " ".join(
            (ROUND1 / "reference-routes.md").read_text(encoding="utf-8").split()
        )

    def test_exact_scope_is_specified_and_has_no_execution_permission(self):
        self.assertEqual(self.proposal["ticket"], "CHALLENGE-REFERENCE-ROUTES-01")
        self.assertEqual(self.proposal["maturity"], "SPECIFIED")
        self.assertEqual(set(self.rows), FAMILIES)
        self.assertFalse(self.proposal["dispatch_ready"])
        self.assertFalse(self.proposal["runtime_registration"])
        self.assertTrue(self.proposal["permissions"])
        self.assertTrue(
            all(value is False for value in self.proposal["permissions"].values())
        )
        self.assertIn("Cooling is out of scope", self.doc)
        self.assertIn("No solver was run or installed", self.doc)

    def test_all_new_registered_choices_and_package_pins_are_null(self):
        for choice in self.proposal["new_choices"].values():
            self.assertEqual(choice["status"], "HUMAN_INPUT")
            self.assertIsNone(choice["registered"])
            self.assertTrue(choice["recommendation"])
        for row in self.rows.values():
            package = row["package"]
            self.assertTrue(package["proposed_name"])
            self.assertTrue(package["release_candidate"])
            self.assertEqual(package["feature_proof"], "NOT_DEMONSTRATED")
            for key in (
                "package_pr",
                "package_head",
                "source_digest",
                "build_digest",
                "image_digest",
                "mesh_digest",
                "deck_digest",
                "observer_digest",
            ):
                self.assertIsNone(package[key])

    def test_packet_constraints_are_not_loosened_by_cheaper_routes(self):
        for family, row in self.rows.items():
            self.assertEqual(row["packet"], self.requirements[family]["packet"])
            self.assertTrue((ROUND1 / row["packet"]).is_file())
            for anchor in row["buyer_anchors"]:
                value = self.requirements[family]
                for part in anchor["path"]:
                    value = value[part]
                self.assertEqual(anchor["value"], value)
                self.assertIn(anchor["op"], {"<=", ">="})
                self.assertTrue(anchor["unit"])
            self.assertTrue(row["objective"])
            self.assertTrue(row["regret_unit"])

    def test_cost_rank_is_hypothetical_and_has_flip_and_witness_contract(self):
        for row in self.rows.values():
            routes = row["ranked_routes"]
            self.assertEqual([r["cost_rank"] for r in routes], [1, 2, 3])
            self.assertEqual(routes[0]["use"], "SCREENING_ONLY")
            self.assertEqual(routes[1]["use"], "REFERENCE_CANDIDATE")
            self.assertEqual(routes[2]["use"], "WITNESS_CANDIDATE")
            self.assertEqual(row["credibility"], "NOT_DEMONSTRATED")
            self.assertTrue(row["tier2_buyer_tool"])
            self.assertTrue(row["decision_flip"])
            self.assertTrue(row["detection"])
        self.assertIn("geometric work ratios, not measured speedups", self.doc)

    def test_five_eight_case_panels_are_public_recipes_not_truth_or_30_case_claim(self):
        measure = self.proposal["measurement"]
        self.assertEqual(measure["cases_per_family"], 8)
        self.assertEqual(measure["total_primary_cases"], 40)
        self.assertIsNone(measure["exact_deck_manifest"])
        self.assertFalse(measure["completed_foundation_30_case_panel"])
        self.assertFalse(measure["production_p95_supported"])
        for row in self.rows.values():
            cases = row["public_cases"]
            self.assertEqual(len(cases), 8)
            self.assertEqual(len({c["label"] for c in cases}), 8)
            for case in cases:
                self.assertEqual(len(case["parameters"]), len(row["panel_fields"]))
                self.assertLessEqual(set(case), {"label", "parameters", "bank"})
            self.assertTrue(row["case_unit"])
            self.assertTrue(row["panel_gap"])
            self.assertTrue(row["refinement_witness_labels"])
            self.assertLessEqual(
                set(row["refinement_witness_labels"]), {c["label"] for c in cases}
            )

    def test_no_measured_cost_is_replaced_by_a_hypothesis(self):
        for row in self.rows.values():
            cost = row["cost"]
            self.assertEqual(cost["status"], "UNMEASURED")
            for suffix in ("cpu_hours", "peak_rss_gib"):
                low = cost[f"p50_{suffix}_hypothesis"]
                high = cost[f"p95_{suffix}_hypothesis"]
                self.assertGreater(low, 0)
                self.assertGreaterEqual(high, low)
            for key in (
                "measured_p50_cpu_hours",
                "measured_p95_cpu_hours",
                "measured_peak_rss_gib",
            ):
                self.assertIsNone(cost[key])
        self.assertIn(
            "no p95 computed only from fast survivors",
            self.proposal["measurement"]["censored_quantiles"],
        )
        self.assertIn("No linear parallel speedup", self.doc)

    def test_nontransferable_grant_units_and_process_reservations_add_up(self):
        grant = self.proposal["grant_proposal"]
        cpus = grant["allocated_logical_cpus_max"]
        self.assertEqual(grant["status"], "HUMAN_INPUT")
        self.assertIsNone(grant["approved"])
        self.assertEqual(grant["all_in_additional_usd_max"], 0)
        self.assertFalse(grant["transferable"])
        self.assertFalse(grant["paid_fallback"])
        self.assertFalse(grant["supersedes_or_renews_old_grants"])
        for slot in ("exact_host", "stage_authority", "enforced_runner"):
            self.assertIsNone(grant[slot])
        for row in self.rows.values():
            cap = row["free_cap"]
            self.assertEqual(cap["allocated_cpu_hours"], cap["node_hours"] * cpus)
            self.assertEqual(
                sum(row["process_reservations"].values()), cap["process_launches"]
            )
        for field, total in (
            ("node_hours", "total_node_hours_max"),
            ("allocated_cpu_hours", "total_allocated_cpu_hours_max"),
            ("process_launches", "total_process_launches_max"),
        ):
            self.assertEqual(
                sum(row["free_cap"][field] for row in self.rows.values()), grant[total]
            )
        self.assertEqual(grant["total_node_hours_max"], 20)
        self.assertEqual(grant["total_allocated_cpu_hours_max"], 160)
        self.assertEqual(grant["total_process_launches_max"], 442)
        self.assertIn("enforced wall/CPU/RSS/launch/system caps", grant["requires"])
        self.assertEqual(grant["automatic_retries"], 0)

    def test_censored_photon_tail_and_conditional_grant_do_not_enable_fallback(self):
        grant = self.proposal["grant_proposal"]
        row = self.rows["f06"]
        self.assertGreater(
            row["cost"]["p95_peak_rss_gib_hypothesis"],
            grant["aggregate_total_memory_gib_max"],
        )
        conditional = self.proposal["conditional_high_memory_proposal"]
        for slot in ("approved", "exact_platform", "quote", "manifest"):
            self.assertIsNone(conditional[slot])
        self.assertFalse(conditional["automatic_dispatch"])
        self.assertFalse(conditional["old_ceiling_is_unspent_grant"])
        self.assertEqual(
            conditional["allocated_cpu_hours_max_recommendation"],
            conditional["node_hours_max_recommendation"]
            * conditional["allocated_logical_cpus_max_recommendation"],
        )
        self.assertFalse(row["fine_grid"]["free_cpu_allowed"])
        self.assertFalse(row["fine_grid"]["memory_fit_demonstrated"])
        self.assertIn("No swap-assisted completion", self.doc)
        self.assertIn("total cgroup memory", grant["enforcement_memory_metric"])

    def test_photon_normalization_conditions_and_fine_memory_lower_bound(self):
        row = self.rows["f06"]
        self.assertEqual(
            row["vectors_per_geometry"] * row["wavelengths_per_vector"], 45
        )
        self.assertEqual(row["process_reservations"]["primary"], 8 * 9 * 2)
        self.assertEqual(row["process_reservations"]["two20nm_witnesses"], 2 * 9 * 2)
        self.assertFalse(row["broadband_verified"])
        self.assertFalse(row["local_variable_meep_grid_assumed"])
        memory = row["fine_grid"]
        lo, hi = [
            n * memory["empty_real_bytes_per_voxel_lower_bound"] / 2**30
            for n in memory["bare_cells_range"]
        ]
        self.assertAlmostEqual(lo, 51.23, delta=0.02)
        self.assertAlmostEqual(hi, 107.29, delta=0.02)
        self.assertIn("2D remains SCREENING_ONLY", self.doc)
        self.assertIn("not periodic transverse boundaries", self.doc)

    def test_frequency_sweep_is_not_one_solve_or_free_factorization(self):
        work = self.rows["f13"]["frequency_work"]
        start, end = work["band_hz"]
        count = (end - start) // work["dense_step_hz"] + 1
        self.assertEqual(count, work["dense_systems_per_curve"])
        self.assertEqual(count * 16, work["baseline16_design_launches"])
        self.assertEqual(count * 16, work["batched16_design_systems"])
        self.assertEqual(count * 8, work["eight_primary_systems"])
        self.assertEqual(work["batched16_design_processes_if_verified"], 16)
        self.assertFalse(work["same_lu_assumed"])
        self.assertTrue(work["interval_width_weighting"])
        self.assertTrue(work["midpoints_mandatory"])
        # Primary/refined continuation points share a per-curve cap. Controls,
        # one cold repeat and separate-frequency parity smoke are also charged.
        max_reserved = 10 * 601 + 2 * 201 + 201 + 3
        self.assertLessEqual(max_reserved, work["frequency_systems_max"])
        self.assertIn("3,216 frequency systems", self.doc)
        self.assertIn("not just visible extrema", self.doc)

    def test_modal_baseline_and_damping_and_flow_reuse_are_not_assumed(self):
        structure = self.rows["f08"]
        self.assertTrue(structure["existing_baseline_may_already_be_modal"])
        self.assertTrue(structure["direct_witness_requires_same_damping"])
        self.assertFalse(structure["rayleigh_substitution_allowed"])
        self.assertEqual(structure["modal_rungs"], [12, 24, 48])
        mixer = self.rows["f17"]
        self.assertFalse(mixer["flow_reuse_demonstrated"])
        self.assertFalse(mixer["boundedness_proves_low_diffusion"])
        self.assertEqual(
            mixer["process_reservations"]["primary"],
            8
            * (
                mixer["flow_jobs_per_geometry_if_verified"]
                + mixer["scalar_jobs_per_geometry"]
            ),
        )
        self.assertEqual(mixer["no_reuse_jobs_per_geometry"], 9 * 2)

    def test_public_recipe_parameters_remain_in_packet_grammar(self):
        thermal = self.requirements["f02"]["thermal"]
        for case in self.rows["f02"]["public_cases"]:
            coolant, h, initial, split, wave, power, duration = case["parameters"]
            self.assertIn(
                {"coolant_c": coolant, "h_w_m2_k": h}, thermal["cooling_regimes"]
            )
            self.assertIn(initial, thermal["initial_c"])
            self.assertIn(split, {0.5, 0.8})
            self.assertIn(wave, {"rectangular", "ramp", "two-pulse"})
            self.assertIn(power, thermal["peak_w"])
            self.assertIn(duration, thermal["on_time_s"])
        optics = self.requirements["f06"]["optical"]
        for case in self.rows["f06"]["public_cases"]:
            n, pitch, duty, etch, width = case["parameters"]
            for value, name in zip(
                (n, pitch, duty, etch, width), self.rows["f06"]["panel_fields"]
            ):
                self.assertLessEqual(optics[name][0], value)
                self.assertLessEqual(value, optics[name][1])
            for dp, dd in ((-10, -0.03), (10, 0.03), (-10, 0.03), (10, -0.03)):
                self.assertGreaterEqual(
                    (pitch + dp) * min(duty + dd, 1 - duty - dd),
                    optics["minimum_feature_nm"],
                )
        acoustic = self.requirements["f13"]["acoustic"]
        for case in self.rows["f13"]["public_cases"]:
            r1, r2, l1, l2, neck, offset = case["parameters"]
            self.assertLessEqual(l1 + l2 + neck + 20, acoustic["package_length_mm"])
            self.assertLessEqual(2 * max(r1, r2), acoustic["package_diameter_mm"])
            self.assertGreaterEqual(
                min(r1, r2) - acoustic["neck_radius_mm"] - offset,
                acoustic["minimum_clearance_mm"],
            )
        for family, law in (
            ("f08", self.requirements["f08"]["structure"]),
            ("f17", self.requirements["f17"]["mixer"]),
        ):
            for case in self.rows[family]["public_cases"]:
                for field, value in zip(
                    self.rows[family]["panel_fields"], case["parameters"]
                ):
                    self.assertLessEqual(law[field][0], value)
                    self.assertLessEqual(value, law[field][1])

    def test_witness_custody_and_sealed_identity_and_unit_regret(self):
        contract = self.proposal["witness_contract"]
        self.assertEqual(
            set(contract["prohibited"]),
            {"hidden EVAL", "hidden STRESS", "hidden quiz", "hidden tuning"},
        )
        self.assertEqual(len(contract["permitted"]), 2)
        self.assertFalse(contract["two_unresolved_is_agreement"])
        self.assertFalse(contract["subset_pick_is_full_bank_optimum"])
        self.assertFalse(contract["none_feasible_redraw"])
        self.assertFalse(contract["unresolved_redraw"])
        self.assertFalse(contract["reality_claim_without_tier3"])
        self.assertIn("never candidate failure", contract["tool_disagreement"])
        self.assertIn("sealed results retain original identity", contract["revision"])
        for phrase in (
            "outside producer custody",
            "pointwise and decision agreement",
            "all contenders",
            "not silently re-scored",
            "protocol **stage authority**",
            "not an enforced runner",
        ):
            self.assertIn(phrase, self.doc)

    def test_this_suite_is_static_and_imports_only_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
        self.assertEqual(imports, {"ast", "json", "unittest", "pathlib"})


if __name__ == "__main__":
    unittest.main()
