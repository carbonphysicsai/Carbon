"""Supported `codex exec` adapter for independent structured role invocations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .executors import RoleInvocation
from .identity import digest_value
from .models import ExecutorUnavailable, Role, SandboxMode

REQUIRED_HELP_MARKERS = (
    "--config <key=value>",
    "--enable <FEATURE>",
    "--cd <DIR>",
    "--ephemeral",
    "--ignore-user-config",
    "--strict-config",
    "--output-schema <FILE>",
    "--output-last-message <FILE>",
)

REQUIRED_SANDBOX_HELP_MARKERS = (
    "--config <key=value>",
    "--permission-profile <NAME>",
    "--cd <DIR>",
    "--include-managed-config",
)

READ_PROFILE = "carbon-hoh-read-v1"
WRITE_PROFILE = "carbon-hoh-write-v1"
ISOLATION_PROFILE_VERSION = "1"


class CodexExecAdapter:
    """Start a fresh ephemeral Codex thread for every role invocation."""

    def __init__(
        self,
        *,
        executable: str = "codex",
        model: str | None = None,
        timeout_seconds: int = 1800,
    ) -> None:
        resolved = shutil.which(executable)
        if resolved is None:
            raise ExecutorUnavailable(f"Codex executable is unavailable: {executable}")
        self.executable = str(Path(resolved).resolve())
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.version, self.help_text, self.sandbox_help_text = self._probe()
        try:
            self._probe_permission_profiles()
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ExecutorUnavailable(
                f"installed Codex CLI isolation probe failed: {error}"
            ) from error

    def _probe(self) -> tuple[str, str, str]:
        version = subprocess.run(
            [self.executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        help_result = subprocess.run(
            [self.executable, "exec", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        sandbox_help_result = subprocess.run(
            [self.executable, "sandbox", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        features_result = subprocess.run(
            [self.executable, "features", "list"],
            check=False,
            capture_output=True,
            text=True,
        )
        if (
            version.returncode
            or help_result.returncode
            or sandbox_help_result.returncode
            or features_result.returncode
        ):
            raise ExecutorUnavailable("installed Codex CLI probe failed")
        version_text = version.stdout.strip()
        help_text = help_result.stdout
        if not version_text.startswith("codex-cli "):
            raise ExecutorUnavailable(
                f"unexpected Codex version output: {version_text!r}"
            )
        missing = [
            marker for marker in REQUIRED_HELP_MARKERS if marker not in help_text
        ]
        if missing:
            raise ExecutorUnavailable(
                f"installed Codex exec surface lacks required flags: {missing}"
            )
        sandbox_help_text = sandbox_help_result.stdout
        missing = [
            marker
            for marker in REQUIRED_SANDBOX_HELP_MARKERS
            if marker not in sandbox_help_text
        ]
        if missing:
            raise ExecutorUnavailable(
                f"installed Codex sandbox surface lacks required flags: {missing}"
            )
        if "skip_host_skill_discovery" not in features_result.stdout:
            raise ExecutorUnavailable(
                "installed Codex CLI cannot disable host skill discovery"
            )
        return version_text, help_text, sandbox_help_text

    @staticmethod
    def _profile_name(sandbox: SandboxMode) -> str:
        if sandbox is SandboxMode.READ_ONLY:
            return READ_PROFILE
        if sandbox is SandboxMode.WORKSPACE_WRITE:
            return WRITE_PROFILE
        raise ExecutorUnavailable(f"unsupported Codex sandbox mode: {sandbox}")

    @classmethod
    def _profile_arguments(
        cls,
        sandbox: SandboxMode,
        runtime_directory: Path,
    ) -> list[str]:
        profile = cls._profile_name(sandbox)
        workspace_access = "read" if sandbox is SandboxMode.READ_ONLY else "write"
        runtime_path = json.dumps(str(runtime_directory.resolve()))
        policy = (
            '{filesystem={":root"="deny",":minimal"="read",'
            '":tmpdir"="deny",":slash_tmp"="deny",'
            f'":workspace_roots"={{"."="{workspace_access}"}},'
            f'{runtime_path}="write"}},network={{enabled=false}}}}'
        )
        return [
            "--config",
            f"default_permissions={json.dumps(profile)}",
            "--config",
            f"permissions.{profile}={policy}",
        ]

    def _sandbox_probe(
        self,
        *,
        sandbox: SandboxMode,
        workspace: Path,
        runtime_directory: Path,
        codex_home: Path,
        command: list[str],
    ) -> subprocess.CompletedProcess[str]:
        profile = self._profile_name(sandbox)
        return subprocess.run(
            [
                self.executable,
                "sandbox",
                *self._profile_arguments(sandbox, runtime_directory),
                "--permission-profile",
                profile,
                "--cd",
                str(workspace),
                "--include-managed-config",
                *command,
            ],
            cwd=workspace,
            env={
                "CODEX_HOME": str(codex_home),
                "HOME": str(codex_home),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "TMPDIR": str(runtime_directory),
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=min(self.timeout_seconds, 30),
        )

    def _probe_permission_profiles(self) -> None:
        """Prove the CLI enforces projection-only reads before it may run a role."""
        with tempfile.TemporaryDirectory(prefix="carbon-hoh-isolation-probe-") as root:
            probe_root = Path(root)
            workspace = probe_root / "projection"
            runtime_directory = probe_root / "runtime"
            codex_home = probe_root / "codex-home"
            workspace.mkdir()
            runtime_directory.mkdir()
            codex_home.mkdir()
            visible = workspace / "visible.txt"
            sentinel = probe_root / "outside-projection.txt"
            visible.write_text("projection\n", encoding="utf-8")
            sentinel.write_text("must remain unreadable\n", encoding="utf-8")

            readable = self._sandbox_probe(
                sandbox=SandboxMode.READ_ONLY,
                workspace=workspace,
                runtime_directory=runtime_directory,
                codex_home=codex_home,
                command=["/bin/cat", str(visible)],
            )
            denied = self._sandbox_probe(
                sandbox=SandboxMode.READ_ONLY,
                workspace=workspace,
                runtime_directory=runtime_directory,
                codex_home=codex_home,
                command=["/bin/cat", str(sentinel)],
            )
            read_only = self._sandbox_probe(
                sandbox=SandboxMode.READ_ONLY,
                workspace=workspace,
                runtime_directory=runtime_directory,
                codex_home=codex_home,
                command=["/usr/bin/touch", str(visible)],
            )
            writable_target = workspace / "developer-write.txt"
            writable = self._sandbox_probe(
                sandbox=SandboxMode.WORKSPACE_WRITE,
                workspace=workspace,
                runtime_directory=runtime_directory,
                codex_home=codex_home,
                command=["/usr/bin/touch", str(writable_target)],
            )
            write_denied = self._sandbox_probe(
                sandbox=SandboxMode.WORKSPACE_WRITE,
                workspace=workspace,
                runtime_directory=runtime_directory,
                codex_home=codex_home,
                command=["/bin/cat", str(sentinel)],
            )

            if (
                readable.returncode
                or denied.returncode == 0
                or read_only.returncode == 0
                or writable.returncode
                or not writable_target.exists()
                or write_denied.returncode == 0
            ):
                raise ExecutorUnavailable(
                    "installed Codex CLI could not prove the required projection-only "
                    "filesystem boundary"
                )

    def executor_id(self) -> str:
        return "openai-codex-exec-v2"

    def profile_digest(self, role: Role) -> str:
        return digest_value(
            {
                "adapter": self.executor_id(),
                "executable": self.executable,
                "version": self.version,
                "role": role.value,
                "model": self.model,
                "ephemeral": True,
                "ignore_user_config": True,
                "approval_policy": "never",
                "structured_output": True,
                "sanitized_environment": True,
                "private_home": True,
                "codex_home_auth_only": True,
                "host_skill_discovery": False,
                "managed_requirements_probed": True,
                "isolation_profile_version": ISOLATION_PROFILE_VERSION,
                "filesystem": {
                    ":root": "deny",
                    ":minimal": "read",
                    ":tmpdir": "deny",
                    ":slash_tmp": "deny",
                    ":workspace_roots": ("write" if role is Role.DEVELOPER else "read"),
                    "invocation_runtime": "write",
                },
                "command_network": False,
            }
        )

    def execute(self, invocation: RoleInvocation) -> Mapping[str, Any]:
        if not invocation.fresh:
            raise ExecutorUnavailable("Codex role invocations must be fresh")
        expected_sandbox = (
            SandboxMode.WORKSPACE_WRITE
            if invocation.role is Role.DEVELOPER
            else SandboxMode.READ_ONLY
        )
        if invocation.sandbox is not expected_sandbox:
            raise ExecutorUnavailable(
                f"Codex {invocation.role.value} invocation requires "
                f"{expected_sandbox.value} isolation"
            )
        with tempfile.TemporaryDirectory(prefix="carbon-hoh-codex-") as directory:
            output = Path(directory) / "last-message.json"
            command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--strict-config",
                "--enable",
                "skip_host_skill_discovery",
                "--config",
                'approval_policy="never"',
                *self._profile_arguments(invocation.sandbox, Path(directory)),
                "--cd",
                str(invocation.workspace),
                "--output-schema",
                str(invocation.output_schema.resolve()),
                "--output-last-message",
                str(output),
                "--color",
                "never",
            ]
            if self.model is not None:
                command.extend(["--model", self.model])
            command.append(invocation.prompt)
            environment = {
                "CODEX_HOME": os.environ.get("CODEX_HOME", str(Path.home() / ".codex")),
                "HOME": directory,
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "TMPDIR": directory,
            }
            result = subprocess.run(
                command,
                cwd=invocation.workspace,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                raise ExecutorUnavailable(
                    f"Codex {invocation.role.value} invocation failed: {detail}"
                )
            try:
                value = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise ExecutorUnavailable(
                    f"Codex {invocation.role.value} returned invalid structured output: {error}"
                ) from error
        if not isinstance(value, dict):
            raise ExecutorUnavailable("Codex structured result must be a JSON object")
        return value
