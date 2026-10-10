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
    write_outputs,
)

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
            self.policy["framework"] + self.policy["challenges"][CHALLENGE]["sources"]
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
                ["git", "-C", str(self.root), *args], check=True, capture_output=True
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


if __name__ == "__main__":
    unittest.main()
