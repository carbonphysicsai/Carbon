"""Constitutional dependency and authority boundaries for B-07A runtime."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = ROOT / "carbon" / "research"

pytestmark = pytest.mark.invariant


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_research_is_one_canonical_implementation_root() -> None:
    authority = (ROOT / ".agent" / "CODE_AUTHORITY.toml").read_text(encoding="utf-8")
    assert authority.count('"carbon/research"') == 1
    assert RESEARCH_ROOT.is_dir()


def test_v2_runtime_does_not_import_v1_service_or_official_owners() -> None:
    imports = {name for path in RESEARCH_ROOT.glob("*.py") for name in _imports(path)}
    assert "carbon.mcp" not in imports
    assert not any(name.startswith("carbon.mcp.") for name in imports)
    assert not any(name.startswith("carbon.scoring") for name in imports)
    assert not any(name.startswith("carbon.traineval") for name in imports)


def test_no_second_manifest_wire_name_exists() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in RESEARCH_ROOT.glob("*.py")
    )
    assert "class ChallengeInteractionManifest" not in source
    assert "ChallengeInteractionManifest =" not in source
    assert "class InteractionManifest" in source


def test_discovery_adapter_has_no_listener_credentials_or_dispatch_registry() -> None:
    source = (RESEARCH_ROOT / "discovery.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = _imports(RESEARCH_ROOT / "discovery.py")
    assert "socket" not in imports
    assert "asyncio" not in imports
    assert "ssl" not in imports
    assert not any(
        isinstance(node, ast.FunctionDef)
        and node.name in {"listen", "serve", "bind", "authenticate", "submit"}
        for node in ast.walk(tree)
    )
    assert "provider_registry" not in source


def test_b07s_specification_invariants_remain_separate() -> None:
    path = ROOT / "tests" / "invariants" / "test_b07s_research_service_protocol.py"
    source = path.read_text(encoding="utf-8")
    assert source.count("def test_") == 9
    assert "test_ratification_does_not_claim_implementation_or_qualification" in source
