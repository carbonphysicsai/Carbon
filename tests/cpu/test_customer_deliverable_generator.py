"""Synthetic document fixtures only: provenance/gaps, no physical execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.dev.customer_deliverable.generate import (
    BundleReader,
    GitReader,
    Source,
    git_blob,
    load_policy,
    render,
    safe_path,
    scalar_fact,
    write_outputs,
)
from scripts.dev.customer_deliverable.package_sections import PROJECTION_SCHEMA

CHALLENGE = "battery-fastcharge-ageing-development-v1"


class MemoryReader:
    membership_basis = "SYNTHETIC_TEST_ONLY"
    evidence_revision = "a" * 40
    framework_revision = "b" * 40

    def __init__(self, texts):
        self.texts = texts
        self.calls = []

    def get(self, spec, framework=False):
        self.calls.append(spec["path"])
        text = self.texts.get(spec["id"])
        if text is None:
            return None
        revision = self.framework_revision if framework else self.evidence_revision
        return Source(spec["id"], spec["path"], revision, git_blob(text.encode()), text)


def fixture_texts():
    ids = [f"D{i:02}" for i in range(1, 12)]
    classes = {
        "D05": "automatable later",
        "D07": "automatable later",
        "D08": "automatable now",
        "D10": "automatable later",
        "D11": "automatable now",
    }

    template = "\n".join(
        f"## {sid} synthetic document fixture\n\n"
        f"Coverage: HUMAN_INPUT. Automation: {classes.get(sid, 'manual')}.\n"
        for sid in ids
    )
    schema = {
        "properties": {
            "schema_version": {"const": "PROPOSAL_V1"},
            "sections": {"required": ids},
        }
    }
    crosswalk = "\n".join(
        f"| {sid} fixture | NASA fixture | HUMAN_INPUT | preview | topic | DoD |"
        for sid in ids
    )
    reviews = {
        name: {"state": "NOT_STARTED"}
        for name in (
            "customer",
            "launch",
            "numerical_reference",
            "scientific",
            "security",
        )
    }
    return {
        "F1": template,
        "F2": json.dumps(schema),
        "F3": crosswalk,
        "R1": json.dumps({"reviews": reviews}),
        "R2": "29 in-band and 17 out-of-band verified violations\n"
        "**56 of 99 eligible real members commit at least one "
        "reference-verified false\nacceptance**\n"
        "### H1 (primary): UNRESOLVED\n",
        "R4": "There are 25 in-band and 21 out-of-band findings in total\n"
        "The sign-error control's near-limit false-acceptance rate is 0.946\n"
        "| Adversarial score | **FAIL** |\n"
        "**Track A:** 8 of the 10 Track A rebuild-identity constructions "
        "select a protocol the reference verifies infeasible\n"
        "110 of 110 rebuilds match the frozen panel\n",
        "R5": "V3 τ/ρ and every v3 term contribution are therefore "
        "**uncomputable**\n",
    }


def package_fixture_texts():
    """Synthetic arithmetic/transport fixtures; never scientific measurements."""
    texts = fixture_texts()
    image = "sha256:" + "1" * 64
    texts["P1"] = json.dumps(
        {
            "schema": "carbon.code-verification.result.v1",
            "kind": "code_verification",
            "family": "battery-v3",
            "image_digest": image,
            "source_digest": "sha256:" + "3" * 64,
            "criteria_digest": "sha256:" + "4" * 64,
            "norms": [{"l2": 0.01, "linf": 0.02, "samples": 20}],
            "metrics": {"l2_order": 2.0, "linf_order": 2.0},
            "state": "HUMAN_INPUT",
            "accepted_development_pass": False,
            "qualified": False,
        }
    )
    from carbon.trust_map.acceptance import (
        DECISION_ID,
        DECISION_PATH,
        byte_digest,
        digest,
        validate_acceptance,
    )

    policy = load_policy()["challenges"][CHALLENGE]
    paths = {item["id"]: item["path"] for item in policy["package_sources"]}
    texts["P6"] = "SYNTHETIC fixture only: " + DECISION_ID
    criteria = {"family": "battery-v3", "kind": "synthetic-particle"}
    texts["P7"] = json.dumps(criteria)
    mms = json.loads(texts["P1"])
    mms["criteria_digest"] = digest(criteria)
    texts["P1"] = json.dumps(mms)
    link = {
        "schema": "carbon.code-verification.acceptance-link.v1",
        "scope": "DEVELOPMENT_CODE_VERIFICATION",
        "solver": "PyBaMM 26.8.0.0",
        "family": "battery-v3",
        "image_digest": image,
        "criteria_digest": digest(criteria),
        "criteria_path": paths["P7"],
        "decision": {
            "id": DECISION_ID,
            "path": DECISION_PATH,
            "sha256": byte_digest(texts["P6"].encode()),
        },
        "evidence": [
            {"path": paths["P1"], "sha256": byte_digest(texts["P1"].encode())}
        ],
        "conditions": {},
    }
    texts["P2"] = json.dumps(link)
    accepted = validate_acceptance(
        link,
        family="battery-v3",
        image_digest=image,
        criteria_digest=digest(criteria),
        files={paths[k]: texts[k].encode() for k in ("P1", "P6", "P7")},
    )
    texts["P3"] = json.dumps(
        {
            "schema": "carbon.physics-contract.draft.v1",
            "challenge": "battery-v3",
            "runtime_enabled": False,
            "validity": {"status": "HUMAN_INPUT_UNDECLARED"},
            "required_outputs": {"voltage_v": {"availability": "MODEL_AVAILABLE"}},
            "laws": [{"id": "initial-temperature"}, {"id": "capacity-bound"}],
        }
    )
    card = {
        name: {
            "value": 0.1,
            "unit": "fixture-unit",
            "sample_count": 8,
            "statistic": "mean",
            "measurement_version": "fixture-v1",
            "outcome": "NOT_ASSESSED",
        }
        for name in (
            "accuracy_overall",
            "accuracy_near_limits",
            "robustness",
            "extrapolation",
            "uncertainty_calibration",
            "speedup_equal_accuracy",
            "inference_latency",
            "training_cost",
        )
    }
    spec = {
        "axes": [
            {"name": "c1", "edges": [0, 1, 2]},
            {"name": "t_amb_c", "edges": [0, 1]},
        ],
        "bands": {"name": "soc0", "edges": [0, 1]},
        "marginalized": ["c2"],
        "outputs": {"voltage_v": {"length": 1, "unit": "V"}},
        "near_limit": [
            {"output": "voltage_v", "statistic": "max", "operator": "ge", "value": 1}
        ],
    }
    cells = [
        {
            "band": 0,
            "y": 0,
            "x": i,
            "count": 2 if i == 0 else 0,
            "status": "OBSERVED" if i == 0 else "NO_DATA",
            "near_limit_count": 0,
            "error": {
                "voltage_v": {
                    "median": 0.1 if i == 0 else None,
                    "p90": 0.2 if i == 0 else None,
                }
            },
            "disagreement": {
                "voltage_v": {
                    "median": 0.05 if i == 0 else None,
                    "p90": 0.08 if i == 0 else None,
                }
            },
        }
        for i in range(2)
    ]
    native_map = {
        "schema": "carbon.trust-map.v2",
        "maturity": "DEVELOPMENT",
        "model": "synthetic-model",
        "spec": spec,
        "top_models": ["a", "b"],
        "source": {
            "kind": "PUBLIC",
            "evidence": "synthetic fixture",
            "source_sha256": "5" * 64,
        },
        "reference_verification": accepted,
        "cells": cells,
        "basis": {"cases": 2, "models": 2, "top_models": 2},
        "methods": {
            "error": "synthetic",
            "disagreement": "synthetic",
            "marginalization": "synthetic",
        },
        "scored_case_selection": "FORBIDDEN",
    }
    estimates = {
        arm: {
            "mean_best_verified_value_conditional": value,
            "mean_regret_conditional": value / 10,
            "feasible_pick_fraction": 1.0,
        }
        for arm, value in (
            ("solver_alone", 5.0),
            ("baseline_then_solver", 6.0),
            ("model_then_solver", 4.0),
        )
    }
    estimates.update(paired_verified_value_delta=-1.0, paired_verified_value_count=8)
    equal = {
        "schema": "carbon.design-search.equal-budget-report.v1",
        "challenge": "battery-v3",
        "status": "OK",
        "cost_basis": "MEASURED",
        "source_digest": "sha256:" + "6" * 64,
        "panel_digest": "sha256:" + "7" * 64,
        "job_count": 8,
        "independent_clusters": 2,
        "confidence": 0.95,
        "objective": {"direction": "min", "unit": "s"},
        "curves": [
            {
                "budget": {"wall_s": 10, "core_s": 20},
                "estimates": estimates,
                "bootstrap_ci": {"paired_verified_value_delta": [-2.0, -0.5]},
            }
        ],
    }
    projection = {
        "schema": PROJECTION_SCHEMA,
        "mode": "DEVELOPMENT_SAMPLE",
        "challenge": CHALLENGE,
        "disclosure": {
            "kind": "PUBLIC",
            "evidence": "https://example.invalid/synthetic-only",
        },
        "identity": {
            "model_artifact_hash": "sha256:" + "2" * 64,
            "reference_image_digest": image,
            "physics_contract_digest": "sha256:"
            + hashlib.sha256(texts["P3"].encode()).hexdigest(),
        },
        "law_checks": {
            "producer": "PLT-01",
            "measurement_version": "fixture-v1",
            "laws": [
                {
                    "id": "initial-temperature",
                    "sample_count": 8,
                    "violation_rate": 0.25,
                    "residual_median": 0.1,
                    "unit": "K",
                    "outcome": "FAIL",
                    "adopted": False,
                    "calibration_image_digest": image,
                }
            ],
        },
        "model_card": card,
        "trust_map": native_map,
        "verify_r": {
            "schema": "carbon.design-search.verify-aware-result.v1",
            "rule_digest": "sha256:" + "8" * 64,
            "status": "SCORED",
            "v": 1 / 1.2,
            "mean_service_regret": 0.2,
            "offered": 8,
            "unscored": 0,
            "best_known_only": 0,
            "unresolved_family": 0,
            "none_feasible": 0,
        },
        "equal_budget": equal,
    }
    texts["P4"] = json.dumps(projection)
    return texts


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.texts = fixture_texts()
        self.temp = tempfile.TemporaryDirectory(prefix="carbon-deliverable-")
        self.root = Path(self.temp.name)
        self.assertTrue(
            self.root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        )

    def tearDown(self):
        # Verify the absolute recursive-cleanup target is our own fixture dir.
        assert self.root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        assert self.root.name.startswith("carbon-deliverable-")
        self.temp.cleanup()

    def outputs(self, texts=None, profile="nasa-std-7009b"):
        return render(
            CHALLENGE, profile, MemoryReader(texts or self.texts), self.policy
        )

    def test_manual_gaps_and_no_qualification_even_with_successful_rebuilds(self):
        record = json.loads(self.outputs()["sample.json"])
        self.assertEqual(record["eligible_tier"], "UNESTABLISHED")
        self.assertIsNone(record["qualification_record"])
        self.assertEqual(record["mode"], "DEVELOPMENT_SAMPLE")
        for section in record["sections"].values():
            if section["automation"] != "automatable now":
                self.assertEqual(section["coverage"], "GAP")
        findings = {f["id"]: f for f in record["adverse_findings"]}
        self.assertEqual(findings["EV5_ATTACK"]["outcome"], "FAIL")
        self.assertEqual(findings["Q1_MISSING_V3"]["outcome"], "NOT_ASSESSED")

    def test_changed_source_measurement_is_not_cached(self):
        self.texts["R2"] = self.texts["R2"].replace("56 of 99", "57 of 99")
        manifest = json.loads(self.outputs()["generation-manifest.json"])
        fact = next(f for f in manifest["facts"] if f["id"] == "EV4_FALSE_FEASIBLE")
        self.assertEqual(fact["value"], "57 / 99")
        self.assertEqual(fact["quantities"][0]["base"], 57)
        self.assertIn("#L", fact["citation"])

    def test_missing_attack_source_is_gap_and_other_failures_survive(self):
        self.texts.pop("R4")
        outputs = self.outputs()
        manifest = json.loads(outputs["generation-manifest.json"])
        self.assertIn("R4", manifest["missing_sources"])
        self.assertTrue(any("EV5_ATTACK" in x for x in manifest["extraction_gaps"]))
        self.assertIn("56 / 99", outputs["sample.md"])
        self.assertNotIn("no defects", outputs["sample.md"])

    def test_ambiguous_anchor_and_empty_reviews_are_gaps(self):
        self.texts["R4"] += "| Adversarial score | **PASS** |\n"
        self.texts["R1"] = '{"reviews": {}}'
        manifest = json.loads(self.outputs()["generation-manifest.json"])
        self.assertTrue(any("EV5_ATTACK" in x for x in manifest["extraction_gaps"]))
        self.assertTrue(any("reviews" in x for x in manifest["extraction_gaps"]))

    def test_unknown_challenge_and_profile_before_evidence_reads(self):
        reader = MemoryReader(self.texts)
        for challenge, profile in [
            ("unknown", "nasa-std-7009b"),
            (CHALLENGE, "unqualified-profile"),
        ]:
            with self.assertRaises(ValueError):
                render(challenge, profile, reader, self.policy)
        self.assertEqual(reader.calls, [])

    def test_new_adapters_keep_gaps_and_do_not_reuse_battery_facts(self):
        for challenge in ("motor", "cooling-cell", "f02"):
            texts = fixture_texts()
            if challenge == "motor":
                texts["R3"] = json.dumps(
                    {
                        "schema": "carbon.development-cheap-baseline-report.v1",
                        "family": "motor",
                        "held_out": {
                            "status": "HOLD_MISSING_GEOMETRY_AND_FULL_SIGNED_CURVES"
                        },
                        "v4_disposition": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
                        "closed_bank": {
                            "decision": {"summary": {"resolved": 0, "total": 20}}
                        },
                        "unregistered_sensitive_field": "do-not-disclose",
                    }
                )
            elif challenge == "cooling-cell":
                texts["C2"] = (
                    "Final lid/operating parameters await the owner's selection from Data\nThis is **cell-only**, not a full cold plate\n"
                )
            else:
                texts["R2"] = json.dumps(
                    {
                        "schema": "carbon.development.f02-question-law.v1",
                        "value_check": {"feasible": "NOT_DEMONSTRATED"},
                        "action_proposal": {"status": "HUMAN_INPUT"},
                        "cost": {"c2_status": "UNMEASURED"},
                        "context_count": 24,
                    }
                )
            for profile in ("nasa-std-7009b", "asme-vv10"):
                output = render(challenge, profile, MemoryReader(texts), self.policy)
                record = json.loads(output["sample.json"])
                manifest = json.loads(output["generation-manifest.json"])
                self.assertEqual(record["eligible_tier"], "UNESTABLISHED")
                self.assertIsNone(record["qualification_record"])
                self.assertFalse(manifest["qualification_claim"])
                self.assertFalse(
                    any(f["id"].startswith("EV5_") for f in manifest["facts"])
                )
                self.assertNotIn("do-not-disclose", output["sample.md"])
                self.assertTrue(all("role" in src for src in manifest["sources"]))
                self.assertEqual(record["sections"]["D01"]["coverage"], "GAP")

    def test_json_aggregate_wrong_family_missing_or_nonfinite_is_gap_not_zero(self):
        texts = fixture_texts()
        rule = next(
            r
            for r in self.policy["challenges"]["motor"]["extractors"]
            if r["id"] == "MOTOR_LOOKUP_TOTAL"
        )
        for raw in (
            "[]",
            '{"schema":"wrong","family":"motor"}',
            '{"schema":"carbon.development-cheap-baseline-report.v1","family":"battery-v3"}',
            '{"schema":"carbon.development-cheap-baseline-report.v1","family":"motor","closed_bank":{"decision":{"summary":{"total":NaN}}}}',
            '{"schema":"carbon.development-cheap-baseline-report.v1","family":"motor","closed_bank":{"decision":{"summary":{"total":true}}}}',
        ):
            source = Source(
                "R3",
                "docs/development/report.json",
                "a" * 40,
                git_blob(raw.encode()),
                raw,
            )
            with self.assertRaises((ValueError, TypeError)):
                scalar_fact(rule, source)
            texts["R3"] = raw
            manifest = json.loads(
                render("motor", "asme-vv10", MemoryReader(texts), self.policy)[
                    "generation-manifest.json"
                ]
            )
            self.assertFalse(
                any(f["id"] == "MOTOR_LOOKUP_TOTAL" for f in manifest["facts"])
            )
            self.assertTrue(
                any("MOTOR_LOOKUP_TOTAL" in gap for gap in manifest["extraction_gaps"])
            )

    def test_real_committed_adapters_extract_only_their_recorded_scope(self):
        root = Path(__file__).resolve().parents[2]
        reader = GitReader(
            root,
            "65ef88660fe02018c26f54d14655fe7b66354aa8",
            "65ef88660fe02018c26f54d14655fe7b66354aa8",
        )
        expected = {
            "motor": "MOTOR_HELD_OUT",
            "cooling-cell": "COOLING_PENDING_INPUTS",
            "f02": "F02_FEASIBILITY",
        }
        for challenge, fact_id in expected.items():
            output = render(challenge, "nasa-std-7009b", reader, self.policy)
            manifest = json.loads(output["generation-manifest.json"])
            self.assertEqual(manifest["missing_sources"], [])
            self.assertEqual(manifest["extraction_gaps"], [])
            self.assertIn(fact_id, {f["id"] for f in manifest["facts"]})
            self.assertEqual(
                manifest["evidence_revision"],
                "65ef88660fe02018c26f54d14655fe7b66354aa8",
            )
            self.assertTrue(
                all(f["outcome"] == "NOT_ASSESSED" for f in manifest["facts"])
            )

    def test_registered_sources_only_and_no_raw_metadata_disclosure(self):
        self.texts["R1"] = json.dumps(
            {
                "reviews": {
                    name: {
                        "state": "NOT_STARTED",
                        "authority": "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE",
                    }
                    for name in (
                        "customer",
                        "launch",
                        "numerical_reference",
                        "scientific",
                        "security",
                    )
                },
                "unrelated": "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE",
            }
        )
        readiness = json.loads(self.texts["R1"])
        readiness["reviews"]["SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"] = {"state": "PASS"}
        self.texts["R1"] = json.dumps(readiness)
        reader = MemoryReader(self.texts)
        output = render(CHALLENGE, "nasa-std-7009b", reader, self.policy)
        expected = (
            self.policy["framework"]
            + self.policy["challenges"][CHALLENGE]["sources"]
            + self.policy["challenges"][CHALLENGE]["package_sources"]
        )
        self.assertEqual(set(reader.calls), {s["path"] for s in expected})
        self.assertNotIn("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", str(output))
        for path in ("../escape", "hidden/cases.json", "AX42/data", "/absolute"):
            with self.assertRaises(ValueError):
                safe_path(path)

    def test_determinism_schema_copy_and_asme_licensed_gap(self):
        self.assertEqual(self.outputs(), self.outputs())
        manifest = json.loads(self.outputs()["generation-manifest.json"])
        factors = manifest["standard_rendering"]["factors"]
        self.assertEqual(len(factors["capability"]), 5)
        self.assertEqual(len(factors["results"]), 6)
        for group in factors.values():
            for factor in group:
                self.assertEqual(factor["formal_level"], "HUMAN_INPUT")
                self.assertEqual(factor["threshold"], "HUMAN_INPUT")
        self.assertIn("Appendix A record-location subset", self.outputs()["sample.md"])
        outputs = self.outputs(profile="asme-vv10")
        self.assertEqual(outputs["deliverable.schema.json"], self.texts["F2"])
        self.assertIn("ASME V&V 10 clause IDs: HUMAN_INPUT", outputs["sample.md"])
        self.assertNotIn("NASA fixture", outputs["sample.md"])
        self.assertNotIn(
            "factors",
            json.loads(outputs["generation-manifest.json"])["standard_rendering"],
        )

    def test_missing_framework_or_incomplete_crosswalk_refuses(self):
        self.texts.pop("F2")
        with self.assertRaises(ValueError):
            self.outputs()
        self.texts = fixture_texts()
        self.texts["F3"] = self.texts["F3"].replace("| D01 fixture", "| unknown")
        with self.assertRaises(ValueError):
            self.outputs()

    def test_offline_export_tampering_and_role_mismatch_refuse(self):
        spec = self.policy["framework"][0]
        data = self.texts["F1"].encode()
        (self.root / "F1.txt").write_bytes(data)
        item = {
            "path": spec["path"],
            "revision": "b" * 40,
            "git_blob": git_blob(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        receipt = {
            "schema": "PUBLIC_SOURCE_EXPORT_V1",
            "repository": "carbonphysicsai/Carbon",
            "evidence_revision": "a" * 40,
            "framework_revision": "b" * 40,
            "files": {"F1": item},
        }
        path = self.root / "receipt.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertIsNotNone(BundleReader(self.root).get(spec, framework=True))
        (self.root / "F1.txt").write_bytes(data + b"tampered")
        with self.assertRaises(ValueError):
            BundleReader(self.root).get(spec, framework=True)
        item["revision"] = "a" * 40
        path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaises(ValueError):
            BundleReader(self.root).get(spec, framework=True)

    def test_git_reader_uses_commit_and_ignores_working_tree(self):
        def git(*args):
            return subprocess.run(
                # Background upkeep writes and removes `.git` lock files
                # asynchronously, which races this fixture's own commands.
                [
                    "git",
                    "-C",
                    str(self.root),
                    "-c",
                    "maintenance.auto=false",
                    "-c",
                    "gc.auto=0",
                    *args,
                ],
                check=True,
                capture_output=True,
            ).stdout

        git("init")
        path = self.root / "public.md"
        path.write_text("committed synthetic fact\n", encoding="utf-8")
        git("add", "public.md")
        git(
            "-c",
            "user.name=Document Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        )
        revision = git("rev-parse", "HEAD").decode().strip()
        path.write_text("replacement synthetic corruption\n", encoding="utf-8")
        git("add", "public.md")
        git(
            "-c",
            "user.name=Document Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "replacement fixture",
        )
        replacement = git("rev-parse", "HEAD").decode().strip()
        git("replace", revision, replacement)
        path.write_text("uncommitted synthetic corruption\n", encoding="utf-8")
        reader = GitReader(self.root, revision, revision)
        source = reader.get({"id": "T1", "path": "public.md"})
        self.assertEqual(source.text, "committed synthetic fact\n")
        self.assertEqual(source.revision, revision)

    def test_existing_output_refuses_before_any_file_is_overwritten(self):
        (self.root / "sample.md").write_text("retain", encoding="utf-8")
        with self.assertRaises(ValueError):
            write_outputs(self.root, self.outputs())
        self.assertEqual((self.root / "sample.md").read_text(), "retain")
        self.assertFalse((self.root / "sample.json").exists())


class PackageEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.texts = package_fixture_texts()

    def outputs(self):
        return render(
            CHALLENGE, "nasa-std-7009b", MemoryReader(self.texts), self.policy
        )

    def package(self):
        return json.loads(self.outputs()["generation-manifest.json"])[
            "package_evidence"
        ]

    def mutate(self, change):
        projection = json.loads(self.texts["P4"])
        change(projection)
        self.texts["P4"] = json.dumps(projection)

    def test_honesty_note_keeps_current_plating_hold_and_original_source_outcomes(self):
        self.mutate(
            lambda p: p["model_card"]["accuracy_near_limits"].update(outcome="PASS")
        )
        for profile in ("nasa-std-7009b", "asme-vv10", "asme-vv40", "dod-vva"):
            with self.subTest(profile=profile):
                output = render(
                    CHALLENGE, profile, MemoryReader(self.texts), self.policy
                )
                text = output["sample.md"]
                self.assertIn("battery-plating-ref-v2", text)
                self.assertIn("No usable near-onset label", text)
                self.assertIn("SOLVER_NOT_ACCEPTED / GAP", text)
                self.assertIn("annotate, never re-score", text)
                self.assertIn("refinement/failure/fallback costs", text)
                self.assertIn(
                    "Host-declared use, domain and observable coverage are assertions",
                    text,
                )
                manifest = json.loads(output["generation-manifest.json"])
                package = manifest["package_evidence"]
                self.assertFalse(package["qualification_claim"])
                for name in (
                    "law_checks",
                    "model_card",
                    "trust_map",
                    "decision_evidence",
                ):
                    self.assertTrue(
                        any(
                            "battery-plating-ref-v2" in gap
                            and "SOLVER_NOT_ACCEPTED / GAP" in gap
                            for gap in package["sections"][name]["gaps"]
                        )
                    )
                row = next(
                    r
                    for r in package["sections"]["model_card"]["rows"]
                    if r["field"] == "accuracy_near_limits"
                )
                self.assertEqual(row["value"], 0.1)
                self.assertEqual(row["measurement_version"], "fixture-v1")
                self.assertEqual(row["outcome"], "PASS")
                annex = manifest["credibility_evidence"]
                indexed = next(
                    r
                    for r in annex["matrix"]
                    if r["requirement_id"] == "DEVREQ.model_card.accuracy_near_limits"
                )
                self.assertEqual(indexed["source_outcome"], "PASS")
                self.assertEqual(indexed["requirement_outcome"], "NOT_ASSESSED")
                self.assertTrue(
                    any(
                        "authority_ref are assertions" in limit
                        for limit in annex["limits"]
                    )
                )
                self.assertFalse(annex["qualification_claim"])

    def rows(self, section):
        return {
            row["field"]: row for row in self.package()["sections"][section]["rows"]
        }

    def test_five_views_fill_without_qualification_or_schema_widening(self):
        output = self.outputs()
        package = self.package()
        self.assertEqual(
            set(package["sections"]),
            {
                "law_checks",
                "model_card",
                "trust_map",
                "solver_verification",
                "decision_evidence",
            },
        )
        self.assertTrue(
            all(
                section["coverage"] == "PARTIAL"
                for section in package["sections"].values()
            )
        )
        record = json.loads(output["sample.json"])
        self.assertEqual(record["mode"], "DEVELOPMENT_SAMPLE")
        self.assertEqual(record["eligible_tier"], "UNESTABLISHED")
        self.assertIsNone(record["qualification_record"])
        self.assertFalse(package["qualification_claim"])
        self.assertEqual(output["deliverable.schema.json"], self.texts["F2"])
        self.assertEqual(
            set(output),
            {
                "sample.md",
                "sample.json",
                "deliverable.schema.json",
                "generation-manifest.json",
            },
        )

    def test_missing_projection_preserves_mms_and_named_gaps(self):
        self.texts.pop("P4")
        package = self.package()
        for name in ("law_checks", "model_card", "trust_map", "decision_evidence"):
            self.assertEqual(package["sections"][name]["coverage"], "GAP")
            self.assertTrue(package["sections"][name]["gaps"])
        self.assertEqual(
            package["sections"]["solver_verification"]["coverage"], "PARTIAL"
        )
        self.assertIsNone(package["identity"])

    def test_law_failure_retained_and_unadopted_draft_never_gate_authority(self):
        rows = self.rows("law_checks")
        failure = rows["initial-temperature.violation_rate"]
        self.assertEqual(failure["coverage"], "EVIDENCED")
        self.assertEqual(failure["outcome"], "FAIL")
        self.assertFalse(failure["gate_input_eligible"])
        self.assertEqual(rows["capacity-bound"]["coverage"], "GAP")
        record = json.loads(self.outputs()["sample.json"])
        self.assertTrue(
            any(
                f["outcome"] == "FAIL" and f["id"].startswith("PACKAGE_law_checks")
                for f in record["adverse_findings"]
            )
        )
        self.assertIn(
            "EV5 reported adversarial-score verdict: **FAIL**",
            self.outputs()["sample.md"],
        )

    def test_contract_and_calibration_mismatch_hold_only_law_join(self):
        for field in ("contract", "image"):
            with self.subTest(field=field):
                self.texts = package_fixture_texts()
                if field == "contract":
                    self.mutate(
                        lambda p: p["identity"].update(
                            physics_contract_digest="sha256:" + "f" * 64
                        )
                    )
                else:
                    self.mutate(
                        lambda p: p["law_checks"]["laws"][0].update(
                            calibration_image_digest="sha256:" + "f" * 64
                        )
                    )
                self.assertEqual(
                    self.package()["sections"]["law_checks"]["coverage"], "GAP"
                )
                self.assertEqual(
                    self.package()["sections"]["model_card"]["coverage"], "PARTIAL"
                )

    def test_each_card_metric_is_sourced_or_gap_and_floor_is_null(self):
        self.mutate(lambda p: p["model_card"].pop("extrapolation"))
        rows = self.rows("model_card")
        self.assertEqual(rows["accuracy_near_limits"]["sample_count"], 8)
        self.assertTrue(
            rows["accuracy_near_limits"]["citation"].endswith(
                "package-projection.json)"
            )
        )
        self.assertEqual(rows["extrapolation"]["coverage"], "GAP")
        self.assertIsNone(rows["extrapolation"]["value"])
        self.assertTrue(
            all(
                row["floor"] is None and row["floor_authority"] == "HUMAN_INPUT"
                for row in rows.values()
            )
        )

    def test_unmeasured_or_nonfinite_card_values_never_zero_or_pass(self):
        for value, count in ((None, 0), (True, 8), (float("inf"), 8), (0.1, True)):
            with self.subTest(value=value, count=count):
                self.texts = package_fixture_texts()
                self.mutate(
                    lambda p, value=value, count=count: p["model_card"][
                        "robustness"
                    ].update(value=value, sample_count=count, outcome="PASS")
                )
                row = self.rows("model_card")["robustness"]
                self.assertEqual(row["coverage"], "GAP")
                self.assertIsNone(row["value"])
                self.assertNotEqual(row["outcome"], "PASS")

    def test_reference_and_infra_failure_classification_survives_null_measurement(self):
        for state in ("FAILED_REFERENCE", "FAILED_INFRA"):
            self.texts = package_fixture_texts()
            self.mutate(
                lambda p, state=state: p["model_card"]["accuracy_overall"].update(
                    value=None, sample_count=0, outcome=state
                )
            )
            row = self.rows("model_card")["accuracy_overall"]
            self.assertEqual(row["coverage"], "GAP")
            self.assertEqual(row["outcome"], state)
            record = json.loads(self.outputs()["sample.json"])
            self.assertTrue(
                any(f["outcome"] == state for f in record["adverse_findings"])
            )

    def test_native_map_preserves_cells_units_and_no_data(self):
        rows = self.rows("trust_map")
        self.assertEqual(rows["cell.0.error.voltage_v.median"]["value"], 0.1)
        self.assertEqual(rows["cell.0.error.voltage_v.median"]["unit"], "V")
        empty = rows["cell.1.error.voltage_v.median"]
        self.assertEqual(empty["coverage"], "GAP")
        self.assertIsNone(empty["value"])
        self.assertEqual(rows["law_layer"]["coverage"], "GAP")
        self.assertEqual(rows["interval_layer"]["coverage"], "GAP")

    def test_map_disclosure_reference_and_denominator_mismatches_are_gaps(self):
        changes = [
            lambda p: p["trust_map"]["source"].update(kind="PROTECTED"),
            lambda p: p["trust_map"]["reference_verification"].update(
                image_digest="sha256:" + "f" * 64
            ),
            lambda p: p["trust_map"]["basis"].update(cases=999),
            lambda p: p["trust_map"]["cells"][1].update(count=1),
        ]
        for change in changes:
            self.texts = package_fixture_texts()
            self.mutate(change)
            self.assertEqual(self.package()["sections"]["trust_map"]["coverage"], "GAP")

    def test_mms_observations_and_acceptance_link_are_separate(self):
        rows = self.rows("solver_verification")
        self.assertEqual(rows["norm.0.l2"]["value"], 0.01)
        self.assertEqual(rows["machine_verdict"]["value"], "HUMAN_INPUT")
        self.assertFalse(rows["machine_acceptance"]["value"])
        self.assertEqual(
            rows["owner_acceptance_link"]["value"], "RECORDED_OWNER_DECISION"
        )
        self.assertEqual(rows["physical_validation"]["coverage"], "GAP")

    def test_successful_ev5_rebuild_is_never_mms(self):
        self.texts.pop("P1")
        self.texts.pop("P4")
        self.assertEqual(
            self.package()["sections"]["solver_verification"]["coverage"], "GAP"
        )
        self.assertIn("110 / 110", self.outputs()["sample.md"])

    def test_missing_or_mismatched_acceptance_refuses_maps_and_dependent_joins(self):
        for mutation in ("missing", "image", "criteria", "decision", "old_prose"):
            with self.subTest(mutation=mutation):
                self.texts = package_fixture_texts()
                if mutation == "missing":
                    self.texts.pop("P2")
                elif mutation == "decision":
                    self.texts["P6"] += " changed"
                elif mutation == "old_prose":
                    self.texts["P2"] = (
                        "OWNER-CODE-VERIFICATION-ACCEPT-01\n" + "sha256:" + "1" * 64
                    )
                else:
                    link = json.loads(self.texts["P2"])
                    link[mutation + "_digest"] = "sha256:" + "a" * 64
                    self.texts["P2"] = json.dumps(link)
                package = self.package()
                self.assertIsNone(package["identity"])
                rows = self.rows("solver_verification")
                self.assertEqual(rows["owner_acceptance_link"]["coverage"], "GAP")
                self.assertEqual(rows["norm.0.l2"]["value"], 0.01)
                self.assertEqual(package["sections"]["trust_map"]["coverage"], "GAP")

    def test_legacy_map_pass_flag_does_not_establish_acceptance(self):
        self.mutate(lambda p: p["trust_map"].update(schema="carbon.trust-map.v1"))
        self.assertEqual(self.rows("trust_map")["map"]["coverage"], "GAP")

    def test_wrong_mms_family_or_unmeasured_mms_refuses_dependent_joins(self):
        for change in (
            lambda p: p.update(family="motor"),
            lambda p: p.update(norms=[]),
            lambda p: p.update(image_digest="not-an-image"),
        ):
            self.texts = package_fixture_texts()
            mms = json.loads(self.texts["P1"])
            change(mms)
            self.texts["P1"] = json.dumps(mms)
            package = self.package()
            self.assertIsNone(package["identity"])
            self.assertEqual(
                package["sections"]["solver_verification"]["coverage"], "GAP"
            )
            self.assertEqual(package["sections"]["model_card"]["coverage"], "GAP")

    def test_verify_r_and_equal_budget_keep_distinct_bases(self):
        rows = self.rows("decision_evidence")
        self.assertEqual(rows["verify_r.regret"]["value"], 0.2)
        self.assertEqual(
            rows["verify_r.regret"]["unit"], "dimensionless bounded regret"
        )
        self.assertEqual(rows["curve.0.paired_delta"]["value"], -1.0)
        self.assertEqual(rows["curve.0.paired_delta"]["unit"], "s")
        self.assertEqual(rows["curve.0.paired_ci"]["value"], [-2.0, -0.5])
        self.assertEqual(rows["false_feasibility"]["coverage"], "GAP")

    def test_incomplete_verify_r_has_no_regret_default(self):
        self.mutate(
            lambda p: p["verify_r"].update(status="INCOMPLETE_LEGS", unscored=1, v=None)
        )
        row = self.rows("decision_evidence")["verify_r.regret"]
        self.assertEqual(row["coverage"], "GAP")
        self.assertIsNone(row["value"])

    def test_assumed_unresolved_or_wrong_family_equal_budget_cannot_be_measurement(
        self,
    ):
        for change in (
            lambda r: r.update(cost_basis="ASSUMPTION"),
            lambda r: r.update(status="UNRESOLVED_PANEL"),
            lambda r: r.update(challenge="motor"),
        ):
            self.texts = package_fixture_texts()
            self.mutate(lambda p, change=change: change(p["equal_budget"]))
            row = self.rows("decision_evidence")["equal_budget"]
            self.assertEqual(row["coverage"], "GAP")
            self.assertIsNone(row["value"])

    def test_incomplete_paired_jobs_retain_adverse_arms_and_gap_the_delta(self):
        def change(p):
            estimates = p["equal_budget"]["curves"][0]["estimates"]
            estimates["paired_verified_value_count"] = 7
            estimates["paired_verified_value_delta"] = None
            estimates["model_then_solver"]["feasible_pick_fraction"] = 0.5

        self.mutate(change)
        rows = self.rows("decision_evidence")
        self.assertEqual(rows["curve.0.paired_delta"]["coverage"], "GAP")
        self.assertEqual(
            rows["curve.0.model_then_solver.feasible_pick_fraction"]["value"], 0.5
        )

    def test_projection_identity_and_disclosure_fail_closed_without_input_echo(self):
        changes = [
            lambda p: p.update(challenge="motor"),
            lambda p: p["identity"].update(reference_image_digest="sha256:" + "f" * 64),
            lambda p: p["disclosure"].update(kind="PROTECTED"),
            lambda p: p.update(unregistered="SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"),
        ]
        for change in changes:
            self.texts = package_fixture_texts()
            self.mutate(change)
            output = self.outputs()
            package = json.loads(output["generation-manifest.json"])["package_evidence"]
            self.assertIsNone(package["identity"])
            self.assertNotIn("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", str(output))

    def test_malformed_nested_interval_is_a_gap_without_stopping_other_evidence(self):
        self.mutate(
            lambda p: p["equal_budget"]["curves"][0].update(
                bootstrap_ci=["SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"]
            )
        )
        output = self.outputs()
        self.assertEqual(
            self.rows("decision_evidence")["equal_budget"]["coverage"], "GAP"
        )
        self.assertEqual(
            self.rows("decision_evidence")["verify_r.regret"]["value"], 0.2
        )
        self.assertEqual(self.rows("solver_verification")["norm.0.l2"]["value"], 0.01)
        self.assertNotIn("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", str(output))

    def test_malformed_draft_shapes_are_gaps_without_stopping_other_evidence(self):
        for shape in ("root", "required_outputs"):
            with self.subTest(shape=shape):
                self.texts = package_fixture_texts()
                draft = json.loads(self.texts["P3"])
                if shape == "root":
                    draft = ["SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"]
                else:
                    draft["required_outputs"] = ["SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"]
                self.texts["P3"] = json.dumps(draft)
                output = self.outputs()
                self.assertEqual(self.rows("law_checks")["contract"]["coverage"], "GAP")
                self.assertEqual(
                    self.rows("solver_verification")["norm.0.l2"]["value"], 0.01
                )
                self.assertEqual(
                    self.rows("model_card")["accuracy_overall"]["value"], 0.1
                )
                self.assertNotIn("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", str(output))

    def test_duplicate_json_keys_and_raw_questions_do_not_escape(self):
        self.texts["P4"] = self.texts["P4"].replace(
            '"model_card":', '"model_card": null, "model_card":', 1
        )
        self.assertIsNone(self.package()["identity"])
        self.texts = package_fixture_texts()
        self.mutate(
            lambda p: p["verify_r"].update(
                questions=["SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"]
            )
        )
        self.assertNotIn("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", str(self.outputs()))
        self.assertEqual(self.rows("decision_evidence")["verify_r"]["coverage"], "GAP")

    def test_all_registered_families_have_package_views_without_cross_family_facts(
        self,
    ):
        for challenge in (CHALLENGE, "f02", "motor", "cooling-cell"):
            output = render(
                challenge, "asme-vv10", MemoryReader(fixture_texts()), self.policy
            )
            package = json.loads(output["generation-manifest.json"])["package_evidence"]
            self.assertEqual(package["challenge"], challenge)
            self.assertEqual(len(package["sections"]), 5)
            self.assertTrue(
                all(
                    section["coverage"] == "GAP"
                    for section in package["sections"].values()
                )
            )

    def test_package_generation_is_deterministic_and_public_paths_stay_registered(self):
        self.assertEqual(self.outputs(), self.outputs())
        reader = MemoryReader(self.texts)
        render(CHALLENGE, "nasa-std-7009b", reader, self.policy)
        config = self.policy["challenges"][CHALLENGE]
        self.assertEqual(
            set(reader.calls),
            {
                item["path"]
                for item in self.policy["framework"]
                + config["sources"]
                + config["package_sources"]
            },
        )
        manifest = json.loads(self.outputs()["generation-manifest.json"])
        self.assertRegex(manifest["source_policy_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(
            all(
                row["evidence_refs"] == ["P4"]
                for row in self.rows("model_card").values()
            )
        )


class CredibilityAutofillTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.texts = package_fixture_texts()

    def outputs(self, profile="nasa-std-7009b"):
        return render(CHALLENGE, profile, MemoryReader(self.texts), self.policy)

    def annex(self):
        return json.loads(self.outputs()["generation-manifest.json"])[
            "credibility_evidence"
        ]

    def context(self):
        from scripts.dev.customer_deliverable.credibility import CONTEXT_SCHEMA

        context = {
            "schema": CONTEXT_SCHEMA,
            "mode": "DEVELOPMENT_SAMPLE",
            "challenge": CHALLENGE,
            "disclosure": {
                "kind": "PUBLIC",
                "evidence": "https://example.invalid/synthetic-only",
            },
            "identity": json.loads(self.texts["P4"])["identity"],
            "context_of_use": {
                "id": "synthetic-screening-only",
                "version": "fixture-v1",
            },
            "model_influence": {
                "value": "SYNTHETIC_ONE_INPUT_AMONG_OTHERS",
                "authority_ref": "sha256:" + "9" * 64,
            },
            "decision_consequence": {
                "value": "SYNTHETIC_EXPLORATORY_REWORK",
                "authority_ref": "sha256:" + "a" * 64,
            },
            "required_credibility": {"value": None, "authority_ref": None},
        }
        return context

    def test_matrix_retains_failed_observations_without_issuing_acceptance(self):
        annex = self.annex()
        matrix = {row["requirement_id"]: row for row in annex["matrix"]}
        row = matrix["DEVREQ.law_checks.initial-temperature.violation_rate"]
        self.assertEqual(row["coverage"], "EVIDENCED")
        self.assertEqual(row["source_outcome"], "FAIL")
        self.assertEqual(row["value"], 0.25)
        self.assertEqual(row["unit"], "fraction")
        self.assertEqual(row["sample_count"], 8)
        self.assertEqual(row["measurement_version"], "fixture-v1")
        self.assertEqual(
            row["adverse_links"],
            ["PACKAGE_law_checks.initial-temperature.violation_rate"],
        )
        self.assertEqual(row["identity"], annex["identity"])
        self.assertEqual(row["source_versions"][0]["revision"], "a" * 40)
        self.assertIsNone(matrix["DEVREQ.historical.EV5_ATTACK"]["identity"])
        self.assertIn(
            "EV5_ATTACK", matrix["DEVREQ.historical.EV5_ATTACK"]["adverse_links"]
        )
        self.assertEqual(len(matrix), len(annex["matrix"]))
        for row in matrix.values():
            self.assertEqual(row["requirement_outcome"], "NOT_ASSESSED")
            self.assertIsNone(row["criterion"])
            self.assertEqual(row["criterion_authority"], "HUMAN_INPUT")
        self.assertFalse(annex["qualification_claim"])
        self.assertFalse(annex["compliance_claim"])
        self.assertFalse(annex["accreditation_claim"])

    def test_source_pass_and_mms_never_become_physical_or_requirement_pass(self):
        projection = json.loads(self.texts["P4"])
        projection["model_card"]["accuracy_overall"]["outcome"] = "PASS"
        self.texts["P4"] = json.dumps(projection)
        annex = self.annex()
        rows = {row["requirement_id"]: row for row in annex["matrix"]}
        card = rows["DEVREQ.model_card.accuracy_overall"]
        self.assertEqual(card["source_outcome"], "PASS")
        self.assertEqual(card["requirement_outcome"], "NOT_ASSESSED")
        self.assertEqual(card["measurement_version"], "fixture-v1")
        self.assertEqual(
            rows["DEVREQ.solver_verification.physical_validation"]["coverage"], "GAP"
        )
        self.assertIsNone(rows["DEVREQ.solver_verification.norm.0.l2"]["identity"])

    def test_reference_and_infra_failures_remain_typed_in_matrix_and_findings(self):
        for outcome in ("FAILED_REFERENCE", "FAILED_INFRA"):
            with self.subTest(outcome=outcome):
                projection = json.loads(self.texts["P4"])
                projection["model_card"]["robustness"].update(
                    value=None, outcome=outcome
                )
                self.texts["P4"] = json.dumps(projection)
                annex = self.annex()
                row = next(
                    row
                    for row in annex["matrix"]
                    if row["requirement_id"] == "DEVREQ.model_card.robustness"
                )
                self.assertEqual(row["source_outcome"], outcome)
                self.assertEqual(row["coverage"], "GAP")
                self.assertTrue(row["adverse_links"])

    def test_risk_unknowns_and_all_eleven_goals_remain_explicit(self):
        plan = self.annex()["risk_informed_plan"]
        self.assertIsNone(plan["context_of_use"])
        for field in (
            "model_influence",
            "decision_consequence",
            "required_credibility",
        ):
            self.assertIsNone(plan[field]["value"])
            self.assertEqual(plan[field]["basis"], "HUMAN_INPUT")
        self.assertIsNone(plan["risk_combination"]["value"])
        self.assertIsNone(plan["risk_combination"]["rule"])
        self.assertEqual(
            [goal["id"] for goal in plan["goals"]],
            [f"DEVREQ.D{i:02}" for i in range(1, 12)],
        )
        self.assertTrue(
            all(
                goal["next_proof"] and goal["authority"] == "HUMAN_INPUT"
                for goal in plan["goals"]
            )
        )

    def test_declared_context_copies_only_matched_public_fields_without_risk_math(self):
        context = self.context()
        context["required_credibility"] = {
            "value": "SYNTHETIC_OWNER_GOAL",
            "authority_ref": "sha256:" + "b" * 64,
        }
        self.texts["P8"] = json.dumps(context)
        plan = self.annex()["risk_informed_plan"]
        self.assertEqual(plan["context_of_use"], context["context_of_use"])
        for field in (
            "model_influence",
            "decision_consequence",
            "required_credibility",
        ):
            self.assertEqual(plan[field]["value"], context[field]["value"])
            self.assertEqual(
                plan[field]["authority_ref"], context[field]["authority_ref"]
            )
            self.assertEqual(
                plan[field]["basis"], "PUBLIC_DECLARATION_NOT_AUTHENTICATED_ACCEPTANCE"
            )
        self.assertIsNone(plan["risk_combination"]["value"])
        self.assertIsNone(plan["risk_combination"]["rule"])

    def test_context_refusals_do_not_echo_input_or_hide_other_adverse_evidence(self):
        for kind in (
            "family",
            "image",
            "artifact",
            "contract",
            "private",
            "mode",
            "schema",
            "extra",
            "authority",
            "numeric",
            "placeholder",
            "duplicate",
            "no_projection",
            "no_acceptance",
            "no_contract",
            "changed_contract",
            "unnamed_use",
        ):
            with self.subTest(kind=kind):
                self.texts = package_fixture_texts()
                context = self.context()
                if kind == "family":
                    context["challenge"] = "motor"
                elif kind in {"image", "artifact", "contract"}:
                    key = {
                        "image": "reference_image_digest",
                        "artifact": "model_artifact_hash",
                        "contract": "physics_contract_digest",
                    }[kind]
                    context["identity"][key] = "sha256:" + "f" * 64
                elif kind == "private":
                    context["disclosure"]["kind"] = "PRIVATE"
                elif kind in {"mode", "schema"}:
                    context[kind] = "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"
                elif kind == "extra":
                    context["raw_samples"] = "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"
                elif kind == "authority":
                    context["model_influence"]["authority_ref"] = None
                elif kind == "numeric":
                    context["model_influence"]["value"] = 4
                elif kind == "placeholder":
                    context["model_influence"]["value"] = "HUMAN_INPUT"
                elif kind == "no_projection":
                    del self.texts["P4"]
                elif kind == "no_acceptance":
                    del self.texts["P2"]
                elif kind == "no_contract":
                    del self.texts["P3"]
                elif kind == "changed_contract":
                    self.texts["P3"] += "\n"
                elif kind == "unnamed_use":
                    context["context_of_use"]["id"] = "HUMAN_INPUT"
                self.texts["P8"] = json.dumps(context)
                if kind == "duplicate":
                    self.texts["P8"] = self.texts["P8"].replace(
                        '{"schema":',
                        '{"schema": "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE", "schema":',
                        1,
                    )
                output = self.outputs()
                annex = json.loads(output["generation-manifest.json"])[
                    "credibility_evidence"
                ]
                self.assertIsNone(annex["risk_informed_plan"]["context_of_use"])
                self.assertTrue(
                    any(
                        gap.startswith("P8:")
                        for gap in annex["risk_informed_plan"]["gaps"]
                    )
                )
                self.assertTrue(
                    any(
                        finding["id"] == "EV5_ATTACK" and finding["outcome"] == "FAIL"
                        for finding in annex["retained_findings"]
                    )
                )
                self.assertNotIn("SYNTHETIC_CANARY", str(output))

    def test_unknown_context_values_are_not_filled_from_map_or_card(self):
        context = self.context()
        for field in (
            "model_influence",
            "decision_consequence",
            "required_credibility",
        ):
            context[field] = {"value": None, "authority_ref": None}
        self.texts["P8"] = json.dumps(context)
        plan = self.annex()["risk_informed_plan"]
        self.assertIsNotNone(plan["context_of_use"])
        self.assertTrue(
            all(
                plan[field]["value"] is None
                for field in (
                    "model_influence",
                    "decision_consequence",
                    "required_credibility",
                )
            )
        )

    def test_new_profiles_use_the_frozen_crosswalk_columns_for_all_families(self):
        for challenge in (CHALLENGE, "f02", "motor", "cooling-cell"):
            for profile, expected in (("asme-vv40", "topic"), ("dod-vva", "DoD")):
                with self.subTest(challenge=challenge, profile=profile):
                    output = render(
                        challenge, profile, MemoryReader(fixture_texts()), self.policy
                    )
                    manifest = json.loads(output["generation-manifest.json"])
                    standard = manifest["standard_rendering"]
                    self.assertEqual(
                        standard["mapping_status"],
                        (
                            "TOPIC_ONLY_LICENSED_CLAUSES_HUMAN_INPUT"
                            if profile == "asme-vv40"
                            else "MIL_TEMPLATE_ANCHORS_DODI_CONTENTS_ONLY"
                        ),
                    )
                    self.assertEqual(standard["acceptance_authority"], "HUMAN_INPUT")
                    self.assertFalse(standard["clause_complete"])
                    self.assertEqual(len(standard["section_mapping"]), 11)
                    self.assertEqual(
                        {row["anchor"] for row in standard["section_mapping"]},
                        {expected},
                    )
                    self.assertFalse(standard["qualification_claim"])
                    self.assertEqual(
                        json.loads(output["sample.json"])["schema_version"],
                        "PROPOSAL_V1",
                    )
                    self.assertIn("not accreditation", output["sample.md"])

    def test_defense_questions_keep_customer_actions_even_when_all_artifacts_exist(
        self,
    ):
        questions = self.annex()["defense_vva"]
        self.assertEqual(len(questions), 6)
        self.assertTrue(
            all(
                q["coverage"] in {"PARTIAL", "GAP"}
                and q["customer_action"]
                and q["accreditation_outcome"] == "NOT_ASSESSED"
                for q in questions
            )
        )
        self.assertTrue(all(q["mapping_source"] == "F3" for q in questions))

    def test_f02_both_runs_show_conditional_owner_decision_and_original_orders(self):
        root = Path(__file__).resolve().parents[2]
        output = render(
            "f02", "nasa-std-7009b", GitReader(root, "HEAD", "HEAD"), self.policy
        )
        manifest = json.loads(output["generation-manifest.json"])
        rows = {
            row["field"]: row
            for row in manifest["package_evidence"]["sections"]["solver_verification"][
                "rows"
            ]
        }
        self.assertEqual(
            rows["owner_acceptance_link"]["value"],
            "CONDITIONAL, t_end 0.375 (MMS test-design scope)",
        )
        self.assertEqual(
            rows["supplement.owner_acceptance_link"]["value"],
            rows["owner_acceptance_link"]["value"],
        )
        self.assertEqual(rows["acceptance_conditions"]["value"], {"t_end": 0.375})
        self.assertIn("time_orders.0.max", rows)
        self.assertIn("supplement.time_orders.0.max", rows)
        original_spec = next(
            item
            for item in self.policy["challenges"]["f02"]["package_sources"]
            if item["id"] == "P1"
        )
        original = json.loads(GitReader(root, "HEAD", "HEAD").get(original_spec).text)
        self.assertEqual(
            rows["time_orders.0.max"]["value"], original["time_orders"][0]["max"]
        )

    def test_mms_units_name_manufactured_error_separately_from_observed_order(self):
        rows = {
            row["field"]: row
            for row in json.loads(self.outputs()["generation-manifest.json"])[
                "package_evidence"
            ]["sections"]["solver_verification"]["rows"]
        }
        self.assertEqual(
            rows["norm.0.l2"]["unit"], "dimensionless manufactured-solution error"
        )
        self.assertEqual(rows["l2_order"]["unit"], "dimensionless observed order")
        self.assertNotIn("code-verification fixture", str(self.outputs()))

    def test_generation_replays_and_matrix_sources_are_registered(self):
        self.texts["P8"] = json.dumps(self.context())
        self.assertEqual(self.outputs(), self.outputs())
        annex = self.annex()
        registered = {
            item["id"]
            for item in self.policy["challenges"][CHALLENGE]["package_sources"]
            + self.policy["challenges"][CHALLENGE]["sources"]
        }
        self.assertTrue(
            all(set(row["evidence_refs"]) <= registered for row in annex["matrix"])
        )


if __name__ == "__main__":
    unittest.main()
