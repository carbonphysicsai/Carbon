"""Authority and namespace boundaries for the B-07B local lifecycle."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.research import (
    WIRE_RECORD_NAMES_BY_TYPE,
    ExperimentRecord,
    ResearchEvidenceClass,
    ResearchFailureCategory,
    ResearchTaskProvider,
    ResearchTaskState,
)
from carbon.research.lifecycle import _TRANSITIONS

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = ROOT / "carbon" / "research"

pytestmark = pytest.mark.invariant


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_private_records_do_not_widen_the_frozen_wire_registry() -> None:
    assert ExperimentRecord not in WIRE_RECORD_NAMES_BY_TYPE
    assert not any(
        name in WIRE_RECORD_NAMES_BY_TYPE.values()
        for name in (
            "experiment_record",
            "evidence_context",
            "execution_identity",
            "retention_reuse_binding",
        )
    )


def test_transition_table_is_exactly_the_ratified_state_machine() -> None:
    assert _TRANSITIONS == frozenset(
        {
            (ResearchTaskState.QUEUED, ResearchTaskState.RUNNING),
            (ResearchTaskState.QUEUED, ResearchTaskState.CANCELLED),
            (ResearchTaskState.QUEUED, ResearchTaskState.FAILED_INFRA),
            (ResearchTaskState.RUNNING, ResearchTaskState.CANCEL_REQUESTED),
            (ResearchTaskState.RUNNING, ResearchTaskState.SUCCEEDED),
            (ResearchTaskState.RUNNING, ResearchTaskState.FAILED_INFRA),
            (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.CANCELLED),
            (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.SUCCEEDED),
            (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.FAILED_INFRA),
        }
    )


def test_evidence_classes_have_no_official_upgrade_path() -> None:
    assert tuple(ResearchEvidenceClass.__members__) == (
        "STRUCTURAL_ONLY",
        "STATIC_EXACT",
        "CALIBRATED_RESOURCE_FORECAST",
        "PRACTICE_NON_AUTHORITATIVE",
        "MMS_VERIFICATION",
        "REFERENCE_ASSESSMENT",
        "GENERATOR_CONFORMANCE",
        "HYBRID_COMPONENT",
        "PRODUCT_BATTERY",
    )
    assert "OFFICIAL_EVIDENCE" not in ResearchEvidenceClass.__members__


def test_scientific_failure_categories_remain_distinct_from_infrastructure() -> None:
    assert tuple(ResearchFailureCategory.__members__) == (
        "STRATEGY",
        "RECONSTRUCTION",
        "GENERATOR",
        "REFERENCE",
        "MEASUREMENT",
        "SCIENTIFIC_ADMISSIBILITY",
    )
    assert "INFRASTRUCTURE" not in ResearchFailureCategory.__members__


def test_task_provider_contract_remains_three_operations() -> None:
    assert tuple(
        name for name in ResearchTaskProvider.__dict__ if not name.startswith("_")
    ) == (
        "start_research_task",
        "get_research_result",
        "cancel_research_task",
    )


def test_b07b_runtime_does_not_import_official_or_full_service_owners() -> None:
    imports = {
        name
        for path in (RESEARCH_ROOT / "lifecycle.py", RESEARCH_ROOT / "records.py")
        for name in _imports(path)
    }
    assert "carbon.mcp" not in imports
    assert not any(name.startswith("carbon.mcp.") for name in imports)
    assert not any(name.startswith("carbon.scoring") for name in imports)
    assert not any(name.startswith("carbon.traineval") for name in imports)
    assert not any(name.startswith("carbon.leaderboard") for name in imports)


def test_local_lifecycle_has_no_listener_authentication_or_dispatch() -> None:
    source = (RESEARCH_ROOT / "lifecycle.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = _imports(RESEARCH_ROOT / "lifecycle.py")
    assert not imports.intersection({"socket", "ssl", "asyncio"})
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"listen", "serve", "bind", "authenticate", "dispatch"}
        for node in ast.walk(tree)
    )
    assert "ServiceCall" not in source
    assert "ServiceReply" not in source


def test_b07a_discovery_adapter_remains_the_only_local_adapter() -> None:
    discovery = (RESEARCH_ROOT / "discovery.py").read_text(encoding="utf-8")
    assert "START_RESEARCH_TASK" not in discovery
    assert "InMemoryResearchTaskProvider" not in discovery
    assert "class LocalDiscoveryAdapter" in discovery


def test_b07s_specification_test_count_and_manifest_remain_frozen() -> None:
    source = (
        ROOT / "tests" / "invariants" / "test_b07s_research_service_protocol.py"
    ).read_text(encoding="utf-8")
    assert source.count("def test_") == 9
    assert '"task_polls": 10000' in (
        ROOT / "Design_Specs" / "Miner_MCP_Wave_B_Service_Protocol.md"
    ).read_text(encoding="utf-8")
