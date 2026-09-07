"""Static dependency and authority boundaries for B-07E."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "carbon/research/resource_estimation.py"


def _imports() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    output: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            output.add(node.module)
    return output


def test_b07e_does_not_import_private_analytics_scoring_or_settlement():
    forbidden = (
        "carbon.cards",
        "carbon.landscape",
        "carbon.scoring",
        "carbon.traineval",
        "carbon.fees",
        "carbon.chain",
        "carbon.treasury",
        "carbon.settlement",
    )
    imports = _imports()
    assert not any(
        imported == prefix or imported.startswith(prefix + ".")
        for imported in imports
        for prefix in forbidden
    )


def test_b07e_preserves_nominal_static_forecast_and_test_only_separation():
    source = MODULE.read_text(encoding="utf-8")
    assert "class StaticResourceInspectionProvider" in source
    assert "class UncalibratedResourceForecastProvider" in source
    assert "class TestOnlyCalibratedResourceForecastProvider" in source
    assert "_TEST_ONLY_FORECAST_CAPABILITY" in source
    assert "def quote_execution" not in source
    assert "ObservedResourceReceipt(" not in source
    assert "ResourceForecast(" in source


def test_a9_estimate_and_b07d3_alignment_owners_are_not_modified_or_imported():
    imports = _imports()
    assert "carbon.mcp" not in imports
    source = MODULE.read_text(encoding="utf-8")
    assert "DeterministicPriorAlignmentProvider" not in source
    assert "StructuralEstimate" not in source


def test_forecast_source_has_no_production_calibration_or_authority_switch():
    source = MODULE.read_text(encoding="utf-8")
    assert "UncalibratedResourceForecastProvider" in source
    assert "CALIBRATION_AUTHORITY_UNAVAILABLE" in source
    assert "TEST_ONLY_SYNTHETIC_CALIBRATION_NOT_PRODUCTION" in source
    assert "production_calibration=" not in source
    assert "emission_capable" not in source
    assert "caller_authority" not in source
