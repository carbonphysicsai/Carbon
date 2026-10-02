"""Phase 1 of the Challenge Roadmap: the protocol draft and Graphite's
per-stage permission ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.challenge_pipeline.graphite_ledger import STAGES, graphite_may, load_ledger
from carbon.challenge_pipeline.state import PROTOCOL, REPOSITORY

DOCS = REPOSITORY / "docs/development/challenge_pipeline"


def test_every_ledger_role_is_a_graphite_role():
    ledger = load_ledger()
    known = {role.value for role in RoleName}
    assert set(known) == {role.value for role in ROLES}
    for stage in STAGES:
        assert set(ledger["stages"][stage]["roles"]) <= known, stage
    assert ledger["status"] == "DRAFT"


def test_the_frozen_run_admits_no_graphite_role_and_rank_only_the_writer():
    for role in RoleName:
        assert not graphite_may("frozen_run", role)
        assert graphite_may("rank", role) == (role is RoleName.WRITER)
    assert not graphite_may("prioritize", RoleName.CONSTRUCTOR)
    assert not graphite_may("design", RoleName.ATTACKER)
    assert graphite_may("test_iterate", RoleName.ATTACKER)
    assert graphite_may("test_iterate", "attacker")
    assert not graphite_may("deployed", RoleName.WRITER)


def test_the_ledger_refuses_a_reordered_or_missing_stage(tmp_path):
    ledger = json.loads(
        (REPOSITORY / "carbon/challenge_pipeline/graphite_ledger.json").read_text()
    )
    del ledger["stages"]["frozen_run"]
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match="stages"):
        load_ledger(path)


def test_the_protocol_draft_and_its_templates_are_the_step_two_evidence():
    protocol = json.loads(PROTOCOL.read_text())
    step2 = protocol["phase_1"][1]
    assert step2["status"] == "done" and step2["ticket"] == "CHALLENGE-PROTOCOL-02"
    assert (REPOSITORY / step2["evidence"]) == DOCS / "PROTOCOL_DRAFT.md"
    draft = (DOCS / "PROTOCOL_DRAFT.md").read_text()
    for heading in (
        "Stage 1: Prioritize",
        "Stage 2: Design",
        "Stage 3: Test / iterate",
        "Stage 4: Rank for deployment",
        "Graphite permission ledger",
    ):
        assert heading in draft
    for template in (
        "CHALLENGE_BRIEF.md",
        "DESIGN_PACKET.md",
        "FROZEN_EVIDENCE_RECORD.md",
    ):
        text = (DOCS / "templates" / template).read_text()
        assert "DRAFT until protocol lock" in text, template
    assert Path(protocol["roadmap"]).name == "Challenge_Roadmap.md"
