"""Deterministic identity-bound Planner/Developer/Tester outer loop."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .context import (
    DEFAULT_PROTECTED_PATTERNS,
    ContextBroker,
    assert_payload_safe,
    path_matches,
)
from .executors import EvidenceInvocation, Executor, RoleInvocation
from .identity import (
    changed_paths,
    digest_bytes,
    digest_file,
    digest_value,
    git_blob,
    git_blob_bytes,
    git_command,
    head_identity,
    require_ancestor,
    require_clean_worktree,
    resolve_commit,
    resolve_repository_root,
    resolve_tree,
    sanitized_git_environment,
)
from .models import (
    SCHEMA_VERSION,
    ControllerPhase,
    ExecutorUnavailable,
    HarnessError,
    IdentityMismatch,
    PacketValidationError,
    PauseRequested,
    RequirementStatus,
    Role,
    SandboxMode,
    ScopeViolation,
)
from .state_store import StateStore
from .validation import (
    validate_controller_state,
    validate_developer_result,
    validate_iteration_evidence,
    validate_iteration_plan,
    validate_requirements_manifest,
    validate_run_manifest,
)

Validator = Callable[[Any], dict[str, Any]]


class HarnessController:
    """Advance only schema-valid, independently evidenced controller state."""

    def __init__(
        self,
        run_manifest: Mapping[str, Any],
        requirements_manifest: Mapping[str, Any],
        executor: Executor | None,
        state_store: StateStore,
    ) -> None:
        self.run_manifest = validate_run_manifest(dict(run_manifest))
        self.requirements_manifest = validate_requirements_manifest(
            dict(requirements_manifest)
        )
        self.executor = executor
        self.store = state_store
        self.repository = Path(self.run_manifest["developer_worktree"]).resolve()
        if resolve_repository_root(self.repository) != self.repository:
            raise IdentityMismatch(
                "developer_worktree must be the exact root of a dedicated Git worktree"
            )
        self.requirement_ids = {
            item["id"] for item in self.requirements_manifest["requirements"]
        }
        self.requirement_by_id = {
            item["id"]: item for item in self.requirements_manifest["requirements"]
        }
        self.manifest_digest = digest_value(self.run_manifest)
        self.protected_patterns = tuple(
            dict.fromkeys(
                (*DEFAULT_PROTECTED_PATTERNS, *self.run_manifest["protected_patterns"])
            )
        )
        self.context = ContextBroker(
            self.repository,
            self.store.root,
            self.run_manifest,
        )
        self.state: dict[str, Any] | None = None
        self._persisted_state_digest: str | None = None

    @property
    def schemas_root(self) -> Path:
        return Path(__file__).resolve().parent / "schemas"

    @property
    def prompts_root(self) -> Path:
        return Path(__file__).resolve().parent / "prompts"

    def initialize(self) -> dict[str, Any]:
        with self.store.locked():
            return self._initialize_locked()

    def _initialize_locked(self) -> dict[str, Any]:
        self._verify_static_identities()
        self._verify_executor_profiles()
        candidate = head_identity(self.repository)
        candidate_paths = self._authorize_candidate(candidate["head"])
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_manifest["run_id"],
            "run_manifest_digest": self.manifest_digest,
            "phase": ControllerPhase.PLANNING.value,
            "iteration": 1,
            "candidate": {
                **candidate,
                "changed_paths": list(candidate_paths),
            },
            "requirements": [
                {
                    "id": requirement_id,
                    "status": RequirementStatus.UNTESTED.value,
                    "accepted_evidence": [],
                    "failure_reason": None,
                    "failure_evidence": [],
                }
                for requirement_id in sorted(self.requirement_ids)
            ],
            "regressions": [],
            "disclosures": [],
            "plan_digests": [],
            "evidence_digests": [],
            "active_plan": None,
            "paused_from": None,
            "last_error": None,
        }
        validate_controller_state(state, self.requirement_ids)
        assert_payload_safe(state, self.protected_patterns)
        self.store.initialize(self.run_manifest, state)
        self.state = state
        self._persisted_state_digest = digest_value(state)
        return self.snapshot()

    def resume(self, *, verify_executor: bool = True) -> dict[str, Any]:
        with self.store.locked():
            return self._resume_locked(verify_executor=verify_executor)

    def _resume_locked(self, *, verify_executor: bool = True) -> dict[str, Any]:
        stored_manifest = validate_run_manifest(self.store.load_manifest())
        if digest_value(stored_manifest) != self.manifest_digest:
            raise IdentityMismatch(
                "stored run manifest does not match requested manifest"
            )
        state = validate_controller_state(
            self.store.load_state(),
            self.requirement_ids,
        )
        if state["run_manifest_digest"] != self.manifest_digest:
            raise IdentityMismatch("controller state is bound to another run manifest")
        self.state = state
        self._verify_static_identities()
        if verify_executor:
            self._verify_executor_profiles()
        self._verify_candidate_identity()
        assert_payload_safe(state, self.protected_patterns)
        self._verify_resumed_state(replay_final_evidence=verify_executor)
        self._persisted_state_digest = digest_value(state)
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        if self.state is None:
            raise IdentityMismatch("controller is not initialized or resumed")
        return json.loads(json.dumps(self.state))

    def step(self) -> dict[str, Any]:
        with self.store.locked():
            return self._step_locked()

    def _step_locked(self) -> dict[str, Any]:
        if self.state is None:
            raise IdentityMismatch("controller is not initialized or resumed")
        self._require_persisted_state_current()
        phase = ControllerPhase(self.state["phase"])
        try:
            self._verify_static_identities()
            self._verify_executor_profiles()
            self._verify_candidate_identity()
            if phase is ControllerPhase.PLANNING:
                self._plan()
            elif phase is ControllerPhase.DEVELOPING:
                self._develop()
            elif phase is ControllerPhase.TESTING:
                self._test()
            else:
                raise PacketValidationError(
                    f"terminal phase {phase.value} cannot advance"
                )
            if ControllerPhase(self.state["phase"]) not in {
                ControllerPhase.PAUSED_HUMAN,
                ControllerPhase.PAUSED_INFRA,
            }:
                self.state["paused_from"] = None
                self.state["last_error"] = None
        except PauseRequested as error:
            self.state["phase"] = error.phase.value
            self.state["paused_from"] = phase.value
            self.state["last_error"] = error.reason
        except (ExecutorUnavailable, OSError, subprocess.TimeoutExpired) as error:
            self.state["phase"] = ControllerPhase.PAUSED_INFRA.value
            self.state["paused_from"] = phase.value
            self.state["last_error"] = self._safe_diagnostic(error)
        except HarnessError as error:
            self.state["last_error"] = self._safe_diagnostic(error)
            self._persist()
            raise
        self._persist()
        return self.snapshot()

    def retry(self) -> dict[str, Any]:
        """Resume one identity-bound paused run at the phase that requested pause."""

        with self.store.locked():
            return self._retry_locked()

    def _retry_locked(self) -> dict[str, Any]:

        if self.state is None:
            raise IdentityMismatch("controller is not initialized or resumed")
        self._require_persisted_state_current()
        phase = ControllerPhase(self.state["phase"])
        if phase not in {ControllerPhase.PAUSED_HUMAN, ControllerPhase.PAUSED_INFRA}:
            raise PacketValidationError("only a paused run can be retried")
        self._verify_static_identities()
        self._verify_executor_profiles()
        self._verify_candidate_identity()
        source = self.state["paused_from"]
        if source is None:
            raise PacketValidationError("paused run has no resumable source phase")
        next_state = self.snapshot()
        next_state["phase"] = ControllerPhase(source).value
        next_state["paused_from"] = None
        next_state["last_error"] = None
        validate_controller_state(next_state, self.requirement_ids)
        assert_payload_safe(next_state, self.protected_patterns)
        self.store.save_state(next_state)
        self.state = next_state
        self._persisted_state_digest = digest_value(next_state)
        return self.snapshot()

    def _require_persisted_state_current(self) -> None:
        if self._persisted_state_digest is None:
            raise IdentityMismatch("controller has no persisted-state identity")
        persisted = validate_controller_state(
            self.store.load_state(),
            self.requirement_ids,
        )
        if digest_value(persisted) != self._persisted_state_digest:
            raise IdentityMismatch(
                "persisted controller state changed since this controller loaded it"
            )

    def _safe_diagnostic(self, error: BaseException) -> str:
        diagnostic = f"{type(error).__name__}: {error}"
        try:
            assert_payload_safe(diagnostic, self.protected_patterns)
        except PacketValidationError:
            return f"{type(error).__name__}: protected diagnostic redacted"
        return diagnostic

    def _persist(self) -> None:
        assert self.state is not None
        validate_controller_state(self.state, self.requirement_ids)
        assert_payload_safe(self.state, self.protected_patterns)
        self.store.save_state(self.state)
        self._persisted_state_digest = digest_value(self.state)

    def _verify_static_identities(self) -> None:
        authority = self.run_manifest["authority"]
        current_authority = resolve_commit(self.repository, authority["ref"])
        if current_authority != authority["commit"]:
            raise IdentityMismatch(
                f"authority drift: expected {authority['commit']}, found {current_authority}"
            )
        if resolve_tree(self.repository, authority["commit"]) != authority["tree"]:
            raise IdentityMismatch("authority commit/tree binding is invalid")
        ticket_binding = self.run_manifest["ticket"]
        candidate_head = (
            self.state["candidate"]["head"]
            if self.state is not None
            else resolve_commit(self.repository)
        )
        ticket_bytes = git_blob_bytes(
            self.repository, candidate_head, ticket_binding["path"]
        )
        if digest_bytes(ticket_bytes) != ticket_binding["sha256"]:
            raise IdentityMismatch("ticket content digest mismatch")
        requirements_binding = self.run_manifest["requirements"]
        requirements_bytes = git_blob_bytes(
            self.repository, candidate_head, requirements_binding["path"]
        )
        if digest_bytes(requirements_bytes) != requirements_binding["sha256"]:
            raise IdentityMismatch("requirements manifest digest mismatch")
        try:
            bound_requirements = validate_requirements_manifest(
                json.loads(requirements_bytes.decode("utf-8"))
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            PacketValidationError,
        ) as error:
            raise IdentityMismatch(
                f"bound requirements manifest is invalid: {error}"
            ) from error
        if bound_requirements != self.requirements_manifest:
            raise IdentityMismatch(
                "in-memory requirements do not match the bound manifest file"
            )
        ticket = self.requirements_manifest["ticket"]
        if ticket["path"] != ticket_binding["path"]:
            raise IdentityMismatch(
                "requirements manifest is bound to another ticket path"
            )
        if ticket["sha256"] != ticket_binding["sha256"]:
            raise IdentityMismatch(
                "requirements manifest is bound to other ticket bytes"
            )
        current_blob = git_blob(self.repository, candidate_head, ticket["path"])
        if current_blob != ticket["git_blob"]:
            raise IdentityMismatch("requirements manifest ticket Git blob mismatch")

    def _verify_executor_profiles(self) -> None:
        if self.executor is None:
            raise ExecutorUnavailable("a live executor is required for this transition")
        roles = self.run_manifest["roles"]
        executor_id = self.executor.executor_id()
        for role in Role:
            profile = roles[role.value.lower()]
            if executor_id != profile["executor_id"]:
                raise IdentityMismatch(
                    f"{role.value} executor identity differs from the run manifest"
                )
            expected = profile["profile_digest"]
            actual = self.executor.profile_digest(role)
            if actual != expected:
                raise IdentityMismatch(f"{role.value} executor profile drift")

    def _require_executor(self) -> Executor:
        if self.executor is None:
            raise ExecutorUnavailable("a live executor is required for this transition")
        return self.executor

    def _verify_candidate_identity(self) -> None:
        assert self.state is not None
        actual = head_identity(self.repository)
        expected = self.state["candidate"]
        if actual["head"] != expected["head"] or actual["tree"] != expected["tree"]:
            raise IdentityMismatch(
                "candidate head/tree mismatch; refusing to resume or advance"
            )
        actual_paths = self._authorize_candidate(actual["head"])
        if actual_paths != tuple(expected["changed_paths"]):
            raise IdentityMismatch(
                "candidate changed-path manifest does not match exact Git history"
            )

    def _require_candidate_ref(self, operation: str) -> None:
        """Require HEAD to remain the exact state-bound candidate ref."""

        assert self.state is not None
        expected = {
            "head": self.state["candidate"]["head"],
            "tree": self.state["candidate"]["tree"],
        }
        if head_identity(self.repository) != expected:
            raise IdentityMismatch(f"candidate changed during {operation}")

    def _authorize_candidate(self, candidate_head: str) -> tuple[str, ...]:
        """Recompute and enforce the cumulative candidate Git boundary."""

        authority = self.run_manifest["authority"]["commit"]
        require_ancestor(self.repository, authority, candidate_head)
        paths = changed_paths(self.repository, authority, candidate_head)
        self._require_paths_allowed(
            paths,
            tuple(self.run_manifest["permitted_change_paths"]),
            "run manifest",
        )
        for path in paths:
            if path_matches(path, self.protected_patterns):
                raise ScopeViolation(f"candidate changed protected path {path}")
        self._require_regular_git_modes(
            self.repository,
            authority,
            candidate_head,
            paths,
        )
        return paths

    def _verify_resumed_state(self, *, replay_final_evidence: bool = True) -> None:
        """Re-establish lifecycle facts that untrusted persisted JSON cannot assert."""

        assert self.state is not None
        if self.state["run_id"] != self.run_manifest["run_id"]:
            raise IdentityMismatch("controller state belongs to another run")
        if self.state["iteration"] > self.run_manifest["max_iterations"]:
            raise PacketValidationError("controller state exceeds the iteration bound")

        active_plan = self.state["active_plan"]
        if active_plan is not None:
            expected = self._bindings(Role.PLANNER)
            phase = ControllerPhase(self.state["phase"])
            paused_from = self.state["paused_from"]
            testing_candidate = phase is ControllerPhase.TESTING or (
                paused_from == ControllerPhase.TESTING.value
            )
            if testing_candidate:
                expected["candidate_head"] = resolve_commit(
                    self.repository, f"{self.state['candidate']['head']}^"
                )
                expected["candidate_tree"] = resolve_tree(
                    self.repository, expected["candidate_head"]
                )
            if dict(active_plan["bindings"]) != expected:
                raise IdentityMismatch(
                    "persisted active plan bindings do not match its candidate phase"
                )
            self._validate_plan_paths(active_plan)
            open_regressions = self._open_regression_ids()
            if (
                tuple(active_plan["ordered_requirement_ids"][: len(open_regressions)])
                != open_regressions
            ):
                raise PacketValidationError(
                    "persisted plan does not place every open regression first"
                )

        if self.state["phase"] != ControllerPhase.FINAL_CANDIDATE_READY.value:
            return
        for requirement in self.state["requirements"]:
            specification = self.requirement_by_id[requirement["id"]]
            if specification["required"] and (
                requirement["status"] != RequirementStatus.VERIFIED.value
            ):
                raise PacketValidationError(
                    "FINAL_CANDIDATE_READY contains an unverified required requirement"
                )
        if self._open_regression_ids():
            raise PacketValidationError(
                "FINAL_CANDIDATE_READY contains an unresolved regression"
            )
        if replay_final_evidence:
            self._replay_final_persisted_evidence()

    def _replay_final_persisted_evidence(self) -> None:
        """Re-run final accepted evidence instead of trusting external state bytes."""

        assert self.state is not None
        tester_disclosures = [
            item
            for item in self.state["disclosures"]
            if item["role"] == Role.TESTER.value
            and item["iteration"] == self.state["iteration"]
        ]
        authorized_paths, authorized_disclosures = self.context.grant(
            Role.TESTER,
            (item["path"] for item in tester_disclosures),
            iteration=self.state["iteration"],
            candidate=self.state["candidate"],
        )
        expected_disclosures = tuple(
            sorted(tester_disclosures, key=lambda item: item["path"])
        )
        if authorized_disclosures != expected_disclosures:
            raise PacketValidationError(
                "persisted Tester disclosures do not match current authorized files"
            )
        workspace = self.context.projection(
            Role.TESTER,
            self.state["iteration"],
            authorized_paths,
            self.state["candidate"],
        )
        self._verify_evidence(
            {
                "results": [
                    {
                        "requirement_id": item["id"],
                        "status": item["status"],
                        "evidence": item["accepted_evidence"],
                    }
                    for item in self.state["requirements"]
                ]
            },
            workspace,
        )

    def _bindings(self, role: Role) -> dict[str, str]:
        assert self.state is not None
        return {
            "authority_commit": self.run_manifest["authority"]["commit"],
            "authority_tree": self.run_manifest["authority"]["tree"],
            "ticket_sha256": self.run_manifest["ticket"]["sha256"],
            "requirements_sha256": self.run_manifest["requirements"]["sha256"],
            "candidate_head": self.state["candidate"]["head"],
            "candidate_tree": self.state["candidate"]["tree"],
            f"{role.value.lower()}_profile_digest": self.run_manifest["roles"][
                role.value.lower()
            ]["profile_digest"],
        }

    def _require_bindings(self, actual: Mapping[str, Any], role: Role) -> None:
        expected = self._bindings(role)
        if dict(actual) != expected:
            raise IdentityMismatch(
                f"{role.value} packet bindings do not match exact controller state"
            )

    def _role_prompt(self, role: Role, context_paths: tuple[str, ...]) -> str:
        assert self.state is not None
        template = (self.prompts_root / f"{role.value.lower()}.md").read_text(
            encoding="utf-8"
        )
        packet = {
            "run_id": self.run_manifest["run_id"],
            "iteration": self.state["iteration"],
            "bindings": self._bindings(role),
            "requirement_states": self.state["requirements"],
            "open_regressions": self._open_regression_ids(),
            "regression_records": [
                item
                for item in self.state["regressions"]
                if item["resolved_iteration"] is None
            ],
            "disclosed_paths": list(context_paths),
            "authority_ceiling": self.run_manifest["authority_ceiling"],
            "active_plan": self.state["active_plan"],
        }
        assert_payload_safe(packet, self.protected_patterns)
        return f"{template.rstrip()}\n\nCONTROLLER_PACKET\n{json.dumps(packet, sort_keys=True)}\n"

    def _invoke(
        self,
        role: Role,
        schema_name: str,
        validator: Validator,
    ) -> tuple[dict[str, Any], Path, dict[str, str]]:
        assert self.state is not None
        initial = self.run_manifest["initial_context"][role.value.lower()]
        previous = [
            item["path"]
            for item in self.state["disclosures"]
            if item["role"] == role.value
        ]
        planned = []
        if role is Role.DEVELOPER and self.state["active_plan"] is not None:
            patterns = (
                path
                for action in self.state["active_plan"]["actions"]
                for path in action["allowed_paths"]
            )
            planned = list(
                self.context.matching_tracked(patterns, self.state["candidate"])
            )
        context_paths, disclosures = self.context.grant(
            role,
            [*initial, *previous, *planned],
            iteration=self.state["iteration"],
            candidate=self.state["candidate"],
        )
        self._append_disclosures(disclosures)
        before = dict(self.state["candidate"])
        before.pop("changed_paths", None)
        if head_identity(self.repository) != before:
            raise IdentityMismatch(f"candidate changed before {role.value} invocation")
        sandbox = (
            SandboxMode.WORKSPACE_WRITE
            if role is Role.DEVELOPER
            else SandboxMode.READ_ONLY
        )
        for _attempt in range(4):
            workspace = self.context.projection(
                role,
                self.state["iteration"],
                context_paths,
                self.state["candidate"],
            )
            identity_workspace = (
                self.context.developer_shadow(self.state["iteration"])
                if role is Role.DEVELOPER
                else workspace
            )
            workspace_before = head_identity(identity_workspace)
            invocation = RoleInvocation(
                role=role,
                sandbox=sandbox,
                workspace=workspace,
                prompt=self._role_prompt(role, context_paths),
                output_schema=self.schemas_root / schema_name,
                context_paths=context_paths,
                iteration=self.state["iteration"],
            )
            raw = dict(self._require_executor().execute(invocation))
            assert_payload_safe(raw, self.protected_patterns)
            packet = validator(raw)
            requests = tuple(packet["context_requests"])
            if not requests:
                break
            newly_granted, new_disclosures = self.context.grant(
                role,
                requests,
                iteration=self.state["iteration"],
                candidate=self.state["candidate"],
            )
            self._append_disclosures(new_disclosures)
            context_paths = tuple(sorted(set(context_paths) | set(newly_granted)))
        else:
            raise ScopeViolation(f"{role.value} exceeded the context-request limit")
        if role is Role.DEVELOPER:
            workspace = self.context.seal_developer_projection(
                workspace,
                self.state["iteration"],
            )
        else:
            if head_identity(workspace) != workspace_before:
                raise ScopeViolation(f"{role.value} mutated its read-only projection")
            require_clean_worktree(workspace)
            after = head_identity(self.repository)
            if after != before:
                raise ScopeViolation(f"{role.value} mutated the candidate")
        return packet, workspace, workspace_before

    def _append_disclosures(self, disclosures: tuple[dict[str, Any], ...]) -> None:
        assert self.state is not None
        existing = {
            (item["role"], item["iteration"], item["path"], item["sha256"])
            for item in self.state["disclosures"]
        }
        for item in disclosures:
            key = (item["role"], item["iteration"], item["path"], item["sha256"])
            if key not in existing:
                self.state["disclosures"].append(item)
                existing.add(key)
        self.state["disclosures"].sort(
            key=lambda item: (item["iteration"], item["role"], item["path"])
        )

    def _plan(self) -> None:
        assert self.state is not None
        packet, _workspace, _workspace_before = self._invoke(
            Role.PLANNER,
            "iteration_plan.schema.json",
            lambda value: validate_iteration_plan(value, self.requirement_ids),
        )
        self._require_common_packet(packet)
        self._require_bindings(packet["bindings"], Role.PLANNER)
        open_regressions = self._open_regression_ids()
        if (
            tuple(packet["ordered_requirement_ids"][: len(open_regressions)])
            != open_regressions
        ):
            raise PacketValidationError(
                "plan must place every open regression ahead of new work"
            )
        blocker = packet["blocker"]
        if blocker is not None:
            self.state["phase"] = (
                ControllerPhase.PAUSED_HUMAN.value
                if blocker["status"] == RequirementStatus.BLOCKED_HUMAN.value
                else ControllerPhase.PAUSED_INFRA.value
            )
            self.state["paused_from"] = ControllerPhase.PLANNING.value
            self.state["last_error"] = blocker["reason"]
            return
        self._validate_plan_paths(packet)
        self.state["active_plan"] = packet
        self.state["plan_digests"].append(digest_value(packet))
        self.state["phase"] = ControllerPhase.DEVELOPING.value

    def _develop(self) -> None:
        assert self.state is not None
        before = {
            "head": self.state["candidate"]["head"],
            "tree": self.state["candidate"]["tree"],
        }
        packet, workspace, workspace_before = self._invoke(
            Role.DEVELOPER,
            "developer_result.schema.json",
            validate_developer_result,
        )
        self._require_common_packet(packet)
        self._require_bindings(packet["bindings"], Role.DEVELOPER)
        after, iteration_paths = self._import_developer_changes(
            workspace,
            workspace_before,
            before,
        )
        cumulative_paths = changed_paths(
            self.repository,
            self.run_manifest["authority"]["commit"],
            after["head"],
        )
        plan_patterns = tuple(
            path
            for action in self.state["active_plan"]["actions"]
            for path in action["allowed_paths"]
        )
        self._require_paths_allowed(iteration_paths, plan_patterns, "iteration plan")
        self.state["candidate"] = {
            **after,
            "changed_paths": list(cumulative_paths),
        }
        self.state["phase"] = ControllerPhase.TESTING.value
        validate_controller_state(self.state, self.requirement_ids)
        assert_payload_safe(self.state, self.protected_patterns)

    def _test(self) -> None:
        assert self.state is not None
        packet, workspace, _workspace_before = self._invoke(
            Role.TESTER,
            "iteration_evidence.schema.json",
            lambda value: validate_iteration_evidence(value, self.requirement_ids),
        )
        self._require_common_packet(packet)
        self._require_bindings(packet["bindings"], Role.TESTER)
        self._verify_evidence(packet, workspace)
        result_ids = {item["requirement_id"] for item in packet["results"]}
        if result_ids != self.requirement_ids:
            raise PacketValidationError(
                "Tester evidence must cover every requirement on the exact candidate"
            )
        previous = {item["id"]: dict(item) for item in self.state["requirements"]}
        next_states: list[dict[str, Any]] = []
        for result in sorted(
            packet["results"], key=lambda item: item["requirement_id"]
        ):
            requirement_id = result["requirement_id"]
            status = RequirementStatus(result["status"])
            if (
                status is RequirementStatus.OUT_OF_SCOPE
                and self.requirement_by_id[requirement_id]["required"]
            ):
                raise PacketValidationError(
                    f"required requirement {requirement_id} cannot be OUT_OF_SCOPE"
                )
            old = RequirementStatus(previous[requirement_id]["status"])
            if (
                old is RequirementStatus.VERIFIED
                and status is not RequirementStatus.VERIFIED
            ):
                self.state["regressions"].append(
                    {
                        "requirement_id": requirement_id,
                        "detected_iteration": self.state["iteration"],
                        "prior_evidence": previous[requirement_id]["accepted_evidence"],
                        "failure_status": status.value,
                        "failure_reason": result["reason"],
                        "failure_evidence": result["evidence"],
                        "resolved_iteration": None,
                    }
                )
            if status is RequirementStatus.VERIFIED:
                for regression in self.state["regressions"]:
                    if (
                        regression["requirement_id"] == requirement_id
                        and regression["resolved_iteration"] is None
                    ):
                        regression["resolved_iteration"] = self.state["iteration"]
            next_states.append(
                {
                    "id": requirement_id,
                    "status": status.value,
                    "accepted_evidence": (
                        result["evidence"]
                        if status is RequirementStatus.VERIFIED
                        else []
                    ),
                    "failure_reason": (
                        None
                        if status is RequirementStatus.VERIFIED
                        else result["reason"]
                    ),
                    "failure_evidence": (
                        []
                        if status is RequirementStatus.VERIFIED
                        else result["evidence"]
                    ),
                }
            )
        self.state["requirements"] = next_states
        self.state["evidence_digests"].append(digest_value(packet))
        statuses = {RequirementStatus(item["status"]) for item in next_states}
        if RequirementStatus.BLOCKED_HUMAN in statuses:
            self.state["phase"] = ControllerPhase.PAUSED_HUMAN.value
            self.state["paused_from"] = ControllerPhase.TESTING.value
            self.state["last_error"] = "Tester reported a human-owned blocker"
        elif RequirementStatus.BLOCKED_INFRA in statuses:
            self.state["phase"] = ControllerPhase.PAUSED_INFRA.value
            self.state["paused_from"] = ControllerPhase.TESTING.value
            self.state["last_error"] = "Tester reported an infrastructure blocker"
        elif not self._open_regression_ids() and all(
            RequirementStatus(item["status"])
            in {RequirementStatus.VERIFIED, RequirementStatus.OUT_OF_SCOPE}
            for item in next_states
        ):
            self.state["active_plan"] = None
            self.state["phase"] = ControllerPhase.FINAL_CANDIDATE_READY.value
        elif self.state["iteration"] >= self.run_manifest["max_iterations"]:
            self.state["phase"] = ControllerPhase.PAUSED_INFRA.value
            self.state["paused_from"] = ControllerPhase.TESTING.value
            self.state["last_error"] = "bounded iteration limit reached"
        else:
            self.state["active_plan"] = None
            self.state["iteration"] += 1
            self.state["phase"] = ControllerPhase.PLANNING.value

    def _import_developer_changes(
        self,
        workspace: Path,
        workspace_before: Mapping[str, str],
        candidate_before: Mapping[str, str],
    ) -> tuple[dict[str, str], tuple[str, ...]]:
        """Validate and import one sanitized Developer projection commit."""

        require_clean_worktree(workspace)
        projected_after = head_identity(workspace)
        if projected_after == dict(workspace_before):
            raise PacketValidationError(
                "Developer produced no committed candidate change"
            )
        iteration_paths = changed_paths(
            workspace,
            workspace_before["head"],
            projected_after["head"],
        )
        plan_patterns = tuple(
            path
            for action in self.state["active_plan"]["actions"]
            for path in action["allowed_paths"]
        )
        self._require_paths_allowed(iteration_paths, plan_patterns, "iteration plan")
        self._require_paths_allowed(
            iteration_paths,
            tuple(self.run_manifest["permitted_change_paths"]),
            "run manifest",
        )
        for path in iteration_paths:
            if path_matches(path, self.protected_patterns):
                raise ScopeViolation(f"Developer changed protected path {path}")
        self._require_regular_git_modes(
            workspace,
            workspace_before["head"],
            projected_after["head"],
            iteration_paths,
        )
        if head_identity(self.repository) != dict(candidate_before):
            raise IdentityMismatch("candidate changed during Developer invocation")
        diff = subprocess.run(
            git_command(
                "diff",
                "--binary",
                "--full-index",
                "--no-ext-diff",
                "--no-textconv",
                workspace_before["head"],
                projected_after["head"],
                "--",
            ),
            cwd=workspace,
            env=sanitized_git_environment(),
            check=False,
            capture_output=True,
        )
        if diff.returncode or not diff.stdout:
            raise PacketValidationError("Developer commit has no importable patch")
        with tempfile.TemporaryDirectory(
            prefix="candidate-transaction-", dir=self.store.root
        ) as transaction_directory:
            index_path = Path(transaction_directory) / "index"
            environment = {
                **sanitized_git_environment(home=transaction_directory),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_INDEX_FILE": str(index_path),
            }

            def run_git(*arguments: str, input_bytes: bytes | None = None):
                return subprocess.run(
                    git_command(*arguments),
                    cwd=self.repository,
                    env=environment,
                    input=input_bytes,
                    check=False,
                    capture_output=True,
                )

            read_tree = run_git("read-tree", candidate_before["head"])
            checked = run_git(
                "apply",
                "--binary",
                "--cached",
                "--check",
                input_bytes=diff.stdout,
            )
            applied = run_git("apply", "--binary", "--cached", input_bytes=diff.stdout)
            if read_tree.returncode or checked.returncode or applied.returncode:
                detail = (
                    read_tree.stderr
                    or checked.stderr
                    or applied.stderr
                    or applied.stdout
                ).decode("utf-8", errors="replace")
                raise PacketValidationError(
                    f"Developer patch import failed closed: {detail.strip()}"
                )
            tree_result = run_git("write-tree")
            if tree_result.returncode:
                detail = (tree_result.stderr or tree_result.stdout).decode(
                    "utf-8", errors="replace"
                )
                raise PacketValidationError(
                    f"controller could not write candidate tree: {detail.strip()}"
                )
            candidate_tree = tree_result.stdout.decode().strip()
            commit_environment = {
                **environment,
                "GIT_AUTHOR_NAME": "Carbon HoH Controller",
                "GIT_AUTHOR_EMAIL": "carbon-hoh@example.invalid",
                "GIT_COMMITTER_NAME": "Carbon HoH Controller",
                "GIT_COMMITTER_EMAIL": "carbon-hoh@example.invalid",
            }
            committed = subprocess.run(
                git_command(
                    "-c",
                    "commit.gpgsign=false",
                    "commit-tree",
                    candidate_tree,
                    "-p",
                    candidate_before["head"],
                    "-m",
                    f"Carbon HoH iteration {self.state['iteration']}",
                ),
                cwd=self.repository,
                env=commit_environment,
                check=False,
                capture_output=True,
            )
            if committed.returncode:
                detail = (committed.stderr or committed.stdout).decode(
                    "utf-8", errors="replace"
                )
                raise PacketValidationError(
                    f"controller could not create candidate commit: {detail.strip()}"
                )
            candidate_commit = committed.stdout.decode().strip()

        candidate_identity = {
            "head": candidate_commit,
            "tree": resolve_tree(self.repository, candidate_commit),
        }
        if (
            resolve_commit(self.repository, f"{candidate_commit}^")
            != candidate_before["head"]
        ):
            raise IdentityMismatch("off-ref candidate commit parent mismatch")
        if candidate_identity["tree"] != candidate_tree:
            raise IdentityMismatch("off-ref candidate commit/tree identity mismatch")
        cumulative_paths = self._authorize_candidate(candidate_commit)
        self._require_paths_allowed(
            iteration_paths,
            plan_patterns,
            "iteration plan",
        )
        if not set(iteration_paths).issubset(cumulative_paths):
            raise IdentityMismatch("candidate commit omitted Developer paths")

        with tempfile.TemporaryDirectory(
            prefix="candidate-install-", dir=self.store.root
        ) as install_directory:
            hooks_directory = Path(install_directory) / "empty-hooks"
            hooks_directory.mkdir()
            install_environment = sanitized_git_environment(home=install_directory)

            def run_install_git(*arguments: str):
                return subprocess.run(
                    git_command(
                        "-c",
                        f"core.hooksPath={hooks_directory}",
                        *arguments,
                    ),
                    cwd=self.repository,
                    env=install_environment,
                    check=False,
                    capture_output=True,
                )

            updated = run_install_git(
                "update-ref",
                "HEAD",
                candidate_commit,
                candidate_before["head"],
            )
            if updated.returncode:
                raise IdentityMismatch(
                    "candidate changed during atomic Developer import; "
                    "no ref was overwritten"
                )
        if head_identity(self.repository) != candidate_identity:
            raise IdentityMismatch(
                "candidate changed after atomic Developer import; "
                "no external ref or shared checkout was modified"
            )
        return candidate_identity, iteration_paths

    @staticmethod
    def _require_regular_git_modes(
        workspace: Path,
        before: str,
        after: str,
        paths: tuple[str, ...],
    ) -> None:
        for reference in (before, after):
            for path in paths:
                entry = subprocess.run(
                    git_command("ls-tree", "-z", reference, "--", path),
                    cwd=workspace,
                    env=sanitized_git_environment(),
                    check=False,
                    capture_output=True,
                )
                if entry.returncode:
                    raise PacketValidationError(
                        f"could not inspect Developer Git mode for {path}"
                    )
                if not entry.stdout:
                    continue
                header, separator, recorded_path = entry.stdout.rstrip(b"\0").partition(
                    b"\t"
                )
                fields = header.split()
                if (
                    not separator
                    or recorded_path.decode("utf-8", errors="strict") != path
                    or len(fields) != 3
                    or fields[0] not in {b"100644", b"100755"}
                    or fields[1] != b"blob"
                ):
                    raise ScopeViolation(
                        f"Developer result has unsupported Git mode: {path}"
                    )

    def _verify_evidence(self, packet: Mapping[str, Any], workspace: Path) -> None:
        """Execute only manifest-authorized evidence in the isolated projection."""

        assert self.state is not None
        self._require_candidate_ref("evidence replay")
        disclosed = {
            item["path"]
            for item in self.state["disclosures"]
            if item["role"] == Role.TESTER.value
            and item["iteration"] == self.state["iteration"]
        }
        for result in packet["results"]:
            requirement_id = result["requirement_id"]
            allowed_commands = {
                tuple(command)
                for command in self.requirements_manifest["verification_commands"][
                    requirement_id
                ]
            }
            for evidence in result["evidence"]:
                artifact = evidence["artifact"]
                if artifact not in disclosed:
                    raise PacketValidationError(
                        f"evidence artifact was not disclosed to Tester: {artifact}"
                    )
                path = workspace / artifact
                if path.is_symlink() or not path.is_file():
                    raise PacketValidationError(
                        f"evidence artifact is not a candidate file: {artifact}"
                    )
                if digest_file(path) != evidence["sha256"]:
                    raise PacketValidationError(
                        f"evidence artifact digest mismatch: {artifact}"
                    )
                command = tuple(evidence["command"])
                if command not in allowed_commands:
                    raise PacketValidationError(
                        f"evidence command is not authorized for {requirement_id}"
                    )
                if artifact not in command:
                    raise PacketValidationError(
                        f"evidence command does not name its artifact: {artifact}"
                    )
                try:
                    projection_before = head_identity(workspace)
                    completed = self._require_executor().execute_evidence(
                        EvidenceInvocation(
                            command=command,
                            workspace=workspace,
                        )
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise ExecutorUnavailable(
                        f"evidence command could not complete: {error}"
                    ) from error
                output_digest = hashlib.sha256(
                    completed.stdout + b"\0" + completed.stderr
                ).hexdigest()
                if completed.returncode != evidence["exit_code"]:
                    raise PacketValidationError(
                        f"evidence exit code mismatch for {requirement_id}"
                    )
                if output_digest != evidence["output_sha256"]:
                    raise PacketValidationError(
                        f"evidence output digest mismatch for {requirement_id}"
                    )
                if (
                    result["status"] == RequirementStatus.VERIFIED.value
                    and completed.returncode != 0
                ):
                    raise PacketValidationError(
                        f"VERIFIED requirement {requirement_id} has failing evidence"
                    )
                if head_identity(workspace) != projection_before:
                    raise PacketValidationError(
                        "evidence command mutated its projection"
                    )
                require_clean_worktree(workspace)
                self._require_candidate_ref("evidence replay")
        self._require_candidate_ref("evidence replay")

    def _require_common_packet(self, packet: Mapping[str, Any]) -> None:
        assert self.state is not None
        if packet["run_id"] != self.run_manifest["run_id"]:
            raise IdentityMismatch("role packet run_id mismatch")
        if packet["iteration"] != self.state["iteration"]:
            raise IdentityMismatch("role packet iteration mismatch")

    def _open_regression_ids(self) -> tuple[str, ...]:
        assert self.state is not None
        return tuple(
            sorted(
                {
                    item["requirement_id"]
                    for item in self.state["regressions"]
                    if item["resolved_iteration"] is None
                }
            )
        )

    def _validate_plan_paths(self, packet: Mapping[str, Any]) -> None:
        permitted = tuple(self.run_manifest["permitted_change_paths"])
        for action in packet["actions"]:
            self._require_paths_allowed(
                tuple(action["allowed_paths"]),
                permitted,
                f"action {action['requirement_id']}",
                patterns_as_paths=True,
            )

    @staticmethod
    def _require_paths_allowed(
        paths: tuple[str, ...],
        patterns: tuple[str, ...],
        label: str,
        *,
        patterns_as_paths: bool = False,
    ) -> None:
        if paths and not patterns:
            raise ScopeViolation(f"{label} permits no changed paths")
        for path in paths:
            if patterns_as_paths:
                contains_glob = any(character in path for character in "*?[")
                allowed = (
                    path in patterns if contains_glob else path_matches(path, patterns)
                )
            else:
                allowed = path_matches(path, patterns)
            if not allowed:
                raise ScopeViolation(f"{label} does not permit path {path}")
