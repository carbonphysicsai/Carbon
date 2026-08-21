"""Digest-first strict JSON loader for fixture-only A5 Score Packs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn

from carbon.registry import (
    ArtifactAccessError,
    ChallengeKey,
    is_sha256_digest,
    read_verified_artifact_bytes,
    validate_canonical_identifier,
    validate_version,
)
from carbon.scoring.model import (
    BooleanInput,
    NumericInput,
    ScoreInput,
    ScoreInputError,
    ScorePackPin,
)

SCORE_PACK_SCHEMA_VERSION = "1.0"
MAX_SCORE_PACK_BYTES = 1024 * 1024
UNRESOLVED_STATES = ("HUMAN_INPUT", "BLOCKED_FOR_LIVE_UNTIL_SET")

_NUMERICAL_PROFILE = "python_binary64_v1"
_COMBINATION = "weighted_geometric_logspace"
_MAX_NUMBER_TOKEN_LENGTH = 128
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "challenge_id",
    "challenge_version",
    "scoring_version",
    "generator_version_required",
    "generator_digest_required",
    "numerical_profile",
    "fixture_origin",
    "hard_gates",
    "physics",
    "robustness",
    "accuracy",
    "weights",
    "combination",
}
_THRESHOLD_GATE_FIELDS = {
    "operator",
    "id",
    "input_key",
    "mandatory",
    "threshold",
}
_BOOLEAN_GATE_FIELDS = {"operator", "id", "input_key", "mandatory"}
_COMPONENT_FIELDS = {"id", "input_key", "threshold", "weight"}
_CATEGORY_FIELDS = {
    "id",
    "mean_input_key",
    "tail_input_key",
    "weight",
}
_SAFE_PATH_MEMBERS = (
    _TOP_LEVEL_FIELDS
    | _THRESHOLD_GATE_FIELDS
    | _BOOLEAN_GATE_FIELDS
    | _COMPONENT_FIELDS
    | _CATEGORY_FIELDS
    | {
        "blend_weights",
        "categories",
        "components",
        "mean",
        "sharpness",
        "tail",
        "tail_quantile",
    }
)

PackScalar = float | str


class ScorePackError(Exception):
    """Base class for safe Score Pack failures with stable code and path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(message)


class ScorePackAccessError(ScorePackError):
    """The configured artifact could not be accessed safely."""


class ScorePackIntegrityError(ScorePackError):
    """The external digest contract was absent, invalid, or mismatched."""


class ScorePackParseError(ScorePackError):
    """Exact artifact bytes were not one strict UTF-8 JSON document."""


class ScorePackSchemaError(ScorePackError):
    """A parsed JSON document did not satisfy closed schema 1.0."""


class ScorePackPinError(ScorePackError):
    """The source-contained pin did not exactly match its expectation."""


class ScorePackInputError(ScorePackError):
    """Fixture input did not exactly match a ready loaded pack."""


@dataclass(frozen=True, slots=True)
class GateSpec:
    """One validated, declared-order hard-gate specification."""

    gate_id: str
    operator: str
    input_key: str
    mandatory: bool
    threshold: PackScalar | None


@dataclass(frozen=True, slots=True)
class WeightedComponent:
    """One validated physics or accuracy scalar component."""

    component_id: str
    input_key: str
    threshold: PackScalar
    weight: PackScalar


@dataclass(frozen=True, slots=True)
class PhysicsSpec:
    """Closed quadratic-barrier leg specification."""

    components: tuple[WeightedComponent, ...]


@dataclass(frozen=True, slots=True)
class RobustnessCategory:
    """One validated robustness category scalar-input binding."""

    category_id: str
    mean_input_key: str
    tail_input_key: str
    weight: PackScalar


@dataclass(frozen=True, slots=True)
class RobustnessSpec:
    """Closed tail-logistic leg specification."""

    tail_quantile: PackScalar
    mean_weight: PackScalar
    tail_weight: PackScalar
    threshold: PackScalar
    sharpness: PackScalar
    categories: tuple[RobustnessCategory, ...]


@dataclass(frozen=True, slots=True)
class AccuracySpec:
    """Closed reciprocal-error leg specification."""

    components: tuple[WeightedComponent, ...]


@dataclass(frozen=True, slots=True, init=False)
class LoadedScorePack:
    """One validated exact-byte fixture pack; direct construction is forbidden."""

    pack_pin: ScorePackPin
    ready: bool
    hard_gates: tuple[GateSpec, ...]
    physics: PhysicsSpec
    robustness: RobustnessSpec
    accuracy: AccuracySpec
    top_level_weights: tuple[PackScalar, PackScalar, PackScalar]

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ScorePackSchemaError(
            "score_pack.direct_init",
            "",
            "LoadedScorePack must be created by the verified artifact loader.",
        )

    def fixture_score_input(
        self,
        *,
        numeric_inputs: tuple[NumericInput, ...],
        boolean_inputs: tuple[BooleanInput, ...],
    ) -> ScoreInput:
        """Build the fixture-only closed input in deterministic pack order."""
        if self.ready is not True:
            raise ScorePackInputError(
                "score_pack.input_not_ready",
                "",
                "An unready Score Pack cannot construct scientific input.",
            )
        if type(numeric_inputs) is not tuple:
            raise ScorePackInputError(
                "score_pack.input_type",
                "/numeric_inputs",
                "Fixture numeric inputs must be an exact tuple.",
            )
        if type(boolean_inputs) is not tuple:
            raise ScorePackInputError(
                "score_pack.input_type",
                "/boolean_inputs",
                "Fixture Boolean inputs must be an exact tuple.",
            )

        numeric_by_key: dict[str, NumericInput] = {}
        all_keys: set[str] = set()
        for index, entry in enumerate(numeric_inputs):
            path = f"/numeric_inputs/{index}"
            if type(entry) is not NumericInput:
                raise ScorePackInputError(
                    "score_pack.input_entry_type",
                    path,
                    "Fixture numeric input contains an invalid entry.",
                )
            key = _revalidate_numeric_input(entry, path)
            if key in all_keys:
                raise ScorePackInputError(
                    "score_pack.input_duplicate",
                    path,
                    "Fixture input contains a duplicate key.",
                )
            all_keys.add(key)
            numeric_by_key[key] = entry

        boolean_by_key: dict[str, BooleanInput] = {}
        for index, entry in enumerate(boolean_inputs):
            path = f"/boolean_inputs/{index}"
            if type(entry) is not BooleanInput:
                raise ScorePackInputError(
                    "score_pack.input_entry_type",
                    path,
                    "Fixture Boolean input contains an invalid entry.",
                )
            key = _revalidate_boolean_input(entry, path)
            if key in all_keys:
                raise ScorePackInputError(
                    "score_pack.input_duplicate",
                    path,
                    "Fixture input contains a duplicate key.",
                )
            all_keys.add(key)
            boolean_by_key[key] = entry

        expected_numeric, expected_boolean = _expected_input_keys(self)
        if set(numeric_by_key) != set(expected_numeric):
            raise ScorePackInputError(
                "score_pack.input_key_set",
                "/numeric_inputs",
                "Fixture numeric input keys do not exactly match the loaded pack.",
            )
        if set(boolean_by_key) != set(expected_boolean):
            raise ScorePackInputError(
                "score_pack.input_key_set",
                "/boolean_inputs",
                "Fixture Boolean input keys do not exactly match the loaded pack.",
            )

        try:
            return ScoreInput._from_validated_fixture(
                pack_pin=self.pack_pin,
                numeric_inputs=tuple(numeric_by_key[key] for key in expected_numeric),
                boolean_inputs=tuple(boolean_by_key[key] for key in expected_boolean),
            )
        except ScoreInputError as exc:
            raise ScorePackInputError(
                "score_pack.input_invalid",
                "",
                "Fixture input could not satisfy the closed scoring boundary.",
            ) from exc


@dataclass(frozen=True, slots=True)
class _NumberToken:
    lexeme: str


RawScalar = _NumberToken | str


class _JSONObject(list[tuple[str, Any]]):
    pass


class _InvalidConstant(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _RawGate:
    gate_id: str
    operator: str
    input_key: str
    mandatory: bool
    threshold: RawScalar | None


@dataclass(frozen=True, slots=True)
class _RawComponent:
    component_id: str
    input_key: str
    threshold: RawScalar
    weight: RawScalar


@dataclass(frozen=True, slots=True)
class _RawCategory:
    category_id: str
    mean_input_key: str
    tail_input_key: str
    weight: RawScalar


@dataclass(frozen=True, slots=True)
class _RawRobustness:
    tail_quantile: RawScalar
    mean_weight: RawScalar
    tail_weight: RawScalar
    threshold: RawScalar
    sharpness: RawScalar
    categories: tuple[_RawCategory, ...]


@dataclass(frozen=True, slots=True)
class _ScalarSlot:
    value: RawScalar
    path: str
    rule: str
    score_bearing: bool


def _parse_number(lexeme: str) -> _NumberToken:
    return _NumberToken(lexeme)


def _reject_constant(value: str) -> NoReturn:
    del value
    raise _InvalidConstant


def _materialize(value: Any, path: str) -> Any:
    if type(value) is _JSONObject:
        seen: set[str] = set()
        for key, _ in value:
            if key in seen:
                raise ScorePackParseError(
                    "score_pack.json_duplicate",
                    path,
                    "Score Pack JSON contains a duplicate object member.",
                )
            seen.add(key)
        return {
            key: _materialize(child, _child_path(path, key)) for key, child in value
        }
    if type(value) is list:
        return [
            _materialize(child, f"{path}/{index}") for index, child in enumerate(value)
        ]
    return value


def _strict_json(payload: bytes) -> dict[str, Any]:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ScorePackParseError(
            "score_pack.bom", "", "Score Pack JSON must not contain a UTF-8 BOM."
        )
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScorePackParseError(
            "score_pack.utf8", "", "Score Pack bytes are not strict UTF-8."
        ) from exc
    try:
        parsed = json.loads(
            source,
            object_pairs_hook=_JSONObject,
            parse_float=_parse_number,
            parse_int=_parse_number,
            parse_constant=_reject_constant,
        )
        materialized = _materialize(parsed, "")
    except ScorePackParseError:
        raise
    except _InvalidConstant as exc:
        raise ScorePackParseError(
            "score_pack.json_constant",
            "",
            "Score Pack JSON contains a forbidden non-JSON constant.",
        ) from exc
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ScorePackParseError(
            "score_pack.json_invalid",
            "",
            "Score Pack bytes are not one strict JSON document.",
        ) from exc
    if type(materialized) is not dict:
        raise ScorePackParseError(
            "score_pack.top_level_type",
            "",
            "Score Pack JSON top level must be an object.",
        )
    return materialized


def _child_path(path: str, member: str) -> str:
    if member not in _SAFE_PATH_MEMBERS:
        return path
    escaped = member.replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"


def _object(value: object, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ScorePackSchemaError(
            "score_pack.field_type",
            path,
            "Score Pack field has an invalid JSON type.",
        )
    return value


def _array(value: object, path: str) -> list[Any]:
    if type(value) is not list:
        raise ScorePackSchemaError(
            "score_pack.field_type",
            path,
            "Score Pack field has an invalid JSON type.",
        )
    return value


def _exact_fields(value: dict[str, Any], fields: set[str], path: str) -> None:
    for field in sorted(fields):
        if field not in value:
            raise ScorePackSchemaError(
                "score_pack.field_required",
                _child_path(path, field),
                "Required Score Pack field is missing.",
            )
    if set(value) != fields:
        raise ScorePackSchemaError(
            "score_pack.field_unknown",
            path,
            "Score Pack object contains an unknown field.",
        )


def _exact_string(value: object, path: str) -> str:
    if type(value) is not str:
        raise ScorePackSchemaError(
            "score_pack.field_type",
            path,
            "Score Pack field must be an exact string.",
        )
    return value


def _literal(value: object, expected: str, path: str) -> str:
    actual = _exact_string(value, path)
    if actual != expected:
        raise ScorePackSchemaError(
            "score_pack.field_value",
            path,
            "Score Pack field has an unsupported value.",
        )
    return actual


def _identifier(value: object, path: str) -> str:
    identifier = _exact_string(value, path)
    try:
        return validate_canonical_identifier(identifier, "Score Pack identifier")
    except ValueError as exc:
        raise ScorePackSchemaError(
            "score_pack.identifier_invalid",
            path,
            "Score Pack identifier is not canonical.",
        ) from exc


def _version(value: object, path: str) -> str:
    version = _exact_string(value, path)
    try:
        return validate_version(version)
    except ValueError as exc:
        raise ScorePackSchemaError(
            "score_pack.version_invalid",
            path,
            "Score Pack version is not canonical.",
        ) from exc


def _number_or_state(value: object, path: str) -> RawScalar:
    if type(value) is _NumberToken:
        return value
    if type(value) is str and value in UNRESOLVED_STATES:
        return value
    raise ScorePackSchemaError(
        "score_pack.numeric_type",
        path,
        "Score Pack numeric field must be a JSON number or explicit state.",
    )


def _parse_pin(document: dict[str, Any], scoring_digest: str) -> ScorePackPin:
    schema_version = _literal(
        document["schema_version"], SCORE_PACK_SCHEMA_VERSION, "/schema_version"
    )
    challenge_id = _identifier(document["challenge_id"], "/challenge_id")
    challenge_version = _version(document["challenge_version"], "/challenge_version")
    scoring_version = _version(document["scoring_version"], "/scoring_version")
    generator_version = _version(
        document["generator_version_required"], "/generator_version_required"
    )
    generator_digest = _exact_string(
        document["generator_digest_required"], "/generator_digest_required"
    )
    if not is_sha256_digest(generator_digest):
        raise ScorePackSchemaError(
            "score_pack.digest_invalid",
            "/generator_digest_required",
            "Score Pack generator digest is not canonical tagged SHA-256.",
        )
    numerical_profile = _literal(
        document["numerical_profile"], _NUMERICAL_PROFILE, "/numerical_profile"
    )
    fixture_origin = document["fixture_origin"]
    if type(fixture_origin) is not bool:
        raise ScorePackSchemaError(
            "score_pack.field_type",
            "/fixture_origin",
            "Score Pack fixture origin must be an exact Boolean.",
        )
    if fixture_origin is not True:
        raise ScorePackSchemaError(
            "score_pack.fixture_only",
            "/fixture_origin",
            "A5 accepts only fixture-origin Score Packs.",
        )
    try:
        return ScorePackPin(
            challenge_key=ChallengeKey(challenge_id, challenge_version),
            scoring_version=scoring_version,
            scoring_digest=scoring_digest,
            generator_version_required=generator_version,
            generator_digest_required=generator_digest,
            schema_version=schema_version,
            numerical_profile=numerical_profile,
            fixture_origin=fixture_origin,
        )
    except (TypeError, ValueError) as exc:  # defensive convergence on model checks
        raise ScorePackSchemaError(
            "score_pack.pin_invalid", "", "Score Pack pin is invalid."
        ) from exc


def _parse_gates(value: object) -> tuple[_RawGate, ...]:
    records = _array(value, "/hard_gates")
    if not records:
        raise ScorePackSchemaError(
            "score_pack.array_empty",
            "/hard_gates",
            "Score Pack hard-gate array must not be empty.",
        )
    gates: list[_RawGate] = []
    identifiers: set[str] = set()
    input_keys: set[str] = set()
    for index, raw_record in enumerate(records):
        path = f"/hard_gates/{index}"
        record = _object(raw_record, path)
        if "operator" not in record:
            raise ScorePackSchemaError(
                "score_pack.field_required",
                f"{path}/operator",
                "Required Score Pack field is missing.",
            )
        operator = _exact_string(record["operator"], f"{path}/operator")
        if operator == "less_than":
            _exact_fields(record, _THRESHOLD_GATE_FIELDS, path)
        elif operator == "boolean_true":
            _exact_fields(record, _BOOLEAN_GATE_FIELDS, path)
        else:
            raise ScorePackSchemaError(
                "score_pack.operator_invalid",
                f"{path}/operator",
                "Score Pack operator is not supported by schema 1.0.",
            )
        gate_id = _identifier(record["id"], f"{path}/id")
        input_key = _identifier(record["input_key"], f"{path}/input_key")
        mandatory = record["mandatory"]
        if type(mandatory) is not bool:
            raise ScorePackSchemaError(
                "score_pack.field_type",
                f"{path}/mandatory",
                "Score Pack mandatory flag must be an exact Boolean.",
            )
        if gate_id in identifiers:
            raise ScorePackSchemaError(
                "score_pack.identifier_duplicate",
                f"{path}/id",
                "Score Pack identifier is duplicated in its scope.",
            )
        if input_key in input_keys:
            raise ScorePackSchemaError(
                "score_pack.input_key_duplicate",
                f"{path}/input_key",
                "Score Pack input key is duplicated in its scope.",
            )
        identifiers.add(gate_id)
        input_keys.add(input_key)
        threshold = (
            _number_or_state(record["threshold"], f"{path}/threshold")
            if operator == "less_than"
            else None
        )
        gates.append(_RawGate(gate_id, operator, input_key, mandatory, threshold))
    if not any(gate.mandatory for gate in gates):
        raise ScorePackSchemaError(
            "score_pack.mandatory_gate_required",
            "/hard_gates",
            "Score Pack requires at least one mandatory hard gate.",
        )
    return tuple(gates)


def _parse_components(value: object, path: str) -> tuple[_RawComponent, ...]:
    records = _array(value, path)
    if not records:
        raise ScorePackSchemaError(
            "score_pack.array_empty",
            path,
            "Score Pack component array must not be empty.",
        )
    components: list[_RawComponent] = []
    identifiers: set[str] = set()
    input_keys: set[str] = set()
    for index, raw_record in enumerate(records):
        item_path = f"{path}/{index}"
        record = _object(raw_record, item_path)
        _exact_fields(record, _COMPONENT_FIELDS, item_path)
        component_id = _identifier(record["id"], f"{item_path}/id")
        input_key = _identifier(record["input_key"], f"{item_path}/input_key")
        if component_id in identifiers:
            raise ScorePackSchemaError(
                "score_pack.identifier_duplicate",
                f"{item_path}/id",
                "Score Pack identifier is duplicated in its scope.",
            )
        if input_key in input_keys:
            raise ScorePackSchemaError(
                "score_pack.input_key_duplicate",
                f"{item_path}/input_key",
                "Score Pack input key is duplicated in its scope.",
            )
        identifiers.add(component_id)
        input_keys.add(input_key)
        components.append(
            _RawComponent(
                component_id,
                input_key,
                _number_or_state(record["threshold"], f"{item_path}/threshold"),
                _number_or_state(record["weight"], f"{item_path}/weight"),
            )
        )
    return tuple(components)


def _parse_physics(value: object) -> tuple[_RawComponent, ...]:
    record = _object(value, "/physics")
    _exact_fields(record, {"operator", "components"}, "/physics")
    _literal(record["operator"], "quadratic_barrier", "/physics/operator")
    return _parse_components(record["components"], "/physics/components")


def _parse_accuracy(value: object) -> tuple[_RawComponent, ...]:
    record = _object(value, "/accuracy")
    _exact_fields(record, {"operator", "components"}, "/accuracy")
    _literal(record["operator"], "reciprocal_error", "/accuracy/operator")
    return _parse_components(record["components"], "/accuracy/components")


def _parse_robustness(value: object) -> _RawRobustness:
    path = "/robustness"
    record = _object(value, path)
    _exact_fields(
        record,
        {
            "operator",
            "tail_quantile",
            "blend_weights",
            "threshold",
            "sharpness",
            "categories",
        },
        path,
    )
    _literal(record["operator"], "tail_logistic", f"{path}/operator")
    blend = _object(record["blend_weights"], f"{path}/blend_weights")
    _exact_fields(blend, {"mean", "tail"}, f"{path}/blend_weights")
    categories_raw = _array(record["categories"], f"{path}/categories")
    if not categories_raw:
        raise ScorePackSchemaError(
            "score_pack.array_empty",
            f"{path}/categories",
            "Score Pack category array must not be empty.",
        )
    categories: list[_RawCategory] = []
    identifiers: set[str] = set()
    input_keys: set[str] = set()
    for index, raw_category in enumerate(categories_raw):
        item_path = f"{path}/categories/{index}"
        category = _object(raw_category, item_path)
        _exact_fields(category, _CATEGORY_FIELDS, item_path)
        category_id = _identifier(category["id"], f"{item_path}/id")
        mean_key = _identifier(
            category["mean_input_key"], f"{item_path}/mean_input_key"
        )
        tail_key = _identifier(
            category["tail_input_key"], f"{item_path}/tail_input_key"
        )
        if category_id in identifiers:
            raise ScorePackSchemaError(
                "score_pack.identifier_duplicate",
                f"{item_path}/id",
                "Score Pack identifier is duplicated in its scope.",
            )
        if mean_key in input_keys or tail_key in input_keys or mean_key == tail_key:
            raise ScorePackSchemaError(
                "score_pack.input_key_duplicate",
                item_path,
                "Score Pack input key is duplicated in its scope.",
            )
        identifiers.add(category_id)
        input_keys.update((mean_key, tail_key))
        categories.append(
            _RawCategory(
                category_id,
                mean_key,
                tail_key,
                _number_or_state(category["weight"], f"{item_path}/weight"),
            )
        )
    return _RawRobustness(
        tail_quantile=_number_or_state(
            record["tail_quantile"], f"{path}/tail_quantile"
        ),
        mean_weight=_number_or_state(blend["mean"], f"{path}/blend_weights/mean"),
        tail_weight=_number_or_state(blend["tail"], f"{path}/blend_weights/tail"),
        threshold=_number_or_state(record["threshold"], f"{path}/threshold"),
        sharpness=_number_or_state(record["sharpness"], f"{path}/sharpness"),
        categories=tuple(categories),
    )


def _parse_top_weights(value: object) -> tuple[RawScalar, RawScalar, RawScalar]:
    weights = _object(value, "/weights")
    _exact_fields(weights, {"physics", "robustness", "accuracy"}, "/weights")
    return (
        _number_or_state(weights["physics"], "/weights/physics"),
        _number_or_state(weights["robustness"], "/weights/robustness"),
        _number_or_state(weights["accuracy"], "/weights/accuracy"),
    )


def _scalar_slots(
    gates: tuple[_RawGate, ...],
    physics: tuple[_RawComponent, ...],
    robustness: _RawRobustness,
    accuracy: tuple[_RawComponent, ...],
    top_weights: tuple[RawScalar, RawScalar, RawScalar],
) -> tuple[_ScalarSlot, ...]:
    slots: list[_ScalarSlot] = []
    for index, gate in enumerate(gates):
        if gate.operator == "less_than":
            assert gate.threshold is not None
            slots.append(
                _ScalarSlot(
                    gate.threshold,
                    f"/hard_gates/{index}/threshold",
                    "positive",
                    gate.mandatory,
                )
            )
    for index, component in enumerate(physics):
        path = f"/physics/components/{index}"
        slots.extend(
            (
                _ScalarSlot(component.threshold, f"{path}/threshold", "positive", True),
                _ScalarSlot(component.weight, f"{path}/weight", "weight", True),
            )
        )
    slots.extend(
        (
            _ScalarSlot(
                robustness.tail_quantile,
                "/robustness/tail_quantile",
                "probability",
                True,
            ),
            _ScalarSlot(
                robustness.mean_weight,
                "/robustness/blend_weights/mean",
                "weight",
                True,
            ),
            _ScalarSlot(
                robustness.tail_weight,
                "/robustness/blend_weights/tail",
                "weight",
                True,
            ),
            _ScalarSlot(
                robustness.threshold,
                "/robustness/threshold",
                "positive",
                True,
            ),
            _ScalarSlot(
                robustness.sharpness,
                "/robustness/sharpness",
                "positive",
                True,
            ),
        )
    )
    for index, category in enumerate(robustness.categories):
        slots.append(
            _ScalarSlot(
                category.weight,
                f"/robustness/categories/{index}/weight",
                "weight",
                True,
            )
        )
    for index, component in enumerate(accuracy):
        path = f"/accuracy/components/{index}"
        slots.extend(
            (
                _ScalarSlot(component.threshold, f"{path}/threshold", "positive", True),
                _ScalarSlot(component.weight, f"{path}/weight", "weight", True),
            )
        )
    for name, value in zip(("physics", "robustness", "accuracy"), top_weights):
        slots.append(_ScalarSlot(value, f"/weights/{name}", "weight", True))
    return tuple(slots)


def _validate_number(slot: _ScalarSlot) -> tuple[Decimal, float]:
    token = slot.value
    assert type(token) is _NumberToken
    if len(token.lexeme) > _MAX_NUMBER_TOKEN_LENGTH:
        raise ScorePackSchemaError(
            "score_pack.numeric_token_too_long",
            slot.path,
            "Score Pack numeric token exceeds the schema limit.",
        )
    try:
        decimal_value = Decimal(token.lexeme)
    except InvalidOperation as exc:
        raise ScorePackSchemaError(
            "score_pack.numeric_invalid",
            slot.path,
            "Score Pack numeric token is invalid.",
        ) from exc
    if not decimal_value.is_finite():
        raise ScorePackSchemaError(
            "score_pack.numeric_nonfinite",
            slot.path,
            "Score Pack numeric value must remain finite.",
        )
    zero = Decimal(0)
    one = Decimal(1)
    if decimal_value <= zero:
        raise ScorePackSchemaError(
            "score_pack.numeric_range",
            slot.path,
            "Score Pack numeric value violates its required range.",
        )
    if slot.rule == "weight" and decimal_value > one:
        raise ScorePackSchemaError(
            "score_pack.numeric_range",
            slot.path,
            "Score Pack numeric value violates its required range.",
        )
    if slot.rule == "probability" and decimal_value >= one:
        raise ScorePackSchemaError(
            "score_pack.numeric_range",
            slot.path,
            "Score Pack numeric value violates its required range.",
        )
    try:
        binary_value = float(decimal_value)
    except (OverflowError, ValueError) as exc:
        raise ScorePackSchemaError(
            "score_pack.numeric_binary64",
            slot.path,
            "Score Pack numeric value cannot be represented by the profile.",
        ) from exc
    if not math.isfinite(binary_value) or binary_value <= 0.0:
        raise ScorePackSchemaError(
            "score_pack.numeric_binary64",
            slot.path,
            "Score Pack numeric value cannot be represented by the profile.",
        )
    if slot.rule == "probability" and binary_value >= 1.0:
        raise ScorePackSchemaError(
            "score_pack.numeric_binary64",
            slot.path,
            "Score Pack numeric value cannot be represented by the profile.",
        )
    return decimal_value, binary_value


def _exact_unit_sum(values: tuple[Decimal, ...], path: str) -> None:
    tuples = tuple(value.as_tuple() for value in values)
    exponents = tuple(item.exponent for item in tuples)
    if any(type(exponent) is not int for exponent in exponents):
        raise ScorePackSchemaError(
            "score_pack.weight_sum", path, "Score Pack weight map is not unit-sum."
        )
    common_exponent = min(0, *(int(exponent) for exponent in exponents))
    total = 0
    for item in tuples:
        coefficient = 0
        for digit in item.digits:
            coefficient = coefficient * 10 + digit
        total += coefficient * (10 ** (int(item.exponent) - common_exponent))
    if total != 10 ** (-common_exponent):
        raise ScorePackSchemaError(
            "score_pack.weight_sum", path, "Score Pack weight map is not unit-sum."
        )


def _validate_input_key_types(
    gates: tuple[_RawGate, ...],
    physics: tuple[_RawComponent, ...],
    robustness: _RawRobustness,
    accuracy: tuple[_RawComponent, ...],
) -> None:
    entries: list[tuple[str, str, str]] = []
    for index, gate in enumerate(gates):
        scalar_type = "boolean" if gate.operator == "boolean_true" else "numeric"
        entries.append((gate.input_key, scalar_type, f"/hard_gates/{index}/input_key"))
    entries.extend(
        (
            component.input_key,
            "numeric",
            f"/physics/components/{index}/input_key",
        )
        for index, component in enumerate(physics)
    )
    for index, category in enumerate(robustness.categories):
        entries.extend(
            (
                (
                    category.mean_input_key,
                    "numeric",
                    f"/robustness/categories/{index}/mean_input_key",
                ),
                (
                    category.tail_input_key,
                    "numeric",
                    f"/robustness/categories/{index}/tail_input_key",
                ),
            )
        )
    entries.extend(
        (
            component.input_key,
            "numeric",
            f"/accuracy/components/{index}/input_key",
        )
        for index, component in enumerate(accuracy)
    )
    declared_types: dict[str, str] = {}
    for key, scalar_type, path in entries:
        prior_type = declared_types.setdefault(key, scalar_type)
        if prior_type != scalar_type:
            raise ScorePackSchemaError(
                "score_pack.input_key_type_collision",
                path,
                "Score Pack input key is declared as both numeric and Boolean.",
            )


def _resolved(value: RawScalar, binary_values: dict[int, float]) -> PackScalar:
    if type(value) is _NumberToken:
        return binary_values[id(value)]
    return value


def _make_loaded_pack(
    *,
    pack_pin: ScorePackPin,
    ready: bool,
    gates: tuple[_RawGate, ...],
    physics: tuple[_RawComponent, ...],
    robustness: _RawRobustness,
    accuracy: tuple[_RawComponent, ...],
    top_weights: tuple[RawScalar, RawScalar, RawScalar],
    binary_values: dict[int, float],
) -> LoadedScorePack:
    instance = object.__new__(LoadedScorePack)
    object.__setattr__(instance, "pack_pin", pack_pin)
    object.__setattr__(instance, "ready", ready)
    object.__setattr__(
        instance,
        "hard_gates",
        tuple(
            GateSpec(
                gate.gate_id,
                gate.operator,
                gate.input_key,
                gate.mandatory,
                (
                    None
                    if gate.threshold is None
                    else _resolved(gate.threshold, binary_values)
                ),
            )
            for gate in gates
        ),
    )
    object.__setattr__(
        instance,
        "physics",
        PhysicsSpec(
            tuple(
                WeightedComponent(
                    component.component_id,
                    component.input_key,
                    _resolved(component.threshold, binary_values),
                    _resolved(component.weight, binary_values),
                )
                for component in physics
            )
        ),
    )
    object.__setattr__(
        instance,
        "robustness",
        RobustnessSpec(
            _resolved(robustness.tail_quantile, binary_values),
            _resolved(robustness.mean_weight, binary_values),
            _resolved(robustness.tail_weight, binary_values),
            _resolved(robustness.threshold, binary_values),
            _resolved(robustness.sharpness, binary_values),
            tuple(
                RobustnessCategory(
                    category.category_id,
                    category.mean_input_key,
                    category.tail_input_key,
                    _resolved(category.weight, binary_values),
                )
                for category in robustness.categories
            ),
        ),
    )
    object.__setattr__(
        instance,
        "accuracy",
        AccuracySpec(
            tuple(
                WeightedComponent(
                    component.component_id,
                    component.input_key,
                    _resolved(component.threshold, binary_values),
                    _resolved(component.weight, binary_values),
                )
                for component in accuracy
            )
        ),
    )
    object.__setattr__(
        instance,
        "top_level_weights",
        tuple(_resolved(value, binary_values) for value in top_weights),
    )
    return instance


def _expected_input_keys(
    pack: LoadedScorePack,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    numeric: list[str] = []
    boolean: list[str] = []
    numeric_seen: set[str] = set()
    boolean_seen: set[str] = set()

    def append_once(values: list[str], seen: set[str], key: str) -> None:
        if key not in seen:
            seen.add(key)
            values.append(key)

    for gate in pack.hard_gates:
        if gate.operator == "boolean_true":
            append_once(boolean, boolean_seen, gate.input_key)
        elif type(gate.threshold) is float:
            append_once(numeric, numeric_seen, gate.input_key)
    for component in pack.physics.components:
        append_once(numeric, numeric_seen, component.input_key)
    for category in pack.robustness.categories:
        append_once(numeric, numeric_seen, category.mean_input_key)
        append_once(numeric, numeric_seen, category.tail_input_key)
    for component in pack.accuracy.components:
        append_once(numeric, numeric_seen, component.input_key)
    return tuple(numeric), tuple(boolean)


def _revalidate_numeric_input(entry: NumericInput, path: str) -> str:
    try:
        key = entry.key
        value = entry.value
    except AttributeError as exc:
        raise ScorePackInputError(
            "score_pack.input_entry_invalid",
            path,
            "Fixture numeric input entry is malformed.",
        ) from exc
    try:
        validate_canonical_identifier(key, "ScoreInput key")
    except (TypeError, ValueError) as exc:
        raise ScorePackInputError(
            "score_pack.input_key_invalid",
            path,
            "Fixture input key is not canonical.",
        ) from exc
    if type(value) is not float or not math.isfinite(value) or value < 0:
        raise ScorePackInputError(
            "score_pack.input_value_invalid",
            path,
            "Fixture numeric input is not a finite non-negative binary64 value.",
        )
    return key


def _revalidate_boolean_input(entry: BooleanInput, path: str) -> str:
    try:
        key = entry.key
        value = entry.value
    except AttributeError as exc:
        raise ScorePackInputError(
            "score_pack.input_entry_invalid",
            path,
            "Fixture Boolean input entry is malformed.",
        ) from exc
    try:
        validate_canonical_identifier(key, "ScoreInput key")
    except (TypeError, ValueError) as exc:
        raise ScorePackInputError(
            "score_pack.input_key_invalid",
            path,
            "Fixture input key is not canonical.",
        ) from exc
    if type(value) is not bool:
        raise ScorePackInputError(
            "score_pack.input_value_invalid",
            path,
            "Fixture Boolean input is not an exact Boolean.",
        )
    return key


def load_score_pack(
    artifact_root: Path,
    relative_path: object,
    expected_pin: ScorePackPin,
) -> LoadedScorePack:
    """Load one exact-byte, digest-verified, fixture-only Score Pack."""
    if type(expected_pin) is not ScorePackPin:
        raise ScorePackPinError(
            "score_pack.expected_pin_type",
            "",
            "Expected Score Pack pin must be an exact ScorePackPin.",
        )

    try:
        payload = read_verified_artifact_bytes(
            artifact_root,
            relative_path,
            expected_pin.scoring_digest,
            max_bytes=MAX_SCORE_PACK_BYTES,
        )
    except ArtifactAccessError as exc:
        error_type: type[ScorePackError]
        if exc.code in {"artifact.digest_invalid", "artifact.digest_mismatch"}:
            error_type = ScorePackIntegrityError
            message = "Score Pack artifact failed exact-byte integrity verification."
        else:
            error_type = ScorePackAccessError
            message = "Score Pack artifact could not be accessed safely."
        raise error_type(exc.code, "", message) from exc

    document = _strict_json(payload)
    _exact_fields(document, _TOP_LEVEL_FIELDS, "")
    source_pin = _parse_pin(document, expected_pin.scoring_digest)
    gates = _parse_gates(document["hard_gates"])
    physics = _parse_physics(document["physics"])
    robustness = _parse_robustness(document["robustness"])
    accuracy = _parse_accuracy(document["accuracy"])
    top_weights = _parse_top_weights(document["weights"])
    _literal(document["combination"], _COMBINATION, "/combination")
    _validate_input_key_types(gates, physics, robustness, accuracy)

    if source_pin != expected_pin:
        raise ScorePackPinError(
            "score_pack.pin_mismatch",
            "",
            "Score Pack pin does not exactly match the external expectation.",
        )

    slots = _scalar_slots(gates, physics, robustness, accuracy, top_weights)
    decimals: dict[int, Decimal] = {}
    binary_values: dict[int, float] = {}
    for slot in slots:
        if type(slot.value) is _NumberToken:
            decimal_value, binary_value = _validate_number(slot)
            decimals[id(slot.value)] = decimal_value
            binary_values[id(slot.value)] = binary_value

    ready = not any(type(slot.value) is str and slot.score_bearing for slot in slots)
    if ready:
        _exact_unit_sum(
            tuple(decimals[id(component.weight)] for component in physics),
            "/physics/components",
        )
        _exact_unit_sum(
            (
                decimals[id(robustness.mean_weight)],
                decimals[id(robustness.tail_weight)],
            ),
            "/robustness/blend_weights",
        )
        _exact_unit_sum(
            tuple(decimals[id(category.weight)] for category in robustness.categories),
            "/robustness/categories",
        )
        _exact_unit_sum(
            tuple(decimals[id(component.weight)] for component in accuracy),
            "/accuracy/components",
        )
        _exact_unit_sum(
            tuple(decimals[id(value)] for value in top_weights),
            "/weights",
        )

    return _make_loaded_pack(
        pack_pin=source_pin,
        ready=ready,
        gates=gates,
        physics=physics,
        robustness=robustness,
        accuracy=accuracy,
        top_weights=top_weights,
        binary_values=binary_values,
    )


__all__ = (
    "MAX_SCORE_PACK_BYTES",
    "SCORE_PACK_SCHEMA_VERSION",
    "UNRESOLVED_STATES",
    "AccuracySpec",
    "GateSpec",
    "LoadedScorePack",
    "PhysicsSpec",
    "RobustnessCategory",
    "RobustnessSpec",
    "ScorePackAccessError",
    "ScorePackError",
    "ScorePackInputError",
    "ScorePackIntegrityError",
    "ScorePackParseError",
    "ScorePackPinError",
    "ScorePackSchemaError",
    "WeightedComponent",
    "load_score_pack",
)
