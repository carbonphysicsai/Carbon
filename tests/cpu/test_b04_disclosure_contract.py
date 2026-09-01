"""Focused positive-disclosure and protected-data proofs for B-04."""

from __future__ import annotations

import pickle
from dataclasses import FrozenInstanceError, fields, replace
from weakref import WeakKeyDictionary

import pytest

import carbon.evaluation.disclosure as disclosure_module
from carbon.evaluation.disclosure import (
    PublicReferenceOutcomeProjection,
    PublicReferencePolicyProjection,
    ReferenceDisclosureAuthority,
    ReferenceDisclosureVerificationEcho,
    _issue_reference_disclosure_authority,
    create_public_reference_outcome_projection,
    create_public_reference_policy_projection,
)
from carbon.evaluation.enums import (
    ConditioningStatus,
    ReferenceAuthorityFunction,
    ReferenceAuthorityTargetKind,
    ReferenceCompositionKind,
    ReferenceFailureReason,
    ReferenceRunOutcome,
    ReferenceSourceClass,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from carbon.evaluation.errors import (
    ReferenceDisclosureCode,
    ReferenceDisclosureError,
)
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph

_POLICY_FIELDS = (
    "schema_version",
    "answer_key_target_kind",
    "composition_kind",
)
_OUTCOME_FIELDS = (
    "schema_version",
    "authority_function",
    "source_class",
    "outcome",
    "reason",
    "applicability_status",
    "conditioning_status",
    "uncertainty_status",
)
_FORBIDDEN_PUBLIC_FIELDS = frozenset(
    {
        "artifact_binding",
        "artifact_content_digest",
        "artifact_ref",
        "case_ref",
        "challenge_key",
        "comparison_refs",
        "configuration_ref",
        "dependency_disclosures",
        "diagnostics_ref",
        "disclosure_policy_ref",
        "environment_ref",
        "evidence_refs",
        "grant_ref",
        "hardware_ref",
        "implementation_ref",
        "method_ref",
        "policy_id",
        "policy_ref",
        "policy_version",
        "precision_ref",
        "provenance_binding",
        "representation_ref",
        "resource_receipt_ref",
        "run_id",
        "run_ref",
        "solution_bytes",
    }
)
_SECRET = "protected_reference_secret_must_not_escape"


class _PositiveDisclosureRegistry:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def verify_reference_disclosure(
        self, **bindings: object
    ) -> ReferenceDisclosureVerificationEcho:
        self.calls.append(dict(bindings))
        return ReferenceDisclosureVerificationEcho(**bindings)


class _RejectingDisclosureRegistry:
    def verify_reference_disclosure(self, **bindings: object) -> object:
        del bindings
        raise RuntimeError(_SECRET)


def _authority(graph: object) -> tuple[
    ReferenceDisclosureAuthority,
    _PositiveDisclosureRegistry,
]:
    registry = _PositiveDisclosureRegistry()
    authority = _issue_reference_disclosure_authority(
        disclosure_policy_ref=graph.policy.disclosure_policy_ref,
        authority=registry,
    )
    return authority, registry


def test_positive_factories_reconstruct_only_the_exact_categorical_allowlist() -> None:
    graph = build_b04_fixture_reference_graph()
    authority, registry = _authority(graph)

    policy = create_public_reference_policy_projection(
        graph.policy,
        disclosure_authority=authority,
    )
    outcome = create_public_reference_outcome_projection(
        graph.primary_run,
        grant=graph.primary_grant,
        disclosure_authority=authority,
    )

    assert type(policy) is PublicReferencePolicyProjection
    assert type(outcome) is PublicReferenceOutcomeProjection
    assert (
        policy.answer_key_target_kind
        is ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION
    )
    assert policy.composition_kind is ReferenceCompositionKind.REGISTERED_HYBRID_POLICY
    assert outcome.authority_function is ReferenceAuthorityFunction.PRIMARY
    assert outcome.source_class is ReferenceSourceClass.DIRECT_REGISTERED_SOURCE
    assert outcome.outcome is ReferenceRunOutcome.SUPPORTED
    assert outcome.reason is None
    assert (
        outcome.applicability_status
        is SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
    )
    assert (
        outcome.conditioning_status
        is ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
    )
    assert outcome.uncertainty_status is UncertaintyStatus.RESOLVED

    assert tuple(field.name for field in fields(policy)) == _POLICY_FIELDS
    assert tuple(field.name for field in fields(outcome)) == _OUTCOME_FIELDS
    assert _FORBIDDEN_PUBLIC_FIELDS.isdisjoint(_POLICY_FIELDS)
    assert _FORBIDDEN_PUBLIC_FIELDS.isdisjoint(_OUTCOME_FIELDS)
    assert tuple(call["projection_kind"].value for call in registry.calls) == (
        "POLICY",
        "OUTCOME",
    )
    assert registry.calls[0]["source_ref"] == graph.policy.to_ref()
    assert registry.calls[1]["source_ref"] == graph.primary_run.to_ref()


def test_projections_are_fresh_frozen_non_subclassable_and_safely_picklable() -> None:
    graph = build_b04_fixture_reference_graph()
    authority, _ = _authority(graph)
    first = create_public_reference_outcome_projection(
        graph.primary_run,
        grant=graph.primary_grant,
        disclosure_authority=authority,
    )
    second = create_public_reference_outcome_projection(
        graph.primary_run,
        grant=graph.primary_grant,
        disclosure_authority=authority,
    )
    policy = create_public_reference_policy_projection(
        graph.policy,
        disclosure_authority=authority,
    )

    assert first == second
    assert first is not second
    assert pickle.loads(pickle.dumps(first)) == first
    assert pickle.loads(pickle.dumps(policy)) == policy
    with pytest.raises(FrozenInstanceError):
        first.outcome = ReferenceRunOutcome.CANCELLED  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        policy.composition_kind = (  # type: ignore[misc]
            ReferenceCompositionKind.REGISTERED_HYBRID_POLICY
        )
    with pytest.raises(TypeError):

        class OutcomeSubclass(PublicReferenceOutcomeProjection):
            pass

    with pytest.raises(TypeError):

        class PolicySubclass(PublicReferencePolicyProjection):
            pass


@pytest.mark.parametrize(
    ("path_name", "expected_outcome", "expected_reason"),
    (
        (
            "conditioning_path",
            ReferenceRunOutcome.CONDITIONING_UNRESOLVED,
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
        ),
        (
            "numerical_path",
            ReferenceRunOutcome.NUMERICAL_FAILURE,
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
        ),
        (
            "malformed_path",
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
        ),
        (
            "infrastructure_path",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
        ),
    ),
)
def test_outcome_projection_preserves_typed_reference_terminal_categories(
    path_name: str,
    expected_outcome: ReferenceRunOutcome,
    expected_reason: ReferenceFailureReason,
) -> None:
    graph = build_b04_fixture_reference_graph()
    authority, _ = _authority(graph)
    path = getattr(graph, path_name)

    projection = create_public_reference_outcome_projection(
        path.run,
        grant=path.grant,
        disclosure_authority=authority,
    )

    assert projection.outcome is expected_outcome
    assert projection.reason is expected_reason
    rendered = repr((projection.outcome.value, projection.reason.value))
    assert all(
        forbidden not in rendered
        for forbidden in ("CANDIDATE", "SCORE", "RANK", "SETTLEMENT")
    )


def test_projection_repr_and_pickle_never_retain_protected_source_identity() -> None:
    graph = build_b04_fixture_reference_graph()
    authority, _ = _authority(graph)
    policy = create_public_reference_policy_projection(
        graph.policy,
        disclosure_authority=authority,
    )
    outcome = create_public_reference_outcome_projection(
        graph.primary_run,
        grant=graph.primary_grant,
        disclosure_authority=authority,
    )
    public_surface = b" ".join(
        (
            repr(policy).encode("ascii"),
            repr(outcome).encode("ascii"),
            pickle.dumps(policy),
            pickle.dumps(outcome),
        )
    )
    protected_tokens = (
        graph.policy.policy_id,
        graph.policy.to_ref().content_digest,
        graph.primary_run.run_id,
        graph.primary_run.to_ref().content_digest,
        graph.primary_run.case_ref.content_digest,
        graph.primary_grant.disclosure_policy_ref.object_id,
        graph.primary_run.configuration_ref.identity_id,
        graph.primary_run.provenance_binding.source_ref.identity_id,
    )
    assert all(
        token.encode("ascii") not in public_surface for token in protected_tokens
    )

    forged = object.__new__(PublicReferenceOutcomeProjection)
    object.__setattr__(forged, "schema_version", _SECRET)
    with pytest.raises(TypeError) as caught:
        pickle.dumps(forged)
    assert _SECRET not in repr(forged)
    assert _SECRET not in repr(caught.value)


def test_disclosure_capability_is_exact_frozen_redacted_and_nonserializable() -> None:
    graph = build_b04_fixture_reference_graph()
    authority, _ = _authority(graph)

    assert repr(authority) == "ReferenceDisclosureAuthority(<protected>)"
    assert graph.policy.disclosure_policy_ref.object_id not in repr(authority)
    with pytest.raises(FrozenInstanceError):
        authority.disclosure_policy_ref = None  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        authority._authority = object()  # type: ignore[misc]
    with pytest.raises(TypeError):
        pickle.dumps(authority)
    with pytest.raises(PermissionError):
        ReferenceDisclosureAuthority(
            _token=object(),
            disclosure_policy_ref=graph.policy.disclosure_policy_ref,
            authority=_PositiveDisclosureRegistry(),
        )


def test_object_setattr_cannot_replace_a_denying_disclosure_registry() -> None:
    graph = build_b04_fixture_reference_graph()
    authority = _issue_reference_disclosure_authority(
        disclosure_policy_ref=graph.policy.disclosure_policy_ref,
        authority=_RejectingDisclosureRegistry(),
    )

    def require_denial() -> None:
        with pytest.raises(ReferenceDisclosureError) as denied:
            create_public_reference_policy_projection(
                graph.policy,
                disclosure_authority=authority,
            )
        assert (
            denied.value.code == ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED.value
        )

    require_denial()
    with pytest.raises(AttributeError):
        object.__setattr__(authority, "_authority", _PositiveDisclosureRegistry())
    with pytest.raises(AttributeError):
        object.__setattr__(authority, "disclosure_policy_ref", None)
    with pytest.raises(AttributeError):
        object.__getattribute__(authority, "_authority")
    require_denial()

    exposed_copy = authority.disclosure_policy_ref
    object.__setattr__(
        exposed_copy,
        "object_id",
        "attacker_mutated_disclosure_policy",
    )
    assert (
        authority.disclosure_policy_ref.object_id
        == graph.policy.disclosure_policy_ref.object_id
    )


def test_module_mapping_replacement_cannot_replace_closure_owned_denial() -> None:
    graph = build_b04_fixture_reference_graph()
    authority = _issue_reference_disclosure_authority(
        disclosure_policy_ref=graph.policy.disclosure_policy_ref,
        authority=_RejectingDisclosureRegistry(),
    )
    module_state = vars(disclosure_module)
    forbidden_state_names = (
        "_DISCLOSURE_AUTHORITY_STATES",
        "_DISCLOSURE_AUTHORITY_STATES_LOCK",
        "_ReferenceDisclosureAuthorityState",
        "_build_disclosure_authority_state_operations",
    )
    assert all(name not in module_state for name in forbidden_state_names)
    assert not any(
        isinstance(value, WeakKeyDictionary) for value in module_state.values()
    )

    fake_allowing_state = {
        authority: (
            _PositiveDisclosureRegistry(),
            graph.policy.disclosure_policy_ref,
        )
    }
    module_state["_DISCLOSURE_AUTHORITY_STATES"] = fake_allowing_state
    try:
        with pytest.raises(ReferenceDisclosureError) as denied:
            create_public_reference_policy_projection(
                graph.policy,
                disclosure_authority=authority,
            )
        assert (
            denied.value.code == ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED.value
        )
        assert module_state["_DISCLOSURE_AUTHORITY_STATES"] is fake_allowing_state
    finally:
        del module_state["_DISCLOSURE_AUTHORITY_STATES"]
    assert all(name not in module_state for name in forbidden_state_names)
    assert not any(
        isinstance(value, WeakKeyDictionary) for value in module_state.values()
    )


def test_absent_wrong_or_rejecting_disclosure_authority_fails_closed() -> None:
    graph = build_b04_fixture_reference_graph()

    with pytest.raises(ReferenceDisclosureError) as absent_policy:
        create_public_reference_policy_projection(
            graph.policy,
            disclosure_authority=None,
        )
    assert (
        absent_policy.value.code
        == ReferenceDisclosureCode.DISCLOSURE_POLICY_REQUIRED.value
    )

    wrong_authority = _issue_reference_disclosure_authority(
        disclosure_policy_ref=replace(
            graph.policy.disclosure_policy_ref,
            object_id="b04_fixture_wrong_disclosure_policy",
        ),
        authority=_PositiveDisclosureRegistry(),
    )
    with pytest.raises(ReferenceDisclosureError) as wrong_policy:
        create_public_reference_policy_projection(
            graph.policy,
            disclosure_authority=wrong_authority,
        )
    assert (
        wrong_policy.value.code
        == ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED.value
    )

    rejecting = _issue_reference_disclosure_authority(
        disclosure_policy_ref=graph.policy.disclosure_policy_ref,
        authority=_RejectingDisclosureRegistry(),
    )
    with pytest.raises(ReferenceDisclosureError) as denied:
        create_public_reference_outcome_projection(
            graph.primary_run,
            grant=graph.primary_grant,
            disclosure_authority=rejecting,
        )
    denied_surface = repr(
        (str(denied.value), repr(denied.value), denied.value.__dict__)
    )
    assert denied.value.code == ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED.value
    assert denied.value.__cause__ is None
    assert denied.value.__suppress_context__ is True
    assert _SECRET not in denied_surface


def test_outcome_projection_requires_the_exact_nominal_bound_grant() -> None:
    graph = build_b04_fixture_reference_graph()
    authority, _ = _authority(graph)

    with pytest.raises(ReferenceDisclosureError) as wrong_grant:
        create_public_reference_outcome_projection(
            graph.primary_run,
            grant=graph.witness_grant,
            disclosure_authority=authority,
        )
    assert (
        wrong_grant.value.code == ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED.value
    )

    with pytest.raises(ReferenceDisclosureError) as hostile_source:
        create_public_reference_outcome_projection(
            _HostileSource(),
            grant=graph.primary_grant,
            disclosure_authority=authority,
        )
    hostile_surface = repr(
        (
            str(hostile_source.value),
            repr(hostile_source.value),
            hostile_source.value.__dict__,
        )
    )
    assert _SECRET not in hostile_surface


@pytest.mark.parametrize("source_kind", ("policy", "run"))
def test_malformed_exact_sources_raise_only_fixed_disclosure_errors(
    source_kind: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    if source_kind == "policy":
        malformed = object.__new__(type(graph.policy))
        with pytest.raises(ReferenceDisclosureError) as captured:
            create_public_reference_policy_projection(
                malformed,
                disclosure_authority=None,
            )
    else:
        malformed = object.__new__(type(graph.primary_run))
        with pytest.raises(ReferenceDisclosureError) as captured:
            create_public_reference_outcome_projection(
                malformed,
                grant=graph.primary_grant,
                disclosure_authority=None,
            )
    assert captured.value.code == ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED.value
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


class _HostileSource:
    def __repr__(self) -> str:
        return _SECRET

    __str__ = __repr__


def test_public_projection_constructors_are_factory_only_and_exact_typed() -> None:
    with pytest.raises(TypeError):
        PublicReferencePolicyProjection(
            schema_version="1.0",
            answer_key_target_kind=ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY,
            composition_kind=ReferenceCompositionKind.SINGLE_ENTRY,
            _token=object(),
        )
    with pytest.raises(TypeError):
        PublicReferenceOutcomeProjection(
            schema_version="1.0",
            authority_function=ReferenceAuthorityFunction.PRIMARY,
            source_class=ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
            outcome=ReferenceRunOutcome.SUPPORTED,
            reason=None,
            applicability_status=SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
            conditioning_status=ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
            uncertainty_status=UncertaintyStatus.RESOLVED,
            _token=object(),
        )
