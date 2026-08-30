"""Complete-graph resolution and the one-way B-02A-to-A3 verifier adapter."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, final

from carbon.registry import (
    ChallengeKey,
    ScientificAuthoringEligibility,
    ScientificAuthoringGraphOrigin,
    ScientificAuthoringReason,
    is_sha256_digest,
)

from .history import AuthoringHistoryError, AuthoringHistoryStore
from .loading import (
    AuthoringGraphOrigin,
    GraphCompositionAuthority,
    GraphOriginTag,
    LoadedAuthoringArtifact,
    compose_authoring_graph_origin,
)
from .primitives import reconstruct_challenge_key
from .refs import (
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    TopLevelObjectRef,
    reconstruct_top_level_ref,
    require_owner_ref,
)

_MAX_GRAPH_NODES = 4096
_GRAPH_FINGERPRINT_HEADER = b"carbon.scientific-authoring.graph-fingerprint.v1\x00"
_REQUIRED_AUTHORED_KINDS = frozenset(
    {
        "physical_system_spec",
        "candidate_output_contract",
        "instance_distribution_contract",
        "sampling_plan",
        "training_support_contract",
    }
)


class StatisticsDesignAuthorization(str, Enum):
    """Closed external-owner outcomes for one exact finite design."""

    EXACT_W_ADMITTED = "EXACT_W_ADMITTED"
    NO_W_NONAGGREGATING_AUTHORIZED = "NO_W_NONAGGREGATING_AUTHORIZED"
    NO_W_NONOFFICIAL_REPORTING_AUTHORIZED = "NO_W_NONOFFICIAL_REPORTING_AUTHORIZED"


@final
@dataclass(frozen=True, slots=True)
class StatisticsDesignVerificationRequest:
    """Exact immutable statistics question assembled from a loaded graph.

    The complete SamplingPlan is carried as an exact value so allocation,
    stopping, replacement, duplicate, and other design controls cannot be
    omitted from the external owner's decision.  The resolved population
    objects make P/Q/w substitution independently detectable without adding
    a reverse SamplingPlanRef edge to any authored population.
    """

    sampling_plan_ref: SamplingPlanRef
    sampling_plan: object
    primary_population: object
    selection_population: object
    target_population: object | None
    official_proposal: object | None
    evidence_weight: object | None

    def __post_init__(self) -> None:
        if type(self) is not StatisticsDesignVerificationRequest:
            raise TypeError(
                "StatisticsDesignVerificationRequest subclasses are rejected"
            )
        from .model import ApplicabilityBinding, exact
        from .populations import InstanceDistributionContract
        from .sampling import SamplingPlan

        ref = exact(self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref")
        plan = exact(self.sampling_plan, SamplingPlan, "sampling_plan")
        if ref != plan.to_ref():
            raise ValueError("sampling_plan_ref differs from the exact SamplingPlan")

        primary = exact(
            self.primary_population,
            InstanceDistributionContract,
            "primary_population",
        )
        selection = exact(
            self.selection_population,
            InstanceDistributionContract,
            "selection_population",
        )
        if primary.to_ref() != plan.primary_population_ref:
            raise ValueError("primary population differs from the SamplingPlan pin")
        if selection.to_ref() != plan.selection_population_ref:
            raise ValueError("selection population differs from the SamplingPlan pin")

        def checked_optional(
            value: object | None,
            binding: ApplicabilityBinding[InstanceDistributionContractRef],
            field: str,
        ) -> object | None:
            if binding.is_bound:
                population = exact(value, InstanceDistributionContract, field)
                if population.to_ref() != binding.value:
                    raise ValueError(f"{field} differs from the SamplingPlan pin")
                return population
            if value is not None:
                raise ValueError(f"{field} supplied for an inapplicable binding")
            return None

        target = checked_optional(
            self.target_population,
            plan.target_population_binding,
            "target_population",
        )
        proposal = checked_optional(
            self.official_proposal,
            plan.official_proposal_binding,
            "official_proposal",
        )
        weight = checked_optional(
            self.evidence_weight,
            plan.evidence_weight_binding,
            "evidence_weight",
        )
        object.__setattr__(self, "sampling_plan_ref", ref)
        object.__setattr__(self, "sampling_plan", plan)
        object.__setattr__(self, "primary_population", primary)
        object.__setattr__(self, "selection_population", selection)
        object.__setattr__(self, "target_population", target)
        object.__setattr__(self, "official_proposal", proposal)
        object.__setattr__(self, "evidence_weight", weight)


def _copy_statistics_request(
    value: object,
) -> StatisticsDesignVerificationRequest:
    from .model import exact

    request = exact(
        value,
        StatisticsDesignVerificationRequest,
        "statistics verification request",
    )
    return StatisticsDesignVerificationRequest(
        sampling_plan_ref=request.sampling_plan_ref,
        sampling_plan=request.sampling_plan,
        primary_population=request.primary_population,
        selection_population=request.selection_population,
        target_population=request.target_population,
        official_proposal=request.official_proposal,
        evidence_weight=request.evidence_weight,
    )


@final
@dataclass(frozen=True, slots=True)
class StatisticsDesignVerification:
    """Exact owner authorization whose request echo is identity-bearing."""

    request: StatisticsDesignVerificationRequest
    authorization: StatisticsDesignAuthorization

    def __post_init__(self) -> None:
        if type(self) is not StatisticsDesignVerification:
            raise TypeError("StatisticsDesignVerification subclasses are rejected")
        from .model import exact_enum

        object.__setattr__(self, "request", _copy_statistics_request(self.request))
        object.__setattr__(
            self,
            "authorization",
            exact_enum(
                self.authorization,
                StatisticsDesignAuthorization,
                "statistics design authorization",
            ),
        )


class StatisticsDesignAuthority(Protocol):
    """Statistics-owner verifier for one exact SamplingPlan and design law."""

    def verify_statistics_design(
        self,
        request: StatisticsDesignVerificationRequest,
        /,
    ) -> StatisticsDesignVerification:
        """Return an exact echoing authorization or fail closed."""
        ...


class TransientTimeComponent(str, Enum):
    """Closed physical components an equivalence result must cover."""

    TIME_COORDINATE = "TIME_COORDINATE"
    HORIZON = "HORIZON"
    ENDPOINT = "ENDPOINT"


_TRANSIENT_TIME_COMPONENTS = (
    TransientTimeComponent.TIME_COORDINATE,
    TransientTimeComponent.HORIZON,
    TransientTimeComponent.ENDPOINT,
)


@final
@dataclass(frozen=True, slots=True)
class TransientTimeEquivalenceRequest:
    """Exact SciML question for one loaded transient physical/candidate pair."""

    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    physical_time_contract: object
    candidate_time_horizon_binding: object
    candidate_input_contracts: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not TransientTimeEquivalenceRequest:
            raise TypeError("TransientTimeEquivalenceRequest subclasses are rejected")
        from .model import TimeMode, exact, exact_tuple
        from .physical import TimeContract, TimeHorizonBinding, ValueFieldContract

        physical_ref = exact(
            self.physical_system_ref,
            PhysicalSystemSpecRef,
            "physical_system_ref",
        )
        candidate_ref = exact(
            self.candidate_output_ref,
            CandidateOutputContractRef,
            "candidate_output_ref",
        )
        if physical_ref.challenge_key != candidate_ref.challenge_key:
            raise ValueError("transient equivalence refs cross Challenge versions")
        time_contract = exact(
            self.physical_time_contract,
            TimeContract,
            "physical_time_contract",
        )
        if time_contract.mode is not TimeMode.TRANSIENT:
            raise ValueError("transient equivalence requires a transient TimeContract")
        binding = exact(
            self.candidate_time_horizon_binding,
            TimeHorizonBinding,
            "candidate_time_horizon_binding",
        )
        fields = exact_tuple(
            self.candidate_input_contracts,
            ValueFieldContract,
            "candidate_input_contracts",
            nonempty=True,
            unique=True,
        )
        field_ids = tuple(item.field_id for item in fields)
        if len(set(field_ids)) != len(field_ids):
            raise ValueError("candidate input contracts contain a duplicate field ID")
        if not set(binding.candidate_field_ids).issubset(field_ids):
            raise ValueError(
                "time/horizon binding names an unknown candidate input contract"
            )
        object.__setattr__(self, "physical_system_ref", physical_ref)
        object.__setattr__(self, "candidate_output_ref", candidate_ref)
        object.__setattr__(self, "physical_time_contract", time_contract)
        object.__setattr__(self, "candidate_time_horizon_binding", binding)
        object.__setattr__(self, "candidate_input_contracts", tuple(fields))


def _copy_transient_request(value: object) -> TransientTimeEquivalenceRequest:
    from .model import exact

    request = exact(
        value,
        TransientTimeEquivalenceRequest,
        "transient equivalence request",
    )
    return TransientTimeEquivalenceRequest(
        physical_system_ref=request.physical_system_ref,
        candidate_output_ref=request.candidate_output_ref,
        physical_time_contract=request.physical_time_contract,
        candidate_time_horizon_binding=request.candidate_time_horizon_binding,
        candidate_input_contracts=request.candidate_input_contracts,
    )


@final
@dataclass(frozen=True, slots=True)
class TransientTimeComponentBinding:
    """One exact SciML-owned component-to-candidate equivalence decision."""

    component: TransientTimeComponent
    candidate_field_id: str
    candidate_semantic_role_ref: object
    equivalence_ref: object

    def __post_init__(self) -> None:
        if type(self) is not TransientTimeComponentBinding:
            raise TypeError("TransientTimeComponentBinding subclasses are rejected")
        from .model import exact_enum
        from .primitives import validate_canonical_id

        object.__setattr__(
            self,
            "component",
            exact_enum(
                self.component,
                TransientTimeComponent,
                "transient time component",
            ),
        )
        object.__setattr__(
            self,
            "candidate_field_id",
            validate_canonical_id(self.candidate_field_id, "candidate_field_id"),
        )
        object.__setattr__(
            self,
            "candidate_semantic_role_ref",
            require_owner_ref(
                self.candidate_semantic_role_ref,
                "semantic_clause",
            ),
        )
        object.__setattr__(
            self,
            "equivalence_ref",
            require_owner_ref(self.equivalence_ref, "semantic_equivalence"),
        )


@final
@dataclass(frozen=True, slots=True)
class TransientTimeEquivalenceVerification:
    """Exact SciML authorization for all transient time components."""

    request: TransientTimeEquivalenceRequest
    component_bindings: tuple[TransientTimeComponentBinding, ...]

    def __post_init__(self) -> None:
        if type(self) is not TransientTimeEquivalenceVerification:
            raise TypeError(
                "TransientTimeEquivalenceVerification subclasses are rejected"
            )
        from .model import exact_tuple

        request = _copy_transient_request(self.request)
        binding = request.candidate_time_horizon_binding
        components = exact_tuple(
            self.component_bindings,
            TransientTimeComponentBinding,
            "component_bindings",
            nonempty=True,
            unique=True,
        )
        if tuple(item.component for item in components) != _TRANSIENT_TIME_COMPONENTS:
            raise ValueError(
                "transient verification must bind coordinate, horizon, and endpoint"
            )
        component_field_ids = tuple(item.candidate_field_id for item in components)
        if len(set(component_field_ids)) != len(component_field_ids) or set(
            component_field_ids
        ) != set(binding.candidate_field_ids):
            raise ValueError(
                "transient components must cover each bound candidate field exactly once"
            )
        candidate_fields = {
            item.field_id: item for item in request.candidate_input_contracts
        }
        for component in components:
            if (
                component.candidate_semantic_role_ref
                != candidate_fields[component.candidate_field_id].semantic_role_ref
            ):
                raise ValueError(
                    "transient component semantic ref differs from its candidate field"
                )
        expected_equivalence_refs = (
            binding.time_coordinate_equivalence_ref,
            binding.horizon_equivalence_ref,
            binding.endpoint_equivalence_ref,
        )
        if (
            tuple(item.equivalence_ref for item in components)
            != expected_equivalence_refs
        ):
            raise ValueError(
                "transient component equivalence refs differ from the exact request"
            )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "component_bindings", tuple(components))


class SciMLTimeEquivalenceAuthority(Protocol):
    """SciML-owner verifier for one exact transient candidate binding."""

    def verify_transient_time_equivalence(
        self,
        request: TransientTimeEquivalenceRequest,
        /,
    ) -> TransientTimeEquivalenceVerification:
        """Return an exact echoing equivalence result or fail closed."""
        ...


def _ref_key(value: TopLevelObjectRef) -> tuple[object, ...]:
    extra = ()
    if hasattr(value, "expected_population_role"):
        extra = (value.expected_population_role,)
    elif hasattr(value, "disclosure_class"):
        extra = (value.disclosure_class,)
    return (
        value.object_kind,
        value.challenge_key.challenge_id,
        value.challenge_key.version,
        value.object_id,
        value.object_version,
        value.schema_version,
        value.canonicalization_profile,
        value.content_digest,
        *extra,
    )


def _exact_refs(
    value: object, *, field: str, nonempty: bool
) -> tuple[TopLevelObjectRef, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise TypeError(f"{field} must be a nonempty exact tuple")
    copied = tuple(reconstruct_top_level_ref(item) for item in value)
    ordered = tuple(sorted(copied, key=_ref_key))
    if len(set(ordered)) != len(ordered):
        raise ValueError(f"{field} contains a duplicate exact ref")
    return ordered


def scientific_authoring_graph_fingerprint(value: object) -> str:
    """Hash one exact resolved graph manifest for A3's opaque pin seam."""
    if type(value) is not AuthoringGraphOrigin:
        raise TypeError("value must be an exact AuthoringGraphOrigin")
    from .canonical import (
        CanonicalRecord,
        CanonicalText,
        CanonicalTuple,
        encode_value,
        owner_ref_to_canonical,
        tagged_sha256,
        top_level_ref_to_canonical,
    )

    record = CanonicalRecord(
        "authoring_graph_origin",
        (
            (
                "composition_audit_ref",
                owner_ref_to_canonical(value.composition_audit_ref),
            ),
            (
                "dependency_refs",
                CanonicalTuple(
                    tuple(
                        top_level_ref_to_canonical(ref) for ref in value.dependency_refs
                    ),
                    set_like=True,
                ),
            ),
            ("graph_origin", CanonicalText(value.graph_origin.value)),
            (
                "origin_evidence_refs",
                CanonicalTuple(
                    tuple(
                        owner_ref_to_canonical(ref)
                        for ref in value.origin_evidence_refs
                    ),
                    set_like=True,
                ),
            ),
            ("root_ref", top_level_ref_to_canonical(value.root_ref)),
        ),
    )
    return tagged_sha256(_GRAPH_FINGERPRINT_HEADER + encode_value(record))


@final
@dataclass(frozen=True, slots=True)
class AuthoringGraphBinding:
    """Prospective exact composition-root binding configured outside A3."""

    challenge_key: ChallengeKey
    root_ref: TopLevelObjectRef
    required_refs: tuple[TopLevelObjectRef, ...]
    composition_audit_ref: object

    def __post_init__(self) -> None:
        key = reconstruct_challenge_key(self.challenge_key)
        root = reconstruct_top_level_ref(self.root_ref)
        required = _exact_refs(self.required_refs, field="required_refs", nonempty=True)
        if root in required:
            raise ValueError("root_ref must not be duplicated in required_refs")
        if root.challenge_key != key or any(
            ref.challenge_key != key for ref in required
        ):
            raise ValueError("every graph binding ref must use the exact Challenge key")
        present_kinds = {root.object_kind, *(ref.object_kind for ref in required)}
        if not _REQUIRED_AUTHORED_KINDS.issubset(present_kinds):
            raise ValueError(
                "graph binding must include every required authored-contract kind"
            )
        audit = require_owner_ref(
            self.composition_audit_ref, "origin_composition_audit"
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "root_ref", root)
        object.__setattr__(self, "required_refs", required)
        object.__setattr__(self, "composition_audit_ref", audit)


def _eligibility(
    key: ChallengeKey,
    *,
    graph_fingerprint: str,
    origin: ScientificAuthoringGraphOrigin,
    complete: bool,
    revoked: bool,
) -> ScientificAuthoringEligibility:
    reasons: list[ScientificAuthoringReason] = []
    if not complete:
        reasons.append(ScientificAuthoringReason.GRAPH_INCOMPLETE)
    if origin is ScientificAuthoringGraphOrigin.FIXTURE_DERIVED:
        reasons.append(ScientificAuthoringReason.GRAPH_FIXTURE_DERIVED)
    elif origin is ScientificAuthoringGraphOrigin.DRAFT_OR_UNRESOLVED:
        reasons.append(ScientificAuthoringReason.GRAPH_DRAFT_OR_UNRESOLVED)
    if revoked:
        reasons.append(ScientificAuthoringReason.GRAPH_REVOKED)
    return ScientificAuthoringEligibility(
        challenge_key=key,
        graph_fingerprint=graph_fingerprint,
        graph_origin=origin,
        complete=complete,
        revoked=revoked,
        reasons=tuple(reasons),
    )


@final
class StoreBackedScientificAuthoringVerifier:
    """A3 provider that resolves only exact immutable B-02A history refs."""

    __slots__ = (
        "_bindings",
        "_registered_authority",
        "_sciml_time_equivalence_authority",
        "_statistics_design_authority",
        "_store",
    )

    def __init__(
        self,
        store: AuthoringHistoryStore,
        bindings: tuple[AuthoringGraphBinding, ...],
        *,
        registered_authority: GraphCompositionAuthority | None,
        statistics_design_authority: StatisticsDesignAuthority | None = None,
        sciml_time_equivalence_authority: SciMLTimeEquivalenceAuthority | None = None,
    ) -> None:
        if type(store) is not AuthoringHistoryStore:
            raise TypeError("store must be an exact AuthoringHistoryStore")
        if type(bindings) is not tuple or any(
            type(item) is not AuthoringGraphBinding for item in bindings
        ):
            raise TypeError("bindings must be an exact tuple of graph bindings")
        copied = tuple(
            AuthoringGraphBinding(
                item.challenge_key,
                item.root_ref,
                item.required_refs,
                item.composition_audit_ref,
            )
            for item in bindings
        )
        if len({item.challenge_key for item in copied}) != len(copied):
            raise ValueError("bindings contain a duplicate Challenge key")
        if registered_authority is not None and not callable(
            getattr(registered_authority, "verify_registered_graph", None)
        ):
            raise TypeError("registered_authority must provide verify_registered_graph")
        if statistics_design_authority is not None and not callable(
            getattr(
                statistics_design_authority,
                "verify_statistics_design",
                None,
            )
        ):
            raise TypeError(
                "statistics_design_authority must provide verify_statistics_design"
            )
        if sciml_time_equivalence_authority is not None and not callable(
            getattr(
                sciml_time_equivalence_authority,
                "verify_transient_time_equivalence",
                None,
            )
        ):
            raise TypeError(
                "sciml_time_equivalence_authority must provide "
                "verify_transient_time_equivalence"
            )
        self._store = store
        self._bindings = {item.challenge_key: item for item in copied}
        self._registered_authority = registered_authority
        self._statistics_design_authority = statistics_design_authority
        self._sciml_time_equivalence_authority = sciml_time_equivalence_authority

    @staticmethod
    def _dependencies(
        artifact: LoadedAuthoringArtifact,
    ) -> tuple[TopLevelObjectRef, ...]:
        provider = getattr(artifact.authored_object, "dependency_refs", None)
        if not callable(provider):
            raise TypeError("authored object does not expose dependency_refs")
        return _exact_refs(provider(), field="dependency_refs", nonempty=False)

    @staticmethod
    def _resolved_population(
        objects_by_ref: dict[TopLevelObjectRef, object],
        binding: object,
        *,
        field: str,
    ) -> object | None:
        from .model import ApplicabilityBinding, exact
        from .populations import InstanceDistributionContract

        checked = exact(binding, ApplicabilityBinding, field)
        if not checked.is_bound:
            return None
        try:
            value = objects_by_ref[checked.value]
        except KeyError as exc:
            raise ValueError(f"{field} dependency is missing") from exc
        return exact(value, InstanceDistributionContract, field)

    def _verify_statistics_designs(
        self,
        objects_by_ref: dict[TopLevelObjectRef, object],
    ) -> None:
        from .model import SamplingRole, exact
        from .populations import InstanceDistributionContract
        from .sampling import SamplingPlan

        authority = self._statistics_design_authority
        verifier = (
            None
            if authority is None
            else getattr(authority, "verify_statistics_design", None)
        )
        plans = tuple(
            value for value in objects_by_ref.values() if type(value) is SamplingPlan
        )
        if plans and not callable(verifier):
            raise TypeError("statistics design authority is unavailable")
        for plan in plans:
            primary = exact(
                objects_by_ref[plan.primary_population_ref],
                InstanceDistributionContract,
                "primary_population",
            )
            selection = exact(
                objects_by_ref[plan.selection_population_ref],
                InstanceDistributionContract,
                "selection_population",
            )
            request = StatisticsDesignVerificationRequest(
                sampling_plan_ref=plan.to_ref(),
                sampling_plan=plan,
                primary_population=primary,
                selection_population=selection,
                target_population=self._resolved_population(
                    objects_by_ref,
                    plan.target_population_binding,
                    field="target_population",
                ),
                official_proposal=self._resolved_population(
                    objects_by_ref,
                    plan.official_proposal_binding,
                    field="official_proposal",
                ),
                evidence_weight=self._resolved_population(
                    objects_by_ref,
                    plan.evidence_weight_binding,
                    field="evidence_weight",
                ),
            )
            raw_result = verifier(request)
            if type(raw_result) is not StatisticsDesignVerification:
                raise TypeError("statistics authority returned a wrong result type")
            result = StatisticsDesignVerification(
                request=raw_result.request,
                authorization=raw_result.authorization,
            )
            if result.request != request:
                raise ValueError("statistics authority echoed another exact design")
            if plan.evidence_weight_binding.is_bound:
                allowed = (StatisticsDesignAuthorization.EXACT_W_ADMITTED,)
            elif plan.sampling_role is SamplingRole.OFFICIAL_EVALUATION:
                allowed = (
                    StatisticsDesignAuthorization.NO_W_NONAGGREGATING_AUTHORIZED,
                )
            else:
                allowed = (
                    StatisticsDesignAuthorization.NO_W_NONAGGREGATING_AUTHORIZED,
                    StatisticsDesignAuthorization.NO_W_NONOFFICIAL_REPORTING_AUTHORIZED,
                )
            if result.authorization not in allowed:
                raise ValueError(
                    "statistics authority returned an incompatible authorization"
                )

    def _verify_transient_time_equivalence(
        self,
        objects_by_ref: dict[TopLevelObjectRef, object],
    ) -> None:
        from .model import TimeMode, exact
        from .physical import (
            CandidateOutputContract,
            PhysicalSystemSpec,
        )

        authority = self._sciml_time_equivalence_authority
        verifier = (
            None
            if authority is None
            else getattr(authority, "verify_transient_time_equivalence", None)
        )
        candidates = tuple(
            value
            for value in objects_by_ref.values()
            if type(value) is CandidateOutputContract
        )
        for candidate in candidates:
            physical = exact(
                objects_by_ref[candidate.physical_system_ref],
                PhysicalSystemSpec,
                "candidate physical system",
            )
            if physical.time_contract.mode is not TimeMode.TRANSIENT:
                continue
            if not callable(verifier):
                raise TypeError("SciML time-equivalence authority is unavailable")
            request = TransientTimeEquivalenceRequest(
                physical_system_ref=physical.to_ref(),
                candidate_output_ref=candidate.to_ref(),
                physical_time_contract=physical.time_contract,
                candidate_time_horizon_binding=candidate.time_horizon_binding,
                candidate_input_contracts=tuple(candidate.candidate_inputs),
            )
            raw_result = verifier(request)
            if type(raw_result) is not TransientTimeEquivalenceVerification:
                raise TypeError("SciML authority returned a wrong result type")
            result = TransientTimeEquivalenceVerification(
                request=raw_result.request,
                component_bindings=raw_result.component_bindings,
            )
            if result.request != request:
                raise ValueError("SciML authority echoed another transient binding")

    def verify_scientific_authoring(
        self,
        challenge_key: ChallengeKey,
        expected_graph_fingerprint: str,
        /,
    ) -> ScientificAuthoringEligibility:
        """Resolve one exact graph and return necessary-only structural status."""
        key = reconstruct_challenge_key(challenge_key)
        if not is_sha256_digest(expected_graph_fingerprint):
            raise ValueError("expected_graph_fingerprint must be canonical SHA-256")
        binding = self._bindings.get(key)
        if binding is None:
            return _eligibility(
                key,
                graph_fingerprint=expected_graph_fingerprint,
                origin=ScientificAuthoringGraphOrigin.DRAFT_OR_UNRESOLVED,
                complete=False,
                revoked=False,
            )

        # The external binding is the exact complete node manifest.  Loading
        # every member does not make it reachable: closure and undirected
        # connectivity are checked independently below.
        manifest_refs = (binding.root_ref, *binding.required_refs)
        manifest_set = frozenset(manifest_refs)
        loaded: dict[TopLevelObjectRef, LoadedAuthoringArtifact] = {}
        revoked = False
        try:
            if len(manifest_refs) > _MAX_GRAPH_NODES:
                raise AuthoringHistoryError(
                    "authoring.graph_too_large",
                    "Authoring graph exceeds its bounded node count.",
                )
            for ref in manifest_refs:
                artifact = self._store.get(ref)
                if artifact.expected_ref.challenge_key != key:
                    raise AuthoringHistoryError(
                        "authoring.graph_challenge_mismatch",
                        "Authoring graph contains a cross-Challenge dependency.",
                    )
                loaded[ref] = artifact
                revoked = revoked or self._store.is_revoked(ref)

            root = loaded[binding.root_ref]
            adjacency = {ref: set() for ref in manifest_refs}
            for ref, artifact in loaded.items():
                for dependency_ref in self._dependencies(artifact):
                    if dependency_ref.challenge_key != key:
                        raise AuthoringHistoryError(
                            "authoring.graph_challenge_mismatch",
                            "Authoring graph contains a cross-Challenge dependency.",
                        )
                    if dependency_ref not in manifest_set:
                        raise AuthoringHistoryError(
                            "authoring.graph_manifest_dependency_missing",
                            "Authored dependency is absent from the exact graph manifest.",
                        )
                    adjacency[ref].add(dependency_ref)
                    adjacency[dependency_ref].add(ref)

            reachable = {binding.root_ref}
            pending = [binding.root_ref]
            while pending:
                ref = pending.pop()
                for neighbour in adjacency[ref]:
                    if neighbour not in reachable:
                        reachable.add(neighbour)
                        pending.append(neighbour)
            if reachable != manifest_set:
                raise AuthoringHistoryError(
                    "authoring.graph_manifest_disconnected",
                    "Exact graph manifest contains a disconnected authored node.",
                )
            dependency_refs = binding.required_refs

            # Domain validation is an exact closed dispatcher; it does not
            # delegate scientific truth to the configured A3 provider.
            from .model import validate_loaded_authoring_graph

            objects_by_ref = {
                ref: artifact.authored_object for ref, artifact in loaded.items()
            }
            validate_loaded_authoring_graph(objects_by_ref)
            self._verify_statistics_designs(objects_by_ref)
            self._verify_transient_time_equivalence(objects_by_ref)
            graph = compose_authoring_graph_origin(
                root=root,
                dependencies=tuple(loaded[ref] for ref in dependency_refs),
                expected_dependency_refs=binding.required_refs,
                composition_audit_ref=binding.composition_audit_ref,
                registered_authority=self._registered_authority,
                revoked_refs=tuple(
                    ref for ref in loaded if self._store.is_revoked(ref)
                ),
            )
        except Exception:  # noqa: BLE001 - provider boundary is fail-closed.
            return _eligibility(
                key,
                graph_fingerprint=expected_graph_fingerprint,
                origin=ScientificAuthoringGraphOrigin.DRAFT_OR_UNRESOLVED,
                complete=False,
                revoked=revoked,
            )

        mapped_origin = {
            GraphOriginTag.REGISTERED_GRAPH: (
                ScientificAuthoringGraphOrigin.REGISTERED_GRAPH
            ),
            GraphOriginTag.FIXTURE_DERIVED: (
                ScientificAuthoringGraphOrigin.FIXTURE_DERIVED
            ),
            GraphOriginTag.DRAFT_OR_UNRESOLVED: (
                ScientificAuthoringGraphOrigin.DRAFT_OR_UNRESOLVED
            ),
        }[graph.graph_origin]
        resolved_fingerprint = scientific_authoring_graph_fingerprint(graph)
        if not hmac.compare_digest(
            resolved_fingerprint,
            expected_graph_fingerprint,
        ):
            return _eligibility(
                key,
                graph_fingerprint=resolved_fingerprint,
                origin=ScientificAuthoringGraphOrigin.DRAFT_OR_UNRESOLVED,
                complete=False,
                revoked=revoked,
            )
        return _eligibility(
            key,
            graph_fingerprint=resolved_fingerprint,
            origin=mapped_origin,
            complete=True,
            revoked=revoked,
        )


__all__ = [
    "AuthoringGraphBinding",
    "SciMLTimeEquivalenceAuthority",
    "StatisticsDesignAuthority",
    "StatisticsDesignAuthorization",
    "StatisticsDesignVerification",
    "StatisticsDesignVerificationRequest",
    "StoreBackedScientificAuthoringVerifier",
    "TransientTimeComponent",
    "TransientTimeComponentBinding",
    "TransientTimeEquivalenceRequest",
    "TransientTimeEquivalenceVerification",
    "scientific_authoring_graph_fingerprint",
]
