"""Strict packet validation independent of model or executor behavior."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from .context import DEFAULT_PROTECTED_PATTERNS
from .identity import GIT_OID_RE, SHA256_RE, normalized_repo_path
from .models import (
    ACCEPTED_EVIDENCE_KINDS,
    FORBIDDEN_AUTHORITY_WORDS,
    PACKET_TYPE_DEVELOPER,
    PACKET_TYPE_EVIDENCE,
    PACKET_TYPE_PLAN,
    SCHEMA_VERSION,
    ControllerPhase,
    PacketValidationError,
    RequirementStatus,
    Role,
    SandboxMode,
)

RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
REQUIREMENT_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{2,63}$")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PacketValidationError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PacketValidationError(f"{label} must be an array")
    return value


def _string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise PacketValidationError(f"{label} must be a non-empty string")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PacketValidationError(f"{label} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise PacketValidationError(f"{label} must be a boolean")
    return value


def _exact_keys(
    value: Mapping[str, Any],
    required: Iterable[str],
    label: str,
    *,
    optional: Iterable[str] = (),
) -> None:
    required_set = set(required)
    optional_set = set(optional)
    missing = required_set - set(value)
    extra = set(value) - required_set - optional_set
    if missing or extra:
        raise PacketValidationError(
            f"{label} keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _schema_version(value: Any, label: str) -> None:
    if value != SCHEMA_VERSION:
        raise PacketValidationError(
            f"{label}.schema_version must be {SCHEMA_VERSION!r}"
        )


def _sha256(value: Any, label: str) -> str:
    text = _string(value, label)
    if not SHA256_RE.fullmatch(text):
        raise PacketValidationError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _oid(value: Any, label: str) -> str:
    text = _string(value, label)
    if not GIT_OID_RE.fullmatch(text):
        raise PacketValidationError(f"{label} must be a lowercase 40-character Git OID")
    return text


def _run_id(value: Any, label: str = "run_id") -> str:
    text = _string(value, label)
    if not RUN_ID_RE.fullmatch(text):
        raise PacketValidationError(f"{label} has an invalid format")
    return text


def _requirement_id(value: Any, label: str) -> str:
    text = _string(value, label)
    if not REQUIREMENT_ID_RE.fullmatch(text):
        raise PacketValidationError(f"{label} has an invalid format")
    return text


def _unique_strings(value: Any, label: str) -> tuple[str, ...]:
    items = tuple(_string(item, f"{label}[]") for item in _array(value, label))
    if len(items) != len(set(items)):
        raise PacketValidationError(f"{label} must not contain duplicates")
    return items


def _paths(value: Any, label: str) -> tuple[str, ...]:
    try:
        items = tuple(normalized_repo_path(item) for item in _array(value, label))
    except Exception as error:
        raise PacketValidationError(
            f"{label} contains an invalid path: {error}"
        ) from error
    if len(items) != len(set(items)):
        raise PacketValidationError(f"{label} must not contain duplicates")
    return items


def validate_requirements_manifest(value: Any) -> dict[str, Any]:
    root = dict(_mapping(value, "RequirementsManifest"))
    _exact_keys(
        root,
        [
            "schema_version",
            "manifest_id",
            "ticket",
            "requirements",
            "verification_commands",
        ],
        "RequirementsManifest",
    )
    _schema_version(root["schema_version"], "RequirementsManifest")
    _string(root["manifest_id"], "manifest_id")
    ticket = _mapping(root["ticket"], "ticket")
    _exact_keys(ticket, ["path", "git_blob", "sha256"], "ticket")
    normalized_repo_path(_string(ticket["path"], "ticket.path"))
    _oid(ticket["git_blob"], "ticket.git_blob")
    _sha256(ticket["sha256"], "ticket.sha256")
    requirements = _array(root["requirements"], "requirements")
    if not requirements:
        raise PacketValidationError("requirements must not be empty")
    seen: set[str] = set()
    for index, raw in enumerate(requirements):
        item = _mapping(raw, f"requirements[{index}]")
        _exact_keys(
            item,
            ["id", "exact_text", "required", "authority_path"],
            f"requirements[{index}]",
        )
        requirement_id = _requirement_id(item["id"], f"requirements[{index}].id")
        if requirement_id in seen:
            raise PacketValidationError(f"duplicate requirement id {requirement_id}")
        seen.add(requirement_id)
        _string(item["exact_text"], f"requirements[{index}].exact_text")
        _boolean(item["required"], f"requirements[{index}].required")
        normalized_repo_path(
            _string(item["authority_path"], f"requirements[{index}].authority_path")
        )
    commands = _mapping(root["verification_commands"], "verification_commands")
    if set(commands) != seen:
        raise PacketValidationError(
            "verification_commands must exactly cover every requirement id"
        )
    for requirement_id, raw_commands in commands.items():
        entries = _array(raw_commands, f"verification_commands.{requirement_id}")
        normalized: list[tuple[str, ...]] = []
        for command_index, raw_command in enumerate(entries):
            command = tuple(
                _string(
                    argument,
                    f"verification_commands.{requirement_id}[{command_index}][]",
                )
                for argument in _array(
                    raw_command,
                    f"verification_commands.{requirement_id}[{command_index}]",
                )
            )
            if not command:
                raise PacketValidationError("verification command must not be empty")
            normalized.append(command)
        if len(normalized) != len(set(normalized)):
            raise PacketValidationError(
                f"verification_commands.{requirement_id} contains duplicates"
            )
    return root


def validate_run_manifest(value: Any) -> dict[str, Any]:
    root = dict(_mapping(value, "RunManifest"))
    _exact_keys(
        root,
        [
            "schema_version",
            "run_id",
            "authority",
            "ticket",
            "requirements",
            "roles",
            "developer_worktree",
            "initial_context",
            "context_allow_paths",
            "permitted_change_paths",
            "protected_patterns",
            "max_iterations",
            "authority_ceiling",
        ],
        "RunManifest",
    )
    _schema_version(root["schema_version"], "RunManifest")
    _run_id(root["run_id"])
    authority = _mapping(root["authority"], "authority")
    _exact_keys(authority, ["ref", "commit", "tree"], "authority")
    _string(authority["ref"], "authority.ref")
    _oid(authority["commit"], "authority.commit")
    _oid(authority["tree"], "authority.tree")
    for key in ("ticket", "requirements"):
        binding = _mapping(root[key], key)
        _exact_keys(binding, ["path", "sha256"], key)
        normalized_repo_path(_string(binding["path"], f"{key}.path"))
        _sha256(binding["sha256"], f"{key}.sha256")
    roles = _mapping(root["roles"], "roles")
    _exact_keys(roles, [role.value.lower() for role in Role], "roles")
    expected_sandboxes = {
        Role.PLANNER: SandboxMode.READ_ONLY,
        Role.DEVELOPER: SandboxMode.WORKSPACE_WRITE,
        Role.TESTER: SandboxMode.READ_ONLY,
    }
    for role in Role:
        profile = _mapping(roles[role.value.lower()], f"roles.{role.value.lower()}")
        _exact_keys(
            profile,
            ["executor_id", "profile_digest", "sandbox"],
            f"roles.{role.value.lower()}",
        )
        _string(profile["executor_id"], f"roles.{role.value.lower()}.executor_id")
        _sha256(profile["profile_digest"], f"roles.{role.value.lower()}.profile_digest")
        if profile["sandbox"] != expected_sandboxes[role].value:
            raise PacketValidationError(
                f"{role.value} sandbox must be {expected_sandboxes[role].value}"
            )
    worktree = _string(root["developer_worktree"], "developer_worktree")
    if not PurePosixPath(worktree).is_absolute():
        raise PacketValidationError("developer_worktree must be an absolute path")
    context = _mapping(root["initial_context"], "initial_context")
    _exact_keys(context, [role.value.lower() for role in Role], "initial_context")
    for role in Role:
        _paths(context[role.value.lower()], f"initial_context.{role.value.lower()}")
    context_allow = _mapping(root["context_allow_paths"], "context_allow_paths")
    _exact_keys(
        context_allow,
        [role.value.lower() for role in Role],
        "context_allow_paths",
    )
    for role in Role:
        _paths(
            context_allow[role.value.lower()],
            f"context_allow_paths.{role.value.lower()}",
        )
    _paths(root["permitted_change_paths"], "permitted_change_paths")
    protected = _unique_strings(root["protected_patterns"], "protected_patterns")
    missing_protections = set(DEFAULT_PROTECTED_PATTERNS) - set(protected)
    if missing_protections:
        raise PacketValidationError(
            "protected_patterns must include every mandatory default: "
            f"{sorted(missing_protections)}"
        )
    _integer(root["max_iterations"], "max_iterations", minimum=1)
    ceilings = _unique_strings(root["authority_ceiling"], "authority_ceiling")
    forbidden_missing = FORBIDDEN_AUTHORITY_WORDS - set(ceilings)
    if forbidden_missing:
        raise PacketValidationError(
            "authority_ceiling must explicitly deny all reserved outcomes: "
            f"{sorted(forbidden_missing)}"
        )
    return root


def _validate_bindings(value: Any, label: str, *, profile_key: str) -> dict[str, Any]:
    bindings = dict(_mapping(value, label))
    _exact_keys(
        bindings,
        [
            "authority_commit",
            "authority_tree",
            "ticket_sha256",
            "requirements_sha256",
            "candidate_head",
            "candidate_tree",
            profile_key,
        ],
        label,
    )
    _oid(bindings["authority_commit"], f"{label}.authority_commit")
    _oid(bindings["authority_tree"], f"{label}.authority_tree")
    _sha256(bindings["ticket_sha256"], f"{label}.ticket_sha256")
    _sha256(bindings["requirements_sha256"], f"{label}.requirements_sha256")
    _oid(bindings["candidate_head"], f"{label}.candidate_head")
    _oid(bindings["candidate_tree"], f"{label}.candidate_tree")
    _sha256(bindings[profile_key], f"{label}.{profile_key}")
    return bindings


def validate_iteration_plan(value: Any, requirement_ids: set[str]) -> dict[str, Any]:
    root = dict(_mapping(value, "IterationPlan"))
    _exact_keys(
        root,
        [
            "schema_version",
            "packet_type",
            "run_id",
            "iteration",
            "bindings",
            "ordered_requirement_ids",
            "actions",
            "context_requests",
            "blocker",
        ],
        "IterationPlan",
    )
    _schema_version(root["schema_version"], "IterationPlan")
    if root["packet_type"] != PACKET_TYPE_PLAN:
        raise PacketValidationError("IterationPlan.packet_type is invalid")
    _run_id(root["run_id"])
    _integer(root["iteration"], "iteration", minimum=1)
    _validate_bindings(
        root["bindings"], "bindings", profile_key="planner_profile_digest"
    )
    ordered = _unique_strings(
        root["ordered_requirement_ids"], "ordered_requirement_ids"
    )
    if not ordered or not set(ordered).issubset(requirement_ids):
        raise PacketValidationError("plan contains missing or unknown requirement ids")
    actions = _array(root["actions"], "actions")
    action_ids: list[str] = []
    for index, raw in enumerate(actions):
        item = _mapping(raw, f"actions[{index}]")
        _exact_keys(
            item, ["requirement_id", "summary", "allowed_paths"], f"actions[{index}]"
        )
        requirement_id = _requirement_id(
            item["requirement_id"], f"actions[{index}].requirement_id"
        )
        if requirement_id not in requirement_ids:
            raise PacketValidationError(f"unknown action requirement {requirement_id}")
        action_ids.append(requirement_id)
        _string(item["summary"], f"actions[{index}].summary")
        _paths(item["allowed_paths"], f"actions[{index}].allowed_paths")
    if action_ids != list(ordered):
        raise PacketValidationError(
            "plan actions must exactly follow ordered_requirement_ids"
        )
    _paths(root["context_requests"], "context_requests")
    blocker = root["blocker"]
    if blocker is not None:
        item = _mapping(blocker, "blocker")
        _exact_keys(item, ["status", "reason"], "blocker")
        if item["status"] not in {
            RequirementStatus.BLOCKED_HUMAN.value,
            RequirementStatus.BLOCKED_INFRA.value,
        }:
            raise PacketValidationError("plan blocker has an invalid status")
        _string(item["reason"], "blocker.reason")
    return root


def validate_developer_result(value: Any) -> dict[str, Any]:
    root = dict(_mapping(value, "DeveloperResult"))
    _exact_keys(
        root,
        [
            "schema_version",
            "packet_type",
            "run_id",
            "iteration",
            "bindings",
            "summary",
            "context_requests",
        ],
        "DeveloperResult",
    )
    _schema_version(root["schema_version"], "DeveloperResult")
    if root["packet_type"] != PACKET_TYPE_DEVELOPER:
        raise PacketValidationError("DeveloperResult.packet_type is invalid")
    _run_id(root["run_id"])
    _integer(root["iteration"], "iteration", minimum=1)
    _validate_bindings(
        root["bindings"],
        "bindings",
        profile_key="developer_profile_digest",
    )
    _string(root["summary"], "summary")
    _paths(root["context_requests"], "context_requests")
    return root


def validate_iteration_evidence(
    value: Any, requirement_ids: set[str]
) -> dict[str, Any]:
    root = dict(_mapping(value, "IterationEvidence"))
    _exact_keys(
        root,
        [
            "schema_version",
            "packet_type",
            "run_id",
            "iteration",
            "bindings",
            "results",
            "context_requests",
            "summary",
        ],
        "IterationEvidence",
    )
    _schema_version(root["schema_version"], "IterationEvidence")
    if root["packet_type"] != PACKET_TYPE_EVIDENCE:
        raise PacketValidationError("IterationEvidence.packet_type is invalid")
    _run_id(root["run_id"])
    _integer(root["iteration"], "iteration", minimum=1)
    _validate_bindings(
        root["bindings"], "bindings", profile_key="tester_profile_digest"
    )
    results = _array(root["results"], "results")
    if not results:
        raise PacketValidationError("evidence results must not be empty")
    seen: set[str] = set()
    for index, raw in enumerate(results):
        item = _mapping(raw, f"results[{index}]")
        _exact_keys(
            item,
            ["requirement_id", "status", "evidence", "reason"],
            f"results[{index}]",
        )
        requirement_id = _requirement_id(
            item["requirement_id"], f"results[{index}].requirement_id"
        )
        if requirement_id not in requirement_ids or requirement_id in seen:
            raise PacketValidationError(f"unknown or duplicate result {requirement_id}")
        seen.add(requirement_id)
        try:
            status = RequirementStatus(item["status"])
        except (TypeError, ValueError) as error:
            raise PacketValidationError(
                f"invalid result status for {requirement_id}"
            ) from error
        if status is RequirementStatus.UNTESTED:
            raise PacketValidationError("Tester cannot emit UNTESTED")
        evidence = _array(item["evidence"], f"results[{index}].evidence")
        for evidence_index, raw_evidence in enumerate(evidence):
            accepted = _mapping(
                raw_evidence, f"results[{index}].evidence[{evidence_index}]"
            )
            _exact_keys(
                accepted,
                [
                    "kind",
                    "artifact",
                    "sha256",
                    "command",
                    "exit_code",
                    "output_sha256",
                    "summary",
                ],
                f"results[{index}].evidence[{evidence_index}]",
            )
            if accepted["kind"] not in ACCEPTED_EVIDENCE_KINDS:
                raise PacketValidationError("unsupported accepted-evidence kind")
            normalized_repo_path(_string(accepted["artifact"], "evidence.artifact"))
            _sha256(accepted["sha256"], "evidence.sha256")
            command = tuple(
                _string(argument, "evidence.command[]")
                for argument in _array(accepted["command"], "evidence.command")
            )
            if not command:
                raise PacketValidationError("evidence.command must not be empty")
            _integer(accepted["exit_code"], "evidence.exit_code", minimum=0)
            _sha256(accepted["output_sha256"], "evidence.output_sha256")
            _string(accepted["summary"], "evidence.summary")
        if status is RequirementStatus.VERIFIED and not evidence:
            raise PacketValidationError(
                f"VERIFIED requirement {requirement_id} has no accepted evidence"
            )
        _string(item["reason"], f"results[{index}].reason")
    _paths(root["context_requests"], "context_requests")
    _string(root["summary"], "summary")
    return root


def _validate_accepted_evidence(value: Any, label: str) -> None:
    accepted = _mapping(value, label)
    _exact_keys(
        accepted,
        [
            "kind",
            "artifact",
            "sha256",
            "command",
            "exit_code",
            "output_sha256",
            "summary",
        ],
        label,
    )
    if accepted["kind"] not in ACCEPTED_EVIDENCE_KINDS:
        raise PacketValidationError(f"{label}.kind is unsupported")
    normalized_repo_path(_string(accepted["artifact"], f"{label}.artifact"))
    _sha256(accepted["sha256"], f"{label}.sha256")
    command = tuple(
        _string(argument, f"{label}.command[]")
        for argument in _array(accepted["command"], f"{label}.command")
    )
    if not command:
        raise PacketValidationError(f"{label}.command must not be empty")
    _integer(accepted["exit_code"], f"{label}.exit_code", minimum=0)
    _sha256(accepted["output_sha256"], f"{label}.output_sha256")
    _string(accepted["summary"], f"{label}.summary")


def validate_controller_state(value: Any, requirement_ids: set[str]) -> dict[str, Any]:
    root = dict(_mapping(value, "ControllerState"))
    _exact_keys(
        root,
        [
            "schema_version",
            "run_id",
            "run_manifest_digest",
            "phase",
            "iteration",
            "candidate",
            "requirements",
            "regressions",
            "disclosures",
            "plan_digests",
            "evidence_digests",
            "active_plan",
            "paused_from",
            "last_error",
        ],
        "ControllerState",
    )
    _schema_version(root["schema_version"], "ControllerState")
    _run_id(root["run_id"])
    _sha256(root["run_manifest_digest"], "run_manifest_digest")
    try:
        ControllerPhase(root["phase"])
    except (TypeError, ValueError) as error:
        raise PacketValidationError("invalid controller phase") from error
    _integer(root["iteration"], "iteration", minimum=1)
    candidate = _mapping(root["candidate"], "candidate")
    _exact_keys(candidate, ["head", "tree", "changed_paths"], "candidate")
    _oid(candidate["head"], "candidate.head")
    _oid(candidate["tree"], "candidate.tree")
    _paths(candidate["changed_paths"], "candidate.changed_paths")
    states = _array(root["requirements"], "requirements")
    seen: set[str] = set()
    for index, raw in enumerate(states):
        item = _mapping(raw, f"requirements[{index}]")
        _exact_keys(
            item,
            [
                "id",
                "status",
                "accepted_evidence",
                "failure_reason",
                "failure_evidence",
            ],
            f"requirements[{index}]",
        )
        requirement_id = _requirement_id(item["id"], f"requirements[{index}].id")
        if requirement_id not in requirement_ids or requirement_id in seen:
            raise PacketValidationError(
                f"invalid controller requirement {requirement_id}"
            )
        seen.add(requirement_id)
        try:
            status = RequirementStatus(item["status"])
        except (TypeError, ValueError) as error:
            raise PacketValidationError(
                "invalid controller requirement status"
            ) from error
        accepted = _array(item["accepted_evidence"], "accepted_evidence")
        for evidence_index, evidence in enumerate(accepted):
            _validate_accepted_evidence(
                evidence,
                f"requirements[{index}].accepted_evidence[{evidence_index}]",
            )
        if status is RequirementStatus.VERIFIED and not accepted:
            raise PacketValidationError("persisted VERIFIED state lacks evidence")
        if status is not RequirementStatus.VERIFIED and accepted:
            raise PacketValidationError("non-VERIFIED state carries accepted evidence")
        failure_evidence = _array(item["failure_evidence"], "failure_evidence")
        for evidence_index, evidence in enumerate(failure_evidence):
            _validate_accepted_evidence(
                evidence,
                f"requirements[{index}].failure_evidence[{evidence_index}]",
            )
        if status in {RequirementStatus.UNTESTED, RequirementStatus.VERIFIED}:
            if item["failure_reason"] is not None or failure_evidence:
                raise PacketValidationError(
                    "UNTESTED/VERIFIED state cannot carry failure detail"
                )
        else:
            _string(item["failure_reason"], f"requirements[{index}].failure_reason")
    if seen != requirement_ids:
        raise PacketValidationError("controller state omits requirements")
    for index, raw in enumerate(_array(root["regressions"], "regressions")):
        regression = _mapping(raw, f"regressions[{index}]")
        _exact_keys(
            regression,
            [
                "requirement_id",
                "detected_iteration",
                "prior_evidence",
                "failure_status",
                "failure_reason",
                "failure_evidence",
                "resolved_iteration",
            ],
            f"regressions[{index}]",
        )
        requirement_id = _requirement_id(
            regression["requirement_id"], f"regressions[{index}].requirement_id"
        )
        if requirement_id not in requirement_ids:
            raise PacketValidationError(f"unknown regression {requirement_id}")
        _integer(
            regression["detected_iteration"],
            f"regressions[{index}].detected_iteration",
            minimum=1,
        )
        try:
            failure_status = RequirementStatus(regression["failure_status"])
        except (TypeError, ValueError) as error:
            raise PacketValidationError(
                "regression failure_status is invalid"
            ) from error
        if failure_status in {RequirementStatus.UNTESTED, RequirementStatus.VERIFIED}:
            raise PacketValidationError("regression failure_status must be a failure")
        for evidence_label in ("prior_evidence", "failure_evidence"):
            evidence_items = _array(
                regression[evidence_label], f"regressions[{index}].{evidence_label}"
            )
            for evidence_index, evidence in enumerate(evidence_items):
                _validate_accepted_evidence(
                    evidence,
                    f"regressions[{index}].{evidence_label}[{evidence_index}]",
                )
        if not regression["prior_evidence"]:
            raise PacketValidationError(
                "regression must retain prior accepted evidence"
            )
        _string(regression["failure_reason"], f"regressions[{index}].failure_reason")
        if regression["resolved_iteration"] is not None:
            resolved = _integer(
                regression["resolved_iteration"],
                f"regressions[{index}].resolved_iteration",
                minimum=1,
            )
            if resolved < regression["detected_iteration"]:
                raise PacketValidationError("regression resolves before detection")
    for index, raw in enumerate(_array(root["disclosures"], "disclosures")):
        disclosure = _mapping(raw, f"disclosures[{index}]")
        _exact_keys(
            disclosure,
            ["role", "iteration", "path", "sha256"],
            f"disclosures[{index}]",
        )
        try:
            Role(disclosure["role"])
        except (TypeError, ValueError) as error:
            raise PacketValidationError("disclosure role is invalid") from error
        _integer(
            disclosure["iteration"],
            f"disclosures[{index}].iteration",
            minimum=1,
        )
        normalized_repo_path(_string(disclosure["path"], f"disclosures[{index}].path"))
        _sha256(disclosure["sha256"], f"disclosures[{index}].sha256")
    for label in ("plan_digests", "evidence_digests"):
        for digest in _array(root[label], label):
            _sha256(digest, f"{label}[]")
    if root["active_plan"] is not None:
        validate_iteration_plan(root["active_plan"], requirement_ids)
    paused_from = root["paused_from"]
    phase = ControllerPhase(root["phase"])
    paused_phases = {
        ControllerPhase.PAUSED_HUMAN,
        ControllerPhase.PAUSED_INFRA,
    }
    if paused_from is not None:
        try:
            source_phase = ControllerPhase(paused_from)
        except (TypeError, ValueError) as error:
            raise PacketValidationError("paused_from is invalid") from error
        if (
            source_phase in paused_phases
            or source_phase is ControllerPhase.FINAL_CANDIDATE_READY
        ):
            raise PacketValidationError("paused_from must be an active phase")
    if (phase in paused_phases) != (paused_from is not None):
        raise PacketValidationError("paused phase and paused_from must appear together")
    if root["last_error"] is not None:
        _string(root["last_error"], "last_error")
    return root
