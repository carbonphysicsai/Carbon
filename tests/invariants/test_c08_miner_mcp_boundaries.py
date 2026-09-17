"""C-08 composes source owners without acquiring their authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "miner_mcp"


def _literal_exports() -> tuple[str, ...]:
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]
    assert len(declarations) == 1
    exports = ast.literal_eval(declarations[0].value)
    assert isinstance(exports, tuple)
    return exports


def test_package_is_exact_and_exports_no_official_or_network_surface() -> None:
    miner_mcp_exports = _literal_exports()
    assert {path.name for path in PACKAGE.glob("*.py")} == {
        "__init__.py",
        "model.py",
        "research.py",
        "service.py",
        "store.py",
    }
    assert tuple(miner_mcp_exports) == (
        "AuthenticatedMcpResult",
        "AuthenticatedMinerMcpService",
        "BindMode",
        "MinerMcpCode",
        "MinerMcpFailure",
        "MinerMcpJournal",
    )
    assert not any(
        fragment in name
        for name in miner_mcp_exports
        for fragment in ("Archive", "Official", "Reward", "Score", "Weight")
    )


def test_source_owners_do_not_depend_on_c08_and_c08_has_no_lateral_authority() -> None:
    for owner in ("transport", "mcp", "execution", "orchestration", "fees"):
        for path in (ROOT / "carbon" / owner).glob("*.py"):
            assert "carbon.miner_mcp" not in path.read_text(encoding="utf-8")
    forbidden = (
        "carbon.archive",
        "carbon.chain.publisher",
        "carbon.evidence_archive",
        "carbon.frontier",
        "carbon.leaderboard",
        "carbon.qualification",
        "carbon.rewards",
        "carbon.scoring",
    )
    violations = []
    for path in PACKAGE.glob("*.py"):
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in forbidden
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def test_c08_opens_no_listener_process_dynamic_code_or_pickle_surface() -> None:
    forbidden_roots = {
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
    for path in PACKAGE.glob("*.py"):
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


def test_c08_projection_contains_only_literal_false_eligibility() -> None:
    source = (PACKAGE / "model.py").read_text(encoding="utf-8")
    assert 'item is not False for item in copied["eligibility"].values()' in source
    for forbidden in (
        "ScoreResult(",
        "ArchiveAcknowledgement(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in source
