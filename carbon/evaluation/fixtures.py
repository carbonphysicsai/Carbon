"""Deterministic fixture-only reference graph and nominal runners for B-04.

The graph below is conspicuous test material.  It performs no scientific
calculation, provider discovery, I/O, retry, or fallback.  Its fixed records
exist only to exercise the protected B-04 contracts.
"""

from __future__ import annotations

import threading
from dataclasses import FrozenInstanceError, dataclass
from types import MappingProxyType
from weakref import WeakKeyDictionary

from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.registry.model import ChallengeKey

from .assets import (
    FixtureReferenceAsset,
    ReferenceArtifact,
    create_fixture_reference_asset,
    create_reference_artifact,
)
from .comparison import ReferenceComparisonRecord, create_reference_comparison_record
from .enums import (
    ConditioningStatus,
    DependencyCategory,
    DependencyRelation,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceComparisonReason,
    ReferenceCompositionKind,
    ReferenceFailureReason,
    ReferenceIdentityKind,
    ReferenceSourceClass,
    ResolutionOutcome,
    SupportApplicabilityStatus,
    UncertaintyComponentKind,
    UncertaintyStatus,
)
from .errors import ReferenceInputCode
from .execution import (
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    ReferenceResolutionRecord,
    ReferenceRunRecord,
    WitnessReferenceRequest,
    WitnessRunGrant,
    _bind_run_attempt_executor,
    create_reference_resolution_record,
    create_reference_run_record,
)
from .model import (
    ArtifactContentBinding,
    ConditioningAssessment,
    DependencyDisclosure,
    OptionalBinding,
    PinnedReferenceIdentity,
    QualificationBinding,
    RealizedComponentBinding,
    ReferenceAuthorityTargetBinding,
    ReferenceProvenance,
    ReferenceScopeBinding,
    SupportApplicabilityAssessment,
    UncertaintyRepresentation,
    exact,
    invalid,
    owner,
    pinned_identity,
)
from .policy import (
    PrecomputedReferenceSourceManifest,
    ReferenceComposition,
    ReferencePolicy,
    ReferencePolicyEntry,
    primary_target_for_composition,
    validate_reference_policy_graph,
    witness_target_for_entry,
)
from .runners import validate_primary_invocation, validate_witness_invocation

_VERSION = "1.0"
_POLICY_ID = "b04_fixture_reference_policy"
_PRIMARY_PAYLOAD = b"CARBON B04 FIXTURE PRIMARY PAYLOAD V1\n"
_WITNESS_PAYLOAD = b"CARBON B04 FIXTURE WITNESS PAYLOAD V1\n"
_RUNNER_TOKEN = object()


def _digest(label: str) -> str:
    return tagged_sha256(label.encode("ascii"))


def _owner(kind: str, label: str, challenge: ChallengeKey) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(challenge),
        object_id=f"b04_fixture_{label}_{kind}",
        object_version=_VERSION,
        content_digest=_digest(f"owner:{challenge}:{label}:{kind}"),
    )


def _identity(
    kind: ReferenceIdentityKind,
    label: str,
    challenge: ChallengeKey,
) -> PinnedReferenceIdentity:
    return PinnedReferenceIdentity(
        challenge,
        _digest(f"identity:{challenge}:{label}:{kind.value}"),
        f"b04_fixture_{label}_{kind.value.lower()}",
        kind,
        _VERSION,
    )


def _common_top_fields(
    challenge: ChallengeKey,
    label: str,
) -> tuple[object, ...]:
    return (
        challenge,
        f"b04_fixture_{label}",
        _VERSION,
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        _digest(f"top:{challenge}:{label}"),
    )


def _scope(challenge: ChallengeKey) -> ReferenceScopeBinding:
    return ReferenceScopeBinding(
        CandidateOutputContractRef(*_common_top_fields(challenge, "candidate_output")),
        _owner("claim_scope", "scope", challenge),
        _owner("evidence_campaign", "scope", challenge),
        (
            InstanceDistributionContractRef(
                *_common_top_fields(challenge, "evidence_population"),
                "EVIDENCE_CAMPAIGN",
            ),
        ),
        PhysicalSystemSpecRef(*_common_top_fields(challenge, "physical_system")),
        InstanceDistributionContractRef(
            *_common_top_fields(challenge, "proposal_population"),
            "OFFICIAL_PROPOSAL_Q",
        ),
        _owner("reference_fidelity_allocation", "scope", challenge),
        SamplingPlanRef(*_common_top_fields(challenge, "sampling_plan")),
        InstanceDistributionContractRef(
            *_common_top_fields(challenge, "target_population"),
            "TARGET_WORKLOAD_P",
        ),
        _owner("intended_estimand_or_reporting", "scope", challenge),
    )


def _case_ref(challenge: ChallengeKey) -> CanonicalChallengeCaseRef:
    return CanonicalChallengeCaseRef(
        *_common_top_fields(challenge, "protected_case"),
        "PROTECTED",
    )


def _dependency_disclosures(
    challenge: ChallengeKey,
) -> tuple[DependencyDisclosure, ...]:
    return tuple(
        DependencyDisclosure(
            category,
            (
                _owner(
                    "provenance",
                    f"shared_dependency_{category.value.lower()}",
                    challenge,
                ),
            ),
            DependencyRelation.SHARED,
        )
        for category in DependencyCategory
    )


def _provenance(
    *,
    challenge: ChallengeKey,
    environment_ref: PinnedReferenceIdentity,
    implementation_ref: PinnedReferenceIdentity,
    method_ref: PinnedReferenceIdentity,
    rights_profile_ref: object,
    scope: ReferenceScopeBinding,
    source_ref: PinnedReferenceIdentity,
) -> ReferenceProvenance:
    return ReferenceProvenance(
        _dependency_disclosures(challenge),
        environment_ref,
        scope.evidence_campaign_ref,
        (_owner("provenance", "fixed_copied_bytes", challenge),),
        implementation_ref,
        method_ref,
        (_owner("provenance", "fixture_registration", challenge),),
        (_owner("authority_evidence", "fixture_reviewer", challenge),),
        rights_profile_ref,
        source_ref,
    )


def _applicability(
    challenge: ChallengeKey,
    status: SupportApplicabilityStatus,
) -> SupportApplicabilityAssessment:
    return SupportApplicabilityAssessment(
        (_owner("applicability_evidence", "fixed_scope", challenge),),
        (_owner("restriction", "fixture_only", challenge),),
        _identity(
            ReferenceIdentityKind.APPLICABILITY_METHOD, "applicability", challenge
        ),
        status,
        _owner("support_boundary", "shared_scope", challenge),
    )


def _conditioning(
    challenge: ChallengeKey,
    status: ConditioningStatus,
) -> ConditioningAssessment:
    return ConditioningAssessment(
        (_owner("sensitivity_analysis", "fixed_conditioning", challenge),),
        (_owner("restriction", "fixture_only", challenge),),
        _identity(ReferenceIdentityKind.CONDITIONING_METHOD, "conditioning", challenge),
        status,
    )


def _uncertainty(
    challenge: ChallengeKey,
    status: UncertaintyStatus = UncertaintyStatus.RESOLVED,
) -> UncertaintyRepresentation:
    return UncertaintyRepresentation(
        (UncertaintyComponentKind.NUMERICAL,),
        _owner("coverage_qualification", "fixture_coverage", challenge),
        _owner(
            "replication_dependence_policy",
            "fixture_dependence",
            challenge,
        ),
        _owner("estimand_scope", "fixture_estimand", challenge),
        (_owner("audit_evidence", "fixture_uncertainty", challenge),),
        (_owner("restriction", "fixture_only", challenge),),
        _identity(ReferenceIdentityKind.UNCERTAINTY_METHOD, "uncertainty", challenge),
        _identity(
            ReferenceIdentityKind.UNCERTAINTY_REPRESENTATION,
            "uncertainty",
            challenge,
        ),
        status,
        _identity(ReferenceIdentityKind.UNITS, "fixture_units", challenge),
        (_owner("permitted_use", "fixture_tests", challenge),),
    )


def _component_bindings(
    grant: PrimaryRunGrant | WitnessRunGrant,
) -> tuple[RealizedComponentBinding, ...]:
    return tuple(
        RealizedComponentBinding(
            grant.configuration_ref,
            entry_ref,
            grant.environment_ref,
            grant.hardware_ref,
            grant.implementation_ref,
            grant.method_ref,
            grant.precision_ref,
        )
        for entry_ref in grant.component_entry_refs
    )


def _create_fixture_runner_meta():
    """Create a metaclass whose concrete fixture family can be sealed once."""

    sealed = False

    class FixtureRunnerMeta(type):
        def __new__(
            cls,
            name: str,
            bases: tuple[type, ...],
            namespace: dict[str, object],
        ):
            if sealed:
                raise TypeError("fixture runner family is sealed")
            return super().__new__(cls, name, bases, namespace)

        def __setattr__(cls, name: str, value: object) -> None:
            if sealed:
                raise TypeError("fixture runner classes are immutable")
            super().__setattr__(name, value)

        def __delattr__(cls, name: str) -> None:
            if sealed:
                raise TypeError("fixture runner classes are immutable")
            super().__delattr__(name)

    def seal() -> None:
        nonlocal sealed
        sealed = True

    return FixtureRunnerMeta, seal


_FixtureRunnerMeta, _seal_fixture_runner_family = _create_fixture_runner_meta()
del _create_fixture_runner_meta


def _create_fixture_runner_state():
    """Create closure-owned runner bindings without exporting capability state."""

    lock = threading.Lock()
    behaviors: MappingProxyType | None = None
    states: WeakKeyDictionary[
        object,
        tuple[
            object,
            ReferenceResolutionRecord,
            object,
            type,
            PinnedReferenceIdentity,
            ReferenceFailureReason | None,
            str,
            bytes | None,
        ],
    ] = WeakKeyDictionary()

    def configure(
        value: tuple[
            tuple[
                type,
                ReferenceFailureReason | None,
                str,
                bytes | None,
            ],
            ...,
        ],
    ) -> None:
        nonlocal behaviors
        configured: dict[
            type,
            tuple[ReferenceFailureReason | None, str, bytes | None],
        ] = {}
        for runner_type, reason, label, payload in value:
            if (
                type(runner_type) is not _FixtureRunnerMeta
                or runner_type in configured
                or (reason is not None and type(reason) is not ReferenceFailureReason)
                or type(label) is not str
                or (payload is not None and type(payload) is not bytes)
            ):
                raise invalid("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
            configured[runner_type] = (reason, label, payload)
        with lock:
            if behaviors is not None:
                raise invalid("/runner", ReferenceInputCode.STALE_BINDING)
            behaviors = MappingProxyType(configured)

    def require_state(runner: object):
        with lock:
            state = states.get(runner)
        if state is None or state[3] is not type(runner):
            raise invalid("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
        return state

    def register(
        runner: object,
        resolution: ReferenceResolutionRecord,
        source_ref: PinnedReferenceIdentity,
        rights_profile_ref: object,
    ) -> None:
        with lock:
            behavior = None if behaviors is None else behaviors.get(type(runner))
        if behavior is None:
            raise invalid("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
        capability = _bind_run_attempt_executor(resolution, runner)
        state = (
            capability,
            resolution,
            owner(
                rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge_key=resolution.challenge_key,
            ),
            type(runner),
            source_ref,
            *behavior,
        )
        with lock:
            if runner in states:
                raise invalid("/runner", ReferenceInputCode.STALE_BINDING)
            states[runner] = state

    def require_outcome(runner: object, outcome: ResolutionOutcome) -> None:
        state = require_state(runner)
        if state[1].outcome is not outcome:
            raise invalid("/resolution_ref", ReferenceInputCode.STALE_BINDING)

    def create_run(
        runner: object,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
    ) -> ReferenceRunRecord:
        state = require_state(runner)
        capability, resolution, rights, _, source, reason, label, payload = state
        challenge = request.challenge_key
        observed = () if reason is None else (reason,)
        conditioning_status = (
            ConditioningStatus.UNRESOLVED
            if reason is ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED
            else ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
        )
        artifact = (
            ArtifactContentBinding(
                tagged_sha256(payload),
                _identity(
                    ReferenceIdentityKind.ARTIFACT_DESCRIPTOR,
                    f"{label}_artifact",
                    challenge,
                ),
                ReferenceArtifactOrigin.FIXTURE_ONLY,
            )
            if reason is None and type(payload) is bytes
            else None
        )
        return create_reference_run_record(
            request=request,
            grant=grant,
            resolution=resolution,
            observed_reasons=observed,
            artifact_content=artifact,
            applicability_assessment=_applicability(
                challenge,
                SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
            ),
            component_bindings=_component_bindings(grant),
            conditioning_assessment=_conditioning(challenge, conditioning_status),
            diagnostics_ref=_identity(
                ReferenceIdentityKind.DIAGNOSTICS,
                f"{label}_diagnostics",
                challenge,
            ),
            provenance_binding=_provenance(
                challenge=challenge,
                environment_ref=grant.environment_ref,
                implementation_ref=grant.implementation_ref,
                method_ref=grant.method_ref,
                rights_profile_ref=rights,
                scope=request.scope_binding,
                source_ref=source,
            ),
            resource_receipt_ref=_identity(
                ReferenceIdentityKind.RESOURCE_RECEIPT,
                f"{label}_receipt",
                challenge,
            ),
            run_id=f"b04_fixture_{label}_run",
            run_version=_VERSION,
            uncertainty_binding=_uncertainty(challenge),
            _attempt_executor=runner,
            _attempt_capability=capability,
        )

    return configure, register, require_outcome, create_run


(
    _configure_fixture_runner_behaviors,
    _register_fixture_runner,
    _require_fixture_runner_outcome,
    _create_fixture_run,
) = _create_fixture_runner_state()
del _create_fixture_runner_state


class _FixtureRunnerBase(metaclass=_FixtureRunnerMeta):
    __slots__ = ("__weakref__",)

    def __init__(
        self,
        resolution: ReferenceResolutionRecord,
        source_ref: PinnedReferenceIdentity,
        rights_profile_ref: object,
        *,
        _token: object,
    ) -> None:
        if _token is not _RUNNER_TOKEN:
            raise TypeError("fixture runners require the fixed graph builder")
        checked_resolution = exact(
            resolution,
            ReferenceResolutionRecord,
            "/resolution_ref",
        )
        checked_source = pinned_identity(
            source_ref,
            ReferenceIdentityKind.SOURCE,
            "/source_ref",
            challenge_key=checked_resolution.challenge_key,
        )
        _register_fixture_runner(
            self,
            checked_resolution,
            checked_source,
            rights_profile_ref,
        )

    def _create_run(
        self,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
    ) -> ReferenceRunRecord:
        return _create_fixture_run(self, request, grant)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise FrozenInstanceError("fixture runners are immutable")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected fixture runners cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected fixture runners cannot be pickled")


class SupportedPrimaryFixtureRunner(_FixtureRunnerBase):
    """Fixed primary fixture capability returning conspicuous bytes."""

    __slots__ = ()

    def run_primary(
        self,
        grant: PrimaryRunGrant,
        request: PrimaryReferenceRequest,
    ) -> ReferenceRunRecord:
        validate_primary_invocation(grant, request)
        _require_fixture_runner_outcome(
            self,
            ResolutionOutcome.PRIMARY_GRANT_ISSUED,
        )
        return self._create_run(request, grant)


class ConditioningLimitedPrimaryFixtureRunner(_FixtureRunnerBase):
    """Fixed primary fixture capability with unresolved conditioning evidence."""

    __slots__ = ()

    run_primary = SupportedPrimaryFixtureRunner.run_primary


class NumericalFailurePrimaryFixtureRunner(_FixtureRunnerBase):
    """Fixed primary fixture capability with a numerical terminal reason."""

    __slots__ = ()

    run_primary = SupportedPrimaryFixtureRunner.run_primary


class MalformedPrimaryFixtureRunner(_FixtureRunnerBase):
    """Fixed primary fixture capability with a malformed terminal reason."""

    __slots__ = ()

    run_primary = SupportedPrimaryFixtureRunner.run_primary


class InfrastructureFailurePrimaryFixtureRunner(_FixtureRunnerBase):
    """Fixed primary fixture capability with an infrastructure terminal reason."""

    __slots__ = ()

    run_primary = SupportedPrimaryFixtureRunner.run_primary


class SupportedWitnessFixtureRunner(_FixtureRunnerBase):
    """Fixed witness fixture capability returning conspicuous distinct bytes."""

    __slots__ = ()

    def run_witness(
        self,
        grant: WitnessRunGrant,
        request: WitnessReferenceRequest,
    ) -> ReferenceRunRecord:
        validate_witness_invocation(grant, request)
        _require_fixture_runner_outcome(
            self,
            ResolutionOutcome.WITNESS_GRANT_ISSUED,
        )
        return self._create_run(request, grant)


_configure_fixture_runner_behaviors(
    (
        (SupportedPrimaryFixtureRunner, None, "primary_supported", _PRIMARY_PAYLOAD),
        (
            ConditioningLimitedPrimaryFixtureRunner,
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
            "primary_conditioning",
            None,
        ),
        (
            NumericalFailurePrimaryFixtureRunner,
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            "primary_numerical",
            None,
        ),
        (
            MalformedPrimaryFixtureRunner,
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
            "primary_malformed",
            None,
        ),
        (
            InfrastructureFailurePrimaryFixtureRunner,
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
            "primary_infrastructure",
            None,
        ),
        (SupportedWitnessFixtureRunner, None, "witness_supported", _WITNESS_PAYLOAD),
    )
)
_seal_fixture_runner_family()
del _configure_fixture_runner_behaviors
del _seal_fixture_runner_family


@dataclass(frozen=True, slots=True, repr=False)
class B04FixtureRunPath:
    """One exact request/grant/resolution/run path in the fixed graph."""

    grant: PrimaryRunGrant | WitnessRunGrant
    request: PrimaryReferenceRequest | WitnessReferenceRequest
    resolution: ReferenceResolutionRecord
    run: ReferenceRunRecord
    runner: object

    def __repr__(self) -> str:
        return "B04FixtureRunPath(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected fixture paths cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class B04FixtureReferenceGraph:
    """Complete deterministic graph used only by B-04 engineering tests."""

    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    comparison: ReferenceComparisonRecord
    compositions: tuple[ReferenceComposition, ...]
    conditioning_path: B04FixtureRunPath
    entries: tuple[ReferencePolicyEntry, ...]
    infrastructure_path: B04FixtureRunPath
    malformed_path: B04FixtureRunPath
    numerical_path: B04FixtureRunPath
    policy: ReferencePolicy
    precomputed_manifest: PrecomputedReferenceSourceManifest
    primary_artifact: ReferenceArtifact
    primary_fixture_asset: FixtureReferenceAsset
    primary_path: B04FixtureRunPath
    scope_binding: ReferenceScopeBinding
    witness_artifact: ReferenceArtifact
    witness_fixture_asset: FixtureReferenceAsset
    witness_path: B04FixtureRunPath

    @property
    def primary_grant(self) -> PrimaryRunGrant:
        grant = self.primary_path.grant
        if type(grant) is not PrimaryRunGrant:
            raise invalid("/primary_path", ReferenceInputCode.ROLE_MISMATCH)
        return grant

    @property
    def primary_request(self) -> PrimaryReferenceRequest:
        request = self.primary_path.request
        if type(request) is not PrimaryReferenceRequest:
            raise invalid("/primary_path", ReferenceInputCode.ROLE_MISMATCH)
        return request

    @property
    def primary_resolution(self) -> ReferenceResolutionRecord:
        return self.primary_path.resolution

    @property
    def primary_run(self) -> ReferenceRunRecord:
        return self.primary_path.run

    @property
    def witness_grant(self) -> WitnessRunGrant:
        grant = self.witness_path.grant
        if type(grant) is not WitnessRunGrant:
            raise invalid("/witness_path", ReferenceInputCode.ROLE_MISMATCH)
        return grant

    @property
    def witness_request(self) -> WitnessReferenceRequest:
        request = self.witness_path.request
        if type(request) is not WitnessReferenceRequest:
            raise invalid("/witness_path", ReferenceInputCode.ROLE_MISMATCH)
        return request

    @property
    def witness_resolution(self) -> ReferenceResolutionRecord:
        return self.witness_path.resolution

    @property
    def witness_run(self) -> ReferenceRunRecord:
        return self.witness_path.run

    def __repr__(self) -> str:
        return "B04FixtureReferenceGraph(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected fixture graphs cannot be pickled")


def _policy_entry(
    *,
    label: str,
    authority_function: ReferenceAuthorityFunction,
    challenge: ChallengeKey,
    scope: ReferenceScopeBinding,
    source_ref: PinnedReferenceIdentity,
    representation_ref: PinnedReferenceIdentity,
    artifact_schema_ref: PinnedReferenceIdentity,
    rights_profile_ref: object,
    manifest: PrecomputedReferenceSourceManifest | None = None,
) -> ReferencePolicyEntry:
    return ReferencePolicyEntry(
        applicability_policy_ref=_owner("applicability", label, challenge),
        artifact_schema_ref=artifact_schema_ref,
        authority_function=authority_function,
        challenge_key=challenge,
        conditioning_policy_ref=_owner("sensitivity_analysis", label, challenge),
        correlation_policy_ref=_owner(
            "replication_dependence_policy", label, challenge
        ),
        dependency_constraints_ref=_identity(
            ReferenceIdentityKind.DEPENDENCY_SET, label, challenge
        ),
        disclosure_policy_ref=_owner("disclosure_policy", "policy", challenge),
        entry_id=f"b04_fixture_{label}_entry",
        entry_version=_VERSION,
        environment_constraints_ref=_identity(
            ReferenceIdentityKind.ENVIRONMENT, f"{label}_constraints", challenge
        ),
        evidence_role_binding=EvidenceRoleBinding(EvidenceRole.NUMERICAL),
        expected_representation_ref=representation_ref,
        implementation_constraints_ref=_identity(
            ReferenceIdentityKind.IMPLEMENTATION, f"{label}_constraints", challenge
        ),
        method_constraints_ref=_identity(
            ReferenceIdentityKind.METHOD, f"{label}_constraints", challenge
        ),
        policy_id=_POLICY_ID,
        policy_version=_VERSION,
        precomputed_source_manifest_ref=(
            OptionalBinding.present(manifest.to_ref())
            if manifest is not None
            else OptionalBinding.absent()
        ),
        provenance_policy_ref=_owner("provenance", label, challenge),
        qualification_policy_ref=_owner(
            "reference_qualification_policy", label, challenge
        ),
        resource_policy_ref=_owner("reference_resource_limit", "policy", challenge),
        rights_profile_ref=rights_profile_ref,
        scope_binding=scope,
        source_class=ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
        source_ref=source_ref,
        support_boundary_ref=_owner("support_boundary", "shared_scope", challenge),
        uncertainty_policy_ref=_owner("statistics_objective", label, challenge),
    )


def _precomputed_manifest(
    *,
    challenge: ChallengeKey,
    scope: ReferenceScopeBinding,
    source_ref: PinnedReferenceIdentity,
    representation_ref: PinnedReferenceIdentity,
    artifact_schema_ref: PinnedReferenceIdentity,
    rights_profile_ref: object,
) -> PrecomputedReferenceSourceManifest:
    return PrecomputedReferenceSourceManifest(
        artifact_schema_ref=artifact_schema_ref,
        challenge_key=challenge,
        manifest_id="b04_fixture_precomputed_manifest",
        manifest_version=_VERSION,
        provenance_binding=_provenance(
            challenge=challenge,
            environment_ref=_identity(
                ReferenceIdentityKind.ENVIRONMENT,
                "precomputed_manifest",
                challenge,
            ),
            implementation_ref=_identity(
                ReferenceIdentityKind.IMPLEMENTATION,
                "precomputed_manifest",
                challenge,
            ),
            method_ref=_identity(
                ReferenceIdentityKind.METHOD,
                "precomputed_manifest",
                challenge,
            ),
            rights_profile_ref=rights_profile_ref,
            scope=scope,
            source_ref=source_ref,
        ),
        representation_ref=representation_ref,
        rights_profile_ref=rights_profile_ref,
        scope_binding=scope,
        source_class=ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
        source_corpus_digest=_digest("fixed precomputed fixture corpus"),
        source_ref=source_ref,
        supersedes=OptionalBinding.absent(),
    )


def _primary_composition(
    *,
    challenge: ChallengeKey,
    scope: ReferenceScopeBinding,
    members: tuple[ReferencePolicyEntry, ReferencePolicyEntry],
    representation_ref: PinnedReferenceIdentity,
    artifact_schema_ref: PinnedReferenceIdentity,
    rights_profile_ref: object,
) -> ReferenceComposition:
    return ReferenceComposition(
        applicability_policy_ref=_owner("applicability", "composition", challenge),
        artifact_schema_ref=artifact_schema_ref,
        authority_function=ReferenceAuthorityFunction.PRIMARY,
        challenge_key=challenge,
        combination_environment_ref=_identity(
            ReferenceIdentityKind.ENVIRONMENT, "composition", challenge
        ),
        combination_implementation_ref=_identity(
            ReferenceIdentityKind.IMPLEMENTATION, "composition", challenge
        ),
        combination_method_ref=_identity(
            ReferenceIdentityKind.COMBINATION_METHOD, "composition", challenge
        ),
        composition_id="b04_fixture_primary_composition",
        composition_kind=ReferenceCompositionKind.REGISTERED_HYBRID_POLICY,
        composition_version=_VERSION,
        conditioning_policy_ref=_owner(
            "sensitivity_analysis", "composition", challenge
        ),
        correlation_policy_ref=_owner(
            "replication_dependence_policy", "composition", challenge
        ),
        disclosure_policy_ref=_owner("disclosure_policy", "policy", challenge),
        expected_representation_ref=representation_ref,
        member_entry_refs=tuple(member.to_ref() for member in members),
        policy_id=_POLICY_ID,
        policy_version=_VERSION,
        provenance_policy_ref=_owner("provenance", "composition", challenge),
        qualification_policy_ref=_owner(
            "reference_qualification_policy", "composition", challenge
        ),
        resource_policy_ref=_owner("reference_resource_limit", "policy", challenge),
        rights_profile_ref=rights_profile_ref,
        scope_binding=scope,
        uncertainty_policy_ref=_owner("statistics_objective", "composition", challenge),
    )


def _reference_policy(
    *,
    challenge: ChallengeKey,
    scope: ReferenceScopeBinding,
    entries: tuple[ReferencePolicyEntry, ...],
    composition: ReferenceComposition,
    witness: ReferencePolicyEntry,
    rights_profile_ref: object,
) -> ReferencePolicy:
    primary_target = primary_target_for_composition(composition)
    witness_target = witness_target_for_entry(witness)
    return ReferencePolicy(
        answer_key_authority_target=ReferenceAuthorityTargetBinding.bound(
            primary_target
        ),
        applicability_policy_ref=_owner("applicability", "policy", challenge),
        challenge_key=challenge,
        comparison_policy_ref=_owner("semantic_equivalence", "policy", challenge),
        composition_refs=(composition.to_ref(),),
        disclosure_policy_ref=_owner("disclosure_policy", "policy", challenge),
        entry_refs=tuple(entry.to_ref() for entry in entries),
        fallback_policy_ref=_owner("restriction", "no_fallback", challenge),
        history_binding_ref=_owner("authoring_registration", "policy", challenge),
        policy_id=_POLICY_ID,
        policy_version=_VERSION,
        provenance_policy_ref=_owner("provenance", "policy", challenge),
        qualification_policy_ref=_owner(
            "reference_qualification_policy", "policy", challenge
        ),
        registered_witness_targets=(witness_target,),
        resource_policy_ref=_owner("reference_resource_limit", "policy", challenge),
        revocation_binding_ref=OptionalBinding.absent(),
        rights_profile_ref=rights_profile_ref,
        scope_binding=scope,
        supersedes=OptionalBinding.absent(),
        uncertainty_policy_ref=_owner("statistics_objective", "policy", challenge),
    )


def _request(
    *,
    label: str,
    policy: ReferencePolicy,
    case_ref: CanonicalChallengeCaseRef,
    witness: bool,
) -> PrimaryReferenceRequest | WitnessReferenceRequest:
    primary_target = policy.answer_key_authority_target.value
    common = {
        "answer_key_authority_target": primary_target,
        "case_ref": case_ref,
        "challenge_key": policy.challenge_key,
        "disclosure_policy_ref": policy.disclosure_policy_ref,
        "idempotency_ref": _identity(
            ReferenceIdentityKind.DETERMINISTIC_MODE,
            f"{label}_request",
            policy.challenge_key,
        ),
        "policy_ref": policy.to_ref(),
        "representation_ref": _identity(
            ReferenceIdentityKind.REPRESENTATION,
            "shared_representation",
            policy.challenge_key,
        ),
        "request_id": f"b04_fixture_{label}_request",
        "request_version": _VERSION,
        "requested_resource_policy_ref": policy.resource_policy_ref,
        "scope_binding": policy.scope_binding,
    }
    if witness:
        return WitnessReferenceRequest(
            execution_target=policy.registered_witness_targets[0],
            **common,
        )
    return PrimaryReferenceRequest(execution_target=primary_target, **common)


def _grant(
    *,
    label: str,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    component_entry_refs: tuple[object, ...],
) -> PrimaryRunGrant | WitnessRunGrant:
    challenge = request.challenge_key
    issuer = _identity(ReferenceIdentityKind.RUN_ISSUER, f"{label}_issuer", challenge)
    common = {
        "answer_key_authority_target": request.answer_key_authority_target,
        "capability_ref": issuer,
        "case_ref": request.case_ref,
        "challenge_key": challenge,
        "component_entry_refs": component_entry_refs,
        "configuration_ref": _identity(
            ReferenceIdentityKind.CONFIGURATION, f"{label}_configuration", challenge
        ),
        "disclosure_policy_ref": request.disclosure_policy_ref,
        "environment_ref": _identity(
            ReferenceIdentityKind.ENVIRONMENT, f"{label}_environment", challenge
        ),
        "grant_id": f"b04_fixture_{label}_grant",
        "grant_version": _VERSION,
        "hardware_ref": _identity(
            ReferenceIdentityKind.HARDWARE, f"{label}_hardware", challenge
        ),
        "implementation_ref": _identity(
            ReferenceIdentityKind.IMPLEMENTATION,
            f"{label}_implementation",
            challenge,
        ),
        "issuance_token": f"b04-fixture-{label}-issuance-v1",
        "issuer_ref": issuer,
        "method_ref": _identity(
            ReferenceIdentityKind.METHOD, f"{label}_method", challenge
        ),
        "policy_ref": request.policy_ref,
        "precision_ref": _identity(
            ReferenceIdentityKind.PRECISION, f"{label}_precision", challenge
        ),
        "representation_ref": request.representation_ref,
        "resource_authorization_ref": _identity(
            ReferenceIdentityKind.RESOURCE_AUTHORIZATION,
            f"{label}_resource",
            challenge,
        ),
        "scope_binding": request.scope_binding,
        "source_class": ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
    }
    if type(request) is PrimaryReferenceRequest:
        return PrimaryRunGrant(
            authority_function=ReferenceAuthorityFunction.PRIMARY,
            evidence_role_binding=EvidenceRoleBinding(EvidenceRole.NUMERICAL),
            execution_target=request.execution_target,
            request_ref=request.to_ref(),
            **common,
        )
    return WitnessRunGrant(
        authority_function=ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        evidence_role_binding=EvidenceRoleBinding(EvidenceRole.NUMERICAL),
        execution_target=request.execution_target,
        request_ref=request.to_ref(),
        **common,
    )


def _resolution(
    *,
    label: str,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    policy: ReferencePolicy,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
    manifest: PrecomputedReferenceSourceManifest,
) -> ReferenceResolutionRecord:
    return create_reference_resolution_record(
        request=request,
        grant=grant,
        observed_reasons=(),
        applicability_assessment=_applicability(
            request.challenge_key,
            SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
        ),
        authority_function=grant.authority_function,
        evidence_role_binding=grant.evidence_role_binding,
        qualification_binding=QualificationBinding.bound(
            _owner(
                "qualification_evidence_bundle",
                f"{label}_structural",
                request.challenge_key,
            )
        ),
        resolution_id=f"b04_fixture_{label}_resolution",
        resolution_version=_VERSION,
        resolver_ref=_identity(
            ReferenceIdentityKind.RESOLVER,
            f"{label}_resolver",
            request.challenge_key,
        ),
        resource_policy_ref=request.requested_resource_policy_ref,
        source_class=grant.source_class,
        policy=policy,
        entries=entries,
        compositions=compositions,
        precomputed_manifests=(manifest,),
    )


def _primary_path(
    *,
    label: str,
    runner_type: type[_FixtureRunnerBase],
    policy: ReferencePolicy,
    case_ref: CanonicalChallengeCaseRef,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
    manifest: PrecomputedReferenceSourceManifest,
    source_ref: PinnedReferenceIdentity,
) -> B04FixtureRunPath:
    request = _request(label=label, policy=policy, case_ref=case_ref, witness=False)
    if type(request) is not PrimaryReferenceRequest:
        raise invalid("/request", ReferenceInputCode.ROLE_MISMATCH)
    component_refs = compositions[0].member_entry_refs
    grant = _grant(
        label=label,
        request=request,
        component_entry_refs=component_refs,
    )
    if type(grant) is not PrimaryRunGrant:
        raise invalid("/grant", ReferenceInputCode.ROLE_MISMATCH)
    resolution = _resolution(
        label=label,
        request=request,
        grant=grant,
        policy=policy,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
    )
    runner = runner_type(
        resolution,
        source_ref,
        policy.rights_profile_ref,
        _token=_RUNNER_TOKEN,
    )
    run_method = runner.run_primary
    run = run_method(grant, request)
    return B04FixtureRunPath(grant, request, resolution, run, runner)


def _witness_path(
    *,
    policy: ReferencePolicy,
    case_ref: CanonicalChallengeCaseRef,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
    manifest: PrecomputedReferenceSourceManifest,
    source_ref: PinnedReferenceIdentity,
) -> B04FixtureRunPath:
    label = "witness_supported"
    request = _request(label=label, policy=policy, case_ref=case_ref, witness=True)
    if type(request) is not WitnessReferenceRequest:
        raise invalid("/request", ReferenceInputCode.ROLE_MISMATCH)
    component_refs = (entries[-1].to_ref(),)
    grant = _grant(
        label=label,
        request=request,
        component_entry_refs=component_refs,
    )
    if type(grant) is not WitnessRunGrant:
        raise invalid("/grant", ReferenceInputCode.ROLE_MISMATCH)
    resolution = _resolution(
        label=label,
        request=request,
        grant=grant,
        policy=policy,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
    )
    runner = SupportedWitnessFixtureRunner(
        resolution,
        source_ref,
        policy.rights_profile_ref,
        _token=_RUNNER_TOKEN,
    )
    run = runner.run_witness(grant, request)
    return B04FixtureRunPath(grant, request, resolution, run, runner)


def _build_b04_fixture_reference_graph() -> B04FixtureReferenceGraph:
    """Build one byte-stable fixture graph with no caller-selectable behavior."""

    challenge = ChallengeKey("b04_fixture_reference", _VERSION)
    scope = _scope(challenge)
    case_ref = _case_ref(challenge)
    representation = _identity(
        ReferenceIdentityKind.REPRESENTATION,
        "shared_representation",
        challenge,
    )
    artifact_schema = _identity(
        ReferenceIdentityKind.ARTIFACT_SCHEMA,
        "shared_artifact_schema",
        challenge,
    )
    rights = _owner("rights_profile", "policy", challenge)
    primary_source = _identity(
        ReferenceIdentityKind.SOURCE,
        "primary_source",
        challenge,
    )
    witness_source = _identity(
        ReferenceIdentityKind.SOURCE,
        "witness_source",
        challenge,
    )
    manifest = _precomputed_manifest(
        challenge=challenge,
        scope=scope,
        source_ref=primary_source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
    )
    first = _policy_entry(
        label="primary_component_one",
        authority_function=ReferenceAuthorityFunction.REGISTERED_COMPONENT,
        challenge=challenge,
        scope=scope,
        source_ref=primary_source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
        manifest=manifest,
    )
    second = _policy_entry(
        label="primary_component_two",
        authority_function=ReferenceAuthorityFunction.REGISTERED_COMPONENT,
        challenge=challenge,
        scope=scope,
        source_ref=primary_source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
    )
    witness = _policy_entry(
        label="witness",
        authority_function=ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        challenge=challenge,
        scope=scope,
        source_ref=witness_source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
    )
    entries = (first, second, witness)
    composition = _primary_composition(
        challenge=challenge,
        scope=scope,
        members=(first, second),
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
    )
    compositions = (composition,)
    policy = _reference_policy(
        challenge=challenge,
        scope=scope,
        entries=entries,
        composition=composition,
        witness=witness,
        rights_profile_ref=rights,
    )
    validate_reference_policy_graph(
        policy,
        entries=entries,
        compositions=compositions,
        precomputed_manifests=(manifest,),
    )
    primary = _primary_path(
        label="primary_supported",
        runner_type=SupportedPrimaryFixtureRunner,
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=primary_source,
    )
    witness_path = _witness_path(
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=witness_source,
    )
    conditioning = _primary_path(
        label="primary_conditioning",
        runner_type=ConditioningLimitedPrimaryFixtureRunner,
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=primary_source,
    )
    numerical = _primary_path(
        label="primary_numerical",
        runner_type=NumericalFailurePrimaryFixtureRunner,
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=primary_source,
    )
    malformed = _primary_path(
        label="primary_malformed",
        runner_type=MalformedPrimaryFixtureRunner,
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=primary_source,
    )
    infrastructure = _primary_path(
        label="primary_infrastructure",
        runner_type=InfrastructureFailurePrimaryFixtureRunner,
        policy=policy,
        case_ref=case_ref,
        entries=entries,
        compositions=compositions,
        manifest=manifest,
        source_ref=primary_source,
    )
    comparison = create_reference_comparison_record(
        primary_run=primary.run,
        witness_run=witness_path.run,
        observed_reasons=(ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,),
        applicability_evidence_refs=(
            _owner("applicability_evidence", "comparison", challenge),
        ),
        comparison_id="b04_fixture_contested_comparison",
        comparison_method_ref=_identity(
            ReferenceIdentityKind.COMPARISON_METHOD,
            "comparison",
            challenge,
        ),
        comparison_policy_ref=policy.comparison_policy_ref,
        comparison_version=_VERSION,
        dependency_disclosures=_dependency_disclosures(challenge),
        evidence_refs=(_owner("audit_evidence", "comparison", challenge),),
        uncertainty_treatment_ref=_identity(
            ReferenceIdentityKind.UNCERTAINTY_METHOD,
            "comparison_treatment",
            challenge,
        ),
        witness_target=policy.registered_witness_targets[0],
    )
    primary_artifact = create_reference_artifact(
        primary.run,
        artifact_id="b04_fixture_primary_artifact",
        artifact_version=_VERSION,
    )
    witness_artifact = create_reference_artifact(
        witness_path.run,
        artifact_id="b04_fixture_witness_artifact",
        artifact_version=_VERSION,
    )
    primary_asset = create_fixture_reference_asset(
        primary_artifact,
        primary.run,
        fixture_asset_id="b04_fixture_primary_asset",
        fixture_asset_version=_VERSION,
        fixture_provenance_ref=_owner(
            "fixture_registration", "primary_asset", challenge
        ),
        payload_bytes=_PRIMARY_PAYLOAD,
    )
    witness_asset = create_fixture_reference_asset(
        witness_artifact,
        witness_path.run,
        fixture_asset_id="b04_fixture_witness_asset",
        fixture_asset_version=_VERSION,
        fixture_provenance_ref=_owner(
            "fixture_registration", "witness_asset", challenge
        ),
        payload_bytes=_WITNESS_PAYLOAD,
    )
    return B04FixtureReferenceGraph(
        case_ref,
        challenge,
        comparison,
        compositions,
        conditioning,
        entries,
        infrastructure,
        malformed,
        numerical,
        policy,
        manifest,
        primary_artifact,
        primary_asset,
        primary,
        scope,
        witness_artifact,
        witness_asset,
        witness_path,
    )


def _create_fixture_graph_builder(raw_builder):
    """Memoize the one globally registered deterministic fixture graph."""

    lock = threading.Lock()
    graph: B04FixtureReferenceGraph | None = None

    def build() -> B04FixtureReferenceGraph:
        nonlocal graph
        with lock:
            if graph is None:
                graph = raw_builder()
            return graph

    return build


build_b04_fixture_reference_graph = _create_fixture_graph_builder(
    _build_b04_fixture_reference_graph
)
del _create_fixture_graph_builder
del _build_b04_fixture_reference_graph


__all__ = [
    "B04FixtureReferenceGraph",
    "B04FixtureRunPath",
    "ConditioningLimitedPrimaryFixtureRunner",
    "InfrastructureFailurePrimaryFixtureRunner",
    "MalformedPrimaryFixtureRunner",
    "NumericalFailurePrimaryFixtureRunner",
    "SupportedPrimaryFixtureRunner",
    "SupportedWitnessFixtureRunner",
    "build_b04_fixture_reference_graph",
]
