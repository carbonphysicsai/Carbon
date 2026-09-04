"""Deterministic identity-bound Planner/Developer/Tester outer loop."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .context import ContextBroker, assert_payload_safe
from .executors import Executor, RoleInvocation
from .identity import (
    changed_paths,
    digest_file,
    digest_value,
    git_blob,
    head_identity,
    require_clean_worktree,
    resolve_commit,
    resolve_repository_root,
    resolve_tree,
)
from .models import (
    SCHEMA_VERSION,
    ControllerPhase,
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
        executor: Executor,
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
        self.context = ContextBroker(
            self.repository,
            self.store.root,
            self.run_manifest,
        )
        self.state: dict[str, Any] | None = None

    @property
    def schemas_root(self) -> Path:
        return Path(__file__).resolve().parent / "schemas"

    @property
    def prompts_root(self) -> Path:
        return Path(__file__).resolve().parent / "prompts"

    def initialize(self) -> dict[str, Any]:
        self._verify_static_identities()
        self._verify_executor_profiles()
        require_clean_worktree(self.repository)
        candidate = head_identity(self.repository)
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_manifest["run_id"],
            "run_manifest_digest": self.manifest_digest,
            "phase": ControllerPhase.PLANNING.value,
            "iteration": 1,
            "candidate": {
                **candidate,
                "changed_paths": list(
                    changed_paths(
                        self.repository,
                        self.run_manifest["authority"]["commit"],
                        candidate["head"],
                    )
                ),
            },
            "requirements": [
                {
                    "id": requirement_id,
                    "status": RequirementStatus.UNTESTED.value,
                    "accepted_evidence": [],
                }
                for requirement_id in sorted(self.requirement_ids)
            ],
            "regressions": [],
            "disclosures": [],
            "plan_digests": [],
            "evidence_digests": [],
            "active_plan": None,
            "last_error": None,
        }
        validate_controller_state(state, self.requirement_ids)
        assert_payload_safe(state, self.run_manifest["protected_patterns"])
        self.store.initialize(self.run_manifest, state)
        self.state = state
        return self.snapshot()

    def resume(self) -> dict[str, Any]:
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
        self._verify_executor_profiles()
        self._verify_candidate_identity()
        assert_payload_safe(state, self.run_manifest["protected_patterns"])
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        if self.state is None:
            raise IdentityMismatch("controller is not initialized or resumed")
        return json.loads(json.dumps(self.state))

    def step(self) -> dict[str, Any]:
        if self.state is None:
            raise IdentityMismatch("controller is not initialized or resumed")
        try:
            self._verify_static_identities()
            self._verify_executor_profiles()
            self._verify_candidate_identity()
            phase = ControllerPhase(self.state["phase"])
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
            self.state["last_error"] = None
        except PauseRequested as error:
            self.state["phase"] = error.phase.value
            self.state["last_error"] = error.reason
        except HarnessError as error:
            self.state["last_error"] = f"{type(error).__name__}: {error}"
            self._persist()
            raise
        self._persist()
        return self.snapshot()

    def _persist(self) -> None:
        assert self.state is not None
        validate_controller_state(self.state, self.requirement_ids)
        assert_payload_safe(self.state, self.run_manifest["protected_patterns"])
        self.store.save_state(self.state)

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
        ticket_path = self.repository / ticket_binding["path"]
        if digest_file(ticket_path) != ticket_binding["sha256"]:
            raise IdentityMismatch("ticket content digest mismatch")
        requirements_binding = self.run_manifest["requirements"]
        requirements_path = self.repository / requirements_binding["path"]
        if digest_file(requirements_path) != requirements_binding["sha256"]:
            raise IdentityMismatch("requirements manifest digest mismatch")
        try:
            bound_requirements = validate_requirements_manifest(
                json.loads(requirements_path.read_text(encoding="utf-8"))
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
        current_blob = git_blob(self.repository, "HEAD", ticket["path"])
        if current_blob != ticket["git_blob"]:
            raise IdentityMismatch("requirements manifest ticket Git blob mismatch")

    def _verify_executor_profiles(self) -> None:
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

    def _verify_candidate_identity(self) -> None:
        assert self.state is not None
        actual = head_identity(self.repository)
        expected = self.state["candidate"]
        if actual["head"] != expected["head"] or actual["tree"] != expected["tree"]:
            raise IdentityMismatch(
                "candidate head/tree mismatch; refusing to resume or advance"
            )
        require_clean_worktree(self.repository)

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
            "disclosed_paths": list(context_paths),
            "authority_ceiling": self.run_manifest["authority_ceiling"],
            "active_plan": self.state["active_plan"],
        }
        assert_payload_safe(packet, self.run_manifest["protected_patterns"])
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
            planned = list(self.context.matching_tracked(patterns))
        context_paths, disclosures = self.context.grant(
            role,
            [*initial, *previous, *planned],
            iteration=self.state["iteration"],
        )
        self._append_disclosures(disclosures)
        before = head_identity(self.repository)
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
                before,
            )
            workspace_before = head_identity(workspace)
            invocation = RoleInvocation(
                role=role,
                sandbox=sandbox,
                workspace=workspace,
                prompt=self._role_prompt(role, context_paths),
                output_schema=self.schemas_root / schema_name,
                context_paths=context_paths,
                iteration=self.state["iteration"],
            )
            raw = dict(self.executor.execute(invocation))
            assert_payload_safe(raw, self.run_manifest["protected_patterns"])
            packet = validator(raw)
            requests = tuple(packet["context_requests"])
            if not requests:
                break
            newly_granted, new_disclosures = self.context.grant(
                role,
                requests,
                iteration=self.state["iteration"],
            )
            self._append_disclosures(new_disclosures)
            context_paths = tuple(sorted(set(context_paths) | set(newly_granted)))
        else:
            raise ScopeViolation(f"{role.value} exceeded the context-request limit")
        if role is not Role.DEVELOPER:
            if head_identity(workspace) != workspace_before:
                raise ScopeViolation(f"{role.value} mutated its read-only projection")
            require_clean_worktree(workspace)
            after = head_identity(self.repository)
            if after != before:
                raise ScopeViolation(f"{role.value} mutated the candidate")
            require_clean_worktree(self.repository)
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
            self.state["last_error"] = blocker["reason"]
            return
        self._validate_plan_paths(packet)
        self.state["active_plan"] = packet
        self.state["plan_digests"].append(digest_value(packet))
        self.state["phase"] = ControllerPhase.DEVELOPING.value

    def _develop(self) -> None:
        assert self.state is not None
        before = head_identity(self.repository)
        packet, workspace, workspace_before = self._invoke(
            Role.DEVELOPER,
            "developer_result.schema.json",
            validate_developer_result,
        )
        self._require_common_packet(packet)
        self._require_bindings(packet["bindings"], Role.DEVELOPER)
        require_clean_worktree(self.repository)
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
        self._require_paths_allowed(
            cumulative_paths,
            tuple(self.run_manifest["permitted_change_paths"]),
            "run manifest",
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
                }
            )
        self.state["requirements"] = next_states
        self.state["evidence_digests"].append(digest_value(packet))
        self.state["active_plan"] = None
        statuses = {RequirementStatus(item["status"]) for item in next_states}
        if RequirementStatus.BLOCKED_HUMAN in statuses:
            self.state["phase"] = ControllerPhase.PAUSED_HUMAN.value
        elif RequirementStatus.BLOCKED_INFRA in statuses:
            self.state["phase"] = ControllerPhase.PAUSED_INFRA.value
        elif all(
            RequirementStatus(item["status"])
            in {RequirementStatus.VERIFIED, RequirementStatus.OUT_OF_SCOPE}
            for item in next_states
        ):
            self.state["phase"] = ControllerPhase.FINAL_CANDIDATE_READY.value
        elif self.state["iteration"] >= self.run_manifest["max_iterations"]:
            self.state["phase"] = ControllerPhase.PAUSED_INFRA.value
            self.state["last_error"] = "bounded iteration limit reached"
        else:
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
            if any(
                fnmatch.fnmatchcase(path, pattern)
                for pattern in self.run_manifest["protected_patterns"]
            ):
                raise ScopeViolation(f"Developer changed protected path {path}")
            projected_path = workspace / path
            if projected_path.exists() and (
                projected_path.is_symlink() or not projected_path.is_file()
            ):
                raise ScopeViolation(f"Developer result is not a regular file: {path}")
        require_clean_worktree(self.repository)
        if head_identity(self.repository) != dict(candidate_before):
            raise IdentityMismatch("candidate changed during Developer invocation")
        diff = subprocess.run(
            [
                "git",
                "diff",
                "--binary",
                "--full-index",
                workspace_before["head"],
                projected_after["head"],
                "--",
            ],
            cwd=workspace,
            check=False,
            capture_output=True,
        )
        if diff.returncode or not diff.stdout:
            raise PacketValidationError("Developer commit has no importable patch")
        for arguments in (("--check", "--index"), ("--index",)):
            applied = subprocess.run(
                ["git", "apply", "--binary", *arguments],
                cwd=self.repository,
                input=diff.stdout,
                check=False,
                capture_output=True,
            )
            if applied.returncode:
                detail = (applied.stderr or applied.stdout).decode(
                    "utf-8", errors="replace"
                )
                raise PacketValidationError(
                    f"Developer patch import failed closed: {detail.strip()}"
                )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB"],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
        )
        staged_paths = tuple(
            sorted(line for line in staged.stdout.splitlines() if line)
        )
        if staged.returncode or staged_paths != tuple(sorted(iteration_paths)):
            raise PacketValidationError(
                "imported Developer paths do not match projection"
            )
        committed = subprocess.run(
            [
                "git",
                "-c",
                "user.name=Carbon HoH Controller",
                "-c",
                "user.email=carbon-hoh@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--quiet",
                "--message",
                f"Carbon HoH iteration {self.state['iteration']}",
            ],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
        )
        if committed.returncode:
            raise PacketValidationError(
                "controller could not commit imported Developer patch: "
                f"{(committed.stderr or committed.stdout).strip()}"
            )
        require_clean_worktree(self.repository)
        return head_identity(self.repository), iteration_paths

    def _verify_evidence(self, packet: Mapping[str, Any], workspace: Path) -> None:
        """Execute only manifest-authorized evidence in the isolated projection."""

        assert self.state is not None
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
                environment_root = self.store.root / "command-environment"
                home = environment_root / "home"
                temporary = environment_root / "tmp"
                home.mkdir(parents=True, exist_ok=True)
                temporary.mkdir(parents=True, exist_ok=True)
                environment = {
                    "HOME": str(home),
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "TMPDIR": str(temporary),
                }
                try:
                    projection_before = head_identity(workspace)
                    completed = subprocess.run(
                        command,
                        cwd=workspace,
                        check=False,
                        capture_output=True,
                        env=environment,
                        timeout=300,
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise PacketValidationError(
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
                    path in patterns
                    if contains_glob
                    else any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
                )
            else:
                allowed = any(
                    fnmatch.fnmatchcase(path, pattern) for pattern in patterns
                )
            if not allowed:
                raise ScopeViolation(f"{label} does not permit path {path}")
