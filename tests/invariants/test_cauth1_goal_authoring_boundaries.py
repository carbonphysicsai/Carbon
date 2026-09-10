"""C-AUTH1 authority, evidence-role, and execution-boundary invariants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.authoring.goals import compile_goal_intake
from carbon.generators import burgers_dynamics

pytestmark = pytest.mark.invariant

_ROOT = Path(__file__).resolve().parents[2]
_FILES = (
    _ROOT / "carbon" / "authoring" / "goals.py",
    _ROOT / "carbon" / "authoring" / "cli.py",
    _ROOT / "carbon" / "generators" / "burgers_dynamics.py",
)


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def test_cauth1_runtime_has_no_network_process_or_dynamic_code_imports() -> None:
    forbidden = {
        "asyncio",
        "ctypes",
        "http",
        "importlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    for path in _FILES:
        assert _imports(path).isdisjoint(forbidden), path


def test_cauth1_defines_no_arbitrary_callable_or_execution_primitive() -> None:
    forbidden = {"Callable", "eval", "exec", "compile", "__import__"}
    for path in _FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert identifiers.isdisjoint(forbidden), path


def test_public_burgers_generator_imports_no_official_or_qualification_api() -> None:
    source = (_ROOT / "carbon" / "generators" / "burgers_dynamics.py").read_text(
        encoding="utf-8"
    )
    forbidden = {
        "OfficialContext",
        "OfficialEntropy",
        "QualificationContext",
        "QualificationEntropy",
        "derive_official_seed",
        "derive_qualification_seed",
    }
    assert all(name not in source for name in forbidden)


def test_candidate_payload_has_only_the_four_declared_inputs() -> None:
    assert burgers_dynamics.CANDIDATE_PAYLOAD_KEYS == {
        "domain_length",
        "initial_field",
        "requested_times",
        "viscosity",
    }


def test_authoring_api_exposes_no_registration_or_qualification_action() -> None:
    public = set(compile_goal_intake.__module__.split())
    assert public == {"carbon.authoring.goals"}
    source = (_ROOT / "carbon" / "authoring" / "goals.py").read_text(encoding="utf-8")
    for call in ("register_challenge(", "qualify(", "publish(", "sign("):
        assert call not in source


def test_no_workbench_field_archive_or_numpy_payload_is_committed() -> None:
    delivery_roots = (
        _ROOT / ".agent",
        _ROOT / "Design_Specs",
        _ROOT / "carbon",
        _ROOT / "docs",
        _ROOT / "tests",
    )
    tracked_roots = tuple(
        path
        for root in delivery_roots
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    forbidden_suffixes = {".npz", ".npy"}
    assert not [path for path in tracked_roots if path.suffix in forbidden_suffixes]
    assert not [
        path for path in tracked_roots if path.name.endswith("Workbench_V1.zip")
    ]
