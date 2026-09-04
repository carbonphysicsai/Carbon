"""Deterministic temporary-repository support for B-01H tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from agent_pack.executors.hoh.context import DEFAULT_PROTECTED_PATTERNS
from agent_pack.executors.hoh.executors import RoleInvocation, ScriptedExecutor
from agent_pack.executors.hoh.identity import digest_file, git_blob, head_identity
from agent_pack.executors.hoh.models import Role
from agent_pack.executors.hoh.state_store import StateStore


def git(repository: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


def commit_file(repository: Path, path: str, content: str, message: str) -> None:
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(repository, "add", path)
    git(repository, "commit", "--quiet", "--message", message)


def controller_packet(invocation: RoleInvocation) -> dict[str, Any]:
    payload = invocation.prompt.split("CONTROLLER_PACKET\n", 1)[1].splitlines()[0]
    value = json.loads(payload)
    assert isinstance(value, dict)
    return value


def plan_packet(
    invocation: RoleInvocation,
    ordered: list[str] | None = None,
    *,
    context_requests: list[str] | None = None,
    blocker: dict[str, str] | None = None,
) -> dict[str, Any]:
    packet = controller_packet(invocation)
    requirement_ids = ordered or [item["id"] for item in packet["requirement_states"]]
    return {
        "schema_version": "1.0",
        "packet_type": "iteration_plan",
        "run_id": packet["run_id"],
        "iteration": packet["iteration"],
        "bindings": packet["bindings"],
        "ordered_requirement_ids": requirement_ids,
        "actions": [
            {
                "requirement_id": requirement_id,
                "summary": f"Implement {requirement_id}",
                "allowed_paths": ["src.txt"],
            }
            for requirement_id in requirement_ids
        ],
        "context_requests": context_requests or [],
        "blocker": blocker,
    }


def developer_packet(invocation: RoleInvocation) -> dict[str, Any]:
    packet = controller_packet(invocation)
    return {
        "schema_version": "1.0",
        "packet_type": "developer_result",
        "run_id": packet["run_id"],
        "iteration": packet["iteration"],
        "bindings": packet["bindings"],
        "summary": "Committed the bounded implementation slice.",
        "context_requests": [],
    }


def evidence_packet(
    invocation: RoleInvocation,
    repository: Path,
    statuses: dict[str, str],
) -> dict[str, Any]:
    packet = controller_packet(invocation)
    evidence = {
        "kind": "TEST_RESULT",
        "artifact": "src.txt",
        "sha256": digest_file(repository / "src.txt"),
        "summary": "Synthetic exact-candidate assertion.",
    }
    return {
        "schema_version": "1.0",
        "packet_type": "iteration_evidence",
        "run_id": packet["run_id"],
        "iteration": packet["iteration"],
        "bindings": packet["bindings"],
        "results": [
            {
                "requirement_id": requirement_id,
                "status": status,
                "evidence": [evidence],
                "reason": f"Synthetic Tester result: {status}.",
            }
            for requirement_id, status in sorted(statuses.items())
        ],
        "context_requests": [],
        "summary": "Independent synthetic Tester pass.",
    }


def make_repository(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    repository = tmp_path / "candidate"
    repository.mkdir()
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Carbon HoH Test")
    git(repository, "config", "user.email", "carbon-hoh@example.invalid")
    git(repository, "config", "commit.gpgsign", "false")
    (repository / "ticket.md").write_text("# Synthetic ticket\n", encoding="utf-8")
    (repository / "src.txt").write_text("base\n", encoding="utf-8")
    private = repository / "private_validator" / "official_cases" / "seed.txt"
    private.parent.mkdir(parents=True)
    private.write_text("protected synthetic canary\n", encoding="utf-8")
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "--message", "base files")
    requirements = {
        "schema_version": "1.0",
        "manifest_id": "synthetic-requirements-v1",
        "ticket": {
            "path": "ticket.md",
            "git_blob": git_blob(repository, "HEAD", "ticket.md"),
            "sha256": digest_file(repository / "ticket.md"),
        },
        "requirements": [
            {
                "id": "REQ-001",
                "exact_text": "The synthetic source records behavior one.",
                "required": True,
                "authority_path": "ticket.md",
            },
            {
                "id": "REQ-002",
                "exact_text": "The synthetic source records behavior two.",
                "required": True,
                "authority_path": "ticket.md",
            },
        ],
    }
    (repository / "requirements.json").write_text(
        json.dumps(requirements, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    git(repository, "add", "requirements.json")
    git(repository, "commit", "--quiet", "--message", "requirements")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repository, requirements


def run_manifest(
    repository: Path,
    requirements: dict[str, Any],
    executor: ScriptedExecutor,
    *,
    permitted: list[str] | None = None,
    max_iterations: int = 4,
) -> dict[str, Any]:
    identity = head_identity(repository)
    profiles = {}
    for role in Role:
        profiles[role.value.lower()] = {
            "executor_id": executor.executor_id(),
            "profile_digest": executor.profile_digest(role),
            "sandbox": ("workspace-write" if role is Role.DEVELOPER else "read-only"),
        }
    return {
        "schema_version": "1.0",
        "run_id": "synthetic-run",
        "authority": {
            "ref": "refs/remotes/origin/main",
            "commit": identity["head"],
            "tree": identity["tree"],
        },
        "ticket": {
            "path": "ticket.md",
            "sha256": digest_file(repository / "ticket.md"),
        },
        "requirements": {
            "path": "requirements.json",
            "sha256": digest_file(repository / "requirements.json"),
        },
        "roles": profiles,
        "developer_worktree": str(repository),
        "initial_context": {
            "planner": ["ticket.md", "requirements.json"],
            "developer": ["ticket.md", "requirements.json"],
            "tester": ["ticket.md", "requirements.json", "src.txt"],
        },
        "context_allow_paths": {
            "planner": ["ticket.md", "requirements.json", "src.txt"],
            "developer": ["**"],
            "tester": ["ticket.md", "requirements.json", "src.txt"],
        },
        "permitted_change_paths": permitted or ["src.txt"],
        "protected_patterns": list(DEFAULT_PROTECTED_PATTERNS),
        "max_iterations": max_iterations,
        "authority_ceiling": [
            "APPROVED_FOR_MERGE",
            "LIVE_AUTHORIZED",
            "MERGE_AUTHORIZED",
            "PRODUCTION_QUALIFIED",
            "SCIENTIFICALLY_QUALIFIED",
            "SECURITY_QUALIFIED",
        ],
    }


def state_store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "external-state")
