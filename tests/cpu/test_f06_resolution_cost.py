"""Offline specification arithmetic only; no physical evidence or solver."""

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs/development/challenge_pipeline/solver-package-specs"
DATA = json.loads(
    (DIR / "f06-resolution-cost/analysis.json").read_text(encoding="utf-8")
)


def cpu(spacing):
    return 4 * (30 / spacing) ** 4


def test_no_measurement_adoption_or_execution_claim():
    assert DATA["maturity"] == "SPECIFIED"
    for key in (
        "executable",
        "solver_runs_authorised",
        "spend_authorised",
        "protected_data_access",
    ):
        assert DATA[key] is False
    for key in (
        "coarsest_adequate_grid_nm",
        "measured_cpu_h",
        "accepted_image_digest",
        "adopted_grid_nm",
    ):
        assert DATA[key] is None
    assert DATA["cost_status"] == "UNMEASURED"
    assert DATA["proof_policy"]["rank_overlap"] == "UNRESOLVED"
    assert DATA["proof_policy"]["runtime_ids_activated"] == []
    assert not DATA["proof_policy"]["missing_truth_is_none_feasible"]


def test_lower_bound_and_larger_domain_memory_are_not_rss_proof():
    memory = DATA["memory"]
    assert not memory["scenario_is_upper_bound"]
    assert memory["ccx63_advertised_ram_bytes"] / 2**30 == pytest.approx(178.813934)
    document = (DIR / "f06-resolution-cost/README.md").read_text(encoding="utf-8")
    for h, expected in (
        (40, "0.80 / 1.68"),
        (30, "1.90 / 3.97"),
        (10, "51.23 / 107.29"),
    ):
        values = [n * (10 / h) ** 3 * 96 / 2**30 for n in memory["bare_cells_at_10nm"]]
        assert " / ".join(f"{value:.2f}" for value in values) == expected
        assert expected in document
    scenario = 1200000000 * 120 / 2**30 * 2.5 * 1.5
    assert scenario > memory["ccx63_advertised_ram_bytes"] / 2**30


def test_witnesses_are_complete_and_do_not_rescue_failed_primary_bank():
    assumptions = DATA["cost_assumptions"]
    assert assumptions["witness_rows"] == 45
    assert not assumptions["throughput_measured"]
    assert not assumptions["bank_law_adopted"]
    for row in DATA["worked_examples"]:
        throughput = row["effective_throughput"]
        primary = 20 + 1.37 * 256 * cpu(row["primary_nm"]) / throughput
        assert primary == pytest.approx(row["primary_eur"])
        for h in (20, 10):
            witness_price = 1.37 * cpu(h) / throughput
            count = math.floor(max(0, 100 - primary) / witness_price)
            assert count == row[f"witnesses_{h}nm"]
            if primary <= 100:
                assert primary + count * witness_price <= 100
                assert primary + (count + 1) * witness_price > 100
            else:
                assert count == 0


def test_scaling_and_ladder_cost_are_hypotheses():
    assert not DATA["cpu_hypothesis"]["measured_quantiles"]
    assert not DATA["cpu_hypothesis"]["broadband_parity_proven"]
    assert cpu(20) == pytest.approx(20.25)
    assert cpu(10) == 324
    assert 8 * (cpu(30) + cpu(20)) + 2 * cpu(10) == 842


def test_local_links_and_required_decision_boundaries():
    import re

    path = DIR / "f06-resolution-cost/README.md"
    document = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", document):
        if "://" not in target:
            assert (path.parent / target.split("#")[0]).is_file(), target
    for statement in (
        "COARSEST_ADEQUATE_GRID_NOT_DEMONSTRATED",
        "UNRESOLVED",
        "not a total error certificate",
        "not a second customer reframe",
        "No safety or buyer limit is relaxed",
    ):
        assert statement in document
