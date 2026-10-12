"""Public-only score-leg audit: toy results, no solver or reference files."""

import pytest

from scripts.dev.battery.score_leg_audit_public import audit


def _fixture():
    names = ["mlp-a-s0", "mlp-b-s0", "mlp-c-s0", "mlp-d-s0", "control-bad"]
    components = {
        name: {
            "eligible": True,
            "E": float(i),
            "E_important": float(i),
            "decision": {"score": 1 / (i + 1)},
        }
        for i, name in enumerate(names)
    }
    decisions = {
        name: {
            f"D-{j}": {
                "split": "development",
                "outcome": {
                    "decision_loss": float(i + j),
                    "kind": (
                        "SELECTED_INFEASIBLE"
                        if i == 3 and j == 1
                        else "SELECTED_FEASIBLE"
                    ),
                },
            }
            for j in range(3)
        }
        for i, name in enumerate(names)
    }
    manifest = {
        "levels": [
            {"pattern": "^control-", "level": None},
            {"pattern": "^mlp-", "level": 0},
        ],
        "roles": {
            "known_bad": ["control-bad"],
            "adversarial": [],
        },
    }
    return {
        "claims": {"evidence_class": "PUBLIC_SYNTHETIC_DEVELOPMENT"},
        "components": components,
        "decisions": decisions,
    }, manifest


def test_public_audit_uses_one_mask_and_reuses_proof_statistics():
    results, manifest = _fixture()
    first = audit(results, manifest, bootstrap=30)
    assert first == audit(results, manifest, bootstrap=30)
    assert first["common_resolved_development_questions"] == 3
    assert first["pools"]["L0"] == first["pools"]["pooled"]
    pool = first["pools"]["L0"]
    assert pool["primary_members"] == 4
    assert pool["measures"]["a"]["tau"] == pytest.approx(1.0)
    assert pool["measures"]["SELECTED_INFEASIBLE"]["status"] == "MEASURED"
    assert pool["measures"]["p"]["status"] == "UNMEASURED"
    assert pool["measures"]["q"]["status"] == "UNMEASURED"
    assert pool["measures"]["feasibility"]["status"] == "UNMEASURED"
    assert pool["outcome_shares"]["SELECTED_INFEASIBLE"] == pytest.approx(1 / 12)
    assert pool["value_ceiling"]["status"] == "MEASURED"
    assert first["pools"]["L1"]["status"] == "NOT_MEASURABLE"


def test_audit_refuses_non_public_result_and_missing_common_reference():
    results, manifest = _fixture()
    results["claims"]["evidence_class"] = "SEALED"
    with pytest.raises(ValueError, match="public_ev4_evidence_required"):
        audit(results, manifest, bootstrap=5)
    results["claims"]["evidence_class"] = "PUBLIC_SYNTHETIC_DEVELOPMENT"
    results["decisions"]["mlp-a-s0"]["D-0"]["outcome"]["decision_loss"] = None
    results["decisions"]["mlp-a-s0"]["D-1"]["outcome"]["decision_loss"] = None
    results["decisions"]["mlp-a-s0"]["D-2"]["outcome"]["decision_loss"] = None
    with pytest.raises(ValueError, match="no_common_resolved_development_mask"):
        audit(results, manifest, bootstrap=5)


def test_missing_primary_measure_is_never_silently_dropped():
    results, manifest = _fixture()
    results["components"]["mlp-b-s0"]["E"] = None
    report = audit(results, manifest, bootstrap=5)
    assert report["pools"]["L0"]["measures"]["a"]["status"] == "UNMEASURED"
    assert report["pools"]["L0"]["primary_members"] == 4
