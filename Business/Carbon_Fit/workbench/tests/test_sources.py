import hashlib
import importlib.util
import json
import subprocess
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


extract = module("extract", ROOT / "tools/extract_atlas.py")
cpes = module("cpes", ROOT / "tools/import_cpes_evidence.py")
packager = module("packager", ROOT / "tools/package_release.py")


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = json.loads((ROOT / "data/atlas.json").read_text())
        cls.study = json.loads((ROOT / "data/cpes_study_v1.json").read_text())
        cls.source = ROOT / "sources" / cls.atlas["source"]["file"]

    def test_complete_reextraction(self):
        self.assertEqual(extract.extract(self.source), self.atlas)

    def test_exact_atlas_source_hash(self):
        self.assertEqual(
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
            self.atlas["source"]["sha256"],
        )

    def test_all_64_source_opportunities_and_groups_survive(self):
        self.assertEqual(len(self.atlas["opportunities"]), 64)
        self.assertEqual(len({o["id"] for o in self.atlas["opportunities"]}), 64)
        self.assertEqual(
            [sum(o["group"] == g for o in self.atlas["opportunities"]) for g in "ABCD"],
            [13, 17, 15, 19],
        )

    def test_reference_mms_and_experiment_tables_survive(self):
        self.assertEqual(len(self.atlas["reference_families"]), 8)
        self.assertEqual(len(self.atlas["mms_roles"]), 5)
        self.assertEqual(len(self.atlas["mms_factory"]), 6)
        self.assertEqual(len(self.atlas["experiments"]), 10)

    def test_source_hypotheses_never_become_qualification(self):
        self.assertTrue(
            all(
                not o["qualified_carbon_evidence"]
                and o["profile_status"] == "NOT_PROFILED"
                for o in self.atlas["opportunities"]
            )
        )
        self.assertTrue(
            all(
                o["equations_to_register"] is None
                and o["boundary_conditions_to_register"] is None
                for o in self.atlas["opportunities"]
            )
        )

    def test_historical_citations_and_reports_preserved(self):
        self.assertEqual(
            [r["id"] for r in self.atlas["bibliography"]],
            [f"C{i}" for i in range(1, 12)] + [f"E{i}" for i in range(1, 42)],
        )
        for record in json.loads((ROOT / "data/studies.json").read_text())["studies"]:
            self.assertEqual(
                hashlib.sha256(
                    (ROOT / "sources" / record["filename"]).read_bytes()
                ).hexdigest(),
                record["sha256"],
            )
            self.assertFalse(record["qualified_claim_refs"])

    def test_seed_index_parity(self):
        index = json.loads((ROOT / "data/seed_index.json").read_text())
        self.assertEqual(
            [x["id"] for x in index["records"]],
            [x["id"] for x in self.atlas["opportunities"]],
        )

    def test_all_eight_pinned_evidence_members_verify(self):
        index_path = ROOT / "evidence/cpes_reference_reuse_v2/evidence_index_v1.json"
        self.assertEqual(
            hashlib.sha256(index_path.read_bytes()).hexdigest(), cpes.INDEX_SHA256
        )
        index = json.loads(index_path.read_text())
        self.assertEqual(len(index["files"]), 8)
        for name, meta in index["files"].items():
            raw = (index_path.parent / name).read_bytes()
            self.assertEqual(len(raw), meta["bytes"], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"], name)

    def test_evidence_member_schemas_and_cross_consistency(self):
        expected = {
            "adaptive_bank_control_v1.json": "carbon.cpes-reuse.adaptive-bank-control.v1",
            "persistent_probes_v1.json": "carbon.cpes-reuse.persistent-probes.v1",
            "source_manifest_v1.json": "carbon.cpes-reuse.source-manifest.v1",
            "study_summary_v1.json": "carbon.cpes-reuse.study-summary.v1",
            "profiler_summary_v1.json": "carbon.challenge-profiler.cpes-reuse-study.v1",
            "cost_delay_analysis_v1.json": "carbon.cpes-reuse.cost-delay-study.v1",
        }
        base = ROOT / "evidence/cpes_reference_reuse_v2"
        for name, schema in expected.items():
            self.assertEqual(
                json.loads((base / name).read_text())["schema_version"], schema
            )
        rows = json.loads((base / "attack_dispositions_v2.json").read_text())
        self.assertEqual(
            [r["attack_id"] for r in rows], [f"AT-{i:02d}" for i in range(1, 31)]
        )
        traces = [
            json.loads(line)
            for line in (base / "attack_traces_v2.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(traces), 12)
        self.assertTrue(
            all("probe" in trace and "evidence_layer" in trace for trace in traces)
        )
        self.assertEqual(cpes.validate(), self.study)

    def test_public_study_keeps_layers_unknowns_and_authority_separate(self):
        self.assertEqual(self.study["recommendation"], "RETAIN_A")
        self.assertEqual(
            self.study["attack_counts"],
            {
                "BLOCKED": 5,
                "REJECTED_BY_PERSISTENT_RESEARCH_PROTOTYPE": 8,
                "REJECTED_BY_REPRODUCED_ORIGINAL_MODEL": 17,
            },
        )
        self.assertEqual(
            self.study["blocked_attack_ids"],
            ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"],
        )
        self.assertIsNone(self.study["categories"]["qualified_carbon_evidence"])
        self.assertIsNone(self.study["provenance"]["study_implementation_revision"])
        self.assertFalse(
            self.study["observations"]["cross_hardware_composition_permitted"]
        )
        self.assertTrue(
            all(value is None for value in self.study["quantity_unknowns"].values())
        )

    def test_adaptive_negative_control_exact_values(self):
        a = self.study["adaptive_negative_control"]
        self.assertEqual(
            (
                a["whole_cases"],
                a["queries"],
                a["recovered_bank_exactly"],
                a["reused_bank_accuracy"],
                a["independent_holdout_accuracy"],
            ),
            (32, 33, True, 1.0, 0.46875),
        )

    def test_build_is_deterministic_and_script_safe(self):
        subprocess.run(
            ["/usr/bin/python3", str(ROOT / "tools/build.py")],
            check=True,
            capture_output=True,
        )
        first = (ROOT / "Carbon_Opportunity_Workbench.html").read_bytes()
        intake_first = (ROOT / "Carbon_Client_Intake_Preview.html").read_bytes()
        pilot_first = (ROOT / "Carbon_Client_Pilot_Designer_Preview.html").read_bytes()
        subprocess.run(
            ["/usr/bin/python3", str(ROOT / "tools/build.py")],
            check=True,
            capture_output=True,
        )
        second = (ROOT / "Carbon_Opportunity_Workbench.html").read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(
            intake_first, (ROOT / "Carbon_Client_Intake_Preview.html").read_bytes()
        )
        self.assertEqual(
            pilot_first,
            (ROOT / "Carbon_Client_Pilot_Designer_Preview.html").read_bytes(),
        )
        self.assertEqual(intake_first, pilot_first)
        text = first.decode()
        self.assertIn("default-src 'none'", text)
        self.assertNotIn("</script><script>alert", text)
        self.assertIn("Goal-to-Challenge Workbench", text)
        intake_text = intake_first.decode()
        self.assertIn("nothing is submitted from this preview", intake_text)
        self.assertIn("Enable AI guidance", intake_text)
        self.assertIn("Draft pilot for Carbon review", intake_text)
        self.assertNotIn("OWNER-GW07-RYAN-SNAPSHOT-01", intake_text)
        self.assertNotIn("approved_assessments", intake_text)

    def test_current_schema_is_closed_v02(self):
        schema = json.loads((ROOT / "data/workspace.schema.json").read_text())
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "carbon_workbench_workspace_v0.2",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["drafts"]["items"]["properties"][
                "qualification_status"
            ]["const"],
            "NOT_QUALIFIED_BY_THIS_TOOL",
        )

    def test_additive_goal_and_intake_schemas_are_closed_v09_and_reproducible(self):
        tool = ROOT / "tools/build_goal_schema.py"
        subprocess.run(["/usr/bin/python3", str(tool)], check=True, capture_output=True)
        schema_path = ROOT / "data/goal_workspace.schema.json"
        constants_path = ROOT / "data/goal_constants.json"
        first = (schema_path.read_bytes(), constants_path.read_bytes())
        subprocess.run(["/usr/bin/python3", str(tool)], check=True, capture_output=True)
        self.assertEqual(first, (schema_path.read_bytes(), constants_path.read_bytes()))
        schema = json.loads(first[0])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "carbon.goal-workbench.workspace.v0.10",
        )
        self.assertEqual(
            schema["properties"]["authority"]["properties"]["launch"]["const"],
            "NOT_LAUNCHED",
        )
        self.assertEqual(schema["properties"]["jobs"]["maxItems"], 64)
        evidence = schema["properties"]["jobs"]["items"]["properties"]["designs"][
            "items"
        ]["properties"]["measurement_evidence"]
        self.assertFalse(evidence["items"]["additionalProperties"])
        design = schema["properties"]["jobs"]["items"]["properties"]["designs"]["items"]
        self.assertFalse(design["properties"]["route_plan"]["additionalProperties"])
        self.assertFalse(
            design["properties"]["evidence_bindings"]["items"]["additionalProperties"]
        )
        self.assertFalse(design["properties"]["coordination"]["additionalProperties"])
        self.assertFalse(
            design["properties"]["source_assessments"]["additionalProperties"]
        )
        binding = design["properties"]["evidence_bindings"]["items"]["properties"]
        self.assertIn("scientific_review_reasons", binding)
        self.assertIn("origin_verification", binding)
        self.assertNotIn(
            "CARRIED_FORWARD_UNCHANGED_SCOPE",
            binding["scientific_applicability"]["enum"],
        )
        intake = json.loads((ROOT / "data/intake_draft.schema.json").read_text())
        self.assertFalse(intake["additionalProperties"])
        self.assertNotIn("qualified", intake["properties"])
        self.assertNotIn("approval", intake["properties"])
        reviewed = json.loads((ROOT / "data/intake_reviewed.schema.json").read_text())
        self.assertFalse(reviewed["additionalProperties"])
        self.assertFalse(reviewed["properties"]["brief"]["additionalProperties"])
        self.assertFalse(reviewed["properties"]["ai_guidance"]["additionalProperties"])
        self.assertNotIn("approved", reviewed["properties"])
        self.assertNotIn("qualified", reviewed["properties"])

    def test_repository_snapshot_schemas_are_deeply_closed_and_reproducible(self):
        tool = ROOT / "tools/build_repository_snapshot_schemas.py"
        schema_dir = ROOT / "source_assessment/repository_snapshot/v1/schemas"
        subprocess.run(["/usr/bin/python3", str(tool)], check=True, capture_output=True)
        first = {path.name: path.read_bytes() for path in schema_dir.glob("*.json")}
        subprocess.run(["/usr/bin/python3", str(tool)], check=True, capture_output=True)
        self.assertEqual(
            first, {path.name: path.read_bytes() for path in schema_dir.glob("*.json")}
        )

        def assert_closed(value):
            if isinstance(value, dict):
                if value.get("type") == "object" or "properties" in value:
                    self.assertIs(value.get("additionalProperties"), False)
                for child in value.values():
                    assert_closed(child)
            elif isinstance(value, list):
                for child in value:
                    assert_closed(child)

        for raw_schema in first.values():
            assert_closed(json.loads(raw_schema))

    def test_retained_c05_fixture_index_binds_exact_source_digests(self):
        index = json.loads((ROOT / "data/c05_fixture_index_v1.json").read_text())
        self.assertEqual(len(index["fixtures"]), 2)
        for filename, item in zip(
            [
                "c05_public_development_evidence_v1.json",
                "c05_public_development_noncomplete_v1.json",
            ],
            index["fixtures"],
            strict=True,
        ):
            bundle = json.loads((ROOT / "data" / filename).read_text())
            self.assertEqual(
                "sha256:"
                + hashlib.sha256(
                    bundle["measurement_request_json"].encode("ascii")
                ).hexdigest(),
                item["request_digest"],
            )
            self.assertEqual(
                "sha256:"
                + hashlib.sha256(
                    bundle["measurement_result_json"].encode("ascii")
                ).hexdigest(),
                item["result_digest"],
            )
            self.assertFalse(bundle["authority"]["score_eligible"])

    def test_saved_c05_projection_index_is_exact_and_reproducible(self):
        tool = ROOT / "tools/build_c05_saved_fixture_index.cjs"
        subprocess.run(["node", str(tool)], check=True, capture_output=True)
        path = ROOT / "data/c05_fixture_index_v2.json"
        first = path.read_bytes()
        subprocess.run(["node", str(tool)], check=True, capture_output=True)
        self.assertEqual(first, path.read_bytes())
        index = json.loads(first)
        self.assertEqual(
            index["schema_version"], "carbon.goal-workbench.c05-fixture-index.v2"
        )
        for item in index["fixtures"]:
            self.assertTrue(
                item["saved_projection"]["imported_artifact_digest"].startswith(
                    "sha256:"
                )
            )

    def test_frozen_v05_journeys_keep_routes_and_authority_closed(self):
        record = json.loads(
            (ROOT / "data/goal_workbench_05_journeys_v1.json").read_text()
        )
        self.assertEqual(
            [item["route"] for item in record["journeys"]],
            [
                "USE_EXISTING_CAPABILITY",
                "ADAPT_SUPPORTED_CHALLENGE",
                "DEVELOP_NEW_CAPABILITY",
                "ADAPT_SUPPORTED_CHALLENGE",
            ],
        )
        self.assertFalse(record["journeys"][0]["challenge_authoring_required"])
        self.assertEqual(
            record["journeys"][3]["external_state"], "EXPORTED_OWNER_REQUEST"
        )
        self.assertTrue(
            all(value is False for value in record["global_authority_ceiling"].values())
        )

    def test_manifest_and_bundle_are_complete_and_reproducible(self):
        manifest_path, archive_path = packager.build()
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        self.assertEqual(manifest["pinned_evidence_index_sha256"], cpes.INDEX_SHA256)
        self.assertIn("GOAL-WORKBENCH-03", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-04", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-05", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-05A", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-07A", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-08", manifest["decision_ids"])
        self.assertIn("GOAL-WORKBENCH-10", manifest["decision_ids"])
        self.assertIn(
            "OWNER-GW07-RYAN-SNAPSHOT-01-ADOPTION-001",
            manifest["decision_ids"],
        )
        self.assertEqual(
            manifest["accepted_goal_workbench_05_baseline"]["merge_commit"],
            "3681f7fb10be0c6e278f53d59ff9b022099ef12d",
        )
        self.assertEqual(
            manifest["accepted_goal_workbench_baseline"]["merge_commit"],
            "e576fbdc711c9194dbcc7d90405480e90577407e",
        )
        self.assertEqual(
            manifest["accepted_goal_workbench_07_baseline"]["merge_commit"],
            "b71b1a68b6f9a895f12fc608e2dec895ea038760",
        )
        self.assertEqual(
            manifest["accepted_core_workbench_adapter"]["merge_commit"],
            "7461e168b9ca96c0f212f6cc221703dd5672b167",
        )
        self.assertEqual(
            manifest["private_team_workflow"]["scientific_task_interface"],
            "C_CORE_04_LOCAL_STRUCTURAL_CHECK_ACCEPTED",
        )
        self.assertEqual(
            manifest["source_assessment_snapshot"]["production_approved_entries"],
            1,
        )
        self.assertEqual(
            manifest["source_assessment_snapshot"]["admission_state"],
            "OWNER_ADOPTED_ASSESSMENT_ADMITTED",
        )
        self.assertEqual(
            manifest["accepted_detached_research_reference"]["owner_request_status"],
            "EXPORTED_OWNER_REQUEST",
        )
        self.assertEqual(manifest["grok_plan_artifact"]["pages_inspected"], 10)
        self.assertEqual(
            manifest["grok_plan_artifact"]["source_docx_digest_status"],
            "VERIFIED_BEFORE_RENDER",
        )
        self.assertEqual(
            manifest["grok_plan_artifact"]["source_docx_sha256"],
            "799108791ec951ebfd51b2d56c35f70df51ebc559929a4991cc118efd13981b5",
        )
        for name, meta in manifest["files"].items():
            path = ROOT / name
            self.assertEqual(path.stat().st_size, meta["bytes"], name)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"], name
            )
        with zipfile.ZipFile(archive_path) as bundle:
            names = bundle.namelist()
            self.assertIn("carbon_goal_workbench_v0_10/MANIFEST.json", names)
            self.assertIn(
                "carbon_goal_workbench_v0_10/Carbon_Opportunity_Workbench.html", names
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/Carbon_Client_Intake_Preview.html", names
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/Carbon_Client_Pilot_Designer_Preview.html",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/evidence/cpes_reference_reuse_v2/evidence_index_v1.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/goal_workspace.schema.json", names
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/goal_workbench_03_rehearsal_record_v1.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/docs/GOAL_WORKBENCH_03_REHEARSAL_REPORT.md",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/tools/run_operational_rehearsal.cjs",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/goal_workbench_05_journeys_v1.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/docs/GOAL_WORKBENCH_05_OPTIMIZATION_REPORT.md",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/docs/GOAL_WORKBENCH_05A_STATE_INTEGRITY_REPORT.md",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/goal_workbench_05a_transition_evidence_v1.json",
                names,
            )
            self.assertIn("carbon_goal_workbench_v0_10/src/source_assessment.js", names)
            self.assertIn("carbon_goal_workbench_v0_10/src/intake.js", names)
            self.assertIn("carbon_goal_workbench_v0_10/src/team_review.js", names)
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/intake_draft.schema.json", names
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/source_assessment/repository_snapshot/v1/approved_assessments.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/source_assessment/repository_snapshot/v1/adoption/owner_gw07_ryan_snapshot_01.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/source_assessment/repository_snapshot/v1/candidate/public_example_workspace.json",
                names,
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/tools/team_intake_server.cjs", names
            )
            self.assertIn(
                "carbon_goal_workbench_v0_10/data/goal_workbench_09_team_scenarios_v1.json",
                names,
            )
            self.assertNotIn(
                "carbon_goal_workbench_v0_10/Carbon_Physics_Opportunity_Workbench_v0_2.zip",
                names,
            )
            before = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        packager.build()
        self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()


class AssistanceDefaultTests(unittest.TestCase):
    """Assistance must not become default-on through a build variant.

    The private-science flag exists to let the Workbench reach its operator's
    scientific service. It must not, as a side effect, change anything about the
    client intake preview, which is the surface a customer sees and the one that
    would carry assistance if it were ever switched on by configuration.
    """

    def test_the_client_preview_is_identical_in_both_build_variants(self):
        import tempfile

        builder = module("builder", ROOT / "tools/build.py")
        with tempfile.TemporaryDirectory() as directory:
            offline = Path(directory) / "offline"
            private = Path(directory) / "private"
            builder.build(output_directory=offline)
            builder.build(private_science=True, output_directory=private)

            for name in (
                "Carbon_Client_Intake_Preview.html",
                "Carbon_Client_Pilot_Designer_Preview.html",
            ):
                self.assertEqual(
                    (offline / name).read_bytes(),
                    (private / name).read_bytes(),
                    f"{name} differs between build variants, so a variant could "
                    "change client-facing assistance behaviour",
                )

            # The variant does change the Workbench artifact, so the comparison
            # above is a real constraint rather than a comparison of two
            # identical builds.
            workbench = "Carbon_Opportunity_Workbench.html"
            self.assertNotEqual(
                (offline / workbench).read_bytes(),
                (private / workbench).read_bytes(),
            )

            # Neither variant ships assistance enabled.
            for variant in (offline, private):
                preview = (variant / "Carbon_Client_Intake_Preview.html").read_text(
                    encoding="utf-8"
                )
                self.assertIn("let guidanceEnabled = false;", preview)
                self.assertIn("let guidanceAvailable = false;", preview)
                self.assertNotIn("let guidanceEnabled = true", preview)
                # The preview may not reach a provider without being asked to.
                self.assertIn("connect-src 'self'", preview)
