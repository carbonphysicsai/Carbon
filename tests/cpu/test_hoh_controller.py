"""State-machine, isolation, identity, resume, and synthetic-loop tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from agent_pack.executors.hoh.controller import HarnessController
from agent_pack.executors.hoh.executors import ScriptedExecutor
from agent_pack.executors.hoh.models import (
    ControllerPhase,
    IdentityMismatch,
    PacketValidationError,
    Role,
    ScopeViolation,
)
from tests.cpu.hoh_support import (
    accepted_evidence,
    commit_file,
    controller_packet,
    developer_packet,
    evidence_packet,
    git,
    make_repository,
    plan_packet,
    run_manifest,
    state_store,
)


def _developer_commit(_repository: Path, contents: list[str]):
    def hook(invocation) -> None:
        content = contents.pop(0)
        commit_file(
            invocation.workspace,
            "src.txt",
            f"{content}\n",
            f"iteration {invocation.iteration}",
        )

    return hook


def _controller(
    tmp_path: Path,
    executor: ScriptedExecutor,
    *,
    permitted: list[str] | None = None,
    max_iterations: int = 4,
) -> tuple[HarnessController, Path, dict]:
    repository, requirements = make_repository(tmp_path)
    manifest = run_manifest(
        repository,
        requirements,
        executor,
        permitted=permitted,
        max_iterations=max_iterations,
    )
    return (
        HarnessController(
            manifest,
            requirements,
            executor,
            state_store(tmp_path),
        ),
        repository,
        manifest,
    )


def test_synthetic_failure_replan_regression_repair_success(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, repository, manifest = _controller(tmp_path, executor)
    executor._responses = {  # deterministic queues are part of the fake adapter
        Role.PLANNER: __import__("collections").deque(
            [
                lambda invocation: plan_packet(invocation),
                lambda invocation: plan_packet(invocation, ["REQ-002", "REQ-001"]),
                lambda invocation: plan_packet(invocation, ["REQ-001", "REQ-002"]),
            ]
        ),
        Role.DEVELOPER: __import__("collections").deque(
            [developer_packet, developer_packet, developer_packet]
        ),
        Role.TESTER: __import__("collections").deque(
            [
                lambda invocation: evidence_packet(
                    invocation,
                    repository,
                    {"REQ-001": "VERIFIED", "REQ-002": "FAILED"},
                ),
                lambda invocation: evidence_packet(
                    invocation,
                    repository,
                    {"REQ-001": "FAILED", "REQ-002": "VERIFIED"},
                ),
                lambda invocation: evidence_packet(
                    invocation,
                    repository,
                    {"REQ-001": "VERIFIED", "REQ-002": "VERIFIED"},
                ),
            ]
        ),
    }
    executor._hooks[Role.DEVELOPER] = _developer_commit(
        repository, ["bad", "repair-b", "repair-regression"]
    )
    controller.initialize()
    phases = []
    for _ in range(9):
        phases.append(controller.step()["phase"])
    state = controller.snapshot()
    assert phases == [
        "DEVELOPING",
        "TESTING",
        "PLANNING",
        "DEVELOPING",
        "TESTING",
        "PLANNING",
        "DEVELOPING",
        "TESTING",
        "FINAL_CANDIDATE_READY",
    ]
    assert state["iteration"] == 3
    assert state["phase"] == ControllerPhase.FINAL_CANDIDATE_READY.value
    assert state["regressions"] == [
        {
            "requirement_id": "REQ-001",
            "detected_iteration": 2,
            "prior_evidence": state["regressions"][0]["prior_evidence"],
            "failure_status": "FAILED",
            "failure_reason": "Synthetic Tester result: FAILED.",
            "failure_evidence": state["regressions"][0]["failure_evidence"],
            "resolved_iteration": 3,
        }
    ]
    third_plan = executor.invocations[6]
    assert third_plan.role is Role.PLANNER
    assert controller_packet(third_plan)["open_regressions"] == ["REQ-001"]
    assert all(item["status"] == "VERIFIED" for item in state["requirements"])
    assert state["candidate"]["head"] != manifest["authority"]["commit"]


@pytest.mark.parametrize("role", [Role.PLANNER, Role.TESTER])
def test_read_roles_use_read_only_projection_not_candidate(
    tmp_path: Path,
    role: Role,
) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)
    if role is Role.PLANNER:
        executor._responses = {
            Role.PLANNER: __import__("collections").deque([plan_packet])
        }
        controller.initialize()
        controller.step()
        invocation = executor.invocations[0]
    else:
        executor._responses = {
            Role.PLANNER: __import__("collections").deque([plan_packet]),
            Role.DEVELOPER: __import__("collections").deque([developer_packet]),
            Role.TESTER: __import__("collections").deque(
                [
                    lambda invocation: evidence_packet(
                        invocation,
                        repository,
                        {"REQ-001": "FAILED", "REQ-002": "FAILED"},
                    )
                ]
            ),
        }
        executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["candidate"])
        controller.initialize()
        controller.step()
        controller.step()
        controller.step()
        invocation = executor.invocations[-1]
    assert invocation.role is role
    assert invocation.sandbox.value == "read-only"
    assert invocation.workspace.resolve() != repository.resolve()
    assert (invocation.workspace / ".carbon-hoh-context.json").is_file()
    disclosed = invocation.workspace / "ticket.md"
    with pytest.raises(PermissionError):
        disclosed.write_text("mutation attempt\n", encoding="utf-8")
    assert (repository / "ticket.md").read_text(
        encoding="utf-8"
    ) == "# Synthetic ticket\n"


def test_developer_is_bound_to_workspace_and_plan_scope(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)
    executor._responses = {
        Role.PLANNER: __import__("collections").deque([plan_packet]),
        Role.DEVELOPER: __import__("collections").deque([developer_packet]),
    }
    executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["bounded"])
    controller.initialize()
    controller.step()
    controller.step()
    invocation = executor.invocations[-1]
    assert invocation.role is Role.DEVELOPER
    assert invocation.sandbox.value == "workspace-write"
    assert invocation.workspace.resolve() != repository.resolve()
    assert not (
        invocation.workspace / "private_validator" / "official_cases" / "seed.txt"
    ).exists()
    assert (repository / "src.txt").read_text(encoding="utf-8") == "bounded\n"


def test_unexpected_path_expansion_fails_closed(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, _repository, _ = _controller(tmp_path, executor)
    executor._responses = {
        Role.PLANNER: __import__("collections").deque([plan_packet]),
        Role.DEVELOPER: __import__("collections").deque([developer_packet]),
    }

    def expand(invocation) -> None:
        commit_file(
            invocation.workspace,
            "outside.txt",
            "expanded\n",
            "scope expansion",
        )

    executor._hooks[Role.DEVELOPER] = expand
    controller.initialize()
    controller.step()
    with pytest.raises(ScopeViolation, match="does not permit path outside.txt"):
        controller.step()
    assert controller.snapshot()["phase"] == "DEVELOPING"


def test_malformed_plan_cannot_advance(tmp_path: Path) -> None:
    def malformed(invocation):
        packet = plan_packet(invocation)
        packet["merge_authorized"] = True
        return packet

    executor = ScriptedExecutor({Role.PLANNER: [malformed]})
    controller, _, _ = _controller(tmp_path, executor)
    controller.initialize()
    with pytest.raises(PacketValidationError, match="extra"):
        controller.step()
    assert controller.snapshot()["phase"] == "PLANNING"


def test_blocked_human_model_packet_cannot_promote_itself(tmp_path: Path) -> None:
    executor = ScriptedExecutor(
        {
            Role.PLANNER: [
                lambda invocation: plan_packet(
                    invocation,
                    blocker={
                        "status": "BLOCKED_HUMAN",
                        "reason": "Reserved scientific value is unavailable.",
                    },
                )
            ]
        }
    )
    controller, _, _ = _controller(tmp_path, executor)
    controller.initialize()
    state = controller.step()
    assert state["phase"] == "PAUSED_HUMAN"
    with pytest.raises(PacketValidationError, match="terminal phase"):
        controller.step()


def test_authority_drift_and_candidate_mismatch_fail_closed(tmp_path: Path) -> None:
    executor = ScriptedExecutor({Role.PLANNER: [plan_packet]})
    controller, repository, _ = _controller(tmp_path, executor)
    controller.initialize()
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD^")
    with pytest.raises(IdentityMismatch, match="authority drift"):
        controller.step()

    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    commit_file(repository, "src.txt", "unexpected candidate\n", "external mutation")
    with pytest.raises(IdentityMismatch, match="candidate head/tree mismatch"):
        controller.step()


def test_resume_is_deterministic_and_manifest_bound(tmp_path: Path) -> None:
    executor = ScriptedExecutor({Role.PLANNER: [plan_packet]})
    controller, _repository, manifest = _controller(tmp_path, executor)
    initialized = controller.initialize()
    resumed = HarnessController(
        manifest,
        controller.requirements_manifest,
        executor,
        controller.store,
    )
    assert resumed.resume() == initialized

    changed = copy.deepcopy(manifest)
    changed["max_iterations"] += 1
    mismatched = HarnessController(
        changed,
        controller.requirements_manifest,
        executor,
        controller.store,
    )
    with pytest.raises(IdentityMismatch, match="stored run manifest"):
        mismatched.resume()


def test_in_memory_requirements_must_match_bound_manifest_file(
    tmp_path: Path,
) -> None:
    executor = ScriptedExecutor({})
    repository, requirements = make_repository(tmp_path)
    manifest = run_manifest(repository, requirements, executor)
    substituted = copy.deepcopy(requirements)
    substituted["requirements"][0]["exact_text"] = "Substituted requirement."
    controller = HarnessController(
        manifest,
        substituted,
        executor,
        state_store(tmp_path),
    )
    with pytest.raises(IdentityMismatch, match="in-memory requirements"):
        controller.initialize()


def test_regression_must_lead_next_plan(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)
    executor._responses = {
        Role.PLANNER: __import__("collections").deque(
            [
                plan_packet,
                lambda invocation: plan_packet(invocation, ["REQ-002", "REQ-001"]),
            ]
        ),
        Role.DEVELOPER: __import__("collections").deque([developer_packet]),
        Role.TESTER: __import__("collections").deque(
            [
                lambda invocation: evidence_packet(
                    invocation,
                    repository,
                    {"REQ-001": "FAILED", "REQ-002": "VERIFIED"},
                )
            ]
        ),
    }
    executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["candidate"])
    controller.initialize()
    controller.step()
    controller.step()
    state = controller.snapshot()
    state["requirements"][0] = {
        "id": "REQ-001",
        "status": "VERIFIED",
        "accepted_evidence": [accepted_evidence(repository, "REQ-001")],
    }
    controller.state = state
    controller.step()
    with pytest.raises(PacketValidationError, match="open regression"):
        controller.step()


def test_fabricated_evidence_digest_cannot_create_verified(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)

    def fabricated(invocation):
        packet = evidence_packet(
            invocation,
            repository,
            {"REQ-001": "VERIFIED", "REQ-002": "VERIFIED"},
        )
        packet["results"][0]["evidence"][0]["sha256"] = "0" * 64
        return packet

    executor._responses = {
        Role.PLANNER: __import__("collections").deque([plan_packet]),
        Role.DEVELOPER: __import__("collections").deque([developer_packet]),
        Role.TESTER: __import__("collections").deque([fabricated]),
    }
    executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["candidate"])
    controller.initialize()
    controller.step()
    controller.step()
    with pytest.raises(PacketValidationError, match="digest mismatch"):
        controller.step()
    assert controller.snapshot()["phase"] == "TESTING"


def test_disclosed_file_and_fabricated_success_cannot_create_verified(
    tmp_path: Path,
) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)

    def fabricated(invocation):
        packet = evidence_packet(
            invocation,
            repository,
            {"REQ-001": "VERIFIED", "REQ-002": "VERIFIED"},
        )
        forged = packet["results"][0]["evidence"][0]
        forged["command"] = ["python3", "-c", "raise SystemExit(0)"]
        forged["exit_code"] = 0
        forged["output_sha256"] = __import__("hashlib").sha256(b"\0").hexdigest()
        forged["summary"] = "A disclosed file proves success."
        return packet

    executor._responses = {
        Role.PLANNER: __import__("collections").deque([plan_packet]),
        Role.DEVELOPER: __import__("collections").deque([developer_packet]),
        Role.TESTER: __import__("collections").deque([fabricated]),
    }
    executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["candidate"])
    controller.initialize()
    controller.step()
    controller.step()
    with pytest.raises(PacketValidationError, match="not authorized"):
        controller.step()
    assert controller.snapshot()["phase"] == "TESTING"
