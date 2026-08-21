"""Deterministic dependency-free A5 scoring over validated fixture packs."""

from __future__ import annotations

import math

from carbon.registry import validate_canonical_identifier
from carbon.scoring.model import (
    BooleanInput,
    GateDecision,
    InternalResult,
    LegScore,
    NumericInput,
    ScalarScore,
    ScoreInput,
    ScoreInputError,
    ScorePackPin,
    ScoreStatus,
)
from carbon.scoring.pack import (
    UNRESOLVED_STATES,
    AccuracySpec,
    GateSpec,
    LoadedScorePack,
    PhysicsSpec,
    RobustnessCategory,
    RobustnessSpec,
    ScorePackError,
    ScorePackSchemaError,
    WeightedComponent,
)

_LEG_ORDER = ("physics", "robustness", "accuracy")


class ScoringComputationError(ArithmeticError):
    """Non-scientific scoring arithmetic failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _pack_error(path: str, message: str) -> None:
    raise ScorePackSchemaError("score_pack.engine_invalid", path, message)


def _pack_identifier(value: object, path: str) -> str:
    if type(value) is not str:
        _pack_error(path, "Loaded Score Pack identifier must be an exact string.")
    try:
        return validate_canonical_identifier(value, "Loaded Score Pack identifier")
    except ValueError as exc:
        raise ScorePackSchemaError(
            "score_pack.engine_invalid",
            path,
            "Loaded Score Pack identifier is not canonical.",
        ) from exc


def _pack_scalar(value: object, path: str, rule: str) -> float | str:
    if type(value) is str:
        if value not in UNRESOLVED_STATES:
            _pack_error(path, "Loaded Score Pack contains an unknown scalar state.")
        return value
    if type(value) is not float or not math.isfinite(value) or value <= 0.0:
        _pack_error(path, "Loaded Score Pack scalar is not finite and positive.")
    if rule == "weight" and value > 1.0:
        _pack_error(path, "Loaded Score Pack weight is outside (0.0, 1.0].")
    if rule == "probability" and value >= 1.0:
        _pack_error(path, "Loaded Score Pack probability is outside (0.0, 1.0).")
    return value


def _validate_component(
    component: object,
    path: str,
    identifiers: set[str],
) -> tuple[str, str, bool]:
    if type(component) is not WeightedComponent:
        _pack_error(path, "Loaded Score Pack component has an invalid type.")
    component_id = _pack_identifier(component.component_id, f"{path}/id")
    input_key = _pack_identifier(component.input_key, f"{path}/input_key")
    if component_id in identifiers:
        _pack_error(f"{path}/id", "Loaded Score Pack component id is duplicated.")
    identifiers.add(component_id)
    threshold = _pack_scalar(component.threshold, f"{path}/threshold", "positive")
    weight = _pack_scalar(component.weight, f"{path}/weight", "weight")
    return input_key, component_id, type(threshold) is str or type(weight) is str


def _validate_loaded_pack(
    pack: LoadedScorePack,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Defensively revalidate the trusted pack shape needed by the engine."""
    if type(pack.pack_pin) is not ScorePackPin:
        _pack_error("", "Loaded Score Pack pin has an invalid type.")
    try:
        ScorePackPin(
            challenge_key=pack.pack_pin.challenge_key,
            scoring_version=pack.pack_pin.scoring_version,
            scoring_digest=pack.pack_pin.scoring_digest,
            generator_version_required=pack.pack_pin.generator_version_required,
            generator_digest_required=pack.pack_pin.generator_digest_required,
            schema_version=pack.pack_pin.schema_version,
            numerical_profile=pack.pack_pin.numerical_profile,
            fixture_origin=pack.pack_pin.fixture_origin,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ScorePackSchemaError(
            "score_pack.engine_invalid", "", "Loaded Score Pack pin is invalid."
        ) from exc
    if type(pack.ready) is not bool:
        _pack_error("/ready", "Loaded Score Pack readiness must be an exact Boolean.")
    if type(pack.hard_gates) is not tuple or not pack.hard_gates:
        _pack_error("/hard_gates", "Loaded Score Pack gates must be a non-empty tuple.")

    numeric_keys: list[str] = []
    boolean_keys: list[str] = []
    numeric_key_set: set[str] = set()
    boolean_key_set: set[str] = set()

    def add_numeric_key(key: str, path: str) -> None:
        if key in boolean_key_set:
            _pack_error(
                path,
                "Loaded Score Pack input key is reused across numeric and Boolean types.",
            )
        if key not in numeric_key_set:
            numeric_key_set.add(key)
            numeric_keys.append(key)

    def add_boolean_key(key: str, path: str) -> None:
        if key in numeric_key_set:
            _pack_error(
                path,
                "Loaded Score Pack input key is reused across numeric and Boolean types.",
            )
        if key not in boolean_key_set:
            boolean_key_set.add(key)
            boolean_keys.append(key)

    gate_ids: set[str] = set()
    gate_input_keys: set[str] = set()
    has_mandatory = False
    unresolved_required = False
    for index, gate in enumerate(pack.hard_gates):
        path = f"/hard_gates/{index}"
        if type(gate) is not GateSpec:
            _pack_error(path, "Loaded Score Pack gate has an invalid type.")
        gate_id = _pack_identifier(gate.gate_id, f"{path}/id")
        input_key = _pack_identifier(gate.input_key, f"{path}/input_key")
        if gate_id in gate_ids:
            _pack_error(f"{path}/id", "Loaded Score Pack gate id is duplicated.")
        gate_ids.add(gate_id)
        if input_key in gate_input_keys:
            _pack_error(
                f"{path}/input_key", "Loaded Score Pack gate input key is duplicated."
            )
        gate_input_keys.add(input_key)
        if type(gate.mandatory) is not bool:
            _pack_error(
                f"{path}/mandatory",
                "Loaded Score Pack mandatory flag must be an exact Boolean.",
            )
        has_mandatory = has_mandatory or gate.mandatory
        if type(gate.operator) is not str:
            _pack_error(
                f"{path}/operator", "Loaded Score Pack operator must be a string."
            )
        if gate.operator == "boolean_true":
            if gate.threshold is not None:
                _pack_error(
                    f"{path}/threshold",
                    "Boolean gate cannot contain a threshold.",
                )
            add_boolean_key(input_key, f"{path}/input_key")
        elif gate.operator == "less_than":
            threshold = _pack_scalar(gate.threshold, f"{path}/threshold", "positive")
            if type(threshold) is float:
                add_numeric_key(input_key, f"{path}/input_key")
            elif gate.mandatory:
                unresolved_required = True
        else:
            _pack_error(
                f"{path}/operator", "Loaded Score Pack operator is unsupported."
            )
    if not has_mandatory:
        _pack_error("/hard_gates", "Loaded Score Pack requires a mandatory gate.")

    if type(pack.physics) is not PhysicsSpec:
        _pack_error("/physics", "Loaded Score Pack physics spec has an invalid type.")
    if type(pack.physics.components) is not tuple or not pack.physics.components:
        _pack_error(
            "/physics/components",
            "Loaded Score Pack physics components must be a non-empty tuple.",
        )
    physics_ids: set[str] = set()
    physics_input_keys: set[str] = set()
    for index, component in enumerate(pack.physics.components):
        path = f"/physics/components/{index}"
        input_key, _, unresolved = _validate_component(component, path, physics_ids)
        if input_key in physics_input_keys:
            _pack_error(
                f"{path}/input_key",
                "Loaded Score Pack physics input key is duplicated in its scope.",
            )
        physics_input_keys.add(input_key)
        unresolved_required = unresolved_required or unresolved
        add_numeric_key(input_key, f"{path}/input_key")

    if type(pack.robustness) is not RobustnessSpec:
        _pack_error(
            "/robustness", "Loaded Score Pack robustness spec has an invalid type."
        )
    robustness_scalars = (
        ("tail_quantile", pack.robustness.tail_quantile, "probability"),
        ("blend_weights/mean", pack.robustness.mean_weight, "weight"),
        ("blend_weights/tail", pack.robustness.tail_weight, "weight"),
        ("threshold", pack.robustness.threshold, "positive"),
        ("sharpness", pack.robustness.sharpness, "positive"),
    )
    for member, value, rule in robustness_scalars:
        scalar = _pack_scalar(value, f"/robustness/{member}", rule)
        unresolved_required = unresolved_required or type(scalar) is str
    if type(pack.robustness.categories) is not tuple or not pack.robustness.categories:
        _pack_error(
            "/robustness/categories",
            "Loaded Score Pack robustness categories must be a non-empty tuple.",
        )
    category_ids: set[str] = set()
    robustness_input_keys: set[str] = set()
    for index, category in enumerate(pack.robustness.categories):
        path = f"/robustness/categories/{index}"
        if type(category) is not RobustnessCategory:
            _pack_error(path, "Loaded Score Pack category has an invalid type.")
        category_id = _pack_identifier(category.category_id, f"{path}/id")
        mean_key = _pack_identifier(category.mean_input_key, f"{path}/mean_input_key")
        tail_key = _pack_identifier(category.tail_input_key, f"{path}/tail_input_key")
        if category_id in category_ids:
            _pack_error(f"{path}/id", "Loaded Score Pack category id is duplicated.")
        category_ids.add(category_id)
        weight = _pack_scalar(category.weight, f"{path}/weight", "weight")
        unresolved_required = unresolved_required or type(weight) is str
        for key, member in (
            (mean_key, "mean_input_key"),
            (tail_key, "tail_input_key"),
        ):
            if key in robustness_input_keys:
                _pack_error(
                    f"{path}/{member}",
                    "Loaded Score Pack robustness input key is duplicated in its scope.",
                )
            robustness_input_keys.add(key)
            add_numeric_key(key, f"{path}/{member}")

    if type(pack.accuracy) is not AccuracySpec:
        _pack_error("/accuracy", "Loaded Score Pack accuracy spec has an invalid type.")
    if type(pack.accuracy.components) is not tuple or not pack.accuracy.components:
        _pack_error(
            "/accuracy/components",
            "Loaded Score Pack accuracy components must be a non-empty tuple.",
        )
    accuracy_ids: set[str] = set()
    accuracy_input_keys: set[str] = set()
    for index, component in enumerate(pack.accuracy.components):
        path = f"/accuracy/components/{index}"
        input_key, _, unresolved = _validate_component(component, path, accuracy_ids)
        if input_key in accuracy_input_keys:
            _pack_error(
                f"{path}/input_key",
                "Loaded Score Pack accuracy input key is duplicated in its scope.",
            )
        accuracy_input_keys.add(input_key)
        unresolved_required = unresolved_required or unresolved
        add_numeric_key(input_key, f"{path}/input_key")

    if type(pack.top_level_weights) is not tuple or len(pack.top_level_weights) != 3:
        _pack_error(
            "/weights", "Loaded Score Pack top-level weights must be a 3-tuple."
        )
    for index, value in enumerate(pack.top_level_weights):
        scalar = _pack_scalar(value, f"/weights/{_LEG_ORDER[index]}", "weight")
        unresolved_required = unresolved_required or type(scalar) is str

    if pack.ready is unresolved_required:
        _pack_error(
            "/ready", "Loaded Score Pack readiness is inconsistent with its values."
        )
    return tuple(numeric_keys), tuple(boolean_keys)


def _validate_input_identifier(value: object) -> str:
    if type(value) is not str:
        raise ScoreInputError(
            "score_input.key_invalid", "ScoreInput key must be an exact string."
        )
    try:
        return validate_canonical_identifier(value, "ScoreInput key")
    except ValueError as exc:
        raise ScoreInputError(
            "score_input.key_invalid", "ScoreInput key is not canonical."
        ) from exc


def _validate_ready_input(
    score_input: ScoreInput,
    pack: LoadedScorePack,
    expected_numeric: tuple[str, ...],
    expected_boolean: tuple[str, ...],
) -> None:
    if type(score_input.pack_pin) is not ScorePackPin:
        raise ScoreInputError(
            "score_input.pin_type", "ScoreInput pin must be an exact ScorePackPin."
        )
    if score_input.pack_pin != pack.pack_pin:
        raise ScoreInputError(
            "score_input.pin_mismatch", "ScoreInput pin does not match the Score Pack."
        )
    if type(score_input.numeric_inputs) is not tuple:
        raise ScoreInputError(
            "score_input.container_type", "Numeric ScoreInput entries must be a tuple."
        )
    if type(score_input.boolean_inputs) is not tuple:
        raise ScoreInputError(
            "score_input.container_type", "Boolean ScoreInput entries must be a tuple."
        )

    numeric_keys: set[str] = set()
    all_keys: set[str] = set()
    for entry in score_input.numeric_inputs:
        if type(entry) is not NumericInput:
            raise ScoreInputError(
                "score_input.entry_type", "Numeric ScoreInput entry has invalid type."
            )
        key = _validate_input_identifier(entry.key)
        if key in all_keys:
            raise ScoreInputError(
                "score_input.duplicate_key", "ScoreInput contains a duplicate key."
            )
        if (
            type(entry.value) is not float
            or not math.isfinite(entry.value)
            or entry.value < 0.0
        ):
            raise ScoreInputError(
                "score_input.value_invalid",
                "Numeric ScoreInput value must be finite and non-negative.",
            )
        numeric_keys.add(key)
        all_keys.add(key)

    boolean_keys: set[str] = set()
    for entry in score_input.boolean_inputs:
        if type(entry) is not BooleanInput:
            raise ScoreInputError(
                "score_input.entry_type", "Boolean ScoreInput entry has invalid type."
            )
        key = _validate_input_identifier(entry.key)
        if key in all_keys:
            raise ScoreInputError(
                "score_input.duplicate_key", "ScoreInput contains a duplicate key."
            )
        if type(entry.value) is not bool:
            raise ScoreInputError(
                "score_input.value_invalid",
                "Boolean ScoreInput value must be an exact Boolean.",
            )
        boolean_keys.add(key)
        all_keys.add(key)

    if numeric_keys != set(expected_numeric):
        raise ScoreInputError(
            "score_input.key_set",
            "Numeric ScoreInput keys do not exactly match the Score Pack.",
        )
    if boolean_keys != set(expected_boolean):
        raise ScoreInputError(
            "score_input.key_set",
            "Boolean ScoreInput keys do not exactly match the Score Pack.",
        )


def _ready_float(value: object, path: str) -> float:
    if type(value) is not float:
        _pack_error(path, "Ready Score Pack contains an unresolved scalar.")
    return value


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ScoringComputationError(
            "scoring.nonfinite", f"{label} is not finite under python_binary64_v1."
        )
    return value


def _nonnegative(value: float, label: str) -> float:
    _finite(value, label)
    if value < 0.0:
        raise ScoringComputationError(
            "scoring.range", f"{label} is outside the required non-negative range."
        )
    return value


def _unit_interval(value: float, label: str) -> float:
    _finite(value, label)
    if value < 0.0 or value > 1.0:
        raise ScoringComputationError(
            "scoring.range", f"{label} is outside [0.0, 1.0]."
        )
    return value


def _ordered_fsum(terms: tuple[float, ...], label: str) -> float:
    try:
        value = math.fsum(terms)
    except (OverflowError, ValueError) as exc:
        raise ScoringComputationError(
            "scoring.arithmetic", f"{label} could not be combined."
        ) from exc
    return _finite(value, label)


def _physics_score(score_input: ScoreInput, spec: PhysicsSpec) -> LegScore:
    components: list[ScalarScore] = []
    terms: list[float] = []
    for index, component in enumerate(spec.components):
        path = f"/physics/components/{index}"
        error = score_input.numeric_value(component.input_key)
        threshold = _ready_float(component.threshold, f"{path}/threshold")
        weight = _ready_float(component.weight, f"{path}/weight")
        if error < threshold:
            ratio = _unit_interval(error / threshold, "physics ratio")
            squared_ratio = _unit_interval(ratio * ratio, "physics squared ratio")
            margin = _unit_interval(1.0 - squared_ratio, "physics component")
        else:
            margin = 0.0
        components.append(ScalarScore(component.component_id, margin))
        terms.append(_unit_interval(weight * margin, "physics weighted term"))
    score = _unit_interval(
        _ordered_fsum(tuple(terms), "physics ordered sum"), "physics leg"
    )
    return LegScore("physics", tuple(components), score)


def _robustness_score(score_input: ScoreInput, spec: RobustnessSpec) -> LegScore:
    mean_weight = _ready_float(spec.mean_weight, "/robustness/blend_weights/mean")
    tail_weight = _ready_float(spec.tail_weight, "/robustness/blend_weights/tail")
    threshold = _ready_float(spec.threshold, "/robustness/threshold")
    sharpness = _ready_float(spec.sharpness, "/robustness/sharpness")
    components: list[ScalarScore] = []
    terms: list[float] = []
    for category in spec.categories:
        mean_value = score_input.numeric_value(category.mean_input_key)
        tail_value = score_input.numeric_value(category.tail_input_key)
        mean_term = _nonnegative(mean_weight * mean_value, "robustness mean blend term")
        tail_term = _nonnegative(tail_weight * tail_value, "robustness tail blend term")
        blended = _nonnegative(
            _ordered_fsum((mean_term, tail_term), "robustness ordered two-term blend"),
            "robustness blended error",
        )
        difference = _finite(blended - threshold, "robustness threshold difference")
        scaled = _finite(sharpness * difference, "robustness scaled difference")
        z_value = _finite(scaled / threshold, "robustness z value")
        try:
            if z_value >= 0.0:
                q_value = _unit_interval(
                    math.exp(-z_value), "robustness positive-branch exponential"
                )
                denominator = _finite(1.0 + q_value, "robustness denominator")
                category_score = _unit_interval(
                    q_value / denominator, "robustness category score"
                )
            else:
                q_value = _unit_interval(
                    math.exp(z_value), "robustness negative-branch exponential"
                )
                denominator = _finite(1.0 + q_value, "robustness denominator")
                category_score = _unit_interval(
                    1.0 / denominator, "robustness category score"
                )
        except OverflowError as exc:
            raise ScoringComputationError(
                "scoring.arithmetic", "Robustness exponential overflowed."
            ) from exc
        components.append(ScalarScore(category.category_id, category_score))
        weight = _ready_float(category.weight, "/robustness/categories/weight")
        terms.append(
            _unit_interval(weight * category_score, "robustness weighted category term")
        )
    score = _unit_interval(
        _ordered_fsum(tuple(terms), "robustness ordered sum"), "robustness leg"
    )
    return LegScore("robustness", tuple(components), score)


def _accuracy_score(score_input: ScoreInput, spec: AccuracySpec) -> LegScore:
    components: list[ScalarScore] = []
    terms: list[float] = []
    for index, component in enumerate(spec.components):
        path = f"/accuracy/components/{index}"
        error = score_input.numeric_value(component.input_key)
        threshold = _ready_float(component.threshold, f"{path}/threshold")
        weight = _ready_float(component.weight, f"{path}/weight")
        denominator = _finite(threshold + error, "accuracy denominator")
        if denominator <= 0.0:
            raise ScoringComputationError(
                "scoring.range", "Accuracy denominator is not positive."
            )
        component_score = _unit_interval(threshold / denominator, "accuracy component")
        components.append(ScalarScore(component.component_id, component_score))
        terms.append(_unit_interval(weight * component_score, "accuracy weighted term"))
    score = _unit_interval(
        _ordered_fsum(tuple(terms), "accuracy ordered sum"), "accuracy leg"
    )
    return LegScore("accuracy", tuple(components), score)


def _combined_score(
    leg_scores: tuple[LegScore, LegScore, LegScore],
    weights: tuple[float | str, float | str, float | str],
) -> float:
    component_scores = tuple(leg_score.score for leg_score in leg_scores)
    if any(component == 0.0 for component in component_scores):
        return 0.0

    log_terms: list[float] = []
    for index, component in enumerate(component_scores):
        weight = _ready_float(weights[index], f"/weights/{_LEG_ORDER[index]}")
        try:
            logarithm = math.log(component)
        except ValueError as exc:
            raise ScoringComputationError(
                "scoring.arithmetic", "Top-level logarithm is undefined."
            ) from exc
        logarithm = _finite(logarithm, "top-level logarithm")
        if logarithm > 0.0:
            raise ScoringComputationError(
                "scoring.range", "Top-level logarithm is unexpectedly positive."
            )
        term = _finite(weight * logarithm, "top-level log term")
        if term > 0.0:
            raise ScoringComputationError(
                "scoring.range", "Top-level log term is unexpectedly positive."
            )
        log_terms.append(term)
    log_sum = _ordered_fsum(tuple(log_terms), "top-level ordered log sum")
    if log_sum > 0.0:
        raise ScoringComputationError(
            "scoring.range", "Top-level ordered log sum is unexpectedly positive."
        )
    try:
        combined = math.exp(log_sum)
    except OverflowError as exc:
        raise ScoringComputationError(
            "scoring.arithmetic", "Top-level exponential overflowed."
        ) from exc
    return _unit_interval(combined, "combined score")


class ScoreEngine:
    """Stateless evaluator for one validated A5 fixture Score Pack."""

    @staticmethod
    def score(
        score_input: ScoreInput | None,
        pack: LoadedScorePack,
    ) -> InternalResult:
        """Evaluate one closed scalar input under one exact loaded pack."""
        if type(pack) is not LoadedScorePack:
            raise ScorePackSchemaError(
                "score_pack.engine_type",
                "",
                "ScoreEngine requires an exact LoadedScorePack.",
            )
        try:
            expected_numeric, expected_boolean = _validate_loaded_pack(pack)
        except ScorePackError:
            raise
        except AttributeError as exc:
            raise ScorePackSchemaError(
                "score_pack.engine_invalid",
                "",
                "Loaded Score Pack is structurally incomplete.",
            ) from exc

        if pack.ready is not True:
            if score_input is not None:
                raise ScoreInputError(
                    "score_input.pack_not_ready",
                    "An unready Score Pack accepts only exact None input.",
                )
            return InternalResult(
                ScoreStatus.PACK_NOT_READY,
                pack.pack_pin,
                (),
                (),
                None,
                False,
            )

        if score_input is None:
            raise ScoreInputError(
                "score_input.required", "A ready Score Pack requires ScoreInput."
            )
        if type(score_input) is not ScoreInput:
            raise ScoreInputError(
                "score_input.type", "ScoreEngine requires an exact ScoreInput."
            )
        try:
            _validate_ready_input(score_input, pack, expected_numeric, expected_boolean)
        except AttributeError as exc:
            raise ScoreInputError(
                "score_input.incomplete", "ScoreInput is structurally incomplete."
            ) from exc

        decisions: list[GateDecision] = []
        for gate in pack.hard_gates:
            if gate.operator == "less_than":
                if type(gate.threshold) is str:
                    continue
                threshold = _ready_float(gate.threshold, "/hard_gates/threshold")
                passed = score_input.numeric_value(gate.input_key) < threshold
            else:
                passed = score_input.boolean_value(gate.input_key) is True
            decisions.append(GateDecision(gate.gate_id, passed, gate.mandatory))
        gate_decisions = tuple(decisions)

        if any(
            decision.mandatory and not decision.passed for decision in gate_decisions
        ):
            return InternalResult(
                ScoreStatus.MANDATORY_GATE_FAILED,
                pack.pack_pin,
                gate_decisions,
                (),
                0.0,
                False,
            )

        physics = _physics_score(score_input, pack.physics)
        robustness = _robustness_score(score_input, pack.robustness)
        accuracy = _accuracy_score(score_input, pack.accuracy)
        leg_scores = (physics, robustness, accuracy)
        combined = _combined_score(leg_scores, pack.top_level_weights)
        return InternalResult(
            ScoreStatus.SCORED,
            pack.pack_pin,
            gate_decisions,
            leg_scores,
            combined,
            False,
        )


__all__ = ("ScoreEngine", "ScoringComputationError")
