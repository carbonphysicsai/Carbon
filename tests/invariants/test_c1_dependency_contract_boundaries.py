"""Fail-closed checks for the selected Wave-C development contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_c09_remains_contract_only_and_unselected() -> None:
    ticket = _read(".agent/tickets/C-09_official_testnet_publication_provider.md")
    assert ticket.startswith("# C-09 ")
    assert (
        "`future_reserved`; contract materialized, unselected and unstarted" in ticket
    )
    assert "Contract materialization only" in ticket


def test_only_cw1_development_slice_is_selected() -> None:
    wave = _read(".agent/WAVE.md")
    wave_c = _read(".agent/WAVE_C.md")
    graph = _read(".agent/plans/C1_DEPENDENCY_GRAPH.md")
    for record in (wave, wave_c):
        assert "**Selected ticket:** C-W1-D2 — `in_progress`" in record
        assert "**Active ticket:**" in record
        assert "C-W1-D1" in record
        assert "DEVELOPMENT" in record
        assert "**Next boundary:**" in record
        assert "ROW_VERIFIED" in record
        assert "INDETERMINATE_NO_ACCEPTANCE_RULE" in record
        assert "C-EA2" in record and "blocked" in record
    assert "C-04(PR #154 engineering + D-03/D-04 prerequisite harness)" in graph
    assert "C-05(PR #157 engineering + D-02/D-05 prerequisite harness)" in graph
    assert "C-06(PR #161 DEVELOPMENT receipt)" in graph
    assert (
        "C-07(PR #163 DEVELOPMENT orchestration) ─> C-08(PR #167 DEVELOPMENT composition)"
        in graph
    )
    assert "C-06 + C-07 ─> C-10(PR #173 bounded DEVELOPMENT re-execution)" in graph
    assert "C-EP1 ─> C-EP2(done measurement/replay only; no sharing runtime)" in graph
    assert "C-02(merged DEVELOPMENT adapter prerequisite; full ticket open)" in graph
    assert "└─> C-03(PR #149 capability + PR #151 hardening)" in graph
    assert graph.count("| **no** |") >= 2
    assert (
        "| C-03 | PR #149 bounded DEVELOPMENT capability and PR #151 hardening accepted"
        in graph
    )
    assert "**yes, C-W1-D2 only**" in graph
    assert "AWS deployment deferred" in graph
    assert "Hippius preferred but unverified" in graph


def test_jax_and_archive_blocks_remain_complete_and_fail_closed() -> None:
    graph = _read(".agent/plans/C1_DEPENDENCY_GRAPH.md")
    c02 = _read(".agent/tickets/C-02_real_reconstruction.md")
    c03 = _read(".agent/tickets/C-03_isolated_reconstruction_worker.md")
    c09 = _read(".agent/tickets/C-09_official_testnet_publication_provider.md")
    required = (
        "authorized JAX repository/source",
        "immutable commit/revision",
        "reproducible dependency/build identity",
        "training and inference entry",
        "batching/layout rules",
        "PRNG/RNG ownership",
        "checkpoint/artifact format",
        "JIT/sharding expectations",
        "failure/error semantics",
    )
    for marker in required:
        assert marker in graph
    assert "satisfied for this bounded" in c02
    assert "Production source selection" in c02
    assert "Wrap the merged C-02 adapter in one pinned Docker/OCI worker" in c03
    assert "full C-02 closure remains open and non-blocking" in c03
    assert "C-EA2" in c09
    assert "synthetic-archive" in c09


def test_hub_projects_only_cw1_development_slice() -> None:
    data = json.loads(_read("docs/development/carbon_hub/data/hub_data_v2.json"))
    current = data["current"]
    assert current["last_completed_ticket"]["id"] == "C-10"
    assert current["selected_ticket"]["id"] == "C-W1-D2"
    assert current["next_selected_ticket"] is None
    tickets = {ticket["id"]: ticket for ticket in data["tickets"]}
    assert tickets["C-EP1"]["status"] == "done"
    assert tickets["C-EP2"]["status"] == "done"
    assert tickets["C-EP3"]["status"] == "done"
    assert tickets["C-02"]["status"] == "in_progress"
    assert tickets["C-03"]["status"] == "in_progress"
    assert tickets["C-03"]["implementation_state"] == "bounded_development_accepted"
    assert "34778563403" in tickets["C-03"]["current_stage"]
    assert tickets["C-04"]["status"] == "done"
    assert tickets["C-04"]["implementation_state"] == "bounded_development_accepted"
    assert "34784739423" in tickets["C-04"]["current_stage"]
    assert tickets["C-05"]["status"] == "done"
    assert tickets["C-05"]["implementation_state"] == "bounded_development_accepted"
    assert "34789621325" in tickets["C-05"]["current_stage"]
    assert tickets["C-06"]["status"] == "done"
    assert tickets["C-06"]["implementation_state"] == "bounded_development_accepted"
    assert "34797587027" in tickets["C-06"]["current_stage"]
    assert tickets["C-07"]["status"] == "done"
    assert tickets["C-07"]["implementation_state"] == "bounded_development_accepted"
    assert "34807243278" in tickets["C-07"]["current_stage"]
    assert tickets["C-08"]["status"] == "done"
    assert tickets["C-08"]["implementation_state"] == "bounded_development_accepted"
    assert "34816242461" in tickets["C-08"]["current_stage"]
    assert tickets["C-EA1"]["status"] == "in_progress"
    assert (
        tickets["C-EA1"]["implementation_state"]
        == "aws_v2_package_accepted_deployment_deferred"
    )
    assert "PR #180" in tickets["C-EA1"]["current_stage"]
    assert "Hippius is preferred but unverified" in tickets["C-EA1"]["current_stage"]
    assert tickets["C-EA1"]["maturity_states"]["tested"] == "earned"
    assert tickets["C-10"]["status"] == "done"
    assert tickets["C-10"]["implementation_state"] == "bounded_development_accepted"
    assert tickets["C-09"]["status"] == "todo"
    assert tickets["C-09"]["implementation_state"] == "unstarted"
    assert "not dependency-ready" in tickets["C-09"]["current_stage"]
    assert tickets["C-W1"]["status"] == "in_progress"
    assert (
        tickets["C-W1"]["implementation_state"]
        == "development_testnet_candidate_official_unstarted"
    )
    assert "No subsequent activation" in tickets["C-W1"]["current_stage"]
    assert "8010852" in current["stage"]
    assert "Subnet 567" in current["stage"]
    assert "AWS stays deferred" in current["stage"]
    assert "Hippius unverified" in current["stage"]
    assert "No subsequent activation" in current["stage"]
    assert "C-W1 DEVELOPMENT" in current["stage"]
