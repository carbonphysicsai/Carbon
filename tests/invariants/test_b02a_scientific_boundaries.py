"""Constitutional separation invariants for B-02A authoring types."""

from __future__ import annotations

import inspect

import pytest

from carbon.authoring import training_support
from carbon.authoring.cases import (
    CanonicalChallengeCase,
    InternalCaseIdentityProjection,
    ProtectedCaseIdentityProjection,
    PublicCaseIdentityProjection,
)
from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.evidence import RealizedValidEvidenceRecord
from carbon.authoring.model import (
    CaseState,
    CensoringReason,
    EvidenceRole,
    PopulationRole,
    SamplingRole,
)
from carbon.authoring.physical import AxisExtent, AxisExtentKind


@pytest.mark.invariant
def test_population_vocabulary_cannot_accept_training_support_or_r_strategy() -> None:
    values = {role.value for role in PopulationRole}
    assert "TRAINING_SUPPORT" not in values
    assert "R_strategy" not in values
    assert "RESOLVED_TRAINING_SAMPLING_POLICY" not in values


@pytest.mark.invariant
def test_b02a_defines_no_b02b_resolved_training_policy() -> None:
    names = set(dir(training_support))
    assert "ResolvedTrainingSamplingPolicy" not in names
    assert "TrainingSamplingPolicyRef" not in names
    assert "R_strategy" not in names


@pytest.mark.invariant
def test_sampling_roles_do_not_alias_population_roles() -> None:
    assert SamplingRole.OFFICIAL_EVALUATION.value not in {
        role.value for role in PopulationRole
    }
    assert PopulationRole.DEPLOYMENT.value not in {role.value for role in SamplingRole}


@pytest.mark.invariant
def test_candidate_and_generator_failures_are_not_censoring_reasons() -> None:
    reasons = {reason.value for reason in CensoringReason}
    assert "CANDIDATE_FAILURE" not in reasons
    assert "CANDIDATE_TIMEOUT" not in reasons
    assert "GENERATOR_FAILURE" not in reasons
    assert "SCIENTIFIC_EXCLUSION" not in reasons


@pytest.mark.invariant
def test_case_states_keep_exclusion_censoring_and_generation_failure_distinct() -> None:
    assert {state.value for state in CaseState} == {
        "VALID",
        "CENSORED",
        "EXCLUDED",
        "GENERATION_FAILURE",
    }


@pytest.mark.invariant
def test_mms_has_only_verification_role_not_live_or_target_authority() -> None:
    values = {role.value for role in EvidenceRole}
    assert "MANUFACTURED_SOLUTION_VERIFICATION" in values
    assert "TARGET_WORKLOAD_P" not in values
    assert "PHYSICAL_MODEL_VALIDATION" not in values
    assert "LIVE_EXAM" not in values


@pytest.mark.invariant
def test_public_case_projection_schema_has_no_raw_or_reversible_identity_fields() -> (
    None
):
    public_fields = set(PublicCaseIdentityProjection.__dataclass_fields__)
    forbidden = {
        "case_ref",
        "content_digest",
        "payload_ref",
        "intended_slot_ref",
        "seed",
        "entropy",
        "realized_stratum_binding",
        "replacement_linkage",
    }
    assert not public_fields & forbidden
    assert "case_ref" in InternalCaseIdentityProjection.__dataclass_fields__
    assert "case_ref" in ProtectedCaseIdentityProjection.__dataclass_fields__
    assert CanonicalChallengeCase.__dataclass_params__.frozen is True


@pytest.mark.invariant
def test_realized_evidence_cannot_be_caller_constructed() -> None:
    signature = inspect.signature(RealizedValidEvidenceRecord)
    assert "_capability" in signature.parameters
    with pytest.raises(PermissionError):
        RealizedValidEvidenceRecord(_capability=object())


@pytest.mark.invariant
def test_bool_cannot_enter_positive_integer_extent() -> None:
    with pytest.raises(AuthoringValidationError):
        AxisExtent(AxisExtentKind.FIXED, fixed_extent=True)
