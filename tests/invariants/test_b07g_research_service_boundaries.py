"""Static and behavioral authority boundaries for B-07G composition."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from carbon import research

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "carbon" / "research" / "service.py"


def _imports() -> set[str]:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if type(node) is ast.Import:
            found.update(alias.name for alias in node.names)
        elif type(node) is ast.ImportFrom and node.module:
            found.add(node.module)
    return found


def test_service_has_no_official_fixture_adapter_or_later_wave_dependency() -> None:
    imports = _imports()
    forbidden = (
        "carbon.mcp",
        "carbon.traineval",
        "carbon.scoring",
        "carbon.cards",
        "carbon.leaderboard",
        "carbon.chain",
        "bittensor",
    )
    assert not any(
        name == blocked or name.startswith(f"{blocked}.")
        for name in imports
        for blocked in forbidden
    )


def test_dispatcher_owns_no_store_lock_task_or_domain_model_state() -> None:
    assert research.LocalResearchService.__slots__ == ("_context", "_fixture")
    assert not any(
        token in research.LocalResearchService.__dict__
        for token in (
            "_tasks",
            "_records",
            "_priors",
            "_plans",
            "_forecasts",
            "_lock",
        )
    )
    assert not hasattr(research.LocalResearchService, "submit")
    assert not hasattr(research.LocalResearchService, "get_submission_result")
    assert not hasattr(research.LocalResearchService, "quote_execution")


def test_operation_matrix_has_one_delegate_and_complete_authority_metadata() -> None:
    assert tuple(item.operation for item in research.OPERATION_MATRIX) == (
        *research.SUPPORTED_OPERATIONS,
    )
    for item in research.OPERATION_MATRIX:
        assert type(item) is research.OperationContract
        assert item.context_availability == ("EXTERNAL_PUBLIC", "FIXTURE")
        assert item.semantic_owner in {
            "B-07A",
            "B-07D3",
            "B-07C",
            "A2",
            "B-02B",
            "B-07E",
            "B-07B",
        }
        assert item.authority_ceiling
        assert item.disclosure_class
        assert item.resource_accounting_class
        assert item.error_surface
        assert item.forbidden_cross_namespace_result is (
            research.ResearchServiceErrorCode.NAMESPACE_MISMATCH
        )


def test_only_fixture_context_possesses_test_only_authority_fields() -> None:
    external = {
        field.name
        for field in dataclasses.fields(research.ExternalPublicResearchContext)
    }
    fixture = {
        field.name for field in dataclasses.fields(research.FixtureResearchContext)
    }
    assert fixture - external == {
        "test_only_prior_provider",
        "test_only_authorization_provider",
    }
    assert not {"mode", "context", "providers", "provider_registry"} & external
    assert not {"mode", "context", "providers", "provider_registry"} & fixture


def test_v1_and_b07f_public_sources_are_unchanged_by_b07g() -> None:
    from carbon import mcp
    from carbon.traineval.resolved_fixture import ResolvedPlanFixtureTrainEvalService

    assert len(mcp.__all__) == 34
    assert set(research.SUPPORTED_OPERATIONS).isdisjoint(
        {"submit", "get_submission_result"}
    )
    assert ResolvedPlanFixtureTrainEvalService not in {
        value
        for name in research.__all__
        if isinstance((value := getattr(research, name)), type)
    }
