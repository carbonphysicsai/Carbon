"""PUBLIC-DEV-DECISIONS-01: VERIFY-R on the LEG half of the public questions,
value on the VALUE half, never both (synthetic references and predictions)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_tuning_quiz import truth

from carbon.battery.value import contract as ev
from scripts.dev.battery import verify_r_public as vp

SPLIT = json.loads(vp.SPLIT.read_text())


def contract(n):
    base, _ = ev.load(
        REPOSITORY / "carbon/battery/value/contracts/ev4-dev-proof-v1.json"
    )
    base = json.loads(json.dumps(base))
    base["scenarios"]["development"] = [
        {"id": f"D-{k:04d}", "conditions": [[10.25 + k, 0.2 + 0.01 * k]]}
        for k in range(n)
    ]
    base["scenarios"]["verification"] = []
    return base


def refs_and_predictions(c, shift):
    refs, preds = {}, {}
    for s in ev.scenarios(c, "development"):
        for cand in ev.candidates(c):
            case = ev.case_id(c, s, cand, 0)
            t, soc = s["conditions"][0]
            job = {
                "case_id": case,
                "c1": cand["c1"],
                "c2": cand["c2"],
                "t_amb_c": t,
                "soc0": soc,
            }
            refs[case] = {"case_id": case, "status": "OK", "outputs": truth(job, ())}
            out = truth(job, ())
            out["plating_margin_v"] += shift
            preds[case] = out
    return refs, preds


def test_the_split_puts_every_question_on_one_side_only():
    c = contract(40)
    ids = [s["id"] for s in ev.scenarios(c, "development")]
    leg = {i for i in ids if vp.side(SPLIT, i) == "LEG"}
    value = {i for i in ids if vp.side(SPLIT, i) == "VALUE"}
    assert leg and value and not leg & value and leg | value == set(ids)
    results = {"decisions": {"m": {i: {"split": "development"} for i in ids}}}
    kept = vp.value_results(results, value)
    assert set(kept["decisions"]["m"]) == value
    assert kept["value_split"]["rule"] == "public-dev-split-v1"


def test_verify_r_scores_the_leg_questions_on_the_35_action_bank():
    c = contract(6)
    refs, oracle = refs_and_predictions(c, 0.0)
    _, optimist = refs_and_predictions(c, 0.05)
    leg = [s for s in ev.scenarios(c, "development")]
    legs, diagnostics = vp.legs_from(
        c, leg, {"oracle": oracle, "optimist": optimist}, refs, "r"
    )
    assert legs["v3"]["oracle"] == 1.0
    assert legs["v3"]["optimist"] == 0.5
    assert "control-oracle" in legs["v3"]
    assert diagnostics["v3"]["questions"] == 6
    assert diagnostics["v3"]["budget_stopped"] == 0
