"""Public D3 comparison only; no v3 reference rule is selected here."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.dev.battery import plating_band_v3_options as options


@pytest.fixture
def public_d3():
    values = {}
    for name, digest in options.INPUT_SHA256.items():
        raw = (options.D3 / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        values[name] = (
            [json.loads(line) for line in raw.splitlines()]
            if name.endswith(".jsonl")
            else json.loads(raw)
        )
    return values


def _analyze(files, bands=(0.1, 0.2, 0.4)):
    return options.analyze(
        files["labels-v2-r1.json"],
        files["labels.json"],
        files["records.jsonl"],
        sensitivity_bands_mv=list(bands),
    )


def test_public_d3_counts_and_missing_evidence_are_explicit(public_d3):
    result = _analyze(public_d3)
    assert result["source_counts"] == {"ev4": 77, "pdd": 695}
    assert result["v2_label_counts"] == {
        "FEASIBLE": 114,
        "INFEASIBLE": 447,
        "UNRESOLVED": 211,
    }
    assert result["mesh160_solved"] == 669
    assert result["mesh160_pending"] == 103
    assert result["draft_feasible_lost_under_v2"] == 46
    assert result["lost_with_40_80_160_rungs"] == 6
    assert result["lost_without_mesh80"] == 40
    assert result["richardson"]["additional_mesh80_needed_for_solved"] == 602
    assert result["richardson"]["achievable_band_mv"] is None
    assert result["richardson"]["recovered_of_46"] is None
    assert result["mesh320"]["successful_public_rungs"] == 0
    assert result["mesh320"]["achievable_band_mv"] is None
    assert result["mesh320"]["approved_cost"] is None
    # Every public ID has the same prefix, so this also tests source-field grouping.
    assert all(
        row["case_id"].startswith("ev4:")
        for row in public_d3["labels-v2-r1.json"]["rows"]
    )
    assert "case_id" not in json.dumps(result)
    assert "D-0000" not in json.dumps(result)


def test_stale_pre_v2_rule_is_refused_even_if_label_looks_valid(public_d3):
    files = copy.deepcopy(public_d3)
    files["labels-v2-r1.json"]["rows"][0]["rule"] = "m160-d3"
    with pytest.raises(options.AnalysisRefused, match="unregistered_v2_rule"):
        _analyze(files)


def test_wrong_source_is_refused_against_joined_draft(public_d3):
    files = copy.deepcopy(public_d3)
    row = next(
        row for row in files["labels-v2-r1.json"]["rows"] if row["rule"] == "m160-d3-r1"
    )
    row["source"] = "ev4" if row["source"] == "pdd" else "pdd"
    with pytest.raises(options.AnalysisRefused, match="draft_solved_mismatch"):
        _analyze(files)


def test_changed_v2_label_is_refused(public_d3):
    files = copy.deepcopy(public_d3)
    row = next(
        row for row in files["labels-v2-r1.json"]["rows"] if row["label"] == "FEASIBLE"
    )
    row["label"] = "INFEASIBLE"
    with pytest.raises(options.AnalysisRefused, match="v2_label_mismatch"):
        _analyze(files)


def test_incomplete_cost_coverage_is_refused(public_d3):
    files = copy.deepcopy(public_d3)
    files["records.jsonl"] = [
        row for row in files["records.jsonl"] if row["mesh"] != 80
    ]
    with pytest.raises(options.AnalysisRefused, match="cost_record_coverage"):
        _analyze(files)


def test_extrapolation_rung_tampering_is_refused(public_d3):
    files = copy.deepcopy(public_d3)
    files["labels.json"]["convergence_check"]["rows"][0]["extrapolated_mv"] += 0.1
    with pytest.raises(
        options.AnalysisRefused, match="convergence_extrapolation_mismatch"
    ):
        _analyze(files)


@pytest.mark.parametrize("band", [float("nan"), float("inf"), -0.1])
def test_nonfinite_or_negative_sensitivity_band_is_refused(public_d3, band):
    with pytest.raises(options.AnalysisRefused, match="source_or_sensitivity_contract"):
        _analyze(public_d3, (band,))


def test_cli_checks_source_digest_before_analysis(public_d3, tmp_path, monkeypatch):
    for name in options.INPUT_SHA256:
        (tmp_path / name).write_bytes((options.D3 / name).read_bytes())
    path = tmp_path / "labels-v2-r1.json"
    path.write_bytes(path.read_bytes() + b"\n")
    monkeypatch.setattr(options, "D3", tmp_path)
    with pytest.raises(options.AnalysisRefused, match="public_d3_digest_mismatch"):
        options.main(["--sensitivity-band-mv", "0.1"])
