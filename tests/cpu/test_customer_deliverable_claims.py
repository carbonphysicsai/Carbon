"""Synthetic citation controls; no reference solve or scientific qualification."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.customer_deliverable.claims import (
    SCHEMA,
    check_generated_manifest,
    check_inventory,
    check_package_outputs,
    generated_claims,
    locate,
    require_pass,
    sha256,
)
from scripts.dev.customer_deliverable.generate import load_policy, render
from tests.cpu.test_customer_deliverable_generator import (
    CHALLENGE,
    MemoryReader,
    package_fixture_texts,
)

ROOT = Path(__file__).resolve().parents[2]


def citation(artifact, data, kind="file", value="file"):
    locator = {"kind": kind, "value": value}
    return {
        "artifact": artifact,
        "locator": locator,
        "sha256": sha256(locate(data, locator)),
    }


def fixture_inventory():
    payloads = {
        "public/measurement.json": b'{"value": 1}',
        "public/version.json": b'{"version": "fixture-v1"}',
    }
    artifacts = [
        {
            "id": "measurement",
            "path": "public/measurement.json",
            "sha256": sha256(payloads["public/measurement.json"]),
        },
        {
            "id": "reference",
            "path": "public/version.json",
            "sha256": sha256(payloads["public/version.json"]),
        },
    ]
    surfaces, claims = [], []
    for surface in ("package", "guard", "model-card", "trust-map", "crosswalk"):
        path = f"public/{surface}.md"
        data = b"Synthetic fixture-v1 source observation: 1."
        payloads[path] = data
        artifacts.append({"id": surface, "path": path, "sha256": sha256(data)})
        key = surface + ".synthetic-observation"
        surfaces.append({"id": surface, "artifact": surface, "claims": [key]})
        claims.append(
            {
                "id": key,
                "surface": surface,
                "statement": citation(surface, data),
                "basis": "SOURCE_OBSERVATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "citations": [
                    citation(
                        "measurement",
                        payloads["public/measurement.json"],
                        "json-pointer",
                        "/value",
                    )
                ],
                "reference": None,
            }
        )
    return {
        "schema": SCHEMA,
        "surfaces": surfaces,
        "artifacts": artifacts,
        "claims": claims,
    }, payloads


def test_actual_five_surface_artifacts_and_locators_are_examined():
    inventory, payloads = fixture_inventory()
    seen = []

    def read(path):
        seen.append(path)
        return payloads.get(path)

    report = require_pass(check_inventory(inventory, read))
    assert report["claims_examined"] == 5
    assert len(seen) == report["artifacts_examined"] == 7
    assert report["qualification_claim"] is False
    assert report["basis"] == "ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE"


@pytest.mark.parametrize(
    "surface", ["package", "guard", "model-card", "trust-map", "crosswalk"]
)
def test_missing_statement_is_fail_named_by_claim_and_artifact(surface):
    inventory, payloads = fixture_inventory()
    del payloads[f"public/{surface}.md"]
    report = check_inventory(inventory, payloads.get)
    assert report["status"] == "FAIL"
    with pytest.raises(
        ValueError, match=rf"{surface}\.synthetic-observation: public/{surface}\.md"
    ):
        require_pass(report)


@pytest.mark.parametrize("change", ["missing", "changed", "empty"])
def test_evidence_absence_and_changed_bytes_never_pass(change):
    inventory, payloads = fixture_inventory()
    if change == "missing":
        del payloads["public/measurement.json"]
    else:
        payloads["public/measurement.json"] = (
            b'{"value": 2}' if change == "changed" else b""
        )
    report = check_inventory(inventory, payloads.get)
    assert all(row["status"] == "FAIL" for row in report["results"])
    with pytest.raises(ValueError, match="public/measurement.json"):
        require_pass(report)


def test_changed_scalar_still_fails_after_artifact_digest_is_rebound():
    inventory, payloads = fixture_inventory()
    payloads["public/measurement.json"] = b'{"value": 2}'
    inventory["artifacts"][0]["sha256"] = sha256(payloads["public/measurement.json"])
    report = check_inventory(inventory, payloads.get)
    assert report["status"] == "FAIL"
    assert "cited claim value/text changed" in str(report)


def test_superseded_reference_is_not_accepted_after_bytes_are_rebound():
    inventory, payloads = fixture_inventory()
    claim = inventory["claims"][0]
    claim["requirement"] = "CURRENT_REFERENCE"
    claim["reference"] = {
        "artifact": "reference",
        "locator": {"kind": "json-pointer", "value": "/version"},
        "version": "fixture-v1",
    }
    assert check_inventory(inventory, payloads.get)["status"] == "PASS"
    payloads["public/version.json"] = b'{"version": "fixture-v2"}'
    inventory["artifacts"][1]["sha256"] = sha256(payloads["public/version.json"])
    report = check_inventory(inventory, payloads.get)
    assert report["status"] == "FAIL"
    assert "reference version superseded" in str(report)
    assert "public/version.json" in str(report)


@pytest.mark.parametrize(
    "basis", ["HOST_DECLARED_NOT_COMPARED", "IMPLEMENTATION", "SOURCE_OBSERVATION"]
)
def test_valid_citation_cannot_invent_verified_authority(basis):
    inventory, payloads = fixture_inventory()
    inventory["claims"][0].update(basis=basis, requirement="VERIFIED")
    report = check_inventory(inventory, payloads.get)
    assert report["results"][0]["status"] == "FAIL"
    assert report["qualification_claim"] is False


def test_empty_or_removed_inventory_is_not_a_green_from_nothing():
    inventory, payloads = fixture_inventory()
    inventory["claims"].pop()
    with pytest.raises(ValueError, match="complete surface claim coverage"):
        check_inventory(inventory, payloads.get)
    inventory["claims"] = []
    with pytest.raises(ValueError, match="nonempty"):
        check_inventory(inventory, payloads.get)


def test_new_uncited_presentation_text_invalidates_surface_lock():
    inventory, payloads = fixture_inventory()
    payloads["public/guard.md"] += b"\nUnsupported new speed claim: 100."
    report = check_inventory(inventory, payloads.get)
    assert report["status"] == "FAIL"
    assert "guard.synthetic-observation" in str(report)


def test_python_reference_selector_never_executes_code():
    data = b'PANEL_SCHEMA = "fixture-v2"\nraise AssertionError("must not execute")\n'
    assert (
        locate(data, {"kind": "python-constant", "value": "PANEL_SCHEMA"})
        == b"fixture-v2"
    )
    with pytest.raises(ValueError, match="literal"):
        locate(
            b"PANEL_SCHEMA = malicious()\n",
            {"kind": "python-constant", "value": "PANEL_SCHEMA"},
        )


def snapshot(profile="nasa-std-7009b"):
    texts = package_fixture_texts()
    outputs = render(CHALLENGE, profile, MemoryReader(texts), load_policy())
    return json.loads(outputs["generation-manifest.json"]), texts


@pytest.mark.parametrize(
    "profile", ["nasa-std-7009b", "asme-vv10", "asme-vv40", "dod-vva"]
)
def test_all_profiles_publish_actual_claim_inventory_and_traceability_basis(profile):
    manifest, texts = snapshot(profile)
    assert manifest["claim_inventory"] == generated_claims(manifest)
    report = require_pass(
        check_generated_manifest(manifest, MemoryReader(texts), load_policy())
    )
    assert report["claims_examined"] > 0
    assert report["basis"] == "ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE"
    assert manifest["credibility_evidence"]["qualification_claim"] is False


def test_old_output_fails_when_actual_registered_evidence_changes():
    manifest, texts = snapshot()
    texts["R2"] = texts["R2"].replace("56 of 99", "57 of 99")
    report = check_generated_manifest(manifest, MemoryReader(texts), load_policy())
    assert report["status"] == "FAIL"
    assert "EV4_FALSE_FEASIBLE" in str(report)
    assert "BATTERY_ENGINEERING_VALUE_EV4.md" in str(report)


def test_old_output_fails_when_artifact_disappears_in_current_commit():
    manifest, texts = snapshot()
    del texts["P4"]
    report = check_generated_manifest(manifest, MemoryReader(texts), load_policy())
    assert report["status"] == "FAIL"
    assert "package-projection.json" in str(report)
    assert "cited artifact missing" in str(report)


def test_forged_numeric_claim_and_inventory_are_compared_with_actual_source():
    manifest, texts = snapshot()
    manifest["package_evidence"]["sections"]["model_card"]["rows"][0]["value"] = 123
    manifest["claim_inventory"] = generated_claims(manifest)
    report = check_generated_manifest(manifest, MemoryReader(texts), load_policy())
    assert report["status"] == "FAIL"
    assert "model_card.accuracy_overall" in str(report)
    assert "actual registered artifact" in str(report)


@pytest.mark.parametrize(
    "mutation",
    ["remove_inventory", "extra_number", "qualification", "compliance", "risk"],
)
def test_unindexed_or_unsupported_claim_cannot_bypass_known_row_checks(mutation):
    manifest, texts = snapshot()
    manifest = copy.deepcopy(manifest)
    if mutation == "remove_inventory":
        del manifest["claim_inventory"]
    elif mutation == "extra_number":
        manifest["unsupported_speedup"] = 100
    elif mutation == "qualification":
        manifest["qualification_claim"] = True
    elif mutation == "compliance":
        manifest["credibility_evidence"]["compliance_claim"] = True
    else:
        manifest["credibility_evidence"]["risk_informed_plan"]["risk_combination"][
            "value"
        ] = 99
    assert (
        check_generated_manifest(manifest, MemoryReader(texts), load_policy())["status"]
        == "FAIL"
    )


def repository_inventory():
    return json.loads(
        (
            ROOT / "Business/research/deliverable-generator/claim-inventory.json"
        ).read_text(encoding="utf-8")
    )


def public_repository_artifact(path):
    resolved = ROOT / path
    if resolved.is_symlink():
        raise ValueError("registered artifact must not be a symlink")
    return resolved.read_text(encoding="utf-8").encode("utf-8")


def test_registered_current_presentations_and_reference_tokens_are_consistent():
    inventory = repository_inventory()
    report = require_pass(check_inventory(inventory, public_repository_artifact))
    assert report["claims_examined"] == len(inventory["claims"])
    assert {"package", "guard", "trust-map", "credibility", "reference-note"} <= {
        r["surface"] for r in report["results"]
    }
    assert report["qualification_claim"] is False


def test_real_battery_route_version_change_invalidates_named_customer_note():
    inventory = repository_inventory()
    worker_path = "scripts/dev/battery/plating_rereference.py"
    changed = public_repository_artifact(worker_path).replace(
        b'VERSION = "battery-plating-ref-v2"', b'VERSION = "synthetic-future-reference"'
    )
    assert changed != public_repository_artifact(worker_path)
    next(a for a in inventory["artifacts"] if a["path"] == worker_path)["sha256"] = (
        sha256(changed)
    )
    # Even a rebound whole-file digest cannot preserve the old version claim.
    report = check_inventory(
        inventory,
        lambda path: (
            changed if path == worker_path else public_repository_artifact(path)
        ),
    )
    assert report["status"] == "FAIL"
    assert "reference-note" in str(report)
    assert "reference version superseded" in str(report)
    assert worker_path in str(report)


def test_known_obsolete_trust_map_header_is_rejected_against_actual_runtime():
    inventory = repository_inventory()
    claim = next(
        c for c in inventory["claims"] if c["id"] == "trust-map.disclosed-panel-version"
    )
    claim["reference"]["version"] = "carbon.trust-map.disclosed-panel.v1"
    report = check_inventory(inventory, public_repository_artifact)
    assert report["status"] == "FAIL"
    assert "trust-map.disclosed-panel-version" in str(report)
    assert "carbon/trust_map/core.py" in str(report)


@pytest.mark.parametrize(
    "name", ["sample.md", "sample.json", "deliverable.schema.json"]
)
def test_actual_customer_file_change_cannot_hide_behind_valid_manifest(name):
    texts = package_fixture_texts()
    outputs = render(CHALLENGE, "nasa-std-7009b", MemoryReader(texts), load_policy())
    manifest = json.loads(outputs["generation-manifest.json"])
    assert (
        check_package_outputs(manifest, outputs, MemoryReader(texts), load_policy())[
            "output_files_examined"
        ]
        == 3
    )
    outputs[name] += "\nUnsupported speedup claim: 100.\n"
    with pytest.raises(ValueError, match=name):
        check_package_outputs(manifest, outputs, MemoryReader(texts), load_policy())


@pytest.mark.parametrize(
    "mutation",
    [
        "fake_citation_commit",
        "wrong_citation_path",
        "source_header_revision",
        "nested_extra_number",
        "stored_qualification",
        "stored_count",
    ],
)
def test_citations_and_derived_report_cannot_smuggle_unsupported_claims(mutation):
    manifest, texts = snapshot()
    if mutation == "fake_citation_commit":
        manifest["facts"][0]["citation"] = manifest["facts"][0]["citation"].replace(
            "a" * 40, "c" * 40
        )
    elif mutation == "wrong_citation_path":
        manifest["sources"][0]["url"] += "/missing"
    elif mutation == "source_header_revision":
        manifest["evidence_revision"] = "c" * 40
    elif mutation == "nested_extra_number":
        manifest["credibility_evidence"]["risk_informed_plan"]["sources"] = 123
    elif mutation == "stored_qualification":
        manifest["claim_check"]["qualification_claim"] = True
    else:
        manifest["claim_check"]["claims_examined"] = 999
    # Rebinding the index does not establish actual citation/value integrity.
    manifest["claim_inventory"] = generated_claims(manifest)
    assert (
        check_generated_manifest(manifest, MemoryReader(texts), load_policy())["status"]
        == "FAIL"
    )


def test_actual_host_context_is_indexed_as_not_compared_not_verified():
    from tests.cpu.test_customer_deliverable_generator import CredibilityAutofillTests

    fixture = CredibilityAutofillTests()
    fixture.setUp()
    fixture.texts["P8"] = json.dumps(fixture.context())
    outputs = render(
        CHALLENGE, "nasa-std-7009b", MemoryReader(fixture.texts), fixture.policy
    )
    manifest = json.loads(outputs["generation-manifest.json"])
    host = [
        c for c in manifest["claim_inventory"] if c["id"].startswith("crosswalk.host.")
    ]
    assert host
    assert all(c["basis"] == "HOST_DECLARED_NOT_COMPARED" for c in host)
    report = require_pass(
        check_generated_manifest(manifest, MemoryReader(fixture.texts), fixture.policy)
    )
    assert all(
        r["requirement"] != "VERIFIED"
        for r in report["results"]
        if r["claim"].startswith("crosswalk.host.")
    )
    assert (
        manifest["credibility_evidence"]["risk_informed_plan"]["risk_combination"][
            "value"
        ]
        is None
    )
