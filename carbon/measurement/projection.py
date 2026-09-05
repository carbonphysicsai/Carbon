"""Fail-closed B-05 projection onto the unchanged A5 input vocabulary."""

from __future__ import annotations

import math
from dataclasses import dataclass

from carbon.authoring.primitives import MAX_CANONICAL_TUPLE_ITEMS, validate_canonical_id
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.scoring.model import ScorePackPin
from carbon.scoring.pack import LoadedScorePack

from .canonical import measurement_ref
from .enums import (
    A5DestinationKind,
    MeasurementDefinitionKind,
    MeasurementMaterialSource,
    MeasurementMaterialState,
    MeasurementRole,
    ScientificValueState,
    ScoreAggregationRole,
    ScoreScalarKind,
    ScoreUseRole,
    StratumApplicabilityStatus,
)
from .errors import MeasurementInputCode, MeasurementValidationError
from .model import (
    MeasurementContract,
    ScorePackAuthoringContract,
    ScorePackInputBinding,
    UncertaintyPolicy,
)
from .refs import (
    MeasurementContractRef,
    MeasurementDefinitionRef,
    UncertaintyPolicyRef,
)


def _invalid(path: str, code: MeasurementInputCode) -> MeasurementValidationError:
    return MeasurementValidationError(code, path=path)


def _exact(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    return value


def _definition(
    value: object,
    kind: MeasurementDefinitionKind,
    challenge_key: object,
    path: str,
) -> MeasurementDefinitionRef:
    ref = _exact(value, MeasurementDefinitionRef, path)
    if ref.definition_kind is not kind:
        raise _invalid(path, MeasurementInputCode.ROLE_CONFUSION)
    if ref.challenge_key != challenge_key:
        raise _invalid(path, MeasurementInputCode.CROSS_CHALLENGE)
    return ref


@dataclass(frozen=True, slots=True)
class MeasurementMaterial:
    """One typed measurement result; only COMPLETE may carry one scalar."""

    measurement_contract_ref: MeasurementContractRef
    measurement_output_ref: MeasurementDefinitionRef
    case_scope_ref: MeasurementDefinitionRef
    stratum_ref: MeasurementDefinitionRef
    reference_policy_ref: ReferencePolicyRef
    uncertainty_policy_ref: UncertaintyPolicyRef
    applicability_evidence_ref: MeasurementDefinitionRef | None
    qualification_ref: MeasurementDefinitionRef | None
    admissibility_evidence_ref: MeasurementDefinitionRef | None
    provenance_ref: MeasurementDefinitionRef
    source: MeasurementMaterialSource
    state: MeasurementMaterialState
    scalar_kind: ScoreScalarKind
    numeric_scalar: float | None
    boolean_scalar: bool | None
    reason_ref: MeasurementDefinitionRef | None
    fixture_origin: bool

    def __post_init__(self) -> None:
        contract_ref = _exact(
            self.measurement_contract_ref,
            MeasurementContractRef,
            "/measurement_contract_ref",
        )
        challenge_key = contract_ref.challenge_key
        for name, kind in (
            ("measurement_output_ref", MeasurementDefinitionKind.MEASUREMENT_OUTPUT),
            ("case_scope_ref", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_ref", MeasurementDefinitionKind.STRATUM),
            ("provenance_ref", MeasurementDefinitionKind.EVIDENCE_SOURCE),
        ):
            _definition(getattr(self, name), kind, challenge_key, f"/{name}")
        reference = _exact(
            self.reference_policy_ref, ReferencePolicyRef, "/reference_policy_ref"
        )
        uncertainty = _exact(
            self.uncertainty_policy_ref,
            UncertaintyPolicyRef,
            "/uncertainty_policy_ref",
        )
        if reference.challenge_key != challenge_key:
            raise _invalid(
                "/reference_policy_ref", MeasurementInputCode.CROSS_CHALLENGE
            )
        if uncertainty.challenge_key != challenge_key:
            raise _invalid(
                "/uncertainty_policy_ref", MeasurementInputCode.CROSS_CHALLENGE
            )
        if self.applicability_evidence_ref is not None:
            _definition(
                self.applicability_evidence_ref,
                MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
                challenge_key,
                "/applicability_evidence_ref",
            )
        if self.qualification_ref is not None:
            _definition(
                self.qualification_ref,
                MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                challenge_key,
                "/qualification_ref",
            )
        if self.admissibility_evidence_ref is not None:
            _definition(
                self.admissibility_evidence_ref,
                MeasurementDefinitionKind.SCORE_ADMISSIBILITY_EVIDENCE,
                challenge_key,
                "/admissibility_evidence_ref",
            )
        _exact(self.source, MeasurementMaterialSource, "/source")
        _exact(self.state, MeasurementMaterialState, "/state")
        _exact(self.scalar_kind, ScoreScalarKind, "/scalar_kind")
        if type(self.fixture_origin) is not bool:
            raise _invalid("/fixture_origin", MeasurementInputCode.WRONG_TYPE)
        if self.state is MeasurementMaterialState.COMPLETE:
            if self.reason_ref is not None:
                raise _invalid("/reason_ref", MeasurementInputCode.ROLE_CONFUSION)
            if self.applicability_evidence_ref is None:
                raise _invalid(
                    "/applicability_evidence_ref",
                    MeasurementInputCode.MATERIAL_UNRESOLVED,
                )
            if self.qualification_ref is None:
                raise _invalid(
                    "/qualification_ref", MeasurementInputCode.MATERIAL_UNRESOLVED
                )
            if self.admissibility_evidence_ref is None:
                raise _invalid(
                    "/admissibility_evidence_ref",
                    MeasurementInputCode.MATERIAL_UNRESOLVED,
                )
            if self.scalar_kind is ScoreScalarKind.NUMERIC:
                if (
                    type(self.numeric_scalar) is not float
                    or not math.isfinite(self.numeric_scalar)
                    or self.numeric_scalar < 0.0
                    or self.boolean_scalar is not None
                ):
                    raise _invalid(
                        "/numeric_scalar", MeasurementInputCode.INVALID_VALUE
                    )
            elif (
                type(self.boolean_scalar) is not bool or self.numeric_scalar is not None
            ):
                raise _invalid("/boolean_scalar", MeasurementInputCode.INVALID_VALUE)
        else:
            if self.numeric_scalar is not None or self.boolean_scalar is not None:
                raise _invalid("/state", MeasurementInputCode.ROLE_CONFUSION)
            _definition(
                self.reason_ref,
                MeasurementDefinitionKind.MEASUREMENT_MATERIAL_REASON,
                challenge_key,
                "/reason_ref",
            )


@dataclass(frozen=True, slots=True)
class ScoreScalarProjection:
    """A scalar still separated by B-05 use role; this is not A5 ScoreInput."""

    input_key: str
    scalar_kind: ScoreScalarKind
    use_role: ScoreUseRole
    numeric_scalar: float | None
    boolean_scalar: bool | None

    def __post_init__(self) -> None:
        try:
            validate_canonical_id(self.input_key, "input_key")
        except (TypeError, ValueError):
            raise _invalid("/input_key", MeasurementInputCode.INVALID_VALUE) from None
        _exact(self.scalar_kind, ScoreScalarKind, "/scalar_kind")
        _exact(self.use_role, ScoreUseRole, "/use_role")
        if self.scalar_kind is ScoreScalarKind.NUMERIC:
            if (
                type(self.numeric_scalar) is not float
                or not math.isfinite(self.numeric_scalar)
                or self.numeric_scalar < 0.0
                or self.boolean_scalar is not None
            ):
                raise _invalid("/numeric_scalar", MeasurementInputCode.WRONG_TYPE)
        elif type(self.boolean_scalar) is not bool or self.numeric_scalar is not None:
            raise _invalid("/boolean_scalar", MeasurementInputCode.WRONG_TYPE)


@dataclass(frozen=True, slots=True)
class ScorePackProjection:
    """Mandatory-first projection result; deferred results contain no scalars."""

    pack_pin: ScorePackPin
    outcome: MeasurementMaterialState
    blocking_input_keys: tuple[str, ...]
    mandatory_scalars: tuple[ScoreScalarProjection, ...]
    soft_scalars: tuple[ScoreScalarProjection, ...]
    diagnostic_scalars: tuple[ScoreScalarProjection, ...]

    def __post_init__(self) -> None:
        _exact(self.pack_pin, ScorePackPin, "/pack_pin")
        _exact(self.outcome, MeasurementMaterialState, "/outcome")
        if type(self.blocking_input_keys) is not tuple:
            raise _invalid("/blocking_input_keys", MeasurementInputCode.WRONG_TYPE)
        for index, value in enumerate(self.blocking_input_keys):
            try:
                validate_canonical_id(value, "input_key")
            except (TypeError, ValueError):
                raise _invalid(
                    f"/blocking_input_keys/{index}",
                    MeasurementInputCode.INVALID_VALUE,
                ) from None
        role_fields = (
            ("mandatory_scalars", self.mandatory_scalars, ScoreUseRole.MANDATORY_GATE),
            ("soft_scalars", self.soft_scalars, ScoreUseRole.SOFT_COMPONENT),
            ("diagnostic_scalars", self.diagnostic_scalars, ScoreUseRole.DIAGNOSTIC),
        )
        for name, values, role in role_fields:
            if type(values) is not tuple:
                raise _invalid(f"/{name}", MeasurementInputCode.WRONG_TYPE)
            if any(
                type(item) is not ScoreScalarProjection or item.use_role is not role
                for item in values
            ):
                raise _invalid(f"/{name}", MeasurementInputCode.ROLE_CONFUSION)
        all_scalars = (
            self.mandatory_scalars + self.soft_scalars + self.diagnostic_scalars
        )
        if self.outcome is MeasurementMaterialState.COMPLETE:
            if self.blocking_input_keys:
                raise _invalid(
                    "/blocking_input_keys", MeasurementInputCode.ROLE_CONFUSION
                )
        elif not self.blocking_input_keys or all_scalars:
            raise _invalid("/outcome", MeasurementInputCode.ROLE_CONFUSION)


def _expected_pack_bindings(pack: LoadedScorePack) -> dict[str, tuple[object, ...]]:
    expected: dict[str, tuple[object, ...]] = {}

    def add(key: str, spec: tuple[object, ...]) -> None:
        if key in expected:
            raise _invalid(
                "/input_bindings", MeasurementInputCode.PACK_COVERAGE_MISMATCH
            )
        expected[key] = spec

    for gate in pack.hard_gates:
        scalar_kind = (
            ScoreScalarKind.BOOLEAN
            if gate.operator == "boolean_true"
            else ScoreScalarKind.NUMERIC
        )
        if gate.mandatory:
            add(
                gate.input_key,
                (
                    scalar_kind,
                    ScoreUseRole.MANDATORY_GATE,
                    ScoreAggregationRole.MANDATORY_ADMISSIBILITY,
                    A5DestinationKind.MANDATORY_GATE,
                    gate.gate_id,
                ),
            )
        else:
            add(
                gate.input_key,
                (
                    scalar_kind,
                    ScoreUseRole.DIAGNOSTIC,
                    ScoreAggregationRole.NONE,
                    A5DestinationKind.DIAGNOSTIC_GATE,
                    gate.gate_id,
                ),
            )
    for component in pack.physics.components:
        add(
            component.input_key,
            (
                ScoreScalarKind.NUMERIC,
                ScoreUseRole.SOFT_COMPONENT,
                ScoreAggregationRole.PHYSICS,
                A5DestinationKind.PHYSICS_COMPONENT,
                component.component_id,
            ),
        )
    for category in pack.robustness.categories:
        add(
            category.mean_input_key,
            (
                ScoreScalarKind.NUMERIC,
                ScoreUseRole.SOFT_COMPONENT,
                ScoreAggregationRole.ROBUSTNESS_MEAN,
                A5DestinationKind.ROBUSTNESS_MEAN,
                category.category_id,
            ),
        )
        add(
            category.tail_input_key,
            (
                ScoreScalarKind.NUMERIC,
                ScoreUseRole.SOFT_COMPONENT,
                ScoreAggregationRole.ROBUSTNESS_TAIL,
                A5DestinationKind.ROBUSTNESS_TAIL,
                category.category_id,
            ),
        )
    for component in pack.accuracy.components:
        add(
            component.input_key,
            (
                ScoreScalarKind.NUMERIC,
                ScoreUseRole.SOFT_COMPONENT,
                ScoreAggregationRole.ACCURACY,
                A5DestinationKind.ACCURACY_COMPONENT,
                component.component_id,
            ),
        )
    return expected


def validate_score_pack_coverage(
    contract: ScorePackAuthoringContract,
    pack: LoadedScorePack,
    measurement_contracts: tuple[MeasurementContract, ...],
    uncertainty_policies: tuple[UncertaintyPolicy, ...],
) -> tuple[ScorePackInputBinding, ...]:
    """Validate exact ready-pack coverage without constructing A5 ScoreInput."""

    contract = _exact(contract, ScorePackAuthoringContract, "/contract")
    pack = _exact(pack, LoadedScorePack, "/pack")
    if pack.ready is not True:
        raise _invalid("/pack", MeasurementInputCode.PACK_NOT_READY)
    if pack.pack_pin != contract.score_pack_pin:
        raise _invalid("/score_pack_pin", MeasurementInputCode.DIGEST_MISMATCH)
    if not contract.has_complete_score_policy_authority:
        raise _invalid(
            "/score_policy_authority", MeasurementInputCode.MATERIAL_UNRESOLVED
        )
    expected = _expected_pack_bindings(pack)
    bindings = {item.input_key: item for item in contract.input_bindings}
    if set(bindings) != set(expected):
        raise _invalid("/input_bindings", MeasurementInputCode.PACK_COVERAGE_MISMATCH)
    if type(measurement_contracts) is not tuple:
        raise _invalid("/measurements", MeasurementInputCode.WRONG_TYPE)
    if type(uncertainty_policies) is not tuple:
        raise _invalid("/uncertainties", MeasurementInputCode.WRONG_TYPE)
    measurements: dict[object, MeasurementContract] = {}
    for index, item in enumerate(measurement_contracts):
        item = _exact(item, MeasurementContract, f"/measurements/{index}")
        ref = measurement_ref(item)
        if ref in measurements:
            raise _invalid("/measurements", MeasurementInputCode.DUPLICATE_IDENTITY)
        measurements[ref] = item
    uncertainties: dict[object, UncertaintyPolicy] = {}
    for index, item in enumerate(uncertainty_policies):
        item = _exact(item, UncertaintyPolicy, f"/uncertainties/{index}")
        ref = measurement_ref(item)
        if ref in uncertainties:
            raise _invalid("/uncertainties", MeasurementInputCode.DUPLICATE_IDENTITY)
        uncertainties[ref] = item
    if set(measurements) != {
        item.measurement_contract_ref for item in contract.input_bindings
    }:
        raise _invalid("/measurements", MeasurementInputCode.PACK_COVERAGE_MISMATCH)
    if set(uncertainties) != {
        item.uncertainty_policy_ref for item in contract.input_bindings
    }:
        raise _invalid("/uncertainties", MeasurementInputCode.PACK_COVERAGE_MISMATCH)
    intended_roles = {
        ScoreUseRole.MANDATORY_GATE: MeasurementRole.MANDATORY,
        ScoreUseRole.SOFT_COMPONENT: MeasurementRole.SOFT,
        ScoreUseRole.DIAGNOSTIC: MeasurementRole.DIAGNOSTIC,
    }
    ordered: list[ScorePackInputBinding] = []
    for input_key, expected_spec in expected.items():
        binding = bindings[input_key]
        actual_spec = (
            binding.scalar_kind,
            binding.use_role,
            binding.aggregation_role,
            binding.destination_kind,
            binding.destination_id,
        )
        if actual_spec != expected_spec:
            code = (
                MeasurementInputCode.ROLE_CONFUSION
                if binding.use_role is not expected_spec[1]
                else MeasurementInputCode.PACK_COVERAGE_MISMATCH
            )
            raise _invalid(
                f"/input_bindings/{input_key}",
                code,
            )
        measurement = measurements.get(binding.measurement_contract_ref)
        uncertainty = uncertainties.get(binding.uncertainty_policy_ref)
        if measurement is None or uncertainty is None:
            raise _invalid(
                f"/input_bindings/{input_key}", MeasurementInputCode.UNKNOWN_OBJECT
            )
        if measurement.intended_role is not intended_roles[binding.use_role]:
            raise _invalid(
                f"/input_bindings/{input_key}/use_role",
                MeasurementInputCode.ROLE_CONFUSION,
            )
        if measurement.fixture_origin != binding.fixture_origin:
            raise _invalid(
                f"/input_bindings/{input_key}/fixture_origin",
                MeasurementInputCode.FIXTURE_REQUIRED,
            )
        applicable = {
            item.stratum_ref: item.status for item in measurement.stratum_applicability
        }
        if (
            applicable.get(binding.stratum_ref)
            is not StratumApplicabilityStatus.APPLICABLE
        ):
            raise _invalid(
                f"/input_bindings/{input_key}/stratum_ref",
                MeasurementInputCode.MATERIAL_UNRESOLVED,
            )
        selected_policy = measurement.uncertainty_policy_binding
        if (
            selected_policy.state is ScientificValueState.BOUND
            and selected_policy.policy_ref != binding.uncertainty_policy_ref
        ):
            raise _invalid(
                f"/input_bindings/{input_key}/uncertainty_policy_ref",
                MeasurementInputCode.ROLE_CONFUSION,
            )
        if (
            uncertainty.fixture_origin != binding.fixture_origin
            or uncertainty.measurement_output_binding.state
            is not ScientificValueState.BOUND
            or uncertainty.measurement_output_binding.component_ref
            != binding.measurement_output_ref
            or uncertainty.estimand_binding.state is not ScientificValueState.BOUND
            or uncertainty.estimand_binding.component_ref != binding.estimand_ref
        ):
            raise _invalid(
                f"/input_bindings/{input_key}/uncertainty_policy_ref",
                MeasurementInputCode.ROLE_CONFUSION,
            )
        ordered.append(binding)
    return tuple(ordered)


_OUTCOME_PRECEDENCE = (
    MeasurementMaterialState.INAPPLICABLE,
    MeasurementMaterialState.REFERENCE_FAILED,
    MeasurementMaterialState.PARTIAL,
    MeasurementMaterialState.NON_FINITE,
    MeasurementMaterialState.NUMERICAL_FLOOR_UNRESOLVED,
    MeasurementMaterialState.UNCERTAINTY_UNRESOLVED,
    MeasurementMaterialState.QUALIFICATION_UNRESOLVED,
    MeasurementMaterialState.EVIDENCE_DEFERRED,
)


def project_score_scalars(
    contract: ScorePackAuthoringContract,
    pack: LoadedScorePack,
    measurement_contracts: tuple[MeasurementContract, ...],
    uncertainty_policies: tuple[UncertaintyPolicy, ...],
    materials: tuple[MeasurementMaterial, ...],
) -> ScorePackProjection:
    """Resolve all bindings before exposing mandatory, then soft, scalars."""

    ordered = validate_score_pack_coverage(
        contract, pack, measurement_contracts, uncertainty_policies
    )
    if type(materials) is not tuple or len(materials) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid("/materials", MeasurementInputCode.WRONG_TYPE)
    by_output: dict[
        tuple[MeasurementContractRef, MeasurementDefinitionRef], MeasurementMaterial
    ] = {}
    for index, item in enumerate(materials):
        material = _exact(item, MeasurementMaterial, f"/materials/{index}")
        key = (material.measurement_contract_ref, material.measurement_output_ref)
        if key in by_output:
            raise _invalid("/materials", MeasurementInputCode.DUPLICATE_IDENTITY)
        by_output[key] = material
    expected_outputs = {
        (item.measurement_contract_ref, item.measurement_output_ref) for item in ordered
    }
    if set(by_output) != expected_outputs:
        raise _invalid("/materials", MeasurementInputCode.PACK_COVERAGE_MISMATCH)

    matched: list[tuple[ScorePackInputBinding, MeasurementMaterial]] = []
    for binding in ordered:
        material = by_output[
            (binding.measurement_contract_ref, binding.measurement_output_ref)
        ]
        path = f"/materials/{binding.input_key}"
        if material.source is not MeasurementMaterialSource.QUALIFIED_MEASUREMENT:
            raise _invalid(f"{path}/source", MeasurementInputCode.FORBIDDEN_SOURCE)
        if (
            material.scalar_kind is not binding.scalar_kind
            or material.case_scope_ref != binding.case_scope_ref
            or material.stratum_ref != binding.stratum_ref
            or material.uncertainty_policy_ref != binding.uncertainty_policy_ref
            or material.applicability_evidence_ref
            not in (None, binding.applicability_evidence_ref)
            or material.qualification_ref not in (None, binding.qualification_ref)
            or material.admissibility_evidence_ref
            not in (None, binding.admissibility_evidence_ref)
            or material.provenance_ref != binding.provenance_ref
            or material.fixture_origin != binding.fixture_origin
        ):
            raise _invalid(path, MeasurementInputCode.ROLE_CONFUSION)
        measurement = next(
            item
            for item in measurement_contracts
            if measurement_ref(item) == binding.measurement_contract_ref
        )
        if material.reference_policy_ref != measurement.reference_policy_ref:
            raise _invalid(
                f"{path}/reference_policy_ref", MeasurementInputCode.ROLE_CONFUSION
            )
        matched.append((binding, material))

    for outcome in _OUTCOME_PRECEDENCE[:4]:
        blockers = tuple(
            binding.input_key
            for binding, material in matched
            if material.state is outcome
        )
        if blockers:
            return ScorePackProjection(
                contract.score_pack_pin, outcome, blockers, (), (), ()
            )

    measurements_by_ref = {
        measurement_ref(item): item for item in measurement_contracts
    }
    uncertainties_by_ref = {
        measurement_ref(item): item for item in uncertainty_policies
    }
    floor_blockers = tuple(
        binding.input_key
        for binding, material in matched
        if material.state is MeasurementMaterialState.NUMERICAL_FLOOR_UNRESOLVED
        or measurements_by_ref[
            binding.measurement_contract_ref
        ].numerical_floor_binding.state
        is not ScientificValueState.BOUND
    )
    if floor_blockers:
        return ScorePackProjection(
            contract.score_pack_pin,
            MeasurementMaterialState.NUMERICAL_FLOOR_UNRESOLVED,
            floor_blockers,
            (),
            (),
            (),
        )

    uncertainty_blockers = tuple(
        binding.input_key
        for binding, material in matched
        if material.state is MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
        or measurements_by_ref[
            binding.measurement_contract_ref
        ].uncertainty_policy_binding.state
        is not ScientificValueState.BOUND
        or not uncertainties_by_ref[
            binding.uncertainty_policy_ref
        ].has_complete_score_authority
    )
    if uncertainty_blockers:
        return ScorePackProjection(
            contract.score_pack_pin,
            MeasurementMaterialState.UNCERTAINTY_UNRESOLVED,
            uncertainty_blockers,
            (),
            (),
            (),
        )

    for outcome in _OUTCOME_PRECEDENCE[6:]:
        blockers = tuple(
            binding.input_key
            for binding, material in matched
            if material.state is outcome
        )
        if blockers:
            return ScorePackProjection(
                contract.score_pack_pin, outcome, blockers, (), (), ()
            )

    projections = tuple(
        ScoreScalarProjection(
            binding.input_key,
            binding.scalar_kind,
            binding.use_role,
            material.numeric_scalar,
            material.boolean_scalar,
        )
        for binding, material in matched
    )
    return ScorePackProjection(
        contract.score_pack_pin,
        MeasurementMaterialState.COMPLETE,
        (),
        tuple(
            item for item in projections if item.use_role is ScoreUseRole.MANDATORY_GATE
        ),
        tuple(
            item for item in projections if item.use_role is ScoreUseRole.SOFT_COMPONENT
        ),
        tuple(item for item in projections if item.use_role is ScoreUseRole.DIAGNOSTIC),
    )


__all__ = (
    "MeasurementMaterial",
    "ScorePackProjection",
    "ScoreScalarProjection",
    "project_score_scalars",
    "validate_score_pack_coverage",
)
