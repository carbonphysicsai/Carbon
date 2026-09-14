"""C-10 stays a DEVELOPMENT audit composition without judge authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
FILES = tuple(sorted((ROOT / "carbon" / "reexecution").glob("*.py")))
MODEL = ROOT / "carbon" / "reexecution" / "model.py"


def test_reexecution_modules_have_no_scoring_archive_network_or_reward_authority() -> (
    None
):
    forbidden = (
        "carbon.chain",
        "carbon.evidence_archive",
        "carbon.frontier",
        "carbon.leaderboard",
        "carbon.miner_mcp",
        "carbon.qualification",
        "carbon.rewards",
        "carbon.scoring",
        "carbon.transport",
    )
    violations = []
    for path in FILES:
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in forbidden
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def test_reexecution_modules_open_no_network_process_or_dynamic_code_surface() -> None:
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
    for path in FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line in direct_import_modules(ROOT, path, tree=tree):
            if module.partition(".")[0] in forbidden_roots:
                violations.append(f"{path.name}:{line}:{module}")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile", "__import__"}
            ):
                violations.append(f"{path.name}:{node.lineno}:{node.func.id}")
    assert violations == []


def test_every_outcome_authority_field_is_structurally_false() -> None:
    tree = ast.parse(MODEL.read_text(encoding="utf-8"), filename=str(MODEL))
    marker = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AUTHORITY_MARKER"
            for target in node.targets
        )
    )
    assert ast.literal_eval(marker) == (
        "DEVELOPMENT_REEXECUTION_ONLY_NOT_SCIENTIFIC_RESOLUTION"
    )

    outcome = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ReexecutionOutcome"
    )
    authority_fields = {
        "comparison_policy_qualified",
        "scientific_resolution",
        "official",
        "publishable_winner",
        "archive_eligible",
        "network_eligible",
        "weight_eligible",
        "reward_eligible",
    }
    defaults = {
        node.target.id: node.value.value
        for node in outcome.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in authority_fields
        and isinstance(node.value, ast.Constant)
    }
    assert defaults == dict.fromkeys(authority_fields, False)

    document = next(
        node
        for node in outcome.body
        if isinstance(node, ast.FunctionDef) and node.name == "document"
    )
    returned = next(
        node.value for node in ast.walk(document) if isinstance(node, ast.Return)
    )
    assert isinstance(returned, ast.Dict)
    authority = next(
        value
        for key, value in zip(returned.keys, returned.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "authority"
    )
    assert isinstance(authority, ast.Dict)
    projected = {
        key.value: value
        for key, value in zip(authority.keys, authority.values, strict=True)
        if isinstance(key, ast.Constant)
    }
    assert set(projected) == authority_fields | {"marker"}
    assert all(
        isinstance(projected[name], ast.Constant) and projected[name].value is False
        for name in authority_fields
    )
    assert ast.dump(projected["marker"]) == ast.dump(
        ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr="authority_marker",
            ctx=ast.Load(),
        )
    )

    source = "\n".join(path.read_text(encoding="utf-8") for path in FILES)
    assert "value is not False" in source
    for forbidden in (
        "ArchiveAcknowledgement(",
        "ScoreResult(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in source
