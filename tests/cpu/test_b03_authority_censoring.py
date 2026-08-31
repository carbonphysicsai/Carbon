"""Focused authority identity and censoring-basis contract proof for B-03."""

from __future__ import annotations

import hashlib

import pytest

from carbon.authoring.evidence import (
    CensoringTrigger,
    CensoringTriggerKind,
    EvidenceScopeBinding,
    InfrastructureCensoringTrigger,
)
from carbon.authoring.model import (
    ApplicabilityBinding,
    CensoringReason,
    PopulationRole,
    SamplingRole,
)
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import (
    ChallengeScope,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.generators.authorities import (
    CensoringRecordBasis,
    IntendedUnitLinkDecision,
    IntendedUnitLinkRequest,
)
from carbon.generators.canonical import (
    decode_canonical_bytes,
    verify_canonical_ref,
)
from carbon.generators.errors import GeneratorInputCode, GeneratorValidationError
from carbon.generators.model import GenerationRoleBinding
from carbon.generators.refs import GeneratorReplayCommitmentRef
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import RoleKey, SeedDomain


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def _key() -> ChallengeKey:
    return ChallengeKey("b03_authority_fixture", "1.0")


def _owner(kind: str, object_id: str) -> object:
    key = _key()
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{object_id}"),
    )


def _na(object_id: str) -> ApplicabilityBinding[object]:
    return ApplicabilityBinding.not_applicable(
        _owner("applicability_reason", object_id)
    )


def _plan_ref() -> SamplingPlanRef:
    return SamplingPlanRef(
        _key(),
        "fixture_sampling_plan",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _digest("sampling_plan"),
    )


def _population_ref() -> InstanceDistributionContractRef:
    return InstanceDistributionContractRef(
        _key(),
        "fixture_primary_population",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _digest("primary_population"),
        PopulationRole.TARGET_WORKLOAD_P.value,
    )


def _role_binding() -> GenerationRoleBinding:
    return GenerationRoleBinding(
        SamplingRole.OFFICIAL_EVALUATION,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("generator_sampling"),
        _plan_ref(),
    )


def _replay_ref() -> GeneratorReplayCommitmentRef:
    return GeneratorReplayCommitmentRef(
        _key(),
        "carbon_generator_fixture_replay",
        "1.0",
        _owner("authority_evidence", "reservation_issuer"),
        _digest("replay_commitment"),
    )


def _scope() -> EvidenceScopeBinding:
    return EvidenceScopeBinding(
        evidence_campaign_binding=_na("campaign_not_applicable"),
        query_population_binding=_na("query_not_applicable"),
        observation_population_binding=_na("observation_not_applicable"),
        intended_estimand_or_reporting_ref=_owner(
            "intended_estimand_or_reporting",
            "fixture_reporting",
        ),
        measurement_applicability_binding=_na("measurement_not_applicable"),
    )


def test_intended_unit_link_decision_canonical_round_trip_and_ref() -> None:
    request = IntendedUnitLinkRequest(
        challenge_key=_key(),
        sampling_plan_ref=_plan_ref(),
        selection_population_ref=InstanceDistributionContractRef(
            _key(),
            "fixture_selection_population",
            "1.0",
            "1.0",
            CANONICALIZATION_PROFILE,
            _digest("selection_population"),
            PopulationRole.OFFICIAL_PROPOSAL_Q.value,
        ),
        role_binding=_role_binding(),
        replay_ref=_replay_ref(),
        intended_slot_ref=_owner("protected_intended_slot", "slot_1"),
        intended_evidence_unit_ref=_owner(
            "protected_intended_evidence_unit",
            "unit_1",
        ),
        attempt_ref=_owner("protected_attempt_commitment", "attempt_1"),
    )
    decision = IntendedUnitLinkDecision(
        challenge_key=_key(),
        request=request,
        link_evidence_ref=_owner("authority_evidence", "link_evidence"),
    )

    decoded = decode_canonical_bytes(
        decision.canonical_bytes(),
        IntendedUnitLinkDecision,
    )

    assert decoded == decision
    assert repr(decision) == "IntendedUnitLinkDecision(<protected>)"
    verify_canonical_ref(decision, decision.to_ref())

    for value in (request, decision):

        class ClonedSubclass(type(value)):
            pass

        with pytest.raises(GeneratorValidationError) as rejected:
            ClonedSubclass(
                **{
                    field_name: getattr(value, field_name)
                    for field_name in value.__dataclass_fields__
                }
            )
        assert rejected.value.code == GeneratorInputCode.WRONG_TYPE.value


def test_censoring_basis_is_closed_to_b03_v1_cause_families() -> None:
    basis = CensoringRecordBasis(
        intended_evidence_unit_ref=_owner(
            "protected_intended_evidence_unit",
            "unit_1",
        ),
        evidence_scope=_scope(),
        censoring_reason=(CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER),
        trigger_failure_binding=CensoringTrigger(
            CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE,
            InfrastructureCensoringTrigger(
                _owner(
                    "evidence_acquisition_operation",
                    "fixture_acquisition",
                ),
                _owner("infrastructure_failure", "fixture_failure"),
            ),
        ),
        actor_authority_ref=_owner(
            "censoring_authority",
            "fixture_censoring_authority",
        ),
        population_ref=_population_ref(),
        sampling_plan_ref=_plan_ref(),
        evidence_campaign_binding=_scope().evidence_campaign_binding,
        query_observation_provenance=(),
        accounting_binding=_owner(
            "censoring_accounting",
            "fixture_accounting",
        ),
        missingness_adjustment_binding=_na("missingness_not_applicable"),
        audit_evidence_refs=(_owner("audit_evidence", "censoring_audit"),),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
    )

    assert repr(basis) == "CensoringRecordBasis(<protected>)"
    with pytest.raises(GeneratorValidationError) as caught:
        CensoringRecordBasis(
            **{
                name: getattr(basis, name)
                for name in basis.__dataclass_fields__
                if name != "censoring_reason"
            },
            censoring_reason=CensoringReason.OBSERVATION_MISSING,
        )
    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
