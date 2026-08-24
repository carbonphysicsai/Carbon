"""CPU acceptance tests for A5's fixture-only scoring boundary."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields
from decimal import localcontext
from pathlib import Path
from typing import Any

import pytest

from carbon.registry import ChallengeKey
from carbon.scoring import ScoreEngine, ScoringComputationError
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
    MAX_SCORE_PACK_BYTES,
    LoadedScorePack,
    ScorePackAccessError,
    ScorePackError,
    ScorePackInputError,
    ScorePackIntegrityError,
    ScorePackParseError,
    ScorePackPinError,
    ScorePackSchemaError,
    load_score_pack,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_RELATIVE_PATH = Path("tests/fixtures/score_packs/a5_fixture_v1.json")
FIXTURE_PATH = REPOSITORY_ROOT / FIXTURE_RELATIVE_PATH
FIXTURE_DIGEST = (
    "sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
)
GENERATOR_DIGEST = "sha256:" + "1" * 64
LEG_ORDER = ("physics", "robustness", "accuracy")
FIXTURE_NUMERIC_VALUES = (
    ("gate_error", 0.25),
    ("diagnostic_error", 0.5),
    ("physics_error", 0.25),
    ("robust_mean_a", 0.25),
    ("robust_tail_a", 0.5),
    ("robust_mean_b", 0.5),
    ("robust_tail_b", 0.75),
    ("accuracy_error_a", 0.25),
    ("accuracy_error_b", 0.5),
)
FIXTURE_BOOLEAN_VALUES = (("finite_ok", True),)


class _FloatSubclass(float):
    pass


class _IntegerSubclass(int):
    pass


class _StringSubclass(str):
    pass


class _CoercibleFloat:
    def __float__(self) -> float:
        return 0.25


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def _fixture_object() -> dict[str, Any]:
    value = json.loads(_fixture_bytes())
    assert type(value) is dict
    return value


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _payload_with(path: tuple[str | int, ...], value: object) -> bytes:
    document = _fixture_object()
    target: Any = document
    for member in path[:-1]:
        target = target[member]
    target[path[-1]] = value
    return _json_bytes(document)


def _payload_without(path: tuple[str | int, ...]) -> bytes:
    document = _fixture_object()
    target: Any = document
    for member in path[:-1]:
        target = target[member]
    del target[path[-1]]
    return _json_bytes(document)


def _pin(
    *,
    challenge_key: object = ChallengeKey("a5_fixture", "fixture-1.0"),
    scoring_version: object = "fixture-1.0",
    scoring_digest: object = FIXTURE_DIGEST,
    generator_version_required: object = "fixture-1.0",
    generator_digest_required: object = GENERATOR_DIGEST,
    schema_version: object = "1.0",
    numerical_profile: object = "python_binary64_v1",
    fixture_origin: object = True,
) -> ScorePackPin:
    return ScorePackPin(
        challenge_key=challenge_key,  # type: ignore[arg-type]
        scoring_version=scoring_version,  # type: ignore[arg-type]
        scoring_digest=scoring_digest,  # type: ignore[arg-type]
        generator_version_required=generator_version_required,  # type: ignore[arg-type]
        generator_digest_required=generator_digest_required,  # type: ignore[arg-type]
        schema_version=schema_version,  # type: ignore[arg-type]
        numerical_profile=numerical_profile,  # type: ignore[arg-type]
        fixture_origin=fixture_origin,  # type: ignore[arg-type]
    )


def _unsafe_pin(**overrides: object) -> ScorePackPin:
    """Forge an invalid exact-type pin only to exercise the hostile boundary."""
    values = {
        "challenge_key": ChallengeKey("a5_fixture", "fixture-1.0"),
        "scoring_version": "fixture-1.0",
        "scoring_digest": FIXTURE_DIGEST,
        "generator_version_required": "fixture-1.0",
        "generator_digest_required": GENERATOR_DIGEST,
        "schema_version": "1.0",
        "numerical_profile": "python_binary64_v1",
        "fixture_origin": True,
    }
    values.update(overrides)
    pin = object.__new__(ScorePackPin)
    for name, value in values.items():
        object.__setattr__(pin, name, value)
    return pin


def _load_fixture() -> LoadedScorePack:
    return load_score_pack(
        REPOSITORY_ROOT,
        FIXTURE_RELATIVE_PATH.as_posix(),
        _pin(),
    )


def _load_payload(
    tmp_path: Path,
    payload: bytes,
    *,
    expected_pin: ScorePackPin | None = None,
    relative_path: str = "pack.json",
) -> LoadedScorePack:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(exist_ok=True)
    (artifact_root / relative_path).write_bytes(payload)
    return load_score_pack(
        artifact_root,
        relative_path,
        expected_pin or _pin(scoring_digest=_digest(payload)),
    )


def _fixture_input(
    pack: LoadedScorePack,
    *,
    numeric_values: tuple[tuple[str, float], ...] = FIXTURE_NUMERIC_VALUES,
    boolean_values: tuple[tuple[str, bool], ...] = FIXTURE_BOOLEAN_VALUES,
) -> ScoreInput:
    return pack.fixture_score_input(
        numeric_inputs=tuple(NumericInput(key, value) for key, value in numeric_values),
        boolean_inputs=tuple(BooleanInput(key, value) for key, value in boolean_values),
    )


def _numeric_values(**overrides: float) -> tuple[tuple[str, float], ...]:
    unknown = set(overrides).difference(key for key, _ in FIXTURE_NUMERIC_VALUES)
    assert not unknown
    return tuple(
        (key, overrides.get(key, value)) for key, value in FIXTURE_NUMERIC_VALUES
    )


def _score_fixture(
    *,
    pack: LoadedScorePack | None = None,
    numeric_values: tuple[tuple[str, float], ...] = FIXTURE_NUMERIC_VALUES,
    boolean_values: tuple[tuple[str, bool], ...] = FIXTURE_BOOLEAN_VALUES,
) -> InternalResult:
    loaded = pack or _load_fixture()
    return ScoreEngine.score(
        _fixture_input(
            loaded,
            numeric_values=numeric_values,
            boolean_values=boolean_values,
        ),
        loaded,
    )


def _score_input(
    *,
    numeric_inputs: tuple[NumericInput, ...] = (
        NumericInput("gate_error", 0.25),
        NumericInput("diagnostic_error", 0.5),
        NumericInput("physics_error", 0.25),
        NumericInput("robust_mean_a", 0.25),
        NumericInput("robust_tail_a", 0.5),
        NumericInput("robust_mean_b", 0.5),
        NumericInput("robust_tail_b", 0.75),
        NumericInput("accuracy_error_a", 0.25),
        NumericInput("accuracy_error_b", 0.5),
    ),
    boolean_inputs: tuple[BooleanInput, ...] = (BooleanInput("finite_ok", True),),
) -> ScoreInput:
    return ScoreInput._from_validated_fixture(
        pack_pin=_pin(),
        numeric_inputs=numeric_inputs,
        boolean_inputs=boolean_inputs,
    )


def _gate_decisions(
    *,
    mandatory_passed: bool = True,
) -> tuple[GateDecision, ...]:
    return (
        GateDecision("synthetic_error_gate", mandatory_passed, True),
        GateDecision("synthetic_finite_gate", True, True),
        GateDecision("synthetic_optional_diagnostic", False, False),
    )


def _leg_scores(*, score: float = 1.0) -> tuple[LegScore, ...]:
    return tuple(
        LegScore(
            leg,
            (ScalarScore(f"{leg}_component", score),),
            score,
        )
        for leg in LEG_ORDER
    )


def _scored_result(*, combined_score: float = 1.0) -> InternalResult:
    return InternalResult(
        status=ScoreStatus.SCORED,
        pack_pin=_pin(),
        gate_decisions=_gate_decisions(),
        leg_scores=_leg_scores(score=combined_score),
        combined_score=combined_score,
        eligible_for_emission=False,
    )


def _result_for_status(status: ScoreStatus) -> InternalResult:
    if status is ScoreStatus.SCORED:
        return _scored_result(combined_score=0.75)
    if status is ScoreStatus.MANDATORY_GATE_FAILED:
        return InternalResult(
            status=status,
            pack_pin=_pin(),
            gate_decisions=_gate_decisions(mandatory_passed=False),
            leg_scores=(),
            combined_score=0.0,
            eligible_for_emission=False,
        )
    assert status is ScoreStatus.PACK_NOT_READY
    return InternalResult(
        status=status,
        pack_pin=_pin(),
        gate_decisions=(),
        leg_scores=(),
        combined_score=None,
        eligible_for_emission=False,
    )


def _unsafe_copy_exact(value: object, **overrides: object) -> Any:
    copied = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(
            copied,
            item.name,
            overrides.get(item.name, getattr(value, item.name)),
        )
    return copied


def _forged_score_status(member: ScoreStatus) -> ScoreStatus:
    forged = str.__new__(ScoreStatus, member.value)
    object.__setattr__(forged, "_name_", "FORGED_" + member.name)
    object.__setattr__(forged, "_value_", member.value)
    return forged


def test_canonical_fixture_bytes_have_the_independent_golden_digest() -> None:
    payload = _fixture_bytes()
    assert len(payload) == 2126
    assert payload.endswith(b"\n")
    assert _digest(payload) == FIXTURE_DIGEST


@pytest.mark.parametrize(
    "mutator",
    (
        lambda payload: b" " + payload,
        lambda payload: payload + b"\n",
        lambda payload: payload.replace(b'"threshold": 1.0', b'"threshold": 1.00', 1),
        lambda payload: payload.replace(
            b'"schema_version": "1.0",\n  "challenge_id": "a5_fixture"',
            b'"challenge_id": "a5_fixture",\n  "schema_version": "1.0"',
            1,
        ),
    ),
)
def test_any_source_byte_perturbation_changes_pack_identity(mutator: Any) -> None:
    payload = _fixture_bytes()
    changed = mutator(payload)
    assert changed != payload
    assert _digest(changed) != FIXTURE_DIGEST


def test_fixture_is_the_only_runtime_score_pack_and_has_no_yaml_twin() -> None:
    score_pack_directory = FIXTURE_PATH.parent
    assert tuple(path.name for path in sorted(score_pack_directory.iterdir())) == (
        "a5_fixture_v1.json",
    )


def test_fixture_uses_the_exact_closed_schema_1_0_shape() -> None:
    value = _fixture_object()
    assert set(value) == {
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
    assert value["schema_version"] == "1.0"
    assert value["numerical_profile"] == "python_binary64_v1"
    assert value["fixture_origin"] is True
    assert value["combination"] == "weighted_geometric_logspace"
    assert value["challenge_id"] == "a5_fixture"
    assert value["challenge_version"].startswith("fixture-")
    assert value["scoring_version"].startswith("fixture-")
    assert value["generator_version_required"].startswith("fixture-")

    threshold_gate, boolean_gate, optional_gate = value["hard_gates"]
    assert set(threshold_gate) == {
        "operator",
        "id",
        "input_key",
        "mandatory",
        "threshold",
    }
    assert set(boolean_gate) == {"operator", "id", "input_key", "mandatory"}
    assert set(optional_gate) == set(threshold_gate)
    assert [gate["operator"] for gate in value["hard_gates"]] == [
        "less_than",
        "boolean_true",
        "less_than",
    ]

    assert set(value["physics"]) == {"operator", "components"}
    assert value["physics"]["operator"] == "quadratic_barrier"
    assert all(
        set(component) == {"id", "input_key", "threshold", "weight"}
        for component in value["physics"]["components"]
    )

    assert set(value["robustness"]) == {
        "operator",
        "tail_quantile",
        "blend_weights",
        "threshold",
        "sharpness",
        "categories",
    }
    assert value["robustness"]["operator"] == "tail_logistic"
    assert set(value["robustness"]["blend_weights"]) == {"mean", "tail"}
    assert all(
        set(category) == {"id", "mean_input_key", "tail_input_key", "weight"}
        for category in value["robustness"]["categories"]
    )

    assert set(value["accuracy"]) == {"operator", "components"}
    assert value["accuracy"]["operator"] == "reciprocal_error"
    assert all(
        set(component) == {"id", "input_key", "threshold", "weight"}
        for component in value["accuracy"]["components"]
    )
    assert set(value["weights"]) == set(LEG_ORDER)


def test_fixture_contains_no_internal_digest_hash_stub_or_aggregation_alias() -> None:
    forbidden_keys = {
        "aggregation",
        "content_hash",
        "pack_hash",
        "scoring_digest",
        "type",
        "kind",
    }

    def walk(value: object) -> None:
        if type(value) is dict:
            assert forbidden_keys.isdisjoint(value)
            for nested in value.values():
                walk(nested)
        elif type(value) is list:
            for nested in value:
                walk(nested)

    walk(_fixture_object())


def test_score_pack_pin_accepts_only_the_exact_fixture_contract() -> None:
    pin = _pin()
    assert pin.challenge_key == ChallengeKey("a5_fixture", "fixture-1.0")
    assert pin.scoring_digest == FIXTURE_DIGEST
    assert pin.generator_digest_required == GENERATOR_DIGEST
    assert pin.schema_version == "1.0"
    assert pin.numerical_profile == "python_binary64_v1"
    assert pin.fixture_origin is True


@pytest.mark.parametrize(
    ("overrides", "error_type"),
    (
        ({"challenge_key": object()}, TypeError),
        ({"scoring_version": "not canonical!"}, ValueError),
        ({"scoring_digest": "sha256:abc"}, ValueError),
        ({"generator_version_required": "not canonical!"}, ValueError),
        ({"generator_digest_required": "sha256:abc"}, ValueError),
        ({"schema_version": "1.1"}, ValueError),
        ({"schema_version": _StringSubclass("1.0")}, TypeError),
        ({"numerical_profile": "python_binary64_v2"}, ValueError),
        ({"numerical_profile": _StringSubclass("python_binary64_v1")}, TypeError),
        ({"fixture_origin": False}, ValueError),
        ({"fixture_origin": 1}, TypeError),
    ),
)
def test_score_pack_pin_rejects_each_non_exact_binding(
    overrides: dict[str, object], error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        _pin(**overrides)


@pytest.mark.parametrize(
    "value",
    (
        True,
        False,
        0,
        1,
        _IntegerSubclass(1),
        _FloatSubclass(0.25),
        "0.25",
        _CoercibleFloat(),
        None,
        float("nan"),
        float("inf"),
        -float("inf"),
        -0.25,
    ),
)
def test_numeric_score_input_requires_exact_finite_non_negative_float(
    value: object,
) -> None:
    with pytest.raises(ScoreInputError):
        NumericInput("synthetic_input", value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (-0.0, 0.0, 1.0, float("1e308")))
def test_numeric_score_input_accepts_exact_finite_non_negative_float(
    value: float,
) -> None:
    assert NumericInput("synthetic_input", value).value == value


@pytest.mark.parametrize(
    "value",
    (0, 1, _IntegerSubclass(1), "true", None, object()),
)
def test_boolean_score_input_requires_exact_builtin_bool(value: object) -> None:
    with pytest.raises(ScoreInputError):
        BooleanInput("synthetic_predicate", value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (True, False))
def test_boolean_score_input_accepts_both_exact_boolean_actuals(value: bool) -> None:
    assert BooleanInput("synthetic_predicate", value).value is value


@pytest.mark.parametrize(
    "key",
    ("", "Not_Canonical", "contains space", "leading_", _StringSubclass("valid")),
)
def test_score_input_keys_require_exact_canonical_strings(key: object) -> None:
    with pytest.raises(ScoreInputError):
        NumericInput(key, 0.0)  # type: ignore[arg-type]


def test_score_input_direct_construction_is_forbidden() -> None:
    with pytest.raises(ScoreInputError) as captured:
        ScoreInput()  # type: ignore[call-arg]
    assert captured.value.code == "score_input.direct_init"


@pytest.mark.parametrize(
    ("numeric_inputs", "boolean_inputs"),
    (
        (
            (NumericInput("duplicate", 0.0), NumericInput("duplicate", 1.0)),
            (),
        ),
        (
            (NumericInput("duplicate", 0.0),),
            (BooleanInput("duplicate", True),),
        ),
        (
            (),
            (BooleanInput("duplicate", True), BooleanInput("duplicate", False)),
        ),
    ),
)
def test_fixture_score_input_rejects_duplicate_and_cross_type_keys(
    numeric_inputs: tuple[NumericInput, ...],
    boolean_inputs: tuple[BooleanInput, ...],
) -> None:
    with pytest.raises(ScoreInputError) as captured:
        ScoreInput._from_validated_fixture(
            pack_pin=_pin(),
            numeric_inputs=numeric_inputs,
            boolean_inputs=boolean_inputs,
        )
    assert captured.value.code == "score_input.duplicate_key"


def test_fixture_score_input_is_frozen_and_uses_exact_lookup() -> None:
    score_input = _score_input()
    assert score_input.numeric_value("physics_error") == 0.25
    assert score_input.boolean_value("finite_ok") is True
    with pytest.raises(ScoreInputError):
        score_input.numeric_value("missing")
    with pytest.raises(ScoreInputError):
        score_input.boolean_value("missing")
    with pytest.raises(FrozenInstanceError):
        score_input.pack_pin = _pin()  # type: ignore[misc]


def test_private_result_has_only_the_allowed_frozen_field_contract() -> None:
    assert tuple(field.name for field in fields(InternalResult)) == (
        "status",
        "pack_pin",
        "gate_decisions",
        "leg_scores",
        "combined_score",
        "eligible_for_emission",
    )
    assert tuple(field.name for field in fields(GateDecision)) == (
        "gate_id",
        "passed",
        "mandatory",
    )
    assert tuple(field.name for field in fields(ScalarScore)) == (
        "identifier",
        "score",
    )
    assert tuple(field.name for field in fields(LegScore)) == (
        "leg",
        "components",
        "score",
    )

    result = _scored_result()
    with pytest.raises(FrozenInstanceError):
        result.combined_score = 0.5  # type: ignore[misc]


@pytest.mark.parametrize(
    "status",
    (
        ScoreStatus.SCORED,
        ScoreStatus.MANDATORY_GATE_FAILED,
        ScoreStatus.PACK_NOT_READY,
    ),
)
def test_internal_result_private_copy_preserves_each_exact_status(
    status: ScoreStatus,
) -> None:
    source = _result_for_status(status)

    copied = source._copy()

    assert type(copied) is InternalResult
    assert copied is not source
    assert copied == source
    assert copied.status is status
    assert copied.combined_score == source.combined_score
    if copied.combined_score == 0.0:
        assert math.copysign(1.0, copied.combined_score) == 1.0
    assert copied.eligible_for_emission is False


def test_internal_result_private_copy_recursively_owns_the_entire_graph() -> None:
    source = _scored_result(combined_score=0.75)

    copied = source._copy()

    assert copied.pack_pin is not source.pack_pin
    assert copied.pack_pin.challenge_key is not source.pack_pin.challenge_key
    assert copied.gate_decisions is not source.gate_decisions
    assert copied.leg_scores is not source.leg_scores
    assert all(
        copied_gate is not source_gate
        for copied_gate, source_gate in zip(
            copied.gate_decisions,
            source.gate_decisions,
            strict=True,
        )
    )
    assert all(
        copied_leg is not source_leg
        and copied_leg.components is not source_leg.components
        and all(
            copied_component is not source_component
            for copied_component, source_component in zip(
                copied_leg.components,
                source_leg.components,
                strict=True,
            )
        )
        for copied_leg, source_leg in zip(
            copied.leg_scores,
            source.leg_scores,
            strict=True,
        )
    )

    object.__setattr__(source.pack_pin, "scoring_version", "fixture-9.0")
    object.__setattr__(source.gate_decisions[0], "passed", False)
    object.__setattr__(source.leg_scores[0].components[0], "score", 0.0)
    object.__setattr__(source, "combined_score", 0.0)

    assert copied.pack_pin.challenge_key.challenge_id == "a5_fixture"
    assert copied.pack_pin.scoring_version == "fixture-1.0"
    assert copied.gate_decisions[0].passed is True
    assert copied.leg_scores[0].components[0].score == 0.75
    assert copied.combined_score == 0.75


def test_internal_result_private_copy_rejects_subclasses_and_arguments() -> None:
    class InternalResultSubclass(InternalResult):
        pass

    source = _scored_result()
    subclass = InternalResultSubclass(
        source.status,
        source.pack_pin,
        source.gate_decisions,
        source.leg_scores,
        source.combined_score,
        source.eligible_for_emission,
    )

    with pytest.raises(TypeError):
        subclass._copy()
    with pytest.raises(TypeError):
        source._copy("caller field")  # type: ignore[call-arg]


def test_internal_result_private_copy_revalidates_hostile_source_graph() -> None:
    class ChallengeKeySubclass(ChallengeKey):
        pass

    class GateDecisionSubclass(GateDecision):
        pass

    class LegScoreSubclass(LegScore):
        pass

    class ScalarScoreSubclass(ScalarScore):
        pass

    valid = _scored_result(combined_score=0.75)
    malformed_pin = _unsafe_copy_exact(valid.pack_pin, scoring_version="bad version")
    subclass_key = ChallengeKeySubclass("a5_fixture", "fixture-1.0")
    subclass_pin = _unsafe_copy_exact(valid.pack_pin, challenge_key=subclass_key)
    malformed_gate = _unsafe_copy_exact(valid.gate_decisions[0], passed=1)
    malformed_component = _unsafe_copy_exact(
        valid.leg_scores[0].components[0],
        score=float("nan"),
    )
    malformed_leg = _unsafe_copy_exact(
        valid.leg_scores[0],
        components=(malformed_component,),
    )
    gate_subclass = GateDecisionSubclass("synthetic_error_gate", True, True)
    component_subclass = ScalarScoreSubclass("physics_component", 0.75)
    component_subclass_leg = _unsafe_copy_exact(
        valid.leg_scores[0],
        components=(component_subclass,),
    )
    leg_subclass = LegScoreSubclass(
        "physics",
        (ScalarScore("physics_component", 0.75),),
        0.75,
    )
    mandatory_failed = _result_for_status(ScoreStatus.MANDATORY_GATE_FAILED)
    pack_not_ready = _result_for_status(ScoreStatus.PACK_NOT_READY)

    malformed_results = (
        _unsafe_copy_exact(valid, status=_forged_score_status(ScoreStatus.SCORED)),
        _unsafe_copy_exact(valid, pack_pin=object()),
        _unsafe_copy_exact(valid, pack_pin=malformed_pin),
        _unsafe_copy_exact(valid, pack_pin=subclass_pin),
        _unsafe_copy_exact(valid, gate_decisions=list(valid.gate_decisions)),
        _unsafe_copy_exact(
            valid,
            gate_decisions=(gate_subclass, *valid.gate_decisions[1:]),
        ),
        _unsafe_copy_exact(
            valid,
            gate_decisions=(malformed_gate, *valid.gate_decisions[1:]),
        ),
        _unsafe_copy_exact(valid, leg_scores=list(valid.leg_scores)),
        _unsafe_copy_exact(
            valid,
            leg_scores=(leg_subclass, *valid.leg_scores[1:]),
        ),
        _unsafe_copy_exact(
            valid,
            leg_scores=(component_subclass_leg, *valid.leg_scores[1:]),
        ),
        _unsafe_copy_exact(
            valid,
            leg_scores=(malformed_leg, *valid.leg_scores[1:]),
        ),
        _unsafe_copy_exact(valid, combined_score=float("inf")),
        _unsafe_copy_exact(valid, eligible_for_emission=True),
        _unsafe_copy_exact(
            mandatory_failed,
            gate_decisions=_gate_decisions(mandatory_passed=True),
        ),
        _unsafe_copy_exact(mandatory_failed, combined_score=-0.0),
        _unsafe_copy_exact(
            pack_not_ready,
            gate_decisions=_gate_decisions(),
        ),
        _unsafe_copy_exact(
            valid,
            leg_scores=tuple(reversed(valid.leg_scores)),
        ),
    )

    for malformed in malformed_results:
        with pytest.raises((TypeError, ValueError, AttributeError)):
            malformed._copy()


def test_pack_not_ready_result_has_no_scientific_evidence_and_never_emits() -> None:
    result = InternalResult(
        status=ScoreStatus.PACK_NOT_READY,
        pack_pin=_pin(),
        gate_decisions=(),
        leg_scores=(),
        combined_score=None,
        eligible_for_emission=False,
    )
    assert result.gate_decisions == ()
    assert result.leg_scores == ()
    assert result.combined_score is None
    assert result.eligible_for_emission is False


def test_mandatory_failure_result_requires_full_atomic_zero_false_invariant() -> None:
    result = InternalResult(
        status=ScoreStatus.MANDATORY_GATE_FAILED,
        pack_pin=_pin(),
        gate_decisions=_gate_decisions(mandatory_passed=False),
        leg_scores=(),
        combined_score=0.0,
        eligible_for_emission=False,
    )
    assert result.status is ScoreStatus.MANDATORY_GATE_FAILED
    assert math.copysign(1.0, result.combined_score) == 1.0
    assert result.eligible_for_emission is False


@pytest.mark.parametrize("combined_score", (-0.0, None, 0.25, float("nan")))
def test_mandatory_failure_result_rejects_noncanonical_score(
    combined_score: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        InternalResult(
            status=ScoreStatus.MANDATORY_GATE_FAILED,
            pack_pin=_pin(),
            gate_decisions=_gate_decisions(mandatory_passed=False),
            leg_scores=(),
            combined_score=combined_score,  # type: ignore[arg-type]
            eligible_for_emission=False,
        )


def test_scored_zero_result_requires_canonical_positive_zero() -> None:
    result = _scored_result(combined_score=0.0)
    assert result.status is ScoreStatus.SCORED
    assert math.copysign(1.0, result.combined_score) == 1.0
    assert result.eligible_for_emission is False
    with pytest.raises(ValueError):
        _scored_result(combined_score=-0.0)


@pytest.mark.parametrize(
    "status",
    (ScoreStatus.SCORED, ScoreStatus.MANDATORY_GATE_FAILED, ScoreStatus.PACK_NOT_READY),
)
def test_every_result_status_rejects_emission_eligibility(status: ScoreStatus) -> None:
    gate_decisions = _gate_decisions()
    leg_scores = _leg_scores()
    combined_score: float | None = 1.0
    if status is ScoreStatus.MANDATORY_GATE_FAILED:
        gate_decisions = _gate_decisions(mandatory_passed=False)
        leg_scores = ()
        combined_score = 0.0
    elif status is ScoreStatus.PACK_NOT_READY:
        gate_decisions = ()
        leg_scores = ()
        combined_score = None

    with pytest.raises(ValueError):
        InternalResult(
            status=status,
            pack_pin=_pin(),
            gate_decisions=gate_decisions,
            leg_scores=leg_scores,
            combined_score=combined_score,
            eligible_for_emission=True,
        )


def test_internal_result_recursively_excludes_weights_and_downstream_identity() -> None:
    forbidden_names = {
        "block_height",
        "decay",
        "draw_id",
        "eligible_weight",
        "evaluation_binding",
        "exam_id",
        "fee",
        "hotkey",
        "miner",
        "pack_weights",
        "payment",
        "receipt",
        "seed",
        "strategy",
        "submission",
        "tie_break",
        "validator",
        "weights",
    }
    result = _scored_result(combined_score=0.5)
    nested_field_names = {
        field.name
        for value in (
            result,
            result.pack_pin,
            *result.gate_decisions,
            *result.leg_scores,
        )
        for field in fields(value)
    }
    nested_field_names.update(
        field.name
        for leg_score in result.leg_scores
        for component in leg_score.components
        for field in fields(component)
    )
    assert forbidden_names.isdisjoint(nested_field_names)


def test_fixture_loads_through_the_exact_digest_first_boundary() -> None:
    pack = _load_fixture()
    assert pack.ready is True
    assert pack.pack_pin == _pin()
    assert [gate.gate_id for gate in pack.hard_gates] == [
        "synthetic_error_gate",
        "synthetic_finite_gate",
        "synthetic_optional_diagnostic",
    ]
    assert [component.component_id for component in pack.physics.components] == [
        "synthetic_residual"
    ]
    assert [category.category_id for category in pack.robustness.categories] == [
        "synthetic_category_a",
        "synthetic_category_b",
    ]
    assert [component.component_id for component in pack.accuracy.components] == [
        "synthetic_accuracy_a",
        "synthetic_accuracy_b",
    ]
    assert pack.top_level_weights == (0.5, 0.3, 0.2)


def test_loaded_score_pack_direct_construction_is_forbidden() -> None:
    with pytest.raises(ScorePackSchemaError) as captured:
        LoadedScorePack()  # type: ignore[call-arg]
    assert captured.value.code == "score_pack.direct_init"


@pytest.mark.parametrize("expected_pin", (None, object(), _pin))
def test_loader_rejects_absent_or_non_instance_external_pin(
    expected_pin: object,
) -> None:
    with pytest.raises(ScorePackPinError) as captured:
        load_score_pack(
            REPOSITORY_ROOT,
            FIXTURE_RELATIVE_PATH.as_posix(),
            expected_pin,  # type: ignore[arg-type]
        )
    assert captured.value.code == "score_pack.expected_pin_type"


@pytest.mark.parametrize(
    ("expected_pin", "expected_code"),
    (
        (_unsafe_pin(scoring_digest=""), "artifact.digest_invalid"),
        (_unsafe_pin(scoring_digest="sha256:" + "A" * 64), "artifact.digest_invalid"),
        (_pin(scoring_digest="sha256:" + "0" * 64), "artifact.digest_mismatch"),
    ),
)
def test_loader_rejects_malformed_or_mismatched_external_digest(
    expected_pin: ScorePackPin,
    expected_code: str,
) -> None:
    with pytest.raises(ScorePackIntegrityError) as captured:
        load_score_pack(
            REPOSITORY_ROOT,
            FIXTURE_RELATIVE_PATH.as_posix(),
            expected_pin,
        )
    assert captured.value.code == expected_code


def test_digest_validation_precedes_artifact_access_and_json_parsing(
    tmp_path: Path,
) -> None:
    invalid_payload = b"\xef\xbb\xbfnot json"
    path = tmp_path / "pack.json"
    path.write_bytes(invalid_payload)
    with pytest.raises(ScorePackIntegrityError) as captured:
        load_score_pack(
            tmp_path,
            "missing.json",
            _unsafe_pin(scoring_digest="malformed"),
        )
    assert captured.value.code == "artifact.digest_invalid"


@pytest.mark.parametrize(
    "payload",
    (
        b"\xef\xbb\xbf" + _fixture_bytes(),
        _fixture_bytes()[:-2] + b"\xff\n",
        b"schema_version: '1.0'\nfixture_origin: true\n",
        _fixture_bytes() + b"{}",
        b"[]",
        b"null",
        b"",
    ),
)
def test_loader_rejects_non_strict_utf8_json_documents(
    tmp_path: Path,
    payload: bytes,
) -> None:
    with pytest.raises(ScorePackParseError):
        _load_payload(tmp_path, payload)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (
            b'{\n  "schema_version": "1.0",',
            b'{\n  "schema_version": "1.0",\n  "schema_version": "1.0",',
        ),
        (
            b'      "operator": "less_than",',
            b'      "operator": "less_than",\n      "operator": "less_than",',
        ),
        (
            b'  "physics": {\n    "operator": "quadratic_barrier",',
            (
                b'  "physics": {\n    "operator": "quadratic_barrier",\n'
                b'    "operator": "quadratic_barrier",'
            ),
        ),
        (
            b'        "id": "synthetic_residual",',
            (
                b'        "id": "synthetic_residual",\n'
                b'        "id": "synthetic_residual",'
            ),
        ),
        (
            b'    "blend_weights": {\n      "mean": 0.5,',
            b'    "blend_weights": {\n      "mean": 0.5,\n      "mean": 0.5,',
        ),
        (
            b'        "id": "synthetic_category_a",',
            (
                b'        "id": "synthetic_category_a",\n'
                b'        "id": "synthetic_category_a",'
            ),
        ),
        (
            b'        "id": "synthetic_accuracy_a",',
            (
                b'        "id": "synthetic_accuracy_a",\n'
                b'        "id": "synthetic_accuracy_a",'
            ),
        ),
        (
            b'  "weights": {\n    "physics": 0.5,',
            b'  "weights": {\n    "physics": 0.5,\n    "physics": 0.5,',
        ),
    ),
)
def test_duplicate_json_members_reject_at_every_object_depth(
    tmp_path: Path,
    needle: bytes,
    replacement: bytes,
) -> None:
    payload = _fixture_bytes().replace(needle, replacement, 1)
    assert payload != _fixture_bytes()
    with pytest.raises(ScorePackParseError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == "score_pack.json_duplicate"


@pytest.mark.parametrize(
    "payload",
    (
        _payload_with(("unknown",), True),
        _payload_without(("combination",)),
        _payload_with(("physics", "aggregation"), "weighted_sum"),
        _payload_without(("physics", "operator")),
        _payload_with(("hard_gates", 0, "type"), "less_than"),
        _payload_with(("hard_gates", 0, "kind"), "less_than"),
        _payload_with(("hard_gates", 0, "threshold"), None),
        _payload_with(("hard_gates", 0, "mandatory"), 1),
        _payload_with(("hard_gates",), {}),
        _payload_with(("weights",), []),
        _payload_with(("fixture_origin",), "true"),
    ),
)
def test_closed_schema_rejects_unknown_missing_aliased_null_and_wrong_types(
    tmp_path: Path,
    payload: bytes,
) -> None:
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, payload)


@pytest.mark.parametrize(
    ("context", "path"),
    (
        ("threshold_gate", ("hard_gates", 0)),
        ("physics", ("physics",)),
        ("robustness", ("robustness",)),
        ("accuracy", ("accuracy",)),
    ),
)
@pytest.mark.parametrize("mode", ("missing", "type", "kind", "unknown"))
def test_every_operator_context_requires_exact_operator_discriminator(
    tmp_path: Path,
    context: str,
    path: tuple[str | int, ...],
    mode: str,
) -> None:
    document = _fixture_object()
    record: Any = document
    for member in path:
        record = record[member]
    original = record.pop("operator")
    if mode in {"type", "kind"}:
        record[mode] = original
    elif mode == "unknown":
        record["operator"] = f"unknown_{context}"
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, _json_bytes(document))


@pytest.mark.parametrize("constant", (b"NaN", b"Infinity", b"-Infinity"))
def test_non_json_numeric_constants_reject_before_schema_validation(
    tmp_path: Path,
    constant: bytes,
) -> None:
    payload = _fixture_bytes().replace(
        b'"threshold": 1.0', b'"threshold": ' + constant, 1
    )
    with pytest.raises(ScorePackParseError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == "score_pack.json_constant"


@pytest.mark.parametrize("field", ("scoring_digest", "content_hash", "pack_hash"))
def test_loader_rejects_internal_digest_and_hash_stub_fields(
    tmp_path: Path,
    field: str,
) -> None:
    payload = _payload_with((field,), FIXTURE_DIGEST)
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == "score_pack.field_unknown"


def test_safe_relative_artifact_path_loads(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    nested = artifact_root / "nested"
    nested.mkdir(parents=True)
    (nested / "pack.json").write_bytes(_fixture_bytes())
    pack = load_score_pack(artifact_root, "nested/pack.json", _pin())
    assert pack.pack_pin == _pin()


@pytest.mark.parametrize(
    "relative_path",
    (
        None,
        Path("pack.json"),
        "",
        ".",
        "../pack.json",
        "nested/../pack.json",
        "/absolute/pack.json",
        "C:\\pack.json",
        "nested//pack.json",
    ),
)
def test_unsafe_artifact_paths_reject(
    tmp_path: Path,
    relative_path: object,
) -> None:
    with pytest.raises(ScorePackAccessError) as captured:
        load_score_pack(tmp_path, relative_path, _pin())
    assert captured.value.code == "artifact.path_invalid"


def test_symbolic_link_artifact_rejects(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_bytes(_fixture_bytes())
    link = artifact_root / "pack.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(ScorePackAccessError) as captured:
        load_score_pack(artifact_root, "pack.json", _pin())
    assert captured.value.code == "artifact.path_escape"


def test_non_regular_artifact_rejects(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "pack.json").mkdir()
    with pytest.raises(ScorePackAccessError) as captured:
        load_score_pack(artifact_root, "pack.json", _pin())
    assert captured.value.code == "artifact.not_regular_file"


def test_unreadable_artifact_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "pack.json").write_bytes(_fixture_bytes())
    real_open = os.open

    def deny_final_open(
        path: str | bytes | int,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == "pack.json" and dir_fd is not None:
            raise PermissionError("synthetic unreadable artifact")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", deny_final_open)
    with pytest.raises(ScorePackAccessError) as captured:
        load_score_pack(artifact_root, "pack.json", _pin())
    assert captured.value.code == "artifact.unreadable"


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("challenge_id",), "other_fixture"),
        (("challenge_version",), "fixture-2.0"),
        (("scoring_version",), "fixture-2.0"),
        (("generator_version_required",), "fixture-2.0"),
        (("generator_digest_required",), "sha256:" + "2" * 64),
    ),
)
def test_source_pin_field_mismatch_rejects_one_at_a_time(
    tmp_path: Path,
    path: tuple[str | int, ...],
    value: object,
) -> None:
    payload = _payload_with(path, value)
    expected_pin = _pin(scoring_digest=_digest(payload))
    with pytest.raises(ScorePackPinError) as captured:
        _load_payload(tmp_path, payload, expected_pin=expected_pin)
    assert captured.value.code == "score_pack.pin_mismatch"


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("schema_version",), "1.1"),
        (("numerical_profile",), "python_binary64_v2"),
        (("fixture_origin",), False),
        (("fixture_origin",), 1),
    ),
)
def test_literal_pin_constraints_reject_at_schema_boundary(
    tmp_path: Path,
    path: tuple[str | int, ...],
    value: object,
) -> None:
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, _payload_with(path, value))


def test_pack_module_exposes_no_production_origin_loader() -> None:
    import carbon.scoring.pack as pack_module

    public_names = set(pack_module.__all__)
    assert "load_score_pack" in public_names
    assert all("production" not in name.lower() for name in public_names)
    assert all("live" not in name.lower() for name in public_names)


def test_fixture_input_accepts_only_the_complete_exact_pack_key_sets() -> None:
    pack = _load_fixture()
    score_input = _fixture_input(
        pack,
        numeric_values=tuple(reversed(FIXTURE_NUMERIC_VALUES)),
        boolean_values=tuple(reversed(FIXTURE_BOOLEAN_VALUES)),
    )
    assert tuple(entry.key for entry in score_input.numeric_inputs) == tuple(
        key for key, _ in FIXTURE_NUMERIC_VALUES
    )
    assert tuple(entry.key for entry in score_input.boolean_inputs) == ("finite_ok",)
    assert score_input.pack_pin == pack.pack_pin


@pytest.mark.parametrize(
    ("numeric_values", "boolean_values"),
    (
        (FIXTURE_NUMERIC_VALUES[:-1], FIXTURE_BOOLEAN_VALUES),
        (FIXTURE_NUMERIC_VALUES + (("unknown", 0.0),), FIXTURE_BOOLEAN_VALUES),
        (FIXTURE_NUMERIC_VALUES, ()),
        (FIXTURE_NUMERIC_VALUES, FIXTURE_BOOLEAN_VALUES + (("unknown", True),)),
        (
            tuple(
                (key, value)
                for key, value in FIXTURE_NUMERIC_VALUES
                if key != "gate_error"
            ),
            FIXTURE_BOOLEAN_VALUES + (("gate_error", True),),
        ),
    ),
)
def test_fixture_input_rejects_missing_extra_and_cross_typed_keys(
    numeric_values: tuple[tuple[str, float], ...],
    boolean_values: tuple[tuple[str, bool], ...],
) -> None:
    with pytest.raises(ScorePackInputError) as captured:
        _fixture_input(
            _load_fixture(),
            numeric_values=numeric_values,
            boolean_values=boolean_values,
        )
    assert captured.value.code == "score_pack.input_key_set"


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "prediction",
        "reference",
        "raw_percentile",
        "seed",
        "draw_id",
        "submission",
        "miner",
        "fee",
        "receipt",
        "estimate",
        "light_score",
    ),
)
def test_forbidden_or_downstream_input_keys_cannot_construct_score_input(
    forbidden_key: str,
) -> None:
    with pytest.raises(ScorePackInputError) as captured:
        _fixture_input(
            _load_fixture(),
            numeric_values=FIXTURE_NUMERIC_VALUES + ((forbidden_key, 0.0),),
        )
    assert captured.value.code == "score_pack.input_key_set"


def test_fixture_input_rejects_non_tuple_containers_and_non_scalar_entries() -> None:
    pack = _load_fixture()
    with pytest.raises(ScorePackInputError) as captured:
        pack.fixture_score_input(
            numeric_inputs=[  # type: ignore[arg-type]
                NumericInput(key, value) for key, value in FIXTURE_NUMERIC_VALUES
            ],
            boolean_inputs=tuple(
                BooleanInput(key, value) for key, value in FIXTURE_BOOLEAN_VALUES
            ),
        )
    assert captured.value.code == "score_pack.input_type"
    with pytest.raises(ScorePackInputError) as captured:
        pack.fixture_score_input(
            numeric_inputs=(object(),),  # type: ignore[arg-type]
            boolean_inputs=(),
        )
    assert captured.value.code == "score_pack.input_entry_type"


def test_fixture_input_boundary_revalidates_forged_scalar_objects() -> None:
    forged = object.__new__(NumericInput)
    object.__setattr__(forged, "key", "gate_error")
    object.__setattr__(forged, "value", float("nan"))
    numeric_inputs = tuple(
        forged if key == "gate_error" else NumericInput(key, value)
        for key, value in FIXTURE_NUMERIC_VALUES
    )
    with pytest.raises(ScorePackInputError) as captured:
        _load_fixture().fixture_score_input(
            numeric_inputs=numeric_inputs,
            boolean_inputs=(BooleanInput("finite_ok", True),),
        )
    assert captured.value.code == "score_pack.input_value_invalid"


@pytest.mark.parametrize("state", ("HUMAN_INPUT", "BLOCKED_FOR_LIVE_UNTIL_SET"))
@pytest.mark.parametrize(
    "path",
    (
        ("hard_gates", 0, "threshold"),
        ("physics", "components", 0, "threshold"),
        ("physics", "components", 0, "weight"),
        ("robustness", "tail_quantile"),
        ("robustness", "blend_weights", "mean"),
        ("robustness", "threshold"),
        ("robustness", "sharpness"),
        ("robustness", "categories", 0, "weight"),
        ("accuracy", "components", 0, "threshold"),
        ("accuracy", "components", 0, "weight"),
        ("weights", "physics"),
    ),
)
def test_every_required_score_bearing_sentinel_makes_pack_not_ready(
    tmp_path: Path,
    path: tuple[str | int, ...],
    state: str,
) -> None:
    pack = _load_payload(tmp_path, _payload_with(path, state))
    assert pack.ready is False
    with pytest.raises(ScorePackInputError) as captured:
        _fixture_input(pack)
    assert captured.value.code == "score_pack.input_not_ready"


@pytest.mark.parametrize("state", ("HUMAN_INPUT", "BLOCKED_FOR_LIVE_UNTIL_SET"))
def test_unresolved_optional_diagnostic_is_omitted_without_affecting_readiness(
    tmp_path: Path,
    state: str,
) -> None:
    payload = _payload_with(("hard_gates", 2, "threshold"), state)
    pack = _load_payload(tmp_path, payload)
    assert pack.ready is True
    assert pack.hard_gates[2].threshold == state
    numeric_values = tuple(
        item for item in FIXTURE_NUMERIC_VALUES if item[0] != "diagnostic_error"
    )
    score_input = _fixture_input(pack, numeric_values=numeric_values)
    assert all(entry.key != "diagnostic_error" for entry in score_input.numeric_inputs)
    with pytest.raises(ScorePackInputError):
        _fixture_input(pack)


@pytest.mark.parametrize("invalid", (None, "human_input", "UNKNOWN", "", True, []))
def test_null_or_unknown_unresolved_state_alias_rejects(
    tmp_path: Path,
    invalid: object,
) -> None:
    payload = _payload_with(("physics", "components", 0, "threshold"), invalid)
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, payload)


def test_omitted_required_score_bearing_value_rejects(tmp_path: Path) -> None:
    payload = _payload_without(("physics", "components", 0, "threshold"))
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, payload)


def test_unready_sentinel_does_not_mask_invalid_concrete_sibling(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["hard_gates"][0]["threshold"] = "HUMAN_INPUT"
    document["physics"]["components"][0]["weight"] = 0.0
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, _json_bytes(document))
    assert captured.value.code == "score_pack.numeric_range"


def test_weight_validation_is_independent_of_ambient_decimal_context(
    tmp_path: Path,
) -> None:
    payload = _fixture_bytes().replace(
        b'"physics": 0.5,\n    "robustness": 0.3,\n    "accuracy": 0.2',
        b'"physics": 5e-1,\n    "robustness": 3e-1,\n    "accuracy": 2e-1',
        1,
    )
    with localcontext() as context:
        context.prec = 1
        context.Emax = 1
        context.Emin = -1
        pack = _load_payload(tmp_path, payload)
    assert pack.top_level_weights == (0.5, 0.3, 0.2)


def test_exact_decimal_unit_sum_does_not_require_binary64_sum_to_equal_one(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["weights"] = {"physics": 0.06, "robustness": 0.57, "accuracy": 0.37}
    pack = _load_payload(tmp_path, _json_bytes(document))
    assert sum(pack.top_level_weights) != 1.0
    assert pack.top_level_weights == (0.06, 0.57, 0.37)


@pytest.mark.parametrize(
    ("path", "invalid"),
    (
        (("weights", "physics"), 0.0),
        (("weights", "physics"), -0.1),
        (("weights", "physics"), 0.4),
        (("physics", "components", 0, "weight"), 0.9),
        (("robustness", "blend_weights", "mean"), 0.4),
        (("robustness", "categories", 0, "weight"), 0.4),
        (("accuracy", "components", 0, "weight"), 0.4),
    ),
)
def test_invalid_weight_maps_reject_without_normalization(
    tmp_path: Path,
    path: tuple[str | int, ...],
    invalid: float,
) -> None:
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, _payload_with(path, invalid))


@pytest.mark.parametrize(
    "payload",
    (
        _payload_without(("weights", "accuracy")),
        _payload_with(("weights", "extra"), 0.1),
        _payload_without(("robustness", "blend_weights", "tail")),
        _payload_with(("robustness", "blend_weights", "extra"), 0.1),
    ),
)
def test_missing_or_extra_weights_reject_instead_of_defaulting(
    tmp_path: Path,
    payload: bytes,
) -> None:
    with pytest.raises(ScorePackSchemaError):
        _load_payload(tmp_path, payload)


def test_score_pack_errors_have_only_safe_stable_metadata(tmp_path: Path) -> None:
    with pytest.raises(ScorePackError) as captured:
        _load_payload(tmp_path, b"not json")
    error = captured.value
    assert type(error.code) is str
    assert type(error.path) is str
    assert "not json" not in str(error)


def test_scoring_root_import_is_dependency_isolated_and_never_delegates_to_legacy(
    tmp_path: Path,
) -> None:
    script = f"""
import importlib.abc
import json
import pathlib
import sys

blocked_roots = {{
    "bittensor", "jax", "mcp", "numpy", "scipy", "torch", "yaml"
}}
blocked_carbon = {{
    "carbon.cards", "carbon.chain", "carbon.common.scoring", "carbon.evaluation",
    "carbon.fees", "carbon.fsm", "carbon.leaderboard", "carbon.logging",
    "carbon.logging_utils", "carbon.mcp", "carbon.receipts", "carbon.traineval",
    "carbon.validator", "neurons.scoring", "poc", "poc.eval.score"
}}

class BoundaryBlocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition(".")[0]
        blocked = root in blocked_roots or any(
            fullname == name or fullname.startswith(name + ".")
            for name in blocked_carbon
        )
        if blocked:
            self.attempted.append(fullname)
            raise ModuleNotFoundError("blocked A5 boundary import", name=fullname)
        return None

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})
blocker = BoundaryBlocker()
sys.meta_path.insert(0, blocker)
from carbon.scoring import ScoreEngine, load_score_pack

sensitive_loaded = sorted(
    name for name in sys.modules
    if name.partition(".")[0] in blocked_roots
    or any(name == item or name.startswith(item + ".") for item in blocked_carbon)
)
print(json.dumps({{
    "attempted": blocker.attempted,
    "callable": callable(load_score_pack) and callable(ScoreEngine.score),
    "sensitive_loaded": sensitive_loaded,
}}))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "attempted": [],
        "callable": True,
        "sensitive_loaded": [],
    }


def test_digest_mismatch_beats_malformed_payload_on_the_same_artifact(
    tmp_path: Path,
) -> None:
    payload = b"\xef\xbb\xbfnot json"
    artifact = tmp_path / "pack.json"
    artifact.write_bytes(payload)
    with pytest.raises(ScorePackIntegrityError) as captured:
        load_score_pack(
            tmp_path,
            "pack.json",
            _pin(scoring_digest="sha256:" + "0" * 64),
        )
    assert captured.value.code == "artifact.digest_mismatch"


def test_score_pack_size_cap_rejects_before_json_parsing(tmp_path: Path) -> None:
    payload = b"{" + b" " * MAX_SCORE_PACK_BYTES + b"}"
    with pytest.raises(ScorePackAccessError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == "artifact.too_large"


@pytest.mark.parametrize(
    ("token", "expected_code"),
    (
        (b"1." + b"0" * 127, "score_pack.numeric_token_too_long"),
        (b"1e-4000", "score_pack.numeric_binary64"),
        (b"1e4000", "score_pack.numeric_binary64"),
    ),
)
def test_numeric_tokens_reject_overlong_or_binary64_losing_values(
    tmp_path: Path,
    token: bytes,
    expected_code: str,
) -> None:
    payload = _fixture_bytes().replace(b'"threshold": 1.0', b'"threshold": ' + token, 1)
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == expected_code


def test_missing_fixture_origin_rejects(tmp_path: Path) -> None:
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, _payload_without(("fixture_origin",)))
    assert captured.value.code == "score_pack.field_required"


def test_same_numeric_input_key_may_be_reused_across_operator_scopes(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["hard_gates"][0]["input_key"] = "shared_numeric"
    document["physics"]["components"][0]["input_key"] = "shared_numeric"
    document["robustness"]["categories"][0]["mean_input_key"] = "shared_numeric"
    document["accuracy"]["components"][0]["input_key"] = "shared_numeric"
    pack = _load_payload(tmp_path, _json_bytes(document))
    numeric_values = (
        ("shared_numeric", 0.25),
        ("diagnostic_error", 0.5),
        ("robust_tail_a", 0.5),
        ("robust_mean_b", 0.5),
        ("robust_tail_b", 0.75),
        ("accuracy_error_b", 0.5),
    )
    score_input = _fixture_input(pack, numeric_values=numeric_values)
    assert tuple(entry.key for entry in score_input.numeric_inputs) == tuple(
        key for key, _ in numeric_values
    )
    assert ScoreEngine.score(score_input, pack).status is ScoreStatus.SCORED


def test_cross_scope_numeric_boolean_input_key_collision_rejects(
    tmp_path: Path,
) -> None:
    payload = _payload_with(
        ("physics", "components", 0, "input_key"),
        "finite_ok",
    )
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, payload)
    assert captured.value.code == "score_pack.input_key_type_collision"


@pytest.mark.parametrize(
    ("path", "duplicate"),
    (
        (("hard_gates", 2, "input_key"), "gate_error"),
        (("robustness", "categories", 1, "mean_input_key"), "robust_mean_a"),
        (("accuracy", "components", 1, "input_key"), "accuracy_error_a"),
    ),
)
def test_in_scope_input_key_duplicates_reject(
    tmp_path: Path,
    path: tuple[str | int, ...],
    duplicate: str,
) -> None:
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, _payload_with(path, duplicate))
    assert captured.value.code == "score_pack.input_key_duplicate"


def test_public_scoring_surface_is_small_and_keeps_evidence_types_private() -> None:
    from carbon import scoring

    assert scoring.__all__ == (
        "BooleanInput",
        "LoadedScorePack",
        "NumericInput",
        "ScoreEngine",
        "ScoreInput",
        "ScoreInputError",
        "ScorePackAccessError",
        "ScorePackError",
        "ScorePackInputError",
        "ScorePackIntegrityError",
        "ScorePackParseError",
        "ScorePackPin",
        "ScorePackPinError",
        "ScorePackSchemaError",
        "ScoreStatus",
        "ScoringComputationError",
        "load_score_pack",
    )
    assert not hasattr(scoring, "InternalResult")
    assert not hasattr(scoring, "GateDecision")
    assert not hasattr(scoring, "LegScore")
    assert not hasattr(scoring, "ScalarScore")


def test_fixture_golden_scoring_result_is_exact_binary64() -> None:
    result = _score_fixture()
    assert result.status is ScoreStatus.SCORED
    assert [decision.passed for decision in result.gate_decisions] == [True, True, True]
    assert tuple(leg.leg for leg in result.leg_scores) == LEG_ORDER
    assert result.leg_scores[0].components[0].score == float.fromhex(
        "0x1.f800000000000p-1"
    )
    assert result.leg_scores[0].score == float.fromhex("0x1.f800000000000p-1")
    assert tuple(component.score for component in result.leg_scores[1].components) == (
        float.fromhex("0x1.d9291ddb596f8p-1"),
        float.fromhex("0x1.a2991f2a97914p-1"),
    )
    assert result.leg_scores[1].score == float.fromhex("0x1.bde11e82f8806p-1")
    assert tuple(component.score for component in result.leg_scores[2].components) == (
        float.fromhex("0x1.999999999999ap-1"),
        float.fromhex("0x1.5555555555555p-1"),
    )
    assert result.leg_scores[2].score == float.fromhex("0x1.7777777777778p-1")
    assert result.combined_score == float.fromhex("0x1.ca07e7d41b693p-1")
    assert result.eligible_for_emission is False


def test_score_engine_rejects_invalid_pack_before_creating_a_result() -> None:
    with pytest.raises(ScorePackSchemaError) as captured:
        ScoreEngine.score(None, object())  # type: ignore[arg-type]
    assert captured.value.code == "score_pack.engine_type"


def test_ready_pack_requires_exact_score_input() -> None:
    pack = _load_fixture()
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(None, pack)
    assert captured.value.code == "score_input.required"
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(object(), pack)  # type: ignore[arg-type]
    assert captured.value.code == "score_input.type"


@pytest.mark.parametrize("state", ("HUMAN_INPUT", "BLOCKED_FOR_LIVE_UNTIL_SET"))
def test_valid_unready_pack_accepts_only_none_and_returns_empty_evidence(
    tmp_path: Path,
    state: str,
) -> None:
    pack = _load_payload(
        tmp_path,
        _payload_with(("physics", "components", 0, "threshold"), state),
    )
    result = ScoreEngine.score(None, pack)
    assert result.status is ScoreStatus.PACK_NOT_READY
    assert result.pack_pin == pack.pack_pin
    assert result.gate_decisions == ()
    assert result.leg_scores == ()
    assert result.combined_score is None
    assert result.eligible_for_emission is False
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(_score_input(), pack)
    assert captured.value.code == "score_input.pack_not_ready"


def test_score_input_pin_mismatch_rejects_before_gate_evaluation(
    tmp_path: Path,
) -> None:
    pack = _load_payload(tmp_path, b" " + _fixture_bytes())
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(_score_input(), pack)
    assert captured.value.code == "score_input.pin_mismatch"


def test_partial_or_infra_shaped_input_never_becomes_a_failed_gate() -> None:
    partial_input = ScoreInput._from_validated_fixture(
        pack_pin=_pin(),
        numeric_inputs=(NumericInput("gate_error", 2.0),),
        boolean_inputs=(),
    )
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(partial_input, _load_fixture())
    assert captured.value.code == "score_input.key_set"
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(
            {"infra_failure": True, "reference": None},  # type: ignore[arg-type]
            _load_fixture(),
        )
    assert captured.value.code == "score_input.type"


@pytest.mark.parametrize(
    ("actual", "expected_status", "expected_passed"),
    (
        (-0.0, ScoreStatus.SCORED, True),
        (math.nextafter(1.0, 0.0), ScoreStatus.SCORED, True),
        (1.0, ScoreStatus.MANDATORY_GATE_FAILED, False),
        (math.nextafter(1.0, math.inf), ScoreStatus.MANDATORY_GATE_FAILED, False),
    ),
)
def test_threshold_gate_uses_strict_below_equal_above_boundary(
    actual: float,
    expected_status: ScoreStatus,
    expected_passed: bool,
) -> None:
    result = _score_fixture(numeric_values=_numeric_values(gate_error=actual))
    assert result.status is expected_status
    assert result.gate_decisions[0].passed is expected_passed


@pytest.mark.parametrize(
    ("actual", "expected_status"),
    ((True, ScoreStatus.SCORED), (False, ScoreStatus.MANDATORY_GATE_FAILED)),
)
def test_boolean_gate_passes_only_on_exact_true(
    actual: bool,
    expected_status: ScoreStatus,
) -> None:
    result = _score_fixture(boolean_values=(("finite_ok", actual),))
    assert result.status is expected_status
    assert result.gate_decisions[1].passed is actual


def test_all_resolved_gates_are_evaluated_in_order_before_mandatory_failure() -> None:
    result = _score_fixture(
        numeric_values=_numeric_values(gate_error=1.0, diagnostic_error=2.0),
        boolean_values=(("finite_ok", False),),
    )
    assert result.status is ScoreStatus.MANDATORY_GATE_FAILED
    assert tuple(decision.gate_id for decision in result.gate_decisions) == (
        "synthetic_error_gate",
        "synthetic_finite_gate",
        "synthetic_optional_diagnostic",
    )
    assert tuple(decision.passed for decision in result.gate_decisions) == (
        False,
        False,
        False,
    )
    assert result.leg_scores == ()
    assert result.combined_score == 0.0
    assert math.copysign(1.0, result.combined_score) == 1.0
    assert result.eligible_for_emission is False


def test_mandatory_failure_never_calls_soft_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    def forbidden_soft_score(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("mandatory failure entered soft scoring")

    monkeypatch.setattr(engine_module, "_physics_score", forbidden_soft_score)
    result = _score_fixture(numeric_values=_numeric_values(gate_error=1.0))
    assert result.status is ScoreStatus.MANDATORY_GATE_FAILED
    assert result.leg_scores == ()


def test_optional_boolean_diagnostic_is_evaluated_in_order_but_score_inert(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["hard_gates"][2] = {
        "operator": "boolean_true",
        "id": "synthetic_optional_diagnostic",
        "input_key": "diagnostic_ok",
        "mandatory": False,
    }
    pack = _load_payload(tmp_path, _json_bytes(document))
    numeric_values = tuple(
        item for item in FIXTURE_NUMERIC_VALUES if item[0] != "diagnostic_error"
    )
    passing = _score_fixture(
        pack=pack,
        numeric_values=numeric_values,
        boolean_values=(("finite_ok", True), ("diagnostic_ok", True)),
    )
    failing = _score_fixture(
        pack=pack,
        numeric_values=numeric_values,
        boolean_values=(("finite_ok", True), ("diagnostic_ok", False)),
    )
    assert tuple(decision.gate_id for decision in passing.gate_decisions) == (
        "synthetic_error_gate",
        "synthetic_finite_gate",
        "synthetic_optional_diagnostic",
    )
    assert passing.gate_decisions[2].passed is True
    assert failing.gate_decisions[2].passed is False
    assert passing.status is failing.status is ScoreStatus.SCORED
    assert passing.leg_scores == failing.leg_scores
    assert passing.combined_score == failing.combined_score


def test_pack_requires_a_non_vacuous_mandatory_gate_set(tmp_path: Path) -> None:
    document = _fixture_object()
    for gate in document["hard_gates"]:
        gate["mandatory"] = False
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, _json_bytes(document))
    assert captured.value.code == "score_pack.mandatory_gate_required"


def test_pack_rejects_an_empty_hard_gate_set(tmp_path: Path) -> None:
    with pytest.raises(ScorePackSchemaError) as captured:
        _load_payload(tmp_path, _payload_with(("hard_gates",), []))
    assert captured.value.code == "score_pack.array_empty"


def test_resolved_optional_diagnostic_failure_has_zero_scoring_influence() -> None:
    passing = _score_fixture(numeric_values=_numeric_values(diagnostic_error=0.0))
    failing = _score_fixture(numeric_values=_numeric_values(diagnostic_error=2.0))
    assert passing.status is failing.status is ScoreStatus.SCORED
    assert passing.gate_decisions[2].passed is True
    assert failing.gate_decisions[2].passed is False
    assert passing.leg_scores == failing.leg_scores
    assert passing.combined_score == failing.combined_score
    assert failing.eligible_for_emission is False


def test_unresolved_optional_diagnostic_is_absent_from_engine_evidence(
    tmp_path: Path,
) -> None:
    pack = _load_payload(
        tmp_path,
        _payload_with(("hard_gates", 2, "threshold"), "HUMAN_INPUT"),
    )
    numeric_values = tuple(
        item for item in FIXTURE_NUMERIC_VALUES if item[0] != "diagnostic_error"
    )
    result = _score_fixture(pack=pack, numeric_values=numeric_values)
    assert result.status is ScoreStatus.SCORED
    assert tuple(decision.gate_id for decision in result.gate_decisions) == (
        "synthetic_error_gate",
        "synthetic_finite_gate",
    )
    assert result.combined_score == _score_fixture().combined_score


def test_zero_soft_leg_remains_scored_and_takes_positive_zero_branch() -> None:
    result = _score_fixture(numeric_values=_numeric_values(physics_error=2.0))
    assert result.status is ScoreStatus.SCORED
    assert all(decision.passed for decision in result.gate_decisions[:2])
    assert result.leg_scores[0].score == 0.0
    assert result.combined_score == 0.0
    assert math.copysign(1.0, result.combined_score) == 1.0
    assert result.eligible_for_emission is False


@pytest.mark.parametrize(
    "error",
    (0.0, math.nextafter(2.0, 0.0), 2.0, math.nextafter(2.0, math.inf)),
)
def test_quadratic_barrier_exact_boundaries(error: float) -> None:
    result = _score_fixture(numeric_values=_numeric_values(physics_error=error))
    component = result.leg_scores[0].components[0].score
    if error < 2.0:
        ratio = error / 2.0
        expected = 1.0 - ratio * ratio
    else:
        expected = 0.0
    assert component == expected


def test_quadratic_barrier_uses_divide_multiply_subtract_order(
    tmp_path: Path,
) -> None:
    threshold = 4.580056320720132e62
    error = 3.9212668579391345e62
    document = _fixture_object()
    document["physics"]["components"][0]["threshold"] = threshold
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(
        pack=pack,
        numeric_values=_numeric_values(physics_error=error),
    )
    ratio = error / threshold
    expected = 1.0 - ratio * ratio
    reordered = 1.0 - (error * error) / (threshold * threshold)
    assert expected != reordered
    assert result.leg_scores[0].components[0].score == expected


def _stable_logistic(z_value: float) -> float:
    if z_value >= 0.0:
        q_value = math.exp(-z_value)
        return q_value / (1.0 + q_value)
    q_value = math.exp(z_value)
    return 1.0 / (1.0 + q_value)


@pytest.mark.parametrize("summary", (0.0, 1.0, 2.0, 1e307))
def test_tail_logistic_both_sign_branches_boundary_and_positive_extreme(
    summary: float,
) -> None:
    result = _score_fixture(
        numeric_values=_numeric_values(
            robust_mean_a=summary,
            robust_tail_a=summary,
            robust_mean_b=summary,
            robust_tail_b=summary,
        )
    )
    difference = summary - 1.0
    scaled = 4.0 * difference
    z_value = scaled / 1.0
    expected = _stable_logistic(z_value)
    assert tuple(component.score for component in result.leg_scores[1].components) == (
        expected,
        expected,
    )


def test_tail_logistic_negative_extreme_is_stable_without_overflow(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["robustness"]["sharpness"] = 1e308
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(
        pack=pack,
        numeric_values=_numeric_values(
            robust_mean_a=0.0,
            robust_tail_a=0.0,
            robust_mean_b=0.0,
            robust_tail_b=0.0,
        ),
    )
    assert tuple(component.score for component in result.leg_scores[1].components) == (
        1.0,
        1.0,
    )


def test_tail_logistic_uses_subtract_multiply_divide_order(
    tmp_path: Path,
) -> None:
    summary = 4345.525366191914
    threshold = 5275.933301018302
    sharpness = 3.2797573271903024
    document = _fixture_object()
    document["robustness"]["threshold"] = threshold
    document["robustness"]["sharpness"] = sharpness
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(
        pack=pack,
        numeric_values=_numeric_values(
            robust_mean_a=summary,
            robust_tail_a=summary,
        ),
    )
    difference = summary - threshold
    scaled = sharpness * difference
    z_value = scaled / threshold
    reordered_z = sharpness * (summary / threshold - 1.0)
    expected = _stable_logistic(z_value)
    reordered = _stable_logistic(reordered_z)
    assert expected != reordered
    assert result.leg_scores[1].components[0].score == expected


@pytest.mark.parametrize("error", (0.0, 1.0, sys.float_info.max))
def test_reciprocal_error_boundaries(error: float) -> None:
    result = _score_fixture(
        numeric_values=_numeric_values(accuracy_error_a=error),
    )
    denominator = 1.0 + error
    expected = 1.0 / denominator
    assert result.leg_scores[2].components[0].score == expected


def test_reciprocal_error_uses_add_then_divide_order(tmp_path: Path) -> None:
    threshold = 4.630515493543561e-29
    error = 5.387835860285573e170
    document = _fixture_object()
    document["accuracy"]["components"][0]["threshold"] = threshold
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(
        pack=pack,
        numeric_values=_numeric_values(accuracy_error_a=error),
    )
    expected = threshold / (threshold + error)
    reordered = 1.0 / (1.0 + error / threshold)
    assert expected != reordered
    assert result.leg_scores[2].components[0].score == expected


def test_all_within_leg_and_top_level_sums_use_declared_order_math_fsum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    pack = _load_fixture()
    score_input = _fixture_input(pack)
    real_fsum = engine_module.math.fsum
    observed: list[tuple[float, ...]] = []

    def recording_fsum(values: tuple[float, ...]) -> float:
        materialized = tuple(values)
        observed.append(materialized)
        return real_fsum(materialized)

    monkeypatch.setattr(engine_module.math, "fsum", recording_fsum)
    result = ScoreEngine.score(score_input, pack)
    physics, robustness, accuracy = result.leg_scores
    assert observed == [
        (physics.components[0].score,),
        (0.5 * 0.25, 0.5 * 0.5),
        (0.5 * 0.5, 0.5 * 0.75),
        tuple(0.5 * component.score for component in robustness.components),
        tuple(0.5 * component.score for component in accuracy.components),
        (
            0.5 * math.log(physics.score),
            0.3 * math.log(robustness.score),
            0.2 * math.log(accuracy.score),
        ),
    ]


def test_required_robustness_category_evidence_cannot_be_partial() -> None:
    missing_category_value = tuple(
        item for item in FIXTURE_NUMERIC_VALUES if item[0] != "robust_tail_b"
    )
    with pytest.raises(ScorePackInputError) as captured:
        _fixture_input(_load_fixture(), numeric_values=missing_category_value)
    assert captured.value.code == "score_pack.input_key_set"


def test_all_one_log_space_path_returns_exact_one(tmp_path: Path) -> None:
    document = _fixture_object()
    document["robustness"]["sharpness"] = 1e308
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(
        pack=pack,
        numeric_values=_numeric_values(
            gate_error=0.0,
            diagnostic_error=0.0,
            physics_error=0.0,
            robust_mean_a=0.0,
            robust_tail_a=0.0,
            robust_mean_b=0.0,
            robust_tail_b=0.0,
            accuracy_error_a=0.0,
            accuracy_error_b=0.0,
        ),
    )
    assert tuple(leg.score for leg in result.leg_scores) == (1.0, 1.0, 1.0)
    assert result.combined_score == 1.0


def test_zero_component_path_does_not_evaluate_logarithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    pack = _load_fixture()
    score_input = _fixture_input(
        pack,
        numeric_values=_numeric_values(physics_error=2.0),
    )

    def forbidden_log(value: float) -> float:
        raise AssertionError(f"zero branch called log({value!r})")

    monkeypatch.setattr(engine_module.math, "log", forbidden_log)
    result = ScoreEngine.score(score_input, pack)
    assert result.status is ScoreStatus.SCORED
    assert result.combined_score == 0.0


def test_positive_top_level_path_calls_three_logs_and_one_final_exponential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    real_log = engine_module.math.log
    real_exp = engine_module.math.exp
    log_arguments: list[float] = []
    exp_arguments: list[float] = []

    def recording_log(value: float) -> float:
        log_arguments.append(value)
        return real_log(value)

    def recording_exp(value: float) -> float:
        exp_arguments.append(value)
        return real_exp(value)

    monkeypatch.setattr(engine_module.math, "log", recording_log)
    monkeypatch.setattr(engine_module.math, "exp", recording_exp)
    result = _score_fixture()
    assert log_arguments == [leg.score for leg in result.leg_scores]
    assert len(log_arguments) == 3
    assert len(exp_arguments) == len(result.leg_scores[1].components) + 1
    expected_log_sum = math.fsum(
        (
            0.5 * real_log(result.leg_scores[0].score),
            0.3 * real_log(result.leg_scores[1].score),
            0.2 * real_log(result.leg_scores[2].score),
        )
    )
    assert exp_arguments[-1] == expected_log_sum
    assert result.combined_score == real_exp(expected_log_sum)


@pytest.mark.parametrize(
    ("top_exp_value", "expected_code"),
    (
        (float("nan"), "scoring.nonfinite"),
        (1.25, "scoring.range"),
    ),
)
def test_invalid_top_level_exponential_result_is_typed_non_scientific_error(
    monkeypatch: pytest.MonkeyPatch,
    top_exp_value: float,
    expected_code: str,
) -> None:
    import carbon.scoring.engine as engine_module

    real_exp = engine_module.math.exp
    calls = 0

    def substituted_top_exp(value: float) -> float:
        nonlocal calls
        calls += 1
        if calls == 3:
            return top_exp_value
        return real_exp(value)

    monkeypatch.setattr(engine_module.math, "exp", substituted_top_exp)
    with pytest.raises(ScoringComputationError) as captured:
        _score_fixture()
    assert calls == 3
    assert captured.value.code == expected_code


def test_top_level_exponential_underflow_remains_scored_canonical_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    real_exp = engine_module.math.exp
    calls = 0

    def underflowing_top_exp(value: float) -> float:
        nonlocal calls
        calls += 1
        if calls == 3:
            return 0.0
        return real_exp(value)

    monkeypatch.setattr(engine_module.math, "exp", underflowing_top_exp)
    result = _score_fixture()
    assert calls == 3
    assert result.status is ScoreStatus.SCORED
    assert result.combined_score == 0.0
    assert math.copysign(1.0, result.combined_score) == 1.0


def test_robustness_intermediate_overflow_is_typed_not_a_gate_failure() -> None:
    with pytest.raises(ScoringComputationError) as captured:
        _score_fixture(
            numeric_values=_numeric_values(
                robust_mean_a=sys.float_info.max,
                robust_tail_a=sys.float_info.max,
                robust_mean_b=sys.float_info.max,
                robust_tail_b=sys.float_info.max,
            )
        )
    assert captured.value.code == "scoring.nonfinite"


@pytest.mark.parametrize(
    ("log_value", "expected_code"),
    (
        (float("nan"), "scoring.nonfinite"),
        (0.25, "scoring.range"),
    ),
)
def test_invalid_log_space_values_raise_typed_non_scientific_error(
    monkeypatch: pytest.MonkeyPatch,
    log_value: float,
    expected_code: str,
) -> None:
    import carbon.scoring.engine as engine_module

    monkeypatch.setattr(engine_module.math, "log", lambda value: log_value)
    with pytest.raises(ScoringComputationError) as captured:
        _score_fixture()
    assert captured.value.code == expected_code


def test_undefined_log_space_operation_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.scoring.engine as engine_module

    def invalid_log(value: float) -> float:
        raise ValueError(f"synthetic invalid log {value!r}")

    monkeypatch.setattr(engine_module.math, "log", invalid_log)
    with pytest.raises(ScoringComputationError) as captured:
        _score_fixture()
    assert captured.value.code == "scoring.arithmetic"


def test_nonfinite_soft_arithmetic_is_not_converted_to_gate_failure(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["accuracy"]["components"][0]["threshold"] = 1e308
    pack = _load_payload(tmp_path, _json_bytes(document))
    with pytest.raises(ScoringComputationError) as captured:
        _score_fixture(
            pack=pack,
            numeric_values=_numeric_values(accuracy_error_a=sys.float_info.max),
        )
    assert captured.value.code == "scoring.nonfinite"


def test_top_level_order_is_fixed_and_json_object_order_is_irrelevant(
    tmp_path: Path,
) -> None:
    baseline = _score_fixture()
    document = _fixture_object()
    weights = document["weights"]
    document["weights"] = {
        "accuracy": weights["accuracy"],
        "physics": weights["physics"],
        "robustness": weights["robustness"],
    }
    reordered_pack = _load_payload(tmp_path, _json_bytes(document))
    reordered = _score_fixture(pack=reordered_pack)
    assert reordered_pack.top_level_weights == (0.5, 0.3, 0.2)
    assert reordered.gate_decisions == baseline.gate_decisions
    assert reordered.leg_scores == baseline.leg_scores
    assert reordered.combined_score == baseline.combined_score


def test_declared_component_order_is_retained_in_result_evidence(
    tmp_path: Path,
) -> None:
    document = _fixture_object()
    document["accuracy"]["components"].reverse()
    pack = _load_payload(tmp_path, _json_bytes(document))
    result = _score_fixture(pack=pack)
    assert tuple(
        component.identifier for component in result.leg_scores[2].components
    ) == ("synthetic_accuracy_b", "synthetic_accuracy_a")
    assert result.leg_scores[2].score == _score_fixture().leg_scores[2].score


def test_repeated_scoring_is_exactly_deterministic() -> None:
    pack = _load_fixture()
    score_input = _fixture_input(pack)
    first = ScoreEngine.score(score_input, pack)
    for _ in range(10):
        assert ScoreEngine.score(score_input, pack) == first


def test_every_fixture_result_disposition_is_non_emitting(tmp_path: Path) -> None:
    scored = _score_fixture()
    gate_failed = _score_fixture(numeric_values=_numeric_values(gate_error=1.0))
    unready_pack = _load_payload(
        tmp_path,
        _payload_with(("weights", "physics"), "BLOCKED_FOR_LIVE_UNTIL_SET"),
    )
    pack_not_ready = ScoreEngine.score(None, unready_pack)
    assert (
        scored.status,
        gate_failed.status,
        pack_not_ready.status,
    ) == (
        ScoreStatus.SCORED,
        ScoreStatus.MANDATORY_GATE_FAILED,
        ScoreStatus.PACK_NOT_READY,
    )
    assert all(
        result.eligible_for_emission is False
        for result in (scored, gate_failed, pack_not_ready)
    )


def test_scoring_computation_error_exposes_only_stable_safe_code() -> None:
    error = ScoringComputationError("scoring.synthetic", "safe message")
    assert error.code == "scoring.synthetic"
    assert str(error) == "safe message"
