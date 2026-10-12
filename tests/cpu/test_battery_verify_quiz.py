"""VERIFY-R on the Q3 quiz (registry v8, OWNER-VERIFY-R-DEFAULTS-01).

Every quiz here is the scripted two-scenario quiz of the tuning quiz tests:
a Q3 lattice point plates when c1 >= 1.5, and charges faster as c1 + c2
grows, so the best feasible design is c1 = 1.375, c2 = 1.0. Nothing is
solved and no real quiz is read.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_tuning_quiz import _member, _quiz_work, truth

from carbon.battery import quiz_stratum as qs
from carbon.battery.value import decision as d
from carbon.battery.value import score_tuning as st
from carbon.battery.value import verify_quiz as vq
from carbon.challenge_validator import tuning

REGISTRIES = REPOSITORY / "docs/development/evidence/battery-score-tuning"


@pytest.fixture
def quiz(tmp_path):
    work, document = _quiz_work(tmp_path)
    contract = qs.contract(REPOSITORY)
    refs = tuning.quiz_references(work, document, contract)
    return work, document, contract, refs


def near_miss(document):
    """Predicts the c1 = 1.5 column feasible (it plates): its first pick is
    infeasible, but its third is the best feasible design."""
    predictions = _member(document, 0.0)
    for case_id, x in qs.inputs(document).items():
        if case_id.startswith("ev4:") and x["c1"] == 1.5:
            predictions[case_id]["plating_margin_v"] = 0.01
    return predictions


def scores(quiz, members):
    _work, document, contract, refs = quiz
    return vq.member_scores(contract, document["q3"], members, refs, "sha256:quiz")


def test_the_owner_values_are_registered_and_k_is_closed():
    assert vq.K_POINTS == (1, 3, 5)
    assert vq.WALL_PER_PANEL_S == 120.0 and vq.REGRET_UNIT_S == 1200.0
    rule = vq.rule(3)
    assert rule["k"] == 3
    assert rule["budget"] == {"complete_panels": 3, "wall_s": 360.0, "core_s": 360.0}
    assert rule["regret_unit"] == {"value": 1200.0, "unit": "s"}
    with pytest.raises(vq.VerifyQuizRefused):
        vq.rule(2)


def test_verify_r_rewards_finding_a_feasible_design_within_k(quiz):
    _work, document, _contract, _refs = quiz
    legs, diagnostics = scores(
        quiz,
        {
            "oracle": _member(document, 0.0),
            "optimist": _member(document, 0.05),
            "pessimist": _member(document, -0.05),
            "near-miss": near_miss(document),
        },
    )
    # The oracle's first pick is the best feasible design: no regret.
    assert {leg: legs[leg]["oracle"] for leg in vq.LEG.values()} == dict.fromkeys(
        ("v1", "v3", "v5"), 1.0
    )
    # The optimist's top five all plate, the pessimist commits nothing:
    # nothing verified, bounded regret 1, v = 1 / 2.
    for member in ("optimist", "pessimist"):
        assert all(legs[leg][member] == 0.5 for leg in vq.LEG.values())
    # The near miss: wrong at k = 1, recovered by verification at k = 3.
    assert legs["v1"]["near-miss"] == 0.5
    assert legs["v3"]["near-miss"] == legs["v5"]["near-miss"] == 1.0
    for leg in vq.LEG.values():
        assert diagnostics[leg]["questions"] == 2
        assert diagnostics[leg]["overhead_charged"] is False
        # The scripted records carry no wall time: charged at the bound.
        assert diagnostics[leg]["cost_unmeasured_panels"] == 2 * 117
        assert diagnostics[leg]["budget_stopped"] == 0


def test_the_first_committed_point_is_the_q3_pick(quiz):
    _work, document, contract, _refs = quiz
    for entry in document["q3"]:
        scenario = qs.scenario(entry)
        for predictions in (_member(document, 0.0), near_miss(document)):
            order = vq.ordered_actions(contract, scenario, predictions)
            lattice = vq._lattice(contract, scenario)
            quantities = {
                (c["id"], 0): d.measure(contract, predictions[case_id])
                for c, case_id in lattice
            }
            candidates = [c for c, _ in lattice]
            predicted = d.assess_predicted(contract, scenario, candidates, quantities)
            assert order[0] == d.select(candidates, predicted)
            assert len(order) == len(set(order))


def test_a_missing_prediction_leaves_the_leg_unscored(quiz):
    _work, document, _contract, _refs = quiz
    partial = _member(document, 0.0)
    partial.pop(next(c for c in partial if c.startswith("ev4:")))
    legs, _ = scores(quiz, {"partial": partial})
    assert all(legs[leg]["partial"] is None for leg in vq.LEG.values())


def test_a_slow_reference_solve_does_not_stop_the_list(quiz):
    """Amendment 9: every panel is charged the registered 120 s, so the budget
    is exactly k panels; a slow recorded solve is counted, never charged."""
    _work, document, contract, refs = quiz
    slow = {c: {**r, "wall_s": 200.0} for c, r in refs.items()}
    near = near_miss(document)
    legs, diagnostics = vq.member_scores(
        contract,
        document["q3"],
        {"oracle": _member(document, 0.0), "near-miss": near},
        slow,
        "q",
    )
    assert legs["v1"]["oracle"] == legs["v3"]["oracle"] == 1.0
    # The near miss still needs k = 3 to recover; k = 1 still fails.
    assert legs["v1"]["near-miss"] == 0.5 and legs["v3"]["near-miss"] == 1.0
    for leg in vq.LEG.values():
        assert diagnostics[leg]["budget_stopped"] == 0
        assert diagnostics[leg]["panels_over_allotment"] == 2 * 117
        assert diagnostics[leg]["cost_unmeasured_panels"] == 0


def test_the_cli_writes_owner_only_legs_with_the_controls(tmp_path, quiz):
    from scripts.dev.battery import verify_r_quiz

    quiz_dir, document, _contract, _refs = quiz
    work = tuning._owner_only_dir(tmp_path / "work")
    folder = tuning._owner_only_dir(work / "quiz-predictions")
    tuning._write_private(
        folder / "oracle.json",
        {
            "member": "oracle",
            "quiz_digest": qs.digest(document),
            "predictions": _member(document, 0.0),
        },
    )
    assert verify_r_quiz.main(["--work", str(work), "--quiz", str(quiz_dir)]) == 0
    out = work / "verify-r.json"
    assert stat.S_IMODE(os.lstat(out).st_mode) == 0o600
    result = json.loads(out.read_text())
    assert result["quiz_digest"] == qs.digest(document)
    assert result["legs"]["v3"]["oracle"] == 1.0
    assert "control-oracle" in result["legs"]["v3"]
    assert set(result["legs"]) == {"v1", "v3", "v5"}


def test_registry_v8_keeps_v7_and_adds_verify_r():
    v7, _ = st.load_registry(REGISTRIES / "registry-v7.json")
    v8, _ = st.load_registry(REGISTRIES / "registry-v8.json")
    assert {k: v for k, v in v8.items() if k in v7} == v7
    grid = ("0.005", "0.01", "0.02", "0.05", "0.1", "1.01")
    assert set(v8) - set(v7) == {
        "VERIFY-R-k1",
        "VERIFY-R-k3",
        "VERIFY-R-k5",
        "A-VERIFY-R-k3",
        *(f"G-FEAS+ENV/VERIFY-R-k3@{c}" for c in grid),
        *(f"G-FEAS+ENV/A-VERIFY-R-k3@{c}" for c in grid),
    }
    assert v8["VERIFY-R-k3"].weights == {"v3": 1.0}
    assert v8["A-VERIFY-R-k3"].weights == {"a": 0.5, "v3": 0.5}
    row = {"eligible": True, "E": 0.1, "legs": {"a": 0.64, "v3": 0.81}}
    assert st.score_member(v8["VERIFY-R-k3"], row) == pytest.approx(0.81)
    assert st.score_member(v8["A-VERIFY-R-k3"], row) == pytest.approx(0.72)
    # Without the VERIFY-R legs the candidates are unscored, never guessed;
    # every earlier candidate ignores the new legs.
    assert st.score_member(v8["VERIFY-R-k3"], {**row, "legs": {"a": 0.64}}) is None
    assert st.score_member(v8["A"], {**row, "legs": {"a": 0.64}}) == pytest.approx(0.64)


def test_member_legs_adds_only_registered_verify_legs():
    with pytest.raises(st.TuningError):
        st.member_legs(None, {}, None, [], None, {"v2": 0.9})


def test_the_score_proof_reads_registry_v8():
    from scripts.dev.battery import score_proof
    from scripts.dev.battery import tuning_rescore as tr

    assert score_proof.REGISTRY.name == "registry-v8.json"
    assert tr.verify_of(None, "m") is None
    assert tr.verify_of({"v1": {"m": 0.9}, "v3": {}}, "m") == {"v1": 0.9, "v3": None}


def test_truth_is_the_scripted_reference():
    # Guards the fixture assumption the expectations above rest on.
    job = {"case_id": "ev4:x", "t_amb_c": 20.0, "soc0": 0.3, "c1": 1.5, "c2": 1.0}
    assert truth(job, ())["plating_margin_v"] < 0
