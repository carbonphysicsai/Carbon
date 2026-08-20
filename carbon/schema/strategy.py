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
_NON_TOKEN = re.compile(r"[^A-Za-z0-9]+", re.ASCII)
_URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:", re.ASCII)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"[A-Za-z]:[\\/]", re.ASCII)

_FORBIDDEN_TOKEN_ROOTS = frozenset(
    {
        "artifact",
        "blob",
        "checkpoint",
        "code",
        "command",
        "containerfile",
        "dataset",
        "dependency",
        "dockerfile",
        "entrypoint",
        "environment",
        "executable",
        "file",
        "gate",
        "import",
        "metric",
        "module",
        "network",
        "package",
        "path",
        "payload",
        "pickle",
        "prediction",
        "pyproject",
        "repo",
        "repository",
        "requirement",
        "score",
        "scoring",
        "script",
        "seed",
        "shell",
        "socket",
        "subprocess",
        "uri",
        "url",
    }
)
_FORBIDDEN_COMPACT_KEYS = frozenset(
    {
        "blockhash",
        "disablegates",
        "drawid",
        "drawids",
        "entrypoint",
        "entrypoints",
        "examid",
        "examids",
        "executableblob",
        "filereference",
        "filepath",
        "gateoverride",
        "gatethreshold",
        "modelartifact",
        "modelweights",
        "officialexamoverride",
        "precomputedmetrics",
        "repositoryreference",
        "runnonce",
        "scoreoverride",
        "scorepack",
        "scoringweights",
        "serializedblob",
        "shellcommand",
        "sourcecode",
        "statedict",
    }
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
        character if character.isprintable() else f"~u{ord(character):06x}"
        for character in escaped
    )


def _child_path(path: str, segment: str) -> str:
    return f"{path}/{_pointer_segment(segment)}"


def _policy_key(value: str) -> tuple[str, frozenset[str]]:
    separated = _CAMEL_BOUNDARY.sub("_", value)
    normalized = _NON_TOKEN.sub("_", separated).strip("_").lower()
    return normalized, frozenset(token for token in normalized.split("_") if token)


def _singular_token(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return f"{value[:-3]}y"
    if value.endswith("s") and not value.endswith("ss") and len(value) > 1:
        return value[:-1]
    return value


def _is_forbidden_parameter_key(value: str) -> bool:
    normalized, tokens = _policy_key(value)
    singular_tokens = frozenset(_singular_token(token) for token in tokens)
    compact = normalized.replace("_", "")

    if singular_tokens & _FORBIDDEN_TOKEN_ROOTS:
        return True
    if compact in _FORBIDDEN_COMPACT_KEYS:
        return True
    if compact.endswith(("seed", "seeds", "dataset", "datasets")):
        return True
    if normalized in {"source", "sources", "weights"}:
        return True
    if "entry" in singular_tokens and "point" in singular_tokens:
        return True
    if {"state", "dict"}.issubset(singular_tokens) or {
        "state",
        "dictionary",
    }.issubset(singular_tokens):
        return True
    if "data" in singular_tokens and singular_tokens & {
        "eval",
        "evaluation",
        "official",
        "stress",
        "train",
        "training",
    }:
        return True
    if "draw" in singular_tokens and "id" in singular_tokens:
        return True
    if "exam" in singular_tokens and singular_tokens & {"id", "override"}:
        return True
    if {"block", "hash"}.issubset(singular_tokens):
        return True
    if {"run", "nonce"}.issubset(singular_tokens):
        return True
    if "model" in singular_tokens and singular_tokens & {
        "artifact",
        "state",
        "weight",
    }:
        return True
    if "serialized" in singular_tokens or "serialization" in singular_tokens:
        return True
    if "override" in singular_tokens:
        return bool(
            singular_tokens
            & {
                "eval",
                "evaluation",
                "exam",
                "gate",
                "official",
                "score",
                "scoring",
                "threshold",
            }
        )
    return False


def _is_forbidden_string_value(value: str) -> bool:
    candidate = value.strip()
    return bool(
        candidate in {".", "..", "~"}
        or _URI_SCHEME.match(candidate)
        or _WINDOWS_ABSOLUTE_PATH.match(candidate)
        or candidate.startswith(
            ("/", "\\", "~/", "~\\", "./", ".\\", "../", "..\\", "git@")
        )
    )


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
            if _is_forbidden_string_value(value):
                issues.append(
                    _issue(
                        "capability.forbidden",
                        path,
                        "This value can supply a forbidden external reference.",
                    )
                )
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
