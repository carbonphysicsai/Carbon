"""Toy-only checks of the development v3 input collector."""

import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from carbon.battery.value import score_tuning as tuning
from scripts.dev.battery import v3_score_inputs as v3


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True
    )


def test_panel_must_be_committed_clean_and_in_development(tmp_path):
    base = tmp_path / "docs/development/evidence/v3-score-inputs"
    base.mkdir(parents=True)
    panel = base / "panel.json"
    panel.write_text("{}")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Toy")
    _git(tmp_path, "config", "user.email", "toy@example.invalid")
    with pytest.raises(v3.Refused, match="panel_not_committed_clean"):
        v3._registered_panel(tmp_path, panel)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "register toy panel")
    assert v3._registered_panel(tmp_path, panel) == panel
    panel.write_text('{"changed": true}')
    with pytest.raises(v3.Refused, match="panel_not_committed_clean"):
        v3._registered_panel(tmp_path, panel)
    with pytest.raises(v3.Refused, match="development_path_required"):
        v3._registered_panel(tmp_path, tmp_path / "hidden/panel.json")


def test_reference_digest_and_path_fail_closed(tmp_path):
    good = b'{"case_id":"toy"}\n'
    (tmp_path / "references.jsonl").write_bytes(good)
    entry = {"path": "references.jsonl", "sha256": "sha256:" + hashlib.sha256(good).hexdigest()}
    assert v3._file(tmp_path, entry)[1] == good
    with pytest.raises(v3.Refused, match="file_digest_mismatch"):
        v3._file(tmp_path, {**entry, "sha256": "sha256:" + "0" * 64})
    with pytest.raises(v3.Refused, match="development_path_required"):
        v3._file(tmp_path, {**entry, "path": "../hidden.jsonl"})


def _toy_evaluation(monkeypatch, g_feas=0.0):
    from carbon.battery.value import quiz

    monkeypatch.setattr(quiz, "q3_grid", lambda contract, scenario: [{"case_id": "q3"}])
    monkeypatch.setattr(v3.exam, "_finite_shape", lambda outputs, shapes: outputs == {"toy": 1})
    monkeypatch.setattr(v3.PublicMaterial, "load", lambda root: SimpleNamespace(ocv_soc=[0, 1], ocv_v=[3, 4]))
    monkeypatch.setattr(v3, "frozen_calibration", lambda root: (object(), {}))
    monkeypatch.setattr(v3.sc, "components", lambda *args: {"eligible": True, "E": 0.25, "E_important": None})
    monkeypatch.setattr(v3.tuning, "false_feasible_rate", lambda *args: g_feas)
    monkeypatch.setattr(v3, "_q3_outcomes", lambda *args: [{"kind": "SELECTED_FEASIBLE", "decision_loss": 1.0}])
    candidate = tuning.Candidate(
        "G-FEAS/A-Q@0.05", weights={"a": 0.5, "q": 0.5},
        gate={"measure": "feasibility", "cutoff": 0.05},
    )
    refs = {"screen": {"status": "OK", "inputs": {"soc0": 0.5}, "outputs": {"toy": 1}}}
    settled = {"q3": {"status": "OK", "outputs": {"toy": 1}}}
    predictions = {"screen": {"toy": 1}, "q3": {"toy": 1}}
    args = (".", {"mistake_costs": {}}, candidate, ["screen"], refs,
            [{"id": "toy"}], settled, predictions, {"panel_sha256": "sha256:toy"},
            {"member": "toy", "seed": 1})
    return args


def test_v3_terms_share_registered_scorer_and_gate(monkeypatch):
    args = _toy_evaluation(monkeypatch)
    # A-Q = geometric mean of a=0.8 and q=0.5, using the registered candidate.
    result = v3.evaluate_member(*args)
    assert result["status"] == "SCORED"
    assert result["a"] == pytest.approx(0.8)
    assert result["q"] == pytest.approx(0.5)
    assert result["raw_score"] == pytest.approx((0.8 * 0.5) ** 0.5)
    assert result["g_feas"] == 0
    monkeypatch.setattr(v3.tuning, "false_feasible_rate", lambda *args: 0.2)
    failed = v3.evaluate_member(*args)
    assert failed["status"] == "INELIGIBLE"
    assert failed["gate_verdict"] == "FAIL"


def test_reference_failure_never_becomes_candidate_failure(monkeypatch):
    args = _toy_evaluation(monkeypatch)
    refs = {**args[4], "screen": {**args[4]["screen"], "status": "FAILED_INFRA"}}
    result = v3.evaluate_member(*args[:4], refs, *args[5:])
    assert result["status"] == "FAILED_INFRA"
    assert result["eligible"] is None
    predictions = {**args[7], "q3": {"toy": float("nan")}}
    result = v3.evaluate_member(*args[:7], predictions, *args[8:])
    assert result["status"] == "INELIGIBLE"
    assert result["cause"] == "candidate_prediction_invalid"


def test_unresolved_could_change_q3_best_is_unmeasured(monkeypatch):
    from carbon.battery.value import quiz

    candidates = [
        {"id": "a", "c1": 0.5, "c2": 0.2},
        {"id": "b", "c1": 0.6, "c2": 0.2},
    ]
    monkeypatch.setattr(quiz, "q3_candidates", lambda: candidates)
    monkeypatch.setattr(quiz, "q3_grid", lambda contract, scenario: [{"case_id": "a"}, {"case_id": "b"}])
    monkeypatch.setattr(v3.d, "assess_reference", lambda *args: {
        "a": {"status": v3.d.FEASIBLE, "objective": 10.0},
        "b": {"status": v3.d.UNRESOLVED, "objective": 9.0},
    })
    monkeypatch.setattr(quiz, "q3_judge", lambda *args: {"kind": "SELECTED_FEASIBLE", "decision_loss": 0.0})
    with pytest.raises(v3.Refused, match="q3_reference_could_change_best"):
        v3._q3_outcomes({}, [{"id": "toy"}], {"a": {}, "b": {}}, {})


def test_run5_correlation_waits_for_all_eight_same_panel(tmp_path):
    q1 = v3.ROOT / "docs/development/evidence/graphite-run5-q1/q1-report.json"
    missing = v3.compare_run5(q1, [])
    assert missing["expected_members"] == 8
    assert missing["v2"]["kendall_tau_b"] == pytest.approx(-0.47280542884465016)
    assert missing["v3"] is None
    source = json.loads(q1.read_text())
    paths = []
    for member in source["one_seed"]["members_ranked"]:
        row = source["members"][member]
        path = tmp_path / (member + ".json")
        path.write_text(json.dumps({
            "status": "SCORED", "recipe": {"member": member, "seed": row["seed"]},
            "identity": {"panel_sha256": "sha256:toy"},
            "raw_score": -row["development_decision_loss"],
        }))
        paths.append(path)
    matched = v3.compare_run5(q1, paths)
    assert matched["status"] == "SCORED"
    assert matched["v3"]["kendall_tau_b"] == pytest.approx(1.0)
    paths.pop()
    assert v3.compare_run5(q1, paths)["v3"] is None
