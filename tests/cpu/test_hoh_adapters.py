"""Codex adapter, context boundary, state location, and authority-ceiling tests."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from agent_pack.executors.hoh import cli
from agent_pack.executors.hoh.codex import (
    REQUIRED_HELP_MARKERS,
    REQUIRED_SANDBOX_HELP_MARKERS,
    TRUSTED_EXECUTION_PATH,
    CodexExecAdapter,
)
from agent_pack.executors.hoh.context import ContextBroker, assert_payload_safe
from agent_pack.executors.hoh.executors import (
    EvidenceInvocation,
    ManualExecutor,
    RoleInvocation,
    ScriptedExecutor,
)
from agent_pack.executors.hoh.identity import head_identity
from agent_pack.executors.hoh.models import (
    ControllerPhase,
    ExecutorUnavailable,
    IdentityMismatch,
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
        if command[1] == "exec" and "--output-schema" not in command:
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text("READY\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command, 0, "READY\n", "sandbox: custom permissions\n"
            )
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ok":true}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, '{"ok":true}\n', "")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("PATH", f".:{tmp_path}")
    adapter = CodexExecAdapter(executable=executable, model="synthetic-model")
    assert all(kwargs["timeout"] == 15 for _command, kwargs in calls[:4])
    assert all(
        kwargs["env"]["PATH"] == TRUSTED_EXECUTION_PATH
        for _command, kwargs in calls[:4]
    )
    exec_preflights = [
        command
        for command, _kwargs in calls
        if len(command) > 1
        and command[1] == "exec"
        and "--output-last-message" in command
        and "--output-schema" not in command
    ]
    assert len(exec_preflights) == 2
    assert 'default_permissions="carbon-hoh-read-v1"' in exec_preflights[0]
    assert 'default_permissions="carbon-hoh-write-v1"' in exec_preflights[1]
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
        "GIT_ATTR_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_NO_REPLACE_OBJECTS",
        "GIT_TERMINAL_PROMPT",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONDONTWRITEBYTECODE",
        "TMPDIR",
    }
    assert kwargs["env"]["HOME"] == kwargs["env"]["TMPDIR"]
    assert kwargs["env"]["PATH"] == TRUSTED_EXECUTION_PATH
    profile_digest = adapter.profile_digest(Role.TESTER)

    monkeypatch.setenv("PATH", str(tmp_path / "changed-after-start"))
    assert adapter.profile_digest(Role.TESTER) == profile_digest
    evidence = adapter.execute_evidence(
        EvidenceInvocation(command=("/bin/cat", "visible.txt"), workspace=workspace)
    )
    assert evidence.returncode == 0
    evidence_command, evidence_kwargs = calls[-1]
    assert evidence_command[1] == "sandbox"
    assert "carbon-hoh-read-v1" in evidence_command
    assert "--include-managed-config" in evidence_command
    assert evidence_kwargs["cwd"] == workspace
    assert evidence_kwargs["env"]["GIT_ATTR_NOSYSTEM"] == "1"
    assert evidence_kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert evidence_kwargs["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert evidence_kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert evidence_kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert evidence_kwargs["env"]["HOME"] == evidence_kwargs["env"]["CODEX_HOME"]
    assert evidence_kwargs["env"]["PATH"] == TRUSTED_EXECUTION_PATH

    sentinel = tmp_path / "outside-projection.txt"
    sentinel.write_text("protected canary\n", encoding="utf-8")
    denied_evidence = adapter.execute_evidence(
        EvidenceInvocation(
            command=("/bin/cat", str(sentinel)),
            workspace=workspace,
        )
    )
    assert denied_evidence.returncode != 0
    denied_command, _ = calls[-1]
    assert denied_command[1] == "sandbox"
    assert "carbon-hoh-read-v1" in denied_command

    second_executable = tmp_path / "codex-second"
    second_executable.write_text("synthetic executable\n", encoding="utf-8")
    second_executable.chmod(0o755)
    second_adapter = CodexExecAdapter(
        executable=second_executable,
        model="synthetic-model",
    )
    assert second_adapter.profile_digest(Role.TESTER) != profile_digest

    executable.write_text("replaced executable\n", encoding="utf-8")
    executable.chmod(0o755)
    with pytest.raises(ExecutorUnavailable, match="identity changed"):
        adapter.execute_evidence(
            EvidenceInvocation(command=("/bin/cat", "visible.txt"), workspace=workspace)
        )
    assert adapter.profile_digest(Role.TESTER) == profile_digest


def test_codex_role_environment_ignores_ambient_path_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", f".:{tmp_path / 'hostile'}")
    first = CodexExecAdapter._role_environment(tmp_path / "first")
    monkeypatch.setenv("PATH", str(tmp_path / "changed"))
    second = CodexExecAdapter._role_environment(tmp_path / "second")

    assert first["PATH"] == TRUSTED_EXECUTION_PATH
    assert second["PATH"] == TRUSTED_EXECUTION_PATH


def test_codex_adapter_never_resolves_its_binary_through_hostile_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = tmp_path / "counterfeit-ran"
    counterfeit = tmp_path / "codex"
    counterfeit.write_text(
        f"#!/bin/sh\n/usr/bin/touch {sentinel}\n",
        encoding="utf-8",
    )
    counterfeit.chmod(0o755)
    monkeypatch.setenv("PATH", f".:{tmp_path}:/usr/bin:/bin")

    with pytest.raises(ExecutorUnavailable, match="exact absolute path"):
        CodexExecAdapter()

    assert not sentinel.exists()


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

    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(ExecutorUnavailable, match="projection-only"):
        CodexExecAdapter(executable=executable)


def test_codex_adapter_bounds_and_wraps_initial_cli_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("synthetic executable\n", encoding="utf-8")
    executable.chmod(0o755)

    def timeout(command, **kwargs):
        assert kwargs["timeout"] == 3
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("subprocess.run", timeout)
    with pytest.raises(ExecutorUnavailable, match="isolation probe failed"):
        CodexExecAdapter(executable=executable, timeout_seconds=3)


def test_codex_adapter_fails_closed_when_exec_selects_legacy_sandbox(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("synthetic executable\n", encoding="utf-8")
    executable.chmod(0o755)
    conflicting_home = tmp_path / "conflicting-codex-home"
    conflicting_home.mkdir()
    (conflicting_home / "config.toml").write_text(
        'sandbox_mode = "danger-full-access"\n', encoding="utf-8"
    )

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
        if command[1] == "sandbox":
            target = Path(command[-1])
            if target.name == "outside-projection.txt":
                return subprocess.CompletedProcess(command, 1, b"", b"denied")
            if command[-2] == "/usr/bin/touch":
                if "carbon-hoh-write-v1" in command:
                    target.touch()
                    return subprocess.CompletedProcess(command, 0, b"", b"")
                return subprocess.CompletedProcess(command, 1, b"", b"denied")
            return subprocess.CompletedProcess(command, 0, b"projection\n", b"")
        assert "--ignore-user-config" in command
        assert _kwargs["env"]["CODEX_HOME"] == str(conflicting_home)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text("READY\n", encoding="utf-8")
        diagnostic = (
            "sandbox: custom permissions\n"
            if any("carbon-hoh-read-v1" in item for item in command)
            else "sandbox: workspace-write\n"
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "sandbox: custom permissions\nREADY\n",
            diagnostic,
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("CODEX_HOME", str(conflicting_home))
    with pytest.raises(
        ExecutorUnavailable, match="workspace-write profile did not complete"
    ):
        CodexExecAdapter(executable=executable)


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


def test_cli_persists_lazy_codex_preflight_failure_and_status_still_works(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, requirements = make_repository(tmp_path)
    bound = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, bound)
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = tmp_path / "run-state"
    executable = tmp_path / "exact-codex"

    common = [
        str(manifest_path),
        "--state-dir",
        str(store),
        "--codex-executable",
        str(executable),
    ]
    assert cli.main(["init", *common]) == 0

    def unavailable(**_kwargs):
        raise ExecutorUnavailable("synthetic Codex preflight unavailable")

    monkeypatch.setattr(cli, "CodexExecAdapter", unavailable)
    assert cli.main(["step", *common]) == 0
    paused = StateStore(store).load_state()
    assert paused["phase"] == "PAUSED_INFRA"
    assert paused["paused_from"] == "PLANNING"
    assert "synthetic Codex preflight unavailable" in paused["last_error"]
    assert cli.main(["status", str(manifest_path), "--state-dir", str(store)]) == 0


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
            candidate=head_identity(repository),
        )


def test_projection_commit_ignores_ambient_git_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, requirements = make_repository(tmp_path)
    hooks = tmp_path / "ambient-hooks"
    hooks.mkdir()
    sentinel = tmp_path / "hook-ran"
    hook = hooks / "pre-commit"
    hook.write_text(f"#!/bin/sh\n/usr/bin/touch {sentinel}\n", encoding="utf-8")
    hook.chmod(0o755)
    template = tmp_path / "ambient-template"
    template.mkdir()
    (template / "injected-template-file").write_text("ambient\n", encoding="utf-8")
    (repository / ".gitattributes").write_text(
        "src.txt filter=ambient\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", ".gitattributes"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "--message", "attributes fixture"],
        cwd=repository,
        check=True,
    )
    global_config = tmp_path / "global-git-config"
    global_config.write_text(
        f"[core]\n\thooksPath = {hooks}\n"
        f"[init]\n\ttemplateDir = {template}\n"
        f'[filter "ambient"]\n\tclean = /usr/bin/touch {sentinel}\n'
        f"\tsmudge = /usr/bin/touch {sentinel}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    broker = ContextBroker(repository, tmp_path / "state", manifest)

    broker.projection(
        Role.PLANNER,
        1,
        (".gitattributes", "src.txt", "ticket.md"),
        head_identity(repository),
    )

    assert not sentinel.exists()
    assert not (
        broker.state_root / "projections/1/planner/.git/injected-template-file"
    ).exists()


def test_projection_materializes_exact_candidate_blobs_not_live_worktree(
    tmp_path: Path,
) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    candidate = head_identity(repository)
    (repository / "src.txt").write_text("uncommitted verifier swap\n", encoding="utf-8")
    broker = ContextBroker(repository, tmp_path / "state", manifest)

    projection = broker.projection(
        Role.TESTER,
        1,
        ("src.txt", "verify.py"),
        candidate,
    )

    assert (projection / "src.txt").read_text(encoding="utf-8") == "base\n"
    assert (repository / "src.txt").read_text(encoding="utf-8") == (
        "uncommitted verifier swap\n"
    )


def test_read_only_projection_preserves_executable_git_mode(tmp_path: Path) -> None:
    repository, requirements = make_repository(tmp_path)
    verifier = repository / "executable-verifier.sh"
    verifier.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    verifier.chmod(0o755)
    subprocess.run(["git", "add", "executable-verifier.sh"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "--message", "executable fixture"],
        cwd=repository,
        check=True,
    )
    manifest = run_manifest(repository, requirements, ScriptedExecutor({}))
    broker = ContextBroker(repository, tmp_path / "state", manifest)

    projection = broker.projection(
        Role.TESTER,
        1,
        ("executable-verifier.sh",),
        head_identity(repository),
    )

    assert stat.S_IMODE((projection / "executable-verifier.sh").stat().st_mode) == 0o500
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=projection,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    executed = subprocess.run(["./executable-verifier.sh"], cwd=projection, check=False)
    assert executed.returncode == 0


def test_projection_rejects_symlinked_managed_parent_without_touching_target(
    tmp_path: Path,
) -> None:
    repository, requirements = make_repository(tmp_path)
    manifest = run_manifest(repository, requirements, ScriptedExecutor({}))
    broker = ContextBroker(repository, tmp_path / "state", manifest)
    outside = tmp_path / "outside-projections"
    outside.mkdir(mode=0o750)
    canary = outside / "canary.txt"
    canary.write_text("unchanged\n", encoding="utf-8")
    (broker.state_root / "projections").symlink_to(outside)

    with pytest.raises(ScopeViolation, match="state directory is unsafe"):
        broker.projection(
            Role.TESTER,
            1,
            ("src.txt",),
            head_identity(repository),
        )

    assert canary.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o750


def test_developer_seal_rejects_symlink_swap_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    broker = ContextBroker(repository, tmp_path / "state", manifest)
    workspace = broker.projection(
        Role.DEVELOPER,
        1,
        ("src.txt",),
        head_identity(repository),
    )
    outside = tmp_path / "outside-target"
    outside.write_text("must survive\n", encoding="utf-8")
    outside.chmod(0o640)
    original_open = os.open
    swapped = False

    def swap_before_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if (
            path == "src.txt"
            and dir_fd is not None
            and flags & os.O_DIRECTORY == 0
            and flags & os.O_ACCMODE == os.O_RDONLY
            and not swapped
        ):
            swapped = True
            (workspace / "src.txt").unlink()
            (workspace / "src.txt").symlink_to(outside)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_before_open)
    with pytest.raises(ScopeViolation, match="safely seal Developer entry"):
        broker.seal_developer_projection(workspace, 1)

    assert swapped
    assert outside.read_text(encoding="utf-8") == "must survive\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o640


def test_projection_cleanup_never_follows_role_created_symlinks(
    tmp_path: Path,
) -> None:
    repository, requirements = make_repository(tmp_path)
    executor = ScriptedExecutor({})
    manifest = run_manifest(repository, requirements, executor)
    broker = ContextBroker(repository, tmp_path / "state", manifest)
    candidate = head_identity(repository)
    projection = broker.projection(
        Role.DEVELOPER,
        1,
        ("ticket.md",),
        candidate,
    )
    outside_file = tmp_path / "outside-file"
    outside_file.write_text("unchanged\n", encoding="utf-8")
    outside_file.chmod(0o640)
    outside_directory = tmp_path / "outside-directory"
    outside_directory.mkdir(mode=0o750)
    (projection / "file-link").symlink_to(outside_file)
    (projection / "directory-link").symlink_to(outside_directory)

    broker.projection(Role.DEVELOPER, 1, ("ticket.md",), candidate)

    assert outside_file.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside_file.stat().st_mode) == 0o640
    assert stat.S_IMODE(outside_directory.stat().st_mode) == 0o750


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
        broker.grant(
            Role.PLANNER,
            ["hidden_evaluation/case.json"],
            iteration=1,
            candidate=head_identity(repository),
        )


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


def test_state_store_rejects_symlinked_root_without_touching_target(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside-root"
    outside.mkdir(mode=0o750)
    canary = outside / "canary.txt"
    canary.write_text("unchanged\n", encoding="utf-8")
    linked_root = tmp_path / "linked-state"
    linked_root.symlink_to(outside)

    with pytest.raises(IdentityMismatch, match="external state root is unsafe"):
        StateStore(linked_root)

    assert canary.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o750


def test_state_store_rejects_broad_existing_root_without_chmod(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing-state"
    existing.mkdir(mode=0o750)

    with pytest.raises(IdentityMismatch, match="not private mode-0700"):
        StateStore(existing)

    assert stat.S_IMODE(existing.stat().st_mode) == 0o750


def test_state_store_rejects_symlink_lock_without_touching_target(
    tmp_path: Path,
) -> None:
    store = StateStore(tmp_path / "state")
    outside = tmp_path / "outside-lock"
    outside.write_text("unchanged\n", encoding="utf-8")
    outside.chmod(0o640)
    store.lock_path.symlink_to(outside)

    with (
        pytest.raises(IdentityMismatch, match="controller lock is unsafe"),
        store.locked(),
    ):
        pass

    assert outside.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o640


def test_state_store_detects_temp_replacement_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = StateStore(tmp_path / "state")
    outside = tmp_path / "outside-state"
    outside.write_text("unchanged\n", encoding="utf-8")
    outside.chmod(0o640)
    original_replace = os.replace

    def replace_temp_with_symlink(
        source,
        destination,
        *,
        src_dir_fd=None,
        dst_dir_fd=None,
    ):
        os.unlink(source, dir_fd=src_dir_fd)
        os.symlink(outside, source, dir_fd=src_dir_fd)
        return original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "replace", replace_temp_with_symlink)
    with pytest.raises(IdentityMismatch, match="installed state file identity changed"):
        store.save_pending_install({"synthetic": True})

    assert outside.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o640


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
