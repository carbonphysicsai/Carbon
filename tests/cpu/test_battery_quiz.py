"""The battery quiz library, on committed public references (EV4's decision
references and the scoring set). No sealed material."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from carbon.battery.value import contract as ev
from carbon.battery.value import panel as pn
from carbon.battery.value import quiz
from carbon.battery.value import scoring as sc

ROOT = Path(__file__).resolve().parents[2]
CONTRACT, _ = ev.load(
    ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
)


@pytest.fixture(scope="module")
def scoring():
    store, ids, _ = sc.scoring_set(ROOT)
    return store, ids[:300]


@pytest.fixture(scope="module")
def ev4_refs():
    path = (
        ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
    )
    out = {}
    for line in gzip.decompress(path.read_bytes()).decode().splitlines():
        if line.strip():
            record = json.loads(line)
            out[record["case_id"]] = record
    return out


def test_q2_near_widens_with_the_band_and_skips_unavailable(scoring):
    store, ids = scoring
    near1 = {c for c in ids if quiz.q2_near(CONTRACT, store.refs[c], 1.0)}
    near4 = {c for c in ids if quiz.q2_near(CONTRACT, store.refs[c])}
    assert near1 <= near4 and near4
    assert not quiz.q2_near(CONTRACT, {"status": "REFERENCE_SOLVER_FAILED"})


def test_q2_select_is_deterministic_and_reads_no_reference(scoring):
    store, ids = scoring
    pool = [c for c in ids if quiz.q2_near(CONTRACT, store.refs[c])]
    panel = {
        kind: pn.control_predictions(kind, store.refs)
        for kind in ("oracle", "conservative", "boundary_optimist")
    }
    first = quiz.q2_select(CONTRACT, pool, panel, n=20)
    assert first == quiz.q2_select(CONTRACT, list(reversed(pool)), panel, n=20)
    assert len(first) == min(20, len(pool)) and set(first) <= set(pool)


def test_q2_measures_known_answers(scoring):
    store, ids = scoring
    pool = [c for c in ids if quiz.q2_near(CONTRACT, store.refs[c])]
    oracle = pn.control_predictions("oracle", store.refs)
    optimist = pn.control_predictions("boundary_optimist", store.refs)
    o = quiz.q2_measures(CONTRACT, oracle, pool, store.refs)
    b = quiz.q2_measures(CONTRACT, optimist, pool, store.refs)
    assert o["false_feasible"] == 0.0 and o["false_infeasible"] == 0.0
    assert b["false_feasible"] > o["false_feasible"]
    missing = quiz.q2_measures(CONTRACT, {}, pool, store.refs)
    assert missing == {
        "false_feasible": None,
        "plating_fa": None,
        "false_infeasible": None,
    }


def _ev4_scenario(contract, sid):
    scenario = next(s for s in ev.scenarios(contract) if s["id"] == sid)
    return scenario


def test_q3_grid_judge_and_measures_on_ev4_references(ev4_refs):
    # EV4's verification scenario V-T9-S0.40 has a feasible design; V-T9-S0.06
    # has none (the committed references).
    feasible = _ev4_scenario(CONTRACT, "V-T9-S0.40")
    none = _ev4_scenario(CONTRACT, "V-T9-S0.06")
    grid = quiz.q3_grid(CONTRACT, feasible)
    assert len(grid) == 35 and all("V-T9-S0.40" in j["case_id"] for j in grid)
    assert quiz.q3_feasible(CONTRACT, feasible, ev4_refs)
    assert not quiz.q3_feasible(CONTRACT, none, ev4_refs)
    oracle = {j["case_id"]: ev4_refs[j["case_id"]]["outputs"] for j in grid}
    judged = quiz.q3_judge(CONTRACT, feasible, oracle, ev4_refs)
    assert judged["kind"] == "SELECTED_FEASIBLE" and judged["decision_loss"] == 0.0
    missing = quiz.q3_judge(CONTRACT, feasible, {}, ev4_refs)
    assert missing["kind"] == "MODEL_OUTPUT_MISSING"
    measures = quiz.q3_measures(
        [judged, {"kind": "SELECTED_INFEASIBLE", "decision_loss": 10.0}]
    )
    assert measures == {"false_feasible": 0.5, "regret": 5.0, "over_caution": 0.0}
    assert quiz.q3_measures([{"kind": "X", "decision_loss": None}])["regret"] is None


def test_q3_scenario_is_one_condition():
    scenario = quiz.q3_scenario("Q3-opaque", (12.5, 0.33))
    assert scenario == {"id": "Q3-opaque", "conditions": [[12.5, 0.33]]}
    assert len(quiz.q3_grid(CONTRACT, scenario)) == 35
