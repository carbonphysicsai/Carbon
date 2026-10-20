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


#: The only numpy payloads allowed in the delivery roots: the pinned public
#: DEVELOPMENT TRAIN tensors whose bytes are their Challenge kits' train_digest
#: (Validator ruling, 2026-10-19). Each must still hash to its pin.
_PINNED_NUMPY_PAYLOADS = {
    "carbon/challenge_kit/data/cooling-dev-train-400-v1.npz": (
        "b8d7839dcbfc777aa8b506a18bb9fc9b216786cb0d3533df18e6fb76ca4ec3bf"
    ),
    "carbon/challenge_kit/data/motor-dev-train-150-v1.npz": (
        "5d27220b8b0c0ccddd013299183118cdce61f205057fe99bceb95c1f52173361"
    ),
    "carbon/challenge_kit/data/f08-dev-train-255-v1.npz": (
        "65eb6a5f4e95ab3e2120c78cf3cd6a60d37554934c7d7ddea71e53cdadaac947"
    ),
    "carbon/challenge_kit/data/f08-dev-train-287-v2.npz": (
        "4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a"
    ),
}


def _forbidden_payloads(root: Path) -> list[str]:
    import hashlib

    delivery_roots = (
        root / ".agent",
        root / "Design_Specs",
        root / "carbon",
        root / "docs",
        root / "tests",
    )
    tracked_roots = tuple(
        path
        for base in delivery_roots
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    forbidden_suffixes = {".npz", ".npy"}
    found = []
    for path in tracked_roots:
        relative = path.relative_to(root).as_posix()
        if path.name.endswith("Workbench_V1.zip"):
            found.append(relative)
        elif path.suffix in forbidden_suffixes:
            pinned = _PINNED_NUMPY_PAYLOADS.get(relative)
            if (
                pinned is None
                or hashlib.sha256(path.read_bytes()).hexdigest() != pinned
            ):
                found.append(relative)
    return found


def test_no_workbench_field_archive_or_numpy_payload_is_committed() -> None:
    assert not _forbidden_payloads(_ROOT)


def test_an_unlisted_or_changed_numpy_payload_is_refused(tmp_path) -> None:
    (tmp_path / "carbon" / "challenge_kit" / "data").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "field.npz").write_bytes(b"PK")
    listed = (
        tmp_path / "carbon" / "challenge_kit" / "data" / "motor-dev-train-150-v1.npz"
    )
    listed.write_bytes(b"not the pinned tensor")
    assert sorted(_forbidden_payloads(tmp_path)) == [
        "carbon/challenge_kit/data/motor-dev-train-150-v1.npz",
        "docs/field.npz",
    ]


def test_c02_requires_actual_pinned_jax_interface_without_imposing_names() -> None:
    ticket = (_ROOT / ".agent/tickets/C-02_real_reconstruction.md").read_text(
        encoding="utf-8"
    )
    handoff = (
        _ROOT / "Design_Specs/Goal_Driven_Authoring_and_Burgers_Dynamics_V1.md"
    ).read_text(encoding="utf-8")
    for text in (ticket, handoff):
        assert "authorized JAX" in text
        assert "immutable revision" in text
        assert "training/inference" in text
        assert "must not require" in text or "not required to" in text
    assert "Carbon owns the adapter" in ticket
