"""Synthetic Stage A summaries only; no operator, hidden, or solver data."""

import hashlib
import json
import math

import pytest

from scripts.dev.battery import stage_a_alignment as alignment


@pytest.fixture(autouse=True)
def _toy_registered_candidate(monkeypatch):
    """The real loader requires Git metadata unavailable in a Windows WSL worktree."""
    candidate = alignment.tuning.Candidate(
        id=alignment.CANDIDATE,
        weights={"a": 0.5, "q": 0.5},
        gate={"measure": "feasibility", "cutoff": 0.05},
    )
    monkeypatch.setattr(
        alignment.tuning,
        "load_registry",
        lambda *_args, **_kwargs: ({alignment.CANDIDATE: candidate}, "toy"),
    )


def _sha(letter):
    return "sha256:" + letter * 64


def _fixture(tmp_path):
    registry = alignment.REGISTRY.read_bytes()
    context = {
        "challenge": "battery-fastcharge-ageing-development-v1",
        "level": 0,
        "decision_measure": "toy_development_loss",
        "decision_panel_sha256": _sha("b"),
        "v3_panel_sha256": _sha("a"),
        "v3_registry_sha256": "sha256:" + hashlib.sha256(registry).hexdigest(),
    }
    members = []
    for name, exam, loss, leg in (
        ("bad", 0.1, 2.0, 0.4),
        ("middle", 0.2, 1.0, 0.6),
        ("good", 0.3, 0.0, 0.8),
    ):
        report = {
            "schema": alignment.V3_SCHEMA,
            "identity": {
                "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT",
                "job": "battery-q3-v8",
                "panel_sha256": context["v3_panel_sha256"],
                "registry_sha256": context["v3_registry_sha256"],
            },
            "recipe": {
                "member": name,
                "seed": 17,
                "recipe_digest": _sha("1"),
                "confirmation_sha256": _sha("e"),
            },
            "status": "SCORED",
            "a": leg,
            "q": leg,
            "g_feas": 0.0,
            "q3_regret": 1 / leg - 1,
            "raw_score": leg,
            "eligible": True,
            "gate_verdict": "PASS",
        }
        v3_path = tmp_path / f"{name}-v3.json"
        body = json.dumps(report, sort_keys=True).encode()
        v3_path.write_bytes(body)
        members.append(
            {
                "member": name,
                "recipe": name,
                "recipe_digest": _sha("1"),
                "seed": 17,
                "confirmation_sha256": _sha("e"),
                "practice": {
                    "state": "SCORED",
                    "score": exam,
                    "panel_sha256": _sha("d"),
                    "source_sha256": _sha("2"),
                },
                "exam": {
                    "state": "SCORED",
                    "score": exam,
                    "eligible": True,
                    "rule": "v2",
                    "rule_sha256": _sha("c"),
                    "pool_version": 1,
                    "device_class": "toy-cpu",
                    "source_sha256": _sha("3"),
                },
                "decision": {
                    "state": "RESOLVED",
                    "loss": loss,
                    "source_sha256": _sha("4"),
                },
                "v3_report": {
                    "path": v3_path.name,
                    "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                },
            }
        )
    manifest = {
        "schema": alignment.SCHEMA,
        "scope": alignment.SCOPE,
        "context": context,
        "members": members,
    }
    path = tmp_path / "stage-a-summary.json"
    _write(path, manifest)
    return path, manifest


def _write(path, manifest):
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_v2_v3_alignment_terms_and_recipe_practice_exam(tmp_path):
    path, _ = _fixture(tmp_path)
    first = alignment.analyze(path, draws=80, seed=7)
    assert first == alignment.analyze(path, draws=80, seed=7)
    cohort = first["cohorts"][0]
    assert cohort["status"] == "MEASURED"
    assert cohort["planned_members"] == cohort["matched_members"] == 3
    assert cohort["v2"]["alignment"] == {"tau_b": -1.0, "rho": -1.0}
    assert cohort["v3"]["alignment"] == {"tau_b": 1.0, "rho": 1.0}
    assert cohort["v3"]["term_alignment"]["accuracy_a"]["tau_b"] == 1.0
    assert cohort["v3"]["term_alignment"]["q3_q"]["rho"] == 1.0
    assert cohort["v3"]["term_alignment"]["g_feas_lower_better"]["rho"] is None
    assert {r["member"] for r in cohort["v2"]["divergent_members"]} == {"bad", "middle"}
    assert cohort["v3"]["divergent_members"] == []
    assert cohort["practice_vs_exam"]["rank_association"] == {"tau_b": 1.0, "rho": 1.0}
    assert len(cohort["practice_vs_exam"]["per_recipe"]) == 3
    assert cohort["v3"]["bootstrap_95_descriptive"]["tau_b"]["defined_draws"] > 0


def test_missing_v3_keeps_v2_measured_but_reference_failure_stops_it(tmp_path):
    path, manifest = _fixture(tmp_path)
    manifest["members"][0]["v3_report"] = None
    _write(path, manifest)
    cohort = alignment.analyze(path, draws=8)["cohorts"][0]
    assert cohort["status"] == "V2_ONLY"
    assert cohort["v2"]["alignment"]["tau_b"] == -1.0
    assert cohort["v3"] is None
    assert cohort["unmeasured_members"] == [
        {"member": "bad", "causes": ["v3:REPORT_MISSING"]}
    ]
    manifest["members"][0]["decision"] = {
        "state": "FAILED_INFRA",
        "loss": None,
        "source_sha256": _sha("4"),
    }
    _write(path, manifest)
    causes = alignment.analyze(path, draws=8)["cohorts"][0]["unmeasured_members"][0][
        "causes"
    ]
    assert "decision:FAILED_INFRA" in causes
    assert alignment.analyze(path, draws=8)["cohorts"][0]["status"] == "UNMEASURED"


def test_refuses_extra_fields_digest_change_and_escape(tmp_path):
    path, manifest = _fixture(tmp_path)
    manifest["members"][0]["hidden_case_id"] = "must-not-enter-summary"
    _write(path, manifest)
    with pytest.raises(alignment.Refused, match="member_shape"):
        alignment.analyze(path, draws=4)
    del manifest["members"][0]["hidden_case_id"]
    manifest["members"][0]["v3_report"]["sha256"] = _sha("f")
    _write(path, manifest)
    with pytest.raises(alignment.Refused, match="v3_file_digest_mismatch"):
        alignment.analyze(path, draws=4)
    manifest["members"][0]["v3_report"]["path"] = "../outside.json"
    _write(path, manifest)
    with pytest.raises(alignment.Refused, match="v3_file_outside_input"):
        alignment.analyze(path, draws=4)


def test_v3_report_cannot_smuggle_case_level_fields(tmp_path):
    path, manifest = _fixture(tmp_path)
    entry = manifest["members"][0]["v3_report"]
    v3_path = tmp_path / entry["path"]
    report = json.loads(v3_path.read_text(encoding="utf-8"))
    report["hidden_cases"] = ["forbidden"]
    body = json.dumps(report, sort_keys=True).encode()
    v3_path.write_bytes(body)
    entry["sha256"] = "sha256:" + hashlib.sha256(body).hexdigest()
    _write(path, manifest)
    with pytest.raises(alignment.Refused, match="v3_report_fields"):
        alignment.analyze(path, draws=4)


def test_pool_and_practice_panel_comparability(tmp_path):
    path, manifest = _fixture(tmp_path)
    manifest["members"][0]["exam"]["pool_version"] = 2
    _write(path, manifest)
    report = alignment.analyze(path, draws=4)
    assert len(report["cohorts"]) == 2
    assert sorted(row["matched_members"] for row in report["cohorts"]) == [1, 2]
    assert sorted(row["status"] for row in report["cohorts"]) == [
        "MEASURED",
        "UNMEASURED",
    ]
    manifest["members"][0]["exam"]["pool_version"] = 1
    manifest["members"][0]["practice"]["panel_sha256"] = _sha("f")
    _write(path, manifest)
    cohort = alignment.analyze(path, draws=4)["cohorts"][0]
    assert cohort["status"] == "MEASURED"
    assert cohort["practice_vs_exam"]["rank_association_status"] == (
        "DIFFERENT_PRACTICE_PANELS"
    )
    assert cohort["practice_vs_exam"]["rank_association"]["tau_b"] is None


def test_gate_failure_is_separate_from_soft_contributions(tmp_path):
    path, manifest = _fixture(tmp_path)
    good = manifest["members"][2]
    v3_path = tmp_path / good["v3_report"]["path"]
    report = json.loads(v3_path.read_text(encoding="utf-8"))
    report.update(
        {
            "g_feas": 0.1,
            "eligible": False,
            "gate_verdict": "FAIL",
            "status": "INELIGIBLE",
        }
    )
    body = json.dumps(report, sort_keys=True).encode()
    v3_path.write_bytes(body)
    good["v3_report"]["sha256"] = "sha256:" + hashlib.sha256(body).hexdigest()
    _write(path, manifest)
    cohort = alignment.analyze(path, draws=10)["cohorts"][0]
    assert cohort["status"] == "MEASURED"
    assert cohort["v3"]["alignment"]["tau_b"] < 1
    pair = cohort["v3"]["divergent_members"][0]["inversions"][0]
    assert pair["g_feas_gate"]["better_decider"] == "FAIL"
    assert math.isfinite(pair["accuracy_log_delta"])


def test_v2_exam_ineligibility_is_ranked_below_passers_without_a_score(tmp_path):
    path, manifest = _fixture(tmp_path)
    exam = manifest["members"][0]["exam"]
    exam["eligible"] = False
    exam["score"] = None
    _write(path, manifest)
    cohort = alignment.analyze(path, draws=8)["cohorts"][0]
    assert cohort["status"] == "MEASURED"
    assert cohort["practice_vs_exam"]["rank_association_status"] == (
        "EXAM_INELIGIBILITY"
    )
    assert cohort["practice_vs_exam"]["rank_association"]["rho"] is None
    assert cohort["practice_vs_exam"]["per_recipe"][0]["mean_exam_score"] is None
