"""Bounded measurement controls; none dispatch a research task or training."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess

import pytest

from scripts.dev import launchpad_offline_coverage as audit

SOURCE_COMMIT = "31c6fc76a6f2555183d9f9d7915a1f641ea14415"
ARTIFACT_SHA256 = "9fd6f49b059a6208ba626bfd7ddf19b22ca6c1752a5e562442b38098b93c864d"


def _assert_historical_source(value):
    assert value["source_commit"] == SOURCE_COMMIT
    assert len(value["source_files"]) == 14
    for name, digest in value["source_files"].items():
        original = subprocess.check_output(
            ["git", "show", f"{SOURCE_COMMIT}:{name}"], cwd=audit.ROOT
        )
        assert hashlib.sha256(original).hexdigest() == digest, name


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


@pytest.mark.parametrize("case", ["C4", "X3"])
def test_graph_combination_marker_control_cannot_be_mistaken_for_valid_graph_acceptance(
    case,
):
    from carbon.battery import (
        composed_graph,
        development_rebuild,
        level4_model,
        level4_worker,
    )
    from carbon.battery import level4_lowering as battery_lowering
    from carbon.level4 import allowlist, intake, staging, submission

    # S2 can compile metadata for a graph combination. The zero marker is
    # still not authenticated submission content and cannot build a model.
    found = audit.measure(case, "construction")
    assert found["status"] == "ACCEPTED"
    assert found["cli_exit_code"] == 0
    assert found["execution"] == "STATIC_COMPILE_ONLY"
    strategy = audit.strategies()[case]
    marker = audit.dc.compile(strategy)
    assert development_rebuild.uses_graph(marker.record)
    with pytest.raises(ImportError, match=level4_worker.BLOCKED):
        development_rebuild.build_in_process(marker.construction, marker.record)

    # A real public bundle supplies a positive control for the same boundary.
    manifest, files = battery_lowering.lower_recipe(
        audit.strategies()["C0"],
        allowlist.load(),
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    workspace = staging.workspace(submission.canonical(manifest), files)
    digest = submission.digest(manifest)
    assert staging.from_workspace(workspace, digest)
    with pytest.raises(staging.StagingCorrupt) as corrupt:
        staging.from_workspace(workspace, strategy["parameters"]["composition_graphs"])
    assert corrupt.value.kind == "FAILED_INFRA"
    with pytest.raises(ImportError, match="level4_staging_corrupt"):
        development_rebuild.build_in_process(
            marker.construction, marker.record, workspace
        )
    valid_strategy = copy.deepcopy(strategy)
    valid_strategy["parameters"]["composition_graphs"] = digest
    valid = audit.dc.compile(valid_strategy)
    model = development_rebuild.build_in_process(
        valid.construction, valid.record, workspace
    )
    assert isinstance(model, (level4_model.GraphModel, composed_graph.ComposedGraph))
    # Build only: no fit, train, reference or execution.


def test_uncalibrated_zero_forecast_is_reported_without_acceptance():
    found = audit.measure("C0", "forecast_resources")
    assert found["reply_status"] == "OK" and found["status"] == "RETURNED"
    assert "SUPPORT:UNRESOLVED" in found["limitations"]
    assert found["wall_seconds_band"] == [0.0, 0.0]
    assert "ZERO_BAND_IS_UNRESOLVED_PLACEHOLDER" in found["limitations"]
    assert "NO_RESOURCE_PREDICTION" in found["limitations"]
    assert not any(found["execution_allowance_used"].values())


def test_committed_measurements_have_pinned_source_and_complete_explicit_basis():
    artifact = audit.ROOT / audit.DIRECTORY / "MEASURED.json"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == ARTIFACT_SHA256
    value = json.loads(artifact.read_text(encoding="utf-8"))
    _assert_historical_source(value)
    expected = {
        (case, operation)
        for case in value["strategies"]
        for operation in (
            "construction",
            "dry_validate",
            "compile_strategy",
            "inspect_resources",
            "forecast_resources",
        )
    }
    rows = value["measurements"]
    assert len(rows) == len(expected) == value["basis"]["actual_calls"] == 55
    assert {(row["case"], row["operation"]) for row in rows} == expected
    assert all(row["ran"] is True for row in rows)
    assert all(
        row["command"]
        == (
            "python -m scripts.dev.launchpad_offline_coverage "
            f"--case {row['case']} --operation {row['operation']}"
        )
        for row in rows
    )
    assert all(
        row["scope"] == "UNVERIFIED_GRAPH_METADATA_ONLY"
        for row in rows
        if row["case"] in {"C4", "X3"}
    )
    unrun = value["unrun_matrix"]
    assert (
        len(unrun) == len({(row["change"], row["capability"]) for row in unrun}) == 240
    )
    assert all(row["ran"] is False and row["outcome"] == "HOST_BOUND" for row in unrun)
    assert value["b18"]["live_serving"] == "HOST_BOUND_UNVERIFIED"
    assert value["basis"]["training_runs"] == value["basis"]["host_runs"] == 0


@pytest.mark.parametrize("tamper", ["commit", "source_hash"])
def test_historical_source_binding_refuses_tampered_identity_or_hash(tamper):
    artifact = audit.ROOT / audit.DIRECTORY / "MEASURED.json"
    value = json.loads(artifact.read_text(encoding="utf-8"))
    if tamper == "commit":
        value["source_commit"] = "0" * 40
    else:
        value["source_files"]["carbon/battery/compile.py"] = "0" * 64
    with pytest.raises(AssertionError):
        _assert_historical_source(value)
