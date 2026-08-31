"""Exact inert resolved construction plan for B-02B."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import ClassVar

from carbon.authoring.canonical import (
    CanonicalText,
    CanonicalTuple,
    encode_value,
    top_level_ref_from_canonical,
)
from carbon.authoring.errors import AuthoringError, AuthoringValidationError
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_version_token,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    PhysicalSystemSpecRef,
    TrainingSupportContractRef,
    reconstruct_top_level_ref,
)
from carbon.construction import model as m
from carbon.construction.canonical import (
    canonical_record,
    construction_document,
    decode_document,
    from_canonical_value,
    to_canonical_value,
)
from carbon.construction.catalog import (
    _validate_authority_identifiers_with_pin_context,
    _validate_resource_output_identifiers,
)
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    TrainingSamplingPolicyRef,
    make_resolved_ref,
    reconstruct_authored_ref,
    reconstruct_resolved_ref,
    verify_construction_ref,
)
from carbon.fees.strategy_identity import StrategyHash
from carbon.registry import ChallengeKey

_PLAN_FIELDS = (
    "object_kind",
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "strategy_schema_version",
    "strategy_hash",
    "authoring_origin_binding",
    "physical_system_ref",
    "candidate_output_ref",
    "training_support_ref",
    "candidate_assembly_ref",
    "parameter_catalog_ref",
    "compiler_identity",
    "backbone_binding",
    "resolved_surfaces",
    "satisfied_compatibility_rule_ids",
    "resolved_components",
    "training_sampling_policy_ref",
    "dependency_pins",
    "environment_pins",
    "implementation_pins",
    "static_resource_requirements",
    "resource_impact_tags",
    "assembly_provenance",
    "catalog_provenance",
    "authority_marker",
)


def _invalid(code: str, message: str, path: str) -> ConstructionValidationError:
    return ConstructionValidationError(code, message, path=path)


def _challenge_key(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.challenge_key_invalid",
            "challenge_key must be an exact valid A3 ChallengeKey",
            "/challenge_key",
        ) from exc


def _canonical_id(value: object, field: str) -> str:
    try:
        return validate_canonical_id(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.identifier_invalid",
            f"{field} must be an exact canonical identifier",
            f"/{field}",
        ) from exc


def _version(value: object, field: str) -> str:
    try:
        return validate_version_token(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.version_invalid",
            f"{field} must be an exact bounded version token",
            f"/{field}",
        ) from exc


def _copy_model(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.nominal_type_invalid",
            f"{field} must have exact nominal type {expected_type.__name__}",
            f"/{field}",
        )
    return from_canonical_value(to_canonical_value(value), expected_type)


def _copy_union(value: object, allowed: tuple[type, ...], field: str) -> object:
    if type(value) not in allowed:
        raise _invalid(
            "construction.union_type_invalid",
            f"{field} contains an unknown closed variant",
            f"/{field}",
        )
    return _copy_model(value, type(value), field)


def _copy_top_ref(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.authoring_ref_type_invalid",
            f"{field} must use exact nominal type {expected_type.__name__}",
            f"/{field}",
        )
    try:
        result = reconstruct_top_level_ref(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.authoring_ref_invalid",
            f"{field} is not a valid exact B-02A ref",
            f"/{field}",
        ) from exc
    assert type(result) is expected_type
    return result


def _copy_authored_ref(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.reference_type_invalid",
            f"{field} has the wrong exact nominal construction ref type",
            f"/{field}",
        )
    result = reconstruct_authored_ref(value)
    assert type(result) is expected_type
    return result


def _copy_policy_ref(value: object) -> TrainingSamplingPolicyRef:
    if type(value) is not TrainingSamplingPolicyRef:
        raise _invalid(
            "construction.reference_type_invalid",
            "training_sampling_policy_ref has the wrong exact nominal type",
            "/training_sampling_policy_ref",
        )
    result = reconstruct_resolved_ref(value)
    assert type(result) is TrainingSamplingPolicyRef
    return result


def _copy_strategy_hash(value: object) -> StrategyHash:
    if type(value) is not StrategyHash:
        raise _invalid(
            "construction.strategy_hash_type_invalid",
            "strategy_hash must be the exact shared A7 StrategyHash type",
            "/strategy_hash",
        )
    try:
        return StrategyHash(value.value)
    except ValueError as exc:
        raise _invalid(
            "construction.strategy_hash_invalid",
            "strategy_hash must be an exact tagged SHA-256 identity",
            "/strategy_hash",
        ) from exc


def _exact_tuple(value: object, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise _invalid(
            "construction.tuple_type_invalid",
            f"{field} must be an exact built-in tuple",
            f"/{field}",
        )
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid(
            "construction.tuple_size_invalid",
            f"{field} exceeds the canonical item bound",
            f"/{field}",
        )
    return value


def _canonical_key(value: object) -> bytes:
    return encode_value(to_canonical_value(value))


def _canonical_model_tuple(
    value: object,
    expected_type: type,
    field: str,
    *,
    nonempty: bool = False,
) -> tuple:
    raw = _exact_tuple(value, field)
    if nonempty and not raw:
        raise _invalid(
            "construction.tuple_size_invalid",
            f"{field} must not be empty",
            f"/{field}",
        )
    copied = tuple(_copy_model(item, expected_type, field) for item in raw)
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            f"/{field}",
        )
    return tuple(sorted(copied, key=_canonical_key))


def _canonical_union_tuple(
    value: object, allowed: tuple[type, ...], field: str
) -> tuple:
    raw = _exact_tuple(value, field)
    copied = tuple(_copy_union(item, allowed, field) for item in raw)
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            f"/{field}",
        )
    return tuple(sorted(copied, key=_canonical_key))


def _canonical_ids(value: object, field: str) -> tuple[str, ...]:
    copied = tuple(_canonical_id(item, field) for item in _exact_tuple(value, field))
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            f"/{field}",
        )
    return tuple(sorted(copied, key=_canonical_key))


def _ordered_surfaces(value: object) -> tuple[m.ResolvedSurface, ...]:
    allowed = (m.SelectedSurface, m.DefaultedSurface, m.NotApplicableSurface)
    raw = _exact_tuple(value, "resolved_surfaces")
    copied = tuple(_copy_union(item, allowed, "resolved_surfaces") for item in raw)
    surface_ids = tuple(item.surface_id for item in copied)
    if len(set(surface_ids)) != len(surface_ids):
        raise _invalid(
            "construction.resolved_surface_duplicate",
            "resolved surfaces must name unique catalog surface ids",
            "/resolved_surfaces",
        )
    return tuple(sorted(copied, key=lambda item: item.surface_id.encode("ascii")))


def _ordered_components(value: object) -> tuple[m.ResolvedComponentBinding, ...]:
    copied = tuple(
        _copy_model(item, m.ResolvedComponentBinding, "resolved_components")
        for item in _exact_tuple(value, "resolved_components")
    )
    if len({item.slot_id for item in copied}) != len(copied) or len(
        {item.selector_surface_id for item in copied}
    ) != len(copied):
        raise _invalid(
            "construction.resolved_component_duplicate",
            "resolved components must have unique slots and selector surfaces",
            "/resolved_components",
        )
    return tuple(sorted(copied, key=lambda item: item.slot_id.encode("ascii")))


def _validate_pin_ids(pins: tuple, field: str, id_field: str) -> None:
    ids = tuple(getattr(pin, id_field) for pin in pins)
    if len(set(ids)) != len(ids):
        raise _invalid(
            "construction.pin_identity_conflict",
            f"{field} contains multiple pins for one identity",
            f"/{field}",
        )


def _scope(value: object, key: ChallengeKey, *, portable: bool = False) -> None:
    m.validate_owner_ref_scope(
        value,
        expected_challenge_key=key,
        portable=portable,
    )


def _scopes(
    values: tuple[object, ...], key: ChallengeKey, *, portable: bool = False
) -> None:
    for value in values:
        _scope(value, key, portable=portable)


def _validate_provenance_scope(
    provenance: m.ConstructionProvenance, key: ChallengeKey
) -> None:
    if type(provenance) is m.FixtureProvenance:
        _scope(provenance.fixture_registration_ref, key)
    else:
        assert type(provenance) is m.RegisteredProvenance
        _scope(provenance.authoring_registration_ref, key)
    _scopes(provenance.source_provenance_refs, key, portable=True)
    _scopes(provenance.origin_evidence_refs, key, portable=True)


def _validate_scopes(plan: ResolvedConstructionPlan) -> None:
    key = plan.challenge_key
    origin = plan.authoring_origin_binding
    _scopes(origin.origin_evidence_refs, key, portable=True)
    _scope(origin.composition_audit_ref, key, portable=True)
    _scope(plan.backbone_binding.applicability_ref, key)
    _scopes(plan.backbone_binding.assumption_refs, key)
    _scopes(plan.backbone_binding.limitation_refs, key)
    for surface in plan.resolved_surfaces:
        if type(surface) is m.NotApplicableSurface:
            _scope(surface.reason_ref, key)
    for component in plan.resolved_components:
        _scope(component.applicability_ref, key)
        _scopes(component.assumption_refs, key)
        _scopes(component.limitation_refs, key)
        _scopes(component.public_falsification_refs, key)
    for requirement in plan.static_resource_requirements:
        _scope(requirement.unit_ref, key, portable=True)
    _validate_provenance_scope(plan.assembly_provenance, key)
    _validate_provenance_scope(plan.catalog_provenance, key)


def _validate_selector_bindings(plan: ResolvedConstructionPlan) -> None:
    surfaces = {surface.surface_id: surface for surface in plan.resolved_surfaces}
    backbone_surface = surfaces.get("strategy_backbone")
    if (
        type(backbone_surface) is not m.SelectedSurface
        or backbone_surface.value.value_type is not m.SurfaceValueType.BACKBONE_SELECTOR
        or plan.backbone_binding.surface_id != "strategy_backbone"
        or plan.backbone_binding.selector_token != backbone_surface.value.value
    ):
        raise _invalid(
            "construction.backbone_binding_mismatch",
            "strategy_backbone resolution and specialized binding must be exact",
            "/backbone_binding",
        )
    for surface in plan.resolved_surfaces:
        if (
            type(surface) in (m.SelectedSurface, m.DefaultedSurface)
            and surface.value.value_type is m.SurfaceValueType.BACKBONE_SELECTOR
            and surface.surface_id != "strategy_backbone"
        ):
            raise _invalid(
                "construction.backbone_selector_duplicate",
                "only strategy_backbone may carry a backbone selector",
                "/resolved_surfaces",
            )
    component_surfaces = {
        surface.surface_id: surface
        for surface in plan.resolved_surfaces
        if type(surface) in (m.SelectedSurface, m.DefaultedSurface)
        and surface.value.value_type is m.SurfaceValueType.COMPONENT_SELECTOR
    }
    components = {
        component.selector_surface_id: component
        for component in plan.resolved_components
    }
    if set(component_surfaces) != set(components):
        raise _invalid(
            "construction.component_binding_membership_mismatch",
            "component selector resolutions and specialized bindings differ",
            "/resolved_components",
        )
    for surface_id, surface in component_surfaces.items():
        component = components[surface_id]
        if (
            component.selector_token != surface.value.value
            or component.consumer_target != surface.consumer_target
        ):
            raise _invalid(
                "construction.component_binding_mismatch",
                "component selector value or consumer target differs from its binding",
                f"/resolved_components/{surface_id}",
            )


def _validate_plan_graph(plan: ResolvedConstructionPlan) -> None:
    key = plan.challenge_key
    origin_refs = {
        plan.authoring_origin_binding.root_ref,
        *plan.authoring_origin_binding.dependency_refs,
    }
    if any(ref.challenge_key != key for ref in origin_refs):
        raise _invalid(
            "construction.authoring_origin_challenge_mismatch",
            "authoring-origin refs must match the plan ChallengeKey",
            "/authoring_origin_binding",
        )
    if not {
        plan.physical_system_ref,
        plan.candidate_output_ref,
        plan.training_support_ref,
    }.issubset(origin_refs):
        raise _invalid(
            "construction.authoring_origin_membership_mismatch",
            "required B-02A refs are not exact members of the authoring graph",
            "/authoring_origin_binding",
        )


def _validate_complete_pins(plan: ResolvedConstructionPlan) -> None:
    nested_implementations = {
        plan.backbone_binding.implementation_pin,
        *(component.implementation_pin for component in plan.resolved_components),
    }
    if set(plan.implementation_pins) != nested_implementations:
        raise _invalid(
            "construction.implementation_pins_incomplete",
            "implementation_pins must exactly cover all specialized bindings",
            "/implementation_pins",
        )
    nested_environments = {
        plan.backbone_binding.environment_pin,
        *(component.environment_pin for component in plan.resolved_components),
    }
    if not nested_environments.issubset(set(plan.environment_pins)):
        raise _invalid(
            "construction.environment_pins_incomplete",
            "environment_pins omit a specialized binding pin",
            "/environment_pins",
        )
    nested_dependencies = {
        *plan.backbone_binding.dependency_pins,
        *(
            pin
            for component in plan.resolved_components
            for pin in component.dependency_pins
        ),
    }
    if not nested_dependencies.issubset(set(plan.dependency_pins)):
        raise _invalid(
            "construction.dependency_pins_incomplete",
            "dependency_pins omit a specialized binding pin",
            "/dependency_pins",
        )


def _validate_plan_authority_carriers(plan: ResolvedConstructionPlan) -> None:
    identities: list[tuple[str, str]] = [
        (plan.candidate_assembly_ref.object_id, "/candidate_assembly_ref/object_id"),
        (plan.parameter_catalog_ref.object_id, "/parameter_catalog_ref/object_id"),
        (plan.compiler_identity.compiler_id, "/compiler_identity/compiler_id"),
        (plan.backbone_binding.surface_id, "/backbone_binding/surface_id"),
        (plan.backbone_binding.selector_token, "/backbone_binding/selector_token"),
        (plan.backbone_binding.backbone_id, "/backbone_binding/backbone_id"),
        (
            plan.backbone_binding.implementation_pin.implementation_id,
            "/backbone_binding/implementation_pin/implementation_id",
        ),
        (
            plan.backbone_binding.environment_pin.environment_id,
            "/backbone_binding/environment_pin/environment_id",
        ),
        (
            plan.backbone_binding.input_interface_pin.interface_id,
            "/backbone_binding/input_interface_pin/interface_id",
        ),
        (
            plan.backbone_binding.output_interface_pin.interface_id,
            "/backbone_binding/output_interface_pin/interface_id",
        ),
    ]
    identities.extend(
        (pin.dependency_id, "/backbone_binding/dependency_pins/dependency_id")
        for pin in plan.backbone_binding.dependency_pins
    )
    for surface in plan.resolved_surfaces:
        identities.extend(
            (
                (surface.surface_id, "/resolved_surfaces/surface_id"),
                (
                    surface.consumer_target.consumer_id,
                    "/resolved_surfaces/consumer_target/consumer_id",
                ),
                (
                    surface.consumer_target.field_id,
                    "/resolved_surfaces/consumer_target/field_id",
                ),
            )
        )
        if (
            type(surface) in {m.SelectedSurface, m.DefaultedSurface}
            and type(surface.value.value) is str
        ):
            identities.append((surface.value.value, "/resolved_surfaces/value/value"))
    identities.extend(
        (rule_id, "/satisfied_compatibility_rule_ids")
        for rule_id in plan.satisfied_compatibility_rule_ids
    )
    for component in plan.resolved_components:
        identities.extend(
            (
                (component.slot_id, "/resolved_components/slot_id"),
                (
                    component.selector_surface_id,
                    "/resolved_components/selector_surface_id",
                ),
                (component.selector_token, "/resolved_components/selector_token"),
                (component.component_id, "/resolved_components/component_id"),
                (
                    component.consumer_target.consumer_id,
                    "/resolved_components/consumer_target/consumer_id",
                ),
                (
                    component.consumer_target.field_id,
                    "/resolved_components/consumer_target/field_id",
                ),
                (
                    component.implementation_pin.implementation_id,
                    "/resolved_components/implementation_pin/implementation_id",
                ),
                (
                    component.environment_pin.environment_id,
                    "/resolved_components/environment_pin/environment_id",
                ),
                (
                    component.input_interface_pin.interface_id,
                    "/resolved_components/input_interface_pin/interface_id",
                ),
                (
                    component.output_interface_pin.interface_id,
                    "/resolved_components/output_interface_pin/interface_id",
                ),
            )
        )
        identities.extend(
            (pin.dependency_id, "/resolved_components/dependency_pins/dependency_id")
            for pin in component.dependency_pins
        )
    identities.extend(
        (pin.dependency_id, "/dependency_pins/dependency_id")
        for pin in plan.dependency_pins
    )
    identities.extend(
        (pin.environment_id, "/environment_pins/environment_id")
        for pin in plan.environment_pins
    )
    identities.extend(
        (pin.implementation_id, "/implementation_pins/implementation_id")
        for pin in plan.implementation_pins
    )
    for requirement in plan.static_resource_requirements:
        _validate_resource_output_identifiers(
            (requirement.dimension_id, *requirement.impact_tags),
            path="/static_resource_requirements",
        )
        identities.extend(
            (source_id, "/static_resource_requirements/contributing_source_ids")
            for source_id in requirement.contributing_source_ids
        )
    _validate_resource_output_identifiers(
        plan.resource_impact_tags,
        path="/resource_impact_tags",
    )
    _validate_authority_identifiers_with_pin_context(tuple(identities))


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResolvedConstructionPlan:
    """One complete construction result or no result; never a partial plan."""

    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    strategy_schema_version: str
    strategy_hash: StrategyHash
    authoring_origin_binding: m.AuthoringOriginBinding
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    training_support_ref: TrainingSupportContractRef
    candidate_assembly_ref: CandidateAssemblyContractRef
    parameter_catalog_ref: ParameterCatalogRef
    compiler_identity: m.CompilerIdentity
    backbone_binding: m.ResolvedBackboneBinding
    resolved_surfaces: tuple[m.ResolvedSurface, ...]
    satisfied_compatibility_rule_ids: tuple[str, ...]
    resolved_components: tuple[m.ResolvedComponentBinding, ...]
    training_sampling_policy_ref: TrainingSamplingPolicyRef
    dependency_pins: tuple[m.DependencyPin, ...]
    environment_pins: tuple[m.EnvironmentPin, ...]
    implementation_pins: tuple[m.ImplementationPin, ...]
    static_resource_requirements: tuple[m.StaticResourceRequirement, ...]
    resource_impact_tags: tuple[str, ...]
    assembly_provenance: m.ConstructionProvenance
    catalog_provenance: m.ConstructionProvenance
    authority_marker: m.AuthorityMarker

    OBJECT_KIND: ClassVar[str] = "resolved_construction_plan"

    def __post_init__(self) -> None:
        if type(self) is not ResolvedConstructionPlan:
            raise _invalid(
                "construction.subclass_rejected",
                "ResolvedConstructionPlan subclasses are rejected",
                "/type",
            )
        if type(self.object_kind) is not str or self.object_kind != self.OBJECT_KIND:
            raise _invalid(
                "construction.object_kind_invalid",
                "resolved plan has a wrong exact object kind",
                "/object_kind",
            )
        if (
            type(self.schema_version) is not str
            or self.schema_version != CONSTRUCTION_SCHEMA_VERSION
        ):
            raise _invalid(
                "construction.schema_version_unsupported",
                "resolved plan supports only construction schema 1.0",
                "/schema_version",
            )
        if (
            type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != CONSTRUCTION_CANONICALIZATION_PROFILE
        ):
            raise _invalid(
                "construction.canonicalization_profile_invalid",
                "resolved plan uses an unknown canonicalization profile",
                "/canonicalization_profile",
            )
        key = _challenge_key(self.challenge_key)
        strategy_version = _version(
            self.strategy_schema_version, "strategy_schema_version"
        )
        if strategy_version != "1.0":
            raise _invalid(
                "construction.strategy_schema_version_unsupported",
                "B-02B compiles only the accepted Strategy v1.0 envelope",
                "/strategy_schema_version",
            )
        strategy_hash = _copy_strategy_hash(self.strategy_hash)
        origin = _copy_model(
            self.authoring_origin_binding,
            m.AuthoringOriginBinding,
            "authoring_origin_binding",
        )
        physical_ref = _copy_top_ref(
            self.physical_system_ref,
            PhysicalSystemSpecRef,
            "physical_system_ref",
        )
        candidate_ref = _copy_top_ref(
            self.candidate_output_ref,
            CandidateOutputContractRef,
            "candidate_output_ref",
        )
        training_ref = _copy_top_ref(
            self.training_support_ref,
            TrainingSupportContractRef,
            "training_support_ref",
        )
        assembly_ref = _copy_authored_ref(
            self.candidate_assembly_ref,
            CandidateAssemblyContractRef,
            "candidate_assembly_ref",
        )
        catalog_ref = _copy_authored_ref(
            self.parameter_catalog_ref,
            ParameterCatalogRef,
            "parameter_catalog_ref",
        )
        policy_ref = _copy_policy_ref(self.training_sampling_policy_ref)
        refs = (
            physical_ref,
            candidate_ref,
            training_ref,
            assembly_ref,
            catalog_ref,
            policy_ref,
        )
        if any(ref.challenge_key != key for ref in refs):
            raise _invalid(
                "construction.reference_challenge_mismatch",
                "all resolved-plan refs must match its exact ChallengeKey",
                "/challenge_key",
            )
        compiler = _copy_model(
            self.compiler_identity, m.CompilerIdentity, "compiler_identity"
        )
        if (
            compiler.construction_schema_version != self.schema_version
            or compiler.canonicalization_profile != self.canonicalization_profile
        ):
            raise _invalid(
                "construction.compiler_profile_mismatch",
                "compiler identity differs from the resolved-plan profile",
                "/compiler_identity",
            )
        backbone = _copy_model(
            self.backbone_binding, m.ResolvedBackboneBinding, "backbone_binding"
        )
        surfaces = _ordered_surfaces(self.resolved_surfaces)
        satisfied = _canonical_ids(
            self.satisfied_compatibility_rule_ids,
            "satisfied_compatibility_rule_ids",
        )
        components = _ordered_components(self.resolved_components)
        dependencies = _canonical_model_tuple(
            self.dependency_pins, m.DependencyPin, "dependency_pins"
        )
        environments = _canonical_model_tuple(
            self.environment_pins, m.EnvironmentPin, "environment_pins"
        )
        implementations = _canonical_model_tuple(
            self.implementation_pins,
            m.ImplementationPin,
            "implementation_pins",
            nonempty=True,
        )
        resources = _canonical_model_tuple(
            self.static_resource_requirements,
            m.StaticResourceRequirement,
            "static_resource_requirements",
        )
        if len({item.dimension_id for item in resources}) != len(resources):
            raise _invalid(
                "construction.resource_dimension_duplicate",
                "static resource requirements must have unique dimensions",
                "/static_resource_requirements",
            )
        tags = _canonical_ids(self.resource_impact_tags, "resource_impact_tags")
        required_tags = {
            tag for requirement in resources for tag in requirement.impact_tags
        }
        if not required_tags.issubset(set(tags)):
            raise _invalid(
                "construction.resource_impact_tags_incomplete",
                "resource_impact_tags omit an aggregated requirement tag",
                "/resource_impact_tags",
            )
        assembly_provenance = _copy_union(
            self.assembly_provenance,
            (m.FixtureProvenance, m.RegisteredProvenance),
            "assembly_provenance",
        )
        catalog_provenance = _copy_union(
            self.catalog_provenance,
            (m.FixtureProvenance, m.RegisteredProvenance),
            "catalog_provenance",
        )
        if (
            type(self.authority_marker) is not m.AuthorityMarker
            or self.authority_marker
            is not m.AuthorityMarker.CONSTRUCTION_ONLY_NOT_QUALIFICATION
        ):
            raise _invalid(
                "construction.authority_marker_invalid",
                "resolved plan must retain the construction-only authority marker",
                "/authority_marker",
            )
        _validate_pin_ids(dependencies, "dependency_pins", "dependency_id")
        _validate_pin_ids(environments, "environment_pins", "environment_id")
        _validate_pin_ids(implementations, "implementation_pins", "implementation_id")

        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "strategy_schema_version", strategy_version)
        object.__setattr__(self, "strategy_hash", strategy_hash)
        object.__setattr__(self, "authoring_origin_binding", origin)
        object.__setattr__(self, "physical_system_ref", physical_ref)
        object.__setattr__(self, "candidate_output_ref", candidate_ref)
        object.__setattr__(self, "training_support_ref", training_ref)
        object.__setattr__(self, "candidate_assembly_ref", assembly_ref)
        object.__setattr__(self, "parameter_catalog_ref", catalog_ref)
        object.__setattr__(self, "compiler_identity", compiler)
        object.__setattr__(self, "backbone_binding", backbone)
        object.__setattr__(self, "resolved_surfaces", surfaces)
        object.__setattr__(self, "satisfied_compatibility_rule_ids", satisfied)
        object.__setattr__(self, "resolved_components", components)
        object.__setattr__(self, "training_sampling_policy_ref", policy_ref)
        object.__setattr__(self, "dependency_pins", dependencies)
        object.__setattr__(self, "environment_pins", environments)
        object.__setattr__(self, "implementation_pins", implementations)
        object.__setattr__(self, "static_resource_requirements", resources)
        object.__setattr__(self, "resource_impact_tags", tags)
        object.__setattr__(self, "assembly_provenance", assembly_provenance)
        object.__setattr__(self, "catalog_provenance", catalog_provenance)

        _validate_scopes(self)
        _validate_plan_graph(self)
        _validate_selector_bindings(self)
        _validate_complete_pins(self)
        _validate_plan_authority_carriers(self)

    def canonical_bytes(self) -> bytes:
        return resolved_construction_plan_canonical_bytes(self)

    def to_ref(self) -> ResolvedConstructionPlanRef:
        return resolved_construction_plan_to_ref(self)


_VERIFIED_PLANS: weakref.WeakSet = weakref.WeakSet()


def _mark_resolved_construction_plan_verified(
    plan: ResolvedConstructionPlan,
) -> ResolvedConstructionPlan:
    if type(plan) is not ResolvedConstructionPlan:
        raise _invalid(
            "construction.plan_derivation_unverified",
            "only an exact resolved construction plan can be verified",
            "/plan",
        )
    _VERIFIED_PLANS.add(plan)
    return plan


def _require_resolved_construction_plan_verified(
    plan: ResolvedConstructionPlan,
) -> None:
    if plan not in _VERIFIED_PLANS:
        raise _invalid(
            "construction.plan_derivation_unverified",
            "plan identity is available only after compiler or decoder verification",
            "/plan",
        )


def _canonical_tuple(values: tuple[object, ...], *, set_like: bool) -> CanonicalTuple:
    return CanonicalTuple(
        tuple(to_canonical_value(value) for value in values),
        set_like=set_like,
    )


def resolved_construction_plan_canonical_bytes(
    plan: ResolvedConstructionPlan,
) -> bytes:
    """Return complete domain-separated resolved-plan identity bytes."""

    if type(plan) is not ResolvedConstructionPlan:
        raise _invalid(
            "construction.nominal_type_invalid",
            "plan must use the exact ResolvedConstructionPlan type",
            "/plan",
        )
    _require_resolved_construction_plan_verified(plan)
    record = canonical_record(
        plan.OBJECT_KIND,
        (
            ("object_kind", plan.object_kind),
            ("schema_version", plan.schema_version),
            ("canonicalization_profile", plan.canonicalization_profile),
            ("challenge_key", plan.challenge_key),
            ("strategy_schema_version", plan.strategy_schema_version),
            ("strategy_hash", plan.strategy_hash.value),
            ("authoring_origin_binding", plan.authoring_origin_binding),
            ("physical_system_ref", plan.physical_system_ref),
            ("candidate_output_ref", plan.candidate_output_ref),
            ("training_support_ref", plan.training_support_ref),
            ("candidate_assembly_ref", plan.candidate_assembly_ref),
            ("parameter_catalog_ref", plan.parameter_catalog_ref),
            ("compiler_identity", plan.compiler_identity),
            ("backbone_binding", plan.backbone_binding),
            (
                "resolved_surfaces",
                _canonical_tuple(plan.resolved_surfaces, set_like=False),
            ),
            (
                "satisfied_compatibility_rule_ids",
                _canonical_tuple(plan.satisfied_compatibility_rule_ids, set_like=True),
            ),
            (
                "resolved_components",
                _canonical_tuple(plan.resolved_components, set_like=False),
            ),
            ("training_sampling_policy_ref", plan.training_sampling_policy_ref),
            (
                "dependency_pins",
                _canonical_tuple(plan.dependency_pins, set_like=True),
            ),
            (
                "environment_pins",
                _canonical_tuple(plan.environment_pins, set_like=True),
            ),
            (
                "implementation_pins",
                _canonical_tuple(plan.implementation_pins, set_like=True),
            ),
            (
                "static_resource_requirements",
                _canonical_tuple(plan.static_resource_requirements, set_like=False),
            ),
            (
                "resource_impact_tags",
                _canonical_tuple(plan.resource_impact_tags, set_like=True),
            ),
            ("assembly_provenance", plan.assembly_provenance),
            ("catalog_provenance", plan.catalog_provenance),
            ("authority_marker", plan.authority_marker),
        ),
    )
    return construction_document(plan.object_kind, plan.schema_version, record)


def resolved_construction_plan_to_ref(
    plan: ResolvedConstructionPlan,
) -> ResolvedConstructionPlanRef:
    """Derive the exact digest-only reference for one complete plan."""

    result = make_resolved_ref(
        ResolvedConstructionPlanRef,
        canonical_bytes=resolved_construction_plan_canonical_bytes(plan),
        challenge_key=plan.challenge_key,
    )
    assert type(result) is ResolvedConstructionPlanRef
    return result


def _text_field(fields: object, name: str) -> str:
    value = fields.get(name)
    if type(value) is not CanonicalText:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_text_invalid",
            f"{name} must be exact canonical TEXT",
            path=f"/{name}",
        )
    return value.value


def _tuple_field(
    fields: object,
    name: str,
    expected_type: type,
    *,
    set_like: bool,
    union_types: tuple[type, ...] = (),
) -> tuple:
    value = fields.get(name)
    if type(value) is not CanonicalTuple:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_tuple_invalid",
            f"{name} must be an exact canonical tuple",
            path=f"/{name}",
        )
    if union_types:
        result = []
        for item in value.items:
            matches = []
            for candidate in union_types:
                try:
                    matches.append(from_canonical_value(item, candidate))
                except ConstructionCanonicalDecodingError:
                    continue
            if len(matches) != 1:
                raise ConstructionCanonicalDecodingError(
                    "construction.canonical_union_invalid",
                    f"{name} contains an unknown or ambiguous union variant",
                    path=f"/{name}",
                )
            result.append(matches[0])
        return tuple(result)
    return tuple(from_canonical_value(item, expected_type) for item in value.items)


def _string_tuple_field(
    fields: object, name: str, *, set_like: bool
) -> tuple[str, ...]:
    value = fields.get(name)
    if type(value) is not CanonicalTuple:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_tuple_invalid",
            f"{name} must be an exact canonical tuple",
            path=f"/{name}",
        )
    strings = []
    for item in value.items:
        if type(item) is not CanonicalText:
            raise ConstructionCanonicalDecodingError(
                "construction.canonical_text_invalid",
                f"{name} must contain only canonical TEXT",
                path=f"/{name}",
            )
        strings.append(item.value)
    return tuple(strings)


def _decode_top_ref(value: object, expected_type: type, field: str) -> object:
    try:
        result = top_level_ref_from_canonical(value)
    except AuthoringError as exc:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_authoring_ref_invalid",
            f"{field} is malformed",
            path=f"/{field}",
        ) from exc
    if type(result) is not expected_type:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_authoring_ref_type_invalid",
            f"{field} has the wrong exact nominal type",
            path=f"/{field}",
        )
    return result


def decode_resolved_construction_plan(
    payload: object,
    *,
    expected_ref: object,
) -> ResolvedConstructionPlan:
    """Decode and digest-verify one exact complete plan before returning it."""

    if type(expected_ref) is not ResolvedConstructionPlanRef:
        raise ConstructionReferenceMismatchError(
            "construction.reference_type_mismatch",
            "expected_ref must be an exact ResolvedConstructionPlanRef",
        )
    decoded = decode_document(
        payload,
        expected_object_kind=ResolvedConstructionPlan.OBJECT_KIND,
        expected_schema_version=CONSTRUCTION_SCHEMA_VERSION,
        allowed_record_fields=_PLAN_FIELDS,
    )
    fields = decoded.record.field_map()
    try:
        strategy_hash = StrategyHash(_text_field(fields, "strategy_hash"))
    except ValueError as exc:
        raise ConstructionCanonicalDecodingError(
            "construction.strategy_hash_invalid",
            "strategy_hash is not an exact shared A7 identity",
            path="/strategy_hash",
        ) from exc
    plan = ResolvedConstructionPlan(
        object_kind=_text_field(fields, "object_kind"),
        schema_version=_text_field(fields, "schema_version"),
        canonicalization_profile=_text_field(fields, "canonicalization_profile"),
        challenge_key=from_canonical_value(fields["challenge_key"], ChallengeKey),
        strategy_schema_version=_text_field(fields, "strategy_schema_version"),
        strategy_hash=strategy_hash,
        authoring_origin_binding=from_canonical_value(
            fields["authoring_origin_binding"], m.AuthoringOriginBinding
        ),
        physical_system_ref=_decode_top_ref(
            fields["physical_system_ref"],
            PhysicalSystemSpecRef,
            "physical_system_ref",
        ),
        candidate_output_ref=_decode_top_ref(
            fields["candidate_output_ref"],
            CandidateOutputContractRef,
            "candidate_output_ref",
        ),
        training_support_ref=_decode_top_ref(
            fields["training_support_ref"],
            TrainingSupportContractRef,
            "training_support_ref",
        ),
        candidate_assembly_ref=from_canonical_value(
            fields["candidate_assembly_ref"], CandidateAssemblyContractRef
        ),
        parameter_catalog_ref=from_canonical_value(
            fields["parameter_catalog_ref"], ParameterCatalogRef
        ),
        compiler_identity=from_canonical_value(
            fields["compiler_identity"], m.CompilerIdentity
        ),
        backbone_binding=from_canonical_value(
            fields["backbone_binding"], m.ResolvedBackboneBinding
        ),
        resolved_surfaces=_tuple_field(
            fields,
            "resolved_surfaces",
            object,
            set_like=False,
            union_types=(
                m.SelectedSurface,
                m.DefaultedSurface,
                m.NotApplicableSurface,
            ),
        ),
        satisfied_compatibility_rule_ids=_string_tuple_field(
            fields, "satisfied_compatibility_rule_ids", set_like=True
        ),
        resolved_components=_tuple_field(
            fields,
            "resolved_components",
            m.ResolvedComponentBinding,
            set_like=False,
        ),
        training_sampling_policy_ref=from_canonical_value(
            fields["training_sampling_policy_ref"], TrainingSamplingPolicyRef
        ),
        dependency_pins=_tuple_field(
            fields, "dependency_pins", m.DependencyPin, set_like=True
        ),
        environment_pins=_tuple_field(
            fields, "environment_pins", m.EnvironmentPin, set_like=True
        ),
        implementation_pins=_tuple_field(
            fields, "implementation_pins", m.ImplementationPin, set_like=True
        ),
        static_resource_requirements=_tuple_field(
            fields,
            "static_resource_requirements",
            m.StaticResourceRequirement,
            set_like=False,
        ),
        resource_impact_tags=_string_tuple_field(
            fields, "resource_impact_tags", set_like=True
        ),
        assembly_provenance=_decode_provenance(fields["assembly_provenance"]),
        catalog_provenance=_decode_provenance(fields["catalog_provenance"]),
        authority_marker=_enum_field(fields, "authority_marker", m.AuthorityMarker),
    )
    _mark_resolved_construction_plan_verified(plan)
    if type(payload) is not bytes or plan.canonical_bytes() != payload:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_document_noncanonical",
            "resolved-plan fields are not in their unique canonical order",
        )
    verify_construction_ref(
        expected_ref,
        canonical_bytes=payload,
        challenge_key=plan.challenge_key,
    )
    return plan


def _decode_provenance(value: object) -> m.ConstructionProvenance:
    matches = []
    for expected in (m.FixtureProvenance, m.RegisteredProvenance):
        try:
            matches.append(from_canonical_value(value, expected))
        except ConstructionCanonicalDecodingError:
            continue
    if len(matches) != 1:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_provenance_invalid",
            "construction provenance has an unknown or ambiguous variant",
        )
    return matches[0]


def _enum_field(fields: object, name: str, enum_type: type) -> object:
    value = fields.get(name)
    if type(value) is not CanonicalText:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_enum_invalid",
            f"{name} must be exact canonical TEXT",
            path=f"/{name}",
        )
    try:
        return enum_type(value.value)
    except ValueError as exc:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_enum_invalid",
            f"{name} contains an unknown closed literal",
            path=f"/{name}",
        ) from exc


decode_construction_plan = decode_resolved_construction_plan


__all__ = [
    "ResolvedConstructionPlan",
    "decode_construction_plan",
    "decode_resolved_construction_plan",
    "resolved_construction_plan_canonical_bytes",
    "resolved_construction_plan_to_ref",
]
