"""Codex adapter, context boundary, state location, and authority-ceiling tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_pack.executors.hoh.codex import (
    REQUIRED_HELP_MARKERS,
    REQUIRED_SANDBOX_HELP_MARKERS,
    CodexExecAdapter,
)
from agent_pack.executors.hoh.context import ContextBroker, assert_payload_safe
from agent_pack.executors.hoh.executors import (
    ManualExecutor,
    RoleInvocation,
    ScriptedExecutor,
)
from agent_pack.executors.hoh.models import (
    ControllerPhase,
    ExecutorUnavailable,
    PacketValidationError,
    PauseRequested,
    Role,
    SandboxMode,
    ScopeViolation,
)
from agent_pack.executors.hoh.state_store import StateStore
from tests.cpu.hoh_support import make_repository, run_manifest


def test_codex_adapter_probes_and_uses_only_bounded_supported_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("synthetic executable\n", encoding="utf-8")
    executable.chmod(0o755)
    calls: list[tuple[list[str], dict]] = []

    def fake_run(command, **kwargs):
        command = [str(item) for item in command]
        calls.append((command, kwargs))
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "codex-cli 0.test\n", "")
        if command[-2:] == ["exec", "--help"]:
            return subprocess.CompletedProcess(
                command,
                0,
                "\n".join(REQUIRED_HELP_MARKERS),
                "",
            )
        if command[-2:] == ["sandbox", "--help"]:
            return subprocess.CompletedProcess(
                command,
                0,
                "\n".join(REQUIRED_SANDBOX_HELP_MARKERS),
                "",
            )
        if command[-2:] == ["features", "list"]:
            return subprocess.CompletedProcess(
                command, 0, "skip_host_skill_discovery under-development false\n", ""
            )
        if command[1] == "sandbox":
            target = Path(command[-1])
            if target.name == "outside-projection.txt":
                return subprocess.CompletedProcess(command, 1, "", "denied")
            if command[-2] == "/usr/bin/touch":
                if "carbon-hoh-write-v1" in command:
                    target.touch()
                    return subprocess.CompletedProcess(command, 0, "", "")
                return subprocess.CompletedProcess(command, 1, "", "denied")
            return subprocess.CompletedProcess(command, 0, "projection\n", "")
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ok":true}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, '{"ok":true}\n', "")

    monkeypatch.setattr("shutil.which", lambda _name: str(executable))
    monkeypatch.setattr("subprocess.run", fake_run)
    adapter = CodexExecAdapter(model="synthetic-model")
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object"}\n', encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    value = adapter.execute(
        RoleInvocation(
            role=Role.PLANNER,
            sandbox=SandboxMode.READ_ONLY,
            workspace=workspace,
            prompt="Return JSON.",
            output_schema=schema,
            context_paths=(),
            iteration=1,
        )
    )
    assert value == {"ok": True}
    command, kwargs = calls[-1]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--strict-config" in command
    assert "--sandbox" not in command
    assert command[command.index("--enable") + 1] == "skip_host_skill_discovery"
    assert 'approval_policy="never"' in command
    assert 'default_permissions="carbon-hoh-read-v1"' in command
    profile = next(item for item in command if item.startswith("permissions."))
    assert '":root"="deny"' in profile
    assert '":workspace_roots"={"."="read"}' in profile
    assert "network={enabled=false}" in profile
    assert "--output-schema" in command
    assert "danger-full-access" not in command
    assert "resume" not in command
    assert kwargs["cwd"] == workspace
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert set(kwargs["env"]) == {
        "CODEX_HOME",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONDONTWRITEBYTECODE",
        "TMPDIR",
    }
    assert kwargs["env"]["HOME"] == kwargs["env"]["TMPDIR"]


def test_codex_adapter_fails_closed_when_outside_sentinel_is_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("synthetic executable\n", encoding="utf-8")
    executable.chmod(0o755)

    def fake_run(command, **_kwargs):
        command = [str(item) for item in command]
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "codex-cli 0.test\n", "")
        if command[-2:] == ["exec", "--help"]:
            return subprocess.CompletedProcess(
                command, 0, "\n".join(REQUIRED_HELP_MARKERS), ""
            )
        if command[-2:] == ["sandbox", "--help"]:
            return subprocess.CompletedProcess(
                command, 0, "\n".join(REQUIRED_SANDBOX_HELP_MARKERS), ""
            )
        if command[-2:] == ["features", "list"]:
            return subprocess.CompletedProcess(
                command, 0, "skip_host_skill_discovery under-development false\n", ""
            )
        return subprocess.CompletedProcess(command, 0, "sentinel leaked\n", "")

    monkeypatch.setattr("shutil.which", lambda _name: str(executable))
    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(ExecutorUnavailable, match="projection-only"):
        CodexExecAdapter()


def test_manual_executor_pauses_human_without_claiming_success(tmp_path: Path) -> None:
    executor = ManualExecutor()
    with pytest.raises(PauseRequested) as captured:
        executor.execute(
            RoleInvocation(
                role=Role.TESTER,
                sandbox=SandboxMode.READ_ONLY,
                workspace=tmp_path,
                prompt="test",
                output_schema=tmp_path / "schema.json",
                context_paths=(),
                iteration=1,
            )
        )
    assert captured.value.phase is ControllerPhase.PAUSED_HUMAN


def test_manual_executor_consumes_one_external_packet(tmp_path: Path) -> None:
    packet = {"externally_reviewed": True}
    executor = ManualExecutor(packet=packet)
    invocation = RoleInvocation(
        role=Role.PLANNER,
        sandbox=SandboxMode.READ_ONLY,
        workspace=tmp_path,
        prompt="test",
        output_schema=tmp_path / "schema.json",
        context_paths=(),
        iteration=1,
    )
    assert executor.execute(invocation) == packet
    with pytest.raises(PauseRequested):
        executor.execute(invocation)


def test_protected_context_request_is_rejected_and_not_disclosed(
    tmp_path: Path,
) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    manifest["context_allow_paths"]["planner"] = ["**"]
    broker = ContextBroker(repository, tmp_path / "state", manifest)
    with pytest.raises(ScopeViolation, match="protected"):
        broker.grant(
            Role.PLANNER,
            ["private_validator/official_cases/seed.txt"],
            iteration=1,
        )


def test_secret_values_and_protected_paths_cannot_be_persisted() -> None:
    patterns = ["**/hidden_evaluation/**"]
    with pytest.raises(PacketValidationError, match="protected value key"):
        assert_payload_safe({"OPENAI_API_KEY": "not-allowed"}, patterns)
    with pytest.raises(PacketValidationError, match="protected path"):
        assert_payload_safe({"path": "data/hidden_evaluation/case.json"}, patterns)
    with pytest.raises(PacketValidationError, match="protected path"):
        assert_payload_safe(
            {"summary": "Observed data/hidden_evaluation/case.json in the worktree."},
            patterns,
        )
    with pytest.raises(PacketValidationError, match="protected path"):
        assert_payload_safe(
            {"summary": "Observed hidden_evaluation/case.json in the worktree."},
            patterns,
        )


def test_root_level_protected_context_is_rejected(tmp_path: Path) -> None:
    repository, requirements = make_repository(tmp_path)
    protected = repository / "hidden_evaluation" / "case.json"
    protected.parent.mkdir()
    protected.write_text("protected\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "hidden_evaluation/case.json"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--quiet", "--message", "root protected fixture"],
        cwd=repository,
        check=True,
    )
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    manifest["context_allow_paths"]["planner"] = ["**"]
    broker = ContextBroker(repository, tmp_path / "state", manifest)
    with pytest.raises(ScopeViolation, match="protected"):
        broker.grant(Role.PLANNER, ["hidden_evaluation/case.json"], iteration=1)


def test_default_state_store_is_under_git_common_directory(tmp_path: Path) -> None:
    repository, _ = make_repository(tmp_path)
    store = StateStore.for_repository(repository, "bounded-run")
    common = Path(
        subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve()
    assert store.root == common / ".carbon-hoh" / "runs" / "bounded-run"


def test_run_manifest_explicitly_denies_final_authorities(tmp_path: Path) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    denied = set(manifest["authority_ceiling"])
    assert denied == {
        "APPROVED_FOR_MERGE",
        "LIVE_AUTHORIZED",
        "MERGE_AUTHORIZED",
        "PRODUCTION_QUALIFIED",
        "SCIENTIFICALLY_QUALIFIED",
        "SECURITY_QUALIFIED",
    }
    serialized = json.dumps(manifest)
    assert "production credential" not in serialized.lower()


def test_run_manifest_cannot_remove_mandatory_protected_patterns(
    tmp_path: Path,
) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    manifest["protected_patterns"] = []
    from agent_pack.executors.hoh.validation import validate_run_manifest

    with pytest.raises(PacketValidationError, match="mandatory default"):
        validate_run_manifest(manifest)
