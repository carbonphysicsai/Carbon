"""Atomic external run-state persistence under the Git common directory."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .identity import canonical_json_bytes, resolve_git_common_dir
from .models import IdentityMismatch


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @classmethod
    def for_repository(cls, repository: Path, run_id: str) -> StateStore:
        common = resolve_git_common_dir(repository)
        return cls(common / ".carbon-hoh" / "runs" / run_id)

    @property
    def manifest_path(self) -> Path:
        return self.root / "run_manifest.json"

    @property
    def state_path(self) -> Path:
        return self.root / "controller_state.json"

    def _atomic_write(self, path: Path, value: Any) -> None:
        payload = canonical_json_bytes(value)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=self.root,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def initialize(self, run_manifest: dict[str, Any], state: dict[str, Any]) -> None:
        if self.manifest_path.exists() or self.state_path.exists():
            raise IdentityMismatch(f"run state already exists at {self.root}")
        self._atomic_write(self.manifest_path, run_manifest)
        self._atomic_write(self.state_path, state)

    def save_state(self, state: dict[str, Any]) -> None:
        if not self.manifest_path.is_file():
            raise IdentityMismatch("run manifest is missing from external state")
        self._atomic_write(self.state_path, state)

    def load_manifest(self) -> dict[str, Any]:
        return self._load(self.manifest_path, "run manifest")

    def load_state(self) -> dict[str, Any]:
        return self._load(self.state_path, "controller state")

    @staticmethod
    def _load(path: Path, label: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise IdentityMismatch(f"cannot load {label} {path}: {error}") from error
        if not isinstance(value, dict):
            raise IdentityMismatch(f"{label} must be a JSON object")
        return value
