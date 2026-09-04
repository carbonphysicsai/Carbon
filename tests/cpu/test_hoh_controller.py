"""State-machine, isolation, identity, resume, and synthetic-loop tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from agent_pack.executors.hoh.controller import HarnessController
from agent_pack.executors.hoh.executors import ManualExecutor, ScriptedExecutor
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
    second_plan_state = {
        item["id"]: item
        for item in controller_packet(executor.invocations[3])["requirement_states"]
    }
    assert second_plan_state["REQ-002"]["failure_reason"] == (
        "Synthetic Tester result: FAILED."
    )
    assert second_plan_state["REQ-002"]["failure_evidence"]
    regression_records = controller_packet(third_plan)["regression_records"]
    assert regression_records[0]["requirement_id"] == "REQ-001"
    assert regression_records[0]["prior_evidence"]
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


def test_plan_glob_cannot_expand_beyond_run_change_scope(tmp_path: Path) -> None:
    def broad_plan(invocation):
        packet = plan_packet(invocation)
        for action in packet["actions"]:
            action["allowed_paths"] = ["**"]
        return packet

    executor = ScriptedExecutor({Role.PLANNER: [broad_plan]})
    controller, _, _ = _controller(tmp_path, executor, permitted=["src.txt"])
    controller.initialize()
    with pytest.raises(ScopeViolation, match="does not permit path \\*\\*"):
        controller.step()
    assert controller.snapshot()["phase"] == "PLANNING"


def test_plan_actions_must_follow_ordered_requirement_ids(tmp_path: Path) -> None:
    def metadata_only_regression_order(invocation):
        packet = plan_packet(invocation)
        packet["actions"] = packet["actions"][1:]
        return packet

    executor = ScriptedExecutor({Role.PLANNER: [metadata_only_regression_order]})
    controller, _, _ = _controller(tmp_path, executor)
    controller.initialize()
    with pytest.raises(PacketValidationError, match="exactly follow"):
        controller.step()
    assert controller.snapshot()["phase"] == "PLANNING"


def test_root_protected_developer_path_never_mutates_candidate(tmp_path: Path) -> None:
    def protected_plan(invocation):
        packet = plan_packet(invocation)
        for action in packet["actions"]:
            action["allowed_paths"] = ["hidden_*"]
        return packet

    executor = ScriptedExecutor(
        {Role.PLANNER: [protected_plan], Role.DEVELOPER: [developer_packet]}
    )
    controller, repository, _ = _controller(tmp_path, executor, permitted=["hidden_*"])

    def add_protected(invocation) -> None:
        commit_file(
            invocation.workspace,
            "hidden_evaluation/case.json",
            "must not import\n",
            "protected path",
        )

    executor._hooks[Role.DEVELOPER] = add_protected
    state = controller.initialize()
    original_head = state["candidate"]["head"]
    controller.step()
    with pytest.raises(ScopeViolation, match="protected path"):
        controller.step()
    assert git(repository, "rev-parse", "HEAD") == original_head
    assert not (repository / "hidden_evaluation" / "case.json").exists()


def test_non_regular_developer_git_mode_never_mutates_candidate(tmp_path: Path) -> None:
    def link_plan(invocation):
        packet = plan_packet(invocation)
        for action in packet["actions"]:
            action["allowed_paths"] = ["link.txt"]
        return packet

    executor = ScriptedExecutor(
        {Role.PLANNER: [link_plan], Role.DEVELOPER: [developer_packet]}
    )
    controller, repository, _ = _controller(tmp_path, executor, permitted=["link.txt"])

    def add_link(invocation) -> None:
        (invocation.workspace / "link.txt").symlink_to("missing-target")
        git(invocation.workspace, "add", "link.txt")
        git(invocation.workspace, "commit", "--quiet", "--message", "symlink")

    executor._hooks[Role.DEVELOPER] = add_link
    original_head = controller.initialize()["candidate"]["head"]
    controller.step()
    with pytest.raises(ScopeViolation, match="unsupported Git mode"):
        controller.step()
    assert git(repository, "rev-parse", "HEAD") == original_head
    assert not (repository / "link.txt").exists()


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


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda state: state.update(
                phase="FINAL_CANDIDATE_READY",
                evidence_digests=["0" * 64],
            ),
            "resolved requirement states",
        ),
        (
            lambda state: state.update(phase="DEVELOPING"),
            "requires an active plan",
        ),
        (
            lambda state: state.update(run_id="another-run"),
            "another run",
        ),
    ],
)
def test_resume_rejects_lifecycle_incoherent_persisted_state(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    executor = ScriptedExecutor({})
    controller, _, manifest = _controller(tmp_path, executor)
    state = controller.initialize()
    mutation(state)
    controller.store.save_state(state)
    resumed = HarnessController(
        manifest,
        controller.requirements_manifest,
        executor,
        controller.store,
    )
    with pytest.raises((IdentityMismatch, PacketValidationError), match=message):
        resumed.resume()


def test_resume_recomputes_scope_and_replays_final_evidence(tmp_path: Path) -> None:
    executor = ScriptedExecutor(
        {
            Role.PLANNER: [plan_packet],
            Role.DEVELOPER: [developer_packet],
            Role.TESTER: [
                lambda invocation: evidence_packet(
                    invocation,
                    repository,
                    {"REQ-001": "VERIFIED", "REQ-002": "VERIFIED"},
                )
            ],
        }
    )
    controller, repository, manifest = _controller(tmp_path, executor)
    executor._hooks[Role.DEVELOPER] = _developer_commit(repository, ["candidate"])
    controller.initialize()
    controller.step()
    controller.step()
    final_state = controller.step()
    assert final_state["phase"] == "FINAL_CANDIDATE_READY"

    resumed = HarnessController(
        manifest,
        controller.requirements_manifest,
        executor,
        controller.store,
    )
    assert resumed.resume() == final_state

    forged_evidence = copy.deepcopy(final_state)
    forged_evidence["requirements"][0]["accepted_evidence"][0]["output_sha256"] = (
        "0" * 64
    )
    controller.store.save_state(forged_evidence)
    with pytest.raises(PacketValidationError, match="output digest mismatch"):
        HarnessController(
            manifest,
            controller.requirements_manifest,
            executor,
            controller.store,
        ).resume()

    forged_scope = copy.deepcopy(final_state)
    forged_scope["candidate"]["changed_paths"] = []
    controller.store.save_state(forged_scope)
    with pytest.raises(IdentityMismatch, match="changed-path manifest"):
        HarnessController(
            manifest,
            controller.requirements_manifest,
            executor,
            controller.store,
        ).resume()


def test_every_role_executor_identity_is_bound(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    repository, requirements = make_repository(tmp_path)
    manifest = run_manifest(repository, requirements, executor)
    manifest["roles"]["tester"]["executor_id"] = "substituted-executor"
    controller = HarnessController(
        manifest,
        requirements,
        executor,
        state_store(tmp_path),
    )
    with pytest.raises(IdentityMismatch, match="TESTER executor identity"):
        controller.initialize()


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
        "failure_reason": None,
        "failure_evidence": [],
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


def test_open_optional_regression_blocks_final_handoff(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, repository, _ = _controller(tmp_path, executor)
    controller.state = controller.initialize()
    controller.requirements_manifest["requirements"][0]["required"] = False
    controller.requirements_manifest["requirements"][1]["required"] = False
    controller.requirement_by_id["REQ-001"]["required"] = False
    controller.requirement_by_id["REQ-002"]["required"] = False
    controller.state["phase"] = "TESTING"
    controller.state["requirements"][1] = {
        "id": "REQ-002",
        "status": "VERIFIED",
        "accepted_evidence": [accepted_evidence(repository, "REQ-002")],
        "failure_reason": None,
        "failure_evidence": [],
    }
    invocation_packet = {
        "schema_version": "1.0",
        "packet_type": "iteration_evidence",
        "run_id": controller.run_manifest["run_id"],
        "iteration": 1,
        "bindings": controller._bindings(Role.TESTER),
        "results": [],
        "context_requests": [],
        "summary": "Optional regression.",
    }
    for requirement_id in ("REQ-001", "REQ-002"):
        invocation_packet["results"].append(
            {
                "requirement_id": requirement_id,
                "status": "OUT_OF_SCOPE",
                "evidence": [],
                "reason": "Synthetic Tester result: OUT_OF_SCOPE.",
            }
        )
    executor._responses = {
        Role.TESTER: __import__("collections").deque([invocation_packet])
    }
    controller._test()
    state = controller.snapshot()
    assert state["phase"] == "PLANNING"
    assert state["regressions"][0]["resolved_iteration"] is None


def test_paused_infrastructure_run_can_retry_same_phase(tmp_path: Path) -> None:
    executor = ScriptedExecutor({})
    controller, _, _ = _controller(tmp_path, executor)
    state = controller.initialize()
    assert state["phase"] == "PLANNING"
    paused = controller.step()
    assert paused["phase"] == "PAUSED_INFRA"
    assert paused["paused_from"] == "PLANNING"
    executor._responses = {Role.PLANNER: __import__("collections").deque([plan_packet])}
    retried = controller.retry()
    assert retried["phase"] == "PLANNING"
    assert retried["paused_from"] is None
    assert controller.step()["phase"] == "DEVELOPING"


def test_manual_packet_can_resume_identity_bound_paused_run(tmp_path: Path) -> None:
    repository, requirements = make_repository(tmp_path)
    waiting = ManualExecutor()
    manifest = run_manifest(repository, requirements, waiting)
    store = state_store(tmp_path)
    controller = HarnessController(manifest, requirements, waiting, store)
    controller.initialize()
    paused = controller.step()
    assert paused["phase"] == "PAUSED_HUMAN"
    packet = {
        "schema_version": "1.0",
        "packet_type": "iteration_plan",
        "run_id": manifest["run_id"],
        "iteration": 1,
        "bindings": controller._bindings(Role.PLANNER),
        "ordered_requirement_ids": ["REQ-001", "REQ-002"],
        "actions": [
            {
                "requirement_id": requirement_id,
                "summary": f"Implement {requirement_id}",
                "allowed_paths": ["src.txt"],
            }
            for requirement_id in ("REQ-001", "REQ-002")
        ],
        "context_requests": [],
        "blocker": None,
    }
    resumed = HarnessController(
        manifest,
        requirements,
        ManualExecutor(packet=packet),
        store,
    )
    resumed.resume()
    resumed.retry()
    assert resumed.step()["phase"] == "DEVELOPING"


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
