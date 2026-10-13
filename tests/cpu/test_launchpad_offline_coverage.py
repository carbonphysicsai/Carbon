"""Bounded measurement controls; none dispatch a research task or training."""

from __future__ import annotations

import pytest

from scripts.dev import launchpad_offline_coverage as audit


def test_callbacks_fail_closed_before_any_execution():
    with pytest.raises(RuntimeError, match="never dispatches execution"):
        audit.no_execution("practice")


def test_current_toolbox_accepts_base_but_names_development_field_refusals():
    base = audit.measure("C0", "compile_strategy")
    assert base["status"] == "ACCEPTED"
    loss = audit.measure("C1", "compile_strategy")
    assert loss["status"] == "REFUSED"
    assert loss["issues"]
    assert {issue["code"] for issue in loss["issues"]} == {
        "strategy.parameter_shape_invalid"
    }
    assert loss["issues"][0]["path"] == ["parameters"]
    assert not any(base["execution_allowance_used"].values())
    assert not any(loss["execution_allowance_used"].values())


def test_cross_level_cli_is_executed_with_budget_gate_and_returns_composed(monkeypatch):
    actual_run = audit.subprocess.run
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return actual_run(argv, **kwargs)

    monkeypatch.setattr(audit.subprocess, "run", run)
    found = audit.measure("X2", "construction")
    assert found["status"] == "ACCEPTED" and found["rebuild"] == "composed"
    assert found["cli_exit_code"] == 0
    assert len(calls) == 1
    assert calls[0][1:3] == ["-m", "carbon.reconstruction.development_composition"]
    assert "--no-budget" not in calls[0]


def test_graph_combination_marker_control_cannot_be_mistaken_for_valid_graph_acceptance():
    found = audit.measure("X3", "construction")
    assert found["status"] == "REFUSED"
    assert found["code"] == "construction_rebuild_unavailable"
    assert any("composition_graphs" in issue[1] for issue in found["issues"])
    assert found["cli_exit_code"] == 2


def test_uncalibrated_zero_forecast_is_reported_without_acceptance():
    found = audit.measure("C0", "forecast_resources")
    assert found["reply_status"] == "OK" and found["status"] == "RETURNED"
    assert "SUPPORT:UNRESOLVED" in found["limitations"]
    assert found["wall_seconds_band"] == [0.0, 0.0]
    assert "ZERO_BAND_IS_UNRESOLVED_PLACEHOLDER" in found["limitations"]
    assert "NO_RESOURCE_PREDICTION" in found["limitations"]
    assert not any(found["execution_allowance_used"].values())
