"""C-07 non-official DEVELOPMENT orchestration authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "orchestration"

EXPECTED = {
    "__init__.py",
    "model.py",
    "projection.py",
    "report.py",
    "service.py",
}
FORBIDDEN_NAMESPACES = (
    "carbon.archive",
    "carbon.chain",
    "carbon.evidence_archive",
    "carbon.fees.service",
    "carbon.frontier",
    "carbon.leaderboard",
    "carbon.mcp",
    "carbon.qualification",
    "carbon.rewards",
    "carbon.scoring",
    "carbon.transport",
)


def _files() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE.glob("*.py")))


def _declared_exports() -> tuple[str, ...]:
    init_path = PACKAGE / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    declarations = [
        node.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and (
            (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "__all__"
            )
        )
    ]
    assert len(declarations) == 1
    exports = ast.literal_eval(declarations[0])
    assert isinstance(exports, (list, tuple))
    assert all(isinstance(exported, str) for exported in exports)
    return tuple(exports)


def test_orchestration_package_is_exact_and_exports_no_authority_upgrade() -> None:
    assert {path.name for path in _files()} == EXPECTED
    forbidden_fragments = {
        "ArchiveAcknowledgement",
        "Frontier",
        "Official",
        "Qualification",
        "Reward",
        "ScoreResult",
        "Settlement",
        "Weight",
    }
    assert not any(
        fragment in exported
        for exported in _declared_exports()
        for fragment in forbidden_fragments
    )


def test_orchestration_composes_source_owners_without_archive_or_network_imports() -> (
    None
):
    violations = []
    for path in _files():
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in FORBIDDEN_NAMESPACES
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def test_orchestration_has_no_network_process_pickle_or_dynamic_code_surface() -> None:
    forbidden_roots = {
        "asyncio",
        "ctypes",
        "http",
        "multiprocessing",
        "pickle",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    violations = []
    for path in _files():
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


def test_orchestration_authority_is_literal_false_in_model_and_projection() -> None:
    model = (PACKAGE / "model.py").read_text(encoding="utf-8")
    projection = (PACKAGE / "projection.py").read_text(encoding="utf-8")
    for field in (
        "official",
        "protected_execution_eligible",
        "score_eligible",
        "archive_acknowledged",
        "network_eligible",
        "reward_eligible",
    ):
        assert f"{field}: bool = False" in model
    for value in (
        "official",
        "protected",
        "score",
        "archive_acknowledged",
        "network",
        "reward",
    ):
        assert f'"{value}": False' in projection
    for forbidden in (
        "ScoreResult(",
        "ArchiveAcknowledgement(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in model
        assert forbidden not in projection
