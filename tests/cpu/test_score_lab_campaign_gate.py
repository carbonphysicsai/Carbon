"""Development-only control checks for OPT-15c."""

from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_gate
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "Business/research/value-metric-audit/results.json"
STRESS = ROOT / "Business/research/value-metric-v2-stress/results.json"
TOY = {
    "space": "small-grid",
    "optima": "multi",
    "constraint": "tight",
    "shift": "nominal",
    "verification_cost_ASSUMPTION": 0.2,
}


def test_public_and_toy_controls_pass_on_stated_development_evidence():
    result = campaign_gate.run(
        audit_path=AUDIT,
        stress_path=STRESS,
        problem=TOY,
        questions_per_side=8,
        cap=3,
    )
    assert result["status"] == "CONTROL_PASS"
    assert result["public"]["abstain_rank"] == [2, 2, 100]
    assert result["public"]["capture"] == 1.0
    assert result["toy"]["abstain_rank"] == [1, 14]
    assert result["toy"]["finite_grid_optimum_capture"] == 1.0
    assert result["toy"]["priced_questions"] == 4


def test_toy_gate_stops_if_cheap_arm_misses_finite_grid_optimum():
    altered = {**TOY, "constraint": "loose"}
    result = campaign_gate.run(
        audit_path=AUDIT,
        stress_path=STRESS,
        problem=altered,
        questions_per_side=8,
        cap=3,
    )
    assert result["status"] == "CONTROL_FAIL_STOP_CAMPAIGN"


def test_public_gate_rejects_changed_recorded_rank():
    import json

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    stress = json.loads(STRESS.read_text(encoding="utf-8"))
    audit["historical"]["ev5"]["verification"]["always_abstain_rank_against_real"][
        "best"
    ] = 1
    with pytest.raises(LabRefused, match="campaign_abstain_public_rank_mismatch"):
        campaign_gate._public_controls(audit, stress)


def test_public_gate_rejects_changed_capture():
    import json

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    stress = json.loads(STRESS.read_text(encoding="utf-8"))
    stress["primary"]["k3-c0.1"]["families"]["nominal"][
        "bilinear_ceiling_capture"
    ] = 0.5
    with pytest.raises(LabRefused, match="campaign_cheap_public_capture_mismatch"):
        campaign_gate._public_controls(audit, stress)
