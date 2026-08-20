"""Pure validation for Carbon Strategy schema version 1.0.

This module validates an inert declarative document. It deliberately does not
normalize miner input, resolve challenges, consult the runtime backbone
registry, construct models, or assign execution semantics to ``parameters``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_SCHEMA_VERSION = "1.0"
_TOP_LEVEL_FIELDS = (
    "schema_version",
    "challenge_id",
    "backbone",
    "parameters",
)
_SUPPORTED_BACKBONES = frozenset(
    {
        "deeponet",
        "fno",
        "physicsnemo_fno",
        "uno",
    }
)
_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*\Z", re.ASCII)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])", re.ASCII)
_POLICY_SEPARATOR = re.compile(r"[-_ ]+", re.ASCII)

# Strategy v1.0 deliberately uses an explicit vocabulary, not semantic token
# roots. Matching ignores only superficial case/camel-case differences and
# hyphen, ASCII-space, or underscore separators (including compact forms). A
# compound parameter such as ``module_count`` therefore remains inert JSON
# rather than inheriting policy from ``modules``.
_V1_RESERVED_PARAMETER_KEYS = frozenset(
    {
        # Executable material and execution capabilities.
        "code",
        "script",
        "source_code",
        "imports",
        "modules",
        "entrypoint",
        "entrypoints",
        "command",
        "shell_command",
        "subprocess",
        "executable_blob",
        # External resource and dependency/environment references.
        "path",
        "file_path",
        "file_reference",
        "url",
        "uri",
        "repository_reference",
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
        # Evaluation data, hidden identity, and official-control overrides.
        "training_dataset",
        "eval_dataset",
        "evaluation_dataset",
        "seed",
        "seeds",
        "official_seed",
        "eval_seed",
        "evaluation_seed",
        "stress_seed",
        "draw_id",
        "draw_ids",
        "exam_id",
        "exam_ids",
        "official_exam_override",
        "block_hash",
        "run_nonce",
        # Gate, Score Pack, and precomputed-result overrides.
        "disable_gates",
        "gate_override",
        "gate_threshold",
        "score_pack",
        "scoring_weights",
        "score_override",
        "precomputed_metrics",
        "scores",
        "gates",
        "predictions",
    }
)


def _policy_key(value: str) -> str:
    separated = _CAMEL_BOUNDARY.sub("_", value)
    return _POLICY_SEPARATOR.sub("", separated).lower()


_V1_RESERVED_PARAMETER_KEY_FORMS = frozenset(
    _policy_key(key) for key in _V1_RESERVED_PARAMETER_KEYS
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable, miner-safe Strategy validation issue."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Immutable result returned by :func:`dry_validate`."""

    ok: bool
    errors: tuple[ValidationIssue, ...]


def _issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def _pointer_segment(value: str) -> str:
    escaped = value.replace("~", "~0").replace("/", "~1")
    return "".join(
        character if 0x20 <= ord(character) <= 0x7E else f"~u{ord(character):06x}"
        for character in escaped
    )


def _child_path(path: str, segment: str) -> str:
    return f"{path}/{_pointer_segment(segment)}"


def _is_forbidden_parameter_key(value: str) -> bool:
    return _policy_key(value) in _V1_RESERVED_PARAMETER_KEY_FORMS


def _validate_parameters(parameters: dict[object, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    active_containers: set[int] = set()
    completed_containers: set[int] = set()
    stack: list[tuple[bool, object, str]] = [(False, parameters, "/parameters")]

    while stack:
        leaving, value, path = stack.pop()
        value_type = type(value)

        if leaving:
            active_containers.remove(id(value))
            completed_containers.add(id(value))
            continue

        if value_type is dict or value_type is list:
            identity = id(value)
            if identity in active_containers:
                issues.append(
                    _issue(
                        "json.cycle",
                        path,
                        "Cyclic containers are not valid JSON values.",
                    )
                )
                continue
            if identity in completed_containers:
                continue

            active_containers.add(identity)
            stack.append((True, value, path))

            if value_type is dict:
                items = list(dict.items(value))
                if any(type(key) is not str for key, _ in items):
                    issues.append(
                        _issue(
                            "json.key_type",
                            path,
                            "JSON object keys must be strings.",
                        )
                    )
                string_items = sorted(
                    ((key, child) for key, child in items if type(key) is str),
                    key=lambda item: item[0],
                    reverse=True,
                )
                for key, child in string_items:
                    child_path = _child_path(path, key)
                    if _is_forbidden_parameter_key(key):
                        issues.append(
                            _issue(
                                "capability.forbidden",
                                child_path,
                                "This field can supply a forbidden capability or data.",
                            )
                        )
                        continue
                    stack.append((False, child, child_path))
            else:
                for index in range(len(value) - 1, -1, -1):
                    stack.append(
                        (False, list.__getitem__(value, index), f"{path}/{index}")
                    )
            continue

        if value is None or value_type is bool or value_type is int:
            continue
        if value_type is float:
            if not math.isfinite(value):
                issues.append(
                    _issue(
                        "json.non_finite",
                        path,
                        "Non-finite numbers are not valid JSON values.",
                    )
                )
            continue
        if value_type is str:
            continue

        issues.append(
            _issue(
                "json.value_type",
                path,
                "Value is not representable by the Strategy JSON contract.",
            )
        )

    return issues


def dry_validate(strategy: object) -> ValidationResult:
    """Validate a hostile Strategy value without executing or normalizing it."""
    issues: list[ValidationIssue] = []

    if type(strategy) is not dict:
        return ValidationResult(
            ok=False,
            errors=(
                _issue(
                    "strategy.type",
                    "",
                    "Strategy must be a JSON object.",
                ),
            ),
        )

    items = list(dict.items(strategy))
    if any(type(key) is not str for key, _ in items):
        issues.append(
            _issue(
                "json.key_type",
                "",
                "JSON object keys must be strings.",
            )
        )
    fields = {key: value for key, value in items if type(key) is str}

    for field in _TOP_LEVEL_FIELDS:
        if field not in fields:
            issues.append(
                _issue(
                    "field.required",
                    _child_path("", field),
                    "Field is required.",
                )
            )

    for field in sorted(set(fields) - set(_TOP_LEVEL_FIELDS)):
        issues.append(
            _issue(
                "field.unknown",
                _child_path("", field),
                "Unknown top-level field is not allowed.",
            )
        )

    schema_version = fields.get("schema_version")
    if "schema_version" in fields:
        if type(schema_version) is not str:
            issues.append(
                _issue(
                    "field.type",
                    "/schema_version",
                    "Field must be a JSON string.",
                )
            )
        elif schema_version != _SCHEMA_VERSION:
            issues.append(
                _issue(
                    "version.unsupported",
                    "/schema_version",
                    "Only Strategy schema version 1.0 is supported.",
                )
            )

    challenge_id = fields.get("challenge_id")
    if "challenge_id" in fields:
        if type(challenge_id) is not str:
            issues.append(
                _issue(
                    "field.type",
                    "/challenge_id",
                    "Field must be a JSON string.",
                )
            )
        elif _IDENTIFIER.fullmatch(challenge_id) is None:
            issues.append(
                _issue(
                    "identifier.invalid",
                    "/challenge_id",
                    "Identifier must use canonical lowercase ASCII token syntax.",
                )
            )

    backbone = fields.get("backbone")
    if "backbone" in fields:
        if type(backbone) is not str:
            issues.append(
                _issue(
                    "field.type",
                    "/backbone",
                    "Field must be a JSON string.",
                )
            )
        elif _IDENTIFIER.fullmatch(backbone) is None:
            issues.append(
                _issue(
                    "identifier.invalid",
                    "/backbone",
                    "Identifier must use canonical lowercase ASCII token syntax.",
                )
            )
        elif backbone not in _SUPPORTED_BACKBONES:
            issues.append(
                _issue(
                    "backbone.unsupported",
                    "/backbone",
                    "Backbone is not recognized by Strategy schema version 1.0.",
                )
            )

    parameters = fields.get("parameters")
    if "parameters" in fields:
        if type(parameters) is not dict:
            issues.append(
                _issue(
                    "field.type",
                    "/parameters",
                    "Field must be a JSON object.",
                )
            )
        else:
            issues.extend(_validate_parameters(parameters))

    errors = tuple(sorted(issues, key=lambda issue: (issue.path, issue.code)))
    return ValidationResult(ok=not errors, errors=errors)


__all__ = ["ValidationIssue", "ValidationResult", "dry_validate"]
