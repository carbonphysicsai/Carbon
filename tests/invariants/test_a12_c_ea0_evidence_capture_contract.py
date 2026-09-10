from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "Design_Specs" / "evidence_capture_contract_v1.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_c_ea0_contract_has_five_independent_closed_status_axes() -> None:
    contract = _contract()
    axes = contract["status_axes"]

    assert isinstance(axes, dict)
    assert set(axes) == {
        "execution_disposition",
        "scientific_result",
        "evidence_completeness",
        "qualification_origin",
        "named_use_eligibility",
    }
    for name, values in axes.items():
        assert isinstance(name, str)
        assert isinstance(values, list)
        assert values
        assert len(values) == len(set(values))


def test_c_ea0_cases_cover_every_attempt_disposition_and_fail_closed() -> None:
    contract = _contract()
    axes = contract["status_axes"]
    cases = contract["contract_cases"]

    assert isinstance(axes, dict)
    assert isinstance(cases, list)
    assert {case["execution_disposition"] for case in cases} == set(
        axes["execution_disposition"]
    )
    assert {case["source_failure_class"] for case in cases} == set(
        contract["source_failure_classes"]
    )
    assert all(case["scientific_result"] in axes["scientific_result"] for case in cases)
    assert all(
        case["evidence_completeness"] in axes["evidence_completeness"] for case in cases
    )
    assert all(
        case["qualification_origin"] in axes["qualification_origin"] for case in cases
    )
    assert all(
        case["named_use_eligibility"] in axes["named_use_eligibility"] for case in cases
    )
    assert {
        "MISSING_REQUIRED_ARTIFACT",
        "WITHDRAWN_ARTIFACT",
        "KEY_UNAVAILABLE",
        "MISSING_APPROVED_DURABILITY_PROFILE",
    } <= {case["id"] for case in cases}
    assert not {
        "CANDIDATE_PHYSICS_FAILURE",
        "PHYSICS_FAILURE",
        "SCORE_ZERO",
    } & {case["expected_effect"] for case in cases}


def test_c_ea0_unknown_and_dependence_semantics_are_explicit() -> None:
    contract = _contract()

    assert "UNKNOWN" in contract["epistemic_values"]
    assert {"SHARED_CASE", "ANCESTRY", "UNKNOWN"} <= set(contract["dependence_kinds"])
    assert set(contract["named_uses"]) == {
        "INTERNAL_AUDIT",
        "LANDSCAPE_RESEARCH",
        "RELEASE_CANDIDATE",
        "EXTERNAL_RELEASE",
        "COMMERCIAL_USE",
    }
    cases = {case["id"]: case for case in contract["contract_cases"]}
    assert cases["UNKNOWN_SELECTION_AND_EXPOSURE"]["expected_effect"] == (
        "UNKNOWN_VALUES_PRESERVED_NOT_INFERRED"
    )
    assert cases["SHARED_CASE_AND_ANCESTRY"]["expected_effect"] == (
        "DEPENDENCE_LINKS_PRESERVED_NO_INDEPENDENCE_CLAIM"
    )


def test_c_ea0_acknowledgement_requires_verified_current_availability() -> None:
    contract = _contract()
    acknowledgement = contract["acknowledgement"]

    assert acknowledgement["scope"] == "DECLARED_APPROVED_PROFILE_ONLY"
    assert set(acknowledgement["blocks_finalization"]) == {
        "NOT_ACKNOWLEDGED",
        "PENDING",
        "REJECTED",
    }
    assert {
        "APPROVED_DURABILITY_PROFILE_REF",
        "CONDITIONALLY_REQUIRED_ARTIFACTS_VERIFIED",
        "MANIFEST_CONTENT_ID_VERIFIED",
        "CATALOGUE_COMMIT_VERIFIED",
        "CURRENT_OBJECT_AVAILABILITY_VERIFIED",
        "CUSTODY_POLICY_REF_VERIFIED",
    } <= set(acknowledgement["verified_requires"])


def test_c_ea0_reserves_human_decisions_and_disclaims_universal_losslessness() -> None:
    contract = _contract()

    assert contract["runtime_wire_schema"] is False
    assert contract["maturity"] == "SPECIFIED_ONLY"
    assert contract["reserved_decisions"]
    assert set(contract["reserved_decisions"].values()) == {"HUMAN_INPUT"}
    losslessness = contract["losslessness_boundary"]
    assert losslessness["universal_losslessness_claimed"] is False
    assert losslessness["correlated_failure_coverage"] == "HUMAN_INPUT"
    assert losslessness["restore_acceptance"] == "HUMAN_INPUT"
