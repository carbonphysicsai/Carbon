"""Thin command-line interface for the bounded HoH controller."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .codex import CodexExecAdapter
from .controller import HarnessController
from .executors import ManualExecutor
from .models import ControllerPhase, HarnessError, Role
from .state_store import StateStore
from .validation import (
    validate_controller_state,
    validate_developer_result,
    validate_iteration_evidence,
    validate_iteration_plan,
    validate_requirements_manifest,
    validate_run_manifest,
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _executor(arguments: argparse.Namespace):
    if arguments.manual:
        return ManualExecutor()
    return CodexExecAdapter(model=arguments.model)


def _controller(arguments: argparse.Namespace) -> HarnessController:
    manifest = validate_run_manifest(_load(arguments.manifest))
    repository = Path(manifest["developer_worktree"])
    requirements_path = repository / manifest["requirements"]["path"]
    requirements = validate_requirements_manifest(_load(requirements_path))
    store = (
        StateStore(arguments.state_dir)
        if arguments.state_dir is not None
        else StateStore.for_repository(repository, manifest["run_id"])
    )
    return HarnessController(manifest, requirements, _executor(arguments), store)


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _run_controller(arguments: argparse.Namespace) -> int:
    controller = _controller(arguments)
    if arguments.command == "init":
        _print(controller.initialize())
        return 0
    controller.resume()
    if arguments.command == "status":
        _print(controller.snapshot())
        return 0
    if arguments.command == "step":
        _print(controller.step())
        return 0
    while ControllerPhase(controller.snapshot()["phase"]) not in {
        ControllerPhase.PAUSED_HUMAN,
        ControllerPhase.PAUSED_INFRA,
        ControllerPhase.FINAL_CANDIDATE_READY,
    }:
        controller.step()
    _print(controller.snapshot())
    return 0


def _validate(arguments: argparse.Namespace) -> int:
    value = _load(arguments.path)
    kind = arguments.kind
    if kind == "run":
        validated = validate_run_manifest(value)
    elif kind == "requirements":
        validated = validate_requirements_manifest(value)
    elif kind == "plan":
        validated = validate_iteration_plan(value, set(arguments.requirement_id))
    elif kind == "evidence":
        validated = validate_iteration_evidence(value, set(arguments.requirement_id))
    elif kind == "developer":
        validated = validate_developer_result(value)
    else:
        validated = validate_controller_state(value, set(arguments.requirement_id))
    _print(validated)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe-codex")
    probe.add_argument("--model")
    validate = commands.add_parser("validate")
    validate.add_argument(
        "kind",
        choices=("run", "requirements", "plan", "developer", "evidence", "state"),
    )
    validate.add_argument("path", type=Path)
    validate.add_argument("--requirement-id", action="append", default=[])
    for name in ("init", "step", "run", "status"):
        command = commands.add_parser(name)
        command.add_argument("manifest", type=Path)
        command.add_argument("--state-dir", type=Path)
        command.add_argument("--manual", action="store_true")
        command.add_argument("--model")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "probe-codex":
            adapter = CodexExecAdapter(model=arguments.model)
            _print(
                {
                    "available": True,
                    "executor_id": adapter.executor_id(),
                    "executable": adapter.executable,
                    "version": adapter.version,
                    "profiles": {
                        role.value: adapter.profile_digest(role) for role in Role
                    },
                }
            )
            return 0
        if arguments.command == "validate":
            return _validate(arguments)
        return _run_controller(arguments)
    except (HarnessError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Carbon HoH failed closed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
