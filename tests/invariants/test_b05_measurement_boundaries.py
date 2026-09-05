from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pytest

from carbon import measurement
from tests.cpu.test_b05_measurement_contract import contract

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT_ROOT = REPOSITORY_ROOT / "carbon" / "measurement"
UPSTREAM_ROOTS = (
    REPOSITORY_ROOT / "carbon" / "authoring",
    REPOSITORY_ROOT / "carbon" / "evaluation",
    REPOSITORY_ROOT / "carbon" / "resource_policy",
    REPOSITORY_ROOT / "carbon" / "scoring",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
    return result


@pytest.mark.invariant
def test_completed_upstream_packages_do_not_import_measurement() -> None:
    for root in UPSTREAM_ROOTS:
        for path in root.rglob("*.py"):
            assert all(
                module != "carbon.measurement"
                and not module.startswith("carbon.measurement.")
                for module in imported_modules(path)
            ), path


@pytest.mark.invariant
def test_first_slice_has_no_resource_scoring_or_later_ticket_import() -> None:
    forbidden = (
        "carbon.resource_policy",
        "carbon.scoring",
        "carbon.qualification",
        "carbon.mcp",
    )
    for path in MEASUREMENT_ROOT.rglob("*.py"):
        for module in imported_modules(path):
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden
            ), (path, module)


@pytest.mark.invariant
def test_public_surface_exposes_no_a5_constructor_or_engine() -> None:
    assert "ScoreInput" not in measurement.__all__
    assert "ScoreEngine" not in measurement.__all__
    assert "LoadedScorePack" not in measurement.__all__
    assert not hasattr(measurement, "ScoreInput")
    assert not hasattr(measurement, "ScoreEngine")


@pytest.mark.invariant
def test_measurement_refs_are_protected_and_nonpickleable() -> None:
    value = contract()
    refs = (value.unit_ref, measurement.measurement_ref(value))
    for ref in refs:
        assert "fixture-burgers" not in repr(ref)
        assert "fixture-burgers" not in str(ref)
        with pytest.raises(TypeError):
            pickle.dumps(ref)
