"""Closed resource-only receipt and reconstruction-seam model tests for B-02C."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest

from carbon.authoring.refs import ChallengeScope, GlobalScope, owner_ref
from carbon.construction.model import EnvironmentPin
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    ResolvedConstructionPlanRef,
)
from carbon.registry import ChallengeKey
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    BoundReconstructionReplicate,
    CompleteBuild,
    CompleteBuildIdentity,
    DeclaredResourceEvidenceStage,
    FixturePracticeResourceContext,
    FrozenArtifactReuseWindow,
    IncompleteBuild,
    IncompleteBuildIdentity,
    IncompleteReconstructionReplicate,
    IncompleteReconstructionReplicateIdentity,
    NoBuildStarted,
    NoEnforcementEvent,
    NoResourceStop,
    NoReuse,
    ObservationUnavailableReason,
    ObservedMetricObserved,
    ObservedMetricUnavailable,
    ObservedResourceQuantity,
    ObservedResourceReceipt,
    ReconstructionReplicateIdentity,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResourceEpistemicLayer,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    ResourceStopCause,
)
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    FixtureResourceDecisionRef,
    ResearchResourcePolicyRef,
    ResourceCancellationRecordRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
)

_KEY = ChallengeKey("fixture_receipt", "1.0")
_OTHER_KEY = ChallengeKey("other_fixture_receipt", "1.0")
_DIGEST = "sha256:" + "5" * 64


def _field_names(value_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(value_type))


def _owner(kind: str, object_id: str, *, portable: bool = False) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope() if portable else ChallengeScope(_KEY),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _plan_ref(*, key: ChallengeKey = _KEY) -> ResolvedConstructionPlanRef:
    return ResolvedConstructionPlanRef(
        key,
        CONSTRUCTION_SCHEMA_VERSION,
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _policy_ref(*, key: ChallengeKey = _KEY) -> ResearchResourcePolicyRef:
    return ResearchResourcePolicyRef(
        key,
        "fixture_resource_policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _class_ref(*, key: ChallengeKey = _KEY) -> ResourceClassRef:
    return ResourceClassRef(
        key,
        "fixture_resource_class",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _resolved_ref(ref_type: type, *, key: ChallengeKey = _KEY) -> object:
    return ref_type(
        key,
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _context() -> FixturePracticeResourceContext:
    return FixturePracticeResourceContext(
        _KEY,
        "fixture_practice",
        _owner("fixture_registration", "resource_fixture"),
        _owner("internal_service_scope", "resource_practice_scope"),
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )


def _environment() -> EnvironmentPin:
    return EnvironmentPin("fixture_resource_environment", "1.0", _DIGEST)


def _complete_identity(*, key: ChallengeKey = _KEY) -> CompleteBuildIdentity:
    return CompleteBuildIdentity(
        key,
        _plan_ref(key=key),
        _policy_ref(key=key),
        _class_ref(key=key),
        _environment(),
        "fixture_build_attempt",
        _DIGEST,
    )


def _incomplete_identity() -> IncompleteBuildIdentity:
    return IncompleteBuildIdentity(
        _KEY,
        _plan_ref(),
        _policy_ref(),
        _class_ref(),
        _environment(),
        "fixture_build_attempt",
        _DIGEST,
    )


def _quantity(
    metric_id: str,
    quantity: int,
    role: ResourceObservationRole,
) -> ObservedResourceQuantity:
    return ObservedResourceQuantity(
        metric_id,
        _owner("unit", "resource_count", portable=True),
        quantity,
        role,
    )


def _receipt(**overrides: object) -> ObservedResourceReceipt:
    values: dict[str, object] = {
        "object_kind": "observed_resource_receipt",
        "schema_version": RESOURCE_POLICY_SCHEMA_VERSION,
        "canonicalization_profile": RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "challenge_key": _KEY,
        "policy_ref": _policy_ref(),
        "resource_class_ref": _class_ref(),
        "construction_plan_ref": _plan_ref(),
        "assessment_ref": _resolved_ref(StaticResourceAssessmentRef),
        "fixture_decision_ref": _resolved_ref(FixtureResourceDecisionRef),
        "authority_context": _context(),
        "build_completion": NoBuildStarted(),
        "frozen_artifact_reuse": NoReuse(),
        "reconstruction_replicate": ReplicateNotApplicable(
            ReplicateNotApplicableReason.NO_WORK_STARTED
        ),
        "observed_consumption_quantities": (),
        "observed_latency": ObservedMetricUnavailable(
            ObservationUnavailableReason.NO_WORK_STARTED
        ),
        "observed_cost": ObservedMetricUnavailable(
            ObservationUnavailableReason.NO_WORK_STARTED
        ),
        "evidence_stage_label": DeclaredResourceEvidenceStage.NO_WORK_STARTED,
        "stop_cause": ResourceStopCause.EVIDENCE_DEFERRED,
        "stop_record_binding": NoResourceStop(),
        "enforcement_event_binding": NoEnforcementEvent(),
        "work_started": False,
        "epistemic_layer": ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT,
        "authority_marker": (
            ResourcePolicyAuthorityMarker.RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE
        ),
    }
    values.update(overrides)
    return ObservedResourceReceipt(**values)  # type: ignore[arg-type]


def _complete_receipt(**overrides: object) -> ObservedResourceReceipt:
    identity = _complete_identity()
    values: dict[str, object] = {
        "build_completion": CompleteBuild(identity),
        "reconstruction_replicate": ReplicateNotApplicable(
            ReplicateNotApplicableReason.NOT_A_RECONSTRUCTION_REPLICATE
        ),
        "observed_consumption_quantities": (
            _quantity(
                "consumed_units",
                13,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
        ),
        "observed_latency": ObservedMetricObserved(
            _quantity(
                "latency_units",
                3,
                ResourceObservationRole.OBSERVED_LATENCY,
            )
        ),
        "observed_cost": ObservedMetricObserved(
            _quantity(
                "cost_units_not_price",
                7,
                ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
            )
        ),
        "evidence_stage_label": DeclaredResourceEvidenceStage.DECLARED_BUILD_ACCOUNTING,
        "stop_cause": ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
        "work_started": True,
    }
    values.update(overrides)
    return _receipt(**values)


def test_receipt_and_reconstruction_field_inventories_are_exact() -> None:
    common_identity = (
        "challenge_key",
        "construction_plan_ref",
        "policy_ref",
        "resource_class_ref",
    )
    assert _field_names(IncompleteBuildIdentity) == (
        *common_identity,
        "execution_environment_pin",
        "build_attempt_id",
        "build_attempt_digest",
    )
    assert _field_names(CompleteBuildIdentity) == (
        *common_identity,
        "execution_environment_pin",
        "build_attempt_id",
        "complete_build_digest",
    )
    assert _field_names(NoBuildStarted) == ()
    assert _field_names(IncompleteBuild) == ("build_identity",)
    assert _field_names(CompleteBuild) == ("build_identity",)
    assert _field_names(NoReuse) == ()
    assert _field_names(FrozenArtifactReuseWindow) == (
        "window_id",
        "complete_build_identity",
        "reuse_policy_ref",
        "maximum_declared_uses",
        "observed_use_ordinal",
    )
    assert _field_names(ReconstructionReplicateIdentity) == (
        *common_identity,
        "replicate_id",
        "replicate_digest",
    )
    assert _field_names(IncompleteReconstructionReplicateIdentity) == (
        *common_identity,
        "replicate_attempt_id",
        "replicate_attempt_digest",
    )
    assert _field_names(ReplicateNotApplicable) == ("reason",)
    assert _field_names(IncompleteReconstructionReplicate) == ("replicate_identity",)
    assert _field_names(BoundReconstructionReplicate) == ("replicate_identity",)
    assert _field_names(NoResourceStop) == ()
    assert _field_names(ObservedResourceReceipt) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "construction_plan_ref",
        "assessment_ref",
        "fixture_decision_ref",
        "authority_context",
        "build_completion",
        "frozen_artifact_reuse",
        "reconstruction_replicate",
        "observed_consumption_quantities",
        "observed_latency",
        "observed_cost",
        "evidence_stage_label",
        "stop_cause",
        "stop_record_binding",
        "enforcement_event_binding",
        "work_started",
        "epistemic_layer",
        "authority_marker",
    )


def test_unstarted_receipt_is_exact_non_scientific_resource_deferral() -> None:
    receipt = _receipt()

    assert receipt.work_started is False
    assert type(receipt.build_completion) is NoBuildStarted
    assert receipt.stop_cause is ResourceStopCause.EVIDENCE_DEFERRED
    assert receipt.epistemic_layer is ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT
    assert receipt.authority_marker is (
        ResourcePolicyAuthorityMarker.RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE
    )
    with pytest.raises(FrozenInstanceError):
        receipt.work_started = True  # type: ignore[misc]


def test_unstarted_law_is_if_and_only_if_and_rejects_truthiness_confusion() -> None:
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(work_started=True)
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(work_started=0)
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(build_completion=IncompleteBuild(_incomplete_identity()))
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.OBSERVATION_FAILED
            )
        )


def test_complete_receipt_requires_observed_resource_facts_not_price_or_science() -> (
    None
):
    receipt = _complete_receipt()

    assert type(receipt.build_completion) is CompleteBuild
    assert receipt.stop_cause is ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING
    assert not hasattr(receipt, "price")
    assert not hasattr(receipt, "score")
    assert not hasattr(receipt, "scientific_outcome")

    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(observed_consumption_quantities=())
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.OBSERVATION_FAILED
            )
        )
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            epistemic_layer=ResourceEpistemicLayer.STATIC_CONSTRUCTION_REQUIREMENT
        )


@pytest.mark.parametrize(
    ("maximum", "ordinal"),
    (
        (0, 1),
        (1, 0),
        (1, 2),
        (True, 1),
        (1, True),
        (1.0, 1),
        (1, float("inf")),
        (1 << 64, 1),
    ),
)
def test_reuse_window_bounds_reject_zero_bool_float_nonfinite_and_overflow(
    maximum: object,
    ordinal: object,
) -> None:
    with pytest.raises(ResourcePolicyInputRejected):
        FrozenArtifactReuseWindow(
            "fixture_reuse_window",
            _complete_identity(),
            _owner("restriction", "fixture_reuse_policy"),
            maximum,  # type: ignore[arg-type]
            ordinal,  # type: ignore[arg-type]
        )


def test_reuse_requires_exact_complete_identity_and_matching_challenge_scope() -> None:
    identity = _complete_identity()
    reuse = FrozenArtifactReuseWindow(
        "fixture_reuse_window",
        identity,
        _owner("restriction", "fixture_reuse_policy"),
        2,
        1,
    )
    receipt = _complete_receipt(frozen_artifact_reuse=reuse)

    assert receipt.frozen_artifact_reuse.complete_build_identity == identity
    with pytest.raises(ResourcePolicyInputRejected):
        FrozenArtifactReuseWindow(
            "fixture_reuse_window",
            _complete_identity(key=_OTHER_KEY),
            _owner("restriction", "fixture_reuse_policy"),
            2,
            1,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            frozen_artifact_reuse=replace(
                reuse,
                complete_build_identity=replace(
                    identity,
                    build_attempt_id="different_build_attempt",
                ),
            )
        )


def test_replicate_binding_is_required_exactly_for_replicate_stages() -> None:
    complete_identity = ReconstructionReplicateIdentity(
        _KEY,
        _plan_ref(),
        _policy_ref(),
        _class_ref(),
        "fixture_replicate",
        _DIGEST,
    )
    receipt = _complete_receipt(
        reconstruction_replicate=BoundReconstructionReplicate(complete_identity),
        evidence_stage_label=(
            DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING
        ),
    )

    assert type(receipt.reconstruction_replicate) is BoundReconstructionReplicate
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            evidence_stage_label=(
                DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING
            )
        )
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            reconstruction_replicate=BoundReconstructionReplicate(complete_identity)
        )

    incomplete_identity = IncompleteReconstructionReplicateIdentity(
        _KEY,
        _plan_ref(),
        _policy_ref(),
        _class_ref(),
        "fixture_replicate_attempt",
        _DIGEST,
    )
    incomplete = IncompleteReconstructionReplicate(incomplete_identity)
    with pytest.raises(ResourcePolicyInputRejected):
        _complete_receipt(
            reconstruction_replicate=incomplete,
            evidence_stage_label=(
                DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING
            ),
        )

    stopped = _complete_receipt(
        build_completion=IncompleteBuild(_incomplete_identity()),
        reconstruction_replicate=incomplete,
        evidence_stage_label=(
            DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING
        ),
        stop_cause=ResourceStopCause.CANCELLED,
        stop_record_binding=_resolved_ref(ResourceCancellationRecordRef),
    )
    assert type(stopped.reconstruction_replicate) is (IncompleteReconstructionReplicate)
    with pytest.raises(ResourcePolicyInputRejected):
        replace(
            stopped,
            reconstruction_replicate=BoundReconstructionReplicate(complete_identity),
        )
