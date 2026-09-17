"""C-05 measurement runtime dependency and authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "measurement_runtime"
CARBON = ROOT / "carbon"

EXPECTED = {
    "__init__.py",
    "controller.py",
    "development.py",
    "development_controls.py",
    "model.py",
    "protocol.py",
    "qualification_candidate.py",
    "validator.py",
}
FORBIDDEN_NAMESPACES = (
    "carbon.cards",
    "carbon.chain",
    "carbon.fees",
    "carbon.leaderboard",
    "carbon.mcp",
    "carbon.qualification",
    "carbon.rewards",
    "carbon.scoring",
    "carbon.transport",
)


def _files() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE.glob("*.py")))


def test_runtime_package_is_exact_and_has_no_root_authority_surface() -> None:
    assert {path.name for path in _files()} == EXPECTED
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "__all__"
    ]
    assert len(declarations) == 1
    assert ast.literal_eval(declarations[0].value) == ()


def test_measurement_runtime_does_not_import_scoring_or_consumer_authority() -> None:
    violations = []
    for path in _files():
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in FORBIDDEN_NAMESPACES
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


@pytest.mark.parametrize(
    "name", ("model.py", "development.py", "development_controls.py")
)
def test_numerical_model_has_no_network_process_or_dynamic_code_surface(name) -> None:
    path = PACKAGE / name
    forbidden_roots = {
        "asyncio",
        "ctypes",
        "http",
        "multiprocessing",
        "os",
        "pickle",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    violations = []
    for module, line in direct_import_modules(ROOT, path):
        if module.partition(".")[0] in forbidden_roots:
            violations.append(f"{path.name}:{line}:{module}")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "compile", "__import__"}
        ):
            violations.append(f"{path.name}:{node.lineno}:{node.func.id}")
    assert violations == []


def test_worker_has_one_fixed_measurement_dispatch_without_caller_command() -> None:
    entrypoint = (CARBON / "reconstruction" / "worker" / "entrypoint.py").read_text(
        encoding="utf-8"
    )
    assert "run_staged_measurement_worker" in entrypoint
    assert "measurement-request.json" in entrypoint
    assert "sys.argv" not in entrypoint
    assert "subprocess" not in entrypoint


def test_measurement_has_no_score_reward_archive_or_network_effect() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _files())
    for forbidden in (
        "ScoreEngine(",
        "ScoreInput(",
        "SettlementObligation(",
        "ArchiveAcknowledgement(",
        "WeightIntent(",
    ):
        assert forbidden not in source
    assert '"score_input": None' in source
    assert '"score": False' in source
