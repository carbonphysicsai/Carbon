"""SCORE-PROOF-01 amendment 13: the always-abstain control (RES-07, #1209)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import experiment as ex
from carbon.battery.value import panel as pn

ROOT = Path(__file__).resolve().parents[2]
EV4 = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
REFS = ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"


def references():
    out = {}
    for line in gzip.decompress(REFS.read_bytes()).decode().splitlines():
        if line.strip():
            record = json.loads(line)
            out[record["case_id"]] = record
    return out


def test_the_control_never_picks_on_real_ev4_references():
    contract, _ = ev.load(EV4)
    candidates = ev.candidates(contract)
    refs = references()
    decided = 0
    for scenario in ev.scenarios(contract):
        preds = {}
        for candidate in candidates:
            for index in range(len(scenario["conditions"])):
                case_id = ev.case_id(contract, scenario, candidate, index)
                record = refs.get(case_id)
                if record is not None and record.get("status") == "OK":
                    preds[case_id] = pn.always_abstain(record["outputs"])
        quantities = ex._quantities(contract, preds, scenario, candidates)
        if quantities is None:
            continue
        predicted = d.assess_predicted(contract, scenario, candidates, quantities)
        assert d.select(candidates, predicted) is None, scenario["id"]
        decided += 1
    assert decided > 0


def test_its_decisions_match_decision_outcome_with_no_selection():
    contract, _ = ev.load(EV4)
    results = {
        "decisions": {"m": {"S1": {}, "S2": {}, "S3": {}}},
        "references": {
            "S1": {"split": "development", "best_in_tested_set": "c1=1.5,c2=0.6",
                   "status_counts": {"FEASIBLE": 4, "INFEASIBLE": 30, "UNRESOLVED": 1}},
            "S2": {"split": "development", "best_in_tested_set": None,
                   "status_counts": {"FEASIBLE": 0, "INFEASIBLE": 35, "UNRESOLVED": 0}},
            "S3": {"split": "development", "best_in_tested_set": None,
                   "status_counts": {"FEASIBLE": 0, "INFEASIBLE": 34, "UNRESOLVED": 1}},
            "LEG": {"split": "development", "best_in_tested_set": "x",
                    "status_counts": {}},
        },
    }  # fmt: skip
    out = pn.abstain_decisions(contract, results)
    assert set(out) == {"S1", "S2", "S3"}  # never a scenario nobody was decided on
    assert out["S1"]["outcome"]["kind"] == "MISSED_OPPORTUNITY"
    assert (
        out["S1"]["outcome"]["decision_loss"]
        == contract["mistake_costs"]["missed_opportunity"]
    )
    assert (out["S2"]["outcome"]["kind"], out["S2"]["outcome"]["decision_loss"]) == (
        "CORRECT_ABSTENTION",
        0.0,
    )
    assert (out["S3"]["outcome"]["kind"], out["S3"]["outcome"]["decision_loss"]) == (
        "ABSTENTION_UNRESOLVED",
        None,
    )


def test_it_is_known_bad_in_the_screen_and_outside_frozen_panels():
    from scripts.dev.battery import score_proof as script

    members = json.loads(script.MEMBERS.read_text())
    assert script.MEMBERS.name == "proof-members-v2.json"
    assert "control-always_abstain" in members["roles"]["known_bad"]
    v1 = json.loads((script.MEMBERS.parent / "proof-members-v1.json").read_text())
    assert members["roles"]["known_bad"][:-1] == v1["roles"]["known_bad"]
    assert "always_abstain" not in pn.CONTROLS and pn.SCREEN_CONTROLS == (
        "always_abstain",
    )
