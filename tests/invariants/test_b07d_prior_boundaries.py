"""Static authority and dependency boundaries for B-07D1/D2/D3."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    ROOT / "carbon/research/prior_store.py",
    ROOT / "carbon/research/prior_publisher.py",
    ROOT / "carbon/research/prior_provider.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    output: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            output.add(node.module)
    return output


def test_prior_runtime_does_not_reach_private_analytics_or_official_scoring():
    forbidden = (
        "carbon.cards",
        "carbon.landscape",
        "carbon.scoring",
        "carbon.traineval",
        "carbon.mcp",
    )
    for path in MODULES:
        imports = _imports(path)
        assert not any(
            imported == prefix or imported.startswith(prefix + ".")
            for imported in imports
            for prefix in forbidden
        ), path


def test_publisher_has_no_experiment_record_or_public_activation_route():
    source = MODULES[1].read_text(encoding="utf-8")
    assert not any("records" in imported for imported in _imports(MODULES[1]))
    assert "def activate_public" not in source
    assert "QUALIFIED_OFFICIAL" in source  # specified as future-only vocabulary


def test_v1_compatibility_is_offline_and_defines_no_provider():
    source = (ROOT / "carbon/prior_compat.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert not any(name.endswith("Provider") for name in class_names)
    assert "project_v2_to_v1_private" in source


def test_static_providers_preserve_nominal_public_fixture_separation():
    source = MODULES[2].read_text(encoding="utf-8")
    assert "class StaticPublicPriorProvider" in source
    assert "class StaticTestOnlyPriorProvider" in source
    assert "_FIXTURE_CAPABILITY" in source
    assert "latest" not in source.lower()
