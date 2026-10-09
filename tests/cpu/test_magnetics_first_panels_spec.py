"""Static proposal/arithmetic checks only. No model, package build or solver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SPECS = ROOT / "docs/development/challenge_pipeline/magnetics-first-panels"


@pytest.fixture
def proposal():
    return json.loads((SPECS / "panels.json").read_text(encoding="utf-8"))


def test_no_adoption_or_dispatch_from_spec(proposal):
    assert proposal["schema"] == "carbon.magnetics-first-panels.proposal.v1"
    assert proposal["status"] == "SPECIFIED_NOT_APPROVED"
    assert proposal["dispatch_ready"] is False
    assert set(proposal["approval"].values()) == {"HUMAN_INPUT"}
    assert proposal["maturity"]["customer_confirmed"] is False
    assert proposal["maturity"]["reference_adequacy"] == "NOT_DEMONSTRATED"
    assert proposal["maturity"]["C1"] == "UNMEASURED"
    assert proposal["budget"]["enforcement"] == "NOT_IMPLEMENTED"
    assert proposal["law"]["Q"] == "FIXED_PUBLIC_DIAGNOSTIC_SCHEDULE"
    assert proposal["law"]["P"] != proposal["law"]["Q"]
    assert proposal["law"]["w"] == "HUMAN_INPUT"


@pytest.mark.parametrize("name", ["solenoid_pole", "planar_transformer"])
def test_named_designs_and_bounds(proposal, name):
    family = proposal["families"][name]
    rows = family["designs"]
    assert len(rows) == 10
    assert len({row["id"] for row in rows}) == 10
    assert len({tuple(row["parameters"]) for row in rows}) == 10
    assert family["registered_status"] == "NORMALIZED_PROPOSAL_ONLY_ANCHOR_UNBOUND"
    for row in rows:
        assert len(row["parameters"]) == len(family["fields"])
        for value, bound in zip(row["parameters"], family["bounds"]):
            if isinstance(value, str):
                assert value in bound
                assert value.count("P") == value.count("S") == 2
            else:
                assert bound[0] <= value <= bound[1]
    assert family["primary_cases"] == len(rows) * len(proposal["strata"])
    assert family["refined_cases"] == len(family["refined_designs"]) * len(
        proposal["strata"]
    )
    assert set(family["refined_designs"]) <= {row["id"] for row in rows}
    assert len(family["witness_pairs"]) * 2 == family["witness_case_allocations"]
    for pair in family["witness_pairs"]:
        assert pair["design"] in {row["id"] for row in rows}
        assert pair["stratum"] in proposal["strata"]


@pytest.mark.parametrize("name", ["solenoid_pole", "planar_transformer"])
def test_complete_excitation_and_refinement_cost_not_one_field(proposal, name):
    family = proposal["families"][name]
    fields = family["fields_per_complete_case"]
    extra = 0
    if name == "solenoid_pole":
        assert (
            fields
            == len(family["stroke_fractions"]) * len(family["current_fractions"])
            == 27
        )
        virtual = family["virtual_work"]
        extra = len(virtual["stroke_fractions"]) * len(virtual["probe_multipliers"])
        assert extra == virtual["extra_fields_per_refined_case"] == 12
        assert virtual["epsilon"] == "HUMAN_INPUT"
    else:
        assert fields == len(family["excitation_states"]) == 5
    coarse = (
        family["primary_cases"]
        + family["control_case_allocations"]
        + family["witness_case_allocations"]
        + family["failed_case_allocations"]
    )
    refined_fields = family["refined_cases"] * (fields + extra)
    assert family["max_field_system_allocations"] == coarse * fields + refined_fields
    equivalents = coarse + refined_fields / fields * family["refined_cost_multiplier"]
    assert family["coarse_complete_case_equivalents"] == pytest.approx(equivalents)


@pytest.mark.parametrize("name", ["solenoid_pole", "planar_transformer"])
def test_budget_all_scopes_and_high_case_honesty(proposal, name):
    budget, family = proposal["budget"], proposal["families"][name]
    factor = budget["rate_eur_node_hour"] * budget["tax_multiplier"]
    bills = [
        factor
        * (
            budget["setup_idle_mesh_fit_hours"]
            + family["coarse_complete_case_equivalents"]
            * cpu
            * budget["elapsed_cpu_ratio"]
        )
        + budget["other_cash_reserve_eur"]
        for cpu in family["C1_cpu_hours_hypothesis"]
    ]
    assert family["cost_eur_hypothesis"] == pytest.approx(bills)
    assert family["complete_at_high_hypothesis_within_cash_cap"] is (bills[-1] <= 20)
    assert bills[0] < bills[1] < bills[2]
    assert (
        factor * budget["node_wall_cap_hours"] + budget["other_cash_reserve_eur"] < 20
    )
    assert (
        budget["aggregate_if_both_selected_eur"]
        == 2 * budget["cap_eur_per_family"]
        == 40
    )
    assert budget["solver_threads"] == budget["worker_processes"] == 1
    assert budget["gpu"] is budget["automatic_retries"] is False
    assert budget["human_labour"] == "NOT_PRICED"


def test_planar_prefix_and_3d_not_free_or_qualified(proposal):
    family = proposal["families"]["planar_transformer"]
    assert family["prefix_is_subset_not_extra"] is True
    assert set(family["measured_prefix_designs"]) <= {
        row["id"] for row in family["designs"]
    }
    assert family["prefix_stratum"] in proposal["strata"]
    assert family["later_3D_witness_jobs"] == 4
    assert family["later_3D_cost"] == "UNMEASURED_OUTSIDE_20_EUR_SLICE_PANEL"
    assert family["actual_device_feasibility"] == "UNRESOLVED_SLICE_ONLY"
    assert "3D_end_turns" in family["not_checked"]
    assert "thermal_hotspot" in family["not_checked"]


def test_reuse_exact_inputs_and_human_authority(proposal):
    source = proposal["source"]
    assert source["main"] == "432d22b786a7341de788bc8b1206526849f3a31f"
    assert source["discovery_head"] == "536a2716bd24a41751a1d382fca40038ff1384ae"
    dockerfile = (ROOT / "scripts/dev/motor/reference/Dockerfile").read_text(
        encoding="utf-8"
    )
    for token in (
        "getdp-3.5.0",
        "gmsh-4.15.2",
        "bca39450cc6f33feac27bff1c8c3e47bb200f44679b0f03d85820def84ef1444",
    ):
        assert token in dockerfile
    for filename in ("README.md", "solenoid-pole.md", "planar-transformer.md"):
        text = (SPECS / filename).read_text(encoding="utf-8")
        assert "HUMAN_INPUT" in text
        assert "baseline" in text.lower()
        assert "not approved" in text.lower() or "NOT_APPROVED" in text


def test_physical_dimension_and_energy_seams_are_not_hidden():
    sol = (SPECS / "solenoid-pole.md").read_text(encoding="utf-8")
    planar = (SPECS / "planar-transformer.md").read_text(encoding="utf-8")
    common = (SPECS / "README.md").read_text(encoding="utf-8")
    assert "Fclosing=-dWco/ds" in sol
    assert "not use 0.5*B*H" in sol
    assert "not proof" in sol
    assert "not measured operating-frequency" in planar
    assert "2D EUR20 estimate" in common
    assert "independent" in planar
    assert "separately priced" in common
