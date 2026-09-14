"""Fail-closed checks for the selected bounded C-06 dependency contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_materialized_tickets_are_contract_only_and_unselected() -> None:
    for path, ticket_id in (
        (".agent/tickets/C-08_authenticated_miner_mcp_e2e.md", "C-08"),
        (".agent/tickets/C-09_official_testnet_publication_provider.md", "C-09"),
    ):
        ticket = _read(path)
        assert ticket.startswith(f"# {ticket_id} ")
        assert (
            "`future_reserved`; contract materialized, unselected and unstarted"
            in ticket
        )
        assert "Contract materialization only" in ticket


def test_only_c06_development_receipt_is_selected_and_c07_is_next() -> None:
    wave = _read(".agent/WAVE.md")
    wave_c = _read(".agent/WAVE_C.md")
    graph = _read(".agent/plans/C1_DEPENDENCY_GRAPH.md")
    for record in (wave, wave_c):
        assert "**Selected ticket:** C-06 — `in_progress`" in record
        assert "**Active ticket:** C-06 signed non-official DEVELOPMENT" in record
        assert "**Next authorized ticket after current merge:** C-07" in record
    assert "C-04(PR #154 engineering + D-03/D-04 prerequisite harness)" in graph
    assert "C-05(PR #157 engineering + D-02/D-05 prerequisite harness)" in graph
    assert "C-06(selected DEVELOPMENT receipt)" in graph
    assert "C-EP1 ─> C-EP2(done measurement/replay only; no sharing runtime)" in graph
    assert "C-02(merged DEVELOPMENT adapter prerequisite; full ticket open)" in graph
    assert "└─> C-03(PR #149 capability + PR #151 hardening)" in graph
    assert graph.count("| **no** |") >= 5
    assert (
        "| C-03 | PR #149 bounded DEVELOPMENT capability and PR #151 hardening accepted"
        in graph
    )
    assert "**yes, current slice; not protected/official/archive-eligible**" in graph


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


def test_hub_projects_only_development_receipt_and_future_contract_status() -> None:
    data = json.loads(_read("docs/development/carbon_hub/data/hub_data_v2.json"))
    current = data["current"]
    assert current["last_completed_ticket"]["id"] == "C-05"
    assert current["selected_ticket"]["id"] == "C-06"
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
    assert tickets["C-06"]["status"] == "in_progress"
    assert tickets["C-06"]["implementation_state"] == "candidate_implementation"
    assert "Selected" in tickets["C-06"]["current_stage"]
    for ticket_id in ("C-08", "C-09"):
        assert tickets[ticket_id]["status"] == "todo"
        assert tickets[ticket_id]["implementation_state"] == "unstarted"
        assert "not dependency-ready" in tickets[ticket_id]["current_stage"]
    assert "34518806217" in current["stage"]
    assert "standard-profile localnet" in current["stage"]
    assert "OWNER-C1-BURGERS-ALPHA-01" in current["stage"]
