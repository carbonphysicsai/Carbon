"""Adversarial regression coverage for exact-type, non-canonical B-04 carriers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.evaluation.assets import (
    ReferenceArtifact,
    create_fixture_reference_asset,
    create_reference_artifact,
    validate_reference_artifact,
)
from carbon.evaluation.comparison import create_reference_comparison_record
from carbon.evaluation.enums import (
    OptionalBindingTag,
    ReferenceFailureReason,
    ResolutionReason,
    UncertaintyComponentKind,
)
from carbon.evaluation.errors import ReferenceInputCode, ReferenceValidationError
from carbon.evaluation.execution import (
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    ReferenceRunRecord,
    create_reference_resolution_record,
)
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.model import (
    DependencyDisclosure,
    OptionalBinding,
    QualificationBinding,
    ReferenceAuthorityTarget,
    ReferenceAuthorityTargetBinding,
    ReferenceGrantBinding,
    ReferenceWitnessTarget,
    RunArtifactBinding,
)

_SECRET = "noncanonical-carrier-protected-secret"


def _pseudo(member):
    pseudo = str.__new__(type(member), member.value)
    object.__setattr__(pseudo, "_name_", member.name)
    object.__setattr__(pseudo, "_value_", _SECRET)
    assert pseudo is not member
    return pseudo


def _forged_role_binding() -> EvidenceRoleBinding:
    return EvidenceRoleBinding(_pseudo(EvidenceRole.NUMERICAL))


def _assert_closed(captured: pytest.ExceptionInfo[ReferenceValidationError]) -> None:
    assert type(captured.value) is ReferenceValidationError
    assert captured.value.code in tuple(item.value for item in ReferenceInputCode)
    assert _SECRET not in repr(captured.value)
    assert _SECRET not in str(captured.value)
    assert captured.value.__cause__ is None
    assert not isinstance(captured.value, AttributeError)


@pytest.mark.parametrize("record_name", ("entry", "grant", "run"))
def test_pseudo_evidence_role_is_rejected_by_policy_grant_and_run_construction(
    record_name: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    record = {
        "entry": graph.entries[0],
        "grant": graph.primary_grant,
        "run": graph.primary_run,
    }[record_name]

    with pytest.raises(ReferenceValidationError) as captured:
        replace(record, evidence_role_binding=_forged_role_binding())

    _assert_closed(captured)
    assert captured.value.path == "/evidence_role_binding"


@pytest.mark.parametrize(
    ("factory", "member"),
    (
        (
            ReferenceAuthorityTargetBinding.absent,
            ResolutionReason.POLICY_PRIMARY_MISSING,
        ),
        (ReferenceGrantBinding.absent, ResolutionReason.POLICY_PRIMARY_MISSING),
        (RunArtifactBinding.absent, ReferenceFailureReason.PROVIDER_RESULT_MALFORMED),
    ),
)
def test_pseudo_absence_reasons_cannot_enter_tagged_bindings(factory, member) -> None:
    with pytest.raises(ReferenceValidationError) as captured:
        factory(_pseudo(member))

    _assert_closed(captured)


def test_pseudo_uncertainty_component_kind_is_rejected() -> None:
    uncertainty = build_b04_fixture_reference_graph().primary_run.uncertainty_binding

    with pytest.raises(ReferenceValidationError) as captured:
        replace(
            uncertainty,
            component_kinds=(_pseudo(UncertaintyComponentKind.NUMERICAL),),
        )

    _assert_closed(captured)
    assert captured.value.path == "/component_kinds"


@pytest.mark.parametrize("target", ("policy", "run"))
def test_pseudo_optional_binding_tag_is_not_normalized_to_absence(target: str) -> None:
    graph = build_b04_fixture_reference_graph()
    malformed = object.__new__(OptionalBinding)
    object.__setattr__(malformed, "tag", _pseudo(OptionalBindingTag.ABSENT))
    object.__setattr__(malformed, "value", None)

    with pytest.raises(ReferenceValidationError) as captured:
        if target == "policy":
            replace(graph.policy, supersedes=malformed)
        else:
            replace(graph.primary_run, reason=malformed)

    _assert_closed(captured)


def _resolution_kwargs(graph) -> dict[str, object]:
    resolution = graph.primary_resolution
    return {
        "observed_reasons": (),
        "applicability_assessment": resolution.applicability_assessment,
        "authority_function": resolution.authority_function,
        "evidence_role_binding": resolution.evidence_role_binding,
        "qualification_binding": resolution.qualification_binding,
        "resolution_id": "b04_partial_carrier_resolution",
        "resolution_version": "1.0",
        "resolver_ref": resolution.resolver_ref,
        "resource_policy_ref": resolution.resource_policy_ref,
        "source_class": resolution.source_class,
        "policy": graph.policy,
        "entries": graph.entries,
        "compositions": graph.compositions,
        "precomputed_manifests": (graph.precomputed_manifest,),
    }


@pytest.mark.parametrize(
    ("request_carrier", "grant_carrier", "expected_path"),
    (
        (object.__new__(PrimaryReferenceRequest), None, "/request_binding"),
        (None, object.__new__(PrimaryRunGrant), "/grant_binding"),
    ),
)
def test_resolution_factory_normalizes_partial_request_and_grant_carriers(
    request_carrier: object | None,
    grant_carrier: object | None,
    expected_path: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    supplied_request = (
        graph.primary_request if request_carrier is None else request_carrier
    )
    supplied_grant = graph.primary_grant if grant_carrier is None else grant_carrier

    with pytest.raises(ReferenceValidationError) as captured:
        create_reference_resolution_record(
            request=supplied_request,
            grant=supplied_grant,
            **_resolution_kwargs(graph),
        )

    _assert_closed(captured)
    assert captured.value.path == expected_path


@pytest.mark.parametrize(
    ("operation", "expected_path"),
    (
        (
            lambda graph: create_reference_artifact(
                object.__new__(ReferenceRunRecord),
                artifact_id="b04_partial_run_artifact",
                artifact_version="1.0",
            ),
            "/run_ref",
        ),
        (
            lambda graph: validate_reference_artifact(
                object.__new__(ReferenceArtifact), graph.primary_run
            ),
            "/artifact_ref",
        ),
        (
            lambda graph: create_fixture_reference_asset(
                object.__new__(ReferenceArtifact),
                graph.primary_run,
                fixture_asset_id="b04_partial_artifact_asset",
                fixture_asset_version="1.0",
                fixture_provenance_ref=graph.primary_fixture_asset.fixture_provenance_ref,
                payload_bytes=b"",
            ),
            "/artifact_ref",
        ),
        (
            lambda graph: create_fixture_reference_asset(
                graph.primary_artifact,
                object.__new__(ReferenceRunRecord),
                fixture_asset_id="b04_partial_run_asset",
                fixture_asset_version="1.0",
                fixture_provenance_ref=graph.primary_fixture_asset.fixture_provenance_ref,
                payload_bytes=b"",
            ),
            "/run_ref",
        ),
    ),
)
def test_asset_factories_normalize_partial_run_and_artifact_carriers(
    operation,
    expected_path: str,
) -> None:
    graph = build_b04_fixture_reference_graph()

    with pytest.raises(ReferenceValidationError) as captured:
        operation(graph)

    _assert_closed(captured)
    assert captured.value.path == expected_path


def _comparison_kwargs(graph) -> dict[str, object]:
    comparison = graph.comparison
    return {
        "observed_reasons": (comparison.reason,),
        "applicability_evidence_refs": comparison.applicability_evidence_refs,
        "comparison_id": "b04_partial_carrier_comparison",
        "comparison_method_ref": comparison.comparison_method_ref,
        "comparison_policy_ref": comparison.comparison_policy_ref,
        "comparison_version": "1.0",
        "dependency_disclosures": comparison.dependency_disclosures,
        "evidence_refs": comparison.evidence_refs,
        "uncertainty_treatment_ref": comparison.uncertainty_treatment_ref,
        "witness_target": comparison.witness_target,
    }


@pytest.mark.parametrize(
    ("field", "partial", "expected_path"),
    (
        ("primary_run", object.__new__(ReferenceRunRecord), "/primary_run_ref"),
        ("witness_run", object.__new__(ReferenceRunRecord), "/witness_run_ref"),
        ("witness_target", object.__new__(ReferenceWitnessTarget), "/witness_target"),
        (
            "dependency_disclosures",
            (object.__new__(DependencyDisclosure),),
            "/dependency_disclosures/0",
        ),
    ),
)
def test_comparison_factory_normalizes_partial_run_target_and_disclosure_carriers(
    field: str,
    partial: object,
    expected_path: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    kwargs = _comparison_kwargs(graph)
    kwargs.update(
        primary_run=graph.primary_run,
        witness_run=graph.witness_path.run,
    )
    kwargs[field] = partial

    with pytest.raises(ReferenceValidationError) as captured:
        create_reference_comparison_record(**kwargs)

    _assert_closed(captured)
    assert captured.value.path == expected_path


def test_partial_authority_target_is_rejected_during_run_reconstruction() -> None:
    graph = build_b04_fixture_reference_graph()

    with pytest.raises(ReferenceValidationError) as captured:
        replace(
            graph.primary_run,
            answer_key_authority_target=object.__new__(ReferenceAuthorityTarget),
        )

    _assert_closed(captured)
    assert captured.value.path == "/answer_key_authority_target"


@pytest.mark.parametrize("record_name", ("grant", "run", "comparison"))
def test_partial_challenge_key_is_rejected_by_record_reconstruction(
    record_name: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    record = {
        "grant": graph.primary_grant,
        "run": graph.primary_run,
        "comparison": graph.comparison,
    }[record_name]
    partial = object.__new__(type(record.challenge_key))

    with pytest.raises(ReferenceValidationError) as captured:
        replace(record, challenge_key=partial)

    _assert_closed(captured)
    assert captured.value.path == "/challenge_key"


def test_partial_challenge_key_is_rejected_by_reference_constructor() -> None:
    ref = build_b04_fixture_reference_graph().policy.to_ref()
    partial = object.__new__(type(ref.challenge_key))

    with pytest.raises(ReferenceValidationError) as captured:
        type(ref)(
            partial,
            ref.content_digest,
            ref.schema_version,
            ref.canonicalization_profile,
        )

    _assert_closed(captured)
    assert captured.value.path == "/challenge_key"


@pytest.mark.parametrize("grant_name", ("primary_grant", "witness_grant"))
def test_partial_grant_execution_target_is_rejected_before_direct_member_checks(
    grant_name: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    grant = getattr(graph, grant_name)
    partial = object.__new__(type(grant.execution_target))

    with pytest.raises(ReferenceValidationError) as captured:
        replace(grant, execution_target=partial)

    _assert_closed(captured)
    assert captured.value.path == "/execution_target"


def test_partial_qualification_owner_ref_is_rejected() -> None:
    binding = (
        build_b04_fixture_reference_graph().primary_resolution.qualification_binding
    )
    assert binding.is_bound
    partial = object.__new__(type(binding.value))

    with pytest.raises(ReferenceValidationError) as captured:
        QualificationBinding.bound(partial)

    _assert_closed(captured)
    assert captured.value.path == "/qualification_binding"


def test_partial_dependency_evidence_ref_is_rejected() -> None:
    disclosure = build_b04_fixture_reference_graph().comparison.dependency_disclosures[
        0
    ]
    partial = object.__new__(type(disclosure.evidence_refs[0]))

    with pytest.raises(ReferenceValidationError) as captured:
        replace(disclosure, evidence_refs=(partial,))

    _assert_closed(captured)
    assert captured.value.path == "/dependency_disclosures/evidence_refs"
