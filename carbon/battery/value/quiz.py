"""The battery near-limit quiz: Q2 (per-case) and Q3 (decision scenarios).

The designs, sizes and rules come from the quiz registries
(`docs/development/evidence/battery-quiz-designs/quiz-registry-v3`..`v6`),
which were registered before any computation and compared on the public
stand-in. This module is the shared definition. The Validator's producer,
validator and tuning plumbing (VALIDATOR-19 slice Q) and the score-tuning
loop call it, so a quiz case or verdict means one thing everywhere.

- **Q2.** Within `Q2_POOL_BANDS` contract bands of the plating or thermal
  limit, on either side (`q2_near`), the cases where a versioned public
  panel splits most evenly between calling them feasible and infeasible
  (`q2_select`). Each candidate model is then measured on them
  (`q2_measures`).
- **Q3.** One operating condition per scenario, decided by the candidate
  model inside EV4's fixed decision rules over a pre-solved 35-candidate
  reference grid (`q3_grid`, `q3_judge`). Scenarios whose grid has no
  feasible design are excluded (`q3_feasible`, quiz-registry-v5).
  `q3_measures` gives decision false-feasible, regret and over-caution.

Every margin, cutoff and threshold that would gate a score stays
HUMAN_INPUT. Nothing here chooses one. DEVELOPMENT; no LIVE authority.
"""

from __future__ import annotations

import statistics

from . import contract as ev
from . import decision as d
from . import false_acceptance as fa
from . import margins

#: quiz-registry-v3/v5 and the agreed sizes (Test Lead, 2026-10-06): Q2 takes
#: 80 cases from a near-limit pool of about 320, within 4 bands.
Q2_POOL_BANDS = 4.0
Q2_N = 80
Q2_POOL = 320
#: quiz-registry-v4/v5: 8 decision scenarios per batch, all-infeasible ones
#: excluded.
Q3_K = 8
#: The disagreement panel is versioned (disagreement-panel-v1.json).
PANEL_VERSION = 1


def _feasible_call(contract, outputs, bands=None):
    verdicts = d.check(contract, d.measure(contract, outputs), bands)
    return all(v == d.PASS for v in verdicts.values()), verdicts


# --- Q2 --------------------------------------------------------------------------------


def q2_near(contract, reference_record, bands=Q2_POOL_BANDS):
    """Whether a reference lies within `bands` contract bands of the plating
    or peak-temperature limit, on either side. An unavailable reference is
    never near (it cannot be a quiz case)."""
    outputs = reference_record.get("outputs")
    if reference_record.get("status", "OK") != "OK" or outputs is None:
        return False
    values = margins._margins(contract, outputs)
    return min(abs(v) for v in values.values()) <= bands


def q2_select(contract, pool_ids, panel_predictions, n=Q2_N):
    """The `n` pool cases where the panel splits most evenly between calling
    the case feasible and infeasible. Deterministic: ties go to the lower case
    id. A case some panel member did not predict is skipped. No reference is
    read: the selection never sees the answers."""
    scored = []
    for case_id in sorted(pool_ids):
        calls = []
        for predictions in panel_predictions.values():
            outputs = predictions.get(case_id)
            if outputs is None:
                break
            calls.append(_feasible_call(contract, outputs)[0])
        else:
            if calls:
                share = sum(calls) / len(calls)
                scored.append((abs(share - 0.5), case_id))
    return [case_id for _gap, case_id in sorted(scored)[:n]]


def q2_measures(contract, predictions, quiz_ids, refs):
    """A model's quiz measures. Each is None when unmeasurable (a missing
    prediction, or no reference case of that kind):
    - `false_feasible` (G-FEAS): of the reference-infeasible cases (any
      constraint FAILs, contract bands), the share it calls feasible;
    - `plating_fa` (G-PLATE): of the reference plating FAILs, the share it
      calls PASS;
    - `false_infeasible`: of the reference-feasible cases, the share it calls
      infeasible."""
    bands = contract["reference"]["uncertainty"]["bands"]
    infeasible = accepted = feasible = rejected = 0
    for case_id in quiz_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return {
                "false_feasible": None,
                "plating_fa": None,
                "false_infeasible": None,
            }
        truth = d.check(contract, d.measure(contract, reference), bands)
        said, _ = _feasible_call(contract, outputs)
        if any(v == d.FAIL for v in truth.values()):
            infeasible += 1
            accepted += said
        elif all(v == d.PASS for v in truth.values()):
            feasible += 1
            rejected += not said
    component = fa.component(contract, predictions, list(quiz_ids), refs)
    plating = (
        None
        if component is None
        else component["constraints"]["no_plating_onset"]["false_acceptance_rate"]
    )
    return {
        "false_feasible": accepted / infeasible if infeasible else None,
        "plating_fa": plating,
        "false_infeasible": rejected / feasible if feasible else None,
    }


# --- Q3 --------------------------------------------------------------------------------


def q3_scenario(scenario_id, condition):
    """A Q3 scenario: one opaque id and one (t_amb_c, soc0) condition."""
    t_amb_c, soc0 = condition
    return {"id": scenario_id, "conditions": [[float(t_amb_c), float(soc0)]]}


def q3_grid(contract, scenario):
    """The reference jobs for a scenario: every candidate on the contract's
    grid at its condition. Case ids carry no reference information
    (`contract.case_id`)."""
    t_amb_c, soc0 = scenario["conditions"][0]
    return [
        {
            "case_id": ev.case_id(contract, scenario, candidate, 0),
            "c1": candidate["c1"],
            "c2": candidate["c2"],
            "t_amb_c": float(t_amb_c),
            "soc0": float(soc0),
        }
        for candidate in ev.candidates(contract)
    ]


def _reference(contract, scenario, grid_refs):
    candidates = ev.candidates(contract)
    refs = {}
    for candidate in candidates:
        case_id = ev.case_id(contract, scenario, candidate, 0)
        if case_id in grid_refs:
            refs[(candidate["id"], 0)] = grid_refs[case_id]
    return candidates, d.assess_reference(contract, scenario, candidates, refs)


def q3_feasible(contract, scenario, grid_refs):
    """Whether the scenario's reference grid holds at least one feasible
    design. An all-infeasible scenario is excluded from the quiz
    (quiz-registry-v5)."""
    candidates, reference = _reference(contract, scenario, grid_refs)
    return d.best_in_set(candidates, reference) is not None


def q3_judge(contract, scenario, grid_predictions, grid_refs):
    """The model's decision in a scenario under EV4's fixed rules (predicted
    assessment, selection with the contract's tie rule and abstention), judged
    against the reference grid: `{kind, decision_loss, selected}`."""
    candidates, reference = _reference(contract, scenario, grid_refs)
    baseline_id = ev.candidate_id(contract["baseline"]["protocol"])
    quantities = {}
    for candidate in candidates:
        outputs = grid_predictions.get(ev.case_id(contract, scenario, candidate, 0))
        if outputs is None:
            best = d.best_in_set(candidates, reference)
            return {
                "kind": "MODEL_OUTPUT_MISSING",
                "selected": None,
                "decision_loss": (
                    contract["mistake_costs"]["missed_opportunity"] if best else 0.0
                ),
            }
        quantities[(candidate["id"], 0)] = d.measure(contract, outputs)
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    selection = d.select(candidates, predicted)
    result = d.outcome(contract, candidates, selection, reference, baseline_id)
    return {
        "kind": result["kind"],
        "selected": result.get("selected"),
        "decision_loss": result["decision_loss"],
    }


def q3_measures(outcomes):
    """Over a model's outcomes on feasible scenarios (resolved ones only):
    `false_feasible` (picks the reference shows infeasible), `regret` (mean
    decision loss) and `over_caution` (missed opportunities). None when no
    outcome is resolved."""
    resolved = [o for o in outcomes if o["decision_loss"] is not None]
    if not resolved:
        return {"false_feasible": None, "regret": None, "over_caution": None}
    return {
        "false_feasible": sum(o["kind"] == "SELECTED_INFEASIBLE" for o in resolved)
        / len(resolved),
        "regret": statistics.fmean(o["decision_loss"] for o in resolved),
        "over_caution": sum(o["kind"] == "MISSED_OPPORTUNITY" for o in resolved)
        / len(resolved),
    }
