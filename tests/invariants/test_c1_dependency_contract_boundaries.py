"""Fail-closed checks for the post-C-EP2 C1 dependency contracts."""

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
        (".agent/tickets/C-03_isolated_reconstruction_worker.md", "C-03"),
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


def test_only_bounded_development_input_acquisition_ticket_is_selected() -> None:
    wave = _read(".agent/WAVE.md")
    wave_c = _read(".agent/WAVE_C.md")
    graph = _read(".agent/plans/C1_DEPENDENCY_GRAPH.md")
    for record in (wave, wave_c):
        assert "**Selected ticket:** C-EP3 — `in_progress`" in record
        assert "**Active ticket:** C-EP3" in record
        assert "**Next selected ticket:** none" in record
    assert "No real-vertical implementation ticket is dependency-ready" in graph
    assert "no real-vertical or Variant-B implementation ticket is selected" in graph
    assert "C-EP1 ─> C-EP2(done measurement/replay only; no sharing runtime)" in graph
    assert (
        "C-EP2 + C-AUTH1 ─> C-EP3(selected input acquisition/public component probe)"
        in graph
    )
    assert graph.count("| **no** |") >= 10


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
    assert "Until those source/interface facts are supplied" in c02
    assert "C-03 wraps C-02's actual authorized JAX adapter" in c03
    assert "C-EA2" in c09
    assert "synthetic-archive" in c09


def test_hub_projects_only_development_acquisition_selection_and_future_contract_status() -> (
    None
):
    data = json.loads(_read("docs/development/carbon_hub/data/hub_data_v2.json"))
    current = data["current"]
    assert current["last_completed_ticket"]["id"] == "C-EP2"
    assert current["selected_ticket"]["id"] == "C-EP3"
    assert current["next_selected_ticket"] is None
    tickets = {ticket["id"]: ticket for ticket in data["tickets"]}
    assert tickets["C-EP1"]["status"] == "done"
    assert tickets["C-EP2"]["status"] == "done"
    assert tickets["C-EP3"]["status"] == "in_progress"
    assert "shared membership" in tickets["C-EP3"]["does_not"]
    for ticket_id in ("C-03", "C-08", "C-09"):
        assert tickets[ticket_id]["status"] == "todo"
        assert tickets[ticket_id]["implementation_state"] == "unstarted"
        assert "not dependency-ready" in tickets[ticket_id]["current_stage"]
    assert "34518806217" in current["stage"]
    assert "standard-profile disposable v445 localnet" in current["stage"]
