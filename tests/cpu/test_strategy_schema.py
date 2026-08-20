"""Ratified A2 Strategy v1.0 schema and pure ``dry_validate`` tests."""

from __future__ import annotations

import builtins
import copy
import io
import json
import os
import random
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from carbon.schema import ValidationIssue, ValidationResult, dry_validate

SUPPORTED_BACKBONES = ("deeponet", "fno", "physicsnemo_fno", "uno")
REQUIRED_FIELDS = ("schema_version", "challenge_id", "backbone", "parameters")


def _strategy(**overrides: object) -> dict[object, object]:
    strategy: dict[object, object] = {
        "schema_version": "1.0",
        "challenge_id": "burgers_1d",
        "backbone": "fno",
        "parameters": {},
    }
    strategy.update(overrides)
    return strategy


def _assert_single_issue(
    strategy: object,
    *,
    code: str,
    path: str,
) -> ValidationIssue:
    result = dry_validate(strategy)

    assert isinstance(result, ValidationResult)
    assert result.ok is False
    assert isinstance(result.errors, tuple)
    assert len(result.errors) == 1
    issue = result.errors[0]
    assert isinstance(issue, ValidationIssue)
    assert (issue.code, issue.path) == (code, path)
    assert isinstance(issue.message, str)
    assert issue.message
    return issue


def _fail_if_called(operation: str) -> Callable[..., Any]:
    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError(f"dry_validate unexpectedly used {operation}")

    return fail


def test_minimal_strategy_is_valid_and_result_is_immutable() -> None:
    result = dry_validate(_strategy())

    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == ()
    with pytest.raises((AttributeError, TypeError)):
        result.ok = False  # type: ignore[misc]


def test_valid_inert_nested_parameters_are_not_interpreted() -> None:
    strategy = _strategy(
        parameters={
            "learning_rate": "0.001",
            "source_term": {"kind": "periodic", "coefficients": [1, 2.5, None]},
            "weight_decay": 0.01,
            "flags": [True, False],
            "metadata": {
                "notes": [
                    "official_seed",
                    "import os; subprocess.run('anything')",
                    "distance/time",
                    "relative/reference",
                ]
            },
        }
    )

    assert dry_validate(strategy) == ValidationResult(ok=True, errors=())


@pytest.mark.parametrize("backbone", SUPPORTED_BACKBONES)
def test_each_strategy_v1_backbone_is_accepted(backbone: str) -> None:
    assert dry_validate(_strategy(backbone=backbone)).ok is True


@pytest.mark.parametrize(
    "challenge_id",
    ("a", "burgers1d", "navier_stokes_2d", "challenge-2d_v1"),
)
def test_canonical_identifier_examples_are_accepted(challenge_id: str) -> None:
    assert dry_validate(_strategy(challenge_id=challenge_id)).ok is True


@pytest.mark.parametrize(
    "strategy",
    (None, True, 1, 1.0, "strategy", [], (), set()),
)
def test_non_object_root_is_rejected(strategy: object) -> None:
    _assert_single_issue(strategy, code="strategy.type", path="")


@pytest.mark.parametrize("missing_field", REQUIRED_FIELDS)
def test_each_top_level_field_is_required(missing_field: str) -> None:
    strategy = _strategy()
    del strategy[missing_field]

    _assert_single_issue(
        strategy,
        code="field.required",
        path=f"/{missing_field}",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", 1.0),
        ("schema_version", None),
        ("challenge_id", 7),
        ("challenge_id", b"burgers_1d"),
        ("backbone", ["fno"]),
        ("backbone", None),
        ("parameters", []),
        ("parameters", None),
    ),
)
def test_required_fields_have_exact_types(field: str, value: object) -> None:
    _assert_single_issue(
        _strategy(**{field: value}),
        code="field.type",
        path=f"/{field}",
    )


@pytest.mark.parametrize(
    "unknown_field",
    ("extra", "challenge", "optim", "backbone_cfg", "strategy_version"),
)
def test_unknown_and_legacy_top_level_fields_are_rejected(
    unknown_field: str,
) -> None:
    _assert_single_issue(
        _strategy(**{unknown_field: {}}),
        code="field.unknown",
        path=f"/{unknown_field}",
    )


@pytest.mark.parametrize("version", ("", "1", "v1", "1.1", "2.0"))
def test_unknown_string_versions_fail_closed(version: str) -> None:
    _assert_single_issue(
        _strategy(schema_version=version),
        code="version.unsupported",
        path="/schema_version",
    )


@pytest.mark.parametrize(
    "challenge_id",
    (
        "",
        "1burgers",
        "_burgers",
        "-burgers",
        "Burgers",
        "f\N{LATIN SMALL LETTER N WITH TILDE}o",
        "has space",
        "has\tcontrol",
        "has\ncontrol",
        "path/name",
        "path\\name",
        "path..name",
        "path.name",
        "double__separator",
        "double--separator",
        "mixed_-separator",
        "trailing_",
        "trailing-",
    ),
)
def test_noncanonical_identifiers_are_rejected(challenge_id: str) -> None:
    _assert_single_issue(
        _strategy(challenge_id=challenge_id),
        code="identifier.invalid",
        path="/challenge_id",
    )


@pytest.mark.parametrize("backbone", ("FNO", "PhysicsNeMo_FNO", "fno/2d"))
def test_backbone_is_not_normalized(backbone: str) -> None:
    _assert_single_issue(
        _strategy(backbone=backbone),
        code="identifier.invalid",
        path="/backbone",
    )


@pytest.mark.parametrize(
    "backbone",
    ("fno1d", "fno2d", "gino", "pino", "transolver", "wno", "custom_backend"),
)
def test_legacy_proposal_and_custom_backbones_are_unsupported(
    backbone: str,
) -> None:
    _assert_single_issue(
        _strategy(backbone=backbone),
        code="backbone.unsupported",
        path="/backbone",
    )


def test_runtime_backbone_registration_does_not_change_schema_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from carbon import backbones

    calls: list[str] = []

    def factory() -> object:
        calls.append("constructed")
        return object()

    monkeypatch.setattr(backbones, "_backbones", {})
    backbones.register_backbone("custom_backend", factory)

    unsupported = dry_validate(_strategy(backbone="custom_backend"))
    supported = dry_validate(_strategy(backbone="fno"))

    assert [(issue.code, issue.path) for issue in unsupported.errors] == [
        ("backbone.unsupported", "/backbone")
    ]
    assert supported.ok is True
    assert calls == []


@pytest.mark.parametrize(
    ("parameters", "path"),
    (
        ({1: "value"}, "/parameters"),
        ({"nested": {False: "value"}}, "/parameters/nested"),
        ({"items": [{None: "value"}]}, "/parameters/items/0"),
    ),
)
def test_non_string_mapping_keys_are_rejected(
    parameters: object,
    path: str,
) -> None:
    _assert_single_issue(
        _strategy(parameters=parameters),
        code="json.key_type",
        path=path,
    )


def test_non_string_top_level_key_is_rejected_without_echoing_it() -> None:
    strategy = _strategy()
    strategy[7] = "secret"

    issue = _assert_single_issue(strategy, code="json.key_type", path="")
    assert "secret" not in issue.message


@pytest.mark.parametrize(
    ("value", "path"),
    (
        (b"bytes", "/parameters/value"),
        ({1, 2}, "/parameters/value"),
        ((1, 2), "/parameters/value"),
        (lambda: None, "/parameters/value"),
        (object(), "/parameters/value"),
    ),
)
def test_non_json_parameter_values_are_rejected(value: object, path: str) -> None:
    _assert_single_issue(
        _strategy(parameters={"value": value}),
        code="json.value_type",
        path=path,
    )


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_non_finite_numbers_are_rejected(value: float) -> None:
    _assert_single_issue(
        _strategy(parameters={"nested": [0, value]}),
        code="json.non_finite",
        path="/parameters/nested/1",
    )


@pytest.mark.parametrize(
    "external_reference",
    (
        "https://miner.invalid/model.pkl",
        "file:///private/hidden-pack.json",
        "file:/private/hidden-pack.json",
        "urn:carbon:hidden-exam",
        "data:text/plain,executable-payload",
        "javascript:runMinerCode()",
        "  https://miner.invalid/leading-space",
        "/private/hidden-pack.json",
        "  /private/leading-space.json",
        ".",
        "..",
        "~",
        ".   ",
        " .. ",
        "~ ",
        "./relative-artifact.bin",
        ".\\relative-artifact.bin",
        "../parent-artifact.bin",
        "..\\parent-artifact.bin",
        "~/private-artifact.bin",
        "~\\private-artifact.bin",
        "C:\\private\\artifact.bin",
        "\\\\server\\share\\artifact.bin",
        "git@host.invalid:miner/repository.git",
    ),
)
def test_external_reference_values_are_forbidden_under_neutral_keys(
    external_reference: str,
) -> None:
    issue = _assert_single_issue(
        _strategy(parameters={"value": external_reference}),
        code="capability.forbidden",
        path="/parameters/value",
    )
    if len(external_reference.strip()) > 3:
        assert external_reference not in issue.message


def test_json_pointer_paths_escape_mapping_keys() -> None:
    _assert_single_issue(
        _strategy(parameters={"a/b": {"tilde~key": float("nan")}}),
        code="json.non_finite",
        path="/parameters/a~1b/tilde~0key",
    )


def test_control_character_path_escaping_is_unambiguous() -> None:
    result = dry_validate(
        _strategy(
            parameters={
                "\n": float("nan"),
                "\\u000a": float("nan"),
                "~u00000a": float("nan"),
                "\ufefff": float("nan"),
                "\U000fefff": float("nan"),
            }
        )
    )

    assert {issue.path for issue in result.errors} == {
        "/parameters/~u00000a",
        "/parameters/\\u000a",
        "/parameters/~0u00000a",
        "/parameters/~u00fefff",
        "/parameters/~u0fefff",
    }


def test_mapping_cycle_is_rejected() -> None:
    cycle: dict[str, object] = {}
    cycle["again"] = cycle

    _assert_single_issue(
        _strategy(parameters={"loop": cycle}),
        code="json.cycle",
        path="/parameters/loop/again",
    )


def test_list_cycle_is_rejected() -> None:
    cycle: list[object] = []
    cycle.append(cycle)

    _assert_single_issue(
        _strategy(parameters={"loop": cycle}),
        code="json.cycle",
        path="/parameters/loop/0",
    )


def test_shared_acyclic_container_is_valid() -> None:
    shared = {"coefficient": 1.0}
    strategy = _strategy(parameters={"left": shared, "right": shared})

    assert dry_validate(strategy).ok is True


def test_deep_shared_dag_is_valid_without_repeated_traversal() -> None:
    shared: dict[str, object] = {"leaf": True}
    for _ in range(100):
        shared = {"left": shared, "right": shared}

    assert dry_validate(_strategy(parameters=shared)).ok is True


def test_deep_acyclic_json_does_not_depend_on_python_recursion_limit() -> None:
    nested: dict[str, object] = {"leaf": True}
    for _ in range(1_200):
        nested = {"child": nested}

    assert dry_validate(_strategy(parameters=nested)).ok is True


class _HostileValue:
    def __repr__(self) -> str:
        raise AssertionError("validator called repr on hostile input")

    def __str__(self) -> str:
        raise AssertionError("validator called str on hostile input")


class _HostileMapping(dict[str, object]):
    def items(self) -> object:
        raise AssertionError("validator traversed a mapping subclass")

    def keys(self) -> object:
        raise AssertionError("validator traversed a mapping subclass")

    def __iter__(self) -> object:
        raise AssertionError("validator traversed a mapping subclass")


def test_arbitrary_value_is_rejected_without_calling_user_display_methods() -> None:
    issue = _assert_single_issue(
        _strategy(parameters={"value": _HostileValue()}),
        code="json.value_type",
        path="/parameters/value",
    )

    assert "HostileValue" not in issue.message


def test_mapping_subclass_is_not_traversed_as_trusted_json() -> None:
    _assert_single_issue(
        _HostileMapping(_strategy()),
        code="strategy.type",
        path="",
    )


FORBIDDEN_PARAMETER_KEYS = (
    # Executable material and execution capabilities.
    "code",
    "script",
    "source",
    "imports",
    "modules",
    "entrypoint",
    "command",
    "shell_command",
    "subprocess",
    "executable_blob",
    # External resources and environment/dependency manifests.
    "path",
    "file_path",
    "file_reference",
    "url",
    "uri",
    "repository",
    "dependencies",
    "requirements",
    "packages",
    "environment",
    # Opaque serialized or model artifacts.
    "pickle",
    "serialized_blob",
    "model_weights",
    "state_dict",
    "checkpoint",
    "model_artifact",
    # Miner-controlled evaluation material and identity overrides.
    "training_dataset",
    "eval_dataset",
    "official_seed",
    "eval_seed",
    "stress_seed",
    "draw_id",
    "exam_id",
    "official_exam_override",
    "block_hash",
    "run_nonce",
    # Gate, Score Pack, and precomputed-result overrides.
    "disable_gates",
    "gate_threshold",
    "score_pack",
    "scoring_weights",
    "precomputed_metrics",
    "scores",
    "gates",
    "predictions",
)


@pytest.mark.parametrize("forbidden_key", FORBIDDEN_PARAMETER_KEYS)
def test_forbidden_capability_keys_are_rejected_recursively(
    forbidden_key: str,
) -> None:
    secret = "SENSITIVE_MINER_VALUE_MUST_NOT_BE_ECHOED"
    strategy = _strategy(parameters={"outer": [{"inner": {forbidden_key: secret}}]})

    issue = _assert_single_issue(
        strategy,
        code="capability.forbidden",
        path=f"/parameters/outer/0/inner/{forbidden_key}",
    )
    assert secret not in issue.message


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "OfficialSeed",
        "official-seed",
        "officialseed",
        "evalseed",
        "stressseed",
        "drawid",
        "examid",
        "blockhash",
        "runnonce",
        "STATE_DICT",
        "statedict",
        "modelweights",
        "scorePack",
        "scorepack",
        "shellcommand",
        "precomputedmetrics",
        "trainingdataset",
    ),
)
def test_forbidden_key_matching_cannot_be_bypassed_by_spelling_variants(
    forbidden_key: str,
) -> None:
    result = dry_validate(_strategy(parameters={forbidden_key: "secret"}))

    assert result.ok is False
    assert [(issue.code, issue.path) for issue in result.errors] == [
        ("capability.forbidden", f"/parameters/{forbidden_key}")
    ]


def test_top_level_forbidden_name_is_still_a_fixed_node_unknown_field() -> None:
    _assert_single_issue(
        _strategy(official_seed="secret"),
        code="field.unknown",
        path="/official_seed",
    )


def test_validation_is_non_mutating_and_does_not_normalize_or_default() -> None:
    strategy = _strategy(
        parameters={
            "learning_rate": "1e-3",
            "nested": [{"width": 32}, {"enabled": False}],
        }
    )
    original = copy.deepcopy(strategy)
    parameters = strategy["parameters"]
    assert isinstance(parameters, dict)
    nested = parameters["nested"]

    first = dry_validate(strategy)
    second = dry_validate(strategy)

    assert first == second == ValidationResult(ok=True, errors=())
    assert strategy == original
    assert strategy["parameters"] is parameters
    assert parameters["nested"] is nested


def test_error_order_is_stable_across_input_insertion_order() -> None:
    fields = [
        ("zeta", 1),
        ("parameters", {"nested": {"value": float("nan")}, "code": "secret"}),
        ("backbone", "fno1d"),
        ("schema_version", "2.0"),
        ("challenge_id", "Not_Canonical"),
        ("alpha", 2),
    ]
    forward = dict(fields)
    reverse = dict(reversed(fields))

    first = dry_validate(forward)
    repeated = dry_validate(forward)
    reordered = dry_validate(reverse)
    observed = tuple((issue.code, issue.path) for issue in first.errors)

    assert first == repeated == reordered
    assert observed == (
        ("field.unknown", "/alpha"),
        ("backbone.unsupported", "/backbone"),
        ("identifier.invalid", "/challenge_id"),
        ("capability.forbidden", "/parameters/code"),
        ("json.non_finite", "/parameters/nested/value"),
        ("version.unsupported", "/schema_version"),
        ("field.unknown", "/zeta"),
    )


def test_errors_do_not_echo_values_tracebacks_or_internal_details() -> None:
    secrets_in_input = (
        "PRIVATE_SEED_000000000000000000000000",
        "/Users/validator/private/evaluation-pack.json",
        "https://internal.invalid/hidden-exam",
    )
    result = dry_validate(
        _strategy(
            parameters={
                "official_seed": secrets_in_input[0],
                "file_path": secrets_in_input[1],
                "url": secrets_in_input[2],
                "bad_value": _HostileValue(),
            }
        )
    )
    messages = "\n".join(issue.message for issue in result.errors)

    assert result.ok is False
    for secret in secrets_in_input:
        assert secret not in messages
    assert "Traceback" not in messages
    assert "strategy.py" not in messages
    assert "HostileValue" not in messages


def test_dry_validate_uses_no_runtime_or_external_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from carbon import backbones
    from carbon.backbones import registry as backbone_registry

    with monkeypatch.context() as patch:
        # Filesystem and environment state.
        patch.setattr(builtins, "open", _fail_if_called("builtins.open"))
        patch.setattr(io, "open", _fail_if_called("io.open"))
        patch.setattr(Path, "open", _fail_if_called("Path.open"))
        patch.setattr(Path, "read_text", _fail_if_called("Path.read_text"))
        patch.setattr(Path, "read_bytes", _fail_if_called("Path.read_bytes"))
        patch.setattr(os, "open", _fail_if_called("os.open"))
        patch.setattr(os, "getenv", _fail_if_called("os.getenv"))
        patch.setattr(os, "urandom", _fail_if_called("os.urandom"))
        patch.setattr(type(os.environ), "__getitem__", _fail_if_called("os.environ"))
        patch.setattr(type(os.environ), "get", _fail_if_called("os.environ.get"))

        # Network, randomness, and clock state.
        patch.setattr(socket, "socket", _fail_if_called("socket.socket"))
        patch.setattr(
            socket,
            "create_connection",
            _fail_if_called("socket.create_connection"),
        )
        patch.setattr(socket, "getaddrinfo", _fail_if_called("socket.getaddrinfo"))
        for attribute in ("random", "randint", "randrange", "getrandbits"):
            patch.setattr(random, attribute, _fail_if_called(f"random.{attribute}"))
        for attribute in ("choice", "randbelow", "token_bytes", "token_hex"):
            patch.setattr(secrets, attribute, _fail_if_called(f"secrets.{attribute}"))
        for attribute in ("time", "monotonic", "perf_counter", "process_time"):
            patch.setattr(time, attribute, _fail_if_called(f"time.{attribute}"))

        # Mutable runtime registry lookup or adapter construction.
        for module in (backbones, backbone_registry):
            for attribute in (
                "get_backbone",
                "list_backbones",
                "list_available_backbones",
                "register_backbone",
            ):
                if hasattr(module, attribute):
                    patch.setattr(
                        module,
                        attribute,
                        _fail_if_called(f"{module.__name__}.{attribute}"),
                    )

        result = dry_validate(
            _strategy(parameters={"nested": [None, True, 2, 3.5, "value"]})
        )

    assert result == ValidationResult(ok=True, errors=())


def test_installed_outside_tree_import_is_dependency_free_and_isolated(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert tmp_path != repository_root
    assert repository_root not in tmp_path.parents

    script = """
import importlib.abc
import json
import sys

blocked_roots = {
    "bittensor",
    "jax",
    "neuralop",
    "numpy",
    "physicsnemo",
    "pydantic",
    "scipy",
    "torch",
}
blocked_carbon_modules = {
    "carbon.audit",
    "carbon.backbones",
    "carbon.base",
    "carbon.cards",
    "carbon.chain",
    "carbon.challenges",
    "carbon.common",
    "carbon.data",
    "carbon.emission",
    "carbon.evaluation",
    "carbon.fees",
    "carbon.landscape",
    "carbon.leaderboard",
    "carbon.logging_utils",
    "carbon.mcp",
    "carbon.miner",
    "carbon.physics",
    "carbon.protocol",
    "carbon.qualification",
    "carbon.registry",
    "carbon.sciml",
    "carbon.scoring",
    "carbon.seeding",
    "carbon.specialist",
    "carbon.symbolic",
    "carbon.traineval",
    "carbon.training",
    "carbon.validator",
}

class BoundaryBlocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition(".")[0]
        blocked = root in blocked_roots or any(
            fullname == name or fullname.startswith(name + ".")
            for name in blocked_carbon_modules
        )
        if blocked:
            self.attempted.append(fullname)
            raise ModuleNotFoundError(
                "blocked A2 boundary import",
                name=fullname,
            )
        return None

blocker = BoundaryBlocker()
sys.meta_path.insert(0, blocker)

from carbon.schema import ValidationIssue, ValidationResult, dry_validate
from carbon.schema.strategy import dry_validate as module_dry_validate

strategy = {
    "schema_version": "1.0",
    "challenge_id": "burgers_1d",
    "backbone": "fno",
    "parameters": {"nested": [None, True, 3, 2.5, "value"]},
}
result = dry_validate(strategy)
assert module_dry_validate is dry_validate
assert isinstance(result, ValidationResult)
assert result.ok and result.errors == ()
assert ValidationIssue.__module__ == "carbon.schema.strategy"

sensitive_loaded = sorted(
    name
    for name in sys.modules
    if name.partition(".")[0] in blocked_roots
    or any(
        name == blocked or name.startswith(blocked + ".")
        for blocked in blocked_carbon_modules
    )
)
print(json.dumps({
    "attempted": blocker.attempted,
    "errors_type": type(result.errors).__name__,
    "module": module_dry_validate.__module__,
    "ok": result.ok,
    "sensitive_loaded": sensitive_loaded,
}))
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
        "errors_type": "tuple",
        "module": "carbon.schema.strategy",
        "ok": True,
        "sensitive_loaded": [],
    }
