"""Structural B-E2 no-fallback, no-execution, and authority invariants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

_ROOT = Path(__file__).resolve().parents[2]
_BOUNDARY = _ROOT / "carbon" / "evaluation" / "service_boundary.py"
_FIXTURES = _ROOT / "carbon" / "evaluation" / "service_fixtures.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_be2_wraps_only_the_existing_evaluation_owner() -> None:
    for path in (_BOUNDARY, _FIXTURES):
        imports = {
            alias.name
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imports = {
            node.module
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        names = imports | from_imports
        assert not any(
            name.startswith(
                (
                    "carbon.scoring",
                    "carbon.leaderboard",
                    "carbon.traineval",
                    "carbon.mcp",
                    "carbon.qualification",
                    "carbon.generators",
                    "carbon.seeding",
                )
            )
            for name in names
        )


def test_be2_has_no_dynamic_code_io_network_or_fallback_call() -> None:
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "popen",
        "request",
        "urlopen",
    }
    violations = []
    for path in (_BOUNDARY, _FIXTURES):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if name in forbidden_calls:
                violations.append(f"{path.name}:{node.lineno}:{name}")
    assert violations == []


def test_be2_service_surface_has_no_candidate_score_truth_or_fallback_result() -> None:
    tree = _tree(_BOUNDARY)
    declared = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert not any(
        token in name.lower()
        for name in declared
        for token in (
            "candidate",
            "fallback",
            "leaderboard",
            "promotion",
            "ranking",
            "score",
            "settlement",
            "truthasset",
        )
    )
    exported = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    )
    exported_names = {
        item.value
        for item in exported.value.elts
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }
    assert all("Truth" not in name and "Score" not in name for name in exported_names)


def test_be2_response_schema_carries_no_ambient_authority_or_protected_payload() -> (
    None
):
    tree = _tree(_BOUNDARY)
    response = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ReferenceServiceResponse"
    )
    fields = {
        node.target.id
        for node in response.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    forbidden = {
        "callable",
        "candidate_result",
        "code",
        "command",
        "credential",
        "filesystem_path",
        "import_path",
        "mode",
        "password",
        "protected_case",
        "seed",
        "token",
        "url",
    }
    assert fields.isdisjoint(forbidden)
    assert "artifact_content" in fields
    assert "request_ref" in fields
    assert "grant_ref" in fields
    assert "resolution_ref" in fields


def test_be2_does_not_import_or_restore_archived_julia() -> None:
    assert not (_ROOT / "Julia").exists()
    for path in (_BOUNDARY, _FIXTURES):
        source = path.read_text(encoding="utf-8")
        assert "juliacall" not in source
        assert "pyjulia" not in source
        assert "Pkg.add" not in source
        assert "Pkg.update" not in source
