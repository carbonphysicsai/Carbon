"""Supported `codex exec` adapter for independent structured role invocations."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .executors import RoleInvocation
from .identity import digest_value
from .models import ExecutorUnavailable, Role

REQUIRED_HELP_MARKERS = (
    "--sandbox <SANDBOX_MODE>",
    "--cd <DIR>",
    "--ephemeral",
    "--ignore-user-config",
    "--output-schema <FILE>",
    "--output-last-message <FILE>",
)


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
        self.version, self.help_text = self._probe()

    def _probe(self) -> tuple[str, str]:
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
        if version.returncode or help_result.returncode:
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
        return version_text, help_text

    def executor_id(self) -> str:
        return "openai-codex-exec-v1"

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
                "structured_output": True,
            }
        )

    def execute(self, invocation: RoleInvocation) -> Mapping[str, Any]:
        if not invocation.fresh:
            raise ExecutorUnavailable("Codex role invocations must be fresh")
        with tempfile.TemporaryDirectory(prefix="carbon-hoh-codex-") as directory:
            output = Path(directory) / "last-message.json"
            command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--sandbox",
                invocation.sandbox.value,
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
            result = subprocess.run(
                command,
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
