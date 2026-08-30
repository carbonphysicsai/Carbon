"""POSIX acceptance coverage for B-02A history graphs at A3's LIVE seam."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from carbon.authoring.graph import (
    AuthoringGraphBinding,
    StatisticsDesignAuthorization,
    StatisticsDesignVerification,
    StatisticsDesignVerificationRequest,
    StoreBackedScientificAuthoringVerifier,
    TransientTimeComponent,
    TransientTimeComponentBinding,
    TransientTimeEquivalenceRequest,
    TransientTimeEquivalenceVerification,
    scientific_authoring_graph_fingerprint,
)
from carbon.authoring.history import AuthoringHistoryStore
from carbon.authoring.loading import (
    AuthoringOriginIssuer,
    FixtureAuthoringCapability,
    LoadedAuthoringArtifact,
    OriginTag,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import (
    ApplicabilityBinding,
    PopulationRole,
    TimeMode,
    validate_loaded_authoring_graph,
)
from carbon.authoring.physical import TimeContract, TimeHorizonBinding
from carbon.authoring.refs import GlobalScope, TopLevelObjectRef, owner_ref
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    LiveActivationError,
    QualificationEvidence,
    QualificationManifest,
    ScientificAuthoringGraphOrigin,
    ScientificAuthoringReason,
)
from tests.cpu import test_b02a_contract_models as domain_fixtures

pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="secure descriptor-relative history and registry I/O requires POSIX",
)

_KEY = ChallengeKey("fixture_authoring", "1.0")
_DEFAULT_OWNER_AUTHORITY = object()


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('utf-8')).hexdigest()}"


def _owner(kind: str, label: str) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope(),
        object_id=label,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{label}"),
    )


@dataclass(frozen=True, slots=True)
class _ExactOriginAuthority:
    principal_ref: object
    authority_evidence_refs: tuple[object, ...]
    source_provenance_refs: tuple[object, ...]

    def verify_authoring_origin(
        self,
        *,
        origin_tag: OriginTag,
        principal_ref: object,
        authority_evidence_refs: tuple[object, ...],
        source_provenance_refs: tuple[object, ...],
    ) -> bool:
        return (
            origin_tag is OriginTag.REGISTERED
            and principal_ref == self.principal_ref
            and authority_evidence_refs == self.authority_evidence_refs
            and source_provenance_refs == self.source_provenance_refs
        )


class _ExactGraphAuthority:
    def __init__(
        self,
        *,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        composition_audit_ref: object,
    ) -> None:
        self._root_ref = root_ref
        self._dependency_refs = dependency_refs
        self._origin_evidence_refs = frozenset(origin_evidence_refs)
        self._composition_audit_ref = composition_audit_ref
        self.calls = 0

    def verify_registered_graph(
        self,
        *,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        composition_audit_ref: object,
    ) -> bool:
        self.calls += 1
        return (
            root_ref == self._root_ref
            and dependency_refs == self._dependency_refs
            and len(origin_evidence_refs) == len(self._origin_evidence_refs)
            and frozenset(origin_evidence_refs) == self._origin_evidence_refs
            and composition_audit_ref == self._composition_audit_ref
        )


class _ExactStatisticsAuthority:
    def __init__(
        self,
        authorizations: dict[object, StatisticsDesignAuthorization],
        *,
        stale_request: StatisticsDesignVerificationRequest | None = None,
    ) -> None:
        self._authorizations = dict(authorizations)
        self._stale_request = stale_request
        self.calls = 0
        self.last_request: StatisticsDesignVerificationRequest | None = None

    def verify_statistics_design(
        self,
        request: StatisticsDesignVerificationRequest,
        /,
    ) -> StatisticsDesignVerification:
        self.calls += 1
        self.last_request = request
        try:
            authorization = self._authorizations[request.sampling_plan_ref]
        except KeyError as exc:
            raise ValueError("unregistered exact statistics design") from exc
        return StatisticsDesignVerification(
            request=self._stale_request or request,
            authorization=authorization,
        )


class _ExactSciMLAuthority:
    def __init__(
        self,
        component_ids: dict[object, tuple[str, str, str]],
        *,
        stale_request: TransientTimeEquivalenceRequest | None = None,
    ) -> None:
        self._component_ids = dict(component_ids)
        self._stale_request = stale_request
        self.calls = 0
        self.last_request: TransientTimeEquivalenceRequest | None = None

    def verify_transient_time_equivalence(
        self,
        request: TransientTimeEquivalenceRequest,
        /,
    ) -> TransientTimeEquivalenceVerification:
        self.calls += 1
        self.last_request = request
        echoed = self._stale_request or request
        try:
            candidate_ids = self._component_ids[request.candidate_output_ref]
        except KeyError as exc:
            raise ValueError("unregistered exact transient candidate") from exc
        fields = {item.field_id: item for item in echoed.candidate_input_contracts}
        binding = echoed.candidate_time_horizon_binding
        equivalence_refs = (
            binding.time_coordinate_equivalence_ref,
            binding.horizon_equivalence_ref,
            binding.endpoint_equivalence_ref,
        )
        return TransientTimeEquivalenceVerification(
            request=echoed,
            component_bindings=tuple(
                TransientTimeComponentBinding(
                    component=component,
                    candidate_field_id=field_id,
                    candidate_semantic_role_ref=fields[field_id].semantic_role_ref,
                    equivalence_ref=equivalence_ref,
                )
                for component, field_id, equivalence_ref in zip(
                    (
                        TransientTimeComponent.TIME_COORDINATE,
                        TransientTimeComponent.HORIZON,
                        TransientTimeComponent.ENDPOINT,
                    ),
                    candidate_ids,
                    equivalence_refs,
                    strict=True,
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class _GraphBundle:
    store: AuthoringHistoryStore
    binding: AuthoringGraphBinding
    verifier: StoreBackedScientificAuthoringVerifier
    fingerprint: str
    loaded: dict[TopLevelObjectRef, LoadedAuthoringArtifact]
    graph_authority: _ExactGraphAuthority
    statistics_authority: object | None
    sciml_authority: object | None


def _objects_for_pair(
    physical: object,
    candidate: object,
    *,
    include_weight: bool = True,
    estimand_label: str = "fixture_estimand",
) -> tuple[object, ...]:
    target = domain_fixtures._population(
        PopulationRole.TARGET_WORKLOAD_P,
        physical,
        candidate,
    )
    proposal = domain_fixtures._population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
    )
    weight = (
        domain_fixtures._population(
            PopulationRole.EVIDENCE_WEIGHT_W,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
            proposal_binding=ApplicabilityBinding.bound(proposal.to_ref()),
            estimand_ref=domain_fixtures._owner(
                "estimand_scope",
                estimand_label,
            ),
        )
        if include_weight
        else None
    )
    plan = domain_fixtures._fixed_sampling_plan(
        target,
        proposal,
        w=weight,
        estimand_ref=domain_fixtures._owner(
            "intended_estimand_or_reporting",
            estimand_label,
        ),
    )
    training_support = domain_fixtures._training_support(physical, candidate)
    objects = (
        physical,
        candidate,
        target,
        proposal,
        *((weight,) if weight is not None else ()),
        plan,
        training_support,
    )
    validate_loaded_authoring_graph({value.to_ref(): value for value in objects})
    return objects


def _base_objects() -> tuple[object, ...]:
    physical = domain_fixtures._physical()
    candidate = domain_fixtures._candidate(physical)
    return _objects_for_pair(physical, candidate)


def _transient_objects(
    *,
    component_count: int = 3,
) -> tuple[object, ...]:
    physical_time = replace(
        domain_fixtures._value("physical_time_coordinate"),
        unit_ref=domain_fixtures._owner("unit", "fixture_time_unit"),
    )
    physical = replace(
        domain_fixtures._physical(),
        object_id="transient_physical_job",
        time_contract=TimeContract(
            mode=TimeMode.TRANSIENT,
            time_coordinate_binding=ApplicabilityBinding.bound(physical_time),
            horizon_binding=ApplicabilityBinding.bound(
                domain_fixtures._owner(
                    "semantic_clause",
                    "transient_horizon",
                )
            ),
            endpoint_inclusion_semantic_ref=domain_fixtures._owner(
                "semantic_clause",
                "transient_endpoint",
            ),
            time_unit_ref=physical_time.unit_ref,
        ),
    )
    base_candidate = domain_fixtures._candidate(physical)
    time_fields = (
        replace(physical_time, field_id="candidate_time_coordinate"),
        replace(
            physical_time,
            field_id="candidate_horizon",
            semantic_role_ref=domain_fixtures._owner(
                "semantic_clause",
                "candidate_horizon_semantic",
            ),
        ),
        replace(
            physical_time,
            field_id="candidate_endpoint",
            semantic_role_ref=domain_fixtures._owner(
                "semantic_clause",
                "candidate_endpoint_semantic",
            ),
        ),
        replace(
            physical_time,
            field_id="candidate_unrelated_same_unit",
            semantic_role_ref=domain_fixtures._owner(
                "semantic_clause",
                "unrelated_same_unit_semantic",
            ),
        ),
    )[:component_count]
    candidate = replace(
        base_candidate,
        object_id=f"transient_candidate_{component_count}",
        candidate_inputs=(*base_candidate.candidate_inputs, *time_fields),
        time_horizon_binding=TimeHorizonBinding(
            candidate_field_ids=tuple(item.field_id for item in time_fields),
            time_coordinate_equivalence_ref=domain_fixtures._owner(
                "semantic_equivalence",
                "transient_coordinate_equivalence",
            ),
            horizon_equivalence_ref=domain_fixtures._owner(
                "semantic_equivalence",
                "transient_horizon_equivalence",
            ),
            endpoint_equivalence_ref=domain_fixtures._owner(
                "semantic_equivalence",
                "transient_endpoint_equivalence",
            ),
        ),
    )
    return _objects_for_pair(physical, candidate)


def _registered_origin() -> object:
    registration = _owner("authoring_registration", "integration_registration")
    authority_evidence = (_owner("authority_evidence", "integration_authority"),)
    provenance = (_owner("provenance", "integration_source"),)
    authority = _ExactOriginAuthority(
        registration,
        authority_evidence,
        provenance,
    )
    return AuthoringOriginIssuer(authority).issue_registered(
        registration_ref=registration,
        authority_evidence_refs=authority_evidence,
        source_provenance_refs=provenance,
    )


def _load_objects(
    objects: tuple[object, ...],
    *,
    fixture_refs: frozenset[TopLevelObjectRef],
) -> dict[TopLevelObjectRef, LoadedAuthoringArtifact]:
    registered_origin = _registered_origin()
    fixture_origin = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=_owner(
            "fixture_registration",
            "integration_fixture_registration",
        ),
        source_provenance_refs=(_owner("provenance", "integration_fixture_source"),),
    )
    loaded: dict[TopLevelObjectRef, LoadedAuthoringArtifact] = {}
    for index, value in enumerate(objects):
        ref = value.to_ref()
        is_fixture = ref in fixture_refs
        loaded[ref] = load_authoring_bytes(
            ref,
            value.canonical_bytes(),
            origin=fixture_origin if is_fixture else registered_origin,
            origin_evidence_ref=_owner(
                "authoring_origin_evidence",
                f"integration_node_{index}",
            ),
            source_provenance_refs=(
                _owner(
                    "provenance",
                    (
                        f"integration_fixture_node_{index}"
                        if is_fixture
                        else f"integration_registered_node_{index}"
                    ),
                ),
            ),
            audit_evidence_refs=(
                _owner("audit_evidence", f"integration_load_{index}"),
            ),
            qualification_evidence=(
                ApplicabilityBinding.not_applicable(
                    _owner(
                        "applicability_reason",
                        f"integration_fixture_unqualified_{index}",
                    )
                )
                if is_fixture
                else ApplicabilityBinding.bound(
                    _owner(
                        "qualification_evidence_bundle",
                        f"integration_qualification_{index}",
                    )
                )
            ),
        )
    return loaded


def _bundle(
    tmp_path: Path,
    *,
    objects: tuple[object, ...] | None = None,
    required_refs: tuple[TopLevelObjectRef, ...] | None = None,
    fixture_refs: frozenset[TopLevelObjectRef] = frozenset(),
    omitted_store_refs: frozenset[TopLevelObjectRef] = frozenset(),
    store: AuthoringHistoryStore | None = None,
    statistics_design_authority: object = _DEFAULT_OWNER_AUTHORITY,
    sciml_time_equivalence_authority: object = _DEFAULT_OWNER_AUTHORITY,
) -> _GraphBundle:
    authored = objects or _base_objects()
    loaded = _load_objects(authored, fixture_refs=fixture_refs)
    plan = next(value for value in authored if value.object_kind == "sampling_plan")
    root_ref = plan.to_ref()
    exact_required = required_refs or tuple(
        value.to_ref() for value in authored if value.to_ref() != root_ref
    )
    audit_ref = _owner(
        "origin_composition_audit",
        f"integration_graph_{len(exact_required)}",
    )
    binding = AuthoringGraphBinding(
        _KEY,
        root_ref,
        exact_required,
        audit_ref,
    )
    history = store or AuthoringHistoryStore(tmp_path / "authoring-history")
    for ref, artifact in loaded.items():
        if ref not in omitted_store_refs:
            history.put(artifact)

    graph_authority = _ExactGraphAuthority(
        root_ref=binding.root_ref,
        dependency_refs=binding.required_refs,
        origin_evidence_refs=tuple(
            loaded[ref].origin_evidence_ref
            for ref in (binding.root_ref, *binding.required_refs)
        ),
        composition_audit_ref=binding.composition_audit_ref,
    )
    graph = compose_authoring_graph_origin(
        root=loaded[binding.root_ref],
        dependencies=tuple(loaded[ref] for ref in binding.required_refs),
        expected_dependency_refs=binding.required_refs,
        composition_audit_ref=binding.composition_audit_ref,
        registered_authority=graph_authority,
    )
    fingerprint = scientific_authoring_graph_fingerprint(graph)
    if statistics_design_authority is _DEFAULT_OWNER_AUTHORITY:
        statistics_design_authority = _ExactStatisticsAuthority(
            {
                value.to_ref(): (
                    StatisticsDesignAuthorization.EXACT_W_ADMITTED
                    if value.evidence_weight_binding.is_bound
                    else StatisticsDesignAuthorization.NO_W_NONAGGREGATING_AUTHORIZED
                )
                for value in authored
                if value.object_kind == "sampling_plan"
            }
        )
    if sciml_time_equivalence_authority is _DEFAULT_OWNER_AUTHORITY:
        transient_candidates = tuple(
            value
            for value in authored
            if value.object_kind == "candidate_output_contract"
            and next(
                physical
                for physical in authored
                if physical.to_ref() == value.physical_system_ref
            ).time_contract.mode
            is TimeMode.TRANSIENT
        )
        sciml_time_equivalence_authority = (
            _ExactSciMLAuthority(
                {
                    value.to_ref(): tuple(
                        value.time_horizon_binding.candidate_field_ids[:3]
                    )
                    for value in transient_candidates
                }
            )
            if transient_candidates
            else None
        )
    verifier = StoreBackedScientificAuthoringVerifier(
        history,
        (binding,),
        registered_authority=graph_authority,
        statistics_design_authority=statistics_design_authority,
        sciml_time_equivalence_authority=sciml_time_equivalence_authority,
    )
    return _GraphBundle(
        history,
        binding,
        verifier,
        fingerprint,
        loaded,
        graph_authority,
        statistics_design_authority,
        sciml_time_equivalence_authority,
    )


def _a3_registry(
    tmp_path: Path,
    *,
    verifier: StoreBackedScientificAuthoringVerifier,
    fingerprint: str,
    complete_human_gates: bool,
    name: str,
) -> ChallengeRegistry:
    registry_root = tmp_path / f"registry-{name}"
    artifact_root = tmp_path / f"artifacts-{name}"
    artifact_root.mkdir()
    registry = ChallengeRegistry(
        registry_root,
        artifact_root,
        scientific_authoring_verifier=verifier,
    )
    artifact_id = "test_only_qualification_bundle"
    artifact_path = f"{_KEY.challenge_id}/{_KEY.version}/qualification.bin"
    artifact_bytes = (
        b"B-02A/A3 integration structure only; no human qualification authority\n"
    )
    target = artifact_root.joinpath(*artifact_path.split("/"))
    target.parent.mkdir(parents=True)
    target.write_bytes(artifact_bytes)
    slots = (
        {
            slot: QualificationEvidence(
                state=state,
                artifact_id=artifact_id,
                reference="test-only-structural-human-gate-fixture",
            )
            for slot, state in REQUIRED_QUALIFICATION_STATES
        }
        if complete_human_gates
        else {}
    )
    registry.save(
        ChallengeRecord(
            challenge_id=_KEY.challenge_id,
            version=_KEY.version,
            fixture_origin=False,
            allowed_backbones=("fno",),
            artifacts={
                artifact_id: ArtifactBinding(
                    path=artifact_path,
                    digest=f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}",
                )
            },
            qualification=QualificationManifest(
                challenge_id=_KEY.challenge_id,
                challenge_version=_KEY.version,
                mode="production",
                slots=slots,
                scientific_authoring_graph_fingerprint=fingerprint,
            ),
            scientific_authoring_graph_fingerprint=fingerprint,
        )
    )
    return registry


def _reason_codes(registry: ChallengeRegistry) -> tuple[str, ...]:
    assessment = registry.assess_live_eligibility(
        _KEY.challenge_id,
        _KEY.version,
    )
    return tuple(reason.code for reason in assessment.reasons)


def _assert_a3_graph_incomplete(
    tmp_path: Path,
    *,
    verifier: StoreBackedScientificAuthoringVerifier,
    fingerprint: str,
    name: str,
) -> None:
    registry = _a3_registry(
        tmp_path,
        verifier=verifier,
        fingerprint=fingerprint,
        complete_human_gates=True,
        name=name,
    )
    assert _reason_codes(registry) == (
        "scientific_authoring.graph_incomplete",
        "scientific_authoring.draft_or_unresolved",
    )


def test_real_registered_history_graph_satisfies_exact_a3_pin(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)

    structural = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert structural.eligible
    assert structural.complete
    assert not structural.revoked
    assert structural.graph_origin is ScientificAuthoringGraphOrigin.REGISTERED_GRAPH
    assert structural.graph_fingerprint == bundle.fingerprint

    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=True,
        name="positive",
    )
    assert registry.assess_live_eligibility(
        _KEY.challenge_id,
        _KEY.version,
    ).eligible
    assert registry.activate_live(_KEY.challenge_id, _KEY.version).status == "live"
    assert registry.is_effectively_live(_KEY.challenge_id, _KEY.version)
    assert bundle.graph_authority.calls >= 4


def test_exact_statistics_owner_authorizes_official_no_w_only_for_exact_plan(
    tmp_path: Path,
) -> None:
    physical = domain_fixtures._physical()
    candidate = domain_fixtures._candidate(physical)
    objects = _objects_for_pair(
        physical,
        candidate,
        include_weight=False,
        estimand_label="owner_verified_nonaggregating_use",
    )
    bundle = _bundle(tmp_path, objects=objects)

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert result.eligible
    assert isinstance(bundle.statistics_authority, _ExactStatisticsAuthority)
    assert bundle.statistics_authority.calls == 1
    request = bundle.statistics_authority.last_request
    assert request is not None
    plan = next(value for value in objects if value.object_kind == "sampling_plan")
    assert request.sampling_plan_ref == plan.to_ref()
    assert request.sampling_plan.full_design_law_ref == plan.full_design_law_ref
    assert (
        request.sampling_plan.intended_estimand_or_reporting_ref
        == plan.intended_estimand_or_reporting_ref
    )
    assert request.evidence_weight is None


def test_missing_or_raw_statistics_owner_fails_closed(
    tmp_path: Path,
) -> None:
    missing = _bundle(
        tmp_path / "missing",
        statistics_design_authority=None,
    )
    assert not missing.verifier.verify_scientific_authoring(
        _KEY,
        missing.fingerprint,
    ).eligible

    class RawBooleanStatisticsAuthority:
        def verify_statistics_design(self, request: object, /) -> bool:
            return True

    raw = _bundle(
        tmp_path / "raw",
        statistics_design_authority=RawBooleanStatisticsAuthority(),
    )
    assert not raw.verifier.verify_scientific_authoring(
        _KEY,
        raw.fingerprint,
    ).eligible


def test_statistics_result_for_same_role_other_plan_cannot_authorize_changed_design(
    tmp_path: Path,
) -> None:
    first_objects = _base_objects()
    first = _bundle(tmp_path / "first", objects=first_objects)
    assert first.verifier.verify_scientific_authoring(
        _KEY,
        first.fingerprint,
    ).eligible
    assert isinstance(first.statistics_authority, _ExactStatisticsAuthority)
    stale_request = first.statistics_authority.last_request
    assert stale_request is not None

    first_plan = next(
        value for value in first_objects if value.object_kind == "sampling_plan"
    )
    second_plan = replace(
        first_plan,
        full_design_law_ref=domain_fixtures._owner(
            "full_design_law",
            "changed_full_design",
        ),
        censoring_policy_ref=domain_fixtures._owner(
            "censoring_policy",
            "changed_censoring_policy",
        ),
    )
    second_objects = tuple(
        second_plan if value is first_plan else value for value in first_objects
    )
    stale_authority = _ExactStatisticsAuthority(
        {
            second_plan.to_ref(): StatisticsDesignAuthorization.EXACT_W_ADMITTED,
        },
        stale_request=stale_request,
    )
    second = _bundle(
        tmp_path / "second",
        objects=second_objects,
        statistics_design_authority=stale_authority,
    )

    result = second.verifier.verify_scientific_authoring(
        _KEY,
        second.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons


def test_official_aggregating_no_w_cannot_use_nonofficial_authorization(
    tmp_path: Path,
) -> None:
    physical = domain_fixtures._physical()
    candidate = domain_fixtures._candidate(physical)
    objects = _objects_for_pair(
        physical,
        candidate,
        include_weight=False,
        estimand_label="opaque_official_aggregate_score",
    )
    plan = next(value for value in objects if value.object_kind == "sampling_plan")
    authority = _ExactStatisticsAuthority(
        {
            plan.to_ref(): (
                StatisticsDesignAuthorization.NO_W_NONOFFICIAL_REPORTING_AUTHORIZED
            ),
        }
    )
    bundle = _bundle(
        tmp_path,
        objects=objects,
        statistics_design_authority=authority,
    )

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons


def test_exact_sciml_owner_verifies_three_distinct_transient_components(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, objects=_transient_objects())

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert result.eligible
    assert isinstance(bundle.sciml_authority, _ExactSciMLAuthority)
    assert bundle.sciml_authority.calls == 1
    request = bundle.sciml_authority.last_request
    assert request is not None
    assert request.physical_time_contract.mode is TimeMode.TRANSIENT
    assert len(request.candidate_time_horizon_binding.candidate_field_ids) == 3


def test_missing_or_raw_sciml_owner_fails_only_transient_graphs(
    tmp_path: Path,
) -> None:
    steady = _bundle(
        tmp_path / "steady",
        sciml_time_equivalence_authority=None,
    )
    assert steady.verifier.verify_scientific_authoring(
        _KEY,
        steady.fingerprint,
    ).eligible

    missing = _bundle(
        tmp_path / "missing",
        objects=_transient_objects(),
        sciml_time_equivalence_authority=None,
    )
    assert not missing.verifier.verify_scientific_authoring(
        _KEY,
        missing.fingerprint,
    ).eligible

    class RawMappingSciMLAuthority:
        def verify_transient_time_equivalence(
            self,
            request: object,
            /,
        ) -> dict[str, object]:
            return {"verified": True}

    raw = _bundle(
        tmp_path / "raw",
        objects=_transient_objects(),
        sciml_time_equivalence_authority=RawMappingSciMLAuthority(),
    )
    assert not raw.verifier.verify_scientific_authoring(
        _KEY,
        raw.fingerprint,
    ).eligible


@pytest.mark.parametrize("component_count", (2, 4))
def test_sciml_component_coverage_rejects_omitted_or_extra_same_unit_field(
    tmp_path: Path,
    component_count: int,
) -> None:
    bundle = _bundle(
        tmp_path,
        objects=_transient_objects(component_count=component_count),
    )

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons


def test_sciml_component_coverage_rejects_duplicate_candidate_assignment(
    tmp_path: Path,
) -> None:
    objects = _transient_objects()
    candidate = next(
        value for value in objects if value.object_kind == "candidate_output_contract"
    )
    coordinate, _, endpoint = candidate.time_horizon_binding.candidate_field_ids
    authority = _ExactSciMLAuthority(
        {
            candidate.to_ref(): (coordinate, coordinate, endpoint),
        }
    )
    bundle = _bundle(
        tmp_path,
        objects=objects,
        sciml_time_equivalence_authority=authority,
    )

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons


def test_sciml_result_for_another_candidate_binding_fails_closed(
    tmp_path: Path,
) -> None:
    first_objects = _transient_objects()
    first = _bundle(tmp_path / "first", objects=first_objects)
    assert first.verifier.verify_scientific_authoring(
        _KEY,
        first.fingerprint,
    ).eligible
    assert isinstance(first.sciml_authority, _ExactSciMLAuthority)
    stale_request = first.sciml_authority.last_request
    assert stale_request is not None

    physical = next(
        value for value in first_objects if value.object_kind == "physical_system_spec"
    )
    first_candidate = next(
        value
        for value in first_objects
        if value.object_kind == "candidate_output_contract"
    )
    second_candidate = replace(
        first_candidate,
        object_id="substituted_transient_candidate",
        time_horizon_binding=replace(
            first_candidate.time_horizon_binding,
            endpoint_equivalence_ref=domain_fixtures._owner(
                "semantic_equivalence",
                "substituted_endpoint_equivalence",
            ),
        ),
    )
    second_objects = _objects_for_pair(physical, second_candidate)
    authority = _ExactSciMLAuthority(
        {
            second_candidate.to_ref(): tuple(
                second_candidate.time_horizon_binding.candidate_field_ids
            ),
        },
        stale_request=stale_request,
    )
    second = _bundle(
        tmp_path / "second",
        objects=second_objects,
        sciml_time_equivalence_authority=authority,
    )

    result = second.verifier.verify_scientific_authoring(
        _KEY,
        second.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons


def test_omitted_reachable_dependency_fails_closed(tmp_path: Path) -> None:
    objects = _base_objects()
    plan = next(value for value in objects if value.object_kind == "sampling_plan")
    proposal_ref = plan.selection_population_ref
    required = tuple(
        value.to_ref()
        for value in objects
        if value.to_ref() not in {plan.to_ref(), proposal_ref}
    )
    bundle = _bundle(
        tmp_path,
        objects=objects,
        required_refs=required,
    )

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons
    _assert_a3_graph_incomplete(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        name="omitted-dependency",
    )


def test_disconnected_required_subgraph_fails_closed(tmp_path: Path) -> None:
    objects = _base_objects()
    detached_physical = replace(
        objects[0],
        object_id="detached_physical",
    )
    detached_candidate = replace(
        domain_fixtures._candidate(detached_physical),
        object_id="detached_candidate",
    )
    detached_training = replace(
        domain_fixtures._training_support(
            detached_physical,
            detached_candidate,
        ),
        object_id="detached_training_support",
    )
    disconnected = (*objects, detached_physical, detached_candidate, detached_training)
    bundle = _bundle(tmp_path, objects=disconnected)

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons
    _assert_a3_graph_incomplete(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        name="disconnected-subgraph",
    )


def test_extra_unrelated_manifest_node_fails_closed(tmp_path: Path) -> None:
    objects = _base_objects()
    unrelated = replace(objects[0], object_id="unrelated_physical")
    bundle = _bundle(tmp_path, objects=(*objects, unrelated))

    result = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons
    _assert_a3_graph_incomplete(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        name="unrelated-node",
    )


def test_cross_challenge_ref_is_rejected_before_provider(tmp_path: Path) -> None:
    objects = _base_objects()
    plan = next(value for value in objects if value.object_kind == "sampling_plan")
    other_physical = replace(
        objects[0],
        challenge_key=ChallengeKey("other_fixture_authoring", "1.0"),
        object_id="other_physical",
    )
    required = tuple(
        value.to_ref() for value in objects if value.to_ref() != plan.to_ref()
    )

    with pytest.raises(ValueError, match="exact Challenge key"):
        AuthoringGraphBinding(
            _KEY,
            plan.to_ref(),
            (*required, other_physical.to_ref()),
            _owner("origin_composition_audit", "cross_challenge"),
        )
    assert not (tmp_path / "authoring-history").exists()


def test_same_key_graph_swap_yields_exact_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    first = _bundle(tmp_path)
    alternate_objects = list(_base_objects())
    alternate_objects[-1] = replace(
        alternate_objects[-1],
        object_id="alternate_training_support",
    )
    second = _bundle(
        tmp_path,
        objects=tuple(alternate_objects),
        store=first.store,
    )
    assert first.fingerprint != second.fingerprint

    registry = _a3_registry(
        tmp_path,
        verifier=second.verifier,
        fingerprint=first.fingerprint,
        complete_human_gates=True,
        name="graph-swap",
    )
    assert _reason_codes(registry) == (
        "scientific_authoring.graph_fingerprint_provider_mismatch",
    )


def test_fixture_derived_graph_is_rejected_by_a3(tmp_path: Path) -> None:
    objects = _base_objects()
    fixture_ref = objects[-1].to_ref()
    bundle = _bundle(
        tmp_path,
        objects=objects,
        fixture_refs=frozenset((fixture_ref,)),
    )
    structural = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert structural.graph_origin is ScientificAuthoringGraphOrigin.FIXTURE_DERIVED
    assert structural.reasons == (ScientificAuthoringReason.GRAPH_FIXTURE_DERIVED,)

    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=True,
        name="fixture-graph",
    )
    assert _reason_codes(registry) == ("scientific_authoring.fixture_derived",)


def test_revoked_history_node_fails_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    revoked_ref = next(
        ref
        for ref in bundle.binding.required_refs
        if ref.object_kind == "instance_distribution_contract"
    )
    bundle.store.register_revocation(
        revoked_ref,
        _owner("authoring_revocation", "integration_revocation"),
    )

    structural = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not structural.eligible
    assert structural.revoked
    assert ScientificAuthoringReason.GRAPH_REVOKED in structural.reasons

    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=True,
        name="revoked",
    )
    assert _reason_codes(registry) == (
        "scientific_authoring.graph_fingerprint_provider_mismatch",
    )


def test_missing_store_node_fails_closed(tmp_path: Path) -> None:
    objects = _base_objects()
    missing_ref = objects[-1].to_ref()
    bundle = _bundle(
        tmp_path,
        objects=objects,
        omitted_store_refs=frozenset((missing_ref,)),
    )

    structural = bundle.verifier.verify_scientific_authoring(
        _KEY,
        bundle.fingerprint,
    )
    assert not structural.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in structural.reasons

    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=True,
        name="missing-store-node",
    )
    assert _reason_codes(registry) == (
        "scientific_authoring.graph_incomplete",
        "scientific_authoring.draft_or_unresolved",
    )


def test_unknown_store_ref_fails_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    training_ref = next(
        ref
        for ref in bundle.binding.required_refs
        if ref.object_kind == "training_support_contract"
    )
    unknown_ref = replace(
        training_ref,
        content_digest=_digest("unknown-training-support"),
    )
    required = tuple(
        unknown_ref if ref == training_ref else ref
        for ref in bundle.binding.required_refs
    )
    binding = AuthoringGraphBinding(
        _KEY,
        bundle.binding.root_ref,
        required,
        bundle.binding.composition_audit_ref,
    )
    verifier = StoreBackedScientificAuthoringVerifier(
        bundle.store,
        (binding,),
        registered_authority=bundle.graph_authority,
    )
    result = verifier.verify_scientific_authoring(
        _KEY,
        _digest("unknown-manifest-pin"),
    )
    assert not result.eligible
    assert ScientificAuthoringReason.GRAPH_INCOMPLETE in result.reasons
    _assert_a3_graph_incomplete(
        tmp_path,
        verifier=verifier,
        fingerprint=_digest("unknown-manifest-pin"),
        name="unknown-store-ref",
    )


def test_provider_exception_is_non_echoing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=True,
        name="provider-exception",
    )
    protected_detail = "protected-history-provider-detail"

    def explode(*_: object) -> object:
        raise RuntimeError(protected_detail)

    monkeypatch.setattr(
        StoreBackedScientificAuthoringVerifier,
        "verify_scientific_authoring",
        explode,
    )
    assessment = registry.assess_live_eligibility(
        _KEY.challenge_id,
        _KEY.version,
    )
    assert tuple(reason.code for reason in assessment.reasons) == (
        "scientific_authoring.verifier_failed",
    )
    assert protected_detail not in " ".join(
        reason.message for reason in assessment.reasons
    )


def test_valid_graph_cannot_bypass_human_qualification_gates(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    registry = _a3_registry(
        tmp_path,
        verifier=bundle.verifier,
        fingerprint=bundle.fingerprint,
        complete_human_gates=False,
        name="human-gates",
    )

    assessment = registry.assess_live_eligibility(
        _KEY.challenge_id,
        _KEY.version,
    )
    assert not assessment.eligible
    assert not any(
        reason.code.startswith("scientific_authoring.") for reason in assessment.reasons
    )
    assert tuple(reason.code for reason in assessment.reasons) == (
        "qualification.slot_missing",
    ) * len(REQUIRED_QUALIFICATION_STATES)
    assert not registry.can_go_live(_KEY.challenge_id, _KEY.version)
    with pytest.raises(LiveActivationError):
        registry.activate_live(_KEY.challenge_id, _KEY.version)
