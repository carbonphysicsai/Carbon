"""Deterministic fail-closed compiler from Strategy v1 to inert construction data."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TypeAlias

from carbon.authoring.errors import AuthoringError
from carbon.authoring.loading import (
    AuthoringGraphOrigin,
    FixtureOrigin,
    GraphOriginTag,
    LoadedAuthoringArtifact,
    RegisteredOrigin,
)
from carbon.authoring.primitives import reconstruct_challenge_key
from carbon.construction import model as m
from carbon.construction.canonical import encode_model
from carbon.construction.catalog import (
    CandidateAssemblyContract,
    ParameterCatalog,
    validate_candidate_assembly,
    validate_parameter_catalog,
)
from carbon.construction.errors import ConstructionError
from carbon.construction.plan import (
    ResolvedConstructionPlan,
    _mark_resolved_construction_plan_verified,
)
from carbon.construction.policy import _build_training_sampling_policy
from carbon.construction.refs import (
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    verify_construction_ref,
)
from carbon.fees.strategy_identity import (
    StrategyHash,
    SubmissionResourceLimits,
    identify_strategy,
)
from carbon.registry import ChallengeKey

_UINT64_MAX = (1 << 64) - 1
_SAFE_PATH = re.compile(
    r"/(?:[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*(?:/[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*)*)?\Z",
    re.ASCII,
)


SUPPORTED_COMPILER_IDENTITY = m.CompilerIdentity(
    compiler_id="carbon_strategy_compiler",
    compiler_version="1.0",
    implementation_digest=(
        "sha256:53cb3ec840eb756e61f55bb5edd7d872" "1fae2624942b5199a96ed0bccb63c827"
    ),
    construction_schema_version="1.0",
    canonicalization_profile="carbon_construction_canonical_v1",
)

COMPILE_ISSUE_CODES = (
    "strategy.invalid",
    "strategy.identity_invalid",
    "strategy.challenge_mismatch",
    "strategy.backbone_mismatch",
    "strategy.parameter_shape_invalid",
    "strategy.negative_zero",
    "reference.type_mismatch",
    "reference.kind_mismatch",
    "reference.challenge_mismatch",
    "reference.schema_mismatch",
    "reference.version_mismatch",
    "reference.digest_mismatch",
    "reference.pin_mismatch",
    "reference.retired_for_new_compilation",
    "compiler.identity_mismatch",
    "compiler.version_unsupported",
    "catalog.duplicate_surface",
    "catalog.consumer_collision",
    "catalog.selector_collision",
    "catalog.rule_invalid",
    "catalog.dependency_cycle",
    "parameter.unknown",
    "parameter.unused",
    "parameter.missing_required",
    "parameter.type_mismatch",
    "parameter.bool_int_confusion",
    "parameter.domain_mismatch",
    "parameter.coercion_forbidden",
    "parameter.default_invalid",
    "parameter.not_applicable",
    "parameter.dependency_unsatisfied",
    "parameter.unsupported_combination",
    "component.unknown",
    "component.role_confusion",
    "component.interface_mismatch",
    "component.pin_mismatch",
    "component.fallback_forbidden",
    "component.graph_forbidden",
    "training_support.mismatch",
    "training_policy.binding_invalid",
    "training_policy.forbidden_authority",
    "training_policy.randomness_forbidden",
    "resource.dimension_unknown",
    "resource.unit_conflict",
    "resource.lookup_missing",
    "resource.overflow",
    "resource.policy_forbidden",
    "authority.origin_invalid",
    "capability.forbidden",
    "canonicalization.failed",
    "compile.internal_failure",
)

_ISSUE_MESSAGES = {
    "strategy.invalid": "Strategy v1 validation failed.",
    "strategy.identity_invalid": "Strategy identity could not be established.",
    "strategy.challenge_mismatch": "Strategy and Challenge family differ.",
    "strategy.backbone_mismatch": "Strategy backbone is not registered by the assembly.",
    "strategy.parameter_shape_invalid": "Strategy parameters are not one flat scalar map.",
    "strategy.negative_zero": "Negative zero is forbidden by construction identity.",
    "reference.type_mismatch": "A trusted input has the wrong exact reference type.",
    "reference.kind_mismatch": "A trusted input has the wrong reference kind.",
    "reference.challenge_mismatch": "A trusted reference crosses Challenge versions.",
    "reference.schema_mismatch": "A trusted reference uses a different schema.",
    "reference.version_mismatch": "A trusted reference uses a different exact version.",
    "reference.digest_mismatch": "A trusted reference digest does not match its bytes.",
    "reference.pin_mismatch": "A trusted dependency or pin does not match exactly.",
    "reference.retired_for_new_compilation": "A retired surface cannot enter new compilation.",
    "compiler.identity_mismatch": "Compiler identity differs from the catalog binding.",
    "compiler.version_unsupported": "Compiler version is not supported by this implementation.",
    "catalog.duplicate_surface": "Catalog contains a duplicate semantic surface.",
    "catalog.consumer_collision": "Catalog maps multiple surfaces to one consumer target.",
    "catalog.selector_collision": "Catalog selector projection is ambiguous.",
    "catalog.rule_invalid": "Catalog compatibility rules are invalid.",
    "catalog.dependency_cycle": "Catalog dependency graph is cyclic.",
    "parameter.unknown": "Strategy contains a parameter outside the exact catalog.",
    "parameter.unused": "Strategy contains a parameter with no active consumer.",
    "parameter.missing_required": "An applicable required parameter is missing.",
    "parameter.type_mismatch": "A parameter has the wrong exact scalar type.",
    "parameter.bool_int_confusion": "Boolean and integer parameter types are distinct.",
    "parameter.domain_mismatch": "A parameter is outside its exact catalog domain.",
    "parameter.coercion_forbidden": "Parameter coercion is forbidden.",
    "parameter.default_invalid": "An explicit catalog default is invalid.",
    "parameter.not_applicable": "Strategy supplies a parameter that is not applicable.",
    "parameter.dependency_unsatisfied": "An applicable parameter dependency is unsatisfied.",
    "parameter.unsupported_combination": "Resolved parameters violate a closed compatibility table.",
    "component.unknown": "A selected component is not registered in its exact slot.",
    "component.role_confusion": "A component role differs from its owning slot.",
    "component.interface_mismatch": "A component interface differs from its owning slot.",
    "component.pin_mismatch": "A component pin differs from its assembly declaration.",
    "component.fallback_forbidden": "Component fallback is forbidden in construction v1.",
    "component.graph_forbidden": "Participant-defined component graphs are forbidden.",
    "training_support.mismatch": "Training policy and assembly use different support contracts.",
    "training_policy.binding_invalid": "Resolved training bindings are incomplete or invalid.",
    "training_policy.forbidden_authority": "Training policy contains forbidden evaluation authority.",
    "training_policy.randomness_forbidden": "Training policy contains realized randomness authority.",
    "resource.dimension_unknown": "A resource contribution uses an unknown dimension.",
    "resource.unit_conflict": "A resource contribution uses a conflicting unit.",
    "resource.lookup_missing": "A resource lookup has no exact resolved case.",
    "resource.overflow": "Static resource aggregation overflows UInt64.",
    "resource.policy_forbidden": "Resource-policy authority is forbidden in construction.",
    "authority.origin_invalid": "Scientific authoring origin is incomplete or unresolved.",
    "capability.forbidden": "A participant capability is forbidden at compilation.",
    "canonicalization.failed": "Canonical construction identity could not be materialized.",
    "compile.internal_failure": "Compilation failed closed.",
}


@dataclass(frozen=True, slots=True)
class CompileIssue:
    """One exact non-echoing compiler rejection issue."""

    code: str
    path: str
    message: str

    def __post_init__(self) -> None:
        if type(self) is not CompileIssue:
            raise TypeError("CompileIssue subclasses are rejected")
        if type(self.code) is not str or self.code not in COMPILE_ISSUE_CODES:
            raise ValueError("compile issue code is outside the closed v1 registry")
        if type(self.path) is not str or _SAFE_PATH.fullmatch(self.path) is None:
            raise ValueError("compile issue path is not a safe canonical path")
        if type(self.message) is not str or self.message != _ISSUE_MESSAGES[self.code]:
            raise ValueError("compile issue message must be the fixed v1 text")


@dataclass(frozen=True, slots=True)
class CompileRejected:
    """Fail-closed result containing no policy or partial plan."""

    issues: tuple[CompileIssue, ...]

    def __post_init__(self) -> None:
        if type(self) is not CompileRejected:
            raise TypeError("CompileRejected subclasses are rejected")
        if type(self.issues) is not tuple or not self.issues:
            raise ValueError("CompileRejected requires a nonempty exact tuple")
        if any(type(issue) is not CompileIssue for issue in self.issues):
            raise TypeError("CompileRejected issues must have exact nominal type")
        ordered = tuple(sorted(self.issues, key=lambda issue: (issue.path, issue.code)))
        if len(set(ordered)) != len(ordered):
            raise ValueError("CompileRejected issues must be unique")
        object.__setattr__(self, "issues", ordered)


@dataclass(frozen=True, slots=True)
class CompileAccepted:
    """Complete compiler result; no field is optional or caller-owned."""

    training_policy: object
    training_policy_ref: object
    construction_plan: ResolvedConstructionPlan
    construction_plan_ref: object

    def __post_init__(self) -> None:
        from carbon.construction.policy import ResolvedTrainingSamplingPolicy
        from carbon.construction.refs import (
            ResolvedConstructionPlanRef,
            TrainingSamplingPolicyRef,
        )

        if type(self) is not CompileAccepted:
            raise TypeError("CompileAccepted subclasses are rejected")
        if type(self.training_policy) is not ResolvedTrainingSamplingPolicy:
            raise TypeError("training_policy has a wrong exact nominal type")
        if type(self.training_policy_ref) is not TrainingSamplingPolicyRef:
            raise TypeError("training_policy_ref has a wrong exact nominal type")
        if type(self.construction_plan) is not ResolvedConstructionPlan:
            raise TypeError("construction_plan has a wrong exact nominal type")
        if type(self.construction_plan_ref) is not ResolvedConstructionPlanRef:
            raise TypeError("construction_plan_ref has a wrong exact nominal type")
        if self.training_policy.to_ref() != self.training_policy_ref:
            raise ValueError("training policy and reference must have exact identity")
        if self.construction_plan.to_ref() != self.construction_plan_ref:
            raise ValueError("construction plan and reference must have exact identity")
        if (
            self.construction_plan.training_sampling_policy_ref
            != self.training_policy_ref
            or self.construction_plan.parameter_catalog_ref
            != self.training_policy.catalog_ref
            or self.construction_plan.training_support_ref
            != self.training_policy.training_support_ref
        ):
            raise ValueError("accepted policy and plan must be mutually bound")
        challenge_keys = {
            self.training_policy.challenge_key,
            self.training_policy_ref.challenge_key,
            self.construction_plan.challenge_key,
            self.construction_plan_ref.challenge_key,
        }
        if len(challenge_keys) != 1:
            raise ValueError("accepted outputs must share one exact ChallengeKey")


CompileResult: TypeAlias = CompileAccepted | CompileRejected


class _CompileFailure(RuntimeError):
    def __init__(self, *issues: CompileIssue) -> None:
        self.issues = issues
        super().__init__("compilation rejected")


def _issue(code: str, path: str) -> CompileIssue:
    return CompileIssue(code, path, _ISSUE_MESSAGES[code])


def _fail(code: str, path: str) -> None:
    raise _CompileFailure(_issue(code, path))


def _map_catalog_error(exc: ConstructionError) -> None:
    code = exc.code
    if code == "construction.training_owner_mismatch":
        _fail("training_policy.binding_invalid", "/entries")
    if code == "construction.training_randomness_authority_forbidden":
        _fail("training_policy.randomness_forbidden", "/entries")
    if code == "construction.resource_policy_authority_forbidden":
        _fail("resource.policy_forbidden", "/entries")
    if code == "construction.component_graph_authority_forbidden":
        _fail("component.graph_forbidden", "/entries")
    if code == "construction.capability_authority_forbidden":
        _fail("capability.forbidden", "/entries")
    if code == "construction.scientific_authority_forbidden":
        _fail("training_policy.forbidden_authority", "/entries")
    if "duplicate" in code and "surface" in code:
        _fail("catalog.duplicate_surface", "/entries")
    if "consumer" in code:
        _fail("catalog.consumer_collision", "/entries")
    if "selector" in code:
        _fail("catalog.selector_collision", "/entries")
    if "cycle" in code or "dependency" in code:
        _fail("catalog.dependency_cycle", "/entries")
    if "retired" in code:
        _fail("reference.retired_for_new_compilation", "/entries")
    if "rule" in code or "compatibility" in code:
        _fail("catalog.rule_invalid", "/compatibility_rules")
    _fail("reference.pin_mismatch", "/parameter_catalog")


def _verify_authored_ref(
    provided: object,
    actual: object,
    expected_type: type,
    path: str,
) -> None:
    if type(provided) is not expected_type:
        _fail("reference.type_mismatch", path)
    if type(actual) is not expected_type:
        _fail("reference.kind_mismatch", path)
    if provided.challenge_key != actual.challenge_key:
        _fail("reference.challenge_mismatch", path)
    if (
        provided.schema_version != actual.schema_version
        or provided.canonicalization_profile != actual.canonicalization_profile
    ):
        _fail("reference.schema_mismatch", path)
    if (
        provided.object_id != actual.object_id
        or provided.object_version != actual.object_version
    ):
        _fail("reference.version_mismatch", path)
    if provided.content_digest != actual.content_digest:
        _fail("reference.digest_mismatch", path)


def _verify_inputs(
    *,
    challenge_key: object,
    candidate_assembly: object,
    candidate_assembly_ref: object,
    parameter_catalog: object,
    parameter_catalog_ref: object,
    authoring_origin: object,
    authoring_artifacts: object,
    compiler_identity: object,
) -> tuple[
    ChallengeKey,
    CandidateAssemblyContract,
    CandidateAssemblyContractRef,
    ParameterCatalog,
    ParameterCatalogRef,
    m.AuthoringOriginBinding,
]:
    if type(challenge_key) is not ChallengeKey:
        _fail("reference.type_mismatch", "/challenge_key")
    try:
        key = reconstruct_challenge_key(challenge_key)
    except AuthoringError:
        _fail("reference.type_mismatch", "/challenge_key")

    if type(candidate_assembly) is not CandidateAssemblyContract:
        _fail("reference.type_mismatch", "/candidate_assembly")
    if type(parameter_catalog) is not ParameterCatalog:
        _fail("reference.type_mismatch", "/parameter_catalog")
    assembly = candidate_assembly
    catalog = parameter_catalog
    if assembly.challenge_key != key or catalog.challenge_key != key:
        _fail("reference.challenge_mismatch", "/challenge_key")

    if type(compiler_identity) is not m.CompilerIdentity:
        _fail("reference.type_mismatch", "/compiler_identity")
    if (
        compiler_identity.compiler_version
        != SUPPORTED_COMPILER_IDENTITY.compiler_version
    ):
        _fail("compiler.version_unsupported", "/compiler_identity")
    if compiler_identity != SUPPORTED_COMPILER_IDENTITY:
        _fail("compiler.identity_mismatch", "/compiler_identity")
    if catalog.compiler_identity != compiler_identity:
        _fail("compiler.identity_mismatch", "/parameter_catalog")

    try:
        validate_candidate_assembly(assembly)
        validate_parameter_catalog(
            catalog,
            candidate_assembly=assembly,
            expected_compiler_identity=compiler_identity,
            reject_retired=True,
        )
        actual_assembly_ref = assembly.to_ref()
        actual_catalog_ref = catalog.to_ref(candidate_assembly=assembly)
    except ConstructionError as exc:
        _map_catalog_error(exc)

    _verify_authored_ref(
        candidate_assembly_ref,
        actual_assembly_ref,
        CandidateAssemblyContractRef,
        "/candidate_assembly_ref",
    )
    _verify_authored_ref(
        parameter_catalog_ref,
        actual_catalog_ref,
        ParameterCatalogRef,
        "/parameter_catalog_ref",
    )
    try:
        verify_construction_ref(
            candidate_assembly_ref,
            canonical_bytes=assembly.canonical_bytes(),
            challenge_key=key,
            object_id=assembly.object_id,
            object_version=assembly.object_version,
        )
        verify_construction_ref(
            parameter_catalog_ref,
            canonical_bytes=catalog.canonical_bytes(candidate_assembly=assembly),
            challenge_key=key,
            object_id=catalog.object_id,
            object_version=catalog.object_version,
        )
    except ConstructionError:
        _fail("reference.digest_mismatch", "/parameter_catalog_ref")
    if catalog.candidate_assembly_ref != candidate_assembly_ref:
        _fail("reference.pin_mismatch", "/candidate_assembly_ref")
    if catalog.training_support_ref != assembly.training_support_ref:
        _fail("training_support.mismatch", "/training_support_ref")

    if type(authoring_origin) is not AuthoringGraphOrigin:
        _fail("authority.origin_invalid", "/authoring_origin")
    if type(authoring_artifacts) is not tuple or any(
        type(item) is not LoadedAuthoringArtifact for item in authoring_artifacts
    ):
        _fail("authority.origin_invalid", "/authoring_artifacts")
    origin = authoring_origin
    expected_refs = (origin.root_ref, *origin.dependency_refs)
    artifact_refs = tuple(item.expected_ref for item in authoring_artifacts)
    artifact_evidence_refs = tuple(
        item.origin_evidence_ref for item in authoring_artifacts
    )
    if (
        len(set(expected_refs)) != len(expected_refs)
        or len(set(artifact_refs)) != len(artifact_refs)
        or set(artifact_refs) != set(expected_refs)
        or any(item.expected_ref != item.recomputed_ref for item in authoring_artifacts)
        or len(set(artifact_evidence_refs)) != len(artifact_evidence_refs)
        or set(artifact_evidence_refs) != set(origin.origin_evidence_refs)
    ):
        _fail("authority.origin_invalid", "/authoring_artifacts")
    artifact_origins = tuple(item.origin for item in authoring_artifacts)
    contains_fixture = any(type(item) is FixtureOrigin for item in artifact_origins)
    if (
        type(origin.graph_origin) is not GraphOriginTag
        or contains_fixture
        and origin.graph_origin is not GraphOriginTag.FIXTURE_DERIVED
        or origin.graph_origin is GraphOriginTag.FIXTURE_DERIVED
        and not contains_fixture
        or origin.graph_origin is GraphOriginTag.REGISTERED_GRAPH
        and any(type(item) is not RegisteredOrigin for item in artifact_origins)
    ):
        _fail("authority.origin_invalid", "/authoring_origin")
    if origin.root_ref.challenge_key != key or any(
        ref.challenge_key != key for ref in origin.dependency_refs
    ):
        _fail("reference.challenge_mismatch", "/authoring_origin")
    required_authoring_refs = (
        assembly.physical_system_ref,
        assembly.candidate_output_ref,
        assembly.training_support_ref,
    )
    if any(ref not in set(expected_refs) for ref in required_authoring_refs):
        _fail("reference.pin_mismatch", "/authoring_origin")
    try:
        origin_binding = m.AuthoringOriginBinding.from_capability(origin)
    except (AuthoringError, ConstructionError, TypeError, ValueError):
        _fail("authority.origin_invalid", "/authoring_origin")
    return (
        key,
        assembly,
        candidate_assembly_ref,
        catalog,
        parameter_catalog_ref,
        origin_binding,
    )


def _domain_contains(domain: m.SurfaceDomain, value: m.SurfaceValue) -> bool:
    if type(domain) is m.BooleanDomain:
        return (
            value.value_type is m.SurfaceValueType.BOOL
            and value.value in domain.allowed_values
        )
    if type(domain) is m.Int64RangeDomain:
        return (
            value.value_type is m.SurfaceValueType.INT64
            and domain.minimum <= value.value <= domain.maximum
        )
    if type(domain) is m.UInt64RangeDomain:
        return (
            value.value_type is m.SurfaceValueType.UINT64
            and domain.minimum <= value.value <= domain.maximum
        )
    if type(domain) is m.Float64RangeDomain:
        if value.value_type is not m.SurfaceValueType.FLOAT64:
            return False
        lower = (
            value.value >= domain.minimum
            if domain.lower_inclusive
            else value.value > domain.minimum
        )
        upper = (
            value.value <= domain.maximum
            if domain.upper_inclusive
            else value.value < domain.maximum
        )
        return lower and upper
    if type(domain) is m.ChoiceDomain:
        return (
            value.value_type
            in {
                m.SurfaceValueType.CANONICAL_CHOICE,
                m.SurfaceValueType.BACKBONE_SELECTOR,
                m.SurfaceValueType.COMPONENT_SELECTOR,
            }
            and value.value in domain.allowed_ids
        )
    return False


def _surface_value(entry: m.ParameterCatalogEntry, raw: object) -> m.SurfaceValue:
    path = f"/parameters/{entry.surface_id}"
    expected = entry.value_type
    raw_type = type(raw)
    if raw_type is float and raw == 0.0 and math.copysign(1.0, raw) < 0.0:
        _fail("strategy.negative_zero", path)
    if expected is m.SurfaceValueType.BOOL:
        if raw_type is int:
            _fail("parameter.bool_int_confusion", path)
        if raw_type is not bool:
            _fail("parameter.type_mismatch", path)
    elif expected in {m.SurfaceValueType.INT64, m.SurfaceValueType.UINT64}:
        if raw_type is bool:
            _fail("parameter.bool_int_confusion", path)
        if raw_type is float:
            _fail("parameter.coercion_forbidden", path)
        if raw_type is not int:
            _fail("parameter.type_mismatch", path)
    elif expected is m.SurfaceValueType.FLOAT64:
        if raw_type is bool:
            _fail("parameter.bool_int_confusion", path)
        if raw_type is int:
            _fail("parameter.coercion_forbidden", path)
        if raw_type is not float:
            _fail("parameter.type_mismatch", path)
    else:
        if raw_type is not str:
            _fail("parameter.type_mismatch", path)
    try:
        value = m.SurfaceValue(expected, raw)
    except ConstructionError:
        _fail("parameter.domain_mismatch", path)
    if not _domain_contains(entry.domain, value):
        _fail("parameter.domain_mismatch", path)
    return value


def _topological_entries(
    entries: tuple[m.ParameterCatalogEntry, ...],
) -> tuple[m.ParameterCatalogEntry, ...]:
    by_surface = {entry.surface_id: entry for entry in entries}
    remaining = dict(by_surface)
    ordered: list[m.ParameterCatalogEntry] = []
    resolved: set[str] = set()
    while remaining:
        ready = tuple(
            sorted(
                (
                    entry
                    for entry in remaining.values()
                    if set(entry.dependency_surface_ids) <= resolved
                ),
                key=lambda item: item.surface_id,
            )
        )
        if not ready:
            _fail("catalog.dependency_cycle", "/entries")
        for entry in ready:
            ordered.append(entry)
            resolved.add(entry.surface_id)
            del remaining[entry.surface_id]
    return tuple(ordered)


def _is_applicable(
    entry: m.ParameterCatalogEntry,
    resolved: dict[str, m.ResolvedSurface],
) -> bool:
    if type(entry.applicability) is m.AlwaysApplicable:
        return True
    if type(entry.applicability) is not m.WhenSurfaceIn:
        _fail("catalog.rule_invalid", "/entries")
    controller = resolved.get(entry.applicability.selector_surface_id)
    if controller is None:
        _fail("parameter.dependency_unsatisfied", f"/parameters/{entry.surface_id}")
    if type(controller) is m.NotApplicableSurface:
        return False
    return controller.value in entry.applicability.allowed_values


def _resolve_surfaces(
    *,
    snapshot: dict[str, object],
    catalog: ParameterCatalog,
) -> tuple[tuple[m.ResolvedSurface, ...], tuple[str, ...]]:
    parameters = snapshot.get("parameters")
    if type(parameters) is not dict or any(type(key) is not str for key in parameters):
        _fail("strategy.parameter_shape_invalid", "/parameters")
    if any(type(value) not in {bool, int, float, str} for value in parameters.values()):
        _fail("strategy.parameter_shape_invalid", "/parameters")

    entries = catalog.entries
    by_surface = {entry.surface_id: entry for entry in entries}
    parameter_entries = {
        entry.surface_id
        for entry in entries
        if entry.input_source is m.InputSource.PARAMETER_KEY
    }
    if any(key not in parameter_entries for key in parameters):
        _fail("parameter.unknown", "/parameters")

    backbone = snapshot.get("backbone")
    resolved: dict[str, m.ResolvedSurface] = {}
    consumed: set[str] = set()
    for entry in _topological_entries(entries):
        path = f"/parameters/{entry.surface_id}"
        applicable = _is_applicable(entry, resolved)
        if not applicable:
            if entry.surface_id in parameters:
                _fail("parameter.not_applicable", path)
            if type(entry.applicability) is not m.WhenSurfaceIn:
                _fail("catalog.rule_invalid", "/entries")
            resolved[entry.surface_id] = m.NotApplicableSurface(
                entry.surface_id,
                entry.consumer_target,
                entry.applicability.not_applicable_reason_ref,
            )
            continue
        if any(
            type(resolved[dependency]) is m.NotApplicableSurface
            for dependency in entry.dependency_surface_ids
            if dependency in resolved
        ):
            _fail("parameter.dependency_unsatisfied", path)

        if entry.input_source is m.InputSource.TOP_LEVEL_BACKBONE:
            if (
                type(entry.domain) is m.ChoiceDomain
                and type(backbone) is str
                and backbone not in entry.domain.allowed_ids
            ):
                _fail("strategy.backbone_mismatch", "/backbone")
            value = _surface_value(entry, backbone)
            resolved[entry.surface_id] = m.SelectedSurface(
                entry.surface_id,
                entry.consumer_target,
                value,
            )
            continue
        if entry.surface_id in parameters:
            raw_value = parameters[entry.surface_id]
            if (
                entry.value_type is m.SurfaceValueType.COMPONENT_SELECTOR
                and type(entry.component_slot_binding) is m.BoundComponentSelection
                and type(entry.domain) is m.ChoiceDomain
                and type(raw_value) is str
                and raw_value not in entry.domain.allowed_ids
            ):
                _fail(
                    "component.unknown",
                    f"/components/{entry.component_slot_binding.slot_id}",
                )
            value = _surface_value(entry, raw_value)
            consumed.add(entry.surface_id)
            resolved[entry.surface_id] = m.SelectedSurface(
                entry.surface_id,
                entry.consumer_target,
                value,
            )
        elif type(entry.requirement) is m.ExplicitDefaultSurface:
            default = entry.requirement.default_value
            if not _domain_contains(entry.domain, default):
                _fail("parameter.default_invalid", path)
            resolved[entry.surface_id] = m.DefaultedSurface(
                entry.surface_id,
                entry.consumer_target,
                default,
            )
        elif type(entry.requirement) is m.RequiredSurface:
            _fail("parameter.missing_required", path)
        else:
            _fail("catalog.rule_invalid", "/entries")

    if consumed != set(parameters):
        _fail("parameter.unused", "/parameters")
    exact = tuple(
        resolved[entry.surface_id]
        for entry in sorted(entries, key=lambda item: item.surface_id)
    )
    return exact, tuple(sorted(by_surface))


def _compatibility(
    catalog: ParameterCatalog,
    surfaces: tuple[m.ResolvedSurface, ...],
) -> tuple[str, ...]:
    resolved = {surface.surface_id: surface for surface in surfaces}
    satisfied: list[str] = []
    for rule in sorted(catalog.compatibility_rules, key=lambda item: item.rule_id):
        row: tuple[m.CompatibilityCell, ...] = tuple(
            (
                m.NotApplicableCompatibilityCell()
                if type(resolved[surface_id]) is m.NotApplicableSurface
                else m.ValueCompatibilityCell(resolved[surface_id].value)
            )
            for surface_id in rule.surface_ids
        )
        if row not in rule.allowed_rows:
            _fail(
                "parameter.unsupported_combination",
                f"/compatibility_rules/{rule.rule_id}",
            )
        satisfied.append(rule.rule_id)
    return tuple(satisfied)


def _resolved_by_surface(
    surfaces: tuple[m.ResolvedSurface, ...],
) -> dict[str, m.ResolvedSurface]:
    return {surface.surface_id: surface for surface in surfaces}


def _resolve_backbone(
    assembly: CandidateAssemblyContract,
    surfaces: tuple[m.ResolvedSurface, ...],
) -> tuple[m.ResolvedBackboneBinding, m.BackboneOption]:
    surface = _resolved_by_surface(surfaces).get("strategy_backbone")
    if type(surface) is not m.SelectedSurface:
        _fail("strategy.backbone_mismatch", "/backbone")
    if surface.value.value_type is not m.SurfaceValueType.BACKBONE_SELECTOR:
        _fail("strategy.backbone_mismatch", "/backbone")
    options = tuple(
        option
        for option in assembly.backbone_surface.options
        if option.selector_token == surface.value.value
    )
    if len(options) != 1:
        _fail("strategy.backbone_mismatch", "/backbone")
    option = options[0]
    return (
        m.ResolvedBackboneBinding(
            surface_id=assembly.backbone_surface.surface_id,
            selector_token=option.selector_token,
            backbone_id=option.backbone_id,
            backbone_version=option.backbone_version,
            content_digest=option.content_digest,
            implementation_pin=option.implementation_pin,
            environment_pin=option.environment_pin,
            dependency_pins=option.dependency_pins,
            input_interface_pin=option.input_interface_pin,
            output_interface_pin=option.output_interface_pin,
            applicability_ref=option.applicability_ref,
            assumption_refs=option.assumption_refs,
            limitation_refs=option.limitation_refs,
        ),
        option,
    )


def _resolve_components(
    assembly: CandidateAssemblyContract,
    surfaces: tuple[m.ResolvedSurface, ...],
) -> tuple[
    tuple[m.ResolvedComponentBinding, ...],
    tuple[tuple[m.ComponentSlotContract, m.RegisteredComponentOption], ...],
]:
    by_surface = _resolved_by_surface(surfaces)
    bindings: list[m.ResolvedComponentBinding] = []
    selected: list[tuple[m.ComponentSlotContract, m.RegisteredComponentOption]] = []
    for slot in sorted(assembly.component_slots, key=lambda item: item.slot_id):
        if slot.fallback_policy is not m.FallbackPolicy.FAIL_CLOSED:
            _fail("component.fallback_forbidden", f"/components/{slot.slot_id}")
        surface = by_surface.get(slot.selector_surface_id)
        if type(surface) is m.NotApplicableSurface:
            continue
        if type(surface) not in {m.SelectedSurface, m.DefaultedSurface}:
            _fail("component.unknown", f"/components/{slot.slot_id}")
        if surface.value.value_type is not m.SurfaceValueType.COMPONENT_SELECTOR:
            _fail("component.unknown", f"/components/{slot.slot_id}")
        options = tuple(
            option
            for option in slot.options
            if option.selector_token == surface.value.value
        )
        if len(options) != 1:
            _fail("component.unknown", f"/components/{slot.slot_id}")
        option = options[0]
        if option.role is not slot.role:
            _fail("component.role_confusion", f"/components/{slot.slot_id}")
        if (
            option.consumer_target != slot.consumer_target
            or option.input_interface_pin != slot.input_interface_pin
            or option.output_interface_pin != slot.output_interface_pin
        ):
            _fail("component.interface_mismatch", f"/components/{slot.slot_id}")
        if (
            option.state_policy is not slot.state_policy
            or option.side_effect_policy is not slot.side_effect_policy
            or option.trainability_boundary is not slot.trainability_boundary
        ):
            _fail("component.pin_mismatch", f"/components/{slot.slot_id}")
        bindings.append(
            m.ResolvedComponentBinding(
                slot_id=slot.slot_id,
                selector_surface_id=slot.selector_surface_id,
                selector_token=option.selector_token,
                component_id=option.component_id,
                component_version=option.component_version,
                content_digest=option.content_digest,
                role=option.role,
                consumer_target=option.consumer_target,
                input_interface_pin=option.input_interface_pin,
                output_interface_pin=option.output_interface_pin,
                state_policy=option.state_policy,
                side_effect_policy=option.side_effect_policy,
                trainability_boundary=option.trainability_boundary,
                implementation_pin=option.implementation_pin,
                environment_pin=option.environment_pin,
                dependency_pins=option.dependency_pins,
                applicability_ref=option.applicability_ref,
                assumption_refs=option.assumption_refs,
                limitation_refs=option.limitation_refs,
                public_falsification_refs=option.public_falsification_refs,
            )
        )
        selected.append((slot, option))
    return tuple(bindings), tuple(selected)


def _canonical_set(values: tuple[object, ...]) -> tuple:
    unique = set(values)
    return tuple(sorted(unique, key=encode_model))


def _resource_requirements(
    *,
    assembly: CandidateAssemblyContract,
    catalog: ParameterCatalog,
    surfaces: tuple[m.ResolvedSurface, ...],
    backbone_option: m.BackboneOption,
    component_options: tuple[
        tuple[m.ComponentSlotContract, m.RegisteredComponentOption], ...
    ],
) -> tuple[m.StaticResourceRequirement, ...]:
    dimensions = {item.dimension_id: item for item in assembly.resource_dimensions}
    resolved = _resolved_by_surface(surfaces)
    aggregate: dict[str, tuple[int, set[str], set[str]]] = {}

    sources: list[
        tuple[str, tuple[m.StaticResourceContribution, ...], tuple[str, ...]]
    ] = []
    for entry in catalog.entries:
        if type(resolved[entry.surface_id]) is not m.NotApplicableSurface:
            sources.append(
                (
                    entry.surface_id,
                    entry.static_resource_contributions,
                    entry.resource_impact_tags,
                )
            )
    sources.append(
        (
            assembly.backbone_surface.surface_id,
            backbone_option.static_resource_contributions,
            backbone_option.resource_impact_tags,
        )
    )
    sources.extend(
        (
            slot.slot_id,
            option.static_resource_contributions,
            option.resource_impact_tags,
        )
        for slot, option in component_options
    )
    for source_id, contributions, source_tags in sorted(
        sources, key=lambda item: item[0]
    ):
        for contribution in contributions:
            dimension = dimensions.get(contribution.dimension_id)
            if dimension is None:
                _fail("resource.dimension_unknown", "/static_resources")
            if contribution.unit_ref != dimension.unit_ref:
                _fail("resource.unit_conflict", "/static_resources")
            if type(contribution) is m.FixedResourceContribution:
                quantity = contribution.quantity
            elif type(contribution) is m.DiscreteLookupResourceContribution:
                selector = resolved.get(contribution.selector_surface_id)
                if type(selector) not in {m.SelectedSurface, m.DefaultedSurface}:
                    _fail("resource.lookup_missing", "/static_resources")
                cases = tuple(
                    case
                    for case in contribution.cases
                    if case.selector_value == selector.value
                )
                if len(cases) != 1:
                    _fail("resource.lookup_missing", "/static_resources")
                quantity = cases[0].quantity
            else:
                _fail("resource.policy_forbidden", "/static_resources")
            current, contributing, tags = aggregate.get(
                contribution.dimension_id,
                (0, set(), set()),
            )
            if quantity > _UINT64_MAX - current:
                _fail("resource.overflow", "/static_resources")
            contributing.add(source_id)
            tags.update(source_tags)
            tags.update(contribution.impact_tags)
            aggregate[contribution.dimension_id] = (
                current + quantity,
                contributing,
                tags,
            )
    return tuple(
        m.StaticResourceRequirement(
            dimension_id=dimension_id,
            unit_ref=dimensions[dimension_id].unit_ref,
            quantity=quantity,
            contributing_source_ids=tuple(contributing),
            impact_tags=tuple(tags),
        )
        for dimension_id, (quantity, contributing, tags) in sorted(aggregate.items())
    )


def _plan_pins(
    assembly: CandidateAssemblyContract,
    backbone_option: m.BackboneOption,
    component_options: tuple[
        tuple[m.ComponentSlotContract, m.RegisteredComponentOption], ...
    ],
) -> tuple[
    tuple[m.DependencyPin, ...],
    tuple[m.EnvironmentPin, ...],
    tuple[m.ImplementationPin, ...],
]:
    options = (backbone_option, *(option for _, option in component_options))
    dependency_pins = _canonical_set(
        (
            *assembly.dependency_pins,
            *(pin for option in options for pin in option.dependency_pins),
        )
    )
    environment_pins = _canonical_set(
        (*assembly.environment_pins, *(option.environment_pin for option in options))
    )
    implementation_pins = _canonical_set(
        tuple(option.implementation_pin for option in options)
    )
    return dependency_pins, environment_pins, implementation_pins


def _compile_detached_strategy(
    *,
    snapshot: dict[str, object],
    strategy_hash: StrategyHash,
    challenge_key: object,
    candidate_assembly: object,
    candidate_assembly_ref: object,
    parameter_catalog: object,
    parameter_catalog_ref: object,
    authoring_origin: object,
    authoring_artifacts: object,
    compiler_identity: object,
) -> CompileAccepted:
    (
        key,
        assembly,
        assembly_ref,
        catalog,
        catalog_ref,
        origin_binding,
    ) = _verify_inputs(
        challenge_key=challenge_key,
        candidate_assembly=candidate_assembly,
        candidate_assembly_ref=candidate_assembly_ref,
        parameter_catalog=parameter_catalog,
        parameter_catalog_ref=parameter_catalog_ref,
        authoring_origin=authoring_origin,
        authoring_artifacts=authoring_artifacts,
        compiler_identity=compiler_identity,
    )
    surfaces, _ = _resolve_surfaces(snapshot=snapshot, catalog=catalog)
    satisfied_rules = _compatibility(catalog, surfaces)
    backbone_binding, backbone_option = _resolve_backbone(assembly, surfaces)
    components, component_options = _resolve_components(assembly, surfaces)
    training_policy, training_policy_ref = _build_training_sampling_policy(
        challenge_key=key,
        training_support_ref=assembly.training_support_ref,
        catalog_ref=catalog_ref,
        entries=catalog.entries,
        resolved_surfaces=surfaces,
    )
    resources = _resource_requirements(
        assembly=assembly,
        catalog=catalog,
        surfaces=surfaces,
        backbone_option=backbone_option,
        component_options=component_options,
    )
    dependency_pins, environment_pins, implementation_pins = _plan_pins(
        assembly,
        backbone_option,
        component_options,
    )
    resolved = _resolved_by_surface(surfaces)
    impact_tags = set(backbone_option.resource_impact_tags)
    for entry in catalog.entries:
        if type(resolved[entry.surface_id]) is not m.NotApplicableSurface:
            impact_tags.update(entry.resource_impact_tags)
    for _, option in component_options:
        impact_tags.update(option.resource_impact_tags)
    for requirement in resources:
        impact_tags.update(requirement.impact_tags)

    plan = ResolvedConstructionPlan(
        object_kind="resolved_construction_plan",
        schema_version="1.0",
        canonicalization_profile="carbon_construction_canonical_v1",
        challenge_key=key,
        strategy_schema_version=snapshot["schema_version"],
        strategy_hash=strategy_hash,
        authoring_origin_binding=origin_binding,
        physical_system_ref=assembly.physical_system_ref,
        candidate_output_ref=assembly.candidate_output_ref,
        training_support_ref=assembly.training_support_ref,
        candidate_assembly_ref=assembly_ref,
        parameter_catalog_ref=catalog_ref,
        compiler_identity=compiler_identity,
        backbone_binding=backbone_binding,
        resolved_surfaces=surfaces,
        satisfied_compatibility_rule_ids=satisfied_rules,
        resolved_components=components,
        training_sampling_policy_ref=training_policy_ref,
        dependency_pins=dependency_pins,
        environment_pins=environment_pins,
        implementation_pins=implementation_pins,
        static_resource_requirements=resources,
        resource_impact_tags=tuple(impact_tags),
        assembly_provenance=assembly.provenance,
        catalog_provenance=catalog.provenance,
        authority_marker=m.AuthorityMarker.CONSTRUCTION_ONLY_NOT_QUALIFICATION,
    )
    _mark_resolved_construction_plan_verified(plan)
    plan_ref = plan.to_ref()
    return CompileAccepted(
        training_policy=training_policy,
        training_policy_ref=training_policy_ref,
        construction_plan=plan,
        construction_plan_ref=plan_ref,
    )


def compile_strategy(
    strategy: object,
    *,
    challenge_key: object,
    candidate_assembly: object,
    candidate_assembly_ref: object,
    parameter_catalog: object,
    parameter_catalog_ref: object,
    authoring_origin: object,
    authoring_artifacts: object,
    compiler_identity: object,
    strategy_limits: object,
) -> CompileResult:
    """Compile one bounded detached Strategy snapshot or return typed rejection."""

    if type(strategy_limits) is not SubmissionResourceLimits:
        return CompileRejected((_issue("strategy.identity_invalid", "/strategy"),))
    try:
        identity = identify_strategy(strategy, strategy_limits)
    except Exception:  # noqa: BLE001 - hostile identity failures must fail closed.
        return CompileRejected((_issue("strategy.identity_invalid", "/strategy"),))
    if identity.validation is None or not identity.validation.ok:
        return CompileRejected((_issue("strategy.invalid", "/strategy"),))
    if (
        identity.a7_error_code is not None
        or type(identity.strategy) is not dict
        or type(identity.strategy_hash) is not StrategyHash
    ):
        return CompileRejected((_issue("strategy.identity_invalid", "/strategy"),))
    snapshot = identity.strategy
    if type(challenge_key) is not ChallengeKey:
        return CompileRejected((_issue("reference.type_mismatch", "/challenge_key"),))
    if snapshot.get("challenge_id") != challenge_key.challenge_id:
        return CompileRejected(
            (_issue("strategy.challenge_mismatch", "/challenge_id"),)
        )
    try:
        return _compile_detached_strategy(
            snapshot=snapshot,
            strategy_hash=identity.strategy_hash,
            challenge_key=challenge_key,
            candidate_assembly=candidate_assembly,
            candidate_assembly_ref=candidate_assembly_ref,
            parameter_catalog=parameter_catalog,
            parameter_catalog_ref=parameter_catalog_ref,
            authoring_origin=authoring_origin,
            authoring_artifacts=authoring_artifacts,
            compiler_identity=compiler_identity,
        )
    except _CompileFailure as exc:
        return CompileRejected(exc.issues)
    except Exception:  # noqa: BLE001 - the public compiler never leaks internals.
        return CompileRejected((_issue("compile.internal_failure", "/"),))


__all__ = [
    "COMPILE_ISSUE_CODES",
    "SUPPORTED_COMPILER_IDENTITY",
    "CompileAccepted",
    "CompileIssue",
    "CompileRejected",
    "CompileResult",
    "compile_strategy",
]
