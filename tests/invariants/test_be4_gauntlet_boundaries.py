"""Static and nominal boundaries for the B-E4 engineering harness."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from carbon.gauntlet import (
    HISTORICAL_V2_DESIGN_DIGEST,
    AgentSession,
    DataOnlyStrategyProposal,
    DesignAnalysisClassification,
    ExecutionReadinessProposal,
    FixtureAgentDriver,
    GauntletPreregistration,
    GauntletRecord,
    GauntletStatus,
    PreparedFixturePreflight,
    ProposedGauntletDesign,
    ReadinessProposalError,
    RunIdentity,
    parse_execution_readiness_proposal,
    parse_proposed_design,
)

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.invariant
def test_gauntlet_has_no_official_or_protected_data_dependency() -> None:
    files = tuple((ROOT / "carbon/gauntlet").glob("*.py"))
    imported = set()
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
    assert not any(
        name.startswith(
            ("carbon.generators", "carbon.evaluation.assets", "carbon.scoring")
        )
        for name in imported
    )


@pytest.mark.invariant
def test_gauntlet_records_do_not_define_a_utility_or_security_verdict() -> None:
    fields = set(GauntletRecord.__dataclass_fields__)
    assert "utility_passed" not in fields
    assert "leakage_passed" not in fields
    assert "security_qualified" not in fields
    assert "production_qualified" not in fields


@pytest.mark.invariant
def test_reserved_inputs_default_missing_and_v2_pins_are_nominal() -> None:
    preregistration = GauntletPreregistration()
    assert not preregistration.is_complete
    assert preregistration.missing_inputs
    assert "prior_pack_ref" in RunIdentity.__dataclass_fields__
    assert "test_only_authorization_ref" in RunIdentity.__dataclass_fields__
    assert "authorization_verified" not in RunIdentity.__dataclass_fields__
    assert "QUALIFYING_EXECUTION_RECORDED" not in GauntletStatus.__members__
    assert "ENGINEERING_READY" not in GauntletStatus.__members__


@pytest.mark.invariant
def test_design_analysis_artifact_has_no_ratification_or_execution_authority() -> None:
    path = ROOT / ".agent" / "preregistrations" / "B-E4_recommended_design_v2.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "f765ec85995ec52eb2f0d7c28af1dd061feed0f59c205192861e045ddf6b710a"
    )
    design = parse_proposed_design(path.read_text(encoding="utf-8"))
    assert type(design) is ProposedGauntletDesign
    assert design.design_digest == HISTORICAL_V2_DESIGN_DIGEST
    assert not design.qualifying_execution_ready
    assert not design.is_verified_owner_ratified
    assert not hasattr(design, "ratifications")
    assert all(
        item.value.startswith("DESIGN_ANALYSIS_ONLY_")
        for item in DesignAnalysisClassification
    )


@pytest.mark.invariant
def test_v3_proposal_is_exactly_blocked_unratified_and_content_bound() -> None:
    path = ROOT / ".agent" / "preregistrations" / "B-E4_recommended_design_v3.json"
    document = path.read_text(encoding="utf-8")
    payload = json.loads(document)
    proposal = parse_execution_readiness_proposal(document)

    assert type(proposal) is ExecutionReadinessProposal
    assert proposal.status == payload["status"] == "STILL_BLOCKED"
    assert payload["previous_design_digest"] == HISTORICAL_V2_DESIGN_DIGEST
    assert payload["ratifications"] == []
    assert payload["readiness"]["human_ratifications_present"] is False
    assert payload["readiness"]["qualifying_execution_ready"] is False
    assert proposal.preregistration.ratifications == ()
    assert not proposal.is_verified_owner_ratified
    assert not proposal.qualifying_execution_ready
    assert proposal.preregistration_design_digest == (
        "sha256:11a2b6b7e3817cea62631dfbdd0e5b59393d70f0cb9617776b8996ed535d1538"
    )
    assert proposal.proposal_digest == (
        "sha256:98d06ae32ce75f3966795d57d8a45b229254b14d717ebe00d5636cf1151301ce"
    )

    payload["status"] = "EXECUTION_READY_PROPOSED"
    payload["readiness"]["engineering_blockers"] = []
    for component in payload["engineering_readiness"].values():
        component["state"] = "READY"
        component["blockers"] = []
    with pytest.raises(
        ReadinessProposalError, match="cross-profile dependence blocker"
    ):
        parse_execution_readiness_proposal(json.dumps(payload, sort_keys=True))


@pytest.mark.invariant
def test_readiness_proposal_cannot_create_a_qualifying_gauntlet_record() -> None:
    path = ROOT / ".agent" / "preregistrations" / "B-E4_recommended_design_v3.json"
    proposal = parse_execution_readiness_proposal(path.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="qualifying execution recording unavailable"):
        GauntletRecord(proposal.preregistration, (), (), (), (), True)


@pytest.mark.invariant
def test_agent_visible_preflight_has_no_io_execution_or_shadow_identity() -> None:
    path = ROOT / "carbon" / "gauntlet" / "agents.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if type(node) in (ast.Import, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_roots.isdisjoint(
        {"asyncio", "http", "os", "pathlib", "requests", "socket", "subprocess"}
    )
    assert "eval(" not in source and "exec(" not in source
    assert "shadow" not in source.casefold()

    agent_visible_slots = set().union(
        AgentSession.__slots__,
        FixtureAgentDriver.__slots__,
        DataOnlyStrategyProposal.__slots__,
        PreparedFixturePreflight.__slots__,
    )
    assert not any("shadow" in name.casefold() for name in agent_visible_slots)
