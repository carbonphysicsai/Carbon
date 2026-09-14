"""C-06 signed DEVELOPMENT evidence authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "audit"

EXPECTED = {
    "__init__.py",
    "model.py",
    "projection.py",
    "signing.py",
    "store.py",
}
FORBIDDEN_NAMESPACES = (
    "carbon.archive",
    "carbon.cards",
    "carbon.chain",
    "carbon.fees",
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


def test_audit_package_is_exact_and_exports_only_development_receipt_surface() -> None:
    assert {path.name for path in _files()} == EXPECTED
    forbidden_fragments = {
        "Official",
        "Qualification",
        "Reward",
        "ScoreInput",
        "Settlement",
        "Weight",
    }
    assert not any(
        fragment in exported
        for exported in _declared_exports()
        for fragment in forbidden_fragments
    )


def test_audit_does_not_import_archive_score_reward_or_network_authority() -> None:
    violations = []
    for path in _files():
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in FORBIDDEN_NAMESPACES
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def test_audit_has_no_network_process_pickle_or_dynamic_code_surface() -> None:
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


def test_receipt_authority_is_literal_false_and_has_no_upgrade_adapter() -> None:
    model = (PACKAGE / "model.py").read_text(encoding="utf-8")
    projection = (PACKAGE / "projection.py").read_text(encoding="utf-8")
    for field in (
        "protected_execution_eligible",
        "score_eligible",
        "archive_acknowledged",
        "network_eligible",
        "reward_eligible",
    ):
        assert f"{field}: bool = False" in model
        assert f'"{field}": False' in model
    for forbidden in (
        "ScoreInput(",
        "ScoreResult(",
        "ArchiveAcknowledgement(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in model
        assert forbidden not in projection
