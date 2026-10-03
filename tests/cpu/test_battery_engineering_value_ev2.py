"""EV2: the wider, per-condition decision and the decision-aware component.

Fixture checks only (no PyBaMM): the EV2 contract is valid and leaves EV1
unchanged; the decision-agreement component scores constraint calls with the
contract's own bands and costs; decision-aware profiles use it and nothing
else changes; the experiment runs EV2 end to end through the real path and
reports the pre-registered boundary-optimist check.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_engineering_value import (
    FixtureBackend,
    fixture_solver,
    scoring_refs,  # noqa: F401 - fixture
)

from carbon.battery.value import contract as ev
from carbon.battery.value import panel as pn
from carbon.battery.value import scoring as sc
from carbon.battery.value.experiment import Experiment

EV2_PATH = ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json"
EV1_DIGEST = "sha256:292c0473f295ac5898845b2a75b05e9cf6d843722fecd3812ad79abe7ea8d0f9"
EV2, EV2_DIGEST = ev.load(EV2_PATH)


def test_ev2_is_valid_and_leaves_ev1_unchanged():
    ev1, digest = ev.load()
    assert digest == EV1_DIGEST  # EV1's frozen identity (its retained evidence)
    assert ev.decision_cases(ev1)[0]["case_id"].startswith("ev1:")
    assert [m for m, *_ in pn.members()] == [m for m, *_ in pn.members("ev1")]
    assert len(ev.candidates(EV2)) == 35
    assert len(ev.decision_cases(EV2)) == 560
    assert all(c["case_id"].startswith("ev2:") for c in ev.decision_cases(EV2))
    assert all(len(s["conditions"]) == 1 for s in ev.scenarios(EV2))
    ev1_conditions = {tuple(c) for s in ev.scenarios(ev1) for c in s["conditions"]}
    ev2_conditions = {tuple(c) for s in ev.scenarios(EV2) for c in s["conditions"]}
    assert not ev1_conditions & ev2_conditions
    # Unchanged from EV1: every rule that shapes a decision's outcome.
    for key in ("objective", "constraints", "mistake_costs", "baseline", "tie_rule"):
        if key == "objective":
            assert {
                k: v for k, v in EV2[key].items() if k not in ("name", "definition")
            } == {k: v for k, v in ev1[key].items() if k not in ("name", "definition")}
        else:
            assert EV2[key] == ev1[key]
    assert EV2["reference"]["uncertainty"] == ev1["reference"]["uncertainty"]
    assert (
        EV2["scoring_candidates"]["weight_profiles"]
        == ev1["scoring_candidates"]["weight_profiles"]
    )


def test_the_ev2_panel_adds_families_and_keeps_ev1s():
    ev1 = pn.members("ev1")
    ev2 = pn.members("ev2")
    assert ev2[: len(ev1)] == ev1
    families = {family for _m, family, *_ in ev2} - {family for _m, family, *_ in ev1}
    assert families == {"deeponet", "mlp_wide", "knn15"}
    assert len(ev2) <= EV2["budgets"]["reconstructions_max"]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda c: c.update(case_prefix="ev9"), "case_prefix"),
        (lambda c: c.update(panel="all"), "panel"),
        (
            lambda c: c["scoring_candidates"]["decision_aware_profiles"].append(
                c["scoring_candidates"]["weight_profiles"][1]
            ),
            "profile_duplicate",
        ),
    ],
)
def test_the_new_contract_fields_are_refused_by_name(mutate, code):
    document = copy.deepcopy(EV2)
    mutate(document)
    with pytest.raises(ev.ContractError) as refused:
        ev.validate(document)
    assert refused.value.code == code


def _scoring():
    store, case_ids, _ = sc.scoring_set(REPOSITORY)
    return store, case_ids


def _shifted(store, case_ids, plating=0.0, temperature=0.0):
    out = {}
    for case_id in case_ids:
        o = copy.deepcopy(store.refs[case_id]["outputs"])
        o["plating_margin_v"] += plating
        o["temperature_c"] = [o["temperature_c"][0]] + [
            t + temperature for t in o["temperature_c"][1:]
        ]
        out[case_id] = o
    return out


def test_decision_agreement_uses_the_contracts_bands_and_asymmetric_costs():
    store, case_ids = _scoring()
    exact = sc.decision_agreement(EV2, _shifted(store, case_ids), case_ids, store)
    assert exact["score"] == 1.0
    assert exact["false_acceptances"] == exact["false_rejections"] == 0
    # Optimism near the limits becomes false acceptances (cost 10 each);
    # the mirror-image pessimism becomes false rejections (cost 1 each).
    optimistic = sc.decision_agreement(
        EV2, _shifted(store, case_ids, plating=0.01, temperature=-3.0), case_ids, store
    )
    pessimistic = sc.decision_agreement(
        EV2, _shifted(store, case_ids, plating=-0.01, temperature=3.0), case_ids, store
    )
    assert optimistic["false_acceptances"] > 0 and optimistic["false_rejections"] == 0
    assert pessimistic["false_rejections"] > 0 and pessimistic["false_acceptances"] == 0
    assert optimistic["score"] < pessimistic["score"] < 1.0
    # Unresolved reference calls are excluded, never forced either way.
    assert exact["calls"] < 3 * len(case_ids)
    # A missing prediction is not measured, never scored as perfect.
    partial = dict(list(_shifted(store, case_ids).items())[1:])
    assert sc.decision_agreement(EV2, partial, case_ids, store) is None


def test_decision_aware_profiles_use_only_the_decision_leg():
    component = {
        "eligible": True,
        "E": 0.25,
        "E_important": 0.5,
        "decision": {"score": 0.8},
    }
    scores = sc.rule_scores(EV2, component)
    assert scores["dar-p0-r100-a0"] == pytest.approx(0.8)
    assert scores["p0-r30-a70"] == pytest.approx((1 / 1.5) ** 0.3 * (1 / 1.25) ** 0.7)
    assert scores["dar-p0-r30-a70"] == pytest.approx(0.8**0.3 * (1 / 1.25) ** 0.7)
    assert scores["p45-r30-a25"].startswith("NOT_MEASURABLE")
    unmeasured = sc.rule_scores(EV2, {**component, "decision": None})
    assert unmeasured["dar-p0-r100-a0"].startswith("NOT_MEASURABLE")
    ineligible = sc.rule_scores(EV2, {**component, "eligible": False})
    assert ineligible["dar-p0-r100-a0"] == 0.0


def test_ev2_runs_end_to_end_with_the_boundary_optimist_check(
    tmp_path, scoring_refs  # noqa: F811
):
    experiment = Experiment(tmp_path / "ev2", repository=REPOSITORY)
    experiment.freeze(EV2_PATH)
    backend = FixtureBackend(scoring_refs)
    result = experiment.run(solver=fixture_solver, backend=backend, workers=2)
    assert result["status"] == "EVALUATED"
    status = experiment.status()
    assert status["references"]["terminal"] == 560
    results = json.loads((tmp_path / "ev2" / "results" / "results.json").read_text())
    assert {
        m for m in results["summary"]["members"] if not m.startswith("control-")
    } == {m for m, *_ in pn.members("ev2")}
    for rule in ("dar-p0-r100-a0", "dar-p0-r30-a70", "dar-p0-r50-a50"):
        assert rule in results["comparison"]
    check = results["summary"]["boundary_optimist_check"]
    assert set(check) == set(results["comparison"])
    assert check["p45-r30-a25"] is None
    row = check["dar-p0-r100-a0"]
    assert row["eligible_members"] > 0
    report = (tmp_path / "ev2" / "results" / "report.md").read_text()
    assert "boundary-optimist control below every eligible model" in report
