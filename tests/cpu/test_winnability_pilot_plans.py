"""Pilot documents and arithmetic only; no fit, solve, grant or qualification."""

import json
import math
from pathlib import Path

import pytest

from carbon.design_search import equal_budget as eb

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/development/challenge_pipeline/challenge-factory/pilots"
DATA = json.loads((FOLDER / "plans.json").read_text(encoding="utf-8"))
ROWS = {row["id"]: row for row in DATA["plans"]}


def test_eight_proposals_are_not_dispatch_or_earned_winnability():
    assert set(ROWS) == {
        "f02",
        "motor",
        "cooling-cell",
        "solenoid-pole",
        "seal-gland",
        "connector-contact-spring",
        "planar-transformer",
        "bolted-joint",
    }
    assert DATA["execution_performed"] is DATA["dispatch_authorized"] is False
    assert DATA["spend_usd"] == 0 and DATA["thresholds"] == "HUMAN_INPUT"
    assert DATA["ranking"]["dispatch_order_adopted"] is False
    assert "floors are zero" in DATA["ranking"]["meaning"]
    for row in ROWS.values():
        assert row["runnable_now"] is row["dispatch_authorized"] is False
        assert row["thresholds"] == "HUMAN_INPUT"
        assert row["image_presence"] == "UNKNOWN_NO_OPERATOR_QUERY"
        assert row["gaps"] and row["model_recipe"].startswith("Existing")
        assert row["fit_cpu_hours_cap"] == 4
        assert row["new_reference_attempts_cap"] == sum(
            row[k]
            for k in (
                "new_primary",
                "new_refined",
                "new_control",
                "new_failed",
                "new_3d_witness_jobs",
            )
        )
        assert (FOLDER / (row["id"] + ".md")).is_file()
        assert all((ROOT / source).is_file() for source in row["refs"])


@pytest.mark.parametrize("row", DATA["plans"], ids=ROWS)
def test_whole_pod_lifecycle_caps_and_probe_are_counted(row):
    host = DATA["host"]
    assert host["vcpus"] == 32 and host["memory_gb"] == 64
    assert host["terminate_not_stop"] and host["quote_capacity_enforcer_required"]
    cents = math.ceil(
        row["wall"] * 60 * host["inclusive_usd_per_hour_ceiling"] * 100 / 60
    )
    assert row["usd_cap"] == pytest.approx(cents / 100 + 0.4)
    assert row["allocated_vcpu_hours_cap"] == row["wall"] * 32
    assert row["cpu"] <= row["allocated_vcpu_hours_cap"]
    assert row["probe_lifecycle_minutes"] / 60 <= row["wall"]
    probe = row["probe_lifecycle_minutes"] / 60 * 1.2 + 0.4
    assert row["probe_usd_cap"] == pytest.approx(probe)
    assert row["probe_usd_cap"] <= row["usd_cap"]
    assert max(row["expected"]) <= row["cpu"]
    assert row["expected_wall_hours_serial_assumption"] == pytest.approx(
        [value + 1 for value in row["expected"]], abs=1e-6
    )


def test_conditional_information_order_is_reproducible_not_an_adopted_score():
    for row in ROWS.values():
        assert row["priority"] == pytest.approx(
            3 * row["factor"][1] / row["usd_cap"], abs=1e-6
        )
    order = sorted(ROWS.values(), key=lambda row: -row["priority"])
    assert [row["rank"] for row in order] == list(range(1, 9))
    assert order[0]["id"] == "f02"
    assert "NOT_SCIENTIFIC_SCORE_OR_ROI" in DATA["ranking"]["kind"]


def test_missing_routes_and_kits_are_not_aliased_to_other_families():
    missing = {
        "solenoid-pole",
        "seal-gland",
        "planar-transformer",
        "connector-contact-spring",
    }
    for name, row in ROWS.items():
        if name in missing:
            assert row["route"] is None and name not in eb.CHALLENGE_ROUTES
            assert row["budget_status"] == "MISSING_ROUTE_AND_REGISTRATION"
        else:
            assert row["route"] == name and name in eb.CHALLENGE_ROUTES
        if name not in {"motor", "f02"}:
            assert row["model_kit_status"] == "NOT_IN_CARBON_ARM_KITS"


def test_reference_counts_keep_full_cases_and_histories():
    for name in (
        "solenoid-pole",
        "seal-gland",
        "connector-contact-spring",
        "planar-transformer",
        "bolted-joint",
    ):
        row = ROWS[name]
        assert row["train_records"] == row["train_geometries"] * row["strata"]
        assert row["heldout_records"] == row["heldout_geometries"] * row["strata"]
        assert row["new_primary"] == row["train_records"] + row["heldout_records"]
        equivalents = row["new_primary"] + row["new_control"] + row["new_failed"]
        equivalents += row["new_refined"] * (3 if name == "solenoid-pole" else 2)
        high = {
            "solenoid-pole": 0.12,
            "seal-gland": 0.15,
            "connector-contact-spring": 0.25,
            "planar-transformer": 0.20,
            "bolted-joint": 0.24,
        }[name]
        assert row["expected"][-1] == pytest.approx(equivalents * high + 8)
    assert ROWS["bolted-joint"]["strata"] == 4
    assert ROWS["f02"]["heldout_records"] == 384
    assert ROWS["f02"]["train_records"] == 8 * 24
    assert ROWS["motor"]["train_records"] == 16 * 11
    assert ROWS["motor"]["heldout_records"] == 12 * 11
    assert ROWS["motor"]["new_primary"] + ROWS["motor"]["new_refined"] == 6
    assert (
        ROWS["planar-transformer"]["expected_time_status"]
        == "SLICE_ONLY_PLUS_UNMEASURED_3D"
    )
    assert (
        "Four additional physical3D witness jobs"
        in ROWS["planar-transformer"]["reference"]
    )


def test_exact_report_readers_and_scope_are_documented():
    text = (FOLDER / "README.md").read_text(encoding="utf-8")
    for field in (
        "mean_pointwise_error",
        "decision_agreement_fraction",
        "paired_model_minus_cheap_improvement",
        "paired_bootstrap_ci",
        "finite_bank_mean_mlp_regret_conditional",
        "mlp_feasible_pick_fraction",
    ):
        assert field in text
    for boundary in (
        "HUMAN_INPUT",
        "No solves",
        "whole-minute",
        "Terminate, do not stop",
        "PUBLIC_HELDOUT",
        "three extra solves",
        "two-refinement-band",
    ):
        assert boundary in text
    for name in ("seal-gland", "connector-contact-spring"):
        assert "HUMAN_INPUT" in ROWS[name]["ranges"]
    assert "<=5%" in ROWS["motor"]["buyer"] and "peak12 N m" in ROWS["motor"]["buyer"]
    assert "Point C is excluded" in ROWS["cooling-cell"]["notes"]
